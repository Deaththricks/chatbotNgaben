"""Custom actions for the GraphRAG Ngaben bot using Neo4j and Qwen via Ollama."""
import functools
import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Text, Optional

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from rapidfuzz import fuzz

from kb_resolver import _ortho_key, get_resolver
from kb_content import PART_IS_SUBJECT, PREDICATE_FAMILIES, get_content

load_dotenv(find_dotenv())

_BOT_DIR = Path(__file__).resolve().parent
_REFUSAL_LOG_PATH = _BOT_DIR / "llm_refusal_log.jsonl"
_UNRESOLVED_LOG_PATH = _BOT_DIR / "unresolved_log.jsonl"
_NEO4J_ERROR_LOG_PATH = _BOT_DIR / "neo4j_error_log.jsonl"

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Initialize Qwen via Ollama. The context window is set explicitly: Ollama's default is
# 4096 tokens, and a prompt about a hub term (ngaben) went over it -- llama.cpp then keeps
# the first 4 and the last ~2046 tokens, so the rules and the question were cut and the
# model answered in English about ngaben whatever was asked (prompt_eval_count = 2050 on
# every such turn, 2026-09-29).
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "12288"))
LLM_NUM_PREDICT = 1024
# Read timeout between streamed chunks (ChatOllama streams), so a long answer that keeps
# coming never times out -- only a hung server does. Without one, a hung Ollama held the
# turn until Sanic's 300 s limit and the user got a 503 instead of the plain answer.
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
llm = ChatOllama(model="qwen2.5", temperature=0, num_ctx=LLM_NUM_CTX, num_predict=LLM_NUM_PREDICT,
                 client_kwargs={"timeout": LLM_TIMEOUT})
# After a failed call, further calls fail at once for this long: a turn makes up to three
# calls, and three timeouts in a row would pass Sanic's 300 s limit anyway.
_LLM_COOLDOWN_S = 60.0
_llm_down_until = 0.0


def _llm_invoke(messages: List[Any]) -> Any:
    """llm.invoke(...) (an AIMessage: .content, and response_metadata["done_reason"] is
    "length" when the answer was cut at LLM_NUM_PREDICT), failing fast while Ollama has
    just failed. Callers catch the exception and fall back to the deterministic answer."""
    global _llm_down_until
    if time.monotonic() < _llm_down_until:
        raise RuntimeError("Ollama failed less than a minute ago; not retrying yet")
    try:
        return llm.invoke(messages)
    except Exception:
        _llm_down_until = time.monotonic() + _LLM_COOLDOWN_S
        raise
# ~3.5 characters per token measured on these prompts (8742 chars -> 2499 tokens); 3.0
# leaves a margin. The synthesis prompt is trimmed to this many characters.
_PROMPT_CHAR_BUDGET = int((LLM_NUM_CTX - LLM_NUM_PREDICT - 512) * 3.0)


class Neo4jConnection:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            with self._driver.session() as session:
                return [r.data() for r in session.run(cypher, params or {})]
        except Exception as e:
            print(f"Neo4j Error: {e}")
            # A console print is easy to miss on a long-running action server --
            # log it durably too, the same way LLM refusals/fabrications and
            # unresolved terms already are, so a Neo4j outage is discoverable
            # after the fact instead of silently degrading every answer's
            # relationships to empty with no trace.
            _log_jsonl(_NEO4J_ERROR_LOG_PATH, {"kind": "neo4j_query_error", "error": str(e)})
            return []

    def close(self) -> None:
        self._driver.close()


neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)


def recent_user_turns(tracker: Tracker, limit: int = 4) -> List[str]:
    """Last `limit` user utterances *since the current session began* (oldest first,
    current message included).

    Bounded by the most recent `session_started` marker event so a long-idle session
    restart (domain.yml's session_expiration_time: 60) doesn't leak turns from over an
    hour ago -- or a prior session -- into the coreference prompt. current_entity /
    entity_history deliberately still carry over across sessions
    (carry_over_slots_to_new_session: true); this only bounds the raw transcript text.
    """
    events = list(tracker.events)
    last_session_start = 0
    for i, e in enumerate(events):
        if e.get("event") == "session_started":
            last_session_start = i
    turns = [
        e.get("text", "")
        for e in events[last_session_start:]
        if e.get("event") == "user" and e.get("text")
    ]
    return turns[-limit:]


# Fetch by canonical KB id, not fuzzy text match -- entity resolution (aliases,
# typos, force-merges) is kb_resolver's job, done *before* we ever touch Neo4j.
_GRAPH_QUERY = """
UNWIND $entity_ids AS eid
MATCH (n:Node {id: eid})
OPTIONAL MATCH (n)-[r]-(m:Node)
WHERE coalesce(r.confidence, '') <> 'LOW'
// kinds/parts/members first, so a hub node never loses them to the cap. The cap was 40:
// ngaben reached 49 edges (2026-09-29) and "palebon adalah sebutan halus untuk ngaben"
// fell off the end; the prompt size is now bounded by _fit_context instead.
WITH n, r, m ORDER BY CASE WHEN type(r) IN $child_preds THEN 0 ELSE 1 END
RETURN n.id AS id,
       n.name AS name,
       n.definition AS graph_definition,
       labels(n) AS labels,
       collect(DISTINCT {
         relation: type(r),
         outgoing: startNode(r) = n,
         target: m.name,
         target_id: m.id,
         target_labels: labels(m),
         variant_region: r.variant_region,
         variant_op: r.variant_op,
         variant_replaces: r.variant_replaces
       })[..200] AS relationships
"""

# Substrings the synthesis LLM uses when it (correctly or not) decides the
# context doesn't answer the question -- rule 5 of synth_sys_prompt, plus the
# near-paraphrases observed in real transcripts (conersation.md).
_REFUSAL_SIGNALS = (
    "belum tercatat di basis data",
    "tidak tercatat di basis data",
    "tidak tercatat secara spesifik",
    "tidak disebutkan dalam data",
    "tidak ditemukan dalam data",
)

# Meta/instruction words the extraction LLM has echoed back as if they were a
# term to look up (observed in conersation.md: a bare "jelaskan" follow-up
# produced raw_terms ["jelaskan", "unsur unsur panca maha butha"]). These carry
# no entity meaning on their own. The second group are aspect words -- they say
# WHICH facet of a term is asked about ("apa saja unsurnya", "fungsinya"), never
# a term themselves (unresolved_log.jsonl: 'fungsinya', 'saja', 'simbolis', ...).
_META_TERMS = frozenset({
    "jelaskan", "jelaskanlah", "sebutkan", "coba", "tolong", "terangkan",
    "terangkanlah", "ceritakan", "jabarkan", "uraikan",
    "unsur", "unsurnya", "unsur-unsurnya", "bagian", "bagiannya", "jenis", "jenisnya",
    "fungsi", "fungsinya", "makna", "maknanya", "arti", "artinya", "hubungan",
    "hubungannya", "kata dasar", "apa saja", "saja", "perbedaan", "bedanya",
    "kenapa", "mengapa", "demikian", "simbolis", "tahapan", "tahapannya",
})

# "What does the word X mean" -- the user wants each word of a compound term
# explained on its own, then the compound (conersation.md 2026-09-24: "apa arti
# kata dasar pitra yadnya").
_WORD_MEANING_RE = re.compile(r"arti kata|kata dasar|asal kata|harfiah|etimologi", re.I)

# Predicates whose object is a standalone child concept worth pulling its own
# definition in for (same "parent decomposes into these things" shape as
# TERMASUK_JENIS) -- see the comment at the enrichment loop in
# _extract_and_resolve for how this was found (eteh-eteh sawa's BERUPA-linked
# parts each had a real definition that was never being fetched).
# BAGIAN_DARI added 2026-09-23: the KB semantics-fix pass (how_it_works.md §2.5)
# moved several stages (mapegat, tarpana, pabersihan_mati, ...) off a false
# TERMASUK_JENIS "type of ngaben" edge onto BAGIAN_DARI "stage of ngaben", so a
# "what are the stages" answer needs their definitions too. Location/time/actor
# predicates stay excluded -- a bare target name is enough for those.
# Composition edges added 2026-09-24: a component (soda BERUPA nasi, punjung BERISI
# kopi) needs its own definition too, or the model invents one ("canang sari ...
# berisi kertas-kertas berdoa").
_CHILD_IS_SOURCE = frozenset({"TERMASUK_JENIS", "BAGIAN_DARI"})   # child -[r]-> parent
_CHILD_IS_OBJECT = frozenset({"BERUPA", "TERDIRI_DARI", "BERISI", "DIISI_DENGAN", "DILENGKAPI",
                              "BERUNSUR", "TERBUAT_DARI", "DISERTAI"})  # parent -[r]-> part
_CHILD_DEF_PREDICATES = _CHILD_IS_SOURCE | _CHILD_IS_OBJECT
_CHILD_DEF_CAP = 24   # child definitions per term in one prompt (see _llm_context)

# Words too generic/frequent across every answer to count as evidence of
# grounding either way. Includes discourse/connector words a small LLM reaches
# for in ANY elaboration regardless of correctness (terdiri, disebut,
# pembentuk, filosofis, pemahaman, kehidupan, ...) -- confirmed these, not
# invented nouns, were what pushed a factually correct, fully graph-grounded
# answer about pancamahabutha's five elements over the fabrication threshold.
_STOPWORDS_ID = frozenset("""
yang untuk dalam adalah dengan atau dari pada juga akan telah tidak dapat
seperti karena namun sebagai serta secara sebelum sesudah setelah hingga
mereka semua salah satu bagian proses upacara ngaben ini itu tersebut para
kepada oleh maupun berbagai memiliki menjadi digunakan dipakai berupa jenis
konteks terdiri disebut dinyatakan menyatakan pembentuk filosofis pemahaman
kehidupan diberikan merupakan berdasarkan berkaitan berhubungan menggambarkan
menunjukkan termasuk beberapa bentuk dasar tentang sesuatu sehingga meskipun
yaitu
""".split())

_WORD_RE = re.compile(r"[a-zA-Zç]+")

# qwen2.5 occasionally emits a Cyrillic look-alike inside a Latin word ("Pitра"),
# which renders fine but breaks copy/search; answers are always Indonesian.
_CYRILLIC_LOOKALIKES = str.maketrans("аеорсухіјАВЕКМНОРСТХ", "aeopcyxijABEKMHOPCTX")


def _content_words(text: Optional[Text], min_len: int = 5) -> set:
    return {
        w for w in _WORD_RE.findall((text or "").lower())
        if len(w) >= min_len and w not in _STOPWORDS_ID
    }


def _context_vocabulary(enriched: List[Dict[str, Any]]) -> set:
    vocab: set = set()
    for e in enriched:
        vocab |= _content_words(e.get("name"))
        vocab |= _content_words(e.get("definition"))
        # sarana_facts too: a correct "apa saja sarana ngaben" list scored 0.65 ungrounded
        # without them (cutoff 0.75), so a longer list would have been discarded (2026-09-30)
        for fact in ((e.get("facts") or []) + (e.get("aspect_facts") or []) + (e.get("sarana_facts") or [])
                     + (e.get("source_facts") or [])):
            vocab |= _content_words(fact)
        for rel in e.get("relationships") or []:
            vocab |= _content_words(rel.get("target"))
            vocab |= _content_words(rel.get("target_definition"))
            vocab |= _content_words(rel.get("statement"))
    return vocab


def _grounded(word: str, vocab: set, prefix_len: int = 5) -> bool:
    """A word counts as grounded if it (or an Indonesian-affix root, approximated
    by a shared prefix) appears in the context vocabulary handed to the LLM."""
    if word in vocab:
        return True
    if len(word) < prefix_len:
        return False
    prefix = word[:prefix_len]
    return any(v.startswith(prefix) for v in vocab)


def _log_jsonl(path: Path, record: Dict[str, Any]) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Log write error ({path.name}): {e}")


def _log_unresolved(user_msg: str, unresolved: List[str], suggestions: List[str]) -> None:
    """Ongoing curation feed for kb_resolver misses -- mirrors review_queue.jsonl's
    pattern for relation-extraction confidence, but for entity resolution."""
    if not unresolved:
        return
    _log_jsonl(_UNRESOLVED_LOG_PATH, {
        "kind": "unresolved_term",
        "terms": unresolved,
        "user_msg": user_msg,
        "suggestions": suggestions,
        "decision": "",
        "decision_hint": "force_merge: <id> | alias: <id> | new_entity | ignore",
    })


def _log_refusal(user_msg: str, enriched: List[Dict[str, Any]], llm_answer: str, kept: bool = False) -> None:
    _log_jsonl(_REFUSAL_LOG_PATH, {
        "kind": "llm_refusal_kept" if kept else "llm_refusal_override",
        "user_msg": user_msg,
        "entities": [e["id"] for e in enriched],
        "llm_answer": llm_answer,
    })


def _log_fabrication(user_msg: str, enriched: List[Dict[str, Any]], llm_answer: str,
                     kind: str = "llm_fabrication_override") -> None:
    _log_jsonl(_REFUSAL_LOG_PATH, {
        "kind": kind,
        "user_msg": user_msg,
        "entities": [e["id"] for e in enriched],
        "llm_answer": llm_answer,
    })


def _has_grounding(enriched: List[Dict[str, Any]]) -> bool:
    return any(
        e.get("definition") not in (None, "", "Tidak ada definisi langsung") or e.get("facts")
        for e in enriched
    )


def _has_refusal_signal(answer: Text) -> bool:
    """True if a refusal phrase is present AND it's basically the whole answer,
    not an honest one-line caveat inside an otherwise substantial one. 2026-09-23:
    used to fire on ANY occurrence, discarding real, mostly-correct, multi-fact
    answers (bhuta_kala, tirtha_pangentas) purely because they honestly flagged
    one remaining sub-detail as not recorded -- replacing them with the flat
    deterministic template, which is a WORSE answer (less complete, often about
    the wrong facet entirely) than what was discarded. Confirmed live via
    llm_refusal_log.jsonl. A short answer that's essentially just the refusal
    (few content words) is still caught -- that's a real "nothing to say" case."""
    low = answer.lower()
    if not any(sig in low for sig in _REFUSAL_SIGNALS):
        return False
    return len(_content_words(answer)) < 12


def _has_fabrication_signal(answer: Text, enriched: List[Dict[str, Any]]) -> bool:
    """Flags answers that introduce substantial vocabulary absent from the KB
    context handed to the LLM -- observed directly in conersation.md (the
    "ngaben svasta symbolism" turn, where Qwen invented flowers/jewelry/clothing/
    food/personal items that appear nowhere in the actual tirtha/toyo-çarira
    facts it was given). Same shape as _has_refusal_signal: a deterministic,
    Python-side check backstopping an LLM instruction (synth_sys_prompt rule 3)
    a small local model doesn't reliably follow on its own."""
    answer_words = _content_words(answer)
    if len(answer_words) < 4:
        return False  # too short to judge reliably either way
    vocab = _context_vocabulary(enriched)
    if not vocab:
        return False
    ungrounded = [w for w in answer_words if not _grounded(w, vocab)]
    # 0.6 was too aggressive: a factually correct, fully graph-grounded answer
    # about pancamahabutha's five elements measured ~0.61 purely from ordinary
    # discourse connectors ("mengacu", "merujuk", "mencakup", "dikelompokkan",
    # ...), while the real invented-symbolism case measured ~0.9. 0.75 keeps a
    # comfortable margin below the real fabrication while no longer punishing
    # normal elaboration.
    return len(ungrounded) / len(answer_words) > 0.75


# Words that appear only in an English answer ("Based on the information provided,
# here are some key points about Ngaben", conersation.md 2026-09-29) -- the fabrication
# ratio let most of those through, since the ritual names in them are all grounded.
_ENGLISH_WORDS = frozenset("""
the and of is are was were with this that these those which based provided information
including key points about also known some other various such ceremony performed
""".split())


def _looks_english(answer: Text) -> bool:
    words = re.findall(r"[a-zA-Z]+", answer.lower())
    if len(words) < 8:
        return False
    hits = sum(w in _ENGLISH_WORDS for w in words)
    return hits >= 4 and hits / len(words) >= 0.08


# A single English word inside an Indonesian answer: English-only endings (Indonesian
# uses -si, not -tion) or words Indonesian never uses. "karena dianggap tidak propitious"
# came back twice (conersation.md L117, Tier B 2026-09-29); "membebaskan atma mendiang dari siklus
# rebirth" (Tier B 2026-10-05).
_ENGLISH_WORD_RE = re.compile(r"\b(?:[a-z]+(?:tion|tions|ious|ness|ful|ship)|the|and|with|which|because|however"
                              r"|rebirth|afterlife|souls?)\b", re.I)


def _english_words(answer: Text) -> List[str]:
    return sorted({m.group(0).lower() for m in _ENGLISH_WORD_RE.finditer(answer)})


# What the retry still left in English, swapped for its Indonesian word: told "tanpa kata bahasa
# Inggris seperti propitious", the model wrote "dianggap tidak propitious" again (Tier B 2026-10-05)
_ENGLISH_SWAPS = {"propitious": "baik", "auspicious": "baik", "inauspicious": "tidak baik",
                  "unpropitious": "tidak baik", "rebirth": "kelahiran kembali", "afterlife": "alam setelah kematian",
                  "soul": "jiwa", "souls": "jiwa"}


def _swap_english(answer: Text) -> Text:
    out = re.sub(r"\btidak\s+(propitious|auspicious)\b", "tidak baik", answer, flags=re.I)
    return re.sub(r"\b(" + "|".join(_ENGLISH_SWAPS) + r")\b", lambda m: _ENGLISH_SWAPS[m.group(1).lower()],
                  out, flags=re.I)


# A question that asks more than what X is -- why, whether, how many, when, who -- can be
# correctly refused when the KB lacks it. Replacing that refusal with X's definition
# answered something else ("kenapa angka 11 dipilih untuk bade raja?" -> the definition
# of bade; llm_refusal_log.jsonl 2026-09-29).
_SPECIFIC_Q_RE = re.compile(
    r"\b(kenapa|mengapa|apakah|bagaimana|berapa|kapan|siapa|di ?mana|boleh|harus|hanya|"
    r"dipilih|alasan|hari baik)\b", re.I)
_WHY_Q_RE = re.compile(r"\b(kenapa|mengapa|alasan(nya)?)\b", re.I)

# The prompt's own field names ("... seperti yang tercantum dalam 'target_definition'
# masing-masing", Tier B 2026-09-29): a sentence that names one is dropped.
_FIELD_LEAK_RE = re.compile(r"[^.\n]*\b(target_definition|also_called|relationships)\b[^.\n]*\.?[ \t]*")


def _fix_kind_claims(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """"X termasuk salah satu jenis Y" where the graph says X is a stage/part of Y (and
    not a kind of it) is rewritten to "X adalah bagian dari Y" -- "Pabasmian termasuk
    salah satu jenis ngaben" for a stage of ngaben (Tier B 2026-09-29), although rule 7
    says a stage is never a jenis."""
    for e in enriched:
        rels = e.get("relationships") or []
        kinds = {r.get("target") for r in rels if r.get("relation") == "TERMASUK_JENIS" and r.get("outgoing")}
        parts = {r.get("target") for r in rels if r.get("relation") == "BAGIAN_DARI" and r.get("outgoing")}
        for t in parts - kinds:
            if not t:
                continue
            pat = re.compile(rf"\b({re.escape(e['name'])})\s+termasuk\s+(?:salah\s+satu\s+)?jenis\s+({re.escape(t)})\b",
                             re.I)
            answer = pat.sub(lambda m: f"{m.group(1)} adalah bagian dari {m.group(2)}", answer)
    return answer


# Words that tell set members apart (panca datu, panca dewata, beras catur, pancamahabutha), the
# bade tiers a kind of wangsa was given (2026-10-02) and the yadnya a sasih is good for: "Sasih
# kaenem, sasih kalima, dan sasih kapat memiliki kebaikan untuk Dewa Yadnya" (kaenem's is Bhuta
# Yadnya; Tier B 2026-10-02). Pitra yadnya is left out: it frames every Ngaben answer.
_MEMBER_MARKERS = {w: re.compile(rf"\b{w}\b", re.I) for w in """
timur selatan barat utara tengah putih merah kuning hitam iswara brahma mahadewa wisnu wishnu siwa shiwa
sebelas sembilan
""".split()}
_MEMBER_MARKERS.update({
    "dewa yadnya": re.compile(r"\bdewa\s+yadnya\b", re.I),
    "bhuta yadnya": re.compile(r"\bbh?uta\s+yadnya\b", re.I),
    "manusa yadnya": re.compile(r"\bmanusa\s+yadnya\b", re.I),
    "rsi yadnya": re.compile(r"\br[e]?si\s+yadnya\b", re.I),
    # "Sasih kadasa, asada, dan dyestha dianggap sasih mati" (only asada and dyestha are)
    "sasih mati": re.compile(r"\bsasih\s+mati\b|\btanpa\s+amer?tha\b", re.I),
})


def _fix_moved_member_facts(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A sentence about members of a set (the child terms with a definition in context) that
    gives them a direction, colour, god or bade tier no named member's own definition has, but
    another term's in context does, moved a fact: one member -> replaced by that member's own first
    definition sentence, several -> dropped. "Perak, yang berwarna kuning, ditempatkan di arah
    barat dan berdewa Dewa Mahadewa" (that is emas; perak is putih, timur, Iswara) for "untuk apa
    panca datu dalam ngaben?", and "jenazah dari kalangan Pasek ... menggunakan tingkatan bade
    bertingkat sebelas" (Pasek's is the Singa petulangan) for "apa hubungan wangsa dengan
    tingkatan bade" (Tier B 2026-10-02). Rule 8 alone did not hold. Never leaves nothing."""
    members = {}
    for e in enriched:
        for r in e.get("relationships") or []:
            if r.get("target_definition") and r.get("target"):
                members[r["target"].lower()] = r["target_definition"]
    if len(members) < 2:
        return answer

    def markers(text: str) -> set:
        return {w for w, rx in _MEMBER_MARKERS.items() if rx.search(text)}
    marks = {m: markers(d) for m, d in members.items()}
    context_marks = set().union(*(markers(e.get("definition") or "") for e in enriched))
    out, sentences = answer, re.findall(r"[^.!?\n]+[.!?]*", answer)
    for s in sentences:
        hits = {m: re.search(rf"\b{re.escape(m)}\b", s, re.I) for m in members}
        named = [m for m, h in hits.items() if h]
        if not named:
            continue
        if not markers(s):
            continue
        # Each member is checked against the markers that follow it up to the next member; members
        # with nothing between them share what follows ("kaenem, kalima, dan kapat ... Dewa
        # Yadnya" gives Dewa Yadnya to all three). Markers before the first member go to the first.
        # "Sasih kadasa baik untuk Dewa Yadnya ..., sasih kaenem baik untuk Dewa Yadnya ...,
        # sasih kalima baik untuk Dewa Yadnya ..." had passed as a whole, kalima's Dewa Yadnya
        # covering kadasa and kaenem (Tier B 2026-10-05).
        starts = sorted((hits[m].start(), hits[m].end(), m) for m in named)
        groups, cur = [], []
        for k, (a, b, m) in enumerate(starts):
            nxt = starts[k + 1][0] if k + 1 < len(starts) else len(s)
            cur.append(m)
            seg = markers(s[b:nxt]) | (markers(s[:starts[0][0]]) if not groups else set())
            if seg or k + 1 == len(starts):
                groups.append((cur, seg, starts[k - len(cur) + 1][0], nxt))
                cur = []

        def wrong(group: tuple) -> bool:
            ms, seg = group[0], group[1]
            return any((seg - marks[m]) & context_marks.union(*(marks[o] for o in members if o != m)) for m in ms)
        bad = [g for g in groups if wrong(g)]
        if not bad:
            continue
        if len(groups) > 1 and len(bad) < len(groups):
            # keep the clauses that are right, drop the members' clauses that are not
            fixed = s
            for _, _, a, b in sorted(bad, key=lambda g: -g[2]):
                fixed = fixed[:a] + fixed[b:]
            fixed = re.sub(r"(?:,|;|\bdan)\s*([.!?]?)\s*$", r"\1", fixed.strip()).strip()
            if fixed and fixed[-1] not in ".!?":
                fixed += "."
            fixed = fixed[:1].upper() + fixed[1:]
            out = re.sub(r"[ \t]{2,}", " ", out.replace(s.strip(), fixed, 1))
            continue
        own = ""
        if len(named) == 1:
            m = named[0]
            own = _first_sentence(members[m], limit=400)
            if own and not own.lower().startswith(m):
                own = f"{m[:1].upper()}{m[1:]}: {own[:1].lower()}{own[1:]}"
        candidate = re.sub(r"[ \t]{2,}", " ", out.replace(s.strip(), own if own and own not in out else "", 1))
        if candidate.strip():
            out = candidate
    return out.strip()


def _first_sentence(text: Optional[Text], limit: int = 300) -> str:
    if not text or text == "Tidak ada definisi langsung":
        return ""
    s = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + " ..."


def _last_bot_utterance(tracker: Tracker) -> Optional[Text]:
    for e in reversed(tracker.events):
        if e.get("event") == "bot" and e.get("text"):
            return e.get("text")
    return None


def _is_near_repeat(answer: Text, previous: Optional[Text], threshold: float = 0.7) -> bool:
    """True if `answer` shares most of its content vocabulary with the bot's own
    immediately preceding utterance -- observed directly in conersation.md: four
    different phrasings of "how is banten pamegat used" ("digunakan untuk apa",
    "tapi digunakan bagaimana?", "digunakan bagaimana?", "jelaskan") all got back
    near-verbatim-identical paragraphs that never actually answered "how", because
    the KB only has "when" facts for it and nothing flagged that the answer wasn't
    new. Same shape as the refusal/fabrication guards: a deterministic backstop
    for something the small local model doesn't reliably self-detect."""
    if not previous:
        return False
    a = _content_words(answer)
    b = _content_words(previous)
    if len(a) < 4 or len(b) < 4:
        return False
    return len(a & b) / len(a | b) >= threshold


def _deterministic_answer(enriched: List[Dict[str, Any]]) -> str:
    """Fallback answer built straight from `enriched` -- pure Python, so it can't
    itself hedge or refuse the way a small local LLM sometimes does.

    Definitions only. It used to append every fact after the definition, which
    produced strings of unrelated claims ("pitra berwujud sekah kangsen. pitra
    dipersilakan masuk ke sekah kangsen. pitra menerima ...") that read as
    nonsense (conersation.md 2026-09-24). Facts are used only for an entity
    with no definition at all, and then only a few. The one exception is the
    asked aspect's attributes (`aspect_facts`): they ARE the answer to "apa warna
    besi" / "di mana kawangen diletakkan", so they follow the definition."""
    sentences = []
    for e in enriched:
        name = e.get("name") or e.get("id")
        definition = e.get("definition")
        if definition and definition != "Tidak ada definisi langsung":
            def_text = definition.rstrip(".")
            # a definition is often already a full "{name} adalah ..." sentence --
            # don't double the subject ("soda adalah Soda adalah ...").
            if def_text.lower().startswith(f"{name}".lower()):
                sentences.append(f"{def_text}.")
            else:
                sentences.append(f"{name[:1].upper()}{name[1:]} adalah {def_text[:1].lower()}{def_text[1:]}.")
        elif e.get("facts"):
            sentences.append(". ".join(e["facts"][:3]) + ".")
        for fact in e.get("aspect_facts") or []:
            sentences.append(f"{fact[:1].upper()}{fact[1:]}.")
    return " ".join(sentences)


# Aspect words the extraction LLM sometimes glues onto the term: "apa warna besi"
# -> "warna besi", which resolves to nothing (regression 2026-09-24). kb_resolver's
# strip_modifiers can't take these -- that list is shared with build_kb.py, where
# stripping them would change how the corpus is resolved. A real name that starts
# with one of them still wins: a word is peeled only while the term doesn't resolve.
_ASPECT_WORDS = frozenset("""
warna makna arti fungsi kegunaan guna manfaat tujuan peran peranan letak posisi lokasi
waktu bentuk ukuran panjang ciri lambang simbol filosofi asal syarat cara proses pelaku
""".split())


def _peel_aspect_words(term: str, resolver) -> str:
    toks = term.split()
    while len(toks) > 1 and re.sub(r"nya$", "", toks[0]) in _ASPECT_WORDS:
        hit = resolver.resolve(" ".join(toks))
        if hit and hit.via != "fuzzy":
            break
        toks = toks[1:]
    return " ".join(toks)


def _widen_to_named_term(term: str, user_msg: Text, resolver) -> str:
    """The extraction LLM sometimes shortens what the user named toward a term from the
    history: "di mana kawangen jeriji diletakkan" after a turn about kawangen came back
    as "kawangen" (regression 2026-09-24). If every occurrence of the term in the
    message sits inside a longer phrase that is itself an exact KB name, use that name.
    A standalone occurrence ("kawangen dan kawangen jeriji") keeps the term as is."""
    msg = re.findall(r"[\w-]+", user_msg.lower())
    t = term.lower().split()
    n = len(t)
    own = resolver.resolve(term)
    starts = [i for i in range(len(msg) - n + 1) if msg[i:i + n] == t]
    best = None
    for i in starts:
        found = None
        for lo in range(max(0, i - 3), i + 1):
            for hi in range(i + n, min(len(msg), i + n + 3) + 1):
                if hi - lo <= n:
                    continue
                phrase = " ".join(msg[lo:hi])
                hit = resolver.resolve(phrase)
                # the phrase must BE a name/alias (resolve() also peels "apa itu ...")
                # of another entity than the term's own
                if (hit and hit.via in ("exact", "alias") and (own is None or hit.id != own.id)
                        and phrase in {hit.name.lower()} | {a.lower() for a in hit.entity.get("aliases") or []}
                        and (found is None or len(phrase) > len(found))):
                    found = phrase
        if found is None:
            return term
        if best is None or len(found) > len(best):
            best = found
    return best or term


def _user_spelling(term: str, user_msg: Text, entity: Dict[str, Any]) -> str:
    """The name as the user wrote it: the extraction LLM may misspell it ("nggerorasin"),
    and that spelling would reach the answer's "X adalah sebutan lain untuk Y"."""
    if term.lower() in user_msg.lower():
        return term
    key = _ortho_key(term)
    for name in entity.get("aliases") or []:
        if _ortho_key(name) == key and name.lower() in user_msg.lower():
            return name
    return term


def _term_is_grounded(term: str, said: set, skip: frozenset = frozenset()) -> bool:
    words = [w for w in re.findall(r"\w+", term.lower()) if len(w) >= 3 and w not in skip]
    return any(w in said or any(fuzz.ratio(w, s) >= 80 for s in said) for w in words)


# Class words a name shares with ordinary questions: "upacara ngelungah" was kept as
# named by "apa saja sarana upacara yang digunakan untuk ngaben" (2026-09-29).
_GENERIC_NAME_WORDS = frozenset("""
upacara prosesi ritual acara istilah konsep kata sarana banten tirtha tirta sasih daun
bunga kain pura bale dewa tahap jenis
""".split())


# Single words the message scan never looks up on their own: question words and
# connectors, plus aspect words ("makna", "sarana") that say which facet is asked.
_SCAN_SKIP = frozenset("""
apa itu ini dan yang untuk dengan dalam saja kenapa mengapa bagaimana apakah
ada tidak boleh harus hanya oleh atau juga jadi dari pada sebagai seperti pun lagi sih
arti artinya makna maknanya maksud maksudnya definisi jelaskan sebutkan
jenis tahapan hubungan tujuan peran fungsi sarana acara cara proses siapa kapan berapa
mana umum masyarakat cocok melaksanakan dilaksanakan hal digunakan dipakai
""".split())


def _scan_terms(user_msg: Text, resolver) -> "tuple[list, List[str], List[bool]]":
    """The n-gram scan behind _mentioned_terms: (start, end, Match, phrase) in message
    order, plus the message tokens and which of them a term covers."""
    toks = re.findall(r"[\w-]+", user_msg.lower())
    used = [False] * len(toks)
    found = []
    # ("ngaben" is in _STOPWORDS_ID for the grounding checks, not here)
    lone_skip = (_STOPWORDS_ID - {"ngaben"}) | _ASPECT_WORDS | _META_TERMS
    for allow_fuzzy in (False, True):     # an exact name before any typo match
        for n in range(min(5, len(toks)), 0, -1):
            for i in range(len(toks) - n + 1):
                words = toks[i:i + n]
                if any(used[i:i + n]) or words[0] in _SCAN_SKIP or words[-1] in _SCAN_SKIP:
                    continue
                if n == 1 and (len(words[0]) < 3 or words[0] in lone_skip):
                    continue
                phrase = " ".join(words)
                m = resolver.resolve(phrase)
                if not m or (m.via == "fuzzy" and (not allow_fuzzy or any(len(w) < 6 for w in words))):
                    continue
                # a 3-letter word only as an exact name (abu, air, lis, uye): "abu jenazah"
                # was answered about jenazah alone (live crosscheck 2026-09-30)
                if n == 1 and len(words[0]) == 3 and m.via not in ("exact", "alias"):
                    continue
                # an everyday word alone is no typo of a longer name: "berapa tingkat bade"
                # made "tingkat" tingkatan upacara and put it first (2026-10-01)
                if n == 1 and m.via == "fuzzy" and words[0] in resolver.common_words:
                    continue
                found.append((i, i + n, m, phrase))
                used[i:i + n] = [True] * n
    found.sort(key=lambda x: x[0])
    return found, toks, used


def _is_kind_of(entity: Dict[str, Any], class_id: Text, resolver, hops: int = 3) -> bool:
    for _ in range(hops):
        parent = entity.get("broader")
        if not parent:
            return False
        if parent == class_id:
            return True
        entity = resolver.by_id.get(parent) or {}
    return False


@functools.lru_cache(maxsize=1)
def _named_kind_classes(resolver) -> frozenset:
    """Classes whose kinds are (nearly) all named "<class> <name>": sasih (sasih kasa, sasih
    karo, ...), banten, pura, bale. A user copying that pattern for a term that is no kind of
    the class ("sasih kliwon") holds a wrong premise, not two terms."""
    kids: Dict[str, List[str]] = {}
    for e in resolver.by_id.values():
        if e.get("broader"):
            kids.setdefault(e["broader"], []).append(e["name"].lower())
    out = set()
    for cid, names in kids.items():
        c = resolver.by_id.get(cid)
        if c and len(names) >= 2 and sum(n.startswith(c["name"].lower() + " ") for n in names) >= 0.8 * len(names):
            out.add(cid)
    return frozenset(out)


def _misclassed_terms(user_msg: Text, resolver) -> List[tuple]:
    """(class Match, class surface, term Match, term surface) for each "<class> <term>" in the
    message whose term is no kind of that class: "apa hubungan sasih kliwon dengan pitra yadnya"
    (kliwon is a pancawara day) was answered "Sasih kliwon adalah salah satu jenis sasih ...
    sasih kedua" (Tier B 2026-10-02). The term must be named as written, not reached through a
    verb ("abu jenazah dihanyutkan" is no "jenazah nganyut")."""
    found = _scan_terms(user_msg, resolver)[0]
    classes = _named_kind_classes(resolver)
    return [(a[2], a[3], b[2], b[3]) for a, b in zip(found, found[1:])
            if a[1] == b[0] and a[2].id in classes and a[2].id != b[2].id
            and b[2].via in _NAMED_VIA and not _VERB_FORM_RE.match(b[3])
            and not _is_kind_of(b[2].entity, a[2].id, resolver)]


def _mentioned_terms(user_msg: Text, resolver) -> "tuple[List[tuple], List[str]]":
    """KB terms the message itself names, as (Match, surface) in message order --
    longest phrase first, so "tirtha pangentas" wins over "tirtha". The extraction LLM
    sometimes swaps a new term for one from the history ("apa saja sarana upacara yang
    digunakan dalam acara nglungah" came back as "ngaben", 2026-09-29); this scan does
    not look at the history at all. A fuzzy hit counts only on long words.

    Also returns the message's leftover words: the ones no found term covers and that
    are not question / connector words or a question aspect ("diletakkan",
    "melambangkan"). With none left, the message is fully explained by its terms."""
    found, toks, used = _scan_terms(user_msg, resolver)
    lone_skip = (_STOPWORDS_ID - {"ngaben"}) | _ASPECT_WORDS | _META_TERMS
    # a class word right before its member names the member, not a second term:
    # "sasih malamasa" is malamasa (a sasih) -- as two terms, "sasih" became the topic
    # and "jadi, kenapa tidak boleh?" was answered about every sasih (2026-09-29).
    # Before a term that is no kind of it ("sasih kliwon") it is the user's wrong premise.
    drop = {a[2].id for a, b in zip(found, found[1:])
            if a[1] == b[0] and b[2].entity.get("broader") == a[2].id}
    drop |= {c.id for c, _, _, _ in _misclassed_terms(user_msg, resolver)}
    # a term whose name is one word of another found term's name, that other term found
    # through its other word: "kenapa tirtha ada harganya" names harga tirtha (as "harganya"),
    # not tirtha as a second topic -- with tirtha first, some Ollama loads answered about
    # tirtha's uses and never said "punia" (2026-10-02). A relation / comparison question
    # names both on purpose.
    if not (_RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg)):
        def okeys(s: str) -> set:
            return {_ortho_key(w) for w in s.split()}
        for _, _, a, a_surf in found:
            for _, _, b, b_surf in found:
                if a.id != b.id and okeys(a.name) < okeys(b.name) and not okeys(a_surf) & okeys(b_surf):
                    drop.add(a.id)
    out, seen = [], set()
    for _, _, m, phrase in found:
        if m.id not in seen and m.id not in drop:
            seen.add(m.id)
            out.append((m, phrase))
    leftover = [t for t, u in zip(toks, used)
                if not u and len(t) >= 4 and t not in _SCAN_SKIP and t not in lone_skip
                and not any(p.search(t) for p in _ASPECT_WORD_RES)]
    return out, leftover


# A follow-up that points back at the topic ("kenapa itu harus dihindari?", "hanya itu
# sarananya?"); checked on the message with its question lead ("apa itu") removed.
_ANAPHOR_RE = re.compile(r"\b(itu|ini|tersebut|tadi|keduanya|begitu|demikian)\b|\b(?!yadnya\b)\w{3,}nya\b",
                         re.I)
# "yang pertama / yang terakhir" picks an item of the previous answer -- the extraction
# LLM resolves that, not the topic rule below
_ORDINAL_REF_RE = re.compile(r"\byang\s+(pertama|kedua|ketiga|keempat|kelima|terakhir)\b", re.I)
_DEICTIC_WORDS = frozenset({"itu", "ini", "tersebut", "tadi"})


def _points_back(user_msg: Text, mentioned: List[tuple], resolver) -> bool:
    """A standalone itu/ini/tersebut/tadi that does not follow a term the message names
    ("bade itu" is that bade; "kapan itu dilakukan, sebelum atau sesudah nyiramang layon?"
    after a turn about pangringkes means pangringkes, live crosscheck T65)."""
    toks = re.findall(r"[\w-]+", resolver.clean_query(user_msg))
    named = [p.split() for _, p in mentioned]
    for i, t in enumerate(toks):
        if t not in _DEICTIC_WORDS or (i > 0 and toks[i - 1] == "apa"):
            continue
        if not any(len(p) <= i and toks[i - len(p):i] == p for p in named):
            return True
    return False


def _definition_hit(words: List[str], resolver):
    """The one entity whose definition contains every content word of a message that
    names no term: "apakah bayi yang giginya belum tanggal boleh dibakar?" is upacara
    ngelungah ("upacara kematian bagi bayi ... yang gigi susunya belum tanggal"), live
    crosscheck T69. A word matches a definition word on its first 5 letters (whole word
    if shorter); at least two words, and exactly one entity may match."""
    words = [re.sub(r"nya$", "", w) for w in words]
    words = [w for w in words if len(w) >= 4 and w not in _STOPWORDS_ID]
    if len(words) < 2:
        return None
    content = get_content()
    hits = []
    for eid, definition in content.entity_def.items():
        dwords = set(_WORD_RE.findall(definition.lower()))
        if all(any(d[:5] == w[:5] if len(w) >= 5 else d == w for d in dwords) for w in words):
            hits.append(eid)
            if len(hits) > 1:
                return None
    return resolver.resolve(content.entity_name[hits[0]]) if hits else None


_WHAT_IS_RE = re.compile(r"^\s*(?:apa(?:kah)?|siapa)\s+(?:itu|yang dimaksud(?:\s+dengan)?)\b", re.I)


def _partial_name(user_msg: Text, mentioned: List[tuple], resolver) -> Optional[str]:
    """"apa itu paca mahamaha buta": the scan found only "buta" (bhuta), and the model called
    the user's whole phrase "salah satu jenis bhuta kala" -- a kind nobody recorded
    (conersation.md 2026-10-02). When a what-is question's subject holds words besides the one
    term it names, and one of them is no everyday word, the user named something the KB lacks:
    the whole phrase is the miss."""
    if not _WHAT_IS_RE.search(user_msg) or len(mentioned) != 1:
        return None
    subject = re.split(r"[,?]|\s(?:dan|serta)\s", resolver.clean_query(user_msg))[0].strip()
    m, surface = mentioned[0]
    # the term's own words and other KB terms are known: "apa itu nyiramin layon" names
    # nyiramang layon (as "nyiramin") and its "layon" (Tier B 2026-10-02)
    named = set(re.findall(r"[\w-]+", surface)) | set(m.name.lower().split())
    extra = [w for w in re.findall(r"[\w-]+", subject)
             if w not in named and w not in _SCAN_SKIP and w not in _STOPWORDS_ID]

    def unknown(w: str) -> bool:
        hit = resolver.resolve(w)
        return len(w) >= 3 and not _is_everyday_word(w, resolver) and not (hit and hit.via in ("exact", "alias"))
    if any(unknown(w) for w in extra):
        return subject
    return None


_PREFIXES = ("meng", "meny", "mem", "men", "me", "peng", "peny", "pem", "pen", "per", "pe", "ber", "ter",
             "di", "ke", "se")
_SUFFIXES = ("nya", "kan", "lah", "kah", "an", "i")
_EVERYDAY_ROOTS: Optional[frozenset] = None


def _root(word: str) -> str:
    """A rough Indonesian root: one suffix, then one prefix, each only if 4+ letters remain
    ("dihindari" and "menghindari" -> "hindar", "giginya" -> "gigi")."""
    for s in _SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 4:
            word = word[:-len(s)]
            break
    for p in _PREFIXES:
        if word.startswith(p) and len(word) - len(p) >= 4:
            return word[len(p):]
    return word


def _is_everyday_word(word: str, resolver) -> bool:
    """In the common-word list (6k words of a formal corpus), or sharing a root with one of
    them: the list has "menghindari" but not "dihindari", "gigi" but not "giginya"."""
    global _EVERYDAY_ROOTS
    if _EVERYDAY_ROOTS is None:
        _EVERYDAY_ROOTS = frozenset(_root(w) for w in resolver.common_words)
    return word in resolver.common_words or _root(word) in _EVERYDAY_ROOTS


# "kenapa orang bali membakar mayat?" (conersation.md 2026-10-02)
_BURN_RE =re.compile(r"\b(?:mem|di|ter)?bakar(?:nya|kan)?\b|\bpembakaran\b", re.I)


def _extract_and_resolve(
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    user_msg: Text,
    entity_history: List[str],
    current_entity: Optional[str] = None,
    announce_miss: bool = True,
) -> "tuple[List[Dict[str, Any]], List[str], List[str]]":
    """Steps 1-3: LLM term extraction -> kb_resolver -> Neo4j + curated-content
    enrichment. Shared by ActionGraphRAG and ActionLLMFallback so a genuine
    follow-up that trips the fallback classifier still gets KB-grounded.

    Returns (enriched, unresolved, found_names). `enriched` is [] on total failure;
    when `announce_miss` is True (ActionGraphRAG), a resolver-level explanatory
    message has already been dispatched in that case -- when False
    (ActionLLMFallback), the caller is expected to fall through to its own
    ungrounded answer instead.
    """
    turns = recent_user_turns(tracker, limit=4)
    prior_turns = turns[:-1] if len(turns) > 1 else []
    history_block = "\n".join(f'- "{t}"' for t in prior_turns) or "(tidak ada)"
    entities_block = ", ".join(entity_history) or "(tidak ada)"
    resolver = get_resolver()
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    partial = _partial_name(user_msg, mentioned, resolver)
    if partial:
        suggestions = resolver.suggest(partial, k=3)
        _log_unresolved(user_msg, [partial], suggestions)
        if announce_miss:
            dispatcher.utter_message(
                text=(f"Maaf, saya tidak menemukan '{partial}' di basis data. Mungkin maksud Anda: "
                      f"{', '.join(suggestions)}?") if suggestions else
                     f"Maaf, informasi mengenai '{partial}' belum tercatat di basis data.")
        return [], [partial], []
    # The extraction LLM is for what the words alone cannot give: a pronoun or ellipsis
    # ("kenapa itu harus dihindari?"), a relation/comparison question whose second term
    # may come from the history, or a word the scan could not place. A message fully
    # explained by the terms it names ("apa itu ngaben", "apa makna banten") skips it:
    # its extra terms would be filtered out in Step 2b anyway, and it cost a full LLM
    # call on every such turn (2026-09-30).
    use_llm = bool(not mentioned or leftover or _ANAPHOR_RE.search(resolver.clean_query(user_msg))
                   or _RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg))

    # Step 1: LLM handles coreference + multi-term splitting. It no longer
    # guesses "correct" spelling -- that's kb_resolver's job (Step 2), which has
    # the real alias table, force-merges, and rapidfuzz, and won't silently
    # drift a term toward the wrong canonical form.
    resolve_prompt = f"""
    You are extracting the term(s) a user is asking about from a Balinese Ngaben
    chatbot conversation, so they can be looked up in a database.

    Current user input: "{user_msg}"

    Recent conversation turns before this message (oldest first):
    {history_block}

    Entities discussed so far this session, most recently discussed last:
    {entities_block}

    Topic being discussed right now, if the current input uses a pronoun or
    ellipsis with no other candidate in the entities list above: {current_entity or "(tidak ada)"}

    Task:
    - Pull out the term(s) the user is asking about right now, as close to their
      original wording as possible. Do NOT try to fix spelling or guess the
      "official" form -- a separate matching step handles that.
    - If the current input uses a pronoun or ellipsis ("itu", "ini", "yang tadi",
      "yang pertama", "yang kedua", "keduanya", etc.), replace it with the actual
      term(s) it refers to, using the recent conversation and the entities list above.
    - A generic collective reference with no specific noun of its own ("setiap
      barang", "semua itu", "masing-masing", "setiap hal tersebut", "setiap
      bagiannya") is NOT itself a term to look up -- it means "every part of
      the thing we were just discussing". Return the topic being discussed
      right now (below) instead of the literal collective phrase.
    - If the current input clearly introduces a brand new term unrelated to the
      history, ignore the history and just return that new term.
    - If the current input already names its own complete subject (it is not just
      a bare pronoun, ellipsis, or instruction verb), return ONLY that subject --
      do not also add older terms from history just because the topic is related.
    - A vague add-on like "dan apa istilah lainnya" / "dan yang lain-lain" ("and
      what other terms") has no specific referent -- it does NOT mean "also
      return an unrelated term from the entities list above". If nothing in the
      current input or the entities list clearly answers "what other term", drop
      that add-on and return only the term(s) the input clearly names.
    - Never include the user's own instruction verb (e.g. "jelaskan", "sebutkan",
      "coba", "tolong") as one of the returned terms -- only the actual subject
      matter being asked about.
    - Return ONLY a comma-separated list of the term(s), lowercase, no extra text,
      no punctuation.
    """
    raw_terms: List[str] = []
    try:
        if use_llm:
            resolved_text = _llm_invoke([HumanMessage(content=resolve_prompt)]).content.strip().lower()
            raw_terms = [t.strip() for t in resolved_text.split(",") if t.strip()]
            # Deterministic backstop for the instruction above -- see _META_TERMS.
            raw_terms = [t for t in raw_terms if t not in _META_TERMS]
            # The extraction LLM sometimes returns a word nobody said ("apa saja
            # unsurnya" -> "unsurlunya", conersation.md 2026-09-24). Keep a term only
            # if one of its words is close to a word actually present in the
            # conversation (or an entity already discussed) -- coreference
            # substitutions pass, inventions don't.
            said = set(re.findall(r"\w+", " ".join(
                turns + entity_history + [current_entity or ""]).lower()))
            raw_terms = [t for t in raw_terms if _term_is_grounded(t, said)]
    except Exception as e:
        # Ollama down/unreachable/timed out -- degrade instead of crashing the
        # action (every intent path runs through this function). No
        # coreference/ellipsis handling in this mode, but kb_resolver can still
        # match a self-contained question directly off the raw message.
        print(f"LLM term-extraction error: {e}")
        raw_terms = [user_msg.strip().lower()] if user_msg.strip() else []

    # Step 2: kb_resolver maps each free-text term to a canonical KB id --
    # exact name/alias -> force_merge -> modifier-strip -> rapidfuzz.
    # (No early return on an empty LLM list any more: the message's own terms
    # (Step 2b) and the topic fallback below still apply.)
    matches = []
    unresolved = []
    asked_as: Dict[str, str] = {}
    typed_as: Dict[str, str] = {}

    def note_spelling(m, term: str) -> None:
        # a different name for the same concept ("samskara" -> sangaskara), not a typo.
        # "ortho" too: the extraction LLM wrote "nggerorasin" for the user's
        # "ngerorasin" (an alias of Atma Wedana), and the answer then called
        # ngerorasin "a type of Atma Wedana" (2026-09-25)
        t, n = term.lower(), m.name.lower()
        if (m.via in ("alias", "force_merge", "ortho") and t not in n and n not in t
                and _ortho_key(t) != _ortho_key(n)):
            asked_as.setdefault(m.id, _user_spelling(term, user_msg, m.entity))
        elif m.via != "exact" and t != n and t in user_msg.lower():
            # the user's misspelling: the synthesis question uses the KB name instead,
            # or the model repeats it ("Moksaa adalah ... Moksaa sama dengan moksa")
            typed_as.setdefault(m.id, term)

    for term in raw_terms:
        term = _widen_to_named_term(_peel_aspect_words(term, resolver), user_msg, resolver)
        m = resolver.resolve(term)
        if m and m.id not in {x.id for x in matches}:
            matches.append(m)
            note_spelling(m, term)
        elif not m:
            unresolved.append(term)

    # Step 2b: the terms the message itself names -- a deterministic scan of its words
    # plus resolve_many()'s "X dan Y" split -- are added even when the extraction LLM
    # dropped or replaced them (e.g. "bade dan naga banda"; "... acara nglungah" -> ngaben).
    own: list = []
    for m in [mm for mm, _ in mentioned] + resolver.resolve_many(user_msg, limit=4):
        if m.id not in {x.id for x in own}:
            own.append(m)
    for m, surface in mentioned:
        note_spelling(m, surface)
    if not own and (len(leftover) >= 3 or re.search(r"\byang\b", user_msg, re.I)):
        # a term described rather than named (T69: "bayi yang giginya belum tanggal") -- not a
        # short name the KB lacks: "apa itu bahasa kawi" became layon, whose definition says
        # "sebutan halus (bahasa Bali/Kawi)" (conersation.md 2026-10-02)
        hit = _definition_hit(leftover, resolver)
        if hit:
            own.append(hit)
    # burning a body IS ngaben ("upacara pembakaran jenazah"), whose purpose answers "kenapa
    # orang bali membakar mayat?": named jenazah alone, the bot gave a stage-scoped attribute
    # as the reason (conersation.md 2026-10-02)
    if (_BURN_RE.search(user_msg) and any(m.id == "jenazah" for m in own)
            and not any(m.entity.get("type") == "RITUAL_KEMATIAN" for m in own)):
        hit = resolver.resolve("ngaben")
        if hit:
            own.insert(0, hit)
    # "hari apa yang harus dihindari untuk ngaben" asks about dewasa ngaben, which holds the
    # allowed and forbidden days -- the message never names it (live crosscheck T96)
    if _DAY_Q_RE.search(user_msg) and not any(m.id == "dewasa_ngaben" for m in own):
        hit = resolver.resolve("dewasa ngaben")
        if hit:
            own.insert(0, hit)
    matched_ids = {m.id for m in matches}
    for m in own:
        if m.id not in matched_ids:
            matches.append(m)
            matched_ids.add(m.id)
    # A term the extraction LLM carried over from the history is not part of a question
    # that names its own term(s): "apa itu nglungah" after a turn about ngaben came back
    # as [ngaben, ngelungah], "apa itu tujuan ngaben" after moksa as [ngaben, moksa]
    # (2026-09-29). The one exception is a relation/comparison question that names only
    # one term -- "apa hubungannya dengan jenazah" after a turn about sawa needs sawa.
    own_order = [m.id for m in own]
    needs_history = len(own_order) == 1 and bool(
        _RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg))
    # (clean_query peels "apa itu" but not "siapa itu", whose "itu" points at nothing)
    anaphor = bool(_ANAPHOR_RE.search(re.sub(r"^\s*siapa\s+itu\b", "", resolver.clean_query(user_msg))))
    # A message that names no term but has a word that is no everyday word ("thanks", "siapa
    # itu Pewdiepie", "apa itu bahasa kwai") asks about something the KB lacks. The extraction
    # LLM still returned the last topic, which the grounding check accepts (any word of the
    # history counts), so each was answered about jenazah / nyiramang layon (conersation.md
    # 2026-10-02). Without a word pointing back, only terms the message itself says count.
    unknown_word = (not own_order and not anaphor and not _ORDINAL_REF_RE.search(user_msg)
                    and any(not _is_everyday_word(w, resolver) for w in leftover))
    if (own_order and not needs_history) or unknown_word:
        said = set(re.findall(r"\w+", user_msg.lower()))
        matches = [m for m in matches if m.id in own_order or any(
            _term_is_grounded(n, said, _GENERIC_NAME_WORDS)
            for n in [m.name] + list(m.entity.get("aliases") or []))]
    # "lontar apa yang menjelaskan ngaben": the generic lontar node is the question word,
    # not a term (T94); the sources come from _source_facts
    if "sumber" in _aspect_families(user_msg) and len(matches) > 1:
        matches = [m for m in matches if m.id != "lontar"]
    # the message's own terms first, in its order: enriched[0] is the asked term
    matches.sort(key=lambda m: own_order.index(m.id) if m.id in own_order else len(own_order))

    # A follow-up about the topic puts it first: one that names no term and points back or
    # says nothing else ("jadi, kenapa tidak boleh?" after a malamasa question went to
    # ngaben, a term the extraction LLM took from the history -- T30/T31), and one that
    # names a term plus a standalone "itu" (T65). Until then only an empty match list fell
    # back to the topic.
    # ("no leftover" needs a question: a bare "ok" is not about the topic again)
    asks =bool("?" in user_msg or _SPECIFIC_Q_RE.search(user_msg) or _aspect_families(user_msg))
    if current_entity and not _ORDINAL_REF_RE.search(user_msg) and (
            (not own_order and (anaphor or (not leftover and asks)))
            or (own_order and _points_back(user_msg, mentioned, resolver))):
        topic = resolver.resolve(current_entity)
        if topic:
            matches = [topic] + [m for m in matches if m.id != topic.id]
    matched_ids = {m.id for m in matches}
    matches = matches[:4]

    # "arti kata (dasar) pitra yadnya": also look up each word of a multi-word
    # term on its own (exact/alias only -- a fuzzy hit on a single word is noise).
    if _WORD_MEANING_RE.search(user_msg):
        if len(matches) >= 2:
            joined = resolver.resolve(" ".join(m.name for m in matches))
            if joined and joined.via in ("exact", "alias") and joined.id not in matched_ids:
                matches.append(joined)
                matched_ids.add(joined.id)
        for m in list(matches):
            for word in m.name.split():
                w = resolver.resolve(word)
                if w and w.via in ("exact", "alias") and w.id not in matched_ids:
                    matches.append(w)
                    matched_ids.add(w.id)
        matches = matches[:6]

    if not matches:
        suggestions = []
        for term in unresolved:
            suggestions.extend(resolver.suggest(term, k=3))
        suggestions = list(dict.fromkeys(suggestions))  # dedupe, keep order
        _log_unresolved(user_msg, unresolved, suggestions)
        if announce_miss:
            if not unresolved:
                dispatcher.utter_message(text="Maaf, saya tidak menangkap istilah spesifik dari pertanyaan Anda.")
            elif suggestions:
                dispatcher.utter_message(
                    text=f"Maaf, saya tidak menemukan '{', '.join(unresolved)}' di basis data. "
                         f"Mungkin maksud Anda: {', '.join(suggestions)}?"
                )
            else:
                dispatcher.utter_message(
                    text=f"Maaf, informasi mengenai '{', '.join(unresolved)}' belum tercatat di basis data."
                )
        # Keep prior context intact for the next turn either way.
        return [], unresolved, []

    # Step 3: fetch the resolved entities from the graph by exact id, then layer
    # the curated KB content on top -- glossary/fact-derived definitions for
    # entities whose graph node has no `definition` property, plus supporting
    # facts for richer synthesis.
    content = get_content()
    entity_ids = [m.id for m in matches]
    graph_rows = {row["id"]: row for row in neo4j_conn.query(_GRAPH_QUERY, {"entity_ids": entity_ids,
                                                     "child_preds": sorted(_CHILD_DEF_PREDICATES)})}

    enriched = []
    for m in matches:
        row = graph_rows.get(m.id, {"id": m.id, "name": m.name, "graph_definition": None,
                                      "labels": [], "relationships": []})
        definition = content.best_definition(m.id, row.get("graph_definition"))
        # _GRAPH_QUERY's OPTIONAL MATCH + collect(DISTINCT {...}) is a known Cypher
        # gotcha: a node with zero matching relationships still yields one
        # {relation: null, target: null, target_labels: null} entry instead of an
        # empty list (confirmed live -- every :Isolated node, ~93/476 entities,
        # returns this). Drop it here rather than feed null junk into the LLM context.
        relationships = [r for r in row.get("relationships", []) if r.get("relation")]
        # The graph query is undirected, so each edge is rendered as a sentence in
        # its real direction. Handing the LLM bare {relation, target} pairs let it
        # guess the direction and invert it ("canang sari ... dilengkapi dengan
        # soda" for soda DILENGKAPI canang_sari, conersation.md 2026-09-24).
        ent_name = row.get("name") or m.name
        for r in relationships:
            subj, obj = (ent_name, r["target"]) if r.get("outgoing") else (r["target"], ent_name)
            variant = ({"region": r["variant_region"], "op": r["variant_op"],
                        "replaces": r.get("variant_replaces")} if r.get("variant_op") else None)
            r["statement"] = content.render_variant(r["relation"], subj, obj, variant)
        # For the is-a/part-of spine specifically, a bare child name is not enough
        # context to answer "what does each part mean" -- the LLM otherwise has to
        # guess from its own background knowledge and can mix up e.g. which Panca
        # Maha Bhuta element is which classical meaning, or (confirmed live: eteh
        # eteh sawa's 7 BERUPA-linked items -- leluwur, samsam, udeng, etc. --
        # each already have a specific, correct KB definition, e.g. samsam's is
        # "dipakai sebagai unsur pembuatan Tirtha Panglukatan...", but nothing
        # ever fetched it here since only TERMASUK_JENIS was checked) invent
        # identical generic filler for every child instead. BERUPA/TERDIRI_DARI
        # are the same "parent decomposes into standalone child concepts" shape
        # as TERMASUK_JENIS in this KB (see kb_content.PREDICATE_FAMILIES's
        # "bahan" family) -- not the full family, just the two whose object is
        # normally a linkable concept worth its own definition, rather than a
        # raw material/substance. Pull each child's own definition in
        # (glossary/facts-backed, no extra Neo4j round trip) so the answer is
        # actually grounded in this KB's text, not the model's memory. The cap on
        # how many reach the prompt is applied in _llm_context, AFTER the question
        # aspect has filtered the edges: capping here, in Cypher order, left the last
        # of ngaben's types (asti wedana) without a definition once ngaben gained its
        # 8 stages, and "apa saja jenis ngaben" then merged it into sawa wedana
        # (2026-09-25).
        for r in relationships:
            # only when the OTHER node is the child/part/member -- attaching the
            # parent's definition to a child's answer made the model restate the
            # parent ("mlaspas kajang termasuk salah satu jenis ngaben")
            child_is_target = (r.get("relation") in _CHILD_IS_OBJECT) == bool(r.get("outgoing"))
            if r.get("relation") in _CHILD_DEF_PREDICATES and child_is_target and r.get("target_id"):
                child_def = content.best_definition(r["target_id"])
                if child_def:
                    r["target_definition"] = child_def
        enriched.append({
            "id": m.id,
            "name": row.get("name") or m.name,
            "definition": definition or "Tidak ada definisi langsung",
            "labels": row.get("labels", []),
            "relationships": relationships,
            "facts": content.facts_for(m.id),
            "asked_as": asked_as.get(m.id),
            "typed_as": typed_as.get(m.id),
            # "sulinggih/griya" read as one name ("Gria juga dikenal sebagai sulinggih/griya", T51)
            "aliases": [a for a in (m.entity.get("aliases") or []) if len(a.split()) <= 4 and "/" not in a][:8],
        })

    if unresolved:
        _log_unresolved(user_msg, unresolved, [])
        # Only a missing second term of "hubungan/beda X dan Y" is worth a note -- the
        # other misses are qualifiers the extraction LLM returned as terms ("angka 11",
        # "masyarakat umum", "harganya"), and the note read as noise (2026-09-29).
        # nor one everyday word ("giginya") or a phrase whose words were all found as terms
        # ("sasih kliwon" -> sasih + kliwon), conersation.md 2026-10-02; "mata angin" (two
        # everyday words, no term) still gets the note
        found_words = {w for e in enriched for w in e["name"].lower().split()}
        # "sasih kliwon" with sasih dropped as a wrong class word: the answer corrects it instead
        misclassed = {f"{cs} {ts}".lower() for _, cs, _, ts in _misclassed_terms(user_msg, resolver)}
        typed = [t for t in unresolved if t.lower() in user_msg.lower()
                 and not any(t.lower() in (e["name"].lower(), e.get("typed_as") or "") for e in enriched)
                 and not (len(t.split()) == 1 and _is_everyday_word(t.lower(), resolver))
                 and not all(w in found_words for w in t.lower().split())
                 and t.lower() not in misclassed]
        if typed and (_RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg)):
            # the synthesis model is told too, or it relates the missing term anyway
            # ("Sasih kliwon adalah salah satu jenis pitra yadnya")
            enriched[0]["missing_terms"] = typed
            if announce_miss:
                dispatcher.utter_message(
                    text=f"(Catatan: '{', '.join(typed)}' tidak ditemukan, melanjutkan dengan yang lain.)"
                )

    found_names = [row["name"] for row in enriched]
    return enriched, unresolved, found_names


# Question aspect -> the family of edge AND text-only attribute predicates relevant to
# it (families: kb_content.PREDICATE_FAMILIES, shared with kb_lint). On a hub node
# (ngaben has ~30 edges) the small model otherwise mixes kinds up -- e.g. listing
# ngaben's TYPES (ngaben massal, sawa prateka) as its "sebutan lain" (other names).
# Attributes ("kawangen melambangkan sikap amusti karana", "besi berwarna hitam")
# are shown ONLY when their aspect is asked -- never for a plain "apa itu X", where
# unrelated facts read as tangents (conersation.md 2026-09-24).
_KINDS_Q_RE = re.compile(r"\bjenis\b|\bmacam\b|\bragam\b|\bcontoh", re.I)
# "bagaimana alur prosesi ngaben", "ceritakan proses ngaben dari awal sampai akhir" ask for
# the stages too: as "cara" alone they got an invented sequence (T38/T103/T104)
_PROCESS_Q_RE = re.compile(r"\balur\b|\bprose(s|si)\b|\blangkah|\bdari awal (sampai|hingga)\b", re.I)
_STAGES_Q_RE = re.compile(r"\btahap|\burutan\b|\brangkaian\b|" + _PROCESS_Q_RE.pattern, re.I)
# which days are allowed / avoided: dewasa ngaben holds them (T96)
_DAY_Q_RE = re.compile(r"\bhari\b(?:\s+\w+){0,6}?\s+(?:baik|buruk|dihindari|pantang|dilarang|tidak boleh|cocok|tepat)\b",
                       re.I)
# a list question ("banten apa saja ...", "sebutkan ...") -- see _class_filter
_LIST_Q_RE = re.compile(r"\bapa saja\b|\bsebutkan\b|\bmana saja\b|\bapa-apa saja\b", re.I)
_COMPARE_Q_RE = re.compile(r"\bperbedaan\b|\bbeda(nya)?\b|\bmembedakan\b", re.I)
# "apa hubungan X dengan Y": with every edge of both terms in context the model padded
# the answer with each term's unrelated facts ("sawa ... disertai kakawin ... berada di
# galar", conersation.md items 5 and 7, 2026-09-25) -- only the linking edges are shown
# "apa itu ngaben tanpa tirtha pangentas" asks how X stands without Y -- the same
# linking facts; with both terms' full edge lists it came back as a 7-part dump
_RELATION_Q_RE = re.compile(r"\bhubungan(nya)?\b|\bkaitan(nya)?\b|\bberhubungan\b|\bterkait\b|\btanpa\b",
                            re.I)
_ASPECT_FAMILIES = (
    (re.compile(r"sebutan lain|nama lain|istilah lain|disebut juga|dikenal (juga )?sebagai|sinonim", re.I),
     "sebutan_lain"),
    (_KINDS_Q_RE, "jenis"),
    (_STAGES_Q_RE, "tahapan"),
    # a process question keeps its how-facts as well as the stages
    (_PROCESS_Q_RE, "cara"),
    # what X is made of / contains / comes with ("soda dilengkapi apa?", "apa isi punjung")
    (re.compile(r"dilengkapi|kelengkapan|\bisi(nya)?\b|berisi|terdiri|terbuat|\bbahan|komponen|\bunsur", re.I),
     "komposisi"),
    (re.compile(r"\bmakna|\blambang|melambangkan|simbol|filosofi", re.I), "simbol"),
    # "dari mana diperoleh" (T92: tirta pangentas is made at the gria or at home)
    (re.compile(r"di ?mana|\bletak(nya)?\b|diletakkan|ditaruh|ditempatkan|ke ?mana|dari ?mana|\bposisi", re.I),
     "lokasi"),
    (re.compile(r"\bkapan\b|hari apa|berapa hari|hari ke|\bwaktu(nya)?\b|saat apa|\bsyarat|"
                r"hari baik|\bdewasa\b|padewasan", re.I), "waktu"),
    (_DAY_Q_RE, "waktu"),
    (re.compile(r"\bsiapa (yang|saja)\b|oleh siapa|dipimpin|dilakukan oleh|\bpelaku", re.I), "pelaku"),
    (re.compile(r"\bwarna|\bbentuk(nya)?\b|berbentuk|ukuran|\bpanjang(nya)?\b|\bciri|bertingkat|"
                r"berapa (tingkat|panjang|banyak|lapis|kali|buah|lembar)", re.I), "ciri"),
    (re.compile(r"\bfungsi|kegunaan|\bguna(nya)?\b|untuk apa|\btujuan|\bbertujuan|manfaat|\bperan(an|nya)?\b|"
                r"\bakibat|\bdampak|\bmengapa\b|\bkenapa\b|\balasan", re.I), "fungsi"),
    # a reason is as often a meaning as a purpose: with fungsi alone, "kenapa bade ada yang
    # bertingkat 11" lost "bade menunjukkan status sosial seseorang" (MENUNJUKKAN, simbol)
    # and rule 21 then said the reason was not recorded (2026-09-30)
    (_WHY_Q_RE, "simbol"),
    # which lontar describes a term (DIJELASKAN_DALAM / MERINCI edges)
    (re.compile(r"lontar apa|naskah apa|\bsumber(nya)?\b|dijelaskan dalam|diuraikan dalam", re.I), "sumber"),
    # which offerings/equipment a ceremony uses ("apa saja sarana upacara ngaben",
    # "apa saja sarananya"); _stage_sarana_facts adds those of its stages
    (re.compile(r"\bsaranan?\w*|\bperlengkapan|\bupakara\w*|\bbanten apa|\bsesajen apa|\balat(-alat)?\b", re.I),
     "sarana"),
)
# "digunakan untuk" is fungsi only when nothing more specific matched: in "hari baik yang
# cocok digunakan untuk melaksanakan ngaben" it pulled ngaben's purpose facts (2026-09-29)
_FUNGSI_WEAK_RE = re.compile(r"dipakai untuk|digunakan untuk", re.I)
# "how / what happens" is the broadest aspect: used only when no specific one matched,
# and never for "bagaimana hubungan/perbedaan X dan Y" (a relation question needs every edge)
_HOW_RE = re.compile(r"\bbagaimana\b(?!\s+(hubungan|kaitan|perbedaan|beda))|\bcara\b|\bprose(s|si)\b|"
                     r"diperlakukan|apa yang terjadi|menjadi apa|\bberubah", re.I)


# every pattern that names a question aspect (see _mentioned_terms' leftover words)
_ASPECT_WORD_RES = [p for p, _ in _ASPECT_FAMILIES] + [_FUNGSI_WEAK_RE, _HOW_RE]


_COMPOSITION_Q_RE = re.compile(r"dilengkapi|kelengkapan|\bisi(nya)?\b|berisi|terdiri|terbuat|\bbahan|komponen", re.I)
# what X itself holds or is made of -- not "unsur"/"terdiri", whose members are often kinds
# (Panca Maha Bhuta's elements). "apa saja isi banten peras" was answered with its kinds and
# with the banten it is inside of (T82).
_CONTENTS_Q_RE = re.compile(r"dilengkapi|kelengkapan|\bisi(nya)?\b|berisi|terbuat|\bbahan|komponen", re.I)
_MEMBERS_Q_RE = re.compile(r"\bunsur|terdiri", re.I)
# "jelaskan isi banten peras satu per satu" wants each part explained (rule 9)
_EXPLAIN_EACH_RE = re.compile(r"\bjelaskan\b|\bsetiap\b|\btiap\b|\bmasing-masing\b|\bsatu per satu\b", re.I)
_NUMBER_WORDS = {"1": "satu", "2": "dua", "3": "tiga", "4": "empat", "5": "lima", "6": "enam", "7": "tujuh",
                 "8": "delapan", "9": "sembilan", "10": "sepuluh", "11": "sebelas", "12": "duabelas"}
# "karena": jenazah bayi's tiers each say why ("karena ia masih dinilai suci murni"), yet "kenapa
# jenazah bayi tidak boleh dibakar?" opened with "Maaf, alasannya belum tercatat" (Tier B 2026-10-05)
_MEANING_IN_DEF_RE = re.compile(r"\b(?:melambangkan|menggambarkan|bermakna|maknanya|menyimbolkan|"
                                r"karena|sebab)\b", re.I)
_VERB_FORM_RE = re.compile(r"^(?:di|me[mny]?|meng|meny|ber|ter)\w{3,}(?:kan|i)$", re.I)
_TELL_Q_RE = re.compile(r"\b(?:ceritakan|uraikan|jelaskan|terangkan)\b", re.I)
_YES_NO_Q_RE = re.compile(r"^\s*(?:jadi,?\s+)?apakah\b", re.I)
_KIND_PREDICATES = frozenset({"TERMASUK_JENIS", "MEMILIKI_JENIS"})
# a definition that itself states contents ("terbuat dari daun lontar", "berisi aksara")
_CONTENTS_IN_DEF_RE = re.compile(r"\bberisi|\bterdiri (?:dari|atas)|\bterbuat dari|\bdibuat dari|\bbahan|\bisinya|"
                                 r"\bdilengkapi|\bdiisi", re.I)


def _contents_question(user_msg: Text) -> bool:
    return bool(_CONTENTS_Q_RE.search(user_msg) and not _MEMBERS_Q_RE.search(user_msg)
                and not _KINDS_Q_RE.search(user_msg))


def _aspect_families(user_msg: Text) -> List[str]:
    families = [fam for pattern, fam in _ASPECT_FAMILIES if pattern.search(user_msg)]
    if not families and _FUNGSI_WEAK_RE.search(user_msg):
        families = ["fungsi"]
    if not families and _HOW_RE.search(user_msg):
        families = ["cara"]
    return families


def _aspect_predicates(user_msg: Text) -> Optional[set]:
    families = _aspect_families(user_msg)
    if not families:
        return None
    preds = set().union(*(PREDICATE_FAMILIES[f] for f in families))
    if _contents_question(user_msg):
        preds -= _KIND_PREDICATES
    return preds


# Offerings/equipment used in a ceremony are mostly linked to its stages, not to the
# ceremony itself: ngaben had 2 direct ones (sarana_coverage_report.md, 2026-09-29).
_STAGE_SARANA_QUERY = """
UNWIND $entity_ids AS eid
MATCH (n:Node {id: eid})
OPTIONAL MATCH (st:Node)-[b:BAGIAN_DARI*1..2]->(n)
WHERE all(x IN b WHERE coalesce(x.confidence, '') <> 'LOW')
WITH n, [n] + collect(DISTINCT st) AS places
UNWIND places AS p
MATCH (s:Node)-[r]-(p)
// buildings (gupura, payadnyan, sanggar surya) are where a stage happens, not its sarana:
// "banten apa saja yang dipakai dalam atma wedana" listed them as banten (2026-09-30)
WHERE coalesce(r.confidence, '') <> 'LOW' AND s <> n AND NOT s:BANGUNAN_RITUAL AND (
      (type(r) IN $use_in AND startNode(r) = s) OR (type(r) IN $use_out AND startNode(r) = p))
RETURN n.id AS id, p.id AS place_id, p.name AS place, collect(DISTINCT s.name) AS items
"""
_SARANA_USE_IN = ("DIGUNAKAN_DALAM", "DIGUNAKAN_PADA", "DIGUNAKAN_SAAT", "DIPAKAI_UNTUK", "DIGUNAKAN_UNTUK")
_SARANA_USE_OUT = ("MENGGUNAKAN", "MEMAKAI")


def _stage_sarana_facts(enriched: List[Dict[str, Any]]) -> None:
    """Set e["sarana_facts"]: one sentence per ceremony/stage listing what it uses."""
    rows = neo4j_conn.query(_STAGE_SARANA_QUERY, {"entity_ids": [e["id"] for e in enriched],
                                                  "use_in": list(_SARANA_USE_IN),
                                                  "use_out": list(_SARANA_USE_OUT)})
    by_id: Dict[str, List[str]] = {}
    for r in rows:
        items = sorted(set(r["items"]))
        if not items:
            continue
        e_name = next(e["name"] for e in enriched if e["id"] == r["id"])
        # the ceremony's own items are named as such -- labelled like a stage, the model
        # skipped them and "sarana ngaben" came back without bade (Tier B 2026-09-29)
        where = (f"{e_name} itu sendiri (bukan hanya tahapannya)" if r["place_id"] == r["id"]
                 else f"{r['place']} (bagian dari {e_name})")
        by_id.setdefault(r["id"], []).append(f"Sarana yang digunakan dalam {where}: {', '.join(items)}")
    for e in enriched:
        e["sarana_facts"] = sorted(by_id.get(e["id"], []), key=lambda f: "(bagian dari" in f)


# Which lontar describes a term: the sources are mostly linked to its kinds and stages
# (ngaben has none of its own; sawa prateka, ngaben svasta, ... are in Lontar Sundarigama).
# "lontar apa yang menjelaskan tentang ngaben" got "lontar yang merinci pitra" (T94).
_SOURCE_QUERY = """
UNWIND $entity_ids AS eid
MATCH (n:Node {id: eid})
OPTIONAL MATCH p = (k:Node)-[:TERMASUK_JENIS|BAGIAN_DARI*1..2]->(n)
WHERE all(x IN relationships(p) WHERE coalesce(x.confidence, '') <> 'LOW')
WITH n, collect(DISTINCT {node: k, kind: all(x IN relationships(p) WHERE type(x) = 'TERMASUK_JENIS')}) AS ks
UNWIND [{node: n, kind: null}] + ks AS item
WITH n, item WHERE item.node IS NOT NULL
MATCH (k:Node)-[r:DIJELASKAN_DALAM|MERINCI]-(l:Node)
WHERE k = item.node AND coalesce(r.confidence, '') <> 'LOW' AND l <> n
RETURN n.id AS id, k.name AS item, item.kind AS kind, type(r) AS rel, startNode(r) = k AS outgoing,
       l.name AS source
"""


def _source_facts(enriched: List[Dict[str, Any]]) -> None:
    """Set e["source_facts"]: one sentence per lontar that describes the term or one of
    its kinds/stages."""
    rows = neo4j_conn.query(_SOURCE_QUERY, {"entity_ids": [e["id"] for e in enriched]})
    content = get_content()
    by_id: Dict[str, List[str]] = {}
    for r in rows:
        subj, obj = (r["item"], r["source"]) if r["outgoing"] else (r["source"], r["item"])
        fact = content.render(r["rel"], subj, obj)
        e_name = next(e["name"] for e in enriched if e["id"] == r["id"])
        if r["kind"] is not None:
            fact += f" ({r['item']} adalah {'jenis' if r['kind'] else 'bagian'} dari {e_name})"
        if fact not in by_id.setdefault(r["id"], []):
            by_id[r["id"]].append(fact)
    for e in enriched:
        e["source_facts"] = by_id.get(e["id"], [])


# A list question about a class and a term ("banten apa saja yang dipakai saat nyiramang
# layon", "sasih apa saja yang baik untuk atma wedana"): the term's items are cut to members
# of the class, and the class's kinds to those tied to the term. Unfiltered, the first got
# every sarana of the stage (T79) and the second the sasih for Ngaben (T102).
_FOR_TERM_RE = r"\b(?:untuk|dalam|pada|saat|ketika|selama|di|sewaktu)\s+(?:\w+\s+){{0,2}}{}\b"


def _class_filter(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[tuple]:
    """Filter enriched in place; returns (class name, [term names]) when it applied."""
    if len(enriched) < 2:
        return None
    content = get_content()
    cls = enriched[0]
    if not content.kinds_of(cls["id"]) or not (
            _LIST_Q_RE.search(user_msg) or re.search(rf"\b{re.escape(cls['name'])}\s+apa\b", user_msg, re.I)):
        return None
    low = user_msg.lower()
    terms = [e for e in enriched[1:]
             if any(re.search(_FOR_TERM_RE.format(re.escape(s.lower())), low)
                    for s in [e["name"]] + (e.get("aliases") or []) + [e.get("asked_as") or "", e.get("typed_as") or ""]
                    if s)]
    if not terms:
        return None

    def is_member(eid: Optional[str]) -> bool:
        return bool(eid) and eid != cls["id"] and content.is_kind_of(eid, cls["id"])

    reach: set = set()
    names: List[str] = []
    for t in terms:
        reach |= {r.get("target_id") for r in t.get("relationships") or []}
        names += [t["name"]] + (t.get("aliases") or [])
        names += [content.entity_name.get(k, "") for k in content.kinds_of(t["id"])]
        # the term's items: members of the class only
        t["relationships"] = [r for r in t.get("relationships") or [] if is_member(r.get("target_id"))]
        kept_facts = []
        for fact in t.get("sarana_facts") or []:
            head, items = fact.split(":", 1)
            items = [x.strip() for x in items.split(",")
                     if is_member(content.id_by_name.get(x.strip().lower()))]
            reach |= {content.id_by_name.get(x.lower()) for x in items}
            if items:
                kept_facts.append(f"{head}: {', '.join(items)}")
        t["sarana_facts"] = kept_facts
    name_res = [re.compile(rf"\b{re.escape(n.lower())}\b") for n in names if n]

    def tied(r: Dict[str, Any]) -> bool:
        d = (content.best_definition(r.get("target_id")) or "").lower()
        return r.get("target_id") in reach or any(p.search(d) for p in name_res)

    # the class's kinds tied to the term; its other facts are not what the list asks
    cls["relationships"] = [r for r in cls.get("relationships") or []
                            if r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing") and tied(r)]
    cls["sarana_facts"] = []
    return cls["name"], [t["name"] for t in terms]


# "tahap kelima dari delapan tahapan pelaksanaan Ngaben" -> 5
_ORDINALS = {"pertama": 1, "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5, "keenam": 6,
             "ketujuh": 7, "kedelapan": 8, "kesembilan": 9, "kesepuluh": 10}
_STAGE_NUM_RE = re.compile(r"\btahap(?:an)?\s+(?:ke-?\s*(\d+)|(" + "|".join(_ORDINALS) + r"))\b", re.I)


def _stage_number(definition: Optional[Text]) -> Optional[int]:
    m = _STAGE_NUM_RE.search(definition or "")
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else _ORDINALS[m.group(2).lower()]


def _numbered_stages(e: Dict[str, Any]) -> List[tuple]:
    """(number, name) of e's stages whose definitions number them, in order."""
    content = get_content()
    out = []
    for r in e.get("relationships") or []:
        if r.get("relation") == "BAGIAN_DARI" and not r.get("outgoing"):
            n = _stage_number(content.best_definition(r.get("target_id")))
            if n:
                out.append((n, r["target"]))
    out = sorted(set(out))
    return out if len({n for n, _ in out}) >= 2 else []


def _order_stages(e: Dict[str, Any]) -> None:
    """Numbered stages first, in their number order, so the context reads like the corpus
    list (T75 numbered Mlaspas Kajang twice and put Nguyeg third)."""
    content = get_content()

    def key(r: Dict[str, Any]) -> int:
        if r.get("relation") == "BAGIAN_DARI" and not r.get("outgoing"):
            return _stage_number(content.best_definition(r.get("target_id"))) or 99
        return 100
    e["relationships"] = sorted(e.get("relationships") or [], key=key)


def _complete_unnumbered_stages(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """Stages no definition numbers (atma wedana's nguyeg, amrethi karana, pralina): an answer
    leaving one out gets the recorded ones listed, with no order claimed. The model listed atma
    wedana's kinds as its stages 1-3, _drop_kinds_from_stages took them out, and nguyeg was never
    named (Tier B 2026-10-05)."""
    if not enriched:
        return answer
    resolver, said = get_resolver(), _ortho_key(answer)
    names, missing = [], False
    for r in enriched[0].get("relationships") or []:
        if r.get("relation") != "BAGIAN_DARI" or r.get("outgoing") or not r.get("target"):
            continue
        name = r["target"]
        if name in names:
            continue
        names.append(name)
        hit = resolver.resolve(name)
        surfaces = [name] + (list(hit.entity.get("aliases") or []) if hit else [])
        if not any(len(s) >= 5 and _ortho_key(s) in said for s in surfaces):
            missing = True
    if len(names) < 2 or not missing:
        return answer
    listed = ", ".join(n[:1].upper() + n[1:] for n in names)
    return answer.rstrip() + f"\nTahapan {enriched[0]['name']} yang tercatat: {listed}."


def _complete_stage_order(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A stages answer -- a list or a told story -- that leaves a stage out, gives one out of
    the corpus order, lists one twice, or numbers an unnumbered part in a stage's place, gets
    the corpus order appended (built from the definitions' numbers). A list that numbers its
    items its own way but keeps the order ("3. Pangringkes (tahap kedua)") is left alone: the
    appended line only repeated it (conersation.md 2026-10-02). The user accepted the model's
    own numbering as long as every stage is there and in order (2026-10-02)."""
    stages = _numbered_stages(enriched[0]) if enriched else []
    if not stages:
        return _complete_unnumbered_stages(answer, enriched)
    want: Dict[str, set] = {}
    alts: Dict[str, str] = {}     # a name or alias's key -> the stage's key ("ngeringkes" in a story)
    resolver = get_resolver()
    for n, name in stages:
        key = _ortho_key(name)
        want.setdefault(key, set()).add(n)
        alts[key] = key
        hit = resolver.resolve(name)
        # its aliases and force_merge spellings ("ngeringkes" is pangringkes)
        surfaces = list(hit.entity.get("aliases") or []) if hit else []
        surfaces += [k for k, v in resolver.force_merge.items() if hit and v == hit.id]
        for alias in surfaces:
            if len(alias) >= 5 and "/" not in alias:
                alts.setdefault(_ortho_key(alias), key)
    seen: Dict[str, int] = {}
    wrong = False
    lines = list(re.finditer(r"(?m)^\s*(\d+)[.)]\s*\**([^:\n(*]+)", answer))
    for m in lines:
        key = _ortho_key(m.group(2).strip())
        hit = next((alts[k] for k in alts if k and (k in key or key in k)), None)
        if hit is None:
            # an unnumbered part in a numbered stage's place ("2. Mlaspas Kajang")
            wrong = True
            continue
        seen[hit] = seen.get(hit, 0) + 1
        if seen[hit] > 1:
            wrong = True
    # where each stage is first named, from the list on when there is one (an intro sentence
    # may name a few stages out of order)
    said = _ortho_key(answer[lines[0].start():] if lines else answer)
    pos = {k: min((p for a, s in alts.items() if s == k for p in [said.find(a)] if p >= 0), default=-1)
           for k in want}
    if any(p < 0 for p in pos.values()):
        wrong = True
    else:
        numbers = [min(want[k]) for k in sorted(want, key=pos.get)]
        if any(a > b for a, b in zip(numbers, numbers[1:])):
            wrong = True
    if not wrong:
        return answer
    by_num: Dict[int, List[str]] = {}
    for n, name in stages:
        by_num.setdefault(n, []).append(name[:1].upper() + name[1:])
    order = ", ".join(f"{n}. {'/'.join(names)}" for n, names in sorted(by_num.items()))
    return answer.rstrip() + f"\nUrutan tahapan menurut sumber: {order}."


# a list item, or a sentence that files something under the asked term
_LIST_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s")
_FILED_UNDER_RE = re.compile(r"\b(meliputi|terdiri|mencakup|tahap(?:an)?|rangkaian)\b", re.I)


def _drop_kinds_from_stages(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A stages answer lists stages only: a list item or a "meliputi/terdiri/tahap ..."
    sentence that names a kind (jenis) of the asked term and none of its stages goes, and a
    heading left with no list under it goes too. "apa saja tahapan atma wedana" ended with
    "Selain tahap-tahap tersebut, Atma Wedana juga meliputi: - Mamukur, Sekah Kurung, dan
    Ngangsen" -- kinds named in its definition (Tier B 2026-10-02), although rule 15 says a
    jenis is never a stage."""
    if not enriched:
        return answer
    e, content = enriched[0], get_content()
    kinds = [content.entity_name.get(k, "") for k in content.kinds_of(e["id"])]
    stages = [r.get("target") or "" for r in e.get("relationships") or []
              if r.get("relation") == "BAGIAN_DARI" and not r.get("outgoing")]
    kind_res = [re.compile(rf"\b{re.escape(k)}\b", re.I) for k in kinds if k]
    stage_res = [re.compile(rf"\b{re.escape(s)}\b", re.I) for s in stages if s]
    if not kind_res:
        return answer

    def kind_only(text: Text) -> bool:
        return any(p.search(text) for p in kind_res) and not any(p.search(text) for p in stage_res)

    lines = []
    for line in answer.split("\n"):
        if _LIST_ITEM_RE.match(line):
            if not kind_only(line):
                lines.append(line)
            continue
        sents = re.split(r"(?<=[.!?])\s+", line)
        lines.append(" ".join(s for s in sents if not (kind_only(s) and _FILED_UNDER_RE.search(s))))
    out = []
    for i, line in enumerate(lines):
        if line.rstrip().endswith(":"):
            nxt = next((x for x in lines[i + 1:] if x.strip()), "")
            if not _LIST_ITEM_RE.match(nxt):
                continue
        out.append(line)
    # the numbered items left are renumbered: with the three kinds gone, the stages list
    # started at "4. Amrethi Karana" (Tier B 2026-10-05)
    numbered = re.compile(r"^\s*\d+[.)]\s")
    if sum(bool(numbered.match(x)) for x in out) < sum(bool(numbered.match(x)) for x in answer.split("\n")):
        counter = iter(range(1, 1000))
        out = [re.sub(r"^(\s*)\d+([.)])", lambda m: f"{m.group(1)}{next(counter)}{m.group(2)}", line)
               if numbered.match(line) else line for line in out]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _complete_kind_lists(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """An answer that names at least half of the asked term's kinds names all of them:
    "apa itu sasih" listed eleven sasih and dropped Kawulu (T21). A numeral set is
    _complete_set_members' job. Only for "apa itu X" / "jenis X" -- a question that picks
    some kinds ("sasih yang cocok ...") must not get the others appended."""
    if not enriched or _NUMERAL_SET_RE.match(enriched[0].get("name") or ""):
        return answer
    e = enriched[0]
    kinds = []
    for r in e.get("relationships") or []:
        if r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing") and r.get("target") not in kinds:
            kinds.append(r["target"])
    if len(kinds) < 3:
        return answer
    said = _ortho_key(answer)
    missing = [k for k in kinds if _ortho_key(k) not in said]
    if missing and (len(kinds) - len(missing)) * 2 >= len(kinds):
        answer = answer.rstrip() + f" Jenis {e['name']} lainnya yang tercatat: {', '.join(missing)}."
    return answer


# "Maaf, alasannya belum tercatat di basis data. Namun, berdasarkan fakta yang ada, ..." when
# the context HAS the reason (T39/T68/T74)
_WHY_REFUSAL_RE = re.compile(r"^\s*Maaf,\s*alasannya belum tercatat di basis data\.\s*"
                             r"(?:Namun,?\s*(?:berdasarkan fakta yang (?:ada|tercatat),?\s*)?)?", re.I)
_REASON_FAMILIES = PREDICATE_FAMILIES["fungsi"] | PREDICATE_FAMILIES["simbol"]


def _has_reason_facts(enriched: List[Dict[str, Any]]) -> bool:
    """A purpose or meaning of a term itself: an attribute, an edge FROM it, or a definition that
    states one ("Nganyut ... melambangkan pelepasan terakhir menuju moksha" opened with "Maaf,
    alasannya belum tercatat", Tier B 2026-10-02)."""
    return any(e.get("aspect_facts") or _MEANING_IN_DEF_RE.search(e.get("definition") or "")
               or any(r.get("relation") in _REASON_FAMILIES and r.get("outgoing")
                      for r in e.get("relationships") or [])
               for e in enriched)


# the same refusal inside the answer: "... tanpa memilih hari baik. Alasannya belum tercatat di basis
# data, namun ini karena bayi dianggap masih suci murni ..." (Tier B 2026-10-05)
_WHY_REFUSAL_INNER_RE = re.compile(r"(?<=[.!?]\s)\s*(?:Maaf,\s*)?alasannya belum tercatat di basis data[.,]?\s*"
                                   r"(?:namun,?\s*)?(\w)", re.I)


def _strip_why_refusal(answer: Text) -> Text:
    """Cut the refusal when facts follow it; an answer that is only the refusal stays."""
    out = _WHY_REFUSAL_RE.sub("", answer, count=1).strip()
    out = _WHY_REFUSAL_INNER_RE.sub(lambda m: m.group(1).upper(), out)
    if out == answer.strip() or len(out.split()) < 4:
        return answer
    return out[:1].upper() + out[1:]


# Hedges the model uses to guess: "Biasanya melibatkan keluarga dekat, tetua desa ..." for
# who performs pangringkes (T64), "... sebelum dimasukkan ke dalam kubur" (T66)
_SPECULATION_RE = re.compile(r"\b(mungkin|barangkali|kemungkinan|biasanya|umumnya|pada umumnya)\b", re.I)
# The closing filler of a list answer: "Setiap komponen memiliki peran khusus dalam upacara
# Ngaben, baik sebagai simbolisme maupun dalam proses ritual." after the contents of banten
# penebusan, whose context says nothing about roles (Tier B 2026-10-02)
_ROLE_FILLER_RE = re.compile(r"\b(?:setiap|masing-masing|semua|seluruh)\b[^.!?\n]*"
                             r"\b(?:peran|perannya|makna|maknanya|fungsi|fungsinya|tujuan|arti)\b", re.I)
# A sentence announcing its own guess: "Meskipun tidak disebutkan secara spesifik tujuan utamanya
# dapat dipahami sebagai persiapan jenazah ..." (pangringkes), "Meskipun informasi spesifik ...
# tidak, dapat ditarik kesimpulan ..." (nyiram layon), conersation.md 2026-10-02. Always a guess.
# A hedged reason is a guess too: "Alasan menghindari sasih paruwak tahuk dan malamasa mungkin
# karena dianggap tidak baik untuk upacara-upacara besar" (Tier B 2026-10-02); no KB text says
# "mungkin karena".
_INFERENCE_RE = re.compile(r"\bdapat (?:ditarik (?:sebuah )?kesimpulan|disimpulkan|dipahami sebagai|diasumsikan)"
                           r"|\bmeskipun (?:informasi[^.!?\n]*|tidak (?:disebutkan|dijelaskan)\b)"
                           r"|\btidak disebutkan secara (?:spesifik|eksplisit|rinci)"
                           r"|\b(?:mungkin|kemungkinan(?: besar)?|diduga)\s+(?:karena|disebabkan|terkait dengan)\b",
                           re.I)


_VAGUE_REASON_RE = re.compile(r"\b(energi|positif|negatif|keberuntungan|keberkahan|kesialan|aura|vibrasi)\b", re.I)


def _drop_speculation(answer: Text, context_text: Text) -> Text:
    """Drop a sentence that hedges with a word the context itself never uses (the
    definitions do say "biasanya tiga lembar", "mungkin bertingkat"), or that says each item
    has its own role, AND whose other content words are mostly not in the context:
    "Palebon adalah istilah halus untuk ... ngaben, yang biasanya dipakai untuk kalangan
    tertentu" is the definition reworded and stays. Never leaves nothing."""
    ctx = context_text.lower()
    vocab = _content_words(context_text)

    def guessed(s: str) -> bool:
        if _INFERENCE_RE.search(s):
            return True
        # the model's stock metaphysics when no reason is recorded: "energi negatif", "kekuatan
        # positif", "membawa keberuntungan" (malamasa / paruwak tahuk, Tier B 2026-10-05)
        if any(not re.search(rf"\b{w}\b", ctx) for w in _VAGUE_REASON_RE.findall(s.lower())):
            return True
        # a reason told in words the context never uses: "... karena dianggap memiliki energi
        # negatif atau tidak sesuai dengan energi positif yang diinginkan" for malamasa (Tier B
        # 2026-10-05), whose context only says it is "dinilai tidak baik"
        reason = re.search(r"\b(?:karena|sebab)\b(.*)", s, re.I)
        if reason:
            rwords = _content_words(reason.group(1))
            unground = sum(not _grounded(w, vocab) for w in rwords)
            if unground >= 3 and unground * 3 >= 2 * len(rwords):
                return True
        hedges = {m.group(1).lower() for m in _SPECULATION_RE.finditer(s)}
        unstated = any(not re.search(rf"\b{re.escape(h)}\b", ctx) for h in hedges)
        if not unstated and not _ROLE_FILLER_RE.search(s):
            return False
        words = [w for w in _content_words(s) if w not in hedges]
        return not words or sum(not _grounded(w, vocab) for w in words) * 2 >= len(words)

    parts = re.findall(r"[^.!?\n]+[.!?]*", answer)
    drop = [s for s in parts if guessed(s)]
    if not drop or len(drop) == len([s for s in parts if s.strip()]):
        return answer
    out = answer
    for s in drop:
        out = out.replace(s, "", 1)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _trim_cut_off(answer: Text) -> Text:
    """An answer stopped at LLM_NUM_PREDICT ends mid-word ("... sarana seperti ulantaga
    (walantaga), keki", T80): cut its last line back to its last full sentence, or drop
    that line when it has none. A period after a list number ("2.") is not a sentence end."""
    s = answer.rstrip()
    start = s.rfind("\n") + 1
    ends = [m.end() for m in re.finditer(r"(?<!\d)[.!?](?=\s)", s[start:])]
    if ends:
        return s[:start + ends[-1]].rstrip()
    return s[:start].rstrip() or s


# What rule 23 calls each asked aspect that no fact covers. jenis, sebutan_lain, asal_kata
# and cara are left out: their absence is shown by the definition alone.
_ASPECT_LABELS = {
    "pelaku": "who performs it", "lokasi": "where it is (or where it comes from)", "waktu": "when it is done",
    "fungsi": "its purpose", "simbol": "its meaning", "ciri": "its form", "tahapan": "its stages",
    "komposisi": "what it contains or is made of", "sarana": "which sarana it uses",
    "sumber": "which lontar describes it",
}
# the asked term's own purpose / meaning is an edge FROM it ("X DIGUNAKAN_DALAM nyiramang
# layon" is X's purpose, not nyiramang layon's)
_OUTGOING_ONLY_FAMILIES = frozenset({"fungsi", "simbol"})


def _aspect_present(family: str, enriched: List[Dict[str, Any]]) -> bool:
    """Whether any term has a fact of the asked aspect ("berapa tingkat bade" also resolved
    tingkatan upacara first; bade's tier counts are still the answer)."""
    preds = PREDICATE_FAMILIES[family]
    content = get_content()
    for e in enriched:
        if family == "sarana" and e.get("sarana_facts") or family == "sumber" and e.get("source_facts"):
            return True
        if content.attribute_sentences(e["id"], preds):
            return True
        if family == "komposisi" and content.inherited_parts(e["id"])[0]:
            return True
        if any(r.get("relation") in preds and (r.get("outgoing") or family not in _OUTGOING_ONLY_FAMILIES)
               for r in e.get("relationships") or []):
            return True
    return False


# "apakah masyarakat umum boleh memakai bade?" (T73)
_PERMISSION_Q_RE = re.compile(r"\bapa(kah)?\b.*\b(boleh|harus|wajib|dilarang)\b|\bbolehkah\b|\bharuskah\b", re.I)

def _complete_day_rules(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A day question must give both halves of dewasa ngaben: an answer without the wuku/
    wewaran days, or without the sasih, gets the definition's own sentence about the missing
    half. With rule 22 in the prompt, "hari apa yang harus dihindari untuk ngaben" still came
    back with only the sasih, and "hari baik apa saja" with only the days (Tier B 2026-10-01;
    T15/T16/T20/T96)."""
    definition = get_content().best_definition("dewasa_ngaben") or ""
    sentences = re.split(r"(?<=[.!?])\s+", definition)
    for key in ("sasih", "wuku"):
        if re.search(rf"\b{key}\b", answer, re.I):
            continue
        add = next((s for s in sentences if re.search(rf"\b{key}\b", s, re.I)), None)
        if add:
            answer = answer.rstrip() + " " + add
    return answer.strip()


# "hanya itu sarananya?" -> "Tidak, hanya itu saranannya." (T44)
_ONLY_THAT_Q_RE = re.compile(r"\bhanya itu\b|\bitu saja\b|\bcuma itu\b", re.I)


_PROHIBITION_RE = re.compile(r"\btidak boleh\b|\bdilarang\b|\blarangan\b|\bpantang\b|\btidak diperkenankan\b", re.I)


def _fix_unstated_prohibition(answer: Text, context_text: Text) -> Text:
    """A whether-question ("apakah masyarakat umum boleh memakai bade?"): a bare verdict
    line ("tidak boleh" alone, then the text) is cut, and when nothing in the context states a
    prohibition, so is every sentence claiming one -- the definition only says who usually
    uses the bade (T41/T73, Tier B 2026-10-01). "tidak ada larangan" is not a claim."""
    answer = re.sub(r"^\s*(?:tidak boleh|boleh|tidak|ya)\s*[.!]?\s*\n\s*\n", "", answer, count=1)
    answer = answer[:1].upper() + answer[1:]
    if _PROHIBITION_RE.search(context_text) or re.search(r"\bdihindari\b", context_text, re.I):
        return answer
    parts = re.findall(r"[^.!?\n]+[.!?]*", answer)
    drop = [s for s in parts if _PROHIBITION_RE.search(s)
            and not re.search(r"\btidak ada (?:larangan|aturan)|\bbukan larangan|\btidak (?:tercatat|disebutkan)", s, re.I)]
    if not drop or len(drop) == len([s for s in parts if s.strip()]):
        return answer
    for s in drop:
        answer = answer.replace(s, "", 1)
    return re.sub(r"[ \t]{2,}", " ", answer).strip()


# a sentence saying who usually uses the term ("Bade dan lembu lazimnya dipakai golongan
# berkasta lebih tinggi.") and any rule a sentence may state instead
_USAGE_NORM_RE = re.compile(r"\b(?:lazim(?:nya)?|biasanya|umumnya)\b[^.]*\b(?:dipakai|memakai|digunakan|menggunakan)\b"
                            r"|\b(?:dipakai|memakai|digunakan|menggunakan)\b[^.]*\b(?:lazim(?:nya)?|biasanya|umumnya)\b",
                            re.I)
_RULE_STATED_RE = re.compile(r"\bboleh\b|\bdilarang\b|\blarangan\b|\bpantang\b|\bdiperkenankan\b|\bdihindari\b"
                             r"|\bwajib\b|\bharus\b|\bhanya\b", re.I)


_SURFACES: Dict[bool, tuple] = {}


def _named_terms(text: Text, everyday: bool = False) -> List[str]:
    """Ids of the KB terms a text names as written (names, aliases, force_merge surfaces), in
    order of first mention. Everyday words that are also names ("air", "kain", "wadah") are
    skipped unless `everyday`: named in passing, they are rarely the terms a reader needs
    explained."""
    if everyday not in _SURFACES:
        r = get_resolver()
        table = {k: v for k, v in list(r.surface.items()) + list(r.force_merge.items())
                 if len(k) >= 4 and (everyday or " " in k or k not in r.common_words)}
        pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(table, key=len, reverse=True))
                             + r")\b", re.I)
        _SURFACES[everyday] = (pattern, table)
    pattern, table = _SURFACES[everyday]
    out: List[str] = []
    for m in pattern.finditer(text or ""):
        _id = table.get(m.group(1).lower())
        if _id and _id not in out:
            out.append(_id)
    return out


def _sentences(text: Optional[Text]) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s]


_USE_VERB_RE = re.compile(r"\b(?:memakai|menggunakan|dipakai|digunakan|pakai|gunakan)\b", re.I)


def _used_term(user_msg: Text, enriched: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The term a usage question is about: the first one named after the verb -- "apakah
    wangsa sudra boleh menggunakan bade tingkat 11?" asks about bade, and was answered with
    the sudra's cremation-vessel norm (conersation.md 2026-10-02) -- else the first term."""
    m = _USE_VERB_RE.search(user_msg)
    if m:
        after = user_msg.lower()[m.end():]
        hits = []
        for e in enriched:
            pos = [after.find(n.lower()) for n in [e["name"]] + list(e.get("aliases") or [])]
            pos = [p for p in pos if p >= 0]
            if pos:
                hits.append((min(pos), enriched.index(e), e))
        if hits:
            return min(hits, key=lambda h: h[:2])[2]
    return enriched[0]


def _usage_norm_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """"apakah masyarakat umum boleh memakai bade?" when the term's definition and facts state no
    rule, only who lazimnya uses it: no rule is recorded, then those sentences as written. Rule
    24 asks the model for exactly this, but it merged the two sentences of bade's definition into
    "... golongan berkasta lebih tinggi, termasuk warga ... yang tidak berkasta" (Tier B
    2026-10-02). None when a rule is stated or no such sentence exists (the model answers).
    The user wanted it explained, not only stated (conersation.md 2026-10-02): the definition's
    sentences sharing a word with the question follow ("tingkat" -> the tiers by rank), then the
    other terms' norm sentences, then what the other thing used is ("Wadah adalah ...") and a
    term that explanation names ("Badawang nala adalah ...")."""
    if not enriched or not _PERMISSION_Q_RE.search(user_msg):
        return None
    e = _used_term(user_msg, enriched)
    definition = e.get("definition") or ""
    stated = " ".join([definition] + [r.get("statement") or "" for r in e.get("relationships") or []]
                      + (e.get("aspect_facts") or []))
    if _RULE_STATED_RE.search(stated):
        return None
    norms = [s for s in _sentences(definition) if _USAGE_NORM_RE.search(s)]
    if not norms:
        return None
    asked = {w for w in _content_words(user_msg) if w not in _content_words(e["name"])}
    out = list(norms)
    out += [s for s in _sentences(definition)
            if s not in out and any(_grounded(w, _content_words(s)) for w in asked)]
    for other in enriched:
        if other is not e:
            out += [s for s in _sentences(other.get("definition")) if _USAGE_NORM_RE.search(s) and s not in out]
    # what the other group uses: the subject of a norm sentence that is not the asked term
    # ("Wadah, yaitu ..., lazimnya dipakai oleh warga ..."), then one term its explanation names
    content, shown = get_content(), {x["id"] for x in enriched}
    shown |= set(_named_terms(user_msg, everyday=True))
    for s in norms:
        subject = next(iter(_named_terms(s, everyday=True)), None)
        if subject is None or subject in shown:
            continue
        gloss = _first_sentence(content.best_definition(subject), limit=400)
        if not gloss:
            continue
        out.append(gloss)
        shown.add(subject)
        # a two-word name before a generic word ("badawang nala" before "usungan")
        subs = [t for t in _named_terms(gloss) if t not in shown]
        sub = next((t for t in subs if " " in content.entity_name.get(t, "")), subs[0] if subs else None)
        sub_gloss = _first_sentence(content.best_definition(sub), limit=400) if sub else None
        if sub_gloss:
            out.append(sub_gloss)
            shown.add(sub)
    rule = "kewajiban" if re.search(r"\b(?:harus|wajib)\b", user_msg, re.I) else "larangan"
    return f"Tidak ada {rule} yang tercatat; yang tercatat hanya kebiasaannya. " + " ".join(out)


def _stated_rule_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A whether-question whose term's definition states the rule for the asked act: that
    sentence first, then the definition's other sentences sharing a question word, as written.
    "apakah bayi yang giginya belum tanggal boleh dibakar?" -- jenazah bayi's definition says
    "hanya anak berusia lima bulan ke atas yang boleh ... dibakar" and gives the age tiers, yet
    the model answered "tidak perlu atau boleh dibakar" from the youngest tiers (Tier B
    2026-10-02). None when no sentence states a rule about a word of the question."""
    if not enriched or not _PERMISSION_Q_RE.search(user_msg):
        return None
    e = _used_term(user_msg, enriched)
    name_words = _content_words(" ".join([e["name"]] + list(e.get("aliases") or [])))
    asked = {w for w in _content_words(user_msg)
             if w not in name_words and not _RULE_STATED_RE.search(w)}
    if not asked:
        return None
    sentences = _sentences(e.get("definition"))

    def shares(s: str) -> bool:
        return any(_grounded(w, _content_words(s)) for w in asked)
    rules = [s for s in sentences if _RULE_STATED_RE.search(s) and shares(s)]
    if not rules:
        return None
    return " ".join(rules + [s for s in sentences if s not in rules and shares(s)])


def _case_compare_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A comparison inside one term -- two cases its definition tells apart: the definition's
    sentences sharing a word of the question, as written. "apakah ada perbedaan prosesi untuk bayi
    yang giginya sudah tanggal dan belum?" got the age tiers swapped ("yang giginya sudah tanggal
    ... diupacarai dengan upacara Ngelungah") on two Ollama loads, the definition split into one
    sentence per tier or not (Tier B 2026-10-05). None unless one term and 2+ such sentences."""
    if len(enriched) != 1 or not _COMPARE_Q_RE.search(user_msg):
        return None
    e = enriched[0]
    name_words = _content_words(" ".join([e["name"]] + list(e.get("aliases") or [])))
    asked = {w for w in _content_words(user_msg)
             if w not in name_words and not _COMPARE_Q_RE.search(w) and w not in {"prosesi", "upacara"}}
    picked = [s for s in _sentences(e.get("definition"))
              if any(_grounded(w, _content_words(s)) for w in asked)]
    if len(picked) < 2:
        return None
    return f"Yang tercatat tentang {e['name']}: " + " ".join(picked)


# order edges: +1 when the subject comes first ("X diikuti oleh Y"), -1 when it comes after
_ORDER_SIGN = {"DIIKUTI_OLEH": 1, "DILAKUKAN_SEBELUM": 1, "SEBELUM": 1, "DILAKUKAN_MENJELANG": 1,
               "MENJELANG": 1, "DIPERCIKKAN_SEBELUM": 1, "DIGUNAKAN_SEBELUM": 1,
               "DILAKUKAN_SETELAH": -1, "DILAKSANAKAN_SETELAH": -1, "SETELAH": -1}
_ORDER_Q_RE = re.compile(r"\b(?:sebelum|sesudah|setelah)\b", re.I)


def _order_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """"apakah itu dilakukan sebelum atau sesudah nyiramang layon?" after a turn about
    pangringkes, answered from the order facts and stage numbers without the model: it read
    "nyiramang layon diikuti oleh pangringkes" backwards ("Nyiramang layon dilakukan sesudah
    pangringkes", conersation.md 2026-10-02). None when nothing orders the first two terms."""
    if len(enriched) < 2 or not _ORDER_Q_RE.search(user_msg) or not (
            "?" in user_msg or re.search(r"\b(?:apakah|kapan|mana)\b", user_msg, re.I)):
        return None
    a, b = enriched[0], enriched[1]
    signs, facts = set(), []
    for r in a.get("relationships") or []:
        sign = _ORDER_SIGN.get(r.get("relation"))
        if sign and r.get("target_id") == b["id"]:
            signs.add(sign if r.get("outgoing") else -sign)
            facts.append(r.get("statement") or "")
    na, nb = _stage_number(a.get("definition")), _stage_number(b.get("definition"))
    if not signs and na and nb and na != nb:
        signs.add(1 if na < nb else -1)
    if len(signs) != 1:
        return None
    first = signs.pop() > 0
    name_a, name_b = a["name"][:1].upper() + a["name"][1:], b["name"]
    out = [f"{name_a} dilakukan {'sebelum' if first else 'sesudah'} {name_b}."]
    out += [f[:1].upper() + f[1:].rstrip(".") + "." for f in facts if f]
    # definition sentences that order things: the first term's own ("... dilaksanakan setelah
    # Pabersihan Mati selesai"), and the other's that name the first ("Urutannya: ..., ngeringkes,
    # lalu ...")
    order_word = re.compile(r"\b(?:urutan(?:nya)?|setelah|sesudah|sebelum|menjelang|lalu|kemudian|diikuti)\b", re.I)
    for x, y, need_name in ((a, b, False), (b, a, True)):
        for s in _sentences(x.get("definition")):
            if order_word.search(s) and (not need_name or y["id"] in _named_terms(s)) and s not in out:
                out.append(re.sub(r"^Urutannya:", f"Urutan {x['name']}:", s))
                break
    return " ".join(out)


def _fix_only_that(answer: Text, user_msg: Text) -> Text:
    if not _ONLY_THAT_Q_RE.search(user_msg):
        return answer
    return re.sub(r"^\s*Tidak,\s*hanya itu\b", "Ya, yang tercatat hanya itu", answer, count=1, flags=re.I)


# A named set -- Panca Yadnya, Tri Loka, Tri Sarira, Panca Maha Bhuta, ... -- is
# only explained when all its members are named. The small model sometimes names
# one member and drifts to it (panca yadnya -> only pitra yadnya), so the member
# list is completed deterministically from the graph when the answer misses some.
_NUMERAL_SET_RE = re.compile(r"^(eka|dwi|tri|catur|panca|sad|sapta|asta|nawa|dasa)[ -]?\w", re.I)
_NUMERAL_VALUE = {"eka": 1, "dwi": 2, "tri": 3, "catur": 4, "panca": 5, "sad": 6, "sapta": 7, "asta": 8,
                  "nawa": 9, "dasa": 10}


def _set_members(e: Dict[str, Any]) -> List[str]:
    out = []
    for r in e.get("relationships") or []:
        rel, outgoing = r.get("relation"), bool(r.get("outgoing"))
        if (rel in ("TERMASUK_JENIS", "BAGIAN_DARI") and not outgoing) or \
                (rel in ("TERDIRI_DARI", "BERUPA", "BERUNSUR") and outgoing):
            if r.get("target") and r["target"] not in out:
                out.append(r["target"])
    return out


def _complete_sarana_lists(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A "sarana" answer must name the items of each group (the term itself, each stage).
    Once the stages' tetandingan banten were in the KB (2026-09-30), "apa saja sarana upacara
    yang digunakan untuk ngaben" came back with only the stage NAMES under "sarana yang
    digunakan pada beberapa tahap". Every group whose items the answer mostly left out is
    added as its fact sentence."""
    said = _ortho_key(answer)
    for e in enriched:
        for fact in e.get("sarana_facts") or []:
            items = [x.strip() for x in fact.split(":", 1)[-1].split(",") if x.strip()]
            named = sum(_ortho_key(x) in said for x in items)
            # a stage group the answer never names, though its banten are named under other
            # stages: "sarana ngaben" left out sangaskara (Tier B 2026-10-02)
            stage = re.match(r"Sarana yang digunakan dalam (.+?)(?: \(| itu sendiri|:)", fact)
            unnamed = bool(stage) and _ortho_key(stage.group(1)) not in said
            if items and (named * 2 < len(items) or unnamed):
                answer = answer.rstrip() + f"\n{fact}."
    return answer


# a reason, not an order: "... sering digelar pada hari ke-12 setelah pangabenan" (ngroras's
# etymology) is no link between ngaben and atma wedana
# offered / directed TO the term (incoming), and the verbs that would make the term the giver
_OFFERED_TO = frozenset({"DIPERSEMBAHKAN_KEPADA", "DIHATURKAN_KEPADA", "DITUJUKAN_UNTUK", "DIBERIKAN_KEPADA",
                         "DIAYABKAN_KEPADA"})
_GIVING_RE = re.compile(r"\b(?:memberikan|memberi|menyampaikan|mempersembahkan|menghaturkan|menyerahkan)\b", re.I)


def _drop_reversed_offerings(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A sentence or list item making the term the giver of what is offered TO it goes: with
    "punia dipersembahkan kepada sulinggih" and "santapan istimewa dipersembahkan kepada
    sulinggih" in context, "apa itu sulinggih" listed "Memberikan persembahan punia dan santapan
    istimewa" among its roles on one load in four (Tier B 2026-10-05, after pandita was merged into
    sulinggih). One that names the term as the receiver ("kepada sulinggih") stays. Never leaves
    nothing."""
    out = answer
    for e in enriched:
        rels = e.get("relationships") or []
        given = {(r.get("target") or "").lower() for r in rels
                 if r.get("relation") in _OFFERED_TO and not r.get("outgoing") and r.get("target")}
        gives = {(r.get("target") or "").lower() for r in rels if r.get("outgoing") and r.get("target")}
        given -= gives
        if not given:
            continue
        names = [e["name"]] + list(e.get("aliases") or [])
        to_term = re.compile(r"\b(?:kepada|untuk|bagi)\s+(?:sang\s+|para\s+)?(?:" +
                             "|".join(re.escape(n) for n in names) + r")\b", re.I)
        for part in re.findall(r"[^.!?\n]+[.!?]*", out):
            if not _GIVING_RE.search(part) or to_term.search(part):
                continue
            if any(re.search(rf"\b{re.escape(g)}\b", part, re.I) for g in given):
                candidate = out.replace(part, "", 1)
                if candidate.strip():
                    out = candidate
    if out == answer:
        return answer
    # the removed list items leave empty lines behind
    out = re.sub(r"(?m)^[ \t]*[-*•]?[ \t]*$\n?", "", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _ensure_definition_lead(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A plain "apa itu X" answer that leaves out most of X's first definition sentence gets that
    sentence in front. "apa itu pitra yadnya" opened with the definition's third sentence ("adalah
    upacara keagamaan ...") on three fresh Ollama loads, dropping the general meaning the user wants
    first ("pengorbanan ... kepada leluhur", conersation.md 2026-10-02; Tier B 2026-10-05)."""
    if not enriched:
        return answer
    lead = _first_sentence(enriched[0].get("definition"), limit=500)
    words = _content_words(lead)
    if len(words) < 4:
        return answer
    # under 40%: pitra yadnya's answer had 17% of the lead; "apa itu lingga sarira" (50%) said
    # "badan halus" and only left out "alam pikiran, perasaan ...", which is no missing lead
    said = _content_words(answer)
    if sum(_grounded(w, said) for w in words) >= 0.4 * len(words):
        return answer
    return f"{lead} {answer}"


_DEPENDENCY_RE = re.compile(r"\b(?:karena|sebab|sehingga)\b", re.I)


# "kenapa tidak boleh / dihindari / dilarang ..." asks why something is avoided
_WHY_AVOID_Q_RE = re.compile(r"\b(?:tidak|nggak|ga|gak)\s+(?:boleh|bisa|dianjurkan)\b|\bdihindari\b|\bdilarang\b"
                             r"|\bpantang\b|\bjangan\b", re.I)
# a definition sentence judging its term -- the stated reason it is avoided ("dihindari" alone only
# repeats that it is)
_JUDGEMENT_RE = re.compile(r"\btidak baik\b|\bburuk\b|\bkotor\b|\balaning\b|\bdilarang\b|\btidak boleh\b"
                           r"|\btidak dianjurkan\b|\btidak diperkenankan\b|\bmencemari\b|\bsasih mati\b"
                           r"|\btanpa amer?tha\b|\bpantang\b", re.I)


def _complete_stated_reasons(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text) -> Text:
    """A why-avoided question gets, for each term it names, the first definition sentence that
    judges the term when the answer left most of it out. "kenapa tidak boleh melakukan yadnya pada
    sasih paruwak tahuk dan malamasa?" was answered "dianggap tidak baik atau kotor" without
    malamasa's "Kata mala berarti tidak baik ..." or paruwak tahuk's Lontar Aji Swamandala sentence,
    although asked about paruwak tahuk alone it cited the lontar (user, 2026-10-05). One sentence per
    term: the next one on paruwak tahuk is the caru remedy, which no source ties to Ngaben."""
    said, asked = _content_words(answer), _ortho_key(user_msg)
    # only what the sentence adds to the question counts: "dianggap tidak baik atau kotor" shared
    # "malamasa", "sasih", "yadnya" with malamasa's reason sentence and passed as covering it,
    # without "mala berarti tidak baik" or "sasih kotor" (Tier B 2026-10-05)
    question_words = _content_words(user_msg)
    for e in enriched:
        names = [e["name"]] + list(e.get("aliases") or [])
        if not any(len(n) >= 4 and _ortho_key(n) in asked for n in names):
            continue
        for s in _sentences(e.get("definition")):
            if not _JUDGEMENT_RE.search(s):
                continue
            words = _content_words(s) - question_words - _content_words(" ".join(names))
            if words and sum(_grounded(w, said) for w in words) < 0.6 * len(words):
                answer = answer.rstrip() + "\n\n" + s
                said |= words
            break
    return answer


def _complete_stated_link(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A comparison or relation question about two terms gets each definition sentence that
    names the other term with a reason or order ("Ngaben memisahkan jiwa ... tetapi jiwanya masih
    berbadan halus ...; karena itulah Atma Wedana diselenggarakan setelah Ngaben") when the answer
    left most of it out. Rule 17 asks for that dependency, yet "apa perbedaan ngaben dan atma
    wedana" gave two separate definitions on most loads (Tier B 2026-10-02/05)."""
    said = _content_words(answer)
    for e in enriched:
        others = [o for o in enriched if o is not e]
        names = [n for o in others for n in [o["name"]] + list(o.get("aliases") or []) if len(n) >= 4]
        if not names:
            continue
        named = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b", re.I)
        for s in _sentences(e.get("definition")):
            words = _content_words(s)
            if (named.search(s) and _DEPENDENCY_RE.search(s) and words
                    and sum(_grounded(w, said) for w in words) < 0.6 * len(words)):
                answer = answer.rstrip() + "\n\n" + s
                said |= words
    return answer


# How each composition predicate reads in the breakdown, whole first ("bade: terbuat dari
# kayu, bambu"). PART_IS_SUBJECT predicates are read from the whole's side too.
_COMPOSITION_PHRASE = {
    "TERBUAT_DARI": "terbuat dari", "TERDIRI_DARI": "terdiri dari", "BERISI": "berisi",
    "DIISI": "diisi", "DIISI_DENGAN": "diisi", "DIMASUKKAN_KE_DALAM": "diisi",
    "DILENGKAPI": "dilengkapi", "DILENGKAPKAN_PADA": "dilengkapi", "BERUPA": "berupa",
    "MELIPUTI": "meliputi", "BERUNSUR": "berunsur", "MENGANDUNG": "mengandung",
    "DIBUNGKUS_DENGAN": "dibungkus", "DIALASI_DENGAN": "dialasi", "DIIKAT_DENGAN": "diikat dengan",
    "DISISIPI": "disisipi", "DIPASANG": "dipasangi", "DISAMBUNG_DENGAN": "disambung dengan",
    "DIHIAS_DENGAN": "dihias dengan", "BERKERANGKA": "berkerangka",
    "BAGIAN_DARI": "bagian-bagiannya", "DIPERLUKAN_UNTUK_MEMBUAT": "pembuatannya memerlukan",
}
_COMPOSITION_MAX_LINES = 12


def _composition_q(user_msg: Text) -> bool:
    return bool(_COMPOSITION_Q_RE.search(user_msg) and not _KINDS_Q_RE.search(user_msg))


def _short_source(source: Optional[Text]) -> Text:
    """"https://www.detik.com/bali/..." -> "detik.com"; a corpus citation stays as written."""
    m = re.match(r"https?://(?:www\.)?([^/]+)", source or "")
    return m.group(1) if m else (source or "").strip()


def _composition_breakdown(entity_id: Text) -> Text:
    """The layered "made of" breakdown of a sarana / tirtha / building, built from the KB in
    code: one line per composite item (breadth-first, main version), then the regional
    variants with their source. Empty when the item has no recorded parts."""
    content = get_content()
    tree = content.composition_tree(entity_id)
    if not tree["parts"]:
        return ""
    lines, variants, leaves, cut = [], [], [], False
    queue = [tree]
    while queue:
        node = queue.pop(0)
        groups: Dict[str, List[str]] = {}
        for p in node["parts"]:
            child = p["node"]
            v = p.get("variant")
            if v:
                # "variasi (di X): ..." -> "di X: ..." under the "Variasi" heading
                line = re.sub(r"^variasi \((.*?)\):\s*", r"\1: ",
                              content.render_variant(p["predicate"], node["name"], child["name"], v))
                variants.append(line + (f" (sumber: {_short_source(v.get('source'))})" if v.get("source") else ""))
                continue
            phrase = _COMPOSITION_PHRASE.get(p["predicate"], p["predicate"].lower().replace("_", " "))
            groups.setdefault(phrase, []).append(child["name"])
            if child["parts"]:
                queue.append(child)
            elif child["raw"] and child["name"] not in leaves:
                leaves.append(child["name"])
            cut = cut or child["cut"]
        if not groups:
            continue
        if len(lines) == _COMPOSITION_MAX_LINES:
            cut = True
            break
        body = "; ".join(f"{ph} {', '.join(items)}" for ph, items in groups.items())
        kind = f" (sebagai jenis {node['inherited_from']})" if node.get("inherited_from") else ""
        lines.append(f"- {node['name'][:1].upper()}{node['name'][1:]}{kind}: {body}.")
    if not lines and not variants:
        return ""
    out = ["Rincian bahan menurut basis data:"] + lines
    if leaves:
        out.append(f"Bahan dasarnya antara lain: {', '.join(leaves)}.")
    if variants:
        out.append("Variasi (daerah atau pilihan lain):")
        out += [f"- {v[:1].upper()}{v[1:]}." for v in variants]
    if cut:
        out.append("(Rincian dipotong; tanyakan bagian tertentu untuk detailnya.)")
    return "\n".join(out)


def _complete_composition(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """"X terbuat dari apa": the 7B model drops or mixes up levels of a deep breakdown
    (tirta pangentas -> pripih emas -> daun dapdap), so the breakdown is appended from the KB
    unless the answer already names every item in it."""
    if not enriched:
        return answer
    breakdown = _composition_breakdown(enriched[0]["id"])
    if not breakdown:
        return answer
    said = _ortho_key(answer)
    items = [x.strip() for line in breakdown.splitlines()[1:] if ":" in line
             for x in re.split(r"[,;]", line.split(":", 1)[1].rstrip(".")) if x.strip()]
    items = [re.sub(r"^(?:" + "|".join(sorted(set(_COMPOSITION_PHRASE.values()), key=len, reverse=True))
                    + r")\s+", "", x) for x in items]
    if items and all(_ortho_key(x) in said for x in items) and "Variasi (" not in breakdown:
        return answer
    return answer.rstrip() + "\n" + breakdown


def _raw_material_answer(enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A raw material ("beras terbuat dari apa") is a leaf: it is not made of other sarana."""
    if not enriched or not get_content().is_raw(enriched[0]["id"]):
        return None
    e = enriched[0]
    name = f"{e['name'][:1].upper()}{e['name'][1:]}"
    known = _first_sentence(e.get("definition"))
    return f"{name} adalah bahan dasar; tidak tersusun dari sarana lain." + (f" {known}" if known else "")


def _add_literal_meaning(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A word-meaning question must give the literal meaning when the KB records one
    (BERARTI_HARFIAH). With it in context, the model still left it out on some runs of the
    same prompt -- "apa arti kata ngulapin" passed once and failed once without
    "melambaikan tangan" (Ollama is not fully deterministic at temperature 0, 2026-09-30).
    Only the quoted phrase is compared and added."""
    attrs = get_content().attributes
    for e in enriched[:1]:
        for value in attrs.get(e["id"], {}).get("BERARTI_HARFIAH", []):
            m = re.match(r'\s*"([^"]+)"', value)
            literal = m.group(1) if m else None
            if literal and literal.lower() not in answer.lower():
                answer = (answer.rstrip() + f' Secara harfiah, {e["name"]} berarti "{literal}".').strip()
    return answer


def _complete_set_members(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    # only for the set the question is about (the first resolved term), and
    # spelling-insensitive ("antahkarana" == "antah karana")
    m = _NUMERAL_SET_RE.match(enriched[0].get("name") or "") if enriched else None
    if not m:
        return answer
    e = enriched[0]
    members = _set_members(e)
    said = _ortho_key(answer)
    # more members than the numeral: the corpus gives two versions of the set (panca datu's
    # fifth metal is mirah or logam campuran) and the definition explains which -- a flat
    # "terdiri dari" list of six for "panca" would contradict it (lint waiver panca_datu>5)
    if len(members) > _NUMERAL_VALUE[m.group(1).lower()]:
        return answer
    if len(members) >= 2 and any(_ortho_key(x) not in said for x in members):
        answer = answer.rstrip() + f" {e['name'][:1].upper()}{e['name'][1:]} terdiri dari: {', '.join(members)}."
    return answer


def _link_targets(enriched: List[Dict[str, Any]]) -> set:
    """For "hubungan X dengan Y": the ids whose edges link the asked terms -- the terms
    themselves when any edge joins two of them, else the nodes they are all linked to."""
    ids = {e["id"] for e in enriched}
    targets = [{r.get("target_id") for r in e.get("relationships") or []} - {None} for e in enriched]
    if any(t & (ids - {e["id"]}) for e, t in zip(enriched, targets)):
        return ids
    return set.intersection(*targets) if targets else set()


def _link_filter(enriched: List[Dict[str, Any]]) -> Optional[set]:
    """_link_targets, or None (no filtering) when nothing links the terms: with only
    their definitions left, "hubungan tirtha dan pitra yadnya" became "tidak ada
    hubungan langsung" (2026-09-25), though tirtha's kinds are used in every Ngaben."""
    keep = _link_targets(enriched)
    return keep or None


# References to the prompt itself ("Jenis-jenis ngaben yang terdapat dalam konteks
# tersebut adalah", "seperti yang tercantum dalam konteks"). Rule 6 forbids them, but
# the 7B model keeps writing them (Tier B 2026-09-25), so they are cut from the answer.
_CONTEXT_WORD = r"(?:dalam|di)\s+konteks(?:\s+(?:tersebut|ini|di atas|yang diberikan|yang tersedia))?"
_META_PHRASE_RE = re.compile(
    r",?\s*(?:seperti|sebagaimana)\s+(?:yang\s+)?(?:tercantum|disebutkan|dijelaskan|tertulis|terdapat)\s+"
    + _CONTEXT_WORD +
    # ", seperti yang disebutkan dalam definisi malamasa." (Tier B 2026-10-01)
    r"|,?\s*(?:seperti|sebagaimana)\s+(?:yang\s+)?(?:tercantum|disebutkan|dijelaskan|tertulis|terdapat)\s+"
    r"(?:dalam|di)\s+(?:definisi|informasi|data|fakta)(?:\s+[\w-]+){0,3}?(?=\s*[.,!?]|\s*$)"
    r"|\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)\s+" + _CONTEXT_WORD +
    # "... yang disebutkan dalam definisi dan hubungan yang diberikan"
    r"|\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)\s+(?:dalam|di)\s+"
    r"(?:definisi|informasi|data|fakta)(?:\s+dan\s+(?:hubungan|fakta|definisi))?\s+yang\s+(?:diberikan|tersedia)" +
    # "..., karena berdasarkan definisi dewasa ngaben, keduanya ..." (Tier B 2026-10-01)
    r"|\b(?:berdasarkan|menurut)\s+definisi(?:\s+[\w-]+){0,3}?\s*,\s*"
    # "Menurut definisi dan hubungan yang diberikan, ..." (Tier B 2026-10-01)
    r"|\b(?:berdasarkan|menurut)\s+(?:informasi|konteks|data|fakta|definisi)"
    r"(?:\s+dan\s+(?:hubungan|fakta|definisi|informasi))?(?:\s+yang\s+(?:diberikan|tersedia|ada|tercatat))?"
    r"(?:\s+(?:tersebut|ini|di atas))?\s*,\s*"
    # "..., berdasarkan informasi yang tercatat dalam konteks tersebut." (2026-09-29);
    # "..., sesuai dengan informasi yang tercatat dalam konteks tersebut." (2026-10-01)
    r"|,?\s*(?:berdasarkan|menurut|sesuai dengan)\s+(?:informasi|konteks|data|fakta)"
    r"(?:\s+yang\s+(?:diberikan|tersedia|ada|tercatat))?"
    r"(?:\s+(?:dalam|di)\s+konteks)?(?:\s+(?:tersebut|ini|di atas))?(?=\s*[.!?]|\s*$)"
    r"|\bdalam\s+konteks\s+(?:tersebut|ini|di atas|yang diberikan)\s*,\s*",
    re.I)
# A sentence still about the prompt after those cuts goes whole: "Perlu dicatat bahwa daftar
# lengkap bahan-bahan ... tidak disebutkan secara detail dalam konteks ini." above a complete
# breakdown, "... bahan-bahan lainnya yang disebutkan dalam fakta-fakta tersebut." (Tier B
# 2026-10-02). KB text says "dalam konteks Ngaben/upacara", never "konteks ini" or "fakta tersebut",
# and never "dalam definisi" / "dalam fakta": "... sudah disebutkan dalam definisi tirta pangentas.
# Namun, bahan-bahan lain yang disebutkan dalam fakta-fakta tidak disebutkan ..." (same day).
_PROMPT_REF_RE = re.compile(
    # "..., tetapi berdasarkan informasi yang diberikan:" before a list (Tier B 2026-10-02)
    r"\b(?:informasi|data)\s+yang\s+(?:diberikan|tersedia)\b|"
    r"\bkonteks\s+(?:ini|tersebut|di atas|yang\s+(?:diberikan|tersedia))\b"
    r"|\bfakta(?:-fakta)?\s+(?:ini|tersebut|di atas|yang\s+(?:diberikan|tersedia))\b"
    r"|\b(?:dalam|di)\s+(?:definisi|fakta(?:-fakta)?)\b|\bdefinisi\s+(?:ini|tersebut)\b", re.I)


def _strip_meta_phrases(answer: Text) -> Text:
    # until nothing changes: "berdasarkan fakta yang terdapat dalam konteks, ..." lost only its
    # inner "yang terdapat dalam konteks" and kept "Berdasarkan fakta," (Tier B 2026-10-05)
    out, prev = answer, None
    while out != prev:
        prev, out = out, _META_PHRASE_RE.sub("", out)
    # a cut that took a negated predicate leaves its "tidak": "Alasan spesifik mengapa ... dihindari
    # dalam Ngaben tidak disebutkan dalam definisi yang diberikan." -> "... dalam Ngaben tidak."
    # (Tier B 2026-10-05); that sentence goes whole
    for s in re.findall(r"[^.!?\n]+[.!?]*", out):
        if re.search(r"\b(?:tidak|belum)\s*[.!?]*\s*$", s) and s.strip() not in answer:
            out = out.replace(s, "", 1)
    parts = re.findall(r"[^.!?\n]+[.!?]*", out)
    about_prompt = [s for s in parts if _PROMPT_REF_RE.search(s)]
    if about_prompt and len(about_prompt) < len([s for s in parts if s.strip()]):
        for s in about_prompt:
            out = out.replace(s, "", 1)
        out = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", out).strip()
    if out == answer:
        return answer
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"[ \t]+([.,:;])", r"\1", out)
    # a sentence that began with the cut phrase starts with a capital again
    return re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)


def _llm_context(enriched: List[Dict[str, Any]], with_relationships: bool = True,
                 only_predicates: Optional[set] = None,
                 keep_to: Optional[set] = None,
                 contents_only: bool = False,
                 part_definitions: bool = True,
                 keep_children: Optional[set] = None,
                 meaning_words: Optional[set] = None) -> List[Dict[str, Any]]:
    """What the synthesis LLM sees: each term's definition plus its graph edges
    as directed sentences. Raw ids, labels and predicate names stay out -- they
    leaked into answers as "BAGIAN_DARI"/"upacara_palebon_ngaben"-style tokens and
    let the model guess edge direction. `e["facts"]` (facts.jsonl) are the same edges
    as the relationships, so they are not repeated. `aspect_facts` are the text-only
    attributes of the asked aspect (set by _synthesize); when an entity has any edge
    or attribute of that aspect, its other edges are dropped. `keep_to` (a relation
    question about 2+ terms, from _link_filter) keeps only the edges to those ids.
    `contents_only` (a "what does X contain / what is it made of" question) keeps only the
    composition edges in which the term is the whole, and none of its kinds.
    `part_definitions=False` leaves out the other terms' definitions: a part's definition
    tells where else it is used, and the model wrote that as its role in the whole.
    `keep_children` (ids) keeps those terms' type / member / stage edges through the aspect
    filter too (a purpose question about a class). `meaning_words` (a why / makna question's
    own words) keeps a child whose definition states a meaning and shares one of them."""
    out = []
    for e in enriched:
        rels = []
        rs = (e.get("relationships") or []) if with_relationships else []
        aspect_facts = e.get("aspect_facts") or []
        # sarana_facts / source_facts answer the aspect too: without them counted, "lontar apa
        # yang menjelaskan ngaben" kept all of ngaben's 60 edges beside its sources
        if only_predicates and (aspect_facts or e.get("sarana_facts") or e.get("source_facts")
                                or any(r.get("relation") in only_predicates for r in rs)):
            # a child whose definition states a meaning or reason answers a why / makna question
            # too: "kenapa harus 11?" about bade is in tingkatan bade's definition ("tumpang
            # sebelas menggambarkan ..."), which the filter dropped with the part edge (2026-10-02)
            # -- when that definition shares a word or number with the question
            def answers_meaning(r: Dict[str, Any]) -> bool:
                d = r.get("target_definition") or ""
                return bool(meaning_words and _MEANING_IN_DEF_RE.search(d)
                            and any(_grounded(w, _content_words(d)) for w in meaning_words))
            rs = [r for r in rs if r.get("relation") in only_predicates
                  or (keep_children and e["id"] in keep_children and r.get("target_definition"))
                  or answers_meaning(r)]
        if contents_only:
            rs = [r for r in rs if r.get("relation") not in _KIND_PREDICATES and (
                r.get("relation") not in PREDICATE_FAMILIES["komposisi"]
                or bool(r.get("outgoing")) != (r.get("relation") in PART_IS_SUBJECT))]
        if keep_to is not None:
            rs = [r for r in rs if r.get("target_id") in keep_to and r.get("target_id") != e["id"]]
        if e.get("sarana_facts"):
            # already listed, grouped per stage, in sarana_facts
            rs = [r for r in rs if r.get("relation") not in _SARANA_USE_IN + _SARANA_USE_OUT]
        n_child_defs = 0
        for r in rs:
            item = {"fact": r.get("statement") or f"{e['name']} -- {r.get('target')}"}
            # capped so a hub's plain "apa itu X" prompt stays short (CPU-bound Ollama)
            if part_definitions and r.get("target_definition") and n_child_defs < _CHILD_DEF_CAP:
                item["target_definition"] = f"{r['target']}: {r['target_definition']}"
                n_child_defs += 1
            rels.append(item)
        # first: _fit_context trims from the end
        rels = [{"fact": f} for f in (e.get("sarana_facts") or []) + (e.get("source_facts") or [])] + rels
        item = {"term": e["name"], "definition": e["definition"], "relationships": rels}
        if aspect_facts:
            item["facts"] = aspect_facts
        if e.get("aliases"):
            item["also_called"] = e["aliases"]
        out.append(item)
    return out


_RELATED_CAP = 8        # related-term explanations per prompt (see _add_related_terms)
_RELATED_DEF_CHARS = 300


def _add_related_terms(items: List[Dict[str, Any]], enriched: List[Dict[str, Any]]) -> None:
    """Give each entry 'related_terms': the first sentence of the definition of each term its
    kept facts only name. With a term only named ("ngaben didukung dengan sredaning cita",
    "ngangsen dilakukan setelah ngaben") the model made up what it was ("ritual-ritual ...",
    "memohon keberkahan", conersation.md 2026-10-02); the user wanted explained answers. Not
    the terms a definition names (Tier B 2026-10-02): dewasa ngaben's twenty sasih and wuku
    buried the question (kaenem listed as avoided), bade's badawang nala gave its symbolism to
    "kenapa harus 11", and ngaben's own four (atiwa-tiwa, sawa, ...) padded every ngaben answer
    and made atiwa-tiwa "salah satu jenis ngaben". Kept short; the first thing _fit_context trims."""
    content = get_content()
    shown = {e["id"] for e in enriched}
    total = 0
    for item, e in zip(items, enriched):
        kept = {f.get("fact") for f in item["relationships"] if "target_definition" not in f}
        named = [r["target_id"] for r in e.get("relationships") or []
                 if r.get("statement") in kept and r.get("target_id")]
        glosses = []
        for tid in dict.fromkeys(named):
            if total >= _RELATED_CAP:
                break
            definition = content.best_definition(tid)
            if tid in shown or not definition:
                continue
            shown.add(tid)
            text = _first_sentence(definition, limit=_RELATED_DEF_CHARS)
            glosses.append(f"{content.entity_name.get(tid, tid)}: {text}")
            total += 1
        if glosses:
            item["related_terms"] = glosses


def _json_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _fit_context(items: List[Dict[str, Any]], budget: int) -> List[Dict[str, Any]]:
    """Trim the synthesis context to `budget` characters: related-term explanations go first,
    then child definitions, each from the last term backwards, then the longest term's last
    relationships. See LLM_NUM_CTX for what an over-long prompt did."""
    while len(_json_compact(items)) > budget:
        with_related = [it for it in items if it.get("related_terms")]
        if with_related:
            with_related[-1]["related_terms"].pop()
            if not with_related[-1]["related_terms"]:
                with_related[-1].pop("related_terms")
            continue
        with_def = [r for it in items for r in it["relationships"] if "target_definition" in r]
        if with_def:
            with_def[-1].pop("target_definition")
            continue
        longest = max(items, key=lambda it: len(it["relationships"]))
        if not longest["relationships"]:
            break
        longest["relationships"].pop()
    return items


def _synthesize(user_msg: Text, enriched: List[Dict[str, Any]], tracker: Optional[Tracker] = None) -> str:
    """Step 4: synthesize a natural Indonesian answer from `enriched`, with a
    deterministic guard against the local LLM refusing/hedging on context it was
    actually given (observed directly in conersation.md for terms that HAD
    resolved successfully -- e.g. ngeroras, naga banda, tirte, panca maha butha)."""
    # A word-meaning question is answered from definitions alone: with the edges
    # in context too, the small model kept listing them ("pitra berwujud sekah
    # kangsen, menerima daksina tapakan ...") instead of saying what the words mean.
    word_meaning = bool(_WORD_MEANING_RE.search(user_msg))
    families = _aspect_families(user_msg)
    aspect_preds = _aspect_predicates(user_msg)
    # the text-only attributes of the asked aspect (a word-meaning question gets the
    # literal meaning / word origin ones); none for a plain "apa itu X"
    attr_preds = PREDICATE_FAMILIES["asal_kata"] if word_meaning else aspect_preds
    content = get_content()
    day_q = any(e["id"] == "dewasa_ngaben" for e in enriched) and bool(re.search(r"\bhari\b", user_msg, re.I))
    for e in enriched:
        # "hari apa yang harus dihindari untuk ngaben dan kenapa" asks why those days: ngaben's
        # own purposes ("menjaga harmoni ...") came back as the reason to avoid kekeran desa
        # (Tier B 2026-10-02)
        if day_q and e["id"] != "dewasa_ngaben":
            e["aspect_facts"] = []
            continue
        e["aspect_facts"] = content.attribute_sentences(e["id"], attr_preds) if attr_preds else []
        if "komposisi" in families:
            # gajah mina has no parts of its own; the breakdown shows those of patulangan, its
            # kind-parent. Without them here, rule 23 made the model write "tidak tercatat" right
            # above that breakdown (Tier B 2026-10-02)
            e["aspect_facts"] += content.inherited_part_sentences(e["id"])
    list_q =bool(_LIST_Q_RE.search(user_msg)) and len(enriched) >= 2
    if "sarana" in families or list_q:
        _stage_sarana_facts(enriched)
    if "sumber" in families:
        _source_facts(enriched)
    class_list = _class_filter(user_msg, enriched)
    if not class_list and "sarana" not in families:
        # computed only for the class filter, which did not apply
        for e in enriched:
            e["sarana_facts"] = []
    stages_q = bool(_STAGES_Q_RE.search(user_msg))
    if stages_q and enriched:
        _order_stages(enriched[0])
    # None also when nothing links the terms: the full edge lists stay, and rule 18
    # (which says the shown edges ARE the links) is left out
    link_to = _link_filter(enriched) if len(enriched) >= 2 and _RELATION_Q_RE.search(user_msg) else None
    # "apa saja isi banten peras": told to name the parts only (rule 13), the model still
    # described each from its definition ("beras: direndam dan digiling halus menjadi
    # babelonyoh ...", Tier B 2026-10-02); the appended breakdown says what each is made of
    contents_q = _contents_question(user_msg)
    # "apa peran tirta dalam pengabenan" / "untuk apa panca datu": a purpose question about a
    # class or set keeps its types / members, whose definitions say what each is for
    keep_children = ({enriched[0]["id"]} if "fungsi" in families and enriched and not _WHY_Q_RE.search(user_msg)
                     and sum(1 for r in enriched[0]["relationships"] if r.get("target_definition")) >= 2
                     else None)
    meaning_words = None
    if aspect_preds and aspect_preds & PREDICATE_FAMILIES["simbol"]:
        names = set().union(*(_content_words(e["name"]) for e in enriched)) if enriched else set()
        meaning_words = (_content_words(user_msg) - names) | {
            _NUMBER_WORDS[n] for n in re.findall(r"\b\d{1,2}\b", user_msg) if n in _NUMBER_WORDS}
    context_items = _llm_context(enriched, with_relationships=not word_meaning,
                                 only_predicates=aspect_preds, keep_to=link_to,
                                 contents_only=contents_q,
                                 part_definitions=not contents_q or bool(_EXPLAIN_EACH_RE.search(user_msg)),
                                 keep_children=keep_children, meaning_words=meaning_words)
    # a contents or sarana list names items only (rules 13 and 19), and a word-meaning answer
    # uses definitions alone: the other terms' explanations would come back as roles there
    if not (contents_q or word_meaning or "sarana" in families):
        _add_related_terms(context_items, enriched)

    synth_sys_prompt = """
    You are a knowledgeable, factual assistant for the Balinese Ngaben ceremony.

    RULES:
    1. Answer ONLY the user's question, using the provided knowledge-base context. Each entry has a 'term', its 'definition', optional 'also_called' (other names for the term), 'relationships' -- each relationship is a 'fact' sentence (already in the correct direction; never reverse it) and sometimes a 'target_definition' explaining the other term -- and optional 'related_terms', short explanations of other terms its definition or facts name.
    2. Answer fully, like a patient teacher. Begin with the direct answer to the question in one or two sentences, then explain it in connected sentences or short paragraphs: give the numbers, examples, names and reasons the context states, and when you mention another term, explain it briefly from its 'target_definition' or 'related_terms' entry. Use the 'related_terms' to connect facts (for example, what is still left after one ceremony that the next one completes). Leave out facts that do not help answer the question. For "apa hubungan X dan Y", explain the link itself -- do not describe X and Y one by one.
    3. NEVER HALLUCINATE. Every statement must come from the context. Do not add facts, reasons, examples, numbers, names or explanations from your own knowledge -- not even ones you believe are true -- and never guess. If the context does not state something, do not state it: elaborate only by explaining and connecting what the context DOES say. Never list example items, categories, or sub-types unless those exact items appear in the context. If a term has no 'target_definition' and no 'related_terms' entry, do NOT invent a description, symbolism, or function for it -- just name it. A 'target_definition' or 'related_terms' entry describes only its own term: never give its meaning, symbolism, purpose, colour, direction or number to the asked term or to any other term.
    4. If a term has a non-empty 'definition' or 'relationships', you MUST use them -- never claim that information about it is missing.
    5. Only if the context lacks the answer entirely, reply: "Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data."
    6. Answer in natural, fluid Indonesian; keep Balinese and Sanskrit ritual terms, but never use English words (no "ceremony", "the", "and"). Do not start sentences with "Dalam konteks Ngaben" -- the whole conversation is already about Ngaben. Never mention "data", "JSON", "konteks", or "basis data" unless using rule 5, and never refer to where the facts came from (no "dalam konteks tersebut", "seperti yang tercantum", "berdasarkan informasi yang diberikan").
    7. Relationship wording: "termasuk salah satu jenis" means a type/variant, "adalah bagian dari" means a stage or part, and "sama dengan" / "dikenal sebagai" mean another name for the same thing. Never call a type a "tahap", never call a stage a "jenis", and never list types or stages as "sebutan lain" (other names).
    8. For "apa itu X", give X's definition in full substance and in its own order, beginning with what its first sentence says; if X has more than six types or members, just name them; if X is a group or set, name every member listed in its definition or in its "termasuk salah satu jenis X" facts. Describe each member only with its own 'target_definition' -- never move a fact from one member to another.
    9. If the user asks to explain each ("setiap"/"masing-masing"/"semua") item or element of something, give each item that has a 'target_definition' its own short explanation from that 'target_definition'.
    10. If the user asks about one specific aspect (e.g. HOW something is done) and the context only covers a different aspect, give what IS available and say plainly that the specific aspect is not detailed -- do not restate the same facts as if they answered it.
    11. Keep each statement with its own subject: never move what a definition says about one thing (for example the body or its elements) to another thing (for example the atma or soul).
    """

    if _COMPOSITION_Q_RE.search(user_msg):
        # "soda dilengkapi apa?" means every component, not only the edge whose verb
        # happens to match the question (the model answered just "canang sari"). Asked to describe
        # each part, it gave a part's use elsewhere as its role inside the whole ("beras kuning:
        # untuk menerangi jalan roh" in canang sari, Tier B 2026-10-02); the breakdown says the rest
        synth_sys_prompt += (
            "\n    13. The user asks what the term consists of / contains / is completed with. "
            "List EVERY component from the facts that say 'berupa', 'berisi', 'terdiri dari', "
            "'dilengkapi', 'diisi dengan', 'terbuat dari' or 'disertai' -- all of them, not only "
            "the one whose verb matches the question. Only name the components: a "
            "'target_definition' tells you what a component is, but what it is used for elsewhere "
            "is not its role here, so do not describe them (unless the user asks to explain each "
            "one, rule 9). A 'jenis' (type) is never a content, and a fact in which the term "
            "is inside something else is not its content. If no fact lists its contents, say that "
            "they are not recorded.\n")

    if any(e["aspect_facts"] for e in enriched):
        # only when present, so the prompt for a plain "apa itu X" is unchanged
        synth_sys_prompt += (
            "\n    14. Some entries also have 'facts': statements about exactly the aspect the user "
            "asks (its meaning, place, time, function, form, who does it, or how). Answer from "
            "those facts and the matching relationships; do not add facts about other aspects.\n")

    # Rules 15-17 are added only for their question shape, like 12-14. Each answers a
    # misreading seen in the 2026-09-25 transcript although the context was right.
    if _STAGES_Q_RE.search(user_msg):
        # "tahapan atma wedana" came back as its types ("Tingkatannya ... Ngerorasin,
        # Mamukur") and skipped its real parts; nguyeg got an invented "tahap keenam"
        synth_sys_prompt += (
            "\n    15. The user asks for the stages. The stages are exactly the terms that 'adalah bagian "
            "dari' the asked term. If their definitions number them ('tahap pertama ... dari delapan "
            "tahapan'), give those numbered stages first, in that order and with those numbers, and "
            "say for each in a sentence what is done in it, from its own 'target_definition'; then "
            "name the other parts in one separate sentence, without numbers. Never give a stage a "
            "number its own definition does not state. A term 'dilakukan menjelang' the asked term "
            "comes before it and a term 'dilakukan setelah' it comes after it; neither is inside it. "
            "A 'jenis' or 'tingkatan' (type or level) is never a stage.\n")
    if _TELL_Q_RE.search(user_msg):
        # "ceritakan proses ngaben dari awal sampai akhir" came back as bare points; the user
        # asked for a story (conersation.md 2026-10-02)
        synth_sys_prompt += (
            "\n    28. The user asks you to tell or explain it (ceritakan / uraikan / jelaskan): answer in "
            "flowing paragraphs, not a bare list. Stages are narrated in their order ('Tahap pertama, "
            "... Setelah itu, ...'), with the numbers their definitions state.\n")
    if _YES_NO_Q_RE.search(user_msg):
        # "apakah lembu juga dibuat oleh seorang undagi?" -> "Lembu tidak dibuat oleh seorang
        # undagi", which nothing stated (conersation.md 2026-10-02)
        synth_sys_prompt += (
            "\n    27. The user asks a yes/no question. Begin with 'Ya' or 'Tidak' only when a fact or "
            "definition decides it, then explain with those facts. If none decides it, say that it is not "
            "recorded and give the related facts -- never answer 'tidak' only because a fact is missing.\n")
    if keep_children:
        # "apa peran tirta dalam pengabenan": the user wanted which tirtha is used where and for
        # what, not only tirtha's general purposes (conersation.md 2026-10-02)
        synth_sys_prompt += (
            "\n    29. The asked term has types or members (the facts with a 'target_definition'). After "
            "its own purpose, say for each type or member where it is used and what it is for, only "
            "from that one's own 'target_definition'; if that does not say, just name it.\n")
    if _KINDS_Q_RE.search(user_msg):
        # "jenis ngaben" dropped asti wedana and pinned svasta's "sama dengan Asti Wedana"
        # on sawa wedana; "jenis tirtha" ran past the length limit mid-word (T80)
        synth_sys_prompt += (
            "\n    16. The user asks for the types. List EVERY term that 'termasuk salah satu jenis' the "
            "asked term, each once, with ONE short sentence each from its own 'target_definition' -- "
            "never move a fact from one type to another.\n")
    if _COMPARE_Q_RE.search(user_msg):
        # "ngangsen ... mengangkat status pitra" -- its definition says the status is NOT
        # changed; "ngerorasin ... tanpa tujuan ..." was invented as the contrast
        synth_sys_prompt += (
            "\n    17. The user asks how terms differ. State only differences the facts show. A fact given "
            "for one term only is not evidence that the other term lacks it or does the opposite. Keep "
            "each fact's meaning exactly: never turn 'belum' or 'tidak' into its opposite. When a "
            "definition says why one comes after or depends on the other, say that too.\n")
    if link_to:
        # "apa hubungan palebon dengan bade" re-described both terms one by one
        synth_sys_prompt += (
            "\n    18. The user asks how the terms are related. The relationships shown are only the "
            "facts that link them (or a term they are both linked to). If one term's definition names "
            "the other, state that link first. Then give only the linking facts, in their direction -- "
            "do not describe each term's other facts.\n")

    if word_meaning:
        # only here -- as a standing rule the small model applied this format to
        # ordinary questions too ("Jadi, 'X' berarti ...", with invented meanings)
        synth_sys_prompt += (
            "\n    12. The user asks what the word(s) of a term mean. Answer in this order: first "
            "'Kata \"<kata 1>\" berarti ...', then 'Kata \"<kata 2>\" berarti ...', then "
            "'Jadi, \"<istilah gabungan>\" berarti ...'. For each word, use its literal meaning from "
            "'facts' (\"secara harfiah berarti ...\") when there is one, else its definition (a compound "
            "term's definition may itself explain its words). Do not add unrelated facts.\n")

    if any(e.get("sarana_facts") for e in enriched):
        synth_sys_prompt += (
            "\n    19. The user asks which offerings or equipment (sarana, banten, upakara) are used. "
            "List the items of every 'Sarana yang digunakan dalam ...' fact, all of them: first the items "
            "used in the asked term itself, then one group per stage it names. Only name the items -- do "
            "not describe them and do not say where the information comes from.\n")
    why_q = bool(_WHY_Q_RE.search(user_msg))
    # with a purpose/meaning fact in context the model still opened with "alasannya belum
    # tercatat" (T39/T68/T74): that opening is cut by code (_strip_why_refusal), not forbidden
    # here -- a rule saying "never say it is not recorded" made it invent reasons ("agar ...
    # mendapatkan keberkahan yang maksimal", Tier B 2026-10-01)
    has_reason = _has_reason_facts(enriched)
    if why_q:
        # "kenapa angka 11 dipilih untuk bade raja?" got an invented reason ("angka 11 memiliki
        # arti khusus dan simbolis") the fabrication ratio did not catch (Tier B 2026-09-29);
        # a definition restated as the reason was circular (T29)
        synth_sys_prompt += (
            "\n    21. The user asks WHY. Give a reason only if the context states it (for example with "
            "'karena', 'sebab', 'agar', 'bertujuan', 'bermakna', 'melambangkan', 'menunjukkan'), from "
            "whichever definition or fact explains the asked thing. If it does not, begin with 'Maaf, "
            "alasannya belum tercatat di basis data.' and then give only the related facts that are "
            "recorded -- never guess a reason. Merely restating what the thing is, is not a reason.\n")
    if day_q:
        # T15/T16/T20/T96 answered "which days" with the sasih (months) only; with the reasons
        # asked, sasih kaenem and kapitu (dewasa madya) were listed as avoided (Tier B 2026-10-02)
        synth_sys_prompt += (
            "\n    22. The user asks about DAYS (hari). A day is a wuku/wewaran day (for example buda wuku "
            "landep), not only a sasih (month). From the definition of dewasa ngaben give: the days that "
            "are allowed, the days that must not be used, and then the good and avoided sasih. Use only "
            "what that definition lists. Something is avoided only where the definition says so "
            "(dihindari, tidak boleh, sasih mati); dewasa madya (kaenem, kapitu) is middling, not avoided. "
            "A reason for avoiding one comes only from that term's own definition or 'related_terms'.\n")
    # (a why-question's missing reason is rule 21's)
    missing_aspects = list(dict.fromkeys(
        f for f in families if f in _ASPECT_LABELS and not (why_q and f in _OUTGOING_ONLY_FAMILIES)
        and not class_list and enriched and not _aspect_present(f, enriched)))
    if missing_aspects:
        # "siapa yang melakukannya?" about pangringkes got "biasanya melibatkan keluarga dekat,
        # tetua desa ..." (T64); "apa tujuannya" an invented "sebelum dimasukkan ke dalam kubur" (T66)
        asked = ", ".join(_ASPECT_LABELS[f] for f in missing_aspects)
        synth_sys_prompt += (
            f"\n    23. The user asks about {asked} of {enriched[0]['name']}. No fact in the context states "
            "it. Unless a definition states it, say that it is not recorded in the knowledge base. Never "
            "guess, and never use 'biasanya', 'umumnya' or 'mungkin' to fill the gap.\n")
    if _PERMISSION_Q_RE.search(user_msg):
        # "apakah masyarakat umum boleh memakai bade?" -> "tidak boleh" from a definition that
        # only says who usually uses it (T41/T73)
        # (no quoted Indonesian verdict here: quoted, it came back as a bare first line)
        synth_sys_prompt += (
            "\n    24. The user asks whether something is allowed or required. Call it forbidden or required "
            "only if a fact or definition explicitly states a prohibition, an avoidance or a duty. That a "
            "group usually (lazimnya) uses something does not forbid it to others: then say what is usual "
            "and that no prohibition is recorded. Answer in full sentences.\n")
    if class_list:
        cls_name, term_names = class_list
        synth_sys_prompt += (
            f"\n    25. The user asks which {cls_name} relate to {', '.join(term_names)}. Name only the "
            f"{cls_name} in the context; if none is listed for it, say that it is not recorded.\n")
    if _ONLY_THAT_Q_RE.search(user_msg):
        # "hanya itu sarananya?" -> "Tidak, hanya itu" (T44)
        synth_sys_prompt += (
            "\n    26. The user asks whether that is all. If the context has nothing more, begin with "
            "'Ya, yang tercatat hanya itu' -- never 'Tidak'.\n")
    missing = [t for e in enriched for t in e.get("missing_terms") or []]
    if missing:
        # "apa hubungan sasih kliwon dengan pitra yadnya" -> "Sasih kliwon adalah salah satu
        # jenis pitra yadnya" (2026-09-29): the model related a term it had no entry for
        synth_sys_prompt += (
            f"\n    20. The user also asked about: {', '.join(missing)}. It is NOT in the context: say in "
            "one sentence that it is not recorded, and never describe it or relate it to anything.\n")

    # Ask the synthesis model about the canonical name. Shown "apa itu lingga sarira"
    # beside an entry named "suksma sarira", it wrote "lingga sarira termasuk salah
    # satu jenis suksma sarira" -- even when told the two are one thing (2026-09-25).
    # The answer still opens with "<asked name> adalah sebutan lain untuk <name>" (below).
    # A misspelling is replaced too, or the model repeats it (typed_as).
    synth_q = user_msg
    for e in enriched:
        for surface in (e.get("asked_as"), e.get("typed_as")):
            if surface:
                synth_q = re.sub(r"\b" + re.escape(surface) + r"\b", e["name"], synth_q, flags=re.I)
    # "nyiramin layon" -> "nyiramang layon layon" (T88)
    synth_q = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", synth_q, flags=re.I)
    # "sasih kliwon" -> "kliwon": shown the user's wrong premise, the model went along with it
    # ("Sasih kliwon adalah sasih kedua"). The answer opens with the term's own sentence saying
    # it is no such class, when its definition has one.
    corrections = []
    for cls, cls_surf, term, term_surf in _misclassed_terms(user_msg, get_resolver()):
        synth_q = re.sub(rf"\b{re.escape(cls_surf)}\s+{re.escape(term_surf)}\b", term_surf, synth_q, flags=re.I)
        definition = get_content().entity_def.get(term.id) or ""
        for s in re.split(r"(?<=[.;])\s+", definition):
            if re.search(rf"\bbukan\b[^.;]*\b{re.escape(cls.name)}\b", s, re.I):
                s = re.sub(r"^(?:jadi|maka),?\s+", "", s.strip(), flags=re.I).rstrip(";.")
                corrections.append(f"{s[:1].upper()}{s[1:]}.")
                break

    # The question comes again after the context: it must survive any truncation, and
    # a small model follows the last instruction it read.
    budget = _PROMPT_CHAR_BUDGET - len(synth_sys_prompt) - 2 * len(synth_q) - 200
    raw_context = _json_compact(_fit_context(context_items, budget))
    synth_user_prompt = (f"Pertanyaan: {synth_q}\nKonteks:\n{raw_context}\n\n"
                         f"Jawab pertanyaan ini dalam bahasa Indonesia: {synth_q}")
    cut_off = False
    # "apa saja isi banten peras": nothing records its contents, and with rule 13 in the prompt
    # the model still listed "upacara pengaskaran, pemelaspas kajang ..." as its contents (Tier B
    # 2026-10-01) -- that miss is answered without the model
    no_contents = bool(
        _contents_question(user_msg) and set(families) == {"komposisi"} and context_items
        and not context_items[0]["relationships"] and not context_items[0].get("facts")
        and not _CONTENTS_IN_DEF_RE.search(enriched[0].get("definition") or ""))

    def ask(system: str) -> str:
        nonlocal cut_off
        msg = _llm_invoke([SystemMessage(content=system), HumanMessage(content=synth_user_prompt)])
        cut_off = (getattr(msg, "response_metadata", None) or {}).get("done_reason") == "length"
        return msg.content

    composition_q = _composition_q(user_msg)
    if composition_q:
        raw_answer = _raw_material_answer(enriched)
        if raw_answer:
            return _tidy_answer(raw_answer)
        if _composition_breakdown(enriched[0]["id"]):
            no_contents = False
    usage_answer = (_usage_norm_answer(user_msg, enriched) or _stated_rule_answer(user_msg, enriched)
                    or _case_compare_answer(user_msg, enriched) or _order_answer(user_msg, enriched))
    if usage_answer:
        return _tidy_answer(usage_answer)
    if no_contents:
        name, known = enriched[0]["name"], _first_sentence(enriched[0].get("definition"))
        answer = (f"Maaf, isi atau bahan {name} belum tercatat di basis data."
                  + (f" Yang tercatat tentang {name}: {known}" if known else ""))
        return _tidy_answer(answer)
    try:
        answer = ask(synth_sys_prompt)
        english = _english_words(answer)
        if _looks_english(answer) or english:
            _log_fabrication(user_msg, enriched, answer, kind="llm_english_retry")
            avoid = f", tanpa kata bahasa Inggris seperti {', '.join(english)}" if english else ""
            answer = _swap_english(ask(synth_sys_prompt + f"\n    Tulis seluruh jawaban dalam bahasa Indonesia{avoid}.\n"))
        if cut_off:
            answer = _trim_cut_off(answer)
    except Exception as e:
        # Ollama down/unreachable/timed out -- fall back to the pure-Python
        # answer instead of crashing the action and leaving the user with no
        # reply at all.
        print(f"LLM synthesis error: {e}")
        return _deterministic_answer(enriched)

    if not answer.strip() or _looks_english(answer):
        # an empty reply reached the user as silence
        _log_fabrication(user_msg, enriched, answer, kind="llm_empty_or_english_override")
        answer = _deterministic_answer(enriched)
    elif _has_grounding(enriched):
        plain = aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg)
        known = _first_sentence(enriched[0].get("definition"))
        if _has_refusal_signal(answer):
            if plain:
                # "apa itu X" refused although X's definition was right there
                _log_refusal(user_msg, enriched, answer)
                answer = _deterministic_answer(enriched)
            else:
                # the asked detail really is not recorded: keep the refusal, add what is
                _log_refusal(user_msg, enriched, answer, kept=True)
                if known:
                    answer = f"{answer.rstrip()} Yang tercatat tentang {enriched[0]['name']}: {known}"
        elif _has_fabrication_signal(answer, enriched):
            _log_fabrication(user_msg, enriched, answer)
            if plain or not known:
                answer = _deterministic_answer(enriched)
            else:
                # an invented reason for "kenapa angka 11 dipilih ..." is replaced by an
                # honest miss, not by a definition that answers something else
                answer = ("Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data. "
                          f"Yang tercatat tentang {enriched[0]['name']}: {known}")

    answer = _tidy_answer(answer)
    if why_q and has_reason:
        answer = _strip_why_refusal(answer)
    answer = _drop_speculation(answer, raw_context)
    if _PERMISSION_Q_RE.search(user_msg):
        answer = _fix_unstated_prohibition(answer, raw_context)
    answer = _fix_only_that(answer, user_msg)
    answer = _fix_kind_claims(answer, enriched)
    answer = _fix_moved_member_facts(answer, enriched)
    answer = _drop_reversed_offerings(answer, enriched)
    answer = _complete_set_members(answer, enriched)
    if not class_list and (aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg)
                           or families == ["jenis"]):
        answer = _complete_kind_lists(answer, enriched)
    if (not class_list and aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg) and len(enriched) == 1
            and not _RELATION_Q_RE.search(user_msg) and not _COMPARE_Q_RE.search(user_msg)):
        answer = _ensure_definition_lead(answer, enriched)
    answer = _complete_sarana_lists(answer, enriched)
    if len(enriched) >= 2 and (_COMPARE_Q_RE.search(user_msg) or _RELATION_Q_RE.search(user_msg)):
        answer = _complete_stated_link(answer, enriched)
    if why_q and _WHY_AVOID_Q_RE.search(user_msg):
        answer = _complete_stated_reasons(answer, enriched, user_msg)
    if composition_q:
        answer = _complete_composition(answer, enriched)
    if day_q:
        answer = _complete_day_rules(answer, enriched)
    if stages_q:
        answer = _drop_kinds_from_stages(answer, enriched)
        answer = _complete_stage_order(answer, enriched)
    if word_meaning:
        answer = _add_literal_meaning(answer, enriched)
    for c in reversed(corrections):
        if _ortho_key(c) not in _ortho_key(answer):
            answer = f"{c} {answer}"

    # the user asked by another name for the same concept -- say so, instead of
    # the "nothing more is recorded" note below, which read as a refusal after
    # "apa itu samskara" following "apa itu sangaskara" (2026-09-24)
    # (not for a verb form: "Dihanyutkan adalah sebutan lain untuk nganyut" opened "mengapa abu
    # jenazah dihanyutkan ...", conersation.md 2026-10-02)
    synonyms = [f"{e['asked_as'][:1].upper()}{e['asked_as'][1:]} adalah sebutan lain untuk {e['name']}."
                for e in enriched if e.get("asked_as") and not _VERB_FORM_RE.match(e["asked_as"])]
    if synonyms:
        answer = " ".join(synonyms) + " " + answer
    elif (tracker is not None and _is_near_repeat(answer, _last_bot_utterance(tracker))
          and not any(e["name"].lower() in user_msg.lower() for e in enriched)):
        # a follow-up like "tapi digunakan bagaimana?" that got the same facts back --
        # not a user who re-asked about the term by name
        answer += (
            " (Ini sama dengan penjelasan saya sebelumnya -- informasi yang lebih "
            "rinci mengenai hal ini belum tercatat di basis data.)"
        )

    return answer


def _tidy_answer(answer: Text) -> Text:
    """Output clean-up every answer gets: Cyrillic look-alikes, references to the prompt
    itself, and sentences naming a prompt field."""
    answer = answer.translate(_CYRILLIC_LOOKALIKES)
    answer = _strip_meta_phrases(answer)
    # rule 6 forbids opening a sentence with it, the whole conversation being about Ngaben; it still
    # came ("Dalam konteks Ngaben, bhuta kala dianggap ...", Tier B 2026-10-05). Inside a sentence it
    # stays: the KB's own definitions say "dalam konteks Ngaben" there.
    answer = re.sub(r"(^|[.!?]\s+|\n\s*)Dalam konteks (?:upacara )?Ngaben,\s+(\w)",
                    lambda m: m.group(1) + m.group(2).upper(), answer, flags=re.I)
    answer = _FIELD_LEAK_RE.sub("", answer).strip()
    # "pras arepan terbuat dari ..." (the model copies the question's lowercase name)
    return answer[:1].upper() + answer[1:]


# The fallback prompt's reply for an off-topic question.
_OFF_TOPIC_MARK = "DI_LUAR_TOPIK"
# Resolver tiers that match a name as written -- not a typo guess, and not a loose
# force_merge surface ("harga" -> harga tirtha made "berapa harga kopi" a KB question).
_NAMED_VIA = frozenset({"exact", "alias", "strip", "ortho"})


def _names_kb_term(user_msg: Text) -> bool:
    """ActionOutOfScope's test (regression Tier A checks it on the out_of_scope examples):
    the message names a KB term as written, and either that term is ngaben or no other
    word is left over. A word only a typo / force_merge hit explains counts as left over."""
    mentioned, leftover = _mentioned_terms(user_msg, get_resolver())
    named = [m for m, _ in mentioned if m.via in _NAMED_VIA]
    leftover = leftover + [p for m, p in mentioned if m.via not in _NAMED_VIA]
    return bool(named) and (not leftover or any(m.id == "ngaben" for m in named))


def _slot_events(entity_history: List[str], found_names: List[str]) -> List[Dict[Text, Any]]:
    """The topic is the term the question named (found_names[0] -- the message's own
    terms come first). It used to be found_names[-1], usually a term carried over from
    the history, so "hanya itu sarananya?" after "apa itu nyiramang layon ..." went to
    ngaben (2026-09-29). The history keeps the most recently discussed term last."""
    topic = found_names[0]
    history = [n for n in entity_history if n not in found_names] + found_names[1:] + [topic]
    return [SlotSet("current_entity", topic), SlotSet("entity_history", history[-6:])]


class ActionGraphRAG(Action):
    def name(self) -> Text:
        return "action_graph_rag"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        current_entity = tracker.get_slot("current_entity")
        entity_history: List[str] = tracker.get_slot("entity_history") or []

        enriched, unresolved, found_names = _extract_and_resolve(
            dispatcher, tracker, user_msg, entity_history,
            current_entity=current_entity, announce_miss=True
        )
        if not enriched:
            # Don't clear history/current_entity -- a failed extraction/resolution
            # this turn shouldn't erase what was successfully established earlier.
            return []

        answer = _synthesize(user_msg, enriched, tracker)
        dispatcher.utter_message(text=answer)
        return _slot_events(entity_history, found_names)


class ActionLLMFallback(Action):
    def name(self) -> Text:
        return "action_llm_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        current_entity = tracker.get_slot("current_entity")
        entity_history: List[str] = tracker.get_slot("entity_history") or []

        # Goal 1 fix: nlu_fallback used to mean "fully ungrounded answer, memory
        # untouched" even for a genuine follow-up that happened to trip the
        # fallback classifier. Try the same KB resolution path first (silently --
        # announce_miss=False, since a resolver-level "not found" message here
        # would just be confusing followed by a fallback answer); only drop to a
        # free-form answer on a genuine resolution miss, and leave memory
        # untouched in that case, same as a failed ActionGraphRAG turn.
        enriched, unresolved, found_names = _extract_and_resolve(
            dispatcher, tracker, user_msg, entity_history,
            current_entity=current_entity, announce_miss=False
        )
        if enriched:
            answer = _synthesize(user_msg, enriched, tracker)
            dispatcher.utter_message(text=answer)
            return _slot_events(entity_history, found_names)

        fallback_prompt = f"""
        You are an assistant for the Balinese Ngaben ceremony. A user asked: "{user_msg}", but no
        matching term was found in the knowledge base for this question.
        If the question is not about Ngaben, Balinese Hindu death rituals or their terms (for
        example weather, food recipes, politics, sports, technology), reply with exactly
        {_OFF_TOPIC_MARK} and nothing else.
        Otherwise answer briefly and conversationally in Indonesian, without any English word.
        Do NOT state specific ritual details, names, or steps as if they were confirmed facts
        from the Ngaben knowledge base -- you have no KB context for this question. If you
        are not sure, say plainly that this detail is not recorded in the knowledge base
        rather than guessing.
        """
        # This answer has no KB context, so it gets the same output checks as a KB answer
        # and an off-topic question gets the out-of-scope reply: until 2026-09-30 an
        # uncertain off-topic question ("siapa presiden ...") was answered freely.
        try:
            answer = _llm_invoke([HumanMessage(content=fallback_prompt)]).content
        except Exception as e:
            print(f"LLM fallback error: {e}")
            answer = "Maaf, saya sedang mengalami gangguan teknis. Silakan coba lagi sebentar lagi."
        if _OFF_TOPIC_MARK in answer:
            dispatcher.utter_message(response="utter_out_of_scope")
            return []
        if not answer.strip() or _looks_english(answer) or _english_words(answer):
            _log_fabrication(user_msg, [], answer, kind="llm_fallback_english_or_empty")
            answer = "Maaf, informasi mengenai hal tersebut belum tercatat di basis data istilah Ngaben."
        dispatcher.utter_message(text=_tidy_answer(answer))
        return []


class ActionOutOfScope(Action):
    """NLU said out_of_scope. A message that names a KB term is answered anyway when
    the term is ngaben itself or nothing else is left in the message: NLU sees only the
    words, and a Ngaben question it misfiles ("bagaimana proses ngaben" was out_of_scope
    until 2026-09-29) got a flat refusal without the KB ever being asked. Any KB term
    alone is not enough -- nasi, kopi, emas, bunga, pura and harga are KB terms, and
    "resep nasi goreng" must stay out of scope. A typo-level hit does not overrule NLU."""

    def name(self) -> Text:
        return "action_out_of_scope"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if _names_kb_term(tracker.latest_message.get("text", "")):
            return ActionGraphRAG().run(dispatcher, tracker, domain)
        dispatcher.utter_message(response="utter_out_of_scope")
        return []

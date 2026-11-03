"""Custom actions for the GraphRAG Ngaben bot: Neo4j + the curated KB, templates for simple
questions, and Qwen on Groq for the rest.

Map, in file order (helpers sit near their first user, so look a name up rather than a section):
  the LLM call (_llm_invoke) and the graph (neo4j_conn)
  shared helpers: the conversation, the logs, the refusal / fabrication / English checks, _deterministic_answer
  steps 1-3, which terms the question is about: _mentioned_terms (the message's own words), then
    _extract_and_resolve and its steps (_needs_extraction ... _enrich)
  what the question asks: the *_Q_RE patterns, _aspect_families / _aspect_predicates (PREDICATE_FAMILIES)
  the context the model gets: _class_filter, _stage_sarana_facts, _link_filter, _llm_context, _fit_context
  answer checks (_drop_*, _fix_*, _complete_*, _trim_*, _strip_*) and code answers (_*_answer), interleaved
  step 4, the answer: _synthesize and its steps (_read_question ... _closing_notes), then _tidy_answer
  templates for simple questions: _template_route decides, _template_answer answers (_TEMPLATES)
  the Rasa actions: ActionGraphRAG, ActionTemplateAnswer, ActionLLMFallback, ActionSapa, ActionOutOfScope

Where to add:
  a template: a _template_<aspect>(family, enriched, user_msg) function, listed in _TEMPLATES
  a code answer (no LLM): a function returning the answer or None, in the chain in _code_answer
  an answer check: a _drop_ / _fix_ / _complete_ function, called from _answer_checks at its place in the order
    (batch_ask.py logs which checks changed an answer by those name prefixes)
  a prompt rule: in _synthesis_rules, under the condition for its question shape"""
from dataclasses import dataclass
import functools
import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Text, Optional

from dotenv import find_dotenv, load_dotenv
from groq import Groq
from neo4j import GraphDatabase
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from rapidfuzz import fuzz

from kb_resolver import _QUESTION_WORDS, _ortho_key, _ortho_token, get_resolver
from kb_content import COMPOSITE_TYPES, PART_IS_SUBJECT, PREDICATE_FAMILIES, get_content

load_dotenv(find_dotenv())

_BOT_DIR = Path(__file__).resolve().parent
_REFUSAL_LOG_PATH = _BOT_DIR / "llm_refusal_log.jsonl"
_UNRESOLVED_LOG_PATH = _BOT_DIR / "unresolved_log.jsonl"
_NEO4J_ERROR_LOG_PATH = _BOT_DIR / "neo4j_error_log.jsonl"

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# The LLM: Qwen on Groq, the senior's choice (2026-10-13; qwen2.5 on a local Ollama until then).
# Simple questions never reach it -- ActionTemplateAnswer answers them from the KB in code -- so it
# serves the complex ones: term extraction (only when the words alone cannot settle the terms) and
# answer synthesis. The prompts and answer guards below were tuned on qwen2.5 and re-checked on this
# model with the full regression (Tier B); run it again before trusting another model.
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
LLM_NUM_PREDICT = 1024
# Prompt size cap. Groq's limit for this model was 8K tokens per minute (developer plan,
# 2026-10-13), and a hub term's prompt reached ~9K tokens on qwen2.5's 12K window -- trimmed to this,
# one turn's calls fit the minute, and a complex answer costs at most this much input.
LLM_MAX_PROMPT_TOKENS = int(os.getenv("LLM_MAX_PROMPT_TOKENS", "6000"))
# Seconds one call may take. Without a limit, a hung server held the turn until Sanic's 300 s
# limit and the user got a 503 instead of the plain answer.
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
# Every call's token use, for the cost of the complex path (the reason for the templates)
_LLM_USAGE_LOG_PATH = _BOT_DIR / "llm_usage_log.jsonl"
# After a failed call, further calls fail at once for this long: a turn makes up to three
# calls, and three timeouts in a row would pass Sanic's 300 s limit anyway.
_LLM_COOLDOWN_S = 60.0
_llm_down_until = 0.0
_llm_client: Optional[Groq] = None
# the last failure (the regression harness stops on Groq's daily token cap)
_llm_last_error: Optional[Exception] = None
# A Qwen 3 model can open its reply with a (here empty) reasoning block, even in instruct mode
_THINK_BLOCK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.S)


def _llm_invoke(messages: List[Dict[str, str]], purpose: str) -> "tuple[str, bool]":
    """One chat call -> (text, cut_off); cut_off is True when the answer stopped at
    LLM_NUM_PREDICT. `messages` are {"role", "content"} dicts; `purpose` names the call in the
    usage log. Fails fast for a minute after a failure (the SDK itself retries a rate limit,
    honouring Groq's retry-after); callers catch the exception and answer without the LLM."""
    global _llm_client, _llm_down_until, _llm_last_error
    if time.monotonic() < _llm_down_until:
        raise RuntimeError("the LLM failed less than a minute ago; not retrying yet")
    try:
        if _llm_client is None:
            # reads GROQ_API_KEY (.env); a missing key fails here like any other outage
            _llm_client = Groq(timeout=LLM_TIMEOUT, max_retries=2)
        # instruct mode: the reasoning a thinking model writes first is billed as output
        reply = _llm_client.chat.completions.create(
            model=LLM_MODEL, messages=messages, temperature=0,
            max_completion_tokens=LLM_NUM_PREDICT, reasoning_effort="none")
    except Exception as e:
        _llm_down_until = time.monotonic() + _LLM_COOLDOWN_S
        _llm_last_error = e
        raise
    usage = reply.usage
    _log_jsonl(_LLM_USAGE_LOG_PATH, {"kind": purpose, "model": LLM_MODEL,
                                     "prompt_tokens": getattr(usage, "prompt_tokens", None),
                                     "completion_tokens": getattr(usage, "completion_tokens", None)})
    choice = reply.choices[0]
    return _THINK_BLOCK_RE.sub("", choice.message.content or ""), choice.finish_reason == "length"


# ~3.5 characters per token measured on these prompts (8742 chars -> 2499 tokens); 3.0
# leaves a margin. The synthesis prompt is trimmed to this many characters.
_PROMPT_CHAR_BUDGET = int((LLM_MAX_PROMPT_TOKENS - 512) * 3.0)


class Neo4jConnection:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        # Set by a failed query, cleared at the start of each turn (_extract_and_resolve).
        # An empty result and an outage both came back as [], so with Neo4j down every
        # answer lost its edges and the model told the user "tahapan ... belum tercatat"
        # for facts the KB holds: all 119 questions of the 2026-10-07 batch ran that way.
        self.failed = False

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
            self.failed = True
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
# "apa arti dari kata ngaben?" got the definition, not what the word means (2026-10-07 batch)
# "istilah salaran berasal dari mana" asks where the word comes from: read as a place question, it went to
# the LLM for "Maaf, asal istilah salaran belum tercatat" (5 in plan #16's test, 2026-10-26)
_WORD_MEANING_RE = re.compile(r"\barti(?:\s+dari)?\s+(?:kata|istilah)\b|\bmakna\s+kata\b|kata dasar|asal kata"
                              r"|berasal dari kata|asal[- ]usul\s+(?:kata|istilah|nama)|harfiah|etimologi"
                              r"|\basal\s+(?:istilah|nama)\b"
                              r"|\b(?:istilah|kata|nama)\s+(?:[\w-]+\s+){1,4}?berasal\s+dari\s*(?:mana|bahasa)\b", re.I)


def _word_label(user_msg: Text) -> str:
    """What a word question asks, for its miss: where the word comes from, or what it means."""
    origin = re.search(r"\basal\b|\bberasal\b|etimologi", user_msg, re.I)
    return "asal kata" if origin and not re.search(r"\barti\b|\bmakna\b|harfiah", user_msg, re.I) else "arti kata"

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


def _has_fabrication_signal(answer: Text, enriched: List[Dict[str, Any]], context_text: Text = "") -> bool:
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
    # and the prompt's context as sent: its 'related_terms' glosses (rule 2 tells the model to use them)
    # are in no enriched field, so "kikir, lemat sudhamala, arit gobed" made a correct "apa itu baja"
    # answer look invented and it was thrown away (#174, LLM comparison 2026-10-20)
    vocab = _context_vocabulary(enriched) | _content_words(context_text)
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


def _tion_to_si(m: "re.Match") -> str:
    """An English "-tion" word as its Indonesian loanword: "-tion" is "-si" and a "c" before a/o/u
    is "k" -- reincarnation -> reinkarnasi, purification -> purifikasi, tradition -> tradisi. "bebas
    dari siklus reincarnation" survived the retry (2026-10-07 batch); no Indonesian word ends in -tion."""
    w = re.sub(r"tions?$", "si", m.group(0).lower())
    return re.sub(r"c(?=[aou])", "k", w)


def _swap_english(answer: Text) -> Text:
    out = re.sub(r"\btidak\s+(propitious|auspicious)\b", "tidak baik", answer, flags=re.I)
    out = re.sub(r"\b(" + "|".join(_ENGLISH_SWAPS) + r")\b", lambda m: _ENGLISH_SWAPS[m.group(1).lower()],
                 out, flags=re.I)
    return re.sub(r"\b[a-z]+tions?\b", _tion_to_si, out, flags=re.I)


# A question that asks more than what X is -- why, whether, how many, when, who -- can be
# correctly refused when the KB lacks it. Replacing that refusal with X's definition
# answered something else ("kenapa angka 11 dipilih untuk bade raja?" -> the definition
# of bade; llm_refusal_log.jsonl 2026-09-29).
# A rule question too: "apa ketentuan penggunaan niskala" was read as a plain "apa itu X" and got the
# definition put in front of "Ketentuan ... tidak tercatat" (plan #16, 2026-10-26)
_SPECIFIC_Q_RE = re.compile(
    r"\b(kenapa|mengapa|apakah|bagaimana|berapa|kapan|siapa|di ?mana|boleh|harus|hanya|"
    r"dipilih|alasan|hari baik|ketentuan(?:nya)?|aturan(?:nya)?|syarat(?:nya)?|larangan(?:nya)?|pantangan(?:nya)?)\b",
    re.I)
_WHY_Q_RE = re.compile(r"\b(kenapa|mengapa|alasan(nya)?)\b", re.I)
# What happens if something is NOT done: "kalao misalnya di bali tidak ngaben", "emang kalok
# semisal nggak ngaben kenapa?", "apa yang terjadi kalau emang sawa tidak kembali menjadi panca
# maha butha", "apa yang konsekuensinya terhadap pitra?" (conersation.md 2026-10-07). With no
# aspect they kept every edge, and the answers listed ngaben's stages and kinds, or "ngaben
# adalah pilihan" -- the user asked for "if A doesn't happen then B, B matters because C".
# A missing means is the user's situation, not something left undone: "kalo keluarga gak punya
# duit banyak, ada cara ngaben yang lebih hemat gak?" got the all-kinds-are-equal template and
# "kalau ... gak ada sulinggih, ngabennya tetep bisa jalan gak?" "Maaf, akibatnya belum
# tercatat" (reasoning test 2026-10-09/12).
_CONSEQUENCE_Q_RE = re.compile(
    r"\b(?:kalau|kalao|kalo|kalok|jika|jikalau|bila|apabila|seandainya|andaikan|andai)\b(?:\s+[\w-]+){0,7}?\s+"
    r"(?:tidak|tak|nggak|ngga|enggak|gak|ga|tanpa|belum)\b(?!\s+(?:punya|ada|mampu|cukup|sempat)\b)"
    r"|\bapa (?:yang )?(?:terjadi|akibatnya|dampaknya)\b|\bkonsekuensi"
    # "apa itu ngaben tanpa tirtha pangentas": read as the name of a kind ("Ngaben tanpa tirta
    # pangentas adalah upacara ... termasuk salah satu jenis pitra yadnya", "masih dilaksanakan")
    # on two fresh loads in five, while the context says it counts as not done (Tier B 2026-10-08)
    r"|\bapa itu\b[^?.]*\btanpa\b", re.I)
_LOSS_WORD_RE = re.compile(r"\b(?:tidak|tak|tanpa|jika|kalau|apabila|bila|maka|sehingga|akibat(?:nya)?|belum|"
                           r"gagal|terhambat|terhalang)\b", re.I)
_PURPOSE_WORD_RE = re.compile(r"\b(?:berfungsi|bertujuan|fungsi(?:nya)?|tujuan(?:nya)?)\b", re.I)


_GUESS_HEDGE_RE = re.compile(r"\b(?:mungkin|kemungkinan|barangkali|bisa jadi)\b", re.I)


def _trim_consequence_answer(answer: Text) -> Text:
    """A consequence answer says what is lost. After its opening (what the thing achieves, rule
    30), a sentence that only names another purpose and no loss answers nothing: "Secara sosial,
    ngaben juga berfungsi sebagai perekat kohesi sosial." (conersation.md 2026-10-07, point 2;
    again in Tier B 2026-10-08). Nor does one that guesses at the loss: no source states a
    consequence, the chain of purposes is the answer, and "... jasad sawa mungkin tidak dapat
    sepenuhnya melepaskan jiwa" / "unsur-unsur alam tersebut mungkin tidak dapat kembali ... dapat
    mengganggu proses pengembalian roh leluhur" were the model's (same days). Never leaves nothing."""
    parts = [s for s in re.findall(r"[^.!?\n]+[.!?]*", answer) if s.strip()]
    drop = [s for s in parts[1:] if _PURPOSE_WORD_RE.search(s) and not _LOSS_WORD_RE.search(s)
            or _GUESS_HEDGE_RE.search(s)]
    opening_is_marker = not parts or not re.sub(r"[\s\d.)]", "", parts[0])   # "1." of a list
    if not drop or opening_is_marker and len(drop) == len(parts) - 1:
        return answer
    for s in drop:
        answer = answer.replace(s, "", 1)
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", re.sub(r"[ \t]{2,}", " ", answer)).strip()


_ALL_KINDS_EQUAL_RE = re.compile(r"\bsemua jenis\b[^.]*\b(?:nilai yang sama|sama saja|sama-sama)\b", re.I)


def _kind_consequence_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """"lantas memang kenapa jika ngaben dengan cara yama purwana tatwa tidak terlaksana? apa yang
    konsekuensinya terhadap pitra?" -- one kind of a ceremony not done -- was "just a big blunder"
    (conersation.md 2026-10-07) and, on the 2026-10-08 replay, invented "pitra tidak akan mendapatkan
    pencerahan". Ngaben's definition states the answer (corpus L1072, L1945): every kind has the
    same spiritual value and leads to Atma Wedana. So: the kind's class, that sentence as written,
    and the other kinds recorded. None unless a consequence question names a kind of a class
    whose definition says so."""
    if not _CONSEQUENCE_Q_RE.search(user_msg):
        return None
    content = get_content()
    for e in enriched:
        for parent in sorted(content.kind_parents.get(e["id"], ())):
            p_def = content.best_definition(parent) or ""
            same = next((s for s in _sentences(p_def) if _ALL_KINDS_EQUAL_RE.search(s)), None)
            if not same:
                continue
            p_name = content.entity_name.get(parent, parent)
            others = [content.entity_name.get(k, k) for k in content.kinds_of(parent) if k != e["id"]]
            out = f"{e['name'][:1].upper()}{e['name'][1:]} adalah salah satu jenis {p_name}. {same}"
            if others:
                out += f" Jenis {p_name} lain yang tercatat: {', '.join(others)}."
            return out
    return None


_GOAL_FACT_RE = re.compile(r"\buntuk mencapai\b|\btujuan (?:akhir|tertinggi|utama)\b", re.I)


def _complete_consequence_goal(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A consequence answer ends at the stated goal: "if A doesnt Happen then B, reason why B is
    important is C, as C is the main goal of this religion" (conersation.md 2026-10-07). "kalao
    misalnya di bali tidak ngaben" named lost purification and "kohesi sosial" and never moksa
    (2026-10-08 replay). The term's goal edge ("ngaben merupakan salah satu tahap untuk mencapai
    moksa") and the goal's own first sentence follow when the answer never names the goal."""
    if not enriched:
        return answer
    for r in enriched[0].get("relationships") or []:
        statement, target = r.get("statement") or "", r.get("target") or ""
        if (r.get("outgoing") and target and _GOAL_FACT_RE.search(statement)
                and not re.search(rf"\b{re.escape(target)}\b", answer, re.I)):
            gloss = _first_sentence(get_content().best_definition(r.get("target_id")), limit=400)
            return answer.rstrip() + f"\n\nPadahal, {statement.rstrip('.')}." + (f" {gloss}" if gloss else "")
    return answer


def _asks_what_is_first(user_msg: Text, enriched: List[Dict[str, Any]]) -> bool:
    """"apa itu X dan ..." / "siapa itu X dan ...", X being the first term."""
    m = re.match(r"^\s*(?:apa|siapa)\s+itu\s+(.+?)(?:\s+dan\b|[?,]|$)", user_msg, re.I)
    if not m or not enriched:
        return False
    asked, e = _ortho_key(m.group(1)), enriched[0]
    return any(s and _ortho_key(s) == asked for s in [e["name"], e.get("asked_as"), e.get("typed_as")]
               + list(e.get("aliases") or []))


def _opens_with(answer: Text, e: Dict[str, Any]) -> bool:
    """The answer opens with `e` as its subject: a surface of it among its first three words
    ("Brahma adalah salah satu dewa Trimurti" names Trimurti, but is about Brahma)."""
    first = _ortho_key(" ".join(answer.split()[:3]))
    return any(s and _ortho_key(s) in first for s in [e["name"], e.get("asked_as"), e.get("typed_as")]
               + list(e.get("aliases") or []))


def _drop_empty_items(answer: Text) -> Text:
    """A list item whose text a guard cut leaves its marker: "apa saja bahan pepaga" showed
    "1." / "4." / "5." on lines of their own (Tier B 2026-10-08). The markers go and the
    numbered items left are renumbered in order."""
    # a list's first item cut whole leaves a blank line under its heading: "Menurut sasih:" / "" / "- Sasih
    # kaenem ..." (the good sasih, said in the opening, went as a repeat; plan #16, 2026-10-26)
    answer = re.sub(r"(:[ \t]*)\n[ \t]*\n(?=[ \t]*(?:\d+[.)]|[-*•])\s)", r"\1\n", answer)
    lines = answer.split("\n")
    kept = [x for x in lines if not re.fullmatch(r"\s*(?:\d+[.)]|[-*•])\s*", x)]
    if len(kept) == len(lines):
        return answer
    if any(re.fullmatch(r"\s*\d+[.)]\s*", x) for x in lines):
        # each list counts from 1; a line of prose between two lists starts a new one
        n, out = 0, []
        for x in kept:
            if re.match(r"\s*\d+[.)]\s", x):
                n += 1
                x = re.sub(r"^(\s*)\d+([.)])", lambda m: f"{m.group(1)}{n}{m.group(2)}", x)
            elif x.strip():
                n = 0
            out.append(x)
        kept = out
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()

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
# markers of one kind: a member named by one of them (the direction "selatan") has the others as peers
_MARKER_CLASSES = (frozenset("timur selatan barat utara tengah".split()), frozenset("putih merah kuning hitam".split()),
                   frozenset("iswara brahma mahadewa wisnu wishnu siwa shiwa".split()),
                   frozenset({"sebelas", "sembilan"}),
                   frozenset({"dewa yadnya", "bhuta yadnya", "manusa yadnya", "rsi yadnya"}))


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
    resolver = get_resolver()
    out, sentences = answer, re.findall(r"[^.!?\n]+[.!?]*", answer)
    for s in sentences:
        if not markers(s):
            continue
        # Where members are named, by any surface the term finder knows ("Sudra" is wangsa sudra jadma,
        # "Dewa Siwa" is shiwa), and the other terms named. A member's name inside a longer term's
        # ("kain" in "kain putih") does not name the member. All misfired in the LLM comparison
        # (2026-10-20): "kain putih" read as kain's colour put "Kain adalah lembaran tenunan." into an
        # answer and Ngaben's definition over pangringkes's; Sudra's "beruang hitam" was pinned on
        # Wesia; the Trimurti gods' own names read as moved gods.
        spans = []
        for m, phrase in _mentioned_terms(s, resolver)[0]:
            key = (m.name or "").lower()
            for mm in re.finditer(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", s, re.I):
                spans.append((mm.start(), mm.end(), key if key in members else None))
        for key in members:
            for mm in re.finditer(rf"(?<![\w-]){re.escape(key)}(?![\w-])", s, re.I):
                spans.append((mm.start(), mm.end(), key))

        def inside_longer(sp) -> bool:
            return any(o[0] <= sp[0] and sp[1] <= o[1] and o[1] - o[0] > sp[1] - sp[0] and o[2] != sp[2]
                       for o in spans)
        member_spans = sorted({sp for sp in spans if sp[2] and not inside_longer(sp)})
        if not member_spans:
            continue
        # A member named by a marker (the direction "selatan") has the other markers of that kind as peers, not
        # facts: "(timur, selatan, barat, utara, dan tengah)" listed the directions and "Dewa Iswara di timur ...,
        # Dewa Brahma di selatan ..." paired each with its god, yet only selatan has a card, so every other
        # direction read as moved onto it and selatan's definition replaced the list (Tier B 2026-10-27). Peers
        # bound the members' stretches like members (key ""), and are never judged.
        classes = [c for c in _MARKER_CLASSES if any(markers(key) & c for _, _, key in member_spans)]
        peers = sorted({(mm.start(), mm.end(), "") for c in classes for w in c for mm in _MEMBER_MARKERS[w].finditer(s)
                        if not any(sp[0] <= mm.start() < sp[1] for sp in member_spans)})
        spans += peers
        # the markers are read with the member names and the longer names holding one blanked out, and a
        # colour that is part of any term's name ("kain putih", "bunga tunjung putih") or right after a
        # term ("kain serba putih" is the cloth, not a moved fact: read as one, it put pengerikan kuku's
        # definition over pabersihan mati's steps, V2 run 2026-11-02). God names stay markers outside a
        # member's own name: "berdewa Dewa Mahadewa" is what a panca datu metal is wrongly given.
        masked = list(s)
        for a, b, key in spans:
            if key or any(h[2] and h[0] >= a and h[1] <= b for h in spans):
                masked[a:b] = " " * (b - a)
            else:
                for c in re.finditer(r"\b(?:putih|merah|kuning|hitam)\b", s[a:b], re.I):
                    masked[a + c.start():a + c.end()] = " " * (c.end() - c.start())
        for a, b, key in spans:
            col = key != "" and re.match(r"\s+(?:serba\s+)?(?:putih|merah|kuning|hitam)\b", s[b:], re.I)
            if col:
                masked[b:b + col.end()] = " " * col.end()
        for a, b, _ in peers:
            masked[a:b] = " " * (b - a)
        masked = "".join(masked)
        if not markers(masked):
            continue
        # Each member is checked against the markers that follow it up to the next member; members
        # with nothing but "dan" / commas between them share what follows ("kaenem, kalima, dan kapat
        # ... Dewa Yadnya" gives Dewa Yadnya to all three). Markers before the first member go to the
        # first. "Sasih kadasa baik untuk Dewa Yadnya ..., sasih kaenem baik untuk Dewa Yadnya ...,
        # sasih kalima baik untuk Dewa Yadnya ..." had passed as a whole, kalima's Dewa Yadnya
        # covering kadasa and kaenem (Tier B 2026-10-05).
        starts = []
        for a, b, m in sorted(member_spans + peers, key=lambda x: (x[0], -x[1])):
            if not any(a < e and s0 < b for s0, e, _ in starts):   # one hit per place, the longest
                starts.append((a, b, m))
        named = list(dict.fromkeys(m for _, _, m in starts if m))

        def boundary(lo: int, hi: int) -> Optional[int]:
            # the last , ; : between two members: what comes after it is the next member's own clause
            # ("..., Dewa Brahma di selatan" gives Brahma to selatan, not to the member before)
            cuts = [x.start() for x in re.finditer(r"[,;:]", masked[lo:hi])]
            return lo + cuts[-1] if cuts else None
        groups, cur, lead_end = [], [], 0
        for k, (a, b, m) in enumerate(starts):
            nxt = starts[k + 1][0] if k + 1 < len(starts) else len(s)
            cut = boundary(b, nxt) if k + 1 < len(starts) else None
            end = cut if cut is not None else nxt
            prev_end = starts[k - 1][1] if k else 0
            # (the first member too: "jumlah tingkatnya (tujuh, sembilan, atau sebelas) menandai kedudukan sosial
            # mendiang, serta menyebutkan bahan pembuatannya seperti bambu, kayu, ..." gave bade's tiers to bambu and
            # cut it, leaving "seperti , kayu" -- route audit, Qwen 2026-10-27)
            lead = boundary(prev_end, a)
            lead_from = (lead + 1) if lead is not None else (0 if k == 0 else a)
            cur.append(m)
            seg = markers(masked[b:end]) | markers(masked[max(lead_from, lead_end):a])
            listed = bool(re.fullmatch(r"[\s,;]*(?:(?:dan|serta|atau|maupun)\b[\s,]*)?(?:sasih\s+|wuku\s+)?",
                                       masked[b:nxt], re.I))
            if not cur[:-1]:
                group_from = lead_from if lead is not None else a
            if seg or not listed or k + 1 == len(starts):
                groups.append(([x for x in cur if x], seg, group_from, end))
                cur = []
            lead_end = end

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
            # a sentence that names its subject stands as it is; only a subjectless fragment gets
            # one -- "Dewa brahma: brahma adalah salah satu dewa Trimurti ..." opened an answer
            # (conersation.md 2026-10-07, "clunky")
            names_subject = (re.search(r"^(?:\S+\s+){0,4}?(?:adalah|merupakan|ialah)\b", own, re.I)
                             or any(own.lower().startswith(w) for w in m.split() if len(w) >= 4))
            if own and not own.lower().startswith(m) and not names_subject:
                own = f"{m[:1].upper()}{m[1:]} adalah {own[:1].lower()}{own[1:]}"
        candidate = re.sub(r"[ \t]{2,}", " ", out.replace(s.strip(), own if own and own not in out else "", 1))
        if candidate.strip():
            out = candidate
    return out.strip()


def _first_sentence(text: Optional[Text], limit: int = 300) -> str:
    if not text or text == "Tidak ada definisi langsung":
        return ""
    s = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + " ..."


def _known_sentence(definition: Optional[Text], limit: int = 300) -> str:
    """The definition's first sentence for a "Yang tercatat tentang X: ..." line the user reads: a long
    one ends at a clause boundary rather than mid-clause with "..." -- 41 template misses of the NLU sweep
    ended "... wangsa seseorang turut menentukan ..." (2026-10-19). (_first_sentence's own cut stays: it
    feeds the prompt too.)"""
    s = _first_sentence(definition, limit=10 ** 6)
    if len(s) <= limit:
        return s
    ends = [x.start() for x in _CLAUSE_END_RE.finditer(s, 0, limit) if x.start() >= 60]
    return s[:ends[-1]].rstrip(" ,;:") + "." if ends else _first_sentence(definition, limit)


def _last_bot_utterance(tracker: Tracker) -> Optional[Text]:
    for e in reversed(tracker.events):
        if e.get("event") == "bot" and e.get("text"):
            return e.get("text")
    return None


def _recent_bot_utterances(tracker: Tracker, n: int = 3) -> List[Text]:
    """The bot's last `n` answers, newest first."""
    texts = [e.get("text") for e in reversed(tracker.events) if e.get("event") == "bot" and e.get("text")]
    return texts[:n]


def _previous_user_message(tracker: Tracker) -> Text:
    """The user's message before the current one ("" if none)."""
    texts = [e.get("text") or "" for e in tracker.events if e.get("event") == "user"]
    return texts[-2] if len(texts) >= 2 else ""


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


# a definition's opening subject: "X adalah", "X (...) adalah", "X berarti", "X mengacu pada" (the verb of
# the last two stays: "1. Atma lingga-sarira: mengacu pada atma ...", not "...: Atma Lingga-Sarira mengacu ..."),
# after an opening phrase too: "Dalam konteks kalender Bali, Wayang adalah ..." became "Wayang adalah dalam
# konteks kalender Bali, Wayang adalah ..." (adegan's alike; 2026-10-19)
_DEF_SUBJECT_RE = re.compile(r"(?:(?:dalam|di|pada|menurut|secara)\b[^,.]{0,70},\s*|secara\s+harfiah\s+)?"
                             r"(.{1,80}?)(?:\s*\([^)]*\))?\s+(?:(?:adalah|merupakan|ialah|yaitu)\s+"
                             r"|(?=(?:berarti|mengacu\s+pada|merujuk\s+pada)\s))", re.I)


def _definition_subject(definition: Text, entity_id: Optional[Text], name: Text) -> Optional["re.Match"]:
    """The definition's opening "X adalah ..." when X is the term itself -- its name or an alias, spelled
    as the resolver spells them alike: "Tirtha Pangentas" is tirta pangentas, "Siwa" shiwa, "Panca Maha
    Bhuta" pancamahabutha. Compared with the name alone, the definition template answered "Tirta
    pangentas adalah tirtha Pangentas adalah ..." (NLU sweep 2026-10-19)."""
    m = _DEF_SUBJECT_RE.match(definition or "")
    if not m:
        return None
    entity = get_resolver().by_id.get(entity_id or "") or {}
    # and the name without its class word: "Wishnu adalah ..." is dewa wishnu's ("Dewa wishnu adalah wishnu
    # adalah ...", 2026-10-19; the eight gods of nawa dewata alike)
    names = [name] + list(entity.get("aliases") or []) + ([name.split(" ", 1)[1]] if " " in name else [])
    if _ortho_key(m.group(1)) in {_ortho_key(n) for n in names if n}:
        return m
    # or another class word before the same rest: "Banten Sesayut adalah ..." is ayaban sesayut's ("Ayaban
    # sesayut adalah banten Sesayut adalah ...", LLM comparison 2026-10-20) -- a definition's first sentence
    # defines its own term
    subject = m.group(1).split(" ", 1)
    if " " in name and len(subject) == 2 and _ortho_key(subject[1]) == _ortho_key(name.split(" ", 1)[1]):
        return m
    return None


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
            # don't double the subject ("soda adalah Soda adalah ...", nor "Antah karana sarira
            # adalah antahkarana sarira adalah ...": spaces and hyphens aside; nor "Tirta pangentas adalah
            # tirtha Pangentas adalah ...": another spelling or an alias)
            if (re.sub(r"[\s-]", "", def_text.lower()).startswith(re.sub(r"[\s-]", "", name.lower()))
                    or _definition_subject(def_text, e.get("id"), name)):
                sentences.append(f"{def_text}.")
            else:
                sentences.append(f"{name[:1].upper()}{name[1:]} adalah {def_text[:1].lower()}{def_text[1:]}.")
        elif e.get("facts"):
            sentences.append(". ".join(e["facts"][:3]) + ".")
        for fact in e.get("aspect_facts") or []:
            sentences.append(f"{fact[:1].upper()}{fact[1:]}.")
    return " ".join(sentences)


def _outage_answer(enriched: List[Dict[str, Any]]) -> str:
    """The graph is unreachable, so the terms' edges are missing, not absent: a model told to
    answer from the definitions alone said "tahapan ngaben belum tercatat" and "ngaben hanya
    memiliki satu jenis" (2026-10-07 batch). Say what is known and why it is short."""
    return (_deterministic_answer(enriched) + "\n\n(Catatan: basis data relasi sedang tidak "
            "dapat dihubungi, jadi jawaban ini hanya berisi definisi istilah -- tahapan, sarana, "
            "jenis, dan hubungannya belum bisa ditampilkan. Silakan coba lagi nanti.)")


def _synonym_sentences(enriched: List[Dict[str, Any]], answer: Text) -> List[str]:
    """"<asked name> adalah sebutan lain untuk <name>." for each term the user asked by another
    name. Not for a verb form: "Dihanyutkan adalah sebutan lain untuk nganyut" opened "mengapa abu
    jenazah dihanyutkan ...", conersation.md 2026-10-02. Nor for a description made of everyday
    words, or one the answer already uses: "Jenazah dimandikan adalah sebutan lain untuk nyiramang
    layon", "Hari baik ngaben adalah sebutan lain untuk dewasa ngaben. Dewasa ngaben adalah hari
    baik ..." read clunky, 2026-10-08. Nor a rephrasing of the name itself: "Bade tingkat adalah
    sebutan lain untuk tingkatan bade", 2026-10-08 replay."""
    resolver = get_resolver()
    return [f"{e['asked_as'][:1].upper()}{e['asked_as'][1:]} adalah sebutan lain untuk {e['name']}."
            for e in enriched if e.get("asked_as") and not _VERB_FORM_RE.match(e["asked_as"])
            and not any(_VERB_FORM_RE.match(w) for w in _WORD_RE.findall(e["asked_as"].lower()))
            and not all(_is_everyday_word(w, resolver) or w in _ALIAS_NAME_WORDS
                        or _root(w) in _sentence_roots(e["name"])
                        for w in _WORD_RE.findall(e["asked_as"].lower()))
            and not re.search(rf"\b{re.escape(e['asked_as'])}\b", answer, re.I)]


def _with_note(note: Text, answer: Text) -> str:
    """A note in front of the answer: on its own line before a list ("... sebutan lain untuk nawa
    dewata. 1. Dewa Iswara ..." ran the note into the first item, 2026-10-15), else a space. Not before a
    miss: "Upakara adalah sebutan lain untuk banten. Maaf, banten untuk wayang belum tercatat ..." explained a
    word the answer then says nothing about (7 in the LLM comparison, 2026-10-20)."""
    if not note or re.match(r"\s*Maaf\b", answer):
        return answer
    return note + ("\n" if re.match(r"\s*(?:\d+[.)]|[-*•])\s", answer) else " ") + answer


# Aspect words the extraction LLM sometimes glues onto the term: "apa warna besi"
# -> "warna besi", which resolves to nothing (regression 2026-09-24). kb_resolver's
# strip_modifiers can't take these -- that list is shared with build_kb.py, where
# stripping them would change how the corpus is resolved. A real name that starts
# with one of them still wins: a word is peeled only while the term doesn't resolve.
_ASPECT_WORDS = frozenset("""
warna makna arti fungsi kegunaan guna manfaat tujuan peran peranan letak posisi lokasi
waktu bentuk ukuran panjang ciri lambang simbol filosofi asal syarat cara proses pelaku
""".split())


# Words of a question that point back or ask, with no subject of their own (see _extract_and_resolve)
_POINTER_WORDS = frozenset("""
itu ini tersebut tadi hal maksud kedua pertama ketiga terakhir keduanya ketiganya semuanya saja lagi jelaskan
sebutkan ceritakan uraikan boleh harus wajib perlu jadi begitu gitu terus lalu kok emang memang dong sih tuh
apaan coba kasih tau jelasin dilakukan dilaksanakan diletakkan dilakukannya isi isinya terbuat bahan komponen
nama lainnya sebutan istilah tahapan urutan prosesnya caranya sarana sarananya perlengkapan jenis macam
contoh contohnya tempat tempatnya dimana kapan siapa membuat melakukan dipimpin pelakunya bagian termasuk
upacara panjang berapa kenapa begitu ada aja buat beda bedanya kata katanya lain lainnya hanya melambangkan
dihindari artinya
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


def _is_meta_term(term: str, resolver) -> bool:
    """An extraction result that names no term: an instruction or aspect word (_META_TERMS); a word
    pointing back with no topic to point at -- itu/ini/tersebut/tadi, or an everyday word with "-nya"
    ("katanya", "sarananya", "keduanya"); or the model's own note instead of a term. With no topic, "itu
    apa?" got "tidak menemukan 'itu' ... Mungkin maksud Anda: hitungan galar, ...?" and "jelaskan keduanya"
    "informasi mengenai 'making the pronoun "keduanya" (both of them) unresolvable.' belum tercatat"
    (NLU sweep 2026-10-19)."""
    if term in _META_TERMS:
        return True
    words = term.split()
    if re.search(r"[^\w\s'-]", term) or len(words) > 6:
        return True
    # ("berasnya" stays: beras is a KB name)
    return all(w in _DEICTIC_WORDS or w in _META_TERMS or w in _QUESTION_WORDS
               or (len(w) >= 5 and w.endswith("nya") and w[:-3] not in resolver.surface
                   and _is_everyday_word(w[:-3], resolver))
               for w in words)


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

# Cardinal numbers, digit -> Indonesian word. A number is a quantifier/modifier, not a
# term the KB is missing: "bade tingkat 9" and "bade tingkat sembilan" must behave the same.
# The digit form is never tokenized as a >=4-letter leftover word, so the spelled-out form
# is dropped from the leftover list too (below); and a makna/why question maps either form to
# the number word so the relevant tier definition is kept (_synthesize, meaning_words).
_NUMBER_WORDS = {"1": "satu", "2": "dua", "3": "tiga", "4": "empat", "5": "lima", "6": "enam", "7": "tujuh",
                 "8": "delapan", "9": "sembilan", "10": "sepuluh", "11": "sebelas", "12": "duabelas"}
_NUMBER_WORD_SET = frozenset(_NUMBER_WORDS.values())
_NUMERAL_RE = re.compile(r"\b(\d{1,2}|" + "|".join(_NUMBER_WORDS.values()) + r")\b", re.I)
# "tingkat 9", "bade tingkat sembilan", "tumpang sebelas", "bertingkat 7"
_TIER_Q_RE = re.compile(r"\b(?:tingkat|tumpang|bertingkat)\s+(\d{1,2}|" + "|".join(_NUMBER_WORDS.values()) + r")\b", re.I)


def _tier_numbers(s: Text) -> set:
    s = re.sub(r"\bsalah satu\b", " ", re.sub(r"^\s*\d+[.)]\s*", "", s), flags=re.I)
    return {_NUMBER_WORDS.get(n, n.lower()) for n in _NUMERAL_RE.findall(s)}


def _keep_asked_tier(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A question about one tier gets that tier: "apa makna bade tingkat sembilan" was answered
    with all three, nine in the middle -- "it just misses the question" (conersation.md
    2026-10-07). A sentence or list item naming only other numbers goes (never "salah satu",
    never a list marker), and so does the line announcing a list ("... berbeda-beda:") when one
    item is left. An asked tier the answer never names gets the clause of the first term's
    definition naming it: "apa makna bade tingkat sebelas dan tujuh?" got sebelas only
    (2026-10-08). Never leaves nothing."""
    asked = {_NUMBER_WORDS.get(n, n.lower()) for n in _TIER_Q_RE.findall(user_msg)}
    asked |= {_NUMBER_WORDS.get(n, n.lower()) for n in
              re.findall(r"\b(?:dan|atau|,)\s*(\d{1,2}|" + "|".join(_NUMBER_WORDS.values()) + r")\b", user_msg, re.I)
              } if asked else set()
    if not asked:
        return answer
    parts = [s for s in re.findall(r"[^.!?\n]+[.!?]*", answer) if s.strip()
             and not re.fullmatch(r"\s*\d+[.)]\s*", s)]
    if len(asked) == 1 and any(asked <= _tier_numbers(s) for s in parts):
        drop = [s for s in parts if _tier_numbers(s) and not asked & _tier_numbers(s)]
        if drop and len(drop) < len(parts):
            for s in drop:
                answer = answer.replace(s, "", 1)
            answer = re.sub(r"(?m)^\s*[-*•]\s*$", "", re.sub(r"[ \t]{2,}", " ", answer))   # an emptied bullet
    # markers left by the cut items ("2." alone on a line) go first: counted, they made one item two
    answer = _drop_empty_items(answer)
    if len(asked) == 1 and len(re.findall(r"(?m)^[ \t]*(?:\d+[.)]|[-*•])[ \t]+\S", answer)) == 1:
        # the one item left is no list ("1. Bade bertingkat sebelas ..."), and nothing is announced
        # any more ("Jumlah tingkatan ini memiliki simbolisme yang berbeda-beda:"), whether the
        # other tiers were cut or never written
        answer = re.sub(r"(?m)^[ \t]*(?:\d+[.)]|[-*•])[ \t]+", "", answer, count=1)
        answer = re.sub(r"(?:(?<=[.!?])|^)[ \t]*[^.!?\n]*:[ \t]*\n+", " ", answer, count=1).strip()
    said = set().union(*(_tier_numbers(s) for s in re.findall(r"[^.!?\n]+[.!?]*", answer))) if answer else set()
    definition = (enriched[0].get("definition") or "") if enriched else ""
    for tier in sorted(asked - said):
        clause = next((c.strip() for c in re.split(r"[;.]", definition) if tier in _tier_numbers(c)), None)
        if clause:
            answer = answer.rstrip() + f" {clause[:1].upper()}{clause[1:]}."
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", answer).strip()


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
                # "tingkatan(nya)" beside bade is bade's tiers: "apa itu bade dan kenapa tingkatannya
                # berbeda" got tingkatan upacara (nista/madya/utama, "kemampuan sosial ekonomi")
                # through the fuzzy tier (conersation.md 2026-10-07, again 2026-10-08)
                if (n == 1 and m.via == "fuzzy" and re.fullmatch(r"tingkat(?:an)?(?:nya)?", words[0])
                        and re.search(r"\b(?:bade|wadah|tumpang|bertingkat)\b", " ".join(toks))):
                    m = resolver.resolve("tingkatan bade") or m
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


_LEVEL_IDS = frozenset({"nista", "madya", "utama"})
_LEVEL_Q_RE = re.compile(r"\btingkat(?:an)?(?:nya)?\b", re.I)
# words a level follows when it IS the level: "ngaben utama", "upacara tingkat madya"
_LEVEL_HEADS = frozenset({"upacara", "ngaben", "pengabenan", "pangabenan", "palebon", "yadnya", "banten",
                          "upakara", "tingkat", "tingkatan", "nista", "madya", "utama", "dan", "atau"})


def _mentioned_terms(user_msg: Text, resolver) -> "tuple[List[tuple], List[str]]":
    """KB terms the message itself names, as (Match, surface) in message order --
    longest phrase first, so "tirtha pangentas" wins over "tirtha". The extraction LLM
    sometimes swaps a new term for one from the history ("apa saja sarana upacara yang
    digunakan dalam acara nglungah" came back as "ngaben", 2026-09-29); this scan does
    not look at the history at all. A fuzzy hit counts only on long words.

    Also returns the message's leftover words: the ones no found term covers and that
    are not question / connector words, a question aspect ("diletakkan", "melambangkan")
    or a spelled-out number. With none left, the message is fully explained by its terms.
    A number word is excluded for the same reason a digit is (a digit is never a >=4-letter
    token): "bade tingkat sembilan" named its subject in full just as "bade tingkat 9" did,
    so both skip the extraction LLM instead of the word form alone treating "sembilan" as an
    unexplained term and taking a different, worse path (conersation.md 2026-10-05)."""
    found, toks, used = _scan_terms(user_msg, resolver)
    lone_skip = (_STOPWORDS_ID - {"ngaben"}) | _ASPECT_WORDS | _META_TERMS
    # a class word right before its member names the member, not a second term:
    # "sasih malamasa" is malamasa (a sasih) -- as two terms, "sasih" became the topic
    # and "jadi, kenapa tidak boleh?" was answered about every sasih (2026-09-29).
    # Before a term that is no kind of it ("sasih kliwon") it is the user's wrong premise.
    drop = {a[2].id for a, b in zip(found, found[1:])
            if a[1] == b[0] and b[2].entity.get("broader") == a[2].id}
    drop |= {c.id for c, _, _, _ in _misclassed_terms(user_msg, resolver)}
    # nista / madya / utama name a ceremony level only beside another level word, "tingkat(an)",
    # or the ceremony they grade; elsewhere they are the adjectives "main / middle / low":
    # "apa tujuan utama dari upacara pitra yadnya?" and "apa perlengkapan utama saat upacara
    # nganyut?" were answered with the definition of the utama level (2026-10-07 batch)
    levels = [(i, m) for i, j, m, _ in found if m.id in _LEVEL_IDS and j - i == 1]
    if levels and len({m.id for _, m in levels}) == 1 and not {"tingkat", "tingkatan"} & set(toks):
        for i, m in levels:
            prev = toks[i - 1] if i > 0 else ""
            # "apa saja jenis madya?": a level closing the question after jenis / macam asks for its sub-levels
            # (it found no term, canon sweep 2026-10-28); "jenis utama banten" goes on, so utama is "main" there
            closing_kind = prev in ("jenis", "macam", "pembagian") and i == len(toks) - 1
            if prev not in _LEVEL_HEADS and not closing_kind and resolver.clean_query(user_msg) != toks[i]:
                drop.add(m.id)
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
    # a one-word alias that is the HEAD of its term's name -- "harga" for harga tirtha, the price of tirtha --
    # is any price beside another term unless the rest of the name is said: "berapa harga upacara ngaben" was
    # answered with the holy water's price (plan #16 / 2026-10-27). The modifier aliases stay: "bayi" is jenazah bayi.
    msg_keys = {_ortho_key(t) for t in toks}
    for _, _, m, surf in found:
        name = m.name.lower().split()
        if (len(surf.split()) == 1 and len(name) >= 2
                and _ortho_key(re.sub(r"nya$", "", surf.lower())) == _ortho_key(name[0])
                and not {_ortho_key(w) for w in name[1:]} & msg_keys
                and any(o.id != m.id for _, _, o, _ in found)):
            drop.add(m.id)
    out, seen = [], set()
    for _, _, m, phrase in found:
        if m.id not in seen and m.id not in drop:
            seen.add(m.id)
            out.append((m, phrase))
    leftover = [t for t, u in zip(toks, used)
                if not u and len(t) >= 4 and t not in _SCAN_SKIP and t not in lone_skip
                and t not in _NUMBER_WORD_SET
                and not any(p.search(t) for p in _ASPECT_WORD_RES)]
    return out, leftover


# A follow-up that points back at the topic ("kenapa itu harus dihindari?", "hanya itu
# sarananya?"); checked on the message with its question lead ("apa itu") removed.
_ANAPHOR_RE = re.compile(r"\b(itu|ini|tersebut|tadi|keduanya|begitu|demikian)\b|\b(?!yadnya\b)\w{3,}nya\b",
                         re.I)
# the verb of a question about the topic with its object left out: "kapan dilakukan?" after "apa itu ngaben"
# counted "dilakukan" as a word of its own, named no term and got "tidak menemukan 'kapan dilakukan?'" (the 12
# evaluation categories' conversation, 2026-10-27). Only these: "cuaca hari ini?" is no follow-up.
_ELLIPSIS_VERBS = frozenset({"dilakukan", "dilaksanakan", "diadakan", "diselenggarakan", "dilaksanain", "dilakuin",
                             "diadain", "dibuat", "membuat", "dipakai", "dipake", "digunakan", "berlangsung",
                             "dimulai", "dipimpin", "memimpin", "dipuput", "memuput"})
# "yang pertama / yang terakhir" picks an item of the previous answer -- the extraction
# LLM resolves that, not the topic rule below
_ORDINAL_REF_RE = re.compile(r"\byang\s+(pertama|kedua|ketiga|keempat|kelima|terakhir)\b", re.I)
_DEICTIC_WORDS = frozenset({"itu", "ini", "tersebut", "tadi"})


_TRAILING_POINTER_RE = re.compile(r"\b(?:untuk|buat|bagi|dari|dengan|pada|di|ke|dalam|sama|kayak|seperti|soal|tentang"
                                  r"|oleh|saat|waktu|selama)\s+(?:itu|ini|tersebut|tadi)\s*[?.!]*\s*$", re.I)


def _points_back(user_msg: Text, mentioned: List[tuple], resolver) -> bool:
    """A standalone itu/ini/tersebut/tadi that does not follow a term the message names
    ("bade itu" is that bade; "kapan itu dilakukan, sebelum atau sesudah nyiramang layon?"
    after a turn about pangringkes means pangringkes, live crosscheck T65)."""
    # ... also the last word after a preposition, which clean_query peels as the "X itu?" tail: "banten apa aja yang
    # perlu disiapin buat itu?" after nyiramang layon kept banten alone (human test 2026-11-03)
    if _TRAILING_POINTER_RE.search(user_msg):
        return True
    toks = re.findall(r"[\w-]+", resolver.clean_query(user_msg))
    named = [p.split() for _, p in mentioned]
    for i, t in enumerate(toks):
        # "apa itu X" / "siapa itu X" ask what X is: "siapa itu siwa dan apa hubungannya dengan
        # ngaben" kept bade from the turn before as its first term (2026-10-09 replay)
        if t not in _DEICTIC_WORDS or (i > 0 and toks[i - 1] in ("apa", "siapa")):
            continue
        # (nor one inside a named surface: the scan reads "sulinggih tersebut" as one surface of sulinggih, so after
        # ngaben "apa itu sulinggih tersebut" had put ngaben first, 2026-10-28)
        if not any(len(p) <= i and toks[i - len(p):i] == p or len(p) > 1 and p[-1] == t and toks[i - len(p) + 1:i + 1] == p
                   for p in named):
            return True
    return False


# "yang dibuat undagi", "yang dipakai oleh sulinggih": a thing described by its link to a named term
# (not "yang dimaksud / disebut X": that is X itself)
_DESCRIBED_BY_LINK = (r"\byang\s+(?!dimaksud|disebut|dinamakan|dikenal)di\w+"
                      r"(?:\s+(?:oleh|dalam|untuk|pada|saat|di|ke|dengan))?\s+")


def _linked_earlier_topic(user_msg: Text, mentioned: List[tuple], own_ids: List[str],
                          current_entity: Optional[Text], entity_history: List[str], resolver):
    """What a message pointing back describes by its link to a term it names: the most recent of the topic
    and the remembered terms that an edge joins to that term. "kalau tadi yang dibuat undagi itu apa?" after
    bade and then kajang is bade (Bade dibuat oleh undagi), not kajang (evaluation category 11, 2026-10-28).
    None when the message has no such phrase or no remembered term is linked."""
    msg = resolver.clean_query(user_msg)
    if not any(re.search(_DESCRIBED_BY_LINK + re.escape(p) + r"\b", msg, re.I) for _, p in mentioned):
        return None
    for name in [current_entity] + list(reversed(entity_history or [])):
        m = resolver.resolve(name) if name else None
        if m and m.id not in own_ids and any(r["target_id"] in own_ids for r in _kb_relationships(m.id)):
            return m
    return None


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
    them: the list has "menghindari" but not "dihindari", "gigi" but not "giginya". Its spoken forms too
    (_colloquial_forms)."""
    global _EVERYDAY_ROOTS
    if _EVERYDAY_ROOTS is None:
        _EVERYDAY_ROOTS = frozenset(_root(w) for w in resolver.common_words)
    # (a word of a KB name keeps its own spelling: "kepeng" of uang kepeng is no "kepang", "ngajar" of ngajar-ajar)
    forms = {word} if _ortho_token(word) in resolver.name_tokens else _colloquial_forms(word)
    return any(w in resolver.common_words or _root(w) in _EVERYDAY_ROOTS for w in forms)


def _colloquial_forms(word: str) -> set:
    """The word and the written forms of it as spoken: "-in" for "-kan" / "-i" ("disiapin"), "e" for "a" in the last
    syllable ("denger", "sebenernya"), "ng-" for "meng-" ("ngerti"), a doubled word written with 2 ("nanya2"). "sebenernya
    ngaben itu apa sih? aku sering denger tapi gak ngerti" read three unknown words and went to the LLM, which listed
    every avoided day for a beginner (human test 2026-11-03). Only words of the common-word list count, so a Balinese
    word stays unknown unless it is spelled like an Indonesian one."""
    w = re.sub(r"2$", "", word.lower())
    tail = "nya" if w.endswith("nya") and len(w) > 6 else ""
    base = w[:-3] if tail else w
    bases = {base}
    if base.endswith("in") and len(base) > 5:
        bases |= {base[:-2] + "kan", base[:-2] + "i"}
    if re.match(r"ng[aeiou]", base):
        bases |= {"me" + b for b in set(bases)}
    # (from six letters: Balinese "angen", "idep" are no "angan", "idap")
    bases |= {re.sub(r"e([^aeiou]+)$", r"a\1", b) for b in set(bases) if len(b) >= 6}
    return {word} | bases | {b + tail for b in bases}


# "kenapa orang bali membakar mayat?" (conersation.md 2026-10-02); "mengapa orang meninggal di bali dikremasi"
# named no term and got "Maaf, saya tidak menemukan 'orang meninggal di bali dikremasi'" (plan #16, 2026-10-26)
_BURN_RE =re.compile(r"\b(?:mem|di|ter)?bakar(?:nya|kan)?\b|\bpembakaran\b|\b(?:di|meng?)?kremasi(?:kan|nya)?\b", re.I)
_DEAD_PERSON_RE = re.compile(r"\bmeninggal\b|\bmendiang\b|\balmarhum\w*", re.I)
_NOT = r"(?:tidak|tak|gak|nggak|ngga|enggak|ga|belum)"
_MONEY = r"(?:biaya\w*|dana|duit|uang)"
# a situation term that stands for a corpse word the message also names: the question is about the act
_SITUATION_REPLACES = {t: {"layon", "jenazah", "sawa"} for t in ("nyiramang_layon", "pangringkes", "ngaben")}
# "saat ada yang meninggal", "kalau orang tua wafat"
_WHEN_DIES = (r"\b(?:saat|ketika|waktu|kalau|kalo|jika|bila|begitu|setelah|sesudah|pas)\b[^.?!]{0,30}?"
              r"\b(?:meninggal|wafat|mati|berpulang)\b")
# a family that cannot afford a Ngaben, or a cheaper way to hold one: about ngaben, or the family's own means ("kalo
# keluarganya gak mampu gimana dong" names no term, human test 2026-11-03)
_CANNOT_AFFORD_RE = re.compile(
    r"^(?=.*\b(?:ng|di)?aben)(?=.*(?:\b(?:hemat|murah|irit|terjangkau|kurang\s+mampu|miskin)\b"
    rf"|\b{_NOT}\s+mampu\b|\b{_NOT}\s+(?:ada|punya|cukup)\s+{_MONEY}|\b{_MONEY}\s+(?:ditanggung\s+)?bersama\b))"
    rf"|\b(?:keluarga\w*|orang|warga)\b[^.?!]{{0,40}}?\b(?:(?:{_NOT}|kurang)\s+mampu|miskin)\b", re.I | re.S)
# A situation the user describes in everyday words, and the term the corpus names for it: what the
# bge-m3 meaning search found until 2026-10-13 (removed with Ollama), now decided in code and added
# before the message's own terms. Each pattern follows the corpus's own wording of the case.
_SITUATION_TERMS = (
    # a child's age in days or months, or milk teeth: jenazah bayi's case (its definition holds the tiers).
    # "anak umur 4 bulan meninggal, abis diupacarai perlu dibuatin atma wedana juga nggak?" named atma wedana
    # alone and got "Ya, perlu" -- a child of that age gets ngelungah, not atma wedana (Tier B 2026-10-14)
    # A child who died, with no age: "anak kecil yg meninggal diaben juga gk?" named ngaben alone and got "Tidak, anak
    # kecil tidak diaben ... Sawa Prateka ... penguburan" once and "tidak tercatat" once, while L167-169 / L756-765 give
    # the tiers by age (human test 2026-11-03). Not a child at someone's ngaben ("anak kecil boleh ikut ngaben?")
    ("jenazah bayi", re.compile(r"\b(?:umur|usia|berusia|berumur)\s+\d+\s*(?:hari|bulan)\b"
                                r"|\b(?:anak|bayi)\b[^.?!]*\b\d+\s*(?:hari|bulan)\b|\bgigi susu"
                                r"|\b(?:anak\s+kecil|anak-anak|anak\s+bayi|balita|bocah|bayi)\b[^.?!]{0,40}?"
                                r"\b(?:meninggal|wafat|mati|berpulang|diaben|dibakar|dikubur|dikremasi|diupacarai)\b"
                                r"|\b(?:jenazah|mayat|sawa)\s+(?:anak\s+kecil|anak-anak|balita|bocah)\b"
                                r"|\b(?:meninggal|wafat)\b[^.?!]{0,20}?\bmasih\s+(?:anak\s+kecil|kecil|balita|bayi)\b", re.I)),
    # L25 "Swasta adalah upacara yang dilakukan jika jenazah tidak ditemukan atau meninggal di perantauan":
    # "keluargaku meninggal pas merantau jauh dan jenazahnya gak bisa dibawa pulang. masih bisa diaben gak?"
    ("ngaben svasta", re.compile(rf"\bjenazah\w*\b[^.?!]{{0,40}}?\b{_NOT}\s+(?:(?:bisa|dapat|mungkin|bakal|akan)\s+)?"
                                 r"(?:dibawa\s+pulang|dipulangkan|ditemukan|diketemukan|ketemu|dijangkau)\b"
                                 r"|\bjenazah\w*\s+(?:hilang|lenyap)\b"
                                 r"|\bmeninggal\s+(?:di|pas|saat|waktu|ketika|selama)\s+(?:perantauan|rantau|merantau)\b",
                                 re.I)),
    # L888/L934/L958: a body is "dikubur atau dibakar titip" until the real ngaben; L928: Ngaben is put off
    # for its cost. "belum ada biaya buat ngaben, jenazahnya sementara diapain?"
    ("upacara ngaben titip", re.compile(rf"\b(?:ditunda|menunda|dititip\w*|nitip)\b"
                                        r"|\bbelum\s+(?:bisa|sempat|mampu)\s+(?:segera\s+)?(?:di)?aben\b"
                                        rf"|\b{_NOT}\s+(?:ada|punya|cukup)\s+{_MONEY}[^.?!]*\bjenazah"
                                        # not "jenazah sementara diletakkan di bale" (a stage)
                                        r"|\bjenazah\w*\s+sementara\s+(?:diapa\w*|dikubur\w*|ditanam|disimpan|gimana|"
                                        r"bagaimana)", re.I)),
    # L71 "Keluarga kurang mampu beradaptasi melalui Ngaben Massal"; L928 "Ngaben serentak ... yang
    # biayanya ditanggung bersama". "kalo keluarga gak punya duit banyak, ada cara ngaben yang lebih hemat gak?"
    # Only about ngaben: "apakah banten ini murah" is not
    ("ngaben massal", _CANNOT_AFFORD_RE),
    # ... and L162 "sesuaikan dengan kemampuanmu mengupacarai orang yang meninggal, lakukan dengan upacara nista, madya,
    # dan utama": tingkatan upacara's card says the level is "disesuaikan dengan kemampuan pihak yang menyelenggarakan".
    # "kalau keluarganya gak mampu buat ngaben gimana?" named ngaben alone and got "belum tercatat" (human test 2026-11-03)
    ("tingkatan upacara", _CANNOT_AFFORD_RE),
    # L149 "Bila telah dibongkar dan ditemukan tulang belulangnya" (ngangkid): "kakek udah lama dikubur, pas
    # mau diaben tulangnya diambil gimana?"
    ("ngangkid", re.compile(r"\b(?:dikubur\w*|dipendam|ditanam|terkubur|kuburan\w*|makam\w*)\b[^.?!]{0,60}?"
                            r"\b(?:tulang\w*|digali|dibongkar|diangkat)\b"
                            r"|\b(?:membongkar|bongkar|menggali|gali)\s+(?:kubur\w*|makam\w*)\b", re.I)),
    # L2403-2406 "orang yang baru meninggal, di Bali disebut dengan 'wawu lampus'": "orang baru aja
    # meninggal, langkah pertama keluarganya ngapain?"; its definition is "tahap awal segera setelah
    # kematian", so also the first step when someone dies: "apa yang harus dilakukan keluarga pertama kali
    # saat ada yang meninggal" named no term (NLU sweep 2026-10-19). A time word before "meninggal" keeps
    # out "tahap pertama ... di tempat meninggalnya"
    ("wawu lampus", re.compile(r"\b(?:baru|barusan)\s+(?:saja\s+|aja\s+|sj\s+)?(?:meninggal|wafat|mati|berpulang)\b"
                               rf"|\b(?:pertama(?:\s+kali)?|awal(?:nya)?)\b[^.?!]{{0,50}}?{_WHEN_DIES}"
                               rf"|{_WHEN_DIES}[^.?!]{{0,50}}?\b(?:pertama(?:\s+kali)?|langkah\s+awal|awalnya|"
                               r"terlebih\s+dahulu)\b"
                               r"|\bsegera\s+setelah\s+(?:\w+\s+){0,2}?(?:meninggal|wafat|kematian)\b", re.I)),
    # cleaning the corpse is nyiramang layon -- its Pabersihan Hidup and Mati (as "memandikan jenazah" is, a
    # force_merge): "bagaimana layon dibersihkan" got layon's "digulung dengan kain putih" (NLU sweep
    # 2026-10-19). Not "pembersihan awal jenazah" (wawu lampus). The corpse word goes (_SITUATION_REPLACES)
    # Purifying it too: "bagaimana jenazah disucikan" got jenazah's facts of every stage in one unordered list (V2 run
    # 2026-11-02); nyiramang layon's card is "upacara memandikan dan menyucikan jenazah"
    # Bathing it in everyday words: "yang mandiin jenazah itu namanya apa?" kept jenazah as the topic, and the next
    # turn's "banten apa aja yang perlu disiapin buat itu?" lost the rite the answer had named (human test 2026-11-03)
    ("nyiramang layon", re.compile(r"\b(?:layon|jenazah|mayat|sawa)\w*\s+(?:\w+\s+){0,2}?(?:(?:di|mem)?bersihkan"
                                   r"|(?:di)?(?:me)?n?(?:s|ny)ucikan|(?:di|me)?mandi(?:kan|in))\b"
                                   r"|\b(?:mem|pem)bersih(?:kan|an)\s+(?:layon|jenazah|mayat|sawa)\b"
                                   r"|\b(?:menyucikan|penyucian|pensucian|mensucikan)\s+(?:layon|jenazah|mayat|sawa)\b"
                                   r"|\b(?:(?:di|me)?mandi(?:kan|in)|pemandian)\s+(?:layon|jenazah|mayat|sawa)\b",
                                   re.I)),
    # L852-855 "kain pangringkesan digulungkan ke tubuh jenazah ... Pangringkes luar dibuat dengan tikar": wrapping
    # the corpse is pangringkes, not layon's own facts
    ("pangringkes", re.compile(r"\b(?:layon|jenazah|mayat|sawa)\w*\s+(?:\w+\s+){0,2}?(?:di|mem)?(?:bungkus|gulung|"
                               r"ringkes)(?:kan)?\b"
                               r"|\b(?:mem|pem)(?:bungkus|gulung)(?:kan|an)?\s+(?:layon|jenazah|mayat|sawa)\b", re.I)),
    # "bagaimana prosesi jenazah" asked the rite a body goes through, and got jenazah's facts of every stage in one
    # unordered list (V2 run 2026-11-02): Ngaben's stages answer it
    ("ngaben", re.compile(r"\b(?:prosesi|rangkaian|urutan)\s+(?:upacara\s+)?(?:layon|jenazah|mayat|sawa)\b", re.I)),
    # L34 "Nuduk Galih: Pengumpulan sisa-sisa tulang (abu) setelah pembakaran", L135 "Sisa pembakaran berupa
    # tulang/galih dipungut ...": "abis pembakaran, sisa tulangnya diapain?" named no term and got "tidak menemukan
    # 'sisa tulang'" (2026-10-27; meaning search had found tulang belulang, the bones of a buried body). Not bones
    # dug up from a grave (ngangkid, above), nor the ashes, which nganyut floats away, nor where the bones go: "sisa
    # tulang setelah kremasi dibawa ke mana" got "tempat nuduk galih belum tercatat"
    # L2637/L3660 "Adanya perbedaan itu disebabkan oleh Desa, Kala, Patra dan Desa Mawa Cara ... esensi atau makna
    # ... tetap sama": "apakah ngaben di semua desa sama" named ngaben alone (the 12 evaluation categories,
    # 2026-10-27). About a rite done differently from place to place
    ("desa kala patra", re.compile(r"\b(?:semua|setiap|tiap|seluruh|masing-masing|tiap-tiap|antar)\s+(?:desa|daerah|"
                                   r"tempat|wilayah|banjar|kabupaten)\b"
                                   r"|\b(?:berbeda-beda|beda-beda|bervariasi|variasi)\b"
                                   r"|\b(?:desa|daerah)\s+(?:lain|yang\s+berbeda)\b", re.I)),
    # ulah pati's card "Ulah pati berarti bunuh diri" (web, approved 2026-10-29) and L162, Sang Hyang Yama's ngaben "asal
    # mati dengan benar (tidak salah ulah pati)": "orang yang meninggal karena bunuh diri boleh diaben gak?" named ngaben
    # alone and got "tidak tercatat" once that card existed (Tier B 2026-10-30)
    ("ulah pati", re.compile(r"\b(?:mem)?bunuh\s+diri\b", re.I)),
    ("nuduk galih", re.compile(r"^(?!.*\b(?:ke\s*mana|di\s*mana|dikemana\w*)\b)(?=.*(?:"
                               r"\b(?:abis|habis|setelah|sesudah|selesai)\s+(?:\w+\s+){0,2}?(?:pembakaran|dibakar|bakar|"
                               r"kremasi|dikremasi)\b[^.?!]{0,50}?\b(?:tulang\w*|galih\w*)"
                               r"|\b(?:sisa\w*\s+tulang\w*|tulang\w*\s+sisa\w*)\b[^.?!]{0,50}?"
                               r"\b(?:pembakaran|dibakar|kremasi|diapa\w*|gimana|bagaimana)\b))", re.I | re.S)),
)


@dataclass
class _Scan:
    """What the message itself names, read once by _extract_and_resolve and shared by its steps."""
    msg: Text
    resolver: Any
    mentioned: List[tuple]                    # (match, surface) of each term the message names (_mentioned_terms)
    leftover: List[str]                       # the message's words no term explains
    turns: List[str]                          # the recent user turns, this one last (recent_user_turns)
    entity_history: List[str]
    current_entity: Optional[str]


def _extract_and_resolve(
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    user_msg: Text,
    entity_history: List[str],
    current_entity: Optional[str] = None,
    announce_miss: bool = True,
    allow_llm: bool = True,
) -> "tuple[List[Dict[str, Any]], List[str], List[str]]":
    """Steps 1-3: LLM term extraction -> kb_resolver -> Neo4j + curated-content
    enrichment. Shared by ActionGraphRAG and ActionLLMFallback so a genuine
    follow-up that trips the fallback classifier still gets KB-grounded, and by
    ActionTemplateAnswer with `allow_llm=False`: no extraction call, only the message's
    own terms and the remembered topic.

    Returns (enriched, unresolved, found_names). `enriched` is [] on total failure;
    when `announce_miss` is True (ActionGraphRAG), a resolver-level explanatory
    message has already been dispatched in that case -- when False
    (ActionLLMFallback), the caller is expected to fall through to its own
    ungrounded answer instead.

    The steps: scan the message's own terms (a name only partly known is a miss), the extraction LLM when the
    words alone cannot give the terms (_needs_extraction, _extracted_terms), resolve its terms (_resolve_terms),
    add the terms the message names or describes (_message_terms), drop what the history carried in
    (_without_carried_terms), order them (_in_message_order), put the topic first (_topic_first), add the words of
    a word-meaning question (_with_word_parts), then the graph and the curated content (_enrich) and the note on a
    term not found (_note_missing_terms).
    """
    neo4j_conn.failed = False   # this turn's graph queries start clean (see Neo4jConnection)
    turns = recent_user_turns(tracker, limit=4)
    resolver = get_resolver()
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    s = _Scan(user_msg, resolver, mentioned, leftover, turns, entity_history, current_entity)
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
    raw_terms = _extracted_terms(s) if allow_llm and _needs_extraction(s) else []

    # Step 2: kb_resolver maps each free-text term to a canonical KB id --
    # exact name/alias -> force_merge -> modifier-strip -> rapidfuzz.
    # (No early return on an empty LLM list any more: the message's own terms
    # (Step 2b) and the topic fallback below still apply.)
    asked_as: Dict[str, str] = {}
    typed_as: Dict[str, str] = {}
    matches, unresolved = _resolve_terms(s, raw_terms, asked_as, typed_as)
    own, replaced = _message_terms(s)
    for m, surface in mentioned:
        _note_spelling(s, m, surface, asked_as, typed_as)
    matched_ids = {m.id for m in matches}
    for m in own:
        if m.id not in matched_ids:
            matches.append(m)
            matched_ids.add(m.id)
    own_order = [m.id for m in own]
    anaphor = _refers_back(s, own_order)
    matches = _without_carried_terms(s, matches, own_order, anaphor, replaced)
    matches = _in_message_order(s, matches, own, own_order)
    matches = _topic_first(s, matches, own_order, anaphor)
    matched_ids = {m.id for m in matches}   # before the cap: a word-meaning part counts these too
    matches = matches[:4]
    if _WORD_MEANING_RE.search(user_msg):
        matches = _with_word_parts(s, matches, matched_ids)

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

    enriched = _enrich(matches, asked_as, typed_as)
    if unresolved:
        _note_missing_terms(dispatcher, s, enriched, unresolved, announce_miss)
    found_names = [row["name"] for row in enriched]
    return enriched, unresolved, found_names


def _asks_a_question(user_msg: Text) -> bool:
    """A question mark, a specific question word or an aspect word."""
    return bool("?" in user_msg or _SPECIFIC_Q_RE.search(user_msg) or _aspect_families(user_msg))


def _needs_extraction(s: _Scan) -> bool:
    """Whether the extraction LLM runs: only for what the message's own words cannot give."""
    user_msg, mentioned, leftover, resolver = s.msg, s.mentioned, s.leftover, s.resolver
    prior_turns = s.turns[:-1] if len(s.turns) > 1 else []
    # The extraction LLM is for what the words alone cannot give: a pronoun or ellipsis
    # ("kenapa itu harus dihindari?"), a relation/comparison question whose second term
    # may come from the history, or a word the scan could not place. A message fully
    # explained by the terms it names ("apa itu ngaben", "apa makna banten") skips it:
    # its extra terms would be filtered out in Step 2b anyway, and it cost a full LLM
    # call on every such turn (2026-09-30).
    # ... and never for a message that names nothing and points back at nothing: no term, no turn before
    # it, only question, aspect and pointing words ("apa maknanya?", "yang kedua itu apa maksudnya"). The
    # call had nothing to resolve: 67 of the 1,864 NLU examples paid ~600 tokens each for "tidak menangkap
    # istilah", and "yang kedua" was then searched as a term ("Mungkin maksud Anda: kedua mata jenazah")
    # (LLM comparison 2026-10-20). A content word ("orang meninggal di bali dikremasi") still gets the call.
    nothing_to_extract = (not mentioned and not prior_turns and not s.entity_history and not s.current_entity
                          and not {w for w in _asked_specifics(user_msg, []) if not w.isdigit()
                                   and not {w, re.sub(r"nya$", "", w)} & (_ASPECT_WORDS | _POINTER_WORDS)})
    pointing = bool(_ANAPHOR_RE.search(resolver.clean_query(user_msg)))
    linking = bool(_RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg))
    asks = _asks_a_question(user_msg)
    # Nor for a message that names its term and whose other words are everyday ones, with nothing pointing back
    # and no relation or comparison: of 108 such calls in the recorded Qwen runs, one added a term the scan had
    # not found -- the whole of a part named with it ("berapa tingkat bade untuk raja": bade), which keeps the
    # call. ~600 tokens each, also before code answers ("ngaben dilakukan kapan"; route audit 2026-10-27)
    names_whole = any(
        f["predicate"] == "BAGIAN_DARI" and get_content().entity_name.get(f["object_id"])
        and re.search(rf"(?<![\w-]){re.escape(get_content().entity_name[f['object_id']])}(?![\w-])", surface, re.I)
        for m, surface in mentioned for f in get_content().facts_by_subj.get(m.id, []))
    only_everyday = all(_is_everyday_word(w, resolver) or w in _ASPECT_VOCAB for w in leftover)
    # and a follow-up that names nothing and says only an ellipsis verb ("kapan dilakukan?"): the topic answers it
    bare_follow_up = (not mentioned and bool(s.current_entity) and not pointing and not linking and asks
                      and set(leftover) <= _ELLIPSIS_VERBS)
    return not nothing_to_extract and not bare_follow_up and bool(
        not mentioned or (leftover and not (only_everyday and not names_whole)) or pointing or linking)


def _extracted_terms(s: _Scan) -> List[str]:
    """Step 1: the terms the extraction LLM finds, each grounded in the conversation; the raw message when the
    call fails."""
    user_msg, resolver, turns, entity_history, current_entity = (
        s.msg, s.resolver, s.turns, s.entity_history, s.current_entity)
    prior_turns = turns[:-1] if len(turns) > 1 else []
    history_block = "\n".join(f'- "{t}"' for t in prior_turns) or "(tidak ada)"
    entities_block = ", ".join(entity_history) or "(tidak ada)"
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
        resolved_text = _llm_invoke([{"role": "user", "content": resolve_prompt}], "extract")[0].strip().lower()
        raw_terms = [t.strip() for t in resolved_text.split(",") if t.strip()]
        # Deterministic backstop for the instruction above -- see _META_TERMS.
        raw_terms = [t for t in raw_terms if not _is_meta_term(t, resolver)]
        # The extraction LLM sometimes returns a word nobody said ("apa saja
        # unsurnya" -> "unsurlunya", conersation.md 2026-09-24). Keep a term only
        # if one of its words is close to a word actually present in the
        # conversation (or an entity already discussed) -- coreference
        # substitutions pass, inventions don't.
        said = set(re.findall(r"\w+", " ".join(
            turns + entity_history + [current_entity or ""]).lower()))
        raw_terms = [t for t in raw_terms if _term_is_grounded(t, said)]
    except Exception as e:
        # LLM down/unreachable/timed out/rate-limited -- degrade instead of crashing the
        # action (every intent path runs through this function). No
        # coreference/ellipsis handling in this mode, but kb_resolver can still
        # match a self-contained question directly off the raw message.
        print(f"LLM term-extraction error: {e}")
        raw_terms = [user_msg.strip().lower()] if user_msg.strip() else []
    return raw_terms


def _note_spelling(s: _Scan, m, term: str, asked_as: Dict[str, str], typed_as: Dict[str, str]) -> None:
    """How the user wrote a resolved term, when it is not the KB name: another name for it (asked_as) or a
    misspelling (typed_as)."""
    user_msg, resolver = s.msg, s.resolver
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
        if m.via == "strip":
            # only the name's own words are its spelling, not the modifiers the match stripped: "beda ngaben
            # massal" was replaced whole, and "apa beda ngaben massal dan ngaben svasta" reached Qwen as "apa
            # ngaben massal svasta" ("perbedaan pangringkes", "nama lain jenazah", "bade tingkat sembilan" lost
            # their asked word too; the 12 evaluation categories, 2026-10-27)
            core = " ".join(w for w in t.split() if w not in resolver.strip_modifiers)
            if not core or core == n or core not in user_msg.lower():
                return
            term = core
        typed_as.setdefault(m.id, term)


def _resolve_terms(s: _Scan, raw_terms: List[str], asked_as: Dict[str, str],
                   typed_as: Dict[str, str]) -> "tuple[list, List[str]]":
    """The extracted terms resolved to KB entities (matches, each once) and the ones that did not resolve."""
    matches = []
    unresolved = []
    for term in raw_terms:
        term = _widen_to_named_term(_peel_aspect_words(term, s.resolver), s.msg, s.resolver)
        m = s.resolver.resolve(term)
        if m and m.id not in {x.id for x in matches}:
            matches.append(m)
            _note_spelling(s, m, term, asked_as, typed_as)
        elif not m:
            unresolved.append(term)
    return matches, unresolved


def _message_terms(s: _Scan) -> "tuple[list, set]":
    """Step 2b: the terms the message names, then those it implies: the whole of a part named with it, a term it
    describes, ngaben for a burned body, a described situation, dewasa ngaben for a day, the priced cards of a
    price question, the ceremony levels. -> (terms, the ids a situation replaces)"""
    user_msg, mentioned, leftover, resolver = s.msg, s.mentioned, s.leftover, s.resolver
    # Step 2b: the terms the message itself names -- a deterministic scan of its words
    # plus resolve_many()'s "X dan Y" split -- are added even when the extraction LLM
    # dropped or replaced them (e.g. "bade dan naga banda"; "... acara nglungah" -> ngaben).
    own: list = []
    for m in [mm for mm, _ in mentioned] + resolver.resolve_many(user_msg, limit=4):
        if m.id not in {x.id for x in own}:
            own.append(m)
    # a part matched loosely from its whole's name and a qualifier is that part AND the whole: "bade
    # tingkat 11" is tingkatan bade (a part of bade) and the bade itself. "apakah wangsa sudra boleh
    # menggunakan bade tingkat 11?" lost bade -- and its usage norms -- once the extraction LLM stopped
    # adding a bare "bade" beside it (qwen3.8, Tier B 2026-10-13)
    for m, surface in mentioned:
        if m.via in ("exact", "alias"):
            continue
        for f in get_content().facts_by_subj.get(m.id, []):
            whole = get_content().entity_name.get(f["object_id"], "")
            if (f["predicate"] == "BAGIAN_DARI" and whole and f["object_id"] not in {x.id for x in own}
                    and re.search(rf"(?<![\w-]){re.escape(whole)}(?![\w-])", surface, re.I)):
                hit = resolver.resolve(whole)
                if hit and hit.id == f["object_id"]:
                    own.insert([x.id for x in own].index(m.id) + 1, hit)
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
    if (_BURN_RE.search(user_msg)
            and (any(m.id == "jenazah" for m in own) or not own and _DEAD_PERSON_RE.search(user_msg))
            and not any(m.entity.get("type") == "RITUAL_KEMATIAN" for m in own)):
        hit = resolver.resolve("ngaben")
        if hit:
            own.insert(0, hit)
    # a described situation names its term (_SITUATION_TERMS), first in the table's order
    situated = [resolver.resolve(name) for name, rx in _SITUATION_TERMS if rx.search(user_msg)]
    # ... but not a part of a rite the message names when it asks that rite's stages: there the situation is the setting
    # and the stage list holds it. "kakek saya baru meninggal minggu lalu, keluarga mau ngaben. tahapannya apa aja ya?"
    # got wawu lampus ("baru meninggal", BAGIAN_DARI ngaben) alone instead of Ngaben's stages (human test 2026-11-03)
    if "tahapan" in _aspect_families(user_msg):
        named_ids = {m.id for m, _ in mentioned}
        situated = [h for h in situated if h and not any(
            f["predicate"] == "BAGIAN_DARI" and f["object_id"] in named_ids
            for f in get_content().facts_by_subj.get(h.id, []))]
    for hit in reversed([h for h in situated if h]):
        if not any(m.id == hit.id for m in own):
            own.insert(0, hit)
    replaced = set().union(*(_SITUATION_REPLACES.get(h.id, set()) for h in situated if h))
    own = [m for m in own if m.id not in replaced]
    # "hari apa yang harus dihindari untuk ngaben" asks about dewasa ngaben, which holds the
    # allowed and forbidden days -- the message never names it (live crosscheck T96)
    if _asks_about_day(user_msg) and not any(m.id == "dewasa_ngaben" for m in own):
        hit = resolver.resolve("dewasa ngaben")
        if hit:
            # after a month or day the message names, which stays the topic: "kenapa sasih malamasa tidak boleh
            # dilaksanakannya ngaben" made dewasa ngaben the topic, and "kenapa itu harus dihindari?" got its list
            # of avoided days (Tier B, plan #16, 2026-10-26)
            content = get_content()
            days = [i for i, m in enumerate(own) if m.id in ("purnama", "tilem") or any(
                content.is_kind_of(m.id, c) for c in ("sasih", "wuku", "wewaran"))]
            own.insert(days[-1] + 1 if days else 0, hit)
    # "berapa biaya ngaben" asks what the KB says a Ngaben costs: krematorium's card has the rupiah packages and
    # "Ngaben mandiri tradisional minimal 20 juta rupiah", harga tirtha the priest's punia -- neither named, so the
    # answer said no price is recorded (2026-10-27). The cards that name the asked term and state a price follow it.
    if own and _PRICE_Q_RE.search(user_msg):
        own += [h for h in _priced_terms(own[0]) if all(m.id != h.id for m in own)]
    # "apa saja tingkatan dalam upacara ngaben" asks for nista/madya/utama, which ngaben is
    # "dilakukan berdasarkan"; the alias "tingkatan ngaben" only matches side by side, and the
    # question got ngaben's eight stages as its "tingkatan" (2026-10-08 batch). Not for a term
    # with no such edge: atma wedana's tingkatan are its kinds, bade's its tiers.
    if (_LEVEL_Q_RE.search(user_msg) and not any(m.id == "tingkatan_upacara" for m in own)
            and any(f["object_id"] == "tingkatan_upacara"
                    for m in own for f in get_content().facts_by_subj.get(m.id, []))):
        hit = resolver.resolve("tingkatan upacara")
        if hit:
            own.insert(0, hit)
    return own, replaced


def _refers_back(s: _Scan, own_order: List[str]) -> bool:
    """A pointing-back word (itu, tersebut, -nya ...), or no term named and only the topic's own card's words."""
    # (clean_query peels "apa itu" but not "siapa itu", whose "itu" points at nothing)
    anaphor = bool(_ANAPHOR_RE.search(re.sub(r"^\s*siapa\s+itu\b", "", s.resolver.clean_query(s.msg))))
    # ... or quotes the topic's own card ("karunia seperti apa yang dimaksud?" after anugerah raja)
    return anaphor or bool(not own_order and _quotes_topic(s.leftover, s.current_entity, s.resolver))


def _without_carried_terms(s: _Scan, matches: list, own_order: List[str], anaphor: bool,
                           replaced: set) -> list:
    """The terms that belong to this question: not one the extraction LLM carried over from the history when
    the message names its own, not one a situation replaces, not the generic lontar of a source question."""
    user_msg, resolver = s.msg, s.resolver
    # A term the extraction LLM carried over from the history is not part of a question
    # that names its own term(s): "apa itu nglungah" after a turn about ngaben came back
    # as [ngaben, ngelungah], "apa itu tujuan ngaben" after moksa as [ngaben, moksa]
    # (2026-09-29). The one exception is a relation/comparison question that names only
    # one term -- "apa hubungannya dengan jenazah" after a turn about sawa needs sawa.
    needs_history = len(own_order) == 1 and bool(
        _RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg))
    # A message that names no term but has a word that is no everyday word ("thanks", "siapa
    # itu Pewdiepie", "apa itu bahasa kwai") asks about something the KB lacks. The extraction
    # LLM still returned the last topic, which the grounding check accepts (any word of the
    # history counts), so each was answered about jenazah / nyiramang layon (conersation.md
    # 2026-10-02). Without a word pointing back, only terms the message itself says count.
    unknown_word = (not own_order and not anaphor and not _ORDINAL_REF_RE.search(user_msg)
                    and any(not _is_everyday_word(w, resolver) for w in s.leftover))
    if (own_order and not needs_history) or unknown_word:
        said = set(re.findall(r"\w+", user_msg.lower()))
        matches = [m for m in matches if m.id in own_order or any(
            _term_is_grounded(n, said, _GENERIC_NAME_WORDS)
            for n in [m.name] + list(m.entity.get("aliases") or []))]
    matches = [m for m in matches if m.id not in replaced]
    # "lontar apa yang menjelaskan ngaben": the generic lontar node is the question word,
    # not a term (T94); the sources come from _source_facts
    if "sumber" in _aspect_families(user_msg) and len(matches) > 1:
        matches = [m for m in matches if m.id != "lontar"]
    return matches


def _in_message_order(s: _Scan, matches: list, own: list, own_order: List[str]) -> list:
    """The message's own terms first, in its order, a class word after the term it belongs to."""
    # the message's own terms first, in its order: enriched[0] is the asked term
    matches.sort(key=lambda m: own_order.index(m.id) if m.id in own_order else len(own_order))
    # ... but a class another named term counts or is a kind of is that term's word, after it: "sebutkan semua dewa dan
    # arahnya dalam dewata nawa sanga" made the generic dewa card the topic once dewa had one (2026-10-28). Named terms
    # only: the price rule adds ngaben massal, a kind of ngaben, and "berapa biaya ngaben" lost ngaben itself to the cap
    # of four below (Tier B 2026-10-30)
    named_ids = {m.id for m, _ in s.mentioned}
    if len(named_ids) > 1:
        sub = {m.id for t in own if t.id in named_ids for m, _ in _topic_class_words(s.mentioned, t, s.msg)}
        if sub:
            matches.sort(key=lambda m: m.id in sub)
    return matches


def _topic_first(s: _Scan, matches: list, own_order: List[str], anaphor: bool) -> list:
    """The topic rule: the remembered topic first when the message points back at it."""
    user_msg, mentioned, leftover, resolver, current_entity = (
        s.msg, s.mentioned, s.leftover, s.resolver, s.current_entity)
    # A follow-up about the topic puts it first: one that names no term and points back or
    # says nothing else ("jadi, kenapa tidak boleh?" after a malamasa question went to
    # ngaben, a term the extraction LLM took from the history -- T30/T31), and one that
    # names a term plus a standalone "itu" (T65). Until then only an empty match list fell
    # back to the topic.
    # ("no leftover" needs a question: a bare "ok" is not about the topic again)
    topic_now = resolver.resolve(current_entity) if current_entity else None
    # ("nama 9 dewa tersebut": a class the topic's card names does not stop "tersebut" pointing at the topic)
    off_card = ([x for x in mentioned if x not in _topic_class_words(mentioned, topic_now, user_msg)] if topic_now
                else mentioned)
    if current_entity and not _ORDINAL_REF_RE.search(user_msg) and (
            (not own_order and (anaphor or ((not leftover or set(leftover) <= _ELLIPSIS_VERBS)
                                            and _asks_a_question(user_msg))))
            or (own_order and (_points_back(user_msg, off_card, resolver)
                               # every named term is the topic's class word, and "-nya" points back: "sebutkan semua
                               # arah dan dewa yang menguasainya" after nawa dewata. It needs a named term: a term found
                               # by a situation pattern named none, and "orang baru aja meninggal, langkah pertama
                               # keluarganya ngapain?" put the turn before's ngangkid first (Tier B 2026-10-30)
                               or mentioned and not off_card and anaphor and not _WHAT_IS_RE.search(user_msg)))):
        topic = resolver.resolve(current_entity)
        if own_order:
            # described by its link to the named term: the remembered term so linked, which may be older
            topic = _linked_earlier_topic(user_msg, mentioned, own_order, current_entity, s.entity_history,
                                          resolver) or topic
        else:
            remembered = topic
            topic = _rite_topic(user_msg, topic, s.entity_history, resolver)
            if topic is not remembered:
                # the thing it replaces came from the history only: the message never said it
                matches = [m for m in matches if not remembered or m.id != remembered.id]
        if topic and own_order and _TRAILING_POINTER_RE.search(user_msg) and get_content().kinds_of(matches[0].id):
            # a class asked for the topic, "banten apa aja yang perlu disiapin buat itu?": the class first, as in "banten
            # apa saja untuk nyiramang layon", so that _class_filter keeps its kinds (human test 2026-11-03)
            matches = [m for m in matches if m.id != topic.id]
            matches.insert(1, topic)
        elif topic:
            matches = [topic] + [m for m in matches if m.id != topic.id]
            # what the topic costs is in the cards that state its price, as for "berapa biaya ngaben" (_message_terms):
            # "mahal gak biayanya?" about ngaben got "biaya ngaben belum tercatat" (human test 2026-11-03)
            if not own_order and _PRICE_Q_RE.search(user_msg):
                matches += [h for h in _priced_terms(topic) if all(m.id != h.id for m in matches)]
            # "kapan dilakukan?" about Ngaben asks its days, as "kapan ngaben dilakukan" does (_WHEN_NGABEN_RE)
            if (not own_order and topic.id in _DAY_TOPICS and _TOPIC_WHEN_RE.search(user_msg)
                    and not any(m.id == "dewasa_ngaben" for m in matches)):
                hit = resolver.resolve("dewasa ngaben")
                if hit:
                    matches.insert(1, hit)
    return matches


# what only a rite has: how long it takes from start to end, what holding it costs and whether the family can afford it,
# who leads it, its stages. Not "harga" or "mahal" alone, which a thing has too
_RITE_Q_RE = re.compile(rf"\bberapa\s+lama\b|\bdari\s+awal\s+(?:sampai|sampe|hingga|smp|ke)\b|\bbiaya\w*|\bongkos\w*"
                        rf"|\bdana(?:nya)?\b|\b(?:{_NOT}|kurang)\s+mampu\b|\bdipimpin\b|\bsiapa\b[^.?!]*\b(?:me)?mimpin\b"
                        rf"|\b(?:me)?mimpin\b[^.?!]*\bsiapa\b|\btahapan(?:nya)?\b|\brangkaian(?:nya)?\b", re.I)


def _rite_topic(user_msg: Text, topic, entity_history: List[str], resolver):
    """The topic a follow-up that names nothing is about: the remembered one, unless it asks what only a rite has
    and the remembered term is a thing -- then the most recent rite of the conversation. "mahal gak biayanya?" after
    "terus abunya dikemanain?" (a turn after three about ngaben) got "harga atau biaya abu belum tercatat", and "kalo
    keluarganya gak mampu gimana dong" opened with abu's definition (human test 2026-11-03)."""
    content = get_content()
    if (not topic or not _RITE_Q_RE.search(user_msg) or content.entity_type.get(topic.id) in _STAGE_TYPES
            # a thing with a price of its own keeps a price question
            or _PRICE_Q_RE.search(user_msg) and (_priced_terms(topic)
                                                 or _PRICE_IN_DEF_RE.search(_definition_text(topic.entity)))):
        return topic
    for name in reversed(entity_history or []):
        m = resolver.resolve(name)
        if m and m.id != topic.id and content.entity_type.get(m.id) in _STAGE_TYPES:
            return m
    return topic


def _with_word_parts(s: _Scan, matches: list, matched_ids: set) -> list:
    """A word-meaning question: also each word of a multi-word term on its own."""
    resolver = s.resolver
    # "arti kata (dasar) pitra yadnya": also look up each word of a multi-word
    # term on its own (exact/alias only -- a fuzzy hit on a single word is noise).
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
    return matches[:6]


def _enrich(matches: list, asked_as: Dict[str, str], typed_as: Dict[str, str]) -> List[Dict[str, Any]]:
    """Step 3: each resolved term as the pipeline uses it -- its graph edges as sentences, its definition and
    facts from the curated KB, its other names and how the user wrote it."""
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
            # "sulinggih/griya" read as one name ("Gria juga dikenal sebagai sulinggih/griya", T51).
            # A list or a phrase with a conjunction is a surface the term resolves from, not
            # another name for it: "Pancamahabutha juga dikenal dengan istilah mahabutha atau
            # unsur" (alias "unsur, elemen atau mahabutha"), "Adegan juga dikenal dengan sebutan
            # adegan dan pengawak" (the corpus's "alat upakara (adegan dan pengawak)"), 2026-10-07.
            # Nor a phrase holding the name itself: "Jenazah juga dikenal sebagai jenazah mendiang,
            # jenazah seseorang, dan samping jenazah" (2026-10-15)
            "aliases": [a for a in (m.entity.get("aliases") or [])
                        if len(a.split()) <= 4 and "/" not in a and "," not in a
                        and not re.search(r"\s(?:dan|atau|serta)\s", a)
                        and not re.search(rf"(?<![\w-]){re.escape(m.name)}(?![\w-])", a, re.I)][:8],
        })
    return enriched


def _note_missing_terms(dispatcher: CollectingDispatcher, s: _Scan, enriched: List[Dict[str, Any]],
                        unresolved: List[str], announce_miss: bool) -> None:
    """Log the terms that did not resolve; a relation or comparison question missing one of its terms says so."""
    user_msg, resolver = s.msg, s.resolver
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

    def composed_of_found(t: str) -> bool:
        # a found term plus everyday words or other KB names: "tingkatan nista madya" (nista,
        # madya and utama were all found) and "ngaben sawa wedana" got "tidak ditemukan"
        # notes above complete answers (2026-10-07 batch). Without a found term in it the
        # phrase is a miss: "mata angin" (two everyday words) still gets the note.
        ws = re.findall(r"[\w-]+", t.lower())
        if not any(w in found_words for w in ws):
            return False
        return all(w in found_words or _is_everyday_word(w, resolver)
                   or getattr(resolver.resolve(w), "via", None) in ("exact", "alias") for w in ws)
    typed = [t for t in unresolved if t.lower() in user_msg.lower()
             and not any(t.lower() in (e["name"].lower(), e.get("typed_as") or "") for e in enriched)
             and not (len(t.split()) == 1 and _is_everyday_word(t.lower(), resolver))
             and not composed_of_found(t)
             and t.lower() not in misclassed]
    if typed and (_RELATION_Q_RE.search(user_msg) or _COMPARE_Q_RE.search(user_msg)):
        # the synthesis model is told too, or it relates the missing term anyway
        # ("Sasih kliwon adalah salah satu jenis pitra yadnya")
        enriched[0]["missing_terms"] = typed
        if announce_miss:
            dispatcher.utter_message(
                text=f"(Catatan: '{', '.join(typed)}' tidak ditemukan, melanjutkan dengan yang lain.)"
            )


# Question aspect -> the family of edge AND text-only attribute predicates relevant to
# it (families: kb_content.PREDICATE_FAMILIES, shared with kb_lint). On a hub node
# (ngaben has ~30 edges) the small model otherwise mixes kinds up -- e.g. listing
# ngaben's TYPES (ngaben massal, sawa prateka) as its "sebutan lain" (other names).
# Attributes ("kawangen melambangkan sikap amusti karana", "besi berwarna hitam")
# are shown ONLY when their aspect is asked -- never for a plain "apa itu X", where
# unrelated facts read as tangents (conersation.md 2026-09-24).
# ("X terbagi menjadi apa saja" too: read as "menjadi apa", a how-question, it went to the LLM, which made
# up how jun pere "terbagi" -- NLU sweep 2026-10-19)
_KINDS_Q_RE = re.compile(r"\bjenis\b|\bmacam\b|\bragam\b|\bcontoh|\btipe\b|\bklasifikasi(?:nya)?\b|\bpembagian(?:nya)?\b"
                         r"|\b(?:ter|di)bagi\s+(?:menjadi|atas|dalam|ke)\b", re.I)
# "bagaimana alur prosesi ngaben", "ceritakan proses ngaben dari awal sampai akhir" ask for
# the stages too: as "cara" alone they got an invented sequence (T38/T103/T104)
_PROCESS_Q_RE = re.compile(r"\balur\b|\bprose(s|si)\b|\blangkah|\bdari awal (sampai|hingga)\b", re.I)
_STAGES_Q_RE = re.compile(r"\btahap|\burutan\b|\brangkaian\b|" + _PROCESS_Q_RE.pattern, re.I)
# the words that ask for the stages themselves, not just name a process (see _aspect_families)
_STAGE_WORD_RE = re.compile(r"\btahap|\burutan\b|\brangkaian\b|\balur\b|\blangkah|\bdari awal (sampai|hingga)\b", re.I)
# one stage, not the list: "apa tahapan berikutnya", "apa prosesi awal", "tahapan terakhir" got the
# whole corpus order appended (2026-10-08 batch)
_ONE_STAGE_Q_RE = re.compile(r"\b(?:berikutnya|selanjutnya|sesudahnya|setelahnya|sebelumnya|pertama|terakhir)\b"
                             r"|\b(?:setelah|sesudah|sebelum)\b|\bawal\b(?!\s+(?:sampai|hingga))", re.I)
# which days are allowed / avoided: dewasa ngaben holds them (T96). Also "kapan waktu yang tepat
# untuk melaksanakan upacara ngaben?", answered "tidak tercatat" (2026-10-07 batch).
# "kapan ngaben dilakukan" is a day question too: Ngaben's own waktu fact is a condition, "Ngaben mensyaratkan
# sawa" (Tier B 2026-10-13); its days are dewasa ngaben's
# "nenek meninggal pas sasih kadasa, terus kapan ngabennya bisa dilaksanain?" -- the "-nya" and "bisa"
# forms missed it, and the answer named no good month (2026-10-15)
_WHEN_NGABEN_RE = re.compile(r"\bkapan\s+(?:(?:sebaiknya|baiknya|biasanya|waktu|hari|upacara|bisa|boleh)\s+){0,2}"
                             r"(?:ngaben|pengabenan|pangabenan|palebon)(?:nya)?\b"
                             r"|\b(?:ngaben|pengabenan|pangabenan|palebon)(?:nya)?\s+"
                             r"(?:(?:sebaiknya|biasanya|bisa|boleh)\s+)?"
                             r"(?:dilakukan|dilaksanakan|diadakan|dilaksanain|dilakuin|diadain)\s+kapan\b", re.I)
# "sasih apa yang baik untuk ngaben" named sasih and ngaben and went to the LLM (the 12 evaluation categories,
# 2026-10-27); only for Ngaben / Pitra Yadnya, whose days dewasa ngaben gives ("sasih apa saja yang baik untuk atma
# wedana" has its own context, Tier B); "sasih kaenem baik untuk apa" asks about one month and stays out
_DAY_Q_RE = re.compile(r"\bhari\b(?:\s+\w+){0,6}?\s+(?:baik|buruk|dihindari|pantang|dilarang|tidak boleh|cocok|tepat)\b"
                       r"|\b(?:sasih|wuku)\s+apa\b(?:\s+\w+){0,4}?\s+(?:baik|buruk|dihindari|pantang|dilarang|tidak boleh|"
                       r"cocok|tepat|bagus)\b(?=.*\b(?:ngaben\w*|pengabenan|pangabenan|palebon|pitra\s+yadnya)\b)"
                       r"|\bwaktu\s+(?:yang\s+)?(?:tepat|baik|cocok|terbaik)\b|" + _WHEN_NGABEN_RE.pattern, re.I)
# a when-question about the remembered topic: Ngaben's days are dewasa ngaben's (_good_days_answer). Not its order
# ("kapan ... setelah apa") -- the stages' order answers that
_DAY_TOPICS = frozenset({"ngaben", "pitra_yadnya"})
_TOPIC_WHEN_RE = re.compile(r"^(?!.*\b(?:setelah|sesudah|sebelum|menjelang|tahap\w*|urutan)\b).*"
                            r"(?:\bkapan\b|\bhari\s+apa\b|\bwaktu(?:nya)?\s+(?:yang\s+)?(?:tepat|baik)\b)", re.I | re.S)
_PERMIT_WORD_RE = re.compile(r"\b(?:boleh|bolehkah|dilarang|pantang|bisa|dihindari|cocok)\b", re.I)


_PRICE_Q_RE = re.compile(r"\b(?:harga\w*|biaya\w*|ongkos\w*|tarif\w*|mahal\w*)\b", re.I)
# a definition stating a price: an amount of money, or a cost word ("biaya", the priest's "punia") -- not a count
# of coins ("11 kepeng" in a kawangen)
_PRICE_IN_DEF_RE = re.compile(r"\b(?:biaya|ongkos|tarif|harga|punia)\b|\d[\d.,]*\s*(?:juta|ribu|rupiah)\b", re.I)


def _priced_terms(term, cap: int = 4) -> list:
    """The KB terms whose definition names `term` (a resolver Match) by any surface and states a price, best first
    (an amount of money before a cost word alone)."""
    content, resolver = get_content(), get_resolver()
    names = [n for n in [term.name] + list(term.entity.get("aliases") or []) if len(n) >= 4]
    if not names:
        return []
    named = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b", re.I)
    hits = []
    for eid, definition in content.entity_def.items():
        if eid == term.id or not _PRICE_IN_DEF_RE.search(definition) or not named.search(definition):
            continue
        money = bool(re.search(r"\d[\d.,]*\s*(?:juta|ribu|rupiah|kepeng)\b", definition, re.I))
        hits.append((not money, eid))
    out = []
    for _, eid in sorted(hits):
        hit = resolver.resolve(content.entity_name.get(eid, eid))
        if hit and hit.id == eid:
            out.append(hit)
    return out[:cap]


def _asks_about_day(user_msg: Text) -> bool:
    """_DAY_Q_RE, or a permission word with "hari X" where X is a word of dewasa ngaben's own
    definition: "apakah upacara ngaben boleh dilakukan saat hari pasah?" named no KB term
    beside ngaben, and the model called pasah "hari libur umat Islam ... Nabi Musa" (2026-10-07
    batch). The day names come from the KB, so "boleh dibakar dalam 42 hari" stays out."""
    if _DAY_Q_RE.search(user_msg):
        return True
    low = user_msg.lower()
    if not _PERMIT_WORD_RE.search(user_msg):
        return False
    content = get_content()
    words = set(_WORD_RE.findall((content.best_definition("dewasa_ngaben") or "").lower())) - _STOPWORDS_ID
    m = re.search(r"\bhari\s+([a-z]+)", low)
    if m:
        return m.group(1) in words
    # a day named without "hari", about Ngaben: "ngaben pas purnama boleh gak?" got no day rules and answered
    # "Tidak ada larangan yang tercatat" although dewasa ngaben avoids purnama (#1862, LLM comparison 2026-10-20).
    # Only a calendar day the rules name: purnama, tilem, a sasih, wuku or wewaran day.
    if not re.search(r"\bngaben\w*|\bpengabenan\b|\b(?:mem|di)?bakar\b", low):
        return False
    resolver = get_resolver()
    for w in set(_WORD_RE.findall(low)) & words:
        hit = resolver.resolve(w)
        if hit and hit.via in _NAMED_VIA and (hit.id in ("purnama", "tilem") or any(
                content.is_kind_of(hit.id, c) for c in ("sasih", "wuku", "wewaran"))):
            return True
    return False
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
    # what X is made of / contains / comes with ("soda dilengkapi apa?", "apa isi punjung"); "dibuat dari",
    # "tersusun dari", "bagian-bagian X", "apa yang dibutuhkan untuk membuat X" found no aspect, so an honest
    # "not recorded" was swapped for the bare definition as if "apa itu X" had been asked (#767, #808, #811,
    # #784, LLM comparison 2026-10-20)
    (re.compile(r"dilengkapi|kelengkapan|\bisi(nya)?\b|berisi|terdiri|terbuat|\bbahan|komponen|\bunsur"
                r"|\bdibuat\s+dari\b|\btersusun\b|\bbagian-bagian(?:nya)?\b|\bdibutuhkan\s+untuk\s+membuat\b", re.I),
     "komposisi"),
    # "menyimbolkan" holds "nyimbol", not "simbol" (#288 "babelonyoh itu menyimbolkan apa")
    (re.compile(r"\bmakna|\blambang|melambangkan|simbol|menyimbolkan|disimbolkan|filosofi", re.I), "simbol"),
    # "dari mana diperoleh" (T92: tirta pangentas is made at the gria or at home)
    # "lekesan dimasukkan ke dalam apa" (Tier B 2026-10-13)
    (re.compile(r"di ?mana|\bletak(nya)?\b|diletakkan|ditaruh|ditempatkan|ke ?mana|dari ?mana|\bposisi|"
                r"\bdimasukkan\b|\bditempelkan\b", re.I),
     "lokasi"),
    (re.compile(r"\bkapan\b|hari apa|berapa hari|hari ke|\bwaktu(nya)?\b|saat apa|\bsyarat|"
                r"hari baik|\bdewasa\b|padewasan|"
                # "setelah ngaben selesai upacara lanjutan apa": its DILAKUKAN_SETELAH edges, not
                # all of ngaben's (it answered "nguyeg", 2026-10-08 batch)
                r"\b(?:ke)?lanjutan(?:nya)?\b|\bdilanjutkan\b", re.I), "waktu"),
    (_DAY_Q_RE, "waktu"),
    # "siapa saja" + a noun asks for a list, like "apa saja": "siapa saja nama 9 dewa tersebut" got "Maaf,
    # ... belum tercatat" as nawa dewata's "doer" (live 2026-10-15); "siapa saja yang ..." asks who
    # "yang mimpin X siapa" (everyday "memimpin") had no aspect, so its miss said "hal tersebut"
    (re.compile(r"\bsiapa\s+(?:saja\s+)?yang\b|\bsiapa\s+saja\s*(?:[?.!]|$)|oleh siapa|dipimpin|dilakukan oleh"
                r"|\bpelaku|\b(?:me)?mimpin\b|\b(?:me)?muput\b|\bdipuput\b|\bpemuput\b", re.I), "pelaku"),
    (re.compile(r"\bwarna|\bbentuk(nya)?\b|berbentuk|ukuran|\bpanjang(nya)?\b|\bciri|bertingkat|"
                r"berapa (tingkat|panjang|banyak|lapis|kali|buah|lembar)", re.I), "ciri"),
    # ("apa tugas pemangku dalam ngaben": a person's duty, read as nlu_fallback by the 2026-10-27 model)
    (re.compile(r"\bfungsi|kegunaan|\bguna(nya)?\b|untuk apa|\bbuat apa\b|\btujuan|\bbertujuan|manfaat|\bperan(an|nya)?\b|"
                r"\btugas(nya)?\b|"
                r"\bakibat|\bdampak|\bmengapa\b|\bkenapa\b|\balasan", re.I), "fungsi"),
    # a reason is as often a meaning as a purpose: with fungsi alone, "kenapa bade ada yang
    # bertingkat 11" lost "bade menunjukkan status sosial seseorang" (MENUNJUKKAN, simbol)
    # and rule 21 then said the reason was not recorded (2026-09-30)
    (_WHY_Q_RE, "simbol"),
    # what is lost without it is what it is for, and what it means (see _CONSEQUENCE_Q_RE)
    (_CONSEQUENCE_Q_RE, "fungsi"),
    (_CONSEQUENCE_Q_RE, "simbol"),
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
# "karena": jenazah bayi's tiers each say why ("karena ia masih dinilai suci murni"), yet "kenapa
# jenazah bayi tidak boleh dibakar?" opened with "Maaf, alasannya belum tercatat" (Tier B 2026-10-05)
# "lambang": prasawya "dianggap sebagai lambang proses pradana ... gerak ke atas", yet "kenapa harus
# diputar ke kiri" opened with "Maaf, alasannya belum tercatat" (Tier B 2026-10-08)
_MEANING_IN_DEF_RE = re.compile(r"\b(?:melambangkan|menggambarkan|bermakna|maknanya|menyimbolkan|"
                                r"karena|sebab|lambang)\b", re.I)
# also a bare passive, 4+ letters after "di" as in `_root`: "Diaben adalah sebutan lain untuk ngaben" opened "orang
# yang meninggal karena bunuh diri boleh diaben gak?" (Tier B 2026-10-27), "Dilarung ... nganyut" (2026-10-08);
# the KB's nouns dipan and diksa are shorter
_VERB_FORM_RE = re.compile(r"^(?:di|me[mny]?|meng|meny|ber|ter)\w{3,}(?:kan|i)$|^di\w{4,}$", re.I)
# the topic words a description of a term is built from ("hari baik ngaben", "memandikan
# jenazah"): with everyday words they make a description, not another name
_ALIAS_NAME_WORDS = frozenset({"ngaben", "jenazah", "sawa", "layon", "upacara", "mayat"})
_TELL_Q_RE = re.compile(r"\b(?:ceritakan|uraikan|jelaskan|terangkan)\b", re.I)
_YES_NO_Q_RE = re.compile(r"^\s*(?:jadi,?\s+)?apakah\b", re.I)
# ... and in everyday speech: "anak umur 4 bulan ... perlu dibuatin atma wedana juga nggak?", "ngaben
# pas purnama boleh gak?", "ngabennya tetep bisa jalan gak?" (reasoning test 2026-10-09/12), also typed with no
# question mark: "pabersihan mati tanpa sorohan kecil bisa gak" kept "Tidak, ... tidak dapat dilakukan tanpa sorohan
# kecil karena keduanya tidak memiliki hubungan" (V2 run 2026-11-02)
_CASUAL_YES_NO_RE = re.compile(r"\b(?:gak|nggak|ngga|enggak|ga|ndak|tidak|belum)\s*\?"
                               r"|\b(?:gak|nggak|ngga|enggak|ndak)\s*[.!]?\s*$"
                               r"|\batau\s+(?:tidak|nggak|gak|enggak|belum)(?:nya)?\b", re.I)


def _whether_question(user_msg: Text) -> bool:
    return bool(_YES_NO_Q_RE.search(user_msg) or _CASUAL_YES_NO_RE.search(user_msg))


# "apa itu X", "apa yang dimaksud dengan X", "pengertian X", "jelaskan X", "X itu apa"
_OVERVIEW_Q_RE = re.compile(r"\bapa itu\b|\bapa yang dimaksud\b|\bpengertian\b|\bdefinisi\b|\bjelaskan\b|"
                            r"\bterangkan\b|\bceritakan\b|\buraikan\b|\bitu apa\b|\bsebenarnya\b", re.I)
_KIND_PREDICATES = frozenset({"TERMASUK_JENIS", "MEMILIKI_JENIS"})
# a definition that itself states contents ("terbuat dari daun lontar", "berisi aksara")
_CONTENTS_IN_DEF_RE = re.compile(r"\bberisi|\bterdiri (?:dari|atas)|\bterbuat dari|\bdibuat dari|\bbahan|\bisinya|"
                                 r"\bdilengkapi|\bdiisi", re.I)


# "kelengkapan" asked of what is no thing means the sarana it uses (_equipment_as_sarana)
_EQUIPMENT_Q_RE = re.compile(r"\bkelengkapan(?:nya)?\b", re.I)
# what something is made of, not its members ("unsur", "terdiri")
_MATERIAL_Q_RE = re.compile(r"\bbahan(?:nya)?\b|terbuat|dibuat dari|\bisi(?:nya)?\b|berisi", re.I)


def _equipment_as_sarana(user_msg: Text, enriched: List[Dict[str, Any]]) -> Text:
    """The question as the pipeline reads it: "kelengkapan" of a ceremony, a stage or a person -- no thing
    with contents -- is its "perlengkapan", the sarana it uses. Read as contents, the aspect filter kept
    no edge of a ceremony (which has no contents) and rule 23 said nothing was recorded (2026-10-19)."""
    if (enriched and _EQUIPMENT_Q_RE.search(user_msg) and not _MATERIAL_Q_RE.search(user_msg)
            and not re.search(r"\bunsur|terdiri|komponen", user_msg, re.I)
            and get_content().entity_type.get(enriched[0]["id"]) not in COMPOSITE_TYPES):
        return re.sub(r"\bkelengkapan", "perlengkapan", user_msg, flags=re.I)
    return user_msg


def _contents_question(user_msg: Text) -> bool:
    return bool(_CONTENTS_Q_RE.search(user_msg) and not _MEMBERS_Q_RE.search(user_msg)
                and not _KINDS_Q_RE.search(user_msg))


def _aspect_families(user_msg: Text) -> List[str]:
    # once each: two patterns may name one family ("akibat" is fungsi, and so is a consequence
    # question), and callers compare the list ("families == ['jenis']")
    families = list(dict.fromkeys(fam for pattern, fam in _ASPECT_FAMILIES if pattern.search(user_msg)))
    if not families and _FUNGSI_WEAK_RE.search(user_msg):
        families = ["fungsi"]
    if not families and _HOW_RE.search(user_msg):
        families = ["cara"]
    # "proses(i) X" often only names the act: "kapan prosesi nyiramin dilaksanakan", "di mana
    # prosesi memandikan jenazah", "apa hubungan ngaben dan proses moksha" got the stage list
    # appended (2026-10-08 batch). With another aspect asked, or in a relation question, and no
    # stage word, it asks for neither the stages nor the how.
    if (not _STAGE_WORD_RE.search(user_msg)
            and (any(f not in ("tahapan", "cara") for f in families) or _RELATION_Q_RE.search(user_msg))):
        families = [f for f in families if f not in ("tahapan", "cara")]
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


def _sarana_by_place(entity_ids: List[str]) -> Dict[str, List[tuple]]:
    """{entity id: [(place id, place name, sorted items)]}: what the ceremony itself and each of
    its stages uses, the ceremony first."""
    rows = neo4j_conn.query(_STAGE_SARANA_QUERY, {"entity_ids": entity_ids, "use_in": list(_SARANA_USE_IN),
                                                  "use_out": list(_SARANA_USE_OUT)})
    by_id: Dict[str, List[tuple]] = {}
    for r in rows:
        items = sorted(set(r["items"]))
        if items:
            by_id.setdefault(r["id"], []).append((r["place_id"], r["place"], items))
    for eid, places in by_id.items():
        places.sort(key=lambda p: p[0] != eid)
    return by_id


def _stage_sarana_facts(enriched: List[Dict[str, Any]]) -> None:
    """Set e["sarana_facts"]: one sentence per ceremony/stage listing what it uses."""
    by_id = _sarana_by_place([e["id"] for e in enriched])
    for e in enriched:
        e["sarana_facts"] = []
        for pid, place, items in by_id.get(e["id"], []):
            # the ceremony's own items are named as such -- labelled like a stage, the model
            # skipped them and "sarana ngaben" came back without bade (Tier B 2026-09-29)
            where = (f"{e['name']} itu sendiri (bukan hanya tahapannya)" if pid == e["id"]
                     else f"{place} (bagian dari {e['name']})")
            e["sarana_facts"].append(f"Sarana yang digunakan dalam {where}: {', '.join(items)}")


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
    # "... buat itu?": the topic, which _topic_first puts after the class
    if not terms and _TRAILING_POINTER_RE.search(user_msg):
        terms = enriched[1:2]
    if not terms:
        return None

    def is_member(eid: Optional[str]) -> bool:
        return bool(eid) and eid != cls["id"] and content.is_kind_of(eid, cls["id"])

    def for_term(r: Dict[str, Any]) -> bool:
        # what is used before or after the term is not used for it: "banten pamegat DIGUNAKAN_SEBELUM
        # pabersihan mati" became "Banten yang dipakai saat Pabersihan Mati adalah banten pamegat" (NLU
        # sweep 2026-10-19)
        return not re.search(r"(?:^|_)(?:SEBELUM|SETELAH|SESUDAH|MENJELANG)(?:_|$)", r.get("relation") or "")

    reach: set = set()
    names: List[str] = []
    for t in terms:
        reach |= {r.get("target_id") for r in t.get("relationships") or [] if for_term(r)}
        names += [t["name"]] + (t.get("aliases") or [])
        names += [content.entity_name.get(k, "") for k in content.kinds_of(t["id"])]
        # the term's items: members of the class only
        t["relationships"] = [r for r in t.get("relationships") or []
                              if is_member(r.get("target_id")) and for_term(r)]
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

    def named_for_term(d: Text) -> bool:
        # the definition names the term, not as what it comes before or after ("... sebelum upacara
        # Pabersihan Mati" is banten pamegat's)
        return any(not re.search(r"\b(?:sebelum|setelah|sesudah|menjelang)\s+(?:(?:upacara|acara|tahap)\s+)?$",
                                 d[max(0, m.start() - 30):m.start()])
                   for p in name_res for m in p.finditer(d))

    def tied(r: Dict[str, Any]) -> bool:
        d = (content.best_definition(r.get("target_id")) or "").lower()
        return r.get("target_id") in reach or named_for_term(d)

    # the class's kinds tied to the term; its other facts are not what the list asks
    cls["relationships"] = [r for r in cls.get("relationships") or []
                            if r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing") and tied(r)]
    cls["sarana_facts"] = []
    # nor a definition sentence naming 3+ of the kinds left out: sasih's "berurutan: Kasa, Karo,
    # Katiga, ..." would read as the answer to "sasih apa saja yang baik untuk atma wedana" -- in the
    # prompt and in the definitions-only fallback alike (2026-10-14)
    kept = {r.get("target_id") for r in cls["relationships"]}
    prefix = re.compile(rf"^{re.escape(cls['name'].lower())}\s+")
    left_out = [re.compile(rf"\b{re.escape(prefix.sub('', content.entity_name.get(k, k).lower()))}\b", re.I)
                for k in content.kinds_of(cls["id"]) if k not in kept]
    if cls.get("definition"):
        cls["definition"] = " ".join(s for s in _sentences(cls["definition"])
                                     if sum(bool(p.search(s)) for p in left_out) < 3)
    return cls["name"], [t["name"] for t in terms]


# "tahap kelima dari delapan tahapan pelaksanaan Ngaben" -> 5
_ORDINALS = {"pertama": 1, "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5, "keenam": 6,
             "ketujuh": 7, "kedelapan": 8, "kesembilan": 9, "kesepuluh": 10}
_STAGE_NUM_RE = re.compile(r"\btahap(?:an)?\s+(?:ke-?\s*(\d+)|(" + "|".join(_ORDINALS) + r"))\b", re.I)


def _rite_surfaces(entity_id: Optional[str]) -> List[str]:
    """A rite's name and aliases, to find it after a stage number."""
    entity = get_resolver().by_id.get(entity_id or "") or {}
    return [n for n in [entity.get("name")] + list(entity.get("aliases") or []) if n and len(n) >= 4]


def _stage_number(definition: Optional[Text], rite: Optional[str] = None) -> Optional[int]:
    """The stage number a definition states for the rite `rite` (an entity id): a "tahap ke-N" followed by
    dari / dalam / upacara / rangkaian / pelaksanaan (or a stop) whose own clause -- the words after it up to
    , ; : . or "dan" -- names that rite ("tahap keempat dari delapan tahapan pelaksanaan Ngaben", "tahap keenam
    upacara Nyiramang Layon"). Every number in the definition is tried; with no rite, the first such one.
    "tahap pertama penyucian jenazah" numbers the two purification steps, not a rite's stages: as its first
    number, nyiramang layon's stages read "1. Nedunan layon dan pabersihan hidup ... 2. Pabersihan mati ...
    6. Memunjung", and "tahap kedua penyucian jenazah dalam rangkaian Ngaben" made pabersihan mati ngaben's
    stage 2 (plan #19 batch 2, 2026-10-28)."""
    text = definition or ""
    surfaces = _rite_surfaces(rite) if rite else []
    for m in _STAGE_NUM_RE.finditer(text):
        clause = re.split(r"[,;:.]|\bdan\b", text[m.end():m.end() + 90], maxsplit=1)[0]
        if not re.match(r"\s*(?:\([^)]*\)\s*)?(?:$|[)]|(?:dari|dalam|upacara|rangkaian|pelaksanaan)\b)",
                        clause, re.I):
            continue
        if surfaces and not any(re.search(rf"(?<![\w-]){re.escape(s)}(?![\w-])", clause, re.I) for s in surfaces):
            continue
        return int(m.group(1)) if m.group(1) else _ORDINALS[m.group(2).lower()]
    return None


def _numbered_stages(e: Dict[str, Any]) -> List[tuple]:
    """(number, name) of e's stages whose definitions number them, in order."""
    content = get_content()
    out = []
    for r in e.get("relationships") or []:
        if r.get("relation") == "BAGIAN_DARI" and not r.get("outgoing"):
            n = _stage_number(content.best_definition(r.get("target_id")), e.get("id"))
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
            return _stage_number(content.best_definition(r.get("target_id")), e.get("id")) or 99
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
            # the item's head is what it lists: "1. Mamukur: ... jenis Atma Wedana ... meliputi
            # Ngajum, Pangutpetian, Amrethi Karana, dan Pralina" is a kind although its body names
            # stages (Tier B 2026-10-08)
            head = re.match(r"\s*(?:\d+[.)]|[-*•])\s*\**([^:*\n]+?)\**\s*:", line)
            if not kind_only(head.group(1) if head else line):
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
    some kinds ("sasih yang cocok ...") must not get the others appended. A kind counts as named by any surface the KB
    knows: "Brahmana, Ksatria, Wesia, dan Sudra" got "Jenis wangsa lainnya yang tercatat: wangsa sudra jadma" (Tier B on
    Qwen, 2026-10-26 and 10-29), "Sudra" being that kind's alias."""
    if not enriched or _NUMERAL_SET_RE.match(enriched[0].get("name") or ""):
        return answer
    e = enriched[0]
    kinds = []
    for r in e.get("relationships") or []:
        if r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing") and r.get("target") not in kinds:
            kinds.append(r["target"])
    if len(kinds) < 3:
        return answer
    said, named = _ortho_key(answer), _named_in(answer)
    missing = [k for k in kinds if _ortho_key(k) not in said and k.lower() not in named]
    if missing and (len(kinds) - len(missing)) * 2 >= len(kinds):
        # its own paragraph after a list: glued to the last bullet it read as that item's ("* ... bentuk Singa.
        # Jenis wangsa lainnya yang tercatat: wangsa sudra jadma.", Tier B 2026-10-26)
        after_list = re.search(r"(?m)^[ \t]*(?:[-*•]|\d+[.)])\s.*\Z", answer.rstrip())
        answer = (answer.rstrip() + ("\n\n" if after_list else " ")
                  + f"Jenis {e['name']} lainnya yang tercatat: {', '.join(missing)}.")
    return answer


def _complete_aspect_facts(answer: Text, enriched: List[Dict[str, Any]], limit: int = 2) -> Text:
    """A follow-up asking an aspect of the same term ("apa maknanya hal tersebut?" after "apa itu
    pradaksina") gets the asked term's aspect facts the answer left out: told not to repeat its
    previous answer, the model gave one recalled sentence and dropped "pradaksina melambangkan
    turunnya purusa meresapi pradana ..." (2026-10-08) -- "how is this one more elaborate than the
    previous one" (conersation.md 2026-10-07). At most `limit`."""
    if not enriched:
        return answer
    said = _sentence_roots(answer)
    adds = []
    for fact in enriched[0].get("aspect_facts") or []:
        roots = _sentence_roots(fact)
        if len(adds) < limit and roots and len(roots & said) * 2 < len(roots):
            adds.append(fact.strip().rstrip("."))
            said |= roots
    if not adds:
        return answer
    # said once: a second fact on the same subject joins the first, not a second "Selain itu," (human test 2026-11-03)
    subject = re.compile(rf"^{re.escape(enriched[0]['name'])}\s+", re.I)
    text = f"Selain itu, {adds[0][:1].lower()}{adds[0][1:]}"
    for fact in adds[1:]:
        text += f" dan {subject.sub('', fact)}" if subject.match(fact) and subject.match(adds[0]) else f". {fact}"
    return answer.rstrip() + f" {text}."


def _complete_other_names(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A pure "sebutan lain" answer names every other name the asked term's edges record:
    "apa sebutan lain untuk ngaben" gave mreteka sawa, atiwa-tiwa and malebuang and left out
    palebon, the one edge pointing the other way ("palebon adalah sebutan halus untuk ngaben"),
    on a fresh load (Tier B 2026-10-08)."""
    if not enriched:
        return answer
    e, said = enriched[0], _ortho_key(answer)
    names = list(dict.fromkeys(r["target"] for r in e.get("relationships") or []
                               if r.get("relation") in PREDICATE_FAMILIES["sebutan_lain"] and r.get("target")))
    missing = [n for n in names if _ortho_key(n) not in said]
    if missing:
        answer = answer.rstrip() + f" Sebutan lain yang juga tercatat: {', '.join(missing)}."
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


# A sentence that IS the answer's verdict or says the asked thing is not recorded: "Tidak ada hubungan
# langsung antara X dan Y yang tercatat ...", "Mengenai makna daksina, ... belum tercatat di basis data".
# The cutting guards spare it, or cut only the part that is not the verdict: in the LLM comparison
# (2026-10-20/21) they removed it from 27-28 of 254 answers a run, which then described both terms and
# never answered (qwen_problems_2026-10-26.md, section 1).
_VERDICT_RE = re.compile(
    r"\b(?:belum|tidak)\s+(?:tercatat|tercantum|dicatat)\b"
    r"|\btidak\s+ada\s+(?:\w+\s+)?(?:hubungan|kaitan|keterkaitan|larangan|aturan|ketentuan|keterangan|catatan"
    r"|kewajiban)\b"
    r"|\btidak\s+(?:memiliki|mempunyai)\s+(?:\w+\s+)?(?:hubungan|kaitan|keterkaitan)\b"
    r"|\btidak\s+dapat\s+ditentukan\b", re.I)

# What a why-question may say besides the term without asking about anything else: why it is done, used,
# needed or avoided. Any other word is what the question is about -- "menangis" in "kenapa tidak boleh
# menangis saat ngaben", "disebut" in "kenapa disebut tirtha", "bertingkat 11" -- and a reason fact of the
# term (its purpose) does not answer it, so the honest "alasannya belum tercatat" stays (2026-10-26).
_WHY_GENERIC_ROOTS = frozenset(_root(w) for w in """
kenapa mengapa alasan alasannya harus perlu wajib ada dilakukan dilaksanakan diadakan digunakan dipakai
dipergunakan dihindari hindari boleh dilarang larangan buruk pantang melakukan melaksanakan upacara yadnya
ngaben pengabenan bali umat hindu orang sasih wuku hari dan atau saat pada untuk dalam sarana""".split())


def _why_about_term_only(user_msg: Text, enriched: List[Dict[str, Any]], avoid_q: bool) -> bool:
    """A why-question about the term itself: one term (or a why-avoided question, whose terms' judging
    definitions are the reasons), and no word asking about something else. "kenapa disebut tirtha" asks
    about the name, which no purpose of tirtha explains. Ngaben beside the term is the setting, not a
    second subject ("mengapa uang kepeng digunakan dalam sarana ngaben")."""
    if len([e for e in enriched if e.get("id") != "ngaben" and e.get("name") != "ngaben"]) > 1 and not avoid_q:
        return False
    if re.search(r"\b(?:disebut|dinamakan|dinamai|bernama|namanya|istilah(?:nya)?)\b", user_msg, re.I):
        return False
    # nor the words that named the term ("jenazah dimandikan", a force_merge surface of nyiramang layon) or the Ngaben
    # setting after an order word ("sebelum dibakar"): "kenapa jenazah dimandikan sebelum dibakar?" kept "Maaf, alasannya
    # belum tercatat" above both stages' meanings (2026-10-30). A bare burn word stays asked: "kenapa mapendem dibakar"
    ids = {e.get("id") for e in enriched}
    named = {w for m, surface in _mentioned_terms(user_msg, get_resolver())[0] if m.id in ids
             for w in re.findall(r"\w+", surface.lower())}
    msg = re.sub(r"\b(?:sebelum|sesudah|setelah|menjelang)\s+(?:(?:di|ter|mem)?bakar\w*|pembakaran\w*|(?:di)?kremasi\w*"
                 r"|ngaben\w*|pengabenan)\b", " ", user_msg, flags=re.I)
    return not {w for w in _asked_specifics(msg, enriched) if _root(w) not in _WHY_GENERIC_ROOTS and w not in named}


def _strip_why_refusal(answer: Text, enriched: Optional[List[Dict[str, Any]]] = None) -> Text:
    """Cut the refusal when facts follow it; an answer that is only the refusal stays. With `enriched`, only
    when what follows gives the reason: a sentence naming the asked term with a purpose, meaning or reason
    word. "kenapa harus ada lemat sudhamala" lost its "Maaf, alasannya belum tercatat" above "Fakta yang
    tercatat mengenai lemat sudhamala adalah sebagai berikut: ... pisau ... eteh-eteh" (plan #16, 2026-10-26)."""
    out = _WHY_REFUSAL_RE.sub("", answer, count=1).strip()
    out = _WHY_REFUSAL_INNER_RE.sub(lambda m: m.group(1).upper(), out)
    if out == answer.strip() or len(out.split()) < 4:
        return answer
    if enriched:
        terms = [e for e in enriched if e.get("id") != "ngaben"] or enriched
        names = [n for e in terms for n in [e.get("name")] + list(e.get("aliases") or []) if n]
        # or points back to it: "Sesajen ini dihaturkan untuk mengawali upacara Ngaskara" (caru pengelambuk)
        name_rx = re.compile("|".join(rf"\b{re.escape(n)}\b" for n in names)
                             + r"|^\s*(?:[-*•]|\d+\.)?\s*(?:[\w-]+\s+){0,2}(?:ini|tersebut)\b", re.I)
        marker = re.compile(rf"\b(?:{_FOCUS_MARKERS['fungsi']}|{_FOCUS_MARKERS['simbol']}|{_REASON_MARKERS})\b", re.I)
        if not any(marker.search(s) and name_rx.search(s) for s in _sentences(out)):
            return answer
    return out[:1].upper() + out[1:]


# Hedges the model uses to guess: "Biasanya melibatkan keluarga dekat, tetua desa ..." for
# who performs pangringkes (T64), "... sebelum dimasukkan ke dalam kubur" (T66)
# Not after a negation: "jenazah yang tidak mungkin ditemukan kembali" (ngaben svasta's definition) is no guess,
# and Asti Wedana's and Ngaben Svasta's facts went from "apakah ngaben harus dilakukan dalam tujuh hari" (plan #16)
_SPECULATION_RE = re.compile(r"\b(?<!tidak )(?<!tak )(mungkin|barangkali|kemungkinan|biasanya|umumnya|pada umumnya)\b",
                             re.I)
# The closing filler of a list answer: "Setiap komponen memiliki peran khusus dalam upacara
# Ngaben, baik sebagai simbolisme maupun dalam proses ritual." after the contents of banten
# penebusan, whose context says nothing about roles (Tier B 2026-10-02)
# Also with the quantifier after the noun: "Komponen-komponen tersebut memiliki peran masing-masing
# dalam upacara." (daksina, conersation.md 2026-10-07)
_ROLE_FILLER_RE = re.compile(r"\b(?:setiap|masing-masing|semua|seluruh)\b[^.!?\n]*"
                             r"\b(?:peran|perannya|makna|maknanya|fungsi|fungsinya|tujuan|arti)\b"
                             r"|\b(?:peran|makna|fungsi|tujuan|arti)(?:nya)?\s+(?:masing-masing|tersendiri)\b",
                             re.I)
# A sentence announcing its own guess: "Meskipun tidak disebutkan secara spesifik tujuan utamanya
# dapat dipahami sebagai persiapan jenazah ..." (pangringkes), "Meskipun informasi spesifik ...
# tidak, dapat ditarik kesimpulan ..." (nyiram layon), conersation.md 2026-10-02. Always a guess.
# A hedged reason is a guess too: "Alasan menghindari sasih paruwak tahuk dan malamasa mungkin
# karena dianggap tidak baik untuk upacara-upacara besar" (Tier B 2026-10-02); no KB text says
# "mungkin karena".
# "Meskipun tidak ada informasi spesifik tentang ..., kita dapat mengambil beberapa asumsi." and
# "Ini dapat diartikan bahwa ..." (panca mahabhuta, 2026-10-07 batch). None of these phrases
# occurs in the KB's own text (checked against kb/output), so they can only be the model's.
_INFERENCE_RE = re.compile(r"\bdapat (?:ditarik (?:sebuah )?kesimpulan|disimpulkan|dipahami sebagai|diasumsikan"
                           r"|diartikan bahwa)"
                           r"|\b(?:mengambil|membuat|menarik)\s+(?:beberapa\s+|sebuah\s+)?(?:asumsi|dugaan)\b"
                           r"|\bmeskipun (?:informasi[^.!?\n]*|tidak (?:disebutkan|dijelaskan)\b"
                           r"|tidak ada (?:informasi|data|keterangan|penjelasan)\b)"
                           r"|\btidak disebutkan secara (?:spesifik|eksplisit|rinci)"
                           r"|\b(?:mungkin|kemungkinan(?: besar)?|diduga)\s+(?:karena|disebabkan|terkait dengan)\b",
                           re.I)


# "kekuatan spiritual": "sasih paruwak tahuk dihindari karena dianggap tidak memiliki kekuatan
# spiritual yang cukup untuk proses ngaben" (2026-10-08)
_VAGUE_REASON_RE = re.compile(r"\b(energi|positif|negatif|keberuntungan|keberkahan|kesialan|aura|vibrasi|"
                              r"kekuatan spiritual)\b", re.I)


def _sentence_roots(text: Text) -> set:
    return {_root(w) for w in _WORD_RE.findall(text.lower()) if len(w) >= 4 and w not in _STOPWORDS_ID}


# a closing sentence that sums up what was said
_SUMMARY_OPENER_RE = re.compile(r"^\s*(?:dengan demikian|jadi|secara (?:keseluruhan|umum|singkat)|kesimpulannya|"
                                r"singkatnya|intinya|oleh karena itu)\b", re.I)


def _asked_specifics(user_msg: Text, enriched: List[Dict[str, Any]]) -> set:
    """The words that make this question what it is -- not a question word, an aspect word, or
    a word of a term's name: "sembilan" in "apa makna bade tingkat sembilan", "11"/"sebelas" in
    "kenapa harus 11?"."""
    # the canonical name and aliases only: the surface typed ("bade tingkat sembilan") holds the
    # very word that makes the question (2026-10-08 replay)
    names = set()
    for e in enriched:
        names |= _sentence_roots(" ".join([e.get("name") or ""] + list(e.get("aliases") or [])))
    words = {w for w in _WORD_RE.findall(user_msg.lower()) if len(w) >= 3 and w not in _STOPWORDS_ID
             and w not in _QUESTION_WORDS and w not in _ASPECT_WORDS and _root(w) not in names}
    return words | {_NUMBER_WORDS[n] for n in re.findall(r"\b\d{1,2}\b", user_msg) if n in _NUMBER_WORDS} | \
        set(re.findall(r"\b\d{1,2}\b", user_msg))


def _opening_term(sentence: Text) -> Optional[str]:
    """The KB term a sentence opens with, named as written within its first three words: "Tingkatan utama
    berarti ..." is utama, "Ngaben massal adalah ..." ngaben massal."""
    resolver = get_resolver()
    words = _WORD_RE.findall(sentence)[:3]
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            m = resolver.resolve(" ".join(words[i:i + n]))
            if m and m.via in _NAMED_VIA:
                return m.id
    return None


def _item_parents(eid: str) -> set:
    """What a term is a kind or a part of."""
    return set(get_content().kind_parents.get(eid, ())) | {
        r["target_id"] for r in _kb_relationships(eid) if r["relation"] == "BAGIAN_DARI" and r["outgoing"]}


def _next_list_item(s: Text, roots: set, said: List[set], said_texts: List[Text]) -> bool:
    """s opens with a term, and every earlier sentence it shares half its words with opens with another term
    of the same kind or whole: the next item of a list, not a repeat."""
    near = [t for r, t in zip(said, said_texts) if len(roots & r) >= 0.5 * len(roots)]
    item = _opening_term(s) if near else None
    if not item:
        return False
    parents = _item_parents(item)
    for t in near:
        other = _opening_term(t)
        if not other or other == item or not parents & _item_parents(other):
            return False
    return True


def _drop_repeated_sentences(answer: Text, earlier: Text = "", loose: bool = True,
                             protect: Optional[set] = None) -> Text:
    """A sentence most of whose words one earlier sentence already said goes: "apa itu bade" gave
    the tiers in the definition's words, then again in tingkatan bade's ("Bade bertingkat sebelas
    dipakai untuk jenazah Raja Bali, bertingkat sembilan ..."), and "apa itu ngaben" its kinds
    twice (conersation.md 2026-10-07: "It sometimes repeats itself"; 2026-10-08 batch). So does
    one the sentences before it say together (nine tenths of its words), and a closing summary
    ("Dengan demikian ...") they mostly say. `earlier` is the bot's previous answer when this is a
    follow-up on the same term: "apa maknanya" re-said it ("how is this one more elaborate than
    the previous one"); `loose` (a follow-up) drops what it re-says in other words too, otherwise
    only a near-copy goes. A sentence holding a `protect` word (what this question asks) is never
    dropped for repeating `earlier`. Sentences with under five words that count stay; never
    leaves nothing."""
    protect_re = (re.compile(r"\b(?:" + "|".join(re.escape(w) for w in protect) + r")\b", re.I)
                  if protect else None)
    prior = [r for r in (_sentence_roots(s) for s in re.findall(r"[^.!?\n]+[.!?]*", earlier)) if len(r) >= 4]
    prior_union = set().union(*prior) if prior else set()
    said, union, said_texts = [], set(), []
    parts = re.findall(r"[^.!?\n]+[.!?]*", answer)
    last = next((s for s in reversed(parts) if s.strip()), None)
    drop, trims = [], []
    for s in parts:
        roots = _sentence_roots(s)
        if len(roots) >= 5:
            best = max((len(roots & r) / len(roots) for r in said), default=0.0)
            covered = len(roots & union) / len(roots)
            # the previous answer, re-said in other words ("Tirta pangentas memiliki makna sebagai alat
            # sangaskara ...") -- looser, the user has just read it
            best_prior = max((len(roots & r) / len(roots) for r in prior), default=0.0)
            covered_prior = len(roots & (union | prior_union)) / len(roots)
            repeats_prior = (not (protect_re and protect_re.search(s))
                             and (best_prior >= 0.8 or loose and (best_prior >= 0.6 or covered_prior >= 0.75)))
            repeats = (best >= 0.8 or covered >= 0.9 and len(roots) >= 6
                       or _SUMMARY_OPENER_RE.match(s) and covered >= 0.7
                       # a closing sentence saying again what came before ("Pembersihan fisik dan
                       # spiritual ... bertujuan untuk memastikan jenazah ... siap untuk proses pembakaran")
                       or s is last and len(roots) >= 6 and covered >= 0.75)
            # the next item of a list told in one frame is no repeat of the items before it: "Tingkatan utama
            # berarti 'besar' dan merupakan tingkatan dengan jumlah sesajen ... paling banyak" went after nista's
            # and madya's sentences ("apa saja tingkatan dalam upacara ngaben", 2026-10-28) -- only the previous
            # answer counts against it
            if ((repeats or repeats_prior) and not _SUMMARY_OPENER_RE.match(s)
                    and _next_list_item(s, roots, said, said_texts)):
                repeats = False
                covered_prior = len(roots & prior_union) / len(roots)
                repeats_prior = (not (protect_re and protect_re.search(s))
                                 and (best_prior >= 0.8 or loose and (best_prior >= 0.6 or covered_prior >= 0.75)))
            if repeats or repeats_prior:
                drop.append(s)
                continue
        # a closing "sehingga ..." clause one earlier sentence already said: madiksa's and sulinggih's
        # sentences both ended "sehingga berwenang memuja Ida Sang Hyang Widhi Wasa, membuat tirtha
        # ..., dan memimpin ... Panca Yadnya" (Tier B 2026-10-09)
        tail = re.search(r",?\s+sehingga\s+([^.!?\n]+)", s)
        if tail and said:
            t_roots = _sentence_roots(tail.group(1))
            if len(t_roots) >= 5 and max(len(t_roots & r) / len(t_roots) for r in said) >= 0.85:
                trims.append((s, s[:tail.start()].rstrip(" ,") + s[tail.end():]))
        if len(roots) >= 4:
            said.append(roots)
            said_texts.append(s)
            union |= roots
    if not trims and (not drop or len(drop) == len([s for s in parts if _sentence_roots(s)])):
        return answer
    for s, short in trims:
        answer = answer.replace(s, short, 1)
    if len(drop) == len([s for s in parts if _sentence_roots(s)]):
        drop = []
    for s in drop:
        answer = answer.replace(s, "", 1)
    answer = re.sub(r"[ \t]{2,}", " ", answer)
    answer = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", answer).strip()
    # a connective left in front ("Dengan demikian, tirtha ini menjadi penunjuk jalan ...")
    answer = re.sub(r"^(?:dengan demikian|selain itu|oleh karena itu|jadi|namun|akan tetapi),\s*", "", answer, flags=re.I)
    return answer[:1].upper() + answer[1:]


# "Bade tingkat 11 memiliki makna yang mendalam dalam ritual Ngaben di Bali." -- the question
# restated with a filler, before the answer (conersation.md 2026-10-07: "it doesnt immedietly make
# it clear that it has answered the question")
_FILLER_RE = re.compile(r"\bmemiliki (?:makna|arti|peran(?:an)?|nilai|kedudukan|hubungan|fungsi)"
                        r"(?: \w+)? (?:yang )?(?:sangat |cukup |amat )?(?:mendalam|penting|besar|khusus|signifikan|erat|istimewa)\b"
                        r"|\bberperan (?:sangat )?penting\b", re.I)
# "Setiap tahap memiliki peran dan makna tersendiri dalam proses ...", "Setiap jenis memiliki
# karakteristik dan prosedur yang berbeda" -- says each has its own without saying what (2026-10-08)
_PADDING_RE = re.compile(r"\b(?:setiap|masing-masing)\s+(?:jenis|tahap|tahapan|komponen|unsur|bagian|banten|sarana|"
                         r"benda|elemen|tingkatan|upacara|tingkat)\w*\s+(?:[\w-]+\s+)?(?:ini\s+|tersebut\s+)?(?:juga\s+)?memiliki\s+"
                         r"(?:peran|makna|fungsi|tujuan|arti|karakteristik|ciri|prosedur|keunikan|simbolisme)", re.I)
_FILLER_GENERIC_ROOTS = frozenset(_root(w) for w in (
    "ritual", "upacara", "ngaben", "bali", "hindu", "tradisi", "kepercayaan", "agama", "budaya", "konteks",
    "spiritual", "filosofis", "filosofi", "masyarakat", "rangkaian", "prosesi", "keagamaan"))


def _drop_filler_openers(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A sentence that only says the asked thing is meaningful, important or closely related --
    every other word it has is the question's, a term's name, or a word like "ritual Ngaben di
    Bali" -- goes, so the answer starts with the answer. Never leaves nothing."""
    known = _sentence_roots(user_msg) | _FILLER_GENERIC_ROOTS
    for e in enriched:
        known |= _sentence_roots(" ".join([e.get("name") or ""] + list(e.get("aliases") or [])))
    parts = [s for s in re.findall(r"[^.!?\n]+[.!?]*", answer) if s.strip()]
    drop = [s for s in parts if _FILLER_RE.search(s) and _sentence_roots(_FILLER_RE.sub(" ", s)) <= known]
    # padding, and a closing summary that leads with the filler ("Dengan demikian, ngaben memiliki
    # makna yang mendalam dalam ritual Ngaben, melibatkan proses spiritual ...", 2026-10-08)
    drop += [s for s in parts[1:] if s not in drop and (
        _PADDING_RE.search(s) or _SUMMARY_OPENER_RE.match(s) and _FILLER_RE.search(s))]
    if not drop or len(drop) == len(parts):
        return answer
    for s in drop:
        answer = answer.replace(s, "", 1)
    answer = re.sub(r"[ \t]{2,}", " ", answer).strip()
    return answer[:1].upper() + answer[1:]


_SEQUENCE_GLUE_ROOTS = frozenset(_root(w) for w in """
kemudian lalu selanjutnya setelahnya akhirnya lagi cara caranya dilakukan dilaksanakan melakukan prosesnya
langkah langkahnya""".split())


def _drop_unsupported(answer: Text, context_text: Text, user_msg: Text) -> Text:
    """A sentence after the opening that the context does not support goes, hedged or not: "Upacara
    ini juga dapat dilakukan di tempat lain yang dianggap suci ... tergantung pada situasi
    spesifik jenazah", "Setra dipilih ... karena memiliki kepentingan spiritual", "dengan bagian-bagian
    tubuh tertentu seperti kepala, tangan, dan kaki memiliki peran khusus" (2026-10-08). Its words
    (rough roots, 5+ of them, the question's aside) must be half covered by its two best-matching
    context sentences, unless at most one of them appears nowhere in the context. Calibrated on 36
    batch questions (182 sentences, plan #9): of the supported ones only a half-padded one fell under
    it ("tugas utama pemangku adalah memohon tirtha, yang merupakan aspek esensial ..."); "Hubungan
    Siwa dengan Ngaben terletak pada peran beliau sebagai dewa pelebur" (0.50) stays. Never leaves
    nothing; never the opening sentence, which answers the question in the question's words.
    The words that join a told sequence count neither way: "Proses pembungkusannya dilakukan dengan cara
    menggulung jenazah menggunakan kain yang telah dirajah, kemudian digulung lagi dengan tikar" -- two
    context facts word for word -- went for "kemudian", "dilakukan", "cara" (plan #16, 2026-10-26)."""
    ctx_sents = [r for r in (_sentence_roots(x) for x in re.split(r"[.;!?\n]|\",\"", context_text)) if r]
    if not ctx_sents:
        return answer
    vocab = set().union(*ctx_sents)
    q_roots = _sentence_roots(user_msg)
    parts = [s for s in re.findall(r"[^.!?\n]+[.!?]*", answer) if s.strip()]

    def unsupported(s: Text) -> bool:
        # the bot's own miss wording is in no context ("informasi detail ... belum tercatat di basis data"):
        # #1715 "apa itu daksina dan apa maknanya" lost the sentence saying its meaning is not recorded
        if _VERDICT_RE.search(s):
            return False
        roots = _sentence_roots(s) - q_roots - _SEQUENCE_GLUE_ROOTS
        if len(roots) < 5:
            return False
        best = max(ctx_sents, key=lambda c: len(roots & c))
        second = max(ctx_sents, key=lambda c: len((roots - best) & c))
        return len(roots & (best | second)) < 0.5 * len(roots) and len(roots - vocab) >= 2
    drop = [s for s in parts[1:] if unsupported(s)]
    if not drop or len(drop) == len(parts):
        return answer
    for s in drop:
        answer = answer.replace(s, "", 1)
    answer = re.sub(r"[ \t]{2,}", " ", answer)
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", answer).strip()


def _kb_linked(a: Text, b: Text) -> bool:
    """Whether the KB joins two terms: an edge either way, a kind-of link, or a definition naming the other."""
    content = get_content()
    if (any(f["object_id"] == b for f in content.facts_by_subj.get(a, []))
            or any(f["object_id"] == a for f in content.facts_by_subj.get(b, []))
            or content.is_kind_of(a, b) or content.is_kind_of(b, a)):
        return True
    return (b in _named_terms(content.best_definition(a) or "", everyday=True)
            or a in _named_terms(content.best_definition(b) or "", everyday=True))


def _drop_unlinked_glosses(answer: Text, context_text: Text) -> Text:
    """A bracket glossing a KB term as another KB term that the KB never links to it goes: "sehingga pitra (jenazah)
    tidak berhak mendapat upacara Atma Wedana" (V3 #1857, 2026-11-03) -- pitra is the deceased's spirit ("pitra (roh)",
    corpus L1072; its card), the body is jenazah, and no edge or definition joins the two. The same check caught
    "sepasang pering (bambu)" (pering is janur, canon audit 2026-10-28) and "memandikan (nyekah)" in the recorded
    answers. A bracket often glosses the whole phrase before it, and those stay: the terms are linked ("wadah
    pembakaran jenazah (patulangan)", "digali kembali dari kuburan (ngangkid galih)"), or the bracketed term's card
    describes it with the two words before the bracket ("jumlah hiasan (mangle)": mangle is a "sarana hias", "sarana
    persembahyangan (banten)", "badan manusia (Suku Tunggal)"). Only a bracket that is exactly one KB name, right after
    another; one the context writes itself stays."""
    _named_terms("", everyday=True)
    _, names = _SURFACES[True]
    ctx = context_text.lower()
    content = get_content()

    def cut(m: "re.Match") -> Text:
        inner = names.get(m.group(1).strip().lower())
        if not inner:
            return m.group(0)
        before = m.string[:m.start()]
        words = re.findall(r"[\w'-]+", before[-80:])
        for n in range(min(5, len(words)), 0, -1):
            surface = " ".join(words[-n:])
            term = names.get(surface.lower())
            if term and re.search(rf"{re.escape(surface)}$", before):
                break
        else:
            return m.group(0)
        described = _sentence_roots(" ".join(re.split(r"[,.;:!?()\n]", before)[-1].split()[-2:]))
        if (term == inner or _kb_linked(term, inner)
                or described & _sentence_roots(content.best_definition(inner) or "")
                or f"{surface} ({m.group(1).strip()})".lower() in ctx):
            return m.group(0)
        return ""
    return re.sub(r"[ \t]*\(([^()\n]{2,60})\)", cut, answer)


def _drop_speculation(answer: Text, context_text: Text) -> Text:
    """Drop a sentence that hedges with a word the context itself never uses (the
    definitions do say "biasanya tiga lembar", "mungkin bertingkat"), or that says each item
    has its own role, AND whose other content words are mostly not in the context:
    "Palebon adalah istilah halus untuk ... ngaben, yang biasanya dipakai untuk kalangan
    tertentu" is the definition reworded and stays. Never leaves nothing."""
    ctx = context_text.lower()
    vocab = _content_words(context_text)
    ctx_sentences = [r for r in (_sentence_roots(x) for x in re.split(r"[.;!?\n]|\",\"", context_text)) if r]
    resolver = get_resolver()
    parts = re.findall(r"[^.!?\n]+[.!?]*", answer)
    first = next((s for s in parts if s.strip()), None)

    def guessed(s: str) -> bool:
        if _INFERENCE_RE.search(s):
            return True
        # what a hedge introduces must be one context sentence's: "Setra ... biasanya berdekatan
        # dengan pura desa" (2026-10-08), while the context says "biasanya" only of other things,
        # so the word check below let it through. Not the opening sentence -- the direct answer
        # ("Ngaben biasanya dilaksanakan di setra, ...") paraphrases more than one fact.
        hedge = _SPECULATION_RE.search(s)
        if hedge and s is not first:
            claim = _sentence_roots(s[hedge.end():])
            if len(claim) >= 2 and max((len(claim & r) / len(claim) for r in ctx_sentences), default=0) < 0.5:
                return True
        # the model's stock metaphysics when no reason is recorded: "energi negatif", "kekuatan
        # positif", "membawa keberuntungan" (malamasa / paruwak tahuk, Tier B 2026-10-05). The
        # context must use the word about the same thing -- a sentence sharing a rarer word with
        # this one: banten byakawonan's "bhuta kala yang bersifat negatif", shown among ngaben's
        # related terms, let "menghindari pengaruh negatif" stand for paruwak tahuk (2026-10-08)
        s_roots = _sentence_roots(s)
        for w in _VAGUE_REASON_RE.findall(s.lower()):
            w_roots = {_root(x) for x in w.split()}
            others = {r for r in s_roots - w_roots if not _is_everyday_word(r, resolver)}
            if not any(w_roots <= r and r & others for r in ctx_sentences):
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

    drop = [s for s in parts if guessed(s)]
    if not drop or len(drop) == len([s for s in parts if s.strip()]):
        return answer
    out = answer
    for s in drop:
        if _VERDICT_RE.search(s):
            # the verdict stays; only a guessed reason after it goes: "Tidak ada keterangan yang menyatakan
            # bahwa klungah boleh ... pada saat tepung ketan, karena keduanya memiliki fungsi dan konteks
            # penggunaan yang berbeda" (#1731, 2026-10-20)
            cut = re.search(r",?\s+(?:karena|sebab)\b", s, re.I)
            if cut and _VERDICT_RE.search(s[:cut.start()]):
                out = out.replace(s, s[:cut.start()].rstrip() + ".", 1)
            continue
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
        if any(r.get("relation") in preds and (
                # parts are what the term holds or its kinds, never what it is a part or kind of:
                # "wuku kuningan TERMASUK_JENIS wuku", "mapendem BAGIAN_DARI pitra yadnya" counted, so
                # "wuku kuningan terdiri dari apa saja" got no rule 23 and Qwen wrote "Sasih Kaenem
                # tidak memiliki bagian-bagian ...; ia adalah satu kesatuan" (plan #16, 2026-10-26)
                bool(r.get("outgoing")) != (r.get("relation") in PART_IS_SUBJECT | {"TERMASUK_JENIS"})
                if family == "komposisi" else
                (r.get("outgoing") or family not in _OUTGOING_ONLY_FAMILIES))
               for r in e.get("relationships") or []):
            return True
    return False


# The synthesis prompt's "Yang ditanyakan" line: what each asked aspect is called
_FOCUS_LABELS = {
    "sebutan_lain": "sebutan lain", "jenis": "jenis", "tahapan": "tahapan", "cara": "cara atau proses",
    "komposisi": "isi atau bahan", "simbol": "makna", "lokasi": "tempat", "waktu": "waktu", "pelaku": "pelaku",
    "ciri": "bentuk, warna atau ciri", "fungsi": "fungsi atau tujuan", "sumber": "sumber (lontar)",
    "sarana": "sarana",
}
_REQUIREMENT_Q_RE = re.compile(r"\b(?:per)?syarat(?:an|nya)?\b", re.I)


def _aspect_label(family: str, question: Text, english: bool = False) -> str:
    """The asked aspect's name for the focus line and the misses (`english`: rule 23's). A requirement
    sits in the waktu family with its SYARAT / MENSYARATKAN edges, and "apa syarat melakukan pedangal" was
    told and answered "waktu pelaksanaan pedangal belum tercatat" (NLU sweep 2026-10-19)."""
    if (family == "waktu" and _REQUIREMENT_Q_RE.search(question)
            and not re.search(r"\bkapan\b|\bwaktu", question, re.I)):
        return "its requirements" if english else "syarat"
    # "berapa tingkat tirtha kawitan" asks its rank: not "bentuk, warna atau ciri" (V2 run 2026-11-02)
    if family == "ciri" and re.search(r"\btingkat", question, re.I):
        return "its rank" if english else "tingkat"
    # "dari mana diperoleh" asks where it comes from: "Asal ...", not "Tempat ..."
    if family == "lokasi" and re.search(r"\bdari\s*mana\b|\basal(?:nya)?\b|\bdiperoleh\b|\bdidapat", question, re.I):
        return "where it comes from" if english else "asal"
    return (_ASPECT_LABELS if english else _FOCUS_LABELS)[family]


# words that carry no part of what is asked ("emang kalok semisal nggak ngaben kenapa?")
_FOCUS_FILLER = frozenset("""
saja hal ada harus sih dong deh emang memang lantas kalau kalao kalo kalok jika bila apabila misalnya semisal
nggak ngga enggak gak tak dilakukan dilaksanakan melakukan melaksanakan saat ketika dan atau serta lalu
boleh bolehkah wajib dilarang melakukannya melaksanakannya dilakukannya dilaksanakannya terjadi
""".split())
_NEGATION_WORDS = {"nggak": "tidak", "ngga": "tidak", "enggak": "tidak", "gak": "tidak", "ga": "tidak",
                   "tak": "tidak"}
# a consequence question's condition, as asked: "akibat ngaben tanpa tirta pangentas" (the terms
# alone, "akibat ngaben dan tirta pangentas", lost the "tanpa": the answer dropped "pengabenan
# dianggap belum dilaksanakan", Tier B 2026-10-09)
_CONDITION_DROP = frozenset("""
apa itu yang kalau kalao kalo kalok jika jikalau bila apabila seandainya andaikan andai misalnya semisal emang
memang lantas sih dong deh terjadi akibatnya dampaknya konsekuensi konsekuensinya kenapa mengapa
""".split())
# the words that only say which kind of question it is
_FOCUS_QUESTION_RES = _ASPECT_WORD_RES + [_RELATION_Q_RE, _COMPARE_Q_RE, _LIST_Q_RE, _OVERVIEW_Q_RE]
_FOCUS_PREPOSITIONS = frozenset("dalam untuk pada saat di ke dari bagi dengan terhadap oleh setelah sebelum "
                                "sesudah selama".split())


_NEGATION_TOKENS = frozenset({"tidak", "tak", "gak", "nggak", "ngga", "enggak", "ga", "belum", "bukan"})


def _question_focus(question: Text, enriched: List[Dict[str, Any]], families: List[str]) -> Text:
    """What the question asks, in a few words: the asked aspect, the terms as the KB names them
    and the question's own words ("makna tingkatan bade (kata kunci: sembilan)"). The model was
    shown the question only as typed, so a follow-up reached it with no term: "apa maknanya?"
    about banten pamegat came back as its definition (2026-10-08 replay). `question` is the
    synthesis question, whose terms are already the KB's names."""
    if not enriched:
        return ""
    names = list(dict.fromkeys(e["name"] for e in enriched))
    subject = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " dan " + names[-1]
    specifics = _asked_specifics(question, enriched)
    words: List[str] = []
    for w in re.findall(r"[a-z]+|\d{1,2}", question.lower()):
        if (w in specifics and w not in words and w not in _FOCUS_FILLER
                and not any(p.search(w) for p in _FOCUS_QUESTION_RES)):
            words.append(w)
            if w in _NUMBER_WORDS and _NUMBER_WORDS[w] not in words:
                words.append(_NUMBER_WORDS[w])
    # why-avoided: the avoided terms are the named ones their definitions judge; "kenapa tidak boleh
    # melakukan yadnya pada sasih paruwak tahuk dan malamasa?" opened "Yadnya, sasih paruwak tahuk,
    # dan malamasa dihindari ..." (Tier B 2026-10-09). Not dewasa ngaben brought in by a day question:
    # "alasan dewasa ngaben dihindari untuk ngaben" came back word for word.
    named = set(_named_terms(question, everyday=True))
    judged = [e["name"] for e in enriched
              if e["id"] in named and _JUDGEMENT_RE.search(e.get("definition") or "")]
    # the subject of an aspect is the asked term: "pelaku ngaben dan jenazah" got a paragraph on
    # the corpse not leading the ceremony, "fungsi atau tujuan tirtha dan ngaben" ngaben's purposes
    # as tirtha's (Tier B 2026-10-09). Terms the question names together are the subject only of a
    # relation, comparison, consequence or why-avoided question.
    what = re.match(r"^\s*(?:apa|siapa)\s+itu\s+(.+?)(?:\s+dan\b|[?,]|$)", question, re.I)
    first = next((e for e in enriched if what and _ortho_key(what.group(1)) in
                  {_ortho_key(s) for s in [e["name"], e.get("asked_as")] + list(e.get("aliases") or []) if s}),
                 None)
    main = next((e["name"] for e in enriched if e is not first), names[0])
    # ... and the terms joined to it ("apa arti kata pitra dan yadnya" lost yadnya): not one after a
    # preposition ("dalam pengabenan") or inside another term's name in the question
    spans = {}
    for e in enriched:
        m = re.search(rf"(?<![\w-]){re.escape(e['name'])}(?![\w-])", question, re.I)
        if m:
            spans[e["name"]] = m.span()
    # A term after a preposition stays, with it: "fungsi atau tujuan tirtha dalam ngaben", "boleh atau
    # tidaknya ngaben saat sasih kadasa".
    coord, context = [main], []
    for n in names:
        if n == main or n not in spans or (first and n == first["name"]):
            continue
        s, t = spans[n]
        inside = any(o != n and os <= s and t <= ot and (os, ot) != (s, t) for o, (os, ot) in spans.items())
        before = re.findall(r"[\w-]+|,", question[:s])
        if inside or not before:
            continue
        if before[-1].lower() in {"dan", "atau", "serta", ","}:
            coord.append(n)
        elif before[-1].lower() in _FOCUS_PREPOSITIONS:
            context.append(f"{before[-1].lower()} {n}")
    main = " dan ".join(coord) + "".join(f" {c}" for c in context)
    if any(e["id"] == "dewasa_ngaben" for e in enriched) and "dewasa_ngaben" not in named:
        # a day question in its own words: "hari yang harus dihindari untuk ngaben, dan alasannya"
        phrase = [w for w in re.findall(r"[\w-]+", question.lower().split("?")[0])
                  if w not in _QUESTION_WORDS and w not in {"saja", "sih", "dong", "jadi"}]
        while phrase and phrase[-1] in {"dan", "atau"}:
            phrase.pop()
        return " ".join(phrase) + (", dan alasannya" if _WHY_Q_RE.search(question) else "")
    if _CONSEQUENCE_Q_RE.search(question):
        cond = [_NEGATION_WORDS.get(w, w) for w in re.findall(r"[\w-]+", question.lower().split("?")[0])
                if w not in _CONDITION_DROP]
        # as a question, not "akibat bila X": the model echoed it and filled in a noun, "Akibat bila
        # di Bali tidak ngaben adalah penundaan ..." -- no source says it is delayed (2026-10-09 replay)
        if cond:
            subject = " ".join(cond[:12])
            aspect, words = "apa yang terjadi bila", []
        else:
            aspect = "apa yang terjadi"
    elif _WHY_Q_RE.search(question) and _WHY_AVOID_Q_RE.search(question) and judged and len(judged) < len(names):
        others = [n for n in names if n not in judged]
        subject = (f"{' dan '.join(judged)} dihindari untuk {' dan '.join(others)}")
        aspect = "alasan"
    elif len(names) >= 2 and _COMPARE_Q_RE.search(question):
        aspect = "perbedaan"
    elif len(names) >= 2 and _RELATION_Q_RE.search(question):
        aspect = "hubungan"
    else:
        subject = main
        if _WHY_Q_RE.search(question):
            aspect = "alasan"
        elif _PERMISSION_Q_RE.search(question) and (_whether_question(question)
                                                    or re.search(r"\b(?:boleh|harus)kah\b", question, re.I)):
            # "apakah niskala wajib" was asked "boleh atau tidaknya" and answered about "boleh atau tidaknya";
            # "apa yang harus dilakukan keluarga pertama kali ..." asks what, not whether
            must = (re.search(r"\b(?:harus|haruskah|wajib)\b", question, re.I)
                    and not re.search(r"\bboleh(?:kah)?\b|\bdilarang\b", question, re.I))
            aspect = "wajib atau tidaknya" if must else "boleh atau tidaknya"
        elif _WORD_MEANING_RE.search(question):
            # "apa arti kata ngaben dan dari mana asal katanya": "arti kata ngaben" alone lost "beya"
            aspect = "arti dan asal kata" if re.search(r"\basal\b", question, re.I) else "arti kata"
            words = [w for w in words if not w.startswith("kata") and w != "asal"]
        elif families:
            aspect = " dan ".join(dict.fromkeys(_aspect_label(f, question) for f in families if f in _FOCUS_LABELS))
        elif _LIST_Q_RE.search(question):
            # a list question with no aspect is clear as asked, and every label changed the list's
            # shape: "daftar pura kahyangan tiga" got the three names and nothing on each, "apa saja
            # yang termasuk sasih paruwak tahuk" the sasih without the wuku that make them so (sasih
            # kasa alone is a good month; Tier B 2026-10-09, 2/2 loads each)
            return ""
        elif _OVERVIEW_Q_RE.search(question) or not words:
            aspect = "pengertian"
        else:
            # "apa ketentuan penggunaan petulangan": no aspect word, the question's own words say it -- with the
            # negation before a word, and about the term the question names rather than one code added before it:
            # "kalau keluarganya gak mampu buat ngaben gimana?" reached Qwen as "keluarganya mampu buat ngaben massal"
            # and got ngaben massal's definition alone (human test 2026-11-03)
            toks = re.findall(r"[a-z]+|\d{1,2}", question.lower())
            negated = {toks[i] for i in range(1, len(toks)) if toks[i - 1] in _NEGATION_TOKENS and toks[i - 1] not in words}
            aspect, words = " ".join(f"tidak {w}" if w in negated else w for w in words), []
            if names[0] not in spans:
                content = get_content()
                subject = next((e["name"] for e in enriched[1:] if e["name"] in spans
                                and content.is_kind_of(enriched[0]["id"], e["id"])), subject)
    focus = f"{aspect} {subject}" if aspect else subject
    if first and aspect != "pengertian":
        # "apa itu bade dan kenapa tingkatannya berbeda": what bade is first, then the reason
        focus = f"pengertian {first['name']}, lalu {focus}"
    if words:
        focus += f" (kata kunci: {', '.join(words)})"
    return focus


# What a sentence that answers each asked aspect says (_lead_with_asked_aspect): an opening with
# any of these is left alone. Not a bare "untuk" / "digunakan": "Bahan utama yang digunakan untuk
# membuat patulangan adalah bambu" says nothing of what patulangan is for.
_FOCUS_MARKERS = {
    "simbol": r"melambangkan|lambang\w*|makna\w*|bermakna|menggambarkan|menandakan|menandai|menunjukkan|simbol\w*|"
              r"menyimbolkan|wujud|perwujudan|mewujudkan|diwujudkan|mencerminkan|berarti|"
              r"sebagai (?:tanda|penanda|pertanda|penegasan)",
    "fungsi": r"berfungsi|fungsi\w*|tujuan\w*|bertujuan|berguna|kegunaan\w*|guna|berperan|peran\w*|manfaat\w*|agar|"
              r"supaya|diyakini|sebagai (?:tempat|sarana|alat|media|wadah|penunjuk|pengganti|penanda|lambang|simbol)|"
              r"(?:digunakan|dipakai|dihaturkan|dipersembahkan) (?:sebagai|untuk)(?! (?:membuat|membentuk|mengikat))",
}
_REASON_MARKERS = r"karena|sebab|agar|supaya|sehingga|bertujuan|tujuan\w*"
# says there is a meaning or role without saying it: "Uang kepeng ... memiliki makna simbolis dalam
# ritual ini" answered "mengapa uang kepeng digunakan" (Tier B 2026-10-09)
# ("memiliki makna filosofis dalam pelepasan jiwa ..." does say it: only the phrase with nothing
# after it is vague)
_VAGUE_ASPECT_RE = re.compile(r"\b(?:memiliki|mempunyai|mengandung)\s+(?:makna|arti|peran|fungsi|nilai)"
                              r"(?:\s+(?:yang\s+)?(?:simbolis|penting|mendalam|khusus|tersendiri|besar|sakral|"
                              r"spiritual|religius|filosofis))*"
                              r"(?:\s+(?:dalam|bagi|pada)\s+(?:ritual|upacara|prosesi)(?:\s+(?:ini|tersebut|ngaben))?)?"
                              r"\s*[.!?]?\s*$", re.I)
_LEAD_CONNECTIVE_RE = re.compile(r"^\s*(?:selain itu|namun|juga|kemudian|sementara itu|di samping itu),?\s+", re.I)
# an answer cannot open by leaning on a sentence before it
_OPENING_LEANBACK_RE = re.compile(r"^\s*(?:meskipun demikian|walaupun demikian|namun demikian|namun|akan tetapi|"
                                  r"selain itu|di samping itu|sementara itu|oleh karena itu|dengan demikian),\s*", re.I)
# a sentence that leans on the one before it cannot open the answer
_LEANS_BACK_RE = re.compile(r"^\s*(?:ini|itu|hal ini|hal tersebut|tersebut|[\w-]+ (?:ini|itu|tersebut)|"
                            r"dengan demikian|oleh karena itu|karena itu)\b", re.I)


_UNRECORDED_RE = re.compile(r"\b(?:belum|tidak)\s+(?:secara\s+\w+\s+)?(?:tercatat|disebutkan|dijelaskan|diuraikan|"
                            r"dirinci)\b", re.I)


def _say_unrecorded(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]], missing: List[str]) -> Text:
    """Rule 23's miss said in code: the prompt told the model that nothing records the asked aspect, and
    "nistaning madya dibuat dari apa" still came back as the definition alone, which reads as the answer
    (NLU sweep 2026-10-19). One term, one plain question, an aspect whose wording code can see (contents,
    place, time, doer, how -- meaning and purpose are _lead_with_asked_aspect's), said by no definition in
    the context nor by the answer: "Maaf, <aspek> X belum tercatat di basis data. Yang tercatat tentang X:"
    goes in front of the answer."""
    if (not missing or len(enriched) != 1 or _WHY_Q_RE.search(user_msg) or _CONSEQUENCE_Q_RE.search(user_msg)
            or _whether_question(user_msg)):
        return answer
    name, definition = enriched[0]["name"], enriched[0].get("definition") or ""

    def marker(f: str):
        if f == "komposisi":
            return _CONTENTS_IN_DEF_RE
        return re.compile(rf"\b(?:{_TEMPLATE_DEF_MARKERS[f]})\b", re.I) if f in _TEMPLATE_DEF_MARKERS else None
    if _asks_what_is_first(user_msg, enriched):
        # "apa itu paksa mahayana, dari mana diperoleh, dan apa fungsinya": a part nothing records and the
        # answer skips gets its own closing sentence -- the model answered two of the three (2026-10-19)
        gaps = [f for f in missing if (m := marker(f)) and not m.search(answer) and not m.search(definition)]
        if not gaps or _UNRECORDED_RE.search(answer):
            return answer
        label = " atau ".join(_aspect_label(f, user_msg) for f in gaps)
        return f"{answer.rstrip()} {label[:1].upper()}{label[1:]} {name} belum tercatat di basis data."
    if answer.lstrip().startswith("Maaf") or _UNRECORDED_RE.search(answer) or set(missing) & {"simbol", "fungsi"}:
        return answer
    markers = [marker(f) for f in missing]
    if not all(markers) or any(m.search(t) for m in markers for t in (definition, answer)):
        return answer
    label = " atau ".join(_aspect_label(f, user_msg) for f in missing)
    return (f"Maaf, {label} {name} belum tercatat di basis data. Yang tercatat tentang {name}: "
            f"{answer.lstrip()[:1].upper()}{answer.lstrip()[1:]}")


_DUTY_RE = re.compile(r"\b(?:wajib|kewajiban|diwajibkan|harus|perlu|mutlak|syarat|mensyaratkan)\b", re.I)


def _complete_duty_verdict(answer: Text, context_text: Text, user_msg: Text) -> Text:
    """A must-it question answered with facts and no verdict: "apakah niskala wajib" got niskala's
    definition and nothing about a duty (NLU sweep 2026-10-19). When no rule of the context is about the
    question, "Kewajiban untuk hal tersebut tidak tercatat di basis data." goes in front -- never a "Ya"
    or "Tidak" of code's own."""
    if (not re.search(r"\b(?:wajib|harus(?:kah)?|perlu(?:kah)?|diwajibkan)\b", user_msg, re.I)
            or re.match(r"^\s*\**\s*(?:ya|tidak|boleh|wajib|harus|perlu|bukan)\b", answer, re.I)
            or _DUTY_RE.search(answer) or _UNRECORDED_RE.search(answer)
            or _rule_about_question(context_text, user_msg, _DUTY_RE)):
        return answer
    return "Kewajiban untuk hal tersebut tidak tercatat di basis data. " + answer.lstrip()


def _complete_rule_answer(answer: Text, context_text: Text, user_msg: Text) -> Text:
    """A question about a term's rules ("apa ketentuan penggunaan niskala") whose context states no rule
    about it: the model passed the definition off as the rule ("Ketentuan penggunaannya adalah bahwa
    pembakaran jenazah dipahami berlangsung pada dua tataran", NLU sweep 2026-10-19). That framing goes, and
    "Ketentuan atau aturan khusus untuk hal tersebut tidak tercatat di basis data." goes in front."""
    if not _RULE_Q_RE.search(user_msg) or _rule_about_question(context_text, user_msg, _RULE_STATED_RE):
        return answer
    # who it is used by is what "ketentuan penggunaan" asks of a thing ("apa ketentuan penggunaan petulangan":
    # "gajah mina ... digunakan oleh golongan Wesia", "macan ... diperuntukkan bagi wangsa Pande"); with those
    # norms the answer opened "Ketentuan ... tidak tercatat. Ketentuan penggunaan patulangan ditentukan oleh golongan"
    # (Tier B, plan #16, 2026-10-26)
    used_by = re.compile(r"\b(?:digunakan|dipakai|diperuntukkan)\s+(?:oleh|bagi)\b", re.I)
    if used_by.search(answer) and used_by.search(context_text):
        return answer
    # "Aturan pemakaian Dewa Wishnu dalam upacara Ngaben adalah Beliau berstana ..." (plan #16): the framing
    # was cut only with two words before "adalah"; a pronoun after it becomes the name ("Dewa Wishnu berstana")
    out = re.sub(r"(^|(?<=[.!?]\s)|\n)\s*(?:ketentuan|aturan|syarat|larangan|pantangan)"
                 r"(?:\s+(?:pemakaian|penggunaan|pelaksanaan|pemujaan)(?:nya)?)?\s+((?:[\w-]+\s+){0,3}?[\w-]+)"
                 r"(?:\s+(?:dalam|pada|untuk)(?:\s+[\w-]+){1,3}?)?\s+(?:adalah|ialah|yaitu)\s+(?:bahwa\s+)?"
                 r"(?:beliau|ia|dia)\b", lambda m: m.group(1) + m.group(2)[:1].upper() + m.group(2)[1:],
                 answer, flags=re.I)
    out = re.sub(r"(^|(?<=[.!?]\s)|\n)\s*(?:ketentuan|aturan|syarat|larangan|pantangan)(?:\s+[\w-]+){0,8}?"
                 r"\s+(?:adalah|ialah|yaitu)\s+(?:bahwa\s+)?(\w)", lambda m: m.group(1) + m.group(2).upper(),
                 out, flags=re.I)
    if not (_UNRECORDED_RE.search(out) or re.search(r"\btidak ada (?:ketentuan|aturan|larangan|syarat)", out, re.I)):
        out = "Ketentuan atau aturan khusus untuk hal tersebut tidak tercatat di basis data. " + out.lstrip()
    return out


_GENERIC_MISS_RE = re.compile(r"^(\s*Maaf, )informasi detail mengenai hal tersebut(?= belum tercatat)")


def _name_missing(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]], families: List[str],
                  class_list: Optional[tuple]) -> Text:
    """Rule 5's refusal says what is missing, as a template's miss does ("Maaf, sarana X belum
    tercatat"): "Maaf, informasi detail mengenai hal tersebut belum tercatat" was the whole answer to "apa
    maknanya" about banten pamegat (Tier B 2026-10-09) and to 57 sarana / pelaku / komponen questions of
    the NLU sweep (2026-10-19). A class list names the class and the term it scopes ("banten untuk
    wayang"). A why or consequence question misses a reason or an outcome, as rules 21 and 30 have the
    model say it ("Maaf, alasannya / akibatnya belum tercatat")."""
    if not enriched or not _GENERIC_MISS_RE.match(answer):
        return answer
    keys = [f for f in ("simbol", "fungsi") if f in families] or (
        families if len(families) == 1 and families[0] in _FOCUS_LABELS else [])
    rule = _RULE_Q_RE.search(user_msg)
    if _CONSEQUENCE_Q_RE.search(user_msg):
        what = "akibatnya"
    elif _WHY_Q_RE.search(user_msg):
        what = "alasannya"
    elif rule and len(enriched) == 1 and not class_list:
        # "apa larangan saat sorohan" -> "Maaf, larangan untuk sorohan belum tercatat"
        what = f"{re.sub(r'nya$', '', rule.group(0).lower())} untuk {enriched[0]['name']}"
    elif class_list:
        what = f"{class_list[0]} untuk {_join_names(class_list[1])}"
    elif _WORD_MEANING_RE.search(user_msg):
        # as the asal_kata template says it (its words follow the term: "arti kata pitra yadnya")
        what = f"{_word_label(user_msg)} {enriched[0]['name']}"
    elif len(enriched) == 1 and re.search(r"\b(?:harga\w*|biaya\w*|ongkos\w*|tarif\w*)\b", user_msg, re.I):
        # "berapa harga upacara ngaben" (2026-10-27)
        what = f"harga atau biaya {enriched[0]['name']}"
    elif keys and len(enriched) == 1:
        what = f"{' atau '.join(_aspect_label(k, user_msg) for k in keys)} {enriched[0]['name']}"
    else:
        return answer
    return _GENERIC_MISS_RE.sub(lambda m: m.group(1) + what, answer, count=1)


def _lead_with_asked_aspect(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]],
                            families: List[str], previous: Optional[Text] = None) -> Text:
    """A meaning, purpose or why question whose answer opens (first two sentences) with nothing
    of that aspect: the answer's own later sentence that says it about the asked term comes first,
    else the term's first fact of that aspect the answer never uses. The question is in the
    prompt twice and rule 2 says to open with the answer, and still "apa makna daksina" opened
    with what daksina contains and "apa guna patulangan" with its material (2026-10-08 replay).
    An answer opening "Makna (dari) X adalah ..." when nothing records it (one term, not a why --
    rule 21's): the answer says so first -- rule 23 alone let "Makna dari banten pamegat adalah
    sarana ritual ..." (its definition) stand as the meaning. Not a why-avoided question:
    _complete_stated_reasons gives its judging sentence."""
    keys = [f for f in ("simbol", "fungsi") if f in families]
    if (not enriched or not keys or answer.lstrip().startswith("Maaf")
            or _CONSEQUENCE_Q_RE.search(user_msg) or _LIST_Q_RE.search(user_msg)
            or _WHY_Q_RE.search(user_msg) and _WHY_AVOID_Q_RE.search(user_msg)
            # "apa itu tirta pangentas, dari mana diperoleh, dan apa fungsinya?": what it is comes first
            or _asks_what_is_first(user_msg, enriched)):
        return answer
    why = _WHY_Q_RE.search(user_msg)
    marker = re.compile(r"\b(?:" + "|".join(_FOCUS_MARKERS[k] for k in keys)
                        + ("|" + _REASON_MARKERS if why else "") + r")\b", re.I)
    # an opening that gives a purpose for a meaning question, or the reverse, answers it ("apa makna
    # ngaben": "Tujuannya adalah memusnahkan jasad sawa ...")
    answers = re.compile(r"\b(?:" + "|".join(_FOCUS_MARKERS.values())
                         + ("|" + _REASON_MARKERS if why else "") + r")\b", re.I)
    sents = _sentences(answer)
    if not sents:
        return answer
    if previous:
        # the turn before was about the same term (`previous`, its answer): a later sentence it
        # already said that says nothing of the asked aspect nor the question's own words goes --
        # "apa makna bade tingkat 7" after "... tingkat 9" said "jumlah mangle ... bergantung pada
        # tingkatan bade" again (2026-10-09 replay). The answering sentence always stays: cutting
        # every repeat cut "apa guna patulangan"'s own answer (2026-10-08).
        specifics = _asked_specifics(user_msg, enriched)
        prior = [r for r in (_sentence_roots(p) for p in _sentences(previous)) if r]
        for s in sents[1:]:
            roots = _sentence_roots(s)
            if (len(roots) >= 5 and not answers.search(_VAGUE_ASPECT_RE.sub("", s))
                    and not any(re.search(rf"\b{re.escape(w)}\b", s, re.I) for w in specifics)
                    and any(len(roots & p) >= 0.8 * len(roots) for p in prior)):
                answer = answer.replace(s, "", 1)
        answer = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", re.sub(r"[ \t]{2,}", " ", answer)).strip()
        sents = _sentences(answer)
    e = enriched[0]
    preds = set().union(*(PREDICATE_FAMILIES[k] for k in keys))
    pool = list(e.get("aspect_facts") or [])
    pool += [r["statement"] for r in e.get("relationships") or []
             if r.get("relation") in preds and r.get("outgoing") and r.get("statement")]
    pool += [s for s in _sentences(e.get("definition")) if marker.search(s)]
    names = "|".join(re.escape(n) for n in [e["name"], e.get("asked_as")] if n)
    # "Makna dari X adalah ...", or "X memiliki makna sebagai sarana ritual ..." (Tier B 2026-10-09)
    claim = re.match(rf"^\s*(?:makna|arti|fungsi|tujuan|kegunaan|guna|peran)(?:nya)?\s+(?:dari\s+)?"
                     rf"(?=(?:{names})\s+(?:adalah|ialah|yaitu|merupakan)\b)", answer, re.I)
    claim_as = re.match(rf"^\s*(?:{names})\s+(?:(?:memiliki|mempunyai)\s+(?:makna|arti|fungsi|peran)(?:nya)?|bermakna)"
                        rf"\s+(?:sebagai|yaitu|yakni)\s+", answer, re.I)
    # Whether anything about the term states the aspect, read off the context rather than off the
    # answer's wording: given the definition again, the model also wrote it plainly, with only the
    # repeat note to say nothing more is known. A purpose counts for a meaning; for a purpose
    # question a bare "untuk"/"digunakan" counts too (banten byakawonan "untuk menetralkan ...").
    recorded = re.compile(r"\b(?:" + "|".join(_FOCUS_MARKERS.values())
                          + (r"|untuk|digunakan|dipakai|dipergunakan|dihaturkan" if "fungsi" in keys else "")
                          + r")\b", re.I)
    sources = ([e.get("definition") or ""] + list(e.get("aspect_facts") or [])
               + [t for r in e.get("relationships") or []
                  for t in (r.get("statement") if r.get("outgoing") else "", r.get("target_definition"))
                  if t])
    # an absence asserted where it is only unrecorded: "Bali Dataran tidak memiliki simbolisme khusus."
    # (NLU sweep 2026-10-19) -- that sentence says so plainly, the rest stays
    denial = re.match(rf"^\s*(?:{names})\s+tidak\s+(?:memiliki|mempunyai)\s+(?:simbolisme|makna|arti|fungsi|peran|"
                      rf"tujuan)(?:\s+(?:khusus|tertentu|apa\s*pun))?\s*\.\s*", answer, re.I)
    if denial and not (len(enriched) > 1 or _WHY_Q_RE.search(user_msg)
                       or any(_aspect_present(k, enriched) for k in keys)
                       or any(recorded.search(t) for t in sources)):
        rest = answer[denial.end():].strip()
        return (f"Maaf, {' atau '.join(_FOCUS_LABELS[k] for k in keys)} {e['name']} belum tercatat di basis data."
                + (f" {rest}" if rest else ""))
    # said to be unrecorded and nothing more: "Makna banten pamegat tidak tercatat secara detail dalam
    # basis data." (rule 23, Tier B 2026-10-09) -- what IS recorded is still given
    owned = re.search(r"\b(?:belum|tidak) (?:tercatat|dijelaskan|disebutkan)\b", answer, re.I)
    bare = bool(owned and len(sents) == 1 and _first_sentence(e.get("definition")))
    if (claim or claim_as or bare or "simbol" in keys) and (bare or not owned) and not (
            len(enriched) > 1 or _WHY_Q_RE.search(user_msg)
            or any(_aspect_present(k, enriched) for k in keys)
            or any(recorded.search(t) for t in sources)):
        label = " atau ".join(_FOCUS_LABELS[k] for k in keys)
        body = (_known_sentence(e.get("definition")) if bare
                else answer[claim.end():].strip() if claim
                else f"{e['name']} adalah {answer[claim_as.end():].strip()}" if claim_as else answer.strip())
        return (f"Maaf, {label} {e['name']} belum tercatat di basis data. "
                f"Yang tercatat tentang {e['name']}: {body[:1].upper()}{body[1:]}")
    if any(answers.search(_VAGUE_ASPECT_RE.sub("", s)) for s in sents[:2]):
        return answer
    surfaces = [_ortho_key(n) for n in [e["name"], e.get("asked_as")] + list(e.get("aliases") or []) if n]
    # moving a sentence would scramble a list. Not one that only says there is a meaning ("...
    # memiliki makna simbolis dalam ritual ini").
    if not re.search(r"(?m)^\s*(?:\d+\.|[-*•])\s", answer):
        for s in sents[2:]:
            lead = _LEAD_CONNECTIVE_RE.sub("", s, count=1)
            if (marker.search(_VAGUE_ASPECT_RE.sub("", lead)) and not _LEANS_BACK_RE.match(lead)
                    and any(k and k in _ortho_key(lead) for k in surfaces)):
                # "Daksina juga menjadi perwujudan ..." opens the answer now
                lead = re.sub(r"^((?:[\w-]+\s+){1,3}?)juga\s+", r"\1", lead, count=1)
                rest = re.sub(r"[ \t]{2,}", " ", answer.replace(s, "", 1)).strip()
                return f"{lead[:1].upper()}{lead[1:]} {rest}"
    said = _sentence_roots(answer)
    for fact in pool:
        fact = _LEAD_CONNECTIVE_RE.sub("", fact, count=1).strip()
        roots = _sentence_roots(fact)
        if roots and len(roots & said) * 2 < len(roots) and not _LEANS_BACK_RE.match(fact):
            return f"{fact[:1].upper()}{fact[1:].rstrip('.')}. {answer.lstrip()}"
    return answer


# "apakah masyarakat umum boleh memakai bade?" (T73)
# ... and its everyday form, "ngaben pas purnama boleh gak?": read as no permission question, it skipped
# _stated_rule_answer, which answers "boleh saat hari pasah?" from dewasa ngaben's rule, and Qwen's right "Tidak,
# ... tidak boleh dilaksanakan pada hari purnama" got "Tidak ada larangan yang tercatat" put in front (plan #16)
_PERMISSION_Q_RE = re.compile(r"\bapa(kah)?\b.*\b(boleh|harus|wajib|dilarang)\b|\bbolehkah\b|\bharuskah\b"
                              rf"|\b(?:boleh|harus|wajib|dilarang)\b(?=.*(?:{_CASUAL_YES_NO_RE.pattern}))", re.I)

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
# "apakah upacara ngaben bisa dipimpin oleh pemangku tanpa sulinggih?" -> "Tidak, upacara ngaben
# tidak bisa dipimpin oleh pemangku ... pemangku tidak memiliki otoritas ..." (2026-10-07 batch),
# reasoned from rank alone: the context only said a sulinggih is "berwenang memimpin" and a
# pemangku ranks below one, and the corpus has pemangku leading acara (L147, L177) and "Sulinggih
# dan Pemangku bertugas muput" (L56). A can-it question is checked like a may-it question, with
# its own claim words: "tidak dapat" is everywhere in the KB ("tidak dapat ditemukan kembali"),
# so it cannot join _PROHIBITION_RE, which also tests the context. An "only X can" sentence is the
# restriction such a claim needs.
_CAPABILITY_Q_RE = re.compile(r"\bapa(kah)?\b.*\b(bisa|dapat)\b|\bbisakah\b|\bdapatkah\b", re.I)
_INCAPACITY_RE = re.compile(r"\btidak (?:bisa|dapat|berwenang|berhak)\b"
                            r"|\btidak memiliki (?:otoritas|wewenang|kewenangan|hak)\b", re.I)
_RESTRICTION_RE = re.compile(r"\bhanya\b[^.!?\n]*\b(?:dapat|bisa|boleh|berwenang|oleh)\b", re.I)


# words every rule question and rule sentence share, which say nothing about WHAT is ruled on
_RULE_TALK_ROOTS = frozenset(_root(w) for w in (
    "boleh", "bolehkah", "bisa", "bisakah", "dapat", "dapatkah", "harus", "haruskah", "wajib", "dilarang",
    "larangan", "hanya", "tidak", "dilakukan", "dilaksanakan", "digunakan", "dipakai", "diadakan", "dibuat",
    "upacara", "apakah"))


def _absent_asked_words(context_text: Text, user_msg: Text) -> set:
    """The question's rare words (not everyday, compared by root) the context never uses:
    "krematorium" in "apakah pembakaran jenazah boleh dilakukan di krematorium?"."""
    resolver = get_resolver()
    context_roots = {_root(w) for w in _WORD_RE.findall(context_text.lower())}
    return {w for w in _WORD_RE.findall(user_msg.lower())
            if len(w) >= 4 and w not in _STOPWORDS_ID and _root(w) not in _RULE_TALK_ROOTS
            and _root(w) not in context_roots and not _is_everyday_word(w, resolver)}


def _context_sentences(context_text: Text) -> List[str]:
    """The prompt context's sentences. It is JSON: a definition's last sentence ends in `."`, not
    in ". ", and split only at whitespace, pemangku's closing "tirtha pangentas tidak boleh dibuat
    oleh pemangku, hanya oleh sulinggih." ran on into `","relationships":[]},{"term":"sulinggih",
    "definition":"... memimpin ...` -- one "rule sentence" naming the asked act, which let "Tidak,
    upacara Ngaben tidak bisa dipimpin oleh pemangku" stand (Tier B 2026-10-15). Each unescaped quote
    (a JSON string's edge) ends a sentence too."""
    return re.split(r'(?<=[.!?;])\s+|\n|(?<!\\)"', context_text)


_WITHOUT_STOP = (r"(?:bisa|boleh|dapat|apa|apakah|gak|nggak|ngga|enggak|ga|ndak|tidak|sih|ya|kah|dilakukan"
                 r"|dilaksanakan|diadakan|atau|tetap|tetep|masih|sah|jalan|berjalan)")


def _without_what(user_msg: Text) -> Text:
    """The Y of "X tanpa Y bisa gak": what the question asks the act to go without ("sorohan kecil")."""
    m = re.search(rf"\btanpa\s+((?:(?!{_WITHOUT_STOP}\b)[\w-]+\s*){{1,4}})", user_msg, re.I)
    return m.group(1).strip() if m else ""


_NEED_RE = re.compile(r"\b(?:harus|wajib|mutlak|memerlukan|membutuhkan|syarat\w*|hanya)\b", re.I)


def _no_rule_line(user_msg: Text, context_text: Text, duty: bool = False) -> Text:
    """What a cut verdict leaves in front: no recorded rule, or for "X tanpa Y bisa gak" no recorded need of Y -- but
    only when no context sentence ties Y to a need: "Tirtha Pangentas hanya dapat dibuat oleh sulinggih" makes "tidak
    ada ketentuan ... memerlukan sulinggih" false for "bisa dipimpin oleh pemangku tanpa sulinggih?" (Tier B
    2026-11-02); that one keeps "tidak ada larangan"."""
    without = _without_what(user_msg)
    roots = {_root(w) for w in _WORD_RE.findall(without.lower()) if len(w) >= 4}
    if roots and not any(_NEED_RE.search(s) and roots <= {_root(w) for w in _WORD_RE.findall(s.lower())}
                         for s in _context_sentences(context_text)):
        return f"Tidak ada ketentuan yang tercatat bahwa hal tersebut memerlukan {without}."
    return f"Tidak ada {'kewajiban' if duty else 'larangan'} yang tercatat untuk hal tersebut."


def _rule_about_question(context_text: Text, user_msg: Text, rule_re, act: bool = False) -> bool:
    """Does a rule sentence of the context (one `rule_re` matches) rule on what the question
    asks? Any such sentence used to license every claim: ngaben's context always has one
    ("pada sasih kadasa tidak boleh membakar jenazah", "hanya dapat dilakukan oleh sulinggih" for
    tirta pangentas), so "Tidak, pembakaran jenazah tidak boleh dilakukan di krematorium" and
    "ngaben tidak bisa dipimpin oleh pemangku" stood (2026-10-08 batch). Now the question may name
    nothing rare the context never uses (krematorium appears nowhere), and the sentence must share
    two of the question's own words (by root, rule talk aside): "bolehkah ngaben dilakukan pada
    sasih kadasa" is ruled on by the kadasa sentence.
    `act` (a can-it question): the sentence must also name the asked act, a prefixed verb that is
    not rule talk. "tirtha pangentas tidak boleh dibuat oleh pemangku, hanya oleh sulinggih" shares
    pemangku and sulinggih with "apakah upacara ngaben bisa dipimpin oleh pemangku tanpa
    sulinggih?" but rules on making the tirtha, and let "Tidak, ... tidak bisa dipimpin oleh
    pemangku" stand (Tier B 2026-10-14, once pemangku's definition held that clause).
    "X tanpa Y": the sentence must name Y -- a rule of X alone says nothing about doing it without Y."""
    if _absent_asked_words(context_text, user_msg):
        return False
    asked = {_root(w) for w in _WORD_RE.findall(user_msg.lower())
             if len(w) >= 4 and w not in _STOPWORDS_ID} - _RULE_TALK_ROOTS
    acts = {_root(w) for w in _WORD_RE.findall(user_msg.lower())
            if act and re.match(r"(?:di|me|ber)", w) and _root(w) != w} - _RULE_TALK_ROOTS
    needed = {_root(w) for w in _WORD_RE.findall(_without_what(user_msg).lower()) if len(w) >= 4} - _RULE_TALK_ROOTS

    def near(a: Text, r: Text) -> bool:
        # the same root, or a 5+ letter one inside a longer one ("ngaben" in "pengabenan"). Not
        # min()/max() by length: for two roots of one length both return the first, and any two
        # (pimpin, tirtha) counted as shared (2026-10-14)
        short, long_ = sorted((a, r), key=len)
        return a == r or len(short) >= 5 and len(short) < len(long_) and short in long_

    def about(sentence: Text) -> bool:
        roots = {_root(w) for w in _WORD_RE.findall(sentence.lower())}
        return (sum(1 for a in asked if any(near(a, r) for r in roots)) >= 2
                and (not acts or any(near(a, r) for a in acts for r in roots))
                and all(any(near(n, r) for r in roots) for n in needed))
    return any(rule_re.search(s) and about(s) for s in _context_sentences(context_text))


def _fix_unstated_prohibition(answer: Text, context_text: Text, capability: bool = False,
                              user_msg: Text = "") -> Text:
    """A whether-question ("apakah masyarakat umum boleh memakai bade?"): a bare verdict
    line ("tidak boleh" alone, then the text) is cut, and when nothing in the context states a
    prohibition, so is every sentence claiming one -- the definition only says who usually
    uses the bade (T41/T73, Tier B 2026-10-01). "tidak ada larangan" is not a claim.
    `capability`: a can-it question (see _CAPABILITY_Q_RE); its "tidak bisa / tidak memiliki
    otoritas" claims go the same way, and a cut verdict leaves the recorded "no rule" in front."""
    answer = re.sub(r"^\s*(?:tidak boleh|boleh|tidak|ya)\s*[.!]?\s*\n\s*\n", "", answer, count=1)
    answer = answer[:1].upper() + answer[1:]
    if _rule_about_question(context_text, user_msg, re.compile(_PROHIBITION_RE.pattern + r"|\bdihindari\b", re.I),
                            act=capability):
        return answer
    if capability and _rule_about_question(context_text, user_msg, _RESTRICTION_RE, act=True):
        return answer
    # can the ceremony go ahead at all: a condition of the asked term decides it. "kalau di desa cuma ada
    # pemangku, ngabennya tetep bisa jalan gak?" -- "Tanpa Tirtha Pangentas, sebuah pengabenan dianggap belum
    # dilaksanakan" and only a sulinggih makes it -- had its correct "Tidak" turned into "Tidak ada larangan"
    # (#1861, LLM comparison 2026-10-20). Not "bisa dipimpin oleh pemangku" (who leads, see above).
    if capability and re.search(r"\b(?:jalan|berjalan|terlaksana|dilaksanakan|dilakukan|diadakan|sah)\b", user_msg, re.I):
        terms = {_root(w) for w in _WORD_RE.findall(user_msg.lower()) if len(w) >= 5} - _RULE_TALK_ROOTS
        for c in _context_sentences(context_text):
            if re.search(r"dianggap\s+belum\s+(?:dilaksanakan|lengkap|sah)|\btidak\s+sah\b|\bmutlak\b", c, re.I):
                roots = {_root(w) for w in _WORD_RE.findall(c.lower())}
                if any(t == r or len(t) >= 5 and t in r or len(r) >= 5 and r in t for t in terms for r in roots):
                    return answer
    # a bare "Tidak," opening a can-it answer is the incapacity claim on its own: "Tidak, ngaben
    # biasanya dipimpin oleh sulinggih" for "apakah upacara ngaben bisa dipimpin oleh pemangku tanpa
    # sulinggih?", whose hidden reasoning had found nothing that rules it out (2026-10-12). The
    # sentence after it is a fact and stays. So it is for a may-it question: "apakah lembu boleh
    # dilakukan saat umbi sikapa" opened "Tidak, lembu tidak digunakan ..." (NLU sweep 2026-10-19) --
    # not for must-it (harus / wajib), where "Tidak" says there is no duty, not a ban.
    may = re.search(r"\bboleh(?:kah)?\b|\bdilarang\b", user_msg, re.I)
    bare_no = re.match(r"^\s*\**\s*tidak\s*\**\s*[,.]\s*", answer, re.I) if capability or may else None
    if bare_no:
        # its reason stays without the connector: "Tidak, karena babelonyoh dan emas adalah dua hal yang berbeda" left
        # "... memerlukan Emas. Karena babelonyoh dan emas ..." (V3 run 2026-11-02)
        rest = re.sub(r"^(?:karena|sebab|dikarenakan)\s+", "", answer[bare_no.end():], flags=re.I)
        answer = _no_rule_line(user_msg, context_text) + " " + rest[:1].upper() + rest[1:]
    parts = re.findall(r"[^.!?\n]+[.!?]*", answer)
    # a sentence about what the context never names can only be the model's reasoning:
    # "Krematorium tidak sesuai untuk upacara Ngaben karena tidak memenuhi persyaratan ritual"
    absent = _absent_asked_words(context_text, user_msg)

    def content_roots(text: Text) -> set:
        return {_root(w) for w in _WORD_RE.findall(text.lower()) if len(w) >= 4 and w not in _STOPWORDS_ID}
    # a sentence restating a rule the context states (about another act) stays: "tirtha pangentas
    # tidak boleh dibuat oleh pemangku dan hanya dapat dibuat oleh sulinggih" is what a ngaben without
    # a sulinggih turns on, and went with the invented "tidak bisa dipimpin oleh pemangku" (2026-10-14)
    context_rules = [content_roots(c) for c in _context_sentences(context_text)
                     if _PROHIBITION_RE.search(c) or _RESTRICTION_RE.search(c)]

    def restates_rule(s: Text) -> bool:
        roots = content_roots(s) - _RULE_TALK_ROOTS
        return bool(roots) and any(len(roots & r) >= 0.7 * len(roots) for r in context_rules)
    # "... larangan atau kewajiban ... belum tercatat di basis data" says no rule is recorded: cut as a claim, it
    # left "Tidak ada larangan yang tercatat" as the answer to "apakah niskala wajib" (plan #16, 2026-10-26)
    drop = [s for s in parts if (_PROHIBITION_RE.search(s) or capability and _INCAPACITY_RE.search(s)
                                 or any(re.search(rf"\b{re.escape(w)}\b", s, re.I) for w in absent))
            and not re.search(r"\btidak ada (?:larangan|aturan)|\bbukan larangan"
                              r"|\b(?:tidak|belum) (?:tercatat|disebutkan|dijelaskan)|\btidak (?:mencatat|menyebutkan)\b",
                              s, re.I)
            and not restates_rule(s)]
    if not drop or len(drop) == len([s for s in parts if s.strip()]):
        return answer
    # a cut opening verdict leaves the recorded "no rule" in front, for may-it questions too:
    # "Tidak, pembakaran jenazah tidak boleh dilakukan di krematorium." (2026-10-08 batch)
    verdict_cut = bool(parts) and parts[0] in drop
    for s in drop:
        # the reason given for a cut claim stays, but no longer points back: "Tidak, ... tidak bisa dipimpin oleh
        # pemangku. Hal ini karena Ngaben dipimpin oleh sulinggih" became "Tidak ada larangan yang tercatat ... Hal
        # ini karena ..." (Tier B 2026-10-30)
        reason = re.search(re.escape(s) + r"(\s*)(?:hal ini|ini|hal tersebut|hal itu)\s+(?:karena|disebabkan(?:\s+oleh)?"
                           r"|dikarenakan)\s+(\w)", answer, re.I)
        if reason:
            answer = answer[:reason.start()] + reason.group(1) + reason.group(2).upper() + answer[reason.end():]
        else:
            answer = answer.replace(s, "", 1)
    answer = re.sub(r"[ \t]{2,}", " ", answer).strip()
    if verdict_cut:
        must = (re.search(r"\b(?:harus|haruskah|wajib)\b", user_msg, re.I)
                and not re.search(r"\bboleh(?:kah)?\b|\bdilarang\b", user_msg, re.I))
        answer = _no_rule_line(user_msg, context_text, duty=bool(must)) + " " + answer
    return answer


# "Tidak, informasi mengenai ... tidak tercatat di basis data.", "Tidak, tidak ada aturan yang menyatakan ..."
_HOLLOW_VERDICT_RE = re.compile(
    r"^\s*\**\s*(?:ya|tidak)\s*\**\s*,\s*(?=[^.!?\n]*\b(?:(?:tidak|belum)\s+(?:tercatat|disebutkan|dijelaskan)"
    r"|tidak\s+ada\s+(?:aturan|informasi|keterangan|catatan|larangan|ketentuan|hubungan)))", re.I)


# the seven-day week names before a five- or three-day one ("saniscara kliwon"), and those day names
_SAPTAWARA_RE = r"(?:redite|soma|anggara|budh?a|wrh?aspati|wrespati|sukra|saniscara)"
_LONE_DAY_NAMES = ("umanis", "paing", "pon", "wage", "kliwon", "pasah", "beteng", "kajeng")
_AVOID_RE = re.compile(r"\b(?:di|meng?|ter)?hindar\w*|\btidak boleh\b|\bdilarang\b|\bpantang\b|\btidak baik\b"
                       r"|\bburuk\b", re.I)
_NOT_AVOIDED_RE = re.compile(r"\btidak\s+(?:perlu\s+|harus\s+)?dihindari\b|\bbukan\b", re.I)


def _fix_lone_day_claims(answer: Text, context_text: Text) -> Text:
    """A pancawara / triwara day called avoided on its own when the context avoids it only within a
    combined day: "Kliwon berhubungan dengan Pitra Yadnya sebagai salah satu nama hari dalam siklus
    pancawara yang harus dihindari" -- the KB avoids saniscara, buda and anggara kliwon, and only for a
    Ngaben within seven days of death (a slip logged 2026-10-05, still there on Qwen 3.8, Tier B
    2026-10-27). In a list the day becomes its combined days; elsewhere its sentence goes -- a first
    sentence becomes "<condition>, yang dihindari bukan X saja, melainkan <combined days>.", which also
    closes an answer no longer naming them. A day the context avoids alone (pasah) is left as said."""
    ctx = _context_sentences(context_text)
    for day in _LONE_DAY_NAMES:
        day_re = re.compile(rf"\b(?:({_SAPTAWARA_RE})\s+)?{day}\b", re.I)
        combos, lone_avoided, cond = [], False, ""
        for s in ctx:
            hits = list(day_re.finditer(s))
            if any(not m.group(1) for m in hits) and _AVOID_RE.search(s):
                lone_avoided = True
            for m in hits:
                if m.group(1) and m.group(0).lower() not in combos:
                    combos.append(m.group(0).lower())
                    cond = cond or (re.match(r"\s*((?:bila|jika|kalau|apabila)\b[^,]*),", s, re.I) or [None, ""])[1]
        if lone_avoided or not combos or not re.search(rf"\b{day}\b", answer, re.I):
            continue
        combo_text = (", ".join(combos[:-1]) + ", dan " + combos[-1]) if len(combos) > 1 else combos[0]
        parts = re.split(r"((?<=[.!?])\s+)", answer)
        changed = False
        for i in range(0, len(parts), 2):
            s = parts[i]
            lone = [m for m in day_re.finditer(s) if not m.group(1)]
            if not lone or any(m.group(1) for m in day_re.finditer(s)) or not _AVOID_RE.search(s) \
                    or _NOT_AVOIDED_RE.search(s):
                continue
            m = lone[0]
            before, after = s[:m.start()].rstrip(), s[m.end():]
            # a list item, not the subject after a verdict ("Ya, kliwon dihindari")
            verdict = re.fullmatch(r"\s*(?:ya|tidak|benar|betul|bukan)\s*,", before, re.I)
            if not verdict and (before.endswith(",") or re.search(r"\b(?:dan|atau|serta)$", before, re.I)
                                or after.startswith(",")):
                parts[i] = s[:m.start()] + ", ".join(combos) + s[m.end():]
            else:
                parts[i] = ""
            changed = True
        if not changed:
            continue
        rest = "".join(p for j, p in enumerate(parts) if j % 2 == 0)
        if not parts[0] or not any(c in rest.lower() for c in combos):
            fix = (f"{cond}, yang dihindari" if cond else "Yang dihindari") + \
                  f" bukan {day} saja, melainkan {combo_text}."
            fix = fix[:1].upper() + fix[1:]
            if not parts[0]:
                parts[0] = fix
            else:
                parts.append(" " + fix)
        # the separators a removed sentence leaves behind
        answer = re.sub(r"[ \t]{2,}", " ", "".join(parts))
        answer = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", answer)).strip()
    return answer


def _drop_hollow_verdict(answer: Text) -> Text:
    """A whether-answer opening "Ya," / "Tidak," whose own sentence then says nothing recorded decides
    it: the verdict word is cut, the sentence stays. "apakah Hyang Prajapati juga dipakai dalam purnama?"
    -> "Tidak, informasi mengenai ... tidak tercatat di basis data." read as a "no" (NLU sweep 2026-10-19)."""
    m = _HOLLOW_VERDICT_RE.match(answer)
    if not m:
        return answer
    rest = answer[m.end():]
    return rest[:1].upper() + rest[1:]


def _complete_terse_verdict(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A whether-answer that is one "Ya/Tidak" sentence naming a term an asked term links to gets that term's
    gloss: "apakah ngaben wajib" got only "Ya, ngaben adalah kewajiban suci (swadharma)." -- swadharma is
    "kewajiban anak/keturunan untuk mengupacarai (mengaben) orang tua atau leluhur", and ngaben's context was
    too big to keep that related-term gloss (Tier B 2026-10-26; rules 2-3 ask for the reason)."""
    if len(_sentences(answer)) != 1 or not re.match(r"\s*(?:ya|tidak)\b", answer, re.I):
        return answer
    asked = {e["id"] for e in enriched}
    linked = {r.get("target_id") for e in enriched for r in e.get("relationships") or []}
    content = get_content()
    for tid in _named_terms(answer):
        if tid in asked or tid not in linked:
            continue
        known = _known_sentence(content.best_definition(tid))
        if not known:
            continue
        name = content.entity_name.get(tid, tid)
        if not (re.match(rf"\s*{re.escape(name)}\b", known, re.I) or _definition_subject(known, tid, name)):
            known = f"{name[:1].upper()}{name[1:]} adalah {known[:1].lower()}{known[1:]}"
        return f"{answer.rstrip()} {known}"
    return answer


# a sentence saying who usually uses the term ("Bade dan lembu lazimnya dipakai golongan
# berkasta lebih tinggi.") and any rule a sentence may state instead
_USAGE_NORM_RE = re.compile(r"\b(?:lazim(?:nya)?|biasanya|umumnya)\b[^.]*\b(?:dipakai|memakai|digunakan|menggunakan)\b"
                            r"|\b(?:dipakai|memakai|digunakan|menggunakan)\b[^.]*\b(?:lazim(?:nya)?|biasanya|umumnya)\b",
                            re.I)
# (and a stated condition: ulah pati's "diupacarai sesuai kemampuan, asal ia mati dengan benar (tidak salah ulah pati)"
# answers "orang yang meninggal karena bunuh diri boleh diaben gak?" -- Qwen read it as "tidak memenuhi syarat untuk
# diupacarai", Tier B 2026-10-30. Not a bare "asal": "asal kata" is a word's origin)
_RULE_STATED_RE = re.compile(r"\bboleh\b|\bdilarang\b|\blarangan\b|\bpantang\b|\bdiperkenankan\b|\bdihindari\b"
                             r"|\bwajib\b|\bharus\b|\bhanya\b|\basal(?:kan)?\s+(?:ia|tidak)\b|\bdengan syarat\b", re.I)


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


_USERS_Q_RE = re.compile(r"\b(?:kalangan|golongan|kasta|berkasta|masyarakat|warga|wangsa|rakyat)\b", re.I)


def _complete_usage_norms(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A question about who uses the term ("kenapa bade hanya untuk kalangan tertentu") gets every
    "lazimnya/biasanya dipakai ..." sentence of its definition that the answer mostly left out:
    the model gave bade's tiers and "lazimnya dipakai oleh golongan berkasta lebih tinggi" and
    dropped the other half, "Wadah ... lazimnya dipakai oleh warga (klan) dan masyarakat yang
    tidak berkasta", on two fresh loads in three (Tier B 2026-10-08)."""
    if not enriched:
        return answer
    said = _sentence_roots(answer)
    for s in _sentences(enriched[0].get("definition")):
        roots = _sentence_roots(s)
        if _USAGE_NORM_RE.search(s) and roots and len(roots & said) * 2 < len(roots):
            answer = answer.rstrip() + " " + s
            said |= roots
    return answer


def _stated_rule_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A whether-question whose term's definition states the rule for the asked act: that
    sentence first, then the definition's other sentences sharing a question word, as written.
    "apakah bayi yang giginya belum tanggal boleh dibakar?" -- jenazah bayi's definition says
    "hanya anak berusia lima bulan ke atas yang boleh ... dibakar" and gives the age tiers, yet
    the model answered "tidak perlu atau boleh dibakar" from the youngest tiers (Tier B
    2026-10-02). None when no sentence states a rule about a word of the question."""
    if not enriched or not _PERMISSION_Q_RE.search(user_msg):
        return None
    # the used term, then the day rules when they were added for a named day ("ngaben pas purnama boleh gak?":
    # ngaben's definition rules nothing on purnama, dewasa ngaben's does)
    used = _used_term(user_msg, enriched)
    for e in [used] + [x for x in enriched if x["id"] == "dewasa_ngaben" and x is not used]:
        name_words = _content_words(" ".join([e["name"]] + list(e.get("aliases") or [])))
        asked = {w for w in _content_words(user_msg)
                 if w not in name_words and not _RULE_STATED_RE.search(w)}
        sentences = _sentences(e.get("definition"))

        def shares(s: str) -> bool:
            return any(_grounded(w, _content_words(s)) for w in asked)
        rules = [s for s in sentences if _RULE_STATED_RE.search(s) and shares(s)] if asked else []
        if rules:
            break
    else:
        return None
    verdict, clauses = _rule_verdict(user_msg, rules, asked)
    if verdict:
        # only what rules on the asked thing: dewasa ngaben's whole wuku sentence and the
        # seven-day exception buried "pasah" ("only the important and relevant ones", 2026-10-07)
        return f"{verdict} " + " ".join(c.strip().rstrip(".") + "." for c in clauses)
    return " ".join(rules + [s for s in sentences if s not in rules and shares(s)])


def _stated_prohibition_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A who / what question about a ban, not a whether-question: the asked term's definition sentences stating a
    ban that share a word of the question, as written. "siapa yang tidak boleh ikut sembah bhakti" got "Sembah
    bhakti dipimpin oleh pemangku" from the doer template, while sembah bhakti's definition says "Yang pantang ikut
    menyembah pitara: wanita yang sedang datang bulan, ..." (the 12 evaluation categories, 2026-10-27)."""
    # (not "apa larangan saat X", a rule question, nor a day question: _avoided_days_answer says those)
    if (not enriched or _whether_question(user_msg) or any(x["id"] == "dewasa_ngaben" for x in enriched)
            or not re.search(r"\b(?:tidak\s+boleh|dilarang|pantang|tidak\s+diperkenankan)\b", user_msg, re.I)
            or not re.search(r"\b(?:siapa|apa|mana)\b", user_msg, re.I)):
        return None
    e = _used_term(user_msg, enriched)
    name_words = _content_words(" ".join([e["name"]] + list(e.get("aliases") or [])))
    asked = {w for w in _content_words(user_msg) if w not in name_words and not _RULE_STATED_RE.search(w)
             and w not in {"siapa", "apa", "mana", "saja", "yang"}}
    # with nothing asked beside the ban ("siapa yang tidak boleh ikut X": "ikut" is no content word), every ban the
    # term's definition states
    bans = [s for s in _sentences(e.get("definition"))
            if _NEG_RULE_RE.search(s) and (not asked or any(_grounded(w, _content_words(s)) for w in asked))]
    # and what the library forbids during it, as an edge on it: "apa yang tidak boleh dilakukan saat ngaben" -- Qwen
    # answered "menangis tidak boleh dilakukan saat ngaben" and _fix_unstated_prohibition cut it (2026-10-27). Said by
    # the forbidden thing's own first sentence when that states the ban (menangis: why, FAQ L73)
    content = get_content()
    for r in e.get("relationships") or []:
        if r.get("outgoing") or not re.search(r"TIDAK_BOLEH|DILARANG|PANTANG", r.get("relation") or ""):
            continue
        first = _first_sentence(content.best_definition(r.get("target_id")), limit=10 ** 6)
        said = first if first and _NEG_RULE_RE.search(first) else (r.get("statement") or "")
        if said:
            bans.append(said)
    return " ".join(_distinct_sentences(bans)) or None


_DEFINITION_ASK_RE = re.compile(r"\W*(?:apa\s+itu|apa\s+yang\s+dimaksud(?:\s+dengan)?|jelaskan|pengertian|definisi)"
                                r"\s+(?:dan|serta|,)?\s*(?:dan|serta)?\W*", re.I)


def _two_definitions_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """"apa itu pitra dan pramakusa", "jelaskan nganyut dan pabersihan": two definitions and nothing more asked --
    each term's definition, as the definition template gives it (they went to Qwen; route audit 2026-10-27)."""
    if len(enriched) != 2 or _aspect_families(user_msg) or _WHY_Q_RE.search(user_msg):
        return None
    resolver = get_resolver()
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    if leftover or {m.id for m, _ in mentioned} != {e["id"] for e in enriched}:
        return None
    rest = user_msg
    for _, surface in mentioned:
        rest = re.sub(rf"(?<![\w-]){re.escape(surface)}(?![\w-])", " ", rest, flags=re.I)
    if not _DEFINITION_ASK_RE.fullmatch(rest):
        return None
    parts = [_deterministic_answer([dict(e, aspect_facts=[])]) for e in enriched]
    return "\n\n".join(p for p in parts if p) if all(parts) else None


_NEG_RULE_RE = re.compile(r"\b(?:tidak boleh|tidak diperbolehkan|tidak diperkenankan|dilarang|dihindari|pantang|"
                          r"tidak baik)\b", re.I)
_POS_RULE_RE = re.compile(r"(?<!tidak )\b(?:boleh|dibolehkan|diperbolehkan|baik|utama)\b", re.I)


def _rule_verdict(user_msg: Text, rules: List[Text], asked: set) -> tuple:
    """The verdict a quoted rule gives, to open the answer: "apakah ngaben boleh dilakukan saat
    hari pasah?" was answered with dewasa ngaben's whole wuku sentence, pasah somewhere in its
    middle (2026-10-08 batch; conersation.md 2026-10-07: "it doesnt immedietly make it clear that
    it has answered the question"). Each clause naming one of the question's rare words rules on
    it with the first rule word after it, else the last one before it; one verdict only when
    every such clause agrees -- jenazah bayi's age tiers say both, and get none. Returns
    (verdict or None, the clauses that ruled). None for a must-question."""
    if re.search(r"\b(?:harus|haruskah|wajib)\b", user_msg, re.I):
        return None, []
    resolver = get_resolver()
    keys = [w for w in asked if not _is_everyday_word(w, resolver)]
    verdicts, clauses = set(), []
    for s in rules:
        for clause in s.split(";"):
            for k in keys:
                for m in re.finditer(rf"\b{re.escape(k)}\b", clause, re.I):
                    hits = [(x.start(), True) for x in _NEG_RULE_RE.finditer(clause)]
                    hits += [(x.start(), False) for x in _POS_RULE_RE.finditer(clause)]
                    after = sorted(h for h in hits if h[0] >= m.end())
                    before = sorted(h for h in hits if h[0] < m.start())
                    pick = after[0] if after else (before[-1] if before else None)
                    if pick:
                        verdicts.add(pick[1])
                        if clause not in clauses:
                            clauses.append(clause)
    if len(verdicts) != 1:
        return None, []
    forbidden = verdicts.pop()
    if re.search(r"\b(?:dilarang|larangan|pantang)\b", user_msg, re.I):
        return ("Ya, dilarang." if forbidden else "Tidak dilarang."), clauses
    return ("Tidak boleh." if forbidden else "Boleh."), clauses


# a good-day question: "hari baik ngaben", "kapan waktu yang tepat untuk ngaben", "hari baik apa
# saja yang cocok" -- not one about days to avoid, a reason, or a permission
_GOOD_DAY_Q_RE = re.compile(r"\b(?:baik|tepat|cocok|terbaik|bagus)\b", re.I)
_AVOID_DAY_Q_RE = re.compile(r"\b(?:dihindari|hindari|buruk|tidak boleh|dilarang|pantang|kenapa|mengapa|alasan|"
                             r"boleh|bolehkah)\b", re.I)


def _good_days_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """"hari baik ngaben" got dewasa ngaben's whole definition, the forbidden wuku before the
    allowed ones: "I like the content ... but it doesnt immedietly make it clear that it has
    answered the question ... Not all of the facs about sasih and wewaran need to be extracted
    too. only the important and relevant ones" (conersation.md 2026-10-07); rule 22 asks for
    exactly this order and the model kept the definition's (2026-10-08). Built from the
    definition's own clauses: the good sasih, then the allowed wuku/wewaran days, then one
    sentence on what is avoided, then the seven-day exception. Only for Ngaben itself: "sasih
    apa yang baik untuk atma wedana" needs the kadasa clause. None otherwise."""
    ids = {e["id"] for e in enriched}
    # "kapan ngaben boleh dilaksanakan" asks when it is allowed, not whether one day is (it went to the LLM, which
    # gave dewasa ngaben's definition; route audit 2026-10-27); "kapan dilakukan?" about Ngaben names no ngaben
    when = re.search(r"\bkapan\b", user_msg, re.I)
    avoid_q = _AVOID_DAY_Q_RE.search(re.sub(r"\bboleh(?:kah)?\b", " ", user_msg, flags=re.I) if when else user_msg)
    # "sasih apa yang baik untuk ngaben": the month half only
    calendar = ids & {"sasih", "wuku", "wewaran"}
    if ("dewasa_ngaben" not in ids or not ids - calendar <= {"dewasa_ngaben", "ngaben", "pitra_yadnya"}
            or not (_GOOD_DAY_Q_RE.search(user_msg) or _WHEN_NGABEN_RE.search(user_msg) or when)
            or avoid_q):
        return None
    rules = _dewasa_rules()
    if not rules or not rules["good_sasih"] or not rules["good_wuku"]:
        return None
    if calendar == {"sasih"}:
        return (f"Menurut sasih, {'; '.join(rules['good_sasih'])}."
                + (f" Yang dihindari: {'; '.join(rules['bad_sasih'])}." if rules["bad_sasih"] else ""))
    out = [f"Menurut sasih, {'; '.join(rules['good_sasih'])}.",
           f"Menurut wuku dan wewaran, {'; '.join(rules['good_wuku'])}."]
    avoid = list(rules["bad_sasih"])
    for c in rules["bad_wuku"]:
        rule = re.match(r"(.+?) tidak boleh dijadikan patokan, dan hari (.+?) tidak boleh dipakai$", c)
        avoid += ([f"{rule.group(1)} (tidak boleh dijadikan patokan)", f"hari {rule.group(2)}"] if rule else [c])
    if avoid:
        out.append(f"Yang dihindari: {'; '.join(avoid)}.")
    out += rules["seven_days"]
    return " ".join(out)


def _dewasa_rules() -> Optional[Dict[str, List[str]]]:
    """Dewasa ngaben's day rules as its own clauses: good and avoided sasih, good and avoided
    wuku/wewaran days, and the seven-day exception sentence. None if the definition lacks them."""
    sentences = _sentences(get_content().best_definition("dewasa_ngaben"))
    sasih = next((s for s in sentences if re.match(r"Berdasarkan sasih\b", s)), None)
    wuku = next((s for s in sentences if re.match(r"Berdasarkan wuku\b", s)), None)
    if not sasih or not wuku:
        return None

    def split(s: Text, lead: Text) -> tuple:
        good, bad = [], []
        for c in s.rstrip(".").split(";"):
            c = re.sub(rf"^\s*{lead},\s*", "", c.strip(), flags=re.I)
            (bad if _NEG_RULE_RE.search(c) or re.search(r"\bsasih mati\b", c, re.I) else good).append(c)
        return good, bad
    good_sasih, bad_sasih = split(sasih, "Berdasarkan sasih")
    good_wuku, bad_wuku = split(wuku, "Berdasarkan wuku dan wewaran")
    return {"good_sasih": good_sasih, "bad_sasih": bad_sasih, "good_wuku": good_wuku, "bad_wuku": bad_wuku,
            "seven_days": [s for s in sentences if re.search(r"\btujuh hari\b", s)]}


# "hari apa yang harus dihindari untuk ngaben (dan kenapa)": what to avoid, not whether one act is
# allowed (_stated_rule_answer)
_AVOIDED_DAYS_Q_RE = re.compile(r"\b(?:dihindari|hindari|buruk|pantang|tidak baik)\b", re.I)


def _avoided_days_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """Which days Ngaben avoids, and why if asked, from the sources' own clauses -- like
    _good_days_answer. On one load "hari apa yang harus dihindari untuk ngaben dan kenapa?" listed
    sasih dyestha and asada under "Menurut wuku dan wewaran", left out every avoided wewaran day and
    said the reason was not recorded (Tier B 2026-10-09). The reasons are the avoided sasih's own
    judging sentences (kadasa "mencemari ...", malamasa "Kata mala berarti ...", paruwak tahuk's
    lontar); no source says why the wuku/wewaran days are avoided, and the answer says so."""
    ids = {e["id"] for e in enriched}
    if ("dewasa_ngaben" not in ids or not ids <= {"dewasa_ngaben", "ngaben", "pitra_yadnya"}
            or not _AVOIDED_DAYS_Q_RE.search(user_msg) or _YES_NO_Q_RE.search(user_msg)):
        return None
    rules = _dewasa_rules()
    if not rules or not rules["bad_sasih"] or not rules["bad_wuku"]:
        return None
    out = [f"Menurut sasih, yang dihindari untuk Ngaben: {'; '.join(rules['bad_sasih'])}.",
           f"Menurut wuku dan wewaran, {'; '.join(rules['bad_wuku'])}."]
    out += rules["seven_days"]
    if _WHY_Q_RE.search(user_msg):
        # each avoided sasih's judging clauses, not its whole sentence (kadasa's opens with the
        # Uttarayana calendar), and not a clause already given (dyestha's and asada's say each other's)
        content, reasons, said = get_content(), [], set()
        for tid in _named_terms(" ".join(rules["bad_sasih"]), everyday=True):
            judging = next((s for s in _sentences(content.entity_def.get(tid) or "") if _JUDGEMENT_RE.search(s)), None)
            clauses = []
            for c in re.split(r"\s*;\s*|:\s+", (judging or "").strip().rstrip(".")):
                roots = _sentence_roots(c)
                if _JUDGEMENT_RE.search(c) and roots and len(roots & said) < 0.8 * len(roots):
                    clauses.append(c)
                    said |= roots
            if clauses:
                text = "; ".join(clauses)
                reasons.append(text[:1].upper() + text[1:] + ".")
        if reasons:
            out.append("Alasannya menurut sumber: " + " ".join(reasons))
        out.append("Alasan untuk hari-hari wuku dan wewaran tersebut belum tercatat di basis data.")
    return "\n\n".join([" ".join(out[:2 + len(rules["seven_days"])])] + out[2 + len(rules["seven_days"]):])


def _stated_reason_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A why-question about two terms whose definition states the reason, naming the other term
    with "karena / sebab / sehingga" and a word of the question: that term's opening sentence
    when it says the same, then the reason sentence, as written. "kenapa atma wedana hanya boleh
    dilakukan setelah ngaben" opened with "karena setelah ngaben, suksma sarira mendiang sudah
    disucikan" -- the reverse of the definition's "jiwanya masih berbadan halus ...; karena itulah
    Atma Wedana diselenggarakan setelah Ngaben, untuk menyucikan suksma sarira itu" -- on fresh
    loads (Tier B 2026-10-02/08). None otherwise."""
    if len(enriched) < 2 or not _WHY_Q_RE.search(user_msg) or _CONSEQUENCE_Q_RE.search(user_msg):
        return None
    # an order question only: with any shared word, "kenapa tidak boleh yadnya pada sasih paruwak
    # tahuk dan malamasa" got malamasa's "... sehingga upacara Panca Yadnya tidak dianjurkan" alone
    # through "tidak" (2026-10-08)
    asked = set(_ORDER_WORD_RE.findall(user_msg.lower()))
    if not asked:
        return None

    def shares(s: Text) -> bool:
        return any(re.search(rf"\b{re.escape(w)}\b", s, re.I) for w in asked)
    for e in enriched:
        others = [n for o in enriched if o is not e for n in [o["name"]] + list(o.get("aliases") or []) if len(n) >= 4]
        named = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in others) + r")\b", re.I) if others else None
        sentences = _sentences(e.get("definition"))
        for s in sentences:
            if named and named.search(s) and _DEPENDENCY_RE.search(s) and shares(s):
                lead = sentences[0]
                opening = [lead] if lead is not s and named.search(lead) and shares(lead) else []
                # the opening's list of other names reads as clutter here ("Atma Wedana (disebut
                # juga Ngroras atau Ngerorasin, Pangroras, ...) adalah ...")
                opening = [re.sub(r"\s*\((?:disebut|dikenal)\s+juga[^)]*\)", "", o) for o in opening]
                return " ".join(opening + [s])
    return None


_ORDER_WORD_RE = re.compile(r"\b(?:setelah|sesudah|sebelum|sebelumnya|sesudahnya|setelahnya)\b", re.I)


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
    # stage numbers only within a rite both are stages of: pangringkes is ngaben's stage 2 and nyiramang
    # layon's stage 5
    na = nb = None
    for rite in [f["object_id"] for f in get_content().facts_by_subj.get(a.get("id"), [])
                 if f["predicate"] == "BAGIAN_DARI"]:
        na, nb = _stage_number(a.get("definition"), rite), _stage_number(b.get("definition"), rite)
        if na and nb:
            break
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


def _set_members(e: Dict[str, Any], _seen: Optional[set] = None) -> List[str]:
    """A numeral set's members. A member that is itself a numeral set stands for its own members:
    nawa dewata holds panca dewata and four gods, and "Nawa dewata terdiri dari: panca dewata, dewa
    maheswara, dewa rudra, dewa sambu, dewa sangkara" named five things for nine (2026-10-15)."""
    content = get_content()
    seen = (_seen or set()) | {(e.get("name") or "").lower()}
    out: List[str] = []
    for r in e.get("relationships") or []:
        rel, outgoing = r.get("relation"), bool(r.get("outgoing"))
        if (rel in ("TERMASUK_JENIS", "BAGIAN_DARI") and not outgoing) or \
                (rel in ("TERDIRI_DARI", "BERUPA", "BERUNSUR") and outgoing):
            name = r.get("target")
            mid = content.id_by_name.get((name or "").lower())
            inner = []
            if mid and _NUMERAL_SET_RE.match(name) and name.lower() not in seen:
                # its members from the KB files: the edges, and its kinds (the broader spine)
                inner = _set_members({"name": name, "relationships": _kb_relationships(mid)}, seen)
                inner += [content.entity_name[k] for k in content.kinds_of(mid)
                          if content.entity_name[k] not in inner]
            for x in (inner if len(inner) >= 2 else [name]):
                if x and x not in out:
                    out.append(x)
    return out


def _complete_sarana_lists(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A "sarana" answer must name the items of each group (the term itself, each stage).
    Once the stages' tetandingan banten were in the KB (2026-09-30), "apa saja sarana upacara
    yang digunakan untuk ngaben" came back with only the stage NAMES under "sarana yang
    digunakan pada beberapa tahap". Every group whose items the answer mostly left out is
    added as its fact sentence. Not for a why-question (see the call): "mengapa uang kepeng
    digunakan dalam sarana upacara ngaben" got all of ngaben's groups appended (2026-10-08
    batch)."""
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


# what a what-is question may say besides its term
_WHAT_IS_FILLER = frozenset({"dong", "deh", "sih", "nih", "tuh", "kak", "min", "info", "informasi", "tentang", "soal",
                             "mengenai", "tolong", "coba", "kasih", "tahu", "tau", "jelasin", "jelaskan", "apaan"})


def _asks_what_it_is(user_msg: Text) -> bool:
    """A question asking what its term is: "apa itu X", "X itu apa(an)", "jelaskan X", "arti X", or the term with
    nothing else ("kajang dong"). Not a question asking anything else that names no aspect: "yang mandiin jenazah itu
    namanya apa?" got jenazah's definition in front of the name, "anak kecil yg meninggal diaben juga gk?" "Ngaben adalah
    ..." in front of its verdict (human test 2026-11-03)."""
    if _whether_question(user_msg) or re.search(r"\b(?:nama(?:nya)?|disebut|dinamakan|sebutannya|istilahnya)\b",
                                                user_msg, re.I):
        return False
    if (_OVERVIEW_Q_RE.search(user_msg) or _WHAT_IS_RE.search(user_msg)
            or re.search(r"\barti(?:nya)?\b|\bmaksud(?:nya)?\b", user_msg, re.I)
            or re.search(r"\bapa(?:an)?\s*(?:sih|ya|kah|tuh|dong)?\s*[?.!]*\s*$", user_msg, re.I)):
        return True
    return all(w in _WHAT_IS_FILLER for w in _mentioned_terms(user_msg, get_resolver())[1])


_KNOWN_WORDS: Optional[frozenset] = None
_MULTIWORD_SURFACES: Optional[List[str]] = None
_AFFIX_PREFIXES = frozenset({"di", "ke", "se", "be", "me", "pe", "ber", "ter", "per", "mem", "men", "pem", "pen"})
_AFFIX_SUFFIXES = frozenset({"nya", "kan", "an", "i", "lah", "kah", "pun", "ku", "mu"})


_KB_ONLY_WORDS: Optional[frozenset] = None


def _known_words() -> frozenset:
    """Every word written as some source writes it: the whole everyday list, every word of the KB's names, aliases and
    cards, and every word of the source corpus. Spellings Qwen takes from these ("Wisnu", "sthana", "pamuput",
    "ketiadaan") are no misspellings, though the context may lack them."""
    global _KNOWN_WORDS, _KB_ONLY_WORDS
    if _KNOWN_WORDS is None:
        from kb_resolver import _COMMON_WORDS_FILE, _load_common_words
        content, resolver = get_content(), get_resolver()
        everyday = set(_load_common_words(min_count=1))
        kb = set()
        for text in list(content.entity_def.values()) + list(resolver.surface):
            kb |= set(re.findall(r"[a-z][a-z-]*", (text or "").lower()))
        corpus = _COMMON_WORDS_FILE.parent / "ngaben-merge-cleaned.txt"
        words = everyday | kb
        if corpus.exists():
            words |= set(re.findall(r"[a-z][a-z-]*", corpus.read_text(encoding="utf-8").lower()))
        _KNOWN_WORDS = frozenset(words)
        # the KB's own words that are no everyday ones (galih, sesenden, gegaleng): what a misspelling is corrected to
        _KB_ONLY_WORDS = frozenset(w for w in kb if w not in everyday and not _is_everyday_word(w, resolver))
    return _KNOWN_WORDS


def _affix_variant(a: str, b: str) -> bool:
    """One word is the other with an affix ("penyucian" / "penyuciannya", "bakar" / "dibakar"): no misspelling."""
    # (and the adjective in -is: "kosmologis" / "kosmologi")
    return any(x.startswith(y) and x[len(y):] in _AFFIX_SUFFIXES or x.endswith(y) and x[:-len(y)] in _AFFIX_PREFIXES
               or x == y + "s" and y.endswith("i") for x, y in ((a, b), (b, a)))


def _fix_misspellings(answer: Text, context_text: Text) -> Text:
    """A KB word the model misspelled gets the context's spelling. "Nuduk Gali: ... pengumpulan sisa-sis tulang (galili)
    ... ditumbuk (diuyeg) di atas sescenden" (the context: Nuduk Galih, sisa-sisa, galih, sesenden; human test
    2026-11-03). Only a word no source writes (_known_words) becomes a word of the context that is the KB's own (no
    everyday word): one letter off, or two with the first three letters the same. A KB name whose last word lost its
    last letter after a word of its own ("Nuduk Gali") gets it back; a doubled word cut short ("sisa-sis") is doubled.
    Tried more loosely on every recorded Qwen reply, it turned Wisnu into Wishnu, ketiadaan into keadaan, sthana into
    sarana and "anugerah raja bagi" into "raja bali"."""
    global _MULTIWORD_SURFACES
    from rapidfuzz.distance import Levenshtein
    ctx = context_text.lower()
    ctx_words = set(re.findall(r"[a-z][a-z-]*", ctx))
    known = _known_words()
    targets = ctx_words & _KB_ONLY_WORDS

    def respell(word: str, target: str) -> str:
        return target[:1].upper() + target[1:] if word[:1].isupper() else target

    def fix_word(m: "re.Match") -> str:
        w = m.group(0)
        lw = w.lower()
        if len(lw) < 5 or lw in known or lw in ctx_words:
            return w
        halves = lw.split("-")
        if len(halves) == 2 and halves[1] and halves[0] != halves[1] and halves[0].startswith(halves[1]):
            return respell(w, f"{halves[0]}-{halves[0]}")
        near = sorted((Levenshtein.distance(lw, c), c) for c in targets
                      if c[:1] == lw[:1] and len(c) >= 4 and not _affix_variant(lw, c))
        near = [(d, c) for d, c in near if d == 1 or d == 2 and len(lw) >= 6 and c[:3] == lw[:3]]
        if near and (len(near) == 1 or near[0][0] < near[1][0]):
            return respell(w, near[0][1])
        return w
    answer = re.sub(r"(?<![\w-])[A-Za-z][A-Za-z-]*[A-Za-z](?![\w-])", fix_word, answer)
    if _MULTIWORD_SURFACES is None:
        resolver = get_resolver()
        _MULTIWORD_SURFACES = [s for s in resolver.surface if len(s.split()) >= 2 and re.fullmatch(r"[a-z ]+", s)
                               and any(not _is_everyday_word(w, resolver) for w in s.split()[:-1])]
    for s in _MULTIWORD_SURFACES:
        if s not in ctx:
            continue
        head, last = s.rsplit(" ", 1)

        def fix_name(m: "re.Match") -> str:
            got = m.group(2).lower()
            if got != last and len(last) >= 5 and last[:-1] == got:
                return f"{m.group(1)} {respell(m.group(2), last)}"
            return m.group(0)
        head_rx = r"\s+".join(re.escape(w) for w in head.split())
        answer = re.sub(rf"(?<![\w-])({head_rx})\s+([A-Za-z]+)(?![\w-])", fix_name, answer, flags=re.I)
    return answer


def _ensure_definition_lead(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A plain "apa itu X" answer that leaves out most of X's first definition sentence gets that
    sentence in front. "apa itu pitra yadnya" opened with the definition's third sentence ("adalah
    upacara keagamaan ...") on three fresh Ollama loads, dropping the general meaning the user wants
    first ("pengorbanan ... kepada leluhur", conersation.md 2026-10-02; Tier B 2026-10-05)."""
    if not enriched:
        return answer
    # with its subject: a gloss alone ("Para pendahulu, seperti orang tua ...") opened "apa itu pitra dan
    # pramakusa" naming neither (#1776, LLM comparison 2026-10-20)
    lead = _first_sentence(_deterministic_answer([dict(enriched[0], aspect_facts=[])]) or enriched[0].get("definition"),
                           limit=500)
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
    resolver = get_resolver()
    for e in enriched:
        names = [e["name"]] + list(e.get("aliases") or [])
        if not any(len(n) >= 4 and _ortho_key(n) in asked for n in names):
            continue
        sentences = _sentences(e.get("definition"))
        judging = next((s for s in sentences if _JUDGEMENT_RE.search(s)), None)
        # the opening sentence too, when it says what makes the term so: paruwak tahuk's "yaitu
        # sasih yang di dalamnya tidak jatuh hari Tumpek" is the reason, but has no judging word, and
        # on one load in four the answer gave "berbadankan kosong" and the lontar without it (Tier B
        # 2026-10-05/08) -- added when a rare word of it is missing
        lead = sentences[0] if sentences and sentences[0] is not judging else None
        clause = re.search(r"\b(?:yaitu|berarti|artinya)\b([^;.]*)", lead or "")
        for s in (lead if clause else None, judging):
            if not s:
                continue
            words = _content_words(s) - question_words - _content_words(" ".join(names))
            rare = {w for w in _content_words(clause.group(1)) if not _is_everyday_word(w, resolver)} if clause else set()
            missing_rare = s is lead and any(not _grounded(w, said) for w in rare)
            if words and (s is judging and sum(_grounded(w, said) for w in words) < 0.6 * len(words)
                          or missing_rare):
                answer = answer.rstrip() + "\n\n" + s
                said |= words
            elif s is judging:
                # covered as a whole -- "dianggap tidak baik", and "dewasa" from the lontar's
                # "alaning dewasa" -- while the clauses that give the reason were left out: malamasa's
                # "Kata mala berarti 'tidak baik'" and "sasih kotor" (Tier B 2026-10-05, 2026-10-09).
                # Only those clauses, so the covered part is not said twice.
                extra = [c for c in re.split(r"\s*[;:]\s*", s.strip().rstrip("."))
                         if c and _clause_left_out(c, answer, user_msg, names)]
                if extra:
                    text = "; ".join(extra)
                    answer = answer.rstrip() + "\n\n" + text[:1].upper() + text[1:] + "."
                    said |= _content_words(text)
    return answer


# judgements said in other words: "dianggap ... tidak disarankan untuk pelaksanaan upacara Panca Yadnya" got
# malamasa's "sasih mala dinilai tidak baik, sehingga upacara Panca Yadnya tidak dianjurkan ..." appended as
# its own paragraph (Tier B 2026-10-14 and 2026-10-27)
_JUDGEMENT_SAME = (("tidak dianjurkan", "tidak disarankan"),
                   ("dilarang", "tidak boleh", "tidak diperkenankan", "tidak diizinkan"))


def _clause_left_out(clause: Text, answer: Text, user_msg: Text, names: List[str]) -> bool:
    """A clause of a judging sentence whose own judgement the answer never uses ("kotor"), nor in
    other words (`_JUDGEMENT_SAME`), or a word-meaning clause ("Kata mala berarti ...") under half of
    whose words the answer has."""
    low = answer.lower()
    for m in _JUDGEMENT_RE.finditer(clause):
        word = m.group(0).lower()
        if not any(v in low for v in next((g for g in _JUDGEMENT_SAME if word in g), (word,))):
            return True
    if not re.search(r"\b(?:berarti|yaitu|artinya)\b", clause, re.I):
        return False
    roots = _sentence_roots(clause) - _sentence_roots(user_msg) - _sentence_roots(" ".join(names))
    return bool(roots) and len(roots & _sentence_roots(answer)) * 2 < len(roots)


_CHAIN_QUERY = """
MATCH (a:Node {id: $a}), (b:Node {id: $b})
OPTIONAL MATCH p = shortestPath((a)-[:BAGIAN_DARI|TERMASUK_JENIS*1..3]->(b))
WHERE all(x IN relationships(p) WHERE coalesce(x.confidence, '') <> 'LOW')
OPTIONAL MATCH q = shortestPath((b)-[:BAGIAN_DARI|TERMASUK_JENIS*1..3]->(a))
WHERE all(x IN relationships(q) WHERE coalesce(x.confidence, '') <> 'LOW')
OPTIONAL MATCH (a)-[r1:BAGIAN_DARI|TERMASUK_JENIS]->(m:Node)<-[r2:BAGIAN_DARI|TERMASUK_JENIS]-(b)
WHERE type(r1) = type(r2) AND coalesce(r1.confidence, '') <> 'LOW' AND coalesce(r2.confidence, '') <> 'LOW'
RETURN [n IN nodes(p) | n.id] AS p_ids, [r IN relationships(p) | type(r)] AS p_rels,
       [n IN nodes(q) | n.id] AS q_ids, [r IN relationships(q) | type(r)] AS q_rels,
       collect(DISTINCT [m.id, type(r1)])[0] AS shared
"""


_NO_LINK_RE = re.compile(r"\btidak\s+(?:ada|memiliki|mempunyai)\s+(?:\w+\s+)?(?:hubungan|kaitan|keterkaitan)\b"
                         r"|\b(?:hubungan|kaitan)\b[^.!?\n]{0,80}\b(?:belum|tidak)\s+tercatat\b", re.I)


def _say_no_link(answer: Text, a: Dict[str, Any], b: Dict[str, Any]) -> Text:
    """A relation question about two terms nothing joins -- no edge, no chain of kinds or parts, a definition naming
    neither -- says so first when the answer does not: "Pemangku berhubungan dengan ayaban sesayut bagaimana" got
    "Hubungan antara pemangku dan ayaban sesayut ... adalah bahwa pemangku tidak memberikan ayaban sesayut", a link
    read from sulinggih giving it (Tier B 2026-10-30; the run before had "Tidak ada hubungan langsung ..."). An
    opening "Hubungan (antara) ..." is then the indirect link, as in _complete_chain_link: not cut -- "Hubungan antara
    yadnya dan kayu cendana terletak pada peran kayu cendana sebagai ... sarana ... dalam upacara Ngaben" is true."""
    if _NO_LINK_RE.search(answer):
        return answer
    if (b["name"].lower() in _named_in(a.get("definition") or "")
            or a["name"].lower() in _named_in(b.get("definition") or "")):
        return answer
    answer = re.sub(r"^\s*Hubungan\b", "Secara tidak langsung, hubungan", answer, count=1)
    return f"Tidak ada hubungan langsung antara {a['name']} dan {b['name']} yang tercatat. {answer.lstrip()}".strip()


def _complete_chain_link(answer: Text, enriched: List[Dict[str, Any]], relation: bool = False) -> Text:
    """A comparison or relation question about two terms no edge joins gets the chain of kinds and parts between
    them, when the answer does not say it: "apa perbedaan pangringkes dan pitra yadnya" got two long descriptions
    and never "pangringkes is a stage of ngaben, a kind of pitra yadnya" (Tier B 2026-10-26). Else a parent both
    share ("sama-sama tahapan ngaben"). Up front; after an opening "tidak ada hubungan (langsung)" as its indirect
    link. `relation` (a relation question, not a comparison): with no chain either, `_say_no_link`."""
    if len(enriched) != 2:
        return answer
    a, b = enriched
    if any(r.get("target_id") == b["id"] for r in a.get("relationships") or []) or \
            any(r.get("target_id") == a["id"] for r in b.get("relationships") or []):
        return answer
    rows = neo4j_conn.query(_CHAIN_QUERY, {"a": a["id"], "b": b["id"]})
    if not rows:
        return answer
    row, content, resolver = rows[0], get_content(), get_resolver()

    def name(i: str) -> str:
        return content.entity_name.get(i, i)

    def hop(x: str, rel: str, y: str) -> str:
        if rel == "TERMASUK_JENIS":
            return f"{name(x)} termasuk jenis {name(y)}"
        if content.entity_type.get(x) in _STAGE_TYPES:
            return f"{name(x)} merupakan salah satu tahapan {name(y)}"
        return f"{name(x)} merupakan bagian dari {name(y)}"
    ids, rels = (row["p_ids"], row["p_rels"]) if row.get("p_ids") else (row.get("q_ids"), row.get("q_rels"))
    if ids:
        hops = [(ids[k], rels[k], ids[k + 1]) for k in range(len(rels))]
        clauses = [hop(*h) for h in hops]
        text = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + ", dan " + clauses[-1]
    elif row.get("shared") and row["shared"][0]:
        mid, rel = row["shared"]
        hops = [(a["id"], rel, mid), (b["id"], rel, mid)]
        both = f"{name(a['id'])} dan {name(b['id'])} sama-sama"
        text = (f"{both} jenis {name(mid)}" if rel == "TERMASUK_JENIS"
                else f"{both} tahapan {name(mid)}" if content.entity_type.get(a["id"]) in _STAGE_TYPES
                else f"{both} bagian dari {name(mid)}")
    else:
        return _say_no_link(answer, a, b) if relation else answer

    def surfaces(i: str) -> List[str]:
        return [name(i)] + list((resolver.by_id.get(i) or {}).get("aliases") or [])
    sentences = re.findall(r"[^.!?\n]+[.!?]*", answer)

    def stated(x: str, y: str) -> bool:
        # both ends in one sentence of the opening with a kind / part word ("Ngaben merupakan salah satu jenis Pitra
        # Yadnya", "... merupakan dua dari tiga lapis alam dalam kosmologi Tri Loka"): the pangringkes answer had both
        # facts, each deep inside a paragraph about one term
        return any(any(re.search(rf"\b{re.escape(n)}\b", s, re.I) for n in surfaces(x))
                   and any(re.search(rf"\b{re.escape(n)}\b", s, re.I) for n in surfaces(y))
                   and re.search(r"\b(?:jenis|bagian|tahap\w*|termasuk|rangkaian|salah satu|(?:dua|tiga|empat|lima) "
                                 r"dari|anggota)\b", s, re.I)
                   for s in [x for x in sentences if x.strip()][:2])
    if all(stated(x, y) for x, _, y in hops):
        return answer
    text = text[:1].upper() + text[1:] + "."
    first = next((s for s in sentences if s.strip()), "")
    if re.search(r"\btidak ada (?:hubungan|kaitan|perbedaan)\b", first, re.I):
        cut = answer.index(first) + len(first)
        return f"{answer[:cut].rstrip()} Secara tidak langsung, {text[:1].lower()}{text[1:]}{answer[cut:]}"
    return f"{text} {answer.lstrip()}"


def _complete_stated_link(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A comparison or relation question about two terms gets each definition sentence that
    names the other term with a reason or order ("Ngaben memisahkan jiwa ... tetapi jiwanya masih
    berbadan halus ...; karena itulah Atma Wedana diselenggarakan setelah Ngaben") when the answer
    left most of it out. Rule 17 asks for that dependency, yet "apa perbedaan ngaben dan atma
    wedana" gave two separate definitions on most loads (Tier B 2026-10-02/05).
    A later answer sentence the appended one holds whole goes ("Sementara itu, sulinggih adalah
    pendeta atau tokoh suci yang telah disucikan melalui upacara madiksa." above sulinggih's own
    sentence, Tier B 2026-10-09); never the first."""
    said = _content_words(answer)
    for e in enriched:
        others = [o for o in enriched if o is not e]
        names = [n for o in others for n in [o["name"]] + list(o.get("aliases") or []) if len(n) >= 4]
        if not names:
            continue
        named = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b", re.I)
        for s in _sentences(e.get("definition")):
            words = _content_words(s)
            # per ;-clause too: "karena itulah Atma Wedana diselenggarakan setelah Ngaben" said made
            # atma wedana's sentence look covered without its reason, "jiwanya masih berbadan halus ...
            # dan masih berkedudukan sebagai pitra" (Tier B 2026-10-09)
            clauses = [_content_words(c) for c in re.split(r"\s*;\s*", s)]
            if (named.search(s) and _DEPENDENCY_RE.search(s) and words
                    and any(c and sum(_grounded(w, said) for w in c) < 0.6 * len(c) for c in clauses)):
                roots = _sentence_roots(s)
                for t in _sentences(answer)[1:]:
                    t_roots = _sentence_roots(t)
                    if t_roots and len(t_roots & roots) >= 0.8 * len(t_roots) and not re.search(r"(?m)^\s*\d+\.", t):
                        answer = answer.replace(t, "", 1)
                answer = re.sub(r"[ \t]{2,}", " ", answer).rstrip() + "\n\n" + s
                said |= words
    return answer


# How each composition predicate reads in the breakdown, whole first ("bade terbuat dari
# kayu, bambu"). PART_IS_SUBJECT predicates are read from the whole's side too.
_COMPOSITION_PHRASE = {
    "TERBUAT_DARI": "terbuat dari", "TERDIRI_DARI": "terdiri dari", "BERISI": "berisi",
    "DIISI": "diisi", "DIISI_DENGAN": "diisi", "DIMASUKKAN_KE_DALAM": "diisi",
    "DILENGKAPI": "dilengkapi", "DILENGKAPKAN_PADA": "dilengkapi", "BERUPA": "berupa",
    "MELIPUTI": "meliputi", "BERUNSUR": "berunsur", "MENGANDUNG": "mengandung",
    "DIBUNGKUS_DENGAN": "dibungkus", "DIALASI_DENGAN": "dialasi", "DIIKAT_DENGAN": "diikat dengan",
    "DISISIPI": "disisipi", "DIPASANG": "dipasangi", "DISAMBUNG_DENGAN": "disambung dengan",
    "DIHIAS_DENGAN": "dihias dengan", "BERKERANGKA": "berkerangka",
    "BAGIAN_DARI": "memiliki bagian berupa", "DIPERLUKAN_UNTUK_MEMBUAT": "pembuatannya memerlukan",
}
_COMPOSITION_MAX_LINES = 12


def _composition_q(user_msg: Text) -> bool:
    return bool(_COMPOSITION_Q_RE.search(user_msg) and not _KINDS_Q_RE.search(user_msg))


def _short_source(source: Optional[Text]) -> Text:
    """"https://www.detik.com/bali/..." -> "detik.com"; a corpus citation stays as written."""
    m = re.match(r"https?://(?:www\.)?([^/]+)", source or "")
    return m.group(1) if m else (source or "").strip()


def _composition_rows(entity_id: Text) -> Dict[str, Any]:
    """The KB's composition tree of a sarana / tirtha / building, breadth-first (main version):
    {"rows": [(item name, kind parent it inherits its parts from or None, [(phrase, [part
    names])])], "leaves": the raw materials met, "variants": [(region, sentence, source)],
    "cut": bool}. No rows when the item has no recorded parts."""
    content = get_content()
    out: Dict[str, Any] = {"rows": [], "leaves": [], "variants": [], "cut": False}
    queue = [content.composition_tree(entity_id)]
    while queue:
        node = queue.pop(0)
        groups: Dict[str, List[str]] = {}
        for p in node["parts"]:
            child = p["node"]
            v = p.get("variant")
            if v:
                # "variasi (di X): <sentence>" -> ("di X", "<sentence>")
                line = content.render_variant(p["predicate"], node["name"], child["name"], v)
                m = re.match(r"variasi \((.*?)\):\s*(.*)", line, re.S)
                region, sentence = (m.group(1), m.group(2)) if m else ("", line)
                out["variants"].append((region, sentence, _short_source(v.get("source")) if v.get("source") else ""))
                continue
            phrase = _COMPOSITION_PHRASE.get(p["predicate"], p["predicate"].lower().replace("_", " "))
            groups.setdefault(phrase, []).append(child["name"])
            if child["parts"]:
                queue.append(child)
            elif child["raw"] and child["name"] not in out["leaves"]:
                out["leaves"].append(child["name"])
            out["cut"] = out["cut"] or child["cut"]
        if not groups:
            continue
        if len(out["rows"]) == _COMPOSITION_MAX_LINES:
            out["cut"] = True
            break
        out["rows"].append((node["name"], node.get("inherited_from"), list(groups.items())))
    return out


def _join_clauses(clauses: List[str]) -> str:
    """Predicates of one subject in one sentence: "a dan b", "a, serta b" (when one already holds
    a "dan" or a list), "a, b, serta c" -- with semicolons from three when a clause holds its own
    comma list ("dialasi ceper; berisi beras, benang, dan pisang; serta dilengkapi sampian").
    What follows in time comes with "lalu" ("..., lalu diikuti oleh pangringkes")."""
    if len(clauses) <= 1:
        return "".join(clauses)
    # what follows in time is said last: not "diikuti oleh pangringkes, serta dilakukan setelah ngulapin"
    clauses = sorted(clauses, key=lambda c: c.lower().startswith("diikuti"))
    last = ("lalu " if clauses[-1].lower().startswith("diikuti") else "serta ") + clauses[-1]
    if len(clauses) == 2:
        plain = not any("," in c or re.search(r"\s(?:dan|serta)\s", c) for c in clauses)
        return f"{clauses[0]} dan {clauses[1]}" if plain and last.startswith("serta") else f"{clauses[0]}, {last}"
    if any("," in c for c in clauses):
        return "; ".join(clauses[:-1]) + "; " + last
    return ", ".join(clauses[:-1]) + ", " + last


# the order a breakdown sentence says its predicates in: what it is made of, then what it holds, how
# it is wrapped or set, what decorates and completes it ("Daksina terbuat dari daun kelapa; berisi
# beras, ...; serta dilengkapi uang kepeng", not "dilengkapi ...; terbuat dari ...; berisi ...")
_COMPOSITION_ORDER = ["terbuat dari", "berkerangka", "terdiri dari", "berupa", "meliputi", "berunsur",
                      "mengandung", "berisi", "diisi", "disisipi", "dialasi", "dibungkus", "diikat dengan",
                      "disambung dengan", "dipasangi", "dihias dengan", "dilengkapi", "memiliki bagian berupa",
                      "pembuatannya memerlukan"]


def _composition_sentence(name: Text, kind_of: Optional[Text], groups: List[tuple]) -> str:
    """One breakdown row as a sentence: "Pripih cendana, sebagai salah satu jenis pripih,
    dibungkus daun dapdap." """
    subject = f"{name[:1].upper()}{name[1:]}" + (f", sebagai salah satu jenis {kind_of}," if kind_of else "")
    groups = sorted(groups, key=lambda g: _COMPOSITION_ORDER.index(g[0]) if g[0] in _COMPOSITION_ORDER
                    else len(_COMPOSITION_ORDER))
    return f"{subject} {_join_clauses([f'{ph} {_join_names(items)}' for ph, items in groups])}."


def _composition_breakdown(entity_id: Text) -> Text:
    """The layered "made of" breakdown, built from the KB in code and written as sentences (user
    2026-10-15: templates must read like natural language, not "Rincian bahan menurut basis data:
    - X: terbuat dari a, b"): the item itself, its composite parts ("Rinciannya:"), the raw
    materials it comes down to (only when there are deeper levels -- with one level they are the
    sentence's own list), then the variants with their source. Empty when no parts are recorded."""
    data = _composition_rows(entity_id)
    rows, variants = data["rows"], data["variants"]
    if not rows and not variants:
        return ""
    blocks = []
    sentences = [_composition_sentence(*r) for r in rows]
    if len(sentences) <= 2:
        # one part explained: "Kojong terbuat dari daun pisang." reads on in the same paragraph
        blocks.append(" ".join(sentences))
    else:
        blocks += [sentences[0], "Rinciannya:\n" + "\n".join(f"- {s}" for s in sentences[1:])]
    if len(rows) > 1 and data["leaves"]:
        blocks.append(f"Jadi, bahan dasarnya antara lain {_join_names(data['leaves'])}.")
    if variants:
        blocks.append("Ada pula variasinya menurut daerah atau sumber lain:\n" + "\n".join(
            f"- {region[:1].upper()}{region[1:]}: {sentence}" + (f" (sumber: {source})" if source else "") + "."
            if region else f"- {sentence[:1].upper()}{sentence[1:]}."
            for region, sentence, source in variants))
    if data["cut"]:
        blocks.append("Rinciannya masih berlanjut; tanyakan bagian tertentu untuk detailnya.")
    return "\n".join(b for b in blocks if b)


def _complete_composition(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """"X terbuat dari apa": the 7B model drops or mixes up levels of a deep breakdown
    (tirta pangentas -> pripih emas -> daun dapdap), so the breakdown is appended from the KB
    unless the answer already names every item in it."""
    if not enriched:
        return answer
    data = _composition_rows(enriched[0]["id"])
    if not data["rows"] and not data["variants"]:
        return answer
    said = _ortho_key(answer)
    items = [x for _, _, groups in data["rows"] for _, names in groups for x in names]
    if items and all(_ortho_key(x) in said for x in items) and not data["variants"]:
        return answer
    return answer.rstrip() + "\n\nRincian lengkapnya menurut basis data:\n" + _composition_breakdown(enriched[0]["id"])


def _raw_material_answer(enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A raw material ("beras terbuat dari apa") is a leaf: it is not made of other sarana."""
    if not enriched or not get_content().is_raw(enriched[0]["id"]):
        return None
    e = enriched[0]
    name = f"{e['name'][:1].upper()}{e['name'][1:]}"
    known = _first_sentence(e.get("definition"))
    return f"{name} adalah bahan dasar yang tidak tersusun dari sarana lain." + (f" {known}" if known else "")


def _add_literal_meaning(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text = "") -> Text:
    """A word-meaning question must give the literal meaning when the KB records one
    (BERARTI_HARFIAH). With it in context, the model still left it out on some runs of the
    same prompt -- "apa arti kata ngulapin" passed once and failed once without
    "melambaikan tangan" (Ollama is not fully deterministic at temperature 0, 2026-09-30).
    Only the quoted phrase is compared and added. So is the word's origin (BERASAL_DARI_KATA) when
    the question asks "asal": "apa arti kata ngaben dan dari mana asal katanya" lost "beya, yang
    berarti bekal" on a fresh load (Tier B 2026-10-09)."""
    content = get_content()
    attrs = content.attributes
    for e in enriched[:1]:
        for value in attrs.get(e["id"], {}).get("BERARTI_HARFIAH", []):
            m = re.match(r'\s*"([^"]+)"', value)
            literal = m.group(1) if m else None
            if literal and literal.lower() not in answer.lower():
                answer = (answer.rstrip() + f' Secara harfiah, {e["name"]} berarti "{literal}".').strip()
        if re.search(r"\basal\b", user_msg, re.I):
            for value in attrs.get(e["id"], {}).get("BERASAL_DARI_KATA", []):
                word = re.split(r"[,:(]", value, maxsplit=1)[0].strip().strip('"')
                if word and not re.search(rf"\b{re.escape(word)}\b", answer, re.I):
                    sentence = content.render("BERASAL_DARI_KATA", e["name"], value).rstrip(".")
                    answer = f"{answer.rstrip()} {sentence[:1].upper()}{sentence[1:]}."
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
    # any name the KB knows counts: "Dewa Wisnu" is dewa wishnu, "Siwa" shiwa
    named = {get_content().entity_name.get(i, "").lower() for i in _named_terms(answer, everyday=True)}
    # more members than the numeral: the corpus gives two versions of the set (panca datu's
    # fifth metal is mirah or logam campuran) and the definition explains which -- a flat
    # "terdiri dari" list of six for "panca" would contradict it (lint waiver panca_datu>5)
    if len(members) > _NUMERAL_VALUE[m.group(1).lower()]:
        return answer
    if len(members) >= 2 and any(_ortho_key(x) not in said and x.lower() not in named for x in members):
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
# Never right after "tidak"/"belum": there the verb is the sentence's predicate, and cutting
# "disebutkan dalam konteks" out of "Namun, tidak disebutkan dalam konteks apa saja yang
# dimasukkan ..." left "Namun, tidak apa saja yang dimasukkan ..." (2026-10-07 batch, also
# "tidak siapa yang bertanggung jawab", "tidak secara spesifik"). _PROMPT_REF_RE drops that
# whole sentence instead.
_NOT_NEGATED = r"(?<!\btidak)(?<!\btidak\s)(?<!\bbelum)(?<!\bbelum\s)"
_META_PHRASE_RE = re.compile(
    r",?\s*(?:seperti|sebagaimana)\s+(?:yang\s+)?(?:tercantum|disebutkan|dijelaskan|tertulis|terdapat)\s+"
    + _CONTEXT_WORD +
    # ", seperti yang disebutkan dalam definisi malamasa." (Tier B 2026-10-01)
    r"|,?\s*(?:seperti|sebagaimana)\s+(?:yang\s+)?(?:tercantum|disebutkan|dijelaskan|tertulis|terdapat)\s+"
    r"(?:dalam|di)\s+(?:definisi|informasi|data|fakta)(?:\s+[\w-]+){0,3}?(?=\s*[.,!?]|\s*$)"
    r"|" + _NOT_NEGATED + r"\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)\s+" + _CONTEXT_WORD +
    # "... yang disebutkan dalam definisi dan hubungan yang diberikan"
    r"|" + _NOT_NEGATED + r"\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)\s+(?:dalam|di)\s+"
    r"(?:definisi|informasi|data|fakta)(?:\s+dan\s+(?:hubungan|fakta|definisi))?\s+yang\s+(?:diberikan|tersedia)" +
    # "Kelima dewa yang disebutkan secara spesifik dalam informasi ini adalah ..." (live 2026-10-15)
    r"|" + _NOT_NEGATED + r"\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)(?:\s+secara\s+\w+)?\s+"
    r"(?:dalam|di)\s+(?:definisi|informasi|data|fakta)\s+(?:ini|tersebut|di atas)\b" +
    # "..., karena berdasarkan definisi dewasa ngaben, keduanya ..." (Tier B 2026-10-01)
    r"|\b(?:berdasarkan|menurut)\s+definisi(?:\s+[\w-]+){0,3}?\s*,\s*"
    # "Menurut definisi dan hubungan yang diberikan, ..." (Tier B 2026-10-01); "Namun, dari definisi dan hubungan
    # yang tersedia, diketahui bahwa kajang ..." (Tier B 2026-10-26/27)
    r"|\b(?:berdasarkan|menurut|dari)\s+(?:informasi|konteks|data|fakta|definisi)"
    r"(?:\s+dan\s+(?:hubungan|fakta|definisi|informasi))?(?:\s+yang\s+(?:diberikan|tersedia|ada|tercatat))?"
    r"(?:\s+(?:tersebut|ini|di atas))?\s*,\s*"
    # "..., berdasarkan informasi yang tercatat dalam konteks tersebut." (2026-09-29);
    # "..., sesuai dengan informasi yang tercatat dalam konteks tersebut." (2026-10-01)
    r"|,?\s*(?:berdasarkan|menurut|sesuai dengan)\s+(?:informasi|konteks|data|fakta)"
    r"(?:\s+yang\s+(?:diberikan|tersedia|ada|tercatat))?"
    r"(?:\s+(?:dalam|di)\s+konteks)?(?:\s+(?:tersebut|ini|di atas))?(?=\s*[.!?]|\s*$)"
    r"|\bdalam\s+konteks\s+(?:tersebut|ini|di atas|yang diberikan|yang tersedia)\s*,\s*"
    # "tidak ada aturan dalam konteks yang menyatakan bahwa setra dilarang ..." (NLU sweep 2026-10-19); KB
    # text says "dalam konteks Ngaben / kalender Bali", never "dalam konteks yang ..."
    r"|\s+(?:dalam|di)\s+konteks(?=\s+yang\s+(?:menyatakan|menyebutkan|mengatakan|menunjukkan|menjelaskan)\b)"
    # "Konteks menyebutkan bahwa bale dalam upacara Ngaben ..." (2026-10-08 batch). Only before "bahwa"
    # and a clause that does not go on to say what the context lacks: cut from "Catatan: Konteks hanya
    # menyebutkan secara eksplisit nama lima dewa ...", it left "Catatan: secara eksplisit nama lima
    # dewa"; "Konteks juga menyatakan bahwa X ..., tetapi tidak memberikan nama spesifik ..." would
    # leave X "not giving names" (live 2026-10-15). Those sentences go whole (_PROMPT_REF_RE).
    # The same with "Informasi yang tersedia (mengenai X)" as the subject: "Informasi yang tersedia hanya
    # menyatakan bahwa wadah digunakan dalam ngaben, ..." went whole and left "Upacara ini bertujuan ..." with
    # no ceremony named (#1778, LLM comparison 2026-10-20)
    r"|\b(?:konteks|informasi\s+yang\s+(?:tersedia|diberikan)(?:\s+(?:mengenai|tentang)\s+[\w-]+(?:\s+[\w-]+){0,3}?)?)"
    r"\s+(?:(?:hanya|juga)\s+)?(?:menyebutkan|menjelaskan|mencatat|memuat|menyatakan)\s+bahwa\s+"
    r"(?![^.!?\n]*\b(?:tidak|belum)\s+(?:memberikan|menyebutkan|mencantumkan|menjelaskan|merinci|mencatat)\b)",
    re.I)
# A sentence still about the prompt after those cuts goes whole: "Perlu dicatat bahwa daftar
# lengkap bahan-bahan ... tidak disebutkan secara detail dalam konteks ini." above a complete
# breakdown, "... bahan-bahan lainnya yang disebutkan dalam fakta-fakta tersebut." (Tier B
# 2026-10-02). KB text says "dalam konteks Ngaben/upacara", never "konteks ini" or "fakta tersebut",
# and never "dalam definisi" / "dalam fakta": "... sudah disebutkan dalam definisi tirta pangentas.
# Namun, bahan-bahan lain yang disebutkan dalam fakta-fakta tidak disebutkan ..." (same day).
_PROMPT_REF_RE = re.compile(
    # "..., tetapi berdasarkan informasi yang diberikan:" before a list (Tier B 2026-10-02). Not
    # "basis data yang tersedia", the bot's own words: "Fungsi bale delod ... tidak tercatat dalam
    # basis data yang tersedia." went whole and left "Meskipun demikian, bale semanggen ..." (2026-10-09)
    r"\b(?:informasi|(?<!basis\s)data)\s+yang\s+(?:diberikan|tersedia)\b|"
    r"\bkonteks\s+(?:ini|tersebut|di atas|yang\s+(?:diberikan|tersedia))\b"
    r"|\bfakta(?:-fakta)?\s+(?:ini|tersebut|di atas|yang\s+(?:diberikan|tersedia))\b"
    r"|\b(?:dalam|di)\s+(?:definisi|fakta(?:-fakta)?)\b|\bdefinisi\s+(?:ini|tersebut)\b"
    # the context as a sentence's subject: "Konteks hanya menyebutkan ...", "Konteks juga menyatakan ...,
    # tetapi tidak memberikan ..." (live 2026-10-15); "dalam informasi ini"
    r"|\bkonteks\s+(?:(?:hanya|juga|tidak|secara\s+\w+)\s+)*(?:menyebutkan|menjelaskan|mencatat|memuat|menyatakan"
    r"|memberikan|mencantumkan|merinci)\b|\b(?:dalam|di)\s+informasi\s+(?:ini|tersebut|di atas)\b"
    # "Urutan ... tidak disebutkan secara spesifik dalam konteks." (see _NOT_NEGATED)
    r"|\b(?:tidak|belum)\s+(?:secara\s+\w+\s+)?(?:disebutkan|dijelaskan|tercantum|terdapat|dirinci|diuraikan)\b"
    r"(?:\s+[\w-]+){0,3}?\s+(?:dalam|di)\s+(?:konteks|informasi|data)\b", re.I)


# Inside a verdict sentence, where the prompt is named as the source: "... yang tercatat dalam informasi yang
# tersedia", "... tidak dapat ditentukan dari informasi yang tersedia". Not "dalam konteks Ngaben" (KB text).
_PROMPT_SOURCE_RE = re.compile(
    r"\s+(?:dalam|di|dari|berdasarkan|menurut)\s+(?:informasi|konteks|data|fakta)"
    r"(?:\s+yang\s+(?:tersedia|diberikan|ada)|\s+(?:ini|tersebut|di atas)|(?=\s*[.,!?;]))", re.I)
# The prompt as the subject of a miss: "konteks yang tersedia tidak merinci tahapan prosedural" says that the
# stages are not recorded
_CONTEXT_LACKS_RE = re.compile(
    r"\b(?:konteks|informasi|data)(?:\s+yang\s+(?:tersedia|diberikan))?\s+(?:juga\s+)?(?:tidak|belum)\s+"
    r"(?:secara\s+\w+\s+)?(?:merinci|menyebutkan|menjelaskan|mencatat|mencantumkan|memuat|menguraikan|memberikan)"
    r"\s+(?:(?:informasi|keterangan)\s+(?:mengenai|tentang)\s+)?([^.!?,;\n]+)", re.I)


def _rescue_verdict(sentence: Text) -> Optional[Text]:
    """A verdict sentence that names the prompt, said without it -- or None when it cannot be: "Tidak ada
    kaitan langsung antara krematorium dan upih yang tercatat dalam informasi yang tersedia." -> "... yang
    tercatat." (#1708, #1762, #1766 had lost their whole verdict and answered with two definitions)."""
    # "konteks tidak mencatat bahwa tepung ketan dipakai dalam apah" -> "tidak tercatat bahwa tepung ketan ..."
    out = _CONTEXT_LACKS_RE.sub(lambda m: (f"tidak tercatat {m.group(1).strip()}" if m.group(1).lower().startswith("bahwa ")
                                           else f"{m.group(1).strip()} belum tercatat di basis data"), sentence)
    out = re.sub(r"[ \t]{2,}", " ", _PROMPT_SOURCE_RE.sub("", out))
    return out if _VERDICT_RE.search(out) and not _PROMPT_REF_RE.search(out) else None


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
        # the answer's only verdict is said without the prompt rather than lost with it -- and so is an opening
        # verdict: "Tidak, konteks tidak mencatat bahwa rasa bersifat wajib." went, and "apakah rasa wajib" was
        # answered from its last sentence (plan #16, 2026-10-26)
        first = next((s for s in parts if s.strip()), None)
        others_judge = any(_VERDICT_RE.search(s) for s in parts if s not in about_prompt)
        rescued = next(((s, r) for s in about_prompt if (not others_judge or s == first)
                        and (_VERDICT_RE.search(s) or _CONTEXT_LACKS_RE.search(s)) and (r := _rescue_verdict(s))),
                       None)
        for s in about_prompt:
            if rescued and s == rescued[0]:
                lead = re.match(r"\s*", s).group(0)
                out = out.replace(s, lead + rescued[1].strip()[:1].upper() + rescued[1].strip()[1:]
                                  + (" " if s.endswith(" ") else ""), 1)
                continue
            out = out.replace(s, "", 1)
        out = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", out).strip()
    if out == answer:
        return answer
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"[ \t]+([.,:;])", r"\1", out)
    # a sentence that began with the cut phrase starts with a capital again
    return re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)


# A child that only says who uses it ("Gajah mina: ... umumnya digunakan oleh golongan Wesia",
# "Macan: ... diperuntukkan bagi warga keturunan wangsa Pande") says nothing about what the class
# is for: kept for "apa guna patulangan", all six forms came back as the answer, under the one
# sentence that said its use (conersation.md 2026-10-07). A stated purpose keeps it.
_USERS_ONLY_RE = re.compile(r"\b(?:digunakan|dipakai|dipergunakan|diperuntukkan)\s+(?:oleh|bagi)\b"
                            r"|\b(?:yang|keluarga yang)\s+memakai\b|\bdipakai\s+(?:kalangan|golongan)\b", re.I)
_PURPOSE_IN_DEF_RE = re.compile(r"\b(?:berfungsi|fungsinya|bertujuan|tujuannya|agar)\b"
                                r"|\b(?:digunakan|dipakai|dimohon)\s+untuk\b|\buntuk\s+(?:me|di|ber)\w{3,}"
                                r"|\bsebagai\s+(?:sarana|alat|tempat|wadah|lambang)\b", re.I)


def _says_what_for(definition: Text) -> bool:
    return not _USERS_ONLY_RE.search(definition) or bool(_PURPOSE_IN_DEF_RE.search(definition))


def _llm_context(enriched: List[Dict[str, Any]], with_relationships: bool = True,
                 only_predicates: Optional[set] = None,
                 keep_to: Optional[set] = None,
                 contents_only: bool = False,
                 part_definitions: bool = True,
                 keep_children: Optional[set] = None,
                 meaning_words: Optional[set] = None,
                 overview: bool = False) -> List[Dict[str, Any]]:
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
    own words) keeps a child whose definition states a meaning and shares one of them.
    `overview` (a plain "apa itu X" about one term) leaves out the things used IN X: "bisa
    jelaskan apa itu ngaben?" listed "bade, banten byakawonan, banten pejati, ... wadah" between
    its stages and kinds (2026-10-08 batch; "the bot just shit out as much facts as possible",
    conersation.md 2026-10-07). "apa saja sarana X" asks for them."""
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
                  or (keep_children and e["id"] in keep_children and r.get("target_definition")
                      and _says_what_for(r["target_definition"]))
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
        if overview:
            rs = [r for r in rs if not (r.get("relation") in _SARANA_USE_IN and not r.get("outgoing")
                                        or r.get("relation") in _SARANA_USE_OUT and r.get("outgoing"))]
        n_child_defs = 0
        for r in rs:
            item = {"fact": r.get("statement") or f"{e['name']} -- {r.get('target')}"}
            # capped so a hub's prompt stays short (it was CPU-bound Ollama; now tokens are billed)
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
        # and the terms its aspect facts name: "pradaksina melambangkan turunnya purusa meresapi
        # pradana" is explained by purusa-pradana's entry (an elaborate answer, 2026-10-08)
        for fact in item.get("facts") or []:
            named += _named_terms(fact)
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
    relationships. See LLM_MAX_PROMPT_TOKENS for why the prompt is capped."""
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


def _collapse_name_words(synth_q: Text, enriched: List[Dict[str, Any]]) -> str:
    """"apa itu purusa dan pradana" -> "purusa-pradana dan pradana", which came back as "Purusa-pradana-pradana adalah
    ..." (2026-10-08 replay): a word of the name beside the name is that name. Not a word that begins or ends another
    asked term's name: "apa beda ngaben massal dan ngaben svasta" became "apa ngaben massal svasta", and Qwen gave
    ngaben massal's definition alone (the 12 evaluation categories, 2026-10-27)."""
    for e in enriched:
        words = [w for w in re.split(r"[-\s]+", e["name"]) if len(w) >= 3]
        if len(words) < 2:
            continue
        alt, name = "|".join(re.escape(w) for w in words), re.escape(e["name"])
        others = [re.escape(x["name"]) for x in enriched if x is not e and x["name"].lower() != e["name"].lower()]
        # the word as the start of another name ("ngaben" of "ngaben svasta"), or as its end ("massal" of "ngaben
        # massal" before "dan ..."): the other term, not this one's word
        starts_other = rf"(?!(?:{'|'.join(others)})(?![-\w]))" if others else ""
        # both surfaces replaced ("purusa-pradana dan purusa-pradana") first, then one of them
        synth_q = re.sub(rf"\b{name}\s+(?:dan|atau|&|,)\s+{name}(?![-\w])", e["name"], synth_q, flags=re.I)
        synth_q = re.sub(rf"\b{name}\s+(?:dan|atau|&|,)\s+{starts_other}(?:{alt})(?![-\w])", e["name"], synth_q,
                         flags=re.I)

        def unless_ends_other(m: "re.Match") -> str:
            # "ngaben massal dan ngaben svasta" with e = ngaben svasta: "massal" ends "ngaben massal"
            before = m.string[:m.start()]
            if any(re.search(rf"(?<![-\w]){o}$", before + m.group("w"), re.I) for o in others):
                return m.group(0)
            return e["name"]
        synth_q = re.sub(rf"(?<![-\w])(?P<w>{alt})\s+(?:dan|atau|&|,)\s+{name}(?![-\w])", unless_ends_other, synth_q,
                         flags=re.I)
    return synth_q


@dataclass
class _Question:
    """What _synthesize knows about the question, built once by _read_question and shared by its steps."""
    msg: Text                                 # the user's message, "kelengkapan" read as sarana (_equipment_as_sarana)
    enriched: List[Dict[str, Any]]            # the resolved terms, with their context filled in for this question
    tracker: Optional[Tracker]
    word_meaning: bool                        # "arti kata X"
    consequence_q: bool                       # "kalau tidak ngaben ..."
    families: List[str]                       # the asked aspect families (_aspect_families)
    aspect_preds: Any                         # their predicates, None for no aspect
    day_q: bool                               # a question about days (dewasa ngaben)
    class_list: Any                           # (class name, term names) of a class list, else None
    stages_q: bool
    link_to: Any                              # the linking targets of a relation question (_link_filter)
    contents_q: bool
    keep_children: Any
    overview: bool                            # a plain "apa itu X"
    previous: Optional[Text]                  # the bot's last answer
    follow_up: bool                           # a follow-up on the same term (rule 32)
    context_items: List[Dict[str, Any]]       # the prompt's context entries
    why_q: bool
    has_reason: bool                          # a purpose / meaning fact exists (_strip_why_refusal may cut)
    missing_aspects: List[str]                # asked aspects no fact covers (rule 23, _say_unrecorded)
    composition_q: bool
    synth_q: Text                             # the question with each term as the KB names it
    corrections: List[Text]                   # "X bukan ... sasih" openings (_misclassed_terms)
    about: Dict[str, Any]                     # the term an honest miss describes
    raw_context: Text = ""                    # the compact JSON context, set by _synthesis_user_prompt


def _read_question(user_msg: Text, enriched: List[Dict[str, Any]], tracker: Optional[Tracker]) -> Optional[_Question]:
    """What the question asks and which context it gets: the aspect, its shape (why, consequence, days, stages,
    class list, relation ...), the follow-up, the context entries, the question as the KB names its terms. Fills
    the terms' aspect facts on the way. None when the graph is down (_outage_answer)."""
    # A word-meaning question is answered from definitions alone: with the edges
    # in context too, the small model kept listing them ("pitra berwujud sekah
    # kangsen, menerima daksina tapakan ...") instead of saying what the words mean.
    user_msg = _equipment_as_sarana(user_msg, enriched)
    word_meaning = bool(_WORD_MEANING_RE.search(user_msg))
    consequence_q = bool(_CONSEQUENCE_Q_RE.search(user_msg))
    families = _aspect_families(user_msg)
    aspect_preds = _aspect_predicates(user_msg)
    # the text-only attributes of the asked aspect (a word-meaning question gets the
    # literal meaning / word origin ones); none for a plain "apa itu X"
    attr_preds = PREDICATE_FAMILIES["asal_kata"] if word_meaning else aspect_preds
    content = get_content()
    # not a question about one month or day the message names: "kenapa sasih malamasa tidak boleh
    # dilaksanakannya ngaben" got rule 22's two groups and dewasa ngaben's whole wuku sentence appended (Tier B,
    # plan #16, 2026-10-26) -- dewasa ngaben is in its context for the rule, not to list every day
    named_day = any(e["id"] in ("purnama", "tilem") or any(content.is_kind_of(e["id"], c) for c in ("sasih", "wuku", "wewaran"))
                    for e in enriched)
    day_q = any(e["id"] == "dewasa_ngaben" for e in enriched) and (
        bool(re.search(r"\bhari\b", user_msg, re.I)) or _asks_about_day(user_msg) and not named_day)
    for e in enriched:
        # "hari apa yang harus dihindari untuk ngaben dan kenapa" asks why those days: ngaben's
        # own purposes ("menjaga harmoni ...") came back as the reason to avoid kekeran desa
        # (Tier B 2026-10-02)
        if day_q and e["id"] != "dewasa_ngaben":
            e["aspect_facts"] = []
            # nor what comes before or after the ceremony: "nenek meninggal pas sasih kadasa, terus kapan ngabennya
            # bisa dilaksanain?" added "Jika dalam 42 hari setelah kematian ... Ngangsen" from ngangsen
            # DILAKUKAN_SETELAH ngaben and its gloss -- 42 days after the ngaben, not the death (plan #17, Tier B
            # 2026-10-27; the run before had no such sentence: a near-tie)
            e["relationships"] = [r for r in e.get("relationships") or [] if r.get("relation") not in _ORDER_PREDICATES]
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
    if neo4j_conn.failed:
        return None
    class_list = _class_filter(user_msg, enriched)
    if not class_list and "sarana" not in families:
        # computed only for the class filter, which did not apply
        for e in enriched:
            e["sarana_facts"] = []
    stages_q = "tahapan" in families
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
                     and not consequence_q
                     and sum(1 for r in enriched[0]["relationships"]
                             if r.get("target_definition") and _says_what_for(r["target_definition"])) >= 2
                     else None)
    meaning_words = None
    if aspect_preds and aspect_preds & PREDICATE_FAMILIES["simbol"]:
        names = set().union(*(_content_words(e["name"]) for e in enriched)) if enriched else set()
        meaning_words = (_content_words(user_msg) - names) | {
            _NUMBER_WORDS[n] for n in re.findall(r"\b\d{1,2}\b", user_msg) if n in _NUMBER_WORDS}
    # a plain "apa itu X" / "jelaskan X" about one term -- not a list question ("apa saja sasih yang
    # berbadankan kosong" lost the wuku of each pair under rule 31, Tier B 2026-10-08)
    overview = (aspect_preds is None and not word_meaning and len(enriched) == 1 and not class_list
                and not _SPECIFIC_Q_RE.search(user_msg) and not consequence_q and not _LIST_Q_RE.search(user_msg)
                and bool(_OVERVIEW_Q_RE.search(user_msg)
                         or not _sentence_roots(re.sub(re.escape(enriched[0]["name"]), " ", user_msg, flags=re.I))))
    # a follow-up on the same term ("apa maknanya hal tersebut?") -- the previous answer is about
    # it. Not a message that names the term, by any surface: "apa makna bade tingkat sembilan"
    # after "apa makna tingkat 9" asks again in other words and wants the answer, which the
    # follow-up's no-repeat rule cut (Tier B 2026-10-08)
    # Nor one asking the same aspect again: "kenapa harus 11?" after "kenapa bade ada yang
    # bertingkat 11" lost the very reason it asked for, as a repeat (Tier B 2026-10-08).
    previous = _last_bot_utterance(tracker) if tracker is not None else None
    follow_up = bool(previous and enriched and tracker.get_slot("current_entity") == enriched[0]["name"]
                     and set(families) - set(_aspect_families(_previous_user_message(tracker)))
                     and not enriched[0].get("asked_as")
                     and enriched[0]["id"] not in _named_terms(user_msg, everyday=True)
                     and not any(n and re.search(rf"\b{re.escape(n)}\b", user_msg, re.I)
                                 for n in [enriched[0]["name"]] + list(enriched[0].get("aliases") or [])))
    context_items = _llm_context(enriched, with_relationships=not word_meaning,
                                 only_predicates=aspect_preds, keep_to=link_to,
                                 contents_only=contents_q,
                                 part_definitions=not contents_q or bool(_EXPLAIN_EACH_RE.search(user_msg)),
                                 keep_children=keep_children, meaning_words=meaning_words,
                                 overview=overview)
    # a contents or sarana list names items only (rules 13 and 19), and a word-meaning answer
    # uses definitions alone: the other terms' explanations would come back as roles there
    if not (contents_q or word_meaning or "sarana" in families):
        _add_related_terms(context_items, enriched)
    # "emang kalok semisal nggak ngaben kenapa?" asks what follows, not why ngaben exists
    why_q = bool(_WHY_Q_RE.search(user_msg)) and not consequence_q
    # with a purpose/meaning fact in context the model still opened with "alasannya belum
    # tercatat" (T39/T68/T74): that opening is cut by code (_strip_why_refusal), not forbidden
    # here -- a rule saying "never say it is not recorded" made it invent reasons ("agar ...
    # mendapatkan keberkahan yang maksimal", Tier B 2026-10-01)
    # For a why-avoided question the definition's judgement IS the reason: "kenapa tidak boleh
    # melakukan upacara pada sasih paruwak tahuk?" opened "Maaf, alasannya belum tercatat. Namun,
    # ... termasuk dalam alaning dewasa (hari-hari buruk)" (2026-10-07 batch)
    has_reason = _has_reason_facts(enriched) or (
        why_q and bool(_WHY_AVOID_Q_RE.search(user_msg))
        and any(_JUDGEMENT_RE.search(e.get("definition") or "") for e in enriched))
    # "hari baik ngaben" got every sasih and wewaran rule in the definition's order: "content good,
    # but clunky; it doesn't immediately make clear it has answered" (user, conersation.md 2026-10-07)
    # (a why-question's missing reason is rule 21's)
    missing_aspects = list(dict.fromkeys(
        f for f in families if f in _ASPECT_LABELS and not (why_q and f in _OUTGOING_ONLY_FAMILIES)
        and not class_list and enriched and not _aspect_present(f, enriched)))
    # Ask the synthesis model about the canonical name. Shown "apa itu lingga sarira"
    # beside an entry named "suksma sarira", it wrote "lingga sarira termasuk salah
    # satu jenis suksma sarira" -- even when told the two are one thing (2026-09-25).
    # The answer still opens with "<asked name> adalah sebutan lain untuk <name>" (below).
    # A misspelling is replaced too, or the model repeats it (typed_as).
    synth_q = user_msg
    for e in enriched:
        for surface in (e.get("asked_as"), e.get("typed_as")):
            if surface:
                # not inside a hyphenated word: "purusa dan pradana" became "purusa-pradana", then
                # the typed "purusa" was replaced inside it -- "purusa-pradana-pradana" (2026-10-08)
                synth_q = re.sub(r"(?<![\w-])" + re.escape(surface) + r"(?![\w-])", e["name"], synth_q, flags=re.I)
    # "nyiramin layon" -> "nyiramang layon layon" (T88)
    synth_q = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", synth_q, flags=re.I)
    synth_q = _collapse_name_words(synth_q, enriched)
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
    composition_q = _composition_q(user_msg)
    # the term an honest miss describes: a class list ("upakara apa saja yang digunakan dalam wayang") is
    # about the term it scopes, not the class -- its miss described banten (NLU sweep 2026-10-19)
    about = next((e for e in enriched if class_list and e["name"] in class_list[1]), enriched[0])
    return _Question(
        msg=user_msg, enriched=enriched, tracker=tracker, word_meaning=word_meaning, consequence_q=consequence_q,
        families=families, aspect_preds=aspect_preds, day_q=day_q, class_list=class_list, stages_q=stages_q,
        link_to=link_to, contents_q=contents_q, keep_children=keep_children, overview=overview, previous=previous,
        follow_up=follow_up, context_items=context_items, why_q=why_q, has_reason=has_reason,
        missing_aspects=missing_aspects, composition_q=composition_q, synth_q=synth_q, corrections=corrections,
        about=about)


def _synthesis_rules(q: _Question) -> str:
    """The system prompt: the standing rules 1-11, then each rule for this question's shape (12-32)."""
    user_msg, enriched, word_meaning, consequence_q = q.msg, q.enriched, q.word_meaning, q.consequence_q
    day_q, class_list, stages_q, link_to = q.day_q, q.class_list, q.stages_q, q.link_to
    keep_children, overview, previous, follow_up = q.keep_children, q.overview, q.previous, q.follow_up
    why_q, missing_aspects, about = q.why_q, q.missing_aspects, q.about
    synth_sys_prompt = """
    You are a knowledgeable, factual assistant for the Balinese Ngaben ceremony.

    RULES:
    1. Answer ONLY the user's question, using the provided knowledge-base context. The line 'Yang ditanyakan' says what the question asks, about which term (for a follow-up, the term it points back to): answer exactly that, and begin with it. Each entry has a 'term', its 'definition', optional 'also_called' (other names for the term), 'relationships' -- each relationship is a 'fact' sentence (already in the correct direction; never reverse it) and sometimes a 'target_definition' explaining the other term -- and optional 'related_terms', short explanations of other terms its definition or facts name.
    2. Answer fully, like a patient teacher. Begin with the direct answer to the question in one or two sentences, then explain it in connected sentences or short paragraphs: give the numbers, examples, names and reasons the context states, and when you mention another term, explain it briefly from its 'target_definition' or 'related_terms' entry. Use the 'related_terms' to connect facts (for example, what is still left after one ceremony that the next one completes). Leave out facts that do not help answer the question. For "apa hubungan X dan Y", explain the link itself -- do not describe X and Y one by one. State each fact ONCE: never say the same thing again in other words, and never end with a summary that repeats ("Dengan demikian ..."). Never open with a sentence that only says the topic is meaningful, important or closely related ("X memiliki makna yang mendalam dalam ritual Ngaben") -- open with the answer itself.
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

    if overview:
        # "apa itu bade": "a miss and match of a lot of different infos regarding one topic that
        # isnt worded properly. It sometimes repeats itself. and some of the infos can be
        # elaborated further" (conersation.md 2026-10-07)
        synth_sys_prompt += (
            "\n    31. Organize the answer by topic, one short paragraph each, in this order and only for "
            "topics the context covers: what it is; what it is for or what it means; how it is made, "
            "used or carried out; its kinds, parts or stages. Put every fact under one topic only. "
            "Rather than listing many small facts, explain the important ones: say what a named term is "
            "from its 'target_definition' or 'related_terms' entry and why it matters here.\n")
    if follow_up:
        # "apa maknanya" after "apa itu pradaksina": "this is okay but how is this one more
        # elaborate than the previous one" (conersation.md 2026-10-07)
        synth_sys_prompt += (
            "\n    32. This is a follow-up about the same term. The user has ALREADY read this answer: «"
            + previous[:900] + "» Do not repeat it. Answer the new question with what that answer did "
            "not say -- go deeper into the asked aspect with the 'target_definition', 'related_terms' and "
            "facts it did not use. If the context has nothing more on it, say in one sentence that nothing "
            "further is recorded about that, and recall the key point in one sentence.\n")
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
    if stages_q:
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
    if _whether_question(user_msg):
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
    if consequence_q:
        synth_sys_prompt += (
            "\n    30. The user asks what happens if something is NOT done or does not happen. Answer "
            "that, not what the thing is. First say what it achieves according to the context -- what "
            "it releases, returns, purifies or raises -- as what would then not be achieved; then why "
            "that matters, following the chain of purposes the context states (what must be returned "
            "and why, what is freed and where it can then go, what higher goal it is a step towards). "
            "Use only purposes and consequences the context states. Do not list its stages, kinds, "
            "sarana or levels. If the context states no purpose or consequence, reply: 'Maaf, "
            "akibatnya belum tercatat di basis data.'\n")
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
            "landep), not only a sasih (month). Begin with ONE sentence that answers the question "
            "directly (for good days: the best sasih and that the day also depends on wuku/wewaran). Then "
            "give two short groups from the definition of dewasa ngaben -- 'Menurut sasih:' and 'Menurut "
            "wuku dan wewaran:' -- each naming what the question asks for (good ones for good days, "
            "avoided ones for days to avoid), with the other kind in at most one sentence. Use only what "
            "that definition lists. Something is avoided only where the definition says so (dihindari, "
            "tidak boleh, sasih mati); dewasa madya (kaenem, kapitu) is middling, not avoided. A reason "
            "for avoiding one comes only from that term's own definition or 'related_terms'.\n")
    if missing_aspects:
        # "siapa yang melakukannya?" about pangringkes got "biasanya melibatkan keluarga dekat,
        # tetua desa ..." (T64); "apa tujuannya" an invented "sebelum dimasukkan ke dalam kubur" (T66)
        asked = ", ".join(_aspect_label(f, user_msg, english=True) for f in missing_aspects)
        # what 'Yang ditanyakan' asks for is then the gap: told by rule 1 to begin with it, the model
        # made up who performs pangringkes ("keluarga dekat", Tier B 2026-10-09). Said in rule 1 for
        # every question, the same words cost other answers their facts ("purusa" for pradaksina).
        synth_sys_prompt += (
            f"\n    23. The user asks about {asked} of {enriched[0]['name']}. No fact in the context states "
            "it. Unless a definition states it, begin by saying that it is not recorded in the knowledge "
            "base, although 'Yang ditanyakan' asks for it. Never guess, and never use 'biasanya', "
            "'umumnya' or 'mungkin' to fill the gap.\n")
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
    return synth_sys_prompt


def _synthesis_user_prompt(q: _Question, synth_sys_prompt: str) -> str:
    """The user prompt: question, what it asks, the context fitted to the budget, the question again. Sets
    q.raw_context."""
    user_msg, enriched, families, contents_q = q.msg, q.enriched, q.families, q.contents_q
    context_items, synth_q, raw_context = q.context_items, q.synth_q, q.raw_context
    # The question comes again after the context: it must survive any truncation, and
    # a small model follows the last instruction it read. With it, in plain words, what it asks
    # (rule 1): a follow-up names no term ("apa maknanya?").
    # Not for a contents/made-of question, whose list code builds: shown "Yang ditanyakan: isi atau
    # bahan tirta pangentas", the model gave each part a made-up gloss ("Soda adalah sejenis bahan
    # kimia", "Uulantaga adalah sejenis tumbuhan") on every load (Tier B 2026-10-09).
    focus = "" if contents_q or _composition_q(user_msg) else _question_focus(synth_q, enriched, families)
    # No reasoning step before a whether-verdict any more: the hidden <pikir> note (added 2026-10-12, when it took
    # qwen2.5 from 4 to 8 right of 12 whether-questions) changed no verdict of the 12 on Qwen 3.8 and cost ~30% more
    # tokens (batch_runs/fix-2026-10-27/pikir/RESULTS.md); dropped on the user's word 2026-11-02 after the Tier B
    # whether-turns ran without it (batch_runs/pikir-drop-2026-11-02/).
    budget = _PROMPT_CHAR_BUDGET - len(synth_sys_prompt) - 2 * len(synth_q) - 2 * len(focus) - 250
    raw_context = _json_compact(_fit_context(context_items, budget))
    synth_user_prompt = (f"Pertanyaan: {synth_q}\n" + (f"Yang ditanyakan: {focus}\n" if focus else "")
                         + f"Konteks:\n{raw_context}\n\n"
                         f"Jawab pertanyaan ini dalam bahasa Indonesia: {synth_q}"
                         + (f" (yang ditanyakan: {focus})" if focus else ""))
    q.raw_context = raw_context
    return synth_user_prompt


def _code_answer(q: _Question) -> Optional[str]:
    """An answer code writes without the model, or None: a raw material, a stated rule / norm / reason / order /
    day list ..., a contents miss, an aspect or class-list miss."""
    user_msg, enriched, families, class_list = q.msg, q.enriched, q.families, q.class_list
    follow_up, context_items, missing_aspects, composition_q = q.follow_up, q.context_items, q.missing_aspects, q.composition_q
    # "apa saja isi banten peras": nothing records its contents, and with rule 13 in the prompt
    # the model still listed "upacara pengaskaran, pemelaspas kajang ..." as its contents (Tier B
    # 2026-10-01) -- that miss is answered without the model
    no_contents = bool(
        _contents_question(user_msg) and set(families) == {"komposisi"} and context_items
        and not context_items[0]["relationships"] and not context_items[0].get("facts")
        and not _CONTENTS_IN_DEF_RE.search(enriched[0].get("definition") or ""))
    if composition_q:
        raw_answer = _raw_material_answer(enriched)
        if raw_answer:
            return _tidy_answer(raw_answer)
        if _composition_breakdown(enriched[0]["id"]):
            no_contents = False
    usage_answer = (_usage_norm_answer(user_msg, enriched) or _stated_rule_answer(user_msg, enriched)
                    or _stated_prohibition_answer(user_msg, enriched)
                    or _case_compare_answer(user_msg, enriched) or _order_answer(user_msg, enriched)
                    or _good_days_answer(user_msg, enriched) or _avoided_days_answer(user_msg, enriched)
                    or _stated_reason_answer(user_msg, enriched)
                    or _kind_consequence_answer(user_msg, enriched)
                    or _two_definitions_answer(user_msg, enriched)
                    or _duration_miss(user_msg, enriched)
                    or _name_answer(user_msg, enriched))
    if usage_answer:
        return _tidy_answer(usage_answer)
    if no_contents:
        name, known = enriched[0]["name"], _known_sentence(enriched[0].get("definition"))
        answer = (f"Maaf, isi atau bahan {name} belum tercatat di basis data."
                  + (f" Yang tercatat tentang {name}: {known}" if known else ""))
        return _tidy_answer(answer)
    if not follow_up:
        miss = (_class_list_miss(class_list, enriched) if class_list
                else _code_miss(user_msg, enriched, families, missing_aspects))
        if miss:
            return _tidy_answer(miss)
    return None


def _llm_answer(q: _Question, synth_sys_prompt: str, synth_user_prompt: str) -> str:
    """The model's answer: asked again if it wrote English, cut to its last full sentence if cut off."""
    user_msg, enriched = q.msg, q.enriched
    cut_off = False
    def ask(system: str, purpose: str = "synthesize") -> str:
        nonlocal cut_off
        text, cut_off = _llm_invoke([{"role": "system", "content": system},
                                     {"role": "user", "content": synth_user_prompt}], purpose)
        return text

    answer = ask(synth_sys_prompt)
    english = _english_words(answer)
    if _looks_english(answer) or english:
        _log_fabrication(user_msg, enriched, answer, kind="llm_english_retry")
        avoid = f", tanpa kata bahasa Inggris seperti {', '.join(english)}" if english else ""
        answer = _swap_english(ask(synth_sys_prompt + f"\n    Tulis seluruh jawaban dalam bahasa Indonesia{avoid}.\n",
                                   "synthesize_english_retry"))
    if cut_off:
        answer = _trim_cut_off(answer)
    return answer


def _answer_overrides(q: _Question, answer: str) -> str:
    """An empty or English reply, a refusal or a fabrication: the definitions, an honest miss, or the refusal
    kept with what is recorded."""
    user_msg, enriched, consequence_q, aspect_preds = q.msg, q.enriched, q.consequence_q, q.aspect_preds
    overview, about, raw_context = q.overview, q.about, q.raw_context
    if not answer.strip() or _looks_english(answer):
        # an empty reply reached the user as silence
        _log_fabrication(user_msg, enriched, answer, kind="llm_empty_or_english_override")
        answer = _deterministic_answer(enriched)
    elif _has_grounding(enriched):
        # a plain "apa itu X" -- not any question with no aspect word found: "sasih apa yang baik untuk dasa
        # mala", "apa hubungan antara tiying gading dengan bwah loka", "Kayu Cendana dilakukan sebelum atau
        # sesudah wesia" had their honest "not recorded" swapped for bare definitions (12 a run, LLM
        # comparison 2026-10-20)
        # not a consequence question ("tanpa" is a relation word): "apa yang terjadi jika Sorohan Kecil dilakukan
        # tanpa ngaben" got "Maaf, hubungan antara sorohan kecil dan ngaben belum tercatat" (plan #16)
        relation_q = len(enriched) >= 2 and bool(_RELATION_Q_RE.search(user_msg)) and not consequence_q
        plain = (aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg) and not relation_q
                 and not _ORDER_Q_RE.search(user_msg)
                 and (overview or bool(_WHAT_IS_SHAPE_RE.search(user_msg))))
        known = _known_sentence(about.get("definition"))
        if _has_refusal_signal(answer):
            if plain:
                # "apa itu X" refused although X's definition was right there
                _log_refusal(user_msg, enriched, answer)
                answer = _deterministic_answer(enriched)
            elif relation_q:
                # no link recorded: say so about both, with what each is
                _log_refusal(user_msg, enriched, answer, kept=True)
                a, b = enriched[0], enriched[1]
                answer = f"Maaf, hubungan antara {a['name']} dan {b['name']} belum tercatat di basis data."
                for e in (a, b):
                    k = _known_sentence(e.get("definition"))
                    if k:
                        answer += f" Yang tercatat tentang {e['name']}: {k}"
            else:
                # the asked detail really is not recorded: keep the refusal, add what is
                _log_refusal(user_msg, enriched, answer, kept=True)
                if known:
                    answer = f"{answer.rstrip()} Yang tercatat tentang {about['name']}: {known}"
        elif _has_fabrication_signal(answer, enriched, raw_context):
            _log_fabrication(user_msg, enriched, answer)
            if plain or not known:
                answer = _deterministic_answer(enriched)
            else:
                # an invented reason for "kenapa angka 11 dipilih ..." is replaced by an
                # honest miss, not by a definition that answers something else
                answer = ("Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data. "
                          f"Yang tercatat tentang {about['name']}: {known}")
    return answer


def _answer_checks(q: _Question, answer: str) -> str:
    """The checks on the model's answer, in order: cut what the context does not support, complete what it left
    out, put the asked thing first. Each says in its comment or name what it catches."""
    user_msg, enriched, tracker, word_meaning = q.msg, q.enriched, q.tracker, q.word_meaning
    consequence_q, families, aspect_preds, day_q = q.consequence_q, q.families, q.aspect_preds, q.day_q
    class_list, stages_q, previous, follow_up = q.class_list, q.stages_q, q.previous, q.follow_up
    why_q, has_reason, missing_aspects, composition_q = q.why_q, q.has_reason, q.missing_aspects, q.composition_q
    synth_q, about, raw_context = q.synth_q, q.about, q.raw_context
    answer = _fix_misspellings(_tidy_answer(answer), raw_context)
    avoid_q = bool(_WHY_AVOID_Q_RE.search(user_msg))
    if why_q and has_reason and _why_about_term_only(user_msg, enriched, avoid_q):
        # a why-avoided answer's reasons are judging words (tidak baik, sasih mati), not purpose words
        answer = _strip_why_refusal(answer, None if avoid_q else enriched)
    answer = _drop_speculation(answer, raw_context)
    answer = _drop_unsupported(answer, raw_context, synth_q)
    answer = _drop_unlinked_glosses(answer, raw_context)
    answer = _drop_filler_openers(answer, user_msg, enriched)
    # not on a why-question about something else than the term, which its purpose does not answer: "kenapa jenazahnya
    # harus dibakar? gak dikubur aja gitu" got "Selain itu, ngaben berfungsi sebagai perekat kohesi sosial. Selain itu,
    # ngaben melambangkan siklus kematian." (human test 2026-11-03)
    if follow_up and aspect_preds and not (why_q and not _why_about_term_only(user_msg, enriched, avoid_q)):
        # first, so that a sentence only recalling the previous answer can go once a new fact is there
        answer = _complete_aspect_facts(answer, enriched)
    answer = _keep_asked_tier(answer, user_msg, enriched)
    # before the completions below: what code appends is never a repeat to drop. The last answer
    # counts only on a follow-up: tried on every turn on the same topic, it cut the answer itself
    # whenever the turn before had said it -- "apa guna patulangan" lost "berfungsi sebagai tempat
    # pembaringan jenazah", "apa makna banten pejati" its meaning (2026-10-08 replay). A re-asked
    # question wants its answer again.
    answer = _drop_repeated_sentences(answer, previous if follow_up else "", loose=True,
                                      protect=_asked_specifics(user_msg, enriched))
    if consequence_q:
        # the focus line echoed back: "Apa yang terjadi kalau sawa tidak kembali menjadi
        # pancamahabutha adalah sawa tidak dapat ..." -> "Kalau sawa ..., sawa tidak dapat ..."
        # (2026-10-09 replay)
        answer = re.sub(r"^\s*(?:apa yang terjadi|akibat(?:nya)?)\s+(kalau|bila|jika|apabila)\s+(.+?)\s+adalah\s+"
                        r"(?:bahwa\s+)?",
                        lambda m: f"{m.group(1).capitalize()} {m.group(2)}, ", answer, count=1, flags=re.I)
        answer = _trim_consequence_answer(answer)
        answer = _complete_consequence_goal(answer, enriched)
    # ... and their everyday forms: "ngaben pas purnama boleh gak?" (in _PERMISSION_Q_RE), "ngabennya tetep
    # bisa jalan gak?"
    casual = bool(_CASUAL_YES_NO_RE.search(user_msg))
    if _PERMISSION_Q_RE.search(user_msg):
        # synth_q: the question with each term as the KB names it -- "sasih kedasa" read as a word
        # the context never uses, so the kadasa rule was cut as unstated (Tier B 2026-10-08)
        answer = _fix_unstated_prohibition(answer, raw_context, user_msg=synth_q)
        answer = _complete_duty_verdict(answer, raw_context, synth_q)
    elif _CAPABILITY_Q_RE.search(user_msg) or casual and re.search(r"\b(?:bisa|dapat)\b", user_msg, re.I):
        answer = _fix_unstated_prohibition(answer, raw_context, capability=True, user_msg=synth_q)
    if _whether_question(user_msg):
        answer = _drop_hollow_verdict(answer)
        answer = _complete_terse_verdict(answer, enriched)
    answer = _complete_rule_answer(answer, raw_context, synth_q)
    answer = _fix_only_that(answer, user_msg)
    answer = _fix_kind_claims(answer, enriched)
    answer = _fix_moved_member_facts(answer, enriched)
    answer = _fix_lone_day_claims(answer, raw_context)
    answer = _drop_reversed_offerings(answer, enriched)
    answer = _name_missing(answer, user_msg, enriched, families, class_list)
    answer = _say_unrecorded(answer, user_msg, enriched, missing_aspects)
    if not word_meaning:
        # after every guard that cuts sentences: the opening it checks is the one the user reads
        same_topic = bool(previous and enriched and tracker is not None
                          and tracker.get_slot("current_entity") == enriched[0]["name"])
        # the last three answers: against the last one only, "jumlah mangle ... bergantung pada
        # tingkatan bade" came back every other turn of the bade-tier questions (2026-10-09 replay)
        answer = _lead_with_asked_aspect(answer, user_msg, enriched, families,
                                         previous="\n".join(_recent_bot_utterances(tracker)) if same_topic else None)
    answer = _complete_set_members(answer, enriched)
    if not class_list and (aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg)
                           or families == ["jenis"]):
        answer = _complete_kind_lists(answer, enriched)
    if families == ["sebutan_lain"]:
        answer = _complete_other_names(answer, enriched)
    if _USERS_Q_RE.search(user_msg):
        answer = _complete_usage_norms(answer, enriched)
    if (not class_list and aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg) and len(enriched) == 1
            and not _RELATION_Q_RE.search(user_msg) and not _COMPARE_Q_RE.search(user_msg)
            and _asks_what_it_is(user_msg)
            # or "apa itu X dan apa hubungannya dengan Y" about X first: "apa itu tri murthi dan apa
            # hubungannya dengan ngaben" opened with Brahma's definition, never saying what
            # Trimurti is (2026-10-08 replay)
            or _asks_what_is_first(user_msg, enriched)):
        answer = _ensure_definition_lead(answer, enriched)
        if _asks_what_is_first(user_msg, enriched):
            if not _opens_with(answer, enriched[0]):
                # the members named, but never what X is: the lead goes in front all the same
                lead = _first_sentence(_deterministic_answer([dict(enriched[0], aspect_facts=[])])
                                       or enriched[0].get("definition"), limit=600)
                if lead and lead not in answer:
                    answer = f"{lead}\n\n{answer}"
            # what the model said again below the lead goes ("Dewa Brahma, sebagai bagian dari
            # Trimurti, berperan sebagai pencipta alam semesta" below "Dewa Brahma sebagai pencipta")
            answer = _drop_repeated_sentences(answer)
    if not why_q:
        answer = _complete_sarana_lists(answer, enriched)
    if len(enriched) >= 2 and (_COMPARE_Q_RE.search(user_msg) or _RELATION_Q_RE.search(user_msg)):
        answer = _complete_stated_link(answer, enriched)
        answer = _complete_chain_link(answer, enriched, relation=bool(
            _RELATION_Q_RE.search(user_msg) and not _COMPARE_Q_RE.search(user_msg) and not consequence_q))
    if why_q and _WHY_AVOID_Q_RE.search(user_msg):
        answer = _complete_stated_reasons(answer, enriched, user_msg)
    if composition_q:
        answer = _complete_composition(answer, enriched)
    if day_q:
        answer = _complete_day_rules(answer, enriched)
    if stages_q:
        answer = _drop_kinds_from_stages(answer, enriched)
        if not _ONE_STAGE_Q_RE.search(user_msg):
            answer = _complete_stage_order(answer, enriched)
    if word_meaning:
        answer = _add_literal_meaning(answer, enriched, user_msg)
    answer = _drop_empty_items(answer)
    # a sentence cut at a paragraph's start leaves its space: "\n\n Bahkan dalam kasus khusus ..." (Tier B
    # 2026-10-15); a nested list item keeps its indent
    answer = re.sub(r"\n[ \t]+(?=[^\s\-*•\d])", "\n", answer)
    # a connective whose sentence before it was cut: "Meskipun demikian, bale semanggen ..." opened
    # the answer (2026-10-09)
    lead = _OPENING_LEANBACK_RE.match(answer)
    if lead and len(answer) > lead.end():
        answer = answer[lead.end():][:1].upper() + answer[lead.end() + 1:]
    if not answer.strip():
        # the guards above cut every sentence: "apa fungsi bale delod dalam prosesi persemayaman
        # jenazah?" reached the user as silence (2026-10-08 batch)
        known = _known_sentence(about.get("definition"))
        answer = _name_missing("Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data."
                               + (f" Yang tercatat tentang {about['name']}: {known}" if known else ""),
                               user_msg, enriched, families, class_list)
    return answer


def _closing_notes(q: _Question, answer: str) -> str:
    """The corrections ("X bukan ... sasih"), the other-name note, or the "same as before" note."""
    user_msg, enriched, tracker, corrections = q.msg, q.enriched, q.tracker, q.corrections
    about = q.about
    for c in reversed(corrections):
        if _ortho_key(c) not in _ortho_key(answer):
            answer = f"{c} {answer}"

    # the user asked by another name for the same concept -- say so, instead of
    # the "nothing more is recorded" note below, which read as a refusal after
    # "apa itu samskara" following "apa itu sangaskara" (2026-09-24)
    synonyms = _synonym_sentences(enriched, answer)
    if synonyms:
        answer = _with_note(" ".join(synonyms), answer)
    elif (tracker is not None and not answer.startswith("Maaf")
          and _is_near_repeat(answer, _last_bot_utterance(tracker))
          and not any(e["name"].lower() in user_msg.lower() for e in enriched)
          # not when it gives what this question asks and the last answer did not: "apa makna
          # tingkat 9" after "... tingkat 11" was called the same as before (2026-10-09 replay)
          and not any(re.search(rf"\b{re.escape(w)}\b", answer, re.I)
                      and not re.search(rf"\b{re.escape(w)}\b", _last_bot_utterance(tracker) or "", re.I)
                      for w in _asked_specifics(user_msg, enriched))):
        # a follow-up like "tapi digunakan bagaimana?" that got the same facts back --
        # not a user who re-asked about the term by name
        answer += (
            " (Ini sama dengan penjelasan saya sebelumnya -- informasi yang lebih "
            "rinci mengenai hal ini belum tercatat di basis data.)"
        )

    return answer


def _synthesize(user_msg: Text, enriched: List[Dict[str, Any]], tracker: Optional[Tracker] = None) -> str:
    """Step 4: synthesize a natural Indonesian answer from `enriched`, with a
    deterministic guard against the local LLM refusing/hedging on context it was
    actually given (observed directly in conersation.md for terms that HAD
    resolved successfully -- e.g. ngeroras, naga banda, tirte, panca maha butha).

    The steps: _read_question, _synthesis_rules + _synthesis_user_prompt, _code_answer (no model), _llm_answer,
    _answer_overrides, _answer_checks, _closing_notes."""
    q = _read_question(user_msg, enriched, tracker)
    if q is None:
        return _outage_answer(enriched)
    synth_sys_prompt = _synthesis_rules(q)
    synth_user_prompt = _synthesis_user_prompt(q, synth_sys_prompt)
    code = _code_answer(q)
    if code is not None:
        return code
    try:
        answer = _llm_answer(q, synth_sys_prompt, synth_user_prompt)
    except Exception as e:
        # LLM down/unreachable/timed out/rate-limited -- fall back to the pure-Python
        # answer instead of crashing the action and leaving the user with no
        # reply at all.
        print(f"LLM synthesis error: {e}")
        return _deterministic_answer(enriched)
    answer = _answer_overrides(q, answer)
    answer = _answer_checks(q, answer)
    return _closing_notes(q, answer)


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
    # markdown emphasis shows as asterisks in a plain-text chat, and templates never use it: "1. **Pengawak:**
    # ...", "*Pabersihan Mati*" (NLU sweep 2026-10-19). A "* " list marker at a line's start stays.
    answer = re.sub(r"\*\*([^*\n]+?)\*\*", r"\1", answer)
    answer = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"\1", answer)
    # "Fakta yang tercatat mengenai lemat sudhamala adalah sebagai berikut:" talks of the prompt's facts; the
    # bot's own heading is "Yang tercatat tentang X:" (Tier B 2026-10-26; "Informasi yang tercatat ...", 2026-10-27)
    answer = re.sub(r"\b(?:fakta(?:-fakta)?|informasi) yang tercatat (?:mengenai|tentang) ([^:\n]+?)(?: adalah)?"
                    r"(?: sebagai berikut)?:", r"Yang tercatat tentang \1:", answer, flags=re.I)
    # "Status apakah niskala itu wajib atau tidak tidak tercatat." (Tier B 2026-10-26)
    answer = re.sub(r"\b(atau) tidak tidak\b", r"\1 tidaknya tidak", answer, flags=re.I)
    # the model asking itself in brackets: "Karena usianya empat bulan (sudah lebih dari lima bulan? Tidak, definisi
    # bilang ...), maka ..." (Tier B 2026-10-30). A "?" inside quotes is a quoted question and stays: the miss note
    # "(Catatan: '...?' tidak ditemukan ...)".
    answer = re.sub(r"\s*\((?=[^()\n'\"“”‘’]*\?)[^()\n]*\)", "", answer)
    # "pras arepan terbuat dari ..." (the model copies the question's lowercase name)
    return answer[:1].upper() + answer[1:]


# The fallback prompt's reply for an off-topic question.
_OFF_TOPIC_MARK = "DI_LUAR_TOPIK"
# Resolver tiers that match a name as written -- not a typo guess, and not a loose
# force_merge surface ("harga" -> harga tirtha made "berapa harga kopi" a KB question).
_NAMED_VIA = frozenset({"exact", "alias", "strip", "ortho"})


# ---------------------------------------------------------------------------------------------
# Template answers: simple questions answered from the KB in code, with no LLM call (the senior's
# direction, 2026-10-13: save tokens). The NLU intent names the asked aspect. A simple question --
# one term (named, or the remembered topic of a clear follow-up), one aspect the intent and
# _aspect_families() agree on, none of the shapes in _TEMPLATE_BLOCKERS -- gets its template;
# anything else goes to the full pipeline (ActionGraphRAG: its code answers first, then the LLM),
# so a misrouted question costs tokens, never a wrong template.
# ---------------------------------------------------------------------------------------------
_ROUTING_LOG_PATH = _BOT_DIR / "routing_log.jsonl"
# intent -> the aspect family its template answers ("" = the definition; "induk" = what the term
# belongs to: its kind parents, the ceremony it is a stage of, what it is used in)
_TEMPLATE_INTENTS = {
    "tanya_definisi": "", "tanya_makna": "simbol", "tanya_fungsi": "fungsi", "tanya_jenis": "jenis",
    "tanya_tahapan": "tahapan", "tanya_komponen": "komposisi", "tanya_sarana": "sarana",
    "tanya_lokasi": "lokasi", "tanya_waktu": "waktu", "tanya_pelaku": "pelaku",
    "tanya_sebutan_lain": "sebutan_lain", "tanya_asal_kata": "asal_kata", "tanya_bagian_dari": "induk",
}
# the aspects _aspect_families() may find in a question a template answers (default: its own
# family only; finding none is fine -- the intent decides -- except for a definition)
_TEMPLATE_FAMILIES_OK = {"tahapan": {"tahapan", "cara"}, "induk": {"jenis", "tahapan"}}
_NARRATE_Q_RE = re.compile(r"\b(?:ceritakan|uraikan|jabarkan)\b", re.I)
# "apa itu X dan apa maknanya?", "di mana dan kapan ...", two questions in one message
# ("X disebut juga apa" asks one thing: its other names -- it went to the LLM, NLU sweep 2026-10-19)
_MULTI_ASK_RE = re.compile(r"\b(?:dan|serta|lalu|kemudian|(?<!disebut )(?<!dikenal )(?<!dinamakan )(?<!dipanggil )juga)"
                           r"\s+(?:apa|apakah|bagaimana|siapa|kapan|di ?mana|ke ?mana|dari ?mana|kenapa|mengapa|berapa)\b"
                           r"|\?.*\w.*\?", re.I)
# several earlier items at once: the extraction LLM settles which
_GROUP_REF_RE = re.compile(r"\b(?:keduanya|ketiganya|semuanya|masing-masing)\b", re.I)
# what may or must be done, by whom: "apa ketentuan penggunaan petulangan" wants who uses which form,
# and the purpose template gave its purpose (Tier B 2026-10-13)
_RULE_Q_RE = re.compile(r"\b(?:ketentuan(?:nya)?|aturan(?:nya)?|syarat(?:nya)?|larangan(?:nya)?|pantangan(?:nya)?)\b",
                        re.I)
# an amount, size or price -- no template states one. "berapa jenis/macam/tahap" stays: the kinds
# and stages templates number their lists. A retrain read "berapa harga tirtha" as tanya_definisi and
# it got harga tirtha's definition template (2026-10-14)
_COUNT_Q_RE = re.compile(r"\bberapa\b(?!\s+(?:jenis|macam|ragam|tipe|tahap))", re.I)
# a what-is question, whatever the intent says: with no aspect word in it, it gets the definition --
# "apa itu banten pamegat" came back as tanya_makna (its name had been drawn into a makna example)
# and got "makna banten pamegat belum tercatat" (Tier B 2026-10-13)
_WHAT_IS_SHAPE_RE = re.compile(_OVERVIEW_Q_RE.pattern + r"|\bapaan\b|\btuh\s+apa\b", re.I)
# question shapes the full pipeline answers: its code answers (days, order, stated rules) or the
# LLM. A number asks for one tier or count ("makna bade tingkat 9"), which _keep_asked_tier keeps.
_TEMPLATE_BLOCKERS = (
    ("relation", _RELATION_Q_RE), ("comparison", _COMPARE_Q_RE), ("why", _WHY_Q_RE),
    ("consequence", _CONSEQUENCE_Q_RE), ("permission", _PERMISSION_Q_RE), ("day", _DAY_Q_RE),
    ("narrate", _NARRATE_Q_RE), ("multi-part", _MULTI_ASK_RE), ("ordinal", _ORDINAL_REF_RE),
    ("group", _GROUP_REF_RE), ("number", _NUMERAL_RE), ("count", _COUNT_Q_RE), ("only-that", _ONLY_THAT_Q_RE),
    ("rule", _RULE_Q_RE),
    # "siapa yang tidak boleh ikut sembah bhakti" got "Sembah bhakti dipimpin oleh pemangku" (the 12 evaluation
    # categories, 2026-10-27): who may not take part is a rule (_stated_prohibition_answer)
    ("prohibition", _PROHIBITION_RE),
)
_ORIGIN_Q_RE = re.compile(r"\bdari\s*mana\b[^.?!]*\b(?:diperoleh|didapat\w*|diambil|berasal|asalnya)\b"
                          r"|\b(?:diperoleh|didapat\w*|diambil|berasal)\s+dari\s*mana\b", re.I)
# the stage after or before one: "apa tahapan setelah X", "tahap berikutnya setelah X"
_NEXT_STAGE_RE = re.compile(r"\b(?:setelah|sesudah|sebelum|berikutnya|selanjutnya|sesudahnya|setelahnya|"
                            r"sebelumnya)\b", re.I)
# the families a template answers with the term's own aspect facts, as a paragraph (_as_paragraph);
# for a place, time or doer, how the note on a ceremony with none of its own names it
_ASPECT_TEMPLATE_FAMILIES = frozenset({"simbol", "fungsi", "lokasi", "waktu", "pelaku", "cara"})
_STAGE_FALLBACK_HEADS = {"lokasi": "Tempat pelaksanaan", "waktu": "Waktu pelaksanaan", "pelaku": "Pelaku"}
# definition sentences that state the aspect (simbol / fungsi: the markers the LLM path checks
# its opening with)
_TEMPLATE_DEF_MARKERS = {
    **_FOCUS_MARKERS,
    # a person's duties: "apa tugas pemangku dalam ngaben" got "Maaf, fungsi atau tujuan pemangku belum tercatat"
    # above "Pemangku ... bertugas memimpin persembahyangan serta memohonkan tirtha" (2026-10-27)
    # (a duty, not "Saat bertugas ia berpijak pada padi": "Sangging untuk apa" got that, 2026-10-27)
    "fungsi": _FOCUS_MARKERS["fungsi"] + r"|bertugas\s+(?:untuk\s+)?me\w+|tugas(?:nya)?\s+(?:adalah|ialah|yaitu|me\w+)"
                                         r"|pihak yang",
    # (a god "berstana di Pura Dalem": "letak Hyang Prajapati" got "tempat ... belum tercatat" above that very
    # sentence, NLU sweep 2026-10-19)
    # (and "ditaruh pada bibir jenazah", "diletakkan sebagai elemen utama di dalam kawangen", "alas pada pepaga":
    # pedangal, cermin kecil, bunga tunjung putih and tikeh plasa got "tempat ... belum tercatat" above their own
    # place, LLM comparison 2026-10-20)
    # ("pada" only after a verb of placing: "dilakukan pada tahap ini", "berada pada masa Daksinayana" are times)
    # (not "dibuat dari", a material: "baja itu di mana" got "Kikir dan lemat dibuat dari baja"; nor a "yang"
    # clause, which places the noun before it: uang kepeng's "lima dewa yang berada di kelima penjuru" answered
    # "lokasi uang kepeng di mana" -- sheet Failed, route audit 2026-10-27)
    "lokasi": r"(?<!yang )(?:dilakukan|dilaksanakan|diadakan|diletakkan|ditempatkan|ditaruh|ditaruhkan|dipasang|"
              r"dimasukkan|disimpan|berada|disemayamkan|dibawa|dihanyutkan|diusung|dibaringkan|berstana|bersemayam|"
              r"terletak|bertempat)\s+(?:[\w-]+\s+){0,3}?(?:di|ke|dari)"
              r"|(?<!yang )dibuat\s+(?:[\w-]+\s+){0,3}?(?:di|ke)"
              # ("disumbatkan pada mulut jenazah": "pripih dimasukkan ke dalam apa" got "tempat pripih belum tercatat")
              r"|(?:diletakkan|ditempatkan|ditaruh|ditaruhkan|dipasang|dimasukkan|disimpan|disumbatkan|disumbat)"
              r"\s+(?:[\w-]+\s+){0,3}?pada"
              r"|alas\s+(?:pada|di)",
    # (not narrowed to "not before an active verb" for "setelah mencapai tingkat kebebasan" in Paksa Mahayana's
    # definition: that also dropped "saat membangunkan jenazah" for mantra and "saat memandikan jenazah" for
    # babelonyoh, 2026-10-19)
    # (a stage or ceremony dates it too: "Dasa Mala ... dibersihkan ... pada tahap Melelet")
    "waktu": r"saat|ketika|setelah|sesudah|sebelum|menjelang|selama|pada (?:hari|saat|waktu|malam|pagi|sore|tahap|"
             r"upacara|acara)",
    # how it is done ("melalui penyucian ... kedudukannya terangkat menjadi pitara": "alur preta" got only
    # "Preta menjadi pitra"; "mapendem adalah cara menyelenggarakan jenazah dengan menguburkannya", 2026-10-19)
    "cara": r"melalui|cara|caranya|tata pelaksanaan(?:nya)?|dimulai dengan|diawali dengan",
    # who does or makes it -- not who uses it: "Wadah ... lazimnya dipakai oleh warga" opened "siapa yang
    # membuat bade" (Tier B 2026-10-13)
    "pelaku": r"(?:dilakukan|dilaksanakan|diselenggarakan|dipimpin|dipuput|dibuat|dikerjakan|dimantrai|"
              r"dihaturkan|dibawakan)\s+oleh|pemimpin|pemuput",
}
# Definition words that may answer an aspect no fact states: "tirtha kawitan ... dimohon ... melalui pemangku
# kawitan setempat" answers who. With one of them the model gets the question; without, _code_miss says it.
_DEF_MAY_ANSWER = {
    "pelaku": re.compile(r"\boleh\b|\bmelalui\b|\bpemangku\b|\bsulinggih\b|\bpendeta\b|\bpandita\b|\bkeluarga\b"
                         r"|\bundagi\b|\bsangging\b|\bdipuput\b|\bdipimpin\b|\bmemimpin\b|\bmelaksanakan\b", re.I),
    "komposisi": re.compile(r"terbuat|dibuat|berisi|\bisi(?:nya)?\b|terdiri|tersusun|lempengan|bahan|campuran"
                            r"|\bdari\s+(?:daun|bambu|kayu|beras|kain|logam|janur)", re.I),
    "simbol": re.compile(r"melambangkan|lambang|simbol|bermakna|makna|perlambang|menggambarkan|menunjukkan", re.I),
    # (a duty too, as the fungsi template reads it: pemangku "bertugas memimpin persembahyangan")
    "fungsi": re.compile(r"\buntuk\b|berfungsi|\bsebagai\b|digunakan|dipakai|bertujuan|\bagar\b|bertugas|\btugas", re.I),
    "lokasi": re.compile(rf"\b(?:{_TEMPLATE_DEF_MARKERS['lokasi']})\b"
                         r"|\bdi\s+(?:setra|pura|rumah|merajan|sanggah|bale|natah|gria|laut|sungai)\b", re.I),
    "waktu": re.compile(rf"\b(?:{_TEMPLATE_DEF_MARKERS['waktu']})\b", re.I),
    "ciri": re.compile(r"warna|\bbentuk|berbentuk|ukuran|panjang|tingkat|lempengan", re.I),
    "sumber": re.compile(r"lontar|naskah|kitab|purana|sastra|pustaka|\bmenurut\b", re.I),
}


def _code_miss(user_msg: Text, enriched: List[Dict[str, Any]], families: List[str],
               missing: List[str]) -> Optional[str]:
    """One term, one asked aspect, no fact of it, and nothing in its definition that may answer it: the
    miss rule 23 makes the model write, written by code. 104 of the 254 answer calls of a run were that
    reply (~2K tokens each, LLM comparison 2026-10-20). Not for a question that asks more or something
    else (why, whether, a relation, a list, "apa itu X dan ...")."""
    if len(enriched) != 1 or len(families) != 1 or families != missing or _whether_question(user_msg):
        return None
    # "istilah Malamasa berasal dari mana" asks where the word comes from ("Kata mala berarti tidak baik"),
    # though "dari mana" reads as a place
    if _WORD_MEANING_RE.search(user_msg) or re.search(r"\b(?:istilah|kata|nama)\b", user_msg, re.I):
        return None
    pattern = _DEF_MAY_ANSWER.get(families[0])
    # "apa saja" asks for the parts themselves in "terdiri dari apa saja", "apa saja unsur X" -- and no
    # part nor kind is recorded (_aspect_present): 18 such misses went to Qwen in plan #16's test
    blockers = (_WHY_Q_RE, _CONSEQUENCE_Q_RE, _RELATION_Q_RE, _COMPARE_Q_RE, _PERMISSION_Q_RE, _NARRATE_Q_RE,
                _MULTI_ASK_RE, _WHAT_IS_RE, _DAY_Q_RE) + (() if families == ["komposisi"] else (_LIST_Q_RE,))
    if pattern is None or any(rx.search(user_msg) for rx in blockers):
        return None
    e = enriched[0]
    if pattern.search(_definition_text(e)):
        return None
    # a rite's "bahan / unsur" are what it uses: "bahan upacara ngelungah apa saja" got its ten sarana from
    # Qwen, and "belum tercatat" from this miss (plan #16, 2026-10-26)
    if (families == ["komposisi"] and get_content().entity_type.get(e["id"]) in _STAGE_TYPES
            and _sarana_by_place([e["id"]]).get(e["id"])):
        return None
    label = _aspect_label(families[0], user_msg)
    if families == ["komposisi"] and re.search(r"\bunsur|terdiri|tersusun|\bbagian|komponen", user_msg, re.I):
        label = "unsur atau bagian"
    return _template_miss(label, e)


# how long something takes, and a length of time a card states
_DURATION_Q_RE = re.compile(r"\bberapa\s+lama\b|\blama(?:nya)?\s+(?:waktu|proses\w*|upacara\w*|pelaksanaan\w*)\b"
                            r"|\bdurasi\w*|\bmemakan\s+waktu\b|\bberlangsung\s+berapa\b", re.I)
_DURATION_IN_TEXT_RE = re.compile(r"\bselama\b|\bberlangsung\b|\blamanya\b|\bmemakan waktu\b|\b(?:\d+|satu|dua|tiga|"
                                  r"empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|beberapa)\s+(?:hari|malam|"
                                  r"jam|minggu|pekan|bulan|tahun)\b", re.I)


def _duration_miss(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """How long the asked term takes, when nothing of its own -- its card, its text facts, its edges -- states a length
    of time: an honest miss by code. "berapa lama sih proses ngaben dari awal sampe selesai?" got "Proses Ngaben tidak
    memiliki durasi waktu (hari atau jam) yang tetap ... karena lamanya ... belum tercatat": no source says it has no
    fixed length (human test 2026-11-03)."""
    if not enriched or not _DURATION_Q_RE.search(user_msg) or _whether_question(user_msg):
        return None
    e = enriched[0]
    own = [_definition_text(e)] + [str(f) for f in e.get("facts") or []] + [
        json.dumps({k: v for k, v in r.items() if k != "target_definition"}, ensure_ascii=False)
        for r in e.get("relationships") or [] if r.get("outgoing")]
    if any(_DURATION_IN_TEXT_RE.search(t) for t in own):
        return None
    # what a card linked to it says of how long it takes: ngaben's own length is recorded nowhere, but krematorium's
    # card (DIGUNAKAN_UNTUK ngaben) says "prosesnya selesai dalam satu hari" (L66)
    content = get_content()
    linked = sorted({f["object_id"] for f in content.facts_by_subj.get(e["id"], [])}
                    | {f["subject_id"] for f in content.facts_by_obj.get(e["id"], [])})
    for lid in linked:
        clause = _PROCESS_DURATION_RE.search(content.best_definition(lid) or "")
        if clause:
            return (f"Maaf, lama pelaksanaan {e['name']} secara umum belum tercatat di basis data. Yang tercatat tentang "
                    f"{content.entity_name[lid]}: {clause.group(0)}.")
    return _template_miss("lama pelaksanaan", e)


# a card's clause saying how long its process takes: "prosesnya selesai dalam satu hari"
_PROCESS_DURATION_RE = re.compile(r"(?:\b\w+nya\s+)?(?:selesai dalam|berlangsung selama|memakan waktu|dalam tempo)\s+"
                                  r"[^,;.()]+?(?=\s+(?:dan|tetapi|namun|serta)\b|[,;.()]|$)", re.I)
# "yang mandiin jenazah itu namanya apa?", "apa nama upacara memandikan jenazah"; not another name ("nama lainnya apa")
_NAME_OF_Q_RE = re.compile(r"\bnamanya\b|\bnama\s+(?:\w+\s+){0,3}?apa\b|\bapa\s+nama\b|\b(?:disebut|dinamakan|dinamai)"
                           r"\s+apa\b|\bistilahnya\b|\bsebutannya\b", re.I)


def _name_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """What a described act or thing is called, when the message never names it: its name and its card's first
    sentence, by code. "yang mandiin jenazah itu namanya apa?" got the name and then all six steps of Nyiramang Layon,
    which nobody asked (human test 2026-11-03). Not a question naming the term (it asks something else of it), nor one
    asking for another name ("nama lainnya apa", "disebut apa lagi")."""
    if (len(enriched) != 1 or not _NAME_OF_Q_RE.search(user_msg) or _whether_question(user_msg)
            or re.search(r"\blain(?:nya)?\b|\blagi\b|\bjuga\b|\bkenapa\b|\bmengapa\b", user_msg, re.I)):
        return None
    e = enriched[0]
    names = [n for n in [e["name"]] + list(e.get("aliases") or []) if len(n) >= 3]
    if any(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", user_msg, re.I) for n in names):
        return None
    lead = _first_sentence(_deterministic_answer([dict(e, aspect_facts=[])]) or e.get("definition"), limit=500)
    if not lead:
        return None
    written = re.search(rf"(?<![\w-]){re.escape(e['name'])}(?![\w-])", lead, re.I)
    name = written.group(0) if written else e["name"][:1].upper() + e["name"][1:]
    return f"Namanya {name}. {lead}"


def _class_list_miss(class_list: tuple, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """A class list whose filter left nothing ("banten apa yang dipakai saat lidi", "upakara apa saja yang
    digunakan dalam wayang"): no kind of the class tied to the term, no edge or sarana of the term that is
    one, and no definition of the term naming one. The miss _name_missing makes of Qwen's reply, without
    the call (22 of plan #16's test went to Qwen for it, 2026-10-26)."""
    cls_name, term_names = class_list
    cls, terms = enriched[0], [e for e in enriched[1:] if e["name"] in term_names]
    if (not terms or len(enriched) != 1 + len(terms) or cls.get("relationships")
            or any(t.get("relationships") or t.get("sarana_facts") for t in terms)):
        return None
    content = get_content()
    # a kind as the term's definition may name it, with or without the class word ("sasih Kapat", "Kapat")
    prefix = re.compile(rf"^{re.escape(cls['name'].lower())}\s+")
    kinds = {n for k in content.kinds_of(cls["id"])
             for n in (content.entity_name.get(k, "").lower(), prefix.sub("", content.entity_name.get(k, "").lower()))}
    kind_res = [re.compile(rf"\b{re.escape(k)}\b", re.I) for k in kinds if len(k) >= 4]
    term_res = [re.compile(rf"\b{re.escape(n)}\b", re.I) for t in terms for n in [t["name"]] + (t.get("aliases") or [])
                if len(n) >= 4]
    if (any(p.search(_definition_text(t)) for t in terms for p in kind_res)
            or any(p.search(_definition_text(cls)) for p in term_res)):
        return None
    answer = f"Maaf, {cls_name} untuk {_join_names(term_names)} belum tercatat di basis data."
    for t in terms:
        known = _known_sentence(t.get("definition"))
        if known:
            answer += f" Yang tercatat tentang {t['name']}: {known}"
    return answer


# a place, time or doer is said most exactly by an edge ("Undagi membuat bade"); a meaning or purpose by
# the definition's own sentences
_EDGES_FIRST_FAMILIES = frozenset({"lokasi", "waktu", "pelaku"})
# predicates of a family that do not answer its question on their own: "kapan ngaben dilakukan" got
# "Ngaben mensyaratkan sawa." (a condition, not a time; Tier B 2026-10-13)
_NOT_ANSWERING = {"waktu": {"SYARAT", "MENSYARATKAN", "DIHITUNG_BERDASARKAN"},
                  # "apa makna ngaben" listed "Ngaben dilakukan berdasarkan tingkatan upacara" (2026-10-13)
                  "simbol": {"BERDASARKAN", "BERKAITAN_DENGAN"}}
# incoming order edges say when the asked term comes: "nanginin dilakukan sebelum nyiramang layon" answers
# "kapan nyiramang layon dilaksanakan"
_ORDER_PREDICATES = frozenset({"SEBELUM", "SETELAH", "DILAKUKAN_SEBELUM", "DILAKUKAN_SETELAH", "DILAKSANAKAN_SETELAH",
                               "DILAKUKAN_MENJELANG", "DIIKUTI_OLEH"})
# incoming edges that also say who does it ("sulinggih melaksanakan ...")
_AGENT_SUBJECT_PREDICATES = frozenset({"MELAKSANAKAN", "MEMBUAT"})
_STAGE_TYPES = frozenset({"RITUAL", "RITUAL_KEMATIAN", "TAHAPAN_UPACARA"})


# words naming the asked aspect itself that the common-word list lacks: "etimologi pedangal", "asal-usul nama
# kemampuan sosial ekonomi" went to the LLM as an unknown word, which gave the definition (NLU sweep 2026-10-19)
_ASPECT_VOCAB = frozenset({"etimologi", "etimologinya", "asal-usul", "asal-usulnya", "harafiah",
                           # everyday "dipakai" and the Balinese "muput" (to lead a rite to its end, "dipuput oleh
                           # pandita", L271): "mantra dipake buat apa" and 14 "siapa yang memuput X" / "X dipuput oleh
                           # siapa" went to the LLM as an unknown word (route audit 2026-10-27)
                           "dipake", "pake", "make", "memuput", "dipuput", "muput", "pemuput", "puput"})


_WHICH_RITE_Q_RE = re.compile(r"\b(?:digunakan|dipakai|dihaturkan|dipersembahkan|termasuk|bagian)\s+"
                              r"(?:(?:dalam|pada|di|dari)\s+)?(?:upacara|ritual|rangkaian|prosesi)\s+apa\b", re.I)
# "apa saja X" with no aspect word asks for X's kinds or members (the kinds template, or the definition holding the
# list) -- not "apa saja yang digunakan dalam sesajen", a sarana question the aspect words do not catch
_KINDS_LIST_Q_RE = re.compile(r"\bapa\s+saja\b(?!\s+yang\s+(?:di|ber|ter|me)\w+)", re.I)


def _inferred_template_intent(user_msg: Text) -> Optional[str]:
    """The simple intent a message's own words name -- for a turn NLU read as tanya_kompleks or nlu_fallback: one
    aspect family (the stages with their how), a word-meaning question, or a what-is shape with no aspect. None
    otherwise. Each retrain misreads a different ~2 of 83 probes, and a simple question read as complex went to Qwen
    ("Pedangal disebut juga apa", "apa tahapan setelah atma wedana" on the 2026-10-27 retrain)."""
    if _WORD_MEANING_RE.search(user_msg):
        return "tanya_asal_kata"
    families = set(_aspect_families(user_msg))
    if families == {"tahapan", "cara"}:
        families = {"tahapan"}
    if len(families) == 1:
        family = families.pop()
        return next((i for i, f in _TEMPLATE_INTENTS.items() if f == family and f not in ("", "asal_kata", "induk")),
                    None)
    if not families and _WHAT_IS_SHAPE_RE.search(user_msg):
        return "tanya_definisi"
    # a bare term is a definition question, as nlu.yml's bare names are: the balinese-b3a-2026-10-29 retrain read
    # "patulangan" as tanya_kompleks, and it went to Qwen
    if not families:
        mentioned, leftover = _mentioned_terms(user_msg, get_resolver())
        if len(mentioned) == 1 and not leftover:
            return "tanya_definisi"
    # "apa saja pura kahyangan tiga", read as tanya_kompleks by the plan #19 batch 2 model, went to Qwen
    if not families and _KINDS_LIST_Q_RE.search(user_msg):
        return "tanya_jenis"
    # "setelah nyiramang layon apa?": which comes next (the waktu template's order facts)
    if not families and _NEXT_STAGE_RE.search(user_msg) and re.search(r"\bapa\b", user_msg, re.I):
        return "tanya_waktu"
    return None


def _template_route(user_msg: Text, intent: Optional[Text], current_entity: Optional[Text],
                    resolver) -> "tuple[Optional[str], str]":
    """(family, "") when the message is a simple question its intent's template answers, else
    (None, why not). Checked on the message alone, before the graph is asked."""
    if intent not in _TEMPLATE_INTENTS:
        return None, f"intent {intent}"
    family = _TEMPLATE_INTENTS[intent]
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    if len(mentioned) > 1:
        return None, "two or more terms"
    # the shapes are read without the term's own names: "pura kahyangan tiga" holds a number. Not
    # without the surface the scan matched, which can take the asked tier along ("bade tingkat 9")
    rest = user_msg
    for m, _ in mentioned:
        for n in sorted([m.name] + list(m.entity.get("aliases") or []), key=len, reverse=True):
            rest = re.sub(rf"(?<![\w-]){re.escape(n)}(?![\w-])", " ", rest, flags=re.I)
    # "apakah sekah", "apakah itu lembu": the old what-is form, not a yes/no question (it went to the LLM, then with
    # a reasoning note of ~600 tokens, for the definition; LLM comparison 2026-10-20)
    if _whether_question(rest) and not (mentioned and re.fullmatch(r"\W*apakah(?:\s+itu)?\W*(?:itu\W*)?", rest, re.I)):
        return None, "yes/no"
    for why, pattern in _TEMPLATE_BLOCKERS:
        if pattern.search(rest):
            return None, why
    if _asks_about_day(user_msg):
        return None, "day"
    if any(not _is_everyday_word(w, resolver) and w not in _ASPECT_VOCAB for w in leftover):
        return None, "unknown word"
    if not mentioned and not (current_entity and (
            _ANAPHOR_RE.search(resolver.clean_query(user_msg)) or not leftover or set(leftover) <= _ELLIPSIS_VERBS)):
        return None, "no term"
    # "kapan dilakukan?" about Ngaben: its days (_good_days_answer), as for "kapan ngaben dilakukan"
    if not mentioned and _TOPIC_WHEN_RE.search(user_msg):
        topic = resolver.resolve(current_entity)
        if topic and topic.id in _DAY_TOPICS:
            return None, "day"
    # a bare "siapa X" asks who X is, not who does X ("siapa yang memimpin ngaben" keeps its other
    # words): "siapa sang hyang yama" got "pelaku sang hyang yama belum tercatat" (2026-10-14). The
    # scan's surface goes too here, so a force_merge name ("siapa dewa yama") counts as X
    bare = rest
    for _, surface in mentioned:
        bare = re.sub(rf"(?<![\w-]){re.escape(surface)}(?![\w-])", " ", bare, flags=re.I)
    if mentioned and family != "asal_kata" and re.fullmatch(r"\W*siapa(?:kah)?\W*", bare, re.I):
        return "", ""
    families = _aspect_families(rest)
    word_meaning = bool(_WORD_MEANING_RE.search(user_msg))
    # "siapa saja <noun>" asks for members, not a doer (see the pelaku family): the pipeline lists them
    if family == "pelaku" and not families and re.search(r"\bsiapa\s+saja\s+(?!yang\b)\w", rest, re.I):
        return None, "list"
    # "X digunakan dalam upacara apa (saja)" asks which rite X belongs to, whatever aspect the intent guessed: read
    # as tanya_sarana it got "Maaf, sarana banten panjang ilang belum tercatat" (canon sweep 2026-10-28)
    if not families and family != "induk" and _WHICH_RITE_Q_RE.search(rest):
        return "induk", ""
    # "apa saja X" naming no aspect is a list question whatever aspect the intent guessed: a retrain read "apa saja pura
    # kahyangan tiga" and "apa saja sasih yang berbadankan kosong" as sarana questions and both got "sarana ... belum
    # tercatat" (2026-10-28). The kinds template lists X's kinds, or gives the definition holding the list
    # (read as tanya_kompleks, the same question goes here through _inferred_template_intent)
    if family in ("sarana", "lokasi", "waktu", "fungsi", "simbol") and not families and _KINDS_LIST_Q_RE.search(rest):
        return "jenis", ""
    # a what-is shape with no aspect word is the definition whatever the intent says -- also over a
    # tanya_asal_kata misread: "apa itu dewata nawa sanga" went to the LLM (live, 2026-10-15)
    if not families and not word_meaning and _WHAT_IS_SHAPE_RE.search(rest):
        return "", ""
    if word_meaning != (family == "asal_kata"):
        return None, "aspect"
    if family == "asal_kata":
        return family, ""
    # where a thing is obtained from is no place it lies in: "dari mana babelonyoh diperoleh" got "Babelonyoh
    # dioleskan di dada jenazah", "dari mana tabunan diperoleh" "Tabunan diletakkan di celebongkekan" (sheet Failed)
    if _ORIGIN_Q_RE.search(rest):
        return None, "origin"
    # "apa tahapan setelah ngulapin" asks which comes next: the order the waktu template gives (it went to the LLM)
    if family == "waktu" and families == ["tahapan"] and _NEXT_STAGE_RE.search(rest):
        families = ["waktu"]
    # "apa itu X dan maknanya", "apa itu X, dari mana diperoleh, ...": a definition AND an aspect. Not
    # "apa itu tujuan ngaben", which asks one thing (Tier B 2026-10-13)
    if families and _WHAT_IS_RE.search(user_msg) and re.search(r"\s(?:dan|serta|lalu)\s|,", rest):
        return None, "multi-part"
    if (families and family == "") or not set(families) <= _TEMPLATE_FAMILIES_OK.get(family, {family}):
        # the words ask one other simple aspect: its template, as for a turn read as tanya_kompleks
        # (_inferred_template_intent) -- "apa tugas pemangku dalam ngaben", read as tanya_pelaku by a retrain, got
        # "fungsi ... belum tercatat" from the pipeline above "bertugas memimpin persembahyangan" (plan #19 batch 2)
        other = _TEMPLATE_INTENTS.get(_inferred_template_intent(rest) or "")
        if other and set(families) <= _TEMPLATE_FAMILIES_OK.get(other, {other}):
            return other, ""
        return None, "aspect"
    return family, ""


def _definition_text(e: Dict[str, Any]) -> str:
    d = e.get("definition") or ""
    return "" if d == "Tidak ada definisi langsung" else d


def _join_names(names: List[str]) -> str:
    """"a", "a dan b", "a, b, dan c"."""
    names = list(dict.fromkeys(names))
    if len(names) <= 2:
        return " dan ".join(names)
    return ", ".join(names[:-1]) + ", dan " + names[-1]


# where a long gloss may end: a clause boundary, or a comma before a new clause (not "yaitu": what
# follows it is often the point -- akasa "..., yaitu unsur eter")
_CLAUSE_END_RE = re.compile(r";\s|:\s|\s--\s|,\s(?=(?:sehingga|namun|tetapi|lalu|kemudian|karena|agar|biasanya|"
                            r"bersama|misalnya|seperti|termasuk|dilaksanakan|dilakukan)\b)")


def _decap(text: Text) -> str:
    """Lowercase the first letter after "Pabersihan mati:" when the gloss opens with a common noun
    ("Tahap kedua ...", "Lempengan emas tipis ..."): an everyday word, or a word that is no KB name
    followed by a lowercase one. A name keeps its case ("Ngaben yang ...", "Bhuta Kala ...")."""
    words = re.findall(r"[^\W\d_]+", text)
    first = words[0] if words else ""
    if not (first[:1].isupper() and first[1:2].islower()):
        return text
    resolver = get_resolver()
    if (_is_everyday_word(first.lower(), resolver)
            or (len(words) > 1 and words[1][:1].islower() and first.lower() not in get_content().id_by_name)):
        return text[:1].lower() + text[1:]
    return text


def _gloss(entity_id: Optional[str], limit: int = 220) -> str:
    """The first sentence of an entity's definition for a list item, without its own name in front:
    "Ngaben massal adalah upacara ..." and "Nyiramang Layon (disebut juga Nyiramin) adalah upacara
    ..." -> "upacara ..." ("2. Nyiramang layon: Nyiramang Layon (...) adalah ..." said the name
    twice). A long one ends at a clause boundary rather than mid-clause with "...", where it can."""
    content = get_content()
    s = _first_sentence(content.best_definition(entity_id) if entity_id else None, limit=10 ** 6).rstrip(".")
    name = content.entity_name.get(entity_id or "", "")
    # "Pralina berarti ..." too: "Pralina: berarti kembalinya ...", not "Pralina: Pralina berarti ..."
    m = _definition_subject(s, entity_id, name) if name else None
    if m:
        s = s[m.end():]
    s = _decap(s)
    if len(s) > limit:
        ends = [x.start() for x in _CLAUSE_END_RE.finditer(s, 0, limit) if x.start() >= 40]
        s = s[:ends[-1]].rstrip(" ,;:") if ends else s[:limit].rsplit(" ", 1)[0] + " ..."
    return s if not s or s.endswith(("...", ".", "!", "?")) else s + "."


def _meaning_gloss(entity_id: Optional[str]) -> str:
    """_gloss for 'Kata "x" berarti <gloss>': without a leading "berarti" of its own ("Mala berarti kotor ..." gave
    'Kata "mala" berarti berarti kotor', plan #19 batch 2)."""
    return re.sub(r"^berarti\s+", "", _gloss(entity_id), flags=re.I)


def _list_item(entity_id: Text) -> str:
    """"Asti wedana: jenis Ngaben berupa ..." -- a kind, stage or member in a list, with its gloss."""
    name = get_content().entity_name.get(entity_id, entity_id)
    g = _gloss(entity_id)
    return f"{name[:1].upper()}{name[1:]}" + (f": {g}" if g else "")


_TERM_STOPWORDS: Optional[frozenset] = None


def _fact_roots(text: Text) -> set:
    """_sentence_roots, keeping a stopword that is a KB term's name: "ngaben" is a stopword, so "Wadah digunakan
    dalam ngaben" had only "wadah" left and went as a repeat of "Wadah termasuk salah satu jenis usungan" -- seven
    "X digunakan dalam upacara apa" answers lost Ngaben (canon sweep 2026-10-28). Spelled by _ortho_key: an edge
    names "tirta pangentas", a definition "Tirtha Pangentas", and "Pripih emas dimasukkan ke dalam tirta pangentas"
    stood above the definition saying it (2026-10-29)."""
    global _TERM_STOPWORDS
    if _TERM_STOPWORDS is None:
        _TERM_STOPWORDS = frozenset(w for w in _STOPWORDS_ID if w in get_content().id_by_name)
    roots = _sentence_roots(text) | {_root(w) for w in _WORD_RE.findall(text.lower()) if w in _TERM_STOPWORDS}
    return {_ortho_key(r) for r in roots}


def _distinct_sentences(sentences: List[str], subject: Optional[Dict[str, Any]] = None) -> List[str]:
    """Each fact once, as a capitalized sentence: one whose words an earlier one mostly holds goes
    (a definition sentence and the edge it was extracted from say the same thing). `subject`: the term
    the sentences are about -- its name (or an alias) opening a sentence is not compared, or two facts
    shared nothing but it: "Tirtha kawitan termasuk salah satu jenis tirtha" went under "Tirtha kawitan
    digunakan dalam ngaben" (canon sweep 2026-10-28)."""
    names = sorted({(subject.get("name") or "")} | set(subject.get("aliases") or []), key=len, reverse=True) \
        if subject else []
    names = [n for n in names if n]
    out, seen = [], []
    for s in sentences:
        s = re.sub(r"\s+", " ", s or "").strip().rstrip(".")
        body = s
        for n in names:
            stripped = re.sub(rf"^\W*{re.escape(n)}(?![\w-])", "", body, flags=re.I)
            if stripped != body:
                body = stripped
                break
        roots = _fact_roots(body)
        if not s or any(roots and len(roots & r) >= 0.8 * len(roots) for r in seen):
            continue
        seen.append(roots)
        out.append(f"{s[:1].upper()}{s[1:]}.")
    # and one a LATER, longer sentence holds: "Tirta pangentas hanya dapat dibuat oleh sulinggih." above
    # "... hanya dapat dibuat oleh sulinggih yang sudah melaksanakan upacara Mapulang Lingga." (2026-10-13)
    return [s for i, (s, r) in enumerate(zip(out, seen))
            if not any(r and j > i and len(r2) > len(r) and len(r & r2) >= 0.8 * len(r)
                       for j, r2 in enumerate(seen))]


# an incoming edge said with the asked term as its subject: "siapa yang membuat bade" is answered
# "Bade dibuat oleh undagi", not "Undagi membuat bade"; "kapan nyiramang layon" gets "Nyiramang layon
# dilakukan setelah ngulapin", not "Ngulapin diikuti oleh nyiramang layon" (user 2026-10-15: natural)
_TERM_FIRST_INCOMING = {
    "MEMBUAT": "dibuat oleh", "MELAKSANAKAN": "dilaksanakan oleh",
    "DIIKUTI_OLEH": "dilakukan setelah", "SEBELUM": "dilakukan setelah", "DILAKUKAN_SEBELUM": "dilakukan setelah",
    "SETELAH": "dilakukan sebelum", "DILAKUKAN_SETELAH": "dilakukan sebelum",
    "DILAKSANAKAN_SETELAH": "dilakukan sebelum", "DILAKUKAN_MENJELANG": "didahului oleh",
}


def _edge_sentences(e: Dict[str, Any], preds: set, incoming: frozenset = frozenset(),
                    outgoing: bool = True, with_targets: bool = False,
                    literals: Optional[Dict[str, List[str]]] = None) -> list:
    """e's outgoing edges with a predicate in `preds` (and incoming ones whose predicate is in
    `incoming`; `outgoing=False`: those only) as sentences, one per predicate and direction naming
    every target: "kawangen digunakan dalam nyiramang layon, pangringkes, dan ...". An incoming
    edge with a term-first reading (_TERM_FIRST_INCOMING) is said that way, its phrase's targets
    together. A regional variant keeps its own. `literals`: e's text-only values of an outgoing
    predicate, named first in that predicate's sentence -- apart they read "Kawangen diletakkan di kedua
    lutut kaki, serta diletakkan di hulu hati jenazah, ..." (2026-10-29). `with_targets`: (sentence,
    target names) pairs."""
    content = get_content()
    groups: Dict[tuple, List[str]] = {}
    variants = []
    for r in e.get("relationships") or []:
        pred = r.get("relation")
        if (pred not in preds or not r.get("target")
                or not (r.get("outgoing") and outgoing or not r.get("outgoing") and pred in incoming)):
            continue
        if r.get("variant_op"):
            variants.append((r.get("statement") or "", [r["target"]]))
        elif not r.get("outgoing") and pred in _TERM_FIRST_INCOMING:
            groups.setdefault(("", _TERM_FIRST_INCOMING[pred]), []).append(r["target"])
        else:
            first = list((literals or {}).get(pred, [])) if r.get("outgoing") else []
            groups.setdefault((pred, bool(r.get("outgoing"))), first).append(r["target"])
    out = []
    for (pred, how), targets in groups.items():
        targets = list(dict.fromkeys(targets))
        if not pred:
            out.append((f"{e['name']} {how} {_join_names(targets)}", targets))
        else:
            out.append((content.render(pred, e["name"], _join_names(targets)) if how
                        else content.render(pred, _join_names(targets), e["name"]), targets))
    out += variants
    return out if with_targets else [s for s, _ in out]


# A time word dates the term only in a clause about doing something -- a passive verb in it: "dioleskan ... saat
# memandikan jenazah", "disertai mantranya ..., misalnya saat membangunkan jenazah untuk dimandikan",
# "dilaksanakan setelah Pabersihan Hidup". Not "sekte ... yang mengajarkan bahwa setelah mencapai tingkat
# kebebasan tertentu" (Paksa Mahayana's definition answered "dilakukan setelah apa"), nor "dengan harapan ...
# putih saat menjelma kembali" (umbi sikapa; NLU sweep 2026-10-19). Narrowed by the verb after the time word
# instead, it also lost mantra's and babelonyoh's good answers.
_CLAUSE_EDGE_RE = re.compile(r"[,;:]|\s--\s")
_PASSIVE_RE = re.compile(r"\bdi(?!ri\b|a\b|mana\b|ni\b|nas\b)[a-z]{3,}\b|\b(?:jatuh|berlangsung|bertepatan)\b", re.I)


def _dates_the_term(sentence: Text, marker_rx) -> bool:
    for m in marker_rx.finditer(sentence):
        # the term's own "adalah" phrase dates it, with no relative clause or verb before the time word: "Ngliwet
        # (ngeliwet) adalah acara singkat dalam Atma Wedana, sesudah amariaran dan pralina" -- without it "kapan
        # ngliwet dilakukan" got only "Ngliwet dilakukan setelah pralina" (Tier B, plan #16, 2026-10-26)
        head = re.match(r"[^.;:]*?\badalah\b([^.;:]*)$", sentence[:m.start()], re.I)
        if head and not re.search(r"\byang\b|\b(?:me|ber|di)[a-z]{3,}\b", head.group(1), re.I):
            return True
        start = ([e.end() for e in _CLAUSE_EDGE_RE.finditer(sentence, 0, m.start())] or [0])[-1]
        after = _CLAUSE_EDGE_RE.search(sentence, m.end())
        end = after.start() if after else len(sentence)
        # a fronted time phrase has its verb in the next clause: "setelah upacara Ngajar-ajar, Sang Dewa Hyang
        # dilinggihkan" -- a phrase, not a clause with its own verb: "Saat bertugas ia berpijak pada padi satu
        # cekal, dan untuknya disediakan gelang" dated sangging (sheet Failed, route audit 2026-10-27)
        if after and not sentence[start:m.start()].strip() and len(sentence[m.start():after.start()].split()) <= 5:
            nxt = _CLAUSE_EDGE_RE.search(sentence, after.end())
            end = nxt.start() if nxt else len(sentence)
        if _PASSIVE_RE.search(sentence[start:end]):
            return True
    return False


def _aspect_sentences(e: Dict[str, Any], family: str, with_definition: bool = True,
                      with_edges: bool = True) -> List[str]:
    """What the KB states about e's aspect: its definition's sentences that state it, the text-only
    facts of the family, then its edges (`with_edges`)."""
    content = get_content()
    found = []
    marker = _TEMPLATE_DEF_MARKERS.get(family) if with_definition else None
    stated = []
    if marker:
        rx = re.compile(rf"\b(?:{marker})\b", re.I)
        # the definition as the answer gives it: its first sentence has its subject ("Ngaben adalah
        # upacara ...", not "Upacara pembakaran jenazah ... bertujuan ...")
        # a month or a week is itself a time: its definition answers "kapan" as it stands
        calendar = any(e["id"] == c or content.is_kind_of(e["id"], c) for c in ("sasih", "wuku", "wewaran"))
        stated = [s for s in _sentences(_deterministic_answer([dict(e, aspect_facts=[])]))
                  if rx.search(_VAGUE_ASPECT_RE.sub("", s))
                  and (family != "waktu" or calendar or _dates_the_term(s, rx))
                  # what a word means is no symbol: "apa arti simbolis abu" got "Abu secara umum berarti sisa
                  # material ...", "atma wedana simbol dari apa" "Nama Ngroras berasal dari kata roras ...", "lambang
                  # gegaleng" "Gegaleng berarti bantal" (sheet Failed, route audit 2026-10-27)
                  and (family != "simbol" or _symbol_beyond_word_meaning(s, e["name"], rx))]
    if family == "pelaku":
        # who does or makes it is a person, not a rite ("Sekah ... dibuat oleh ngajum"; "atma wedana dilakukan
        # oleh siapa" got "ngajum membuat sekah" from a stage), and what the term itself makes is no doer of it
        e = dict(e, relationships=[
            r for r in e.get("relationships") or []
            if r.get("relation") not in _AGENT_SUBJECT_PREDICATES
            or (not r.get("outgoing") and content.entity_type.get(r.get("target_id")) not in _STAGE_TYPES)])
    if family not in _EDGES_FIRST_FAMILIES:
        found += stated
    preds = PREDICATE_FAMILIES[family] - _NOT_ANSWERING.get(family, set())
    # a word's literal meaning is no symbol unless it also states one, as for the definition's sentences above:
    # "apa yang dilambangkan oleh pitra" got "Pitra ... secara harfiah berarti orangtua"; ngulapin's "...
    # -- maknanya memanggil kembali roh mendiang" stays
    symbol_rx = re.compile(rf"\b(?:{_TEMPLATE_DEF_MARKERS['simbol']})\b", re.I) if family == "simbol" else None

    def says_symbol(sentence: Text) -> bool:
        return _symbol_beyond_word_meaning(sentence, e["name"], symbol_rx)

    if symbol_rx:
        e = dict(e, relationships=[r for r in e.get("relationships") or []
                                   if not (r.get("relation") == "BERARTI_HARFIAH" and r.get("outgoing")
                                           and not says_symbol(r.get("statement") or ""))])
    edge_preds = {r.get("relation") for r in e.get("relationships") or []
                  if r.get("outgoing") and r.get("target") and not r.get("variant_op")} & preds if with_edges else set()
    literals: Dict[str, List[str]] = {}
    for pred, values in content.attributes.get(e["id"], {}).items():
        if symbol_rx and pred == "BERARTI_HARFIAH":
            values = [v for v in values if says_symbol(content.render(pred, e["name"], v))]
        if pred not in preds or not values:
            continue
        # short values of one predicate in one sentence: "Nyekeh dilakukan oleh keluarga pendeta dan
        # keluarga raja", not two sentences each naming one of them -- with its edges' targets too
        if pred in edge_preds and all(len(v.split()) <= 5 for v in values):
            literals[pred] = values
        elif len(values) > 1 and all(len(v.split()) <= 5 for v in values):
            found.append(content.render(pred, e["name"], _join_names(values)))
        else:
            found += [content.render(pred, e["name"], v) for v in values]
    incoming = (_AGENT_SUBJECT_PREDICATES if family == "pelaku" else _ORDER_PREDICATES if family == "waktu"
                else frozenset())
    edges = _edge_sentences(e, preds, incoming, with_targets=True, literals=literals) if with_edges else []
    # an edge one definition sentence of the answer says in full goes: "Ngliwet dilakukan setelah pralina." above
    # "... sesudah amariaran dan pralina: ..." (2026-10-15); its targets named by any surface: "Tikeh plasa juga
    # digunakan dalam nyiramang layon dan pangringkes" below "... tempat Nyiramang Layon dan ... saat ngeringkes"
    named = [_named_in(d) for d in stated] if edges else []
    edges = [s for s, targets in edges if not any(all(t.lower() in n for t in targets) for n in named)]
    if family in _EDGES_FIRST_FAMILIES:
        found += edges + stated
    else:
        found += edges
    return _distinct_sentences(found, e)


_SURFACE_RE: Optional["re.Pattern"] = None
_SURFACE_ID: Dict[str, str] = {}


def _named_in(sentence: Text) -> set:
    """The KB names (lowercase) a sentence names as written or by another of their surfaces -- an alias or a
    force_merge key: "ngeringkes" is pangringkes. Exact surfaces only: the term finder's fuzzy scan took 1.4 s a
    definition sentence (2026-10-29)."""
    global _SURFACE_RE
    content, low = get_content(), sentence.lower()
    if _SURFACE_RE is None:
        resolver = get_resolver()
        _SURFACE_ID.update((s.lower(), eid) for s, eid in resolver.surface.items())
        # the resolver keeps force_merge targets as ids ("sudra" -> wangsa_sudra_jadma); a name only for a one-word id
        for s, target in resolver.force_merge.items():
            eid = target if target in resolver.by_id else content.id_by_name.get((target or "").lower())
            if eid:
                _SURFACE_ID.setdefault(s.lower(), eid)
        alternatives = sorted(_SURFACE_ID, key=len, reverse=True)
        _SURFACE_RE = re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, alternatives)) + r")(?![\w-])", re.I)
    names = {content.entity_name.get(_SURFACE_ID.get(m.group(0).lower(), ""), "").lower()
             for m in _SURFACE_RE.finditer(sentence)} - {""}
    # every name as written too, also one inside a longer surface: "pralina" in "agni pralina"
    return names | {n for n in content.id_by_name
                    if n in low and re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", sentence, re.I)}


def _stage_ids(e: Dict[str, Any]) -> List[str]:
    """The ceremonies / stages that are BAGIAN_DARI e, from its graph edges, in their stated order."""
    content = get_content()
    ids = list(dict.fromkeys(r["target_id"] for r in e.get("relationships") or []
                             if r.get("relation") == "BAGIAN_DARI" and not r.get("outgoing")
                             and content.entity_type.get(r.get("target_id")) in _STAGE_TYPES))
    return sorted(ids, key=lambda s: _stage_number(content.best_definition(s), e.get("id")) or 99)


def _kb_relationships(entity_id: str) -> List[Dict[str, Any]]:
    """An entity's edges as _extract_and_resolve gives them, read from the KB files (facts.jsonl holds
    the same non-LOW edges the graph does) -- for a term the question did not name, such as a stage."""
    content = get_content()
    name = content.entity_name.get(entity_id, entity_id)
    out = []
    for f, outgoing in ([(f, True) for f in content.facts_by_subj.get(entity_id, [])]
                        + [(f, False) for f in content.facts_by_obj.get(entity_id, [])]):
        other = f["object_id"] if outgoing else f["subject_id"]
        target = content.entity_name.get(other)
        if not target:
            continue
        subj, obj = (name, target) if outgoing else (target, name)
        out.append({"relation": f["predicate"], "outgoing": outgoing, "target": target, "target_id": other,
                    "variant_op": (f.get("variant") or {}).get("op"),
                    "statement": content.render_variant(f["predicate"], subj, obj, f.get("variant"))})
    return out


# a predicate's verb and the function word after it ("dilakukan setelah", "dipimpin oleh"): what two
# short facts must share to be said once ("dilakukan setelah ngulapin, nanginin, dan wawu lampus")
_LINK_WORDS = frozenset("oleh di ke dari untuk sebagai dengan pada dalam kepada setelah sebelum sesudah menjelang "
                        "saat bersama".split())


def _as_paragraph(sentences: List[str], name: Text) -> str:
    """Facts about one term as prose, not a list of sentences each opening with its name (user
    2026-10-15: "Kawangen melambangkan A. Kawangen melambangkan B. Kawangen melambangkan C." read
    clunky). The short ones with the term as subject become one sentence at the first one's place:
    a shared verb said once ("Kawangen melambangkan A, B, dan C"), the other predicates joined
    ("Damar kurung ditujukan untuk hyang agni dan membatasi cuntaka"), with "juga" when an earlier
    sentence already had the term as subject. Definitions ("X adalah ...") and long or
    multi-clause sentences stay as they are."""
    subject = re.compile(rf"{re.escape(name)}\s+(.+?)\.?$", re.I | re.S)
    preds: Dict[str, List[str]] = {}
    out: List[Optional[str]] = []
    slot = None
    for s in sentences:
        m = subject.fullmatch(s.strip())
        pred = m.group(1) if m else ""
        words = pred.split()
        if (not m or re.search(r"[;:]|\.\s", pred) or len(words) > 12
                or words[0].lower() in {"adalah", "ialah", "yaitu", "juga"}):
            out.append(s)
            continue
        key = " ".join(words[:2]).lower() if len(words) > 2 and words[1].lower() in _LINK_WORDS else words[0].lower()
        preds.setdefault(key, []).append(pred)
        if slot is None:
            slot = len(out)
            out.append(None)
    if slot is None:
        return " ".join(sentences)
    clauses = []
    for key, group in preds.items():
        objects = [p[len(key):].strip() for p in group]
        if len(group) > 1 and all(o and "," not in o and not re.search(r"\s(?:dan|serta|atau)\s", o)
                                  for o in objects):
            clauses.append(f"{group[0][:len(key)]} {_join_names(objects)}")
        else:
            clauses += group
    title = f"{name[:1].upper()}{name[1:]}"
    also = " juga" if any(subject.fullmatch(s.strip()) or re.match(rf"{re.escape(name)}\b", s, re.I)
                          for s in out[:slot] if s) else ""
    out[slot] = f"{title}{also} {_join_clauses(clauses)}."
    return " ".join(s for s in out if s)


# A definition sentence that says what a word means: "Lembu secara harfiah berarti sapi", 'Kata mala berarti
# "tidak baik"', '"Jun" secara umum berarti periuk', 'bermakna "menebus" kesalahan', "Gegaleng berarti bantal".
# Not "Ganda berasal dari pretiwi" (where the element comes from, not the word).
_WORD_MEANING_IN_DEF_RE = re.compile(
    r"secara harfiah"
    r"|\b(?:kata|istilah|nama)\s+[\"“]?[\w-]+(?:\s+[\w-]+)?[\"”]?\s+(?:secara\s+\w+\s+)?(?:berarti|bermakna|berasal\s+dari)\b"
    r"|[\"“][\w-]+(?:\s+[\w-]+)?[\"”]\s+(?:secara\s+\w+\s+)?(?:berarti|bermakna)\b"
    r"|\b(?:berarti|bermakna)\s+[\"“]"
    r"|\bberasal\s+dari\s+(?:kata|bahasa)\b", re.I)


def _symbol_beyond_word_meaning(sentence: Text, name: Text, marker_rx) -> bool:
    """A symbol marker outside the sentence's word-meaning clauses: daksina tapakan's "... sebagai penegasan formal
    bahwa suatu yadnya telah selesai ...; "tapakan" berarti alas" keeps its first clause; "Gegaleng berarti bantal;
    ... ganjalan kepala jenazah" has none."""
    # a gloss of a word, not 'bermakna "menebus" kesalahan ...', which says what the rite means (penebusan)
    gloss = re.compile(rf"secara\s+(?:harfiah|umum|etimologis)\s+berarti"
                       r"|\b(?:kata|istilah|nama)\s+[\"“]?[\w-]+[\"”]?(?:\s+[\w-]+)?\s+(?:secara\s+\w+\s+)?"
                       r"(?:berarti|bermakna|berasal\s+dari)\b"
                       r"|[\"“][\w-]+(?:\s+[\w-]+)?[\"”]\s+(?:secara\s+\w+\s+)?berarti\b|\bberasal\s+dari\s+kata\b"
                       rf"|^\s*{re.escape(name)}\s+(?:\([^)]*\)\s+)?berarti\b", re.I)
    if not gloss.search(sentence):
        return True
    # a dash ends the gloss too: 'Ngulapin secara harfiah berarti "melambaikan tangan" ... -- maknanya memanggil ...'
    rest = " ".join(c for c in re.split(r"(?<=[;:])\s+|\s+--\s+", sentence) if not gloss.search(c))
    return bool(marker_rx.search(_VAGUE_ASPECT_RE.sub("", rest)))


def _names_word_of(sentence: Text, name: Text) -> bool:
    """The sentence says what a word inside a longer name means: 'Kata "mala" berarti ...' in malamasa's definition."""
    for m in re.finditer(r"(?:\bkata\s+)?[\"“]?([\w-]+)[\"”]?\s+(?:secara\s+\w+\s+)?(?:berarti|bermakna)\b", sentence, re.I):
        w = m.group(1).lower()
        if w != name.lower() and re.search(rf"(?<![\w-]){re.escape(w)}|{re.escape(w)}(?![\w-])", name, re.I) \
                and len(w) >= 3 and (m.group(0).lower().startswith("kata") or '"' in m.group(0) or "“" in m.group(0)):
            return True
    return False


def _word_meaning_elsewhere(name: Text) -> Optional[str]:
    """'Kata "pitra" secara harfiah berarti orang tua (ayah dan ibu) atau dalam arti luas leluhur.' -- a word's
    meaning as another term's definition states it ('kata "pitra" secara harfiah berarti ..., dan "yadnya"
    berarti ...' in pitra yadnya's)."""
    rx = re.compile(rf"\bkata\s+[\"“]{re.escape(name)}[\"”]\s+(secara\s+\w+\s+)?(?:berarti|bermakna)\s+"
                    r"([^.;\"“”]+?)(?=\s*,\s*(?:dan\s+)?[\"“]|\s*[.;]|\s*$)", re.I)
    for definition in get_content().entity_def.values():
        m = rx.search(definition or "")
        if m:
            how = (m.group(1) or "").strip()
            return f'Kata "{name}" {how + " " if how else ""}berarti {m.group(2).strip()}.'
    return None


def _word_meaning_sentence(sentence: Text, name: Text) -> bool:
    return bool(_WORD_MEANING_IN_DEF_RE.search(sentence) or re.match(
        rf"\s*{re.escape(name)}\s+(?:\([^)]*\)\s+)?(?:secara\s+\w+\s+)?(?:berarti|bermakna)\b", sentence, re.I))


# the language a word comes from: "Layon adalah sebutan halus (bahasa Bali/Kawi) untuk jenazah" answers
# "istilah layon berasal dari mana" -- the miss had said its origin is not recorded, above that sentence
_WORD_LANGUAGE_RE = re.compile(r"\bbahasa\s+(?:Bali|Kawi|Jawa|Sanskerta|Sansekerta)\b|\bSanskerta\b|\bSansekerta\b",
                               re.I)


# The other names a definition gives: "Pabersihan (disebut juga Pasucian)", "Wesia (Waisya) adalah ...",
# "Tiying gading (bambu gading, bambu kuning) adalah ...". The sebutan-lain template read only the edges and
# aliases, so "pabersihan disebut juga apa" got "Maaf, sebutan lain untuk pabersihan belum tercatat" (six of
# them in the LLM comparison, 2026-10-20). A gloss in brackets is not a name: "Tikeh plasa (tikar daun pandan
# yang halus) dipakai ..." has no "adalah" after it, and four words or "yang" or quotes mark a description.
_ALSO_CALLED_RE = re.compile(r"\b(?:disebut juga|juga disebut|juga dikenal (?:dengan|sebagai)|dikenal juga (?:dengan|sebagai)"
                             r"|sering disebut)\s+([^.;:()]+)", re.I)


def _definition_other_names(e: Dict[str, Any]) -> List[str]:
    text = _definition_text(e) or ""
    found = []
    lead = re.match(rf"\s*{re.escape(e['name'])}\s*\(([^)]+)\)\s+(?:adalah|merupakan|ialah)\b", text, re.I)
    if lead:
        found.append(re.sub(r"^(?:disebut|dikenal)\s+(?:juga\s+)?(?:dengan\s+|sebagai\s+)?", "", lead.group(1).strip(),
                            flags=re.I))
    found += [m.group(1) for m in _ALSO_CALLED_RE.finditer(text)]
    names = []
    own = set(e["name"].lower().split())
    for chunk in found:
        for raw in re.split(r",|/|;|\s+atau\s+|\s+dan\s+", chunk):
            item = raw.strip(" .'")
            # the list ends at the first item that is no name: "disebut juga Ngelelet atau Melelet, dilaksanakan
            # setelah ..., dan meliputi kerik kuku" (pabersihan mati); a quoted gloss is a translation
            # ('Paksa Mahayana ("kendaraan besar")'); "sering disebut dengan nama ini" is no name
            if (not item or len(item.split()) > 3 or re.search(r"[\"“”]|\d", item)
                    or re.search(r"\b(?:yang|adalah|merupakan|setelah|sebelum|untuk|dengan|meliputi|pada|dalam|dari"
                                 r"|sebagai|oleh|ini|itu|tersebut|nama)\b", item, re.I)):
                break
            # a gloss holding the name itself is a surface, not another name: "Pinang (buah pinang)"
            if not own <= set(item.lower().split()):
                names.append(item)
    return names


def _template_miss(label: Text, e: Dict[str, Any], whole: bool = False) -> str:
    """The asked aspect is not recorded -- what the LLM path says too (rule 23), without the call."""
    name = e["name"]
    known = _definition_text(e) if whole else _known_sentence(e.get("definition"))
    return (f"Maaf, {label} {name} belum tercatat di basis data."
            + (f" Yang tercatat tentang {name}: {known}" if known else ""))


def _stage_aspect_sentences(e: Dict[str, Any], family: str) -> List[str]:
    """What e's stages record of an aspect (place, time, doer), from their edges and text facts only: their
    definitions' place words mean other things ("dipanggil di tempat meninggalnya")."""
    content = get_content()
    staged = []
    for sid in _stage_ids(e):
        stage = {"id": sid, "name": content.entity_name[sid], "definition": content.best_definition(sid),
                 "relationships": _kb_relationships(sid)}
        staged += _aspect_sentences(stage, family, with_definition=False)
    return _distinct_sentences(staged)


# the verbs of a place question that name no act of their own
_GENERIC_PLACE_VERBS = frozenset({"dilakukan", "dilaksanakan", "diadakan", "diselenggarakan", "dilaksanain",
                                  "dilakuin", "diadain", "dimana", "diletakkan", "ditempatkan", "ditaruh", "disimpan"})


def _asked_place_verb(user_msg: Text) -> Optional[str]:
    """The root of the passive verb a place question names ("disemayamkan" -> "semayam"), if it names an act."""
    for w in _WORD_RE.findall(user_msg.lower()):
        if re.fullmatch(r"di\w{4,}", w) and w not in _GENERIC_PLACE_VERBS:
            return _root(w)
    return None


def _purpose_clause(sentence: Text, name: Text) -> str:
    """"Ngaben adalah upacara ..., bertujuan memusnahkan ..." -> "Ngaben bertujuan memusnahkan ...": the purpose
    clause of a definition sentence with its term as subject. Other sentences as they are."""
    m = re.match(rf"\s*({re.escape(name)})\s+(?:\([^)]*\)\s+)?adalah\b[^.;:]*?,\s*((?:bertujuan|berfungsi)\b.*)$",
                 sentence, re.I | re.S)
    return f"{m.group(1)} {m.group(2)}" if m else sentence


_MAKE_ACT_RE = re.compile(r"\b(?:membuat|dibuat|pembuat|bikin|dibikin|dibuatin)\w*\b", re.I)
_LEAD_ACT_RE = re.compile(r"\b(?:memimpin|dipimpin|pemimpin|mimpin|memuput|dipuput|pemuput|muput)\w*\b", re.I)


_COUNT_WORDS = {"dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
                "sepuluh": 10, "sebelas": 11, "dua belas": 12}


def _stated_stage_total(stage_ids: List[Optional[str]]) -> Optional[int]:
    """How many stages the stages' own definitions say there are: "tahap pertama dari delapan tahapan"."""
    content = get_content()
    for sid in stage_ids:
        m = re.search(r"\bdari\s+(\d+|dua belas|\w+)\s+tahap", content.best_definition(sid) or "" if sid else "", re.I)
        if m:
            w = m.group(1).lower()
            return int(w) if w.isdigit() else _COUNT_WORDS.get(w)
    return None


def _asked_act(user_msg: Text) -> Optional[tuple]:
    """The act a who-question names, as (its doer's label, the words a fact must say): making or leading."""
    if _MAKE_ACT_RE.search(user_msg):
        return "pembuat", _MAKE_ACT_RE
    if _LEAD_ACT_RE.search(user_msg):
        return "pemimpin", _LEAD_ACT_RE
    return None


def _template_definition(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """The definition only (user, 2026-10-13)."""
    return _deterministic_answer([dict(enriched[0], aspect_facts=[])]) or None


def _template_aspect(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """Meaning, purpose, place, time, doer or how: the definition's sentences and facts of that aspect, as one
    paragraph; a ceremony with none of its own gives its stages'."""
    e = enriched[0]
    name = e["name"]
    title = f"{name[:1].upper()}{name[1:]}"
    rels = e.get("relationships") or []
    content = get_content()
    found = _aspect_sentences(e, family)
    act = _asked_act(user_msg) if family == "pelaku" else None
    if found and act:
        # the act the question names: "siapa yang membuat jenazah" got "Jenazah dibasmi oleh sang hyang birawi",
        # "siapa yang membuat sekah" "Sekah diajak berkomunikasi oleh keluarga" (sheet Failed, 2026-10-27)
        label, said = act
        found = [s for s in found if said.search(s)]
        if not found:
            rites = [r["target"] for r in rels if r.get("relation") == "MEMBUAT" and not r.get("outgoing")
                     and content.entity_type.get(r.get("target_id")) in _STAGE_TYPES]
            return _template_miss(label, e) + (
                f" {title} dibuat dalam {_join_names(rites)}." if rites and label == "pembuat" else "")
    verb = _asked_place_verb(user_msg) if family == "lokasi" else None
    if found and verb:
        # the act the place question names: "jenazah disemayamkan di mana" listed every place the corpse is
        # carried, laid and washed (the 12 evaluation categories, 2026-10-27)
        found = [s for s in found if any(_root(w) == verb for w in _WORD_RE.findall(s.lower()))] or found
    if found:
        if family == "fungsi":
            own = _sentences(_deterministic_answer([dict(e, aspect_facts=[])]))
            if own and not any(f in own for f in found):
                # with no definition sentence stating a purpose, what the thing is says what it is for:
                # "apa peran wadah" got only "Wadah digunakan dalam ngaben", not that it is the usungan
                # that carries the corpse; gegaleng, babelonyoh, bade the same (LLM comparison 2026-10-20);
                # an edge that sentence already says goes ("... ritual penyucian untuk membersihkan diri ... dari
                # ... leteh. Pabersihan hidup bertujuan membersihkan diri dari leteh.", 2026-10-28)
                found = _distinct_sentences([own[0]] + found, e)
            else:
                # a definition sentence holding the purpose after what the term is says the purpose alone:
                # "Ngaben adalah upacara pembakaran jenazah ..., bertujuan memusnahkan jasad sawa ..." opened
                # "apa tujuan ngaben" as it opens "apa itu ngaben" (the 12 evaluation categories, 2026-10-27)
                found = [_purpose_clause(s, name) for s in found]
        if family == "lokasi" and not verb:
            # a ceremony's own place and its stages' (_stage_aspect_sentences)
            staged = [s for s in _stage_aspect_sentences(e, family) if s not in found]
            if staged:
                own_text = _as_paragraph(found, name)
                return (f"Tempat tahapan {name} yang tercatat:\n" + "\n".join(f"- {s}" for s in staged)
                        + f"\nSelain itu, {own_text[:1].lower()}{own_text[1:]}")
        return _as_paragraph(found, name)
    if family in _EDGES_FIRST_FAMILIES:
        # a ceremony with no place / time / doer of its own: what its stages record. "di mana upacara
        # ngaben biasanya dilaksanakan?" got "tempat ngaben belum tercatat", while pabasmian is "di
        # setra" (Tier B 2026-10-13)
        staged = _stage_aspect_sentences(e, family)
        if staged:
            head = (f"{_STAGE_FALLBACK_HEADS[family]} {name} secara keseluruhan tidak tercatat, tetapi "
                    f"untuk tahapannya tercatat")
            if len(staged) <= 3:
                return f"{head} bahwa {_join_names([s[:1].lower() + s[1:].rstrip('.') for s in staged])}."
            return f"{head}:\n" + "\n".join(f"- {s}" for s in staged)
    if (family == "waktu" and content.entity_type.get(e["id"]) not in _STAGE_TYPES
            and not re.search(r"\b(?:sebelum|setelah|sesudah|sehabis|usai)\b", user_msg, re.I)):
        # a thing's time is the rite it is used in: "waktu pelaksanaan Gegaleng" got "waktu gegaleng belum tercatat"
        # while the KB says it is used in pabersihan mati -- the corpus: "ketika upacara ngelelet dilaksanakan" (L2574;
        # V2 grading, 2026-11-02). Not what comes before or after it: "apa tahapan setelah Pedangal" is no "Pedangal
        # digunakan pada saat nyiramang layon"
        rites = list(dict.fromkeys(r["target"] for r in rels if r.get("relation") in ("DIGUNAKAN_DALAM", "DIGUNAKAN_PADA")
                                   and r.get("outgoing") and r.get("target")
                                   and content.entity_type.get(r.get("target_id")) in _STAGE_TYPES))
        if rites:
            return f"{title} digunakan pada saat {_join_names(rites)}."
    if family == "simbol":
        via = _meaning_via_items(e)
        if via:
            return via
    return _template_miss(act[0] if act else _aspect_label(family, user_msg), e)


def _meaning_via_items(e: Dict[str, Any]) -> Optional[str]:
    """A material's meaning lies in the thing made of it: "baja punya makna apa" -- the steel pieces laid on the
    teeth "bermakna agar gigi ... kokoh dan kuat bagaikan besi baja" (L3177); "makna base dalam upacara itu apa" --
    base gulung in kawangen jeriji (L3232). Both said their meaning was not recorded (V2 grading, 2026-11-02). Only a
    thing made of e (or that e is made into) whose own meaning names e: arit gobed is made of baja too, but its Rare
    Angon symbol is not the steel's."""
    content = get_content()
    name = e["name"]
    items = [r["target_id"] for r in e.get("relationships") or []
             if r.get("target_id") in content.entity_name
             and (r.get("relation") == "TERBUAT_DARI" and not r.get("outgoing")
                  or r.get("relation") == "DIJADIKAN" and r.get("outgoing"))]
    named = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I)
    found = []
    for i in dict.fromkeys(items):
        item = {"id": i, "name": content.entity_name[i], "definition": content.best_definition(i),
                "relationships": _kb_relationships(i)}
        found += [s for s in _aspect_sentences(item, "simbol", with_edges=False) if named.search(s)]
    if not found:
        return None
    return (f"Makna {name} sendiri belum tercatat; yang tercatat tentang benda yang dibuat dari {name}: "
            + " ".join(_distinct_sentences(found)))


def _template_kinds(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """The numbered kinds with their gloss (names only past 12)."""
    e = enriched[0]
    eid, name = e["id"], e["name"]
    rels = e.get("relationships") or []
    content = get_content()
    kinds = content.kinds_of(eid) + [r["target_id"] for r in rels
                                     if r.get("relation") == "MEMILIKI_JENIS" and r.get("outgoing")]
    kinds = [k for k in dict.fromkeys(kinds) if k in content.entity_name]
    if not kinds:
        # "apa saja sasih yang berbadankan kosong?" names no "jenis": its definition holds the list
        # (sasih paruwak tahuk), and "jenis ... belum tercatat" answered a question nobody asked
        if not _KINDS_Q_RE.search(user_msg):
            return _deterministic_answer([dict(e, aspect_facts=[])]) or None
        # a definition that divides it says its kinds: "Maaf, jenis yadnya belum tercatat" stood above "Yadnya
        # dibagi menjadi lima (Panca Yadnya): Dewa Yadnya, ..." (sheet Failed, 2026-10-27)
        divided = [s for s in _sentences(_deterministic_answer([dict(e, aspect_facts=[])]))
                   if re.search(r"\b(?:dibagi|terbagi)\s+(?:menjadi|atas|dalam|ke)\b", s, re.I)]
        if divided:
            return " ".join(divided)
        # kinds told apart by their tiers, which a part card "tingkatan X" holds: "bade ada berapa jenis" got "jenis bade
        # belum tercatat" -- corpus L1563 "Bade jenis apa yang boleh ... dipakai ... ditentukan berdasarkan statusnya",
        # the tiers 11 / 9 / 7 (V2 grading, 2026-11-02)
        tiers = content.id_by_name.get(f"tingkatan {name.lower()}")
        if tiers and any(r["relation"] == "BAGIAN_DARI" and r["outgoing"] and r["target_id"] == eid
                         for r in _kb_relationships(tiers)):
            return f"Jenis {name} dibedakan menurut tingkatnya. {content.best_definition(tiers)}"
        return _template_miss("jenis", e, whole=True)
    count = _NUMBER_WORDS.get(str(len(kinds)), str(len(kinds))).replace("duabelas", "dua belas")
    head = f"Ada {count} jenis {name} yang tercatat"
    if len(kinds) > 12:
        return f"{head}: {_join_names([content.entity_name[k] for k in kinds])}."
    return f"{head}:\n" + "\n".join(f"{i}. {_list_item(k)}" for i, k in enumerate(kinds, 1))


def _template_stages(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """The stages in the source's order (or unnumbered), the first / last one, else how it is done."""
    e = enriched[0]
    eid, name = e["id"], e["name"]
    content = get_content()
    # the stage after or before this one (a misread "apa tahapan setelah X"): its order facts
    if _NEXT_STAGE_RE.search(user_msg):
        return _template_answer("waktu", enriched, user_msg)
    stages = _stage_ids(e)
    numbered = _numbered_stages(e)
    one = re.search(r"\b(?:tahap\w*|upacara|acara|prosesi)\s+(pertama|awal|terakhir|akhir|penutup)\b"
                    r"|\b(pertama|terakhir)\b[^.?!]*\btahap", user_msg, re.I)
    if numbered and one and not re.search(r"dari awal (?:sampai|hingga)", user_msg, re.I):
        # "tahap terakhir ngaben apa" got the whole list (the 12 evaluation categories, 2026-10-27). The last
        # only when the stages run up to the count their definitions state ("dari delapan tahapan")
        word = (one.group(1) or one.group(2)).lower()
        first = word in ("pertama", "awal")
        nums = sorted({n for n, _ in numbered})
        total = _stated_stage_total([content.id_by_name.get(s.lower()) for _, s in numbered])
        if first or not total or nums[-1] == total:
            pick = nums[0] if first else nums[-1]
            group = [s for n, s in numbered if n == pick]
            ids = [content.id_by_name.get(s.lower()) or s for s in group]
            lead = f"Tahap {'pertama' if first else 'terakhir'} {name} menurut sumber"
            if len(group) == 1:
                return f"{lead} adalah {group[0]}: {_gloss(ids[0])}"
            return f"{lead} adalah {_join_names(group)}:\n" + "\n".join(f"- {_list_item(i)}" for i in ids)
        return None
    chain = [] if numbered else _ordered_kinds(eid)
    if len(chain) >= 2:
        # kinds of the rite done one after the other are its stages: "bagaimana prosesi pitra yadnya" listed ngajar-ajar,
        # mapendem, nyekeh and ngaben titip, not that Ngaben is "Pitra Yadnya tahap pertama" and Atma Wedana "tahap
        # kedua" (L1006, L1942; the KB orders them: atma wedana DILAKUKAN_SETELAH ngaben) -- V2 grading, 2026-11-02
        others = [content.entity_name[s] for s in stages if s not in chain]
        return (f"Menurut sumber, tahapan {name} secara berurutan adalah sebagai berikut:\n"
                + "\n".join(f"{i}. {_list_item(k)}" for i, k in enumerate(chain, 1))
                + (f"\nSelain itu, rangkaian {name} juga mencakup {_join_names(others)}." if others else ""))
    if numbered:
        # stages the source gives one number go under it together: "2. Nyiramang layon, pabersihan
        # mati, dan pangringkes:" with each below, not three items numbered 2
        by_number: Dict[int, List[str]] = {}
        for n, stage in numbered:
            by_number.setdefault(n, []).append(stage)
        lines = []
        for n, group in by_number.items():
            ids = [content.id_by_name.get(s.lower()) or s for s in group]
            if len(group) == 1:
                lines.append(f"{n}. {_list_item(ids[0])}")
            else:
                joined = _join_names(group)
                lines.append(f"{n}. {joined[:1].upper()}{joined[1:]}:")
                lines += [f"   - {_list_item(i)}" for i in ids]
        shown = {stage.lower() for _, stage in numbered}
        others = [content.entity_name[s] for s in stages if content.entity_name[s].lower() not in shown]
        return (f"Menurut sumber, tahapan {name} secara berurutan adalah sebagai berikut:\n" + "\n".join(lines)
                + (f"\nSelain itu, rangkaian {name} juga mencakup {_join_names(others)}." if others else ""))
    # one recorded stage is no procedure: "bagaimana upacara ngelungah dilaksanakan" got only ngeluhurang bhatara
    # kumara once that card existed (plan #19 batch 2); a how question goes on to the definition / the model
    if stages and (len(stages) >= 2 or not (_HOW_RE.search(user_msg) and not re.search(r"\btahap", user_msg, re.I))):
        return (f"Tahapan {name} yang tercatat (urutannya tidak disebutkan dalam sumber):\n"
                + "\n".join(f"- {_list_item(s)}" for s in stages))
    # how it is done as the definition and its text facts say it -- not its edges: "bagaimana upacara ngelungah
    # dilaksanakan" got "Upacara ngelungah menggunakan klungah", "apa saja tahapan sangging" "Sangging menggunakan
    # padi ...", "sebutkan tahapan pangringkes" its kain putih and klasa (sheet Failed, 2026-10-27)
    how = _aspect_sentences(e, "cara", with_edges=False)
    if how:
        return _as_paragraph(how, name)
    # a rite with no stage list is the model's to read from its definition; anything else is a miss (the free
    # run of the 1,864 sent 59 "bagaimana alur kopi", "langkah-langkah cermin kecil" to Qwen with the how-words)
    if content.entity_type.get(eid) in _STAGE_TYPES:
        return None
    return _template_miss("tahapan atau cara", e, whole=True)


_AFTER_PREDICATES = frozenset({"DILAKUKAN_SETELAH", "DILAKSANAKAN_SETELAH", "SETELAH"})


def _ordered_kinds(eid: str) -> List[str]:
    """The kinds of eid one is done after another, as a chain in their order (first one first): ngaben, then atma
    wedana for pitra yadnya. Empty unless the KB orders at least two of its kinds among themselves."""
    content = get_content()
    kinds = set(content.kinds_of(eid))
    after = {}
    for k in kinds:
        for r in _kb_relationships(k):
            if r["relation"] in _AFTER_PREDICATES and r["outgoing"] and r["target_id"] in kinds:
                after[k] = r["target_id"]
    firsts = [k for k in set(after.values()) if k not in after]
    if len(firsts) != 1:
        return []
    following = {v: k for k, v in after.items()}
    chain = [firsts[0]]
    while chain[-1] in following and following[chain[-1]] not in chain:
        chain.append(following[chain[-1]])
    return chain


def _template_contents(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """What it is made of or contains: raw material, set members, the composition breakdown, or a miss."""
    e = enriched[0]
    eid, name = e["id"], e["name"]
    title = f"{name[:1].upper()}{name[1:]}"
    rels = e.get("relationships") or []
    content = get_content()
    raw = _raw_material_answer([e])
    if raw:
        return raw
    members = _set_members(e) if _NUMERAL_SET_RE.match(name) else []
    if len(members) >= 2:
        if not _EXPLAIN_EACH_RE.search(user_msg):
            return f"{title} terdiri dari {_join_names(members)}."
        # "jelaskan unsur unsur panca maha butha": each member with its own first sentence
        return f"{title} terdiri dari:\n" + "\n".join(
            f"- {_list_item(content.id_by_name.get(m.lower()) or m)}" for m in members)
    breakdown = _composition_breakdown(eid)
    if breakdown:
        # a wrapping is not what it is made of: "isi pripih apa saja" got only "Pripih dibungkus daun dapdap",
        # while its definition says "lempengan tipis dari logam (emas, perak, tembaga, besi), permata, atau kayu
        # cendana" (sheet Failed, route audit 2026-10-27)
        own = {r["relation"] for r in rels if r.get("outgoing")
               and r.get("relation") in PREDICATE_FAMILIES["komposisi"] - _KIND_PREDICATES}
        if own and all(p.startswith("DIBUNGKUS") for p in own):
            stated = [s for s in _sentences(_deterministic_answer([dict(e, aspect_facts=[])]))
                      if _DEF_MAY_ANSWER["komposisi"].search(s)]
            if stated:
                return f"{stated[0]} {breakdown}"
        return breakdown
    if content.entity_type.get(eid) not in COMPOSITE_TYPES:
        # the "kelengkapan" of a ceremony, a stage or a person is the sarana it uses: as contents,
        # "apa saja kelengkapan pangringkes" got "isi atau bahan pangringkes belum tercatat" (2026-10-19)
        if _equipment_as_sarana(user_msg, enriched) != user_msg:
            return _template_answer("sarana", enriched, user_msg)
        material = bool(_MATERIAL_Q_RE.search(user_msg) or re.search(
            r"\bdilengkapi\b|\bdibutuhkan\s+untuk\s+membuat\b|\bada\s+di\s+dalam\b", user_msg, re.I))
        # a rite's "isi / bahan / dilengkapi" are the sarana it uses: "bahan upacara ngelungah apa saja", "atma
        # wedana dilengkapi apa", "isi pabersihan mati apa saja" went to Qwen, which listed them (route audit
        # 2026-10-27; _code_miss leaves them to it for the same reason)
        if material and content.entity_type.get(eid) in _STAGE_TYPES:
            if _sarana_by_place([eid]).get(eid):
                return _template_answer("sarana", enriched, user_msg)
            return _template_miss("isi atau bahan", e)
        # nor is a concept, a level or a person made of anything: a miss, not the LLM, which answered
        # "nistaning madya dibuat dari apa" with the definition (NLU sweep 2026-10-19)
        if material:
            return _template_miss("isi atau bahan", e)
        if re.search(r"\bunsur|komponen|\bbagian", user_msg, re.I):
            # the "unsur" of a rule card are what its rules go by: "unsur-unsur dewasa ngaben" got "belum tercatat"
            # from Qwen, while the card's rules go by sasih and wuku / wewaran (V2 grading, 2026-11-02)
            sents = _sentences(_definition_text(e))
            bases = [m.group(1) for s in sents if (m := re.match(r"\s*Berdasarkan\s+([^,]+),", s))]
            if len(bases) >= 2:
                # "sasih serta wuku dan wewaran", not "sasih dan wuku dan wewaran"
                joined = (", ".join(bases[:-1]) + " serta " + bases[-1] if any(" dan " in b for b in bases)
                          else _join_names(bases))
                return f"{title} ditentukan berdasarkan {joined}. " + " ".join(sents[1:])
            # a rite's are its stages: "apa saja komponen pitra yadnya" got ngajar-ajar, mapendem, nyekeh and ngaben
            # titip from Qwen, not Ngaben and Atma Wedana, its two stages (V2 grading, 2026-11-02)
            if content.entity_type.get(eid) in _STAGE_TYPES:
                staged = _template_stages("tahapan", enriched, user_msg)
                if staged and not staged.startswith("Maaf"):
                    return staged
        # the "unsur" of a concept or a ceremony: its members, kinds or stages -- the pipeline's
        return None
    stated = [s for s in _sentences(_definition_text(e)) if _CONTENTS_IN_DEF_RE.search(s)]
    if stated:
        return " ".join(stated)
    return _template_miss("isi atau bahan", e)


def _template_sarana(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """The sarana the term and each of its stages use."""
    e = enriched[0]
    eid, name = e["id"], e["name"]
    title = f"{name[:1].upper()}{name[1:]}"
    content = get_content()
    places = _sarana_by_place([eid]).get(eid, [])
    # what is needed to make or complete it: the sarana for a tirtha are what it is made with
    # ("apa saja sarana untuk memohon tirtha kawitan": rayunan, pajegan, ..., Tier B 2026-10-13)
    made_with = _distinct_sentences(_edge_sentences(
        e, {"DIPERLUKAN_UNTUK_MEMBUAT", "DILENGKAPKAN_PADA"},
        frozenset({"DIPERLUKAN_UNTUK_MEMBUAT", "DILENGKAPKAN_PADA"}), outgoing=False))
    if not places and not made_with:
        # what is used in a thing made of parts are its parts: "sarana apa yang dipakai dalam daksina" got "sarana
        # daksina belum tercatat" above daksina's own contents (V2 grading, 2026-11-02)
        if content.entity_type.get(eid) in COMPOSITE_TYPES and _composition_breakdown(eid):
            return _template_contents("komposisi", enriched, user_msg)
        return _template_miss("sarana", e)
    # what a person or a thing uses is said with it as subject: "Sangging menggunakan padi dan uang
    # kepeng", not "Sarana yang digunakan dalam sangging adalah ..." (2026-10-19)
    ritual = content.entity_type.get(eid) in _STAGE_TYPES
    lines = [f"Sarana yang digunakan dalam {name} adalah {_join_names(items)}." if ritual
             else f"{title} menggunakan {_join_names(items)}."
             for pid, _, items in places if pid == eid]
    stage_lines = [f"- {place[:1].upper()}{place[1:]}: {_join_names(items)}."
                   for pid, place, items in places if pid != eid]
    if stage_lines:
        lines.append(("Sarana pada tiap tahapannya:" if lines else f"Sarana yang digunakan dalam tahapan {name}:")
                     + "\n" + "\n".join(stage_lines))
    return "\n".join(made_with + lines)


def _template_other_names(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """One list of its other names, the refined one apart."""
    e = enriched[0]
    name = e["name"]
    title = f"{name[:1].upper()}{name[1:]}"
    rels = e.get("relationships") or []
    content = get_content()
    # one list of the other names, the refined one apart: "Ngaben juga dikenal sebagai mreteka
    # sawa, atiwa-tiwa, malebuang, dan pangabenan. Sebutan halusnya adalah palebon." -- not a
    # sentence per relation ("Ngaben dikenal sebagai ... Ngaben sama dengan ...", 2026-10-15)
    preds = PREDICATE_FAMILIES["sebutan_lain"] - {"ADALAH"}
    names, refined, said = [], [], []
    for r in rels:
        pred, target = r.get("relation"), r.get("target")
        if pred not in preds or not target or r.get("variant_op"):
            continue
        if pred != "SEBUTAN_HALUS_UNTUK":
            names.append(target)
        elif r.get("outgoing"):
            said.append(content.render(pred, name, target))
        else:
            refined.append(target)
    names += (e.get("aliases") or []) + _definition_other_names(e)

    def key(n: Text) -> str:
        # one name with or without its rite word: "upacara ngelelet, Ngelelet, dan Melelet" (2026-10-26)
        return _ortho_key(re.sub(r"^(?:upacara|acara|prosesi|ritual)\s+", "", n.strip(), flags=re.I))

    seen = {key(name)} | {key(n) for n in refined}
    names = [n for n in names if not (key(n) in seen or seen.add(key(n)))]
    found = [f"{title} juga dikenal sebagai {_join_names(names)}."] if names else []
    if refined:
        found.append(f"Sebutan halusnya adalah {_join_names(refined)}.")
    found += _distinct_sentences(said, e)
    return " ".join(found) if found else f"Maaf, sebutan lain untuk {name} belum tercatat di basis data."


# words of a card's gloss that say how a thing is used in a rite, not what the word means
_RITUAL_USE_RE = re.compile(r"\b(?:upacara|upakara|banten|sesajen|sesaji|ngaben|jenazah|patulangan|soda|raka-raka"
                            r"|sarana|ritual|eteh-eteh)\b", re.I)
_PLAIN_WORDS: Optional[frozenset] = None


def _plain_indonesian(name: Text) -> bool:
    """Every word of the name is ordinary Indonesian: in the common-word list, or written as a plain word (tagged O)
    anywhere in the corpus behind it -- "singa" and "telur" fall below that list's three-times cut."""
    global _PLAIN_WORDS
    if _PLAIN_WORDS is None:
        import kb_resolver
        words = set()
        for line in Path(kb_resolver._COMMON_WORDS_FILE).read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[-1] == "O":
                words.add(parts[0].lower())
        _PLAIN_WORDS = frozenset(words)
    resolver = get_resolver()
    return all(w in _PLAIN_WORDS or _is_everyday_word(w, resolver) for w in name.lower().split())


def _gloss_is_ritual_use(entity_id: Text, gloss: Text) -> bool:
    """An ordinary word whose card says only how it is used in a rite, not what the word means: "Beras dalam upacara
    Ngaben direndam ...", "Kelengkapan upakara untuk menghiasi tubuh jenazah ..." (bunga), "Salah satu bentuk
    patulangan ..." (singa). Not a card that defines it ("Banten adalah sesajen ...", "Ayam adalah unggas ...") nor
    one that says what the word means anywhere ("... kurang lebih berarti 'menengah'", madya)."""
    content = get_content()
    name = content.entity_name.get(entity_id, entity_id)
    card = content.best_definition(entity_id) or ""
    # a rite's card is the rite: ngaben's "Upacara pembakaran jenazah ..." defines it
    if (content.entity_type.get(entity_id) in _STAGE_TYPES or not _plain_indonesian(name)
            or not _RITUAL_USE_RE.search(gloss) or re.search(r"\bberarti\b", card, re.I)):
        return False
    defines = re.match(rf"\s*{re.escape(name)}\s*(?:\([^)]*\)\s*)?(?:adalah|merupakan|ialah)\b", card, re.I)
    return not defines or bool(re.match(r"\s*salah satu\b", gloss, re.I))


def _word_card_fits(word: Dict[str, Any], gloss: Text, term: Dict[str, Any]) -> bool:
    """Whether a word's card glosses the word as the term's name uses it (V2 grading, 2026-11-02): not an ordinary
    word whose card gives a ritual use ('Kata "beras" berarti beras dalam upacara Ngaben direndam ...' for beras
    hitam), not a rite the term is no kind or stage of ('Kata "pabersihan" berarti upacara penyucian ... diadakan
    setelah Ngulapin' for pabersihan mati, another rite), not a word the term's own other name spells otherwise
    (Manah Tirtha Ening is "memanah tirtha ening": its manah is no mind)."""
    content = get_content()
    wid, tid, w = word["id"], term["id"], word["name"].lower()
    if _gloss_is_ritual_use(wid, gloss):
        return False
    # a rite named after another rite only ("dewasa ngaben" is the day for the rite ngaben itself)
    if (content.entity_type.get(wid) in _STAGE_TYPES and content.entity_type.get(tid) in _STAGE_TYPES
            and not content.is_kind_of(tid, wid)
            and not any(r.get("relation") == "BAGIAN_DARI" and r.get("outgoing") and r.get("target_id") == wid
                        for r in term.get("relationships") or [])):
        return False
    own = term["name"].lower().split()
    if w in own:
        k = own.index(w)
        for other in (term.get("aliases") or []) + _definition_other_names(term):
            words = other.lower().split()
            # a verb form ("memanah"), not a derived noun of the same word ("dewasa pangabenan" is still ngaben)
            if len(words) == len(own) and words[k] != w and w in words[k] and re.match(r"(?:me|be|di)", words[k]):
                return False
    return True


def _template_word_origin(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """Word origin and literal meaning."""
    e = enriched[0]
    eid, name = e["id"], e["name"]
    content = get_content()
    # not where an element comes from: "asal-usul nama ganda" got "Ganda berasal dari pretiwi", "apa makna kata
    # rasa" "Rasa berasal dari apah" (sheet Failed, 2026-10-27); a word's origin is BERASAL_DARI_KATA
    preds = PREDICATE_FAMILIES["asal_kata"] - {"BERASAL_DARI"}
    found = _edge_sentences(e, preds)
    # the word it comes from, with what that word means: "istilah malamasa berasal dari mana" got only
    # "Malamasa berasal dari kata mala." once that edge existed (plan #19 batch 2) -- the term's own sentence
    # about the word ('Kata mala berarti "tidak baik": ...'), else the word's card
    for r in e.get("relationships") or []:
        if r.get("relation") == "BERASAL_DARI_KATA" and r.get("outgoing") and r.get("target"):
            word = r["target"]
            own = [s for s in _sentences(_definition_text(e))
                   if re.search(rf'\bkata\s+"?{re.escape(word)}"?\s+berarti\b', s, re.I)]
            gloss = _meaning_gloss(r.get("target_id"))
            found += own[:1] or ([f'Kata "{word}" berarti {gloss}'] if gloss else [])
    found = _distinct_sentences(content.attribute_sentences(eid, preds) + found, e)
    # "arti kata pitra yadnya": each word of the name that is a KB term (_extract_and_resolve)
    # 'Kata "pitra" berarti para pendahulu, ...' -- the colon only for a gloss that is itself a
    # sentence about something else ("Bhuta Kala adalah ...")
    words = [f'Kata "{w["name"]}"' + (": " if re.match(r"(?:\S+\s+){1,5}(?:adalah|merupakan)\s", g) else " berarti ")
             + g for w in enriched[1:] if (g := _meaning_gloss(w["id"])) and _word_card_fits(w, g, e)]
    if not found and not words:
        # the definition's own word meaning: "Maaf, arti kata lembu belum tercatat ... Yang tercatat: Lembu
        # secara harfiah berarti sapi" contradicted itself (7 in the LLM comparison, 2026-10-20)
        origin = _word_label(user_msg) == "asal kata"
        # "Layon adalah sebutan halus ... untuk jenazah" says what the word means ("arti kata layon" got
        # "Maaf, arti kata layon belum tercatat" above that sentence)
        names_y = re.compile(rf"\s*{re.escape(name)}\s+(?:\([^)]*\)\s+)?adalah\s+sebutan\b[^.;]*\b(?:untuk|bagi)\b",
                             re.I)
        # where a word comes from: a language, "berasal dari kata", or what a word inside the name means ('Kata
        # "mala" berarti "tidak baik"' for malamasa, '"Jun" ... berarti periuk' for jun pere) -- not what the whole
        # name means: "asal-usul nama abu" got "Abu secara umum berarti sisa material ..." (route audit 2026-10-27)
        def answers(s: Text) -> bool:
            if origin:
                return bool(_WORD_LANGUAGE_RE.search(s) or _names_word_of(s, name) or re.search(
                    r"\b(?:berasal|diambil|diserap)\s+dari\s+(?:kata|bahasa)\b", s, re.I))
            return bool(_word_meaning_sentence(s, name) or names_y.match(s))
        stated = [s for s in _sentences(_definition_text(e)) if answers(s)]
        if stated:
            return " ".join(stated)
        # (not for "secara harfiah", "arti harfiah", "kata dasar": what it names is no literal meaning nor root --
        # 'Kata "cermin kecil" berarti cermin kecil ditaruh ...', free run of the 1,864, 2026-10-27)
        if not origin and not re.search(r"harfiah|harafiah|kata\s+dasar|etimologi", user_msg, re.I):
            # what the word means, as another definition says it ('kata "pitra" secara harfiah berarti orang tua',
            # in pitra yadnya's), else what it names: "arti kata pitra" got "Maaf, arti kata pitra belum
            # tercatat" above its own gloss (the 12 evaluation categories, 2026-10-27)
            elsewhere = _word_meaning_elsewhere(name)
            if elsewhere:
                return elsewhere
            gloss = _meaning_gloss(eid)
            if gloss and _gloss_is_ritual_use(eid, gloss):
                # an ordinary word is no term of its own: 'Kata "singa" berarti salah satu bentuk patulangan ...', 'Kata
                # "buah-buahan" berarti salah satu isi soda' gave a ritual use as the word's meaning (V2 grading)
                lead = _first_sentence(_deterministic_answer([dict(e, aspect_facts=[])]))
                return f'Kata "{name}" adalah kata bahasa Indonesia sehari-hari, bukan istilah khusus. {lead}'
            if gloss:
                return f'Kata "{name}" berarti {gloss}'
        return _template_miss(_word_label(user_msg), e)
    lead = _first_sentence(_deterministic_answer([dict(e, aspect_facts=[])]))
    tail = [f"Jadi, {lead}"] if words and lead else []
    return "\n".join(words + found + tail)


def _template_belongs_to(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """What it belongs to: its kind parents, the rite it is a stage of, what it is used in."""
    e = enriched[0]
    eid, name = e["id"], e["name"]
    content = get_content()
    parents = [content.entity_name[p] for p in sorted(content.kind_parents.get(eid, ()))
               if p in content.entity_name]
    found = [content.render("TERMASUK_JENIS", name, _join_names(parents))] if parents else []
    # what it is a kind of is not where it is used: "babelonyoh termasuk kategori apa" got "Babelonyoh digunakan
    # dalam pabersihan mati", "base jenis dari apa" "Base digunakan dalam nyiramang layon" (sheet Failed)
    kind_q = bool(re.search(r"\bkategori\w*|\bjenis\b|\bgolongan\w*|\bkelompok\w*|\bklasifikasi\w*", user_msg, re.I)
                  and not re.search(r"\bbagian\b|\bdigunakan\b|\bdipakai\b|\b(?:upacara|ritual|rangkaian|prosesi)"
                                    r"\s+apa\b", user_msg, re.I))
    # (what it is a part of stays: "pabersihan mati jenis dari apa" -- a stage of nyiramang layon)
    rites = _edge_sentences(e, {"BAGIAN_DARI"} if kind_q else {"BAGIAN_DARI", "DIGUNAKAN_DALAM", "DIGUNAKAN_PADA"})
    # which ceremony: the whole definition, where a term's use is often said after its first clause
    # ("wangsa digunakan dalam upacara apa" -- "... dalam upacara Ngaben, wangsa seseorang turut
    # menentukan bentuk petulangan" was cut off, NLU sweep 2026-10-19); "termasuk jenis apa" its opening
    which_rite = bool(re.search(r"\b(?:upacara|ritual|rangkaian|prosesi)\s+apa\b", user_msg, re.I))
    # a which-ceremony question with a ceremony recorded is answered by it alone ("Kayu cendana termasuk salah satu
    # jenis kayu" above "digunakan dalam nyiramang layon" answered no part of it, canon sweep 2026-10-28)
    found = _distinct_sentences((rites if which_rite and rites else found + rites), e)
    return " ".join(found) if found else _template_miss("kelompok atau induk", e, whole=which_rite)


# the template of each aspect family (an aspect one, _template_aspect, for _ASPECT_TEMPLATE_FAMILIES)
_TEMPLATES = {
    "": _template_definition,
    "jenis": _template_kinds,
    "tahapan": _template_stages,
    "komposisi": _template_contents,
    "sarana": _template_sarana,
    "sebutan_lain": _template_other_names,
    "asal_kata": _template_word_origin,
    "induk": _template_belongs_to,
}


def _template_answer(family: str, enriched: List[Dict[str, Any]], user_msg: Text = "") -> Optional[str]:
    """The template answer for `family` about enriched[0], or None when this term's question
    needs the pipeline after all. One function per family: _TEMPLATES, _template_aspect."""
    if family in _ASPECT_TEMPLATE_FAMILIES:
        return _template_aspect(family, enriched, user_msg)
    template = _TEMPLATES.get(family)
    return template(family, enriched, user_msg) if template else None


def _names_kb_term(user_msg: Text) -> bool:
    """ActionOutOfScope's test (regression Tier A checks it on the out_of_scope examples):
    the message names a KB term as written, and either that term is ngaben or no other
    word is left over. A word only a typo / force_merge hit explains counts as left over."""
    resolver = get_resolver()
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    named = [m for m, _ in mentioned if m.via in _NAMED_VIA]
    # every loose hit of the scan, also one _mentioned_terms dropped: "berapa harga kopi" -- "harga", the head of
    # harga tirtha, is dropped beside kopi, and kopi alone then read as the whole question (2026-10-27)
    leftover = leftover + [p for _, _, m, p in _scan_terms(user_msg, resolver)[0] if m.via not in _NAMED_VIA]
    return bool(named) and (not leftover or any(m.id == "ngaben" for m in named))


# words that ask for the topic's items without naming them ("nama 9 dewa tersebut")
_FOLLOW_UP_META = frozenset({"nama", "namanya", "daftar", "daftarnya", "sebutan", "istilah", "contoh", "contohnya"})


def _topic_follow_up(user_msg: Text, current_entity: Optional[Text]) -> bool:
    """ActionOutOfScope's second test (Tier A checks it on the out_of_scope examples with a topic):
    the message names no term, points back (tersebut / itu / tadi ..., `_points_back`), and the
    topic's own definition uses every other content word. "siapa saja nama 9 dewa tersebut" after
    "apa itu dewata nawa sanga" was refused as off-topic (live, 2026-10-15); "cuaca hari ini"
    points back too, but no card about the topic says "cuaca"."""
    if not current_entity:
        return False
    resolver = get_resolver()
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    topic = resolver.resolve(current_entity)
    if not topic:
        return False
    # (a class the topic's card names is the topic's word: "nama 9 dewa tersebut" -- see _topic_class_words)
    mentioned = [x for x in mentioned if x not in _topic_class_words(mentioned, topic, user_msg)]
    if mentioned or not _points_back(user_msg, mentioned, resolver):
        return False
    return _card_uses(topic, [re.sub(r"nya$", "", w) for w in leftover
                              if w not in _STOPWORDS_ID and w not in _FOLLOW_UP_META])


_COUNTED_RE = (r"(?:\d+|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|dua belas|para|semua|seluruh|"
               r"kedua|ketiga|keempat|kelima|kesembilan)\s+")


def _topic_class_words(mentioned: List[tuple], topic, user_msg: Text) -> List[tuple]:
    """The mentioned terms that stand for the topic itself: a class (it has kinds) the topic's own card names, that the
    topic is a kind of ("banten tersebut" after banten pejati) or that the message counts ("nama 9 dewa tersebut" after
    nawa dewata, "sembilan dewa ..." -- refused once dewa had a card of its own, 2026-10-28). "sulinggih tersebut" after
    ngaben is sulinggih."""
    content = get_content()
    # the topic's members: its kinds and its parts (nawa dewata's dewa sambu, dewa rudra, ...)
    members = set(content.kinds_of(topic.id)) | {
        r["target_id"] for r in _kb_relationships(topic.id) if r["relation"] == "BAGIAN_DARI" and not r["outgoing"]}
    return [(m, p) for m, p in mentioned
            if m.id != topic.id and content.kinds_of(m.id) and _card_uses(topic, m.name.split())
            and (content.is_kind_of(topic.id, m.id) or re.search(_COUNTED_RE + re.escape(p) + r"\b", user_msg, re.I)
                 or any(content.is_kind_of(x, m.id) for x in members))]


def _card_uses(topic, words: List[str]) -> bool:
    """Every word is in the topic's own card (its definition and name), on its first five letters."""
    dwords = set(_WORD_RE.findall((_definition_text(topic.entity) + " " + topic.entity["name"]).lower()))
    return all(any(d[:5] == w[:5] if len(w) >= 5 else d == w for d in dwords) for w in words)


def _quotes_topic(leftover: List[str], current_entity: Optional[Text], resolver) -> bool:
    """A message naming no term whose every content word is in the topic's own card asks about the topic:
    "karunia seperti apa yang dimaksud?" after "Anugerah raja adalah karunia dari raja ..." got "Maaf, saya tidak
    menemukan 'karunia' ... Mungkin maksud Anda: arjuna?" (user, 2026-10-28). Pointing words (maksud, dimaksud,
    contohnya ...) are no content."""
    topic = resolver.resolve(current_entity) if current_entity else None
    words = [re.sub(r"nya$", "", w) for w in leftover if w not in _STOPWORDS_ID and w not in _FOLLOW_UP_META
             and not {w, re.sub(r"nya$", "", w), re.sub(r"^di", "", w)} & _POINTER_WORDS]
    return bool(topic and words and _card_uses(topic, words))


def _slot_events(entity_history: List[str], found_names: List[str]) -> List[Dict[Text, Any]]:
    """The topic is the term the question named (found_names[0] -- the message's own
    terms come first). It used to be found_names[-1], usually a term carried over from
    the history, so "hanya itu sarananya?" after "apa itu nyiramang layon ..." went to
    ngaben (2026-09-29). The history keeps the most recently discussed term last."""
    topic = found_names[0]
    history = [n for n in entity_history if n not in found_names] + found_names[1:] + [topic]
    return [SlotSet("current_entity", topic), SlotSet("entity_history", history[-6:])]


def _simple_after_all(action, dispatcher: CollectingDispatcher, tracker: Tracker,
                      domain: Dict[Text, Any]) -> Optional[List[Dict[Text, Any]]]:
    """A turn NLU read as tanya_kompleks / nlu_fallback whose own words make it a simple question the template router
    takes (_inferred_template_intent): answered by ActionTemplateAnswer, falling back to `action`'s own pipeline,
    never back here. None when it is not."""
    intent = (tracker.latest_message.get("intent") or {}).get("name")
    if intent not in ("tanya_kompleks", "nlu_fallback"):
        return None
    user_msg = tracker.latest_message.get("text", "")
    inferred = _inferred_template_intent(user_msg)
    if not inferred or _template_route(user_msg, inferred, tracker.get_slot("current_entity"), get_resolver())[0] is None:
        return None
    return ActionTemplateAnswer().answer(dispatcher, tracker, domain, inferred, fallback=action.pipeline)


class ActionGraphRAG(Action):
    def name(self) -> Text:
        return "action_graph_rag"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        simple = _simple_after_all(self, dispatcher, tracker, domain)
        return simple if simple is not None else self.pipeline(dispatcher, tracker, domain)

    def pipeline(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
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


class ActionTemplateAnswer(Action):
    """The simple-question intents (tanya_definisi, tanya_makna, ...): a template answer from the
    KB, with no LLM call. A message that is not simple after all (_template_route), names nothing
    the scan finds, or has no template for its term goes to ActionGraphRAG, as a misfiled question
    goes from ActionOutOfScope. Each turn's route is logged (routing_log.jsonl)."""

    def name(self) -> Text:
        return "action_jawab_template"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return self.answer(dispatcher, tracker, domain, (tracker.latest_message.get("intent") or {}).get("name"))

    def answer(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any], intent: Optional[Text],
               fallback=None) -> List[Dict[Text, Any]]:
        """The turn under `intent` (NLU's, or the one _simple_after_all infers); a question the template cannot
        take goes to `fallback` (ActionGraphRAG's pipeline by default)."""
        user_msg = tracker.latest_message.get("text", "")
        current_entity = tracker.get_slot("current_entity")
        entity_history: List[str] = tracker.get_slot("entity_history") or []

        family, why_not = _template_route(user_msg, intent, current_entity, get_resolver())
        answer, found_names = None, []
        if family is not None:
            # silent on a miss: the pipeline below has the extraction LLM and says what is missing
            enriched, _, found_names = _extract_and_resolve(
                dispatcher, tracker, user_msg, entity_history,
                current_entity=current_entity, announce_miss=False, allow_llm=False)
            if not enriched:
                why_not = "no term found"
            elif neo4j_conn.failed:
                answer = _outage_answer(enriched)
            elif len(enriched) > 1 and family != "asal_kata":
                # a term the rules add (burning -> ngaben, a day -> dewasa ngaben, a description -> its entry)
                why_not = "two or more terms"
            elif _misclassed_terms(user_msg, get_resolver()):
                # "sasih kliwon": the pipeline corrects the premise first
                why_not = "misclassed term"
            else:
                answer = _template_answer(family, enriched, user_msg)
                why_not = "" if answer else "no template for this term"
                if answer:
                    answer = _tidy_answer(_with_note(" ".join(_synonym_sentences(enriched, answer)), answer))
        if answer is None:
            _log_jsonl(_ROUTING_LOG_PATH, {"kind": "pipeline", "intent": intent, "reason": why_not,
                                           "user_msg": user_msg})
            return (fallback or ActionGraphRAG().pipeline)(dispatcher, tracker, domain)
        _log_jsonl(_ROUTING_LOG_PATH, {"kind": "template", "intent": intent, "family": family,
                                       "user_msg": user_msg})
        dispatcher.utter_message(text=answer)
        return _slot_events(entity_history, found_names)


class ActionLLMFallback(Action):
    def name(self) -> Text:
        return "action_llm_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        simple = _simple_after_all(self, dispatcher, tracker, domain)
        return simple if simple is not None else self.pipeline(dispatcher, tracker, domain)

    def pipeline(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
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
            answer = _llm_invoke([{"role": "user", "content": fallback_prompt}], "fallback")[0]
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


# a question word that asks for something (not "apa kabar", "boleh tanya?") and the words of a greeting
_ASKS_RE = re.compile(r"\b(?:berapa|kapan|siapa|bagaimana|gimana|gmn|kenapa|mengapa|knp|di ?mana|ke ?mana|dari ?mana)\b",
                      re.I)
_GREETING_RE = re.compile(r"\b(?:halo|hallo|helo|hai|hi|hello|hey|pagi|siang|sore|malam|swastiastu|salam|assalamualaikum"
                          r"|permisi|kabar|kenalan|namamu|kamu|kau|anda|bot|robot|chatbot)\b", re.I)


class ActionSapa(Action):
    """NLU said sapa (a greeting). A Ngaben question it misfiles is answered, by ActionOutOfScope's test
    (`_names_kb_term`): "boleh foto saat ngaben?" got "Om Swastiastu, Saya asisten ..." (the 12 evaluation
    categories, 2026-10-27)."""

    def name(self) -> Text:
        return "action_sapa"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        if _names_kb_term(user_msg):
            return ActionGraphRAG().run(dispatcher, tracker, domain)
        # a question with no greeting in it: "berapa lama sih prosesnya dari awal sampe selesai?" after three turns about
        # ngaben got "Om Swastiastu, Saya asisten ..." (human test 2026-11-03). The fallback tries the KB with the topic
        # first and refuses what is off-topic; "boleh tanya?" and "halo, apa kabar?" stay greetings
        if (_ASKS_RE.search(user_msg) or _aspect_families(user_msg)) and not _GREETING_RE.search(user_msg):
            return ActionLLMFallback().run(dispatcher, tracker, domain)
        dispatcher.utter_message(response="utter_sapa")
        return []


class ActionOutOfScope(Action):
    """NLU said out_of_scope. A message that names a KB term is answered anyway when
    the term is ngaben itself or nothing else is left in the message: NLU sees only the
    words, and a Ngaben question it misfiles ("bagaimana proses ngaben" was out_of_scope
    until 2026-09-29) got a flat refusal without the KB ever being asked. Any KB term
    alone is not enough -- nasi, kopi, emas, bunga, pura and harga are KB terms, and
    "resep nasi goreng" must stay out of scope. A typo-level hit does not overrule NLU. A
    follow-up about the remembered topic is answered too (`_topic_follow_up`)."""

    def name(self) -> Text:
        return "action_out_of_scope"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        if _names_kb_term(user_msg) or _topic_follow_up(user_msg, tracker.get_slot("current_entity")):
            return ActionGraphRAG().run(dispatcher, tracker, domain)
        dispatcher.utter_message(response="utter_out_of_scope")
        return []

"""Custom actions for the GraphRAG Ngaben bot using Neo4j and Qwen via Ollama."""
import os
import json
import re
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
from kb_content import PREDICATE_FAMILIES, get_content

load_dotenv(find_dotenv())

_BOT_DIR = Path(__file__).resolve().parent
_REFUSAL_LOG_PATH = _BOT_DIR / "llm_refusal_log.jsonl"
_UNRESOLVED_LOG_PATH = _BOT_DIR / "unresolved_log.jsonl"
_NEO4J_ERROR_LOG_PATH = _BOT_DIR / "neo4j_error_log.jsonl"

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Initialize Qwen via Ollama
llm = ChatOllama(model="qwen2.5", temperature=0)


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
// kinds/parts/members first, so a hub node (ngaben: ~30 edges) never loses them to the cap
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
         target_labels: labels(m)
       })[..40] AS relationships
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
        for fact in (e.get("facts") or []) + (e.get("aspect_facts") or []):
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


def _log_refusal(user_msg: str, enriched: List[Dict[str, Any]], llm_answer: str) -> None:
    _log_jsonl(_REFUSAL_LOG_PATH, {
        "kind": "llm_refusal_override",
        "user_msg": user_msg,
        "entities": [e["id"] for e in enriched],
        "llm_answer": llm_answer,
    })


def _log_fabrication(user_msg: str, enriched: List[Dict[str, Any]], llm_answer: str) -> None:
    _log_jsonl(_REFUSAL_LOG_PATH, {
        "kind": "llm_fabrication_override",
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


def _term_is_grounded(term: str, said: set) -> bool:
    words = [w for w in re.findall(r"\w+", term.lower()) if len(w) >= 3]
    return any(w in said or any(fuzz.ratio(w, s) >= 80 for s in said) for w in words)


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
    try:
        resolved_text = llm.invoke([HumanMessage(content=resolve_prompt)]).content.strip().lower()
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

    if not raw_terms:
        if announce_miss:
            dispatcher.utter_message(text="Maaf, saya tidak menangkap istilah spesifik dari pertanyaan Anda.")
        return [], [], []

    # Step 2: kb_resolver maps each free-text term to a canonical KB id --
    # exact name/alias -> force_merge -> modifier-strip -> rapidfuzz.
    resolver = get_resolver()
    matches = []
    unresolved = []
    asked_as: Dict[str, str] = {}
    for term in raw_terms:
        term = _widen_to_named_term(_peel_aspect_words(term, resolver), user_msg, resolver)
        m = resolver.resolve(term)
        if m and m.id not in {x.id for x in matches}:
            matches.append(m)
            # a different name for the same concept ("samskara" -> sangaskara), not a typo.
            # "ortho" too: the extraction LLM wrote "nggerorasin" for the user's
            # "ngerorasin" (an alias of Atma Wedana), and the answer then called
            # ngerorasin "a type of Atma Wedana" (2026-09-25)
            t, n = term.lower(), m.name.lower()
            if (m.via in ("alias", "force_merge", "ortho") and t not in n and n not in t
                    and _ortho_key(t) != _ortho_key(n)):
                asked_as[m.id] = _user_spelling(term, user_msg, m.entity)
        elif not m:
            unresolved.append(term)

    # Step 2b: resolve_many() deterministically splits "X dan Y"/"X vs Y"-style
    # conjunctions and resolves each side -- union in anything it catches that the
    # free-form LLM split (Step 1) silently dropped (e.g. "bade dan naga banda"),
    # without touching what Step 1's coreference-aware path already resolved.
    matched_ids = {m.id for m in matches}
    own = resolver.resolve_many(user_msg, limit=4)
    for m in own:
        if m.id not in matched_ids:
            matches.append(m)
            matched_ids.add(m.id)
    # When the message itself names two or more terms, a term the extraction LLM
    # carried over from the history is not part of this question: "apa itu sawa dan
    # apa hubungannya dengan jenazah" right after a turn about bade came back as
    # [sawa, bade, jenazah] (2026-09-25). With one named term the history still counts
    # -- "apa hubungannya dengan jenazah" after a turn about sawa needs sawa.
    own_ids = {m.id for m in own}
    if len(own_ids) >= 2:
        said = set(re.findall(r"\w+", user_msg.lower()))
        matches = [m for m in matches if m.id in own_ids or any(
            _term_is_grounded(n, said) for n in [m.name] + list(m.entity.get("aliases") or []))]
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
            if suggestions:
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
            r["statement"] = content.render(r["relation"], subj, obj)
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
            "aliases": [a for a in (m.entity.get("aliases") or []) if len(a.split()) <= 4][:8],
        })

    if unresolved:
        _log_unresolved(user_msg, unresolved, [])
        # only mention a miss the user can recognise as their own words
        typed = [t for t in unresolved if t.lower() in user_msg.lower()]
        if announce_miss and typed:
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
_STAGES_Q_RE = re.compile(r"\btahap|\burutan\b|\brangkaian\b", re.I)
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
    # what X is made of / contains / comes with ("soda dilengkapi apa?", "apa isi punjung")
    (re.compile(r"dilengkapi|kelengkapan|\bisi(nya)?\b|berisi|terdiri|terbuat|\bbahan|komponen|\bunsur", re.I),
     "komposisi"),
    (re.compile(r"\bmakna|\blambang|melambangkan|simbol|filosofi", re.I), "simbol"),
    (re.compile(r"di ?mana|\bletak(nya)?\b|diletakkan|ditaruh|ditempatkan|ke ?mana|\bposisi", re.I), "lokasi"),
    (re.compile(r"\bkapan\b|hari apa|berapa hari|hari ke|\bwaktu(nya)?\b|saat apa|\bsyarat", re.I), "waktu"),
    (re.compile(r"\bsiapa (yang|saja)\b|oleh siapa|dipimpin|dilakukan oleh|\bpelaku", re.I), "pelaku"),
    (re.compile(r"\bwarna|\bbentuk(nya)?\b|berbentuk|ukuran|\bpanjang(nya)?\b|\bciri|bertingkat|"
                r"berapa (tingkat|panjang|banyak|lapis|kali|buah|lembar)", re.I), "ciri"),
    (re.compile(r"\bfungsi|kegunaan|\bguna(nya)?\b|untuk apa|\btujuan|\bbertujuan|manfaat|\bperan(an|nya)?\b|"
                r"dipakai untuk|digunakan untuk|\bakibat|\bdampak|\bmengapa\b|\bkenapa\b|\balasan", re.I), "fungsi"),
)
# "how / what happens" is the broadest aspect: used only when no specific one matched,
# and never for "bagaimana hubungan/perbedaan X dan Y" (a relation question needs every edge)
_HOW_RE = re.compile(r"\bbagaimana\b(?!\s+(hubungan|kaitan|perbedaan|beda))|\bcara\b|\bprose(s|si)\b|"
                     r"diperlakukan|apa yang terjadi|menjadi apa|\bberubah", re.I)


_COMPOSITION_Q_RE = re.compile(r"dilengkapi|kelengkapan|\bisi(nya)?\b|berisi|terdiri|terbuat|\bbahan|komponen", re.I)


def _aspect_predicates(user_msg: Text) -> Optional[set]:
    families = [fam for pattern, fam in _ASPECT_FAMILIES if pattern.search(user_msg)]
    if not families and _HOW_RE.search(user_msg):
        families = ["cara"]
    if not families:
        return None
    return set().union(*(PREDICATE_FAMILIES[f] for f in families))


# A named set -- Panca Yadnya, Tri Loka, Tri Sarira, Panca Maha Bhuta, ... -- is
# only explained when all its members are named. The small model sometimes names
# one member and drifts to it (panca yadnya -> only pitra yadnya), so the member
# list is completed deterministically from the graph when the answer misses some.
_NUMERAL_SET_RE = re.compile(r"^(eka|dwi|tri|catur|panca|sad|sapta|asta|nawa|dasa)[ -]?\w", re.I)


def _set_members(e: Dict[str, Any]) -> List[str]:
    out = []
    for r in e.get("relationships") or []:
        rel, outgoing = r.get("relation"), bool(r.get("outgoing"))
        if (rel in ("TERMASUK_JENIS", "BAGIAN_DARI") and not outgoing) or \
                (rel in ("TERDIRI_DARI", "BERUPA", "BERUNSUR") and outgoing):
            if r.get("target") and r["target"] not in out:
                out.append(r["target"])
    return out


def _complete_set_members(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    # only for the set the question is about (the first resolved term), and
    # spelling-insensitive ("antahkarana" == "antah karana")
    if not enriched or not _NUMERAL_SET_RE.match(enriched[0].get("name") or ""):
        return answer
    e = enriched[0]
    members = _set_members(e)
    said = _ortho_key(answer)
    if len(members) >= 2 and any(_ortho_key(m) not in said for m in members):
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
    r"|\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)\s+" + _CONTEXT_WORD +
    # "... yang disebutkan dalam definisi dan hubungan yang diberikan"
    r"|\s*(?:yang\s+)?(?:terdapat|tercantum|disebutkan|dijelaskan)\s+(?:dalam|di)\s+"
    r"(?:definisi|informasi|data|fakta)(?:\s+dan\s+(?:hubungan|fakta|definisi))?\s+yang\s+(?:diberikan|tersedia)" +
    r"|\b(?:berdasarkan|menurut)\s+(?:informasi|konteks|data)(?:\s+yang\s+(?:diberikan|tersedia))?"
    r"(?:\s+(?:tersebut|ini|di atas))?\s*,\s*"
    r"|\bdalam\s+konteks\s+(?:tersebut|ini|di atas|yang diberikan)\s*,\s*",
    re.I)


def _strip_meta_phrases(answer: Text) -> Text:
    out = _META_PHRASE_RE.sub("", answer)
    if out == answer:
        return answer
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"[ \t]+([.,:;])", r"\1", out)
    # a sentence that began with the cut phrase starts with a capital again
    return re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)


def _llm_context(enriched: List[Dict[str, Any]], with_relationships: bool = True,
                 only_predicates: Optional[set] = None,
                 keep_to: Optional[set] = None) -> List[Dict[str, Any]]:
    """What the synthesis LLM sees: each term's definition plus its graph edges
    as directed sentences. Raw ids, labels and predicate names stay out -- they
    leaked into answers as "BAGIAN_DARI"/"upacara_palebon_ngaben"-style tokens and
    let the model guess edge direction. `e["facts"]` (facts.jsonl) are the same edges
    as the relationships, so they are not repeated. `aspect_facts` are the text-only
    attributes of the asked aspect (set by _synthesize); when an entity has any edge
    or attribute of that aspect, its other edges are dropped. `keep_to` (a relation
    question about 2+ terms, from _link_filter) keeps only the edges to those ids."""
    out = []
    for e in enriched:
        rels = []
        rs = (e.get("relationships") or []) if with_relationships else []
        aspect_facts = e.get("aspect_facts") or []
        if only_predicates and (aspect_facts or any(r.get("relation") in only_predicates for r in rs)):
            rs = [r for r in rs if r.get("relation") in only_predicates]
        if keep_to is not None:
            rs = [r for r in rs if r.get("target_id") in keep_to and r.get("target_id") != e["id"]]
        n_child_defs = 0
        for r in rs:
            item = {"fact": r.get("statement") or f"{e['name']} -- {r.get('target')}"}
            # capped so a hub's plain "apa itu X" prompt stays short (CPU-bound Ollama)
            if r.get("target_definition") and n_child_defs < _CHILD_DEF_CAP:
                item["target_definition"] = f"{r['target']}: {r['target_definition']}"
                n_child_defs += 1
            rels.append(item)
        item = {"term": e["name"], "definition": e["definition"], "relationships": rels}
        if aspect_facts:
            item["facts"] = aspect_facts
        if e.get("aliases"):
            item["also_called"] = e["aliases"]
        out.append(item)
    return out


def _synthesize(user_msg: Text, enriched: List[Dict[str, Any]], tracker: Optional[Tracker] = None) -> str:
    """Step 4: synthesize a natural Indonesian answer from `enriched`, with a
    deterministic guard against the local LLM refusing/hedging on context it was
    actually given (observed directly in conersation.md for terms that HAD
    resolved successfully -- e.g. ngeroras, naga banda, tirte, panca maha butha)."""
    # A word-meaning question is answered from definitions alone: with the edges
    # in context too, the small model kept listing them ("pitra berwujud sekah
    # kangsen, menerima daksina tapakan ...") instead of saying what the words mean.
    word_meaning = bool(_WORD_MEANING_RE.search(user_msg))
    aspect_preds = _aspect_predicates(user_msg)
    # the text-only attributes of the asked aspect (a word-meaning question gets the
    # literal meaning / word origin ones); none for a plain "apa itu X"
    attr_preds = PREDICATE_FAMILIES["asal_kata"] if word_meaning else aspect_preds
    content = get_content()
    for e in enriched:
        e["aspect_facts"] = content.attribute_sentences(e["id"], attr_preds) if attr_preds else []
    # None also when nothing links the terms: the full edge lists stay, and rule 18
    # (which says the shown edges ARE the links) is left out
    link_to = _link_filter(enriched) if len(enriched) >= 2 and _RELATION_Q_RE.search(user_msg) else None
    raw_context = json.dumps(_llm_context(enriched, with_relationships=not word_meaning,
                                          only_predicates=aspect_preds, keep_to=link_to),
                             indent=2, ensure_ascii=False)

    synth_sys_prompt = """
    You are a knowledgeable, factual assistant for the Balinese Ngaben ceremony.

    RULES:
    1. Answer ONLY the user's question, using the provided knowledge-base context. Each entry has a 'term', its 'definition', optional 'also_called' (other names for the term), and 'relationships' -- each relationship is a 'fact' sentence (already in the correct direction; never reverse it) and sometimes a 'target_definition' explaining the other term.
    2. Keep the answer focused. Do not append a separate description of every term in the context when the question does not ask for it. For "apa hubungan X dan Y", state how X and Y are related in a few sentences -- do not re-describe X and Y one by one afterwards.
    3. You may connect facts logically, but DO NOT invent facts, lore, examples, or definitions that are missing from the context. Never list example items, categories, or sub-types unless those exact items appear in the context. If a relationship has no 'target_definition', do NOT invent a description, symbolism, or function for that other term -- just name it.
    4. If a term has a non-empty 'definition' or 'relationships', you MUST use them -- never claim that information about it is missing.
    5. Only if the context lacks the answer entirely, reply: "Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data."
    6. Answer in natural, fluid Indonesian; keep Balinese and Sanskrit ritual terms, but never use English words (no "ceremony", "the", "and"). Do not start sentences with "Dalam konteks Ngaben" -- the whole conversation is already about Ngaben. Never mention "data", "JSON", "konteks", or "basis data" unless using rule 5, and never refer to where the facts came from (no "dalam konteks tersebut", "seperti yang tercantum", "berdasarkan informasi yang diberikan").
    7. Relationship wording: "termasuk salah satu jenis" means a type/variant, "adalah bagian dari" means a stage or part, and "sama dengan" / "dikenal sebagai" mean another name for the same thing. Never call a type a "tahap", never call a stage a "jenis", and never list types or stages as "sebutan lain" (other names).
    8. For "apa itu X", give X's definition in full substance; if X is a group or set, name every member listed in its definition or in its "termasuk salah satu jenis X" facts.
    9. If the user asks to explain each ("setiap"/"masing-masing"/"semua") item or element of something, give each item that has a 'target_definition' its own short explanation from that 'target_definition'.
    10. If the user asks about one specific aspect (e.g. HOW something is done) and the context only covers a different aspect, give what IS available and say plainly that the specific aspect is not detailed -- do not restate the same facts as if they answered it.
    """

    if _COMPOSITION_Q_RE.search(user_msg):
        # "soda dilengkapi apa?" means every component, not only the edge whose verb
        # happens to match the question (the model answered just "canang sari")
        synth_sys_prompt += (
            "\n    13. The user asks what the term consists of / contains / is completed with. "
            "List EVERY component from the facts that say 'berupa', 'berisi', 'terdiri dari', "
            "'dilengkapi', 'diisi dengan', 'terbuat dari' or 'disertai' -- all of them, not only "
            "the one whose verb matches the question. Describe a component only with its "
            "'target_definition'.\n")

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
            "tahapan'), list those numbered stages first, in that order and with those numbers; then "
            "name the other parts in one separate sentence, without numbers. Never give a stage a "
            "number its own definition does not state. A term 'dilakukan setelah' the asked term comes "
            "after it, not inside it. A 'jenis' or 'tingkatan' (type or level) is never a stage.\n")
    if _KINDS_Q_RE.search(user_msg):
        # "jenis ngaben" dropped asti wedana and pinned svasta's "sama dengan Asti Wedana"
        # on sawa wedana
        synth_sys_prompt += (
            "\n    16. The user asks for the types. List EVERY term that 'termasuk salah satu jenis' the "
            "asked term, each once, and describe each only with its own 'target_definition' -- never "
            "move a fact from one type to another.\n")
    if _COMPARE_Q_RE.search(user_msg):
        # "ngangsen ... mengangkat status pitra" -- its definition says the status is NOT
        # changed; "ngerorasin ... tanpa tujuan ..." was invented as the contrast
        synth_sys_prompt += (
            "\n    17. The user asks how terms differ. State only differences the facts show. A fact given "
            "for one term only is not evidence that the other term lacks it or does the opposite. Keep "
            "each fact's meaning exactly: never turn 'belum' or 'tidak' into its opposite.\n")
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

    # Ask the synthesis model about the canonical name. Shown "apa itu lingga sarira"
    # beside an entry named "suksma sarira", it wrote "lingga sarira termasuk salah
    # satu jenis suksma sarira" -- even when told the two are one thing (2026-09-25).
    # The answer still opens with "<asked name> adalah sebutan lain untuk <name>" (below).
    synth_q = user_msg
    for e in enriched:
        if e.get("asked_as"):
            synth_q = re.sub(re.escape(e["asked_as"]), e["name"], synth_q, flags=re.I)

    synth_user_prompt = f"Pertanyaan: {synth_q}\nKonteks:\n{raw_context}"

    try:
        answer = llm.invoke([
            SystemMessage(content=synth_sys_prompt),
            HumanMessage(content=synth_user_prompt)
        ]).content
    except Exception as e:
        # Ollama down/unreachable/timed out -- fall back to the pure-Python
        # answer instead of crashing the action and leaving the user with no
        # reply at all.
        print(f"LLM synthesis error: {e}")
        return _deterministic_answer(enriched)

    if _has_grounding(enriched):
        if _has_refusal_signal(answer):
            _log_refusal(user_msg, enriched, answer)
            answer = _deterministic_answer(enriched)
        elif _has_fabrication_signal(answer, enriched):
            _log_fabrication(user_msg, enriched, answer)
            answer = _deterministic_answer(enriched)

    answer = answer.translate(_CYRILLIC_LOOKALIKES)
    answer = _strip_meta_phrases(answer)
    answer = _complete_set_members(answer, enriched)

    # the user asked by another name for the same concept -- say so, instead of
    # the "nothing more is recorded" note below, which read as a refusal after
    # "apa itu samskara" following "apa itu sangaskara" (2026-09-24)
    synonyms = [f"{e['asked_as'][:1].upper()}{e['asked_as'][1:]} adalah sebutan lain untuk {e['name']}."
                for e in enriched if e.get("asked_as")]
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

        updated_history = entity_history + [n for n in found_names if n not in entity_history]
        updated_history = updated_history[-6:]

        return [
            SlotSet("current_entity", found_names[-1] if found_names else current_entity),
            SlotSet("entity_history", updated_history),
        ]


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
            updated_history = entity_history + [n for n in found_names if n not in entity_history]
            updated_history = updated_history[-6:]
            return [
                SlotSet("current_entity", found_names[-1] if found_names else current_entity),
                SlotSet("entity_history", updated_history),
            ]

        fallback_prompt = f"""
        You are an assistant for Balinese Ngaben. A user asked: "{user_msg}", but no
        matching term was found in the knowledge base for this question.
        Answer briefly and conversationally in Indonesian. Do NOT state specific
        ritual details, names, or steps as if they were confirmed facts from the
        Ngaben knowledge base -- you have no KB context for this question. If you
        are not sure, say plainly that this detail is not recorded in the
        knowledge base rather than guessing.
        """
        try:
            answer = llm.invoke([HumanMessage(content=fallback_prompt)]).content
        except Exception as e:
            print(f"LLM fallback error: {e}")
            answer = "Maaf, saya sedang mengalami gangguan teknis. Silakan coba lagi sebentar lagi."
        dispatcher.utter_message(text=answer)
        return []
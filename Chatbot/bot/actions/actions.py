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

from kb_resolver import get_resolver
from kb_content import get_content

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
RETURN n.id AS id,
       n.name AS name,
       n.definition AS graph_definition,
       labels(n) AS labels,
       collect(DISTINCT {
         relation: type(r),
         target: m.name,
         target_id: m.id,
         target_labels: labels(m)
       })[..25] AS relationships
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
# no entity meaning on their own.
_META_TERMS = frozenset({
    "jelaskan", "jelaskanlah", "sebutkan", "coba", "tolong", "terangkan",
    "terangkanlah", "ceritakan", "jabarkan", "uraikan",
})

# Predicates whose object is a standalone child concept worth pulling its own
# definition in for (same "parent decomposes into these things" shape as
# TERMASUK_JENIS) -- see the comment at the enrichment loop in
# _extract_and_resolve for how this was found (eteh-eteh sawa's BERUPA-linked
# parts each had a real definition that was never being fetched).
# BAGIAN_DARI added 2026-09-23: the 2026-09-23 KB semantics-fix pass (how_it_works.md
# §2.10) moved several entities (mapegat, tarpana, pabersihan_mati, ...) off a false
# TERMASUK_JENIS "type of ngaben" edge onto a correct BAGIAN_DARI "stage of ngaben"
# one -- but without this, none of those get a target_definition either, so any true
# elaboration about them (e.g. answering "apa saja tahapan dalam ngaben") reads as an
# undefined-target fabrication and gets discarded by _has_undefined_target_elaboration
# below, even though it's completely correct. Confirmed live via llm_refusal_log.jsonl:
# 7+ correct answers about ngaben/sekah/pamerasan/mlaspas_kajang thrown away this way
# in one test session before this fix. DILETAKKAN_PADA/DILETAKKAN_DI and other
# location/time/actor predicates are deliberately still excluded -- same reasoning as
# the docstring below (widening those specifically causes a different, already-
# rejected problem, per the banten_teben case).
_CHILD_DEF_PREDICATES = frozenset({"TERMASUK_JENIS", "BERUPA", "TERDIRI_DARI", "BAGIAN_DARI"})

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
        for fact in e.get("facts") or []:
            vocab |= _content_words(fact)
        for rel in e.get("relationships") or []:
            vocab |= _content_words(rel.get("target"))
            vocab |= _content_words(rel.get("target_definition"))
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


def _log_undefined_target_fabrication(user_msg: str, enriched: List[Dict[str, Any]], llm_answer: str) -> None:
    _log_jsonl(_REFUSAL_LOG_PATH, {
        "kind": "llm_undefined_target_fabrication_override",
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


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# also split on newlines (2026-09-23): a numbered/bulleted list has no
# period between items ("1. X\n2. Y\n...\n\nSetiap jenis..."), so the old
# period-only split treated the whole list-plus-wrapup as ONE "sentence" --
# confirmed live (llm_refusal_log.jsonl): a correct 9-item TERMASUK_JENIS
# listing for ngaben got discarded because its one-line wrap-up sentence
# ("Setiap jenis ngaben tersebut merupakan varian atau metode...") is full of
# generic Indonesian discourse words no KB definition would ever contain,
# diluted across the whole multi-line block instead of judged on its own --
# same false-positive shape _has_fabrication_signal's 0.6->0.75 threshold
# raise already fixed once for the whole-answer check, just never applied
# here since this check works per-sentence, not per-answer.


def _undefined_target_names(enriched: List[Dict[str, Any]]) -> set:
    """Relationship targets mentioned in context with no 'target_definition' of
    their own (i.e. not in _CHILD_DEF_PREDICATES, or capped out) -- a bare name
    with nothing else about it. Confirmed live: "pering" -> banten_teben via
    DILETAKKAN_PADA carries no target_definition (banten_teben HAS a real one,
    "sajen yang diletakkan dekat lantai/kaki jenazah", it's just not fetched for
    a location predicate), and the LLM filled the gap by inventing "keranjang
    besar yang berisi berbagai bahan ritual" -- a location relation, not a
    composition one, so widening _CHILD_DEF_PREDICATES to cover it would be the
    wrong fix (and would do this for every location/time/actor relation in
    every answer); catching the invented description after the fact is more
    targeted. Same for "lembu" via bale_pamuunan's DIHUNI."""
    names = set()
    for e in enriched:
        for r in e.get("relationships") or []:
            t = r.get("target")
            if t and not r.get("target_definition"):
                names.add(t.strip())
    return names


def _has_undefined_target_elaboration(answer: Text, enriched: List[Dict[str, Any]]) -> bool:
    """True if a sentence mentioning a bare (definition-less) relationship
    target also attaches descriptive content not grounded anywhere else in
    context -- e.g. "banten teben, yang merupakan keranjang besar..." when
    nothing in the given context ever mentions a basket. Lower threshold
    than _has_fabrication_signal's whole-answer 0.75: a short invented clause
    like this gets diluted below 0.75 by the rest of an otherwise well-grounded
    answer, which is exactly why it wasn't already caught.

    Threshold raised 0.5 -> 0.65 and min-descriptive-words 3 -> 4, 2026-09-23:
    after _SENT_SPLIT_RE started splitting on newlines (so a numbered/bulleted
    list is judged item-by-item, not as one blob), 0.5 was still catching short,
    individually-true sentences whose few non-name words happened to be ordinary
    hedges/connectors absent from the narrow KB vocabulary ("mungkin memiliki
    simbolisme", "sebagai sarana ritual") -- confirmed live on otherwise-correct
    bade/naga_banda and pamerasan answers. 0.65 stays well clear of the
    banten_teben case (~1.0 ungrounded, a wholly invented clause) while no
    longer punishing a couple of ordinary filler words next to a real name."""
    bare_names = _undefined_target_names(enriched)
    if not bare_names:
        return False
    vocab = _context_vocabulary(enriched)
    for sent in _SENT_SPLIT_RE.split(answer):
        low = sent.lower()
        mentioned = [n for n in bare_names if n.lower() in low]
        if not mentioned:
            continue
        name_words: set = set()
        for n in mentioned:
            name_words |= _content_words(n)
        descriptive = _content_words(sent) - name_words
        if len(descriptive) < 4:
            continue  # too short to judge -- a bare mention isn't elaboration
        ungrounded = [w for w in descriptive if not _grounded(w, vocab)]
        if len(ungrounded) / len(descriptive) > 0.65:
            return True
    return False


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
    itself hedge or refuse the way a small local LLM sometimes does."""
    sentences = []
    for e in enriched:
        name = e.get("name") or e.get("id")
        definition = e.get("definition")
        facts = e.get("facts") or []
        if definition and definition != "Tidak ada definisi langsung":
            def_text = definition.rstrip(".")
            # kb_content.definition_facts() renders ADALAH/MERUPAKAN facts as
            # "{Subject} adalah {Object}", so `definition` is often already a
            # full "{name} adalah ..." sentence -- prepending "{name} adalah "
            # unconditionally doubles it (observed: "soda adalah Soda adalah
            # salah satu jenis banten..." in conersation.md).
            if def_text.lower().startswith(f"{name}".lower()):
                sentence = f"{def_text}."
            else:
                sentence = f"{name} adalah {def_text}."
        else:
            sentence = f"{name}:"
        if facts:
            sentence += " " + ". ".join(facts) + "."
        sentences.append(sentence)
    return " ".join(sentences)


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
    for term in raw_terms:
        m = resolver.resolve(term)
        if m:
            matches.append(m)
        else:
            unresolved.append(term)

    # Step 2b: resolve_many() deterministically splits "X dan Y"/"X vs Y"-style
    # conjunctions and resolves each side -- union in anything it catches that the
    # free-form LLM split (Step 1) silently dropped (e.g. "bade dan naga banda"),
    # without touching what Step 1's coreference-aware path already resolved.
    matched_ids = {m.id for m in matches}
    for m in resolver.resolve_many(user_msg, limit=4):
        if m.id not in matched_ids:
            matches.append(m)
            matched_ids.add(m.id)
    matches = matches[:4]

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
    graph_rows = {row["id"]: row for row in neo4j_conn.query(_GRAPH_QUERY, {"entity_ids": entity_ids})}

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
        # actually grounded in this KB's text, not the model's memory. Capped --
        # a hub entity with many children shouldn't blow up the prompt. Raised
        # 8 -> 16 2026-09-23: ngaben alone now has 8 real TERMASUK_JENIS children
        # plus 5 real BAGIAN_DARI ones (the semantics-fix pass above), so the old
        # cap of 8 was already exhausted by TERMASUK_JENIS alone, leaving every
        # BAGIAN_DARI child uncovered regardless of the predicate-set fix above.
        # 16 comfortably covers current hub entities with room to grow; qwen2.5's
        # 32k context has plenty of headroom for this many short definitions.
        n_child_defs = 0
        for r in relationships:
            if r.get("relation") in _CHILD_DEF_PREDICATES and r.get("target_id") and n_child_defs < 16:
                child_def = content.best_definition(r["target_id"])
                if child_def:
                    r["target_definition"] = child_def
                    n_child_defs += 1
        enriched.append({
            "id": m.id,
            "name": row.get("name") or m.name,
            "definition": definition or "Tidak ada definisi langsung",
            "labels": row.get("labels", []),
            "relationships": relationships,
            "facts": content.facts_for(m.id),
        })

    if unresolved:
        _log_unresolved(user_msg, unresolved, [])
        if announce_miss:
            dispatcher.utter_message(
                text=f"(Catatan: '{', '.join(unresolved)}' tidak ditemukan, melanjutkan dengan yang lain.)"
            )

    found_names = [row["name"] for row in enriched]
    return enriched, unresolved, found_names


def _synthesize(user_msg: Text, enriched: List[Dict[str, Any]], tracker: Optional[Tracker] = None) -> str:
    """Step 4: synthesize a natural Indonesian answer from `enriched`, with a
    deterministic guard against the local LLM refusing/hedging on context it was
    actually given (observed directly in conersation.md for terms that HAD
    resolved successfully -- e.g. ngeroras, naga banda, tirte, panca maha butha)."""
    raw_context = json.dumps(enriched, indent=2, ensure_ascii=False)

    synth_sys_prompt = """
    You are a knowledgeable, factual assistant for the Balinese Ngaben ceremony.

    RULES:
    1. Use the provided Neo4j Graph Data context to answer the user's question.
    2. Explain terms clearly using the 'definition', 'facts', and 'relationships' provided in the JSON.
    3. You may synthesize and connect relationships logically, but DO NOT invent or fabricate external facts, lore, examples, or definitions that are missing from the context. This includes NEVER listing example items, categories, or sub-types (e.g. "seperti bunga, perhiasan, pakaian, ...") unless those exact items appear in the given 'definition' or 'facts'. This also applies per relationship target: if a 'relationships' entry has no 'target_definition', do NOT invent a description, symbolism, or function for it (e.g. do not claim it "symbolizes protection" or "is a cloth that covers the corpse") -- just name it, or say its meaning is not recorded.
    4. If an entity in the JSON has a non-empty 'definition' or non-empty 'facts', you MUST use it to answer -- never claim that information about it is missing.
    5. Only if the provided data lacks the answer entirely (every relevant entity has no definition and no facts), reply: "Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data."
    6. Answer in natural, fluid Indonesian.
    7. If the user asks to explain "setiap"/"masing-masing"/"semua" (each/every) item of something, and 'relationships' contains entries with their own 'target_definition', give each such entry its own short explanation using that 'target_definition' -- not one vague summary covering several at once. For an entry with no 'target_definition', follow rule 3 (name only, no invented description).
    8. If the user asks about one specific aspect of something (e.g. HOW it is used/works, not just when or where), and the available 'definition'/'facts' only cover a different aspect, give what IS available but explicitly say the specific aspect asked about is not detailed in the available data -- do not restate the same available facts as if they directly answered the question.
    """

    synth_user_prompt = f"User Question: {user_msg}\nGraph Data:\n{raw_context}"

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
        elif _has_undefined_target_elaboration(answer, enriched):
            _log_undefined_target_fabrication(user_msg, enriched, answer)
            answer = _deterministic_answer(enriched)

    if tracker is not None and _is_near_repeat(answer, _last_bot_utterance(tracker)):
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
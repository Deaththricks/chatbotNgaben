"""Custom actions for the GraphRAG Ngaben bot: Neo4j + the curated KB, templates for simple
questions, and Qwen on Groq for the rest.

Map, in file order (helpers sit near their first user, so look a name up rather than a section):
  the LLM call (_llm_invoke) and the graph (neo4j_conn)
  shared helpers: the conversation, the logs, the refusal / fabrication / English checks, _deterministic_answer,
    what the user reads (_present: the miss wording, every action's last step) and the asked name (_in_asked_names)
  steps 1-3, which terms the question is about: _mentioned_terms (the message's own words), then
    _extract_and_resolve and its steps (_needs_extraction ... _enrich)
  what the question asks: the *_Q_RE patterns, _aspect_families / _aspect_predicates (PREDICATE_FAMILIES)
  the context the model gets: _class_filter, _stage_sarana_facts, _link_filter, _llm_context, _fit_context
  answer checks (_drop_*, _fix_*, _complete_*, _trim_*, _strip_*) and code answers (_*_answer), interleaved
  step 4, the answer: _synthesize and its steps (_read_question ... _closing_notes), then _tidy_answer
  templates for simple questions: _template_route decides, _template_answer answers (_TEMPLATES)
  the Rasa actions: ActionGraphRAG, ActionTemplateAnswer, ActionLLMFallback, ActionSapa, ActionPamit, ActionBotChallenge,
  ActionOutOfScope

Where to add:
  a template: a _template_<aspect>(family, enriched, user_msg) function, listed in _TEMPLATES
  a code answer (no LLM): a function returning the answer or None, in the chain in _code_answer
  an answer check: a _drop_ / _fix_ / _complete_ function, called from _answer_checks at its place in the order
    (batch_ask.py logs which checks changed an answer by those name prefixes)
  a prompt rule: in _synthesis_rules, under the condition for its question shape
  a change to how a miss reads: a rule in _PRESENT_RULES (the checks keep detecting "belum tercatat")"""
from dataclasses import dataclass
import functools
import os
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Text, Optional, Tuple

from dotenv import find_dotenv, load_dotenv
from groq import Groq
from neo4j import GraphDatabase
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein


load_dotenv(find_dotenv())


# =====================================================================================================================
# KB access (2026-11-13: moved here from kb_resolver.py and kb_content.py, unchanged but for the names that clashed:
# the resolver's _norm, _ASPECT_WORDS, _SUFFIXES are _res_norm, _RES_ASPECT_WORDS, _RES_SUFFIXES, the content
# layer's _norm is _content_norm). KB_DIR (.env) is read from Chatbot/bot, as before.
# =====================================================================================================================
_KB_DIR = (Path(__file__).resolve().parent.parent / os.getenv("KB_DIR", "../../Graphing/kb")).resolve()


# =====================================================================================================================
# The resolver: a user's wording -> a KB entity id (was kb_resolver.py)
# =====================================================================================================================
# Resolve a user's free-text wording to a canonical KB entity id.
#
# Mirrors the resolution pipeline documented in Graphing/kb/methodology.md and the
# `fuzzy_match_*` helpers in the reference bot, but Python-side (the graph does not
# store aliases in a queryable way).
#
# Order: exact (name/alias) -> force_merge -> modifier-strip retry -> orthographic
# key -> token-checked rapidfuzz.

_WS = re.compile(r"\s+")
# Regex alternation tries branches left-to-right and commits to the first one that
# matches -- it does NOT prefer the longest match. Every multi-word "apa ..." branch
# below must come BEFORE the bare "apa(kah)?" branch, or "apa(kah)?" always wins first
# and silently leaves the rest ("itu", "arti dari", "sih", ...) stuck on the front of
# the term (e.g. "apa itu depa" -> "itu depa" instead of "depa").
_QUESTION_LEAD = re.compile(
    r"^(apa itu|apa yang dimaksud( dengan)?|apa arti kata dasar( dari)?|arti kata dasar( dari)?|"
    r"kata dasar( dari)?|apa arti( dari| kata)?|apa sih|"
    r"apa maksud(nya)?|apa(kah)?|arti|artinya|makna|maksud(nya)?|definisi|"
    r"tolong jelaskan|jelaskan|sebutkan|kasih tahu|coba jelaskan|mau tahu( arti)?)\s+",
    re.IGNORECASE,
)
_QUESTION_TAIL = re.compile(
    r"\s+(itu( apa)?|adalah|apa( ya| sih)?|maksudnya( apa| gimana)?|dong|ya|yg|"
    r"dalam ngaben|pada upacara ngaben|di ngaben)\s*[?.!]*$",
    re.IGNORECASE,
)


def _res_norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip().lower()).strip(" ?.!,")


# Romanized Balinese/Sanskrit terms are spelled several ways in the corpus and by
# users (bhuta/butha/buta, tirtha/tirta, citta/cita, bhuwana/bhuana, ç/s). The
# orthographic key collapses those so a spelling variant resolves exactly instead
# of falling through to fuzzy matching, which is where the wrong-entity hits came
# from (2026-09-24: "butha kala" -> nothing, "bhuta kala" -> bhuta).
_ASPIRATES = (("bh", "b"), ("dh", "d"), ("th", "t"), ("sh", "s"), ("kh", "k"),
              ("gh", "g"), ("ph", "p"), ("jh", "j"), ("ch", "c"))


def _ortho_token(s: str) -> str:
    s = s.lower().replace("ç", "s")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]", "", s)
    for a, b in _ASPIRATES:
        s = s.replace(a, b)
    s = s.replace("uwa", "ua")
    return re.sub(r"(.)\1+", r"\1", s)


def _ortho_key(s: str) -> str:
    return "".join(_ortho_token(t) for t in re.split(r"[\s\-/]+", s or ""))


# Indonesian affixes a user may tack onto a known term ("sodaan", "pitranya").
_RES_SUFFIXES = ("nya", "an", "kan", "i")
# Head words that only say what kind of thing a term is -- a query may carry them
# without the entity name doing so ("upacara pamerasan" -> pamerasan) and vice versa.
_HEAD_WORDS = {"upacara", "prosesi", "ritual", "acara", "istilah", "konsep", "kata",
               "sarana", "banten"}
# Aspect words a query may wrap around a term ("kelengkapan sodaan", "unsur tri
# sarira", "fungsi kawangen") -- ignored on the query side only.
_RES_ASPECT_WORDS = {"kelengkapan", "kelengkapannya", "unsur", "unsurnya", "bagian",
                 "bagiannya", "fungsi", "fungsinya", "makna", "maknanya", "arti",
                 "artinya", "isi", "isinya", "jenis", "jenisnya", "tahapan", "tahapannya",
                 "simbol", "lambang", "tujuan", "tujuannya", "asal", "asalnya"}


_VOWELS = frozenset("aeiou")


def _vowel_edit(a: str, b: str) -> bool:
    """True if a and b differ by exactly one vowel (substituted, inserted or dropped)."""
    ops = list(Levenshtein.editops(a, b))
    if len(ops) != 1:
        return False
    op = ops[0]
    if op.tag == "replace":
        return a[op.src_pos] in _VOWELS and b[op.dest_pos] in _VOWELS
    if op.tag == "delete":
        return a[op.src_pos] in _VOWELS
    return b[op.dest_pos] in _VOWELS


def _token_match(a: str, b: str, anchored: bool = True, common: bool = False, named: bool = False,
                 kbword: bool = False) -> bool:
    """Symmetric. The flags describe the user's word: `common`, an everyday Indonesian
    word, matches only as written (plus a suffix), never through an edit; `named`, a word
    of some KB name, is a real word too -- only a vowel slip (spelling variant) may change
    it: "kahang" (naga kahang) is not kajang, "tunjung" not punjung (2026-10-01).
    `kbword`, a word the KB's own text uses (KbResolver.kb_words), is as strict unless another
    word of the phrase matched exactly: alone, "tumpang" is no tumpeng nor "hidung" kidung;
    beside "sredaning", "citra" is the user's slip for sredaning cita."""
    oa, ob = _ortho_token(a), _ortho_token(b)
    if oa == ob:
        return True
    for suf in _RES_SUFFIXES:
        if len(ob) >= 4 and oa == ob + suf:
            return True
        if len(oa) >= 4 and ob == oa + suf:
            return True
    # a Balinese "-ang" verb in its colloquial Indonesian "-in" form: "nyiramin layon" is
    # nyiramang layon (Tier B 2026-10-02), "malebuin" malebuang
    for x, y in ((oa, ob), (ob, oa)):
        if x.endswith("ang") and len(x) >= 8 and y == x[:-3] + "in":
            return True
    # "kalangan" is not a typo of karangan, nor "bayi" of bayu (live crosscheck 2026-09-30)
    if common or kbword and not anchored:
        return False
    # One-edit typos: "wah loka"/"bwah loka", "sredaning citra"/"sredaning cita",
    # "sulinggi"/"sulinggih". A consonant slip on a word under 6 letters only counts when
    # another word of the phrase matched exactly (`anchored`): alone, peras/perak,
    # sisir/sisig, sabun/sabuk, sekar/sekah are different words (2026-09-29). A vowel slip
    # (nglungah/ngelungah, tirte/tirta) is a typo either way. "pandawa"/"pranawa"
    # (2 edits) and "surya"/"sukra" never match.
    short = min(len(oa), len(ob))
    if short >= 3 and Levenshtein.distance(oa, ob) <= 1:
        if named:
            return _vowel_edit(oa, ob)
        return anchored or short >= 6 or _vowel_edit(oa, ob)
    return not named and short >= 6 and fuzz.ratio(oa, ob) >= 88 and (anchored or short >= 8)


# Everyday Indonesian words (lowercase tokens seen 3+ times in a general Indonesian NER
# corpus of ~600k tokens). Read only; the file is shared with the Graphing pipeline.
_COMMON_WORDS_FILE = _KB_DIR.parent / "data" / "20k_mdee_gazz.txt"


# Question words are everyday words too, but that formal corpus lacks the informal ones:
# "kenapa" went through the typo rule to kelapa (Tier B 2026-10-02, "hari apa yang harus
# dihindari untuk ngaben dan kenapa?").
_QUESTION_WORDS = frozenset({"apa", "apakah", "siapa", "kapan", "kenapa", "mengapa", "bagaimana",
                             "gimana", "dimana", "kemana", "darimana", "mana", "berapa", "bilamana"})
# chat words of a question, which the formal corpus lacks: "kopi tuh apaan", "coba jelasin X dong", "kasih tau
# dong X itu apa" read them as unknown words and went to the LLM instead of the definition template (15 such
# questions of the 1,864 NLU examples, LLM comparison 2026-10-20)
_CHAT_WORDS = frozenset({"apaan", "tuh", "sih", "dong", "deh", "jelasin", "jelasken", "kasih", "tau", "kasitau",
                         "coba", "nih", "yah", "ya", "kak", "min",
                         # everyday spellings: "kalau di desa cuma ada pemangku, ngabennya tetep bisa jalan gak?"
                         # read cuma / tetep as rare words no rule could be about (#1861)
                         "cuma", "tetep", "udah", "kalo", "pas", "gak", "nggak", "ngga", "enggak", "aja", "emang",
                         "banget", "gitu", "gini", "bikin", "kayak", "abis", "sampe", "gimana", "dibuatin"})


def _load_common_words(path: Path = _COMMON_WORDS_FILE, min_count: int = 3) -> frozenset:
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            tok = line.split(maxsplit=1)[0] if line.strip() else ""
            if tok.isalpha() and tok.islower():
                counts[tok] = counts.get(tok, 0) + 1
    return frozenset(w for w, c in counts.items() if c >= min_count) | _QUESTION_WORDS | _CHAT_WORDS


@dataclass
class Match:
    id: str
    name: str
    via: str          # "exact" | "alias" | "force_merge" | "strip" | "ortho" | "typo" | "fuzzy"
    score: float      # 0-100 (100 for non-fuzzy)
    entity: dict


class KbResolver:
    def __init__(self, kb_dir: Path = _KB_DIR):
        self.kb_dir = kb_dir
        ents = json.loads((kb_dir / "output" / "entities.json").read_text(encoding="utf-8"))
        self.by_id: dict[str, dict] = {e["id"]: e for e in ents}

        res = json.loads((kb_dir / "tuning" / "entity_resolution.json").read_text(encoding="utf-8"))
        self.strip_modifiers: list[str] = [w.lower() for w in res.get("strip_modifiers", [])]
        self.keep_distinct: set[str] = {_res_norm(w) for w in res.get("keep_distinct", [])}
        # Generic/ambiguous entities (see entity_resolution.json's _exclude_note) that
        # must never be served as an answer, even on an exact-name match -- kept in
        # entities.json/the graph, just never surfaced by the bot.
        self.excluded_ids: set[str] = set(res.get("exclude_from_resolution", []))
        excluded_ids = self.excluded_ids

        # surface form -> id
        self.surface: dict[str, str] = {}
        self.alias_surface: set[str] = set()
        for e in ents:
            if e["id"] in excluded_ids:
                continue
            self.surface.setdefault(_res_norm(e["name"]), e["id"])
            for a in e.get("aliases", []):
                key = _res_norm(a)
                if key and key not in self.surface:
                    self.surface[key] = e["id"]
                    self.alias_surface.add(key)

        # force_merge values are canonical entity *names* (build_kb.py's contract).
        # This used to look them up as ids, so every multi-word target ("naga
        # banda", "upacara ngelungah", ... 43 of 93) silently never resolved here.
        self.force_merge: dict[str, str] = {}
        for k, v in res.get("force_merge", {}).items():
            if k.startswith("_"):
                continue
            _id = self.surface.get(_res_norm(v)) or (v if v in self.by_id else None)
            if _id and _id not in excluded_ids:
                self.force_merge[_res_norm(k)] = _id

        # orthographic key -> id; a key shared by two different entities is
        # ambiguous and never resolves through this tier.
        self.ortho: dict[str, Optional[str]] = {}
        for key, _id in list(self.surface.items()) + list(self.force_merge.items()):
            ok = _ortho_key(key)
            if ok in self.ortho and self.ortho[ok] != _id:
                self.ortho[ok] = None
            else:
                self.ortho.setdefault(ok, _id)

        # long keys for the whole-key one-edit tier ("pancahmaha butha" -> pancamahabutha:
        # the extra letter sits across a word boundary the token check cannot see)
        self._long_keys = [k for k, v in self.ortho.items() if v and len(k) >= 8]

        # a common word that is itself a KB name token ("air", "kain") still matches as
        # written; the set only stops it from matching another name through an edit
        self.common_words = _load_common_words()
        self.name_tokens = {_ortho_token(t) for s in self.surface for t in re.split(r"[\s\-/]+", s) if t}
        # Words the KB's own definitions use (2+ times, 5+ letters) are real words of this domain,
        # like everyday ones: as written only, never through an edit. The everyday list is a formal
        # Indonesian corpus and lacks them, so "tumpang" (bade's tiers) went to tumpeng, a rice
        # cone (2026-10-07 batch); of 674 such words 15 resolved alone to another term that way --
        # hidung -> kidung, gulungan -> galungan, pinggang -> pinang, kolong -> kojong, kipas -> kapas.
        kb_counts: dict[str, int] = {}
        for e in ents:
            for w in re.findall(r"[a-zA-Z]+", e.get("definition") or ""):
                if len(w) >= 5:
                    o = _ortho_token(w)
                    kb_counts[o] = kb_counts.get(o, 0) + 1
        self.kb_words = frozenset(w for w, n in kb_counts.items() if n >= 2)

        self._choices = list(self.surface.keys())
        # fuzzy candidates are also drawn by orthographic key, so heavy spelling
        # variation ("ssoddaan", "butha") still reaches the token check below
        self._ortho_choices: dict[str, str] = {}
        for key in self._choices:
            self._ortho_choices.setdefault(_ortho_key(key), key)

    # -- helpers ---------------------------------------------------------------
    def _strip_modifiers(self, s: str) -> str:
        toks = s.split()
        changed = True
        while changed and len(toks) > 1:
            changed = False
            if toks[0] in self.strip_modifiers:
                toks = toks[1:]
                changed = True
            if len(toks) > 1 and toks[-1] in self.strip_modifiers:
                toks = toks[:-1]
                changed = True
        return " ".join(toks)

    def clean_query(self, text: str) -> str:
        """Peel a question wrapper off ('apa itu X' -> 'x')."""
        s = _res_norm(text)
        prev = None
        while prev != s:
            prev = s
            s = _QUESTION_LEAD.sub("", s)
            s = _QUESTION_TAIL.sub("", s)
            s = s.strip(" ?.!,")
        return s

    # -- main ---------------------------------------------------------------
    def resolve(self, text: str, fuzzy_threshold: int = 78) -> Optional[Match]:
        raw = self.clean_query(text)
        if not raw:
            return None

        # 1. exact name / alias
        if raw in self.surface:
            _id = self.surface[raw]
            via = "alias" if raw in self.alias_surface else "exact"
            return Match(_id, self.by_id[_id]["name"], via, 100.0, self.by_id[_id])

        # 2. force_merge
        if raw in self.force_merge:
            _id = self.force_merge[raw]
            return Match(_id, self.by_id[_id]["name"], "force_merge", 100.0, self.by_id[_id])

        # 3. modifier-strip retry (never for keep_distinct surface forms). Retries
        # through the same two tiers as steps 1-2 above, not just the alias table --
        # e.g. "unsur unsur panca maha butha" strips down to "panca maha butha",
        # which only resolves via force_merge, not the surface/alias table; without
        # this the strip was computed but silently discarded on a force_merge-only
        # target.
        if raw not in self.keep_distinct:
            stripped = self._strip_modifiers(raw)
            if stripped and stripped != raw:
                if stripped in self.surface:
                    _id = self.surface[stripped]
                    return Match(_id, self.by_id[_id]["name"], "strip", 100.0, self.by_id[_id])
                if stripped in self.force_merge:
                    _id = self.force_merge[stripped]
                    return Match(_id, self.by_id[_id]["name"], "strip", 100.0, self.by_id[_id])

        # 4. orthographic key (spelling variants: butha/bhuta, tirta/tirtha, ...),
        # on the raw form and on the modifier-stripped form.
        for form in (raw, self._strip_modifiers(raw)):
            _id = self.ortho.get(_ortho_key(form))
            if _id:
                return Match(_id, self.by_id[_id]["name"], "ortho", 100.0, self.by_id[_id])

        # 4a. a possessive "-nya" on a known name ("harganya" -> harga): fuzzy matching
        # never sees force_merge keys, so "kenapa tirtha ada harganya" missed harga tirtha
        if raw.endswith("nya") and len(raw) >= 6:
            base = raw[:-3]
            _id = self.surface.get(base) or self.force_merge.get(base)
            if _id:
                return Match(_id, self.by_id[_id]["name"], "strip", 100.0, self.by_id[_id])

        # 4a'. the pe(ng)-/pa(ng)- noun of an ng- rite name: "pengaben" and "pengabenn" (pengabenan, typed short) found
        # nothing -- 8 letters, below the typo tier (user's live session, 2026-11-10). One word, and only onto a name.
        if " " not in raw:
            nm = re.fullmatch(r"p[ae]ng(\w{3,}?)(?:an)?", _ortho_key(raw))
            _id = nm and self.ortho.get(_ortho_key("ng" + nm.group(1)))
            if _id:
                return Match(_id, self.by_id[_id]["name"], "strip", 100.0, self.by_id[_id])

        # 4b. one edit on the whole orthographic key of a long name, if it is unique.
        # "typo", not "ortho": the bot must not call a misspelling "sebutan lain".
        # From 9 letters: "pegabenan" (pengabenan, a force_merge key the fuzzy tier never
        # sees) got "Mungkin maksud Anda: ngaben, benang?" (2026-10-02)
        # A 9-letter word must also keep both ends ("petilasan" is no patulangan).
        # A 9-letter word that is a 10-letter key with its last letter missing counts too: "pengabena" (pengabenan) found
        # nothing (user's live session, 2026-11-10).
        key = _ortho_key(raw)
        if len(key) >= 9 and raw not in self.common_words:
            hits: dict[str, str] = {}
            for k in self._long_keys:
                if (abs(len(k) - len(key)) <= 1 and Levenshtein.distance(k, key) <= 1
                        and (len(key) >= 10 or (k[:2] == key[:2] and k[-2:] == key[-2:])
                             or (len(k) == len(key) + 1 and k.startswith(key)))):
                    hits.setdefault(self.ortho[k], k)
            if len(hits) == 1:
                _id, k = next(iter(hits.items()))
                if not self._edit_in_common_word(raw, key, k):
                    return Match(_id, self.by_id[_id]["name"], "typo", 100.0, self.by_id[_id])

        # 5. fuzzy, token-checked. A string-level score alone produced confident
        # wrong answers (2026-09-24): "surya" -> sukra, "sangaskara" ->
        # putru_sangaskara, "bhuta kala" -> bhuta, "panca budhindrya" ->
        # panca_datu, "upacara palebon" -> nyiramang_layon, "ida sang hyang widhi
        # wasa" -> ida_sang_sadaka. A candidate now only counts when every
        # content token on each side has a close counterpart on the other side
        # (typos and spelling variants still pass: "perhiasasn", "budhaindrya",
        # "sredaning citra", "sodaan") -- an extra or a missing word is a
        # different thing, not a typo.
        cands = {c: s for c, s, _ in process.extract(raw, self._choices, scorer=fuzz.WRatio, limit=10)}
        for okey, s, _ in process.extract(_ortho_key(raw), list(self._ortho_choices), scorer=fuzz.WRatio, limit=10):
            c = self._ortho_choices[okey]
            cands[c] = max(cands.get(c, 0), s)
        best = None
        for cand, score in cands.items():
            if score < fuzzy_threshold - 8 or not self._tokens_cover(raw, cand):
                continue
            if best is None or score > best[1]:
                best = (cand, score)
        if best:
            _id = self.surface[best[0]]
            return Match(_id, self.by_id[_id]["name"], "fuzzy", float(best[1]), self.by_id[_id])

        return None

    def _edit_in_common_word(self, raw: str, key: str, k: str) -> bool:
        """The whole-key typo tier's one edit falls inside an everyday word of the query, and no
        rare word anchors the phrase: the phrase-level check above only asks whether the whole
        phrase is common, so "kepada jenazah" became kepala jenazah, the corpse's head (2026-10-07
        batch) -- both words everyday. Beside a word only that name has, the everyday word is the
        user's slip: "sredaning citra" is sredaning cita. An edit at a word boundary counts only
        when both words it touches are everyday ones. Not when the other words are a KB name as written:
        "ngaben mahal gak" is Ngaben and "mahal", and became ngaben massal (style test 2026-11-07)."""
        spans, pos = [], 0
        toks = [t for t in re.split(r"[\s\-/]+", raw) if t]
        for t in toks:
            o = _ortho_token(t)
            spans.append((pos, pos + len(o), t))
            pos += len(o)
        for op in Levenshtein.editops(key, k):
            p = op.src_pos
            touching = [t for a, b, t in spans if a <= p < b or (op.tag == "insert" and p == b)]
            rest = [t for t in toks if t not in touching]
            if (touching and all(t in self.common_words for t in touching)
                    and (all(t in self.common_words for t in rest) or " ".join(rest) in self.surface)):
                return True
        return False

    @staticmethod
    def _content_tokens(s: str, skip: set) -> list[str]:
        """The words of `s` that say what it is. A reduplicated word ("para-para", "balung-balung")
        is one lexical word, kept even when its half is a modifier: split on the hyphen, "para"
        was dropped as the plural marker, so "para-para tempat pembakaran" reduced to
        "pembakaran" and took every "upacara pembakaran jenazah" (2026-10-07 batch). A
        reduplicated modifier written whole ("unsur-unsur", "masing-masing") is still skipped."""
        out = []
        for w in re.split(r"[\s/]+", s):
            if not w or w in skip:
                continue
            parts = [p for p in w.split("-") if p]
            if len(parts) == 2 and parts[0] == parts[1]:
                out.append(parts[0])
            else:
                out.extend(p for p in parts if p not in skip)
        return out

    def _tokens_cover(self, query: str, cand: str) -> bool:
        skip = set(self.strip_modifiers) | _HEAD_WORDS
        q = self._content_tokens(query, skip | _RES_ASPECT_WORDS)
        c = self._content_tokens(cand, skip)
        if not q or not c:
            return False
        anchored = len(q) >= 2 and any(_ortho_token(a) == _ortho_token(b) for a in q for b in c)
        common, named, kb = self.common_words, self.name_tokens, self.kb_words
        flags = {a: (a in common, _ortho_token(a) in named, _ortho_token(a) in kb) for a in q}
        return (all(any(_token_match(a, b, anchored, *flags[a]) for b in c) for a in q)
                and all(any(_token_match(a, b, anchored, *flags[a]) for a in q) for b in c))

    def resolve_many(self, text: str, limit: int = 2, fuzzy_threshold: int = 80) -> list[Match]:
        """Resolve every distinct term mentioned in a phrase (for 'beda X dan Y').

        Splits on common Indonesian conjunctions, resolves each side, dedups by id.
        """
        raw = self.clean_query(text)

        # A compact "X/Y"-style compound entity name (e.g. "Sulinggih/Griya",
        # "Slepa/Peti") must stay one term even if the user adds spaces around the
        # slash -- try the whole phrase (slash-spacing collapsed) as a single
        # match before treating "/" as an "X or Y" separator below, which would
        # otherwise fragment it (e.g. "sulinggih / griya" -> the wrong entities
        # "sulinggih" + a fuzzy hit for "griya" instead of "sulinggih_griya").
        # Only accept an exact/alias/force_merge/strip whole-phrase match here, not
        # "fuzzy" -- a longer 3+ term phrase (e.g. "sulinggih/griya dan tirtha")
        # can otherwise score a deceptively high WRatio against a shorter
        # candidate (the same hazard noted in resolve()'s fuzzy step above) and
        # wrongly swallow the whole phrase as one match, silently dropping the
        # other term(s) a real "X dan Y" split should have caught.
        collapsed = re.sub(r"\s*/\s*", "/", raw)
        whole = self.resolve(collapsed, fuzzy_threshold=fuzzy_threshold)
        if whole and whole.via != "fuzzy":
            return [whole]

        parts = re.split(r"\s+(?:dan|vs\.?|versus|atau|dengan|,|&|/|\bsama\b)\s+", raw)
        out: list[Match] = []
        seen: set[str] = set()
        for part in parts:
            part = part.strip(" ?.!,")
            if not part:
                continue
            m = self.resolve(part, fuzzy_threshold=fuzzy_threshold)
            if m and m.id not in seen:
                seen.add(m.id)
                out.append(m)
            if len(out) >= limit:
                break
        return out

    # 60 offered "tandri, undagi, panca budhindrya" for "dihindari" (2026-09-29)
    def suggest(self, text: str, k: int = 3, threshold: int = 75) -> list[str]:
        raw = self.clean_query(text)
        if not raw:
            return []
        hits = process.extract(raw, self._choices, scorer=fuzz.WRatio, limit=k)
        seen, out = set(), []
        for name, score, _ in hits:
            if score < threshold:
                continue
            canon = self.by_id[self.surface[name]]["name"]
            if canon not in seen:
                seen.add(canon)
                out.append(canon)
        return out


_RESOLVER: Optional[KbResolver] = None


def get_resolver() -> KbResolver:
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = KbResolver()
    return _RESOLVER


# =====================================================================================================================
# The content layers: facts, definitions, glossary, attributes, sentence templates, predicate families (was
# kb_content.py; kb_lint.py and the curation scripts import them from here)
# =====================================================================================================================
# Read-only access to the richer KB layers that are *not* in the graph in a
# convenient shape: pre-rendered fact sentences, glossary passages, text-only entity
# attributes, the predicate -> Indonesian sentence templates, and the predicate
# families that say which question aspect (makna / letak / waktu / fungsi / ...) each
# edge or attribute answers.
#
# The Neo4j graph stays the source of truth for structure (definition, type,
# broader spine, relation edges). This module adds phrasing, the glossary
# definitions, and the attributes (LITERAL facts) read from entities.json, which the
# graph query does not return.
#
# Files live in KB_DIR (.env) or ../../Graphing/kb by default -- same as the resolver above.

_CONF_RANK = {"HIGH": 0, "MED": 1, "LOW": 2}

# Question aspect -> the predicates (edges AND text-only attributes) that answer it.
# A predicate may sit in more than one family. actions.py maps question wording to a
# family and shows only that family's edges/attributes; kb_lint requires every
# attribute predicate (check 11) and every live edge predicate (check 14) to be in some
# family -- an unmapped one is dropped from every aspect question. 97 edge predicates
# were in none until 2026-09-30: "apa saja bahan untuk membuat tirta pangentas" kept 2
# of its 28 edges and lost all 18 DIPERLUKAN_UNTUK_MEMBUAT ingredients. "cara" (how / what happens) is the broadest and is used only when no other
# aspect matches; "asal_kata" serves word-meaning questions.
PREDICATE_FAMILIES: Dict[str, set] = {
    "sebutan_lain": {"SAMA_DENGAN", "DIKENAL_SEBAGAI", "ADALAH", "SEBUTAN_HALUS_UNTUK", "SEBUTAN_UNTUK"},
    "jenis": {"TERMASUK_JENIS", "CONTOH", "MEMILIKI_JENIS"},
    "tahapan": {
        "BAGIAN_DARI", "SEBELUM", "SETELAH", "DILAKUKAN_SEBELUM", "DILAKUKAN_SETELAH",
        "DILAKUKAN_MENJELANG", "DIIKUTI_OLEH",
        # added 2026-09-30
        "DIAWALI_DENGAN", "DIAKHIRI_DENGAN", "DILAKSANAKAN_SETELAH", "DILAKUKAN_DALAM", "MENJALANI",
    },
    "komposisi": {
        "BERUPA", "TERDIRI_DARI", "BERISI", "DIISI_DENGAN", "DIISI", "BERUNSUR", "MELIPUTI",
        "DILENGKAPI", "TERBUAT_DARI", "DISERTAI", "DIBUNGKUS_DENGAN", "TERMASUK_JENIS",
        "BAGIAN_DARI", "DISISIPI", "MENGANDUNG",
        # added 2026-09-30
        "DIPERLUKAN_UNTUK_MEMBUAT", "DIMASUKKAN_KE_DALAM", "DILENGKAPKAN_PADA", "DISAJIKAN_BERSAMA",
        "DISAMBUNG_DENGAN", "DIPASANG", "MEMILIKI_JENIS",
        # a sarana's base layer, binding and ornaments are parts of it too (composition tree,
        # 2026-10-01)
        "DIALASI", "DIALASI_DENGAN", "DIIKAT_DENGAN", "DIHIAS_DENGAN",
    },
    "asal_kata": {"BERASAL_DARI_KATA", "BERARTI_HARFIAH", "BERASAL_DARI", "SEBUTAN_BERASAL_DARI",
                  "MERUPAKAN_PERUBAHAN_DARI"},
    "simbol": {
        "MELAMBANGKAN", "MENYIMBOLKAN", "BERMAKNA", "BERARTI", "BERARTI_HARFIAH",
        "BERAKAR_PADA", "BERDASARKAN", "MENUNJUKKAN", "MEWUJUDKAN",
        "MERUPAKAN_PERWUJUDAN_DARI", "DIPERLAKUKAN_SEPERTI", "DIANGGAP_SEBAGAI",
        "BERSINAR_BAGAIKAN",
        # added 2026-09-30
        "BERARTI_MENYATU_DENGAN", "BERDEWA", "BERHUTANG_KEPADA", "BERKAITAN_DENGAN",
        "DINILAI_SEBAGAI", "LAHIR_DALAM_WUJUD", "MANIFESTASI_DARI", "MERUPAKAN_WUJUD_DARI",
        "PASANGAN_DARI", "SAKTI_DARI", "MENGEMBALIKAN_UNSUR_KE",
        # literal-only links promoted to edges (2026-10-02)
        "DISERTAI_KEMBALINYA_UNSUR_BADAN_KE", "MERUPAKAN_TAHAP_MENCAPAI", "MENUNJUKKAN_JALAN_ATMA_KE",
        # "ngaben adalah kewajiban suci (swadharma)", corpus L650/L653/L680 (NLU sweep 2026-10-19)
        "MERUPAKAN_KEWAJIBAN",
        # "semua alat upakara dan sesajen ... bukan hanya merupakan suatu simbol" (L1081), "belit kanan dan belit kiri
        # mengandung makna purusa dan pradana" (L858), "hal ini bermakna agar gigi ... kokoh" (L3177) -- V2 2026-11-02
        "BUKAN_HANYA_MERUPAKAN", "MENGANDUNG_MAKNA", "BERMAKNA_AGAR",
    },
    "lokasi": {
        # "bangbang rare menjadi tempat pemakaman khusus bayi pada upacara ngelungah" (2026-10-19)
        "MENJADI_TEMPAT_PEMAKAMAN_PADA",
        # "ngaben dapat dilakukan di krematorium", "jenazah disemayamkan di bale semanggen" (route audit 2026-10-27)
        "DAPAT_DILAKUKAN_DI", "DISEMAYAMKAN_DI",
        "DILETAKKAN_DI", "DILETAKKAN_PADA", "DILETAKKAN_DI_ATAS", "DILETAKKAN_MELINTANG_DI",
        "BERADA_DI", "DILAKUKAN_DI", "DIBUAT_DI", "DIADAKAN_DI", "DIHANYUTKAN_KE", "DIBAWA_KE",
        "DINAIKKAN_KE", "DIPINDAHKAN_KE", "DIPINDAHKAN_DARI", "DITURUNKAN_DI",
        "DIGANTUNGKAN_DI", "DITABURKAN_DI", "DIBARINGKAN_DI", "DIBARINGKAN_DENGAN",
        "BERSEMAYAM_DI", "BERSTANA_DI", "BERTAHTA", "DISEMAYAMKAN_DI", "MENUJU",
        "BERANGKAT_KE", "KEMBALI_KE", "DITARUHKAN_DI_SAMPING", "DITEMPELKAN_DI",
        "DIPASANG_DI_ATAS", "DIPASANG_PADA", "BERALASKAN", "DIALASI", "DIALASI_DENGAN",
        "DIMANDIKAN_DI", "DIMANDIKAN_DI_ATAS", "DIMASUKKAN_KE_DALAM", "DIMASUKKAN_MELALUI",
        "DIMOHONKAN_DI", "DIPERCIKKAN_PADA", "DIUSUNG_KE", "TIDUR_DI", "BERSELONJOR_KE",
        "MEMBELAKANGI", "DITELENTANGKAN_DI", "DITARUH_PADA_PEPAGA", "DAPAT_MEMASUKI",
        # added 2026-09-30
        "BERDAMPINGAN_DENGAN", "DIGILING_DI_ATAS", "DIHANCURKAN_DI", "DIHUNI", "DIIKAT_PADA",
        "DIOLESKAN_DI", "DIPERSILAKAN_DI", "DIPERSILAKAN_MASUK_KE", "DIPUJA_DI", "DISEMBURKAN_PADA",
        "DISTANAKAN_DI", "KEDIAMAN_DARI", "MENJADI_ALAS", "TEMPAT_MEMUJA", "TERTANAM_TITIP_DI",
        # where it is obtained from ("dari mana diperoleh"), added 2026-10-01
        "DIAMBIL_DARI", "DIMOHON_DARI", "DIMOHONKAN_DARI",
        # "raja bali berpusat di gelgel" (Balinese terms, 2026-10-28)
        "BERPUSAT_DI",
    },
    "waktu": {
        "DILAKUKAN_SAAT", "DIGUNAKAN_SAAT", "DIBUAT_SAAT", "DISEMBURKAN_SAAT",
        "DINYALAKAN_SAAT", "MENJELANG", "SEBELUM", "SETELAH", "DILAKUKAN_SEBELUM",
        "DILAKUKAN_SETELAH", "DIPERCIKKAN_SEBELUM", "TIDAK_BOLEH_DILAKUKAN_SAAT",
        "DILAKUKAN_MENJELANG", "DILAKSANAKAN", "DILAKUKAN", "DIADAKAN_JIKA",
        "DILAKUKAN_DALAM_HAL", "SYARAT", "DIGUNAKAN_SEBELUM", "DIBONGKAR_SETELAH",
        "DIBUNGKUS_SETELAH", "MENENTUKAN_WAKTU",
        # added 2026-09-30
        "DIHINDARI_UNTUK", "DIHITUNG_BERDASARKAN", "DILAKSANAKAN_BERSAMA", "DILAKSANAKAN_SETELAH",
        "DIPLASPAS_BERSAMA", "DIPUJA_PADA", "MENSYARATKAN", "MERUPAKAN_HARI_PELAKSANAAN",
        "SEPULUH_HARI_SETELAH",
        # the one order predicate missing here (2026-10-14): "kapan nyiramang layon" lost "ngulapin
        # diikuti oleh nyiramang layon" and "... diikuti oleh pangringkes"
        "DIIKUTI_OLEH",
        # the order of the sarana put into the periuk of Tirtha Pangentas (L3890-3902) and of the tirthas sprinkled on
        # the corpse (L3978) -- V2 2026-11-02
        "DIMASUKKAN_SETELAH", "DIPERCIKKAN_SAAT",
    },
    # the offerings / equipment a ceremony or stage uses (sarana upacara)
    "sarana": {
        "DIGUNAKAN_DALAM", "DIGUNAKAN_PADA", "DIGUNAKAN_SAAT", "DIGUNAKAN_UNTUK", "DIPAKAI_UNTUK",
        "MENGGUNAKAN", "MEMAKAI",
        # added 2026-09-30
        "DIPERLUKAN_UNTUK_MEMBUAT", "DILENGKAPKAN_PADA",
        # "ngaben dianggap belum dilaksanakan tanpa tirta pangentas" (2026-10-12)
        "DIANGGAP_BELUM_DILAKSANAKAN_TANPA",
    },
    "pelaku": {
        "DILAKUKAN_OLEH", "DIPIMPIN_OLEH", "DIMOHONKAN_OLEH", "DIJUNJUNG_OLEH", "DIHATURKAN_OLEH",
        "DIBUAT_OLEH", "DIMANTRAI_OLEH", "DIBASMI_OLEH", "DIUSUNG", "DIJUNJUNG",
        "DIAJAK_BERKOMUNIKASI_OLEH", "DIMOHON_DARI",
        "DIMOHONKAN_DARI", "DIAMBIL_OLEH", "DIPANGKU_OLEH", "DILAKUKAN_ANTARA",
        # added 2026-09-30
        "DIBERIKAN_OLEH", "DIGUNAKAN_OLEH", "DIPERUNTUKKAN_BAGI", "DITENTUKAN_OLEH", "HADIR_DALAM",
        "MELAKSANAKAN", "MEMBUAT",
        # "tirta pangentas hanya dapat dibuat oleh sulinggih" (2026-10-12)
        "HANYA_DAPAT_DIBUAT_OLEH",
        # "puri dihuni oleh raja bali", "setra dimiliki oleh desa adat" (Balinese terms, 2026-10-28)
        "DIHUNI_OLEH", "DIMILIKI_OLEH",
        # naga banda "dipanah oleh Ida Peranda yang muput karya" (L1681), mantra "diucapkan oleh orang yang memimpin
        # upacara" (L3252), nyiramang layon "akan melibatkan Krama Banjar" (L2427), the elder who cleans the head first
        # (L2777) -- V2 2026-11-02
        "DIPANAH_OLEH", "DIUCAPKAN_OLEH", "MELIBATKAN", "DIAWALI_OLEH",
        # nyekeh "lebih sering ditempuh keluarga raja atau pendeta" (L894): who usually holds it, not a rule (2026-11-03)
        "LEBIH_SERING_DITEMPUH_OLEH",
    },
    "fungsi": {
        "DIPAKAI_UNTUK", "DIGUNAKAN_UNTUK", "DIGUNAKAN_PADA", "DIGUNAKAN_DALAM",
        "BERFUNGSI_SEBAGAI", "BERFUNGSI_UNTUK", "BERPERAN_SEBAGAI", "BERTUJUAN_UNTUK",
        "BERTUJUAN_AGAR", "BERTUJUAN_POKOK", "BERTUJUAN_MENYUCIKAN", "DITUJUKAN_UNTUK",
        "MEWAJIBKAN", "MENGHILANGKAN", "MENGHASILKAN", "MENJAMIN", "TIDAK_MENJAMIN",
        "DIMOHON", "MEMOHON", "DIGUNAKAN_DENGAN_HARAPAN", "MENENTUKAN", "MEMPENGARUHI",
        "MENJAGA", "MEMUPUK", "MEMUNGKINKAN", "MENGAKIBATKAN", "DIJATUHKAN_KARENA",
        "BERTUGAS_MENGANGKUT", "DIPERSEMBAHKAN_KEPADA", "MELEBUR",
        "DIPAKAI_UNTUK_MEMOHON_RESTU", "MEMBERIKAN",
        # added 2026-09-30
        "DAPAT_MENCAPAI", "DIHINDARI_UNTUK", "DIMOHONKAN_AGAR_MENUJU", "DIPERSILAKAN_UNTUK",
        "DIPERUNTUKKAN_BAGI", "MELARANG", "MEMBATASI", "MENCEGAH", "MENGANGKAT",
        "MENGEMBALIKAN_UNSUR_KE", "MENGGANTIKAN", "MENJADI_ALAS", "MENSTANAKAN",
        "MENYERAHTERIMAKAN",
        # "ngaben merupakan salah satu tahap untuk mencapai moksa" (2026-10-02)
        "MERUPAKAN_TAHAP_MENCAPAI",
        # "ngaben adalah kewajiban suci (swadharma)": "apakah ngaben wajib" got "Ya" argued from tirta
        # pangentas, the only rule in its context (NLU sweep 2026-10-19)
        "MERUPAKAN_KEWAJIBAN",
        # "pabersihan hidup bertujuan membersihkan diri dari leteh" (the user's definition, 2026-10-28)
        "BERTUJUAN_MEMBERSIHKAN_DARI",
        # "kanoroyang melarang pelanggarnya mengubur ... di setra desa" (canon audit 2026-10-28;
        # MELARANG had read "kanoroyang melarang setra")
        "MELARANG_PENGUBURAN_DI",
    },
    "ciri": {
        # "sasih kaenem tergolong dewasa madya" (route audit 2026-10-27)
        "TERGOLONG_SEBAGAI",
        "BERWARNA", "MEMILIKI_TINGKAT", "BERUKURAN_PANJANG", "SEPANJANG", "BERBENTUK",
        "DIBUAT_BERBENTUK", "BERWUJUD", "MEMILIKI", "DIGUNAKAN_SEBANYAK", "MEMPERTAHANKAN",
        "TIDAK_MENGGUNAKAN", "BERVARIASI_DALAM", "SEBANDING_DENGAN", "MENYEBARKAN",
        "HARUS_DIRASAKAN_SEBAGAI", "DISESUAIKAN_DENGAN", "MENJADI_STANDAR", "MEMBERIKAN",
        # added 2026-09-30
        "BERBEDA_DENGAN", "BERGANTUNG_PADA", "BERLAKU_UNTUK", "BERLAWANAN_DENGAN",
        "DILAKUKAN_TANPA", "MENGANUT", "MILIK_DARI", "TANPA", "TIDAK_MEMILIKI", "TIDAK_TERPENGARUH",
        "WARGA_DARI",
        # influenced by: a trait, not a doer -- in pelaku it answered "Bali Dataran dilakukan oleh siapa" with
        # "Bali dataran mendapat pengaruh dari tradisi hindu-majapahit" (NLU sweep 2026-10-19)
        "MENDAPAT_PENGARUH_DARI",
        # "kakawin ditulis dalam bahasa kawi" (2026-10-02)
        "DITULIS_DALAM",
        # tirtha kawitan in the order of the tirthas sprinkled "dari tingkatan paling rendah" (L3978) -- V2 2026-11-02
        "BERADA_PADA_TINGKATAN",
    },
    # which text (lontar) describes the term ("dijelaskan dalam lontar apa")
    "sumber": {"DIJELASKAN_DALAM", "MERINCI"},
    "cara": {
        "DILAKUKAN_DENGAN", "DIIKAT", "DIIKAT_DENGAN", "DIBUNGKUS", "DIGULUNG_DENGAN",
        "DIBERI", "DIPAKAIKAN", "DITUTUP_DENGAN", "DIHIAS_SEOLAH_OLAH", "HARUS_DIBIARKAN",
        "MEMAKAI", "DIBERSIHKAN_DARI", "DIBERSIHKAN_DENGAN", "DIGANTI_DENGAN",
        "DITARUH_DENGAN", "DITARUH_PADA_PEPAGA", "DIBARINGKAN_DENGAN", "DIMANTRAI",
        "DIPULUNG", "DISUCIKAN_DENGAN", "DISIRAM_DENGAN", "DIKERINGKAN_DENGAN",
        "DIKELILINGI_OLEH", "DIBAWA_MENGHADAP", "MELAKUKAN", "DIJADIKAN", "DIBONGKAR",
        "DIAMBIL_DARI", "MENGELUPASI", "MENGGUNAKAN", "DITERIMA_SEBAGAI", "BERUBAH_WUJUD",
        "BERUBAH_MENJADI", "MENJADI", "MENINGKAT_STATUS", "NAIK_KEDUDUKAN_DARI",
        "NAIK_KEDUDUKAN_MENJADI", "MENINGKAT_KEDUDUKAN_MENJADI", "MUSNAH_MELALUI",
        "DIPERCIKKAN", "MEMANAH", "MENEMPATKAN_DIRI", "MENYERAHKAN", "DILETAKKAN_DENGAN",
        "DILINDUNGI_DENGAN", "DICABUT_DENGAN", "DIANGGAP_SEBAGAI", "DIPERLAKUKAN_SEPERTI",
        # added 2026-09-30
        "BERPAMITAN_KEPADA", "BERPUTAR_DENGAN", "DIAWALI_DENGAN", "DIAKHIRI_DENGAN",
        "DIBENTUK_MENJADI", "DIDUKUNG_DENGAN", "DIGILING_DI_ATAS", "DIHALUSKAN_DENGAN",
        "DIHANCURKAN_DI", "DIHITUNG_BERDASARKAN", "DIIKAT_PADA", "DIKURUNG_DENGAN",
        "DILAKUKAN_SECARA", "DILAKUKAN_TANPA", "DIOLESKAN_DI", "DIPAKAIKAN_PADA", "DIPASANG",
        "DIPERCIKI_DAN_DIMINUMKAN", "DIPERCIKI_DENGAN", "DIPLASPAS_BERSAMA", "DIPUJA", "DIPUJA_DENGAN",
        "DISABUNI_DENGAN", "DISAMBUNG_DENGAN", "DISEMBURKAN_PADA", "DISUGUHI",
        "DITAHBISKAN_MELALUI", "DITENTUKAN_OLEH", "DITUTUPI_DENGAN", "DIUSUNG_SECARA",
        "LAHIR_DALAM_WUJUD", "MELARUNGKAN", "MEMPEROLEH", "MENDAPATKAN", "MENERIMA", "MENJALANI",
        "MERUPAKAN_PERUBAHAN_DARI", "TATA_PELAKSANAAN_SAMA_DENGAN",
        # how a baby's body is handled by age (2026-10-02)
        "DIUPACARAI_DENGAN", "DIUPACARAI_DENGAN_CARA",
        # how Tirtha Pangentas is made (L3794-3962) and how Naga Banda is used (L1678 "bagaimana cara
        # penggunaannya?") -- V2 2026-11-02
        "DIBUAT_MELALUI", "DIGUNAKAN_DENGAN_CARA",
    },
}


# Composition ("X terbuat dari apa"): the komposisi predicates that say what a sarana is made
# of or holds. Most run whole -> part; PART_IS_SUBJECT run part -> whole ("mirah
# DIMASUKKAN_KE_DALAM tirta"). Kinds and "served with" are not parts.
PART_IS_SUBJECT = frozenset({"BAGIAN_DARI", "DIPERLUKAN_UNTUK_MEMBUAT", "DIMASUKKAN_KE_DALAM",
                             "DILENGKAPKAN_PADA"})
COMPOSITION_PREDICATES = frozenset(PREDICATE_FAMILIES["komposisi"]
                                   - {"TERMASUK_JENIS", "MEMILIKI_JENIS", "DISERTAI", "DISAJIKAN_BERSAMA"})
# the entity types a composition tree runs through (a stage BAGIAN_DARI a ritual is not a part)
COMPOSITE_TYPES = frozenset({"SARANA_RITUAL", "TIRTHA_SUCI", "BANGUNAN_RITUAL"})


def _loadl(path: Path) -> List[dict]:
    txt = path.read_text(encoding="utf-8")
    return [json.loads(block) for block in txt.split("\n\n") if block.strip()]


def _content_norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class KbContent:
    def __init__(self, kb_dir: Path = _KB_DIR) -> None:
        self.kb_dir = kb_dir

        phrases = json.loads((kb_dir / "tuning" / "relation_phrases.json").read_text(encoding="utf-8"))
        self.templates: Dict[str, str] = {
            k: v["template"] for k, v in phrases.items() if not k.startswith("_")
        }
        self.variant_templates: Dict[str, str] = phrases.get("_variant", {})
        # raw materials: the leaves of a composition tree ("beras adalah bahan dasar")
        raw = json.loads((kb_dir / "tuning" / "raw_materials.json").read_text(encoding="utf-8"))
        self.raw_materials = frozenset(raw["raw"])

        self.facts_by_subj: Dict[str, List[dict]] = {}
        self.facts_by_obj: Dict[str, List[dict]] = {}
        for f in _loadl(kb_dir / "output" / "facts.jsonl"):
            self.facts_by_subj.setdefault(f["subject_id"], []).append(f)
            self.facts_by_obj.setdefault(f["object_id"], []).append(f)

        # canonical definitions as build_kb.py resolved them (glossary, or a curated
        # row). best_definition() used to consult only the glossary passages, so a
        # child node whose definition came from a curated row (e.g. sawa_prateka)
        # reached the LLM with no target_definition at all.
        ents = json.loads((kb_dir / "output" / "entities.json").read_text(encoding="utf-8"))
        self.entity_def: Dict[str, str] = {e["id"]: e["definition"] for e in ents if e.get("definition")}
        self.entity_name: Dict[str, str] = {e["id"]: e["name"] for e in ents}
        self.entity_type: Dict[str, str] = {e["id"]: e.get("type") or "" for e in ents}
        self.id_by_name: Dict[str, str] = {e["name"].lower(): e["id"] for e in ents}
        # is-a parents: the broader spine plus TERMASUK_JENIS relation rows (kinds of banten
        # from the tetandingan pass are rows, not broader links)
        self.kind_parents: Dict[str, set] = {}
        for e in ents:
            if e.get("broader"):
                self.kind_parents.setdefault(e["id"], set()).add(e["broader"])
        for rows in self.facts_by_subj.values():
            for f in rows:
                if (f.get("predicate") or "").upper() == "TERMASUK_JENIS":
                    self.kind_parents.setdefault(f["subject_id"], set()).add(f["object_id"])
        # text-only facts (LITERAL rows): {id: {PREDICATE: [value, ...]}}
        self.attributes: Dict[str, Dict[str, List[str]]] = {
            e["id"]: {p: [a["value"] for a in vals] for p, vals in e["attributes"].items()}
            for e in ents if e.get("attributes")
        }

        self.glossary_by_ent: Dict[str, List[dict]] = {}
        for p in _loadl(kb_dir / "output" / "passages.jsonl"):
            if p.get("kind") != "glossary":
                continue
            for eid in p.get("entity_ids", []):
                self.glossary_by_ent.setdefault(eid, []).append(p)

    # -- kinds ---------------------------------------------------------------
    def is_kind_of(self, entity_id: str, class_id: str, depth: int = 3) -> bool:
        """entity_id is a kind of class_id, directly or through up to `depth` is-a links."""
        frontier = {entity_id}
        for _ in range(depth):
            frontier = set().union(*(self.kind_parents.get(x, set()) for x in frontier))
            if class_id in frontier:
                return True
            if not frontier:
                return False
        return False

    def kinds_of(self, class_id: str) -> List[str]:
        """The direct kinds of class_id."""
        return sorted(x for x, ps in self.kind_parents.items() if class_id in ps)

    # -- templates -----------------------------------------------------------
    def render(self, predicate: str, subj: str, obj: str) -> str:
        tpl = self.templates.get(predicate.upper())
        if tpl:
            return tpl.format(s=subj, o=obj)
        verb = predicate.lower().replace("_", " ")
        return f"{subj} {verb} {obj}"

    def render_variant(self, predicate: str, subj: str, obj: str, variant: Optional[dict]) -> str:
        """render(), or the regional-variant sentence when the edge is a variant."""
        nl = self.render(predicate, subj, obj)
        if not variant or variant.get("op") not in self.variant_templates:
            return nl
        return self.variant_templates[variant["op"]].format(
            nl=nl, s=subj, o=obj, region=variant.get("region", ""), replaces=variant.get("replaces", ""))

    # -- composition -----------------------------------------------------------
    def composition_parts(self, entity_id: str) -> List[dict]:
        """Direct parts of a sarana/tirtha/building: [{id, predicate, variant}], main version
        first, each part once (a main-version row beats a variant row of the same part)."""
        if self.entity_type.get(entity_id) not in COMPOSITE_TYPES:
            return []
        rows = [(f["object_id"], f) for f in self.facts_by_subj.get(entity_id, [])
                if f["predicate"] in COMPOSITION_PREDICATES and f["predicate"] not in PART_IS_SUBJECT]
        rows += [(f["subject_id"], f) for f in self.facts_by_obj.get(entity_id, [])
                 if f["predicate"] in PART_IS_SUBJECT and self.entity_type.get(f["subject_id"]) in COMPOSITE_TYPES]
        out: Dict[str, dict] = {}
        for pid, f in sorted(rows, key=lambda x: "variant" in x[1]):
            if pid != entity_id and pid not in out:
                out[pid] = {"id": pid, "predicate": f["predicate"], "variant": f.get("variant")}
        return list(out.values())

    def is_raw(self, entity_id: str) -> bool:
        """A raw material, or a kind of one with no parts of its own (kain putih is a kind of
        kain; saput, also a kind of kain, is made of kain putih and so is not raw)."""
        if entity_id in self.raw_materials:
            return True
        return not self.composition_parts(entity_id) and any(
            self.is_kind_of(entity_id, r) for r in self.raw_materials)

    def inherited_parts(self, entity_id: str) -> tuple:
        """(parent_id, parts) of the nearest kind-parent that has parts, for an item with none of
        its own: tirtha pamlaspas is a kind of tirtha, which is made of air. (None, []) if none.
        Not a parent that has the item among its own parts: those are the item's siblings -- pura
        desa, a kind and a part of pura kahyangan tiga, was "made of" pura puseh and pura dalem."""
        if self.composition_parts(entity_id) or self.is_raw(entity_id):
            return None, []
        frontier = set(self.kind_parents.get(entity_id, set()))
        for _ in range(3):
            for parent in sorted(frontier):
                parts = self.composition_parts(parent)
                if parts and all(p["id"] != entity_id for p in parts):
                    return parent, parts
            frontier = set().union(*(self.kind_parents.get(x, set()) for x in frontier)) if frontier else set()
        return None, []

    def inherited_part_sentences(self, entity_id: str) -> List[str]:
        """inherited_parts() as sentences, each saying where the parts come from:
        "gajah mina (sebagai jenis patulangan) terbuat dari kayu"."""
        parent, parts = self.inherited_parts(entity_id)
        if not parent:
            return []
        whole = f"{self.entity_name.get(entity_id, entity_id)} (sebagai jenis {self.entity_name.get(parent, parent)})"
        out = []
        for p in parts:
            part = self.entity_name.get(p["id"], p["id"])
            s, o = (part, whole) if p["predicate"] in PART_IS_SUBJECT else (whole, part)
            out.append(self.render_variant(p["predicate"], s, o, p["variant"]))
        return out

    def composition_tree(self, entity_id: str, depth: int = 4) -> dict:
        """{id, name, raw, inherited_from, parts: [{predicate, variant, node}], cut} down to
        `depth` levels. An item with no parts of its own shows its kind-parent's parts
        (`inherited_from`). Cycle-safe; a composite part met a second time is not expanded
        again (`seen`)."""
        expanded: set = set()

        def walk(eid: str, level: int, path: frozenset) -> dict:
            node = {"id": eid, "name": self.entity_name.get(eid, eid), "raw": self.is_raw(eid),
                    "inherited_from": None, "parts": [], "cut": False, "seen": False}
            parts = self.composition_parts(eid)
            if not parts:
                parent, parts = self.inherited_parts(eid)
                node["inherited_from"] = self.entity_name.get(parent) if parent else None
                path = path | ({parent} if parent else set())
            if not parts:
                return node
            if eid in expanded:
                node["seen"] = True
                return node
            if level >= depth:
                node["cut"] = True
                return node
            expanded.add(eid)
            for p in parts:
                if p["id"] in path:
                    continue
                node["parts"].append({"predicate": p["predicate"], "variant": p["variant"],
                                      "node": walk(p["id"], level + 1, path | {p["id"]})})
            return node

        return walk(entity_id, 0, frozenset({entity_id}))

    def attribute_sentences(self, entity_id: str, predicates: set) -> List[str]:
        """The entity's text-only facts whose predicate is in `predicates`, as sentences."""
        name = self.entity_name.get(entity_id, entity_id)
        return [self.render(p, name, v)
                for p, vals in self.attributes.get(entity_id, {}).items() if p in predicates
                for v in vals]

    # -- facts -------------------------------------------------------------
    def _dedup_sorted(self, rows: List[dict]) -> List[dict]:
        rows = sorted(rows, key=lambda f: _CONF_RANK.get(f.get("confidence"), 3))
        seen, out = set(), []
        for f in rows:
            key = _content_norm(f["text"].rstrip("."))
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out

    def facts_for(self, entity_id: str, limit: int = 6) -> List[str]:
        rows = self.facts_by_subj.get(entity_id, []) + self.facts_by_obj.get(entity_id, [])
        return [f["text"].rstrip(".").strip() for f in self._dedup_sorted(rows)][:limit]

    def definition_facts(self, entity_id: str) -> Optional[str]:
        """A fallback 'definition' assembled from ADALAH / BERARTI / DIKENAL_SEBAGAI."""
        want = {"ADALAH", "BERARTI", "DIKENAL_SEBAGAI", "MERUPAKAN"}
        rows = [
            f for f in self.facts_by_subj.get(entity_id, [])
            if (f.get("predicate") or "").upper() in want
        ]
        rows = self._dedup_sorted(rows)
        if not rows:
            return None
        return "; ".join(f["text"].rstrip(".").strip() for f in rows[:3]) + "."

    # -- passages ---------------------------------------------------------
    def glossary_for(self, entity_id: str) -> Optional[str]:
        rows = self.glossary_by_ent.get(entity_id, [])
        if not rows:
            return None
        text = rows[0].get("text", "")
        return text.split(":", 1)[1].strip() if ":" in text else text.strip()

    def best_definition(self, entity_id: str, graph_definition: Optional[str] = None) -> Optional[str]:
        return (graph_definition or self.entity_def.get(entity_id) or self.glossary_for(entity_id)
                or self.definition_facts(entity_id))


_CONTENT: Optional[KbContent] = None


def get_content() -> KbContent:
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = KbContent()
    return _CONTENT


# =====================================================================================================================
# (end of KB access)
# =====================================================================================================================


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
# Every failed call, why (a rate limit, the daily token cap, a timeout): three live turns answered from definitions
# with no trace of the cause but the action server's console (2026-11-06)
_LLM_ERROR_LOG_PATH = _BOT_DIR / "llm_error_log.jsonl"
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
        _log_jsonl(_LLM_ERROR_LOG_PATH, {"kind": purpose, "error": "skipped: the LLM failed less than a minute ago",
                                         "last_error": f"{type(_llm_last_error).__name__}: {_llm_last_error}"[:400]})
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
        _log_jsonl(_LLM_ERROR_LOG_PATH, {"kind": purpose, "model": LLM_MODEL,
                                         "error": f"{type(e).__name__}: {e}"[:400]})
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
# typos, force-merges) is the resolver's job (KbResolver), done *before* we ever touch Neo4j.
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
# A sentence (or its last part) as the answer checks cut and keep them: up to . ! ? or a line end -- not a dot between
# digits: "berkisar antara 250 hingga 80.000 uang kepeng" was two parts, the first cut as unsupported, and the answer
# read "Maaf, informasi tersebut belum tersedia. 000 uang kepeng." (style test 2026-11-06)
_SENT_PART = r"(?:[^.!?\n]|(?<=\d)\.(?=\d))+[.!?]*"
_SENT_PART_RE = re.compile(_SENT_PART)

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
    """Ongoing curation feed for resolver misses -- mirrors review_queue.jsonl's
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
    # (not having something is the user's situation, not the rite left undone: "ngaben jenis apa yang cocok jika tidak
    # memiliki banyak uang?" got "Padahal, ngaben merupakan salah satu tahap untuk mencapai moksa", 2026-11-06)
    r"(?:tidak|tak|nggak|ngga|enggak|gak|ga|tanpa|belum)\b"
    r"(?!\s+(?:punya|ada|mampu|cukup|sempat|memiliki|mempunyai|banyak|seberapa)\b)"
    # (not the yes/no tail: "kalau jenazahnya dikubur dulu boleh gak?" got the all-kinds-are-equal answer, bot test
    # 2026-11-05)
    r"(?!(?:\s+(?:sih|ya|yah|kah|dong|deh|kak))?\s*[?.!]*\s*$)"
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
    parts = [s for s in _SENT_PART_RE.findall(answer) if s.strip()]
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
        # a kind the message names: "kalau jenazahnya tidak ditemukan, ngaben apa yang dilakukan?" names none (ngaben
        # svasta comes from the situation) and got "Ngaben svasta adalah salah satu jenis ngaben. Semua jenis ...",
        # never what svasta is (style test 2026-11-06)
        surfaces = [e["name"], e.get("asked_as"), e.get("typed_as")] + list(e.get("aliases") or [])
        if not any(s and re.search(rf"(?<![\w-]){re.escape(s)}(?![\w-])", user_msg, re.I) for s in surfaces):
            continue
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


# a child's age as the message gives it: "umur 2 bulan", "bayi 40 hari" -- not a time since the death ("meninggal 2
# bulan lalu")
_BABY_AGE_RE = re.compile(r"\b(?:umur|usia|berusia|berumur)\s+(?:baru\s+)?(\d+)\s*(hari|minggu|bulan)\b"
                          r"|\b(?:bayi|anak)\s+(?:yang\s+)?(?:baru\s+)?(\d+)\s*(hari|minggu|bulan)\b", re.I)
_BABY_SETTING = frozenset({"jenazah_bayi", "ngaben", "upacara_ngelungah", "jenazah"})


def _young_baby_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A baby younger than 105 days (tiga bulan pawukon) gets no Ngaben and no Ngelungah: jenazah bayi's card says the
    first two tiers are only bathed, wrapped and buried. "upacara apa untuk bayi yang meninggal umur 2 bulan?" got
    "Usia 2 bulan termasuk dalam tingkat ketiga ... Upacara Ngelungah" from the model (style test 2026-11-06). Only for
    an age under 105 days even counted at its longest (a month as a pawukon month of 35 days), and only when the
    message names no rite beyond ngaben / ngelungah."""
    ids = {e["id"] for e in enriched}
    m = _BABY_AGE_RE.search(user_msg)
    if "jenazah_bayi" not in ids or not m or ids - _BABY_SETTING:
        return None
    n, unit = int(m.group(1) or m.group(3)), (m.group(2) or m.group(4)).lower()
    if n * {"hari": 1, "minggu": 7, "bulan": 35}[unit] >= 105:
        return None
    baby = next(e for e in enriched if e["id"] == "jenazah_bayi")
    tier = next((s for s in _sentences(baby.get("definition")) if "105 hari" in s and re.search(r"\bdikubur\b", s)),
                None)
    if not tier:
        return None
    # a whether-question gets its verdict first ("bayi tetangga meninggal umur 2 bulan, itu diaben juga gak?")
    verdict = "Tidak. " if (_YES_NO_Q_RE.search(user_msg) or _CASUAL_YES_NO_RE.search(user_msg)) else ""
    return (f"{verdict}Bayi yang meninggal pada usia {n} {unit} belum berusia 105 hari (tiga bulan pawukon), sehingga "
            f"tidak diaben dan tidak diupacarai dengan Upacara Ngelungah. {tier}")


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
    head_only = re.compile(r"(\s*)(\d+[.)]|[-*•])\s+[^:\n]{1,80}:\s*(\.?)\s*")

    def bare(i: int) -> bool:
        # ... or its head and colon: "- Tirtha Gangga:." (live run 2026-11-14). A head with items under it stays: a
        # deeper item, or one of the other kind ("1. Biaya Paket di Krematorium:" over "- Paket ...")
        m = head_only.fullmatch(lines[i])
        if not m:
            return bool(re.fullmatch(r"\s*(?:\d+[.)]|[-*•])\s*", lines[i]))
        if m.group(3):
            return True
        nxt = re.match(r"(\s*)(\d+[.)]|[-*•])\s", next((x for x in lines[i + 1:] if x.strip()), ""))
        return not (nxt and (len(nxt.group(1)) > len(m.group(1)) or nxt.group(2)[0].isdigit() != m.group(2)[0].isdigit()))
    gone = {i for i in range(len(lines)) if bare(i)}
    if not gone:
        return answer
    kept = [x for i, x in enumerate(lines) if i not in gone]
    if any(re.match(r"\s*\d+[.)]", lines[i]) for i in gone):
        # each list counts from 1; a line of prose between two lists starts a new one (a dash item under a numbered
        # one does not)
        n, out = 0, []
        for x in kept:
            if re.match(r"\s*\d+[.)]\s", x):
                n += 1
                x = re.sub(r"^(\s*)\d+([.)])", lambda m: f"{m.group(1)}{n}{m.group(2)}", x)
            elif x.strip() and not re.match(r"\s*[-*•]\s", x):
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


def _drop_unsupported_comparatives(answer: Text, context_text: Text) -> Text:
    """A comparison answer's "lebih X" that no context sentence says ("lebih X" or "paling X", by root): "Sebaliknya,
    Asti Wedana memiliki tata pelaksanaan yang lebih sederhana, dimulai dengan matur piuning ..." -- the cards say only
    that Sawa Wedana has the most upacara (bot test 2026-11-05). A "yang lebih X" modifier loses the comparative; any
    other sentence resting on it goes, unless it is the whole answer."""
    said = {_root(m.group(1).lower()) for m in re.finditer(r"\b(?:lebih|paling)\s+(\w+)", context_text, re.I)}

    def unsupported(m) -> bool:
        return _root(m.group(1).lower()) not in said
    # (not "lebih dahulu", "lebih dari", "lebih lanjut", nor a way of saying it -- "Secara lebih rinci, Sekah dialasi
    # dulang ..." went, 2026-11-05: no comparison of the two)
    rx = re.compile(r"(?<!secara )\blebih\s+(?!(?:dari|daripada|dahulu|dulu|awal|lanjut|lagi|rinci|jelas\w*|tepat\w*|"
                    r"jauh|detail|spesifik|singkat\w*)\b)(\w+)", re.I)
    sentences = re.findall(_SENT_PART + r"\s*|\n+", answer)
    out = []
    for s in sentences:
        hits = [m for m in rx.finditer(s) if unsupported(m)]
        if not hits:
            out.append(s)
            continue
        trimmed = re.sub(r"\s+yang\s+lebih\s+(?!(?:dari|daripada|dahulu|dulu|awal|lanjut|lagi)\b)(\w+)(?=\s*[,.;])",
                         lambda m: "" if _root(m.group(1).lower()) not in said else m.group(0), s, flags=re.I)
        if not any(unsupported(m) for m in rx.finditer(trimmed)):
            out.append(trimmed)
    result = "".join(out).strip()
    return result if result else answer


# "sebagai bentuk / wujud / tanda ... <noun> [dari / bagi / ... the rest of the clause]": what an act is made to stand for
_PURPOSE_PHRASE_RE = re.compile(r",?\s+sebagai\s+(?:bentuk|wujud|tanda|simbol|lambang|ungkapan|perwujudan)\s+([\w-]+)"
                                r"[^,.;:!?\n]*", re.I)


def _drop_unsupported_purposes(answer: Text, context_text: Text) -> Text:
    """A "sebagai bentuk X" no context sentence gives -- X's root nowhere in the context -- goes, the rest of its sentence
    stays: "Upacara mesulub: Melakukan tradisi berjalan membungkuk di bawah jenazah ..., sebagai bentuk penyembuhan dari
    keluarga yang patut." (mesulub's card says its meaning is kesetiaan; "apa tugas keluarga?", Qwen 2026-11-12). The
    support check weighs the whole sentence, which its other words carried."""
    roots = {_root(w) for w in _WORD_RE.findall(context_text.lower())}
    words = set(_WORD_RE.findall(context_text.lower()))

    def cut(m: "re.Match") -> str:
        head = m.group(1).lower()
        # (a prefix as long as the word's root, not six letters: "pengab-dian" met "pengab-enan" and "sebagai bentuk
        # pengabdian" stayed on Tirtha Penembak, plan #31)
        n = max(6, len(head) - 3)
        if head in words or _root(head) in roots or any(w.startswith(head[:n]) for w in words if len(head) >= 6):
            return m.group(0)
        return ""
    out = _PURPOSE_PHRASE_RE.sub(cut, answer)
    return out if out.strip() else answer


_NAME_CLAIM_RE = re.compile(r"\s*(?P<subj>.+?)\s+(?:juga\s+)?(?:dikenal|disebut)\s+(?:juga\s+)?(?:sebagai|dengan(?:\s+(?:nama|"
                            r"istilah|sebutan))?)\s+(?P<y>[^,.;:()]+?)\s*(?:,\s*(?:yaitu|yakni)\s+(?P<gloss>.+?))?\s*\.?$",
                            re.I | re.S)


def _fix_false_name_claims(answer: Text) -> Text:
    """A sentence saying a term is also called a name that is another card's -- no alias of it, no other-name edge
    between them -- loses the claim: "... diganti dengan simbol tirtha yang disebut toyo çarira. Simbol ini juga dikenal
    sebagai pengawak, yaitu simbol pengganti jenazah asli ..." (pengawak is a corpse stand-in of its own, sweep
    2026-11-13). With a ", yaitu <gloss>" it says what the other card is ("Pengawak adalah simbol pengganti ..."),
    else it goes. The subject is a term the sentence names, or for "X ini / tersebut" the last term the sentence before
    it names; nothing changes when either side is no card."""
    resolver, content = get_resolver(), get_content()

    def card(phrase: Text):
        hit = resolver.resolve(phrase.strip())
        return hit if hit and hit.via in ("exact", "alias") and _ortho_key(phrase) in {
            _ortho_key(n) for n in [hit.name] + list(hit.entity.get("aliases") or [])} else None

    def fix(s: Text, before: Text) -> Text:
        m = _NAME_CLAIM_RE.match(s)
        y = card(m.group("y")) if m else None
        if not y:
            return s
        words = m.group("subj").strip()
        if re.fullmatch(r"(?:\w+\s+)?(?:ini|itu|tersebut)", words, re.I):
            prev = (_sentences(before.strip()) or [""])[-1].lower()
            # (the term it points at: the one the sentence before names last, by any of its surfaces)
            at = [(max((prev.rfind(n.lower()) for n in [content.entity_name.get(t, t)] + list(
                        (resolver.by_id.get(t) or {}).get("aliases") or [])), default=-1), t)
                  for t in _named_terms(prev, everyday=True)]
            at = [p for p in at if p[0] >= 0]
            subj = max(at)[1] if at else None
        else:
            hit = card(re.sub(r"^(?:dan|namun|selain itu),?\s+", "", words, flags=re.I))
            subj = hit.id if hit else None
        if not subj or subj == y.id or any(
                f["object_id"] in (y.id, subj) and f["predicate"] in PREDICATE_FAMILIES["sebutan_lain"]
                for f in content.facts_by_subj.get(subj, []) + content.facts_by_subj.get(y.id, [])):
            return s
        gloss = (m.group("gloss") or "").strip().rstrip(".")
        return f"{_cap(_card_cased(y.id))} adalah {gloss}." if gloss else ""
    return _edit_sentences(answer, fix)


def _fix_class_claims(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A sentence about the asked class that says what only one of its kinds' cards says moved that kind's fact onto
    the class: the class name becomes the kind's. "apa peran tirta dalam pengabenan" got "Secara filosofis, tirtha
    berfungsi sebagai alat sangaskara (penyucian) bagi atman, yang mengangkat kedudukan roh dari preta menjadi pitara
    ..." -- Tirtha Pangentas's card; tirtha's own says only that it is holy water asked from a sulinggih (AYUTHAYA
    repair, Tier B on Qwen 2026-11-04, the same on a re-run). Only when most of the sentence's own words (not the
    class's name, card and facts) are one kind's and no other kind comes near; a sentence naming a kind is left."""
    if not enriched:
        return answer
    content, resolver, e = get_content(), get_resolver(), enriched[0]

    def own_text(i: str) -> List[str]:
        return [content.best_definition(i) or ""] + content.attribute_sentences(i, set(content.attributes.get(i, {})))
    kinds = {k: _sentence_roots(" ".join(own_text(k))) for k in content.kinds_of(e["id"])}
    kinds = {k: r for k, r in kinds.items() if r}
    if len(kinds) < 2:
        return answer
    names = [n for n in [e["name"]] + list(e.get("aliases") or []) if n]
    own = _sentence_roots(" ".join(own_text(e["id"]) + [e.get("definition") or ""] + names + [
        r.get("statement") or "" for r in e.get("relationships") or []
        if not (r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing"))]))
    name_rx = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
                         + r")(?![\w-])", re.I)

    def one_kind(claim: set) -> Optional[str]:
        """The kind whose card holds most of the claim, when no other comes near."""
        if len(claim) < 5:
            return None
        share = sorted(((len(claim & r) / len(claim), k) for k, r in kinds.items()), reverse=True)
        return share[0][1] if share[0][0] >= 0.7 and share[1][0] < 0.5 else None

    for s in _SENT_PART_RE.findall(answer):
        first = name_rx.search(s)
        if not first or not one_kind(_sentence_roots(s) - own):
            continue
        # a class another noun narrows is that group, not the class: "untuk jenazah orang dewasa ..., praktik penguburan
        # tidak berlaku" became "jenazah bayi orang dewasa" (bot test 2026-11-05)
        if re.match(r"\s+(?:orang|anak|bayi|dewasa|balita|remaja|lansia|pria|wanita|perempuan|laki-laki|raja|pendeta|"
                    r"sulinggih|keluarga|warga)\b", s[first.end():], re.I):
            continue
        # the term finder last (it is slow): the class named as itself and no kind named -- "Tirtha Pangentas" holds
        # "tirtha" but names the kind; and the claim said in words, not by naming terms -- "Sesajen yang dipakai dalam
        # banten adalah banten pejati, banten suci, banten peras, dan daksina" is a list, each named in Pras Daksina's
        # card (snapshot 2026-11-04)
        found = _mentioned_terms(s, resolver)[0]
        ids = {m.id for m, _ in found}
        if e["id"] not in ids or ids & set(kinds):
            continue
        k = one_kind(_sentence_roots(s) - own - _sentence_roots(" ".join(surface for _, surface in found)))
        if not k:
            continue
        # the kind as the answer writes it elsewhere ("Tirtha Pangentas"), else its name capitalized
        surfaces = sorted((x for x, i in resolver.surface.items() if i == k), key=len, reverse=True)
        written = next((m.group(0) for x in surfaces
                        for m in [re.search(rf"(?<![\w-]){re.escape(x)}(?![\w-])", answer, re.I)] if m), None)
        kind = written or content.entity_name.get(k, k).title()
        answer = answer.replace(s, name_rx.sub(lambda m: kind, s, count=1), 1)
    return answer


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
    out, sentences = answer, _SENT_PART_RE.findall(answer)
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

        # a list item's gloss is about its head: "- Tirtha Gangga: Dipakai dalam pembuatan Tirtha Pangentas, yang ...
        # hanya dapat diturunkan oleh Dewa Siwa" gives Siwa to Tirtha Gangga (its own card's), yet the ":" read as a
        # clause boundary gave it to Tirtha Pangentas, and the cut left "- Tirtha Gangga:." (live run 2026-11-14)
        head = re.match(r"\s*(?:\d+[.)]|[-*•])\s+[^:\n]{1,80}:", s)
        head_marks = set().union(*(marks[m] for _, b, m in member_spans if head and b <= head.end()))

        def wrong(group: tuple) -> bool:
            ms, seg = group[0], group[1]
            return any((seg - marks[m] - head_marks) & context_marks.union(*(marks[o] for o in members if o != m))
                       for m in ms)
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


def _known_sentence(definition: Optional[Text], limit: int = 300, entity_id: Optional[Text] = None,
                    name: Optional[Text] = None) -> str:
    """The definition's first sentence for a "Yang tercatat tentang X: ..." line the user reads: a long
    one ends at a clause boundary rather than mid-clause with "..." -- 41 template misses of the NLU sweep
    ended "... wangsa seseorang turut menentukan ..." (2026-10-19). (_first_sentence's own cut stays: it
    feeds the prompt too.) Given the term's name, the sentence opens with it (_named_definition)."""
    if name and definition and definition != "Tidak ada definisi langsung":
        definition = _named_definition(definition, entity_id, name)
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


def _named_definition(definition: Text, entity_id: Optional[Text], name: Text) -> str:
    """The definition with its own term first, as the bot shows a card's sentences on their own: a gloss with no subject
    gets the name ("Para pendahulu, seperti ..." -> "Pitra adalah para pendahulu, ..."), and an opening phrase goes after
    the subject ("Dalam konteks kalender Bali, Wayang adalah ..." -> "Wayang, dalam konteks kalender Bali, adalah ...").
    The sweep of 2026-11-13 found 194 cards opening either way; a miss quoted them as they stand ("Yang tersedia tentang
    pitra: Para pendahulu, ...")."""
    d = definition.strip()
    # (already "{name} ...": spaces, hyphens and quotes aside -- "Antah karana sarira" is antahkarana sarira, and
    # '"Eteh-eteh" secara umum berarti ...' eteh-eteh's)
    if re.sub(r"[\s\"“”'-]", "", d.lower()).startswith(re.sub(r"[\s-]", "", name.lower())):
        return d
    m = _definition_subject(d, entity_id, name)
    if not m:
        return f"{name[:1].upper()}{name[1:]} adalah {d[:1].lower()}{d[1:]}"
    lead = d[:m.start(1)].strip()
    # (a context phrase only: 'Secara harfiah "nganyut" berarti ...' reads right as it is)
    if not lead.endswith(","):
        return d
    lead = lead.rstrip(",").strip()
    subject, rest = m.group(1), d[m.end(1):]
    bracket = re.match(r"\s*\([^)]*\)", rest)
    if bracket:
        subject, rest = subject + rest[:bracket.end()], rest[bracket.end():]
    return f"{subject[:1].upper()}{subject[1:]}, {lead[:1].lower()}{lead[1:]},{rest}"


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
            # a definition is often already a full "{name} adalah ..." sentence -- don't double the subject ("soda
            # adalah Soda adalah ...", nor "Tirta pangentas adalah tirtha Pangentas adalah ...": another spelling or an
            # alias); _named_definition
            sentences.append(f"{_named_definition(definition.rstrip('.'), e.get('id'), name)}.")
        elif e.get("facts"):
            sentences.append(". ".join(e["facts"][:3]) + ".")
        for fact in e.get("aspect_facts") or []:
            sentences.append(f"{fact[:1].upper()}{fact[1:]}.")
    return " ".join(sentences)


def _outage_answer(enriched: List[Dict[str, Any]]) -> str:
    """The graph is unreachable, so the terms' edges are missing, not absent: a model told to
    answer from the definitions alone said "tahapan ngaben belum tercatat" and "ngaben hanya
    memiliki satu jenis" (2026-10-07 batch). Say what is known and why it is short."""
    return (_deterministic_answer(enriched) + "\n\n(Catatan: sebagian informasi sedang tidak "
            "dapat diakses, jadi jawaban ini hanya berisi definisi istilah -- tahapan, sarana, "
            "jenis, dan hubungannya belum bisa ditampilkan. Silakan coba lagi nanti.)")


# What the user reads when something is not recorded (user, 2026-11-03, the AYUTHAYA change: "smoothen the style ...
# 'Im sorry, this information is not currently available'", "NEVER SAY THE 'THERE ISNT THE INFO IN THE DATABASE'"):
# the checks and the model keep writing "belum tercatat di basis data", which the checks detect, and _present rewrites
# every message the actions send as the last step
_NO_INFO = "Maaf, informasi tersebut belum tersedia."
_MISS_TAIL = (r"(?:belum|tidak)\s+(?:tercatat|tercantum|dicatat)(?:\s+(?:di|dalam)\s+basis\s+data"
              r"(?:\s+(?:yang\s+tersedia|istilah\s+ngaben))?)?")
_PRESENT_RULES = (
    # a term the KB lacks keeps its quote: "Maaf, saya tidak menemukan 'X' di basis data. Mungkin maksud Anda: ..."
    (re.compile(r"Maaf,\s+saya\s+tidak\s+menemukan\s+('[^'\n]+')\s+di\s+basis\s+data", re.I),
     r"Maaf, informasi tentang \1 belum tersedia"),
    (re.compile(rf"Maaf,\s+informasi\s+mengenai\s+('[^'\n]+')\s+{_MISS_TAIL}", re.I), r"Maaf, informasi tentang \1 belum tersedia"),
    # an answer that opens with its miss: the sentence the user chose
    (re.compile(rf"\A\s*Maaf,\s+[^.?!\n']*?\b{_MISS_TAIL}\s*\.", re.I), _NO_INFO),
    # _say_no_link's "Tidak ada hubungan langsung antara X dan Y yang tercatat." (read "... yang tersedia")
    (re.compile(r"\bTidak\s+ada\s+(hubungan|kaitan|keterkaitan)(\s+langsung)?\s+antara\s+([^.\n]+?)\s+yang\s+"
                r"(?:tercatat|tercantum)(?:\s+(?:di|dalam)\s+basis\s+data)?\s*\."),
     r"Informasi tentang \1\2 antara \3 belum tersedia."),
    # ... and Qwen's own order, "tidak ada hubungan langsung yang tercatat antara caru dan Wesia", which read "Tidak ada
    # hubungan langsung yang tersedia antara ..." (live run 2026-11-14)
    (re.compile(r"\b([Tt])idak\s+ada\s+(hubungan|kaitan|keterkaitan)(\s+langsung)?\s+yang\s+(?:tercatat|tercantum|"
                r"tersedia)(?:\s+(?:di|dalam)\s+basis\s+data)?\s+antara\s+([^.\n]+?)\s*\."),
     lambda m: f"{'I' if m.group(1) == 'T' else 'i'}nformasi tentang {m.group(2)}{m.group(3) or ''} antara "
               f"{m.group(4)} belum tersedia."),
    # "Yang tercatat tentang X: ...", and the model's "Yang tercatat adalah bahwa ..."
    (re.compile(r"\b([Yy])ang\s+tercatat\b"), r"\1ang tersedia"),
    # the stage fallback's "... secara keseluruhan tidak tercatat, tetapi untuk bagian-bagiannya tercatat: - ..." and
    # "... tercatat bahwa X." (AYUTHAYA repair, snapshot 2026-11-04)
    (re.compile(r"\buntuk\s+(tahapannya|bagian-bagiannya)\s+tercatat(?::|\s+bahwa\b)"), r"yang tersedia untuk \1:"),
    # the unordered stage list's "(urutannya tidak disebutkan dalam sumber)": no unnamed source (bot test 2026-11-05)
    (re.compile(r"\(urutannya\s+tidak\s+disebutkan\s+dalam\s+sumber\)"), "(urutannya belum tersedia)"),
    (re.compile(r"\b[Bb]asis\s+data\s+tidak\s+(?:mencantumkan|memuat|menyebutkan|mencatat)\s+(?:informasi\s+)?"
                r"(?:mengenai|tentang)\s+([^.;\n]+)"), r"Informasi mengenai \1 belum tersedia"),
    (re.compile(r"\b[Bb]asis\s+data\s+(hanya\s+)?(?:menjelaskan|menyebutkan|mencatat|menyatakan)\b"),
     r"Informasi yang tersedia \1menyebutkan"),
    (re.compile(_MISS_TAIL, re.I), "belum tersedia"),
    (re.compile(r"\s*\b(?:di|dalam|menurut|pada|dari)\s+basis\s+data(?:\s+yang\s+tersedia)?\b", re.I), ""),
    # the same source talk without "basis": "Tidak ada keterangan dalam data yang menyebutkan ..." (live run 2026-11-14)
    (re.compile(r"\s*\b(?:di|dalam|menurut|pada|dari)\s+data(?:\s+yang\s+(?:ada|tersedia))?\b", re.I), ""),
    # a sentence opening with it keeps its capital: "Basis data secara tegas menyatakan ..." read "informasi yang
    # tersedia secara tegas ..." (Tier B on Qwen, AYUTHAYA part B, 2026-11-04)
    (re.compile(r"\bBasis\s+[Dd]ata\b"), "Informasi yang tersedia"),
    (re.compile(r"\bbasis\s+data\b", re.I), "informasi yang tersedia"),
    # no unnamed source: "namun sumber tidak menguraikan kegunaannya secara spesifik" (Tier B on Qwen, 2026-11-04)
    (re.compile(r"\b([Nn]amun\s+|[Tt]etapi\s+)?[Ss]umber(?:nya)?(?:\s+yang\s+ada)?\s+tidak\s+"
                r"(?:menguraikan|menjelaskan|merinci|menyebutkan|mencatat)\s+([^.;\n]+)"),
     r"\1informasi tentang \2 belum tersedia"),
    # the miss that goes on as if a text spoke: "... belum tersedia, melainkan hanya menjelaskan bahwa penentuan harinya
    # ..." (style test 2026-11-06) -- what is there, as a sentence of its own
    (re.compile(r"\bbelum\s+tersedia,?\s+(?:melainkan|tetapi|namun)\s+(?:hanya\s+)?(?:menjelaskan|mencatat|menyebutkan|"
                r"menyatakan)\s+bahwa\s+(\w)"),
     lambda m: f"belum tersedia. Yang tersedia: {m.group(1)}"),
    # "Yang tersedia adalah bahwa Pasah adalah ..." opening the answer (style test 2026-11-06): the fact itself
    (re.compile(r"\A\s*Yang\s+tersedia\s+(?:adalah\s+)?bahwa\s+(\w)"), lambda m: m.group(1).upper()),
)


def _present(text: Text) -> str:
    """The message as the user reads it: no "basis data", an unrecorded thing "belum tersedia" (_NO_INFO)."""
    for pattern, repl in _PRESENT_RULES:
        text = pattern.sub(repl, text)
    text = _drop_contradictory_no_link(text)
    return text


# A message that only says its writer wants to ask, whatever intent NLU gives it: "saya mau nanya" was read as pamit and
# got the goodbye, "mau nanya dong" nlu_fallback, "saya mau nanya lagi" tanya_sebutan_lain (bot test 2026-11-05), and the
# sapa ones ("mau tanya dong", "boleh tanya?") got the greeting alone
_ASK_PARTICLE = (r"(?:dong|donk|nih|ya|yah|kak|kakak|min|sesuatu|lagi|bentar|sebentar|sedikit|dikit|gak|ga|nggak|ngga|"
                 r"tidak|kah|deh|sih|boleh|bisa)")
_WANTS_TO_ASK_RE = re.compile(
    r"\W*(?:(?:halo|hallo|helo|hai|hi|hello|hey|permisi|om\s+swastiastu|swastiastu|selamat\s+(?:pagi|siang|sore|malam)"
    r"|kak|kakak|min|admin|mas|mbak|bli|bang|pak|bu)\W+)*"
    r"(?:(?:saya|aku|aq|gue|gw|kami)\s+)?(?:(?:mau|ingin|pengen|pingin|pgn|boleh|bisa|izin|ijin|numpang)\s+)?"
    rf"(?:tanya|nanya|bertanya|tanyain|nanyain)(?:\W+{_ASK_PARTICLE})*\W*"
    rf"|\W*(?:ada\s+)?(?:yang\s+)?(?:mau|ingin|pengen)\s+(?:saya|aku|gue)\s+tanya(?:kan|in)?(?:\W+{_ASK_PARTICLE})*\W*",
    re.I)


# a request to say the last answer more simply, naming nothing: "bisa jelasin lebih simpel?" got "Maaf, saya tidak
# menangkap istilah spesifik dari pertanyaan Anda." (style test 2026-11-07)
_SIMPLER_RE = re.compile(
    r"\W*(?:(?:bisa|boleh|tolong|coba|mohon|bisakah)\s+)?(?:(?:di)?(?:jelas(?:in|kan|kin)|terangin|terangkan|ulang(?:i|in)?)"
    r"\s+(?:lagi\s+)?)?(?:dengan\s+|secara\s+|dgn\s+|yang\s+|yg\s+)?(?:lebih\s+)?(?:simpel|simple|sederhana|singkat|ringkas|"
    r"gampang|pendek)(?:nya)?(?:\s+(?:lagi|dong|ya|kak|aja|saja|sih))*\W*"
    r"|\W*(?:(?:bisa|boleh|tolong|coba|mohon)\s+)?(?:di)?(?:singkat|ringkas|sederhana)(?:kan|in)(?:\s+(?:lagi|dong|ya|kak|aja|"
    r"saja))*\W*|\W*(?:jadi\s+)?(?:intinya|singkatnya|ringkasnya)(?:\s+(?:apa|gimana|bagaimana))?(?:\s+(?:dong|ya|kak))*\W*",
    re.I)


def _simpler_answer(tracker: Tracker) -> Optional[str]:
    """The last answer said short: its first sentence, and the heads of a list it announced ("Namun, ada penekanan
    khusus pada dua aspek ...: Mapegat dan Tirta Pangentas")."""
    msg = tracker.latest_message.get("text") or ""
    if not _SIMPLER_RE.fullmatch(msg) or _mentioned_terms(msg, get_resolver())[0]:
        return None
    last = _last_bot_utterance(tracker)
    if not last or last == _INVITATION or last.startswith(("Om Swastiastu", "Maaf, saya")):
        return None
    lines = [x.strip() for x in last.split("\n") if x.strip()]
    item = re.compile(r"(?:\d+[.)]|[-*•])\s*\**([^:\n]{2,60}?)\**\s*:")
    out = []
    for i, line in enumerate(lines):
        if i == 0 and len(_sentences(line)) > 1 or not line.endswith(":"):
            if i == 0:
                out.append(_sentences(line)[0])
            if not line.endswith(":"):
                continue
        heads = []
        for x in lines[i + 1:]:
            m = item.match(x)
            if not m:
                break
            heads.append(m.group(1).strip())
        if heads:
            lead = _sentences(line)[-1]
            out.append(f"{lead[:-1].rstrip()}: {_join_names(heads)}.")
        break
    return "Singkatnya: " + " ".join(out) if out else None


def _presented(run):
    """An action's run whose messages go out through _present. Actions call each other's run with one dispatcher:
    rewriting twice changes nothing. A message that only says it wants to ask (_WANTS_TO_ASK_RE) gets the greeting on a
    first turn and the invitation to ask, under any intent."""
    @functools.wraps(run)
    def wrapper(self, dispatcher, tracker, domain):
        if not dispatcher.messages and _WANTS_TO_ASK_RE.fullmatch(tracker.latest_message.get("text") or ""):
            if _last_bot_utterance(tracker) is None:
                dispatcher.utter_message(response="utter_sapa")
            dispatcher.utter_message(text=_INVITATION)
            return []
        simpler = None if dispatcher.messages else _simpler_answer(tracker)
        if simpler:
            dispatcher.utter_message(text=_present(simpler))
            return []
        # a reply to "Mungkin maksud Anda: X?", or "kalau Y?" after a question about X: the question it stands for is
        # what the action answers (an action calling another's run sees it already rewritten)
        if not dispatcher.messages:
            question, reply = _suggestion_reply(tracker)
            if reply:
                dispatcher.utter_message(text=_present(reply))
                return []
            question = question or _elliptic_follow_up(tracker)
            if question:
                tracker.latest_message["text"] = question
        events = run(self, dispatcher, tracker, domain)
        # a death told with nothing asked makes Ngaben the topic, so the next question needs no name: "nenek saya meninggal
        # minggu lalu" -> "apa yang harus disiapkan?" got "saya tidak menangkap istilah" (sweep 2026-11-13); not a case
        # the corpus names (a child, a body lost at sea: _carried_case keeps those)
        msg_now = tracker.latest_message.get("text") or ""
        if (not events and _told_death(msg_now) and any(_INVITATION in (m.get("text") or "") for m in dispatcher.messages)
                and not any(rx.search(msg_now) for _, rx in _SITUATION_TERMS)):
            events = _slot_events(tracker.get_slot("entity_history") or [], ["ngaben"])
        # sympathy first for a death the user tells of, once in a conversation: "anak saya meninggal umur 2 bulan" and
        # "ponakan saya meninggal sebelum potong gigi" got the rule for their case and no word of it (style test
        # 2026-11-06)
        msg = tracker.latest_message.get("text") or ""
        texts = [m for m in dispatcher.messages if m.get("text")]
        # (told, not supposed: "anak kecil yang meninggal diaben juga gak?", "kalau seorang anak ... meninggal" ask about
        # a case; the teller speaks of their own)
        if (texts and _told_death(msg)
                and not any("berduka" in (m.get("text") or "").lower() for m in texts)
                and not any("berduka" in t.lower() for t in _recent_bot_utterances(tracker, 20))):
            texts[0]["text"] = "Turut berduka cita. " + texts[0]["text"]
        for m in dispatcher.messages:
            if m.get("text"):
                m["text"] = _present(m["text"])
        return events
    return wrapper



# words that only title a god or a holy one: "dewa siwa" and "shiwa" are one name, so "apa perbedaan dewa siwa dan
# mahadewa" got no "Dewa siwa juga dikenal sebagai Shiwa." (2026-11-06)
_TITLE_WORDS = frozenset({"dewa", "dewi", "sang", "hyang", "ida", "bhatara", "batara", "betara", "ratu"})


def _without_titles(name: Text) -> Text:
    kept = [w for w in name.split() if w.lower() not in _TITLE_WORDS]
    return " ".join(kept) if kept else name


def _same_name(a: Text, b: Text) -> bool:
    """One name written two ways: a spelling variant (bh/b, sh/s, doubled letters) or a title word more or less."""
    return _ortho_key(_without_titles(a)) == _ortho_key(_without_titles(b))


def _card_cased(entity_id: Text, surface: Optional[Text] = None) -> Text:
    """A card's name (or `surface`, another way it is written) as its own definition writes it inside a sentence
    ("Panca Dewata", "Dewa Mahadewa", "usungan"); at a sentence's start only, a capital says nothing ("Usungan adalah
    ...") unless every word has one ("Ngaben Svasta"); a surface the definition never writes gives way to the name."""
    e = get_resolver().by_id.get(entity_id) or {}
    name = e.get("name") or entity_id
    text = e.get("definition") or ""
    for s in ([surface] if surface else []) + [name]:
        found = list(re.finditer(rf"(?<![\w-]){re.escape(s)}(?![\w-])", text, re.I))
        inside = [m for m in found if re.search(r"[\w,;:(]\s*$", text[:m.start()])]
        if inside:
            return inside[0].group(0)
        if found and all(w[:1].isupper() for w in found[0].group(0).split()) and " " in s:
            return found[0].group(0)
    return name


def _plain_other_name(e: Dict[str, Any], asked: Text) -> bool:
    """Another name the user asked by that is a name the card records as its own (an alias, a name its definition
    gives, an other-name edge): not a surface that only resolves to the card -- "pawintenan" (the rite) finds ekajati
    (the status it gives), and "Pawintenan adalah tingkat kesucian ... melalui upacara pawintenan" was false (AYUTHAYA
    snapshot, 2026-11-03). Not a verb form ("Dihanyutkan adalah sebutan lain untuk nganyut" opened "mengapa abu
    jenazah dihanyutkan ...", conersation.md 2026-10-02), nor a description in everyday words ("Jenazah dimandikan
    adalah sebutan lain untuk nyiramang layon", "Hari baik ngaben ...", 2026-10-08), nor a rephrasing of the name
    ("Bade tingkat ... tingkatan bade", 2026-10-08 replay)."""
    resolver = get_resolver()
    words = _WORD_RE.findall(asked.lower())
    if (_VERB_FORM_RE.match(asked) or any(_VERB_FORM_RE.match(w) for w in words)
            or all(_is_everyday_word(w, resolver) or w in _ALIAS_NAME_WORDS or _root(w) in _sentence_roots(e["name"])
                   for w in words)):
        return False
    other_name_preds = PREDICATE_FAMILIES["sebutan_lain"] - {"ADALAH"}
    recorded = (list(e.get("aliases") or []) + _definition_other_names(e)
                + [r["target"] for r in e.get("relationships") or []
                   if r.get("relation") in other_name_preds and r.get("target") and not r.get("variant_op")])
    # (a recorded name with or without its title word counts: "dewa pitara" is the card's "(Sang Dewa Pitara)", and
    # "bedanya sama dewa pitara apa?" got an answer about Dewa Hyang that never said it is dewa pitara -- plan #31)
    return any(_ortho_key(asked) == _ortho_key(n) or _same_name(asked, n) for n in recorded)


# a clause that speaks of names: the asked name may not take the KB name's place there ("Atma Wedana adalah nama
# resminya menurut pustaka" must not become "Ngerorasin adalah nama resminya")
# ("dengan kata lain" is "in other words")
_NAME_TALK_RE = re.compile(r"\b(?:nama\w*|sebutan\w*|disebut|dikenal|istilah\w*|(?<!dengan\s)kata|resmi\w*)\b", re.I)
_PAREN_RE = re.compile(r"\([^()]*\)")
_NAMES_LIST_RE = r"\s*\((?:disebut\s+juga|juga\s+disebut|dikenal\s+(?:juga\s+)?sebagai)\s+"


def _all_synonyms(e: Dict[str, Any], asked: Text) -> List[str]:
    """All recorded synonyms / other names of `e` (canonical name, aliases, definition names,
    graph relationships), excluding `asked` and spelling variants of `asked`, with canonical name first."""
    name = e["name"]
    card = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", e.get("definition") or "", re.I)
    name_cased = card.group(0) if card else " ".join(w.capitalize() for w in name.split())

    other_name_preds = PREDICATE_FAMILIES.get("sebutan_lain", set()) - {"ADALAH"}
    raw_syns = [name_cased]
    raw_syns.extend(e.get("aliases") or [])
    raw_syns.extend(_definition_other_names(e))
    for rel in e.get("relationships") or []:
        if rel.get("relation") in other_name_preds and rel.get("target") and not rel.get("variant_op"):
            raw_syns.append(rel["target"])

    asked_key = _ortho_key(asked)
    seen = {asked_key}
    synonyms = []
    for s in raw_syns:
        s_clean = s.strip()
        k = _ortho_key(s_clean)
        if not s_clean or k in seen or len(s_clean.split()) > 4:
            continue
        if _same_name(s_clean, asked):
            continue
        seen.add(k)
        cased_syn = " ".join(w.capitalize() for w in s_clean.split()) if s_clean.islower() else s_clean
        synonyms.append(cased_syn)
    return synonyms


def _format_synonyms_phrase(synonyms: List[str]) -> str:
    """Format synonyms as: '(disebut juga A, B, atau C)'"""
    if not synonyms:
        return ""
    if len(synonyms) == 1:
        return f"(disebut juga {synonyms[0]})"
    elif len(synonyms) == 2:
        return f"(disebut juga {synonyms[0]} atau {synonyms[1]})"
    else:
        joined = ", ".join(synonyms[:-1])
        return f"(disebut juga {joined}, atau {synonyms[-1]})"


def _in_asked_names(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text = "") -> str:
    """The answer in the name the user asked by. When the user asks about a term X by an alias/synonym,
    the bot answers using term X first and immediately explains all synonyms of X, replacing references
    to the canonical name with X."""
    resolver = get_resolver()
    for e in enriched:
        asked, name = e.get("asked_as"), e["name"]
        if not asked or _ortho_key(asked) == _ortho_key(name) or not _plain_other_name(e, asked):
            continue
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", user_msg, re.I):
            continue
        card = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", e.get("definition") or "", re.I)
        name_cased = card.group(0) if card else name[:1].upper() + name[1:]

        def cased(token: str) -> str:
            if not token[:1].isupper():
                return asked.lower()
            return " ".join(w[:1].upper() + w[1:] for w in asked.split()) if all(
                w[:1].isupper() for w in token.split()) else asked[:1].upper() + asked[1:]
        held = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I)
        longer = sorted((s for s in resolver.surface if s != name.lower() and held.search(s)), key=len, reverse=True)
        masks: Dict[str, str] = {}

        def mask(m: "re.Match") -> str:
            key = f"\x00{len(masks)}\x00"
            masks[key] = m.group(0)
            return key
        out = answer
        for s in longer:
            out = re.sub(rf"(?<![\w-]){re.escape(s)}(?![\w-])", mask, out, flags=re.I)
        asked_rx = re.compile(rf"(?<![\w-]){re.escape(asked)}(?![\w-])", re.I)

        def name_clause(s: str) -> str:
            # the KB name opening a clause that gives the card's other names takes the asked name's place there too, the
            # KB name joining the names: "Atma Wedana juga memiliki sebutan lain seperti Ngroras atau Patileman" asked
            # as ngerorasin -> "Ngerorasin juga memiliki sebutan lain seperti Atma Wedana, Ngroras atau Patileman"
            # (plan #31: the asked name holds through the whole answer). Not "Atma Wedana adalah nama resminya ...".
            m = re.match(rf"(\s*(?:[^,]{{1,30}},\s*)?)({held.pattern})(?=\s+(?:juga\s+|pun\s+|sering\s+)?(?:memiliki|"
                         rf"mempunyai|dikenal|disebut|bernama))", s, re.I)
            if not m:
                return s
            rest = s[m.end():]
            if asked_rx.search(rest):
                rest = asked_rx.sub(lambda t: name_cased, rest, count=1)
            else:
                lst = re.search(r"\b(?:seperti|yaitu|yakni|antara\s+lain|sebagai|dengan\s+nama|dengan|disebut(?:\s+juga)?)"
                                r"\s+(?=[A-Za-z])", rest, re.I)
                if not lst:
                    return s
                after = rest[lst.end():]
                many = re.match(r"[^,.;]+?(?:\s+(?:atau|dan)\s+|,\s*)\S", after)
                rest = rest[:lst.end()] + name_cased + (", " if many else " atau ") + after
            return m.group(1) + cased(m.group(2)) + rest

        def clause(m: "re.Match") -> str:
            s = m.group(0)
            # ("X adalah sebutan bagi <who>" defines X, and holds for every name of it: "Dewa Hyang (Sang Dewa Pitara)
            # adalah sebutan bagi leluhur ..." asked as dewa pitara -- plan #31)
            # (anywhere in the clause: "Atma adalah roh ..., sedangkan Dewa Hyang adalah sebutan bagi leluhur ..." kept
            # Dewa Hyang and never said it is the dewa pitara asked about, Tier B on Qwen 2026-11-13)
            defines = re.search(rf"{held.pattern}\s*(?:\([^)]*\)\s*)?(?:adalah|merupakan|ialah)\s+(?:sebutan|istilah)\s+"
                                rf"(?:bagi|untuk)\b", s, re.I)
            if _NAME_TALK_RE.search(_PAREN_RE.sub(" ", s)) and not defines:
                return name_clause(s)
            parens: List[str] = []

            def keep(p: "re.Match") -> str:
                # a bracket is where the other names go: one naming the asked name names the KB name instead (unless
                # it names both), and the KB name stays in any bracket
                b = p.group(0)
                if asked_rx.search(b) and not held.search(b):
                    b = asked_rx.sub(lambda t: name_cased if t.group(0)[:1].isupper() else name.lower(), b)
                parens.append(b)
                return f"\x01{len(parens) - 1}\x01"
            s = _PAREN_RE.sub(keep, s)
            s = held.sub(lambda t: cased(t.group(0)), s)
            return re.sub(r"\x01(\d+)\x01", lambda p: parens[int(p.group(1))], s)
        # clauses end at a colon too: "Perbedaan utama antara Atma Wedana dan Ngangsen ...: Atma Wedana adalah nama
        # resmi ..." kept the KB name in the opening because its second half speaks of names (Tier B 2026-11-03)
        out = re.sub(r"[^.!?;:\n]+[.!?;:]*", clause, out)
        for key, value in masks.items():
            out = out.replace(key, value)

        # (only names the answer does not say already: the other-names template's "Ngerorasin juga dikenal sebagai Atma
        # Wedana, ..." got them twice, once in a bracket -- 2026-11-12)
        bare = _PAREN_RE.sub(" ", out)
        syns = [x for x in _all_synonyms(e, asked)
                if not re.search(rf"(?<![\w-]){re.escape(x)}(?![\w-])", bare, re.I)]
        phrase = _format_synonyms_phrase(syns) if syns else ""
        listed = re.search(rf"(?<![\w-]){re.escape(asked)}{_NAMES_LIST_RE}[^)]*\)", out, re.I)
        # the answer's own "<asked> juga memiliki sebutan lain seperti A atau B" takes the names it lacks, so they are
        # not split between it and a bracket (plan #31)
        own_list = re.search(rf"(?<![\w-]){re.escape(asked)}\s+(?:juga\s+(?:disebut|dikenal\s+sebagai)\s+|(?:juga\s+)?"
                             rf"(?:memiliki|mempunyai)\s+(?:beberapa\s+)?(?:sebutan|nama)\s+lain(?:nya)?\s+(?:seperti|yaitu|"
                             rf"yakni|antara\s+lain)\s+)"
                             r"(?P<l>(?-i:[A-Z][\w-]*(?:\s+[A-Z][\w-]*)*)(?:(?:,\s*(?:atau\s+|dan\s+)?|\s+atau\s+|\s+dan\s+)"
                             r"(?-i:[A-Z][\w-]*(?:\s+[A-Z][\w-]*)*))*)", out, re.I)
        if syns and own_list and not listed:
            items = [x.strip() for x in re.split(r",|\s+atau\s+|\s+dan\s+", own_list.group("l")) if x.strip()] + syns
            out = out[:own_list.start("l")] + ", ".join(items[:-1]) + ", atau " + items[-1] + out[own_list.end("l"):]
            syns, phrase = [], ""
        if listed:
            # the card's own "(disebut juga ...)" list after the asked name stays, the KB name put first in it when
            # missing ("apa itu upacara ngerorasin" lost Atma Wedana, Ngroras and Patileman when it was rebuilt)
            if not held.search(listed.group(0)):
                opening = re.match(rf".*?{_NAMES_LIST_RE}", listed.group(0), re.I | re.S).end()
                at = listed.start() + opening
                out = f"{out[:at]}{name_cased}, {out[at:]}"
        elif phrase:
            # (not in a "Yang tersedia tentang <asked>:" heading: "Yang tersedia tentang dewa pitara (disebut juga Dewa
            # Hyang): Dewa Pitara (Sang Dewa Hyang) ..." -- plan #31)
            m_first = next((x for x in re.finditer(rf"(?<![\w-]){re.escape(asked)}(?![\w-])", out, re.I)
                            if not re.match(r"\s*:", out[x.end():])), None)
            if m_first:
                # (a bracket of its own after the name already gives its other forms: "Bedawang nala (badawang nala,
                # bhadawang nala, badawangnala)")
                if not re.match(r"\s*\(", out[m_first.end():]):
                    out = out[:m_first.end()] + f" {phrase}" + out[m_first.end():]
            elif not _same_name(asked, name):
                # the asked name is nowhere in the answer: its other names end the first paragraph ("Ngerorasin
                # (disebut juga ...) Pitra Yadnya lanjutan ..." was no sentence)
                first, sep, rest = out.partition("\n\n")
                listed = _join_names(syns).replace(" dan ", " atau ") if len(syns) > 1 else syns[0]
                out = (f"{first.rstrip()} {cased(asked[:1].upper() + asked[1:])} juga dikenal sebagai {listed}."
                       f"{sep}{rest}")
        answer = out
    return _short_name_brackets(answer)


_NAMES_BRACKET_RE = re.compile(r"\s*\((?:disebut\s+juga|juga\s+disebut|dikenal\s+(?:juga\s+)?sebagai|juga\s+dikenal\s+"
                               r"sebagai)\s+([^()]+)\)", re.I)


def _short_name_brackets(answer: Text) -> Text:
    """At most two other names in a bracket inside a sentence; a longer list becomes one short sentence after the first
    paragraph (plan #31, 2026-11-13): "... sedangkan Nyekah (disebut juga Atma Wedana, Ngerorasin, Ngroras, Patileman,
    atau Pangroras) adalah ..." -> "... sedangkan Nyekah adalah ...", then "Nyekah juga disebut Atma Wedana, Ngerorasin,
    Ngroras, Patileman, atau Pangroras." Only a bracket after a KB name as written; list items keep theirs."""
    if "(" not in answer:
        return answer
    resolver = get_resolver()
    notes: List[str] = []

    def repl(m: "re.Match") -> str:
        names = [x.strip(" .") for x in re.split(r",|\s+atau\s+|\s+dan\s+", m.group(1)) if x.strip(" .")]
        if len(names) <= 2:
            return m.group(0)
        # (a name or alias as written, or a name the resolver pins to its card: "Nyekah"; not "satu jenis Ngerorasin")
        words = re.findall(r"[\w-]+", m.string[:m.start()])[-4:]
        owner = next((" ".join(words[-n:]) for n in range(len(words), 0, -1)
                      if " ".join(words[-n:]).lower() in resolver.surface
                      or " ".join(words[-n:]).lower() in resolver.force_merge), None)
        if not owner:
            return m.group(0)
        note = f"{_cap(owner)} juga disebut {', '.join(names[:-1])}, atau {names[-1]}."
        if note not in notes:
            notes.append(note)
        return ""
    # (each note after the paragraph that held its bracket: the opening's after the opening; one deep in a list answer
    # next to its own paragraph, not far above it)
    out = []
    for p in re.split(r"(\n+)", answer):
        if p.startswith("\n") or _LIST_ITEM_RE.match(p):
            out.append(p)
            continue
        before = len(notes)
        p = _NAMES_BRACKET_RE.sub(repl, p)
        out.append(p + ("\n\n" + " ".join(notes[before:]) if len(notes) > before else ""))
    if not notes:
        return answer
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()


def _with_note(note: Text, answer: Text) -> str:
    """A note in front of the answer: on its own line before a list ("... sebutan lain untuk nawa
    dewata. 1. Dewa Iswara ..." ran the note into the first item, 2026-10-15), else a space. Not before a
    miss: "Upakara adalah sebutan lain untuk banten. Maaf, banten untuk wayang belum tercatat ..." explained a
    word the answer then says nothing about (7 in the LLM comparison, 2026-10-20)."""
    if not note or re.match(r"\s*Maaf\b", answer):
        return answer
    return note + ("\n" if re.match(r"\s*(?:\d+[.)]|[-*•])\s", answer) else " ") + answer


# Aspect words the extraction LLM sometimes glues onto the term: "apa warna besi"
# -> "warna besi", which resolves to nothing (regression 2026-09-24). KbResolver's
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
    parts = [s for s in _SENT_PART_RE.findall(answer) if s.strip()
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
    said = set().union(*(_tier_numbers(s) for s in _SENT_PART_RE.findall(answer))) if answer else set()
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
                             "dimulai", "dipimpin", "memimpin", "dipuput", "memuput",
                             # ("apa yang harus disiapkan?" after a told death, Tier B 2026-11-13)
                             "disiapkan", "dipersiapkan", "disiapin", "disediakan", "dibutuhkan", "dibutuhin",
                             "diperlukan"})
# the modal such a verb may come with ("apa yang harus disiapkan?")
_ELLIPSIS_MODALS = frozenset({"harus", "perlu", "mesti", "musti"})
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
    # ... nor one after a word of a named term's own name: "bade itu ada tingkatannya gak?" named tingkatan bade by
    # "tingkatannya", so "bade itu" read as a bare "itu" and the topic before (lembu) went first (bot test 2026-11-05)
    named += [[w] for m, _ in mentioned for w in m.name.lower().split() if len(w) >= 4]
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


# Balinese everyday words and their Indonesian word: "kalau bisa di laut kenapa ada yang melakukan di tukad?" after
# nganyut lost its topic over "tukad" (user's live session, 2026-11-10). Read as everyday words only when they are no
# word of a KB name (setra, layon, sawa and segara are cards); _card_uses reads all of them as their Indonesian word.
_BALINESE_SYNONYMS: Dict[str, str] = {
    "tukad": "sungai",
    "pasih": "laut",
    "segara": "laut",
    "setra": "kuburan",
    "layon": "jenazah",
    "sawa": "jenazah",
}


def _is_everyday_word(word: str, resolver) -> bool:
    """In the common-word list (6k words of a formal corpus), or sharing a root with one of
    them: the list has "menghindari" but not "dihindari", "gigi" but not "giginya". Its spoken forms too
    (_colloquial_forms)."""
    global _EVERYDAY_ROOTS
    if _EVERYDAY_ROOTS is None:
        _EVERYDAY_ROOTS = frozenset(_root(w) for w in resolver.common_words)
    wl = word.lower()
    if wl in _BALINESE_SYNONYMS and _ortho_token(wl) not in resolver.name_tokens:
        return True
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
# a body buried before its ngaben: "dikubur dulu", "ditanam sementara", "dikuburkan sebelum diaben" (L888 "dikubur atau
# dibakar titip" until the real ngaben)
_BURIED_FIRST = (r"\b(?:dikubur\w*|dipendam|ditanam|dimakamkan|mapendem|mependem)\s+(?:dulu|dahulu|terlebih\s+dahulu|"
                 r"duluan|sementara|sebelum\s+(?:di)?aben\w*)\b")
# a situation term that stands for a corpse word the message also names: the question is about the act
_SITUATION_REPLACES = {t: {"layon", "jenazah", "sawa"} for t in ("nyiramang_layon", "pangringkes", "ngaben")}
# ... and the family's part in Ngaben is the yajamana's: Ngaben named beside it is the setting, and its card crowded out
# the acts' own cards ("apa peran keluarga dalam ngaben" got "Muspa pamitan: dilakukan oleh yajamana." and nothing more,
# 2026-11-12)
_SITUATION_REPLACES["yajamana"] = {"ngaben"}
# "saat ada yang meninggal", "kalau orang tua wafat", "saat ada kematian" ("siapa yang harus dihubungi pertama kali saat
# ada kematian?" named nothing and got "saya tidak menangkap istilah", style test 2026-11-07)
_WHEN_DIES = (r"\b(?:saat|ketika|waktu|kalau|kalo|jika|bila|begitu|setelah|sesudah|pas)\b[^.?!]{0,30}?"
              r"\b(?:meninggal|wafat|mati|berpulang|kematian)\b")
# a month or more ("lebih dari sebulan", "sudah satu bulan", "berbulan-bulan")
_MONTH_KEPT = (r"(?:\b(?:lebih\s+dari|lewat(?:\s+dari)?|di\s+atas|sudah|udah|telah|sampai|hingga)\s+(?:se|satu\s+)bulan\b"
               r"|\bberbulan-bulan\b)")
# a family that cannot afford a Ngaben, or a cheaper way to hold one: about ngaben, or the family's own means ("kalo
# keluarganya gak mampu gimana dong" names no term, human test 2026-11-03)
_CANNOT_AFFORD_RE = re.compile(
    r"^(?=.*\b(?:ng|di)?aben)(?=.*(?:\b(?:hemat|murah|irit|terjangkau|kurang\s+mampu|miskin)\b"
    rf"|\b{_NOT}\s+mampu\b|\b{_NOT}\s+(?:ada|punya|cukup)\s+{_MONEY}|\b{_MONEY}\s+(?:ditanggung\s+)?bersama\b))"
    rf"|\b(?:keluarga\w*|orang|warga)\b[^.?!]{{0,40}}?\b(?:(?:{_NOT}|kurang)\s+mampu|miskin)\b", re.I | re.S)
# Bali's regencies and towns, and its two traditions (a user compares practice between them)
_BALI_PLACE = (r"(?:karangasem|amlapura|denpasar|badung|kuta|mengwi|gianyar|ubud|tabanan|bangli|klungkung|semarapura|"
               r"nusa\s+penida|buleleng|singaraja|jembrana|tenganan|trunyan|"
               r"bali\s+(?:utara|selatan|timur|barat|tengah|aga|dataran))")
# A situation the user describes in everyday words, and the term the corpus names for it: what the
# bge-m3 meaning search found until 2026-10-13 (removed with Ollama), now decided in code and added
# before the message's own terms. Each pattern follows the corpus's own wording of the case.
_MOUTH_FILL_RE = re.compile(
    r"\bmulut\w*\b[^.?!]{0,40}?\b(?:di)?(?:isi|masukkan|masukin|taruh|taruhkan|letakkan|beri|kasih|sisipkan|sumbat|"
    r"pasang)\w*\b|\b(?:di)?(?:masukkan|masukin|taruh|letakkan|sisipkan|sumbatkan|pasang)\w*\s+(?:\w+\s+){0,2}?"
    r"(?:(?:ke|di|pada)\s+)?(?:dalam\s+)?mulut\w*", re.I)
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
                                 # (abroad is far away too: "ngaben apa yang cocok untuk orang yang meninggal di luar
                                 # negeri?" named ngaben alone and got "belum tersedia", style test 2026-11-07)
                                 r"|\bmeninggal\s+(?:di|pas|saat|waktu|ketika|selama)\s+(?:perantauan|rantau|merantau|"
                                 r"luar\s+(?:negeri|negri|bali|pulau)|negeri\s+orang)\b",
                                 re.I)),
    # L888/L934/L958: a body is "dikubur atau dibakar titip" until the real ngaben; L928: Ngaben is put off
    # for its cost. "belum ada biaya buat ngaben, jenazahnya sementara diapain?"
    ("upacara ngaben titip", re.compile(rf"\b(?:ditunda|menunda|dititip\w*|nitip)\b"
                                        r"|\bbelum\s+(?:bisa|sempat|mampu)\s+(?:segera\s+)?(?:di)?aben\b"
                                        rf"|\b{_NOT}\s+(?:ada|punya|cukup)\s+{_MONEY}[^.?!]*\bjenazah"
                                        # not "jenazah sementara diletakkan di bale" (a stage)
                                        r"|\bjenazah\w*\s+sementara\s+(?:diapa\w*|dikubur\w*|ditanam|disimpan|gimana|"
                                        r"bagaimana)|" + _BURIED_FIRST, re.I)),
    # ... and the later burning of the buried body's bones: asti wedana ("pembakaran tulang belulang jenazah yang
    # sebelumnya telah dikubur"). "kalau jenazahnya dikubur dulu boleh gak?" named jenazah alone and got "Ya, boleh,
    # tetapi hanya untuk jenazah bayi" (bot test 2026-11-05)
    # (and a body buried long ago: "nenek saya sudah dikubur 5 tahun lalu" got "Maaf, saya hanya melayani ...", style
    # test 2026-11-06)
    ("asti wedana", re.compile(_BURIED_FIRST + r"|\b(?:sudah|udah|telah)\s+(?:lama\s+)?(?:di)?(?:kubur|makamkan|tanam|"
                               r"pendam)\w*\b|\b(?:di)?(?:kubur|makamkan)\w*\s+(?:sejak\s+)?\d+\s+tahun\b", re.I)),
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
    # the family's own part: the yajamana, "si Yajamana alias sang mayadnya sekeluarga" (L2287; ngaben MELIBATKAN "yajamana,
    # yaitu keluarga yang punya upacara"), whose acts the graph holds (sembah bhakti, mesulub, muspa pamitan, the
    # lancingan, tirtha penembak, punia; sid 902018-902023). "apa tugas keluarga?" after Ngaben's participants got "belum
    # tersedia" (2026-11-12). Not the first step after a death (wawu lampus), nor what to prepare (sarana).
    ("yajamana", re.compile(r"^(?!.*\b(?:pertama|awal\w*|segera|langkah)\b)(?:.*\b(?:tugas|peran(?:an)?|kewajiban|"
                            r"tanggung\s+jawab)(?:nya)?\s+(?:dari\s+|para\s+|pihak\s+|si\s+)?keluarga\b"
                            r"|.*\bapa\s+(?:saja\s+|aja\s+)?yang\s+(?:harus\s+|wajib\s+|perlu\s+|mesti\s+)?"
                            r"(?:dilakukan|dikerjakan)\s+(?:oleh\s+)?(?:pihak\s+)?keluarga\b"
                            r"|.*\bkeluarga\w*\s+(?:harus\s+|wajib\s+|perlu\s+|mesti\s+)?(?:ngapain|ngapa\s+aja|"
                            r"berbuat\s+apa|melakukan\s+apa)\b)", re.I | re.S)),
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
    # Two places of Bali compared: "apakah ngaben di karangasem sama dengan di denpasar?" got only "Karangasem belum
    # tersedia" and Denpasar's krematorium (bot test 2026-11-05). Named places only: "banten di ngaben sama dengan di
    # atma wedana?" compares two rites.
    ("desa kala patra", re.compile(r"\b(?:semua|setiap|tiap|seluruh|masing-masing|tiap-tiap|antar)\s+(?:desa|daerah|"
                                   r"tempat|wilayah|banjar|kabupaten)\b"
                                   r"|\b(?:berbeda-beda|beda-beda|bervariasi|variasi)\b"
                                   r"|\b(?:desa|daerah)\s+(?:lain|yang\s+berbeda)\b"
                                   rf"|^(?=.*\b(?:sama|beda\w*|berbeda|perbedaan|mirip|serupa)\b)"
                                   rf"(?=.*\b{_BALI_PLACE}\b.*\b{_BALI_PLACE}\b)", re.I | re.S)),
    # Sembah bhakti's card: "Yang pantang ikut menyembah pitara: wanita yang sedang datang bulan, wanita hamil atau yang
    # masih menyusui bayi, ..." (L1449). "apakah wanita hamil boleh ikut ngaben?" named ngaben alone and got its miss
    # three times (bot test 2026-11-05)
    ("sembah bhakti", re.compile(r"\b(?:hamil|haid|menstruasi|datang\s+bulan|menyusui)\b"
                                 # ... and who may worship the dead at all: "siapa yang tidak boleh menyembah jenazah?",
                                 # "kenapa orang yang lebih tua tidak boleh menyembah jenazah?" got "belum tersedia" --
                                 # the card gives who and why (sid 901985; style test 2026-11-06)
                                 r"|\b(?:menyembah|nyembah|disembah|sembahyang|bersembahyang|sembah)\s+(?:kepada\s+|ke\s+)?"
                                 r"(?:jenazah|mayat|layon|sawa|mendiang|pitara|pitra|almarhum\w*|orang\s+yang\s+meninggal)\b",
                                 re.I)),
    # L891 "Nyekeh berarti jenazah dibaringkan di rumah adat dalam jangka waktu agak lama": "jenazah boleh disimpan
    # lama sebelum diaben?" got "Tidak, jenazah tidak boleh disimpan lama" (style test 2026-11-06)
    ("nyekeh", re.compile(r"\b(?:jenazah|mayat|layon|sawa)\w*\s+(?:\w+\s+){0,3}?(?:di)?(?:simpan|baringkan|semayamkan|"
                          r"inapkan|taruh)(?:kan)?\s+(?:\w+\s+){0,2}?(?:lama|berhari-hari|berminggu-minggu|berbulan-bulan|"
                          r"bertahun-tahun)\b", re.I)),
    # ulah pati's card "Ulah pati berarti bunuh diri" (web, approved 2026-10-29) and L162, Sang Hyang Yama's ngaben "asal
    # mati dengan benar (tidak salah ulah pati)": "orang yang meninggal karena bunuh diri boleh diaben gak?" named ngaben
    # alone and got "tidak tercatat" once that card existed (Tier B 2026-10-30)
    # ... and its "salah pati berarti mati karena kecelakaan": "bagaimana kalau meninggal karena kecelakaan?" named nothing
    # and got "saya tidak menangkap istilah" (style test 2026-11-07)
    ("ulah pati", re.compile(r"\b(?:mem)?bunuh\s+diri\b|\bsalah\s+pati\b"
                             r"|\b(?:meninggal|mati|wafat|tewas|korban)\b[^.?!]{0,30}?\bkecelakaan\b"
                             r"|\bkecelakaan\b[^.?!]{0,30}?\b(?:meninggal|mati|wafat|tewas)\b", re.I)),
    # the ash taken to the sea or a river is nganyut, whose card says why (L1879, L1882): "kenapa abu jenazah dibuang
    # ke laut?" named abu alone and got "belum tersedia" (style test 2026-11-06)
    ("nganyut", re.compile(r"\babu\w*\s+(?:\w+\s+){0,3}?(?:di)?(?:buang|hanyut|larung|tabur|bawa)\w*\s+(?:\w+\s+){0,2}?"
                           r"ke\s+(?:laut|sungai|segara|pantai)\b", re.I)),
    # what goes into the corpse's mouth: monmon at the bathing and pangringkes (L213, L852), the Panca Datu bundle at
    # masesalin (L1235): "kalau mulutnya diisi apa?" got eteh-eteh in general (style test 2026-11-06)
    ("monmon", _MOUTH_FILL_RE),
    ("masesalin", _MOUTH_FILL_RE),
    # the glass on the corpse's eyes is pecahan kaca, whose card says why (L103 "Kedua mata diisi cermin/kaca", L213
    # "kaca diletakkan pada mata", L3148): "kenapa matanya ditutup kaca?" after eteh-eteh got eteh-eteh's miss (style
    # test 2026-11-07)
    ("pecahan kaca", re.compile(r"\b(?:kaca|cermin)\b[^.?!]{0,40}?\bmata(?:nya)?\b"
                                r"|\bmata(?:nya)?\b[^.?!]{0,40}?\b(?:kaca|cermin)\b", re.I)),
    # a corpse kept a month or more is masekeh ("dibaringkan ... sekurang-kurangnya satu bulan"); said with no corpse
    # word after a talk of a death, see _carried_case
    ("masekeh", re.compile(r"\b(?:jenazah|mayat|layon|sawa|meninggal)\w*\b[^.?!]{0,50}?" + _MONTH_KEPT, re.I)),
    ("nuduk galih", re.compile(r"^(?!.*\b(?:ke\s*mana|di\s*mana|dikemana\w*)\b)(?=.*(?:"
                               r"\b(?:abis|habis|setelah|sesudah|selesai)\s+(?:\w+\s+){0,2}?(?:pembakaran|dibakar|bakar|"
                               r"kremasi|dikremasi)\b[^.?!]{0,50}?\b(?:tulang\w*|galih\w*)"
                               r"|\b(?:sisa\w*\s+tulang\w*|tulang\w*\s+sisa\w*)\b[^.?!]{0,50}?"
                               r"\b(?:pembakaran|dibakar|kremasi|diapa\w*|gimana|bagaimana)\b))", re.I | re.S)),
)


# A message that only tells something -- someone speaking of themselves, with no question, no request and no KB term:
# "bapak saya meninggal kemarin, kami orang bali tapi tinggal di jakarta" got "Maaf, saya tidak menangkap istilah
# spesifik dari pertanyaan Anda.", "halo kak, saya lagi bikin tugas tentang upacara kematian di bali" "Maaf, informasi
# tentang 'upacara kematian di bali' belum tersedia. Mungkin maksud Anda: agama hindu bali, ..." (bot test 2026-11-05).
# It gets an invitation to ask, with no extraction call. Asking about something ("mau nanya tentang ngaben suwung"),
# wanting to know or saying one does not understand is no telling: those keep the miss.
_REQUEST_CUE_RE = re.compile(
    r"\?|\b(?:apa|apakah|apaan|apanya|siapa|kapan|mana|dimana|kemana|darimana|berapa|bagaimana|gimana|gmn|kenapa|"
    r"mengapa|knp|napa|bolehkah|bisakah|haruskah|perlukah|jelaskan|jelasin|terangkan|ceritakan|ceritain|uraikan|"
    r"jabarkan|sebutkan|sebutin|tolong|mohon|minta|bantu|bantuin|tahu|tau|info|informasi|pengertian|arti|artinya|"
    r"maksud|maksudnya|paham|mengerti|ngerti|bingung)\b|\b\w+kah\b", re.I)
# (saying one wants to ask names what about: "saya mau nanya tentang ngaben suwung" keeps its miss)
_ASK_CUE_RE = re.compile(rf"{_REQUEST_CUE_RE.pattern}|\b(?:tanya|nanya|bertanya|tanyakan)\b", re.I)
_TELLER_RE = re.compile(r"\b(?:saya|aku|aq|gue|gw|kami|kita)\b", re.I)
_OPENING_GREETING_RE = re.compile(r"^\W*(?:halo|hallo|helo|hai|hi|hello|hey|om\s+swastiastu|swastiastu|permisi|salam|"
                                  r"selamat\s+(?:pagi|siang|sore|malam))\b", re.I)
_DEATH_NEWS_RE = re.compile(r"\b(?:meninggal|wafat|berpulang|tutup\s+usia|almarhum\w*|kehilangan|berduka)\b", re.I)
_INVITATION = ("Silakan tanyakan apa saja tentang upacara Ngaben dan rangkaiannya, misalnya tahapannya, sarana dan "
               "banten yang dipakai, hari baiknya, atau siapa yang memimpinnya.")


# the subject as a whole: a message that tells something and names only it asks nothing about a part of it
_BROAD_TOPICS = frozenset({"ngaben", "pitra_yadnya"})


def _tells_only(user_msg: Text) -> bool:
    """The speaker tells something of themselves and asks nothing (see _ASK_CUE_RE)."""
    return bool(_TELLER_RE.search(user_msg)) and not _ASK_CUE_RE.search(user_msg)


_SUPPOSITION_RE = re.compile(r"\W*(?:kalau|kalo|klo|jika|bila|apabila|seandainya|andaikan|misal\w*)\b", re.I)


# someone's death as a case, with who died: "kalau ada orang meninggal", "saat keluarga meninggal" -- not "kalau sudah
# meninggal", a follow-up about the topic ("caranya bagaimana kalau sudah meninggal?" after potong gigi; snapshot
# 2026-11-13). "mati" is no death word alone ("lampu mati")
_SOMEONE_DIES_RE = re.compile(
    r"\b(?:ada\s+(?:yang|orang)|orang|seseorang|anggota\s+keluarga|keluarga\w*|kerabat\w*|saudara\w*|ayah\w*|ibu\w*|"
    r"bapak\w*|nenek\w*|kakek\w*|anak\w*|suami\w*|istri\w*|teman\w*|tetangga\w*)\s+(?:\w+\s+){0,3}?(?:yang\s+)?"
    r"(?:sudah\s+|udah\s+|telah\s+|baru\s+)?(?:meninggal|wafat|berpulang)\b", re.I)


def _told_death(user_msg: Text) -> bool:
    """The speaker tells of a death of their own ("nenek saya meninggal minggu lalu"), not a supposed case ("kalau
    seorang anak ... meninggal", "anak kecil yang meninggal diaben juga gak?")."""
    return bool(_DEATH_NEWS_RE.search(user_msg) and _TELLER_RE.search(user_msg) and not _SUPPOSITION_RE.match(user_msg))


def _death_case(user_msg: Text) -> bool:
    """A death the message tells of, or a case of someone dying it asks about (_SOMEONE_DIES_RE)."""
    return _told_death(user_msg) or bool(_SOMEONE_DIES_RE.search(user_msg))


def _invitation(user_msg: Text) -> str:
    """The reply to a message that asks nothing: a greeting back, sympathy for a death it tells of, then what to ask."""
    return " ".join((["Om Swastiastu."] if _OPENING_GREETING_RE.search(user_msg) else [])
                    + (["Turut berduka cita."] if _DEATH_NEWS_RE.search(user_msg) else []) + [_INVITATION])


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
    tracker: Optional[Any] = None


def _recent_compared_terms(s: _Scan) -> list:
    """The two most recently discussed distinct terms from the conversation history,
    for a comparison, difference, or similarity question that names neither subject
    (e.g. 'apa perbedaannya?', 'apa perbedaan keduanya?', 'apa persamaannya?').
    Returns [older_match, newer_match] if two distinct entities are found, else []."""
    resolver = s.resolver
    names: List[str] = []
    if s.current_entity:
        names.append(s.current_entity)
    for h in reversed(s.entity_history or []):
        if h and h not in names:
            names.append(h)

    # Also check prior turns if history had fewer than 2 terms
    if len(names) < 2:
        prior_turns = s.turns[:-1] if len(s.turns) > 1 else []
        for t in reversed(prior_turns):
            mentioned, _ = _mentioned_terms(t, resolver)
            for m, _ in mentioned:
                if m.name not in names and m.id not in names:
                    names.append(m.name)

    matches = []
    seen_ids = set()
    for name in names:
        m = resolver.resolve(name)
        if m and m.id not in seen_ids:
            matches.append(m)
            seen_ids.add(m.id)
        if len(matches) == 2:
            break

    if len(matches) == 2:
        # Return in chronological order [older, newer] so the earlier entity comes first
        return [matches[1], matches[0]]
    return matches


# --- the user's reply to the bot's "Mungkin maksud Anda: X?" (user, 2026-11-10: "the bot ask if the user meant 'satya'
# ..., but when the user confirms that it is indeed what the user mean, the bot did not give the correct answer"; and
# 2026-11-12: "i want the bot to ask back when it is not sure ... and it can understand user's pushback or
# confirmations"). Read in _presented, under any intent NLU gives the reply.
_SUGGESTED_RE = re.compile(r"Mungkin\s+maksud\s+Anda:\s*([^?\n]+)\?", re.I)
_AFFIRM_WORDS = r"(?:iya+|iy|ya+|yap|yup|yep|yes|yoi|iyo|hooh|betul|bener|benar|tepat|ok|oke|okay|sip)"
_ORDINAL_PICK = r"(?:yang\s+)?(?:pertama|kedua|ketiga|1|2|3)"
_AFFIRM_SUGGESTION_RE = re.compile(
    rf"\W*(?:{_AFFIRM_WORDS}(?:[\s,]+(?:{_AFFIRM_WORDS}|sekali|banget))*)?[\s,]*"
    rf"(?:(?:itu|yang\s+itu|yg\s+itu|itu\s+maksud\s+(?:saya|aku|sy)|maksud\s+(?:saya|aku|sy)(?:\s+itu)?|{_ORDINAL_PICK})"
    rf"(?:[\s,]+(?:maksud\s+(?:saya|aku|sy)|ya|kak|dong|deh))*)?\W*", re.I)
_PUSHBACK_RE = re.compile(r"\W*(?:bukan|tidak|tdk|nggak|ngga|enggak|gak|ga|salah|no)\b", re.I)


def _suggestion_reply(tracker: Tracker) -> "tuple[Optional[str], Optional[str]]":
    """(question, None) when the message confirms one of the bot's last suggestions -- the user's earlier question asked
    again with that name ("siapa itu satya devi dari aolani data" -> "siapa itu satya"); (None, reply) when it pushes
    back or leaves the pick open; (None, None) when it is no reply to a suggestion."""
    last = _last_bot_utterance(tracker) or ""
    m = _SUGGESTED_RE.search(last)
    msg = tracker.latest_message.get("text") or ""
    if not m or not msg.strip():
        return None, None
    suggestions = [x.strip() for x in m.group(1).split(",") if x.strip()]
    resolver = get_resolver()
    named = [t for t, _ in _mentioned_terms(msg, resolver)[0]]
    sugg_ids = {getattr(resolver.resolve(x), "id", None) for x in suggestions}
    if _PUSHBACK_RE.match(msg) and not [t for t in named if t.id not in sugg_ids]:
        return None, ("Baik, maaf atas salah tebaknya. Istilah apa yang Anda maksud? Silakan tuliskan nama upacara, "
                      "sarana, atau istilahnya.")
    if not _AFFIRM_SUGGESTION_RE.fullmatch(msg):
        return None, None
    pick = re.search(r"\b(pertama|kedua|ketiga|1|2|3)\b", msg, re.I)
    if pick:
        i = {"pertama": 0, "1": 0, "kedua": 1, "2": 1, "ketiga": 2, "3": 2}[pick.group(1).lower()]
        if i >= len(suggestions):
            return None, None
        chosen = suggestions[i]
    elif len(suggestions) == 1:
        chosen = suggestions[0]
    else:
        # "iya" to three guesses picks none of them
        return None, f"Yang mana yang Anda maksud: {_join_names(suggestions).replace(' dan ', ' atau ')}?"
    if not resolver.resolve(chosen):
        return None, None
    prev = _previous_user_message(tracker)
    asked = re.search(r"'([^']+)'", last)
    if asked and re.search(re.escape(asked.group(1)), prev, re.I):
        question = re.sub(re.escape(asked.group(1)), chosen, prev, count=1, flags=re.I)
        # (the whole question was the missed phrase: what it is asked, as the user asked it)
        if _ortho_key(question) == _ortho_key(chosen):
            question = None
    else:
        question = None
    if not question:
        word = "siapa" if re.match(r"\W*siapa\b", prev, re.I) else "apa"
        question = f"{word} itu {chosen}"
    return question, None


# --- "kalau Y?" after a question about X: the same question about Y (user, 2026-11-12: "lets say the bot just explained
# about ceremony X, and then the user ask 'Kalau Y?' or 'Kalau Y apa?', i want the bot to understand that too")
_ELLIPTIC_OPENER_RE = re.compile(r"\W*(?:(?:nah|terus|trus|lalu|lantas|oh|oke|ok|jadi)[\s,]+)?(?:kalau|kalo|klo|kl|"
                                 r"bagaimana\s+(?:dengan|kalau)|gimana\s+(?:dengan|kalau|kalo)|gmn\s+(?:dgn|kalau|kalo)|"
                                 r"untuk|buat|terus|trus|lalu)\b", re.I)
# (no "itu" / "ini": "kalau upacara ngaben titip itu apa?" asks what it is, and was rebuilt from "bade itu ada
# tingkatannya gak?" -- snapshot 2026-11-12)
_ELLIPTIC_FILLER = frozenset("""
kalau kalo klo kl bagaimana gimana gmn dengan dgn untuk buat terus trus lalu lantas nah oh oke ok jadi apa yang sih dong
ya kak nih juga nya
""".split())


def _elliptic_follow_up(tracker: Tracker) -> Optional[str]:
    """The user's previous question again with this message's one term in place of that question's one term, when the
    message names one term and says nothing else ("kalau mamukur?", "kalo ngerorasin apa?", "terus untuk sawa
    wedana?"). None for anything else: a case follow-up ("kalau umurnya 6 bulan?") names no term, and a previous
    question with two terms, a told situation or the same term is not rebuilt."""
    msg = tracker.latest_message.get("text") or ""
    if not _ELLIPTIC_OPENER_RE.match(msg):
        return None
    resolver = get_resolver()
    found, _ = _mentioned_terms(msg, resolver)
    if len({m.id for m, _ in found}) != 1:
        return None
    term, surface = found[0]
    # every other word is filler (the leftover list holds no question words: "kalau mamukur kapan?" asks a new thing)
    rest = re.sub(rf"(?<![\w-]){re.escape(surface)}(?![\w-])", " ", msg.lower())
    if any(w not in _ELLIPTIC_FILLER for w in _WORD_RE.findall(rest)):
        return None
    # the question this one follows: the last user message that named exactly one other term (a follow-up of the same
    # kind before it is rebuilt the same way)
    users = [e.get("text") or "" for e in tracker.events if e.get("event") == "user"][:-1]
    for prev in reversed(users[-4:]):
        p_found, p_left = _mentioned_terms(prev, resolver)
        p_ids = {m.id for m, _ in p_found}
        if not p_ids:
            continue
        if len(p_ids) != 1 or term.id in p_ids or any(rx.search(prev) for _, rx in _SITUATION_TERMS):
            return None
        p_rest = re.sub(rf"(?<![\w-]){re.escape(p_found[0][1])}(?![\w-])", " ", prev.lower())
        if _ELLIPTIC_OPENER_RE.match(prev) and all(w in _ELLIPTIC_FILLER for w in _WORD_RE.findall(p_rest)):
            continue        # a bare "kalau X?" itself: the question it rebuilt lies further back
        p_surface = p_found[0][1]
        at = re.search(rf"(?<![\w-]){re.escape(p_surface)}(?![\w-])", prev, re.I)
        if not at:
            return None
        return f"{prev[:at.start()]}{surface}{prev[at.end():]}"
    return None


def _extract_and_resolve(
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    user_msg: Text,
    entity_history: List[str],
    current_entity: Optional[str] = None,
    announce_miss: bool = True,
    allow_llm: bool = True,
) -> "tuple[List[Dict[str, Any]], List[str], List[str]]":
    """Steps 1-3: LLM term extraction -> KbResolver -> Neo4j + curated-content
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
    s = _Scan(user_msg, resolver, mentioned, leftover, turns, entity_history, current_entity, tracker)
    partial = _partial_name(user_msg, mentioned, resolver)
    if partial:
        suggestions = ([] if all(_is_everyday_word(w, resolver) for w in _WORD_RE.findall(partial.lower()))
                       else resolver.suggest(partial, k=3))
        _log_unresolved(user_msg, [partial], suggestions)
        if announce_miss:
            dispatcher.utter_message(
                text=(f"Maaf, saya tidak menemukan '{partial}' di basis data. Mungkin maksud Anda: "
                      f"{', '.join(suggestions)}?") if suggestions else
                     f"Maaf, informasi mengenai '{partial}' belum tercatat di basis data.")
        return [], [partial], []
    # (naming only the subject as a whole asks nothing either: "kak aku lagi bikin tugas soal ngaben nih" got Ngaben's
    # purposes, style test 2026-11-06)
    if (all(m.id in _BROAD_TOPICS for m, _ in mentioned) and _tells_only(user_msg)
            and all(m.id in _BROAD_TOPICS for m in _message_terms(s)[0])):
        # it asks nothing (_tells_only): an invitation, not a miss -- ActionLLMFallback says it on its own
        if announce_miss:
            dispatcher.utter_message(text=_invitation(user_msg))
        return [], [], []
    raw_terms = _extracted_terms(s) if allow_llm and _needs_extraction(s) else []

    # Step 2: KbResolver maps each free-text term to a canonical KB id --
    # exact name/alias -> force_merge -> modifier-strip -> rapidfuzz.
    # (No early return on an empty LLM list any more: the message's own terms
    # (Step 2b) and the topic fallback below still apply.)
    asked_as: Dict[str, str] = {}
    typed_as: Dict[str, str] = {}
    matches, unresolved = _resolve_terms(s, raw_terms, asked_as, typed_as)
    # a failed extraction hands back the raw message (_extracted_terms): unresolved, it is no term the KB lacks --
    # whenever Groq was down, "kenapa bisa beda?" read "Informasi tentang 'kenapa bisa beda?' belum tersedia" (style test
    # 2026-11-07; a what-is question still quotes its subject, below)
    if raw_terms == [user_msg.strip().lower()]:
        unresolved = [u for u in unresolved if u != raw_terms[0]]
    own, replaced = _message_terms(s)
    # (before a carried case: after "kalau umurnya 6 bulan bagaimana?" the told baby came first, and "upacaranya namanya
    # apa?" was answered "Namanya Jenazah bayi")
    rite = None if mentioned or any(rx.search(user_msg) for _, rx in _SITUATION_TERMS) else (
        _rite_named_before(user_msg, tracker))
    if rite:
        own = [rite]
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
    # a price question about a term the extraction gave from the history: its priced cards, as for a named one
    # (_message_terms) -- "kenapa bisa mahal?" after "berapa biaya ngaben?" had Ngaben's card alone, and Qwen's prices from
    # its own memory were cut as unsupported, leaving a bare miss (style test 2026-11-07)
    if not own_order and len(matches) == 1 and _PRICE_Q_RE.search(user_msg):
        matches += [h for h in _priced_terms(matches[0]) + _cost_reason_terms(matches[0], user_msg)
                    if h.id != matches[0].id]
    # a why-follow-up about what the topic's card says is done to it: the rite the card names for that act. "kenapa ke
    # laut?" after "abunya dibawa ke mana?" had abu's card alone ("... sebelum dilarung ke laut atau sungai (nganyut)"),
    # and nganyut's stated reason (L1879) never reached the context (style test 2026-11-07)
    if not own_order and len(matches) == 1 and _WHY_Q_RE.search(user_msg):
        rite = _rite_of_act(matches[0], s.leftover)
        if rite:
            matches.append(rite)
    # a comparison/difference/similarity question ("apa perbedaannya?", "apa perbedaan keduanya?",
    # "apa persamaannya?", "apa bedanya dengan X?"): compare the two most recently discussed terms from the history
    # (not when the message names one card by two of its names: "apa bedanya ngaben dan pengabenan" compared Ngaben with
    # a term of an earlier turn -- _same_thing_answer says they are one, user 2026-11-12)
    two_names = len({_ortho_key(sf) for m, sf in mentioned}) >= 2 and len({m.id for m, _ in mentioned}) == 1
    if (_COMPARE_Q_RE.search(user_msg) or re.search(r"\bkeduanya\b", user_msg, re.I)) and not two_names:
        if not own_order:
            two = _recent_compared_terms(s)
            if len(two) == 2:
                if len(matches) < 2 or {m.id for m in matches} != {m.id for m in two}:
                    matches = two
        # (one term named, the other left out or pointed at -- not "apa perbedaan jenis-jenis ngaben?", one term's cases)
        elif len(matches) < 2 and (_OMITTED_SUBJECT_RE.search(user_msg)
                                   or re.search(r"\b(?:yang\s+)?(?:tadi|sebelumnya|sebelum\s+ini|barusan)\b", user_msg, re.I)):
            two = _recent_compared_terms(s)
            other = next((m for m in two if m.id not in {x.id for x in matches}), None)
            if other:
                matches = [other, matches[0]]
    matched_ids = {m.id for m in matches}   # before the cap: a word-meaning part counts these too
    matches = matches[:4]
    if _WORD_MEANING_RE.search(user_msg):
        matches = _with_word_parts(s, matches, matched_ids)

    if not matches:
        if not unresolved and _WHAT_IS_RE.search(user_msg):
            # a what-is question's subject is the missed term: "apa itu dewasa ayu" (everyday words, no extraction)
            # got "Maaf, saya tidak menangkap istilah spesifik ...", not what the KB does hold (bot test 2026-11-05)
            # (pointing words are no subject: "apa itu tadi?" quoted 'tadi')
            subject = re.sub(r"\b(?:sih|ya|dong|deh|kak|kah|tuh|nih|itu|ini|tersebut|tadi|maksudnya|artinya)\b|[?!.,]",
                             " ", _WHAT_IS_RE.sub("", user_msg, count=1))
            subject = " ".join(subject.split()).lower()
            if len(subject) >= 3:
                unresolved = [subject]
        suggestions = []
        for term in unresolved:
            # (none for a phrase of everyday words: "upacara pernikahan" got "Mungkin maksud Anda: mamukur, pabersihan
            # mati, sangaskara?", "anak kecil" "dulang, cili, sajen kecil?" -- style test 2026-11-06)
            if all(_is_everyday_word(w, resolver) for w in _WORD_RE.findall(term.lower())):
                continue
            suggestions.extend(resolver.suggest(term, k=3))
        suggestions = list(dict.fromkeys(suggestions))  # dedupe, keep order
        _log_unresolved(user_msg, unresolved, suggestions)
        if announce_miss:
            if not unresolved and not _REQUEST_CUE_RE.search(user_msg):
                # nothing named and nothing asked ("saya mau nanya"): what to ask, not "tidak menangkap istilah" --
                # which a request still gets ("jelaskan keduanya" with no topic)
                dispatcher.utter_message(text=_invitation(user_msg))
            elif not unresolved:
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


def _rite_of_act(topic, leftover: List[str]):
    """The rite or stage the topic's card names nearest to a word of the message ("laut" in "... dilarung ke laut atau
    sungai (nganyut)" -> nganyut), within one sentence; not Ngaben as a whole. None when no sentence has the word."""
    content, resolver = get_content(), get_resolver()
    words = [w for w in leftover if len(w) >= 4 and w not in _STOPWORDS_ID and not _WHY_Q_RE.search(w)]
    best = None
    for s in _sentences(content.best_definition(topic.id) or ""):
        spots = [m.start() for w in words for m in re.finditer(rf"\b{re.escape(w)}\b", s, re.I)]
        if not spots:
            continue
        for i in _named_terms(s):
            if i == topic.id or i in _BROAD_TOPICS or content.entity_type.get(i) not in _STAGE_TYPES:
                continue
            names = [content.entity_name.get(i, "")] + list(resolver.by_id.get(i, {}).get("aliases") or [])
            at = [m.start() for n in names if len(n) >= 3 for m in re.finditer(rf"\b{re.escape(n)}\b", s, re.I)]
            if at:
                gap = min(abs(a - p) for a in at for p in spots)
                if best is None or gap < best[0]:
                    best = (gap, i)
    if not best:
        return None
    hit = resolver.resolve(content.entity_name.get(best[1], ""))
    return hit if hit and hit.id == best[1] else None


# "the ceremony" asked without its name: "upacaranya namanya apa?"
_RITE_WORD_RE = re.compile(r"\b(?:upacara|ritual|acara|prosesi|tahap(?:an)?)(?:nya)?\b", re.I)


def _rite_named_before(user_msg: Text, tracker: Optional[Tracker]):
    """The rite or stage the bot's last answer names first, for a name question about "the ceremony" that names none:
    "upacaranya namanya apa?" after an answer on a six-month-old's Upacara Ngelungah got "Namanya Jenazah bayi", after
    one on the ashes taken to the sea (nganyut) "Namanya Abu" -- the topic's own card (style test 2026-11-07)."""
    if tracker is None or not _NAME_OF_Q_RE.search(user_msg) or not _RITE_WORD_RE.search(user_msg):
        return None
    content, resolver = get_content(), get_resolver()
    for i in _named_terms(_last_bot_utterance(tracker) or ""):
        if content.entity_type.get(i) in _STAGE_TYPES:
            hit = resolver.resolve(content.entity_name.get(i, ""))
            if hit and hit.id == i:
                return hit
    return None


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
    # guesses "correct" spelling -- that's the resolver's job (Step 2), which has
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
    - If the current input asks about a difference, comparison, or similarity
      ("apa perbedaannya", "apa bedanya", "keduanya", "persamaannya", "apa perbedaan keduanya")
      without naming the terms, return the TWO most recently discussed terms being
      compared from the recent conversation turns, not just the single current topic.
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
        # coreference/ellipsis handling in this mode, but the resolver can still
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
    # ... and a follow-up keeps the case a turn before it told: "anak saya meninggal umur 2 bulan" -> "apakah harus
    # diaben?" got "Ya, ngaben merupakan kewajiban suci", "saudara saya hilang di laut ..." -> "jenazahnya diganti
    # dengan apa?" got "disebut dengan sebutan halus layon" -- each with Ngaben's or jenazah's card alone (style test
    # 2026-11-06). The case stays first, the subject of the talk, while the follow-ups name nothing more particular.
    if not any(situated):
        for hit in reversed([h for h in _carried_case(s, mentioned) if h]):
            if not any(m.id == hit.id for m in own):
                own.insert(0, hit)
    # ... and a death spoken of in a message that asks, naming nothing, is about that death's Ngaben ("nenek saya
    # meninggal minggu lalu, apa yang harus disiapkan?", "kalau ada orang meninggal, apa yang harus disiapkan?" got "saya
    # tidak menangkap istilah", 2026-11-13); not a what-is question ("apa itu kematian?" keeps its miss)
    if not own and not any(situated) and _death_case(user_msg) and not _WHAT_IS_RE.search(user_msg):
        hit = resolver.resolve("ngaben")
        if hit:
            own.append(hit)
    for hit in reversed([h for h in situated if h]):
        if not any(m.id == hit.id for m in own):
            own.insert(0, hit)
    replaced = set().union(*(_SITUATION_REPLACES.get(h.id, set()) for h in situated if h))
    own = [m for m in own if m.id not in replaced]
    # "hari apa yang harus dihindari untuk ngaben" asks about dewasa ngaben, which holds the
    # allowed and forbidden days -- the message never names it (live crosscheck T96)
    if _asks_about_day(user_msg, _day_talk(s.current_entity, resolver)) and not any(m.id == "dewasa_ngaben" for m in own):
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
        own += [h for h in _priced_terms(own[0]) + _cost_reason_terms(own[0], user_msg) if all(m.id != h.id for m in own)]
    # "apa saja tingkatan dalam upacara ngaben" asks for nista/madya/utama, which ngaben is
    # "dilakukan berdasarkan"; the alias "tingkatan ngaben" only matches side by side, and the
    # question got ngaben's eight stages as its "tingkatan" (2026-10-08 batch). Not for a term
    # with no such edge: atma wedana's tingkatan are its kinds, bade's its tiers.
    # (and for the levels themselves: "kenapa ada tingkatan nista madya utama?" had the three cards without the one that
    # says why there are levels, "diadakan agar setiap umat dapat menempuh jalan ...", style test 2026-11-07)
    if (_LEVEL_Q_RE.search(user_msg) and not any(m.id == "tingkatan_upacara" for m in own)
            and any(f["object_id"] == "tingkatan_upacara"
                    for m in own for f in get_content().facts_by_subj.get(m.id, []))
            or own and all(get_content().is_kind_of(m.id, "tingkatan_upacara") for m in own)
            and _LEVEL_Q_RE.search(user_msg)):
        hit = resolver.resolve("tingkatan upacara")
        if hit:
            own.insert(0, hit)
    return own, replaced


# words a follow-up on a told case may name without leaving it: the case is about them
_CASE_GENERIC_IDS = frozenset({"ngaben", "jenazah", "sawa", "layon", "tulang_belulang", "atma"})
# what is done first ("apa yang harus dilakukan pertama kali?")
_FIRST_STEP_RE = re.compile(r"\b(?:pertama(?:\s+kali)?|langkah\s+(?:awal|pertama)|awalnya|duluan|terlebih\s+dahulu)\b",
                            re.I)
# how a follow-up opens: "kalau ...", "terus ...", "jadi ...", "apakah ...", "kenapa ..."
_FOLLOW_UP_CUE_RE = re.compile(r"^\W*(?:kalau|kalo|klo|jika|bila|terus|trus|lalu|jadi|berarti|apakah|kenapa|mengapa|"
                               r"knp|bagaimana|gimana|apa|boleh|bisa|harus|perlu|siapa|kapan|di\s*mana|ke\s*mana)\b", re.I)
# the words a bare what-is question has beside its term ("pitra yadnya tuh apaan", "apa yang dimaksud dengan ngaben")
_BARE_WHAT_IS_WORDS = frozenset({"apa", "itu", "ini", "ya", "kah", "yang", "dimaksud", "dengan", "maksud", "maksudnya",
                                 "arti", "artinya", "pengertian", "definisi", "adalah", "sebenarnya", "sebetulnya",
                                 "emang", "memang"})  # with _WHAT_IS_FILLER


def _bare_what_is(msg: Text, mentioned: List[tuple]) -> bool:
    """The message is its named term(s) and what-is words only. Stricter than _asks_what_it_is, which takes any
    question ending in "apa?" ("ngaben jenis apa itu?" asks a kind, not what Ngaben is)."""
    rest = msg.lower()
    for _, surface in sorted(mentioned, key=lambda p: -len(p[1])):
        rest = re.sub(rf"(?<![\w-]){re.escape(surface.lower())}(?![\w-])", " ", rest)
    words = _WORD_RE.findall(rest)
    return bool(mentioned and words) and all(w in _BARE_WHAT_IS_WORDS or w in _WHAT_IS_FILLER for w in words)


def _carried_case(s: _Scan, mentioned: List[tuple]) -> list:
    """The situation terms of the case an earlier turn told, when this message follows it up: a short message, or one
    opening like a follow-up, that names nothing beyond the case's general words (_CASE_GENERIC_IDS). Walks back over
    earlier follow-ups to the turn that told the case; a turn that named something particular ends the case."""
    def follows_up(msg: Text, names: List[tuple]) -> bool:
        return (all(m.id in _CASE_GENERIC_IDS for m, _ in names)
                and (len(_WORD_RE.findall(msg)) <= 8 or bool(_FOLLOW_UP_CUE_RE.search(msg))))
    # a message that asks nothing follows nothing up ("kak aku lagi bikin tugas soal ngaben nih"), and one that names
    # Ngaben itself with an aspect and points at nothing asks about Ngaben ("berapa tahapan ngaben?" after a burial case)
    names_rite = any(re.search(rf"(?<![\w-]){re.escape(surface)}(?![\w-])", "ngaben pangabenan pengabenan", re.I)
                     for m, surface in mentioned if m.id == "ngaben")
    # ... nor a what-is question: "pitra yadnya tuh apaan" after "anak kecil yg meninggal diaben juga gk?" got the baby
    # tiers first (snapshot 2026-11-06)
    if (not follows_up(s.msg, mentioned) or _tells_only(s.msg) or _bare_what_is(s.msg, mentioned)
            or names_rite and _aspect_families(s.msg) and not _ANAPHOR_RE.search(s.msg)):
        return []
    for prev in reversed(s.turns[:-1]):
        told = [s.resolver.resolve(name) for name, rx in _SITUATION_TERMS if rx.search(prev)]
        # the first step asked after a death the user told: wawu lampus, "tahap awal segera setelah kematian" (the wawu
        # lampus pattern, said over two turns) -- "apa yang harus dilakukan pertama kali?" after "ayah saya meninggal di
        # rumah sakit" got "saya tidak menangkap istilah" (style test 2026-11-07)
        if not any(told) and _FIRST_STEP_RE.search(s.msg) and _DEATH_NEWS_RE.search(prev):
            told = [s.resolver.resolve("wawu lampus")]
        # a month or more after a death: masekeh, a corpse kept "sekurang-kurangnya satu bulan" -- "kalau lebih dari
        # sebulan?" after "berapa lama setelah meninggal ngaben harus dilakukan?" got "belum tersedia" (style test
        # 2026-11-07)
        if (not any(told) and re.search(_MONTH_KEPT, s.msg, re.I)
                and (_DEATH_NEWS_RE.search(prev) or re.search(r"\b(?:mati|kematian|jenazah\w*|mayat)\b", prev, re.I))):
            told = [s.resolver.resolve("masekeh")]
        # any other death a turn naming nothing spoke of is that death's Ngaben: "nenek saya meninggal minggu lalu" (an
        # invitation to ask) -> "apa yang harus disiapkan?" / "berapa biayanya?" got "saya tidak menangkap istilah"
        # (sweep 2026-11-13)
        if not any(told) and _death_case(prev) and not _mentioned_terms(prev, s.resolver)[0]:
            told = [s.resolver.resolve("ngaben")]
        if any(told):
            return told
        if not follows_up(prev, _mentioned_terms(prev, s.resolver)[0]):
            return []
    return []


def _case_follow_up(tracker: Tracker, user_msg: Text) -> bool:
    """Whether the message follows up a case an earlier turn told (_carried_case), and tells none of its own."""
    resolver = get_resolver()
    if any(rx.search(user_msg) for _, rx in _SITUATION_TERMS):
        return False
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    s = _Scan(user_msg, resolver, mentioned, leftover, recent_user_turns(tracker), tracker.get_slot("entity_history") or [],
              tracker.get_slot("current_entity"), tracker)
    # (a case that is Ngaben itself -- a death told with nothing particular -- adds nothing a template of Ngaben lacks:
    # "apa yang harus disiapkan?" after "nenek saya meninggal minggu lalu" gets what "... untuk ngaben?" gets)
    carried = [h for h in _carried_case(s, mentioned) if h]
    return bool(carried) and any(h.id != "ngaben" for h in carried)


def _refers_back(s: _Scan, own_order: List[str]) -> bool:
    """A pointing-back word (itu, tersebut, -nya ...), or no term named and only the topic's own card's words."""
    # (clean_query peels "apa itu" but not "siapa itu", whose "itu" points at nothing)
    anaphor = bool(_ANAPHOR_RE.search(re.sub(r"^\s*siapa\s+itu\b", "", s.resolver.clean_query(s.msg))))
    # ... or quotes the topic's own card ("karunia seperti apa yang dimaksud?" after anugerah raja)
    return anaphor or bool(not own_order and _quotes_topic(s.leftover, s.current_entity, s.resolver, s.tracker))


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
    recent_bot_words = set().union(*(_WORD_RE.findall(u.lower()) for u in _recent_bot_utterances(s.tracker, n=2))) if s.tracker else set()
    unknown_word = (not own_order and not anaphor and not _ORDINAL_REF_RE.search(user_msg)
                    and any(not _is_everyday_word(w, resolver) and w not in recent_bot_words for w in s.leftover))
    if (own_order and not needs_history) or unknown_word:
        said = set(re.findall(r"\w+", user_msg.lower()))
        matches = [m for m in matches if m.id in own_order or any(
            _term_is_grounded(n, said, _GENERIC_NAME_WORDS)
            for n in [m.name] + list(m.entity.get("aliases") or []))]
    matches = [m for m in matches if m.id not in replaced]
    if own_order:
        # a narrower term the extraction LLM made of one the message names: "nama lainnya ngaben apa aja" after ngaben
        # svasta came back "ngaben svasta", and the answer gave svasta's other names (bot test 2026-11-05); a message
        # pointing back still gets the topic from _topic_first
        content = get_content()
        own_names = [content.entity_name.get(i, "").lower() for i in own_order]
        matches = [m for m in matches if m.id in own_order or not any(
            n and n != m.name.lower() and re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", m.name, re.I)
            for n in own_names)]
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
    # (the "-nya" of "nama lainnya" points at nothing: "nama lainnya ngaben apa aja" after ngaben svasta got svasta's
    # other names, ngaben being svasta's class word -- bot test 2026-11-05)
    anaphor_named = anaphor and bool(_ANAPHOR_RE.search(re.sub(r"\blain-?lainnya\b|\blainnya\b", " ",
                                                               resolver.clean_query(user_msg))))
    # a what-is question with its own subject asks about that, though its words are everyday ones: "apa itu dewasa ayu"
    # after desa mawacara got desa mawacara (bot test 2026-11-05)
    own_subject = bool(_WHAT_IS_RE.search(user_msg)) and bool(re.search(
        r"\w{3,}", re.sub(r"\b(?:sih|ya|dong|deh|kak|kah|tuh|nih|itu|ini|tersebut|tadi|maksudnya|artinya)\b|[?!.,]", " ",
                          _WHAT_IS_RE.sub("", user_msg, count=1)), re.I))
    if current_entity and not _ORDINAL_REF_RE.search(user_msg) and (
            (not own_order and not own_subject and (anaphor or ((not leftover or set(leftover) <= _ELLIPSIS_VERBS)
                                                                and _asks_a_question(user_msg))))
            or (own_order and (_points_back(user_msg, off_card, resolver)
                               # every named term is the topic's class word, and "-nya" points back: "sebutkan semua
                               # arah dan dewa yang menguasainya" after nawa dewata. It needs a named term: a term found
                               # by a situation pattern named none, and "orang baru aja meninggal, langkah pertama
                               # keluarganya ngapain?" put the turn before's ngangkid first (Tier B 2026-10-30)
                               or mentioned and not off_card and anaphor_named
                               and not _WHAT_IS_RE.search(user_msg)))):
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
                matches += [h for h in _priced_terms(topic) + _cost_reason_terms(topic, user_msg)
                            if all(m.id != h.id for m in matches)]
            # "kapan dilakukan?" about Ngaben asks its days, as "kapan ngaben dilakukan" does (_WHEN_NGABEN_RE)
            if (not own_order and topic.id in _DAY_TOPICS and _TOPIC_WHEN_RE.search(user_msg)
                    and not any(m.id == "dewasa_ngaben" for m in matches)):
                hit = resolver.resolve("dewasa ngaben")
                if hit:
                    matches.insert(1, hit)
    elif topic_now and len(own_order) == 1 and topic_now.id != own_order[0] and all(m.id != topic_now.id for m in matches):
        content = get_content()
        if _OMITTED_SUBJECT_RE.search(user_msg):
            # "bedanya sama ngaben svasta?" after ngaben titip compares the two: the extraction LLM returned svasta
            # alone and the answer described svasta only -- with both it compared (bot test 2026-11-05)
            matches.insert(1, topic_now)
        elif (_NEEDED_FOR_TOPIC_RE.search(user_msg) and content.kinds_of(own_order[0])
              and content.entity_type.get(topic_now.id) in _STAGE_TYPES):
            # "tirta apa aja yang dibutuhin?" in a talk about ngaben is "tirtha apa saja untuk ngaben", the class first
            # (_class_filter): it got the komponen template, "Tirtha terbuat dari air." (bot test 2026-11-05)
            matches.insert(1, topic_now)
        elif (own := _topics_own(s, topic_now)) == "class":
            # "tirthanya apa?" after ngalukat is ngalukat's tirtha, "siapa yang membaca lontarnya?" after mamutru its
            # lontar: both got the class's own card (style test 2026-11-06). The class first, as above
            matches.insert(1, topic_now)
        elif own == "topic":
            # "jenazahnya diganti dengan apa?" after ngaben svasta ("sawanya diganti dengan simbol") got jenazah's card
            matches.insert(0, topic_now)
        elif own == "tiers":
            # "tingkatannya apa saja?" after atma wedana: its kinds, the topic's own template (a second term would send
            # it to the pipeline)
            matches = [topic_now] + [m for m in matches if m.id not in (topic_now.id, own_order[0])]
    return matches


def _topics_own(s: _Scan, topic) -> Optional[str]:
    """The one term the message names, said with "-nya", as the topic's own: "class" for a class some of whose kinds
    the topic uses or its card names ("tirthanya" after ngalukat, which uses Tirtha Panglukatan); "topic" for a general
    word of a told case (_CASE_GENERIC_IDS) when the message's other words come from the topic's card ("jenazahnya
    diganti dengan apa?" after ngaben svasta). None otherwise: "sekahnya dibuat dari apa?" after atma wedana asks
    the sekah's own card, which its template answers. ("tirthanya apa?" is no what-is question: the "-nya" makes it
    the topic's.)"""
    if len(s.mentioned) != 1:
        return None
    m, surface = s.mentioned[0]
    bare = surface.lower()[:-3] if surface.lower().endswith("nya") else ""
    hit = s.resolver.resolve(bare) if len(bare) >= 3 else None
    if not hit or hit.id != m.id or m.id == topic.id:
        return None
    content = get_content()
    kinds = set(content.kinds_of(m.id))
    if kinds and (any(r["target_id"] in kinds for r in _kb_relationships(topic.id))
                  or any(_card_uses(topic, content.entity_name[k].split()) for k in kinds)):
        return "class"
    words = [w for w in s.leftover if w not in _STOPWORDS_ID]
    if m.id in _CASE_GENERIC_IDS and words and _card_uses(topic, words):
        return "topic"
    # "tingkatannya" of a term not held at nista, madya, utama: its own tiers, its kinds (see _KINDS_Q_RE)
    if (m.id == "tingkatan_upacara" and content.kinds_of(topic.id)
            and not any(f["object_id"] == m.id for f in content.facts_by_subj.get(topic.id, []))):
        return "tiers"
    return None


# "bedanya sama X?", "hubungannya dengan X apa": a comparison or relation with its first side left out
# ... and what follows it: "apakah dilanjutkan dengan atma wedana?" after a six-month-old's ngelungah got "Ya,
# dilanjutkan dengan Atma Wedana" from atma wedana's card alone (style test 2026-11-07; ngelungah's "tidak dilanjutkan")
_OMITTED_SUBJECT_RE = re.compile(r"^\W*(?:(?:terus|lalu|kalau|kalo|trus|jadi|dan|nah),?\s+)?(?:apa\s+)?(?:beda(?:nya)?|"
                                 r"perbedaan(?:nya)?|persamaan(?:nya)?|samanya|hubungan(?:nya)?|kaitan(?:nya)?)\s+"
                                 r"(?:apa\s+)?(?:dengan|sama|dgn|ama|dan)\b"
                                 r"|^\W*(?:(?:terus|lalu|kalau|kalo|trus|jadi|nah),?\s+)?(?:apakah\s+|apa\s+)?"
                                 r"(?:(?:perlu|harus|wajib|akan|bisa|boleh|tetap|juga)\s+)?(?:di)?(?:lanjut(?:kan)?|ikuti|"
                                 r"susul)\s+(?:dengan|oleh|ke)\b", re.I)
# a class asked for with what it is needed in left out: "tirta apa aja yang dibutuhin?"
_NEEDED_FOR_TOPIC_RE = re.compile(r"\bapa\s+(?:saja|aja|sajakah)?\s*yang\s+(?:perlu\s+|harus\s+|mesti\s+)?"
                                  r"(?:dibutuhkan|dibutuhin|diperlukan|diperluin|disiapkan|disiapin|dipakai|dipake|"
                                  r"digunakan)\s*[?.!]*\s*$", re.I)


# what only a rite has: how long it takes from start to end, what holding it costs and whether the family can afford it,
# who leads it, its stages. Not "harga" or "mahal" alone, which a thing has too
# (and who does it: "siapa yang melakukannya?" after "pakai kikir?" -- the tool of a symbolic tooth filing -- got "pelaku
# kikir belum tersedia", style test 2026-11-07)
_RITE_Q_RE = re.compile(rf"\bberapa\s+lama\b|\bdari\s+awal\s+(?:sampai|sampe|hingga|smp|ke)\b|\bbiaya\w*|\bongkos\w*"
                        rf"|\bdana(?:nya)?\b|\b(?:{_NOT}|kurang)\s+mampu\b|\bdipimpin\b|\bsiapa\b[^.?!]*\b(?:me)?mimpin\b"
                        rf"|\b(?:me)?mimpin\b[^.?!]*\bsiapa\b|\btahapan(?:nya)?\b|\brangkaian(?:nya)?\b"
                        rf"|\bsiapa\b[^.?!]*\b(?:me|di)lakukan(?:nya)?\b|\bdilakukan\s+oleh\s+siapa\b", re.I)


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
        # as TERMASUK_JENIS in this KB (see PREDICATE_FAMILIES's
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
            # in the words the user reads elsewhere, naming what the answer is about instead: "(Catatan: 'dewa pitara'
            # tidak ditemukan, melanjutkan dengan yang lain.)" read as a program's log line (style test 2026-11-06)
            found = _join_names([_card_cased(e["id"], e.get("asked_as") or e.get("typed_as")) for e in enriched])
            dispatcher.utter_message(
                text=f"Informasi tentang '{', '.join(typed)}' belum tersedia"
                     + (f"; berikut yang tersedia tentang {found}." if found else ".")
            )


# Question aspect -> the family of edge AND text-only attribute predicates relevant to
# it (families: PREDICATE_FAMILIES, shared with kb_lint). On a hub node
# (ngaben has ~30 edges) the small model otherwise mixes kinds up -- e.g. listing
# ngaben's TYPES (ngaben massal, sawa prateka) as its "sebutan lain" (other names).
# Attributes ("kawangen melambangkan sikap amusti karana", "besi berwarna hitam")
# are shown ONLY when their aspect is asked -- never for a plain "apa itu X", where
# unrelated facts read as tangents (conersation.md 2026-09-24).
# ("X terbagi menjadi apa saja" too: read as "menjadi apa", a how-question, it went to the LLM, which made
# up how jun pere "terbagi" -- NLU sweep 2026-10-19)
# (and a term's tiers: Mamukur is "tingkatan upacara Atma Wedana" on its card -- "apa saja tingkatan atma wedana?" went to
# Qwen, "tingkatannya apa saja?" after it got a miss on tingkatan upacara, style test 2026-11-07; a term held at nista,
# madya, utama gets those first, _message_terms)
_KINDS_Q_RE = re.compile(r"\bjenis\b|\bmacam\b|\bragam\b|\bcontoh|\btipe\b|\bklasifikasi(?:nya)?\b|\bpembagian(?:nya)?\b"
                         r"|\b(?:ter|di)bagi\s+(?:menjadi|atas|dalam|ke)\b|\btingkatan(?:nya)?\b", re.I)
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
# (and the everyday negations: "hari apa yang gak boleh buat ngaben?" went to the LLM without the day rules, bot test
# 2026-11-05)
_DAY_Q_RE = re.compile(rf"\bhari\b(?:\s+\w+){{0,6}}?\s+(?:baik|buruk|jelek|dihindari|pantang|dilarang|"
                       rf"(?:{_NOT}\s+)?(?:boleh|dibolehkan|diperbolehkan|bagus|cocok|tepat))\b"
                       rf"|\b(?:sasih|wuku)\s+apa\b(?:\s+\w+){{0,4}}?\s+(?:baik|buruk|jelek|dihindari|pantang|dilarang|"
                       rf"(?:{_NOT}\s+)?(?:boleh|cocok|tepat|bagus))\b"
                       r"(?=.*\b(?:ngaben\w*|pengabenan|pangabenan|palebon|pitra\s+yadnya)\b)"
                       r"|\bwaktu\s+(?:yang\s+)?(?:tepat|baik|cocok|terbaik)\b"
                       # choosing the day: "gimana caranya milih hari ngaben" got only the avoided days, without dewasa
                       # ngaben's card (style test 2026-11-07). Not who chooses it: "siapa yang menentukan dewasa
                       # ngaben" has its doer template ("dimohon dari sulinggih ...")
                       r"|^(?!.*\bsiapa\b).*?\b(?:me)?(?:milih|pilih|nentuin|menentukan|menetapkan|mencari|nyari)\s+"
                       r"(?:hari|dewasa)\b|"
                       + _WHEN_NGABEN_RE.pattern, re.I)
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


def _cost_reason_terms(term, user_msg: Text) -> list:
    """Why a Ngaben costs what it does: tingkatan upacara, whose card says the level "menjadi dasar penentuan
    besar-kecilnya banten, upakara, dan punia". "kenapa bisa mahal?" after "berapa biaya ngaben?" had only the priced
    cards, and Qwen gave a cause of its own ("karena melibatkan berbagai komponen ... bade, pengawak, tandu", style test
    and Tier B 2026-11-07)."""
    if not (_WHY_Q_RE.search(user_msg) and _PRICE_Q_RE.search(user_msg)) or not term:
        return []
    if term.id != "ngaben" and not get_content().is_kind_of(term.id, "ngaben"):
        return []
    hit = get_resolver().resolve("tingkatan upacara")
    return [hit] if hit else []


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


def _day_talk(current_entity: Optional[Text], resolver) -> bool:
    """The remembered topic is Ngaben, its days' rules, or a day they name (purnama, tilem, a sasih, wuku or wewaran
    day)."""
    topic = resolver.resolve(current_entity) if current_entity else None
    if not topic:
        return False
    content = get_content()
    return (topic.id in _DAY_TOPICS | {"dewasa_ngaben", "purnama", "tilem"}
            or any(content.is_kind_of(topic.id, c) for c in ("sasih", "wuku", "wewaran")))


def _asks_about_day(user_msg: Text, day_talk: bool = False) -> bool:
    """_DAY_Q_RE, or a permission word with "hari X" where X is a word of dewasa ngaben's own
    definition: "apakah upacara ngaben boleh dilakukan saat hari pasah?" named no KB term
    beside ngaben, and the model called pasah "hari libur umat Islam ... Nabi Musa" (2026-10-07
    batch). The day names come from the KB, so "boleh dibakar dalam 42 hari" stays out.
    `day_talk`: the conversation is about Ngaben's days, so a day named without "ngaben" is about Ngaben too."""
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
    # Only a calendar day the rules name: purnama, tilem, a sasih, wuku or wewaran day. ... and in a talk about Ngaben's
    # days, a day alone: "kalau pas purnama boleh gak?" after "kenapa sasih kasanga dihindari?" got "Tidak ada larangan
    # yang tersedia ... belum tersedia", though dewasa ngaben avoids purnama (bot test 2026-11-05)
    if not day_talk and not re.search(r"\bngaben\w*|\bpengabenan\b|\b(?:mem|di)?bakar\b", low):
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
_COMPARE_Q_RE = re.compile(
    r"\b(?:perbedaan(?:nya)?|beda(?:nya)?|membedakan|persamaan(?:nya)?|kesamaan(?:nya)?|samanya)\b",
    re.I
)
# "apa hubungan X dengan Y": with every edge of both terms in context the model padded
# the answer with each term's unrelated facts ("sawa ... disertai kakawin ... berada di
# galar", conersation.md items 5 and 7, 2026-09-25) -- only the linking edges are shown
# "apa itu ngaben tanpa tirtha pangentas" asks how X stands without Y -- the same
# linking facts; with both terms' full edge lists it came back as a 7-part dump
_LINK_Q_RE = re.compile(r"\bhubungan(nya)?\b|\bkaitan(nya)?\b|\bberhubungan\b|\bterkait\b", re.I)
_RELATION_Q_RE = re.compile(_LINK_Q_RE.pattern + r"|\btanpa\b", re.I)
_ASPECT_FAMILIES = (
    (re.compile(r"sebutan lain|nama lain|istilah lain|disebut juga|dikenal (juga )?sebagai|sinonim", re.I),
     "sebutan_lain"),
    (_KINDS_Q_RE, "jenis"),
    # which kind is the most so: "ngaben apa yang paling besar?" had ngaben's 60 edges and its kinds without their cards,
    # and got "belum tersedia" (Sawa Wedana's card: "upakara paling banyak"); "... paling sederhana?" an invented "Ngaben
    # Svasta" (style test 2026-11-07)
    (re.compile(r"^\W*(?:[\w-]+\s+){1,4}?apa\s+(?:saja\s+)?yang\s+(?:paling|lebih)\b", re.I), "jenis"),
    (_STAGES_Q_RE, "tahapan"),
    # what is done in it is its steps: "apa saja yang dilakukan saat pabersihan?" got when pabersihan is held (style
    # test 2026-11-06)
    (re.compile(r"\bapa\s+(?:saja\s+|aja\s+)?yang\s+(?:dilakukan|dikerjakan|terjadi|berlangsung)\s+"
                r"(?:saat|pada|dalam|ketika|selama|waktu)\b", re.I), "tahapan"),
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
    (re.compile(r"\bsaranan?\w*|\bperlengkapan|\bupakara\w*|\bbanten apa|\bsesajen apa|\balat(-alat)?\b"
                # what must be got ready for it: "apa yang harus disiapkan keluarga untuk ngaben?" went to Qwen, which
                # glossed each sarana itself ("Wadah: Tempat untuk menaruh banten", style test 2026-11-07)
                r"|\bapa\s+(?:saja\s+|aja\s+)?yang\s+(?:harus\s+|perlu\s+|mesti\s+|wajib\s+)?(?:di)?(?:siapkan|siapin|"
                r"persiapkan)\b", re.I),
     "sarana"),
)
# the duty of a person the KB has no card for (see _aspect_families)
_PERSON_DUTY_RE = re.compile(r"\b(?:tugas|peran(?:an)?|kewajiban)(?:nya)?\s+(?:dari\s+|para\s+|si\s+|pihak\s+)?(?:keluarga|"
                             r"anak(?:-anak)?|cucu|ahli\s+waris|kerabat|saudara|warga|masyarakat|umat|orang|kami|saya|"
                             r"kita|aku)\b", re.I)
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
    if "fungsi" in families and _PERSON_DUTY_RE.search(user_msg):
        # the duty of someone who is no term asks what that person does, not what the topic is for: "apa tugas
        # keluarga?" after Ngaben's participants opened "Ngaben berfungsi sebagai mekanisme spiritual ..." (style test
        # 2026-11-07). A term's duty stays its purpose ("apa tugas pemangku dalam ngaben": pemangku "bertugas ...").
        rest = _PERSON_DUTY_RE.sub(" ", user_msg)
        if not any(p.search(rest) for p, fam in _ASPECT_FAMILIES if fam == "fungsi"):
            families.remove("fungsi")
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


def _surface_names(e: Dict[str, Any]) -> List[str]:
    """An enriched term's names as the message may write them, lowercased."""
    return [s.lower() for s in [e["name"]] + list(e.get("aliases") or []) + [e.get("asked_as") or "",
                                                                             e.get("typed_as") or ""] if s]


def _said_with_nya(user_msg: Text, e: Dict[str, Any]) -> bool:
    """The message writes the term with "-nya": "tirthanya", the topic's tirtha."""
    return any(re.search(rf"(?<![\w-]){re.escape(n)}nya\b", user_msg, re.I) for n in _surface_names(e))


def _class_filter(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[tuple]:
    """Filter enriched in place; returns (class name, [term names]) when it applied."""
    if len(enriched) < 2:
        return None
    content = get_content()
    cls = enriched[0]
    low = user_msg.lower()
    cls_names = _surface_names(cls)
    # "tirthanya apa?" after ngalukat: the class said as the topic's (_topics_own)
    possessed = _said_with_nya(user_msg, cls)
    if not content.kinds_of(cls["id"]) or not (
            _LIST_Q_RE.search(user_msg) or any(re.search(rf"\b{re.escape(n)}(?:nya)?\s+apa\b", low) for n in cls_names)):
        return None
    terms = [e for e in enriched[1:]
             if any(re.search(_FOR_TERM_RE.format(re.escape(s.lower())), low)
                    for s in [e["name"]] + (e.get("aliases") or []) + [e.get("asked_as") or "", e.get("typed_as") or ""]
                    if s)]
    # "... buat itu?", "C apa aja yang dibutuhin?" and "C-nya apa?": the topic, which _topic_first puts after the class
    if not terms and (_TRAILING_POINTER_RE.search(user_msg) or _NEEDED_FOR_TOPIC_RE.search(user_msg) or possessed):
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
    return answer.rstrip() + f"\nUrutan tahapannya: {order}."


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


def _complete_aspect_facts(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text = "", limit: int = 2) -> Text:
    """A follow-up asking an aspect of the same term ("apa maknanya hal tersebut?" after "apa itu
    pradaksina") gets the asked term's aspect facts the answer left out: told not to repeat its
    previous answer, the model gave one recalled sentence and dropped "pradaksina melambangkan
    turunnya purusa meresapi pradana ..." (2026-10-08) -- "how is this one more elaborate than the
    previous one" (conersation.md 2026-10-07). At most `limit`. A question naming the act (leading, making) gets only
    the facts stating it: "siapa yang berhak memimpin jalannya upacara pembakaran jenazah?" got ngaben's whole list of
    participants appended (AYUTHAYA part B review, 2026-11-04)."""
    if not enriched:
        return answer
    act = _asked_act(user_msg)
    said = _sentence_roots(answer)
    adds = []
    for fact in enriched[0].get("aspect_facts") or []:
        if act and not act[1].search(fact):
            continue
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


# a reason something is avoided -- a judgement beyond the rule itself (dilarang, tidak boleh ...) or a reason word
_AVOID_REASON_RE = re.compile(r"\btidak baik\b|\bburuk\b|\bkotor\b|\balaning\b|\bmencemari\b|\bsasih mati\b"
                              r"|\btanpa amer?tha\b|\bdianggap\b|\bdinilai\b|\b(?:karena|sebab|sehingga|agar|supaya)\b",
                              re.I)


def _strip_why_refusal(answer: Text, enriched: Optional[List[Dict[str, Any]]] = None) -> Text:
    """Cut the refusal when facts follow it; an answer that is only the refusal stays. With `enriched`, only
    when what follows gives the reason: a sentence naming the asked term with a purpose, meaning or reason
    word. "kenapa harus ada lemat sudhamala" lost its "Maaf, alasannya belum tercatat" above "Fakta yang
    tercatat mengenai lemat sudhamala adalah sebagai berikut: ... pisau ... eteh-eteh" (plan #16, 2026-10-26)."""
    out = _WHY_REFUSAL_RE.sub("", answer, count=1).strip()
    out = _WHY_REFUSAL_INNER_RE.sub(lambda m: m.group(1).upper(), out)
    if out == answer.strip() or len(out.split()) < 4:
        return answer
    if enriched is None and not _AVOID_REASON_RE.search(out):
        # why something is avoided, and what follows only says that it is: "kenapa hari pasah tidak boleh untuk ngaben?"
        # lost its "alasannya belum tercatat" above "hari pasah ... termasuk hari yang tidak boleh dipakai" and read as if
        # pasah's definition were the reason (style test 2026-11-07)
        return answer
    if enriched:
        terms = [e for e in enriched if e.get("id") != "ngaben"] or enriched
        names = [n for e in terms for n in [e.get("name")] + list(e.get("aliases") or []) if n]
        # or points back to it: "Sesajen ini dihaturkan untuk mengawali upacara Ngaskara" (caru pengelambuk)
        name_rx = re.compile("|".join(rf"\b{re.escape(n)}\b" for n in names)
                             + r"|^\s*(?:[-*•]|\d+\.)?\s*(?:[\w-]+\s+){0,2}(?:ini|tersebut)\b", re.I)
        # (to whom it goes is no reason: "apa alasan sesajen dilakukan" kept its "Maaf, alasannya belum tercatat" above
        # "... ditujukan pula kepada Ida Bhatara Kumara", AYUTHAYA part B 2026-11-04)
        marker = re.compile(rf"\b(?:{_PURPOSE_MARKERS}|{_FOCUS_MARKERS['simbol']}|{_REASON_MARKERS})\b", re.I)
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
        names |= _sentence_roots(" ".join([e.get("name") or "", e.get("asked_as") or "", e.get("typed_as") or ""]
                                          + list(e.get("aliases") or [])))
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
            # a god's name without its title: "* Brahma berperan ..." is dewa brahma -- the Wishnu item of a Panca
            # Dewata list went as a repeat of Brahma's, whose opening the check did not know (style test 2026-11-06)
            untitled = _untitled_names().get(_ortho_key(" ".join(words[i:i + n])))
            if untitled:
                return untitled
    return None


@functools.lru_cache(maxsize=1)
def _untitled_names() -> Dict[str, str]:
    """Each card whose name opens with a title word ("dewa brahma", "sang hyang yama"), by its name without the title,
    as an orthographic key ("brahma", "yama")."""
    out = {}
    by_id = get_resolver().by_id
    for i, name in get_content().entity_name.items():
        for n in [name] + list((by_id.get(i) or {}).get("aliases") or []):
            bare = _without_titles(n)
            if bare != n and len(bare) >= 4:
                out.setdefault(_ortho_key(bare), i)
    return out


@functools.lru_cache(maxsize=1)
def _surfaces_by_id() -> Dict[str, frozenset]:
    """Each card's id -> every surface the resolver takes as that card as written: name, aliases, force_merge keys."""
    resolver = get_resolver()
    out: Dict[str, set] = {}
    for key, i in list(resolver.surface.items()) + list(resolver.force_merge.items()):
        out.setdefault(i, set()).add(key)
    for i, e in resolver.by_id.items():
        out.setdefault(i, set()).add((e.get("name") or "").lower())
    return {i: frozenset(s for s in v if s) for i, v in out.items()}


def _item_parents(eid: str) -> set:
    """What a term is a kind or a part of."""
    return set(get_content().kind_parents.get(eid, ())) | {
        r["target_id"] for r in _kb_relationships(eid) if r["relation"] == "BAGIAN_DARI" and r["outgoing"]}


def _next_list_item(s: Text, roots: set, said: List[set], said_texts: List[Text], strict: bool = False) -> bool:
    """s opens with a term, and every earlier sentence it shares half its words with opens with another term
    of the same kind or whole: the next item of a list, not a repeat. `strict` (a comparison under the bot's own lead):
    not when that earlier sentence already describes the term -- "Sementara itu, Ngaben Svasta ... adalah ..." under
    "Perbedaannya: Ngaben massal adalah ..., sedangkan Ngaben Svasta adalah ..." (user, 2026-11-10). Only there: in a
    plain list "Tingkatan utama berarti 'besar' ..." follows "tiga tingkatan, yaitu nista, madya, dan utama" and is the
    third item, not a repeat (snapshot 2026-11-12)."""
    near = [t for r, t in zip(said, said_texts) if len(roots & r) >= 0.5 * len(roots)]
    item = _opening_term(s) if near else None
    if not item:
        return False
    parents = _item_parents(item)
    # (every surface of the card, force_merge ones too: the bot's lead named atma wedana "Ngroras", as asked, and
    # "Atma Wedana adalah Pitra Yadnya lanjutan ..." stayed under it as the next list item, Qwen 2026-11-12)
    item_names = sorted(_surfaces_by_id().get(item, ()))
    for t in near:
        other = _opening_term(t)
        if not other or other == item or not parents & _item_parents(other):
            return False
        if strict and any(re.search(rf"\b{re.escape(n)}\b", t, re.I) for n in item_names if n):
            return False
    return True


# a sentence that only continues the one before it ("Untuk yang lebih muda, ...", "Sedangkan ..."): it goes when that
# one goes as a repeat. Not "<word> ini/itu" -- "Bahan ini digunakan ... pada tahap Pabersihan Mati" went with a dropped
# verdict and left "Pada tahap ini, ..." pointing at nothing (AYUTHAYA repair snapshot, 2026-11-04)
_CONTINUES_PREVIOUS_RE = re.compile(r"\s*(?:(?:untuk|bagi)\s+yang|sedangkan|sebaliknya)\b", re.I)


# (not "satu": "salah satu contohnya ..." is no number)
_NUMBER_WORD_RE = re.compile(r"\b(?:\d+|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|"
                             r"seratus|seribu|pertama|kedua|ketiga|keempat|kelima|keenam|ketujuh|kedelapan)\b", re.I)


def _numbers_in(text: Text) -> set:
    return {m.group(0).lower() for m in _NUMBER_WORD_RE.finditer(text)}


@functools.lru_cache(maxsize=1)
def _cards_by_name_word() -> Dict[str, frozenset]:
    """Each word of a KB surface (ortho token) -> the cards whose surfaces have it."""
    out: Dict[str, set] = {}
    for i, surfaces in _surfaces_by_id().items():
        for s in surfaces:
            for w in re.split(r"[\s\-/]+", s):
                if w:
                    out.setdefault(_ortho_token(w), set()).add(i)
    return {w: frozenset(v) for w, v in out.items()}


def _new_kb_words(sentence: Text, before: Text) -> set:
    """The words of `sentence` that are words of a KB name and no everyday word ("svasta", "piuning") and that
    `before` never writes, nor any other name of their card (the lead's "Ngroras" is the model's "Atma Wedana"): a
    sentence holding one says something new, however many other words it shares."""
    resolver = get_resolver()
    seen = {w.lower() for w in _WORD_RE.findall(before)}
    new = {w.lower() for w in _WORD_RE.findall(sentence)
           if len(w) >= 4 and w.lower() not in seen and _ortho_token(w) in resolver.name_tokens
           and not _is_everyday_word(w.lower(), resolver)}
    if not new:
        return new
    surfaces = _surfaces_by_id()
    named_before = lambda i: any(re.search(rf"(?<![\w-]){re.escape(s)}(?![\w-])", before, re.I)  # noqa: E731
                                 for s in surfaces.get(i, ()))
    return {w for w in new if not any(named_before(i) for i in _cards_by_name_word().get(_ortho_token(w), ()))}


def _drop_repeated_sentences(answer: Text, earlier: Text = "", loose: bool = True,
                             protect: Optional[set] = None, strict: bool = False,
                             same_names: Optional[List[List[str]]] = None) -> Text:
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
    # `same_names`: each compared card's names count as one word, whichever is written -- the bot's lead said "Ngroras"
    # (as asked), the model "Atma Wedana", and "Sebaliknya, Atma Wedana dilakukan secara spesifik untuk menyucikan
    # suksma sarira tersebut." counted two new words and stayed (Qwen, 2026-11-12)
    name_res = [re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in sorted({n for n in ns if n}, key=len,
                                                                                       reverse=True)) + r")(?![\w-])",
                           re.I) for ns in (same_names or []) if any(ns)]

    def _roots(text: Text) -> set:
        for k, rx in enumerate(name_res):
            text = rx.sub(f" qqname{chr(ord('x') + k) * 2} ", text)
        return _sentence_roots(text)
    prior = [r for r in (_roots(s) for s in _SENT_PART_RE.findall(earlier)) if len(r) >= 4]
    prior_union = set().union(*prior) if prior else set()
    said, union, said_texts = [], set(), []
    parts = _SENT_PART_RE.findall(answer)
    last = next((s for s in reversed(parts) if s.strip()), None)
    drop, trims = [], []
    prev_part = None
    # a list item repeats only another item of its list, not the lines before the list: "... dua paket utama:" kept
    # "1. Paket lengkap ngelanus" alone, its "Paket mekinsan di geni ... 7,5 juta" said in the opening (style test
    # 2026-11-06). (A part is an item when its line opens with a list mark; "1." itself is a part of its own.)
    item_of, at, positions = {}, 0, []
    for p in parts:
        at = answer.find(p, at)
        positions.append(at)
        line_start = answer.rfind("\n", 0, at) + 1
        item_of[id(p)] = bool(_LIST_ITEM_RE.match(answer[line_start:at + len(p)]))
        at += len(p)
    item_said: List[set] = []
    for s in parts:
        # (an opening connective is no word the sentence says: "Sebaliknya, Ngroras dilakukan secara spesifik untuk
        # menyucikan suksma sarira tersebut." counted "balik" and stayed under the lead saying it, 2026-11-12)
        roots = _roots(re.sub(r"^\s*(?:sebaliknya|sementara\s+itu|selain\s+itu|di\s+sisi\s+lain|adapun|namun|"
                              r"akan\s+tetapi)\b,?", "", s, flags=re.I))
        if item_of.get(id(s)) and len(roots) >= 5:
            if max((len(roots & r) / len(roots) for r in item_said), default=0.0) < 0.8:
                if len(roots) >= 4:
                    said.append(roots)
                    said_texts.append(s)
                    union |= roots
                item_said.append(roots)
                prev_part = s
                continue
            item_said.append(roots)
        if (drop and drop[-1] is prev_part and _CONTINUES_PREVIOUS_RE.match(s) and roots
                and len(roots & union) / len(roots) >= 0.5):
            # a sentence leaning on the one just dropped goes with it when it says nothing new: "Menurut beberapa
            # lontar, hanya anak berusia lima bulan ke atas yang boleh dibakar" went as a repeat of the list and
            # left "Untuk yang lebih muda, jenazah dikubur atau ditanam." on its own (Tier B on Qwen, 2026-11-04)
            drop.append(s)
            prev_part = s
            continue
        prev_part = s
        if len(roots) >= 5:
            best = max((len(roots & r) / len(roots) for r in said), default=0.0)
            covered = len(roots & union) / len(roots)
            # the previous answer, re-said in other words ("Tirta pangentas memiliki makna sebagai alat
            # sangaskara ...") -- looser, the user has just read it
            best_prior = max((len(roots & r) / len(roots) for r in prior), default=0.0)
            covered_prior = len(roots & (union | prior_union)) / len(roots)
            repeats_prior = (not (protect_re and protect_re.search(s))
                             and (best_prior >= 0.8 or loose and (best_prior >= 0.6 or covered_prior >= 0.75)))
            # `strict`: the answer opens with the bot's own lead from the cards (_complete_contrast), and the model's
            # sentences re-saying a card in other words go too ("Sementara itu, Ngaben Svasta ... adalah jenis Ngaben
            # bagi orang yang ..." under the lead's own "sedangkan Ngaben Svasta adalah Ngaben bagi orang yang ...",
            # user 2026-11-10). Everywhere else only a near-copy goes: the looser bar cut Tirtha Pangentas's role, the
            # banten card and a kliwon verdict from answers that said them once (snapshot 2026-11-12).
            repeats = (best >= 0.8 or covered >= 0.9 and len(roots) >= 6
                       or strict and (best >= 0.65 or covered >= 0.85)
                       or _SUMMARY_OPENER_RE.match(s) and covered >= 0.7
                       # a closing sentence saying again what came before ("Pembersihan fisik dan
                       # spiritual ... bertujuan untuk memastikan jenazah ... siap untuk proses pembakaran")
                       or s is last and len(roots) >= 6 and covered >= 0.75)
            # the next item of a list told in one frame is no repeat of the items before it: "Tingkatan utama
            # berarti 'besar' dan merupakan tingkatan dengan jumlah sesajen ... paling banyak" went after nista's
            # and madya's sentences ("apa saja tingkatan dalam upacara ngaben", 2026-10-28) -- only the previous
            # answer counts against it
            # a number nothing before it says is new: "Bade bertingkat sembilan (tumpang sembilan) dipakai untuk
            # keluarga raja ..." went after the "bertingkat sebelas" item and the lembu answer before it (bot test
            # 2026-11-05)
            if (repeats or repeats_prior) and _numbers_in(s) - _numbers_in(" ".join(said_texts) + " " + earlier):
                repeats = repeats_prior = False
            # ... and so is a "not" the sentence closest to it does not say: "Ngelungah tidak dilanjutkan dengan Atma
            # Wedana, sedangkan ..." went under the opening's "Atma Wedana adalah Pitra Yadnya lanjutan ..." (2026-11-12);
            # its half that does re-say the opening goes below
            negs = {w.lower() for w in re.findall(r"\b(?:tidak|tak|bukan|belum|tanpa)\b", s, re.I)}
            if repeats and negs and said:
                closest = said_texts[max(range(len(said)), key=lambda k: len(roots & said[k]))]
                if negs - {w.lower() for w in re.findall(r"\b(?:tidak|tak|bukan|belum|tanpa)\b", closest, re.I)}:
                    repeats = False
            # ... and so is a term nothing before it names: "Sementara itu, pemangku berperan ... memimpin matur piuning"
            # and "... Lontar Sundarigama ... menjelaskan tentang Ngaben Svasta" went once the connective stopped counting
            # as a word (snapshot 2026-11-12)
            if (repeats or repeats_prior) and _new_kb_words(s, " ".join(said_texts) + " " + earlier):
                repeats = repeats_prior = False
            if ((repeats or repeats_prior) and not _SUMMARY_OPENER_RE.match(s)
                    and _next_list_item(s, roots, said, said_texts, strict)):
                repeats = False
                covered_prior = len(roots & prior_union) / len(roots)
                repeats_prior = (not (protect_re and protect_re.search(s))
                                 and (best_prior >= 0.8 or loose and (best_prior >= 0.6 or covered_prior >= 0.75)))
            if repeats or repeats_prior:
                drop.append(s)
                prev_part = s
                continue
        # a closing "sehingga ..." clause one earlier sentence already said: madiksa's and sulinggih's
        # sentences both ended "sehingga berwenang memuja Ida Sang Hyang Widhi Wasa, membuat tirtha
        # ..., dan memimpin ... Panca Yadnya" (Tier B 2026-10-09)
        tail = re.search(r",?\s+sehingga\s+([^.!?\n]+)", s)
        joint = re.search(r",\s*(?:sedangkan|sementara(?:\s+itu)?)\s+([^.!?\n]+)", s, re.I)
        if tail and said:
            t_roots = _roots(tail.group(1))
            if len(t_roots) >= 5 and max(len(t_roots & r) / len(t_roots) for r in said) >= 0.85:
                trims.append((s, s[:tail.start()].rstrip(" ,") + s[tail.end():]))
        elif joint and said and not re.search(r",\s*(?:sedangkan|sementara)\b", joint.group(1), re.I):
            # one half of an "A ..., sedangkan B ..." that a sentence before it already says goes, the other half
            # standing alone -- each is a whole clause: "Atma adalah roh atau jiwa ..., sedangkan pitra adalah para
            # pendahulu ..." under the bot's "Bedanya, Pitra adalah para pendahulu ..." (2026-11-12, "apa bedanya atma
            # dan pitra?": the model's own second opening after the bot's)
            # (never a half holding a "not" the sentence closest to it lacks: "..., sedangkan wadah adalah usungan
            # jenazah yang tidak memiliki badawang nala" went under "Perbedaan utama ... terletak pada keberadaan
            # badawang nala", snapshot 2026-11-12)
            def _said_before(text: Text) -> bool:
                r = _roots(text)
                if len(r) < 5:
                    return False
                k = max(range(len(said)), key=lambda j: len(r & said[j]))
                negs = {w.lower() for w in re.findall(r"\b(?:tidak|tak|bukan|belum|tanpa)\b", text, re.I)}
                return (len(r & said[k]) / len(r) >= (0.65 if strict else 0.8)
                        and not negs - {w.lower() for w in re.findall(r"\b(?:tidak|tak|bukan|belum|tanpa)\b",
                                                                      said_texts[k], re.I)}
                        and not _new_kb_words(text, " ".join(said_texts) + " " + earlier))
            head, rest = s[:joint.start()], joint.group(1)
            if _SUMMARY_OPENER_RE.match(s) and (_said_before(rest) or _said_before(head)):
                # a closing "Jadi, perbedaan kuncinya adalah: A ..., sedangkan B ..." half of which re-says the answer
                # is a summary: it goes whole (with one half cut it set a lone side against nothing, 2026-11-12)
                drop.append(s)
                prev_part = s
                continue
            if _said_before(rest) and not _said_before(head):
                # (a "Perbedaan utama terletak pada ...:" before it set two sides against each other; one is left)
                head = re.sub(r"^(\s*)Perbedaan\w*\b[^:.!?\n]*:\s*(\w)", lambda m: m.group(1) + m.group(2).upper(), head)
                trims.append((s, head.rstrip(" ,") + s[joint.end():]))
            elif _said_before(head) and not _said_before(rest):
                lead_ws = re.match(r"\s*", s).group(0)
                trims.append((s, lead_ws + rest[:1].upper() + rest[1:] + s[joint.end():]))
        if len(roots) >= 4:
            said.append(roots)
            said_texts.append(s)
            union |= roots
    if not trims and (not drop or len(drop) == len([s for s in parts if _sentence_roots(s)])):
        return answer
    if len(drop) == len([s for s in parts if _sentence_roots(s)]):
        drop = []
    # each cut and trim at its own place: replacing the text cut the first copy of it -- "... sedangkan Banten adalah
    # sesajen ..." lost its second half to the model's later sentence saying the same (style test 2026-11-06)
    edits: Dict[int, str] = {}
    for s, short in trims:
        i = next(i for i, p in enumerate(parts) if p is s)
        edits[i] = short
    dropped = {i for i, p in enumerate(parts) if any(p is d for d in drop)}
    # a "therefore" right after a cut sentence draws on what is gone: "Ya, ... memiliki makna spiritual yang sama. Oleh
    # karena itu, upacara tetap punya nilai yang sama ..." (style test 2026-11-06) -- the connective goes with it; so does
    # a "whereas" set against it: "Sebaliknya, Nyekah ditujukan untuk ..." opened its paragraph once the Ngelungah
    # sentence before it had gone as a repeat of the opening (user, 2026-11-12)
    # (last to first: a sentence kept back below for the one after it is then the one a cut sentence before it leans on)
    for i in reversed(range(len(parts) - 1)):
        if i in dropped and i + 1 not in dropped:
            nxt = edits.get(i + 1, parts[i + 1])
            bare = re.sub(r"^(\s*)(?:oleh karena itu|oleh sebab itu|karena itu|dengan demikian|maka dari itu|sebaliknya|"
                          r"sementara itu|di sisi lain|sedangkan|adapun)(?:,\s*|\s+)(\w)",
                          lambda m: m.group(1) + m.group(2).upper(), nxt, flags=re.I)
            # ... and "Tirtha ini" / "Upacara tersebut" pointing at the term the cut sentence was about gets its name:
            # "Sebaliknya, Tirtha Penembak adalah ..." went under the lead, and "Tirtha ini tidak memiliki fungsi
            # penyucian ... seperti Tirtha Pangentas" then read as Tirtha Pangentas's (2026-11-12)
            # (also after a leading phrase: "Secara filosofis, tirtha ini diyakini ..." under a lead ending on Tirtha
            # Penembak)
            pointer = re.match(r"(\s*(?:[^,.!?\n]{1,40},\s*)?)([A-Za-z]\w*)\s+(?:ini|tersebut)\b", bare)
            subject = re.sub(r"^\s*(?:sebaliknya|sementara\s+itu|sedangkan|adapun|selain\s+itu),?\s*", "", parts[i],
                             flags=re.I)
            # (a cut sentence that itself opens pointing back, "Tirtha ini diambil ...", is about no term it names)
            term = None if re.match(r"\s*[A-Za-z]\w*\s+(?:ini|tersebut)\b", subject) else _opening_term(subject)
            named = False
            if pointer and term:
                # (by spelling key: "tirtha ini" is the card "tirta pangentas", alias "tirtha pangentas")
                word = _ortho_key(pointer.group(2))
                surfaces = [_card_cased(term)] + list((get_resolver().by_id.get(term) or {}).get("aliases") or [])
                fits = [s_ for s_ in surfaces if s_ and word in {_ortho_key(w) for w in s_.split()}]
                # (as this answer writes it: "Tirtha Pangentas", not the card's "tirta pangentas")
                written = next((m_.group(0) for s_ in fits
                                for m_ in [re.search(rf"(?<![\w-]){re.escape(s_)}(?![\w-])", answer, re.I)] if m_), None)
                surface = written or (fits[0] if fits else None)
                if surface or pointer.group(2).lower() in {"upacara", "sarana", "tahap", "tahapan", "ritual", "istilah"}:
                    name = written or (_card_cased(term, surface) if surface else _card_cased(term))
                    if not pointer.group(1).strip():
                        name = name[:1].upper() + name[1:]
                    bare = f"{pointer.group(1)}{name}{bare[pointer.end():]}"
                    named = True
            # a pointer nothing can name keeps the sentence it points at when the sentence kept before that is about
            # something else: "Tujuannya adalah ..." read as bade's once "Manah Tirtha Ening adalah bagian dari ...
            # Pabersihan" went, "Cara pengambilan ini ..." as Tirtha Pangentas's (snapshot 2026-11-12) -- a repeat reads
            # better than a wrong referent. (Not when that sentence names the same term: "Rinciannya:" under daksina's
            # components brought back daksina's list a second time.)
            leans = (pointer and not named) or re.match(
                r"\s*(?:[A-Z]\w*\s+\w+\s+(?:ini|tersebut)\b|(?!(?i:selanjut|akhir|biasa|umum|sebenar|misal|terutama|"
                r"sebalik|selain)nya\b)[A-Z]\w+nya\b|(?:Ia|Beliau)\b)", bare)
            if leans:
                kept_before = next((edits.get(j, parts[j]) for j in range(i - 1, -1, -1)
                                    if j not in dropped and parts[j].strip()), "")
                entity = get_resolver().by_id.get(term) or {} if term else {}
                names = [get_content().entity_name.get(term, "")] + list(entity.get("aliases") or []) if term else []
                if not (kept_before and any(n and re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", kept_before, re.I)
                                            for n in names)):
                    dropped.discard(i)
                    continue
            if bare != nxt:
                edits[i + 1] = bare
    for i in dropped:
        edits[i] = ""
    out, last = [], 0
    for i in sorted(edits):
        out += [answer[last:positions[i]], edits[i]]
        last = positions[i] + len(parts[i])
    answer = "".join(out) + answer[last:]
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
    parts = [s for s in _SENT_PART_RE.findall(answer) if s.strip()]
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
    ctx_sents = [r for r in (_sentence_roots(x) for x in re.split(r"(?<!\d)\.|\.(?!\d)|[;!?\n]|\",\"", context_text))
                 if r]
    if not ctx_sents:
        return answer
    vocab = set().union(*ctx_sents)
    q_roots = _sentence_roots(user_msg)
    parts = [s for s in _SENT_PART_RE.findall(answer) if s.strip()]

    def unsupported(s: Text) -> bool:
        # the bot's own miss wording is in no context ("informasi detail ... belum tercatat di basis data"):
        # #1715 "apa itu daksina dan apa maknanya" lost the sentence saying its meaning is not recorded
        if _VERDICT_RE.search(s):
            return False
        # a list's lead-in claims nothing its items do not: "Meskipun demikian, berbagai unsur yang digunakan dalam
        # upacara Ngaben, yang secara implisit harus tersedia atau disiapkan, antara lain:" went and left the list under
        # "Tidak ada rincian spesifik ..." (bot test 2026-11-05)
        at = answer.find(s)
        if s.rstrip().endswith(":") and re.match(r"\s*\n\s*(?:[-*•]|\d+[.)])\s", answer[at + len(s):]):
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


def _fix_outside_glosses(answer: Text, context_text: Text) -> Text:
    """A "<term>, yaitu <gloss>" clause naming a word the context never uses and no everyday word -- a concept from
    outside the KB: "ditentukan oleh dewasa ngaben, yaitu penentuan hari baik berdasarkan perhitungan astrologi Hindu"
    (the full NLU test, #1836, 2026-11-05; the regression already forbade "astrologi" for "apa itu dewasa ngaben") --
    gets the term's own card's gloss instead ("yaitu hari baik untuk melaksanakan Ngaben, yang dipilih menurut sasih serta
    wuku dan wewaran"); with none on the card, and for a gloss that opens with a KB name, the clause stays."""
    _named_terms("", everyday=True)
    _, names = _SURFACES[True]
    resolver, content, ctx = get_resolver(), get_content(), context_text.lower()

    def fix(m: "re.Match") -> Text:
        words = m.group(1).split()
        for n in range(min(4, len(words)), 0, -1):
            term = names.get(" ".join(words[-n:]).lower())
            if term:
                break
        else:
            return m.group(0)
        # a gloss that names a card is the KB's own: "Tahap ketiga dari delapan tahapan pelaksanaan Ngaben, yaitu ngawit
        # pengaksaran (pemberian aksara suci pada jenazah), juga ... dilakukan oleh Sulinggih" was cut to "Tahap ketiga
        # dari delapan tahapan pelaksanaan Ngaben." (#1861, the NLU test's replies replayed, 2026-11-05)
        gloss_words = m.group(3).split()
        if any(names.get(" ".join(gloss_words[:k]).lower()) for k in range(min(4, len(gloss_words)), 0, -1)):
            return m.group(0)
        outside = [w for w in _WORD_RE.findall(m.group(3).lower())
                   if len(w) >= 5 and w not in ctx and not _is_everyday_word(w, resolver)]
        # (one mostly in its card's words stays, a loanword or not: perlambang "yakni simbol atau wakil dari makna maupun
        # wujud tertentu, dalam hal ini merepresentasikan badan halus (atma) jenazah")
        said = _sentence_roots(m.group(3))
        if not outside or len(said & _sentence_roots(content.best_definition(term) or "")) * 2 >= len(said):
            return m.group(0)
        first = _first_sentence(content.best_definition(term) or "", limit=400) or ""
        gloss = re.match(rf"\s*{re.escape(content.entity_name.get(term, ''))}\s+(?:\([^)]*\)\s+)?adalah\s+(.+?)\.?\s*$",
                         first, re.I)
        # (with no gloss on the card the clause stays: cut, it can take the sentence's whole claim with it)
        return f"{m.group(1)}, {m.group(2)} {gloss.group(1)}" if gloss else m.group(0)
    return re.sub(r"\b((?:[\w-]+ ){0,3}[\w-]+),\s+(yaitu|yakni)\s+([^.;:\n]+?)(?=[.;:\n]|$)", fix, answer)


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
    parts = _SENT_PART_RE.findall(answer)
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
kedua keduanya ketiga tersebut ini itu antara
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
        aspect = "persamaan" if re.search(r"\b(?:persamaan|kesamaan|samanya)\b", question, re.I) else "perbedaan"
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
_PURPOSE_MARKERS = (r"berfungsi|fungsi\w*|tujuan\w*|bertujuan|berguna|kegunaan\w*|guna|berperan|peran\w*|manfaat\w*|"
                    r"agar|supaya|diyakini|"
                    r"sebagai (?:tempat|sarana|alat|media|wadah|penunjuk|pengganti|penanda|lambang|simbol)|"
                    r"(?:digunakan|dipakai|dihaturkan|dipersembahkan) (?:sebagai|untuk)(?! (?:membuat|membentuk|mengikat))|"
                    # what is done for a purpose: "Tabunan dilakukan untuk mengatasi bau jenazah" answered "apa alasan
                    # tabunan dilakukan", and still got "Tabunan digunakan dalam sawa wedana." put first (live run
                    # 2026-11-14); not "dilaksanakan untuk jenazah ...", whom it is for
                    r"(?:dilakukan|dilaksanakan|diadakan|diselenggarakan) untuk (?=(?:me|ber)[a-z])")
_FOCUS_MARKERS = {
    # ("perlambang": "Sukutunggal adalah perlambang badan mendiang" -- \blambang does not start inside it; not the
    # effigy, "sawa perlambang", "dibuatkan perlambang": "maknanya pabersihan apa ya" got its definition as the meaning)
    "simbol": r"melambangkan|lambang\w*|(?:sebagai|adalah|merupakan|yakni|ialah|menjadi) perlambang\w*|makna\w*|bermakna|menggambarkan|menandakan|menandai|menunjukkan|simbol\w*|"
              r"menyimbolkan|wujud|perwujudan|mewujudkan|diwujudkan|mencerminkan|berarti|"
              # ("sebagai ungkapan rasa syukur dan permohonan": ngusaba, AYUTHAYA part B 2026-11-03)
              r"sebagai (?:tanda|penanda|pertanda|penegasan|ungkapan|pernyataan)",
    # ("persembahan yang ditujukan kepada para dewa": dewa yadnya's purpose is whom it is for -- but no reason why:
    # _strip_why_refusal goes by _PURPOSE_MARKERS)
    "fungsi": r"ditujukan|" + _PURPOSE_MARKERS,
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
    if why:
        # a why-question's lead states a purpose or reason; where the term is used is none ("Tabunan digunakan dalam
        # sawa wedana." above why tabunan is done, live run 2026-11-14)
        pool = [f for f in pool if marker.search(f)]
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
        body = (_known_sentence(e.get("definition"), entity_id=e["id"], name=e["name"]) if bare
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
# (not what must be done: "apa yang harus disiapkan keluarga untuk ngaben?" asks for things, and lost its sarana
# template to it, style test 2026-11-07)
_PERMISSION_Q_RE = re.compile(r"\bapa(kah)?\b(?!\s+(?:saja\s+|aja\s+)?yang\s+(?:harus|wajib|perlu|mesti)\b)"
                              r".*\b(boleh|harus|wajib|dilarang)\b|\bbolehkah\b|\bharuskah\b"
                              rf"|\b(?:boleh|harus|wajib|dilarang)\b(?=.*(?:{_CASUAL_YES_NO_RE.pattern}))", re.I)

# "sasih serta wuku dan wewaran": what a good day is chosen by, not a rule of either half
_DAY_RULE_SUMMARY_RE = re.compile(r"\bsasih,?\s+(?:serta|dan)\s+wuku(?:,?\s+(?:serta|dan)\s+wewaran)?\b", re.I)


def _calendar_half(eid: Text) -> Optional[Text]:
    """Which half of dewasa ngaben's rules a term is a day of: "sasih" (a sasih, malamasa), "wuku" (a wuku, a wewaran
    day -- kliwon is a part of pancawara, no kind of it --, purnama, gotongan), or None. A term the card's rule
    sentences name ("Berdasarkan sasih ...", "Berdasarkan wuku dan wewaran ...") is of that sentence's half."""
    content = get_content()
    if eid == "sasih" or content.is_kind_of(eid, "sasih"):
        return "sasih"
    parents = [f["object_id"] for f in content.facts_by_subj.get(eid, []) if f["predicate"] in ("TERMASUK_JENIS", "BAGIAN_DARI")]
    if eid in ("wuku", "wewaran") or any(x in ("wuku", "wewaran") or content.is_kind_of(x, "wuku")
                                         or content.is_kind_of(x, "wewaran") for x in [eid] + parents):
        return "wuku"
    name = content.entity_name.get(eid) or ""
    if eid == "dewasa_ngaben" or len(name) < 3:
        return None
    # an item of the sentence's lists, not a word of a longer name: "pitra" is in "yang baik untuk Pitra Yadnya", and
    # "hari baik untuk Pitra kapan" lost the wuku half (2026-11-05)
    for s in _sentences(content.best_definition("dewasa_ngaben") or ""):
        half = re.match(r"Berdasarkan\s+(sasih|wuku)\b", s)
        items = re.split(r",\s*|;\s*|\s+(?:dan|serta|atau)\s+", s)
        if half and any(_ortho_key(re.sub(r"^(?:(?:dan|serta|atau)\s+)?(?:hari|sasih|wuku)\s+", "", i.strip().rstrip("."),
                                          flags=re.I)) == _ortho_key(name) for i in items):
            return half.group(1)
    return None


def _asked_day_half(enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """The one half of dewasa ngaben's rules a question asks when it names days of that half only (_calendar_half);
    None for both or neither."""
    halves = {h for h in (_calendar_half(e["id"]) for e in enriched) if h}
    return halves.pop() if len(halves) == 1 else None


def _drop_unasked_day_half(answer: Text, half: Optional[Text]) -> Text:
    """The other half's rules, which the model copies from the context's sections: "hari kliwon boleh gak buat ngaben"
    got a paragraph "Menurut sasih: Sasih yang baik untuk Ngaben adalah kasa, karo, ..." (bot test 2026-11-05). A
    paragraph opening "Menurut/Berdasarkan sasih" goes when only the wuku half is asked, and the reverse. Never all."""
    if not half:
        return answer
    other = r"sasih" if half == "wuku" else r"wuku"
    paragraphs = re.split(r"\n\s*\n", answer)
    keep = [p for p in paragraphs if not re.match(rf"\s*(?:Menurut|Berdasarkan)\s+{other}\b", p, re.I)]
    return "\n\n".join(keep) if keep and len(keep) < len(paragraphs) else answer


# a clause saying the good-day rules do not decide it (_drop_dewasa_denials): "tidak ditentukan oleh pemilihan dewasa
# ngaben", "aturan waktu ngaben ... tidak secara langsung menentukan kapan cecepan dihaturkan", ", bukan waktu pembakaran
# jenazah (ngaben) yang dipilih berdasarkan sasih dan wuku" -- not a rule ("pada sasih kadasa tidak boleh membakar
# jenazah", "tidak boleh dijadikan patokan"), "ditentukan oleh dewasa ngaben, bukan oleh hari libur" nor "tidak perlu
# memilih dewasa"
_DENY_DECIDES_RE = re.compile(r"\b(?:tidak|bukan)\s+(?:secara\s+langsung\s+|lagi\s+)?(?:ditentukan|menentukan|mengikuti|"
                              r"berdasarkan|bergantung|berlaku|terikat|diatur|mengatur)\b|^\s*bukan\s+(?:waktu|hari|aturan)\b",
                              re.I)
_DAY_RULE_WORD_RE = re.compile(r"\b(?:dewasa|hari\s+baik|sasih|wuku|aturan\s+(?:waktu|pemilihan))\b", re.I)


def _drop_dewasa_denials(answer: Text, other: Optional[Dict[str, Any]]) -> Text:
    """A denial no card makes, that the good-day rules decide it: "Waktu pelaksanaan cecepan tidak ditentukan oleh
    pemilihan dewasa ngaben, melainkan oleh jadwal ... ngulapin." stood above the rules appended after it, and on Qwen the
    same reasoning came back in other words (live run 2026-11-14). For a thing of a Ngaben (`other`) what is unrecorded is
    a day of its own: the first such sentence says so, the later ones go; a trailing ", bukan ..." clause goes alone."""
    def denials(part: Text) -> tuple:
        clauses = re.split(r",\s+(?![^()]*\))", part)
        return clauses, [i for i, c in enumerate(clauses) if _DENY_DECIDES_RE.search(c) and _DAY_RULE_WORD_RE.search(c)]
    if not any(denials(p)[1] for p in re.split(r"(?<=[.!?])\s+", answer)):
        return answer
    paragraphs, first = [], True
    for para in re.split(r"\n\s*\n", answer.strip()):
        out = []
        for part in re.split(r"(?<=[.!?])\s+", para.strip()):
            clauses, denies = denials(part)
            if not denies:
                out.append(part)
            elif all(i > 0 and re.match(r"\s*bukan\b", clauses[i], re.I) for i in denies):
                out.append(", ".join(c for i, c in enumerate(clauses) if i not in denies).rstrip(" ,.") + ".")
            elif other and first:
                out.append(f"Hari baik khusus untuk {other['name']} belum tercatat di basis data.")
            first = False
        if out:
            paragraphs.append(" ".join(out))
    return "\n\n".join(paragraphs).strip()


def _complete_day_rules(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A day question must give both halves of dewasa ngaben: an answer without the wuku/
    wewaran days, or without the sasih, gets the definition's own sentence about the missing
    half. With rule 22 in the prompt, "hari apa yang harus dihindari untuk ngaben" still came
    back with only the sasih, and "hari baik apa saja" with only the days (Tier B 2026-10-01;
    T15/T16/T20/T96). The rule half is the card's "Berdasarkan sasih/wuku ..." sentence, and the card's summary
    ("dipilih menurut sasih serta wuku dan wewaran") says neither half: once the card opened with it, "hari apa yang
    harus dihindari untuk pabersihan mati" got that summary instead of the sasih rules (AYUTHAYA repair, 2026-11-04)."""
    definition = get_content().best_definition("dewasa_ngaben") or ""
    sentences = re.split(r"(?<=[.!?])\s+", definition)
    # a denial no card makes, that dewasa ngaben decides it: "Waktu pelaksanaan cecepan tidak ditentukan oleh pemilihan
    # dewasa ngaben, melainkan oleh jadwal pelaksanaan upacara ngulapin." stood above the rules appended here (live run
    # 2026-11-14). For a thing of a Ngaben, what is unrecorded is a day of its own; for Ngaben itself the denial goes.
    other = next((e for e in enriched if e.get("id") not in ("dewasa_ngaben", "ngaben")), None)
    answer = _drop_dewasa_denials(answer, other)
    said = _DAY_RULE_SUMMARY_RE.sub(" ", answer)
    # (a question about days of one half wants that half: kliwon asks no sasih rule)
    half = _asked_day_half(enriched)
    for key in ("sasih", "wuku"):
        if re.search(rf"\b{key}\b", said, re.I) or half and key != half:
            continue
        add = next((s for s in sentences if re.match(rf"Berdasarkan {key}\b", s, re.I)), None)
        if add:
            answer = answer.rstrip() + " " + add
    return answer.strip()


# "apakah ngaben harus dilakukan dalam tujuh hari": a span of days the question names
_SPAN_Q_RE = re.compile(r"\bdalam\s+(?:waktu\s+|jangka\s+waktu\s+)?(\d+|\w+)\s+hari\b", re.I)


def _complete_span_rule(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A question about holding Ngaben within so many days gets dewasa ngaben's own sentence for that span when the
    answer left it out: "apakah ngaben harus dilakukan dalam tujuh hari" got "Tidak ada ketentuan ... wajib dilakukan
    dalam waktu tujuh hari" and never the card's "Bila Ngaben dilaksanakan dalam tujuh hari sejak kematian, tidak perlu
    memilih dewasa ..." (AYUTHAYA part A note, Tier B on Qwen 2026-11-04)."""
    m = _SPAN_Q_RE.search(user_msg)
    if not m or not any(e.get("id") in ("ngaben", "dewasa_ngaben") for e in enriched):
        return answer
    span = m.group(1).lower()
    numbers = {str(n): w for w, n in _COUNT_WORDS.items()}
    words = {span, numbers.get(span, span)} | {str(n) for w, n in _COUNT_WORDS.items() if w == span}
    said = _sentence_roots(answer)
    for s in _sentences(get_content().best_definition("dewasa_ngaben") or ""):
        roots = _sentence_roots(s)
        if (any(re.search(rf"\bdalam\s+{re.escape(w)}\s+hari\b", s, re.I) for w in words)
                and roots and len(roots & said) * 2 < len(roots)):
            # the rule answers the question: a refusal above it goes -- "bagaimana kalau ngaben dalam tujuh hari setelah
            # meninggal?" read "Maaf, informasi tersebut belum tersedia. Yang tersedia tentang ngaben: ..." and then the
            # rule (style test 2026-11-07)
            if answer.lstrip().startswith("Maaf"):
                return s
            return answer.rstrip() + "\n\n" + s
    return answer


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
    parts = _SENT_PART_RE.findall(answer)
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
    # a which-question's list of what the context itself names is the context's, not an invented ban: "hari apa yang
    # gak boleh buat ngaben?" got its right "Hari-hari yang tidak boleh atau dihindari untuk pelaksanaan Ngaben meliputi
    # gagak anungsang pati, gotongan, ingkel wong, ..." cut and "Tidak ada larangan yang tercatat" put in front (bot
    # test 2026-11-05)
    which_q = bool(re.search(r"\b\w+\s+apa\s+(?:saja\s+|aja\s+)?yang\b|\bapa\s+(?:saja|aja)\s+yang\b"
                             r"|\bsiapa\s+(?:saja\s+|aja\s+)?yang\b", user_msg, re.I))
    context_low = context_text.lower()

    def lists_context_items(s: Text) -> bool:
        if not which_q:
            return False
        names = [get_content().entity_name.get(i, "").lower() for i in _named_terms(s)]
        return len(names) >= 2 and all(n and n in context_low for n in names)
    # "... larangan atau kewajiban ... belum tercatat di basis data" says no rule is recorded: cut as a claim, it
    # left "Tidak ada larangan yang tercatat" as the answer to "apakah niskala wajib" (plan #16, 2026-10-26)
    drop = [s for s in parts if (_PROHIBITION_RE.search(s) or capability and _INCAPACITY_RE.search(s)
                                 or any(re.search(rf"\b{re.escape(w)}\b", s, re.I) for w in absent))
            and not re.search(r"\btidak ada (?:larangan|aturan)|\bbukan larangan"
                              r"|\b(?:tidak|belum) (?:tercatat|disebutkan|dijelaskan)|\btidak (?:mencatat|menyebutkan)\b",
                              s, re.I)
            and not restates_rule(s) and not lists_context_items(s)]
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
            # (only a sentence that avoids it: gotongan's "tiga hari ... yaitu sukra kliwon, saniscara umanis, dan redite
            # paing" put sukra kliwon into the seven-day rule's list once day questions brought gotongan in, 2026-11-05)
            for m in hits if _AVOID_RE.search(s) else []:
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
            # a sentence that allows the day, its avoid word in the condition: "Hari kliwon boleh digunakan untuk Ngaben,
            # asalkan tidak bertepatan dengan kombinasi hari tertentu yang dihindari." became "..., yang dihindari bukan
            # kliwon saja, ..." and the answer lost its verdict (bot test 2026-11-05)
            head = s[:_AVOID_RE.search(s).start()]
            if re.search(r"\b(?:boleh|dibolehkan|diperbolehkan|dapat|bisa)\b", head, re.I) and not re.search(
                    rf"\b{_NOT}\s+(?:boleh|dibolehkan|diperbolehkan|dapat|bisa)\b", head, re.I):
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


_PLACING_VERB = r"(?:diletakkan|ditaruh|ditempatkan|dipasang|disimpan|dibaringkan|diselipkan|disematkan)(?:nya)?"


def _fix_dropped_place_preposition(answer: Text, context_text: Text) -> Text:
    """A place the model joined to its placing verb without the preposition: "diletakkannya daksina dada sang mayat"
    for the cards' "daksina diletakkan di dada sawa" (#1715, NLU test 2026-11-05). Only where one context sentence has
    the verb, the words between, and the preposition before that place."""
    sentences = [s.lower() for s in _context_sentences(context_text)]

    def fix(m: "re.Match") -> Text:
        verb, between, word = m.group(1), m.group(2), m.group(3)
        if re.search(r"\b(?:di|ke|pada|dari|dalam|atas|bawah|dengan|sebagai|untuk|oleh|yang|dan|atau|serta)\s*$",
                     between, re.I):
            return m.group(0)
        stem = re.sub(r"nya$", "", verb.lower())
        for s in sentences:
            said = re.search(rf"\b{re.escape(stem)}\b[^.;]*?\b(di|ke|pada)\s+{re.escape(word.lower())}\b", s)
            if said and all(re.search(rf"\b{re.escape(w)}\b", s) for w in between.lower().split()):
                return f"{verb} {between}{said.group(1)} {word}"
        return m.group(0)
    return re.sub(rf"\b({_PLACING_VERB})\s+((?:[\w-]+\s+){{1,2}}?)([a-z]{{3,}})\b", fix, answer, flags=re.I)


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
        known = _known_sentence(content.best_definition(tid), entity_id=tid, name=content.entity_name.get(tid, tid))
        if not known:
            continue
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
    # a rule about another act is no usage norm: "apakah bade harus dibakar?" got who lazimnya uses bade (style test
    # 2026-11-07)
    act = re.search(r"\b(?:boleh|harus|wajib|perlu|bisa|dapat|dilarang)\s+(?:(?:ikut|tetap|juga)\s+)?"
                    r"((?:di|me[mny]?|meng)[a-z]{3,})\b", user_msg, re.I)
    if act and not _USE_VERB_RE.search(act.group(1)):
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
    # a rule of a term the question did not name says whose rule it is: "apakah wanita hamil boleh ikut ngaben?" got
    # sembah bhakti's "Yang pantang ikut menyembah pitara: ..." alone (bot test 2026-11-05)
    names = [n for n in [e["name"]] + list(e.get("aliases") or []) if n]
    said = list(rules)
    if get_content().entity_type.get(e["id"]) in _STAGE_TYPES and not any(
            re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", user_msg + " " + rules[0], re.I) for n in names):
        said[0] = f"Dalam {e['name']}, {rules[0][:1].lower()}{rules[0][1:]}"
    return " ".join(said + [s for s in sentences if s not in rules and shares(s)])


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


# "apakah benar ngaben dilakukan pada saat hari libur aja?": a claim that a rite is held only at some time
_ONLY_TIME_CLAIM_RE = re.compile(r"\b(?:hari|saat|waktu|pas|tanggal|bulan|musim)\b[^.?!]*\b(?:aja|saja|doang|hanya|cuma|"
                                 r"selalu)\b|\b(?:hanya|cuma|selalu|harus)\b[^.?!]*\b(?:hari|saat|waktu|pas|tanggal|"
                                 r"bulan|musim)\b", re.I)
# the claimed day: a calendar word and one or two words naming it ("hari libur", "tanggal merah", "akhir pekan")
_CLAIMED_DAY = (r"(?:hari|tanggal|bulan|akhir)(?:\s+(?!(?:di|ke|dari|untuk|buat|aja|saja|doang|ya|kah|sih|dong|atau|"
                r"dan)\b)[\w-]+){1,2}")
_CLAIMED_TIME_RE = re.compile(rf"\b(?:pada\s+saat|pada|saat|pas|ketika|waktu)\s+({_CLAIMED_DAY})\s+(?:aja|saja|doang)\b"
                              r"|\b(?:hanya|cuma|selalu|harus)\s+(?:(?:boleh|bisa)\s+)?(?:(?:dilakukan|dilaksanakan|"
                              r"diadakan|digelar)\s+)?(?:pada\s+(?:saat\s+)?|saat\s+|pas\s+)?"
                              rf"({_CLAIMED_DAY})", re.I)


def _false_day_premise_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """A claim that a rite is held only at a time no day rule names: "Tidak benar", what decides its time, and the good
    days (user, 2026-11-03, the AYUTHAYA change: "If a bot knows that something is not true, i.e the KG contradics it,
    i want the bot to know that and answers ... 'apakah benar ngaben dilakukan pada saat hari libur aja?' ... 'not its
    not true, instead ngaben is help on good days according to X and Y and Z'"; it said the case was not recorded).
    Dewasa ngaben's card: "Dewasa ngaben adalah hari baik untuk melaksanakan Ngaben", then the good sasih and days.
    Not when the claim names a day the KB knows (a sasih, wuku or wewaran day, purnama, tilem): the day-rule answers
    take those. Nor a day the card's rules speak of: "apakah ngaben harus dilakukan dalam tujuh hari" got "Tidak benar"
    though the card says a Ngaben within seven days needs no dewasa (AYUTHAYA snapshot, 2026-11-03)."""
    if not (_whether_question(user_msg) or re.search(r"\b(?:benar\w*|betul|bener)\b", user_msg, re.I)):
        return None
    if not _ONLY_TIME_CLAIM_RE.search(user_msg):
        return None
    content = get_content()
    ids = [e["id"] for e in enriched]
    topic = next((i for i in ids if i in _DAY_TOPICS), None)
    if not topic or any(i in ("purnama", "tilem") or any(content.is_kind_of(i, c) for c in ("sasih", "wuku", "wewaran"))
                        for i in ids):
        return None
    rules = _dewasa_rules()
    if not rules or not rules["good_sasih"] or not rules["good_wuku"]:
        return None
    claim = _CLAIMED_TIME_RE.search(user_msg)
    if not claim:
        return None
    claimed = (claim.group(1) or claim.group(2)).strip()
    rule_words = set(_WORD_RE.findall(content.best_definition("dewasa_ngaben").lower()))
    if any(len(w) >= 3 and w in rule_words for w in _WORD_RE.findall(claimed.lower())[1:]):
        return None
    name = content.entity_name[topic]
    name = name[:1].upper() + name[1:]
    return (f"Tidak benar. Waktu pelaksanaan {name} ditentukan oleh dewasa ngaben, yaitu hari baik untuk melaksanakan "
            f"Ngaben, bukan oleh {claimed}. Menurut sasih, {'; '.join(rules['good_sasih'])}. "
            f"Menurut wuku dan wewaran, {'; '.join(rules['good_wuku'])}.")


def _not_avoided_day_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[Text]:
    """Why a sasih or a day is avoided for Ngaben, when dewasa ngaben's card does not avoid it: "kenapa sasih kasanga
    dihindari?" got "Maaf, alasannya belum tersedia" and "Sasih Kasanga adalah ..., dan bahwa sasih merupakan ..." (bot
    test 2026-11-05). The answer says it is not among the avoided ones, the good-day clause naming it, and for a sasih
    the meeting of wuku and sasih that makes it an avoided one (sasih paruwak tahuk: "wuku uye pada sasih katiga dan
    sasih kasanga"). None when the card avoids it, when its own card judges it, or for another rite."""
    if not _WHY_Q_RE.search(user_msg) or not _AVOIDED_DAYS_Q_RE.search(user_msg):
        return None
    content = get_content()
    days = [e for e in enriched if e["id"] in ("purnama", "tilem")
            or any(content.is_kind_of(e["id"], c) for c in ("sasih", "wuku", "wewaran"))]
    if len(days) != 1 or not {e["id"] for e in enriched} - {days[0]["id"]} <= {"dewasa_ngaben", "ngaben", "pitra_yadnya"}:
        return None
    day = days[0]
    rules = _dewasa_rules()
    if not rules or not rules["bad_sasih"]:
        return None
    words = {w for n in [day["name"]] + list(day.get("aliases") or [])
             for w in _WORD_RE.findall(n.lower()) if w not in ("sasih", "wuku", "hari", "wewaran") and len(w) >= 3}
    if not words:
        return None
    names_it = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(words))) + r")\b", re.I)
    if any(names_it.search(c) for c in rules["bad_sasih"] + rules["bad_wuku"] + rules["seven_days"]):
        return None
    if any(_AVOID_RE.search(s) or _JUDGEMENT_RE.search(s) for s in _sentences(day.get("definition"))):
        return None
    sasih = content.is_kind_of(day["id"], "sasih")
    name = day["name"][:1].upper() + day["name"][1:]
    out = [f"{name} sendiri tidak termasuk {'sasih' if sasih else 'hari'} yang dihindari untuk Ngaben."]
    good = [c for c in (rules["good_sasih"] if sasih else rules["good_wuku"]) if names_it.search(c)]
    if good:
        out.append(f"Menurut {'sasih' if sasih else 'wuku dan wewaran'}, {'; '.join(good)}.")
    meeting = None
    if sasih:
        # the avoided sasih kinds whose card names it in a meeting of wuku and sasih
        for tid in _named_terms(" ".join(rules["bad_sasih"]), everyday=True):
            definition = content.entity_def.get(tid) or ""
            clause = next((c.strip() for s in _sentences(definition) for c in re.split(r"\s*;\s*|:\s+", s)
                           if names_it.search(c) and re.search(r"\bwuku\s+\w+.*\bpada\s+sasih\b", c, re.I)), None)
            if clause:
                clause = re.sub(r"^(?:serta|dan)\s+", "", clause.rstrip("."), flags=re.I)
                meeting = (f"Namun, {day['name']} dihindari bila jatuh sebagai {content.entity_name[tid]}, yaitu pada "
                           f"pertemuan {clause}. {_first_sentence(definition, limit=10 ** 6)}")
                break
    if meeting:
        out.append(meeting)
    else:
        out.append(f"Menurut sasih, yang dihindari untuk Ngaben: {'; '.join(rules['bad_sasih'])}." if sasih else
                   f"Menurut wuku dan wewaran, {'; '.join(rules['bad_wuku'])}.")
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
_AVOIDED_DAYS_Q_RE = re.compile(rf"\b(?:dihindari|hindari|buruk|jelek|pantang|dilarang|larangan|jangan)\b"
                                rf"|\b{_NOT}\s+(?:boleh|baik|bagus|cocok|diperbolehkan|dibolehkan)\b", re.I)


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
            out.append("Alasannya: " + " ".join(reasons))
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
                return " ".join([_without_other_names(o) for o in opening] + [s])
    return None


_ORDER_WORD_RE = re.compile(r"\b(?:setelah|sesudah|sebelum|sebelumnya|sesudahnya|setelahnya)\b", re.I)


def _same_thing_answer(user_msg: Text, enriched: List[Dict[str, Any]], topic_id: Optional[str] = None) -> Optional[Text]:
    """Two names of one rite or thing compared: that they are one, by the edge that says so, and what the other name's
    card says of where it is used. "apa perbedaan palebon dan ngaben" got "Perbedaan utama terletak pada penggunaan
    sarana dan tahapan awal tertentu" -- read off which card an edge happens to sit on -- though palebon is
    Ngaben's refined name (bot test 2026-11-05). None unless an other-name edge joins the first two terms -- or one card
    is both sides: "bedanya dengan melukat?" after ngalukat (melukat is its other spelling) described ngalukat and added
    "Ini sama dengan penjelasan saya sebelumnya" (style test 2026-11-07). Only when that card is the topic: "bedanya sama
    dewa pitara apa?" after atma and pitra compares dewa pitara with pitra, and got "Dewa pitara dan dewa hyang adalah
    dua sebutan untuk hal yang sama" (snapshot 2026-11-07)."""
    if (len(enriched) == 1 and topic_id == enriched[0]["id"] and _COMPARE_Q_RE.search(user_msg)
            and _OMITTED_SUBJECT_RE.search(user_msg)):
        e = enriched[0]
        other = e.get("typed_as") or e.get("asked_as")
        if other and _ortho_key(other) != _ortho_key(e["name"]):
            what = "upacara" if get_content().entity_type.get(e["id"]) in _STAGE_TYPES else "hal"
            lead = _first_sentence(_deterministic_answer([dict(e, aspect_facts=[])]) or "", limit=500) or ""
            return (f"{other[:1].upper()}{other[1:]} dan {e['name']} adalah dua sebutan untuk {what} yang sama, bukan dua "
                    f"{what} yang berbeda." + (f" {lead}" if lead else ""))
    # ... or the message names one card by two of its names: "apa bedanya ngaben dan pengabenan" (user, 2026-11-12)
    if len(enriched) == 1 and _COMPARE_Q_RE.search(user_msg):
        e = enriched[0]
        # (each run of 1-3 words resolving to the card as a name, alias or form of it: the term scan keeps one per card)
        resolver, words = get_resolver(), _WORD_RE.findall(user_msg.lower())
        surfaces = []
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                sf = " ".join(words[i:i + n])
                hit = resolver.resolve(sf) if not _is_everyday_word(sf, resolver) or n > 1 else None
                if (hit and hit.id == e["id"] and hit.via != "fuzzy"
                        and not any(sf in s.split() or sf in s for s in surfaces)):
                    surfaces.append(sf)
        if len({_ortho_key(sf) for sf in surfaces}) >= 2:
            what = "upacara" if get_content().entity_type.get(e["id"]) in _STAGE_TYPES else "hal"
            lead = _first_sentence(_deterministic_answer([dict(e, aspect_facts=[])]) or "", limit=500) or ""
            a, b = surfaces[0], surfaces[1]
            return (f"{a[:1].upper()}{a[1:]} dan {b} adalah dua sebutan untuk {what} yang sama, bukan dua {what} yang "
                    f"berbeda." + (f" {lead}" if lead else ""))
    if len(enriched) < 2 or not _COMPARE_Q_RE.search(user_msg):
        return None
    a, b = enriched[0], enriched[1]
    # (not DIKENAL_SEBAGAI, which also reads a kind's name as the class's: "disuguhi sajen kecil yang disebut
    # pengulapan" made "sajen kecil dikenal sebagai pengulapan", and "bukan dua hal yang berbeda" would follow)
    preds = {"SAMA_DENGAN", "SEBUTAN_HALUS_UNTUK", "SEBUTAN_UNTUK"}
    link = next(((x, r) for x, y in ((a, b), (b, a)) for r in x.get("relationships") or []
                 if r.get("relation") in preds and r.get("outgoing") and r.get("target_id") == y["id"]), None)
    if not link:
        return None
    named, r = link
    content = get_content()
    what = "upacara" if all(content.entity_type.get(x["id"]) in _STAGE_TYPES for x in (a, b)) else "hal"
    statement = (r.get("statement") or "").strip().rstrip(".")
    lead = _first_sentence(_deterministic_answer([dict(named, aspect_facts=[])]) or "", limit=500) or ""
    return (f"{a['name'][:1].upper()}{a['name'][1:]} dan {b['name']} bukan dua {what} yang berbeda: {statement}."
            + (f" {lead}" if lead and lead.rstrip(".").lower() != statement.lower() else ""))


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
    sentences = _sentences(e.get("definition"))
    picked = [s for s in sentences if any(_grounded(w, _content_words(s)) for w in asked)]
    if len(picked) < 2:
        return None
    # the two cases are the sentences holding the most of what the question tells apart, by root ("giginya" is gigi):
    # the card's whole text under "Yang tersedia tentang jenazah bayi:" read as a miss, its four tiers for two cases
    # (plan #31, 2026-11-13). Not the card's first sentence, which says what the term is, while two others remain.
    name_roots = _sentence_roots(" ".join([e["name"]] + list(e.get("aliases") or [])))
    told = {_root(w) for w in _WORD_RE.findall(user_msg.lower())
            if len(w) >= 4 and w not in _STOPWORDS_ID and w not in _QUESTION_WORDS and not _COMPARE_Q_RE.search(w)
            and w not in {"prosesi", "proses", "upacara", "apakah", "adakah"}} - name_roots
    # (what the cases differ in -- "gigi ... tanggal" -- without the values the question sets against each other:
    # sudah / belum; "sebelum" shares belum's root)
    told -= {_root(w) for w in ("sudah", "belum", "masih", "telah", "tidak", "bukan", "lebih", "kurang", "yang")}
    cases = [s for s in picked if told and told <= {_root(w) for w in _WORD_RE.findall(s.lower()) if len(w) >= 3}]
    if len(cases) > 2 and sentences and cases[0] is sentences[0]:
        cases = cases[1:]
    if len(cases) < 2:
        cases = picked
    # a whether-question about a difference gets its verdict first: the card tells the cases apart
    verdict = ("Ya, ada. " if _whether_question(user_msg) and re.search(r"\b(?:beda|perbedaan|berbeda)\w*", user_msg, re.I)
               else "")
    return verdict + " ".join(cases)


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
    # (not a why-question: "kenapa atma wedana dilakukan setelah ngaben?" knows the order and asks the reason -- it got
    # "Atma wedana dilakukan sesudah ngaben. Atma wedana dilakukan setelah ngaben." and no reason, style test 2026-11-06)
    if len(enriched) < 2 or not _ORDER_Q_RE.search(user_msg) or _WHY_Q_RE.search(user_msg) or not (
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
    # an order fact that only says the line above again goes ("... dilakukan setelah ngaben" under "... sesudah ngaben")
    said = re.sub(r"\bsesudah\b", "setelah", out[0].lower())
    out += [f[:1].upper() + f[1:].rstrip(".") + "." for f in facts
            if f and re.sub(r"\bsesudah\b", "setelah", f.lower().rstrip(".") + ".") != said]
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
        for part in _SENT_PART_RE.findall(out):
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
    # which one, not what it is: "yang paling besar apa?" got the levels' definition in front of "yang paling besar
    # adalah utama" (style test 2026-11-06)
    if re.search(r"^\W*yang\b|\byang\s+(?:paling|ter[a-z]{3,}|mana)\b|\bmana\s+yang\b", user_msg, re.I):
        return False
    if (_OVERVIEW_Q_RE.search(user_msg) or _WHAT_IS_RE.search(user_msg)
            or re.search(r"\barti(?:nya)?\b|\bmaksud(?:nya)?\b", user_msg, re.I)
            or re.search(r"\bapa(?:an)?\s*(?:sih|ya|kah|tuh|dong)?\s*[?.!]*\s*$", user_msg, re.I)):
        return True
    return all(w in _WHAT_IS_FILLER for w in _mentioned_terms(user_msg, get_resolver())[1])


_KNOWN_WORDS: Optional[frozenset] = None
_MULTIWORD_SURFACES: Optional[List[Tuple[str, bool]]] = None
_AFFIX_PREFIXES = frozenset({"di", "ke", "se", "be", "me", "pe", "ber", "ter", "per", "mem", "men", "pem", "pen"})
_AFFIX_SUFFIXES = frozenset({"nya", "kan", "an", "i", "lah", "kah", "pun", "ku", "mu"})


_KB_ONLY_WORDS: Optional[frozenset] = None


def _known_words() -> frozenset:
    """Every word written as some source writes it: the whole everyday list, every word of the KB's names, aliases and
    cards, and every word of the source corpus. Spellings Qwen takes from these ("Wisnu", "sthana", "pamuput",
    "ketiadaan") are no misspellings, though the context may lack them."""
    global _KNOWN_WORDS, _KB_ONLY_WORDS
    if _KNOWN_WORDS is None:
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


_FREQUENT_BY_PREFIX: Optional[Dict[str, tuple]] = None


def _frequent_words_by_prefix() -> Dict[str, tuple]:
    """The frequent everyday words (the resolver's list) by their first four letters, 8+ letters long."""
    global _FREQUENT_BY_PREFIX
    if _FREQUENT_BY_PREFIX is None:
        index: Dict[str, list] = {}
        for w in get_resolver().common_words:
            if len(w) >= 8 and w.isalpha():
                index.setdefault(w[:4], []).append(w)
        _FREQUENT_BY_PREFIX = {k: tuple(v) for k, v in index.items()}
    return _FREQUENT_BY_PREFIX


def _affixed_known(word: str, known: frozenset) -> bool:
    """`word` is a known word with a prefix and/or a suffix taken off ("jelaskan" = jelas + kan, "dijelaskan")."""
    stems = {word} | {word[len(p):] for p in _AFFIX_PREFIXES if word.startswith(p)}
    stems |= {s[:-len(x)] for s in stems for x in _AFFIX_SUFFIXES if s.endswith(x)}
    return any(len(s) >= 3 and s != word and s in known for s in stems)


def _affix_variant(a: str, b: str) -> bool:
    """One word is the other with an affix ("penyucian" / "penyuciannya", "bakar" / "dibakar"): no misspelling."""
    # (and the adjective in -is: "kosmologis" / "kosmologi")
    return any(x.startswith(y) and x[len(y):] in _AFFIX_SUFFIXES or x.endswith(y) and x[:-len(y)] in _AFFIX_PREFIXES
               or x == y + "s" and y.endswith("i") for x, y in ((a, b), (b, a)))


# (a name list may be long: "Kuncup melati, Bunga teleng, Daun intaran, ..., dan Daun terong polo: Bahan-bahan tumbuhan
# yang digunakan.")
_ITEM_GLOSS_RE = re.compile(r"(?m)^(?P<pre>[ \t]*(?:[-*•]|\d+\.)[ \t]+)(?P<name>[^:\n]{2,300}?)[ \t]*:[ \t]*(?P<gloss>\S[^\n]*)$")
# the words of a gloss that says only what class of thing an item is (_fix_item_glosses)
_HOLLOW_GLOSS_WORDS = frozenset("""kain sarana ritual bahan bahan-bahan tumbuhan tumbuh-tumbuhan benda benda-benda alat
alat-alat perlengkapan barang unsur komponen elemen berbagai lain lainnya lain-lain proses prosesi upacara yang digunakan
dipakai dalam pada untuk sebagai ini tersebut juga""".split())


_STRONG_MODAL_RE = re.compile(r"(?<![\w-])(?<!tidak )(?<!tak )(?<!bukan )(?<!belum )(?<!gak )(?<!nggak )"
                              r"(?:wajib|harus|mesti|diwajibkan(?:\s+untuk)?)\s+(di[a-z]{3,})\b", re.I)


def _fix_modal_strength(answer: Text, context_text: Text, user_msg: Text = "") -> Text:
    """A must the context never says, where it says may or should: "kalau umurnya 6 bulan bagaimana?" got "... wajib
    dibakar (mageseng)", while jenazah bayi's card says a child of five months and over "boleh atau sebaiknya dibakar"
    (style test 2026-11-07). The context's own words replace the must. Not a negated must ("tidak harus dilakukan" is
    no "tidak boleh"), not one the question says itself ("kenapa harus dibuat pada hari pembakaran?"), and only into
    "boleh" / "sebaiknya" -- "dapat dibuat oleh sulinggih" says who can, not that it need not."""
    def soften(m: "re.Match") -> Text:
        verb = m.group(1)
        strong = rf"\b(?:wajib|harus|mesti|diwajibkan|keharusan)\s+(?:\w+\s+)?{re.escape(verb)}\b"
        if re.search(strong, context_text, re.I) or re.search(strong, user_msg, re.I):
            return m.group(0)
        weak = re.search(rf"\b((?:boleh|sebaiknya)(?:\s+atau\s+(?:boleh|sebaiknya))?)\s+{re.escape(verb)}\b",
                         context_text, re.I)
        if not weak:
            return m.group(0)
        said = weak.group(1).lower()
        return f"{said[:1].upper() + said[1:] if m.group(0)[:1].isupper() else said} {verb}"
    return _STRONG_MODAL_RE.sub(soften, answer)


def _fix_item_glosses(answer: Text) -> Text:
    """A list item glossing a KB term with words its own card never uses gets the card's gloss: asked what to prepare
    for Ngaben, Qwen listed "Wadah: Tempat untuk menaruh banten atau sarana lainnya", "Pengawak: Sarana pembawa
    jenazah", "Daksina: Hadiah atau upah untuk pendeta (Sulinggih)" -- the context had them only in "X digunakan dalam
    ngaben" facts (style test 2026-11-07). An item listing names ("Mlaspas kajang: banten peras, daksina, ...") is no
    gloss and stays."""
    resolver, content = get_resolver(), get_content()

    def fix(m: "re.Match") -> Text:
        name, gloss = m.group("name").strip(), m.group("gloss").strip()
        hit = resolver.resolve(name)
        # (the item's name as a name of the card: "Tempat Ngerorasin: Pura Dalem adalah tempat diadakannya ngerorasin"
        # names a place, and became atma wedana's gloss)
        names = [hit.name] + list(hit.entity.get("aliases") or []) if hit else []
        card_named = bool(hit and hit.via in ("exact", "alias") and _ortho_key(name) in {_ortho_key(n) for n in names})
        # a gloss naming only what class of thing it is: "Kamben: Kain yang digunakan dalam proses.", "Kawangen dan
        # Kawangen jeriji: Sarana ritual yang digunakan." (how Pabersihan Mati goes, live run 2026-11-14) -- the card's
        # gloss, or the names alone
        words = set(re.findall(r"[a-z-]+", gloss.lower()))
        if (words and words <= _HOLLOW_GLOSS_WORDS
                and all(len(p.split()) <= 4 for p in re.split(r",\s*(?:dan\s+|serta\s+)?|\s+(?:dan|serta)\s+", name))):
            own = _gloss(hit.id) if card_named else ""
            return f"{m.group('pre')}{name}: {own[:1].upper() + own[1:]}" if own else f"{m.group('pre')}{name}"
        if not card_named:
            return m.group(0)
        # (a stage's line naming its sarana is no gloss, nor one naming a single one: "Nyiramang layon: banten
        # byakawonan.")
        parts = [p for p in re.split(r",\s*|\s+dan\s+", gloss.rstrip(".")) if p.strip()]
        if parts and 2 * sum(bool(_named_terms(p, everyday=True)) for p in parts) >= len(parts):
            return m.group(0)
        card = content.best_definition(hit.id) or ""
        words = _content_words(gloss, min_len=4) - _content_words(name, min_len=4)
        if not card or not words:
            return m.group(0)
        vocab = _content_words(card, min_len=4)
        if 2 * sum(_grounded(w, vocab) for w in words) >= len(words):
            return m.group(0)
        own = _gloss(hit.id)
        return f"{m.group('pre')}{name}: {own[:1].upper() + own[1:]}" if own else f"{m.group('pre')}{name}"
    return _ITEM_GLOSS_RE.sub(fix, answer)


def _trim_card_retellings(answer: Text, user_msg: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A why-answer gives the reason, not the whole card of a term the reason names: "kenapa abu jenazah dihanyutkan ke
    laut?" had "Pancamahabutha adalah lima unsur alam ..., yaitu pertiwi (unsur padat, yaitu tulang dan daging), apah
    (...), teja (...), bayu (...), dan akasa (...)." after its reason (Claude's review, L2, 2026-11-13). A later sentence
    "X adalah ..." about a card none of the question's terms is, mostly that card's words and with no reason or purpose
    word nor a question term in it, keeps the card's first clause."""
    if not enriched or not _WHY_Q_RE.search(user_msg):
        return answer
    resolver, content = get_resolver(), get_content()
    asked = {e["id"] for e in enriched}
    asked_names = [n for e in enriched for n in [e.get("name")] + list(e.get("aliases") or []) if n]
    reason = re.compile(rf"\b(?:{_REASON_MARKERS}|{_PURPOSE_MARKERS})\b", re.I)
    for s in [x.strip() for x in _SENT_PART_RE.findall(answer) if x.strip()][1:]:
        m = re.match(r"((?:[\w-]+\s+){0,3}?[\w-]+)\s+(?:adalah|merupakan|ialah)\s+", s)
        hit = resolver.resolve(m.group(1)) if m else None
        if (not hit or hit.via not in ("exact", "alias") or hit.id in asked or reason.search(s)
                or any(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", s, re.I) for n in asked_names)):
            continue
        roots = _sentence_roots(s) - _sentence_roots(m.group(1))
        card = _sentence_roots(content.best_definition(hit.id) or "")
        short = _short_gloss(hit.id, limit=140)
        if len(roots) >= 10 and len(roots & card) >= 0.7 * len(roots) and short and len(short) < 0.7 * len(s):
            answer = answer.replace(s, f"{m.group(1)} adalah {short}.", 1)
    return answer


def _fix_stray_accents(answer: Text, context_text: Text) -> Text:
    """A Latin letter with a diacritic the context never writes loses it: Qwen wrote "Sawá Wédana adalah Ngaben tingkat
    utamamíng utamá ... sêsajén ... wibawá" (style test 2026-11-07); Indonesian writes none. Vowels only: the KB's one
    such letter is the ç of Raçadana and toyo çarira, which an answer keeps even when its card is not in the context."""
    used = set(context_text)

    def plain(m: "re.Match") -> Text:
        c = m.group(0)
        base = unicodedata.normalize("NFD", c)[0]
        return base if c not in used and base in "aeiouAEIOU" else c
    return re.sub(r"[À-ÖØ-öø-ÿĀ-ſ]", plain, answer)


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
        # an everyday word one letter off, long and with its first four letters ("sementera" -> sementara; Tier B on
        # Qwen, 2026-11-04): only to a frequent word of the same length, only when exactly one is that near, and
        # never a known word with an affix ("jelaskan" is no word of the lists but "jelas" is; it became "jelasken")
        if len(lw) >= 8 and not _affixed_known(lw, known):
            same = [c for c in _frequent_words_by_prefix().get(lw[:4], ()) if len(c) == len(lw)
                    and Levenshtein.distance(lw, c) == 1]
            if len(same) == 1:
                return respell(w, same[0])
        # ... or an everyday word of this answer's own context with a letter the model dropped (and one more slip at
        # most), its first three letters kept: "Segean keturunan mendiang menjunjung lancingan" under lancingan's
        # "segenap keturunan" (2026-11-12, twice on Qwen). One letter longer only: same-length or longer-apart pairs are
        # real words the lists lack -- "menusuk" became "menurut", "pembuatnya" "pembuatannya" (snapshot 2026-11-12).
        if len(lw) >= 6 and not _affixed_known(lw, known):
            ctx_near = sorted((Levenshtein.distance(lw, c), c) for c in ctx_words
                              if len(c) == len(lw) + 1 and c[:3] == lw[:3] and c not in targets and c in known)
            ctx_near = [(d, c) for d, c in ctx_near if d <= 2]
            if ctx_near and (len(ctx_near) == 1 or ctx_near[0][0] < ctx_near[1][0]):
                return respell(w, ctx_near[0][1])
            # ... or one vowel swapped for another in such a word of the same length: "lelehur" under the context's
            # "leluhur" (Tier B on Qwen, 2026-11-13). A vowel only: a consonant pair is a real word the lists lack
            # ("menusuk" / "menurut" above)
            same = [c for c in ctx_words if len(c) == len(lw) and c[:2] == lw[:2] and c in known
                    and sum(a != b for a, b in zip(lw, c)) == 1
                    and all(a in "aeiou" and b in "aeiou" for a, b in zip(lw, c) if a != b)]
            if len(same) == 1:
                return respell(w, same[0])
        return w
    answer = re.sub(r"(?<![\w-])[A-Za-z][A-Za-z-]*[A-Za-z](?![\w-])", fix_word, answer)
    if _MULTIWORD_SURFACES is None:
        resolver = get_resolver()
        # (surface, whether a word before its last is no everyday word -- the lost-last-letter rule needs that)
        _MULTIWORD_SURFACES = [(s, any(not _is_everyday_word(w, resolver) for w in s.split()[:-1]))
                               for s in resolver.surface if len(s.split()) >= 2 and re.fullmatch(r"[a-z ]+", s)]
    for s, strict in _MULTIWORD_SURFACES:
        if s not in ctx:
            continue
        head, last = s.rsplit(" ", 1)

        def fix_name(m: "re.Match") -> str:
            got = m.group(2).lower()
            # its last letter lost ("Nuduk Gali"), a stray ending ("Ida Sang Sulinggihan", "Asti Wedanas"), or letters
            # swapped ("matur piniung") -- the last two only for a spelling no source writes (Tier B on Qwen, 2026-11-04)
            # ... or two letters off, its first two kept ("matur pinoing", Tier B on Qwen 2026-11-13)
            if got != last and len(last) >= 5 and (
                    strict and last[:-1] == got
                    or got not in known and (got in (last + "s", last + "an")
                                             or sorted(got) == sorted(last) and got[:2] == last[:2]
                                             or len(last) >= 6 and got[:2] == last[:2] and not _affixed_known(got, known)
                                             and Levenshtein.distance(got, last) <= 2)):
                return f"{m.group(1)} {respell(m.group(2), last)}"
            return m.group(0)
        head_rx = r"\s+".join(re.escape(w) for w in head.split())
        answer = re.sub(rf"(?<![\w-])({head_rx})\s+([A-Za-z]+)(?![\w-])", fix_name, answer, flags=re.I)
        # its first word misspelled before the right last one, a word no source writes with its first three letters:
        # "matur piuning ke Puring Dalem" (pura dalem; Tier B on Qwen, 2026-11-13)
        if len(head.split()) == 1 and len(head) >= 4:
            def fix_head(m: "re.Match") -> str:
                got = m.group(1).lower()
                if (got != head and got[:3] == head[:3] and got not in known and got not in ctx_words
                        and not _affixed_known(got, known) and abs(len(got) - len(head)) <= 2
                        and Levenshtein.distance(got, head) <= 3):
                    return f"{respell(m.group(1), head)} {m.group(2)}"
                return m.group(0)
            answer = re.sub(rf"(?<![\w-])([A-Za-z]+)\s+({re.escape(last)})(?![\w-])", fix_head, answer, flags=re.I)
    # the context's verb made a noun after "merupakan": nganyut's card "melambangkan pelepasan terakhir" came back twice as
    # "merupakan pelambangkan pelepasan terakhir" (style test 2026-11-07) -- a known word with affixes, which the rules
    # above leave alone; only when the context writes the me- verb
    answer = re.sub(r"\bmerupakan\s+pe([a-z]{3,}kan)\b",
                    lambda m: f"me{m.group(1)}" if f"me{m.group(1)}" in ctx_words else m.group(0), answer)
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
            # a judging sentence of several clauses is measured clause by clause (below): as a whole, Sasih Kadasa's
            # "... masa Uttarayana ...: membakar jenazah ... dianggap mencemari ..., sebab ... pesamuhan ...; untuk Mamukur
            # ..." came back under an answer that gave its reason in full (style test 2026-11-07)
            several = len([c for c in re.split(r"\s*[;:]\s*", s.strip().rstrip(".")) if c]) > 1
            if words and (s is judging and not several and sum(_grounded(w, said) for w in words) < 0.6 * len(words)
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

# any negation: "babelonyoh dan emas adalah dua hal yang berbeda dan tidak saling terkait" links nothing; nor does a
# sentence setting the two side by side ("Pabersihan mati adalah tahap kedua ..., sedangkan sorohan kecil adalah ...")
_REL_NEG_RE = re.compile(r"\b(?:tidak|tak|bukan|belum|tanpa|sedangkan|sementara|sebaliknya|berbeda)\b", re.I)

_REL_LINK_RE = re.compile(
    r"\b(?:hubungan|kaitan|terkait|berhubungan|berkaitan|sama-sama|keduanya|kedua-duanya|"
    r"tahap\w*|bagian|sarana|tujuan|menuju|mencapai|peran|fungsi|proses|"
    r"melalui|dihubungkan|menghubungkan|langkah|jalan)\b", re.I
)
# (no "adalah" / "merupakan": "Pitra Yadnya adalah ..., sedangkan Moksa adalah ..." describes both and links nothing)


def _entity_surfaces(e: Any) -> List[str]:
    content = get_content()
    resolver = get_resolver()
    if isinstance(e, str):
        eid, ename = e, e
        aliases = []
        asked_as = None
        typed_as = None
    else:
        eid = e.get("id") or ""
        ename = e.get("name") or ""
        aliases = list(e.get("aliases") or [])
        asked_as = e.get("asked_as")
        typed_as = e.get("typed_as")

    names = [ename, content.entity_name.get(eid, "")]
    if eid and resolver and hasattr(resolver, "by_id"):
        names += list((resolver.by_id.get(eid) or {}).get("aliases") or [])
    names += aliases
    if asked_as:
        names.append(asked_as)
    if typed_as:
        names.append(typed_as)
    result: List[str] = []
    for n in names:
        if n and n.strip():
            ns = n.strip()
            result.append(ns)
            wt = _without_titles(ns)
            if wt and wt != ns:
                result.append(wt)
    seen = set()
    dedup: List[str] = []
    for s in result:
        low = s.lower()
        if low not in seen and len(low) >= 3:
            seen.add(low)
            dedup.append(s)
    return dedup


def _explains_relationship(text: Text, a: Any, b: Any) -> bool:
    """True when text actually explains how a and b are related or connected (even via another stage/concept),
    so we never contradict the answer with 'tidak ada hubungan / informasi belum tersedia'."""
    if not text or not a or not b:
        return False
    s_a = _entity_surfaces(a)
    s_b = _entity_surfaces(b)
    if not s_a or not s_b:
        return False
    re_a = re.compile(rf"\b(?:{'|'.join(re.escape(n) for n in s_a)})\b", re.I)
    re_b = re.compile(rf"\b(?:{'|'.join(re.escape(n) for n in s_b)})\b", re.I)

    for s in _sentences(text):
        if _REL_NEG_RE.search(s):
            continue
        has_a = bool(re_a.search(s))
        has_b = bool(re_b.search(s))
        if has_a and has_b and _REL_LINK_RE.search(s):
            return True

    sents = [s for s in _sentences(text) if not _REL_NEG_RE.search(s)]
    for i in range(len(sents) - 1):
        s1, s2 = sents[i], sents[i + 1]
        pair = f"{s1} {s2}"
        if re_a.search(pair) and re_b.search(pair):
            if re.search(r"\b(?:hubungan\s+(?:ini|antara)|keduanya|kaitan|melalui|sehingga|dengan\s+demikian)\b", pair, re.I):
                return True
    return False


_CONTRADICTORY_NO_LINK_RE = re.compile(
    r"^\s*(?:Maaf,\s+)?(?:"
    r"(?:Informasi\s+(?:tentang|mengenai)\s+)?(?:hubungan|kaitan|perbedaan|persamaan|kesamaan)(?:\s+langsung)?\s+antara\s+(?P<a>.+?)\s+dan\s+(?P<b>.+?)\s+belum\s+(?:tersedia|tercatat)"
    r"|Tidak\s+ada\s+(?:hubungan|kaitan|perbedaan|persamaan|kesamaan)(?:\s+langsung)?\s+antara\s+(?P<a2>.+?)\s+dan\s+(?P<b2>.+?)\s+yang\s+(?:tercatat|tersedia|tercantum)"
    r"|Maaf,\s+informasi\s+detail\s+mengenai\s+hal\s+tersebut\s+belum\s+(?:tersedia|tercatat)"
    r")\s*[.:!?]\s*",
    re.I
)


def _drop_contradictory_no_link(answer: Text, enriched: Optional[List[Dict[str, Any]]] = None) -> Text:
    """Drop contradictory refusal sentences if the rest of the answer explains the relationship or facts."""
    if not answer:
        return answer
    m = _CONTRADICTORY_NO_LINK_RE.match(answer)
    if m:
        rest = answer[m.end():].lstrip()
        rest = re.sub(r"^(?:Secara\s+tidak\s+langsung,?\s*)", "", rest, flags=re.I)
        if enriched and len(enriched) >= 2:
            a_ent, b_ent = enriched[0], enriched[1]
        else:
            a_name = (m.group("a") or m.group("a2") or "").strip()
            b_name = (m.group("b") or m.group("b2") or "").strip()
            a_ent = {"id": a_name, "name": a_name} if a_name else None
            b_ent = {"id": b_name, "name": b_name} if b_name else None
        if a_ent and b_ent and _explains_relationship(rest, a_ent, b_ent):
            return rest[:1].upper() + rest[1:] if rest else answer
    return answer


def _say_no_link(answer: Text, a: Dict[str, Any], b: Dict[str, Any]) -> Text:
    """A relation question about two terms nothing joins -- no edge, no chain of kinds or parts, a definition naming
    neither -- says so first when the answer does not: "Pemangku berhubungan dengan ayaban sesayut bagaimana" got
    "Hubungan antara pemangku dan ayaban sesayut ... adalah bahwa pemangku tidak memberikan ayaban sesayut", a link
    read from sulinggih giving it (Tier B 2026-10-30; the run before had "Tidak ada hubungan langsung ..."). An
    opening "Hubungan (antara) ..." is then the indirect link, as in _complete_chain_link: not cut -- "Hubungan antara
    yadnya dan kayu cendana terletak pada peran kayu cendana sebagai ... sarana ... dalam upacara Ngaben" is true."""
    if _NO_LINK_RE.search(answer):
        return answer
    if _explains_relationship(answer, a, b):
        return answer
    if (b["name"].lower() in _named_in(a.get("definition") or "")
            or a["name"].lower() in _named_in(b.get("definition") or "")):
        return answer
    note = f"Tidak ada hubungan langsung antara {a['name']} dan {b['name']} yang tercatat."
    first, sep, rest = answer.strip().partition("\n\n")
    if not (sep and _opens_with(first, a)):
        first, rest = "", answer
    rest = re.sub(r"^\s*Hubungan\b", "Secara tidak langsung, hubungan", rest.lstrip(), count=1)
    # an answer that says first what a is ("apa itu tri murthi dan apa hubungannya dengan ngaben": "Trimurti ...
    # adalah ...") keeps that first; the note opens what follows (Tier B 2026-11-04)
    return (f"{first}\n\n" if first else "") + f"{note} {rest}".strip()


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
    # names as their cards write them, and a named set's members are in it, not kinds of it: "Dewa Siwa dan Dewa
    # Mahadewa sama-sama termasuk Panca Dewata", not "Dewa Siwa dan dewa mahadewa sama-sama jenis panca dewata"
    # (2026-11-06); in the name the user wrote when it is the card's own written another way ("dewa siwa" for shiwa)
    def name(i: str) -> str:
        own = content.entity_name.get(i, i)
        typed = next((s for e in enriched if e["id"] == i for s in (e.get("asked_as"), e.get("typed_as"))
                      if s and _same_name(s, own)), None)
        return _card_cased(i, typed)

    def kind_of(y: str) -> str:
        return f"termasuk {name(y)}" if _NUMERAL_SET_RE.match(content.entity_name.get(y, y)) else \
            f"termasuk jenis {name(y)}"

    def hop(x: str, rel: str, y: str) -> str:
        if rel == "TERMASUK_JENIS":
            return f"{name(x)} {kind_of(y)}"
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
        text = (f"{both} {kind_of(mid)}" if rel == "TERMASUK_JENIS"
                else f"{both} tahapan {name(mid)}" if content.entity_type.get(a["id"]) in _STAGE_TYPES
                else f"{both} bagian dari {name(mid)}")
    else:
        return _say_no_link(answer, a, b) if relation else answer

    def surfaces(i: str) -> List[str]:
        # with the name the user asked by and each without its title: the model's "Perbedaan utama antara Siwa dan
        # Dewa Mahadewa ..., meskipun keduanya sama-sama termasuk dalam Panca Dewata" said it (card "shiwa")
        names = [content.entity_name.get(i, i)] + list((resolver.by_id.get(i) or {}).get("aliases") or [])
        names += [e.get("asked_as") for e in enriched if e["id"] == i and e.get("asked_as")]
        return names + [_without_titles(n) for n in names]
    sentences = _SENT_PART_RE.findall(answer)

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
    # a shared parent the model already gives both, anywhere: "... keduanya sama-sama termasuk jenis usungan" -- the
    # opener said it a second time (style test 2026-11-06, "apa beda bade dan wadah?")
    # (the class itself after "termasuk / merupakan (jenis)": not "Semua jenis Ngaben ... sama-sama ...", which
    # kept "Ngaben massal dan Ngaben Svasta sama-sama termasuk jenis Ngaben" out)
    if not ids and any(re.search(r"\b(?:keduanya|kedua-duanya|sama-sama)\b", s, re.I)
                       and any(re.search(rf"\b(?:termasuk|merupakan|adalah)\s+(?:dalam\s+)?(?:salah\s+satu\s+)?"
                                         rf"(?:jenis\s+|bagian\s+dari\s+|tahap(?:an)?\s+|anggota\s+)?{re.escape(n)}\b", s, re.I)
                               for n in surfaces(hops[0][2]))
                       for s in sentences):
        return answer
    first = next((s for s in sentences if s.strip()), "")
    if re.search(r"\btidak ada (?:hubungan|kaitan|perbedaan)\b", first, re.I):
        cut = answer.index(first) + len(first)
        # (the names as their cards write them: "Pangringkes ...", replacing the refusal clause)
        return f"{text[:1].upper()}{text[1:]}.{answer[cut:]}"
    return f"{text[:1].upper()}{text[1:]}. {answer.lstrip()}"


_CONTRAST_RE = re.compile(r"\b(?:sedangkan|sementara\s+itu|sementara|sebaliknya|berbeda|perbedaan\w*|bedanya|beda|"
                          r"adapun|keduanya|bukan)\b", re.I)
# "Perbedaan utama antara X dan Y terletak pada fungsi, cara pembuatannya, ..." -- names the aspects, says no difference
# (ending its sentence: one going on after a colon -- "... terletak pada hakikat tujuannya: moksa adalah ...,
# sedangkan sorga ..." -- says the difference)
_HOLLOW_CONTRAST_RE = re.compile(r"\A\s*Perbedaan\s+(?:utama|mendasar|pokok)?\s*(?:antara\s+)?[^.:!?\n]{0,80}?"
                                 r"\bterletak\s+pada\b[^.:!?\n]*\.\s*", re.I)


# verbs that say what a thing is or is called, not one of its traits: a later clause holding only these tells nothing
# apart
_GENERIC_VERB_ROOTS = frozenset(_root(w) for w in (
    "dilakukan dilaksanakan diselenggarakan merupakan menjadi memiliki mempunyai berarti termasuk disebut dikenal "
    "dinamakan bernama").split())


def _top_level_parts(text: Text, seps: Text = ";:") -> List[str]:
    """`text` cut at each of `seps` outside brackets and quotes."""
    parts, depth, quote, cur = [], 0, False, []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch in "\"“”":
            quote = not quote
        if ch in seps and not depth and not quote:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _telling_gloss(e: Dict[str, Any], other: Dict[str, Any]) -> str:
    """What sets e apart from `other`, from the first sentence of e's card (plan #31, 2026-11-13: the whole sentence
    made "Perbedaannya: Dewa Siwa adalah ...; dalam Nawa Dewata ..., sedangkan ..." and pancamahabutha's colon list):
    its first clause, up to a ";" or ":" outside brackets, and a later clause only when its verb is one the other card
    uses too -- the same trait told differently: wadah's "wadah dipakai oleh suatu warga" against bade's "dipakai oleh
    golongan berkasta" (cut at the ";", wadah once lost who uses it, the difference from bade); Siwa's "berstana di
    tengah" against Mahadewa's "berstana di arah barat"."""
    g = _gloss(e["id"], limit=10 ** 6).rstrip(".")
    clauses = _top_level_parts(g)
    if not clauses:
        return g
    other_roots = {_root(w) for w in _WORD_RE.findall((other.get("definition") or "").lower())}
    other_rx = _names_rx(other)
    keep = [clauses[0]]
    for c in clauses[1:]:
        verbs = [w for w in _WORD_RE.findall(c.lower()) if re.match(r"(?:di|ber|ter|me)\w{3,}$", w)][:2]
        # (or one naming the other term: Ngaben Svasta's "tata pelaksanaannya sama dengan Asti Wedana" against Asti
        # Wedana)
        if (any(_root(v) in other_roots and _root(v) not in _GENERIC_VERB_ROOTS for v in verbs)
                or other_rx and other_rx.search(c)
                and not re.match(r"\s*(?:\w+\s+)?(?:juga\s+)?(?:disebut|dikenal|dinamakan|bernama)\b", c, re.I)):
            keep.append(c)
    # examples are not what tells two terms apart: "... upacara daur hidup manusia seperti upacara potong gigi
    # (mepandes)" (plan #31, the user's "potong gigi" in a manusa / dewa yadnya comparison)
    keep = [re.sub(r",?\s+(?:seperti|misalnya|contohnya)\s+[^;:]*?(?=,\s+(?:dan|serta)\s+|$)", "", c, flags=re.I)
            if len(re.split(r"\s+(?:seperti|misalnya|contohnya)\s+", c, flags=re.I)[0].split()) >= 4 else c
            for c in keep]
    return "; ".join(keep)


def _kind_contrast_lead(enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[Text]:
    """A kind compared with its own class is that class, done its own way: "apa itu ngaben masal dan apa bedanya dengan
    ngaben biasa" got "Perbedaannya: Ngaben massal adalah ..., sedangkan Ngaben adalah upacara pembakaran jenazah ..."
    and never said plainly that it is the same ceremony, held together to save cost (user's live session,
    2026-11-09). "<Kind> adalah salah satu jenis <Class>, jadi pada dasarnya tetap <Class>. Bedanya, <kind's card>."
    None unless one is a direct kind of the other."""
    content = get_content()
    a, b = enriched
    if a["id"] in content.kinds_of(b["id"]):
        kind, cls = a, b
    elif b["id"] in content.kinds_of(a["id"]):
        kind, cls = b, a
    else:
        return None
    g = _telling_gloss(kind, cls)
    if not g:
        return None
    kname = _card_cased(kind["id"], kind.get("asked_as") or kind.get("typed_as"))
    cname = _card_cased(cls["id"], cls.get("asked_as") or cls.get("typed_as"))
    title = f"{kname[:1].upper()}{kname[1:]}"
    # what sets it apart: its card without a leading "salah satu jenis <class> (yang)" the first clause already says
    own = re.sub(rf"^(?:merupakan\s+|adalah\s+)?(?:salah\s+satu\s+)?(?:jenis|bentuk|macam)\s+"
                 rf"{re.escape(cls['name'])}\b,?\s*(?:yang\s+)?", "", g, flags=re.I)
    if not own:
        return None
    verb_first = re.match(r"(?:di|me|ber|ter)\w+\b|(?:untuk|bagi|dengan|tanpa|berarti|merupakan|adalah)\b", own, re.I)
    differs = f"{title} {own}" if verb_first else f"{title} adalah {own}"
    # (not for a kind that stands in for its class: "Ngangsen ... pada dasarnya tetap Ngerorasin" above its card's
    # "upacara darurat/sementara yang menggantikan Ngerorasin")
    if re.search(r"\b(?:menggantikan|pengganti|sementara|darurat)\b", g, re.I):
        return f"{title} adalah salah satu jenis {cname}. Bedanya, {differs}."
    same = (f"sama dengan {cname} biasa" if re.search(rf"\b{re.escape(cls['name'])}\s+biasa\b", user_msg, re.I)
            else f"tetap {cname}")
    return f"{title} adalah salah satu jenis {cname}, jadi pada dasarnya {same}. Bedanya, {differs}."


# a good-day detail or a ritual direction: a side fact of a card, not what sets two terms apart
_SIDE_DETAIL_RE = re.compile(r"\bsasih\s+\w+|\bhari\s+baik\b|\bdewasa\s+ayu\b|\bpradaksina\b|\bprasawya\b", re.I)


def _drop_irrelevant_comparison_sentences(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text) -> Text:
    """A comparison of two terms leaves out the side details nobody asked: "apa perbedaan manusa yadnya dengan dewa
    yadnya" went on with "Selain itu, sasih Kalima dianggap baik untuk pelaksanaan Manusa Yadnya" and the pradaksina /
    prasawya directions (user, 2026-11-10: "the bot dont need to mention incredibly small details that are not
    necessarily relevant"). Only good days and ritual directions, and only when neither the question nor the two
    terms are about them: a sentence naming Ngaben stays -- this is a Ngaben bot."""
    if len(enriched) != 2:
        return answer
    names = " ".join(n for e in enriched for n in [e["name"], e.get("asked_as") or "", e.get("typed_as") or ""])
    # (nor when a term is itself a calendar or direction thing: "cermin kecil dan malamasa itu sama atau beda" lost what
    # malamasa is, "nistaning nista dan wuku" what wuku is -- snapshot 2026-11-12)
    firsts = " ".join(_first_sentence(e.get("definition") or "", limit=400) for e in enriched)
    if re.search(r"\b(?:sasih|bulan|hari|kapan|waktu|dewasa|arah|putar\w*|mutar\w*)\b", user_msg, re.I) \
            or _SIDE_DETAIL_RE.search(names) or re.search(r"\b(?:sasih|dewasa|hari)\b", names, re.I) \
            or _SIDE_DETAIL_RE.search(firsts) or re.search(r"\b(?:kalender|pawukon|wuku|sasih)\b", firsts, re.I):
        return answer
    out = []
    for part in re.split(r"(\n+)", answer):
        if part.startswith("\n") or not part.strip():
            out.append(part)
            continue
        sents = _sentences(part)
        kept = [s for s in sents if not _SIDE_DETAIL_RE.search(s)]
        if len(kept) == len(sents):
            out.append(part)
        elif kept:
            out.append(" ".join(kept))
    res = re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()
    return res or answer


# What a sentence that only announces a difference is made of: the difference word, what kind of difference, the
# aspect it is in, and the words joining them -- "Perbedaan mendasar terletak pada tujuan dan sasaran upacara.",
# "Terdapat juga perbedaan dalam jenis dan pelaksanaan.", "Perbedaan kedua adalah dalam hal kelanjutan ritual."
# (2026-11-12, "apa perbedaan ngelungah dan nyekah?": the last stood alone once the model's next sentence had gone).
_DIFF_TALK_RE = re.compile(r"\b(?:perbedaan\w*|berbeda|beda(?:nya)?|membedakan|pembeda\w*)\b", re.I)
_ANNOUNCE_WORDS = frozenset((
    # what kind, which one
    "utama mendasar pokok penting besar nyata mencolok signifikan pertama kedua ketiga keempat kelima terakhir lain "
    "lainnya berikutnya selanjutnya lagi beberapa sejumlah "
    # joining words
    "terletak terlihat tampak ada terdapat adalah ialah merupakan pada dalam dari di hal segi sisi aspek antara dan "
    "serta atau juga pun jelas sangat cukup yang memiliki mempunyai terutama khususnya selain itu ini tersebut "
    "kemudian lalu keduanya masing-masing secara umum namun tetapi akan "
    # the aspects
    "tujuan sasaran fungsi peran makna arti jenis pelaksanaan penyelenggaraan cara lokasi tempat waktu urutan status "
    "kedudukan kondisi sarana alat bahan bentuk wujud posisi simbolisme penggunaan pembuatan persyaratan tahapan "
    "prosesi upacara ritual konteks cakupan sifat hakikat target objek kelanjutan hubungan asal filosofi filosofis "
    "tata pelaku pemimpin akhir rangkaian roh dasar hasil spiritual prosedural prosedur praktik teknis identitas penempatan "
    "karakteristik ciri konsep sistem esensi mekanisme proses nilai simbol simbolis dimensi kategori struktur susunan "
    "komposisi jumlah ukuran digunakan dipakai dilakukan dilaksanakan diselenggarakan").split())
# says how the two differ after all: a colon, a "whereas", an "i.e."
_SAYS_HOW_RE = re.compile(r":|\b(?:sedangkan|sementara|sebaliknya|yaitu|yakni|bahwa|seperti|misalnya)\b", re.I)


def _announces_only(text: Text, names_re: "re.Pattern", spare: int = 0) -> bool:
    """`text` says there is a difference, and in what, but not what it is (`spare`: words of no list it may have)."""
    if not _DIFF_TALK_RE.search(text) or _SAYS_HOW_RE.search(text):
        return False
    rest = _DIFF_TALK_RE.sub(" ", names_re.sub(" ", text))
    words = [re.sub(r"^(\w+)-\1$", r"\1", re.sub(r"nya$", "", w.lower())) for w in _WORD_RE.findall(rest)]
    return len([w for w in words if w and w not in _ANNOUNCE_WORDS]) <= spare


def _drop_announcing_sentences(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A comparison loses the sentences (and the closing clauses) that only announce a difference without saying it:
    "Perbedaan mendasar terletak pada tujuan dan sasaran upacara.", "Mamukur dan Ngangsen sama-sama termasuk jenis
    Atma Wedana, namun memiliki perbedaan mendasar dalam tujuan, kondisi pelaksanaan, dan sarana yang digunakan." ->
    "... jenis Atma Wedana." Each such heading made the model say the opening again under it (user, 2026-11-12: "it
    repeats a lot of points"). A "Perbedaan utama ... terletak pada <aspects>." with no colon is one wherever it
    stands (_HOLLOW_CONTRAST_RE took it only as the first sentence)."""
    names = [re.escape(n) for e in enriched for n in [e.get("name") or ""] + list(e.get("aliases") or [])
             + [e.get("asked_as") or "", e.get("typed_as") or ""] if n]
    if not names:
        return answer
    names_re = re.compile(rf"(?<![\w-])(?:{'|'.join(sorted(set(names), key=len, reverse=True))})(?![\w-])", re.I)
    out = []
    for part in re.split(r"(\n+)", answer):
        if part.startswith("\n") or not part.strip() or _LIST_ITEM_RE.match(part):
            out.append(part)
            continue
        kept = []
        sents = _sentences(part)
        for i, s in enumerate(sents):
            # (one unknown word is allowed in a heading with nothing after it in its paragraph: "Selain itu, terdapat
            # perbedaan dalam hubungan proseduralnya." ended an answer once the sentence under it went, 2026-11-12)
            if (_announces_only(s, names_re, spare=1 if i == len(sents) - 1 and len(s.split()) <= 12 else 0)
                    or (re.match(r"\s*Perbedaan\w*\b[^.:!?\n]*\bterletak\s+pada\b", s, re.I)
                        and not _SAYS_HOW_RE.search(s))):
                continue
            # a closing ", namun memiliki perbedaan ... dalam <aspects>" on a sentence that says something before it
            tail = re.search(r",\s*(?:namun|tetapi|akan\s+tetapi)\s+([^,.!?\n][^.!?\n]*)([.!?]?)\s*$", s)
            if tail and _announces_only(tail.group(1), names_re):
                s = s[:tail.start()].rstrip() + (tail.group(2) or ".")
            kept.append(s)
        if kept:
            out.append(" ".join(kept))
    res = re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()
    return res[:1].upper() + res[1:] if res else answer


# Words a restated frame is made of beside what it restates ("ditujukan khusus untuk ...", "dengan tujuan ...", "telah
# melalui proses ..."): they say nothing of their own.
_FRAME_LIGHT_ROOTS = frozenset(_root(w) for w in (
    "ditujukan diperuntukkan dikhususkan khusus khususnya untuk bagi kepada tujuan bertujuan tujuannya dengan yang "
    "telah sudah melalui proses tahap tahapan upacara ritual dilakukan dilaksanakan diselenggarakan secara spesifik "
    "utama utamanya terutama adalah merupakan sebaliknya sementara adapun").split())


def _trim_restated_frames(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """In a comparison, a sentence that frames its new fact with what the answer already said of the term goes straight
    to the fact: "Sebaliknya, Nyekah ditujukan untuk mendiang yang telah melalui proses Ngaben, dengan tujuan
    menyucikan badan halusnya agar atmanya benar-benar bebas ..." under an opening saying Nyekah is held after Ngaben to
    purify the subtle body -> "Sebaliknya, dengan Nyekah, atmanya benar-benar bebas ..."; "Ngelungah ditujukan khusus
    untuk jenazah bayi atau anak kecil, di mana jenazah ... dibakar" -> "Pada Ngelungah, jenazah ... dibakar" (user,
    2026-11-12: "it repeats a lot of points"; rule 17 asks for it and Qwen keeps the habit). Only when the frame's own
    words (half at least) are the answer's before it, and it holds no number or negation."""
    names = sorted({n for e in enriched for n in [e.get("name") or ""] + list(e.get("aliases") or [])
                    + [e.get("asked_as") or "", e.get("typed_as") or ""] if n}, key=len, reverse=True)
    if not names:
        return answer
    name_alt = "|".join(re.escape(n) for n in names)
    name_roots = _sentence_roots(" ".join(names))
    conn = r"(?P<conn>(?:Sebaliknya|Sementara\s+itu|Adapun|Di\s+sisi\s+lain|Selain\s+itu),\s*)?"
    joint = r",?\s+(?P<joint>di\s?mana|agar|supaya|sehingga|hingga)\s+(?P<rest>[^.!?\n]+)"
    shapes = [re.compile(rf"^(?P<ws>\s*){conn}(?:upacara\s+)?(?P<t>{name_alt})\s+(?P<frame>(?:ditujukan|diperuntukkan|"
                         rf"dikhususkan|dilakukan|dilaksanakan|diselenggarakan|bertujuan)\b[^.!?\n]*?){joint}", re.I),
              re.compile(rf"^(?P<ws>\s*){conn}Tujuan\s+(?:utama\s+)?(?:upacara\s+)?(?P<t>{name_alt})\s+adalah\s+"
                         rf"(?P<frame>[^.!?\n]*?){joint}", re.I),
              # "Pitra merupakan salah satu jenis atma, yang secara spesifik merujuk pada ..." under "Pitra adalah salah
              # satu jenis Atma ..." -> "Pitra secara spesifik merujuk pada ..." (Tier B on Qwen, 2026-11-12)
              re.compile(rf"^(?P<ws>\s*){conn}(?P<t>{name_alt})\s+(?P<frame>(?:adalah|merupakan)\b[^.!?\n]*?)(?P<comma>,?)\s+"
                         rf"(?P<joint>yang)\s+(?P<rest>[^.!?\n]+)", re.I)]
    out, last = [], 0
    for part in _SENT_PART_RE.finditer(answer):
        s = part.group(0)
        before = answer[:part.start()]
        m = next((x for x in (sh.match(s) for sh in shapes) if x), None) if before.strip() else None
        if m and not re.search(r"\b(?:tidak|tak|bukan|belum|tanpa)\b|\d", m.group("frame"), re.I):
            own = _sentence_roots(m.group("frame")) - _FRAME_LIGHT_ROOTS - name_roots
            # (a frame of short and common words only, "merupakan salah satu jenis atma", restates when every word of
            # it but the linking verb is in the answer before it)
            plain = {w.lower() for w in _WORD_RE.findall(m.group("frame"))} - {"adalah", "merupakan", "ialah"}
            said_words = {w.lower() for w in _WORD_RE.findall(before)}
            # (a "yang" with no comma before it -- "Tirtha Pangentas adalah tirtha terpenting dalam Ngaben yang berfungsi
            # ..." under the lead's "tirtha terpenting dalam Ngaben" -- only when every word of the frame is said: the
            # "yang" may narrow what the frame names, plan #31)
            need = 1.0 if m.groupdict().get("comma") == "" else 0.5
            if (own and len(own & _sentence_roots(before)) >= need * len(own)
                    or not own and plain and plain <= said_words):
                rest, joint = m.group("rest"), m.group("joint").lower()
                if joint == "yang":
                    # (the clause after "yang" says what the term does: it is the sentence's own predicate)
                    head = f"{m.group('conn') or ''}{m.group('t')} "
                elif joint in ("agar", "supaya"):
                    # the purpose the frame gave, said as the term's: "Sebaliknya, dengan Nyekah, atmanya benar-benar
                    # bebas" read stiff and left whose atma open -> "Nyekah bertujuan agar atma mendiang benar-benar
                    # bebas" (plan #31)
                    head = f"{m.group('conn') or ''}{m.group('t')} bertujuan {joint} "
                    rest = _own_nya(rest, m.group("frame"), before)
                else:
                    lead = "Pada" if re.match(r"di\s?mana", m.group("joint"), re.I) else "Dengan"
                    head = (f"{m.group('conn')}{lead.lower()} {m.group('t')}, " if m.group("conn")
                            else f"{lead} {m.group('t')}, ")
                    if lead == "Dengan":
                        rest = _own_nya(rest, m.group("frame"), before)
                out += [answer[last:part.start()], m.group("ws") + head + rest + s[m.end():]]
                last = part.end()
    return "".join(out) + answer[last:]


# a "-nya" that owns nothing: an adverb or a "the" ("sesungguhnya", "biasanya", "selanjutnya")
_NOT_POSSESSIVE_NYA = re.compile(r"(?:selanjut|akhir|biasa|umum|sebenar|sesungguh|misal|terutama|sebalik|selain|tentu|"
                                 r"khusus|utama|bahkan|kira|rupa|seharus|semesti|agak|lebih)nya$", re.I)


def _own_nya(rest: Text, frame: Text, before: Text = "") -> Text:
    """The first "<noun>-nya" of a clause lifted out of its frame gets the owner the frame named: "atmanya benar-benar
    bebas" under "... untuk mendiang ..." -> "atma mendiang benar-benar bebas". Unchanged when no person is named."""
    # (the frame's own person, else "mendiang" when the answer says it: the last person before was the other term's --
    # "Nyekah bertujuan agar atma bayi ..." took Ngelungah's bayi)
    person = r"\b(mendiang|almarhum(?:ah)?|jenazah|orang\s+yang\s+meninggal|bayi|anak)\b"
    owners = re.findall(person, frame, re.I) or re.findall(r"\b(mendiang)\b", before, re.I)
    m = next((x for x in re.finditer(r"\b([a-z]{3,})nya\b", rest) if not _NOT_POSSESSIVE_NYA.match(x.group(0))), None)
    if not owners or not m:
        return rest
    return f"{rest[:m.start()]}{m.group(1)} {owners[-1].lower()}{rest[m.end():]}"


def _two_sided_opening(answer: Text, enriched: List[Dict[str, Any]]) -> bool:
    """The answer opens by saying what each of the two is, side by side -- "A adalah ..., sedangkan B adalah ..." or
    "A adalah .... Sebaliknya, B adalah ...", after a "sama-sama" sentence or not: what the model says after it about
    either goes when it re-says it (strict, as under the bot's own lead)."""
    names_of = [[re.escape(n) for n in [e.get("name") or ""] + list(e.get("aliases") or [])
                 + [e.get("asked_as") or "", e.get("typed_as") or ""] if n] for e in enriched[:2]]
    if len(names_of) < 2 or not all(names_of):
        return False
    res = [re.compile(rf"(?<![\w-])(?:{'|'.join(sorted(set(ns), key=len, reverse=True))})(?![\w-])", re.I)
           for ns in names_of]
    sents = _sentences(answer.split("\n\n")[0])
    if sents and re.search(r"\bsama-sama\b", sents[0], re.I):
        sents = sents[1:]
    for opening in (sents[:1], sents[:2]):
        text = " ".join(opening)
        if all(r.search(text) for r in res) and re.search(r"\b(?:sedangkan|sementara|sebaliknya)\b", text, re.I):
            return True
    return False


def _complete_contrast(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text = "") -> Text:
    """A comparison answer that never says how the two differ opens with what each is: "apa perbedaan pancamaha butha
    dan moksa" got the two definitions one after the other, "apa perbedaan sekah dan adegan" "Perbedaan utama ...
    terletak pada wujud fisik, bahan pembuat, fungsi ..." and then two descriptions (conersation.md section V; style
    test 2026-11-06: "The difference between X and Y is that Y is a philosophy and X is a ceremony"). Each side's card's
    first sentence, joined by "sedangkan"; what the model then says again goes (_drop_repeated_sentences)."""
    if len(enriched) != 2:
        return answer
    # (a heading that only announces a difference says none: it neither counts as the model's contrast below nor stays)
    answer = _drop_announcing_sentences(answer, enriched)
    same = [sorted(_surfaces_by_id().get(e["id"], ())) + [e.get("name") or "", e.get("asked_as") or "",
                                                          e.get("typed_as") or ""] for e in enriched]
    hollow = _HOLLOW_CONTRAST_RE.match(answer)
    after = answer[hollow.end():] if hollow else answer
    # (the model's first two sentences: not a "sama-sama" one before them, which says what they share, no difference --
    # "Ngaben massal dan Ngaben Svasta sama-sama termasuk jenis Ngaben." then "Ngaben Massal adalah ... Sebaliknya, ...")
    opening = _sentences(after)
    if opening and re.search(r"\bsama-sama\b", opening[0], re.I) and not _CONTRAST_RE.search(opening[0]):
        opening = opening[1:]
    opening = opening[:2]
    kind_lead = _kind_contrast_lead(enriched, user_msg)
    if kind_lead:
        names = [re.escape(n) for e in enriched for n in [e["name"]] + list(e.get("aliases") or [])
                 + [e.get("asked_as") or "", e.get("typed_as") or ""] if n]
        names_re = re.compile(rf"(?<![\w-])(?:{'|'.join(sorted(set(names), key=len, reverse=True))})(?![\w-])", re.I)
        # an opening that already says which is a kind of which and how they differ stays as it is: "Perbedaan utama
        # antara Ngaben dan Pitra Yadnya terletak pada cakupannya: Ngaben adalah salah satu jenis ... Pitra Yadnya".
        # The kind word must lead to a name of the two: "..., sedangkan ngaben biasa ... merupakan bagian dari pitra
        # yadnya" says no kind link and kept the lead out (2026-11-12, once the announcing sentence before it went)
        kind_link = re.compile(rf"\b(?:jenis|bagian|termasuk)\b[^.!?\n]{{0,40}}?{names_re.pattern}", re.I)
        if any(len(names_re.findall(s)) >= 2 and kind_link.search(s)
               and _CONTRAST_RE.search(s) for s in opening):
            res = after[:1].upper() + after[1:] if hollow else answer
            return _finish_contrast(res, enriched, user_msg)
        # the model's own "Ngaben massal merupakan salah satu jenis dari Ngaben." says only what the lead says (too
        # short for _drop_repeated_sentences to count it a repeat)
        only_kind = re.compile(r"\s*(?:merupakan|adalah|termasuk|(?:salah\s+)?satu|jenis|dari|dalam|bagian|·|,)\s*", re.I)
        for p in _SENT_PART_RE.findall(after):
            rest = names_re.sub(" · ", p.strip().rstrip(".!"))
            if re.search(r"\bjenis\b", p, re.I) and rest.count("·") >= 2 and not only_kind.sub("", rest).strip():
                after = after.replace(p, "", 1)
        # (and the model's miss: the lead answers from the two cards)
        after = re.sub(r"(?:\A|(?<=[.!?\n]))\s*Maaf,[^.!?\n]*\b(?:belum|tidak)\s+(?:tercatat|tersedia)[^.!?\n]*[.!?](?:\s*Yang\s+(?:tercatat|tersedia)\s+(?:tentang|mengenai)\s+[^:\n]+:\s*)?", "\n\n",
                       after)
        after = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", after)).strip()
        res = _drop_repeated_sentences(f"{kind_lead}\n\n{after}", loose=False, same_names=same)
        return _finish_contrast(res, enriched, user_msg)
    if _CONTRAST_RE.search(" ".join(opening)):
        # the model says the difference: a hollow lead-in before it goes, nothing is added
        after = re.sub(r"(?:\A|(?<=[.!?\n]))\s*Maaf,[^.!?\n]*\b(?:belum|tidak)\s+(?:tercatat|tersedia)[^.!?\n]*[.!?](?:\s*Yang\s+(?:tercatat|tersedia)\s+(?:tentang|mengenai)\s+[^:\n]+:\s*)?", "\n\n",
                       after)
        after = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", after)).strip()
        res = after[:1].upper() + after[1:] if hollow else (after or answer)
        if _two_sided_opening(res, enriched):
            # the model's own "A adalah ..., sedangkan B adalah ..." is a lead like the bot's: what it re-says of
            # either below goes (2026-11-12: "Sebaliknya, Atma Wedana dilakukan secara spesifik untuk menyucikan suksma
            # sarira tersebut." under "... sedangkan Atma Wedana adalah ... untuk menyucikan suksma sarira")
            res = _drop_repeated_sentences(res, loose=False, strict=True, same_names=same)
        return _finish_contrast(res, enriched, user_msg)
    sides = []
    glosses = [_telling_gloss(enriched[0], enriched[1]), _telling_gloss(enriched[1], enriched[0])]
    # (a class both glosses open with tells nothing apart: "salah satu dari Panca Yadnya, yaitu ..." on both sides of
    # manusa / dewa yadnya)
    shared = [re.match(r"salah\s+satu\s+(?:dari\s+|jenis\s+)?[^,;:]+?,\s+(?:yaitu|yakni)\s+", g, re.I) for g in glosses]
    if all(shared) and shared[0].group(0).lower() == shared[1].group(0).lower():
        glosses = [g[m.end():] for g, m in zip(glosses, shared)]
    for e, g in zip(enriched, glosses):
        # (what tells the two apart, _telling_gloss: the whole first sentence made a heavy opening, colons, semicolons
        # and lists included -- plan #31. What the model then re-says goes as a repeat, strict.)
        if not g:
            return answer
        name = _card_cased(e["id"], e.get("asked_as") or e.get("typed_as"))
        sides.append(f"{name[:1].upper()}{name[1:]} adalah {g}" if not re.match(r"(?:berarti|merupakan|adalah)\b", g)
                     else f"{name[:1].upper()}{name[1:]} {g}")
    lead = f"{sides[0]}, sedangkan {sides[1]}."
    # (the model's miss goes: the lead answers from the two cards)
    rest = re.sub(r"(?:\A|(?<=[.!?\n]))\s*Maaf,[^.!?\n]*\b(?:belum|tidak)\s+(?:tercatat|tersedia)[^.!?\n]*[.!?](?:\s*Yang\s+(?:tercatat|tersedia)\s+(?:tentang|mengenai)\s+[^:\n]+:\s*)?", "\n\n",
                  after)
    rest = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", rest)).strip()
    # after the shared class _complete_chain_link puts first ("X dan Y sama-sama termasuk ..."), not before it
    shared = re.match(r"\s*[^.!?\n]*\bsama-sama\b[^.!?\n]*[.!?]\s*", rest)
    head, rest = (shared.group(0).strip() + " ", rest[shared.end():]) if shared else ("", rest)
    res = _drop_repeated_sentences(f"{head}{lead}\n\n{rest.lstrip()}", loose=False, strict=True, same_names=same)
    return _finish_contrast(res, enriched, user_msg)


def _finish_contrast(res: Text, enriched: List[Dict[str, Any]], user_msg: Text) -> Text:
    """What every comparison answer gets last: a frame re-saying the opening goes straight to its new fact, a heading
    left with nothing under it goes (its sentence cut as a repeat above), and so do the side details. Plan #31
    (2026-11-13): a heading before content goes, a clause re-saying the opening beside a new fact goes, one term's
    kinds or examples nobody asked go, two halves about different things become two sentences, and a "Sebaliknya" /
    "Sementara itu" stays only where the answer turns from one term to the other."""
    res = _drop_announcing_sentences(_trim_restated_frames(res, enriched), enriched)
    res = _drop_heading_leads(res, enriched)
    res = _drop_repeated_clauses(res, enriched)
    res = _drop_unasked_kinds(res, enriched, user_msg)
    res = _split_mismatched_contrasts(res, enriched)
    res = _drop_extra_connectives(res, enriched)
    res = _short_name_brackets(res)
    return _drop_irrelevant_comparison_sentences(res, enriched, user_msg)


def _names_rx(e: Dict[str, Any]) -> Optional["re.Pattern"]:
    """Every name a compared card goes by in an answer -- its surfaces, aliases, the asked and the typed name -- as
    one pattern (whole words)."""
    names = {n for n in list(_surfaces_by_id().get(e["id"], ())) + list(e.get("aliases") or [])
             + [e.get("name") or "", e.get("asked_as") or "", e.get("typed_as") or ""] if n and len(n) >= 3}
    if not names:
        return None
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
                      + r")(?![\w-])", re.I)


def _edit_sentences(answer: Text, fn) -> Text:
    """Each sentence of the answer's paragraphs through fn(sentence, text_before) -> its new text ("" drops it). List
    items and the paragraph breaks stay as they are."""
    out: List[str] = []
    changed = False
    for para in re.split(r"(\n+)", answer):
        if para.startswith("\n") or not para.strip() or _LIST_ITEM_RE.match(para):
            out.append(para)
            continue
        kept: List[str] = []
        for m in _SENT_PART_RE.finditer(para):
            s = m.group(0).strip()
            if not s:
                continue
            new = fn(s, "".join(out) + " " + " ".join(kept))
            changed = changed or (new or "").strip() != s
            if new and new.strip():
                kept.append(new.strip())
        out.append(" ".join(kept))
    if not changed:
        return answer
    res = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n\n", "".join(out)).strip()
    return res[:1].upper() + res[1:] if res else answer


def _cap(s: Text) -> Text:
    return s[:1].upper() + s[1:]


# "Dari segi tata upacara, Sawa Wedana ..." -- an aspect named as a heading in front of its own content (2026-11-12)
_ASPECT_HEAD_RE = re.compile(r"(?:Secara\s+(?:lebih\s+)?(?:rinci|detail),\s*(?=\w)|(?:Dari\s+(?:segi|sisi|aspek|sudut\s+pandang)|(?:Dilihat|Ditinjau)\s+dari(?:\s+(?:segi|sisi))?"
                             r"|Dalam\s+hal)\s+[^,.:;!?\n]{1,60}?,\s*(?=\w))", re.I)


def _drop_heading_leads(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """A comparison keeps the content and loses the heading in front of it: "Perbedaan utama terletak pada posisi dan
    identitasnya: Siwa dipandang ..." -> "Siwa dipandang ...", "Dari segi tata upacara, Sawa Wedana merupakan ..." ->
    "Sawa Wedana merupakan ..." (plan #31; _drop_announcing_sentences takes a heading with nothing after it)."""
    rxs = [r for r in (_names_rx(e) for e in enriched[:2]) if r]
    if not rxs:
        return answer
    names_re = re.compile("|".join(f"(?:{r.pattern})" for r in rxs), re.I)

    def fn(s: Text, before: Text) -> Text:
        m = _ASPECT_HEAD_RE.match(s)
        if m:
            s = _cap(s[m.end():])
        # (a colon or a semicolon after the heading: "Lokasi penempatannya juga berbeda; sekah diletakkan ...")
        colon = re.match(r"([^:;.!?\n]*\b(?:perbedaan\w*|berbeda|beda(?:nya)?)\b[^:;.!?\n]*)[:;]\s*(?=\w)", s, re.I)
        if colon and _announces_only(colon.group(1), names_re):
            s = _cap(s[colon.end():])
        return s
    return _edit_sentences(answer, fn)


def _clause_roots(text: Text, rxs: List["re.Pattern"]) -> set:
    """A clause's word roots, each compared card's names counted as one word."""
    for k, rx in enumerate(rxs):
        text = rx.sub(f" qqname{chr(ord('x') + k) * 2} ", text)
    return _sentence_roots(text)


_NEG_RE = re.compile(r"\b(?:tidak|tak|bukan|belum|tanpa)\b", re.I)


def _said_in(clause: Text, before: Text, rxs: List["re.Pattern"], need: float = 0.85) -> bool:
    """`clause` re-says one sentence of `before`: most of its words (two at least) are that sentence's, with no "not"
    that one lacks, no number nothing before says and no KB term nothing before names (plan #30's guards). A card's
    "(disebut juga ...)" names are no fact of the clause: they are said apart (_short_name_brackets)."""
    clause = _NAMES_BRACKET_RE.sub("", clause)
    roots = _clause_roots(clause, rxs)
    if len(roots) < 2:
        return False
    sents = [s for s in _SENT_PART_RE.findall(before) if s.strip()]
    if not sents:
        return False
    best = max(sents, key=lambda t: len(roots & _clause_roots(t, rxs)))
    if len(roots & _clause_roots(best, rxs)) < need * len(roots):
        return False
    if {w.lower() for w in _NEG_RE.findall(clause)} - {w.lower() for w in _NEG_RE.findall(best)}:
        return False
    if _numbers_in(clause) - _numbers_in(before):
        return False
    return not _new_kb_words(clause, before)


_JOINT_RE = re.compile(r",\s*(?:sedangkan|sementara(?:\s+itu)?)\s+", re.I)
# nouns that open like a me- verb
_ME_NOUNS = frozenset("mendiang menara meja merah mereka media menit mesin meru melati mega menantu mempelai".split())
# words after which what follows is their complement, never a trailing phrase to cut
_CLAUSE_LINK_WORD_RE = re.compile(r"dan|serta|atau|ialah|yakni|tanpa|sambil|agar|supaya|bisa|harus|mampu|boleh|perlu|wajib|ingin|hanya|"
                                  r"cara|bila|jika|kalau|ketika|saat|guna|demi|lalu|kemudian|belum|tak|bukan|tugasnya|"
                                  r"fungsinya|tujuannya|perannya", re.I)
_LEAD_CONN = r"(?:(?:Selain\s+itu|Sementara\s+itu|Sebaliknya|Adapun|Di\s+sisi\s+lain|Namun|Pada\s+akhirnya),\s*)?"
_VERB_START = r"(?:ber|di|me|ter|per)\w+\b"


def _drop_repeated_clauses(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """In a comparison, the part of a sentence that re-says the opening goes and its new fact stays (user, 2026-11-12;
    plan #31): "Ngangsen diadakan bila dalam 42 hari ..., dan bertujuan untuk ..." under an opening giving the 42 days
    -> "Ngangsen bertujuan untuk ..."; "Sawa Wedana dilaksanakan 3-7 hari setelah meninggal menggunakan jenazah utuh"
    under "... jenis Ngaben yang menggunakan jenazah utuh" -> "... setelah meninggal"; "Bade dihias dengan boma, kapas,
    dan mangle, sedangkan wadah juga dihias dengan boma, kapas, dan mangle, namun ..." -> "Bade dan wadah sama-sama
    dihias dengan ..., namun wadah dihias dengan ...". Never the first sentence; plan #30's guards hold (_said_in)."""
    if len(enriched) != 2:
        return answer
    rxs = [r for r in (_names_rx(e) for e in enriched) if r]
    if len(rxs) != 2:
        return answer
    names_alt = "|".join(f"(?:{r.pattern})" for r in rxs)

    def which(text: Text) -> Optional[int]:
        m = re.match(rf"\s*{_LEAD_CONN}(?:upacara\s+)?({names_alt})", text, re.I)
        if not m:
            return None
        return next((k for k, r in enumerate(rxs) if r.fullmatch(m.group(1))), None)

    def fn(s: Text, before: Text) -> Text:
        if not before.strip():
            return s
        # (a) "T <said>, dan <verb> <new>" -> "T <verb> <new>"
        m = re.match(rf"(?P<lead>\s*{_LEAD_CONN})(?P<t>{names_alt})\s+(?P<p1>[^.!?]+?),\s+(?:dan|serta)\s+"
                     rf"(?P<p2>{_VERB_START}[^.!?]*[.!?]?)$", s, re.I)
        if m and re.match(_VERB_START, m.group("p1"), re.I) and _said_in(m.group("p1"), before, rxs):
            return f"{m.group('lead')}{m.group('t')} {m.group('p2')}"
        # (f) "T <said>, di mana <new clause>" -> "<New clause>": "Pitra Yadnya dilandasi hati yang tulus suci kepada
        # leluhur, ..., di mana kata "pitra" berarti ..." under a lead saying the first half
        m = re.match(rf"\s*{_LEAD_CONN}(?P<t>{names_alt})\s+(?P<p1>[^.!?]+?),\s+di\s?mana\s+(?P<p2>[^.!?]+[.!?]?)$", s, re.I)
        if m and _said_in(m.group("p1"), before, rxs) and len(_sentence_roots(m.group("p2"))) >= 3:
            return _cap(m.group("p2"))
        # (d) a ";"-clause that a sentence before says goes, the others stay: "Ngroras bertujuan agar atma mendiang
        # benar-benar bebas; setelah Patileman selesai, pitra meningkat ..." under a lead ending "agar atmanya
        # benar-benar bebas"
        clauses = _top_level_parts(s, ";")
        if len(clauses) >= 2:
            kept = [c for c in clauses if not _said_in(c, before, rxs)]
            if kept and len(kept) < len(clauses):
                out = "; ".join(kept)
                return _cap(out) if out[-1:] in ".!?" else _cap(out) + "."
        # (e) "T adalah <a counted set said before>, yaitu <list>" -> "T terdiri dari <list>": "Panca Maha Bhuta adalah
        # lima unsur alam pembentuk tubuh ..., yaitu pertiwi (...), apah (...), ..." under a lead saying the five elements
        m = re.match(rf"(?P<lead>\s*{_LEAD_CONN})(?P<t>{names_alt})\s+(?:adalah|merupakan)\s+(?P<p>[^,;:]+?),\s+(?:yaitu|yakni)\s+"
                     rf"(?P<l>[^.!?]+,[^.!?]+[.!?]?)$", s, re.I)
        if (m and re.search(r"\b(?:dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh)\b", m.group("p"), re.I)
                and _said_in(m.group("p"), before, rxs, need=1.0)):
            return f"{m.group('lead')}{m.group('t')} terdiri dari {m.group('l')}"
        halves = _JOINT_RE.split(s)
        joints = _JOINT_RE.findall(s)
        # (c) "A <P>, sedangkan B (juga) <P>[, namun <R>]" -> "A dan B sama-sama <P>[, namun B <verb> <R>]"
        if len(halves) == 2 and which(halves[0]) is not None and which(halves[1]) is not None \
                and which(halves[0]) != which(halves[1]):
            ha = re.match(rf"(?P<lead>\s*{_LEAD_CONN})(?P<a>{names_alt})\s+(?P<p>{_VERB_START}[^.!?]*?)\s*$", halves[0], re.I)
            hb = re.match(rf"(?P<b>{names_alt})\s+(?:juga\s+)?(?P<p>{_VERB_START}[^.!?]*?)"
                          rf"(?:,\s*(?P<but>namun|tetapi|hanya\s+saja)\s+(?P<r>[^.!?]+?))?\s*(?P<end>[.!?]?)$",
                          halves[1], re.I)
            if ha and hb:
                pa, pb = _clause_roots(ha.group("p"), rxs), _clause_roots(hb.group("p"), rxs)
                if len(pa) >= 2 and pa == pb and not _NEG_RE.search(ha.group("p") + hb.group("p")):
                    out = f"{ha.group('lead')}{ha.group('a')} dan {hb.group('b')} sama-sama {ha.group('p')}"
                    if hb.group("r"):
                        r = hb.group("r")
                        verb = ha.group("p").split()[0]
                        r = f"{hb.group('b')} {verb} {r}" if re.match(r"(?:dengan|tanpa|oleh|di|ke|dari)\b", r, re.I) \
                            else f"pada {hb.group('b')}, {r}"
                        out += f", {hb.group('but')} {r}"
                    return out + (hb.group("end") or ".")
        # (b) a closing "me-<verb> ..." of either half that a sentence before says of the same term goes:
        # "Sawa Wedana dilaksanakan 3-7 hari setelah meninggal menggunakan jenazah utuh, sementara ..."
        new_halves = []
        for h in halves:
            end = re.search(r"[.!?]+$", h)
            body = h[:end.start()] if end else h
            k = which(h)
            own = [t for t in _SENT_PART_RE.findall(before) if rxs[k].search(t)] if k is not None else []
            # (each "me-" word may start the tail, the longest said one wins: "meninggal menggunakan jenazah utuh" is
            # not said, "menggunakan jenazah utuh" is)
            for m in re.finditer(r"\s(?=(?P<tail>(?P<verb>me\w{3,})\s[^,;:()]+)$)", body):
                # (a noun that only looks like a me- verb is no tail: "representasi lahirnya mendiang dalam wujud
                # simbolis" lost "mendiang ...")
                if (m.group("verb").lower() in _ME_NOUNS
                        or _ortho_token(m.group("verb")) in get_resolver().name_tokens):
                    continue
                head = body[:m.start()]
                prev_word = (head.split() or [""])[-1].lower()
                # (never after a function word: "... karena tugasnya adalah menyucikan suksma sarira tersebut" lost its
                # complement and read "karena tugasnya adalah.")
                if (own and prev_word not in _STOPWORDS_ID and not _CLAUSE_LINK_WORD_RE.fullmatch(prev_word)
                        and len(_clause_roots(head, rxs)) >= 3
                        and _said_in(m.group("tail"), " ".join(own), rxs, need=1.0)):
                    h = head.rstrip(" ,") + (end.group(0) if end else "")
                    break
            new_halves.append(h)
        if new_halves != halves:
            return "".join(x for pair in zip(new_halves, joints + [""]) for x in pair)
        return s
    return _edit_sentences(answer, fn)


# one term's kinds or examples, listed: "dengan jenis-jenis seperti Mamukur, ...", "Contoh upacara Dewa Yadnya meliputi
# ...", "Sekah juga memiliki variasi jenis seperti ..."
_KINDS_LIST = (r"(?:jenis-jenis(?:nya)?|jenisnya|beberapa\s+jenis|berbagai\s+jenis|variasi\s+jenis|bagian-bagian\s+lain(?:nya)?(?:\s+dari\s+[\w\s]{1,30}?)?|"
               r"contoh(?:-contoh)?(?:nya)?"
               r"(?:\s+upacara(?:nya)?)?)\s+(?:[\w\s]{0,40}?\s+)?(?:seperti|antara\s+lain|yaitu|yakni|meliputi|"
               r"adalah|di\s?antaranya|misalnya|:)")
_KINDS_CLAUSE_RE = re.compile(rf",\s*(?:(?:dengan|termasuk)\s+{_KINDS_LIST}|contohnya\s+(?:adalah\s+)?|dengan\s+contoh\s+)"
                              r"[^.!?]*", re.I)
_KINDS_SENT_RE = re.compile(rf"^\s*{_LEAD_CONN}(?:Selain\s+[^,.!?]{{1,30}},\s*)?(?:{_KINDS_LIST}|(?:Jenis-jenis|Contoh(?:-contoh)?)\b[^.!?]{{0,60}}?"
                            r"\b(?:meliputi|antara\s+lain|adalah|yaitu|seperti|:)"
                            r"|[^.!?]{0,40}?\b(?:juga\s+)?(?:memiliki|mempunyai)\s+(?:beberapa\s+|berbagai\s+)?(?:variasi\s+)?"
                            r"(?:jenis|variasi|contoh)\b)", re.I)


def _drop_unasked_kinds(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text) -> Text:
    """A comparison leaves out one term's kinds or examples nobody asked (rule 17 asks it; Qwen lists them anyway): "...,
    dengan jenis-jenis seperti Mamukur, Sekah Kurung, dan Ngangsen, ..." in "apa perbedaan ngaben dan ngerorasin"; potong
    gigi, ngusaba and odalan in "apa perbedaan manusa yadnya dengan dewa yadnya" (plan #31) -- and the sentences that
    then describe those examples. Not when the question asks for kinds or examples, when the list names a compared
    term ("Mamukur dan Ngangsen" are kinds of one rite), or when the answer says the other term is a kind of something:
    then the kinds are the difference ("Ngelungah merupakan salah satu jenis ngaben", Nyekah's kinds set against it)."""
    # (nor when it also asks what each is: "apa itu ngaben, apa itu ngroras, apa bedanya" -- the kinds are part of that)
    if len(enriched) != 2 or _KINDS_Q_RE.search(user_msg) or _WHAT_IS_SHAPE_RE.search(user_msg):
        return answer
    rxs = [r for r in (_names_rx(e) for e in enriched) if r]
    if len(rxs) != 2:
        return answer
    kind_claim = [bool(re.search(rf"(?:{rx.pattern})[^.!?]{{0,40}}\b(?:salah\s+satu\s+jenis|termasuk\s+jenis|"
                                 rf"merupakan\s+jenis|adalah\s+jenis)\b", answer, re.I)) for rx in rxs]
    resolver = get_resolver()
    compared = {e["id"] for e in enriched}
    dropped_items: List[str] = []
    state = {"cut": False}

    def items_of(text: Text) -> List[tuple]:
        """The KB terms a list names, as (surface, id): the longest run of each item's words that is a name."""
        text = re.sub(rf"^\s*,?\s*(?:(?:dengan|termasuk)\s+)?(?:{_KINDS_LIST}|contohnya\s+(?:adalah\s+)?|contoh\s+)", "",
                      text, flags=re.I)
        out = []
        for raw in re.split(r",|\s+dan\s+|\s+atau\s+|\s+serta\s+", re.sub(r"\([^)]*\)", " ", text)):
            words = _WORD_RE.findall(raw)[:6]
            found = next(((" ".join(words[i:i + n]), hit.id) for n in range(min(4, len(words)), 0, -1)
                          for i in range(len(words) - n + 1)
                          for hit in [resolver.resolve(" ".join(words[i:i + n]))]
                          if hit and hit.via in _NAMED_VIA and not _is_everyday_word(" ".join(words[i:i + n]).lower(),
                                                                                     resolver)), None)
            if found:
                out.append(found)
        return out

    def keeps(text: Text, owner: Optional[int]) -> bool:
        # a list naming a compared term as one of its items (not inside a longer name: sekah's kinds "sekah abin, sekah
        # kangsen" name no sekah), or set against the other term's being a kind
        return any(i in compared for _, i in items_of(text)) or (owner is not None and kind_claim[1 - owner])

    def drop_items(text: Text) -> None:
        dropped_items.extend(s for s, _ in items_of(text))

    def owner_of(s: Text) -> Optional[int]:
        hits = [(m.start(), k) for k, rx in enumerate(rxs) for m in [rx.search(s)] if m]
        return min(hits)[1] if hits else None

    def fn(s: Text, before: Text) -> Text:
        was_cut, state["cut"] = state["cut"], False
        # a sentence describing an example just dropped ("Ngenteg linggih adalah upacara ..."), or leaning on it with
        # no compared term named ("Jika orang dewasa meninggal sebelum melaluinya, ...")
        if dropped_items and (
                any(re.match(rf"\s*{_LEAD_CONN}(?:upacara\s+)?{re.escape(x)}\b", s, re.I) for x in dropped_items)
                or was_cut and owner_of(s) is None and re.search(r"\b\w+nya\b|\b(?:ini|tersebut)\b", s, re.I)):
            state["cut"] = True
            return ""
        # (one half of "A ..., sementara B ..." first: "Sekah juga memiliki variasi jenis seperti ..., sementara adegan
        # memiliki komponen khusus ..." keeps adegan's half)
        halves = _JOINT_RE.split(s)
        if len(halves) == 2:
            for i, h in enumerate(halves):
                hm = _KINDS_SENT_RE.match(h)
                if hm and not keeps(h[hm.end():], owner_of(h)):
                    drop_items(h[hm.end():])
                    other = halves[1 - i].strip()
                    other = re.sub(r"[.!?]*$", "", other) + "."
                    return _cap(other)
        whole = _KINDS_SENT_RE.match(s)
        if whole and len(halves) == 1:
            rest = s[whole.end():]
            k = owner_of(s)
            if not keeps(rest, k):
                drop_items(rest)
                # (a fact joined to the list stays: "Ngaben memiliki berbagai jenis seperti ..., serta dipimpin oleh
                # sulinggih." -> "Ngaben dipimpin oleh sulinggih.")
                subj = re.match(rf"\s*{_LEAD_CONN}(?P<s>[^.!?]{{1,40}}?)\s+(?:juga\s+)?(?:memiliki|mempunyai)\b", s, re.I)
                tail = re.search(rf",\s+(?:serta|dan)\s+(?P<v>{_VERB_START}[^.!?]*)[.!?]?$", rest, re.I)
                if subj and tail and k is not None and rxs[k].fullmatch(subj.group("s").strip()):
                    return f"{_cap(subj.group('s').strip())} {tail.group('v').strip()}."
                state["cut"] = True
                return ""
        m = _KINDS_CLAUSE_RE.search(s)
        if m and not keeps(m.group(0), owner_of(s)) and len(_sentence_roots(s[:m.start()])) >= 2:
            drop_items(m.group(0))
            return s[:m.start()].rstrip(" ,") + "."
        return s
    return _edit_sentences(answer, fn)


# what each half of an "A ..., sedangkan B ..." speaks of: two halves sharing none of these and no word but the names
# are set against each other only by the joint ("Sawa Wedana bertujuan menyucikan badan halus mendiang, sedangkan Asti
# Wedana menjadi acuan bagi Ngaben Svasta", 2026-11-12)
_HALF_ASPECTS = {
    "apa": re.compile(r"^\s*(?:adalah|merupakan|ialah|yaitu|termasuk)\b", re.I),
    "waktu": re.compile(r"\b(?:setelah|sesudah|sebelum|hari|bulan|tahun|saat|ketika|waktu|selama|menjelang)\b", re.I),
    "tujuan": re.compile(r"\b(?:bertujuan|tujuan\w*|agar|supaya|berfungsi|fungsi\w*|guna|makna\w*|melambangkan)\b", re.I),
    "tempat": re.compile(r"\b(?:tempat|diletakkan|ditempatkan|berstana|digelar|diselenggarakan\s+di|dilaksanakan\s+di|"
                         r"dilakukan\s+di|arah)\b", re.I),
    "pelaku": re.compile(r"\b(?:oleh|dipakai|dipimpin|pemimpin|dibuat|bagi|untuk\s+(?:golongan|orang|jenazah|bayi|anak))\b",
                         re.I),
    "bahan": re.compile(r"\b(?:terbuat|bahan|terdiri|berisi|dihias|menggunakan|digunakan|memakai|sarana)\b", re.I),
    "acuan": re.compile(r"\b(?:acuan|sama\s+dengan|seperti|mengikuti)\b", re.I),
    "status": re.compile(r"\b(?:kedudukan\w*|berstatus|status|meningkat)\b", re.I),
    "cara": re.compile(r"\b(?:dibakar|dikubur|dihanyutkan|diarak|cara|tata|tahap\w*|dimulai|diakhiri)\b", re.I),
}


def _split_mismatched_contrasts(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """Two halves of "A ..., sedangkan B ..." about different things become two sentences: no word but the names
    shared, and no aspect (_HALF_ASPECTS) both speak of (plan #31)."""
    if len(enriched) != 2:
        return answer
    rxs = [r for r in (_names_rx(e) for e in enriched) if r]
    if len(rxs) != 2:
        return answer
    names_alt = "|".join(f"(?:{r.pattern})" for r in rxs)

    def aspects(half: Text) -> set:
        m = re.match(rf"\s*{_LEAD_CONN}(?:upacara\s+)?(?:{names_alt})", half, re.I)
        after = half[m.end():] if m else half
        return {k for k, rx in _HALF_ASPECTS.items() if rx.search(after if k == "apa" else half)}

    def fn(s: Text, before: Text) -> Text:
        halves, joints = _JOINT_RE.split(s), _JOINT_RE.findall(s)
        if len(halves) != 2:
            return s
        a, b = halves
        if not (re.match(rf"\s*{_LEAD_CONN}(?:upacara\s+)?(?:{names_alt})\s", a, re.I)
                and re.match(rf"(?:upacara\s+)?(?:{names_alt})\s", b, re.I)):
            return s
        if _clause_roots(a, rxs) & _clause_roots(b, rxs) - {"qqnamexx", "qqnameyy"}:
            return s
        if aspects(a) & aspects(b) or not aspects(a) or not aspects(b):
            return s
        return f"{a.rstrip(' ,')}. {_cap(b)}"
    return _edit_sentences(answer, fn)


_TURN_CONN_RE = re.compile(r"(?:Sebaliknya|Sementara\s+itu|Di\s+sisi\s+lain),\s*", re.I)


def _drop_extra_connectives(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """"Sebaliknya," / "Sementara itu," / "Di sisi lain," stays only where the sentence turns from one compared term to
    the other and the sentence before it does not already set them against each other (plan #31: most second sentences
    opened with one)."""
    if len(enriched) != 2:
        return answer
    rxs = [r for r in (_names_rx(e) for e in enriched) if r]
    if len(rxs) != 2:
        return answer

    def about(s: Text) -> Optional[int]:
        hits = [(m.start(), k) for k, rx in enumerate(rxs) for m in [rx.search(s)] if m]
        return min(hits)[1] if hits else None

    def fn(s: Text, before: Text) -> Text:
        m = _TURN_CONN_RE.match(s)
        if not m:
            return s
        prev = next((t for t in reversed(_SENT_PART_RE.findall(before)) if t.strip()), "")
        now, then = about(s[m.end():]), about(prev)
        if now is None or then is None:
            return s
        both = all(rx.search(prev) for rx in rxs) and re.search(r"\b(?:sedangkan|sementara|sebaliknya|berbeda)\b",
                                                                 prev, re.I)
        if now != then and not both:
            return s
        return _cap(s[m.end():])
    return _edit_sentences(answer, fn)


def _complete_similarity(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text = "") -> Text:
    """A comparison answer asking for similarities (persamaan/kesamaan) between two terms.
    If the answer already states a similarity (e.g. using 'sama-sama', 'keduanya', 'kesamaan'),
    any trailing refusal/miss sentence is stripped. If no similarity was stated or the model
    refused, formulates the similarity from shared categories in the KB or definitions."""
    if len(enriched) != 2:
        return answer
    hollow = _HOLLOW_CONTRAST_RE.match(answer) if _HOLLOW_CONTRAST_RE else None
    after = answer[hollow.end():] if hollow else answer
    after = re.sub(r"(?:\A|(?<=[.!?\n]))\s*Maaf,[^.!?\n]*\b(?:belum|tidak)\s+(?:tercatat|tersedia)[^.!?\n]*[.!?](?:\s*Yang\s+(?:tercatat|tersedia)\s+(?:tentang|mengenai)\s+[^:\n]+:\s*)?", "\n\n",
                   after)
    after = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", after)).strip()
    opening = _sentences(after)[:2]
    if any(re.search(r"\b(?:sama-sama|keduanya|persamaan(?:nya)?|kesamaan(?:nya)?|memiliki kesamaan|serupa)\b", s, re.I)
           for s in opening):
        res = after[:1].upper() + after[1:]
        return _drop_irrelevant_comparison_sentences(res, enriched, user_msg)

    a, b = enriched[0], enriched[1]
    content = get_content()
    name_a = _card_cased(a["id"], a.get("asked_as") or a.get("typed_as"))
    name_b = _card_cased(b["id"], b.get("asked_as") or b.get("typed_as"))
    name_a_cap = f"{name_a[:1].upper()}{name_a[1:]}"
    name_b_cap = f"{name_b[:1].upper()}{name_b[1:]}"

    pa = set(content.kind_parents.get(a["id"]) or [])
    pb = set(content.kind_parents.get(b["id"]) or [])
    shared = pa & pb
    if shared:
        parent_id = next(iter(shared))
        parent_name = _card_cased(parent_id)
        if _NUMERAL_SET_RE.match(content.entity_name.get(parent_id, parent_id)):
            lead = f"{name_a_cap} dan {name_b_cap} sama-sama termasuk {parent_name}."
        else:
            lead = f"{name_a_cap} dan {name_b_cap} sama-sama termasuk jenis {parent_name}."
    else:
        try:
            rows = neo4j_conn.query(_CHAIN_QUERY, {"a": a["id"], "b": b["id"]})
        except Exception:
            rows = []
        if rows and rows[0].get("shared") and rows[0]["shared"][0]:
            mid, rel = rows[0]["shared"]
            mid_name = _card_cased(mid)
            lead = (f"{name_a_cap} dan {name_b_cap} sama-sama termasuk {mid_name}." if rel == "TERMASUK_JENIS"
                    else f"{name_a_cap} dan {name_b_cap} sama-sama tahapan {mid_name}." if content.entity_type.get(a["id"]) in _STAGE_TYPES
                    else f"{name_a_cap} dan {name_b_cap} sama-sama bagian dari {mid_name}.")
        else:
            # what both are, in words a reader knows; no shared class, no claim ("keduanya memiliki keterkaitan dalam
            # konteks upacara keagamaan Hindu Bali" said nothing the KB holds -- 2026-11-12)
            ta = content.entity_type.get(a["id"])
            label = _SIMILAR_TYPE_LABELS.get(ta) if ta and ta == content.entity_type.get(b["id"]) else None
            lead = f"{name_a_cap} dan {name_b_cap} sama-sama merupakan {label}." if label else ""

    sides = []
    for e in enriched:
        g = _gloss(e["id"], limit=10 ** 6).rstrip(".")
        if g:
            core_g = g.split(";")[0].strip()
            name = _card_cased(e["id"], e.get("asked_as") or e.get("typed_as"))
            sides.append(f"{name[:1].upper()}{name[1:]} adalah {core_g}" if not re.match(r"(?:berarti|merupakan|adalah)\b", core_g)
                         else f"{name[:1].upper()}{name[1:]} {core_g}")
    if after:
        res = _drop_repeated_sentences(f"{lead}\n\n{after}", loose=False) if lead else after
    elif len(sides) == 2:
        res = "\n\n".join(x for x in (lead, f"{sides[0]}. Sementara itu, {sides[1]}.") if x)
    else:
        res = lead
    return _drop_irrelevant_comparison_sentences(res.strip(), enriched, user_msg) if res.strip() else answer


_SIMILARITY_Q_RE = re.compile(r"\b(?:persamaan(?:nya)?|kesamaan(?:nya)?|samanya)\b", re.I)


def _compare_from_cards(enriched: List[Dict[str, Any]], user_msg: Text) -> Text:
    """A two-term comparison or similarity answered from the two cards alone, for when the model's answer is gone
    (failed, refused, made up, or cut to nothing): "" when the question is no such comparison or nothing comes of it."""
    if len(enriched) < 2 or not _COMPARE_Q_RE.search(user_msg):
        return ""
    two = enriched[:2]
    if _SIMILARITY_Q_RE.search(user_msg):
        out = _complete_similarity("", two, user_msg)
    else:
        # what joins them first ("Sawa Wedana dan Asti Wedana sama-sama termasuk jenis Ngaben."), as on a model answer
        out = _complete_contrast(_complete_chain_link("", two).strip(), two, user_msg)
    return _tidy_answer(out) if out and out.strip() else ""


# what two terms of one type both are, as a reader says it (_complete_similarity); a type with no plain name gets none
_SIMILAR_TYPE_LABELS = {"SARANA_RITUAL": "sarana upacara", "TAHAPAN_UPACARA": "tahapan upacara",
                        "BANGUNAN_RITUAL": "bangunan upacara", "RITUAL_KEMATIAN": "upacara kematian",
                        "RITUAL": "upacara", "TIRTHA_SUCI": "tirtha", "NASKAH_SUCI": "naskah suci",
                        "KONSEP_FILOSOFIS": "konsep filosofis", "ENTITAS_KEAGAMAAN": "tokoh atau entitas keagamaan"}


# how one of two terms depends on or differs from the other: an order, or a contrast
_LINK_SAID_RE = re.compile(r"\b(?:setelah|sesudah|sebelum|menjelang|lanjutan|dilanjutkan|baru\s+boleh|tetapi|namun|"
                           r"sedangkan|belum|bukan|berbeda|karena\s+itu(?:lah)?)\b", re.I)


def _complete_stated_link(answer: Text, enriched: List[Dict[str, Any]], differ: bool = False) -> Text:
    """A comparison or relation question about two terms gets each definition sentence that
    names the other term with a reason or order ("Ngaben memisahkan jiwa ... tetapi jiwanya masih
    berbadan halus ...; karena itulah Atma Wedana diselenggarakan setelah Ngaben") when the answer
    left most of it out. Rule 17 asks for that dependency, yet "apa perbedaan ngaben dan atma
    wedana" gave two separate definitions on most loads (Tier B 2026-10-02/05).
    A later answer sentence the appended one holds whole goes ("Sementara itu, sulinggih adalah
    pendeta atau tokoh suci yang telah disucikan melalui upacara madiksa." above sulinggih's own
    sentence, Tier B 2026-10-09); never the first.
    `differ` (a difference question): only a sentence saying how the two differ or depend on each other -- an order or
    a contrast, not "sama-sama" -- and only when no sentence of the answer naming both says an order or reason already:
    "apa perbedaan ngaben dan atma wedana" got "Semua jenis Ngaben ... sama-sama berhak mendapat upacara Atma Wedana."
    under an answer saying Atma Wedana comes after Ngaben (plan #31)."""
    said = _content_words(answer)
    if differ and len(enriched) >= 2:
        rx_a, rx_b = _names_rx(enriched[0]), _names_rx(enriched[1])
        if rx_a and rx_b and any(rx_a.search(t) and rx_b.search(t) and _LINK_SAID_RE.search(t)
                                 for t in _SENT_PART_RE.findall(answer)):
            return answer
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
            if differ and (not _LINK_SAID_RE.search(s) or re.search(r"\b(?:sama-sama|yang\s+sama)\b", s, re.I)):
                continue
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


def _composition_rows(entity_id: Text, max_depth: Optional[int] = None) -> Dict[str, Any]:
    """The KB's composition tree of a sarana / tirtha / building, breadth-first (main version):
    {"rows": [(item name, kind parent it inherits its parts from or None, [(phrase, [part
    names])])], "leaves": the raw materials met, "variants": [(region, sentence, source)],
    "cut": bool}. No rows when the item has no recorded parts. `max_depth` 1: the item's row and its parts' own rows
    only (a deeper part with parts sets "cut")."""
    content = get_content()
    out: Dict[str, Any] = {"rows": [], "leaves": [], "variants": [], "cut": False}
    queue = [(content.composition_tree(entity_id), 0)]
    while queue:
        node, depth = queue.pop(0)
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
                if max_depth is None or depth < max_depth:
                    queue.append((child, depth + 1))
                else:
                    out["cut"] = True
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
        if plain and last.startswith("serta"):
            # a verb both open with is said once: "dilakukan setelah pabasmian dan sesudah jenazah hangus menjadi abu"
            # (bot test 2026-11-05: "... dan dilakukan sesudah ...")
            first, second = clauses[0].split(None, 1)[0], clauses[1].split(None, 1)
            if len(second) == 2 and second[0].lower() == first.lower():
                return f"{clauses[0]} dan {second[1]}"
            return f"{clauses[0]} dan {clauses[1]}"
        return f"{clauses[0]}, {last}"
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


# a question about what a thing is made of, down to its materials -- not what it holds or uses ("apa saja yang digunakan
# dalam sesajen" got nine breakdown lines, a 24-item "bahan dasarnya" list and a variant, sweep 2026-11-13)
_MADE_OF_Q_RE = re.compile(r"\bbahan\w*|\bterbuat\b|\b(?:di)?(?:buat|bikin)\s+(?:dari|pakai|dengan)\b|\bdari\s+apa\b", re.I)


def _composition_breakdown(entity_id: Text, said: Optional[Text] = None, deep: bool = True) -> Text:
    """The layered "made of" breakdown, built from the KB in code and written as sentences (user
    2026-10-15: templates must read like natural language, not "Rincian bahan menurut basis data:
    - X: terbuat dari a, b"): the item itself, its composite parts ("Rinciannya:"), the raw
    materials it comes down to (only when there are deeper levels -- with one level they are the
    sentence's own list), then the variants. Empty when no parts are recorded. `said` (the
    model's answer it is appended to): a row whose parts it already names all is left out -- canang
    sari's own parts came twice, as the model's list and as the breakdown's first sentence (user's
    live session, 2026-11-09). Not `deep` (a question about what it holds or uses, not its materials): the item and its
    parts' own rows, no raw-material summary, and a pointer to ask on when there is more."""
    data = _composition_rows(entity_id)
    # (a short tree is said whole: wadah's three rows got "Rinciannya masih berlanjut" for one line left, snapshot
    # 2026-11-13)
    if not deep and len(data["rows"]) > 4:
        data = _composition_rows(entity_id, 1)
    else:
        deep = True
    rows, variants = data["rows"], data["variants"]
    if not rows and not variants:
        return ""
    key = _ortho_key(said) if said else ""
    told = [bool(said) and all(_ortho_key(x) in key for _, names in groups for x in names) for _, _, groups in rows]
    sentences = [_composition_sentence(*r) for r, t in zip(rows, told) if not t]
    blocks = []
    if not told or not told[0]:
        if len(sentences) <= 2:
            # one part explained: "Kojong terbuat dari daun pisang." reads on in the same paragraph
            blocks.append(" ".join(sentences))
        else:
            blocks += [sentences[0], "Rinciannya:\n" + "\n".join(f"- {s}" for s in sentences[1:])]
    elif sentences:
        blocks.append("Rinciannya:\n" + "\n".join(f"- {s}" for s in sentences))
    if deep and len(rows) > 1 and data["leaves"] and not all(_ortho_key(x) in key for x in data["leaves"]):
        blocks.append(f"Jadi, bahan dasarnya antara lain {_join_names(data['leaves'])}.")
    if variants:
        # no source names: "(sumber: denpasar.kompas.com)" -- the user: "Remove the sumber thing" (2026-11-09); a region
        # that only says it is another option is no label: "- Pilihan lain: ceper memakai ..."
        blocks.append("Ada pula variasinya:\n" + "\n".join(
            f"- {region[:1].upper()}{region[1:]}: {sentence}."
            if region and region.lower() != "pilihan lain" else f"- {sentence[:1].upper()}{sentence[1:]}."
            for region, sentence, _ in variants))
    if data["cut"]:
        blocks.append("Rinciannya masih berlanjut; tanyakan bagian tertentu untuk detailnya.")
    return "\n".join(b for b in blocks if b)


def _complete_composition(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """"X terbuat dari apa": the 7B model drops or mixes up levels of a deep breakdown
    (tirta pangentas -> pripih emas -> daun dapdap), so the breakdown is appended from the KB
    unless the answer already names every item in it; of it only what the answer has not said."""
    if not enriched:
        return answer
    data = _composition_rows(enriched[0]["id"])
    if not data["rows"] and not data["variants"]:
        return answer
    said = _ortho_key(answer)
    items = [x for _, _, groups in data["rows"] for _, names in groups for x in names]
    if items and all(_ortho_key(x) in said for x in items) and not data["variants"]:
        return answer
    rest = _composition_breakdown(enriched[0]["id"], said=answer)
    if not rest:
        return answer
    # (its own parts already said, the rest goes on from the model's list without a second heading)
    head = "" if rest.startswith(("Rinciannya:", "Ada pula", "Jadi,")) else "Rincian lengkapnya:\n"
    return answer.rstrip() + "\n\n" + head + rest


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


def _complete_set_members(answer: Text, enriched: List[Dict[str, Any]], user_msg: Text = "") -> Text:
    # only for the set the question is about (the first resolved term), and
    # spelling-insensitive ("antahkarana" == "antah karana")
    m = _NUMERAL_SET_RE.match(enriched[0].get("name") or "") if enriched else None
    if not m:
        return answer
    # (not in a difference question: "Pancamahabutha terdiri dari: akasa, apah, ..." under "apa perbedaan pancamaha butha
    # dan moksa" is one term's list the other side does not mirror -- plan #31)
    if len(enriched) >= 2 and _COMPARE_Q_RE.search(user_msg) and not _SIMILARITY_Q_RE.search(user_msg):
        return answer
    e = enriched[0]
    members = _set_members(e)
    # (nor in a link question whose other term is no member, the members being no link: "apa hubungan dasa mala dan
    # pinang" got "Dasa mala terdiri dari: ..." after "tidak ada hubungan langsung", live run 2026-11-14)
    if len(enriched) >= 2 and _LINK_Q_RE.search(user_msg) and not any(
            _ortho_key(o.get("name") or "") in {_ortho_key(x) for x in members} for o in enriched[1:]):
        return answer
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


def _complete_kind_facts(answer: Text, enriched: List[Dict[str, Any]]) -> Text:
    """An answer that goes kind by kind through the asked term's kinds, two or more of them said with the same KB term
    (the patulangan of each wangsa), and names another kind without a sentence of its own while that kind's card says it
    with that term, gets the card's clause: "apa itu wangsa dan apa hubungannya dengan ngaben" gave Brahmana's, Wesia's
    and Sudra's patulangan and named Ksatria only in its list of the four, its black Lembu on its card in the context
    (Qwen, a near-tie, 2026-11-14). A kind's own sentence names it and no other kind; only a kind the answer names in an
    enumeration of three or more kinds and nowhere else gets a clause (a list item naming two kinds is no gap: "Tirtha
    Gangga: Dipakai dalam pembuatan Tirtha Pangentas ...")."""
    if not enriched:
        return answer
    content = get_content()
    e = enriched[0]
    kinds = set(r["target_id"] for r in e.get("relationships") or []
                if r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing") and r.get("target_id"))
    if len(kinds) < 3:
        return answer
    sents = [(s.strip(), set(_named_terms(s, everyday=True))) for s in _SENT_PART_RE.findall(answer) if s.strip()]
    own: Dict[str, List[str]] = {}               # kind -> its own sentences
    for s, terms in sents:
        named = terms & kinds
        if len(named) == 1:
            own.setdefault(next(iter(named)), []).append(s)
    with_term: Dict[str, set] = {}
    for k, ss in own.items():
        for s in ss:
            for t in _named_terms(s, everyday=True):
                if t not in kinds and t != e["id"] and t not in _CASE_GENERIC_IDS:
                    with_term.setdefault(t, set()).add(k)
    listed_only = {k for k in kinds - set(own)
                   if any(k in terms for _, terms in sents)
                   and all(len(terms & kinds) >= 3 for _, terms in sents if k in terms)}
    adds, last = [], None
    for t, said_with in with_term.items():
        if len(said_with) < 2 or not listed_only:
            continue
        last = next((s for s, terms in reversed(sents) if t in terms and terms & said_with), last)
        for k in sorted(listed_only):
            clause = next((c.strip() for c in re.split(r"(?<=[.!?;])\s+", content.best_definition(k) or "")
                           if {t, k} <= set(_named_terms(c, everyday=True))), None)
            if clause:
                clause = re.sub(r"^(?:dalam|pada)\s+(?:upacara\s+)?ngaben,\s*", "", clause, flags=re.I).rstrip(" ;.")
                adds.append(clause[:1].upper() + clause[1:] + ".")
    if not adds or not last:
        return answer
    return answer.replace(last, last + " " + " ".join(dict.fromkeys(adds)), 1)


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
    # (also "konteks juga secara eksplisit menyatakan bahwa ngaben dapat dilakukan di krematorium": the sentence went
    # whole and "apakah ngaben harus di setra?" lost its reason, Tier B on Qwen 2026-11-07)
    r"\s+(?:(?:hanya|juga|secara\s+\w+)\s+){0,3}(?:menyebutkan|menjelaskan|mencatat|memuat|menyatakan)\s+bahwa\s+"
    r"(?![^.!?\n]*\b(?:tidak|belum)\s+(?:memberikan|menyebutkan|mencantumkan|menjelaskan|merinci|mencatat)\b)"
    # ... and as the subject of a list's lead-in: "Meskipun demikian, konteks menyebutkan berbagai unsur yang digunakan
    # dalam upacara Ngaben, ..., antara lain:" went whole and left the list under "Tidak ada rincian spesifik ..." (bot
    # test 2026-11-05)
    r"|\bkonteks\s+(?:(?:hanya|juga)\s+)?(?:menyebutkan|mencatat|memuat|menjelaskan)\s+(?!bahwa\b)(?=[^.!?\n:]*:)",
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
    # (and a yes/no verdict: "Tidak, tidak ada pengganti ngaben yang tercatat dalam informasi yang tersedia." went, and
    # "apakah ada pengganti ngaben?" got its verdict last, style test 2026-11-07)
    return (out if (_VERDICT_RE.search(out) or _OPENING_VERDICT_RE.match(out)) and not _PROMPT_REF_RE.search(out)
            else None)


_OPENING_VERDICT_RE = re.compile(r"\s*(?:Ya|Tidak|Bukan|Boleh|Benar)\s*,\s+\S", re.I)


def _strip_meta_phrases(answer: Text) -> Text:
    # until nothing changes: "berdasarkan fakta yang terdapat dalam konteks, ..." lost only its
    # inner "yang terdapat dalam konteks" and kept "Berdasarkan fakta," (Tier B 2026-10-05)
    # the context as what a list's lead-in gives: "Namun, konteks memberikan penekanan khusus pada dua aspek ...:" went
    # whole and left the list under "Tidak ada satu tahapan ... yang paling penting" (style test 2026-11-07)
    out, prev = re.sub(r"\bkonteks\s+(?:(?:juga|hanya)\s+)?(?:memberikan|memberi)\s+(?=[^.!?\n:]*:[ \t]*(?:\n|$))", "ada ",
                       answer, flags=re.I), None
    while out != prev:
        prev, out = out, _META_PHRASE_RE.sub("", out)
    # a second "bahwa" whose first went with the cut lead: "Informasi yang tersedia hanya menyatakan bahwa Sasih Kasanga
    # adalah ..., dan bahwa sasih merupakan ..." read "Sasih Kasanga adalah ..., dan bahwa sasih ..." (bot test 2026-11-05)
    unchanged = {s.strip() for s in _SENT_PART_RE.findall(answer)}

    def no_orphan_bahwa(m: "re.Match") -> Text:
        s = m.group(0)
        second = re.search(r",\s+dan\s+bahwa\s+", s)
        if not second or s.strip() in unchanged or re.search(r"\bbahwa\b", s[:second.start()]):
            return s
        return s[:second.start()] + ", dan " + s[second.end():]
    if out != answer:
        out = _SENT_PART_RE.sub(no_orphan_bahwa, out)
    # a cut that took a negated predicate leaves its "tidak": "Alasan spesifik mengapa ... dihindari
    # dalam Ngaben tidak disebutkan dalam definisi yang diberikan." -> "... dalam Ngaben tidak."
    # (Tier B 2026-10-05); that sentence goes whole
    for s in _SENT_PART_RE.findall(out):
        if re.search(r"\b(?:tidak|belum)\s*[.!?]*\s*$", s) and s.strip() not in answer:
            out = out.replace(s, "", 1)
    parts = _SENT_PART_RE.findall(out)
    about_prompt = [s for s in parts if _PROMPT_REF_RE.search(s)]
    if about_prompt and len(about_prompt) < len([s for s in parts if s.strip()]):
        # the answer's only verdict is said without the prompt rather than lost with it -- and so is an opening
        # verdict: "Tidak, konteks tidak mencatat bahwa rasa bersifat wajib." went, and "apakah rasa wajib" was
        # answered from its last sentence (plan #16, 2026-10-26)
        first = next((s for s in parts if s.strip()), None)
        others_judge = any(_VERDICT_RE.search(s) for s in parts if s not in about_prompt)
        rescued = next(((s, r) for s in about_prompt if (not others_judge or s == first)
                        and (_VERDICT_RE.search(s) or _CONTEXT_LACKS_RE.search(s)
                             or s == first and _OPENING_VERDICT_RE.match(s)) and (r := _rescue_verdict(s))),
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
    cut_off: bool = False                     # the model's reply hit the token limit (_llm_answer)


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
    content = get_content()
    # a why-question keeps every fact of its terms that states a reason, whatever its family: "kenapa (tirtha
    # pangentas) harus dibuat pada hari pembakaran?" and "kenapa orang yang lebih tua tidak boleh menyembah jenazah?"
    # got "belum tersedia" -- the reasons are a DIBUAT_SAAT and a SYARAT fact ("..., karena ...") the purpose and meaning
    # families leave out (style test 2026-11-06)
    if aspect_preds is not None and _WHY_Q_RE.search(user_msg):
        reasons = {p for e in enriched for p, vals in content.attributes.get(e["id"], {}).items()
                   if any(re.search(rf"\b(?:{_REASON_MARKERS})\b", v, re.I) for v in vals)}
        aspect_preds = set(aspect_preds) | reasons
    # the text-only attributes of the asked aspect (a word-meaning question gets the
    # literal meaning / word origin ones); none for a plain "apa itu X"
    attr_preds = PREDICATE_FAMILIES["asal_kata"] if word_meaning else aspect_preds
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
    # "tirthanya apa?" after ngalukat asks ngalukat's tirtha (_class_filter kept those): as "tirtha apa?" the model and
    # the focus line read it as what tirtha is (style test 2026-11-06)
    if class_list and len(enriched) >= 2 and _said_with_nya(user_msg, enriched[0]):
        cls_name, topic_name = enriched[0]["name"], enriched[1]["name"]
        if re.match(rf"^\W*{re.escape(cls_name)}\s+apa(?:\s+(?:saja|aja))?\s*[?.!]*\s*$", synth_q, re.I):
            # (a list question: "tirtha untuk ngalukat apa?" still got the focus "pengertian tirtha untuk ngalukat")
            synth_q = f"{cls_name} apa saja yang digunakan untuk {topic_name}?"
        else:
            synth_q = re.sub(rf"(?<![\w-]){re.escape(cls_name)}(?![\w-])", f"{cls_name} untuk {topic_name}", synth_q,
                             count=1, flags=re.I)
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
        is_similarity = bool(re.search(r"\b(?:persamaan|kesamaan|samanya)\b", user_msg, re.I))
        if is_similarity:
            synth_sys_prompt += (
                "\n    17. The user asks how the terms are SIMILAR (persamaan). Look at both definitions and their relationships. State the shared categories, "
                "purposes, elements, or contexts that both terms have in common according to the context (e.g. both "
                "being kinds of the same class). Never claim a shared role, use or place the context does not state for "
                "BOTH terms. "
                "Formulate the similarity directly from their definitions and facts. NEVER claim information is missing "
                "or say 'belum tercatat' merely because a direct similarity relation is not pre-written in the database. "
                "Only state similarities the facts support -- do not claim they are identical where they differ. "
                "State each fact ONCE: do NOT give the definition or role of a term in the opening comparison and then repeat that same definition or explanation again in later paragraphs.\n")
        else:
            # (2026-11-12, "apa perbedaan ngelungah dan nyekah?": the 11-10 wording -- "differences in purpose,
            # materials, caste/users, or sequence ... principal types or rituals" -- had Qwen open with what each is and
            # then walk those headings, each one saying the opening again: "Perbedaan mendasar terletak pada tujuan dan
            # sasaran upacara. ... Sebaliknya, Nyekah bertujuan menyucikan suksma sarira ..." under "Nyekah adalah ...
            # untuk menyucikan suksma sarira"; the user: "it repeats a lot of points". Its "State each fact ONCE" did
            # not hold against the headings it asked for.)
            synth_sys_prompt += (
                "\n    17. The user asks how terms differ. Give the difference, not two descriptions and not a "
                "list of headings. Open with ONE sentence on what each is, from its definition: 'X adalah ..., "
                "sedangkan Y adalah ...'. After it add only differences that sentence does not already hold, each "
                "once and in as few sentences as it needs. Never say again, in any words, what a term is, who or "
                "what it is for, what it does or when it is held once a sentence has said it -- not to introduce "
                "a new point, not as a summary. Go straight to the new fact: after an opening that said who X is "
                "for and what Y is for, not 'X ditujukan untuk <who>, di mana <new fact>' or 'Tujuan Y adalah "
                "<what it is for> agar <new fact>', but 'Pada X, <new fact>' and 'Dengan Y, <new fact>'. No "
                "sentence that only announces a difference ('Perbedaan mendasar "
                "terletak pada tujuan dan sasaran.', 'Perbedaan kedua adalah dalam hal ...', 'Terdapat juga "
                "perbedaan dalam ...'). Leave out what does not set them apart (a good day, a ritual direction, a "
                "list of one term's steps, kinds or materials) unless the question asks for it. When nothing is "
                "left to add, stop. State only differences the facts show. A fact given for one term only is not "
                "evidence that the other term lacks it or does the opposite. Keep each fact's meaning exactly: "
                "never turn 'belum' or 'tidak' into its opposite. When a definition says why one comes after or "
                "depends on the other, say that too. Never say information is missing only because no fact "
                "compares the two directly.\n")
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
    # A question asking for something the context does not cover (e.g. "apa pakaian yang digunakan pada saat ngaben")
    if (len(enriched) == 1 and not q.families and not missing_aspects and not why_q and not consequence_q
            and not _COMPARE_Q_RE.search(user_msg) and not _RELATION_Q_RE.search(user_msg)):
        thing = _ungrounded_asked_thing(user_msg, enriched)
        if thing:
            synth_sys_prompt += (
                f"\n    33. The question asks specifically about \"{thing}\". The context does "
                "not contain information about this. Use rule 5: say this specific information "
                "is not recorded. Do not answer with the definition or other available facts.\n")
    return synth_sys_prompt


def _conversation_note(q: _Question) -> str:
    """The user's two messages before a follow-up, for the situation they told: the model saw the follow-up alone, and
    "jadi ngaben tingkat apa yang bisa diambil?" after "... jika tidak memiliki banyak uang?" got all three levels and no
    pick, "apakah harus diaben?" after "anak saya meninggal umur 2 bulan" got "Ya" (style test 2026-11-06). Only for a
    follow-up -- a short message or one opening like one -- and only the user's words, never the bot's answers."""
    if not q.tracker:
        return ""
    # (not a bare greeting or thanks: "halo" came in as the situation told)
    turns = [t for t in recent_user_turns(q.tracker, limit=3)[:-1]
             if len(_WORD_RE.findall(t)) >= 3 or _mentioned_terms(t, get_resolver())[0]]
    msg = q.msg
    if not turns or not (len(_WORD_RE.findall(msg)) <= 8 or _FOLLOW_UP_CUE_RE.search(msg) or _ANAPHOR_RE.search(msg)):
        return ""
    said = "; ".join(f'"{t.strip()}"' for t in turns if t.strip())
    return (f"Pesan pengguna sebelumnya (hanya untuk memahami situasi yang ia ceritakan, misalnya umur, keadaan "
            f"jenazah, atau kemampuan biaya; jangan dijawab lagi): {said}\n"
            if said else "")


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
    earlier = _conversation_note(q)
    budget = _PROMPT_CHAR_BUDGET - len(synth_sys_prompt) - 2 * len(synth_q) - 2 * len(focus) - 250 - len(earlier)
    raw_context = _json_compact(_fit_context(context_items, budget))
    synth_user_prompt = (earlier + f"Pertanyaan: {synth_q}\n" + (f"Yang ditanyakan: {focus}\n" if focus else "")
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
    topic = q.tracker.get_slot("current_entity") if q.tracker else None
    topic_id = getattr(get_resolver().resolve(topic), "id", None) if topic else None
    usage_answer = (_young_baby_answer(user_msg, enriched) or _schedule_miss(user_msg, enriched)
                    or _false_day_premise_answer(user_msg, enriched) or _not_avoided_day_answer(user_msg, enriched)
                    or _usage_norm_answer(user_msg, enriched) or _stated_rule_answer(user_msg, enriched)
                    or _stated_prohibition_answer(user_msg, enriched)
                    or _same_thing_answer(user_msg, enriched, topic_id)
                    or _case_compare_answer(user_msg, enriched) or _order_answer(user_msg, enriched)
                    or _good_days_answer(user_msg, enriched) or _avoided_days_answer(user_msg, enriched)
                    or _stated_reason_answer(user_msg, enriched)
                    or _kind_consequence_answer(user_msg, enriched)
                    or _two_definitions_answer(user_msg, enriched)
                    or _since_death_answer(user_msg, enriched)
                    or _duration_miss(user_msg, enriched)
                    or _superlative_answer(user_msg, enriched)
                    or _which_kind_answer(user_msg, enriched)
                    or _name_answer(user_msg, enriched))
    if usage_answer:
        return _tidy_answer(usage_answer)
    if no_contents:
        name, known = enriched[0]["name"], _known_sentence(enriched[0].get("definition"), entity_id=enriched[0]["id"], name=enriched[0]["name"])
        answer = (f"Maaf, isi atau bahan {name} belum tercatat di basis data."
                  + (f" Yang tercatat tentang {name}: {known}" if known else ""))
        return _tidy_answer(answer)
    if not follow_up:
        miss = (_class_list_miss(class_list, enriched) if class_list
                else _code_miss(user_msg, enriched, families, missing_aspects))
        if miss:
            return _tidy_answer(miss)
    # A question asking for a specific thing the KB does not cover: "apa pakaian
    # yang digunakan pada saat ngaben" -- with no aspect detected, the LLM got
    # rule 4's instruction to use the available data and returned ngaben's
    # definition as if it answered the clothing question (conersation.md section IV,
    # 2026-11-09). The miss catches it before the model is called.
    if (not follow_up and len(enriched) == 1 and not families
            and not _COMPARE_Q_RE.search(user_msg) and not _RELATION_Q_RE.search(user_msg)):
        thing = _ungrounded_asked_thing(user_msg, enriched)
        if thing:
            return _tidy_answer(_asked_thing_miss(thing, enriched[0]))
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
        q.cut_off = True
    return answer


def _llm_failed_answer(q: _Question) -> str:
    """The answer when the model cannot be asked (Groq down, the day's tokens spent, a timeout) or replies with nothing:
    the asked aspect by its template, else the first sentence of each asked term (two at most) with the asked aspect's
    facts -- short, and never every card in full. It was every term's whole definition and facts: "kenapa jenazah harus
    dibakar?" read as a page of cards, which the user met live when key 3 ran out (2026-11-06)."""
    enriched = q.enriched
    families = set(q.families)
    # a why-question asks the purpose or meaning; the stages of a how-question come with their how
    for both, one in (({"fungsi", "simbol"}, "fungsi"), ({"tahapan", "cara"}, "tahapan")):
        if families == both:
            families = {one}
    # the asked aspect of the first term, however many the message brought ("kenapa abu jenazah dibuang ke laut?" has
    # nganyut, abu and jenazah); a comparison or relation of two gets each one's first sentence below
    relation = len(enriched) >= 2 and bool(_COMPARE_Q_RE.search(q.msg) or _RELATION_Q_RE.search(q.msg))
    if enriched and len(families) == 1 and not relation:
        family = next(iter(families))
        if family in _ASPECT_TEMPLATE_FAMILIES or family in _TEMPLATES:
            try:
                text = _template_answer(family, enriched, q.msg)
            except Exception as e:  # a template that cannot answer this one: the short form below
                print(f"fallback template error: {e}")
                text = None
            if text:
                return text
    # what it costs is in the priced cards' sentences that state an amount (krematorium's packages, harga tirtha)
    if _PRICE_Q_RE.search(q.msg):
        money = [s for e in enriched for s in _sentences(e.get("definition"))
                 if re.search(r"\d[\d.,]*\s*(?:juta|ribu|rupiah|kepeng)\b", s, re.I)]
        if money:
            return " ".join(dict.fromkeys(money[:3]))
    compared = _compare_from_cards(enriched, q.msg)
    if compared:
        return compared
    parts: List[str] = []
    for e in enriched[:2]:
        lead = _first_sentence(_deterministic_answer([dict(e, aspect_facts=[])]) or "", limit=400)
        if lead:
            parts.append(lead)
        parts += [f"{f[:1].upper()}{f[1:].rstrip('.')}." for f in (e.get("aspect_facts") or [])[:2]]
    return " ".join(parts) or _deterministic_answer(enriched[:1])


def _answer_overrides(q: _Question, answer: str) -> str:
    """An empty or English reply, a refusal or a fabrication: the definitions, an honest miss, or the refusal
    kept with what is recorded."""
    user_msg, enriched, consequence_q, aspect_preds = q.msg, q.enriched, q.consequence_q, q.aspect_preds
    overview, about, raw_context = q.overview, q.about, q.raw_context
    if not answer.strip() or _looks_english(answer):
        # an empty reply reached the user as silence
        _log_fabrication(user_msg, enriched, answer, kind="llm_empty_or_english_override")
        answer = _llm_failed_answer(q)
    elif _has_grounding(enriched):
        # a plain "apa itu X" -- not any question with no aspect word found: "sasih apa yang baik untuk dasa
        # mala", "apa hubungan antara tiying gading dengan bwah loka", "Kayu Cendana dilakukan sebelum atau
        # sesudah wesia" had their honest "not recorded" swapped for bare definitions (12 a run, LLM
        # comparison 2026-10-20)
        # not a consequence question ("tanpa" is a relation word): "apa yang terjadi jika Sorohan Kecil dilakukan
        # tanpa ngaben" got "Maaf, hubungan antara sorohan kecil dan ngaben belum tercatat" (plan #16)
        # (not a question that also asks what each is: "apa itu ngaben, apa itu ngroras, apa bedanya" lost both
        # definitions to a two-line contrast -- the plain path gives them, and the checks add the contrast lead)
        compare_q = (len(enriched) >= 2 and bool(_COMPARE_Q_RE.search(user_msg)) and not consequence_q
                     and not _WHAT_IS_SHAPE_RE.search(user_msg))
        relation_q = len(enriched) >= 2 and bool(_RELATION_Q_RE.search(user_msg)) and not consequence_q
        plain = (aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg) and not relation_q and not compare_q
                 and not _ORDER_Q_RE.search(user_msg)
                 and (overview or bool(_WHAT_IS_SHAPE_RE.search(user_msg))))
        known = _known_sentence(about.get("definition"), entity_id=about.get("id"), name=about.get("name"))
        if _has_refusal_signal(answer):
            if plain:
                # "apa itu X" refused although X's definition was right there
                _log_refusal(user_msg, enriched, answer)
                answer = _deterministic_answer(enriched)
            elif compare_q:
                # User asked difference or similarity between multiple terms:
                # Strip refusal phrases and ensure comparative answer is formulated
                _log_refusal(user_msg, enriched, answer)
                cleaned = re.sub(r"(?:\A|(?<=[.!?\n]))\s*Maaf,[^.!?\n]*\b(?:belum|tidak)\s+(?:tercatat|tersedia)[^.!?\n]*[.!?]", "", answer).strip()
                cleaned = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", cleaned)).strip()
                if cleaned and len(_content_words(cleaned)) >= 6:
                    answer = cleaned
                else:
                    answer = _compare_from_cards(enriched, user_msg) or answer
            elif relation_q:
                cleaned = re.sub(r"(?:\A|(?<=[.!?\n]))\s*Maaf,[^.!?\n]*\b(?:belum|tidak)\s+(?:tercatat|tersedia|disebutkan|ditemukan)[^.!?\n]*[.!?]", "", answer).strip()
                cleaned = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", cleaned)).strip()
                if cleaned and len(enriched) >= 2 and _explains_relationship(cleaned, enriched[0], enriched[1]):
                    answer = cleaned
                else:
                    # no link recorded: say so about both, with what each is
                    _log_refusal(user_msg, enriched, answer, kept=True)
                    a, b = enriched[0], enriched[1]
                    answer = f"Maaf, hubungan antara {a['name']} dan {b['name']} belum tercatat di basis data."
                    for e in (a, b):
                        k = _known_sentence(e.get("definition"), entity_id=e["id"], name=e["name"])
                        if k:
                            answer += f" Yang tercatat tentang {e['name']}: {k}"
            else:
                # the asked detail really is not recorded: keep the refusal, add what is
                _log_refusal(user_msg, enriched, answer, kept=True)
                if known:
                    answer = f"{answer.rstrip()} Yang tercatat tentang {about['name']}: {known}"
        elif _has_fabrication_signal(answer, enriched, raw_context):
            _log_fabrication(user_msg, enriched, answer)
            compared = _compare_from_cards(enriched, user_msg) if compare_q else ""
            if compared:
                answer = compared
            elif plain or not known:
                answer = _deterministic_answer(enriched)
            else:
                # an invented reason for "kenapa angka 11 dipilih ..." is replaced by an
                # honest miss, not by a definition that answers something else
                answer = ("Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data. "
                          f"Yang tercatat tentang {about['name']}: {known}")
    return answer


# a sentence saying something is not recorded, at the answer's start (fullmatch: the whole answer)
_MISS_LEAD_RE = re.compile(r"\s*(?:Maaf,\s*)?[^.!?\n]*\b(?:belum|tidak)\s+tercatat\b[^.!?\n]*[.!?]?")


# a sentence whose complement only names its subject again: "Setelah Ngaben, pitra masih berkedudukan sebagai pitra."
# (plan #31, 2026-11-13)
_EMPTY_SENT_RE = re.compile(
    r"\s*(?:(?:Namun|Tetapi|Akan\s+tetapi|Jadi),\s*)?(?:(?:Setelah|Sesudah|Sebelum|Pada|Dalam|Di|Selama|Saat|Ketika)\s+"
    r"[^,.!?\n]{1,40},\s*)?(?P<s>[A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*)?)\s+(?:(?:masih|tetap|juga|pun|hanya|pada\s+dasarnya)\s+)*"
    r"(?:(?:berkedudukan|berstatus|disebut|dianggap|dinilai|merupakan|adalah|menjadi)\s+)?(?:sebagai\s+)?(?P=s)\s*[.!]?\s*",
    re.I)


def _drop_empty_sentences(answer: Text) -> Text:
    """A sentence that says its subject is itself goes, and a "Namun," / "Tetapi," after it with it (plan #31)."""
    if not _EMPTY_SENT_RE.search(answer):
        return answer
    state = {"cut": False}

    def fn(s: Text, before: Text) -> Text:
        if _EMPTY_SENT_RE.fullmatch(s):
            state["cut"] = True
            return ""
        if state["cut"]:
            state["cut"] = False
            s = _cap(re.sub(r"^(?:namun|tetapi|akan\s+tetapi|meskipun\s+demikian|sebaliknya),\s*", "", s, flags=re.I))
        return s
    return _edit_sentences(answer, fn)


def _answer_checks(q: _Question, answer: str) -> str:
    """The checks on the model's answer, in order: cut what the context does not support, complete what it left
    out, put the asked thing first. Each says in its comment or name what it catches."""
    user_msg, enriched, tracker, word_meaning = q.msg, q.enriched, q.tracker, q.word_meaning
    consequence_q, families, aspect_preds, day_q = q.consequence_q, q.families, q.aspect_preds, q.day_q
    class_list, stages_q, previous, follow_up = q.class_list, q.stages_q, q.previous, q.follow_up
    why_q, has_reason, missing_aspects, composition_q = q.why_q, q.has_reason, q.missing_aspects, q.composition_q
    synth_q, about, raw_context = q.synth_q, q.about, q.raw_context
    answer = _fix_misspellings(_fix_stray_accents(_tidy_answer(answer), raw_context), raw_context)
    avoid_q = bool(_WHY_AVOID_Q_RE.search(user_msg))
    if why_q and has_reason and _why_about_term_only(user_msg, enriched, avoid_q):
        # a why-avoided answer's reasons are judging words (tidak baik, sasih mati), not purpose words
        answer = _strip_why_refusal(answer, None if avoid_q else enriched)
    answer = _drop_speculation(answer, raw_context)
    answer = _drop_unsupported(answer, raw_context, synth_q)
    answer = _drop_unsupported_purposes(answer, raw_context)
    if _COMPARE_Q_RE.search(user_msg):
        answer = _drop_unsupported_comparatives(answer, raw_context)
    answer = _drop_unlinked_glosses(answer, raw_context)
    answer = _fix_outside_glosses(answer, raw_context)
    answer = _fix_item_glosses(answer)
    answer = _trim_card_retellings(answer, user_msg, enriched)
    answer = _fix_modal_strength(answer, raw_context, user_msg)
    answer = _fix_dropped_place_preposition(answer, raw_context)
    answer = _drop_filler_openers(answer, user_msg, enriched)
    answer = _drop_empty_sentences(answer)
    # not on a why-question about something else than the term, which its purpose does not answer: "kenapa jenazahnya
    # harus dibakar? gak dikubur aja gitu" got "Selain itu, ngaben berfungsi sebagai perekat kohesi sosial. Selain itu,
    # ngaben melambangkan siklus kematian." (human test 2026-11-03)
    if follow_up and aspect_preds and not (why_q and not _why_about_term_only(user_msg, enriched, avoid_q)):
        # first, so that a sentence only recalling the previous answer can go once a new fact is there
        answer = _complete_aspect_facts(answer, enriched, user_msg)
    answer = _keep_asked_tier(answer, user_msg, enriched)
    # before the completions below: what code appends is never a repeat to drop. The last answer
    # counts only on a follow-up: tried on every turn on the same topic, it cut the answer itself
    # whenever the turn before had said it -- "apa guna patulangan" lost "berfungsi sebagai tempat
    # pembaringan jenazah", "apa makna banten pejati" its meaning (2026-10-08 replay). A re-asked
    # question wants its answer again.
    # (not under a miss: what is recorded instead is the closest fact even when the turn before said it -- "maknanya
    # apa?" about monmon kept only "Makna monmon tidak tercatat dalam basis data."; nor on a why-question, whose reason is
    # the answer however often it was said -- "kenapa bisa beda?" lost "... terjadi karena adanya prinsip desa kala
    # patra" and opened "Variasi tersebut juga ...", style test 2026-11-07)
    answer = _drop_repeated_sentences(answer, previous if follow_up and not why_q and not _MISS_LEAD_RE.match(answer)
                                      else "", loose=True, protect=_asked_specifics(user_msg, enriched))
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
    answer = _fix_class_claims(answer, enriched)
    answer = _fix_false_name_claims(answer)
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
    answer = _complete_set_members(answer, enriched, user_msg)
    # (and a list cut off at the token limit: "berapa tirtha yang dipakai dalam ngaben?" said "15 jenis" and listed 13,
    # style test 2026-11-07)
    # (not for a question picking some kinds: "pura apa yang berhubungan dengan ngaben?" got "Jenis pura lainnya yang
    # tersedia: merajan pusat, pura besakih", style test 2026-11-07)
    picks = bool(enriched) and bool(re.search(rf"(?<![\w-]){re.escape(enriched[0]['name'])}\s+(?:apa\s+(?:saja\s+|aja\s+)?)?"
                                              r"yang\s+(?!(?:ada|termasuk)\b)", user_msg, re.I))
    if not class_list and not picks and (aspect_preds is None and not _SPECIFIC_Q_RE.search(user_msg)
                                         or families == ["jenis"]) or q.cut_off:
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
        answer = _complete_stated_link(answer, enriched, differ=bool(
            _COMPARE_Q_RE.search(user_msg) and not _RELATION_Q_RE.search(user_msg) and not _SIMILARITY_Q_RE.search(user_msg)))
        # (`relation`: a link question -- "X tanpa Y bisa gak" asks whether X goes without Y, and "Informasi tentang
        # hubungan langsung antara pabersihan mati dan sorohan kecil belum tersedia." stood over its own two misses,
        # live run 2026-11-14)
        answer = _complete_chain_link(answer, enriched, relation=bool(
            _LINK_Q_RE.search(user_msg) and not _COMPARE_Q_RE.search(user_msg) and not consequence_q))
        # (not on a why-question: "kenapa bisa beda?" after Karangasem vs Denpasar asks why practice differs, and got
        # "Perbedaannya: Desa kala patra adalah ..., sedangkan Ngaben adalah ...", style test 2026-11-07)
        if _COMPARE_Q_RE.search(user_msg) and not why_q:
            if re.search(r"\b(?:persamaan|kesamaan|samanya)\b", user_msg, re.I):
                answer = _complete_similarity(answer, enriched, user_msg)
            else:
                answer = _complete_contrast(answer, enriched, user_msg)
    if why_q and _WHY_AVOID_Q_RE.search(user_msg):
        answer = _complete_stated_reasons(answer, enriched, user_msg)
    if composition_q:
        answer = _complete_composition(answer, enriched)
    if day_q and not re.search(r"\bsiapa\b", user_msg, re.I) and not why_q:
        # (who decides the day asks for no day: "siapa yang nentuin hari baiknya?" got its right answer and then every
        # sasih and wuku rule, bot test 2026-11-05; nor does why one is avoided: "kenapa hari pasah tidak boleh untuk
        # ngaben?" got the whole wuku rule after the answer had named pasah's fellow days, style test 2026-11-07)
        answer = _complete_day_rules(_drop_unasked_day_half(answer, _asked_day_half(enriched)), enriched)
    answer = _complete_span_rule(answer, user_msg, enriched)
    if stages_q:
        answer = _drop_kinds_from_stages(answer, enriched)
        if not _ONE_STAGE_Q_RE.search(user_msg):
            answer = _complete_stage_order(answer, enriched)
    if word_meaning:
        answer = _add_literal_meaning(answer, enriched, user_msg)
    # (after the repeat cut, which took the added Ksatria sentence for a repeat of Brahmana's black Lembu)
    answer = _complete_kind_facts(answer, enriched)
    answer = _drop_empty_items(answer)
    # a sentence cut at a paragraph's start leaves its space: "\n\n Bahkan dalam kasus khusus ..." (Tier B
    # 2026-10-15); a nested list item keeps its indent
    answer = re.sub(r"\n[ \t]+(?=[^\s\-*•\d])", "\n", answer)
    # ... and a cut lead-in its blank lines ("... Bhuwana Agung.\n\n\n* Iswara ...", style test 2026-11-06)
    answer = re.sub(r"\n{3,}", "\n\n", answer)
    # a connective whose sentence before it was cut: "Meskipun demikian, bale semanggen ..." opened
    # the answer (2026-10-09)
    lead = _OPENING_LEANBACK_RE.match(answer)
    if lead and len(answer) > lead.end():
        answer = answer[lead.end():][:1].upper() + answer[lead.end() + 1:]
    # ... nor the paragraph under a miss: "Maaf, alasannya belum tercatat di basis data.\n\nSelain itu, dalam konteks
    # upacara Pabersihan Mati, telur ayam ..." once the sentence between went (style test 2026-11-07)
    miss = re.match(r"\s*Maaf,[^\n]*\b(?:belum|tidak)\s+tercatat\b[^\n]*\n\s*\n", answer)
    if miss:
        rest = answer[miss.end():]
        lead = _OPENING_LEANBACK_RE.match(rest)
        if lead and len(rest) > lead.end():
            answer = answer[:miss.end()] + rest[lead.end()].upper() + rest[lead.end() + 1:]
    if not answer.strip():
        # the guards above cut every sentence: "apa fungsi bale delod dalam prosesi persemayaman
        # jenazah?" reached the user as silence (2026-10-08 batch)
        # (a comparison is answered from the two cards: user, 2026-11-10)
        answer = _compare_from_cards(enriched, user_msg)
        if not answer:
            known = _known_sentence(about.get("definition"), entity_id=about.get("id"), name=about.get("name"))
            answer = _name_missing("Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data."
                                   + (f" Yang tercatat tentang {about['name']}: {known}" if known else ""),
                                   user_msg, enriched, families, class_list)
    elif _MISS_LEAD_RE.fullmatch(answer.strip()) and about:
        # ... or every sentence but the miss: "kenapa bisa mahal?" read "Maaf, alasannya belum tercatat di basis data."
        # alone (style test 2026-11-07); the closest recorded fact follows, as on any other miss
        compared = _compare_from_cards(enriched, user_msg)
        if compared:
            answer = compared
        else:
            known = _known_sentence(about.get("definition"), entity_id=about.get("id"), name=about.get("name"))
            if known:
                answer = f"{answer.strip()} Yang tercatat tentang {about['name']}: {known}"
    answer = _drop_contradictory_no_link(answer, enriched)
    return answer


def _closing_notes(q: _Question, answer: str, code: bool = False) -> str:
    """The corrections ("X bukan ... sasih"), the answer in the asked name, or the "same as before" note -- not on a
    code answer (`code`), which answers the question as asked: "bayi tetangga meninggal umur 2 bulan, itu diaben juga
    gak?" got "(Ini sama dengan penjelasan saya sebelumnya ...)" after its own rule (snapshot 2026-11-12)."""
    user_msg, enriched, tracker, corrections = q.msg, q.enriched, q.tracker, q.corrections
    about = q.about
    for c in reversed(corrections):
        if _ortho_key(c) not in _ortho_key(answer):
            answer = f"{c} {answer}"

    # the user asked by another name for the same concept: the answer speaks that name (_in_asked_names), and the
    # "nothing more is recorded" note below does not follow -- it read as a refusal after "apa itu samskara"
    # following "apa itu sangaskara" (2026-09-24)
    if any(e.get("asked_as") and _plain_other_name(e, e["asked_as"]) for e in enriched):
        answer = _in_asked_names(answer, enriched, user_msg)
    elif (tracker is not None and not code and not answer.startswith("Maaf")
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

    return _short_name_brackets(answer)


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
        return _closing_notes(q, code, code=True)
    try:
        answer = _llm_answer(q, synth_sys_prompt, synth_user_prompt)
    except Exception as e:
        # LLM down/unreachable/timed out/rate-limited -- fall back to the pure-Python
        # answer instead of crashing the action and leaving the user with no
        # reply at all.
        print(f"LLM synthesis error: {e}")
        return _closing_notes(q, _llm_failed_answer(q), code=True)
    answer = _answer_overrides(q, answer)
    answer = _answer_checks(q, answer)
    return _closing_notes(q, answer)


_RECORDED_LEAD_RE = re.compile(
    r"(?P<pre>^|[.!?]\s+|\n\s*)(?:"
    r"(?:(?:fakta(?:-fakta)?|informasi|data|hal)\s+)?yang\s+(?:tercatat|tersedia)(?:\s+(?:dalam|di)\s+basis\s+data)?"
    r"(?:\s+(?:mengenai|tentang|terkait(?:\s+dengan)?)\s+(?P<x>[^.:;\n]{1,80}?))?\s+(?:hanyalah|hanya|adalah|ialah)"
    r"|basis\s+data\s+(?:(?:hanya|juga)\s+)?(?:mencatat|menyebutkan|menyatakan|menunjukkan))"
    r"\s+bahwa\s+(?:(?P<pron>ia|dia|beliau)\s+(?=\w))?(?P<c>\w)", re.I)


def _recorded_lead(m: "re.Match") -> Text:
    """The fact under the bot's own heading, "Yang tercatat tentang X: ...", or alone when X is no name. A pronoun
    after it is X: "Yang tercatat mengenai nistaning madya adalah bahwa ia merupakan ..." read "Yang tersedia tentang
    nistaning madya: ia merupakan ..." (live run 2026-11-14)."""
    x = (m.group("x") or "").strip()
    pron = m.group("pron")
    if x and not re.fullmatch(r"(?:hal|hal\s+(?:ini|tersebut|itu)|ini|itu|tersebut)", x, re.I):
        return f"{m.group('pre')}Yang tercatat tentang {x}: " + (f"{x[:1].upper()}{x[1:]} " if pron else "") + m.group("c")
    lead = f"{pron} {m.group('c')}" if pron else m.group("c")
    return m.group("pre") + lead[:1].upper() + lead[1:]


def _tidy_answer(answer: Text) -> Text:
    """Output clean-up every answer gets: Cyrillic look-alikes, references to the prompt
    itself, and sentences naming a prompt field."""
    answer = answer.translate(_CYRILLIC_LOOKALIKES)
    answer = _strip_meta_phrases(answer)
    # the family is the yajamana, not the yajamana's family: "Tugas keluarga yajamana dalam upacara Ngaben ..."
    # ("apa tugas keluarga?", 2026-11-12); "keluarga sang yajamana" keeps its own sense
    # (once: after it, "keluarga" alone)
    answer = re.sub(r"\b(keluarga)\s+(yajamana)\b(?!\s*\()", r"\1 (\2)", answer, count=1, flags=re.I)
    answer = re.sub(r"\b(keluarga)\s+yajamana\b(?!\s*\()", r"\1", answer, flags=re.I)
    # rule 6 forbids opening a sentence with it, the whole conversation being about Ngaben; it still
    # came ("Dalam konteks Ngaben, bhuta kala dianggap ...", Tier B 2026-10-05). Inside a sentence it
    # stays: the KB's own definitions say "dalam konteks Ngaben" there.
    answer = re.sub(r"(^|[.!?]\s+|\n\s*)Dalam konteks (?:upacara )?Ngaben,\s+(\w)",
                    lambda m: m.group(1) + m.group(2).upper(), answer, flags=re.I)
    # a lead that only says the rest matters: "Penting untuk dicatat bahwa Ngaben adalah kewajiban suci ..." (bot test
    # 2026-11-05); the clause after it stays
    # ("Penting untuk dipahami bahwa baik Ngaben yang sederhana ...", style test 2026-11-06)
    # (a list item's too: "- Penting dicatat bahwa harga tirtha bukan ukuran nilai spiritual", live run 2026-11-14)
    answer = re.sub(r"(^\s*(?:(?:\d+[.)]|[-*•])\s+)?|[.!?]\s+|\n\s*(?:(?:\d+[.)]|[-*•])\s+)?)"
                    r"(?:Yang\s+)?(?:Penting|Perlu|Patut)\s+(?:untuk\s+)?(?:dicatat|diingat|diketahui|"
                    r"diperhatikan|dipahami|disadari|digarisbawahi)(?:\s+juga)?(?:\s+adalah)?\s+bahwa\s+(\w)",
                    lambda m: m.group(1) + m.group(2).upper(), answer, flags=re.I)
    answer = _FIELD_LEAK_RE.sub("", answer).strip()
    # markdown emphasis shows as asterisks in a plain-text chat, and templates never use it: "1. **Pengawak:**
    # ...", "*Pabersihan Mati*" (NLU sweep 2026-10-19). A "* " list marker at a line's start becomes the bot's own "- "
    # ("*   Sampian" under canang sari's list, 2026-11-09).
    answer = re.sub(r"\*\*([^*\n]+?)\*\*", r"\1", answer)
    answer = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"\1", answer)
    answer = re.sub(r"(?m)^[ \t]*[*•][ \t]+", "- ", answer)
    # "Fakta yang tercatat mengenai lemat sudhamala adalah sebagai berikut:" talks of the prompt's facts; the
    # bot's own heading is "Yang tercatat tentang X:" (Tier B 2026-10-26; "Informasi yang tercatat ...", 2026-10-27)
    answer = re.sub(r"\b(?:fakta(?:-fakta)?|informasi) yang tercatat (?:mengenai|tentang) ([^:\n]+?)(?: adalah)?"
                    r"(?: sebagai berikut)?:", r"Yang tercatat tentang \1:", answer, flags=re.I)
    # ... and as a clause: "Fakta yang tercatat mengenai telur dalam daksina adalah bahwa daksina berisi telur itik.",
    # "Yang tercatat adalah bahwa Pasah adalah ...", "Basis data mencatat bahwa ngaben dapat dilakukan di krematorium" --
    # kept, they read as talk about the source; cut whole as unsupported, they took their fact along and left "Selain itu,
    # ..." under a bare miss (style test 2026-11-07)
    answer = _RECORDED_LEAD_RE.sub(_recorded_lead, answer)
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
# a coming date: "kapan ngaben massal berikutnya di denpasar?" got dewasa ngaben's whole rule set (style test 2026-11-07)
# -- no card holds a calendar of coming ceremonies (_schedule_miss)
_NEXT_EVENT_RE = re.compile(r"^(?!.*\b(?:setelah|sesudah|sebelum|abis|habis|usai)\b)(?=.*\b(?:kapan|tanggal\s+berapa|"
                            r"jadwal\w*)\b).*\b(?:berikut(?:nya)?|selanjutnya|mendatang|terdekat|"
                            r"(?:tahun|bulan|minggu)\s+(?:ini|depan))\b", re.I)
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
    # which one fits a situation is no list of every kind: "ngaben jenis apa yang cocok jika tidak memiliki banyak
    # uang?" got the nine kinds once "jika tidak memiliki" stopped reading as a consequence (style test 2026-11-06)
    ("fits", re.compile(r"\b(?:cocok|sesuai\s+(?:untuk|bagi|buat)|tepat\s+(?:untuk|bagi|buat)|sebaiknya|disarankan"
                        r"|dianjurkan|(?:bisa|dapat|boleh)\s+(?:di)?(?:ambil|pilih)|dipilih)\b", re.I)),
    # what someone does is their work, in the edges that name them: "apa yang dilakukan undagi?", read as tanya_waktu,
    # got "waktu undagi belum tersedia" (style test 2026-11-07). The term right after the verb ("· "), so "apa saja yang
    # dilakukan saat pabersihan" keeps its stages
    ("duty", re.compile(r"\bapa\s+(?:saja\s+|aja\s+)?yang\s+(?:di)?(?:lakukan|kerjakan)\s+(?:oleh\s+)?·", re.I)),
    # which one is the most so is no list of all: read as a kinds question it got the nine kinds of Ngaben
    ("superlative", re.compile(r"\bpaling\b", re.I)),
    # a coming date is no time a card gives (_schedule_miss)
    ("schedule", _NEXT_EVENT_RE),
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
# what something is put down as, a meaning that is also a purpose ("sebagai penegasan ... bahwa yadnya sudah selesai")
_SIGN_PURPOSE = r"sebagai (?:tanda|penanda|pertanda|penegasan|ungkapan|pernyataan)"
_SIGN_PURPOSE_RE = re.compile(rf"\b{_SIGN_PURPOSE}\b", re.I)
# who uses it, as its DIGUNAKAN_OLEH edges say: "siapa yang berperan dalam singa" got "Singa digunakan oleh pasek" alone,
# the card's "dipakai oleh kalangan raja-raja atau warga Pasek" left out (2026-11-14); and for whom among people (lembu
# "putih dipakai untuk pendeta (sulinggih), ... hitam untuk ... Ksatria", bade "lazimnya dipakai golongan berkasta lebih
# tinggi"). A sentence only these find gives its clause alone (_aspect_sentences).
_USE_DOER_MARKERS = (r"(?:dipakai|digunakan)\s+oleh"
                     r"|(?:dipakai|digunakan)\s+(?:untuk\s+)?(?:para\s+)?(?:pendeta|sulinggih|golongan|kasta|kalangan|"
                     r"wangsa|warga)")
_TEMPLATE_DEF_MARKERS = {
    **_FOCUS_MARKERS,
    # a person's duties: "apa tugas pemangku dalam ngaben" got "Maaf, fungsi atau tujuan pemangku belum tercatat"
    # above "Pemangku ... bertugas memimpin persembahyangan serta memohonkan tirtha" (2026-10-27)
    # (a duty, not "Saat bertugas ia berpijak pada padi": "Sangging untuk apa" got that, 2026-10-27)
    "fungsi": _FOCUS_MARKERS["fungsi"] + r"|bertugas\s+(?:untuk\s+)?me\w+|tugas(?:nya)?\s+(?:adalah|ialah|yaitu|me\w+)"
                                         r"|pihak yang"
              # what it is a means or a place for, said without "sebagai": "yeh panembak adalah sarana penyucian
              # jenazah", pelangkiran "..., tempat memuja roh leluhur" -- both got no purpose (bot test 2026-11-05)
              r"|(?:adalah|merupakan|yakni|ialah|menjadi)\s+(?:sarana|alat|media)\s+(?:untuk\s+)?pe[a-z]+"
              # (not a place phrase: ngulapin's "roh mendiang dipanggil di tempat meninggalnya")
              r"|(?<!di )(?<!ke )(?<!dari )tempat\s+(?:untuk\s+)?(?:me|ber)[a-z]{3,}"
              # what it is put somewhere to do, which is also its meaning: daksina "diletakkan di dada sawa ... sebagai
              # penegasan secara formal bahwa yadnya sudah selesai" -- "apa fungsi daksina?" got only where it is
              # used (style test 2026-11-06)
              r"|" + _SIGN_PURPOSE,
    # (a god "berstana di Pura Dalem": "letak Hyang Prajapati" got "tempat ... belum tercatat" above that very
    # sentence, NLU sweep 2026-10-19)
    # (and "ditaruh pada bibir jenazah", "diletakkan sebagai elemen utama di dalam kawangen", "alas pada pepaga":
    # pedangal, cermin kecil, bunga tunjung putih and tikeh plasa got "tempat ... belum tercatat" above their own
    # place, LLM comparison 2026-10-20)
    # ("pada" only after a verb of placing: "dilakukan pada tahap ini", "berada pada masa Daksinayana" are times)
    # (not "dibuat dari", a material: "baja itu di mana" got "Kikir dan lemat dibuat dari baja"; nor a "yang"
    # clause, which places the noun before it: uang kepeng's "lima dewa yang berada di kelima penjuru" answered
    # "lokasi uang kepeng di mana" -- sheet Failed, route audit 2026-10-27)
    # ("digelar di": "jenis-jenis lainnya digelar di arena khusus bernama Payadnyan", AYUTHAYA part B 2026-11-03)
    "lokasi": r"(?<!yang )(?:dilakukan|dilaksanakan|diadakan|digelar|diletakkan|ditempatkan|ditaruh|ditaruhkan|dipasang|"
              r"dimasukkan|disimpan|berada|disemayamkan|dibawa|dihanyutkan|diusung|dibaringkan|berstana|bersemayam|"
              # (the preposition as a word: "digelar pada hari ke-12" is a time; "berpusat di pura desa": ngusaba)
              r"terletak|bertempat|berpusat)\s+(?:[\w-]+\s+){0,3}?(?:di|ke|dari)(?=\s)"
              # (an offering's place, "dihaturkan di natah"; not "dihaturkan dalam periuknya ke hadapan atma": "di mana
              # ngliwet dilakukan" got its whole definition, AYUTHAYA part B 2026-11-04)
              r"|(?<!yang )dihaturkan\s+di(?=\s)"
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
              r"dihaturkan|dibawakan)\s+oleh|pemimpin|pemuput|" + _USE_DOER_MARKERS,
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
# ... and "berapa hari upacara ngaben dilakukan", which got "waktu ngaben belum tercatat" (conersation.md section IV,
# 2026-11-03) -- not a day counted from something ("berapa hari setelah kematian")
_DURATION_Q_RE = re.compile(r"\bberapa\s+lama\b|\blama(?:nya)?\s+(?:waktu|proses\w*|upacara\w*|pelaksanaan\w*)\b"
                            r"|\bdurasi\w*|\bmemakan\s+waktu\b|\bberlangsung\s+berapa\b"
                            r"|\bberapa\s+(?:hari|jam|minggu|bulan)\b(?![^.?!]*\b(?:setelah|sesudah|sebelum|sejak|"
                            r"menjelang|dari|ke)\b)", re.I)
_DURATION_IN_TEXT_RE = re.compile(r"\bselama\b|\bberlangsung\b|\blamanya\b|\bmemakan waktu\b|\b(?:\d+|satu|dua|tiga|"
                                  r"empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|beberapa)\s+(?:hari|malam|"
                                  r"jam|minggu|pekan|bulan|tahun)\b", re.I)


# how long after a death something is held: "berapa lama setelah meninggal ngaben harus dilakukan?"
_SINCE_DEATH_Q_RE = re.compile(r"\b(?:berapa\s+(?:lama|hari|minggu|bulan)|kapan|paling\s+lambat)\b[^.?!]*?"
                               r"\b(?:setelah|sesudah|sejak|dari)\s+(?:orang(?:nya)?\s+)?(?:meninggal|kematian|wafat|mati)\b"
                               r"|\b(?:setelah|sesudah|sejak)\s+(?:meninggal|kematian|wafat)\b[^.?!]*?"
                               r"\b(?:berapa\s+(?:lama|hari)|kapan)\b", re.I)
# a card's count of days from a death -- not the condition "dalam tujuh hari sejak kematian" of dewasa ngaben's rule
_DAYS_AFTER_DEATH_RE = re.compile(r"(?<!dalam\s)\b(?:paling\s+lambat\s+|sekitar\s+)?(?:\d+\s*-\s*\d+|\d+|satu|dua|tiga|"
                                  r"empat|lima|enam|tujuh|delapan|sembilan|sepuluh)\s+hari\s+(?:setelah|sesudah|sejak)\s+"
                                  r"(?:meninggal|kematian|wafat)\b", re.I)


def _since_death_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """How many days after a death Ngaben is held: the counts the cards state, by code. "berapa lama setelah meninggal
    ngaben harus dilakukan?" got krematorium's "prosesnya selesai dalam satu hari" as Ngaben's length, "berapa hari
    ngaben dilakukan setelah kematian?" "belum tersedia" -- while Piagam Campuhan says "sebisa mungkin paling lambat
    tujuh hari sejak kematian" and Sawa Wedana "3-7 hari setelah meninggal" (style test 2026-11-07)."""
    if not enriched or not _SINCE_DEATH_Q_RE.search(user_msg) or _whether_question(user_msg):
        return None
    content = get_content()
    e = enriched[0]
    if e["id"] != "ngaben" and not content.is_kind_of(e["id"], "ngaben"):
        return None
    rules, kinds = [], []
    for eid, definition in sorted(content.entity_def.items()):
        name = _card_cased(eid)
        for s in _sentences(definition):
            for part in re.split(r"[;:()]", s):
                part = part.strip().rstrip(".,")
                if not _DAYS_AFTER_DEATH_RE.search(part):
                    continue
                if re.match(r"(?:di|ber|me|ter)\w+\b", part, re.I):
                    kinds.append(f"{name[:1].upper()}{name[1:]} {part}.")
                else:
                    rules.append(f"Menurut {name}, {part}.")
    if not rules and not kinds:
        return None
    # what decides the day first, then the counts (the seven days of Piagam Campuhan need no dewasa)
    decided = " ".join(_time_decider_sentences(e))
    return (f"{decided} " if decided else "") + " ".join(rules + kinds)


def _duration_miss(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """How long the asked term takes, when nothing of its own -- its card, its text facts, its edges -- states a length
    of time: an honest miss by code. "berapa lama sih proses ngaben dari awal sampe selesai?" got "Proses Ngaben tidak
    memiliki durasi waktu (hari atau jam) yang tetap ... karena lamanya ... belum tercatat": no source says it has no
    fixed length (human test 2026-11-03)."""
    if (not enriched or not _DURATION_Q_RE.search(user_msg) or _whether_question(user_msg)
            or _SINCE_DEATH_Q_RE.search(user_msg)):
        return None
    e = enriched[0]
    own = [_definition_text(e)] + [str(f) for f in e.get("facts") or []] + [
        json.dumps({k: v for k, v in r.items() if k != "target_definition"}, ensure_ascii=False)
        for r in e.get("relationships") or [] if r.get("outgoing")]
    if any(_DURATION_IN_TEXT_RE.search(t) for t in own):
        return None
    # what a card linked to it says of how long it takes: ngaben's own length is recorded nowhere, but krematorium's
    # card (DIGUNAKAN_UNTUK ngaben) says "prosesnya selesai dalam satu hari" (L66); and what decides its time
    # ("berapa hari upacara ngaben dilakukan" quoted only the krematorium, AYUTHAYA part B, 2026-11-04)
    content = get_content()
    head = f"Maaf, lama pelaksanaan {e['name']} secara umum belum tercatat di basis data."
    decided = " ".join(_time_decider_sentences(e))
    linked = sorted({f["object_id"] for f in content.facts_by_subj.get(e["id"], [])}
                    | {f["subject_id"] for f in content.facts_by_obj.get(e["id"], [])})
    for lid in linked:
        clause = _PROCESS_DURATION_RE.search(content.best_definition(lid) or "")
        if clause:
            return (f"{head} {decided + ' ' if decided else ''}Yang tercatat tentang {content.entity_name[lid]}: "
                    f"{clause.group(0)}.")
    if decided:
        return f"{head} {decided}"
    return _template_miss("lama pelaksanaan", e)


def _time_decider_sentences(e: Dict[str, Any]) -> List[str]:
    """What decides when the term is held, said of it: "dewasa ngaben menentukan waktu pelaksanaan ngaben" ->
    "Waktu pelaksanaan ngaben ditentukan oleh dewasa ngaben, yaitu hari baik untuk melaksanakan Ngaben."."""
    content = get_content()
    out = []
    for r in e.get("relationships") or []:
        if r.get("relation") != "MENENTUKAN_WAKTU" or r.get("outgoing") or not r.get("target"):
            continue
        first = _first_sentence(content.best_definition(r.get("target_id")) or "", limit=400) or ""
        gloss = re.match(rf"\s*{re.escape(r['target'])}\s+adalah\s+(.+?)\.?\s*$", first, re.I)
        sentence = (f"Waktu pelaksanaan {e['name']} ditentukan oleh {r['target']}"
                    + (f", yaitu {gloss.group(1)}" if gloss else "") + ".")
        if sentence not in out:
            out.append(sentence)
    return out


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
    name = written.group(0) if written else e["name"]
    # (a name, capitalized: the card's 'Secara harfiah "nganyut" berarti ...' gave "Namanya nganyut.")
    return f"Namanya {name[:1].upper()}{name[1:]}. {lead}"


# "ngaben jenis apa itu?", "itu termasuk jenis apa?": which kind the thing just talked of is
_WHICH_KIND_Q_RE = re.compile(r"\b(?:jenis|macam)\s+apa\b", re.I)


def _which_kind_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """Which kind the case or topic is, when the message names its class and points back: that kind and its first
    sentence, by code. "ngaben jenis apa itu?" after "saudara saya hilang di laut dan jenazahnya tidak ditemukan" got
    "Jenis Ngaben Svasta yang tersedia adalah Tirta Yadnya Pranawa." -- the kinds of svasta (style test 2026-11-07)."""
    if (len(enriched) < 2 or not _WHICH_KIND_Q_RE.search(user_msg) or not _ANAPHOR_RE.search(user_msg)
            or _whether_question(user_msg)):
        return None
    content = get_content()
    kind, rest = enriched[0], enriched[1:]
    if not any(content.is_kind_of(kind["id"], c["id"]) and re.search(
            rf"(?<![\w-]){re.escape(c['name'])}(?![\w-])", user_msg, re.I) for c in rest):
        return None
    lead = _first_sentence(_deterministic_answer([dict(kind, aspect_facts=[])]) or kind.get("definition"), limit=500)
    return f"Itu termasuk {_card_cased(kind['id'])}." + (f" {lead}" if lead else "")


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
        known = _known_sentence(t.get("definition"), entity_id=t["id"], name=t["name"])
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
                           "dipake", "pake", "make", "memuput", "dipuput", "muput", "pemuput", "puput",
                           # to offer a sarana: "segehan dihaturkan di mana" went to the LLM, which made up why the
                           # places were chosen (Tier B on Qwen, AYUTHAYA part B, 2026-11-04)
                           "dihaturkan", "menghaturkan", "haturkan", "dipersembahkan", "persembahkan"})


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
    # "apa saja pura kahyangan tiga", read as tanya_kompleks by the plan #19 batch 2 model, went to Qwen; before the bare
    # term below, which took "apa saja tingkatan ngaben" for one ("apa saja" leaves no word) and gave the definition
    # (conersation.md section V, 2026-11-06)
    if not families and _KINDS_LIST_Q_RE.search(user_msg):
        return "tanya_jenis"
    # a bare term is a definition question, as nlu.yml's bare names are: the balinese-b3a-2026-10-29 retrain read
    # "patulangan" as tanya_kompleks, and it went to Qwen
    if not families:
        mentioned, leftover = _mentioned_terms(user_msg, get_resolver())
        if len(mentioned) == 1 and not leftover:
            return "tanya_definisi"
    # "setelah nyiramang layon apa?": which comes next (the waktu template's order facts)
    if not families and _NEXT_STAGE_RE.search(user_msg) and re.search(r"\bapa\b", user_msg, re.I):
        return "tanya_waktu"
    return None


# words a question with no aspect word may hold besides its term without asking for something else
_ASK_FILLER = _WHAT_IS_FILLER | frozenset({
    "saat", "pada", "ketika", "waktu", "dalam", "untuk", "buat", "dari", "ke", "di", "yang", "dan", "atau", "ya", "nih",
    "juga", "aja", "saja", "ini", "itu", "tersebut", "tadi", "lagi", "dong", "kah", "upacara", "acara", "ritual",
    "prosesi", "rangkaian", "penjelasan", "pengertian", "definisi", "arti", "maksud", "contoh", "lengkap", "detail",
    "singkat", "sebenarnya", "sebenernya", "bali", "hindu", "umat", "orang"})


@functools.lru_cache(maxsize=1)
def _intent_frame_words() -> Dict[str, frozenset]:
    """Each simple intent's own question words: the words of its frames and follow-ups in scripts/gen_nlu.py, the
    phrasings the NLU was trained on ("{t}" is where a name goes)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_nlu", Path(__file__).resolve().parent.parent / "scripts" / "gen_nlu.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return {intent: frozenset(_WORD_RE.findall(re.sub(r"\{\w+\}", " ", (frames + "\n" + "\n".join(
                gen.FOLLOW_UPS.get(intent, []))).lower())))
            for intent, frames in gen.FRAMES.items()}


def _asked_thing(leftover: List[str], intent: Optional[Text]) -> bool:
    """A noun the question asks for besides its term ("pakaian"): a word none of the intent's own phrasings use ("X
    termasuk kategori apa", "saya ingin tahu tentang X" are tanya_bagian_dari / tanya_definisi frames), no filler, no
    verb form, no aspect or pointing word."""
    frame = _intent_frame_words().get(intent or "", frozenset())
    return any(x not in frame and w not in frame and len(w) >= 3 and w not in _ASK_FILLER and w not in _STOPWORDS_ID
               and w not in _ASPECT_VOCAB and w not in _ELLIPSIS_VERBS and w not in _POINTER_WORDS
               and not _VERB_FORM_RE.match(w) and not re.match(r"(?:di|me|ber|ter|per)\w{4,}", w)
               and not w.endswith("kan")
               for x, w in ((x, re.sub(r"nya$", "", x)) for x in leftover))


# Words too generic to flag as an ungrounded asked thing: common time/manner/place
# words that appear beside a topic without being the question's subject.
_GENERIC_QUESTION_NOUNS = frozenset({
    "saat", "waktu", "masa", "kali", "hari", "cara", "tempat", "orang", "pihak",
    "kata", "nama", "lain", "umum", "awal", "akhir", "lainnya", "biasa", "asli",
    "bisa", "harus", "perlu", "wajib", "utama", "dasar", "kedua", "keduanya",
    "ketiga", "ketiganya", "keempat", "kelima", "semua", "semuanya", "masing-masing",
    "hal", "antara", "persamaan", "persamaannya", "kesamaan", "kesamaannya",
    "perbedaan", "perbedaannya", "beda", "bedanya", "hubungan", "hubungannya",
    "kaitan", "kaitannya",
})


# the thing a question asks for, by the question's shape: "apa (saja) X yang ...", "X apa (saja) yang ...", "X yang
# ... apa?" (X one word, before any KB name is reached)
_ASKED_THING_RES = (re.compile(r"^\W*(?:apa|apakah)\s+(?:saja\s+|aja\s+)?(\w+)\s+yang\b", re.I),
                    re.compile(r"^\W*(\w+)\s+apa\s+(?:saja\s+|aja\s+)?yang\b", re.I),
                    re.compile(r"^\W*(\w+)\s+yang\s+(?:di\w+|biasa\w*|harus\s+di\w+)\b.*\bapa(?:\s+saja|\s+aja)?\W*$", re.I))


def _ungrounded_asked_thing(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    """The thing a question asks for, by its shape (_ASKED_THING_RES), when it is no KB term and no word of the term's
    own context: 'pakaian' in "apa pakaian yang digunakan pada saat ngaben" / "pakaian yang digunakan pada saat ngaben
    apa", which got Ngaben's definition as if it answered (user, 2026-11-09: "make sure the bot says i dont know for a
    question it dont know the facts for"). Only that shape: any word missing from the card made "halo, keluarga
    saya ...", "pakai kikir?", "kalau purnama boleh?" and "ngaben itu intinya apa sih" an "informasi belum tersedia"
    over the right answer (snapshot 2026-11-12). None for anything else."""
    if not enriched or len(enriched) != 1:
        return None
    if _COMPARE_Q_RE.search(user_msg) or _RELATION_Q_RE.search(user_msg) or re.search(r"\bkeduanya\b", user_msg, re.I):
        return None
    heads = {m.group(1).lower() for rx in _ASKED_THING_RES for m in [rx.search(user_msg)] if m}
    if not heads:
        return None
    resolver = get_resolver()
    _, leftover = _mentioned_terms(user_msg, resolver)
    leftover = [w for w in leftover if w.lower() in heads]
    # the term's own card and edges, not the cards of everything around it: "pakaian" is in pabersihan mati's card
    # (the corpse's clothes), which says nothing of what is worn at a Ngaben
    vocab = set()
    for e in enriched:
        vocab |= _content_words(e.get("name")) | _content_words(e.get("definition"))
        for fact in (e.get("facts") or []) + (e.get("aspect_facts") or []):
            vocab |= _content_words(fact)
        for rel in e.get("relationships") or []:
            vocab |= _content_words(rel.get("target")) | _content_words(rel.get("statement"))
    entity_surfaces = {
        s.lower() for e in enriched
        for s in [e["name"]] + list(e.get("aliases") or []) + [e.get("asked_as") or "", e.get("typed_as") or ""]
        if s
    }
    for w in leftover:
        wl = w.lower()
        base = re.sub(r"nya$", "", wl)
        if (len(base) >= 4 and wl not in _STOPWORDS_ID and base not in _STOPWORDS_ID
                and wl not in _GENERIC_QUESTION_NOUNS and base not in _GENERIC_QUESTION_NOUNS
                and wl not in _META_TERMS and base not in _META_TERMS
                and wl not in _QUESTION_WORDS and base not in _QUESTION_WORDS
                and wl not in _ASPECT_VOCAB and base not in _ASPECT_VOCAB
                and wl not in _ASK_FILLER and base not in _ASK_FILLER
                and not _COMPARE_Q_RE.search(wl) and not _COMPARE_Q_RE.search(base)
                and not _RELATION_Q_RE.search(wl) and not _RELATION_Q_RE.search(base)
                and not re.match(r"^ke(?:dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh)", wl)
                and wl not in entity_surfaces and base not in entity_surfaces
                and not _VERB_FORM_RE.match(wl) and not re.match(r"(?:di|me|ber|ter|per)\w{4,}", wl)
                and not wl.endswith("kan")
                and not _grounded(wl, vocab) and not _grounded(base, vocab)):
            return wl
    return None


def _asked_thing_facts(thing: Text, e: Dict[str, Any], limit: int = 3) -> List[str]:
    """What e's stages, and theirs, say of an asked thing e's own card never names (_ungrounded_asked_thing): the
    sentences naming it as a word, stage by stage in order (each stage's own stages under it), their "Pada tahap ini"
    read as the stage's name. A card's defining first sentence only when no later sentence of any stage names it:
    memunjung's "... kain rantasan, pakaian pengganti untuk roh, ..." came along with how the corpse is dressed. At most
    `limit`."""
    content = get_content()
    word = re.compile(rf"(?<![\w-]){re.escape(thing)}(?![\w-])", re.I)
    later, first, seen = [], [], {e["id"]}

    def visit(x: Dict[str, Any], depth: int) -> None:
        for sid in _stage_ids(x):
            if sid in seen:
                continue
            seen.add(sid)
            definition = content.best_definition(sid) or ""
            # the name as the card's opening writes it ("Pabersihan Hidup"), else as its text does
            opening = re.match(rf"\s*({re.escape(content.entity_name.get(sid, ''))})\b", definition, re.I)
            name = opening.group(1) if opening and opening.group(1) else _card_cased(sid)
            sents = _sentences(definition)
            # (a sentence that does not name its stage gets it in front: "Jenazah dikenakan pakaian putih lengkap ..."
            # is Pabersihan Mati's)
            later.extend(re.sub(r"^(?:Pada|Dalam)\s+tahap\s+ini,?\s*", f"Pada {name}, ", s.strip())
                         if re.match(r"(?:Pada|Dalam)\s+tahap\s+ini\b", s.strip(), re.I) or name.lower() in s.lower()
                         else f"Pada {name}, {_decap(s.strip())}"
                         for s in sents[1:] if word.search(s))
            first.extend(s.strip() for s in sents[:1] if word.search(s))
            if depth < 2:
                visit({"id": sid, "relationships": _kb_relationships(sid)}, depth + 1)
    visit(e, 1)
    return _distinct_sentences(later or first)[:limit]


def _asked_thing_miss(thing: Text, e: Dict[str, Any]) -> str:
    """The miss for an asked thing e's own card never names, with what e's stages record of it as the closest fact:
    "pakaian apa yang dipakai saat ngaben?" said only that it is not recorded, though Pabersihan Hidup and Pabersihan
    Mati record how the corpse is dressed (Claude's review, L4, 2026-11-13; what mourners wear stays unrecorded, the user
    2026-11-09: "make sure the bot says i dont know"). Else e's own first sentence, as before."""
    facts = _asked_thing_facts(thing, e)
    if not facts:
        return _template_miss(f"informasi tentang {thing} pada", e)
    return (f"Maaf, informasi tentang {thing} pada {e['name']} belum tercatat di basis data. "
            f"Yang tercatat tentang {thing} dalam {_card_cased(e['id'])}: " + " ".join(facts))


def _template_route(user_msg: Text, intent: Optional[Text], current_entity: Optional[Text],
                    resolver) -> "tuple[Optional[str], str]":
    """(family, "") when the message is a simple question its intent's template answers, else
    (None, why not). Checked on the message alone, before the graph is asked."""
    if intent not in _TEMPLATE_INTENTS:
        return None, f"intent {intent}"
    # a message that asks nothing asks no aspect: "kak aku lagi bikin tugas soal ngaben nih" read "tugas" as a duty and
    # got Ngaben's purposes (style test 2026-11-06); the pipeline answers it with an invitation or the told case
    if _tells_only(user_msg):
        return None, "tells only"
    family = _TEMPLATE_INTENTS[intent]
    mentioned, leftover = _mentioned_terms(user_msg, resolver)
    if len(mentioned) > 1:
        return None, "two or more terms"
    # the shapes are read without the term's own names: "pura kahyangan tiga" holds a number. Not
    # without the surface the scan matched, which can take the asked tier along ("bade tingkat 9")
    rest = user_msg
    for m, _ in mentioned:
        for n in sorted([m.name] + list(m.entity.get("aliases") or []), key=len, reverse=True):
            # a mark, not a space: "pada saat ngaben apa" read as "saat apa", a time question, and "pakaian yang
            # digunakan pada saat ngaben apa" got "Ngaben dilakukan sebelum atma wedana ..." (conersation.md
            # section IV, 2026-11-03)
            rest = re.sub(rf"(?<![\w-]){re.escape(n)}(?![\w-])", " · ", rest, flags=re.I)
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
    # (a death the message tells or asks about names Ngaben, as _message_terms reads it: "nenek saya meninggal minggu
    # lalu, apa yang harus disiapkan?" went to Qwen, which listed every stage's sarana up to its token limit, while "apa
    # yang harus disiapkan untuk ngaben?" gets the sarana template -- Tier B 2026-11-13)
    if not mentioned and not (current_entity and (
            _ANAPHOR_RE.search(resolver.clean_query(user_msg)) or not leftover
            or set(leftover) - _ELLIPSIS_MODALS <= _ELLIPSIS_VERBS) or _death_case(user_msg)):
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
    # "setelah ngaben, upacara apa lagi?" asks which rite comes next, whatever aspect the intent guessed: read as
    # tanya_sebutan_lain it got "Ngaben juga dikenal sebagai mreteka sawa, ..."; "setelah itu apa?" holds "itu apa" and got
    # the topic's definition (style test 2026-11-06). Spoken too, right before the term: "abis ngaben ngapain lagi" went
    # to the LLM as tanya_sebutan_lain and got "Atma Wedana ... memberikan persembahan kepada atma" (style test 2026-11-07)
    if (re.search(r"\b(?:setelah|sesudah|sebelum)\b|\b(?:sehabis|usai|abis|habis)\s+·", rest, re.I)
            and re.search(r"\b(?:apa|ngapain|ngapa)\b", rest, re.I) and not set(families) - {"waktu", "tahapan"}):
        return "waktu", ""
    # (a definition intent too: NLU read "apa saja tingkatannya?" as tanya_definisi, section V 2026-11-06)
    if family in ("", "sarana", "lokasi", "waktu", "fungsi", "simbol") and not families and _KINDS_LIST_Q_RE.search(rest):
        return "jenis", ""
    # a what-is shape with no aspect word is the definition whatever the intent says -- also over a
    # tanya_asal_kata misread: "apa itu dewata nawa sanga" went to the LLM (live, 2026-10-15)
    if not families and not word_meaning and _WHAT_IS_SHAPE_RE.search(rest):
        return "", ""
    # with no aspect word the intent decides -- unless the question asks for a thing no template gives: "pakaian yang
    # digunakan pada saat ngaben apa", read as tanya_waktu, got ngaben's order (conersation.md section IV, 2026-11-03)
    if not families and not word_meaning and _asked_thing(leftover, intent):
        return None, "asked thing"
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
    return _cut_gloss(_decap(s), limit)


def _cut_gloss(s: Text, limit: int = 220) -> str:
    """A gloss at most `limit` long, ending at a clause boundary rather than mid-clause with "...", where it can."""
    if len(s) > limit:
        ends = [x.start() for x in _CLAUSE_END_RE.finditer(s, 0, limit) if x.start() >= 40]
        if not ends:
            # else a comma outside brackets between two phrases of their own (4+ words each -- not a list's items, and
            # not before "yaitu", whose gloss is the point, nor "dan"): "Mamutru: acara membaca Lontar Putru, ... (apa
            # yang dijumpainya, ...), pada hari Pabersihan dalam rangkaian ..." ended mid-phrase with "..." (style test
            # 2026-11-07)
            depth, cuts = 0, [-1]
            for i, ch in enumerate(s):
                depth += (ch == "(") - (ch == ")")
                if ch == "," and depth == 0:
                    cuts.append(i)
            cuts.append(len(s))
            ends = [c for j, c in enumerate(cuts[1:-1], 1)
                    if 60 <= c < limit and len(s[cuts[j - 1] + 1:c].split()) >= 4
                    and len(s[c + 1:cuts[j + 1]].split()) >= 4
                    and not re.match(r"\s*(?:yaitu|yakni|ialah|adalah|berupa|dan|atau|serta)\b", s[c + 1:], re.I)][-1:]
        s = s[:ends[-1]].rstrip(" ,;:") if ends else s[:limit].rsplit(" ", 1)[0] + " ..."
    return s if not s or s.endswith(("...", ".", "!", "?")) else s + "."


def _sibling_glosses(ids: List[str], limit: int = 220) -> Dict[str, str]:
    """Each kind's gloss without the opening clause all of them share: nista, madya and utama each open "salah satu
    dari tiga jalan pokok tingkatan upacara Ngaben (nista, madya, utama);", and the list said nothing else
    (conersation.md section V, 2026-11-06)."""
    full = {i: _gloss(i, limit=10 ** 6) for i in ids}

    def opening(gloss: Text) -> str:
        m = re.match(r"[^;]{20,};\s+", gloss)
        return m.group(0) if m else ""
    heads = {opening(g) for g in full.values()}
    if len(ids) >= 2 and len(heads) == 1 and next(iter(heads)):
        head = next(iter(heads))
        full = {i: _decap(g[len(head):]) for i, g in full.items()}
    return {i: _cut_gloss(g.rstrip("."), limit) if g else g for i, g in full.items()}


def _class_sense_gloss(kind_id: Text, class_id: Text, limit: int = 220) -> Optional[str]:
    """A kind's gloss in its class's list when its card's first sentence is about another sense: "apa aja jenis
    usungan" listed "Padmasana: bangunan suci (pelinggih) untuk memuja Ida Sang Hyang Widhi Wasa ..." -- the shrine --
    while its card's next sentence says that in Ngaben it is also a form of usungan, for a priest's corpse (sweep
    2026-11-13). The card's sentence with the kind as subject that names the class, from its predicate on; None when the
    first sentence names the class already or no sentence does."""
    content = get_content()
    name = content.entity_name.get(kind_id, "")
    surfaces = {content.entity_name.get(class_id, "")} | {s for s in _surfaces_by_id().get(class_id, ())}
    class_rx = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(s) for s in sorted(surfaces, key=len, reverse=True) if s)
                          + r")(?![\w-])", re.I)
    sentences = _sentences(content.best_definition(kind_id) or "")
    if not name or not sentences or class_rx.search(sentences[0]):
        return None
    for s in sentences[1:]:
        m = re.match(rf"\s*(?:dalam\s+[^,]{{1,60}},\s*)?{re.escape(name)}\s+(?:juga\s+)?(?:menjadi|merupakan|adalah|"
                     rf"termasuk)\s+(?:juga\s+)?", s, re.I)
        if m and class_rx.search(s):
            return re.sub(r":\s+", "; ", _cut_gloss(s[m.end():].rstrip("."), limit))
    return None


def _in_card_order(parent_id: Text, ids: List[str], before: Optional[List[str]] = None) -> List[str]:
    """Kinds in the order the parent's card names them ("Tingkatan upacara (nista, madya, utama)"), the rest after in
    their own order; with `before` (the names of the level above, in order), a kind named after one of them goes where
    it goes: nistaning nista, madyaning nista, utamaning nista (corpus L1027), not alphabetically."""
    content = get_content()
    card = (content.best_definition(parent_id) or "").lower()

    def key(i: str):
        name = content.entity_name.get(i, i).lower()
        m = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", card)
        led = next((n for n, b in enumerate(before or []) if name.startswith(b)), len(before or []))
        return (m.start() if m else len(card) + 1, led)
    return sorted(ids, key=key)


def _meaning_gloss(entity_id: Optional[str]) -> str:
    """_gloss for 'Kata "x" berarti <gloss>': without a leading "berarti" of its own ("Mala berarti kotor ..." gave
    'Kata "mala" berarti berarti kotor', plan #19 batch 2)."""
    return re.sub(r"^berarti\s+", "", _gloss(entity_id), flags=re.I)


def _list_item(entity_id: Text) -> str:
    """"Asti wedana: jenis Ngaben berupa ..." -- a kind, stage or member in a list, with its gloss."""
    name = get_content().entity_name.get(entity_id, entity_id)
    g = _gloss(entity_id)
    return f"{name[:1].upper()}{name[1:]}" + (f": {g}" if g else "")


# what a numbered stage list says already: a stage's place ("tahap keempat upacara Nyiramang Layon", ", bersama Ngeringkes
# merupakan tahap kedua dari delapan tahapan ..."), and what it comes after ("sesudah nedunan layon, ...")
_STAGE_PLACE_RE = re.compile(
    r"(?:^|,\s*(?:dan\s+)?)(?:bersama\s+[\w\s]+?\s+merupakan\s+)?(?:salah\s+satu\s+)?tahap(?:an)?\s+(?:ke-?\d+|pertama|kedua|"
    r"ketiga|keempat|kelima|keenam|ketujuh|kedelapan|kesembilan|kesepuluh|terakhir)\b[^,;:]*?(?=\s*[,;:]|\s+yaitu\b|$)",
    re.I)
_STAGE_AFTER_LEAD_RE = re.compile(r"^(?:(?:dilaksanakan|dilakukan)\s+)?(?:sesudah|setelah)\s+[^,;:]*?(?:[,;:]\s*|\s+dan\s+(?=me[a-z]))",
                                  re.I)
_WORD_MEANING_LEAD_RE = re.compile(r"^(?:secara\s+harfiah\s+)?(?:\"[^\"]+\"\s+)?berarti\s+(?:\"[^\"]*\"|[^;]*?)(?:\s*;\s*|$)",
                                   re.I)


def _stage_gloss(entity_id: Text, limit: int = 220) -> str:
    """A step's gloss in a numbered stage list: what it is or does, not its place in the list the number already gives
    ("Pabersihan mati: tahap keempat upacara Nyiramang Layon, dan tahap kedua penyucian jenazah ...") nor what its name
    means ("Nganyut: berarti menghanyutkan ...") -- sweep 2026-11-13. The first card sentence left with something else to
    say (subject taken off as _gloss does), else the gloss in the name's own bracket ("Nedunan layon (menurunkan
    jenazah) adalah tahap pertama ..."), else nothing."""
    content = get_content()
    name = content.entity_name.get(entity_id, "")
    bracket = ""
    for i, s in enumerate(_sentences(content.best_definition(entity_id) or "")):
        m = _definition_subject(s.rstrip("."), entity_id, name) if name else None
        if not m and i:
            # a later sentence about something else ("Urutannya: ...", "Sesudahnya dilakukan ...")
            continue
        if m and not bracket:
            # (a gloss, not another name: "(menurunkan jenazah)", not "(Mapepegat)" or "(pebersihan atau ...)")
            b = re.match(r"\s*\(([^)]*)\)", s.rstrip(".")[m.end(1):])
            if b and len(b.group(1).split()) >= 2 and not re.search(r"\b(?:disebut|juga|atau)\b|,", b.group(1), re.I):
                bracket = b.group(1)
        # (a first sentence with no subject of its own is the gloss itself, as _gloss reads it: ngaben's "Upacara
        # pembakaran jenazah ...")
        g = _WORD_MEANING_LEAD_RE.sub("", s.rstrip(".")[m.end() if m else 0:].strip())
        g = _STAGE_PLACE_RE.sub("", g).strip()
        g = re.sub(r"^[,;:]\s*(?:(?:yaitu|yakni)\s+)?|^(?:yaitu|yakni)\s+", "", g).strip()
        # ("tahap kedelapan dalam Ngarga Tirtha, yang terakhir, sesudah ...: Ida Sang Sulinggih memohon ...")
        g = re.sub(r"^(?:yang\s+)?terakhir\s*,?\s*", "", g, flags=re.I)
        g = _STAGE_AFTER_LEAD_RE.sub("", g).strip()
        if len(_WORD_RE.findall(g)) >= 2:
            # (the item's own colon is the only one: "Ngulapin: ritual pemanggilan roh: roh mendiang dipanggil ...")
            return re.sub(r":\s+", "; ", _cut_gloss(_decap(g), limit))
    return f"{bracket}." if bracket else ""


def _inside_stages(stage_id: Text, shown: List[Text], depth: int = 3) -> bool:
    """Whether the stage is a part of one of the shown stages (BAGIAN_DARI, up to `depth` levels): an ordered list's
    "Selain itu, rangkaian ngaben juga mencakup ..." named 13 more, pabersihan mati among them -- a stage of nyiramang
    layon, item 2 (sweep 2026-11-13)."""
    content = get_content()
    level = {stage_id}
    for _ in range(depth):
        level = {f["object_id"] for s in level for f in content.facts_by_subj.get(s, []) if f["predicate"] == "BAGIAN_DARI"}
        if level & set(shown):
            return True
        if not level:
            return False
    return False


def _stage_item(entity_id: Text) -> str:
    """_list_item for a numbered stage list (_stage_gloss)."""
    name = get_content().entity_name.get(entity_id, entity_id)
    g = _stage_gloss(entity_id)
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


def _without_other_names(sentence: Text) -> Text:
    """A definition sentence without its list of other names, which answers no aspect and reads as clutter outside a
    definition: "apa tujuan atma wedana" got "Atma Wedana (disebut juga Ngroras atau Ngerorasin, Pangroras, Patileman,
    Nyekah, atau Pitra Yadnya tahap kedua) adalah ..." (bot test 2026-11-05)."""
    return re.sub(r"\s*\((?:disebut|dikenal)\s+juga[^)]*\)", "", sentence)


_PURPOSE_FRAME_ROOTS = frozenset(_ortho_key(_root(w)) for w in ("bertujuan", "tujuan", "berfungsi", "fungsi"))


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
        # (a purpose word is the predicate's, not the fact's: "Damar kurung bertujuan agar keletehan ... diblokir terbatas,
        # hanya sebatas tanah pekarangan keluarga mendiang" said again the definition's "... agar keletehan ... terbatas
        # hanya sebatas pekarangan keluarga mendiang", bot test 2026-11-05)
        roots = _fact_roots(body) - _PURPOSE_FRAME_ROOTS
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


def _head_time_sentence(sentence: Text, name: Text, marker_rx) -> Optional[str]:
    """"Mamukur (Memukur) adalah tingkatan upacara Atma Wedana, penyucian roh leluhur lanjutan setelah ngaben yang
    bertujuan ..." -> "Mamukur dilakukan setelah ngaben.": the time phrase of the term's own "adalah" sentence, when
    the sentence dates it there, in its head (as _dates_the_term reads it)."""
    m = marker_rx.search(sentence)
    # (a time word that opens a clause needs all of it: "ketika bayi yang tali pusatnya sudah lepas meninggal" came out
    # "Ngeluhurang bhatara kumara dilakukan ketika bayi.")
    if (not m or re.match(r"(?:saat|ketika|selama)\b", m.group(0), re.I)
            or not re.match(rf"\s*{re.escape(name)}(?![\w-])", sentence, re.I)):
        return None
    head = re.match(r"[^.;:]*?\badalah\b([^.;:]*)$", sentence[:m.start()], re.I)
    # (a time already in the head is the time: manah tirtha ening "adalah acara pada awal hari Pabersihan, ketika
    # keluarga ... memanah air ening" -- the phrase from "ketika" lost the day; so is a stage's number, and a gloss's
    # phrase is the gloss's: nuduk galih "adalah tahap keenam ..., yaitu pengumpulan ... abu setelah pembakaran
    # jenazah" came out "dilakukan setelah pabasmian dan pembakaran jenazah")
    if (not head or re.search(r"\byang\b|\b(?:me|ber|di)[a-z]{3,}\b", head.group(1), re.I)
            or re.search(r"\b(?:pada|hari|malam|pagi|siang|sore|awal|akhir|puncak|tahap\s+ke\w*|pertama|terakhir|"
                         r"urutan|yaitu|yakni|ialah)\b", head.group(1), re.I)):
        return None
    phrase = re.match(r"[^,;:()]+?(?=\s+(?:yang|untuk|bertujuan|dengan|agar|guna|sebagai)\b|\s*[,;:()]|\s+--\s|\s*\.?\s*$)",
                      sentence[m.start():], re.I)
    if not phrase:
        return None
    return f"{name[:1].upper()}{name[1:]} dilakukan {phrase.group(0).strip()}."


# where a definition sentence may be cut into the parts that state the asked aspect: a ";" outside brackets, and ", dan /
# tetapi / namun / sedangkan" before a clause pointing back at the term ("..., dan upacara ini memang sering digelar ...")
_ASPECT_CLAUSE_SPLIT_RE = re.compile(r";\s+|,\s+(?:dan|tetapi|namun|sedangkan)\s+(?=(?:upacara|acara|tahap(?:an)?|ritual|"
                                     r"sarana|benda|banten|tirtha)\s+(?:ini|tersebut)\b)", re.I)
_CLAUSE_LEAD_RE = re.compile(r"^(?:karena\s+itu(?:lah)?|oleh\s+karena\s+itu|maka|sehingga|dan|lalu|kemudian),?\s+", re.I)


def _aspect_clauses(sentence: Text, states, e: Dict[str, Any]) -> str:
    """Of a definition sentence an aspect template quotes, the clauses that state the aspect (`states`): "atma wedana
    dipakai kapan" got the whole card -- what it purifies, why Ngaben leaves the soul a pitra, where the name Ngroras
    comes from -- because each sentence held a time somewhere (sweep 2026-11-13). A clause after the first is kept only
    when it names the term or points at it ("upacara ini ..."). The sentence as it stands when every clause, or none,
    states the aspect."""
    cuts, last = [], 0
    for m in _ASPECT_CLAUSE_SPLIT_RE.finditer(sentence):
        if sentence.count("(", 0, m.start()) == sentence.count(")", 0, m.start()):
            cuts.append(sentence[last:m.start()])
            last = m.end()
    if not cuts:
        return sentence
    clauses = cuts + [sentence[last:]]
    names = [e["name"]] + list(e.get("aliases") or [])
    names_rx = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in names if n) + r")(?![\w-])", re.I)
    kept = []
    for i, c in enumerate(clauses):
        c = c.strip().rstrip(".")
        if not states(c):
            continue
        # (a "juga" leaning on a clause left out keeps the sentence whole: "saat apa sesajen digunakan" kept only "Pada
        # upacara untuk jenazah bayi, sesajen juga ditujukan kepada ..." -- snapshot 2026-11-13)
        if i and len(kept) < i and re.search(r"\bjuga\b", c, re.I):
            return sentence
        if i:
            c = _CLAUSE_LEAD_RE.sub("", c)
            if not (names_rx.search(c) or re.match(r"(?:upacara|acara|tahap(?:an)?|ritual|sarana|benda|banten|tirtha)\s+"
                                                    r"(?:ini|tersebut)\b", c, re.I)):
                continue
        kept.append(f"{c[:1].upper()}{c[1:]}.")
    if not kept or len(kept) == len(clauses):
        return sentence
    return " ".join(kept)


def _aspect_sentences(e: Dict[str, Any], family: str, with_definition: bool = True,
                      with_edges: bool = True, skip: frozenset = frozenset()) -> List[str]:
    """What the KB states about e's aspect: its definition's sentences that state it, the text-only
    facts of the family, then its edges (`with_edges`); none of the predicates in `skip`."""
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
        # (a time or a place only: a purpose, meaning or doer marker is no clause test -- "apa makna dari prosesi
        # mapepegat?" kept 'Mapegat berarti "memutuskan"' and lost "... bermakna krusial untuk memutus ikatan ...",
        # "yang mimpin pemangku siapa" became a miss; snapshot 2026-11-13)
        if not calendar and family in ("waktu", "lokasi"):
            stated = [_aspect_clauses(s, (lambda c: _dates_the_term(c, rx)) if family == "waktu"
                                      else (lambda c: bool(rx.search(_VAGUE_ASPECT_RE.sub("", c)))), e)
                      for s in stated]
        # a sentence taken out of its definition names the term it points back to: "di mana nyiramang layon
        # dilakukan" was answered "Upacara ini biasanya dilakukan di natah ..." (AYUTHAYA part B, 2026-11-04)
        title = e["name"][:1].upper() + e["name"][1:]
        stated = [re.sub(r"^(?:Upacara|Acara|Ritual|Tahap(?:an)?)\s+(?:ini|tersebut)\b", title, s) for s in stated]
        stated = [_without_other_names(s) for s in stated]
        if family == "pelaku":
            # a sentence of the card about another card is no doer of the term: bade's "Wadah, yaitu usungan tanpa
            # badawang nala, lazimnya dipakai oleh warga ..." answered "siapa yang menggunakan bade" (2026-11-14)
            resolver = get_resolver()

            def other_subject(s: Text) -> bool:
                m = re.match(r"\s*((?:[\w-]+\s+){0,3}?[\w-]+?)(?=,|\s+(?:yaitu|adalah|merupakan|lazimnya|umumnya|"
                             r"biasanya|dipakai|digunakan|dilakukan|dipimpin|dibuat)\b)", s)
                hit = resolver.resolve(m.group(1)) if m else None
                return bool(hit and hit.via in ("exact", "alias") and hit.id != e["id"])
            stated = [s for s in stated if not other_subject(s)]
            # who uses it is one clause of a card sentence: "wadah dilakukan oleh siapa" got wadah's whole definition
            # for its "...; wadah dipakai oleh suatu warga (klan), dan jumlah tingkatnya ..." (2026-11-14)
            use_rx = re.compile(rf"\b(?:{_USE_DOER_MARKERS})\b", re.I)
            doer_rx = re.compile(rf"\b(?:{marker.replace(_USE_DOER_MARKERS, '(?!)')})\b", re.I)
            stated = [_aspect_clauses(s, lambda c: bool(use_rx.search(c)), e)
                      if use_rx.search(s) and not doer_rx.search(s) else s for s in stated]
        if family == "waktu" and not calendar and content.entity_type.get(e["id"]) in _STAGE_TYPES:
            # a rite its own "adalah" sentence dates in a phrase: the phrase, not the definition again -- "kapan
            # dilakukan?" after "apa itu mamukur" got the definition word for word (bot test 2026-11-05)
            stated = [_head_time_sentence(s, e["name"], rx) or s for s in stated]
    if family == "pelaku":
        # who does or makes it is a person, not a rite ("Sekah ... dibuat oleh ngajum"; "atma wedana dilakukan
        # oleh siapa" got "ngajum membuat sekah" from a stage), and what the term itself makes is no doer of it
        e = dict(e, relationships=[
            r for r in e.get("relationships") or []
            if r.get("relation") not in _AGENT_SUBJECT_PREDICATES
            or (not r.get("outgoing") and content.entity_type.get(r.get("target_id")) not in _STAGE_TYPES)])
    # a sign something is put down as comes after what the card says the term is for: ngangkid opened with the uang
    # kepeng held "sebagai ungkapan bahwa semua keluarga siap ..." above "Ngangkid bertujuan ..." (card run 2026-11-06)
    signs = ([s for s in stated if not re.search(rf"\b(?:{marker})\b", _SIGN_PURPOSE_RE.sub(" ", s), re.I)]
             if family == "fungsi" and marker and family not in _EDGES_FIRST_FAMILIES else [])
    if family not in _EDGES_FIRST_FAMILIES:
        found += [s for s in stated if s not in signs]
    preds = PREDICATE_FAMILIES[family] - _NOT_ANSWERING.get(family, set()) - skip
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
    if family == "fungsi" and with_edges:
        # what it is used on: "sawa disiram dengan yeh panembak" answers "yeh panembak dipakai untuk apa", which got
        # its card's first sentence and "Yeh panembak juga digunakan pada ngaben" (bot test 2026-11-05)
        edges += _edge_sentences(e, _USED_WITH_PREDICATES, _USED_WITH_PREDICATES, outgoing=False, with_targets=True)
    # an edge one definition sentence of the answer says in full goes: "Ngliwet dilakukan setelah pralina." above
    # "... sesudah amariaran dan pralina: ..." (2026-10-15); its targets named by any surface: "Tikeh plasa juga
    # digunakan dalam nyiramang layon dan pangringkes" below "... tempat Nyiramang Layon dan ... saat ngeringkes"
    named = [_named_in(d) for d in stated] if edges else []
    edges = [s for s, targets in edges if not any(all(t.lower() in n for t in targets) for n in named)]
    if family in _EDGES_FIRST_FAMILIES:
        found += edges + stated
    else:
        found += signs + edges
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
        # (nor a subject shared with another: "Bade dan lembu lazimnya dipakai ..." joined as "Bade dibuat oleh undagi
        # dan dan lembu lazimnya dipakai ...", 2026-11-14)
        if (not m or re.search(r"[;:]|\.\s", pred) or len(words) > 12
                or words[0].lower() in {"adalah", "ialah", "yaitu", "juga", "dan", "serta", "atau"}):
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
    known = (_named_definition(_definition_text(e), e["id"], name) if whole and _definition_text(e)
             else _known_sentence(e.get("definition"), entity_id=e["id"], name=name))
    return (f"Maaf, {label} {name} belum tercatat di basis data."
            + (f" Yang tercatat tentang {name}: {known}" if known else ""))


def _parts_word(e: Dict[str, Any]) -> str:
    """What e's recorded parts are called: "tahapan" when most are stages, else "bagian-bagian" -- pitra yadnya's are
    mostly rites (mapendem, nyekeh, ngaben titip), which "tahapannya" called its stages (AYUTHAYA part B, 2026-11-04)."""
    content = get_content()
    ids = _stage_ids(e)
    stages = sum(content.entity_type.get(i) == "TAHAPAN_UPACARA" for i in ids)
    return "tahapan" if stages * 2 > len(ids) else "bagian-bagian"


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
    clause of a definition sentence with its term as subject; a place it is for, "Pelangkiran adalah pelinggih ...,
    tempat memuja roh leluhur ..." -> "Pelangkiran berfungsi sebagai tempat memuja roh leluhur ..." (bot test
    2026-11-05). Other sentences as they are."""
    # (and a place something is put in: bade "..., tempat jenazah diletakkan saat diarak menuju setra" -- "terus
    # fungsinya apa?" after "apa itu bade?" got the definition's first sentence again, sweep 2026-11-13)
    m = re.match(rf"\s*({re.escape(name)})\s+(?:\([^)]*\)\s+)?adalah\b[^.;:]*?,\s*((?:bertujuan|berfungsi)\b.*"
                 r"|tempat\s+(?:untuk\s+)?(?:me|ber)[a-z]{3,}\b.*|tempat\s+[a-z]+(?:\s+[a-z]+)?\s+di[a-z]{3,}\b.*)$",
                 sentence, re.I | re.S)
    if not m:
        return sentence
    return f"{m.group(1)} {'berfungsi sebagai ' if m.group(2)[:6].lower() == 'tempat' else ''}{m.group(2)}"


def _parent_aspect(e: Dict[str, Any], family: str, act: Optional[tuple], kinds_only: bool = False) -> Optional[str]:
    """A stage with no place or doer of its own: the nearest rite it is part of that has one, said as that rite's
    (the AYUTHAYA change, 2026-11-03: "make sure the location where a certain ceremony is held is available", "who is
    involved and leading ... for every ceremony"). "di mana nedunan layon dilaksanakan" got "tempat ... belum tercatat"
    though nyiramang layon, which it is the first step of, is held in the natah. Not for a time: a stage's time is not
    its rite's."""
    if act and act[0] == "pembuat":
        # who makes a stage is no maker its rite records: "siapa yang membuat pabersihan mati" got ngaben's list of
        # participants for its "undagi, pembuat bade" (AYUTHAYA part B review, 2026-11-04)
        return None
    content = get_content()
    name = e["name"]
    # what the term is of the rite: a stage of it, a kind of it (asti wedana is a kind of ngaben), or another name of
    # it (malebuang is ngaben's refined name)
    # (`kinds_only`, for a meaning or purpose: a kind or another name shares its rite's, a stage has its own)
    how_of = {"TERMASUK_JENIS": "salah satu jenis",
              **{p: "sebutan lain untuk" for p in PREDICATE_FAMILIES["sebutan_lain"] - {"ADALAH"}}}
    if not kinds_only:
        how_of["BAGIAN_DARI"] = "bagian dari"
    seen, frontier = {e["id"]}, [e["id"]]
    relation_to: Dict[str, str] = {}
    via_kind: set = set()   # the rites reached through a kind link
    for _ in range(3):
        parents = []
        for sid in frontier:
            # the broader spine's kind parents are no relation rows: they are in kind_parents
            # (another name goes both ways: "ngaben dikenal sebagai atiwa-tiwa" makes atiwa-tiwa ngaben's too)
            links = ([(r.get("relation"), r.get("target_id")) for r in _kb_relationships(sid)
                      if r.get("outgoing") or (r.get("relation") in how_of and how_of[r["relation"]] == "sebutan lain untuk")]
                     + [("TERMASUK_JENIS", k) for k in sorted(content.kind_parents.get(sid, ()))])
            for rel, pid in links:
                if rel in how_of and pid not in seen and content.entity_type.get(pid) in _STAGE_TYPES:
                    seen.add(pid)
                    parents.append(pid)
                    relation_to.setdefault(pid, how_of[rel] if sid == e["id"] else "bagian dari")
                    if rel == "TERMASUK_JENIS" or sid in via_kind:
                        via_kind.add(pid)
        # the nearest rite first: pangringkes is part of nyiramang layon and of ngaben, and nyiramang layon is part
        # of ngaben -- "siapa yang memimpin pangringkes" got "Ngaben dipimpin oleh sulinggih" (AYUTHAYA part B review,
        # 2026-11-04)
        level = set(parents)
        inside = {pid: {r.get("target_id") for r in _kb_relationships(pid)
                        if r.get("relation") == "BAGIAN_DARI" and r.get("outgoing")} for pid in parents}
        parents.sort(key=lambda pid: -len(inside[pid] & level))
        for pid in parents:
            p = {"id": pid, "name": content.entity_name[pid], "definition": content.best_definition(pid),
                 "relationships": _kb_relationships(pid)}
            said = _aspect_sentences(p, family)
            if family == "lokasi":
                # a place the rite may be held in is no place of its stages: "Ngaben dapat dilakukan di krematorium"
                # answered where ngulapin and nyegara gunung are held
                said = [s for s in said if not re.search(r"\bdapat\s+dilakukan\s+di\b", s, re.I)]
            if family == "pelaku" and act:
                said = [s for s in said if act[1].search(s)] or (said if act[0] == "pemimpin" else [])
            if family == "pelaku":
                if pid in via_kind:
                    # a kind shares its rite's leader, not who takes part: "siapa saja yang terlibat dalam upacara
                    # ngelungah", a baby's rite, got ngaben's krama banjar, undagi and bade (AYUTHAYA part B review)
                    said = [s for s in said if _LEAD_ACT_RE.search(s)]
                said = sorted(said, key=lambda s: not _LEAD_ACT_RE.search(s))   # who leads first
            if said:
                label = (act[0].capitalize() if act
                         else {"simbol": "Makna", "fungsi": "Fungsi atau tujuan"}.get(family)
                         or _STAGE_FALLBACK_HEADS[family])
                return (f"{label} {name} sendiri belum tercatat di basis data; {name} adalah {relation_to[pid]} "
                        f"{p['name']}. " + _as_paragraph(said, p["name"]))
        frontier = parents
        if not frontier:
            break
    return None


def _kind_time_decider(e: Dict[str, Any]) -> str:
    """For a kind of a rite whose time something decides: "<Kind> adalah salah satu jenis <rite>; waktu pelaksanaan
    <rite> ditentukan oleh ..." ("" if none)."""
    content = get_content()
    parents = [r.get("target_id") for r in e.get("relationships") or []
               if r.get("relation") == "TERMASUK_JENIS" and r.get("outgoing")]
    for pid in dict.fromkeys(parents + sorted(content.kind_parents.get(e["id"], ()))):
        if content.entity_type.get(pid) not in _STAGE_TYPES:
            continue
        decided = _time_decider_sentences({"id": pid, "name": content.entity_name[pid],
                                           "relationships": _kb_relationships(pid)})
        if decided:
            return (f"{e['name'][:1].upper()}{e['name'][1:]} adalah salah satu jenis {_card_cased(pid)}; "
                    + " ".join(s[:1].lower() + s[1:] for s in decided))
    return ""


# where something goes, not where it is: "terus atmanya ke mana?" got atma's place miss, while the KB says atma "dapat
# mencapai sorga" and becomes pitra, who "kembali ke pitraloka" and is "dimohonkan agar menuju dewaloka" (style test
# 2026-11-07). Not where a thing is taken: a verb named ("dibawa ke mana") is the place question's
_DESTINATION_Q_RE = re.compile(r"\bke\s*mana\b|\bmenuju\s+(?:ke\s+)?mana\b|\btujuan\s+akhir(?:nya)?\b", re.I)
# (in this order: where it returns, then where it goes on to; not a rite's act, "pitra dipersilakan masuk ke sekah")
_DESTINATION_PREDICATES = ("KEMBALI_KE", "MENUJU", "BERANGKAT_KE", "DIMOHONKAN_AGAR_MENUJU", "DAPAT_MENCAPAI",
                           "DAPAT_MEMASUKI", "MENUNJUKKAN_JALAN_ATMA_KE")
_BECOMES_PREDICATES = frozenset({"NAIK_KEDUDUKAN_MENJADI", "MENINGKAT_KEDUDUKAN_MENJADI", "BERUBAH_MENJADI"})


def _destination_answer(e: Dict[str, Any], user_msg: Text) -> Optional[str]:
    if not _DESTINATION_Q_RE.search(user_msg) or _asked_place_verb(user_msg):
        return None
    content = get_content()

    def goes(x: Dict[str, Any]) -> List[str]:
        return [s for p in _DESTINATION_PREDICATES for s in _edge_sentences(x, {p})]
    paragraphs, own = [], goes(e)
    for r in e.get("relationships") or []:
        tid = r.get("target_id")
        if r.get("relation") not in _BECOMES_PREDICATES or not r.get("outgoing") or tid not in content.entity_name:
            continue
        then = goes({"id": tid, "name": content.entity_name[tid], "relationships": _kb_relationships(tid)})
        if then:
            own.append(content.render(r["relation"], e["name"], content.entity_name[tid]))
            paragraphs.append(_as_paragraph(then, content.entity_name[tid]))
    if not own:
        return None
    return " ".join([_as_paragraph(list(dict.fromkeys(own)), e["name"])] + paragraphs)


# "ngaben apa yang paling sederhana?": a kind's card that says so, or -- when the cards only compare ("Sawa Prateka ...
# lebih sederhana daripada Sawa Wedana") -- that none is said to be. Qwen named Ngaben Svasta ("Istilah svasta merujuk
# pada jenis pelaksanaan yang paling sederhana") and, on a re-run, Sawa Prateka (style test 2026-11-07)
_SUPERLATIVE_Q_RE = re.compile(r"\byang\s+paling\s+([a-z]{4,})\b", re.I)


def _superlative_answer(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    m = _SUPERLATIVE_Q_RE.search(user_msg)
    if not m or _WHY_Q_RE.search(user_msg):
        return None
    adj, content = m.group(1).lower(), get_content()
    for e in enriched:
        kinds = list(dict.fromkeys(r.get("target_id") for r in e.get("relationships") or []
                                   if r.get("relation") == "TERMASUK_JENIS" and not r.get("outgoing")
                                   and r.get("target_id") in content.entity_name))
        if len(kinds) < 2 or not re.search(rf"(?<![\w-]){re.escape(e['name'])}(?![\w-])", user_msg, re.I):
            continue

        def said(degree: str) -> List[str]:
            rx = re.compile(rf"\b{degree}\s+{re.escape(adj)}\b", re.I)
            out = []
            for k in kinds:
                for s in _sentences(content.best_definition(k)):
                    if rx.search(s):
                        name = content.entity_name[k]
                        out.append(s if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", s, re.I)
                                   else f"{_card_cased(k)}: {s}")
            return list(dict.fromkeys(out))
        most = said("paling")
        if most:
            return " ".join(most)
        more = said("lebih")
        if more:
            return (f"Tidak ada jenis {_card_cased(e['id'])} yang disebut paling {adj}. Yang tercatat: "
                    + " ".join(_without_other_names(s) for s in more))
        return None
    return None


def _schedule_miss(user_msg: Text, enriched: List[Dict[str, Any]]) -> Optional[str]:
    if not enriched or not _NEXT_EVENT_RE.search(user_msg):
        return None
    named = _named_terms(user_msg, everyday=True)
    e = next((x for i in named for x in enriched if x["id"] == i), enriched[0])
    known = _known_sentence(e.get("definition"), entity_id=e["id"], name=e["name"])
    return (f"Maaf, jadwal {e['name']} berikutnya belum tercatat di basis data."
            + (f" Yang tercatat tentang {e['name']}: {known}" if known else ""))


_MAKE_ACT_RE = re.compile(r"\b(?:membuat|dibuat|pembuat|bikin|dibikin|dibuatin)\w*\b", re.I)
# a who-fact that names no doer: who it is for, who uses it, who usually holds it ("Sawa wedana lebih sering ditempuh
# oleh keluarga puri dan gria ...", graph audit 2026-11-06)
_NOT_A_DOER_RE = re.compile(r"\bdiperuntukkan\s+bagi\b|\b(?:digunakan|dipakai)\s+oleh\b|\blebih\s+sering\s+ditempuh\s+oleh\b",
                            re.I)
_LEAD_ACT_RE = re.compile(r"\b(?:memimpin|dipimpin|pemimpin|mimpin|memuput|dipuput|pemuput|muput)\w*\b", re.I)
# using it: "siapa yang memakai lembu" opened with "dibuat oleh undagi" before who uses it (2026-11-14)
_USE_ACT_RE = re.compile(r"\b(?:memakai|dipakai|pemakai|menggunakan|digunakan|pengguna|make|dipake|pakai|gunakan)\b",
                         re.I)


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
    """The act a who-question names, as (its doer's label, the words a fact must say): making, leading or using."""
    if _MAKE_ACT_RE.search(user_msg):
        return "pembuat", _MAKE_ACT_RE
    if _LEAD_ACT_RE.search(user_msg):
        return "pemimpin", _LEAD_ACT_RE
    if _USE_ACT_RE.search(user_msg):
        return "pengguna", _USE_ACT_RE
    return None


def _template_definition(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """The definition only (user, 2026-10-13)."""
    return _deterministic_answer([dict(enriched[0], aspect_facts=[])]) or None


def _asked_step_direction(user_msg: Text, e: Dict[str, Any]) -> Optional[int]:
    """+1 when the question asks what comes after the term ("setelah ngajum apa?", "sebelum apa?", "berikutnya"),
    -1 when it asks what comes before it ("sebelum ngajum apa?", "ngajum dilakukan setelah apa?"), else None."""
    names = [n for n in [e["name"]] + list(e.get("aliases") or []) + [e.get("asked_as") or "", e.get("typed_as") or ""]
             if len(n) >= 3]
    term = r"(?:(?:upacara|acara|tahap(?:an)?|prosesi)\s+)?(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w-])"
    if re.search(rf"\b(?:setelah|sesudah|sehabis|usai|abis|habis)\s+{term}", user_msg, re.I):
        return 1
    if re.search(rf"\bsebelum\s+{term}", user_msg, re.I):
        return -1
    if re.search(r"\b(?:setelah|sesudah|sehabis)\s+apa\b|\bsebelumnya\b", user_msg, re.I):
        return -1
    if re.search(r"\bsebelum\s+apa\b|\b(?:berikutnya|selanjutnya|sesudahnya|setelahnya)\b", user_msg, re.I):
        return 1
    return None


def _next_step_answer(e: Dict[str, Any], user_msg: Text) -> Optional[str]:
    """What comes right after (or before) the term, in the direction asked: its order edges, its stage number in its
    rite, or another rite or stage whose card says it comes "sesudah X" / "sebelum X". "setelah ngajum apa?" got "Ngajum
    dilakukan setelah nganget don bingin." -- the step before it -- while ngadegan sekah's card says it is "sesudah
    ngajum sekah dan sebelum pralina" (bot test 2026-11-05). None when the question asks no direction."""
    content = get_content()
    # (a rite or stage only: a thing's "dilakukan setelah apa" is its own order fact -- "Pripih emas dimasukkan setelah
    # padang lepas" -- which the waktu template gives)
    d = _asked_step_direction(user_msg, e) if content.entity_type.get(e["id"]) in _STAGE_TYPES else None
    if d is None:
        return None
    name = e["name"]
    # a step is a rite or stage ("banten pamegat DIGUNAKAN_SEBELUM pabersihan mati" is an offering used before it), and
    # none of the term's own parts or kinds or the rites it is part of: "sebelum ngaben apa?" got pabersihan (part of
    # ngaben, "dua atau tiga hari sebelum ngaben") and ngangkid (a step of asti wedana, for a body buried first);
    # pabersihan's own card says it is held "dua atau tiga hari sebelum ngaben", its own rite
    inside, frontier = set(), {e["id"]}
    for _ in range(3):
        frontier = {f["subject_id"] for i in frontier for f in content.facts_by_obj.get(i, [])
                    if f["predicate"] in ("BAGIAN_DARI", "TERMASUK_JENIS")} | {
            k for i in frontier for k in content.kinds_of(i)}
        frontier -= inside
        inside |= frontier
    inside |= {f["object_id"] for f in content.facts_by_subj.get(e["id"], []) if f["predicate"] == "BAGIAN_DARI"}

    def step(i: Optional[str], stated: bool = False) -> bool:
        # (an order edge is the KB's own word and may join a part: "nyiramang layon diikuti oleh pangringkes", which
        # is also part of it -- "setelah nyiramang layon apa?" is a category 3 sample)
        return (bool(i) and i != e["id"] and content.entity_type.get(i) in _STAGE_TYPES
                and (stated or i not in inside))
    found: List[str] = []
    for r in e.get("relationships") or []:
        sign = _ORDER_SIGN.get(r.get("relation"))
        if sign and step(r.get("target_id"), stated=True) and (sign if r.get("outgoing") else -sign) == d:
            found.append(r["target_id"])
    stating_by: Dict[str, str] = {}   # a card found by its own words -> the sentence that says it
    after_word, before_word = r"(?:sesudah|setelah|sehabis)", r"(?:sebelum|menjelang)"
    any_word = re.compile(rf"\b(?:{after_word[3:-1]}|{before_word[3:-1]})\b", re.I)

    def stages_in(sentence: Text, word: Text) -> List[List[str]]:
        """The rites and stages each "<word> A dan B" phrase of a sentence names, in order (up to the next order word)."""
        out = []
        for m in re.finditer(rf"\b{word}\s+", sentence, re.I):
            rest = re.split(r"[,;:.()]", sentence[m.end():], 1)[0]
            nxt = any_word.search(rest)
            phrase = rest[:nxt.start()] if nxt else rest
            out.append([i for i in _named_terms(phrase) if content.entity_type.get(i) in _STAGE_TYPES])
        return out
    if not found:
        # its own card: "Ngadegan sekah ... sesudah ngajum sekah dan sebelum pralina" -- the next is pralina; of
        # "sesudah A dan B" the one before is B
        own = [s for s in _sentences(content.best_definition(e["id"]) or "") if _dates_the_term(s, any_word)]
        for s in own:
            for group in stages_in(s, before_word if d > 0 else after_word):
                group = [i for i in group if step(i)]
                if group:
                    found.append(group[0] if d > 0 else group[-1])
    if not found:
        # its number in a rite it is a stage of: the stage numbered one after (or before) it
        for f in content.facts_by_subj.get(e["id"], []):
            n = _stage_number(content.best_definition(e["id"]), f["object_id"]) if f["predicate"] == "BAGIAN_DARI" else None
            if n:
                found += [x["subject_id"] for x in content.facts_by_obj.get(f["object_id"], [])
                          if x["predicate"] == "BAGIAN_DARI" and step(x["subject_id"])
                          and _stage_number(content.best_definition(x["subject_id"]), f["object_id"]) == n + d]
    if not found:
        # another card that dates itself from this one in its own words, right after it: of sangaskara's "sesudah Manah
        # Tirtha Ening dan Mlaspas Kajang" only mlaspas kajang comes just before it; "setelah upacara Pabersihan Hidup"
        # names pabersihan hidup, not pabersihan
        for oid in content.entity_def:
            if not step(oid):
                continue
            for s in _sentences(content.best_definition(oid) or ""):
                if not _dates_the_term(s, any_word):
                    continue
                groups = stages_in(s, after_word if d > 0 else before_word)
                if any(g and (g[-1] if d > 0 else g[0]) == e["id"] for g in groups):
                    found.append(oid)
                    stating_by[oid] = s
                    break
    found = list(dict.fromkeys(found))
    stating = [stating_by[i] for i in found if i in stating_by]
    where = "sesudah" if d > 0 else "sebelum"
    if not found:
        known = _known_sentence(e.get("definition") or content.best_definition(e["id"]), entity_id=e["id"], name=name)
        order = _aspect_sentences(e, "waktu")
        return (f"Maaf, tahap {where} {name} belum tercatat di basis data."
                + (f" Yang tercatat tentang urutannya: {' '.join(order)}" if order
                   else f" Yang tercatat tentang {name}: {known}" if known else ""))
    return (f"{where.capitalize()} {name}, yang dilakukan adalah {_join_names([content.entity_name[i] for i in found])}."
            + (" " + " ".join(stating) if stating else ""))


def _template_aspect(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """Meaning, purpose, place, time, doer or how: the definition's sentences and facts of that aspect, as one
    paragraph; a ceremony with none of its own gives its stages'."""
    e = enriched[0]
    name = e["name"]
    title = f"{name[:1].upper()}{name[1:]}"
    rels = e.get("relationships") or []
    content = get_content()
    if family == "waktu":
        step = _next_step_answer(e, user_msg)
        if step:
            return step
    if family == "lokasi":
        gone = _destination_answer(e, user_msg)
        if gone:
            return gone
    found = _aspect_sentences(e, family)
    if family == "waktu":
        # what decides its time first: "kapan ngaben dilakukan" gave only what comes before and after it, never that
        # dewasa ngaben decides its day (category 5, "faktor penentuan waktu pelaksanaan"; AYUTHAYA part B, 2026-11-04)
        decided = _time_decider_sentences(e)
        found = decided + [s for s in found if s not in decided]
    act = _asked_act(user_msg) if family == "pelaku" else None
    if found and act:
        # the act the question names: "siapa yang membuat jenazah" got "Jenazah dibasmi oleh sang hyang birawi",
        # "siapa yang membuat sekah" "Sekah diajak berkomunikasi oleh keluarga" (sheet Failed, 2026-10-27)
        label, said = act
        doers, found = found, [s for s in found if said.search(s)]
        # who it is for or who uses it does none of it: "yang muput upacara sawa wedana siapa?" got "Maaf, pemimpin
        # ... Yang tercatat tentang pelaksananya: Sawa wedana diperuntukkan bagi keluarga puri, gria, ...", while
        # mamukur, with no such fact, got its rite's leader (bot test 2026-11-05)
        # (who usually holds it still says something when no rite above it records a leader: "siapa yang memimpin
        # nyekeh" -- "Nyekeh lebih sering ditempuh oleh keluarga raja atau pendeta", graph audit 2026-11-06)
        holders = [s for s in doers if re.search(r"\blebih\s+sering\s+ditempuh\s+oleh\b", s, re.I)]
        doers = [s for s in doers if not _NOT_A_DOER_RE.search(s)]
        if not found and label == "pemimpin" and content.entity_type.get(e["id"]) in _STAGE_TYPES and doers:
            # who leads a rite nothing says leads it: who does it, which is what "siapa yang memimpin nyiramang
            # layon" wants to know -- it got "pemimpin belum tercatat" above "dilakukan oleh keluarga bersama
            # pemangku" (the AYUTHAYA change: who takes part in every ceremony, 2026-11-03)
            return (f"Maaf, pemimpin {name} belum tercatat di basis data. Yang tercatat tentang pelaksananya: "
                    + _as_paragraph(doers, name))
        if not found and label == "pengguna" and doers:
            # who uses it unrecorded, who makes or does it is the closest fact: "siapa yang menggunakan tirtha pangentas"
            # (2026-11-14) -- before the use act it got the maker as if he were the user
            return (f"Maaf, pengguna {name} belum tercatat di basis data. Yang tercatat tentang pelakunya: "
                    + _as_paragraph(doers, name))
        if not found and label == "pemimpin":
            parent = _parent_aspect(e, family, act)
            if parent:
                return parent
            if holders and content.entity_type.get(e["id"]) in _STAGE_TYPES:
                return (f"Maaf, pemimpin {name} belum tercatat di basis data. Yang tercatat tentang pelaksananya: "
                        + _as_paragraph(holders, name))
        if not found:
            rites = [r["target"] for r in rels if r.get("relation") == "MEMBUAT" and not r.get("outgoing")
                     and content.entity_type.get(r.get("target_id")) in _STAGE_TYPES]
            return _template_miss(label, e) + (
                f" {title} dibuat dalam {_join_names(rites)}." if rites and label == "pembuat" else "")
    if found and family == "pelaku":
        # who leads first, then who takes part: "siapa saja yang melakukan upacara ngaben" ended "Ngaben juga dipimpin
        # oleh sulinggih" after the participants (AYUTHAYA part B review, 2026-11-04)
        found = sorted(found, key=lambda s: not _LEAD_ACT_RE.search(s))
    verb = _asked_place_verb(user_msg) if family == "lokasi" else None
    if found and verb:
        # the act the place question names: "jenazah disemayamkan di mana" listed every place the corpse is
        # carried, laid and washed (the 12 evaluation categories, 2026-10-27)
        found = [s for s in found if any(_root(w) == verb for w in _WORD_RE.findall(s.lower()))] or found
    if found:
        if (family == "simbol" and all(re.search(r"\bdinilai\s+sebagai\b", s, re.I) for s in found)
                and content.entity_type.get(e["id"]) in _STAGE_TYPES | _CROSS_ASPECT_SARANA):
            # a rank is no meaning on its own: "apa makna filosofisnya?" (sawa wedana) got only "Sawa wedana dinilai
            # sebagai utamaning utama.", not that it "bertujuan menyucikan badan halus mendiang" (bot test 2026-11-05)
            found += [s for s in _aspect_sentences(dict(e, relationships=[r for r in rels
                                                                         if r.get("relation") not in _BARE_USE_EDGES]),
                                                   "fungsi", skip=_BARE_USE_FACTS) if s not in found]
        if family == "fungsi":
            own = [_without_other_names(s) for s in _sentences(_deterministic_answer([dict(e, aspect_facts=[])]))]
            if own and not any(f in own for f in found):
                # with no definition sentence stating a purpose, what the thing is says what it is for:
                # "apa peran wadah" got only "Wadah digunakan dalam ngaben", not that it is the usungan
                # that carries the corpse; gegaleng, babelonyoh, bade the same (LLM comparison 2026-10-20);
                # an edge that sentence already says goes ("... ritual penyucian untuk membersihkan diri ... dari
                # ... leteh. Pabersihan hidup bertujuan membersihkan diri dari leteh.", 2026-10-28)
                found = _distinct_sentences([_purpose_clause(own[0], name)] + found, e)
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
                stage_list = (f"Tempat {_parts_word(e)} {name} yang tercatat:\n"
                              + "\n".join(f"- {s}" for s in staged))
                if all(re.search(r"\bdapat\s+dilakukan\s+di\b", s, re.I) for s in found):
                    # only a place it may be held in ("ngaben dapat dilakukan di krematorium"): the stages' first
                    return f"{stage_list}\nSelain itu, {own_text[:1].lower()}{own_text[1:]}"
                # its own place first: "di mana nyiramang layon dilakukan" opened with memunjung's place and put
                # "di natah" last (AYUTHAYA part B, 2026-11-04)
                return f"{own_text}\n\n{stage_list}"
        return _as_paragraph(found, name)
    if family in _EDGES_FIRST_FAMILIES:
        # a ceremony with no place / time / doer of its own: what its stages record. "di mana upacara
        # ngaben biasanya dilaksanakan?" got "tempat ngaben belum tercatat", while pabasmian is "di
        # setra" (Tier B 2026-10-13)
        staged = _stage_aspect_sentences(e, family)
        # a kind of a rite with no time of its own is held when its rite is: "kapan dilakukan?" about asti wedana got
        # only ngangkid's "menjelang pangabenan" and never that dewasa ngaben decides a Ngaben's day (style test
        # 2026-11-07); not a kind with a time of its own (Sawa Wedana is held 3-7 days after the death)
        inherited = _kind_time_decider(e) if family == "waktu" else ""
        if inherited and staged:
            joined = (_join_names([s[:1].lower() + s[1:].rstrip(".") for s in staged]) + "." if len(staged) <= 3
                      else "\n" + "\n".join(f"- {s}" for s in staged))
            return f"{inherited}\n\nYang tercatat untuk {'tahapannya' if _parts_word(e) == 'tahapan' else 'bagian-bagiannya'}: {joined}"
        if inherited:
            return inherited
        if staged:
            head = (f"{_STAGE_FALLBACK_HEADS[family]} {name} secara keseluruhan tidak tercatat, tetapi "
                    f"untuk {'tahapannya' if _parts_word(e) == 'tahapan' else 'bagian-bagiannya'} tercatat")
            if len(staged) <= 3:
                return f"{head} bahwa {_join_names([s[:1].lower() + s[1:].rstrip('.') for s in staged])}."
            return f"{head}:\n" + "\n".join(f"- {s}" for s in staged)
        parent = _parent_aspect(e, family, act) if family in ("lokasi", "pelaku") else None
        if parent:
            return parent
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
    if family in ("simbol", "fungsi"):
        # its philosophy is its meaning or its purpose (the AYUTHAYA change, 2026-11-03: "the philosophy of
        # everything: sarana, ceremonies ..."): with only the other one recorded, that one, said as such. Only for a
        # rite or a sarana -- of a concept or a person the two are not interchangeable ("apa yang dilambangkan oleh
        # pitra" is no "pitra dimohonkan agar menuju dewaloka") -- and never a bare "X digunakan dalam Y" or "ditujukan
        # untuk Y", which says less than the definition the miss shows ("babelonyoh itu menyimbolkan apa",
        # "apa arti simbolis pitra yadnya": "ditujukan untuk orangtua"; "apa filosofi krematorium": "digunakan untuk
        # ngaben")
        other = "fungsi" if family == "simbol" else "simbol"
        alt = []
        if content.entity_type.get(e["id"]) in _STAGE_TYPES | _CROSS_ASPECT_SARANA:
            alt = _aspect_sentences(dict(e, relationships=[r for r in rels if r.get("relation") not in _BARE_USE_EDGES]),
                                    other, skip=_BARE_USE_FACTS)
        if alt:
            what = "fungsi atau tujuannya" if other == "fungsi" else "maknanya"
            return (f"Maaf, {_aspect_label(family, user_msg)} {name} belum tercatat di basis data. Yang tercatat "
                    f"tentang {what}: " + _as_paragraph(alt, name))
        # a kind or another name of a rite: the rite's ("apa makna asti wedana" -- Ngaben's purpose)
        parent = _parent_aspect(e, family, None, kinds_only=True)
        if parent:
            return parent
        # a day: what its card says of it in choosing a good day, and why when it says why ("apa makna sasih kadasa":
        # burning a body then "dianggap mencemari ... sebab ... pesamuhan para dewa") -- only what the card says
        # (not dewasa ngaben itself: its card is the whole rule set, no meaning of it -- "peran dewasa ngaben apa")
        # (not the adult, "jenazah orang dewasa", nor "tanpa memilih hari baik": jenazah bayi's purpose miss read "Yang
        # tersedia tentang jenazah bayi dalam pemilihan hari baik (dewasa): ...", style test 2026-11-07)
        if e["id"] != "dewasa_ngaben" and (
                any(e["id"] == c or content.is_kind_of(e["id"], c) for c in ("sasih", "wuku", "wewaran"))
                or re.search(r"(?<!orang )(?<!usia )\bdewasa\b|(?<!memilih )\bhari baik\b|\bhari buruk\b|\bwariga\b",
                             _definition_text(e), re.I)):
            said = [s for s in _sentences(_deterministic_answer([dict(e, aspect_facts=[])]))
                    if _DAY_STANDING_RE.search(s)]
            # and the day rules of dewasa ngaben that name it ("... buda kliwon, anggara kliwon ... tetap dihindari")
            # (only when its own card says nothing of it: sasih kadasa's card already says it is not for burning)
            named = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I)
            if not said:
                said += [s for s in _sentences(content.best_definition("dewasa_ngaben") or "")
                         if named.search(s) and _DAY_STANDING_RE.search(s) and s not in said]
            if said:
                return (f"Maaf, {_aspect_label(family, user_msg)} {name} belum tercatat di basis data. Yang tercatat "
                        f"tentang {name} dalam pemilihan hari baik (dewasa): " + " ".join(said))
    return _template_miss(act[0] if act else _aspect_label(family, user_msg), e)


# the things whose meaning stands in for a missing purpose and back (with the rites, _STAGE_TYPES)
_CROSS_ASPECT_SARANA = frozenset({"SARANA_RITUAL", "TIRTHA_SUCI", "BANGUNAN_RITUAL"})
# what a thing is used in or addressed to: no meaning or purpose of its own (as a fact of any kind) ...
_BARE_USE_FACTS = frozenset({"DIGUNAKAN_DALAM", "DIGUNAKAN_PADA", "DITUJUKAN_UNTUK", "DIPERSEMBAHKAN_KEPADA",
                             "DIPERUNTUKKAN_BAGI"})
# "X di<verb> dengan Y": Y is used to wrap, lay, tie, wash, ... X -- what Y is for (_aspect_sentences, fungsi)
_USED_WITH_PREDICATES = frozenset({
    "DIBUNGKUS_DENGAN", "DIALASI_DENGAN", "DIIKAT_DENGAN", "DISUCIKAN_DENGAN", "DISIRAM_DENGAN", "DIGULUNG_DENGAN",
    "DIPERCIKI_DENGAN", "DIKURUNG_DENGAN", "DISABUNI_DENGAN", "DITUTUPI_DENGAN", "DIKERINGKAN_DENGAN",
    "DIBERSIHKAN_DENGAN", "DIHALUSKAN_DENGAN", "DIHIAS_DENGAN", "DISAMBUNG_DENGAN", "DIPUJA_DENGAN"})
# ... nor what it is used for when that is another term ("krematorium digunakan untuk ngaben"), nor what it is used on
# ("jenazah dibungkus dengan kain putih"); a text fact says how ("upih digunakan untuk memukul tanah kuburan tiga kali
# ... sebagai tanda panggilan")
_BARE_USE_EDGES = _BARE_USE_FACTS | {"DIGUNAKAN_UNTUK", "DIPAKAI_UNTUK"} | _USED_WITH_PREDICATES


# a sentence that says how a day stands in choosing one: good, avoided, and why
_DAY_STANDING_RE = re.compile(r"\b(?:baik|buruk|utama|madya|dihindari|dibolehkan|diperbolehkan|tidak boleh|"
                              r"tidak diperkenankan|tidak dianjurkan|dianggap|dinilai|sebab|karena|pantang|alaning)\b",
                              re.I)


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


_COUNTED_LEVELS_RE = re.compile(r"\s*Ada\s+(?:dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|\d+)\s+"
                                r"(tingkat|jenis|macam|golongan)\w*\b", re.I)


def _counted_levels(definition: Optional[Text]) -> Optional[tuple]:
    """("Ada empat tingkat usia.", ["Tingkat pertama dan kedua, ...", "Tingkat ketiga: ...", ...]) when a definition
    counts its levels in one sentence and names each in the sentences right after it, else None."""
    sentences = _sentences(definition)
    for i, s in enumerate(sentences):
        m = _COUNTED_LEVELS_RE.match(s)
        if not m:
            continue
        items = []
        for t in sentences[i + 1:]:
            if not re.match(rf"\s*{m.group(1)}\w*\s+(?:ke-?\w+|pertama|kedua|ketiga|keempat|kelima|keenam|ketujuh|"
                            rf"kedelapan|kesembilan|kesepuluh|terakhir)\b", t, re.I):
                break
            items.append(t.strip())
        if len(items) >= 2:
            return s.strip(), items
    return None


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
        # a definition that counts its levels and then names each: "apa saja tingkatan usia bayi" got "Maaf, informasi
        # tersebut belum tersedia" above jenazah bayi's own "Ada empat tingkat usia. Tingkat pertama dan kedua, ...
        # Tingkat ketiga: ... Tingkat keempat: ..." (user's live session, 2026-11-09)
        counted = _counted_levels(_definition_text(e))
        if counted:
            lead, items = counted
            return f"Untuk {name}, {lead[:1].lower()}{lead[1:]}\n" + "\n".join(items)
        # kinds told apart by their tiers, which a part card "tingkatan X" holds: "bade ada berapa jenis" got "jenis bade
        # belum tercatat" -- corpus L1563 "Bade jenis apa yang boleh ... dipakai ... ditentukan berdasarkan statusnya",
        # the tiers 11 / 9 / 7 (V2 grading, 2026-11-02)
        tiers = content.id_by_name.get(f"tingkatan {name.lower()}")
        if tiers and any(r["relation"] == "BAGIAN_DARI" and r["outgoing"] and r["target_id"] == eid
                         for r in _kb_relationships(tiers)):
            return f"Jenis {name} dibedakan menurut tingkatnya. {content.best_definition(tiers)}"
        return _template_miss("jenis", e, whole=True)
    # in the order its card names them, each with what it is and its own kinds: "apa saja tingkatannya?" got the
    # definition, and with "jenis" madya / nista / utama, each "salah satu dari tiga jalan pokok ...", and no word of the
    # nine sub-levels the KB holds (conersation.md section V, 2026-11-06)
    kinds = _in_card_order(eid, kinds)
    count = _NUMBER_WORDS.get(str(len(kinds)), str(len(kinds))).replace("duabelas", "dua belas")
    levels = name.lower().startswith("tingkat")
    head = f"Ada {count} {'' if levels else 'jenis '}{name} yang tercatat"
    if len(kinds) > 12:
        return f"{head}: {_join_names([content.entity_name[k] for k in kinds])}."
    glosses = _sibling_glosses(kinds)
    glosses = {k: _class_sense_gloss(k, eid) or g for k, g in glosses.items()}
    if len(kinds) == 1:
        # one kind is no list: "Ada satu jenis mantra yang tersedia:\n1. Weda pengastawa: ..." (sweep 2026-11-13)
        kname = content.entity_name[kinds[0]]
        gloss = glosses[kinds[0]].strip().rstrip(".")
        return (f"Hanya satu jenis {name} yang tercatat, yaitu {kname[:1].upper()}{kname[1:]}"
                + (f": {gloss}." if gloss else "."))
    above = [content.entity_name[k].lower() for k in kinds]
    lines = []
    for i, k in enumerate(kinds, 1):
        kname = content.entity_name[k]
        title = f"{kname[:1].upper()}{kname[1:]}"
        item = title + (f": {glosses[k]}" if glosses[k] else "")
        subs = [s for s in content.kinds_of(k) if s in content.entity_name]
        if 2 <= len(subs) <= 6:
            subs = _in_card_order(k, subs, before=above)
            item += (f" {'Sub-tingkatannya' if levels else 'Jenis-jenisnya'}: "
                     f"{_join_names([content.entity_name[s] for s in subs])}.")
        lines.append(f"{i}. {item}")
    return f"{head}:\n" + "\n".join(lines)


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
            lead = f"Tahap {'pertama' if first else 'terakhir'} {name}"
            if len(group) == 1:
                g = _stage_gloss(ids[0])
                return f"{lead} adalah {group[0]}" + (f": {g}" if g else ".")
            return f"{lead} adalah {_join_names(group)}:\n" + "\n".join(f"- {_stage_item(i)}" for i in ids)
        return None
    chain = [] if numbered else _ordered_kinds(eid)
    if len(chain) >= 2:
        # kinds of the rite done one after the other are its stages: "bagaimana prosesi pitra yadnya" listed ngajar-ajar,
        # mapendem, nyekeh and ngaben titip, not that Ngaben is "Pitra Yadnya tahap pertama" and Atma Wedana "tahap
        # kedua" (L1006, L1942; the KB orders them: atma wedana DILAKUKAN_SETELAH ngaben) -- V2 grading, 2026-11-02
        others = [content.entity_name[s] for s in stages if s not in chain and not _inside_stages(s, chain)]
        return (f"Tahapan {name} secara berurutan adalah sebagai berikut:\n"
                + "\n".join(f"{i}. {_stage_item(k)}" for i, k in enumerate(chain, 1))
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
                lines.append(f"{n}. {_stage_item(ids[0])}")
            else:
                joined = _join_names(group)
                lines.append(f"{n}. {joined[:1].upper()}{joined[1:]}:")
                lines += [f"   - {_stage_item(i)}" for i in ids]
        shown = {stage.lower() for _, stage in numbered}
        shown_ids = [content.id_by_name.get(s) for s in shown if content.id_by_name.get(s)]
        others = [content.entity_name[s] for s in stages
                  if content.entity_name[s].lower() not in shown and not _inside_stages(s, shown_ids)]
        # how many, first, when that is the question: "berapa tahapan ngaben?" got the list with no number before it
        # (style test 2026-11-06) -- the total the stage cards state ("dari delapan tahapan"), else the list's own
        head = f"Tahapan {name} secara berurutan adalah sebagai berikut:"
        if re.search(r"\b(?:berapa|jumlah)\b", user_msg, re.I):
            total = _stated_stage_total([content.id_by_name.get(s.lower()) for _, s in numbered]) or len(by_number)
            count = _NUMBER_WORDS.get(str(total), str(total))
            head = f"{name[:1].upper()}{name[1:]} memiliki {count} tahapan, secara berurutan:"
        return (f"{head}\n" + "\n".join(lines)
                + (f"\nSelain itu, rangkaian {name} juga mencakup {_join_names(others)}." if others else ""))
    # one recorded stage is no procedure: "bagaimana upacara ngelungah dilaksanakan" got only ngeluhurang bhatara
    # kumara once that card existed (plan #19 batch 2); a how question goes on to the definition / the model
    if stages and (len(stages) >= 2 or not (_HOW_RE.search(user_msg) and not re.search(r"\btahap", user_msg, re.I))):
        return (f"Tahapan {name} yang tercatat (urutannya tidak disebutkan dalam sumber):\n"
                + "\n".join(f"- {_list_item(s)}" for s in stages))
    # how it is done as the definition and its text facts say it -- not its edges: "bagaimana upacara ngelungah
    # dilaksanakan" got "Upacara ngelungah menggunakan klungah", "apa saja tahapan sangging" "Sangging menggunakan
    # padi ...", "sebutkan tahapan pangringkes" its kain putih and klasa (sheet Failed, 2026-10-27)
    # (a protection is no step: "apa saja tahapan mamukur" got "Mamukur dilindungi dengan upaya penyucian wilayah yang
    # ketat ...", bot test 2026-11-05)
    how = _aspect_sentences(e, "cara", with_edges=False, skip=frozenset({"DILINDUNGI_DENGAN"}))
    # how a thing is made: who makes it, in which act and where, and what it is made of -- unless its card writes the
    # making down step by step (Tirta Pangentas "dibuat melalui urutan berikut ..."). "bagaimana cara membuat sekah?"
    # said "belum tersedia" though the KB has the sulinggih, Ngajum ("Kegiatan membuat sekah inilah yang bernama
    # Ngajum", L2121) and sekah's parts; so did bade, daksina, kajang, lembu (2026-11-13)
    if _MAKE_Q_RE.search(user_msg) and content.entity_type.get(eid) not in _STAGE_TYPES \
            and not any(re.search(r"\b(?:dibuat|pembuatan)\b", h, re.I) for h in how):
        made = _making_answer(e)
        if made:
            return made
    if how:
        return _as_paragraph(how, name)
    # a level of a rite with no stages of its own has the rite's, said as the rite's: mamukur is "tingkatan upacara Atma
    # Wedana" (bot test 2026-11-05). Only a level its card names, and not for "bagaimana ... dilaksanakan": ngelungah, a
    # baby's rite and a kind of ngaben, got Ngaben's eight stages for "bagaimana upacara ngelungah dilaksanakan"
    parents = sorted(set(content.kind_parents.get(eid, ())) | {
        r["target_id"] for r in e.get("relationships") or []
        if r.get("relation") == "TERMASUK_JENIS" and r.get("outgoing") and r.get("target_id")})
    for pid in parents if re.search(r"\b(?:tahap\w*|urutan\w*|rangkaian\w*)\b", user_msg, re.I) else []:
        level = re.compile(rf"\btingkat(?:an)?\s+(?:upacara\s+)?{re.escape(content.entity_name.get(pid, ''))}\b", re.I)
        if content.entity_type.get(pid) not in _STAGE_TYPES or not level.search(e.get("definition") or ""):
            continue
        p = {"id": pid, "name": content.entity_name[pid], "definition": content.best_definition(pid),
             "relationships": _kb_relationships(pid)}
        said = _template_stages(family, [p], user_msg) if _stage_ids(p) else None
        if said and not said.startswith("Maaf"):
            return (f"Tahapan {name} sendiri belum tercatat di basis data; {name} adalah salah satu jenis "
                    f"{p['name']}. {said}")
    # a rite with no stage list is the model's to read from its definition; anything else is a miss (the free
    # run of the 1,864 sent 59 "bagaimana alur kopi", "langkah-langkah cermin kecil" to Qwen with the how-words)
    if content.entity_type.get(eid) in _STAGE_TYPES:
        return None
    return _template_miss("tahapan atau cara", e, whole=True)


# a question about how something is made or who makes it
# (not a bare "buat", which is also "for": "cara pakai kajang buat ngaben")
_MAKE_Q_RE = re.compile(r"\b(?:membuat|dibuat|bikin|dibikin|pembuatan|pembuatnya|membuatnya|dibuatnya|"
                        r"membentuk|dibentuk)\b", re.I)
_MAKER_PREDICATES = frozenset({"DIBUAT_OLEH", "HANYA_DAPAT_DIBUAT_OLEH"})


def _making_acts(eid: str) -> List[str]:
    """The rites or stages that make eid, by the KB's edges: "<act> MEMBUAT <eid>" (ngajum membuat sekah), "<eid>
    DIBUAT_MELALUI <act>"; a maker that is a person is no act."""
    content = get_content()
    acts = []
    for r in _kb_relationships(eid):
        if (r["relation"] == "MEMBUAT" and not r["outgoing"] or r["relation"] == "DIBUAT_MELALUI" and r["outgoing"]) \
                and content.entity_type.get(r["target_id"]) in _STAGE_TYPES and r["target_id"] not in acts:
            acts.append(r["target_id"])
    return acts


def _making_answer(e: Dict[str, Any]) -> Optional[str]:
    """How a thing is made, as the KB records it: "<X> dibuat oleh <who> dalam acara <act>, di <where>." and what it is
    made of (the first line of its composition). None when the KB records neither."""
    content = get_content()
    eid = e["id"]
    rels = _kb_relationships(eid)
    acts = _making_acts(eid)
    doers = [r["target_id"] for r in rels if r["outgoing"] and r["relation"] in _MAKER_PREDICATES]
    doers += [r["target_id"] for r in rels if r["relation"] == "MEMBUAT" and not r["outgoing"]
              and content.entity_type.get(r["target_id"]) not in _STAGE_TYPES]
    places = [r["target_id"] for r in rels if r["outgoing"] and r["relation"] == "DIBUAT_DI"]
    places += [r["target_id"] for a in acts for r in _kb_relationships(a) if r["outgoing"]
               and r["relation"] in ("DILAKUKAN_DI", "DIADAKAN_DI")]
    once = lambda ids: list(dict.fromkeys(ids))  # noqa: E731
    title = _cap(_card_cased(eid, e.get("asked_as") or e.get("typed_as")))
    parts = []
    if doers or acts or places:
        s = f"{title} dibuat"
        if doers:
            s += f" oleh {_join_names([_card_cased(d) for d in once(doers)])}"
        if acts:
            s += f" dalam acara {_join_names([_cap(_card_cased(a)) for a in once(acts)])}"
        if places:
            s += f"{',' if acts else ''} di {_join_names([_card_cased(p) for p in once(places)])}"
        parts.append(_gloss_doers(s + ".", eid))
    # (not a raw material's "X adalah bahan dasar ...": "bagaimana cara membuat emas" keeps its honest miss)
    made_of = "" if content.is_raw(eid) else (_template_contents("komposisi", [e], "") or "")
    first = made_of.split("\n")[0].strip()
    if first and not first.startswith("Maaf"):
        parts.append(first)
    return " ".join(parts) or None


def _with_making_act(answer: Text, eid: str, user_msg: Text) -> Text:
    """A who-makes-it answer names the act it is made in too: "Sekah dibuat oleh sulinggih (...) dalam acara Ngajum."
    (the aspect sweep had "siapa yang membuat sekah?" without Ngajum, 2026-11-13)."""
    acts = _making_acts(eid) if _MAKE_Q_RE.search(user_msg) or re.search(r"\bbuat\b", user_msg, re.I) else []
    if not acts or not re.search(r"\bdibuat oleh\b", answer):
        return answer
    names = _join_names([_cap(_card_cased(a)) for a in acts])
    if re.search(rf"\b{re.escape(names)}\b", answer, re.I):
        return answer
    return re.sub(r"(\bdibuat oleh\b[^.!?\n]*?)([.!?])", lambda m: f"{m.group(1)} dalam acara {names}{m.group(2)}",
                  answer, count=1)


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
    breakdown = _composition_breakdown(eid, deep=bool(_MADE_OF_Q_RE.search(user_msg)))
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
    staged = [(place, items) for pid, place, items in places if pid != eid]
    if lines and sum(len(items) for _, items in staged) > 40:
        # too many to read: the rite's own, then which stages have their own, to ask one by one -- "apa saja sarana
        # ngaben?" listed some 200 items over 22 stages (style test 2026-11-06)
        names = _join_names([place for place, _ in staged])
        return "\n".join(made_with + lines + [
            f"Tiap tahapannya juga memakai sarana sendiri, yaitu {names}. Tanyakan sarana tahapan tertentu untuk "
            f"rinciannya, misalnya \"apa saja sarana {staged[0][0]}?\"."])
    if stage_lines:
        lines.append(("Sarana pada tiap tahapannya:" if lines else f"Sarana yang digunakan dalam tahapan {name}:")
                     + "\n" + "\n".join(stage_lines))
    return "\n".join(made_with + lines)


def _template_other_names(family: str, enriched: List[Dict[str, Any]], user_msg: Text) -> Optional[str]:
    """One list of its other names, the refined one apart."""
    e = enriched[0]
    # (asked by another name: that name opens, the KB name first among the others -- user, 2026-11-10)
    asked = e.get("asked_as") or e.get("typed_as")
    is_asked_other = bool(asked and _ortho_key(asked) != _ortho_key(e["name"]) and _plain_other_name(e, asked))
    name = asked if is_asked_other else e["name"]
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
    if is_asked_other:
        card = re.search(rf"(?<![\w-]){re.escape(e['name'])}(?![\w-])", e.get("definition") or "", re.I)
        name_cased = card.group(0) if card else e["name"][:1].upper() + e["name"][1:]
        names.insert(0, name_cased)

    def key(n: Text) -> str:
        # one name with or without its rite word: "upacara ngelelet, Ngelelet, dan Melelet" (2026-10-26)
        return _ortho_key(re.sub(r"^(?:upacara|acara|prosesi|ritual)\s+", "", n.strip(), flags=re.I))

    seen = {key(name)} | {key(n) for n in refined}
    names = [n for n in names if not (key(n) in seen or seen.add(key(n)))]
    found = [f"{title} juga dikenal sebagai {_join_names(names)}."] if names else []
    if refined:
        found.append(f"Sebutan halusnya adalah {_join_names(refined)}.")
    found += _distinct_sentences(said, e)
    # a miss says what is recorded too, as every template miss does (the AYUTHAYA change: "Maaf, informasi tersebut
    # belum tersedia." then what is available)
    return " ".join(found) if found else _template_miss("sebutan lain untuk", e)


# words of a card's gloss that say how a thing is used in a rite, not what the word means
_RITUAL_USE_RE = re.compile(r"\b(?:upacara|upakara|banten|sesajen|sesaji|ngaben|jenazah|patulangan|soda|raka-raka"
                            r"|sarana|ritual|eteh-eteh)\b", re.I)
_PLAIN_WORDS: Optional[frozenset] = None


def _plain_indonesian(name: Text) -> bool:
    """Every word of the name is ordinary Indonesian: in the common-word list, or written as a plain word (tagged O)
    anywhere in the corpus behind it -- "singa" and "telur" fall below that list's three-times cut."""
    global _PLAIN_WORDS
    if _PLAIN_WORDS is None:
        words = set()
        for line in Path(_COMMON_WORDS_FILE).read_text(encoding="utf-8").splitlines():
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
        answer = _template_aspect(family, enriched, user_msg)
        if answer and family == "pelaku":
            return _with_making_act(_gloss_doers(answer, enriched[0]["id"]), enriched[0]["id"], user_msg)
        return answer
    template = _TEMPLATES.get(family)
    return template(family, enriched, user_msg) if template else None


# the cards a doer answer names that a reader may not know: people and roles, not things
_DOER_GLOSS_TYPES = {"STRUKTUR_SOSIAL_ADAT", "ENTITAS_KEAGAMAAN", "KASTA_SOSIAL"}
_DOER_NAMES: Optional[List[tuple]] = None


def _short_gloss(entity_id: str, limit: int = 90) -> str:
    """What a person or role is, in its card's first clause: "orang yang punya upacara" (yajamana), "pendeta atau tokoh
    suci yang memiliki otoritas spiritual tertinggi" (sulinggih). "" when no clean cut fits in `limit`."""
    s = re.sub(r"^(?:sebutan|istilah|gelar)\s+(?:bagi|untuk)\s+", "", _gloss(entity_id, limit=10 ** 6).rstrip(". "),
               flags=re.I)
    depth, cut = 0, len(s)
    for i, ch in enumerate(s):
        depth += (ch == "(") - (ch == ")")
        if depth == 0 and ch in ",;:":
            cut = i
            break
    s = s[:cut].strip()
    if len(s) > limit:
        # (before a "yang ..." clause: "arsitek atau tukang bangunan tradisional Bali yang ahli merancang ...")
        at = [m.start() for m in re.finditer(r"\s+yang\s+", s) if 15 <= m.start() <= limit]
        s = s[:at[0]] if at else ""
    return s if len(s.split()) >= 2 else ""


def _gloss_doers(answer: Text, asked_id: str) -> str:
    """A doer answer explains, once, a person or role it names after "oleh": "Lancingan dijunjung oleh yajamana." read
    as a word the user may not know (user, 2026-11-12: "No explanation of 'yajamana'") -> "... oleh yajamana (orang yang
    punya upacara)". Not the asked term itself, nor a name a bracket or "yaitu" already explains."""
    global _DOER_NAMES
    content, resolver = get_content(), get_resolver()
    if _DOER_NAMES is None:
        # (no everyday word: "digunakan oleh warga (berarti anggota suatu kelompok ...)" explained nothing -- snapshot)
        _DOER_NAMES = sorted(((n, i) for i, n in content.entity_name.items()
                              if content.entity_type.get(i) in _DOER_GLOSS_TYPES and n
                              and not all(_is_everyday_word(w, resolver) for w in n.split())),
                             key=lambda x: len(x[0]), reverse=True)
    # found on the text as it is, longest name first and no two overlapping: "oleh pemangku kawitan setempat" is no
    # "oleh pemangku" -- it got both glosses, one inside the other (snapshot 2026-11-12)
    spans: List[tuple] = []
    for name, eid in _DOER_NAMES:
        if eid == asked_id or any(e == eid for _, _, e in spans):
            continue
        m = re.search(rf"\boleh\s+(?:para\s+|sang\s+)?({re.escape(name)})(?![\w-])(?!\s*\()(?!\s*,?\s*yaitu\b)",
                      answer, re.I)
        if m and not any(a <= m.start(1) < b or m.start(1) <= a < m.end(1) for a, b, _ in spans):
            spans.append((m.start(1), m.end(1), eid))
    for _, end, eid in sorted(spans, key=lambda x: x[0], reverse=True):
        g = re.sub(r"^berarti\s+", "", _short_gloss(eid), flags=re.I)
        name_words = content.entity_name.get(eid, "").lower().split()
        # (not a gloss that says the name again: "pemangku kawitan setempat (pemangku (pengempon pura) dari ...)")
        if g and name_words and g.lower().split()[0] != name_words[0]:
            answer = f"{answer[:end]} ({_decap(g)}){answer[end:]}"
    return answer


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


_CONJUNCTIONS_MODALS: frozenset = frozenset({
    "kalau", "kalo", "klo", "jika", "bila", "apabila", "bisa", "boleh", "harus", "perlu",
    "ada", "kok", "kenapa", "mengapa", "gimana", "bagaimana", "kenapakah", "kenapaan",
    "melakukan", "dilakukan", "lakukan"
})


def _card_uses(topic, words: List[str], extra_words: Optional[set] = None) -> bool:
    """Every word is in the topic's own card (its definition and name), on its first five letters,
    or matches via Balinese synonym (e.g. tukad -> sungai) or appears in recent bot utterances."""
    dwords = set(_WORD_RE.findall((_definition_text(topic.entity) + " " + topic.entity["name"]).lower()))
    if extra_words:
        dwords |= extra_words
    def matches(w: str) -> bool:
        syn = _BALINESE_SYNONYMS.get(w, w)
        for target in (w, syn):
            if any(d[:5] == target[:5] if len(target) >= 5 else d == target for d in dwords):
                return True
        return False
    return all(matches(w) for w in words)


def _quotes_topic(leftover: List[str], current_entity: Optional[Text], resolver, tracker: Optional[Any] = None) -> bool:
    """A message naming no term whose every content word is in the topic's own card asks about the topic:
    "karunia seperti apa yang dimaksud?" after "Anugerah raja adalah karunia dari raja ..." got "Maaf, saya tidak
    menemukan 'karunia' ... Mungkin maksud Anda: arjuna?" (user, 2026-10-28). Pointing words (maksud, dimaksud,
    contohnya ...) are no content."""
    topic = resolver.resolve(current_entity) if current_entity else None
    words = [re.sub(r"nya$", "", w) for w in leftover if w not in _STOPWORDS_ID and w not in _FOLLOW_UP_META
             and w not in _CONJUNCTIONS_MODALS and w not in _QUESTION_WORDS
             and not {w, re.sub(r"nya$", "", w), re.sub(r"^di", "", w)} & _POINTER_WORDS]
    if not topic or not words:
        return False
    extra = set()
    if tracker is not None:
        for u in _recent_bot_utterances(tracker, n=2):
            extra.update(_WORD_RE.findall(u.lower()))
    return _card_uses(topic, words, extra_words=extra)


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

    @_presented
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


def _said_before_note(answer: Text, tracker: Tracker, enriched: List[Dict[str, Any]]) -> Text:
    """An aspect answer that can only open with the card's definition sentence, which the bot's last answer opened
    with too, says so: "fungsinya apa?" after "apa itu wadah?" repeated the definition's first sentence as if new
    (sweep 2026-11-13). The answer stays -- a re-asked question wants it again (2026-10-08), and gets it unmarked, as
    does a question re-asked in other words whose answer opens with its own aspect ("Ngaben dipimpin oleh ...")."""
    previous = _last_bot_utterance(tracker)
    if not previous or not enriched or _MISS_LEAD_RE.match(answer):
        return answer

    def norm(t: Text) -> str:
        return " ".join(_WORD_RE.findall(_present(t).lower()))
    first = norm((_sentences(answer) or [""])[0])
    lead = norm(_first_sentence(_deterministic_answer([dict(enriched[0], aspect_facts=[])]), limit=10 ** 6))
    if (len(first.split()) < 4 or first != lead or norm((_sentences(previous) or [""])[0]) != lead
            or norm(tracker.latest_message.get("text") or "") == norm(_previous_user_message(tracker))):
        return answer
    return f"Seperti disebutkan sebelumnya, {_decap(answer)}"


class ActionTemplateAnswer(Action):
    """The simple-question intents (tanya_definisi, tanya_makna, ...): a template answer from the
    KB, with no LLM call. A message that is not simple after all (_template_route), names nothing
    the scan finds, or has no template for its term goes to ActionGraphRAG, as a misfiled question
    goes from ActionOutOfScope. Each turn's route is logged (routing_log.jsonl)."""

    def name(self) -> Text:
        return "action_jawab_template"

    @_presented
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
        # a follow-up on a case a turn before told goes on with that case, which no template of the named word answers:
        # "ngaben jenis apa itu?" after "saudara saya hilang di laut ..." got Ngaben's nine kinds (style test 2026-11-06)
        if family is not None and _case_follow_up(tracker, user_msg):
            family, why_not = None, "case follow-up"
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
                    answer = _said_before_note(_tidy_answer(_in_asked_names(answer, enriched, user_msg)), tracker,
                                               enriched)
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

    @_presented
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
        if _tells_only(user_msg):
            # it asks nothing: what to ask, not a free-form answer (bot test 2026-11-05)
            dispatcher.utter_message(text=_invitation(user_msg))
            return []

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
# the words of a goodbye or a thank-you: without one, a message NLU read as pamit that asks something is answered
_FAREWELL_RE = re.compile(r"\b(?:terima\s*kasih|makasih|trims|thanks?|thx|tq|dadah|bye|sampai\s+jumpa|selamat\s+tinggal"
                          r"|pamit|cukup|(?:sudah|udah|segitu)\s+(?:dulu|aja)|selesai|oke|ok|sip|mantap|santih)\b", re.I)


class ActionSapa(Action):
    """NLU said sapa (a greeting). A Ngaben question it misfiles is answered, by ActionOutOfScope's test
    (`_names_kb_term`): "boleh foto saat ngaben?" got "Om Swastiastu, Saya asisten ..." (the 12 evaluation
    categories, 2026-10-27)."""

    def name(self) -> Text:
        return "action_sapa"

    @_presented
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


class ActionPamit(Action):
    """NLU said pamit (a goodbye): utter_pamit -- unless the message only says it wants to ask ("saya mau nanya" was
    read as pamit, bot test 2026-11-05), which _presented answers."""

    def name(self) -> Text:
        return "action_pamit"

    @_presented
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # a question with no farewell in it is answered, as ActionSapa does for a misread greeting: "apakah harus potong
        # gigi dulu?" and "boleh dikubur dulu?" got "Om Santih Santih Santih, Semoga bermanfaat." (style test 2026-11-06)
        user_msg = tracker.latest_message.get("text", "")
        if not _FAREWELL_RE.search(user_msg):
            if _names_kb_term(user_msg):
                return ActionGraphRAG().run(dispatcher, tracker, domain)
            if _ASKS_RE.search(user_msg) or _whether_question(user_msg) or "?" in user_msg:
                return ActionLLMFallback().run(dispatcher, tracker, domain)
        dispatcher.utter_message(response="utter_pamit")
        return []


_BOT_CHALLENGE_RE = re.compile(r"\b(?:bot|robot|manusia|ai|asisten|mesin|kamu|anda|lu|lo|siapa\s+(?:kamu|anda))\b", re.I)


class ActionBotChallenge(Action):
    """NLU said bot_challenge ("kamu bot?"): utter_iamabot -- unless the message asks nothing of the bot and names a KB
    term: "kalau mamukur?" after "ngaben tu apa sih" was read as bot_challenge and got "Saya asisten AI untuk upacara
    adat Bali." (2026-11-12). As ActionPamit does for a misread goodbye."""

    def name(self) -> Text:
        return "action_bot_challenge"

    @_presented
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        named = [m for m, _ in _mentioned_terms(user_msg, get_resolver())[0] if m.via != "fuzzy"]
        if not _BOT_CHALLENGE_RE.search(user_msg) and named:
            return ActionGraphRAG().run(dispatcher, tracker, domain)
        dispatcher.utter_message(response="utter_iamabot")
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

    @_presented
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        # (a situation the corpus names, told in everyday words, too: "nenek saya sudah dikubur 5 tahun lalu" is asti
        # wedana's case, style test 2026-11-06)
        if (_names_kb_term(user_msg) or _topic_follow_up(user_msg, tracker.get_slot("current_entity"))
                or any(rx.search(user_msg) for _, rx in _SITUATION_TERMS)):
            return ActionGraphRAG().run(dispatcher, tracker, domain)
        if _tells_only(user_msg) and _DEATH_NEWS_RE.search(user_msg):
            # someone telling of a death is no off-topic message ("bapak saya meninggal kemarin ...", 2026-11-05)
            dispatcher.utter_message(text=_invitation(user_msg))
            return []
        dispatcher.utter_message(response="utter_out_of_scope")
        return []

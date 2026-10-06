"""Resolve a user's free-text wording to a canonical KB entity id.

Mirrors the resolution pipeline documented in Graphing/kb/methodology.md and the
`fuzzy_match_*` helpers in the reference bot, but Python-side (the graph does not
store aliases in a queryable way).

Order: exact (name/alias) -> force_merge -> modifier-strip retry -> orthographic
key -> token-checked rapidfuzz.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

load_dotenv(find_dotenv())

_BOT_DIR = Path(__file__).resolve().parent
_KB_DIR = (_BOT_DIR / os.getenv("KB_DIR", "../../Graphing/kb")).resolve()

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


def _norm(s: str) -> str:
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
_SUFFIXES = ("nya", "an", "kan", "i")
# Head words that only say what kind of thing a term is -- a query may carry them
# without the entity name doing so ("upacara pamerasan" -> pamerasan) and vice versa.
_HEAD_WORDS = {"upacara", "prosesi", "ritual", "acara", "istilah", "konsep", "kata",
               "sarana", "banten"}
# Aspect words a query may wrap around a term ("kelengkapan sodaan", "unsur tri
# sarira", "fungsi kawangen") -- ignored on the query side only.
_ASPECT_WORDS = {"kelengkapan", "kelengkapannya", "unsur", "unsurnya", "bagian",
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


def _token_match(a: str, b: str, anchored: bool = True, common: bool = False, named: bool = False) -> bool:
    """Symmetric. The flags describe the user's word: `common`, an everyday Indonesian
    word, matches only as written (plus a suffix), never through an edit; `named`, a word
    of some KB name, is a real word too -- only a vowel slip (spelling variant) may change
    it: "kahang" (naga kahang) is not kajang, "tunjung" not punjung (2026-10-01)."""
    oa, ob = _ortho_token(a), _ortho_token(b)
    if oa == ob:
        return True
    for suf in _SUFFIXES:
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
    if common:
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


def _load_common_words(path: Path = _COMMON_WORDS_FILE, min_count: int = 3) -> frozenset:
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            tok = line.split(maxsplit=1)[0] if line.strip() else ""
            if tok.isalpha() and tok.islower():
                counts[tok] = counts.get(tok, 0) + 1
    return frozenset(w for w, c in counts.items() if c >= min_count) | _QUESTION_WORDS


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
        self.keep_distinct: set[str] = {_norm(w) for w in res.get("keep_distinct", [])}
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
            self.surface.setdefault(_norm(e["name"]), e["id"])
            for a in e.get("aliases", []):
                key = _norm(a)
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
            _id = self.surface.get(_norm(v)) or (v if v in self.by_id else None)
            if _id and _id not in excluded_ids:
                self.force_merge[_norm(k)] = _id

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
        s = _norm(text)
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

        # 4b. one edit on the whole orthographic key of a long name, if it is unique.
        # "typo", not "ortho": the bot must not call a misspelling "sebutan lain".
        # From 9 letters: "pegabenan" (pengabenan, a force_merge key the fuzzy tier never
        # sees) got "Mungkin maksud Anda: ngaben, benang?" (2026-10-02)
        # A 9-letter word must also keep both ends ("petilasan" is no patulangan).
        key = _ortho_key(raw)
        if len(key) >= 9 and raw not in self.common_words:
            hits = {self.ortho[k] for k in self._long_keys
                    if abs(len(k) - len(key)) <= 1 and Levenshtein.distance(k, key) <= 1
                    and (len(key) >= 10 or (k[:2] == key[:2] and k[-2:] == key[-2:]))}
            if len(hits) == 1:
                _id = hits.pop()
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

    def _tokens_cover(self, query: str, cand: str) -> bool:
        skip = set(self.strip_modifiers) | _HEAD_WORDS
        q = [t for t in re.split(r"[\s\-/]+", query) if t and t not in skip | _ASPECT_WORDS]
        c = [t for t in re.split(r"[\s\-/]+", cand) if t and t not in skip]
        if not q or not c:
            return False
        anchored = len(q) >= 2 and any(_ortho_token(a) == _ortho_token(b) for a in q for b in c)
        common, named = self.common_words, self.name_tokens
        flags = {a: (a in common, _ortho_token(a) in named) for a in q}
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

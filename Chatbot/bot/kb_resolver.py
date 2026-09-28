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
import random
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


def _token_match(a: str, b: str) -> bool:
    oa, ob = _ortho_token(a), _ortho_token(b)
    if oa == ob:
        return True
    for suf in _SUFFIXES:
        if len(ob) >= 4 and oa == ob + suf:
            return True
        if len(oa) >= 4 and ob == oa + suf:
            return True
    # one-edit typos on any token ("wah"/"bwah", "citra"/"cita"); a looser ratio
    # only on longer tokens -- "pandawa"/"pranawa" (2 edits, ratio 86) and
    # "surya"/"sukra" are different words, not typos.
    if min(len(oa), len(ob)) >= 3 and Levenshtein.distance(oa, ob) <= 1:
        return True
    return min(len(oa), len(ob)) >= 6 and fuzz.ratio(oa, ob) >= 88


@dataclass
class Match:
    id: str
    name: str
    via: str          # "exact" | "alias" | "force_merge" | "strip" | "fuzzy"
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

        self._choices = list(self.surface.keys())
        # fuzzy candidates are also drawn by orthographic key, so heavy spelling
        # variation ("ssoddaan", "butha") still reaches the token check below
        self._ortho_choices: dict[str, str] = {}
        for key in self._choices:
            self._ortho_choices.setdefault(_ortho_key(key), key)

        # type -> [entity dict], for "daftar istilah" answers
        self.by_type: dict[str, list[dict]] = {}
        for e in ents:
            if e["id"] in excluded_ids:
                continue
            self.by_type.setdefault((e.get("type") or "").upper(), []).append(e)

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
        return (all(any(_token_match(a, b) for b in c) for a in q)
                and all(any(_token_match(b, a) for a in q) for b in c))

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

    def list_type(self, tipe: str) -> list[dict]:
        """Entities of a KB type. `tipe` is a human phrase ('tahapan upacara')."""
        key = re.sub(r"\s+", "_", _norm(tipe)).upper()
        aliases = {
            "SARANA": "SARANA_RITUAL", "SARANA_RITUAL": "SARANA_RITUAL",
            "PERLENGKAPAN": "SARANA_RITUAL", "PERALATAN": "SARANA_RITUAL",
            "ISTILAH": "ISTILAH_UMUM_RITUAL", "ISTILAH_UMUM": "ISTILAH_UMUM_RITUAL",
            "ISTILAH_UMUM_RITUAL": "ISTILAH_UMUM_RITUAL",
            "TAHAPAN": "TAHAPAN_UPACARA", "TAHAP": "TAHAPAN_UPACARA",
            "TAHAPAN_UPACARA": "TAHAPAN_UPACARA", "PROSESI": "TAHAPAN_UPACARA",
            "KONSEP": "KONSEP_FILOSOFIS", "KONSEP_FILOSOFIS": "KONSEP_FILOSOFIS",
            "FILOSOFI": "KONSEP_FILOSOFIS", "FILSAFAT": "KONSEP_FILOSOFIS",
            "BANGUNAN": "BANGUNAN_RITUAL", "BANGUNAN_RITUAL": "BANGUNAN_RITUAL",
            "TEMPAT": "BANGUNAN_RITUAL",
            "ENTITAS_KEAGAMAAN": "ENTITAS_KEAGAMAAN", "DEWA": "ENTITAS_KEAGAMAAN",
            "TOKOH": "ENTITAS_KEAGAMAAN",
            "RITUAL_KEMATIAN": "RITUAL_KEMATIAN", "RITUAL": "RITUAL_KEMATIAN",
            "UPACARA": "RITUAL_KEMATIAN", "JENIS_NGABEN": "RITUAL_KEMATIAN",
            "TIRTHA": "TIRTHA_SUCI", "TIRTHA_SUCI": "TIRTHA_SUCI",
            "AIR_SUCI": "TIRTHA_SUCI", "TIRTA": "TIRTHA_SUCI",
            "HUKUM_ADAT": "KONSEP_HUKUM_ADAT", "KONSEP_HUKUM_ADAT": "KONSEP_HUKUM_ADAT",
            "ADAT": "KONSEP_HUKUM_ADAT", "AWIG_AWIG": "KONSEP_HUKUM_ADAT",
            "NASKAH": "NASKAH_SUCI", "NASKAH_SUCI": "NASKAH_SUCI", "LONTAR": "NASKAH_SUCI",
        }
        canon = aliases.get(key, key)
        return list(self.by_type.get(canon, []))

    def search(self, query: str, k: int = 12) -> list[dict]:
        """Free-text search over names + aliases (substring, then fuzzy)."""
        q = _norm(query)
        q = re.sub(r"^(cari|carikan|temukan|daftar|sebutkan|istilah|kata|apa saja)\s+", "", q).strip()
        q = re.sub(r"\b(yang|tentang|soal|terkait|mengandung|berhubungan dengan|berkaitan dengan|di ngaben|dalam ngaben)\b", " ", q).strip()
        q = re.sub(r"\s+", " ", q).strip(" ?.!,")
        if not q:
            return []
        out: list[dict] = []
        seen: set[str] = set()
        for surface, _id in self.surface.items():
            if q in surface and _id not in seen:
                seen.add(_id)
                out.append(self.by_id[_id])
        if len(out) < k:
            for name, score, _ in process.extract(q, self._choices, scorer=fuzz.WRatio, limit=k * 2):
                if score < 72:
                    continue
                _id = self.surface[name]
                if _id not in seen:
                    seen.add(_id)
                    out.append(self.by_id[_id])
        return out[:k]

    def random_entity(self, with_definition: bool = True) -> dict:
        candidates = [e for e in self.by_id.values() if e["id"] not in self.excluded_ids]
        pool = [e for e in candidates if e.get("definition")] if with_definition else None
        pool = pool or candidates
        return random.choice(pool)

    def suggest(self, text: str, k: int = 3, threshold: int = 60) -> list[str]:
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

"""Resolve a user's free-text wording to a canonical KB entity id.

Mirrors the resolution pipeline documented in Graphing/kb/METHODOLOGY.md and the
`fuzzy_match_*` helpers in the reference bot, but Python-side (the graph does not
store aliases in a queryable way).

Order: exact (name/alias) -> force_merge -> modifier-strip retry -> rapidfuzz.
"""
from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from rapidfuzz import fuzz, process

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
    r"^(apa itu|apa yang dimaksud( dengan)?|apa arti( dari| kata)?|apa sih|"
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
        ents = json.loads((kb_dir / "entities.json").read_text(encoding="utf-8"))
        self.by_id: dict[str, dict] = {e["id"]: e for e in ents}

        res = json.loads((kb_dir / "entity_resolution.json").read_text(encoding="utf-8"))
        self.force_merge: dict[str, str] = {
            _norm(k): v for k, v in res.get("force_merge", {}).items()
            if not k.startswith("_")
        }
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

        self._choices = list(self.surface.keys())

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
            if _id in self.by_id and _id not in self.excluded_ids:
                return Match(_id, self.by_id[_id]["name"], "force_merge", 100.0, self.by_id[_id])

        # 3. modifier-strip retry (never for keep_distinct surface forms)
        if raw not in self.keep_distinct:
            stripped = self._strip_modifiers(raw)
            if stripped and stripped != raw and stripped in self.surface:
                _id = self.surface[stripped]
                return Match(_id, self.by_id[_id]["name"], "strip", 100.0, self.by_id[_id])

        # 4. fuzzy
        # WRatio's partial-matching component can score a short, unrelated string
        # deceptively high against a much longer candidate (e.g. "ether" vs "kain
        # putih panjangnya puluhan meter" scores 80) -- plain fuzz.ratio compares
        # the full strings and isn't fooled by that, so it's required too as a
        # sanity floor. Checking only the single best WRatio hit (extractOne) can
        # pick a longer phrase that beats the real match on WRatio's partial
        # component yet fails the ratio floor, even when a shorter, correct
        # candidate elsewhere in the list would have passed both -- e.g. "tirte"
        # -> "tirta yadnya pranawa" wins WRatio=80 over plain "tirtha"'s
        # WRatio=73, but only "tirtha" clears the ratio floor. Check the top few
        # WRatio candidates and take the first that also clears the ratio floor,
        # instead of only ever checking the single top-ranked one.
        for cand, score, _ in process.extract(raw, self._choices, scorer=fuzz.WRatio, limit=5):
            if score >= fuzzy_threshold and fuzz.ratio(raw, cand) >= 60:
                _id = self.surface[cand]
                return Match(_id, self.by_id[_id]["name"], "fuzzy", float(score), self.by_id[_id])

        return None

    def resolve_many(self, text: str, limit: int = 2, fuzzy_threshold: int = 80) -> list[Match]:
        """Resolve every distinct term mentioned in a phrase (for 'beda X dan Y').

        Splits on common Indonesian conjunctions, resolves each side, dedups by id.
        """
        raw = self.clean_query(text)
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

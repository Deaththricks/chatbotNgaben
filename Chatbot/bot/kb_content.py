"""Read-only access to the richer KB layers that are *not* in the graph in a
convenient shape: pre-rendered fact sentences, curated FAQ / glossary passages,
the predicate -> Indonesian sentence templates, and predicate families used to
answer targeted questions (fungsi / bahan / lokasi / waktu / pelaku / simbol).

The Neo4j graph stays the source of truth for structure (definition, type,
broader spine, attributes, relation edges). This module only adds nicer phrasing
and the two hand-written passage kinds (`faq`, `glossary`).

Files live in KB_DIR (.env) or ../../Graphing/kb by default -- same as kb_resolver.
"""
from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

_BOT_DIR = Path(__file__).resolve().parent
_KB_DIR = (_BOT_DIR / os.getenv("KB_DIR", "../../Graphing/kb")).resolve()

_CONF_RANK = {"HIGH": 0, "MED": 1, "LOW": 2}

# predicate -> which targeted question it answers. A predicate may appear twice.
PREDICATE_FAMILIES: Dict[str, set] = {
    "fungsi": {
        "DIPAKAI_UNTUK", "DIGUNAKAN_UNTUK", "DIGUNAKAN_PADA", "DIGUNAKAN_DALAM",
        "BERFUNGSI_SEBAGAI", "BERPERAN_SEBAGAI", "BERTUJUAN_UNTUK", "BERTUJUAN_AGAR",
        "BERTUJUAN_MENYUCIKAN", "DITUJUKAN_UNTUK", "MEWAJIBKAN", "MENGHILANGKAN",
        "MENGHASILKAN", "MENJAMIN", "TIDAK_MENJAMIN", "DIMOHON", "MEMOHON",
    },
    "bahan": {
        "TERBUAT_DARI", "TERDIRI_DARI", "BERUPA", "BERWUJUD", "BERBENTUK", "BERISI",
        "DIISI_DENGAN", "BERUNSUR", "DIBUNGKUS_DENGAN", "DIIKAT_DENGAN",
        "DIGULUNG_DENGAN", "DIALASI_DENGAN", "DIALASI", "MEMAKAI", "MENGGUNAKAN",
        "DIBERI", "DILENGKAPI", "DISERTAI", "MELIPUTI", "BERASAL_DARI", "DIAMBIL_DARI",
    },
    "lokasi": {
        "DILETAKKAN_DI", "DILETAKKAN_PADA", "BERADA_DI", "DILAKUKAN_DI", "DIBUAT_DI",
        "DIADAKAN_DI", "DIHANYUTKAN_KE", "DIBAWA_KE", "DINAIKKAN_KE", "DIPINDAHKAN_KE",
        "DITURUNKAN_DI", "DIGANTUNGKAN_DI", "DITABURKAN_DI", "DIBARINGKAN_DI",
        "BERSEMAYAM_DI", "BERSTANA_DI", "BERTAHTA", "MENUJU", "BERANGKAT_KE", "KEMBALI_KE",
        "DITARUHKAN_DI_SAMPING", "DITEMPELKAN_DI", "DIPASANG_DI_ATAS",
    },
    "waktu": {
        "DILAKUKAN_SAAT", "DIGUNAKAN_SAAT", "DIBUAT_SAAT", "DISEMBURKAN_SAAT",
        "MENJELANG", "SEBELUM", "SETELAH", "DILAKUKAN_SEBELUM", "DILAKUKAN_SETELAH",
        "DIPERCIKKAN_SEBELUM", "TIDAK_BOLEH_DILAKUKAN_SAAT", "DILAKUKAN_MENJELANG",
    },
    "pelaku": {
        "DILAKUKAN_OLEH", "DIPIMPIN_OLEH", "DIMOHONKAN_OLEH", "DIJUNJUNG_OLEH",
        "DIBUAT_OLEH", "DIMANTRAI_OLEH", "DIBASMI_OLEH", "DIUSUNG", "DIJUNJUNG",
        "DIAJAK_BERKOMUNIKASI_OLEH", "MENDAPAT_PENGARUH_DARI", "DIMOHON_DARI",
        "DIMOHONKAN_DARI",
    },
    "simbol": {
        "MELAMBANGKAN", "MENYIMBOLKAN", "MENUNJUKKAN", "BERARTI", "BERMAKNA",
        "DIPERLAKUKAN_SEPERTI", "DIKENAL_SEBAGAI", "SAMA_DENGAN", "MENJADI",
        "BERUBAH_MENJADI", "MERUPAKAN_PERUBAHAN_DARI", "LAHIR_DALAM_WUJUD",
    },
}


def _loadl(path: Path) -> List[dict]:
    txt = path.read_text(encoding="utf-8")
    return [json.loads(block) for block in txt.split("\n\n") if block.strip()]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class KbContent:
    def __init__(self, kb_dir: Path = _KB_DIR) -> None:
        self.kb_dir = kb_dir

        phrases = json.loads((kb_dir / "relation_phrases.json").read_text(encoding="utf-8"))
        self.templates: Dict[str, str] = {
            k: v["template"] for k, v in phrases.items() if not k.startswith("_")
        }

        self.facts_by_subj: Dict[str, List[dict]] = {}
        self.facts_by_obj: Dict[str, List[dict]] = {}
        self.all_facts: List[dict] = []
        for f in _loadl(kb_dir / "facts.jsonl"):
            self.all_facts.append(f)
            self.facts_by_subj.setdefault(f["subject_id"], []).append(f)
            self.facts_by_obj.setdefault(f["object_id"], []).append(f)

        self.faq_by_ent: Dict[str, List[dict]] = {}
        self.glossary_by_ent: Dict[str, List[dict]] = {}
        self.all_faq: List[dict] = []
        for p in _loadl(kb_dir / "passages.jsonl"):
            kind = p.get("kind")
            if kind == "faq":
                self.all_faq.append(p)
            if kind not in ("faq", "glossary"):
                continue
            bucket = self.faq_by_ent if kind == "faq" else self.glossary_by_ent
            for eid in p.get("entity_ids", []):
                bucket.setdefault(eid, []).append(p)

    # -- templates -----------------------------------------------------------
    def render(self, predicate: str, subj: str, obj: str) -> str:
        tpl = self.templates.get(predicate.upper())
        if tpl:
            return tpl.format(s=subj, o=obj)
        verb = predicate.lower().replace("_", " ")
        return f"{subj} {verb} {obj}"

    def render_attr(self, predicate: str, subj: str, value: str) -> str:
        return self.render(predicate, subj, value)

    # -- facts -------------------------------------------------------------
    def _dedup_sorted(self, rows: List[dict]) -> List[dict]:
        rows = sorted(rows, key=lambda f: _CONF_RANK.get(f.get("confidence"), 3))
        seen, out = set(), []
        for f in rows:
            key = _norm(f["text"].rstrip("."))
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out

    def facts_for(self, entity_id: str, limit: int = 6) -> List[str]:
        rows = self.facts_by_subj.get(entity_id, []) + self.facts_by_obj.get(entity_id, [])
        return [f["text"].rstrip(".").strip() for f in self._dedup_sorted(rows)][:limit]

    def facts_in_family(self, entity_id: str, family: str, limit: int = 6) -> List[str]:
        preds = PREDICATE_FAMILIES.get(family, set())
        rows = [
            f for f in self.facts_by_subj.get(entity_id, [])
            if (f.get("predicate") or "").upper() in preds
        ]
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
    def faq_for(self, entity_id: str) -> List[dict]:
        return self.faq_by_ent.get(entity_id, [])

    def faq_search(self, text: str, k: int = 3) -> List[dict]:
        toks = [t for t in re.findall(r"\w+", _norm(text)) if len(t) > 3]
        scored = []
        for p in self.all_faq:
            hay = _norm(p.get("text", ""))
            score = sum(1 for t in toks if t in hay)
            if score:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:k]]

    def glossary_for(self, entity_id: str) -> Optional[str]:
        rows = self.glossary_by_ent.get(entity_id, [])
        if not rows:
            return None
        text = rows[0].get("text", "")
        return text.split(":", 1)[1].strip() if ":" in text else text.strip()

    def best_definition(self, entity_id: str, graph_definition: Optional[str] = None) -> Optional[str]:
        return graph_definition or self.glossary_for(entity_id) or self.definition_facts(entity_id)


_CONTENT: Optional[KbContent] = None


def get_content() -> KbContent:
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = KbContent()
    return _CONTENT

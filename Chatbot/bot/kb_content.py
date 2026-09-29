"""Read-only access to the richer KB layers that are *not* in the graph in a
convenient shape: pre-rendered fact sentences, curated FAQ / glossary passages,
text-only entity attributes, the predicate -> Indonesian sentence templates, and
the predicate families that say which question aspect (makna / letak / waktu /
fungsi / ...) each edge or attribute answers.

The Neo4j graph stays the source of truth for structure (definition, type,
broader spine, relation edges). This module adds phrasing, the two hand-written
passage kinds (`faq`, `glossary`), and the attributes (LITERAL facts) read from
entities.json, which the graph query does not return.

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

# Question aspect -> the predicates (edges AND text-only attributes) that answer it.
# A predicate may sit in more than one family. actions.py maps question wording to a
# family and shows only that family's edges/attributes; kb_lint (check 11) requires
# every attribute predicate to be in some family -- an unmapped one could never be
# shown. "cara" (how / what happens) is the broadest and is used only when no other
# aspect matches; "asal_kata" serves word-meaning questions.
PREDICATE_FAMILIES: Dict[str, set] = {
    "sebutan_lain": {"SAMA_DENGAN", "DIKENAL_SEBAGAI", "ADALAH", "SEBUTAN_HALUS_UNTUK"},
    "jenis": {"TERMASUK_JENIS", "CONTOH"},
    "tahapan": {
        "BAGIAN_DARI", "SEBELUM", "SETELAH", "DILAKUKAN_SEBELUM", "DILAKUKAN_SETELAH",
        "DILAKUKAN_MENJELANG", "DIIKUTI_OLEH",
    },
    "komposisi": {
        "BERUPA", "TERDIRI_DARI", "BERISI", "DIISI_DENGAN", "DIISI", "BERUNSUR", "MELIPUTI",
        "DILENGKAPI", "TERBUAT_DARI", "DISERTAI", "DIBUNGKUS_DENGAN", "TERMASUK_JENIS",
        "BAGIAN_DARI", "DISISIPI", "MENGANDUNG",
    },
    "asal_kata": {"BERASAL_DARI_KATA", "BERARTI_HARFIAH", "BERASAL_DARI", "SEBUTAN_BERASAL_DARI"},
    "simbol": {
        "MELAMBANGKAN", "MENYIMBOLKAN", "BERMAKNA", "BERARTI", "BERARTI_HARFIAH",
        "BERAKAR_PADA", "BERDASARKAN", "MENUNJUKKAN", "MEWUJUDKAN",
        "MERUPAKAN_PERWUJUDAN_DARI", "DIPERLAKUKAN_SEPERTI", "DIANGGAP_SEBAGAI",
        "BERSINAR_BAGAIKAN",
    },
    "lokasi": {
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
    },
    "waktu": {
        "DILAKUKAN_SAAT", "DIGUNAKAN_SAAT", "DIBUAT_SAAT", "DISEMBURKAN_SAAT",
        "DINYALAKAN_SAAT", "MENJELANG", "SEBELUM", "SETELAH", "DILAKUKAN_SEBELUM",
        "DILAKUKAN_SETELAH", "DIPERCIKKAN_SEBELUM", "TIDAK_BOLEH_DILAKUKAN_SAAT",
        "DILAKUKAN_MENJELANG", "DILAKSANAKAN", "DILAKUKAN", "DIADAKAN_JIKA",
        "DILAKUKAN_DALAM_HAL", "SYARAT", "DIGUNAKAN_SEBELUM", "DIBONGKAR_SETELAH",
        "DIBUNGKUS_SETELAH", "MENENTUKAN_WAKTU",
    },
    # the offerings / equipment a ceremony or stage uses (sarana upacara)
    "sarana": {
        "DIGUNAKAN_DALAM", "DIGUNAKAN_PADA", "DIGUNAKAN_SAAT", "DIGUNAKAN_UNTUK", "DIPAKAI_UNTUK",
        "MENGGUNAKAN", "MEMAKAI",
    },
    "pelaku": {
        "DILAKUKAN_OLEH", "DIPIMPIN_OLEH", "DIMOHONKAN_OLEH", "DIJUNJUNG_OLEH",
        "DIBUAT_OLEH", "DIMANTRAI_OLEH", "DIBASMI_OLEH", "DIUSUNG", "DIJUNJUNG",
        "DIAJAK_BERKOMUNIKASI_OLEH", "MENDAPAT_PENGARUH_DARI", "DIMOHON_DARI",
        "DIMOHONKAN_DARI", "DIAMBIL_OLEH", "DIPANGKU_OLEH", "DILAKUKAN_ANTARA",
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
    },
    "ciri": {
        "BERWARNA", "MEMILIKI_TINGKAT", "BERUKURAN_PANJANG", "SEPANJANG", "BERBENTUK",
        "DIBUAT_BERBENTUK", "BERWUJUD", "MEMILIKI", "DIGUNAKAN_SEBANYAK", "MEMPERTAHANKAN",
        "TIDAK_MENGGUNAKAN", "BERVARIASI_DALAM", "SEBANDING_DENGAN", "MENYEBARKAN",
        "HARUS_DIRASAKAN_SEBAGAI", "DISESUAIKAN_DENGAN", "MENJADI_STANDAR", "MEMBERIKAN",
    },
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

        phrases = json.loads((kb_dir / "tuning" / "relation_phrases.json").read_text(encoding="utf-8"))
        self.templates: Dict[str, str] = {
            k: v["template"] for k, v in phrases.items() if not k.startswith("_")
        }

        self.facts_by_subj: Dict[str, List[dict]] = {}
        self.facts_by_obj: Dict[str, List[dict]] = {}
        self.all_facts: List[dict] = []
        for f in _loadl(kb_dir / "output" / "facts.jsonl"):
            self.all_facts.append(f)
            self.facts_by_subj.setdefault(f["subject_id"], []).append(f)
            self.facts_by_obj.setdefault(f["object_id"], []).append(f)

        # canonical definitions as build_kb.py resolved them (glossary, or a curated
        # row). best_definition() used to consult only the glossary passages, so a
        # child node whose definition came from a curated row (e.g. sawa_prateka)
        # reached the LLM with no target_definition at all.
        ents = json.loads((kb_dir / "output" / "entities.json").read_text(encoding="utf-8"))
        self.entity_def: Dict[str, str] = {e["id"]: e["definition"] for e in ents if e.get("definition")}
        self.entity_name: Dict[str, str] = {e["id"]: e["name"] for e in ents}
        # text-only facts (LITERAL rows): {id: {PREDICATE: [value, ...]}}
        self.attributes: Dict[str, Dict[str, List[str]]] = {
            e["id"]: {p: [a["value"] for a in vals] for p, vals in e["attributes"].items()}
            for e in ents if e.get("attributes")
        }

        self.faq_by_ent: Dict[str, List[dict]] = {}
        self.glossary_by_ent: Dict[str, List[dict]] = {}
        self.all_faq: List[dict] = []
        for p in _loadl(kb_dir / "output" / "passages.jsonl"):
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

    def attribute_sentences(self, entity_id: str, predicates: set) -> List[str]:
        """The entity's text-only facts whose predicate is in `predicates`, as sentences."""
        name = self.entity_name.get(entity_id, entity_id)
        return [self.render_attr(p, name, v)
                for p, vals in self.attributes.get(entity_id, {}).items() if p in predicates
                for v in vals]

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

    # "ngaben" is the corpus topic word -- it appears in nearly every FAQ, so
    # overlapping on it alone is not a meaningful relevance signal.
    _GENERIC_TOKENS = {"ngaben"}

    def faq_search(self, text: str, k: int = 3, min_score: int = 2) -> List[dict]:
        toks = [t for t in re.findall(r"\w+", _norm(text))
                if len(t) > 3 and t not in self._GENERIC_TOKENS]
        scored = []
        for p in self.all_faq:
            hay = _norm(p.get("text", ""))
            score = sum(1 for t in toks if t in hay)
            if score >= min_score:
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
        return (graph_definition or self.entity_def.get(entity_id) or self.glossary_for(entity_id)
                or self.definition_facts(entity_id))


_CONTENT: Optional[KbContent] = None


def get_content() -> KbContent:
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = KbContent()
    return _CONTENT

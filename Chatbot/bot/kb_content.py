"""Read-only access to the richer KB layers that are *not* in the graph in a
convenient shape: pre-rendered fact sentences, glossary passages, text-only entity
attributes, the predicate -> Indonesian sentence templates, and the predicate
families that say which question aspect (makna / letak / waktu / fungsi / ...) each
edge or attribute answers.

The Neo4j graph stays the source of truth for structure (definition, type,
broader spine, relation edges). This module adds phrasing, the glossary
definitions, and the attributes (LITERAL facts) read from entities.json, which the
graph query does not return.

Files live in KB_DIR (.env) or ../../Graphing/kb by default -- same as kb_resolver.
"""
from __future__ import annotations

import json
import os
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
        # added 2026-09-30
        "BERDAMPINGAN_DENGAN", "DIGILING_DI_ATAS", "DIHANCURKAN_DI", "DIHUNI", "DIIKAT_PADA",
        "DIOLESKAN_DI", "DIPERSILAKAN_DI", "DIPERSILAKAN_MASUK_KE", "DIPUJA_DI", "DISEMBURKAN_PADA",
        "DISTANAKAN_DI", "KEDIAMAN_DARI", "MENJADI_ALAS", "TEMPAT_MEMUJA", "TERTANAM_TITIP_DI",
        # where it is obtained from ("dari mana diperoleh"), added 2026-10-01
        "DIAMBIL_DARI", "DIMOHON_DARI", "DIMOHONKAN_DARI",
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
    },
    # the offerings / equipment a ceremony or stage uses (sarana upacara)
    "sarana": {
        "DIGUNAKAN_DALAM", "DIGUNAKAN_PADA", "DIGUNAKAN_SAAT", "DIGUNAKAN_UNTUK", "DIPAKAI_UNTUK",
        "MENGGUNAKAN", "MEMAKAI",
        # added 2026-09-30
        "DIPERLUKAN_UNTUK_MEMBUAT", "DILENGKAPKAN_PADA",
    },
    "pelaku": {
        "DILAKUKAN_OLEH", "DIPIMPIN_OLEH", "DIMOHONKAN_OLEH", "DIJUNJUNG_OLEH",
        "DIBUAT_OLEH", "DIMANTRAI_OLEH", "DIBASMI_OLEH", "DIUSUNG", "DIJUNJUNG",
        "DIAJAK_BERKOMUNIKASI_OLEH", "MENDAPAT_PENGARUH_DARI", "DIMOHON_DARI",
        "DIMOHONKAN_DARI", "DIAMBIL_OLEH", "DIPANGKU_OLEH", "DILAKUKAN_ANTARA",
        # added 2026-09-30
        "DIBERIKAN_OLEH", "DIGUNAKAN_OLEH", "DIPERUNTUKKAN_BAGI", "DITENTUKAN_OLEH", "HADIR_DALAM",
        "MELAKSANAKAN", "MEMBUAT",
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
    },
    "ciri": {
        "BERWARNA", "MEMILIKI_TINGKAT", "BERUKURAN_PANJANG", "SEPANJANG", "BERBENTUK",
        "DIBUAT_BERBENTUK", "BERWUJUD", "MEMILIKI", "DIGUNAKAN_SEBANYAK", "MEMPERTAHANKAN",
        "TIDAK_MENGGUNAKAN", "BERVARIASI_DALAM", "SEBANDING_DENGAN", "MENYEBARKAN",
        "HARUS_DIRASAKAN_SEBAGAI", "DISESUAIKAN_DENGAN", "MENJADI_STANDAR", "MEMBERIKAN",
        # added 2026-09-30
        "BERBEDA_DENGAN", "BERGANTUNG_PADA", "BERLAKU_UNTUK", "BERLAWANAN_DENGAN",
        "DILAKUKAN_TANPA", "MENGANUT", "MILIK_DARI", "TANPA", "TIDAK_MEMILIKI", "TIDAK_TERPENGARUH",
        "WARGA_DARI",
        # "kakawin ditulis dalam bahasa kawi" (2026-10-02)
        "DITULIS_DALAM",
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
        "DIPERCIKI_DAN_DIMINUMKAN", "DIPERCIKI_DENGAN", "DIPLASPAS_BERSAMA", "DIPUJA",
        "DISABUNI_DENGAN", "DISAMBUNG_DENGAN", "DISEMBURKAN_PADA", "DISUGUHI",
        "DITAHBISKAN_MELALUI", "DITENTUKAN_OLEH", "DITUTUPI_DENGAN", "DIUSUNG_SECARA",
        "LAHIR_DALAM_WUJUD", "MELARUNGKAN", "MEMPEROLEH", "MENDAPATKAN", "MENERIMA", "MENJALANI",
        "MERUPAKAN_PERUBAHAN_DARI", "TATA_PELAKSANAAN_SAMA_DENGAN",
        # how a baby's body is handled by age (2026-10-02)
        "DIUPACARAI_DENGAN", "DIUPACARAI_DENGAN_CARA",
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


def _norm(s: str) -> str:
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
        its own: tirtha pamlaspas is a kind of tirtha, which is made of air. (None, []) if none."""
        if self.composition_parts(entity_id) or self.is_raw(entity_id):
            return None, []
        frontier = set(self.kind_parents.get(entity_id, set()))
        for _ in range(3):
            for parent in sorted(frontier):
                parts = self.composition_parts(parent)
                if parts:
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
            key = _norm(f["text"].rstrip("."))
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

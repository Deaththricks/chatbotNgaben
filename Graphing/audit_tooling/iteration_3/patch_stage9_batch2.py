# -*- coding: utf-8 -*-
"""Stage 9 batch 2: flag.txt continuation, S1482-S2087 (partial coverage of the
S1482-S2363 range - remainder left for a follow-up pass, see final report).
Skips entries already resolved by Stages 1-8's general fixes (S1688 label,
S1699/S1738 subject coordination, S1747/S2028 temporal-suffix, S1782 antara-clause,
S1963[4] dump bug, S1982 duplication, S2000-S2002 tier, S2055 bahwa-ccomp,
S2124 purpose-oblique) -- ADD-only entries kept where the base fix doesn't restore
the missing content."""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"


def mk(subject, relation, obj, subject_label=None, object_label=None):
    return {
        "subject": subject, "subject_label": subject_label,
        "relation": relation, "object": obj, "object_label": object_label,
        "source": "manual_override",
    }


OVERRIDES = {
    1483: [mk("abu", "DIMASUKKAN_KE_DALAM", "klungah nyuh gading yang dikasturi dan disukutunggalkan", "SARANA_RITUAL")],
    1493: [mk("kemampuan sosial ekonomi", "JENIS_DARI", "standar kedudukan seseorang di masyarakat")],
    1522: [mk("mendiang", "DIANGGAP_SEBAGAI", "seseorang yang masih hidup", "ISTILAH_UMUM_RITUAL")],
    1544: [mk("sawa", "MENYEBARKAN", "bau yang kurang sedap", "ISTILAH_UMUM_RITUAL")],
    1552: [mk("sumpe", "BERFUNGSI_SEBAGAI", "penguat rekatan antar badan peti dengan tutupnya")],
    1558: [mk("sawa", "DIKURUNG_DENGAN", "paplengkungan", "ISTILAH_UMUM_RITUAL")],
    1584: [mk("pitara", "MEWUJUDKAN", "bayangan diri dalam air ening", "KONSEP_FILOSOFIS")],
    1601: [mk("kajang", "BERADA_DI", "plengkungan sawa", "SARANA_RITUAL")],
    1603: [mk("jenazah", "DIBAWA_KE", "setra tempat pembakaran", "ISTILAH_UMUM_RITUAL")],
    1605: [mk("kajang", "DILETAKKAN_DI", "depan pendeta yang memujanya", "SARANA_RITUAL")],
    1629: [mk("kajang", "BERPERAN_SEBAGAI", "atribut nilai martabat warga", "SARANA_RITUAL")],
    1639: [mk("kajang", "DIPUJA_PADA", "pamlaspasan", "SARANA_RITUAL")],
    1642: [mk("pelita kecil", "TERBUAT_DARI", "kulit telur ayam berminyak kelapa", "SARANA_RITUAL")],
    1657: [
        mk("panguryagan", "BERALASKAN", "tembong (nyiru yang tabingnya tinggi)"),
        mk("panguryagan", "BERISI", "bermacam-macam ramuan"),
    ],
    1681: [mk("damar kurung", "DINYALAKAN_SAAT", "ngaben jenis sawa wedana (dan angenan turut dinyalakan)", "SARANA_RITUAL")],
    1713: [mk("adegan", "DIAMBIL_OLEH", "keluarga (yang ngaben)", "SARANA_RITUAL")],
    1717: [mk("adegan", "ADALAH", "tempat atma mendiang", "SARANA_RITUAL")],
    1738: [
        mk("mendiang", "ADALAH", "pemangku", "ISTILAH_UMUM_RITUAL"),
        mk("mendiang", "ADALAH", "pejabat", "ISTILAH_UMUM_RITUAL"),
        mk("mendiang", "ADALAH", "sastrawan", "ISTILAH_UMUM_RITUAL"),
        mk("mendiang", "MEMILIKI_ALIAS", "ida bagus", "ISTILAH_UMUM_RITUAL"),
        mk("mendiang", "MEMILIKI_ALIAS", "ida ayu", "ISTILAH_UMUM_RITUAL"),
    ],
    1753: [mk("mendiang", "AKRAB_DENGAN", "penghadang", "ISTILAH_UMUM_RITUAL")],
    1754: [mk("mendiang", "DITERIMA_SEBAGAI", "warga baru dalam pergaulan alam roh", "ISTILAH_UMUM_RITUAL")],
    1763: [
        mk("sekah abin", "BERPERAN_SEBAGAI", "ciri khusus"),
        mk("banten bebangkit atau pulagembal", "BERPERAN_SEBAGAI", "dasar", "SARANA_RITUAL"),
    ],
    1764: [mk("sekah abin", "DIPANGKU_OLEH", "yang menggelar yadnya")],
    1832: [mk("karma phala orangtua atau leluhur", "DIWARISKAN_KEPADA", "keturunan (dalam batas tertentu)", "KONSEP_FILOSOFIS")],
    1845: [mk("panebusan", "MEMPENGARUHI", "kedudukan pitara", "TAHAPAN_UPACARA")],
    1850: [
        mk("mamutru", "BERASAL_DARI_KATA", "putru"),
        mk("mamutru", "MERUPAKAN_PERUBAHAN_DARI", "pitra"),
    ],
    1931: [mk("recadana atau swasta geni", "MELENGKAPI", "pangabenan")],
    1938: [mk("pengabenan", "DINILAI_SEBAGAI", "tingkat utama", "RITUAL_KEMATIAN")],
    1963: [mk("pering", "MENYERUPAI", "mahkota", "SARANA_RITUAL")],
    1987: [mk("bade jenis", "ADALAH", "bade dalam tata kemasyarakatan pada zaman itu", "SARANA_RITUAL")],
    2002: [mk("bade", "DITUJUKAN_UNTUK", "keluarga yang leluhurnya pernah menjadi punggawa dan pejabat yang sederajat", "SARANA_RITUAL")],
    2003: [
        mk("wadah", "ADALAH", "usungan yang tanpa badawang", "SARANA_RITUAL"),
        mk("wadah", "MEMAKAI", "hiasan boma dan warna kapas terbatas", "SARANA_RITUAL"),
    ],
    2029: [mk("mangle", "BERGANTUNG_PADA", "tingkatan bade atau wadah", "SARANA_RITUAL")],
    2087: [mk("naga banda", "DITUJUKAN_UNTUK", "keluarga tertentu saja", "SARANA_RITUAL")],
    2093: [mk("mendiang", "MEMILIKI", "ikatan erat dengan masyarakat", "ISTILAH_UMUM_RITUAL")],
    2115: [mk("kelompok ini", "ADALAH", "paksa mahayana (kendaraan besar)")],
    2117: [],
    2130: [
        mk("peranda shiwa", "MENEMPATKAN", "diri/jenana pada daya suci hyang widhi", "ENTITAS_KEAGAMAAN"),
        mk("peranda shiwa", "MENEMPATKAN_DIRI_DI", "luar alam duniawi (mula-mula di atas)", "ENTITAS_KEAGAMAAN"),
    ],
    2133: [mk("naga banda", "DIGUNAKAN_SAAT", "palebon", "SARANA_RITUAL")],
}

ADDITIONS = {
    1482: [mk("sawa", "DIBAKAR_DENGAN", "khusuk", "ISTILAH_UMUM_RITUAL"), mk("sawa", "MENJADI", "abu (seluruhnya)", "ISTILAH_UMUM_RITUAL")],
    1514: [mk("adegan", "DISISIPI", "awak-awakaning sawa yang terbuat dari sebilah papan cendana atau majagau tipis", "SARANA_RITUAL")],
    1533: [mk("pengawak", "DIPERLAKUKAN_SAMA_DENGAN", "sawa asli")],
    1556: [mk("panca datu", "DIGUNAKAN_UNTUK", "memohon kepada hyang widhi (restu panca dewata)")],
    1584: [mk("tarpana", "DILAKUKAN_DENGAN", "pujastawa"), mk("tarpana", "DILAKUKAN_OLEH", "ida sang sadaka")],
    1602: [mk("lancingan", "ADALAH", "kain putih (panjangnya puluhan meter)")],
    1603: [mk("lancingan kajang", "DIJUNJUNG_OLEH", "segenap keturunan mendiang")],
    1606: [mk("kajang", "DIHIDUPKAN_DENGAN", "puja", "SARANA_RITUAL")],
    1609: [mk("moksa", "ADALAH", "kembalinya unsur badan manusia ke asalnya (bhuwana agung/pancamahabutha)")],
    1629: [mk("kajang", "MEMILIKI", "nilai dan bobot istimewa", "SARANA_RITUAL")],
    1688: [mk("cili", "TERBUAT_DARI", "rontal (dilapisi kertas emas)")],
    1714: [mk("adegan", "DIBAWA_MENGHADAP", "pendeta", "SARANA_RITUAL")],
    1732: [mk("upadesa", "BERARTI", "tatwa pengarahan hidup")],
    1747: [mk("sekah kangsen", "DISERTAI_DI", "samping jenazah")],
    1776: [mk("uang kepeng", "DIBUNGKUS_DENGAN", "daun dapdap"), mk("uang kepeng", "DIIKAT_DENGAN", "benang tridatu (merah, hitam dan putih)")],
    1783: [mk("mendiang", "MENYERAHKAN", "hak dan berbagai milik yang dulunya ada pada mendiang")],
    1823: [mk("upacara panebusan", "ADALAH", "sesuatu yang mutlak (dalam pengabenan)")],
    1853: [mk("lontar putru", "MEMILIKI_JENIS", "putru sangaskara"), mk("lontar putru", "MEMILIKI_JENIS", "putru saji")],
    1898: [mk("yeh panembak", "DIGUNAKAN_PADA", "pengabenan")],
    1915: [mk("pabersihan", "DILANGSUNGKAN_PADA", "hari senin")],
    2000: [mk("raja bali", "BERASAL_DARI", "gelgel/klungkung")],
    2028: [mk("mangle", "DIGANTUNGKAN_DI", "masing-masing tingkatan bade atau wadah", "SARANA_RITUAL")],
    2034: [mk("mangle", "DILETAKKAN_DI", "wadah", "SARANA_RITUAL")],
    2040: [mk("jenazah", "DITURUNKAN_DI", "kuburan")],
    2045: [mk("patulangan", "BERFUNGSI_SEBAGAI", "tempat pembaringan jenazah (dan dapur pembakaran)")],
    2093: [mk("mendiang", "MEMILIKI", "pertalian intim dengan soal duniawi material")],
    2115: [mk("kelompok (paksa mahayana)", "BERTUGAS_MENGANGKUT", "masyarakat manusia ke alam sana")],
    2117: [mk("peranda buddha", "MEMAKAI", "naga banda (pada palebonnya)", "ENTITAS_KEAGAMAAN")],
    2130: [mk("peranda shiwa", "TURUN_MERESAPI", "alam ini", "ENTITAS_KEAGAMAAN")],
    2166: [mk("payadnyan", "BERDAMPINGAN_DENGAN", "jenazah mendiang")],
}

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = nb["cells"][51]["source"]
text = "".join(src) if isinstance(src, list) else src

BATCH1_MARKER = "    # --- Iteration 3 Stage 9 batch 1 (flag.txt S46-S1477) ---\n"
assert text.count(BATCH1_MARKER) == 2, f"expected 2 occurrences, found {text.count(BATCH1_MARKER)}"
first_idx = text.index(BATCH1_MARKER)
second_idx = text.index(BATCH1_MARKER, first_idx + 1)
OVR_MARKER = text[first_idx:first_idx + len(BATCH1_MARKER)]
# unique anchors: prefix a bit of surrounding context so .replace(..., 1) targets the
# right one even though the marker text itself is identical in both spots.
OVR_CONTEXT = text[first_idx - 40:first_idx + len(BATCH1_MARKER)]
ADD_CONTEXT = text[second_idx - 40:second_idx + len(BATCH1_MARKER)]
assert OVR_CONTEXT != ADD_CONTEXT
assert text.count(OVR_CONTEXT) == 1
assert text.count(ADD_CONTEXT) == 1


def fmt_relation(r):
    def pyval(v):
        return "None" if v is None else json.dumps(v, ensure_ascii=False)
    parts = [f'"{k}": {pyval(r[k])}' for k in ("subject", "subject_label", "relation", "object", "object_label", "source")]
    return "{" + ", ".join(parts) + "}"


def fmt_dict_block(d, label):
    lines = [f"    # --- Iteration 3 Stage 9 batch 2 ({label}) ---"]
    for sid, rels in d.items():
        if not rels:
            lines.append(f"    {sid}: [],")
        else:
            lines.append(f"    {sid}: [")
            for r in rels:
                lines.append(f"        {fmt_relation(r)},")
            lines.append("    ],")
    return "\n".join(lines) + "\n"


override_block = fmt_dict_block(OVERRIDES, "flag.txt S1482-S2166")
addition_block = fmt_dict_block(ADDITIONS, "flag.txt S1482-S2166")

# Insert right after each batch-1 marker comment (before batch 1's own entries),
# using the unique surrounding-context anchors so each replace(..., 1) hits the
# correct dict even though the marker line text itself is identical in both.
new_text = text.replace(OVR_CONTEXT, OVR_CONTEXT + override_block, 1)
new_text = new_text.replace(ADD_CONTEXT, ADD_CONTEXT + addition_block, 1)

assert new_text != text

if isinstance(src, list):
    nb["cells"][51]["source"] = [new_text]
else:
    nb["cells"][51]["source"] = new_text

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Patched batch 2. OVERRIDES: {len(OVERRIDES)}, ADDITIONS: {len(ADDITIONS)}")

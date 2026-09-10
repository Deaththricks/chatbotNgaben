# -*- coding: utf-8 -*-
"""Stage 9 batch 1: flag.txt S46-S1477 (user's original free-text section).
FIX/DROP -> MANUAL_RELATION_OVERRIDES (replace). ADD -> MANUAL_RELATION_ADDITIONS (append)."""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"


def mk(subject, relation, obj, subject_label=None, object_label=None):
    return {
        "subject": subject, "subject_label": subject_label,
        "relation": relation, "object": obj, "object_label": object_label,
        "source": "manual_override",
    }


OVERRIDES = {
    46: [
        mk("swasta", "ADALAH", "upacara yang dilakukan jika jenazah tidak ditemukan atau meninggal di perantauan", "RITUAL_KEMATIAN"),
        mk("swasta", "MENGGUNAKAN", "kayu cendana dan aksara sakral sebagai simbol pengganti jasad", "RITUAL_KEMATIAN"),
    ],
    58: [
        mk("nganyut", "BERUPA", "pelarungan abu ke sungai atau laut", "TAHAPAN_UPACARA"),
        mk("abu", "DIHANYUTKAN_KE", "sungai", "SARANA_RITUAL"),
        mk("abu", "DIHANYUTKAN_KE", "laut", "SARANA_RITUAL"),
        mk("nganyut", "MELAMBANGKAN", "pelepasan terakhir menuju moksha", "TAHAPAN_UPACARA"),
    ],
    191: [],
    213: [],
    219: [
        mk("sekar ura", "MELAMBANGKAN", "perpisahan antara yang meninggal dengan keluarga yang ditinggal", "SARANA_RITUAL"),
        mk("sekar ura", "MELAMBANGKAN", "harapan selalu diberikan kesejahteraan dan kemakmuran", "SARANA_RITUAL"),
        mk("sekar ura", "TERDIRI_DARI", "beras kuning", "SARANA_RITUAL"),
        mk("sekar ura", "TERDIRI_DARI", "wang kepeng/bolong", "SARANA_RITUAL"),
        mk("sekar ura", "TERDIRI_DARI", "daun temen", "SARANA_RITUAL"),
        mk("sekar ura", "TERDIRI_DARI", "kembang rampai", "SARANA_RITUAL"),
    ],
    224: [],
    258: [
        mk("tegteg", "DIBAWA_KE", "pura dalem", "SARANA_RITUAL"),
        mk("tegteg", "DIGUNAKAN_UNTUK", "matur piuning serta memohon atma yang akan diaben", "SARANA_RITUAL"),
    ],
    270: [
        mk("ngaben svasta", "ADALAH", "pelaksanaan atiwa-tiwa terhadap orang yang telah meninggal yang jenazahnya tidak mungkin ditemukan kembali", "RITUAL_KEMATIAN"),
        mk("ngaben svasta", "DITUJUKAN_UNTUK", "jenazah yang telah lama terkubur/terpendam", "RITUAL_KEMATIAN"),
        mk("ngaben svasta", "DITUJUKAN_UNTUK", "jenazah yang terlalu jauh dari jangkauan kita", "RITUAL_KEMATIAN"),
    ],
    271: [
        mk("sawa", "DIGANTI_DENGAN", "simbol tirtha", "ISTILAH_UMUM_RITUAL"),
        mk("simbol tirtha", "ADALAH", "toyo Ã§arira"),
        mk("atiwa-tiwa", "ADALAH", "raÃ§adana", "RITUAL_KEMATIAN"),
        mk("atiwa-tiwa", "ADALAH", "tirta yadnya pranawa", "RITUAL_KEMATIAN"),
        mk("raÃ§adana", "SAMA_DENGAN", "atiwa-tiwa asti vedana"),
        mk("tirta yadnya pranawa", "SAMA_DENGAN", "atiwa-tiwa asti vedana"),
        mk("atiwa-tiwa", "BAGIAN_DARI", "ngaben svasta", "RITUAL_KEMATIAN"),
    ],
    399: [
        mk("sasih yang baik untuk pitra yadnya (khususnya ngaben)", "ADALAH", "kasa", "KONSEP_HUKUM_ADAT"),
        mk("sasih yang baik untuk pitra yadnya (khususnya ngaben)", "ADALAH", "karo", "KONSEP_HUKUM_ADAT"),
        mk("sasih yang baik untuk pitra yadnya (khususnya ngaben)", "ADALAH", "katiga", "KONSEP_HUKUM_ADAT"),
    ],
    400: [
        mk("sasih kaenem", "DIKENAL_SEBAGAI", "dewasa madya", "KONSEP_HUKUM_ADAT"),
        mk("sasih kapitu", "DIKENAL_SEBAGAI", "dewasa madya", "KONSEP_HUKUM_ADAT"),
    ],
    # bulk drop list (flag.txt line 42)
    540: [], 541: [], 559: [], 560: [], 591: [], 616: [], 618: [], 631: [], 641: [], 679: [],
    738: [mk("puspa asti", "ADALAH", "abu yang diambil dengan mempergunakan sumpit/sepit", "SARANA_RITUAL")],
    801: [mk("pitra yadnya", "TERDIRI_DARI", "beberapa jenis yang pelaksanaannya ber-bhinneka", "RITUAL")],
    797: [
        mk("pitra yadnya", "ADALAH", "upacara keagamaan yang diadakan untuk menyelenggarakan atau nyangaskara jenazah atau roh keluarga yang meninggal", "RITUAL"),
        mk("pitra yadnya", "MENGGUNAKAN", "pelbagai sajen dan alat-alat upakara", "RITUAL"),
    ],
    809: [
        mk("pitra yadnya dataran rendah", "ADALAH", "hasil penyempurnaan terakhir yang ening sira empu kuturan", "RITUAL"),
        mk("pitra yadnya dataran rendah", "ADALAH", "hasil penyempurnaan terakhir dang hyang dwijendra", "RITUAL"),
        mk("pitra yadnya dataran rendah", "ADALAH", "hasil penyempurnaan terakhir empu lutuk", "RITUAL"),
        mk("pitra yadnya dataran rendah", "ADALAH", "hasil penyempurnaan terakhir dan lain-lain", "RITUAL"),
    ],
    906: [],
    925: [mk("jenazah", "DIMASUKKAN_KE_DALAM", "peti kayu", "ISTILAH_UMUM_RITUAL")],
    961: [
        mk("sawa", "DIBUNGKUS_DENGAN", "kain putih", "ISTILAH_UMUM_RITUAL"),
        mk("sawa", "DIIKAT_DENGAN", "benang leleson", "ISTILAH_UMUM_RITUAL"),
        mk("sawa", "DIIKAT", "sebelas kali", "ISTILAH_UMUM_RITUAL"),
    ],
    967: [],
    971: [
        mk("tirtha", "TERBUAT_DARI", "klungah", "TIRTHA_SUCI"),
        mk("pitra yadnya", "ADALAH", "nglungah", "RITUAL"),
    ],
    1016: [
        mk("ngaben", "BERTUJUAN_UNTUK", "memusnahkan segenap jasad sawa sehalus-halusnya", "RITUAL_KEMATIAN"),
        mk("niskala", "ADALAH", "batiniah", "KONSEP_FILOSOFIS"),
    ],
    1122: [mk("nyekeh", "BERARTI", "jenazah dibaringkan di rumah adat dalam jangka waktu agak lama hingga tiba hari H untuk ngaben sesuai dewasa yang dipilih", "RITUAL_KEMATIAN")],
    1128: [
        mk("nyekeh sawa", "DILAKUKAN_OLEH", "keluarga raja", "RITUAL_KEMATIAN"),
        mk("nyekeh sawa", "DILAKUKAN_OLEH", "keluarga pendeta", "RITUAL_KEMATIAN"),
    ],
    1136: [
        mk("damar kurung", "ADALAH", "sarana permohonan kepada sanghyang agni", "SARANA_RITUAL"),
        mk("damar kurung", "BERTUJUAN_AGAR", "keletehan yang dipancarkan sawa mendiang diblokir terbatas, hanya sebatas tanah pekarangan keluarga mendiang", "SARANA_RITUAL"),
    ],
    1138: [
        mk("mendiang", "MEMPEROLEH", "ayaban upakara diuskamaligi yang bermakna penyucian", "ISTILAH_UMUM_RITUAL"),
        mk("ayaban upakara diuskamaligi", "BERTUJUAN_AGAR", "leteh sawa tidak memancar ke luar dan tidak menghimbasi yang lain", "TAHAPAN_UPACARA"),
    ],
    1150: [],
    1163: [
        mk("ngaben", "ADALAH", "suatu yadnya selaku pelaksanaan ajaran agama", "RITUAL_KEMATIAN"),
        mk("ngaben", "DIDUKUNG_DENGAN", "sredaning manah atau rasa hati tulus dan ikhlas", "RITUAL_KEMATIAN"),
    ],
    1169: [mk("sawa", "DITANAM_ATAU_DIBAKAR_SEMENTARA", "status dititip, menunggu biaya untuk menggelar ngaben beberapa bulan atau tahun kemudian", "ISTILAH_UMUM_RITUAL")],
    1189: [
        mk("tirtha", "ADALAH", "sarana restu dari ida bhatara di kahyangan tersebut", "TIRTHA_SUCI"),
        mk("tirtha", "DITUJUKAN_UNTUK", "arwah mendiang dalam peristiwa beralihnya dari dunia manusia ke dunia roh", "TIRTHA_SUCI"),
    ],
    1205: [mk("tirtha pangentas", "BERFUNGSI_UNTUK", "memotong ikatan dan hubungan jasad dengan atma-jiwa dari mendiang", "TIRTHA_SUCI")],
    1206: [mk("tirtha", "BERPERAN_SEBAGAI", "sarana untuk menetapkan kedudukan arwah mendiang pada satu alam roh (pitra) tertentu", "TIRTHA_SUCI")],
    1238: [],
    1253: [
        mk("ngaben", "ADALAH", "malebuang", "RITUAL_KEMATIAN"),
        mk("ngaben", "ADALAH", "atiwa-tiwa", "RITUAL_KEMATIAN"),
    ],
    1261: [mk("ngaben", "ADALAH", "salah satu yadnya yang paling banyak ragamnya, dari segi variasi besar kecilnya biaya dan wibawa lahiriahnya", "RITUAL_KEMATIAN")],
    1328: [mk("besar kecil punia atau honorarium", "DISINKRONKAN_DENGAN", "jenis upacara", "KONSEP_HUKUM_ADAT")],
    1430: [mk("beras catur", "ADALAH", "lambang kekuatan panca dewata selaku manifestasi hyang widhi yang mengelola alam semesta (bhuwana agung)", "SARANA_RITUAL")],
    1452: [mk("nywasta", "DILAKUKAN_OLEH", "orang", "RITUAL_KEMATIAN")],
    1456: [mk("nywasta", "ADALAH", "ngaben yang sangat sederhana dalam hal sajen dan alat-alat upakaranya", "RITUAL_KEMATIAN")],
    1461: [mk("adegan", "ADALAH", "alat upakara yang terbuat dari daun rontal, beralaskan bakul kecil atau pangkon", "SARANA_RITUAL")],
    1463: [],
    1474: [
        mk("sesajen", "MELIPUTI", "diuskamaligi", "SARANA_RITUAL"),
        mk("sesajen", "MELIPUTI", "nasi angkeb", "SARANA_RITUAL"),
        mk("sesajen", "MELIPUTI", "saji", "SARANA_RITUAL"),
        mk("sesajen", "DIPERSEMBAHKAN_KEPADA", "mendiang", "SARANA_RITUAL"),
    ],
    1477: [
        mk("tirtha pangentas", "ADALAH", "siratan terakhir", "TIRTHA_SUCI"),
        mk("tirtha pangentas (dan isinya)", "DIPERSATUKAN_DENGAN", "isi pengawak", "TIRTHA_SUCI"),
    ],
}

ADDITIONS = {
    215: [mk("layon", "DILETAKKAN_DI", "bale gede", "SARANA_RITUAL"), mk("layon", "DILETAKKAN_DI", "saka roras", "SARANA_RITUAL")],
    246: [mk("ngerorasin", "DIADAKAN_DI", "pura dalem", "TAHAPAN_UPACARA")],
    338: [
        mk("soda", "BERUPA", "nasi", "SARANA_RITUAL"), mk("soda", "BERUPA", "minum", "SARANA_RITUAL"),
        mk("soda", "BERUPA", "buah-buahan", "SARANA_RITUAL"), mk("soda", "BERUPA", "jajan", "SARANA_RITUAL"),
    ],
    358: [mk("leluwur", "BERUPA", "kain putih", "SARANA_RITUAL")],
    364: [
        mk("nanginin", "ADALAH", "membangunkan almarhum seperti membangunkan orang yang sedang tidur", "TAHAPAN_UPACARA"),
        mk("nanginin", "DISERTAI", "kekidungan yang berhubungan dengan kidung pitra yadnya", "TAHAPAN_UPACARA"),
    ],
    738: [mk("puspa asti", "DIHANCURKAN_DI", "sesenden", "SARANA_RITUAL")],
    788: [mk("dua kata", "ADALAH", "yadnya")],
    1160: [mk("patus", "ADALAH", "bantuan gratis", "KONSEP_HUKUM_ADAT")],
    1188: [mk("upacara ini", "MEMPERGUNAKAN", "tirtha panglukatan"), mk("upacara ini", "MEMPERGUNAKAN", "pabersihan")],
    1213: [mk("ayaban", "DILAKUKAN_DI", "rumah")],
    1465: [
        mk("jun pere", "BERISI", "air", "SARANA_RITUAL"),
        mk("jun pere", "BERISI", "54 atau 108 lembar daun alang-alang", "SARANA_RITUAL"),
        mk("jun pere", "BERISI", "sembilan batang kayu cendana", "SARANA_RITUAL"),
    ],
}

# ---- 344: single-sentence override, large enough to warrant its own block ----
OVERRIDES[344] = [
    mk("eteh-eteh sawa", "BERUPA", x, "SARANA_RITUAL") for x in [
        "kain putih untuk saput", "kamben", "tapih", "sabuk", "udeng", "pangulungan",
        "angkeb rai", "angkeb baga/purus", "leluwur", "tatindih",
        "kain putih untuk bantal berisi pis bolong 11 kepeng",
        "kain kuning untuk saput atau selendang",
        "rantasan kain putih kuning dan kain anyar",
        "samsam", "bunga", "kwangen",
    ]
] + [mk("eteh-eteh sawa", "DIMOHONKAN_DARI", "sulinggih/griya", "SARANA_RITUAL")]

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = nb["cells"][51]["source"]
text = "".join(src) if isinstance(src, list) else src

# Insert into MANUAL_RELATION_OVERRIDES dict body (before its closing brace, which is
# followed by the "relations = [" filter block) and into MANUAL_RELATION_ADDITIONS.
OVR_CLOSE = "}\n\nrelations = [\n    relation for relation in relations\n    if relation[\"sentence_id\"] not in MANUAL_RELATION_OVERRIDES\n]"
assert text.count(OVR_CLOSE) == 1, f"override-close anchor found {text.count(OVR_CLOSE)} times"

ADD_OPEN = "MANUAL_RELATION_ADDITIONS = {\n    # sentence_id: [ {subject, subject_label, relation, object, object_label,\n    #                 source: \"manual_override\"}, ... ]\n}"
assert text.count(ADD_OPEN) == 1, f"additions-open anchor found {text.count(ADD_OPEN)} times"


def fmt_relation(r):
    parts = []
    for k in ("subject", "subject_label", "relation", "object", "object_label", "source"):
        v = r[k]
        parts.append(f'"{k}": {json.dumps(v, ensure_ascii=False)}')
    return "{" + ", ".join(parts) + "}"


def fmt_dict_block(d):
    lines = []
    for sid, rels in d.items():
        if not rels:
            lines.append(f"    {sid}: [],")
        else:
            lines.append(f"    {sid}: [")
            for r in rels:
                lines.append(f"        {fmt_relation(r)},")
            lines.append("    ],")
    return "\n".join(lines)


override_block = fmt_dict_block(OVERRIDES)
addition_block = fmt_dict_block(ADDITIONS)

new_ovr_close = (
    "    # --- Iteration 3 Stage 9 batch 1 (flag.txt S46-S1477) ---\n"
    + override_block + "\n" + OVR_CLOSE
)
new_text = text.replace(OVR_CLOSE, new_ovr_close, 1)

new_add_open = (
    "MANUAL_RELATION_ADDITIONS = {\n"
    "    # sentence_id: [ {subject, subject_label, relation, object, object_label,\n"
    "    #                 source: \"manual_override\"}, ... ]\n"
    "    # --- Iteration 3 Stage 9 batch 1 (flag.txt S46-S1477) ---\n"
    + addition_block + "\n}"
)
new_text = new_text.replace(ADD_OPEN, new_add_open, 1)

assert new_text != text

if isinstance(src, list):
    nb["cells"][51]["source"] = [new_text]
else:
    nb["cells"][51]["source"] = new_text

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Patched. OVERRIDES sentences: {len(OVERRIDES)}, ADDITIONS sentences: {len(ADDITIONS)}")

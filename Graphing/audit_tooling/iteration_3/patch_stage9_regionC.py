# -*- coding: utf-8 -*-
"""Iteration 3, Stage 9+10 region C (S3333-S4340). Patches MANUAL_RELATION_OVERRIDES
and MANUAL_RELATION_ADDITIONS in cell 51. Formats dicts as Python literals (None, not
JSON null) to avoid the null-serialization bug hit in prior batches."""
import json, re, sys

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"

def fmt_rel(subj, subj_label, rel, obj, obj_label=None):
    def pyval(v):
        return "None" if v is None else json.dumps(v, ensure_ascii=False)
    return ('        {"subject": %s, "subject_label": %s, "relation": %s, '
            '"object": %s, "object_label": %s, "source": "manual_override"},' %
            (json.dumps(subj, ensure_ascii=False), pyval(subj_label),
             json.dumps(rel, ensure_ascii=False), json.dumps(obj, ensure_ascii=False),
             pyval(obj_label)))

def fmt_block(sid, rels):
    lines = ["    %d: [" % sid]
    for r in rels:
        lines.append(fmt_rel(*r))
    lines.append("    ],")
    return "\n".join(lines)

# ---- OVERRIDES (FIX/DROP; replace-style) ----
OVERRIDES = {
    3333: [("bale", "BANGUNAN_RITUAL", "TERBUAT_DARI", "bambu"),
           ("galar", "SARANA_RITUAL", "TERDIRI_DARI", "bilah-bilah bambu (sebanyak 9 buah)"),
           ("bale", "BANGUNAN_RITUAL", "TERBUAT_DARI", "galar")],
    3340: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIUSUNG_KE", "tempat penusangan"),
           ("tempat penusangan", None, "DIGUNAKAN_UNTUK", "nyiramang layon")],
    3354: [("jenazah", "ISTILAH_UMUM_RITUAL", "NAIK_KE", "pepaga/asagan")],
    3364: [("jenazah", "ISTILAH_UMUM_RITUAL", "HARUS_DIBIARKAN", "sebentar (sebelum dibuka pakaiannya)"),
           ("orang yang dituakan/lebih tua", None, "MENCUCI", "muka dan rambut jenazah")],
    3446: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIBERI", "pakaian seperti layaknya orang masih hidup")],
    3496: [("lekesan", "SARANA_RITUAL", "DITEMPELKAN_DI", "gigi jenazah (ISTILAH_UMUM_RITUAL)"),
           ("jenazah (bibir)", None, "DIBERSIHKAN_DENGAN", "tembakau (diusapkan pada bibir)")],
    3547: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIPERCIKI_DAN_DIMINUMKAN", "tirta"),
           ("tirta", None, "BERASAL_DARI", "bhetara hyang guru"),
           ("tirta", None, "DIMOHONKAN_DI", "sanggah/pamerajan keluarga orang yang meninggal")],
    3559: [("waja", None, "BAGIAN_DARI", "panca datu")],
    3584: [("pengerikan kuku mutlak", None, "DILAKUKAN_SAAT", 'upacara "melelet" (pabersihan mati)')],
    3586: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIANGGAP_SEBAGAI", "orang yang masih hidup")],
    3649: [("bantal kapuk", None, "DIGANTI_DENGAN", "bantal sesisir buah pisang kayu")],
    3651: [("dewa wishnu", "ENTITAS_KEAGAMAAN", "MENDAPATKAN", "tirtha amertha")],
    3653: [("gegaleng kepala", None, "BERARTI", "bantal untuk tidur")],
    3656: [("gegaleng", None, "ADALAH", "pengganti bantal kapuk yang telah dipakai pada waktu pabersihan hidup")],
    3694: [("atma", "KONSEP_FILOSOFIS", "LEPAS_BEBAS_DARI", "badan")],
    3728: [("penggunaan wewangian", None, "BERTUJUAN_AGAR", "orang yang numitis memperoleh pujian keharuman dalam tingkah lakunya")],
    3742: [("kesuna (bawang putih)", None, "BERMAKNA", "agar orang yang numitis kembali memiliki kuku-kuku yang indah dan putih bersih")],
    3783: [("tirtha", "TIRTHA_SUCI", "DIPERCIKKAN_PADA", "seluruh badan hingga ke kaki jenazah"),
           ("priuk (tempat tirtha pangringkes)", None, "DIPECAHKAN", "setelah tirtha dipercikkan"),
           ("priuk (yang pecah)", None, "DIBUANG_DI", "kolong bawah pepaga/asagan")],
    3799: [("kain (penutup jenazah)", None, "DIISI_DENGAN", "rurub sinom sebanyak lima buah")],
    3811: [("rurub sinom", None, "DIAMBIL_DARI", "gulungan jenazah (sebelum dimasukkan ke peti)")],
    3836: [("bale-bale/dipan", None, "DIPAKAI_UNTUK", "warung atau dapur")],
    3843: [("galar (dengan ketekan guling)", None, "DIGUNAKAN_DENGAN_HARAPAN", "membuat ngantuk dan tidur nyenyak")],
    3845: [("bale-bale", None, "DILETAKKAN_DI", "pura atau merajan")],
    3852: [("jumlah galar", None, "CONTOH", "5, 10, 15, 20, 25, 30, dan seterusnya (kelipatan 5)")],
    3909: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIBAWA_KE", "setra untuk segera dikuburkan (bukan diaben)")],
    3914: [("jenazah", "ISTILAH_UMUM_RITUAL", "MENJALANI", "rangkaian upacara lain sebelum dibawa ke setra (jika diaben)")],
    3936: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIBERI", "pakaian seperti layaknya orang masih hidup")],
    3964: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIPERCIKI_DAN_DIMINUMKAN", "tirta"),
           ("tirta", None, "BERASAL_DARI", "bhetara hyang guru"),
           ("tirta", None, "DIMOHONKAN_DI", "sanggah/pamerajan keluarga orang yang meninggal")],
    4035: [("tirtha", "TIRTHA_SUCI", "DIPERCIKKAN_PADA", "seluruh badan hingga ke kaki jenazah"),
           ("priuk (tempat tirtha pangringkes)", None, "DIPECAHKAN", "setelah tirtha dipercikkan"),
           ("priuk (yang pecah)", None, "DIBUANG_DI", "kolong bawah pepaga/asagan")],
    4062: [("tirtha", "TIRTHA_SUCI", "DIPAKAI_UNTUK", "ngalukat"),
           ("ngalukat", None, "ADALAH", "pembersihan tingkat awal"),
           ("tirtha", "TIRTHA_SUCI", "DIPAKAI_UNTUK", "banten"),
           ("tirtha", "TIRTHA_SUCI", "DIPAKAI_UNTUK", "adegan (SARANA_RITUAL)")],
    4065: [("tirtha pabersihan", "TIRTHA_SUCI", "DIBUAT_OLEH", "ida sang sulinggih"),
           ("tirtha pabersihan", "TIRTHA_SUCI", "TIDAK_MEMAKAI", "samsam (tidak seperti tirtha panglukatan)"),
           ("tirtha pabersihan (periuknya)", None, "TANPA", "kalung benang dengan uang kepeng")],
    4087: [("tirtha penembak", "TIRTHA_SUCI", "MEMILIKI", "hubungan erat dengan itihasa (Bisma Parwa, bagian dari Mahabharata)")],
    4090: [("arjuna", "ENTITAS_KEAGAMAAN", "MEMANAH", "tanah (di samping rsi bisma)")],
    4096: [("tirtha", "TIRTHA_SUCI", "DIBAWA_KE", "setra untuk dipergunakan pada waktu pembakaran")],
    4105: [("sarana dan prasarana (upacara pemujaan)", None, "BERUPA", "pras, ajuman, daksina, suci, rayunan, dan kadang-kadang pajegan"),
           ("tirtha", "TIRTHA_SUCI", "DIMOHONKAN_OLEH", "pemangku kawitan setempat")],
    4110: [("sarana dan prasarana (upacara pemujaan)", None, "BERUPA", "pras, ajuman, daksina, suci, rayunan, dan kadang-kadang pajegan"),
           ("tirtha", "TIRTHA_SUCI", "DIMOHONKAN_OLEH", "pemangku kahyangan tiga setempat")],
    4112: [("tirtha", "TIRTHA_SUCI", "BERFUNGSI_SEBAGAI", "sarana pengembalian roh (atma) kepada sang pencipta"),
           ("pura kahyangan tiga", "BANGUNAN_RITUAL", "ADALAH", "tempat pemujaan sang pencipta"),
           ("pura kahyangan tiga", "BANGUNAN_RITUAL", "BERFUNGSI_SEBAGAI", "utpeti"),
           ("pura kahyangan tiga", "BANGUNAN_RITUAL", "BERFUNGSI_SEBAGAI", "sthiti"),
           ("pura kahyangan tiga", "BANGUNAN_RITUAL", "BERFUNGSI_SEBAGAI", "pralina")],
    4121: [("tirtha pangentas", "TIRTHA_SUCI", "DIBUAT_DI", "gria ida sang sulinggih (kediaman pendeta) atau di rumah"),
           ("tirtha pangentas", "TIRTHA_SUCI", "DIBUAT_SAAT", "upacara pengaskaran (bertepatan dengan puncak upacara pengabenan)")],
    4128: [("tirtha pangentas", "TIRTHA_SUCI", "MEMILIKI", 'fungsi utama sebagai sarana untuk "ngentas": memberikan jalan dan membersihkan noda-noda roh atau atma orang yang meninggal, agar dapat menuju ke alam kedewataan')],
    4169: [("tirtha pangentas", "TIRTHA_SUCI", "ADALAH", "sesuatu yang memiliki arti erat dengan upacara pitra yadnya")],
    4170: [("tirtha pangentas", "TIRTHA_SUCI", "ADALAH", "tirtha yang diharapkan dan diyakini sebagai alat atau sarana sangat penting bagi umat hindu, khususnya dalam hubungannya untuk dapat melepaskan roh para leluhur dari ikatan-ikatan keduniawian, sehingga para leluhur dapat bebas dan bisa meningkat menuju alam bhwah loka")],
    4177: [("atma lingga", "KONSEP_FILOSOFIS", "MEWUJUDKAN", "sanghyang ongkara dan tri aksara dalam diri (yang berstana dalam bathin)")],
    4192: [("tirtha pangentas", "TIRTHA_SUCI", "ADALAH", "tirtha gangga yang diturunkan atau dibuat oleh pendeta/sang sulinggih")],
    4212: [("badan", None, "BERSINAR_BAGAIKAN", "matahari")],
    4273: [("padang lepas", "SARANA_RITUAL", "DIMASUKKAN_KE_DALAM", "periuk"),
           ("kalpika", "SARANA_RITUAL", "DIMASUKKAN_KE_DALAM", "periuk")],
    4339: [("tirtha pangentas", "TIRTHA_SUCI", "ADALAH", "lambang penunjuk jalan bagi roh atau atman untuk kembali ke asalnya (brahman/alam swah loka) sebagai tujuan terakhir")],
}

# ---- ADDITIONS (pure ADD; additive, existing relations left alone) ----
ADDITIONS = {
    3339: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIAMBIL_DARI", "balai (tempat jenazah disemayamkan)"),
           ("tempat persemayaman jenazah", None, "DITEMPATKAN_DI", "bale semanggen (rumah adat Bali)")],
    3340: [("tempat penusangan", None, "BERUPA", "pepaga atau asagan")],
    3354: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIDUDUKKAN_DULU_SEBELUM", "tidur tertelentang di pepaga/asagan")],
    3363: [("kepala jenazah", None, "DIALASI_DENGAN", "bantal biasa (bantal kapuk)")],
    3468: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIHIAS_SEOLAH_OLAH", "pergi menghadiri undangan atau ke pura")],
    3584: [("pengerikan kuku", None, "TIDAK_BOLEH_DILAKUKAN_SAAT", "pabersihan hidup")],
    3610: [("jenazah", "ISTILAH_UMUM_RITUAL", "DIBILAS_DENGAN", "air"),
           ("jenazah", "ISTILAH_UMUM_RITUAL", "DIKERINGKAN_DENGAN", "kain kering")],
    3651: [("dewa wishnu", "ENTITAS_KEAGAMAAN", "TIDUR_DI", "atas samudra (dialasi dan dipayungi naga/ular cobra berkepala banyak)")],
    3656: [("gegaleng", None, "DIKENAL_SEBAGAI", "galeng pengerekan")],
    3720: [("anget-angetan", None, "BERMAKNA", "agar orang yang meninggal dapat numitis lagi dan terhindar dari penyakit, serta memiliki budi pekerti dan pikiran yang baik")],
    3728: [("numitis", "KONSEP_FILOSOFIS", "MENYEBABKAN", "badan menjadi harum")],
    3734: [("kojong (kawangen jeriji)", None, "BERISI", "lima buah gulungan base (daun sirih)"),
           ("gulungan daun sirih", None, "DIIKAT_DENGAN", "benang putih"),
           ("gulungan sirih", None, "DIMASUKKAN_KE", "lubang uang kepeng")],
    3791: [("jenazah (setelah dibungkus tiga lapis)", None, "DIIKAT_DENGAN", "tali benang tukelan")],
    3816: [("bilahan-bilahan bambu (ante)", None, "DIKENAL_SEBAGAI", "galar")],
    3904: [("masyarakat setempat", None, "MELAKUKAN", "upacara mesaji (atau memunjung), ketika jenazah masih di atas pepaga/asagan")],
    4090: [("air (dari tanah yang dipanah arjuna)", None, "MENGENAI", "bibir rsi bisma")],
    4128: [("upacara pengabenan", "RITUAL_KEMATIAN", "ADALAH", "upacara penyucian roh atau atman (purusa) orang yang telah meninggal, agar terlepas dari ikatan panca mahabhuta, sehingga dapat menuju alam dewa (swah loka)")],
    4175: [("upacara mapulang lingga", None, "BERARTI", '"ngelinggihang lingga" (dalam diri)')],
    4212: [("abu abu kekototan (kekotoran)", "SARANA_RITUAL", "MUSNAH", "melalui ritual amrethi karana"),
           ("amrethi karana", None, "DILAKUKAN_DENGAN", "mengucurkan tirtha amertha dalam diri")],
    4266: [("pramakusa", "SARANA_RITUAL", "DIMANTRAI", "sebelum dimasukkan ke dalam priuk")],
    4273: [("jijih (biji padi)", None, "DIMASUKKAN_KE_DALAM", "periuk"),
           ("pripih emas", None, "DIMASUKKAN_KE_DALAM", "periuk"),
           ("recadana", None, "DIMASUKKAN_KE_DALAM", "periuk"),
           ("ulantaga", None, "DIMASUKKAN_KE_DALAM", "periuk"),
           ("sarana-sarana tersebut", None, "DIMANTRAI_OLEH", "ida sang sulinggih (sebelum dimasukkan)")],
    4336: [("pengabenan (tanpa tirtha pangentas)", None, "DIANGGAP", "belum dilaksanakan")],
}

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = nb["cells"][51]["source"]
if isinstance(src, list):
    text = "".join(src)
else:
    text = src

overrides_anchor = '''    3330: [
        {"subject": "krama (masyarakat banjar)", "subject_label": None, "relation": "MEMBUAT", "object": "bale-bale tempat memandikan mayat", "object_label": None, "source": "manual_override"},
    ],
}'''
additions_anchor = '''    3332: [
        {"subject": "pepaga", "subject_label": None, "relation": "DIKENAL_SEBAGAI", "object": "bale penusangan (istilah Denpasar)", "object_label": None, "source": "manual_override"},
        {"subject": "pepaga/asagan", "subject_label": None, "relation": "ADALAH", "object": "semacam dipan atau bale darurat", "object_label": None, "source": "manual_override"},
        {"subject": "pepaga/asagan", "subject_label": None, "relation": "DIPERGUNAKAN_SEBAGAI", "object": "usungan", "object_label": None, "source": "manual_override"},
        {"subject": "pepaga/asagan", "subject_label": None, "relation": "DIPERGUNAKAN_SEBAGAI", "object": "tandu", "object_label": None, "source": "manual_override"},
    ],
}'''

assert text.count(overrides_anchor) == 1, "overrides anchor not found exactly once: %d" % text.count(overrides_anchor)
assert text.count(additions_anchor) == 1, "additions anchor not found exactly once: %d" % text.count(additions_anchor)

overrides_new_blocks = "\n".join(fmt_block(sid, rels) for sid, rels in OVERRIDES.items())
overrides_replacement = overrides_anchor[:-1] + "\n    # --- Iteration 3 Stage 9+10 region C (flag.txt S3333-S4340) ---\n" + overrides_new_blocks + "\n}"

additions_new_blocks = "\n".join(fmt_block(sid, rels) for sid, rels in ADDITIONS.items())
additions_replacement = additions_anchor[:-1] + "\n    # --- Iteration 3 Stage 9+10 region C (flag.txt S3333-S4340) ---\n" + additions_new_blocks + "\n}"

text = text.replace(overrides_anchor, overrides_replacement, 1)
text = text.replace(additions_anchor, additions_replacement, 1)

nb["cells"][51]["source"] = text.splitlines(keepends=True)

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("OK: %d override sentences, %d addition sentences added." % (len(OVERRIDES), len(ADDITIONS)))

import json, io

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"

with io.open(NB_PATH, encoding="utf-8") as f:
    nb = json.load(f)

src = nb["cells"][51]["source"]
text = "".join(src) if isinstance(src, list) else src

OVERRIDES_ANCHOR = '''        {"subject": "eteh-eteh sawa", "subject_label": "SARANA_RITUAL", "relation": "DIMOHONKAN_DARI", "object": "sulinggih/griya", "object_label": None, "source": "manual_override"},
    ],
}

relations = ['''

NEW_OVERRIDES = '''    # --- Iteration 3 Stage 9, region B (flag.txt S2166-S3332, tail of Part1 + all Part2) ---
    2256: [
        {"subject": "pamerasan", "subject_label": None, "relation": "ADALAH", "object": "sejumlah uang kepeng", "object_label": None, "source": "manual_override"},
        {"subject": "uang kepeng", "subject_label": None, "relation": "DIBUNGKUS_DENGAN", "object": "daun dapdap", "object_label": None, "source": "manual_override"},
        {"subject": "uang kepeng", "subject_label": None, "relation": "DIIKAT_DENGAN", "object": "benang tridatu", "object_label": None, "source": "manual_override"},
    ],
    2258: [
        {"subject": "pamerasan", "subject_label": None, "relation": "ADALAH", "object": "sarana pemberitahuan akan adanya pangabenan untuk mendiang", "object_label": None, "source": "manual_override"},
        {"subject": "pamerasan", "subject_label": None, "relation": "ADALAH", "object": "tanda bahwa keluarga mendiang tidak lupa akan ikatan keluarga", "object_label": None, "source": "manual_override"},
    ],
    2262: [
        {"subject": "tirtha", "subject_label": None, "relation": "DIMOHON_KEPADA", "object": "pendeta yang muput pangabenan itu sendiri", "object_label": None, "source": "manual_override"},
        {"subject": "sang cucu", "subject_label": None, "relation": "MEMOHON", "object": "tirtha", "object_label": None, "source": "manual_override"},
    ],
    2323: [
        {"subject": "bade dan lembu", "subject_label": None, "relation": "TERGOLONG_BERSAMA", "object": "alat penting lainnya", "object_label": None, "source": "manual_override"},
    ],
    2340: [
        {"subject": "adegan", "subject_label": None, "relation": "DIJADIKAN", "object": "unsur arak-arakan indah (oleh pemudi-pemudi keluarga bersangkutan)", "object_label": None, "source": "manual_override"},
    ],
    2363: [
        {"subject": "bale pamuunan", "subject_label": None, "relation": "DIKELILINGI_OLEH", "object": "bade dengan jenazahnya (sebanyak tiga kali)", "object_label": None, "source": "manual_override"},
    ],
    2370: [
        {"subject": "pradaksina", "subject_label": None, "relation": "MELAMBANGKAN", "object": "turunnya purusa meresapi pradana (material memperoleh imbas kesucian dari yang immaterial)", "object_label": None, "source": "manual_override"},
    ],
    2387: [
        {"subject": "bade", "subject_label": None, "relation": "DILETAKKAN_DI", "object": "sebelah hilir lembu", "object_label": None, "source": "manual_override"},
    ],
    2406: [
        {"subject": "jenazah atau simbolik", "subject_label": None, "relation": "MENJADI", "object": "sasaran segala kegiatan", "object_label": None, "source": "manual_override"},
    ],
    2419: [
        {"subject": "adegan, angenan, pisang jati, panguryagan, dan lain-lain alat yang harus dibakar", "subject_label": None, "relation": "DIPERSEMBAHKAN_KEPADA", "object": "hyang agni (api), tanpa sisa", "object_label": None, "source": "manual_override"},
        {"subject": "hyang agni", "subject_label": None, "relation": "ADALAH", "object": "api", "object_label": None, "source": "manual_override"},
    ],
    2448: [
        {"subject": "suku tunggal", "subject_label": None, "relation": "MENGHATURKAN", "object": "sembah bakti pamitan kepada bhatara-bhatari", "object_label": None, "source": "manual_override"},
    ],
    2455: [
        {"subject": "pangabenan", "subject_label": None, "relation": "TERDIRI_DARI", "object": "berbagai jenis", "object_label": None, "source": "manual_override"},
    ],
    2472: [
        {"subject": "pranawa", "subject_label": None, "relation": "BERARTI", "object": "lambang suara \\"om\\"", "object_label": None, "source": "manual_override"},
    ],
    2483: [
        {"subject": "mendiang", "subject_label": None, "relation": "MEMPEROLEH", "object": "situasi demikian di alam lain", "object_label": None, "source": "manual_override"},
        {"subject": "supta pranawa", "subject_label": None, "relation": "ADALAH", "object": "satu pangabenan yang berlandaskan hasrat, semoga mendiang mendapatkan situasi demikian di alam lain", "object_label": None, "source": "manual_override"},
    ],
    2485: [
        {"subject": "pangabenan pranawa", "subject_label": None, "relation": "DITUJUKAN_UNTUK", "object": "mendiang yang telah tak ada sawanya lagi", "object_label": None, "source": "manual_override"},
    ],
    2502: [
        {"subject": "sawa wedana", "subject_label": None, "relation": "BERTUJUAN_MENYUCIKAN", "object": "roh", "object_label": None, "source": "manual_override"},
        {"subject": "sawa wedana", "subject_label": None, "relation": "BERTUJUAN_MENYUCIKAN", "object": "arwah", "object_label": None, "source": "manual_override"},
        {"subject": "sawa wedana", "subject_label": None, "relation": "BERTUJUAN_MENYUCIKAN", "object": "badan halus mendiang", "object_label": None, "source": "manual_override"},
        {"subject": "badan halus mendiang (roh/arwah)", "subject_label": None, "relation": "MENJADI", "object": "atma yang tanpa badan sama sekali", "object_label": None, "source": "manual_override"},
    ],
    2527: [
        {"subject": "pura, pamrajan, atau kahyangan jenis apapun", "subject_label": None, "relation": "ADALAH", "object": "dewaloka", "object_label": None, "source": "manual_override"},
        {"subject": "pura, pamrajan, atau kahyangan jenis apapun", "subject_label": None, "relation": "ADALAH", "object": "alam kedewaan", "object_label": None, "source": "manual_override"},
    ],
    2566: [
        {"subject": "bhuwana agung (masing-masing arah yang berjumlah 11)", "subject_label": None, "relation": "MEMPEROLEH", "object": "cuntaka selama sehari", "object_label": None, "source": "manual_override"},
    ],
    2571: [
        {"subject": "arjuna", "subject_label": None, "relation": "MENGHUKUM", "object": "diri", "object_label": None, "source": "manual_override"},
    ],
    2604: [
        {"subject": "ngangsen", "subject_label": None, "relation": "ADALAH", "object": "upacara penyucian sementara bagi sang pitra", "object_label": None, "source": "manual_override"},
        {"subject": "pitra (dalam ngangsen)", "subject_label": None, "relation": "BARU_LEPAS_PERTALIAN_DENGAN", "object": "stulasarira nya", "object_label": None, "source": "manual_override"},
        {"subject": "ngangsen", "subject_label": None, "relation": "BERTUJUAN", "object": "agar suksmasarira pitra tidak lagi dilekati bekas-bekas badan kasar", "object_label": None, "source": "manual_override"},
    ],
    2624: [
        {"subject": "pitra mendiang", "subject_label": None, "relation": "DIPERSILAKAN_MASUK_KE", "object": "sekah kangsen", "object_label": None, "source": "manual_override"},
        {"subject": "pitra mendiang", "subject_label": None, "relation": "MEMAKAI", "object": "wujud tersebut selaku pralingga (perlambang diri yang dihuni)", "object_label": None, "source": "manual_override"},
    ],
    2630: [
        {"subject": "pitra", "subject_label": None, "relation": "MENERIMA", "object": "sembah bhakti serta ayaban sajen", "object_label": None, "source": "manual_override"},
    ],
    2642: [
        {"subject": "sekah kangsen", "subject_label": None, "relation": "DIBONGKAR_SETELAH", "object": "pamralina", "object_label": None, "source": "manual_override"},
    ],
    2644: [
        {"subject": "abu daun (yang dinilai selaku bekas-bekas stulasarira mendiang)", "subject_label": None, "relation": "DIMASUKKAN_KE_DALAM", "object": "klungah nyuh gading (yang dibentuk menjadi suku tunggal)", "object_label": None, "source": "manual_override"},
    ],
    2651: [
        {"subject": "atma wedana", "subject_label": None, "relation": "DITUJUKAN_UNTUK", "object": "mendiang (baru dapat diadakan setelah mungkin lima atau sepuluh tahun kemudian)", "object_label": None, "source": "manual_override"},
    ],
    2667: [
        {"subject": "payadnyan", "subject_label": None, "relation": "ADALAH", "object": "bangunan pokok pada arena ini", "object_label": None, "source": "manual_override"},
    ],
    2672: [
        {"subject": "payadnyan", "subject_label": None, "relation": "ADALAH", "object": "bangunan yang paling rendah (dari segi ukuran)", "object_label": None, "source": "manual_override"},
    ],
    2750: [],
    2752: [
        {"subject": "mendiang", "subject_label": None, "relation": "LAHIR_DALAM_WUJUD", "object": "sekah", "object_label": None, "source": "manual_override"},
        {"subject": "mendiang (dalam wujud sekah)", "subject_label": None, "relation": "DIAJAK_BERKOMUNIKASI_OLEH", "object": "keluarga", "object_label": None, "source": "manual_override"},
    ],
    2794: [
        {"subject": "sekah", "subject_label": None, "relation": "DITURUNKAN_DARI", "object": "pawedan", "object_label": None, "source": "manual_override"},
        {"subject": "sangge", "subject_label": None, "relation": "JENIS_DARI", "object": "sekah", "object_label": None, "source": "manual_override"},
    ],
    2824: [
        {"subject": "sekah", "subject_label": None, "relation": "DIMASUKKAN_MELALUI", "object": "pintu belakang", "object_label": None, "source": "manual_override"},
    ],
    2894: [
        {"subject": "pralina", "subject_label": None, "relation": "KALAH_MERIAH_DIBANDING", "object": "upacara saji tarpana", "object_label": None, "source": "manual_override"},
    ],
    2954: [
        {"subject": "atma pitara", "subject_label": None, "relation": "DIMOHONKAN_AGAR_MENUJU", "object": "dewaloka", "object_label": None, "source": "manual_override"},
    ],
    2988: [
        {"subject": "pitra", "subject_label": None, "relation": "MENINGKAT_KEDUDUKAN_MENJADI", "object": "bhatara atau bhatari (sejak selesainya patileman)", "object_label": None, "source": "manual_override"},
    ],
    3001: [
        {"subject": "punia", "subject_label": None, "relation": "ADALAH", "object": "perwujudan nyata dari pernyataan parama suksma lahir batin (purusa-pradana)", "object_label": None, "source": "manual_override"},
        {"subject": "punia", "subject_label": None, "relation": "LAHIR_ATAS", "object": "jasa tuntunan yang telah dianugrahkan oleh beliau", "object_label": None, "source": "manual_override"},
        {"subject": "patileman", "subject_label": None, "relation": "DAPAT_SELESAI_SECARA", "object": "tuntas (berkat punia)", "object_label": None, "source": "manual_override"},
    ],
    3063: [
        {"subject": "jenazah", "subject_label": None, "relation": "DIBERSIHKAN_DARI", "object": "kotoran-kotoran (yang telah lama berada pada badan orang yang meninggal)", "object_label": None, "source": "manual_override"},
        {"subject": "jenazah", "subject_label": None, "relation": "DIBERSIHKAN_DARI", "object": "hal-hal yang lain", "object_label": None, "source": "manual_override"},
    ],
    3078: [
        {"subject": "jenazah", "subject_label": None, "relation": "DITUTUP_DENGAN", "object": "kain putih (dari ujung kepala hingga ujung kaki)", "object_label": None, "source": "manual_override"},
        {"subject": "jenazah (ditutup kain putih)", "subject_label": None, "relation": "BERTUJUAN", "object": "agar tidak kelihatan sama sekali", "object_label": None, "source": "manual_override"},
    ],
    3110: [
        {"subject": "daun intaran", "subject_label": None, "relation": "DIGUNAKAN_SEBANYAK", "object": "2 lembar", "object_label": None, "source": "manual_override"},
    ],
    3150: [
        {"subject": "sekar ura", "subject_label": None, "relation": "DITABURKAN_DI", "object": "setiap persimpangan jalan menuju setra", "object_label": None, "source": "manual_override"},
    ],
    3165: [
        {"subject": "anget-angetan", "subject_label": None, "relation": "DISEMBURKAN_PADA", "object": "hulu hati jenazah", "object_label": None, "source": "manual_override"},
        {"subject": "anget-angetan", "subject_label": None, "relation": "DISEMBURKAN_SAAT", "object": "upacara ngelelet", "object_label": None, "source": "manual_override"},
    ],
    3295: [
        {"subject": "jenazah", "subject_label": None, "relation": "NAIK", "object": "bale (dari arah teben menuju luanan/hulu)", "object_label": None, "source": "manual_override"},
    ],
    3330: [
        {"subject": "krama (masyarakat banjar)", "subject_label": None, "relation": "MEMBUAT", "object": "bale-bale tempat memandikan mayat", "object_label": None, "source": "manual_override"},
    ],
'''

ADDITIONS_ANCHOR = '''        {"subject": "jun pere", "subject_label": "SARANA_RITUAL", "relation": "BERISI", "object": "sembilan batang kayu cendana", "object_label": None, "source": "manual_override"},
    ],
}

for sentence_id, extra_relations in MANUAL_RELATION_ADDITIONS.items():'''

NEW_ADDITIONS = '''    # --- Iteration 3 Stage 9, region B (flag.txt S2166-S3332, tail of Part1 + all Part2) ---
    2184: [
        {"subject": "bale salunglung", "subject_label": None, "relation": "DILETAKKAN_DI", "object": "sekitar empat atau lima meter di arah hulu dari tempat pembakaran jenazah", "object_label": None, "source": "manual_override"},
    ],
    2234: [
        {"subject": "jenazah seseorang", "subject_label": None, "relation": "TERTANAM_TITIP_DI", "object": "sebuah setra", "object_label": None, "source": "manual_override"},
    ],
    2252: [
        {"subject": "mendiang (keponakan, cucu-cucu)", "subject_label": None, "relation": "TERGOLONG", "object": "keluarga sampingan (bukan keluarga satu sidikara/saling sembah)", "object_label": None, "source": "manual_override"},
    ],
    2269: [
        {"subject": "bale pamuun (dan alat-alat upakara lainnya)", "subject_label": None, "relation": "TELAH_SELESAI_SECARA", "object": "de facto", "object_label": None, "source": "manual_override"},
    ],
    2448: [
        {"subject": "bhatara-bhatari", "subject_label": None, "relation": "BERSEMAYAM_DI", "object": "pura dan pamrajan panyiwiannya", "object_label": None, "source": "manual_override"},
    ],
    2455: [
        {"subject": "pangabenan jenis (masing-masing)", "subject_label": None, "relation": "MEMILIKI", "object": "nama sendiri-sendiri", "object_label": None, "source": "manual_override"},
    ],
    2520: [
        {"subject": "atma wedana", "subject_label": None, "relation": "BERBEDA_DENGAN", "object": "ngaben (dalam hal sifat sebel)", "object_label": None, "source": "manual_override"},
    ],
    2542: [
        {"subject": "jenis atma wedana (masing-masing)", "subject_label": None, "relation": "MEMILIKI", "object": "nama dan ciri-ciri tersendiri", "object_label": None, "source": "manual_override"},
    ],
    2672: [
        {"subject": "payadnyan", "subject_label": None, "relation": "DIHIAS_PALING", "object": "indah", "object_label": None, "source": "manual_override"},
    ],
    2762: [
        {"subject": "upanisad", "subject_label": None, "relation": "TENTANG", "object": "jalan yang harus ditempuh", "object_label": None, "source": "manual_override"},
    ],
    2803: [
        {"subject": "pawedan", "subject_label": None, "relation": "JUGA_ADALAH", "object": "tempat ngajum serta mengutpeti sekah", "object_label": None, "source": "manual_override"},
    ],
    2810: [
        {"subject": "pawedan (tempat memuja)", "subject_label": None, "relation": "BUKAN_SEKADAR", "object": "\\"madyapada\\"", "object_label": None, "source": "manual_override"},
    ],
    2850: [
        {"subject": "punia (besar-kecilnya)", "subject_label": None, "relation": "SEPADAN_DENGAN", "object": "jenis yadnya dan martabat sang mayadnya", "object_label": None, "source": "manual_override"},
    ],
    2869: [
        {"subject": "pitara (menggunakan tirtha ening)", "subject_label": None, "relation": "HINGGA_TAMPAK", "object": "bayangan nya", "object_label": None, "source": "manual_override"},
    ],
    2951: [
        {"subject": "suku tunggal abu (diarak mapradaksina)", "subject_label": None, "relation": "MELAMBANGKAN", "object": "diresapkannya sinar suci hyang widhi", "object_label": None, "source": "manual_override"},
        {"subject": "abu", "subject_label": None, "relation": "BERUBAH_DARI", "object": "bekas benda badan linggasarira", "object_label": None, "source": "manual_override"},
        {"subject": "abu", "subject_label": None, "relation": "MENJADI", "object": "mahabutha yang suci", "object_label": None, "source": "manual_override"},
    ],
    3007: [
        {"subject": "pandita (selaku pemuka agama)", "subject_label": None, "relation": "MEMAKLUMI", "object": "ketentuan punia yang demikian itu", "object_label": None, "source": "manual_override"},
    ],
    3118: [
        {"subject": "daun dapdap (yang dihaluskan)", "subject_label": None, "relation": "BERGUNA_SEBAGAI", "object": "sampo pencuci rambut (keramas) bagi jenazah", "object_label": None, "source": "manual_override"},
        {"subject": "daun dapdap", "subject_label": None, "relation": "DIGUNAKAN_SAAT", "object": "upacara nyiramang layon", "object_label": None, "source": "manual_override"},
    ],
    3122: [
        {"subject": "malem (setelah dipulung, minimal dua buah)", "subject_label": None, "relation": "DITARUH_DI", "object": "atas takir", "object_label": None, "source": "manual_override"},
        {"subject": "malem (di atas takir)", "subject_label": None, "relation": "DIGUNAKAN_UNTUK", "object": "ditaruh pada kedua lubang kuping jenazah ketika upacara melelet", "object_label": None, "source": "manual_override"},
    ],
    3141: [
        {"subject": "kawangen", "subject_label": None, "relation": "DIISI", "object": "11 kepeng (ditaruh pada setiap persendian/buku-buku)", "object_label": None, "source": "manual_override"},
        {"subject": "kawangen", "subject_label": None, "relation": "DIISI", "object": "25 kepeng untuk pebaktian jenazah (ditaruh di dada, seolah-olah dipegang oleh tangan jenazah)", "object_label": None, "source": "manual_override"},
    ],
    3142: [
        {"subject": "kwangen (setiap gulungan)", "subject_label": None, "relation": "DIISI_DENGAN", "object": "uang kepeng", "object_label": None, "source": "manual_override"},
        {"subject": "kwangen", "subject_label": None, "relation": "DIISI_DENGAN", "object": "bawang putih sebagai lambang kuku (di ujungnya)", "object_label": None, "source": "manual_override"},
        {"subject": "kwangen (dengan bawang putih ini)", "subject_label": None, "relation": "DITARUH_DI", "object": "tiap-tiap jari tangan dan kaki jenazah", "object_label": None, "source": "manual_override"},
    ],
    3153: [
        {"subject": "sisig (di atas takir ini)", "subject_label": None, "relation": "DIGUNAKAN_UNTUK", "object": "gosok gigi jenazah", "object_label": None, "source": "manual_override"},
    ],
    3154: [
        {"subject": "pecahan kaca", "subject_label": None, "relation": "DITARUH_DI", "object": "kedua mata (jenazah)", "object_label": None, "source": "manual_override"},
        {"subject": "pecahan besi baja", "subject_label": None, "relation": "DITARUH_DI", "object": "gigi jenazah", "object_label": None, "source": "manual_override"},
    ],
    3294: [
        {"subject": "jenazah", "subject_label": None, "relation": "HARUS_MELALUI", "object": "ujung pepaga/asagan yang di teben (barat)", "object_label": None, "source": "manual_override"},
        {"subject": "jenazah", "subject_label": None, "relation": "DIMASUKKAN", "object": "kepala terlebih dahulu", "object_label": None, "source": "manual_override"},
        {"subject": "kaki jenazah", "subject_label": None, "relation": "BERSELONJOR_KE", "object": "teben/barat", "object_label": None, "source": "manual_override"},
    ],
    3296: [
        {"subject": "keluarga/masyarakat", "subject_label": None, "relation": "DILARANG", "object": "tergesa-gesa memandikan jenazah", "object_label": None, "source": "manual_override"},
    ],
    3330: [
        {"subject": "bale-bale (tempat memandikan mayat)", "subject_label": None, "relation": "DIKENAL_SEBAGAI", "object": "pepaga", "object_label": None, "source": "manual_override"},
        {"subject": "bale-bale (tempat memandikan mayat)", "subject_label": None, "relation": "DIKENAL_SEBAGAI", "object": "asagan", "object_label": None, "source": "manual_override"},
    ],
    3332: [
        {"subject": "pepaga", "subject_label": None, "relation": "DIKENAL_SEBAGAI", "object": "bale penusangan (istilah Denpasar)", "object_label": None, "source": "manual_override"},
        {"subject": "pepaga/asagan", "subject_label": None, "relation": "ADALAH", "object": "semacam dipan atau bale darurat", "object_label": None, "source": "manual_override"},
        {"subject": "pepaga/asagan", "subject_label": None, "relation": "DIPERGUNAKAN_SEBAGAI", "object": "usungan", "object_label": None, "source": "manual_override"},
        {"subject": "pepaga/asagan", "subject_label": None, "relation": "DIPERGUNAKAN_SEBAGAI", "object": "tandu", "object_label": None, "source": "manual_override"},
    ],
'''

assert text.count(OVERRIDES_ANCHOR) == 1, "overrides anchor not unique/found"
assert text.count(ADDITIONS_ANCHOR) == 1, "additions anchor not unique/found"

OVERRIDES_REPLACEMENT = (
    '        {"subject": "eteh-eteh sawa", "subject_label": "SARANA_RITUAL", "relation": "DIMOHONKAN_DARI", "object": "sulinggih/griya", "object_label": None, "source": "manual_override"},\n'
    "    ],\n"
    + NEW_OVERRIDES +
    "}\n\nrelations = ["
)
ADDITIONS_REPLACEMENT = (
    '        {"subject": "jun pere", "subject_label": "SARANA_RITUAL", "relation": "BERISI", "object": "sembilan batang kayu cendana", "object_label": None, "source": "manual_override"},\n'
    "    ],\n"
    + NEW_ADDITIONS +
    "}\n\nfor sentence_id, extra_relations in MANUAL_RELATION_ADDITIONS.items():"
)

text = text.replace(OVERRIDES_ANCHOR, OVERRIDES_REPLACEMENT, 1)
text = text.replace(ADDITIONS_ANCHOR, ADDITIONS_REPLACEMENT, 1)

nb["cells"][51]["source"] = text

with io.open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("patched OK")

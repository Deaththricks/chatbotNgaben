"""
Order /009: fold the ~26 deferred flag.txt corrections into MANUAL_RELATION_OVERRIDES (cell 51).

Each entry = the sentence's auto-extracted triples with good ones copied verbatim from the fresh
2026-09-07 run output and bad ones fixed/dropped per flag.txt. See
audit_tooling/iteration_3/order_009_report.md for the per-sentence rationale (user-approved,
including S2166 ADD deletion, S3800 BERUKURAN_PANJANG, S3812 split w/ DILETAKKAN_MELINTANG_DI).

Also deletes the now-superseded S2166 MANUAL_RELATION_ADDITIONS entry (wrong subject "payadnyan").

Idempotent, anchor-guarded string-replace into cell 51 source (same pattern as prior patches).
"""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CELL_INDEX = 51

# (sid, [ (subject, subject_label, RELATION, object, object_label), ... ])
OVERRIDES = [
    (2166, [
        ("naga banda", "SARANA_RITUAL", "DILETAKKAN_DI", "ruang bale semanggen", "BANGUNAN_RITUAL"),
        ("naga banda", "SARANA_RITUAL", "BERDAMPINGAN_DENGAN", "jenazah mendiang", "ISTILAH_UMUM_RITUAL"),
    ]),
    (2198, [
        ("bale salunglung", "BANGUNAN_RITUAL", "ADALAH", "bagaikan pitraloka", "KONSEP_FILOSOFIS"),
        ("bale salunglung", "BANGUNAN_RITUAL", "ADALAH", "tempat pitra mendiang yang diaben", None),
        ("bale salunglung", "BANGUNAN_RITUAL", "ADALAH", "wilayah", None),
        ("wilayah", None, "ADALAH", "kantongnya segala sesuatu yang didetasering di dunia ini", None),
    ]),
    (2234, [
        ("jenazah seseorang (yang telah tertanam-titip)", "ISTILAH_UMUM_RITUAL", "DIBAKAR", "setra lain", "BANGUNAN_RITUAL"),
    ]),
    (2337, [
        ("jenazah /pengawak", "ISTILAH_UMUM_RITUAL", "DILETAKKAN_DI", "balai-balai bade", "SARANA_RITUAL"),
        ("kajang", "SARANA_RITUAL", "DILIPAT_DI", "jenazah", "ISTILAH_UMUM_RITUAL"),
        ("kajang", "SARANA_RITUAL", "DILIPAT_DI", "simbol", None),
    ]),
    (2758, [
        ("mendiang", "ISTILAH_UMUM_RITUAL", "MENGALAMI", "perubahan wujud", None),
        ("mendiang", "ISTILAH_UMUM_RITUAL", "BERUBAH_DARI_SUKSMA_SARIRA_MENJADI",
         "tanpa berbadan sama sekali atau atma tattwatma", None),
    ]),
    (2762, [
        ("mendiang", "ISTILAH_UMUM_RITUAL", "MEMPEROLEH", "upanisad", "KONSEP_FILOSOFIS"),
        ("upanisad", "KONSEP_FILOSOFIS", "ADALAH", "pawisik", None),
        ("mendiang", "ISTILAH_UMUM_RITUAL", "MEMPEROLEH_DARI", "pendeta", None),
    ]),
    (2780, [
        ("sanggar surya baligia", "BANGUNAN_RITUAL", "MEMILIKI", "tiga buah ruang", None),
    ]),
    (2803, [
        ("pawedan", "BANGUNAN_RITUAL", "ADALAH", "tempat sang sulinggih dalam memuja", None),
        ("tempat sang sulinggih dalam memuja", None, "DIGUNAKAN_UNTUK",
         "segenap upacara atma wedana ini", None),
    ]),
    (2810, [
        ("pawedan (tempat memuja)", None, "MERUPAKAN", "shiwa (dewa) loka", None),
        ("shiwa", "ENTITAS_KEAGAMAAN", "ADALAH", "dewa loka", None),
    ]),
    (2869, [
        ("pitara", "ENTITAS_KEAGAMAAN", "MENGGUNAKAN", "tirtha ening", "TIRTHA_SUCI"),
    ]),
    (2872, [
        ("manah tirtha ening", "KONSEP_FILOSOFIS", "ADALAH",
         "pawai yang bernilai seni, lebih-lebih yang untuk pamukuran", None),
    ]),
    (2885, [
        ("sulinggih", "ENTITAS_KEAGAMAAN", "MEMBERIKAN", "panjaya-jaya", None),
        ("sulinggih", "ENTITAS_KEAGAMAAN", "MEMBERIKAN", "ayaban sesayut", "SARANA_RITUAL"),
    ]),
    (2914, [
        ("suksma sarira", "KONSEP_FILOSOFIS", "ADALAH", "materi (walaupun sangat halus)", None),
    ]),
    (2923, [
        ("mamukur dan upacara sebangsa", "RITUAL_KEMATIAN", "DILINDUNGI_DENGAN",
         "upaya penyucian wilayah yang ketat dengan berbagai pantangannya", None),
    ]),
    (2947, [
        ("abu", "SARANA_RITUAL", "DIGILING_DI_ATAS", "sesenden", "SARANA_RITUAL"),
        ("sesenden", "SARANA_RITUAL", "ADALAH", "dulang tanah", None),
    ]),
    (2986, [
        ("pitra", "KONSEP_FILOSOFIS", "BAGIAN_DARI", "sekeluarga tunggalan pamrajan", "BANGUNAN_RITUAL"),
        ("pitra", "KONSEP_FILOSOFIS", "MENERIMA", "dua buah daksina tapakan (dibuat untuknya)", "SARANA_RITUAL"),
        ("daksina tapakan", "SARANA_RITUAL", "DITUJUKAN_UNTUK", "bhatara", "ENTITAS_KEAGAMAAN"),
        ("daksina tapakan", "SARANA_RITUAL", "DITUJUKAN_UNTUK", "bhatari", "ENTITAS_KEAGAMAAN"),
    ]),
    (3091, [
        ("atma baan nyilih dan nyawa", "KONSEP_FILOSOFIS", "ADALAH",
         "pinjaman yang tidak memiliki ketentuan batas, sehingga nyawa itu dapat diambil "
         "sewaktu-waktu kapan saja tanpa ada pemberitahuan sebelumnya", None),
    ]),
    (3122, [
        ("malem", "SARANA_RITUAL", "DIPULUNG", "kelereng", None),
        ("malem", "SARANA_RITUAL", "DIPULUNG", "minimal dua buah", None),
    ]),
    (3133, [
        ("paes gedubang", "SARANA_RITUAL", "DILETAKKAN_DI", "atas takir", "SARANA_RITUAL"),
        ("paes gedubang", "SARANA_RITUAL", "DILETAKKAN_DENGAN",
         "secarik kain hitam yang digunakan untuk menutup kelamin (angkeb sarira)", None),
    ]),
    (3155, [
        ("anggapan", "SARANA_RITUAL", "ADALAH",
         "pisau khusus yang digunakan untuk memotong padi pada masa lalu", None),
        ("arit gobed", "SARANA_RITUAL", "ADALAH", "sabit kecil untuk memotong rumput", None),
    ]),
    (3195, [
        ("banten pamegat", "SARANA_RITUAL", "DIGUNAKAN_SAAT", "acara maktining layon", "SARANA_RITUAL"),
        ("banten pamegat", "SARANA_RITUAL", "DIPAKAI_UNTUK_SEBELUM", "upacara pabresihan mati", None),
        ("upacara pabresihan mati", None, "ADALAH", "ngelelet", "TAHAPAN_UPACARA"),
    ]),
    (3623, [
        ("jenazah", "ISTILAH_UMUM_RITUAL", "DIPAKAIKAN", "pakaian putih-putih", None),
        ("kain bawah", None, "BERWARNA", "putih", None),
        ("saput", None, "BERWARNA", "putih", None),
        ("umpal", None, "BERWARNA", "putih", None),
        ("umpal", None, "ADALAH", "tali saput", None),
        ("udeng (untuk laki-laki)", "SARANA_RITUAL", "BERWARNA", "putih", None),
    ]),
    (3654, [
        ("gegaleng", "SARANA_RITUAL", "TERBUAT_DARI", "uang kepeng (pipis bolong) sebanyak 250 biji", None),
        ("uang kepeng", None, "ADALAH", "pipis bolong", "SARANA_RITUAL"),
        ("gegaleng", "SARANA_RITUAL", "TERBUAT_DARI",
         "potongan-potongan dahan kayu dapdap yang dibungkus dengan kain putih", None),
    ]),
    (3800, [
        ("rurub sinom", "SARANA_RITUAL", "ADALAH", "hiasan", None),
        ("hiasan", None, "TERBUAT_DARI", "blangsah", "SARANA_RITUAL"),
        ("hiasan", None, "TERBUAT_DARI", "daun kelapa muda (busung)", None),
        ("blangsah", "SARANA_RITUAL", "ADALAH", "bunga pinang yang belum mekar", None),
        ("rurub sinom", "SARANA_RITUAL", "BERUKURAN_PANJANG", "kira-kira 40 sampai 45 sentimeter", None),
    ]),
    (3812, [
        ("jenazah", "ISTILAH_UMUM_RITUAL", "DIMASUKKAN_KE_DALAM", "peti", None),
        ("rurub sinom tadi", "SARANA_RITUAL", "DILETAKKAN_DI", "atas peti", None),
        ("rurub sinom tadi", "SARANA_RITUAL", "DILETAKKAN_MELINTANG_DI",
         "kepala, leher, perut, paha dan kaki", None),
    ]),
    (3860, [
        ("upacara mesulub", "RITUAL_KEMATIAN", "ADALAH",
         "kepercayaan setempat yang telah diwarisi turun temurun sejak jaman dulu di daerah atau desa setempat", None),
        ("kepercayaan setempat", None, "ADALAH", "kepercayaan lokal", None),
    ]),
    (3862, [
        ("upacara mesulub", "RITUAL_KEMATIAN", "ADALAH", "konsep satya (kesetiaan)", None),
    ]),
]

ANCHOR_OVERRIDES_TAIL = (
    '"object": "lambang penunjuk jalan bagi roh atau atman untuk kembali ke asalnya '
    '(brahman/alam swah loka) sebagai tujuan terakhir", "object_label": None, '
    '"source": "manual_override"},\n    ],\n}'
)

ANCHOR_S2166_ADD = (
    '\n    2166: [\n'
    '        {"subject": "payadnyan", "subject_label": None, "relation": "BERDAMPINGAN_DENGAN", '
    '"object": "jenazah mendiang", "object_label": None, "source": "manual_override"},\n'
    '    ],\n'
)


def _pystr(v):
    return "None" if v is None else json.dumps(v, ensure_ascii=False)


def render_entry(sid, triples):
    lines = [f"    {sid}: ["]
    for subj, sl, rel, obj, ol in triples:
        lines.append(
            f'        {{"subject": {_pystr(subj)}, "subject_label": {_pystr(sl)}, '
            f'"relation": {_pystr(rel)}, "object": {_pystr(obj)}, '
            f'"object_label": {_pystr(ol)}, "source": "manual_override"}},'
        )
    lines.append("    ],")
    return "\n".join(lines)


def main():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)
    cell = nb["cells"][CELL_INDEX]
    src = "".join(cell["source"])
    n0 = len(src)

    if "Order /009" in src:
        raise SystemExit("[FAIL] already patched (Order /009 marker present)")
    for sid, _ in OVERRIDES:
        # each sid must NOT already be a key in the OVERRIDES literal
        if f"\n    {sid}: [" in src.split("MANUAL_RELATION_ADDITIONS")[0]:
            raise SystemExit(f"[FAIL] S{sid} already in MANUAL_RELATION_OVERRIDES")

    # ---- 1. append the 26 entries to MANUAL_RELATION_OVERRIDES ----
    if src.count(ANCHOR_OVERRIDES_TAIL) != 1:
        raise SystemExit(f"[FAIL] OVERRIDES tail anchor count = {src.count(ANCHOR_OVERRIDES_TAIL)}")
    block = "\n\n    # --- Order /009: deferred flag.txt corrections (see order_009_report.md) ---\n"
    block += "\n".join(render_entry(sid, tr) for sid, tr in OVERRIDES)
    new_tail = ANCHOR_OVERRIDES_TAIL.replace("\n    ],\n}", "\n    ]," + block + "\n}")
    src = src.replace(ANCHOR_OVERRIDES_TAIL, new_tail, 1)

    # ---- 2. delete the superseded S2166 ADDITIONS entry ----
    if src.count(ANCHOR_S2166_ADD) != 1:
        raise SystemExit(f"[FAIL] S2166 ADD anchor count = {src.count(ANCHOR_S2166_ADD)}")
    src = src.replace(ANCHOR_S2166_ADD, "\n", 1)

    try:
        compile(src, "<cell51-patched-009>", "exec")
    except SyntaxError as e:
        raise SystemExit(f"[FAIL] patched cell 51 SyntaxError: {e}")
    print("[ok] patched cell 51 compiles cleanly")

    # sanity: every new sid parses into MANUAL_RELATION_OVERRIDES as expected
    ns = {}
    ov_start = src.index("MANUAL_RELATION_OVERRIDES = {")
    ov_end = src.index("\n}\n", ov_start) + 2
    exec(compile(src[ov_start:ov_end].replace("MANUAL_RELATION_OVERRIDES", "_OV"), "<ov>", "exec"), ns)
    ov = ns["_OV"]
    for sid, tr in OVERRIDES:
        assert sid in ov and len(ov[sid]) == len(tr), f"S{sid} did not land correctly"
    add_src = src.split("MANUAL_RELATION_ADDITIONS = {", 1)[1]
    assert "\n    2166: [" not in add_src, "S2166 ADDITIONS entry not removed"
    assert '"subject": "payadnyan", "subject_label": None, "relation": "BERDAMPINGAN_DENGAN"' not in src, \
        "S2166 payadnyan BERDAMPINGAN_DENGAN triple still present"
    print(f"[ok] {len(OVERRIDES)} override entries verified in MANUAL_RELATION_OVERRIDES; S2166 ADD removed")

    cell["source"] = src.splitlines(keepends=True)
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\nOrder /009 patch complete. {len(src) - n0:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

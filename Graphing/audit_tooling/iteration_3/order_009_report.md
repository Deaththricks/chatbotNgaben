# Order /009 — deferred-override cleanup: proposed fixes

**Context.** Iteration 3 Stage 9 hard-coded every `flag.txt` correction into cell 51, but for
~28 sentences it deliberately left the fix un-done: `flag.txt` said *"triple [N] is wrong, the
others are fine"* without quoting the exact text of the "fine" ones, so writing an all-or-nothing
`MANUAL_RELATION_OVERRIDES` entry would have meant retyping good triples from memory. The notebook
has now been run (fresh output at `Results/Final/relation_results_ngaben/`, 2026-09-07 09:53), so
the current triples for every deferred sentence are visible and can be copied verbatim.

**Method.** For each sentence: `OVERRIDES[sid]` = the *auto-extracted* triples, good ones copied
verbatim from the fresh output, bad ones fixed or dropped per `flag.txt`. Where a sentence already
has a `MANUAL_RELATION_ADDITIONS` entry (the "ADD landed" ones), that entry is **left untouched** —
it re-appends after the override, so the override only needs to carry the corrected auto set.
`subject_label` / `object_label` are copied from the current output for preserved triples, `None`
for new/changed objects. `object_type` and `context_sentence` are filled by later passes as usual.

**26 sentences below. S3720 needs nothing — its `flag.txt` ask was a pure ADD and that already
landed. All 3 open questions RESOLVED 2026-09-07: S2166 delete bad ADD, S3800 `BERUKURAN_PANJANG`
ok, S3812 split with `DILETAKKAN_MELINTANG_DI`.**

**New predicates introduced by this batch** (sync into `Neo4/normalize.py` / `relation_map.json` /
`kb/relation_phrases.json` later): `BERUBAH_DARI_SUKSMA_SARIRA_MENJADI` (S2758),
`BERUKURAN_PANJANG` (S3800), `DILETAKKAN_MELINTANG_DI` (S3812). Plus reused-but-check:
`DIGILING_DI_ATAS` (S2947), `MEMPEROLEH_DARI` (S2762).

Notation: `(subject) -[RELATION]-> (object)`. "keep" = verbatim from current output.

---

## Region B (S2166–S3332)

### S2166  — FIX [0] (add juxtaposition), drop stray "menjelang" shape
**RESOLVED: delete the existing S2166 ADDITIONS entry** (`payadnyan` subject was wrong; the
override below covers the fact).
```
(naga banda) -[DILETAKKAN_DI]-> (ruang bale semanggen)          # keep [0]
(naga banda) -[BERDAMPINGAN_DENGAN]-> (jenazah mendiang)        # the point flag.txt wants
```

### S2198 — FIX decomposition child [3], keep [0]–[2]
```
(bale salunglung) -[ADALAH]-> (bagaikan pitraloka)                       # keep [0]
(bale salunglung) -[ADALAH]-> (tempat pitra mendiang yang diaben)        # keep [1]
(bale salunglung) -[ADALAH]-> (wilayah)                                  # keep [2]
(wilayah) -[ADALAH]-> (kantongnya segala sesuatu yang didetasering di dunia ini)   # FIX [3]
```

### S2234 — FIX subject (restore "yang telah tertanam-titip"). ADDITIONS entry kept.
```
(jenazah seseorang (yang telah tertanam-titip)) -[DIBAKAR]-> (setra lain)
```

### S2337 — FIX [2] garbled object
```
(jenazah /pengawak) -[DILETAKKAN_DI]-> (balai-balai bade)   # keep [0]
(kajang) -[DILIPAT_DI]-> (jenazah)                          # keep [1]
(kajang) -[DILIPAT_DI]-> (simbol)                           # FIX [2] (was "simbol /ditindihkan")
```

### S2758 — FIX [1] wrong subject/relation (/118, predicate text as flag.txt asked)
```
(mendiang) -[MENGALAMI]-> (perubahan wujud)                                             # keep [0]
(mendiang) -[BERUBAH_DARI_SUKSMA_SARIRA_MENJADI]-> (tanpa berbadan sama sekali atau atma tattwatma)
```

### S2762 — FIX [2] agency reversal + garbled object. ADDITIONS entry (["upanisad" TENTANG …]) kept.
```
(mendiang) -[MEMPEROLEH]-> (upanisad)          # keep [0]
(upanisad) -[ADALAH]-> (pawisik)               # keep [1] (decomp)
(mendiang) -[MEMPEROLEH_DARI]-> (pendeta)      # FIX [2] (was DIPEROLEH_DARI -> "pendeta jalan")
```

### S2780 — FIX [0] (restore "tiga buah"), DROP [1] (vague, /114)
```
(sanggar surya baligia) -[MEMILIKI]-> (tiga buah ruang)
```

### S2803 — FIX [0] subject + [1] relation. ADDITIONS entry ([2] JUGA_ADALAH …) kept.
```
(pawedan) -[ADALAH]-> (tempat sang sulinggih dalam memuja)
(tempat sang sulinggih dalam memuja) -[DIGUNAKAN_UNTUK]-> (segenap upacara atma wedana ini)
```

### S2810 — FIX [0] to the sentence's central claim. ADDITIONS entry (BUKAN_SEKADAR "madyapada") kept.
```
(pawedan (tempat memuja)) -[MERUPAKAN]-> (shiwa (dewa) loka)
(shiwa) -[ADALAH]-> (dewa loka)     # keep the gloss (flag.txt: "keep either way")
```

### S2869 — DROP [1] (parenthetical etymology, /0). ADDITIONS entry (HINGGA_TAMPAK) kept.
```
(pitara) -[MENGGUNAKAN]-> (tirtha ening)      # keep [0]
```

### S2872 — FIX [0] clause-stripped (/122)
```
(manah tirtha ening) -[ADALAH]-> (pawai yang bernilai seni, lebih-lebih yang untuk pamukuran)
```

### S2885 — DROP [2] (misdirected "kepada putra-putri", /0)
```
(sulinggih) -[MEMBERIKAN]-> (panjaya-jaya)       # keep [0]
(sulinggih) -[MEMBERIKAN]-> (ayaban sesayut)     # keep [1]
```

### S2914 — FIX [0] (restore concessive, /122)
```
(suksma sarira) -[ADALAH]-> (materi (walaupun sangat halus))
```

### S2923 — FIX [0] object clause-stripped (/122)
```
(mamukur dan upacara sebangsa) -[DILINDUNGI_DENGAN]-> (upaya penyucian wilayah yang ketat dengan berbagai pantangannya)
```

### S2947 — DROP [0] (manner adverb, /0), FIX [1] relation (/119), keep [2]
```
(abu) -[DIGILING_DI_ATAS]-> (sesenden)      # FIX [1] (was DIUYEG)
(sesenden) -[ADALAH]-> (dulang tanah)       # keep [2] (decomp)
```

### S2986 — FIX [1] benefactive inversion (/119), FIX [2][3] wrong subject (/118)
```
(pitra) -[BAGIAN_DARI]-> (sekeluarga tunggalan pamrajan)                  # keep [0]
(pitra) -[MENERIMA]-> (dua buah daksina tapakan (dibuat untuknya))        # FIX [1] (was DIBUATKAN_UNTUK)
(daksina tapakan) -[DITUJUKAN_UNTUK]-> (bhatara)                          # FIX [2] subject
(daksina tapakan) -[DITUJUKAN_UNTUK]-> (bhatari)                          # FIX [3] subject
```

### S3091 — FIX [0] clause-stripped (/122)
```
(atma baan nyilih dan nyawa) -[ADALAH]-> (pinjaman yang tidak memiliki ketentuan batas, sehingga nyawa itu dapat diambil sewaktu-waktu kapan saja tanpa ada pemberitahuan sebelumnya)
```

### S3122 — DROP [2] ("ditaruh" is a verb not a noun, /0). ADDITIONS entry ([3][4]) kept.
```
(malem) -[DIPULUNG]-> (kelereng)            # keep [0]
(malem) -[DIPULUNG]-> (minimal dua buah)    # keep [1]
```

### S3133 — FIX [0] stray "bersama" (/116), FIX [1] restore purpose clause (/122)
```
(paes gedubang) -[DILETAKKAN_DI]-> (atas takir)
(paes gedubang) -[DILETAKKAN_DENGAN]-> (secarik kain hitam yang digunakan untuk menutup kelamin (angkeb sarira))
```

### S3155 — FIX both, restore purpose obliques (/122)
```
(anggapan) -[ADALAH]-> (pisau khusus yang digunakan untuk memotong padi pada masa lalu)
(arit gobed) -[ADALAH]-> (sabit kecil untuk memotong rumput)
```

### S3195 — FIX [0] relation (/119), keep [1][2]
```
(banten pamegat) -[DIGUNAKAN_SAAT]-> (acara maktining layon)        # FIX [0] (was DILAKUKAN_SAAT)
(banten pamegat) -[DIPAKAI_UNTUK_SEBELUM]-> (upacara pabresihan mati)   # keep [1]
(upacara pabresihan mati) -[ADALAH]-> (ngelelet)                    # keep [2] (decomp)
```

---

## Region C (S3333–S4340)

### S3623 — rebuild: fix nonsense "jenazah BERWARNA udeng", add missing garments (/116 /113)
```
(jenazah) -[DIPAKAIKAN]-> (pakaian putih-putih)      # keep [0]
(kain bawah) -[BERWARNA]-> (putih)
(saput) -[BERWARNA]-> (putih)                        # was missing entirely
(umpal) -[BERWARNA]-> (putih)
(umpal) -[ADALAH]-> (tali saput)                     # keep [4] (decomp)
(udeng (untuk laki-laki)) -[BERWARNA]-> (putih)      # FIX the nonsense [5]/[6]
```

### S3654 — FIX both objects (restore count + wrapping, /115)
```
(gegaleng) -[TERBUAT_DARI]-> (uang kepeng (pipis bolong) sebanyak 250 biji)
(uang kepeng) -[ADALAH]-> (pipis bolong)             # keep [1] (decomp)
(gegaleng) -[TERBUAT_DARI]-> (potongan-potongan dahan kayu dapdap yang dibungkus dengan kain putih)
```

### S3720 — NO ACTION. `flag.txt` asked only for the symbolic-purpose ADD; it landed as the
current [1] `BERMAKNA` triple. Nothing to override.

### S3800 — FIX: add busung as a material, add length, restore "belum mekar" (/113 /115)
**RESOLVED: predicate `BERUKURAN_PANJANG` approved.**
```
(rurub sinom) -[ADALAH]-> (hiasan)                                  # keep [0]
(hiasan) -[TERBUAT_DARI]-> (blangsah)                               # keep [1]
(hiasan) -[TERBUAT_DARI]-> (daun kelapa muda (busung))             # was missing
(blangsah) -[ADALAH]-> (bunga pinang yang belum mekar)              # FIX [2] (add "yang belum mekar")
(rurub sinom) -[BERUKURAN_PANJANG]-> (kira-kira 40 sampai 45 sentimeter)
```

### S3812 — FIX [1] restore position detail (/115) — user asked for MORE detail: split it
Introduces predicate `DILETAKKAN_MELINTANG_DI` (melintang = crosswise).
```
(jenazah) -[DIMASUKKAN_KE_DALAM]-> (peti)                                          # keep [0]
(rurub sinom tadi) -[DILETAKKAN_DI]-> (atas peti)                                  # FIX [1]
(rurub sinom tadi) -[DILETAKKAN_MELINTANG_DI]-> (kepala, leher, perut, paha dan kaki)   # position detail
```
The sentence also notes the position is "sama seperti ketika menaruh di atas jenazah" (same as
when it was placed on the corpse) — that's a back-reference, not adding a new fact, so not
triplified.

### S3860 — FIX [0] restore inheritance clause (/116)
```
(upacara mesulub) -[ADALAH]-> (kepercayaan setempat yang telah diwarisi turun temurun sejak jaman dulu di daerah atau desa setempat)
(kepercayaan setempat) -[ADALAH]-> (kepercayaan lokal)     # keep [1] (decomp)
```

### S3862 — FIX [0] restore coordinate gloss (/115)
```
(upacara mesulub) -[ADALAH]-> (konsep satya (kesetiaan))
```

---

## After approval

1. Patch script `audit_tooling/iteration_3/patch_009.py` appends these 26 entries to
   `MANUAL_RELATION_OVERRIDES` (anchored on the `4339:` entry's tail), plus the S2166 ADDITIONS
   edit if you approve it.
2. `audit_tooling/verify_nb.py` + `audit_tooling/harness.py` + `audit_tooling/smoke.py`.
3. You re-run the notebook once more; I verify each of the 26 sentences reads as intended in the
   fresh output.
4. Update `RELATION_AUDIT_RUNBOOK.md` changelog; `/009` closed.

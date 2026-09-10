# Chunk 3 audit (S1261..S1688)

Convergence re-audit. 59 sentences; ~35 already carry a flag.txt verdict. Most of those
verdicts are now satisfied in the data (see NOTE). New/remaining issues below.

## FIX  (triple is salvageable — give the corrected triple)

- **S1290 [0]**  current: `yadnya | BERPERAN_SEBAGAI | beban`
  fix: `yadnya | HARUS_DIRASAKAN_SEBAGAI | beban (bagi pemikulnya)`
  why: raw = "yadnya itu harus dirasakan sebagai 'beban' bagi pemikulnya" ("that yadnya
  must be *felt* as a 'burden' by the one who bears it"). Quotes mark it as figurative;
  BERPERAN_SEBAGAI states it flatly as a role and drops "bagi pemikulnya".

- **S1308 [0]**  current: `tirtha | MEMILIKI | tarif bak barang dagangan`
  fix: `tirtha | MEMILIKI | tarif`
  why: sentence is a rhetorical question — "mengapa tirtha punya tarif bak barang dagangan
  di pasar swalayan?" ("...a price like merchandise in a supermarket?"). The simile is
  rhetorical flavour; the fact actually supported by the surrounding passage ("ada
  ketentuan 'tarif' tirtha ... berdasarkan nista, madya, dan utama") is just that tirtha
  has a tarif. Drop the simile from the object.

- **S1407 [0]**  current: `ngaben jenis | DILAKUKAN_DENGAN | sawa`
  fix: `ngaben cara yama purwana tatwa | DILAKUKAN_DENGAN | sawa`
  why: subject "ngaben jenis" is a truncated fragment (parser dropped "ini"). Raw context:
  the passage is about "Ngaben ... dengan cara Yama Purwana Tatwa" / simple ngaben, and
  "Ngaben jenis ini selalu dilakukan dengan sawa". Unresolved anaphor — same class as
  flag.txt 213.

- **S1421 [0]**  current: `sawa | DIBERI | pakaian selengkap`
  fix: `sawa | DIBERI | pakaian lengkap`  (raw: "pakaian selengkapnya")
  why: "pakaian selengkap" is a broken lemma of "selengkapnya" (its full/complete attire).

- **S1422 [0]**  current: `sawa | DIPERCIKKAN_PADA | tirtha`
  fix: `sawa | DIPERCIKI_DENGAN | berbagai jenis tirtha`
  why: raw = "sawa disirati berbagai jenis tirtha" = "the corpse is sprinkled *with*
  various kinds of tirtha". Current triple reverses the roles (corpse sprinkled *onto*
  tirtha) and drops "berbagai jenis". Correct direction is shown in S1476
  (`tirtha DIPERCIKKAN_PADA kedua perlambang`).

- **S1523 [0], [1], [2]**  current: `mendiang | DITUJUKAN_UNTUK | {hyang prajapati / pura dalem / sedahan setra}`
  fix: `mendiang | BERPAMITAN_KEPADA | {hyang prajapati / pura dalem / sedahan setra}`
  why: raw = "mendiang melaku[kan] muspa pamitan kepada Sang Hyang Prajapati, Pura Dalem
  dan Sedahan Setra" = "the deceased prays a farewell to...". DITUJUKAN_UNTUK ("intended
  for") mislabels a farewell salutation and loses the "pamitan" (taking leave) sense.
  flag.txt called these 3 recipients "good", but that was under an earlier label; the
  LAINNYA/"pamitan" relation it flagged is now gone and the recipients relabelled to
  DITUJUKAN_UNTUK.

- **S1458 [0]**  current: `sesajen dan alat upakara | DISEDIAKAN_DI | rumah`
  fix: `sesajen dan alat upakara | DISEDIAKAN_DI | rumah yang bersangkutan`
  why: minor — drops "yang bersangkutan" (the household concerned) and "setuntas mungkin"
  (as completely as possible).

- **S1467 [0]**  current: `adegan dan pengawak | BERADA_DI | tempat yang telah ditentukan`
  fix: `adegan dan pengawak | DIDUDUKKAN_DI | tempat yang telah ditentukan`
  why: verb is "didudukkan" (ceremonially seated/installed) — more specific than the
  generic locative BERADA_DI.

- **S1468 [0]**  current: `upakara | DISUCIKAN_DENGAN | sajen hingga dianggap wajar untuk digunakan`
  fix: `upakara | DISUCIKAN_DENGAN | sajen`
  why: result clause "hingga dianggap wajar untuk digunakan" fused into the object.

- **S1468 [1]**  current: `upakara | DISUCIKAN_DENGAN | tirtha panglukatan dengan sajen dan tirtha panglukatan selaku sarana utama nya , hingga dianggap wajar untuk digunakan`
  fix: `upakara | DISUCIKAN_DENGAN | tirtha panglukatan`
  why: garbled run-on — "tirtha panglukatan" duplicated and the whole adverbial phrase
  swallowed into the object.

- **S1642 [0]**  current: `pelita kecil | TERBUAT_DARI | kulit telur ayam berminyak kelapa`
  fix: `angenan | TERBUAT_DARI | kulit telur ayam berminyak kelapa`
  why: raw = "angenan, merupakan sebuah pelita kecil terbuat dari...". Angenan is the
  named sarana; "pelita kecil" is its predicate nominal. Subject should be angenan.

## DROP  (triple should be removed)

- **S1439 [0]**  `abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki | DIGILING | lumat-lumat`
  why: "lumat-lumat" ("finely / to a pulp") is a reduplicated manner adverb, not an
  entity — nonsense object (same as flag.txt 2947[0]). Keep [1] (DIGILING_DI sesenden)
  and [2] (DIMASUKKAN_KE_DALAM klungah nyuh gading).

- **S1452 [0]**  `nywasta | DILAKUKAN_OLEH | orang`
  why: from "nywasta ditempuh orang" ("undertaken by people") — "orang" is generic
  filler, near-contentless. The sentence's real content is the *condition* for nywasta
  (a corpse that cannot be found: died in battle, drowned, on a distant island). Replace
  with the ADD below. flag.txt already: "the triples for this is just such a mess."

## ADD  (missing triples the sentence supports)

- **S1407**  `ngaben cara yama purwana tatwa | BERSASARAN | jenazah secara nyata`
  why: "artinya benar-benar sasarannya adalah jenazah secara nyata" — the sentence's
  actual point (this simple ngaben must act on a real corpse, not a symbolic body) is
  unextracted.

- **S1417**  `semua sarana | DIBAWA_KE | setra`
  why: "sawa beserta semua sarana diangkut ke setra" — the sarana are transported too,
  only sawa was captured.

- **S1439**  `abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki | DIBENTUK_MENJADI | sukutunggal`
  why: "serta dibentuk menjadi sukutunggal (sebuah wujud perlambang badan)" — the final
  shaping step is dropped entirely.

- **S1452**  `nywasta | DILAKUKAN_DALAM_HAL | jenazah yang tak dapat ditemukan (mati dalam pertempuran, tenggelam, di pulau seberang, dsb.)`
  why: replaces the vacuous [0]; this is the defining condition for undertaking nywasta.

- **S1558**  `sawa | DIBARINGKAN_DI | tumpang salu`
  why: "sawa kembali dibaringkan di atas tumpang salu, serta dikurung dengan
  paplengkungan" — only the DIKURUNG_DENGAN half survived.

- **S1601**  `kajang | BERFUNGSI_SEBAGAI | kain kafan teratas (pada plengkungan sawa)`
  why: after the BERADA_DI fix landed (flag.txt), the sentence's actual main predicate
  ("berfungsi sebagai 'kain kafan teratas'") is now unextracted.

- **S1639**  `kajang | DILETAKKAN_DI | paplengkungan jenazah`
  why: the sole triple is DIPUJA_PADA pamlaspasan; the main clause "kajang itu diletakkan
  di atas paplengkungan jenazah" is dropped.

- **S1642**  `angenan | ADALAH | pelita kecil`
  why: the definitional predicate nominal, currently only present as a mis-assigned
  subject.

## NOTE  (borderline / systemic observation, no single fix)

- **S1523**  "melakumuspa" in the processed TEXT is a segmentation fusion of
  "melaku[kan] muspa" (performs muspa / prayer). Could also ADD
  `mendiang | MELAKUKAN | muspa pamitan`.

- **S1465 [3], [4]**  attaching "54/108 lembar daun alang-alang" and "sembilan batang
  kayu cendana" as BERISI of *jun pere* is uncertain. Grammatically they may be coordinate
  components of *pengawak* itself (parallel to jun pere), not contents of the small pot;
  if so, [0] `pengawak TERDIRI_DARI ...` should list them and [3]/[4] be re-based to
  pengawak.

- **S1514 [0]**  `adegan | DIUSUNG | setra tempat jasad mendiang` drops "ditanam atau
  bakar titip" and is typed ISTILAH_UMUM_RITUAL (setra is BANGUNAN_RITUAL). Minor. The
  flag.txt 1514 concern (the insertion clause) is now handled by [1] (DISISIPI).

- **S1429 [0] / S1430 [0]**  long single-clause objects, faithful as written. flag.txt
  /113 on both wants component-level splitting (daksina placement on dada sawa; beras
  catur = beras putih/merah/kuning/hitam) — that content lives in adjacent sentences,
  not in S1429/S1430 themselves.

- **flag.txt fixes that still appear UN-applied in this data:**
  - S1261 [0] object still un-split (flag.txt /112).
  - S1328 [0] subject still "besar kecil punia atau honorarium ..."; flag.txt wants it
    trimmed to `punia | DISINKRONKAN_DENGAN | jenis upacara`.
  - S1456 [0] object still "ngaben yang sangat sederhana dalam hal sajen dan alat-alat
    upakaranya"; flag.txt wants "ngaben yang sangat sederhana".
  - S1461 [0] still one combined object (flag.txt /113 wants split into
    terbuat_dari / beralaskan).
  - S1609 [0] object "satu jiwa/atma paratma/brahman" still garbled; flag.txt wants
    "penyatuan jiwa/atma dengan paratma/brahman".

- **Convergence — confirmed FIXED since flag.txt** (no remaining issue): S1474 (subject
  now "sesajen", MELIPUTI + DIPERSEMBAHKAN_KEPADA), S1482 (both missing triples added),
  S1483 / S1544 / S1552 (clause retention now holding), S1493, S1533, S1558 (label),
  S1584 (all 3 requested fixes present), S1601 (label), S1602, S1603, S1606, S1629,
  S1639 (label), S1642 (object), S1688 (label + missing triple).

## Chunk stats
FIX: 13   DROP: 2   ADD: 8   sentences reviewed: 59

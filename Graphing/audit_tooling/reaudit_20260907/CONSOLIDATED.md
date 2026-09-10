# Ngaben relation extraction — convergence re-audit (2026-09-07)

Full triple-by-triple re-check of the current run (`Results/Final/relation_results_ngaben`,
916 triples / 466 sentences) against `Data/ngaben-merge-cleaned.txt`, 8 parallel auditors,
one chunk each. Same rubric as the original `flag.txt` pass.

## Verdict: converged well

| | FIX | DROP | ADD |
|---|---|---|---|
| **total** | **79** | **12** | **~60** |
| as % of 916 triples | ~9% | ~1% | — |

The original `flag.txt` audit flagged **42–66%** of the corpus. This pass flags **~10%**, and the
auditors independently confirmed that the large majority of `flag.txt` FIX/DROP/ADD items landed
correctly as `manual_override` triples. What's left is a long tail, not a systemic failure.

---

## Systemic themes (what the 79 FIX / 12 DROP break down into)

1. **`dependency_rule` triples the override pass never reached** — the single biggest bucket.
   `flag.txt` had already specified `/116` `/117` `/122` fixes for many of these, but only the
   *ADD*s and *full-replacement overrides* got written; the pure-FIX corrections on auto triples
   were left. Chunks 5, 6, 7, 8 all call this out explicitly. Examples: S2374, S2377, S2535,
   S2542, S2548, S2555, S2563 (chunk 5); S2768, S2812, S2854 (chunk 6); S3355, S3544, S3591
   (chunk 7); S4074, S4338, S4340 (chunk 8).

2. **Clause-stripping on copular objects** (`ADALAH` / `BERMAKNA` / `BERFUNGSI_SEBAGAI`) — the
   defining `yang…` / appositive / `alias` clause dropped, leaving a vague or vacuous object.
   The long-standing D1/N1 gap, now down to ~15 cases.

3. **Locative grabbed as a direct object** — `X DIMANDIKAN natar rumah` should be
   `X DIMANDIKAN_DI natar rumah`. Concentrated in chunk 2 (S957, S1039, S972, S1219) and scattered
   elsewhere (S246, S1467).

4. **Mega-fused predicates** (small count): `DITANAM_ATAU_DIBAKAR_SEMENTARA` (S1169),
   `DIPERCIKKAN_PADA_SEBELUM` (S978), `DIPAKAI_UNTUK_SEBELUM` (S3195), `DIDUDUKKAN_DULU_SEBELUM`
   (S3354), `DIMOHONKAN_AGAR_MENUJU` (S2954).

5. **Meaning reversals**: `BERASAL_DARI` for "dipindahkan dari" (S1060); sprinkle direction
   reversed (S1422); `kuburan DIAMBIL tulang` — bones taken *from* the grave (S254).

6. **Wrong relation label**: `MENUJU` vs *membujur* "lies oriented" (S366); `MELAMBANGKAN` vs
   `BERBENTUK` (S69); `DITUJUKAN_UNTUK` vs `BERPAMITAN_KEPADA` for a farewell prayer (S1523).

7. **Factual errors inside `manual_override` triples** (rare but real):
   - **S1738 [3][4]** `mendiang MEMILIKI_ALIAS ida bagus / ida ayu` — WRONG. "Ida Bagus / Ida Ayu"
     here = the priest's young *walaka* children who would cut the effigy's hair and withdraw when
     the deceased was prominent. Not aliases of the deceased. → **DROP both.**
   - **S1747 [3]** `sekah kangsen DISERTAI_DI samping jenazah` — hallucinated; "sekah kangsen"
     appears nowhere in S1747, and `DISERTAI_DI` is not a predicate. → **DROP.**

8. **Leftover redundant triples** — an override replaced a sentence's relations but a stale
   `dependency_rule` / `object_decomposition` triple survived alongside: S2000 [1], S2034 [1],
   S1714 [1], S1853 [0], S2184 [1], S1738 [0-2 flatten conditional]. → **DROP the stale one.**

9. **`X adalah simbol dari Y, yaitu Z`** construction — `dependency_rule` emits one garbled fused
   object. Needs the symbol-vs-emblem split: S3589, S3591 (and the pattern recurs).

10. **Cosmetic serialization bugs** (not content): S4062 [3] object string has the entity-type
    tag printed twice `(SARANA_RITUAL) (SARANA_RITUAL)`; S4110 [1] object typed BANGUNAN_RITUAL
    for a person (`pemangku` → ENTITAS_KEAGAMAAN).

11. **`flag.txt` fixes still un-applied** (specified but never written): S1261, S1328, S1456,
    S1461, S1609, S1782, S1963, S1987; plus the chunk-5 auto-triple list in theme 1.

---

## FIX list (all chunks, by sentence id)

Format: `S___ [i]  current → fix   | why`

### Chunk 1 (S4–S785)
- **S69 [0]** `gedarba MELAMBANGKAN beruang` → `gedarba BERBENTUK "beruang berwarna hitam"` | raw "berbentuk menyerupai beruang berwarna hitam"; berwujud≠melambangkan; restore colour
- **S81 [0]** `singa ADALAH 3:2:2` → `perbandingan kepala singa ADALAH 3:2:2` | it's a head-proportion ratio, subject dropped "perbandingan kepala"
- **S92 [0]** `"kanoroyang sanksi terberat" BERUPA pemberhentian…` → `kanoroyang ADALAH "sanksi terberat berupa pemberhentian keanggotaan desa adat"` | "sanksi terberat" fused into subject span
- **S104 [0]** → DROP (see DROP + ADD)
- **S332 [0]** `jenazah DILETAKKAN_DI "balai posisi kepala berhulu utara"` → `jenazah DILETAKKAN_DI balai` | location fused with head-orientation adjunct; dropped "atau timur" (see ADD)
- **S366 [0][1]** `jenazah MENUJU timur / utara` → `jenazah MEMBUJUR_KE timur / utara` | *membujur* = lies oriented, not *menuju* = heads toward
- **S370 [1]** `jenazah DIGULUNG_DENGAN "kain yang telah dirajah dengan tikar dan kain yang telah dirajah"` → `jenazah DIGULUNG_DENGAN "kain yang telah dirajah"` | self-duplication garble
- **S370 [3][4]** `jenazah DILETAKKAN_DI ibu jari kaki / tangan` → `itik-itik DIPASANG_PADA "ibu jari tangan dan kaki"` | wrong subject + relation; itik-itik are attached to the thumbs/toes
- **S283 [0]** `banten DIKENAL_SEBAGAI "kala puspa"` → `"banten yang menjadi simbol orang yang meninggal" DIKENAL_SEBAGAI "kala puspa"` | not all banten is kala puspa
- **S415 [0]** trim tautological tail "disebut juga malamasa" from object
- **S254 [0]** `kuburan DIAMBIL "tulang belulang"` → `"tulang belulang" DIAMBIL_DARI kuburan` | direction/subject reversed
- **S246 [0]** `puspa lingga DIAMBIL keampigan` → `puspa lingga DIBUKA keampigan` | verb is *dibuka*

### Chunk 2 (S788–S1256)
- **S923 [0]** `"jenazah momong" DISERTAI "peti samping"` → `jenazah DIIRINGI "peti (di sampingnya)"` | passive "di momong" fused into subject
- **S917 [0]** `jenazah DIBUNGKUS "kain putih setelah dimandikan"` → `"jenazah bayi" DIBUNGKUS_DENGAN "kain putih"` | infant section; qualify subject; drop fused temporal
- **S925 [0]** `jenazah DIMASUKKAN_KE_DALAM "peti kayu"` → `"jenazah bayi" DIMASUKKAN_KE_DALAM "peti kayu"` | infant section; subject qualifier only
- **S957 [1]** `"jenazah bayi" DIMANDIKAN "natar rumah"` → `… DIMANDIKAN_DI "natar rumah"` | locative-as-object
- **S1039 [0]** `jenazah DIMANDIKAN "balai-balai rumah adat"` → `… DIMANDIKAN_DI_ATAS "balai-balai rumah adat"` | locative-as-object
- **S1056 [0]** `pepaga BERFUNGSI_SEBAGAI "balai-balai alas memandikan ngringkes"` → `… BERFUNGSI_SEBAGAI "balai-balai alas ngringkes"` | garbled coordinate; [1] already covers "memandikan jenazah"
- **S1058 [0]** `pepaga DIPASANG "secarik kain putih"` → `"kain putih" DIPASANG_DI_ATAS pepaga` | direction reversed
- **S1060 [0]** `jenazah BERASAL_DARI "rumah adat"` → `jenazah DIPINDAHKAN_DARI "rumah adat"` | meaning reversal
- **S1066 [1]** `jenazah DIBERI "sarana simbolik pangringkesan, antara lain sesisir pisang…"` → `jenazah DIBERI "berbagai sarana simbolik pangringkesan"` | example already in [2]
- **S972 [0]** `"sawa anak" DIBAKAR "pitra yadnya nglungah"` → `"sawa anak yang telah berusia lima bulan ke atas" DIBAKAR_DALAM "pitra yadnya nglungah"` | age qualifier is the whole point; "dibakar dalam" = burned within the ceremony
- **S1017 [0]** `mahabutha DITUJUKAN_UNTUK "induk asal"` → `"mahabutha (yang lima unsur)" KEMBALI_KEPADA "induk asalnya masing-masing"` | "kembali kepada" ≠ "ditujukan untuk"; "masing-masing" dropped
- **S1188 [3]** `"upacara ini" MEMPERGUNAKAN "pabersihan" (TAHAPAN_UPACARA)` → `"upacara ngaben titip" MEMPERGUNAKAN "tirtha pabersihan" (TIRTHA_SUCI)` | shared head "Tirtha [Panglukatan dan Pabersihan]"; wrong type
- **S1188 [2][3]** subject `upacara ini` → resolve to `upacara ngaben titip`
- **S1219 [0]** `sawa DIBAKAR "alat pangringkesan"` → `sawa DITANAM_ATAU_DIBAKAR_BERSAMA "semua alat pangringkesan"` | tools buried/burned *with* the corpse; "ditanam atau" dropped
- **S978 [0]** `tirtha DIPERCIKKAN_PADA_SEBELUM "tirtha pangentas"` → `"tirtha (dari pamrajan/kahyangan tiga/prajapati)" DIPERCIKKAN_SEBELUM "tirtha pangentas"` | mega-fused predicate; split temporal frame (see ADD)

### Chunk 3 (S1261–S1688)
- **S1290 [0]** `yadnya BERPERAN_SEBAGAI beban` → `yadnya HARUS_DIRASAKAN_SEBAGAI "beban (bagi pemikulnya)"` | "harus dirasakan sebagai" — figurative, quoted
- **S1308 [0]** `tirtha MEMILIKI "tarif bak barang dagangan"` → `tirtha MEMILIKI tarif` | rhetorical-question simile
- **S1407 [0]** `"ngaben jenis" DILAKUKAN_DENGAN sawa` → `"ngaben cara yama purwana tatwa" DILAKUKAN_DENGAN sawa` | truncated fragment subject (dropped "ini")
- **S1421 [0]** `sawa DIBERI "pakaian selengkap"` → `sawa DIBERI "pakaian lengkap"` | broken lemma of "selengkapnya"
- **S1422 [0]** `sawa DIPERCIKKAN_PADA tirtha` → `sawa DIPERCIKI_DENGAN "berbagai jenis tirtha"` | direction reversed; "berbagai jenis" dropped
- **S1523 [0][1][2]** `mendiang DITUJUKAN_UNTUK {hyang prajapati / pura dalem / sedahan setra}` → `mendiang BERPAMITAN_KEPADA {…}` | "muspa pamitan kepada" — a farewell prayer
- **S1458 [0]** append "yang bersangkutan" to object (minor)
- **S1467 [0]** `"adegan dan pengawak" BERADA_DI "tempat yang telah ditentukan"` → `… DIDUDUKKAN_DI …` | verb is "didudukkan"
- **S1468 [0]** `upakara DISUCIKAN_DENGAN "sajen hingga dianggap wajar untuk digunakan"` → `upakara DISUCIKAN_DENGAN sajen` | result clause fused
- **S1468 [1]** garbled run-on → `upakara DISUCIKAN_DENGAN "tirtha panglukatan"`
- **S1642 [0]** `"pelita kecil" TERBUAT_DARI "kulit telur ayam berminyak kelapa"` → `angenan TERBUAT_DARI …` | angenan is the named sarana; "pelita kecil" is its predicate nominal (see ADD)

### Chunk 4 (S1699–S2198)
- **S1782 [0]** object dumps the sentence → `pamerasan ADALAH "upacara timbang terima (secara keagamaan)"` + ADD `pamerasan DILAKUKAN_ANTARA "mendiang dan keluarga yang masih hidup"` | flag.txt 1782 /112 not applied; "timbang terima" truncated to "timbang"
- **S1982 [0]** `bade ADALAH "bangunan sawa"` → `bade ADALAH "bangunan untuk sawa"` | dedup dropped "untuk" (purposive sense)
- **S1987 [0]** `"bade jenis" ADALAH "bade dalam tata kemasyarakatan…"` → `"jenis bade yang dipakai seseorang" DITENTUKAN_BERDASARKAN "status orang tersebut dalam tata kemasyarakatan pada zaman itu"` | nonsense both ends; real predicate is "ditentukan berdasarkan"
- **S2034 [0]** `mangle ADALAH "pengganti tingkat bade"` → `mangle ADALAH "pengganti tingkat bade atau wadah"` | 2-item list, 2nd member dropped
- **S2045 [0]** `patulangan MENGHASILKAN "bentuk yang berwujud binatang, yang mempunyai nilai religi tertentu"` → `patulangan DIBUAT_BERBENTUK "binatang (yang mempunyai nilai religi tertentu)"` | MENGHASILKAN mislabel
- **S2055 [0]** subject over-generalizes → `"patulangan yang berbentuk naga kahang dan gajah mina" ADALAH "pertanda bahwa keluarga tersebut keturunan dari orang yang condong pada paksa wesnawa"` | "mereka" unresolved anaphora

### Chunk 5 (S2212–S2686) — all `flag.txt`-specified, mostly `dependency_rule`, never written
- **S2234 [0]** `"jenazah seseorang (yang telah tertanam-titip)" DIBAKAR "setra lain"` → `… DIABEN_DI "setra lain"` | verb is *diaben*; setra is a location (locative missing)
- **S2336 [3]** `kajang DIBERI "30 meter"` → fold into [2] as `SEPANJANG "dua atau 30 meter"` or DROP | stranded measurement fragment
- **S2364 [0]** `bade DILETAKKAN_DI "teben lembu"` → `bade DILETAKKAN_DI "sebelah hilir atau teben lembu"` | disjunct dropped
- **S2374 [0]** append "dari sesuatu, atau gerak ke atas" to object | truncated
- **S2377 [0]** `ngaben MEMILIKI "tujuan pokok"` → `ngaben BERTUJUAN_POKOK "merubah jenazah… kembali menjadi pancamahabutha sebagaimana asalnya semula"` | empty head; purpose clause is the sentence
- **S2380 [1]** `"cara prasawya" ADALAH berputar` → `… ADALAH "berputar ke kiri, berlawanan dengan putaran jarum jam"` | bare verb; parenthetical gloss is the definition
- **S2535 [0]** append "(yang merupakan 'kulit dirinya')" to object | defining appositive dropped
- **S2542 [0]** `"atma wedana" MEMILIKI jenis` → `… MEMILIKI "beberapa jenis"` | quantifier dropped
- **S2548 [0][1]** append "(hanya sekali saja)" to each object | defining ritual constraint dropped
- **S2555 [0]** `"atma wedana" ADALAH "upacara penyucian pitra"` → `… ADALAH "nama resmi upacara penyucian pitra"` | "nama resmi" framing is the point
- **S2563 [0]** append "yang mudah ditimpa suasana 'sebel'" to object | defining relative clause dropped
- **S2612 [0]** `pitra DIBUATKAN_UNTUK perlambang` → `"pitra mendiang" DIBUATKAN "perlambang (yang disebut sekah kangsen)"` | benefactive still inverted; subject fix
- **S2623 [1]** verbatim-duplication in object → `"sekah kangsen" DISUCIKAN_DENGAN "sajen kecil (sebagai pengantar)"`

### Chunk 6 (S2748–S3295)
- **S2768 [0]** `sangge ADALAH dia` → `sangge ADALAH "'sang ngae' diri kita"` | object truncated to bare pronoun; folk-etymology lost
- **S2812 [1]** `pitra ADALAH atma` → `pitra ADALAH "atma yang masih bersuksmasarira"` | relative clause is what distinguishes pitra from atma
- **S2854 [1]** `"pitra mendiang" MENYAKSIKAN "anak cucu"` → `… MENYAKSIKAN "anak cucunya melakukan upacara manusa yadnya tersebut"` | embedded clause is the content
- **S3153 [0]** `sisig TERBUAT_DARI "arang pembakaran jaja gina uli"` → `… "arang pembakaran jaja gina"` | word-merge garble; [1] holds "jaja uli", [0] should be the other disjunct "jaja gina"
- **S2777 [1]** `utpeti ADALAH masuk` → `utpeti ADALAH "masuk dan menghuni"` | 2nd coordinate member dropped
- **S2777 [4]** `bhatara BERPERAN_SEBAGAI "badan suksma"` → `puspalingga BERPERAN_SEBAGAI "badan suksma bhatara"` | *selaku badan suksmanya* modifies puspalingga; wrong subject
- **S2777 [0]** `bhatara DITUJUKAN_UNTUK utpeti` → `bhatara DIPERSILAKAN_UNTUK utpeti` | "dipersilakan untuk" = invited to
- **S2948 [0]** restore both defining relative clauses on subject + object (minor)
- **S2819 [0]** append "di mercapada ini" to object (minor locative)
- **S3004 [1]** object still drops "yang bersangkutan" → append it

### Chunk 7 (S3296–S3862)
- **S3355 [0]** `jenazah MEMILIKI "makna agar…menemui brahman"` → `"jenazah yang masuk melalui teben dari pepaga" BERMAKNA "agar orang yang meninggal lebih cepat menemui brahman (sang pencipta)"` | condition dropped; trim "makna" noun
- **S3544 [0]** `kawangen MELAMBANGKAN "tanda doa restu setelah selesai upacara sembah bhakti ini ,"` → `kawangen MELAMBANGKAN "tanda doa restu"` | stray leading temporal clause fused; purpose clause dropped (see ADD)
- **S3591 [0]** scrambled run-on → split: `"anggapan (ani-ani atau ketam)" ADALAH "simbol Dewi Sri"` + `anggapan MELAMBANGKAN kesuburan` | "dari dewi sri" duplicated
- **S3589 [0]** fused object → split: `"arit gobed" ADALAH "simbol Rare Angon"` + `"arit gobed" MELAMBANGKAN "keperkasaan seorang laki-laki"`
- **S3728 [1]** `numitis MENYEBABKAN "badan menjadi harum"` → `"penggunaan wewangian" BERTUJUAN_AGAR "tubuh jenazah kelak berbau harum"` | wrong subject + invented predicate
- **S3339 [2]** drop the "(rumah adat Bali)" gloss on `bale semanggen` — mislabels the entity

### Chunk 8 (S3868–S4340)
- **S4074 [0]** run-on object dumps two `sehingga` clauses → `"tirtha ening" BERFUNGSI_SEBAGAI "simbol pikiran dan perasaan sang yajamana (orang yang punya upacara)"` (move consequences to ADD)
- **S4338 [1]** `"tirtha pangentas" ADALAH penyucian` → `… ADALAH "alat sangaskara atau penyucian kepada roh atau atman orang yang telah meninggal dunia"` | clause-stripped to near-vacuity; merge with [0]
- **S4340 [0]** `"tirtha pangentas" BERFUNGSI_SEBAGAI "pelebur unsur karma wasana"` → `… "pelebur unsur karma wasana yang mengikat roh atau atman"` | flag.txt 934 /115 still open
- **S4035 [1]** `"priuk…" DIPECAHKAN "setelah tirtha dipercikkan"` → demote temporal to parenthetical, or DROP (redundant with [2])

---

## DROP list

- **S104 [0]** `"bali aga vs bali dataran" MEMPEROLEH "perbedaan mendasar"` — heading-as-subject + "vs"; nonsense predicate (replace with 2 ADDs)
- **S1439 [0]** `"abu tulang…" DIGILING "lumat-lumat"` — reduplicated manner adverb, not an entity
- **S1452 [0]** `nywasta DILAKUKAN_OLEH orang` — near-contentless "orang" filler (replace with ADD)
- **S1738 [3]** `mendiang MEMILIKI_ALIAS "ida bagus"` — factually wrong (priest's children, not the deceased)
- **S1738 [4]** `mendiang MEMILIKI_ALIAS "ida ayu"` — same
- **S1747 [3]** `"sekah kangsen" DISERTAI_DI "samping jenazah"` — hallucinated subject; not a predicate
- **S1853 [0]** `"lontar putru" MEMILIKI jenis` — vacuous; [1]/[2] name the types
- **S2000 [1]** `"jenazah raja bali" ADALAH "gelgel/klungkung"` — a corpse is not a place; redundant with [3]
- **S2034 [1]** `mangle DILETAKKAN_DI wadah` — misreads coordinate "bade atau wadah" as a location
- **S1714 [1]** `adegan DITUJUKAN_UNTUK pendeta` — the sembah bakti is directed to the priest, not the adegan; redundant
- **S2184 [1]** `"bale salunglung" DILETAKKAN_DI "arah hulu"` — redundant with and less precise than [2]
- **S3134 [3]** `lekesan DILETAKKAN_DI "ujung atas"` — misparse; covered by [2]

---

## ADD list (missing triples the source supports)

**Chunk 1:** S104 (`bali aga MEMPERTAHANKAN "tradisi asli kuno"` + `bali dataran MENDAPAT_PENGARUH_DARI "tradisi hindu-majapahit"`), S124, S126 (2×`ngaben BERFUNGSI_SEBAGAI …`), S128, S6 (`ngaben BERAKAR_PADA "filosofi pelepasan jiwa…"`), S44 (formalin), S47 (2× baby-corpse procedural), S217 (3× pelebon events), S265, S332 (orientation), S364 (2× nanginin), S376, S399 (`sasih karo ADALAH "sasih utama…"`), S254 (`kuburan DIBONGKAR`), S780 (2×).

**Chunk 2:** S789 (`orangtua ADALAH ibu`), S792 (`pitra yadnya DITUJUKAN_UNTUK leluhur`), S851 (`manusia DINILAI_SEBAGAI "pihak berhutang"`), S1016 (2×), S1060 (2×), S1215 (`sawa DILETAKKAN_DI "para-para…"`), S1058, S957 (`dusa ADALAH …`), S974.

**Chunk 3:** S1407, S1417 (`"semua sarana" DIBAWA_KE setra`), S1439 (`DIBENTUK_MENJADI sukutunggal`), S1452, S1558 (`sawa DIBARINGKAN_DI "tumpang salu"`), S1601 (`kajang BERFUNGSI_SEBAGAI "kain kafan teratas"`), S1639, S1642 (`angenan ADALAH "pelita kecil"`).

**Chunk 4:** S1717 (`adegan ADALAH "alat upakara"`), S1963 (4× placement + `pering MELAMBANGKAN "purusa-pradana"`), S2002 (`bade MEMILIKI_TINGKAT tujuh`), S2087 (`naga banda DIGUNAKAN_DALAM "upacara palebon"`), S1845.

**Chunk 5:** S2323 (`"bade dan lembu" MENJADI "sarana siap pakai (setelah diplaspas)"`), S2363 (`"bale pamuunan" DIHUNI lembu`), S2380 (`bade BERLAWANAN_DENGAN "gerak pradaksina…"`), S2473 (`"pangabenan…pranawa" DILATARBELAKANGI_OLEH "hasrat supaya mendiang memperoleh ketenangan, kemantapan, kesucian"`).

**Chunk 6:** S2969 (`ngajar-ajar BERMAKNA "ucapan terima kasih…kepada para penuntun"`), S2777 (`bhatara DIPENDAK_SECARA khusus`), S3110 (`"daun intaran" DITARUH_DI "kedua alis jenazah (ketika ngelelet)"`).

**Chunk 7:** S3544 (`"kawangen (di samping jenazah)" BERTUJUAN_AGAR "perjalanan roh…tidak mendapat halangan"`), S3591 (`"penggunaan anggapan" BERTUJUAN_AGAR "wanita yang numitis memiliki kesuburan…"`), S3355 (`jenazah DIMASUKKAN_MELALUI "teben pepaga/asagan"`), S3546 (`jenazah DIISI_DENGAN "kawangen di tangan"`), S3799 (`jenazah DITUTUPI_DENGAN "kain putih (panjang ~2–2,5 m)"`).

**Chunk 8:** S3977 (`jenazah DIBILAS_DENGAN air` + `jenazah DIKERINGKAN_DENGAN "kain kering"` + `"pemakaian umbi sikapa/sekapa" BERMAKNA "agar kulit orang yang meninggal putih bersih (jika numitis)"`), S4074 (2× `sehingga` consequences), S4338 (`"roh atau atman" NAIK_KEDUDUKAN_DARI "preta menjadi pitara"` + `pitara DAPAT_MEMASUKI "alam bwah loka"`), S4079 (`"tirtha pemanah" DIBUAT_SAAT "upacara pengaskaran"`), S3963 (minor).

---

## Cosmetic bugs (not `MANUAL_RELATION_*` — need a code look)

- **S4062 [3]** — object string carries the entity-type tag twice: `"adegan (SARANA_RITUAL) (SARANA_RITUAL)"`. Serialization double-append somewhere in cell 51 §13.9e.
- **S4110 [1]** — `"pemangku kahyangan tiga setempat"` typed `BANGUNAN_RITUAL`; a `pemangku` is a person (`ENTITAS_KEAGAMAAN`). S4105 [1] (parallel sentence) is correctly typed — worth a diff.

---

## Recommended next step

This is an **Iteration 4 fix batch** — smaller than Iteration 3. Almost all FIX/DROP entries are
`MANUAL_RELATION_OVERRIDES` work (same mechanism as `/009`), plus:
- 2 cosmetic code bugs (S4062, S4110) to trace in cell 51.
- Theme 1 suggests a cheaper systemic option for the ~15 `dependency_rule` clause-strip cases:
  the auto extractor's copular-object path still doesn't retain a trailing defining `yang…`
  clause in these specific shapes — but a code fix there is higher-risk than 15 overrides.

Suggest: you review this list, mark KEEP/SKIP on anything you disagree with, and I fold the rest
into an Iteration 4 override batch + fix the 2 code bugs, then you re-run once.

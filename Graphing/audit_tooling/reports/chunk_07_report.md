# Chunk 7 audit (S3155..S3812)

## FIX  (triple is salvageable — give the corrected triple)

- **S3155 [0]**  current: `anggapan (ani-ani/ketam) | ADALAH | pisau khusus`
  fix: `anggapan | ADALAH | pisau khusus yang digunakan untuk memotong padi pada masa lalu`
  why: N1 regression — copula object is a generic noun ("pisau khusus") and the defining "yang digunakan untuk..." clause is stripped, losing the whole point (what it's used for and when).

- **S3155 [1]**  current: `arit gobed | ADALAH | sabit kecil`
  fix: `arit gobed | ADALAH | sabit kecil untuk memotong rumput`
  why: same N1 pattern — purpose oblique "untuk memotong rumput" dropped.

- **S3165 [0]**  current: `anget-angetan | DIPERCIKKAN_PADA | hulu hati jenazah`
  fix: `anget-angetan | DISEMBURKAN_PADA | hulu hati jenazah`
  why: text says "dikunyah dan kemudian disemburkan" (chewed then sprayed from the mouth), not "dipercikkan" (sprinkled). Wrong relation label (failure mode 5).

- **S3165 [1]**  current: `anget-angetan | DIPERCIKKAN_PADA | upacara ngelelet`
  fix: drop, or `anget-angetan | DISEMBURKAN_SAAT | upacara ngelelet`
  why: "pada saat upacara ngelelet" is a time adjunct (obl:tmod), not something the herbal mix is applied "onto" — current object type/relation misrepresents a ceremony name as a physical target.

- **S3237 [0]**  current: `tembakau | JENIS_DARI | lekesan`
  fix: `lekesan | BERISI/TERMASUK | tembakau`
  why: gloss — lekesan = a rolled betel-leaf (sirih) quid; "isinya termasuk tembakau" = its contents include tobacco. Direction/predicate is reversed; lekesan is the container/whole, tembakau one ingredient.

- **S3283 [0]**  current: `jenazah | BERASAL_DARI | tebenan`
  fix: `jenazah | DITARUH_DARI_ARAH | tebenan (barat)`
  why: this is a directional-placement question ("ditaruh dari... harus dari 'tebenan'"), not an origin/ancestry fact. BERASAL_DARI wrongly implies the corpse "comes from" tebenan. Note the sentence is phrased as an open question ("apakah boleh... atau harus...") — treat as describing a debated convention, not a settled fact.

- **S3295 [0]**  current: `jenazah | LAINNYA | bale teben`
  fix: `jenazah | NAIK | bale (dari arah teben menuju luanan/hulu)`
  why: LAINNYA is a vacuous catch-all label; the garbled object "bale teben" conflates the platform (bale) with the direction of approach (teben). Text: the corpse ascends the bale from the teben (foot) end heading toward luanan/hulu (head end), not from the side. See ADD below for the split-out direction facts.

- **S3330 [0]**  current: `krama | MENGHASILKAN | bale-bale tempat`
  fix: `krama (masyarakat banjar) | MEMBUAT | bale-bale tempat memandikan mayat`
  why: minor label fix (MEMBUAT is the actual verb; MENGHASILKAN is an odd paraphrase). The bigger loss is the missing alias — see ADD.

- **S3340 [1]**  current: `tempat penusangan | ADALAH | nyiramang layon`
  fix: `tempat penusangan | DIGUNAKAN_UNTUK | nyiramang layon`
  why: category mismatch — a place cannot be equated (ADALAH) with an event/ceremony name; it's the place *where* that ceremony happens. Also see ADD for "yang berupa pepaga atau asagan," entirely dropped.

- **S3354 [0]**  current: `jenazah | MENUJU | pepaga/asagan`
  fix: `jenazah | NAIK_KE | pepaga/asagan`
  why: text says "naik ke" (climbs/ascends onto), not "menuju" (heads toward) — understates that the corpse is actually placed on top of it. See ADD for the dropped duduk→tidur sequence.

- **S3446 [0]**  current: `jenazah | DIBERI | pakaian layak orang`
  fix: `jenazah | DIBERI | pakaian seperti layaknya orang masih hidup`
  why: drops "masih hidup" (still alive) — the entire symbolic point of the sentence (dressing the corpse as if it were still living) is lost.

- **S3496 [1]**  current: `lekesan | DIBERSIHKAN_DENGAN | cara mengusap-usapkan tembakau pada bibir jenazah`
  fix: `jenazah (bibir) | DIBERSIHKAN_DENGAN | tembakau (diusapkan pada bibir)`
  why: wrong subject — it's the corpse's lips/mouth being cleaned by rubbing tobacco, not the lekesan itself being cleaned.

- **S3544 [0]**  current: `kawangen | MELAMBANGKAN | tanda doa restu`
  fix: `kawangen | MELAMBANGKAN | tanda doa restu agar perjalanan roh yang meninggal tidak mendapatkan halangan`
  why: N1-style truncation — purpose clause ("so the deceased's soul-journey meets no obstacle") dropped.

- **S3546 [1]**  current: `pabersihan hidup tangan jenazah/layon | DILETAKKAN_DI | dada`
  fix: `tangan jenazah/layon | DILETAKKAN_DI | dada`
  why: subject-fusion bug — a TAHAPAN_UPACARA phrase ("pabersihan hidup") got glued onto "tangan jenazah/layon" into one wrong compound subject. Real subject is just "tangan jenazah/layon" (the hand), placed on the chest at the end of pabersihan hidup.

- **S3546 [2]**  current: `pabersihan hidup tangan jenazah/layon | DITARUH_DENGAN | telapak tangan`
  fix: `tangan jenazah/layon | DITARUH_DENGAN | posisi telapak tangan ditumpuk (ditumpangkan)`
  why: same subject-fusion bug; also entirely missing is the reason this is done — "diisi sebuah kawangen sebagai simbol sikap amusti karana" (filled with a kawangen as a symbol of the amusti karana prayer gesture, because the corpse is treated as if joining in worship) — see ADD.

- **S3559 [0]**  current: `waja | LAINNYA | panca datu`
  fix: `waja | BAGIAN_DARI | panca datu`
  why: gloss — "meka" ≈ Balinese "adalah/yaitu"; waja (steel/iron) is one of the panca datu (the five sacred ritual metals, cf. S3755–S3758's perak/tembaga/emas/besi/logam-campuran table). LAINNYA is a vacuous label for a real equivalence/membership fact.

- **S3584 [0]**  current: `pengerikan kuku mutlak | DILAKUKAN_SAAT | upacara`
  fix: `pengerikan kuku mutlak | DILAKUKAN_SAAT | upacara "melelet" (pabersihan mati)`
  why: object "upacara" alone drops the actual ceremony name entirely. See ADD for the missing prohibition (must NOT be done during pabersihan hidup).

- **S3586 [0]**  current: `jenazah | DIKENAL_SEBAGAI | orang`
  fix: `jenazah | DIANGGAP_SEBAGAI | orang yang masih hidup`
  why: **this is the exact sentence flagged as an N1 failure in Iteration 1 and it is still broken.** "Dianggap sebagai" (regarded/considered as) is the real verb, not "dikenal sebagai" (known as); and "yang masih hidup" (still alive) — the entire point of the passage — is dropped. N1 fix is NOT holding for this sentence.

- **S3589 [0]**  current: `arit gobed | ADALAH | simbol rare angon`
  fix: `arit gobed | ADALAH | simbol dari rare angon, yaitu lambang keperkasaan seorang laki-laki`
  why: N1 truncation — the "yaitu lambang..." appositive continuation is dropped. Gloss: rare angon = a shepherd-boy folklore figure; lambang keperkasaan = symbol of a man's virility/machismo.

- **S3591 [0]**  current: `anggapan | ADALAH | simbol dewi sri`
  fix: `anggapan | ADALAH | simbol dewi sri, yaitu lambang kesuburan, agar wanita yang kelak numitis memiliki kesuburan untuk melahirkan`
  why: N1 truncation — the entire symbolic-purpose payload ("yaitu lambang kesuburan, yang mana...") is dropped. Gloss: numitis = to be reincarnated/reborn; dewi sri = rice/fertility goddess.

- **S3623 [1]**  current: `jenazah | DIPAKAIKAN | pakaian`
  fix: `jenazah | DIPAKAIKAN | pakaian (berwarna putih)`
  why: "pakaian atau kain bawahnya berwarna putih" — the shared color qualifier is dropped from both list alternatives (see next item too).

- **S3623 [2]**  current: `jenazah | DIPAKAIKAN | kain bawah`
  fix: `jenazah | DIPAKAIKAN | kain bawah (berwarna putih)`
  why: same color-qualifier loss as [1].

- **S3623 [6]**  current: `jenazah | BERWARNA | udeng laki-laki`
  fix: `udeng (untuk laki-laki) | BERWARNA | putih`
  why: nonsense triple — the corpse itself is not "colored" by a headdress; the headdress is white. Subject/object are swapped/fused (failure mode 3). Note "saput" (the shroud) is separately mis-parsed as an adjective in this sentence and never captured as a garment at all — see ADD.

- **S3649 [0]**  current: `jenazah | BERBANTALKAN | kapuk`
  fix: `bantal kapuk | DIGANTI_DENGAN | bantal sesisir buah pisang kayu`
  why: the current triple states the OLD practice as if current, but the sentence's actual point is a substitution ("yang tadinya... berbantalkan kapuk diganti dengan bantal sesisir buah pisang kayu"). As extracted, this misrepresents present practice.

- **S3654 [0]**  current: `gegaleng | TERBUAT_DARI | uang kepeng`
  fix: `gegaleng | TERBUAT_DARI | uang kepeng (pipis bolong) sebanyak 250 biji`
  why: drops the count (250 biji) — lost nuance.

- **S3654 [2]**  current: `gegaleng | TERBUAT_DARI | potongan-potongan dahan kayu dapdap`
  fix: `gegaleng | TERBUAT_DARI | potongan-potongan dahan kayu dapdap yang dibungkus dengan kain putih`
  why: drops "yang dibungkus dengan kain putih" (wrapped in white cloth).

- **S3656 [0]**  current: `gegaleng | ADALAH | pengganti bantal kapuk`
  fix: `gegaleng | ADALAH | pengganti bantal kapuk yang dipakai pada waktu pabersihan hidup`
  why: N1 truncation of the "yang telah dipakai..." clause. See ADD for the entirely-missing alias "galeng pengerekan."

- **S3694 [0]**  current: `atma | MENINGGAL | badan`
  fix: `atma | LEPAS_BEBAS_DARI | badan`
  why: nonsense triple — text says the soul (atma) is "released free from" the body ("lepas bebas dari badannya"), not that the soul "died" the body. Subject/predicate/object scrambled.

- **S3728 [0]**  current: `numitis | MEMPEROLEH | pujian keharuman`
  fix: `penggunaan wewangian | BERTUJUAN_AGAR | orang yang numitis memperoleh pujian keharuman dalam tingkah lakunya`
  why: wrong subject — "numitis" (reincarnation, an abstract process) can't itself "obtain praise"; it's the reincarnated person, and the actual topic sentence is about the purpose of using fragrance/perfume (wewangian), entirely dropped as subject. See ADD for the second dropped clause (body becoming fragrant).

- **S3742 [0]**  current: `kesuna | BERMAKNA | orang`
  fix: `kesuna (bawang putih) | BERMAKNA | agar orang yang numitis kembali memiliki kuku-kuku yang indah dan putih bersih`
  why: object "orang" alone is meaningless; the whole point (fingernails becoming beautiful/clean upon reincarnation) is dropped. Gloss: kesuna = bawang putih = garlic.

- **S3747 [0]**  current: `kawangen | DIISI_DENGAN | hulu hati`
  fix: `kawangen | DILETAKKAN_DI | hulu hati`  (+ see ADD for the contents triple)
  why: **N4, confirmed still open exactly as flagged in Iteration 1.** "Di hulu hati, diisi sebuah kawangen yang berisi 9 biji uang kepeng dan bunga tunjung putih" describes (a) where the kawangen is placed (hulu hati) and (b) what it contains (9 kepeng coins + white lotus flower) — the extractor instead produces the nonsensical "kawangen filled-with hulu-hati," dropping the contents entirely.

- **S3749 [0]**  current: `kawangen | DIISI_DENGAN | dada`
  fix: `kawangen | DILETAKKAN_DI | dada`  (+ see ADD)
  why: same N4 bug as S3747, still open — confirmed.

- **S3753 [0]**  current: `kawangen | DIISI_DENGAN | kedua lutut kaki`
  fix: `kawangen | DILETAKKAN_DI | kedua lutut kaki`  (+ see ADD)
  why: same N4 bug, still open — confirmed.

- **S3783 [0]**  current: `tirtha | DIPERCIKKAN_PADA | badan`
  fix: `tirtha | DIPERCIKKAN_PADA | seluruh badan hingga ke kaki jenazah`
  why: drops "hingga ke kaki jenazah" (down to the corpse's feet). See ADD for the entirely-missing second half of the sentence (the pot being broken and discarded).

- **S3799 [1]**  current: `jenazah | DIISI_DENGAN | rurub sinom`
  fix: `kain (penutup jenazah) | DIISI/DILETAKKAN | rurub sinom sebanyak lima buah`
  why: wrong subject — text says "di atas kain tersebut diisi rurub sinom..." (on top of that cloth, 5 rurub sinom are placed), not that the corpse itself is "filled with" rurub sinom. Also recovers the dropped count ("sebanyak lima buah").

- **S3811 [0]**  current: `rurub sinom | DITUJUKAN_UNTUK | jenazah`
  fix: `rurub sinom | DIAMBIL_DARI | gulungan jenazah (sebelum dimasukkan ke peti)`
  why: the sentence is about removing the rurub sinom before coffining a corpse, not about the rurub sinom being generically "for" the corpse. Current triple misreads the sentence's actual action (failure mode 5).

## DROP  (triple should be removed)

- **S3334 [0]**  `kesembilan galar | DITARUH | bilah bambu`
  why: self-referential nonsense — "galar atau bilah bambu" is one entity (galar = bilah bambu per apposition), so subject and object are the same referent. The real content ("bilah bambu yang nomer 5/di tengah diletakkan terbalik") is entirely missing — see ADD.

- **S3733 [1]**  `kwangen jeriji | DITARUH | kawangen jeriji`
  why: self-loop — subject and object are the same entity (kwangen/kawangen jeriji spelled two ways). Contributes nothing.

- **S3742 [1]**  `kesuna | MEMILIKI | kuku-kuku`
  why: wrong subject — garlic doesn't "have" fingernails; it's the reincarnated person who gains beautiful nails (see FIX on S3742[0] which properly attributes this).

- **S3799 [2]**  `jenazah | DIISI_DENGAN | kain`
  why: redundant/garbled artifact of [0]'s "kain putih" and [1]'s misattributed subject; adds nothing and restates the wrong-subject error.

## ADD  (missing triples the sentence supports)

- **S3294**  `jenazah | HARUS_MELALUI | ujung pepaga/asagan yang di teben (barat)` (+) `jenazah | DIMASUKKAN | kepala terlebih dahulu` (+) `kaki jenazah | BERSELONJOR_KE | teben/barat`
  why: sentence is packed with placement-orientation detail (must enter from the teben/west end, body rotated, head first, feet stretched toward teben/west) that's entirely missing from the single terse DILETAKKAN_DI triple.

- **S3295**  `jenazah | BERGERAK_DARI | teben` (+) `jenazah | MENUJU | luanan (hulu)`
  why: splits out the garbled "bale teben" object into the two real facts (direction of travel), supplementing the FIX above.

- **S3296**  `keluarga/masyarakat | DILARANG | tergesa-gesa memandikan jenazah`
  why: this behavioral norm (don't rush to bathe the corpse right after placement) is the sentence's actual point and is entirely unextracted.

- **S3330**  `bale-bale (tempat memandikan mayat) | DIKENAL_SEBAGAI | pepaga` (+) `bale-bale | DIKENAL_SEBAGAI | asagan`
  why: "yang disebut pepaga atau asagan" — both alias names for the bathing platform are dropped entirely.

- **S3332**  `pepaga | DIKENAL_SEBAGAI | bale penusangan (istilah Denpasar)` (+) `pepaga/asagan | ADALAH | semacam dipan atau bale darurat` (+) `pepaga/asagan | DIPERGUNAKAN_SEBAGAI | usungan` (+) `pepaga/asagan | DIPERGUNAKAN_SEBAGAI | tandu`
  why: only the pepaga=asagan equivalence survived; the Denpasar alias, the definitional clause, and the dual-use-as-bier/stretcher facts are all missing (be generous per rubric).

- **S3339**  `jenazah | DIAMBIL_DARI | balai (tempat jenazah disemayamkan)` (+) `tempat persemayaman jenazah | DITEMPATKAN_DI | bale semanggen (rumah adat Bali)`
  why: only the bare "krama MENGAMBIL jenazah" survives; where-from and the traditional-house detail are dropped.

- **S3340**  `tempat penusangan | BERUPA | pepaga atau asagan`
  why: "yang berupa pepaga atau asagan" entirely dropped — this identifies exactly what the bathing spot physically is.

- **S3354**  `jenazah | DIDUDUKKAN_DULU_SEBELUM | tidur tertelentang di pepaga/asagan`
  why: "dengan terlebih dulu duduk dan kemudian baru tidur tertelentang" (first seated, then laid supine) — the actual placement procedure — is missing.

- **S3363**  `kepala jenazah | DIALASI_DENGAN | bantal kapuk (bantal biasa)`
  why: major under-extraction — the sentence's main clause (a pillow is placed under the corpse's head) isn't captured at all; only a restated subordinate clause from an earlier sentence survives.

- **S3364**  `jenazah | HARUS_DIBIARKAN | sebentar (sebelum dibuka pakaiannya)` (+) `orang yang dituakan/lebih tua | MENCUCI | muka dan rambut jenazah`
  why: the entire normative point of the sentence (don't rush to undress it; wait for an elder to wash the face/hair first) is missing.

- **S3468**  `jenazah | DIHIAS_SEOLAH-OLAH | pergi menghadiri undangan atau ke pura`
  why: the framing that the corpse is adorned as if going out (to an event or the temple) — the point of the accessorizing — is dropped. (Note: N10 check — the 3-item list cincin/kalung/gelang is fully captured, holding well.)

- **S3547**  `tirtha | BERASAL_DARI | bhetara hyang guru` (+) `tirtha | DIMOHONKAN_DI | sanggah/pamerajan keluarga orang yang meninggal`
  why: the long literal object is unwieldy and buries two separable facts (origin of the holy water; where it's requested) that would be cleaner as their own triples. Also recovers the dropped "diperciki" action (only "diminumkan" survives; the corpse is both sprinkled AND given the water to drink).

- **S3584**  `pengerikan kuku | TIDAK_BOLEH_DILAKUKAN_SAAT | pabersihan hidup`
  why: the sentence's explicit prohibition is completely missing.

- **S3604 / S3973**  `jempol jari tangan (kedua ibu jari) | DIIKAT_DENGAN | tali benang tukelan (benang tenun Bali) berwarna putih` (+) `jempol jari kaki | DIIKAT_DENGAN | tali benang tukelan` (S3604 only, which also covers the feet)
  why: the sentence's actual content — thumbs (and, in S3604, toes) tied together with white handspun thread — is never captured; both sentences only produce the nonsense "itik-itik SETELAH kuku tangan/kaki" (see NOTE on N7 below).

- **S3610**  `jenazah | DIBILAS_DENGAN | air` (+) `jenazah | DIKERINGKAN_DENGAN | kain kering`
  why: the rinse-and-dry steps after washing with umbi sikapa/sekapa are dropped.

- **S3651**  `dewa wishnu | MENDAPATKAN | tirtha amertha` (+) `dewa wishnu | TIDUR_DI | atas samudra (dialasi dan dipayungi naga/ular cobra berkepala banyak)`
  why: this Samudra Manthana myth digression (churning the ocean of milk, obtaining the nectar of immortality, sleeping on a many-headed cobra) is entirely reduced to a vacuous LAINNYA triple.

- **S3653**  fix object of [0] to add `untuk tidur` — object currently just "bantal" instead of "bantal untuk tidur" (pillow for sleeping); minor N1-style truncation, noted here rather than as a full FIX bullet since predicate/subject are otherwise fine.

- **S3654**  see FIX bullets above.

- **S3656**  `gegaleng | DIKENAL_SEBAGAI | galeng pengerekan`
  why: "sehingga gegaleng ini juga disebut dengan 'galeng pengerekan'" — this alias is entirely missing.

- **S3720**  `anget-angetan | BERMAKNA | agar orang yang meninggal dapat numitis lagi dan terhindar dari penyakit` (+) `anget-angetan | BERMAKNA | agar orang tersebut memiliki budi pekerti dan pikiran baik, jernih, terlepas dari kebusukan`
  why: the sentence's rich symbolic-purpose content (reincarnation, disease-avoidance, good character) is reduced to the bare physical fact "menghilangkan bau busuk."

- **S3734**  `kojong (kawangen jeriji) | BERISI | lima gulungan daun sirih (base)` (+) `gulungan daun sirih | DIIKAT_DENGAN | benang putih` (+) `gulungan sirih | DIMASUKKAN_KE | lubang uang kepeng`
  why: only the "ADALAH kojong / TERBUAT_DARI daun pisang" shell survives; the entire construction detail (contents, binding, insertion into a coin) is missing.

- **S3756–S3758**  `logam campuran | BERADA_DI | tengah-tengah`
  why: the panca-datu correspondence table (metal→color→direction→deity) captures BERWARNA/BERADA_DI/BERDEWA for perak, tembaga, emas, and besi, but the fifth element (logam campuran) is missing its BERADA_DI (tempatnya di tengah-tengah) — an asymmetric gap in an otherwise clean manual_override set.

- **S3760**  `jarum (jaum) | DITARUH_DI | lengan jenazah` (+) `besi paku | DITARUH_DI | lengan jenazah`
  why: major under-extraction — the sentence's entire point (a needle and iron nail placed on the corpse's arm before wrapping) produces zero triples; only an unrelated "jenazah SEBELUM pangringkesan" survives from a subordinate clause.

- **S3783**  `priuk (tempat tirtha pangringkes) | DIPECAHKAN | [setelah tirtha dipercikkan]` (+) `priuk (yang pecah) | DIBUANG_DI | kolong bawah pepaga/asagan`
  why: the ritual vessel-breaking-and-discarding step is entirely missing.

- **S3791**  `jenazah (setelah dibungkus tiga lapis) | DIIKAT_DENGAN | tali benang tukelan`
  why: the tying-with-thread step after the three-layer wrap is dropped.

- **S3800**  `hiasan (rurub sinom) | DIJAHIT_DENGAN | daun kelapa muda (busung)`
  why: "dijarit bersama daun kelapa muda (busung)" is missing; also note blangsah's "yang belum mekar" (not-yet-bloomed) qualifier is lost — minor nuance loss.

- **S3812**  `rurub sinom | DILETAKKAN_DI | posisi kepala, leher, perut, paha, dan kaki (melintang), sama seperti penempatan sebelumnya di atas jenazah`
  why: the detailed positional description is reduced to a bare "DILETAKKAN_DI peti."

## NOTE  (borderline / systemic observation, no single fix)

- **N1 — copula/generic-noun defining-clause truncation — verdict: PARTIAL, not consistently holding.** The specific "berfungsi sebagai X" parataxis sub-case is genuinely fixed and clean at **S3647** (`daun pisang saba BERFUNGSI_SEBAGAI tikar` correctly split via object_decomposition). But the plain "ADALAH/BERMAKNA/BERARTI + generic noun + yang/yaitu/agar continuation" shape is still broken across many sentences in this chunk: **S3155[0,1], S3446, S3544, S3586 (the exact sentence flagged in Iteration 1 — still broken), S3589, S3591, S3653, S3656, S3720, S3728, S3742**. This looks like a narrow fix (parataxis clauses only) rather than a general fix for copula-defining-clause truncation.

- **N10 — coordinate list capture — verdict: HOLDING well in this chunk.** S3196's 15-item `TERDIRI_DARI` list (sasap...coblong) is captured completely (15/15), and S3468's 3-item `MEMAKAI` list (cincin/kalung/gelang) is captured completely (3/3). No truncated coordinate lists found in chunk 7.

- **S13 — attribution/citation-adjunct suppression — verdict: HOLDING, no leak found.** Checked candidate citation contexts (e.g. S3651's "kitab purana yang menceriterakan..." mythological source) — none of these citation/source phrases leaked through as relation objects in this chunk.

- **N4 — kawangen placement + contents split — verdict: STILL OPEN, confirmed exactly as flagged.** S3747, S3749, S3753 all still mis-type as `DIISI_DENGAN <body-part>` and drop the contents (uang kepeng count + flower type) entirely, exactly as described in Iteration 1. A related-but-distinct subject-fusion bug in the same passage appears at S3546 (a TAHAPAN_UPACARA phrase wrongly fused with a body-part noun into one subject).

- **N7 — section-heading noun captured as subject of following clause — verdict: STILL PRESENT for the classic shape, but inconsistent.** Confirmed still broken at **S3604** (`itik-itik SETELAH kesepuluh kuku tangan/kuku kaki` — the heading noun grabs an unrelated clause's temporal adjunct as if it were a relation object) and **S3733** (`kwangen jeriji SETELAH pelaksanaan eteh-eteh pabersihan mati` — same bug, plus a separate self-loop nonsense triple `kwangen jeriji DITARUH kawangen jeriji`, see DROP). By contrast, **S3237** and **S3653** show a related-but-different flaw (wrong direction / truncation rather than grabbing an unrelated clause), and **S3760** doesn't show the classic junk-entity bug at all — instead the heading is silently ignored and the sentence's real content (needle/nail on the arm) is simply never extracted. Net: the heading-noun bug is not resolved, though its exact manifestation varies by sentence.

- **N11** — not applicable to this chunk (the Panca Maha Bhuta closing-verse sentences S4300–S4305 are in chunk 8).

## Chunk stats
FIX: 36   DROP: 4   ADD: 30   sentences reviewed: 61

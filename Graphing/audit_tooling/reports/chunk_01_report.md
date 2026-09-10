# Chunk 1 audit (S4..S559)

## FIX  (triple is salvageable — give the corrected triple)

- **S4 [0]**  current: `ngaben | MELAMBANGKAN | siklus kehidupan`
  fix: `ngaben | MELAMBANGKAN | siklus kehidupan dan kematian`
  why: "siklus kehidupan **dan kematian**" (cycle of life **and death**) — the second conjunct is dropped, a 2-item coordinate loss identical in spirit to the flagged sasih cases.

- **S12 [0]**  current: `ngaben | MEMILIKI | sudut pandang pemaknaan`
  fix: `ngaben | MEMILIKI | beberapa sudut pandang pemaknaan`
  why: drops "beberapa" (several) — same "beberapa jenis" nuance-loss pattern as flag.txt S801.

- **S26 [0]**  current: `apah | MELAMBANGKAN | unsur cair`
  fix: `apah | MELAMBANGKAN | unsur cair dalam tubuh`
  why: drops "dalam tubuh" (in the body); inconsistent with the sibling sentence S29 (akasa), which keeps the equivalent "tubuh" qualifier.

- **S32 [0]**  current: `ngaben | MEMILIKI | peran ganda`
  fix: `ngaben | MEMILIKI | peran ganda yang saling menguatkan`
  why: **N1 gap** — MEMILIKI + generic noun "peran ganda" (dual role) drops its defining "yang saling menguatkan" (that mutually reinforce) relative clause. N1 holds for ADALAH+yang but not for MEMILIKI+yang here.

- **S44 [0]**  current: `sawa wedana | ADALAH | upacara jenazah utuh untuk jenazah utuh (3-7 hari setelah meninggal)`
  fix: `sawa wedana | ADALAH | upacara untuk jenazah utuh (3-7 hari setelah meninggal)`
  why: "jenazah utuh" is duplicated verbatim in the object string — an extraction bug (same duplication pattern recurs at chunk-2 S785).

- **S48 [0]**  current: `ngaben massal | ADALAH | pelaksanaan kolektif`
  fix: `ngaben massal | ADALAH | pelaksanaan kolektif oleh warga desa untuk efisiensi biaya dan tenaga tanpa mengurangi nilai sakralitasnya`
  why: **N1 gap** — the purpose-oblique ("untuk efisiensi biaya dan tenaga") and agent-oblique ("oleh warga desa") children of the generic noun "pelaksanaan kolektif" are entirely dropped, despite N1's widened rule explicitly naming purpose-oblique children as something to retain.

- **S58 [3]**  current: `nganyut | MELAMBANGKAN | simbol pelepasan terakhir`
  fix: `nganyut | MELAMBANGKAN | simbol pelepasan terakhir menuju moksha`
  why: drops "menuju moksha" (toward moksha/liberation), the destination that gives the symbol its meaning.

- **S61 [0]**  current: `mapegat | MEMILIKI | makna krusial`
  fix: `mapegat | MEMILIKI | makna krusial untuk memutus ikatan emosional dan duniawi antara mendiang (niskala) dengan keluarga (skala)`
  why: **N1 gap** — MEMILIKI + "makna krusial" drops its entire purpose-xcomp ("untuk memutus ikatan...") even though purpose-oblique/xcomp retention is explicitly part of the widened N1 spec.

- **S77 [0]**  current: `naga banda | MEMILIKI | panjang 1.600 depa`
  fix: `naga banda | MEMILIKI | panjang 1.600 depa (sekitar 2,4 km)`
  why: drops the clarifying metric conversion "(sekitar 2,4 km)".

- **S92 [0]**  current: `kanoroyang sanksi terberat | BERUPA | pemberhentian keanggotaan desa adat`
  fix: `kanoroyang | ADALAH | sanksi terberat berupa pemberhentian keanggotaan desa adat`
  why: subject wrongly merges "kanoroyang" with its own predicate noun "sanksi terberat"; cleaner to keep "kanoroyang" as subject with the descriptive complement intact as object (matches N1 pattern for BERUPA-clauses).

- **S104 [0]**  current: `bali aga vs bali dataran | MEMPEROLEH | perbedaan mendasar`
  fix: DROP this triple (see DROP list) and replace with two ADD triples (see ADD list)
  why: "MEMPEROLEH" (obtained) does not fit the source verb "terdapat" (there exists/there is); the heading-style subject "bali aga vs bali dataran" is not a real acting entity. Wrong relation label (failure mode 5) + wrong subject (failure mode 1).

- **S124 [0]**  current: `bali dataran | MENGGUNAKAN | sarana mewah`
  fix: `bali dataran | MENGGUNAKAN | sarana mewah (bade/petulangan) pengaruh majapahit`
  why: drops "pengaruh majapahit" (Majapahit-influenced), the qualifier explaining why these tools are "mewah" (luxurious).

- **S126 [0]**  current: `ngaben | ADALAH | institusi sosial-religius`
  fix: `ngaben | ADALAH | institusi sosial-religius yang kompleks`
  why: drops "yang kompleks" (that is complex). See ADD list for the much bigger companion miss (the "berfungsi sebagai..." parataxis clause).

- **S128 [0]**  current: `ngaben | ADALAH | identitas budaya dinamis`
  fix: `ngaben | ADALAH | identitas budaya dinamis yang terus menjaga harmoni antara manusia, alam, dan sang pencipta`
  why: **N1 gap** — drops the entire "yang terus menjaga harmoni..." relative clause, which itself contains a 3-item list (manusia, alam, dan sang pencipta) we can't yet test for N10 because the clause never survives extraction at all.

- **S191 [0]**  current: `jenazah | DIKUBUR_DENGAN | kehendak lain`
  fix: `jenazah | DIKUBUR_SEMENTARA_KARENA | keterbatasan dana (keputusan keluarga)`
  why: "kehendak lain" (other will/wish) alone is nonsense as something one is "buried with"; the real content is that the corpse is buried *temporarily* due to a family decision driven by limited funds. Flag.txt asked whether to drop this one — recommend FIX instead, it's salvageable.

- **S219 [0]**  current: `sekar ura | MELAMBANGKAN | simbol perpisahan`
  fix: `sekar ura | MELAMBANGKAN | simbol perpisahan antara yang meninggal dengan keluarga yang ditinggal`
  why: adds back the "antara..." qualifier that gives the symbol its meaning (who is separating from whom); the outer "dengan harapan..." tail can reasonably stay dropped (too deep to be useful).

- **S246 [0]**  current: `puspa lingga | DIAMBIL | keampigan`
  fix: `puspa lingga | DIBUKA_MENJADI | keampigan`
  why: source verb is "dibuka" (opened/uncovered), not "diambil" (taken) — wrong relation label.

- **S254 [0]**  current: `kuburan | DIAMBIL | tulang belulang`
  fix: `tulang belulang | DIAMBIL_DARI | kuburan`
  why: wrong direction — the bones are taken *from* the grave, the grave does not "take" the bones (failure mode 1/2).

- **S258 [2]**  current: `tegteg | DISERTAI | memohon`
  fix: `tegteg | DISERTAI | permohonan atma yang akan diaben`
  why: object is a bare verb stem "memohon" (to request) with no content — nonsense triple (failure mode 3, same class as "banten ADALAH menjadi"); the real request-object is "atma yang akan diaben" (the soul to be cremated).

- **S271 [4]**  current: `atiwa-tiwa | ADALAH | sama atiwa-tiwa asti vedana`
  fix: `tata pelaksanaan atiwa-tiwa (ngaben) svasta | SAMA_DENGAN | atiwa-tiwa asti vedana`
  why: object squashes "sama dengan" (same as) into the noun phrase, and the real subject of the comparison is "tata pelaksanaannya" (its procedure), not bare "atiwa-tiwa" — wrong subject + malformed object.

- **S283 [0]**  current: `banten | DIKENAL_SEBAGAI | kala puspa`
  fix: `banten yang menjadi simbol orang yang meninggal | DIKENAL_SEBAGAI | kala puspa`
  why: matches flag.txt's 283c point — only the specific offering that "menjadi simbol orang yang meninggal" (becomes a symbol of the deceased) is called kala puspa, not "banten" in general; the defining clause should be on the subject.

- **S332 [0]**  current: `jenazah | DILETAKKAN_DI | balai posisi kepala berhulu utara`
  fix: `jenazah | DILETAKKAN_DI | balai dengan posisi kepala berhulu utara atau timur`
  why: drops the "atau timur" (or east) disjunct — a missing coordinate member (2-item list, only first kept).

- **S366 [0]**  current: `jenazah | MENUJU | utara`
  fix: `jenazah | MEMBUJUR_KE | utara atau timur`
  why: matches flag.txt exactly (still unfixed) — "membujur" means the corpse lies oriented/stretched toward a direction (static posture), not "menuju" (heading toward, implying motion); also restores the dropped "atau timur" disjunct.

- **S370 [2]**  current: `jenazah | DIPASANG | itik-itik`
  fix: `itik-itik | DIPASANG_PADA | ibu jari tangan dan kaki jenazah`
  why: matches flag.txt 370c — it's the itik-itik that get affixed to the thumb/big toe, not a generic "jenazah gets itik-itik" action; the location "pada ibu jari tangan dan kaki" is the essential part currently lost.

- **S399**  current (all of [0]-[2]): `sasih | ADALAH | kasa / karo / katiga`
  fix: `sasih yang baik untuk pitra yadnya (khususnya ngaben) | ADALAH | kasa, karo, dan katiga`
  why: matches flag.txt exactly, still unfixed — subject "sasih" needs the "yang baik..." qualifier (which months, specifically the *good* ones). Note: the 3-item coordinate object list itself (kasa/karo/katiga) IS fully preserved — good N10 evidence — only the subject-side qualifier is still missing.

- **S540 [0]**  current: `banten | DIPERSEMBAHKAN_KEPADA | sakabuatan`
  fix: `banten saji | BERJENIS | sakabuatan`
  why: "sakabuatan" (a complete/full set) describes the offering's composition, not a recipient — "dipersembahkan kepada" (offered to) implies a recipient deity/person, which doesn't fit here. Wrong relation label.

- **S559 [0]**  current: `sorohan banten | LAINNYA | ajeng sulinggih`
  fix: `sorohan banten | DIPERSEMBAHKAN_DI_HADAPAN | sulinggih`
  why: matches flag.txt exactly, still unfixed — "ring ajeng sulinggih" = "in front of/in the presence of the high priest (sulinggih)"; generic LAINNYA should be resolved to an "offered before/at" relation as flag.txt requests.

## DROP  (triple should be removed)

- **S104 [0]**  `bali aga vs bali dataran | MEMPEROLEH | perbedaan mendasar`
  why: nonsensical heading-triple; "terdapat" (there exists) isn't an "acquire" relation, and "bali aga vs bali dataran" isn't a real acting subject. Replaced by two ADD triples below.

- **S224 [0]**  `usungan | MEMILIKI | upacara pembasmian`
  why: reaffirming flag.txt's verdict (still unfixed) — the bier (usungan) does not "own" the cremation ceremony; the ceremony is held *after* the bier is set down.

- **S283 [1]**  `banten | DIKENAL_SEBAGAI | lontar`
  why: **S13 gap** — "lontar" here refers to the *source text* ("sebagaimana juga disebutkan dalam lontar yama purva tattwa" = as also stated in the lontar Yama Purva Tattwa), a citation adjunct, not an alias of banten. This is precisely the pattern the widened S13 rule is meant to suppress, and it still leaked through.

- **S370 [3]**  `jenazah | DILETAKKAN_DI | ibu jari tangan`
  why: nonsensical — "ibu jari tangan dan kaki" is where the itik-itik are placed (see fix above), not a location the corpse itself is placed at; parser misattached the "pada ibu jari..." phrase to the wrong verb.

- **S541 [0]**  `banten panjang ilang | LAINNYA | rateng`
  why: reaffirming flag.txt's verdict (still unfixed) — segmentation-mangled fragment; "mentah" is wrongly tagged as the root VERB when the sentence is actually a flat list of banten types (panjang, ilang, mentah, rateng).

## ADD  (missing triples the sentence supports)

- **S44**  `formalin | DIGUNAKAN_UNTUK | memperlambat pembusukan jenazah selama masa persiapan`
  why: the sentence's second half (modern formalin use to slow decomposition) is entirely unextracted.

- **S46**  `swasta | MENGGUNAKAN | kayu cendana dan aksara sakral`  (+ `kayu cendana dan aksara sakral | MELAMBANGKAN | pengganti jasad`)
  why: finer-grained extraction of the means/symbol described in the retained ADALAH clause — good opportunity for more granular triples now that N1 keeps the whole clause.

- **S69**  `gedarba | DIGUNAKAN_OLEH | wangsa sudra jadma (masyarakat umum)`
  why: matches flag.txt 69b exactly — the parataxis clause "digunakan oleh wangsa sudra jadma" is completely absent from extraction, even though N1's widened rule explicitly says parataxis like this should be retained. Concrete N1 gap.

- **S81**  `perbandingan kepala lembu | ADALAH | 2:1:1`
  why: matches flag.txt exactly, still missing — only the "singa" ratio was ever extracted, the "kepala lembu" ratio (2:1:1) is dropped entirely.

- **S104**  `masyarakat bali aga (pegunungan) | MEMPERTAHANKAN | tradisi asli kuno`  (+ `masyarakat bali dataran | MENDAPAT_PENGARUH_DARI | tradisi hindu-majapahit`)
  why: replaces the nonsensical DROP'd heading triple with the two real comparative facts the sentence actually asserts.

- **S124**  `bali aga | MENONJOLKAN | tradisi asli (yang terkadang tidak menggunakan pembakaran fisik secara masif)`
  why: the entire second half of the sentence (the Bali Aga contrast) is unextracted.

- **S126**  `ngaben | BERFUNGSI_SEBAGAI | mekanisme spiritual pemurnian jiwa sekaligus perekat kohesi sosial`
  why: **major N1 gap** — this is the exact "berfungsi sebagai..." parataxis shape the widened N1 rule names explicitly, and it is completely absent from extraction (0 triples for this clause), not just truncated.

- **S215**  `layon | DILETAKKAN_DI | bale gede`  (+ `layon | DILETAKKAN_DI | saka roras`)
  why: matches flag.txt ("could be more extraction") — the whole "diletakkan di bale gede/saka roras atau tempat..." parataxis clause is unextracted; a 3-way location list (bale gede, saka roras, tempat yang diperuntukkan) is entirely missing.

- **S217**  `pelebon | DIAWALI_DENGAN | upacara ngaskara`  (+ `pelebon | DIAWALI_DENGAN | caru pengelambuk`, + `jenazah | BERANGKAT_KE | setra`)
  why: matches flag.txt ("could be more extraction") — pelebon itself, its two opening rites, and the final departure to the cemetery are all unextracted; only the "dinaikkan ke usungan" step survived.

- **S246**  `ngerorasin | DILAKSANAKAN_DI | pura dalem`
  why: exactly flag.txt's suggested triple — still missing.

- **S265**  `tegteg | DITEMPATKAN_DI | tumpang salu`
  why: the sentence's final clause ("selanjutnya tegteg ditempatkan di tumpang salu") is dropped.

- **S270**  `ngaben svasta | DILAKUKAN_JIKA | jenazah tidak ditemukan`  (+ `... | jenazah telah lama terkubur/terpendam`, + `... | lokasi jenazah terlalu jauh dari jangkauan`)
  why: matches flag.txt ("could be another extraction specifying what ngaben svasta is") — the three disjunctive conditions defining when this rite applies are entirely unextracted.

- **S271**  `tata pelaksanaan atiwa-tiwa svasta | MELIPUTI | matur piuning, pembakaran, hingga nganyut, dan ngelinggihang dewa hyang`
  why: the procedural sequence ("mulai dari matur piuning ke pura dalem, pembakaran, hingga nganyut, dan dilanjutkan...") is entirely unextracted.

- **S338**  `soda | BERUPA | nasi, minum, buah-buahan, jajan, dan lainnya`
  why: **major N10 test case, currently a total miss** — the 5-item conjunct list ("berupa nasi, minum, buah-buahan, jajan, dan lainnya") attached via xcomp to "disuguhi" is not extracted at all (0 triples), separate from the [0] DILENGKAPI canang sari relation that does exist. Matches flag.txt exactly.

- **S344**  itemize `eteh-eteh sawa | BERUPA | <item>` for each of: kamben, tapih, sabuk, udeng, pangulungan, angkeb rai, angkeb baga/purus, leluwur, tatindih, kain kuning untuk saput atau selendang, rantasan kain putih kuning dan kain anyar, samsam, bunga, kwangen  (+ `eteh-eteh sawa | DIMOHONKAN_DARI | sulinggih/griya`)
  why: **the single biggest N10 finding in this chunk** — matches flag.txt exactly ("there should be a lot of extraction... so many tools"). Currently the ~14-item semicolon/comma-segmented list is dumped verbatim as ONE giant literal string across 2 relations instead of being split into per-item triples; the conjunct-walk clearly does not operate on this shape.

- **S354**  `pepaga | TERBUAT_DARI (hitungan) | wangke`  (+ `... | wangkong`, `... | galar`, `... | galir`, `... | galur`)
  why: **major N10 test case, confirmed truncation** — "dengan hitungan: likah, wangke, wangkong, dan galar, galir, galur" is a 6-item conjunct chain; only "likah" (merged into "hitungan likah") survived, the other 5 are dropped. Matches flag.txt ("there should be more components here") exactly.

- **S358**  `leluwur | BERUPA | kain putih`
  why: exactly the triple flag.txt asked for — still missing; "berupa kain putih" (in the form of white cloth) is an unsplit xcomp on "dipasang leluwur".

- **S364**  `nanginin | ADALAH | upacara membangunkan almarhum seperti membangunkan orang yang sedang tidur`  (+ `nanginin | DISERTAI | kekidungan yang berhubungan dengan kidung pitra yadnya`)
  why: the entire definitional content of the nanginin rite (waking ritual + accompanying chant) is unextracted; only the preceding "dibawa ke tempat pemandian" survived.

- **S370**  `jenazah | DITEMPATKAN_DI | bale gede/sakaroras atau tempat yang disiapkan`  (+ `jenazah | DIPOSISIKAN_KEPALA_KE | utara atau timur`)
  why: the sentence's final clause (final resting placement + head orientation) is unextracted.

- **S376**  `jenazah | DIBASMI_OLEH | sang hyang birawi`
  why: matches flag.txt's ask (mislabeled S370 in flag.txt, but the "dibasmi ... sang hyang Birawi" content actually lives in S376) — "dibasmi oleh sang hyang birawi" (cremated by Sang Hyang Birawi) is dropped entirely; only "dibawa ke setra" survived.

- **S400**  `sasih kapitu | DIKENAL_SEBAGAI | dewasa madya`
  why: "sasih kaenem **dan kapitu** disebut dewasa madya" — a 2-item coordinate subject, only "kaenem" kept, "kapitu" dropped.

- **S411**  `wuku kuningan | BERADA_DI | sasih kapitu`
  why: matches flag.txt exactly — STILL unfixed. "sasih kasa **dan kapitu**" — only "kasa" extracted.

- **S413**  `uye | BERADA_DI | sasih kasanga`
  why: matches flag.txt exactly — STILL unfixed. "sasih katiga **dan kasanga**" — only "katiga" extracted.

- **S414**  `wayang | BERADA_DI | sasih kadasa`
  why: matches flag.txt exactly — STILL unfixed. "sasih kapat **dan kadasa**" — only "kapat" extracted.

## NOTE  (borderline / systemic observation, no single fix)

- **N1 regression check — PARTIAL.** Holds well for the simple "X ADALAH/BERPERAN_SEBAGAI generic-noun **yang**-clause" shape: S6, S45, S73 (via object_decomposition), S213 (previously flagged as too terse — now fully resolved, full clause retained), S415 (previously flagged as too terse — now resolved, even the trailing parataxis "disebut juga malamasa" is kept), and S4[1]. **Gaps found**: MEMILIKI+yang-clause dropped (S32), MEMILIKI+purpose-xcomp dropped (S61), ADALAH+purpose/agent-oblique dropped (S48), and — most importantly — bare parataxis clauses ("berfungsi sebagai...", S126; "digunakan oleh...", S69) are dropped **entirely** rather than truncated, even though the widened rule explicitly names both of these shapes. Verdict: holds for plain ADALAH+yang, does not yet hold for MEMILIKI-headed nouns or for parataxis continuations.

- **N10 regression check — PARTIAL/MIXED.** Holds for flat "A, B, dan/serta C(+)" conjunct chains directly governing one relation's object: S27/S28 (2-item), S219 (4-item mixed dan/serta), S399 (3-item kasa/karo/katiga — all three kept). **Fails** for: colon-introduced enumerations (S354, 6-item list, 5/6 dropped), semicolon-segmented appositive-heavy dumps (S344, ~14 items dumped as one literal blob instead of split — the single biggest miss in the chunk), and plain 2-item "X dan Y" objects/subjects in non-BERUPA relations (S4 kehidupan/kematian, S332 utara/timur, S400 kaenem/kapitu subject, and — most damning — **all three** of the flag.txt-flagged S411/S413/S414 sasih pairs remain truncated to a single item). The walk appears to work only for a narrow set of relation-generation paths, not universally.

- **S13 regression check — NOT HOLDING.** S283[1] "banten DIKENAL_SEBAGAI lontar" leaks the citation adjunct "sebagaimana juga disebutkan dalam lontar yama purva tattwa" through as a relation object, exactly the pattern the widened rule targets.

- **N6 regression check — NO TEST CASE.** No "X termasuk Y" membership construction occurs anywhere in chunk 1 (zero occurrences of "termasuk"); cannot evaluate from this chunk (see chunk 2 report for the one relevant occurrence found in the corpus).

- **S58 [1]/[2]** — flag.txt 58b/58c ("nganyut" should not be the subject of DIHANYUTKAN_KE, subject should be "abu") remains unaddressed as of this iteration. Same bug class recurs at chunk-2 S1187 (see that report) — this looks like a systemic, unfixed pattern, not an isolated case.

- **S540 vs S591 (cross-chunk duplicate text)** — "banten saji sakabuatan." appears verbatim at S540 (this chunk, recommended FIX above) and at S591 (chunk 2, flag.txt says DROP). Recommend the team pick one consistent verdict for this boilerplate sentence wherever it recurs in the corpus.

- **Duplication bug** — S44's object string repeats "jenazah utuh" verbatim; the identical duplication pattern recurs at chunk-2 S785 ("istilah umat hindu bagi umat hindu"). Looks like a systemic bug in object-string reconstruction when a noun is referenced twice (once as compound head, once inside a "bagi/untuk X" phrase).

## Chunk stats
FIX: 27   DROP: 5   ADD: 26   sentences reviewed: 61

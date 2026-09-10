# Chunk 3 audit (S1188..S1597)

## FIX  (triple is salvageable — give the corrected triple)

- **S1197 [1]**  current: `jun pere | BERISI | gambar`
  fix: `jun pere | BERISI | gambar yang khas`
  why: "khas" (distinctive) qualifies gambar/aksara; dropping it loses the point of the sentence (the writing/pictures are distinctive).

- **S1219 [0]**  current: `sawa | DIBAKAR | alat pangringkesan`
  fix: `sawa | DISERTAI | alat pangringkesan` (and add `sawa | DITANAM | alat pangringkesan` since ditanam/dibakar are coordinate alternatives)
  why: "beserta" = "together with" — the corpse isn't burning the wrapping tools, they're cremated/buried *along with* it. DIBAKAR misrepresents an oblique-of-accompaniment as a direct action on the object.

- **S1226 [0]**  current: `sawa | DINILAI_DI | mata umat hindu`
  fix: `sawa | DINILAI | sesuatu yang leteh atau tidak suci`
  why: "di mata umat hindu" ("in the eyes of Hindu people") is an attribution adjunct (whose judgment this is), not the object of the verdict — this is exactly the S13 pattern the instructions name explicitly. The real predicate nominal ("something leteh/impure") was dropped entirely. See S13 regression note below — this is a leak-through.

- **S1253 [0]**  current: `ngaben bahasa alus-singgih | ADALAH | malebuang`
  fix: `ngaben | ADALAH | malebuang`
  why: "dalam bahasa alus-singgihnya" ("in its polite/high register") is an adjunct describing the register of the *name*, not part of the subject entity. Padding it into the subject creates a garbled compound.

- **S1253 [1]**  current: `ngaben bahasa alus-singgih | ADALAH | atiwa-tiwa`
  fix: `ngaben | ADALAH | atiwa-tiwa`
  why: same subject-padding bug as [0].

- **S1261 [0]**  current: `ngaben | ADALAH | satu yadnya yang paling banyak ragam nya`
  fix: `ngaben | ADALAH | salah satu yadnya yang paling banyak ragamnya`
  why: "salah" ("one of many") got dropped, losing the "one among many" nuance (flag.txt-style lost-nuance issue). N1 clause-retention itself is holding here (the `yang paling banyak ragamnya` relative clause survived) — only the "salah" quantifier was clipped.

- **S1290 [0]**  current: `yadnya | BERPERAN_SEBAGAI | beban`
  fix: `yadnya | BERPERAN_SEBAGAI | beban bagi pemikulnya`
  why: "bagi pemikulnya" ("for the one who bears it") is the whole point — a burden is only meaningful relative to who carries it.

- **S1308 [0]**  current: `tirtha | MEMILIKI | tarif bak barang dagangan`
  fix: `tirtha | MEMILIKI | tarif bak barang dagangan di pasar swalayan`
  why: "di pasar swalayan" (in a supermarket) is dropped from the object though it's the whole simile being drawn (tirtha priced like supermarket goods).

- **S1328 [0]**  current: `besar kecil punia | DILAKUKAN_DENGAN | upacara`
  fix: `besar kecil punia atau honorarium | DISINKRONKAN_DENGAN | jenis upacara tersebut`
  why: "disinkronkan dengan" = "synchronized with," not "dilakukan dengan" (done with) — wrong relation label. Subject also drops the "atau honorarium" alternative name, and object drops "jenis ... tersebut."

- **S1335 [0]**  current: `tirtha | MEMILIKI | nilai spiritual`
  fix: `tirtha | MEMILIKI | nilai spiritual yang sama`
  why: "yang sama" (the same, regardless of price) carries the rhetorical point of the passage (cf. S1308's price framing) — dropped.

- **S1361 [0]-[4]**  current: `yadnya | BERDASARKAN | penuh sredaning citta / penuh kesanggupan / kesungguhan / kemulusan / keikhlasan hati`
  fix: relabel all five to `yadnya | DIDUKUNG_DENGAN | ...` (same objects)
  why: "hendaklah didukung dengan" = "should be supported/carried out with," not "based on." Wrong relation label across the board. (Positive note: this is a genuine 5-way coordinate chain and **all five members were correctly captured** — N10 holding strongly here, see regression note.)

- **S1378 [0]**  current: `yama purwana tatwa | ADALAH | lontar`
  fix: `yama purwana tatwa | ADALAH | nama lontar yang memuat satu jenis pengabenan dengan sawa langsung selaku sasarannya`
  why: strips the defining relative clause explaining *what kind* of lontar this is — an N1-pattern gap not on the named check-list but same defect (see N1 regression note).

- **S1422 [0]**  current: `sawa | DIPERCIKKAN_PADA | tirtha`
  fix: `sawa | DISIRATI_DENGAN | berbagai jenis tirtha`
  why: "disirati" = sawa is sprinkled *with* tirtha (tirtha is the instrument); DIPERCIKKAN_PADA reverses the roles (implies sawa is sprinkled onto tirtha). Also restores "berbagai jenis" (various kinds), dropped per the flag.txt #801 pattern.

- **S1429 [0]**  current: `daksina | ADALAH | penegasan`
  fix: `daksina | ADALAH | penegasan secara formal bahwa yadnya sudah selesai (siddhaning yadnya)`
  why: N1 regression — the "bahwa" continuation clause (attached as advcl to the copula root, not as acl to the object noun) was stripped entirely, leaving a vacuous object. Named check-list sentence; **GAP, not holding**. See N1 regression note.

- **S1430 [0]**  current: `beras catur | ADALAH | lambang kekuatan panca dewata`
  fix: `beras catur | ADALAH | lambang kekuatan panca dewata selaku manifestasi hyang widhi yang mengelola alam semesta (bhuwana agung)`
  why: strips the "selaku manifestasi..." clause explaining what panca dewata are — another N1-pattern gap beyond the named list.

- **S1439 [0],[1],[2]**  current: subject `abu tulang kepala` for all three relations (DIGILING / DIGILING_DI / DIMASUKKAN_KE_DALAM)
  fix: subject should be `abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki` (all 7 conjuncts)
  why: **major N10 regression** — the subject NP is a 7-way coordinate list of body parts (kepala, tangan, punggung, dada, bokong, paha, kaki all `conj` of "abu"), and only the first member survived. This shows N10's conjunct-walk fix does not reach subject-side compounds. See N10 regression note.

- **S1452 [0]**  current: `nywasta | DILAKUKAN_OLEH | orang hal sawa`
  fix: `nywasta | DILAKUKAN_OLEH | orang`
  why: "dalam hal sawa tan inulatan atau jenazah..." is a circumstantial clause ("in the case of..."), not part of the agent NP; merging it into the object garbles it (segmentation bleed).

- **S1456 [0]**  current: `nywasta | ADALAH | ngaben`
  fix: `nywasta | ADALAH | ngaben yang sangat sederhana dalam hal sajen dan alat-alat upakaranya`
  why: N1 regression — the `yang sangat sederhana...` relative clause is attached directly (acl:relcl) to the object noun "ngaben" yet was still stripped. Named check-list sentence; **GAP, not holding**.

- **S1461 [0]**  current: `adegan | ADALAH | alat upakara`
  fix: `adegan | ADALAH | alat upakara yang terbuat dari daun rontal, beralaskan bakul kecil atau pangkon (paso kecil agak tinggi dari tanah atau perak)`
  why: another N1-pattern gap — the defining relative clause is dropped, leaving an uninformative generic-noun triple.

- **S1468 [0]**  current: `upakara | DISUCIKAN_DENGAN | sajen hingga dianggap wajar untuk digunakan`
  fix: `upakara | DISUCIKAN_DENGAN | sajen`
  why: "hingga dianggap wajar untuk digunakan" (until deemed fit to use) belongs to the main verb's result clause, not to "sajen" — merging it in creates a garbled object. ([1] `upakara DISUCIKAN_DENGAN tirtha panglukatan` is fine and correctly keeps both members of this 2-item list.)

- **S1474 [0]-[3]**  current: `sesajen | DIPERSEMBAHKAN_KEPADA | diuskamaligi / nasi angkeb / saji / lain-lain`
  fix: relabel to `sesajen | MELIPUTI | diuskamaligi / nasi angkeb / saji / lain-lain` (these are types/examples of sesajen, listed via "antara lain," not recipients)
  why: DIPERSEMBAHKAN_KEPADA (offered to) misreads an enumeration ("antara lain: X, Y, Z") as a recipient list. The real recipient, "mendiang," is missing entirely — see ADD below. (Positive: the 4-item enumeration itself was fully captured — N10-adjacent success.)

- **S1476 [0]**  current: `tirtha | DIPERCIKKAN_PADA | kedua perlambang`
  fix: `berbagai tirtha | DIPERCIKKAN_PADA | kedua perlambang`
  why: "berbagai" (various) dropped from the subject.

- **S1483 [0]**  current: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading yang dikasturi dan disukutunggalkan`
  why: drops the relative clause describing the process (perfumed with kasturi, shaped into sukutunggal) — N1-pattern gap on a non-copula relation.

- **S1493 [0]**  current: `kemampuan sosial ekonomi | JENIS_DARI | manah`
  fix: `kemampuan sosial ekonomi | JENIS_DARI | standar kedudukan seseorang di masyarakat`
  why: N6 check — the member/category **direction is correct** (member as subject, category as object — the swap fix is working), but the category anchor is wrong: "termasuk kemampuan sosial ekonominya" attaches to "standar kedudukan..." (the thing it's a component of), not to "manah" (the sentence's unrelated grammatical subject). See N6 regression note.

- **S1522 [0]**  current: `mendiang | DIKENAL_SEBAGAI | seseorang`
  fix: `mendiang | DIANGGAP_SEBAGAI | seseorang yang masih hidup`
  why: without "yang masih hidup" (who is still alive) the triple is trivially true and meaningless — the whole point is that the deceased is treated *as if still alive*. Relation label also loosely off (dianggap ≠ dikenal).

- **S1523 [0]**  current: `mendiang | LAINNYA | pamitan`
  fix: `mendiang | MELAKUKAN | pamitan`
  why: LAINNYA is a non-descriptive fallback label; "melakumuspa pamitan" is a farewell-homage action. (Positive: [1]-[3] correctly capture all three recipients — hyang prajapati, pura dalem, sedahan setra — a clean 3-way N10 success, see regression note.)

- **S1544 [0]**  current: `sawa | MENYEBARKAN | bau`
  fix: `sawa | MENYEBARKAN | bau yang kurang sedap`
  why: "yang kurang sedap" (unpleasant) is the entire point of the sentence and was dropped.

- **S1552 [0]**  current: `sumpe | BERFUNGSI_SEBAGAI | penguat rekatan`
  fix: `sumpe | BERFUNGSI_SEBAGAI | penguat rekatan antar badan peti dengan tutupnya`
  why: N1 regression — this is exactly the "berfungsi sebagai" pattern named in the fix spec, yet the nmod continuation ("antar badan peti dengan tutupnya" — what is being reinforced) was stripped. **GAP** on a pattern the fix explicitly targets.

- **S1558 [1]**  current: `sawa | DIBUNGKUS_DENGAN | paplengkungan semula`
  fix: `sawa | DIKURUNG_DENGAN | paplengkungan`
  why: "semula" ("as before") is a manner adverb ("sebagaimana semula"), not part of the object noun; also "dikurung" (enclosed/caged) is closer to the source verb than "dibungkus" (wrapped).

- **S1584 [0]**  current: `pitara | MELAMBANGKAN | bayangan diri`
  fix: `pitara | MEWUJUDKAN | bayangan diri dalam air ening`
  why: "mewujudkan" (manifests) is more accurate than "melambangkan" (symbolizes); also restores "dalam air ening" (in the clear water), the medium of the reflection.

## DROP  (triple should be removed)

- **S1452 [1]**  `nywasta | MENURUT | lontar petunjuknya`
  why: **S13 regression** — "menurut lontar X" is precisely the citation/attribution phrase the widened S13 fix is supposed to suppress regardless of relation label, and it still leaked through here as a full triple. Not holding on this instance. See S13 regression note.

- **S1452 [2],[3],[4]**  `nywasta | MENINGGAL | pulau seberang` / `tenggelam` / `musibah lain`
  why: wrong-subject bug (nywasta is the *name of the ritual*, not a person who can "meninggal" — the real subject is the missing/unrecoverable deceased) compounded with nonsense objects ("tenggelam" is a bare verb stem used as an object). Same class of bug as flag.txt's #58b nganyut case. Replace with a single clean triple, see ADD.

- **S1477 [1]**  `tirtha pangentas | ADALAH | daun alang-alang`
  why: "daun alang-alang" is one example item from the parenthetical list of "isinya" (its contents: daun alang-alang, walantaga, kekitir, pripih), mis-attached as if it were an alias/definition of "tirtha pangentas" itself — classic appositive-misattribution (flag.txt #283-style). The sentence's real predicate ("dipersatukan dengan isi pengawak") was never extracted at all — see ADD.

- **S1522 [1]**  `mendiang | DIKENAL_SEBAGAI | situasi`
  why: "situasi" comes from the oblique adjunct "dalam situasi itu" (in that situation), not a predicate nominal — nonsense triple (object is a stray adjunct-head, not a real category the deceased is "known as").

## ADD  (missing triples the sentence supports)

- **S1188**  `upacara ini | MEMPERGUNAKAN | tirtha panglukatan` (+ `upacara ini | MEMPERGUNAKAN | pabersihan`)
  why: the sentence's actual main clause ("upacara ini juga mempergunakan tirtha, ... tirtha panglukatan dan pabersihan selaku sarana penyucian") was never extracted; only the subordinate "agar sawa boleh menerima..." clause was. Existing [0]/[1] (sawa MEMPEROLEH sesaji/tirtha lainnya) are fine as-is.

- **S1213**  `ayaban | DILAKUKAN_DI | rumah`
  why: main clause "ada daerah yang membiasakan ayaban itu dilakukan di rumah" was skipped in favor of only the "ada pula setelah sawa berada di kuburan" branch.

- **S1215**  `sawa | DILETAKKAN_DI | para-para tempat pembakarannya`
  why: sentence gives two alternative resting places joined by "atau" (lubang tempat penguburan / para-para tempat pembakaran); only the first survived (the "atau" coordination was parsed as nmod rather than conj, so the standard conjunct-walk missed it).

- **S1238**  `keluarga (yang ditinggalkan) | BERADA_DI | dunia ini`
  why: parallel-structure sentence contrasts family (in this world) vs. the deceased (in their own realm); only the "mendiang" branch was captured.

- **S1290**  `yadnya | BERPERAN_SEBAGAI | pengorbanan`
  why: "sebagai pengorbanan" (as a sacrifice) is a second predicate-role assertion on the same clause, entirely dropped.

- **S1407**  `ngaben jenis ini | MEMILIKI_SASARAN | jenazah`
  why: the sentence's second clause ("artinya benar-benar sasarannya adalah jenazah secara nyata" — meaning its real target is truly the corpse) states an important fact never extracted.

- **S1458**  `alat upakara | DISEDIAKAN_DI | rumah`
  why: "sesajen dan alat upakaranya" is a 2-item coordinate subject; only "sesajen" survived.

- **S1461**  `adegan | TERBUAT_DARI | daun rontal` (+ `adegan | BERALASKAN | bakul kecil atau pangkon`)
  why: generous component-level extraction per the rubric's "more extraction" mandate — these details are present but only captured as one long literal blob (see FIX above).

- **S1463**  `roh mendiang | DIPERSILAKAN_DI | adegan`
  why: "atma atau roh mendiang" is a 2-item coordinate subject; only "atma" survived.

- **S1465**  `jun pere | BERISI | air` (+ `jun pere | BERISI | 54 atau 108 lembar daun alang-alang`, `jun pere | BERISI | sembilan batang kayu cendana`)
  why: "berisikan air, ... lembar daun alang-alang serta ... batang kayu cendana" is a 3-item coordinate list nested under the jun pere's contents, entirely unextracted (existing relations only cover pengawak→jun pere and jun pere→periuk tanah).

- **S1467**  `pengawak | BERADA_DI | tempat yang telah ditentukan`
  why: "adegan dan pengawak" is a 2-item coordinate subject; only "adegan" survived.

- **S1474**  `sesajen | DIPERSEMBAHKAN_KEPADA | mendiang`
  why: the actual recipient of the offerings ("kepada mendiang") was dropped from the relations entirely in favor of the enumerated item list (see FIX above for that mislabeling).

- **S1477**  `tirtha pangentas (dan isinya) | DIPERSATUKAN_DENGAN | isi pengawak`
  why: this is the sentence's actual main verb/predicate and was never extracted at all (see DROP above for the bad decomposition that replaced it).

- **S1482**  `sawa | MENJADI | abu (seluruhnya)`
  why: "hingga hangus jadi abu seluruhnya" (until entirely reduced to ash) is the culminating result of the cremation and sets up the very next sentence (S1483, "abu itu...") — currently unextracted.

- **S1504**  `ngulapin | MEMILIKI_MAKNA | makna yang mirip dengan itu`
  why: the sentence's main clause ("ngulapin juga mempunyai makna yang mirip dengan itu") was skipped entirely in favor of only the "selaku nama upacara" adjunct.

- **S1525**  `pengawak | BERADA_DI | balai adat` (+ `pengawak | DIBERI | sajen`, `pengawak | DIBERI | perjamuan lain`)
  why: "adegan dan pengawak" is a 2-item coordinate subject; "pengawak" was dropped from all three relations built on this sentence. Same systemic subject-coordination gap as S1439/S1458/S1463/S1467 — see N10 regression note.

- **S1533**  `pengawak | DIPERLAKUKAN_SAMA_DENGAN | sawa asli`
  why: "sama dengan sawa asli dalam pengabenan itu" (treated the same as the real corpse) is the whole point of the sentence and was dropped.

- **S1556**  `panca datu | DIGUNAKAN_UNTUK | memohon kepada hyang widhi (restu panca dewata)`
  why: the long purpose clause explaining what the mystical power is *for* was entirely unextracted; proposing a simplified version rather than the full clause given its length/complexity.

- **S1584**  `tarpana | DILAKUKAN_DENGAN | pujastawa` (+ `tarpana | DILAKUKAN_OLEH | ida sang sadaka`)
  why: the second clause of the sentence (the ritual invocation performed via pujastawa by the priest during tarpana) was entirely unextracted.

- **S1597**  `kakerebsari | ADALAH | alat upakara yang pelik dalam pangabenan ini`
  why: "kajang atau kakerebsari" is a 2-item coordinate subject (alternate name); only "kajang" survived.

## NOTE  (borderline / systemic observation, no single fix)

- **N1 regression check (sentences S1189/S1205/S1206/S1261/S1429/S1456 named in task, plus others found):**
  HOLDING: S1189, S1205, S1206 (full "berfungsi/untuk menetapkan" clauses retained), S1261 (relative clause retained, only a quantifier lost), S1597 (full relative clause retained). Also newly confirmed holding elsewhere in this chunk isn't applicable (S1189-S1206 are the chunk-3 anchors).
  **NOT HOLDING (gap):** S1429 and S1456 — both named check sentences — still strip the defining clause. Additional gap instances found beyond the named list: S1378, S1430, S1461, S1483, S1552 (the last is a direct "berfungsi sebagai" case, the exact named pattern). Pattern of the gap: it fails specifically when the defining clause is (a) an acl:relcl attached to the object head noun without an intervening "secara ADJ berfungsi" pivot (S1456), or (b) a "bahwa" clause attached as advcl to the copula root rather than as a child of the object noun (S1429). **Verdict for chunk 3: partial** — holding for the "X secara formal/religius berfungsi Y" shape, still leaking for plain "yang"/"bahwa" relative and complement clauses on the object.

- **N10 regression check:** strong successes on **object-side** coordinate lists — S1361 (5-way), S1474 (4-way), S1523 (3-way) all fully captured. But **subject-side** coordinate NPs are still being truncated to their first member across the board: S1439 (7-way body-part list — only 1 kept), S1458, S1463, S1467, S1525 (all 2-item "X dan Y" subjects — only X kept), S1597 (2-item alternate-name subject). **Verdict: the N10 fix appears to only walk conjuncts reachable from the object/relation-argument side; subject-side compound/coordinate NPs are unaffected and still truncated.**

- **S13 regression check:** two clear leak-throughs found — S1226 ("di mata umat hindu," the exact phrase named in the instructions as an S13 example) and S1452 ("menurut lontar petunjuknya"). **Verdict: not holding** in this chunk; both instances produced a full relation triple using the attribution phrase as the object.

- **N6 regression check:** S1493 is the only "termasuk"-style case in this chunk. The swap mechanism itself is working (member as subject, category as object, JENIS_DARI direction correct), but the category-anchor resolution grabbed the wrong noun (the sentence's unrelated main subject "manah" instead of the true antecedent "standar kedudukan..."). **Verdict: partial** — direction fixed, anchor resolution still buggy.

- **N5/N7/N8/N9 (still-open, unfixed) confirmation:** S1514 shows the same subject-qualifier-stripping pattern named in the task (adegan's descriptive relative clause "yang sudah disisipkan sebuah awak-awakaning sawa..." stripped from the subject) — confirmed still present, as expected (not newly regressed, just still open).

- **S1221**: object "klungah nyuh gading/suku tunggal" merges what may be two distinct containers (klungah nyuh gading vs. suku tunggal, per NER canonical mapping) via a literal "/" in the source text — ambiguous whether this should be split into two relations or kept as one alternation. Flagging for awareness, not a hard fix.

- **S1409**: sentence contains two negated exclusions ("bukan dari hasil galian tanam titip," "bukan dari sawa yang disekeh") that carry real information but don't fit the positive-triple schema; likely fine to leave unextracted given the relation vocabulary has no negation predicate.

## Chunk stats
FIX: 30   DROP: 5   ADD: 20   sentences reviewed: 61

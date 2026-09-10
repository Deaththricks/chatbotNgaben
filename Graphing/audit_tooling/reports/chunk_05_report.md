# Chunk 5 audit (S2093..S2630)

## FIX  (triple is salvageable — give the corrected triple)

- **S2093 [0]**  current: `mendiang | MEMILIKI | ikatan erat`
  fix: `mendiang | MEMILIKI | ikatan erat dengan masyarakat`
  why: object dropped "dengan masyarakat" (with society) — too terse, loses who the bond is with.

- **S2115 [0]**  current: `swadharma kemasyarakatan | ADALAH | mahayana`
  fix: `kelompok ini | ADALAH | paksa mahayana (kendaraan besar)`
  why: wrong subject. "dinamai" (is named) really applies to "kelompok ini" (this group); "swadharma kemasyarakatannya itu" is the *karena* (because)-clause giving the reason for the name, not the entity being named. Translation: "this group is called Mahayana ('great vehicle'), because its duty is to carry humankind to the afterlife."

- **S2130 [0]/[1]**  current: `peranda shiwa | MENEMPATKAN | diri` / `peranda shiwa | MENEMPATKAN | jenana`
  fix: `peranda shiwa | MENEMPATKAN | diri/jenana pada daya suci hyang widhi`
  why: both drop the locative "pada daya suci hyang widhi itu" (at/in the sacred power of Hyang Widhi) — the actual destination of the placement, not a decorative detail.

- **S2130 [2]**  current: `peranda shiwa | DILETAKKAN_DI | atas alias`
  fix: `peranda shiwa | MENEMPATKAN_DIRI_DI | luar alam duniawi (mula-mula di atas / di luar alam duniawi)`
  why: "atas alias" is a broken fragment — "alias" here means "atau/aka", joining two paraphrases of the same location ("above", aka "outside the mundane world"), not a distinct object. Also mislabeled as passive DILETAKKAN when the verb is active "menempatkan" (the priest places himself).

- **S2133 [0]**  current: `naga banda | DILAKUKAN_SAAT | palebon`
  fix: `naga banda | DIGUNAKAN_SAAT | palebon`
  why: naga banda is a ritual object that is "used" (digunakan), not an event that "is done" (dilakukan) — wrong relation label.

- **S2184 [1]**  current: `bale salunglung | DILETAKKAN_DI | arah hulu`
  fix: `bale salunglung | DILETAKKAN_DI | sekitar empat atau lima meter di arah hulu dari tempat pembakaran jenazah`
  why: drops the distance and reference point ("about 4-5 meters upstream from the cremation site") — too terse.

- **S2198 [3]**  current: `wilayah | ADALAH | kantongnya sesuatu`
  fix: `wilayah | ADALAH | kantongnya segala sesuatu yang didetasering di dunia ini`
  why: object drops "segala" (all/every) and the defining relative clause "yang didetasering di dunia ini" (that which is discharged/released into this world) — this is the entire point of the metaphor. See N1 regression note below.

- **S2212 [0]**  current: `bale salunglung | ADALAH | simbol pitraloka`
  fix: `bale salunglung | ADALAH | simbol pitraloka untuk tempat badan halus mendiang`
  why: drops the parenthetical purpose clause "(untuk tempat badan halusnya mendiang)" = "(as the place for the deceased's subtle body)" — explains what the symbol is for.

- **S2256 [0]**  current: `pamerasan | ADALAH | uang kepeng`
  fix: `pamerasan | ADALAH | sejumlah uang kepeng yang dibungkus dengan daun dapdap dan diikat benang tridatu`
  why: drops the defining relative clause (wrapped in dapdap leaf, tied with tridatu thread) that actually explains what pamerasan physically is — N1-style truncation.

- **S2258 [0]**  current: `pamerasan | ADALAH | sarana pemberitahuan`
  fix: `pamerasan | ADALAH | sarana pemberitahuan akan adanya pangabenan untuk mendiang`
  why: drops "akan adanya pangabenan untuk mendiang" (about the upcoming ngaben for the deceased) — the object of the notification, not decorative. See N1 regression note below.

- **S2258 [1]**  current: `sarana pemberitahuan | DITUJUKAN_UNTUK | mendiang`
  fix: drop this triple (superseded by fix to [0]) or relabel as `pangabenan | DITUJUKAN_UNTUK | mendiang`
  why: "untuk mendiang" grammatically attaches to "pangabenan" (whose ngaben it is), not to "sarana" itself; as extracted it wrongly implies the notification is directed *at* the deceased.

- **S2262 [0]**  current: `tirtha | DIMOHON_DI | pendeta`
  fix: `tirtha | DIMOHON_KEPADA | pendeta yang muput pangabenan itu`
  why: "pada pendeta" means "from/to the priest" (a person), not a location — DIMOHON_DI wrongly implies location; also drops the defining relative clause (the priest who officiates that very ngaben).

- **S2323 [1]**  current: `bade | BAGIAN_DARI | alat penting lainnya`
  fix: `bade (dan lembu) | TERMASUK_BERSAMA | alat penting lainnya (semua tergolong sarana siap pakai)`
  why: reversed/wrong relation. "termasuk segala alat penting lainnya" is a parenthetical noting that bade & lembu are grouped WITH other tools under "sarana siap pakai" — it is not a part-of relation with bade as the whole. Same failure family as the N6 "termasuk" reversal.

- **S2336 [4]**  current: `kajang | MELAMBANGKAN | tanda hormat bakti`
  fix: `kajang | MELAMBANGKAN | tanda hormat bakti kepada mendiang`
  why: drops "kepada mendiang" (to the deceased) — who the gesture of respect is directed at.

- **S2340 [0]**  current: `adegan | ADALAH | arak-arakan indah`
  fix: `adegan | DIJADIKAN | unsur arak-arakan indah (oleh pemudi-pemudi keluarga bersangkutan)`
  why: wrong label (ADALAH implies identity; text says "dijadikan" = made into) and drops "unsur" (element of) — adegan is a *component* of the procession, not equal to the whole procession.

- **S2363 [0]**  current: `bale pamuunan | DIKELILINGI | tiga kali`
  fix: `bale pamuunan | DIKELILINGI_OLEH | bade dengan jenazahnya (sebanyak tiga kali)`
  why: "tiga kali" is just the frequency adverbial; the real missing content is the agent doing the circling (the bade carrying the corpse).

- **S2364 [0]**  current: `bade | DILETAKKAN_DI | teben lembu`
  fix: `bade | DILETAKKAN_DI | sebelah hilir atau teben lembu`
  why: drops the coordinate alternative "sebelah hilir" (downstream side) — "hilir" and "teben" are conjoined via atau (or) in the parse; missing coordinate member.

- **S2370 [0]**  current: `pradaksina | MEMPEROLEH | imbas kesucian`
  fix: `material | MEMPEROLEH | imbas kesucian dari yang immaterial`
  why: wrong subject. Pradaksina (the ritual turning) *symbolizes* the process; it is "material" that receives the imprint of sanctity per the embedded clause, not pradaksina itself.

- **S2374 [0]**  current: `prasawya | ADALAH | lambang gerak peningkatan diri`
  fix: `prasawya | ADALAH | lambang gerak peningkatan diri dari sesuatu, atau gerak ke atas`
  why: drops the second coordinate alternative definition "atau gerak ke atas" (or: upward movement) — missing coordinate member.

- **S2377 [0]**  current: `ngaben | MEMILIKI | tujuan pokok`
  fix: `ngaben | MEMILIKI | tujuan pokok untuk merubah jenazah (atau "benda bekas" badan seseorang) hingga kembali menjadi pancamahabutha sebagaimana asalnya semula`
  why: N1 regression — see note below; the untuk-continuation defining the actual purpose is entirely dropped.

- **S2380 [1]**  current: `cara prasawya | ADALAH | berputar`
  fix: `cara prasawya | ADALAH | berputar ke kiri, berlawanan dengan putaran jarum jam`
  why: truncated to a bare verb stem, dropping the only informative part (counterclockwise, leftward turning).

- **S2387 [0]**  current: `bade sawa atas | DILETAKKAN_DI | hilir lembu`
  fix: `bade (dengan sawa di atasnya) | DILETAKKAN_DI | sebelah hilir lembu`
  why: subject is a flattened, ungrammatical fusion ("bade sawa atas") that drops the prepositions "dengan" and "di" showing how bade and sawa relate; object drops "sebelah" (the side/vicinity of).

- **S2419 [0]**  current: `adegan | DIPERSEMBAHKAN_KEPADA | hyang agni`
  fix: `adegan, angenan, pisang jati, panguryagan, dan lain-lain alat yang harus dibakar | DIPERSEMBAHKAN_KEPADA | hyang agni (api), tanpa sisa`
  why: major N10-type coordinate-list truncation — the sentence lists five conjuncts (a "dan lain-lain" list) but only "adegan" (the first) was kept as subject.

- **S2448 [0]**  current: `suku tunggal | DITUJUKAN_UNTUK | bhatara-bhatari`
  fix: `suku tunggal | MENGHATURKAN | sembah bakti pamitan kepada bhatara-bhatari`
  why: flattens the actual predicate (offering a farewell homage) into a generic "directed to", losing the specific ritual act being described.

- **S2455 [0]**  current: `pangabenan | TERDIRI_DARI | jenis`
  fix: `pangabenan | TERDIRI_DARI | berbagai jenis`
  why: drops "berbagai" (various) — matches flag.txt precedent (#801) that bare "jenis" loses the quantifier nuance.

- **S2472 [0]**  current: `pranawa | BERARTI | lambang suara`
  fix: `pranawa | BERARTI | lambang suara "om"`
  why: drops the appositive "om" naming which sound-symbol is meant — without it the object is vague.

- **S2483 [0]**  current: `mendiang | MEMPEROLEH | situasi demikian`
  fix: `mendiang | MEMPEROLEH | situasi demikian di alam lain`
  why: drops "di alam lain" (in the afterlife/other realm) — an important locative qualifier.

- **S2483 [1]**  current: `supta pranawa | ADALAH | satu pangabenan`
  fix: `supta pranawa | ADALAH | satu pangabenan yang berlandaskan hasrat, semoga mendiang mendapatkan situasi demikian di alam lain`
  why: N1-style truncation — "satu pangabenan" is a generic noun whose defining yang-clause was dropped.

- **S2485 [0]**  current: `pangabenan pranawa | DITUJUKAN_UNTUK | mendiang`
  fix: `pangabenan pranawa | DITUJUKAN_UNTUK | mendiang yang telah tak ada sawanya lagi`
  why: drops the crucial defining relative clause — this ngaben type is specifically for deaths where no physical corpse remains; without the clause the triple is much broader than the source claims.

- **S2502 [1]/[2]/[3]**  current: `sawa wedana | DIGELAR_DENGAN | roh` / `arwah` / `badan halus mendiang`
  fix: `sawa wedana | BERTUJUAN_MENYUCIKAN | roh` / `arwah` / `badan halus mendiang`
  why: roh/arwah/badan-halus are the *targets being purified* by the ceremony, not something the ceremony "is held with" — wrong relation label.

- **S2502 [4]**  current: `sawa wedana | MENJADI | atma`
  fix: `badan halus mendiang (roh/arwah) | MENJADI | atma yang tanpa badan sama sekali`
  why: wrong subject — the ceremony itself doesn't "become" atma; the deceased's spirit/subtle-body does, as the ceremony's result.

- **S2527 [0]/[1]**  current: `pura | ADALAH | dewaloka` / `pura | ADALAH | alam kedewaan`
  fix: `pura, pamrajan, atau kahyangan jenis apapun | ADALAH | dewaloka atau alam kedewaan`
  why: N10 coordinate-list truncation — subject lists 3 conjuncts (pura, pamrajan, kahyangan jenis apapun) via atau, but only "pura" was kept.

- **S2535 [0]**  current: `pitara | MENGELUPASI | suksmasarira`
  fix: `pitara | MENGELUPASI | suksmasarira yang merupakan "kulit dirinya"`
  why: drops the defining appositive clause ("which is the skin of himself").

- **S2542 [0]**  current: `atma wedana | MEMILIKI | jenis`
  fix: `atma wedana | MEMILIKI | beberapa jenis`
  why: drops "beberapa" (several) — same terseness pattern as flag.txt #801.

- **S2548 [0]/[1]**  current: `tirtha pangentas atiwa-tiwa | DIPERCIKKAN_PADA | sesosok mayat` / `perlambang`
  fix: `tirtha pangentas atiwa-tiwa | DIPERCIKKAN_PADA | sesosok mayat atau perlambangnya, hanya sekali saja`
  why: drops the ritual constraint "hanya boleh... sekali saja" (may only be sprinkled once) — a defining rule, not decoration.

- **S2555 [0]**  current: `atma wedana | ADALAH | upacara penyucian pitra`
  fix: `atma wedana | ADALAH | nama resmi upacara penyucian pitra`
  why: drops "nama resmi" (official name) framing — changes "official name for X" into a flatter identity claim.

- **S2563 [0]**  current: `bhuwana alit | MEMILIKI | 11 bidang`
  fix: `bhuwana alit | MEMILIKI | 11 bidang yang mudah ditimpa suasana "sebel"`
  why: N1-adjacent — drops the defining relative clause about these 11 spheres.

- **S2566 [0]**  current: `demikian bhuwana agung | MEMPEROLEH | cuntaka`
  fix: `bhuwana agung (masing-masing arah yang berjumlah 11) | MEMPEROLEH | cuntaka selama sehari`
  why: subject wrongly includes the stray sentence-adverb "demikian" (likewise) and drops the appositive "masing-masing arah yang berjumlah 11" (each of its 11 directions) — the actual referent receiving cuntaka.

- **S2571 [0]**  current: `arjuna | MENGHUKUM | diri`
  keep as-is (fine).

- **S2604 [0]**  current: `kedua ngangsen | ADALAH | <45-word verbatim run-on>`
  fix (split into atomic triples):
  `ngangsen | ADALAH | upacara penyucian sementara bagi sang pitra`
  `pitra (dalam ngangsen) | BARUSAN_LEPAS_PERTALIAN_DENGAN | stulasarira nya`
  `ngangsen | BERTUJUAN | agar suksmasarira pitra tidak lagi dilekati bekas-bekas badan kasar`
  why: current triple dumps the entire sentence as one undifferentiated ~45-word literal object (the opposite failure of terseness); should be decomposed as elsewhere in this corpus. Subject also wrongly retains "kedua" (a list-numbering discourse marker "secondly"), not part of the entity name.

- **S2612 [0]**  current: `pitra | MENGHASILKAN | perlambang`
  fix: `pitra mendiang | DIBUATKAN | perlambang (yang disebut sekah kangsen)`
  why: benefactive-passive inversion (N3-family) — "dibuatkan" means the effigy is made FOR the pitra (recipient), not that pitra actively produces it; MENGHASILKAN wrongly casts pitra as agent.

- **S2620 [0]**  current: `dulang | DILETAKKAN_DI | hulu arena upacara`
  fix: `dulang atau meja kecil | DILETAKKAN_DI | bagian hulu arena upacara`
  why: drops the coordinate subject "atau meja kecil" — missing coordinate member.

- **S2624 [0]**  current: `pitra mendiang | MEMAKAI | wujud`
  fix: `pitra mendiang | MEMAKAI | wujud tersebut selaku "pralingga"-nya (perlambang diri yang dihuni)`
  why: drops the defining appositive explaining what "wujud" refers to.

- **S2630 [0]**  current: `pitra | DINILAI_DENGAN | upacara penyucian`
  fix: `pitra | MENERIMA | sembah bhakti serta ayaban sajen`
  why: "dengan upacara penyucian ini" is an instrumental adjunct on the whole sentence, mislabeled as an evaluative fact about pitra; the real predicate (pitra receives homage and offerings) is missing entirely.

## DROP  (triple should be removed)

- **S2117 [0]**  `peranda buddha | BERDASARKAN | pengertian`
  why: "berdasarkan" is a citation/reasoning-basis adjunct ("based on this understanding..."), not a real-world predicate connecting peranda to pengertian — nonsense triple; see ADD for the real content.

- **S2269 [0]**  `bale pamuun (BANGUNAN_RITUAL) | LAINNYA | de facto`
  why: nonsensical; "secara de facto" is an adverbial phrase describing completion status ("has actually already been completed"), not an entity; LAINNYA is a non-predicate catch-all label.

- **S2502 [0]**  `sawa wedana | ADALAH | wedana`
  why: "(wedana)" is a same-root gloss of the verb "menyucikan" ("to purify" = "mewedana"), not a distinct entity; tautological/nonsensical restating sawa wedana as "wedana".

- **S2542 [1]**  `atma wedana (RITUAL_KEMATIAN) | MEMILIKI | hal pangabenan (RITUAL_KEMATIAN)`
  why: "sebagaimana halnya pangabenan" is a comparative adjunct ("just as with ngaben"), not a possession fact — S13 leak of a comparative clause into a nonsense MEMILIKI triple. See regression note below (confirmed still-open, matches iteration-1 flag on this exact sentence).

- **S2566 [1]**  `demikian bhuwana agung | MEMPEROLEH | sehari`
  why: duplicate fragment — "selama sehari" is a duration adjunct of relation [0], not an independent fact; also inherits the stray-"demikian" subject problem.

- **S2571 [1]**  `arjuna | MENGHUTAN | 12 tahun`
  why: wrong object (drops "sang rama beserta laksmana", the actual target of "menghutankan"/exiled-to-forest) and likely wrong subject (Arjuna is probably not who exiles Rama here — this reads as a separate mythological comparison). Segmentation is too garbled to safely reconstruct; recommend drop over a guessed fix (cf. flag.txt #191).

## ADD  (missing triples the sentence supports)

- **S2093**  `mendiang | MEMILIKI | pertalian intim dengan soal duniawi material`
  why: second parataxis clause ("mempunyai pertalian yang intim dengan soal duniawiah material") not extracted at all.

- **S2115**  `kelompok (paksa mahayana) | BERTUGAS_MENGANGKUT | masyarakat manusia ke alam sana`
  why: the purpose/duty clause ("bertugas memuat/mengangkut masyarakat manusia ke alam sana" — tasked with carrying humankind to the afterlife) is entirely unextracted.

- **S2117**  `peranda buddha | MEMAKAI | naga banda` (+ `naga banda | DIPAKAI_SAAT | palebon`)
  why: the sentence's actual content (a Buddhist priest is deemed fit to wear naga banda at his cremation) was never extracted; only a nonsense "berdasarkan" fragment was.

- **S2124**  `swadharma (beliau) | BERTUJUAN_UNTUK | menyucikan dunia ini`
  why: "untuk mamari-suddha (menyucikan) dunia ini" (to purify this world) — the purpose of the swadharma — sits on the subject side and is entirely dropped from any relation.

- **S2130**  `peranda shiwa | TURUN_MERESAPI | alam ini`
  why: "lalu turun meresapi alam ini" (then descends to permeate this world) — the resolution of the sentence — is unextracted.

- **S2234**  `jenazah seseorang | TERTANAM_TITIP_DI | sebuah setra`
  why: the parenthetical describing the prior provisional-burial site ("yang telah tertanam-titip pada sebuah setra") is dropped.

- **S2252**  `mendiang (keponakan, cucu-cucu) | TERGOLONG | keluarga sampingan (bukan keluarga satu sidikara/saling sembah)`
  why: the relative clause classifying these relatives as distant, not close, kin is unextracted.

- **S2258**  `pamerasan | ADALAH | tanda bahwa keluarga mendiang tidak lupa akan adanya ikatan keluarga`
  why: the second parataxis conjunct ("serta selaku tanda, bahwa...") is entirely dropped — see N1 regression note.

- **S2262**  `sang cucu | MEMOHON | tirtha`
  why: subject of the requesting action ("oleh sang cucu... tirtha itu dimohon") is not represented in any relation.

- **S2269**  `bale pamuun (dan alat-alat upakara lainnya) | TELAH_SELESAI | (secara de facto)`
  why: real content of the sentence (the building and ritual tools are, in practice, already complete) has no corresponding triple once [0] is dropped.

- **S2336**  (note only, see below — 3-item coordinate list already fully captured here, a positive confirmation of N10).

- **S2363**  `bale pamuunan | DIHUNI | lembu`
  why: relative clause "yang telah dihuni lembu" (already housed by the lembu) is unextracted.

- **S2370**  `pradaksina | MELAMBANGKAN | turunnya purusa meresapi pradana`
  why: the sentence's primary symbolic content (spirit descending to permeate matter) — what "melambangkan" actually governs — is missing from every relation; only a mis-subjected tail effect was captured.

- **S2380**  `bade | BERLAWANAN_DENGAN | gerak pradaksina yang dilakukan pada upacara dewa yadnya di pura`
  why: the second coordinate clause ("serta berlawanan pula dengan gerak pradaksina...") is entirely unextracted.

- **S2419**  (superseded by FIX above restoring the full coordinate subject list).

- **S2448**  `bhatara-bhatari | BERSEMAYAM_DI | pura dan pamrajan panyiwiannya`
  why: the relative clause describing where the deities reside is unextracted.

- **S2455**  `pangabenan jenis (masing-masing) | MEMILIKI | nama sendiri-sendiri`
  why: "masing-masing mempunyai nama sendiri-sendiri" (each type has its own name) is a distinct fact, unextracted.

- **S2473**  `pangabenan yang menggunakan nama pranawa | DILATARBELAKANGI_OLEH | hasrat supaya mendiang memperoleh ketenangan, kemantapan, dan kesucian`
  why: the main clause of the sentence (what motivates using the name "pranawa") is entirely missing; only the embedded supaya-clause was captured (correctly, as 3 coordinate members — good).

- **S2520**  `atma wedana | BERBEDA_DENGAN | ngaben (dalam hal sifat sebel)`
  why: the comparative clause ("berbeda dengan ngaben") establishing the contrast between ceremony types is unextracted.

- **S2535**  (NOTE, not ADD — see below; the simile is likely too poetic to encode as a factual triple).

- **S2542**  `jenis atma wedana (masing-masing) | MEMILIKI | nama dan ciri-ciri tersendiri`
  why: "masing-masing punya nama dan ciri-ciri tersendiri" is unextracted.

- **S2612**  (see FIX above — recipient/agent correction covers the missing nuance).

- **S3080** — n/a (chunk 6).

- **S2604 / S3001-style run-ons**: see FIX splits above.

## NOTE  (borderline / systemic observation, no single fix)

- **N1 regression check — S2198**: mostly HOLDING. Relations [0] and [1] correctly retain their defining continuations ("bagaikan pitraloka"; "tempat pitra mendiang yang diaben"). But relation [3], an `object_decomposition` child of "wilayah", still truncates the appositive's own relative clause ("yang didetasering di dunia ini") — the fix appears applied at the top-level copula split but not recursively into decomposition children. **Partial regression** (see FIX above).

- **N1 regression check — S2258**: NOT HOLDING. The object_decomposition still misattributes "untuk mendiang" as if the *sarana* itself is directed at the deceased (rather than describing whose ngaben is being announced), and the second parataxis conjunct ("serta selaku tanda, bahwa keluarga mendiang tidak lupa...") is entirely dropped — exactly the parataxis-retention behavior N1 was supposed to add. **Confirmed regression / unfixed.**

- **N1 regression check — S2377**: NOT HOLDING. `ngaben MEMILIKI tujuan pokok` still truncates the object without its "untuk merubah jenazah... hingga kembali menjadi pancamahabutha..." continuation — this is the exact case iteration 1 flagged, and it remains unfixed in iteration 2.

- **N1-adjacent (outside the required check list)**: The same "ADALAH/MEMILIKI + bare generic noun, defining clause dropped" pattern recurs repeatedly and inconsistently elsewhere in this chunk: S2256, S2483[1], S2502(all), S2555, S2563, S2624, S3091(chunk 6) all show the same gap, while S2265 ("nyikut karang ADALAH upacara yang sangat sederhana"), S2649(chunk 6), and S2904(chunk 6) show it working correctly. The fix looks like it was applied to specific patterns/sentences rather than generalized across all copula+generic-noun cases.

- **N10 check — S2336**: HOLDING (positive). The 3-member coordinate chain "sambungan, kain putih, [dua atau 30] meter" is fully captured across three separate relations (kajang DIBERI sambungan/kain putih/30 meter) — good confirmation the transitive conjunct walk generalizes beyond the specifically-flagged iteration-1 examples.

- **N10 violations found beyond the required check list**: S2419 (5-member "dan lain-lain" list truncated to 1), S2527 (3-member atau-list truncated to 1), S2093/S2374/S2380/S2455/S2620/S2566 (2-member lists, one member dropped). N10 is holding for straightforward "A, B, dan/atau C" lists but still fails on longer or more loosely-structured lists (open-ended "dan lain-lain", multi-level nesting, or lists spread across appositives/parentheticals rather than a single flat conjunction chain).

- **S13 check — S2527 / S2555**: HOLDING. The attribution/perspective phrases "di mata hati umat hindu" (in the hearts of Hindu people) and "menurut pustaka yang kita warisi" (according to the scriptures we've inherited) are correctly excluded from any relation object in both sentences — no leakage observed.

- **S2542 comparative check ("sebagaimana halnya X")**: NOT HOLDING — see DROP entry above. This is the exact sentence iteration 1 flagged as still-open, and the widened S13 fix has not closed it. Confirmed regression.

- **S2224**: `ngangkid galih ADALAH kegiatan kerja semata` — borderline KEEP; drops "hampir hanya" (almost merely), a minor hedging nuance, not worth a hard FIX.

- **S2316**: `undagi TERLIBAT_DI acara khusus` — KEEP but note the comitative "dengan bade atau wadah dan lembunya" (implying these ritual objects are also involved) is not separately captured; low priority.

- **S2337**: relations reasonably sound; "dinaikkan" (raised) as a distinct co-ordinate action alongside "dilipat-lipat/ditindihkan" has no object of its own in the source text, so nothing to extract there — no issue.

- **S2406**: `jenazah ADALAH sasaran kegiatan` — minor: "menjadi" (becomes) softened to "adalah", and "segala" (every) dropped; not worth a hard fix.

- **S2449**: `suku tunggal DIHANYUTKAN_KE laut` — correct subject (the ash vessel, not the ceremony name) — good confirmation that the flag.txt #58b/58c wrong-subject pattern is not recurring here.

- **S2535**: the simile "sebagaimana halnya seekor udang yang tengah menylongsong" (like a molting shrimp) is entirely unextracted; likely acceptable to leave out as a literary comparison rather than a factual sarana relation, but flagging in case the team wants poetic similes captured too.

- **S2780** (chunk 6 cross-reference only — not applicable here).

## Chunk stats
FIX: 40   DROP: 6   ADD: 20   sentences reviewed: 61

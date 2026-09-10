# Chunk 8 audit (S3816..S4340)

## FIX  (triple is salvageable — give the corrected triple)

- **S3836 [1]**  current: `bale-bale dipan | DIPAKAI_UNTUK | warung`
  fix: `bale-bale/dipan (dengan galar berketekan cawan) | DIPAKAI_UNTUK | dipan/plangkan di warung atau di dapur`
  why: N10 gap — "di warung ataupun di dapur" is a 2-item list; "dapur" (kitchen) is dropped. (See DROP for the companion [0] triple, which is circular nonsense.)

- **S3843 [2]**  current: `galar | MEMBUAT_DENGAN | harapan (Place)`
  fix: `galar (dengan ketekan guling) | DIGUNAKAN_DENGAN_HARAPAN | membuat ngantuk dan tidur nyenyak`
  why: nonsense triple — "harapan" (hope) is mistagged as object_type Place, and the predicate garbles "digunakan... dengan harapan bisa membuat ngantuk" (used with the hope it induces sleepiness) into a meaningless "MEMBUAT_DENGAN."

- **S3845 [0]**  current: `galar | MENGHASILKAN | keinginan`
  fix: `galar (dengan ketekan cekur) | MENGHASILKAN | keinginan untuk bertembang seperti makidung atau makekawin`
  why: N1-style truncation — the purpose clause (desire to sing traditional chant forms) is dropped. Gloss: cekur = an aromatic ginger-family root used here as a divination-count name; makidung/makekawin = traditional Balinese chant/poetry forms.

- **S3845 [1]**  current: `bale-bale | DILETAKKAN_DI | pura`
  fix: `bale-bale | DILETAKKAN_DI | pura atau merajan`
  why: N10 gap — "di pura atau di merajan" 2-item list; "merajan" (family shrine) dropped.

- **S3852 [1]**  current: `jumlah kelipatan 5 | ADALAH | misalnya 5 10`
  fix: `jumlah galar | CONTOH | 5, 10, 15, 20, 25, 30, dan seterusnya (kelipatan 5)`
  why: nonsense decomposition truncating a numeric example series after 2 of 6 values — a numeric-list analogue of the N10 truncation problem.

- **S3860 [0]**  current: `upacara mesulub | ADALAH | kepercayaan setempat`
  fix: `upacara mesulub | ADALAH | kepercayaan setempat (lokal) yang diwarisi turun-temurun sejak jaman dulu di daerah/desa setempat`
  why: N1 truncation — the "yang telah diwarisi..." relative clause is dropped.

- **S3862 [0]**  current: `upacara mesulub | ADALAH | konsep satya`
  fix: `upacara mesulub | ADALAH | konsep "satya" atau kesetiaan`
  why: drops the coordinate gloss "atau kesetiaan" (or loyalty/faithfulness) that explains the term.

- **S3909 [0]**  current: `jenazah | DIBAWA_KE | setra`
  fix: `jenazah | DIBAWA_KE | setra untuk segera dikuburkan (bukan diaben)`
  why: drops the crucial qualifier that this describes burial, not cremation — the whole point of the (rhetorical/contrastive) sentence.

- **S3914 [0]**  current: `jenazah | MEMILIKI | rangkaian upacara lain`
  fix: `jenazah | MENJALANI | rangkaian upacara lain sebelum dibawa ke setra (jika diaben)`
  why: wrong relation — the corpse doesn't "possess" a series of ceremonies; it undergoes them (and only if cremation, not burial, is chosen).

- **S3936 [0]**  current: `jenazah | DIBERI | pakaian layak orang`
  fix: `jenazah | DIBERI | pakaian seperti layaknya orang masih hidup`
  why: same N1 truncation as chunk 7's S3446 (duplicate passage) — "masih hidup" dropped.

- **S3964 [0]**  current: `jenazah | DIMINUMKAN | [very long literal clause]`
  fix: split into `jenazah | DIPERCIKI_DAN_DIMINUMKAN | tirta` (+) `tirta | BERASAL_DARI | bhatara hyang guru` (+) `tirta | DIMOHONKAN_DI | sanggah/pamerajan keluarga orang yang meninggal`
  why: duplicate of chunk 7's S3547 — a valid but unwieldy run-on literal that should be split into clean sub-facts; also recovers the dropped "diperciki" action (only "diminumkan" currently survives).

- **S4074 [0]**  current: `tirtha ening | BERFUNGSI_SEBAGAI | symbol pikiran`
  fix: `tirtha ening | BERFUNGSI_SEBAGAI | symbol pikiran dan perasaan sang yajamana, agar roh/atman tidak mengalami kegoncangan dan dapat mencapai alam sorga dengan tenang`
  why: N1-adjacent truncation — the object NP itself is cut short ("dan perasaan..." dropped) AND the consequence clause chained via "sehingga" off the main verb is also dropped. Contrast with S4116 below, where a similarly-long BERFUNGSI_SEBAGAI clause is retained in full — the fix appears to hold for clauses embedded inside the object NP but not for sibling "sehingga" consequence clauses hanging off the governing verb.

- **S4087 [0]**  current: `tirtha penembak | MEMILIKI | hubungan herat`
  fix: `tirtha penembak | MEMILIKI | hubungan erat dengan itihasa (Bisma Parwa, bagian dari Mahabharata)`
  why: drops "dengan itihasa" — the actual entity the relationship is with. Confirms the "MEMILIKI + dropped 'dengan X'" sub-pattern extends beyond the originally-flagged sentences (see NOTE on N1 below).

- **S4090 [0]**  current: `arjuna | MENYUGUHKAN | air cara dengan cara memanah tanah yang berada disamping rsi bisma`
  fix: `arjuna | MEMANAH | tanah (di samping rsi bisma)`
  why: object contains a garbled duplicate ("air cara dengan cara") — a malformed phrase. See ADD for the dropped result clause (water reaching Bisma's lips), which is the actual point of this Mahabharata reference (Arjuna's water-arrow for the dying Bhishma).

- **S4096 [0]**  current: `tirtha | DIBAWA_KE | setra`
  fix: `tirtha | DIBAWA_KE | setra untuk dipergunakan pada waktu pembakaran`
  why: drops the purpose-oblique "untuk dipergunakan pada waktu pembakaran" (to be used during the cremation).

- **S4106 [0]**  current: `tirtha ini | MEMILIKI | fungsi sarana`
  fix: `tirtha ini | MEMILIKI | fungsi sarana untuk mengucapkan permohonan pamit terhadap leluhur, agar dapat ikut masuk ke alam kedewataan`
  why: **N1 regression, one of the originally-flagged sentences — confirmed still broken.** The "MEMILIKI fungsi/hubungan + truncated head" sub-pattern is not fixed even though the sibling "ADALAH tirtha yang..." sub-pattern (see S4077/S4086/S4126 below) now is.

- **S4111 [0]**  current: `tirtha ini | MEMILIKI | fungsi sarana`
  fix: `tirtha ini | MEMILIKI | fungsi sarana yang dapat mengantarkan roh agar mendapatkan tempat yang baik, tidak mengalami kesengsaraan`
  why: same MEMILIKI-fungsi truncation, confirmed still broken (originally flagged).

- **S4121 [0]+[1]**  current: `tirtha pangentas | DIBUAT_DI | gria ida` (+) `tirtha pangentas | DIBUAT_DI | sulinggih`
  fix: merge into `tirtha pangentas | DIBUAT_DI | gria ida sang sulinggih (kediaman/kertas pendeta)`
  why: "gria ida sang sulinggih" is one entity (the priest's residence); splitting it produced a nonsensical second triple treating the priest himself as a location.

- **S4121 [2]**  current: `tirtha pangentas | DILAKSANAKAN | upacara pengabenan`
  fix: `tirtha pangentas | DIBUAT_SAAT | upacara pengaskaran (bertepatan dengan puncak upacara pengabenan)`
  why: wrong relation — the tirtha itself isn't "carried out"; it's made at a particular time within the larger cremation-ceremony sequence.

- **S4128 [0]**  current: `tirtha pangentas | MEMILIKI | fungsi utama`
  fix: `tirtha pangentas | MEMILIKI | fungsi utama sebagai sarana untuk "ngentas": memberikan jalan dan membersihkan noda-noda roh/atma agar dapat menuju alam kedewataan`
  why: same MEMILIKI-fungsi truncation, confirmed still broken.

- **S4128 [1]**  current: `tirtha pangentas | MEMBERIKAN | jalan`
  fix: `tirtha pangentas | MEMBERSIHKAN | noda-noda para roh/atma orang yang meninggal`  (in addition to, not replacing, MEMBERIKAN jalan)
  why: "memberikan jalan DAN membersihkan noda-noda" is a 2-verb coordination; only the first verb survived. See ADD for the entirely-missing independent clause about upacara pengabenan.

- **S4169 [0]**  current: `tirtha pangentas | ADALAH | seuatu`
  fix (best-effort, source text itself looks like a typo/OCR garble — "seuatu yang memiliki arti yang dengan..." probably means "sesuatu yang memiliki arti yang erat dengan"): `tirtha pangentas | ADALAH | sesuatu yang memiliki arti (erat) dengan upacara pitra yadnya`
  why: as extracted, "ADALAH seuatu" ("is something") is content-free — essentially a vacuous triple. Flag with caveat that the underlying sentence is disfluent.

- **S4170 [0]**  current: `tirtha pangentas | ADALAH | tirtha yang diharapkan dan diyakini sebagai alat atau sarana sangat penting bagi umat hindu`
  fix: `tirtha pangentas | ADALAH | tirtha yang diharapkan/diyakini sebagai sarana penting bagi umat hindu, khususnya untuk melepaskan roh leluhur dari ikatan keduniawian, agar dapat meningkat menuju alam bhwah loka`
  why: **N1 regression, originally-flagged sentence — confirmed still broken.** Drops the entire "khususnya dalam hubungannya untuk..." explanation of what the tirtha actually does — the most substantive part of the sentence.

- **S4177 [1]**  current: `atma lingga | ADALAH | mewujudkan sanghyang ongkans`
  fix: `atma lingga | MEWUJUDKAN | sanghyang ongkara dan tri aksara dalam diri (yang berstana dalam bathin)`
  why: nonsense — ADALAH (copula) cannot take a verb phrase ("mewujudkan...") as its complement. The real verb is "mewujudkan"; also recovers "dan tri aksara" and "yang berstana dalam bathin," both dropped.

- **S4192 [0]**  current: `tirtha pangentas | ADALAH | sesunguhnya tirtha gangga`
  fix: `tirtha pangentas | ADALAH | tirtha gangga yang diturunkan atau dibuat oleh pendeta/sang sulinggih`
  why: N1 truncation — drops who brings it down/makes it (the priest).

- **S4212 [0]**  current: `abu abu kekototan | BERSINAR | matahari`
  fix: `badan | BERSINAR_BAGAIKAN | matahari`
  why: wrong subject — text says the "ash of impurity" (abu-abu kekototan) *vanishes* (musnah), while it is the *body* that begins to shine like the sun. As extracted, this claims the ash shines, which is backwards. See ADD for the dropped "musnah" fact.

- **S4273 [0]**  current: `padang lepas | DIBAWA_KE | periuk`
  fix: `padang lepas | DIMASUKKAN_KE_DALAM | periuk`
  why: label inconsistency — "dimasukan ke dalam periuk" is an insertion, not a transport-to-a-place (compare S4266's correct DIMASUKKAN_KE_DALAM usage).

- **S4336**  current: `tirtha pangentas | ADALAH | tirtha yang terpenting dalam upacara pengabenan`
  fix (or ADD): `pengabenan (tanpa tirtha pangentas) | DIANGGAP | belum dilaksanakan`
  why: drops the causal justification ("karena tanpa tirtha pangentas maka pengabenan itu dianggap belum dilaksanakan") — arguably the more important claim.

- **S4339 [0]**  current: `tirtha pangentas | ADALAH | lambang penunjuk jalan`
  fix: `tirtha pangentas | ADALAH | lambang penunjuk jalan bagi roh/atman untuk kembali ke asalnya (brahman/alam swah loka) sebagai tujuan terakhir`
  why: N1 truncation — drops the entire "bagi roh atau atman untuk kembali..." purpose clause, which is the actual philosophical claim.

## DROP  (triple should be removed)

- **S3836 [0]**  `bale-bale dipan | DIPAKAI_UNTUK | dipan`
  why: circular/nonsense — the subject already contains "dipan"; saying it's "used for dipan" is self-referential and contributes nothing (see FIX on [1] for the real content).

- **S4062 [3]**  `tirtha | DIPAKAI_UNTUK | lainnya`
  why: vacuous — "yang lainnya" ("and others") is not a real referent; this triple encodes nothing.

- **S4273 [1]**  `padang lepas | DIMASUKAN | sarana-sarana yang lainnya`
  why: nonsense coordination bug — padang lepas doesn't act on the other sarana; both padang lepas and the other items (jijih, pripih emas, recadana, ulantaga, kalpika) are independently placed into the periuk. See ADD for the correctly-split individual triples.

## ADD  (missing triples the sentence supports)

- **S3816**  `bilahan-bilahan bambu (ante) | DIKENAL_SEBAGAI | galar`
  why: "yang disebut dengan 'galar'" is the whole point of this definitional sentence and is dropped entirely.

- **S3904**  `masyarakat setempat | MELAKUKAN | upacara mesaji (atau memunjung), ketika jenazah masih di atas pepaga/asagan`
  why: the sentence's main clause (an additional ceremony some communities perform) is missing; only a restated subordinate clause survives.

- **S4065**  `tirtha pabersihan | DIBUAT_OLEH | ida sang sulinggih` (+) `tirtha pabersihan | TIDAK_MEMAKAI | samsam (tidak seperti tirtha panglukatan)` (+) `tirtha pabersihan (periuknya) | TANPA | kalung benang dengan uang kepeng`
  why: the vague "MEMILIKI perbedaan" triple captures none of the actual differences the sentence specifies (materials, mantra, and pot decoration).

- **S4079**  `tirtha pemanah | DIBUAT_SAAT | upacara "pengaskaran"` (+) `tirtha-tirtha lain | DIBUAT_OLEH | ida sang sulinggih (langsung)`
  why: the sentence's actual point of comparison (how/when each is made) is dropped; only the bare "berbeda dengan" survives.

- **S4090**  `air (dari tanah yang dipanah arjuna) | MENGENAI | bibir rsi bisma`
  why: the myth's actual payoff (water reaches the dying Bisma's lips) is entirely missing.

- **S4105 / S4110**  `sarana dan prasarana (upacara pemujaan) | BERUPA | pras, ajuman, daksina, suci, rayunan, (kadang-kadang) pajegan`
  why: both sentences drop this 6-item list wholesale (not just truncate it) — the "berupa X, Y, Z" list-introducing shape isn't reached by whatever conjunct-walk logic handles TERDIRI_DARI-governed lists (which work well elsewhere in this corpus, e.g. S4109 below).

- **S4109**  *(no ADD needed — confirmed clean)*: `tirtha kahyangan tiga DIMOHON_DARI pura desa/puseh/dalem/mrajapti` — all 4 coordinate members captured; cited here as a positive N10 control alongside S4103 (2/2 members captured).

- **S4112**  `pura kahyangan tiga (tempat pemujaan pencipta) | BERFUNGSI_SEBAGAI | utpeti, sthiti, dan pralina`
  why: the Trimurti-function triad (creation/preservation/dissolution) is a 3-item coordinate list dropped entirely — same "sebagai X, Y dan Z" gap as S4105/S4110.

- **S4128**  `upacara pengabenan | ADALAH | upacara penyucian roh/atman (purusa) orang yang telah meninggal, agar terlepas dari ikatan panca mahabhuta, menuju alam dewa (swah loka)`
  why: the sentence's second independent clause (after "sedangkan") is completely unextracted.

- **S4175**  `brahman | DITEMPATKAN | diri (sendiri)` (+) `upacara mapulang lingga | BERARTI | "ngelinggihang lingga" (dalam diri)`
  why: "tuhan atau brahman" is a 2-item coordinate subject; only "tuhan" survives (brahman dropped — N10 gap). Separately, the ceremony-name definition in the sentence's first clause is entirely missing.

- **S4212**  `abu abu kekototan (kekotoran) | MUSNAH | [melalui ritual amrethi karana]` (+) `amrethi karana | DILAKUKAN_DENGAN | mengucurkan tirtha amertha dalam diri`
  why: recovers the actually-stated fact (impurity vanishes) that the wrong-subject FIX above removes, plus the ritual method itself.

- **S4266**  `pramakusa | DIMANTRAI | (sebelum dimasukkan ke dalam priuk)`
  why: the mantra-blessing step before insertion is dropped.

- **S4273**  `jijih (biji padi) | DIMASUKKAN_KE_DALAM | periuk` (+) `pripih emas | DIMASUKKAN_KE_DALAM | periuk` (+) `recadana | DIMASUKKAN_KE_DALAM | periuk` (+) `ulantaga | DIMASUKKAN_KE_DALAM | periuk` (+) `sarana-sarana tersebut | DIMANTRAI_OLEH | ida sang sulinggih (sebelum dimasukkan)`
  why: of a 5-item coordinate list (jijih, pripih emas, recadana, ulantaga, kalpika) only the syntactically-closest item (kalpika) got its own clean triple; the other four collapsed into the nonsense DROP above. The final mantra-blessing clause is also entirely missing.

- **S4338**  `tirtha pangentas | MENGANGKAT_KEDUDUKAN | roh (dari preta menjadi pitara)` (+) `roh (pitara) | MEMASUKI | alam bwah loka (sebagai tumpuan menuju alam swah loka)`
  why: the sentence's entire doctrinal payload (the tirtha elevates the spirit's status and enables its cosmological ascent) is dropped; only the opening "ADALAH alat sangaskara" survives.

## NOTE  (borderline / systemic observation, no single fix)

- **N1 — copula/generic-noun defining-clause truncation — verdict: PARTIAL, with a clean split by shape.** Scorecard against the originally-flagged sentences: **FIXED** — S4077, S4086, S4126 (all "tirtha X ADALAH tirtha yang..." shape; the full relative clause is now retained, even if unwieldy as one long literal). **STILL BROKEN** — S3586 (chunk 7), S4106, S4111, S4128, S4170 (all "X MEMILIKI fungsi/hubungan ... sebagai/dengan Y" shape; truncates right after the bare head noun "fungsi"/"hubungan"). New instances of the still-broken MEMILIKI-pattern found beyond the flagged list: **S4087**. Net: the fix appears to have specifically patched the ADALAH-copula shape but not the MEMILIKI-fungsi/hubungan shape — exactly the gap the task description anticipated. A further, distinct gap: BERFUNGSI_SEBAGAI clauses that chain a "sehingga X" consequence clause off the main verb (a sibling advcl, not embedded in the object NP) still get dropped even when the fix otherwise holds for that sentence's core object phrase — compare broken **S4074** against fully-retained **S4116** and **S4167**/**S4171** (all ADALAH-shape, fully retained).

- **N10 — coordinate list capture — verdict: MIXED.** Large, simple coordinate NPs governed directly by one verb still work well: S4109 (pura desa/puseh/dalem/mrajapti, 4/4) and S4103 (merajan kawitan/pusat, 2/2). But two sub-patterns still lose members: (1) short "X atau Y" 2-item lists sometimes still drop the second member — **S3836** ("dapur" dropped), **S3845** ("merajan" dropped), **S4175** ("brahman" dropped as a coordinate subject); (2) lists introduced several dependency-hops below the main verb via "berupa X, Y, Z" or "sebagai X, Y dan Z" are dropped **wholesale**, not just truncated — **S4105/S4110** (6-item sarana list), **S4112** (3-item utpeti/sthiti/pralina list), **S4273** (5-item sarana list, only the syntactically-closest conjunct survived).

- **S13 — attribution/citation-adjunct suppression — verdict: HOLDING, no leak found.** Checked candidate citation contexts (S4087's itihasa/Bisma Parwa/Mahabharata reference, S4065's priest-authorship discussion) — none leaked through as spurious relation objects.

- **N4 — kawangen placement + contents split — verdict: not re-triggered in this chunk** (no new "di X, diisi sebuah Y yang berisi Z" instances found), but the duplicate passage S4035 (= chunk 7's S3783) confirms the same dropped "hingga ke kaki jenazah" qualifier and the entirely-missing priuk-breaking/discarding fact recur wherever this passage appears in the corpus.

- **N7 — section-heading noun captured as subject of following clause — verdict: not clearly triggered in this chunk.** No instance of the classic heading-noun-grabs-unrelated-clause bug was found; the closest analog (S3836's "cawan," heading) didn't reproduce that exact shape, though the sentence has other problems (see FIX/DROP above).

- **N11 — Panca Maha Bhuta closing verse manual overrides — verdict: LANDED, clean.** S4300 (`ganda BERASAL_DARI pretiwi` + `ganda KEMBALI_KE pretiwi`), S4301 (`rasa BERASAL_DARI apah`, correctly with **no** KEMBALI_KE since this sentence has no "mulih maring" return-clause), S4303 (`rupa BERASAL_DARI teja` + `rupa KEMBALI_KE teja`), S4304 (`ambekan BERASAL_DARI bayu` + `ambekan KEMBALI_KE bayu`), S4305 (`sabda BERASAL_DARI akasa` + `sabda KEMBALI_KE akasa`) are all correct, complete, and correctly omit KEMBALI_KE exactly where the source text lacks a return-clause. No errors found — this fix is fully holding.

## Chunk stats
FIX: 30   DROP: 3   ADD: 15   sentences reviewed: 60

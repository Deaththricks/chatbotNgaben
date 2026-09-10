# Chunk 6 audit (S2635..S3154)

## FIX  (triple is salvageable — give the corrected triple)

- **S2635 [0]**  current: `tarpana | ADALAH | klimaks upacara sederhana`
  fix: `tarpana dan muspa | ADALAH | klimaks dalam upacara sederhana ini`
  why: coordinate subject "dan muspa" dropped entirely — N10 violation on a 2-item list.

- **S2642 [0]**  current: `sekah kangsen | SETELAH | pamralina`
  fix: `sekah kangsen | DIBONGKAR_SETELAH | pamralina`
  why: "SETELAH" alone is a temporal marker, not a predicate; the real action "dibongkar" (is dismantled) was dropped entirely.

- **S2644 [0]**  current: `abu daun | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu daun (yang dinilai selaku bekas-bekas stulasarira mendiang) | DIMASUKKAN_KE_DALAM | klungah nyuh gading (yang dibentuk menjadi suku tunggal)`
  why: both subject and object drop their defining relative clauses.

- **S2651 [0]**  current: `atma wedana | DITUJUKAN_UNTUK | mendiang`
  fix: `atma wedana | DITUJUKAN_UNTUK | mendiang (baru dapat diadakan setelah mungkin lima atau sepuluh tahun kemudian)`
  why: drops the significant temporal constraint (this ceremony often can't be held until 5-10 years after death).

- **S2667 [0]**  current: `payadnyan | ADALAH | bangunan pokok`
  fix: `payadnyan | ADALAH | bangunan pokok pada arena ini`
  why: drops the locative "pada arena ini".

- **S2672 [0]**  current: `payadnyan | ADALAH | bangunan`
  fix: `payadnyan | ADALAH | bangunan yang paling rendah`
  why: N1-adjacent — truncates to a bare generic noun, dropping the defining relative clause (the lowest of the buildings).

- **S2748 [0]/[1]/[2]**  — no fix needed, correct. See N6 note below (this sentence is a regression-check target and is HOLDING).

- **S2752 [0]**  current: `mendiang | MENGHASILKAN | wujud sekah`
  fix: `mendiang | LAHIR_DALAM_WUJUD | sekah`
  why: wrong relation label — "lahir dalam wujud X" (is reborn in the form of X) mislabeled as MENGHASILKAN (produces X), reversing the sense; mendiang doesn't produce the sekah, mendiang becomes/takes the sekah form.

- **S2758 [1]**  current: `suksma sarira | ADALAH | tanpa berbadan sama sekali atau hanya "atma tattwatma"...`
  fix: `mendiang | BERUBAH_DARI_SUKSMA_SARIRA_MENJADI | tanpa berbadan sama sekali atau "atma tattwatma"`
  why: wrong subject — "dari suksma sarira menjadi X" means suksma sarira *changes into* X; it does not equal X. The current triple falsely equates the starting state with the ending state of a transformation.

- **S2762 [2]**  current: `mendiang | DIPEROLEH_DARI | pendeta jalan`
  fix: `mendiang | MEMPEROLEH_DARI | pendeta` (+ `upanisad | TENTANG | jalan yang harus ditempuh`)
  why: current label reverses agency (implies mendiang is obtained-from the priest) and the object nonsensically fuses two unrelated nouns ("pendeta" + "jalan") into a fake compound.

- **S2768 [0]**  current: `sangge | ADALAH | dia`
  fix: `sangge | ADALAH | "sang ngae" diri kita`
  why: object truncated to a meaningless bare pronoun "dia"; the actual predicate nominal ("the maker of our self" — the folk-etymology claim the sentence is making) was dropped.

- **S2777 [0]**  current: `bhatara | DITUJUKAN_UNTUK | utpeti`
  fix: `bhatara | DIPERSILAKAN_UNTUK | utpeti (masuk dan menghuni)`
  why: mislabeled — bhatara is invited/welcomed to *perform* utpeti (enter and dwell), not "directed for the purpose of" utpeti.

- **S2777 [1]**  current: `utpeti | ADALAH | masuk`
  fix: `utpeti | ADALAH | masuk dan menghuni`
  why: drops the second coordinate verb "dan menghuni" (and inhabit).

- **S2780 [0]**  current: `sanggar surya baligia | MEMILIKI | ruang`
  fix: `sanggar surya baligia | MEMILIKI | tiga buah ruang`
  why: drops the quantity "tiga buah" (three).

- **S2787** — correct, no fix needed.

- **S2794 [0]**  current: `sekah | BERASAL_DARI | pawedan`
  fix: `sekah | DITURUNKAN_DARI | pawedan`
  why: "diturunkan" (brought/carried down) mislabeled as BERASAL_DARI (originates from), losing the physical-relocation sense. Note: [1] `sangge JENIS_DARI sekah` is correct — see N6 note below.

- **S2803 [0]**  current: `pawedan samping tempat ngajum | ADALAH | tempat sulinggih`
  fix: `pawedan | ADALAH | tempat sang sulinggih dalam memuja`
  why: subject wrongly fuses an adjunct clause ("di samping sebagai tempat ngajum") into the entity name; that's a separate fact (see ADD).

- **S2803 [1]**  current: `tempat sulinggih | DIPERSEMBAHKAN_KEPADA | upacara atma wedana`
  fix: `tempat sulinggih (dalam memuja) | DIGUNAKAN_UNTUK | segenap upacara atma wedana ini`
  why: DIPERSEMBAHKAN_KEPADA (offered to) doesn't fit a location; the sense is "used for/in service of" the ceremony.

- **S2810 [0]**  current: `pawedan tempat | LAINNYA | shiwa`
  fix: `pawedan (tempat memuja) | MERUPAKAN | "shiwa (dewa) loka"`
  why: nonsense catch-all label LAINNYA; the real predicate ("religiously constitutes Shiwaloka") is the sentence's central claim.

- **S2812 [1]**  current: `pitra | ADALAH | atma`
  fix: `pitra | ADALAH | atma yang masih bersuksmasarira`
  why: drops the defining relative clause distinguishing "pitra" from a plain "atma" (still possessing a subtle body).

- **S2819 [0]**  current: `payadnyan | ADALAH | sekadar bangunan darurat buatan manusia`
  fix: `payadnyan | ADALAH | sekadar bangunan darurat buatan manusia di mercapada ini`
  why: minor — drops the locative "di mercapada ini" (in this mortal realm).

- **S2824 [0]**  current: `sekah | DIMASUKKAN_KE_DALAM | pintu belakang`
  fix: `sekah | DIMASUKKAN_MELALUI | pintu belakang`
  why: "melalui" (through/via) mislabeled as "ke dalam" (into) — the sekah passes *through* the back door, not into it.

- **S2832 [0]**  current: `sekah | MEMBELAKANGI | pendeta`
  fix: `sekah | MEMBELAKANGI | pendeta yang ada di pawedannya (jika masuk melalui jalan depan)`
  why: drops the defining relative clause on the object and the conditional framing.

- **S2843 [0]**  current: `sulinggih | DIPERSEMBAHKAN_KEPADA | santapan istimewa`
  fix: `santapan istimewa | DIHATURKAN_KEPADA | sulinggih, tukang banten, dan tamu terhormat/khusus lainnya`
  why: reversed direction — the food is what's offered *to* the priest/guests, not the priest offered *to* the food. Also restores the missing coordinate recipients (N10 violation: only "sulinggih" of a 4-member list was kept). See N3 regression note below.

- **S2854 [1]**  current: `pitra mendiang | MENYAKSIKAN | anak cucu`
  fix: `pitra mendiang | MENYAKSIKAN | anak cucu (nya) melakukan upacara manusa yadnya tersebut`
  why: drops the embedded clause describing *what* is witnessed (performing the ceremony), turning a specific witnessed-event into a vague "sees grandchildren".

- **S2894 [0]**  current: `pralina | DILAKUKAN_DENGAN | upacara saji tarpana`
  fix: `pralina | KALAH_MERIAH_DIBANDING | upacara saji tarpana`
  why: "kalah dengan" means "loses to/is less grand than" (a comparison), mislabeled as DILAKUKAN_DENGAN (performed together with) — reverses/erases the comparative meaning.

- **S2914 [0]**  current: `suksma sarira | ADALAH | materi`
  fix: `suksma sarira | ADALAH | materi (walaupun sangat halus)`
  why: drops the concessive qualifier — an important philosophical nuance (it IS matter, even though extremely subtle).

- **S2923 [0]**  current: `mamukur | DILINDUNGI_DENGAN | upaya penyucian wilayah`
  fix: `mamukur dan upacara sebangsanya | DILINDUNGI_DENGAN | upaya penyucian wilayah yang ketat dengan berbagai pantangannya`
  why: drops both the coordinate subject ("dan upacara sebangsanya") and the defining relative clause on the object.

- **S2948 [0]**  current: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu (yang sudah lumat) | DIMASUKKAN_KE_DALAM | klungah nyuh gading yang "disukutunggalkan"`
  why: both subject and object drop defining relative clauses.

- **S2954 [0]**  current: `atma pitara | MENUJU | dewaloka`
  fix: `atma pitara | DIMOHONKAN_AGAR_MENUJU | dewaloka`
  why: minor — drops the petitionary framing ("dimohonkan agar dapat" = is prayed/petitioned so that it may), turning a hoped-for outcome into a stated fact.

- **S2969 [0]**  current: `ngajar-ajar | BERMAKNA | upacara pernyataan parama suksmaning idep`
  fix: `ngajar-ajar | BERMAKNA | upacara pernyataan parama suksmaning idep, alias ucapan terima kasih dari pihak sang mayadnya kepada para penuntun (para ajar) yang telah memberikan jasa-jasanya`
  why: drops the "alias" gloss clause that translates the fancy term into plain language — an N1-style continuation.

- **S2986 [1]**  current: `pitra | MENGHASILKAN | dua buah daksina tapakan`
  fix: `pitra | MENERIMA | dua buah daksina tapakan (dibuat untuknya)`
  why: benefactive-passive inversion — "dibuat...bagi-nya" means the offerings are made FOR the pitra (recipient), not that pitra produces them. See N3 regression note below.

- **S2986 [2]/[3]**  current: `pitra | DITUJUKAN_UNTUK | bhatara` / `bhatari`
  fix: `daksina tapakan (satu) | DITUJUKAN_UNTUK | bhatara` / `daksina tapakan (satu) | DITUJUKAN_UNTUK | bhatari`
  why: wrong subject — "masing-masing untuk bhatara dan bhatari" describes which *offering* is for which deity-ancestor, not that pitra itself is directed at them.

- **S2988 [0]**  current: `patileman pitra | MENINGKAT | kedudukan`
  fix: `pitra | MENINGKAT_KEDUDUKAN_MENJADI | bhatara atau bhatari (sejak selesainya patileman)`
  why: subject wrongly fuses "patileman" (a temporal adjunct, "since the completion of...") into the entity name, and the object drops the crucial destination status "menjadi bhatara atau bhatari" — the sentence's entire point (the ancestor is elevated to deity status).

- **S3001 [0]**  current: `punia | ADALAH | <45-word verbatim run-on>`
  fix (split): `punia | ADALAH | perwujudan nyata dari pernyataan parama suksma lahir batin (purusa-pradana)`; `punia | LAHIR_ATAS | jasa tuntunan yang telah dianugrahkan oleh beliau`; `patileman | DAPAT_SELESAI_SECARA | tuntas (berkat punia)`
  why: dumps the whole sentence as one undifferentiated literal object; should be decomposed into atomic sub-triples, same defect class as S2604 in chunk 5.

- **S3004 [1]**  current: `perwujudan sredaning cita | ADALAH | wujud ketulus-ikhlasan hati pihak dari ketulus-ikhlasan hati pihak yang bersangkutan`
  fix: `perwujudan sredaning cita | ADALAH | wujud dari ketulus-ikhlasan hati pihak yang bersangkutan`
  why: object contains a duplicated phrase fragment ("ketulus-ikhlasan hati pihak" repeated) — a decomposition artifact.

- **S3063 [0]**  current: `jenazah | BERASAL_DARI | kotoran-kotoran`
  fix: `jenazah | DIBERSIHKAN_DARI | kotoran-kotoran (yang telah lama berada pada badan orang yang meninggal)`
  why: major meaning-reversal — "dibersihkan dari X" means X is *removed from* the corpse; BERASAL_DARI wrongly implies the corpse originates from/is made of the dirt.

- **S3080 [0]**  current: `jenazah | DITARUHKAN | punjung`
  fix: `punjung (makanan kecil) | DITARUHKAN_DI_SAMPING | jenazah`
  why: N3 — "jenazah" is a locative reference point ("beside the corpse"), not the patient of "ditaruhkan"; the parse mistakenly tagged it nsubj:pass, and extraction inherited that error, producing a triple that backwards implies the corpse is placed as a food offering. See regression note below.

- **S3110 [1]**  current: `daun intaran | DILETAKKAN_DI | kedua alis orang`
  fix: `daun intaran | DILETAKKAN_DI | kedua alis orang yang meninggal, ketika upacara mabersih mati (ngelelet)`
  why: drops the defining relative clause and the ceremony-timing context.

- **S3122 [0]/[1]** — acceptable as-is (size/count descriptors), no fix needed beyond ADD below for [2].

- **S3133 [0]**  current: `paes gedubang | DILETAKKAN_DI | atas takir bersama`
  fix: `paes gedubang | DILETAKKAN_DI | atas takir`
  why: stray fragment "bersama" glued onto the location; "bersama dengan..." is a separate comitative clause (see [1]).

- **S3133 [1]**  current: `paes gedubang | DILETAKKAN_DENGAN | secarik kain hitam`
  fix: `paes gedubang | DILETAKKAN_DENGAN | secarik kain hitam yang nanti akan digunakan untuk menutup kelamin (angkeb sarira)`
  why: drops the defining purpose clause for the cloth.

- **S3150 [0]**  current: `sekar ura | DILAKUKAN_DI | persimpangan jalan menuju`
  fix: `sekar ura | DITABURKAN_DI | setiap persimpangan jalan menuju setra`
  why: generic DILAKUKAN_DI replaces the specific verb "ditaburkan" (scattered/sprinkled); object also truncated, dropping the destination "ke setra" and leaving a dangling "jalan menuju".

- **S3153 [0]**  current: `sisig | TERBUAT_DARI | arang pembakaran jaja uli`
  fix: `sisig | TERBUAT_DARI | arang pembakaran jaja uli atau jaja gina`
  why: drops the coordinate alternative "atau jaja gina" — missing coordinate member.

- **S3154 [0]**  current: `pecahan kaca | DILETAKKAN_DI | atas takir`
  fix: `pecahan kaca dan pecahan besi baja | DILETAKKAN_DI | atas takir`
  why: drops the coordinate subject "dan pecahan besi baja" entirely — N10 violation.

## DROP  (triple should be removed)

- **S2750 [0]/[1]/[2]**  `pitra mendiang | BERPERAN_SEBAGAI | sarana` / `sarana | ADALAH | sulinggih pujastawa` / `pitra mendiang | BERPERAN_SEBAGAI | satu sajen sederhana`
  why: sentence is heavily garbled/run-on ("dengan satu sajen sederhana selaku sarananya, sang sulinggih dengan pujastawa dan tirthanya, pitra mendiang dipersilakan masuk..."). "selaku sarananya" grammatically describes the *offering* (sajen) as a medium, not pitra mendiang's role; parser misattachment drags the top subject into these relations. Too tangled to safely reconstruct — recommend dropping per flag.txt's precedent for segmentation-mangled sentences (cf. #191). See ADD for the one recoverable fact.

- **S2947 [0]**  `abu (SARANA_RITUAL) | DIUYEG | selumat-lumat (None)`
  why: "selumat-lumatnya" is a manner adverb ("as finely as possible"), not an entity — redundant with/subsumed by [1]'s more meaningful location object (sesenden).

- **S3110 [0]**  `daun intaran (SARANA_RITUAL) | DIPAKAI_UNTUK | lembar (None)`
  why: "lembar" is merely the counting classifier for daun (2 lembar = 2 leaves), not a distinct purpose-object — nonsense triple.

- **S3122 [2]**  `malem (SARANA_RITUAL) | DIPULUNG | ditaruh (None)`
  why: "ditaruh" (placed) is a second coordinate VERB, not a noun object — verb-as-object nonsense.

- **S3134 [3]**  `lekesan (SARANA_RITUAL) | DIISI_DENGAN | ujung atas (None)`
  why: "ujung atasnya" (its upper end) is the LOCATION where the filling happens, not a substance lekesan is filled with — duplicate/confused extraction of [2]'s location as a spurious object.

## ADD  (missing triples the sentence supports)

- **S2748**  no ADD needed — sentence fully covered; see N6 note.

- **S2752**  `mendiang (dalam wujud sekah) | DIAJAK_BERKOMUNIKASI_OLEH | keluarga`
  why: purpose clause ("agar dapat diajak berkomunikasi oleh keluarganya") entirely unextracted.

- **S2750**  `pitra mendiang | DIPERSILAKAN_MASUK_KE | (wujud/puspalingga)`
  why: the one clearly recoverable fact in this garbled sentence — pitra mendiang is invited to enter and don a form — is currently unextracted; the existing relations only capture (incorrectly) the "selaku sarana" fragment.

- **S2762**  `upanisad | TENTANG | jalan yang harus ditempuh`
  why: "tentang jalan yang harus ditempuh" (about the path that must be traveled) was fused into a nonsense compound rather than extracted as its own fact — see FIX above.

- **S2777**  `bhatara | DIPENDAK_SECARA | khusus`
  why: "dipendak (disongsong) secara khusus" (specially welcomed/received) is entirely unextracted.

- **S2803**  `pawedan | JUGA_ADALAH | tempat ngajum serta mengutpeti sekah`
  why: restores the "di samping sebagai tempat ngajum..." clause as its own triple instead of fusing it into the subject.

- **S2810**  `pawedan (tempat memuja) | BUKAN_SEKADAR | "madyapada"`
  why: the contrastive negation ("bukanlah sekadar bernilai madyapada saja") frames the sentence's central claim and is entirely unextracted.

- **S2850**  `punia (besar-kecilnya) | SEPADAN_DENGAN | jenis yadnya dan martabat sang mayadnya`
  why: the qualifying clause ("walaupun besar-kecilnya sangat relatif, sepadan dengan...") is entirely dropped.

- **S2869**  `pitara (menggunakan tirtha ening) | HINGGA_TAMPAK | bayangan nya`
  why: the result clause ("hingga tampaklah bayangannya") is unextracted.

- **S2951**  `suku tunggal abu (diarak mapradaksina) | MELAMBANGKAN | diresapkannya sinar suci hyang widhi`; `abu | BERUBAH_DARI | bekas benda badan linggasarira`; `abu | MENJADI | mahabutha yang suci`
  why: the sentence's core transformation claim (the ash's status/sanctity rising, from a bodily remnant into the sacred five elements) is entirely missing; only the "is paraded" fact was captured.

- **S2977**  no ADD needed — reasonably complete.

- **S3007**  `pandita (selaku pemuka agama) | MEMAKLUMI | ketentuan punia yang demikian itu`
  why: the sentence's main predicate (the priest thoroughly understands such punia rules) is entirely unextracted; only the appositive was captured.

- **S3063**  `jenazah | DIBERSIHKAN_DARI | hal-hal yang lain`
  why: missing second coordinate ("maupun dari hal-hal yang lain") — a 2-item list, one dropped.

- **S3078**  `jenazah (ditutup kain putih) | BERTUJUAN | agar tidak kelihatan sama sekali`
  why: purpose clause unextracted.

- **S3080**  `punjung | BERISI | nasi dengan lauknya`; `punjung | BERISI | kopi`; `punjung | BERISI | rokok`
  why: N10-relevant — a 3-item coordinate list ("nasi dengan lauknya, kopi dan rokok") describing the food offering's contents is entirely unextracted.

- **S3110**  `daun intaran | DIGUNAKAN_SEBANYAK | 2 lembar`
  why: replaces the nonsense DROP above with a properly-framed quantity fact.

- **S3118**  `daun dapdap (yang dihaluskan) | BERGUNA_SEBAGAI | sampo pencuci rambut (keramas) bagi jenazah`; `daun dapdap | DIGUNAKAN_SAAT | upacara nyiramang layon`
  why: the sentence's main point (this is a corpse-shampoo, used during the nyiramang layon rite) is completely unextracted — only two minor preparation steps were captured.

- **S3122**  `malem (setelah dipulung, minimal dua buah) | DITARUH_DI | atas takir`; `malem (di atas takir) | DIGUNAKAN_UNTUK | ditaruh pada kedua lubang kuping jenazah ketika upacara melelet`
  why: restores the second coordinate action (placed on the takir) as a proper relation, and the sentence's actual purpose (placed in the corpse's ear-holes during melelet) which is entirely unextracted.

- **S3141**  `kawangen | DIISI | 11 kepeng (ditaruh pada setiap persendian/buku-buku)`; `kawangen | DIISI | 25 kepeng untuk pebaktian jenazah (ditaruh di dada, seolah-olah dipegang oleh tangan jenazah)`
  why: two specific quantity/placement variants of the coin-filling are described in detail and entirely missing.

- **S3142**  `kwangen (setiap gulungan) | DIISI_DENGAN | uang kepeng`; `kwangen | DIISI_DENGAN | bawang putih sebagai lambang kuku (di ujungnya)`; `kwangen (dengan bawang putih ini) | DITARUH_DI | tiap-tiap jari tangan dan kaki jenazah`
  why: major under-extraction — the sentence's central purpose (placement at fingers/toes, garlic symbolizing nails) is entirely missing.

- **S3153**  `sisig (di atas takir ini) | DIGUNAKAN_UNTUK | gosok gigi jenazah`
  why: the item's entire purpose (used to brush the corpse's teeth) is unextracted.

- **S3154**  `pecahan kaca | DITARUH_DI | kedua mata (jenazah)`; `pecahan besi baja | DITARUH_DI | gigi jenazah`
  why: major under-extraction — the specific placement of each material (glass at the eyes, steel at the teeth) is the sentence's main content and entirely missing.

## NOTE  (borderline / systemic observation, no single fix)

- **N1 regression check — S2649**: HOLDING (positive). `ngangsen ADALAH upacara untuk bertangguh` correctly retains the "untuk" purpose continuation.

- **N1 regression check — S2872**: NOT HOLDING. `manah tirtha ening ini ADALAH pawai` truncates the object without its defining relative clause "yang bernilai seni" (of artistic value) and drops the "lebih-lebih yang untuk pamukuran" (especially the one for pamukuran) continuation entirely. This is the same N1 failure pattern iteration 1 flagged for the related S3155 (out of range for this chunk) — confirmed still present at S2872. Translation note: "manah" here is glossed loosely as "the practice/contemplation of [using] clear holy water" — the term is unclear/possibly OCR-affected and should be double-checked against source.
  fix: `manah tirtha ening ini | ADALAH | suatu pawai yang bernilai seni, lebih-lebih yang untuk pamukuran`

- **N1-adjacent (outside required list)**: S2672, S2812[1], S2969, S2954 all show the same "generic-noun object truncated, defining clause dropped" pattern recurring inconsistently; S2649 and S2904 show it working. Consistent with chunk 5's observation that the fix is applied to specific patterns rather than generalized.

- **N10 regression check — S2635/S2780/S2843/S2986/S3063/S3153/S3154**: recurring 2-to-4 member coordinate-list truncations found beyond the specifically-flagged iteration-1 examples (see FIX/ADD above for each). N10 holds for short, flat "A dan/atau B" lists (S2645, S2686, S2777[1] once fixed, S2968) but still drops members when the list is longer, appears inside a relative/parenthetical clause, or spans multiple sentence positions (subject-side lists especially, e.g. S2843, S3154).

- **N6 regression check — S2748 (REQUIRED)**: HOLDING / FIXED. Relation [3] "sekah sangge JENIS_DARI sekah" correctly places the specific member (sekah sangge) as subject and the general category (sekah) as object — the correct direction, matching the N6 fix intent. Iteration 1 flagged this exact sentence for having subject/object reversed; confirmed fixed.

- **N6 regression check — S2794 (REQUIRED)**: HOLDING / FIXED. Relation [1] "sangge JENIS_DARI sekah" is likewise correctly directed (member → category). Both of iteration 1's originally-flagged N6 cases (S2748, S2794) are confirmed fixed in this chunk. (Relation [0] in this same sentence has an unrelated mislabeling issue — see FIX above — but it is not an N6/direction problem.)

- **N3 regression check — S2843 (REQUIRED)**: NOT FIXED. "sulinggih DIPERSEMBAHKAN_KEPADA santapan istimewa" reads backward — real-world direction is food → priest, not priest → food. This is the benefactive-passive-style inversion N3 targets; confirmed still present. See FIX above.

- **N3 regression check — S3080 (REQUIRED)**: NOT FIXED, and the clearest example of the pattern in this chunk. "jenazah DITARUHKAN punjung" backwards implies the corpse is placed as a food offering; the underlying dependency parse mistags the locative "di samping jenazah" as nsubj:pass, and the extraction rule inherited that parse error verbatim. Confirmed present, unfixed. See FIX above.

- **N3 regression check — S2794 (REQUIRED, but re-examined)**: On close inspection, relation [0] of S2794 (sekah BERASAL_DARI/DITURUNKAN_DARI pawedan) is actually NOT an instance of benefactive-recipient-in-subject-position — "sekah" is correctly the syntactic patient/subject of the passive "diturunkan", and "pawedan" is correctly a source-location oblique. The only defect here is a relation-label mismatch (see FIX above), not an N3-style inversion. Flagging this so the team can confirm whether S2794 was miscategorized in the check list, or whether a different sub-clause of that sentence was intended.

- **N3 regression check — S2885 (REQUIRED)**: PARTIAL. The core giving relations (sulinggih MEMBERIKAN panjaya-jaya / ayaban sesayut) are correctly active-voice with sulinggih as true agent — no inversion there. However relation [2] ("sulinggih DITUJUKAN_UNTUK putra-putri") misdirects the benefactive "kepada putra-putri" clause by making the giver himself the subject of a "directed-for" relation, producing a confusing near-duplicate that echoes the same recipient/direction confusion N3 targets, though it is not a strict passive-inversion case. Recommend treating as a related but distinct residual defect (see FIX above).

- **N3 regression check — S2986 (REQUIRED)**: NOT FIXED. Relation [1] ("pitra MENGHASILKAN dua buah daksina tapakan") inverts a benefactive passive ("dibuat...bagi-nya" = made FOR them) into an active-production claim, wrongly making the recipient (pitra) the agent/producer. Confirmed present, matching iteration 1's flagged pattern. See FIX above.

- **N3-adjacent (outside required list)**: S2612 (chunk 5) and S2752 show the same benefactive/transformation-direction confusion family, suggesting N3 is a broad, still-entirely-open failure class, not isolated to the five named examples.

- **S2777**: the earlier clause "bhatara yang dimohon selaku 'lingga' (demikian namanya)" (the deity invoked as "lingga") is only implicitly present via context; acceptable as-is given the sentence's density, but flagging for awareness.

- **S2780 [1]**: "akibat lanjutan" (subsequent consequences) is a vague abstract noun without further specification in the source text — borderline meaningless as an isolated triple; consider dropping in a future pass if no clearer referent can be established.

## Chunk stats
FIX: 39   DROP: 5   ADD: 21   sentences reviewed: 61

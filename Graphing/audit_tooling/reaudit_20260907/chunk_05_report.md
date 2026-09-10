# Chunk 5 audit (S2212..S2686)

Convergence re-audit. flag.txt's continuation pass already covers this whole range
(S2212-S2686). Most `manual_override` triples in this chunk landed **exactly** as
flag.txt specified and are now clean (see NOTE). The findings below are the
genuinely-still-broken cases: mostly `dependency_rule` triples the override pass
never reached, plus a couple of overrides that still carry a defect.

## FIX  (triple is salvageable — give the corrected triple)

- **S2234 [0]**  current: `jenazah seseorang (yang telah tertanam-titip) | DIBAKAR | setra lain`
  fix: `jenazah seseorang (yang telah tertanam-titip) | DIABEN_DI | setra lain`
  why: Raw (line 1737): "...jenazah seseorang (yang telah tertanam-titip) pada sebuah setra, **diaben di setra lain**." The verb is *diaben* (cremated) and *setra lain* is a location. Bare `DIBAKAR` with a place object reads as if the setra is what's burned; the locative `_DI` is missing. (`tertanam-titip` = provisionally buried/entrusted at one graveyard.)

- **S2336 [3]**  current: `kajang | DIBERI | 30 meter`
  fix: fold the length into the cloth triple — `sambungan kain putih | SEPANJANG | dua atau 30 meter`  (or DROP [3])
  why: Raw (line 1818): "...diberilah sambungan ('lancingan') kain putih **dua atau 30 meter** lagi." "30 meter" alone is a stranded measurement fragment, not a distinct thing given to the kajang; it is the length of the kain-putih extension already captured in [2]. flag.txt /115.

- **S2364 [0]**  current: `bade | DILETAKKAN_DI | teben lembu`
  fix: `bade | DILETAKKAN_DI | sebelah hilir atau teben lembu`
  why: Raw (line 1830): "...Bade diletakkan di **sebelah hilir atau teben** Sang Lembu." Disjunct member "sebelah hilir" (downstream side) dropped. flag.txt /117 — not applied (still `dependency_rule`).

- **S2374 [0]**  current: `prasawya | ADALAH | lambang gerak peningkatan diri`
  fix: `prasawya | ADALAH | lambang gerak peningkatan diri dari sesuatu, atau gerak ke atas`
  why: Raw (line 1839): "Prasawya adalah lambang gerak peningkatan diri **dari sesuatu, atau gerak ke atas**." Object truncated, dropping the "dari sesuatu" complement and the whole "atau gerak ke atas" disjunct. flag.txt /117 — not applied.

- **S2377 [0]**  current: `ngaben | MEMILIKI | tujuan pokok`
  fix: `ngaben | BERTUJUAN_POKOK | merubah jenazah atau "benda bekas" badan seseorang kembali menjadi pancamahabutha sebagaimana asalnya semula`
  why: Raw (line 1842): "Ngaben mempunyai tujuan pokok **untuk merubah jenazah atau 'benda bekas' badan seseorang, hingga kembali menjadi Pancamahabutha sebagaimana asalnya semula**." Current triple keeps only the empty head "tujuan pokok" and drops the purpose clause that IS the sentence. flag.txt /122 — not applied.

- **S2380 [1]**  current: `cara prasawya | ADALAH | berputar`
  fix: `cara prasawya | ADALAH | berputar ke kiri, berlawanan dengan putaran jarum jam`
  why: Raw (line 1842): "...berputar dengan cara prasawya (**berputar ke kiri, berlawanan dengan putaran jarum jam**)." Bare verb "berputar" as object is contentless; the parenthetical gloss is the definition. flag.txt /122 — not applied. (See also ADD below for the second missing relation on this sentence.)

- **S2535 [0]**  current: `pitara | MENGELUPASI | suksmasarira`
  fix: `pitara | MENGELUPASI | suksmasarira (yang merupakan "kulit dirinya")`
  why: TEXT: "...mengelupasi suksmasarira **yang merupakan 'kulit dirinya'**, sebagaimana halnya seekor udang yang tengah menylongsong." Gloss: the pitara sheds the subtle body (suksmasarira), which is "the skin of its self," like a moulting shrimp. The defining appositive is dropped. flag.txt /122 — not applied.

- **S2542 [0]**  current: `atma wedana | MEMILIKI | jenis`
  fix: `atma wedana | MEMILIKI | beberapa jenis`
  why: TEXT: "...atma wedana pun ada **beberapa** jenis..." Quantifier dropped (mirror of the "beberapa jenis" nuance case in flag.txt line 37). flag.txt /116 — not applied. ([1] with the "masing-masing punya nama dan ciri" ADD did land correctly.)

- **S2548 [0] & [1]**  current: `tirtha pangentas atiwa-tiwa | DIPERCIKKAN_PADA | sesosok mayat` / `... | DIPERCIKKAN_PADA | perlambang`
  fix: append the constraint to each object, e.g. `... | DIPERCIKKAN_PADA | sesosok mayat (hanya sekali saja)` / `... perlambang (hanya sekali saja)`
  why: TEXT: "...hanya boleh disiratkan **sekali saja** kepada sesosok mayat atau perlambangnya." "Only once" is a defining ritual constraint, not filler. flag.txt /116 — not applied.

- **S2555 [0]**  current: `atma wedana | ADALAH | upacara penyucian pitra`
  fix: `atma wedana | ADALAH | nama resmi upacara penyucian pitra`
  why: TEXT: "atma wedana adalah **nama resmi** upacara penyucian pitra menurut pustaka yang kita warisi." The "nama resmi" (official name) framing is the point — atma wedana is the formal/scriptural name for the rite. flag.txt /116 — not applied. (The "menurut pustaka..." attribution is correctly excluded.)

- **S2563 [0]**  current: `bhuwana alit | MEMILIKI | 11 bidang`
  fix: `bhuwana alit | MEMILIKI | 11 bidang yang mudah ditimpa suasana "sebel"`
  why: TEXT: "...bhuwana alit hanya mempunyai 11 bidang **yang mudah ditimpa suasana 'sebel'**." Defining relative clause (the 11 fields are prone to ritual impurity) dropped — that is why the number matters here. flag.txt /122 — not applied.

- **S2612 [0]**  current: `pitra | DIBUATKAN_UNTUK | perlambang`
  fix: `pitra mendiang | DIBUATKAN | perlambang (yang disebut sekah kangsen)`
  why: TEXT: "pitra mendiang, yang merupakan sasaran upacara **dibuatkan** perlambang yang disebut sekah kangsen." Benefactive passive: a symbol is made FOR the pitra. `DIBUATKAN_UNTUK` with object "perlambang" inverts it, making the symbol the beneficiary ("pitra is made for the purpose of a symbol"). Also subject should be "pitra mendiang". flag.txt /119 — the override direction is still wrong. ([1] `perlambang | DIKENAL_SEBAGAI | sekah kangsen` is fine.)

- **S2623 [1]**  current: `sekah kangsen | DISUCIKAN_DENGAN | sajen kecil dengan tirtha dan sajen kecil sebagai pengantar nya`
  fix: `sekah kangsen | DISUCIKAN_DENGAN | sajen kecil (sebagai pengantar)`
  why: TEXT: "...disucikan dengan tirtha dan sajen kecil sebagai pengantarnya." Object has a verbatim duplication artifact ("sajen kecil ... dan sajen kecil"). flag.txt /116 — not applied. ([0] `... DISUCIKAN_DENGAN tirtha` is fine.)

## DROP  (triple should be removed)

- none outright — S2336 [3] is listed under FIX with a DROP fallback.

## ADD  (missing triples the sentence supports)

- **S2323**  `bade dan lembu | MENJADI | sarana yang benar-benar "siap pakai" (hanya setelah diplaspas)`
  why: Raw (line 1806): "Hanya setelah diplaspas-lah, Bade dan lembu (termasuk segala alat penting lainnya) **merupakan sarana yang benar-benar berkeadaan 'siap pakai'** betapa mestinya." The lone current triple ([0] `bade dan lembu | TERGOLONG_BERSAMA | alat penting lainnya`) only captures the parenthetical "termasuk..." aside; the main predicate is unextracted. (*diplaspas* = ritually consecrated.)

- **S2363**  `bale pamuunan | DIHUNI | lembu`
  why: TEXT: "bale pamuunan **yang telah dihuni lembu**, dikelilingi..." The relative clause on the subject was dropped when the override was authored. flag.txt /113 for this sentence — only the main DIKELILINGI_OLEH fix landed.

- **S2380**  `bade | BERLAWANAN_DENGAN | gerak pradaksina yang dilakukan pada upacara dewa yadnya di pura`
  why: Raw (line 1842): "...serta **berlawanan pula dengan gerak pradaksina yang dilakukan pada upacara Dewa Yadnya di pura**." A whole coordinate clause (bade's prasawya rotation is the opposite of the pradaksina used in temple dewa-yadnya rites) is unextracted. flag.txt /113 — not applied.

- **S2473**  `pangabenan yang menggunakan nama pranawa | DILATARBELAKANGI_OLEH | hasrat supaya mendiang memperoleh ketenangan, kemantapan, serta kesucian`
  why: The three current triples (`mendiang | MEMPEROLEH | ketenangan / kemantapan / kesucian`) capture only the embedded wish-list and drop the sentence's actual main clause (why the name "pranawa" is used). They also over-assert — the raw is "dilatarbelakangi oleh **hasrat supaya** mendiang ... **dapat** memperoleh" (a wish, not a fact). flag.txt gave an explicit /113 ADD here that did not land.

## NOTE  (borderline / systemic observation, no single fix)

- **Convergence is good on the override pass.** The large majority of `manual_override` triples in this chunk match flag.txt's requested fixes verbatim and are clean now: S2252[2], S2256 (3-way split), S2258 (2-way split), S2262, S2269, S2340, S2387, S2406, S2419, S2448, S2455, S2483, S2485, S2502 (drop + BERTUJUAN_MENYUCIKAN split + MENJADI subject fix), S2520[1], S2527, S2566 (subject-bleed removed), S2604 (3-way split), S2624 (2-way split), S2630, S2642 (DIBONGKAR_SETELAH), S2644 (both clauses retained), S2667, S2672 (object fix + DIHIAS_PALING ADD). No re-flag on these.

- **The remaining defects are almost all `dependency_rule` triples the override pass skipped** — S2374, S2377, S2535, S2542[0], S2548, S2555, S2563, plus S2612 (`object_decomposition`/`dependency_rule`). Same clause-stripping / terseness / dropped-disjunct family flag.txt logged as /116 /117 /122 for these exact S-ids; the fixes were specified but never written. A targeted second override batch over just these ~9 sentences would close the chunk.

- **S2269 [0]** `bale pamuun (dan alat-alat upakara lainnya) | TELAH_SELESAI_SECARA | de facto` — "de facto" is adverbial, not an entity, so the triple is shape-awkward, but it is hand-authored and matches flag.txt's own /113 proposal and is faithful to "telah selesai secara de facto." Keeping as-is per clunky-but-faithful.

- **S2651 [0]** `atma wedana | DITUJUKAN_UNTUK | mendiang (baru dapat diadakan setelah mungkin lima atau sepuluh tahun kemudian)` — predicate is weak (the sentence is really "only after 5-10 years can atma wedana be held"); `DAPAT_DIADAKAN_SETELAH | lima atau sepuluh tahun` would be cleaner. The temporal constraint flag.txt /122 asked for is at least captured in the parenthetical, so this is a borderline keep.

- **S2686 [0]/[1]** `pitra mendiang | BERTAHTA | sekah` / `puspalingga` — flag.txt marked /1. Predicate would read better as `BERTAHTA_DI` / `BERSTANA_DI` (locative), but not re-flagging against the user's verdict.

## Chunk stats
FIX: 13   DROP: 0   ADD: 4   sentences reviewed: 59

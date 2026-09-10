# Chunk 6 audit (S2748..S3295)

Convergence re-audit. All 59 sentences in this chunk already carry a verdict in
flag.txt (Part 2, S2364-S3332). The great majority of the flag.txt fixes DID
land in this fresh run — the `source=manual_override` triples now match the
corrections flag.txt authored (spot-confirmed on S2752, S2758, S2762, S2794,
S2803, S2810, S2824, S2850, S2872, S2894, S2914, S2923, S2947, S2951, S2954,
S2986, S2988, S3001, S3007, S3063, S3078, S3118, S3122, S3133, S3141, S3142,
S3150, S3155, S3165, S3196, S3237, S3294, S3295). The items below are the
genuine remaining problems: flag.txt fixes that did NOT converge, plus a few
additional issues.

## FIX  (triple is salvageable — give the corrected triple)

- **S2768 [0]**  current: `sangge | ADALAH | dia`
  fix: `sangge | ADALAH | "sang ngae" diri kita`
  why: raw (line 2141) = "sangge adalah dia 'sang ngae' diri kita". Balinese
  *ngae* = membuat/mencipta, so *sang ngae diri kita* = "the maker of our self
  (body)". Object was truncated to the bare pronoun "dia" — the folk-etymology
  claim is lost. flag.txt /122, not converged.

- **S2812 [1]**  current: `pitra | ADALAH | atma`
  fix: `pitra | ADALAH | atma yang masih bersuksmasarira`
  why: raw (line 2177) = "berkedudukan sebagai Pitra (atma yang masih
  bersuksmasarira)". The relative clause is exactly what distinguishes pitra
  from a plain atma; dropping it makes the triple vacuous. flag.txt /122, not
  converged.

- **S2854 [1]**  current: `pitra mendiang | MENYAKSIKAN | anak cucu`
  fix: `pitra mendiang | MENYAKSIKAN | anak cucunya melakukan upacara manusa yadnya tersebut`
  why: the embedded clause (what is witnessed) is the content of the sentence —
  a specific rite, not just "sees grandchildren". flag.txt /122, not converged.

- **S3153 [0]**  current: `sisig | TERBUAT_DARI | arang pembakaran jaja gina uli`
  fix: `sisig | TERBUAT_DARI | arang pembakaran jaja gina`
  why: raw (line 2525) = "dibuat dari arang pembakaran jaja uli atau jaja gina"
  — two disjunct sources. [1] already correctly holds "arang pembakaran jaja
  uli"; [0] should be the other member "jaja gina" but instead fuses both words
  into a nonexistent "jaja gina uli". Additional issue (word-merge garble).

- **S2777 [1]**  current: `utpeti | ADALAH | masuk`
  fix: `utpeti | ADALAH | masuk dan menghuni`
  why: raw (line 2150) = "utpeti (masuk dan menghuni)". Second coordinate member
  of the parenthetical gloss dropped. flag.txt /117, not converged.

- **S2777 [4]**  current: `bhatara | BERPERAN_SEBAGAI | badan suksma`
  fix: `puspalingga | BERPERAN_SEBAGAI | badan suksma bhatara`
  why: raw = "...pada Puspalingga (sejenis Sangge) selaku badan suksmanya" —
  *selaku badan suksmanya* modifies Puspalingga (the puspalingga functions as
  bhatara's subtle body), not bhatara. Wrong subject. Additional issue —
  flag.txt had marked [4] fine.

- **S2777 [0]**  current: `bhatara | DITUJUKAN_UNTUK | utpeti`
  fix: `bhatara | DIPERSILAKAN_UNTUK | utpeti`
  why: raw = "dipersilakan untuk utpeti" (invited to perform utpeti), not "aimed
  at". Minor label correction. flag.txt /119, not converged.

- **S2948 [0]**  current: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu (yang sudah lumat) | DIMASUKKAN_KE_DALAM | klungah nyuh gading yang disukutunggalkan`
  why: both subject and object drop their defining relative clauses ("already
  pulverized" / the shell "that has been ritually unified"). flag.txt /122, not
  converged. Lower priority.

- **S2819 [0]**  current: `payadnyan | ADALAH | sekadar bangunan darurat buatan manusia`
  fix: `payadnyan | ADALAH | sekadar bangunan darurat buatan manusia di mercapada ini`
  why: drops the locative "di mercapada ini" (in this mortal realm). flag.txt
  /116, not converged. Minor.

- **S3004 [1]**  current: `perwujudan sredaning cita | ADALAH | wujud ketulus-ikhlasan hati pihak`
  fix: `perwujudan sredaning cita | ADALAH | wujud ketulus-ikhlasan hati pihak yang bersangkutan`
  why: the earlier verbatim-duplication bug is fixed, but "yang bersangkutan"
  (the party concerned) is still dropped, leaving "pihak" dangling. flag.txt
  /116, partially converged.

## DROP  (triple should be removed)

- **S3134 [3]**  `lekesan | DILETAKKAN_DI | ujung atas`
  why: misparse of "di ujung atasnya diisi bawang putih" — "ujung atas" is where
  the garlic is inserted, not where the lekesan is placed. Already covered by
  [2] (`lekesan DIISI_DENGAN bawang putih`). flag.txt /0, not converged.

## ADD  (missing triples the sentence supports)

- **S2969**  `ngajar-ajar | BERMAKNA | ucapan terima kasih dari pihak sang mayadnya kepada para penuntun (para ajar)`
  why: raw (line 2304) — the sentence glosses ngajar-ajar twice: "upacara
  pernyataan parama suksmaning idep" (captured in [0]) *alias* "ucapan terima
  kasih dari pihak sang mayadnya kepada para penuntun (para ajar)" (dropped).
  The second is the plain-language payload. flag.txt /122.

- **S2777**  `bhatara | DIPENDAK_SECARA | khusus`
  why: raw = "dipendak (disongsong) secara khusus" (specially welcomed/received)
  — an entire main-clause action currently unextracted. flag.txt /113.

- **S3110**  `daun intaran | DITARUH_DI | kedua alis jenazah (ketika upacara mabersih mati / ngelelet)`
  why: text = "akan ditaruh pada kedua alis orang yang meninggal ketika upacara
  mabersih mati (ngelelet)". The placement fact — the point of the sentence — is
  now entirely missing; only `DIGUNAKAN_SEBANYAK 2 lembar` survived. flag.txt
  had flagged this relation as clause-stripped ([1]); it has since disappeared
  altogether.

## NOTE  (borderline / systemic observation, no single fix)

- **S3195 [1]**  `banten pamegat | DIPAKAI_UNTUK_SEBELUM | upacara pabresihan mati`
  — fused purpose+temporal predicate label, and it drops the other half of the
  timing ("setelah upacara pabersihan hidup"). Cleaner: `banten pamegat |
  DIGUNAKAN_SEBELUM | upacara pabresihan mati`. flag.txt marked [1] fine /1, so
  low priority, but the fused-marker label shape is one of the known defect
  classes.

- **S2832 [0]**  `sekah | MEMBELAKANGI | pendeta` still drops the conditional
  frame "kalau masuk melalui jalan depan" and "yang ada di pawedannya". The
  whole point of the sentence is that entering by the front door causes this.
  flag.txt /122, not converged. Low priority (rhetorical question sentence).

- **Convergence**: this chunk converged well. ~34 of the ~40 flag.txt fixes in
  range landed cleanly. The residual misses are almost all the same class:
  defining `yang`/appositive/`alias` clauses still stripped from ADALAH/BERMAKNA
  objects (S2768, S2812, S2854, S2948, S2969, S2819, S3004, S2832) — the
  long-standing D1/N1 clause-retention gap, now down to a handful of cases here.

## Chunk stats
FIX: 10   DROP: 1   ADD: 3   sentences reviewed: 59

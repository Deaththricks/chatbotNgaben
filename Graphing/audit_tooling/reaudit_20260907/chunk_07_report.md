# Chunk 7 audit (S3296..S3862)

Convergence re-audit. 59 sentences. The earlier flag.txt pass (part 2/3, S3296-S3862) is
authoritative and its FIX/ADD recommendations have almost all been applied as
`source=manual_override` triples in this re-run. Spot-checks below confirm most sentences
have genuinely converged (S3330, S3332, S3333, S3340, S3354, S3363, S3364, S3446, S3468,
S3496, S3547, S3559, S3584, S3586, S3604, S3610, S3623, S3649, S3651, S3653, S3654, S3656,
S3694, S3720, S3733, S3734, S3742, S3747, S3749, S3753, S3755-S3758, S3760, S3783, S3791,
S3800, S3811, S3812, S3816, S3836, S3843, S3845, S3852, S3860, S3862 — all clean now).

Only genuine remaining problems are listed.

## FIX  (triple is salvageable — give the corrected triple)

- **S3355 [0]**  current: `jenazah | MEMILIKI | makna agar orang yang meninggal tersebut lebih cepat menemui brahman ( sang pencipta )`
  fix: `jenazah yang masuk melalui teben dari pepaga | BERMAKNA | agar orang yang meninggal lebih cepat menemui brahman (sang pencipta)`
  why: raw (line 2741): "Disamping itu jenazah yang masuk melalui Teben dari Pepaga, memiliki makna agar orang yang meninggal tersebut lebih cepat menemui Brahman...". `teben` = the downstream / foot-end of the platform. It is *entering via the teben* that carries the symbolic meaning; the bare subject "jenazah" drops the entire condition. `dependency_rule` extraction, never manually corrected. Also trim the stray "makna" noun from the object.

- **S3544 [0]**  current: `kawangen | MELAMBANGKAN | tanda doa restu setelah selesai upacara sembah bhakti ini ,`
  fix: `kawangen | MELAMBANGKAN | tanda doa restu`
  why: raw (line 2998): "...semua Kawangen ... dikumpulkan dan ditaruh di samping jenazah, sebagai tanda doa restu agar perjalanan roh yang meninggal tidak mendapatkan suatu halangan." The object has a stray leading temporal clause ("setelah selesai upacara sembah bhakti ini ,") fused in from the front of the sentence, and drops the purpose clause. flag.txt flagged this /115; the fix was not applied (still `dependency_rule`). See ADD for the dropped purpose.

- **S3591 [0]**  current: `anggapan | ADALAH | simbol dewi sri , yang mana nanti nya diharapkan wanita yang akan " numitis " memiliki kesuburan untuk dapat melahirkan dari dewi sri , yaitu lambang kesuburan`
  fix (split): `anggapan (ani-ani atau ketam) | ADALAH | simbol Dewi Sri`  +  `anggapan | MELAMBANGKAN | kesuburan`
  why: raw (line 3042): "Anggapan (ani-ani atau ketam) adalah simbol dari Dewi Sri, yaitu lambang kesuburan, yang mana nantinya diharapkan wanita yang akan 'numitis' memiliki kesuburan untuk dapat melahirkan." Current object is a scrambled run-on: "dari dewi sri" is duplicated / misplaced, and "yaitu lambang kesuburan" is stranded after the relative clause. `dependency_rule`, never manually fixed. flag.txt flagged /116 (the older duplication bug); the current form is a different garble, still open. See ADD for the purpose clause.

- **S3589 [0]**  current: `arit gobed | ADALAH | simbol rare angon yaitu lambang keperkasaan seorang laki-laki`
  fix (split): `arit gobed | ADALAH | simbol Rare Angon`  +  `arit gobed | MELAMBANGKAN | keperkasaan seorang laki-laki`
  why: raw (line 3042): "Arit Gobed adalah simbol dari Rare Angon yaitu lambang keperkasaan seorang laki-laki." The old "rare angon DARI rare angon" duplication is gone, but the object still fuses two distinct claims (symbol of Rare Angon / emblem of male virility). `dependency_rule`. Lower severity than S3591 but same construction family flag.txt called systemic.

- **S3728 [1]**  current: `numitis | MENYEBABKAN | badan menjadi harum`
  fix: `penggunaan wewangian | BERTUJUAN_AGAR | tubuh jenazah kelak berbau harum`
  why: raw (line 3226): "Adapun makna penggunaan wewangian adalah ... di samping tersebut tubuhnya agar kelak berbau harum." The fragrance *usage* aims for the body to smell fragrant later; reincarnation (`numitis`) is not the cause. Wrong subject + invented predicate. (Compare [0], which was correctly fixed to `penggunaan wewangian | BERTUJUAN_AGAR | ...`.)

- **S3339 [2]**  current: `tempat persemayaman jenazah | DITEMPATKAN_DI | bale semanggen (rumah adat Bali)`
  fix: `tempat persemayaman jenazah | DITEMPATKAN_DI | bale semanggen`  (drop the "(rumah adat Bali)" gloss, or change to "(pada rumah bergaya adat Bali)")
  why: raw (line 2727): "bagi umat Hindu di Bali yang memiliki tatanan rumah stil Bali, tempat persemayaman jenazah ditempatkan di Bale Semanggen." Bale Semanggen is a specific pavilion, not "rumah adat Bali" (a Balinese traditional house). The parenthetical mislabels the entity. Minor.

## DROP

(none — no triple in this chunk needs outright removal)

## ADD  (missing triples the sentence supports)

- **S3544**  `kawangen (di samping jenazah) | BERTUJUAN_AGAR | perjalanan roh yang meninggal tidak mendapat halangan`
  why: the purpose clause "agar perjalanan roh yang meninggal tidak mendapatkan suatu halangan" (raw line 2998) is dropped entirely by the current single triple; flag.txt /115.

- **S3591**  `penggunaan anggapan | BERTUJUAN_AGAR | wanita yang numitis memiliki kesuburan untuk melahirkan`
  why: the "yang mana nantinya diharapkan..." purpose clause (raw line 3042) currently only survives as garble inside [0]'s run-on object; give it its own clean triple.

- **S3355**  `jenazah | DIMASUKKAN_MELALUI | teben pepaga/asagan`
  why: raw (line 2741, and reinforced by S3294): the corpse must be brought onto the platform through the teben (foot-end) — a concrete placement rule, currently unextracted.

- **S3546**  `jenazah | DIISI_DENGAN | kawangen di tangan`
  why: the sentence's main clause "jenazah tersebut sebelumnya diisi dengan sebuah kawangen di tangannya" (raw) is not captured; only the parenthetical detail ([0]-[2]) is.

- **S3799**  `jenazah | DITUTUPI_DENGAN | kain putih (panjang kira-kira 2 sampai 2,5 meter)`
  why: current [0] only captures "kain diisi rurub sinom"; the main clause "jenazah ditutupi dengan selembar kain putih yang panjangnya kira-kira dua sampai dua setengah meter" is dropped.

## NOTE  (borderline / systemic observation, no single fix)

- **S3783 [1]**  `priuk (tempat tirtha pangringkes) | DIPECAHKAN | setelah tirtha dipercikkan` — the object is a temporal adjunct, not a real object, and the "broken" fact is already implied by [2] ("priuk yang pecah dibuang"). Borderline redundant; consider merging [1]+[2] into `priuk ... | DIPECAHKAN_DAN_DIBUANG_DI | kolong bawah pepaga/asagan`. Manual override, faithful enough to keep.

- **S3589 / S3591**  confirm flag.txt's "X adalah simbol dari Y, yaitu Z" systemic pattern: `dependency_rule` still emits one fused/garbled object for this construction and needs the symbol-vs-emblem split. Two more instances here.

- **S3363 [0]** `jenazah | DITARUH | atas pepaga/asagan` — object leads with the stray preposition "atas"; should be "pepaga/asagan" or "di atas pepaga/asagan". Cosmetic, `dependency_rule`.

- **S3728 [0]** and **S3720 [1]**: objects are long purpose-clauses ("agar ... numitis lagi dan terhindar dari penyakit, serta memiliki budi pekerti...") — kept per flag.txt's explicit ADD requests, so not flagged, but they sit at the edge of the terseness rule.

## Chunk stats
FIX: 6   DROP: 0   ADD: 5   sentences reviewed: 59

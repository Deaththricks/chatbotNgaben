# Chunk 1 audit (S4..S785)

Convergence re-audit of 59 sentences. flag.txt verdicts treated as authoritative for
S46, S58, S215, S219, S246, S253, S258, S270, S271, S338, S344, S354, S358, S364, S399, S400 —
all of those now carry the requested manual_override fixes and are confirmed applied (only
additional issues noted below). Remaining problems are genuine and mostly untouched by the
earlier pass.

Glosses used: *membujur* = "lie oriented / stretched out" (NOT menuju = head toward);
*berbentuk/berwujud/menyerupai* = "takes the form of" (NOT melambangkan = symbolizes);
*gedarba* = a bull-shaped/animal-shaped patulangan (cremation-bier animal) for commoners;
*keampigan* = a side-panel/wing element of the puspa lingga; *sekar ura* = scattered-flower
mix; *sasih* = (lunar) month; *ditampih / diduakalikan* = intercalated / doubled.

---

## FIX  (triple is salvageable — give the corrected triple)

- **S69 [0]**  current: `gedarba | MELAMBANGKAN | beruang`
  fix: `gedarba | BERBENTUK | beruang berwarna hitam`
  why: Raw (line 45): "Gedarba: Berbentuk menyerupai beruang berwarna hitam, digunakan oleh
  wangsa sudra jadma." The gedarba *is shaped like* a black bear, it does not *symbolize* a
  bear — the recurring berwujud/melambangkan confusion. Also restores dropped "berwarna hitam".
  (See ADD for the dropped user clause.)

- **S81 [0]**  current: `singa | ADALAH | 3:2:2`
  fix: `perbandingan kepala singa | ADALAH | 3:2:2`
  why: Raw (line 53): "perbandingan kepala Lembu adalah 2:1:1, sedangkan Singa adalah 3:2:2."
  The 3:2:2 is a *head-proportion ratio*, not an identity of the lion figure. Subject dropped
  "perbandingan kepala". (See ADD for the lembu member.)

- **S92 [0]**  current: `kanoroyang sanksi terberat | BERUPA | pemberhentian keanggotaan desa adat`
  fix: `kanoroyang | ADALAH | sanksi terberat berupa pemberhentian keanggotaan desa adat`
  why: Raw (line 61): "Kanoroyang: Sanksi terberat berupa pemberhentian keanggotaan desa adat."
  "kanoroyang" is the heading/entity; "sanksi terberat" was wrongly fused into the subject span.

- **S104 [0]**  current: `bali aga vs bali dataran | MEMPEROLEH | perbedaan mendasar`
  fix: DROP (see DROP + ADD) — heading-as-subject with "vs"; "MEMPEROLEH perbedaan" is nonsense.

- **S332 [0]**  current: `jenazah | DILETAKKAN_DI | balai posisi kepala berhulu utara`
  fix: `jenazah | DILETAKKAN_DI | balai`
  why: Raw (line 195): "Jenazah diletakkan pada balai dengan posisi kepala berhulu utara atau
  timur." Object fused the location with the head-orientation adjunct and dropped the "atau timur"
  disjunct. Add a second triple for the orientation (see ADD).

- **S366 [0] & [1]**  current: `jenazah | MENUJU | timur` / `jenazah | MENUJU | utara`
  fix: `jenazah | MEMBUJUR_KE | timur` / `jenazah | MEMBUJUR_KE | utara`
  why: Raw (line 219): "Jenazah membujur ke utara atau ke timur." *membujur* = lies oriented,
  not *menuju* = heads toward. This is exactly failure mode #5 in the instructions.

- **S370 [1]**  current: `jenazah | DIGULUNG_DENGAN | kain yang telah dirajah dengan tikar dan kain yang telah dirajah`
  fix: `jenazah | DIGULUNG_DENGAN | kain yang telah dirajah`
  why: Self-duplication garble; TEXT is "digulung dengan tikar dan kain yang telah dirajah"
  ([0] already covers "tikar").

- **S370 [3] & [4]**  current: `jenazah | DILETAKKAN_DI | ibu jari kaki` / `jenazah | DILETAKKAN_DI | ibu jari tangan`
  fix: `itik-itik | DIPASANG_PADA | ibu jari tangan dan kaki`
  why: TEXT: "dipasang itik-itik pada ibu jari tangan dan kaki." The itik-itik are attached to
  the thumbs/big-toes; the jenazah is not "placed at" the toes. Wrong subject + wrong relation.
  ([2] "jenazah DIPASANG itik-itik" is also loose but tolerable.)

- **S283 [0]**  current: `banten | DIKENAL_SEBAGAI | kala puspa`
  fix: `banten yang menjadi simbol orang yang meninggal | DIKENAL_SEBAGAI | kala puspa`
  why: Raw (line 167): "banten yang menjadi simbol orang yang meninggal disebut Kala Puspa."
  Not all banten is kala puspa — only the effigy-banten standing for the deceased. Clause loss
  narrows a too-broad claim. (Lontar Yama Purva Tattwa correctly excluded — no source bleed.)

- **S415 [0]**  current: `malamasa | ADALAH | sasih yang ditampih atau diduakalikan , disebut juga malamasa`
  fix: `malamasa | ADALAH | sasih yang ditampih atau diduakalikan`
  why: Raw (line 246) literally repeats "disebut juga malamasa" (a source oddity); the triple
  copied the tautological tail. Trim it.

- **S254 [0]**  current: `kuburan | DIAMBIL | tulang belulang`
  fix: `tulang belulang | DIAMBIL_DARI | kuburan`
  why: TEXT: "maka kuburan dibongkar dan diambil tulang belulangnya." Bones are taken *from*
  the grave; the grave is not "taken". Direction/subject wrong. (See ADD for "dibongkar".)

- **S246 [0]**  current: `puspa lingga | DIAMBIL | keampigan`
  fix: `puspa lingga | DIBUKA | keampigan`
  why: TEXT: "puspa lingga tersebut dibuka keampigan..." verb is *dibuka* (opened), not diambil.
  Low-severity; sentence itself is murky ("upacara ini" anaphora, untriaged).

---

## DROP  (triple should be removed)

- **S104 [0]**  `bali aga vs bali dataran | MEMPEROLEH | perbedaan mendasar`
  why: Subject is a section heading joined by "vs"; predicate "obtains a fundamental difference"
  is meaningless. Raw (line 70) states the contrast content directly — replace with the two
  ADD triples below.

---

## ADD  (missing triples the sentence supports)

- **S104**  `bali aga | MEMPERTAHANKAN | tradisi asli kuno`  +  `bali dataran | MENDAPAT_PENGARUH_DARI | tradisi hindu-majapahit`
  why: Raw line 70 — the actual content of the "perbedaan mendasar" clause.

- **S124**  `bali aga | MENONJOLKAN | tradisi asli`  +  `bali aga | TIDAK_MENGGUNAKAN | pembakaran fisik secara masif`
  why: TEXT's "sedangkan bali aga..." contrast clause is entirely unextracted (only the
  bali-dataran half was pulled). Drops "pengaruh majapahit" from [0] too — minor.

- **S126**  `ngaben | BERFUNGSI_SEBAGAI | mekanisme spiritual pemurnian jiwa`  +  `ngaben | BERFUNGSI_SEBAGAI | perekat kohesi sosial`
  why: Raw (line 87): "...berfungsi sebagai mekanisme spiritual pemurnian jiwa sekaligus perekat
  kohesi sosial." Only "ngaben ADALAH institusi sosial-religius" survived.

- **S128**  `ngaben | MENJAGA | harmoni antara manusia, alam, dan sang pencipta`
  why: Raw (line 87) — defining clause "yang terus menjaga harmoni antara manusia, alam, dan
  Sang Pencipta" dropped from the ADALAH object.

- **S6**  `ngaben | BERAKAR_PADA | filosofi pelepasan jiwa (atma) dari ikatan duniawi`
  why: [0] is one long ADALAH object ("ritual kremasi yang berakar pada filosofi..."). Split:
  keep `ngaben | ADALAH | ritual kremasi` and add this BERAKAR_PADA triple.

- **S44**  `formalin | DIGUNAKAN_UNTUK | memperlambat pembusukan (selama masa persiapan)`
  why: Second independent clause of S44 ("di era modern, penggunaan formalin umum dilakukan
  untuk memperlambat pembusukan...") is unextracted.

- **S47**  `jenazah | DIKUBUR | segera`  +  `upacara ngelungah | DILAKUKAN | minimal 12 hari kemudian`
  why: Second clause ("jenazahnya segera dikubur dan upacaranya dilakukan minimal 12 hari
  kemudian") unextracted. NOTE: this is a baby-corpse sentence (cf. flag.txt 917/925) but the
  facts here are procedural and clean, not the problematic "corpse-of-a-baby as entity" pattern.

- **S217**  `pelebon | DIAWALI_DENGAN | upacara ngaskara`  +  `pelebon | DIAWALI_DENGAN | caru pengelambuk`  +  `jenazah | BERANGKAT_KE | setra`
  why: Only "jenazah DINAIKKAN_KE usungan" was pulled from a sentence carrying 4+ events
  (dilaksanakan pelebon, diawali dengan ngaskara dan caru pengelambuk, ... lalu berangkat ke setra).

- **S265**  `tegteg | DITEMPATKAN_DI | tumpang salu`
  why: Final clause "selanjutnya tegteg ditempatkan di tumpang salu" unextracted.

- **S332**  `jenazah | MEMBUJUR_KE | kepala di utara atau timur`
  why: Head-orientation adjunct that was wrongly fused into [0]'s location object; restore as
  its own triple (and it carries the "atau timur" disjunct [0] lost).

- **S364**  `nanginin | DILAKUKAN_DENGAN | memanggil nama almarhum dan mengucapkan kata-kata lemah lembut`  +  `nanginin | DILAKUKAN_SEBELUM | jenazah diusung ke tempat pemandian`
  why: flag.txt 364 explicitly asks for "more extraction for the nanginin ceremony"; the manner
  clause and the temporal frame are both still unextracted.

- **S376**  `jenazah | DIBASMI_OLEH | sang hyang birawi`
  why: Purpose clause "untuk dibasmi oleh sang hyang birawi" (cremation agent) unextracted.

- **S399**  `sasih karo | ADALAH | sasih utama untuk pitra yadnya`
  why: TEXT tail "dengan yang utama pada sasih karo" (karo is the primary month) unextracted.

- **S254**  `kuburan | DIBONGKAR | (untuk mengambil tulang belulang)`
  why: "kuburan dibongkar dan diambil tulang belulangnya" — the dismantling act is dropped.

- **S780**  `puspa asti | DIPANGKU_OLEH | salah seorang keluarga`  +  `persembahyangan | DIPIMPIN_OLEH | sulinggih`
  why: TEXT: "...atau dipangku oleh salah seorang keluarga; persembahyangan ini dipimpin oleh
  sulinggih." Disjunct alternative and the second independent clause both unextracted.

---

## NOTE  (borderline / systemic observation, no single fix)

- **S6, S45, S48, S61**  Long single-object ADALAH extractions that would read better split.
  S45: `asti wedana ADALAH upacara pembakaran tulang belulang` + `tulang belulang DIGALI_DARI
  kuburan (sesuai aturan adat setempat)`. S48: drops agent "oleh warga desa" ("pelaksanaan
  kolektif oleh warga desa untuk efisiensi..."). S61 [0]: purpose clause "untuk memutus ikatan
  emosional dan duniawi antara mendiang (niskala) dengan keluarga (skala)" could be its own
  BERTUJUAN triple. All faithful-but-verbose; low priority. S61 [1] "mapegat BERARTI memutuskan"
  is good.

- **S26 / S27 / S28 / S29**  panca-maha-bhuta element triples (`apah/teja/bayu/akasa MELAMBANGKAN
  ...`) each drop "dalam tubuh" ("mewakili unsur cair dalam tubuh" etc.). Minor nuance loss;
  arguably fine as-is. S29 renders "rongga dalam tubuh" as "rongga tubuh" — acceptable.

- **S12**  `ngaben MEMILIKI sudut pandang pemaknaan` drops "beberapa" (several). Minor (/115).

- **S73 [1]**  Decomposition child uses `boneka naga raksasa` as subject where `naga banda`
  would be cleaner; object "pengikat keinginan duniawi raja" is faithful. Tolerable.

- **S77 [0]**  `naga banda MEMILIKI panjang 1.600 depa` drops "seharusnya" — raw (line 1634):
  "panjang ... seharusnya 1.600 depa". It is the *ideal/prescribed* length, not actual. Minor.

- **S197**  `ngaben BERDASARKAN tingkatan upacara` — a bare section heading, but the triple
  (ngaben is classified by ceremony level) is semantically harmless. Leave.

- **S633**  `banten DIPERSEMBAHKAN_KEPADA sulinggih utawi pinandita` — source is a heading
  fragment ("banten pengajeng sulinggih utawi pinandita"); "utawi" (Balinese "atau") left
  untranslated in the object. Relation is a reasonable reading. Low priority.

- **S785**  `pitra yadnya ADALAH istilah umat hindu` — raw: "telah menjadi sebuah istilah bagi
  umat hindu di sini." Object is awkward and NER-typed AGAMA (from "hindu"); "istilah bagi umat
  hindu" would be truer. Borderline.

- **S344 [10]–[12]**  Still-compound objects ("kain putih untuk bantal berisi pis bolong 11
  kepeng", "kain kuning untuk saput atau selendang", "rantasan kain putih kuning dan kain
  anyar") despite flag.txt 344/344.2 asking for maximum terseness. These are manual_override;
  weighting toward trust, but flagging that the split is not fully carried through.

---

## Chunk stats
FIX: 12   DROP: 1   ADD: 15 (across 13 sentences)   sentences reviewed: 59

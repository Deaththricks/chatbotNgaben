# Glossary Review — Master List

**Status:** these definitions are already live in `Graphing/data/ngaben-glossary.txt` and `entities.json` — this file is a markup copy for you to flag corrections, not a pending queue. If you check/annotate something here, the actual fix has to be made in `Graphing/data/ngaben-glossary.txt` directly (find the matching `* Term:  Definition.` line), then rebuild (`python build_kb.py` from `Graphing/kb/`) and reload Neo4j.

**2026-09-23 update:** 4 of the original 46 turned out to be "quantity baked into the entity name" mistakes (e.g. defining "five pieces of betel leaf" as if it were its own term) -- flagged by the user, re-audited against the raw source text, and fixed:
- `uang_kepeng_sebanyak_250_biji` -- merged into the already-existing `uang_kepeng` entity (force_merge); the "250 biji" detail moved into a new **Gegaleng** definition instead of living in a quantity-entity.
- `sembilan_batang_kayu_cendana` -> renamed to **Kayu Cendana**. Also fixed a real subject-attribution bug found while investigating: the source sentence says *pengawak* (not jun pere) consists of jun pere+water, alang-alang grass, AND the sandalwood sticks as three siblings -- the KB had wrongly attached the sticks to jun pere. Fixed via `review_decisions.json`.
- `lima_buah_lembaran_lembaran_daun_sirih` -> renamed to **Lembaran Daun Sirih**. Same kind of bug: the source specifically says "Kawangen Jeriji" (an existing, more specific entity), not generic kawangen -- fixed via `review_decisions.json`.
- `bilah_bilah_bambu_sebanyak_9_buah` -> renamed to **Bilah Bambu Galar** (subject attribution to `galar` was already correct, just the naming issue).

These 4 are removed from the list below since their entity ids changed; see the updated definitions directly in `ngaben-glossary.txt` if you want to re-review them under their new names.

Note: `build_glossary_review_master.py` can't regenerate this list anymore — it only lists currently-*undefined* entities, and these 46 no longer qualify. This is a static file now.

**2026-09-22 update:** added a new section at the very bottom, **New entities (no KB entry at all yet)**, for terms that don't have an entity in the graph *at all* — found by scanning definitions/facts/glossary+FAQ passages for words that get referenced but never got their own KB entry (see the "referenced but ungrounded" audit from this session). These are unlike everything above: there's no existing definition to review, it's blank. Write the definition straight into that section; it gets merged into `ngaben-glossary.txt` as a brand-new line and only becomes a real graph entity on the next `build_kb.py` run.

Grouped by theme below instead of one flat list, since related items are easier to sanity-check side by side.

---

## Lis Bale Gading components (9)
*(lis bale gading = a ceremonial offering assemblage; supporting fact for each is "lis bale gading terdiri dari X" unless noted)*

- [ ] **Benang Tatebus** (`benang_tatebus`) — Benang suci sebagai simbol penebusan dan pengikat spiritual dalam rangkaian sesajen lis bale gading.
- [ ] **Bersihan Payasan** (`bersihan_payasan`) — Perlengkapan penyucian dan perhiasan simbolis di dalam rangkaian lis bale gading.
- [ ] **Coblong** (`coblong`) — Wadah kecil dari tanah liat untuk menampung air suci pada kelengkapan lis bale gading.
- [ ] **Gelar Sanga** (`gelar_sanga`) — Segehan atau sesajen persembahan untuk menetralisir kekuatan Bhuta Kala dan Sang Yama Raja.
- [ ] **Padma** (`padma`) — Simbolisme bunga teratai perepresentasi tempat suci tertinggi dewata dalam sesajen lis bale gading.
- [ ] **Raka-Raka** (`raka_raka`) — Sesajen pelengkap dari aneka buah-buahan dan jajanan tradisional sebagai pengisi lis bale gading.
- [ ] **Rangkadan** (`rangkadan`) — Susunan persembahan dalam porsi kelompok kecil yang menjadi bagian dari rentetan isi lis bale gading.
- [ ] **Sampian Pusung** (`sampian_pusung`) — Ornamen upakara dari anyaman janur dengan bentuk ujung dipusung (ditekuk) di dalam lis bale gading.
- [ ] **Tipat** (`tipat`) — Anyaman janur berisi beras yang dikukus (ketupat) sebagai sarana persembahan di dalam lis bale gading.

## Kawangen components (2)
*(kawangen = a specific Balinese ritual offering)*

- [ ] **Bunga Tunjung Putih** (`bunga_tunjung_putih`) — fact: "kawangen berisi bunga tunjung putih". Bunga teratai putih lambang kesucian tertinggi, diletakkan sebagai elemen utama di dalam kawangen.
- [ ] **Pusuh Bunga Cempaka Kuning** (`pusuh_bunga_cempaka_kuning`) — fact: "kawangen berisi pusuh bunga cempaka kuning". Kuncup bunga cempaka kuning wangi yang diletakkan ke dalam balutan kawangen.

## Eteh-Eteh components -- corpse wrapping/dressing items (9)
*(eteh-eteh = ritual cloth/paraphernalia used to dress the corpse; supporting fact is "eteh-eteh berupa X" unless noted)*

- [ ] **Kain Kuning untuk Saput/Selendang** (`kain_kuning_untuk_saput_selendang`) — Kain kuning yang difungsikan sebagai selendang atau saput penutup tubuh jenazah (eteh-eteh).
- [ ] **Kain Putih Panjang** (`kain_putih_panjang`) — fact: "jenazah ditutupi dengan kain putih panjang". Kain kafan (kajang) panjang untuk menutupi seluruh tubuh jenazah setelah disucikan.
- [ ] **Kain Putih untuk Bantal** (`kain_putih_untuk_bantal`) — Kain putih lapis eteh-eteh untuk membungkus bantal alas kepala jenazah (gegaleng).
- [ ] **Kamben** (`kamben`) — Kain panjang atau sarung khas Bali yang dipakaikan pada jenazah sebagai kelengkapan busana utama.
- [ ] **Pangulungan** (`pangulungan`) — Lapisan kain pembungkus atau penggulung badan jenazah (eteh-eteh).
- [ ] **Rantasan Kain Putih-Kuning** (`rantasan_kain_putih_kuning`) — Tumpukan kain suci berwarna putih dan kuning sebagai bekal pakaian (eteh-eteh) untuk perjalanan roh.
- [ ] **Sabuk** (`sabuk`) — Ikat pinggang carik kain yang dibebatkan pada busana jenazah sebagai eteh-eteh.
- [ ] **Tapih** (`tapih`) — Kain bawahan atau pelapis dasar pertama yang dipakaikan untuk membalut tubuh jenazah.
- [ ] **Tatindih** (`tatindih`) — Kain berlapis yang ditindihkan secara khusus di atas susunan persembahan atau tubuh jenazah.

## Pepaga bamboo-counting cluster (5)
*(all five share one supporting fact shape: "pepaga terbuat dari hitungan X" -- see also Bilah-Bilah Bambu below, same pepaga topic)*

- [ ] **Hitungan Galir** (`hitungan_galir`) — Salah satu dari enam sebutan berurutan (likah, wangke, wangkong, galar, galir, galur) dalam sistem hitungan bilah bambu tradisional Bali untuk menentukan ukuran pepaga (alas memandikan jenazah); hitungan yang dianjurkan untuk pepaga adalah wangke atau galar, bukan galir.
- [ ] **Hitungan Galur** (`hitungan_galur`) — Salah satu dari enam sebutan berurutan (likah, wangke, wangkong, galar, galir, galur) dalam sistem hitungan bilah bambu tradisional Bali untuk menentukan ukuran pepaga (alas memandikan jenazah); hitungan yang dianjurkan untuk pepaga adalah wangke atau galar, bukan galur.
- [ ] **Hitungan Likah** (`hitungan_likah`) — Salah satu dari enam sebutan berurutan (likah, wangke, wangkong, galar, galir, galur) dalam sistem hitungan bilah bambu tradisional Bali untuk menentukan ukuran pepaga (alas memandikan jenazah); hitungan yang dianjurkan untuk pepaga adalah wangke atau galar, bukan likah.
- [ ] **Hitungan Wangke** (`hitungan_wangke`) — Salah satu dari enam sebutan berurutan (likah, wangke, wangkong, galar, galir, galur) dalam sistem hitungan bilah bambu tradisional Bali; bersama galar, wangke adalah hitungan yang dianjurkan saat membuat pepaga, alas untuk memandikan jenazah.
- [ ] **Hitungan Wangkong** (`hitungan_wangkong`) — Salah satu dari enam sebutan berurutan (likah, wangke, wangkong, galar, galir, galur) dalam sistem hitungan bilah bambu tradisional Bali untuk menentukan ukuran pepaga (alas memandikan jenazah); hitungan yang dianjurkan untuk pepaga adalah wangke atau galar, bukan wangkong.

## Pepaga / structural (1)

- [ ] **Balai-Balai Alas Ngringkes** (`balai_balai_alas_ngringkes`) — fact: "pepaga berfungsi sebagai balai-balai alas ngringkes". Tempat pembaringan (umumnya pepaga atau keranda bambu) khusus untuk prosesi ngringkes atau merawat dan menggulung jenazah.

## Ceremony / cosmology specifics (5)

- [ ] **Macan** (`macan`) — fact: "patulangan berbentuk macan". Wadah pembakaran jenazah (patulangan) menyerupai harimau, umumnya diperuntukkan bagi warga keturunan wangsa Pande.
- [ ] **Ngaben Cara Yama Purwana Tatwa** (`ngaben_cara_yama_purwana_tatwa`) — fact: "ngaben cara yama purwana tatwa dilakukan dengan sawa". Tata pelaksanaan Ngaben yang merujuk Lontar Yama Purwana Tattwa, dilakukan secara langsung menggunakan jenazah fisik (sawa).
- [ ] **Panjaya-Jaya** (`panjaya_jaya`) — fact: "sulinggih memberikan panjaya-jaya". Mantra pemberkatan oleh Sulinggih untuk memohon keselamatan dan kelancaran transisi roh ke alam nirwana.
- [ ] **Sthiti** (`sthiti`) — fact: "pura kahyangan tiga berfungsi sebagai sthiti". Aspek pemeliharaan (preservation) dalam konsep Tri Murti Hindu Bali, salah satu dari tiga fungsi utama bersama utpatti (penciptaan, Brahma) dan pralina (peleburan, Siwa); dalam kerangka Kahyangan Tiga, Pura Puseh secara khusus mewakili fungsi sthiti ini sebagai stana Dewa Wisnu.
- [ ] **Sukutunggal** (`sukutunggal`) — fact: "abu dibentuk menjadi sukutunggal". Sisa abu jenazah pasca-kremasi yang dikumpulkan dan dirangkai kembali secara utuh sebagai perwujudan esensi roh tunggal.

## Calendar (1)

- [ ] **Galungan** (`galungan`) — fact: "wuku kuningan sepuluh hari setelah galungan". Hari Raya kemenangan Dharma di Bali; wuku Kuningan dilaksanakan tepat sepuluh hari sesudahnya.

## Materials & offerings (10)

- [ ] **Arang Pembakaran Jaja Gina** (`arang_pembakaran_jaja_gina`) — fact: "sisig terbuat dari arang pembakaran jaja gina". Arang dari pembakaran penganan tradisional jaja gina, digunakan sebagai bahan utama pembuatan sisig (pembersih gigi) saat prosesi memandikan jenazah.
- [ ] **Arang Pembakaran Jaja Uli** (`arang_pembakaran_jaja_uli`) — fact: "sisig terbuat dari arang pembakaran jaja uli". Arang dari jaja uli yang dibakar, ditumbuk dan dijadikan bahan sisig untuk menyucikan jenazah secara simbolis.
- [ ] **Beras Kuning** (`beras_kuning`) — fact: "sekar ura terdiri dari beras kuning". Beras berpewarna kuning alami yang dicampur dalam sekar ura (taburan bunga) untuk menerangi jalan roh jenazah.
- [ ] **Bunga** (`bunga`) — fact: "eteh-eteh berupa bunga". Kelengkapan upakara untuk menghiasi tubuh jenazah dan pelengkap sesajen pembakaran.
- [ ] **Daun Kelapa Muda Busung** (`daun_kelapa_muda_busung`) — fact: "hiasan terbuat dari daun kelapa muda busung". Janur yang dianyam untuk membuat berbagai bentuk hiasan upakara pengiring jenazah.
- [ ] **Daun Pisang** (`daun_pisang`) — fact: "kojong terbuat dari daun pisang". Lembaran daun pisang yang digulung membentuk kerucut (kojong) sebagai wadah perlengkapan upakara.
- [ ] **Daun Rontal** (`daun_rontal`) — fact: "adegan terbuat dari daun rontal". Daun lontar kering yang dirangkai menjadi adegan, yakni perwujudan simbolis badan roh jenazah.
- [ ] **Daun Temen** (`daun_temen`) — fact: "sekar ura terdiri dari daun temen". Daun yang dirajang dan dicampur dengan bunga jepun untuk melengkapi ramuan sekar ura.
- [ ] **Kulit Telur Ayam Berminyak Kelapa** (`kulit_telur_ayam_berminyak_kelapa`) — fact: "angenan terbuat dari kulit telur ayam berminyak kelapa". Cangkang telur kosong berisi minyak kelapa untuk membuat damar angenan, pelita penuntun jalan roh.
- [ ] **Rontal Dilapisi Kertas Emas** (`rontal_dilapisi_kertas_emas`) — fact: "cili terbuat dari rontal dilapisi kertas emas". Lontar berhias kertas prada/emas yang dibentuk menjadi cili, simbolisasi perawakan badan halus (atma) jenazah.

---

## 2026-09-23 research pass — proposed revised definitions (all 42 terms, lines above)

*(Requested by the user: re-derive every definition in the four sections above from the raw corpus (via `Graphing/results/final/relationResultsNgaben/relation_results_ngaben.md` — the sentence-by-sentence markdown rendering of the corpus, since the `.txt` corpus files don't carry per-sentence IDs) plus web research, rather than trusting the definitions already live. Method: grep the corpus md for each term's raw sentence(s) first; for terms that only ever appear as flat list members with no standalone definition sentence — most of the Lis Bale Gading / Kawangen / Eteh-Eteh items — web-search the general Balinese-Hindu ritual vocabulary instead, since the corpus has nothing to ground them in. Unchanged = corpus/web confirms the existing definition; only entries marked "revised" actually need the live `ngaben-glossary.txt` line changed.)*

**2026-09-23 — applied:** all 19 REVISED entries below (checked `[x]`) are now live in `Graphing/data/ngaben-glossary.txt`, `build_kb.py` was re-run (495 entities, 395 relations), and Neo4j was reloaded (`load_ngaben_to_neo4j.py --source kb`: 495 nodes, 395 edges). The "confirmed unchanged" and "LOW CONFIDENCE" entries (Bersihan Payasan, Coblong, Padma, Rangkadan, Tipat, the 7 eteh-eteh items, Sthiti, Macan, the 6 materials-&-offerings items) were left untouched, still `[ ]` — no live edit needed for those.

### Lis Bale Gading components — mostly ungrounded in-corpus (S3196 is a flat list, no per-item definitions)

- [x] **Benang Tatebus** — REVISED: Benang (biasanya putih) yang dipintal/disatukan sebagai simbol penebusan dan penyatuan tekad dalam upacara yadnya — sebagaimana utas-utas tatebus yang terpisah dipintal menjadi satu, filosofinya menuntut ritual dijalani secara tuntas.
  - _source: web ([budaya-indonesia.org](https://budaya-indonesia.org/Makna-Penggunaan-Benang-Pada-Upacara-Yadnya-Agama-Hindu-Bali), [guliangkangin.or.id](https://guliangkangin.or.id/artikel/2015/11/19/makna-penggunaan-benang-saat-upacara)) — general benang-tatebus philosophy across Balinese yadnya, not ngaben-specific. Corpus (S3196) only records list membership, no standalone definition sentence._
- [ ] **Bersihan Payasan** — LOW CONFIDENCE, no dedicated source found. Web search surfaced no standalone definition of this compound term; kept close to the existing gloss (bersihan = cleaning/purification items, payasan = adornment/decoration items — both real Balinese words, but the compound's specific referent inside lis bale gading isn't documented anywhere I could find). Flag for a human who knows the item directly rather than trusting either version.
- [ ] **Coblong** — confirmed close to unchanged: Wadah kecil dari tanah liat/gerabah untuk menampung air (sering air suci/tirtha), lazim diletakkan di pelinggih/sanggah atau sebagai kelengkapan banten.
  - _source: web ([Bali Express](https://baliexpress.jawapos.com/balinese/675248408/sering-ditemukan-pada-pelinggih-caratan-dan-coblong-simbol-purusa-dan-pradana-memiliki-unsur-tanah-air-dan-api)) — clay water-vessel function confirmed generically across Balinese ritual use, not ngaben-specific._
- [x] **Gelar Sanga** — REVISED (drops an uncorroborated claim): Segehan/sesajen yang dihaturkan kepada Bhatari Durga, Kala, dan Bhuta (Bhuta Kala) — lazim dihaturkan saat piodalan di pura/sanggah — untuk menjaga keseimbangan dan mencegah gangguan kekuatan negatif.
  - _source: web ([kesrasetda.bulelengkab.go.id](https://kesrasetda.bulelengkab.go.id/informasi/detail/artikel/11_makna-dan-arti-segehan-serta-fungsinya) on segehan/Bhuta Kala; [tarubali.baliprov.go.id](https://tarubali.baliprov.go.id/konsepsi-dewata-nawa-sanga/) on Dewata Nawa Sanga) — the old definition's specific "Sang Yama Raja" target wasn't corroborated by any source found, so it's dropped rather than carried forward unverified._
- [ ] **Padma** — confirmed close to unchanged: Simbol bunga teratai (padma) yang merepresentasikan sthana (tempat berstana) tertinggi para dewata dan kesucian tertinggi dalam kosmologi Hindu Bali (konsep padma bhuana).
  - _source: web ([Kemenag DIY](https://diy.kemenag.go.id/11275-tapak-dara-swastika-dan-padma-dalam-hindu.html)) — general Hindu-Bali lotus/padma symbolism; corpus gives no ngaben-specific elaboration beyond list membership._
- [x] **Raka-Raka** — REVISED (adds a named source text): Sesajen pelengkap berupa aneka buah-buahan (pisang, apel, salak, jeruk, dll) dan jajan tradisional — menurut Lontar Yadnya Prakerti disebut "rakan banten", melambangkan Hyang Widyadhara-Widyadhari (penguasa ilmu pengetahuan suci).
  - _source: web ([basabali.org kamus](https://dictionary.basabali.org/w/index.php?title=Raka-raka&uselang=id), [cakepane.blogspot.com](https://cakepane.blogspot.com/2014/12/makna-banten-dan-bebantenan-di-bali.html))._
- [ ] **Rangkadan** — LOW CONFIDENCE, no dedicated source found. Web search only surfaced the compound "kojong rangkadan" in passing, no definition of "rangkadan" on its own. Kept the existing gloss (a small clustered sub-arrangement within the offering) as the best available guess — root word likely "rangkad" (cluster/set) — but this is unverified and should get a native-speaker check.
- [x] **Sampian Pusung** — REVISED (corrects the shape gloss): Ornamen upakara anyaman janur berbentuk pusung (sanggul/simpul seperti gelungan rambut, bukan sekadar "ditekuk") — dipakai a.l. pada banten sambutan alit — melambangkan penyempitan/pemusatan indria menuju Brahman sebagai tujuan akhir.
  - _source: web (sampiyan/sampian-pusung descriptions from Balinese offering-craft sources) — upgrades the prior "ujung dipusung (ditekuk)" gloss with the actual bun/knot shape and its stated symbolism._
- [ ] **Tipat** — confirmed unchanged: Ketupat — anyaman janur berbentuk kantong berisi beras yang dikukus — dipakai sebagai salah satu sarana persembahan.
  - _source: standard, well-known Indonesian/Balinese term; no correction needed._

### Kawangen components — flat list in corpus (S3747/S3749/S3753), no per-item definitions there either

- [x] **Bunga Tunjung Putih** — REVISED (adds real symbolism the old def lacked): Bunga teratai putih, dianggap raja segala bunga dalam Hindu Bali — melambangkan kesucian hati/jiwatman sekaligus sthana suci Ida Sang Hyang Widhi Wasa; strukturnya dikaitkan dengan Dewata Nawa Sanga, dengan Sang Hyang Siwa di bagian tengahnya.
  - _source: web ([rri.co.id](https://rri.co.id/singaraja/regional/2523791/filosofi-bunga-tunjung-lambang-kesucian) "Filosofi Bunga Tunjung Lambang Kesucian")._
- [x] **Pusuh Bunga Cempaka Kuning** — REVISED (adds deity association): Kuncup bunga cempaka kuning (Michelia champaca) yang wangi — dalam persembahyangan/yadnya Bali dikaitkan dengan Dewa Mahadewa — dimasukkan ke dalam balutan kawangen.
  - _source: web (general Balinese flower-symbolism sources on cempaka kuning / Mahadewa association)._

### Eteh-Eteh components — grounded directly by corpus S344's full list sentence

- [ ] **Kain Kuning untuk Saput/Selendang**, **Kain Putih Panjang**, **Kain Putih untuk Bantal**, **Kamben**, **Rantasan Kain Putih-Kuning**, **Sabuk**, **Tapih** — confirmed unchanged. All seven are directly named in corpus S344 ("eteh-eteh sawa, berupa kain putih untuk saput, kamben, tapih, sabuk, udeng, pangulungan, ... kain putih untuk bantal berisi pis bolong 11 kepeng; kain kuning untuk saput atau selendang; rantasan kain putih kuning dan kain anyar...") and are standard, unambiguous Balinese clothing/textile terms — no correction warranted.
- [x] **Pangulungan** — REVISED (tightened, same meaning): Kain pembungkus/penggulung jenazah — dari akar kata "gulung" (menggulung) — lapisan yang dililitkan mengelilingi tubuh jenazah sebagai bagian dari eteh-eteh sawa.
  - _source: corpus S344 (list membership) + Balinese etymology (gulung = roll/wrap)._
- [x] **Tatindih** — REVISED (drops an uncited "silk cloth" claim seen during web research): Kain/lapisan yang ditindihkan (ditekan/dibebankan di atas) secara khusus pada susunan eteh-eteh atau tubuh jenazah — dari akar kata "tindih" (menindih/menekan).
  - _source: corpus S344 (list membership) + Balinese etymology (tindih = press/weigh down). A web search result called this "kain sutera" (silk cloth) with no traceable citation behind it — not adopted, since it can't be verified and would be a fabricated specific if wrong._

### Pepaga bamboo-counting cluster — real correction: the six counts split into two separate systems, not one flat set of six

*(New grounding: short crossbars use likah/wangke/wangkong; long lengthwise bars use galar/galir/galur — two parallel three-way systems, not six interchangeable options. This explains why the existing defs paired "wangke or galar" as the recommended pepaga counts: one from each system.)*

- [x] **Hitungan Likah** — REVISED: Hitungan bilah bambu pendek (palang pendek) dalam sistem likah-wangke-wangkong, diperuntukkan bagi bangunan/perlengkapan orang yang masih hidup (manusa) — bukan untuk pepaga (alas memandikan jenazah), yang semestinya memakai hitungan wangke.
- [x] **Hitungan Wangke** — REVISED: Hitungan bilah bambu pendek yang diperuntukkan khusus bagi jenazah/orang yang telah meninggal — bersama galar, wangke adalah hitungan yang dianjurkan untuk membuat pepaga.
- [x] **Hitungan Wangkong** — REVISED: Hitungan bilah bambu pendek yang dipercaya menyebabkan sakit pinggang bagi penggunanya — karena itu dihindari, termasuk untuk pepaga.
- [x] **Hitungan Galir** — REVISED: Hitungan bilah bambu panjang (palang memanjang) dalam sistem galar-galir-galur, dipercaya membuat dipan/pepaga tidak stabil dan berbunyi — karena itu dihindari, semestinya memakai hitungan galar.
- [x] **Hitungan Galur** — REVISED: Hitungan bilah bambu panjang yang dipercaya membuat dipan/pepaga cepat rusak/lapuk — karena itu dihindari, semestinya memakai hitungan galar.
  - _source (all five): web ([kadeksugi.info](https://www.kadeksugi.info/2017/03/jumlah-likah-yang-salah-ternyata-bisa-membuat-sakit-pinggang/) "Jumlah Likah Bisa Membuat Sakit Pinggang", [ubadbali.wordpress.com](https://ubadbali.wordpress.com/2018/12/04/mengenal-dulu-teben-serta-galargalir-galur-tidur-pun-ada-aturanya-di-bali/)) + corpus S354 ("pepaga terbuat dari bambu dengan hitungan: likah, wangke, wangkong, dan galar, galir, galur")._

### Pepaga / structural

- [x] **Balai-Balai Alas Ngringkes** — REVISED (this is pepaga's function, not a separate object): Fungsi pepaga sebagai tempat pembaringan sekaligus alas untuk memandikan jenazah (nyiramang layon) dan untuk ngringkes (membungkus/menggulung jenazah) — bukan entitas terpisah dari pepaga, melainkan salah satu fungsi/perannya.
  - _source: corpus S1056, direct grounding: "pepaga ini berfungsi sebagai balai-balai alas memandikan jenazah dan ngringkes." The old definition described it as if a distinct physical object ("tempat pembaringan... khusus"); the raw sentence frames it as pepaga's stated function instead._

### Ceremony / cosmology specifics

- [ ] **Macan** — confirmed, with corpus's own framing added: Bentuk patulangan (wadah pembakaran jenazah) menyerupai harimau berwarna merah dengan corak belang — dipakai oleh keturunan Maha Mpu Brahma Raja Wisesa (wangsa Pande). Korpus sendiri mengelompokkan macan bersama singa dan gadarba sebagai "ciri paksa brahmanisme" — konsisten dengan Pande sebagai klan yang mengklaim status setara Brahmana, jadi ini bukan kontradiksi meski butuh dibaca hati-hati.
  - _source: corpus S2056 ("patulangan yang berbentuk macan, singa, gadarba (beruang)... adalah ciri paksa brahmanisme") + web ([balikonten.com](https://balikonten.com/peran-penting-petulangan-dalam-upacara-ngaben-lengkap-dengan-jenis-dan-peruntukannya/) "Jenis Petulangan dalam Pengabenan") confirming the macan-form/Pande-descent link specifically._
- [x] **Ngaben Cara Yama Purwana Tatwa** — REVISED (important scope correction): Salah satu metode Ngaben yang disebutkan dalam Lontar Yama Purwana Tattwa, dilakukan langsung menggunakan jenazah fisik (sawa) — lontar ini sendiri juga memuat metode-metode lain (mis. recadana, swasta geni) untuk kondisi jenazah tidak ditemukan/tanpa jasad fisik, jadi istilah ini merujuk spesifik pada varian yang memakai sawa, bukan pada lontar itu sendiri secara keseluruhan.
  - _source: corpus S1931 ("berdasarkan lontar yama purwana tatwa, recadana ... atau swasta geni yang sederhana pun pangabenan telah selesai dengan tuntas") + web (researchgate.net / jurnal.stkipahsingaraja.ac.id "Lontar Yama Purwana Tattwa") confirming the lontar covers simple/menengah/utama levels, not one fixed method._
- [x] **Panjaya-Jaya** — REVISED (corrects who the blessing is for): Berkat/pemberkatan yang diberikan sulinggih kepada anak-keturunan yang menyelenggarakan upacara (mis. saat ngroras, sesudah saji tarpana hari pertama), memohon keselamatan dan penyucian diri — serupa dengan upacara mejaya-jaya yang lazim dikenal dalam ritus Hindu Bali. Bukan mantra yang ditujukan untuk jenazah/roh itu sendiri, seperti klaim definisi lama.
  - _source: corpus S2885 ("sang sulinggih memberikan panjaya-jaya serta memberikan ayaban sesayut kepada putra-putri yang berupacara") + web ([rri.co.id](https://rri.co.id/singaraja/regional/1618730/mejaya-jaya-upacara-permohonan-keselamatan-dan-penyucian-diri) "Mejaya-Jaya, Upacara Permohonan Keselamatan dan Penyucian Diri")._
- [ ] **Sthiti** — confirmed unchanged, already well grounded (corpus S4023-4027 plus the KB's own `wisnu`/`pura_puseh`/`kahyangan_tiga`-adjacent definitions agree). No revision needed.
- [x] **Sukutunggal** — REVISED (drops a drifted "roh tunggal" framing not actually in the source): Bentuk abu jenazah yang telah digiling halus dari tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki, dimasukkan ke klungah nyuh gading (kelapa gading muda), dan dibentuk menjadi wujud perlambang badan — representasi simbolis utuh tubuh jenazah pasca-kremasi.
  - _source: corpus S1439, direct grounding, uses the corpus's own gloss verbatim: "...dibentuk menjadi sukutunggal (sebuah wujud perlambang badan)." The old definition's "esensi roh tunggal" (single-soul essence) framing isn't what the raw sentence says — it's a body-symbol, not a soul-symbol._

### Calendar

- [x] **Galungan** — REVISED (adds the specific Pawukon timing, otherwise unchanged): Hari Raya kemenangan Dharma atas Adharma dalam kalender Pawukon Bali, jatuh setiap 210 hari sekali pada Rabu Kliwon wuku Dungulan; wuku Kuningan (Hari Raya Kuningan) dilaksanakan tepat sepuluh hari sesudahnya, pada Sabtu Kliwon.
  - _source: general, well-established Hindu-Bali calendar knowledge (web-confirmed); the core claim was already correct, this just adds the day/wuku specifics the old definition left out._

### Materials & offerings — all ten already grounded directly in the corpus, confirmed unchanged except one

- [ ] **Arang Pembakaran Jaja Gina**, **Arang Pembakaran Jaja Uli** — confirmed unchanged (corpus S3153: sisig terbuat dari arang pembakaran jaja uli/jaja gina, dipakai gosok gigi jenazah).
- [ ] **Beras Kuning**, **Daun Temen** — confirmed unchanged (corpus S219: keduanya komponen sekar ura).
- [ ] **Bunga** — confirmed unchanged (corpus S344: eteh-eteh sawa berupa bunga).
- [x] **Daun Kelapa Muda Busung** — REVISED (adds the concrete example the old generic def lacked): Janur (daun kelapa muda/busung) yang dijahit bersama blangsah (bunga pinang yang belum mekar) untuk membuat hiasan rurub sinom sepanjang kira-kira 40-45 cm, selain dianyam untuk berbagai hiasan upakara pengiring jenazah lainnya.
  - _source: corpus S3800 ("rurub sinom adalah hiasan yang terbuat dari blangsah... dijarit bersama daun kelapa muda (busung), dengan panjang kira-kira 40 sampai 45 sentimeter")._
- [ ] **Daun Pisang** — confirmed unchanged (corpus S3647/S3734: alas jenazah dan bahan kojong).
- [ ] **Daun Rontal** — confirmed unchanged (corpus S1461: bahan adegan).
- [ ] **Kulit Telur Ayam Berminyak Kelapa** — confirmed unchanged (corpus S1642: bahan angenan/pelita).
- [ ] **Rontal Dilapisi Kertas Emas** — confirmed unchanged (corpus S1688: bahan cili).

## New entities — no KB entry at all yet (63)
*(these have no entity, no definition, nothing — found by scanning every bot-active definition/fact/glossary+FAQ passage for gazetteer words referenced but never given their own KB entry. Grouped by the gazetteer's own category, sorted by reference count within each group — more refs roughly means "shows up more," not "more important," you're the judge of that. Skip whatever doesn't actually deserve its own entry — this is a candidate list, not a mandate. Definitions I've already drafted (grounded in this KB's own text + web-checked for the general cultural/religious facts, sources noted) are filled in below, checkbox left for your review/edit — everything still unchecked and refs-only is still waiting to be drafted.)*

**2026-09-22 — 2 removed, not new entities after all:** `Sang Hyang Prajapati` and `Sang Hyang Atma` turned out to be honorific-prefixed forms of entities that already exist (`hyang_prajapati`, `atma`) — the resolver just couldn't connect them (`sang` strips fine, but the remainder "hyang prajapati" isn't independently a gazetteer/alias entry, so the whole strip attempt got abandoned). Fixed as 2 `force_merge` entries in `entity_resolution.json` instead of new definitions — real resolver bug, not a content gap. Needs a KB rebuild + Neo4j reload to take effect (not done yet, bundling it with the rest of this pass).

### Religious entities/beings (4)
- [x] **Bhuta** (`bhuta`) — refs: 16 — Bhuta (dari akar Sanskerta "menjadi/ada/wujud") merujuk pada unsur-unsur pembentuk alam semesta -- disebut Panca Maha Bhuta untuk lima unsurnya (tanah, air, api, udara, eter) -- sekaligus pada kekuatan elemental-alamiah itu sendiri (Bhuta Kala), yang dalam ajaran Hindu diyakini punya sisi baik dan buruk sehingga perlu diseimbangkan lewat ritual seperti Bhuta Yadnya, bukan sekadar "roh jahat" yang harus disingkirkan.
  - _source: KB definitions of akasa/apah/bayu/pretiwi/teja all describe Panca Maha Bhuta; gelar_sanga's def references "Bhuta Kala"; web: [RRI.co.id](https://rri.co.id/denpasar/regional/2091404/arti-kata-bhuta-kala), [PHDI Pusat](http://phdi.parisada.or.id/artikel.php?id=memahami-kehadiran-bhuta-kala) on Bhuta Kala's dual (not purely negative) nature._
- [x] **Wisnu** (`wisnu`) — refs: 9 — Wisnu (Dewa Wisnu) adalah salah satu dari Panca Dewata (lima manifestasi Ida Sang Hyang Widhi Wasa, bersama Iswara, Brahma, Mahadewa, dan Siwa) dan bagian dari Trimurti (bersama Brahma dan Siwa), berperan sebagai pemelihara (sthiti); di Bali, Wisnu berstana di Pura Puseh, salah satu pura Kahyangan Tiga.
  - _source: KB's own `panca_dewata`, `sthiti`, `pura_puseh`, `tirtha_amertha` definitions already state all of this — this entry just consolidates it under Wisnu's own name._
- [x] **Dewi** (`dewi`) — refs: 8 — Dewi adalah sebutan umum untuk manifestasi Tuhan (Ida Sang Hyang Widhi Wasa) dalam wujud perempuan (padanan laki-laki: Bhatara/Dewa) -- misalnya Dewi Sri (dewi kesuburan dan padi) atau Dewi Durga (dipuja di Pura Dalem, berkaitan dengan siklus kematian).
  - _source: KB's `bhatari` ("sebutan untuk dewi..."), `anggapan_ani_ani_atau_ketam` (Dewi Sri), `pura_dalem` (Dewi Durga)._
- [x] **Tuhan** (`tuhan`) — refs: 7 — Tuhan, dalam ajaran Hindu Bali disebut formal sebagai Ida Sang Hyang Widhi Wasa, adalah Yang Maha Esa yang bermanifestasi dalam berbagai wujud dewa (Bhatara) dan dewi (Bhatari); istilah ini dipakai hampir berdampingan dengan Brahman (realitas tertinggi) dalam beberapa konteks -- misalnya saat upacara Mapulang Lingga "menstanakan" Tuhan/Brahman ke dalam diri seorang sulinggih.
  - _source: KB's `bhatara`/`bhatari` ("sebutan untuk dewa/dewi atau manifestasi Tuhan"), `upacara_mapulang_lingga` ("Tuhan atau Brahman di-stanakan... dalam diri sendiri")._

### Rituals / ceremonies (5)
- [x] **Bhuta Yadnya** (`bhuta_yadnya`) — refs: 8 — Bhuta Yadnya adalah salah satu dari Panca Yadnya (lima jenis persembahan suci Hindu Bali), yaitu persembahan untuk menetralisir dan menyelaraskan kekuatan unsur-unsur alam (Bhuta Kala) agar harmonis -- bukan sekadar mengusir "roh jahat". Dalam konteks Ngaben, hari-hari yang baik untuk Bhuta Yadnya (seperti sasih Kaenem dan Kapitu) berbeda dari hari-hari yang baik untuk Pitra Yadnya seperti Ngaben itu sendiri.
  - _source: KB's `dewasa_madya`, `sasih_kaenem`, `sasih_kapitu`, `banten_bebangkit_atau_pulagembal`; web: [Paduarsana](https://paduarsana.com/2012/06/07/yadnya-dalam-hindu-panca-yadnya/) on the Panca Yadnya framework._
- [x] **Dewa Yadnya** (`dewa_yadnya`) — refs: 6 — Dewa Yadnya adalah salah satu dari Panca Yadnya, yaitu persembahan yang ditujukan kepada para dewa sebagai manifestasi Ida Sang Hyang Widhi Wasa. Dalam konteks Ngaben, hari baik untuk Dewa Yadnya (seperti sasih Kapat) berbeda dari hari baik untuk Pitra Yadnya seperti Ngaben, dan arah pradaksina (memutar searah jarum jam) yang dipakai dalam upacara Dewa Yadnya di pura berlawanan dengan arah prasawya yang dipakai saat memutar Bade dalam prosesi Ngaben.
  - _source: KB's `bhatara_bhatari`, `sasih_kapat`, `wayang` (sentence 2380, bade↔prasawya vs dewa yadnya↔pradaksina)._
- [x] **Upacara Atiwa-Tiwa** (`upacara_atiwa_tiwa`) — refs: 4 — Upacara Atiwa-Tiwa adalah rangkaian upacara kematian dalam Hindu Bali, mencakup berbagai bentuk pelaksanaan -- mulai dari yang sederhana seperti Nywasta hingga yang menggunakan jenazah fisik penuh seperti Ngaben Cara Yama Purwana Tatwa -- bertujuan menghaturkan pengorbanan suci (yadnya) bagi mendiang dan memutus ikatan jasad dengan roh lewat sarana seperti Tirtha Pangentas.
  - _confirmed valid/distinct entity by user 2026-09-22, not a `ngaben` alias. Separately: the existing `ngaben` entity's alias "pangabenan jenis masing-masing" (which I'd cited while flagging this) turned out to be a real pre-existing KB bug, not a legitimate alias — traced to sentence 2455's context ("...pangabenan terdiri dari berbagai jenis, masing-masing mempunyai nama sendiri-sendiri" = "pangabenan comes in various types, each with its own name"), a summary/meta sentence that a manual_addition mis-extracted as if "pangabenan jenis masing-masing" ("pangabenan each type") were itself a nameable entity. Fixed via `review_decisions.json` ("2455|pangabenan jenis masing-masing|nama sendiri-sendiri": "reject") — same mechanism as every other relation-extraction fix this session, not something new._
  - _source: KB's `pengorbanan_suci`, `tirtha_pangentas_atiwa_tiwa`, `atiwa_tiwa_asti_vedana`._
- [x] **Madiksa** (`madiksa`) — refs: 2 — Madiksa (disebut juga Mawinten) adalah upacara pentahbisan/penyucian yang menjadikan seorang rohaniwan Hindu Bali sah menyandang gelar Pandita/Sulinggih, sehingga berwenang memuja Ida Sang Hyang Widhi Wasa, membuat tirtha (air suci), dan memimpin upacara Panca Yadnya termasuk Ngaben.
  - _source: KB's `pandita` ("telah disucikan melalui upacara madiksa/mawinten...")._
- [x] **Panca Yadnya** (`panca_yadnya`) — refs: 2 — Panca Yadnya adalah kerangka lima jenis persembahan suci wajib dalam Hindu Bali: Dewa Yadnya (kepada dewa), Rsi Yadnya (kepada pendeta/orang suci), Pitra Yadnya (kepada leluhur/roh, termasuk Ngaben), Manusa Yadnya (upacara daur hidup manusia), dan Bhuta Yadnya (menyelaraskan kekuatan alam). Dalam konteks Ngaben, seorang Pandita berwenang memimpin berbagai upacara Panca Yadnya, termasuk Ngaben sebagai bagian dari Pitra Yadnya.
  - _source: KB's `pandita`; web: [Paduarsana](https://paduarsana.com/2012/06/07/yadnya-dalam-hindu-panca-yadnya/) confirms the 5-category framework and each category's target._

### Caste / social class (6)
- [x] **Brahmana** (`brahmana`) — refs: 6 — Brahmana adalah wangsa/kasta tertinggi dalam sistem catur wangsa Hindu Bali, secara tradisional golongan pendeta (sulinggih); dalam konteks Ngaben, jenazah dari kalangan Brahmana/Sulinggih menggunakan petulangan (wadah kremasi) berbentuk Lembu (sapi).
  - _source: KB's `gria`, `pemangku_kawitan_setempat`, `perbandingan_kepala_lembu` (Lembu petulangan for Brahmana/Sulinggih); web: [detik.com Bali](https://www.detik.com/bali/budaya/d-7373239/mengenal-tingkatan-sosial-di-bali-brahmana-ksatria-waisya-sudra), [Wikipedia: Sistem kasta Bali](https://id.wikipedia.org/wiki/Sistem_kasta_Bali) confirm Brahmana = highest/priestly caste._
- [x] **Ksatria** (`ksatria`) — refs: 4 — Ksatria adalah wangsa/kasta kedua dalam sistem catur wangsa Hindu Bali, secara tradisional golongan bangsawan/prajurit; istilah "Upacara Palebon" (bentuk halus dari ngaben) umumnya dipakai khusus untuk kalangan Ksatria/bangsawan.
  - _source: KB's `upacara_palebon_ngaben` ("penyebutan lebih halus... untuk kalangan bangsawan/ksatria"); web sources above confirm Ksatria = warrior/noble caste, second rank._
- [x] **Wangsa Sudra Jadma** (`wangsa_sudra_jadma`) — refs: 3 — Wangsa Sudra Jadma (Sudra) adalah wangsa/kasta keempat -- golongan masyarakat umum -- dalam sistem catur wangsa Hindu Bali; dalam konteks Ngaben, jenazah dari kalangan ini lazim menggunakan petulangan berbentuk Gedarba/Gadarba (beruang hitam), berbeda dari Lembu (Brahmana/Sulinggih) atau Singa (kalangan raja).
  - _source: KB's `gedarba` ("digunakan oleh wangsa sudra jadma atau masyarakat umum... berbeda dengan Lembu untuk Pendeta/Sulinggih atau Singa untuk kalangan raja")._
- [x] **Wesia** (`wesia`) — refs: 2 — Wesia (Waisya) adalah wangsa/kasta ketiga dalam sistem catur wangsa Hindu Bali, secara tradisional golongan pedagang; dalam konteks Ngaben, jenazah dari golongan Wesia lazim menggunakan petulangan berbentuk Gajah Mina (gabungan gajah dan ikan).
  - _source: KB's `gajah_mina` ("umumnya digunakan oleh golongan Wesia"); web sources above confirm Wesia/Waisya = merchant caste, third rank._
- [x] **Wangsa** (`wangsa`) — refs: 2 — Wangsa adalah istilah umum untuk golongan kasta/klan/garis keturunan dalam masyarakat Hindu Bali -- mencakup baik keempat kasta utama catur wangsa (Brahmana, Ksatria, Wesia, Sudra) maupun klan/garis keturunan spesifik seperti wangsa Pande; dalam konteks Ngaben, wangsa seseorang turut menentukan bentuk petulangan (wadah kremasi) yang dipakai.
  - _source: KB's `gedarba` (wangsa sudra jadma), `macan` (wangsa Pande) — both tie wangsa to petulangan shape._
- [x] **Pasek** (`pasek`) — refs: 2 — Pasek adalah salah satu kelompok klan/garis keturunan (soroh) besar dalam masyarakat Bali; dalam konteks Ngaben, jenazah dari kalangan Pasek -- bersama kalangan raja-raja -- lazim menggunakan petulangan berbentuk Singa.
  - _source: KB's `singa` ("umumnya dipakai oleh kalangan raja-raja atau warga Pasek"). Deliberately not claiming Pasek's catur-wangsa rank — that's a genuinely disputed point in real Balinese society (Pasek/Pande groups have long-running claims to non-Sudra status) and the corpus itself never asserts one either._

### Ceremony stages/steps (8 — 3 more turned out to be alias fixes, see below)
- [x] **Matur Piuning** (`matur_piuning`) — refs: 4 — Matur Piuning adalah tindakan menghaturkan piuning (permakluman/pemberitahuan formal) secara langsung -- misalnya oleh Tegteg yang diiring ke Pura Dalem untuk matur piuning dan memohon atma yang akan diaben. Menjadi tahap awal dalam rangkaian upacara Atiwa-tiwa Asti Vedana, sebelum pembakaran dan nganyut.
  - _source: KB's `tegteg`, `atiwa_tiwa_asti_vedana`; sentence 258, 271._
- [x] **Piuning** (`piuning`) — refs: 4 — Piuning berarti permakluman atau pemberitahuan formal, dihaturkan kepada sosok niskala (seperti Sedahan Setra, penunggu setra/kuburan) sebagai bagian dari rangkaian upacara sebelum penguburan atau pembakaran jenazah -- misalnya pada Ngelungah dan Ngulapin.
  - _source: KB's `sedahan_setra`, `upacara_ngelungah`._
- [x] **Pengutangan** (`pengutangan`) — refs: 4 — Pengutangan adalah sebutan untuk hari pelaksanaan pembakaran jenazah (juga disebut hari Pelebon) dalam rangkaian Ngaben. Pada hari ini, jenazah yang telah disemayamkan (misalnya di Bale Gede) diawali dengan upacara Ngaskara dan Caru Pengelambuk sebelum dinaikkan ke usungan menuju setra.
  - _source: KB's `bale_gede`, `caru_pengelambuk`; sentence 217._
- [x] **Ngajum** (`ngajum`) — refs: 4 — Ngajum adalah proses pembuatan sekah (representasi simbolis atma mendiang, misalnya berbentuk sangge/lingga) yang dilakukan di pawedan, dipakai khusus dalam upacara tingkat lanjut seperti Mamukur atau Sekah Kurung.
  - _source: KB's `pawedan`, `sekah_sangge`._
- [x] **Mabersih Mati** (`mabersih_mati`) — refs: 2 — Mabersih Mati (disebut juga Pabersihan Mati, Melelet, atau Ngelelet) adalah tahap penyucian jenazah pasca-kematian dalam rangkaian Ngaben -- dibedakan dari Pabersihan Hidup (penyucian semasa hidup) -- mencakup prosesi seperti pengerikan kuku (menghilangkan Dasa Mala) dan peletakan daun intaran pada alis jenazah, dilaksanakan sebelum tahap Ngeringkes (pembungkusan jenazah).
  - _source: KB's `daun_intaran`, `pangringkes`, `pengerikan_kuku_mutlak` (all three independently name the Melelet/Ngelelet/Pabersihan Mati cluster and the Hidup/Mati distinction)._
- [x] **Nguyeg** (`nguyeg`) — refs: 2 — Nguyeg adalah istilah untuk prosesi pembakaran jasad dalam Ngaben -- momen ketika unsur-unsur Panca Maha Bhuta pada diri mendiang (teja/api, bayu/angin, akasa/eter) dikembalikan kepada Sang Pancamahabutha (asalnya) melalui api pembakaran.
  - _source: KB's `teja` (the only source that mentions it — kept deliberately close to that wording rather than asserting a more specific technical meaning I couldn't verify)._
- [x] **Mlaspas Kajang** (`mlaspas_kajang`) — refs: 2 — Mlaspas Kajang adalah upacara penyucian/pentasbihan (mlaspas) atas Kajang (kain berisi aksara suci pembungkus jenazah) sebelum digunakan. Dilaksanakan bersama Manah Tirtha Ening, sebelum Upacara Ngaskara yang mengawali rangkaian Pelebon/Pabersihan.
  - _source: KB's `upacara_ngaskara`, `kajang`._
- [x] **Ngelinggihang** (`ngelinggihang`) — refs: 1 — Ngelinggihang berarti "menstanakan/mendudukkan" sesuatu yang suci ke tempatnya (dari kata "linggih", kedudukan/singgasana) -- misalnya dalam "Ngelinggihang Dewa Hyang" (mengukuhkan leluhur yang telah diaben ke kedudukannya sebagai Dewa Hyang) atau dalam Upacara Mapulang Lingga (menstanakan Tuhan/Brahman ke dalam diri seorang sulinggih).
  - _source: KB's `upacara_mapulang_lingga`; sentence 271 ("...hingga upacara ngelinggihang dewa hyang")._

**3 removed, not new entities — same alias-fix pattern as before:** `Ngeringkes` (bare verb form of the existing `pangringkes` entity — its own definition already says "disebut juga Upacara Pangringkesan", and a source-sentence note independently confirms the same concept), `Pasucian` (the existing `pabersihan` entity's definition literally says "juga disebut Pasucian"), and `Kerik Kuku` (bare form of the existing `pengerikan kuku` entity, same nail-scraping ritual). All 3 fixed as `force_merge` entries.

### Ritual tools/materials (14 — 2 more turned out to be alias fixes, see below)
- [x] **Alang-Alang** (`alang_alang`) — refs: 6 — Alang-alang adalah jenis rumput (Imperata cylindrica) yang daunnya dipakai sebagai salah satu isian pengawak (perlambang badan mendiang) dalam Ngaben -- misalnya 54 atau 108 lembar daun alang-alang dimasukkan ke dalam jun pere bersama air dan kayu cendana.
  - _source: KB's `isi_pengawak`, `jun_pere`, `kayu_cendana`; sentence 1465._
- [x] **Bunga Teratai** (`bunga_teratai`) — refs: 4 — Bunga Teratai (lotus) adalah bunga yang menjadi simbol kesucian tertinggi dan tempat suci para dewata dalam berbagai sarana upacara Hindu Bali -- misalnya sebagai elemen utama Bunga Tunjung Putih di dalam kawangen, atau sebagai dasar simbolisme Padma dalam sesajen Lis Bale Gading.
  - _source: KB's `bunga_tunjung_putih`, `padma`._
- [x] **Kekitir** (`kekitir`) — refs: 4 — Kekitir adalah sarana upacara berupa lembaran kertas bersurat (aksara suci), dipakai bersama Ulantaga/Walantaga dalam pembuatan Tirtha Pangentas, dan menjadi salah satu isian pengawak (perlambang badan mendiang) dalam rangkaian Ngaben.
  - _source: KB's `isi_pengawak`, `ulantaga`._
- [x] **Ukur** (`ukur`) — refs: 4 — Ukur berarti satuan pengukuran tradisional berbasis proporsi tubuh manusia (seperti depa/rentangan tangan, asta, dan nyari) yang dipakai dalam seni bangunan sarana upacara Hindu Bali (disebut abah bangun) -- misalnya menentukan proporsi kepala Petulangan (wadah kremasi) berbentuk Lembu (2:1:1) atau Singa (3:2:2), dengan keyakinan ketaatan pada ukuran ini memberi "jiwa" pada sarana yang dibuat.
  - _source: KB's `perbandingan_kepala_lembu`, `perbandingan_kepala_singa`._
- [x] **Tumpeng** (`tumpeng`) — refs: 2 — Tumpeng adalah nasi berbentuk kerucut, salah satu bentuk sesajen/persembahan (ayaban) yang dihaturkan kepada Bhatara, atma, maupun leluhur dalam hampir setiap tahapan upacara Pitra Yadnya/Ngaben.
  - _source: KB's `ayaban`._
- [x] **Ilih** (`ilih`) — refs: 2 — Ilih adalah kipas tradisional yang dipakai sebagai sarana untuk mendekati/melambangkan unsur bayu (angin/napas) pada lingga sarira Sang Pitara (wujud halus roh leluhur) dalam rangkaian Ngaben.
  - _source: KB's `bayu`._
- [x] **Tabunan** (`tabunan`) — refs: 2 — Tabunan adalah asap pembakaran/pengasapan tradisional yang pada masa lalu (sebelum dikenalnya formalin) dipakai untuk mengatasi bau jenazah yang disemayamkan beberapa hari sebelum upacara Ngaben.
  - _source: KB's `formalin`._
- [x] **Boma** (`boma`) — refs: 2 — Boma (Karang Boma, dari "Boma Narakasura", putra Dewa Wisnu dan Dewi Pertiwi -- berarti "putra Bumi" dalam bahasa Sanskerta) adalah motif wajah raksasa pelindung dalam seni ukir Bali, umumnya diukir di atas gerbang pura; dalam konteks Ngaben juga dipakai sebagai topeng hiasan dekoratif pada sarana seperti Bade, Wadah, atau Adegan.
  - _source: KB's `hiasan`; web: [Wikipedia: Karang boma](https://id.wikipedia.org/wiki/Karang_boma), [Bali Express](https://baliexpress.jawapos.com/balinese/25/12/2017/begini-makna-karang-boma-yang-selalu-ada-di-candi-kurung-jeroan-pura/)._
- [x] **Api Takep** (`api_takep`) — refs: 2 — Api Takep adalah sarana berupa api yang diletakkan di bawah pepaga (alas memandikan jenazah), berfungsi sebagai lambang kesaksian (upasaksi) kepada Hyang Agni (Sang Hyang Agni/Dewa Api) dalam rangkaian Ngaben.
  - _source: KB's `hyang_agni`._
- [x] **Kuncup Teratai** (`kuncup_teratai`) — refs: 2 — Kuncup teratai (bunga teratai yang belum mekar) adalah sarana yang digosokkan pada bibir jenazah sebagai pengganti kikir, dipakai dalam rangkaian upacara Potong Gigi simbolis pasca-kematian bila bibir jenazah terkatup rapat.
  - _source: KB's `jenazah_bibir`._
- [x] **Kikir** (`kikir`) — refs: 2 — Kikir adalah alat pengikir/pengasah (rasp/file) yang secara normal dipakai dalam rangkaian upacara Potong Gigi simbolis pasca-kematian pada jenazah -- digantikan oleh kuncup teratai bila bibir jenazah terkatup rapat sehingga kikir tak dapat dipakai langsung.
  - _source: KB's `jenazah_bibir`._
- [x] **Bubur Pirata** (`bubur_pirata`) — refs: 2 — Bubur Pirata adalah bubur yang dihaturkan sebagai salah satu banten (sesajen) bagi mendiang, biasa disajikan bersama Nasi Angkeb dalam rangkaian upacara Ngaben.
  - _source: KB's `nasi_angkeb`. Kept minimal -- the corpus only shows it co-occurring with Nasi Angkeb, no fuller description found._
- [x] **Nyiru** (`nyiru`) — refs: 2 — Nyiru adalah nampan anyaman bambu tradisional (umum dipakai untuk menampi beras); dalam konteks Ngaben, nyiru bertabing tinggi (disebut tembong) menjadi alas bagi Panguryagan, alat upakara berisi bermacam-macam ramuan.
  - _source: KB's `panguryagan`._
- [x] **Boreh** (`boreh`) — refs: 2 — Boreh adalah bubuk atau lulur wangi tradisional (misalnya boreh miik/bubuk cendana) yang dioleskan pada tubuh jenazah saat memandikannya (Nyiramang Layon), bertujuan menghilangkan bau tak sedap dan membuat tubuh jenazah berbau harum.
  - _source: KB's `penggunaan_wewangian`._

**2 removed, not new entities — same alias-fix pattern as before:** `Walantaga` (the existing `ulantaga` entity's definition literally says "disebut juga walantaga") and `Umbi Gadung` (the existing `umbi_sikapa_sekapa` entity's definition opens with "Umbi gadung mentah yang dipakai...", and its source sentence itself writes "umbi sikapa/sekapa (umbi gadung)"). Both fixed as `force_merge` entries.

### Philosophical concepts (10)
- [x] **Brahman** (`brahman` — new, not yet in `entities.json`) — refs: 5 — Brahman adalah konsep realitas tertinggi/absolut dalam filsafat Hindu -- dalam sumber ini digambarkan sebagai "sang pencipta" (tujuan akhir mendiang, yang jenazahnya dimasukkan lewat teben pepaga agar lebih cepat menemuinya) dan sebagai wujud yang menyatu dengan jiwa/atma saat moksa tercapai (paratma/Brahman).
  - source, sentence 3355: "...jenazah yang masuk melalui teben dari pepaga, memiliki makna agar orang yang meninggal tersebut lebih cepat menemui **brahman (sang pencipta)**, sesuai dengan kisah yang disebutkan dalam kitab mahabarata."
  - source, sentence 1609: "moksa adalah menjadi satunya jiwa/atma dengan **paratma/brahman**, serta kembalinya pula unsur badan manusia ke asalnya yakni badannya bhuwana agung (pancamahabutha)."
- [x] **Numitis** (`numitis`) — refs: 4 — Numitis berarti bereinkarnasi atau lahir kembali ke dunia. Dalam konteks Ngaben, berbagai sarana dan prosesi (seperti pemasangan paku besi di lengan jenazah, atau pengerikan kuku untuk menghilangkan Dasa Mala) dimaksudkan agar mendiang kelak numitis dengan kondisi baik -- misalnya bertulang kuat atau senantiasa berbau harum.
  - _source: KB's `besi_paku`, `pengerikan_kuku_mutlak`, sentence 3728 (wewangian↔numitis)._
- [x] **Dasa Mala** (`dasa_mala`) — refs: 4 — Dasa Mala secara harfiah berarti "sepuluh kekotoran/cacat" -- sepuluh sifat/perbuatan tercela yang mengotori jiwa menurut ajaran Hindu. Dalam konteks Ngaben, Dasa Mala pada jenazah dibersihkan lewat prosesi seperti pengerikan kuku pada tahap Melelet/Pabersihan Mati, agar tidak lagi melekat pada roh saat kelak numitis (bereinkarnasi).
  - _source: KB's `pengerikan_kuku`, `pengerikan_kuku_mutlak` (both already gloss it as "kekotoran rohani")._
- [x] **Swah Loka** (`swah_loka`) — refs: 2 — Swah Loka adalah alam tertinggi dalam kosmologi Tri Loka Hindu (bersama Bhur Loka/alam manusia dan Bhuwah Loka/alam antara) -- alam para dewa, alam spiritual murni. Dalam konteks Ngaben, upacara pengabenan bertujuan menyucikan roh (atman) mendiang agar terlepas dari ikatan Panca Maha Bhuta sehingga dapat menuju alam Swah Loka.
  - _source: KB's `upacara_pengabenan`, `antah_karana_sarira`; web: [PHDI Pusat](https://parisada.or.id/bhur-bhuvah-svah-tiga-kesadaran-alam/) on Tri Loka._
- [x] **Pitraloka** (`pitraloka`) — refs: 2 — Pitraloka adalah alam khusus tempat bersemayamnya para pitara (roh leluhur yang telah disucikan) -- dilambangkan misalnya lewat Bale Salunglung sebagai tempat badan halus mendiang. Dalam konteks Ngaben, upacara seperti Ngangsen bertujuan menstabilkan (pangenteg linggih) kedudukan Sang Pitara di Pitraloka hingga upacara Atma Wedana yang sesungguhnya dapat dilaksanakan.
  - _source: KB's `bale_salunglung`, `ngangsen`._
- [x] **Upasaksi** (`upasaksi`) — refs: 2 — Upasaksi berarti saksi -- dalam konteks ritual, saksi ilahi/spiritual atas jalannya sebuah upacara. Dalam konteks Ngaben, api pembakaran jenazah dipersembahkan kepada Hyang Agni sebagai upasaksi, misalnya lewat sarana Api Takep yang diletakkan di bawah pepaga sebagai lambang kesaksian tersebut.
  - _source: KB's `hyang_agni`._
- [x] **Bwah Loka** (`bwah_loka`) — refs: 1 — Bwah Loka (Bhuwah Loka) adalah alam antara dalam kosmologi Tri Loka Hindu -- di atas Bhur Loka (alam manusia/fisik) namun di bawah Swah Loka (alam dewa) -- tempat roh berstatus preta (belum sepenuhnya suci) transit sebelum kedudukannya terangkat menjadi pitara dan dapat menuju Swah Loka.
  - _source: KB's `antah_karana_sarira`; web: [PHDI Pusat](https://parisada.or.id/bhur-bhuvah-svah-tiga-kesadaran-alam/) on Tri Loka._
- ~~**Suksmasarira**~~ — **removed, confirmed by user 2026-09-22 to be the same concept as `lingga_sarira_pitara`.** Fixed as a `force_merge` entry ("suksmasarira" → "lingga sarira pitara"), same as the other alias fixes.
  - _source: KB's `lingga_sarira_pitara`, `ngangsen`._
- [x] **Pangenteg Linggih** (`pangenteg_linggih`) — refs: 1 — Pangenteg Linggih berarti "menstabilkan/meneguhkan kedudukan (linggih)" -- sebuah tindakan ritual, bukan upacara mandiri, dilakukan misalnya dalam Ngangsen untuk mengukuhkan kedudukan Sang Pitara di Pitraloka sebelum Atma Wedana yang sesungguhnya dapat dilaksanakan.
  - _source: KB's `ngangsen`._

**Ether removed** — turned out to be the plain English gloss the KB's own `akasa` and `lingga_sarira_pitara` definitions already use ("akasa (ether/ruang)"), not a separate concept. Fixed as a 3rd `force_merge` entry in `entity_resolution.json`, same as the Sang Hyang pair.

### Customary-law concepts (9)
- [x] **Leteh** (`leteh`) — refs: 4 — Leteh berarti kotoran atau kekotoran spiritual. Dalam konteks Ngaben, leteh yang melekat pada sawa (jenazah) akibat kematian perlu disucikan agar tidak memancar keluar dan menular kepada yang lain, misalnya lewat upakara Diuskamaligi.
  - _source: KB's `ayaban_upakara_diuskamaligi`, `diuskamaligi` (both independently gloss it as "kotoran/kekotoran spiritual")._
- [x] **Daksinayana** (`daksinayana`) — refs: 4 — Daksinayana adalah periode dalam kalender Hindu Bali ketika matahari berada di belahan selatan bumi -- meliputi sasih Kalima, Kaenem, dan Kapitu. Sasih Kalima baik untuk Dewa dan Manusa Yadnya (alam dewa dan bhatara sama-sama terbuka); sasih Kaenem dan Kapitu sangat baik untuk Bhuta Yadnya, namun untuk Pitra Yadnya seperti Ngaben tergolong dewasa madya (sedang-sedang saja).
  - _source: `ngaben-merge-cleaned.txt` lines 224-225 ("c. Daksinayana", the authoritative A/B/C classification — see the Uttarayana/Indrayana note below), cross-checked against KB's `sasih_kaenem`, `sasih_kapitu`. Revised 2026-09-22 to use the fuller source passage instead of just the two sasih entities' own definitions._
- [x] **Sebel** (`sebel`) — refs: 2 — Sebel berarti kekotoran (spiritual). Dalam konteks Ngaben, kematian dipercaya membuat sebelas bidang pada diri manusia (bhuwana alit) mudah ditimpa suasana sebel, sehingga perlu disucikan melalui rangkaian upacara.
  - _source: KB's `bhuwana_alit`. Close in meaning to Leteh but kept separate — neither the corpus nor this entry claims they're identical, just near-synonyms anchored to different specific contexts (sawa itself vs. the person's bhuwana alit)._
- [x] **Purnama** (`purnama`) — refs: 2 — Purnama adalah hari bulan purnama (bulan penuh) dalam kalender Bali. Jenazah yang telah melewati Purnama dan Tilem sekurang-kurangnya satu bulan disebut berstatus Masekeh, salah satu syarat sebelum diupacarai Ngaben.
  - _source: KB's `masekeh`; sentence 1123._
- [x] **Tilem** (`tilem`) — refs: 2 — Tilem adalah hari bulan mati (bulan baru) dalam kalender Bali. Jenazah yang telah melewati Purnama dan Tilem sekurang-kurangnya satu bulan disebut berstatus Masekeh, salah satu syarat sebelum diupacarai Ngaben.
  - _source: KB's `masekeh`; sentence 1123._
- [x] **Guru Tiga** (`guru_tiga`) — refs: 2 — Guru Tiga (secara harfiah "tiga guru/pemimpin") adalah sebutan untuk pimpinan warga dalam struktur sosial adat Bali. Dalam konteks Ngaben, Guru Tiga turut hadir bersama prajuru desa dan pendeta dalam upacara Penebusan, permohonan maaf atas kesalahan mendiang semasa hidupnya terhadap masyarakat.
  - _source: KB's `penebusan`._
- [x] **Uttarayana** (`uttarayana`) — refs: 2 — **corrected 2026-09-22, see note:** Uttarayana adalah periode dalam kalender Hindu Bali ketika matahari bergerak ke utara dari tengah bulatan bumi -- meliputi sasih Kadasa, Dyestha, Asada, Kasa, Karo, dan Katiga -- umumnya baik untuk Pitra Yadnya karena pintu alam Wisnu, pitra, dan yama sedang terbuka. Khusus sasih Kadasa, pembakaran jenazah dipantang karena dianggap masa pesamuhan para dewa.
  - _source: `ngaben-merge-cleaned.txt` lines 220-221 ("a. Uttarayana"), cross-checked against KB's `sasih_kadasa`._
  - _**correction note:** my first draft of this entry wrongly included sasih Kapat as part of Uttarayana (conflated from `sasih_kadasa`'s and `sasih_kapat`'s definitions, which both mention solar-direction language without me checking the actual full source classification). User caught this. Kapat actually belongs to **Indrayana**, a third category distinct from both Uttarayana and Daksinayana — see below. Rewritten from the raw source's own "A. Berdasarkan Sasih" a/b/c breakdown (lines 218-225) rather than reconstructed piecemeal from individual sasih entities._
- [x] **Indrayana** (`indrayana`) — refs: 2 — Indrayana adalah periode dalam kalender Hindu Bali ketika matahari berada di tengah-tengah belahan bumi -- terjadi dua kali: pertama saat matahari datang dari utara (sasih Kapat), kedua saat matahari datang dari selatan (sasih Kawulu). Menurut lontar-lontar Wariga, pada saat ini alam dewa sedang terbuka, sehingga sasih Kapat sangat baik untuk Dewa Yadnya, sedangkan sasih Kawulu baik untuk Bhuta Yadnya.
  - _source: `ngaben-merge-cleaned.txt` lines 222-223 ("b. Indrayana") — user supplied this passage directly. It's a genuinely distinct third category, not an alternate name for Uttarayana as I'd guessed — confirmed by the source's own explicit three-way a/b/c split (Uttarayana / Indrayana / Daksinayana)._
- [x] **Sukra** (`sukra`) — refs: 2 — Sukra adalah nama hari dalam sistem penanggalan Bali yang bertepatan dengan hari Jumat (dari bahasa Sanskerta, terkait planet Venus). Hari Sukra yang jatuh pada Wuku Kuningan termasuk dewasa (hari) yang diperbolehkan untuk melaksanakan Ngaben.
  - _source: KB's `wuku_kuningan`._

### Ritual buildings (4)
- [x] **Merajapati** (`merajapati`) — refs: 4 — Merajapati (Pura Merajapati) adalah salah satu pura yang berperan dalam rangkaian Ngaben, disebutkan berdampingan dengan Pura Dalem -- misalnya sebagai salah satu dari tiga tujuan banten piuning pada Upacara Ngelungah (bersama Pura Dalem dan Bangbang Rare).
  - _flag: likely related to (maybe the same site as) `hyang_prajapati`'s "Pura Prajapati" and the unresolved gazetteer term "pura mrajapti" seen in this build's unresolved-entities list -- three spellings of what may be one temple. Didn't merge myself since none of the 3 sources explicitly equates them the way the Pasucian/pabersihan case did; your call._
  - _source: KB's `pura`, `upacara_ngelungah`._
- [x] **Bangbang Rare** (`bangbang_rare`) — refs: 2 — Bangbang Rare (secara harfiah "lubang/liang bayi") adalah tempat pemakaman khusus untuk bayi atau anak yang meninggal sebelum berumur tiga bulan pada Upacara Ngelungah -- salah satu dari tiga tujuan banten piuning (bersama Pura Dalem dan Merajapati) sebelum jenazah dipendam tanpa pembakaran.
  - _source: KB's `upacara_ngelungah`._
- [x] **Pelangkiran** (`pelangkiran`) — refs: 1 — Pelangkiran adalah pelinggih (tempat pemujaan) kecil, biasa dipasang menempel di dinding rumah, tempat memuja roh leluhur yang masih berstatus pitra (belum sepenuhnya disucikan sebagai bhatara/bhatari). Dalam konteks Ngaben, pitra yang diupacarai lewat Ngangsen (upacara sementara) dipuja di pelangkiran, sebelum kedudukannya terangkat dan dipindah ke Pamrajan Rong Tiga lewat Atma Wedana yang sesungguhnya.
  - _source: KB's `ngangsen`._
- [x] **Pamrajan Rong Tiga** (`pamrajan_rong_tiga`) — refs: 1 — Pamrajan Rong Tiga adalah tempat suci keluarga (pamrajan) berstruktur tiga rong (ruang/bilik), tempat leluhur yang telah sepenuhnya disucikan dan berstatus bhatara/bhatari dipuja -- jenjang di atas pelangkiran, tempat pitra yang belum sepenuhnya disucikan masih dipuja.
  - _source: KB's `ngangsen`._

### Misc — one-off categories (5)
- [x] **Yama Purwana Tattwa** (`yama_purwana_tattwa`) — refs: 2 — Yama Purwana Tattwa adalah nama sebuah lontar (naskah suci tradisional Bali) yang menjadi rujukan bagi salah satu tata cara pelaksanaan Ngaben (Ngaben Cara Yama Purwana Tatwa), yaitu Ngaben yang dilakukan secara langsung menggunakan jenazah fisik (sawa).
  - _source: KB's `ngaben_cara_yama_purwana_tatwa`._
- [x] **Dadia** (`dadia`) — refs: 2 — Dadia adalah kelompok keluarga besar atau garis keturunan (klan) dalam masyarakat Hindu Bali yang berbagi satu tempat suci leluhur bersama (pamrajan/merajan/sanggah).
  - _source: KB's `pamrajan`._
- [x] **Prajuru** (`prajuru`) — refs: 2 — Prajuru adalah sebutan untuk pengurus/pejabat adat desa (prajuru desa) dalam struktur sosial Bali. Dalam konteks Ngaben, prajuru desa turut hadir bersama pendeta dan guru tiga (pimpinan warga) dalam upacara Penebusan, permohonan maaf atas kesalahan mendiang semasa hidupnya terhadap masyarakat.
  - _source: KB's `penebusan`._
- [x] **Tirtha Gangga** (`tirtha_gangga`) — refs: 2 — Tirtha Gangga adalah air suci yang secara simbolis dikaitkan dengan Sungai Gangga (Ganga), sungai suci dalam tradisi Hindu. Dalam konteks Ngaben, hanya Dewa Siwa yang diyakini berwenang menurunkan Tirtha Gangga, yang kemudian dipakai dalam pembuatan Tirtha Pangentas -- air suci penting untuk melepas ikatan roh mendiang.
  - _source: KB's `shiwa`._
- [x] **Wawu Lampus** (`wawu_lampus`) — refs: 2 — Wawu Lampus (secara harfiah "baru saja meninggal") adalah sebutan untuk tahap awal segera setelah kematian -- mencakup pembersihan awal jenazah di rumah dan penutupan jenazah dengan kain putih dari kepala hingga kaki -- dilakukan sebelum upacara resmi Nyiramang Layon (memandikan jenazah).
  - _source: KB's `jenazah_ditutup_kain_putih`._

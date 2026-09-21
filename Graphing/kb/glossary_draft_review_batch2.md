# Glossary Draft — Batch 2 (next 50 by mention frequency)

Same process as batch 1 (`glossary_draft_review.md`): drafts pulled from existing KB facts,
review/correct, check the box when done. `badan`/`manusia` already handled (excluded from
resolver, not shown here).

**Status:** DRAFT — nothing applied yet.

## Confident drafts (facts directly support these, low inference)

- [ ] `* Sesajen:  Persembahan yang dipersembahkan kepada mendiang, ditujukan untuk Ida Bhatara Kumara, meliputi nasi angkeb dan diuskamaligi.`
- [ ] `* Sekah:  Perlambang atau wujud mendiang, dialasi dulang dan diletakkan di balai pawedan.`
- [ ] `* Bale-Bale:  Bangunan yang berfungsi sebagai bale semanggen, diletakkan di pura atau merajan.`
- [ ] `* Pabersihan Hidup:  Upacara pembersihan yang dilakukan semasa hidup; pengerikan kuku tidak boleh dilakukan saat upacara ini.`
- [ ] `* Adegan:  Alat upakara yang melambangkan atma, diletakkan di ruang paturon di samping jenazah.`
- [ ] `* Abu:  Sisa jenazah yang telah dibakar, digiling di atas sesenden dan dimasukkan ke dalam klungah nyuh gading.`
- [ ] `* Eteh-Eteh:  Kelengkapan sawa yang terdiri dari angkeb baga/purus, angkeb rai, kain putih untuk saput, dan kawangen.`
- [ ] `* Lontar:  Naskah daun lontar yang merinci ajaran tentang pitra.`
- [ ] `* Layon:  Jenazah yang telah dimandikan dan digulung dengan kain putih, diletakkan di bale gede atau saka roras sebelum upacara.`
- [ ] `* Nyiramang Layon:  Prosesi memandikan layon (jenazah), dilakukan menggunakan tempat penusangan.`
- [ ] `* Kuburan:  Tempat penguburan jenazah, tempat sawa dan tulang belulang berada sebelum atau menggantikan pembakaran.`
- [ ] `* Pemangku:  Pemuka agama Hindu di Bali yang bertugas memohonkan tirtha, statusnya di bawah sulinggih.`
- [ ] `* Bhatari:  Sebutan untuk dewi atau manifestasi Tuhan dalam wujud perempuan, dipuja dengan daksina tapakan.`
- [ ] `* Kajang:  Kain berisi aksara suci yang diletakkan di plengkungan/paplengkungan jenazah, disambung dengan lancingan dan kain putih.`
- [ ] `* Lembu:  Sarana pembakaran jenazah berbentuk lembu (banteng), sejenis dengan bade, ditempatkan di bale pamuunan.`
- [ ] `* Pengawak:  Simbol pengganti jenazah, terdiri dari jun pere (periuk tanah kecil) dan unsur lain, berfungsi sama seperti sawa asli.`
- [ ] `* Pamrajan:  Tempat suci keluarga (merajan/sanggah), tempat sarana ritual seperti yeh panembak diletakkan.`
- [ ] `* Kawangen:  Sarana persembahyangan berbentuk anyaman daun, diletakkan di jenazah dan diisi dengan uang kepeng.`
- [ ] `* Tarpana:  Upacara persembahan tetesan air suci kepada leluhur, dilakukan oleh ida sang sadaka (pendeta).`
- [ ] `* Dulang:  Alas atau wadah berbentuk talam berkaki, digunakan sebagai alas sekah.`
- [ ] `* Galar:  Bilahan bambu yang digunakan sebagai alas sawa atau bahan bale.`
- [ ] `* Pura Dalem:  Pura yang berkaitan dengan upacara kematian, tempat ngerorasin diadakan dan mendiang berpamitan sebelum menuju alam roh.`
- [ ] `* Sesenden:  Alat atau tempat untuk menggiling/menghancurkan abu atau puspa asti.`
- [ ] `* Takir:  Wadah kecil dari daun, digunakan sebagai tempat sisig, daun dapdap, atau paes gedubang.`
- [ ] `* Tirta Panglukatan:  Air suci untuk penyucian (panglukatan), digunakan dalam ngaben titip dan untuk menyucikan banten.`
- [ ] `* Angenan:  Tempat meletakkan manah (perlambang hati/pikiran) dalam rangkaian sarana ritual.`
- [ ] `* Bale:  Bangunan/paviliun tradisional Bali, dapat dibuat dari galar (bilah bambu); ada banyak jenis sesuai fungsinya.`

## Thin evidence / philosophical terms — please write these yourself, not draft from my guess

These touch real Hindu philosophy (element/deity correspondences) where a wrong guess is
worse than no definition. Only 1 thin fact each, and I don't have the domain grounding to
confidently expand them:

- [ ] `Rasa` — only fact: "rasa berasal dari apah" (possibly one of the panca tan matra / sense elements — needs your knowledge)
- [ ] `Emas` — only fact: "emas berdewa dewa mahadewa" (metal-deity correspondence)
- [ ] `Perak` — only fact: "perak berdewa dewa iswara" (same pattern as emas)
- [ ] `Manah` — only fact: "manah diletakkan di angenan" (mind/heart concept)
- [ ] `Swadharma` — facts suggest "duty/obligation" but I'm not confident on nuance
- [ ] `Akasa` — pancamahabutha element (space/ether), only 1 fact
- [ ] `Bayu` — pancamahabutha element (wind/energy), only 1 fact
- [ ] `Klungah` — fact phrasing is odd ("tirtha berarti klungah" — reversed?), possible extraction error, please check source text directly

## Zero facts at all — need you to look at source text directly, I have nothing to draft from

`pura`, `perlambang`, `pabersihan_mati`, `ngulapin`, `pandita`, `ante`, `ayaban`,
`daun_intaran`, `niskala`, `teja`

## Possible skip candidates — same pattern as `badan`/`manusia`

`kaki_jenazah` and `kepala_jenazah` (foot/head of corpse) look like generic
body-part-location descriptors that got extracted as if they were named ritual terms,
same as the `badan`/`manusia` issue from before. Recommend the same treatment
(exclude from resolver rather than force a definition) unless you know these are
actually meaningful standalone terms in the ritual.

## How to apply (same as batch 1)

1. Edit/approve lines above.
2. Add approved lines to `Graphing/Data/ngaben-merge-cleaned.txt`'s "11. Glosarium" section.
3. For skip candidates: add to `exclude_from_resolution` in `Graphing/kb/entity_resolution.json`.
4. Rebuild: `python build_kb.py` (from `Graphing/kb/`).
5. Reload: `python Neo4/load_ngaben_to_neo4j.py --source kb` (from `Graphing/`).
6. Restart action server.

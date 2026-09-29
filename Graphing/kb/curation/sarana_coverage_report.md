# Sarana upacara / offering coverage: corpus vs KG (2026-09-29)

## Status after the 2026-09-29 fix (same 198 curated terms)

| | before | after |
|---|---|---|
| resolve to their own node | 83 | 133 |
| missing | 103 | 58 |
| own node AND linked to a ceremony/stage | 22 | 98 |
| `SARANA_RITUAL` nodes linked to a ceremony/stage (KG-wide) | 25 / 201 | 90 / 229 |
| wrong-entity fuzzy hits (§5) | 7 | 0 |

Done: §2 (Tirtha Pangentas ingredients, `DIPERLUKAN_UNTUK_MEMBUAT tirta pangentas`), §3 (Pabersihan
Mati items), §4 (Nyiramang Layon items), §5 (resolver: a lone short word no longer fuzzy-matches on a
consonant slip), §6 (aliases), the fix-option-4 question shape (`sarana` aspect in actions.py), and
the core banten of §1 (pejati, peras, suci, prayascita, tatebasan durmanggala, byakawonan, daksina,
tumpeng, lis bale gading, ... linked to sangaskara/pabasmian/ngulapin/atma wedana/mlaspas kajang/
pamerasan). Definitions of the banten the corpus only names come from the web and are tagged in
tuning/definition_sources.json for review.

Still missing (corpus names them without explaining them; no definition written): the rarer banten
of §1 (catursari, papendakan, pengadang-adang, panjang ilang, penyumpit areng, gambelan, rayunan,
salaran, pemanisan, canang oyodan/tambur/meraka, pras pengambyan/arepan, daksina lingga, jaja
bantal/pasung/uli, segehan manca warna as a named item), tirta penyeeb / pemerelina, toya anyar,
segau, balung-balung, bijaratus, karowista, kelepikan jepun, recedana (clashes with the Nywasta/
Recadana ngaben type), jarum/paku, pisau pengutik, asem, menjangan.

Corpus: `C:\Misc\Work\chatbot-project-madya-2026\chatbot-ngaben\Graphing\Data\ngaben-merge-cleaned.md`
(same content as `Graphing/data/ngaben-merge-cleaned.txt`; md line numbers below).
KG: `Graphing/kb/output/entities.json` + `relations.jsonl` (577 entities, 696 relations), non-LOW edges only.
"Resolves" means the bot's own `kb_resolver.KbResolver.resolve()`. "Linked" means a 1-hop edge
(relation or `broader`) to a `TAHAPAN_UPACARA` / `RITUAL_KEMATIAN` / `RITUAL` node.

Method: scraped (a) every numbered/lettered list item under an offering lead-in (banten, sesajen,
upakara, sarana, perlengkapan, persiapan, eteh-eteh, tirtha, sorohan, palet, pedagingan, ...), (b) every
offering head word + its modifiers anywhere (banten X, tirta X, canang X, daksina X, pripih X, ...),
(c) the Pabersihan Mati numbered items and the eteh-eteh table. 583 raw candidates, hand-curated to
198 distinct sarana/offering terms, each resolved against the KG.

## Headline

| | count |
|---|---|
| Curated sarana/offering terms from corpus | 198 |
| Resolve to their own KG node (exact/alias) | 83 (42%) |
| Missing from KG entirely | 103 (52%) |
| Resolve only by fuzzy/ortho match | 12 (7 of them to the WRONG entity) |
| Present AND linked to any ceremony/stage node | 22 of 83 |
| KG-wide: `SARANA_RITUAL` nodes linked to any ceremony/stage | 25 of 201 (12%) |
| Sarana linked directly to `ngaben` | 2 (`bade`, `panguryagan`, both `DIGUNAKAN_DALAM`) |

So: the *objects* are about half there; the *"used in which ceremony"* knowledge is almost absent.
"sarana apa yang digunakan untuk ngaben" can only surface bade and panguryagan.

## 1. Biggest gap: "12. Upakara Ngaben" banten tables (md 1290-1694)

The corpus's full tetandingan banten per stage (Yama Tatwa): A. Pengaskaran (Palet I-V + Ajeng
Sulinggih + Tirta + Tedun Sawa), B. Tunon (Palet I-IX), C. Ngulapin/Mamitang ring Segara,
D. Ngerorasin/Nyekah/Mamukur, E. Penyekahan (Palet I-XII). ~150 item lines. Verbless lists, so the
dependency-rule extractor produced almost nothing from them (the extraction output mentions pejati,
prayascita, byokawon, durmanggala, catursari, sesayut, bijaratus, karowista, pusuh menuh, bunga teleng
only 8 times in total).

Missing (no node): peras / pras (see §5: resolves to `perak`), suci / suci asoroh, pejati, ajuman,
canang (oyodan, meraka, tambur), byakaon / byokawon / pabyokawon, prayascita, durmanggala, tatebasan
(pasupati, sidhakarya, ardhanareswari), sesayut, rantasan, salaran, pujungan, banten saji (sakabuatan,
asele), pengadang-adang, panjang ilang, papegatan (see alias gaps), catursari, padudusan, pemelaspas,
penyumpit areng, papendakan, gambelan, rayunan, jaja bantal/pasung/uli/gina, pemanisan, lis, ketipat
kelanan/bantal, daksina gede / daksina lingga, pras pengambyan / arepan, pagnian, toya anyar, tirta
penyeeb, tirta pemerelina, geni pamralinan.

Present but not linked to the stage/palet they belong to: daksina, tumpeng, tipat, lis_bale_gading,
bubur_pirata, nasi_angkeb, sekar_ura, rurub_sinom, adegan, klungah_nyuh_gading, puspa_lingga,
sesenden, gelar_sanga (linked to `segehan` only). Exception: pengulapan -> ngulapin.

## 2. Tirtha Pangentas ingredients (md 10297-10361)

17 sarana + 11 banten.

| item | KG |
|---|---|
| periuk (ditulisi Dasaksara) | missing |
| jun pere | `jun_pere` (not linked to tirta_pangentas) |
| pripih cendana / perak / tembaga | missing |
| pripih emas | `pripih_emas` -> DIMASUKKAN_KE_DALAM tirta_pangentas |
| mirah | missing |
| balung-balung | missing |
| jijih (biji padi) | `jijih_biji_padi` -> tirta_pangentas |
| don dapdap | alias gap (`daun_dapdap` exists) |
| bijaratus, karowista, kelepikan jepun | missing |
| ambengan | alias gap (`alang_alang` exists, not linked) |
| padang lepas | `padang_lepas` -> generic `tirtha`, not tirta_pangentas |
| ulantaga | `ulantaga` -> tirta_pangentas |
| recedana | missing (the string "recadana" resolves to `ngaben_svasta`, a different sense) |
| banten: daksina gede sarwa kutus, pedagingan, suci gede, peras sesantun, ajuman, bayuhan, lis, karangan, nasi sokan | all missing (sodan -> `soda`, soroan -> `sorohan` exist, unlinked) |

## 3. Eteh-eteh Pabersihan Mati / Ngelelet (md 8595-9140, repeated 9729-9979; table md 1244-1289)

20 numbered items (one per body part).

Present: babelonyoh, itik_itik, umbi_sikapa, daun_pisang_saba, gegaleng, daun_intaran, pecahan_kaca,
waja, besi, malem, anget_angetan, kawangen_jeriji, kawangen.
Missing: telor ayam, angkeb sarira, sesisir pisang kayu, bunga teleng, pusuh menuh / kacip melati,
daun delem / don delem-delem, wewangian / boreh miik / minyak wangi, daun terong, daun teratai,
jarum / paku (table).

Linkage: only `anget_angetan` and `banten_pamegat` link to `pabersihan_mati`. The rest link to
`jenazah` (DILETAKKAN_DI) and the stage appears only inside LITERAL attribute text
(e.g. daun_intaran DILETAKKAN_DI "kedua alis jenazah ketika upacara mabersih mati / ngelelet"),
which the bot shows only for a "di mana" question. `eteh_eteh` itself (BERUPA list) has no stage link.

## 4. Persiapan Nyiramang Layon (md 6991-7560, ~45 items)

Present: daun_dapdap, boreh (both linked to nyiramang_layon), malem, daun_pisang_saba, paes_gedubang,
lekesan, kawangen, kawangen_jeriji, sisig, pecahan_kaca, pecahan_besi_baja, anggapan, api_takep,
tali_penyalin, uang_kepeng, kayu_cendana, blangsah, tirta panglukatan/pabersihan/pengeringkes.
Missing: pusuh menuh, bunga teleng, don pucuk, don delem-delem, don tuwung polo, pisau kecil, sindrong,
telor ayam, minyak wangi, kain hitam, cermin, suwah petat, asem, sabun, pisang kayu, pakaian/kamben
putih, kain kasa, tikeh plasa, tirta betara hyang, padi satu cekal, pedangal tebu, batang dapdap,
air cendana.

## 5. Wrong resolutions (worse than missing: bot answers about a different thing)

One-edit fuzzy on short words, plus polysemy:

| user says | resolves to | should be |
|---|---|---|
| peras, banten peras | `perak` (silver) | peras (banten) - missing |
| sisir | `sisig` | comb - missing |
| sabun | `sabuk` | soap - missing |
| base | `bade` | base = sirih leaf - missing |
| lante | `ante` | `lante_bambu` (exists) |
| sekar | `sekah` | sekar = flower |
| bubur | `bukur` | bubur (bubur_pirata exists) |
| utik | `itik_itik` | utik (tool) |
| jarum | `jarum_jaum` | needle - missing (verify jarum_jaum) |
| kasa (cloth) | `sasih_kasa` (month) | polysemy |
| banten penebusan | `penebusan` (stage) | the offering - arguably fine |

## 6. Alias gaps (entity exists, corpus spelling does not resolve)

intaran / don intaran -> daun_intaran; don dapdap -> daun_dapdap; ambengan -> alang_alang;
busung -> daun_kelapa_muda_busung; bawang putih -> kesuna_bawang_putih; pipis bolong -> uang_kepeng;
candana -> kayu_cendana; benang tukelan -> tali_benang_tukelan; dyus kamaligi -> diuskamaligi;
byokawon / pabyokawonan / byakaon -> banten_byakawonan; banten papegatan -> banten_pamegat (verify
same banten); lante -> lante_bambu; ketipat -> tipat.

## 7. What is in good shape

Wadah / pengusung / pembakaran: bade, lembu, patulangan, gedarba, gajah_mina, singa, macan, naga_banda,
pepaga, galar, kajang, bale_salunglung, bale_pamuunan all present (menjangan missing). Tirtha types
mostly present (panglukatan, pabersihan, ening, pemanah, penembak, kawitan, kahyangan tiga, pangentas,
pengeringkes, gangga, amertha); but penembak, kawitan, kahyangan tiga, ening, pengeringkes have no
ceremony link.

## Fix options (not applied)

1. Out-of-band triples (the existing `manual_addition` route) for the §1-§4 lists:
   `<item> DIGUNAKAN_DALAM <stage>` / `<tirtha> TERBUAT_DARI|BERISI <item>`, one per list line, with
   the md line as provenance. Needs new entities + definitions for the missing items (kb_lint's
   closure/definition checks will demand them).
2. `force_merge` / aliases for §6.
3. Resolver: one-edit fuzzy on <=5-letter tokens produces §5. Either require ratio on short tokens or
   add the missing words as entities so exact match wins. Add every §5 row to
   `Chatbot/bot/regression/questions.json` as a forbidden-pattern check.
4. A "sarana apa (yang digunakan) untuk X" question shape: `DIGUNAKAN_DALAM` into X and into X's
   stages (BAGIAN_DARI children), since most items belong to a stage, not to ngaben directly.

# Chunk 2 audit (S788..S1256)

Convergence re-audit of 59 sentences. Most triples are clean post-flag.txt. Below are only
the genuine remaining problems. Sentences already ruled on in flag.txt (788, 797, 801, 809,
917, 925, 961, 971, 1122, 1128, 1136, 1138, 1160, 1163, 1169, 1173, 1188, 1189, 1205, 1206,
1213, 1253) are trusted unless I found an ADDITIONAL issue, which is called out as such.

Balinese/ritual glosses used below: sawa/layon = corpse; pepaga/asagan = bamboo bier-platform;
ngringkes/pangringkesan = wrapping/shrouding the corpse; natar = house yard; dusa = special
corpse-washing platform; tirtha = holy water; panglukatan/pabersihan = purification (types of
tirtha); nglungah = infant cremation using a young-coconut shell; mahabutha = the five gross
elements; niskala = the unseen/spiritual; leteh/keletehan = ritual impurity; momong = to
carry/cradle; klungah nyuh gading = young yellow-coconut shell.

## FIX  (triple is salvageable — give the corrected triple)

- **S923 [0]**  current: `jenazah momong | DISERTAI | peti samping`
  fix: `jenazah | DIIRINGI | peti (di sampingnya)`
  why: Raw "Saat berangkat ke kuburan, jenazah di momong, diiringi peti di sampingnya" = "on the
  way to the cemetery the corpse is carried, accompanied by the coffin at its side." Parser fused
  the passive "di momong" into the subject and "di sampingnya" into "samping". Subject is just
  `jenazah`; object is `peti`.

- **S917 [0]**  current: `jenazah | DIBUNGKUS | kain putih setelah dimandikan`
  fix: `jenazah bayi | DIBUNGKUS_DENGAN | kain putih`
  why: Raw section "Sesudah Kepus Pungsed" — this is specifically an infant corpse ("jasad bayi
  tersebut dibungkus dengan kain putih setelah dimandikan"). Per user's baby-corpse instruction,
  qualify the subject to `jenazah bayi` so it doesn't read as a general adult-ngaben rule. Also
  the temporal "setelah dimandikan" is fused into the object; drop it or split as
  `jenazah bayi | DIBUNGKUS_SETELAH | dimandikan`.

- **S925 [0]**  current: `jenazah | DIMASUKKAN_KE_DALAM | peti kayu`  (source=manual_override)
  fix: `jenazah bayi | DIMASUKKAN_KE_DALAM | peti kayu`
  why: Same infant section ("Sesudah Kepus Pungsed"). Fact is faithful to raw ("jenazah
  dimasukkan ke dalam peti kayu") so it is salvageable rather than a drop — only the unqualified
  subject is the problem. Qualify to `jenazah bayi` per user's baby-corpse instruction.

- **S957 [1]**  current: `jenazah bayi | DIMANDIKAN | natar rumah`
  fix: `jenazah bayi | DIMANDIKAN_DI | natar rumah`
  why: "dimandikan ... di natar rumah" = bathed in the house yard — `natar rumah` is a location,
  not the thing it is bathed with (that is [0], `air biasa`). Predicate must carry the locative.

- **S1039 [0]**  current: `jenazah | DIMANDIKAN | balai-balai rumah adat`
  fix: `jenazah | DIMANDIKAN_DI_ATAS | balai-balai rumah adat`
  why: "jenazah pun dimandikan di atas balai-balai rumah adat" — same locative-grabbed-as-object
  issue; the platform is where the washing happens.

- **S1056 [0]**  current: `pepaga | BERFUNGSI_SEBAGAI | balai-balai alas memandikan ngringkes`
  fix: `pepaga | BERFUNGSI_SEBAGAI | balai-balai alas ngringkes`
  why: Raw "berfungsi sebagai balai-balai alas memandikan jenazah dan ngringkes" coordinates two
  uses: (1) washing the corpse, (2) ngringkes (shrouding). [1] already captures use (1)
  correctly; [0] is a garbled version that fused "memandikan" onto "ngringkes" and dropped
  "jenazah dan". [0] should be the second coordinate member: base for `ngringkes`.

- **S1058 [0]**  current: `pepaga | DIPASANG | secarik kain putih`
  fix: `kain putih | DIPASANG_DI_ATAS | pepaga`
  why: Raw "Di atas pepaga itu dipasang secarik kain putih selaku 'leluhur' atau langit-langit
  tandu tersebut." The thing installed is the cloth, onto the pepaga; current direction reads
  backwards. See ADD for the dropped significance.

- **S1060 [0]**  current: `jenazah | BERASAL_DARI | rumah adat`
  fix: `jenazah | DIPINDAHKAN_DARI | rumah adat`
  why: Raw "Setelah jenazah dipindahkan dari rumah adat ke pepaga, kain penutup dibuka" =
  "moved from the traditional house to the pepaga." BERASAL_DARI ("originates from") is a
  meaning reversal — the corpse does not come from the house, it is relocated. Same class as
  the S3063 "dibersihkan dari" reversal flagged in flag.txt.

- **S1066 [1]**  current: `jenazah | DIBERI | sarana simbolik pangringkesan , antara lain sesisir pisang selaku kalang bahu`
  fix: `jenazah | DIBERI | berbagai sarana simbolik pangringkesan`
  why: Run-on object — the "antara lain sesisir pisang selaku kalang bahu" example is already
  extracted as [2]. Trim [1] to the head NP.

- **S972 [0]**  current: `sawa anak | DIBAKAR | pitra yadnya nglungah`
  fix: `sawa anak yang telah berusia lima bulan ke atas | DIBAKAR_DALAM | pitra yadnya nglungah`
  why: Raw "hanya sawa anak yang telah berusia lima bulan ke atas boleh atau sebaiknya dibakar
  dalam Pitra Yadnya Nglungah ini." Two problems: (a) "dibakar dalam pitra yadnya nglungah" =
  burned *within* this ceremony (context frame), not that the ceremony is the object being
  burned; (b) the age qualifier "yang telah berusia lima bulan ke atas" is the entire point of
  the sentence (only corpses of children 5 months+ may be cremated this way) and was stripped.

- **S1017 [0]**  current: `mahabutha | DITUJUKAN_UNTUK | induk asal`
  fix: `mahabutha (yang lima unsur) | KEMBALI_KEPADA | induk asalnya masing-masing`
  why: Raw "semua mahabutha yang lima unsur itu, kembali kepada induk asalnya masing-masing" =
  "all the mahabhuta, the five elements, return to their respective origins." "kembali kepada"
  (return to) is not "ditujukan untuk" (aimed at); and "masing-masing" (respective) was dropped.

- **S1188 [3]**  current: `upacara ini | MEMPERGUNAKAN | pabersihan (TAHAPAN_UPACARA)`
  fix: `upacara ngaben titip | MEMPERGUNAKAN | tirtha pabersihan (TIRTHA_SUCI)`
  why: Raw "mempergunakan tirtha antara lain, Tirtha Panglukatan dan Pabersihan selaku sarana
  penyucian." Shared head noun "Tirtha" governs both conjuncts — "Pabersihan" alone should be
  `tirtha pabersihan`, and the type is TIRTHA_SUCI not TAHAPAN_UPACARA. This is exactly the
  "Tirtha [Panglukatan dan Pabersihan]" calibration case.

- **S1188 [2] & [3]**  current subject: `upacara ini` (anaphoric, unresolved)
  fix: resolve to `upacara ngaben titip` / `pitra yadnya titip` (the section is about the
  provisional/titip cremation: "Jika sawa dibakar titip...").
  why: Bare "upacara ini" left as an endpoint — same anaphoric-subject issue called out in the
  calibration list.

- **S1219 [0]**  current: `sawa | DIBAKAR | alat pangringkesan (TAHAPAN_UPACARA)`
  fix: `sawa | DITANAM_ATAU_DIBAKAR_BERSAMA | semua alat pangringkesan`
  why: Raw "barulah sawa ditanam atau dibakar beserta semua alat pangringkesannya." The tools
  are buried/burned *together with* the corpse — they are not the target of "dibakar". Also
  "ditanam atau" (buried or) was dropped. Type should be SARANA_RITUAL.

- **S978 [0]**  current: `tirtha | DIPERCIKKAN_PADA_SEBELUM | tirtha pangentas`
  fix: `tirtha (dari pamrajan/kahyangan tiga/prajapati) | DIPERCIKKAN_SEBELUM | tirtha pangentas`
  why: (additional issue beyond the user's anaphora wish) "DIPERCIKKAN_PADA_SEBELUM" is a
  mega-fused predicate welding "pada saat menjelang" + "sebelum". Raw: "Tirtha ini dipercikkan
  sebelum Tirtha Pangentas pada saat menjelang penguburan atau pembakaran sawa." Split the
  temporal frame out (see ADD). Per raw line 776, "tirtha ini" = tirtha requested from the
  pamrajan / Kahyangan Tiga / Pangulun Setra/Prajapati for a corpse already treated as adult.

## DROP  (triple should be removed)

- none — the remaining weak triples in this chunk are all salvageable via FIX above, or already
  adjudicated in flag.txt.

## ADD  (missing triples the sentence supports)

- **S789**  `orangtua | ADALAH | ibu`
  why: "'pitra' berarti orangtua (ayah dan ibu)." The object_decomposition [1] captured only
  `ayah`; "ibu" is the missing coordinate member of the parenthetical gloss.

- **S792**  `pitra yadnya | DITUJUKAN_UNTUK | leluhur`
  why: "pengorbanan ... kepada leluhur, terutama kepada orangtua." [1] captured only the
  "terutama" sub-target (orangtua) and dropped the primary target, `leluhur` (ancestors).

- **S851**  `manusia | DINILAI_SEBAGAI | pihak berhutang`
  why: The sentence's main clause — "manusia 'pemakai' lima unsur zat itu dinilai selaku pihak
  berhutang" = "humans, as users of the five elements, are judged to be debtors" (the pitra-rna
  debt motif) — is entirely unextracted; only the subordinate `pancamahabutha BERWUJUD tubuh
  manusia` survived.

- **S1016**  `wujud sawa | BERUBAH_MENJADI | unsur, elemen atau mahabutha`  (+)
  `mahabutha | ADALAH | asal materi yang jauh lebih halus dari benda (lebih halus dari abu)`
  why: user /111 "more extraction here". Raw: "sehingga wujud sawa dari benda yang wungkul
  menjadi unsur, elemen atau mahabutha, yakni asal materi yang jauh lebih halus dari pada
  benda, lebih halus dari abu." Only `ngaben BERTUJUAN_UNTUK ...` and `niskala ADALAH batiniah`
  were pulled.

- **S1060**  `jenazah | DIPINDAHKAN_KE | pepaga`  (+)  `kain penutup | DIBUKA`
  why: "dipindahkan dari rumah adat ke pepaga, kain penutup dibuka" — the destination and the
  main clause (the cover cloth is opened) are both unextracted.

- **S1215**  `sawa | DILETAKKAN_DI | para-para tempat pembakaran`
  why: Raw "sawa diletakkan di atas lubang tempat penguburan **atau di atas para-para tempat
  pembakarannya nanti**." Only the first disjunct (`lubang tempat penguburan`) was kept.

- **S1058**  `kain putih | DISEBUT | "leluhur" (langit-langit tandu)`
  why: "dipasang secarik kain putih selaku 'leluhur' atau langit-langit tandu tersebut" — the
  cloth's ritual role/name (the "leluhur"/canopy of the bier) is the informative part and is
  dropped.

- **S957**  `dusa | ADALAH | balai-balai khusus pemandian jenazah`
  why: The parenthetical gloss "dusa (balai-balai khusus pemandian jenazah)" defines dusa; worth
  a decomposition triple. (Optionally also `jenazah bayi | DIMANDIKAN_DI_ATAS | dusa`.)

- **S974**  `abu | DISUGUHKAN | sesaji sederhana`
  why: "Setelah disuguhkan sesaji sederhana, abu itu dihanyutkan ke laut atau ke sungai" — the
  ash is first presented a simple offering; minor but supported.

## NOTE  (borderline / systemic observation, no single fix)

- **S1169**  `sawa | DITANAM_ATAU_DIBAKAR_SEMENTARA | status dititip, menunggu biaya untuk
  menggelar ngaben beberapa bulan atau tahun kemudian` — user already flagged /114. Confirming
  it is still a mega-fused predicate + run-on clause object, i.e. the exact
  `DITANAM_ATAU_DIBAKAR_SEMENTARA` pattern named in the calibration notes. If not dropped, it
  would be better as `sawa | DITANAM_ATAU_DIBAKAR | dengan status dititip` +
  `sawa (dititip) | MENUNGGU | rezeki untuk menggelar ngaben`.

- **S1188 [0]/[1]**  `sawa MEMPEROLEH sesaji` / `sawa MEMPEROLEH tirtha lainnya` — both flatten
  the purpose clause ("agar sawa boleh dan wajar menerima sesaji dan tirtha lainnya" — so that
  the corpse *may properly* receive them), and [1]'s endpoint `tirtha lainnya` is an unresolved
  anaphor ("other tirtha"). Low priority; user already flagged the sentence /113 /111.

- **S797 [0]**  object "upacara keagamaan yang diadakan untuk menyelenggarakan atau nyangaskara
  jenazah atau roh keluarga yang meninggal" is still long, but it is a single ADALAH definition
  and splitting it would fracture the meaning. manual_override — trusting per user's /111.

- **S1221 [0]**  object `klungah nyuh gading/suku tunggal` keeps a slash-joined pair as one
  compound. Raw "dimasukkan ke dalam klungah nyuh gading/suku tunggal" — these read as
  alternative vessels (young-coconut shell / suku tunggal); arguably two disjunct members.
  Borderline, low priority.

- **S961 [2]** (manual_override, flag.txt-adjudicated) `sawa | DIIKAT | sebelas kali` — raw verb
  is "dibelit sebelas kali dari hulu ke kaki" (wound/coiled eleven times). "DIIKAT" is a mild
  paraphrase of "dibelit"; faithful enough, noting only.

## Chunk stats
FIX: 15   DROP: 0   ADD: 11 (across 9 sentences)   sentences reviewed: 59

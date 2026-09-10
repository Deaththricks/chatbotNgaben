# Chunk 8 audit (S3868..S4340)

Convergence re-audit. 53 sentences, ~80 triples. Almost every sentence here is
covered in `flag.txt` (the S3333-S4340 "densest under-extraction territory"
block). The great majority of the flag.txt fixes have LANDED cleanly in this
fresh run (see NOTE). Below are only the genuine remaining problems plus a few
fresh findings on the handful of sentences flag.txt did not touch
(S3963, S3973, S3977, S4035, S4079, S4338).

Glosses used: `tirtha/tirta` = holy water; `pangentas` = the "ferrying-across"
liberation water; `sangkaning` = "berasal dari / asal-mulanya"; `mulih ring /
maring` = "kembali ke"; `ganda/rasa/rupa/bayu(ambekan)/sabda` = smell / taste /
form / breath / sound (the five sense-objects returning to the Panca Maha Bhuta);
`preta` = a still-impure ghost stage; `pitara` = the ancestralized, purified
spirit; `ngentas` = to liberate/ferry the soul across.

---

## FIX  (triple is salvageable — give the corrected triple)

- **S4074 [0]**  current: `tirtha ening | BERFUNGSI_SEBAGAI | symbol pikiran dan perasaan sang yajamana ( orang yang punya upacara ) , sehingga roh atau atman yang di upacarai tidak mengalami kegoncangan , sehingga dapat mencapai alam sorga dengan tenang`
  fix: `tirtha ening | BERFUNGSI_SEBAGAI | simbol pikiran dan perasaan sang yajamana (orang yang punya upacara)`
  why: `dependency_rule` triple dumps the whole sentence — the two `sehingga` result-clauses — into one run-on object. flag.txt flagged an earlier duplication bug here ("pikiran DARI pikiran"); that specific duplication is gone, but the object is now a mega-string. Trim to the copular predicate nominal; move the consequences to their own triples (see ADD).

- **S4338 [1]**  current: `tirtha pangentas | ADALAH | penyucian`
  fix: `tirtha pangentas | ADALAH | alat sangaskara atau penyucian kepada roh atau atman orang yang telah meninggal dunia`
  why: raw (line 3998): "…adalah sebagai alat Sangaskara atau Penyucian kepada Roh atau Atman orang yang telah meninggal dunia…". `alat sangaskara` and `penyucian` are one coordinated nominal with a shared `kepada …` complement. [0] keeps the first half, [1] strips to the bare word "penyucian" — clause-stripped to near-vacuity. Merge into one triple (or give [1] the same `kepada …` complement [0] has).

- **S4340 [0]**  current: `tirtha pangentas | BERFUNGSI_SEBAGAI | pelebur unsur karma wasana`
  fix: `tirtha pangentas | BERFUNGSI_SEBAGAI | pelebur unsur karma wasana yang mengikat roh atau atman`
  why: flag.txt line 934 flagged this exact drop (/115) — still open in this run. "karma wasana yang mengikat roh atau atman" (the karmic residue that *binds* the soul) — the relative clause is the whole reason `ngentas` is needed. Aliases in [1]/[2] are fine.

- **S4035 [1]**  current: `priuk (tempat tirtha pangringkes) | DIPECAHKAN | setelah tirtha dipercikkan`
  fix: `priuk (tempat tirtha pangringkes) | DIPECAHKAN | (setelah tirtha dipercikkan)` — i.e. demote the temporal clause to a parenthetical qualifier, object slot otherwise empty; or DROP [1] outright since [2] (`priuk yang pecah | DIBUANG_DI | kolong bawah pepaga/asagan`) already presupposes it.
  why: `DIPECAHKAN` is intransitive here; "setelah tirtha dipercikkan" is a time adjunct, not a patient. Currently reads as a pseudo-object (failure mode 3 shape). Low stakes — manual_override, faithful meaning — but the object slot is misused.

---

## DROP  (triple should be removed)

- none. (S4035 [1] is a possible drop — logged under FIX above.)

---

## ADD  (missing triples the sentence supports)

- **S3977**  `jenazah | DIBILAS_DENGAN | air`  +  `jenazah | DIKERINGKAN_DENGAN | kain kering`  +  `pemakaian umbi sikapa/sekapa | BERMAKNA | agar kulit orang yang meninggal putih bersih (jika numitis lagi)`
  why: raw (line 3067): "Jenazah disabuni (digosok) dengan umbi sikapa/sekapa, **kemudian dibilas dengan air dan dikeringkan dengan kain kering**. Ini memiliki makna agar bila orang yang meninggal tersebut nantinya numitis lagi, diharapkan kulitnya akan putih bersih seperti umbi sikapa/sekapa." Only the soaping step ([0]) was extracted; the rinse, dry, and the symbolic-meaning payload are all dropped. Same rinse/dry under-extraction flag.txt raised for S3610.

- **S4074**  `roh atau atman yang diupacarai | TIDAK_MENGALAMI | kegoncangan`  +  `roh atau atman | DAPAT_MENCAPAI | alam sorga dengan tenang`
  why: the two `sehingga` result-clauses currently buried in [0]'s run-on object (see FIX). These are the stated effect of tirtha ening functioning as the yajamana's mental symbol.

- **S4338**  `roh atau atman (orang yang telah meninggal) | NAIK_KEDUDUKAN_DARI | preta menjadi pitara`  +  `pitara | DAPAT_MEMASUKI | alam bwah loka (tumpuan menuju alam swah loka)`
  why: raw (line 3998): "…sehingga Roh atau Atman tersebut kedudukannya menjadi terangkat, yaitu dari Roh yang tingkatannya masih Preta … menjadi Pitara, sehingga bisa memasuki alam Bwah Loka yaitu sebagai tumpuan untuk menuju ke alam Swah Loka." The entire consequence chain — the actual point of the sentence — produces zero triples; only the two thin `ADALAH` fragments survive. Major under-extraction, exactly the pattern flag.txt's S3333-S4340 note describes.

- **S4079**  `tirtha pemanah | DIBUAT_SAAT | upacara pengaskaran`
  why: raw (line 3699): "…karena Tirtha Pemanah … dibuat tepat pada waktu Upacara 'Pengaskaran'…". [0] captures only "berbeda dengan tirtha-tirtha … di atas"; the *reason for* the difference (made precisely at pengaskaran) is dropped. (Redundant with S4121 [1] for tirtha pangentas but distinct subject.)

- **S3963**  `kawangen | DIKUMPULKAN | (setelah upacara sembah bhakti)`  (minor)
  why: raw (line 3467, the short variant that matches this sentence): "…semua kawangen … **dikumpulkan** dan ditaruh di samping jenazah." Only the second coordinate verb ("ditaruh di samping jenazah") was extracted. Low priority. NB: the longer variant with the "tanda doa restu / agar perjalanan roh … tidak mendapatkan halangan" clause is a *different* corpus sentence (raw line 2998) — already handled at flag.txt S3544 — so do NOT graft that clause onto S3963.

---

## NOTE  (borderline / systemic observation, no single fix)

- **Convergence is strong for this chunk.** flag.txt-flagged sentences that are now resolved in this run: S3904 (main-clause ADD landed), S3909, S3914 (MENJALANI), S3936 ("masih hidup" restored), S3964 (D15 giant-dump split into 3), S4062 (banten added, vacuous "lainnya" dropped — but see below), S4065 (vague "perbedaan" → concrete differences + maker), S4087 (Bisma Parwa retained), S4090 (garble gone, myth payoff added), S4096, S4105 / S4110 (berupa-list captured + separate "dimohonkan oleh" fact), S4112 (utpeti/sthiti/pralina list + "kepada sang pencipta" restored), S4121 (priest-residence merged, "atau di rumah" + pengaskaran timing added), S4128 (both purpose clauses restored), S4169 (matches user's best-effort /114 fix), S4170 (middle clause restored), S4175 (ceremony-name definition added), S4177 (ADALAH→MEWUJUDKAN, "tri aksara" + "berstana dalam bathin" restored, "ongkans"→"ongkara"), S4192 (maker clause restored), S4212 (subject fixed to "badan", ritual clause added), S4266 (mantra fact added), S4273 (full 5-item list + padang lepas + mantra clause — was the worst case, now complete), S4336 (causal justification added), S4339 (purpose clause restored). The MEMILIKI-fungsi clause-retention fix (S4106/S4111/S4116) and the Panca Maha Bhuta verses (S4300-S4305) are holding.

- **S4062 [3]**  `tirtha | DIPAKAI_UNTUK | adegan (SARANA_RITUAL) (SARANA_RITUAL)` — the entity-type annotation is doubled/printed twice in the object string. Cosmetic serialization bug, not a content error, but visible in output.

- **S4110 [1]**  `tirtha | DIMOHONKAN_OLEH | pemangku kahyangan tiga setempat (BANGUNAN_RITUAL)` — object typed BANGUNAN_RITUAL; `pemangku` is a person (ENTITAS_KEAGAMAAN). S4105 [1], the parallel sentence, is fine. Wrong-type only.

- **S4112 [2][3][4]**  `pura kahyangan tiga | BERFUNGSI_SEBAGAI | utpeti / sthiti / pralina` — raw says the temple is "tempat pemujaan sang pencipta **dalam fungsi sebagai** utpeti, sthiti dan pralina", i.e. it is *the creator's* threefold function, not the building's. Faithful-ish and manual_override; flagging only that the subject is arguably `sang pencipta`, not the temple.

- **S4126 [0]** and **S4077 [0]**, **S4167 [0]**, **S4171 [0]** — long single-string `ADALAH` definitions that read clunkily ("tirtha dari beberapa jenis-jenis tirtha penting … yang paling terpenting dalam hal ini"). flag.txt explicitly cleared all four ("no issues found"), so leaving as-is per authoritative verdict; noting the terseness/run-on style persists in the `dependency_rule` copular path.

- **S3868 [0]**  object `bale tempat jenazah` truncates "…disemayamkan"; subject-side type is ISTILAH_UMUM_RITUAL for what is a building. flag.txt cleared it; minor.

## Chunk stats
FIX: 4   DROP: 0   ADD: 5   sentences reviewed: 53

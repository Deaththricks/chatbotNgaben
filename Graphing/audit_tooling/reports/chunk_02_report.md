# Chunk 2 audit (S560..S1187)

## FIX  (triple is salvageable — give the corrected triple)

- **S560 [0]**  current: `banten pejati saha banten peras gede | LAINNYA | asoroh`
  fix: `banten pejati, peras gede, dan suci | ADALAH | asoroh (satu set lengkap)`
  why: matches flag.txt's suggestion — "asoroh" = "a complete set" (sa + soroh); the three offering types (pejati, peras gede, suci) together make up one asoroh. Segmentation is badly garbled (root parsed as the adjective "suci" acting as a verb) but the intended meaning is recoverable.

- **S616 (all of [0]-[3])**  current: `banten nuwur pakuluh | LAINNYA | merajan / paibon / panti / kawitan`
  fix: `banten nuwur pakuluh | DIPERSEMBAHKAN_DI | merajan / paibon / panti / kawitan`
  why: matches flag.txt exactly ("all instances of 616: ring = put at/offered to") — STILL unfixed, still generic LAINNYA. Positive note: the 4-item location list itself is fully preserved (good N10 evidence) — only the relation label needs fixing.

- **S618 [1]**  current: `banten | DIPERSEMBAHKAN_KEPADA | merajapati`
  fix: `banten atur piuning | DIPERSEMBAHKAN_DI | merajapati`
- **S618 [2]**  current: `banten | DIPERSEMBAHKAN_KEPADA | panghulunin setra`
  fix: `banten atur piuning | DIPERSEMBAHKAN_DI | panghulunin setra`
  why: matches flag.txt exactly ("supposed to be 'banten atur piuning', not just banten... offered in dalem, merajapati, etc") — subject still bare "banten", still unfixed; also apply the "ring = offered at" gloss. See DROP/ADD for the third location ("dalem") which the extractor still gets wrong/misses.

- **S738 [0]**  (retain as-is: `puspa asti | ADALAH | abu`) — see ADD below for the missing relative-clause content flag.txt asked for.

- **S780 [0]**  current: `puspa asti | DILETAKKAN_DI | balai selunglung`
  keep, but see ADD below for the missing "atau dipangku oleh keluarga" disjunct.

- **S785 [0]**  current: `pitra yadnya | ADALAH | istilah umat hindu bagi umat hindu di sini`
  fix: `pitra yadnya | ADALAH | istilah bagi umat hindu di sini`
  why: "istilah umat hindu bagi umat hindu di sini" duplicates "umat hindu" — same duplication bug seen at chunk-1 S44 ("jenazah utuh...jenazah utuh").

- **S792 [0]**  current: `pitra yadnya | BERARTI | pengorbanan , terutama kepada orangtua`
  fix: `pitra yadnya | BERARTI | pengorbanan yang dilandasi hati yang tulus suci kepada leluhur, terutama kepada orangtua`
  why: matches flag.txt exactly ("a bit too terse") — the object string is not just terse but literally broken (dangling comma), dropping the entire "yang dilandasi hati yang tulus suci kepada leluhur" relative clause mid-string. **N1 gap** for BERARTI+relative-clause.

- **S801 [0]**  current: `pitra yadnya | TERDIRI_DARI | jenis`
  fix: `pitra yadnya | TERDIRI_DARI | beberapa jenis (yang pelaksanaannya ber-bhinneka)`
  why: matches flag.txt exactly ("object should be 'beberapa jenis'") — STILL missing the "beberapa" (several) qualifier.

- **S906 [0]**  current: `jabang bayi | MENINGGAL | kandungan`
  fix: `jabang bayi | MENINGGAL_DI | kandungan`
  why: drops the "dalam" (in) preposition, making "kandungan" read as an object rather than a location. See ADD below for the much bigger missing content flag.txt asked about.

- **S923 [0]**  current: `jenazah momong | DISERTAI | peti samping`
  fix: split into `jenazah | DIMOMONG_KE | kuburan` and `jenazah | DISERTAI | peti`
  why: matches flag.txt exactly, still unfixed — subject wrongly absorbs the verb "momong" (tenderly carried) and object wrongly absorbs "samping" (beside); both ends are garbled merges.

- **S961 [3]**  current: `sawa | BERASAL_DARI | hulu kaki`
  fix: `sawa | DIIKAT_DARI | hulu ke kaki`
  why: matches flag.txt exactly ("961d... should be sawa | diikat dari | hulu kaki") — STILL unfixed. "dari hulu ke kaki" describes the direction of winding (head-to-foot), not an "origin" relation.

- **S1016 [0]**  current: `ngaben | BERTUJUAN | niskala`
  fix: `ngaben | BERTUJUAN_UNTUK | memusnahkan segenap jasad sawa sehalus-halusnya`
  why: wrong object — "secara niskala (batiniah)" is a manner-adverbial ("in the unseen/spiritual sense"), not the goal itself. The true purpose clause of "bertujuan" (to destroy the corpse down to its finest elements) is entirely missing, replaced by a manner marker misread as the target.

- **S1017 [0]**  current: `mahabutha | DITUJUKAN_UNTUK | induk asal`
  fix: `mahabutha | KEMBALI_KE | induk asal (masing-masing)`
  why: "kembali kepada" = "returns to" (a cyclical return), not "ditujukan untuk" (intended for) — wrong relation label.

- **S1056 [0]**  current: `pepaga | BERFUNGSI_SEBAGAI | balai-balai alas memandikan jenazah`
  fix: `pepaga | BERFUNGSI_SEBAGAI | balai-balai alas memandikan jenazah dan ngringkes`
  why: **N10 gap** — drops the "dan ngringkes" (and binding/wrapping) second conjunct of the two listed functions.

- **S1060 [0]**  current: `jenazah | BERASAL_DARI | rumah adat`
  fix: `jenazah | DIPINDAHKAN_DARI | rumah adat (ke pepaga)`
  why: "dipindahkan dari X ke Y" is a directional-move relation, not "berasal dari" (originates from). Also see ADD below — the sentence's actual root clause ("kain penutup dibuka") was skipped entirely in favor of the subordinate clause.

- **S1082 [1]**  current: `jenazah | DIPERSEMBAHKAN_KEPADA | sajen kecil`
  fix: `jenazah | DISUGUHI | sajen kecil`
  why: "disuguhi X" means "is presented/served with X" (jenazah is the recipient); "dipersembahkan kepada X" (offered up to X) reverses the direction of giving.

- **S1122 [0]**  current: `nyekeh | BERARTI | jenazah`
  fix: `nyekeh | BERARTI | jenazah dibaringkan di rumah adat dalam jangka waktu agak lama hingga tiba hari H untuk ngaben sesuai dewasa yang dipilih`
  why: **severe N1-adjacent gap** — object truncated to the bare noun "jenazah", which is circular/meaningless on its own (nyekeh IS the practice of laying out the corpse; saying "nyekeh means jenazah" says nothing). The entire defining xcomp clause is dropped. N1's widened rule as worded targets ADALAH/BERPERAN_SEBAGAI specifically — this shows the same failure mode also affects BERARTI, which isn't covered.

- **S1128 [0]**  current: `nyekeh sawa | DILAKUKAN_OLEH | keluarga raja`
  fix: `nyekeh sawa | DILAKUKAN_OLEH | keluarga raja atau pendeta`
  why: drops the "atau pendeta" (or priest) disjunct — 2-item list, second item missing.

- **S1128 [1]**  current: `nyekeh sawa | BERASAL_DARI | masyarakat`
  fix: `keluarga raja atau pendeta | BERASAL_DARI | golongan masyarakat yang mampu melakukan upacara ini`
  why: the clause explains why royal/priestly families are the ones who do nyekeh (they belong to the social class able to afford/perform it) — not that "nyekeh" itself "originates from society". Wrong subject + garbled causal reasoning.

- **S1173 [1]**  current: `ngaben | MEMUPUK | rasa kekeluargaan`
  fix: `ngaben | MEMUPUK | rasa kekeluargaan dan kebersamaan`
  why: drops the "dan kebersamaan" (and togetherness) second conjunct.

- **S1187 [0]**  current: `sesajen | DIHANYUTKAN_KE | samudera`
  fix: `abu jenazah | DIHANYUTKAN_KE | samudera`
  why: **same wrong-subject bug as flag.txt S58b/c**, recurring in a fresh, previously-unflagged sentence — "abu jenazah" (the ashes), not "sesajen" (the offering), is what gets floated to the ocean. See ADD below for the sentence's actual main clause, which was dropped in favor of this borrowed embedded-clause action.

## DROP  (triple should be removed)

- **S618 [0]**  `banten | DIPERSEMBAHKAN_KEPADA | piuning`
  why: "piuning" is not a recipient/location — it's part of the banten's own designation ("atur piuning" = presenting formal notification). Nonsense triple; see FIX/ADD for the corrected structure.

- **S591 [0]**  `banten | DIPERSEMBAHKAN_KEPADA | sakabuatan`
  why: reaffirming flag.txt's verdict (still unfixed). Note: the identical sentence at chunk-1 S540 is recommended as a FIX rather than a drop in this audit — flag either both or neither for consistency (see cross-chunk NOTE).

- **S631 [0]**  `banten panebusan | LAINNYA | rateng saha salaran sejangkep`
  why: segmentation-mangled, same pattern as flag.txt's S541 (chunk 1) — "mentah" is wrongly tagged as the root verb, when "mentah lan rateng" (raw and cooked) is really a 2-item descriptor pair on the offering, not a verb+object.

- **S641 [1]**  `surya | ADALAH | banten pejati saha suci asoroh`
  why: matches flag.txt exactly ("641b: surya is not those bantens, drop this") — STILL unfixed. The offerings are *for* Surya, not identical to Surya.

- **S679 [0]** and **[1]**  `banten | DIPERSEMBAHKAN_KEPADA | asele` / `asele | ADALAH | jauman`
  why: reaffirming flag.txt's verdict ("679a: drop this") — STILL unfixed, both triples built on the same shaky base.

- **S809 [1]**  `pitra yadnya | ADALAH | rupa`
  why: matches flag.txt exactly ("809b: doesn't really make sense") — STILL unfixed. "rupanya" here is the adverb "apparently/it seems", not the noun "rupa" (form/appearance); a POS-tagging error produced a nonsense triple.

- **S925 [1]**  `jenazah | DIMASUKKAN_KE_DALAM | kuburan upakara apa`
  why: matches flag.txt exactly ("925b: drop this") — STILL unfixed, and worse than cosmetic: the source text says "**tanpa** upakara apapun" (WITHOUT any offering) — the extractor ignored the negation "tanpa" and merged "kuburan" with "upakara apa[pun]" into one object, actually reversing the sentence's meaning.

## ADD  (missing triples the sentence supports)

- **S618**  `banten atur piuning | DIPERSEMBAHKAN_DI | dalem`
  why: the third/first location in "ring dalem, merajapati, lan panghulunin setra" is structurally nested one level deeper (as the object of "ring" itself) and gets missed even though merajapati/panghulunin setra survive as conjuncts of "piuning" — a coordinate-completeness gap distinct from, but related to, the N10 pattern.

- **S641**  `banten munggah ring surya | DIPERSEMBAHKAN_KEPADA | surya`
  why: matches flag.txt exactly ("641a: munggah ring surya means the offerings to Surya") — currently the only triple present ([0]) uses generic LAINNYA; recommend the corrected label as an explicit addition alongside dropping [1].

- **S738**  `puspa asti | DIAMBIL_DENGAN | sumpit/sepit`  (+ `puspa asti | DIHANCURKAN_DI | sesenden`)
  why: matches flag.txt exactly ("puspa ati | diambil dengan | sumpit") — STILL missing. **N1 gap**: ADALAH+"abu"+yang-relative-clause is dropped entirely.

- **S780**  `puspa asti | DIPANGKU_OLEH | salah seorang keluarga`  (+ `persembahyangan (ini) | DIPIMPIN_OLEH | sulinggih`)
  why: drops the "atau dipangku oleh keluarga" disjunct and the entire second clause about who leads the prayer service.

- **S788**  `dua kata | ADALAH | yadnya`
  why: "yakni 'pitra' **dan** 'yadnya'" — a 2-item list, only "pitra" survived the object_decomposition step.

- **S789**  `orangtua | ADALAH | ibu`
  why: "ayah **dan** ibu" — a 2-item list, only "ayah" survived the object_decomposition step. (Same pattern as S788 — see NOTE on object_decomposition's conjunct handling.)

- **S809**  `pitra yadnya (dataran rendah) | DISEMPURNAKAN_OLEH | empu kuturan`  (+ `... | dang hyang dwijendra`, `... | empu lutuk`)
  why: matches flag.txt ("809: could be more extraction") — the attribution to specific historical priest-figures is entirely unextracted; a 3+ item list ("empu kuturan, dang hyang dwijendra, empu lutuk dan lain-lain") that never even makes it into a relation, so N10 can't be tested on it directly.

- **S851**  `manusia | BERHUTANG_PADA | pancamahabutha`
  why: matches flag.txt exactly — STILL missing. "manusia 'pemakai' lima unsur zat itu dinilai selaku pihak berhutang" (humans, as users of the five elements, are considered the indebted party).

- **S898**  `ida bhatara kumara | MENGASUH | bayi`
  why: matches flag.txt exactly — STILL missing. "yang diyakini sebagai 'mengasuh' bayi tersebut" (believed to care for/nurture the baby).

- **S906**  `ari-ari (placenta) | DIBIARKAN_MENUNGGAL_DENGAN | jasad sang bayi`
  why: matches flag.txt ("not enough extraction") — the sentence's actual core content (a tradition of keeping the placenta united with the baby's body) is entirely unextracted; only a minor "meninggal di kandungan" fact survives.

- **S957**  `jenazah bayi | DIMANDIKAN_DI_ATAS | dusa (balai-balai khusus pemandian jenazah)`
  why: the text explicitly glosses "dusa" as the special corpse-bathing platform; currently only the broader "natar rumah" (house yard) location survives.

- **S967**  `penyelesaian sawa dewasa | DISESUAIKAN_DENGAN | ketentuan dewasa ayu atau hari baik`
  why: the sentence's second clause (procedure timing adjusted to auspicious-day rules) is unextracted.

- **S970 (positive note, no ADD needed)**  flag.txt's flagged bad triple ("tirtha | menurut | tata cara doesn't make sense, drop this") is **gone** — replaced by the sensible `tirtha | DIMOHON_DARI | sulinggih`. Resolved.

- **S971 (no ADD needed)** — reviewed, both triples are reasonable, minor "ini" (this) qualifier loss only.

- **S974**  optional: `sesaji sederhana | DISUGUHKAN_SEBELUM | abu dihanyutkan`
  why: low priority — the temporal framing clause is dropped, but the 2-item "laut atau sungai" disjunct that matters is fully preserved (good N10 evidence).

- **S978**  `tirtha (ini) | DIPERCIKKAN_MENJELANG | penguburan atau pembakaran sawa`
  why: the entire temporal-context disjunct pair (burial or cremation) is unextracted; also note the current relation label "SEBELUM" is really a temporal conjunction repurposed as a predicate — consider renaming to "DIPERCIKKAN_SEBELUM" for clarity.

- **S1016**  `jasad sawa (wujud) | BERUBAH_MENJADI | unsur, elemen, atau mahabutha`
  why: the sentence's result clause (corpse transforms from solid matter into finer elements) is unextracted — a 3-item disjunct list, good future N10 test if implemented.

- **S1024**  `upacara (ini) | DIIRINGI_TUJUAN | permohonan kepada tuhan (yang maha pengampun)`
  why: the current triple only captures the deeply embedded final clause ("mendiang diberi ampun"); the sentence's own main clause (the ceremony's additional purpose) is skipped over entirely.

- **S1040**  `tikar (alas jenazah) | DITARIK | (dari bawah sawa)`
  why: the causal first clause (mat pulled out from under the corpse) is dropped, leaving only its result ("sawa berada di atas galar").

- **S1058**  `secarik kain putih | DISEBUT | leluhur (atau langit-langit tandu)`
  why: the apposition explaining what the white cloth represents/is called is unextracted.

- **S1060**  `kain penutup (jenazah) | DIBUKA | (setelah dipindahkan ke pepaga)`
  why: this is the sentence's actual ROOT clause ("kain penutup dibuka") — currently skipped entirely in favor of the subordinate advcl about the corpse being moved.

- **S1066**  `sesisir pisang | MELAMBANGKAN | kalang bahu`
  why: drops the "selaku kalang bahu" gloss explaining what the banana comb represents.

- **S1123**  `jenazah (disebut masekeh) | BERSYARAT | berada minimal satu bulan, dilewati bulan purnama dan tilem, serta upacaranya memenuhi syarat`
  why: the three qualifying conditions for the "masekeh" label are entirely unextracted.

- **S1134**  `punjung | DIPERSEMBAHKAN_KEPADA | mendiang`
  why: "sesajen **dan punjung** dihaturkan kepada mendiang" — a 2-item coordinate subject, only "sesajen" survived.

- **S1136**  `damar kurung | BERTUJUAN_AGAR | keletehan (sawa mendiang) diblokir terbatas (hanya sebatas tanah pekarangan keluarga)`
  why: **N1 gap for "agar"-purpose clauses** — the purpose clause explaining why this ritual tool exists is dropped; the widened N1 rule's examples center on "untuk"-clauses, this shows "agar"-clauses fall through the same gap.

- **S1138**  fix `mendiang | MEMPEROLEH | ayaban upakara diuskamaligi` → `... | ayaban upakara diuskamaligi yang bermakna penyucian`  (+ ADD `ayaban upakara diuskamaligi | BERTUJUAN_AGAR | leteh sawa tidak memancar ke luar dan tidak menghimbasi yang lain`)
  why: **N1 gap** — MEMPEROLEH + generic noun drops its "yang bermakna penyucian" (which means purification) relative clause, mirroring chunk-1 S32's MEMILIKI pattern with a different verb; also drops the entire result clause.

- **S1160**  `patus | ADALAH | bantuan gratis (dari komunitas/krama)`
  why: minor — the subject's own embedded relative clause ("patus yang benar-benar merupakan bantuan gratis") is informative enough to warrant its own triple, even though NER glossing already covers "patus" = Gotong Royong.

- **S1169**  fix `sawa | DIBAKAR_DENGAN | status` → `sawa | DITANAM_ATAU_DIBAKAR_SEMENTARA | status dititip (menunggu biaya untuk ngaben)`  (+ ADD `sawa (berstatus dititip) | MENUNGGU | rezeki untuk menggelar upacara ngaben beberapa bulan/tahun kemudian`)
  why: current object "status" alone is meaningless; the real content (temporary burial/cremation pending funds, followed by ngaben months/years later) is entirely unextracted, and the predicate disjunct "ditanam atau dibakar" collapses to just "dibakar", losing the "ditanam" (buried) alternative.

- **S1187**  `sesajen (ini) | DIHATURKAN_PADA_SAAT | abu jenazah dihanyutkan ke samudera`
  why: this is the sentence's real main clause (what happens to the offering) — currently dropped in favor of the wrong-subject reworking (see FIX above).

## NOTE  (borderline / systemic observation, no single fix)

- **N1 regression check — PARTIAL, stronger positive evidence than chunk 1 but real gaps persist.** Excellent holding examples: S797 (very long ADALAH clause, internally nested "atau"/"dan" coordination all intact) and S1163 (same, plus a nested disjunct-within-disjunct fully preserved) — both suggest N1's core mechanism is solid for plain ADALAH. Also holds for object_decomposition-nested "yang" clauses at S958. **Gaps found**: MEMPEROLEH+yang-clause dropped (S1138, mirrors chunk-1 S32's MEMILIKI pattern almost exactly — same failure shape, different verb, strong signal this is a verb-class gap not a one-off), BERARTI+xcomp-clause dropped to a bare, meaningless noun (S1122 — severe), BERARTI+relative-clause mid-string-mangled (S792), and ADALAH+"agar"-purpose clause dropped (S1136 — the widened rule's examples center on "untuk", this shows "agar" isn't covered). Verdict: solid for ADALAH+yang/atau/dan, still gapped for MEMILIKI/MEMPEROLEH/BERARTI-headed generic nouns and for "agar"-purpose clauses.

- **N10 regression check — leaning NOT HOLDING for the common 2-item case.** Found repeatedly across unrelated relation types: S788 (decomposition "dua kata": kept "pitra", dropped "yadnya"), S789 (decomposition "orangtua": kept "ayah", dropped "ibu"), S1056 (BERFUNGSI_SEBAGAI: kept "memandikan jenazah", dropped "dan ngringkes"), S1128 (DILAKUKAN_OLEH: kept "keluarga raja", dropped "atau pendeta"), S1134 (subject conjunct: kept "sesajen", dropped "dan punjung"), S1173 (MEMUPUK: kept "kekeluargaan", dropped "dan kebersamaan"). Positive counter-evidence: S974 (2-item "laut atau sungai" fully kept) and S616 (a full 4-item list kept, just with the wrong relation label — see FIX). Net verdict: the widened rule seems to help specific patterns (flat locative/BERUPA-style lists) but a large class of plain "X dan/atau Y" 2-item objects and subjects across other relation types is still truncated to one item — this looks like the dominant remaining failure mode in the whole corpus.

- **S13 regression check — NOT HOLDING (confirmed with a verbatim match to the spec's own example).** S972[1] "sawa anak TERTULIS lontar" leaks "sebagaimana **tertulis dalam** beberapa lontar" through as a relation — the exact phrase pattern the widened S13 rule's own description names ("sebagaimana disinggung/diuraikan/**tertulis dalam**...") is not being suppressed. This is the strongest single piece of evidence that S13 has a real, specific gap rather than being merely incomplete. Partial positive counter-note: S970's previously-flagged bad "menurut"-based triple is gone in this iteration, so suppression does work in at least some contexts — the "tertulis dalam beberapa lontar" phrasing at S972 specifically is what still slips through.

- **N6 regression check — one occurrence found, but it's the wrong sense of "termasuk".** S851 contains "termasuk setelah meninggal" (**including** after death), an adverbial/inclusive use, not the "X termasuk Y" (Y is a kind/member of X) membership-classification pattern the N6 fix targets. No genuine N6 test case exists in either chunk 1 or chunk 2 — recommend checking other chunks specifically for classification-style "termasuk" sentences (e.g. "X termasuk jenis Y") to actually validate this fix.

- **Cross-chunk wrong-subject recurrence.** S1187 ("sesajen DIHANYUTKAN_KE samudera") is the exact same bug class as flag.txt's already-flagged S58b/c (nganyut/abu confusion, chunk 1): an embedded temporal clause's own subject ("abu jenazah dihanyutkan...") gets misattributed to the outer clause's subject ("sesajen"). This is a fresh, previously-unflagged instance, suggesting the bug is systemic across the corpus rather than limited to the two originally-flagged sentences.

- **S591 vs S540 (cross-chunk duplicate text)** — see chunk 1 NOTE; same underlying sentence, inconsistent recommended verdicts (S540 → FIX, S591 → DROP per flag.txt). Recommend picking one consistent treatment for this boilerplate wherever it recurs.

- **Duplication bug** — S785's object ("istilah umat hindu bagi umat hindu di sini") repeats "umat hindu" verbatim, the same bug pattern as chunk-1 S44 ("jenazah utuh...jenazah utuh"). Recommend a dedicated pass looking for this duplication signature (a noun appearing both as a compound head and again inside a following "bagi/untuk X" phrase).

## Chunk stats
FIX: 22   DROP: 7   ADD: 26   sentences reviewed: 61

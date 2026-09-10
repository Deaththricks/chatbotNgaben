# Chunk 4 audit (S1601..S2087)

## FIX  (triple is salvageable — give the corrected triple)

- **S1601 [1]**  current: `kajang | DILAKUKAN_DI | plengkungan sawa`
  fix: `kajang | BERADA_DI | plengkungan sawa`
  why: kajang is an object, not an action — "dilakukan di" (done at) doesn't fit; it's simply located/placed there.

- **S1603 [0]**  current: `lancingan kajang | DIBAWA_KE | setra tempat pembakaran`
  fix: `jenazah | DIBAWA_KE | setra tempat pembakaran`
  why: wrong-subject bug — "di kala jenazah diangkut ke setra..." is an adverbial clause whose subject is *jenazah* (the corpse), not "lancingan kajang" (the main clause's subject, which is what's being carried aloft *while* the corpse is transported). Same class of bug as flag.txt's #58b nganyut case. See ADD for the real main-clause relation.

- **S1605 [0]**  current: `kajang | DILETAKKAN_DI | depan pendeta`
  fix: `kajang | DILETAKKAN_DI | depan pendeta yang memujanya`
  why: drops "yang memujanya" (who blesses/worships it), a minor but real qualifier.

- **S1629 [0]**  current: `kajang suratan | DIKENAL_SEBAGAI | atribut nilai martabat warga`
  fix: relabel to `kajang | BERPERAN_SEBAGAI | atribut nilai martabat warga`
  why: "dianggap ... selaku" = "considered ... as," not "dikenal sebagai" (known as) — imprecise relation label.

- **S1639 [1]**  current: `kajang | DIPUJA | pamlaspasan`
  fix: `kajang | DIPUJA_PADA | pamlaspasan`
  why: pamlaspasan is the ceremony/occasion the blessing happens at, not the object of worship — needs a locative relation, not a bare "worshipped X."

- **S1642 [1]**  current: `pelita kecil | TERBUAT_DARI | kulit telur ayam`
  fix: `pelita kecil | TERBUAT_DARI | kulit telur ayam berminyak kelapa`
  why: drops "berminyak kelapa" (oiled with coconut oil), part of the material description.

- **S1688 [0]**  current: `adegan | MELAMBANGKAN | cili`
  fix: `adegan | BERWUJUD | cili`
  why: "berwujud" = "takes the form of," a more literal fit than "melambangkan" (symbolizes).

- **S1699 [0]**  current subject: `sangaskara`
  fix: also add `samskara | ADALAH | upacara penyucian` and `panyangaskara | ADALAH | upacara penyucian`
  why: "sangaskara, samskara atau panyangaskara" is a 3-way coordinate subject (three names for the same rite); only the first survived. See N10 regression note.

- **S1713 [0]**  current: `adegan | DIAMBIL_DENGAN | penuh hormat keluarga`
  fix: `adegan | DIAMBIL_OLEH | keluarga (yang ngaben)`
  why: "oleh keluarga" is the agent and "dengan penuh hormat" is manner — these two distinct oblique roles were merged into one garbled noun phrase. The agent relation is the more useful one to keep.

- **S1732 [1]**  current: `upadesa | BERARTI | bisikan dang guru`
  add: `upadesa | BERARTI | tatwa pengarahan hidup`
  why: "atau juga berarti 'tatwa pengarahan hidup'" is a second coordinate definition, dropped entirely (2-item list, only first kept).

- **S1738 [0]**  current: `mendiang hidup | ADALAH | pemangku`
  fix: subject to plain `mendiang`; also add `mendiang | ADALAH | pejabat` and `mendiang | ADALAH | sastrawan`
  why: (a) subject-mangling bug — "semasa hidupnya" (during their lifetime) got compounded into the subject as "mendiang hidup," a nonsensical entity name; the same bug recurs at S1823. (b) the appositive list "(seorang pemangku, pejabat, sastrawan dan sebagainya)" is a 3-way conj chain and only "pemangku" was kept — a genuine N10 miss on an appositive coordination. See N10 regression note.

- **S1738 [2]**  current: `mendiang hidup | LAINNYA | ida bagus`
  fix: subject to `mendiang`; add coordinate member `ida ayu`
  why: same subject-mangling bug, plus "atau ida ayu" (2-item alternation) dropped.

- **S1753 [0]**  current: `mendiang | DIYAKINI_DENGAN | penghadang`
  fix: `mendiang | AKRAB_DENGAN | penghadang`
  why: "diyakini akan akrab dengan X" = "is believed to become close with X" — the actual predicate adjective ("akrab") was dropped in favor of the epistemic wrapper "diyakini," producing an inaccurate label.

- **S1763 [0]**  current: `banten | MENGHASILKAN | sekah abin`
  fix: drop this relation and instead add `sekah abin | BERPERAN_SEBAGAI | ciri khusus` as its own triple (see ADD)
  why: "sekah abin" is not produced by banten — the sentence coordinates two *separate* assertions (banten bebangkit/pulagembal = the base; sekah abin = the special mark), and the extractor incorrectly made one the object of the other.

- **S1763 [1]**  current subject: `banten`
  fix: `banten bebangkit atau pulagembal | BERPERAN_SEBAGAI | dasar`
  why: drops the "bebangkit atau pulagembal" qualifier specifying which kind of banten.

- **S1764 [0]**  current: `sekah abin | DIPANGKU | nama`
  fix: `sekah abin | DIPANGKU_OLEH | yang menggelar yadnya`
  why: nonsense triple — "nama" comes from the parenthetical aside "(abin = dipangku)" explaining etymology, not a real object of "dipangku." The real oblique ("oleh yang menggelar yadnya" — by the one holding the yadnha) was skipped.

- **S1782 [0]**  current: `pamerasan | ADALAH | upacara timbang`
  fix: `pamerasan | ADALAH | upacara timbang terima secara keagamaan, antara mendiang yang akan pergi ke dunia lain dengan keluarga (terutama anak-anak) yang masih hidup`
  why: two compounding defects — (1) the fixed compound "timbang terima" (handover ceremony) got truncated to just "timbang" ("weigh"), which is not even a real word for the concept; (2) N1-pattern gap — the entire defining "antara mendiang...yang masih hidup" clause explaining what the ceremony is a handover *between* was stripped. (Positive: "menurut sang arif bijaksana," the attribution phrase, correctly did NOT leak into the object — S13 holding here.)

- **S1823 [0]**  current: `mendiang masa hidup | MEMEGANG | jabatan`
  fix: `mendiang | MEMEGANG | jabatan`
  why: same subject-mangling bug as S1738 ("di masa hidupnya" compounded into the subject).

- **S1832 [0]**  current: `karma phala orangtua | DITUJUKAN_UNTUK | keturunan`
  fix: `karma phala orangtua | DIWARISKAN_KEPADA | keturunan`
  why: "diwariskan kepada" = "can be inherited by," not "ditujukan untuk" (aimed at) — these carry different meanings (inheritance vs. purpose).

- **S1845 [0]**  current: `panebusan | DITUJUKAN_UNTUK | kedudukan pitara`
  fix: `panebusan | MEMPENGARUHI | kedudukan pitara`
  why: "berpengaruh kepada" = "has an effect/influence on," not "ditujukan untuk" (aimed at) — wrong relation label misrepresents causal influence as purpose.

- **S1850 [0]**  current: `mamutru | LAINNYA | asal kata`
  fix: `mamutru | BERASAL_DARI_KATA | putru`
  why: LAINNYA is a non-descriptive bucket label, and the object dropped the actual quoted root word "putru," leaving "asal kata" (origin word) uninformative.

- **S1850 [1]**  current: `mamutru | LAINNYA | perubahan kata pitra`
  fix: `mamutru | MERUPAKAN_PERUBAHAN_DARI | pitra`
  why: same non-descriptive label issue.

- **S1889 [0]**  current: `pangabenan | DILAKUKAN | tiga hari ngaben`
  fix: `pabersihan | DILAKUKAN | dua atau tiga hari sebelum ngaben`
  why: wrong-subject bug — the sentence's actual subject of "dilakukan dua atau tiga hari sebelum ngaben" is "pabersihan" (a purification rite held *before* ngaben), not "pangabenan"/ngaben itself; the extractor conflated the two distinct ceremonies. The object also garbles "dua atau tiga hari sebelum ngaben" by dropping "dua atau" and "sebelum."

- **S1938 [0]**  current: `pengabenan | MEMILIKI | tingkat utama`
  fix: `pengabenan | DINILAI_SEBAGAI | tingkat utama`
  why: "dinilai" (is rated/regarded as) is an evaluation, not possession ("memiliki").

- **S1963 [3]**  current: `pering | LAINNYA | mahkota`
  fix: `pering | MENYERUPAI | mahkota`
  why: "bagaikan mahkotanya" = "like its crown" — LAINNYA is a non-descriptive bucket label; MENYERUPAI (resembles) fits the simile.

- **S1963 [4]**  current: `pering | DILAKUKAN_DI | sajen surya untuk surya , penebusan , pamerasan , banten teben dan sebagai nya`
  fix: split into four: `pering | DILETAKKAN_PADA | sajen untuk surya`, `... | ... | penebusan`, `... | ... | pamerasan`, `... | ... | banten teben`
  why: this is a genuine 4-item coordinate list that *was* walked correctly (all four members present) but dumped into a single garbled literal string with duplicated "surya" and stray punctuation, instead of being emitted as four separate relations the way [0]-[2] were. Inconsistent application of the N10 fix within the same sentence — see N10 regression note. Relation label also wrong (DILAKUKAN_DI doesn't fit "diletakkan ... pada sajen").

- **S2000 [1]**  current: `jenazah raja bali | ADALAH | gelgel/klungkung`
  fix: relabel/restructure to `raja bali | BERASAL_DARI | gelgel/klungkung` (or fold into the subject as "raja bali (gelgel/klungkung)")
  why: "(gelgel/klungkung)" specifies which historical kingdom the king belonged to — it modifies "raja," not "jenazah" (corpse) — treating it as an identity statement about the corpse is a mild appositive-misattribution.

- **S2002 [0]**  current: `bade | DITUJUKAN_UNTUK | keluarga`
  fix: `bade | DITUJUKAN_UNTUK | keluarga yang leluhurnya pernah menjadi punggawa dan pejabat yang sederajat`
  why: strips the defining relative clause specifying *which* families qualify — N1-pattern gap on a non-copula relation.

- **S2003 [0]**  current: `wadah | ADALAH | usungan`
  fix: `wadah | ADALAH | usungan yang tanpa badawang mungkin bertingkat memakai hiasan boma dan warna kapas terbatas`
  why: N1-pattern gap — drops the clause describing this variant (no badawang base, possibly tiered, boma ornament, limited-color cloth). Related to the still-open bade/wadah tier-and-shape-qualifier stripping pattern (see NOTE).

- **S2029 [0]**  current: `mangle | DILETAKKAN_DI | tingkatan bade`
  fix: `mangle | BERGANTUNG_PADA | tingkatan bade atau wadah`
  why: "tergantung pada" = "depends on" (quantity of mangle depends on tier count) — DILETAKKAN_DI (placed at) misrepresents a dependency relation as a location, and duplicates the (correct) placement fact already given in S2028.

- **S2087 [2]**  current: `naga banda | BERASAL_DARI | keluarga`
  fix: `naga banda | DITUJUKAN_UNTUK | keluarga tertentu saja`
  why: "dari keluarga tertentu saja" restricts *who may use* naga banda, not where it originates from — BERASAL_DARI (originates from) is the wrong relation; also restores "tertentu saja" (only certain ones).

## DROP  (triple should be removed)

- **S1738 [1]**  `mendiang hidup | DILAKUKAN_DENGAN | rendah hati`
  why: low-confidence extraction from a culturally dense, ambiguous sentence (the honorific-title-withdrawal custom around "mundurlah ida bagus/ida ayu") — the subject is mangled (see FIX above for [0]/[2]) and it's unclear the deceased is even the one acting "dengan rendah hati" (more likely the honorific-holder who withdraws). Recommend dropping rather than guessing at a fix.

## ADD  (missing triples the sentence supports)

- **S1602**  `lancingan | ADALAH | kain putih (panjangnya puluhan meter)`
  why: "yakni kain putih yang panjangnya puluhan meter" is a defining appositive for "lancingan," entirely unextracted.

- **S1603**  `lancingan kajang | DIJUNJUNG_OLEH | keturunan mendiang`
  why: this is the sentence's actual main clause (who carries the lancingan aloft) and was never extracted — see FIX above for the wrong-subject bug on the other relation from this sentence.

- **S1606**  `kajang | DIHIDUPKAN_DENGAN | puja`
  why: "disucikan dan 'dihidupkan'" is a 2-item coordinate verb sharing the same oblique ("dengan puja itu"); only "disucikan" produced a relation.

- **S1609**  `moksa | ADALAH | kembalinya unsur badan manusia ke asalnya (bhuwana agung/pancamahabutha)`
  why: "serta kembalinya pula unsur badan manusia ke asalnya..." is a second, coordinate definitional clause for moksa, entirely dropped in favor of only the first ("menjadi satunya jiwa/atma dengan paratma/brahman").

- **S1629**  `kajang | MEMILIKI | nilai dan bobot istimewa`
  why: "dianggap mempunyai nilai dan bobot istimewa" is a distinct assertion from the "selaku atribut..." predicate that was captured — both should be separate triples.

- **S1688**  `cili | TERBUAT_DARI | rontal (dilapisi kertas emas)`
  why: descriptive material detail entirely dropped.

- **S1776**  `uang kepeng | DIBUNGKUS_DENGAN | daun dapdap` (+ `uang kepeng | DIIKAT_DENGAN | benang tridatu (merah, hitam dan putih)`)
  why: the defining relative clause describing how the uang kepeng is wrapped/tied (2 coordinate verbs) was entirely dropped.

- **S1783**  `mendiang | MENYERAHKAN | hak` (+ `mendiang | MENYERAHKAN | berbagai milik yang dulunya ada pada mendiang`)
  why: "diiringi dengan penyerahan hak dan berbagai milik..." is a second coordinate handover clause, entirely dropped. (Positive: the first clause's 3-item list — swadharma, beban, tanggung jawab — was fully captured; N10 holding there, see regression note.)

- **S1823**  `upacara panebusan | ADALAH | sesuatu yang mutlak (dalam pengabenan)`
  why: the sentence's actual main clause ("dalam pengabenan, upacara panebusan merupakan sesuatu yang mutlak...") was skipped entirely in favor of only the conditional subordinate clause about the deceased's former position.

- **S1853**  `lontar putru | MEMILIKI_JENIS | putru sangaskara` (+ `lontar putru | MEMILIKI_JENIS | putru saji`)
  why: the only extracted relation ("lontar putru MEMILIKI jenis") is vacuous — it doesn't say which types. The two named types, joined via "antara lain," were dropped entirely (attached via an nmod+conj chain rather than a direct object conj, likely why the N10 walk missed it — see N10 regression note).

- **S1898**  `yeh panembak | DIGUNAKAN_PADA | pengabenan`
  why: "menunggu saat digunakan pada pengabenan" (waiting to be used at the cremation) states its eventual use and was dropped.

- **S1899**  `yeh panembak | DIPAKAI_OLEH | umat hindu di bali`
  why: "yang sudah lazim dipakai umat hindu di bali itu" is a substantial descriptive clause on the subject, entirely dropped. (Positive: both S13 — "menurut sejumlah pakar" correctly excluded — and N1 — the full "adalah sarana...paksa surya" defining clause retained — are holding on this sentence.)

- **S1915**  `pabersihan | DILANGSUNGKAN_PADA | hari senin`
  why: the sentence coordinates two clauses ("pabersihan ... hari senin dan pangabenan ... hari kamis"); only the second produced a relation.

- **S2045**  `patulangan | BERFUNGSI_SEBAGAI | tempat pembaringan jenazah (dan dapur pembakaran)`
  why: the first half of the sentence, describing patulangan's practical/functional shape (as opposed to its symbolic animal shapes, which *is* captured), was entirely dropped.

## NOTE  (borderline / systemic observation, no single fix)

- **N1 regression check (sentences S1610/S1937/S1982/S2055/S2056 named in task, plus others found):**
  HOLDING: S1610 (purpose clause "untuk mencapai moksa" retained), S1982 (purpose retained as compound "bangunan sawa"), S1650, S1657 (a strong example — full nested relative + coordinate clause retained), S1717, S1899 (full "yang digunakan oleh..." clause retained), S1639/S1732/S1782 for the *attribution-suppression* half of the pattern (see S13 note) even where the definitional half still leaks.
  **NOT HOLDING (gap):** S1937 and S2055 — both named check sentences — strip the defining clause ("yang paling banyak ada upacara..." and "bahwa mereka merupakan keturunan..." respectively; S2055's is a `ccomp`, a distinct attachment the fix doesn't seem to cover). S2056 has no clause to strip (object is already a complete compound) so it's not a meaningful test either way. Additional gap instances found beyond the named list: S1782 (major — "timbang terima" itself truncated plus the whole defining clause dropped), S2002, S2003. **Verdict for chunk 4: partial**, same failure shape as chunk 3 — holding for "purpose"/"berfungsi sebagai" shapes reachable via xcomp/nmod on the copula, still leaking for `bahwa`-ccomp and plain relative clauses on the object noun.

- **N10 regression check:** object-side coordinate lists mostly still succeed — S1783 (3-way), S1963 [0]-[2] (3-way) both fully captured — but two new failure shapes surfaced in this chunk: (1) **subject-side** coordination is still dropped, same as chunk 3 — S1699 (3-way subject: sangaskara/samskara/panyangaskara, only 1 kept), and an **appositive**-coordination miss at S1738 (3-way: pemangku/pejabat/sastrawan, only 1 kept); (2) S1963[4] shows the walk *succeeding* (all 4 members reached) but then dumping them into one garbled literal string instead of emitting separate relations — an inconsistency in how the fix is applied even within a single sentence. S1853 shows a list attached via nmod+conj (rather than direct object conj) that the walk missed entirely. **Verdict: partial**, with the subject-side gap now confirmed as a recurring, systemic hole across both chunks rather than an isolated miss.

- **S13 regression check:** holding well in this chunk — S1639 ("sebagaimana telah disinggung di depan," the exact named pattern), S1732 ("menurut para ahli"), S1782 ("menurut sang arif bijaksana"), and S1899 ("menurut sejumlah pakar") were all correctly excluded from the extracted objects. **Verdict: holding** for `menurut X` and `sebagaimana ... disinggung ...` shapes in this chunk (contrast with chunk 3, where two leak-throughs were found — the fix appears inconsistent rather than absent).

- **N6 regression check:** S2065 is a second confirmed instance of the same anchor-resolution bug seen at S1493 (chunk 3) — the member/category swap direction is correct, but "termasuk"/enumeration items ("api jatu pembakaran," "linting anugrah ida sang sulinggih") get anchored to the nearest proper noun ("tirtha pangentas") rather than the true category ("segala sesuatu syarat agama" / the overall ceremony). Given how convoluted the source sentence is, low confidence either way — flagging as a FIX candidate but DROP is defensible too. **Verdict: partial**, same as chunk 3.

- **N5/N7/N8/N9 (still-open, unfixed) confirmation:** S2055 and S2056 both confirm the named bade/patulangan shape-qualifier-stripping pattern — "patulangan yang berbentuk naga kahang dan gajah mina" / "yang berbentuk macan, singa, gadarba..." both get reduced to bare "patulangan" as the subject, exactly as flagged as still-open. Additionally, a related but distinct **new** subject-mangling pattern was found (not on the named list): "mendiang" + a temporal oblique ("semasa/di masa hidupnya") gets fused into a garbled compound subject "mendiang hidup" / "mendiang masa hidup" at S1738 and S1823 — worth tracking separately from the bade/patulangan issue since it's a different mechanism (fusing an adjunct's head noun into the subject, rather than dropping a qualifier from it).

- **S2000, S2028, S2029, S2034**: "bade" and "wadah" are NER-canonicalized as the same entity (wadah → canonical Bade), so several "atau wadah" coordinate members being dropped (S2028, S2029, S2034) are lower-priority than a true missing-entity case — flagging for awareness but not scoring as hard misses.

## Chunk stats
FIX: 29   DROP: 1   ADD: 13   sentences reviewed: 61

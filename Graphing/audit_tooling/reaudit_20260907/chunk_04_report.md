# Chunk 4 audit (S1699..S2198)

Convergence re-audit. All 59 sentences in this chunk are already covered by
flag.txt "Part 1 — S1482 through S2363". Most of those fixes/ADDs have been
applied in this data (spot-confirmed on S1713, S1714, S1732, S1753, S1754,
S1763, S1764, S1776, S1783, S1823, S1832, S1845, S1850, S1898, S1915, S1938,
S2029, S2087, S2093, S2115, S2117, S2124, S2130, S2133, S2180, S2198). What
follows is (a) flag.txt fixes that were only partially applied and (b) issues
not caught in flag.txt.

## FIX  (triple is salvageable — give the corrected triple)

- **S1782 [0]**  current: `pamerasan | ADALAH | upacara timbang , antara mendiang yang akan pergi ke dunia lain dengan keluarga ( terutama anak-anak ) yang masih hidup`
  fix: `pamerasan | ADALAH | upacara timbang terima (secara keagamaan)`
  + ADD `pamerasan | DILAKUKAN_ANTARA | mendiang dan keluarga yang masih hidup`
  why: flag.txt 1782 (/112) proposed exactly this split; not applied. Raw (line 1402):
  "Pamerasan adalah upacara timbang terima secara keagamaan, antara mendiang yang akan
  pergi ke dunia lain dengan keluarga (terutama anak-anak) yang masih hidup." The object
  still dumps most of the sentence and truncates "timbang terima" (handing-over / weighing-and-receiving)
  to a bare "timbang" with a stray comma.

- **S1982 [0]**  current: `bade | ADALAH | bangunan sawa`
  fix: `bade | ADALAH | bangunan untuk sawa`
  why: flag.txt 1982 fix was "bangunan untuk sawa"; the dedup instead dropped "untuk",
  yielding "bangunan sawa" (corpse-building) which loses the purposive sense. Raw: "Bade
  adalah bangunan untuk Sawa."

- **S1987 [0]**  current: `bade jenis | ADALAH | bade dalam tata kemasyarakatan pada zaman itu`
  fix: `jenis bade yang dipakai seseorang | DITENTUKAN_BERDASARKAN | status orang tersebut dalam tata kemasyarakatan pada zaman itu`
  why: current triple is nonsense on both ends ("bade jenis" fragment subject; object just
  restates the subject with a locative tacked on). Raw: "Bade jenis apa yang boleh dan wajar
  dipakai oleh seseorang, ditentukan berdasarkan statusnya dalam tata kemasyarakatan pada
  zaman itu." The real predicate is "ditentukan berdasarkan". flag.txt 1987 rated this only
  /116; it is closer to /120.

- **S2034 [0]**  current: `mangle | ADALAH | pengganti tingkat bade`
  fix: `mangle | ADALAH | pengganti tingkat bade atau wadah`
  why: flag.txt 2034 (/115) — 2-item list "bade atau wadah", second member dropped. Raw:
  "mangle merupakan pengganti tingkat bade atau wadah." (See also DROP of [1] below.)

- **S2045 [0]**  current: `patulangan | MENGHASILKAN | bentuk yang berwujud binatang , yang mempunyai nilai religi tertentu`
  fix: `patulangan | DIBUAT_BERBENTUK | binatang (yang mempunyai nilai religi tertentu)`
  why: MENGHASILKAN (produces) is a mislabel — patulangan does not produce shapes, it is made
  in animal shapes. "patulangan dibuat dalam berbagai bentuk yang berwujud binatang".

- **S2055 [0]**  current: `patulangan | ADALAH | pertanda bahwa mereka merupakan keturunan dari orang yang condong pada paksa wesnawa`
  fix: `patulangan yang berbentuk naga kahang dan gajah mina | ADALAH | pertanda bahwa keluarga tersebut keturunan dari orang yang condong pada paksa wesnawa`
  why: subject over-generalizes. The sign of wesnawa descent is specifically a *naga-kahang / gajah-mina*
  shaped patulangan (raw: "patulangan yang berbentuk naga kahang dan gajah mina ... adalah pertanda
  bahwa mereka merupakan keturunan..."), not any patulangan. "mereka" is also unresolved anaphora
  ("that family").

## DROP  (triple should be removed)

- **S1738 [3]**  `mendiang | MEMILIKI_ALIAS | ida bagus`
- **S1738 [4]**  `mendiang | MEMILIKI_ALIAS | ida ayu`
  why: wrong entity. Raw (line 1369): "...dengan rendah hati mundurlah Ida Bagus atau Ida Ayu
  kita. Mereka tak jadi menggunting adegan itu." "Ida Bagus / Ida Ayu" here = the young walaka
  brahmana (putra-putri pendeta) who would perform the hair-cutting; when the deceased was
  prominent they humbly withdraw. These are not aliases of the deceased. flag.txt 1738 only
  flagged the LAINNYA label (/116); the manual_override then encoded a factually wrong ALIAS claim.

- **S1747 [3]**  `sekah kangsen | DISERTAI_DI | samping jenazah`
  why: "sekah kangsen" does not occur anywhere in S1747, and DISERTAI_DI is not a predicate.
  Raw (line 1372): "Begitulah setelah Paguntingan dan Upadesa, berakhirnya, kembalilah Adegan
  didudukkan pada ruang paturon di samping jenazah." Hallucinated subject. If anything the
  intended fact is `adegan | DIDUDUKKAN_DI | ruang paturon (di samping jenazah)` — but [0]
  already carries `adegan | BERADA_DI | ruang paturon`; just append "(di samping jenazah)" to [0].

- **S1853 [0]**  `lontar putru | MEMILIKI | jenis`
  why: vacuous ("has types" with no type named). flag.txt 1853 (/112) said this should be
  replaced by the named types — [1]/[2] (putru sangaskara / putru saji) were added but [0]
  was left in place. Remove [0].

- **S2000 [1]**  `jenazah raja bali | ADALAH | gelgel/klungkung`
  why: a corpse is not a place. "(gelgel/klungkung)" modifies "raja bali". flag.txt 2000
  (/116) proposed `raja bali | BERASAL_DARI | gelgel/klungkung`, which was added as [3];
  the object_decomposition [1] was left behind and is now redundant nonsense.

- **S2034 [1]**  `mangle | DILETAKKAN_DI | wadah`
  why: misreads the coordinate "bade atau wadah" as a location. S2034 says nothing about
  placing mangle in a wadah; it says mangle substitutes for the *tier* of a bade/wadah.

- **S1714 [1]**  `adegan | DITUJUKAN_UNTUK | pendeta`
  why: what is directed to the priest is the sembah bakti, not the adegan. [0] (`adegan |
  MELAKUKAN | sembah bakti`) and [2] (`adegan | DIBAWA_MENGHADAP | pendeta`, manual_override)
  already cover the sentence; this leftover dependency_rule triple is a redundant misfire.

- **S2184 [1]**  `bale salunglung | DILETAKKAN_DI | arah hulu`
  why: redundant with and less precise than [2] (`... | DILETAKKAN_DI | sekitar empat atau
  lima meter di arah hulu dari tempat pembakaran jenazah`, manual_override), which was added
  per flag.txt 2184.

## ADD  (missing triples the sentence supports)

- **S1717**  `adegan | ADALAH | alat upakara`
  why: raw "adegan, adalah alat upakara, tempat atma mendiang didudukkan." Current sole triple
  keeps only "tempat atma mendiang"; the explicit "adalah alat upakara" identity is dropped.

- **S1963**  `pering | MELAMBANGKAN | purusa-pradana`  +  `pering | DILETAKKAN_PADA | sajen untuk surya`  +  `... | penebusan`  +  `... | pamerasan`  +  `... | banten teben`
  why: current data has only `pering | MENYERUPAI | mahkota`. flag.txt 1963 wanted the garbled
  dump replaced by 4 split placement relations and noted [0]-[2] (pering as perlambang
  purusa-pradana etc.) were clean — but the override collapsed everything to the single
  mahkota simile. Raw (line 1545): "Pering dibuat berpasang-pasangan sebagai perlambang
  purusa-pradana dan diletakkan ... pada sajen untuk Surya, Penebusan, Pamerasan, Banten
  Teben dan sebagainya."

- **S2002**  `bade | MEMILIKI_TINGKAT | tujuh`
  why: S2000 and S2001 both got a MEMILIKI_TINGKAT triple for their tier count (11, sembilan);
  S2002 ("bade bertingkat tujuh") did not. Inconsistent.

- **S2087**  `naga banda | DIGUNAKAN_DALAM | upacara palebon (ngaben)`
  why: the main clause "naga banda hanya digunakan dalam upacara palebon (ngaben)..." is
  unextracted; current sole triple keeps only the "dari keluarga tertentu saja" restriction.

- **S1845**  `semua upacara dalam pitra yadnya | MEMPENGARUHI | kedudukan pitara`
  why: coordinate subject "panebusan dan bahkan semua upacara dalam pitra yadnya" — only
  "panebusan" was kept.

## NOTE  (borderline / systemic observation, no single fix)

- **S1732**  raw text is genuinely truncated mid-clause ("...satu hal perlu kita catat,
  bahwa" — no continuation), as flag.txt already noted. The 3 triples are individually OK;
  [1] "bisikan dang guru" drops "kepada sisia" (to the pupil) — minor.

- **S1747 [1]/[2]**  `adegan | BERAKHIR_SETELAH | paguntingan / upadesa` — flag.txt 1747
  (/121) flagged these as bare-temporal-marker labels and they are still unaddressed. They
  are also semantically wrong: what "berakhir" is paguntingan + upadesa, not adegan. Recommend
  drop both, or fold into a real predicate on the correct subject.

- **S2065 [0]/[1]**  `tirtha pangentas dan segala sesuatu syarat agama | BERISI | api jatu
  pembakaran / linting anugrah ida sulinggih` — fused subject + BERISI mislabels "termasuk"
  ("including", listing another requirement carried out, not container-contents). flag.txt
  2065 rated this /114 (leave as known-weak); I lean toward DROP both — they misrepresent
  the sentence and the subject is unusable.

- **S1738 [0]/[1]/[2]**  `mendiang | ADALAH | pemangku / pejabat / sastrawan` flattens the
  conditional "kalau mendiang ... punya kedudukan tertentu (seorang pemangku, pejabat,
  sastrawan dan sebagainya)". `mendiang | MEMPUNYAI_KEDUDUKAN | ...` would be truer, and the
  whole S1738 sentence is culturally dense (priest's children defer to a prominent deceased) —
  an ADD like `putra-putri pendeta (ida bagus/ida ayu) | TIDAK_JADI_MENGGUNTING | adegan (bila mendiang terkemuka)`
  would capture the actual point.

- **S1931 [0]**  `recadana atau swasta geni | MELENGKAPI | pangabenan` — the garble flag.txt
  1931 flagged is fixed, but MELENGKAPI is loose for "pangabenan telah selesai dengan tuntas"
  (a simple recadana / swasta geni is already *sufficient to complete* the pangabenan), and
  "yang sederhana" (simple) is dropped from swasta geni.

- **S1783 [3]**  object "hak dan berbagai milik yang dulunya ada pada mendiang" — the relative
  clause is mildly redundant; "hak dan berbagai milik (mendiang)" is tighter (/115).

- **S2124 [1]**  object "mamari-suddha ( menyucikan ) dunia ini" carries a clunky spaced
  parenthetical gloss; "menyucikan dunia ini" is cleaner. Possessive "beliau" dropped from
  both relations — minor.

## Chunk stats
FIX: 6   DROP: 8   ADD: 5 sentences (9 triples)   sentences reviewed: 59

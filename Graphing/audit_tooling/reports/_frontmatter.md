# Ngaben relation-extraction — Iteration 1 audit

**Scope:** every relation record in `Results/Final/relation_results_ngaben/` after the Iteration 0
fixes were run — **777 triples across 489 sentences** (down from 792/496 pre-fix), checked one by
one against the source sentence, the NER tags and the CoNLLU parse. Method and rubric unchanged
from Iteration 0 (`audit_tooling/AUDIT_INSTRUCTIONS.md` + `flag.txt`). Work was fanned out over 8
parallel `general-purpose` auditors (~62 sentences each, last chunk 55); each was additionally
asked to flag any triple that an Iteration 0 fix should have caught, as a named regression /
fix-gap. This document consolidates them.

**Standing rule honoured:** this is the report. No code, notebook or output file has been changed.
Nothing gets edited until you approve — [[feedback_report_before_fix]].

---

## 1. Headline numbers

| Verdict | Iteration 1 | Iteration 0 (v1) | Delta |
|---|---|---|---|
| **FIX** — triple salvageable, corrected form given | **285** | ~324 | −39 |
| **DROP** — triple should be removed | **89** | ~102 | −13 |
| **KEEP** — correct / minor-nuance-only, left unlisted | ~403 | ~366 | +37 |
| **ADD** — missing triples the sentences support | **~415** (across ~300 sentences) | ~340 | +75 |
| Corpus size | 777 triples / 489 sentences | 792 / 496 | −15 / −7 |

FIX and DROP both fell — the Iteration 0 rule changes measurably cleaned the corpus. ADD rose,
mostly because agents were told to be generous and this pass hit several very information-dense
procedural passages (body preparation, ritual-tool assembly) that were barely touched in v1's
chunking. Read as a rate: v1 was ~53% FIX+DROP of 792; this pass is ~48% of 777 — real but modest
improvement, concentrated in a few defects (below) rather than spread evenly.

### Per-chunk breakdown

| Chunk | Range | FIX | DROP | ADD | reviewed |
|---|---|---|---|---|---|
| 1 | S4–S560 | 36 | 9 | 77 | 62 |
| 2 | S591–S1188 | 28 | 13 | 55 | 62 |
| 3 | S1189–S1597 | 31 | 12 | 33 | 62 |
| 4 | S1601–S2087 | 43 | 9 | 39 entries (~70 triples) | 62 |
| 5 | S2093–S2630 | 41 | 11 | 43 | 62 |
| 6 | S2635–S3155 | 39 | 9 | 37 | 62 |
| 7 | S3165–S3836 | 34 | 11 | 78 | 62 |
| 8 | S3843–S4340 | 33 | 15 | 53 | 55 |
| **Total** | | **285** | **89** | **~415** | **489** |

---

## 2. Iteration 0 scorecard — did the landed fixes hold?

Verified two ways: (a) direct query of the regenerated `relation_results_ngaben.json` for the
flagship sentences Iteration 0 targeted, (b) every regression the 8 auditors flagged in-chunk.

| Fix | Verdict | Evidence |
|---|---|---|
| **S1** object-side negation → drop | **HOLDING, strong** | Verified directly: **S2477** ("tanpa jenazah / dengan tanpa tulang") now has **0 triples** (was 2 false-positive assertions). **S3622** ("bhuta kala … menjadi hilang") now **0 triples**. **S1409** ("bukan dari hasil galian … juga bukan dari sawa") now has only the one *unrelated* triple left, both negated ones gone. Two residual chunk-flagged gaps: S925[1] "tanpa upakara apapun" still asserted positively (ch2); S2758[1] "tanpa berbadan sama sekali" still asserted (ch6). Both are `tanpa` inside a *nested* clause, not the direct object subtree — likely why the scan misses them. |
| **S2** passive `masuk`/`naik` → `DIMASUKKAN_KE_DALAM`/`DINAIKKAN_KE`, not `MENUJU` | **HOLDING, with one open edge** | `MENUJU` count corpus-wide is down to **3** (was ~14+ pre-fix). Confirmed correct in S217, S370, S1221, S1439, S1483, S2644, S2787, S2948, S3134 across chunks. Gap: **active-intransitive `naik ke X`** (no `di-...-kan` passive morphology) isn't covered by the fix — S3354 still emits `MENUJU`, S3295 falls through to `LAINNYA` (ch7). Also one `DIBAWA_KE` used for `dimasukkan ke dalam` at S4273 (ch8) — a different verb form (`dibawa` vs `dimasukkan`) than the fix targets. |
| **S3** copula + bare generic-category noun keeps the `yang`/`untuk`/`dari` clause | **NOT HOLDING — the #1 open defect this iteration** | Fresh violations in **all 8 chunks**, ~45 triples total (S6/S47/S126/S128 ch1; S738/S797/S1136 ch2; S1189/S1205/S1206/S1261/S1429/S1456 ch3; S1610/S1937/S1982/S2055/S2056 ch4; S2198/S2258/S2377 ch5; S2872/S3155 ch6; S3586 ch7; S4077/S4086/S4106/S4111/S4126/S4128/S4170 ch8). The fix only fires on a narrow shape; it misses: **parataxis** (`berfungsi sebagai …`), **`acl:relcl` on `berakar pada`/`berupa`**, **`bahwa`-complements**, **`selaku sarana untuk V`**, and — the largest sub-pattern in chunk 8 — **`MEMILIKI fungsi/hubungan/simbol + truncated head`** where the real predicate is a whole `untuk…`/`dari…`/`dengan…` continuation, not a relative clause at all. |
| **S4** `ADALAH`/bare-verb → real predicate (`BERBENTUK`/`BERARTI`/…) | **PARTIAL** | The `VERB_STUB_OBJECTS` backstop clearly removes the worst cases (no more `ADALAH menjadi`/`ADALAH berfungsi` fragments reported). Still leaking: `berarti` → still `ADALAH` (S61 ch1); `berbentuk`/`berwujud` → `ADALAH` or wrongly `MELAMBANGKAN` (S69 ch1, S1688/S2045 ch4, S2180 ch5); `berputar` (S2380 ch5); a doubled `adalah adalah` artifact (S4177 ch8). `_SHAPE_MEANING_NONCOPULA` needs `berwujud` and `berarti` added, and the `berwujud→MELAMBANGKAN` confusion needs its own guard (berwujud = takes the physical form of; MELAMBANGKAN = symbolizes — not interchangeable). |
| **S8** `sirat`/`percik` family → `DIPERCIKKAN_PADA` | **HOLDING, one direction gap** | Correct wherever the verb carries `kepada`/`terhadap` (S2548, S3165, S3783, S4035, and the `disembur`/`disemburkan` variants). Gap: the **bare applicative `X disirati tirtha`** (no adposition — the theme is a plain object, not marked with `terhadap`) still comes out with subject/object inverted — S1422 (ch3): `sawa | DIPERCIKKAN_PADA | tirtha` should be `tirtha | DIPERCIKKAN_PADA | sawa`. |
| **S9** `X MELAMBANGKAN lambang` tautology | **PARTIAL** | The exact `lambang`/`simbol` head is usually stripped, but the near-synonym **`tanda`** and the phrase **`sebagai simbol X`** are not covered: S58[3]/S219 (ch1), S2336[3] (ch5), S3544 (ch7). |
| **S13** attribution adjuncts (`menurut…`, `dalam lontar…`) suppressed | **PARTIAL** | The `menurut ahli/pakar/pustaka` lemma guard clearly works (confirmed clean in ch4, ch5). Not covered: **`dalam lontar X`** as an alias source (S283 ch1 — the exact flag.txt 283b/c case, still recurring), **`sebagaimana tertulis/disinggung/diuraikan dalam …`** (S972 ch2, S1255/S1414 ch3), **`menurut lontar …`** (S1452 ch3), **`di mata umat hindu`** idiom (S1226 ch3), **`sebagaimana halnya X`** comparative (S2542 ch5). |
| **S15** `berisi`/`diisi` → `BERISI`/`DIISI_DENGAN`, not `MEMILIKI` | **HOLDING where the trigger verb fires, two residual gaps** | Correct wherever `berisi`/`diisi` is the governing verb (S3118, S3141, S3142, S3734 and others). Gaps: (a) `MEMILIKI` still used for **existential "there exists / ada … yang …"** — S3914 "jenazah MEMILIKI rangkaian upacara lain" (ch8), and for a non-container subject S3742[1] "kesuna MEMILIKI kuku" (ch7); (b) `berisi` sometimes **not extracted at all** when it sits on a dropped `conj` branch — S344 (ch1), S1657 (ch4). |
| **Overrides**: S133 re-anchor, S1298 empty, S3755–S3758 five-metals | **LANDED, verified clean** | S133 carries exactly the 2 intended override triples, matching its current text. S1298 correctly empty (misconception sentence). **S3755–S3758: all 16 rows are `manual_override`, complete (BERWARNA/BERADA_DI/BERDEWA per metal), and there is no leaked auto-extraction `dewa ADALAH dewa X` alongside them** — confirmed by reading the bundle RELATIONS block directly. Chunk 7's audit report lists these as FIX items quoting the *pre-Iteration-0* `dewa ADALAH dewa iswara` form; that finding is **stale/superseded** and should be disregarded — the override is already correct. Only real nit: S133's override predicate is written `TIDAK MENJAMIN` with a literal space, inconsistent with the corpus's `UPPER_SNAKE_CASE` convention elsewhere. |

---

## 3. New / re-ranked systemic defects for Iteration 2

Numbered fresh (N1…) where the pattern wasn't named in v1, or re-flagged from v1's S-numbers where
still fully open. Ranked by estimated triple count affected.

### N1 (was v1 S3, now the top lever). Copula + generic-noun clause-stripping — see scorecard above.
~45 FIX + an unknown but large share of the 415 ADD depend on this one rule.
**Fix location:** `extract_definition_relations` (current offset **L2048**) + the
`GENERIC_CATEGORY_NOUNS` set from Iteration 0. Needs: parataxis handling, `bahwa`-complement
support, and a distinct path for `MEMILIKI fungsi/hubungan/simbol + head` (this shape isn't a
copula at all — it needs its own rule in `derive_raw_relation_label`, not the copula extractor).

### N2. `DILAKUKAN_DI`/`DILAKUKAN_SAAT` on a non-event sarana (v1 S7 — still fully open)
A lamp is *lit*, a kajang/ornament is *placed*, an effigy is *seated* — not "performed at/when".
Cases across every chunk from ch4 on: S1601, S1639, S1681, S1963, S2028, S2133, S3150, S3165,
S3195. **Fix location:** `derive_raw_relation_label` (**L283**), rule 12 area — needs
`subject_label` plumbed in (the exact plumbing v1 already called for) so `SARANA_RITUAL` /
`BANGUNAN_RITUAL` subjects route to `DILETAKKAN_DI`/`DIGANTUNG_DI`/`DINYALAKAN_SAAT`/
`DIGUNAKAN_SAAT` instead.

### N3. Benefactive / locative passives invert subject and object
`dihaturkan`/`disuguhi`/`ditaruhkan`/`dibuat untuk`/`diturunkan dari`/`memberikan … kepada` put
the recipient or location in subject position: S2843, S3080, S2794, S2885, S2986, S1082 (v1-era),
plus ~10 more in chunk 6 alone. Broader than v1's S5 (which only covered the Balinese
offering-list subset) — this is a general Indonesian benefactive-passive problem.
**Fix location:** `_emit_relations_for_verb` (**L1105**) — add a lemma class
`{hatur, suguh, taruh(kan), beri(kan), turun(kan)}` that, when the verb is passive and the subject
is animate/BANGUNAN/place, swaps to `<obj> <REL> <subj>`.

### N4. `DIISI_DI <body-part>` mis-types placement AND drops contents
`di <body-part>, diisi sebuah X yang berisi <contents>` → should split into
`X DILETAKKAN_DI <body-part>` + `X BERISI <contents>`; currently emits
`X DIISI_DENGAN <body-part>` and the contents list is lost entirely. S3546, S3747, S3749, S3753
(ch7) — the single densest information loss found this iteration (every coin/flower count in the
kawangen-placement passage is gone). **Fix location:** `find_object_tokens` (**L844**) /
`derive_raw_relation_label` — needs a two-triple emission for this shape, not a relabel.

### N5. `bade`/`patulangan` qualifier stripping (v1 S6-adjacent, sharpened)
Tier number (`bertingkat 11/9/7`) and shape (`berbentuk naga kahang/macan/singa`) dropped,
collapsing distinct facts into contradictory near-duplicate triples: S2000–S2002, S2045, S2055,
S2056. **Fix location:** `expand_phrase` (**L1337**) — a `bertingkat NUM` / `berbentuk NOUN`
modifier on the subject head should never be trimmed.

### N6. `termasuk X` direction reversed (v1 S11 — still open)
`semua sekah termasuk sangge` → sangge is the *member*, not the subject's whole. S2748, S2794 (ch6).
**Fix location:** `derive_raw_relation_label` (**L283**), `CLASSIFY_LEMMAS` branch — swap subject/
object for surface `termasuk` with an NP object.

### N7. Section-heading noun captured as clause subject (v1 S14 — still fully open)
`itik-itik,` / `kwangen jeriji,` / `gegaleng kepala:` / `lekesan,` bound as nsubj of the next
passive verb → junk triples (`itik-itik SETELAH kuku kaki`, `kwangen jeriji DITARUH kwangen
jeriji`). S3237, S3546, S3604, S3653, S3733, S3760, S3973 — all in chunk 7/8's body-prep section.
**Fix location:** `find_subject_clause_relations` (**L1897**) — detect the `NOUN (,|:) …` opening
and treat the lead noun as a topic label, not an argument of the following clause.

### N8. Leading discourse adverb / trailing clitic glued to subject
`demikian bhuwana agung`, `kedua ngangsen`, `mendiang hidup`, `jenazah baru`, `rurub sinom tadi`,
`pengerikan kuku mutlak`. **Fix location:** `expand_phrase` (**L1337**) — strip sentence-initial
`demikian/kedua/begitu pula/sedang` and trailing `baru/tadi/ini/tersebut/mutlak/asli` from the
subject span (this is the same function as N5, so N5+N8 should land together).

### N9. `object_decomposition` over-fires on appositives / example lists / parentheticals
Manufactures fragment subjects (`pelita kecil`, `alat upakara`, `kajang suratan`, `jenazah raja
bali`, `mendiang hidup`, `dua kata`) and tautology `ADALAH` edges (`sarana ADALAH sulinggih
pujastawa`). **Fix location:** `decompose_object` (**L1788**) — restrict `DECOMPOSE_OBJECTS`
firing to genuine `X, yaitu/yakni Y` alias appositives; suppress on `(e.g. …)`-style parentheticals
and coordinate example lists.

### N10. Coordinate-member loss (v1 S10 — still open, ~30+ triples)
`adegan dan pengawak`, `sasih kasa dan kapitu`, `sungai atau laut`, multi-item component lists —
consistently only the first `conj` child survives. **Fix location:** `get_conjuncts` (**L1387**).

### N11. Kawi verse `X sangkaning Y mulih maring X` split on `sangkaning` as a name
S4303, S4304 (ch8) — same defect v1 flagged, unresolved. Needs the two-triple rewrite
`Y BERASAL_DARI X` + `Y KEMBALI_KE X`, most cleanly as a targeted manual override (only 2
sentences) rather than a general rule.

### N12. Massive procedural under-extraction (not a bug — a coverage gap)
Body-prep and ritual-tool-assembly sentences (S3122, S3134, S3141, S3142, S3153, S3154, S3604,
S3734, S3760, S3973, S4035, S4090, S4273) each carry 3–6 recoverable triples (grind → shape → tie
→ insert → fill → place → purpose chains); the rules currently pull 1–2. This is where a large
share of the ~415 ADD proposals in §4 come from. Not urgent to fix as a "defect" — it's an ADD-
appetite decision (§4 below).

---

## 4. Recommended resolution path for Iteration 2

1. **N1 (copula/generic-noun clause) first** — it's now the single highest-leverage rule, spanning
   every chunk. Rework `extract_definition_relations` to always retain the `yang`/`untuk`/`dari`/
   `bahwa` clause (object or second triple), and give the `MEMILIKI fungsi/hubungan/simbol + head`
   shape its own rule in `derive_raw_relation_label` rather than routing it through the copula path.
2. **Plumb `subject_label` into `derive_raw_relation_label`** — this single change unblocks N2 and
   sharpens N3; it was already deferred from Iteration 0's S7.
3. **N10 (`get_conjuncts` transitive walk)** — cheap, recovers ~30+ triples across every chunk.
4. **Span-hygiene batch** — N5, N7, N8, N9 together in `expand_phrase` / `find_subject_clause_relations`
   / `decompose_object`; they're all "don't trust the raw dependency span, trim/gate it" fixes.
5. **S13 lemma/phrase-list extension** — cheap, add `dalam lontar X`, `sebagaimana tertulis/
   disinggung/diuraikan dalam`, `di mata X`, `sebagaimana halnya X` to the attribution-adjunct guard.
6. **N4 (`DIISI_DI` two-triple split)** — narrow but high-value (recovers every coin/flower count
   in the body-prep passage).
7. **Balinese offering-list retag (v1 S5)** — still deferred; needs the UPOS-level `ring`/`lan`/
   `saha`/`utawi`/`sane` pre-pass in `LEMMA_CORRECTIONS`. Chunk 2's audit shows it landed for one
   shape (S618) but not the sibling S616/S641 sentences — worth revisiting alongside N3.
8. **Manual overrides**: N11 (S4303/S4304 two-triple rewrite), the S133 predicate underscore, plus
   the ~30–40 per-sentence semantic-reversal FIX/DROP in §5 below that no general rule can safely
   recover.
9. **N12 / ADD appetite** — needs your call (see below); it roughly doubles per-sentence yield in
   the procedural passages if fully pursued.
10. **Re-run the notebook** (you run it) → regenerate `Results/Final/` → propagate any new predicate
    vocabulary to `Neo4/normalize.py` + `kb/relation_phrases.json` per
    [[project_neo4j_graph_cleanup]] / [[project_ngaben_chatbot_kb]].

**Suggested review order for §5** (per-chunk detail below): skim each chunk's **DROP** list first
(fastest agreement), then the **FIX** items that map to N1–N12 above (systemic, will be batch-
fixed), then decide the **ADD** appetite for N12-class procedural sentences — e.g. "accept ADDs
that name a ritual entity/sarana or a symbolic meaning; defer pure step-by-step procedure capture
unless you want full procedural coverage."

---

## 5. Per-chunk findings (full detail)

Each chunk below lists every FIX (current → corrected triple + reason), DROP (+ reason), ADD
(+ source phrase) and NOTE for its sentences, exactly as returned by the auditing sub-agent for
that chunk. Sentence IDs are contiguous per chunk. One correction applied to the raw agent output:
chunk 7's S3755–S3758 entries are noted in §2 above as stale (the manual_override already covers
them correctly) and should be disregarded rather than acted on.


# Ngaben relation-extraction — Iteration 2 audit

**Scope:** every relation record in `Results/Final/relation_results_ngaben/` after the Iteration 1
fixes were run — **784 triples across 487 sentences** (was 777/489 after Iteration 0's fixes;
792/496 pre-fix). Method and rubric unchanged from Iteration 0/1
(`audit_tooling/AUDIT_INSTRUCTIONS.md` + `flag.txt`). Work was fanned out over **4 parallel
`general-purpose` auditors** (~122 sentences each, i.e. two of the eight `build_bundles.py` chunks
per agent — half the agent count of Iteration 1, at the user's request, with no reduction in
per-sentence scrutiny). Each agent was additionally given the specific Iteration 1 fixes (N1, N10,
S13, N6, N11) and the exact flagged sentence IDs to check directly for regressions, plus spot-checks
on the still-open N3/N4/N7 defects. This document consolidates all four.

**Update — fixes landed:** per the loop's standing pre-approval (audit → report → implement without
a second prompt, unless risky/semantic-reversing — see [[feedback_report_before_fix]] and
`RELATION_AUDIT_RUNBOOK.md` §1), the systemic-defect batch below (D1-D4, D7-D10, D13, D14 + 5
targeted `MANUAL_RELATION_OVERRIDES`) has been implemented in cell 51 and verified (harness 83/83,
smoke 0 errors — full detail in the runbook's Iteration 2 changelog). D5/D6/D11/D12/D15/D16 and a
handful of individually-cited sentences (S2612/S2986/S2885) were deliberately deferred — either too
risky to generalize with confidence in the time available, or (D16) a scope call that's the user's
to make, not a rule fix. **The `Results/Final/` output below still reflects the PRE-fix (Iteration
1) state** — everything in §1–§5 is the audit that this fix batch was written in response to.
Re-run the notebook to see them take effect, then the Iteration 3 audit re-checks the same way
Iteration 2 re-checked Iteration 1.

---

## 1. Headline numbers

| Verdict | Iteration 2 | Iteration 1 | Iteration 0 (v1) | Δ (I2 vs I1) |
|---|---|---|---|---|
| **FIX** — triple salvageable, corrected form given | **253** | 285 | ~324 | −32 |
| **DROP** — triple should be removed | **36** | 89 | ~102 | **−53** |
| **KEEP** — correct / minor-nuance-only, left unlisted | ~495 | ~403 | ~366 | +92 |
| **ADD** — missing triples the sentences support | **171** | ~415 | ~340 | −244 |
| Corpus size | 784 triples / 487 sentences | 777 / 489 | 792 / 496 | +7 / −2 |

**Reading this:** DROP nearly halved (89→36) — the Iteration 1 fixes (S1 negation, N11 overrides,
N6 direction, the manual overrides) genuinely eliminated a lot of nonsense/reversed triples. FIX
fell more modestly (285→253) because, as §2 details, several Iteration 1 fixes only patched a
narrow sub-shape of their target pattern and the *same failure mode* keeps resurfacing under a
different verb or clause type — the fix "moved" some instances into KEEP but left siblings broken.
ADD fell sharply (415→171) partly because agents this iteration were pointed at specific regression
checks rather than open-ended "be generous" sweeps of dense procedural passages already covered
last time, and partly because several Iteration-1-flagged ADD opportunities are now folded into
corrected FIX triples (fuller clauses retained → less separately-addable content left over). Read
as a rate: Iteration 1 was ~48% FIX+DROP of 777; this pass is ~37% of 784 (253+36=289) — a real
quality improvement, but concentrated in DROP-elimination more than FIX-elimination.

### Per-chunk breakdown

| Chunk | Range | FIX | DROP | ADD | reviewed |
|---|---|---|---|---|---|
| 1 | S4–S559 | 27 | 5 | 26 | 61 |
| 2 | S560–S1187 | 22 | 7 | 26 | 61 |
| 3 | S1188–S1597 | 30 | 5 | 20 | 61 |
| 4 | S1601–S2087 | 29 | 1 | 13 | 61 |
| 5 | S2093–S2630 | 40 | 6 | 20 | 61 |
| 6 | S2635–S3154 | 39 | 5 | 21 | 61 |
| 7 | S3155–S3812 | 36 | 4 | 30 | 61 |
| 8 | S3816–S4340 | 30 | 3 | 15 | 60 |
| **Total** | | **253** | **36** | **171** | **487** |

---

## 2. Iteration 1 fix scorecard — did the landed fixes hold?

Checked two ways: (a) direct query of every sentence ID Iteration 1 named as a fix target or a
flagship example, (b) every regression the 4 auditors flagged in-chunk against the same failure
pattern.

| Fix | Verdict | Evidence |
|---|---|---|
| **N1** — copula/generic-noun clause retention | **PARTIAL, clean split by shape — the #1 remaining defect** | **Holds** for: plain `ADALAH + yang`-relative-clause directly on the object head (S213, S415, S6, S45, S1189/S1205/S1206 all clean); the "tirtha X ADALAH tirtha yang..." shape (S4077, S4086, S4126 — all fully retained even when unwieldy); the `berfungsi sebagai` parataxis-via-decomposition path in at least one case (S3647). **Does NOT hold** for: (a) **`MEMILIKI`/`MEMPEROLEH`/`TERDIRI_DARI`-headed generic nouns** — this is now the single largest recurring instance of the pattern, confirmed at S32, S61, S1138, S2256, S2258, S2377, S2483[1], S2502, S2555, S2563, S2624, S2872, S2969, S2954, S3091, S4087, and — critically — the **exact originally-flagged** S4106/S4111/S4128/S4170 ("MEMILIKI fungsi/hubungan + truncated head") are all **still broken**; (b) `bahwa`-ccomp clauses attached to the copula root rather than the object noun (S1429, S2055); (c) plain `acl:relcl` directly on the object head in many cases (S1456, S1461, S1483, S3155, S3446, S3544, **S3586** — the exact Iteration-1-flagged sentence, still broken, S3589, S3591, S3653, S3656, S3720, S3728, S3742, S3860, S3862, S4192, S4212, S4339); (d) `agar`-purpose clauses, as opposed to `untuk` (S1136); (e) a sibling `sehingga`-consequence clause hanging off the governing verb rather than embedded in the object NP (S4074, contrast fully-retained S4116/S4167/S4171); (f) recursive `object_decomposition` children — the top-level split works but a nested child still truncates (S2198[3]). |
| **N10** — transitive conjunct walk (3+ items) | **PARTIAL/MIXED — subject-side coordination is now the dominant gap** | **Holds** for flat, directly-governed, object-side "A, B, dan/serta C(+)" chains: S1361 (5-way), S1474 (4-way), S1523 (3-way), S3196 (15-way!), S4109 (4-way), S4103 (2-way), S2336 (3-way), S399 (3-way, the exact flag.txt sasih case for the *object* side). **Does NOT hold** for: (a) **subject-side coordinate/appositive NPs**, truncated to the first member almost everywhere the shape occurs — S1439 (7-way body-part list!), S1458, S1463, S1467, S1525, S1597, S1699, S1738 (3-way appositive), S2527, S2635, S2780, S2843, S2986, S3154 — this is the single most common remaining N10 miss, suggesting the walk only runs from the object/relation-argument side, never the subject-NP builder; (b) plain 2-item "X dan/atau Y" lists in relation types other than BERUPA/TERDIRI_DARI — still truncated very frequently, and this includes **flag.txt's own original S411/S413/S414 sasih-pair cases, still unfixed after two iterations** (S4, S332, S400, S788, S789, S1056, S1128, S1134, S1173, S2093, S2374, S2380, S2419, S2455, S2620, S2566, S3063, S3153, S3836, S3845, S4175 also affected); (c) colon/semicolon-introduced or "dan lain-lain" open enumerations — dropped almost entirely or **dumped as one garbled literal blob instead of being split** (S354 6-item list, only 1 survives; S344 ~14-item list dumped as one string; S1963[4] — walk actually *succeeds* in reaching all 4 members but then emits one garbled string instead of 4 relations, a distinct rendering bug; S3852[1] numeric example series truncated after 2 of 6); (d) lists introduced several dependency-hops below the main verb via "berupa X, Y, Z"/"sebagai X, Y dan Z" — dropped **wholesale**, not truncated (S4105/S4110 6-item, S4112 3-item, S4273 5-item, only the syntactically-closest member survives). |
| **S13** — attribution/citation suppression, widened | **INCONSISTENT — holds in some chunks, leaks in others on phrasings the fix's own spec names** | **Holds** in chunks 4/7/8 with no leaks found (S1639, S1732, S1782, S1899, S2527, S2555, and checked candidates in ch7/8). **Leaks** in chunks 1/2/3/5-6: S283 ("dalam lontar yama purva tattwa" — bare citation, no menurut/sebagaimana marker), **S972** (chunk 2 — "tertulis dalam beberapa lontar," the *exact phrase the widened fix's own description names* as a target), **S1226** (chunk 3 — "di mata umat hindu," also an exact named example), S1452 ("menurut lontar petunjuknya"), and **S2542** — the exact "sebagaimana halnya pangabenan" comparative Iteration 1 flagged as still-open, **confirmed still open**. Net: the pattern list covers `menurut X` and `sebagaimana ... disinggung/diuraikan ...` reliably but still misses bare `dalam lontar X` citations, `tertulis dalam` specifically, the `di mata X` idiom, and `sebagaimana halnya X` comparatives — a phrasing-coverage gap, not an absence of the mechanism. |
| **N6** — "termasuk" direction swap | **HOLDING on the original cases; a new narrower anchor bug found** | Both of Iteration 1's originally-flagged-and-fixed sentences, **S2748 and S2794, are confirmed fixed** — member as subject, category as object, correct direction. Two fresh test cases (S1493, S2065) show the **swap mechanism itself is correct** but the **category-anchor resolution** grabs the wrong noun — the nearest proper noun / an unrelated main clause subject — instead of the true "termasuk" antecedent. This is a distinct, narrower bug from the original direction-reversal N6 targeted. S2323[1] (chunk 5) shows a related but separate "termasuk" mislabeling that never enters the swap path at all. |
| **N11** — Panca Maha Bhuta manual overrides | **FULLY LANDED, clean** | S4300 (`ganda BERASAL_DARI/KEMBALI_KE pretiwi`), S4301 (`rasa BERASAL_DARI apah`, correctly **omitting** KEMBALI_KE since this sentence has no return-clause), S4303 (`rupa BERASAL_DARI/KEMBALI_KE teja`), S4304 (`ambekan BERASAL_DARI/KEMBALI_KE bayu`), S4305 (`sabda BERASAL_DARI/KEMBALI_KE akasa`) — all correct, complete, correctly asymmetric where the source text is. No errors found. One unrelated residual gap noted nearby: the parallel panca-datu table at S3756–S3758 is missing a `BERADA_DI` for the fifth element (logam campuran) — cosmetic, not an N11 defect (see ADD, chunk 7). |
| **N3** (still-open, unfixed) — benefactive/locative passive inversion | **Confirmed still fully open, now the clear #3 defect after N1/N10** | S2612, S2843, S2885 (partial), S2986, **S3080** (clearest case — the dependency parser itself mistags a locative "di samping jenazah" as `nsubj:pass`, and extraction inherits the parser's error verbatim), S2752 (transformation-direction variant). Spans chunks 5 and 6 broadly; not narrow to the 5-6 originally-cited sentences. |
| **N4** (still-open, unfixed) — `DIISI_DI` two-triple split | **Confirmed still fully open, unchanged** | S3747, S3749, S3753 (chunk 7) all still mis-type as `DIISI_DENGAN <body-part>` and drop the contents (kepeng-coin counts, flower types) entirely — exactly as flagged in Iteration 1, not re-triggered elsewhere in the corpus this pass. |
| **N5/N7/N8/N9** (still-open, unfixed) — span-hygiene batch | **Confirmed still present, plus one new related bug** | Bade/patulangan tier-shape stripping confirmed at S2055/S2056. Section-heading-as-subject confirmed at S3604/S3733/S3973 (manifestation varies — sometimes a junk clause is grabbed, sometimes the heading is just silently dropped and the sentence's real content goes unextracted, e.g. S3760). **New, distinct subject-fusion bug** found (not on the original N5/N8 list): a temporal-oblique's head noun gets fused into the subject compound, producing nonsense entities — "mendiang hidup" / "mendiang masa hidup" (S1738, S1823) and "pabersihan hidup tangan jenazah" (S3546). Different mechanism from N5 (which drops a qualifier) — this one *adds* a wrong one. |

---

## 3. New / re-ranked systemic defects for Iteration 3

Ranked by estimated leverage (triple count affected × how central the fix is).

### D1 (was N1, now split). Copula/generic-noun clause-stripping — the MEMILIKI/MEMPEROLEH/TERDIRI_DARI gap
The single largest recurring pattern this iteration. Iteration 1's fix generalized clause-retention
for `ADALAH`/`BERPERAN_SEBAGAI` but not for other identity/possession verbs governing the same
"generic noun + defining clause" shape. Confirmed broken at (partial list): S32, S61, S1138, S2256,
S2258, S2377, S2502, S2555, S2563, S2624, S2872, S2969, S2954, S3091, S4087, **S4106, S4111, S4128,
S4170** (the exact sentences Iteration 1's own "MEMILIKI fungsi/hubungan + truncated head"
sub-pattern named as its biggest chunk-8 miss). **Likely fix:** the clause-retention check needs to
trigger on the *shape* (generic-noun object + `yang`/`untuk`/`bahwa`/`agar`/appositive continuation)
independent of which governing verb (ADALAH/MEMILIKI/MEMPEROLEH/TERDIRI_DARI/BERARTI/MELAMBANGKAN)
sits on top — right now it looks hard-coded to the copula verbs only.

### D2 (was N1, sub-cases). Clause-attachment shapes N1 still misses even for ADALAH
`bahwa`-ccomp attached to the copula root rather than the object noun (S1429, S2055); `agar`-purpose
clauses (S1136, only `untuk` is covered); a sibling `sehingga`-consequence clause hanging off the
governing verb rather than embedded in the object NP (S4074 vs. working S4116/S4167/S4171); and
recursive `object_decomposition` children not inheriting the fix from their parent split (S2198[3]).

### D3 (was N10, re-split). Subject-side coordinate/appositive NP truncation
Now the dominant N10 gap — the transitive conjunct walk appears to run only from the object/relation
-argument side, never the subject-NP builder. Confirmed at S1439 (**7-way** body-part list reduced
to 1!), S1458, S1463, S1467, S1525, S1597, S1699 (3-way), S1738 (3-way appositive), S2527, S2635,
S2780, S2843, S2986, S3154. **Fix location:** wherever the subject NP is constructed/rendered
(likely a sibling function to the object-side conjunct walk that was never given the same
transitive-walk treatment).

### D4 (was N10, re-split). Plain 2-item "X dan/atau Y" truncation outside BERUPA/TERDIRI_DARI
Cheap, high-count, and includes flag.txt's own original S411/S413/S414 sasih pairs — **still broken
after two iterations**, a good regression-test anchor for whatever fix lands here. Also: S4, S332,
S400, S788, S789, S1056, S1128, S1134, S1173, S2093, S2374, S2380, S2419, S2455, S2620, S2566,
S3063, S3153, S3836, S3845, S4175.

### D5 (was N10, re-split). List-introducer shapes dropped wholesale
"berupa X, Y, Z" / "sebagai X, Y dan Z" several dependency-hops below the main verb lose the
**entire** list, not just members past the first: S4105/S4110 (6-item), S4112 (3-item), S4273
(5-item, only the syntactically-closest conjunct survives). Also colon/semicolon enumerations and
"dan lain-lain" open lists: S354 (6-item, 5 dropped), S344 (~14-item list dumped as one literal
string instead of split — **the single biggest information-loss instance found this iteration**),
S3852[1] (numeric series truncated after 2 of 6 values).

### D6 (new). "Successful walk, garbled single-string dump" artifact
Distinct from D3-D5: at S1963[4] the conjunct walk *does* reach all 4 members but then renders them
into one garbled literal string with duplicated tokens instead of 4 separate relations —
inconsistent even within the same sentence (siblings [0]-[2] in the same sentence emit correctly).
A rendering/emission bug, not a walk bug.

### D7 (was N3, still open). Benefactive/locative passive inversion
Confirmed still fully open and broad — S2612, S2843, S2885, S2986, S2752, and the clearest case
**S3080**, where the dependency parser itself mistags a locative oblique as `nsubj:pass` and the
extraction rule inherits that parser error verbatim (may need a parser-output sanity check, not just
a lemma-class rule, for this specific case). Now the clear #3 defect by volume after D1/D3.

### D8 (was N4, still open). `DIISI_DI <body-part>` two-triple split
Unchanged, still fully open: S3747, S3749, S3753. High information density (every coin/flower count
in the kawangen-placement passage is lost) despite low sentence count.

### D9 (was N5/N7/N8, still open + 1 new). Span-hygiene batch
Bade/patulangan qualifier stripping (S2055/S2056) and section-heading-as-subject (S3604/S3733/S3973)
both still present, inconsistent manifestation. **New sibling bug**: a temporal oblique's head noun
fuses into the subject compound — "mendiang hidup"/"mendiang masa hidup" (S1738, S1823),
"pabersihan hidup tangan jenazah" (S3546) — opposite failure from N5 (adds a wrong token rather than
dropping a right one); recommend fixing together since both are subject-span hygiene issues.

### D10 (was S13, phrasing gap). Attribution/citation suppression — specific missed phrasings
The mechanism works for `menurut X`/`sebagaimana ... disinggung/diuraikan ...` but still misses:
bare `dalam lontar X` (no menurut/sebagaimana marker) — S283; `tertulis dalam` specifically — S972
(the exact phrase the fix's own spec names); the `di mata X` idiom — S1226 (also a named example);
`sebagaimana halnya X` comparatives — S2542 (the exact sentence flagged as still-open in Iteration
1, confirmed still open). Cheap: add these four phrasings to the existing pattern list.

### D11 (was N6, narrower). "termasuk" category-anchor resolution
The subject/object swap direction is fixed and holding (S2748, S2794 confirmed). A narrower bug
remains: the category-anchor picks the nearest proper noun / an unrelated clause subject instead of
the true antecedent — S1493, S2065. Lower priority, narrow blast radius.

### D12 (new). Recurring "duplication" artifact in reconstructed spans
A noun appears twice verbatim in one object/subject string, as if double-substituted during span
reconstruction: S44 ("jenazah utuh...jenazah utuh"), S785 ("istilah umat hindu bagi umat hindu"),
S3004[1] ("ketulus-ikhlasan hati pihak" repeated). Recurs across three different chunks/relation
types — worth a dedicated look at whatever function stitches a head noun back together with a
trailing "bagi/untuk X" phrase that happens to repeat the same noun.

### D13 (new, but recurrence of flag.txt's #58b/c pattern). Wrong-subject via borrowed embedded-clause
The extractor keeps picking the *outer* clause's subject when the actual predicate belongs to an
*embedded* clause's own (different) subject — flag.txt's original nganyut/abu case, still recurring
fresh: S1187 (sesajen vs. abu jenazah), S1603 (lancingan kajang vs. jenazah), S1889 (pangabenan vs.
pabersihan), S3283, and S3080 (see D7 — same family, parser-level root cause there). Systemic enough
across four+ independent sentences that a general rule (rather than one-off overrides) is probably
warranted.

### D14 (new). Self-loop nonsense triples
Subject and object resolve to the same real-world entity (spelled two ways, or one glossing the
other): S3334 ("galar" / "bilah bambu" — apposition, not two things), S3733[1] ("kwangen jeriji" /
"kawangen jeriji" — spelling variants of the same word). Cheap final-filter fix: drop any triple
where subject and object normalize to the same string/entity.

### D15 (new, was implicitly present since Iteration 0). Undifferentiated giant-literal-object dump
The opposite failure of terseness: `object_decomposition` occasionally gives up and returns the
entire remaining sentence as one 40+-word literal object instead of splitting it into atomic
triples: S2604, S3001, S4090 (with an internal garbled duplicate on top). Same underlying mechanism
as D6 (S1963[4]) — recommend investigating together.

### D16 (unchanged). Massive procedural under-extraction — ADD-appetite decision, not a bug
Body-prep and ritual-tool-assembly passages (S3122, S3141, S3142, S3153, S3154, S3604, S3734,
S3760, S3973, S4035/S4273) still carry far more recoverable triples than the rules pull. ADD count
is down overall (171 vs 415) but still concentrated here — same open question as Iteration 1's N12,
still needs the user's call on how far to push procedural coverage.

---

## 4. Recommended resolution path for Iteration 3

1. **D1 first** — generalize N1's clause-retention check to be verb-class-independent (MEMILIKI/
   MEMPEROLEH/TERDIRI_DARI/BERARTI/MELAMBANGKAN, not just ADALAH/BERPERAN_SEBAGAI). Highest
   leverage — this single gap now spans every chunk and includes the exact sentences Iteration 1
   named as its top priority.
2. **D2** — extend clause-attachment coverage to `bahwa`-ccomp, `agar`-purpose, sibling
   `sehingga`-consequence clauses, and make the fix recurse into nested `object_decomposition`
   children.
3. **D3** — give subject-side coordinate/appositive NPs the same transitive conjunct walk the
   object side already has. Highest-count single fix available (recovers the 7-way S1439 list alone,
   plus a dozen+ 2-3-way subject lists across every chunk).
4. **D4** — extend the walk (or add a lightweight fallback) to plain 2-item "X dan/atau Y" pairs
   outside BERUPA/TERDIRI_DARI relations. Cheap; use flag.txt's own S411/S413/S414 as the regression
   anchor since they're still broken after two iterations.
5. **D5 + D6 + D15 together** — these three all trace to the same area (how a coordinate/list
   object is detected and rendered): fix the wholesale-drop on deep "berupa/sebagai X,Y,Z"
   introducers, the garbled-single-string-dump artifact, and the giant-literal-object fallback in
   one pass, since they likely share a root cause in the decomposition/rendering step.
6. **D7 (N3)** — implement the lemma-class subject/object swap for benefactive passives, as already
   scoped in Iteration 1's own resolution path (§1 step 2: plumb `subject_label` into
   `derive_raw_relation_label`). For S3080 specifically, consider a targeted check for the parser's
   locative-mistagged-as-nsubj:pass error rather than trusting the dependency label at face value.
7. **D8 (N4)** — implement the two-triple split, as already scoped in Iteration 1.
8. **D9** — span-hygiene batch: bade/patulangan qualifier stripping, section-heading-as-subject, and
   the new temporal-oblique-fusion bug, together (all are "trim/gate the raw span" fixes).
9. **D10 (S13)** — cheap, add the four missed phrasings (`dalam lontar X`, `tertulis dalam`,
   `di mata X`, `sebagaimana halnya X`) to the existing attribution pattern list.
10. **D13** — investigate whether the wrong-subject-via-borrowed-embedded-clause bug (4+ independent
    recurrences now) can be fixed generally rather than continuing to patch one sentence at a time.
11. **D14** — cheap final-filter: drop self-loop triples (subject == object after normalization).
12. **D11 (N6 anchor)**, **D12 (duplication artifact)** — narrow, lower priority, fix opportunistically.
13. **D16 / N12 ADD appetite** — still needs your call; unchanged recommendation from Iteration 1
    ("accept ADDs that name a ritual entity/sarana or symbolic meaning; defer pure step-by-step
    procedure capture unless full procedural coverage is wanted").
14. Small housekeeping ADD alongside any of the above: S3756-S3758's missing `logam campuran
    BERADA_DI` entry (cosmetic, one-line fix to the existing manual override).
15. **Re-run the notebook** (you run it) → regenerate `Results/Final/` → propagate any new predicate
    vocabulary to `Neo4/normalize.py` + `kb/relation_phrases.json` per
    [[project_neo4j_graph_cleanup]] / [[project_ngaben_chatbot_kb]].

**Suggested review order for §5** (per-chunk detail below): skim each chunk's **DROP** list first
(fastest agreement, and much shorter than last time), then the **FIX** items that map to D1-D16
above (systemic, will be batch-fixed), then decide the **ADD** appetite for D16-class procedural
sentences.

---

## 5. Per-chunk findings (full detail)

Each chunk below lists every FIX (current → corrected triple + reason), DROP (+ reason), ADD
(+ source phrase) and NOTE for its sentences, exactly as returned by the auditing sub-agent for
that chunk.

# Chunk 1 audit (S4..S559)

## FIX  (triple is salvageable — give the corrected triple)

- **S4 [0]**  current: `ngaben | MELAMBANGKAN | siklus kehidupan`
  fix: `ngaben | MELAMBANGKAN | siklus kehidupan dan kematian`
  why: "siklus kehidupan **dan kematian**" (cycle of life **and death**) — the second conjunct is dropped, a 2-item coordinate loss identical in spirit to the flagged sasih cases.

- **S12 [0]**  current: `ngaben | MEMILIKI | sudut pandang pemaknaan`
  fix: `ngaben | MEMILIKI | beberapa sudut pandang pemaknaan`
  why: drops "beberapa" (several) — same "beberapa jenis" nuance-loss pattern as flag.txt S801.

- **S26 [0]**  current: `apah | MELAMBANGKAN | unsur cair`
  fix: `apah | MELAMBANGKAN | unsur cair dalam tubuh`
  why: drops "dalam tubuh" (in the body); inconsistent with the sibling sentence S29 (akasa), which keeps the equivalent "tubuh" qualifier.

- **S32 [0]**  current: `ngaben | MEMILIKI | peran ganda`
  fix: `ngaben | MEMILIKI | peran ganda yang saling menguatkan`
  why: **D1 gap** — MEMILIKI + generic noun "peran ganda" (dual role) drops its defining "yang saling menguatkan" (that mutually reinforce) relative clause. N1 holds for ADALAH+yang but not for MEMILIKI+yang here.

- **S44 [0]**  current: `sawa wedana | ADALAH | upacara jenazah utuh untuk jenazah utuh (3-7 hari setelah meninggal)`
  fix: `sawa wedana | ADALAH | upacara untuk jenazah utuh (3-7 hari setelah meninggal)`
  why: "jenazah utuh" is duplicated verbatim in the object string — an extraction bug (D12, same duplication pattern recurs at chunk-2 S785).

- **S48 [0]**  current: `ngaben massal | ADALAH | pelaksanaan kolektif`
  fix: `ngaben massal | ADALAH | pelaksanaan kolektif oleh warga desa untuk efisiensi biaya dan tenaga tanpa mengurangi nilai sakralitasnya`
  why: **D2 gap** — the purpose-oblique ("untuk efisiensi biaya dan tenaga") and agent-oblique ("oleh warga desa") children of the generic noun "pelaksanaan kolektif" are entirely dropped, despite N1's widened rule explicitly naming purpose-oblique children as something to retain.

- **S58 [3]**  current: `nganyut | MELAMBANGKAN | simbol pelepasan terakhir`
  fix: `nganyut | MELAMBANGKAN | simbol pelepasan terakhir menuju moksha`
  why: drops "menuju moksha" (toward moksha/liberation), the destination that gives the symbol its meaning.

- **S61 [0]**  current: `mapegat | MEMILIKI | makna krusial`
  fix: `mapegat | MEMILIKI | makna krusial untuk memutus ikatan emosional dan duniawi antara mendiang (niskala) dengan keluarga (skala)`
  why: **D1 gap** — MEMILIKI + "makna krusial" drops its entire purpose-xcomp ("untuk memutus ikatan...") even though purpose-oblique/xcomp retention is explicitly part of the widened N1 spec.

- **S77 [0]**  current: `naga banda | MEMILIKI | panjang 1.600 depa`
  fix: `naga banda | MEMILIKI | panjang 1.600 depa (sekitar 2,4 km)`
  why: drops the clarifying metric conversion "(sekitar 2,4 km)".

- **S92 [0]**  current: `kanoroyang sanksi terberat | BERUPA | pemberhentian keanggotaan desa adat`
  fix: `kanoroyang | ADALAH | sanksi terberat berupa pemberhentian keanggotaan desa adat`
  why: subject wrongly merges "kanoroyang" with its own predicate noun "sanksi terberat"; cleaner to keep "kanoroyang" as subject with the descriptive complement intact as object.

- **S104 [0]**  current: `bali aga vs bali dataran | MEMPEROLEH | perbedaan mendasar`
  fix: DROP this triple (see DROP list) and replace with two ADD triples (see ADD list)
  why: "MEMPEROLEH" (obtained) does not fit the source verb "terdapat" (there exists/there is); the heading-style subject "bali aga vs bali dataran" is not a real acting entity. Wrong relation label + wrong subject.

- **S124 [0]**  current: `bali dataran | MENGGUNAKAN | sarana mewah`
  fix: `bali dataran | MENGGUNAKAN | sarana mewah (bade/petulangan) pengaruh majapahit`
  why: drops "pengaruh majapahit" (Majapahit-influenced), the qualifier explaining why these tools are "mewah" (luxurious).

- **S126 [0]**  current: `ngaben | ADALAH | institusi sosial-religius`
  fix: `ngaben | ADALAH | institusi sosial-religius yang kompleks`
  why: drops "yang kompleks" (that is complex). See ADD list for the much bigger companion miss (the "berfungsi sebagai..." parataxis clause).

- **S128 [0]**  current: `ngaben | ADALAH | identitas budaya dinamis`
  fix: `ngaben | ADALAH | identitas budaya dinamis yang terus menjaga harmoni antara manusia, alam, dan sang pencipta`
  why: **D2 gap** — drops the entire "yang terus menjaga harmoni..." relative clause, which itself contains a 3-item list (manusia, alam, dan sang pencipta).

- **S191 [0]**  current: `jenazah | DIKUBUR_DENGAN | kehendak lain`
  fix: `jenazah | DIKUBUR_SEMENTARA_KARENA | keterbatasan dana (keputusan keluarga)`
  why: "kehendak lain" (other will/wish) alone is nonsense as something one is "buried with"; the real content is that the corpse is buried *temporarily* due to a family decision driven by limited funds. Flag.txt asked whether to drop this one — recommend FIX instead, it's salvageable.

- **S219 [0]**  current: `sekar ura | MELAMBANGKAN | simbol perpisahan`
  fix: `sekar ura | MELAMBANGKAN | simbol perpisahan antara yang meninggal dengan keluarga yang ditinggal`
  why: adds back the "antara..." qualifier that gives the symbol its meaning; the outer "dengan harapan..." tail can reasonably stay dropped (too deep to be useful).

- **S246 [0]**  current: `puspa lingga | DIAMBIL | keampigan`
  fix: `puspa lingga | DIBUKA_MENJADI | keampigan`
  why: source verb is "dibuka" (opened/uncovered), not "diambil" (taken) — wrong relation label.

- **S254 [0]**  current: `kuburan | DIAMBIL | tulang belulang`
  fix: `tulang belulang | DIAMBIL_DARI | kuburan`
  why: wrong direction — the bones are taken *from* the grave, the grave does not "take" the bones.

- **S258 [2]**  current: `tegteg | DISERTAI | memohon`
  fix: `tegteg | DISERTAI | permohonan atma yang akan diaben`
  why: object is a bare verb stem "memohon" (to request) with no content — nonsense triple; the real request-object is "atma yang akan diaben" (the soul to be cremated).

- **S271 [4]**  current: `atiwa-tiwa | ADALAH | sama atiwa-tiwa asti vedana`
  fix: `tata pelaksanaan atiwa-tiwa (ngaben) svasta | SAMA_DENGAN | atiwa-tiwa asti vedana`
  why: object squashes "sama dengan" (same as) into the noun phrase, and the real subject of the comparison is "tata pelaksanaannya" (its procedure), not bare "atiwa-tiwa".

- **S283 [0]**  current: `banten | DIKENAL_SEBAGAI | kala puspa`
  fix: `banten yang menjadi simbol orang yang meninggal | DIKENAL_SEBAGAI | kala puspa`
  why: matches flag.txt's 283c point — only the specific offering that "menjadi simbol orang yang meninggal" is called kala puspa, not "banten" in general.

- **S332 [0]**  current: `jenazah | DILETAKKAN_DI | balai posisi kepala berhulu utara`
  fix: `jenazah | DILETAKKAN_DI | balai dengan posisi kepala berhulu utara atau timur`
  why: drops the "atau timur" (or east) disjunct — a missing coordinate member (D4, 2-item list, only first kept).

- **S366 [0]**  current: `jenazah | MENUJU | utara`
  fix: `jenazah | MEMBUJUR_KE | utara atau timur`
  why: matches flag.txt exactly (still unfixed) — "membujur" means the corpse lies oriented/stretched toward a direction (static posture), not "menuju" (heading toward, implying motion); also restores the dropped "atau timur" disjunct.

- **S370 [2]**  current: `jenazah | DIPASANG | itik-itik`
  fix: `itik-itik | DIPASANG_PADA | ibu jari tangan dan kaki jenazah`
  why: matches flag.txt 370c — it's the itik-itik that get affixed to the thumb/big toe, not a generic "jenazah gets itik-itik" action.

- **S399**  current (all of [0]-[2]): `sasih | ADALAH | kasa / karo / katiga`
  fix: `sasih yang baik untuk pitra yadnya (khususnya ngaben) | ADALAH | kasa, karo, dan katiga`
  why: matches flag.txt exactly, still unfixed — subject "sasih" needs the "yang baik..." qualifier. Note: the 3-item coordinate object list itself IS fully preserved — good N10 evidence — only the subject-side qualifier is still missing.

- **S540 [0]**  current: `banten | DIPERSEMBAHKAN_KEPADA | sakabuatan`
  fix: `banten saji | BERJENIS | sakabuatan`
  why: "sakabuatan" (a complete/full set) describes the offering's composition, not a recipient.

- **S559 [0]**  current: `sorohan banten | LAINNYA | ajeng sulinggih`
  fix: `sorohan banten | DIPERSEMBAHKAN_DI_HADAPAN | sulinggih`
  why: matches flag.txt exactly, still unfixed — "ring ajeng sulinggih" = "in front of/in the presence of the high priest (sulinggih)".

## DROP  (triple should be removed)

- **S104 [0]**  `bali aga vs bali dataran | MEMPEROLEH | perbedaan mendasar`
  why: nonsensical heading-triple; "terdapat" (there exists) isn't an "acquire" relation, and "bali aga vs bali dataran" isn't a real acting subject. Replaced by two ADD triples below.

- **S224 [0]**  `usungan | MEMILIKI | upacara pembasmian`
  why: reaffirming flag.txt's verdict (still unfixed) — the bier (usungan) does not "own" the cremation ceremony; the ceremony is held *after* the bier is set down.

- **S283 [1]**  `banten | DIKENAL_SEBAGAI | lontar`
  why: **D10 gap** — "lontar" here refers to the *source text*, a citation adjunct, not an alias of banten. This is precisely the pattern the widened S13 rule is meant to suppress, and it still leaked through.

- **S370 [3]**  `jenazah | DILETAKKAN_DI | ibu jari tangan`
  why: nonsensical — "ibu jari tangan dan kaki" is where the itik-itik are placed, not a location the corpse itself is placed at.

- **S541 [0]**  `banten panjang ilang | LAINNYA | rateng`
  why: reaffirming flag.txt's verdict (still unfixed) — segmentation-mangled fragment.

## ADD  (missing triples the sentence supports)

- **S44**  `formalin | DIGUNAKAN_UNTUK | memperlambat pembusukan jenazah selama masa persiapan`
- **S46**  `swasta | MENGGUNAKAN | kayu cendana dan aksara sakral`  (+ `kayu cendana dan aksara sakral | MELAMBANGKAN | pengganti jasad`)
- **S69**  `gedarba | DIGUNAKAN_OLEH | wangsa sudra jadma (masyarakat umum)` — matches flag.txt 69b exactly, still missing.
- **S81**  `perbandingan kepala lembu | ADALAH | 2:1:1` — matches flag.txt exactly, still missing.
- **S104**  `masyarakat bali aga (pegunungan) | MEMPERTAHANKAN | tradisi asli kuno`  (+ `masyarakat bali dataran | MENDAPAT_PENGARUH_DARI | tradisi hindu-majapahit`)
- **S124**  `bali aga | MENONJOLKAN | tradisi asli (yang terkadang tidak menggunakan pembakaran fisik secara masif)`
- **S126**  `ngaben | BERFUNGSI_SEBAGAI | mekanisme spiritual pemurnian jiwa sekaligus perekat kohesi sosial` — **major D1/parataxis gap**, 0 triples for this clause.
- **S215**  `layon | DILETAKKAN_DI | bale gede`  (+ `layon | DILETAKKAN_DI | saka roras`)
- **S217**  `pelebon | DIAWALI_DENGAN | upacara ngaskara`  (+ `pelebon | DIAWALI_DENGAN | caru pengelambuk`, + `jenazah | BERANGKAT_KE | setra`)
- **S246**  `ngerorasin | DILAKSANAKAN_DI | pura dalem` — exactly flag.txt's suggested triple, still missing.
- **S265**  `tegteg | DITEMPATKAN_DI | tumpang salu`
- **S270**  `ngaben svasta | DILAKUKAN_JIKA | jenazah tidak ditemukan`  (+ `... | jenazah telah lama terkubur/terpendam`, + `... | lokasi jenazah terlalu jauh dari jangkauan`)
- **S271**  `tata pelaksanaan atiwa-tiwa svasta | MELIPUTI | matur piuning, pembakaran, hingga nganyut, dan ngelinggihang dewa hyang`
- **S338**  `soda | BERUPA | nasi, minum, buah-buahan, jajan, dan lainnya` — **major D5 test case, total miss** (0 triples).
- **S344**  itemize `eteh-eteh sawa | BERUPA | <item>` for each of: kamben, tapih, sabuk, udeng, pangulungan, angkeb rai, angkeb baga/purus, leluwur, tatindih, kain kuning untuk saput atau selendang, rantasan kain putih kuning dan kain anyar, samsam, bunga, kwangen  (+ `eteh-eteh sawa | DIMOHONKAN_DARI | sulinggih/griya`) — **the single biggest D5 finding in this chunk**, ~14 items dumped verbatim as one string.
- **S354**  `pepaga | TERBUAT_DARI (hitungan) | wangke`  (+ `... | wangkong`, `... | galar`, `... | galir`, `... | galur`) — 6-item conjunct chain, only 1 survived.
- **S358**  `leluwur | BERUPA | kain putih` — exactly the triple flag.txt asked for, still missing.
- **S364**  `nanginin | ADALAH | upacara membangunkan almarhum seperti membangunkan orang yang sedang tidur`  (+ `nanginin | DISERTAI | kekidungan yang berhubungan dengan kidung pitra yadnya`)
- **S370**  `jenazah | DITEMPATKAN_DI | bale gede/sakaroras atau tempat yang disiapkan`  (+ `jenazah | DIPOSISIKAN_KEPALA_KE | utara atau timur`)
- **S376**  `jenazah | DIBASMI_OLEH | sang hyang birawi`
- **S400**  `sasih kapitu | DIKENAL_SEBAGAI | dewasa madya` — 2-item coordinate subject, only "kaenem" kept.
- **S411**  `wuku kuningan | BERADA_DI | sasih kapitu` — matches flag.txt exactly, STILL unfixed.
- **S413**  `uye | BERADA_DI | sasih kasanga` — matches flag.txt exactly, STILL unfixed.
- **S414**  `wayang | BERADA_DI | sasih kadasa` — matches flag.txt exactly, STILL unfixed.

## NOTE

- **D1 (N1) regression check** — holds for plain "X ADALAH/BERPERAN_SEBAGAI generic-noun yang-clause" (S6, S45, S73, S213, S415, S4[1]). Gaps: MEMILIKI+yang-clause (S32), MEMILIKI+purpose-xcomp (S61), ADALAH+purpose/agent-oblique (S48), and bare parataxis clauses ("berfungsi sebagai...", S126; "digunakan oleh...", S69) dropped entirely rather than truncated.
- **D3/D4 (N10) regression check** — holds for flat "A, B, dan/serta C(+)" chains (S27/S28, S219, S399). Fails for colon-introduced enumerations (S354), semicolon-segmented dumps (S344, biggest miss), and plain 2-item "X dan Y" objects/subjects in non-BERUPA relations (S4, S332, S400, and all three flag.txt-flagged S411/S413/S414 sasih pairs).
- **D10 (S13) regression check** — S283[1] leaks the citation adjunct through, exactly the pattern the widened rule targets.
- **N6 regression check** — no test case in chunk 1 (zero "termasuk" occurrences).
- **D13** — flag.txt 58b/58c (nganyut/abu subject bug) remains unaddressed; same bug class recurs at chunk-2 S1187.
- **S540 vs S591 cross-chunk duplicate** — same sentence, inconsistent verdicts (S540→FIX here, S591→DROP in chunk 2 per flag.txt). Recommend picking one consistent treatment.
- **D12 duplication bug** — S44's object repeats "jenazah utuh"; recurs at chunk-2 S785.

## Chunk stats
FIX: 27   DROP: 5   ADD: 26   sentences reviewed: 61

---

# Chunk 2 audit (S560..S1187)

## FIX  (triple is salvageable — give the corrected triple)

- **S560 [0]**  current: `banten pejati saha banten peras gede | LAINNYA | asoroh`
  fix: `banten pejati, peras gede, dan suci | ADALAH | asoroh (satu set lengkap)`
  why: "asoroh" = "a complete set"; the three offering types together make up one asoroh.

- **S616 (all of [0]-[3])**  current: `banten nuwur pakuluh | LAINNYA | merajan / paibon / panti / kawitan`
  fix: `banten nuwur pakuluh | DIPERSEMBAHKAN_DI | merajan / paibon / panti / kawitan`
  why: matches flag.txt exactly ("ring = put at/offered to") — STILL unfixed, still generic LAINNYA. Positive: the 4-item location list itself is fully preserved.

- **S618 [1]**  current: `banten | DIPERSEMBAHKAN_KEPADA | merajapati`
  fix: `banten atur piuning | DIPERSEMBAHKAN_DI | merajapati`
- **S618 [2]**  current: `banten | DIPERSEMBAHKAN_KEPADA | panghulunin setra`
  fix: `banten atur piuning | DIPERSEMBAHKAN_DI | panghulunin setra`
  why: matches flag.txt exactly ("supposed to be 'banten atur piuning'") — subject still bare "banten", still unfixed.

- **S738 [0]**  (retain as-is: `puspa asti | ADALAH | abu`) — see ADD for the missing relative-clause content flag.txt asked for.

- **S780 [0]**  current: `puspa asti | DILETAKKAN_DI | balai selunglung`
  keep, but see ADD below for the missing "atau dipangku oleh keluarga" disjunct.

- **S785 [0]**  current: `pitra yadnya | ADALAH | istilah umat hindu bagi umat hindu di sini`
  fix: `pitra yadnya | ADALAH | istilah bagi umat hindu di sini`
  why: duplicates "umat hindu" — same D12 duplication bug seen at chunk-1 S44.

- **S792 [0]**  current: `pitra yadnya | BERARTI | pengorbanan , terutama kepada orangtua`
  fix: `pitra yadnya | BERARTI | pengorbanan yang dilandasi hati yang tulus suci kepada leluhur, terutama kepada orangtua`
  why: matches flag.txt exactly ("a bit too terse") — the object string is literally broken (dangling comma), dropping the entire relative clause. **D1 gap** for BERARTI+relative-clause.

- **S801 [0]**  current: `pitra yadnya | TERDIRI_DARI | jenis`
  fix: `pitra yadnya | TERDIRI_DARI | beberapa jenis (yang pelaksanaannya ber-bhinneka)`
  why: matches flag.txt exactly — STILL missing the "beberapa" qualifier.

- **S906 [0]**  current: `jabang bayi | MENINGGAL | kandungan`
  fix: `jabang bayi | MENINGGAL_DI | kandungan`
  why: drops the "dalam" (in) preposition. See ADD below for the much bigger missing content flag.txt asked about.

- **S923 [0]**  current: `jenazah momong | DISERTAI | peti samping`
  fix: split into `jenazah | DIMOMONG_KE | kuburan` and `jenazah | DISERTAI | peti`
  why: matches flag.txt exactly, still unfixed — subject wrongly absorbs the verb "momong" and object wrongly absorbs "samping".

- **S961 [3]**  current: `sawa | BERASAL_DARI | hulu kaki`
  fix: `sawa | DIIKAT_DARI | hulu ke kaki`
  why: matches flag.txt exactly ("961d") — STILL unfixed.

- **S1016 [0]**  current: `ngaben | BERTUJUAN | niskala`
  fix: `ngaben | BERTUJUAN_UNTUK | memusnahkan segenap jasad sawa sehalus-halusnya`
  why: wrong object — "secara niskala" is a manner-adverbial, not the goal itself.

- **S1017 [0]**  current: `mahabutha | DITUJUKAN_UNTUK | induk asal`
  fix: `mahabutha | KEMBALI_KE | induk asal (masing-masing)`
  why: "kembali kepada" = "returns to", not "ditujukan untuk".

- **S1056 [0]**  current: `pepaga | BERFUNGSI_SEBAGAI | balai-balai alas memandikan jenazah`
  fix: `pepaga | BERFUNGSI_SEBAGAI | balai-balai alas memandikan jenazah dan ngringkes`
  why: **D4 gap** — drops the "dan ngringkes" second conjunct.

- **S1060 [0]**  current: `jenazah | BERASAL_DARI | rumah adat`
  fix: `jenazah | DIPINDAHKAN_DARI | rumah adat (ke pepaga)`
  why: "dipindahkan dari X ke Y" is a directional-move relation, not "berasal dari".

- **S1082 [1]**  current: `jenazah | DIPERSEMBAHKAN_KEPADA | sajen kecil`
  fix: `jenazah | DISUGUHI | sajen kecil`
  why: "disuguhi X" means jenazah is the recipient; DIPERSEMBAHKAN_KEPADA reverses the direction.

- **S1122 [0]**  current: `nyekeh | BERARTI | jenazah`
  fix: `nyekeh | BERARTI | jenazah dibaringkan di rumah adat dalam jangka waktu agak lama hingga tiba hari H untuk ngaben sesuai dewasa yang dipilih`
  why: **severe D1-adjacent gap** — object truncated to a circular bare noun. Shows the same failure mode also affects BERARTI, which isn't covered by the named N1 fix.

- **S1128 [0]**  current: `nyekeh sawa | DILAKUKAN_OLEH | keluarga raja`
  fix: `nyekeh sawa | DILAKUKAN_OLEH | keluarga raja atau pendeta`
  why: drops "atau pendeta" — 2-item list, second item missing.

- **S1128 [1]**  current: `nyekeh sawa | BERASAL_DARI | masyarakat`
  fix: `keluarga raja atau pendeta | BERASAL_DARI | golongan masyarakat yang mampu melakukan upacara ini`
  why: wrong subject + garbled causal reasoning.

- **S1173 [1]**  current: `ngaben | MEMUPUK | rasa kekeluargaan`
  fix: `ngaben | MEMUPUK | rasa kekeluargaan dan kebersamaan`
  why: drops "dan kebersamaan".

- **S1187 [0]**  current: `sesajen | DIHANYUTKAN_KE | samudera`
  fix: `abu jenazah | DIHANYUTKAN_KE | samudera`
  why: **same wrong-subject bug as flag.txt S58b/c (D13)**, recurring fresh.

## DROP  (triple should be removed)

- **S618 [0]**  `banten | DIPERSEMBAHKAN_KEPADA | piuning`
  why: "piuning" is not a recipient/location — part of the banten's own designation.

- **S591 [0]**  `banten | DIPERSEMBAHKAN_KEPADA | sakabuatan`
  why: reaffirming flag.txt's verdict (still unfixed). Cross-chunk duplicate of chunk-1 S540 (there recommended FIX) — see NOTE.

- **S631 [0]**  `banten panebusan | LAINNYA | rateng saha salaran sejangkep`
  why: segmentation-mangled, same pattern as flag.txt's S541 (chunk 1).

- **S641 [1]**  `surya | ADALAH | banten pejati saha suci asoroh`
  why: matches flag.txt exactly ("641b") — STILL unfixed. The offerings are *for* Surya, not identical to Surya.

- **S679 [0]** and **[1]**  `banten | DIPERSEMBAHKAN_KEPADA | asele` / `asele | ADALAH | jauman`
  why: reaffirming flag.txt's verdict ("679a: drop this") — STILL unfixed.

- **S809 [1]**  `pitra yadnya | ADALAH | rupa`
  why: matches flag.txt exactly ("809b") — STILL unfixed. POS-tagging error ("rupanya" = adverb, not noun).

- **S925 [1]**  `jenazah | DIMASUKKAN_KE_DALAM | kuburan upakara apa`
  why: matches flag.txt exactly ("925b") — STILL unfixed, and reverses the sentence's meaning by ignoring the negation "tanpa".

## ADD  (missing triples the sentence supports)

- **S618**  `banten atur piuning | DIPERSEMBAHKAN_DI | dalem`
- **S641**  `banten munggah ring surya | DIPERSEMBAHKAN_KEPADA | surya` — matches flag.txt exactly ("641a").
- **S738**  `puspa asti | DIAMBIL_DENGAN | sumpit/sepit`  (+ `puspa asti | DIHANCURKAN_DI | sesenden`) — matches flag.txt exactly, STILL missing.
- **S780**  `puspa asti | DIPANGKU_OLEH | salah seorang keluarga`  (+ `persembahyangan (ini) | DIPIMPIN_OLEH | sulinggih`)
- **S788**  `dua kata | ADALAH | yadnya` — 2-item list, only "pitra" survived.
- **S789**  `orangtua | ADALAH | ibu` — 2-item list, only "ayah" survived.
- **S809**  `pitra yadnya (dataran rendah) | DISEMPURNAKAN_OLEH | empu kuturan`  (+ `... | dang hyang dwijendra`, `... | empu lutuk`)
- **S851**  `manusia | BERHUTANG_PADA | pancamahabutha` — matches flag.txt exactly, STILL missing.
- **S898**  `ida bhatara kumara | MENGASUH | bayi` — matches flag.txt exactly, STILL missing.
- **S906**  `ari-ari (placenta) | DIBIARKAN_MENUNGGAL_DENGAN | jasad sang bayi`
- **S957**  `jenazah bayi | DIMANDIKAN_DI_ATAS | dusa (balai-balai khusus pemandian jenazah)`
- **S967**  `penyelesaian sawa dewasa | DISESUAIKAN_DENGAN | ketentuan dewasa ayu atau hari baik`
- **S970 (positive note)**  flag.txt's flagged bad triple is **gone** — replaced by sensible `tirtha DIMOHON_DARI sulinggih`. Resolved.
- **S974**  optional: `sesaji sederhana | DISUGUHKAN_SEBELUM | abu dihanyutkan`
- **S978**  `tirtha (ini) | DIPERCIKKAN_MENJELANG | penguburan atau pembakaran sawa`
- **S1016**  `jasad sawa (wujud) | BERUBAH_MENJADI | unsur, elemen, atau mahabutha`
- **S1024**  `upacara (ini) | DIIRINGI_TUJUAN | permohonan kepada tuhan (yang maha pengampun)`
- **S1040**  `tikar (alas jenazah) | DITARIK | (dari bawah sawa)`
- **S1058**  `secarik kain putih | DISEBUT | leluhur (atau langit-langit tandu)`
- **S1060**  `kain penutup (jenazah) | DIBUKA | (setelah dipindahkan ke pepaga)`
- **S1066**  `sesisir pisang | MELAMBANGKAN | kalang bahu`
- **S1123**  `jenazah (disebut masekeh) | BERSYARAT | berada minimal satu bulan, dilewati bulan purnama dan tilem, serta upacaranya memenuhi syarat`
- **S1134**  `punjung | DIPERSEMBAHKAN_KEPADA | mendiang` — 2-item coordinate subject, only "sesajen" survived.
- **S1136**  `damar kurung | BERTUJUAN_AGAR | keletehan (sawa mendiang) diblokir terbatas (hanya sebatas tanah pekarangan keluarga)` — **D2 gap for "agar"-purpose clauses**.
- **S1138**  fix `mendiang | MEMPEROLEH | ayaban upakara diuskamaligi` → `... yang bermakna penyucian`  (+ ADD `ayaban upakara diuskamaligi | BERTUJUAN_AGAR | leteh sawa tidak memancar ke luar dan tidak menghimbasi yang lain`)
- **S1160**  `patus | ADALAH | bantuan gratis (dari komunitas/krama)`
- **S1169**  fix `sawa | DIBAKAR_DENGAN | status` → `sawa | DITANAM_ATAU_DIBAKAR_SEMENTARA | status dititip (menunggu biaya untuk ngaben)`  (+ ADD `sawa (berstatus dititip) | MENUNGGU | rezeki untuk menggelar upacara ngaben beberapa bulan/tahun kemudian`)
- **S1187**  `sesajen (ini) | DIHATURKAN_PADA_SAAT | abu jenazah dihanyutkan ke samudera`

## NOTE

- **D1 (N1) regression check** — good positive evidence: S797, S1163 (long ADALAH clauses, internal coordination intact), S958. Gaps: MEMPEROLEH+yang-clause (S1138, mirrors chunk-1 S32's MEMILIKI pattern), BERARTI+xcomp dropped to a bare meaningless noun (S1122), BERARTI+relative-clause mangled (S792), ADALAH+"agar"-purpose clause dropped (S1136).
- **D3/D4 (N10) regression check** — leaning NOT HOLDING for the common 2-item case: S788, S789, S1056, S1128, S1134, S1173. Positive counter-evidence: S974, S616 (full 4-item list, just wrong label).
- **D10 (S13) regression check** — S972[1] leaks "sebagaimana tertulis dalam beberapa lontar" through — the exact phrase the widened rule's own spec names.
- **N6 regression check** — S851's "termasuk" is the adverbial "including" sense, not the membership pattern; no genuine test case in chunks 1-2.
- **D13 cross-chunk recurrence** — S1187 is the same bug class as flag.txt's S58b/c, a fresh previously-unflagged instance.
- **S591 vs S540** — same underlying sentence, inconsistent verdicts; pick one.
- **D12 duplication bug** — S785 repeats "umat hindu" verbatim, same pattern as chunk-1 S44.

## Chunk stats
FIX: 22   DROP: 7   ADD: 26   sentences reviewed: 61

---

# Chunk 3 audit (S1188..S1597)

## FIX  (triple is salvageable — give the corrected triple)

- **S1197 [1]**  current: `jun pere | BERISI | gambar`
  fix: `jun pere | BERISI | gambar yang khas`

- **S1219 [0]**  current: `sawa | DIBAKAR | alat pangringkesan`
  fix: `sawa | DISERTAI | alat pangringkesan` (and add `sawa | DITANAM | alat pangringkesan`)
  why: "beserta" = "together with" — wrong relation label.

- **S1226 [0]**  current: `sawa | DINILAI_DI | mata umat hindu`
  fix: `sawa | DINILAI | sesuatu yang leteh atau tidak suci`
  why: "di mata umat hindu" is an attribution adjunct — exactly the D10/S13 pattern; leaked through.

- **S1253 [0]/[1]**  current: `ngaben bahasa alus-singgih | ADALAH | malebuang / atiwa-tiwa`
  fix: `ngaben | ADALAH | malebuang` / `ngaben | ADALAH | atiwa-tiwa`
  why: register adjunct padded into the subject creates a garbled compound.

- **S1261 [0]**  current: `ngaben | ADALAH | satu yadnya yang paling banyak ragam nya`
  fix: `ngaben | ADALAH | salah satu yadnya yang paling banyak ragamnya`
  why: "salah" dropped. N1 clause-retention itself is holding here — only the "salah" quantifier clipped.

- **S1290 [0]**  current: `yadnya | BERPERAN_SEBAGAI | beban`
  fix: `yadnya | BERPERAN_SEBAGAI | beban bagi pemikulnya`

- **S1308 [0]**  current: `tirtha | MEMILIKI | tarif bak barang dagangan`
  fix: `tirtha | MEMILIKI | tarif bak barang dagangan di pasar swalayan`

- **S1328 [0]**  current: `besar kecil punia | DILAKUKAN_DENGAN | upacara`
  fix: `besar kecil punia atau honorarium | DISINKRONKAN_DENGAN | jenis upacara tersebut`

- **S1335 [0]**  current: `tirtha | MEMILIKI | nilai spiritual`
  fix: `tirtha | MEMILIKI | nilai spiritual yang sama`

- **S1361 [0]-[4]**  current: `yadnya | BERDASARKAN | penuh sredaning citta / ...`
  fix: relabel all five to `yadnya | DIDUKUNG_DENGAN | ...`
  why: wrong relation label. Positive: a genuine 5-way coordinate chain, all five members correctly captured — N10 holding strongly here.

- **S1378 [0]**  current: `yama purwana tatwa | ADALAH | lontar`
  fix: `yama purwana tatwa | ADALAH | nama lontar yang memuat satu jenis pengabenan dengan sawa langsung selaku sasarannya`
  why: N1-pattern gap not on the named checklist, same defect.

- **S1422 [0]**  current: `sawa | DIPERCIKKAN_PADA | tirtha`
  fix: `sawa | DISIRATI_DENGAN | berbagai jenis tirtha`
  why: reverses roles; tirtha is the instrument, sawa the recipient.

- **S1429 [0]**  current: `daksina | ADALAH | penegasan`
  fix: `daksina | ADALAH | penegasan secara formal bahwa yadnya sudah selesai (siddhaning yadnya)`
  why: **D2 regression** — the "bahwa" continuation (advcl to the copula root, not acl to the object noun) was stripped. Named checklist sentence, GAP.

- **S1430 [0]**  current: `beras catur | ADALAH | lambang kekuatan panca dewata`
  fix: `beras catur | ADALAH | lambang kekuatan panca dewata selaku manifestasi hyang widhi yang mengelola alam semesta (bhuwana agung)`

- **S1439 [0]/[1]/[2]**  current subject `abu tulang kepala` for all three relations
  fix: subject should be `abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki` (all 7 conjuncts)
  why: **major D3 regression** — a 7-way coordinate subject list, only the first member survived.

- **S1452 [0]**  current: `nywasta | DILAKUKAN_OLEH | orang hal sawa`
  fix: `nywasta | DILAKUKAN_OLEH | orang`

- **S1456 [0]**  current: `nywasta | ADALAH | ngaben`
  fix: `nywasta | ADALAH | ngaben yang sangat sederhana dalam hal sajen dan alat-alat upakaranya`
  why: **D2 regression** — acl:relcl directly attached to the object noun yet still stripped. Named checklist sentence, GAP.

- **S1461 [0]**  current: `adegan | ADALAH | alat upakara`
  fix: `adegan | ADALAH | alat upakara yang terbuat dari daun rontal, beralaskan bakul kecil atau pangkon (paso kecil agak tinggi dari tanah atau perak)`

- **S1468 [0]**  current: `upakara | DISUCIKAN_DENGAN | sajen hingga dianggap wajar untuk digunakan`
  fix: `upakara | DISUCIKAN_DENGAN | sajen`
  why: result clause merged into the object; [1] correctly keeps both members of its 2-item list.

- **S1474 [0]-[3]**  current: `sesajen | DIPERSEMBAHKAN_KEPADA | diuskamaligi / nasi angkeb / saji / lain-lain`
  fix: relabel to `sesajen | MELIPUTI | diuskamaligi / nasi angkeb / saji / lain-lain`
  why: these are types/examples, not recipients; the real recipient "mendiang" is missing — see ADD. Positive: 4-item enumeration fully captured.

- **S1476 [0]**  current: `tirtha | DIPERCIKKAN_PADA | kedua perlambang`
  fix: `berbagai tirtha | DIPERCIKKAN_PADA | kedua perlambang`

- **S1483 [0]**  current: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading yang dikasturi dan disukutunggalkan`

- **S1493 [0]**  current: `kemampuan sosial ekonomi | JENIS_DARI | manah`
  fix: `kemampuan sosial ekonomi | JENIS_DARI | standar kedudukan seseorang di masyarakat`
  why: **N6 check** — direction is correct (swap fix working), but the category anchor is wrong (D11).

- **S1522 [0]**  current: `mendiang | DIKENAL_SEBAGAI | seseorang`
  fix: `mendiang | DIANGGAP_SEBAGAI | seseorang yang masih hidup`

- **S1523 [0]**  current: `mendiang | LAINNYA | pamitan`
  fix: `mendiang | MELAKUKAN | pamitan`
  why: positive: [1]-[3] correctly capture all three recipients — a clean 3-way N10 success.

- **S1544 [0]**  current: `sawa | MENYEBARKAN | bau`
  fix: `sawa | MENYEBARKAN | bau yang kurang sedap`

- **S1552 [0]**  current: `sumpe | BERFUNGSI_SEBAGAI | penguat rekatan`
  fix: `sumpe | BERFUNGSI_SEBAGAI | penguat rekatan antar badan peti dengan tutupnya`
  why: **D2 regression** — this is exactly the "berfungsi sebagai" pattern named in the fix spec, yet the nmod continuation was stripped.

- **S1558 [1]**  current: `sawa | DIBUNGKUS_DENGAN | paplengkungan semula`
  fix: `sawa | DIKURUNG_DENGAN | paplengkungan`

- **S1584 [0]**  current: `pitara | MELAMBANGKAN | bayangan diri`
  fix: `pitara | MEWUJUDKAN | bayangan diri dalam air ening`

## DROP  (triple should be removed)

- **S1452 [1]**  `nywasta | MENURUT | lontar petunjuknya`
  why: **D10 regression** — "menurut lontar X" is precisely the citation phrase the widened S13 fix should suppress; leaked through.

- **S1452 [2],[3],[4]**  `nywasta | MENINGGAL | pulau seberang` / `tenggelam` / `musibah lain`
  why: wrong-subject bug (D13) compounded with nonsense objects.

- **S1477 [1]**  `tirtha pangentas | ADALAH | daun alang-alang`
  why: appositive-misattribution; the sentence's real predicate ("dipersatukan dengan isi pengawak") was never extracted — see ADD.

- **S1522 [1]**  `mendiang | DIKENAL_SEBAGAI | situasi`
  why: "situasi" comes from an oblique adjunct, not a predicate nominal.

## ADD  (missing triples the sentence supports)

- **S1188**  `upacara ini | MEMPERGUNAKAN | tirtha panglukatan` (+ `upacara ini | MEMPERGUNAKAN | pabersihan`)
- **S1213**  `ayaban | DILAKUKAN_DI | rumah`
- **S1215**  `sawa | DILETAKKAN_DI | para-para tempat pembakarannya`
- **S1238**  `keluarga (yang ditinggalkan) | BERADA_DI | dunia ini`
- **S1290**  `yadnya | BERPERAN_SEBAGAI | pengorbanan`
- **S1407**  `ngaben jenis ini | MEMILIKI_SASARAN | jenazah`
- **S1458**  `alat upakara | DISEDIAKAN_DI | rumah` — 2-item coordinate subject, only "sesajen" survived.
- **S1461**  `adegan | TERBUAT_DARI | daun rontal` (+ `adegan | BERALASKAN | bakul kecil atau pangkon`)
- **S1463**  `roh mendiang | DIPERSILAKAN_DI | adegan` — 2-item coordinate subject, only "atma" survived.
- **S1465**  `jun pere | BERISI | air` (+ `jun pere | BERISI | 54 atau 108 lembar daun alang-alang`, `jun pere | BERISI | sembilan batang kayu cendana`)
- **S1467**  `pengawak | BERADA_DI | tempat yang telah ditentukan` — 2-item coordinate subject, only "adegan" survived.
- **S1474**  `sesajen | DIPERSEMBAHKAN_KEPADA | mendiang`
- **S1477**  `tirtha pangentas (dan isinya) | DIPERSATUKAN_DENGAN | isi pengawak`
- **S1482**  `sawa | MENJADI | abu (seluruhnya)`
- **S1504**  `ngulapin | MEMILIKI_MAKNA | makna yang mirip dengan itu`
- **S1525**  `pengawak | BERADA_DI | balai adat` (+ `pengawak | DIBERI | sajen`, `pengawak | DIBERI | perjamuan lain`) — same systemic subject-coordination gap as S1439/S1458/S1463/S1467.
- **S1533**  `pengawak | DIPERLAKUKAN_SAMA_DENGAN | sawa asli`
- **S1556**  `panca datu | DIGUNAKAN_UNTUK | memohon kepada hyang widhi (restu panca dewata)`
- **S1584**  `tarpana | DILAKUKAN_DENGAN | pujastawa` (+ `tarpana | DILAKUKAN_OLEH | ida sang sadaka`)
- **S1597**  `kakerebsari | ADALAH | alat upakara yang pelik dalam pangabenan ini` — 2-item coordinate subject, only "kajang" survived.

## NOTE

- **D1/D2 (N1) regression check (named sentences + others found):** HOLDING: S1189, S1205, S1206, S1261, S1597. **GAP:** S1429, S1456 (both named checklist sentences), plus S1378, S1430, S1461, S1483, S1552. Pattern: fails when the defining clause is an acl:relcl without an intervening pivot (S1456), or a "bahwa" clause attached as advcl to the copula root (S1429).
- **D3 (N10) regression check** — strong successes on object-side lists (S1361 5-way, S1474 4-way, S1523 3-way). Subject-side coordinate NPs still truncated across the board: S1439 (7-way!), S1458, S1463, S1467, S1525, S1597.
- **D10 (S13) regression check** — two clear leak-throughs: S1226 (exact named example) and S1452.
- **D11 (N6) regression check** — S1493: swap direction correct, category-anchor resolution buggy.
- **N5/N7/N8/N9 confirmation** — S1514 shows the subject-qualifier-stripping pattern still present.
- **S1221** — object merges two possibly-distinct containers via a literal "/"; ambiguous, flagging for awareness.
- **S1409** — two negated exclusions carry real information but don't fit the positive-triple schema; fine to leave unextracted.

## Chunk stats
FIX: 30   DROP: 5   ADD: 20   sentences reviewed: 61

---

# Chunk 4 audit (S1601..S2087)

## FIX  (triple is salvageable — give the corrected triple)

- **S1601 [1]**  current: `kajang | DILAKUKAN_DI | plengkungan sawa`
  fix: `kajang | BERADA_DI | plengkungan sawa`

- **S1603 [0]**  current: `lancingan kajang | DIBAWA_KE | setra tempat pembakaran`
  fix: `jenazah | DIBAWA_KE | setra tempat pembakaran`
  why: **D13 wrong-subject bug** — adverbial clause's subject is jenazah, not the main clause's "lancingan kajang". See ADD for the real main-clause relation.

- **S1605 [0]**  current: `kajang | DILETAKKAN_DI | depan pendeta`
  fix: `kajang | DILETAKKAN_DI | depan pendeta yang memujanya`

- **S1629 [0]**  current: `kajang suratan | DIKENAL_SEBAGAI | atribut nilai martabat warga`
  fix: relabel to `kajang | BERPERAN_SEBAGAI | atribut nilai martabat warga`

- **S1639 [1]**  current: `kajang | DIPUJA | pamlaspasan`
  fix: `kajang | DIPUJA_PADA | pamlaspasan`

- **S1642 [1]**  current: `pelita kecil | TERBUAT_DARI | kulit telur ayam`
  fix: `pelita kecil | TERBUAT_DARI | kulit telur ayam berminyak kelapa`

- **S1688 [0]**  current: `adegan | MELAMBANGKAN | cili`
  fix: `adegan | BERWUJUD | cili`

- **S1699 [0]**  current subject: `sangaskara`
  fix: also add `samskara | ADALAH | upacara penyucian` and `panyangaskara | ADALAH | upacara penyucian`
  why: 3-way coordinate subject (three names for the same rite), only first survived — **D3**.

- **S1713 [0]**  current: `adegan | DIAMBIL_DENGAN | penuh hormat keluarga`
  fix: `adegan | DIAMBIL_OLEH | keluarga (yang ngaben)`

- **S1732 [1]**  current: `upadesa | BERARTI | bisikan dang guru`
  add: `upadesa | BERARTI | tatwa pengarahan hidup`
  why: 2-item list, only first kept.

- **S1738 [0]**  current: `mendiang hidup | ADALAH | pemangku`
  fix: subject to plain `mendiang`; also add `mendiang | ADALAH | pejabat` and `mendiang | ADALAH | sastrawan`
  why: (a) **D9 subject-fusion bug** — "semasa hidupnya" compounded into the subject as "mendiang hidup"; recurs at S1823. (b) 3-way conj chain, only "pemangku" kept — **D3**.

- **S1738 [2]**  current: `mendiang hidup | LAINNYA | ida bagus`
  fix: subject to `mendiang`; add coordinate member `ida ayu`

- **S1753 [0]**  current: `mendiang | DIYAKINI_DENGAN | penghadang`
  fix: `mendiang | AKRAB_DENGAN | penghadang`

- **S1763 [0]**  current: `banten | MENGHASILKAN | sekah abin`
  fix: drop this relation and instead add `sekah abin | BERPERAN_SEBAGAI | ciri khusus` as its own triple (see ADD)

- **S1763 [1]**  current subject: `banten`
  fix: `banten bebangkit atau pulagembal | BERPERAN_SEBAGAI | dasar`

- **S1764 [0]**  current: `sekah abin | DIPANGKU | nama`
  fix: `sekah abin | DIPANGKU_OLEH | yang menggelar yadnya`

- **S1782 [0]**  current: `pamerasan | ADALAH | upacara timbang`
  fix: `pamerasan | ADALAH | upacara timbang terima secara keagamaan, antara mendiang yang akan pergi ke dunia lain dengan keluarga (terutama anak-anak) yang masih hidup`
  why: (1) "timbang terima" truncated to "timbang"; (2) **D1 gap** — the entire defining clause stripped. (Positive: the attribution phrase "menurut sang arif bijaksana" correctly did NOT leak — S13 holding here.)

- **S1823 [0]**  current: `mendiang masa hidup | MEMEGANG | jabatan`
  fix: `mendiang | MEMEGANG | jabatan`
  why: same D9 subject-mangling bug as S1738.

- **S1832 [0]**  current: `karma phala orangtua | DITUJUKAN_UNTUK | keturunan`
  fix: `karma phala orangtua | DIWARISKAN_KEPADA | keturunan`

- **S1845 [0]**  current: `panebusan | DITUJUKAN_UNTUK | kedudukan pitara`
  fix: `panebusan | MEMPENGARUHI | kedudukan pitara`

- **S1850 [0]/[1]**  current: `mamutru | LAINNYA | asal kata` / `perubahan kata pitra`
  fix: `mamutru | BERASAL_DARI_KATA | putru` / `mamutru | MERUPAKAN_PERUBAHAN_DARI | pitra`

- **S1889 [0]**  current: `pangabenan | DILAKUKAN | tiga hari ngaben`
  fix: `pabersihan | DILAKUKAN | dua atau tiga hari sebelum ngaben`
  why: **D13 wrong-subject bug** — extractor conflated two distinct ceremonies.

- **S1938 [0]**  current: `pengabenan | MEMILIKI | tingkat utama`
  fix: `pengabenan | DINILAI_SEBAGAI | tingkat utama`

- **S1963 [3]**  current: `pering | LAINNYA | mahkota`
  fix: `pering | MENYERUPAI | mahkota`

- **S1963 [4]**  current: `pering | DILAKUKAN_DI | sajen surya untuk surya , penebusan , pamerasan , banten teben dan sebagai nya`
  fix: split into four separate relations
  why: **D6** — a genuine 4-item list *was* walked correctly but dumped into one garbled literal string instead of being emitted as four separate relations.

- **S2000 [1]**  current: `jenazah raja bali | ADALAH | gelgel/klungkung`
  fix: relabel/restructure to `raja bali | BERASAL_DARI | gelgel/klungkung`

- **S2002 [0]**  current: `bade | DITUJUKAN_UNTUK | keluarga`
  fix: `bade | DITUJUKAN_UNTUK | keluarga yang leluhurnya pernah menjadi punggawa dan pejabat yang sederajat`

- **S2003 [0]**  current: `wadah | ADALAH | usungan`
  fix: `wadah | ADALAH | usungan yang tanpa badawang mungkin bertingkat memakai hiasan boma dan warna kapas terbatas`

- **S2029 [0]**  current: `mangle | DILETAKKAN_DI | tingkatan bade`
  fix: `mangle | BERGANTUNG_PADA | tingkatan bade atau wadah`

- **S2087 [2]**  current: `naga banda | BERASAL_DARI | keluarga`
  fix: `naga banda | DITUJUKAN_UNTUK | keluarga tertentu saja`

## DROP  (triple should be removed)

- **S1738 [1]**  `mendiang hidup | DILAKUKAN_DENGAN | rendah hati`
  why: low-confidence extraction from a culturally dense, ambiguous sentence; subject is mangled and unclear who's acting.

## ADD  (missing triples the sentence supports)

- **S1602**  `lancingan | ADALAH | kain putih (panjangnya puluhan meter)`
- **S1603**  `lancingan kajang | DIJUNJUNG_OLEH | keturunan mendiang`
- **S1606**  `kajang | DIHIDUPKAN_DENGAN | puja`
- **S1609**  `moksa | ADALAH | kembalinya unsur badan manusia ke asalnya (bhuwana agung/pancamahabutha)`
- **S1629**  `kajang | MEMILIKI | nilai dan bobot istimewa`
- **S1688**  `cili | TERBUAT_DARI | rontal (dilapisi kertas emas)`
- **S1776**  `uang kepeng | DIBUNGKUS_DENGAN | daun dapdap` (+ `uang kepeng | DIIKAT_DENGAN | benang tridatu (merah, hitam dan putih)`)
- **S1783**  `mendiang | MENYERAHKAN | hak` (+ `mendiang | MENYERAHKAN | berbagai milik yang dulunya ada pada mendiang`) — positive: first clause's 3-item list fully captured.
- **S1823**  `upacara panebusan | ADALAH | sesuatu yang mutlak (dalam pengabenan)`
- **S1853**  `lontar putru | MEMILIKI_JENIS | putru sangaskara` (+ `lontar putru | MEMILIKI_JENIS | putru saji`)
- **S1898**  `yeh panembak | DIGUNAKAN_PADA | pengabenan`
- **S1899**  `yeh panembak | DIPAKAI_OLEH | umat hindu di bali` — positive: both S13 and N1 holding on this sentence.
- **S1915**  `pabersihan | DILANGSUNGKAN_PADA | hari senin`
- **S2045**  `patulangan | BERFUNGSI_SEBAGAI | tempat pembaringan jenazah (dan dapur pembakaran)`

## NOTE

- **D1/D2 (N1) regression check (named sentences + others):** HOLDING: S1610, S1982, S1650, S1657, S1717, S1899, and (attribution half only) S1639/S1732/S1782. **GAP:** S1937 and S2055 (both named checklist sentences — S2055's is a `ccomp`, a distinct attachment). Also S1782 (major), S2002, S2003.
- **D3 (N10) regression check** — object-side mostly succeeds (S1783 3-way, S1963[0]-[2] 3-way). New failure shapes: subject-side coordination (S1699, S1738 appositive), and S1963[4] shows the walk *succeeding* but dumping into a garbled single string (D6). S1853 shows an nmod+conj chain the walk missed entirely.
- **D10 (S13) regression check** — holding well in this chunk: S1639, S1732, S1782, S1899.
- **D11 (N6) regression check** — S2065 is a second confirmed instance of the anchor-resolution bug seen at S1493.
- **D9 confirmation** — S2055/S2056 confirm the bade/patulangan shape-qualifier-stripping pattern still present; plus the new "mendiang hidup"/"mendiang masa hidup" subject-fusion bug at S1738/S1823.
- **S2000/S2028/S2029/S2034** — "bade"/"wadah" are NER-canonicalized as the same entity, so some dropped "atau wadah" members are lower-priority.

## Chunk stats
FIX: 29   DROP: 1   ADD: 13   sentences reviewed: 61

---

# Chunk 5 audit (S2093..S2630)

## FIX  (triple is salvageable — give the corrected triple)

- **S2093 [0]**  current: `mendiang | MEMILIKI | ikatan erat`
  fix: `mendiang | MEMILIKI | ikatan erat dengan masyarakat`

- **S2115 [0]**  current: `swadharma kemasyarakatan | ADALAH | mahayana`
  fix: `kelompok ini | ADALAH | paksa mahayana (kendaraan besar)`
  why: wrong subject; "swadharma kemasyarakatannya" is the karena-clause giving the reason for the name.

- **S2130 [0]/[1]**  current: `peranda shiwa | MENEMPATKAN | diri` / `jenana`
  fix: `peranda shiwa | MENEMPATKAN | diri/jenana pada daya suci hyang widhi`

- **S2130 [2]**  current: `peranda shiwa | DILETAKKAN_DI | atas alias`
  fix: `peranda shiwa | MENEMPATKAN_DIRI_DI | luar alam duniawi (mula-mula di atas / di luar alam duniawi)`
  why: "alias" here means "atau", joining two paraphrases, not a distinct object.

- **S2133 [0]**  current: `naga banda | DILAKUKAN_SAAT | palebon`
  fix: `naga banda | DIGUNAKAN_SAAT | palebon`

- **S2184 [1]**  current: `bale salunglung | DILETAKKAN_DI | arah hulu`
  fix: `bale salunglung | DILETAKKAN_DI | sekitar empat atau lima meter di arah hulu dari tempat pembakaran jenazah`

- **S2198 [3]**  current: `wilayah | ADALAH | kantongnya sesuatu`
  fix: `wilayah | ADALAH | kantongnya segala sesuatu yang didetasering di dunia ini`
  why: see D2 note — a nested `object_decomposition` child of a sentence whose top-level split otherwise works correctly.

- **S2212 [0]**  current: `bale salunglung | ADALAH | simbol pitraloka`
  fix: `bale salunglung | ADALAH | simbol pitraloka untuk tempat badan halus mendiang`

- **S2256 [0]**  current: `pamerasan | ADALAH | uang kepeng`
  fix: `pamerasan | ADALAH | sejumlah uang kepeng yang dibungkus dengan daun dapdap dan diikat benang tridatu`

- **S2258 [0]**  current: `pamerasan | ADALAH | sarana pemberitahuan`
  fix: `pamerasan | ADALAH | sarana pemberitahuan akan adanya pangabenan untuk mendiang`
  why: **D1 gap, still not holding** (see NOTE).

- **S2258 [1]**  current: `sarana pemberitahuan | DITUJUKAN_UNTUK | mendiang`
  fix: drop this triple (superseded by fix to [0]) or relabel as `pangabenan | DITUJUKAN_UNTUK | mendiang`

- **S2262 [0]**  current: `tirtha | DIMOHON_DI | pendeta`
  fix: `tirtha | DIMOHON_KEPADA | pendeta yang muput pangabenan itu`

- **S2323 [1]**  current: `bade | BAGIAN_DARI | alat penting lainnya`
  fix: `bade (dan lembu) | TERMASUK_BERSAMA | alat penting lainnya (semua tergolong sarana siap pakai)`
  why: reversed/wrong relation — same failure family as the N6 "termasuk" reversal (D11-adjacent, doesn't go through the swap path).

- **S2336 [4]**  current: `kajang | MELAMBANGKAN | tanda hormat bakti`
  fix: `kajang | MELAMBANGKAN | tanda hormat bakti kepada mendiang`

- **S2340 [0]**  current: `adegan | ADALAH | arak-arakan indah`
  fix: `adegan | DIJADIKAN | unsur arak-arakan indah (oleh pemudi-pemudi keluarga bersangkutan)`

- **S2363 [0]**  current: `bale pamuunan | DIKELILINGI | tiga kali`
  fix: `bale pamuunan | DIKELILINGI_OLEH | bade dengan jenazahnya (sebanyak tiga kali)`

- **S2364 [0]**  current: `bade | DILETAKKAN_DI | teben lembu`
  fix: `bade | DILETAKKAN_DI | sebelah hilir atau teben lembu`
  why: **D4** — missing coordinate member.

- **S2370 [0]**  current: `pradaksina | MEMPEROLEH | imbas kesucian`
  fix: `material | MEMPEROLEH | imbas kesucian dari yang immaterial`

- **S2374 [0]**  current: `prasawya | ADALAH | lambang gerak peningkatan diri`
  fix: `prasawya | ADALAH | lambang gerak peningkatan diri dari sesuatu, atau gerak ke atas`
  why: **D4** — missing coordinate member.

- **S2377 [0]**  current: `ngaben | MEMILIKI | tujuan pokok`
  fix: `ngaben | MEMILIKI | tujuan pokok untuk merubah jenazah (atau "benda bekas" badan seseorang) hingga kembali menjadi pancamahabutha sebagaimana asalnya semula`
  why: **D1 regression — the exact sentence Iteration 1 flagged, confirmed still broken.**

- **S2380 [1]**  current: `cara prasawya | ADALAH | berputar`
  fix: `cara prasawya | ADALAH | berputar ke kiri, berlawanan dengan putaran jarum jam`

- **S2387 [0]**  current: `bade sawa atas | DILETAKKAN_DI | hilir lembu`
  fix: `bade (dengan sawa di atasnya) | DILETAKKAN_DI | sebelah hilir lembu`

- **S2419 [0]**  current: `adegan | DIPERSEMBAHKAN_KEPADA | hyang agni`
  fix: `adegan, angenan, pisang jati, panguryagan, dan lain-lain alat yang harus dibakar | DIPERSEMBAHKAN_KEPADA | hyang agni (api), tanpa sisa`
  why: **major D3 truncation** — 5-conjunct "dan lain-lain" list, only first kept.

- **S2448 [0]**  current: `suku tunggal | DITUJUKAN_UNTUK | bhatara-bhatari`
  fix: `suku tunggal | MENGHATURKAN | sembah bakti pamitan kepada bhatara-bhatari`

- **S2455 [0]**  current: `pangabenan | TERDIRI_DARI | jenis`
  fix: `pangabenan | TERDIRI_DARI | berbagai jenis`

- **S2472 [0]**  current: `pranawa | BERARTI | lambang suara`
  fix: `pranawa | BERARTI | lambang suara "om"`

- **S2483 [0]/[1]**  current: `mendiang | MEMPEROLEH | situasi demikian` / `supta pranawa | ADALAH | satu pangabenan`
  fix: `... | ... | situasi demikian di alam lain` / `... | ... | satu pangabenan yang berlandaskan hasrat, semoga mendiang mendapatkan situasi demikian di alam lain`
  why: [1] is N1-style truncation.

- **S2485 [0]**  current: `pangabenan pranawa | DITUJUKAN_UNTUK | mendiang`
  fix: `pangabenan pranawa | DITUJUKAN_UNTUK | mendiang yang telah tak ada sawanya lagi`

- **S2502 [1]/[2]/[3]**  current: `sawa wedana | DIGELAR_DENGAN | roh` / `arwah` / `badan halus mendiang`
  fix: `sawa wedana | BERTUJUAN_MENYUCIKAN | roh` / `arwah` / `badan halus mendiang`

- **S2502 [4]**  current: `sawa wedana | MENJADI | atma`
  fix: `badan halus mendiang (roh/arwah) | MENJADI | atma yang tanpa badan sama sekali`
  why: wrong subject.

- **S2527 [0]/[1]**  current: `pura | ADALAH | dewaloka` / `alam kedewaan`
  fix: `pura, pamrajan, atau kahyangan jenis apapun | ADALAH | dewaloka atau alam kedewaan`
  why: **D3** — subject lists 3 conjuncts, only "pura" kept.

- **S2535 [0]**  current: `pitara | MENGELUPASI | suksmasarira`
  fix: `pitara | MENGELUPASI | suksmasarira yang merupakan "kulit dirinya"`

- **S2542 [0]**  current: `atma wedana | MEMILIKI | jenis`
  fix: `atma wedana | MEMILIKI | beberapa jenis`

- **S2548 [0]/[1]**  current: `tirtha pangentas atiwa-tiwa | DIPERCIKKAN_PADA | sesosok mayat` / `perlambang`
  fix: `tirtha pangentas atiwa-tiwa | DIPERCIKKAN_PADA | sesosok mayat atau perlambangnya, hanya sekali saja`

- **S2555 [0]**  current: `atma wedana | ADALAH | upacara penyucian pitra`
  fix: `atma wedana | ADALAH | nama resmi upacara penyucian pitra`

- **S2563 [0]**  current: `bhuwana alit | MEMILIKI | 11 bidang`
  fix: `bhuwana alit | MEMILIKI | 11 bidang yang mudah ditimpa suasana "sebel"`

- **S2566 [0]**  current: `demikian bhuwana agung | MEMPEROLEH | cuntaka`
  fix: `bhuwana agung (masing-masing arah yang berjumlah 11) | MEMPEROLEH | cuntaka selama sehari`

- **S2571 [0]**  current: `arjuna | MENGHUKUM | diri` — keep as-is (fine).

- **S2604 [0]**  current: `kedua ngangsen | ADALAH | <45-word verbatim run-on>`
  fix (split): `ngangsen | ADALAH | upacara penyucian sementara bagi sang pitra`; `pitra (dalam ngangsen) | BARUSAN_LEPAS_PERTALIAN_DENGAN | stulasarira nya`; `ngangsen | BERTUJUAN | agar suksmasarira pitra tidak lagi dilekati bekas-bekas badan kasar`
  why: **D15** — dumps entire sentence as one undifferentiated ~45-word object.

- **S2612 [0]**  current: `pitra | MENGHASILKAN | perlambang`
  fix: `pitra mendiang | DIBUATKAN | perlambang (yang disebut sekah kangsen)`
  why: **D7 (N3-family)** benefactive-passive inversion.

- **S2620 [0]**  current: `dulang | DILETAKKAN_DI | hulu arena upacara`
  fix: `dulang atau meja kecil | DILETAKKAN_DI | bagian hulu arena upacara`

- **S2624 [0]**  current: `pitra mendiang | MEMAKAI | wujud`
  fix: `pitra mendiang | MEMAKAI | wujud tersebut selaku "pralingga"-nya (perlambang diri yang dihuni)`

- **S2630 [0]**  current: `pitra | DINILAI_DENGAN | upacara penyucian`
  fix: `pitra | MENERIMA | sembah bhakti serta ayaban sajen`

## DROP  (triple should be removed)

- **S2117 [0]**  `peranda buddha | BERDASARKAN | pengertian`
  why: citation/reasoning-basis adjunct, not a real predicate — see ADD for the real content.

- **S2269 [0]**  `bale pamuun (BANGUNAN_RITUAL) | LAINNYA | de facto`
  why: nonsensical; "secara de facto" describes completion status, not an entity.

- **S2502 [0]**  `sawa wedana | ADALAH | wedana`
  why: tautological same-root gloss, not a distinct entity.

- **S2542 [1]**  `atma wedana (RITUAL_KEMATIAN) | MEMILIKI | hal pangabenan (RITUAL_KEMATIAN)`
  why: **D10 — comparative adjunct leak, confirmed still-open, matches iteration-1 flag on this exact sentence.**

- **S2566 [1]**  `demikian bhuwana agung | MEMPEROLEH | sehari`
  why: duplicate fragment of relation [0].

- **S2571 [1]**  `arjuna | MENGHUTAN | 12 tahun`
  why: wrong object, likely wrong subject; too garbled to safely reconstruct.

## ADD  (missing triples the sentence supports)

- **S2093**  `mendiang | MEMILIKI | pertalian intim dengan soal duniawi material`
- **S2115**  `kelompok (paksa mahayana) | BERTUGAS_MENGANGKUT | masyarakat manusia ke alam sana`
- **S2117**  `peranda buddha | MEMAKAI | naga banda` (+ `naga banda | DIPAKAI_SAAT | palebon`)
- **S2124**  `swadharma (beliau) | BERTUJUAN_UNTUK | menyucikan dunia ini`
- **S2130**  `peranda shiwa | TURUN_MERESAPI | alam ini`
- **S2234**  `jenazah seseorang | TERTANAM_TITIP_DI | sebuah setra`
- **S2252**  `mendiang (keponakan, cucu-cucu) | TERGOLONG | keluarga sampingan (bukan keluarga satu sidikara/saling sembah)`
- **S2258**  `pamerasan | ADALAH | tanda bahwa keluarga mendiang tidak lupa akan adanya ikatan keluarga`
- **S2262**  `sang cucu | MEMOHON | tirtha`
- **S2269**  `bale pamuun (dan alat-alat upakara lainnya) | TELAH_SELESAI | (secara de facto)`
- **S2363**  `bale pamuunan | DIHUNI | lembu`
- **S2370**  `pradaksina | MELAMBANGKAN | turunnya purusa meresapi pradana`
- **S2380**  `bade | BERLAWANAN_DENGAN | gerak pradaksina yang dilakukan pada upacara dewa yadnya di pura`
- **S2419**  (superseded by FIX above restoring the full coordinate subject list).
- **S2448**  `bhatara-bhatari | BERSEMAYAM_DI | pura dan pamrajan panyiwiannya`
- **S2455**  `pangabenan jenis (masing-masing) | MEMILIKI | nama sendiri-sendiri`
- **S2473**  `pangabenan yang menggunakan nama pranawa | DILATARBELAKANGI_OLEH | hasrat supaya mendiang memperoleh ketenangan, kemantapan, dan kesucian`
- **S2520**  `atma wedana | BERBEDA_DENGAN | ngaben (dalam hal sifat sebel)`
- **S2542**  `jenis atma wedana (masing-masing) | MEMILIKI | nama dan ciri-ciri tersendiri`

## NOTE

- **D1 (N1) regression check — S2198**: mostly HOLDING at the top level; a nested `object_decomposition` child still truncates (D2, "recursive" gap).
- **D1 regression check — S2258**: NOT HOLDING — object_decomposition misattributes "untuk mendiang", and the second parataxis conjunct is entirely dropped.
- **D1 regression check — S2377**: NOT HOLDING — the exact case Iteration 1 flagged, remains unfixed.
- **D1-adjacent (outside required list)**: recurs at S2256, S2483[1], S2502(all), S2555, S2563, S2624; contrast S2265, S2649(ch6), S2904(ch6) where it works.
- **D3 (N10) check — S2336**: HOLDING (positive), 3-member chain fully captured across three relations.
- **D3/D5 violations beyond checklist**: S2419 (5-member list truncated to 1), S2527 (3-member), S2093/S2374/S2380/S2455/S2620/S2566 (2-member).
- **D10 (S13) check — S2527/S2555**: HOLDING, no leakage.
- **D10 comparative check ("sebagaimana halnya X")**: NOT HOLDING at S2542 — the exact sentence Iteration 1 flagged, confirmed still open.
- **S2224/S2316/S2337/S2406/S2449/S2535**: minor nits or positive confirmations, no hard fix needed (S2449 confirms the flag.txt #58b/58c wrong-subject pattern is NOT recurring there — good).

## Chunk stats
FIX: 40   DROP: 6   ADD: 20   sentences reviewed: 61

---

# Chunk 6 audit (S2635..S3154)

## FIX  (triple is salvageable — give the corrected triple)

- **S2635 [0]**  current: `tarpana | ADALAH | klimaks upacara sederhana`
  fix: `tarpana dan muspa | ADALAH | klimaks dalam upacara sederhana ini`
  why: **D4** — coordinate subject "dan muspa" dropped entirely.

- **S2642 [0]**  current: `sekah kangsen | SETELAH | pamralina`
  fix: `sekah kangsen | DIBONGKAR_SETELAH | pamralina`

- **S2644 [0]**  current: `abu daun | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu daun (yang dinilai selaku bekas-bekas stulasarira mendiang) | DIMASUKKAN_KE_DALAM | klungah nyuh gading (yang dibentuk menjadi suku tunggal)`

- **S2651 [0]**  current: `atma wedana | DITUJUKAN_UNTUK | mendiang`
  fix: `atma wedana | DITUJUKAN_UNTUK | mendiang (baru dapat diadakan setelah mungkin lima atau sepuluh tahun kemudian)`

- **S2667 [0]**  current: `payadnyan | ADALAH | bangunan pokok`
  fix: `payadnyan | ADALAH | bangunan pokok pada arena ini`

- **S2672 [0]**  current: `payadnyan | ADALAH | bangunan`
  fix: `payadnyan | ADALAH | bangunan yang paling rendah`
  why: **D1-adjacent** — truncates to bare generic noun.

- **S2748 [0]/[1]/[2]** — no fix needed, correct. **N6 regression-check target, HOLDING.**

- **S2752 [0]**  current: `mendiang | MENGHASILKAN | wujud sekah`
  fix: `mendiang | LAHIR_DALAM_WUJUD | sekah`

- **S2758 [1]**  current: `suksma sarira | ADALAH | tanpa berbadan sama sekali atau hanya "atma tattwatma"...`
  fix: `mendiang | BERUBAH_DARI_SUKSMA_SARIRA_MENJADI | tanpa berbadan sama sekali atau "atma tattwatma"`

- **S2762 [2]**  current: `mendiang | DIPEROLEH_DARI | pendeta jalan`
  fix: `mendiang | MEMPEROLEH_DARI | pendeta` (+ `upanisad | TENTANG | jalan yang harus ditempuh`)

- **S2768 [0]**  current: `sangge | ADALAH | dia`
  fix: `sangge | ADALAH | "sang ngae" diri kita`

- **S2777 [0]**  current: `bhatara | DITUJUKAN_UNTUK | utpeti`
  fix: `bhatara | DIPERSILAKAN_UNTUK | utpeti (masuk dan menghuni)`

- **S2777 [1]**  current: `utpeti | ADALAH | masuk`
  fix: `utpeti | ADALAH | masuk dan menghuni`

- **S2780 [0]**  current: `sanggar surya baligia | MEMILIKI | ruang`
  fix: `sanggar surya baligia | MEMILIKI | tiga buah ruang`

- **S2787** — correct, no fix needed.

- **S2794 [0]**  current: `sekah | BERASAL_DARI | pawedan`
  fix: `sekah | DITURUNKAN_DARI | pawedan`
  why: note [1] `sangge JENIS_DARI sekah` is correct — **N6 HOLDING**.

- **S2803 [0]/[1]**  current: `pawedan samping tempat ngajum | ADALAH | tempat sulinggih` / `tempat sulinggih | DIPERSEMBAHKAN_KEPADA | upacara atma wedana`
  fix: `pawedan | ADALAH | tempat sang sulinggih dalam memuja` / `tempat sulinggih (dalam memuja) | DIGUNAKAN_UNTUK | segenap upacara atma wedana ini`

- **S2810 [0]**  current: `pawedan tempat | LAINNYA | shiwa`
  fix: `pawedan (tempat memuja) | MERUPAKAN | "shiwa (dewa) loka"`

- **S2812 [1]**  current: `pitra | ADALAH | atma`
  fix: `pitra | ADALAH | atma yang masih bersuksmasarira`

- **S2819 [0]**  current: `payadnyan | ADALAH | sekadar bangunan darurat buatan manusia`
  fix: `payadnyan | ADALAH | sekadar bangunan darurat buatan manusia di mercapada ini`

- **S2824 [0]**  current: `sekah | DIMASUKKAN_KE_DALAM | pintu belakang`
  fix: `sekah | DIMASUKKAN_MELALUI | pintu belakang`

- **S2832 [0]**  current: `sekah | MEMBELAKANGI | pendeta`
  fix: `sekah | MEMBELAKANGI | pendeta yang ada di pawedannya (jika masuk melalui jalan depan)`

- **S2843 [0]**  current: `sulinggih | DIPERSEMBAHKAN_KEPADA | santapan istimewa`
  fix: `santapan istimewa | DIHATURKAN_KEPADA | sulinggih, tukang banten, dan tamu terhormat/khusus lainnya`
  why: **D7 (N3, required check) — NOT FIXED**, reversed direction plus a 4-member D3 list truncation.

- **S2854 [1]**  current: `pitra mendiang | MENYAKSIKAN | anak cucu`
  fix: `pitra mendiang | MENYAKSIKAN | anak cucu (nya) melakukan upacara manusa yadnya tersebut`

- **S2894 [0]**  current: `pralina | DILAKUKAN_DENGAN | upacara saji tarpana`
  fix: `pralina | KALAH_MERIAH_DIBANDING | upacara saji tarpana`

- **S2914 [0]**  current: `suksma sarira | ADALAH | materi`
  fix: `suksma sarira | ADALAH | materi (walaupun sangat halus)`

- **S2923 [0]**  current: `mamukur | DILINDUNGI_DENGAN | upaya penyucian wilayah`
  fix: `mamukur dan upacara sebangsanya | DILINDUNGI_DENGAN | upaya penyucian wilayah yang ketat dengan berbagai pantangannya`

- **S2948 [0]**  current: `abu | DIMASUKKAN_KE_DALAM | klungah nyuh gading`
  fix: `abu (yang sudah lumat) | DIMASUKKAN_KE_DALAM | klungah nyuh gading yang "disukutunggalkan"`

- **S2954 [0]**  current: `atma pitara | MENUJU | dewaloka`
  fix: `atma pitara | DIMOHONKAN_AGAR_MENUJU | dewaloka`

- **S2969 [0]**  current: `ngajar-ajar | BERMAKNA | upacara pernyataan parama suksmaning idep`
  fix: `ngajar-ajar | BERMAKNA | upacara pernyataan parama suksmaning idep, alias ucapan terima kasih dari pihak sang mayadnya kepada para penuntun (para ajar) yang telah memberikan jasa-jasanya`

- **S2986 [1]**  current: `pitra | MENGHASILKAN | dua buah daksina tapakan`
  fix: `pitra | MENERIMA | dua buah daksina tapakan (dibuat untuknya)`
  why: **D7 (N3, required check) — NOT FIXED.**

- **S2986 [2]/[3]**  current: `pitra | DITUJUKAN_UNTUK | bhatara` / `bhatari`
  fix: `daksina tapakan (satu) | DITUJUKAN_UNTUK | bhatara` / `bhatari`

- **S2988 [0]**  current: `patileman pitra | MENINGKAT | kedudukan`
  fix: `pitra | MENINGKAT_KEDUDUKAN_MENJADI | bhatara atau bhatari (sejak selesainya patileman)`

- **S3001 [0]**  current: `punia | ADALAH | <45-word verbatim run-on>`
  fix (split): three atomic triples — see chunk detail.
  why: **D15**, same class as S2604.

- **S3004 [1]**  current: `perwujudan sredaning cita | ADALAH | wujud ketulus-ikhlasan hati pihak dari ketulus-ikhlasan hati pihak yang bersangkutan`
  fix: `perwujudan sredaning cita | ADALAH | wujud dari ketulus-ikhlasan hati pihak yang bersangkutan`
  why: **D12 duplication artifact.**

- **S3063 [0]**  current: `jenazah | BERASAL_DARI | kotoran-kotoran`
  fix: `jenazah | DIBERSIHKAN_DARI | kotoran-kotoran (yang telah lama berada pada badan orang yang meninggal)`
  why: major meaning-reversal.

- **S3080 [0]**  current: `jenazah | DITARUHKAN | punjung`
  fix: `punjung (makanan kecil) | DITARUHKAN_DI_SAMPING | jenazah`
  why: **D7 (N3, required check) — NOT FIXED, clearest example**; parser mistags "jenazah" as nsubj:pass.

- **S3110 [1]**  current: `daun intaran | DILETAKKAN_DI | kedua alis orang`
  fix: `daun intaran | DILETAKKAN_DI | kedua alis orang yang meninggal, ketika upacara mabersih mati (ngelelet)`

- **S3122 [0]/[1]** — acceptable as-is, no fix needed beyond ADD below for [2].

- **S3133 [0]**  current: `paes gedubang | DILETAKKAN_DI | atas takir bersama`
  fix: `paes gedubang | DILETAKKAN_DI | atas takir`

- **S3133 [1]**  current: `paes gedubang | DILETAKKAN_DENGAN | secarik kain hitam`
  fix: `paes gedubang | DILETAKKAN_DENGAN | secarik kain hitam yang nanti akan digunakan untuk menutup kelamin (angkeb sarira)`

- **S3150 [0]**  current: `sekar ura | DILAKUKAN_DI | persimpangan jalan menuju`
  fix: `sekar ura | DITABURKAN_DI | setiap persimpangan jalan menuju setra`

- **S3153 [0]**  current: `sisig | TERBUAT_DARI | arang pembakaran jaja uli`
  fix: `sisig | TERBUAT_DARI | arang pembakaran jaja uli atau jaja gina`

- **S3154 [0]**  current: `pecahan kaca | DILETAKKAN_DI | atas takir`
  fix: `pecahan kaca dan pecahan besi baja | DILETAKKAN_DI | atas takir`
  why: **D3** — drops coordinate subject entirely.

## DROP  (triple should be removed)

- **S2750 [0]/[1]/[2]**  `pitra mendiang | BERPERAN_SEBAGAI | sarana` / `sarana | ADALAH | sulinggih pujastawa` / `pitra mendiang | BERPERAN_SEBAGAI | satu sajen sederhana`
  why: sentence heavily garbled/run-on; too tangled to safely reconstruct. See ADD for the one recoverable fact.

- **S2947 [0]**  `abu (SARANA_RITUAL) | DIUYEG | selumat-lumat (None)`
  why: manner adverb, not an entity.

- **S3110 [0]**  `daun intaran (SARANA_RITUAL) | DIPAKAI_UNTUK | lembar (None)`
  why: counting classifier, not a purpose-object.

- **S3122 [2]**  `malem (SARANA_RITUAL) | DIPULUNG | ditaruh (None)`
  why: "ditaruh" is a second coordinate verb, not a noun object.

- **S3134 [3]**  `lekesan (SARANA_RITUAL) | DIISI_DENGAN | ujung atas (None)`
  why: location, not a substance — duplicate/confused extraction.

## ADD  (missing triples the sentence supports)

- **S2748**  no ADD needed — see N6 note.
- **S2752**  `mendiang (dalam wujud sekah) | DIAJAK_BERKOMUNIKASI_OLEH | keluarga`
- **S2750**  `pitra mendiang | DIPERSILAKAN_MASUK_KE | (wujud/puspalingga)`
- **S2762**  `upanisad | TENTANG | jalan yang harus ditempuh`
- **S2777**  `bhatara | DIPENDAK_SECARA | khusus`
- **S2803**  `pawedan | JUGA_ADALAH | tempat ngajum serta mengutpeti sekah`
- **S2810**  `pawedan (tempat memuja) | BUKAN_SEKADAR | "madyapada"`
- **S2850**  `punia (besar-kecilnya) | SEPADAN_DENGAN | jenis yadnya dan martabat sang mayadnya`
- **S2869**  `pitara (menggunakan tirtha ening) | HINGGA_TAMPAK | bayangan nya`
- **S2951**  `suku tunggal abu (diarak mapradaksina) | MELAMBANGKAN | diresapkannya sinar suci hyang widhi`; `abu | BERUBAH_DARI | bekas benda badan linggasarira`; `abu | MENJADI | mahabutha yang suci`
- **S2977**  no ADD needed — reasonably complete.
- **S3007**  `pandita (selaku pemuka agama) | MEMAKLUMI | ketentuan punia yang demikian itu`
- **S3063**  `jenazah | DIBERSIHKAN_DARI | hal-hal yang lain`
- **S3078**  `jenazah (ditutup kain putih) | BERTUJUAN | agar tidak kelihatan sama sekali`
- **S3080**  `punjung | BERISI | nasi dengan lauknya`; `punjung | BERISI | kopi`; `punjung | BERISI | rokok`
- **S3110**  `daun intaran | DIGUNAKAN_SEBANYAK | 2 lembar`
- **S3118**  `daun dapdap (yang dihaluskan) | BERGUNA_SEBAGAI | sampo pencuci rambut (keramas) bagi jenazah`; `daun dapdap | DIGUNAKAN_SAAT | upacara nyiramang layon`
- **S3122**  `malem (setelah dipulung, minimal dua buah) | DITARUH_DI | atas takir`; `malem (di atas takir) | DIGUNAKAN_UNTUK | ditaruh pada kedua lubang kuping jenazah ketika upacara melelet`
- **S3141**  `kawangen | DIISI | 11 kepeng (ditaruh pada setiap persendian/buku-buku)`; `kawangen | DIISI | 25 kepeng untuk pebaktian jenazah (ditaruh di dada, seolah-olah dipegang oleh tangan jenazah)`
- **S3142**  `kwangen (setiap gulungan) | DIISI_DENGAN | uang kepeng`; `kwangen | DIISI_DENGAN | bawang putih sebagai lambang kuku (di ujungnya)`; `kwangen (dengan bawang putih ini) | DITARUH_DI | tiap-tiap jari tangan dan kaki jenazah`
- **S3153**  `sisig (di atas takir ini) | DIGUNAKAN_UNTUK | gosok gigi jenazah`
- **S3154**  `pecahan kaca | DITARUH_DI | kedua mata (jenazah)`; `pecahan besi baja | DITARUH_DI | gigi jenazah`

## NOTE

- **D1 (N1) regression check — S2649**: HOLDING (positive).
- **D1 regression check — S2872**: NOT HOLDING — same failure pattern flagged for S3155 (chunk 7).
- **D1-adjacent**: S2672, S2812[1], S2969, S2954 all show the pattern recurring; S2649, S2904 show it working.
- **D3 (N10) regression check** — S2635/S2780/S2843/S2986/S3063/S3153/S3154 recurring 2-4 member truncations beyond the named examples. Holds for short flat "A dan/atau B" lists (S2645, S2686, S2777[1], S2968).
- **N6 regression check — S2748 (REQUIRED)**: HOLDING/FIXED.
- **N6 regression check — S2794 (REQUIRED)**: HOLDING/FIXED. Both of Iteration 1's originally-flagged N6 cases confirmed fixed.
- **D7 (N3) regression check — S2843 (REQUIRED)**: NOT FIXED.
- **D7 regression check — S3080 (REQUIRED)**: NOT FIXED, clearest example — parser-level root cause.
- **D7 regression check — S2794 (REQUIRED, re-examined)**: on inspection this is NOT an N3 inversion — a plain relation-label mismatch. Flagging so the team can confirm whether S2794 was miscategorized in the original check list.
- **D7 regression check — S2885 (REQUIRED)**: PARTIAL — core giving relations correctly active-voice; one relation shows a related recipient/direction confusion, not strict passive-inversion.
- **D7 regression check — S2986 (REQUIRED)**: NOT FIXED.
- **D7-adjacent (outside required list)**: S2612 (chunk 5), S2752 — same family, suggesting N3/D7 is broad and entirely open, not isolated to the five named examples.
- **S2777/S2780[1]**: minor nits, no hard fix needed.

## Chunk stats
FIX: 39   DROP: 5   ADD: 21   sentences reviewed: 61

---

# Chunk 7 audit (S3155..S3812)

## FIX  (triple is salvageable — give the corrected triple)

- **S3155 [0]/[1]**  current: `anggapan | ADALAH | pisau khusus` / `arit gobed | ADALAH | sabit kecil`
  fix: add back the purpose clauses ("yang digunakan untuk memotong padi pada masa lalu" / "untuk memotong rumput")
  why: **D1 regression** — purpose oblique dropped in both.

- **S3165 [0]**  current: `anget-angetan | DIPERCIKKAN_PADA | hulu hati jenazah`
  fix: `anget-angetan | DISEMBURKAN_PADA | hulu hati jenazah`

- **S3165 [1]**  current: `anget-angetan | DIPERCIKKAN_PADA | upacara ngelelet`
  fix: drop, or `anget-angetan | DISEMBURKAN_SAAT | upacara ngelelet`

- **S3237 [0]**  current: `tembakau | JENIS_DARI | lekesan`
  fix: `lekesan | BERISI/TERMASUK | tembakau`
  why: direction/predicate reversed (D11-adjacent).

- **S3283 [0]**  current: `jenazah | BERASAL_DARI | tebenan`
  fix: `jenazah | DITARUH_DARI_ARAH | tebenan (barat)`

- **S3295 [0]**  current: `jenazah | LAINNYA | bale teben`
  fix: `jenazah | NAIK | bale (dari arah teben menuju luanan/hulu)`

- **S3330 [0]**  current: `krama | MENGHASILKAN | bale-bale tempat`
  fix: `krama (masyarakat banjar) | MEMBUAT | bale-bale tempat memandikan mayat`

- **S3340 [1]**  current: `tempat penusangan | ADALAH | nyiramang layon`
  fix: `tempat penusangan | DIGUNAKAN_UNTUK | nyiramang layon`

- **S3354 [0]**  current: `jenazah | MENUJU | pepaga/asagan`
  fix: `jenazah | NAIK_KE | pepaga/asagan`

- **S3446 [0]**  current: `jenazah | DIBERI | pakaian layak orang`
  fix: `jenazah | DIBERI | pakaian seperti layaknya orang masih hidup`

- **S3496 [1]**  current: `lekesan | DIBERSIHKAN_DENGAN | cara mengusap-usapkan tembakau pada bibir jenazah`
  fix: `jenazah (bibir) | DIBERSIHKAN_DENGAN | tembakau (diusapkan pada bibir)`

- **S3544 [0]**  current: `kawangen | MELAMBANGKAN | tanda doa restu`
  fix: `kawangen | MELAMBANGKAN | tanda doa restu agar perjalanan roh yang meninggal tidak mendapatkan halangan`

- **S3546 [1]/[2]**  current: `pabersihan hidup tangan jenazah/layon | DILETAKKAN_DI | dada` / `DITARUH_DENGAN | telapak tangan`
  fix: `tangan jenazah/layon | DILETAKKAN_DI | dada` / `tangan jenazah/layon | DITARUH_DENGAN | posisi telapak tangan ditumpuk (ditumpangkan)`
  why: **D9 subject-fusion bug** — a TAHAPAN_UPACARA phrase glued onto the real subject.

- **S3559 [0]**  current: `waja | LAINNYA | panca datu`
  fix: `waja | BAGIAN_DARI | panca datu`

- **S3584 [0]**  current: `pengerikan kuku mutlak | DILAKUKAN_SAAT | upacara`
  fix: `pengerikan kuku mutlak | DILAKUKAN_SAAT | upacara "melelet" (pabersihan mati)`

- **S3586 [0]**  current: `jenazah | DIKENAL_SEBAGAI | orang`
  fix: `jenazah | DIANGGAP_SEBAGAI | orang yang masih hidup`
  why: **this is the exact sentence flagged as a D1/N1 failure in Iteration 1 and it is still broken.**

- **S3589 [0]**  current: `arit gobed | ADALAH | simbol rare angon`
  fix: `arit gobed | ADALAH | simbol dari rare angon, yaitu lambang keperkasaan seorang laki-laki`

- **S3591 [0]**  current: `anggapan | ADALAH | simbol dewi sri`
  fix: `anggapan | ADALAH | simbol dewi sri, yaitu lambang kesuburan, agar wanita yang kelak numitis memiliki kesuburan untuk melahirkan`

- **S3623 [1]/[2]**  current: `jenazah | DIPAKAIKAN | pakaian` / `kain bawah`
  fix: add "(berwarna putih)" to both.

- **S3623 [6]**  current: `jenazah | BERWARNA | udeng laki-laki`
  fix: `udeng (untuk laki-laki) | BERWARNA | putih`
  why: nonsense triple, subject/object swapped/fused.

- **S3649 [0]**  current: `jenazah | BERBANTALKAN | kapuk`
  fix: `bantal kapuk | DIGANTI_DENGAN | bantal sesisir buah pisang kayu`

- **S3654 [0]/[2]**  current: `gegaleng | TERBUAT_DARI | uang kepeng` / `potongan-potongan dahan kayu dapdap`
  fix: add back the count (250 biji) and "yang dibungkus dengan kain putih".

- **S3656 [0]**  current: `gegaleng | ADALAH | pengganti bantal kapuk`
  fix: `gegaleng | ADALAH | pengganti bantal kapuk yang dipakai pada waktu pabersihan hidup`

- **S3694 [0]**  current: `atma | MENINGGAL | badan`
  fix: `atma | LEPAS_BEBAS_DARI | badan`
  why: nonsense triple, subject/predicate/object scrambled.

- **S3728 [0]**  current: `numitis | MEMPEROLEH | pujian keharuman`
  fix: `penggunaan wewangian | BERTUJUAN_AGAR | orang yang numitis memperoleh pujian keharuman dalam tingkah lakunya`

- **S3742 [0]**  current: `kesuna | BERMAKNA | orang`
  fix: `kesuna (bawang putih) | BERMAKNA | agar orang yang numitis kembali memiliki kuku-kuku yang indah dan putih bersih`

- **S3747/S3749/S3753 [0]**  current: `kawangen | DIISI_DENGAN | hulu hati` / `dada` / `kedua lutut kaki`
  fix: `kawangen | DILETAKKAN_DI | <same location>` (+ see ADD for the contents triple)
  why: **D8 (N4), confirmed still open exactly as flagged in Iteration 1**, all three instances.

- **S3783 [0]**  current: `tirtha | DIPERCIKKAN_PADA | badan`
  fix: `tirtha | DIPERCIKKAN_PADA | seluruh badan hingga ke kaki jenazah`

- **S3799 [1]**  current: `jenazah | DIISI_DENGAN | rurub sinom`
  fix: `kain (penutup jenazah) | DIISI/DILETAKKAN | rurub sinom sebanyak lima buah`
  why: wrong subject (D13-family).

- **S3811 [0]**  current: `rurub sinom | DITUJUKAN_UNTUK | jenazah`
  fix: `rurub sinom | DIAMBIL_DARI | gulungan jenazah (sebelum dimasukkan ke peti)`

## DROP  (triple should be removed)

- **S3334 [0]**  `kesembilan galar | DITARUH | bilah bambu`
  why: **D14 self-loop** — subject and object are the same referent.

- **S3733 [1]**  `kwangen jeriji | DITARUH | kawangen jeriji`
  why: **D14 self-loop**.

- **S3742 [1]**  `kesuna | MEMILIKI | kuku-kuku`
  why: wrong subject.

- **S3799 [2]**  `jenazah | DIISI_DENGAN | kain`
  why: redundant/garbled artifact.

## ADD  (missing triples the sentence supports)

- **S3294**  `jenazah | HARUS_MELALUI | ujung pepaga/asagan yang di teben (barat)` (+) `jenazah | DIMASUKKAN | kepala terlebih dahulu` (+) `kaki jenazah | BERSELONJOR_KE | teben/barat`
- **S3295**  `jenazah | BERGERAK_DARI | teben` (+) `jenazah | MENUJU | luanan (hulu)`
- **S3296**  `keluarga/masyarakat | DILARANG | tergesa-gesa memandikan jenazah`
- **S3330**  `bale-bale (tempat memandikan mayat) | DIKENAL_SEBAGAI | pepaga` (+) `bale-bale | DIKENAL_SEBAGAI | asagan`
- **S3332**  `pepaga | DIKENAL_SEBAGAI | bale penusangan (istilah Denpasar)` (+) `pepaga/asagan | ADALAH | semacam dipan atau bale darurat` (+) `pepaga/asagan | DIPERGUNAKAN_SEBAGAI | usungan` (+) `... | tandu`
- **S3339**  `jenazah | DIAMBIL_DARI | balai (tempat jenazah disemayamkan)` (+) `tempat persemayaman jenazah | DITEMPATKAN_DI | bale semanggen (rumah adat Bali)`
- **S3340**  `tempat penusangan | BERUPA | pepaga atau asagan`
- **S3354**  `jenazah | DIDUDUKKAN_DULU_SEBELUM | tidur tertelentang di pepaga/asagan`
- **S3363**  `kepala jenazah | DIALASI_DENGAN | bantal kapuk (bantal biasa)`
- **S3364**  `jenazah | HARUS_DIBIARKAN | sebentar (sebelum dibuka pakaiannya)` (+) `orang yang dituakan/lebih tua | MENCUCI | muka dan rambut jenazah`
- **S3468**  `jenazah | DIHIAS_SEOLAH-OLAH | pergi menghadiri undangan atau ke pura` — N10 check: 3-item list cincin/kalung/gelang fully captured, holding well.
- **S3547**  `tirtha | BERASAL_DARI | bhetara hyang guru` (+) `tirtha | DIMOHONKAN_DI | sanggah/pamerajan keluarga orang yang meninggal`
- **S3584**  `pengerikan kuku | TIDAK_BOLEH_DILAKUKAN_SAAT | pabersihan hidup`
- **S3604 / S3973**  `jempol jari tangan (kedua ibu jari) | DIIKAT_DENGAN | tali benang tukelan (benang tenun Bali) berwarna putih` (+) `jempol jari kaki | DIIKAT_DENGAN | tali benang tukelan` (S3604 only)
- **S3610**  `jenazah | DIBILAS_DENGAN | air` (+) `jenazah | DIKERINGKAN_DENGAN | kain kering`
- **S3651**  `dewa wishnu | MENDAPATKAN | tirtha amertha` (+) `dewa wishnu | TIDUR_DI | atas samudra (dialasi dan dipayungi naga/ular cobra berkepala banyak)`
- **S3653**  minor — add "untuk tidur" to the object.
- **S3656**  `gegaleng | DIKENAL_SEBAGAI | galeng pengerekan`
- **S3720**  `anget-angetan | BERMAKNA | agar orang yang meninggal dapat numitis lagi dan terhindar dari penyakit` (+) `... | agar orang tersebut memiliki budi pekerti dan pikiran baik, jernih, terlepas dari kebusukan`
- **S3734**  `kojong (kawangen jeriji) | BERISI | lima gulungan daun sirih (base)` (+) `gulungan daun sirih | DIIKAT_DENGAN | benang putih` (+) `gulungan sirih | DIMASUKKAN_KE | lubang uang kepeng`
- **S3756–S3758**  `logam campuran | BERADA_DI | tengah-tengah` — asymmetric gap in the otherwise-clean N11 manual-override set.
- **S3760**  `jarum (jaum) | DITARUH_DI | lengan jenazah` (+) `besi paku | DITARUH_DI | lengan jenazah`
- **S3783**  `priuk (tempat tirtha pangringkes) | DIPECAHKAN | [setelah tirtha dipercikkan]` (+) `priuk (yang pecah) | DIBUANG_DI | kolong bawah pepaga/asagan`
- **S3791**  `jenazah (setelah dibungkus tiga lapis) | DIIKAT_DENGAN | tali benang tukelan`
- **S3800**  `hiasan (rurub sinom) | DIJAHIT_DENGAN | daun kelapa muda (busung)`
- **S3812**  `rurub sinom | DILETAKKAN_DI | posisi kepala, leher, perut, paha, dan kaki (melintang), sama seperti penempatan sebelumnya di atas jenazah`

## NOTE

- **D1/D2 (N1) — verdict: PARTIAL, not consistently holding.** "berfungsi sebagai X" via decomposition works and is clean (S3647). Plain "ADALAH/BERMAKNA/BERARTI + generic noun + continuation" still broken across S3155[0,1], S3446, S3544, **S3586** (the exact Iteration-1-flagged sentence, still broken), S3589, S3591, S3653, S3656, S3720, S3728, S3742.
- **D3/D5 (N10) — verdict: HOLDING well in this chunk.** S3196 15-item list captured completely, S3468 3-item list complete. No truncated coordinate lists found in chunk 7.
- **D10 (S13) — verdict: HOLDING, no leak found.**
- **D8 (N4) — verdict: STILL OPEN, confirmed exactly as flagged.** S3747/S3749/S3753 all still mis-type. Related subject-fusion bug (D9) at S3546.
- **D9 (N7) — verdict: STILL PRESENT for the classic shape, but inconsistent.** S3604 and S3733 confirmed broken (plus a self-loop at S3733, see DROP). S3237/S3653 show a related-but-different flaw; S3760 shows the heading silently ignored rather than producing junk.
- **N11 — not applicable to this chunk** (S4300-S4305 are in chunk 8).

## Chunk stats
FIX: 36   DROP: 4   ADD: 30   sentences reviewed: 61

---

# Chunk 8 audit (S3816..S4340)

## FIX  (triple is salvageable — give the corrected triple)

- **S3836 [1]**  current: `bale-bale dipan | DIPAKAI_UNTUK | warung`
  fix: `bale-bale/dipan (dengan galar berketekan cawan) | DIPAKAI_UNTUK | dipan/plangkan di warung atau di dapur`
  why: **D4** — "dapur" dropped from a 2-item list.

- **S3843 [2]**  current: `galar | MEMBUAT_DENGAN | harapan (Place)`
  fix: `galar (dengan ketekan guling) | DIGUNAKAN_DENGAN_HARAPAN | membuat ngantuk dan tidur nyenyak`
  why: nonsense triple — "harapan" mistagged as object_type Place.

- **S3845 [0]**  current: `galar | MENGHASILKAN | keinginan`
  fix: `galar (dengan ketekan cekur) | MENGHASILKAN | keinginan untuk bertembang seperti makidung atau makekawin`
  why: **D2 truncation** — purpose clause dropped.

- **S3845 [1]**  current: `bale-bale | DILETAKKAN_DI | pura`
  fix: `bale-bale | DILETAKKAN_DI | pura atau merajan`
  why: **D4** — "merajan" dropped.

- **S3852 [1]**  current: `jumlah kelipatan 5 | ADALAH | misalnya 5 10`
  fix: `jumlah galar | CONTOH | 5, 10, 15, 20, 25, 30, dan seterusnya (kelipatan 5)`
  why: **D5** — numeric example series truncated after 2 of 6 values.

- **S3860 [0]**  current: `upacara mesulub | ADALAH | kepercayaan setempat`
  fix: `upacara mesulub | ADALAH | kepercayaan setempat (lokal) yang diwarisi turun-temurun sejak jaman dulu di daerah/desa setempat`

- **S3862 [0]**  current: `upacara mesulub | ADALAH | konsep satya`
  fix: `upacara mesulub | ADALAH | konsep "satya" atau kesetiaan`

- **S3909 [0]**  current: `jenazah | DIBAWA_KE | setra`
  fix: `jenazah | DIBAWA_KE | setra untuk segera dikuburkan (bukan diaben)`

- **S3914 [0]**  current: `jenazah | MEMILIKI | rangkaian upacara lain`
  fix: `jenazah | MENJALANI | rangkaian upacara lain sebelum dibawa ke setra (jika diaben)`

- **S3936 [0]**  current: `jenazah | DIBERI | pakaian layak orang`
  fix: `jenazah | DIBERI | pakaian seperti layaknya orang masih hidup`
  why: same truncation as chunk 7's S3446 (duplicate passage).

- **S3964 [0]**  current: `jenazah | DIMINUMKAN | [very long literal clause]`
  fix: split into three sub-triples (duplicate of chunk 7's S3547).
  why: **D15/D6-family** run-on literal.

- **S4074 [0]**  current: `tirtha ening | BERFUNGSI_SEBAGAI | symbol pikiran`
  fix: `tirtha ening | BERFUNGSI_SEBAGAI | symbol pikiran dan perasaan sang yajamana, agar roh/atman tidak mengalami kegoncangan dan dapat mencapai alam sorga dengan tenang`
  why: **D2** — object NP itself cut short AND the "sehingga"-chained consequence clause also dropped; contrast fully-retained S4116.

- **S4087 [0]**  current: `tirtha penembak | MEMILIKI | hubungan herat`
  fix: `tirtha penembak | MEMILIKI | hubungan erat dengan itihasa (Bisma Parwa, bagian dari Mahabharata)`
  why: confirms the MEMILIKI+dropped-"dengan X" sub-pattern (**D1**) extends beyond originally-flagged sentences.

- **S4090 [0]**  current: `arjuna | MENYUGUHKAN | air cara dengan cara memanah tanah yang berada disamping rsi bisma`
  fix: `arjuna | MEMANAH | tanah (di samping rsi bisma)`
  why: garbled duplicate phrase (**D12/D15-adjacent**).

- **S4096 [0]**  current: `tirtha | DIBAWA_KE | setra`
  fix: `tirtha | DIBAWA_KE | setra untuk dipergunakan pada waktu pembakaran`

- **S4106 [0]**  current: `tirtha ini | MEMILIKI | fungsi sarana`
  fix: `tirtha ini | MEMILIKI | fungsi sarana untuk mengucapkan permohonan pamit terhadap leluhur, agar dapat ikut masuk ke alam kedewataan`
  why: **D1 regression, one of the originally-flagged sentences — confirmed still broken.**

- **S4111 [0]**  current: `tirtha ini | MEMILIKI | fungsi sarana`
  fix: `tirtha ini | MEMILIKI | fungsi sarana yang dapat mengantarkan roh agar mendapatkan tempat yang baik, tidak mengalami kesengsaraan`
  why: same MEMILIKI-fungsi truncation, confirmed still broken (originally flagged).

- **S4121 [0]+[1]**  current: `tirtha pangentas | DIBUAT_DI | gria ida` (+) `... | sulinggih`
  fix: merge into `tirtha pangentas | DIBUAT_DI | gria ida sang sulinggih (kediaman/kertas pendeta)`

- **S4121 [2]**  current: `tirtha pangentas | DILAKSANAKAN | upacara pengabenan`
  fix: `tirtha pangentas | DIBUAT_SAAT | upacara pengaskaran (bertepatan dengan puncak upacara pengabenan)`

- **S4128 [0]**  current: `tirtha pangentas | MEMILIKI | fungsi utama`
  fix: `tirtha pangentas | MEMILIKI | fungsi utama sebagai sarana untuk "ngentas": memberikan jalan dan membersihkan noda-noda roh/atma agar dapat menuju alam kedewataan`
  why: same MEMILIKI-fungsi truncation, confirmed still broken.

- **S4128 [1]**  current: `tirtha pangentas | MEMBERIKAN | jalan`
  fix: add `tirtha pangentas | MEMBERSIHKAN | noda-noda para roh/atma orang yang meninggal`
  why: **D4** 2-verb coordination, only first survived.

- **S4169 [0]**  current: `tirtha pangentas | ADALAH | seuatu`
  fix (best-effort, source text itself looks disfluent): `tirtha pangentas | ADALAH | sesuatu yang memiliki arti (erat) dengan upacara pitra yadnya`

- **S4170 [0]**  current: `tirtha pangentas | ADALAH | tirtha yang diharapkan dan diyakini sebagai alat atau sarana sangat penting bagi umat hindu`
  fix: extend with "khususnya untuk melepaskan roh leluhur dari ikatan keduniawian, agar dapat meningkat menuju alam bhwah loka"
  why: **D1 regression, originally-flagged sentence — confirmed still broken.**

- **S4177 [1]**  current: `atma lingga | ADALAH | mewujudkan sanghyang ongkans`
  fix: `atma lingga | MEWUJUDKAN | sanghyang ongkara dan tri aksara dalam diri (yang berstana dalam bathin)`
  why: nonsense — ADALAH cannot take a verb phrase as complement.

- **S4192 [0]**  current: `tirtha pangentas | ADALAH | sesunguhnya tirtha gangga`
  fix: `tirtha pangentas | ADALAH | tirtha gangga yang diturunkan atau dibuat oleh pendeta/sang sulinggih`

- **S4212 [0]**  current: `abu abu kekototan | BERSINAR | matahari`
  fix: `badan | BERSINAR_BAGAIKAN | matahari`
  why: wrong subject — the ash *vanishes*, the body shines.

- **S4273 [0]**  current: `padang lepas | DIBAWA_KE | periuk`
  fix: `padang lepas | DIMASUKKAN_KE_DALAM | periuk`

- **S4336**  current: `tirtha pangentas | ADALAH | tirtha yang terpenting dalam upacara pengabenan`
  fix (or ADD): `pengabenan (tanpa tirtha pangentas) | DIANGGAP | belum dilaksanakan`

- **S4339 [0]**  current: `tirtha pangentas | ADALAH | lambang penunjuk jalan`
  fix: `tirtha pangentas | ADALAH | lambang penunjuk jalan bagi roh/atman untuk kembali ke asalnya (brahman/alam swah loka) sebagai tujuan terakhir`

## DROP  (triple should be removed)

- **S3836 [0]**  `bale-bale dipan | DIPAKAI_UNTUK | dipan`
  why: **D14-adjacent** circular/self-referential nonsense.

- **S4062 [3]**  `tirtha | DIPAKAI_UNTUK | lainnya`
  why: vacuous, "yang lainnya" is not a real referent.

- **S4273 [1]**  `padang lepas | DIMASUKAN | sarana-sarana yang lainnya`
  why: nonsense coordination bug — see ADD for the correctly-split individual triples.

## ADD  (missing triples the sentence supports)

- **S3816**  `bilahan-bilahan bambu (ante) | DIKENAL_SEBAGAI | galar`
- **S3904**  `masyarakat setempat | MELAKUKAN | upacara mesaji (atau memunjung), ketika jenazah masih di atas pepaga/asagan`
- **S4065**  `tirtha pabersihan | DIBUAT_OLEH | ida sang sulinggih` (+) `tirtha pabersihan | TIDAK_MEMAKAI | samsam (tidak seperti tirtha panglukatan)` (+) `tirtha pabersihan (periuknya) | TANPA | kalung benang dengan uang kepeng`
- **S4079**  `tirtha pemanah | DIBUAT_SAAT | upacara "pengaskaran"` (+) `tirtha-tirtha lain | DIBUAT_OLEH | ida sang sulinggih (langsung)`
- **S4090**  `air (dari tanah yang dipanah arjuna) | MENGENAI | bibir rsi bisma`
- **S4105 / S4110**  `sarana dan prasarana (upacara pemujaan) | BERUPA | pras, ajuman, daksina, suci, rayunan, (kadang-kadang) pajegan`
  why: **D5** — 6-item list dropped wholesale (not just truncated); contrast S4109 which works.
- **S4109**  *(no ADD needed, positive N10 control)*: all 4 coordinate members captured, alongside S4103 (2/2).
- **S4112**  `pura kahyangan tiga (tempat pemujaan pencipta) | BERFUNGSI_SEBAGAI | utpeti, sthiti, dan pralina`
  why: **D5** — same "sebagai X, Y dan Z" gap as S4105/S4110.
- **S4128**  `upacara pengabenan | ADALAH | upacara penyucian roh/atman (purusa) orang yang telah meninggal, agar terlepas dari ikatan panca mahabhuta, menuju alam dewa (swah loka)`
- **S4175**  `brahman | DITEMPATKAN | diri (sendiri)` (+) `upacara mapulang lingga | BERARTI | "ngelinggihang lingga" (dalam diri)`
  why: **D4** — 2-item coordinate subject, "brahman" dropped.
- **S4212**  `abu abu kekototan (kekotoran) | MUSNAH | [melalui ritual amrethi karana]` (+) `amrethi karana | DILAKUKAN_DENGAN | mengucurkan tirtha amertha dalam diri`
- **S4266**  `pramakusa | DIMANTRAI | (sebelum dimasukkan ke dalam priuk)`
- **S4273**  `jijih (biji padi) | DIMASUKKAN_KE_DALAM | periuk` (+) `pripih emas | ...` (+) `recadana | ...` (+) `ulantaga | ...` (+) `sarana-sarana tersebut | DIMANTRAI_OLEH | ida sang sulinggih (sebelum dimasukkan)`
  why: of a 5-item list only the closest conjunct got its own triple.
- **S4338**  `tirtha pangentas | MENGANGKAT_KEDUDUKAN | roh (dari preta menjadi pitara)` (+) `roh (pitara) | MEMASUKI | alam bwah loka (sebagai tumpuan menuju alam swah loka)`

## NOTE

- **D1 (N1) — verdict: PARTIAL, with a clean split by shape.** **FIXED**: S4077, S4086, S4126 (all "tirtha X ADALAH tirtha yang..." shape, fully retained). **STILL BROKEN**: S3586 (chunk 7), **S4106, S4111, S4128, S4170** (all "MEMILIKI fungsi/hubungan ... sebagai/dengan Y" shape — the exact originally-flagged sentences). New instance: S4087. Net: the fix patched the ADALAH-copula shape but not the MEMILIKI-fungsi/hubungan shape, exactly the gap anticipated. Further gap: `sehingga X` sibling-consequence clauses still dropped even when the object NP itself is retained — compare broken S4074 against fully-retained S4116/S4167/S4171.
- **D3/D5 (N10) — verdict: MIXED.** Large simple coordinate NPs governed directly by one verb work well (S4109 4/4, S4103 2/2). Two sub-patterns still lose members: short 2-item lists (S3836, S3845, S4175) and list-introducer shapes several hops below the main verb, dropped wholesale (S4105/S4110, S4112, S4273).
- **D10 (S13) — verdict: HOLDING, no leak found.**
- **D8 (N4) — verdict: not re-triggered in this chunk**, but the duplicate passage S4035 (=chunk 7's S3783) confirms the same gaps recur wherever this passage appears.
- **D9 (N7) — verdict: not clearly triggered in this chunk.** No classic heading-noun bug found; S3836's "cawan" heading has other problems but not that exact shape.
- **N11 — verdict: LANDED, clean.** S4300/S4301/S4303/S4304/S4305 all correct, complete, correctly asymmetric. No errors found — fully holding.

## Chunk stats
FIX: 30   DROP: 3   ADD: 15   sentences reviewed: 60
</content>

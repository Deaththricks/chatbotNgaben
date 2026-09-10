# Relation-Extraction Audit & Fix Loop â€” Runbook

*Last updated 2026-09-05. Keep this current at the end of every loop iteration.*

This file is the standing context for the iterative quality pass on the Ngaben pipeline's
relation-extraction output. Read this first when resuming; you should not need the user to
re-explain anything.

---

## 0. One-paragraph statement of the goal

`Knowledge Processing.ipynb` extracts `subject â€”[RELATION]â†’ object` triples from an
Indonesian/Balinese corpus about **Ngaben** (Balinese Hindu cremation). The rule-based extractor
is good but leaks a lot of wrong, half-wrong, and missing triples. We are running a
**fix â†’ the-user-reruns â†’ re-audit â†’ fix** loop until an audit pass turns up nothing but
subjective/trivial nits. "Best" means *the very best the current method (dependency-rule + copula
+ object-decomposition extraction) can produce* â€” not "best given the known bug list". Every loop
we raise the bar.

## 1. Who does what

| Step | Owner |
|---|---|
| Edit the notebook code (cell 51 etc.) | **me (Claude)** â€” never run the notebook |
| Run the notebook, regenerate `Results/Final/` | **the user** (Stanza dep; slow; not a quick re-run) |
| Parallel per-chunk audit of the fresh output | **me + 8 sub-agents** |
| Consolidate audit â†’ report â†’ get approval | **me** |
| Decide ADD appetite / disputed calls | **the user** |

Report-before-fix ([[feedback_report_before_fix]]) still applies for *new* systemic changes, but
within this loop the user has pre-approved: audit â†’ report â†’ implement without a second prompt,
*unless* a change is risky or reverses semantics â€” call those out and wait.

## 1b. Working principle â€” scour the whole project

Do not hesitate to read anything and everything in `C:\Misc\Work\AI_Chatbot\Graphing` to find or solve a problem.
The dependency parse, the NER output, the coreference output, the source corpus in `Data/`, the
dictionaries, the downstream `Neo4/` and `kb/` code and their reports, prior `.bak` notebooks,
`Example/`, `Next Step/`, `Knowledge graph/` â€” all of it is fair game. A wrong triple often has
its real cause upstream (a bad lemma, a mis-segmented sentence, an NER gap, a coref miss) or shows
up as a symptom downstream. Trace it to the root wherever the root lives; don't stop at cell 51's
boundary. Use sub-agents freely to fan out across the tree.

## 2. The loop, step by step

### 2a. AUDIT (after each notebook re-run)
1. `python scratchpad/build_bundles.py` â€” rebuilds `scratchpad/bundles/chunk_01..08.txt`.
   Each bundle groups, per sentence: `TEXT`, `NER` line, CoNLLU `PARSE`, and the extracted
   `RELATIONS` (indexed `[0]`,`[1]`,â€¦). It reads:
   - `Results/Final/relation_results_ngaben/relation_results_ngaben.json`
   - `Results/Final/dependency_results_ngaben/dependency_results_ngaben.conllu`
   - `Results/Final/ner_results_ngaben/hybrid_ner_results.txt`
   Chunking is 8 equal slices of the sentences-that-have-relations, in sentence order.
2. Dispatch **8 `general-purpose` sub-agents in parallel**, one per chunk. Each agent prompt:
   read `scratchpad/AUDIT_INSTRUCTIONS.md` (the rubric), read `flag.txt` (the 50 seed examples),
   read its `chunk_NN.txt`, audit every triple, write `scratchpad/reports/chunk_NN_report.md`
   in the fixed FIX / DROP / ADD / NOTE / stats format, and return it.
3. Consolidate all 8 into `relation_audit_report.md`:
   Â§1 numbers, Â§2 systemic defects ranked by impact (each with a cell-51 fix location),
   Â§3 resolution path, Â§4 the full per-chunk detail.
4. `SendUserFile` the report. Wait for "approve" (+ any ADD-appetite / disputed-call rulings).

### 2b. FIX
1. Back up the notebook: `Copy-Item "Knowledge Processing.ipynb" "Knowledge Processing.ipynb.bak_relfix_<UTCstamp>"`.
2. Edit cell 51 via a **patch script** (`scratchpad/patch_nb_relations.py` style): load the
   notebook JSON, string-replace within `nb["cells"][51]["source"]`, write back. Direct
   `NotebookEdit` also works but the cell is huge â€” the patch-script approach is safer and
   reviewable. (The Read tool cannot page a multi-MB `.ipynb`; use `scratchpad/nbgrep.py`
   â€” modes: `list`, `grep <re>`, `context <re> <n>`, `cell <i> <a> <b>` â€” to inspect.)
3. **Verify with a standalone harness before pushing** (mandatory, same as FIX #8/#24â€“27):
   exec the edited function defs from a scratch copy, feed hand-built token lists that match the
   real `.conllu` for every cited sentence ID, assert the corrected triple comes out; add
   **regression** cases from the KEEP set so nothing that was right breaks.
4. Update this runbook's Â§4 changelog + the report's status. Tell the user to re-run.

### 2c. Repeat 2aâ†’2b until convergence (see Â§5).

## 3. Key paths

| What | Path |
|---|---|
| Notebook | `C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb` â€” relation extraction is **cell 51**, save/writer is cell 53/54 |
| User's seed flags | `C:\Misc\Work\AI_Chatbot\Graphing\flag.txt` (50 examples + the audit instruction) |
| Consolidated audit report | `C:\Misc\Work\AI_Chatbot\Graphing\relation_audit_report.md` (regenerated each loop) |
| This runbook | `C:\Misc\Work\AI_Chatbot\Graphing\RELATION_AUDIT_RUNBOOK.md` |
| Extractor output | `Results/Final/relation_results_ngaben/` â€” `.json` (audit source), `.jsonl` (pretty, per [[feedback_jsonl_pretty_format]]), `.txt` |
| Bundle builder | `audit_tooling/build_bundles.py` â†’ `audit_tooling/bundles/` |
| Audit rubric for agents | `audit_tooling/AUDIT_INSTRUCTIONS.md` |
| Per-chunk agent reports | `audit_tooling/reports/chunk_NN_report.md` (overwritten each loop) |
| Notebook inspector | `audit_tooling/nbgrep.py` |
| Notebook backups | `Knowledge Processing.ipynb.bak_relfix_*` |

*All audit tooling lives in `C:\Misc\Work\AI_Chatbot\Graphing\audit_tooling\` so it persists across sessions.
`build_bundles.py` and `nbgrep.py` resolve paths relative to the repo root â€” just run them.*

## 4. Relation schema (current)

`sentence_id, context_sentence, subject, subject_label, relation, object, object_label,
object_type (ENTITY|LITERAL), source (dependency_rule | object_decomposition | manual_override)`.
`relation` is a canonical UPPER_SNAKE predicate. Design intent: **terse, readable** triples â€”
short objects with meaning preserved, natural everyday-Indonesian predicates (not schema jargon).

### Cell-51 map (section â†’ line ~offset in cell source, as of Iteration 1)
- 13.3b `is_negated` L61 Â· `_object_is_negated` L109 (AUDIT S1)
  Â· 13.3c/d `derive_raw_relation_label` L283 (marker-first, voice-aware cascade; `_SWAP_JENIS_DARI`
  sentinel for `termasuk` â€” AUDIT N6 â€” lives near the S15 berisi/diisi block)
- 13.4 `find_object_tokens` L853 Â· `find_coordinated_verb_relations` L1065
- 13.4b `_emit_relations_for_verb` L1114 (subject/object swap for N6 + the N1e verb-level
  purpose-clause fallback both live here) Â· `extract_subject_verb_relations` L1200
- 13.5 `expand_phrase` L1382 Â· `_strip_stray_ring_head` L1408 Â· `get_conjuncts` L1432
  (transitive walk, AUDIT N10)
- 13.5d object decomposition L1606 (`expand_object_with_clauses`, `DECOMPOSE_OBJECTS`,
  `GENERIC_CATEGORY_NOUNS` L1670, `_purpose_oblique_children` L1731 (AUDIT N1),
  `_clause_children` L1749, `decompose_object`, `resolve_object`)
- 13.5c `find_subject_clause_relations` L2000
- 13.6 `extract_definition_relations` L2151
- 13.8b `MANUAL_RELATION_OVERRIDES` L2528 â€” dict `{sentence_id: [ {subject, subject_label,
  relation, object, object_label, source:"manual_override"}, ... ]}`; **replaces** that
  sentence's auto relations entirely; flows through typing/taxonomy/dedup like any other.
  Carries S133, S1298, S3755-S3758 (Iteration 0) + S4300/S4301/S4303-S4305 (Iteration 1, AUDIT N11).
- 13.9 `lookup_entity_label` Â· 13.9e `classify_object_kind`
- 13.10 `RELATION_TAXONOMY` L2829 Â· 13.10c bare-function-word-object drop, `VERB_STUB_OBJECTS`,
  `_MENURUT_ATTRIBUTION_OBJECTS`, `_ATTRIBUTION_OBJECT_PATTERN` L2902 (AUDIT S13, widened
  Iteration 1) Â· 13.10b dedup

**Line numbers drift on every notebook edit** â€” re-derive with
`python audit_tooling\nbgrep.py grep "def derive_raw_relation_label|^MANUAL_RELATION_OVERRIDES|..."`
rather than trusting this table verbatim after future patches.

### Downstream to keep in sync after any predicate-vocab change
`Neo4/normalize.py` (`CANONICAL_RELATIONS`, `relation_map.json`), `kb/build_kb.py`
(`kb/relation_phrases.json`) â€” per [[project_neo4j_graph_cleanup]], [[project_ngaben_chatbot_kb]].

## 5. Definition of done (convergence)

Stop the loop when a full 8-chunk audit produces:
- **0** DROP-for-correctness (no triple asserts something false / opposite of its sentence),
- **0** nonsense objects (bare verbs, function words, mangled spans),
- **< ~15** FIX total, all of them subjective phrasing/nuance calls the user would shrug at,
- ADD list down to genuinely optional enrichment the user has explicitly de-scoped.
Record the final audit report + a short "converged" note here.

## 6. Changelog (append each iteration)

### Iteration 0 â€” 2026-09-04
- First full corpus audit (from `flag.txt`). `relation_audit_report.md` v1: ~324 FIX / ~102 DROP /
  ~340 ADD, 15 systemic defects. User approved implementing all of Â§2 + overrides.
- **Fixes landed in cell 51** (backup `Knowledge Processing.ipynb.bak_relfix_20260904_082244`,
  patch scripts `scratchpad/patch_nb_relations.py` + `fix_s4.py` + `fix_s9.py`, verified by
  `scratchpad/harness.py` 19/19 + `scratchpad/smoke.py` 0 errors over 7134 `derive_raw_relation_label`
  / 25653 `decompose_object` calls):
  - **S1** â€” `_object_is_negated()` (new, after `is_negated`); object-side negation
    (`tanpa`/`bukan dari`/`tidak`/`tan`â€¦) now drops the triple in all 3 emit paths
    (`_emit_relations_for_verb`, `extract_definition_relations`, `_subrelations_from_clause`).
  - **S2** â€” `derive_raw_relation_label`: passive `masuk`â†’`DIMASUKKAN_KE_DALAM`,
    `naik/unggah`â†’`DINAIKKAN_KE` (was `MENUJU`).
  - **S3** â€” `GENERIC_CATEGORY_NOUNS` set + `decompose_object` fallback: a bare 1-word generic
    category head (`upacara`/`tirtha`/`sarana`â€¦) whose relative clause produced no sub-relation
    keeps the clause on the object (typed LITERAL) instead of dropping it.
  - **S4** â€” `is_definition_predicate` surface denylist `_SHAPE_MEANING_NONCOPULA`
    (`berbentuk`/`berarti`/`bermakna`/`bernama`/`berupa`/`berwujud`/`berbadankan`/`menyerupai`)
    â†’ routed to the verb extractor (`BERBENTUK`/`BERARTI`â€¦), not `ADALAH`. `merupakan`/`ialah`/
    `adalah` untouched. Backstop: `VERB_STUB_OBJECTS` final filter drops any triple whose object
    is still a bare inflected verb.
  - **S8** â€” `sirat/percik/perci/sembur/ciprat` â†’ `DIPERCIKKAN_PADA` (holy-water-onto-target).
  - **S9** â€” `_SELF_RESTATE` final filter: drops `X MELAMBANGKAN lambang/simbol`, `X ADALAH hal`.
  - **S13** â€” `_MENURUT_ATTRIBUTION_OBJECTS` final filter: drops `X MENURUT tata cara/ahli/â€¦`.
  - **S15** â€” `isi`/`berisi`/`diisi` â†’ `BERISI` / `DIISI_DENGAN` (was `MEMILIKI`).
  - **Overrides:** `134`â†’`133` re-anchor (numbering had shifted; verified against `.conllu`);
    `1298: []` (misconception); `3755â€“3758` five-metals set (anaphora Stanza can't resolve).
- **Deferred to Iteration 1** (higher-risk / needs fresh output to tune): S5 Balinese offering-list
  retag (`ring`/`lan`/`saha` â†’ needs UPOS-level change in `LEMMA_CORRECTIONS`/a Balinese pre-pass),
  S6 subject/object span trim, S7 `DILAKUKAN_DI`-on-non-event-subject (needs subject_label plumbed
  into `derive_raw_relation_label`), S10 dropped coordinate members, S11 `termasuk` reversal,
  S12 general misconception/hypothetical detection, S14 heading-noun-as-subject, and the bulk of
  the per-sentence FIX/DROP/ADD in report Â§4.
- New raw predicates emitted (need adding to `Neo4/normalize.py` `CANONICAL_RELATIONS` +
  `relation_map.json`, and `kb/relation_phrases.json`): `DIMASUKKAN_KE_DALAM`, `DINAIKKAN_KE`,
  `DIPERCIKKAN_PADA`, `BERISI`, `DIISI_DENGAN`, `BERBENTUK`, `BERWUJUD`, `BERARTI` (some may already
  exist), plus override predicates `BERDEWA`, `BERWARNA`, `MENGANDUNG`, `BERADA_DI`.
- **Next: user re-runs the notebook â†’ Iteration 1 audit** (`build_bundles.py` â†’ 8 agents â†’ report).

### Iteration 1 audit â€” 2026-09-04
- User re-ran the notebook with Iteration 0's fixes: `Results/Final/` regenerated, corpus now
  777 triples / 489 sentences (was 792/496). 8-chunk audit rerun (`build_bundles.py` was already
  fresh from the re-run; 8 `general-purpose` agents dispatched, each also asked to flag Iteration 0
  regressions). `relation_audit_report.md` v2: **285 FIX / 89 DROP / ~415 ADD** (down from
  ~324/~102, up from ~340 respectively) â€” both FIX and DROP fell, confirming Iteration 0 landed.
- **Iteration 0 scorecard** (full detail in report Â§2): **S1** (object negation) and **S8**
  (sirat/percik) holding strong, each with 1-2 residual edge-case gaps. **S2** (masuk/naik not
  MENUJU) holding - MENUJU corpus-wide down to 3 - but doesn't cover active-intransitive `naik ke`.
  **S15** (berisi/diisi not MEMILIKI) holding wherever the trigger verb fires. **S4** and **S9**
  partial (narrower lemma coverage than needed). **S13** partial (the `menurut ahli` guard works,
  several attribution-adjunct shapes don't). **S3** (copula + generic-noun clause-stripping) is
  **NOT holding** - regressed in all 8 chunks, now the #1 open defect (~45 triples). Overrides
  (S133, S1298, S3755-S3758) all verified landed and clean.
- **New/re-ranked systemic defects for Iteration 2** (full detail + cell-51 locations in report
  Â§3): N1 copula/generic-noun clause-stripping (=S3, top priority), N2 `DILAKUKAN_DI` on non-event
  sarana (=v1 S7, still fully open), N3 benefactive/locative passives inverting subject/object
  (broader than v1 S5), N4 `DIISI_DI <body-part>` mis-typing + dropping contents, N5 bade/
  patulangan qualifier stripping, N6 `termasuk` direction (=v1 S11), N7 section-heading-as-subject
  (=v1 S14), N8 leading-adverb/trailing-clitic subject bleed, N9 `object_decomposition`
  over-firing on appositives, N10 coordinate-member loss (=v1 S10), N11 Kawi `sangkaning` split
  (S4303/S4304), N12 procedural under-extraction (ADD-appetite decision, not a bug).
- Resolution path for Iteration 2 (report Â§4): N1 first (highest leverage) -> plumb
  `subject_label` into `derive_raw_relation_label` (unblocks N2+N3) -> N10 (`get_conjuncts`,
  cheap) -> span-hygiene batch (N5/N7/N8/N9) -> S13 lemma-list extension -> N4 -> Balinese
  offering-list retag (still-deferred v1 S5) -> manual overrides (N11, S133 predicate underscore)
  -> ADD-appetite call on N12.
- Report sent to user via SendUserFile.
- **Fixes landed in cell 51** (backup `Knowledge Processing.ipynb.bak_relfix_20260904_215508`,
  patch script `audit_tooling/iteration_1/patch_iter1.py`, verified by `audit_tooling/harness.py`
  42/42 + `audit_tooling/smoke.py` 0 errors over 7134 `derive_raw_relation_label` / 25653
  `decompose_object` / 75339 `get_conjuncts` calls). For each: what the audit found, why it
  happened, what changed.
  - **N1 â€” copula/generic-noun clause-stripping (the #1 open defect).** *Found:* "tirtha
    BERPERAN_SEBAGAI sarana" (S1206), "ngaben ADALAH satu tahap" (S1610), "pitra yadnya ADALAH
    upacara keagamaan" (S797) all threw away the clause that carried the actual meaning. *Why:*
    Iteration 0's S3 fallback only fired when the ENTIRE object phrase was a single-word exact
    match against `GENERIC_CATEGORY_NOUNS` â€” a quantifier ("satu tahap") or a compound modifier
    ("upacara keagamaan") riding along in the rendered string silently blocked it every time; and
    the fallback only ever looked for `acl`/`acl:relcl`/`appos` children, never a purpose oblique
    ("untuk menetapkan...") attached either to the object noun or (S1206's case) to the *governing
    verb* as a sibling of the object. *Fix:* the fallback now checks the resolved **head token's
    lemma**, not the whole surface phrase (`decompose_object`); a new `_purpose_oblique_children()`
    picks up `advcl(untuk/agar/supaya)` and `nmod`/`obl(untuk/dari/bagi/terhadap/kepada/dengan)`
    children on the object head (`_clause_children`, `expand_object_with_clauses`); a further
    verb-level check in `_emit_relations_for_verb` (N1e) catches the sibling-xcomp case Stanza
    produces for "selaku"/"sebagai" (mistagged as VERB). `GENERIC_CATEGORY_NOUNS` also gained
    `pengabenan`/`penegasan`/`hubungan`/`fungsi`/`pertanda`/`ciri`, evidenced by the audit.
  - **N10 â€” `get_conjuncts` was single-hop.** *Found:* 3+-item coordinate lists ("sasih kasa,
    karo, dan katiga") kept only the first two members when later items chain `conj` to the
    *previous* conjunct rather than all attaching directly to the head. *Fix:* made transitive
    (recursive walk with a visited-set guard against parse cycles); smoke-tested over all 75339
    tokens, max chain length 19, zero errors.
  - **S13 â€” attribution-adjunct filter widened.** *Found:* the Iteration 0 filter only fired when
    the relation label had already come out literally `"MENURUT"` â€” but the same source/citation
    adjunct ("dalam lontar X", "sebagaimana disinggung/diuraikan/tertulis dalam...", "di mata umat
    hindu") was leaking through under `DIKENAL_SEBAGAI`, `TERTULIS`, `DISINGGUNG_DI`, `DIURAIKAN`,
    `DINILAI_DI` and others, because those are all *different verbs the parser happened to land
    on* governing the exact same kind of adjunct object. *Fix:* new `_ATTRIBUTION_OBJECT_PATTERN`
    regex matches on the **object's content**, independent of relation label.
  - **N6 â€” "X termasuk Y" direction reversed.** *Found:* "semua sekah termasuk sangge" (sangge is
    a *kind of* sekah) came out as `sekah BAGIAN_DARI sangge` â€” backwards, because `CLASSIFY_LEMMAS`
    routes every member including `termasuk` through the same subjectâ†’object direction that's
    correct for `golong`/`kategori`/`kelompok` but not for `termasuk`. *Fix:* `termasuk` now
    returns a `_SWAP_JENIS_DARI` sentinel that `_emit_relations_for_verb` swaps subject/object on
    (`sangge JENIS_DARI sekah`); scoped to the primary subject-verb extraction path only.
  - **N11 â€” Panca Maha Bhuta closing verse + S133 formatting.** *Found:* "teja sangkaning rupa
    mulih maring teja" (light is the origin of form; form returns to light) parses with "teja
    sangkaning" split off as if it were a compound name, producing nonsense (`teja sangkaning
    ADALAH mulih maring teja` / `LAINNYA`); the sibling verses S4300/S4301/S4305 carry the
    identical construction and were yielding **zero** relations. *Fix:* manual overrides for all
    five (`ganda/rasa/rupa/ambekan/sabda BERASAL_DARI <element>` + `KEMBALI_KE` where the source
    text states the "returns to" half â€” S4301's sentence is truncated before it, so only
    BERASAL_DARI is asserted there). Also: S133's override predicate `"tidak menjamin"` (literal
    space) â†’ `"tidak_menjamin"`, matching the corpus's uppercase-underscore convention once
    canonicalized.
- **Deferred to Iteration 2** (unchanged from the audit's own resolution path): N2/N3 (needs
  `subject_label` plumbed into `derive_raw_relation_label`), N4 (`DIISI_DI` two-triple split â€”
  spans two separate extraction paths), N5/N7/N8/N9 (span-hygiene batch), N12 (ADD-appetite
  decision), and the still-open Balinese offering-list retag (v1 S5, needs a UPOS-level
  `LEMMA_CORRECTIONS` pass).
- New/changed raw predicates this pass (need adding to `Neo4/normalize.py` `CANONICAL_RELATIONS` +
  `relation_map.json`, and `kb/relation_phrases.json`, alongside Iteration 0's still-pending list):
  `JENIS_DARI` (N6), `KEMBALI_KE` (N11; `BERASAL_DARI` already existed), `TIDAK_MENJAMIN` (S133,
  now canonical-cased).
- **Next: user re-runs the notebook â†’ Iteration 2 audit** (same loop: `build_bundles.py` â†’ 8
  agents â†’ report). Report-before-fix still applies for the *next* systemic batch; within this
  loop the user has pre-approved audit â†’ report â†’ implement without a second prompt, unless a
  change is risky or reverses semantics.

### Iteration 2 audit â€” 2026-09-05
- User re-ran the notebook with Iteration 1's fixes: `Results/Final/` regenerated, corpus now
  **784 triples / 487 sentences** (was 777/489). Audit dispatched over **4** `general-purpose`
  agents instead of 8 (user's explicit ask this round â€” "use only max 4 agents"), each covering two
  of `build_bundles.py`'s 8 chunk files (~122 sentences/agent) with no reduction in per-sentence
  scrutiny. Each agent was handed the Iteration 1 fix list (N1, N10, S13, N6, N11) plus the exact
  flagged sentence IDs to re-check, and spot-checked the still-open N3/N4/N7 defects.
  `relation_audit_report.md` v3: **253 FIX / 36 DROP / 171 ADD** (down from 285/89/~415) â€” DROP
  nearly halved, confirming Iteration 1 landed real quality gains; FIX fell more modestly because
  several Iteration 1 fixes only patched a narrow sub-shape and the same failure mode resurfaces
  under a different verb/clause type.
- **Iteration 1 scorecard** (full detail in report Â§2): **N11** (Panca Maha Bhuta overrides) fully
  landed and clean. **N6** (termasuk swap direction) holding on both originally-fixed sentences
  (S2748, S2794); a new narrower "wrong category anchor" bug found (S1493, S2065). **N1** PARTIAL â€”
  holds for plain `ADALAH + yang`-clause but **not** for `MEMILIKI`/`MEMPEROLEH`/`TERDIRI_DARI`-
  headed generic nouns (now the single largest recurring gap, includes the exact S4106/S4111/
  S4128/S4170 sentences Iteration 1 named), nor for `bahwa`-ccomp, `agar`-purpose, sibling
  `sehingga`-clauses, or nested `object_decomposition` children. **N10** PARTIAL â€” holds for flat
  object-side lists but subject-side coordinate/appositive NPs are now the dominant gap (S1439's
  7-way list reduced to 1!), plus plain 2-item lists outside BERUPA/TERDIRI_DARI (flag.txt's own
  S411/S413/S414 still broken after two iterations) and list-introducer shapes dropped wholesale.
  **S13** INCONSISTENT â€” holds in some chunks, leaks bare `dalam lontar X`, `tertulis dalam`,
  `di mata X`, and `sebagaimana halnya X` (S2542, the exact Iteration-1-flagged sentence) in others.
  **N3/N4/N5/N7/N8/N9** (deferred, unfixed) all confirmed still open as expected; N3 is now the
  clear #3 defect by volume (S3080 traced to a parser-level nsubj:pass mistagging).
- **New/re-ranked systemic defects for Iteration 3** (full detail + cell-51 hints in report Â§3,
  renamed D1-D16 to reflect the split): D1 MEMILIKI/MEMPEROLEH/TERDIRI_DARI clause-stripping (top
  priority, supersedes N1), D2 remaining N1 clause-attachment gaps (bahwa/agar/sehingga/recursive),
  D3 subject-side conjunct walk (supersedes N10's biggest remaining piece), D4 plain 2-item list
  truncation, D5 list-introducer shapes dropped wholesale, D6 "successful walk, garbled dump"
  artifact (new), D7 = N3, D8 = N4, D9 = N5/N7/N8/N9 + new temporal-oblique subject-fusion bug,
  D10 = S13 phrasing gap, D11 = N6 anchor bug, D12 duplication artifact (new), D13 wrong-subject-
  via-borrowed-embedded-clause (new, recurrence of flag.txt's #58b/c pattern, 4+ independent
  sentences), D14 self-loop nonsense triples (new), D15 undifferentiated giant-literal-object dump
  (new), D16 = N12 ADD-appetite (unchanged, still needs user's call).
- Resolution path for Iteration 3 (report Â§4): D1 first (highest leverage, verb-class-independent
  clause retention) -> D2 (remaining attachment shapes) -> D3 (subject-side conjunct walk) -> D4
  (2-item lists, use flag.txt's S411/S413/S414 as regression anchor) -> D5+D6+D15 together (shared
  root cause in list/decomposition rendering) -> D7/N3 (plumb subject_label, as already scoped in
  Iteration 1) -> D8/N4 (two-triple split) -> D9 (span-hygiene batch) -> D10/S13 (add 4 missed
  phrasings) -> D13 (general fix for the recurring wrong-subject bug) -> D14 (cheap self-loop
  filter) -> D11/D12 (narrow, opportunistic) -> D16/N12 (ADD-appetite call).
- Report sent to user via SendUserFile. **No fixes landed yet this session** â€” audit + report only,
  per the user's request to "do the audit" (with the reduced agent count); awaiting approval before
  implementing the Iteration 3 batch.

- **Iteration 2 fixes landed in cell 51** (backup `Knowledge Processing.ipynb.bak_relfix_20260905_211954`,
  patch scripts `audit_tooling/iteration_2/patch_iter2.py` + `patch_iter2_stage2.py` +
  `patch_iter2_stage3.py` + `patch_iter2_stage4.py` + `patch_iter2_stage5.py` â€” split into stages
  per defect group as the runbook's Â§2b allows, each anchor-guarded and syntax-checked before
  writing; `patch_iter2_stage5.py` is a harness-driven follow-up correction, not a separate defect.
  Verified by `audit_tooling/harness.py` **83/83** (42 carried over from Iterations 0/1, all still
  passing â€” no regressions â€” plus 41 new Iteration-2 cases) + `audit_tooling/smoke.py` **0 errors**
  over 7134 `derive_raw_relation_label` / 25653 `decompose_object` / `expand_subject_phrase` /
  `_compound_child_conjunct_phrases` / `find_subject_clause_relations` / 8504
  `find_coordinated_verb_relations` / 75339 `get_conjuncts` / `_normalize_for_self_loop` calls
  across every sentence in the corpus):
  - **D1 â€” MEMILIKI/MEMPEROLEH/TERDIRI_DARI clause-stripping.** *Found:* the Iteration 1 N1 fix's
    clause-retention fallback only fired when the object's resolved head **lemma** was in
    `GENERIC_CATEGORY_NOUNS`, and only ever looked one hop deep for `acl`/`acl:relcl`/`appos`/
    purpose-oblique children of that exact head token. Two distinct gaps: (a) many entries added to
    the set (e.g. `penegasan`, `kedudukan`) are derived nouns whose Stanza **lemma** strips back to
    the root (`tegas`, `duduk`) â€” the lemma-only check could never match their own **surface** form;
    (b) "MEMILIKI **fungsi SEBAGAI sarana** UNTUK menetapkan..." (S4106) attaches its defining
    `acl`/purpose-oblique clause to **"sarana"** â€” a `sebagai`-marked nmod **child** of the generic
    head "fungsi" â€” never to "fungsi" itself, so the one-hop scan found nothing regardless of the
    lemma/set question. *Fix:* new `_predicate_complement_child()` descends one hop into a
    `sebagai`/`selaku`-marked nmod child for its own defining clauses too, wired into
    `_clause_children()` (used by both `decompose_object()`'s sub-relation attempt and, after
    refactoring `expand_object_with_clauses()` to call the same shared helper instead of duplicating
    the scan inline, the final re-append fallback that actually produces the rendered object text);
    every `GENERIC_CATEGORY_NOUNS` gate (in `decompose_object()`, the verb-level N1e fallback in
    `_emit_relations_for_verb()`, and the new definition-path fallback below) now checks the token's
    surface text as well as its lemma. Set widened with `peran`, `makna`, `arti`, `nilai`, `tarif`,
    `simbol`, `symbol` (English-spelled loanword, S4074), `kedudukan`, `keinginan`, `alasan`,
    `syarat`, `kondisi`, `tanda`.
  - **D2 â€” remaining clause-attachment gaps.** *Found:* `_PURPOSE_ADVCL_MARKS` only recognized
    `untuk`/`agar`/`supaya`-marked `advcl` children â€” a `bahwa`-clause (S1429: "penegasan **secara
    formal BAHWA** yadnya sudah selesai") or a `sehingga`-consequence clause (S4074) carries the
    same defining content but wasn't covered by mark, and separately both cases plus S1136's
    `agar`-clause attach to the **governing verb** ("merupakan"/"berfungsi") as a sibling of the
    object rather than to the object noun â€” a shape only `_emit_relations_for_verb()`'s N1e fallback
    handled, and only for the non-copula path. *Fix:* `bahwa`/`sehingga` added to
    `_PURPOSE_ADVCL_MARKS`; N1e's gate relaxed to key off the object's own head lemma/text (not the
    fully-resolved phrase string) and to no longer require `not object_has_clause` (so an
    object-side clause AND a verb-side sibling clause can both be appended, S4074); a new,
    equivalent verb-level fallback added to `extract_definition_relations()` for the copula path
    (S1136, S1429 â€” both needed this, not the mark-widening alone, since the clause attaches to
    `predicate_token` not the object).
  - **D3 â€” subject-side coordinate NPs.** *Found:* `expand_phrase()`'s `collect_phrase_tokens()`
    deliberately never walks `conj` (by design, so a coordinate object still resolves as N separate
    relations via the caller's own `get_conjuncts()` loop) â€” but nothing ever gave the **subject**
    side an equivalent, so "abu tulang kepala, tangan, punggung, dada, bokong, paha **dan kaki**"
    (S1439, 7-way!) collapsed to just "abu tulang kepala". *Fix:* new `expand_subject_phrase()` â€”
    joins `get_conjuncts()`'s (already-transitive, Iteration 1) result into one coordinated phrase
    (not N relations, since subjects share one predicate/object across all members) â€” applied at
    both top-level entity subject-phrase construction sites
    (`extract_subject_verb_relations`/`extract_definition_relations`).
  - **D4 â€” compound-child conjunct truncation.** *Found:* flag.txt's own S411/S413/S414
    ("sasih **kasa dan kapitu**") â€” "kapitu" is `conj` of "kasa" (a **compound child** of "sasih"),
    not of "sasih" itself, so `get_conjuncts(sasih)` found nothing; still broken after two
    iterations. *Fix:* new `_compound_child_conjunct_phrases()` detects this one-hop-deeper shape
    and renders a substitute phrase per conjunct with the shared prefix intact ("sasih kasa" ->
    "sasih kapitu"), emitted as additional relations in `_emit_relations_for_verb()`'s object loop.
    Scoped to that one call site (the shape's origin); not yet applied to
    `extract_definition_relations`'s object loop â€” deferred, narrow.
  - **D7 (was N3) â€” benefactive-passive swap, narrow subset.** *Found:* "sulinggih... **DIHATURKAN**
    santapan istimewa" (S2843) backwards implies the priest is being offered up â€” the `-kan`
    benefactive/applicative voice promotes the recipient to subject, the bare (no case marker)
    object is the actual theme. *Fix:* new sentinel (`_SWAP_DIPERSEMBAHKAN_KEPADA`, mirroring N6's
    `_SWAP_JENIS_DARI`) fires only for `lemma in ("hatur", "suguh")` + passive + case-marker-free
    object + `-kan`/`-i` surface â€” **deliberately excludes** `taruh`/`beri`/`turun`/`buat`: those
    lemmas collide on the exact same root between genuinely benefactive forms and plain,
    correctly-subject-as-patient passives (`_passive_action_label`'s own header comment already
    documents this exact class of Stanza lemma collision), and blanket-swapping them without a real
    disambiguation signal (`subject_label` plumbing, still not done â€” this is the second iteration
    this exact deferral has been carried forward) risked corrupting already-correct triples. S3080
    handled instead as a targeted override (see below) since its root cause is a parser mistag
    (locative "di samping jenazah" tagged `nsubj:pass`), not this benefactive pattern at all. S2986
    and S2885 remain open (deferred â€” see below).
  - **D8 (was N4) â€” `DIISI_DI` locative/contents split.** *Found:* "**di hulu hati**, diisi sebuah
    kawangen **yang berisi** 9 biji uang kepeng..." (S3747/S3749/S3753) â€” the S15 rule
    (`isi`/`berisi`/`diisi` -> `DIISI_DENGAN`/`BERISI`) fired unconditionally on any object,
    including a **locative** oblique (where the kawangen is placed) as if it were the contents; the
    kawangen's own nested `acl:relcl` contents clause was never reached by any subject-clause branch
    at all. *Fix:* the S15 rule now checks the object's case marker â€” a `NOUN_LOC_MARKERS`-marked
    object routes to `DILETAKKAN_DI` instead; a new `find_subject_clause_relations()` branch for
    `isi`/`berisi`/`diisi` lemmas recovers the contents clause as a separate `BERISI` relation (one
    per conjunct, consistent with the corpus's existing multi-BERISI convention).
  - **D9 â€” span-hygiene batch.** *Found three distinct sub-patterns:* (a) "patulangan **YANG
    BERBENTUK** naga kahang dan gajah mina..." (S2055/S2056) â€” `is_definition_predicate()`
    deliberately excludes `_SHAPE_MEANING_NONCOPULA` surface forms (`berbentuk`/`berwujud`/etc., by
    design per Iteration 0's S4) so they route through the ordinary verb-label cascade instead of
    `ADALAH` â€” but that meant **no** subject-clause branch recognized them either, so the whole
    clause (including its 4-way conjunct list) was silently dropped; (b) "mendiang **SEMASA
    HIDUPNYA** punya kedudukan..." (S1738) / "mendiang **DI MASA HIDUPNYA** memegang jabatan..."
    (S1823) â€” a temporal-era `nmod` ("semasa X" / "di masa X") is clause-level time-framing, not
    part of the entity's identity, but `collect_phrase_tokens()` walks any `nmod` within distance 2
    unconditionally, fusing it into the subject as "mendiang hidup" / "mendiang masa hidup"; (c) a
    related but structurally different bug at S3546 (compound-**chain** fusion, not `nmod`) proved
    too risky to trim generally (would need a semantic body-part/ceremony-stage-noun dictionary to
    tell "pabersihan hidup" apart from a legitimate 4-deep compound like "abu tulang kepala") â€”
    handled as a targeted override instead. *Fix for (a):* new `find_subject_clause_relations()`
    branch for `_SHAPE_MEANING_NONCOPULA` surface forms, computing the label via the real
    `derive_raw_relation_label()` cascade (which already produces `BERBENTUK` etc. for these via its
    floor `voiced_surface_label()` fallback) rather than a hard-coded constant. *Fix for (b):*
    `collect_phrase_tokens()` now skips an `nmod` child whose case marker is `semasa` or whose lemma
    is `masa`. Section-heading-as-subject (v1 N7, S3604/S3733/S3973) remains **fully deferred** â€” no
    safe general dependency-based signal found to distinguish a mis-attached topic heading from a
    legitimate subject separated from its predicate by a comma; forcing a heuristic risked
    suppressing good extractions elsewhere.
  - **D10 (was S13) â€” attribution-phrasing gaps.** *Found:* `_ATTRIBUTION_OBJECT_PATTERN` required
    `di mata (umat|orang)` with the leading `di`, but that preposition is usually consumed into the
    relation label itself (e.g. `DINILAI_DI`) and never survives in the object string (S1226);
    required `dalam lontar` adjacently, missing an intervening quantifier ("tertulis dalam
    **beberapa** lontar", S972); a bare, unqualified `lontar` object (the citation's own surrounding
    context lost during decomposition, S283) matched nothing at all; "sebagaimana **halnya**
    pangabenan" (S2542) â€” the existing bare-discourse-connective check for "hal" only fired when
    every child was a generic filler pronoun, and "halnya pangabenan" carries real content
    ("pangabenan") as its compound child, so it never qualified. *Fix:* regex loosened to
    `mata (umat|orang)` (no leading `di`) and `dalam\s+(?:\w+\s+)?lontar`; new exact-match filter
    drops a bare `lontar` object outright; `_is_bare_discourse_connective()` now also returns True
    for `hal` governed by a `SIMILATIVE_CASE_MARKERS` case marker (`sebagaimana`/`seperti`/etc.)
    regardless of what content its own child carries.
  - **D13 â€” wrong-subject via borrowed embedded-clause, general fix + targeted overrides.**
    *Found:* "sesajen **DIHATURKAN** pada saat abu jenazah **DIHANYUTKAN** ke samudera" (S1187) /
    "**di kala** jenazah **DIANGKUT** ke setra..., lancingan kajang **DIJUNJUNG**..." (S1603) â€” the
    temporal clause's own verb gets attached as an `advcl` **sibling** of the main verb (rather than
    properly subordinated), with its real subject mis-attached to the temporal noun ("saat abu
    jenazah" / "kala jenazah") instead of to the verb itself â€” so `find_coordinated_verb_relations`'s
    `has_own_subject` guard reads False even though it isn't really a subject-less coordinate
    action, and the temporal clause's content gets wrongly extracted as if it shared the OUTER
    subject. This is the general mechanism behind flag.txt's original #58b/#58c
    (nganyut/abu) bug, confirmed recurring on fresh, previously-unflagged sentences. *Fix:* new
    `_obl_has_temporal_lemma()` check (added `kala` to `TEMPORAL_ADJUNCT_LEMMAS` alongside the
    existing `saat`/`waktu`/`ketika`) â€” `find_coordinated_verb_relations()` now skips an `advcl`
    sibling when either the outer verb or the sibling itself carries a genuine
    `pada saat X`/`di kala X` temporal-framing oblique. S1889 and S3283 (same wrong-subject bug
    family, per the audit) had no equally clean general signal found in the time available â€”
    handled as targeted overrides instead of risking a broader, less-certain rule.
  - **D14 â€” self-loop final filter.** *Found:* "kwangen jeriji DITARUH **kawangen jeriji**" (S3733)
    â€” the existing exact-match self-loop guards (at each extraction call site) don't catch spelling
    variants. *Fix:* new final-pass filter (`_normalize_for_self_loop()`, alongside the other
    13.10c backstops) with a small spelling-variant map (`kwangen`->`kawangen`) for the handful this
    corpus uses interchangeably. S3334 (`galar`/`bilah bambu` â€” an apposition, not a spelling
    variant, so unreachable by string normalization) handled as a targeted override instead.
  - **Targeted `MANUAL_RELATION_OVERRIDES` additions** (5 new sentence IDs, each noted above with
    why a general rule wasn't attempted): **1889** (`pabersihan DILAKUKAN dua atau tiga hari sebelum
    ngaben` â€” D13), **3283** (`[]`, a genuine open question about a debated convention, not a
    stated fact â€” D13), **3080** (`punjung DITARUHKAN_DI_SAMPING jenazah` + 3x `BERISI` for its
    contents â€” D7/D13, parser mistag), **3546** (3 relations recovering the tangan/dada placement
    and the kawangen's symbolism â€” D9), **3334** (`[]`, apposition self-loop too densely embedded to
    safely reconstruct â€” D14).

### Iteration 3, Stages 1-3 landed â€” 2026-09-06

Full 100%-coverage manual audit completed this session in `flag.txt` (805 triples / 484 sentences
â€” user hand-audited S46-S1477, Claude continued S1482-S4340 via 3 parallel forks), then planned
(2 research passes: headless-execution feasibility + a spot-checked technical design) and
implemented in one large fork session. Plan file:
`C:\Users\ASUS TUF\.claude\plans\i-want-you-to-frolicking-bachman.md`. Backup:
`Knowledge Processing.ipynb.bak_relfix_20260906_222448`. Patch scripts in
`audit_tooling/iteration_3/` (`patch_stage1.py`, `patch_stage1_extra.py`, `patch_stage2.py`,
`patch_stage3.py`). Verified: harness **112/112** (99 carried forward from Iterations 0-2, all
still passing â€” zero regressions â€” + 13 new for Stage 1 + 8 for Stage 2 + 6 for Stage 3), smoke
**0 errors** over the same call volumes as before (7134 `derive_raw_relation_label` / 25653
`decompose_object` / 75339 `get_conjuncts` / 8504 `find_coordinated_verb_relations` / 25653
`find_subject_clause_relations`).

**Stage 1 (cheap, independent fixes):**
- **1a â€” berwujud/melambangkan lemma confusion.** *Found:* `derive_raw_relation_label`'s active-
  voice MELAMBANGKAN lemma set included `"wujud"` (berwujud's lemma) alongside `"lambang"`, wrongly
  conflating "takes the physical form of" with "symbolizes" (S1688, S2180). *Fix:* removed `"wujud"`
  from that set â€” `berwujud` now falls through to the (already-correct) `voiced_surface_label()`
  floor, giving `BERWUJUD`.
- **1b â€” LAINNYA vacuous label.** *Found:* `voiced_surface_label()`'s own last-resort fallback (no
  recoverable voicing prefix on the verb) was shipping the literal string `"LAINNYA"` as a real
  relation label in the output (10+ named instances: S1523, S1629, S1850, S2269, S2340, S2810,
  S3295, S3330, S3651, S3742). *Fix:* new final-pass filter dropping any relation whose label is
  exactly `LAINNYA`, same philosophy as the existing `VERB_STUB_OBJECTS`/`FUNCTION_WORD_OBJECTS`
  backstops (drop rather than guess). Several LAINNYA sentences need a *replacement* fact, not just
  a drop â€” flagged for the Stage 9/10 override batch, not done here.
- **1c â€” sequence/temporal case marker (`/121`) as a bare relation label, two shapes.** *Found:*
  (a) `derive_raw_relation_label` step 2 REPLACED the whole predicate with `SETELAH`/`MENJELANG`
  whenever the object carried that case marker, discarding the real verb ("sekah kangsen
  **dibongkar** SETELAH pamralina" shipped as bare `SETELAH`, S1747/S2028/S2166/S2642); (b) a
  *different* shape â€” the verb token itself is literally `menjelang` ("**menjelang** dan sampai
  dengan hari pabersihan, naga banda diletakkan...", S2028/S2166) â€” was being picked up by
  `find_coordinated_verb_relations()` as a spurious independent coordinate-action sibling of the
  real root verb. *Fix (a):* split `derive_raw_relation_label` into a thin wrapper (computes the
  case-marker suffix) + `_derive_raw_relation_label_core` (the original cascade, now suffix-unaware)
  â€” suffix combines onto the real base label (`DIBONGKAR_SETELAH`, not bare `SETELAH`); falls back
  to the bare marker only when the base label is itself unrecoverable (`LAINNYA` or a sentinel).
  *Fix (b):* `find_coordinated_verb_relations()` now also excludes a sibling `advcl` whose own verb
  lemma is itself a sequence/temporal marker word, mirroring the existing temporal-oblique exclusion
  (D13) for the "marker word IS the verb" shape rather than "marker word heads an oblique child".
  *Known limitation, not a regression:* S2642 specifically still ships bare `SETELAH` â€” Stanza's own
  lemmatizer failed to strip the `di-` prefix for that one token (`lemma == surface == "dibongkar"`),
  so the pre-existing `voiced_surface_label()` safety net (`lemma == surface -> LAINNYA`) fires for
  an unrelated upstream reason; the wrapper correctly degrades to the bare suffix rather than
  emitting a bogus `LAINNYA_SETELAH`. Flagged as a possible future lemmatization-quirk defect, out
  of scope for this pass.
- **1d â€” "termasuk" swap over-firing (S3237).** *Found:* the N6/Iteration-1 swap (`lemma ==
  "termasuk"` unconditionally returns the `_SWAP_JENIS_DARI` sentinel) correctly handles the
  membership sense ("**semua** sekah termasuk sangge" â€” sangge is a *kind of* sekah) but wrongly
  reverses the plain containment sense too ("lekesan termasuk tembakau" = lekesan *contains*
  tobacco, not "tobacco is a kind of lekesan"). *Fix:* new `_subject_has_totality_quantifier()` +
  `_find_verb_subject()` (which falls back to the verb's *head's* subject when `termasuk` itself has
  no `nsubj` child â€” the common shape when it hangs as an `advcl`/`ccomp` off the real root verb,
  confirmed against S2748/S2794's real parses) â€” the swap now fires only when the subject carries a
  totality quantifier (`semua`/`segala`/`setiap`/`seluruh`); otherwise routes to a new `BERISI`
  label instead. Verified against real tokens: S2748/S2794 (swap targets) still swap; S3237 no
  longer does.
- **1e â€” `FUNCTION_WORD_OBJECTS` manual-override exemption (confirmed root cause of a "missing"
  Iteration-2 fix).** *Found:* this filter (meant to catch bare-fragment auto-extracted objects like
  "X DILETAKKAN_DI atas") applies unconditionally to *every* relation including
  `manual_override`-sourced ones â€” S3758's `logam campuran BERADA_DI tengah` override (correctly
  present in `MANUAL_RELATION_OVERRIDES` since Iteration 2) was being silently dropped because
  `"tengah"` is in the stopword list. *Fix:* exempt `source == "manual_override"` relations from
  this filter â€” they're hand-curated, not raw fragments. **1f** (add the missing row) turned out to
  be a no-op on inspection â€” the row was never missing, 1e is what makes it actually surface.
- **1g â€” two raw-source typos**, confirmed by direct inspection (not extraction bugs): `Data\
  ngaben-merge-cleaned.txt` line 3783 near S4169 (missing word â€” inserted "erat": "...arti yang
  **erat** dengan upacara..."), line 3789 near S4177 (doubled "adalah adalah" â€” removed the
  duplicate).

**Stage 2 â€” D4 (plain coordinate-member truncation), still open per fresh flag.txt evidence.**
Investigation with real tokens found the fresh failures were **not** the "wire into more functions"
gap the original plan guessed (`_compound_child_conjunct_phrases()` was already correctly wired
into `_emit_relations_for_verb`) â€” two different, narrower, previously-unidentified gaps:
- **Fix A â€” compound chain was only walked one hop deep.** *Found:* "arang pembakaran **jaja uli**
  ATAU **jaja gina**" (S3153) needs *three* compound hops (arang -> pembakaran -> jaja[uli] -conj->
  jaja[gina]); `_compound_child_conjunct_phrases()` only checked immediate children of the object
  head. *Fix:* widened to a transitive BFS walk of the whole compound/flat/flat:name chain (same
  spirit as `get_conjuncts()`'s own Iteration-1 N10 transitive fix), stopping at the first node with
  a conjunct. *Known minor wording artifact:* at 3-hop depth the text-substitution can trail
  oddly ("jaja **gina uli**" instead of a cleaner "jaja uli dan jaja gina") â€” the missing fact is
  correctly recovered, just not optimally phrased; not pursued further this pass.
- **Fix B â€” a second, structurally different shape.** *Found:* "di **warung** ATAU(PUN) di
  **dapur**" (S3836), "di **pura** ATAU di **merajan**" (S3845) â€” because the second alternative
  carries its own case marker, Stanza attaches it as an `nmod` of the first noun rather than a
  `conj`, invisible to `get_conjuncts()`. *Fix:* new narrow helper `_nmod_cc_conjunct_phrases()` â€”
  fires only when an `nmod` child has *both* its own `case` child *and* its own `cc` child (both
  signals required, to avoid over-firing on ordinary nmod modifiers) â€” wired into
  `_emit_relations_for_verb` alongside Fix A's existing loop.
- *Investigated and deliberately excluded* (confirmed via real tokens, not the shape D4 targets):
  S2374/S2455/S2566/S2419/S4175 are D1/D2/D9/D3-family clause-retention or terseness issues, not
  coordinate-member loss. S3063's "maupun dari hal-hal yang lain" is a badly garbled parse (the
  second alternative attaches 4 levels deep inside an unrelated nested relative clause) â€” not a safe
  general-rule target, left for a Stage 9 manual override.

**Stage 3 â€” D1/D2 clause-retention generalization.** The plan's own S32/S61 citations were
**stale** (pulled from the older pre-fix `relation_audit_report.md` rather than the current
`flag.txt`) â€” both confirmed already correct in the actual current output and not mentioned in
`flag.txt` at all; no fix needed. Three genuinely still-open flag.txt-confirmed targets, each far
simpler to fix than originally scoped by reusing/widening existing narrow mechanisms rather than
inventing new relation-splitting logic:
- **3b â€” subject-side purpose-oblique (S2124).** *Found:* "swadharma beliau **UNTUK** mamari-suddha
  (menyucikan) dunia ini, merupakan fungsi pokok" â€” the object-side purpose-oblique mechanism
  (`_purpose_oblique_children`, Iteration 1's N1) has no subject-side equivalent, so the clause
  (which *is* the sentence's actual point) was silently dropped, leaving content-free "X ADALAH
  fungsi pokok". *Fix:* new branch in `find_subject_clause_relations()`, scoped conservatively to
  `"untuk"`-marked children only (not the full purpose-oblique marker set, since this is new code on
  the subject side rather than a widening of an already-proven mechanism) â€” emits a separate
  `BERTUJUAN_UNTUK` relation.
- **3c â€” "antara X dengan Y" attachment (S1782).** *Found:* "upacara timbang terima ... **ANTARA**
  mendiang ... **DENGAN** keluarga..." â€” the object head's nmod child carrying `antara` wasn't
  recognized by `_purpose_oblique_children()` at all. *Fix:* added `"antara"` to
  `_PURPOSE_OBLIQUE_CASE_MARKS` â€” reuses the *existing* glue-onto-object fallback (no new relation
  type needed), verified: "upacara timbang" -> "upacara timbang, antara mendiang yang akan pergi ke
  dunia lain dengan keluarga (terutama anak-anak) yang masih hidup".
- **3d â€” bahwa-ccomp on the copula root (S2055, one of Iteration 2's own original D2 targets,
  confirmed still broken).** *Found:* "patulangan ... ADALAH pertanda **BAHWA** mereka
  **MERUPAKAN** keturunan..." â€” "merupakan" attaches via `ccomp`, not `advcl`;
  `_purpose_oblique_children()`'s advcl branch never even looked at `ccomp`. *Fix:* widened the
  deprel check to `("advcl", "ccomp")`. Verified: "pertanda" -> "pertanda bahwa mereka merupakan
  keturunan dari orang yang condong pada paksa wesnawa" â€” exactly the flag.txt-requested fix.
- 3a (S32/S61) needed no change (already fixed); 3e (S2198[3], recursive decomposition) deferred to
  after Stage 4 lands, per the plan â€” **not yet re-checked, since Stage 4 itself was deferred this
  pass** (see below).

**Stage 4 (D5/D6/D15, shared root cause) â€” investigated, deliberately DEFERRED, no code changed.**
This is the highest-risk stage in the plan and the directive explicitly permits narrowing/deferring
rather than forcing a fix through. Root cause is real and was traced precisely for the flagship case
(S1963[4], "pering ... DILAKUKAN_DI sajen **surya** UNTUK **surya**, penebusan, pamerasan, banten
teben dan sebagainya" â€” the duplicated "surya"): `_purpose_oblique_children()`'s nmod/obl branch
finds a clause child that `expand_phrase()` may have **already** included once in `base_phrase`
(ordinary `nmod` children are walked by `expand_phrase`, unlike the `acl`/`acl:relcl`/`appos`
children the clause-glue mechanism was originally designed to recover) â€” then
`expand_object_with_clauses()`'s glue loop appends that same node's full subtree *again* via
`render_subtree_text()`, which also doesn't reformat a coordinate list into readable prose, just
dumps it in token-id order. A safe fix requires either (a) detecting and de-duplicating the overlap
between `base_phrase` and each `clause_text` before appending, or (b) splitting a clause_root with
its own `get_conjuncts()` into separate relations instead of one glued string â€” but
`expand_object_with_clauses`/`decompose_object`'s glue-fallback path is shared by **every** relation
in the corpus (called from the same code path S1782/S2055's Stage-3 fixes above also depend on), so
either change needs full-corpus regression testing this session's remaining time budget didn't
support doing safely. Left as a clearly-scoped starting point for a dedicated future pass: **D5**
(wholesale list-drop: S344, S4105/S4110/S4112/S4273, S3852[1]), **D6** (garbled-dump: S1963[4]),
**D15** (giant undifferentiated object: S2604, S3001, S4090, S3547/S3964 duplicate passage) all
still open, unchanged from the Iteration 2 audit.

**New/changed raw predicates this pass** (need adding to `Neo4/normalize.py`'s
`CANONICAL_RELATIONS`/`relation_map.json` and `kb/relation_phrases.json`, alongside the still-
pending lists from Iterations 0-2 â€” not yet verified as synced): `BERISI` (already existed, now also
reachable via the narrowed `termasuk` non-swap path), `BERTUJUAN_UNTUK` (already existed, now also
emitted from the subject side), plus every `<VERB>_SETELAH`/`<VERB>_SESUDAH`/`<VERB>_SELAIN`/
`<VERB>_MENJELANG` suffix-combination Stage 1c's wrapper can now produce (open-ended by design, not
a fixed new list â€” same pattern as the existing `<VERB>_DENGAN`/`<VERB>_DI` suffix combinators).

### Iteration 3, Stages 4-7 landed â€” 2026-09-06 (second wave, same day)

Continuation of the wave above, after an interim interruption (a dedicated Stage-4-only attempt hit
the account's spend limit mid-implementation, before any code change â€” verified safe, see the plan
file's progress log). This wave: re-attempted Stage 4, then did Stages 5, 6, 7 in full; Stage 8 was
investigated and deliberately deferred (see below). Backups (chronological):
`Knowledge Processing.ipynb.bak_relfix_20260906_154336` (Stage 4), `..._154605` (Stage 5a),
`..._154831` (Stage 5b), `..._155005`/`..._155056` (Stage 6, two sub-patches), `..._155307`/
`..._155402` (Stage 7, relocated a function for testability). Patch scripts in
`audit_tooling/iteration_3/` (`patch_stage4.py`, `patch_stage5a.py`, `patch_stage5b.py`,
`patch_stage6.py`, `patch_stage6b.py`, `patch_stage7.py`, `patch_stage7b.py`). Verified: harness
**138/138** (all prior cases still passing â€” zero regressions â€” + 26 new this wave), smoke **0
errors**, same call volumes as before.

**Stage 4 (D6 portion landed; D5/D15 still deferred).** Root cause was already precisely traced by
the interrupted attempt (see the earlier Stage-4 entry above) â€” `_purpose_oblique_children()`'s
nmod/obl branch can find a clause child `expand_phrase()` already walked into `base_phrase`, then
`expand_object_with_clauses()`'s glue loop appends that same node's subtree *again* via
`render_subtree_text()` (which also doesn't reformat a coordinate list, just dumps it in token-id
order). *Fix:* track which token ids `base_phrase` already covers (`collect_phrase_tokens`); when a
clause child's id is already covered, don't re-glue it â€” instead, if it has coordinate siblings
(`get_conjuncts`), surface only those (the genuinely new content) as a joined list, stripping each
conjunct's own leading punctuation before joining (a second, smaller fix â€” the first version left a
"X, , Y" double-comma artifact). Verified against real tokens: S1963[4] went from
`"sajen surya , penebusan , pamerasan , banten teben dan sebagai nya"` (duplicated "surya", garbled)
to `"sajen surya penebusan, pamerasan, banten teben, dan sebagai nya"` (no duplication, all 4
conjunct siblings present, only a minor missing-comma-before-the-list artifact â€” same class of
"known minor wording artifact, not pursued further" as Stage 2's own precedent). *Investigated and
confirmed NOT the same shape:* D5's flagship case (S344, ~14-item `berupa X, Y, Z...` list) is
structurally different â€” multiple semicolon-separated coordinate clauses nested inside each other,
not a simple base_phrase/clause-child overlap â€” this fix does not reach it. **D5 (wholesale
list-introducer drop: S344, S4105/S4110/S4112/S4273, S3852[1]) and D15 (giant undifferentiated
object: S2604, S3001, S4090, S3547/S3964) remain open**, need their own dedicated investigation, not
covered by this fix despite sharing the same *filed defect number* as D6.

**Stage 5 â€” D9 remainder.**
- *Bade/patulangan tier-count stripping (S2000-S2002).* *Found:* "bade YANG BERTINGKAT 11" attaches
  `bertingkat` as `acl`/`acl:relcl` on the subject head (confirmed via real tokens, with a `nummod`
  child carrying the number) â€” but no branch in `find_subject_clause_relations` recognized lemma
  `tingkat`, so the whole clause was silently dropped (`object_candidates` stayed `None`). *Fix:* new
  branch emitting a `MEMILIKI_TINGKAT` relation with the nummod child as object. Verified: S2000 â†’
  `bade MEMILIKI_TINGKAT 11`, S2001 â†’ `sembilan`, S2002 â†’ `tujuh`.
- *Section-heading-as-subject (S3604/S3733/S3973/S3760).* Re-checked after Stage 1c per the plan â€”
  confirmed **still open**: the parser attaches a heading-style noun ("itik-itik,", "kwangen
  jeriji:") as `nsubj:pass` of an unrelated following clause's verb; Stage 1c improves the *label*
  quality (bare `SETELAH` â†’ `DIKERIK_SETELAH`-style suffix) but doesn't fix the underlying wrong
  *subject*. Iteration 2 already found no safe general signal here and a second look this pass
  agreed â€” converted to targeted `MANUAL_RELATION_OVERRIDES` using flag.txt's own confirmed content:
  S3604 (2 rows, thumb+toe thread-tying), S3973 (1 row, thumb only â€” no "begitu juga" toe clause in
  this sentence), S3733 (2 rows, the two already-good placement facts reconstructed, replacing all
  three auto relations so the junk `SETELAH` one can't resurface), S3760 (2 rows, needle+nail
  placement â€” an N12-class near-total under-extraction, done opportunistically alongside this).

**Stage 6 â€” D7 remainder, narrower than the plan scoped it, but covers more.** *Found:* `dibuat`
(plain passive, "X is made") and `dibuatkan` (benefactive passive, "X is made FOR someone") share
lemma `buat` and were both routed to `DIHASILKAN`/`MENGHASILKAN`, wrongly implying the
deceased/recipient *produces* the thing made for them. Two distinct signals confirmed against real
tokens, not one: (a) S2612's verb is literally `dibuatkan` (a `-kan` suffix on the surface form);
(b) S2986[1]'s verb is `dibuat` (no suffix) but carries its own `"bagi"`-marked oblique child
("dibuat ... **bagi**-nya") â€” the plan assumed both were the same `-kan`-suffix shape, they aren't.
*Fix:* `_passive_action_label` now takes `surface` and a computed `benefactive` flag (true when the
verb has a `bagi`-cased `obl` child); either signal alone routes to a new `DIBUATKAN_UNTUK` label
instead of `DIHASILKAN`. Verified: S2612 â†’ `DIBUATKAN_UNTUK`, S2986[1] â†’ `DIBUATKAN_UNTUK`;
regression-checked a genuine plain `membuat` (S3330, active voice, no benefactive signal) still
returns `MENGHASILKAN`, not swept in. **Descopes the previously-deferred full `subject_label`
plumbing for this narrow class**, as the plan anticipated. S2986[2]/[3] (wrong subject â€” "masing-
masing untuk bhatara dan bhatari" describes which *offering* goes to which deity, not that pitra
itself is directed at them) and S2885[2] remain genuinely distinct low-count misparses, left for a
future manual-override pass, not attempted here.

**Stage 7 â€” D12 duplication artifact.** *Found:* a short phrase (1-4 words) gets glued to itself
across a `dari`/`untuk`/`bagi` marker during span reconstruction â€” confirmed 7 real instances across
2 sub-shapes: the general reconstruction bug (S44 "jenazah utuh...jenazah utuh", S785 "umat
hindu...umat hindu", S1982 "sawa...sawa", S3004 "ketulus-ikhlasan hati pihak...(repeated)") and a
narrower "X adalah simbol dari Y, yaitu Z" construction (S3589 "rare angon...rare angon", S3591
"dewi sri...dewi sri", S4074 "pikiran...pikiran") â€” confirmed to share the exact same underlying
shape (marker-bounded exact-phrase repeat), not two separate bugs as first suspected. *Fix:* a
narrow post-processing regex (`_dedupe_repeated_phrase_fragment`, exact backreference match only,
1-4 word phrases) applied to every relation's final subject/object text, placed after extraction â€”
deliberately does not touch `collect_phrase_tokens`'s nmod walk (load-bearing elsewhere). Function
definition relocated to before the RUN EXTRACTION cut so it's directly unit-testable (the
extraction-time application loop stays where the bug's context lives, in the 13.10a filter block).
Verified against all 7 real strings + 2 negative regression cases (legitimate short repeats that
must NOT collapse: "kaki jenazah dan kaki lembu", "upacara untuk keluarga besar dan ... kecil").
S2623 ("sajen kecil dengan tirtha dan sajen kecil...") was investigated and found to be a *different*
shape (the repeated phrase has intervening content between the marker and the duplicate, not
matching the narrow regex by design) â€” not covered, left open.

**Stage 8 â€” D11 anchor bug: investigated, deliberately deferred (not the fix location the plan
assumed).** *Found:* `_find_verb_subject()` (S3237's Stage-1d fix) is called *only* from
`_subject_has_totality_quantifier()` â€” i.e. it only gates whether the `termasuk` swap fires at all,
it is **not** the code that builds the actual category-anchor object in the emitted relation. The
real anchor-selection logic lives elsewhere (not yet located this pass). S1493 has a clean candidate
signal (its root verb is passive with an "oleh"-marked agent oblique â€” `standar kedudukan seseorang
di masyarakat` â€” that should outrank the plain `nsubj:pass` `manah` as the anchor) but implementing
it correctly requires first finding where the anchor is actually assembled, which this pass's
remaining time didn't cover. S2065 remains genuinely ambiguous (flag.txt's own audit already called
it "low confidence either way, leave as a known-weak instance") â€” not attempted. **Both S1493 and
S2065 still open**, unchanged from the Iteration 2 audit.

**New/changed raw predicates this wave** (add to `Neo4/normalize.py`'s `CANONICAL_RELATIONS`/
`relation_map.json` and `kb/relation_phrases.json`, alongside the still-unverified pending list from
every prior iteration): `MEMILIKI_TINGKAT` (Stage 5), `DIBUATKAN_UNTUK` (Stage 6). Stage 7 (D12)
introduces no new predicate â€” it only edits existing subject/object text.

**Not yet done this session:** Stage 9 (the ~110+ flag.txt exact-triple overrides + drop list) and
Stage 10 (D16/N12 full procedural coverage, user-approved) were **not attempted** â€” the user asked
to wrap up the code-fix stages and run the notebook once, then review before deciding next steps,
rather than continuing straight through to the large manual-override volume. D5/D15 (Stage 4
remainder) and D11 (Stage 8) also remain open per above.

**Next: the notebook gets run once** (headless execution, confirmed feasible earlier this session â€”
`pip install nbconvert` already done) to regenerate `Results/Final/` against everything landed in
Stages 1-3 + 4(partial)-7. The user will review the result and decide the next step (Stage 9/10,
another fix round, or something else) rather than the loop auto-continuing into a fresh audit pass
this time.

### Iteration 3, Stage 9 partial (batches 1-2) landed â€” 2026-09-07

User changed course after the above: rather than running the notebook on just Stages 1-7, decided
to push through Stage 9/10 first (full flag.txt coverage) and run the notebook once at the very
end. This entry covers the first two of several planned batches.

**Infrastructure**: `MANUAL_RELATION_ADDITIONS` dict added (cell 51, ~L3692, right after the
existing `MANUAL_RELATION_OVERRIDES` merge block) â€” additive (appends to a sentence's existing
auto-extracted relations) rather than replace-style, for pure-ADD flag.txt entries where the
existing relations are already correct. Wired in with the same `sentence_id`-stamping pattern as
`MANUAL_RELATION_OVERRIDES`; dedup (13.10b) runs after both, so no duplicate-relation risk.

**Batch 1 (flag.txt S46-S1477, the user's original free-text section)**: 53 sentences in
`MANUAL_RELATION_OVERRIDES` (FIX/DROP, including the bulk drop list: 540/541/559/560/591/616/618/
631/641/679), 11 sentences in `MANUAL_RELATION_ADDITIONS`. Covers every entry in this section â€”
S46's split, S58's abu/nganyut subject fix, S219/S270/S271/S344/S399/S400/S809's splits, S738/S801/
S1016/S1122/S1136/S1169/S1253/S1328/S1430/S1452/S1456/S1461/S1474/S1477's fixes, and more.
**Bug caught and fixed during this batch**: the first patch script used `json.dumps()` to serialize
Python `None` values, which emits JSON's `null` instead of Python's `None` â€” silent `NameError` at
exec time, not a syntax error (`ast.parse` doesn't catch it). Caught by `harness.py`'s exec-based
verification (not by `verify_nb.py`'s syntax-only check) exactly as the process is designed to
catch this class of bug. Fixed with a corrective pass (`fix_null_bug.py`) that replaced the 116
occurrences; harness back to 138/138 after.

**Batch 2 (flag.txt continuation, partial: S1482-S2166 of the S1482-S2363 range)**: 38 sentences in
`MANUAL_RELATION_OVERRIDES`, 30 in `MANUAL_RELATION_ADDITIONS`. Cross-checked against Stages 1-8
before transcribing â€” skipped entries already resolved generally: S1688 (berwujud/melambangkan,
Stage 1a), S1699/S1738-subject (D3, already converged), S1747/S2028 (temporal-marker suffix, Stage
1c â€” though both still needed a *separate* ADD for content the marker fix doesn't restore), S1782
(antara-clause, Stage 3c), S1963[4] (D6 dump bug, Stage 4), S1982/S2623-partial (D12, Stage 7),
S2000-S2002 tier (Stage 5 â€” but S2000's raja-bali/gelgel-klungkung sub-issue and S2002's dropped
clause still needed their own entries), S2055 (bahwa-ccomp, Stage 3d), S2124 (purpose-oblique,
Stage 3b). **Verified**: harness 138/138 (no new assertions added yet â€” data-entry volume this
large wasn't individually harness-tested per-entry, per the plan's own "representative sample, not
one-per-override" guidance; a handful of spot-checks recommended before the notebook run), smoke 0
errors, `verify_nb.py` clean (cell 51 now 3993+ lines after batch 1, more after batch 2).

**Not yet covered**: the remainder of S1482-S2363 (roughly S2166-S2363, ~15-20 sentences), and all
of S2364-S3332 and S3333-S4340 (the two other continuation parts, ~200+ more entries combined),
plus Stage 10's full procedural-coverage ADD pass (not started). Backup:
`Knowledge Processing.ipynb.bak_relfix_20260906_235945` (taken before this session's batches).

**Next**: further Stage 9 batches (S2166 onward through S4340) and Stage 10, then the single
notebook run, per the user's explicit "finish everything, run once" instruction.

### Iteration 3, Stage 9 region B (S2166-S3332) landed â€” 2026-09-07

Covers the tail of flag.txt's "Part 1" continuation (S2166-S2363) plus all of "Part 2"
(S2364-S3332, the range flagged as densest under-extraction territory). Backup:
`Knowledge Processing.ipynb.bak_relfix_20260907_001501` (taken before this batch).

**Landed**: 43 sentences in `MANUAL_RELATION_OVERRIDES` (FIX/DROP â€” including S2750's pure drop),
26 sentences in `MANUAL_RELATION_ADDITIONS`. Cross-checked against Stages 1-8 first â€” skipped
entries already resolved generally: S2180 (berwujud/melambangkan, Stage 1a), S2612[0]/S2986[1]
(dibuat/dibuatkan, Stage 6), S3004[1] (D12 dedup regex, Stage 7), S3153[0] (D4 compound-chain fix,
Stage 2), S3237 (termasuk-swap narrowing, Stage 1d â€” now correctly routes to `BERISI`), and pure
`/1`-confirmed-good sentences with no accompanying ADD (S2449, S2480, S2489, S2558, S2619, S2620,
S2635, S2645, S2649, S2686, S2748, S2787, S2843, S2904, S2968, S2977, S3080, S3196, S3221).

**Bug caught and fixed during this batch, before it ever reached harness/smoke**: the first patch
script used two textually-identical marker comments (`# --- Iteration 3 Stage 9 batch 2 (flag.txt
S1482-S2166) ---`) as insertion anchors for *both* `MANUAL_RELATION_OVERRIDES` and
`MANUAL_RELATION_ADDITIONS` â€” Python's `str.replace(..., 1)` found the first (OVERRIDES-side)
occurrence both times, so the entire ADDITIONS batch landed inside `MANUAL_RELATION_OVERRIDES`
instead, and â€” worse â€” sentence 3330 ended up as a **duplicate dict key** within the same literal
(Python silently keeps only the last value for a duplicate key), which would have silently
discarded the S3330 FIX in favor of the S3330 ADD-only content. Caught by manually verifying entry
placement with a targeted regex check (`sid in MANUAL_RELATION_OVERRIDES` vs. `...ADDITIONS`) after
noticing the region-B marker text appeared twice in the file â€” not caught by `harness.py`/
`smoke.py`, since both dicts still parsed as syntactically valid Python either way and no existing
test case happened to touch S3330 or the reassigned sentences. **Fixed** by reverting to the
pre-batch backup and re-patching with each dict's insertion anchored on its own unique tail content
(the literal text of each dict's last existing entry) rather than a shared comment string. Verified
correct post-fix: every intended sentence_id confirmed present in the right dict via direct text
search, no duplicate keys, harness 138/138 (unchanged â€” this batch's entries are new data, not new
assertions, consistent with the plan's "representative sample, not one-per-override" guidance),
smoke 0 errors. **Lesson for future batches**: never reuse the same literal marker/anchor string for
insertions into two different dicts in one patch script, even if it seems convenient â€” always anchor
on content unique to the specific dict being edited, and spot-check entry *placement* (which dict a
sentence_id landed in), not just that the file still parses.

**Explicitly deferred within this range** (too little confidence to safely reconstruct a full
`MANUAL_RELATION_OVERRIDES` replacement without risking deletion of a sibling relation whose exact
original text wasn't available â€” see the general principle below): S2166, S2198 (nested
decomposition, already known still-open), S2234, S2337, S2758, S2762[2] (partial â€” the ADD-only
part *was* captured), S2780, S2803[dropping the good [0]/[1] wasn't attempted, only the ADD landed],
S2810[1] preservation, S2869[0] preservation, S2872 (D1/D2, confirmed still open, no safe
reconstruction), S2885, S2914, S2923 (minor), S2947, S2986[2]/[3] (the D7-adjacent subject_label gap
â€” confirmed still open exactly as the last audit flagged), S3091, S3122[2] (the nonsense "ditaruh"
relation â€” ADD-only content for this sentence landed, the bad relation itself wasn't removed),
S3133[1], S3155 (D1/D2, confirmed still open), S3195. **General principle applied**: when flag.txt
says "some relations are fine, one is wrong" but the exact text of the "fine" ones isn't in hand,
default to leaving the sentence alone (or ADD-only) rather than risking an `OVERRIDES` replacement
that silently deletes correct content it can't faithfully reproduce.

**New predicates introduced this batch** (add to `Neo4/normalize.py`/`relation_map.json`/
`kb/relation_phrases.json` alongside every prior iteration's still-unverified pending list):
`TERGOLONG_BERSAMA`, `DIJADIKAN`, `DIKELILINGI_OLEH`, `MENGHATURKAN`, `MEMPEROLEH` (already existed),
`BERTUJUAN_MENYUCIKAN`, `DIBONGKAR_SETELAH`, `BARU_LEPAS_PERTALIAN_DENGAN`, `DIPERSILAKAN_MASUK_KE`,
`DITURUNKAN_DARI`, `JENIS_DARI` (already existed), `DIMASUKKAN_MELALUI`, `KALAH_MERIAH_DIBANDING`,
`DIMOHONKAN_AGAR_MENUJU`, `MENINGKAT_KEDUDUKAN_MENJADI`, `LAHIR_ATAS`, `DAPAT_SELESAI_SECARA`,
`DIBERSIHKAN_DARI`, `DIGUNAKAN_SEBANYAK`, `DITABURKAN_DI`, `DISEMBURKAN_PADA`, `DISEMBURKAN_SAAT`,
`TERTANAM_TITIP_DI`, `TERGOLONG`, `TELAH_SELESAI_SECARA`, `BERSEMAYAM_DI`, `BERBEDA_DENGAN`,
`DIHIAS_PALING`, `JUGA_ADALAH`, `BUKAN_SEKADAR`, `SEPADAN_DENGAN`, `HINGGA_TAMPAK`, `BERUBAH_DARI`,
`MEMAKLUMI`, `BERGUNA_SEBAGAI`, `HARUS_MELALUI`, `BERSELONJOR_KE`, `DILARANG`.

**Not yet covered**: all of S3333-S4340 (the third continuation part, ~200 entries), plus Stage 10's
remaining full procedural-coverage ADD pass beyond what this batch's ADDITIONS already captured for
its own range.

**Next**: Stage 9/10 for S3333-S4340, then the single notebook run, per the user's "finish
everything, run once" instruction.

### Iteration 3, Stage 9 region C (S3333-S4340) landed â€” 2026-09-07

Final flag.txt region â€” **flag.txt is now fully covered end-to-end across all four Stage 9+10
batches** (S46-S1477 batch 1, S1482-S2166 batch 2, S2166-S3332 region B, S3333-S4340 region C).
Backup: `Knowledge Processing.ipynb.bak_relfix_20260907_002632` (taken before this batch).

**Landed**: 46 sentences in `MANUAL_RELATION_OVERRIDES` (FIX/DROP), 22 sentences in
`MANUAL_RELATION_ADDITIONS`. Cross-checked against Stages 1-8 first â€” skipped entries already
resolved generally: S3589/S3591/S4074 (D12 dedup regex, Stage 7 â€” confirmed by the flag.txt entry
itself naming the exact same repeated-phrase shape Stage 7 targets), S3604/S3733/S3973/S3760
(section-heading-as-subject overrides already added in Stage 5, not Stage 9), S3758 (Stage 1e's
`FUNCTION_WORD_OBJECTS` manual-override exemption already makes the existing S3758 override
surface correctly). S4300/S4301/S4303-S4305 (Panca Maha Bhuta closing verses) confirmed still clean
per flag.txt's own "positive confirmations" note â€” untouched.

**Duplicate-passage sentences handled with matching content**: S3446/S3936 (same "pakaian layak
orang" passage), S3547/S3964 (same D15 tirta-percikan dump), S3783/S4035 (same D15
tirta-pot-breaking dump â€” S4035's current extraction was directly readable in
`relation_results_ngaben.txt`, giving high confidence for S3783's near-identical text), S4105/S4110
(same "sarana dan prasarana berupa..." 6-item list-drop).

**D15 (still open per Stage 4, S344/S4105/S4110/S4112/S4273/S3547-family) partially worked around
via targeted overrides** for this batch's specific instances (S3547/S3964, S3783/S4035,
S4105/S4110) rather than waiting for a general fix â€” same "override what a deferred general fix
would otherwise leave broken" pattern used elsewhere this iteration.

**Deferred within this range** (insufficient confidence in the exact current text of "the other
relations that are fine" to safely reconstruct a full `MANUAL_RELATION_OVERRIDES` replacement
without risking silent deletion of correct content â€” same general principle applied in region B):
S3623 (multi-relation sentence, several distinct sub-issues, only partial current-text visibility),
S3654, S3720 (ADD landed, FIX of the base relation not attempted), S3800, S3812, S3860, S3862.

**New predicates introduced this batch**: `DIUSUNG_KE`, `NAIK_KE`, `DIPERCIKI_DAN_DIMINUMKAN`,
`DIDUDUKKAN_DULU_SEBELUM`, `HARUS_DIBIARKAN`, `MENCUCI`, `DIALASI_DENGAN` (already existed),
`DIHIAS_SEOLAH_OLAH`, `DIANGGAP_SEBAGAI`, `BAGIAN_DARI` (already existed), `DIGANTI_DENGAN` (already
existed), `TIDUR_DI`, `BERMAKNA` (already existed), `LEPAS_BEBAS_DARI`, `BERTUJUAN_AGAR`,
`MENYEBABKAN`, `DIISI_DENGAN` (already existed), `DIAMBIL_DARI`, `DIPECAHKAN`, `DIBUANG_DI`,
`DIPAKAI_UNTUK` (already existed), `DIGUNAKAN_DENGAN_HARAPAN`, `CONTOH`, `MENJALANI`,
`DIKENAL_SEBAGAI` (already existed), `MELAKUKAN` (already existed), `DIMANTRAI`, `DIMANTRAI_OLEH`,
`MEWUJUDKAN` (already existed), `BERSINAR_BAGAIKAN`, `MUSNAH`, `DILAKUKAN_DENGAN` (already existed),
`TIDAK_MEMAKAI`, `TANPA`, `DIMOHONKAN_OLEH`, `BERUPA` (already existed), `DIANGGAP`.

**Predicate-vocabulary sync (Neo4/normalize.py, kb/relation_phrases.json, and the still-pending
lists from Iterations 0-2 and this iteration's earlier Stages/batches): NOT ATTEMPTED this pass.**
`Neo4/normalize.py`'s `CANONICAL_RELATIONS` set already has an open-tail `VOICED_PREDICATE` regex
(`^(DI|TER|ME|MEM|MEN|MENG|MENY|BER)[A-Z]{2,}(_(DENGAN|DI|KE|PADA|DARI|UNTUK|SEBAGAI|OLEH))?$`) that
auto-accepts most well-formed voiced-verb predicates without needing an explicit listing â€” so most
new predicates from this whole iteration likely already pass through cleanly. But active-voice
predicates that don't start with those prefixes (e.g. `NAIK_KE`, `CONTOH`, `TANPA`) will NOT match
and will show up in `normalize.py`'s own "5c. STILL-UNMAPPED RELATIONS" review log rather than fail
outright â€” not a blocker for running normalize.py, just a report-quality gap. Given the volume (four
Iteration-3 changelog entries' worth of new predicates, plus the never-verified Iterations 0-2
pending lists), a rushed sync risked more error than value within this pass's remaining scope â€” left
for a dedicated pass. **Concrete next step**: run `python Neo4/normalize.py` once after the notebook
re-run and read its own "STILL-UNMAPPED RELATIONS" report section â€” it will name exactly which
predicates need adding, more reliably than manually cross-referencing four changelog entries.

**Verification**: `verify_nb.py` syntax clean (cell 51 now 4691 lines), harness **138/138** (no
regressions; this batch's ~68 sentences are data entries, not new assertions, consistent with the
established "representative sample, not one-per-override" approach), smoke **0 errors**, same call
volumes as every prior check this iteration.

**flag.txt coverage status: COMPLETE.** All four Stage 9+10 batches together span S46-S4340 with no
gaps in the ranges attempted (a small number of individual sentences within each range were
deliberately left un-overridden per the "don't risk deleting unseen-but-correct content" principle
â€” see each batch's "deferred" list â€” these remain genuinely open, not silently skipped).

**Next**: the single notebook run (headless, `nbconvert` already installed, feasibility confirmed
earlier this session) to regenerate `Results/Final/` against the full Iteration 3 batch (Stages
1-8 + all Stage 9/10 overrides/additions). Per the user's explicit instruction, no further
iteration/audit loop after that run â€” the user reviews and decides next steps themselves.

### 2026-09-07 â€” misc

- **NER speed fix landed** (not a relation-extraction change): `dictionary_ner()` (NER cell, index
  31) was rebuilding + recompiling a regex per `(sentence x 11,709 gazetteer entries)` pair â€” the
  general-NER pass alone was ~33-50 min. Patched to compile all patterns once
  (`compiled_dictionary`) before the sentence loop. Verified byte-identical output vs. the old code
  on real gazetteer + samples. Backup `Knowledge Processing.ipynb.bak_nerperf_20260907_074315`.
  Cuts the general-NER pass to ~5-7 min. Bigger win (n-gram set lookup, ~100x) left as a backlog
  note. See memory `[[project-dictionary-ner-perf]]`.
- **"/009" = the deferred-override cleanup.** The ~28 sentences the Stage 9 region B/C batches
  deliberately left un-overridden (each batch's "Deferred within this range" list above) are now a
  named recurring task the user will trigger with "/009" / "Order #009". Needs a fresh notebook run
  first (so the current triples are visible), then write proper `MANUAL_RELATION_OVERRIDES` entries
  = verbatim good triples + the flag.txt fix. See memory
  `[[feedback-order-009-deferred-override-cleanup]]`.

### 2026-09-07 â€” /009 executed + perf batch 2 (one combined notebook edit)

Iteration 3 was run once (`Results/Final/` regenerated 09:53, 918 relations). Then a single edit
landed three things; backup `Knowledge Processing.ipynb.bak_009_perf2_20260907_102336`; patch
scripts `audit_tooling/iteration_3/patch_009.py`, `audit_tooling/perf_2/patch_lookup_entity_label.py`,
`audit_tooling/perf_2/patch_stanza_batch.py`; `verify_nb` OK, harness **138/138**, smoke **0 errors**.

- **/009 â€” 27 `MANUAL_RELATION_OVERRIDES` entries** (S2166, S2198, S2234, S2337, S2758, S2762,
  S2780, S2803, S2810, S2869, S2872, S2885, S2914, S2923, S2947, S2986, S3091, S3122, S3133, S3155,
  S3195, S3623, S3654, S3800, S3812, S3860, S3862), each = the sentence's auto triples with good
  ones copied verbatim from the fresh output + the flag.txt FIX/DROP. S3720 needed nothing (its
  ask was a pure ADD, already landed). The superseded S2166 `MANUAL_RELATION_ADDITIONS` entry
  (wrong subject "payadnyan") was deleted. Per-sentence rationale + user sign-off in
  `audit_tooling/iteration_3/order_009_report.md`. New predicates:
  `BERUBAH_DARI_SUKSMA_SARIRA_MENJADI` (S2758), `BERUKURAN_PANJANG` (S3800),
  `DILETAKKAN_MELINTANG_DI` (S3812) â€” add to `Neo4/normalize.py` / `relation_map.json` /
  `kb/relation_phrases.json` with the rest of the pending list.
- **perf: `lookup_entity_label` precompile** (cell 51) â€” the buried-word fallback re-sorted the
  ~12k `COMBINED_ENTITY_DICTIONARY` and recompiled ~12k boundary-regex strings per call (~805+
  calls). Now a module-level `_ENTITY_LABEL_LOOKUP` list of `(entity, label, compiled_pattern)`
  built once. Verified byte-identical (`scratchpad/verify_lookup_entity_label.py`, 3061 phrases x2
  modes).
- **perf: Stanza batching** (cells 25 + 42) â€” `pos_tag_sentences` and `dependency_parsing` now
  call `nlp.bulk_process(list(sentences))` once instead of `nlp(sentence)` 4,340x each. Verified
  byte-identical (`scratchpad/verify_stanza_batch.py`, looped vs batched, 433 depparse entries incl.
  all 19 re-split sub-sentences + 413 POS). `tokenize_no_ssplit` deliberately NOT set.

**Re-run + verified 2026-09-07 10:36.** `scratchpad/compare_run.py` vs backup
`Results/Final.bak_pre009run_20260907_103102`: `hybrid_ner_results.txt`, both dependency files, and
both coreference files **byte-identical** (perf batch 2 confirmed non-destructive in a real full
run); `relation_results_ngaben.{json,txt}` changed in **exactly the 27 /009 sentence_ids, nothing
else** (918 -> 916 relations); every /009 sentence reads as the report intended. `/009` CLOSED.

### 2026-09-07 â€” predicate sync (downstream configs, not the notebook)

The notebook cascade's open tail had grown to **264 distinct predicates**; the `Neo4/` and `kb/`
configs were stale against it. Full report: `audit_tooling/predicate_sync_report.md`.

- `Neo4/relation_map.json` â€” +18 synonym merges. `Neo4/normalize.py` â€” `VOICED_PREDICATE` regex
  loosened to `^(DI|TER|MEâ€¦|BER)[A-Z]{2,}(_[A-Z]{2,})*$`; ~20 non-voiced open-tail predicates added
  to `CANONICAL_RELATIONS`. "still-unmapped" log 70 â†’ 0; distinct relations 264 â†’ 234.
- `kb/build_kb.py` â€” new `derived_phrase_spec()` / `phrase_spec()`: any predicate missing from
  `relation_phrases.json` (208 of them) now gets a morphology-derived `ok_prep` + template instead
  of `{}`, which was false-flagging every locative/instrumental auto fact to LOW + review queue.
  `relation_phrases.json` itself untouched.
- Regenerated `Neo4/relation_results_ngaben.normalized.json` + all of `kb/`. KB: HIGH/MED/LOW
  84/170/36 â†’ **191/103/11**, review_queue 50 â†’ **24**, underscore-in-NL renders â†’ **0**.
  `kb/build_report.txt.pre_predsync` = before snapshot.

### 2026-09-07 â€” convergence re-audit (Iteration 4 candidate)

Full triple-by-triple re-check of the current 916-triple run vs the raw file, 8 parallel
auditors (bundles regenerated by `build_bundles.py`), per-chunk reports in
`audit_tooling/reaudit_20260907/chunk_NN_report.md`, consolidated in
`audit_tooling/reaudit_20260907/CONSOLIDATED.md`. **Converged well: ~79 FIX + 12 DROP + ~60 ADD,
~10% of triples flagged (vs 42â€“66% originally).** The auditors confirmed the great majority of
flag.txt/Iteration-3 fixes landed. Remaining themes: (1) `dependency_rule` triples the override
pass never reached â€” flag.txt specified /116//117//122 fixes but only ADDs/full-replacements were
written; (2) copular-object clause-stripping (D1/N1 tail, ~15 cases); (3) locative-as-object;
(4) a few mega-fused predicates; (5) 2 genuine factual errors in manual_override (S1738 ALIAS,
S1747 hallucinated triple â†’ DROP); (6) ~6 stale redundant triples left beside an override;
(7) 2 cosmetic code bugs (S4062 doubled type tag, S4110 wrong type). Awaiting user review of
CONSOLIDATED.md before an Iteration 4 override batch.

**Iteration 4 fix batch LANDED 2026-09-07** (user: "FIX EVERYTHING"). 8 patch-builder agents turned
CONSOLIDATED.md into per-chunk `chunk_NN_iter4.json`; `iter4_normalize.py` (lowercase names,
UPPER_SNAKE relations, label validation); `patch_iter4.py` spliced them into cell 51 â€”
**92 override sids (189 triples: 16 replacing existing /009/iter3 entries, 76 new; S2065 = pure
drop `[]`), 36 addition sids (50 triples), 15 stale ADDITIONS entries dropped as now-overridden.**
The S4062/S4110 "code bugs" turned out to be data typos in earlier override entries (label in the
object string / wrong object_label) â€” fixed as overrides, no code change. Backup
`Knowledge Processing.ipynb.bak_iter4_20260907_121200`; MANUAL_RELATION_OVERRIDES now 302 entries
/ 534 triples, ADDITIONS 108 / 153, no dup keys; `verify_nb` OK, harness **138/138**, smoke **0**.
Pre-batch Results backup: `Results/Final.bak_pre_iter4_20260907_121259`.

**Iteration 4 re-run + verified 2026-09-07 12:27.** `compare_iter4.py`: dependency byte-identical;
NER/coref differ only by the new `(canonical: X)` annotations from the earlier
`normalization-ngaben.json` additions (entity list unchanged); `relation_results` changed in
**exactly the 127 iter4 sids, zero collateral** (916 â†’ 980 triples). Spot-check `verify_iter4_landed.py`:
19/21 landed. **2 needed a follow-up** (`patch_iter4b.py`, applied â€” needs one more re-run):
- S2377: override object contained "sebagaimana" â†’ whole row dropped by
  `_ATTRIBUTION_OBJECT_PATTERN` (false-positive: "sebagaimana asalnya semula" â‰  a citation).
  Reworded "sebagaimana" â†’ "seperti".
- S4110: `lookup_entity_label` re-types "pemangku kahyangan tiga setempat" â†’ BANGUNAN_RITUAL via
  buried "kahyangan tiga", overriding the hand-set ENTITAS_KEAGAMAAN. Object shortened to
  "pemangku" (exact ENTITAS_KEAGAMAAN dict hit).

**Lesson:** manual_override objects are still subject to `VERB_STUB_OBJECTS` /
`_ATTRIBUTION_OBJECT_PATTERN` / `_SELF_RESTATE` drops and to `lookup_entity_label` re-typing â€”
`scan_filter_collisions.py` checks a batch's objects against those before applying.

### 2026-09-07 â€” Solution 1: surgical per-triple manual fixes

Problem: `MANUAL_RELATION_OVERRIDES` is all-or-nothing per sentence â€” a 1-triple fix forces
re-listing every triple, re-tagging all of them `manual_override` (now 687/981 = 70%; only ~50
are genuinely hand-authored, the ADDs). `build_kb.py:612` auto-HIGHs every `manual_override` row,
so the KB confidence layer is now mostly a rubber stamp.

**Part 1 LANDED** (`patch_solution1.py`, cell 51, backup `*.bak_sol1_*`; both new dicts empty so
zero output change; smoke 0):
- **Â§13.8 pre-override snapshot** â€” writes `Results/Final/relation_results_ngaben/_preoverride_relations.json`
  (the pure auto relation set, before OVERRIDES/ADDITIONS/EDITS/DROPS) every run.
- **Â§13.8d `MANUAL_RELATION_DROPS`** `{sid: [(subject, relation, object), â€¦]}` and
  **`MANUAL_RELATION_EDITS`** `{sid: [{"match": (s,r,o), "set": {â€¦fieldsâ€¦}}, â€¦]}` â€” match a triple
  on its current text, change/remove only that one, leave the rest (source and all) untouched.
  Assert: no sid in both OVERRIDES and DROPS/EDITS.

**Part 2 (pending a run):** migrate the ~302 existing OVERRIDES entries against
`_preoverride_relations.json` â€” delete no-op overrides (list == current auto), convert
"auto minus N" â†’ DROPS, "auto with N edited" â†’ EDITS, keep true full-rebuilds as OVERRIDES.
Then re-run and verify relation *content* is byte-identical to the current output (only `source`
tags change for the verbatim-copied triples). New predicates introduced: `MEMBUJUR_KE`, `DIMANDIKAN_DI`,
`DIMANDIKAN_DI_ATAS`, `BERAKAR_PADA`, `DIPINDAHKAN_DARI`, `KEMBALI_KEPADA`, `DIBAKAR_DALAM`,
`DITANAM_ATAU_DIBAKAR_BERSAMA`, `HARUS_DIRASAKAN_SEBAGAI`, `DIPERCIKI_DENGAN`, `BERPAMITAN_KEPADA`,
`DIDUDUKKAN_DI`, `DITENTUKAN_BERDASARKAN`, `DIBUAT_BERBENTUK`, `DILAKUKAN_ANTARA`, `DIABEN_DI`,
`DIPERSILAKAN_UNTUK`, `DIPENDAK_SECARA`, `BERTUJUAN_AGAR`, `DIMASUKKAN_MELALUI`, `BERVARIASI_DALAM`,
`NAIK_KEDUDUKAN_DARI`, `DAPAT_MEMASUKI`, `DIBILAS_DENGAN`, `DIKERINGKAN_DENGAN` â€¦ â€” sync into
`Neo4/` + `kb/` after the run (VOICED_PREDICATE regex already accepts them).
- **Still manual:** `python Neo4/load_ngaben_to_neo4j.py` + re-export KG SVG (needs a running
  Neo4j). `flag.txt` is hand-authored â€” nothing to regenerate there.

### 2026-09-07 â€” entity-resolution / fragment cleanup (downstream)

Conservative pass to collapse duplicate graph nodes (auto-merge by head noun was tried and
rejected â€” it would fold "dewa siwa" â†’ "dewa"). Changes:
- `Data/normalization-ngaben.json` â€” added `uang kepeng` / `pipis bolong` / `bale-bale` /
  `pepaga`+`asagan` families to the concept map (were missing entirely).
- `kb/entity_resolution.json` â€” `strip_modifiers` += tadi, mendiang, seseorang, sejumlah,
  beberapa, biji, segenap, masing-masing, setiap, seluruh, segala, helai, lembar, â€¦;
  `force_merge` += ~22 exact variants (jenazah seseorangâ†’jenazah, pitra mendiangâ†’pitra,
  rurub sinom tadiâ†’rurub sinom, â€¦).
- `kb/build_kb.py` `_strip()` â€” now also strips a leading bare-number token
  ("5 biji uang kepeng" â†’ "uang kepeng").
- `Neo4/normalize.py` â€” `SUBJECT_MAX_WORDS = 5`: a subject of â‰¥5 words is a captured clause,
  drop the row (raw graph only; the KB keeps those via force_merge).
- Regenerated normalize + build_kb + kg_visualizer. normalize 916â†’847 rows, 559â†’503 nodes;
  KB unresolved entities **290â†’247**, canonical entities 489â†’448, review_queue **24â†’13**,
  HIGH/MED/LOW 191/103/11 â†’ **192/95/7**. Graph: `pepaga` (12â†’20), `pitra` (12â†’16),
  `uang kepeng` now a proper hub (was scattered). Structural sparseness (20% isolated,
  46% degree-1) is unchanged â€” that's extraction density, not a config issue.
- **Remaining 247 unresolved** is a curation task for the domain expert (concept map +
  gazetteer), not auto-fixable.

### 2026-09-07 â€” relation results also saved as Markdown

Notebook cell 54, new section 14.3c (`audit_tooling/iteration_3/patch_relation_md.py`): writes
`Results/Final/relation_results_ngaben/relation_results_ngaben.md` â€” one Markdown table per
sentence (subject / relation / object / source) with the source sentence quoted above it.
Additive; the .json/.txt writers are unchanged. Generated for the current run without a re-run
(194 KB, 916 relations / 466 sentences).

### 2026-09-08 â€” Solution 1 Part 2 LANDED + manual layer moved to an external file

The whole manual-correction layer now lives in **`Data/relation_patches.json`** (pretty-printed,
git-diffable, reviewable without opening the notebook) instead of three inline dicts. The
relation-extraction engine cell loads it and applies four op types:

| key | effect | `source` on the row |
|---|---|---|
| `deletions`  | remove one auto triple, matched normalized-exact on `(sid, subject, relation, object)` | (row gone) |
| `edits`      | `dict.update(set)` one auto triple, same match | `manual_edit` |
| `additions`  | append one missing triple | `manual_addition` |
| `legacy_overrides` | all-or-nothing sentence replacement (kept as an escape hatch; **currently empty**) | `manual_override` |

Migration (`Neo4/migrate_overrides_to_patches.py`, reads the pre-A notebook backup +
`_preoverride_relations.json`): each of the 302 `MANUAL_RELATION_OVERRIDES` sentences was diffed
against its pure-auto extraction â€”
- auto triple the override kept verbatim â†’ **dropped from the patch file** (auto flows through as
  `dependency_rule` / `object_decomposition`); 98 triples stopped being fake-manual.
- auto triple the override removed â†’ `deletions` (327).
- override triple the extractor never produced â†’ `additions` (391 from overrides + 99 from the old
  `MANUAL_RELATION_ADDITIONS`).
- 1:1 `(subject, relation)` delete+add pair â†’ collapsed to `edits` (99).
- 35 `[]`-override sids â†’ a deletion per auto triple.

`legacy_overrides` came out **empty** â€” every wholesale entry decomposed cleanly.

**Verified provenance-only** (static end-to-end sim of the full post-extraction pipeline, old
inline dicts vs new patch file): final output **981 triples, 0 lost, 0 gained**. Only `source`
changes: was `{manual_override 687, dependency_rule 276, object_decomposition 18}`, now
`{manual_addition 490, dependency_rule 356, manual_edit 99, object_decomposition 36}` â€” manual
share 70% â†’ 60%, and every manual row is now an individually-reviewable per-triple entry with a
`reason` + `context`.

Engine-cell changes (backup `*.bak_preAB_*`): inline `MANUAL_RELATION_OVERRIDES` /
`MANUAL_RELATION_ADDITIONS` / `MANUAL_RELATION_DROPS` / `MANUAL_RELATION_EDITS` literals deleted
(~144 KB); external loader added; apply blocks rewritten for the flat-list shapes; new `source`
tags. **A4:** an explicit non-null `object_label` in an addition/edit now sticks (`_manual_label`
flag skips the `lookup_entity_label` overwrite) â€” 84 rows. **Filter fix:** the
`FUNCTION_WORD_OBJECTS` drop exemption widened from `source == "manual_override"` to
`source.startswith("manual_")` (load-bearing for exactly S3758 `logam campuran BERADA_DI tengah`,
now `manual_edit`).

**VERIFIED on the user's real re-run 2026-09-08 11:12:** 981 triples out, 0 lost / 0 gained vs
the pre-migration backup; 0 `[warn] PATCH_*`; 0 rows missing `source`; `.md` renders per-triple
provenance correctly. **`build_kb.py:612` fixed** â€” the auto-HIGH check was `source ==
"manual_override"`, now `source.startswith("manual_")` so the 589 rows retagged `manual_edit` /
`manual_addition` keep HIGH confidence (deliberate: they're all hand-verified in
`relation_patches.json`; re-reviewing them via the KB review_queue was the rejected alternative).
`normalize.py` + `load_ngaben_to_neo4j.py` use `source` for nothing â€” unchanged.
**Still to do (user):** `python Neo4/normalize.py` â†’ `python kb/build_kb.py` â†’ copy
`Results/Final/.../relation_results_ngaben.json` â†’ `Neo4/`. Supersedes yesterday's blanket
`source` rename.

**Part C (extractor quality) â€” investigated 2026-09-08, dropped.** Deep read of cell 52's
object path + re-analysis of the 327 deletions revised the earlier "81% one root cause / 150-195
sentences recoverable" way down: ~263/327 deletions are domain-knowledge restructuring (Balinese
offering-list drops, list-sentence splits, KB rephrasing) no parse rule reproduces. Rule-fixable
â‰ˆ 28 clause-trim (medium risk: an object-string change silently breaks the patch-file match specs
and can flip ENTITY/LITERAL via the `>5 words | yang` label guard) + ~22 fragment/copula (needs
the Stanza POS tag â€” a plain string filter over `me/di/ber/ke`-prefix objects hit 14 false
positives: `beruang`, `keluarga`, `keris`, `keponakan`, `kelereng`...). Safe string-level subset
(3 source typos + `DILAKUKAN_SAAT`â†’`DIGUNAKAN_SAAT` + numeric-object-under-`ADALAH` drop) clears
only ~5 patch entries â€” not worth a ~2h notebook run. `python Neo4/migrate_overrides_to_patches.py
--audit` stays available (reports which patch entries an extractor change made redundant) if this
is ever revisited.

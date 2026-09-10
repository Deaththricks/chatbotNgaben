# Knowledge Graph Cleanup Plan

## Context

The Neo4j visualization (`Knowledge graph\visualisation1.svg`) has two layers of problems:

1. **The SVG is stale.** It was exported from a database built with an older relation
   taxonomy (`ATRIBUT / LOKASI / DEFINISI / TUJUAN / AKIBAT / KLASIFIKASI`) *plus* the
   current one (`PUNYA / DI / ARTINYA / BUAT / JADINYA / TERMASUK`). ~176 relationships
   are drawn twice as parallel edges. The loader uses `MERGE` (add-only, never deletes),
   so re-running it without wiping keeps the doubles.

2. **The source data has quality issues** that will show in any regenerated graph:
   - Spelling-variant nodes that should be one node: `tirta`/`tirtha`, `kawangen`/`kwangen`,
     `pitra`/`pitara`, `pangabenan`/`pengabenan`, `ngelungah`/`nglungah`,
     `puspa lingga`/`puspalingga`, `bale pamuun`/`bale pamuunan`,
     `balai selunglung`/`bale salunglung`, `lontar yama purva tattwa`/`lontar yama purwana tatwa`,
     `atma pitara`/`atma/pitara`, `kawangen jeriji`/`kwangen jeriji` (~12 pairs).
   - ~42 "entity" objects that are actually whole clauses (up to 199 chars), e.g.
     S797 `pitra yadnya -[PUNYA]-> "arti tersendiri, yakni upacara keagamaan yang..."`.
     They render as giant unreadable blobs.
   - Relation-name sprawl: 105 distinct predicates, 57 used exactly once â€” mostly raw
     Indonesian verb lemmas that fell through the notebook's `RELATION_TAXONOMY`
     (`WARNA`, `OLES`, `PUTAR`, `SIRAMLAH`, `TEMPELL` [sic]...).
   - Junk rows: S1498 & S2571 have `object: "nya"`.
   - One mislabel: S45 `asti wedana -[ARTINYA]-> "..." | BANGUNAN_RITUAL` (it's a
     definition, not a building).
   - 102 of 487 nodes float with no edges (all subjects whose relations are 100% LITERAL).

**Decisions made with the user:**
- Cleanup lives in a **standalone `normalize.py`** (messy JSON -> clean JSON). The notebook
  is NOT touched and NOT re-run.
- Visualization stays on **Neo4j**: fix the loader, user re-loads the clean JSON and
  re-exports the SVG from Neo4j Browser.
- `revision.txt` is already executed upstream â€” **delete it**, do not address its contents.
- Cleanup intensity: **Moderate** (merge spelling variants; bucket stray relations;
  drop pure-junk rows; fix the S45 mislabel; demote clause-objects to node properties;
  keep all other literals as properties; hide isolated nodes from the view).
  No promotion of short literals to nodes.

## Existing infrastructure to reuse (do not rebuild)

- `Data\normalization-ngaben.json` â€” the notebook's alias map (~199 pairs, 7 buckets).
  **Caveat:** it is *concept-level*, not spelling-level â€” it merges `mamukur`/`nyekah`/
  `atma wedana` -> `Ngerorasin`, `puspalingga` -> `Sekah`, etc., and emits Title-Case.
  Do NOT apply it wholesale (that over-collapses and contradicts the notebook, which
  deliberately does not canonicalize relation subjects/objects). Use it only as a
  reference when building the focused spelling map below.
- `Data\ngaben-dictionary.json` â€” authoritative term -> type gazetteer (765 entries,
  14 labels). Use for: resolving label conflicts on merged nodes, and confirming a
  demoted-clause subject still has a label.
- `load_ngaben_to_neo4j.py` â€” the loader. Small, already understood.

## Deliverables

### 1. `Neo4\normalize.py` (new)

Reads `Results\Final\relation_results_ngaben\relation_results_ngaben.json` (pipeline
output, authoritative â€” identical to the current `Neo4\` copy), writes
`Neo4\relation_results_ngaben.normalized.json` (pretty-printed JSON array, 2-space
indent, per the user's JSONL/JSON formatting rule). Deterministic; safe to re-run.

Pipeline, in order (order matters):

1. **Canonicalize subject & object** through a new focused map
   `Neo4\node_aliases.json` (checked in, hand-curated, ~12-20 entries,
   `"variant" -> "canonical"`, all lowercase). Seeded list with merge targets:

   | variant | canonical | note |
   |---|---|---|
   | `tirta` | `tirtha` | dominant form has deg 11 |
   | `kwangen` | `kawangen` | |
   | `kwangen jeriji` | `kawangen jeriji` | |
   | `pitara` | `pitra` | label -> KONSEP_FILOSOFIS (pick dominant) |
   | `pengabenan` | `pangabenan` | |
   | `hal pangabenan` | `pangabenan` | |
   | `nglungah` | `ngelungah` | |
   | `puspalingga` | `puspa lingga` | NOT `Sekah` |
   | `bale pamuun` | `bale pamuunan` | |
   | `balai selunglung` | `bale salunglung` | label -> BANGUNAN_RITUAL |
   | `atma/pitara` | `atma pitara` | |
   | `lontar yama purva tattwa` | `lontar yama purwana tatwa` | |
   | `bele-bale` | `bale-bale` | |

   Do **not** merge `sawa`/`sawa dewasa` or `dewa`/`dewa iswara` (real subtypes).
   Applied first so dedup and relation mapping see canonical names.

2. **Strip boundary junk** from subject/object: leading/trailing quotes, commas,
   spaces, stray `"` pairs. Drop the row if the object becomes empty or is a bare
   stopword (`nya`, `ini`, `itu`, `yang`, ...). Expected drops: 2 (`"nya"` rows).

3. **Fix known mislabels** via `Neo4\label_overrides.json` (checked in, keyed by
   `sentence_id` + object text). Seed: S45 object -> `KONSEP_FILOSOFIS`.

4. **Demote clause-objects.** If `object_type == "ENTITY"` and the object is
   clause-like (> ~50 chars, or contains a finite-verb marker / embedded `,` `(` `"`),
   set `object_type = "LITERAL"` and `object_label = null`. This turns ~42 blob nodes
   into a property on the subject instead of an edge. Log each one.

5. **Map relations** through `Neo4\relation_map.json` (checked in). Contains the
   notebook's 12 canonical buckets + new entries for the ~57 fall-through lemmas.
   Rules:
   - Map obvious synonyms into existing buckets (`OLES`,`SIRAMLAH`,`SEMBUR` -> `TINDAKAN`;
     `WARNA` -> `PUNYA`; `TULIS` -> `TINDAKAN`; etc.).
   - Fix typos: `TEMPELL` -> `TEMPEL` then bucket; `MELAKUMUSPA` -> `PERSEMBAHAN`.
   - Keep genuinely distinct temporal/sequence predicates as-is: `SEBELUM`, `SETELAH`,
     `SEMENTARA`, `HANYUT`/`LARUNG`, `MANDI`.
   - Anything still unmapped -> keep verbatim (uppercased) and list it in the run
     report for manual review. Target: < 20 distinct predicates.

6. **Dedup** exact `(subject, relation, object, object_type)` rows after all mapping
   (expected: ~16 removed).

7. **Attach provenance**: keep `source`; add `raw_relation` (pre-map value) and, for
   demoted clauses, keep the full text as the property value. Preserve `sentence_id`,
   `context_sentence`.

8. **Write report** to stdout + `Neo4\normalize_report.txt`: counts in/out, every
   node merge, every clause demotion, every unmapped relation, every dropped row.

### 2. `load_ngaben_to_neo4j.py` (edit)

- Point `JSON_PATH` at `relation_results_ngaben.normalized.json`.
- **Wipe before load**: add `session.run("MATCH (n) DETACH DELETE n")` before the
  constraint/MERGE block (guarded by a `WIPE = True` constant with a comment). This is
  what actually kills the doubled edges.
- **Respect `object_label` on LITERAL rows**: in `build()`, also read
  `d.get('object_label')` for LITERAL objects so a demoted-clause / labelled-literal
  subject keeps its type in the `label` dict (currently only ENTITY objects contribute).
- Everything else unchanged (literal -> node property, entity -> edge).

### 3. Cleanup

- Delete `C:\Misc\Work\AI_Chatbot\Graphing\revision.txt`.

## Out of scope (explicit)

- No notebook edits, no pipeline re-run.
- No promotion of literal objects into nodes.
- No new standalone renderer â€” SVG regen is the user's Neo4j Browser export.
- The 102 isolated nodes are not deleted; they are simply not shown (user filters the
  view in Neo4j Browser, or we can add a `:Isolated` marker â€” decide at implementation).

## Verification

1. `python Neo4\normalize.py` â€” runs clean, report shows ~770 rows out, ~12 merges,
   ~42 demotions, 2 drops, < 20 distinct predicates, 0 unmapped surprises.
2. Spot-check `relation_results_ngaben.normalized.json`: no `tirta` (only `tirtha`),
   no `object: "nya"`, S45 label fixed, S797 object now `LITERAL`.
3. Diff distinct node names before/after (expect ~487 -> ~473).
4. Wipe + reload Neo4j: `python Neo4\load_ngaben_to_neo4j.py`. Console reports fewer
   nodes, and edge count ~= 311 (not ~490).
5. In Neo4j Browser: confirm no node pair has both `PUNYA` and `ATRIBUT` (or any
   old-taxonomy label) between them. Re-export to replace `visualisation1.svg`.

## Files

| Path | Action |
|---|---|
| `Neo4\normalize.py` | new |
| `Neo4\node_aliases.json` | new (curated) |
| `Neo4\relation_map.json` | new (curated) |
| `Neo4\label_overrides.json` | new (curated) |
| `Neo4\relation_results_ngaben.normalized.json` | generated |
| `Neo4\normalize_report.txt` | generated |
| `Neo4\load_ngaben_to_neo4j.py` | edit (wipe + literal-label) |
| `revision.txt` | delete |

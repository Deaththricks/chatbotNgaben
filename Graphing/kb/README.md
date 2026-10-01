# Ngaben Knowledge Base

A cleaned, entity-resolved knowledge base built from the Ngaben relation-extraction
pipeline **plus** the source report. The chatbot (`Chatbot/bot/`) reads it two ways:
the graph (`output/entities.json` + `relations.jsonl`, loaded into Neo4j) for structure,
and `output/` directly (through `kb_resolver.py` and `kb_content.py`) for names,
definitions, text-only attributes and sentence templates. See `methodology.md` for how it
is built, and CLAUDE.md for the rules that keep it correct.

## Layout

```
kb/
  build_kb.py, README.md, methodology.md   -- the build script + docs (this folder's root)
  output/     -- everything build_kb.py generates (see Files below)
  tuning/     -- hand-authored curation knobs build_kb.py reads
  curation/   -- review/audit tooling and reports (not part of the build itself)
```

## Build

From `Graphing/kb/`:

```
python build_kb.py                                                      # -> output/
cd curation && ..\..\..\Chatbot\rasa_bot\Scripts\python.exe kb_lint.py  # quality gate: must exit 0
cd ..\..\neo4 && python load_ngaben_to_neo4j.py                         # wipe + reload Neo4j (default --source kb)
```

Then run the regression harness (`Chatbot/bot/regression/run_regression.py`, see CLAUDE.md).

`build_kb.py` reads (never writes):

- `../neo4/relation_results_ngaben.normalized.json` -- the relation rows. It began as
  `neo4/normalize.py`'s output, but nearly all later KB fixes were added to it by hand
  (source `manual_addition+...`), so **do not re-run `normalize.py` onto it** -- the
  script refuses to while it holds rows it would not produce.
- `../data/ngaben-glossary.txt` -- the definitions (`* Term:  Definition.` lines).
- `../data/ngaben-merge-cleaned.txt` -- the source report, cut into passages.
- `../data/ngaben-dictionary.json` (gazetteer: term -> type),
  `../data/normalization-ngaben.json` (concept map), `../neo4/node_aliases.json` (spelling map).
- `tuning/entity_resolution.json` (force_merge, broader_overrides, broader_suppress,
  type_overrides, strip_modifiers, keep_distinct), `tuning/review_decisions.json`
  (per-triple accept / reject / fix), `tuning/relation_phrases.json` (predicate -> sentence
  template), `tuning/definition_sources.json` (web-sourced definitions, for review).

`tuning/lint_waivers.json` is read only by `curation/kb_lint.py`; `tuning/definitions.json`
holds drafted definitions for `curation/build_glossary_review_master.py`, not the build.

## Files (all in `output/`)

| file | what it is | used by |
|---|---|---|
| `entities.json` | 713 canonical entities: `id`, `name`, `type`, `aliases`, `definition`, `broader` (IS-A parent), `attributes` (text-only facts with provenance), `mention_passages` | the resolver, `kb_content.py`, the Neo4j loader |
| `relations.jsonl` | every entity -> entity edge (1,182; all HIGH or MED at present) with `confidence`, `nl`, provenance | the Neo4j loader (the bot queries non-LOW edges) |
| `facts.jsonl` | the HIGH + MED relations as Indonesian sentences with `source_sentence` | `kb_content.py` (definitions fallback, grounding checks) |
| `passages.jsonl` | 1,168 passages: 466 chunks of the report, 697 glossary entries, 5 FAQ entries (`kind`) | `kb_content.py` reads the glossary entries |
| `glossary.md` | human-readable entities grouped by type | review |
| `review_queue.jsonl` | LOW-confidence edges + fragment entities with a blank `decision` (empty at present) | `curation/apply_review.py` |
| `build_report.txt` | counts, type breakdown, unresolved entities, LOW reasons | what to fix next |

`glossary.md`, `review_queue.jsonl` and `build_report.txt` are gitignored.

## Graph view

`python ../neo4/load_ngaben_to_neo4j.py` loads `entities.json` as nodes (label = `type`,
`broader` as `:TERMASUK_JENIS`) and `relations.jsonl` as edges (`confidence` is a property).
To view it without Neo4j:

```
python ../neo4/kgVisualizer/build_graph.py --source kb   # writes kgVisualizer/graph_data.js (gitignored)
# then open ../neo4/kgVisualizer/index.html
```

## Confidence

- **HIGH** -- both endpoints resolve to known entities, the predicate is a concrete one,
  and the source sentence's preposition agrees with it.
- **MED** -- one endpoint unresolved, or a vaguer predicate (`MEMILIKI`, `DIKENAI`).
- **LOW** -- unresolved endpoints, `LAINNYA`, or a preposition/provenance mismatch. Not in
  `facts.jsonl`, never shown by the bot; sits in `output/review_queue.jsonl`.
  `review_decisions.json` `accept` promotes an edge past LOW.

## Known limits

The relation extractor is dependency-rule based and gets ~1 edge in 4 wrong (direction or
predicate). The confidence layer, the review decisions and hand-curated rows contain that;
the extractor itself is not changed. `passages.jsonl` is verbatim source text and is the
reliable layer. See `methodology.md`.

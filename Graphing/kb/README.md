# Ngaben Knowledge Base

A cleaned, entity-resolved knowledge base built from the Ngaben relation-extraction
pipeline **plus** the source report. Designed to feed either a vector-RAG chatbot
or a graph database — the retrieval stack is not fixed yet.

## Build

```
python ../Neo4/normalize.py     # row-level cleanup  -> relation_results_ngaben.normalized.json
python build_kb.py              # this folder        -> the files below
```

`build_kb.py` reads (never writes) `../Neo4/relation_results_ngaben.normalized.json`,
`../Data/ngaben-merge-cleaned.txt`, `../Data/ngaben-dictionary.json`,
`../Data/normalization-ngaben.json`, `../Neo4/node_aliases.json`, and the two
tuning files in this folder (`entity_resolution.json`, `relation_phrases.json`).

## Files

| file | what it is | for a chatbot |
|---|---|---|
| `passages.jsonl` | the source report split into ~480 chunks, each with `section_path`, `entity_ids`, char offsets; FAQ and glossary entries tagged `kind` | **primary RAG corpus** — embed `text`, keep the rest as metadata |
| `entities.json` | ~305 canonical entities: `id`, `name`, `type`, `aliases`, `definition`, `broader` (IS-A parent), `attributes` (with provenance), `mention_passages` | entity grounding / entity-linking / a "card" to show per term |
| `facts.jsonl` | HIGH+MED confidence relations rendered as Indonesian sentences, each with `source_sentence` | secondary RAG corpus — short atomic facts with citations |
| `relations.jsonl` | every entity->entity edge (incl. LOW), structured, with `confidence`, `nl`, provenance | load into a graph DB; filter by `confidence` |
| `glossary.md` | human-readable entities grouped by type | review / documentation |
| `review_queue.jsonl` | LOW-confidence edges + fragment entities, each with a blank `decision` field | human adjudication — see `apply_review.py` |
| `build_report.txt` | counts, type breakdown, every unresolved entity, every LOW reason | what to fix next |

## Recipe A — vector RAG

1. Embed `passages.jsonl[].text` (primary) and `facts.jsonl[].text` (secondary).
   Store `id`, `section_path` / `source_sentence`, `entity_ids` as metadata.
2. On a query, retrieve top-k from both; prefer passages, use facts to pin
   specifics.
3. Optionally expand the query with entity aliases from `entities.json`
   (`name` + `aliases`) so "mamukur" also matches "ngerorasin".
4. Cite `passages.char_start/char_end` back into `../Data/ngaben-merge-cleaned.txt`,
   or quote `facts.source_sentence`.

## Recipe B — knowledge graph

```
python ../Neo4/load_ngaben_to_neo4j.py --source kb
```

loads `entities.json` as nodes (label = `type`, `broader` as `:TERMASUK_JENIS`)
and `relations.jsonl` as edges (`confidence` is a property; filter
`WHERE r.confidence <> 'LOW'` for a clean view). Or view it in the browser:

```
python ../Neo4/kg_visualizer/build_graph.py --source kb
# then open ../Neo4/kg_visualizer/index.html
```

## Confidence

- **HIGH** — both endpoints resolve to known entities, the predicate is a
  concrete one, and the source sentence's preposition agrees with it.
- **MED** — one endpoint unresolved, or a vaguer predicate (`MEMILIKI`,
  `DIKENAI`). Spot-check before relying on it.
- **LOW** — unresolved endpoints, `LAINNYA`, or a preposition/provenance
  mismatch. Not in `facts.jsonl`; sits in `review_queue.jsonl`.

## Known limits

The relation extractor is dependency-rule based and gets ~1 edge in 4 wrong
(direction or predicate). The confidence layer + review queue contain that; it
is not fixed at source. `passages.jsonl` is verbatim source text and has no
such problem — it is the reliable layer. See `METHODOLOGY.md`.

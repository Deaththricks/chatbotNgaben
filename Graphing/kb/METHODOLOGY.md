# How the Ngaben knowledge base is built

A note on method, for review. The goal is a knowledge base an AI chatbot can
answer from — accurately, with citations — not a perfect graph.

## The pipeline

```
  corpus (ngaben-merge-cleaned.txt)
        │
        │  Stanza NLP notebook  (Knowledge Processing.ipynb — run separately)
        │    NER  ->  coreference  ->  dependency parse  ->  relation extraction
        ▼
  relation_results_ngaben.json          774 raw (subject, relation, object) rows
        │
        │  normalize.py          row-level cleanup, deterministic, re-runnable
        │    · merge spelling variants (node_aliases.json)
        │    · drop junk / Balinese-only / self-loop / fragment / bare-word rows
        │    · collapse ~100 raw predicates -> 23 controlled ones (relation_map.json)
        │    · BERARTI is a definition, never an edge
        ▼
  relation_results_ngaben.normalized.json    719 rows
        │
        │  build_kb.py           entity resolution + enrichment + scoring
        ▼
  kb/  ── entities.json · relations.jsonl · facts.jsonl
          passages.jsonl · review_queue.jsonl · glossary.md
```

## Why two layers

| layer | source | trust | role |
|---|---|---|---|
| **passages** | verbatim chunks of the report | high — it is the original text | primary answer material for RAG |
| **entities + facts** | the extracted triples, cleaned | medium — the extractor errs | structure: grounding, glossary, graph, query expansion |

The report already contains a Glosarium and an FAQ; those are carried through as
tagged passages and used as high-priority definitions.

## Entity resolution (build_kb.py)

Every subject / object string is mapped to a canonical entity by, in order:

1. **concept map** — `Data/normalization-ngaben.json` (~195 pairs, 7 buckets).
   Merges ritual synonyms: `mamukur`, `atma wedana` → `ngerorasin`;
   `puspalingga` → `sekah`.
2. **spelling map** — `Neo4/node_aliases.json` (`tirta`→`tirtha`, …).
3. **gazetteer** — `Data/ngaben-dictionary.json` (765 term→type). Exact hit = its
   own canonical.
4. **modifier strip** — remove non-distinguishing edge words
   (`tersebut, ini, baru, atas, kedua, …`) and retry 1–3. Semantic modifiers
   (`dewasa, anak, bayi, pangentas, …`) are never stripped, so subtypes stay
   separate.
5. **unresolved** — kept as its own entity, flagged in `build_report.txt`.

A multi-word entity whose head word is itself a known entity gets a
`broader` link (`tirtha pangentas` → `tirtha`), giving the graph an IS-A spine
without collapsing the distinction. This reconnects most of the small islands
the raw graph had.

`type` comes from the gazetteer, else a majority vote of the extractor's labels,
else the broader entity's type. `definition` prefers the Glosarium, then a
`BERARTI` gloss, then a defining sentence from the passages. `attributes` are the
non-edge (LITERAL) facts, kept with their `sentence_id`.

## Confidence scoring (per relation edge)

Signals used:

- **endpoint resolution** — did both subject and object map to known entities?
- **predicate class** — concrete (`BERADA_DI`, `DIPERSEMBAHKAN_KEPADA`, temporal…)
  vs vague (`MEMILIKI`, `DIKENAI`) vs error-prone (`MENJADI`, `MENSYARATKAN`…).
- **preposition agreement** — the word before the object in the source sentence
  (`di / ke / dari / dengan / tentang …`) is checked against what the predicate
  expects. "diusung **ke** setra" tagged `DIKENAI` → mismatch → LOW.
- **provenance** — the cited sentence must actually mention the subject or object.

HIGH+MED → `facts.jsonl`. LOW → `review_queue.jsonl` with the reason(s).

## The review loop

`review_queue.jsonl` has one record per flagged item with a blank `decision`
field. Fill it with `accept`, `reject`, or `fix: <corrected triple>`, then run
`apply_review.py` — accepted/fixed items fold into `facts.jsonl` +
`relations.jsonl`, decisions are logged to `review_resolved.jsonl` so the build
stays reproducible. Same shape as the existing "Order #109" dictionary gap-fill.

## What is deliberately *not* done

- The notebook / extractor is not modified. Direction errors are contained by
  the confidence layer, not fixed at the parse.
- No machine translation — the KB is Indonesian, matching the corpus.
- The concept map's synonym merges are applied in full here (unlike in
  `normalize.py`, which stays conservative for the Neo4j view) because for a
  chatbot, "what is mamukur" and "what is ngerorasin" should reach the same
  entity.

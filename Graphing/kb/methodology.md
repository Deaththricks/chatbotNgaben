# How the Ngaben knowledge base is built

A note on method, for review. The goal is a knowledge base an AI chatbot can
answer from -- accurately, with citations -- not a perfect graph.

## The pipeline

```
  corpus (data/ngaben-merge-cleaned.txt)
        │
        │  Stanza NLP notebook  (knowledge_processing.ipynb -- run separately)
        │    NER  ->  coreference  ->  dependency parse  ->  relation extraction
        ▼
  results/final/relationResultsNgaben/relation_results_ngaben.json   980 raw rows
        │
        │  neo4/normalize.py     row-level cleanup, deterministic
        │    · merge spelling variants (node_aliases.json)
        │    · drop junk / Balinese-only / self-loop / fragment / bare-word rows
        │    · collapse raw predicates to controlled ones (relation_map.json)
        │    · BERARTI is a definition, never an edge
        ▼
  neo4/relation_results_ngaben.normalized.json    1,859 rows
        │    (the normalized output PLUS every hand-curated row added since
        │     2026-09-17: 1,482 rows carry a manual_* source tag; normalize.py
        │     refuses to overwrite them)
        │
        │  kb/build_kb.py        entity resolution + definitions + scoring
        ▼
  kb/output/  ── entities.json · relations.jsonl · facts.jsonl
                 passages.jsonl · review_queue.jsonl · glossary.md
        │
        │  neo4/load_ngaben_to_neo4j.py     (the graph the chatbot queries)
        ▼
  Neo4j
```

## Why two layers

| layer | source | trust | role |
|---|---|---|---|
| **passages** | verbatim chunks of the report + the glossary | high -- it is the original text | definitions, citations |
| **entities + relations** | extracted and hand-curated triples | curated -- every live edge is HIGH or MED | structure: the graph the bot answers from |

## Entity resolution (build_kb.py)

Every subject / object string is mapped to a canonical entity by, in order:

1. **tuning force_merge** -- `tuning/entity_resolution.json` (surface -> canonical entity
   *name*). It overrides the concept map below: e.g. `ngerorasin` is an alias of
   `atma wedana` (the corpus uses it as Atma Wedana's everyday name), `mamukur` and
   `puspa lingga` are their own entities, `wadah` is its own entity (not bade).
2. **concept map** -- `data/normalization-ngaben.json` (207 pairs in 7 buckets).
3. **spelling map** -- `neo4/node_aliases.json` (`tirta` -> `tirtha`, ...).
4. **gazetteer** -- `data/ngaben-dictionary.json` (767 term -> type). An exact hit is its
   own canonical.
5. **modifier strip** -- remove non-distinguishing edge words (`strip_modifiers`:
   `tersebut, ini, baru, atas, kedua, ...`) and retry. Semantic modifiers (`dewasa, anak,
   bayi, pangentas, ...`) are never stripped, so subtypes stay separate; `keep_distinct`
   protects named forms.
6. **unresolved** -- kept as its own entity, flagged in `build_report.txt`.

A multi-word entity whose leading word is itself an entity gets a `broader` link
(`tirtha pangentas` -> `tirtha`), giving the graph an IS-A spine without collapsing the
distinction. "Itself an entity" here means a concept-map, alias or gazetteer entry: a term that
exists only through the glossary and relation rows (`kain`, `kayu`, added 2026-10-01 as bade's
materials) gets no kinds from the heuristic, so its kinds are listed in `broader_overrides`
(lint check 13 asks for them: every definition that files a node under "Kain ..." needs the link).
`broader_overrides` adds links the heuristic can't derive; `broader_suppress`
removes false ones (a stage is not a "kind of" its ceremony -- that link is a
`BAGIAN_DARI` relation row instead, since every `broader` is loaded as `TERMASUK_JENIS`).

`type` comes from `type_overrides`, else the gazetteer, else a majority vote of the row
labels, else the broader entity's type, else `ISTILAH_UMUM_RITUAL`. `definition` comes from `data/ngaben-glossary.txt`
(the corpus's glossary plus hand-written entries; web-sourced ones are listed in
`tuning/definition_sources.json`), then a `BERARTI` gloss, then a defining sentence from
the passages. All 713 entities have one. `attributes` are the text-only (LITERAL) facts,
kept with their `sentence_id`; the bot shows one only when its question aspect is asked.

## Confidence scoring (per relation edge)

- **endpoint resolution** -- did both subject and object map to known entities?
- **predicate class** -- concrete (`BERADA_DI`, `DIPERSEMBAHKAN_KEPADA`, temporal...)
  vs vague (`MEMILIKI`, `DIKENAI`) vs error-prone (`MENJADI`, `MENSYARATKAN`...).
- **preposition agreement** -- the word before the object in the source sentence
  (`di / ke / dari / dengan / tentang ...`) is checked against what the predicate expects.
  "diusung **ke** setra" tagged `DIKENAI` -> mismatch -> LOW.
- **provenance** -- the cited sentence must actually mention the subject or object.

HIGH + MED -> `facts.jsonl` and the bot. LOW -> `review_queue.jsonl` with the reason(s).

## The review loop

Decisions live in `tuning/review_decisions.json`, keyed `sentence_id|subject|object`, and
`build_kb.py` applies them at entity creation and at relation scoring: `accept` (promote
past LOW), `reject` (drop the triple), `fix: S | P | O` (replace it). Two ways to add them:
hand-edit the file, or fill the blank `decision` fields in `output/review_queue.jsonl` and
run `curation/apply_review.py`, which merges them into the file. The key has no
object_type, so a `reject` also drops an ENTITY row that shares a LITERAL row's key.

Hand-curated facts the extractor missed are added as rows in
`relation_results_ngaben.normalized.json` (source `manual_addition+<pass>`, a
`context_sentence` quoting the corpus line). `curation/kb_lint.py` is the gate every
change must pass.

## What is deliberately *not* done

- The notebook / extractor is not modified. Its errors are contained by the confidence
  layer, the review decisions and the lint, not fixed at the parse.
- No machine translation -- the KB is Indonesian, matching the corpus.
- Synonym merges are applied in full here (unlike in `normalize.py`, which stays
  conservative), because for a chatbot "apa itu ngerorasin" and "apa itu atma wedana"
  should reach the same entity.

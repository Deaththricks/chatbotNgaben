# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo overview

Two coupled subprojects that together build a **Rasa chatbot answering questions about Ngaben
(Balinese cremation ritual) terminology**:

- **`Graphing/`** — an offline NLP/KB pipeline over a Ngaben source corpus: NER + dependency-rule
  relation extraction -> a curated knowledge base (`Graphing/kb/`) -> loaded into Neo4j.
  `Graphing/chatbot-budaya-bali/` is a senior colleague's unrelated reference bot — ignored, and
  excluded via `.gitignore`; do not build on it.
- **`Chatbot/bot/`** — the Rasa Open Source 3.6.x project (NLU + rules + custom actions) that
  queries the Neo4j graph and the KB's curated layers to answer in Indonesian.

**Working agreement:** Claude writes the bot files; the user trains, runs, and tests the bot
themselves (see Environment limitation below) and audits KB/relation-extraction quality.

## Commands

All Python commands run against the project venv at `Chatbot/rasa_bot/` (not `.venv`), created
with `uv`. Activation doesn't persist across separate tool calls, so pass the interpreter
explicitly:

```
# install/sync deps (from Chatbot/)
uv pip install --python .\rasa_bot\Scripts\python.exe --override overrides.txt -r requirements.txt

# train (non-interactive, safe to run here) — from Chatbot/bot/
..\rasa_bot\Scripts\rasa.exe train

# validate data without training
..\rasa_bot\Scripts\rasa.exe data validate

# run NLU/core tests
..\rasa_bot\Scripts\rasa.exe test
```

`rasa shell`, `rasa interactive`, and the `rasa init` training prompt are **interactive** and crash
under this shell (`NoConsoleScreenBufferError` — prompt_toolkit needs a real console). The action
server (`rasa run actions`) also needs a persistent foreground process. **These must be run by the
user in their own PowerShell window**, not through Claude's Bash/PowerShell tool.

Neo4j KB pipeline (from `Graphing/`):

```
python Neo4/load_ngaben_to_neo4j.py --source kb   # loads Graphing/kb/entities.json + relations.jsonl
```

Requires `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` in `.env` (repo root; copy from `.env.example`).
`neo4j://127.0.0.1:7687` must already be running locally — this script doesn't start it.

## Environment gotchas (Python 3.10 venv on Windows)

- Rasa 3.6.x requires **Python 3.10**, not 3.11.
- Never move `Chatbot/rasa_bot/` after creating it — its `.exe` shims hard-code the venv's
  absolute path.
- `pyyaml` is overridden to `>=6.0.1` via `overrides.txt` (Rasa's `5.4.1` pin fails to build).
- A patch is applied inside the venv's own `rasa` install
  (`rasa_bot/Lib/site-packages/rasa/engine/storage/local_model_storage.py`,
  `_extract_archive_to_directory`) to drop a hardcoded `\\?\` long-path prefix that otherwise
  raises `WinError 123` on this Python/tarfile combination when loading any trained model. If the
  venv is ever recreated from a fresh `pip install`, reapply this patch before `rasa run`/`rasa
  test` will work.

## Architecture: how a question gets answered

```
user utterance (Indonesian)
  -> Rasa NLU (DIET + RegexEntityExtractor over the 485-term lookup table)
  -> intent + entities (istilah / istilah2 / tipe)
  -> RulePolicy: 1 intent -> 1 custom action (Chatbot/bot/actions/actions.py)
       -> kb_resolver.py: free text -> canonical KB entity id
       -> Cypher query against Neo4j (graph = structural source of truth:
          definition, type/labels, :TERMASUK_JENIS broader/narrower, attribute edges)
       -> kb_content.py: enrich with curated layers that aren't graph-shaped
          (facts.jsonl sentences, passages.jsonl faq/glossary, relation_phrases.json templates)
       -> deterministic Indonesian string
       -> optional Groq rephrase (llm/groq_client.py) with try/except fallback to the
          deterministic string if GROQ_API_KEY is unset or the call fails
  -> response
```

Key modules in `Chatbot/bot/`:
- `actions/actions.py` — one Action class per intent family (definisi, klasifikasi, jenis,
  atribut [fungsi/bahan/lokasi/waktu/pelaku/simbol via `PREDICATE_FAMILIES`], relasi, alasan,
  daftar_istilah, bandingkan, cari, acak, fallback).
- `kb_resolver.py` — resolution order: exact name/alias -> `entity_resolution.json` force_merge ->
  modifier-strip retry -> rapidfuzz (WRatio, threshold ~70-80). Mirrors
  `Graphing/kb/METHODOLOGY.md` but done Python-side because the graph doesn't store aliases
  queryably.
- `kb_content.py` — read-only loader for `facts.jsonl` / `passages.jsonl` / `relation_phrases.json`;
  the graph stays authoritative for structure, this module only supplies phrasing and the two
  hand-written passage kinds (`faq`, `glossary`).
- `KB_DIR` (`.env`, default `../../Graphing/kb`) points both `kb_resolver.py` and `kb_content.py`
  at the same KB build — keep it in sync with whatever `Graphing/kb/build_kb.py` last produced.

**Confidence filtering:** `relations.jsonl` / graph edges carry `confidence` (HIGH/MED/LOW); the
bot and `facts.jsonl` only use non-LOW edges (`WHERE r.confidence <> 'LOW'` / already filtered at
KB-build time) — LOW-confidence relation extraction is ~25% wrong and sits in
`Graphing/kb/review_queue.jsonl` for human review, not surfaced to users.

## Regenerating the KB (`Graphing/kb/`)

`Graphing/kb/build_kb.py` reads (never writes) upstream extraction/data files plus
`entity_resolution.json` and `relation_phrases.json`, and produces `entities.json`,
`facts.jsonl`, `relations.jsonl`, `passages.jsonl`, `glossary.md`, `review_queue.jsonl`,
`build_report.txt`. See `Graphing/kb/README.md` for the full recipe and `METHODOLOGY.md` for the
entity-resolution/confidence rules. After rebuilding the KB, re-run
`Neo4/load_ngaben_to_neo4j.py --source kb` to refresh the graph the bot queries.

Relation-extraction quality auditing (rule-based extractor, ~1 edge in 4 wrong) is tracked via
`Graphing/audit_tooling/` and `Graphing/Misc/relation_audit_report.md` /
`RELATION_AUDIT_RUNBOOK.md` — `Graphing/flag.txt` is the hand-audited rubric of known failure
modes (wrong subject/object, nonsense triples, source-text bleed, wrong relation label, dropped
coordinate members, under-extraction) that any further audit pass should follow.

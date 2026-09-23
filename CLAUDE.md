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
python neo4/load_ngaben_to_neo4j.py --source kb   # loads Graphing/kb/output/entities.json + relations.jsonl
```

Requires `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` in `.env` (repo root; copy from `.env.example`).
`neo4j://127.0.0.1:7687` must already be running locally — this script doesn't start it.

## Environment gotchas (Python 3.10 venv on Windows)

- Rasa 3.6.x requires **Python 3.10**, not 3.11.
- Never move `Chatbot/rasa_bot/` after creating it — its `.exe` shims hard-code the venv's
  absolute path.
- **Ollama is a hard runtime dependency, not optional.** `actions.py` calls a local Ollama
  server running the `qwen2.5` model on every single turn (term extraction/coreference *and*
  answer synthesis) — there's no offline/no-LLM mode. Before `rasa run actions` will produce
  real answers: `ollama pull qwen2.5`, then `ollama serve` (or leave the desktop app running).
  If Ollama is unreachable, calls are caught and the bot degrades to a plain templated answer
  (or a fixed "gangguan teknis" message on the free-form fallback path) instead of crashing —
  see `requirements.txt`'s comment and `how_it_works.md` §3.5 for exactly where each guard is.
- **Broad questions can 503 with `Service Unavailable` instead of answering.** A question that
  resolves to a hub entity with several `TERMASUK_JENIS` children (e.g. "eteh-eteh sawa dan semua
  hal yang membentuknya") pulls each child's own definition into the synthesis context
  (`actions.py`'s child-definition enrichment, capped at 8) — a bigger prompt plus a longer
  generated answer on local CPU-bound Ollama inference can push the two chained Qwen calls well
  past a minute. Two independent Sanic apps sit in the request path and *both* silently defaulted
  to Sanic's bare 60s `RESPONSE_TIMEOUT` instead of something longer:
  - the action server (`rasa run actions`, via `rasa_sdk`) — `create_app()` in
    `rasa_bot/Lib/site-packages/rasa_sdk/endpoint.py` never sets `RESPONSE_TIMEOUT` at all;
  - core itself (`rasa shell`/`rasa run` *without* `--enable-api`, which is what `rasa shell`
    actually uses) — `_create_app_without_api()` in `rasa_bot/Lib/site-packages/rasa/core/run.py`
    also never sets it. Only the `--enable-api` branch (`server.create_app()`) explicitly
    defaults it to 1 hour (`DEFAULT_RESPONSE_TIMEOUT` in `rasa/core/constants.py`) — easy to
    mistake for the general default since it *looks* like the only code path at a glance.
  Whichever of the two hits its 60s ceiling first cancels the in-flight request and returns 503
  before the answer is ever produced. This is not an `actions.py` bug — a normal,
  correctly-resolved answer just arrived too late. Both are patched in the venv (one line each,
  right after their respective `app = Sanic(...)`): `app.config.RESPONSE_TIMEOUT = 300` in
  `rasa_sdk/endpoint.py`'s `create_app` and in `rasa/core/run.py`'s `_create_app_without_api`. If
  the venv is ever recreated from a fresh `pip install`, reapply both patches alongside the
  WinError 123 one below.
- `pyyaml` is overridden to `>=6.0.1` via `overrides.txt` (Rasa's `5.4.1` pin fails to build).
- A patch is applied inside the venv's own `rasa` install
  (`rasa_bot/Lib/site-packages/rasa/engine/storage/local_model_storage.py`,
  `_extract_archive_to_directory`) to drop a hardcoded `\\?\` long-path prefix that otherwise
  raises `WinError 123` on this Python/tarfile combination when loading any trained model. If the
  venv is ever recreated from a fresh `pip install`, reapply this patch before `rasa run`/`rasa
  test` will work.

## Architecture: how a question gets answered

**This diverged from an earlier design and was corrected here 2026-09-17** — the bot no longer
does deterministic-string-plus-optional-rephrase; it's LLM-first with a deterministic fallback
used only as a quality guard:

```
user utterance (Indonesian)
  -> Rasa NLU (DIET + RegexEntityExtractor over lookup_istilah.yml)
  -> intent (sapa / pamit / bot_challenge / out_of_scope / ask_ngaben_detail / nlu_fallback)
  -> RulePolicy -> ActionGraphRAG (ask_ngaben_detail) or ActionLLMFallback (nlu_fallback)
       [both in Chatbot/bot/actions/actions.py, sharing _extract_and_resolve()]
       Step 1: Qwen2.5 via Ollama (ChatOllama) turns the utterance + recent turns +
               entity_history into a comma-separated term list (coreference/ellipsis-aware,
               does NOT guess spelling)
       Step 2: kb_resolver.py resolves each term to a canonical KB id
       Step 3: Cypher query against Neo4j (non-LOW-confidence edges) + kb_content.py
               (facts.jsonl / passages.jsonl glossary+faq) enrichment -- for a
               _CHILD_DEF_PREDICATES relationship (TERMASUK_JENIS is-a/broader,
               or BERUPA/TERDIRI_DARI "consists of" -- same "parent decomposes
               into standalone child concepts" shape) specifically, each child's
               own definition is pulled in too (capped at 8), so a hub concept like
               "pancamahabutha" or "eteh-eteh sawa" grounds what each of its
               elements actually means instead of the LLM guessing from
               background knowledge
       Step 4: Qwen2.5 synthesizes the final Indonesian answer from that JSON context
               (synth_sys_prompt forbids inventing facts/examples not in the context) ->
               a deterministic Python-built answer (_deterministic_answer) overrides the
               LLM's output if it detects any of: a refusal signal, a fabrication signal
               (answer vocabulary not traceable to the given context -- see
               _has_fabrication_signal), an undefined-target elaboration (a sentence
               describing a relationship target that has no target_definition of its
               own -- e.g. inventing "banten teben adalah keranjang besar..." when
               banten_teben was only ever a bare relationship target in that turn's
               context -- see _has_undefined_target_elaboration; lower per-sentence
               threshold than the whole-answer fabrication check, since a short
               invented clause gets diluted below that check's 0.75 by the rest of an
               otherwise-grounded answer), or a near-verbatim repeat of the bot's own
               immediately preceding turn (_is_near_repeat -- appends a note that no
               further detail is recorded instead of silently re-serving the same
               paragraph under a new phrasing of the question). All four guards exist
               because a small local model doesn't reliably follow the prompt's
               "don't invent"/"don't refuse grounded content"/"say so if you don't
               have this specific detail" rules on its own -- see conersation.md for
               the transcripts that motivated each one
  -> response
```

`Chatbot/bot/llm/` (a Groq rephrase-only wrapper, superseded by the Qwen/Ollama integration) was
dead code — unimported by `actions.py` — and was deleted 2026-09-18. Don't reintroduce a second LLM
path without reconciling it with the Qwen call sites above.

Key modules in `Chatbot/bot/`:
- `actions/actions.py` — two Action classes: `ActionGraphRAG` (normal `ask_ngaben_detail` turns)
  and `ActionLLMFallback` (`nlu_fallback` — retries the same KB-grounded path silently first,
  only drops to a free-form, explicitly-unverified Qwen answer on a genuine resolution miss).
  There is no longer one action class per intent family (definisi/klasifikasi/atribut/etc.) —
  a single LLM-driven pipeline now handles all question shapes.
- `kb_resolver.py` — resolution order: exact name/alias -> `entity_resolution.json` force_merge ->
  modifier-strip retry (itself retrying both the alias table and force_merge) -> rapidfuzz
  (WRatio, threshold ~70-80). Mirrors `Graphing/kb/methodology.md` but done Python-side because
  the graph doesn't store aliases queryably.
- `kb_content.py` — read-only loader for `facts.jsonl` / `passages.jsonl` / `relation_phrases.json`;
  the graph stays authoritative for structure, this module only supplies phrasing and the two
  hand-written passage kinds (`faq`, `glossary`). Its `PREDICATE_FAMILIES` /
  `facts_in_family` / `render_attr` / `faq_search`, and `kb_resolver.py`'s `list_type` / `search`,
  are currently unused by `actions.py` (dormant, not deleted — a more targeted per-intent
  breakdown could reuse them later).
- `KB_DIR` (`.env`, default `../../Graphing/kb`) points both `kb_resolver.py` and `kb_content.py`
  at the same KB build — keep it in sync with whatever `Graphing/kb/build_kb.py` last produced.

**Confidence filtering:** `relations.jsonl` / graph edges carry `confidence` (HIGH/MED/LOW); the
bot and `facts.jsonl` only use non-LOW edges (`WHERE r.confidence <> 'LOW'` / already filtered at
KB-build time) — LOW-confidence relation extraction is ~25% wrong and sits in
`Graphing/kb/output/review_queue.jsonl` for human review, not surfaced to users.

## Regenerating the KB (`Graphing/kb/`)

As of 2026-09-22, `Graphing/kb/` is split into `output/` (everything `build_kb.py` generates:
`entities.json`, `relations.jsonl`, `facts.jsonl`, `passages.jsonl`, `glossary.md`,
`review_queue.jsonl`, `build_report.txt`), `tuning/` (hand-authored curation knobs:
`entity_resolution.json`, `relation_phrases.json`, `review_decisions.json`, `definitions.json`),
and `curation/` (the review/audit tooling: `apply_review.py`, `audit_connectivity.py`,
`build_glossary_review_master.py`, `definition_quality.py`, and their `.md` reports) — done
because the flat folder had become hard to read with all of these mixed together. `build_kb.py`
itself, `README.md`, and `methodology.md` stay at `Graphing/kb/` root.

`Graphing/kb/build_kb.py` (run from `Graphing/kb/`) reads (never writes) upstream extraction/data
files plus `tuning/entity_resolution.json` and `tuning/relation_phrases.json`, and produces the
`output/` files listed above. See `Graphing/kb/README.md` for the full recipe and `methodology.md`
for the entity-resolution/confidence rules. After rebuilding the KB, re-run
`neo4/load_ngaben_to_neo4j.py --source kb` to refresh the graph the bot queries.

Two curated-JSON knobs worth knowing about when the graph is missing a connection or shows a
nonsense one (see `how_it_works.md` §2.5-2.6 for the full mechanics and worked examples):
- `entity_resolution.json`'s **`broader_overrides`** — manual is-a/part-of links for cases the
  automatic multi-word-head heuristic can't derive (it only spots a parent when a multi-word
  surface's *leading* word is the parent's name, never a trailing one, and never for
  single-word children at all). Used to fix e.g. Panca Maha Bhuta's five elements and a batch
  of jenazah/tirtha/galar/kawangen items that referenced an existing graphed concept in their
  own definition text but were never linked to it (92 -> 63 `:Isolated` nodes, 2026-09-17 audit).
- `Graphing/kb/tuning/review_decisions.json` — per-triple `accept` / `reject` / `fix: S | P | O`
  decisions keyed by `"<sentence_id>|<raw subject>|<raw object>"`, consulted by `build_kb.py`
  at **both** the entity-creation loop and the relation-scoring loop (a 2026-09-17 fix — it used
  to only gate relation writing, so a `reject`ed triple's object could still get created as a
  phantom entity with its own auto-derived broader link). Use `reject` for a garbled/fabricated
  triple (e.g. a negated sentence mis-extracted into a fake entity), `fix:` to correct a
  wrong-but-salvageable subject/predicate/object. `accept` also promotes a triple's confidence
  past `LOW` (to `HIGH` if both endpoints resolve cleanly, else `MED`) — the only way to make a
  structurally-fine but low-gazetteer-confidence edge bot-visible without touching the extractor.

**A third failure mode, found and fixed 2026-09-18 (92 -> 63 -> 59 `:Isolated` nodes across the
09-17 and 09-18 passes):** a coordinate list's members (e.g. "eteh-eteh berupa kain putih, kamben,
tapih, ...") sometimes got manually added to `relation_results_ngaben.normalized.json` with some
siblings tagged `object_type: "ENTITY"` and others `"LITERAL"`, for no semantic reason — the
`LITERAL` ones then never became graph edges at all (`build_kb.py`'s relation loop skips
non-`ENTITY` rows outright), just flat attribute strings on the subject, invisible to the bot.
Confirmed live: `leluwur`/`samsam`/`udeng`/etc. all had real, specific, correct KB definitions
that the bot never fetched because of this. Two compounding issues on top: (a) a `LITERAL` sibling
promoted to `ENTITY` can still land at `LOW` confidence if its new entity doesn't resolve to a
gazetteer type — same `review_decisions.json` `accept` fix as above; (b) a long-but-legitimate
multi-word item name (>5 words) trips `build_kb.py`'s `looks_fragment()` sentence-fragment filter
and never reaches `entities.json` at all even after the `object_type` fix — checked whether raising
that threshold was safe first (no: 2 of the pre-existing fragments are genuine garbage clauses a
higher threshold would readmit), so the fix is shortening the specific name instead (to its
core identity, or to a shorter form the corpus's own text already uses elsewhere), not touching
the shared filter. `Graphing/kb/curation/audit_connectivity.py` (new, read-only, run from
`Graphing/kb/curation/`) scans for this pattern — mixed `ENTITY`/`LITERAL` sibling groups,
all-`LITERAL` compositional groups (same issue with no surviving `ENTITY` sibling to signal it),
and isolated nodes whose own definition names another known entity (candidate `broader_overrides`
targets, e.g. how the 09-18 pass found 9 `sasih_*` (calendar month) entities each independently
saying "a month in the Balinese calendar" with no `sasih` parent entity to link to — same shape
as Panca Maha Bhuta, just never noticed). It writes `curation/connectivity_report.md`, a list of
candidates for review, same spirit as `output/review_queue.jsonl` — every finding still needs a
judgment call (generic word vs. specific term worth its own entity), not blind auto-apply.

**The 2026-09-23 semantics audit: TERMASUK_JENIS (is-a) vs. stage-of/used-in/represents.**
User-reported bug: the graph showed `mapegat` (a numbered step, 4 of 8, in the Ngaben
sequence — `ngaben-merge-cleaned.txt` line 32) as `TERMASUK_JENIS ngaben` ("a type of
Ngaben"), which is false — it's a stage *within* Ngaben, not a variant *of* it.
Root cause: `Neo4/load_ngaben_to_neo4j.py` renders **every** entity's `broader` field as
`TERMASUK_JENIS` unconditionally, with no way to say "this parent link is stage-of/
used-in/represents, not is-a" — and `entity_resolution.json`'s `broader_overrides` had,
over several prior sessions, been used for exactly that dual purpose despite the
section's own docstring calling itself "is-a/part-of links." Audited all 47 cross-type
`broader` edges (same-type edges, e.g. SARANA_RITUAL→SARANA_RITUAL, are lower-risk by
construction and were *not* audited) plus all 397 live relations on identity predicates
(ADALAH/SAMA_DENGAN/DIKENAL_SEBAGAI/BERARTI), cross-checked against
`ngaben-merge-cleaned.txt` and, where the corpus didn't settle it (Panca Dewata vs. Nawa
Sanga membership), the open web. Found and fixed:
- **19 stage-of/used-in/represents entities mislabeled as TERMASUK_JENIS** (mapegat,
  tarpana, pabersihan_mati, ayaban_upakara_diuskamaligi, mlaspas_kajang, matur_piuning,
  daun_intaran, malem, saput, sekah, kalpika, padang_lepas, pramakusa, pengulapan,
  boreh, balai_balai_bade, bangbang_rare, pangenteg_linggih, ngerorasin). Fix: a new
  **`broader_suppress`** list in `entity_resolution.json` (checked last in
  `Resolver.resolve()`, wins over both the heuristic and `broader_overrides` — the one
  `build_kb.py` code change this pass made) nulls the false `broader` pointer; 18 of
  the 19 get an explicit typed relation instead (BAGIAN_DARI/DILETAKKAN_DI/
  DILETAKKAN_PADA/MELAMBANGKAN/DIMASUKKAN_KE_DALAM/DIGUNAKAN_SAAT/DILAKUKAN_SAAT, as
  fits — out-of-band S900057-900075, `relation_results_ngaben.normalized.json`, tag
  `manual_addition+kg_semantic_fix`); `ngerorasin` gets no replacement (its old
  `broader`, "atma," was a plain heuristic mis-hit its own definition never supports —
  it already has other real edges, so it doesn't regress to isolated).
- **4 wrong-parent `broader_overrides`** repointed: `sawa_wedana`→ngaben (not sawa —
  corpus line 1191 literally says "Ngaben jenis Sawa Wedana"), `bhuta_yadnya`/
  `pitra_yadnya`→panca_yadnya (not bhuta/pitra — each is "one of the five Panca
  Yadnya" per its own definition, same shape `dewa_yadnya` already used), `tirta_
  pengeringkes`→tirtha (not pangringkes — a holy water isn't "a type of" a ceremony
  stage).
- **2 garbage entities deleted** via `review_decisions.json` `reject` on their source
  rows: `dua_kata` (a meta-linguistic "Pitra Yadnya terdiri dari dua kata" remark about
  the *term's* word-count, mis-extracted as if "dua kata" were a real entity equal to
  both "pitra" and "yadnya") and `samsam_tidak_seperti_tirtha_panglukatan` (a negated
  comparison clause mangled into a fake entity name — same failure class as
  `flag.txt`'s known negation bug).
- **6 more identity-predicate fixes**, incl. one bad prior decision caught and
  reverted: a pre-existing `review_decisions.json` `"fix:"` had overwritten an
  already-correct `tirtha TERBUAT_DARI klungah` (matches S971: "tirtha tersebut dibuat
  dari klungah") into a false `tirtha BERARTI klungah` ("tirtha means klungah") —
  removed, letting the original correct extraction stand. Also rejected `mendiang
  ADALAH pemangku` (S1738 lists pemangku as one example of a past occupation, not an
  identity), `pamerasan ADALAH sejumlah uang kepeng` (S2256 is the corpus's *other*,
  explicitly-disclaimed sense of the polysemous word "Pamerasan" — see open item
  below), `adegan ADALAH atma` (entity resolution had collapsed "tempat atma mendiang"
  down to bare "atma," turning "adegan is the vessel for the soul" into "adegan is the
  soul"); fixed `pitra_yadnya ADALAH upacara_ngelungah` into the correct-direction
  `upacara_ngelungah TERMASUK_JENIS pitra_yadnya` (S971: "jenis ini dinamakan pula
  nglungah" — Ngelungah is a type of Pitra Yadnya, not identical to the whole
  category).

**Verified against the live Neo4j graph, not just the generated files** (549→547
entities, 397→409 relations after the fixes): direct Cypher query confirmed
`mapegat` now edges `BAGIAN_DARI`→`ngaben`, not `TERMASUK_JENIS`.

**Two open items from this pass, deliberately not resolved (judgment calls for the
project owner):**
- `bhuta` went isolated (64→65 isolated nodes) as a direct, expected side effect of
  removing the false `bhuta_yadnya→bhuta` edge — that edge was `bhuta`'s only
  connection in the whole graph. Not a regression; a real, pre-existing gap the wrong
  edge was masking. Needs its own connectivity work (separate corpus research), not
  folded into this pass.
- `pamerasan` conflates two distinct corpus senses into one entity — an adoption/
  family-notice offering item (uang kepeng wrapped in dapdap leaf) vs. a stage within
  the Pabersihan sequence — because entity resolution merges by string match with no
  sense-disambiguation. The offering-sense fact was rejected (removed) rather than the
  entity being split into two; splitting means new ids, re-sorting every existing
  mention/attribute on `pamerasan` by which sense it belongs to, and possibly touching
  `kb_resolver.py`'s alias table and `Chatbot/bot/kb_content.py` — real content-
  modeling call with bot-facing blast radius, left for a dedicated pass.

**Not audited this pass** (scope note for whoever continues): the other 142 same-type
`broader` edges, and the ~370 `relations.jsonl` edges on non-identity predicates
(BERADA_DI/TERBUAT_DARI/MENGGUNAKAN/DILETAKKAN_DI/etc.) — could still hold undiscovered
subject/predicate/object errors of the same general kind `flag.txt` already tracks for
the rule-based extractor.

**Also computed this pass, not a fix but worth recording:** a corpus-traceability ratio
across the (then-)397 live relations, joining each back to its raw extraction row's
`source` tag — **~91% (361/397) trace to one identifiable, quoted corpus sentence;
~8% (32/397) are curator-authored bridging facts** not tied to a single sentence
(synthetic `sentence_id` ≥ 900000, spot-checked for plausibility, not individually
corpus-verified); ~1% ambiguous in the join. At the entity-definition level, 514/549
(93.6%) trace directly to corpus text (435 from the corpus's own glossary section
verbatim, 79 auto-derived from one specific extracted sentence); 35 (6.4%) have no
definition at all (mostly sentence-fragment surface strings that slipped
`looks_fragment()`'s filter — cleanup candidates, not fixed this pass).

Relation-extraction quality auditing (rule-based extractor, ~1 edge in 4 wrong) is tracked via
`Graphing/auditTooling/` — `Graphing/misc/flag.txt` is the hand-audited rubric of known failure
modes (wrong subject/object, nonsense triples, source-text bleed, wrong relation label, dropped
coordinate members, under-extraction) that any further audit pass should follow.
(`Graphing/misc/relation_audit_report.md` and `RELATION_AUDIT_RUNBOOK.md`, the earlier iteration
tracker this superseded, were fully consumed and deleted 2026-09-22.)
`Graphing/auditTooling/reaudit20260907/consolidated.md` (+ 8 per-chunk reports) is a full
source-text re-audit that found ~60 more under-extracted relations across the whole corpus by
reading the raw text directly; the 2026-09-18 pass cross-referenced every one of its FIX/ADD items
against current data — most had already landed as `manual_addition`/`manual_override` triples over
time, a residual ~7 genuinely missing ones (plus the `sasih`/`wuku_kuningan`-`galungan` cluster,
found separately) were added then. Read that report before starting a new source-text audit pass —
large parts of the corpus already converged well as of that check.

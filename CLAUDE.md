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
  see `requirements.txt`'s comment and `how_it_works.md` §3.10 for exactly where each guard is.
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
       Step 2: kb_resolver.py resolves each term to a canonical KB id, after two
               deterministic backstops on the LLM's term: _peel_aspect_words ("warna
               besi" -> "besi"; not in strip_modifiers, which build_kb.py shares) and
               _widen_to_named_term (user said "kawangen jeriji", history-biased LLM
               returned "kawangen" -> use the longer exact name the user typed). When
               the message itself names 2+ terms (resolve_many), a term the LLM carried
               over from the history is dropped -- "apa itu sawa dan apa hubungannya
               dengan jenazah" after a turn about bade came back with bade (2026-09-25)
       Step 3: Cypher query against Neo4j (non-LOW-confidence edges, WITH direction) +
               kb_content.py enrichment. Each edge is handed to the LLM as a directed
               Indonesian sentence (relation_phrases.json templates via KbContent.render),
               never as a bare {relation, target} pair -- the undirected pair let the
               model invert edges ("canang sari dilengkapi soda"). Kind/part/member
               edges (_CHILD_DEF_PREDICATES) are ordered first (cap 40 edges) and the
               child's own definition is attached -- only when the other node IS the
               child. The cap of 24 child definitions per prompt (_CHILD_DEF_CAP) is
               applied in _llm_context AFTER aspect filtering: capping earlier, in
               Cypher order, left asti wedana undefined once ngaben gained its 8 stages
               and the model merged it into sawa wedana (2026-09-25).
               A question aspect ("sebutan lain" / "jenis" / "tahapan")
               narrows the edges to the matching kinds (_ASPECT_PREDICATES); a word-
               meaning question ("arti kata", "kata dasar") gets definitions only, plus
               the compound formed by the resolved words. A relation question about 2+
               terms ("apa hubungan X dengan Y", "X tanpa Y", _RELATION_Q_RE) keeps only
               the edges that link them -- or, if none do, the edges to a node they
               share; if nothing at all links them, every edge stays (_link_filter) --
               plus prompt rule 18, only when it did filter: with every edge of both
               terms the model padded the answer ("sawa ... disertai kakawin ... di
               galar", 2026-09-25).
               Text-only attributes (LITERAL facts: "besi berwarna hitam", "kawangen
               melambangkan ...") are NOT in the graph query; KbContent reads them from
               entities.json and they are added as `facts` ONLY when the question asks
               their aspect (makna / letak / waktu / pelaku / ciri / fungsi / cara,
               _ASPECT_FAMILIES -> kb_content.PREDICATE_FAMILIES). A plain "apa itu X"
               never gets them (2026-09-24).
       Step 4: Qwen2.5 synthesizes the final Indonesian answer. Deterministic guards:
               refusal signal and fabrication signal -> _deterministic_answer
               (DEFINITIONS ONLY since 2026-09-24 -- it used to dump every fact, which is
               where "pitra berwujud sekah kangsen. pitra menerima ..." came from); a
               named set (Panca/Tri/Catur... -- _NUMERAL_SET_RE) gets its missing members
               appended; "X adalah sebutan lain untuk Y" when asked by a real synonym
               (also when the extraction LLM misspelled it and it resolved by
               orthographic key -- "nggerorasin"; X is the user's own spelling,
               _user_spelling) -- and the synthesis prompt's question is rewritten to
               the canonical name
               (asked "lingga sarira", the model wrote "lingga sarira termasuk salah satu
               jenis suksma sarira" even when told they are one thing, 2026-09-25);
               the near-repeat note only for a follow-up that doesn't re-name the term.
               Question-shape rules 12-18 are appended only for their shape (word
               meaning, composition, aspect facts, stages, types, comparison,
               relation). A plain "apa itu X" has no rule for how much to add after
               the definition, so Qwen flips between "definition + a few stages / other
               names" and a bare definition when a hub's edges change ("apa itu
               ngaben" after batch10). Two prompt rules for a closing summary were
               tried 2026-09-25 and reverted: the model still left ngaben bare and
               invented structure elsewhere ("besi: jenisnya perak, tembaga, emas"). Phrases that refer to the prompt itself ("yang terdapat dalam
               konteks tersebut", "seperti yang tercantum dalam konteks") are cut from
               every answer by _strip_meta_phrases -- rule 6 alone did not stop the 7B
               model (2026-09-25).
               KNOWN OPEN (2026-09-25): Qwen 7B still misreads stage-list questions
               whose context is correct -- "tahapan atma wedana" lists its types,
               "tahapan ngaben" numbers mlaspas kajang / gives nguyeg an invented
               ordinal. Proposed fix (building "apa saja jenis/tahapan X" answers from
               the graph without the LLM) is parked until the project owner's senior
               decides. ("ngangsen menggantikan ngerorasin" was a KB fault, not the
               model's: the corpus uses Ngroras/Ngerorasin as Atma Wedana's everyday
               name, and the KB had them as two nodes -- merged 2026-09-25.)
               _has_undefined_target_elaboration was REMOVED 2026-09-24: the refusal log
               showed it discarding ~30 correct answers; its premise (undefined edge
               targets) is closed at the KB level by kb_lint's closure check instead.
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
  modifier-strip retry -> orthographic key (bh/b, th/t, dh/d, ç/s, doubled letters, spaces:
  butha=bhuta, tirta=tirtha, citta=cita) -> token-checked fuzzy (every content token on each side
  must have a 1-edit / ratio>=88 counterpart; an extra or missing word is a different thing --
  this killed surya->sukra, sangaskara->putru_sangaskara, bhuta kala->bhuta, pandawa->pranawa).
  **force_merge values are canonical entity NAMES** (build_kb.py's contract); the bot used to
  treat them as ids, which silently broke 43 of 93 merges until 2026-09-24.
- `kb_content.py` — read-only loader for `facts.jsonl` / `passages.jsonl` / `relation_phrases.json`
  and the entities' text-only `attributes`; the graph stays authoritative for structure, this
  module supplies phrasing, the two hand-written passage kinds (`faq`, `glossary`), and
  `attribute_sentences()`. `PREDICATE_FAMILIES` (question aspect -> edge/attribute predicates) is
  shared by `actions.py` (aspect filtering) and `kb_lint.py` (check 11). `facts_in_family` /
  `faq_search`, and `kb_resolver.py`'s `list_type` / `search`, are unused (dormant, not deleted).
- `KB_DIR` (`.env`, default `../../Graphing/kb`) points both `kb_resolver.py` and `kb_content.py`
  at the same KB build — keep it in sync with whatever `Graphing/kb/build_kb.py` last produced.

**Confidence filtering:** `relations.jsonl` / graph edges carry `confidence` (HIGH/MED/LOW); the
bot and `facts.jsonl` only use non-LOW edges (`WHERE r.confidence <> 'LOW'` / already filtered at
KB-build time) — LOW-confidence relation extraction is ~25% wrong and sits in
`Graphing/kb/output/review_queue.jsonl` for human review, not surfaced to users.

## Quality gates — run these before calling any KB/bot change done (2026-09-24)

Past passes fixed the examples the user reported and proved "done" with counts that could not
see the rest of the bug class, so the same classes kept coming back (see `conersation.md`). Two
gates now make "done" mean the class is closed:

- **`Graphing/kb/curation/kb_lint.py`** (run from `Graphing/kb/curation/` with the bot venv:
  `..\..\..\Chatbot\rasa_bot\Scripts\python.exe kb_lint.py`) — exit 0 required. Blocking checks:
  name hygiene, definitions (none missing, no one-clause fragments), isolated nodes, **term
  closure** (every capitalized term inside any definition resolves non-fuzzily -- "every term
  the bot can say, it can explain"), numeral-set groups have members, every TERMASUK_JENIS pair
  is plain "<parent> <qualifier>" or reviewed, no self-loops, **composition** (what a node is
  made of / contains / comes with is an edge to a defined node -- never only a LITERAL text
  property, which the bot cannot see: soda's nasi/minuman/buah-buahan/jajan sat there unseen),
  **attributes** (check 11: every LITERAL attribute's predicate is in a
  `kb_content.PREDICATE_FAMILIES` aspect, so the bot can show it, and its value is not junk --
  no deictic "tersebut/itu/ini/beliau/nya", no vague head "beberapa/berbagai/tertentu", no
  one-word value after MEMILIKI/MEMPEROLEH/...), **stages** (check 12: BAGIAN_DARI into a
  ritual/stage node means "a stage of" to the bot, so a tool or building there is
  DIGUNAKAN_DALAM -- panguryagan was listed as a Ngaben stage), **genus** (check 13: the term a
  definition files its entity under -- "X adalah [nama sebuah] <genus> ..." -- is linked to it
  when that term is itself an entity; yama purwana tattwa "adalah nama sebuah lontar" had no
  link to lontar, and 54 more like it were linked or waived 2026-09-25), force_merge targets are real
  names, `exclude_from_resolution` empty (trash gets fixed, never hidden). Judgment calls live in
  `tuning/lint_waivers.json` with a reason each -- add there, never re-litigate.
- **`Chatbot/bot/regression/run_regression.py`** — `--tier A` (resolver, plus a fallback check:
  no turn's forbidden pattern may match the definitions the deterministic fallback would say --
  "Satu dua perhiasan pusaka" only surfaced when Ollama was down; seconds) and
  `--tier B` (real `ActionGraphRAG` vs live Neo4j + Ollama, ~4 min, writes `transcript.md`).
  Check `curl http://127.0.0.1:11434/api/tags` first: a Tier B run with Ollama down prints
  `WinError 10061` per turn and its results mean nothing. (`regression/` is gitignored.)
  **Every question the user reports goes into `regression/questions.json`.** Keyword checks are
  weak: read the whole Tier B transcript before reporting anything as fixed.

Definitions written from web sources (corpus silent) are tagged in
`tuning/definition_sources.json` and show up as `definition_source: "glossary (web: ...)"`.
Edits to the rows file must not reuse a (subject, relation, object) already present as a LITERAL
row -- that silently keeps the new ENTITY edge out (build_kb.py's `fix:` now redirects entity
creation too, so a fixed triple no longer mints a phantom node from its old wording, and since
2026-09-25 a LITERAL row's attribute predicate/value as well -- a fixed "ngroras BERASAL_DARI kata
roras" used to stay an attribute "atma wedana berasal dari kata roras").
Web-sourced definitions are listed in `tuning/definition_sources.json`; the user approved the
first 25 on 2026-09-25 (its `_approved` note) -- entries added later still need their review.
The reverse also bites: a `review_decisions.json` key (`sentence_id|subject|object`) has no
object_type, so `reject`ing a LITERAL row also drops an ENTITY row sharing that key (this once
removed `ngerorasin BERASAL_DARI roras`). Check the key against ENTITY rows before rejecting,
and diff `relations.jsonl` before/after any batch of rejects.

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

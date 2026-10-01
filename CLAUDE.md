# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
It holds the current rules only. The dated history of each fix and audit (why a rule exists, with
examples) is in `how_it_works.md` -- its last appendix is the full CLAUDE.md as of 2026-09-30.

## Repo overview

Two coupled subprojects that together build a **Rasa chatbot answering questions about Ngaben
(Balinese cremation ritual) terminology**:

- **`Graphing/`** -- an offline NLP/KB pipeline over a Ngaben source corpus: NER + dependency-rule
  relation extraction -> a curated knowledge base (`Graphing/kb/`) -> loaded into Neo4j.
- **`Chatbot/bot/`** -- the Rasa Open Source 3.6.x project (NLU + rules + custom actions) that
  queries the Neo4j graph and the KB's curated layers to answer in Indonesian.

**Working agreement:** Claude writes the bot files; the user trains, runs, and tests the bot
themselves (see the interactive-command limit below) and audits KB/relation-extraction quality.

## Commands

All Python commands use the venv at `Chatbot/rasa_bot/` (not `.venv`), created with `uv`.
Activation doesn't persist across tool calls, so pass the interpreter explicitly:

```
# install/sync deps (from Chatbot/)
uv pip install --python .\rasa_bot\Scripts\python.exe --override overrides.txt -r requirements.txt

# from Chatbot/bot/
..\rasa_bot\Scripts\rasa.exe train            # non-interactive, safe to run here
..\rasa_bot\Scripts\rasa.exe data validate
..\rasa_bot\Scripts\rasa.exe test
```

`rasa shell`, `rasa interactive`, the `rasa init` prompt and `rasa run actions` need a real console
(`NoConsoleScreenBufferError`) or a persistent foreground process: **the user runs these in their
own PowerShell window**, never through Claude's Bash/PowerShell tool.

KB pipeline (see "Regenerating the KB"):

```
cd Graphing\kb;   python build_kb.py                  # tuning + normalized rows -> kb/output/
cd Graphing\neo4; python load_ngaben_to_neo4j.py      # wipes + reloads Neo4j from kb/output (default --source kb)
```

The loader needs `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` in `.env` (repo root; copy
`.env.example`) and a running Neo4j at `neo4j://127.0.0.1:7687`. `--source raw` loads the old
name-keyed view without node ids -- the bot finds nothing in that graph.

### "Continue the backburner"

Parked and in-progress plans are indexed in root `BACKBURNER.md`, with one step file per plan in
`backburner/`. Both are local and gitignored. The standing resume prompt is at the top of that index:
resume the first IN PROGRESS plan (else the first QUEUED one) and follow its status file. A newly
parked plan gets a row and a status file in the same format before the session ends.

### "Push to shared repo"

When the user says "push to shared repo" (the group's class repo, folder `chatbot-ngaben/`), run
from the repo root:

```
.\sync-to-shared-repo.ps1 -Message "<short summary of what changed>"
```

It syncs this project's **last commit** (not uncommitted edits -- it lists any) into
`C:\Misc\Work\chatbot-project-madya-2026\chatbot-ngaben\`, commits and pushes to
`mangeejjin/chatbot-project-madya-2026` `main`. If the user has uncommitted work they want shared,
ask whether to commit it first. It refuses to run if the shared clone has uncommitted changes;
`-NoPush` stages without committing. It rebuilds the folder (so re-cased paths come out right) and
keeps `Graphing/data/ngaben-merge-cleaned.md`, which exists only in the shared repo. The script is
gitignored (local-only).

## Environment gotchas (Python 3.10 venv on Windows)

- Rasa 3.6.x requires **Python 3.10**, not 3.11. Never move `Chatbot/rasa_bot/` -- its `.exe`
  shims hard-code the venv path.
- `pyyaml` is overridden to `>=6.0.1` via `overrides.txt` (Rasa's `5.4.1` pin fails to build).
- **Ollama is a hard runtime dependency.** `actions.py` calls a local Ollama `qwen2.5` for term
  extraction and answer synthesis: `ollama pull qwen2.5`, then `ollama serve` (or the desktop app).
  Every call goes through `_llm_invoke`: `LLM_TIMEOUT` (default 120 s) is the gap allowed between
  streamed chunks, and after a failure further calls fail at once for 60 s. On failure the bot
  answers from definitions (`_deterministic_answer`), or a fixed "gangguan teknis" message on the
  free-form fallback path.
- **Three patches live inside the venv** -- reapply all three if it is ever recreated:
  - `rasa/engine/storage/local_model_storage.py` `_extract_archive_to_directory`: drop the
    hardcoded `\\?\` long-path prefix (else `WinError 123` loading any model).
  - `rasa_sdk/endpoint.py` `create_app` and `rasa/core/run.py` `_create_app_without_api`:
    `app.config.RESPONSE_TIMEOUT = 300` right after `app = Sanic(...)`. Both Sanic apps otherwise
    default to 60 s, and a broad question (a hub with many children) then returns 503. Only the
    `--enable-api` branch sets a long timeout itself; `rasa shell` does not use it.

## Architecture: how a question gets answered

```
user utterance (Indonesian)
  -> Rasa NLU (DIET; lookup_istilah.yml feeds RegexFeaturizer only)
  -> intent: sapa / pamit / bot_challenge / out_of_scope / ask_ngaben_detail / nlu_fallback
  -> RulePolicy (every intent has a rule; no TED policies):
       ask_ngaben_detail -> ActionGraphRAG
       nlu_fallback      -> ActionLLMFallback (KB path first; free-form only on a real miss)
       out_of_scope      -> ActionOutOfScope (answers anyway when _names_kb_term: the message
                            names a KB term as written and that term is ngaben or nothing else
                            is left; nasi/kopi/emas are KB terms, so "resep nasi goreng" stays out)
  all in Chatbot/bot/actions/actions.py, sharing _extract_and_resolve() and _synthesize()
```

1. **Terms.** `_mentioned_terms` scans the message's n-grams against the KB (exact before fuzzy; a
   class word before its member is dropped: "sasih malamasa" is malamasa; a 3-letter word only as
   an exact name: abu, air, lis, uye; a lone everyday word never as a fuzzy hit: "tingkat" is not
   tingkatan upacara) and returns the words no term explains. The Qwen extraction
   call (coreference/ellipsis over recent turns + `entity_history`) runs only when needed: no term
   found, leftover words, a pronoun/anaphor, or a relation/comparison question. Backstops on its
   terms: `_META_TERMS`, grounding in the conversation, `_peel_aspect_words`,
   `_widen_to_named_term`. When the message names its own terms, terms carried from the history
   are dropped (except a one-term relation/comparison question). A message naming no term is
   matched against definitions (`_definition_hit`: every content word, exactly one entity --
   "bayi yang giginya belum tanggal" is upacara ngelungah). A "hari ... baik/dihindari/..."
   question adds dewasa_ngaben; a sumber question drops the generic `lontar`. **Topic rule:**
   `current_entity` goes first when the message names no term and points back (or is a bare
   question with no leftover), or names a term plus a standalone itu/ini/tersebut/tadi that does
   not follow a named surface (`_points_back`); never for "yang pertama/terakhir". Otherwise the
   message's own terms come first; `current_entity` is the first of them.
2. **Resolve.** `kb_resolver.py`: exact name/alias -> `force_merge` (values are canonical entity
   NAMES) -> modifier strip -> orthographic key (bh/b, th/t, doubled letters, spaces) -> "-nya" ->
   one edit on a long whole key ("typo") -> token-checked fuzzy (every content token on each side
   needs a close counterpart). In the edit tiers, a query word that is an everyday Indonesian word
   (lowercase, 3+ times in `Graphing/data/20k_mdee_gazz.txt`, read at load) matches only as written
   (kalangan is not karangan, bayi not bayu); a word of some KB name changes only by a vowel slip
   (kahang is not kajang); otherwise a consonant slip counts from 6 letters (sulinggi).
3. **Retrieve.** Cypher by KB id (non-LOW edges, with direction, cap 200, kinds/parts/members
   first) + `kb_content.py`. Each edge reaches the LLM as a directed Indonesian sentence
   (`relation_phrases.json` via `KbContent.render`), never a bare pair. Child definitions are
   attached only when the other node is the child (cap 24 after aspect filtering).
   **Aspect filter:** the question's wording picks families in `kb_content.PREDICATE_FAMILIES`
   (`_ASPECT_FAMILIES`: sebutan lain, jenis, tahapan, komposisi, simbol, lokasi, waktu, pelaku,
   ciri, fungsi, sarana, sumber; "cara" only when nothing else matched, or with a process word --
   alur/proses/prosesi/langkah/"dari awal sampai" map to tahapan AND cara). An entity with any edge,
   attribute, sarana_facts or source_facts of the asked families keeps only those. A why-question
   maps to fungsi AND simbol. A contents question (isi/berisi/terbuat/bahan/dilengkapi, not
   unsur/terdiri/jenis) drops kinds and keeps only composition edges where the term is the whole
   (`_PART_IS_SUBJECT` gives the part->whole predicates). A stages question orders the term's
   stages by the number their definitions state. "sumber" pulls DIJELASKAN_DALAM/MERINCI from the
   term's kinds/stages (`_source_facts`). **Class filter** (`_class_filter`): a list question
   ("apa saja"/"sebutkan"/"C apa") whose first term C has kinds, plus a term X after
   untuk/dalam/saat/...: X's edges and sarana_facts keep only kinds of C (is-a, 3 hops, broader +
   TERMASUK_JENIS rows); C keeps only its kinds whose definition names X/aliases/kinds or that X
   reaches.
   Text-only attributes (LITERAL facts) are shown only for their aspect, never for "apa itu X".
   Word-meaning questions get definitions + `asal_kata` only. A relation question about 2+ terms
   keeps only the linking edges (`_link_filter`; all edges if nothing links them). "sarana"
   questions list what the term and its stages (`BAGIAN_DARI*1..2`) use (`_stage_sarana_facts`,
   buildings excluded); `_complete_sarana_lists` appends any group the answer mostly left out.
   (`sangaskara` reaches ngaben through `pabersihan BAGIAN_DARI ngaben`, added 2026-10-01, so
   pengaskaran's banten are in "sarana ngaben".)
4. **Synthesize.** Qwen with `num_ctx` `LLM_NUM_CTX` (12288); compact JSON trimmed to
   `_PROMPT_CHAR_BUDGET`, question repeated after the context (Ollama's default 4096 truncated
   hub prompts into English non-answers). Rule 11 (keep each statement with its own subject) is
   standing; question-shape rules (12-26) are appended only for their shape: 21 why (a stated reason
   only, else "Maaf, alasannya ..."; a version forbidding that opening made Qwen invent reasons), 22
   days from dewasa ngaben's wuku/wewaran, 23 an asked aspect with no fact on any term -> "not
   recorded, never biasanya/mungkin" (`_aspect_present`; fungsi/simbol count outgoing edges only), 24 allowed/
   required (no "tidak boleh" without a stated prohibition), 25 class list, 26 "hanya itu?".
   A contents-only question with no composition fact and no content in the definition gets
   "Maaf, isi atau bahan X belum tercatat" without the LLM (it invented banten peras's contents).
   Deterministic guards after the call: an answer cut at `LLM_NUM_PREDICT` (done_reason "length")
   is trimmed to its last full sentence; English/empty -> one retry, then definitions; refusal ->
   definitions only for a plain "apa itu X", else kept + first definition sentence; fabrication
   ratio (> 0.75 of content words outside the context vocabulary, which includes sarana_facts and
   source_facts) -> definitions or an honest miss; `_tidy_answer` (Cyrillic look-alikes, prompt
   meta-phrases, prompt field names); `_strip_why_refusal` (that opening is cut when a purpose/meaning fact exists and
   something follows it);
   `_drop_speculation` (a sentence hedging with mungkin/biasanya/umumnya/... that the context never
   uses, when half or more of its other content words are ungrounded too);
   `_fix_unstated_prohibition` (whether-questions: a bare "tidak boleh" first line is cut, and with
   no prohibition in the context so is every sentence claiming one); `_fix_only_that`
   ("Tidak, hanya itu" -> "Ya, yang tercatat hanya itu"); `_fix_kind_claims` (a stage is not a "jenis"); `_complete_set_members` (numeral sets; skipped when the set has more
   members than its numeral -- the definition explains the variants); `_complete_kind_lists` (plain
   "apa itu X" or a pure jenis question only: an answer naming >= half of the term's kinds gets
   the rest); `_complete_day_rules` (a day question missing "wuku" or "sasih" gets dewasa ngaben's
   sentence about that half); `_complete_sarana_lists`;
   `_complete_stage_order` (stages question: a stage numbered unlike its definition, listed twice,
   or missing -> "Urutan tahapan menurut sumber: 1. ..." from the definitions' numbers);
   `_add_literal_meaning` (word meaning keeps the BERARTI_HARFIAH phrase); "X adalah sebutan lain
   untuk Y" for a real synonym; a near-repeat note. The synthesis question collapses a doubled word
   after the synonym swap ("nyiramang layon layon"); `also_called` drops aliases containing "/".
   KNOWN OPEN: Qwen 7B misreads stage lists whose context is correct ("apa saja tahapan dalam
   ngaben" numbers stages wrongly); `_complete_stage_order` appends the corpus order as a guard,
   but building those answers from the graph without the LLM is parked until the project owner's
   senior decides.

`Chatbot/bot/llm/` (a Groq rephrase wrapper) was deleted 2026-09-18 -- don't reintroduce a second
LLM path without reconciling it with the call sites above.

Key modules in `Chatbot/bot/`: `actions/actions.py` (the three actions above); `kb_resolver.py`;
`kb_content.py` (facts, glossary definitions, attributes, templates, `PREDICATE_FAMILIES` --
shared with `kb_lint.py`). `KB_DIR` (`.env`, default `../../Graphing/kb`) points both at the same
KB build. Curation logs: `actions/llm_refusal_log.jsonl`, `unresolved_log.jsonl`,
`neo4j_error_log.jsonl` (the regression harness writes to `regression/logs/` instead).

**Confidence:** edges carry HIGH/MED/LOW; the bot and `facts.jsonl` use non-LOW only. LOW
extraction is ~25% wrong and waits in `Graphing/kb/output/review_queue.jsonl`.

## Quality gates -- run before calling any KB/bot change done

Past passes fixed the reported examples and proved "done" with counts that could not see the rest
of the bug class (see `conersation.md`). "Done" means the class is closed:

- **`Graphing/kb/curation/kb_lint.py`** (from `Graphing/kb/curation/`:
  `..\..\..\Chatbot\rasa_bot\Scripts\python.exe kb_lint.py`) -- exit 0 required. 14 blocking
  checks: names, definitions, isolated nodes, term closure (every capitalized term in a
  definition resolves non-fuzzily), numeral-set groups (>= 2 distinct members and no more than
  the numeral; waiver key `<id>><n>`, e.g. `panca_datu>5`), TERMASUK_JENIS naming, self-loops,
  composition (never only a LITERAL property), attributes (predicate in a family, no junk value),
  stages (BAGIAN_DARI into a stage only from a stage), genus (a definition's head term is linked),
  **edge_aspects** (every live edge predicate is in a `PREDICATE_FAMILIES` family -- 97 were not
  until 2026-09-30, so aspect questions dropped their edges), force_merge targets are names,
  `exclude_from_resolution` empty. Judgment calls go in `tuning/lint_waivers.json` with a reason.
- **`Chatbot/bot/regression/run_regression.py`** (from `Chatbot/bot/`; `regression/` is gitignored):
  `--tier A` (resolver probes, fallback-definition leaks, out_of_scope rescue on every
  `out_of_scope` NLU example + probes; seconds), `--tier B` (real `ActionGraphRAG` vs live Neo4j +
  Ollama, ~10 min, writes `transcript.md`; check `curl http://127.0.0.1:11434/api/tags` first), and
  `--tier N [--model x.tar.gz]` (NLU intents). **Every question the user reports goes into
  `regression/questions.json`.** Keyword checks are weak: read the whole Tier B transcript before
  reporting anything as fixed. Tier B is not fully deterministic (Ollama at temperature 0 still
  varies between runs): re-run a single failure before blaming a change.

Definitions written from web sources are tagged in `tuning/definition_sources.json`; its
`_approved` note records what the user reviewed (the first 25, the 7 banten of 2026-09-29, and bade's
"lazimnya" web part on 2026-10-01). Still unreviewed: kidung, kakawin, the ten Dasa Mala terms, and
daksina and daksina tapakan (container and contents). A term neither
the corpus nor a clear web source describes gets a definition saying only what the corpus says
(where it is used) -- never a guess -- and never lists its siblings (the model read "ditumbuk
bersama cengkeh, mesui ..." as the item's own contents).

## Regenerating the KB (`Graphing/kb/`)

Layout: `output/` (everything `build_kb.py` generates), `tuning/` (hand-authored knobs),
`curation/` (review/audit tooling and reports). `build_kb.py` reads (never writes)
`neo4/relation_results_ngaben.normalized.json`, `data/ngaben-glossary.txt` (the definitions:
`* Term:  Definition.` lines), `data/ngaben-dictionary.json`, `data/normalization-ngaben.json`,
`neo4/node_aliases.json` and `tuning/`. After a rebuild: lint, reload Neo4j, regression. When
entity names/aliases changed, also regenerate the NLU lookup (`Chatbot/bot`:
`..\rasa_bot\Scripts\python.exe scripts\gen_lookup.py`), retrain, and run Tier N. Keep the
docs current in the same pass: `Graphing/kb/README.md`, `methodology.md`, `how_it_works.md`,
`RASA-DEVIATIONS.md`, and regenerate `curation/connectivity_report.md`
(`audit_connectivity.py`).

Rules that are easy to break:
- **Manual KB fixes live only in `relation_results_ngaben.normalized.json`** (source tags
  `manual_addition+...`, mostly sentence ids >= 900000; 1,482 of 1,859 rows). `neo4/normalize.py` refuses to
  overwrite it while it holds rows the run would not produce (`--force` overrides -- don't).
  New rows: `object_type: "ENTITY"` (a LITERAL row never becomes an edge), labels set, a
  `context_sentence` quoting the corpus line.
- **`tuning/review_decisions.json`** keys are `sentence_id|subject|object` with no object_type:
  `reject` on a LITERAL row also drops an ENTITY row sharing the key -- check first, and diff
  `relations.jsonl` before/after a batch. `accept` promotes a LOW edge; `fix: S | P | O`
  corrects a triple (it also redirects entity creation and LITERAL attributes).
- **`tuning/entity_resolution.json`**: `force_merge` (surface -> canonical NAME; a tuning entry
  overrides `data/normalization-ngaben.json`, e.g. `"wadah": "wadah"`), `broader_overrides`
  (is-a/part-of the head-word heuristic can't derive), `broader_suppress` (a false parent; wins
  over both), `type_overrides`. `load_ngaben_to_neo4j.py` renders every `broader` as
  TERMASUK_JENIS, so a stage/used-in/represents link must be a typed relation row instead.
  A force_merge must name the same thing: "lubang uang kepeng" -> "gulungan daun sirih" made the
  KB say the lekesan goes into itself (fixed 2026-09-30).
- A new name one edit away from an existing surface can capture it in the resolver's typo tier
  ("upakara pamerasan" took "upacara pamerasan"); check near names and pin with force_merge.
- `looks_fragment()` drops names over 5 words: shorten the name, don't loosen the filter.
- Generic words that are also KB terms: `kasa` -> sasih kasa (use `kain kasa`), `pasucian` ->
  pabersihan (the tetandingan banten is `banten pasucian`), `wadah` is the cremation tower.

Curation references: `curation/sarana_coverage_report.md` (sarana vs corpus; the 2026-09-30 pass
added the tetandingan L338-547 banten per stage, the tirta pangentas list, and every "made of /
contains" statement in the corpus, 102 nodes), `curation/audit_connectivity.py`,
`Graphing/misc/flag.txt` (relation-extraction failure modes), and
`Graphing/auditTooling/reaudit20260907/consolidated.md` (read before a new source-text audit).
Not yet audited: the same-type `broader` edges and the non-identity relation predicates.

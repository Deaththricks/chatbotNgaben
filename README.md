# Ngaben chatbot

A Rasa chatbot that answers questions, in Indonesian, about the terms of Ngaben (the Balinese
cremation ritual). It looks terms up in a knowledge graph (Neo4j) built from a Ngaben source text
and phrases the answer with a local LLM (Qwen 2.5 via Ollama).

## What you need

- **Python 3.10** (Rasa 3.6 does not run on 3.11) and [uv](https://docs.astral.sh/uv/)
- **Neo4j 5** (Desktop or server) listening on `neo4j://127.0.0.1:7687`
- **Ollama** (https://ollama.com) with the `qwen2.5` model

## Setup (once)

From the repo root, in PowerShell:

```
# 1. Python environment (keep it at Chatbot\rasa_bot: its .exe files hard-code that path)
cd Chatbot
uv python install 3.10
uv venv rasa_bot --python 3.10
uv pip install --python .\rasa_bot\Scripts\python.exe "setuptools<81" pip
uv pip install --python .\rasa_bot\Scripts\python.exe --override overrides.txt -r requirements.txt
cd ..

# 2. Settings: copy the example and fill in your Neo4j password
copy .env.example .env

# 3. The LLM
ollama pull qwen2.5
```

**Three small patches inside the environment (Windows).** Without them the bot cannot load its
model, or answers to broad questions time out:

1. `Chatbot\rasa_bot\Lib\site-packages\rasa\engine\storage\local_model_storage.py`, function
   `_extract_archive_to_directory`: remove the hard-coded `\\?\` long-path prefix and call
   `tar.extractall(temporary_directory)` plainly (otherwise `OSError: [WinError 123]`).
2. `Chatbot\rasa_bot\Lib\site-packages\rasa_sdk\endpoint.py`, function `create_app`, and
3. `Chatbot\rasa_bot\Lib\site-packages\rasa\core\run.py`, function `_create_app_without_api`:
   add `app.config.RESPONSE_TIMEOUT = 300` right after `app = Sanic(...)` (the default 60 s
   returns a 503 on questions with many facts).

**Load the knowledge graph into Neo4j** (Neo4j running; this wipes and reloads the database):

```
cd Graphing\neo4
..\..\Chatbot\rasa_bot\Scripts\python.exe load_ngaben_to_neo4j.py
cd ..\..
```

**Train the bot:**

```
cd Chatbot\bot
..\rasa_bot\Scripts\rasa.exe train
```

## Run

Keep Neo4j and Ollama running, then open two PowerShell windows in `Chatbot\bot`:

```
# window 1: the action server (answers the questions)
..\rasa_bot\Scripts\rasa.exe run actions

# window 2: chat in the terminal
..\rasa_bot\Scripts\rasa.exe shell
```

Try `apa itu ngaben`, `apa saja tahapan dalam ngaben`, `mangle terbuat dari apa`.
If Ollama is down the bot still answers, from the stored definitions only.

## What is in this repo

| Path | What it is |
|---|---|
| `Chatbot/bot/` | the Rasa project: NLU data, rules, domain, and the custom actions (`actions/actions.py`) with the term resolver (`kb_resolver.py`) and KB reader (`kb_content.py`) |
| `Chatbot/requirements.txt`, `overrides.txt` | Python dependencies |
| `Graphing/kb/output/` | the built knowledge base the bot and the loader read (entities, relations, facts, passages) |
| `Graphing/kb/tuning/` | hand-made KB settings and decisions (name merges, sentence templates, raw materials, ...) |
| `Graphing/neo4/load_ngaben_to_neo4j.py` | loads `Graphing/kb/output/` into Neo4j |
| `Graphing/neo4/relation_results_ngaben.normalized.json` | every relation row, including the hand-made fixes (the KB's source) |
| `Graphing/data/` | the Ngaben source text, its glossary of definitions, and the word list the resolver reads (`20k_mdee_gazz.txt`) |
| `Graphing/knowledge_processing.ipynb`, `Graphing/results/` | the NLP notebook (NER, dependency parsing, relation extraction) and its outputs |

The tools that rebuild and check the knowledge base (`build_kb.py`, `curation/`, `normalize.py`)
are kept out of this repo; the checked-in `Graphing/kb/output/` is the finished build.

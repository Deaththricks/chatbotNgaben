"""Route Graphing/Neo4/definitions.json into the KB's existing human-review
workflow instead of merging it into the build automatically.

definitions.json has no entity ids (free-text names only) and never passed
through build_kb.py's confidence/review machinery, so it's treated the same
way glossary_draft_review*.md's content was: cross-checked against
kb_resolver + a deterministic quality gate, then handed to a human for the
actual sign-off. See PROJECT plan, Goal 4 Phase B.

Outputs (never overwrites entities.json or anything build_kb.py reads):
  - glossary_draft_review_batch3.md  -- candidates that resolve to a
    currently-undefined KB entity AND pass definition_quality's gate, in the
    same checkbox format batches 1/2 already used.
  - definition_review_queue.jsonl    -- everything else (unresolved name,
    already-defined entity, or failed the quality gate), same shape as
    review_queue.jsonl, for case-by-case adjudication.

Usage (from Graphing/kb/, using the bot's venv so kb_resolver's deps resolve):
  ..\..\Chatbot\rasa_bot\Scripts\python.exe definitions_to_review.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "Chatbot" / "bot"))

from kb_resolver import get_resolver  # noqa: E402
from definition_quality import check_definition  # noqa: E402

DEFINITIONS_JSON = HERE.parent / "Neo4" / "definitions.json"
ENTITIES_JSON = HERE / "entities.json"
BATCH3_MD = HERE / "glossary_draft_review_batch3.md"
REVIEW_QUEUE = HERE / "definition_review_queue.jsonl"


def main() -> None:
    resolver = get_resolver()
    entities = {e["id"]: e for e in json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))}
    defs = json.loads(DEFINITIONS_JSON.read_text(encoding="utf-8"))

    confident: list[tuple[str, str, str]] = []
    review: list[dict] = []

    for item in defs:
        name = (item.get("name") or "").strip()
        definition = (item.get("definition") or "").strip()
        if not name:
            continue

        match = resolver.resolve(name)
        if match is None:
            review.append({
                "kind": "definition_candidate",
                "key": name,
                "reasons": ["name does not resolve to a known KB entity"],
                "source_name": name,
                "definition": definition,
                "decision": "",
            })
            continue

        entity = entities.get(match.id, {})
        if entity.get("definition"):
            review.append({
                "kind": "definition_candidate",
                "key": match.id,
                "reasons": [
                    f"entity '{match.id}' already has a definition "
                    f"(source: {entity.get('definition_source')})"
                ],
                "source_name": name,
                "definition": definition,
                "decision": "",
            })
            continue

        reasons = check_definition(definition, resolver)
        if reasons:
            review.append({
                "kind": "definition_candidate",
                "key": match.id,
                "reasons": reasons,
                "source_name": name,
                "definition": definition,
                "decision": "",
            })
        else:
            confident.append((match.id, entity.get("name") or match.name, definition))

    confident.sort(key=lambda t: t[1].lower())

    lines = [
        "# Glossary Draft — Batch 3 (from Graphing/Neo4/definitions.json)",
        "",
        "Same process as batch 1/2 (`glossary_draft_review.md`, "
        "`glossary_draft_review_batch2.md`): drafts pulled from "
        "`Graphing/Neo4/definitions.json`, cross-checked against kb_resolver "
        "(must resolve to a KB entity with no existing definition) and "
        "`definition_quality.py`'s deterministic gate (length, boilerplate, "
        "encoding, circular-reference heuristics). Review/correct against the "
        "source corpus (`Graphing/Data/ngaben-merge-cleaned.txt`), check the "
        "box when done, then apply into the Glosarium section the same way "
        "batch 1 was applied.",
        "",
        "**Status:** DRAFT — nothing applied yet.",
        "",
        f"## Confident drafts ({len(confident)} terms -- resolved to a "
        f"currently-undefined entity, passed the quality gate)",
        "",
    ]
    for eid, ename, definition in confident:
        lines.append(f"- [ ] `* {ename}:  {definition}`")
    BATCH3_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with REVIEW_QUEUE.open("w", encoding="utf-8") as f:
        for rec in review:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"{len(defs)} definitions.json entries processed")
    print(f"{len(confident)} confident drafts -> {BATCH3_MD.name}")
    print(f"{len(review)} routed to review -> {REVIEW_QUEUE.name}")


if __name__ == "__main__":
    main()

"""Merge every currently-undefined KB entity's review material into ONE file.

Consolidates:
  - Graphing/kb/glossary_draft_review_batch2.md's "Confident drafts" (facts-based
    drafts, hand-curated)
  - Graphing/Neo4/definitions.json (LLM-paraphrased drafts, gated by
    definition_quality.py)
  - Graphing/kb/facts.jsonl (supporting facts, via kb_content.facts_for(), for
    entities with no draft at all -- something to write from)

into Graphing/kb/glossary_review_master.md, tiered by how much material exists,
so a full pass over every undefined entity is one scroll instead of four files.
Supersedes batch2/batch3 as the single review surface going forward; batch2/
batch3 are left on disk (already-checked boxes in batch2 aren't lost) but this
file is now the one to work through.

Usage (from Graphing/kb/, using the bot's venv so kb_resolver's deps resolve):
  ..\\..\\Chatbot\\rasa_bot\\Scripts\\python.exe build_glossary_review_master.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "Chatbot" / "bot"))

from kb_resolver import get_resolver  # noqa: E402
from kb_content import get_content  # noqa: E402
from definition_quality import check_definition  # noqa: E402

ENTITIES_JSON = HERE / "entities.json"
DEFINITIONS_JSON = HERE.parent / "Neo4" / "definitions.json"
BATCH2_MD = HERE / "glossary_draft_review_batch2.md"
OUT_MD = HERE / "glossary_review_master.md"

_BATCH2_LINE_RE = re.compile(r"^- \[.\] `\*\s*([^:]+):\s*(.+?)`\s*$")


def parse_batch2_confident(text: str) -> dict[str, str]:
    """name (as written) -> draft definition, from batch2's Confident drafts section."""
    out: dict[str, str] = {}
    in_section = False
    for line in text.splitlines():
        if line.startswith("## Confident drafts"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        m = _BATCH2_LINE_RE.match(line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def main() -> None:
    resolver = get_resolver()
    content = get_content()
    entities = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in entities}

    batch2_raw = BATCH2_MD.read_text(encoding="utf-8")
    batch2_drafts_by_name = parse_batch2_confident(batch2_raw)
    batch2_by_id: dict[str, str] = {}
    for name, draft in batch2_drafts_by_name.items():
        m = resolver.resolve(name)
        if m:
            batch2_by_id[m.id] = draft

    defs_json = json.loads(DEFINITIONS_JSON.read_text(encoding="utf-8"))
    defsjson_by_id: dict[str, tuple[str, list[str]]] = {}
    for item in defs_json:
        name = (item.get("name") or "").strip()
        definition = (item.get("definition") or "").strip()
        if not name or not definition:
            continue
        m = resolver.resolve(name)
        if not m:
            continue
        reasons = check_definition(definition, resolver)
        # Prefer the first (only) definitions.json entry that resolves here;
        # don't overwrite if this id already has one from an earlier row.
        defsjson_by_id.setdefault(m.id, (definition, reasons))

    undefined_ids = [
        e["id"] for e in entities
        if not (e.get("definition") or "").strip()
        and e["id"] not in resolver.excluded_ids
    ]

    tier_a, tier_b, tier_c, tier_d = [], [], [], []
    for eid in undefined_ids:
        e = by_id[eid]
        name = e.get("name") or eid
        b2 = batch2_by_id.get(eid)
        dj = defsjson_by_id.get(eid)
        facts = content.facts_for(eid, limit=6)

        if b2 or (dj and not dj[1]):
            tier_a.append((name, eid, b2, dj, facts))
        elif dj:
            tier_b.append((name, eid, b2, dj, facts))
        elif facts:
            tier_c.append((name, eid, b2, dj, facts))
        else:
            tier_d.append((name, eid, b2, dj, facts))

    for tier in (tier_a, tier_b, tier_c, tier_d):
        tier.sort(key=lambda t: t[0].lower())

    def render_entry(name, eid, b2, dj, facts) -> list[str]:
        lines = [f"- [ ] **{name}** (`{eid}`)"]
        if b2:
            lines.append(f"  - draft (batch 2, facts-based): {b2}")
        if dj:
            definition, reasons = dj
            flag = f"  -- flagged: {'; '.join(reasons)}" if reasons else ""
            lines.append(f"  - draft (definitions.json){flag}: {definition}")
        if facts:
            lines.append(f"  - supporting facts: {'; '.join(facts)}")
        if not b2 and not dj and not facts:
            lines.append("  - nothing to go on -- check the source corpus directly")
        return lines

    out = [
        "# Glossary Review — Master List",
        "",
        f"Every one of `entities.json`'s {len(undefined_ids)} currently-undefined "
        "entities (out of 477 total), in one place: draft text from "
        "`glossary_draft_review_batch2.md` and/or `Graphing/Neo4/definitions.json` "
        "where available, quality-gate flags on the latter, and supporting facts "
        "from `facts.jsonl` as raw material where no draft exists at all. "
        "Supersedes batch 2/3 as the single review surface -- generated by "
        "`build_glossary_review_master.py`, safe to regenerate any time.",
        "",
        "**How to apply an approved definition:** add it to the \"11. Glosarium\" "
        "section of `Graphing/Data/ngaben-merge-cleaned.txt` in "
        "`* Term:  Definition.` form (same as batch 1), then rebuild "
        "(`python build_kb.py` from `Graphing/kb/`) and reload "
        "(`python Neo4/load_ngaben_to_neo4j.py --source kb` from `Graphing/`).",
        "",
        f"- Tier A -- ready to review ({len(tier_a)}): a solid draft already exists.",
        f"- Tier B -- draft exists but flagged ({len(tier_b)}): definitions.json "
        "text failed the automated quality gate (thin/circular/boilerplate/"
        "encoding) -- read it with extra scrutiny.",
        f"- Tier C -- facts only, no draft ({len(tier_c)}): write from the listed "
        "facts.",
        f"- Tier D -- nothing at all ({len(tier_d)}): needs a direct look at the "
        "source corpus.",
        "",
        "---",
        "",
        f"## Tier A -- ready to review ({len(tier_a)})",
        "",
    ]
    for entry in tier_a:
        out.extend(render_entry(*entry))
    out += ["", f"## Tier B -- draft exists but flagged ({len(tier_b)})", ""]
    for entry in tier_b:
        out.extend(render_entry(*entry))
    out += ["", f"## Tier C -- facts only, no draft ({len(tier_c)})", ""]
    for entry in tier_c:
        out.extend(render_entry(*entry))
    out += ["", f"## Tier D -- nothing at all, needs source-text research ({len(tier_d)})", ""]
    for entry in tier_d:
        out.extend(render_entry(*entry))

    OUT_MD.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(undefined_ids)} undefined entities -> {OUT_MD.name}")
    print(f"  Tier A (ready): {len(tier_a)}")
    print(f"  Tier B (flagged draft): {len(tier_b)}")
    print(f"  Tier C (facts only): {len(tier_c)}")
    print(f"  Tier D (nothing): {len(tier_d)}")


if __name__ == "__main__":
    main()

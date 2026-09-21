"""
audit_connectivity.py -- find candidate missing/broken graph connections in the
Ngaben KB, for human (or Claude) review. Read-only: writes a report, never
touches entities.json/relations.jsonl/relation_results_ngaben.normalized.json
itself. Companion to build_kb.py, same way definition_quality.py and
apply_review.py are.

Why this exists: a 2026-09-18 audit found that "everything that should be
connected, isn't" mostly traces back to a handful of reproducible patterns in
relation_results_ngaben.normalized.json (upstream of build_kb.py), not to the
KB build itself:

  1. Coordinate-list siblings split between object_type ENTITY and LITERAL for
     no semantic reason -- e.g. eteh-eteh sawa's 17 components, where 7 were
     ENTITY and 9 were LITERAL. build_kb.py's relation-building loop silently
     skips every LITERAL row, so those 9 never became graph edges at all; they
     just turned into flat attribute strings on the subject.
  2. The same pattern with NO surviving ENTITY sibling (all-LITERAL groups) --
     invisible to pattern 1's contrast signal, needs its own scan.
  3. A KB-wide source-text audit (Graphing/audit_tooling/reaudit_20260907/)
     had already found ~60 more under-extracted relations by reading the raw
     corpus; most were applied over time but a residual few were not -- that
     reconciliation was done by hand this pass, cross-referencing the 8 chunk
     reports against current data (not something this script re-derives).
  4. Entity families whose own definitions all name the same missing parent
     concept (e.g. the 9 "sasih_*" entities each saying "a month in the
     Balinese calendar", but no "sasih" entity existed to link them to) --
     same shape as the pre-existing Panca Maha Bhuta fix in
     entity_resolution.json's broader_overrides, just not yet found for other
     families. This script's isolated-node scan surfaces candidates for that,
     filtered against ubiquitous "hub" words (ngaben, jenazah, sawa, atma, ...)
     that appear in nearly every definition and are not a real signal on their
     own -- edit _HUB_WORDS below if the corpus changes enough to need it.

A 2026-09-18 graph-fix pass (working off a hand-audit in conersation.md) found
three more reproducible patterns while looking up specific entities, none of
which the checks above catch, so they're added here rather than as a one-off
script:

  5. Self-loops (relations.jsonl subject_id == object_id) -- almost always an
     anaphora/coreference mis-resolution within one sentence ("X ... it ...")
     rather than a real reflexive fact. Found on mangle (x3), sasih_karo,
     nganyut, anggapan_ani_ani_atau_ketam and others.
  6. Dangling references -- a relations.jsonl edge (or an entity's `broader`
     pointer) whose endpoint id isn't in entities.json at all, usually because
     the id was later dropped (fragment filter, a `reject` decision) after the
     edge referencing it was written.
  7. Near-duplicate ids -- two ids that read like two separate extractions of
     the same concept, either typo-level spelling drift (panebusan vs
     penebusan) or one id being a near-superstring of the other
     (pangabenan_jenis_pranawa vs pangabenan_pranawa). Candidates for
     force_merge or a SAMA_DENGAN edge, never auto-applied.

None of these are fixed automatically here: every finding in the earlier audit
needed a judgment call (is this LITERAL genuinely generic, or a specific term
that should connect? are these two ids really the same concept, or genuinely
distinct things that happen to share wording?), and getting that wrong in
either direction has a real cost (silently drop real content vs. mint junk
entities / build a meaningless hub, or wrongly merge two distinct concepts).
Run this, read report.md, decide case by case -- same process used
2026-09-18, just without re-deriving the scan logic from scratch each time.

Run (from Graphing/kb/):  python audit_connectivity.py
Reads:  ../Neo4/relation_results_ngaben.normalized.json, ./entities.json
Writes: ./connectivity_report.md
"""
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REL_JSON = HERE.parent / "Neo4" / "relation_results_ngaben.normalized.json"
ENTITIES = HERE / "entities.json"
RELATIONS_JSONL = HERE / "relations.jsonl"
OUT = HERE / "connectivity_report.md"

# Predicates whose object is normally a standalone concept worth its own
# entity -- "parent decomposes into these things" shape. Mirrors
# Chatbot/bot/actions/actions.py's _CHILD_DEF_PREDICATES plus the wider
# "bahan" (material/composition) family from Chatbot/bot/kb_content.py's
# PREDICATE_FAMILIES, since either can carry a coordinate list.
COMPOSITIONAL_PREDICATES = {
    "TERMASUK_JENIS", "BERUPA", "TERDIRI_DARI", "TERBUAT_DARI", "MELIPUTI",
    "BERISI", "MEMILIKI_JENIS", "DIISI_DENGAN", "BERUNSUR",
}

# Common in nearly every entity's definition text in this corpus -- a shared
# mention of one of these is not a meaningful "these two are specifically
# related" signal the way a rarer shared term is.
_HUB_WORDS = {
    "ngaben", "jenazah", "sawa", "atma", "mendiang", "upacara", "banten",
    "yadnya", "pitra", "sarana", "ritual", "bhatara",
}


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load_rows():
    return load_json(REL_JSON)


def load_entities():
    return load_json(ENTITIES)


def load_relations_jsonl():
    txt = RELATIONS_JSONL.read_text(encoding="utf-8")
    return [json.loads(b) for b in txt.split("\n\n") if b.strip()]


def find_truly_isolated_ids(ents, rels):
    """Same definition Neo4/load_ngaben_to_neo4j.py's :Isolated tag uses: zero
    relations.jsonl edges in either direction (broader-spine edges count too,
    since load_kb() draws those the same way)."""
    connected = set()
    for r in rels:
        connected.add(r["subject_id"])
        connected.add(r["object_id"])
    ids = {e["id"] for e in ents}
    for e in ents:
        if e.get("broader") in ids:
            connected.add(e["id"])
            connected.add(e["broader"])
    return {e["id"] for e in ents} - connected


def find_mixed_sibling_groups(rows):
    """Pattern 1: same (sentence_id, subject, relation), siblings split
    between ENTITY and LITERAL."""
    groups = defaultdict(list)
    for r in rows:
        key = (r.get("sentence_id"), r.get("subject"), r.get("relation"))
        groups[key].append(r)
    out = []
    for key, items in sorted(groups.items()):
        types = {i.get("object_type") for i in items}
        if len(items) >= 2 and types == {"ENTITY", "LITERAL"}:
            out.append((key, items))
    return out


def find_all_literal_compositional_groups(rows):
    """Pattern 2: compositional-predicate groups with no surviving ENTITY
    sibling at all -- invisible to the mixed-group contrast signal."""
    groups = defaultdict(list)
    for r in rows:
        key = (r.get("sentence_id"), r.get("subject"), r.get("relation"))
        groups[key].append(r)
    out = []
    for key, items in sorted(groups.items()):
        if key[2] not in COMPOSITIONAL_PREDICATES:
            continue
        if {i.get("object_type") for i in items} == {"LITERAL"}:
            out.append((key, items))
    return out


def find_isolated_self_reference_candidates(ents, isolated_ids):
    """Pattern 4: nodes with zero relations.jsonl edges whose OWN definition
    text names another existing entity -- candidate entity_resolution.json
    broader_overrides targets. Filtered against _HUB_WORDS. Expect most
    isolated nodes to have NO hits (a real, common outcome -- most of them are
    isolated because they only share ubiquitous vocabulary with the rest of
    the corpus, not because of a specific missed link; see the 2026-09-18
    audit's finding on this for the ~60 nodes that were isolated then)."""
    surface_to_id = []
    for e in ents:
        for nm in [e["name"]] + e.get("aliases", []):
            if len(nm) >= 4:
                surface_to_id.append((nm.lower(), e["id"]))
    surface_to_id.sort(key=lambda x: -len(x[0]))

    out = []
    for e in ents:
        if e["id"] not in isolated_ids:
            continue
        text = (e.get("definition") or "").lower()
        if not text:
            continue
        hits = {}
        for surface, target in surface_to_id:
            if target == e["id"] or surface in _HUB_WORDS:
                continue
            if re.search(r"(?<![a-zà-ÿ])" + re.escape(surface) + r"(?![a-zà-ÿ])", text):
                if target not in hits or len(surface) > len(hits[target]):
                    hits[target] = surface
        if hits:
            out.append((e["id"], hits))
    return out


def find_self_loops(rels):
    """Pattern 5: relations.jsonl edges where subject_id == object_id --
    almost always an extraction bug (anaphora/coreference mis-resolved within
    one sentence), not a real reflexive fact."""
    return [r for r in rels if r.get("subject_id") and r.get("subject_id") == r.get("object_id")]


def find_dangling_references(ents, rels):
    """Pattern 6: a relations.jsonl edge (or an entity's `broader` pointer)
    whose endpoint id isn't present in entities.json -- usually a partial
    resolution, or an id dropped (fragment filter / `reject`) after the edge
    referencing it was written."""
    ids = {e["id"] for e in ents}
    out = []
    for r in rels:
        missing = [k for k in ("subject_id", "object_id") if r.get(k) not in ids]
        if missing:
            out.append(("relation", r.get("subject_id"), r.get("predicate"), r.get("object_id"), missing))
    for e in ents:
        b = e.get("broader")
        if b and b not in ids:
            out.append(("broader", e["id"], "TERMASUK_JENIS", b, ["broader:" + b]))
    return out


def find_near_duplicate_ids(ents, min_ratio=0.78):
    """Pattern 7: ids whose spelling is close enough to suggest they're two
    separate extractions of the same concept -- typo-level drift (panebusan
    vs penebusan) or one id as a near-superstring of the other
    (pangabenan_jenis_pranawa vs pangabenan_pranawa). O(n^2) over id strings;
    entity count here (~500) keeps that cheap -- revisit if the KB grows a
    lot bigger."""
    items = [(e["id"], e["id"].replace("_", " ")) for e in ents]
    out = []
    for i in range(len(items)):
        id_a, norm_a = items[i]
        if len(norm_a) < 5:
            continue
        for j in range(i + 1, len(items)):
            id_b, norm_b = items[j]
            if len(norm_b) < 5:
                continue
            ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
            if ratio >= min_ratio:
                out.append((id_a, id_b, round(ratio, 2)))
    out.sort(key=lambda x: -x[2])
    return out


def main():
    rows = load_rows()
    ents = load_entities()
    rels = load_relations_jsonl()

    mixed = find_mixed_sibling_groups(rows)
    all_lit = find_all_literal_compositional_groups(rows)
    isolated_ids = find_truly_isolated_ids(ents, rels)
    self_ref = find_isolated_self_reference_candidates(ents, isolated_ids)
    self_loops = find_self_loops(rels)
    dangling = find_dangling_references(ents, rels)
    near_dupes = find_near_duplicate_ids(ents)

    lines = ["# Connectivity audit report", "",
             f"Source: {REL_JSON.name} ({len(rows)} rows), {ENTITIES.name} ({len(ents)} entities)",
             "", "Read the module docstring before acting on anything here -- every", "line is a candidate, not a verdict.", ""]

    lines += [f"## Mixed ENTITY/LITERAL sibling groups ({len(mixed)})", "",
              "Same sentence+subject+relation, some siblings already ENTITY, some", "still LITERAL -- the LITERAL ones are invisible to the bot/graph.", ""]
    for key, items in mixed:
        sid, subj, rel = key
        ent_objs = [i["object"] for i in items if i["object_type"] == "ENTITY"]
        lit_objs = [i["object"] for i in items if i["object_type"] == "LITERAL"]
        lines.append(f"- S{sid} `{subj}` -{rel}-> ENTITY: {ent_objs} | LITERAL: {lit_objs}")
    lines.append("")

    lines += [f"## All-LITERAL compositional groups ({len(all_lit)})", "",
              "No ENTITY sibling survives in these -- judge each LITERAL on its", "own: specific ritual-object noun phrase (candidate to flip) vs generic", "word / abstract quality / descriptive clause (correctly stays LITERAL).", ""]
    for key, items in all_lit:
        sid, subj, rel = key
        objs = [i["object"] for i in items]
        lines.append(f"- S{sid} `{subj}` -{rel}-> {objs}")
    lines.append("")

    lines += [f"## Isolated nodes: {len(isolated_ids)} total, {len(self_ref)} with a definition self-reference", "",
              "Isolated = zero relations.jsonl edges in either direction (same", "definition Neo4/load_ngaben_to_neo4j.py's :Isolated tag uses). Of these,", "the ones below have their own definition text naming another known", "entity (hub words already filtered out) -- candidate broader_overrides", "targets. The rest of the isolated set had NO such hit; that's a normal,", "expected outcome (see docstring), not a sign this pass missed something.", ""]
    for eid, hits in self_ref:
        mentions = ", ".join(f"{v}->{k}" for k, v in hits.items())
        lines.append(f"- `{eid}`: {mentions}")
    lines.append("")

    lines += [f"## Self-loops ({len(self_loops)})", "",
              "subject_id == object_id -- almost always a coreference/anaphora", "mis-resolution, not a real reflexive fact.", ""]
    for r in self_loops:
        lines.append(f"- S{r.get('provenance', {}).get('sentence_id', '?')} `{r.get('subject_id')}` -{r.get('predicate')}-> `{r.get('object_id')}` (confidence={r.get('confidence')})")
    lines.append("")

    lines += [f"## Dangling references ({len(dangling)})", "",
              "An edge or broader-pointer whose endpoint id isn't in entities.json.", ""]
    for kind, subj, pred, obj, missing in dangling:
        lines.append(f"- [{kind}] `{subj}` -{pred}-> `{obj}` (missing: {', '.join(missing)})")
    lines.append("")

    lines += [f"## Near-duplicate ids ({len(near_dupes)})", "",
              "Spelling-similarity candidates for force_merge or a SAMA_DENGAN edge --", "read both entities before deciding; a shared root word alone (e.g. the", "sasih_* family) is not by itself evidence of duplication.", ""]
    for id_a, id_b, ratio in near_dupes:
        lines.append(f"- `{id_a}` ~ `{id_b}` (ratio={ratio})")
    lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"mixed sibling groups: {len(mixed)}")
    print(f"all-LITERAL compositional groups: {len(all_lit)}")
    print(f"isolated nodes: {len(isolated_ids)} ({len(self_ref)} with a definition self-reference)")
    print(f"self-loops: {len(self_loops)}")
    print(f"dangling references: {len(dangling)}")
    print(f"near-duplicate ids: {len(near_dupes)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

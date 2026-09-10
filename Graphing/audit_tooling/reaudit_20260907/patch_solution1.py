"""
Solution 1 (part 1 of 2): add a SURGICAL per-triple manual-fix mechanism to cell 51,
so a one-triple fix no longer forces re-listing (and re-tagging manual_override) the
whole sentence.

Adds:
  * a dump of the pre-override `relations` to a companion file, so the existing
    ~300 all-or-nothing OVERRIDES entries can be migrated (part 2, after one run).
  * MANUAL_RELATION_DROPS   {sid: [(subject, relation, object), ...]}
  * MANUAL_RELATION_EDITS   {sid: [{"match": (s,r,o), "set": {..fields..}}, ...]}
    applied after OVERRIDES + ADDITIONS, before typing. They match on the current
    (subject, relation, object) text and touch ONLY that triple; untouched auto
    triples keep their dependency_rule / object_decomposition source.

Both new dicts start EMPTY -- this patch changes no output. Idempotent guard:
the "13.8d." marker.
"""
import json

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CELL = 51

ANCHOR_DUMP = '''for relation in relations:
    relation["source_text"] = original_sentence_lookup.get(
        relation["sentence_id"],
        None
    )

# ==========================================
# 13.8b. MANUAL OVERRIDES FOR KNOWN BAD'''

NEW_DUMP = '''for relation in relations:
    relation["source_text"] = original_sentence_lookup.get(
        relation["sentence_id"],
        None
    )

# ----------------------------------------------------
# PRE-OVERRIDE SNAPSHOT: the pure auto-extracted relation set, before any
# MANUAL_RELATION_OVERRIDES / _ADDITIONS / _EDITS / _DROPS touch it. Written
# to a companion file so hand-fix entries can be diffed against what the
# extractor actually produces (and migrated between the whole-sentence
# OVERRIDES form and the surgical EDITS/DROPS form). Cheap; no effect on output.
# ----------------------------------------------------
try:
    import os as _os
    _preov_dir = _os.path.join(BASE_RESULTS_FOLDER, "relation_results_ngaben")
    _os.makedirs(_preov_dir, exist_ok=True)
    with open(_os.path.join(_preov_dir, "_preoverride_relations.json"), "w",
              encoding="utf-8") as _f:
        json.dump(
            [{"sentence_id": r["sentence_id"], "subject": r["subject"],
              "subject_label": r.get("subject_label"), "relation": r["relation"],
              "object": r["object"], "object_label": r.get("object_label"),
              "source": r.get("source")}
             for r in relations],
            _f, ensure_ascii=False, indent=1)
except Exception as _e:
    print(f"(pre-override snapshot skipped: {_e})")

# ==========================================
# 13.8b. MANUAL OVERRIDES FOR KNOWN BAD'''

ANCHOR_MECH = '''for sentence_id, extra_relations in MANUAL_RELATION_ADDITIONS.items():
    for relation in extra_relations:
        relation["sentence_id"] = sentence_id
        relation.setdefault("source", "manual_override")
        relations.append(relation)

# ==========================================
# 13.9. TYPE THE RELATION OBJECTS'''

NEW_MECH = '''for sentence_id, extra_relations in MANUAL_RELATION_ADDITIONS.items():
    for relation in extra_relations:
        relation["sentence_id"] = sentence_id
        relation.setdefault("source", "manual_override")
        relations.append(relation)

# ==========================================
# 13.8d. MANUAL PER-TRIPLE EDITS + DROPS
# ==========================================
# Surgical alternative to MANUAL_RELATION_OVERRIDES (which replaces a whole
# sentence and re-tags EVERY triple manual_override, even the correct auto
# ones -- see RELATION_AUDIT_RUNBOOK.md). EDITS / DROPS match a triple on its
# current (subject, relation, object) TEXT and change or remove ONLY that
# triple; every other triple for the sentence is left exactly as the extractor
# emitted it, source and all. A sentence must NOT appear in both
# MANUAL_RELATION_OVERRIDES and (DROPS or EDITS).

MANUAL_RELATION_DROPS = {
    # sentence_id: [ (subject, relation, object), ... ]   -- remove each match
}

MANUAL_RELATION_EDITS = {
    # sentence_id: [ {"match": (subject, relation, object),
    #                 "set": {"subject": ..., "relation": ..., "object": ...,
    #                         "subject_label": ..., "object_label": ...}}, ... ]
    # only the keys present in "set" are changed; source becomes manual_override.
}

_pt_both = (set(MANUAL_RELATION_DROPS) | set(MANUAL_RELATION_EDITS)) & set(MANUAL_RELATION_OVERRIDES)
assert not _pt_both, f"sentence(s) in both OVERRIDES and DROPS/EDITS: {sorted(_pt_both)}"


def _pt_norm(s):
    return re.sub(r"\\s+", " ", str(s).strip().lower())


_pt_drops = _pt_edits = 0

for _sid, _specs in MANUAL_RELATION_DROPS.items():
    _keys = {(_pt_norm(s), _pt_norm(r), _pt_norm(o)) for s, r, o in _specs}
    _before = len(relations)
    relations = [
        _rel for _rel in relations
        if not (_rel["sentence_id"] == _sid
                and (_pt_norm(_rel["subject"]), _pt_norm(_rel["relation"]),
                     _pt_norm(_rel["object"])) in _keys)
    ]
    _hit = _before - len(relations)
    _pt_drops += _hit
    if _hit == 0:
        print(f"  [warn] MANUAL_RELATION_DROPS S{_sid}: no triple matched")

for _sid, _specs in MANUAL_RELATION_EDITS.items():
    for _spec in _specs:
        _ms, _mr, _mo = (_pt_norm(x) for x in _spec["match"])
        _matched = False
        for _rel in relations:
            if (_rel["sentence_id"] == _sid
                    and _pt_norm(_rel["subject"]) == _ms
                    and _pt_norm(_rel["relation"]) == _mr
                    and _pt_norm(_rel["object"]) == _mo):
                _rel.update(_spec["set"])
                _rel["source"] = "manual_override"
                _pt_edits += 1
                _matched = True
        if not _matched:
            print(f"  [warn] MANUAL_RELATION_EDITS S{_sid}: no triple matched "
                  f"{_spec['match']}")

print(f"manual per-triple fixes: {_pt_drops} drop(s), {_pt_edits} edit(s)")

# ==========================================
# 13.9. TYPE THE RELATION OBJECTS'''


def main():
    nb = json.load(open(NB, encoding="utf-8"))
    cell = nb["cells"][CELL]
    src = "".join(cell["source"])
    n0 = len(src)
    if "13.8d. MANUAL PER-TRIPLE" in src:
        raise SystemExit("[FAIL] already patched")
    for label, a, b in (("pre-override dump", ANCHOR_DUMP, NEW_DUMP),
                        ("per-triple mechanism", ANCHOR_MECH, NEW_MECH)):
        if src.count(a) != 1:
            raise SystemExit(f"[FAIL] anchor for {label}: {src.count(a)} matches")
        src = src.replace(a, b, 1)
        print(f"[ok] {label}")
    try:
        compile(src, "<c51-sol1>", "exec")
    except SyntaxError as e:
        raise SystemExit(f"[FAIL] SyntaxError: {e}")
    cell["source"] = src.splitlines(keepends=True)
    with open(NB, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\nSolution-1 mechanism added. {len(src) - n0:+d} chars. Both new dicts empty (no output change).")


if __name__ == "__main__":
    main()

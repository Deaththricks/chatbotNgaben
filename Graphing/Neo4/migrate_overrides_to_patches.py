"""
migrate_overrides_to_patches.py -- one-time migration + re-runnable audit.

Turns the wholesale MANUAL_RELATION_OVERRIDES / MANUAL_RELATION_ADDITIONS dicts
inside "Knowledge Processing.ipynb" cell 52 into a surgical, external, per-triple
patch file: Data/relation_patches.json (deletions / edits / additions).

Wholesale override -> per sentence:
  * an override triple that the auto extractor already produced  -> dropped from
    the patch file entirely (the auto triple flows through on its own)
  * an auto triple the override removed                          -> a `deletions` entry
  * an override triple the extractor never produced              -> an `additions` entry
  * a delete + add that share (subject, relation) 1:1            -> collapsed to an `edits` entry
  * an override key mapped to []                                 -> `deletions` for every auto triple
MANUAL_RELATION_ADDITIONS entries are copied straight into `additions`.

Matching is normalized-exact on (subject, relation, object): lowercase + collapsed
whitespace -- identical to cell 52's `_pt_norm`, and to how the notebook's DROPS /
EDITS application matches. Deletion / edit `match` specs are stored in the
*pre-canonicalization* form taken from _preoverride_relations.json, because the
notebook applies DROPS / EDITS before predicate canonicalization (cell 52 L4878 /
L4892, canonicalization at L5113).

Usage:
    python migrate_overrides_to_patches.py            # write Data/relation_patches.json + report
    python migrate_overrides_to_patches.py --audit    # report only, do not touch the patch file
                                                      # (use after every part-C extractor change:
                                                      #  deletion count should fall)
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

NOTEBOOK = os.path.join(ROOT, "Knowledge Processing.ipynb")
PREOVERRIDE = os.path.join(ROOT, "Results", "Final", "relation_results_ngaben",
                           "_preoverride_relations.json")
BACKUP = os.path.join(ROOT, "Results", "Final", "relation_results_ngaben",
                      "relation_results_ngaben backup.json")
PATCHES_OUT = os.path.join(ROOT, "Data", "relation_patches.json")
REPORT_OUT = os.path.join(HERE, "migrate_overrides_report.txt")

CELL_INDEX = 52

_COPULA = {
    "menjadi", "merupakan", "berfungsi", "adalah", "rupa", "berupa", "berwujud",
    "terbuat", "berbentuk", "wedana", "keadaan", "hal", "sesuatu",
}
_RELCLAUSE = re.compile(r"\b(yang|yaitu|yakni)\b")


def norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def triple_key(row):
    return (norm(row["subject"]), norm(row["relation"]), norm(row["object"]))


# --------------------------------------------------------------------------- #
#  pull the two literal dicts out of the notebook cell                        #
# --------------------------------------------------------------------------- #
def _grab_literal(cell_src, name):
    """Return the source text of `name = { ... }` with balanced braces."""
    m = re.search(rf"^{name}\s*=\s*\{{", cell_src, re.M)
    if not m:
        raise RuntimeError(f"{name} not found in cell {CELL_INDEX}")
    depth = 0
    for j in range(m.end() - 1, len(cell_src)):
        c = cell_src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return cell_src[m.start():j + 1]
    raise RuntimeError(f"unbalanced braces in {name}")


def load_notebook_dicts():
    """Read the legacy MANUAL_RELATION_* literals. Part A deletes them from the
    live notebook, so fall back to the newest pre-A backup."""
    import glob
    candidates = [NOTEBOOK] + sorted(
        glob.glob(NOTEBOOK + ".bak_preAB_*"), reverse=True)
    for path in candidates:
        cell_src = "".join(json.load(open(path, encoding="utf-8"))
                           ["cells"][CELL_INDEX]["source"])
        if "MANUAL_RELATION_ADDITIONS = {" not in cell_src:
            continue
        ns = {}
        exec(_grab_literal(cell_src, "MANUAL_RELATION_OVERRIDES"), ns)   # noqa: S102
        exec(_grab_literal(cell_src, "MANUAL_RELATION_ADDITIONS"), ns)   # noqa: S102
        print(f"legacy dicts read from {os.path.basename(path)}")
        return ns["MANUAL_RELATION_OVERRIDES"], ns["MANUAL_RELATION_ADDITIONS"]
    raise RuntimeError("no notebook (live or backup) still contains the legacy "
                       "MANUAL_RELATION_* dicts -- migration already done; use --audit")


# --------------------------------------------------------------------------- #
#  reason heuristic (seed text for human review only -- loader ignores it)    #
# --------------------------------------------------------------------------- #
def guess_reason(auto_obj, human_objs):
    ao = norm(auto_obj)
    if ao in _COPULA or len(ao.split()) == 1 and ao in _COPULA:
        return "fragment/copula object"
    if _RELCLAUSE.search(ao) or len(ao.split()) > 6:
        return "object is a relative clause / long description"
    for ho in human_objs:
        h = norm(ho)
        if h.startswith(ao + " ") or h.startswith(ao + " (") or ao and ao in h:
            return "object truncated (auto span is a prefix of the human span)"
        if h and (h in ao):
            return "object over-extended (human span is shorter)"
    if any(w in ao for w in (" dan ", " atau ", " serta ")):
        return "coordination split"
    return "object replaced by human"


# --------------------------------------------------------------------------- #
def build(overrides, additions):
    pre = json.load(open(PREOVERRIDE, encoding="utf-8"))
    bak = json.load(open(BACKUP, encoding="utf-8"))

    ctx = {}
    for r in bak:
        ctx.setdefault(r["sentence_id"], r.get("context_sentence", ""))
    for r in pre:
        ctx.setdefault(r["sentence_id"], "")

    auto_by_sid = defaultdict(list)
    for r in pre:
        auto_by_sid[r["sentence_id"]].append(r)

    deletions, edits, additions_out, legacy = [], [], [], {}
    stats = Counter()
    per_sentence = []

    override_sids = sorted(int(k) for k in overrides)
    for sid in override_sids:
        # a sentence can be in BOTH dicts: OVERRIDES replaces the auto set, then
        # ADDITIONS appends more. For the auto/human diff, "human" is the union --
        # otherwise an auto triple that ADDITIONS re-adds looks like auto-only and
        # wrongly yields a deletion that would wipe the re-added row.
        human = list(overrides[sid]) + list(additions.get(sid, []))
        auto = auto_by_sid.get(sid, [])
        auto_keys = {triple_key(r): r for r in auto}
        human_keys = {triple_key(r): r for r in human}

        kept_auto = auto_keys.keys() & human_keys.keys()
        to_delete = [auto_keys[k] for k in auto_keys.keys() - human_keys.keys()]
        to_add = [human_keys[k] for k in human_keys.keys() - auto_keys.keys()]

        # collapse 1:1 (subject, relation) delete+add pairs into an edit
        del_by_sr = defaultdict(list)
        for r in to_delete:
            del_by_sr[(norm(r["subject"]), norm(r["relation"]))].append(r)
        add_by_sr = defaultdict(list)
        for r in to_add:
            add_by_sr[(norm(r["subject"]), norm(r["relation"]))].append(r)

        edited_del, edited_add = set(), set()
        for sr in list(del_by_sr):
            if len(del_by_sr[sr]) == 1 and len(add_by_sr.get(sr, [])) == 1:
                d, a = del_by_sr[sr][0], add_by_sr[sr][0]
                edits.append({
                    "sentence_id": sid,
                    "match": {"subject": d["subject"], "relation": d["relation"],
                              "object": d["object"]},
                    "set": _edit_set(d, a),
                    "reason": "object rephrased (same subject + predicate)",
                    "context": ctx.get(sid, ""),
                })
                edited_del.add(id(d))
                edited_add.add(id(a))
                stats["edits"] += 1

        human_objs = [h["object"] for h in human]
        for r in to_delete:
            if id(r) in edited_del:
                continue
            deletions.append({
                "sentence_id": sid,
                "subject": r["subject"], "relation": r["relation"], "object": r["object"],
                "reason": (guess_reason(r["object"], human_objs) if human else
                           "override key mapped to [] (drop all auto triples)"),
                "context": ctx.get(sid, ""),
            })
            stats["deletions"] += 1

        for r in to_add:
            if id(r) in edited_add:
                continue
            additions_out.append(_addition_entry(sid, r, ctx.get(sid, ""),
                                                 "wholesale override -> per-triple add"))
            stats["additions"] += 1

        stats["auto_kept"] += len(kept_auto)
        per_sentence.append((sid, len(kept_auto), len(to_delete), len(to_add),
                             len(auto), len(human)))

    # MANUAL_RELATION_ADDITIONS for sentences NOT also in OVERRIDES (the overlap
    # sids already folded their additions into the human set above).
    _ov_set = {int(k) for k in overrides}
    add_sids = sorted(int(k) for k in additions if int(k) not in _ov_set)
    for sid in add_sids:
        for r in additions[sid]:
            additions_out.append(_addition_entry(sid, r, ctx.get(sid, ""),
                                                 "from MANUAL_RELATION_ADDITIONS"))
            stats["additions_from_ADDITIONS"] += 1

    patches = {
        "_comment": (
            "Surgical per-triple corrections to relation extraction. Generated by "
            "Neo4/migrate_overrides_to_patches.py from the wholesale MANUAL_RELATION_* "
            "dicts. Match is normalized-exact (lowercase + collapsed whitespace) on "
            "(sentence_id, subject, relation, object). 'reason' and 'context' are for "
            "human review; the notebook loader ignores them. legacy_overrides has the "
            "same all-or-nothing semantics as the old MANUAL_RELATION_OVERRIDES."
        ),
        "deletions": sorted(deletions, key=lambda d: (d["sentence_id"], d["subject"], d["object"])),
        "edits": sorted(edits, key=lambda d: (d["sentence_id"], d["match"]["subject"])),
        "additions": sorted(additions_out, key=lambda d: (d["sentence_id"], d["subject"], d["object"])),
        "legacy_overrides": legacy,
    }
    return patches, stats, per_sentence


def _edit_set(deleted, added):
    out = {}
    if norm(deleted["subject"]) != norm(added["subject"]):
        out["subject"] = added["subject"]
    if norm(deleted["relation"]) != norm(added["relation"]):
        out["relation"] = added["relation"]
    if norm(deleted["object"]) != norm(added["object"]):
        out["object"] = added["object"]
    if added.get("subject_label") is not None:
        out["subject_label"] = added["subject_label"]
    if added.get("object_label") is not None:
        out["object_label"] = added["object_label"]
    return out


def _addition_entry(sid, r, context, reason):
    return {
        "sentence_id": sid,
        "subject": r["subject"],
        "subject_label": r.get("subject_label"),
        "relation": r["relation"],
        "object": r["object"],
        "object_label": r.get("object_label"),
        "reason": reason,
        "context": context,
    }


# --------------------------------------------------------------------------- #
def verify(patches):
    """Every deletion / edit match spec must hit a real pre-override auto triple."""
    pre = json.load(open(PREOVERRIDE, encoding="utf-8"))
    pre_keys = defaultdict(set)
    for r in pre:
        pre_keys[r["sentence_id"]].add(triple_key(r))
    problems = []
    for d in patches["deletions"]:
        k = (norm(d["subject"]), norm(d["relation"]), norm(d["object"]))
        if k not in pre_keys[d["sentence_id"]]:
            problems.append(f"deletion S{d['sentence_id']} has no matching auto triple: {k}")
    for e in patches["edits"]:
        m = e["match"]
        k = (norm(m["subject"]), norm(m["relation"]), norm(m["object"]))
        if k not in pre_keys[e["sentence_id"]]:
            problems.append(f"edit S{e['sentence_id']} has no matching auto triple: {k}")
    return problems


def write_report(stats, per_sentence, problems, audit):
    lines = [
        "=" * 74,
        "OVERRIDE -> PATCH MIGRATION REPORT" + ("  (audit only)" if audit else ""),
        "=" * 74,
        "",
        f"override sentences processed : {len(per_sentence)}",
        f"auto triples now flowing through (were 'manual'): {stats['auto_kept']}",
        f"deletions                    : {stats['deletions']}",
        f"edits                        : {stats['edits']}",
        f"additions (from overrides)    : {stats['additions']}",
        f"additions (from ADDITIONS)    : {stats['additions_from_ADDITIONS']}",
        "",
        "verification (every deletion/edit must match a pre-override auto triple):",
        f"  problems: {len(problems)}",
    ]
    lines += [f"    {p}" for p in problems]
    lines += ["", "per-sentence  (sid: kept_auto / del / add / n_auto / n_human)", "-" * 60]
    for sid, kept, ndel, nadd, nauto, nhuman in per_sentence:
        flag = "  <-- no auto triples" if nauto == 0 else ""
        lines.append(f"  S{sid:<5} {kept} / {ndel} / {nadd} / {nauto} / {nhuman}{flag}")
    open(REPORT_OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))
    print(f"\nwrote {REPORT_OUT}")


def audit():
    """After a part-C extractor change: which existing patch entries has the
    improved extractor made redundant? (deletion/edit no longer matches any auto
    triple; addition is now produced by the extractor directly.)"""
    patches = json.load(open(PATCHES_OUT, encoding="utf-8"))
    pre = json.load(open(PREOVERRIDE, encoding="utf-8"))
    auto = defaultdict(set)
    for r in pre:
        auto[r["sentence_id"]].add(triple_key(r))

    dead_del = [d for d in patches["deletions"]
                if (norm(d["subject"]), norm(d["relation"]), norm(d["object"]))
                not in auto[d["sentence_id"]]]
    dead_edit = [e for e in patches["edits"]
                 if (norm(e["match"]["subject"]), norm(e["match"]["relation"]),
                     norm(e["match"]["object"])) not in auto[e["sentence_id"]]]
    now_auto_add = [a for a in patches["additions"]
                    if (norm(a["subject"]), norm(a["relation"]), norm(a["object"]))
                    in auto[a["sentence_id"]]]

    lines = [
        "=" * 74, "PATCH AUDIT vs current _preoverride_relations.json", "=" * 74, "",
        f"deletions total {len(patches['deletions'])}, now redundant (no matching auto triple): {len(dead_del)}",
        f"edits     total {len(patches['edits'])}, now redundant: {len(dead_edit)}",
        f"additions total {len(patches['additions'])}, now emitted by extractor directly: {len(now_auto_add)}",
        "",
        "redundant deletions (extractor no longer emits the bad triple -- safe to drop from patch file):",
    ]
    lines += [f"  S{d['sentence_id']}  {d['subject']} -[{d['relation']}]-> {d['object']}"
              for d in dead_del]
    lines += ["", "redundant edits:"]
    lines += [f"  S{e['sentence_id']}  {e['match']}" for e in dead_edit]
    lines += ["", "additions the extractor now produces on its own:"]
    lines += [f"  S{a['sentence_id']}  {a['subject']} -[{a['relation']}]-> {a['object']}"
              for a in now_auto_add]
    open(REPORT_OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    print(f"\nwrote {REPORT_OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true",
                    help="report which existing patch entries a part-C extractor "
                         "change has made redundant; do not touch the patch file")
    args = ap.parse_args()

    if args.audit:
        audit()
        return

    overrides, additions = load_notebook_dicts()
    patches, stats, per_sentence = build(overrides, additions)
    problems = verify(patches)

    if not args.audit:
        with open(PATCHES_OUT, "w", encoding="utf-8") as fh:
            json.dump(patches, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"wrote {PATCHES_OUT}  "
              f"({len(patches['deletions'])} deletions, {len(patches['edits'])} edits, "
              f"{len(patches['additions'])} additions)")

    write_report(stats, per_sentence, problems, False)
    if problems:
        raise SystemExit(f"\n{len(problems)} verification problem(s) -- see report")


if __name__ == "__main__":
    main()

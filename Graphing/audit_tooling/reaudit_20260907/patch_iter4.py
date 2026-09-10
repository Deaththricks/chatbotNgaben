"""
Iteration 4 fix batch: apply the convergence re-audit (audit_tooling/reaudit_20260907/
CONSOLIDATED.md) to cell 51 via MANUAL_RELATION_OVERRIDES / MANUAL_RELATION_ADDITIONS.

Consumes the 8 per-chunk JSON files chunk_NN_iter4.json (produced by the patch-builder
agents), each: {"overrides": {sid: [triple,...]}, "additions": {sid: [triple,...]}}.

For each override sid: replace its existing OVERRIDES entry in place if present, else append;
and if that sid also has an ADDITIONS entry, drop it (the override is now authoritative).
For each additions-only sid: replace its ADDITIONS entry if present, else append.

Idempotent guard: the "# --- Iteration 4" marker.
"""
import json, os, re, glob

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CELL_INDEX = 51
DIR = r"C:\Misc\Work\AI_Chatbot\Graphing\audit_tooling\reaudit_20260907"
MARK = "# --- Iteration 4 (convergence re-audit, CONSOLIDATED.md) ---"

VALID_KEYS = {"subject", "subject_label", "relation", "object", "object_label", "source"}


def load_batches():
    ov, add = {}, {}
    for p in sorted(glob.glob(os.path.join(DIR, "chunk_0*_iter4.json"))):
        d = json.load(open(p, encoding="utf-8"))
        for sid, trips in (d.get("overrides") or {}).items():
            k = str(int(str(sid).lstrip("Ss")))
            assert k not in ov, f"dup override sid {k} across chunks"
            ov[k] = trips
        for sid, trips in (d.get("additions") or {}).items():
            k = str(int(str(sid).lstrip("Ss")))
            assert k not in add, f"dup addition sid {k} across chunks"
            add[k] = trips
        print(f"  {os.path.basename(p)}: {len(d.get('overrides') or {})} ov, {len(d.get('additions') or {})} add")
    return ov, add


def render_triple(t):
    for k in t:
        assert k in VALID_KEYS, f"bad triple key {k!r} in {t}"
    def v(x):
        return "None" if x is None else json.dumps(x, ensure_ascii=False)
    return ('{"subject": %s, "subject_label": %s, "relation": %s, "object": %s, '
            '"object_label": %s, "source": "manual_override"}' % (
                v(t["subject"]), v(t.get("subject_label")), v(t["relation"]),
                v(t["object"]), v(t.get("object_label"))))


def render_entry(sid, trips):
    body = "".join(f"        {render_triple(t)},\n" for t in trips)
    return f"    {sid}: [\n{body}    ],\n"


def dict_span(src, name):
    a = src.index(f"{name} = {{")
    b = src.index("\n}\n", a) + 2
    return a, b


def entry_span(src, lo, hi, sid):
    """char span of `    <sid>: [ ... ],\n` inside src[lo:hi], or None."""
    m = re.search(rf"\n    {sid}: \[\n", src[lo:hi])
    if not m:
        return None
    start = lo + m.start() + 1  # keep the leading \n out; start at the 4-space indent
    end_m = re.search(r"\n    \],\n", src[lo + m.end():hi])
    end = lo + m.end() + end_m.end()
    return start, end


def main():
    nb = json.load(open(NB_PATH, encoding="utf-8"))
    cell = nb["cells"][CELL_INDEX]
    src = "".join(cell["source"])
    n0 = len(src)
    if MARK in src:
        raise SystemExit("[FAIL] already patched (Iteration 4 marker present)")

    ov, add = load_batches()
    print(f"total: {len(ov)} override sids, {len(add)} addition-only sids")
    add = {s: t for s, t in add.items() if s not in ov}  # override wins

    ov_lo, ov_hi = dict_span(src, "MANUAL_RELATION_OVERRIDES")
    replaced_ov = appended_ov = 0
    # process appends last so spans stay valid; do replacements first (they don't shift much,
    # but recompute span each time to be safe)
    append_ov = []
    for sid in sorted(ov, key=int):
        entry = render_entry(sid, ov[sid])
        ov_lo, ov_hi = dict_span(src, "MANUAL_RELATION_OVERRIDES")
        sp = entry_span(src, ov_lo, ov_hi, sid)
        if sp:
            src = src[:sp[0]] + entry + src[sp[1]:]
            replaced_ov += 1
        else:
            append_ov.append(entry)
    if append_ov:
        ov_lo, ov_hi = dict_span(src, "MANUAL_RELATION_OVERRIDES")
        ins = ov_hi - 2  # just before "\n}"
        src = src[:ins] + "\n    " + MARK + "\n" + "".join(append_ov) + src[ins:]
        appended_ov = len(append_ov)

    # drop ADDITIONS entries for any sid that now has an override
    dropped_add = 0
    for sid in list(ov):
        a_lo, a_hi = dict_span(src, "MANUAL_RELATION_ADDITIONS")
        sp = entry_span(src, a_lo, a_hi, sid)
        if sp:
            src = src[:sp[0]] + src[sp[1]:]
            dropped_add += 1

    replaced_add = appended_add = 0
    append_add = []
    for sid in sorted(add, key=int):
        entry = render_entry(sid, add[sid])
        a_lo, a_hi = dict_span(src, "MANUAL_RELATION_ADDITIONS")
        sp = entry_span(src, a_lo, a_hi, sid)
        if sp:
            src = src[:sp[0]] + entry + src[sp[1]:]
            replaced_add += 1
        else:
            append_add.append(entry)
    if append_add:
        a_lo, a_hi = dict_span(src, "MANUAL_RELATION_ADDITIONS")
        ins = a_hi - 2
        src = src[:ins] + "\n    " + MARK + "\n" + "".join(append_add) + src[ins:]
        appended_add = len(append_add)

    try:
        compile(src, "<cell51-iter4>", "exec")
    except SyntaxError as e:
        raise SystemExit(f"[FAIL] SyntaxError: {e}")

    # verify dicts eval + no duplicate keys + all sids landed
    for name, want in (("MANUAL_RELATION_OVERRIDES", ov), ("MANUAL_RELATION_ADDITIONS", add)):
        lo, hi = dict_span(src, name)
        lit = src[lo:hi]
        keys = re.findall(r"\n    (\d+): \[", lit)
        assert len(keys) == len(set(keys)), f"{name}: duplicate keys {sorted(k for k in set(keys) if keys.count(k) > 1)}"
        ns = {}
        exec(compile(lit.replace(name, "_D"), "<d>", "exec"), ns)
        for sid in want:
            k = int(sid)
            assert k in ns["_D"] and len(ns["_D"][k]) == len(want[sid]), f"{name} S{sid} mismatch"

    print(f"\noverrides: {replaced_ov} replaced, {appended_ov} appended | "
          f"additions: {replaced_add} replaced, {appended_add} appended, {dropped_add} dropped (now overridden)")
    cell["source"] = src.splitlines(keepends=True)
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Iteration 4 patch complete. {len(src) - n0:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

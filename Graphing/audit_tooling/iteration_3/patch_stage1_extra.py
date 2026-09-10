"""
Iteration 3, Stage 1 (follow-up): S2028/S2166 are a DIFFERENT shape of the
same /121 defect than S1747/S2642 -- there the verb ITSELF is literally
"menjelang" ("menjelang dan sampai dengan hari pabersihan, naga banda
diletakkan..."), picked up by find_coordinated_verb_relations() as a
spurious coordinate-action sibling of the real root verb, then
derive_raw_relation_label's step-3b special case ("lemma == 'menjelang'")
returns bare "MENJELANG" for it -- exactly the same symptom (a temporal/
sequence marker shipping as if it were the whole predicate) but via the
sibling-collection path, not the case-marker-suffix path patch_stage1.py
already fixed. The already-existing D13 (Iteration 2) exclusion in
find_coordinated_verb_relations() drops a sibling advcl that carries a
temporal-framing OBL child ("pada saat X") -- extend it to also drop a
sibling advcl whose own VERB LEMMA is itself one of the sequence/temporal
marker words (sebelum/sesudah/setelah/selain/menjelang): such a verb is BY
DEFINITION clause-framing, never a genuine parallel action, so it should
never be treated as an independent coordinate relation at all.
"""
import json

NB_PATH = "Knowledge Processing.ipynb"
CELL_INDEX = 51


def apply(src, old, new, label):
    count = src.count(old)
    if count == 0:
        raise SystemExit(f"[FAIL] anchor not found for: {label}")
    if count > 1:
        raise SystemExit(f"[FAIL] anchor ambiguous ({count} matches) for: {label}")
    print(f"[ok] {label}")
    return src.replace(old, new, 1)


def main():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)
    cell = nb["cells"][CELL_INDEX]
    src = "".join(cell["source"])
    original_len = len(src)

    src = apply(
        src,
        '''    for sibling in sorted(siblings, key=lambda x: x["id"]):

        if sibling["deprel"] == "advcl" and _advcl_has_subordinate_mark(sibling, tokens):
            continue

        if sibling["deprel"] == "advcl" and (
            outer_has_temporal_frame or _obl_has_temporal_lemma(sibling, tokens)
        ):
            continue''',
        '''    for sibling in sorted(siblings, key=lambda x: x["id"]):

        if sibling["deprel"] == "advcl" and _advcl_has_subordinate_mark(sibling, tokens):
            continue

        if sibling["deprel"] == "advcl" and (
            outer_has_temporal_frame or _obl_has_temporal_lemma(sibling, tokens)
        ):
            continue

        # AUDIT /121 (Iteration 3, S2028/S2166): a sibling advcl whose own
        # VERB LEMMA is itself a sequence/temporal marker word ("menjelang
        # dan sampai dengan hari pabersihan, naga banda diletakkan...") is
        # BY DEFINITION clause-framing, never a genuine parallel action --
        # emitting it as its own coordinate relation ships the bare marker
        # ("MENJELANG") as if it were a real predicate. Same family as the
        # temporal-obl exclusion just above; this catches the shape where
        # the marker word IS the verb rather than heading an obl child.
        if sibling["deprel"] == "advcl" and (
            sibling["lemma"].lower() in SEQUENCE_CASE_MARKERS
            or sibling["lemma"].lower() in TEMPORAL_MARKERS_EXTRA
        ):
            continue''',
        "1c follow-up: exclude a sibling advcl whose own lemma is a sequence/temporal marker",
    )

    try:
        compile(src, "<cell51-patched-stage1extra>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    lines = src.splitlines(keepends=True)
    cell["source"] = lines
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"\nStage 1 (follow-up) complete. {len(src) - original_len:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

"""
Stage 5: harness-driven fixup. S1429's "penegasan" (lemma "tegas", a
pe-...-an nominalization) never matched GENERIC_CATEGORY_NOUNS because that
check only ever tested the LEMMA -- but several entries in the set (added in
both Iteration 1 and this iteration) are themselves derived-noun SURFACE
forms whose lemma differs. Check both. Reads and writes the notebook
directly (this is a follow-up correction after stage4's write, found via the
harness) -- same idempotent, anchor-guarded pattern as the earlier stages.
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
        '''    if (
        not sub_relations
        and clause_children
        and content_head["lemma"].lower() in GENERIC_CATEGORY_NOUNS
    ):''',
        '''    # AUDIT D1 (Iteration 2, harness fixup): several GENERIC_CATEGORY_NOUNS
    # entries are pe-/pen-/ke-...-an DERIVED nouns ("penegasan", "kedudukan")
    # whose Stanza LEMMA strips back to the root ("tegas", "duduk") -- the
    # lemma-only check could never match them. Check the surface text too.
    if (
        not sub_relations
        and clause_children
        and (
            content_head["lemma"].lower() in GENERIC_CATEGORY_NOUNS
            or content_head["text"].lower() in GENERIC_CATEGORY_NOUNS
        )
    ):''',
        "D1 fixup: check surface text too in decompose_object's GENERIC_CATEGORY_NOUNS gate",
    )

    old_n1e = '''            if (
                not sub_relations
                and obj_tok["lemma"].lower() in GENERIC_CATEGORY_NOUNS
            ):'''
    count = src.count(old_n1e)
    if count != 1:
        raise SystemExit(f"[FAIL] N1e gate anchor ambiguous/missing ({count})")
    new_n1e = '''            if (
                not sub_relations
                and (
                    obj_tok["lemma"].lower() in GENERIC_CATEGORY_NOUNS
                    or obj_tok["text"].lower() in GENERIC_CATEGORY_NOUNS
                )
            ):'''
    src = src.replace(old_n1e, new_n1e, 1)
    print("[ok] D1 fixup: check surface text too in _emit_relations_for_verb N1e gate")

    old_def_fallback = '''                if (
                    not sub_relations
                    and obj_tok["lemma"].lower() in GENERIC_CATEGORY_NOUNS
                ):'''
    count = src.count(old_def_fallback)
    if count != 1:
        raise SystemExit(f"[FAIL] extract_definition_relations fallback gate anchor ambiguous/missing ({count})")
    new_def_fallback = '''                if (
                    not sub_relations
                    and (
                        obj_tok["lemma"].lower() in GENERIC_CATEGORY_NOUNS
                        or obj_tok["text"].lower() in GENERIC_CATEGORY_NOUNS
                    )
                ):'''
    src = src.replace(old_def_fallback, new_def_fallback, 1)
    print("[ok] D1 fixup: check surface text too in extract_definition_relations fallback gate")

    try:
        compile(src, "<cell51-patched-stage5>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    lines = src.splitlines(keepends=True)
    cell["source"] = lines
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"\nStage 5 complete. {len(src) - original_len:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

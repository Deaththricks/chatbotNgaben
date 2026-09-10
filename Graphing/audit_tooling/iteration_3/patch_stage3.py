"""
Iteration 3, Stage 3: D1/D2 clause-retention generalization.

Investigation with real tokens found the plan's original S32/S61 citations
were STALE (pulled from the older relation_audit_report.md, pre-Iteration-2
-fix) -- both are already correct in the current output and NOT mentioned
in flag.txt at all. Confirmed genuinely still-broken per flag.txt: S2124
(3b), S1782 (3c), S2055 (3d). All three turned out to have much simpler,
lower-risk fixes than originally scoped, by widening existing narrow
mechanisms rather than adding new relation-splitting logic:

3b. Subject-side purpose-oblique ("swadharma beliau UNTUK mamari-suddha
    (menyucikan) dunia ini, merupakan fungsi pokok" -- S2124): the object
    side already has _purpose_oblique_children() to catch this shape; the
    subject side had no equivalent. New narrow branch in
    find_subject_clause_relations(), scoped to "untuk"-marked children only
    (not the full _PURPOSE_OBLIQUE_CASE_MARKS set, to stay conservative
    since this is genuinely new code, unlike 3c/3d below).

3c. "antara X dengan Y" attachment (S1782): the object head's nmod child
    ("mendiang", case "antara") wasn't recognized by
    _purpose_oblique_children() at all -- "antara" wasn't in
    _PURPOSE_OBLIQUE_CASE_MARKS. Added. This reuses the EXISTING glue-onto-
    object fallback (decompose_object's GENERIC_CATEGORY_NOUNS path) rather
    than requiring a new dedicated relation type, and is empirically
    verified: "upacara timbang" -> "upacara timbang, antara mendiang yang
    akan pergi ke dunia lain dengan keluarga (terutama anak-anak) yang
    masih hidup".

3d. bahwa-ccomp on the copula root (S2055, one of Iteration 2's own
    original D2 targets, still broken): "merupakan" attaches to "pertanda"
    via ccomp, not advcl -- _purpose_oblique_children()'s advcl branch never
    even looked at deprel=="ccomp". Widened the deprel check. Verified:
    "pertanda" -> "pertanda bahwa mereka merupakan keturunan dari orang
    yang condong pada paksa wesnawa" (exactly the flag.txt-requested fix).

3a (S32/S61) and 3e (S2198[3], re-check after Stage 4) are not part of this
patch -- 3a needs no code change (already fixed), 3e is deferred to after
Stage 4 lands per the plan.
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

    # ---- 3c: "antara" recognized as a purpose-oblique case marker ----
    src = apply(
        src,
        '_PURPOSE_OBLIQUE_CASE_MARKS = {"untuk", "dari", "bagi", "terhadap", "kepada", "dengan"}',
        '''_PURPOSE_OBLIQUE_CASE_MARKS = {"untuk", "dari", "bagi", "terhadap", "kepada", "dengan"}
# AUDIT (Iteration 3, S1782): "upacara timbang terima ... ANTARA mendiang
# ... DENGAN keluarga ..." -- "antara X dengan Y" names the two parties a
# rite is held between; the object head's nmod child carrying "antara" was
# invisible to _purpose_oblique_children() below, so the whole clause
# (which IS the point of the sentence) was dropped. Reuses the same
# glue-onto-object fallback as the other markers here, not a new relation
# type -- consistent with this codebase's existing terseness/safety stance.
_PURPOSE_OBLIQUE_CASE_MARKS = _PURPOSE_OBLIQUE_CASE_MARKS | {"antara"}''',
        "3c: add 'antara' to _PURPOSE_OBLIQUE_CASE_MARKS",
    )

    # ---- 3d: ccomp recognized alongside advcl for bahwa/agar/supaya/sehingga ----
    src = apply(
        src,
        '''def _purpose_oblique_children(token, tokens):
    out = []
    for child in tokens:
        if child["head"] != token["id"]:
            continue
        if child["deprel"] == "advcl":
            marks = {
                t["lemma"].lower() for t in tokens
                if t["head"] == child["id"] and t["deprel"] == "mark"
            }
            if marks & _PURPOSE_ADVCL_MARKS:
                out.append(child)
        elif child["deprel"] in ("nmod", "obl"):
            if get_case_marker(child, tokens) in _PURPOSE_OBLIQUE_CASE_MARKS:
                out.append(child)
    return out''',
        '''def _purpose_oblique_children(token, tokens):
    out = []
    for child in tokens:
        if child["head"] != token["id"]:
            continue
        # AUDIT (Iteration 3, S2055): a "bahwa"-clause restating the head
        # via a copula verb ("pertanda BAHWA mereka MERUPAKAN keturunan...")
        # attaches as ccomp, not advcl -- one of Iteration 2's own D2
        # targets, still broken because only advcl was ever checked here.
        # Same mark-based test as the advcl branch; ccomp genuinely shares
        # the "clause restates/defines the head" semantics advcl already
        # covers for bahwa/sehingga.
        if child["deprel"] in ("advcl", "ccomp"):
            marks = {
                t["lemma"].lower() for t in tokens
                if t["head"] == child["id"] and t["deprel"] == "mark"
            }
            if marks & _PURPOSE_ADVCL_MARKS:
                out.append(child)
        elif child["deprel"] in ("nmod", "obl"):
            if get_case_marker(child, tokens) in _PURPOSE_OBLIQUE_CASE_MARKS:
                out.append(child)
    return out''',
        "3d: recognize ccomp alongside advcl in _purpose_oblique_children",
    )

    # ---- 3b: subject-side purpose-oblique -> its own BERTUJUAN_UNTUK relation ----
    src = apply(
        src,
        '''def find_subject_clause_relations(subject_phrase, subject_label, subject_head, tokens):

    extra_relations = []

    clause_children = [
        child for child in tokens
        if child["head"] == subject_head["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]''',
        '''def find_subject_clause_relations(subject_phrase, subject_label, subject_head, tokens):

    extra_relations = []

    # AUDIT D1/D2 (Iteration 3, S2124): "swadharma beliau UNTUK mamari-
    # suddha (menyucikan) dunia ini, merupakan fungsi pokok" -- the purpose
    # clause sits on the SUBJECT head, not the object. The object-side
    # equivalent (_purpose_oblique_children, used throughout 13.5d) has no
    # subject-side counterpart, so this was silently dropped, leaving a
    # content-free "X ADALAH fungsi pokok". Scoped narrowly to "untuk"
    # (purpose) only, not the full _PURPOSE_OBLIQUE_CASE_MARKS set -- this
    # is new code on the subject side, not a widening of an already-proven
    # mechanism like 3c/3d, so stay conservative.
    for purpose_child in _purpose_oblique_children(subject_head, tokens):
        if get_case_marker(purpose_child, tokens) != "untuk":
            continue
        if is_negated(purpose_child, tokens):
            continue
        purpose_child = resolve_conjunct_head(purpose_child, tokens)
        purpose_phrase, _purpose_clausal = expand_object_with_clauses(purpose_child, tokens)
        purpose_phrase = _strip_stray_ring_head(purpose_phrase)
        if (
            purpose_phrase.strip()
            and subject_phrase.lower().strip() != purpose_phrase.lower().strip()
        ):
            extra_relations.append({
                "subject": subject_phrase,
                "subject_label": subject_label,
                "relation": "BERTUJUAN_UNTUK",
                "object": purpose_phrase,
                "object_label": None,
                "object_is_clausal": _purpose_clausal,
                "source": "dependency_rule",
            })

    clause_children = [
        child for child in tokens
        if child["head"] == subject_head["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]''',
        "3b: subject-side purpose-oblique -> BERTUJUAN_UNTUK relation in find_subject_clause_relations",
    )

    try:
        compile(src, "<cell51-patched-stage3>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    lines = src.splitlines(keepends=True)
    cell["source"] = lines
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"\nStage 3 complete. {len(src) - original_len:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

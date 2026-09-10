"""
Iteration 3, Stage 2: D4 (plain coordinate-member truncation), still open
per fresh flag.txt evidence. Investigation (real tokens, not guessed) found
TWO distinct narrow gaps, not the "wire into more functions" fix the report
originally guessed:

Fix A: _compound_child_conjunct_phrases() only checked ONE hop of the
compound/flat/flat:name chain below the object head. S3153 ("arang
pembakaran jaja uli ATAU jaja gina") needs THREE hops (arang -> pembakaran
-> jaja[uli] -conj-> jaja[gina]) -- widened to a transitive BFS walk of the
whole compound chain, same spirit as get_conjuncts()'s own N10 transitive
fix.

Fix B: a genuinely different shape -- "di warung ATAU di dapur" (S3836),
"di pura ATAU di merajan" (S3845) -- the second alternative carries its OWN
case marker, so Stanza attaches it as an `nmod` of the first noun rather
than a `conj` of it. New narrow helper `_nmod_cc_conjunct_phrases()` only
fires on an nmod child that ALSO has its own case-marker child AND its own
cc child (both signals required, to avoid over-firing on ordinary nmod
modifiers that aren't coordinate members at all).

Investigated and deliberately NOT included in this stage (confirmed via
real tokens, not the shape this fix targets): S2374/S2455/S2566/S2419/S4175
are D1/D2/D9/D3-family clause-retention or terseness issues, not coordinate
-member loss. S3063's "maupun dari hal-hal yang lain" is a badly garbled
parse (the second alternative attaches 4 levels deep inside an unrelated
nested relative clause) -- not a safe general-rule target; left for a
Stage 9 manual override instead.
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

    # ---- Fix A: transitive compound-chain walk ----
    src = apply(
        src,
        '''def _compound_child_conjunct_phrases(head_token, tokens):
    """
    AUDIT D4 (Iteration 2): when head_token itself carries no conj (the
    normal get_conjuncts() path already handles that case), check
    whether a compound/flat child of it does -- "sasih kasa dan kapitu"
    parses with "kapitu" as conj of "kasa" (compound child of "sasih"),
    not of "sasih" directly. Returns one rendered phrase per conjunct,
    substituting the compound child's own text with the conjunct's own
    phrase inside head_token's full phrase -- "sasih kasa" ->
    ["sasih kapitu"] -- so the shared "sasih" prefix survives instead of
    being lost (which a bare get_conjuncts()-on-the-child would do).
    """
    if get_conjuncts(head_token, tokens):
        return []

    base_phrase = expand_phrase(head_token, tokens)

    for child in tokens:
        if (
            child["head"] != head_token["id"]
            or child["deprel"] not in ("compound", "flat", "flat:name")
        ):
            continue
        conjuncts = get_conjuncts(child, tokens)
        if not conjuncts:
            continue
        phrases = []
        for conjunct in conjuncts:
            conjunct = resolve_conjunct_head(conjunct, tokens)
            replacement = expand_phrase(conjunct, tokens)
            if child["text"] in base_phrase:
                phrases.append(base_phrase.replace(child["text"], replacement, 1))
            else:
                phrases.append(f"{base_phrase} {replacement}")
        return phrases

    return []''',
        '''def _compound_child_conjunct_phrases(head_token, tokens):
    """
    AUDIT D4 (Iteration 2, widened Iteration 3): when head_token itself
    carries no conj (the normal get_conjuncts() path already handles that
    case), check whether a DESCENDANT reached by walking a chain of
    compound/flat/flat:name children does -- "sasih kasa dan kapitu"
    parses with "kapitu" as conj of "kasa" (a compound child of "sasih"),
    not of "sasih" directly; "arang pembakaran jaja uli atau jaja gina"
    (S3153) is the same shape one hop deeper -- "jaja"(gina) is conj of
    "jaja"(uli), a compound child of "pembakaran", itself a compound child
    of "arang". Walks the whole compound chain (BFS, not just the first
    hop) looking for the first node with a conjunct, and substitutes that
    node's own text with each conjunct's rendered phrase inside
    head_token's full phrase -- so the shared prefix survives instead of
    being lost, at whatever depth the real conjunct sits.
    """
    if get_conjuncts(head_token, tokens):
        return []

    base_phrase = expand_phrase(head_token, tokens)

    frontier = [head_token]
    visited = {head_token["id"]}
    while frontier:
        current = frontier.pop(0)
        compound_children = sorted(
            (
                child for child in tokens
                if child["head"] == current["id"]
                and child["deprel"] in ("compound", "flat", "flat:name")
                and child["id"] not in visited
            ),
            key=lambda x: x["id"],
        )
        for child in compound_children:
            visited.add(child["id"])
            conjuncts = get_conjuncts(child, tokens)
            if conjuncts:
                phrases = []
                for conjunct in conjuncts:
                    conjunct = resolve_conjunct_head(conjunct, tokens)
                    replacement = expand_phrase(conjunct, tokens)
                    if child["text"] in base_phrase:
                        phrases.append(base_phrase.replace(child["text"], replacement, 1))
                    else:
                        phrases.append(f"{base_phrase} {replacement}")
                return phrases
            frontier.append(child)

    return []


def _nmod_cc_conjunct_phrases(head_token, tokens):
    """
    AUDIT D4 (Iteration 3): a second alternative in a locative/
    prepositional coordination sometimes parses as an `nmod` child of the
    first noun rather than a plain `conj` -- "di warung atau di dapur"
    (S3836), "di pura atau di merajan" (S3845) -- because the second
    alternative carries its OWN case marker ("di"), Stanza attaches it as
    a separate PP modifying the first noun instead of coordinating it.
    Recognize this narrow, specific shape only: an nmod child that (a) has
    its own case-marker child (independently case-marked, not a bare
    modifier) AND (b) has its own cc child (a coordinating conjunction
    genuinely attached to IT, confirming it reads as a coordinate
    alternative rather than an ordinary modifier) -- both signals
    required, to avoid over-firing on ordinary nmod modifiers. Returns one
    rendered phrase per such nmod-conjunct (just the child's own phrase,
    not head_token's -- unlike the compound-chain case above there is no
    shared prefix embedded inside a single object token to preserve).
    """
    if get_conjuncts(head_token, tokens):
        return []

    phrases = []
    for child in tokens:
        if child["head"] != head_token["id"] or child["deprel"] != "nmod":
            continue
        has_own_case = any(
            c["head"] == child["id"] and c["deprel"] == "case" for c in tokens
        )
        has_own_cc = any(
            c["head"] == child["id"] and c["deprel"] == "cc" for c in tokens
        )
        if has_own_case and has_own_cc:
            phrases.append(expand_phrase(child, tokens))
    return phrases''',
        "Stage 2 Fix A+B: transitive compound-chain walk + new nmod+cc conjunct helper",
    )

    # ---- wire Fix B's helper into _emit_relations_for_verb ----
    src = apply(
        src,
        '''        for extra_phrase in _compound_child_conjunct_phrases(object_token, tokens):
            if subject_phrase.lower().strip() == extra_phrase.lower().strip():
                continue
            d4_subject, d4_object = (
                (extra_phrase, subject_phrase) if _swap_termasuk
                else (subject_phrase, extra_phrase)
            )
            emitted.append({
                "sentence_id": sentence_id,
                "subject": d4_subject,
                "subject_label": subject_label if not _swap_termasuk else None,
                "relation": raw_label,
                "object": d4_object,
                "object_label": None,
                "object_is_clausal": False,
                "source": "dependency_rule",
            })

        for obj_tok in all_object_tokens:''',
        '''        for extra_phrase in _compound_child_conjunct_phrases(object_token, tokens):
            if subject_phrase.lower().strip() == extra_phrase.lower().strip():
                continue
            d4_subject, d4_object = (
                (extra_phrase, subject_phrase) if _swap_termasuk
                else (subject_phrase, extra_phrase)
            )
            emitted.append({
                "sentence_id": sentence_id,
                "subject": d4_subject,
                "subject_label": subject_label if not _swap_termasuk else None,
                "relation": raw_label,
                "object": d4_object,
                "object_label": None,
                "object_is_clausal": False,
                "source": "dependency_rule",
            })

        # AUDIT D4 (Iteration 3): the OTHER narrow shape -- see
        # _nmod_cc_conjunct_phrases()'s own docstring. Same emission
        # pattern as the compound-chain block just above.
        for extra_phrase in _nmod_cc_conjunct_phrases(object_token, tokens):
            if subject_phrase.lower().strip() == extra_phrase.lower().strip():
                continue
            d4_subject, d4_object = (
                (extra_phrase, subject_phrase) if _swap_termasuk
                else (subject_phrase, extra_phrase)
            )
            emitted.append({
                "sentence_id": sentence_id,
                "subject": d4_subject,
                "subject_label": subject_label if not _swap_termasuk else None,
                "relation": raw_label,
                "object": d4_object,
                "object_label": None,
                "object_is_clausal": False,
                "source": "dependency_rule",
            })

        for obj_tok in all_object_tokens:''',
        "Stage 2: wire _nmod_cc_conjunct_phrases into _emit_relations_for_verb",
    )

    try:
        compile(src, "<cell51-patched-stage2>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    lines = src.splitlines(keepends=True)
    cell["source"] = lines
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"\nStage 2 complete. {len(src) - original_len:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

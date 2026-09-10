"""
Stage 2 of the Iteration 2 patch: D3, D4, D9 (partial), D10, D14, plus the
extract_definition_relations verb-level fallback and the
find_subject_clause_relations D8/D9 branches, and the MANUAL_RELATION_OVERRIDES
additions. Reads audit_tooling/iteration_2/_stage1_source.txt (produced by
patch_iter2.py), applies its own anchor-guarded edits, writes
audit_tooling/iteration_2/_stage2_source.txt.
"""
import json

STAGE1_PATH = "audit_tooling/iteration_2/_stage1_source.txt"
STAGE2_PATH = "audit_tooling/iteration_2/_stage2_source.txt"


def apply(src, old, new, label):
    count = src.count(old)
    if count == 0:
        raise SystemExit(f"[FAIL] anchor not found for: {label}")
    if count > 1:
        raise SystemExit(f"[FAIL] anchor ambiguous ({count} matches) for: {label}")
    print(f"[ok] {label}")
    return src.replace(old, new, 1)


def main():
    with open(STAGE1_PATH, "r", encoding="utf-8") as f:
        src = f.read()
    original_len = len(src)

    # ------------------------------------------------------------------
    # 1. D3: subject-side coordinate NPs never got the transitive
    #    conjunct walk objects already have -- "abu tulang kepala,
    #    tangan, punggung, dada, bokong, paha DAN kaki" (S1439, 7-way!)
    #    collapsed to just "abu tulang kepala" because expand_phrase()'s
    #    collect_phrase_tokens() deliberately never walks `conj` (the
    #    object side instead loops get_conjuncts() at the call site,
    #    emitting one relation per member -- subjects share one predicate
    #    across all members, so here they're joined into one phrase
    #    instead). New helper, applied at both call sites that build a
    #    top-level entity's subject phrase.
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''CCONJ_LEMMAS = {"dan", "atau", "lan", "serta"}''',
        '''CCONJ_LEMMAS = {"dan", "atau", "lan", "serta"}


def _coordinator_lemma(conjunct_token, tokens):
    """The cc lemma (dan/atau/serta/lan) coordinating this conjunct, if any."""
    for child in tokens:
        if child["head"] == conjunct_token["id"] and child["deprel"] == "cc":
            return child["lemma"].lower()
    return None


def expand_subject_phrase(subject_head, tokens):
    """
    AUDIT D3 (Iteration 2): like expand_phrase(), but when subject_head
    has coordinate (conj) siblings -- "abu tulang kepala, tangan,
    punggung, dada, bokong, paha dan kaki" (S1439) -- render the full
    coordinated list instead of silently keeping only the head's own
    phrase. get_conjuncts()'s transitive walk (AUDIT N10, Iteration 1)
    was already available but never invoked for the SUBJECT NP -- only
    the object side loops it, emitting one relation per conjunct member,
    which doesn't fit subjects (the predicate/object stay the same for
    every member, so here they're joined into one phrase instead: "sasih
    kaenem dan kapitu", not two separate relations).
    """
    base = expand_phrase(subject_head, tokens)
    conjuncts = get_conjuncts(subject_head, tokens)
    if not conjuncts:
        return base

    coordinator = None
    parts = [base]
    for c in conjuncts:
        c = resolve_conjunct_head(c, tokens)
        parts.append(expand_phrase(c, tokens))
        cc = _coordinator_lemma(c, tokens)
        if cc:
            coordinator = cc

    if coordinator is None:
        coordinator = "dan"

    if len(parts) == 2:
        return f"{parts[0]} {coordinator} {parts[1]}"

    return ", ".join(parts[:-1]) + f", {coordinator} {parts[-1]}"''',
        "D3: add expand_subject_phrase helper",
    )

    # Apply at the two top-level subject-phrase construction sites.
    old_subj_1 = '''            # FIX #7: expand subject along the dependency tree
            # (nested compounds like "sasih paruwak tahuk") instead
            # of trusting the raw NER-matched entity text.
            subject_phrase = expand_phrase(subject_head, tokens)

            # Predikat = head dari subject.'''
    new_subj_1 = '''            # FIX #7: expand subject along the dependency tree
            # (nested compounds like "sasih paruwak tahuk") instead
            # of trusting the raw NER-matched entity text.
            # AUDIT D3 (Iteration 2): also join any coordinate (conj)
            # subject members into the phrase -- see expand_subject_phrase().
            subject_phrase = expand_subject_phrase(subject_head, tokens)

            # Predikat = head dari subject.'''
    src = apply(src, old_subj_1, new_subj_1, "D3: apply expand_subject_phrase in extract_subject_verb_relations")

    old_subj_2 = '''            # FIX #7: expand the subject along the dependency tree
            # instead of trusting the raw NER-matched entity text.
            subject_phrase = expand_phrase(subject_head, tokens)'''
    new_subj_2 = '''            # FIX #7: expand the subject along the dependency tree
            # instead of trusting the raw NER-matched entity text.
            # AUDIT D3 (Iteration 2): also join any coordinate (conj)
            # subject members into the phrase -- see expand_subject_phrase().
            subject_phrase = expand_subject_phrase(subject_head, tokens)'''
    src = apply(src, old_subj_2, new_subj_2, "D3: apply expand_subject_phrase in extract_definition_relations")

    # ------------------------------------------------------------------
    # 2. D4: a coordinate member sometimes chains off a COMPOUND
    #    MODIFIER of the resolved object head, not the head itself --
    #    "sasih kasa dan kapitu": "kapitu" is conj of "kasa" (a compound
    #    child of "sasih"), so get_conjuncts(sasih) finds nothing
    #    (flag.txt's own S411/S413/S414, still broken after two
    #    iterations). New helper producing one substitute PHRASE per
    #    conjunct (keeping the shared "sasih" prefix), applied in
    #    _emit_relations_for_verb's object loop.
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''def resolve_conjunct_head(token, tokens):''',
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

    return []


def resolve_conjunct_head(token, tokens):''',
        "D4: add _compound_child_conjunct_phrases helper",
    )

    old_verb_obj_loop = '''        all_object_tokens = (
            [object_token]
            + get_conjuncts(object_token, tokens)
        )

        for obj_tok in all_object_tokens:

            obj_tok = resolve_conjunct_head(obj_tok, tokens)

            if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                continue

            object_phrase, object_has_clause, sub_relations = resolve_object(
                obj_tok, tokens, subject_phrase
            )'''
    new_verb_obj_loop = '''        all_object_tokens = (
            [object_token]
            + get_conjuncts(object_token, tokens)
        )

        # AUDIT D4 (Iteration 2): a compound-child conjunct ("sasih
        # kasa dan kapitu") isn't a token to resolve_object() the
        # normal way -- it's already a fully-rendered substitute
        # phrase for the SAME object_token. Emit those directly,
        # alongside (not instead of) the normal per-token loop below.
        # (raw_label here is already fully resolved -- any N6/D7 swap
        # sentinel was converted to its real label above; this block
        # only handles the D4 shape, unrelated to those swaps.)
        for extra_phrase in _compound_child_conjunct_phrases(object_token, tokens):
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

        for obj_tok in all_object_tokens:

            obj_tok = resolve_conjunct_head(obj_tok, tokens)

            if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                continue

            object_phrase, object_has_clause, sub_relations = resolve_object(
                obj_tok, tokens, subject_phrase
            )'''
    src = apply(src, old_verb_obj_loop, new_verb_obj_loop, "D4: apply compound-child conjunct phrases in verb-emit loop")

    # ------------------------------------------------------------------
    # 3. D7: resolve the "_SWAP_DIPERSEMBAHKAN_KEPADA" sentinel added in
    #    stage 1's derive_raw_relation_label() -- same swap mechanism as
    #    the existing N6 _swap_termasuk, applied alongside it.
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''        # AUDIT N6/S11 (Iteration 1): see the sentinel comment in
        # derive_raw_relation_label().
        _swap_termasuk = (raw_label == "_SWAP_JENIS_DARI")
        if _swap_termasuk:
            raw_label = "JENIS_DARI"''',
        '''        # AUDIT N6/S11 (Iteration 1): see the sentinel comment in
        # derive_raw_relation_label().
        _swap_termasuk = (raw_label == "_SWAP_JENIS_DARI")
        if _swap_termasuk:
            raw_label = "JENIS_DARI"

        # AUDIT D7 (Iteration 2): see the sentinel comment in
        # derive_raw_relation_label().
        _swap_offer = (raw_label == "_SWAP_DIPERSEMBAHKAN_KEPADA")
        if _swap_offer:
            raw_label = "DIPERSEMBAHKAN_KEPADA"''',
        "D7: resolve swap sentinel (part 1)",
    )
    src = apply(
        src,
        '''            # "X termasuk Y" case flagged above.
            final_subject, final_subject_label, final_object = (
                (object_phrase, None, subject_phrase)
                if _swap_termasuk
                else (subject_phrase, subject_label, object_phrase)
            )''',
        '''            # "X termasuk Y" case flagged above, and AUDIT D7 (Iteration 2)
            # for the benefactive-passive swap.
            final_subject, final_subject_label, final_object = (
                (object_phrase, None, subject_phrase)
                if (_swap_termasuk or _swap_offer)
                else (subject_phrase, subject_label, object_phrase)
            )''',
        "D7: resolve swap sentinel (part 2)",
    )

    with open(STAGE2_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print(f"\nStage 2 complete. {len(src) - original_len:+d} chars.")


if __name__ == "__main__":
    main()

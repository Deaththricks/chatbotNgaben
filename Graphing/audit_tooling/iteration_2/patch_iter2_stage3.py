"""
Stage 3 of the Iteration 2 patch: D8 (contents-clause), D9 (bade/patulangan
shape clause + temporal-nmod subject-fusion), D2 (definition-path verb-level
fallback), D10 (attribution phrasing + sebagaimana-halnya), D14 (self-loop
filter), and D1/D8 housekeeping (S3756-3758 note only, no code change
needed -- verified already present). Reads _stage2_source.txt, writes
_stage3_source.txt.
"""

STAGE2_PATH = "audit_tooling/iteration_2/_stage2_source.txt"
STAGE3_PATH = "audit_tooling/iteration_2/_stage3_source.txt"


def apply(src, old, new, label):
    count = src.count(old)
    if count == 0:
        raise SystemExit(f"[FAIL] anchor not found for: {label}")
    if count > 1:
        raise SystemExit(f"[FAIL] anchor ambiguous ({count} matches) for: {label}")
    print(f"[ok] {label}")
    return src.replace(old, new, 1)


def main():
    with open(STAGE2_PATH, "r", encoding="utf-8") as f:
        src = f.read()
    original_len = len(src)

    # ------------------------------------------------------------------
    # 1. D9: collect_phrase_tokens() -- a "semasa/di masa X" temporal-era
    #    nmod is clause-level time-framing ("mendiang SEMASA HIDUPNYA
    #    punya...", S1738; "bila mendiang DI MASA HIDUPNYA memegang...",
    #    S1823), not part of the entity's own identity, but was getting
    #    glued into the subject NP as "mendiang hidup" / "mendiang masa
    #    hidup".
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''        if child["deprel"] not in [
            "amod",
            "compound",
            "flat",
            "flat:name",
            "fixed",
            "nmod",
            "nummod"
        ]:
            continue

        distance = abs(child["id"] - token["id"])''',
        '''        if child["deprel"] not in [
            "amod",
            "compound",
            "flat",
            "flat:name",
            "fixed",
            "nmod",
            "nummod"
        ]:
            continue

        # AUDIT D9 (Iteration 2): a "semasa/di masa X" temporal-era nmod
        # is clause-level time-framing, not part of the entity's own
        # identity -- was getting silently glued into the subject/object
        # NP ("mendiang hidup" / "mendiang masa hidup", S1738/S1823).
        if child["deprel"] == "nmod" and (
            get_case_marker(child, tokens) == "semasa"
            or child["lemma"].lower() == "masa"
        ):
            continue

        distance = abs(child["id"] - token["id"])''',
        "D9: temporal-era nmod exclusion in collect_phrase_tokens",
    )

    # ------------------------------------------------------------------
    # 2. D8/D9: find_subject_clause_relations() -- add a branch for
    #    "isi"/"berisi" (D8: recovers the contents clause the S15 label
    #    fix above deliberately stopped attaching to the main verb, e.g.
    #    "kawangen YANG BERISI 9 biji uang kepeng...", S3747/S3749/S3753)
    #    and for _SHAPE_MEANING_NONCOPULA surface forms (D9: "patulangan
    #    YANG BERBENTUK naga kahang dan gajah mina...", S2055/S2056 --
    #    is_definition_predicate() deliberately excludes these so they
    #    route through the ordinary verb cascade instead of ADALAH, but
    #    that means NONE of the existing subject-clause branches
    #    recognized them, so the whole clause was silently dropped).
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''        elif surface.startswith("terdiri"):
            raw_label = "TERDIRI_DARI"
            object_candidates = find_object_tokens(clause_root, tokens)''',
        '''        elif surface.startswith("terdiri"):
            raw_label = "TERDIRI_DARI"
            object_candidates = find_object_tokens(clause_root, tokens)
        elif lemma == "isi" or surface.startswith("berisi") or surface.startswith("diisi"):
            # AUDIT D8 (Iteration 2): "kawangen YANG BERISI 9 biji uang
            # kepeng dan bunga tunjung putih" -- the contents clause on
            # the subject itself, not previously recognized here.
            raw_label = "BERISI"
            object_candidates = find_object_tokens(clause_root, tokens)
        elif surface in _SHAPE_MEANING_NONCOPULA:
            # AUDIT D9 (Iteration 2): "patulangan YANG BERBENTUK naga
            # kahang dan gajah mina ..." -- is_definition_predicate()
            # deliberately excludes these surface forms (AUDIT S4) so
            # they route through the ordinary verb-label cascade instead
            # of ADALAH, but that meant no subject-clause branch here
            # recognized them either, and the whole clause was dropped.
            candidates = find_object_tokens(clause_root, tokens)
            if candidates:
                raw_label = derive_raw_relation_label(
                    clause_root, candidates[0][0], tokens, candidates[0][1]
                )
                object_candidates = candidates''',
        "D8/D9: new find_subject_clause_relations branches",
    )

    # ------------------------------------------------------------------
    # 3. D2: extract_definition_relations() has no equivalent of
    #    _emit_relations_for_verb's N1e verb-level fallback -- "damar
    #    kurung ITU MERUPAKAN sarana permohonan ..., AGAR keletehan ...
    #    diblokir..." (S1136) has the agar-advcl attached to the
    #    copula VERB ("merupakan") itself, a sibling of the object
    #    ("sarana"), not to the object noun -- so it was silently
    #    dropped no matter how GENERIC_CATEGORY_NOUNS or
    #    _purpose_oblique_children was widened on the object side alone.
    # ------------------------------------------------------------------
    old_def_obj_loop = '''            for obj_tok in all_object_tokens:

                obj_tok = resolve_conjunct_head(obj_tok, tokens)

                if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                    continue

                # FIX #6c: expand_object_with_clauses() (bukan
                # expand_phrase() biasa) supaya relative/
                # complement clause DAN appositive gloss yang
                # menempel di object head ikut kebawa, bukan
                # hilang jadi noun kosong.
                object_phrase, object_has_clause, sub_relations = resolve_object(
                    obj_tok,
                    tokens,
                    subject_phrase
                )'''
    new_def_obj_loop = '''            for obj_tok in all_object_tokens:

                obj_tok = resolve_conjunct_head(obj_tok, tokens)

                if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                    continue

                # FIX #6c: expand_object_with_clauses() (bukan
                # expand_phrase() biasa) supaya relative/
                # complement clause DAN appositive gloss yang
                # menempel di object head ikut kebawa, bukan
                # hilang jadi noun kosong.
                object_phrase, object_has_clause, sub_relations = resolve_object(
                    obj_tok,
                    tokens,
                    subject_phrase
                )

                # AUDIT D2 (Iteration 2): a defining purpose/consequence
                # clause sometimes hangs off the copula VERB
                # (predicate_token) as a sibling of the object rather
                # than off the object noun -- see the N1e comment in
                # _emit_relations_for_verb() for the mirror case on the
                # non-copula path.
                if (
                    not sub_relations
                    and obj_tok["lemma"].lower() in GENERIC_CATEGORY_NOUNS
                ):
                    verb_purpose = [
                        c for c in _purpose_oblique_children(predicate_token, tokens)
                        + [t for t in tokens
                           if t["head"] == predicate_token["id"] and t["deprel"] == "xcomp"]
                        if c["id"] != obj_tok["id"]
                    ]
                    if verb_purpose:
                        extra = " ".join(
                            render_subtree_text(c, tokens)
                            for c in sorted(verb_purpose, key=lambda x: x["id"])
                        )
                        if extra.strip() and extra.strip().lower() not in object_phrase.lower():
                            object_phrase = f"{object_phrase} {extra}"
                            object_has_clause = True'''
    src = apply(src, old_def_obj_loop, new_def_obj_loop, "D2: verb-level fallback in extract_definition_relations")

    # ------------------------------------------------------------------
    # 4. D10: widen _ATTRIBUTION_OBJECT_PATTERN -- "mata (umat|orang)"
    #    without requiring a leading "di" (the case marker is usually
    #    consumed into the relation label, e.g. DINILAI_DI, so it never
    #    survives in the object string, S1226); "dalam ... lontar" with
    #    an intervening quantifier ("tertulis dalam BEBERAPA lontar",
    #    S972); bare "lontar" as an exact-match object (a truncated
    #    citation reference on its own, S283).
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''_ATTRIBUTION_OBJECT_PATTERN = re.compile(
    r"\\b(menurut|sebagaimana|dalam lontar|pada lontar|lontar (yama|petunjuk)"
    r"|uraian terdahulu|lembaran terdahulu|di mata (umat|orang))\\b",
    re.IGNORECASE,
)
relations = [
    relation for relation in relations
    if not _ATTRIBUTION_OBJECT_PATTERN.search(relation["object"])
]''',
        '''_ATTRIBUTION_OBJECT_PATTERN = re.compile(
    r"\\b(menurut|sebagaimana|dalam\\s+(?:\\w+\\s+)?lontar|pada lontar"
    r"|lontar (yama|petunjuk)|uraian terdahulu|lembaran terdahulu"
    r"|mata (umat|orang))\\b",
    re.IGNORECASE,
)
relations = [
    relation for relation in relations
    if not _ATTRIBUTION_OBJECT_PATTERN.search(relation["object"])
]

# AUDIT D10 (Iteration 2): a bare, unqualified "lontar" object is always
# a truncated citation reference in this corpus (the surrounding "dalam
# lontar X" context gets lost during decomposition, leaving just the
# word itself) -- never real content about the subject.
relations = [
    relation for relation in relations
    if relation["object"].strip().lower() != "lontar"
]''',
        "D10: widen _ATTRIBUTION_OBJECT_PATTERN + bare-lontar filter",
    )

    # ------------------------------------------------------------------
    # 5. D10: "sebagaimana halnya X" (S2542) -- "hal" already has a
    #    generic discourse-connective check, but it only fires when
    #    EVERY child of "hal" is a bare filler pronoun; "halnya
    #    pangabenan" carries real content ("pangabenan") as its
    #    compound child, so the existing check didn't catch it. But
    #    "hal" governed by a SIMILATIVE case marker ("sebagaimana") is
    #    unambiguously a comparison introducer regardless of what
    #    follows it.
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''def _is_bare_discourse_connective(candidate, tokens):

    if candidate["lemma"].lower() not in DISCOURSE_CONNECTIVE_LEMMAS:
        return False''',
        '''def _is_bare_discourse_connective(candidate, tokens):

    # AUDIT D10 (Iteration 2): "sebagaimana halnya pangabenan" (S2542) --
    # "hal" governed by a similative marker is a comparison introducer no
    # matter what content its own compound child carries.
    if (
        candidate["lemma"].lower() == "hal"
        and get_case_marker(candidate, tokens) in SIMILATIVE_CASE_MARKERS
    ):
        return True

    if candidate["lemma"].lower() not in DISCOURSE_CONNECTIVE_LEMMAS:
        return False''',
        "D10: sebagaimana-halnya comparative filter",
    )

    # ------------------------------------------------------------------
    # 6. D14: final filter -- drop a triple whose subject and object
    #    resolve to the same referent under light normalization
    #    (whitespace/punctuation, plus a couple of spelling variants
    #    this corpus uses interchangeably) -- "kwangen jeriji DITARUH
    #    kawangen jeriji" (S3733).
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''# ==========================================
# 13.10b. REMOVE DUPLICATE RELATIONS
# ==========================================''',
        '''# AUDIT D14 (Iteration 2): subject and object resolving to the same
# referent (spelled two ways) carries no information -- "kwangen jeriji
# DITARUH kawangen jeriji" (S3733). The exact-match self-loop guards at
# each extraction call site (FIX #5 etc.) don't catch spelling variants;
# this final pass does, for the handful this corpus uses interchangeably.
_SELF_LOOP_SPELLING_VARIANTS = {"kwangen": "kawangen"}


def _normalize_for_self_loop(text):
    words = re.sub(r"[^a-z0-9\\s]", "", text.lower()).split()
    words = [_SELF_LOOP_SPELLING_VARIANTS.get(w, w) for w in words]
    return " ".join(words)


relations = [
    relation for relation in relations
    if _normalize_for_self_loop(relation["subject"])
    != _normalize_for_self_loop(relation["object"])
]

# ==========================================
# 13.10b. REMOVE DUPLICATE RELATIONS
# ==========================================''',
        "D14: self-loop final filter",
    )

    with open(STAGE3_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    print(f"\nStage 3 complete. {len(src) - original_len:+d} chars.")


if __name__ == "__main__":
    main()

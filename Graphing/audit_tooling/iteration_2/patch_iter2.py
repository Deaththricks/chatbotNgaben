"""
Iteration 2 fix batch (D1-D14) for Knowledge Processing.ipynb cell 51.
Idempotent, anchor-guarded: each replacement asserts its OLD text is
present exactly once before touching the file. Run from repo root:
    python audit_tooling/iteration_2/patch_iter2.py
"""
import json
import re
import sys

NB_PATH = "Knowledge Processing.ipynb"
CELL_INDEX = 51


def load_cell_source(nb):
    cell = nb["cells"][CELL_INDEX]
    src = "".join(cell["source"])
    return cell, src


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

    cell, src = load_cell_source(nb)
    original_len = len(src)

    # ------------------------------------------------------------------
    # 1. D2: widen _PURPOSE_ADVCL_MARKS with "bahwa" (S1429/S2055 bahwa-
    #    ccomp/advcl) and "sehingga" (S4074 sibling-consequence clause).
    #    Also add "kala" to TEMPORAL_ADJUNCT_LEMMAS (D13, S1603).
    # ------------------------------------------------------------------
    src = apply(
        src,
        '_PURPOSE_ADVCL_MARKS = {"untuk", "agar", "supaya"}',
        (
            '_PURPOSE_ADVCL_MARKS = {"untuk", "agar", "supaya"}\n'
            "# AUDIT D2 (Iteration 2): a defining clause is also introduced by\n"
            '# "bahwa" ("daksina ADALAH penegasan ... BAHWA yadnya sudah selesai",\n'
            "# S1429/S2055 -- a ccomp/advcl-style complement, not a purpose clause,\n"
            "# but structurally reached the same way) or hangs off the governing\n"
            '# verb as a "sehingga"-consequence sibling (S4074) rather than a\n'
            "# purpose oblique -- both carry the sentence's real content just as\n"
            "# much as untuk/agar/supaya do.\n"
            '_PURPOSE_ADVCL_MARKS = {"untuk", "agar", "supaya", "bahwa", "sehingga"}'
        ),
        "D2: widen _PURPOSE_ADVCL_MARKS (bahwa/sehingga)",
    )

    src = apply(
        src,
        'TEMPORAL_ADJUNCT_LEMMAS = {"saat", "waktu", "ketika"}',
        (
            "# AUDIT D13 (Iteration 2): \"kala\" (\"di kala X\" = \"at the time X\") is a\n"
            "# synonym of saat/waktu/ketika that was missing here -- see\n"
            "# find_coordinated_verb_relations()'s temporal-oblique guard below.\n"
            'TEMPORAL_ADJUNCT_LEMMAS = {"saat", "waktu", "ketika", "kala"}'
        ),
        "D13: add 'kala' to TEMPORAL_ADJUNCT_LEMMAS",
    )

    # ------------------------------------------------------------------
    # 2. D13: find_coordinated_verb_relations -- skip an advcl sibling
    #    that is really a temporal-framing clause's own (mis-attached)
    #    content, not a genuine coordinate action sharing the subject.
    #    Fixes S1187 (sesajen/abu) and S1603 (lancingan kajang/jenazah),
    #    both flag.txt-#58b-family wrong-subject bugs.
    # ------------------------------------------------------------------
    old_find_coord = '''def find_coordinated_verb_relations(relation_token, tokens):

    siblings = [
        child for child in tokens
        if child["head"] == relation_token["id"]
        and child["deprel"] in ("conj", "advcl")
        and child["upos"] == "VERB"
    ]

    result = []

    for sibling in sorted(siblings, key=lambda x: x["id"]):

        if sibling["deprel"] == "advcl" and _advcl_has_subordinate_mark(sibling, tokens):
            continue

        has_own_subject = any(
            grandchild["head"] == sibling["id"]
            and grandchild["deprel"] in ("nsubj", "nsubj:pass")
            for grandchild in tokens
        )

        if has_own_subject:
            continue

        if is_negated(sibling, tokens):
            continue

        result.append(sibling)

    return result'''
    new_find_coord = '''def _obl_has_temporal_lemma(head_token, tokens):
    """
    True when head_token has an obl child that is itself a temporal-frame
    noun ("saat"/"waktu"/"ketika"/"kala") with its own case marker -- i.e.
    a genuine "pada saat X" / "di kala X" temporal framing exists on this
    verb.
    """
    return any(
        child["head"] == head_token["id"]
        and child["deprel"] == "obl"
        and child["lemma"].lower() in TEMPORAL_ADJUNCT_LEMMAS
        and get_case_marker(child, tokens) is not None
        for child in tokens
    )


def find_coordinated_verb_relations(relation_token, tokens):

    siblings = [
        child for child in tokens
        if child["head"] == relation_token["id"]
        and child["deprel"] in ("conj", "advcl")
        and child["upos"] == "VERB"
    ]

    result = []

    # AUDIT D13 (Iteration 2): "sesajen DIHATURKAN pada saat abu jenazah
    # DIHANYUTKAN ke samudera" (S1187) / "di kala jenazah DIANGKUT ke
    # setra ..., lancingan kajang DIJUNJUNG ..." (S1603) -- the temporal
    # clause's own verb ("dihanyutkan"/"diangkut") gets attached as an
    # advcl SIBLING of the main verb, with its real subject mis-attached
    # to the temporal noun ("saat abu jenazah" / "kala jenazah") instead
    # of to the verb itself -- so has_own_subject below reads False even
    # though it isn't really a subject-less coordinate action. Two
    # shapes seen: the temporal oblique sits on the OUTER relation_token
    # (S1187) or on the candidate sibling itself (S1603) -- check both.
    outer_has_temporal_frame = _obl_has_temporal_lemma(relation_token, tokens)

    for sibling in sorted(siblings, key=lambda x: x["id"]):

        if sibling["deprel"] == "advcl" and _advcl_has_subordinate_mark(sibling, tokens):
            continue

        if sibling["deprel"] == "advcl" and (
            outer_has_temporal_frame or _obl_has_temporal_lemma(sibling, tokens)
        ):
            continue

        has_own_subject = any(
            grandchild["head"] == sibling["id"]
            and grandchild["deprel"] in ("nsubj", "nsubj:pass")
            for grandchild in tokens
        )

        if has_own_subject:
            continue

        if is_negated(sibling, tokens):
            continue

        result.append(sibling)

    return result'''
    src = apply(src, old_find_coord, new_find_coord, "D13: temporal-frame guard in find_coordinated_verb_relations")

    # ------------------------------------------------------------------
    # 3. D7 (was N3): narrow, safe benefactive-passive swap for
    #    dihaturkan/disuguhi-type verbs with a bare (no case marker)
    #    object -- the recipient is in subject position, the theme is
    #    the object; swap so the theme becomes the subject. Deliberately
    #    scoped to a two-lemma allowlist (not taruh/beri/turun/buat --
    #    those lemmas collide with plain, correctly-subject-as-patient
    #    passives on the exact same root, too risky to blanket-swap
    #    without also plumbing subject_label for a real disambiguation
    #    signal -- deferred, see runbook changelog).
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''    if lemma == "termasuk":
        return "_SWAP_JENIS_DARI"''',
        '''    if lemma == "termasuk":
        return "_SWAP_JENIS_DARI"

    # AUDIT D7 (Iteration 2, was N3): "sulinggih ... DIHATURKAN santapan
    # istimewa" backwards implies the priest is being offered up -- the
    # recipient ("sulinggih...") got promoted to subject by the -kan
    # benefactive/applicative voice, while the bare (case-marker-free)
    # object is the actual THEME being given. Scoped to a curated
    # two-lemma set (hatur/suguh) whose surface always carries this
    # sense in this corpus; sentinel mirrors _SWAP_JENIS_DARI above.
    if (
        voice == "passive"
        and case is None
        and lemma in ("hatur", "suguh")
        and surface.endswith(("kan", "i"))
    ):
        return "_SWAP_DIPERSEMBAHKAN_KEPADA"''',
        "D7: benefactive swap sentinel in derive_raw_relation_label",
    )

    # ------------------------------------------------------------------
    # 4. D8 (was N4): "diisi (dengan) X" only means "contains X" when X
    #    is genuinely the CONTENTS (no case marker, or "dengan") -- a
    #    locative "di <body-part>, diisi sebuah kawangen" has the body
    #    part as WHERE the kawangen goes, not what it's filled with.
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''    # AUDIT S15: "berisi / diisi (dengan) X" = contains X, never MEMILIKI.
    if lemma == "isi" or surface.startswith("berisi") or surface.startswith("diisi"):
        return "DIISI_DENGAN" if voice == "passive" else "BERISI"''',
        '''    # AUDIT S15: "berisi / diisi (dengan) X" = contains X, never MEMILIKI.
    # AUDIT D8 (Iteration 2): but only when X is genuinely the contents --
    # "di hulu hati, diisi sebuah kawangen" (S3747/S3749/S3753) has the
    # body part as a LOCATIVE oblique (WHERE the kawangen is placed), not
    # what it's filled with; that shape routes to DILETAKKAN_DI instead.
    # The kawangen's own contents ("yang berisi 9 biji uang kepeng...")
    # are picked up separately as a BERISI relation via the new
    # find_subject_clause_relations() branch below.
    if lemma == "isi" or surface.startswith("berisi") or surface.startswith("diisi"):
        if case in NOUN_LOC_MARKERS:
            return "DILETAKKAN_DI"
        return "DIISI_DENGAN" if voice == "passive" else "BERISI"''',
        "D8: DIISI_DI locative guard in derive_raw_relation_label",
    )

    # ------------------------------------------------------------------
    # 5. D1: GENERIC_CATEGORY_NOUNS -- broaden beyond ADALAH/BERPERAN_SEBAGAI
    #    to the MEMILIKI/MEMPEROLEH/TERDIRI_DARI-headed generic nouns the
    #    audit found (peran, makna, arti, nilai, tarif, symbol/simbol...).
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''    # AUDIT N1 (Iteration 1 additions): "X ADALAH pengabenan/penegasan/..."
    # showed the identical bare-noun-loses-its-clause pattern.
    "pengabenan", "penegasan", "hubungan", "fungsi", "pertanda", "ciri",
}''',
        '''    # AUDIT N1 (Iteration 1 additions): "X ADALAH pengabenan/penegasan/..."
    # showed the identical bare-noun-loses-its-clause pattern.
    "pengabenan", "penegasan", "hubungan", "fungsi", "pertanda", "ciri",
    # AUDIT D1 (Iteration 2): the same pattern recurs under MEMILIKI/
    # MEMPEROLEH/TERDIRI_DARI/BERARTI, not just ADALAH/BERPERAN_SEBAGAI --
    # "ngaben MEMILIKI peran ganda yang..." (S32), "mapegat MEMILIKI makna
    # krusial untuk..." (S61), "tirtha MEMILIKI fungsi SEBAGAI symbol dari
    # ..." (S4074, English-spelled "symbol"), "X MEMILIKI hubungan erat
    # DENGAN itihasa" (S4087).
    "peran", "makna", "arti", "nilai", "tarif", "simbol", "symbol",
    "kedudukan", "keinginan", "alasan", "syarat", "kondisi", "tanda",
}''',
        "D1: broaden GENERIC_CATEGORY_NOUNS",
    )

    # ------------------------------------------------------------------
    # 6. D1: a "sebagai/selaku X" nmod child of the object head ("fungsi
    #    SEBAGAI sarana", "peran SELAKU X") is a predicate-nominal
    #    complement -- any acl/purpose-oblique clause hanging off THAT
    #    child ("sarana UNTUK menetapkan...") carries the head's real
    #    defining content, but _clause_children() never looked past one
    #    hop. New helper + widened _clause_children().
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''def _clause_children(token, tokens):
    base = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]
    base += _purpose_oblique_children(token, tokens)
    return sorted(base, key=lambda x: x["id"])''',
        '''_PREDICATE_COMPLEMENT_CASE_MARKS = {"sebagai", "selaku"}


def _predicate_complement_child(token, tokens):
    """
    AUDIT D1 (Iteration 2): a "sebagai/selaku X" nmod child of a generic
    head noun ("fungsi SEBAGAI sarana", S4106/S4111/S4128) is a
    predicate-nominal complement, not a mere modifier -- it IS the
    generic noun's real content. Returns that child when there's exactly
    one, so its own defining clauses can be pulled in too.
    """
    candidates = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] == "nmod"
        and get_case_marker(child, tokens) in _PREDICATE_COMPLEMENT_CASE_MARKS
    ]
    return candidates[0] if len(candidates) == 1 else None


def _clause_children(token, tokens):
    base = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]
    base += _purpose_oblique_children(token, tokens)
    # AUDIT D1 (Iteration 2): descend one hop into a "sebagai/selaku X"
    # predicate-nominal complement for ITS OWN defining clause too --
    # "MEMILIKI fungsi SEBAGAI sarana UNTUK menetapkan..." (S4106) only
    # attaches the untuk-clause to "sarana", never to "fungsi" itself, so
    # the old single-hop _clause_children(fungsi) found nothing at all.
    complement = _predicate_complement_child(token, tokens)
    if complement is not None:
        base += [
            c for c in tokens
            if c["head"] == complement["id"]
            and c["deprel"] in ("acl", "acl:relcl", "appos")
        ]
        base += _purpose_oblique_children(complement, tokens)
    return sorted(base, key=lambda x: x["id"])''',
        "D1: predicate-complement descent in _clause_children",
    )

    # ------------------------------------------------------------------
    # 7. D1: expand_object_with_clauses() had its own INLINE duplicate of
    #    the acl/acl:relcl/appos + purpose-oblique scan instead of calling
    #    _clause_children() -- so the predicate-complement descent just
    #    added above never reached the actual rendered object text (only
    #    the sub-relation-attempt path). Route it through the shared
    #    helper so both paths benefit.
    # ------------------------------------------------------------------
    src = apply(
        src,
        '''    base_phrase = expand_phrase(token, tokens)

    clause_children = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]
    # AUDIT N1 (Iteration 1): also attach a purpose/goal oblique directly on
    # the head -- see _purpose_oblique_children() below.
    clause_children += _purpose_oblique_children(token, tokens)

    clause_children = sorted(clause_children, key=lambda x: x["id"])

    has_clause = bool(clause_children)''',
        '''    base_phrase = expand_phrase(token, tokens)

    # AUDIT D1 (Iteration 2): was an inline duplicate of acl/acl:relcl/
    # appos + purpose-oblique scanning; now routed through the shared
    # _clause_children() so the predicate-complement descent (a
    # "sebagai/selaku X" child's own defining clause) applies here too,
    # not just in decompose_object()'s sub-relation-attempt path.
    clause_children = _clause_children(token, tokens)

    has_clause = bool(clause_children)''',
        "D1: expand_object_with_clauses uses shared _clause_children",
    )

    # ------------------------------------------------------------------
    # 8. D2: extend N1e's verb-level fallback in _emit_relations_for_verb
    #    -- gate on the object's OWN head lemma (not the fully-resolved
    #    phrase string, which may already include unrelated appended
    #    text) and drop the "not object_has_clause" requirement so a
    #    sibling sehingga-clause on the verb still gets appended even
    #    when the object side already found ITS OWN defining clause
    #    (S4074: both the "dari pikiran..." nmod AND the "sehingga
    #    mengalami..." sibling advcl carry real content).
    # ------------------------------------------------------------------
    old_n1e = '''            # AUDIT N1e (Iteration 1): bare generic-category object with no
            # clause found on ITS side -- check the governing verb for a
            # purpose oblique/xcomp of its own before giving up.
            if (
                not object_has_clause
                and not sub_relations
                and object_phrase.strip().lower() in GENERIC_CATEGORY_NOUNS
            ):
                verb_purpose = [
                    c for c in _purpose_oblique_children(verb_token, tokens)
                    + [t for t in tokens
                       if t["head"] == verb_token["id"] and t["deprel"] == "xcomp"]
                    if c["id"] != obj_tok["id"]
                ]
                if verb_purpose:
                    extra = " ".join(
                        render_subtree_text(c, tokens)
                        for c in sorted(verb_purpose, key=lambda x: x["id"])
                    )
                    object_phrase = f"{object_phrase} {extra}"
                    object_has_clause = True'''
    new_n1e = '''            # AUDIT N1e (Iteration 1)/D2 (Iteration 2): a defining purpose/
            # consequence clause sometimes hangs off the GOVERNING VERB as a
            # sibling of the object rather than off the object noun itself
            # ("tirtha ... selaku sarana UNTUK menetapkan..." S1206;
            # "berfungsi sebagai symbol ..., SEHINGGA roh ... mengalami
            # kegoncangan" S4074). Gate on the object's OWN head lemma
            # (obj_tok, not the fully-decomposed object_phrase string,
            # which may already carry unrelated appended text) and don't
            # require object_has_clause to still be False -- the object
            # side and the verb side can each carry independent real
            # content for the same generic-noun object.
            if (
                not sub_relations
                and obj_tok["lemma"].lower() in GENERIC_CATEGORY_NOUNS
            ):
                verb_purpose = [
                    c for c in _purpose_oblique_children(verb_token, tokens)
                    + [t for t in tokens
                       if t["head"] == verb_token["id"] and t["deprel"] == "xcomp"]
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
    src = apply(src, old_n1e, new_n1e, "D2: relax N1e verb-level fallback gate")

    with open("audit_tooling/iteration_2/_stage1_source.txt", "w", encoding="utf-8") as f:
        f.write(src)

    print(f"\nStage 1 complete. {len(src) - original_len:+d} chars.")
    return nb, cell, src


if __name__ == "__main__":
    main()

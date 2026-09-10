"""
Iteration 3, Stage 1: cheap, independent fixes (see the approved plan at
C:\\Users\\ASUS TUF\\.claude\\plans\\i-want-you-to-frolicking-bachman.md).

1a. berwujud/melambangkan lemma confusion (S1688, S2180).
1b. LAINNYA vacuous label -- final-pass drop.
1c. sequence/temporal case marker (SETELAH/MENJELANG) now suffixes the real
    predicate instead of replacing it outright (S1747, S2028, S2166, S2642).
1d. "termasuk" swap narrowed to fire only when the subject carries a
    totality quantifier (S2748/S2794 still swap; S3237 no longer does).
1e. FUNCTION_WORD_OBJECTS filter exempts manual_override-sourced relations
    (root cause of S3758's logam-campuran override silently vanishing).

Same idempotent, anchor-guarded, string-replace-into-cell-51-source pattern
as every prior iteration's patch scripts.
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

    # ---- 1c + helpers for 1d: wrapper/core split + termasuk-quantifier helpers ----
    src = apply(
        src,
        '''def _role_marker(object_token, tokens):
    """'sebagai' / 'selaku' governing the object -- Stanza tags it 'case'
    sometimes and 'mark' other times."""
    if object_token is None:
        return None
    for child in tokens:
        if child["head"] == object_token["id"] and child["deprel"] in ("case", "mark") \\
           and (child["lemma"].lower() in ROLE_MARKERS or child["text"].lower() in ROLE_MARKERS):
            return child["text"].lower()
    return None


def verb_voice(verb_token):''',
        '''def _role_marker(object_token, tokens):
    """'sebagai' / 'selaku' governing the object -- Stanza tags it 'case'
    sometimes and 'mark' other times."""
    if object_token is None:
        return None
    for child in tokens:
        if child["head"] == object_token["id"] and child["deprel"] in ("case", "mark") \\
           and (child["lemma"].lower() in ROLE_MARKERS or child["text"].lower() in ROLE_MARKERS):
            return child["text"].lower()
    return None


_TOTALITY_QUANTIFIER_LEMMAS = {"semua", "segala", "setiap", "seluruh"}


def _find_verb_subject(verb_token, tokens):
    """verb_token's own nsubj/nsubj:pass child if it has one; otherwise (a
    subject-less advcl sharing the matrix clause's subject, e.g. "semua
    sekah ... termasuk sangge" where 'termasuk' hangs as an advcl off the
    real root verb) fall back to its head's nsubj/nsubj:pass. AUDIT S3237,
    Iteration 3."""
    own = next(
        (t for t in tokens if t["head"] == verb_token["id"]
         and t["deprel"] in ("nsubj", "nsubj:pass")),
        None,
    )
    if own is not None:
        return own
    head_id = verb_token.get("head")
    if head_id in (None, 0):
        return None
    return next(
        (t for t in tokens if t["head"] == head_id
         and t["deprel"] in ("nsubj", "nsubj:pass")),
        None,
    )


def _subject_has_totality_quantifier(verb_token, tokens):
    """AUDIT S3237 (Iteration 3): does verb_token's subject (or a det/
    advmod/nummod child of it) carry a totality quantifier (semua/segala/
    setiap/seluruh)? Distinguishes the membership sense of 'termasuk'
    ("semua sekah termasuk sangge") from its plain containment sense
    ("lekesan termasuk tembakau"), which the earlier unconditional swap
    reversed."""
    subj = _find_verb_subject(verb_token, tokens)
    if subj is None:
        return False
    if subj["lemma"].lower() in _TOTALITY_QUANTIFIER_LEMMAS:
        return True
    return any(
        child["head"] == subj["id"]
        and child["deprel"] in ("det", "advmod", "nummod")
        and child["lemma"].lower() in _TOTALITY_QUANTIFIER_LEMMAS
        for child in tokens
    )


def verb_voice(verb_token):''',
        "1d helpers: _find_verb_subject / _subject_has_totality_quantifier inserted",
    )

    # ---- 1c: wrapper/core split for derive_raw_relation_label ----
    src = apply(
        src,
        '''def derive_raw_relation_label(relation_token, object_token, tokens, object_flags=frozenset()):
    """Marker-first, voice-aware. Returns a FINAL natural UPPER_SNAKE predicate.
    Preserves every earlier lemma-collision fix (meninggal/tinggal, tuju 3-way,
    terdiri/berdiri, terbuat/membuat, ada locative/possessive, terima
    active/passive, iring, sequence-marker override)."""

    lemma    = relation_token["lemma"].lower()
    surface  = relation_token["text"].lower()
    voice    = verb_voice(relation_token)
    case     = get_case_marker(object_token, tokens) if object_token is not None else None
    obj_lem  = object_token["lemma"].lower() if object_token is not None else ""
    obj_upos = object_token["upos"] if object_token is not None else ""
    role     = _role_marker(object_token, tokens)

    # 1. similative retarget (FIX #25)
    if "similative_object" in object_flags:
        return "DIPERLAKUKAN_SEPERTI"

    # 2. sequence / comparison marker overrides the verb entirely
    if case in SEQUENCE_CASE_MARKERS:
        return SEQUENCE_CASE_MARKERS[case].upper()
    if case in TEMPORAL_MARKERS_EXTRA:
        return "MENJELANG"

    # 3. FIX #15 -- meninggal (die); lemma is 'tinggal'
''',
        '''def derive_raw_relation_label(relation_token, object_token, tokens, object_flags=frozenset()):
    """Thin wrapper (AUDIT /121, Iteration 3): a sequence/temporal case
    marker (sebelum/sesudah/setelah/selain/menjelang) used to REPLACE the
    whole predicate outright, discarding the verb's real action -- "sekah
    kangsen dibongkar SETELAH pamralina" shipped as bare SETELAH, losing
    "dibongkar" (S1747/S2028/S2166/S2642). None of these markers overlap
    any other case-marker set checked in the core cascade below, so it's
    safe to compute the base predicate as if the marker were absent, then
    suffix it -- "DIBONGKAR_SETELAH", not bare "SETELAH". Sentinel labels
    (leading underscore, e.g. "_SWAP_JENIS_DARI") pass through untouched."""
    case = get_case_marker(object_token, tokens) if object_token is not None else None
    _seq_suffix = None
    if case in SEQUENCE_CASE_MARKERS:
        _seq_suffix = SEQUENCE_CASE_MARKERS[case].upper()
    elif case in TEMPORAL_MARKERS_EXTRA:
        _seq_suffix = "MENJELANG"
    _base = _derive_raw_relation_label_core(relation_token, object_token, tokens, object_flags)
    if _seq_suffix is None or not _base or _base.startswith("_"):
        return _base
    if _base == "LAINNYA":
        return _seq_suffix
    return f"{_base}_{_seq_suffix}"


def _derive_raw_relation_label_core(relation_token, object_token, tokens, object_flags=frozenset()):
    """Marker-first, voice-aware. Returns a FINAL natural UPPER_SNAKE predicate.
    Preserves every earlier lemma-collision fix (meninggal/tinggal, tuju 3-way,
    terdiri/berdiri, terbuat/membuat, ada locative/possessive, terima
    active/passive, iring). Called only from the thin `derive_raw_relation_label`
    wrapper above, which now owns the sequence/temporal-marker suffix logic
    (AUDIT /121, Iteration 3) -- step 2 below no longer returns early on it."""

    lemma    = relation_token["lemma"].lower()
    surface  = relation_token["text"].lower()
    voice    = verb_voice(relation_token)
    case     = get_case_marker(object_token, tokens) if object_token is not None else None
    obj_lem  = object_token["lemma"].lower() if object_token is not None else ""
    obj_upos = object_token["upos"] if object_token is not None else ""
    role     = _role_marker(object_token, tokens)

    # 1. similative retarget (FIX #25)
    if "similative_object" in object_flags:
        return "DIPERLAKUKAN_SEPERTI"

    # 2. (sequence/temporal marker handling now lives in the wrapper above --
    # `case` here naturally never matches any other marker set checked in
    # steps 5-12 when it's sebelum/sesudah/setelah/selain/menjelang, so
    # falling through is safe and reaches the same base-predicate steps
    # 14/15/16 would otherwise have produced.)

    # 3. FIX #15 -- meninggal (die); lemma is 'tinggal'
''',
        "1c: derive_raw_relation_label wrapper/core split for sequence-marker suffixing",
    )

    # ---- 1d: narrow the termasuk swap ----
    src = apply(
        src,
        '''    # AUDIT N6/S11 (Iteration 1): "X termasuk Y" means Y is a MEMBER/kind of
    # X ("semua sekah termasuk sangge" -> sangge is a kind of sekah) -- the
    # opposite direction from the other CLASSIFY_LEMMAS ("golong"/
    # "kategori"/"kelompok"), whose subject->object direction already reads
    # correctly. Sentinel tells _emit_relations_for_verb() to swap
    # subject/object when building the relation record.
    if lemma == "termasuk":
        return "_SWAP_JENIS_DARI"''',
        '''    # AUDIT N6/S11 (Iteration 1, narrowed AUDIT S3237/Iteration 3): "X
    # termasuk Y" means Y is a MEMBER/kind of X only when X carries an
    # explicit totality quantifier ("semua sekah termasuk sangge" -> sangge
    # is a kind of sekah) -- the opposite direction from the other
    # CLASSIFY_LEMMAS ("golong"/"kategori"/"kelompok"), whose subject->object
    # direction already reads correctly. Without a quantifier, "termasuk" is
    # in its plain containment sense instead ("lekesan termasuk tembakau" =
    # lekesan CONTAINS tobacco, not "tobacco is a kind of lekesan") -- the
    # earlier unconditional swap reversed this (S3237). Sentinel (when it
    # fires) tells _emit_relations_for_verb() to swap subject/object when
    # building the relation record.
    if lemma == "termasuk":
        if _subject_has_totality_quantifier(relation_token, tokens):
            return "_SWAP_JENIS_DARI"
        return "BERISI"''',
        "1d: narrow termasuk swap to require a totality quantifier on the subject",
    )

    # ---- 1b + 1e: LAINNYA final-pass drop + manual_override exemption on FUNCTION_WORD_OBJECTS ----
    src = apply(
        src,
        '''for relation in relations:
    raw = relation["relation"]
    # bucketed labels come from the table (already all-caps); anything
    # not in the table is an un-grouped raw predicate -- upper-case it
    # too so EVERY relation label in the output is uniformly all-caps.
    relation["relation"] = RELATION_TAXONOMY.get(raw, raw.upper())

# ==========================================
# 13.10c. DROP TRIPLES WITH A BARE FUNCTION-WORD OBJECT
# ==========================================

FUNCTION_WORD_OBJECTS = SUB_OBJECT_STOPWORDS | {
    "tadi", "situ", "sini", "sana", "demikian", "semua", "mesti", "hal", "cara",
    "nanti", "kaki", "kepala", "arti", "makna", "istilah", "maksud", "sesuatu",
    "semacam", "begitu", "sendiri", "berikut", "misal", "misalnya", "keadaan",
    "posisi", "kenyataan", "sesuatunya",
    "secukupnya", "khusuknya", "seperlunya", "seadanya", "sepenuhnya",
    "semestinya", "selengkapnya", "sewajarnya", "sebaik-baiknya", "seikhlasnya",
    "senantiasa", "sedemikian",
    "atas", "bawah", "dalam", "luar", "depan", "belakang", "tengah", "samping",
    "luanan", "teben", "hulu", "hilir", "kiri", "kanan", "muka",
}
relations = [
    relation for relation in relations
    if relation["object"].strip().lower() not in FUNCTION_WORD_OBJECTS
]''',
        '''for relation in relations:
    raw = relation["relation"]
    # bucketed labels come from the table (already all-caps); anything
    # not in the table is an un-grouped raw predicate -- upper-case it
    # too so EVERY relation label in the output is uniformly all-caps.
    relation["relation"] = RELATION_TAXONOMY.get(raw, raw.upper())

# AUDIT (Iteration 3): "LAINNYA" is voiced_surface_label()'s own last-resort
# marker for "this verb carries no relation sense on its own" (13.3d) -- it
# was shipping as a literal, useless relation label in the output (S1523,
# S1629, S1850, S2269, S2340, S2810, S3295, S3330, S3651, S3742...). Same
# philosophy as VERB_STUB_OBJECTS below: drop rather than guess at a better
# label with no reliable signal.
relations = [relation for relation in relations if relation["relation"] != "LAINNYA"]

# ==========================================
# 13.10c. DROP TRIPLES WITH A BARE FUNCTION-WORD OBJECT
# ==========================================

FUNCTION_WORD_OBJECTS = SUB_OBJECT_STOPWORDS | {
    "tadi", "situ", "sini", "sana", "demikian", "semua", "mesti", "hal", "cara",
    "nanti", "kaki", "kepala", "arti", "makna", "istilah", "maksud", "sesuatu",
    "semacam", "begitu", "sendiri", "berikut", "misal", "misalnya", "keadaan",
    "posisi", "kenyataan", "sesuatunya",
    "secukupnya", "khusuknya", "seperlunya", "seadanya", "sepenuhnya",
    "semestinya", "selengkapnya", "sewajarnya", "sebaik-baiknya", "seikhlasnya",
    "senantiasa", "sedemikian",
    "atas", "bawah", "dalam", "luar", "depan", "belakang", "tengah", "samping",
    "luanan", "teben", "hulu", "hilir", "kiri", "kanan", "muka",
}
# AUDIT (Iteration 3, S3758): this filter is meant to catch bare-fragment
# objects from AUTO-extraction ("X DILETAKKAN_DI atas") -- it was also
# silently dropping deliberately-curated manual_override rows whose object
# happens to collide with one of these words for real (e.g. "logam campuran
# BERADA_DI tengah" -- "tengah" is in this list). Manual overrides are
# hand-verified, not raw fragments -- exempt them.
relations = [
    relation for relation in relations
    if relation.get("source") == "manual_override"
    or relation["object"].strip().lower() not in FUNCTION_WORD_OBJECTS
]''',
        "1b + 1e: LAINNYA final-pass drop, and manual_override exemption on FUNCTION_WORD_OBJECTS",
    )

    # ---- 1a: berwujud/melambangkan lemma fix ----
    src = apply(
        src,
        '''        if lemma in ("wakil", "lambang", "wujud", "representasi", "serupa", "cermin"):
            return "MELAMBANGKAN"''',
        '''        # AUDIT (Iteration 3): "wujud" is berwujud's lemma ("takes the
        # physical form of") -- distinct from melambangkan ("symbolizes").
        # These were being conflated (S1688, S2180); dropped from this set
        # so berwujud falls through to voiced_surface_label() below, which
        # already renders it correctly as BERWUJUD.
        if lemma in ("wakil", "lambang", "representasi", "serupa", "cermin"):
            return "MELAMBANGKAN"''',
        "1a: remove 'wujud' from the MELAMBANGKAN lemma set",
    )

    try:
        compile(src, "<cell51-patched-stage1>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    lines = src.splitlines(keepends=True)
    cell["source"] = lines
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"\nStage 1 complete. {len(src) - original_len:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

"""Iteration-1 systemic fixes to cell 51 (relation extraction) of
Knowledge Processing.ipynb, per relation_audit_report.md section 3 (N1-N12)
and section 2 (Iteration 0 scorecard).

Fixes applied this pass:
  N1  copula/generic-noun clause-stripping (#1 open defect) -- widen what
      counts as "the defining clause" (purpose obliques, not just acl/
      appos), and check the resolved HEAD TOKEN's lemma instead of the
      whole surface phrase against GENERIC_CATEGORY_NOUNS (so "satu tahap",
      "upacara keagamaan", "beberapa jenis" etc. aren't blocked by a
      quantifier/modifier riding along in the string). Also widens
      GENERIC_CATEGORY_NOUNS itself with nouns evidenced in the audit.
  N10 get_conjuncts() made transitive (3+-item coordinate lists chained
      B->A, C->B rather than every member attaching to A were silently
      losing every member past the second).
  S13 (widened) attribution-adjunct filter now matches on OBJECT CONTENT
      ("dalam lontar X", "sebagaimana disinggung/diuraikan...", "di mata
      X") instead of being gated on the relation label already being
      literally "MENURUT" -- the same adjunct was leaking out under
      DIKENAL_SEBAGAI/TERTULIS/DISINGGUNG_DI/DIURAIKAN/DINILAI_DI/etc.
  N6  "X termasuk Y" direction reversed (Y is the member/kind of X, not
      the other way around) -- sentinel handshake between
      derive_raw_relation_label() and _emit_relations_for_verb().
  N11 MANUAL_RELATION_OVERRIDES: the Panca Maha Bhuta closing verse
      (S4300/S4301/S4303/S4304/S4305, "sangkaning ... mulih (ring/maring)
      ..." split on "sangkaning" as if it were a name) + S133 predicate
      formatting ("tidak menjamin" -> "tidak_menjamin", matching the
      corpus's UPPER_SNAKE_CASE convention once uppercased).

Deferred to a later iteration (see relation_audit_report.md section 4):
  N2/N3 (needs subject_label plumbed into derive_raw_relation_label),
  N4 (DIISI_DI <body-part> two-triple split -- two separate extraction
  paths), N5/N7/N8/N9 (span-hygiene batch), and the still-open Balinese
  offering-list retag (v1 S5, needs a UPOS-level LEMMA_CORRECTIONS pass).

Idempotency: each replacement is guarded by an 'ALREADY PATCHED' check on a
sentinel string (same pattern as iteration_0/patch_nb_relations.py).
"""
import json, sys

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
cell = nb["cells"][51]
src = "".join(cell["source"])
orig = src

def repl(old, new, tag):
    global src
    if new.strip() in src:
        print(f"  [skip] {tag} (already patched)")
        return
    if old not in src:
        print(f"  [FAIL] {tag}: anchor not found")
        sys.exit(1)
    if src.count(old) != 1:
        print(f"  [FAIL] {tag}: anchor not unique ({src.count(old)})")
        sys.exit(1)
    src = src.replace(old, new, 1)
    print(f"  [ok]   {tag}")

# ---------------------------------------------------------------------------
# N6: sentinel in derive_raw_relation_label, right after the S15 berisi/diisi
# block (same insertion style as Iteration 0's S2/S8/S15 additions).
# ---------------------------------------------------------------------------
repl(
    '''    # AUDIT S15: "berisi / diisi (dengan) X" = contains X, never MEMILIKI.
    if lemma == "isi" or surface.startswith("berisi") or surface.startswith("diisi"):
        return "DIISI_DENGAN" if voice == "passive" else "BERISI"

    # 5. according-to / basis''',
    '''    # AUDIT S15: "berisi / diisi (dengan) X" = contains X, never MEMILIKI.
    if lemma == "isi" or surface.startswith("berisi") or surface.startswith("diisi"):
        return "DIISI_DENGAN" if voice == "passive" else "BERISI"

    # AUDIT N6/S11 (Iteration 1): "X termasuk Y" means Y is a MEMBER/kind of
    # X ("semua sekah termasuk sangge" -> sangge is a kind of sekah) -- the
    # opposite direction from the other CLASSIFY_LEMMAS ("golong"/
    # "kategori"/"kelompok"), whose subject->object direction already reads
    # correctly. Sentinel tells _emit_relations_for_verb() to swap
    # subject/object when building the relation record.
    if lemma == "termasuk":
        return "_SWAP_JENIS_DARI"

    # 5. according-to / basis''',
    "N6 termasuk sentinel in derive_raw_relation_label",
)

# ---------------------------------------------------------------------------
# N6: handle the sentinel in _emit_relations_for_verb (swap subject/object).
# ---------------------------------------------------------------------------
repl(
    '''    for object_token, object_flags in object_candidates:

        raw_label = derive_raw_relation_label(verb_token, object_token, tokens, object_flags)

        all_object_tokens = (
            [object_token]
            + get_conjuncts(object_token, tokens)
        )''',
    '''    for object_token, object_flags in object_candidates:

        raw_label = derive_raw_relation_label(verb_token, object_token, tokens, object_flags)

        # AUDIT N6/S11 (Iteration 1): see the sentinel comment in
        # derive_raw_relation_label().
        _swap_termasuk = (raw_label == "_SWAP_JENIS_DARI")
        if _swap_termasuk:
            raw_label = "JENIS_DARI"

        all_object_tokens = (
            [object_token]
            + get_conjuncts(object_token, tokens)
        )''',
    "N6 sentinel detection in _emit_relations_for_verb",
)

repl(
    '''            if subject_phrase.lower().strip() == object_phrase.lower().strip():
                continue

            relation_record = {
                "sentence_id": sentence_id,
                "subject": subject_phrase,
                "subject_label": subject_label,
                "relation": raw_label,
                "object": object_phrase,
                "object_label": None,
                # FIX #26: acl/acl:relcl/appos-expanded object -> a description,
                # not an entity name. classify_object_kind() -> LITERAL.
                "object_is_clausal": object_has_clause,
                "source": "dependency_rule",
            }''',
    '''            if subject_phrase.lower().strip() == object_phrase.lower().strip():
                continue

            # AUDIT N6/S11 (Iteration 1): swap subject/object roles for the
            # "X termasuk Y" case flagged above.
            final_subject, final_subject_label, final_object = (
                (object_phrase, None, subject_phrase)
                if _swap_termasuk
                else (subject_phrase, subject_label, object_phrase)
            )

            relation_record = {
                "sentence_id": sentence_id,
                "subject": final_subject,
                "subject_label": final_subject_label,
                "relation": raw_label,
                "object": final_object,
                "object_label": None,
                # FIX #26: acl/acl:relcl/appos-expanded object -> a description,
                # not an entity name. classify_object_kind() -> LITERAL.
                "object_is_clausal": object_has_clause,
                "source": "dependency_rule",
            }''',
    "N6 subject/object swap at relation_record construction",
)

# ---------------------------------------------------------------------------
# N1e: verb-level purpose clause. Some copula-like verbs ("selaku"/"sebagai"
# -- Stanza mistags these as VERB, see the "3b." note in
# derive_raw_relation_label) carry their OWN purpose xcomp as a SIBLING of
# the object noun ("tirtha selaku sarana UNTUK menetapkan..." -- "sarana"
# is obj, "menetapkan" is xcomp, both children of "selaku"), not as a child
# of the object noun itself, so decompose_object() (N1b/c/d above) can't
# see it -- it only ever receives the object head. Caught one level up,
# right after resolve_object() in _emit_relations_for_verb().
# ---------------------------------------------------------------------------
repl(
    '''            object_phrase, object_has_clause, sub_relations = resolve_object(
                obj_tok, tokens, subject_phrase
            )

            if object_phrase.strip().lower() in LIGHT_ANCHOR_HEADS and sub_relations:''',
    '''            object_phrase, object_has_clause, sub_relations = resolve_object(
                obj_tok, tokens, subject_phrase
            )

            # AUDIT N1e (Iteration 1): bare generic-category object with no
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
                    object_has_clause = True

            if object_phrase.strip().lower() in LIGHT_ANCHOR_HEADS and sub_relations:''',
    "N1e verb-level purpose clause in _emit_relations_for_verb",
)

# ---------------------------------------------------------------------------
# N10: get_conjuncts() made transitive.
# ---------------------------------------------------------------------------
repl(
    '''def get_conjuncts(token, tokens):
    """
    Cari token lain yang di-koordinasikan
    dengan token ini lewat kata sambung
    "dan"/"atau" (deprel == "conj").

    Contoh: "kasa, karo, dan katiga" ->
    "karo" dan "katiga" adalah conj dari "kasa".

    Dipakai supaya kalimat definisi dengan
    daftar (list) tidak kehilangan item
    ke-2, ke-3, dst -- hanya mengambil
    item pertama saja.
    """

    conjuncts = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] == "conj"
    ]

    return sorted(
        conjuncts,
        key=lambda x: x["id"]
    )''',
    '''def get_conjuncts(token, tokens, _visited=None):
    """
    Cari token lain yang di-koordinasikan
    dengan token ini lewat kata sambung
    "dan"/"atau" (deprel == "conj").

    Contoh: "kasa, karo, dan katiga" ->
    "karo" dan "katiga" adalah conj dari
    "kasa".

    AUDIT N10 (Iteration 1): a 3+-item coordinate list sometimes chains
    conj B->A, C->B rather than every member attaching directly to A -- the
    original single-hop version silently dropped every member past the
    second ("sasih kasa, karo, dan katiga" kept only "karo"). Walked
    transitively now, with a visited-set guard against any parse cycle.

    Dipakai supaya kalimat definisi dengan
    daftar (list) tidak kehilangan item
    ke-2, ke-3, dst -- hanya mengambil
    item pertama saja.
    """

    if _visited is None:
        _visited = {token["id"]}

    direct = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] == "conj"
        and child["id"] not in _visited
    ]

    all_conjuncts = []
    for child in direct:
        _visited.add(child["id"])
        all_conjuncts.append(child)
        all_conjuncts.extend(get_conjuncts(child, tokens, _visited))

    seen_ids = set()
    unique = []
    for c in all_conjuncts:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique.append(c)

    return sorted(unique, key=lambda x: x["id"])''',
    "N10 get_conjuncts transitive walk",
)

# ---------------------------------------------------------------------------
# N1a: widen GENERIC_CATEGORY_NOUNS with nouns evidenced by the audit.
# ---------------------------------------------------------------------------
repl(
    '''    "istilah", "sebutan", "nama", "kata",
    "doa", "mantra", "aturan", "ketentuan", "pantangan",
}''',
    '''    "istilah", "sebutan", "nama", "kata",
    "doa", "mantra", "aturan", "ketentuan", "pantangan",
    # AUDIT N1 (Iteration 1 additions): "X ADALAH pengabenan/penegasan/..."
    # showed the identical bare-noun-loses-its-clause pattern.
    "pengabenan", "penegasan", "hubungan", "fungsi", "pertanda", "ciri",
}''',
    "N1a GENERIC_CATEGORY_NOUNS additions",
)

# ---------------------------------------------------------------------------
# N1b: purpose-oblique helper, inserted right before _clause_children() (its
# first consumer here; expand_object_with_clauses() above it can still call
# it fine since Python only needs the name to exist by call time).
# ---------------------------------------------------------------------------
repl(
    '''def _clause_children(token, tokens):
    return sorted(
        (
            child for child in tokens
            if child["head"] == token["id"]
            and child["deprel"] in ("acl", "acl:relcl", "appos")
        ),
        key=lambda x: x["id"],
    )''',
    '''# AUDIT N1 (Iteration 1): a purpose/goal oblique attached directly to a
# bare generic-category head ("sarana UNTUK menetapkan...", "fungsi UNTUK
# mengucapkan...", "hubungan DENGAN itihasa...") carries the defining
# content just as much as an acl/acl:relcl clause does, but wasn't being
# picked up as "clause_children" at all -- the S3 fallback below silently
# left these objects bare ("tirtha BERPERAN_SEBAGAI sarana", full stop).
_PURPOSE_OBLIQUE_CASE_MARKS = {"untuk", "dari", "bagi", "terhadap", "kepada", "dengan"}
_PURPOSE_ADVCL_MARKS = {"untuk", "agar", "supaya"}


def _purpose_oblique_children(token, tokens):
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
    return out


def _clause_children(token, tokens):
    base = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]
    base += _purpose_oblique_children(token, tokens)
    return sorted(base, key=lambda x: x["id"])''',
    "N1b _purpose_oblique_children + widened _clause_children",
)

# ---------------------------------------------------------------------------
# N1c: expand_object_with_clauses() picks up the same purpose obliques, so
# the fallback's "appended" string (built by calling this function) actually
# contains them.
# ---------------------------------------------------------------------------
repl(
    '''    clause_children = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]

    clause_children = sorted(clause_children, key=lambda x: x["id"])''',
    '''    clause_children = [
        child for child in tokens
        if child["head"] == token["id"]
        and child["deprel"] in ("acl", "acl:relcl", "appos")
    ]
    # AUDIT N1 (Iteration 1): also attach a purpose/goal oblique directly on
    # the head -- see _purpose_oblique_children() below.
    clause_children += _purpose_oblique_children(token, tokens)

    clause_children = sorted(clause_children, key=lambda x: x["id"])''',
    "N1c expand_object_with_clauses purpose-oblique inclusion",
)

# ---------------------------------------------------------------------------
# N1d: the S3 fallback itself -- check the resolved head token's LEMMA
# instead of requiring the whole surface phrase to be a single-word exact
# match (blocked "satu tahap" / "upacara keagamaan" / "beberapa jenis" etc.)
# ---------------------------------------------------------------------------
repl(
    '''    # AUDIT S3: bare generic category noun + a clause that yielded nothing
    # -> keep the clause on the object rather than lose it.
    if (
        not sub_relations
        and clause_children
        and len(primary_phrase.split()) == 1
        and primary_phrase.strip().lower() in GENERIC_CATEGORY_NOUNS
    ):''',
    '''    # AUDIT S3/N1: bare generic category noun + a clause that yielded nothing
    # -> keep the clause on the object rather than lose it. Iteration 0
    # gated this on the WHOLE primary_phrase string being a single-word
    # exact match, which missed a quantified/modified head ("satu tahap",
    # "upacara keagamaan", "beberapa jenis" all failed the check even
    # though their HEAD noun is the generic one). Check the resolved head
    # token's lemma instead (Iteration 1).
    if (
        not sub_relations
        and clause_children
        and content_head["lemma"].lower() in GENERIC_CATEGORY_NOUNS
    ):''',
    "N1d decompose_object fallback: check head lemma, not whole phrase",
)

# ---------------------------------------------------------------------------
# S13 (widened): match on object CONTENT, not on the relation label already
# being "MENURUT". Inserted right after the original exact-match filter.
# ---------------------------------------------------------------------------
repl(
    '''relations = [
    relation for relation in relations
    if not (relation["relation"] == "MENURUT"
            and relation["object"].strip().lower() in _MENURUT_ATTRIBUTION_OBJECTS)
]

# AUDIT S9: object_decomposition self-restatements''',
    '''relations = [
    relation for relation in relations
    if not (relation["relation"] == "MENURUT"
            and relation["object"].strip().lower() in _MENURUT_ATTRIBUTION_OBJECTS)
]

# AUDIT S13 (Iteration 1, widened): the exact-match list above only fires
# when the LABEL already came out "MENURUT" -- but the same source/
# citation adjunct ("dalam lontar X", "sebagaimana disinggung/diuraikan/
# tertulis dalam...", "di mata umat hindu") gets glued onto an object under
# all sorts of OTHER labels (DIKENAL_SEBAGAI, TERTULIS, DISINGGUNG_DI,
# DIURAIKAN, DINILAI_DI, MEMILIKI...) depending on which verb the parser
# happened to land on. Match on the OBJECT CONTENT instead of the relation
# label -- "zero relations rather than a wrong/meaningless one".
_ATTRIBUTION_OBJECT_PATTERN = re.compile(
    r"\\b(menurut|sebagaimana|dalam lontar|pada lontar|lontar (yama|petunjuk)"
    r"|uraian terdahulu|lembaran terdahulu|di mata (umat|orang))\\b",
    re.IGNORECASE,
)
relations = [
    relation for relation in relations
    if not _ATTRIBUTION_OBJECT_PATTERN.search(relation["object"])
]

# AUDIT S9: object_decomposition self-restatements''',
    "S13 widened attribution-object content filter",
)

# ---------------------------------------------------------------------------
# N11: S133 predicate underscore + the Panca Maha Bhuta verse overrides.
# ---------------------------------------------------------------------------
repl(
    '''            "relation": "tidak menjamin",
            "object": "sorga",''',
    '''            "relation": "tidak_menjamin",
            "object": "sorga",''',
    "N11 S133 predicate underscore",
)

repl(
    '''        {"subject": "logam campuran", "subject_label": None, "relation": "berdewa",
         "object": "dewa siwa", "object_label": None, "source": "manual_override"},
    ],
}

relations = [
    relation for relation in relations
    if relation["sentence_id"] not in MANUAL_RELATION_OVERRIDES
]''',
    '''        {"subject": "logam campuran", "subject_label": None, "relation": "berdewa",
         "object": "dewa siwa", "object_label": None, "source": "manual_override"},
    ],

    # AUDIT N11 (Iteration 1): the Panca Maha Bhuta closing verse --
    # "<element> sangkaning <quality> mulih (ring/maring) <element>" ("X is
    # the origin of quality Y; Y returns to X"). The parser splits
    # "<element> sangkaning" off as if it were a compound proper noun and
    # leaves the rest as a nonsense object (S4303: "teja sangkaning ADALAH
    # mulih maring teja"; S4304: "bayu sangkaning LAINNYA mulih maring
    # bayu"); S4300/S4301/S4305 carry the identical construction but
    # yielded ZERO relations. All five recovered by hand from the parallel
    # structure. S4301's sentence is truncated before "mulih ring apah" in
    # the source text, so only the BERASAL_DARI half is asserted for it.
    4300: [
        {"subject": "ganda", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "pretiwi", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
        {"subject": "ganda", "subject_label": "KONSEP_FILOSOFIS", "relation": "kembali_ke",
         "object": "pretiwi", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],
    4301: [
        {"subject": "rasa", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "apah", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],
    4303: [
        {"subject": "rupa", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "teja", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
        {"subject": "rupa", "subject_label": "KONSEP_FILOSOFIS", "relation": "kembali_ke",
         "object": "teja", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],
    4304: [
        {"subject": "ambekan", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "bayu", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
        {"subject": "ambekan", "subject_label": "KONSEP_FILOSOFIS", "relation": "kembali_ke",
         "object": "bayu", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],
    4305: [
        {"subject": "sabda", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "akasa", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
        {"subject": "sabda", "subject_label": "KONSEP_FILOSOFIS", "relation": "kembali_ke",
         "object": "akasa", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],
}

relations = [
    relation for relation in relations
    if relation["sentence_id"] not in MANUAL_RELATION_OVERRIDES
]''',
    "N11 Panca Maha Bhuta verse overrides",
)

if src == orig:
    print("NO CHANGES MADE")
    sys.exit(1)

lines = src.splitlines(keepends=True)
cell["source"] = lines
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nWrote {NB}  ({len(orig)} -> {len(src)} chars)")

"""Iteration-0 systemic fixes to cell 51 (relation extraction) of
Knowledge Processing.ipynb, per relation_audit_report.md section 2.

Fixes applied: S1 (object negation), S2 (MENUJU->DIMASUKKAN/DINAIKKAN),
S3 (generic-noun copula keeps yang-clause), S4 (ADALAH+bare-verb object),
S8 (holy-water verbs), S13 (menurut-attribution), S15 (berisi/diisi->BERISI),
plus MANUAL_RELATION_OVERRIDES: S134->S133 re-anchor, S1298 drop, S3755-3758 metals.

Idempotency: each replacement is guarded by an 'ALREADY PATCHED' check on a
sentinel string.
"""
import json, sys, io

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
# S1: object-side negation helper, inserted after is_negated().
# ---------------------------------------------------------------------------
repl(
    '''            if child["lemma"] in NEGATION_LEMMAS:
                return True

    return False

# ==========================================
# 13.3c. SURFACE-TEXT-AWARE RELATION LABELING''',
    '''            if child["lemma"] in NEGATION_LEMMAS:
                return True

    return False


# AUDIT S1: negation that sits on the OBJECT, not the predicate or subject.
# "tanpa jenazah", "dengan tanpa tulang", "bukan dari X" -- is_negated() never
# looks here, so these produced triples asserting the OPPOSITE of the sentence.
# Per this section's "zero relations rather than a wrong one" stance, a triple
# whose object is negated is dropped by the callers.
OBJECT_NEGATION_LEMMAS = {
    "tidak", "tak", "bukan", "tanpa", "non", "tan", "nora", "nenten",
    "belum", "jangan", "nir",
}


def _object_is_negated(object_token, tokens):
    if object_token is None:
        return False
    oid = object_token["id"]
    case_ids = {
        c["id"] for c in tokens
        if c["head"] == oid and c["deprel"] == "case"
    }
    for child in tokens:
        if child["lemma"].lower() not in OBJECT_NEGATION_LEMMAS:
            continue
        if child["head"] == oid and child["deprel"] in (
            "advmod", "det", "case", "mark", "amod", "dep", "cc", "nmod",
        ):
            return True
        if child["head"] in case_ids:
            return True
    return False

# ==========================================
# 13.3c. SURFACE-TEXT-AWARE RELATION LABELING''',
    "S1 object-negation helper",
)

# ---------------------------------------------------------------------------
# S2 / S8 / S15: predicate-label additions, right after the 'berada' rule.
# ---------------------------------------------------------------------------
repl(
    '''    # 4. FIX #8d
    if surface == "berada":
        return "BERADA_DI"
''',
    '''    # 4. FIX #8d
    if surface == "berada":
        return "BERADA_DI"

    # AUDIT S2: passive containment / elevation verbs are NOT "MENUJU".
    # "dimasukkan ke (dalam) X" ends up IN X; "dinaikkan ke X" ends up ON X.
    if voice == "passive":
        if lemma == "masuk":
            return "DIMASUKKAN_KE_DALAM"
        if lemma in ("naik", "unggah"):
            return "DINAIKKAN_KE"

    # AUDIT S8: holy-water-onto-a-target verbs are one relation -- the water is
    # applied to a body / effigy / place; it is not an offering TO the corpse
    # and it is not "brought to".
    if lemma in ("sirat", "percik", "perci", "sembur", "ciprat"):
        return "DIPERCIKKAN_PADA"

    # AUDIT S15: "berisi / diisi (dengan) X" = contains X, never MEMILIKI.
    if lemma == "isi" or surface.startswith("berisi") or surface.startswith("diisi"):
        return "DIISI_DENGAN" if voice == "passive" else "BERISI"
''',
    "S2/S8/S15 predicate labels",
)

# ---------------------------------------------------------------------------
# S4: is_definition_predicate excludes inflected "berbentuk / berarti / ...".
# ---------------------------------------------------------------------------
repl(
    '''def is_definition_predicate(token):
    return (
        token["lemma"] in DEFINITION_VERBS
        or token["text"].lower() in DEFINITION_SURFACE_FORMS
    )''',
    '''# AUDIT S4: "berbentuk X" (shaped like), "berarti / bermakna X" (means),
# "bernama X" (named) are inflected verbs whose lemma collides with the
# copula-noun list ("bentuk", "arti", "makna", "nama", "rupa"). They are NOT
# copula definitions -- route them to the verb extractor so they yield
# BERBENTUK / BERARTI / DIKENAL_SEBAGAI, not "X ADALAH berbentuk".
_SHAPE_MEANING_LEMMAS = {"bentuk", "arti", "makna", "rupa", "nama"}


def is_definition_predicate(token):
    t = token["text"].lower()
    if token["lemma"] in _SHAPE_MEANING_LEMMAS and (
        t.startswith("ber") or t.startswith("me") or t.startswith("di")
    ):
        return False
    return (
        token["lemma"] in DEFINITION_VERBS
        or t in DEFINITION_SURFACE_FORMS
    )''',
    "S4 is_definition_predicate",
)

# ---------------------------------------------------------------------------
# S3: GENERIC_CATEGORY_NOUNS constant, next to the decomposition constants.
# ---------------------------------------------------------------------------
repl(
    '''DECOMPOSE_OBJECTS = True            # False -> legacy expand_object_with_clauses everywhere
MAX_OBJECT_DECOMP_DEPTH = 3
MAX_SUBRELATIONS_PER_OBJECT = 5''',
    '''DECOMPOSE_OBJECTS = True            # False -> legacy expand_object_with_clauses everywhere
MAX_OBJECT_DECOMP_DEPTH = 3
MAX_SUBRELATIONS_PER_OBJECT = 5

# AUDIT S3: a bare generic category noun as the WHOLE object of a copula,
# with a relative/reduced clause that produced no sub-relation, means the
# defining content was silently dropped ("swasta ADALAH upacara" <- "...
# upacara yang dilakukan jika jenazah tidak ditemukan..."). For these the
# clause is kept on the object string (typed LITERAL) instead.
GENERIC_CATEGORY_NOUNS = {
    "upacara", "ritual", "upakara", "prosesi", "tradisi", "kegiatan", "proses",
    "tahap", "tahapan", "rangkaian",
    "tirtha", "tirta", "air", "banten", "sesajen", "sajen", "persembahan",
    "sarana", "prasarana", "alat", "benda", "bahan", "kain", "wadah",
    "bangunan", "tempat", "wujud", "bentuk",
    "pengorbanan", "yadnya", "pelaksanaan", "usaha", "cara",
    "sasih", "hari", "bulan", "waktu",
    "istilah", "sebutan", "nama", "kata",
    "doa", "mantra", "aturan", "ketentuan", "pantangan",
}''',
    "S3 GENERIC_CATEGORY_NOUNS constant",
)

# ---------------------------------------------------------------------------
# S3: fallback inside decompose_object.
# ---------------------------------------------------------------------------
repl(
    '''    sub_relations = [
        r for r in sub_relations
        if r["object"].strip()
        and r["object"].strip().lower() not in SUB_OBJECT_STOPWORDS
        and re.search(r"[a-z]{3}", r["object"].lower())
        and r["subject"].strip().lower() != r["object"].strip().lower()
    ][:MAX_SUBRELATIONS_PER_OBJECT]

    return primary_phrase, content_head, False, sub_relations''',
    '''    sub_relations = [
        r for r in sub_relations
        if r["object"].strip()
        and r["object"].strip().lower() not in SUB_OBJECT_STOPWORDS
        and re.search(r"[a-z]{3}", r["object"].lower())
        and r["subject"].strip().lower() != r["object"].strip().lower()
    ][:MAX_SUBRELATIONS_PER_OBJECT]

    # AUDIT S3: bare generic category noun + a clause that yielded nothing
    # -> keep the clause on the object rather than lose it.
    if (
        not sub_relations
        and clause_children
        and len(primary_phrase.split()) == 1
        and primary_phrase.strip().lower() in GENERIC_CATEGORY_NOUNS
    ):
        appended, _hc = expand_object_with_clauses(content_head, tokens)
        appended = _strip_stray_ring_head(appended)
        if appended.strip().lower() != primary_phrase.strip().lower():
            return appended, content_head, True, []

    return primary_phrase, content_head, False, sub_relations''',
    "S3 decompose_object fallback",
)

# ---------------------------------------------------------------------------
# S1 guards in the three emit paths.
# ---------------------------------------------------------------------------
repl(
    '''        for obj_tok in all_object_tokens:

            obj_tok = resolve_conjunct_head(obj_tok, tokens)

            object_phrase, object_has_clause, sub_relations = resolve_object(
                obj_tok, tokens, subject_phrase
            )''',
    '''        for obj_tok in all_object_tokens:

            obj_tok = resolve_conjunct_head(obj_tok, tokens)

            if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                continue

            object_phrase, object_has_clause, sub_relations = resolve_object(
                obj_tok, tokens, subject_phrase
            )''',
    "S1 guard in _emit_relations_for_verb",
)

repl(
    '''            for obj_tok in all_object_tokens:

                obj_tok = resolve_conjunct_head(obj_tok, tokens)

                # FIX #6c: expand_object_with_clauses() (bukan''',
    '''            for obj_tok in all_object_tokens:

                obj_tok = resolve_conjunct_head(obj_tok, tokens)

                if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                    continue

                # FIX #6c: expand_object_with_clauses() (bukan''',
    "S1 guard in extract_definition_relations",
)

repl(
    '''        obj_cands = find_object_tokens(clause_root, tokens)
        for obj_tok, obj_flags in obj_cands[:MAX_SUBRELATIONS_PER_OBJECT]:
            raw = _clause_predicate_label(clause_root, obj_tok, tokens, obj_flags)
            if raw not in CLAUSE_RELATION_WHITELIST:
                continue''',
    '''        obj_cands = find_object_tokens(clause_root, tokens)
        for obj_tok, obj_flags in obj_cands[:MAX_SUBRELATIONS_PER_OBJECT]:
            if _object_is_negated(obj_tok, tokens):   # AUDIT S1
                continue
            raw = _clause_predicate_label(clause_root, obj_tok, tokens, obj_flags)
            if raw not in CLAUSE_RELATION_WHITELIST:
                continue''',
    "S1 guard in _subrelations_from_clause",
)

# ---------------------------------------------------------------------------
# S4 backstop + S13: final filters, next to the 13.10c function-word drop.
# ---------------------------------------------------------------------------
repl(
    '''relations = [
    relation for relation in relations
    if relation["object"].strip().lower() not in FUNCTION_WORD_OBJECTS
]

# ==========================================
# 13.10b. REMOVE DUPLICATE RELATIONS''',
    '''relations = [
    relation for relation in relations
    if relation["object"].strip().lower() not in FUNCTION_WORD_OBJECTS
]

# AUDIT S4 (backstop): an object that is itself a bare (often inflected) verb
# or a copula stub says nothing -- "X ADALAH berbentuk / menjadi / merupakan".
VERB_STUB_OBJECTS = {
    "berbentuk", "berwujud", "berupa", "menjadi", "merupakan", "adalah",
    "ialah", "bertujuan", "berfungsi", "berarti", "bermakna", "terbuat",
    "terjadi", "hilang", "sirna", "musnah", "mantrai", "dimantrai",
    "berbadankan", "berlangsung", "dilakukan", "dilaksanakan", "digunakan",
}
relations = [
    relation for relation in relations
    if relation["object"].strip().lower() not in VERB_STUB_OBJECTS
]

# AUDIT S13: "menurut para ahli / tata cara / ketentuan" is source/manner
# attribution, not a relation.
_MENURUT_ATTRIBUTION_OBJECTS = {
    "ahli", "para ahli", "pendapat", "tata cara", "cara", "ketentuan",
    "aturan", "semestinya", "mestinya", "kebiasaan", "tata",
}
relations = [
    relation for relation in relations
    if not (relation["relation"] == "MENURUT"
            and relation["object"].strip().lower() in _MENURUT_ATTRIBUTION_OBJECTS)
]

# ==========================================
# 13.10b. REMOVE DUPLICATE RELATIONS''',
    "S4 backstop + S13 final filters",
)

# ---------------------------------------------------------------------------
# MANUAL_RELATION_OVERRIDES: re-anchor 134->133, drop 1298, add metals.
# ---------------------------------------------------------------------------
repl(
    '''MANUAL_RELATION_OVERRIDES = {
    134: [
        {
            "subject": "upakara",
            "subject_label": "SARANA_RITUAL",''',
    '''MANUAL_RELATION_OVERRIDES = {
    # AUDIT: re-anchored 134 -> 133. Sentence numbering shifted since this
    # override was written; the "bukan upakara yang besar dan megah yang
    # menjamin..." sentence is now S133 (S134 is "para sentana ... berusaha
    # untuk mengupacarainya...", which the auto extractor handles).
    133: [
        {
            "subject": "upakara",
            "subject_label": "SARANA_RITUAL",''',
    "override re-anchor 134->133",
)

repl(
    '''        {
            "subject": "karma wasana",
            "subject_label": "KONSEP_FILOSOFIS",
            "relation": "menentukan",
            "object": "nasib setelah meninggal",
            "object_label": None,
            "source": "manual_override",
        },
    ],
}''',
    '''        {
            "subject": "karma wasana",
            "subject_label": "KONSEP_FILOSOFIS",
            "relation": "menentukan",
            "object": "nasib setelah meninggal",
            "object_label": None,
            "source": "manual_override",
        },
    ],

    # AUDIT S12: reported misconception ("mereka mengira, bahwa nista, madya,
    # utama merupakan tinggi rendahnya ... yadnya") -- not a fact. Drop.
    1298: [],

    # AUDIT S4/S6: "(N) METAL (colour), tempatnya di DIR, dewanya adalah DEITY"
    # -- Stanza makes the anaphor "dewa(nya)" the subject; the real subject is
    # the metal. Five metals of a genuine kepeng coin (S3755-S3758).
    3755: [
        {"subject": "uang kepeng asli", "subject_label": "SARANA_RITUAL",
         "relation": "mengandung", "object": "lima unsur logam",
         "object_label": None, "source": "manual_override"},
        {"subject": "perak", "subject_label": None, "relation": "berwarna",
         "object": "putih", "object_label": None, "source": "manual_override"},
        {"subject": "perak", "subject_label": None, "relation": "berada_di",
         "object": "timur", "object_label": None, "source": "manual_override"},
        {"subject": "perak", "subject_label": None, "relation": "berdewa",
         "object": "dewa iswara", "object_label": None, "source": "manual_override"},
    ],
    3756: [
        {"subject": "tembaga", "subject_label": None, "relation": "berwarna",
         "object": "merah", "object_label": None, "source": "manual_override"},
        {"subject": "tembaga", "subject_label": None, "relation": "berada_di",
         "object": "selatan", "object_label": None, "source": "manual_override"},
        {"subject": "tembaga", "subject_label": None, "relation": "berdewa",
         "object": "dewa brahma", "object_label": None, "source": "manual_override"},
    ],
    3757: [
        {"subject": "emas", "subject_label": None, "relation": "berwarna",
         "object": "kuning", "object_label": None, "source": "manual_override"},
        {"subject": "emas", "subject_label": None, "relation": "berada_di",
         "object": "barat", "object_label": None, "source": "manual_override"},
        {"subject": "emas", "subject_label": None, "relation": "berdewa",
         "object": "dewa mahadewa", "object_label": None, "source": "manual_override"},
    ],
    3758: [
        {"subject": "besi", "subject_label": None, "relation": "berwarna",
         "object": "hitam", "object_label": None, "source": "manual_override"},
        {"subject": "besi", "subject_label": None, "relation": "berada_di",
         "object": "utara", "object_label": None, "source": "manual_override"},
        {"subject": "besi", "subject_label": None, "relation": "berdewa",
         "object": "dewa wishnu", "object_label": None, "source": "manual_override"},
        {"subject": "logam campuran", "subject_label": None, "relation": "berwarna",
         "object": "manca warna", "object_label": None, "source": "manual_override"},
        {"subject": "logam campuran", "subject_label": None, "relation": "berada_di",
         "object": "tengah", "object_label": None, "source": "manual_override"},
        {"subject": "logam campuran", "subject_label": None, "relation": "berdewa",
         "object": "dewa siwa", "object_label": None, "source": "manual_override"},
    ],
}''',
    "override drop 1298 + metals 3755-3758",
)

if src == orig:
    print("NO CHANGES MADE")
    sys.exit(1)

# write back: split into lines keeping '\n' like nbformat does
lines = src.splitlines(keepends=True)
cell["source"] = lines
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nWrote {NB}  ({len(orig)} -> {len(src)} chars)")

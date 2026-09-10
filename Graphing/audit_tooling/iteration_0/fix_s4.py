import json, sys
NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
cell = nb["cells"][51]
src = "".join(cell["source"])

old = '''# AUDIT S4: "berbentuk X" (shaped like), "berarti / bermakna X" (means),
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
    )'''

new = '''# AUDIT S4: "berbentuk X" (shaped like), "berarti / bermakna X" (means),
# "bernama X" (named), "berwujud X" are inflected verbs whose Stanza lemma
# collides with the copula-noun list ("bentuk"/"arti"/"makna"/"nama"/"rupa").
# They are NOT copula definitions -- route them to the verb extractor so they
# yield BERBENTUK / BERARTI / DIKENAL_SEBAGAI / BERWUJUD, not "X ADALAH
# berbentuk". Denylist by exact surface form so real copulas that ALSO
# lemmatise to "rupa" ("merupakan") are untouched.
_SHAPE_MEANING_NONCOPULA = {
    "berbentuk", "berwujud", "berupa", "berarti", "bermakna", "bernama",
    "berbadankan", "menyerupai", "berbentukkan",
}


def is_definition_predicate(token):
    t = token["text"].lower()
    if t in _SHAPE_MEANING_NONCOPULA:
        return False
    return (
        token["lemma"] in DEFINITION_VERBS
        or t in DEFINITION_SURFACE_FORMS
    )'''

if new.split("\n")[-1] in src and "_SHAPE_MEANING_NONCOPULA" in src:
    print("already fixed"); sys.exit(0)
assert src.count(old) == 1, src.count(old)
src = src.replace(old, new, 1)
cell["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("fixed S4 -> surface denylist")

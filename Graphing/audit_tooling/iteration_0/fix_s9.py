import json, sys
NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
cell = nb["cells"][51]
src = "".join(cell["source"])

anchor = '''relations = [
    relation for relation in relations
    if not (relation["relation"] == "MENURUT"
            and relation["object"].strip().lower() in _MENURUT_ATTRIBUTION_OBJECTS)
]

# ==========================================
# 13.10b. REMOVE DUPLICATE RELATIONS'''

new = '''relations = [
    relation for relation in relations
    if not (relation["relation"] == "MENURUT"
            and relation["object"].strip().lower() in _MENURUT_ATTRIBUTION_OBJECTS)
]

# AUDIT S9: object_decomposition self-restatements -- "X MELAMBANGKAN lambang",
# "X MELAMBANGKAN simbol", "X ADALAH hal/sesuatu".
_SELF_RESTATE = {
    "MELAMBANGKAN": SYMBOL_NOUNS,
    "ADALAH": {"hal", "sesuatu", "sesuatunya", "bagian"},
    "BERPERAN_SEBAGAI": SYMBOL_NOUNS,
}
relations = [
    relation for relation in relations
    if not (relation["relation"] in _SELF_RESTATE
            and relation["object"].strip().lower() in _SELF_RESTATE[relation["relation"]])
]

# ==========================================
# 13.10b. REMOVE DUPLICATE RELATIONS'''

if "_SELF_RESTATE" in src:
    print("already applied"); sys.exit(0)
assert src.count(anchor) == 1, src.count(anchor)
src = src.replace(anchor, new, 1)
cell["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("applied S9 self-restatement filter")

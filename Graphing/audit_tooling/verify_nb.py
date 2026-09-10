import json, ast
NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
assert nb.get("nbformat") == 4, nb.get("nbformat")
print("cells:", len(nb["cells"]))
for i in (43, 51, 53, 54):
    src = "".join(nb["cells"][i]["source"])
    try:
        ast.parse(src)
        print(f"cell {i}: syntax OK ({len(src.splitlines())} lines)")
    except SyntaxError as e:
        print(f"cell {i}: SYNTAX ERROR {e}")
        raise
# all cells have a top-level id?
missing = [i for i, c in enumerate(nb["cells"]) if not c.get("id")]
print("cells missing top-level id:", missing)
# spot-check sentinels present
c51 = "".join(nb["cells"][51]["source"])
for s in ["_object_is_negated", "DIMASUKKAN_KE_DALAM", "GENERIC_CATEGORY_NOUNS",
          "_SHAPE_MEANING_LEMMAS", "VERB_STUB_OBJECTS", "133:", "1298: []", "3758:"]:
    print(f"  {'ok' if s in c51 else 'MISSING'}: {s}")

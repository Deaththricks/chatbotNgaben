import json, shutil, datetime

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup = rf"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb.bak_relfix_{ts}"
shutil.copy(NB, backup)
print("backup:", backup)

nb = json.load(open(NB, encoding="utf-8"))
src = "".join(nb["cells"][51]["source"])

old = '''        elif lemma == "arti" and find_direct_child(clause_root, tokens, "obj") is not None:'''
new = '''        elif lemma == "tingkat" or surface.startswith("bertingkat"):
            # AUDIT D9 (Iteration 3, Stage 5): "bade YANG BERTINGKAT 11" /
            # "bade BERTINGKAT sembilan" -- the tier-count qualifier on the
            # subject was silently dropped (no branch above recognizes
            # "tingkat"), collapsing distinct bade/patulangan variants into
            # contradictory near-duplicate triples (S2000-S2002). Surface it
            # as its own fact rather than losing it.
            nummod = next(
                (c for c in tokens
                 if c["head"] == clause_root["id"] and c["deprel"] == "nummod"),
                None,
            )
            if nummod is not None:
                raw_label = "MEMILIKI_TINGKAT"
                object_candidates = [(nummod, set())]
        elif lemma == "arti" and find_direct_child(clause_root, tokens, "obj") is not None:'''

assert src.count(old) == 1, f"expected exactly 1 match, found {src.count(old)}"
src = src.replace(old, new)

nb["cells"][51]["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("patched.")

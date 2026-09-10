import json, shutil, datetime

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup = rf"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb.bak_relfix_{ts}"
shutil.copy(NB, backup)
print("backup:", backup)

nb = json.load(open(NB, encoding="utf-8"))
src = "".join(nb["cells"][51]["source"])

old = '''            clause_text = ", ".join(
                render_subtree_text(c, tokens) for c in conjuncts
            )'''
new = '''            clause_text = ", ".join(
                # AUDIT D6 (Iteration 3, cosmetic cleanup): each conjunct's own
                # rendered subtree can carry a leading comma/space (its own
                # preceding punct token, e.g. the "," before "penebusan" in
                # "surya, penebusan, pamerasan...") -- strip it before we join
                # with our own ", " separator, or the two combine into "X, , Y".
                render_subtree_text(c, tokens).lstrip(" ,") for c in conjuncts
            )'''

assert src.count(old) == 1, f"expected exactly 1 match, found {src.count(old)}"
src = src.replace(old, new)

nb["cells"][51]["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("patched.")

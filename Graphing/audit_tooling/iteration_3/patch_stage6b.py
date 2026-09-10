import json, shutil, datetime

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup = rf"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb.bak_relfix_{ts}"
shutil.copy(NB, backup)
print("backup:", backup)

nb = json.load(open(NB, encoding="utf-8"))
src = "".join(nb["cells"][51]["source"])

old1 = '''    if lemma == "buat":
        return "DIBUATKAN_UNTUK" if surface.endswith("kan") else "DIHASILKAN"'''
new1 = '''    if lemma == "buat":
        return "DIBUATKAN_UNTUK" if (surface.endswith("kan") or benefactive) else "DIHASILKAN"'''
assert src.count(old1) == 1, f"expected exactly 1 match for old1, found {src.count(old1)}"
src = src.replace(old1, new1)

old2 = '''def _passive_action_label(lemma, obj_upos, surface=""):'''
new2 = '''def _passive_action_label(lemma, obj_upos, surface="", benefactive=False):'''
assert src.count(old2) == 1, f"expected exactly 1 match for old2, found {src.count(old2)}"
src = src.replace(old2, new2)

# call sites: compute the benefactive signal (a "bagi"-cased oblique CHILD of
# the verb itself, e.g. "dibuat ... bagi-nya" -- S2986[1], distinct from
# S2612's "-kan" suffix signal) and pass it through.
old3 = '''        lab = _passive_action_label(lemma, obj_upos, surface=surface)
        if lab:
            return lab
        return voiced_surface_label(relation_token)

    # 16. bare voice (imperative / Balinese)
    lab = _passive_action_label(lemma, obj_upos, surface=surface)
    if lab:
        return lab'''
new3 = '''        # AUDIT D7 (Iteration 3, Stage 6): "dibuat ... BAGI-nya" (S2986[1]) is
        # the same benefactive-passive shape as "dibuatKAN" but the signal is
        # a "bagi"-marked oblique CHILD of the verb, not a verb suffix.
        _benefactive = any(
            c["head"] == relation_token["id"] and c["deprel"] == "obl"
            and get_case_marker(c, tokens) == "bagi"
            for c in tokens
        )
        lab = _passive_action_label(lemma, obj_upos, surface=surface, benefactive=_benefactive)
        if lab:
            return lab
        return voiced_surface_label(relation_token)

    # 16. bare voice (imperative / Balinese)
    lab = _passive_action_label(lemma, obj_upos, surface=surface)
    if lab:
        return lab'''
assert src.count(old3) == 1, f"expected exactly 1 match for old3, found {src.count(old3)}"
src = src.replace(old3, new3)

nb["cells"][51]["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("patched.")

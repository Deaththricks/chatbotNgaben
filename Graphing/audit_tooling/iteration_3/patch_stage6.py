import json, shutil, datetime

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup = rf"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb.bak_relfix_{ts}"
shutil.copy(NB, backup)
print("backup:", backup)

nb = json.load(open(NB, encoding="utf-8"))
src = "".join(nb["cells"][51]["source"])

# 1. function signature + the "buat" branch
old1 = '''def _passive_action_label(lemma, obj_upos):
    if lemma == "beri":                        return "DIBERI"'''
new1 = '''def _passive_action_label(lemma, obj_upos, surface=""):
    # AUDIT D7 (Iteration 3, Stage 6): "dibuat" (plain passive, "X is made")
    # and "dibuatkan" (benefactive passive, "X is made FOR someone") share
    # lemma "buat" and were both routed to DIHASILKAN/MENGHASILKAN, wrongly
    # implying the deceased/recipient PRODUCES the thing made for them
    # (S2612 "pitra mendiang MENGHASILKAN perlambang", S2986[1] "dibuat...
    # bagi-nya"). The subject itself is already correct in both cases -- this
    # is a label bug, not a subject/object swap bug, so it needs none of the
    # subject_label plumbing previously deferred for the broader D7/N3 class.
    if lemma == "buat":
        return "DIBUATKAN_UNTUK" if surface.endswith("kan") else "DIHASILKAN"
    if lemma == "beri":                        return "DIBERI"'''

assert src.count(old1) == 1, f"expected exactly 1 match for old1, found {src.count(old1)}"
src = src.replace(old1, new1)

# 2. remove "buat" from the PRODUCE_LEMMAS branch (now handled above)
old2 = '''    if lemma in PRODUCE_LEMMAS or lemma == "buat":  return "DIHASILKAN"'''
new2 = '''    if lemma in PRODUCE_LEMMAS:                return "DIHASILKAN"'''
assert src.count(old2) == 1, f"expected exactly 1 match for old2, found {src.count(old2)}"
src = src.replace(old2, new2)

# 3. both call sites: pass surface through
old3 = '''        lab = _passive_action_label(lemma, obj_upos)
        if lab:
            return lab
        return voiced_surface_label(relation_token)

    # 16. bare voice (imperative / Balinese)
    lab = _passive_action_label(lemma, obj_upos)
    if lab:
        return lab'''
new3 = '''        lab = _passive_action_label(lemma, obj_upos, surface=surface)
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

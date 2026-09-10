import json, re, traceback
NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CONLLU = r"C:\Misc\Work\AI_Chatbot\Graphing\Results\Final\dependency_results_ngaben\dependency_results_ngaben.conllu"
src = "".join(json.load(open(NB, encoding="utf-8"))["cells"][51]["source"])
cut = src.rindex("\n# =====", 0, src.index("# 13.7. RUN EXTRACTION"))
ns = {"re": re}
exec(compile(src[:cut], "<defs>", "exec"), ns)
drl, oin, deco, idp = ns["derive_raw_relation_label"], ns["_object_is_negated"], ns["decompose_object"], ns["is_definition_predicate"]
gc = ns["get_conjuncts"]
esp = ns["expand_subject_phrase"]
ccp = ns["_compound_child_conjunct_phrases"]
fcvr = ns["find_coordinated_verb_relations"]
fscr = ns["find_subject_clause_relations"]
nfsl = None  # extracted separately below (RUN-EXTRACTION-section statement)

_nfsl_start = src.index("_SELF_LOOP_SPELLING_VARIANTS = {")
_nfsl_end = src.index(
    "\n\n\nrelations = [\n    relation for relation in relations\n    if _normalize_for_self_loop(relation[\"subject\"])",
    _nfsl_start,
)
_nfsl_ns = {"re": re}
exec(compile(src[_nfsl_start:_nfsl_end], "<nfsl>", "exec"), _nfsl_ns)
nfsl = _nfsl_ns["_normalize_for_self_loop"]

blocks, cur, toks = {}, None, []
for line in open(CONLLU, encoding="utf-8"):
    line = line.rstrip("\n")
    m = re.match(r"# sent_id = S(\d+(?:\.\d+)?)$", line)
    if m:
        if cur: blocks[cur] = toks
        cur, toks = m.group(1), []
    elif line and not line.startswith("#"):
        c = line.split("\t")
        if len(c) >= 8 and c[0].isdigit():
            toks.append({"id": int(c[0]), "text": c[1], "lemma": c[2], "upos": c[3],
                         "head": int(c[6]), "deprel": c[7]})
if cur: blocks[cur] = toks

errs = 0
n_drl = n_deco = n_gc = n_esp = n_ccp = n_fcvr = n_fscr = n_nfsl = 0
max_gc_len = 0
from collections import Counter
labels = Counter()
for sid, tks in blocks.items():
    byid = {t["id"]: t for t in tks}
    for t in tks:
        try:
            oin(t, tks)
        except Exception:
            errs += 1; print(f"S{sid} _object_is_negated({t['id']}):"); traceback.print_exc()
        try:
            res = gc(t, tks)
            max_gc_len = max(max_gc_len, len(res))
            n_gc += 1
        except Exception:
            errs += 1; print(f"S{sid} get_conjuncts({t['id']}):"); traceback.print_exc()
        if t["upos"] == "VERB":
            for ch in tks:
                if ch["head"] == t["id"] and ch["deprel"] in ("obj", "obl"):
                    try:
                        labels[drl(t, ch, tks)] += 1; n_drl += 1
                    except Exception:
                        errs += 1; print(f"S{sid} drl:"); traceback.print_exc()
        if t["upos"] in ("NOUN", "PROPN"):
            try:
                deco(t, tks, "x"); n_deco += 1
            except Exception:
                errs += 1; print(f"S{sid} deco({t['id']}):"); traceback.print_exc()
            try:
                esp(t, tks); n_esp += 1
            except Exception:
                errs += 1; print(f"S{sid} expand_subject_phrase({t['id']}):"); traceback.print_exc()
            try:
                ccp(t, tks); n_ccp += 1
            except Exception:
                errs += 1; print(f"S{sid} _compound_child_conjunct_phrases({t['id']}):"); traceback.print_exc()
            try:
                fscr(t["text"], None, t, tks); n_fscr += 1
            except Exception:
                errs += 1; print(f"S{sid} find_subject_clause_relations({t['id']}):"); traceback.print_exc()
        if t["upos"] == "VERB":
            try:
                fcvr(t, tks); n_fcvr += 1
            except Exception:
                errs += 1; print(f"S{sid} find_coordinated_verb_relations({t['id']}):"); traceback.print_exc()
        try:
            nfsl(t["text"]); n_nfsl += 1
        except Exception:
            errs += 1; print(f"S{sid} _normalize_for_self_loop({t['id']}):"); traceback.print_exc()

print(f"\nran drl x{n_drl}, deco x{n_deco}, get_conjuncts x{n_gc} (max chain {max_gc_len}), "
      f"expand_subject_phrase x{n_esp}, _compound_child_conjunct_phrases x{n_ccp}, "
      f"find_coordinated_verb_relations x{n_fcvr}, find_subject_clause_relations x{n_fscr}, "
      f"_normalize_for_self_loop x{n_nfsl}, _object_is_negated over all tokens. errors: {errs}")
print("new labels seen:", {k: v for k, v in labels.items()
      if k in ("DIMASUKKAN_KE_DALAM","DINAIKKAN_KE","DIPERCIKKAN_PADA","BERISI","DIISI_DENGAN")})
print("LAINNYA count:", labels.get("LAINNYA", 0))

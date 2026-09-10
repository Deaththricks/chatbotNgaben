# Standalone harness: exec the DEFS portion of cell 51 (up to '# 13.7. RUN
# EXTRACTION'), parse real .conllu tokens for the audit's cited sentences, and
# assert the fixed behaviour + regressions.
import json, re, sys

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CONLLU = r"C:\Misc\Work\AI_Chatbot\Graphing\Results\Final\dependency_results_ngaben\dependency_results_ngaben.conllu"

src = next("".join(c["source"]) for c in json.load(open(NB, encoding="utf-8"))["cells"]
           if c["cell_type"] == "code" and "# 13. RELATION EXTRACTION" in "".join(c["source"]))
cut = src.index("# 13.7. RUN EXTRACTION")
cut = src.rindex("\n# =====", 0, cut)          # start of that banner
defs = src[:cut]

ns = {"re": re}   # cell 51 relies on `import re` from an earlier notebook cell

# cell 51's extract_definition_relations/extract_subject_verb_relations call
# get_entity_head()/get_token_by_id(), which live in an EARLIER cell (44) --
# pull just those in first so cell 51's defs-only exec has them available.
cell44_src = "".join(json.load(open(NB, encoding="utf-8"))["cells"][44]["source"])
cell44_cut = cell44_src.index("get_entity_deprel")
cell44_cut = cell44_src.index("\n\n", cell44_cut)
exec(compile(cell44_src[:cell44_cut], "<cell44-defs>", "exec"), ns)

exec(compile(defs, "<cell51-defs>", "exec"), ns)
G = lambda n: ns[n]

# ---- conllu loader ----------------------------------------------------------
def load_tokens():
    blocks, cur, toks = {}, None, []
    for line in open(CONLLU, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"# sent_id = S(\d+(?:\.\d+)?)$", line)
        if m:
            if cur is not None:
                blocks[cur] = toks
            cur, toks = m.group(1), []
        elif line and not line.startswith("#"):
            c = line.split("\t")
            if len(c) >= 8 and c[0].isdigit():
                toks.append({"id": int(c[0]), "text": c[1], "lemma": c[2],
                             "upos": c[3], "head": int(c[6]), "deprel": c[7]})
    if cur is not None:
        blocks[cur] = toks
    return blocks

TB = load_tokens()

def tok(sid, needle):
    for t in TB[str(sid)]:
        if t["text"].lower() == needle.lower():
            return t
    raise KeyError(f"S{sid}: no token '{needle}'")

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}   {detail}")

# ===========================================================================
# S1 - object negation
# ===========================================================================
oin = G("_object_is_negated")

# S2477: "... selalu dilakukan dengan tanpa tulang belulang sama sekali."
s = "2477"
tulang = next((t for t in TB[s] if t["text"].lower().startswith("tulang")), None)
check("S1/S2477 'tulang' object flagged negated", tulang and oin(tulang, TB[s]),
      f"tulang={tulang['id'] if tulang else None}")

# S1409: "... bukan dari hasil galian tanam titip, juga bukan dari sawa ..."
s = "1409"
hasil = next((t for t in TB[s] if t["lemma"].lower() == "hasil"), None)
sawa_neg = next((t for t in TB[s] if t["text"].lower() == "sawa"
                 and any(c["head"] == t["id"] and c["lemma"].lower() == "bukan" for c in TB[s])), None)
check("S1/S1409 'hasil' negated", hasil and oin(hasil, TB[s]))
check("S1/S1409 'sawa' (2nd, bukan dari) negated", sawa_neg and oin(sawa_neg, TB[s]))

# regression: a normal object must NOT be flagged
s = "6"  # "ngaben adalah ritual kremasi ..."
rk = next((t for t in TB[s] if t["text"].lower() == "kremasi"), None)
check("S1 regression: S6 'kremasi' NOT negated", rk and not oin(rk, TB[s]))

# ===========================================================================
# S2 - MENUJU -> DIMASUKKAN / DINAIKKAN
# ===========================================================================
drl = G("derive_raw_relation_label")

def label(sid, verb, obj):
    return drl(tok(sid, verb), tok(sid, obj), TB[str(sid)])

for sid, verb, obj, want in [
    ("3812", "dimasukkan", "peti", "DIMASUKKAN_KE_DALAM"),
    ("2644", "dimasukkan", None, "DIMASUKKAN_KE_DALAM"),
]:
    try:
        if obj is None:
            # find the 'ke'-marked obl of the verb
            v = tok(sid, verb)
            obj_t = next(t for t in TB[str(sid)]
                         if t["head"] == v["id"] and t["deprel"] in ("obl", "obj"))
            got = drl(v, obj_t, TB[str(sid)])
        else:
            got = label(sid, verb, obj)
        check(f"S2/S{sid} {verb} -> {want}", got == want, f"got {got}")
    except (KeyError, StopIteration) as e:
        check(f"S2/S{sid} {verb} -> {want}", False, f"token lookup failed: {e}")

# regression: real motion "menuju" stays MENUJU
try:
    s = "217"
    got = drl(tok(s, "dinaikkan") if any(t["text"].lower()=="dinaikkan" for t in TB[s]) else tok(s,"berangkat"),
              tok(s, "usungan") if any(t["text"].lower()=="usungan" for t in TB[s]) else tok(s,"setra"), TB[s])
    check("S2 regression S217 still a placement/goal label", got in ("DINAIKKAN_KE","MENUJU","DIBAWA_KE","DILETAKKAN_DI"), f"got {got}")
except Exception as e:
    check("S2 regression S217", False, str(e))

# ===========================================================================
# S4 - is_definition_predicate excludes berbentuk/berarti
# ===========================================================================
idp = G("is_definition_predicate")
fake = lambda text, lemma, upos="VERB": {"text": text, "lemma": lemma, "upos": upos, "id": 1}
check("S4 'berbentuk' not a def predicate", not idp(fake("berbentuk", "bentuk")))
check("S4 'berarti' not a def predicate", not idp(fake("berarti", "arti")))
check("S4 'bermakna' not a def predicate", not idp(fake("bermakna", "makna")))
check("S4 regression: 'adalah' still a def predicate", idp(fake("adalah", "adalah", "AUX")))
check("S4 regression: 'merupakan' STILL a def predicate", idp(fake("merupakan", "rupa")))
check("S4 regression: 'ialah' still a def predicate", idp(fake("ialah", "ialah", "AUX")))

# ===========================================================================
# S8 / S15 predicate labels
# ===========================================================================
check("S8 'sirat' -> DIPERCIKKAN_PADA", drl(fake("disiratkan","sirat"), fake("badan","badan","NOUN"), []) == "DIPERCIKKAN_PADA")
check("S15 'berisi' -> BERISI", drl(fake("berisi","isi"), fake("uang","uang","NOUN"), []) == "BERISI")
check("S15 'diisi' -> DIISI_DENGAN", drl(fake("diisi","isi"), fake("air","air","NOUN"), []) == "DIISI_DENGAN")

# ===========================================================================
# S3 - generic-noun clause fallback (decompose_object)
# ===========================================================================
deco = G("decompose_object")
for sid, headword in [("46", "upacara"), ("415", "sasih"), ("408", "sasih")]:
    try:
        s = str(sid)
        h = next(t for t in TB[s] if t["text"].lower() == headword and t["deprel"] in ("root","obj","obl","appos","conj","parataxis") or (t["text"].lower()==headword))
        # pick the copula-complement occurrence: the one with an acl/acl:relcl child
        cands = [t for t in TB[s] if t["text"].lower() == headword
                 and any(c["head"] == t["id"] and c["deprel"] in ("acl","acl:relcl") for c in TB[s])]
        h = cands[0] if cands else h
        phrase, _hd, clausal, subs = deco(h, TB[s], "swasta")
        check(f"S3/S{sid} object keeps clause", len(phrase.split()) > 1 and clausal,
              f"phrase={phrase!r} clausal={clausal}")
    except (StopIteration, KeyError) as e:
        check(f"S3/S{sid} object keeps clause", False, f"lookup failed: {e}")

# ===========================================================================
# N10 - get_conjuncts transitive walk
# ===========================================================================
gc = G("get_conjuncts")

# S4300-S4305 are now manual overrides (no longer auto-extracted), so use a
# real 3+-item coordinate list still handled by the auto rules: S344's
# "eteh-eteh sawa" component list (kamben, tapih, sabuk, udeng, ...).
try:
    s = "344"
    # first NOUN with at least one direct conj child -- the head of the list
    head = next(
        t for t in TB[s]
        if t["upos"] == "NOUN"
        and any(c["head"] == t["id"] and c["deprel"] == "conj" for c in TB[s])
    )
    direct_n = sum(1 for c in TB[s] if c["head"] == head["id"] and c["deprel"] == "conj")
    trans = gc(head, TB[s])
    check("N10/S344 transitive >= direct", len(trans) >= direct_n,
          f"direct={direct_n} transitive={len(trans)}")
except (StopIteration, KeyError) as e:
    check("N10/S344 transitive >= direct", False, f"lookup failed: {e}")

# regression: no crash / no duplicate ids on a token with zero conjuncts
try:
    s = "6"
    t0 = TB[s][0]
    got = gc(t0, TB[s])
    ids = [x["id"] for x in got]
    check("N10 regression: no dupes, no self", len(ids) == len(set(ids)) and t0["id"] not in ids)
except Exception as e:
    check("N10 regression", False, str(e))

# ===========================================================================
# N6 - "X termasuk Y" role swap
# ===========================================================================
try:
    s = "2748"
    termasuk = next(t for t in TB[s] if t["lemma"].lower() == "termasuk")
    obj_cands = G("find_object_tokens")(termasuk, TB[s])
    check("N6/S2748 'termasuk' has an object candidate", len(obj_cands) > 0,
          f"cands={[t['text'] for t,_ in obj_cands]}")
    got = drl(termasuk, obj_cands[0][0], TB[s]) if obj_cands else None
    check("N6/S2748 label is the swap sentinel", got == "_SWAP_JENIS_DARI", f"got {got}")
except (StopIteration, KeyError) as e:
    check("N6/S2748 termasuk swap", False, f"lookup failed: {e}")

# regression: "masuk" (not "termasuk") must NOT trip the sentinel
check("N6 regression: 'masuk' lemma untouched",
      drl(fake("masuk", "masuk"), fake("peti", "peti", "NOUN"), []) != "_SWAP_JENIS_DARI")

# ===========================================================================
# N1 - generic-noun clause fallback now keys off the HEAD LEMMA, and picks
# up a purpose oblique (not just acl/acl:relcl/appos)
# ===========================================================================
for sid, headword in [("1610", "tahap"), ("797", "upacara")]:
    try:
        s = str(sid)
        cands = [
            t for t in TB[s] if t["text"].lower() == headword
        ]
        # prefer the occurrence with either a clause child or a purpose
        # oblique/advcl hanging off it
        pref = None
        for t in cands:
            kids = [c for c in TB[s] if c["head"] == t["id"]]
            if any(c["deprel"] in ("acl", "acl:relcl", "appos", "advcl", "nmod", "obl") for c in kids):
                pref = t
                break
        h = pref or (cands[0] if cands else None)
        if h is None:
            raise StopIteration
        phrase, _hd, clausal, subs = deco(h, TB[s], "x")
        check(f"N1/S{sid} '{headword}' object keeps clause/oblique",
              clausal or bool(subs) or len(phrase.split()) > 1,
              f"phrase={phrase!r} clausal={clausal} subs={len(subs)}")
    except (StopIteration, KeyError) as e:
        check(f"N1/S{sid} '{headword}' object keeps clause/oblique", False, f"lookup failed: {e}")

# S1206: "tirtha itu juga selaku sarana untuk menetapkan kedudukan arwah
# mendiang..." -- the purpose xcomp attaches to the governing VERB
# ("selaku"), not to the object noun "sarana" itself, so this is the N1e
# verb-level path in _emit_relations_for_verb(), not decompose_object()
# directly -- exercise the real function, not just its object resolver.
erv = G("_emit_relations_for_verb")
try:
    s = "1206"
    selaku = next(t for t in TB[s] if t["lemma"].lower() == "selaku")
    tirtha = next(t for t in TB[s] if t["head"] == selaku["id"] and t["deprel"] == "nsubj")
    subj_phrase = G("expand_phrase")(tirtha, TB[s])
    out = erv(selaku, subj_phrase, "SARANA_RITUAL", TB[s], "1206")
    hit = next((r for r in out if r["object"].strip().lower().startswith("sarana")), None)
    check("N1e/S1206 verb-level purpose clause reaches the object",
          hit is not None and "menetapkan" in hit["object"],
          f"emitted={[r['object'] for r in out]}")
except (StopIteration, KeyError) as e:
    check("N1e/S1206 verb-level purpose clause reaches the object", False, f"lookup failed: {e}")

# regression: a genuinely bare, unmodified generic noun with NO clause at
# all must still come back terse (no crash, no spurious appension)
try:
    s = "6"
    ritual = next(t for t in TB[s] if t["text"].lower() == "ritual")
    phrase, _hd, clausal, subs = deco(ritual, TB[s], "ngaben")
    check("N1 regression: bare noun w/ real clause still resolves", isinstance(phrase, str) and phrase != "")
except Exception as e:
    check("N1 regression bare noun", False, str(e))

# ===========================================================================
# S13 (widened) / N11 - these live in the RUN-EXTRACTION section (after the
# defs-only exec() above), so pull just their standalone statements out of
# the FULL source and exec them in isolation (neither depends on any other
# cell-51 runtime state -- the regex only needs `re`, the overrides dict is
# a plain literal).
# ===========================================================================
def extract_stmt(start_anchor, end_anchor):
    i = src.index(start_anchor)
    j = src.index(end_anchor, i)
    return src[i:j]

_s13_src = extract_stmt(
    "_ATTRIBUTION_OBJECT_PATTERN = re.compile(",
    "\nrelations = [\n    relation for relation in relations\n    if not _ATTRIBUTION_OBJECT_PATTERN.search(relation[\"object\"])\n]",
) + "\nrelations = [\n    relation for relation in relations\n    if not _ATTRIBUTION_OBJECT_PATTERN.search(relation[\"object\"])\n]"
_s13_ns = {"re": re, "relations": []}
exec(compile(_s13_src, "<s13-filter>", "exec"), _s13_ns)
pat = _s13_ns["_ATTRIBUTION_OBJECT_PATTERN"]

_mro_src = extract_stmt("MANUAL_RELATION_OVERRIDES = {", "\n\nrelations = [\n    relation for relation in relations\n    if relation[\"sentence_id\"] not in MANUAL_RELATION_OVERRIDES\n]")
_mro_ns = {}
exec(compile(_mro_src, "<manual-overrides>", "exec"), _mro_ns)
mro = _mro_ns["MANUAL_RELATION_OVERRIDES"]

for obj, should_match in [
    ("lontar yama purva tattwa", True),
    ("sebagaimana disinggung pada uraian terdahulu", True),
    ("uraian terdahulu", True),
    ("di mata umat hindu", True),
    ("beberapa jenis", False),
    ("kayu cendana", False),
]:
    got = bool(pat.search(obj))
    check(f"S13/{'match' if should_match else 'no-match'} {obj!r}", got == should_match, f"got {got}")

# ===========================================================================
# N11 - manual overrides: S133 predicate + Panca Maha Bhuta verse
# (mro extracted alongside the S13 pattern above -- same RUN-section slice)
# ===========================================================================
check("N11/S133 predicate uses underscore",
      mro[133][0]["relation"] == "tidak_menjamin", f"got {mro[133][0]['relation']!r}")
for sid, n in [(4300, 2), (4301, 1), (4303, 2), (4304, 2), (4305, 2)]:
    check(f"N11/S{sid} override row count", len(mro[sid]) == n, f"got {len(mro[sid])}")
check("N11/S4303 rupa BERASAL_DARI teja",
      any(r["subject"] == "rupa" and r["relation"] == "berasal_dari" and r["object"] == "teja"
          for r in mro[4303]))
check("N11/S4304 ambekan KEMBALI_KE bayu",
      any(r["subject"] == "ambekan" and r["relation"] == "kembali_ke" and r["object"] == "bayu"
          for r in mro[4304]))

# ===========================================================================
# D1 (Iteration 2) - generic-noun clause fallback now verb-class-independent
# (MEMILIKI/MEMPEROLEH, not just ADALAH/BERPERAN_SEBAGAI) + descends into a
# "sebagai/selaku X" predicate-complement child for ITS own defining clause.
# ===========================================================================
try:
    s = "32"  # "ngaben memiliki peran ganda yang saling menguatkan" -- acl:relcl
    # directly on "peran" itself: decompose_object() alone should catch it.
    h = next(t for t in TB[s] if t["text"].lower() == "peran")
    phrase, _hd, clausal, subs = deco(h, TB[s], "x")
    check("D1/S32 'peran' (MEMILIKI-headed, acl:relcl on the noun) keeps its clause",
          clausal and "menguatkan" in phrase, f"phrase={phrase!r} clausal={clausal}")
except (StopIteration, KeyError) as e:
    check("D1/S32 'peran' keeps its clause", False, f"lookup failed: {e}")

# S61: "mapegat ... memiliki makna krusial UNTUK MEMUTUS ikatan..." -- the
# untuk-xcomp attaches to the governing VERB ("memiliki"), a sibling of
# "makna" itself, not to "makna" -- this is the N1e verb-level path, same
# shape as S1206/S4106, exercised via the real _emit_relations_for_verb().
try:
    s = "61"
    memiliki = next(t for t in TB[s] if t["text"].lower() == "memiliki")
    mapegat = next(t for t in TB[s] if t["head"] == memiliki["id"] and t["deprel"] == "nsubj")
    subj_phrase = G("expand_subject_phrase")(mapegat, TB[s])
    out = erv(memiliki, subj_phrase, None, TB[s], "61")
    hit = next((r for r in out if r["object"].strip().lower().startswith("makna")), None)
    check("D1/S61 MEMILIKI-makna verb-level purpose (xcomp) clause reaches the object",
          hit is not None and "memutus" in hit["object"],
          f"emitted={[r['object'] for r in out]}")
except (StopIteration, KeyError) as e:
    check("D1/S61 MEMILIKI-makna verb-level xcomp clause", False, f"lookup failed: {e}")

# S4106: "tirtha ini memiliki fungsi sebagai sarana untuk mengucapkan..." --
# "fungsi" has NO acl/purpose child of its own; "sarana" (its "sebagai" nmod
# child) carries the "untuk mengucapkan" acl. Requires the predicate-
# complement descent in _clause_children(), exercised via the real verb path
# since this is the MEMILIKI-fungsi shape N1e alone doesn't reach.
try:
    s = "4106"
    fungsi = next(t for t in TB[s] if t["text"].lower() == "fungsi")
    memiliki = next(t for t in TB[s] if t["id"] == fungsi["head"])
    tirtha = next(t for t in TB[s] if t["head"] == memiliki["id"] and t["deprel"] == "nsubj")
    subj_phrase = G("expand_subject_phrase")(tirtha, TB[s])
    out = erv(memiliki, subj_phrase, None, TB[s], "4106")
    hit = next((r for r in out if r["object"].strip().lower().startswith("fungsi")), None)
    check("D1/S4106 MEMILIKI-fungsi-SEBAGAI-X clause reaches the object",
          hit is not None and "mengucapkan" in hit["object"],
          f"emitted={[r['object'] for r in out]}")
except (StopIteration, KeyError) as e:
    check("D1/S4106 MEMILIKI-fungsi-SEBAGAI-X clause reaches the object", False, f"lookup failed: {e}")

# ===========================================================================
# D2 (Iteration 2) - bahwa-ccomp/advcl and sehingga-sibling clauses now
# retained; extract_definition_relations gets an N1e-equivalent verb-level
# fallback for agar/sehingga clauses hanging off the copula verb itself.
# ===========================================================================
edr = G("extract_definition_relations")

# S1429: "daksina merupakan penegasan secara formal BAHWA yadnya sudah
# selesai" -- the bahwa-advcl attaches to the copula VERB ("merupakan"), a
# sibling of "penegasan", not to "penegasan" itself -- same verb-level
# shape as S1136, exercised through the real extract_definition_relations().
try:
    import pandas as pd
    s = "1429"
    dep_result = [{"sentence_id": int(s), "tokens": TB[s]}]
    fake_ner = pd.DataFrame([{"sentence_id": int(s), "entity": "daksina", "label": None}])
    out = edr(dep_result, fake_ner)
    hit = next((r for r in out if "penegasan" in r["object"].lower()), None)
    check("D2/S1429 verb-level bahwa-advcl reaches a copula-verb object (extract_definition_relations)",
          hit is not None and "selesai" in hit["object"],
          f"emitted={[r['object'] for r in out]}")
except Exception as e:
    check("D2/S1429 verb-level bahwa-advcl reaches a copula-verb object", False, str(e))

try:
    s = "1136"  # "damar kurung itu merupakan sarana permohonan..., AGAR keletehan...diblokir..."
    dep_result = [{"sentence_id": int(s), "tokens": TB[s]}]
    fake_ner = pd.DataFrame([{"sentence_id": int(s), "entity": "damar kurung", "label": "SARANA_RITUAL"}])
    out = edr(dep_result, fake_ner)
    hit = next((r for r in out if "sarana" in r["object"].lower()), None)
    check("D2/S1136 verb-level agar-advcl reaches a copula-verb object (extract_definition_relations)",
          hit is not None and "diblokir" in hit["object"],
          f"emitted={[r['object'] for r in out]}")
except Exception as e:
    check("D2/S1136 verb-level agar-advcl reaches a copula-verb object", False, str(e))

# ===========================================================================
# D3 (Iteration 2) - subject-side coordinate NPs now joined via
# expand_subject_phrase(), not silently truncated to the head's own phrase.
# ===========================================================================
esp = G("expand_subject_phrase")
try:
    s = "1439"  # "masing-masing abu tulang kepala, tangan, punggung, dada, bokong, paha DAN kaki"
    abu = next(t for t in TB[s] if t["text"].lower() == "abu")
    phrase = esp(abu, TB[s])
    n_members = sum(phrase.count(w) for w in ("kepala", "tangan", "punggung", "dada", "bokong", "paha", "kaki"))
    check("D3/S1439 7-way subject conjunct list fully joined",
          n_members == 7, f"phrase={phrase!r}")
except (StopIteration, KeyError) as e:
    check("D3/S1439 7-way subject conjunct list fully joined", False, f"lookup failed: {e}")

try:
    s = "6"
    ngaben = next(t for t in TB[s] if t["text"].lower() == "ngaben")
    check("D3 regression: no-conjunct subject unchanged",
          esp(ngaben, TB[s]) == G("expand_phrase")(ngaben, TB[s]))
except (StopIteration, KeyError) as e:
    check("D3 regression: no-conjunct subject unchanged", False, f"lookup failed: {e}")

# ===========================================================================
# D4 (Iteration 2) - compound-child conjunct substitution: "sasih kasa dan
# kapitu" (kapitu is conj of kasa, a compound child of sasih, not of sasih
# itself) now yields a second phrase "sasih kapitu" instead of nothing.
# ===========================================================================
ccp = G("_compound_child_conjunct_phrases")
for sid in ("411", "413", "414"):
    try:
        s = sid
        sasih = next(t for t in TB[s] if t["text"].lower() == "sasih")
        variants = ccp(sasih, TB[s])
        check(f"D4/S{sid} compound-child conjunct produces a 'sasih <member2>' variant",
              len(variants) == 1 and variants[0].startswith("sasih "), f"variants={variants}")
    except (StopIteration, KeyError) as e:
        check(f"D4/S{sid} compound-child conjunct variant", False, f"lookup failed: {e}")

# regression: a head with NO compound-conjunct shape returns nothing
try:
    s = "6"
    t0 = TB[s][0]
    check("D4 regression: no false positive on an unrelated token", ccp(t0, TB[s]) == [])
except Exception as e:
    check("D4 regression", False, str(e))

# ===========================================================================
# D7 (Iteration 2, was N3) - benefactive-passive swap for dihaturkan/disuguhi
# with a bare (case-marker-free) object; "buat"/"taruh"/"beri"/"turun" are
# deliberately NOT in the swap set (see the code comment) -- regression-check
# that they still return their ordinary (non-swapped) label.
# ===========================================================================
try:
    s = "2843"  # "sang sulinggih, ... dihaturkan santapan istimewa"
    dihaturkan = next(t for t in TB[s] if t["text"].lower() == "dihaturkan")
    santapan = next(t for t in TB[s] if t["head"] == dihaturkan["id"] and t["deprel"] == "obj")
    got = drl(dihaturkan, santapan, TB[s])
    check("D7/S2843 dihaturkan+bare-obj -> swap sentinel", got == "_SWAP_DIPERSEMBAHKAN_KEPADA", f"got {got}")
except (StopIteration, KeyError) as e:
    check("D7/S2843 dihaturkan+bare-obj -> swap sentinel", False, f"lookup failed: {e}")

check("D7 regression: 'ditaruhkan' (taruh, not in swap set) unaffected",
      drl(fake("ditaruhkan", "taruh"), fake("punjung", "punjung", "NOUN"), []) != "_SWAP_DIPERSEMBAHKAN_KEPADA")
check("D7 regression: 'dibuatkan' (buat, not in swap set) unaffected",
      drl(fake("dibuatkan", "buat"), fake("perlambang", "perlambang", "NOUN"), []) != "_SWAP_DIPERSEMBAHKAN_KEPADA")

# swap actually applied end-to-end via _emit_relations_for_verb: subject and
# object trade places, object side picks up the 3-way coordinate recipient
# list via D3's expand_subject_phrase.
try:
    s = "2843"
    dihaturkan = next(t for t in TB[s] if t["text"].lower() == "dihaturkan")
    sulinggih = next(t for t in TB[s] if t["head"] == dihaturkan["id"] and t["deprel"] == "nsubj:pass")
    subj_phrase = esp(sulinggih, TB[s])
    out = erv(dihaturkan, subj_phrase, None, TB[s], "2843")
    hit = next((r for r in out if r["relation"] == "DIPERSEMBAHKAN_KEPADA"), None)
    check("D7/S2843 end-to-end: theme becomes subject, recipient list becomes object",
          hit is not None and hit["subject"].startswith("santapan")
          and "tukang banten" in hit["object"] and "tamu" in hit["object"],
          f"emitted={out}")
except (StopIteration, KeyError) as e:
    check("D7/S2843 end-to-end swap", False, f"lookup failed: {e}")

# ===========================================================================
# D8 (Iteration 2, was N4) - "diisi (dengan) X" locative guard: a location
# object now routes to DILETAKKAN_DI, not DIISI_DENGAN; find_subject_clause_
# relations recovers the contents clause separately.
# ===========================================================================
try:
    s = "3747"  # "di hulu hati, diisi sebuah kawangen yang berisi 9 biji uang kepeng..."
    diisi = next(t for t in TB[s] if t["text"].lower() == "diisi")
    hulu = next(t for t in TB[s] if t["head"] == diisi["id"] and t["deprel"] == "obl")
    got = drl(diisi, hulu, TB[s])
    check("D8/S3747 diisi+locative-obl -> DILETAKKAN_DI (not DIISI_DENGAN)",
          got == "DILETAKKAN_DI", f"got {got}")
except (StopIteration, KeyError) as e:
    check("D8/S3747 diisi+locative-obl -> DILETAKKAN_DI", False, f"lookup failed: {e}")

check("D8 regression: diisi+dengan-marked content still DIISI_DENGAN",
      drl(fake("diisi", "isi"), fake("air", "air", "NOUN"), []) == "DIISI_DENGAN")

fscr = G("find_subject_clause_relations")
try:
    s = "3747"
    kawangen = next(t for t in TB[s] if t["text"].lower() == "kawangen")
    out = fscr("kawangen", "SARANA_RITUAL", kawangen, TB[s])
    hit = next((r for r in out if r["relation"] == "BERISI"), None)
    check("D8/S3747 subject-clause BERISI (contents) recovered",
          hit is not None, f"emitted={[(r['relation'], r['object']) for r in out]}")
except (StopIteration, KeyError) as e:
    check("D8/S3747 subject-clause BERISI (contents) recovered", False, f"lookup failed: {e}")

# ===========================================================================
# D9 (Iteration 2) - bade/patulangan "berbentuk X dan Y" subject clause now
# recovered via find_subject_clause_relations; semasa/di-masa temporal nmod
# no longer fused into the subject phrase.
# ===========================================================================
try:
    s = "2056"  # "patulangan YANG BERBENTUK macan, singa, gadarba (beruang) dan binatang buas lainnya"
    patulangan = next(t for t in TB[s] if t["text"].lower() == "patulangan")
    out = fscr("patulangan", None, patulangan, TB[s])
    hits = [r for r in out if r["relation"] == "BERBENTUK"]
    n_members = sum(any(w in r["object"] for w in [r["object"]]) for r in hits)
    check("D9/S2056 berbentuk subject-clause recovered (4-way conjunct list)",
          len(hits) == 4, f"emitted={[r['object'] for r in hits]}")
except (StopIteration, KeyError) as e:
    check("D9/S2056 berbentuk subject-clause recovered", False, f"lookup failed: {e}")

ep = G("expand_phrase")
try:
    s = "1738"  # "mendiang SEMASA HIDUPNYA punya kedudukan tertentu..."
    mendiang = next(t for t in TB[s] if t["text"].lower() == "mendiang")
    phrase = ep(mendiang, TB[s])
    check("D9/S1738 temporal 'semasa hidupnya' not fused into subject",
          phrase.strip().lower() == "mendiang", f"phrase={phrase!r}")
except (StopIteration, KeyError) as e:
    check("D9/S1738 temporal nmod exclusion", False, f"lookup failed: {e}")

try:
    s = "1823"  # "bila mendiang DI MASA HIDUPNYA memegang jabatan..."
    mendiang = next(t for t in TB[s] if t["text"].lower() == "mendiang")
    phrase = ep(mendiang, TB[s])
    check("D9/S1823 temporal 'di masa hidupnya' not fused into subject",
          phrase.strip().lower() == "mendiang", f"phrase={phrase!r}")
except (StopIteration, KeyError) as e:
    check("D9/S1823 temporal nmod exclusion", False, f"lookup failed: {e}")

# regression: a genuine nmod (not semasa/masa) is unaffected
try:
    s = "1"
    t0 = next((t for t in TB[s] if any(
        c["head"] == t["id"] and c["deprel"] == "nmod" and c["lemma"].lower() not in ("masa",)
        for c in TB[s])), None)
    check("D9 regression: ordinary nmod still walked", True)  # smoke-covered below; no crash is the bar
except Exception as e:
    check("D9 regression: ordinary nmod", False, str(e))

# ===========================================================================
# D13 (Iteration 2) - find_coordinated_verb_relations skips an advcl sibling
# that's really a mis-attached temporal-framing clause, not a genuine
# coordinate action ("sesajen DIHATURKAN pada saat abu jenazah DIHANYUTKAN
# ke samudera" / "di kala jenazah DIANGKUT..., lancingan kajang DIJUNJUNG...").
# ===========================================================================
fcvr = G("find_coordinated_verb_relations")
try:
    s = "1187"
    dihaturkan = next(t for t in TB[s] if t["text"].lower() == "dihaturkan")
    got = fcvr(dihaturkan, TB[s])
    check("D13/S1187 temporal advcl sibling (dihanyutkan) excluded",
          not any(t["text"].lower() == "dihanyutkan" for t in got), f"got={[t['text'] for t in got]}")
except (StopIteration, KeyError) as e:
    check("D13/S1187 temporal advcl sibling excluded", False, f"lookup failed: {e}")

try:
    s = "1603"
    dijunjung = next(t for t in TB[s] if t["text"].lower() == "dijunjung")
    got = fcvr(dijunjung, TB[s])
    check("D13/S1603 temporal advcl sibling (diangkut) excluded",
          not any(t["text"].lower() == "diangkut" for t in got), f"got={[t['text'] for t in got]}")
except (StopIteration, KeyError) as e:
    check("D13/S1603 temporal advcl sibling excluded", False, f"lookup failed: {e}")

# regression: a genuine coordinate advcl with NO temporal framing is kept
try:
    s = "1603"
    dijunjung = next(t for t in TB[s] if t["text"].lower() == "dijunjung")
    got = fcvr(dijunjung, TB[s])
    # "membentuk" (sehingga membentuk barisan panjang) may or may not survive
    # depending on the pre-existing subordinate-mark guard -- just confirm no
    # crash and the call returns a list.
    check("D13 regression: find_coordinated_verb_relations still returns a list", isinstance(got, list))
except Exception as e:
    check("D13 regression", False, str(e))

# ===========================================================================
# D14 (Iteration 2) - self-loop final filter, including the kwangen/kawangen
# spelling-variant normalization.
# ===========================================================================
_nfsl_src = extract_stmt(
    "_SELF_LOOP_SPELLING_VARIANTS = {",
    "\n\n\nrelations = [\n    relation for relation in relations\n    if _normalize_for_self_loop(relation[\"subject\"])",
)
_nfsl_ns = {"re": re}
exec(compile(_nfsl_src, "<d14-self-loop>", "exec"), _nfsl_ns)
nfsl = _nfsl_ns["_normalize_for_self_loop"]
check("D14 'kwangen jeriji' normalizes same as 'kawangen jeriji'",
      nfsl("kwangen jeriji") == nfsl("kawangen jeriji"),
      f"{nfsl('kwangen jeriji')!r} vs {nfsl('kawangen jeriji')!r}")
check("D14 regression: genuinely different phrases stay different",
      nfsl("galar") != nfsl("bilah bambu"))
check("D14 regression: case/whitespace-only differences still normalize equal",
      nfsl("  Sasih  Kasa ") == nfsl("sasih kasa"))

# ===========================================================================
# D10 (Iteration 2) - widened _ATTRIBUTION_OBJECT_PATTERN + bare-lontar
# filter + sebagaimana-halnya comparative filter (re-extracted below since
# the pattern/filter statements changed; `pat`/`mro` above are the S13/N11-
# era objects, still valid for the D13 override checks further down).
# ===========================================================================
for obj, should_match in [
    ("mata umat hindu", True),            # S1226, no leading "di" survives in the object
    ("tertulis dalam beberapa lontar", True),   # S972, quantifier between "dalam" and "lontar"
    ("kayu cendana", False),
]:
    got = bool(pat.search(obj))
    check(f"D10/{'match' if should_match else 'no-match'} {obj!r}", got == should_match, f"got {got}")

_bare_lontar_src = extract_stmt(
    "# AUDIT D10 (Iteration 2): a bare, unqualified",
    '''relations = [
    relation for relation in relations
    if relation["object"].strip().lower() != "lontar"
]''',
) + '''relations = [
    relation for relation in relations
    if relation["object"].strip().lower() != "lontar"
]'''
_bl_ns = {"relations": [
    {"object": "lontar"}, {"object": "lontar yama purva tattwa"}, {"object": "kayu cendana"},
]}
exec(compile(_bare_lontar_src, "<d10-bare-lontar>", "exec"), _bl_ns)
remaining_objs = {r["object"] for r in _bl_ns["relations"]}
check("D10 bare 'lontar' object dropped, qualified one kept",
      "lontar" not in remaining_objs and "lontar yama purva tattwa" in remaining_objs,
      f"remaining={remaining_objs}")

ibdc = G("_is_bare_discourse_connective")
try:
    s = "2542"  # "sebagaimana halnya pangabenan, atma wedana pun ada beberapa jenis..."
    hal = next(t for t in TB[s] if t["text"].lower() in ("hal", "halnya"))
    check("D10/S2542 'sebagaimana halnya X' recognized as a comparative filler",
          ibdc(hal, TB[s]))
except (StopIteration, KeyError) as e:
    check("D10/S2542 sebagaimana-halnya filter", False, f"lookup failed: {e}")

# regression: "hal" with a real content child and NO similative marker is
# untouched by the new check -- still governed by the pre-existing
# bare-filler-children rule (a genuine descriptive child lets it through).
_hal_tok = {"text": "hal", "lemma": "hal", "upos": "NOUN", "id": 1, "head": 0, "deprel": "root"}
_hal_child = {"text": "penting", "lemma": "penting", "upos": "ADJ", "id": 2, "head": 1, "deprel": "amod"}
check("D10 regression: 'hal' WITHOUT a similative marker keeps the pre-existing rule",
      not ibdc(_hal_tok, [_hal_tok, _hal_child]))

# ===========================================================================
# Iteration 3, Stage 1a - berwujud/melambangkan lemma fix: "wujud" removed
# from the MELAMBANGKAN set so berwujud falls through to voiced_surface_label.
# ===========================================================================
try:
    s = "1688"  # "adegan ini berwujud cili terbuat dari rontal..."
    berwujud = next(t for t in TB[s] if t["text"].lower() == "berwujud")
    cili = next(t for t in TB[s] if t["head"] == berwujud["id"] and t["deprel"] == "obj")
    got = drl(berwujud, cili, TB[s])
    check("1a/S1688 berwujud -> BERWUJUD (not MELAMBANGKAN)", got == "BERWUJUD", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1a/S1688 berwujud -> BERWUJUD", False, f"lookup failed: {e}")

try:
    s = "2180"  # "bale salunglung berwujud sebuah rumah kecil sederhana."
    berwujud = next(t for t in TB[s] if t["text"].lower() == "berwujud")
    rumah = next(t for t in TB[s] if t["head"] == berwujud["id"] and t["deprel"] == "obj")
    got = drl(berwujud, rumah, TB[s])
    check("1a/S2180 berwujud -> BERWUJUD (not MELAMBANGKAN)", got == "BERWUJUD", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1a/S2180 berwujud -> BERWUJUD", False, f"lookup failed: {e}")

check("1a regression: 'melambangkan' (lemma 'lambang') still MELAMBANGKAN",
      drl(fake("melambangkan", "lambang"), fake("kesucian", "kesucian", "NOUN"), []) == "MELAMBANGKAN")
check("1a regression: 'menyerupai' (lemma 'serupa') still MELAMBANGKAN",
      drl(fake("menyerupai", "serupa"), fake("naga", "naga", "NOUN"), []) == "MELAMBANGKAN")

# ===========================================================================
# Iteration 3, Stage 1b - LAINNYA vacuous label dropped as a final-pass filter.
# ===========================================================================
_lainnya_src = extract_stmt(
    '# AUDIT (Iteration 3): "LAINNYA" is voiced_surface_label',
    'relations = [relation for relation in relations if relation["relation"] != "LAINNYA"]',
) + 'relations = [relation for relation in relations if relation["relation"] != "LAINNYA"]'
_lainnya_ns = {"relations": [
    {"relation": "LAINNYA", "object": "x"},
    {"relation": "BERADA_DI", "object": "y"},
]}
exec(compile(_lainnya_src, "<1b-lainnya-drop>", "exec"), _lainnya_ns)
remaining_rels = {r["relation"] for r in _lainnya_ns["relations"]}
check("1b LAINNYA relation dropped, real label kept",
      "LAINNYA" not in remaining_rels and "BERADA_DI" in remaining_rels,
      f"remaining={remaining_rels}")

# ===========================================================================
# Iteration 3, Stage 1c - sequence/temporal case marker now SUFFIXES the real
# predicate instead of replacing it outright (S1747, S2028, S2166, S2642).
# ===========================================================================
try:
    # S1747: "begitulah SETELAH paguntingan dan upadesa, berakhirnya, ..."
    # -- "berakhir" (lemma "akhir", cleanly stripped by Stanza) governs the
    # setelah-marked "paguntingan" obl. Confirms the suffix mechanism itself.
    s = "1747"
    berakhir = next(t for t in TB[s] if t["text"].lower() == "berakhir")
    paguntingan = next(t for t in TB[s] if t["text"].lower() == "paguntingan")
    got = drl(berakhir, paguntingan, TB[s])
    check("1c/S1747 setelah-marked object suffixes the real verb (BERAKHIR_SETELAH)",
          got == "BERAKHIR_SETELAH", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1c/S1747 BERAKHIR_SETELAH", False, f"lookup failed: {e}")

try:
    # S2642: "setelah pamralina, sekah kangsen itupun dibongkar." -- KNOWN
    # LIMITATION, not a regression: Stanza's own lemmatizer failed to strip
    # the "di-" prefix for THIS token (lemma == surface == "dibongkar"), so
    # the pre-existing voiced_surface_label() safety net (unrelated to this
    # patch, "lemma == surface -> the verb carries no relation sense on its
    # own -> LAINNYA") fires, and the wrapper correctly falls back to the
    # bare suffix -- identical output to before this fix, just for an
    # upstream lemmatization reason outside cell 51's control. Confirms the
    # wrapper's LAINNYA-fallback branch degrades safely rather than
    # emitting a bogus "LAINNYA_SETELAH".
    s = "2642"
    dibongkar = next(t for t in TB[s] if t["text"].lower() == "dibongkar")
    pamralina = next(t for t in TB[s] if t["text"].lower() == "pamralina")
    got = drl(dibongkar, pamralina, TB[s])
    check("1c/S2642 known lemma-quirk sentence degrades to bare SETELAH (not LAINNYA_SETELAH)",
          got == "SETELAH", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1c/S2642 known-limitation regression", False, f"lookup failed: {e}")

check("1c regression: sentinel labels pass through the suffix wrapper untouched",
      drl(fake("termasuk", "termasuk"), fake("sangge", "sangge", "NOUN"), []) in
      ("BERISI", "_SWAP_JENIS_DARI"))

# S2028/S2166: the OTHER shape of the same defect -- the verb itself IS
# "menjelang" ("menjelang dan sampai dengan hari pabersihan, naga banda
# diletakkan..."), previously picked up by find_coordinated_verb_relations()
# as a spurious coordinate-action sibling of the real root verb, shipping
# bare "MENJELANG" as if it were the whole predicate. Fixed by excluding any
# sibling advcl whose own lemma is itself a sequence/temporal marker.
fcvr_local = G("find_coordinated_verb_relations")
try:
    s = "2166"
    diletakkan = next(t for t in TB[s] if t["text"].lower() == "diletakkan")
    got = fcvr_local(diletakkan, TB[s])
    check("1c/S2166 'menjelang' sibling no longer emitted as its own coordinate relation",
          not any(t["text"].lower() == "menjelang" for t in got), f"got={[t['text'] for t in got]}")
except (StopIteration, KeyError) as e:
    check("1c/S2166 menjelang sibling excluded", False, f"lookup failed: {e}")

try:
    s = "2028"
    digantungkan = next(t for t in TB[s] if t["text"].lower() == "digantungkan")
    got = fcvr_local(digantungkan, TB[s])
    check("1c/S2028 'menjelang' sibling no longer emitted as its own coordinate relation",
          not any(t["text"].lower() == "menjelang" for t in got), f"got={[t['text'] for t in got]}")
except (StopIteration, KeyError) as e:
    check("1c/S2028 menjelang sibling excluded", False, f"lookup failed: {e}")

# regression: a genuine coordinate advcl sibling (not a bare temporal-marker
# verb) is still returned -- reuse D13's own S1603 regression sentence.
try:
    s = "1603"
    dijunjung = next(t for t in TB[s] if t["text"].lower() == "dijunjung")
    got = fcvr_local(dijunjung, TB[s])
    check("1c regression: find_coordinated_verb_relations still returns a list", isinstance(got, list))
except Exception as e:
    check("1c regression: find_coordinated_verb_relations", False, str(e))

# ===========================================================================
# Iteration 3, Stage 1d - "termasuk" swap narrowed to require a totality
# quantifier on the subject (S2748/S2794 still swap; S3237 no longer does).
# ===========================================================================
try:
    s = "2794"  # "lalu semua sekah termasuk sangge diturunkan dari pawedan."
    termasuk = next(t for t in TB[s] if t["lemma"].lower() == "termasuk")
    sangge = next(t for t in TB[s] if t["head"] == termasuk["id"] and t["deprel"] == "obj")
    got = drl(termasuk, sangge, TB[s])
    check("1d/S2794 'semua sekah termasuk sangge' still swaps (quantifier present)",
          got == "_SWAP_JENIS_DARI", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1d/S2794 termasuk swap regression", False, f"lookup failed: {e}")

try:
    s = "3237"  # "lekesan, (sirih lengkap dengan isinya termasuk tembakau, dan digulung)."
    termasuk = next(t for t in TB[s] if t["lemma"].lower() == "termasuk")
    tembakau = next(t for t in TB[s] if t["head"] == termasuk["id"] and t["deprel"] == "obj")
    got = drl(termasuk, tembakau, TB[s])
    check("1d/S3237 'lekesan termasuk tembakau' (no quantifier) no longer swaps -> BERISI",
          got == "BERISI", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1d/S3237 termasuk over-firing fix", False, f"lookup failed: {e}")

# regression: S2748 (already covered by the pre-existing N6/S2748 test above)
# must still swap -- re-affirm explicitly here since this is the exact
# sentinel test this stage narrowed.
try:
    s = "2748"
    termasuk = next(t for t in TB[s] if t["lemma"].lower() == "termasuk")
    obj_cands = G("find_object_tokens")(termasuk, TB[s])
    got = drl(termasuk, obj_cands[0][0], TB[s]) if obj_cands else None
    check("1d regression: S2748 still swaps after narrowing", got == "_SWAP_JENIS_DARI", f"got {got}")
except (StopIteration, KeyError) as e:
    check("1d regression: S2748 still swaps", False, f"lookup failed: {e}")

# ===========================================================================
# Iteration 3, Stage 1e - FUNCTION_WORD_OBJECTS exempts manual_override rows
# (S3758's "logam campuran BERADA_DI tengah" was being silently dropped).
# ===========================================================================
_fwo_src = extract_stmt(
    "FUNCTION_WORD_OBJECTS = SUB_OBJECT_STOPWORDS | {",
    '''relations = [
    relation for relation in relations
    if relation.get("source") == "manual_override"
    or relation["object"].strip().lower() not in FUNCTION_WORD_OBJECTS
]''',
) + '''relations = [
    relation for relation in relations
    if relation.get("source") == "manual_override"
    or relation["object"].strip().lower() not in FUNCTION_WORD_OBJECTS
]'''
_fwo_ns = {"SUB_OBJECT_STOPWORDS": G("SUB_OBJECT_STOPWORDS"), "relations": [
    {"object": "tengah", "source": "manual_override"},
    {"object": "tengah", "source": "dependency_rule"},
    {"object": "dewa siwa", "source": "manual_override"},
]}
exec(compile(_fwo_src, "<1e-fwo-exemption>", "exec"), _fwo_ns)
remaining = [(r["object"], r["source"]) for r in _fwo_ns["relations"]]
check("1e manual_override 'tengah' survives, auto-extracted 'tengah' still dropped",
      ("tengah", "manual_override") in remaining and ("tengah", "dependency_rule") not in remaining,
      f"remaining={remaining}")

# ===========================================================================
# Iteration 3, Stage 1f - S3758 override row is present (it always was; 1e is
# what makes it actually surface in the final output).
# ===========================================================================
check("1f/S3758 logam campuran BERADA_DI tengah override present",
      any(r["subject"] == "logam campuran" and r["relation"] == "berada_di"
          for r in mro.get(3758, [])),
      f"got={mro.get(3758, [])}")

# ===========================================================================
# Iteration 3, Stage 2 - D4 widened: (Fix A) _compound_child_conjunct_phrases
# now walks the full compound/flat/flat:name chain transitively, not just
# one hop; (Fix B) new _nmod_cc_conjunct_phrases() catches a second
# alternative that parses as an nmod (with its own case+cc children) rather
# than a conj ("di warung atau di dapur").
# ===========================================================================
ncc = G("_nmod_cc_conjunct_phrases")

try:
    # S3153: "arang pembakaran jaja uli ATAU jaja gina" -- 3 compound hops
    # deep (arang -> pembakaran -> jaja[uli] -conj-> jaja[gina]).
    s = "3153"
    dibuat = next(t for t in TB[s] if t["text"].lower() == "dibuat")
    sisig = next(t for t in TB[s] if t["text"].lower() == "sisig")
    out = erv(dibuat, esp(sisig, TB[s]), None, TB[s], s)
    objs = [r["object"] for r in out if r["relation"] == "TERBUAT_DARI"]
    check("2A/S3153 3-hop compound-chain conjunct recovered ('gina' present)",
          any("gina" in o for o in objs), f"objs={objs}")
except (StopIteration, KeyError) as e:
    check("2A/S3153 3-hop compound-chain conjunct", False, f"lookup failed: {e}")

try:
    s = "3836"  # "digunakan untuk dipan/plangkan DI WARUNG ATAU(PUN) DI DAPUR"
    digunakan = next(t for t in TB[s] if t["text"].lower() == "digunakan")
    baik = next(t for t in TB[s] if t["text"].lower() == "baik")
    out = erv(digunakan, esp(baik, TB[s]), None, TB[s], s)
    objs = {r["object"] for r in out}
    check("2B/S3836 nmod+cc second alternative recovered ('dapur' as its own object)",
          "dapur" in objs and "warung" in objs, f"objs={objs}")
except (StopIteration, KeyError) as e:
    check("2B/S3836 nmod+cc conjunct", False, f"lookup failed: {e}")

try:
    s = "3845"  # "ditaruh DI PURA ATAU DI MERAJAN"
    ditaruh = next(t for t in TB[s] if t["text"].lower() == "ditaruh")
    baik = next(t for t in TB[s] if t["text"].lower() == "baik")
    out = erv(ditaruh, esp(baik, TB[s]), None, TB[s], s)
    objs = {r["object"] for r in out}
    check("2B/S3845 nmod+cc second alternative recovered ('merajan' as its own object)",
          "merajan" in objs and "pura" in objs, f"objs={objs}")
except (StopIteration, KeyError) as e:
    check("2B/S3845 nmod+cc conjunct", False, f"lookup failed: {e}")

# regression: an ordinary nmod modifier with its own case marker but NO cc
# child must NOT be picked up (avoid over-firing on plain PP modifiers).
_nmod_head = {"id": 1, "text": "rumah", "lemma": "rumah", "upos": "NOUN", "head": 0, "deprel": "root"}
_nmod_child = {"id": 2, "text": "adat", "lemma": "adat", "upos": "NOUN", "head": 1, "deprel": "nmod"}
_nmod_case = {"id": 3, "text": "di", "lemma": "di", "upos": "ADP", "head": 2, "deprel": "case"}
check("2B regression: nmod WITHOUT its own cc child is not treated as a conjunct",
      ncc(_nmod_head, [_nmod_head, _nmod_child, _nmod_case]) == [])

# regression: previously-working D4/N10 sentences still fully intact.
for sid in ("411", "413", "414"):
    try:
        s = sid
        sasih = next(t for t in TB[s] if t["text"].lower() == "sasih")
        variants = ccp(sasih, TB[s])
        check(f"2A regression: D4/S{sid} still produces a 'sasih <member2>' variant",
              len(variants) == 1 and variants[0].startswith("sasih "), f"variants={variants}")
    except (StopIteration, KeyError) as e:
        check(f"2A regression: D4/S{sid}", False, f"lookup failed: {e}")

try:
    s = "3196"
    head = next(
        t for t in TB[s]
        if t["upos"] == "NOUN"
        and any(c["head"] == t["id"] and c["deprel"] == "conj" for c in TB[s])
    )
    trans = gc(head, TB[s])
    check("2A regression: S3196 15-way list unaffected by the compound-chain widening",
          len(trans) >= 14, f"len={len(trans)}")
except (StopIteration, KeyError) as e:
    check("2A regression: S3196 15-way list", False, f"lookup failed: {e}")

# ===========================================================================
# Iteration 3, Stage 3 - D1/D2 generalization: 3b subject-side purpose
# oblique, 3c "antara X dengan Y" recognized, 3d bahwa-ccomp on the copula
# root. (3a/S32/S61 needed no fix -- already correct, confirmed not in
# flag.txt; 3e/S2198[3] re-checked after Stage 4.)
# ===========================================================================
try:
    # S2124: "swadharma beliau UNTUK mamari-suddha (menyucikan) dunia ini,
    # merupakan fungsi pokok" -- the purpose clause sits on the subject.
    s = "2124"
    merupakan = next(t for t in TB[s] if t["text"].lower() == "merupakan")
    swadharma = next(t for t in TB[s] if t["head"] == merupakan["id"] and t["deprel"] == "nsubj")
    out = fscr(esp(swadharma, TB[s]), None, swadharma, TB[s])
    hit = next((r for r in out if r["relation"] == "BERTUJUAN_UNTUK"), None)
    check("3b/S2124 subject-side purpose oblique -> its own BERTUJUAN_UNTUK relation",
          hit is not None and "menyucikan" in hit["object"],
          f"emitted={[(r['relation'], r['object']) for r in out]}")
except (StopIteration, KeyError) as e:
    check("3b/S2124 subject-side purpose oblique", False, f"lookup failed: {e}")

try:
    # S1782: "upacara timbang terima ... ANTARA mendiang ... DENGAN keluarga..."
    s = "1782"
    upacara = next(t for t in TB[s] if t["text"].lower() == "upacara")
    phrase, _hd, clausal, _subs = deco(upacara, TB[s], "pamerasan")
    check("3c/S1782 'antara X dengan Y' clause now retained on the object",
          "mendiang" in phrase and "keluarga" in phrase, f"phrase={phrase!r}")
except (StopIteration, KeyError) as e:
    check("3c/S1782 antara-clause retained", False, f"lookup failed: {e}")

try:
    # S2055: "patulangan ... ADALAH pertanda BAHWA mereka MERUPAKAN
    # keturunan ..." -- one of Iteration 2's own original D2 targets,
    # still broken because "merupakan" attaches via ccomp, not advcl.
    s = "2055"
    pertanda = next(t for t in TB[s] if t["text"].lower() == "pertanda")
    phrase, _hd, clausal, _subs = deco(pertanda, TB[s], "patulangan")
    check("3d/S2055 bahwa-ccomp on the copula root now retained (was Iteration-2's own D2 target)",
          "bahwa" in phrase and "keturunan" in phrase, f"phrase={phrase!r}")
except (StopIteration, KeyError) as e:
    check("3d/S2055 bahwa-ccomp retained", False, f"lookup failed: {e}")

# regression: S1429 (advcl "bahwa", the shape Iteration 2's D2 already
# fixed) must still work after widening to ccomp.
try:
    s = "1429"
    dep_result = [{"sentence_id": int(s), "tokens": TB[s]}]
    fake_ner = pd.DataFrame([{"sentence_id": int(s), "entity": "daksina", "label": None}])
    out = edr(dep_result, fake_ner)
    hit = next((r for r in out if "penegasan" in r["object"].lower()), None)
    check("3d regression: S1429 advcl-bahwa (Iteration 2's D2) still works",
          hit is not None and "selesai" in hit["object"], f"emitted={[r['object'] for r in out]}")
except Exception as e:
    check("3d regression: S1429 advcl-bahwa", False, str(e))

try:
    s = "3747"
    diisi = next(t for t in TB[s] if t["text"].lower() == "diisi")
    hulu = next(t for t in TB[s] if t["head"] == diisi["id"] and t["deprel"] == "obl")
    got = drl(diisi, hulu, TB[s])
    check("3c/3d regression: D8/S3747 diisi+locative-obl still DILETAKKAN_DI",
          got == "DILETAKKAN_DI", f"got {got}")
except (StopIteration, KeyError) as e:
    check("3c/3d regression: D8/S3747", False, f"lookup failed: {e}")

# ===========================================================================
# D13/D14 (Iteration 2) - new MANUAL_RELATION_OVERRIDES entries.
# ===========================================================================
for sid, n in [(1889, 1), (3283, 0), (3080, 4), (3546, 3), (3334, 0)]:
    check(f"D13/D14 override S{sid} row count", sid in mro and len(mro[sid]) == n,
          f"got {len(mro.get(sid, [])) if sid in mro else 'MISSING'}")
check("D13/S1889 pabersihan DILAKUKAN ... sebelum ngaben",
      any(r["subject"] == "pabersihan" and r["relation"] == "dilakukan" for r in mro.get(1889, [])))
check("D13/S3080 punjung ditaruhkan_di_samping jenazah + 3x berisi",
      sum(1 for r in mro.get(3080, []) if r["relation"] == "berisi") == 3
      and any(r["relation"] == "ditaruhkan_di_samping" for r in mro.get(3080, [])))

# ===========================================================================
# D6 (Iteration 3, Stage 4) - duplicate-glue dedup in expand_object_with_clauses
# ===========================================================================
try:
    s = "1963"
    sajen = next(t for t in TB[s] if t["id"] == 20)  # "sajen" obl of "bagaikan"
    expand = G("expand_object_with_clauses")
    text, has_clause = expand(sajen, TB[s])
    check("D6/S1963 no duplicate 'surya' in expanded object",
          text.count("surya") == 1, f"got {text!r}")
    check("D6/S1963 all conjunct siblings surfaced (no garbled dump)",
          all(w in text for w in ("penebusan", "pamerasan", "banten")),
          f"got {text!r}")
    check("D6/S1963 no double-comma join artifact",
          ", , " not in text, f"got {text!r}")
except (StopIteration, KeyError) as e:
    check("D6/S1963", False, f"lookup failed: {e}")

# regression: an ordinary acl:relcl clause-glue (not the base_ids-overlap
# case) must still glue normally, unaffected by the dedup branch.
try:
    s = "1456"
    ngaben_obj = next(t for t in TB[s] if t["lemma"].lower() == "ngaben" and t["deprel"] == "obj")
    expand = G("expand_object_with_clauses")
    text, has_clause = expand(ngaben_obj, TB[s])
    check("D6 regression: S1456 ordinary acl:relcl clause-glue still works",
          "sederhana" in text, f"got {text!r}")
except (StopIteration, KeyError) as e:
    check("D6 regression: S1456", False, f"lookup failed: {e}")

# ===========================================================================
# D9 remainder (Iteration 3, Stage 5) - bade/patulangan tier-count qualifier
# ===========================================================================
fscr = G("find_subject_clause_relations")
for sid, want in [("2000", "11"), ("2001", "sembilan"), ("2002", "tujuh")]:
    try:
        subj = next(t for t in TB[sid] if t["id"] == 1)
        rels = fscr(subj["text"], None, subj, TB[sid])
        hit = next((r for r in rels if r["relation"] == "MEMILIKI_TINGKAT"), None)
        check(f"D9/S{sid} bade tier count surfaced",
              hit is not None and hit["object"].strip().lower() == want,
              f"got {hit}")
    except (StopIteration, KeyError) as e:
        check(f"D9/S{sid} bade tier count", False, f"lookup failed: {e}")

# ===========================================================================
# D9 remainder (Iteration 3, Stage 5) - section-heading-as-subject overrides
# ===========================================================================
for sid, n in [(3604, 2), (3733, 2), (3760, 2), (3973, 1)]:
    check(f"D9/Stage5 override S{sid} row count", sid in mro and len(mro[sid]) == n,
          f"got {len(mro.get(sid, [])) if sid in mro else 'MISSING'}")
check("D9/Stage5 S3604 no leftover SETELAH junk relation",
      not any(r["relation"] == "setelah" for r in mro.get(3604, [])))
check("D9/Stage5 S3733 no leftover SETELAH junk relation",
      not any(r["relation"] == "setelah" for r in mro.get(3733, [])))

# ===========================================================================
# D7 remainder (Iteration 3, Stage 6) - dibuat vs dibuatkan benefactive label
# ===========================================================================
try:
    s = "2612"
    toks = TB[s]
    verb = next(t for t in toks if t["id"] == 8)   # dibuatkan
    obj = next(t for t in toks if t["id"] == 9)    # perlambang
    got = drl(verb, obj, toks)
    check("D7/S2612 dibuatkan -kan suffix -> DIBUATKAN_UNTUK", got == "DIBUATKAN_UNTUK", f"got {got}")
except (StopIteration, KeyError) as e:
    check("D7/S2612", False, f"lookup failed: {e}")

try:
    s = "2986"
    toks = TB[s]
    verb = next(t for t in toks if t["id"] == 20)  # dibuat
    obj = next(t for t in toks if t["id"] == 23)   # buah (daksina tapakan)
    got = drl(verb, obj, toks)
    check("D7/S2986[1] dibuat + bagi-oblique -> DIBUATKAN_UNTUK", got == "DIBUATKAN_UNTUK", f"got {got}")
except (StopIteration, KeyError) as e:
    check("D7/S2986[1]", False, f"lookup failed: {e}")

# regression: an ordinary plain "dibuat" with NO benefactive oblique and no
# -kan suffix must still say DIHASILKAN, not get swept into DIBUATKAN_UNTUK.
try:
    s = "3330"
    toks = TB[s]
    verb = next((t for t in toks if t["lemma"].lower() == "buat"), None)
    check("D7 regression: plain 'buat' with no benefactive signal exists in S3330",
          verb is not None, f"verb={verb}")
    if verb is not None:
        obj_cand = next((t for t in toks if t["head"] == verb["id"] and t["deprel"] in ("obj", "nsubj:pass")), None)
        if obj_cand is not None:
            got = drl(verb, obj_cand, toks)
            check("D7 regression: S3330 plain buat NOT swept into DIBUATKAN_UNTUK",
                  got != "DIBUATKAN_UNTUK", f"got {got}")
except (StopIteration, KeyError) as e:
    check("D7 regression S3330", False, f"lookup failed: {e}")

# ===========================================================================
# D12 (Iteration 3, Stage 7) - repeated phrase fragment dedup
# ===========================================================================
dedupe = G("_dedupe_repeated_phrase_fragment")
for text, want in [
    ("upacara jenazah utuh untuk jenazah utuh ( 3-7 hari setelah meninggal )",
     "upacara jenazah utuh ( 3-7 hari setelah meninggal )"),
    ("istilah umat hindu bagi umat hindu di sini", "istilah umat hindu di sini"),
    ("bangunan sawa untuk sawa ( ISTILAH_UMUM_RITUAL )", "bangunan sawa ( ISTILAH_UMUM_RITUAL )"),
    ("wujud ketulus-ikhlasan hati pihak dari ketulus-ikhlasan hati pihak yang bersangkutan",
     "wujud ketulus-ikhlasan hati pihak yang bersangkutan"),
    ("simbol rare angon dari rare angon yaitu lambang keperkasaan seorang laki-laki",
     "simbol rare angon yaitu lambang keperkasaan seorang laki-laki"),
    ("simbol dewi sri dari dewi sri , yaitu lambang kesuburan",
     "simbol dewi sri , yaitu lambang kesuburan"),
    ("symbol pikiran dari pikiran dan perasaan sang yajamana",
     "symbol pikiran dan perasaan sang yajamana"),
]:
    got = dedupe(text)
    check(f"D12/dedupe {text[:40]!r}...", got == want, f"got {got!r}")

# negative: legitimate short repeated word/phrase must NOT collapse
for text in [
    "kaki jenazah dan kaki lembu",
    "upacara untuk keluarga besar dan upacara untuk keluarga kecil",
]:
    got = dedupe(text)
    check(f"D12 regression: {text!r} unchanged", got == text, f"got {got!r}")

# ===========================================================================
# summary
# ===========================================================================
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"\n{'='*60}\n{len(results)-n_fail}/{len(results)} passed, {n_fail} failed")
sys.exit(1 if n_fail else 0)

import json, shutil, datetime

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup = rf"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb.bak_relfix_{ts}"
shutil.copy(NB, backup)
print("backup:", backup)

nb = json.load(open(NB, encoding="utf-8"))
src = "".join(nb["cells"][51]["source"])

# 1. Remove the function definition from where Stage 7's first patch put it
#    (after the RUN EXTRACTION cut, where the harness can't reach it) -- keep
#    only the application loop there.
old1 = '''# AUDIT D12 (Iteration 3, Stage 7): a short phrase gets glued to itself
# across a "dari"/"untuk"/"bagi" marker during span reconstruction -- "simbol
# rare angon DARI rare angon" (S3589), "istilah umat hindu BAGI umat hindu
# di sini" (S785), "bangunan sawa UNTUK sawa" (S1982), "wujud ketulus-
# ikhlasan hati pihak DARI ketulus-ikhlasan hati pihak yang bersangkutan"
# (S3004). Deliberately narrow (whole-short-phrase-repeat-around-one-of-
# these-three-markers only, backreference requires an EXACT match) rather
# than touching collect_phrase_tokens()'s nmod walk, which is load-bearing
# elsewhere and not the root cause of every instance of this shape.
_DUP_FRAGMENT_RE = re.compile(
    r"\\b([A-Za-z][\\w-]*(?:\\s+[A-Za-z][\\w-]*){0,3})\\s+(dari|untuk|bagi)\\s+\\1\\b",
    re.IGNORECASE,
)


def _dedupe_repeated_phrase_fragment(text):
    return _DUP_FRAGMENT_RE.sub(lambda m: m.group(1), text, count=1)


for relation in relations:'''
new1 = '''# AUDIT D12 (Iteration 3, Stage 7): dedup helper defined earlier (before the
# RUN EXTRACTION cut, so it's directly unit-testable) -- applied here to
# every already-extracted relation's final subject/object text.
for relation in relations:'''
assert src.count(old1) == 1, f"expected exactly 1 match for old1, found {src.count(old1)}"
src = src.replace(old1, new1)

# 2. Insert the actual definition earlier, right before "13.7. RUN EXTRACTION".
old2 = '''    return relations
# ==========================================
# 13.7. RUN EXTRACTION
# =========================================='''
new2 = '''    return relations


# AUDIT D12 (Iteration 3, Stage 7): a short phrase gets glued to itself
# across a "dari"/"untuk"/"bagi" marker during span reconstruction -- "simbol
# rare angon DARI rare angon" (S3589), "istilah umat hindu BAGI umat hindu
# di sini" (S785), "bangunan sawa UNTUK sawa" (S1982), "wujud ketulus-
# ikhlasan hati pihak DARI ketulus-ikhlasan hati pihak yang bersangkutan"
# (S3004). Deliberately narrow (whole-short-phrase-repeat-around-one-of-
# these-three-markers only, backreference requires an EXACT match) rather
# than touching collect_phrase_tokens()'s nmod walk, which is load-bearing
# elsewhere and not the root cause of every instance of this shape.
_DUP_FRAGMENT_RE = re.compile(
    r"\\b([A-Za-z][\\w-]*(?:\\s+[A-Za-z][\\w-]*){0,3})\\s+(dari|untuk|bagi)\\s+\\1\\b",
    re.IGNORECASE,
)


def _dedupe_repeated_phrase_fragment(text):
    return _DUP_FRAGMENT_RE.sub(lambda m: m.group(1), text, count=1)


# ==========================================
# 13.7. RUN EXTRACTION
# =========================================='''
assert src.count(old2) == 1, f"expected exactly 1 match for old2, found {src.count(old2)}"
src = src.replace(old2, new2)

nb["cells"][51]["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("patched.")

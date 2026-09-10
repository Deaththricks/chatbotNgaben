"""
Perf batch 2, patch 1: precompile lookup_entity_label's fallback loop (cell 51).

Same bug class as the already-fixed dictionary_ner precompile: lookup_entity_label
re-sorts the ~12k-entry COMBINED_ENTITY_DICTIONARY and rebuilds+recompiles ~12k
word-boundary regex STRINGS on every call (Python's 512-entry compile cache thrashes).
Called once per relation for object typing + again for synthetic-subject typing.

Fix: build a module-level list of (entity, label, compiled_pattern) ONCE, sorted
longest-key-first exactly as today, and iterate that instead.

Byte-identical: stable sort of a dict constant after 13.9 => identical order => identical
longest-first / first-match tie-break; compiled.search(s) == re.search(pattern_str, s)
with no flags. Verified offline by scratchpad/verify_lookup_entity_label.py.

Idempotent, anchor-guarded, string-replace-into-cell-51-source (same pattern as every
prior iteration's patch scripts).
"""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CELL_INDEX = 51


def apply(src, old, new, label):
    count = src.count(old)
    if count == 0:
        raise SystemExit(f"[FAIL] anchor not found for: {label}")
    if count > 1:
        raise SystemExit(f"[FAIL] anchor ambiguous ({count} matches) for: {label}")
    print(f"[ok] {label}")
    return src.replace(old, new, 1)


def main():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)
    cell = nb["cells"][CELL_INDEX]
    src = "".join(cell["source"])
    original_len = len(src)

    if "_ENTITY_LABEL_LOOKUP" in src:
        raise SystemExit("[FAIL] already patched (_ENTITY_LABEL_LOOKUP present)")

    # ---- 1. build the precompiled list right after COMBINED_ENTITY_DICTIONARY ----
    src = apply(
        src,
        '''COMBINED_ENTITY_DICTIONARY = {
    **general_ner_dictionary,
    **cultural_dictionary,   # cultural wins on overlap, same as your NER merge
}


def lookup_entity_label(phrase, dictionary, exact_only=False):''',
        '''COMBINED_ENTITY_DICTIONARY = {
    **general_ner_dictionary,
    **cultural_dictionary,   # cultural wins on overlap, same as your NER merge
}

# PERF: lookup_entity_label's buried-word fallback used to re-sort this whole
# ~12k-entry dict and rebuild + recompile ~12k word-boundary pattern STRINGS on
# every call (once per relation, twice for synthetic sub-relations) -- the exact
# anti-pattern the dictionary_ner comment (section 10.4) warns about. Build the
# longest-key-first list of (entity, label, compiled_pattern) ONCE here. Stable
# sort of a dict that is constant from here on => identical iteration order =>
# identical first-match/longest-first result; compiled.search(s) is identical to
# re.search(pattern_str, s) with no flags. Purely a speedup (verified byte-for-byte
# by audit_tooling/perf_2 / verify_lookup_entity_label.py).
_ENTITY_LABEL_LOOKUP = [
    (entity, label, re.compile(r'(?<!\\w)' + re.escape(entity) + r'(?!\\w)'))
    for entity, label in sorted(
        COMBINED_ENTITY_DICTIONARY.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )
]


def lookup_entity_label(phrase, dictionary, exact_only=False):''',
        "1: insert module-level _ENTITY_LABEL_LOOKUP",
    )

    # ---- 2. iterate the precompiled list instead of re-sorting + recompiling ----
    src = apply(
        src,
        '''    # Fallback: a dictionary entry appearing as a whole word inside the
    # object text, e.g. "sekah kangsen di merajan" -> "merajan".
    for entity, label in sorted(
        dictionary.items(),
        key=lambda x: len(x[0]),
        reverse=True
    ):
        pattern = r'(?<!\\w)' + re.escape(entity) + r'(?!\\w)'
        match = re.search(pattern, phrase_lower)
        if not match:
            continue''',
        '''    # Fallback: a dictionary entry appearing as a whole word inside the
    # object text, e.g. "sekah kangsen di merajan" -> "merajan".
    # Iterates the module-level precompiled list (built from
    # COMBINED_ENTITY_DICTIONARY, which is what both call sites pass) in the
    # identical longest-key-first order the old inline sort produced.
    for entity, label, pattern in _ENTITY_LABEL_LOOKUP:
        match = pattern.search(phrase_lower)
        if not match:
            continue''',
        "2: use precompiled _ENTITY_LABEL_LOOKUP in the fallback loop",
    )

    try:
        compile(src, "<cell51-patched-perf2>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    cell["source"] = src.splitlines(keepends=True)
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\nlookup_entity_label patch complete. {len(src) - original_len:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

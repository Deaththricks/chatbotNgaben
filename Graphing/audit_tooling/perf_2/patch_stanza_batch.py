"""
Perf batch 2, patch 2: batch the two Stanza passes (cell 25 POS, cell 42 depparse).

Both pos_tag_sentences (cell 25) and dependency_parsing (cell 42) call nlp(sentence)
once per sentence in a Python loop -- 4,340 calls each, paying full fixed per-call
overhead every time. Replace with a single nlp.bulk_process(list(sentences)) call.

Byte-identical: Stanza's tokenize/mwt/pos/lemma/depparse processors are per-sentence
(BiLSTM / biaffine) with masked padding -- batching across inputs changes no per-token
prediction. Each input string stays its own document, so per-document sentence
splitting (the Sxx.2 sub-sentence case cell 42 handles) is unchanged. tokenize_no_ssplit
is deliberately NOT set. Verified offline by scratchpad/verify_stanza_batch.py
(looped vs batched, token-for-token, on a 420-sentence sample incl. every re-split one).

Idempotent, anchor-guarded string-replace into cell 25 + cell 42 source.
"""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"


def apply(src, old, new, label):
    count = src.count(old)
    if count == 0:
        raise SystemExit(f"[FAIL] anchor not found for: {label}")
    if count > 1:
        raise SystemExit(f"[FAIL] anchor ambiguous ({count} matches) for: {label}")
    print(f"[ok] {label}")
    return src.replace(old, new, 1)


def patch_cell(nb, index, transform):
    cell = nb["cells"][index]
    src = "".join(cell["source"])
    if "bulk_process" in src:
        raise SystemExit(f"[FAIL] cell {index} already patched (bulk_process present)")
    n0 = len(src)
    src = transform(src)
    try:
        compile(src, f"<cell{index}-patched-perf2>", "exec")
    except SyntaxError as e:
        raise SystemExit(f"[FAIL] patched cell {index} SyntaxError: {e}")
    cell["source"] = src.splitlines(keepends=True)
    print(f"[ok] cell {index} compiles cleanly ({len(src) - n0:+d} chars)")


def main():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    # ---- cell 25: pos_tag_sentences ----
    def t25(src):
        return apply(
            src,
            '''    results = []

    for sentence in sentences:

        doc = nlp(sentence)

        sentence_result = []''',
            '''    results = []

    # PERF: one batched call instead of len(sentences) individual nlp() calls.
    # Stanza's tokenize/pos processors are per-sentence with masked padding, so
    # batching changes no per-token prediction; each string stays its own
    # document. Verified byte-for-byte by audit_tooling/perf_2/verify_stanza_batch.py.
    for doc in nlp.bulk_process(list(sentences)):

        sentence_result = []''',
            "cell 25: pos_tag_sentences -> bulk_process",
        )

    # ---- cell 42: dependency_parsing ----
    def t42(src):
        return apply(
            src,
            '''    for sentence_id, sentence in enumerate(
        sentences,
        start=1
    ):

        doc = nlp(sentence)

        # ----------------------------------------------------
        # Stanza does its own internal sentence detection. Almost''',
            '''    # PERF: one batched nlp() call instead of len(sentences) individual calls.
    # Stanza's processors are per-sentence with masked padding so batching
    # changes no per-token prediction, and each string stays its own document so
    # the per-document sentence splitting below (the Sxx.2 sub-sentence case) is
    # unchanged. Verified byte-for-byte by audit_tooling/perf_2/verify_stanza_batch.py.
    for sentence_id, doc in enumerate(
        nlp.bulk_process(list(sentences)),
        start=1
    ):

        # ----------------------------------------------------
        # Stanza does its own internal sentence detection. Almost''',
            "cell 42: dependency_parsing -> bulk_process",
        )

    patch_cell(nb, 25, t25)
    patch_cell(nb, 42, t42)

    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("\nStanza batch patch complete. Notebook written.")


if __name__ == "__main__":
    main()

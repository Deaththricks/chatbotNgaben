"""
Add a Markdown export of the relation-extraction results to the notebook save cell.

New section 14.3c in cell 54: writes
Results/Final/relation_results_ngaben/relation_results_ngaben.md -- one table per
sentence, source context quoted above it. Additive; nothing existing changes.

Idempotent, anchor-guarded string-replace into cell 54 source.
"""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
CELL_INDEX = 54

ANCHOR = '''atomic_write(output_path_rel_txt, write_relation_txt)
print(f"Relation extraction results (txt) saved to {output_path_rel_txt}")

# ----------------------------------
# 14.4. COREFERENCE RESOLUTION'''

NEW = '''atomic_write(output_path_rel_txt, write_relation_txt)
print(f"Relation extraction results (txt) saved to {output_path_rel_txt}")

# ----------------------------------
# 14.3c. RELATION EXTRACTION (Markdown -- one table per
#        sentence with the source context quoted above it,
#        for reading / sharing / pasting into a report)
# ----------------------------------

output_path_rel_md = make_output_path('relation', 'md')


def _md_cell(text):
    """Flatten a value so it can't break a Markdown table row."""
    return str(text).replace('|', r'\\|').replace('\\n', ' ').strip()


def write_relation_md(f):
    n_sent = len({rel['sentence_id'] for rel in sorted_relations})
    f.write("# Ngaben Relation Extraction\\n\\n")
    f.write(f"_{len(sorted_relations)} relations across {n_sent} sentences._\\n\\n")

    current_sid = None
    for rel in sorted_relations:
        sid = rel['sentence_id']

        if sid != current_sid:
            f.write(f"\\n## S{sid}\\n\\n")
            ctx = sentence_lookup.get(sid, '')
            if ctx:
                f.write(f"> {_md_cell(ctx)}\\n\\n")
            f.write("| subject | relation | object | source |\\n")
            f.write("|---|---|---|---|\\n")
            current_sid = sid

        subj = _md_cell(rel['subject'])
        if rel['subject_label']:
            subj += f" _({rel['subject_label']})_"

        obj = _md_cell(rel['object'])
        if rel['object_label']:
            obj += f" _({rel['object_label']})_"

        f.write(f"| {subj} | `{rel['relation']}` | {obj} | {rel['source']} |\\n")

    f.write("\\n")


atomic_write(output_path_rel_md, write_relation_md)
print(f"Relation extraction results (md) saved to {output_path_rel_md}")

# ----------------------------------
# 14.4. COREFERENCE RESOLUTION'''


def main():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)
    cell = nb["cells"][CELL_INDEX]
    src = "".join(cell["source"])
    n0 = len(src)

    if "write_relation_md" in src:
        raise SystemExit("[FAIL] already patched (write_relation_md present)")
    if src.count(ANCHOR) != 1:
        raise SystemExit(f"[FAIL] anchor count = {src.count(ANCHOR)}")

    src = src.replace(ANCHOR, NEW, 1)

    try:
        compile(src, "<cell54-patched-relmd>", "exec")
    except SyntaxError as e:
        raise SystemExit(f"[FAIL] patched cell 54 SyntaxError: {e}")
    print("[ok] patched cell 54 compiles cleanly")

    cell["source"] = src.splitlines(keepends=True)
    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\nrelation .md patch complete. {len(src) - n0:+d} chars. Notebook written.")


if __name__ == "__main__":
    main()

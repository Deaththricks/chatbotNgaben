"""
Iteration 4b: two fixes surfaced by post-run verification of the Iteration 4 batch.

- S2377: its override object contained "sebagaimana asalnya semula" -> the whole row was
  silently dropped by _ATTRIBUTION_OBJECT_PATTERN (which treats "sebagaimana" as a citation
  marker). Reword "sebagaimana" -> "seperti"; drop the literal quotes around "benda bekas".
- S4110: object "pemangku kahyangan tiga setempat" -> lookup_entity_label re-types it
  BANGUNAN_RITUAL via the buried word "kahyangan tiga", overriding the hand-set
  ENTITAS_KEAGAMAAN. Shorten the object to "pemangku" (an exact ENTITAS_KEAGAMAAN dict hit).
"""
import json, re

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"

NEW = {
    2377: [
        {"subject": "ngaben", "subject_label": "RITUAL_KEMATIAN", "relation": "BERTUJUAN_POKOK",
         "object": "merubah jenazah atau benda bekas badan seseorang kembali menjadi pancamahabutha seperti asalnya semula",
         "object_label": None, "source": "manual_override"},
    ],
    4110: [
        {"subject": "sarana dan prasarana (upacara pemujaan)", "subject_label": None, "relation": "BERUPA",
         "object": "pras, ajuman, daksina, suci, rayunan, dan kadang-kadang pajegan",
         "object_label": None, "source": "manual_override"},
        {"subject": "tirtha", "subject_label": "TIRTHA_SUCI", "relation": "DIMOHONKAN_OLEH",
         "object": "pemangku", "object_label": "ENTITAS_KEAGAMAAN", "source": "manual_override"},
    ],
}


def v(x):
    return "None" if x is None else json.dumps(x, ensure_ascii=False)


def render(sid, trips):
    body = "".join(
        '        {"subject": %s, "subject_label": %s, "relation": %s, "object": %s, '
        '"object_label": %s, "source": "manual_override"},\n' % (
            v(t["subject"]), v(t["subject_label"]), v(t["relation"]), v(t["object"]), v(t["object_label"]))
        for t in trips)
    return f"    {sid}: [\n{body}    ],\n"


nb = json.load(open(NB, encoding="utf-8"))
cell = nb["cells"][51]
src = "".join(cell["source"])
n0 = len(src)

for sid, trips in NEW.items():
    m = re.search(rf"\n    {sid}: \[\n.*?\n    \],\n", src, re.S)
    if not m:
        raise SystemExit(f"[FAIL] S{sid} entry not found")
    src = src[:m.start() + 1] + render(sid, trips) + src[m.end():]
    print(f"[ok] replaced S{sid}")

compile(src, "<c51-iter4b>", "exec")
assert "sebagaimana asalnya" not in src
cell["source"] = src.splitlines(keepends=True)
with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"iter4b done. {len(src) - n0:+d} chars.")

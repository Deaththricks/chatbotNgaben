# -*- coding: utf-8 -*-
"""Corrective patch: json.dumps(None) emitted 'null' (JSON) instead of 'None' (Python)
in the Stage-9 batch-1 override/addition data. Fix both occurrence shapes."""
import json

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = nb["cells"][51]["source"]
text = "".join(src) if isinstance(src, list) else src

before = text
n1 = text.count(': null,')
n2 = text.count(': null}')
text = text.replace(': null,', ': None,')
text = text.replace(': null}', ': None}')
n3 = text.count(': null')
assert n3 == 0, f"still {n3} bare 'null' occurrences left"
assert text != before

if isinstance(src, list):
    nb["cells"][51]["source"] = [text]
else:
    nb["cells"][51]["source"] = text

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Fixed {n1} ': null,' and {n2} ': null}}' occurrences.")

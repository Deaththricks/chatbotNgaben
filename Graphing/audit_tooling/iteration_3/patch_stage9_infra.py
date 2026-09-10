"""Stage 9 infra: add MANUAL_RELATION_ADDITIONS (additive, non-destructive) dict
parallel to MANUAL_RELATION_OVERRIDES (all-or-nothing replace). Idempotent."""
import json, sys

NB_PATH = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = nb["cells"][51]["source"]
if isinstance(src, list):
    text = "".join(src)
else:
    text = src

ANCHOR = '''for sentence_id, override_relations in MANUAL_RELATION_OVERRIDES.items():
    for relation in override_relations:
        relation["sentence_id"] = sentence_id
        relations.append(relation)
'''

if "MANUAL_RELATION_ADDITIONS" in text:
    print("Already patched, skipping.")
    sys.exit(0)

assert text.count(ANCHOR) == 1, f"anchor found {text.count(ANCHOR)} times, expected 1"

INSERTION = ANCHOR + '''
# ==========================================
# 13.8c. MANUAL ADDITIONS (Iteration 3, Stage 9)
# ==========================================
# Unlike MANUAL_RELATION_OVERRIDES (all-or-nothing replace -- used for FIX/DROP
# entries where the existing auto-extracted relation(s) for a sentence are wrong
# and get fully replaced, `[]` for a pure drop), this dict is ADDITIVE: it appends
# new relations to a sentence's existing auto-extracted ones without touching them.
# Used for pure-ADD flag.txt entries where the sentence's current relations are
# already correct and only a missing fact needs to be added. Populated per
# flag.txt (Iteration 3 manual audit, S46-S4340). Dedup (13.10b) runs after this,
# so no risk of duplicate relations if an addition happens to coincide with an
# auto-extracted one.
MANUAL_RELATION_ADDITIONS = {
    # sentence_id: [ {subject, subject_label, relation, object, object_label,
    #                 source: "manual_override"}, ... ]
}

for sentence_id, extra_relations in MANUAL_RELATION_ADDITIONS.items():
    for relation in extra_relations:
        relation["sentence_id"] = sentence_id
        relation.setdefault("source", "manual_override")
        relations.append(relation)
'''

new_text = text.replace(ANCHOR, INSERTION, 1)
assert new_text != text

if isinstance(src, list):
    nb["cells"][51]["source"] = [new_text]
else:
    nb["cells"][51]["source"] = new_text

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Patched: MANUAL_RELATION_ADDITIONS infra added.")

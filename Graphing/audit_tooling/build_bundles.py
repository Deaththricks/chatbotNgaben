"""Rebuild per-chunk audit bundles from the current Results/Final relation output.

Run:  python audit_tooling/build_bundles.py
Writes audit_tooling/bundles/chunk_01..08.txt
Each bundle = per sentence: TEXT, NER, CoNLLU PARSE, extracted RELATIONS (indexed).
"""
import json, os, re, math

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASE = os.path.join(REPO, "Results", "Final")
REL = os.path.join(BASE, "relation_results_ngaben", "relation_results_ngaben.json")
CONLLU = os.path.join(BASE, "dependency_results_ngaben", "dependency_results_ngaben.conllu")
NER = os.path.join(BASE, "ner_results_ngaben", "hybrid_ner_results.txt")
OUT = os.path.join(HERE, "bundles")
os.makedirs(OUT, exist_ok=True)

rels = json.load(open(REL, encoding="utf-8"))

from collections import OrderedDict, defaultdict
by_sid = OrderedDict()
for r in rels:
    by_sid.setdefault(r["sentence_id"], []).append(r)

conllu_blocks = {}
cur_id, cur_lines = None, []
for line in open(CONLLU, encoding="utf-8"):
    line = line.rstrip("\n")
    m = re.match(r"# sent_id = S(\d+(?:\.\d+)?)", line)
    if m:
        if cur_id is not None:
            conllu_blocks[cur_id] = "\n".join(cur_lines)
        cur_id, cur_lines = m.group(1), [line]
    elif cur_id is not None:
        cur_lines.append(line)
if cur_id is not None:
    conllu_blocks[cur_id] = "\n".join(cur_lines)

ner_blocks = defaultdict(list)
cur = None
for line in open(NER, encoding="utf-8"):
    line = line.rstrip("\n")
    m = re.match(r"S(\d+(?:\.\d+)?):", line)
    if m:
        cur = m.group(1)
    elif cur and line.startswith("  ") and "->" in line:
        ner_blocks[cur].append(line.strip())

sids = list(by_sid.keys())
print("sentences with relations:", len(sids), " total relations:", len(rels))

def render_sentence(sid):
    recs = by_sid[sid]
    out = [f"### S{sid}", f"TEXT: {recs[0]['context_sentence']}"]
    ner = ner_blocks.get(str(sid), [])
    if ner:
        out.append("NER: " + " | ".join(ner))
    cb = conllu_blocks.get(str(sid))
    if cb:
        out.append("PARSE:")
        out.append(cb)
    out.append("RELATIONS:")
    for i, r in enumerate(recs):
        out.append(f"  [{i}] {r['subject']} ({r.get('subject_label')}) --[{r['relation']}]--> "
                   f"{r['object']} ({r.get('object_label')})  type={r['object_type']} source={r['source']}")
    out.append("")
    return "\n".join(out)

N_CHUNKS = 8
per = math.ceil(len(sids) / N_CHUNKS)
for c in range(N_CHUNKS):
    chunk = sids[c*per:(c+1)*per]
    if not chunk:
        continue
    body = [f"CHUNK {c+1}/{N_CHUNKS} - sentences S{chunk[0]} .. S{chunk[-1]}  ({len(chunk)} sentences)\n"]
    body += [render_sentence(sid) for sid in chunk]
    open(os.path.join(OUT, f"chunk_{c+1:02d}.txt"), "w", encoding="utf-8").write("\n".join(body))
    print(f"chunk {c+1}: S{chunk[0]}..S{chunk[-1]}  {len(chunk)} sentences  "
          f"{sum(len(by_sid[s]) for s in chunk)} relations")

"""
Build the browser knowledge-graph.

Two sources:

  python build_graph.py                  (default)
      from ../relation_results_ngaben.normalized.json -- mirrors the node/edge
      model of ../load_ngaben_to_neo4j.py exactly (ENTITY -> edge, LITERAL ->
      node property, label from *_label, edgeless -> isolated).

  python build_graph.py --source kb
      from ../../kb/output/entities.json + ../../kb/output/relations.jsonl --
      the canonical, entity-resolved knowledge base. Edges carry a confidence
      (HIGH/MED/LOW, shown as opacity); 'broader' links are drawn as
      TERMASUK_JENIS (IS-A).

  python build_graph.py <path.json>      (explicit normalized-format file)

Output: graph_data.js  ->  window.GRAPH_DATA = { nodes, edges, meta }
(a .js assignment, not .json, so index.html loads it straight off the
 filesystem without a web server / CORS).
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE.parent / "relation_results_ngaben.normalized.json"
KB_DIR = HERE.parent.parent / "kb" / "output"
OUTPUT = HERE / "graph_data.js"

KEEP_ONLY_CLEAN = True   # same switch as the Neo4j loader


def clean_ident(s, fallback="Entity"):
    """Cypher-safe identifier -- identical to the loader's helper."""
    out = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    return out or fallback


def build(data):
    rows = [d for d in data if (d["relation"].isupper() if KEEP_ONLY_CLEAN else True)]

    # best-known label per entity name (first non-null wins)
    label = {}
    for d in data:
        s, sl = d["subject"].strip(), d.get("subject_label")
        if sl and s not in label:
            label[s] = clean_ident(sl)
        o, ol = d["object"].strip(), d.get("object_label")
        if ol and o not in label:
            label[o] = clean_ident(ol)

    literals = defaultdict(lambda: defaultdict(list))  # subject -> rel -> [values]
    lit_context = defaultdict(list)                    # subject -> [context rows]
    edges = []
    names = set()

    for d in rows:
        s = d["subject"].strip()
        names.add(s)
        rel = clean_ident(d["relation"])
        if d["object_type"] == "ENTITY":
            o = d["object"].strip()
            names.add(o)
            edges.append({
                "from": s,
                "to": o,
                "rel": rel,
                "raw_relation": d.get("raw_relation"),
                "sentence_id": d.get("sentence_id"),
                "context": d.get("context_sentence", ""),
            })
        else:
            literals[s][rel].append(d["object"].strip())
            lit_context[s].append({
                "rel": rel,
                "value": d["object"].strip(),
                "raw_relation": d.get("raw_relation"),
                "sentence_id": d.get("sentence_id"),
                "context": d.get("context_sentence", ""),
            })

    deg = defaultdict(int)
    for e in edges:
        deg[e["from"]] += 1
        deg[e["to"]] += 1

    nodes = []
    for name in sorted(names):
        nodes.append({
            "id": name,
            "label": name,
            "type": label.get(name, "Entity"),
            "degree": deg[name],
            "isolated": deg[name] == 0,
            "literals": {rel: vals for rel, vals in literals.get(name, {}).items()},
            "literal_rows": lit_context.get(name, []),
        })

    rel_counts = defaultdict(int)
    for e in edges:
        rel_counts[e["rel"]] += 1
    type_counts = defaultdict(int)
    for n in nodes:
        type_counts[n["type"]] += 1

    meta = {
        "input": str(DEFAULT_INPUT.name),
        "rows_total": len(data),
        "rows_kept": len(rows),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "isolated_count": sum(1 for n in nodes if n["isolated"]),
        "literal_value_count": sum(len(v) for d in literals.values() for v in d.values()),
        "relation_types": dict(sorted(rel_counts.items(), key=lambda kv: -kv[1])),
        "node_types": dict(sorted(type_counts.items(), key=lambda kv: -kv[1])),
    }

    return {"nodes": nodes, "edges": edges, "meta": meta}


def _read_jsonl(path):
    blocks = path.read_text(encoding="utf-8").split("\n\n")
    return [json.loads(b) for b in blocks if b.strip()]


def build_from_kb():
    """Graph from the canonical KB (kb/output/entities.json + kb/output/relations.jsonl)."""
    ents = json.loads((KB_DIR / "entities.json").read_text(encoding="utf-8"))
    rels = _read_jsonl(KB_DIR / "relations.jsonl")
    ent_ids = {e["id"] for e in ents}

    edges = []
    for r in rels:
        if r["subject_id"] not in ent_ids or r["object_id"] not in ent_ids:
            continue
        edges.append({
            "from": r["subject_id"], "to": r["object_id"],
            "rel": r["predicate"], "raw_relation": r.get("raw_relation"),
            "sentence_id": r["provenance"]["sentence_id"],
            "context": r["provenance"]["context_sentence"],
            "confidence": r["confidence"],
        })
    for e in ents:
        if e.get("broader") in ent_ids:
            edges.append({"from": e["id"], "to": e["broader"],
                          "rel": "TERMASUK_JENIS", "raw_relation": None,
                          "sentence_id": None, "context": "", "confidence": "HIGH"})

    deg = defaultdict(int)
    for e in edges:
        deg[e["from"]] += 1
        deg[e["to"]] += 1

    nodes = []
    for e in ents:
        lit, rows = {}, []
        if e.get("definition"):
            rows.append({"rel": "DEFINISI", "value": e["definition"],
                         "raw_relation": None, "sentence_id": None, "context": ""})
            lit["DEFINISI"] = [e["definition"]]
        for rel, items in e.get("attributes", {}).items():
            lit[rel] = [it["value"] for it in items]
            for it in items:
                rows.append({"rel": rel, "value": it["value"], "raw_relation": None,
                             "sentence_id": it.get("sentence_id"), "context": ""})
        nodes.append({
            "id": e["id"], "label": e["name"], "type": e["type"],
            "degree": deg[e["id"]], "isolated": deg[e["id"]] == 0,
            "literals": lit, "literal_rows": rows,
        })

    rel_counts, type_counts = defaultdict(int), defaultdict(int)
    for e in edges:
        rel_counts[e["rel"]] += 1
    for n in nodes:
        type_counts[n["type"]] += 1
    meta = {
        "input": "kb/output/entities.json + kb/output/relations.jsonl",
        "rows_total": len(rels), "rows_kept": len(rels),
        "node_count": len(nodes), "edge_count": len(edges),
        "isolated_count": sum(1 for n in nodes if n["isolated"]),
        "literal_value_count": sum(len(v) for n in nodes for v in n["literals"].values()),
        "relation_types": dict(sorted(rel_counts.items(), key=lambda kv: -kv[1])),
        "node_types": dict(sorted(type_counts.items(), key=lambda kv: -kv[1])),
        "confidence_counts": dict(Counter(e.get("confidence") for e in edges)),
    }
    return {"nodes": nodes, "edges": edges, "meta": meta}


def main():
    args = sys.argv[1:]
    if args and args[0] == "--source" and len(args) > 1 and args[1] == "kb":
        graph = build_from_kb()
        src = "kb/"
    else:
        src = Path(args[0]) if args else DEFAULT_INPUT
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
        graph = build(data)

    payload = json.dumps(graph, ensure_ascii=False, indent=2)
    OUTPUT.write_text("window.GRAPH_DATA = " + payload + ";\n", encoding="utf-8")

    m = graph["meta"]
    print("=" * 70)
    print("KNOWLEDGE GRAPH BUILD")
    print("=" * 70)
    print(f"input : {src}")
    print(f"output: {OUTPUT.name}")
    print()
    print(f"rows kept            : {m['rows_kept']} / {m['rows_total']}")
    print(f"nodes               : {m['node_count']}  ({m['isolated_count']} isolated)")
    print(f"edges               : {m['edge_count']}")
    print(f"literal values      : {m['literal_value_count']}")
    print(f"relation types      : {len(m['relation_types'])}")
    print(f"node types          : {len(m['node_types'])}")
    if "confidence_counts" in m:
        print(f"edge confidence     : {m['confidence_counts']}")
    print()
    print("relations : " + ", ".join(m["relation_types"]))
    print("node types: " + ", ".join(m["node_types"]))
    print()
    print(f"wrote {OUTPUT}")
    print("open index.html in a browser to view.")


if __name__ == "__main__":
    main()

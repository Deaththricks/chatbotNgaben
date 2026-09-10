"""
Load Ngaben relation-extraction results into Neo4j.

What it does:
  - ENTITY-target relations  -> a line (relationship) between two dots (nodes)
  - LITERAL-target relations -> a value stored as a property ON the subject dot
                                (kept as a list, so multiple literals of the same
                                 relation type don't overwrite each other)
  - each dot gets a label from subject_label / object_label (default :Entity)
  - base label on every dot is :Node; edgeless dots also get :Isolated

Before running:
  1. pip install neo4j python-dotenv
  2. start your Neo4j database
  3. copy .env.example to .env and fill in NEO4J_PASSWORD (and the rest if needed)
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# ---- settings (from .env, with dev defaults) ------------------------------
URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER     = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")
JSON_PATH = os.getenv("JSON_PATH", "relation_results_ngaben.normalized.json")  # output of normalize.py

if not PASSWORD:
    sys.exit("NEO4J_PASSWORD is not set. Copy .env.example to .env and fill it in.")

# True  = load only clean UPPERCASE relation types (recommended first pass)
# False = load everything, including any messy lowercase parser-verbs
KEEP_ONLY_CLEAN = True

# True = delete every node/relationship first, so a re-run rebuilds from scratch.
# Leave this on: the loader only MERGEs (never deletes), so without a wipe an
# earlier build's edges (e.g. an older relation taxonomy) survive and you get
# doubled relationships in the exported graph.
WIPE_FIRST = True

# True = mark nodes that end up with no relationship as :Isolated, so the graph
# export query can leave them out (see the query in the comments below).
TAG_ISOLATED = True
# ---------------------------------------------------------------------------


def clean_ident(s, fallback="Entity"):
    """Make a Cypher-safe identifier (for relationship types and labels)."""
    out = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').upper()
    return out or fallback


def build(data):
    """Turn the raw rows into: node labels, literal properties, and entity edges."""
    rows = [d for d in data if (d['relation'].isupper() if KEEP_ONLY_CLEAN else True)]

    # best-known label for each entity name (prefer the first non-null we see)
    label = {}
    for d in data:
        s, sl = d['subject'].strip(), d.get('subject_label')
        if sl and s not in label:
            label[s] = clean_ident(sl)
        # an object gets a label whether it becomes its own dot (ENTITY) or a
        # property on the subject (LITERAL) -- normalize.py may attach a label
        # to a literal too.
        o, ol = d['object'].strip(), d.get('object_label')
        if ol and o not in label:
            label[o] = clean_ident(ol)

    literals = defaultdict(lambda: defaultdict(list))  # subject -> relation -> [values]
    edges = []                                         # (subject, REL, object)
    names = set()

    for d in rows:
        s = d['subject'].strip()
        names.add(s)
        rel = clean_ident(d['relation'])
        if d['object_type'] == 'ENTITY':
            o = d['object'].strip()
            names.add(o)
            edges.append((s, rel, o))
        else:
            literals[s][rel].append(d['object'].strip())

    return names, label, literals, edges


def load(tx_data):
    names, label, literals, edges = tx_data
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        if WIPE_FIRST:
            session.run("MATCH (n) DETACH DELETE n")
            print("wiped existing graph")

        # a uniqueness constraint doubles as an index -> fast MERGE on name
        session.run("CREATE CONSTRAINT IF NOT EXISTS "
                    "FOR (n:Node) REQUIRE n.name IS UNIQUE")

        # 1) create every dot, with its label + any literal properties
        for name in names:
            lbl = label.get(name, "Entity")
            props = {rel: vals for rel, vals in literals.get(name, {}).items()}
            session.run(
                f"MERGE (n:Node:{lbl} {{name: $name}}) SET n += $props",
                name=name, props=props,
            )

        # 2) draw every dot->dot line
        for s, rel, o in edges:
            session.run(
                f"MATCH (a:Node {{name: $s}}) "
                f"MATCH (b:Node {{name: $o}}) "
                f"MERGE (a)-[:{rel}]->(b)",
                s=s, o=o,
            )

        # 3) tag dots with no line as :Isolated (subjects that only have
        #    LITERAL relations -> everything they say is stored as a property).
        #    Exclude them from the export with:
        #      MATCH (n:Node) WHERE NOT n:Isolated
        #      OPTIONAL MATCH (n)-[r]-(m:Node) WHERE NOT m:Isolated
        #      RETURN n, r, m
        if TAG_ISOLATED:
            res = session.run(
                "MATCH (n:Node) WHERE NOT (n)--() SET n:Isolated RETURN count(n) AS c"
            )
            print(f"tagged {res.single()['c']} isolated nodes as :Isolated")

    driver.close()
    print(f"done: {len(names)} nodes, {len(edges)} relationships, "
          f"{sum(len(v) for d in literals.values() for v in d.values())} literal values")


def load_kb():
    """Load the canonical KB (../kb/entities.json + relations.jsonl) instead.

    node label = entity type; base label :Node; edgeless -> :Isolated.
    'broader' -> (a)-[:TERMASUK_JENIS]->(b).  relation edges carry
    {confidence, raw_relation, sentence_id} as properties -- filter a clean
    view with  WHERE r.confidence <> 'LOW'.
    """
    kb = Path(__file__).resolve().parent.parent / "kb"
    ents = json.loads((kb / "entities.json").read_text(encoding="utf-8"))
    rels = [json.loads(b) for b in
            (kb / "relations.jsonl").read_text(encoding="utf-8").split("\n\n") if b.strip()]
    ids = {e["id"] for e in ents}

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        if WIPE_FIRST:
            session.run("MATCH (n) DETACH DELETE n")
            print("wiped existing graph")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE")

        for e in ents:
            lbl = clean_ident(e.get("type") or "Entity")
            props = {"id": e["id"], "name": e["name"]}
            if e.get("definition"):
                props["definition"] = e["definition"]
            for rel, items in e.get("attributes", {}).items():
                props[rel] = [it["value"] for it in items]
            session.run(f"MERGE (n:Node:{lbl} {{id: $id}}) SET n += $props",
                        id=e["id"], props=props)

        for e in ents:
            if e.get("broader") in ids:
                session.run("MATCH (a:Node {id:$a}) MATCH (b:Node {id:$b}) "
                            "MERGE (a)-[:TERMASUK_JENIS]->(b)", a=e["id"], b=e["broader"])

        n_edges = 0
        for r in rels:
            if r["subject_id"] not in ids or r["object_id"] not in ids:
                continue
            rt = clean_ident(r["predicate"])
            session.run(
                f"MATCH (a:Node {{id:$s}}) MATCH (b:Node {{id:$o}}) "
                f"MERGE (a)-[x:{rt}]->(b) "
                f"SET x.confidence=$c, x.raw_relation=$rr, x.sentence_id=$sid",
                s=r["subject_id"], o=r["object_id"], c=r["confidence"],
                rr=r.get("raw_relation"), sid=r["provenance"]["sentence_id"])
            n_edges += 1

        if TAG_ISOLATED:
            res = session.run("MATCH (n:Node) WHERE NOT (n)--() SET n:Isolated "
                              "RETURN count(n) AS c")
            print(f"tagged {res.single()['c']} isolated nodes as :Isolated")
    driver.close()
    print(f"done (kb): {len(ents)} nodes, {n_edges} relation edges + broader spine")


if __name__ == "__main__":
    if "--source" in sys.argv and "kb" in sys.argv:
        load_kb()
    else:
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        load(build(data))

"""
Load Ngaben relation-extraction results into Neo4j.

    python load_ngaben_to_neo4j.py              # the KB the chatbot reads (= --source kb)
    python load_ngaben_to_neo4j.py --source raw # old name-keyed view, see below

--source kb loads ../kb/output (see load_kb). --source raw loads the normalized
relation rows directly, as described next -- its nodes have no `id`, so the chatbot
finds nothing in that graph; it is only a raw-extraction view.

What --source raw does:
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

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase

# .env lives at the repo root; find it regardless of where this script is run from
load_dotenv(find_dotenv())

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


_CONF_RANK = {"HIGH": 0, "MED": 1, "LOW": 2}


def load_kb():
    """Load the canonical KB (../kb/output/entities.json + relations.jsonl) -- the graph
    the chatbot queries.

    node label = entity type; base label :Node; edgeless -> :Isolated.
    'broader' -> (a)-[:TERMASUK_JENIS]->(b).  relation edges carry
    {confidence, raw_relation, sentence_id} as properties -- filter a clean
    view with  WHERE r.confidence <> 'LOW'. A regional-variant row also sets
    {variant_region, variant_op, variant_source, variant_replaces}.

    A (subject, predicate, object) that occurs more than once becomes one edge with the
    BEST confidence among its rows, a main-version row beating a variant row. It used to
    be MERGE + SET per row, so the last row won: a LOW duplicate loaded last would have
    hidden a HIGH edge from the bot.
    Writes are batched with UNWIND (one query per label / relation type, not per row).
    """
    kb = Path(__file__).resolve().parent.parent / "kb" / "output"
    ents = json.loads((kb / "entities.json").read_text(encoding="utf-8"))
    rels = [json.loads(b) for b in
            (kb / "relations.jsonl").read_text(encoding="utf-8").split("\n\n") if b.strip()]
    ids = {e["id"] for e in ents}

    nodes_by_label = defaultdict(list)
    for e in ents:
        props = {"id": e["id"], "name": e["name"]}
        if e.get("definition"):
            props["definition"] = e["definition"]
        if e.get("aliases"):
            props["aliases"] = e["aliases"]
        for rel, items in e.get("attributes", {}).items():
            props[rel] = [it["value"] for it in items]
        nodes_by_label[clean_ident(e.get("type") or "Entity")].append({"id": e["id"], "props": props})

    spine = [{"a": e["id"], "b": e["broader"]} for e in ents if e.get("broader") in ids]

    best = {}
    for r in rels:
        if r["subject_id"] not in ids or r["object_id"] not in ids:
            continue
        key = (r["subject_id"], clean_ident(r["predicate"]), r["object_id"])
        rank = (_CONF_RANK.get(r["confidence"], 3), "variant" in r)
        if key not in best or rank < (_CONF_RANK.get(best[key]["confidence"], 3), "variant" in best[key]):
            best[key] = r
    edges_by_type = defaultdict(list)
    for (s, rt, o), r in best.items():
        v = r.get("variant") or {}
        edges_by_type[rt].append({"s": s, "o": o, "c": r["confidence"], "rr": r.get("raw_relation"),
                                  "sid": r["provenance"]["sentence_id"],
                                  "vr": v.get("region"), "vo": v.get("op"), "vs": v.get("source"),
                                  "vx": v.get("replaces")})

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        if WIPE_FIRST:
            session.run("MATCH (n) DETACH DELETE n")
            print("wiped existing graph")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE")

        for lbl, rows in nodes_by_label.items():
            session.run(f"UNWIND $rows AS row MERGE (n:Node:{lbl} {{id: row.id}}) SET n += row.props",
                        rows=rows)

        session.run("UNWIND $rows AS row MATCH (a:Node {id: row.a}) MATCH (b:Node {id: row.b}) "
                    "MERGE (a)-[:TERMASUK_JENIS]->(b)", rows=spine)

        for rt, rows in edges_by_type.items():
            session.run(f"UNWIND $rows AS row MATCH (a:Node {{id: row.s}}) MATCH (b:Node {{id: row.o}}) "
                        f"MERGE (a)-[x:{rt}]->(b) "
                        f"SET x.confidence = row.c, x.raw_relation = row.rr, x.sentence_id = row.sid, "
                        f"x.variant_region = row.vr, x.variant_op = row.vo, x.variant_source = row.vs, "
                        f"x.variant_replaces = row.vx",
                        rows=rows)
        n_edges = sum(len(v) for v in edges_by_type.values())

        if TAG_ISOLATED:
            res = session.run("MATCH (n:Node) WHERE NOT (n)--() SET n:Isolated "
                              "RETURN count(n) AS c")
            print(f"tagged {res.single()['c']} isolated nodes as :Isolated")
    driver.close()
    print(f"done (kb): {len(ents)} nodes, {n_edges} relation edges + {len(spine)} broader links")


if __name__ == "__main__":
    # --source kb (the default) loads the KB the chatbot reads. --source raw is the old
    # name-keyed load of relation_results_ngaben.normalized.json: its nodes have no `id`,
    # so after it every bot query finds nothing. It used to be the default -- running the
    # script without arguments silently broke the bot (2026-09-30).
    source = sys.argv[sys.argv.index("--source") + 1] if "--source" in sys.argv[:-1] else "kb"
    if source == "kb":
        load_kb()
    elif source == "raw":
        print("WARNING: --source raw builds a graph the chatbot cannot query (no node ids).")
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        load(build(data))
    else:
        sys.exit(f"unknown --source {source!r} (use kb or raw)")

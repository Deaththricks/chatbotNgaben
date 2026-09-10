# Ngaben Knowledge Graph â€” Inventory (Phase A)

*What the chatbot will have to work with. Written 2026-09-09 from a read-only
survey of `C:\Misc\Work\AI_Chatbot\Graphing\kb\`, `C:\Misc\Work\AI_Chatbot\Graphing\Neo4\`, `C:\Misc\Work\AI_Chatbot\Graphing\Data\`.*

---

## 1. There are TWO possible graphs. Use the KB one.

Your loader `Neo4/load_ngaben_to_neo4j.py` can build either:

| | **default** (`python load_ngaben_to_neo4j.py`) | **KB** (`python load_ngaben_to_neo4j.py --source kb`) |
|---|---|---|
| Source | `relation_results_ngaben.normalized.json` | `kb/entities.json` + `kb/relations.jsonl` |
| Nodes | ~540, keyed by raw `name` string | **485 canonical entities**, keyed by `id` |
| Entity resolution | none â€” spelling variants are separate nodes | yes â€” aliases merged, synonyms merged, typed |
| Definitions | no | 72 entities carry a `definition` |
| IS-A spine | no | 106 `:TERMASUK_JENIS` links (e.g. `tirtha pangentas` â†’ `tirtha`) |
| Edge confidence | no | every edge has `confidence` = HIGH/MED/LOW |
| Node properties | 579 literal facts as list-props | 175 entities have `attributes` (list-props) |

**â†’ The chatbot should run on the KB graph.** It's the entity-resolved,
deduplicated, typed one. Everything below describes that graph.

---

## 2. Node shape

Every node: base label `:Node` + one type label. Keyed by `id` (snake_case of the name).

```
(:Node:SARANA_RITUAL {
    id: "abu",
    name: "abu",
    definition: null,                       // only 72/485 have one
    BERUBAH_DARI: ["bekas benda badan linggasarira"],   // <- attributes,
    DIHANYUTKAN_KE: ["sungai"],                          //    flattened onto
    DIMASUKKAN_KE_DALAM: ["klungah nyuh gading ..."]     //    the node as props
})
```

Also present on some nodes: `aliases` is **not** loaded as a property by the
current loader (it lives only in `entities.json`) â€” see gap #2 in Â§6.

### Node type labels (count)

| label | n | what it is |
|---|---|---|
| `SARANA_RITUAL` | 139 | ritual implements & offerings (banten, tirtha, sarana) |
| `ISTILAH_UMUM_RITUAL` | 111 | general ritual terminology |
| `TAHAPAN_UPACARA` | 42 | stages / sub-ceremonies (nganyut, ngeseng, â€¦) |
| `KONSEP_FILOSOFIS` | 38 | philosophical concepts (atma, moksha, â€¦) |
| `BANGUNAN_RITUAL` | 37 | ritual structures (bale, bade, â€¦) |
| `ENTITAS_KEAGAMAAN` | 32 | deities / religious beings |
| `RITUAL_KEMATIAN` | 32 | death-rite names |
| `TIRTHA_SUCI` | 20 | holy-water types |
| `KONSEP_HUKUM_ADAT` | 20 | customary-law concepts |
| `NASKAH_SUCI` | 4 | sacred texts / lontar |
| `RITUAL` / `STRUKTUR_SOSIAL_ADAT` / `Place` / `AGAMA` | 4/3/2/1 | small tails |

> 286 of the 485 entities are `resolve_method: "unresolved"` â€” kept as their own
> node, type by majority vote. Many are fine; some are fragments. 8 flagged
> fragments are in `review_queue.jsonl`.

---

## 3. Edge shape

```
(a:Node)-[:BAGIAN_DARI {
    confidence: "HIGH",
    raw_relation: "BAGIAN_DARI",
    sentence_id: 16
}]->(b:Node)
```

- **324 edges total** â€” HIGH **68**, MED **212**, LOW **44**.
- **280 are non-LOW** â€” the usable set. Always query `WHERE r.confidence <> 'LOW'`.
- Plus the **106 `:TERMASUK_JENIS`** IS-A edges (from `broader`; no confidence prop).

### Predicate vocabulary (~90 types; top ones)

| predicate | n | HIGH | reads as |
|---|---|---|---|
| `ADALAH` | 31 | 10 | X is (a) Y |
| `DILETAKKAN_DI` | 27 | 15 | X is placed on/at Y |
| `BERADA_DI` | 24 | 7 | X is located at Y |
| `DIKENAL_SEBAGAI` | 15 | 4 | X is also known as Y |
| `BERUPA` | 10 | 0 | X takes the form of Y |
| `TERDIRI_DARI` | 9 | 3 | X consists of Y |
| `BAGIAN_DARI` | 7 | 3 | X is part of Y |
| `DIPAKAI_UNTUK` | 6 | 4 | X is used for Y |
| `DIPERSEMBAHKAN_KEPADA` | 4 | 1 | X is offered to Y |
| `DIBUNGKUS_DENGAN` | 4 | 3 | X is wrapped in Y |
| â€¦ ~80 more, mostly 1â€“3 uses each | | | long tail of voiced verbs |

The vocabulary is controlled by `Neo4/relation_map.json` + `normalize.py`
(`CANONICAL_RELATIONS`). It is Indonesian, UPPERCASE, snake_case.

---

## 4. The reliable layer is text, not edges

From `kb/METHODOLOGY.md`, stated plainly:

> The relation extractor is dependency-rule based and **gets ~1 edge in 4 wrong**
> (direction or predicate). The confidence layer + review queue contain that; it
> is not fixed at source. `passages.jsonl` is verbatim source text and has no
> such problem â€” it is the reliable layer.

So the trust ranking for answering questions is:

1. **`entities.json` definitions + type + aliases + `broader`** â€” solid, curated.
2. **HIGH-confidence edges (68)** â€” good.
3. **`passages.jsonl` (478 chunks, incl. 7 glossary + 5 FAQ)** â€” verbatim, reliable, but it's *text*, not graph.
4. **MED edges (212)** â€” spot-check before relying.
5. **LOW edges (44)** â€” don't use; they're in the review queue.

**Implication for a "knowledge-graph-only" chatbot:** the graph's *entity* layer
is strong (what is X, what type is X, what is X also called, what are the
subtypes of X). Its *relationship* layer is thin and noisy â€” 68 HIGH edges
across 90 predicates means most "how is X related to Y" questions have either no
edge or a shaky one. See Â§5 for what this means for intent design.

---

## 5. What questions this graph can actually answer

### Strong (entity-centric â€” answer straight from the graph)

| user asks | Cypher shape |
|---|---|
| "apa itu **ngaben**" | node by id/alias â†’ `definition`, `type`, `aliases`, `broader` |
| "**tirtha** ada jenis apa saja" | `(x)<-[:TERMASUK_JENIS]-(sub)` |
| "**tirtha pangentas** itu termasuk apa" | `(x)-[:TERMASUK_JENIS]->(parent)` |
| "sebutkan **sarana ritual** dalam ngaben" | `MATCH (n:SARANA_RITUAL) RETURN n.name` (139 â€” needs paging/topic filter) |
| "**abu** dihanyutkan ke mana" | node attribute `DIHANYUTKAN_KE` |
| "apa beda **X** dan **Y**" | two nodes â†’ compare `type`, `definition`, `broader`, shared neighbours |

### Medium (needs HIGH/MED edges â€” answerable but verify)

| "**ngaben** bagian dari apa" | `(ngaben)-[:BAGIAN_DARI {confidence:'HIGH'}]->()` â†’ pitra yadnya âœ… |
| "apa yang **dipersembahkan kepada** leluhur" | `()-[:DIPERSEMBAHKAN_KEPADA]->(leluhur)` (only 4 edges total) |
| "**nganyut** melambangkan apa" | MED edge â†’ "pelepasan terakhir menuju moksha" |

### Weak / not supported by the graph

- Anything procedural / sequential ("what are the steps of ngaben, in order") â€”
  `TAHAPAN_UPACARA` nodes exist but they are **not chained**; no `DIIKUTI_OLEH`
  ordering survived. This would come from **passages**, not the graph.
- "why" / explanatory questions â€” definitions are short; the depth is in passages.
- Numbers, dates, cost, regional variation â€” live in passage prose only.

---

## 6. Gaps to close before/while building (Phase Câ€“D input)

1. **No Neo4j password convention.** Credentials now come from `.env`
   (`NEO4J_PASSWORD`) via `python-dotenv`; see `.env.example`.
2. **`aliases` aren't queryable in the graph.** The loader drops them. Either
   (a) add `SET n.aliases = $aliases` to `load_kb()`, or (b) have the chatbot
   load `entities.json` alongside Neo4j and resolve the user's wording to an
   `id` in Python before querying (mirrors the Bali example's `fuzzy_match_*`).
   â†’ **(b) is closer to the example and needs no loader change.**
3. **286 unresolved entities** inflate `MATCH (n:TYPE)` list answers with
   fragments. For list-type intents, filter `WHERE n.definition IS NOT NULL` or
   `WHERE size(keys(n)) > 3`, or curate a whitelist per topic.
4. **No `:Ngaben` hub node with structured attributes** like the Bali example's
   `Upacara` nodes had. The Ngaben graph is a *term network about one ritual*,
   not a *catalogue of many rituals*. The chatbot's unit is "a ritual term,"
   not "a ceremony." Intents must reflect that (glossary + relationship
   explorer), not the Bali example's per-ceremony intents.
5. **Procedural questions need passages.** If step-by-step answers are in scope,
   you can't stay pure-graph â€” you'd pull `passages.jsonl` chunks by
   `section_path`. Decide with your supervisor whether that counts as "still a
   graph chatbot" or is out of scope.

---

## 7. Recommended graph queries to smoke-test (once loaded with `--source kb`)

```cypher
// how big is it
MATCH (n:Node) RETURN count(n);                         // ~485
MATCH ()-[r]->() RETURN type(r) AS rel, count(*) ORDER BY count(*) DESC;

// the entity layer works
MATCH (n:Node) WHERE n.definition IS NOT NULL RETURN n.name, n.definition LIMIT 20;

// the IS-A spine
MATCH (a)-[:TERMASUK_JENIS]->(b) RETURN a.name, b.name LIMIT 20;

// clean relationship view
MATCH (a)-[r]->(b) WHERE r.confidence = 'HIGH'
RETURN a.name, type(r), b.name;                          // 68 rows â€” read them all

// what's connected to the central concept
MATCH (n:Node {id:'ngaben'})-[r]-(m) RETURN type(r), m.name, r.confidence;
```

---

## Bottom line

- **Load with `--source kb`.** 485 entities, 280 usable edges, 106 IS-A links.
- **The entity layer is strong; the relationship layer is thin and ~25% noisy.**
- **Design the chatbot as a glossary + relationship explorer over Ngaben
  terminology** â€” not a clone of the Bali example's per-ceremony structure.
- **Decide with your supervisor** whether procedural/explanatory answers (which
  need `passages.jsonl`, i.e. a RAG touch) are in scope. If strictly graph-only,
  scope the bot to: define a term, classify a term, list terms of a type,
  compare two terms, and report a term's HIGH-confidence relations.

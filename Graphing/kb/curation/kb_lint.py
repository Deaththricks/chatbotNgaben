"""
kb_lint.py -- hard quality gate for the Ngaben KB. Read-only.

Why this exists (2026-09-24): earlier curation passes each fixed the entities the
user happened to report, then declared "done" from counts that could not see the
rest of the same bug class -- e.g. "0 undefined entities" said nothing about terms
that only appear *inside* definitions (Tri Loka, Bhur Loka, Bhuta Kala, Panca
Budhindrya, Dewa Surya ...), which the bot then mentions but cannot explain. The
user kept finding new instances of old bug classes. This script checks the whole
KB for every class at once and exits non-zero while any unwaived violation
remains, so "done" means the class is closed, not that the reported examples are.

Checks (BLOCKING -- each must be fixed or waived with a reason):
  1 names       entity name hygiene: no underscores, no ( ) , /, no conjunction-
                joined pairs ("x atau y"), no clause/deictic fragments
                ("... tersebut", "setelah ...", "satu dua ..."), <= 4 words
  2 definitions every entity has one; not an auto-derived clause from a single
                corpus sentence (curated out-of-band rows, sentence_id >= 900000,
                are fine); a leading "X adalah ..." names this entity
  3 isolated    every entity has >= 1 live edge or broader link
  4 closure     every capitalized term used inside any definition resolves via
                kb_resolver exact / alias / force_merge / strip / orthographic
                (fuzzy does NOT count) -- "every term the bot can say is a term
                the bot can explain"
  5 groups      a numeral-set name (tri/catur/panca/... + noun) has >= 2 linked
                members; "salah satu ... <X>" in a definition implies a link to X
  6 broader     every TERMASUK_JENIS (is-a) pair is either the plain "<parent>
                <qualifier>" naming shape with matching types, or reviewed
  7 edges       no self-loops
  8 config      force_merge targets are existing entity *names* (not ids);
                exclude_from_resolution is empty (trash gets fixed, not hidden)
  9 resolver    every entity name / alias resolves back to that same entity
  10 composition  what a node is made of / contains / comes with is an edge to a
                defined node, never only a text property the bot cannot see
  11 attributes  every text-only attribute (LITERAL fact) is one the bot may show:
                its predicate is in a kb_content.PREDICATE_FAMILIES question aspect
                (else it can never be shown), and its value is not junk -- no
                deictic reference (tersebut / itu / ini / beliau / demikian / "nya"
                split off), no vague head (beberapa / berbagai / tertentu / khusus
                ...), no one-word value after a verb that says nothing by itself
                (MEMILIKI / MEMPEROLEH / BERPERAN_SEBAGAI / MENJADI / MEMEGANG).
                Waiver key: "<entity_id>:<PRED>:<value>"
  12 stages     BAGIAN_DARI into a ritual / stage node is "a stage of" to the bot
                (the tahapan question aspect), so its subject must be a ritual /
                stage too -- a tool or building used in the ritual is DIGUNAKAN_DALAM
  13 genus      the head term a definition files the entity under ("X adalah
                [nama sebuah] <genus> ...") is linked to it by an edge or broader,
                when that head term is itself an entity -- yama purwana tattwa
                "adalah nama sebuah lontar" had no link to lontar.
                Waiver key: "<entity_id>><genus_id>"

WARN (listed for review, never blocks): "Dalam konteks Ngaben" boilerplate,
duplicate edges, very long definitions.

Waivers: ../tuning/lint_waivers.json -- one section per check, {key: reason}.
Every judgment call is recorded once there, with its reason, and never
re-litigated. An empty reason is itself a violation.

Run (from Graphing/kb/curation/, with the bot venv -- kb_resolver needs
rapidfuzz):
    ..\\..\\..\\Chatbot\\rasa_bot\\Scripts\\python.exe kb_lint.py
Reads:  ../output/entities.json, ../output/relations.jsonl,
        ../tuning/entity_resolution.json, ../tuning/lint_waivers.json
Writes: ./kb_lint_report.md
Exit:   0 if no unwaived violation, else 1.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent
ENTITIES = KB / "output" / "entities.json"
RELATIONS = KB / "output" / "relations.jsonl"
RESOLUTION = KB / "tuning" / "entity_resolution.json"
WAIVERS = KB / "tuning" / "lint_waivers.json"
OUT = HERE / "kb_lint_report.md"

sys.path.insert(0, str(KB.parent.parent / "Chatbot" / "bot"))
from kb_content import PREDICATE_FAMILIES  # noqa: E402
from kb_resolver import KbResolver  # noqa: E402

NUMERAL_PREFIXES = {"eka", "dwi", "tri", "catur", "panca", "sad", "sapta", "asta",
                    "nawa", "dasa"}
JOIN_WORDS = re.compile(r"\b(atau|dan|serta|untuk|dengan|di|ke|istilah|kata)\b")
FRAGMENT_WORDS = re.compile(
    r"\b(tersebut|sebelum|sesudah|setelah|semua|setiap|segenap|berbagai|kelak|"
    r"tadi|ini|itu|menggunakan|dimasukkan|dipindahkan|dipercikkan)\b|^satu dua\b")
# Capitalized-term candidates inside definitions. Leading/trailing words that
# only situate a term ("Tri Loka Hindu", "Dalam ...") are peeled before lookup.
CAP_SEQ = re.compile(r"[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,4}")
PEEL = {"hindu", "bali", "jawa", "sanskerta", "kuno", "dalam", "menurut", "ajaran",
        "agama", "tradisi", "konsep", "kosmologi", "sistem"}
MEMBER_IN = {"TERMASUK_JENIS", "BAGIAN_DARI"}
MEMBER_OUT = {"TERDIRI_DARI", "BERUPA", "MELIPUTI", "BERUNSUR", "MEMILIKI_JENIS"}
# Parents whose "children" are usually parts/items used ON them, not kinds OF
# them -- every broader pair under these needs an explicit review.
PART_PARENTS = {"jenazah", "sawa", "layon", "mendiang", "bade", "pepaga", "kajang",
                "pangringkes", "pengawak", "galar", "kawangen", "kawangen_jeriji",
                "tirtha", "lembu", "singa", "manah", "shiwa"}
NON_FUZZY = {"exact", "alias", "force_merge", "strip", "ortho"}
COMPOSITION = {"BERUPA", "TERDIRI_DARI", "BERISI", "DIISI_DENGAN", "BERUNSUR", "MELIPUTI",
               "DILENGKAPI", "TERBUAT_DARI", "DISERTAI", "MEMILIKI_JENIS"}
ASPECT_PREDICATES = set().union(*PREDICATE_FAMILIES.values())
ATTR_DEICTIC = re.compile(r"\b(tersebut|itu|ini|tadi|beliau|demikian|bersangkutan|diatas|nya)\b"
                          r"|disebut di atas", re.I)
ATTR_VAGUE_HEAD = re.compile(r"^(beberapa|berbagai|bermacam|tertentu|khusus|sangat|hal-hal|lain(nya)?)\b", re.I)
LIGHT_VERBS = {"MEMILIKI", "MEMPEROLEH", "BERPERAN_SEBAGAI", "MENJADI", "MEMEGANG"}
STAGE_TYPES = {"TAHAPAN_UPACARA", "RITUAL_KEMATIAN", "RITUAL"}
# words before a definition's head term that name no genus ("nama sebuah lontar")
GENUS_FILLER = re.compile(r"^(?:(?:nama|sebutan|istilah|sebuah|suatu|satu|salah satu|jenis|bentuk|"
                          r"semacam|sejenis|dari|untuk|halus|lain|lokal|yang|khusus|bagi)\s+)*", re.I)


def load_relations():
    txt = RELATIONS.read_text(encoding="utf-8")
    return [json.loads(b) for b in txt.split("\n\n") if b.strip()]


def sentence_initial(text, start):
    before = text[:start].rstrip()
    return not before or before[-1] in ".!?:;\"“"


def main():
    ents = json.loads(ENTITIES.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in ents}
    rels = [r for r in load_relations() if r.get("confidence") != "LOW"]
    cfg = json.loads(RESOLUTION.read_text(encoding="utf-8"))
    waivers = json.loads(WAIVERS.read_text(encoding="utf-8")) if WAIVERS.exists() else {}
    resolver = KbResolver(KB)

    viol = defaultdict(list)   # check -> [(key, message)]
    warn = defaultdict(list)

    def waived(section, key):
        reason = (waivers.get(section) or {}).get(key)
        if reason is None:
            return False
        if not str(reason).strip():
            viol["waivers"].append((f"{section}:{key}", "waiver has an empty reason"))
        return True

    def add(section, key, msg):
        if not waived(section, key):
            viol[section].append((key, msg))

    # adjacency (live edges + broader spine)
    adj = defaultdict(set)
    out_by = defaultdict(list)
    in_by = defaultdict(list)
    for r in rels:
        s, o = r["subject_id"], r["object_id"]
        adj[s].add(o)
        adj[o].add(s)
        out_by[s].append(r)
        in_by[o].append(r)
    children = defaultdict(list)
    for e in ents:
        b = e.get("broader")
        if b in by_id:
            adj[e["id"]].add(b)
            adj[b].add(e["id"])
            children[b].append(e["id"])

    # 1 names -----------------------------------------------------------------
    for e in ents:
        n = e["name"]
        why = []
        if "_" in n:
            why.append("underscore")
        if re.search(r"[(),/]", n):
            why.append("punctuation ( ) , /")
        if JOIN_WORDS.search(n):
            why.append(f"joined phrase ('{JOIN_WORDS.search(n).group(1)}')")
        if FRAGMENT_WORDS.search(n):
            why.append(f"clause/deictic fragment ('{FRAGMENT_WORDS.search(n).group(0)}')")
        if len(n.split()) > 4:
            why.append(f"{len(n.split())} words")
        if why:
            add("names", e["id"], f"{n!r}: " + "; ".join(why))

    # 2 definitions -------------------------------------------------------------
    for e in ents:
        d = (e.get("definition") or "").strip()
        src = e.get("definition_source") or ""
        if not d:
            add("definitions", e["id"], "no definition")
            continue
        m = re.match(r"relation:S(\d+)", src)
        # a clause lifted from one extracted sentence reads as a fragment
        # ("bangunan untuk sawa"); a curated, full-sentence row is fine
        if m and int(m.group(1)) < 900000 and (d[:1].islower() or len(d) < 80):
            add("definitions", e["id"],
                f"auto-derived fragment from one corpus clause (S{m.group(1)}): {d[:90]!r}")
        lead = re.match(r'^"?([A-Z][\w\'-]*(?: [\w\'-]+){0,4}?)"?(?: \([^)]*\))? (?:adalah|merupakan|ialah) ', d)
        if lead:
            x = lead.group(1).lower()
            names = [e["name"]] + [a.lower() for a in e.get("aliases", [])]
            hit = resolver.resolve(x)
            same = hit is not None and hit.id == e["id"] and hit.via in NON_FUZZY
            if not same and not any(x in nm or nm in x for nm in names):
                add("definitions", e["id"], f"definition is about {x!r}, not {e['name']!r}")
        if re.search(r"dalam konteks ngaben", d, re.I):
            warn["boilerplate"].append((e["id"], "'Dalam konteks Ngaben' -- keep only if the sentence is Ngaben-specific"))
        if len(d) > 700:
            warn["long_definition"].append((e["id"], f"{len(d)} chars"))

    # 3 isolated --------------------------------------------------------------
    for e in ents:
        if not adj.get(e["id"]):
            add("isolated", e["id"], f"{e['name']!r} has no edge and no broader/child link")

    # 4 closure ---------------------------------------------------------------
    closure_hits = defaultdict(set)
    for e in ents:
        d = e.get("definition") or ""
        for m in CAP_SEQ.finditer(d):
            if sentence_initial(d, m.start()):
                continue
            toks = m.group(0).split()
            while toks and toks[0].lower() in PEEL:
                toks = toks[1:]
            while toks and toks[-1].lower() in PEEL:
                toks = toks[:-1]
            if not toks:
                continue
            term = " ".join(toks)
            key = term.lower()
            if key in {e["name"]} | {a.lower() for a in e.get("aliases", [])}:
                continue
            hit = resolver.resolve(term)
            if hit and hit.via in NON_FUZZY:
                continue
            closure_hits[key].add(e["id"])
    for key, where in sorted(closure_hits.items()):
        hit = resolver.resolve(key)
        note = f" (only fuzzy -> {hit.id})" if hit else ""
        add("closure", key, f"used in {len(where)} definition(s), e.g. {sorted(where)[:4]}{note}")

    # 5 groups ----------------------------------------------------------------
    def member_count(eid):
        n = len(children.get(eid, []))
        n += sum(1 for r in out_by.get(eid, []) if r["predicate"] in MEMBER_OUT)
        n += sum(1 for r in in_by.get(eid, []) if r["predicate"] in MEMBER_IN)
        return n

    for e in ents:
        toks = e["name"].split()
        if len(toks) >= 2 and toks[0] in NUMERAL_PREFIXES and member_count(e["id"]) < 2:
            add("groups", e["id"], f"numeral-set name {e['name']!r} has {member_count(e['id'])} linked member(s)")
    for e in ents:
        d = e.get("definition") or ""
        # only a real membership claim: "salah satu dari [up to 3 words] <Group>"
        # -- not "salah satu sarana dalam upacara Ngaben", which is usage.
        for m in re.finditer(r"salah satu dari (?:[a-z()-]+ ){0,3}?(?=[A-Z])", d):
            cm = CAP_SEQ.match(d, m.end())
            if not cm:
                continue
            toks = [t for t in cm.group(0).split() if t.lower() not in PEEL]
            # longest non-fuzzy-resolving prefix
            target = None
            for k in range(len(toks), 0, -1):
                hit = resolver.resolve(" ".join(toks[:k]))
                if hit and hit.via in NON_FUZZY:
                    target = hit.id
                    break
            if target and target != e["id"] and target not in adj.get(e["id"], set()):
                add("groups", f"{e['id']}>{target}",
                    f"definition says 'salah satu ... {' '.join(toks)}' but no link to {target}")

    # 6 broader semantics -----------------------------------------------------
    for e in ents:
        b = e.get("broader")
        if b not in by_id:
            continue
        p = by_id[b]
        plain_shape = e["name"].startswith(p["name"] + " ")
        same_type = e.get("type") == p.get("type")
        if plain_shape and same_type and b not in PART_PARENTS:
            continue
        why = []
        if not plain_shape:
            why.append("not '<parent> <qualifier>' naming (manual override)")
        if not same_type:
            why.append(f"type {e.get('type')} vs parent {p.get('type')}")
        if b in PART_PARENTS:
            why.append("parent usually has parts/items, not kinds")
        add("broader", f"{e['id']}>{b}", f"{e['name']!r} TERMASUK_JENIS {p['name']!r}: " + "; ".join(why))

    # 7 edges -----------------------------------------------------------------
    dup = Counter((r["subject_id"], r["predicate"], r["object_id"]) for r in rels)
    for r in rels:
        if r["subject_id"] == r["object_id"]:
            add("edges", f"{r['subject_id']}|{r['predicate']}|{r['object_id']}", "self-loop")
    for (s, p, o), c in dup.items():
        if c > 1:
            warn["duplicate_edge"].append((f"{s}|{p}|{o}", f"x{c}"))

    # 10 composition ------------------------------------------------------------
    # "what is X made of / what does X contain" stored as a flat text property
    # (a LITERAL row) never reaches the bot -- soda's nasi/minuman/buah-buahan/jajan
    # sat there while the bot could only name canang sari (2026-09-24). Components
    # must be real edges to defined nodes, or waived as mere description.
    for e in ents:
        for pred, items in (e.get("attributes") or {}).items():
            if pred in COMPOSITION and items:
                vals = "; ".join(a["value"] for a in items)
                add("composition", f"{e['id']}:{pred}",
                    f"{pred} stored as text, invisible to the bot: {vals[:120]!r}")

    # 11 attributes -------------------------------------------------------------
    # the bot shows a node's text-only facts when their question aspect is asked
    # ("apa makna kawangen"), so each one must be a clean, self-contained fact the
    # bot can say -- 2026-09-24 triage found about a third were junk ("stulasarira
    # nya", "wujud tersebut", "beberapa jenis", tirtha MEMILIKI "tarif").
    for e in ents:
        for pred, items in (e.get("attributes") or {}).items():
            for a in items:
                v = a["value"]
                why = []
                if pred not in ASPECT_PREDICATES:
                    why.append("predicate is in no question aspect (kb_content.PREDICATE_FAMILIES) -- never shown")
                m = ATTR_DEICTIC.search(v)
                if m:
                    why.append(f"deictic reference {m.group(0)!r}")
                m = ATTR_VAGUE_HEAD.match(v)
                if m:
                    why.append(f"vague head {m.group(0)!r}")
                if pred in LIGHT_VERBS and len(v.split()) < 2:
                    why.append(f"one-word value after {pred}")
                if why:
                    add("attributes", f"{e['id']}:{pred}:{v}", f"S{a['sentence_id']}: " + "; ".join(why))

    # 12 stages -----------------------------------------------------------------
    # "apa saja tahapan X" lists X's BAGIAN_DARI children, so a tool or building
    # there became a "stage": panguryagan in Ngaben; payadnyan, sanggar surya and
    # gupura in Atma Wedana (2026-09-25).
    for r in rels:
        if r["predicate"] != "BAGIAN_DARI":
            continue
        st = by_id[r["subject_id"]].get("type")
        ot = by_id[r["object_id"]].get("type")
        if ot in STAGE_TYPES and st not in STAGE_TYPES:
            add("stages", f"{r['subject_id']}>{r['object_id']}",
                f"{r['subject_name']!r} ({st}) BAGIAN_DARI {r['object_name']!r} ({ot}): "
                f"not a stage -- use DIGUNAKAN_DALAM")

    # 13 genus ------------------------------------------------------------------
    # "X adalah <genus> ..." files X under a known term, so X must be linked to it
    # (edge or broader, either way): yama purwana tattwa "adalah nama sebuah lontar"
    # had no link to lontar, sawa "Jenazah dalam konteks upacara" none to jenazah
    # (conersation.md, 2026-09-25). Check 5 only covered "salah satu dari <X>".
    for e in ents:
        d = e.get("definition") or ""
        m = re.search(r"\b(?:adalah|ialah|merupakan|yaitu)\s+(.*)", d[:300], re.I)
        words = re.findall(r"[\w'-]+", GENUS_FILLER.sub("", m.group(1) if m else d))[:4]
        hit = None
        for k in range(len(words), 0, -1):
            hit = resolver.resolve(" ".join(words[:k]))
            if hit and hit.via in NON_FUZZY:
                break
            hit = None
        if hit and hit.id != e["id"] and hit.id not in adj.get(e["id"], set()):
            add("genus", f"{e['id']}>{hit.id}",
                f"definition files {e['name']!r} under {' '.join(words[:k])!r} ({hit.id}) but they are not linked")

    # 8 config ----------------------------------------------------------------
    names = {e["name"] for e in ents}
    for k, v in cfg.get("force_merge", {}).items():
        if k.startswith("_"):
            continue
        if v.lower().strip() not in names:
            add("config", f"force_merge:{k}", f"target {v!r} is not an existing entity name")
    for x in cfg.get("exclude_from_resolution", []):
        add("config", f"exclude:{x}", "hidden from the bot instead of fixed (rename / merge / reject)")

    # 9 resolver --------------------------------------------------------------
    for e in ents:
        for s in [e["name"]] + e.get("aliases", []):
            hit = resolver.resolve(s)
            if not hit or hit.id != e["id"] or hit.via not in NON_FUZZY:
                got = f"{hit.id} via {hit.via}" if hit else "nothing"
                add("resolver", f"{e['id']}:{s}", f"{s!r} resolves to {got}")

    # report ------------------------------------------------------------------
    order = ["names", "definitions", "isolated", "closure", "groups", "broader",
             "edges", "composition", "attributes", "stages", "genus", "config", "resolver", "waivers"]
    total = sum(len(v) for v in viol.values())
    L = ["# KB lint report", "",
         f"entities {len(ents)}, live relations {len(rels)}", "",
         f"**BLOCKING violations: {total}**", ""]
    for sec in order:
        L.append(f"- {sec}: {len(viol.get(sec, []))}")
    L.append("")
    for sec in order:
        items = viol.get(sec, [])
        if not items:
            continue
        L.append(f"## {sec} ({len(items)})")
        L.append("")
        for key, msg in items:
            L.append(f"- `{key}` -- {msg}")
        L.append("")
    L.append("# Warnings (non-blocking)")
    L.append("")
    for sec, items in warn.items():
        L.append(f"## {sec} ({len(items)})")
        L.append("")
        for key, msg in items:
            L.append(f"- `{key}` -- {msg}")
        L.append("")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"BLOCKING violations: {total}")
    for sec in order:
        if viol.get(sec):
            print(f"  {sec:12} {len(viol[sec])}")
    print(f"warnings: " + ", ".join(f"{k} {len(v)}" for k, v in warn.items()))
    print(f"wrote {OUT}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

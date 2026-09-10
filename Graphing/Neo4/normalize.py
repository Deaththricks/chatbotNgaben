"""
normalize.py  --  clean the Ngaben relation-extraction output before loading it into Neo4j.

Reads the pipeline output (messy) and writes a cleaned copy plus a full change report.
Deterministic and safe to re-run. Does NOT touch the notebook or the pipeline.

What it does (in order):
  1. Merge spelling / morphology variants of entity names into one node
     (rules: node_aliases.json).
  2. Strip boundary junk (stray quotes / commas / spaces) from subject & object,
     and drop rows whose object is empty or a bare stopword ("nya", ...).
  3. Demote clause-length "entity" objects to LITERAL, so the loader stores them
     as a property on the subject instead of drawing a giant unreadable node.
  4. Drop stray object_label values from LITERAL rows (the loader ignores them
     anyway, and they are substring-match artifacts -- e.g. the S45 mislabel).
  5. Collapse the ~90 raw relation labels into a small controlled set
     (rules: relation_map.json). Original value kept in a new "raw_relation" field.
  6. Resolve subject_label when merged variants disagree (gazetteer wins,
     else majority vote).
  7. De-duplicate identical (subject, relation, object, type) rows.
  8. Sort by sentence_id.

Usage:
    python normalize.py
    python normalize.py --in <path> --out <path> --report <path>

Then:
    python load_ngaben_to_neo4j.py        # now reads the .normalized.json, wipes + reloads
    # ...and re-export the SVG from Neo4j Browser.
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_IN = os.path.join(HERE, "..", "Results", "Final", "relation_results_ngaben",
                          "relation_results_ngaben.json")
DEFAULT_OUT = os.path.join(HERE, "relation_results_ngaben.normalized.json")
DEFAULT_REPORT = os.path.join(HERE, "normalize_report.txt")

ALIASES_PATH = os.path.join(HERE, "node_aliases.json")
RELMAP_PATH = os.path.join(HERE, "relation_map.json")
GAZETTEER_PATH = os.path.join(HERE, "..", "Data", "ngaben-dictionary.json")

# --- tunables -------------------------------------------------------------------
# the natural-language predicate set the relation_map.json rules collapse to.
# 12 renamed notebook buckets + kept temporal/disposal predicates + a few
# one-off verbs that are correct extractions but fit no bucket. Keep this in
# sync with relation_map.json's right-hand values.
CANONICAL_RELATIONS = {
    # Core natural predicate set emitted by the notebook cascade (13.3c).
    # The cascade also emits an OPEN TAIL of voiced-verb predicates
    # (DIBUNGKUS_DENGAN, DICABUT_DENGAN, MEMEGANG, ...) -- those are accepted
    # as-is by the VOICED_PREDICATE regex below, not listed here.
    "ADALAH", "BERARTI", "BERWUJUD", "DIKENAL_SEBAGAI",
    "BERPERAN_SEBAGAI", "BERFUNGSI_SEBAGAI", "MELAMBANGKAN",
    "BAGIAN_DARI", "TERDIRI_DARI", "TERBUAT_DARI", "BERASAL_DARI",
    "MEMILIKI", "MEMPEROLEH", "DIPEROLEH_DARI", "DIBERI", "DIMOHON_DARI", "DIMOHON",
    "MENGGUNAKAN", "MEMAKAI", "DIPAKAI_UNTUK", "BERTUJUAN_UNTUK", "DITUJUKAN_UNTUK",
    "BERADA_DI", "DILETAKKAN_DI", "MENUJU", "DIBAWA_KE", "DIHANYUTKAN_KE",
    "DIBUAT_DI", "DILAKUKAN_DI", "DIPUJA",
    "DIPERSEMBAHKAN_KEPADA",
    "DIBUNGKUS_DENGAN", "DIIKAT_DENGAN", "DIGULUNG_DENGAN", "DISIRAM_DENGAN",
    "DIALASI_DENGAN", "DIPAKAIKAN", "DIAMBIL", "DIKUBUR", "DIBAKAR",
    "DIMANDIKAN", "DITABURKAN", "DIUSUNG", "DIBONGKAR",
    "DILAKUKAN_DENGAN", "DILAKUKAN_OLEH", "BERDASARKAN", "MENURUT",
    "DIGANTI_DENGAN", "DISAMBUNG_DENGAN", "DIAKHIRI_DENGAN",
    "MENGHASILKAN", "MENGHILANGKAN", "MENJADI", "MENGALAMI", "MENENTUKAN",
    "SEBELUM", "SETELAH", "SELAIN", "MENJELANG", "DILAKUKAN_SAAT",
    "DISERTAI", "MENINGGAL", "DIPERLAKUKAN_SEPERTI", "LAINNYA",
    # legacy names still accepted (relation_map.json aliases them)
    "DIGUNAKAN_UNTUK", "MENSYARATKAN", "MEWAJIBKAN", "DIKENAI",
    "BERPENGARUH_PADA", "MENINGKAT_KE",
    # 2026-09-07 predicate-sync pass: new canonical merge targets
    # (relation_map.json folds synonyms into these) + a few accepted
    # open-tail predicates that don't start with a voiced prefix so the
    # VOICED_PREDICATE regex below can't wave them through.
    "DIMASUKKAN_KE_DALAM", "SAMA_DENGAN", "DIGILING_DI_ATAS",
    "AKRAB_DENGAN", "KEMBALI_KE", "LAHIR_ATAS", "LAHIR_DALAM_WUJUD",
    "LEPAS_BEBAS_DARI", "HARUS_MELALUI", "HARUS_DIBIARKAN",
    "DAPAT_SELESAI_SECARA", "TELAH_SELESAI_SECARA", "TIDAK_MEMAKAI",
    "TIDAK_MENJAMIN", "TIDUR_DI", "MUSNAH", "CONTOH",
    "KALAH_MERIAH_DIBANDING", "BARU_LEPAS_PERTALIAN_DENGAN",
    "HINGGA_TAMPAK", "BUKAN_SEKADAR", "TANPA",
}
# An open-tail predicate is a well-formed voiced Indonesian verb form
# (di-/ter- passive, meN-/ber- active), followed by any number of
# underscore-joined all-caps segments (case markers, incorporated nouns,
# sequence markers -- e.g. DIBONGKAR_SETELAH, TERTANAM_TITIP_DI,
# BERUBAH_DARI_SUKSMA_SARIRA_MENJADI). The notebook cascade emits an open
# tail of these on purpose; they are accepted as-is, not flagged.
VOICED_PREDICATE = re.compile(
    r"^(DI|TER|ME|MEM|MEN|MENG|MENY|BER)[A-Z]{2,}(_[A-Z]{2,})*$"
)
CATCHALL_RELATION = "LAINNYA"   # bucket for relations we could not classify

# Sentences that are actually Balinese/Kawi, not Indonesian: Stanza's
# Indonesian parser produces noise for them, so any relation extracted is
# garbage. Drop a row whose context_sentence is short and carries >=2 of
# these Balinese-only function words.
BALINESE_SENTENCE_MARKERS = {
    "maring", "sangkaning", "sane", "punika", "ipun", "nika",
}
CLAUSE_LEN_HARD = 60          # object longer than this -> demote to LITERAL
CLAUSE_LEN_SOFT = 40          # object longer than this AND has a clause marker -> demote
CLAUSE_MARKERS = re.compile(r"\b(yang|yaitu|yakni|sehingga|untuk|dengan|karena|apabila|ketika)\b")
STOPWORD_OBJECTS = {
    "nya", "ini", "itu", "yang", "dan", "atau", "tersebut", "adalah",
    "yaitu", "yakni", "dll", "dsb", "dst",
    "tadi", "situ", "sini", "sana", "demikian", "semua", "mesti", "nanti",
    "sesuatu", "semacam", "begitu", "sendiri", "berikut", "misal", "misalnya",
}
BOUNDARY_CHARS = " \t\"'“”‘’(),.;:-/"

# A subject/object that contains one of these tokens is a sentence fragment the
# NER/relation extractor mis-captured, not an entity name -> drop the row.
# Catches question / comparison / verb fragments like "bade jenis apa",
# "bali aga vs bali dataran", "mewujudkan sanghyang ongkans",
# "perubahan kata pitra", "sama atiwa-tiwa asti vedana", "bagaikan pitraloka".
FRAGMENT_MARKERS = re.compile(
    r"\b(apa|vs|demikian|bagaikan|sama|alias|mewujudkan|perubahan)\b"
)
# extra markers only a *subject* can never legitimately contain (a clause-like
# ENTITY object is instead demoted to a LITERAL property by step 3).
SUBJECT_ONLY_FRAGMENT_MARKERS = re.compile(r"\b(yang|yaitu|yakni|adalah|merupakan)\b")
FRAGMENT_TAIL = re.compile(r"\b(jenis|hal)$")
# A subject of >= this many words is a captured clause, not an entity name --
# the longest real entity in this corpus ("bale semanggen rumah adat bali" is
# already "bale semanggen" over-captured) is 3-4 words. Drop the row.
SUBJECT_MAX_WORDS = 5

# A LITERAL object that is exactly one of these closed-class / bare-lemma tokens
# carries no information (dependency parse grabbed a preposition, direction word,
# or stripped verb) -> drop the row.
CLOSED_CLASS_LITERALS = {
    "atas", "bawah", "utara", "selatan", "timur", "barat", "dalam", "luar",
    "depan", "belakang", "kiri", "kanan", "tengah", "samping",
    "menjadi", "berbentuk", "terbuat", "berupa", "adalah", "merupakan",
    "keadaan", "hal", "rupa", "diri", "jenis", "bentuk", "cara", "bagian",
    "proses", "status",
    "arti", "makna", "istilah", "maksud", "tujuan", "kedudukan", "sifat",
    "ciri", "nama", "unsur", "posisi", "kenyataan", "hulu", "hilir", "muka",
}
# ------------------------------------------------------------------------------


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def clean_boundary(text):
    """Trim stray quotes / commas / brackets / whitespace from the ends; squeeze inner spaces."""
    if text is None:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    prev = None
    while prev != t:
        prev = t
        t = t.strip(BOUNDARY_CHARS).strip()
    # drop an unbalanced trailing quote or open paren left behind
    if t.count('"') % 2 == 1:
        t = t.replace('"', "").strip()
    if t.count("(") != t.count(")"):
        t = t.replace("(", "").replace(")", "").strip()
    return re.sub(r"\s+", " ", t).strip()


RELCLAUSE_MARKER = re.compile(r"\b(yang|yaitu|yakni)\b")


def is_clause_object(obj):
    low = obj.lower()
    # a relative-clause / appositive marker means the object is a description,
    # not an entity name -- regardless of length (root cause is upstream, see plan)
    if RELCLAUSE_MARKER.search(low):
        return True
    n = len(obj)
    if n > CLAUSE_LEN_HARD:
        return True
    if n > CLAUSE_LEN_SOFT and CLAUSE_MARKERS.search(low):
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=DEFAULT_IN)
    ap.add_argument("--out", dest="out", default=DEFAULT_OUT)
    ap.add_argument("--report", dest="report", default=DEFAULT_REPORT)
    args = ap.parse_args()

    data = load_json(args.inp)
    raw_aliases = load_json(ALIASES_PATH)
    raw_relmap = load_json(RELMAP_PATH)
    gazetteer = {k.lower().strip(): v for k, v in load_json(GAZETTEER_PATH).items()}

    aliases = {k.lower().strip(): v.lower().strip()
               for k, v in raw_aliases.items() if not k.startswith("_")}
    relmap = {k: v for k, v in raw_relmap.items() if not k.startswith("_")}

    log = defaultdict(list)      # section -> [lines]
    n_in = len(data)

    # ---- snapshot BEFORE, computed the way the loader sees it -----------------
    def graph_stats(rows):
        names, edges, lit_subjects = set(), set(), set()
        for d in rows:
            if not str(d["relation"]).isupper():
                continue
            s = d["subject"].strip().lower()
            names.add(s)
            if d["object_type"] == "ENTITY":
                o = d["object"].strip().lower()
                names.add(o)
                edges.add((s, d["relation"], o))
            else:
                lit_subjects.add(s)
        deg = defaultdict(int)
        for s, _, o in edges:
            deg[s] += 1
            deg[o] += 1
        isolated = [n for n in names if deg[n] == 0]
        return names, edges, isolated

    names0, edges0, iso0 = graph_stats(data)
    rels0 = Counter(d["relation"] for d in data)

    # ---- 1. alias merge (subject always; object only when ENTITY) ------------
    alias_hits = Counter()
    for d in data:
        d["_raw_subject"] = d["subject"]
        d["_raw_object"] = d["object"]
        d["_raw_relation"] = d["relation"]

        s_key = clean_boundary(d["subject"]).lower()
        if s_key in aliases:
            alias_hits[(s_key, aliases[s_key])] += 1
            s_key = aliases[s_key]
        d["subject"] = s_key

        o_clean = clean_boundary(d["object"])
        if d["object_type"] == "ENTITY":
            o_key = o_clean.lower()
            if o_key in aliases:
                alias_hits[(o_key, aliases[o_key])] += 1
                o_key = aliases[o_key]
            d["object"] = o_key
        else:
            d["object"] = o_clean

    for (variant, canon), c in sorted(alias_hits.items(), key=lambda x: -x[1]):
        log["1. NODE MERGES"].append(f"  {variant!r:45} -> {canon!r:35} ({c} row(s))")

    # ---- 2. drop junk rows --------------------------------------------------
    kept = []
    for d in data:
        obj_l = d["object"].strip().lower()
        if not d["subject"].strip():
            log["2. ROWS DROPPED"].append(f"  S{d['sentence_id']}: empty subject  ({d['_raw_subject']!r} -> '')")
            continue
        if not obj_l:
            log["2. ROWS DROPPED"].append(f"  S{d['sentence_id']}: empty object   ({d['_raw_object']!r} -> '')")
            continue
        if obj_l in STOPWORD_OBJECTS:
            log["2. ROWS DROPPED"].append(
                f"  S{d['sentence_id']}: stopword object {d['object']!r}  "
                f"[{d['subject']} -{d['_raw_relation']}-> {d['_raw_object']}]")
            continue
        subj_l = d["subject"].strip().lower()
        if subj_l == obj_l:
            log["2c. SELF-LOOPS DROPPED"].append(
                f"  S{d['sentence_id']}: {d['subject']!r} -{d['_raw_relation']}-> itself")
            continue
        subj_frag = (FRAGMENT_MARKERS.search(subj_l) or FRAGMENT_TAIL.search(subj_l)
                     or SUBJECT_ONLY_FRAGMENT_MARKERS.search(subj_l)
                     or len(subj_l.split()) >= SUBJECT_MAX_WORDS)
        obj_frag = (d["object_type"] == "ENTITY"
                    and (FRAGMENT_MARKERS.search(obj_l) or FRAGMENT_TAIL.search(obj_l)))
        if subj_frag or obj_frag:
            log["2d. FRAGMENTS DROPPED (not an entity name)"].append(
                f"  S{d['sentence_id']}: {d['subject']!r} -{d['_raw_relation']}-> "
                f"{d['object']!r} ({d['object_type']})")
            continue
        if d["object_type"] == "LITERAL" and obj_l in CLOSED_CLASS_LITERALS:
            log["2e. CLOSED-CLASS LITERAL VALUES DROPPED"].append(
                f"  S{d['sentence_id']}: {d['subject']} -[{d['_raw_relation']}]-> {d['object']!r}")
            continue
        ctx_words = set(re.findall(r"[a-z]+", d.get("context_sentence", "").lower()))
        bal_hits = ctx_words & BALINESE_SENTENCE_MARKERS
        if len(bal_hits) >= 2 and len(ctx_words) <= 10:
            log["2b. ROWS DROPPED (non-Indonesian sentence)"].append(
                f"  S{d['sentence_id']}: {sorted(bal_hits)}  "
                f"[{d.get('context_sentence', '')[:70]}]")
            continue
        kept.append(d)
    data = kept

    # ---- 3. demote clause objects -----------------------------------------
    for d in data:
        if d["object_type"] == "ENTITY" and is_clause_object(d["object"]):
            log["3. CLAUSE OBJECTS DEMOTED (entity -> literal property)"].append(
                f"  S{d['sentence_id']:>4}  {d['subject']} -[{d['_raw_relation']}]-> "
                f"{d['object'][:85]}{'...' if len(d['object']) > 85 else ''}")
            d["object_type"] = "LITERAL"
            d["object_label"] = None

    # ---- 4. strip stray labels from literals ------------------------------
    stripped = []
    for d in data:
        if d["object_type"] == "LITERAL" and d.get("object_label"):
            stripped.append((d["sentence_id"], d["object_label"]))
            d["object_label"] = None
    if stripped:
        log["4. STRAY LABELS REMOVED FROM LITERAL ROWS"].append(
            f"  {len(stripped)} row(s); e.g. " +
            ", ".join(f"S{sid}({lbl})" for sid, lbl in stripped[:12]) +
            (" ..." if len(stripped) > 12 else ""))

    # ---- 5. relation remap ----------------------------------------------
    remap_counts = Counter()
    misc_examples = {}
    for d in data:
        raw = d["relation"]
        new = relmap.get(raw, raw if raw in CANONICAL_RELATIONS else raw.upper())
        d["relation"] = new
        d["raw_relation"] = d["_raw_relation"]
        if new != raw:
            remap_counts[(raw, new)] += 1
        if new == CATCHALL_RELATION and raw not in misc_examples:
            misc_examples[raw] = f"{d['subject']} -> {d['_raw_object'][:50]}"
    for (raw, new), c in sorted(remap_counts.items(), key=lambda kv: -kv[1]):
        log["5. RELATION REMAP"].append(f"  {raw!r:22} -> {new!r:14} ({c})")
    for raw, ex in sorted(misc_examples.items()):
        log["5b. SENT TO 'LAINNYA' (review these - raw kept in raw_relation)"].append(
            f"  {raw!r:22} e.g. {ex}")
    leftover = sorted(r for r in ({d["relation"] for d in data} - CANONICAL_RELATIONS)
                      if not VOICED_PREDICATE.match(r))
    if leftover:
        log["5c. STILL-UNMAPPED RELATIONS (not a well-formed voiced verb -- review)"].append(
            "  " + ", ".join(leftover))

    # ---- 5d. BERARTI is a gloss, never an edge --------------------------
    # "berarti" / "artinya" states what a term MEANS -- the object is a
    # definition, not another entity. Force it to a literal property so it
    # feeds the glossary instead of drawing a bogus relationship.
    berarti_demoted = 0
    for d in data:
        if d["relation"] == "BERARTI" and d["object_type"] == "ENTITY":
            d["object_type"] = "LITERAL"
            d["object_label"] = None
            berarti_demoted += 1
    if berarti_demoted:
        log["5d. BERARTI OBJECTS DEMOTED (entity -> definition literal)"].append(
            f"  {berarti_demoted} row(s)")

    # ---- 6. resolve subject_label conflicts on merged names --------------
    labels_seen = defaultdict(Counter)
    for d in data:
        if d.get("subject_label"):
            labels_seen[d["subject"]][d["subject_label"]] += 1
        if d["object_type"] == "ENTITY" and d.get("object_label"):
            labels_seen[d["object"]][d["object_label"]] += 1

    resolved = {}
    for name, ctr in labels_seen.items():
        if len(ctr) <= 1:
            resolved[name] = next(iter(ctr))
            continue
        gaz = gazetteer.get(name)
        choice = gaz if gaz else ctr.most_common(1)[0][0]
        resolved[name] = choice
        log["6. LABEL CONFLICTS RESOLVED (merged nodes)"].append(
            f"  {name!r:30} {dict(ctr)}  ->  {choice}"
            f"{'  (from gazetteer)' if gaz else '  (majority)'}")

    for d in data:
        if d["subject"] in resolved:
            d["subject_label"] = resolved[d["subject"]]
        if d["object_type"] == "ENTITY" and d["object"] in resolved:
            d["object_label"] = resolved[d["object"]]

    # ---- 7. dedup ------------------------------------------------------
    seen, deduped, dups = set(), [], 0
    for d in sorted(data, key=lambda r: (r["sentence_id"], r["subject"], r["relation"], r["object"])):
        key = (d["subject"], d["relation"], d["object"], d["object_type"])
        if key in seen:
            dups += 1
            log["7. DUPLICATE ROWS REMOVED"].append(
                f"  S{d['sentence_id']}  {d['subject']} -[{d['relation']}]-> {d['object']}")
            continue
        seen.add(key)
        deduped.append(d)
    data = deduped

    # ---- 8. sort + emit ----------------------------------------------
    data.sort(key=lambda r: r["sentence_id"])
    records = [{
        "sentence_id": d["sentence_id"],
        "context_sentence": d["context_sentence"],
        "subject": d["subject"],
        "subject_label": d["subject_label"],
        "relation": d["relation"],
        "raw_relation": d["raw_relation"],
        "object": d["object"],
        "object_label": d["object_label"],
        "object_type": d["object_type"],
        "source": d["source"],
    } for d in data]

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # ---- report -----------------------------------------------------
    names1, edges1, iso1 = graph_stats(records)
    rels1 = Counter(d["relation"] for d in records)

    summary = [
        "=" * 78,
        "NGABEN RELATION NORMALIZATION REPORT",
        "=" * 78,
        f"input : {os.path.relpath(args.inp, HERE)}",
        f"output: {os.path.relpath(args.out, HERE)}",
        "",
        f"rows                : {n_in}  ->  {len(records)}   ({len(records) - n_in:+d})",
        f"  dropped (junk)     : {len(log['2. ROWS DROPPED'])}",
        f"  dropped (balinese) : {len(log['2b. ROWS DROPPED (non-Indonesian sentence)'])}",
        f"  dropped (self-loop): {len(log['2c. SELF-LOOPS DROPPED'])}",
        f"  dropped (fragment) : {len(log['2d. FRAGMENTS DROPPED (not an entity name)'])}",
        f"  dropped (bare word): {len(log['2e. CLOSED-CLASS LITERAL VALUES DROPPED'])}",
        f"  clause->literal    : {len(log['3. CLAUSE OBJECTS DEMOTED (entity -> literal property)'])}",
        f"  berarti->literal   : {berarti_demoted}",
        f"  duplicates removed : {dups}",
        f"nodes               : {len(names0)}  ->  {len(names1)}   ({len(names1) - len(names0):+d})",
        f"edges (unique)       : {len(edges0)}  ->  {len(edges1)}   ({len(edges1) - len(edges0):+d})",
        f"isolated nodes       : {len(iso0)}  ->  {len(iso1)}   ({len(iso1) - len(iso0):+d})",
        f"distinct relations   : {len(rels0)}  ->  {len(rels1)}",
        f"  final set          : {', '.join(sorted(rels1))}",
        "",
    ]
    order = ["1. NODE MERGES", "2. ROWS DROPPED",
             "2b. ROWS DROPPED (non-Indonesian sentence)",
             "2c. SELF-LOOPS DROPPED",
             "2d. FRAGMENTS DROPPED (not an entity name)",
             "2e. CLOSED-CLASS LITERAL VALUES DROPPED",
             "3. CLAUSE OBJECTS DEMOTED (entity -> literal property)",
             "4. STRAY LABELS REMOVED FROM LITERAL ROWS", "5. RELATION REMAP",
             "5b. SENT TO 'LAINNYA' (review these - raw kept in raw_relation)",
             "5c. STILL-UNMAPPED RELATIONS (add to relation_map.json)",
             "5d. BERARTI OBJECTS DEMOTED (entity -> definition literal)",
             "6. LABEL CONFLICTS RESOLVED (merged nodes)", "7. DUPLICATE ROWS REMOVED"]
    body = []
    for sec in order:
        body.append("")
        body.append(sec)
        body.append("-" * len(sec))
        body.extend(log[sec] or ["  (none)"])

    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write("\n".join(summary + body) + "\n")

    print("\n".join(summary))
    print(f"wrote {args.out}")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()

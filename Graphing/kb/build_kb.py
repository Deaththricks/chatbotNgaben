"""
build_kb.py  --  turn the cleaned Ngaben relation output + the source report into
a single canonical knowledge base that can feed either a graph database or a
vector-RAG store.

Inputs (read-only, not modified):
  ../Neo4/relation_results_ngaben.normalized.json   (output of Neo4/normalize.py)
  ../Data/ngaben-merge-cleaned.txt                  (the source report)
  ../Data/ngaben-dictionary.json                    (term -> type gazetteer)
  ../Data/normalization-ngaben.json                 (concept-level merge map)
  ../Neo4/node_aliases.json                         (spelling-variant map)
  ./entity_resolution.json                          (tuning)
  ./relation_phrases.json                           (triple -> sentence templates)

Outputs (this folder):
  entities.json        canonical entities: id, name, type, aliases, definition,
                       broader, attributes, mention_passages, source_strings
  relations.jsonl      cleaned edges: subject/object ids, predicate, confidence,
                       provenance, nl
  facts.jsonl          HIGH+MED edges rendered as Indonesian sentences  (RAG)
  passages.jsonl       source report chunked, with section_path + entity_ids (RAG)
  review_queue.jsonl   LOW-confidence edges + dropped fragments to adjudicate
  glossary.md          human-readable entity reference
  build_report.txt     counts + every merge / unresolved / LOW reason

All .jsonl are pretty-printed: one indented JSON object per record, blank line
between records (house style -- not compact JSONL).

Run:  python build_kb.py
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

REL_JSON   = ROOT / "Neo4" / "relation_results_ngaben.normalized.json"
DECISIONS  = HERE / "review_decisions.json"   # written by apply_review.py
SOURCE_TXT = ROOT / "Data" / "ngaben-merge-cleaned.txt"
GAZETTEER  = ROOT / "Data" / "ngaben-dictionary.json"
CONCEPTMAP = ROOT / "Data" / "normalization-ngaben.json"
ALIASES    = ROOT / "Neo4" / "node_aliases.json"
RESOLUTION = HERE / "entity_resolution.json"
PHRASES    = HERE / "relation_phrases.json"

CHUNK_TARGET = 1100   # chars; a passage chunk aims for this, never crosses a heading
CHUNK_MAX    = 1600

PREP_BEFORE_OBJ = ("di", "ke", "dari", "dengan", "pada", "tentang", "untuk",
                   "oleh", "kepada", "bagi", "sebagai", "menjadi", "seperti",
                   "terhadap", "menjelang", "sebelum", "setelah")

# a surface string matching this is a sentence fragment / description the
# NER over-captured, not an entity -> keep out of entities.json, send to review.
FRAGMENT_ENT_RE = re.compile(
    r"\b(orang|tujuan|nama|penuh|pelaksanaan|demikian|sredaning|umat\s+hindu)\b|"
    r"\btata\s+cara\b|\bsarana\s+simbolik\b")
PLACE_ALLOW = {"bali", "jawa", "india", "nusantara", "trunyan", "bali aga",
               "bali dataran", "klungkung", "gianyar", "majapahit", "besakih"}


def looks_fragment(name, etype):
    if FRAGMENT_ENT_RE.search(name):
        return True
    if len(name.split()) > 5:
        return True
    if etype == "Place" and name not in PLACE_ALLOW:
        return True
    return False


# --------------------------------------------------------------------------- io
def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump_jsonl(path, records):
    """One indented JSON object per record, blank line between -- house style."""
    with open(path, "w", encoding="utf-8") as fh:
        for i, rec in enumerate(records):
            if i:
                fh.write("\n")
            fh.write(json.dumps(rec, ensure_ascii=False, indent=2))
            fh.write("\n")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "x"


def is_deictic_alias(surface, deictic_words):
    """A surface that only differs from its resolved form by a leading/
    trailing demonstrative pronoun ('kelompok ini', 'rurub sinom tadi') is the
    extractor picking up an anaphoric reference within one sentence ("X ...
    this group ..."), not a genuine alternate name -- resolving it to the
    right entity is still correct (force_merge / modifier-strip already
    handles that), but recording it as a bot-facing "also known as" alias is
    misleading. See entity_resolution.json's deictic_words/_deictic_words_note
    -- same config-driven-exclusion shape as strip_modifiers/keep_distinct,
    not a one-off hand fix per occurrence (Batch H, 2026-09-21, item #29)."""
    toks = surface.split()
    return len(toks) > 1 and (toks[0] in deictic_words or toks[-1] in deictic_words)


# ------------------------------------------------------------------- entities
class Resolver:
    def __init__(self):
        gaz_raw = load_json(GAZETTEER)
        self.gaz = {k.lower().strip(): v for k, v in gaz_raw.items()}

        self.concept = {}          # variant(lower) -> canonical (Title Case)
        for bucket in load_json(CONCEPTMAP).values():
            for k, v in bucket.items():
                self.concept[k.lower().strip()] = v.strip()

        self.alias = {k.lower().strip(): v.lower().strip()
                      for k, v in load_json(ALIASES).items() if not k.startswith("_")}

        cfg = load_json(RESOLUTION)
        self.strip_mods = set(cfg.get("strip_modifiers", []))
        self.deictic_words = set(cfg.get("deictic_words", []))
        self.force_merge = {k: v for k, v in cfg.get("force_merge", {}).items()
                            if not k.startswith("_")}
        self.keep_distinct = set(cfg.get("keep_distinct", []))
        self.type_overrides = cfg.get("type_overrides", {})
        self.broader_overrides = {k.lower().strip(): v.lower().strip()
                                  for k, v in cfg.get("broader_overrides", {}).items()
                                  if not k.startswith("_")}
        # Sentence ids whose BERARTI/ADALAH relation is a known mis-attribution
        # (wrong subject) rather than just weak -- see entity_resolution.json's
        # _bad_definition_note. Never accepted as a definition candidate below.
        self.bad_definition_sentences = set(cfg.get("bad_definition_sentences", []))

        self._cache = {}

    def _strip(self, s):
        toks = s.split()
        # a leading bare number ("5 biji uang kepeng", "250 biji ...") is a
        # quantity, not part of the entity identity.
        while len(toks) > 1 and re.fullmatch(r"\d[\d.,/-]*", toks[0]):
            toks = toks[1:]
        while len(toks) > 1 and toks[0] in self.strip_mods:
            toks = toks[1:]
        while len(toks) > 1 and toks[-1] in self.strip_mods:
            toks = toks[:-1]
        # a second pass: "5 biji uang kepeng" -> (num) -> "biji uang kepeng"
        # -> (mod) -> "uang kepeng"; also handles "... N buah" tails.
        while len(toks) > 1 and (toks[0] in self.strip_mods
                                 or re.fullmatch(r"\d[\d.,/-]*", toks[0])):
            toks = toks[1:]
        return " ".join(toks)

    def _base_lookup(self, s):
        """concept-map / alias / gazetteer, no stripping. -> (canonical_name, method) or None"""
        if s in self.concept:
            return self.concept[s], "concept-map"
        if s in self.alias:
            tgt = self.alias[s]
            if tgt in self.concept:
                return self.concept[tgt], "alias+concept"
            return tgt, "alias"
        if s in self.gaz:
            return s, "gazetteer"
        return None

    def resolve(self, surface):
        s = surface.lower().strip()
        if s in self._cache:
            return self._cache[s]

        method = None
        canon = None

        if s in self.force_merge:
            canon, method = self.force_merge[s], "force-merge"
        if canon is None:
            hit = self._base_lookup(s)
            if hit:
                canon, method = hit
        if canon is None and s not in self.keep_distinct:
            stripped = self._strip(s)
            if stripped != s:
                if stripped in self.force_merge:
                    canon, method = self.force_merge[stripped], "force-merge+strip"
                else:
                    hit = self._base_lookup(stripped)
                    if hit:
                        canon, method = hit[0], hit[1] + "+strip"
        if canon is None:
            canon, method = s, "unresolved"

        canon = canon.lower().strip()

        # broader link: if a multi-word surface's head word is itself a known
        # entity distinct from this one, remember it.
        broader = None
        toks = s.split()
        if len(toks) > 1:
            for head in (" ".join(toks[:2]), toks[0]):
                hit = self._base_lookup(head)
                if hit and hit[0].lower() != canon:
                    broader = hit[0].lower()
                    break

        # manual override for is-a links the head-word heuristic above can't
        # derive (a single-word term with no lexical relation to its parent
        # concept, e.g. Panca Maha Bhuta's five elements) -- see
        # entity_resolution.json's broader_overrides. Wins over the heuristic.
        if canon in self.broader_overrides:
            broader = self.broader_overrides[canon]

        ent_id = slug(canon)
        result = (ent_id, canon, method, slug(broader) if broader else None,
                  broader)
        self._cache[s] = result
        return result

    def gaz_type(self, canon):
        return self.type_overrides.get(canon.lower()) or self.gaz.get(canon.lower())


# --------------------------------------------------------------- source report
HEAD_NUM   = re.compile(r"^\s*\d{1,2}\.\s+\S")
HEAD_ALPHA = re.compile(r"^\s*[A-Za-z]\.\s+\S")


def is_heading(line):
    t = line.strip()
    if not t or len(t) > 68:
        return False
    if t.endswith(".") or t.endswith(":") or t.endswith(","):
        return False
    if HEAD_NUM.match(t):
        return True
    if t.isupper() and len(t.split()) <= 6:
        return True
    # Title-case-ish standalone line
    if t[0].isupper() and 1 < len(t.split()) <= 6:
        low = {"dan", "atau", "yang", "di", "ke", "dari", "pada", "untuk"}
        caps = [w for w in t.split() if w[0].isupper() or w.lower() in low
                or not w[0].isalpha()]
        if len(caps) == len(t.split()):
            return True
    return False


def is_subheading(line):
    t = line.strip()
    if not HEAD_ALPHA.match(t) or len(t) > 68:
        return False
    if t.endswith("."):
        return False          # a lettered list item that is a full sentence
    return True


SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(*•\-])")


def chunk_section(body, base_offset):
    body = body.strip()
    if not body:
        return []
    sents = SENT_SPLIT.split(body)
    chunks, cur, cur_start = [], "", 0
    pos = 0
    for sent in sents:
        idx = body.find(sent, pos)
        if idx < 0:
            idx = pos
        pos = idx + len(sent)
        if not cur:
            cur, cur_start = sent, idx
        elif len(cur) + 1 + len(sent) <= CHUNK_MAX and len(cur) < CHUNK_TARGET:
            cur = cur + " " + sent
        else:
            chunks.append((cur.strip(), base_offset + cur_start,
                           base_offset + cur_start + len(cur)))
            cur, cur_start = sent, idx
    if cur.strip():
        chunks.append((cur.strip(), base_offset + cur_start,
                       base_offset + cur_start + len(cur)))
    return chunks


FAQ_LINE = re.compile(r"^\s*\d{1,2}\.\s+(.+?\?)\s{1,}(\S.*)$")
GLOSS_LINE = re.compile(r"^\s*[*•]\s*([^:]{2,50}?):\s{1,}(\S.*)$")


def build_passages(resolver, extra_terms=()):
    raw = SOURCE_TXT.read_text(encoding="utf-8")
    lines = raw.split("\n")

    # line -> starting char offset in raw
    offs, o = [], 0
    for ln in lines:
        offs.append(o)
        o += len(ln) + 1

    doc = "Laporan Komprehensif Ngaben"
    path = []                       # current [heading, subheading]
    sec_lines = []                  # (text, offset) buffer for current section
    passages = []
    glossary_defs = {}
    faqs = []
    in_glossary = in_faq = False

    def flush():
        if not sec_lines:
            return
        body = "\n".join(t for t, _ in sec_lines)
        base = sec_lines[0][1]
        for text, cs, ce in chunk_section(body, base):
            passages.append({"doc": doc, "section_path": list(path),
                             "text": text, "char_start": cs, "char_end": ce})
        sec_lines.clear()

    for ln, off in zip(lines, offs):
        t = ln.strip()
        if not t:
            continue
        if t.upper() == "UPACARA ATIWA-TIWA":
            flush()
            doc = "Upacara Atiwa-Tiwa"
            path = []
            in_glossary = in_faq = False
            continue

        low = t.lower()
        if re.match(r"^\s*11\.\s*glosarium", low):
            flush(); path = ["11. Glosarium"]; in_glossary, in_faq = True, False
            continue
        if re.match(r"^\s*12\.\s*pertanyaan", low):
            flush(); path = ["12. FAQ"]; in_glossary, in_faq = False, True
            continue
        if re.match(r"^\s*13\.\s*ringkasan", low):
            flush(); path = ["13. Ringkasan"]; in_glossary = in_faq = False
            continue

        if in_glossary:
            m = GLOSS_LINE.match(ln)
            if m:
                term, dfn = m.group(1).strip().lower(), m.group(2).strip()
                glossary_defs[term] = dfn
                passages.append({"doc": doc, "section_path": ["11. Glosarium"],
                                 "kind": "glossary", "term": term,
                                 "text": f"{m.group(1).strip()}: {dfn}",
                                 "char_start": off, "char_end": off + len(ln)})
            continue

        if in_faq:
            m = FAQ_LINE.match(ln)
            if m:
                q, a = m.group(1).strip(), m.group(2).strip()
                faqs.append((q, a))
                passages.append({"doc": doc, "section_path": ["12. FAQ"],
                                 "kind": "faq", "question": q, "answer": a,
                                 "text": f"{q} {a}",
                                 "char_start": off, "char_end": off + len(ln)})
            continue

        if is_heading(ln):
            flush()
            path = [t]
            continue
        if is_subheading(ln):
            flush()
            path = (path[:1] + [t]) if path else [t]
            continue
        sec_lines.append((t, off))
    flush()

    # ids + entity linking -- match gazetteer terms AND every surface string
    # that appears in the relation data, so multi-word ritual terms that are
    # not in the gazetteer still link to their entity.
    terms = set(resolver.gaz) | {t.lower().strip() for t in extra_terms}
    terms = {t for t in terms if len(t) >= 3}
    gaz_terms = sorted(terms, key=len, reverse=True)
    term_re = re.compile(r"\b(" + "|".join(re.escape(x) for x in gaz_terms) + r")\b",
                         re.IGNORECASE)
    for i, p in enumerate(passages):
        p_id = f"{slug(p['doc'])[:12]}_{i:03d}"
        if p.get("kind") == "glossary":
            # A glossary line's own definition prose often names OTHER real KB terms
            # (e.g. Ngaben's definition mentions "atiwa-tiwa", "pancamahabutha", "sawa").
            # Scanning the whole passage text like an ordinary narrative passage would
            # wrongly tag -- and later surface -- this definition onto every term it
            # happens to mention. Link it only to the ONE entity it actually defines.
            found = {resolver.resolve(p["term"])[0]}
        elif p.get("kind") == "faq":
            # Only the question determines what a FAQ is "about" -- the answer text
            # often mentions other terms in passing (e.g. "...oleh Sulinggih tetap
            # dijalankan...") without the FAQ being about them.
            found = {resolver.resolve(m.group(1))[0] for m in term_re.finditer(p["question"].lower())}
        else:
            found = {resolver.resolve(m.group(1))[0] for m in term_re.finditer(p["text"].lower())}
        rec = {"id": p_id, "doc": p["doc"], "section_path": p["section_path"]}
        if p.get("kind"):
            rec["kind"] = p["kind"]
        for k in ("term", "question", "answer"):
            if p.get(k):
                rec[k] = p[k]
        rec["text"] = p["text"]
        rec["entity_ids"] = sorted(found)
        rec["char_start"] = p["char_start"]
        rec["char_end"] = p["char_end"]
        passages[i] = rec

    return passages, glossary_defs, faqs


# --------------------------------------------------------------------- facts
DEF_PATTERN = re.compile(r"^(.{2,40}?)\s+(?:adalah|ialah|berarti|yaitu|yakni)\s+(.+)")


def object_preposition(context, obj):
    """token immediately before the object phrase in the source sentence."""
    if not context or not obj:
        return None
    ctx = context.lower()
    o = obj.lower()
    idx = ctx.find(o)
    if idx <= 0:
        # try first 3 words of the object
        o2 = " ".join(o.split()[:3])
        idx = ctx.find(o2)
        if idx <= 0:
            return None
    before = ctx[:idx].strip().split()
    return before[-1] if before else None


# The notebook's relation cascade emits an open tail of ~200 natural voiced-verb
# predicates. relation_phrases.json only hand-tunes ~56 of them; the rest used to
# fall through to `phrases.get(pred, {})` -> ok_prep == {} -> the prep check below
# false-flagged every locative/instrumental fact ("X DITARUH_DI Y", object after
# "di") as suspicious and dumped it to the review queue at LOW confidence. This
# derives a sane ok_prep + template from the predicate's own morphology so those
# facts are scored on their merits. relation_phrases.json still wins when present.
_DERIVED_SUFFIX_PREPS = [
    ("_KE_DALAM", ["ke dalam", "ke", "dalam", "masuk"], "ke dalam"),
    ("_DI_ATAS", ["di atas", "di", "pada", "atas"], "di atas"),
    ("_DI_SAMPING", ["di samping", "di", "pada", "samping"], "di samping"),
    ("_MELALUI", ["melalui", "lewat"], "melalui"),
    ("_KEPADA", ["kepada", "pada", "ke", "bagi", "untuk"], "kepada"),
    ("_DARI", ["dari"], "dari"),
    ("_DENGAN", ["dengan", "oleh", "memakai", "menggunakan"], "dengan"),
    ("_UNTUK", ["untuk", "bagi", "sebagai", "agar", "supaya"], "untuk"),
    ("_SEBAGAI", ["sebagai", "selaku", "menjadi", "untuk"], "sebagai"),
    ("_PADA", ["pada", "di", "ke", "kepada", "atas"], "pada"),
    ("_OLEH", ["oleh"], "oleh"),
    ("_KE", ["ke", "menuju", "kepada"], "ke"),
    ("_DI", ["di", "pada", "ke", "atas", "dalam"], "di"),
    ("_SEBELUM", ["sebelum", "menjelang"], "sebelum"),
    ("_SETELAH", ["setelah", "sesudah", "usai"], "setelah"),
    ("_SAAT", ["saat", "pada", "ketika", "waktu", "menjelang", "kala"], "saat"),
    ("_MENJADI", ["menjadi", "jadi", "ke"], "menjadi"),
    ("_BAGAIKAN", ["bagaikan", "bagai", "seperti", "laksana"], "bagaikan"),
]


def derived_phrase_spec(pred):
    """A fallback {template, ok_prep} for an open-tail predicate with no explicit
    relation_phrases.json entry, inferred from its name."""
    spaced = pred.replace("_", " ").lower().strip()
    for suffix, oks, connector in _DERIVED_SUFFIX_PREPS:
        if pred.endswith(suffix) and len(pred) > len(suffix):
            stem = pred[: -len(suffix)].replace("_", " ").lower().strip()
            return {"template": f"{{s}} {stem} {connector} {{o}}", "ok_prep": oks}
    if pred.startswith(("DI", "TER")):
        # passive form, no explicit case marker: a locative / instrumental /
        # agentive object after di/dengan/oleh/pada is normal, not suspect.
        return {"template": f"{{s}} {spaced} {{o}}",
                "ok_prep": ["dengan", "oleh", "di", "pada", "ke", "untuk", "dari"]}
    # active meN-/ber-/bare form: normally takes a bare direct object.
    return {"template": f"{{s}} {spaced} {{o}}", "ok_prep": []}


def phrase_spec(pred, phrases):
    """relation_phrases.json entry if hand-tuned, else a morphology-derived one."""
    return phrases.get(pred) or derived_phrase_spec(pred)


def main():
    rows = load_json(REL_JSON)
    resolver = Resolver()
    phrases = {k: v for k, v in load_json(PHRASES).items() if not k.startswith("_")}

    decisions = load_json(DECISIONS) if DECISIONS.exists() else {}

    surfaces = {r["subject"] for r in rows}
    surfaces |= {r["object"] for r in rows if r["object_type"] == "ENTITY"}
    passages, glossary_defs, faqs = build_passages(resolver, surfaces)

    # ---- entity aggregation -------------------------------------------------
    ent = {}   # id -> record under construction

    def get_ent(surface):
        eid, canon, method, bid, bname = resolver.resolve(surface)
        if eid not in ent:
            ent[eid] = {
                "id": eid, "name": canon, "type": None,
                "aliases": set(), "source_strings": set(),
                "labels": Counter(), "broader": bid, "broader_name": bname,
                "definition": None, "definition_source": None,
                "attributes": defaultdict(list),
                "resolve_method": method,
            }
        e = ent[eid]
        e["source_strings"].add(surface)
        if surface != canon.lower() and not is_deictic_alias(surface, resolver.deictic_words):
            e["aliases"].add(surface)
        if bid and not e["broader"]:
            e["broader"], e["broader_name"] = bid, bname
        return e

    def weak_literal(v):
        """a literal value too thin / fragmentary to keep as a fact."""
        toks = v.split()
        if len(v) < 5 or not any(len(t) >= 4 for t in toks):
            return True
        if not re.search(r"[a-z]{3}", v.lower()):
            return True
        return False

    dropped_literals = 0
    for r in rows:
        # honor review_decisions.json "reject" here too, not just in the
        # relation-scoring loop below -- otherwise a rejected triple's object
        # (often a garbled/fabricated noun phrase, e.g. a negated clause
        # mangled into a fake entity) still gets created via get_ent() and
        # keeps its automatic broader-link side effect, even though the
        # relation itself never makes it into relations.jsonl.
        if decisions.get(f"{r['sentence_id']}|{r['subject']}|{r['object']}") == "reject":
            continue
        se = get_ent(r["subject"])
        if r.get("subject_label"):
            se["labels"][r["subject_label"]] += 1

        if r["object_type"] == "ENTITY":
            oe = get_ent(r["object"])
            if r.get("object_label"):
                oe["labels"][r["object_label"]] += 1
        else:                                   # LITERAL
            val = r["object"].strip()
            if r["relation"] in ("BERARTI", "ADALAH"):
                sid = f"S{r['sentence_id']}"
                # definition candidate: keep the longest that reads like a
                # definition (a glossary hit still overrides this later), unless
                # this specific sentence is a known mis-attribution.
                if sid not in resolver.bad_definition_sentences and len(val) >= 15 and (
                    not se["definition"] or len(val) > len(se["definition"])
                ):
                    se["definition"] = val
                    se["definition_source"] = f"relation:S{r['sentence_id']}"
            elif weak_literal(val):
                dropped_literals += 1
            else:
                se["attributes"][r["relation"]].append(
                    {"value": val, "sentence_id": r["sentence_id"]})

    # glossary + broader definitions win / fill
    #
    # Resolve each glossary term through the same Resolver (force_merge/alias-aware)
    # used everywhere else, instead of string-matching the entity's post-merge name or
    # an arbitrary single source string against the glossary's raw (pre-merge) spelling
    # -- e.g. a "Panca Maha Bhuta:" glossary line needs to land on the merged
    # "pancamahabutha" entity, which plain string comparison never matched.
    # A Glosarium term that never appeared as a relation-extraction subject/object
    # (e.g. "Pertiwi (Bumi)" -- only in a bullet list the dependency-rule
    # extractor never turned into a row) had no entity in `ent` to attach its
    # definition to and was silently dropped, with no warning and no trace in
    # entities.json at all. get_ent() is the exact same entity-creation path
    # relation-extraction rows use, so reuse it here instead of losing the term.
    glossary_by_id: dict[str, str] = {}
    for term, dfn in glossary_defs.items():
        eid = resolver.resolve(term)[0]
        if eid not in ent:
            get_ent(term)
        glossary_by_id.setdefault(eid, dfn)
    for e in ent.values():
        g = glossary_by_id.get(e["id"])
        if g:
            e["definition"], e["definition_source"] = g, "glossary"

    # types
    for e in ent.values():
        gt = resolver.gaz_type(e["name"])
        if gt:
            e["type"] = gt
        elif e["labels"]:
            e["type"] = e["labels"].most_common(1)[0][0]
    for e in ent.values():
        if not e["type"] and e["broader"] in ent:
            e["type"] = ent[e["broader"]]["type"]
        if not e["type"]:
            e["type"] = "ISTILAH_UMUM_RITUAL"

    # passage mentions
    mentions = defaultdict(list)
    for p in passages:
        for eid in p["entity_ids"]:
            mentions[eid].append(p["id"])

    # ---- fact / relation scoring -----------------------------------------
    relations, facts, review = [], [], []
    HIGH_PREDS = {"BAGIAN_DARI", "BERADA_DI", "DIPERSEMBAHKAN_KEPADA",
                  "DIHANYUTKAN_KE", "MELAMBANGKAN", "DIGUNAKAN_UNTUK",
                  "SEBELUM", "SETELAH", "MENJELANG", "DISAMBUNG_DENGAN",
                  "DIGANTI_DENGAN", "DIAKHIRI_DENGAN", "DIKENAL_SEBAGAI",
                  "ADALAH", "DIPAKAI_UNTUK", "DITUJUKAN_UNTUK", "TERDIRI_DARI",
                  "TERBUAT_DARI", "DILETAKKAN_DI", "DILAKUKAN_SAAT",
                  "BERASAL_DARI", "DIBAWA_KE", "MENUJU", "DIBUAT_DI",
                  "DIBUNGKUS_DENGAN", "DIIKAT_DENGAN", "DIGULUNG_DENGAN",
                  "DISIRAM_DENGAN", "DIALASI_DENGAN", "DIPAKAIKAN", "DIKUBUR",
                  "DIBAKAR", "DIMANDIKAN", "DITABURKAN", "DIPUJA",
                  "BERPERAN_SEBAGAI", "BERFUNGSI_SEBAGAI", "BERDASARKAN",
                  "MENURUT", "DIMOHON_DARI", "DIPEROLEH_DARI", "DIBERI"}
    MED_PREDS = {"MEMILIKI", "DISERTAI", "DIPERLAKUKAN_SEPERTI",
                 "BERWUJUD", "BERTUJUAN_UNTUK", "MENGGUNAKAN", "MEMAKAI",
                 "MEMPEROLEH", "DIUSUNG", "DIAMBIL", "DIBONGKAR",
                 "DILAKUKAN_DENGAN", "DILAKUKAN_DI", "DILAKUKAN_OLEH"}
    # verbs the dependency extractor gets wrong often -- only MED when both
    # endpoints resolve cleanly and nothing else is off, otherwise LOW.
    ERROR_PRONE = {"MENJADI", "MENGALAMI", "MENSYARATKAN", "BERPENGARUH_PADA",
                   "MENINGKAT_KE", "MENGHASILKAN", "MEWAJIBKAN",
                   "MENGHILANGKAN", "MENENTUKAN"}

    def mentioned(ctx, name):
        ctx = ctx.lower()
        return any(w for w in name.lower().split() if len(w) > 3 and w in ctx)

    for r in rows:
        if r["object_type"] != "ENTITY":
            continue
        pred = r["relation"]
        subj, obj = r["subject"], r["object"]
        dkey = f"{r['sentence_id']}|{subj}|{obj}"
        decision = decisions.get(dkey, "")
        if decision == "reject":
            continue
        if decision.startswith("fix:"):
            parts = [p.strip() for p in decision[4:].split("|")]
            if len(parts) == 3:
                subj, pred, obj = parts

        s_id, s_name, s_m, *_ = resolver.resolve(subj)
        o_id, o_name, o_m, *_ = resolver.resolve(obj)
        s_gaz = resolver.gaz_type(s_name) is not None or s_m != "unresolved"
        o_gaz = resolver.gaz_type(o_name) is not None or o_m != "unresolved"

        ctx = r.get("context_sentence", "")
        prep = object_preposition(ctx, obj)
        spec = phrase_spec(pred, phrases)
        ok_prep = set(spec.get("ok_prep", []))
        prep_bad = (prep in PREP_BEFORE_OBJ and prep not in ok_prep
                    and prep is not None)
        prep_fatal = prep == "tentang"

        reasons = []
        if not s_gaz and not o_gaz:
            reasons.append("neither endpoint resolves to a known entity")
        if pred == "LAINNYA":
            reasons.append("relation could not be classified (LAINNYA)")
        if prep_fatal:
            reasons.append("object follows 'tentang' in source -> not a relation")
        if prep_bad:
            reasons.append(f"object follows '{prep}' in source, unexpected for {pred}")
        if ctx and not mentioned(ctx, subj) and not mentioned(ctx, obj):
            reasons.append("source sentence mentions neither subject nor object")

        if r.get("source") == "object_decomposition" and not (s_gaz and o_gaz):
            reasons.append("decomposed sub-relation with an unresolved endpoint")

        clean = s_gaz and o_gaz and not prep_bad and not prep_fatal

        if decision == "accept" or decision.startswith("fix:"):
            conf = "HIGH" if clean else "MED"
            reasons = []
        elif str(r.get("source", "")).startswith("manual_"):
            conf = "HIGH"                     # hand-authored (override / edit / addition)
        elif reasons:
            conf = "LOW"
        elif clean and pred in HIGH_PREDS:
            conf = "HIGH"
        elif clean and pred in ERROR_PRONE:
            conf = "MED"
        elif pred in ERROR_PRONE:
            conf = "LOW"
            reasons.append(f"error-prone predicate ({pred}) with an unresolved endpoint")
        elif (s_gaz or o_gaz) or pred in MED_PREDS:
            conf = "MED"
        else:
            conf = "LOW"
            reasons.append("weak predicate / unresolved endpoint")

        tmpl = spec.get("template", "{s} " + pred.lower() + " {o}")
        nl = tmpl.format(s=s_name, o=o_name)

        rel = {
            "subject_id": s_id, "subject_name": s_name,
            "predicate": pred,
            "object_id": o_id, "object_name": o_name,
            "confidence": conf,
            "nl": nl,
            "raw_relation": r.get("raw_relation"),
            "provenance": {"sentence_id": r["sentence_id"],
                           "context_sentence": r.get("context_sentence", "")},
        }
        relations.append(rel)

        if conf in ("HIGH", "MED"):
            facts.append({
                "id": f"f{r['sentence_id']}_{s_id[:10]}_{o_id[:10]}",
                "text": nl + ".",
                "subject_id": s_id, "predicate": pred, "object_id": o_id,
                "confidence": conf,
                "source_sentence": r.get("context_sentence", ""),
                "sentence_id": r["sentence_id"],
            })
        else:
            review.append({
                "kind": "low_confidence_edge",
                "key": dkey,
                "reasons": reasons,
                "subject": r["subject"], "predicate": r["relation"],
                "raw_relation": r.get("raw_relation"),
                "object": r["object"],
                "rendered": nl,
                "source_sentence": r.get("context_sentence", ""),
                "sentence_id": r["sentence_id"],
                "decision": decision,
                "decision_hint": "accept | reject | fix: <subject> | <PREDICATE> | <object>",
            })

    # ---- finalize entities ------------------------------------------------
    def dedupe_attr(items):
        seen, out = set(), []
        for it in items:
            if it["value"] not in seen:
                seen.add(it["value"])
                out.append(it)
        return out

    ent_out, fragment_ents = [], []
    for e in sorted(ent.values(), key=lambda x: x["id"]):
        rec = {
            "id": e["id"],
            "name": e["name"],
            "type": e["type"],
            "aliases": sorted(e["aliases"]),
            "definition": e["definition"],
            "definition_source": e["definition_source"],
            "broader": e["broader"] if e["broader"] in ent else None,
            "attributes": {k: dedupe_attr(v) for k, v in sorted(e["attributes"].items())},
            "mention_passages": sorted(set(mentions.get(e["id"], []))),
            "resolve_method": e["resolve_method"],
            "n_source_strings": len(e["source_strings"]),
        }
        if (e["resolve_method"] == "unresolved"
                and looks_fragment(e["name"], e["type"])):
            fragment_ents.append(rec)
            review.append({
                "kind": "fragment_entity",
                "reasons": ["surface string looks like a sentence fragment, "
                            "not an entity name"],
                "name": e["name"], "type": e["type"],
                "source_strings": sorted(e["source_strings"]),
                "decision": "",
            })
        else:
            ent_out.append(rec)

    # ---- write ----------------------------------------------------------
    (HERE / "entities.json").write_text(
        json.dumps(ent_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dump_jsonl(HERE / "relations.jsonl", relations)
    dump_jsonl(HERE / "facts.jsonl", facts)
    dump_jsonl(HERE / "passages.jsonl", passages)
    dump_jsonl(HERE / "review_queue.jsonl", review)
    write_glossary(ent_out, relations)
    write_report(rows, ent_out, passages, relations, facts, review, resolver,
                 len(fragment_ents))

    print(f"entities   : {len(ent_out)}  (+{len(fragment_ents)} fragments -> review)")
    print(f"relations  : {len(relations)}  (HIGH/MED facts {len(facts)}, review {len(review)})")
    print(f"passages   : {len(passages)}   (weak literal values dropped: {dropped_literals})")
    print(f"wrote {HERE}\\entities.json, relations.jsonl, facts.jsonl, "
          f"passages.jsonl, review_queue.jsonl, glossary.md, build_report.txt")


def write_glossary(ent_out, relations):
    out_edges = defaultdict(list)
    for r in relations:
        if r["confidence"] != "LOW":
            out_edges[r["subject_id"]].append(f'{r["predicate"].lower().replace("_", " ")} **{r["object_name"]}**')
    lines = ["# Ngaben Knowledge Base -- Glossary", "",
             f"{len(ent_out)} canonical entities. Generated by build_kb.py.", ""]
    by_type = defaultdict(list)
    for e in ent_out:
        by_type[e["type"]].append(e)
    for typ in sorted(by_type):
        lines.append(f"## {typ}")
        lines.append("")
        for e in sorted(by_type[typ], key=lambda x: x["name"]):
            head = f"**{e['name']}**"
            if e["broader"]:
                head += f"  _(-> {e['broader']})_"
            lines.append(f"### {head}")
            if e["definition"]:
                lines.append(f"{e['definition']}")
            if e["aliases"]:
                lines.append(f"*juga:* {', '.join(e['aliases'])}")
            for rel, vals in e["attributes"].items():
                joined = '; '.join(a["value"] for a in vals)
                lines.append(f"- {rel.lower().replace('_', ' ')}: {joined}")
            for edge in out_edges.get(e["id"], []):
                lines.append(f"- {edge}")
            lines.append("")
    (HERE / "glossary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(rows, ent_out, passages, relations, facts, review, resolver,
                 n_fragments=0):
    L = []
    a = L.append
    a("=" * 74)
    a("NGABEN KNOWLEDGE BASE -- BUILD REPORT")
    a("=" * 74)
    a(f"input rows (normalized)   : {len(rows)}")
    a(f"canonical entities        : {len(ent_out)}")
    a(f"  fragments -> review     : {n_fragments}")
    a(f"  with a definition       : {sum(1 for e in ent_out if e['definition'])}")
    a(f"  with a broader link     : {sum(1 for e in ent_out if e['broader'])}")
    a(f"  unresolved (kept as-is) : {sum(1 for e in ent_out if e['resolve_method'] == 'unresolved')}")
    a(f"passages                  : {len(passages)}")
    a(f"  glossary / faq          : {sum(1 for p in passages if p.get('kind') == 'glossary')}"
      f" / {sum(1 for p in passages if p.get('kind') == 'faq')}")
    a(f"relations (entity edges)  : {len(relations)}")
    conf = Counter(r["confidence"] for r in relations)
    a(f"  HIGH / MED / LOW        : {conf['HIGH']} / {conf['MED']} / {conf['LOW']}")
    a(f"facts.jsonl (HIGH+MED)    : {len(facts)}")
    a(f"review_queue.jsonl        : {len(review)}")
    a("")
    a("entity types")
    a("-" * 40)
    for t, c in Counter(e["type"] for e in ent_out).most_common():
        a(f"  {c:4}  {t}")
    a("")
    a("predicates in relations.jsonl")
    a("-" * 40)
    for p, c in Counter(r["predicate"] for r in relations).most_common():
        hi = sum(1 for r in relations if r["predicate"] == p and r["confidence"] == "HIGH")
        a(f"  {c:4}  {p:22} (HIGH {hi})")
    a("")
    a("review-queue reasons")
    a("-" * 40)
    rc = Counter(reason for r in review for reason in r.get("reasons", []))
    for reason, c in rc.most_common():
        a(f"  {c:4}  {reason}")
    a("")
    a("unresolved entities (add to concept map / gazetteer / entity_resolution.json)")
    a("-" * 40)
    for e in ent_out:
        if e["resolve_method"] == "unresolved":
            a(f"  {e['name']!r:40} type={e['type']}  aliases={e['aliases']}")
    (HERE / "build_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())

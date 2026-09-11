"""Custom actions for the Ngaben glossary + relationship bot.

Pipeline per action:
  1. pull term(s) from entity / slot / free text
  2. resolve wording -> canonical entity id (kb_resolver, Python-side)
  3. parameterized Cypher against the KB Neo4j graph  (structure = source of truth)
  4. enrich with the curated KB layers (kb_content: facts, FAQ, glossary, predicate families)
  5. build a deterministic Indonesian answer
  6. optionally smooth it with the Groq layer (llm.rephrase), deterministic string as fallback
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Text

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kb_resolver import get_resolver  # noqa: E402
from kb_content import get_content, PREDICATE_FAMILIES  # noqa: E402
from llm import rephrase, llm_available  # noqa: E402

load_dotenv(find_dotenv())

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

TYPE_LABEL_ID = {
    "SARANA_RITUAL": "sarana / perlengkapan ritual",
    "ISTILAH_UMUM_RITUAL": "istilah umum ritual",
    "TAHAPAN_UPACARA": "tahapan upacara",
    "KONSEP_FILOSOFIS": "konsep filosofis",
    "BANGUNAN_RITUAL": "bangunan / tempat ritual",
    "ENTITAS_KEAGAMAAN": "entitas keagamaan",
    "RITUAL_KEMATIAN": "ritual kematian",
    "TIRTHA_SUCI": "jenis tirtha (air suci)",
    "KONSEP_HUKUM_ADAT": "konsep hukum adat",
    "NASKAH_SUCI": "naskah suci",
    "RITUAL": "ritual (yadnya)",
    "STRUKTUR_SOSIAL_ADAT": "struktur sosial adat",
    "PLACE": "tempat",
    "AGAMA": "tradisi keagamaan",
}

_RESERVED_PROPS = {"id", "name", "definition", "definition_source", "aliases"}

_FAMILY_LABEL = {
    "fungsi": "fungsi / kegunaan",
    "bahan": "bahan / wujud / isi",
    "lokasi": "tempat / arah",
    "waktu": "waktu pelaksanaan",
    "pelaku": "pelaku / pelaksana",
    "simbol": "makna simbolis",
}
_FAMILY_EMPTY = {
    "fungsi": "Basis data belum mencatat fungsi khusus",
    "bahan": "Basis data belum mencatat bahan atau wujud",
    "lokasi": "Basis data belum mencatat lokasi atau arah",
    "waktu": "Basis data belum mencatat waktu pelaksanaan",
    "pelaku": "Basis data belum mencatat siapa pelakunya",
    "simbol": "Basis data belum mencatat makna simbolis",
}


class Neo4jConnection:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            with self._driver.session() as session:
                return [r.data() for r in session.run(cypher, params or {})]
        except Exception:
            return []

    def close(self) -> None:
        self._driver.close()


neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
resolver = get_resolver()
content = get_content()

_NODE_CYPHER = """
MATCH (n:Node {id: $id})
OPTIONAL MATCH (n)-[:TERMASUK_JENIS]->(p:Node)
OPTIONAL MATCH (n)<-[:TERMASUK_JENIS]-(c:Node)
RETURN n.name       AS name,
       n.definition  AS definition,
       labels(n)     AS labels,
       n.aliases     AS aliases,
       properties(n) AS props,
       collect(DISTINCT p.name) AS parents,
       collect(DISTINCT c.name) AS children
"""


# -- shared helpers --------------------------------------------------------
def _human_type(labels: List[str]) -> str:
    for lb in labels or []:
        if lb not in ("Node", "Isolated"):
            return TYPE_LABEL_ID.get(lb, lb.lower().replace("_", " "))
    return "istilah"


def _entities(tracker: Tracker, names=("istilah", "istilah2")) -> List[str]:
    text = _text(tracker)
    raw = [e for e in tracker.latest_message.get("entities", [])
           if e.get("entity") in names and e.get("value")]
    with_span = [e for e in raw if e.get("start") is not None and e.get("end") is not None]
    without_span = [e for e in raw if e not in with_span]

    # RegexEntityExtractor and DIETClassifier can both tag the same mention, and
    # DIETClassifier can even split one multi-word term across adjacent single-word
    # spans (e.g. "ngaben" + "svasta" instead of one "ngaben svasta" entity). Merge
    # overlapping AND whitespace-adjacent same-type spans into one cluster, then take
    # the merged text straight from the original message so a truncated/split regex
    # or DIET match never wins over the correct full-length term.
    clusters: List[Dict[str, int]] = []
    for e in sorted(with_span, key=lambda e: e["start"]):
        s, en = e["start"], e["end"]
        merged = False
        for c in clusters:
            overlaps = s < c["end"] and en > c["start"]
            adjacent = s >= c["end"] and text[c["end"]:s].strip() == ""
            if overlaps or adjacent:
                c["start"] = min(c["start"], s)
                c["end"] = max(c["end"], en)
                merged = True
                break
        if not merged:
            clusters.append({"start": s, "end": en})

    values = [text[c["start"]:c["end"]] for c in sorted(clusters, key=lambda c: c["start"])]
    values += [e["value"] for e in without_span]
    return values


def _terms(tracker: Tracker) -> List[str]:
    vals = _entities(tracker)
    if not vals and tracker.get_slot("istilah"):
        vals = [tracker.get_slot("istilah")]
    return vals


def _text(tracker: Tracker) -> str:
    return (tracker.latest_message.get("text") or "").strip()


def _intent(tracker: Tracker) -> str:
    return (tracker.latest_message.get("intent") or {}).get("name", "")


def _tipe(tracker: Tracker) -> Optional[str]:
    val = next((e["value"] for e in tracker.latest_message.get("entities", [])
                if e.get("entity") == "tipe"), None)
    return val or tracker.get_slot("tipe")


def _fetch(match) -> Dict[str, Any]:
    rows = neo4j_conn.query(_NODE_CYPHER, {"id": match.id})
    if rows:
        return rows[0]
    # graph unreachable / not loaded -> fall back to the KB record the resolver holds
    e = match.entity
    return {
        "name": e["name"], "definition": e.get("definition"),
        "labels": ["Node", (e.get("type") or "").upper()], "aliases": e.get("aliases"),
        "props": {k: [i["value"] for i in v] for k, v in e.get("attributes", {}).items()},
        "parents": [e["broader"]] if e.get("broader") else [],
        "children": [c["name"] for c in resolver.by_id.values() if c.get("broader") == e["id"]],
    }


def _render_attributes(name: str, props: Dict[str, Any], limit: int = 5, only: Optional[set] = None) -> List[str]:
    out: List[str] = []
    for pred, values in (props or {}).items():
        if pred in _RESERVED_PROPS:
            continue
        if only is not None and pred.upper() not in only:
            continue
        vals = values if isinstance(values, list) else [values]
        for v in vals[:2]:
            if v:
                out.append(content.render_attr(pred, name, str(v)))
                if len(out) >= limit:
                    return out
    return out


def _say(dispatcher: CollectingDispatcher, raw: str, tracker: Tracker, smooth: bool = False) -> None:
    if smooth and llm_available():
        raw = rephrase(raw, fallback=raw, question=_text(tracker))
    dispatcher.utter_message(text=raw)


def _not_found(dispatcher, term: str) -> List:
    saran = resolver.suggest(term)
    msg = f'Maaf, saya tidak menemukan istilah "{term}" di basis data Ngaben.'
    if saran:
        msg += " Mungkin maksud Anda: " + ", ".join(saran) + "?"
    dispatcher.utter_message(text=msg)
    return []


def _ask_term(dispatcher) -> List:
    dispatcher.utter_message(text='Istilah mana yang Anda maksud? Contoh: "apa itu bade".')
    return []


def _one(tracker, dispatcher, use_slot_fallback: bool = True):
    """Resolve exactly one term from the message; return (match, r) or (None, None).

    use_slot_fallback=True lets a bare follow-up ("dimana?") reuse the term named in
    the previous turn (the `istilah` slot). Set it False for "apa itu X"-style intents,
    where the user is always naming a term this turn -- silently falling back to an
    unrelated earlier slot there produced answers about the wrong term entirely when
    the entity extractor failed to recognize an unknown/misspelled word.
    """
    ents = _entities(tracker)
    if ents:
        terms = ents
    elif use_slot_fallback and tracker.get_slot("istilah"):
        terms = [tracker.get_slot("istilah")]
    else:
        # No entity was tagged this turn -- peel the question wrapper ("apa itu X" ->
        # "x") so a not-found message shows the term itself, not the whole sentence.
        cleaned = resolver.clean_query(_text(tracker))
        terms = [cleaned] if cleaned else []
    if not terms:
        _ask_term(dispatcher)
        return None, None
    m = resolver.resolve(terms[0])
    if not m:
        _not_found(dispatcher, terms[0])
        return None, None
    return m, _fetch(m)


def _fuzzy_note(match) -> str:
    return f'\n\n_(saya menafsirkan pertanyaan Anda sebagai "{match.name}")_' if match.via == "fuzzy" else ""


# -- definisi -------------------------------------------------------------
class ActionDefinisi(Action):
    def name(self) -> Text:
        return "action_definisi"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        m, r = _one(tracker, dispatcher, use_slot_fallback=False)
        if not m:
            return []
        _say(dispatcher, self._card(r, m), tracker)
        return []

    @staticmethod
    def _card(r: Dict[str, Any], match) -> str:
        name = r["name"]
        parts = [f"*{name}* — {_human_type(r.get('labels') or [])}"]

        definition = content.best_definition(match.id, r.get("definition"))
        if definition:
            parts.append(f"\n\n{definition}")
        else:
            parts.append("\n\nBelum ada definisi ringkas untuk istilah ini; berikut yang tercatat:")

        parents = [p for p in (r.get("parents") or []) if p] or (
            [match.entity["broader"]] if match.entity.get("broader") else [])
        if parents:
            parts.append(f"\nTermasuk / bagian dari: {', '.join(parents)}")

        children = [c for c in (r.get("children") or []) if c]
        if children:
            shown = ", ".join(children[:8])
            more = f" (+{len(children) - 8} lainnya)" if len(children) > 8 else ""
            parts.append(f"\nJenis/bentuk yang tercatat: {shown}{more}")

        attrs = _render_attributes(name, r.get("props") or {}, limit=5)
        facts = content.facts_for(match.id, limit=6)
        extra: List[str] = []
        for line in attrs + facts:
            low = line.rstrip(".").lower()
            if line not in extra and (not definition or low not in definition.lower()):
                extra.append(line)
        for line in extra[:6]:
            parts.append(f"\n• {line}")

        faqs = content.faq_for(match.id)
        if faqs:
            q = faqs[0]
            parts.append(f"\n\n{q.get('question','').strip()}\n   {q.get('answer','').strip()}")

        alias_src = r.get("aliases") or match.entity.get("aliases") or []
        aliases = [a for a in alias_src if a and a.lower() != name.lower()]
        if aliases:
            parts.append(f"\n\nDikenal juga sebagai: {', '.join(aliases[:6])}")

        parts.append(_fuzzy_note(match))
        parts.append("\n\n_Sumber: Knowledge Graph Ngaben_")
        return "".join(parts)


# -- klasifikasi ---------------------------------------------------------
class ActionKlasifikasi(Action):
    def name(self) -> Text:
        return "action_klasifikasi"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        m, r = _one(tracker, dispatcher, use_slot_fallback=False)
        if not m:
            return []
        name = r.get("name", m.name)
        tipe = _human_type(r.get("labels") or [])
        parts = [f"*{name}* tergolong *{tipe}* di basis data Ngaben."]
        parents = [p for p in (r.get("parents") or []) if p]
        if parents:
            parts.append(f"\nTermasuk jenis / bagian dari: {', '.join(parents)}.")
        for f in content.facts_for(m.id, limit=8):
            if f.lower().startswith(name.lower()) and any(
                k in f.lower() for k in ("adalah bagian dari", "adalah ", "termasuk", "dikenal sebagai")
            ):
                parts.append(f"\n• {f}")
        sib = neo4j_conn.query(
            """MATCH (n:Node {id:$id})-[:TERMASUK_JENIS]->(:Node)<-[:TERMASUK_JENIS]-(s:Node)
               WHERE s.id <> n.id RETURN collect(DISTINCT s.name) AS sibs""",
            {"id": m.id},
        )
        sibs = (sib[0]["sibs"] if sib else []) or []
        if sibs:
            parts.append(f"\nSekelompok dengan: {', '.join(sibs[:8])}.")
        if not parents and len(parts) == 1:
            parts.append("\nBasis data belum mencatat induk klasifikasi untuk istilah ini.")
        _say(dispatcher, "".join(parts) + _fuzzy_note(m), tracker, smooth=True)
        return []


# -- jenis / subtipe ---------------------------------------------------
class ActionJenis(Action):
    def name(self) -> Text:
        return "action_jenis"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        m, r = _one(tracker, dispatcher)
        if not m:
            return []
        name = r.get("name", m.name)
        children = [c for c in (r.get("children") or []) if c]
        fam_facts = [f for f in content.facts_for(m.id, limit=12) if any(
            k in f.lower() for k in ("terdiri dari", "meliputi", "memiliki jenis", f"bagian dari {name.lower()}")
        )]
        if children:
            shown = ", ".join(children[:12])
            more = f" (+{len(children) - 12} lagi)" if len(children) > 12 else ""
            msg = f"Jenis / bentuk *{name}* yang tercatat: {shown}{more}."
        elif fam_facts:
            msg = f"Yang tercatat tentang bagian/jenis *{name}*:\n" + "\n".join(f"• {f}" for f in fam_facts[:6])
        else:
            tipe = _human_type(r.get("labels") or [])
            peers = [e["name"] for e in resolver.list_type(tipe) if e["id"] != m.id][:12]
            msg = (f"Basis data belum merinci jenis *{name}*. Istilah segolongan ({tipe}): "
                   f"{', '.join(peers)}." if peers else f"Basis data belum merinci jenis *{name}*.")
        _say(dispatcher, msg + _fuzzy_note(m), tracker)
        return []


# -- targeted attribute questions (fungsi/bahan/lokasi/waktu/pelaku/simbol) --
class ActionAtribut(Action):
    def name(self) -> Text:
        return "action_atribut"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        m, r = _one(tracker, dispatcher)
        if not m:
            return []
        family = _intent(tracker).replace("tanya_", "") or "fungsi"
        if family not in PREDICATE_FAMILIES:
            family = "fungsi"
        name = r.get("name", m.name)
        preds = {p.upper() for p in PREDICATE_FAMILIES[family]}

        lines: List[str] = []
        for x in _render_attributes(name, r.get("props") or {}, limit=6, only=preds):
            if x not in lines:
                lines.append(x)
        for x in content.facts_in_family(m.id, family, limit=6):
            if x not in lines:
                lines.append(x)

        label = _FAMILY_LABEL.get(family, family)
        if lines:
            body = f"*{name}* — {label}:\n" + "\n".join(f"• {x}" for x in lines[:7])
        else:
            body = f"{_FAMILY_EMPTY.get(family)} untuk *{name}*."
            generic = content.facts_for(m.id, limit=4)
            if generic:
                body += " Namun yang tercatat:\n" + "\n".join(f"• {g}" for g in generic)
        _say(dispatcher, body + _fuzzy_note(m), tracker, smooth=True)
        return []


# -- relasi ------------------------------------------------------------
class ActionRelasi(Action):
    def name(self) -> Text:
        return "action_relasi"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        matches = resolver.resolve_many(_text(tracker), limit=2)
        if len(matches) < 2:
            terms = _terms(tracker)
            if not terms and not matches:
                return _ask_term(dispatcher)
            if terms and not matches:
                m = resolver.resolve(terms[0])
                if not m:
                    return _not_found(dispatcher, terms[0])
                matches = [m]

        if len(matches) >= 2:
            a, b = matches[0], matches[1]
            lines = [f"*{a.name}* & *{b.name}*"]
            link = neo4j_conn.query(
                """MATCH (x:Node {id:$a})-[r]-(y:Node {id:$b})
                   WHERE coalesce(r.confidence,'') <> 'LOW'
                   RETURN type(r) AS rel, startNode(r).id AS s""",
                {"a": a.id, "b": b.id},
            )
            for row in link:
                s_name, o_name = (a.name, b.name) if row["s"] == a.id else (b.name, a.name)
                lines.append("\n• " + content.render(row["rel"], s_name, o_name))
            for f in content.facts_for(a.id, limit=25):
                if b.name.lower() in f.lower() and ("\n• " + f) not in lines:
                    lines.append(f"\n• {f}")
            shared = neo4j_conn.query(
                """MATCH (x:Node {id:$a})-[:TERMASUK_JENIS]->(p:Node)<-[:TERMASUK_JENIS]-(y:Node {id:$b})
                   RETURN collect(DISTINCT p.name) AS p""",
                {"a": a.id, "b": b.id},
            )
            if shared and shared[0]["p"]:
                lines.append(f"\n• Sama-sama tergolong: {', '.join(shared[0]['p'])}")
            if len(lines) == 1:
                lines.append("\nBasis data tidak mencatat hubungan langsung antara keduanya.")
            _say(dispatcher, "".join(lines), tracker, smooth=True)
            return []

        m = matches[0]
        r = _fetch(m)
        name = r.get("name", m.name)
        lines = [f"Yang tercatat tentang *{name}*:"]
        seen: List[str] = []
        for line in _render_attributes(name, r.get("props") or {}, limit=8) + content.facts_for(m.id, limit=12):
            if line not in seen:
                seen.append(line)
                lines.append(f"\n• {line}")
        faqs = content.faq_for(m.id)
        if faqs:
            q = faqs[0]
            lines.append(f"\n\n{q.get('question','').strip()}\n   {q.get('answer','').strip()}")
        if len(lines) == 1:
            lines.append("\nBelum ada relasi atau atribut yang tercatat.")
        lines.append("\n\n_Sumber: Knowledge Graph Ngaben_")
        _say(dispatcher, "".join(lines) + _fuzzy_note(m), tracker)
        return []


# -- alasan / "kenapa" -> FAQ ---------------------------------------
class ActionAlasan(Action):
    def name(self) -> Text:
        return "action_alasan"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        terms = _terms(tracker)
        m = resolver.resolve(terms[0]) if terms else None
        # Prefer FAQs curated for the actual resolved term over a free-text keyword
        # search across ALL faqs -- the latter often surfaces a tangentially-worded
        # but unrelated FAQ just from shared common words (e.g. "ngaben", "saat").
        hits = content.faq_for(m.id)[:2] if m else []
        if not hits:
            hits = content.faq_search(_text(tracker), k=2)
        if hits:
            blocks = [f"{h.get('question','').strip()}\n{h.get('answer','').strip()}" for h in hits]
            _say(dispatcher, "\n\n".join(blocks), tracker, smooth=True)
            return []
        if m:
            facts = content.facts_for(m.id, limit=6)
            if facts:
                _say(dispatcher, f"Yang tercatat tentang *{m.name}*:\n"
                     + "\n".join(f"• {f}" for f in facts), tracker, smooth=True)
                return []
        dispatcher.utter_message(
            text="Saya belum punya penjelasan 'mengapa' untuk hal itu di basis data. "
                 "Coba tanyakan artinya, misalnya \"apa itu nganyut\"."
        )
        return []


# -- daftar per kategori --------------------------------------------
class ActionDaftarIstilah(Action):
    def name(self) -> Text:
        return "action_daftar_istilah"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        tipe = _tipe(tracker)
        if not tipe:
            dispatcher.utter_message(
                text="Kategori yang bisa saya daftar: " + ", ".join(sorted(set(TYPE_LABEL_ID.values())))
                + '. Contoh: "sebutkan tahapan upacara ngaben".'
            )
            return []
        ents = resolver.list_type(tipe)
        if not ents:
            dispatcher.utter_message(
                text=f'Saya belum punya kategori "{tipe}". Coba: tahapan upacara, sarana ritual, '
                     "tirtha, bangunan ritual, konsep filosofis, ritual kematian, hukum adat, naskah suci."
            )
            return []
        ents.sort(key=lambda e: (e.get("definition") is None, e["name"]))
        names = [e["name"] for e in ents]
        shown = names[:20]
        more = f"\n… dan {len(names) - 20} istilah lain (tanyakan satu per satu untuk detail)." if len(names) > 20 else ""
        dispatcher.utter_message(
            text=f"Istilah bertipe *{tipe}* ({len(names)} total):\n" + ", ".join(shown) + more
        )
        return []


# -- bandingkan ----------------------------------------------------
class ActionBandingkan(Action):
    def name(self) -> Text:
        return "action_bandingkan"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        raw_terms = [t for t in _terms(tracker) if t]
        matches = list(resolver.resolve_many(_text(tracker), limit=2))
        if len(matches) < 2:
            for t in raw_terms:
                mm = resolver.resolve(t)
                if mm:
                    matches.append(mm)
        uniq: Dict[str, Any] = {}
        for mm in matches:
            uniq.setdefault(mm.id, mm)
        if len(uniq) == 1 and len(raw_terms) >= 2:
            mm = next(iter(uniq.values()))
            dispatcher.utter_message(
                text=f'*{raw_terms[0]}* dan *{raw_terms[1]}* sebenarnya istilah yang sama: keduanya merujuk ke *{mm.name}*.'
            )
            return []
        matches = list(uniq.values())
        if len(matches) < 2:
            dispatcher.utter_message(text='Sebutkan dua istilah, misalnya "apa beda bade dan wadah".')
            return []
        a, b = matches[0], matches[1]
        ra, rb = _fetch(a), _fetch(b)
        out = [f"*{a.name}* vs *{b.name}*"]
        for mm, rr in ((a, ra), (b, rb)):
            tipe = _human_type(rr.get("labels") or [])
            deff = content.best_definition(mm.id, rr.get("definition")) or "—"
            parents = ", ".join([p for p in (rr.get("parents") or []) if p]) or "—"
            key_facts = content.facts_for(mm.id, limit=2)
            out.append(f"\n\n*{mm.name}*\n• tipe: {tipe}\n• definisi: {deff}\n• termasuk: {parents}")
            for kf in key_facts:
                out.append(f"\n• {kf}")
        shared = neo4j_conn.query(
            """MATCH (x:Node {id:$a})-[:TERMASUK_JENIS]->(p:Node)<-[:TERMASUK_JENIS]-(y:Node {id:$b})
               RETURN collect(DISTINCT p.name) AS p""",
            {"a": a.id, "b": b.id},
        )
        if shared and shared[0]["p"]:
            out.append(f"\n\nKesamaan: sama-sama tergolong {', '.join(shared[0]['p'])}.")
        _say(dispatcher, "".join(out), tracker, smooth=True)
        return []


# -- cari / search -----------------------------------------------
class ActionCari(Action):
    def name(self) -> Text:
        return "action_cari"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        tipe = _tipe(tracker)
        if tipe:
            return ActionDaftarIstilah().run(dispatcher, tracker, domain)
        hits = resolver.search(_text(tracker), k=15)
        if not hits:
            dispatcher.utter_message(
                text="Tidak ada istilah yang cocok. Coba kata kunci lain, atau tanyakan kategori "
                     '(mis. "daftar sarana ritual").'
            )
            return []
        names = [h["name"] for h in hits]
        dispatcher.utter_message(
            text=f"{len(names)} istilah yang cocok:\n" + ", ".join(names[:15])
            + '\n\nTanyakan salah satunya, mis. "apa itu ' + names[0] + '".'
        )
        return []


# -- acak / random term ----------------------------------------
class ActionAcak(Action):
    def name(self) -> Text:
        return "action_acak"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        e = resolver.random_entity(with_definition=True)

        class _M:
            id = e["id"]; name = e["name"]; via = "exact"; entity = e
        _say(dispatcher, "Istilah acak:\n\n" + ActionDefinisi._card(_fetch(_M()), _M()), tracker)
        return []


# -- fallback --------------------------------------------------
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="Maaf, saya kurang paham. Saya bisa menjawab: arti istilah, klasifikasi, "
                 "jenis, fungsi, bahan, lokasi, waktu, pelaku, makna simbolis, hubungan antar-istilah, "
                 "daftar per kategori, perbandingan, dan pencarian istilah Ngaben. "
                 'Contoh: "apa itu tirtha pangentas", "bade dipakai untuk apa", '
                 '"apa beda bade dan wadah".'
        )
        return []

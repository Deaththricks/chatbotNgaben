"""Deterministic quality gate for entity definitions.

A router, not a filter: it flags a definition for human review, it never
silently applies or drops content. Consistent with the KB's existing
HIGH/MED/LOW confidence-then-review-queue philosophy (see README.md).

Used by definitions_to_review.py (Graphing/Neo4/definitions.json -> a new
glossary_draft_review batch / definition_review_queue.jsonl) and by
audit_existing_definitions.py (retroactive pass over entities.json's own
populated definitions).
"""
from __future__ import annotations

import re
from typing import List, Optional, Protocol

_MIN_LEN = 40

_BOILERPLATE_RE = re.compile(
    r"^(merupakan |adalah )?konsep filosofis yang (melambangkan|menyimbolkan|berarti|berwujud)\b",
    re.IGNORECASE,
)

# Common UTF-8-decoded-as-Latin-1(-ish) mojibake sequences/characters.
_MOJIBAKE_MARKERS = ("Ã", "Â", "â€™", "â€œ", "â€\x9d", "â€“", "ç", "�")

# A definition that's just a copula pointing at one bare term ("Adalah X."), or
# an explicit "mirip dengan X" / "sama dengan X" comparison -- circular/
# uninformative if X itself isn't a known entity.
_BARE_COPULA_RE = re.compile(
    r"^(adalah|berarti|merupakan|dikenal sebagai)\s+"
    r"([a-zA-ZÀ-ÿ\-]+(?:\s+[a-zA-ZÀ-ÿ\-]+){0,2})\.?$",
    re.IGNORECASE,
)
_CIRCULAR_REF_RE = re.compile(
    r"\b(?:mirip dengan|serupa dengan|sama dengan|seperti)\s+"
    r"([a-zA-ZÀ-ÿ\-]+(?:\s+[a-zA-ZÀ-ÿ\-]+){0,2})",
    re.IGNORECASE,
)


class _Resolves(Protocol):
    def resolve(self, text: str) -> Optional[object]: ...


def _circular_target(text: str) -> Optional[str]:
    m = _BARE_COPULA_RE.match(text.strip())
    if m:
        return m.group(2).strip(" .")
    m = _CIRCULAR_REF_RE.search(text)
    if m:
        return m.group(1).strip(" .")
    return None


def check_definition(definition: str, resolver: _Resolves) -> List[str]:
    """Return reasons this definition should route to human review (empty list
    = passes the gate). `resolver` needs a `.resolve(text) -> Optional[Match]`
    method that returns None for anything not a known KB entity -- pass a
    Chatbot/bot/kb_resolver.KbResolver instance."""
    reasons: List[str] = []
    text = (definition or "").strip()

    if not text:
        return ["empty"]

    if len(text) < _MIN_LEN:
        reasons.append(f"thin (<{_MIN_LEN} chars)")

    if _BOILERPLATE_RE.match(text):
        reasons.append("vague genus, no differentia (boilerplate pattern)")

    if any(marker in text for marker in _MOJIBAKE_MARKERS):
        reasons.append("possible encoding corruption (mojibake character)")

    target = _circular_target(text)
    if target:
        try:
            resolved = resolver.resolve(target)
        except Exception:
            resolved = "unknown"  # resolver call failed -- don't block on it
        if resolved is None:
            reasons.append(
                f"possible circular reference: points to '{target}', "
                f"which doesn't resolve to a known KB entity"
            )

    return reasons

"""Optional LLM rephrasing layer (Stage 6).

The knowledge graph stays the single source of truth. The LLM only turns the
deterministic bullet-point answer into smoother Indonesian prose. Every call site
must pass the deterministic string as `fallback` so that a missing key, a network
error, or a refusal degrades to the templated answer with no user-visible break.
"""
from .groq_client import rephrase, llm_available  # noqa: F401

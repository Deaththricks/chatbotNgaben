"""Find KB entries by meaning: every entry (name, other names, definition) is embedded once
with a local Ollama embedding model, and a message is compared to them by cosine similarity.

actions._meaning_match uses it for a message that describes a term instead of naming it
("keluargaku meninggal pas merantau jauh dan jenazahnya gak bisa dibawa pulang" is ngaben
svasta, "kakek udah lama dikubur, pas mau diaben tulangnya diambil gimana?" is ngangkid).
When a hit counts is decided there; this module only scores.

The embedding model (EMBED_MODEL, default bge-m3: `ollama pull bge-m3`) runs on the CPU
(num_gpu 0), so it never pushes the chat model off the GPU; one message takes ~0.1 s. The
entry vectors are cached in kb_embeddings.npz next to this file, keyed by the model and a hash
of the entry texts, so a KB rebuild re-embeds by itself -- a few minutes on the CPU, in a
background thread (or ahead of time: `python kb_semantic.py`). Until the index is ready, and
whenever Ollama or the model is missing, similarities() returns {} and the bot answers as it
did without it.

Chosen 2026-10-12 (batch_runs/reasoning-2026-10-09): qwen3-embedding:0.6b put the needed
entry in its top 10 for 3 of 9 described-not-named questions, bge-m3 for 8 of 9 and for 9 of
10 situation questions written afterwards.
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from dotenv import find_dotenv, load_dotenv
from ollama import Client

load_dotenv(find_dotenv())

_BOT_DIR = Path(__file__).resolve().parent
_CACHE = _BOT_DIR / "kb_embeddings.npz"
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
_CPU = {"num_gpu": 0}
_DEF_CHARS = 1500       # bge-m3 reads up to 8k tokens; the longest definitions run ~1.5k chars


class KbSemantic:
    def __init__(self, resolver, content, model: str = EMBED_MODEL, cache: Path = _CACHE) -> None:
        self.model, self.cache = model, cache
        self.ids: List[str] = []
        texts: List[str] = []
        for eid, e in resolver.by_id.items():
            definition = content.best_definition(eid) or ""
            if not definition:
                continue
            aliases = ", ".join((e.get("aliases") or [])[:6])
            texts.append(e["name"] + (f" ({aliases})" if aliases else "") + f": {definition[:_DEF_CHARS]}")
            self.ids.append(eid)
        self._texts = texts
        self.key = hashlib.sha1("\n".join([model] + texts).encode("utf-8")).hexdigest()
        self.vecs: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._building = False
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            with np.load(self.cache, allow_pickle=False) as z:
                if str(z["key"]) == self.key and list(z["ids"]) == self.ids:
                    self.vecs = z["vecs"]
        except (OSError, KeyError, ValueError):
            pass

    def _embed(self, texts: List[str], timeout: float) -> np.ndarray:
        client = Client(timeout=timeout)
        out = []
        for i in range(0, len(texts), 16):
            out += client.embed(model=self.model, input=texts[i:i + 16], options=_CPU)["embeddings"]
        v = np.asarray(out, dtype=np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)

    def ensure(self) -> None:
        """Build the index now unless the cache is current (blocking; batch and regression
        runs call it so their first questions get the meaning search too). On failure the
        message says why and similarities() stays empty."""
        if self.vecs is None:
            try:
                self.build()
            except Exception as e:
                print(f"kb_semantic: cannot build the index with {self.model} ({e}); "
                      f"`ollama pull {self.model}`? Meaning search is off for this run.")

    def build(self) -> None:
        """Embed every entry and write the cache (blocking)."""
        vecs = self._embed(self._texts, timeout=600)
        tmp = self.cache.with_suffix(".tmp.npz")
        np.savez(tmp, vecs=vecs, ids=np.asarray(self.ids), key=np.asarray(self.key))
        os.replace(tmp, self.cache)
        self.vecs = vecs

    def _build_in_background(self) -> None:
        with self._lock:
            if self._building or self.vecs is not None:
                return
            self._building = True

        def run() -> None:
            try:
                self.build()
            except Exception as e:      # Ollama down / model not pulled: retried on the next call
                print(f"kb_semantic: index build failed ({e})")
            finally:
                self._building = False
        threading.Thread(target=run, daemon=True).start()

    def similarities(self, text: str) -> Dict[str, float]:
        """Cosine similarity of `text` to every entry with a definition; {} while the index
        is being built or when the embedding model cannot be reached."""
        if self.vecs is None:
            self._build_in_background()
            return {}
        try:
            q = self._embed([text], timeout=10)[0]
        except Exception as e:
            print(f"kb_semantic: embedding failed ({e})")
            return {}
        return dict(zip(self.ids, (self.vecs @ q).tolist()))


_SEMANTIC: Optional[KbSemantic] = None


def get_semantic() -> KbSemantic:
    global _SEMANTIC
    if _SEMANTIC is None:
        from kb_content import get_content
        from kb_resolver import get_resolver
        _SEMANTIC = KbSemantic(get_resolver(), get_content())
    return _SEMANTIC


if __name__ == "__main__":
    import time
    s = get_semantic()
    if s.vecs is not None:
        print(f"{s.cache.name} is current ({len(s.ids)} entries, {s.model})")
    else:
        t0 = time.time()
        s.ensure()
        if s.vecs is not None:
            print(f"embedded {len(s.ids)} entries with {s.model} in {time.time() - t0:.0f} s -> {s.cache.name}")

"""Thin Groq wrapper for the rephrasing layer.

Key comes from the GROQ_API_KEY env var (see .env.example). If the key is absent
or the `groq` package is not installed, `rephrase()` returns the fallback string
unchanged and the bot runs fully deterministic.
"""
from __future__ import annotations

import os
from typing import List, Optional

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# current Groq-hosted models, best first; each is tried in order
_MODELS: List[str] = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

_SYSTEM = (
    "Anda adalah asisten glosarium upacara Ngaben (kremasi Bali). "
    "Anda akan diberi jawaban mentah berisi fakta dari sebuah basis pengetahuan. "
    "Tugas Anda HANYA merapikan jawaban itu menjadi 1-3 kalimat bahasa Indonesia "
    "yang mengalir dan sopan. ATURAN KERAS: jangan menambah fakta, angka, atau "
    "istilah baru; jangan berspekulasi; jangan menghapus fakta penting; "
    "pertahankan semua nama istilah persis seperti aslinya. Jika jawaban mentah "
    "menyatakan data tidak ada, sampaikan itu apa adanya."
)

_client = None
_init_failed = False


def llm_available() -> bool:
    return bool(_API_KEY) and not _init_failed


def _get_client():
    global _client, _init_failed
    if _client is not None or _init_failed:
        return _client
    if not _API_KEY:
        _init_failed = True
        return None
    try:
        from groq import Groq

        _client = Groq(api_key=_API_KEY)
    except Exception:
        _init_failed = True
        _client = None
    return _client


def rephrase(raw_answer: str, fallback: Optional[str] = None, question: str = "") -> str:
    """Return a smoothed version of `raw_answer`, or `fallback` on any problem."""
    fb = fallback if fallback is not None else raw_answer
    client = _get_client()
    if client is None:
        return fb

    user = raw_answer if not question else f"Pertanyaan pengguna: {question}\n\nJawaban mentah:\n{raw_answer}"
    for model in _MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=400,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception:
            continue
    return fb

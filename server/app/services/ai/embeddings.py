"""Turns text into vectors.

Uses OpenAI embeddings when a key is present, otherwise a deterministic local
hashing vectorizer. Callers never care which — but seed-time and runtime MUST use
the same provider so vectors are comparable (both keyed off ``settings.has_openai``).
"""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from app.config import settings
from app.domain.models import Series

LOCAL_EMBED_DIM = 256


@lru_cache(maxsize=1)
def _client() -> OpenAI | None:
    if not settings.has_openai:
        return None
    return OpenAI(api_key=settings.openai_key)


def _fnv1a(text: str) -> int:
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _tokenize(text: str) -> list[str]:
    cleaned = "".join(c if (c.isalnum() or c in " -") else " " for c in text.lower())
    return [t for t in cleaned.split() if len(t) > 1]


def local_embed(text: str, dim: int = LOCAL_EMBED_DIM) -> list[float]:
    """Deterministic hashing vectorizer with L2 normalization. Cosine between two
    such vectors approximates token overlap — good enough for the demo and fully
    reproducible."""
    vec = [0.0] * dim
    for token in _tokenize(text):
        vec[_fnv1a(token) % dim] += 1.0
    mag = sum(v * v for v in vec) ** 0.5
    if mag == 0:
        return vec
    return [v / mag for v in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = _client()
    if client is None:
        return [local_embed(t) for t in texts]
    res = client.embeddings.create(model=settings.embedding_model, input=texts)
    return [d.embedding for d in res.data]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def series_document(s: Series) -> str:
    """Canonical embedding 'document' for a series. Structured attributes are
    repeated so they dominate the vector — makes discovery respect
    genre/tone/language/pacing strongly under both providers."""

    def repeat(tokens: list[str], n: int) -> str:
        return " ".join([" ".join(tokens)] * n)

    # Structured attributes are heavily up-weighted so that under the local hash
    # embedding (no OpenAI) genre/tone/language dominate cosine similarity — this
    # keeps "similar series" and mood search coherent even with no API key.
    return " . ".join(
        [
            s.title,
            s.synopsis,
            repeat(s.genres, 8),
            repeat(s.tone, 6),
            repeat([s.language], 6),
            repeat([s.pacing], 3),
            repeat(s.tags, 2),
        ]
    )

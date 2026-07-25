"""Embedding service.

Primary path is OpenAI `text-embedding-3-small`. When no key is configured the
service falls back to a deterministic hashed bag-of-n-grams embedding so the whole
pipeline still runs offline. The active backend is always reported, never hidden.
"""

from __future__ import annotations

import asyncio
import hashlib

import numpy as np
from openai import APIError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.vectors import content_tokens, normalize

logger = get_logger(__name__)

_MAX_BATCH = 96
_MAX_CHARS = 8000


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncOpenAI | None = None
        self._dimensions = settings.active_embedding_dimensions
        self._degraded = False
        if settings.openai_enabled:
            self._client = AsyncOpenAI(
                api_key=settings.openai_secret,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )

    # --- introspection ------------------------------------------------------

    @property
    def dimensions(self) -> int:
        return self._settings.fallback_embedding_dimensions if self.using_fallback else self._dimensions

    @property
    def using_fallback(self) -> bool:
        return self._client is None or self._degraded

    @property
    def backend(self) -> str:
        return "hash-fallback" if self.using_fallback else f"openai:{self._settings.embedding_model}"

    def describe(self) -> dict:
        return {"backend": self.backend, "dimensions": self.dimensions, "degraded": self._degraded}

    # --- public API ---------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        vectors = await self.embed_many([text])
        return vectors[0] if vectors else []

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [(text or "").strip()[:_MAX_CHARS] or "empty" for text in texts]
        if self.using_fallback:
            return [self._hash_embedding(text) for text in cleaned]
        try:
            return await self._openai_embed(cleaned)
        except (APIError, RateLimitError, asyncio.TimeoutError) as exc:
            # Degrade for this process rather than failing the request. Reported via /health.
            logger.error("OpenAI embeddings unavailable, switching to hash fallback: %s", exc)
            self._degraded = True
            return [self._hash_embedding(text) for text in cleaned]

    # --- backends -----------------------------------------------------------

    async def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        assert self._client is not None
        batches = [texts[index : index + _MAX_BATCH] for index in range(0, len(texts), _MAX_BATCH)]
        results = await asyncio.gather(
            *(
                self._client.embeddings.create(model=self._settings.embedding_model, input=batch)
                for batch in batches
            )
        )
        vectors: list[list[float]] = []
        for response in results:
            vectors.extend(normalize(item.embedding) for item in response.data)
        return vectors

    def _hash_embedding(self, text: str) -> list[float]:
        """Signed hashing trick over unigrams + bigrams.

        Deterministic and dependency-free: the same text always yields the same
        vector, so offline demos produce reproducible similarity scores.
        """
        dimensions = self._settings.fallback_embedding_dimensions
        vector = np.zeros(dimensions, dtype=np.float32)
        words = content_tokens(text)
        if not words:
            return vector.tolist()
        grams = words + [f"{words[i]}_{words[i + 1]}" for i in range(len(words) - 1)]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return normalize(vector)

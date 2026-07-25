"""Centralised, typed access to environment configuration.

``has_openai`` is the single switch that flips the whole system between real
OpenAI-backed AI and the deterministic local-fallback used for offline demos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_url: str = os.getenv("DB_URL", "")
    port: int = int(os.getenv("PORT", "4000"))
    client_origin: str = os.getenv("CLIENT_ORIGIN", "http://localhost:3000")
    openai_key: str = (os.getenv("OPENAI_API_KEY") or "").strip()
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    @property
    def has_openai(self) -> bool:
        return len(self.openai_key) > 0


settings = Settings()

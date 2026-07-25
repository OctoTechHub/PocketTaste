"""LLM access with provider routing and a hard no-fabrication contract.

Two providers:
  * OpenAI (default)
  * Sarvam AI (opt-in, OpenAI-compatible) for Indic-language generations

Every call returns an `LlmResult` that states which backend produced it, so a
heuristic fallback can never be mistaken for a model output.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from openai import APIError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import LabelSource

logger = get_logger(__name__)

#: Prepended to every prompt. The single most important instruction in the service.
GROUNDING_RULES = (
    "You are an analyst inside a content-intelligence system.\n"
    "Hard rules:\n"
    "1. Use ONLY the numbers and facts present in the supplied context.\n"
    "2. Never invent statistics, user counts, percentages, revenue or trends.\n"
    "3. If the context is insufficient, say so explicitly instead of guessing.\n"
    "4. Do not claim anything about real-world platforms you were not given data for.\n"
    "5. Keep language plain and concrete."
)


@dataclass(slots=True)
class LlmResult:
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    source: LabelSource = LabelSource.HEURISTIC
    model: str = "none"
    ok: bool = False
    error: str | None = None


class LlmService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._openai: AsyncOpenAI | None = None
        self._sarvam: AsyncOpenAI | None = None
        self._degraded = False
        if settings.openai_enabled:
            self._openai = AsyncOpenAI(
                api_key=settings.openai_secret,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )
        if settings.sarvam_enabled:
            self._sarvam = AsyncOpenAI(
                api_key=settings.sarvam_api_key,
                base_url=settings.sarvam_base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=1,
            )

    # --- introspection ------------------------------------------------------

    @property
    def available(self) -> bool:
        return (self._openai is not None or self._sarvam is not None) and not self._degraded

    def describe(self) -> dict:
        return {
            "openai": self._settings.llm_model if self._openai else None,
            "sarvam": self._settings.sarvam_model if self._sarvam else None,
            "sarvam_languages": self._settings.sarvam_languages if self._sarvam else [],
            "degraded": self._degraded,
            "available": self.available,
        }

    def _route(self, language: str | None) -> tuple[AsyncOpenAI | None, str]:
        """Indic languages go to Sarvam when configured; everything else to OpenAI."""
        if language and self._sarvam and language.lower() in self._settings.sarvam_languages:
            return self._sarvam, self._settings.sarvam_model
        if self._openai:
            return self._openai, self._settings.llm_model
        if self._sarvam:
            return self._sarvam, self._settings.sarvam_model
        return None, "none"

    # --- public API ---------------------------------------------------------

    async def complete_json(
        self,
        prompt: str,
        *,
        language: str | None = None,
        system: str = GROUNDING_RULES,
        max_tokens: int = 900,
        temperature: float = 0.2,
    ) -> LlmResult:
        """Ask for a strict JSON object. Returns ok=False rather than raising."""
        client, model = self._route(language)
        if client is None or self._degraded:
            return LlmResult(text="", source=LabelSource.HEURISTIC, error="llm_unavailable")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = (response.choices[0].message.content or "").strip()
            return LlmResult(
                text=content,
                data=self._parse_json(content),
                source=LabelSource.LLM,
                model=model,
                ok=True,
            )
        except (APIError, RateLimitError, asyncio.TimeoutError) as exc:
            logger.error("LLM JSON call failed (%s): %s", model, exc)
            self._degraded = isinstance(exc, APIError) and getattr(exc, "status_code", 0) in (401, 403)
            return LlmResult(text="", source=LabelSource.HEURISTIC, error=str(exc)[:200])
        except json.JSONDecodeError as exc:
            return LlmResult(text="", source=LabelSource.HEURISTIC, error=f"bad_json: {exc}")

    async def complete_text(
        self,
        prompt: str,
        *,
        language: str | None = None,
        system: str = GROUNDING_RULES,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> LlmResult:
        client, model = self._route(language)
        if client is None or self._degraded:
            return LlmResult(text="", source=LabelSource.HEURISTIC, error="llm_unavailable")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return LlmResult(
                text=(response.choices[0].message.content or "").strip(),
                source=LabelSource.LLM,
                model=model,
                ok=True,
            )
        except (APIError, RateLimitError, asyncio.TimeoutError) as exc:
            logger.error("LLM text call failed (%s): %s", model, exc)
            return LlmResult(text="", source=LabelSource.HEURISTIC, error=str(exc)[:200])

    async def complete_json_many(
        self, prompts: list[str], *, language: str | None = None, concurrency: int = 6, **kwargs
    ) -> list[LlmResult]:
        """Bounded-concurrency fan-out; used by the content-intelligence agent."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _run(prompt: str) -> LlmResult:
            async with semaphore:
                return await self.complete_json(prompt, language=language, **kwargs)

        return list(await asyncio.gather(*(_run(prompt) for prompt in prompts)))

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        if not content:
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end <= start:
                return {}
            try:
                parsed = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return parsed if isinstance(parsed, dict) else {}

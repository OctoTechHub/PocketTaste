"""A fast outlining engine that keeps GOAT's structure without GOAT's latency.

GOAT-Storytelling-Agent is genuinely good at what it does: it refuses to write a whole
outline in one shot, and instead commits a book spec, then a three-act plot, then
enhances each act, so later chapters cannot contradict earlier ones. That staging is
the reason its outlines hold together.

It is also sequential by construction. Every stage waits for the one before it, so a
plain outline costs 2-5 round trips and a draft costs one more per scene. Measured
against gpt-4o-mini that is 12-20s for an outline and ~80s for a draft, and a creator
staring at a spinner does not care why.

This engine keeps the *shape* of GOAT's thinking and drops the round trips:

  * the same artefacts -- book spec, three acts, chapters with beats and hooks -- so
    the response is interchangeable with the GOAT path and the UI needs no branch;
  * one structured call instead of a chain, because a single model turn sees the whole
    outline at once and therefore cannot contradict itself the way a chain can;
  * scenes generated concurrently, each given the outline plus its neighbours, rather
    than serially threading the previous scene's tail.

What is lost is real: GOAT's `enhance_plot_chapters` pass genuinely deepens an act, and
its scene writer keeps tighter continuity because it reads the actual previous prose.
That is why the GOAT path stays available under `engine="goat"` rather than being
replaced -- this is the default because a fast outline a creator iterates on beats a
better one they never wait for.
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.llm import LlmService

logger = get_logger(__name__)

#: Mirrors GOAT's `init_book_spec` fields, so downstream parsing is unchanged.
_SPEC_FIELDS = ("Title", "Genre", "Setting", "Themes", "Premise", "Characters")

_OUTLINE_PROMPT = """You are a story architect for a long-form audio drama platform.

Return ONE JSON object. No prose outside it.

{{
  "spec": {{
    "Title": "...", "Genre": "...", "Setting": "...",
    "Themes": "...", "Premise": "...", "Characters": "..."
  }},
  "acts": [
    {{"act": 1, "summary": "..."}},
    {{"act": 2, "summary": "..."}},
    {{"act": 3, "summary": "..."}}
  ],
  "chapters": [
    {{"index": 0, "act": 1, "title": "...", "beat": "...", "hook": "..."}}
  ]
}}

Rules that matter:
- Exactly {chapters} chapters, index starting at 0, spread across the three acts.
- `beat` is what happens; `hook` is the unresolved question that makes someone press
  play on the next episode. A hook that resolves inside its own chapter is useless.
- Later chapters must build on earlier ones. Contradicting your own earlier chapter is
  the single worst failure here.
- Write in {language}. Character and place names must suit that language's audience.
- Genre: {genre}. {tone_line}

{avoid_line}

PREMISE
{premise}
"""

_SCENE_PROMPT = """Write chapter {index} of "{title}" as narrated audio-drama prose.

Chapter beat : {beat}
Ends on hook : {hook}
Comes after  : {previous}
Setting      : {setting}

Write {words} words in {language}. Scene prose only -- no headings, no summary, no
commentary. Open in the middle of something happening. End on the hook, unresolved.
"""


class FastStoryEngine:
    """GOAT's artefacts, one round trip."""

    def __init__(self, settings: Settings, llm: LlmService) -> None:
        self._settings = settings
        self._llm = llm

    @property
    def available(self) -> bool:
        """OpenAI specifically, not "some LLM".

        The router sends Indic languages to Sarvam, and Sarvam's chat model rejects
        `response_format: json_object` — so a structured outline in Hindi silently
        returned nothing until every call here was pinned to OpenAI.
        """
        return bool(self._llm.describe().get("openai"))

    def describe(self) -> dict:
        return {
            "name": "fast_openai",
            "available": self.available,
            "calls_per_outline": 1,
            "calls_per_draft": "1 + one per scene, run concurrently",
            "keeps_from_goat": [
                "book spec before plot",
                "three-act structure",
                "per-chapter beat and hook",
                "scene splitting",
            ],
            "drops_from_goat": [
                "enhance_plot_chapters (a second pass per act)",
                "serial scene continuity (scenes see the outline, not the previous prose)",
            ],
        }

    async def outline(
        self,
        *,
        premise: str,
        genre: str,
        language: str,
        tone: str,
        target_chapters: int,
        avoid: list[str],
    ) -> dict:
        prompt = _OUTLINE_PROMPT.format(
            chapters=target_chapters,
            language=language,
            genre=genre,
            premise=premise.strip(),
            tone_line=f"Tone: {tone}." if tone else "",
            avoid_line=(
                "The platform is already over-supplied with these patterns; do not "
                f"reproduce them: {', '.join(avoid)}."
                if avoid
                else ""
            ),
        )
        # provider="openai" is load-bearing: without it the router sends hi/ta/te/…
        # to Sarvam, which cannot honour a JSON response format.
        result = await self._llm.complete_json(
            prompt, provider="openai", max_tokens=2400, temperature=0.75
        )
        if not result.ok or not result.data:
            raise RuntimeError(result.error or "fast outline returned nothing")

        data = result.data
        spec = {field: str(data.get("spec", {}).get(field, "")) for field in _SPEC_FIELDS}
        chapters = self._clean_chapters(data.get("chapters"), target_chapters)
        if not chapters:
            raise RuntimeError("fast outline produced no chapters")

        return {
            "spec": spec,
            "acts": data.get("acts") or [],
            "chapters": chapters,
            "model": result.model,
            "calls": 1,
        }

    async def scenes(
        self,
        *,
        spec: dict,
        chapters: list[dict],
        language: str,
        count: int,
        words: int = 320,
    ) -> list[dict]:
        """Concurrent, because each scene is anchored by the outline rather than by the
        previous scene's text. Serial generation buys tighter continuity and costs the
        whole point of this engine."""
        wanted = chapters[: max(1, count)]

        async def write(position: int, chapter: dict) -> dict:
            previous = (
                chapters[position - 1]["beat"] if position > 0 else "nothing — this opens the story"
            )
            result = await self._llm.complete_text(
                _SCENE_PROMPT.format(
                    index=chapter["index"] + 1,
                    title=spec.get("Title") or "the story",
                    beat=chapter["beat"],
                    hook=chapter["hook"],
                    previous=previous,
                    setting=spec.get("Setting", ""),
                    words=words,
                    language=language,
                ),
                provider="openai",
                max_tokens=int(words * 2.2),
                temperature=0.85,
            )
            return {
                "chapter_index": chapter["index"],
                "title": chapter["title"],
                "text": result.text,
                "ok": result.ok,
            }

        return list(await asyncio.gather(*(write(i, ch) for i, ch in enumerate(wanted))))

    @staticmethod
    def _clean_chapters(raw: object, target: int) -> list[dict]:
        """Trust the model for prose, never for structure.

        Indices come back duplicated, one-based, or missing often enough that using
        them directly puts two chapters at the same position in the UI.
        """
        if not isinstance(raw, list):
            return []
        chapters: list[dict] = []
        for position, entry in enumerate(raw[:target]):
            if not isinstance(entry, dict):
                continue
            act = entry.get("act")
            chapters.append(
                {
                    "index": position,
                    "act": int(act) if isinstance(act, (int, float)) and 1 <= act <= 3 else min(3, position // max(1, target // 3) + 1),
                    "title": str(entry.get("title") or f"Chapter {position + 1}").strip(),
                    "beat": str(entry.get("beat") or "").strip(),
                    "hook": str(entry.get("hook") or "").strip(),
                }
            )
        return chapters

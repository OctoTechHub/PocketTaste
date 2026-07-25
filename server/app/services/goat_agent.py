"""Real GOAT-Storytelling-Agent integration.

Upstream: https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent

The package ships a genuinely good staged-outlining pipeline — book spec, three-act
plot, act-by-act enhancement, scene splitting — with prompts and parsers that have
clearly been iterated on. What it does *not* ship is a way to run without a
self-hosted GOAT-70B behind a HuggingFace TGI or llama.cpp server.

`StoryAgent` funnels every model call through one method, `query_chat(messages)`.
So we subclass it and override exactly that. Everything else — `prompts.py`,
`parse_book_spec`, `Plan.parse_text_plan`, the act-enhancement loop — is upstream
code running unmodified. We supply the transport; GOAT supplies the craft.

Two details worth knowing:

* We pass ``backend="llama.cpp"``. Not because we speak llama.cpp — we never touch
  ``backend_uri`` — but because ``backend="hf"`` eagerly downloads a LlamaTokenizerFast
  from the Hub in ``__init__``. The llama.cpp branch skips that, and since we replace
  ``query_chat`` outright, no llama.cpp code path is ever reached either.
* GOAT is synchronous and blocking. FastAPI runs it in a worker thread so the event
  loop keeps serving.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    from goat_storytelling_agent.plan import Plan
    from goat_storytelling_agent.storytelling_agent import StoryAgent

    GOAT_AVAILABLE = True
    GOAT_IMPORT_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 - the package is optional at runtime
    Plan = None  # type: ignore[assignment]
    StoryAgent = object  # type: ignore[assignment,misc]
    GOAT_AVAILABLE = False
    GOAT_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    logger.warning("GOAT-Storytelling-Agent unavailable (%s)", GOAT_IMPORT_ERROR)


class OpenAIBackedStoryAgent(StoryAgent):  # type: ignore[misc,valid-type]
    """GOAT's StoryAgent with its model transport swapped for our LLM client.

    Upstream calls `query_chat` with an OpenAI-shaped `messages` list already, so the
    override is a straight pass-through — no prompt rewriting, no format translation.
    """

    def __init__(self, client, model: str, *, form: str = "novel", max_tokens: int = 2048) -> None:
        super().__init__(
            backend_uri="unused://openai",
            backend="llama.cpp",   # avoids the eager HF tokenizer download; never invoked
            form=form,
            max_tokens=max_tokens,
            request_timeout=120,
        )
        self._client = client
        self._model = model
        self.calls = 0

    def query_chat(self, messages: list[dict], retries: int = 3) -> str:
        """Synchronous by contract — GOAT drives this from ordinary blocking code."""
        # GOAT sometimes seeds an assistant turn to constrain the continuation. Chat
        # Completions accepts that as a prefix, but the model replies with only the
        # remainder, so we re-attach the seed exactly as the upstream backends do.
        prefix = ""
        if messages and messages[-1].get("role") == "assistant":
            prefix = messages[-1].get("content", "")

        for attempt in range(1, retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.8,
                )
                self.calls += 1
                return prefix + (response.choices[0].message.content or "")
            except Exception as exc:  # noqa: BLE001 - mirror upstream's retry contract
                logger.warning("GOAT query_chat attempt %d/%d failed: %s", attempt, retries, exc)
        return ""


class GoatStorytellingEngine:
    """Async wrapper around the upstream agent.

    Exposes the four staged calls the copilot needs and reports honestly when the
    package or an API key is missing, rather than silently degrading to something
    that is not GOAT.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None
        self._model = settings.llm_model
        if settings.openai_enabled:
            from openai import OpenAI

            # Deliberately the *sync* client: GOAT calls query_chat synchronously
            # from inside a worker thread.
            self._client = OpenAI(
                api_key=settings.openai_secret,
                timeout=settings.llm_timeout_seconds,
                max_retries=1,
            )

    @property
    def available(self) -> bool:
        return GOAT_AVAILABLE and self._client is not None

    def describe(self) -> dict[str, Any]:
        return {
            "package": "goat_storytelling_agent",
            "upstream": "https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent",
            "installed": GOAT_AVAILABLE,
            "import_error": GOAT_IMPORT_ERROR,
            "available": self.available,
            "backend": f"openai:{self._model}" if self._client else None,
            "default_backend_replaced": "GOAT-70B-Storytelling via HF TGI / llama.cpp",
            "integration": (
                "Subclass of upstream StoryAgent overriding only query_chat(). GOAT's "
                "prompts, parse_book_spec and Plan parsing run unmodified."
            ),
            "stages": [
                "init_book_spec",
                "create_plot_chapters",
                "enhance_plot_chapters",
                "split_chapters_into_scenes",
            ],
        }

    def _agent(self, form: str) -> OpenAIBackedStoryAgent:
        return OpenAIBackedStoryAgent(self._client, self._model, form=form)

    async def build_plan(self, topic: str, *, form: str = "audio series", enhance: bool = True) -> dict:
        """Run GOAT's staged outline pipeline off the event loop.

        Returns the book spec dict, the parsed three-act plan, and the raw plan text.
        """
        if not self.available:
            raise RuntimeError("GOAT storytelling engine is not available.")
        return await asyncio.to_thread(self._build_plan_blocking, topic, form, enhance)

    def _build_plan_blocking(self, topic: str, form: str, enhance: bool) -> dict:
        agent = self._agent(form)
        stages: list[str] = []

        _, spec_text = agent.init_book_spec(topic)
        stages.append("init_book_spec")
        spec = agent.parse_book_spec(spec_text)

        _, plan = agent.create_plot_chapters(spec_text)
        stages.append("create_plot_chapters")

        if enhance and plan:
            try:
                _, plan = agent.enhance_plot_chapters(spec_text, plan)
                stages.append("enhance_plot_chapters")
            except Exception:  # noqa: BLE001 - enhancement is a refinement, not a requirement
                logger.exception("GOAT enhance_plot_chapters failed; keeping the base plan")

        return {
            "spec": spec,
            "spec_text": spec_text,
            "plan": plan,
            "plan_text": Plan.plan_2_str(plan) if (Plan and plan) else "",
            "stages_run": stages,
            "model_calls": agent.calls,
        }

    async def split_into_scenes(self, plan: list) -> dict:
        if not self.available:
            raise RuntimeError("GOAT storytelling engine is not available.")
        return await asyncio.to_thread(self._split_blocking, plan)

    def _split_blocking(self, plan: list) -> dict:
        agent = self._agent("audio series")
        _, scene_plan = agent.split_chapters_into_scenes(plan)
        return {"plan": scene_plan, "model_calls": agent.calls}

    async def write_draft(
        self,
        topic: str,
        *,
        form: str = "audio series",
        scenes_to_write: int = 3,
        enhance: bool = False,
    ) -> dict:
        """The full GOAT chain, ending in actual prose.

        `build_plan` stops at the outline. This goes the rest of the way:
        split each chapter into scenes, then write the opening scenes as real text.
        Scene writing is where GOAT's continuity handling earns its keep — each scene
        is generated with the tail of the previous one in context, which is why the
        prose does not read as a set of disconnected fragments.
        """
        if not self.available:
            raise RuntimeError("GOAT storytelling engine is not available.")
        return await asyncio.to_thread(
            self._write_draft_blocking, topic, form, scenes_to_write, enhance
        )

    def _write_draft_blocking(
        self, topic: str, form: str, scenes_to_write: int, enhance: bool
    ) -> dict:
        agent = self._agent(form)
        trace: list[dict] = []

        def step(name: str, note: str) -> None:
            trace.append({"goat_method": name, "result": note, "calls_so_far": agent.calls})

        _, spec_text = agent.init_book_spec(topic)
        spec = agent.parse_book_spec(spec_text)
        step("init_book_spec", f"{len([v for v in spec.values() if v])} spec fields populated")

        _, plan = agent.create_plot_chapters(spec_text)
        step("create_plot_chapters", f"{len(plan)} acts parsed by Plan.parse_text_plan")

        if enhance and plan:
            try:
                _, plan = agent.enhance_plot_chapters(spec_text, plan)
                step("enhance_plot_chapters", "acts refined")
            except Exception:  # noqa: BLE001 - refinement is optional
                logger.exception("GOAT enhance_plot_chapters failed; keeping the base plan")

        scenes_written: list[dict] = []
        if plan:
            try:
                _, plan = agent.split_chapters_into_scenes(plan)
                total = sum(
                    len(scenes)
                    for act in plan
                    for scenes in act.get("chapter_scenes", {}).values()
                )
                step("split_chapters_into_scenes", f"{total} scene descriptions")
                scenes_written = self._write_scenes(agent, plan, scenes_to_write, step)
            except Exception:  # noqa: BLE001 - keep the outline even if prose fails
                logger.exception("GOAT scene stage failed; returning the outline only")

        return {
            "spec": spec,
            "plan": plan,
            "scenes": scenes_written,
            "trace": trace,
            "model_calls": agent.calls,
        }

    @staticmethod
    def _write_scenes(agent, plan: list, limit: int, step) -> list[dict]:
        """Write the first `limit` scenes in reading order, threading continuity."""
        written: list[dict] = []
        previous: str | None = None

        for act in plan:
            for chapter_number in sorted(act.get("chapter_scenes", {})):
                for scene_index, description in enumerate(
                    act["chapter_scenes"][chapter_number], start=1
                ):
                    if len(written) >= limit:
                        return written
                    _, text = agent.write_a_scene(
                        description, scene_index, chapter_number, plan, previous_scene=previous
                    )
                    if not text:
                        continue
                    written.append(
                        {
                            "chapter": chapter_number,
                            "scene": scene_index,
                            "description": description[:400],
                            "text": text,
                            "words": len(text.split()),
                            "continued_from_previous": previous is not None,
                        }
                    )
                    previous = text
                    step(
                        "write_a_scene",
                        f"ch{chapter_number} sc{scene_index}: {len(text.split())} words",
                    )
        return written


def _clean(text: str) -> str:
    """GOAT chapter text carries markdown emphasis and heading marks; strip them."""
    return re.sub(r"[*#_`]+", "", text).strip(" -\t")


def _split_title_and_beat(text: str, fallback_index: int) -> tuple[str, str]:
    """GOAT emits a chapter as ``Title**\\n\\nBody...``.

    The title is the first line. Splitting on the first full stop instead would cut
    mid-sentence, because the body's opening sentence usually runs on past it.
    """
    cleaned = _clean(text)
    head, _, tail = cleaned.partition("\n")
    title, body = _clean(head), _clean(tail)

    # Some acts come back as one unbroken paragraph — fall back to the first sentence.
    if not body or len(title) > 130:
        sentence, separator, remainder = cleaned.partition(". ")
        if separator and len(sentence) <= 130:
            title, body = _clean(sentence), _clean(remainder)
        else:
            title, body = f"Chapter {fallback_index}", cleaned

    return (title[:120] or f"Chapter {fallback_index}"), (body or cleaned)[:900]


def flatten_chapters(plan: list) -> list[dict]:
    """GOAT's plan is act-major: ``[{act_descr, chapters: [...]}, ...]``.

    Creators think in a flat numbered episode list, so flatten it while keeping the
    act each chapter belongs to.
    """
    chapters: list[dict] = []
    number = 1
    for act_index, act in enumerate(plan or [], start=1):
        for chapter_text in act.get("chapters", []):
            title, beat = _split_title_and_beat(str(chapter_text), number)
            chapters.append({"index": number, "act": act_index, "title": title, "beat": beat})
            number += 1
    return chapters

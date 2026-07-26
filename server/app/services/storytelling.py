"""Story copilot — staged outline generation for creators.

Outlining runs on the real **GOAT-Storytelling-Agent** package
(https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent). Its staged pipeline —
book spec, three-act plot, act enhancement — executes upstream and unmodified; only
the model transport is swapped, in `app/services/goat_agent.py`. Staged generation
is what keeps a long outline internally consistent: each stage sees the committed
output of the previous one instead of re-inventing it.

Two things make this more than a wrapper around GOAT:

  1. The premise is screened against the catalog BEFORE anything is written. There
     is no point outlining twelve episodes of a story that will be blocked at upload.
  2. The outline is anchored to a measured demand segment, so the creator sees the
     supply/demand position of what they are about to write, and which narrative
     patterns are already over-supplied.

If GOAT is unavailable (package missing, or no API key) the service says so in
`generated_by` and falls back to a direct staged prompt rather than pretending GOAT
ran.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import RiskLevel
from app.domain.models import ContentItem, ContentProfile, DemandReport, SimilarityReport
from app.services.goat_agent import GoatStorytellingEngine, flatten_chapters
from app.services.llm import LlmService
from app.services.sarvam_finishing import SarvamFinishingService
from app.services.similarity import SimilarityCandidate, SimilarityService

logger = get_logger(__name__)

_WORLD_PROMPT = """Develop the world for a {language} audio story in the {genre} genre.

Premise: {premise}
Requested tone: {tone}

Return JSON:
{{
  "logline": "one sentence, under 30 words",
  "setting": "2-3 sentences",
  "characters": [
    {{"name": "...", "role": "protagonist|antagonist|ally|foil", "want": "...", "flaw": "..."}}
  ],
  "differentiators": ["2-4 specific things that make this distinct from generic {genre}"]
}}

Give 3-5 characters. Be concrete and specific — generic archetypes are the reason
stories in this genre blur together."""

_OUTLINE_PROMPT = """Plan {count} chapters for this audio story.

Logline: {logline}
Setting: {setting}
Characters: {characters}
Genre: {genre} | Language: {language}
Differentiators to preserve: {differentiators}

Avoid these over-supplied narrative patterns where you can: {avoid}

Return JSON:
{{"chapters": [
  {{"index": 1,
    "title": "short chapter title",
    "beat": "2-3 sentences: what happens and what changes",
    "hook": "the unresolved question that pulls the listener into the next chapter"}}
]}}

Rules: exactly {count} chapters, escalating stakes, and every chapter must change
the protagonist's situation. Audio listeners drop off when a chapter ends without a
hook — every hook must be a real open question."""


class StorytellingService:
    def __init__(
        self,
        settings: Settings,
        llm: LlmService,
        similarity: SimilarityService,
        goat: GoatStorytellingEngine,
        sarvam: SarvamFinishingService,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._similarity = similarity
        self._goat = goat
        self._sarvam = sarvam

    def describe_engine(self) -> dict:
        return self._goat.describe()

    async def outline(
        self,
        *,
        premise: str,
        working_title: str,
        genre: str,
        language: str,
        target_chapters: int,
        tone: str,
        creator_id: str,
        catalog: list[ContentItem],
        profiles: dict[str, ContentProfile],
        demand: DemandReport | None,
    ) -> dict:
        # --- stage 0: screen before writing ---------------------------------
        screening = await self._similarity.screen(
            SimilarityCandidate(
                title=working_title or premise[:60],
                description=premise,
                transcript=premise,
                language=language,
                genres=[genre],
                creator_id=creator_id,
            ),
            catalog,
            profiles,
            top_k=3,
            # Deterministic explanation only. The LLM narrator adds ~9s to every
            # copilot request and it paraphrases the signals rather than reading them
            # -- it has claimed "the titles are identical" on a report whose title
            # signal was 0.00. The rationale strings are generated from the numbers,
            # so they cannot contradict them.
            use_llm=False,
        )
        demand_context = self._demand_context(genre, language, demand)
        avoid = self._avoid_patterns(demand)

        if screening.risk is RiskLevel.BLOCK:
            return self._blocked_response(working_title, premise, screening, demand_context)

        # --- outline: GOAT if we have it, staged prompts otherwise ----------
        if self._goat.available:
            world, chapters, engine = await self._outline_with_goat(
                premise, genre, language, tone, target_chapters, avoid
            )
        else:
            world = await self._build_world(premise, genre, language, tone)
            chapters = await self._build_chapters(world, genre, language, target_chapters, avoid)
            engine = {
                "name": "fallback_staged_prompts",
                "reason": self._goat.describe()["import_error"] or "no LLM configured",
                "goat_used": False,
            }

        return {
            "working_title": working_title or world.get("logline", premise)[:80],
            "logline": world.get("logline", ""),
            "setting": world.get("setting", ""),
            "characters": world.get("characters", []),
            "chapters": chapters,
            "engine": engine,
            "originality": {
                "risk": screening.risk.value,
                "originality_score": screening.originality_score,
                "top_similarity": screening.top_score,
                "duplicate_kind": screening.duplicate_kind.value,
                "closest_matches": [
                    {
                        "content_id": match.content_id,
                        "title": match.title,
                        "combined_score": match.combined_score,
                    }
                    # Not sliced: a title collision is appended after the top-k and is
                    # often the single most important row for the creator to see.
                    for match in screening.matches
                ],
                "explanation": screening.explanation,
            },
            "demand_context": demand_context,
            "generated_by": "llm" if self._llm.available else "template_fallback",
            "notice": (
                "This is a drafting aid. The outline is generated text and has not been "
                "fact-checked or edited. The originality block reflects a screening comparison "
                "against the current catalog only."
            ),
        }

    # --- full draft (outline + written prose) -------------------------------

    async def draft(
        self,
        *,
        premise: str,
        working_title: str,
        genre: str,
        language: str,
        target_chapters: int,
        tone: str,
        scenes_to_write: int,
        creator_id: str,
        catalog: list[ContentItem],
        profiles: dict[str, ContentProfile],
        demand: DemandReport | None,
        localize_to: str | None = None,
        narrate: bool = False,
    ) -> dict:
        """Screen, then run GOAT all the way to actual scene text.

        The difference from `outline()` is the last two stages: GOAT splits chapters
        into scenes and writes them as prose, each scene seeing the tail of the one
        before it.

        A Sarvam AI finishing stage runs last, only on scenes that cleared the
        similarity gate: a same-language polish pass, optional translation into an
        Indic language (`localize_to`), and optional TTS narration (`narrate`).
        """
        screening = await self._similarity.screen(
            SimilarityCandidate(
                title=working_title or premise[:60],
                description=premise,
                transcript=premise,
                language=language,
                genres=[genre],
                creator_id=creator_id,
            ),
            catalog,
            profiles,
            top_k=3,
            # Deterministic explanation only. The LLM narrator adds ~9s to every
            # copilot request and it paraphrases the signals rather than reading them
            # -- it has claimed "the titles are identical" on a report whose title
            # signal was 0.00. The rationale strings are generated from the numbers,
            # so they cannot contradict them.
            use_llm=False,
        )
        demand_context = self._demand_context(genre, language, demand)

        if screening.risk is RiskLevel.BLOCK:
            return self._blocked_response(working_title, premise, screening, demand_context) | {
                "scenes": [],
                "trace": [],
                "finishing": {"available": self._sarvam.available, "reason": "blocked_before_generation"},
            }

        if not self._goat.available:
            raise RuntimeError(
                "Scene writing requires the GOAT engine. "
                f"{self._goat.describe()['import_error'] or 'No LLM configured.'}"
            )

        topic = self._compose_topic(
            premise, genre, language, tone, target_chapters, self._avoid_patterns(demand)
        )
        result = await self._goat.write_draft(
            topic,
            form=f"{language} {genre} audio series",
            scenes_to_write=scenes_to_write,
            enhance=target_chapters > 8,
        )

        spec = result["spec"]
        scene_text = "\n\n".join(scene["text"] for scene in result["scenes"] if scene.get("text"))
        finishing = await self._sarvam.finish(
            scene_text,
            source_language=language,
            target_language=localize_to,
            narrate=narrate,
        )
        return {
            "working_title": working_title or spec.get("Premise", premise)[:80],
            "logline": spec.get("Premise", "")[:400],
            "setting": " | ".join(
                part for part in (spec.get("Place", ""), spec.get("Time", "")) if part
            ),
            "characters": self._parse_goat_characters(spec.get("Characters", "")),
            "chapters": flatten_chapters(result["plan"]),
            "scenes": result["scenes"],
            "finishing": finishing,
            "engine": {
                "name": "goat_storytelling_agent",
                "goat_used": True,
                "upstream": "https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent",
                "backend": self._goat.describe()["backend"],
                "book_spec": spec,
                "model_calls": result["model_calls"],
                "scenes_written": len(result["scenes"]),
                "words_written": sum(scene["words"] for scene in result["scenes"]),
            },
            # Exactly which upstream methods ran, in order, with what each produced.
            "goat_trace": result["trace"],
            "originality": {
                "risk": screening.risk.value,
                "originality_score": screening.originality_score,
                "top_similarity": screening.top_score,
                "duplicate_kind": screening.duplicate_kind.value,
                "closest_matches": [
                    {
                        "content_id": match.content_id,
                        "title": match.title,
                        "combined_score": match.combined_score,
                    }
                    for match in screening.matches
                ],
                "explanation": screening.explanation,
            },
            "demand_context": demand_context,
            "generated_by": "goat_storytelling_agent",
            "notice": (
                "Generated draft text. Not fact-checked or edited, and the originality "
                "block compares against this catalog only."
            ),
        }

    # --- GOAT path ----------------------------------------------------------

    async def _outline_with_goat(
        self,
        premise: str,
        genre: str,
        language: str,
        tone: str,
        target_chapters: int,
        avoid: list[str],
    ) -> tuple[dict, list[dict], dict]:
        """Run the upstream GOAT pipeline and adapt its output to our response shape.

        The topic string is where our platform context enters GOAT: the target genre
        and language, and the narrative patterns the demand engine has measured as
        over-supplied. GOAT's own prompts do the rest.
        """
        topic = self._compose_topic(premise, genre, language, tone, target_chapters, avoid)
        try:
            result = await self._goat.build_plan(
                topic, form=f"{language} {genre} audio series", enhance=target_chapters > 8
            )
        except Exception as exc:  # noqa: BLE001 - never fail the request on the optional engine
            logger.exception("GOAT outline failed; falling back to staged prompts")
            world = await self._build_world(premise, genre, language, tone)
            chapters = await self._build_chapters(world, genre, language, target_chapters, avoid)
            return world, chapters, {
                "name": "fallback_staged_prompts",
                "reason": f"goat_error: {type(exc).__name__}",
                "goat_used": False,
            }

        spec = result["spec"]
        chapters = [
            {
                "index": chapter["index"],
                "act": chapter["act"],
                "title": chapter["title"],
                "beat": chapter["beat"],
                # GOAT plans by act rather than by cliffhanger; hooks are an
                # audio-serial concern we layer on rather than attribute to it.
                "hook": "",
            }
            for chapter in flatten_chapters(result["plan"])
        ]

        world = {
            "logline": spec.get("Premise", "")[:400],
            "setting": " | ".join(
                part for part in (spec.get("Place", ""), spec.get("Time", "")) if part
            ),
            "characters": self._parse_goat_characters(spec.get("Characters", "")),
            "differentiators": [],
        }
        engine = {
            "name": "goat_storytelling_agent",
            "goat_used": True,
            "upstream": "https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent",
            "stages_run": result["stages_run"],
            "model_calls": result["model_calls"],
            "backend": self._goat.describe()["backend"],
            "book_spec": spec,
            "acts": len(result["plan"]),
            "chapters_requested": target_chapters,
            "chapters_produced": len(chapters),
            "note": (
                "GOAT's prompts, parse_book_spec and three-act Plan parser ran unmodified; "
                "only the model transport was replaced."
            ),
        }
        if len(chapters) != target_chapters:
            # GOAT plans by act, not to a chapter budget. Trimming would break the
            # three-act shape, so the mismatch is reported instead of hidden.
            engine["chapter_count_note"] = (
                f"GOAT planned {len(chapters)} chapters across {len(result['plan'])} acts rather "
                f"than the {target_chapters} requested. Its outline is act-driven, so the count "
                "follows the story shape; treat the request as a hint, not a contract."
            )
        return world, chapters, engine

    @staticmethod
    def _compose_topic(
        premise: str, genre: str, language: str, tone: str, target_chapters: int, avoid: list[str]
    ) -> str:
        """GOAT takes a single free-text topic — this is where our measured platform
        context gets injected into it."""
        parts = [
            premise.strip(),
            f"Format: a {target_chapters}-episode {genre} audio series in {language}.",
        ]
        if tone:
            parts.append(f"Tone: {tone}.")
        if avoid:
            parts.append(
                "These narrative patterns are already over-supplied on the platform, so "
                f"avoid them where you can: {', '.join(avoid)}."
            )
        parts.append(
            "Every episode must end on an unresolved question, because audio listeners "
            "drop off at episode boundaries without one."
        )
        return " ".join(parts)

    @staticmethod
    def _parse_goat_characters(raw: str) -> list[dict]:
        """Parse GOAT's single-line Characters field.

        It is usually '1. Name - trait. 2. Name - trait.', but GOAT sometimes returns
        one prose sentence describing an ensemble instead. Splitting that on a
        separator that is not there would present a whole sentence as a character
        name, so an unnamed chunk is emitted as a description with no name.
        """
        if not raw.strip():
            return []
        import re

        chunks = [chunk.strip(" .") for chunk in re.split(r"\s*\d+\.\s+", raw) if chunk.strip(" .")]
        characters: list[dict] = []
        for chunk in chunks[:6]:
            name, separator, description = chunk.partition(" - ")
            if not separator:
                name, separator, description = chunk.partition(": ")
            if separator and len(name.strip()) <= 60:
                characters.append(
                    {"name": name.strip()[:80], "role": "", "description": description.strip()[:300]}
                )
            else:
                # Prose, not a named character. Say so rather than inventing a name.
                characters.append({"name": "", "role": "ensemble", "description": chunk[:300]})
        return characters

    # --- fallback stages ----------------------------------------------------

    async def _build_world(self, premise: str, genre: str, language: str, tone: str) -> dict:
        if not self._llm.available:
            return {
                "logline": premise[:160],
                "setting": f"A {genre} setting inferred from the premise.",
                "characters": [
                    {"name": "Protagonist", "role": "protagonist", "want": "unstated", "flaw": "unstated"}
                ],
                "differentiators": [],
            }
        result = await self._llm.complete_json(
            _WORLD_PROMPT.format(
                premise=premise, genre=genre, language=language, tone=tone or "unspecified"
            ),
            language=language,
            system=_CREATIVE_SYSTEM,
            temperature=0.8,
            max_tokens=800,
        )
        if not result.ok or not result.data:
            logger.warning("World-building stage returned nothing: %s", result.error)
            return {"logline": premise[:160], "setting": "", "characters": [], "differentiators": []}
        data = result.data
        characters = data.get("characters")
        return {
            "logline": str(data.get("logline", ""))[:300],
            "setting": str(data.get("setting", ""))[:1200],
            "characters": [entry for entry in characters if isinstance(entry, dict)][:6]
            if isinstance(characters, list)
            else [],
            "differentiators": [
                str(entry)[:160] for entry in data.get("differentiators", []) if isinstance(entry, str)
            ][:4],
        }

    async def _build_chapters(
        self, world: dict, genre: str, language: str, count: int, avoid: list[str]
    ) -> list[dict]:
        if not self._llm.available:
            return [
                {
                    "index": index,
                    "title": f"Chapter {index}",
                    "beat": "Outline generation requires an LLM; no API key is configured.",
                    "hook": "",
                }
                for index in range(1, count + 1)
            ]
        result = await self._llm.complete_json(
            _OUTLINE_PROMPT.format(
                count=count,
                logline=world.get("logline", ""),
                setting=world.get("setting", ""),
                characters=", ".join(
                    f"{entry.get('name', '?')} ({entry.get('role', '?')})"
                    for entry in world.get("characters", [])
                ),
                genre=genre,
                language=language,
                differentiators="; ".join(world.get("differentiators", [])) or "none specified",
                avoid=", ".join(avoid) or "none flagged",
            ),
            language=language,
            system=_CREATIVE_SYSTEM,
            temperature=0.8,
            max_tokens=2200,
        )
        entries = result.data.get("chapters") if result.ok else None
        if not isinstance(entries, list):
            return []
        chapters: list[dict] = []
        for position, entry in enumerate(entries[:count], start=1):
            if not isinstance(entry, dict):
                continue
            chapters.append(
                {
                    "index": int(entry.get("index", position)) or position,
                    "title": str(entry.get("title", f"Chapter {position}"))[:120],
                    "beat": str(entry.get("beat", ""))[:800],
                    "hook": str(entry.get("hook", ""))[:300],
                }
            )
        return chapters

    # --- demand anchoring ---------------------------------------------------

    @staticmethod
    def _demand_context(genre: str, language: str, demand: DemandReport | None) -> dict:
        if demand is None:
            return {
                "available": False,
                "note": "No demand report has been generated yet. Run POST /pipeline/run first.",
            }
        target = f"{genre.lower()}/{language.lower()}"
        match = next((row for row in demand.segments if row.segment == target), None)
        if match is None:
            return {
                "available": False,
                "segment": target,
                "note": (
                    "This genre/language cell has no catalog items and no measured activity, so "
                    "no supply/demand position can be reported for it."
                ),
                "provenance": demand.provenance.value,
            }
        rank = [row.segment for row in demand.segments].index(target) + 1
        return {
            "available": True,
            "segment": match.segment,
            "opportunity_score": match.opportunity_score,
            "opportunity_rank": rank,
            "of_segments": len(demand.segments),
            "catalog_items": match.catalog_items,
            "supply_share": match.supply_share,
            "demand_share": match.demand_share,
            "unique_listeners": match.unique_listeners,
            "completion_rate": match.completion_rate,
            "drop_off_rate": match.drop_off_rate,
            "zero_result_searches": match.unmet_search_count,
            "duplicate_density": match.duplicate_density,
            "confidence": match.confidence.value,
            "provenance": demand.provenance.value,
            "data_notice": demand.data_notice,
        }

    @staticmethod
    def _avoid_patterns(demand: DemandReport | None) -> list[str]:
        if demand is None:
            return []
        return [
            row.narrative_pattern
            for row in demand.saturated_patterns
            if row.saturation_index > 1.0 and row.narrative_pattern != "unclassified"
        ][:4]

    @staticmethod
    def _blocked_response(
        working_title: str, premise: str, screening: SimilarityReport, demand_context: dict
    ) -> dict:
        return {
            "working_title": working_title or premise[:60],
            "logline": "",
            "setting": "",
            "characters": [],
            "chapters": [],
            "originality": {
                "risk": screening.risk.value,
                "originality_score": screening.originality_score,
                "top_similarity": screening.top_score,
                "duplicate_kind": screening.duplicate_kind.value,
                "closest_matches": [
                    {
                        "content_id": match.content_id,
                        "title": match.title,
                        "combined_score": match.combined_score,
                        "rationale": match.rationale,
                    }
                    # Not sliced: a title collision is appended after the top-k and is
                    # often the single most important row for the creator to see.
                    for match in screening.matches
                ],
                "explanation": screening.explanation,
            },
            "demand_context": demand_context,
            "generated_by": "not_generated",
            "notice": (
                "Outline generation was stopped before writing: this premise matches an existing "
                "catalog story closely enough to be blocked at upload. Change the premise, or "
                "request human review of the flagged match."
            ),
        }


_CREATIVE_SYSTEM = (
    "You are a story development assistant for an audio-fiction platform. "
    "Return only valid JSON matching the requested shape. Write original material — "
    "do not reproduce plots, characters or names from existing published works."
)

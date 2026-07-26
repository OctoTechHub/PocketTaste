"""Story copilot for creators."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep, CurrentAccount, StorageDep
from app.core.errors import DependencyUnavailableError
from app.domain.schemas import NarrateRequest, StoryDraftRequest, StoryOutlineRequest

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/outline", summary="Screened, demand-anchored story outline")
async def outline(
    payload: StoryOutlineRequest, container: StorageDep, account: CurrentAccount
) -> dict:
    """Screens the premise against the catalog first. If it would be blocked at
    upload, nothing is generated and the report explains why."""
    catalog, profiles = await container.catalog_service.screening_corpus(
        title=payload.working_title or payload.premise[:60],
        description=payload.premise,
        transcript=payload.premise,
    )
    demand = await container.insight_repo.latest()

    result = await container.storytelling.outline(
        premise=payload.premise,
        working_title=payload.working_title,
        genre=payload.genre.lower(),
        language=payload.language.lower(),
        target_chapters=payload.target_chapters,
        tone=payload.tone,
        creator_id=account.user_id,
        catalog=catalog,
        profiles=profiles,
        demand=demand,
        engine_name=payload.engine,
    )
    return result | {
        "method": {
            "pre_write_screening": "the premise is checked against the catalog before anything is written",
            "outline_engine": container.storytelling.describe_engine(),
            "why_staged": (
                "One prompt for a whole outline drifts: later chapters contradict earlier ones. "
                "GOAT plans the book spec, then the three-act plot, then enhances each act, so "
                "every stage sees the committed output of the previous one."
            ),
        }
    }


@router.post("/draft", summary="Full GOAT chain: outline AND written scene text")
async def draft(
    payload: StoryDraftRequest, container: StorageDep, account: CurrentAccount
) -> dict:
    """Runs GOAT all the way to prose.

    `/copilot/outline` stops at the chapter plan. This continues into
    `split_chapters_into_scenes` and `write_a_scene`, so you get actual text — each
    scene written with the tail of the previous one in context.

    `goat_trace` in the response lists every upstream GOAT method that ran, in order,
    with what it produced. Slower and more expensive than `/outline`: one model call
    per scene.
    """
    catalog, profiles = await container.catalog_service.screening_corpus(
        title=payload.working_title or payload.premise[:60],
        description=payload.premise,
        transcript=payload.premise,
    )
    demand = await container.insight_repo.latest()

    try:
        result = await container.storytelling.draft(
            premise=payload.premise,
            working_title=payload.working_title,
            genre=payload.genre.lower(),
            language=payload.language.lower(),
            target_chapters=payload.target_chapters,
            tone=payload.tone,
            scenes_to_write=payload.scenes_to_write,
            creator_id=account.user_id,
            catalog=catalog,
            profiles=profiles,
            demand=demand,
            localize_to=payload.localize_to.lower() if payload.localize_to else None,
            narrate=payload.narrate,
            engine_name=payload.engine,
        )
    except RuntimeError as exc:
        raise DependencyUnavailableError(str(exc)) from exc
    return result


@router.post(
    "/narrate",
    summary="Sarvam finishing stage on already-generated text (polish, localize, TTS)",
)
async def narrate(payload: NarrateRequest, container: ContainerDep, account: CurrentAccount) -> dict:
    """Runs the same Sarvam finishing stage as `/copilot/draft`, but standalone.

    For turning an already-written draft into voice without paying for another GOAT
    generation: pass the drafted text back in, optionally with `localize_to` to
    translate it into an Indic language first. Always polishes, then optionally
    localizes, then always attempts narration.
    """
    return await container.sarvam_finishing.finish(
        payload.text,
        source_language=payload.language.lower(),
        target_language=payload.localize_to.lower() if payload.localize_to else None,
        narrate=True,
    )


@router.get("/engine", summary="Which outlining engine is active")
async def engine(container: ContainerDep) -> dict:
    return container.storytelling.describe_engine() | {
        "endpoints": {
            "POST /copilot/outline": "book spec + three-act plan (fast, ~2-4 model calls)",
            "POST /copilot/draft": "the above plus scene splitting and written prose "
            "(one extra model call per scene)",
        },
        "finishing_stage": container.sarvam_finishing.describe(),
    }


@router.get("/guardrails", summary="What the copilot will and will not do")
async def guardrails(container: ContainerDep) -> dict:
    return {
        "pre_write_screening": True,
        "blocks_on": ["exact_duplicate", "series_variant", f"combined score >= {container.settings.similarity_block_threshold}"],
        "flags_on": ["near_duplicate", f"combined score >= {container.settings.similarity_review_threshold}"],
        "generation_available": container.llm.available,
        "outline_engine": container.storytelling.describe_engine(),
        "language_routing": container.llm.describe(),
        "finishing_stage": container.sarvam_finishing.describe() | {
            "runs_on": "POST /copilot/draft only, after the similarity gate clears",
            "steps": ["polish (same language)", "localize (localize_to)", "narrate (narrate=true)"],
        },
        "limits": [
            "Generated text is a drafting aid, not publishable copy.",
            "The originality block reflects the current catalog only — it is not a search of "
            "published work outside this platform.",
            "A 'clear' verdict is not a legal clearance.",
        ],
    }

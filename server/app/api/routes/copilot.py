"""Story copilot for creators."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep, CurrentAccount, StorageDep
from app.domain.schemas import StoryOutlineRequest

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/outline", summary="Screened, demand-anchored story outline")
async def outline(
    payload: StoryOutlineRequest, container: StorageDep, account: CurrentAccount
) -> dict:
    """Screens the premise against the catalog first. If it would be blocked at
    upload, nothing is generated and the report explains why."""
    catalog = await container.content_repo.iter_all(with_transcript=True)
    profiles = await container.profile_repo.all_by_id()
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


@router.get("/engine", summary="Which outlining engine is active")
async def engine(container: ContainerDep) -> dict:
    return container.storytelling.describe_engine()


@router.get("/guardrails", summary="What the copilot will and will not do")
async def guardrails(container: ContainerDep) -> dict:
    return {
        "pre_write_screening": True,
        "blocks_on": ["exact_duplicate", "series_variant", f"combined score >= {container.settings.similarity_block_threshold}"],
        "flags_on": ["near_duplicate", f"combined score >= {container.settings.similarity_review_threshold}"],
        "generation_available": container.llm.available,
        "outline_engine": container.storytelling.describe_engine(),
        "language_routing": container.llm.describe(),
        "limits": [
            "Generated text is a drafting aid, not publishable copy.",
            "The originality block reflects the current catalog only — it is not a search of "
            "published work outside this platform.",
            "A 'clear' verdict is not a legal clearance.",
        ],
    }

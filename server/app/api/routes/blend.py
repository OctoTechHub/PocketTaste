"""Blend: a shared feed for two listeners."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount, StorageDep
from app.core.logging import get_logger
from app.domain.schemas import BlendCreate

logger = get_logger(__name__)
router = APIRouter(prefix="/blend", tags=["blend"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Start a blend with someone")
async def create_blend(
    payload: BlendCreate, container: StorageDep, account: CurrentAccount
) -> dict:
    """Adding the same person twice returns the existing blend rather than failing."""
    blend, created = await container.blend_service.create(
        owner_id=account.user_id, partner_email=payload.email
    )
    described = await container.blend_service.describe(blend.blend_id, viewer_id=account.user_id)
    return described | {"created": created}


@router.get("", summary="Blends you are part of")
async def my_blends(container: StorageDep, account: CurrentAccount) -> dict:
    blends = await container.blend_service.list_for(account.user_id)
    return {"blends": blends, "count": len(blends)}


@router.get("/{blend_id}", summary="One blend and how alike the two of you are")
async def get_blend(blend_id: str, container: StorageDep, account: CurrentAccount) -> dict:
    return await container.blend_service.describe(blend_id, viewer_id=account.user_id)


@router.get("/{blend_id}/feed", summary="The blended feed, with per-item attribution")
async def blend_feed(
    blend_id: str,
    container: StorageDep,
    account: CurrentAccount,
    limit: int = Query(default=18, ge=1, le=50),
    language: str | None = Query(default=None),
) -> dict:
    """Each item reports `owner` and `lean`, so the interface can show whose taste
    produced it instead of claiming the feed is evenly split."""
    context = await container.cache.get()
    return await container.blend_service.feed(
        blend_id,
        viewer_id=account.user_id,
        context=context,
        limit=limit,
        language=language,
    )


@router.get("/{blend_id}/feed/stream", summary="The blended feed, streamed stage by stage")
async def blend_feed_stream(
    blend_id: str,
    container: StorageDep,
    account: CurrentAccount,
    limit: int = Query(default=18, ge=1, le=50),
    language: str | None = Query(default=None),
) -> StreamingResponse:
    """Server-sent events: one `stage` per step of the algorithm, then `result`.

    The stages are emitted by the algorithm as each one finishes, carrying the real
    counts — candidates surviving the pool filter, items scored per member, slots the
    representation pass had to reassign. Scoring runs in a worker thread so the event
    loop keeps flushing events while it works; without that the whole stream would
    arrive at once at the end and there would be nothing to watch.
    """
    context = await container.cache.get()
    # Every database read happens here, on the request's own loop. The worker thread
    # below gets plain objects only -- the async Mongo client binds to the loop it was
    # created on and raises if a second loop touches it.
    blend, members = await container.blend_service.prepare(blend_id, viewer_id=account.user_id)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def on_stage(step: str, message: str, detail: dict) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait, {"type": "stage", "step": step, "message": message, **detail}
        )

    async def run() -> None:
        try:
            result = await asyncio.to_thread(
                container.blend_algorithm.blend,
                members,
                context,
                limit=limit,
                language=language,
                on_stage=on_stage,
            )
            payload = container.blend_service.compose(blend, members, result, account.user_id)
            await container.blend_service.mark_viewed(blend)
            await queue.put({"type": "result", **payload})
        except Exception as exc:  # noqa: BLE001 - the stream must report, not hang
            logger.exception("Blend stream failed for %s", blend_id)
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    async def events():
        task = asyncio.create_task(run())
        try:
            while True:
                payload = await queue.get()
                if payload is None:
                    break
                yield f"data: {json.dumps(payload, default=str)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{blend_id}", summary="End a blend")
async def delete_blend(blend_id: str, container: StorageDep, account: CurrentAccount) -> dict:
    await container.blend_service.remove(blend_id, viewer_id=account.user_id)
    return {"blend_id": blend_id, "deleted": True}


@router.get("/{blend_id}/method", summary="How the blend is computed")
async def blend_method(blend_id: str, container: StorageDep, account: CurrentAccount) -> dict:
    from app.services.blend import (
        DEFAULT_ALPHA,
        _REPRESENTATION_FLOOR,
        _SHARED_BAND,
    )

    await container.blend_service.get(blend_id, viewer_id=account.user_id)
    return {
        "scorer": "app.services.ranking.RankingService — the same ranker /recommendations uses",
        "steps": [
            "Score every candidate once per member with the production ranker.",
            "Min-max normalise each member's scores over the shared candidate pool.",
            f"Combine: {DEFAULT_ALPHA} x mean + {round(1 - DEFAULT_ALPHA, 2)} x least-misery(min).",
            f"Label an item 'shared' when the two normalised scores differ by <= {_SHARED_BAND}.",
            f"Select greedily, forcing a slot to whichever member falls below {_REPRESENTATION_FLOOR} representation.",
        ],
        "candidate_rule": (
            "Items either member has not finished stay in. Only titles both have "
            "already been through are dropped, plus duplicates the similarity gate flagged."
        ),
        "weights": container.settings.ranking_weights.as_dict(),
    }

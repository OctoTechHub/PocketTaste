"""Event ingestion — the fuel for everything else.

Every event is attributed to the bearer token that submitted it, so the log records
what really happened and to whom. Events written here carry `is_synthetic=False`,
which is what separates them from the calibrated simulation in every downstream
report.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentAccount, StorageDep
from app.domain.enums import EVENT_WEIGHTS, EventType
from app.domain.schemas import ActivityAcceptedResponse, ActivityBatchCreate, ActivityCreate

router = APIRouter(prefix="/activity", tags=["activity"])


@router.post(
    "",
    response_model=ActivityAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Log one listening event (authenticated)",
)
async def log_event(
    payload: ActivityCreate, container: StorageDep, account: CurrentAccount
) -> ActivityAcceptedResponse:
    accepted, errors = await container.activity_service.record(
        [payload], user_id=account.user_id
    )
    container.cache.invalidate()
    return ActivityAcceptedResponse(
        accepted=len(accepted), rejected=len(errors), event_ids=accepted, errors=errors
    )


@router.post(
    "/batch",
    response_model=ActivityAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Log up to 5000 events in one call (authenticated)",
)
async def log_batch(
    payload: ActivityBatchCreate, container: StorageDep, account: CurrentAccount
) -> ActivityAcceptedResponse:
    accepted, errors = await container.activity_service.record(
        payload.events, user_id=account.user_id
    )
    container.cache.invalidate()
    return ActivityAcceptedResponse(
        accepted=len(accepted), rejected=len(errors), event_ids=accepted[:50], errors=errors[:50]
    )


@router.get("/schema", summary="Accepted event types and their interaction weights")
async def event_schema() -> dict:
    return {
        "event_types": [event.value for event in EventType],
        "interaction_weights": {event.value: weight for event, weight in EVENT_WEIGHTS.items()},
        "authentication": "Bearer token required; the event is attributed to the token holder.",
        "notes": {
            "user_id": "Not accepted in the body — it is taken from the token.",
            "search": "content_id may be null; set result_count=0 to record an unmet search.",
            "drop_off": "position_seconds is required — it drives retention curves and abandon points.",
            "chapter_index": "optional; inferred from position_seconds when the item has chapter markers.",
            "negative_weights": (
                "skip and drop_off carry negative weight. A drop-off early in the runtime is "
                "weighted more negatively than one near the end."
            ),
        },
    }


@router.get("/stats", summary="Log volume, and how much of it is real")
async def stats(container: StorageDep) -> dict:
    total = await container.activity_repo.count()
    synthetic = await container.activity_repo.count({"is_synthetic": True})
    real = total - synthetic
    return {
        "total_events": total,
        "real_events": real,
        "simulated_events": synthetic,
        "unique_users": await container.activity_repo.unique_user_count(),
        "registered_accounts": await container.accounts_repo.count(),
        "by_event_type": await container.activity_repo.counts_by_event_type(),
        "synthetic_share": await container.activity_repo.synthetic_ratio(),
        "note": (
            "real_events are those submitted by authenticated accounts. simulated_events come "
            "from the calibrated simulator. Every downstream report reports which it used."
        ),
    }

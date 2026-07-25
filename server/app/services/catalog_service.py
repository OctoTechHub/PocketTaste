"""Application services for catalog and activity ingestion.

Routes stay thin: they validate the payload and delegate here. All the rules about
what happens on upload (screen first, refuse a blocked duplicate, index the new
item) live in one place.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.data.repositories import (
    ActivityRepository,
    ContentProfileRepository,
    ContentRepository,
    SimilarityAuditRepository,
)
from app.domain.enums import RiskLevel
from app.domain.models import ActivityEvent, Chapter, ContentItem, SimilarityReport
from app.domain.schemas import ActivityCreate, ContentCreate
from app.services.discovery import DiscoveryService
from app.services.similarity import SimilarityCandidate, SimilarityService

logger = get_logger(__name__)


class CatalogService:
    def __init__(
        self,
        settings: Settings,
        content_repo: ContentRepository,
        profile_repo: ContentProfileRepository,
        audit_repo: SimilarityAuditRepository,
        similarity: SimilarityService,
        discovery: DiscoveryService,
    ) -> None:
        self._settings = settings
        self._content_repo = content_repo
        self._profile_repo = profile_repo
        self._audit_repo = audit_repo
        self._similarity = similarity
        self._discovery = discovery

    async def ingest(
        self, payload: ContentCreate, *, screen: bool = True, use_llm: bool = True
    ) -> tuple[ContentItem, SimilarityReport | None]:
        """Screen, then store. A blocked duplicate never reaches the catalog."""
        content_id = payload.content_id or f"cnt_{uuid4().hex[:12]}"
        if await self._content_repo.exists(content_id):
            raise ConflictError(
                f"content_id '{content_id}' already exists.", details={"content_id": content_id}
            )

        report: SimilarityReport | None = None
        if screen:
            report = await self.screen(payload, use_llm=use_llm)
            await self._audit_repo.record(report, creator_id=payload.creator_id, context="upload")
            if report.risk is RiskLevel.BLOCK:
                raise ConflictError(
                    "Upload blocked: this story duplicates an existing catalog item.",
                    details={
                        "risk": report.risk.value,
                        "duplicate_kind": report.duplicate_kind.value,
                        "top_score": report.top_score,
                        "originality_score": report.originality_score,
                        # The per-signal breakdown ships with the refusal. A creator whose
                        # upload is rejected needs to see *which* signal fired to argue
                        # with it -- otherwise the block is unappealable.
                        "matches": [
                            {
                                "content_id": match.content_id,
                                "title": match.title,
                                "creator_id": match.creator_id,
                                "combined_score": match.combined_score,
                                "signals": match.signals.model_dump(mode="json"),
                                "rationale": match.rationale,
                            }
                            for match in report.matches[:3]
                        ],
                        "applied_signals": report.applied_signals,
                        "weights": report.weights,
                        "explanation": report.explanation,
                        "disclaimer": report.disclaimer,
                    },
                )

        item = ContentItem(
            content_id=content_id,
            title=payload.title,
            description=payload.description,
            transcript=payload.transcript,
            creator_id=payload.creator_id,
            language=payload.language,
            genres=payload.genres,
            tags=payload.tags,
            duration_seconds=payload.duration_seconds,
            chapters=[Chapter.model_validate(chapter.model_dump()) for chapter in payload.chapters],
            source=payload.source,
            is_synthetic=False,
            published_at=payload.published_at or utcnow(),
            created_at=utcnow(),
        )
        await self._content_repo.upsert(item)
        logger.info("Ingested content %s ('%s') from %s", item.content_id, item.title, item.creator_id)
        return item, report

    async def screen(self, payload: ContentCreate, *, use_llm: bool = True) -> SimilarityReport:
        catalog, profiles = await self._shortlist(
            title=payload.title, description=payload.description, transcript=payload.transcript
        )
        return await self._similarity.screen(
            SimilarityCandidate(
                title=payload.title,
                description=payload.description,
                transcript=payload.transcript,
                language=payload.language,
                genres=payload.genres,
                chapters=[Chapter.model_validate(chapter.model_dump()) for chapter in payload.chapters],
                creator_id=payload.creator_id,
            ),
            catalog,
            profiles,
            exclude_content_id=payload.content_id,
            use_llm=use_llm,
        )

    async def _shortlist(
        self, *, title: str, description: str, transcript: str, top_k: int = 25
    ) -> tuple[list[ContentItem], dict]:
        """Retrieve plausible matches instead of scanning the whole catalog.

        Falls back to the full catalog when the index is empty (fresh install) —
        correctness first, speed second.
        """
        query = f"{title}\n{description}\n{transcript[:3000]}"
        shortlist_ids = await self._discovery.shortlist_for_similarity(query, top_k=top_k)
        if shortlist_ids:
            catalog = await self._content_repo.get_many(shortlist_ids, with_transcript=True)
        else:
            catalog = await self._content_repo.iter_all(with_transcript=True)
        profiles = await self._profile_repo.get_many([item.content_id for item in catalog])
        return catalog, profiles

    async def get_detail(self, content_id: str) -> ContentItem:
        item = await self._content_repo.get(content_id)
        if item is None:
            raise NotFoundError(f"No catalog item with id '{content_id}'.")
        return item


class ActivityService:
    def __init__(self, content_repo: ContentRepository, activity_repo: ActivityRepository) -> None:
        self._content_repo = content_repo
        self._activity_repo = activity_repo

    async def record(
        self, payloads: list[ActivityCreate], *, user_id: str, is_synthetic: bool = False
    ) -> tuple[list[str], list[str]]:
        """Append events for one authenticated listener.

        `user_id` comes from the caller's token, never from the request body, so a
        client cannot write events into someone else's listening history. Unknown
        content ids are rejected individually rather than failing the whole batch.
        """
        referenced = {payload.content_id for payload in payloads if payload.content_id}
        known = (
            {item.content_id for item in await self._content_repo.get_many(sorted(referenced))}
            if referenced
            else set()
        )

        events: list[ActivityEvent] = []
        errors: list[str] = []
        for index, payload in enumerate(payloads):
            if payload.content_id and payload.content_id not in known:
                errors.append(f"event[{index}]: unknown content_id '{payload.content_id}'")
                continue
            if payload.content_id is None and payload.event_type.value != "search":
                errors.append(f"event[{index}]: content_id is required for '{payload.event_type.value}'")
                continue
            events.append(
                ActivityEvent(
                    event_id=f"evt_{uuid4().hex[:16]}",
                    user_id=user_id,
                    content_id=payload.content_id,
                    session_id=payload.session_id or f"sess_{uuid4().hex[:12]}",
                    event_type=payload.event_type,
                    position_seconds=payload.position_seconds,
                    chapter_index=payload.chapter_index,
                    session_seconds=payload.session_seconds,
                    query=payload.query,
                    result_count=payload.result_count,
                    device=payload.device,
                    is_synthetic=is_synthetic,
                    occurred_at=payload.occurred_at or utcnow(),
                )
            )

        if events:
            await self._activity_repo.insert_many(events)
        return [event.event_id for event in events], errors

"""Persistence for creator insight reports, similarity audits and pipeline runs."""

from __future__ import annotations

from typing import Any

from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository, to_document
from app.domain.models import DemandReport, PipelineRun, SimilarityReport


class InsightRepository(BaseRepository[DemandReport]):
    collection_name = Collections.INSIGHTS
    model_type = DemandReport
    key_field = "generated_at"

    async def save(self, report: DemandReport) -> None:
        await self.collection.insert_one(to_document(report))

    async def latest(self) -> DemandReport | None:
        document = await self.collection.find_one({}, sort=[("generated_at", -1)])
        if document is None:
            return None
        document.pop("_id", None)
        return DemandReport.model_validate(document)


class SimilarityAuditRepository:
    """Append-only audit trail: every upload screening is recorded for review."""

    def __init__(self, gateway) -> None:
        self._gateway = gateway

    @property
    def collection(self):
        return self._gateway.database[Collections.SIMILARITY]

    async def record(self, report: SimilarityReport, *, creator_id: str, context: str) -> None:
        payload: dict[str, Any] = to_document(report)
        payload["creator_id"] = creator_id
        payload["context"] = context
        await self.collection.insert_one(payload)

    async def recent(self, limit: int = 25) -> list[dict]:
        cursor = self.collection.find({}, {"_id": 0}).sort("computed_at", -1).limit(limit)
        return [doc async for doc in cursor]

    async def count(self) -> int:
        return await self.collection.count_documents({})


class PipelineRunRepository(BaseRepository[PipelineRun]):
    collection_name = Collections.RUNS
    model_type = PipelineRun
    key_field = "run_id"

    async def recent(self, limit: int = 20) -> list[PipelineRun]:
        return await self.find({}, limit=limit, sort=[("started_at", -1)])

    async def latest(self) -> PipelineRun | None:
        runs = await self.recent(limit=1)
        return runs[0] if runs else None

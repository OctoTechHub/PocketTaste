"""Conversational discovery over the Haystack hybrid retrieval pipeline."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter

from app.api.deps import ContainerDep, StorageDep
from app.core.clock import utcnow
from app.domain.enums import EventType
from app.domain.models import ActivityEvent
from app.domain.schemas import DiscoveryHit, DiscoveryRequest, DiscoveryResponse

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/search", response_model=DiscoveryResponse, summary="Natural-language catalog search")
async def search(payload: DiscoveryRequest, container: StorageDep) -> DiscoveryResponse:
    """BM25 and dense retrieval run in parallel and are fused with reciprocal rank
    fusion. The search — including a zero-result search — is logged, because an
    unanswered query is the cleanest unmet-demand signal the system gets."""
    documents = await container.discovery.retrieve(
        payload.query, top_k=payload.top_k, language=payload.language
    )
    hits = [
        DiscoveryHit(
            content_id=document.meta["content_id"],
            title=document.meta["title"],
            language=document.meta["language"],
            genres=document.meta.get("genre_list", []),
            score=round(float(document.score or 0.0), 6),
            retrievers=["bm25", "embedding"],
            snippet=document.content[:280] if document.content else "",
        )
        for document in documents
    ]

    logged = False
    if payload.user_id:
        await container.activity_repo.insert_many(
            [
                ActivityEvent(
                    event_id=f"evt_{uuid4().hex[:16]}",
                    user_id=payload.user_id,
                    content_id=None,
                    session_id=f"sess_search_{uuid4().hex[:10]}",
                    event_type=EventType.SEARCH,
                    query=payload.query,
                    result_count=len(hits),
                    occurred_at=utcnow(),
                )
            ]
        )
        logged = True

    answer = await container.discovery.answer(payload.query, documents) if payload.answer else None

    return DiscoveryResponse(
        query=payload.query,
        hits=hits,
        answer=answer,
        pipeline="haystack.AsyncPipeline",
        retrievers_used=["InMemoryBM25Retriever", "InMemoryEmbeddingRetriever"],
        fusion="reciprocal_rank_fusion",
        logged_as_search=logged,
    )


@router.get("/pipeline", summary="Retrieval pipeline topology")
async def pipeline(container: ContainerDep) -> dict:
    return container.discovery.describe() | {
        "why_haystack": (
            "The same retrieval graph serves two consumers: conversational discovery (with a "
            "generator on the tail) and the plagiarism gate (documents only). Haystack lets both "
            "share one index and one fusion policy, and lets the retrievers be swapped for a "
            "managed vector store without touching either caller."
        ),
        "why_reciprocal_rank_fusion": (
            "BM25 scores and cosine scores are not on a comparable scale. Averaging them lets "
            "whichever retriever has the larger numeric range silently dominate; RRF combines "
            "ranks instead, so neither retriever can swamp the other."
        ),
    }


@router.post("/reindex", summary="Rebuild the retrieval index from Mongo")
async def reindex(container: StorageDep) -> dict:
    catalog = await container.content_repo.iter_all(with_transcript=True)
    profiles = await container.profile_repo.all_by_id()
    indexed = container.discovery.index(catalog, profiles)
    return {
        "indexed_documents": indexed,
        "with_embeddings": sum(1 for profile in profiles.values() if profile.embedding),
        "note": "Items without a profile are indexed for BM25 only until the pipeline embeds them.",
    }

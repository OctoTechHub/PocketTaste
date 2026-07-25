"""Haystack retrieval pipelines.

Why Haystack rather than hand-rolled retrieval: we need the *same* retrieval graph
in two places with different tails.

    query -> [BM25 retriever, embedding retriever] -> reciprocal rank fusion -> ...
                                                                              |
        ... -> prompt builder -> generator      (conversational discovery)
        ... -> raw documents                     (plagiarism candidate shortlist)

Haystack lets both share one indexed store and one fusion policy, and lets the
retrievers be swapped for a managed vector store later without touching callers.

Fusion is reciprocal rank fusion rather than score averaging, because BM25 scores
and cosine scores are not on a comparable scale — averaging them silently lets
whichever retriever has the larger numeric range dominate.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import ContentItem, ContentProfile
from app.services.embeddings import EmbeddingService
from app.services.llm import LlmService

logger = get_logger(__name__)

# Haystack is required for the API's discovery and shortlisting, and deliberately
# optional everywhere else.
#
# The Databricks **serverless** runtime pins numpy 1.26 as a core package. Installing
# haystack-ai there drags in numpy 2.x, which changes a core dependency and kills the
# Python kernel outright:
#
#     ERROR_CORE_PACKAGE_VERSION_CHANGE ... (numpy: 1.26.4 -> 2.2.1)
#
# Downgrading haystack to <2.8 would fix that but cost the API real retrieval
# features. The batch tasks do not need retrieval at all — an in-memory index built
# by a job that then exits is pointless, and the all-pairs `similarity_sweep` does
# not use shortlisting — so the import is guarded and the batch tier simply omits it.
try:
    from haystack import Document, component
    from haystack.components.builders import PromptBuilder
    from haystack.components.joiners import DocumentJoiner
    from haystack.components.retrievers.in_memory import (
        InMemoryBM25Retriever,
        InMemoryEmbeddingRetriever,
    )
    from haystack.core.pipeline import AsyncPipeline
    from haystack.document_stores.in_memory import InMemoryDocumentStore
    from haystack.document_stores.types import DuplicatePolicy

    HAYSTACK_AVAILABLE = True
    HAYSTACK_IMPORT_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 - optional outside the API process
    Document = object  # type: ignore[assignment,misc]
    HAYSTACK_AVAILABLE = False
    HAYSTACK_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    logger.warning("Haystack unavailable (%s) — retrieval disabled in this process", HAYSTACK_IMPORT_ERROR)

    class _NoopComponent:
        """Stand-in for Haystack's `@component`, so the module still imports.

        Mirrors the two shapes the decorator is used in: bare on a class, and
        `@component.output_types(...)` on its methods.
        """

        def __call__(self, cls):
            return cls

        @staticmethod
        def output_types(**_kwargs):
            def decorator(function):
                return function

            return decorator

    component = _NoopComponent()  # type: ignore[assignment]

_ANSWER_TEMPLATE = """A listener asked: "{{ query }}"

These catalog stories were retrieved for that query:
{% for document in documents %}
- {{ document.meta.title }} [{{ document.meta.language }}, {{ document.meta.genres }}]
  themes: {{ document.meta.themes }} | tone: {{ document.meta.tone }} | pacing: {{ document.meta.pacing }}
  {{ document.content[:320] }}
{% endfor %}

Recommend at most 3 of these, by exact title, and say in one line each why it fits
the request. Only use the stories listed above. If none genuinely fit, say so."""


@component
class PocketTasteTextEmbedder:  # type: ignore[misc]
    """Bridges Haystack to our EmbeddingService so the query and the indexed
    documents are always embedded by the same backend (OpenAI or hash fallback)."""

    def __init__(self, embeddings: EmbeddingService) -> None:
        self._embeddings = embeddings

    @component.output_types(embedding=list[float])
    async def run_async(self, text: str) -> dict[str, list[float]]:
        return {"embedding": await self._embeddings.embed(text)}

    @component.output_types(embedding=list[float])
    def run(self, text: str) -> dict[str, list[float]]:
        # Synchronous path is unused by the API (which always awaits run_async),
        # but Haystack requires `run` to exist for pipeline validation.
        raise RuntimeError("PocketTasteTextEmbedder is async-only; use the async pipeline entry points.")


class DiscoveryService:
    """Owns the Haystack document store and both pipelines."""

    def __init__(self, settings: Settings, embeddings: EmbeddingService, llm: LlmService) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._llm = llm
        self._indexed = 0
        self._available = HAYSTACK_AVAILABLE
        if not self._available:
            # Batch processes construct the container but never retrieve. Degrade to
            # a no-op rather than refusing to build.
            self._store = None
            self._retrieval_pipeline = None
            self._prompt_builder = None
            return
        self._store = InMemoryDocumentStore(embedding_similarity_function="cosine")
        self._retrieval_pipeline = self._build_retrieval_pipeline()
        self._prompt_builder = PromptBuilder(
            template=_ANSWER_TEMPLATE, required_variables=["query", "documents"]
        )

    # --- indexing -----------------------------------------------------------

    @property
    def indexed_count(self) -> int:
        return self._indexed

    def index(self, catalog: list[ContentItem], profiles: dict[str, ContentProfile]) -> int:
        """(Re)build the in-memory index from the catalog and its profiles."""
        if not self._available:
            logger.debug("Haystack unavailable; skipping index build")
            return 0
        documents: list[Document] = []
        for item in catalog:
            profile = profiles.get(item.content_id)
            documents.append(
                Document(
                    id=item.content_id,
                    content=self._document_text(item, profile),
                    embedding=profile.embedding if profile and profile.embedding else None,
                    meta={
                        "content_id": item.content_id,
                        "title": item.title,
                        "language": item.language,
                        "genres": ", ".join(item.genres) or "general",
                        "genre_list": item.genres,
                        "creator_id": item.creator_id,
                        "themes": ", ".join(profile.themes) if profile else "",
                        "tone": profile.tone if profile else "",
                        "pacing": profile.pacing.value if profile else "",
                        "narrative_pattern": profile.narrative_pattern if profile else "",
                        "duration_seconds": item.duration_seconds,
                        "is_synthetic": item.is_synthetic,
                    },
                )
            )
        self._store.write_documents(documents, policy=DuplicatePolicy.OVERWRITE)
        self._indexed = len(documents)
        logger.info("Haystack index rebuilt with %d documents", self._indexed)
        return self._indexed

    @staticmethod
    def _document_text(item: ContentItem, profile: ContentProfile | None) -> str:
        parts = [item.title, item.description]
        if profile:
            parts.append(" ".join(profile.themes))
            parts.append(" ".join(profile.tropes))
            parts.append(profile.fingerprint.as_text())
        parts.append(" ".join(item.tags))
        parts.append(item.transcript[:3000])
        return "\n".join(part for part in parts if part)

    # --- pipelines ----------------------------------------------------------

    def _build_retrieval_pipeline(self) -> AsyncPipeline:
        # AsyncPipeline (not Pipeline) — it awaits components that expose `run_async`
        # and schedules the purely synchronous ones without blocking the event loop.
        pipeline = AsyncPipeline()
        pipeline.add_component("text_embedder", PocketTasteTextEmbedder(self._embeddings))
        pipeline.add_component("bm25_retriever", InMemoryBM25Retriever(document_store=self._store, top_k=20))
        pipeline.add_component(
            "embedding_retriever", InMemoryEmbeddingRetriever(document_store=self._store, top_k=20)
        )
        pipeline.add_component(
            "joiner", DocumentJoiner(join_mode="reciprocal_rank_fusion", top_k=20, sort_by_score=True)
        )
        pipeline.connect("text_embedder.embedding", "embedding_retriever.query_embedding")
        pipeline.connect("bm25_retriever.documents", "joiner.documents")
        pipeline.connect("embedding_retriever.documents", "joiner.documents")
        return pipeline

    def describe(self) -> dict[str, Any]:
        if not self._available:
            return {
                "available": False,
                "reason": HAYSTACK_IMPORT_ERROR,
                "impact": (
                    "Conversational discovery and similarity shortlisting are disabled in "
                    "this process. Screening falls back to a full-catalog scan, which is "
                    "slower but gives the same verdicts."
                ),
            }
        return {
            "available": True,
            "pipeline": "haystack.AsyncPipeline",
            "components": list(self._retrieval_pipeline.graph.nodes),
            "retrievers": ["InMemoryBM25Retriever", "InMemoryEmbeddingRetriever"],
            "fusion": "reciprocal_rank_fusion",
            "generator": self._settings.llm_model if self._llm.available else None,
            "indexed_documents": self._indexed,
            "embedding_backend": self._embeddings.backend,
        }

    # --- retrieval ----------------------------------------------------------

    async def retrieve(
        self, query: str, *, top_k: int = 10, language: str | None = None
    ) -> list[Document]:
        """Hybrid BM25 + dense retrieval with reciprocal rank fusion."""
        if not self._available or self._indexed == 0:
            return []
        filters = {"field": "meta.language", "operator": "==", "value": language} if language else None
        result = await self._retrieval_pipeline.run_async(
            {
                "text_embedder": {"text": query},
                "bm25_retriever": {"query": query, "top_k": max(top_k * 3, 20), "filters": filters},
                "embedding_retriever": {"top_k": max(top_k * 3, 20), "filters": filters},
                "joiner": {"top_k": top_k},
            }
        )
        return result.get("joiner", {}).get("documents", [])

    async def answer(self, query: str, documents: list[Document]) -> str | None:
        """Grounded generation over the retrieved set. Returns None when no LLM."""
        if not self._available or not self._llm.available or not documents:
            return None
        prompt = self._prompt_builder.run(query=query, documents=documents)["prompt"]
        result = await self._llm.complete_text(prompt, max_tokens=400)
        return result.text if result.ok and result.text else None

    async def shortlist_for_similarity(
        self, item_text: str, *, top_k: int, exclude_content_id: str | None = None
    ) -> list[str]:
        """Candidate shortlist for the plagiarism gate.

        Comparing a new upload against the entire catalog is O(n) expensive pairwise
        work. Retrieval narrows it to the only items that could plausibly match, and
        the expensive per-signal comparison runs on that shortlist.
        """
        documents = await self.retrieve(item_text[:4000], top_k=top_k)
        return [
            document.meta["content_id"]
            for document in documents
            if document.meta.get("content_id") and document.meta["content_id"] != exclude_content_id
        ]

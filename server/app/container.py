"""Composition root.

Every dependency is constructed exactly once, here. Routes never build a service,
services never build a repository, repositories never build a client. This is the
only module that knows how the graph fits together.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents import (
    ContentIntelligenceAgent,
    IngestionAgent,
    InsightAgent,
    PipelineOrchestrator,
)
from app.core.config import Settings
from app.core.logging import get_logger
from app.data.mongo import MongoGateway
from app.data.repositories import (
    ActivityRepository,
    BlendRepository,
    ContentAudioRepository,
    ContentFeaturesRepository,
    ContentProfileRepository,
    ContentRepository,
    InsightRepository,
    PipelineRunRepository,
    SimilarityAuditRepository,
    UserAccountRepository,
    UserProfileRepository,
)
from app.services.auth_service import AuthService
from app.services.blend import BlendService
from app.services.blend_service import BlendApplicationService
from app.services.fast_story_engine import FastStoryEngine
from app.services.catalog_service import ActivityService, CatalogService
from app.services.content_intelligence import ContentIntelligenceService
from app.services.context_cache import RankingContextCache
from app.services.demand import DemandService
from app.services.discovery import DiscoveryService
from app.services.embeddings import EmbeddingService
from app.services.evaluation import EvaluationService
from app.services.goat_agent import GoatStorytellingEngine
from app.services.explanation import ExplanationService
from app.services.llm import LlmService
from app.services.ranking import RankingService
from app.services.sarvam_finishing import SarvamFinishingService
from app.services.scheduler import PipelineScheduler
from app.services.similarity import SimilarityService
from app.services.storytelling import StorytellingService

logger = get_logger(__name__)


@dataclass(slots=True)
class Container:
    settings: Settings
    gateway: MongoGateway

    # repositories
    content_repo: ContentRepository
    activity_repo: ActivityRepository
    profile_repo: ContentProfileRepository
    features_repo: ContentFeaturesRepository
    users_repo: UserProfileRepository
    insight_repo: InsightRepository
    similarity_audit_repo: SimilarityAuditRepository
    runs_repo: PipelineRunRepository
    accounts_repo: UserAccountRepository
    blends_repo: BlendRepository
    audio_repo: ContentAudioRepository

    # services
    embeddings: EmbeddingService
    llm: LlmService
    intelligence: ContentIntelligenceService
    similarity: SimilarityService
    discovery: DiscoveryService
    ranking: RankingService
    demand: DemandService
    explanation: ExplanationService
    evaluation: EvaluationService
    storytelling: StorytellingService
    goat: GoatStorytellingEngine
    sarvam_finishing: SarvamFinishingService
    fast_story: FastStoryEngine
    blend_algorithm: BlendService
    blend_service: BlendApplicationService
    auth: AuthService
    catalog_service: CatalogService
    activity_service: ActivityService
    cache: RankingContextCache

    # orchestration
    orchestrator: PipelineOrchestrator
    scheduler: PipelineScheduler

    async def warm_up(self) -> None:
        """Build the Haystack index from whatever is already persisted."""
        if not self.gateway.connected:
            return
        catalog = await self.content_repo.iter_all(with_transcript=True)
        if not catalog:
            logger.info("Catalog is empty — nothing to index. Run scripts/seed.py to load demo data.")
            return
        profiles = await self.profile_repo.all_by_id()
        self.discovery.index(catalog, profiles)

    async def aclose(self) -> None:
        await self.sarvam_finishing.aclose()


def build_container(settings: Settings, gateway: MongoGateway) -> Container:
    content_repo = ContentRepository(gateway)
    activity_repo = ActivityRepository(gateway)
    profile_repo = ContentProfileRepository(gateway)
    features_repo = ContentFeaturesRepository(gateway)
    users_repo = UserProfileRepository(gateway)
    insight_repo = InsightRepository(gateway)
    similarity_audit_repo = SimilarityAuditRepository(gateway)
    runs_repo = PipelineRunRepository(gateway)
    accounts_repo = UserAccountRepository(gateway)
    blends_repo = BlendRepository(gateway)
    audio_repo = ContentAudioRepository(gateway)

    embeddings = EmbeddingService(settings)
    llm = LlmService(settings)
    intelligence = ContentIntelligenceService(settings, embeddings, llm)
    similarity = SimilarityService(settings, intelligence, llm)
    discovery = DiscoveryService(settings, embeddings, llm)
    ranking = RankingService(settings)
    demand = DemandService(settings, llm)
    explanation = ExplanationService(settings, llm)
    evaluation = EvaluationService(settings, ranking)
    goat = GoatStorytellingEngine(settings)
    auth = AuthService(settings, accounts_repo)
    sarvam_finishing = SarvamFinishingService(settings, llm)
    fast_story = FastStoryEngine(settings, llm)
    storytelling = StorytellingService(
        settings, llm, similarity, goat, sarvam_finishing, fast_story
    )
    catalog_service = CatalogService(
        settings, content_repo, profile_repo, similarity_audit_repo, similarity, discovery, audio_repo
    )
    activity_service = ActivityService(content_repo, activity_repo)
    blend_algorithm = BlendService(settings, ranking)
    blend_service = BlendApplicationService(
        blends_repo, accounts_repo, users_repo, blend_algorithm
    )
    cache = RankingContextCache(
        settings, content_repo, profile_repo, features_repo, activity_repo, users_repo
    )

    orchestrator = PipelineOrchestrator(
        content_intelligence=ContentIntelligenceAgent(
            settings, content_repo, profile_repo, intelligence, similarity, discovery
        ),
        ingestion=IngestionAgent(
            settings, content_repo, activity_repo, features_repo, users_repo, profile_repo
        ),
        insight=InsightAgent(
            settings, content_repo, activity_repo, features_repo, profile_repo, insight_repo, demand
        ),
        runs_repo=runs_repo,
        cache=cache,
    )

    scheduler = PipelineScheduler(settings, orchestrator, activity_repo)

    return Container(
        settings=settings,
        gateway=gateway,
        content_repo=content_repo,
        activity_repo=activity_repo,
        profile_repo=profile_repo,
        features_repo=features_repo,
        users_repo=users_repo,
        insight_repo=insight_repo,
        similarity_audit_repo=similarity_audit_repo,
        runs_repo=runs_repo,
        accounts_repo=accounts_repo,
        blends_repo=blends_repo,
        audio_repo=audio_repo,
        embeddings=embeddings,
        llm=llm,
        intelligence=intelligence,
        similarity=similarity,
        discovery=discovery,
        ranking=ranking,
        demand=demand,
        explanation=explanation,
        evaluation=evaluation,
        storytelling=storytelling,
        goat=goat,
        sarvam_finishing=sarvam_finishing,
        fast_story=fast_story,
        blend_algorithm=blend_algorithm,
        blend_service=blend_service,
        auth=auth,
        catalog_service=catalog_service,
        activity_service=activity_service,
        cache=cache,
        orchestrator=orchestrator,
        scheduler=scheduler,
    )

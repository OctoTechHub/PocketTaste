"""API request/response DTOs. Kept separate from persisted models so storage can
change without breaking the contract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.clock import utcnow
from app.domain.enums import ContentSource, EventType, Provenance
from app.domain.models import Chapter, ContentFeatures, ContentProfile, ContentItem


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterRequest(ApiModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=80)


class LoginRequest(ApiModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AccountResponse(ApiModel):
    user_id: str
    email: str
    display_name: str
    roles: list[str]
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    login_count: int = 0


class TokenResponse(ApiModel):
    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime
    account: AccountResponse


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class ChapterInput(ApiModel):
    index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(ge=0)
    summary: str = Field(default="", max_length=2000)


class ContentCreate(ApiModel):
    content_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    transcript: str = Field(min_length=20, max_length=200_000)
    #: Ignored on POST /catalog — the upload is attributed to the signed-in creator.
    creator_id: str = Field(default="", max_length=64)
    language: str = Field(default="en", min_length=2, max_length=8)
    genres: list[str] = Field(default_factory=list, max_length=8)
    tags: list[str] = Field(default_factory=list, max_length=24)
    duration_seconds: int = Field(default=1800, ge=60, le=200_000)
    chapters: list[ChapterInput] = Field(default_factory=list, max_length=500)
    source: ContentSource = ContentSource.CREATOR_UPLOAD
    published_at: datetime | None = None
    #: Set only when publishing a copilot-narrated story: the merged WAV from the
    #: Sarvam finishing stage (see POST /copilot/narrate), base64-encoded.
    audio_base64: str = Field(default="", max_length=30_000_000)
    audio_language: str = Field(default="", max_length=8)
    audio_source: str = Field(default="", max_length=40)

    @field_validator("genres", "tags")
    @classmethod
    def _normalise(cls, values: list[str]) -> list[str]:
        return [value.strip().lower() for value in values if value.strip()]

    @field_validator("language")
    @classmethod
    def _lower_language(cls, value: str) -> str:
        return value.strip().lower()


class ContentResponse(ApiModel):
    """Catalog item without the heavy transcript payload."""

    content_id: str
    title: str
    description: str
    creator_id: str
    language: str
    genres: list[str]
    tags: list[str]
    duration_seconds: int
    chapter_count: int
    source: ContentSource
    is_synthetic: bool
    published_at: datetime
    transcript_chars: int
    #: Real upstream aggregates (plays, likes, rating, narrator, ...). Empty for
    #: items created through the API. Surfaced so the client can show measured
    #: popularity instead of inventing it.
    popularity: dict = Field(default_factory=dict)
    #: Whether a narrated audio file exists (fetch it via GET /catalog/{id}/audio).
    #: The base64 itself is never included here — it can be hundreds of KB.
    has_audio: bool = False
    audio_language: str = ""

    @classmethod
    def from_domain(cls, item: ContentItem) -> "ContentResponse":
        return cls(
            content_id=item.content_id,
            title=item.title,
            description=item.description,
            creator_id=item.creator_id,
            language=item.language,
            genres=item.genres,
            tags=item.tags,
            duration_seconds=item.duration_seconds,
            chapter_count=len(item.chapters),
            source=item.source,
            is_synthetic=item.is_synthetic,
            published_at=item.published_at,
            transcript_chars=len(item.transcript),
            popularity=item.popularity,
            has_audio=item.has_audio,
            audio_language=item.audio_language,
        )


class ContentDetailResponse(ApiModel):
    content: ContentResponse
    chapters: list[Chapter]
    profile: ContentProfile | None = None
    features: ContentFeatures | None = None


class ContentIngestResponse(ApiModel):
    content_id: str
    created: bool
    similarity_gate: dict | None = None
    profile_queued: bool = True


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


class ActivityCreate(ApiModel):
    """One listener event.

    There is deliberately no `user_id`: it is taken from the bearer token. Accepting
    it from the client would let any caller write events into anyone else's history,
    and the whole demand analysis is downstream of who did what.
    """

    content_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=64)
    event_type: EventType
    position_seconds: int = Field(default=0, ge=0)
    chapter_index: int | None = Field(default=None, ge=0)
    session_seconds: int = Field(default=0, ge=0)
    query: str | None = Field(default=None, max_length=300)
    result_count: int | None = Field(default=None, ge=0)
    device: str = Field(default="android", max_length=32)
    occurred_at: datetime | None = None

    @field_validator("event_type")
    @classmethod
    def _known(cls, value: EventType) -> EventType:
        return value


class ActivityBatchCreate(ApiModel):
    events: list[ActivityCreate] = Field(min_length=1, max_length=5000)


class ActivityAcceptedResponse(ApiModel):
    accepted: int
    rejected: int
    event_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------


class SimilarityCheckRequest(ApiModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=4000)
    transcript: str = Field(default="", max_length=200_000)
    language: str = Field(default="en", max_length=8)
    genres: list[str] = Field(default_factory=list, max_length=8)
    chapters: list[ChapterInput] = Field(default_factory=list, max_length=500)
    exclude_content_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=25)
    #: Controls both LLM narrative-arc extraction and the LLM explanation.
    #: With it off the gate still runs, using deterministic heuristic labels.
    use_llm: bool = True


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class MyRecommendationRequest(ApiModel):
    """Body for POST /me/recommendations. No `user_id`: it comes from the token."""

    limit: int = Field(default=10, ge=1, le=50)
    language: str | None = Field(default=None, max_length=8)
    exclude_content_ids: list[str] = Field(default_factory=list, max_length=200)
    include_seen: bool = False
    include_duplicates: bool = False
    diversity: float | None = Field(default=None, ge=0.0, le=1.0, description="MMR lambda override")
    explain: bool = False


class RecommendationRequest(ApiModel):
    user_id: str = Field(min_length=1, max_length=64)
    limit: int = Field(default=10, ge=1, le=50)
    language: str | None = Field(default=None, max_length=8)
    exclude_content_ids: list[str] = Field(default_factory=list, max_length=200)
    include_seen: bool = False
    include_duplicates: bool = Field(
        default=False, description="Include re-uploads that are normally suppressed."
    )
    diversity: float | None = Field(default=None, ge=0.0, le=1.0, description="MMR lambda override")
    explain: bool = False


# ---------------------------------------------------------------------------
# Discovery (Haystack)
# ---------------------------------------------------------------------------


class DiscoveryRequest(ApiModel):
    query: str = Field(min_length=2, max_length=500)
    user_id: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=8)
    top_k: int = Field(default=6, ge=1, le=25)
    answer: bool = True


class DiscoveryHit(ApiModel):
    content_id: str
    title: str
    language: str
    genres: list[str]
    score: float
    retrievers: list[str]
    snippet: str


class DiscoveryResponse(ApiModel):
    query: str
    hits: list[DiscoveryHit]
    answer: str | None = None
    pipeline: str
    retrievers_used: list[str]
    fusion: str
    logged_as_search: bool = False


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------


class StoryOutlineRequest(ApiModel):
    premise: str = Field(min_length=10, max_length=2000)
    working_title: str = Field(default="", max_length=200)
    genre: str = Field(default="fantasy", max_length=40)
    language: str = Field(default="en", max_length=8)
    target_chapters: int = Field(default=8, ge=3, le=40)
    tone: str = Field(default="", max_length=80)


class StoryDraftRequest(ApiModel):
    """Outline *and* written scene text, via the full GOAT chain."""

    premise: str = Field(min_length=10, max_length=2000)
    working_title: str = Field(default="", max_length=200)
    genre: str = Field(default="fantasy", max_length=40)
    language: str = Field(default="en", max_length=8)
    target_chapters: int = Field(default=8, ge=3, le=40)
    tone: str = Field(default="", max_length=80)
    #: Each scene is a separate model call, so this is the main cost dial.
    scenes_to_write: int = Field(default=2, ge=1, le=10)
    #: Sarvam AI finishing stage, run after the similarity gate clears. Both optional.
    #: ISO code of an Indic language (hi, ta, te, bn, mr, kn, gu, ml, pa, od) to
    #: translate the cleared draft into via Sarvam's Translate API.
    localize_to: str | None = Field(default=None, max_length=8)
    #: Synthesize TTS narration of the final (localized, if requested) text via
    #: Sarvam's Bulbul model.
    narrate: bool = Field(default=False)


class BlendCreate(ApiModel):
    """Start a blend by naming the other listener's email address."""

    email: str = Field(min_length=3, max_length=254)


class NarrateRequest(ApiModel):
    """Run the Sarvam finishing stage on already-generated text, without re-running
    GOAT. Used by the "convert to voice" step in the Studio Copilot, so re-narrating
    or re-localizing a draft doesn't cost another round of story generation."""

    text: str = Field(min_length=10, max_length=200_000)
    language: str = Field(default="en", max_length=8)
    localize_to: str | None = Field(default=None, max_length=8)


class ChapterBeat(ApiModel):
    index: int
    title: str
    beat: str
    hook: str


class StoryOutlineResponse(ApiModel):
    working_title: str
    logline: str
    setting: str
    characters: list[dict]
    chapters: list[ChapterBeat]
    originality: dict
    demand_context: dict
    generated_by: str
    notice: str


# ---------------------------------------------------------------------------
# Pipeline / evaluation
# ---------------------------------------------------------------------------


class PipelineRunRequest(ApiModel):
    stages: list[str] | None = Field(default=None, description="Subset of agents to run, in order.")
    force_relabel: bool = False
    use_llm: bool = True


class EvaluationRequest(ApiModel):
    k: int = Field(default=10, ge=1, le=50)
    max_users: int = Field(default=200, ge=1, le=5000)
    min_interactions: int = Field(default=3, ge=2, le=50)


class HealthResponse(ApiModel):
    status: str
    version: str
    environment: str
    dependencies: dict
    catalog: dict
    provenance: Provenance
    checked_at: datetime = Field(default_factory=utcnow)

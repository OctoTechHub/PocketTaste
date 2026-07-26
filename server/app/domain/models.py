"""Persisted domain models. Pure data — no database, no network, no framework."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.clock import utcnow
from app.domain.enums import (
    AgentName,
    Confidence,
    ContentSource,
    DuplicateKind,
    EventType,
    LabelSource,
    Pacing,
    Provenance,
    RiskLevel,
    RunStatus,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class Chapter(DomainModel):
    index: int = Field(ge=0)
    title: str
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(ge=0)
    summary: str = ""

    @property
    def duration_seconds(self) -> int:
        return max(0, self.end_seconds - self.start_seconds)


class ContentItem(DomainModel):
    """A story/episode in the catalog."""

    content_id: str
    title: str
    description: str
    transcript: str
    creator_id: str
    language: str = "en"
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    duration_seconds: int = Field(default=1800, ge=1)
    chapters: list[Chapter] = Field(default_factory=list)
    source: ContentSource = ContentSource.PLATFORM
    is_synthetic: bool = False
    published_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    #: Real platform aggregates carried over from the upstream catalog (plays, likes,
    #: rating, narrator...). Empty for items created through the API. These are
    #: measured facts, unlike the per-event stream, which may be simulated.
    popularity: dict = Field(default_factory=dict)
    #: Narration produced by the Sarvam TTS finishing stage (see
    #: `services/sarvam_finishing.py`). Empty for every item that was not narrated
    #: through the copilot — this is not a general media host.
    audio_base64: str = ""
    audio_language: str = ""
    audio_source: str = ""
    #: Stored redundantly rather than derived from `audio_base64`: catalog list
    #: reads project that field out (it can be hundreds of KB per item), so a
    #: derived property would silently read as False on every list response.
    has_audio: bool = False

    @property
    def primary_genre(self) -> str:
        return self.genres[0] if self.genres else "general"

    def searchable_text(self) -> str:
        return " \n".join(
            [self.title, self.description, " ".join(self.genres), " ".join(self.tags), self.transcript]
        )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class UserAccount(DomainModel):
    """A real, authenticated person.

    Distinct from `UserProfile`, which is the *derived* taste state. An account is
    who someone is; a profile is what they listen to. Simulated listeners have a
    profile and no account, which is precisely how real and simulated activity stay
    separable.
    """

    user_id: str
    email: str
    display_name: str
    password_hash: str = Field(repr=False)
    roles: list[str] = Field(default_factory=lambda: ["listener"])
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None
    login_count: int = 0

    def public(self) -> dict:
        """Everything except the credential. Used for every outbound payload."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "roles": self.roles,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
            "login_count": self.login_count,
        }


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


class ActivityEvent(DomainModel):
    """One logged listener interaction. This is the fuel for the whole system."""

    event_id: str
    user_id: str
    content_id: str | None = None
    session_id: str
    event_type: EventType
    position_seconds: int = Field(default=0, ge=0)
    chapter_index: int | None = None
    session_seconds: int = Field(default=0, ge=0)
    query: str | None = None
    result_count: int | None = None  # for SEARCH: 0 means unmet demand
    device: str = "android"
    is_synthetic: bool = False
    occurred_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Content intelligence
# ---------------------------------------------------------------------------


class NarrativeFingerprint(DomainModel):
    """Structured story skeleton. Two re-titled uploads of the same story collide here
    even when their wording is completely different."""

    premise: str = ""
    protagonist_archetype: str = ""
    central_conflict: str = ""
    setting: str = ""
    progression_system: str = ""
    resolution_shape: str = ""
    tropes: list[str] = Field(default_factory=list)

    def as_text(self) -> str:
        return " | ".join(
            [
                self.premise,
                self.protagonist_archetype,
                self.central_conflict,
                self.setting,
                self.progression_system,
                self.resolution_shape,
                " ".join(sorted(self.tropes)),
            ]
        ).strip()

    def is_empty(self) -> bool:
        return not self.as_text().replace("|", "").strip()


class ContentProfile(DomainModel):
    """Everything the Content Intelligence Agent derives about one catalog item."""

    content_id: str
    embedding: list[float] = Field(default_factory=list)
    arc_embedding: list[float] = Field(default_factory=list)
    embedding_model: str = "hash-fallback"
    embedding_dimensions: int = 0
    themes: list[str] = Field(default_factory=list)
    tone: str = "neutral"
    tropes: list[str] = Field(default_factory=list)
    narrative_pattern: str = "unclassified"
    target_audience: str = "general"
    pacing: Pacing = Pacing.MEDIUM
    fingerprint: NarrativeFingerprint = Field(default_factory=NarrativeFingerprint)
    cluster_id: str | None = None
    cluster_size: int = 1
    originality_score: float = 1.0
    duplicate_risk: float = 0.0
    duplicate_kind: DuplicateKind = DuplicateKind.NONE
    nearest_neighbours: list[dict] = Field(default_factory=list)
    label_source: LabelSource = LabelSource.HEURISTIC
    computed_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Behavioural features
# ---------------------------------------------------------------------------


class RetentionPoint(DomainModel):
    decile: int = Field(ge=1, le=10)
    position_seconds: int
    retained_ratio: float = Field(ge=0.0, le=1.0)


class ChapterInterest(DomainModel):
    chapter_index: int
    title: str = ""
    replays: int = 0
    drop_offs: int = 0
    jumps_in: int = 0
    skips: int = 0
    listeners: int = 0
    interest_score: float = 0.0     # normalised [0,1]; high = re-listened, low = abandoned


class ContentFeatures(DomainModel):
    """Behavioural features for one catalog item, derived only from logged events."""

    content_id: str
    plays: int = 0
    unique_listeners: int = 0
    sessions: int = 0
    completions: int = 0
    completion_rate: float = 0.0
    skip_rate: float = 0.0
    replay_rate: float = 0.0
    drop_off_rate: float = 0.0
    median_abandon_seconds: int | None = None
    abandon_point_ratio: float | None = None      # median abandon / duration
    avg_session_seconds: float = 0.0
    re_engagement_rate: float = 0.0               # share of listeners returning in a later session
    retention_curve: list[RetentionPoint] = Field(default_factory=list)
    chapter_interest: list[ChapterInterest] = Field(default_factory=list)
    quality_score: float = 0.0                    # blended retention health, [0,1]
    sample_size: int = 0
    confidence: Confidence = Confidence.LOW
    provenance: Provenance = Provenance.REAL
    computed_at: datetime = Field(default_factory=utcnow)


class UserProfile(DomainModel):
    """Per-listener taste state. Independent of any platform-side profile."""

    user_id: str
    taste_vector: list[float] = Field(default_factory=list)
    genre_affinity: dict[str, float] = Field(default_factory=dict)
    language_affinity: dict[str, float] = Field(default_factory=dict)
    pacing_preference: Pacing = Pacing.MEDIUM
    completion_propensity: float = 0.0
    avg_abandon_ratio: float | None = None
    re_engagement_score: float = 0.0
    interacted_content_ids: list[str] = Field(default_factory=list)
    positive_content_ids: list[str] = Field(default_factory=list)
    #: Most-recent-last ordered positive history. Order is the signal a bag-of-items
    #: taste vector throws away.
    recent_sequence: list[str] = Field(default_factory=list)
    events_observed: int = 0
    sessions_observed: int = 0
    is_cold_start: bool = True
    last_active_at: datetime | None = None
    computed_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Similarity gate
# ---------------------------------------------------------------------------


class SimilaritySignals(DomainModel):
    """Each signal is reported separately so a reviewer can see *why* it matched."""

    narrative_arc: float = 0.0
    semantic: float = 0.0
    lexical_shingle: float = 0.0
    title: float = 0.0
    description: float = 0.0
    chapter_structure: float = 0.0


class SimilarityMatch(DomainModel):
    content_id: str
    title: str
    creator_id: str
    language: str
    combined_score: float
    signals: SimilaritySignals
    duplicate_kind: DuplicateKind = DuplicateKind.NONE
    rationale: str = ""


class SimilarityReport(DomainModel):
    candidate_title: str
    risk: RiskLevel
    originality_score: float
    top_score: float
    duplicate_kind: DuplicateKind
    matches: list[SimilarityMatch] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    #: Signals actually used for this draft. A premise with no transcript cannot be
    #: measured for verbatim overlap, so that signal is excluded and the remaining
    #: weights are renormalised rather than scoring it as a zero.
    applied_signals: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    candidates_compared: int = 0
    explanation: str = ""
    disclaimer: str = (
        "Similarity is a screening signal, not a legal plagiarism ruling. "
        "A 'block' verdict means a human must review the upload before it goes live."
    )
    computed_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class RecommendationSignals(DomainModel):
    affinity: float = 0.0
    co_occurrence: float = 0.0
    sequence: float = 0.0
    retention: float = 0.0
    genre_affinity: float = 0.0
    freshness: float = 0.0
    originality: float = 0.0
    exploration: float = 0.0


class RecommendedItem(DomainModel):
    content_id: str
    title: str
    language: str
    genres: list[str] = Field(default_factory=list)
    relevance_score: float
    final_score: float               # after MMR diversity re-selection
    rank: int
    signals: RecommendationSignals
    contributions: dict[str, float] = Field(default_factory=dict)  # weight * signal
    reason: str = ""


class RecommendationResult(DomainModel):
    user_id: str
    items: list[RecommendedItem] = Field(default_factory=list)
    strategy: str = "hybrid"
    cold_start: bool = False
    candidate_pool_size: int = 0
    #: Re-uploads withheld from this list. Reported, never silently dropped.
    suppressed_duplicates: int = 0
    weights: dict[str, float] = Field(default_factory=dict)
    mmr_lambda: float = 0.0
    provenance: Provenance = Provenance.REAL
    explanation: str = ""
    generated_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Creator-facing demand intelligence
# ---------------------------------------------------------------------------


class DemandSegment(DomainModel):
    """One (genre, language) market cell with its measured supply/demand gap."""

    segment: str
    genre: str
    language: str
    catalog_items: int = 0
    supply_share: float = 0.0
    unique_listeners: int = 0
    plays: int = 0
    completions: int = 0
    weighted_demand: float = 0.0
    demand_share: float = 0.0
    unmet_search_count: int = 0        # searches in this segment that returned nothing
    completion_rate: float = 0.0
    drop_off_rate: float = 0.0
    duplicate_density: float = 0.0     # share of catalog items flagged as near-duplicates
    opportunity_score: float = 0.0     # demand_share - supply_share, saturation-adjusted
    execution_gap: float = 0.0         # high demand + poor retention = quality opportunity
    sample_size: int = 0
    confidence: Confidence = Confidence.LOW
    evidence: dict = Field(default_factory=dict)


class PatternSaturation(DomainModel):
    """Narrative patterns that are over-supplied relative to how well they retain."""

    narrative_pattern: str
    catalog_items: int
    share_of_catalog: float
    avg_completion_rate: float
    avg_drop_off_rate: float
    saturation_index: float            # supply share / retention health
    measured_items: int = 0            # items in this pattern that anyone actually played
    listeners: int = 0                 # total listeners behind the retention figure
    verdict: str


class CreatorBrief(DomainModel):
    """A concrete, evidence-backed suggestion for a creator."""

    brief_id: str
    headline: str
    segment: str
    language: str
    genre: str
    rationale: str
    supporting_metrics: dict = Field(default_factory=dict)
    avoid_patterns: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    generated_by: LabelSource = LabelSource.HEURISTIC


class DemandReport(DomainModel):
    segments: list[DemandSegment] = Field(default_factory=list)
    saturated_patterns: list[PatternSaturation] = Field(default_factory=list)
    briefs: list[CreatorBrief] = Field(default_factory=list)
    catalog_items: int = 0
    events_analysed: int = 0
    unique_listeners: int = 0
    #: Zero-result searches we could not confidently place in a (genre, language)
    #: cell. Reported rather than guessed into a segment.
    unattributed_unmet_searches: int = 0
    provenance: Provenance = Provenance.REAL
    data_notice: str = ""
    generated_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------


class AgentRun(DomainModel):
    run_id: str
    agent: AgentName | str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int = 0
    processed: int = 0
    written: int = 0
    skipped: int = 0
    stats: dict = Field(default_factory=dict)
    error: str | None = None


class PipelineRun(DomainModel):
    run_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int = 0
    stages: list[AgentRun] = Field(default_factory=list)
    triggered_by: str = "api"
    error: str | None = None

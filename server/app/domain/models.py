"""Domain entities for PocketTaste.

Pure Pydantic models — no persistence, no framework coupling. Everything else in
the system depends on these definitions, so they sit at the centre.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Language = Literal["Hindi", "English", "Tamil", "Telugu", "Bengali", "Marathi"]

Genre = Literal[
    "romance",
    "thriller",
    "horror",
    "mythology",
    "scifi",
    "comedy",
    "drama",
    "crime",
    "fantasy",
    "slice-of-life",
]

Tone = Literal[
    "dark",
    "wholesome",
    "suspenseful",
    "emotional",
    "lighthearted",
    "gritty",
    "romantic",
    "inspirational",
]

Pacing = Literal["slow-burn", "medium", "fast"]

EventType = Literal[
    "play",
    "complete_episode",
    "complete_series",
    "skip_intro",
    "drop",
    "coin_unlock",
    "rate",
]

CandidateSource = Literal["content", "collaborative", "popularity", "query"]


class Series(BaseModel):
    """A long-form audio series in the catalog."""

    id: str
    title: str
    synopsis: str
    genres: list[Genre] = Field(default_factory=list)
    language: Language
    tone: list[Tone] = Field(default_factory=list)
    pacing: Pacing
    episode_count: int
    avg_episode_minutes: float
    narrator: str = ""
    is_original: bool = False
    is_new: bool = False
    popularity: float = 0.0  # 0..1 global proxy
    coin_price_approx: int = 0  # coins to unlock the paid portion
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)


class BehaviorEvent(BaseModel):
    """A single behavioral signal — the raw fuel for the taste profile."""

    user_id: str
    series_id: str
    type: EventType
    episode_index: Optional[int] = None
    completion_pct: Optional[float] = None
    coins: Optional[int] = None
    value: Optional[float] = None  # explicit rating for type == "rate"
    session_id: Optional[str] = None
    ts: int  # epoch ms


class User(BaseModel):
    id: str
    display_name: str
    languages: list[Language] = Field(default_factory=list)
    created_at: int


class TasteProfile(BaseModel):
    """Derived listener model — computed from behavior, never stored raw."""

    user_id: str
    taste_vector: list[float] = Field(default_factory=list)
    genre_affinity: dict[str, float] = Field(default_factory=dict)
    language_affinity: dict[str, float] = Field(default_factory=dict)
    tone_affinity: dict[str, float] = Field(default_factory=dict)
    pacing_affinity: dict[str, float] = Field(default_factory=dict)
    avg_preferred_episode_minutes: float = 0.0
    coin_spend: int = 0
    completed_series_ids: list[str] = Field(default_factory=list)
    dropped_series_ids: list[str] = Field(default_factory=list)
    recent_series_ids: list[str] = Field(default_factory=list)
    event_count: int = 0


class ScoreBreakdown(BaseModel):
    """Transparent breakdown of why a series scored the way it did."""

    content_similarity: float
    genre_affinity: float
    language_match: float
    tone_match: float
    pacing_match: float
    length_fit: float
    monetization_proxy: float
    freshness: float
    total: float


class RankedSeries(BaseModel):
    series: Series
    score: float
    breakdown: ScoreBreakdown
    sources: list[CandidateSource] = Field(default_factory=list)
    reason: Optional[str] = None


class FeedRail(BaseModel):
    key: str
    title: str
    subtitle: Optional[str] = None
    items: list[RankedSeries] = Field(default_factory=list)


class DiscoveryIntent(BaseModel):
    """Structured intent parsed from a natural-language discovery query."""

    genres: list[Genre] = Field(default_factory=list)
    exclude_genres: list[Genre] = Field(default_factory=list)
    language: Optional[Language] = None
    tones: list[Tone] = Field(default_factory=list)
    pacing: Optional[Pacing] = None
    max_episode_minutes: Optional[float] = None
    keywords: list[str] = Field(default_factory=list)
    mood_text: str = ""

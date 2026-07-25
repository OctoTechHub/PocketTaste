"""Closed vocabularies shared by every layer."""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    """Every meaningful listener interaction we log."""

    PLAY = "play"
    PAUSE = "pause"
    RESUME = "resume"
    SKIP = "skip"
    REPLAY = "replay"
    COMPLETE = "complete"
    DROP_OFF = "drop_off"
    CHAPTER_JUMP = "chapter_jump"
    SEARCH = "search"
    REVISIT = "revisit"


#: Signed interaction weights used to build taste vectors and affinity scores.
#: Negative events matter as much as positive ones — an early abandon is a
#: stronger statement about taste than a play.
EVENT_WEIGHTS: dict[EventType, float] = {
    EventType.COMPLETE: 1.00,
    EventType.REPLAY: 0.90,
    EventType.REVISIT: 0.70,
    EventType.RESUME: 0.50,
    EventType.PLAY: 0.30,
    EventType.CHAPTER_JUMP: 0.15,
    EventType.PAUSE: 0.05,
    EventType.SEARCH: 0.00,
    EventType.SKIP: -0.40,
    EventType.DROP_OFF: -0.60,
}

#: Events that count as a genuine positive interaction for candidate generation.
POSITIVE_EVENTS = frozenset({EventType.COMPLETE, EventType.REPLAY, EventType.REVISIT, EventType.RESUME})


class RiskLevel(StrEnum):
    """Verdict of the similarity gate. `BLOCK` is a hard stop for upload."""

    CLEAR = "clear"
    REVIEW = "review"
    BLOCK = "block"


class DuplicateKind(StrEnum):
    NONE = "none"
    SERIES_VARIANT = "series_variant"     # "Solo Leveling Season 3" re-upload of the same audio
    NEAR_DUPLICATE = "near_duplicate"     # reworded but structurally identical
    EXACT_DUPLICATE = "exact_duplicate"   # verbatim transcript overlap


class ContentSource(StrEnum):
    PLATFORM = "platform"
    CREATOR_UPLOAD = "creator_upload"
    SYNTHETIC = "synthetic"


class Provenance(StrEnum):
    """Attached to every aggregate so no number can be mistaken for real traffic."""

    REAL = "real"
    #: Both catalog and events invented by the built-in simulator.
    SYNTHETIC_SIMULATION = "synthetic_simulation"
    #: The catalog and its aggregate metrics (plays, likes, rating) are the
    #: platform's real data; only the per-listener event stream is simulated, and its
    #: volume is calibrated to those real aggregates. Stronger than
    #: `synthetic_simulation`, weaker than `real` — and it must not be conflated
    #: with either.
    SIMULATED_FROM_REAL_CATALOG = "simulated_from_real_catalog"
    MIXED = "mixed"


class Pacing(StrEnum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentName(StrEnum):
    INGESTION = "ingestion_agent"
    CONTENT_INTELLIGENCE = "content_intelligence_agent"
    INSIGHT = "insight_agent"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class LabelSource(StrEnum):
    """Whether a label came from an LLM or a deterministic fallback — always disclosed."""

    LLM = "llm"
    HEURISTIC = "heuristic"

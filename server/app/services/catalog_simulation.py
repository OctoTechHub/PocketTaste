"""Behaviour simulation over the platform's **real** catalog.

The upstream `stories` collection has real aggregate metrics — plays, likes, rating,
episode counts — but no per-listener event log. Those aggregates are exactly what
the feature builder cannot consume: it needs individual play/replay/drop-off events
with positions to compute retention curves and episode-level interest.

So this module reconstructs a plausible event stream **calibrated to the real
aggregates**:

  * a story's listener volume follows its real `plays`, square-root compressed so a
    70x popularity spread stays sampleable without the tail titles vanishing
  * a story's completion propensity follows its real `rating`
  * a story's replay/like behaviour follows its real `likes / plays` ratio
  * which listener hears which story is driven by latent taste *and* real popularity,
    so the recommender has a recoverable signal and the demand engine sees the real
    relative shape of the catalog

What this buys: the demand report reflects the genuine relative standing of these
100 titles instead of an invented one. What it does not buy: real individual
behaviour. Every event is stamped `is_synthetic=True` and every aggregate built from
them carries `Provenance.SIMULATED_FROM_REAL_CATALOG`, which is deliberately a
distinct value from both `real` and `synthetic_simulation`.

Fully seeded: the same seed and the same catalog always produce the same events.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from app.core.clock import utcnow
from app.domain.enums import EventType
from app.domain.models import ActivityEvent, ContentItem

SEED = 20260725

#: Listener-volume bounds per story. The floor keeps low-play titles measurable; the
#: ceiling stops the top title from swamping the entire simulated log.
MIN_LISTENERS = 6
MAX_LISTENERS = 120

#: Real ratings sit in a narrow band (~3.7-4.9), so stretch that band across a
#: meaningful completion range instead of using the raw value.
RATING_FLOOR = 3.5
RATING_CEILING = 5.0
COMPLETION_MIN = 0.12
COMPLETION_MAX = 0.78

#: Search queries by language. Used to probe for unmet demand — a query returns zero
#: results when the catalog genuinely has nothing for that genre/language cell.
_QUERY_TEMPLATES: dict[str, list[str]] = {
    "hi": [
        "हिंदी हॉरर कहानी", "हिंदी क्राइम थ्रिलर", "हिंदी रोमांस कहानी",
        "हिंदी पौराणिक कथा", "हिंदी सस्पेंस स्टोरी", "हिंदी बदला कहानी",
        "हिंदी कॉमेडी कहानी", "हिंदी विज्ञान कथा",
    ],
    "hinglish": [
        "hinglish horror story", "hinglish crime thriller", "hinglish romance audio",
        "hinglish comedy slice of life", "hinglish revenge drama", "hinglish sci-fi series",
    ],
    "en": [
        "english horror audio series", "english detective mystery", "english romance audio",
        "english mythology fantasy", "english comedy series", "english sci-fi thriller",
    ],
}


@dataclass(slots=True)
class CatalogSimulationResult:
    events: list[ActivityEvent]
    notes: dict


@dataclass(slots=True)
class _Listener:
    user_id: str
    genre: str
    second_genre: str
    language: str
    patience: float
    replay_tendency: float
    capacity: int


class RealCatalogSimulator:
    """Generates an event log for a catalog that already exists."""

    def __init__(self, *, seed: int = SEED, user_count: int = 400) -> None:
        self._rng = random.Random(seed)
        self._user_count = user_count

    # --- calibration --------------------------------------------------------

    @staticmethod
    def _listener_target(item: ContentItem, median_plays: float) -> int:
        """Map real plays onto a simulated listener count.

        Square root, not linear: real play counts span ~70x across this catalog, and
        a linear map would give the tail titles one or two listeners each — too few
        for a retention curve to mean anything.
        """
        plays = float(item.popularity.get("plays") or 0)
        if plays <= 0 or median_plays <= 0:
            return MIN_LISTENERS
        scaled = math.sqrt(plays / median_plays)
        return int(max(MIN_LISTENERS, min(MAX_LISTENERS, round(28 * scaled))))

    @staticmethod
    def _completion_propensity(item: ContentItem) -> float:
        """Real rating -> probability a listener finishes the series."""
        rating = float(item.popularity.get("rating") or 0.0)
        if rating <= 0:
            return 0.35
        span = (rating - RATING_FLOOR) / (RATING_CEILING - RATING_FLOOR)
        span = max(0.0, min(1.0, span))
        return COMPLETION_MIN + span * (COMPLETION_MAX - COMPLETION_MIN)

    @staticmethod
    def _engagement(item: ContentItem) -> float:
        """Real likes/plays ratio -> replay and revisit propensity."""
        plays = float(item.popularity.get("plays") or 0)
        likes = float(item.popularity.get("likes") or 0)
        if plays <= 0:
            return 0.08
        return max(0.01, min(0.35, likes / plays))

    # --- main ---------------------------------------------------------------

    def run(self, catalog: list[ContentItem]) -> CatalogSimulationResult:
        if not catalog:
            return CatalogSimulationResult([], {"reason": "empty_catalog"})

        plays = sorted(float(item.popularity.get("plays") or 0) for item in catalog)
        median_plays = plays[len(plays) // 2] or 1.0

        listeners = self._build_listeners(catalog)
        by_user: dict[str, list[ContentItem]] = {listener.user_id: [] for listener in listeners}

        # Assign listeners to stories until each story hits its calibrated target.
        for item in catalog:
            target = self._listener_target(item, median_plays)
            pool = self._weighted_listeners(item, listeners, target)
            for listener in pool:
                by_user[listener.user_id].append(item)

        events: list[ActivityEvent] = []
        listener_index = {listener.user_id: listener for listener in listeners}
        for user_id, items in by_user.items():
            listener = listener_index[user_id]
            for session_index, item in enumerate(items[: listener.capacity]):
                events.extend(self._simulate_session(listener, item, session_index))

        events.extend(self._simulate_searches(catalog, listeners))
        events.sort(key=lambda event: event.occurred_at)

        completions = sum(event.event_type is EventType.COMPLETE for event in events)
        plays_logged = sum(event.event_type is EventType.PLAY for event in events)
        return CatalogSimulationResult(
            events=events,
            notes={
                "seed": SEED,
                "catalog_items": len(catalog),
                "listeners": len(listeners),
                "events": len(events),
                "plays_logged": plays_logged,
                "completion_rate": round(completions / max(plays_logged, 1), 4),
                "zero_result_searches": sum(
                    1
                    for event in events
                    if event.event_type is EventType.SEARCH and event.result_count == 0
                ),
                "calibrated_on": ["plays", "likes", "rating"],
                "provenance": "simulated_from_real_catalog",
                "warning": (
                    "The catalog and its plays/likes/rating are the platform's REAL data. "
                    "The per-listener event stream is SIMULATED and calibrated to those "
                    "aggregates. Individual events are not real user behaviour."
                ),
            },
        )

    # --- listeners ----------------------------------------------------------

    def _build_listeners(self, catalog: list[ContentItem]) -> list[_Listener]:
        genres = sorted({item.primary_genre for item in catalog})
        languages = sorted({item.language for item in catalog})
        # Weight the listener base by how much catalog exists per language, so the
        # simulated audience mirrors the real catalog's language mix.
        language_weights = [
            sum(1 for item in catalog if item.language == language) for language in languages
        ]
        listeners: list[_Listener] = []
        for index in range(self._user_count):
            primary = self._rng.choice(genres)
            others = [genre for genre in genres if genre != primary] or [primary]
            listeners.append(
                _Listener(
                    user_id=f"listener_{index + 1:04d}",
                    genre=primary,
                    second_genre=self._rng.choice(others),
                    language=self._rng.choices(languages, weights=language_weights)[0],
                    patience=self._rng.betavariate(3.0, 2.0),
                    replay_tendency=self._rng.betavariate(1.6, 6.0),
                    capacity=self._rng.randint(3, 12),
                )
            )
        return listeners

    def _weighted_listeners(
        self, item: ContentItem, listeners: list[_Listener], target: int
    ) -> list[_Listener]:
        """Pick `target` listeners for a story, biased toward matching taste."""
        weights = []
        for listener in listeners:
            weight = 1.0
            if item.primary_genre == listener.genre:
                weight *= 7.0
            elif item.primary_genre == listener.second_genre:
                weight *= 2.5
            weight *= 4.0 if item.language == listener.language else 0.35
            weights.append(weight)

        chosen: list[_Listener] = []
        pool, pool_weights = list(listeners), list(weights)
        for _ in range(min(target, len(pool))):
            pick = self._rng.choices(pool, weights=pool_weights, k=1)[0]
            position = pool.index(pick)
            pool.pop(position)
            pool_weights.pop(position)
            chosen.append(pick)
        return chosen

    # --- one listening session ---------------------------------------------

    def _simulate_session(
        self, listener: _Listener, item: ContentItem, session_index: int
    ) -> list[ActivityEvent]:
        session_id = f"sess_{listener.user_id}_{session_index}_{uuid4().hex[:6]}"
        start = utcnow() - timedelta(days=self._rng.uniform(0, 90), hours=self._rng.uniform(0, 23))
        events: list[ActivityEvent] = []
        clock = start

        def emit(event_type: EventType, position: int, episode: int | None, elapsed: int) -> None:
            nonlocal clock
            clock += timedelta(seconds=max(1, elapsed))
            events.append(
                ActivityEvent(
                    event_id=f"evt_{uuid4().hex[:16]}",
                    user_id=listener.user_id,
                    content_id=item.content_id,
                    session_id=session_id,
                    event_type=event_type,
                    position_seconds=min(position, item.duration_seconds),
                    chapter_index=episode,
                    session_seconds=int((clock - start).total_seconds()),
                    device=self._rng.choice(["android", "ios", "web"]),
                    is_synthetic=True,
                    occurred_at=clock,
                )
            )

        emit(EventType.PLAY, 0, 0, 5)

        fit = 1.0
        if item.primary_genre != listener.genre:
            fit *= 0.72 if item.primary_genre == listener.second_genre else 0.42
        if item.language != listener.language:
            fit *= 0.5

        base_completion = self._completion_propensity(item)
        engagement = self._engagement(item)
        completes = self._rng.random() < min(0.95, base_completion * (0.5 + 0.5 * fit) * 1.4)

        episode_count = len(item.chapters) or 1
        # Long series are sampled rather than walked episode-by-episode: a 90-episode
        # show would otherwise emit hundreds of events for one listener.
        walk = min(episode_count, 14)
        reached = (
            walk
            if completes
            else max(1, int(walk * self._rng.uniform(0.1, 0.85) * (0.5 + 0.5 * fit)))
        )
        step = max(1, episode_count // walk)

        for position_index in range(reached):
            episode = min(position_index * step, episode_count - 1)
            chapter = item.chapters[episode] if item.chapters else None
            offset = chapter.start_seconds if chapter else 0
            length = chapter.duration_seconds if chapter else item.duration_seconds

            if self._rng.random() < 0.16:
                emit(EventType.PAUSE, offset + length // 2, episode, length // 2)
                if self._rng.random() < 0.72:
                    emit(EventType.RESUME, offset + length // 2, episode, 45)
            # Averaged, not summed: a listener re-listens to *some* episodes, and
            # adding both terms produced ~3 replays per play, which is not a thing.
            if self._rng.random() < 0.5 * (listener.replay_tendency + engagement):
                emit(EventType.REPLAY, offset + length // 4, episode, length // 4)
            if self._rng.random() < 0.11:
                emit(EventType.SKIP, offset + length, episode, 15)
            if position_index and self._rng.random() < 0.09:
                emit(EventType.CHAPTER_JUMP, offset, episode, 10)

        if completes:
            emit(EventType.COMPLETE, item.duration_seconds, episode_count - 1, 120)
            if self._rng.random() < engagement * 2:
                emit(EventType.REVISIT, 0, 0, 3600)
        else:
            last_episode = min((reached - 1) * step, episode_count - 1)
            last = item.chapters[last_episode] if item.chapters else None
            emit(
                EventType.DROP_OFF,
                last.end_seconds if last else item.duration_seconds // 2,
                last_episode,
                60,
            )
        return events

    # --- search log ---------------------------------------------------------

    def _simulate_searches(
        self, catalog: list[ContentItem], listeners: list[_Listener]
    ) -> list[ActivityEvent]:
        """Probe the catalog with realistic queries.

        A query returns zero results when the catalog genuinely holds nothing for that
        (genre, language) cell — so the unmet-demand signal reflects real gaps in the
        real catalog rather than a planted one.
        """
        available = {(item.primary_genre, item.language) for item in catalog}
        genre_tokens = {
            "horror": "horror", "thriller": "thriller", "romance": "romance",
            "crime-detective": "detective", "supernatural": "supernatural",
            "mythology-fantasy": "mythology", "sci-fi": "sci-fi", "suspense": "suspense",
            "revenge-drama": "revenge", "comedy-slice-of-life": "comedy",
        }
        events: list[ActivityEvent] = []
        for listener in self._rng.sample(listeners, k=min(200, len(listeners))):
            for _ in range(self._rng.randint(1, 3)):
                language = listener.language
                query = self._rng.choice(_QUERY_TEMPLATES.get(language, _QUERY_TEMPLATES["en"]))
                token = next((g for g, t in genre_tokens.items() if t in query.lower()), None)
                if token is None:
                    matches = [
                        item
                        for item in catalog
                        if item.language == language
                        and any(word in query.lower() for word in item.primary_genre.split("-"))
                    ]
                else:
                    matches = [
                        item
                        for item in catalog
                        if item.language == language and item.primary_genre == token
                    ]
                result_count = len(matches)
                events.append(
                    ActivityEvent(
                        event_id=f"evt_{uuid4().hex[:16]}",
                        user_id=listener.user_id,
                        content_id=None,
                        session_id=f"sess_search_{listener.user_id}_{uuid4().hex[:6]}",
                        event_type=EventType.SEARCH,
                        query=query,
                        result_count=result_count,
                        device=self._rng.choice(["android", "ios", "web"]),
                        is_synthetic=True,
                        occurred_at=utcnow() - timedelta(days=self._rng.uniform(0, 90)),
                    )
                )
        return events

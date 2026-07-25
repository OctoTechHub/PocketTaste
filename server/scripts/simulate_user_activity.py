"""Generate a realistic listening history for the registered accounts.

    python -m scripts.simulate_user_activity              # dry run: show the plan
    python -m scripts.simulate_user_activity --apply
    python -m scripts.simulate_user_activity --apply --clear   # replace previous runs
    python -m scripts.simulate_user_activity --days 90 --apply

**These events are simulated, and they are written with `is_synthetic=True`.** They
are attributed to real accounts, but nobody actually listened to anything. After this
runs, provenance across the system reports `mixed` rather than `real`, and every
report says so. `scripts/clean_data.py --apply` removes them again.

Why bother: four accounts with ten events each cannot exercise a recommender. There
is no retention curve to draw from a single play, no episode-level interest, no
sequence to learn from. This produces the shape of real serial-audio listening so the
pipeline has something to compute on.

What makes it realistic rather than random — each pattern exists because it is what
the feature builder is designed to detect:

  * **Episode-by-episode progression.** Nobody consumes a 57-episode series in one
    sitting. Sessions of 3-8 episodes, spread over days, with `position_seconds`
    advancing through real episode boundaries. This is what fills the retention curve.
  * **Paywall churn.** Premium series lose a chunk of listeners at the episode where
    payment starts. That produces a retention cliff at a *specific* point, which is
    exactly the signal a creator needs to see.
  * **Mid-series churn.** Some listeners drop and never return; others go quiet and
    revisit weeks later. The two look identical after one session and completely
    different after six.
  * **Replay clustering.** Re-listens concentrate on a few episodes rather than
    scattering uniformly — that is what chapter-interest scoring is looking for.
  * **Search before discovery.** A new series usually follows a search, and some of
    those searches return nothing, which is the unmet-demand signal.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import build_container  # noqa: E402
from app.core.clock import utcnow  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.data.mongo import MongoGateway  # noqa: E402
from app.domain.enums import EventType  # noqa: E402
from app.domain.models import ActivityEvent, ContentItem  # noqa: E402

logger = get_logger("simulate")

SEED = 20260726


@dataclass(slots=True)
class Persona:
    """Derived from what each account has actually listened to so far, so the
    generated history extends their real taste instead of contradicting it."""

    email: str
    primary_genre: str
    secondary_genre: str
    languages: tuple[str, ...]
    patience: float          # probability of finishing a series they enjoy
    binge: tuple[int, int]   # episodes per sitting
    replay_rate: float
    explores: float          # chance of trying something outside their genres


PERSONAS: dict[str, Persona] = {
    "krish@gmail.com": Persona("krish@gmail.com", "horror", "thriller", ("hi", "hinglish"), 0.62, (4, 9), 0.22, 0.20),
    "amogh@gmail.com": Persona("amogh@gmail.com", "crime-detective", "suspense", ("hi", "hinglish"), 0.71, (5, 11), 0.14, 0.15),
    "nandan@gmail.com": Persona("nandan@gmail.com", "romance", "comedy-slice-of-life", ("hinglish", "hi"), 0.55, (3, 7), 0.28, 0.25),
    "rahul@gmail.com": Persona("rahul@gmail.com", "sci-fi", "mythology-fantasy", ("en", "hinglish"), 0.48, (3, 8), 0.11, 0.32),
}

SEARCH_TEMPLATES = {
    "hi": ["{g} हिंदी कहानी", "बेस्ट {g} स्टोरी", "नई {g} सीरीज"],
    "hinglish": ["best {g} hinglish story", "new {g} series", "{g} audio series binge"],
    "en": ["best {g} audio series", "new {g} stories", "{g} full series english"],
}


class ListeningSimulator:
    def __init__(self, catalog: list[ContentItem], *, seed: int = SEED, days: int = 60) -> None:
        self._rng = random.Random(seed)
        self._catalog = catalog
        self._days = days
        self._by_segment: dict[tuple[str, str], list[ContentItem]] = {}
        for item in catalog:
            self._by_segment.setdefault((item.primary_genre, item.language), []).append(item)

    # --- selection ----------------------------------------------------------

    def pick_series(self, persona: Persona, count: int) -> list[ContentItem]:
        weights = []
        for item in self._catalog:
            weight = 1.0
            if item.primary_genre == persona.primary_genre:
                weight *= 8.0
            elif item.primary_genre == persona.secondary_genre:
                weight *= 3.0
            else:
                weight *= persona.explores
            weight *= 4.0 if item.language in persona.languages else 0.3
            # Popular titles are likelier to be discovered at all.
            weight *= 1.0 + min(2.0, (item.popularity.get("plays", 0) or 0) / 8_000_000)
            weights.append(weight)

        chosen: list[ContentItem] = []
        pool, pool_weights = list(self._catalog), list(weights)
        for _ in range(min(count, len(pool))):
            pick = self._rng.choices(pool, weights=pool_weights, k=1)[0]
            index = pool.index(pick)
            pool.pop(index)
            pool_weights.pop(index)
            chosen.append(pick)
        return chosen

    # --- one listener's journey through one series --------------------------

    def journey(
        self, user_id: str, persona: Persona, item: ContentItem, start_day: float
    ) -> list[ActivityEvent]:
        events: list[ActivityEvent] = []
        episodes = item.chapters or []
        if not episodes:
            return events

        clock = utcnow() - timedelta(days=start_day)

        def emit(
            event_type: EventType,
            position: int,
            episode: int | None,
            session: str,
            session_seconds: int,
            *,
            query: str | None = None,
            result_count: int | None = None,
        ) -> None:
            events.append(
                ActivityEvent(
                    event_id=f"evt_{uuid4().hex[:16]}",
                    user_id=user_id,
                    content_id=None if event_type is EventType.SEARCH else item.content_id,
                    session_id=session,
                    event_type=event_type,
                    position_seconds=min(position, item.duration_seconds),
                    chapter_index=episode,
                    session_seconds=session_seconds,
                    query=query,
                    result_count=result_count,
                    device=self._rng.choice(["android", "android", "ios", "web"]),
                    is_synthetic=True,
                    occurred_at=clock,
                )
            )

        # A new series is usually found by searching first.
        if self._rng.random() < 0.55:
            language = item.language if item.language in SEARCH_TEMPLATES else "en"
            query = self._rng.choice(SEARCH_TEMPLATES[language]).format(
                g=item.primary_genre.replace("-", " ")
            )
            hits = len(self._by_segment.get((item.primary_genre, item.language), []))
            emit(EventType.SEARCH, 0, None, f"sess_{uuid4().hex[:8]}", 0, query=query, result_count=hits)
            clock += timedelta(minutes=self._rng.randint(1, 8))

        # Where this listener stops, decided up front so the whole journey is coherent.
        enjoys = persona.patience * (
            1.0 if item.primary_genre == persona.primary_genre
            else 0.7 if item.primary_genre == persona.secondary_genre
            else 0.4
        )
        if item.language not in persona.languages:
            enjoys *= 0.5

        total = len(episodes)
        paywall = int(total * 0.30) if item.popularity.get("is_premium") else None

        if paywall and self._rng.random() < 0.45:
            # Churned at the paywall — the cliff a creator most needs to see.
            last_episode, finished = paywall, False
        elif self._rng.random() < enjoys:
            last_episode, finished = total, True
        else:
            last_episode, finished = max(1, int(total * self._rng.uniform(0.15, 0.8))), False

        # Episodes people re-listen to cluster rather than scatter.
        replay_favourites = set(
            self._rng.sample(range(last_episode), k=min(3, max(1, int(last_episode * 0.06))))
        )

        episode = 0
        while episode < last_episode:
            session = f"sess_{user_id}_{item.content_id}_{uuid4().hex[:6]}"
            session_start = clock
            burst = min(self._rng.randint(*persona.binge), last_episode - episode)

            for step in range(burst):
                chapter = episodes[episode]
                elapsed = int((clock - session_start).total_seconds())
                if step == 0:
                    emit(
                        EventType.RESUME if episode else EventType.PLAY,
                        chapter.start_seconds,
                        episode,
                        session,
                        elapsed,
                    )

                if episode in replay_favourites:
                    emit(
                        EventType.REPLAY,
                        chapter.start_seconds + chapter.duration_seconds // 3,
                        episode,
                        session,
                        elapsed,
                    )
                if self._rng.random() < 0.12:
                    emit(EventType.SKIP, chapter.end_seconds, episode, session, elapsed)
                if self._rng.random() < 0.10:
                    emit(EventType.PAUSE, chapter.start_seconds + chapter.duration_seconds // 2,
                         episode, session, elapsed)
                if self._rng.random() < 0.08 and episode:
                    emit(EventType.CHAPTER_JUMP, chapter.start_seconds, episode, session, elapsed)

                clock += timedelta(seconds=chapter.duration_seconds + self._rng.randint(5, 90))
                episode += 1

            # Gap between sittings: usually a day or two, sometimes a long lapse.
            gap_hours = self._rng.choice([6, 18, 22, 26, 30, 48, 72, 96, 24 * 7])
            clock += timedelta(hours=gap_hours * self._rng.uniform(0.7, 1.3))

        last = episodes[min(last_episode, total) - 1]
        final_session = f"sess_{user_id}_{item.content_id}_end"
        if finished:
            emit(EventType.COMPLETE, item.duration_seconds, total - 1, final_session, 0)
            if self._rng.random() < persona.replay_rate + 0.15:
                clock += timedelta(days=self._rng.uniform(3, 21))
                emit(EventType.REVISIT, 0, 0, f"sess_{uuid4().hex[:8]}", 0)
        else:
            emit(EventType.DROP_OFF, last.end_seconds, last_episode - 1, final_session, 0)

        return events

    def run(self, accounts: list[tuple[str, str]]) -> dict[str, list[ActivityEvent]]:
        result: dict[str, list[ActivityEvent]] = {}
        for user_id, email in accounts:
            persona = PERSONAS.get(email)
            if persona is None:
                logger.info("no persona for %s, skipping", email)
                continue
            events: list[ActivityEvent] = []
            series = self.pick_series(persona, self._rng.randint(5, 8))
            for index, item in enumerate(series):
                start_day = self._days * (1 - index / max(len(series), 1)) * self._rng.uniform(0.7, 1.0)
                events.extend(self.journey(user_id, persona, item, start_day))
            events.sort(key=lambda event: event.occurred_at)
            result[user_id] = events
        return result


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()
    gateway = MongoGateway(settings)
    if not await gateway.connect():
        logger.error("Cannot connect to MongoDB. Set DB_URL in server/.env.")
        return 1

    container = build_container(settings, gateway)
    try:
        accounts = await container.accounts_repo.list_accounts()
        if not accounts:
            logger.error("No accounts. Run scripts/onboard_users.py first.")
            return 1
        catalog = await container.content_repo.iter_all(with_transcript=False)
        if not catalog:
            logger.error("Catalog is empty. Run scripts/seed.py first.")
            return 1

        simulator = ListeningSimulator(catalog, seed=args.seed, days=args.days)
        generated = simulator.run([(a.user_id, a.email) for a in accounts])
        by_id = {item.content_id: item for item in catalog}

        logger.info("Plan (%d days of history, seed=%d):", args.days, args.seed)
        total = 0
        for account in accounts:
            events = generated.get(account.user_id, [])
            total += len(events)
            series = {e.content_id for e in events if e.content_id}
            completes = sum(e.event_type is EventType.COMPLETE for e in events)
            drops = sum(e.event_type is EventType.DROP_OFF for e in events)
            genres = {by_id[c].primary_genre for c in series if c in by_id}
            logger.info(
                "  %-22s %4d events | %d series | %d completed | %d dropped | %s",
                account.email, len(events), len(series), completes, drops, ",".join(sorted(genres)),
            )
        logger.info("  %-22s %4d events total", "", total)

        if not args.apply:
            logger.info("")
            logger.info("Dry run. Re-run with --apply to write these events.")
            return 0

        if args.clear:
            removed = await container.activity_repo.collection.delete_many({"is_synthetic": True})
            await container.users_repo.collection.delete_many({"user_id": {"$regex": "^listener_"}})
            logger.info("Cleared %d previously simulated events.", removed.deleted_count)

        for user_id, events in generated.items():
            for start in range(0, len(events), 1000):
                await container.activity_repo.insert_many(events[start : start + 1000])
        logger.info("Wrote %d simulated events across %d accounts.", total, len(generated))

        if args.cohort:
            # Four deep histories cannot produce a demand signal. Genre demand is a
            # statement about a population, and collaborative signals need many
            # listeners rather than many events from a few. This adds a background
            # audience over the same real catalog, calibrated to each story's real
            # plays, likes and rating.
            from app.services.catalog_simulation import RealCatalogSimulator

            logger.info("Adding a %d-listener cohort over the real catalog...", args.cohort)
            cohort = RealCatalogSimulator(seed=args.seed, user_count=args.cohort).run(catalog)
            for start in range(0, len(cohort.events), 2000):
                await container.activity_repo.insert_many(cohort.events[start : start + 2000])
            logger.info(
                "Wrote %d cohort events (%d listeners, completion %.0f%%).",
                len(cohort.events),
                cohort.notes["listeners"],
                cohort.notes["completion_rate"] * 100,
            )

        real = await container.activity_repo.count({"is_synthetic": False})
        synthetic = await container.activity_repo.count({"is_synthetic": True})
        logger.info("")
        logger.info("Event log now: %d real, %d simulated.", real, synthetic)
        logger.info("Provenance will report 'mixed' — these are NOT real listens.")
        logger.info("Next: POST /pipeline/run (or scripts.seed) to rebuild features.")
        logger.info("Undo: python -m scripts.clean_data --apply")
        return 0
    finally:
        await gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate realistic listening history for the accounts.")
    parser.add_argument("--apply", action="store_true", help="Write the events.")
    parser.add_argument("--clear", action="store_true", help="Remove previously simulated events first.")
    parser.add_argument("--days", type=int, default=60, help="How far back the history stretches.")
    parser.add_argument(
        "--cohort",
        type=int,
        default=0,
        help="Also add N background listeners over the real catalog. Genre demand is a "
        "statement about a population; four accounts cannot make one.",
    )
    parser.add_argument("--seed", type=int, default=SEED, help="RNG seed; the run is reproducible.")
    raise SystemExit(asyncio.run(main(parser.parse_args())))

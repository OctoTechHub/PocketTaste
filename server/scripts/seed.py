"""Seed MongoDB with a synthetic-but-realistic world: a Pocket-FM-style catalog
(with embeddings) and persona-driven listener behavior.

Run from the server/ directory:
    python -m scripts.seed        (recommended)
    python scripts/seed.py

The behavior is generated from latent personas so the recommender has genuine
signal — users in the same persona finish overlapping series (creating
collaborative co-occurrence) and drop mismatched ones (creating negative signal).
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

# Make the server root importable regardless of how the script is launched.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.data.repositories import (  # noqa: E402
    event_repository,
    series_repository,
    user_repository,
)
from app.domain.models import BehaviorEvent, Series, User  # noqa: E402
from app.services.ai.embeddings import embed_texts, series_document  # noqa: E402
from scripts.catalog_data import RAW_CATALOG  # noqa: E402

RNG = random.Random(42)
NOW_MS = int(time.time() * 1000)
DAY_MS = 24 * 60 * 60 * 1000

# Each persona is a latent taste archetype. (name, languages, genres, tones)
PERSONAS = [
    ("Hindi Thriller Binger", ["Hindi"], ["thriller", "crime"], ["dark", "gritty", "suspenseful"]),
    ("Hindi Romance Devotee", ["Hindi"], ["romance", "drama"], ["romantic", "emotional", "wholesome"]),
    ("English Sci-Fi Explorer", ["English"], ["scifi", "thriller"], ["suspenseful", "gritty"]),
    ("Mythology & Fantasy Seeker", ["Hindi", "Marathi"], ["mythology", "fantasy"], ["inspirational", "suspenseful"]),
    ("Horror Night-Owl", ["Hindi", "Bengali"], ["horror", "thriller"], ["dark", "suspenseful"]),
    ("Feel-Good Comedy Fan", ["English", "Telugu"], ["comedy", "romance", "slice-of-life"], ["lighthearted", "wholesome"]),
    ("Regional Drama Lover", ["Tamil", "Telugu", "Bengali"], ["drama", "romance"], ["emotional", "romantic"]),
]

# Flagship demo users (first of a persona) get memorable names for the UI.
FLAGSHIP_NAMES = ["Aarohi", "Meera", "Rehan", "Kabir", "Nisha", "Sam", "Anjali"]
FILLER_NAMES = [
    "Rohan", "Priya", "Arjun", "Sneha", "Vikram", "Diya", "Karan", "Isha",
    "Aditya", "Riya", "Manish", "Pooja", "Farhan", "Tara", "Dev", "Zoya",
    "Naveen", "Kavya", "Imran", "Ananya", "Yash", "Simran", "Rahul", "Neha",
]


def build_series() -> list[Series]:
    series_list: list[Series] = []
    for row in RAW_CATALOG:
        (
            sid, title, language, genres, tone, pacing, ep_count, avg_min,
            is_original, is_new, popularity, coin_price, synopsis, tags,
        ) = row
        series_list.append(
            Series(
                id=sid,
                title=title,
                synopsis=synopsis,
                genres=genres,
                language=language,
                tone=tone,
                pacing=pacing,
                episode_count=ep_count,
                avg_episode_minutes=avg_min,
                narrator="PocketFM Studio",
                is_original=is_original,
                is_new=is_new,
                popularity=popularity,
                coin_price_approx=coin_price,
                tags=tags,
                embedding=[],
            )
        )

    # Embed all series in one call (OpenAI batch, or deterministic local hasher).
    docs = [series_document(s) for s in series_list]
    vectors = embed_texts(docs)
    for s, v in zip(series_list, vectors):
        s.embedding = v
    return series_list


def _match_score(series: Series, genres: list[str], tones: list[str], languages: list[str]) -> float:
    score = 0.0
    score += 2.0 * len(set(series.genres) & set(genres))
    score += 1.0 * len(set(series.tone) & set(tones))
    if series.language in languages:
        score += 2.5
    score += 0.5 * series.popularity
    return score


def simulate_user(user: User, persona, catalog: list[Series]) -> list[BehaviorEvent]:
    _, languages, genres, tones = persona
    events: list[BehaviorEvent] = []
    session = 0

    ranked = sorted(catalog, key=lambda s: _match_score(s, genres, tones, languages), reverse=True)
    liked = ranked[: RNG.randint(5, 8)]
    mismatched = [s for s in reversed(ranked) if not (set(s.genres) & set(genres))][: RNG.randint(1, 3)]

    day_cursor = RNG.randint(45, 60)

    def ts_next() -> int:
        nonlocal day_cursor
        day_cursor = max(0, day_cursor - RNG.uniform(0.3, 2.0))
        return int(NOW_MS - day_cursor * DAY_MS)

    # Completed / loved series -> strong positive signal.
    for s in liked:
        session += 1
        finished = RNG.random() < 0.75
        events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="play",
                                    episode_index=1, ts=ts_next(), session_id=f"s{session}"))
        eps = RNG.randint(2, 5) if finished else RNG.randint(1, 2)
        for i in range(eps):
            events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="complete_episode",
                                        episode_index=i + 1, completion_pct=1.0, ts=ts_next(),
                                        session_id=f"s{session}"))
        if finished:
            if RNG.random() < 0.7:
                events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="coin_unlock",
                                            coins=s.coin_price_approx, ts=ts_next(), session_id=f"s{session}"))
            events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="complete_series",
                                        completion_pct=1.0, ts=ts_next(), session_id=f"s{session}"))
        if RNG.random() < 0.5:
            events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="rate",
                                        value=RNG.choice([4, 5, 5]), ts=ts_next(), session_id=f"s{session}"))

    # Mismatched series -> skip / drop (negative signal).
    for s in mismatched:
        session += 1
        events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="play",
                                    episode_index=1, ts=ts_next(), session_id=f"s{session}"))
        events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="skip_intro",
                                    episode_index=1, ts=ts_next(), session_id=f"s{session}"))
        events.append(BehaviorEvent(user_id=user.id, series_id=s.id, type="drop",
                                    completion_pct=RNG.uniform(0.05, 0.3), ts=ts_next(),
                                    session_id=f"s{session}"))

    events.sort(key=lambda e: e.ts)
    return events


def build_users_and_events(catalog: list[Series]) -> tuple[list[User], list[BehaviorEvent]]:
    users: list[User] = []
    all_events: list[BehaviorEvent] = []
    filler = iter(FILLER_NAMES)

    for p_idx, persona in enumerate(PERSONAS):
        persona_name, languages, _, _ = persona
        count = RNG.randint(6, 8)
        for u_idx in range(count):
            if u_idx == 0:
                name = FLAGSHIP_NAMES[p_idx % len(FLAGSHIP_NAMES)]
            else:
                name = next(filler, f"User{p_idx}{u_idx}")
            uid = f"u_{p_idx}_{u_idx}"
            user = User(
                id=uid,
                display_name=f"{name} · {persona_name}",
                languages=languages,
                created_at=NOW_MS - RNG.randint(30, 120) * DAY_MS,
            )
            users.append(user)
            all_events.extend(simulate_user(user, persona, catalog))

    return users, all_events


def main() -> None:
    mode = "OpenAI" if settings.has_openai else "local-fallback (no API key)"
    print(f"[seed] embedding mode: {mode}")

    print("[seed] building catalog + embeddings ...")
    catalog = build_series()
    print(f"[seed] {len(catalog)} series, embedding dim = {len(catalog[0].embedding)}")

    print("[seed] simulating listeners ...")
    users, events = build_users_and_events(catalog)
    print(f"[seed] {len(users)} users, {len(events)} behavior events")

    print("[seed] writing to MongoDB ...")
    series_repository.replace_all(catalog)
    user_repository.replace_all(users)
    event_repository.replace_all(events)

    print("[seed] done. Try: GET /api/feed?user_id=u_0_0")


if __name__ == "__main__":
    main()

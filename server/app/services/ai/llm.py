"""The LLM 'brain' for Stage 3.

Parses a free-text discovery request into a structured intent, and writes a human
"why you'll love this" line. Both have deterministic fallbacks so the features
work with no API key.
"""
from __future__ import annotations

import json
import re

from app.config import settings
from app.domain.models import DiscoveryIntent
from app.domain.vocab import (
    GENRES,
    LANGUAGES,
    PACINGS,
    TONES,
    GENRE_SYNONYMS,
    TONE_SYNONYMS,
    PACING_SYNONYMS,
)
from app.services.ai.embeddings import _client


def parse_discovery_query(query: str) -> DiscoveryIntent:
    client = _client()
    if client is None:
        return heuristic_parse(query)

    try:
        res = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert a listener's natural-language request for an audio series "
                        "into JSON. "
                        f"Allowed genres: {', '.join(GENRES)}. Allowed tones: {', '.join(TONES)}. "
                        f"Allowed languages: {', '.join(LANGUAGES)}. Allowed pacing: {', '.join(PACINGS)}. "
                        "Fields: genres[], exclude_genres[] (things they said NO to, e.g. 'no horror'), "
                        "language, tones[], pacing, max_episode_minutes (number or null), "
                        "keywords[] (salient nouns), mood_text (short phrase capturing the vibe). "
                        "Only use allowed values."
                    ),
                },
                {"role": "user", "content": query},
            ],
        )
        raw = res.choices[0].message.content or "{}"
        data = json.loads(raw)
        return _normalize(data, query)
    except Exception:
        return heuristic_parse(query)


def _in_vocab(values, allowed) -> list:
    return [v for v in (values or []) if v in allowed]


def _normalize(data: dict, query: str) -> DiscoveryIntent:
    language = data.get("language")
    if language not in LANGUAGES:
        language = None
    pacing = data.get("pacing")
    if pacing not in PACINGS:
        pacing = None
    return DiscoveryIntent(
        genres=_in_vocab(data.get("genres"), GENRES),
        exclude_genres=_in_vocab(data.get("exclude_genres"), GENRES),
        language=language,
        tones=_in_vocab(data.get("tones"), TONES),
        pacing=pacing,
        max_episode_minutes=data.get("max_episode_minutes"),
        keywords=[str(k) for k in (data.get("keywords") or [])][:8],
        mood_text=data.get("mood_text") or query,
    )


def heuristic_parse(query: str) -> DiscoveryIntent:
    """Rule-based parser: scans for genre/tone/language/pacing terms + 'no X' negations."""
    q = query.lower()
    genres: set[str] = set()
    exclude: set[str] = set()
    tones: set[str] = set()
    language = None
    pacing = None
    max_minutes = None

    for word, genre in GENRE_SYNONYMS.items():
        if word not in q:
            continue
        negated = re.search(rf"\b(no|not|without|avoid|except)\s+\w*\s*{re.escape(word)}", q)
        (exclude if negated else genres).add(genre)

    for word, tone in TONE_SYNONYMS.items():
        if word in q:
            tones.add(tone)

    for lang in LANGUAGES:
        if lang.lower() in q:
            language = lang

    for word, p in PACING_SYNONYMS.items():
        if word in q:
            pacing = p

    m = re.search(r"(\d{1,3})\s*[- ]?\s*min", q)
    if m:
        max_minutes = float(m.group(1))

    keywords = [w for w in re.sub(r"[^a-z0-9\s]", " ", q).split() if len(w) > 3][:8]

    return DiscoveryIntent(
        genres=list(genres),
        exclude_genres=list(exclude),
        language=language,
        tones=list(tones),
        pacing=pacing,
        max_episode_minutes=max_minutes,
        keywords=keywords,
        mood_text=query,
    )


def write_explanation(context_summary: str, series_title: str, series_facts: str, fallback: str) -> str:
    """One warm second-person sentence. Falls back to the grounded template."""
    client = _client()
    if client is None:
        return fallback
    try:
        res = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0.5,
            max_tokens=60,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You explain, in ONE warm second-person sentence (max 30 words), why a "
                        "listener will love an audio series. Be specific, reference their taste. "
                        "No preamble."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Listener taste: {context_summary}\nSeries: {series_title} — {series_facts}",
                },
            ],
        )
        return (res.choices[0].message.content or fallback).strip() or fallback
    except Exception:
        return fallback

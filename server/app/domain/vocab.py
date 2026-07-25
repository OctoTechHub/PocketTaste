"""Closed vocabularies — shared by the seeder, the NL parser, and validation."""
from __future__ import annotations

GENRES = [
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

TONES = [
    "dark",
    "wholesome",
    "suspenseful",
    "emotional",
    "lighthearted",
    "gritty",
    "romantic",
    "inspirational",
]

LANGUAGES = ["Hindi", "English", "Tamil", "Telugu", "Bengali", "Marathi"]

PACINGS = ["slow-burn", "medium", "fast"]

# Natural-language synonyms -> canonical vocabulary, for the heuristic parser.
GENRE_SYNONYMS = {
    "romance": "romance",
    "love": "romance",
    "romantic": "romance",
    "thriller": "thriller",
    "thrilling": "thriller",
    "suspense": "thriller",
    "horror": "horror",
    "scary": "horror",
    "ghost": "horror",
    "mythology": "mythology",
    "mythological": "mythology",
    "scifi": "scifi",
    "sci-fi": "scifi",
    "space": "scifi",
    "futuristic": "scifi",
    "comedy": "comedy",
    "funny": "comedy",
    "humor": "comedy",
    "humour": "comedy",
    "drama": "drama",
    "crime": "crime",
    "detective": "crime",
    "murder": "crime",
    "mafia": "crime",
    "fantasy": "fantasy",
    "magic": "fantasy",
    "slice-of-life": "slice-of-life",
    "everyday": "slice-of-life",
}

TONE_SYNONYMS = {
    "dark": "dark",
    "wholesome": "wholesome",
    "sweet": "wholesome",
    "feel-good": "wholesome",
    "suspenseful": "suspenseful",
    "tense": "suspenseful",
    "emotional": "emotional",
    "heartbreak": "emotional",
    "sad": "emotional",
    "lighthearted": "lighthearted",
    "light": "lighthearted",
    "gritty": "gritty",
    "raw": "gritty",
    "romantic": "romantic",
    "inspirational": "inspirational",
    "motivational": "inspirational",
}

PACING_SYNONYMS = {
    "slow-burn": "slow-burn",
    "slow burn": "slow-burn",
    "slow": "slow-burn",
    "medium": "medium",
    "fast": "fast",
    "fast-paced": "fast",
    "quick": "fast",
    "bingeable": "fast",
}

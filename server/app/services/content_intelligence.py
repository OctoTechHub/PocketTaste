"""Content intelligence: embeddings, narrative fingerprints, clustering, originality.

Two embeddings are produced per item:

  * ``embedding``     — surface semantics of title/description/tags/transcript.
  * ``arc_embedding`` — the *narrative fingerprint* only.

The second is what catches a re-titled, re-worded upload of the same story. Surface
embeddings drift when a plagiarist paraphrases; the story skeleton does not.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import DuplicateKind, LabelSource, Pacing
from app.domain.models import ContentItem, ContentProfile, NarrativeFingerprint
from app.services.embeddings import EmbeddingService
from app.services.llm import LlmService
from app.services.vectors import content_tokens, cosine

logger = get_logger(__name__)

#: Deterministic backstop when no LLM is available. Keyword -> theme.
THEME_LEXICON: dict[str, tuple[str, ...]] = {
    "fantasy": ("magic", "dungeon", "hunter", "kingdom", "dragon", "portal", "gate", "mana", "guild"),
    "progression": ("level", "system", "rank", "awaken", "skill", "quest", "power", "evolve"),
    "romance": ("love", "marriage", "heart", "wedding", "billionaire", "kiss", "husband", "wife"),
    "thriller": ("murder", "secret", "crime", "detective", "danger", "mystery", "witness", "suspect"),
    "revenge": ("revenge", "betrayal", "vengeance", "payback", "traitor"),
    "family-drama": ("family", "father", "mother", "inheritance", "legacy", "household"),
    "horror": ("ghost", "haunted", "curse", "demon", "nightmare", "spirit", "possessed"),
    "sci-fi": ("space", "future", "robot", "planet", "alien", "quantum", "colony", "ship"),
    "mythology": ("god", "temple", "ancient", "prophecy", "ritual", "divine", "asura"),
    "workplace": ("office", "startup", "company", "boss", "contract", "merger"),
}

NARRATIVE_PATTERNS: dict[str, tuple[str, ...]] = {
    "underdog_progression": ("weakest", "level", "system", "awaken", "rank up", "grew stronger"),
    "revenge_arc": ("revenge", "betrayed", "vengeance", "payback"),
    "forced_proximity_romance": ("contract marriage", "fake marriage", "arranged", "roommate"),
    "whodunnit": ("detective", "suspect", "clue", "murder", "investigate"),
    "haunted_place": ("haunted", "old house", "mansion", "curse", "spirit"),
    "chosen_one": ("prophecy", "destined", "chosen", "bloodline"),
    "survival": ("survive", "apocalypse", "outbreak", "stranded"),
}

#: Volume/season markers stripped before comparing titles. This is what makes
#: "Solo Leveling", "Solo Leveling Season 3" and "Solo Leveling: The End" collide.
_SERIES_MARKERS = re.compile(
    r"\b("
    r"season|series|part|chapter|volume|vol|book|episode|ep|arc"
    r"|final|finale|end|ending|complete|full|new|latest|official|original"
    r"|remastered|reupload|re[- ]?upload|hindi|english|tamil|telugu|bengali|marathi"
    r"|dubbed|version|edition|uncut|extended|test|copy"
    r")\b",
    re.IGNORECASE,
)
_ROMAN_OR_DIGIT = re.compile(r"\b(\d+|[ivxlc]+)\b", re.IGNORECASE)
#: Articles and connectives carry no distinguishing information in a title, and
#: leaving them in means "Solo Leveling: The End" survives as "solo leveling the".
_TITLE_STOPWORDS = frozenset({"the", "a", "an", "of", "and", "or", "to", "in", "is"})

_ARC_PROMPT = """Extract the story skeleton of this audio story as JSON.

Title: {title}
Language: {language}
Genres: {genres}
Description: {description}
Transcript excerpt: {excerpt}

Return exactly this JSON shape:
{{
  "premise": "one sentence, no proper nouns",
  "protagonist_archetype": "2-4 words",
  "central_conflict": "one short phrase",
  "setting": "2-5 words",
  "progression_system": "how the protagonist gains power/status, or 'none'",
  "resolution_shape": "how the arc resolves, or 'open'",
  "tropes": ["3-6 short trope labels"],
  "themes": ["2-5 theme labels"],
  "tone": "one word",
  "narrative_pattern": "snake_case label",
  "target_audience": "short phrase",
  "pacing": "fast | medium | slow"
}}

Describe only what the text supports. Strip character and place names from
`premise` so two versions of the same story with renamed characters still match."""


def normalise_title(title: str) -> str:
    """Strip season/part/language markers so series variants share one key."""
    lowered = re.sub(r"[^\w\s]", " ", title.lower())
    lowered = _SERIES_MARKERS.sub(" ", lowered)
    lowered = _ROMAN_OR_DIGIT.sub(" ", lowered)
    return " ".join(word for word in lowered.split() if word not in _TITLE_STOPWORDS)


class ContentIntelligenceService:
    def __init__(self, settings: Settings, embeddings: EmbeddingService, llm: LlmService) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._llm = llm

    @property
    def embedding_backend(self) -> str:
        return self._embeddings.backend

    # --- labelling ----------------------------------------------------------

    async def analyse(self, item: ContentItem, *, use_llm: bool = True) -> ContentProfile:
        """Produce a full profile for one item (embeddings + labels + fingerprint)."""
        labels, source = await self._label(item, use_llm=use_llm)
        fingerprint = labels["fingerprint"]

        surface_text = item.searchable_text()
        arc_text = fingerprint.as_text() or surface_text[:1200]
        surface_vector, arc_vector = await self._embeddings.embed_many([surface_text, arc_text])

        return ContentProfile(
            content_id=item.content_id,
            embedding=surface_vector,
            arc_embedding=arc_vector,
            embedding_model=self._embeddings.backend,
            embedding_dimensions=len(surface_vector),
            themes=labels["themes"],
            tone=labels["tone"],
            tropes=fingerprint.tropes,
            narrative_pattern=labels["narrative_pattern"],
            target_audience=labels["target_audience"],
            pacing=labels["pacing"],
            fingerprint=fingerprint,
            label_source=source,
            computed_at=utcnow(),
        )

    async def _label(self, item: ContentItem, *, use_llm: bool) -> tuple[dict, LabelSource]:
        if use_llm and self._llm.available:
            prompt = _ARC_PROMPT.format(
                title=item.title,
                language=item.language,
                genres=", ".join(item.genres) or "unspecified",
                description=item.description[:800],
                excerpt=item.transcript[:2500],
            )
            result = await self._llm.complete_json(prompt, language=item.language, max_tokens=700)
            if result.ok and result.data:
                return self._coerce_labels(result.data, item), LabelSource.LLM
        return self._heuristic_labels(item), LabelSource.HEURISTIC

    @staticmethod
    def _coerce_labels(data: dict, item: ContentItem) -> dict:
        def as_list(value, limit: int) -> list[str]:
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list):
                return []
            return [str(entry).strip().lower()[:40] for entry in value if str(entry).strip()][:limit]

        pacing_raw = str(data.get("pacing", "medium")).strip().lower()
        pacing = Pacing(pacing_raw) if pacing_raw in {p.value for p in Pacing} else Pacing.MEDIUM

        fingerprint = NarrativeFingerprint(
            premise=str(data.get("premise", ""))[:400],
            protagonist_archetype=str(data.get("protagonist_archetype", ""))[:80],
            central_conflict=str(data.get("central_conflict", ""))[:160],
            setting=str(data.get("setting", ""))[:80],
            progression_system=str(data.get("progression_system", ""))[:120],
            resolution_shape=str(data.get("resolution_shape", ""))[:120],
            tropes=as_list(data.get("tropes"), 8),
        )
        return {
            "fingerprint": fingerprint,
            "themes": as_list(data.get("themes"), 6) or item.genres or ["general"],
            "tone": str(data.get("tone", "neutral")).strip().lower()[:30] or "neutral",
            "narrative_pattern": re.sub(
                r"[^a-z0-9_]+", "_", str(data.get("narrative_pattern", "unclassified")).strip().lower()
            )[:40]
            or "unclassified",
            "target_audience": str(data.get("target_audience", "general")).strip().lower()[:60],
            "pacing": pacing,
        }

    @staticmethod
    def _heuristic_labels(item: ContentItem) -> dict:
        """Deterministic keyword labelling. Always disclosed as `heuristic`."""
        corpus = " ".join(
            [item.title, item.description, " ".join(item.tags), item.transcript[:4000]]
        ).lower()
        themes = [theme for theme, words in THEME_LEXICON.items() if any(word in corpus for word in words)]
        pattern_hits = {
            pattern: sum(corpus.count(word) for word in words)
            for pattern, words in NARRATIVE_PATTERNS.items()
        }
        best_pattern = max(pattern_hits, key=lambda key: pattern_hits[key]) if pattern_hits else "unclassified"
        if pattern_hits.get(best_pattern, 0) == 0:
            best_pattern = "unclassified"

        frequent = [word for word, _ in Counter(content_tokens(corpus)).most_common(6)]
        fingerprint = NarrativeFingerprint(
            premise=item.description[:280],
            protagonist_archetype=item.tags[0] if item.tags else "protagonist",
            central_conflict=best_pattern.replace("_", " "),
            setting=item.primary_genre,
            progression_system="system" if "system" in corpus else "none",
            resolution_shape="open",
            tropes=sorted(set(themes + frequent))[:6],
        )
        return {
            "fingerprint": fingerprint,
            "themes": themes or item.genres or ["general"],
            "tone": "dark" if any(word in corpus for word in ("curse", "murder", "revenge")) else "neutral",
            "narrative_pattern": best_pattern,
            "target_audience": "general",
            "pacing": Pacing.MEDIUM,
        }

    # --- clustering & originality ------------------------------------------

    def cluster(self, profiles: list[ContentProfile]) -> dict[str, ContentProfile]:
        """Greedy single-pass agglomerative clustering on the arc embedding.

        O(n * k) where k is the number of clusters — cheap, deterministic when the
        input order is stable, and good enough to surface duplicate families.
        Swap for HDBSCAN in the Databricks batch tier when the catalog grows.
        """
        threshold = self._settings.cluster_threshold
        ordered = sorted(profiles, key=lambda profile: profile.content_id)
        centroids: list[tuple[str, list[float]]] = []
        assignments: dict[str, str] = {}

        for profile in ordered:
            vector = profile.arc_embedding or profile.embedding
            if not vector:
                assignments[profile.content_id] = f"cluster_{profile.content_id}"
                continue
            best_id, best_score = None, 0.0
            for cluster_id, centroid in centroids:
                score = cosine(vector, centroid)
                if score > best_score:
                    best_id, best_score = cluster_id, score
            if best_id is not None and best_score >= threshold:
                assignments[profile.content_id] = best_id
            else:
                cluster_id = f"cluster_{len(centroids):04d}"
                centroids.append((cluster_id, vector))
                assignments[profile.content_id] = cluster_id

        sizes = Counter(assignments.values())
        for profile in ordered:
            profile.cluster_id = assignments[profile.content_id]
            profile.cluster_size = sizes[profile.cluster_id]
        return {profile.content_id: profile for profile in ordered}

    @staticmethod
    def apply_originality(
        profile: ContentProfile, neighbours: list[tuple[str, str, float, DuplicateKind]]
    ) -> ContentProfile:
        """Set originality/duplicate fields from the item's nearest catalog neighbours."""
        top = neighbours[0][2] if neighbours else 0.0
        profile.duplicate_risk = round(top, 4)
        profile.originality_score = round(1.0 - top, 4)
        profile.duplicate_kind = neighbours[0][3] if neighbours else DuplicateKind.NONE
        profile.nearest_neighbours = [
            {"content_id": cid, "title": title, "score": round(score, 4), "kind": kind.value}
            for cid, title, score, kind in neighbours[:5]
        ]
        return profile


def fingerprint_from_json(raw: str) -> NarrativeFingerprint:
    """Used by the copilot to reuse the same fingerprint shape for unpublished drafts."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return NarrativeFingerprint()
    return NarrativeFingerprint.model_validate({k: v for k, v in data.items() if k in NarrativeFingerprint.model_fields})

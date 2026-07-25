"""Demand discovery — the creator-facing half of the system.

The unit of analysis is a market cell: (genre, language). For each cell we measure
what listeners *do* and what the catalog *offers*, then report the gap.

    opportunity_score = (demand_share - supply_share) * (1 - duplicate_density)

Subtracting shares rather than dividing them keeps the number bounded in [-1, 1]
and readable: +0.12 means "this cell absorbs 12 percentage points more attention
than its share of the catalog". The saturation factor discounts cells that are
already full of near-duplicate re-uploads — demand there is being met badly, not
left unserved.

Nothing in this module invents a number. Every row carries its raw counts, its
sample size, a confidence label and a provenance tag.
"""

from __future__ import annotations

import re
from collections import defaultdict
from uuid import uuid4

from app.core.clock import utcnow
from app.core.config import Settings
from app.domain.enums import (
    EVENT_WEIGHTS,
    Confidence,
    DuplicateKind,
    EventType,
    LabelSource,
    Provenance,
)
from app.domain.models import (
    ActivityEvent,
    ContentFeatures,
    ContentItem,
    ContentProfile,
    CreatorBrief,
    DemandReport,
    DemandSegment,
    PatternSaturation,
)
from app.domain.provenance import notice as provenance_notice
from app.domain.provenance import resolve_provenance
from app.services.content_intelligence import THEME_LEXICON
from app.services.llm import LlmService
from app.services.vectors import content_tokens

#: Devanagari / Tamil / Telugu / Bengali blocks — used only to attribute a
#: zero-result search to a language cell. Documented as a heuristic in the output.
_SCRIPT_RANGES = {
    "hi": re.compile(r"[ऀ-ॿ]"),
    "ta": re.compile(r"[஀-௿]"),
    "te": re.compile(r"[ఀ-౿]"),
    "bn": re.compile(r"[ঀ-৿]"),
}

_BRIEF_PROMPT = """You are writing content briefs for audio-story creators.

These segments were measured from the platform's own event log. Every number below
is computed, not estimated:

{segments}

Over-supplied narrative patterns (high catalog share, weak retention):
{patterns}

Data provenance: {provenance}
Total events analysed: {events}
Total unique listeners: {listeners}

For each of the {count} segments above, write one brief as JSON:
{{"briefs": [
  {{"headline": "<8-14 words, concrete>",
    "segment": "<exact segment string>",
    "rationale": "<2-3 sentences citing ONLY the numbers given>",
    "avoid_patterns": ["<pattern names from the over-supplied list, or empty>"]}}
]}}

Rules: cite only the supplied numbers. Do not estimate revenue, audience size or
growth. If a segment's sample size is small, say the signal is provisional."""


def _confidence(sample_size: int, threshold: int) -> Confidence:
    if sample_size >= threshold:
        return Confidence.HIGH
    if sample_size >= max(2, threshold // 3):
        return Confidence.MEDIUM
    return Confidence.LOW


#: Language named in the query itself, e.g. "hindi crime thriller".
_LANGUAGE_WORDS = {
    "hindi": "hi", "hi": "hi", "tamil": "ta", "telugu": "te",
    "bengali": "bn", "bangla": "bn", "marathi": "mr", "english": "en",
    # Hinglish is a first-class segment on an Indian audio platform, not a variant
    # of Hindi. Folding it into "hi" would erase a distinct market.
    "hinglish": "hinglish",
}


def _detect_language(query: str) -> str | None:
    """Script first, then an explicitly named language. Returns None when neither applies."""
    for language, pattern in _SCRIPT_RANGES.items():
        if pattern.search(query):
            return language
    for token in content_tokens(query):
        if token in _LANGUAGE_WORDS:
            return _LANGUAGE_WORDS[token]
    return None


#: Non-Latin search terms mapped to genres. The English lexicon cannot match a
#: Devanagari query, and silently dropping those searches would hide exactly the
#: unmet demand we are looking for in Indic-language cells.
#: Keys cover both the slugified genres used by the real catalog and the shorter
#: names used by the synthetic one. Unknown keys are ignored, so listing both is safe.
_NATIVE_GENRE_TERMS: dict[str, tuple[str, ...]] = {
    "thriller": ("थ्रिलर", "रोमांचक"),
    "suspense": ("सस्पेंस", "रहस्य"),
    "crime-detective": ("क्राइम", "जासूस", "डिटेक्टिव", "मर्डर", "हत्या", "जांच", "पुलिस", "अपराध"),
    "revenge-drama": ("बदला", "प्रतिशोध", "इंतकाम"),
    "romance": ("रोमांस", "प्रेम", "प्यार", "शादी", "मोहब्बत", "इश्क"),
    "horror": ("हॉरर", "भूत", "डरावनी", "प्रेत", "श्राप", "चुड़ैल", "आत्मा"),
    "supernatural": ("अलौकिक", "परालौकिक", "तंत्र"),
    "mythology-fantasy": ("पौराणिक", "महाभारत", "रामायण", "देवता", "असुर", "जादू", "तिलिस्म"),
    "sci-fi": ("विज्ञान", "अंतरिक्ष", "भविष्य", "रोबोट"),
    "comedy-slice-of-life": ("कॉमेडी", "हास्य", "मजेदार"),
    # Short-form genre names used by the synthetic catalog.
    "fantasy": ("फैंटेसी", "जादू", "राक्षस", "योद्धा", "तिलिस्म"),
    "mythology": ("पौराणिक", "महाभारत", "रामायण", "देवता", "असुर"),
}

#: Slug fragments too generic to identify a genre on their own.
_GENRE_PART_STOPWORDS = frozenset({"of", "the", "and", "life", "slice", "drama", "fiction", "story"})


def _match_genres(query: str, known_genres: set[str]) -> set[str]:
    """Attribute a free-text search to genres by name, slug fragment, lexicon keyword
    or native-script term.

    Slug fragments matter because the real catalog's genres are multi-word:
    'crime-detective' is never a single token, so a search for "detective mystery"
    would otherwise be attributed to nothing and silently vanish from the demand
    signal.
    """
    tokens = set(content_tokens(query))
    matched = {genre for genre in known_genres if genre in tokens}

    for genre in known_genres:
        parts = [
            part
            for part in genre.split("-")
            if len(part) >= 3 and part not in _GENRE_PART_STOPWORDS
        ]
        if parts and any(part in tokens for part in parts):
            matched.add(genre)

    for genre, words in THEME_LEXICON.items():
        if genre in known_genres and tokens & set(words):
            matched.add(genre)
    for genre, terms in _NATIVE_GENRE_TERMS.items():
        if genre in known_genres and any(term in query for term in terms):
            matched.add(genre)
    return matched


class DemandService:
    def __init__(self, settings: Settings, llm: LlmService) -> None:
        self._settings = settings
        self._llm = llm

    async def build_report(
        self,
        catalog: list[ContentItem],
        events: list[ActivityEvent],
        features: dict[str, ContentFeatures],
        profiles: dict[str, ContentProfile],
        *,
        top_segments: int = 6,
        use_llm: bool = True,
    ) -> DemandReport:
        segments, unattributed = self._segments(catalog, events, features, profiles)
        patterns = self._pattern_saturation(catalog, features, profiles)
        provenance = self._provenance(catalog, events)

        headline_segments = [
            segment for segment in segments if segment.opportunity_score > 0
        ][:top_segments] or segments[:top_segments]

        briefs = await self._briefs(
            headline_segments, patterns, provenance, len(events), catalog, use_llm=use_llm
        )

        return DemandReport(
            segments=segments,
            saturated_patterns=patterns,
            briefs=briefs,
            catalog_items=len(catalog),
            events_analysed=len(events),
            unique_listeners=len({event.user_id for event in events}),
            unattributed_unmet_searches=unattributed,
            provenance=provenance,
            data_notice=self._notice(provenance),
            generated_at=utcnow(),
        )

    # --- segments -----------------------------------------------------------

    def _segments(
        self,
        catalog: list[ContentItem],
        events: list[ActivityEvent],
        features: dict[str, ContentFeatures],
        profiles: dict[str, ContentProfile],
    ) -> tuple[list[DemandSegment], int]:
        by_id = {item.content_id: item for item in catalog}
        known_genres = {genre for item in catalog for genre in (item.genres or ["general"])}

        supply: dict[tuple[str, str], int] = defaultdict(int)
        duplicates: dict[tuple[str, str], int] = defaultdict(int)
        for item in catalog:
            for genre in item.genres or ["general"]:
                key = (genre, item.language)
                supply[key] += 1
                profile = profiles.get(item.content_id)
                if profile and profile.duplicate_kind is not DuplicateKind.NONE:
                    duplicates[key] += 1

        listeners: dict[tuple[str, str], set[str]] = defaultdict(set)
        plays: dict[tuple[str, str], int] = defaultdict(int)
        completes: dict[tuple[str, str], int] = defaultdict(int)
        dropoffs: dict[tuple[str, str], int] = defaultdict(int)
        weighted: dict[tuple[str, str], float] = defaultdict(float)
        unmet: dict[tuple[str, str], int] = defaultdict(int)
        unattributed = 0

        for event in events:
            if event.event_type is EventType.SEARCH:
                # Zero-result searches are the purest unmet-demand signal we have:
                # a listener asked for something the catalog could not serve.
                if event.result_count == 0 and event.query:
                    genres = _match_genres(event.query, known_genres)
                    language = _detect_language(event.query)
                    if not genres or language is None:
                        # Counted and reported, never guessed into a segment.
                        unattributed += 1
                        continue
                    for genre in genres:
                        unmet[(genre, language)] += 1
                continue

            item = by_id.get(event.content_id or "")
            if item is None:
                continue
            weight = EVENT_WEIGHTS.get(event.event_type, 0.0)
            for genre in item.genres or ["general"]:
                key = (genre, item.language)
                listeners[key].add(event.user_id)
                weighted[key] += max(0.0, weight)
                if event.event_type is EventType.PLAY:
                    plays[key] += 1
                elif event.event_type is EventType.COMPLETE:
                    completes[key] += 1
                elif event.event_type is EventType.DROP_OFF:
                    dropoffs[key] += 1

        total_supply = sum(supply.values()) or 1
        keys = set(supply) | set(listeners) | set(unmet)
        # Unmet searches are demand with no catalog behind them — count them in, at a
        # heavier weight than a single play, since a failed search is an explicit ask.
        search_weight = self._settings.unmet_search_weight
        total_demand = sum(weighted.values()) + search_weight * sum(unmet.values()) or 1.0

        rows: list[DemandSegment] = []
        for genre, language in keys:
            key = (genre, language)
            catalog_items = supply[key]
            supply_share = catalog_items / total_supply
            demand_share = (weighted[key] + search_weight * unmet[key]) / total_demand
            duplicate_density = duplicates[key] / catalog_items if catalog_items else 0.0
            segment_plays = plays[key]

            completion_rate = completes[key] / segment_plays if segment_plays else 0.0
            drop_off_rate = dropoffs[key] / segment_plays if segment_plays else 0.0
            opportunity = (demand_share - supply_share) * (1.0 - duplicate_density)
            # High attention + poor retention = the audience is there but the
            # existing execution is losing them. That is a different opportunity.
            execution_gap = demand_share * drop_off_rate

            sample_size = len(listeners[key])
            rows.append(
                DemandSegment(
                    segment=f"{genre}/{language}",
                    genre=genre,
                    language=language,
                    catalog_items=catalog_items,
                    supply_share=round(supply_share, 4),
                    unique_listeners=sample_size,
                    plays=segment_plays,
                    completions=completes[key],
                    weighted_demand=round(weighted[key], 3),
                    demand_share=round(demand_share, 4),
                    unmet_search_count=unmet[key],
                    completion_rate=round(completion_rate, 4),
                    drop_off_rate=round(drop_off_rate, 4),
                    duplicate_density=round(duplicate_density, 4),
                    opportunity_score=round(opportunity, 4),
                    execution_gap=round(execution_gap, 4),
                    sample_size=sample_size,
                    confidence=_confidence(sample_size, self._settings.min_confident_sample_size),
                    evidence={
                        "catalog_items": catalog_items,
                        "unique_listeners": sample_size,
                        "plays": segment_plays,
                        "completions": completes[key],
                        "drop_offs": dropoffs[key],
                        "zero_result_searches": unmet[key],
                        "duplicate_items": duplicates[key],
                    },
                )
            )
        rows.sort(key=lambda row: row.opportunity_score, reverse=True)
        return rows, unattributed

    # --- pattern saturation -------------------------------------------------

    def _pattern_saturation(
        self,
        catalog: list[ContentItem],
        features: dict[str, ContentFeatures],
        profiles: dict[str, ContentProfile],
    ) -> list[PatternSaturation]:
        """Narrative patterns that flood the catalog without earning retention.

        Only patterns with actual listeners are judged. A pattern nobody has played
        has a completion rate of 0.0, and dividing by that would report "over-supplied,
        0% completion" for every story the audience simply has not reached yet —
        turning missing data into a damning verdict. Silence is not a bad review.
        """
        buckets: dict[str, list[str]] = defaultdict(list)
        for item in catalog:
            profile = profiles.get(item.content_id)
            pattern = profile.narrative_pattern if profile else "unclassified"
            buckets[pattern].append(item.content_id)

        total = len(catalog) or 1
        rows: list[PatternSaturation] = []
        for pattern, content_ids in buckets.items():
            # Measured means "someone actually listened", not merely "a row exists".
            observed = [
                features[cid]
                for cid in content_ids
                if cid in features and features[cid].unique_listeners > 0
            ]
            if not observed:
                continue
            listeners = sum(row.unique_listeners for row in observed)
            if listeners < self._settings.min_pattern_listeners:
                continue

            completion = sum(row.completion_rate for row in observed) / len(observed)
            drop_off = sum(row.drop_off_rate for row in observed) / len(observed)
            share = len(content_ids) / total
            health = max(completion, 0.01)
            saturation = share / health
            rows.append(
                PatternSaturation(
                    narrative_pattern=pattern,
                    catalog_items=len(content_ids),
                    share_of_catalog=round(share, 4),
                    avg_completion_rate=round(completion, 4),
                    avg_drop_off_rate=round(drop_off, 4),
                    saturation_index=round(saturation, 4),
                    measured_items=len(observed),
                    listeners=listeners,
                    verdict=(
                        "over-supplied relative to retention"
                        if saturation > 1.0
                        else "healthy supply/retention balance"
                    ),
                )
            )
        rows.sort(key=lambda row: row.saturation_index, reverse=True)
        return rows

    # --- briefs -------------------------------------------------------------

    async def _briefs(
        self,
        segments: list[DemandSegment],
        patterns: list[PatternSaturation],
        provenance: Provenance,
        event_count: int,
        catalog: list[ContentItem],
        *,
        use_llm: bool,
    ) -> list[CreatorBrief]:
        if not segments:
            return []
        deterministic = [self._deterministic_brief(segment, patterns) for segment in segments]
        if not use_llm or not self._llm.available:
            return deterministic

        rendered = "\n".join(
            f"- {segment.segment}: catalog_items={segment.catalog_items}, "
            f"supply_share={segment.supply_share}, demand_share={segment.demand_share}, "
            f"opportunity_score={segment.opportunity_score}, listeners={segment.unique_listeners}, "
            f"plays={segment.plays}, completion_rate={segment.completion_rate}, "
            f"drop_off_rate={segment.drop_off_rate}, zero_result_searches={segment.unmet_search_count}, "
            f"duplicate_density={segment.duplicate_density}, confidence={segment.confidence.value}"
            for segment in segments
        )
        pattern_text = "\n".join(
            f"- {row.narrative_pattern}: share={row.share_of_catalog}, "
            f"avg_completion={row.avg_completion_rate}, saturation_index={row.saturation_index}"
            for row in patterns[:5]
        ) or "- none measured"

        result = await self._llm.complete_json(
            _BRIEF_PROMPT.format(
                segments=rendered,
                patterns=pattern_text,
                provenance=provenance.value,
                events=event_count,
                listeners=sum(segment.unique_listeners for segment in segments),
                count=len(segments),
            ),
            max_tokens=1200,
        )
        entries = result.data.get("briefs") if result.ok else None
        if not isinstance(entries, list) or not entries:
            return deterministic

        by_segment = {segment.segment: segment for segment in segments}
        briefs: list[CreatorBrief] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            segment = by_segment.get(str(entry.get("segment", "")))
            if segment is None:
                continue
            avoid = entry.get("avoid_patterns") or []
            briefs.append(
                CreatorBrief(
                    brief_id=f"brief_{uuid4().hex[:10]}",
                    headline=str(entry.get("headline", ""))[:160],
                    segment=segment.segment,
                    language=segment.language,
                    genre=segment.genre,
                    rationale=str(entry.get("rationale", ""))[:800],
                    supporting_metrics=self._metrics(segment),
                    avoid_patterns=[str(item)[:60] for item in avoid if isinstance(item, (str, int))][:5],
                    confidence=segment.confidence,
                    generated_by=LabelSource.LLM,
                )
            )
        return briefs or deterministic

    def _deterministic_brief(
        self, segment: DemandSegment, patterns: list[PatternSaturation]
    ) -> CreatorBrief:
        over_supplied = [row.narrative_pattern for row in patterns if row.saturation_index > 1.0][:3]
        if segment.opportunity_score > 0:
            headline = (
                f"{segment.genre.title()} in {segment.language} absorbs more attention than it supplies"
            )
            rationale = (
                f"This segment holds {segment.supply_share:.1%} of the catalog but "
                f"{segment.demand_share:.1%} of measured demand, an opportunity gap of "
                f"{segment.opportunity_score:+.3f}. {segment.unique_listeners} listeners and "
                f"{segment.plays} plays were observed, with {segment.unmet_search_count} searches "
                f"returning no results."
            )
        else:
            headline = f"{segment.genre.title()} in {segment.language} is adequately supplied"
            rationale = (
                f"Supply share {segment.supply_share:.1%} already meets demand share "
                f"{segment.demand_share:.1%} (gap {segment.opportunity_score:+.3f}). "
                f"Drop-off rate is {segment.drop_off_rate:.1%}; execution gap {segment.execution_gap:.3f}."
            )
        return CreatorBrief(
            brief_id=f"brief_{uuid4().hex[:10]}",
            headline=headline,
            segment=segment.segment,
            language=segment.language,
            genre=segment.genre,
            rationale=rationale,
            supporting_metrics=self._metrics(segment),
            avoid_patterns=over_supplied,
            confidence=segment.confidence,
            generated_by=LabelSource.HEURISTIC,
        )

    @staticmethod
    def _metrics(segment: DemandSegment) -> dict:
        return {
            "catalog_items": segment.catalog_items,
            "supply_share": segment.supply_share,
            "demand_share": segment.demand_share,
            "opportunity_score": segment.opportunity_score,
            "execution_gap": segment.execution_gap,
            "unique_listeners": segment.unique_listeners,
            "plays": segment.plays,
            "completion_rate": segment.completion_rate,
            "drop_off_rate": segment.drop_off_rate,
            "zero_result_searches": segment.unmet_search_count,
            "duplicate_density": segment.duplicate_density,
            "sample_size": segment.sample_size,
            "confidence": segment.confidence.value,
        }

    @staticmethod
    def _provenance(catalog: list[ContentItem], events: list[ActivityEvent]) -> Provenance:
        return resolve_provenance(
            catalog_total=len(catalog),
            catalog_synthetic=sum(item.is_synthetic for item in catalog),
            events_total=len(events),
            events_synthetic=sum(event.is_synthetic for event in events),
        )

    @staticmethod
    def _notice(provenance: Provenance) -> str:
        return provenance_notice(provenance)

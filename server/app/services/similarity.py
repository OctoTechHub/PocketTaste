"""The similarity / plagiarism gate.

Six independent signals are computed against every shortlisted catalog item and
blended into one score. Reporting them separately matters: a reviewer needs to see
*why* something matched, and different signals imply different kinds of copying.

    narrative_arc      story skeleton match      -> survives paraphrasing
    semantic           surface meaning match     -> catches translation/rewording
    lexical_shingle    5-gram overlap            -> catches verbatim copy-paste
    title              season/part-stripped      -> catches "Solo Leveling Season 3"
    description        blurb overlap             -> catches lazy metadata reuse
    chapter_structure  episode layout match      -> catches re-packaged uploads
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import DuplicateKind, RiskLevel
from app.domain.models import (
    Chapter,
    ContentItem,
    ContentProfile,
    SimilarityMatch,
    SimilarityReport,
    SimilaritySignals,
)
from app.services.content_intelligence import (
    ContentIntelligenceService,
    episode_range,
    normalise_title,
    ranges_overlap,
)
from app.services.llm import LlmService
from app.services.vectors import content_tokens, cosine, jaccard, shingles, verbatim_overlap

logger = get_logger(__name__)

_EXACT_SHINGLE_THRESHOLD = 0.55

#: Calibrated against the live catalog, not guessed. Across all 4,950 genuine
#: distinct pairs the narrative-arc score peaks at 0.726 (p50 0.354, p99 0.586). A
#: reworded re-upload of a real story measures 0.85. The bar sits in that gap.
#:
#: This was originally 0.92, which was too strict: it missed exactly the case the
#: gate exists for — same story, new title, every word rewritten.
_NEAR_ARC_THRESHOLD = 0.80
_NEAR_SEMANTIC_THRESHOLD = 0.65

#: A strong skeleton match is a finding on its own. The arc signal is built to
#: survive paraphrasing, so when it fires the combined blend must not be allowed to
#: bury it — a rewritten copy scores ~0 on verbatim overlap, ~0 on title, and often
#: has no chapter markers, and those zeros drag the average under the threshold.
_ARC_ALONE_REVIEW = 0.80
_VARIANT_SEMANTIC_THRESHOLD = 0.72

_EXPLANATION_PROMPT = """A creator is uploading a story. Our screening gate compared it
against the existing catalog and produced these measurements.

Candidate title: {title}
Verdict: {risk}
Top combined similarity: {top_score}
Duplicate classification: {kind}
Closest matches (with per-signal breakdown):
{matches}

Signal meanings:
- narrative_arc: story-skeleton match, survives rewording
- semantic: surface meaning match
- lexical_shingle: verbatim 5-word-sequence overlap
- title: title match after stripping season/part/language markers
- description / chapter_structure: metadata and episode-layout match

Write 2-4 plain sentences for the creator explaining what was detected and what
happens next. Quote only the numbers above. Do not accuse anyone of plagiarism —
this is a screening signal that routes to human review.

Important: if any match has title=1.0, lead with that one. It means the titles are
identical once season/part/language markers are stripped, which is the single most
actionable thing for the creator to know, even when another match scores higher
overall."""


@dataclass(slots=True)
class SimilarityCandidate:
    """A draft being screened. Not yet persisted to the catalog."""

    title: str
    description: str
    transcript: str
    language: str = "en"
    genres: list[str] | None = None
    chapters: list[Chapter] | None = None
    creator_id: str = "anonymous"

    def as_content_item(self) -> ContentItem:
        return ContentItem(
            content_id="__candidate__",
            title=self.title,
            description=self.description,
            transcript=self.transcript or self.description,
            creator_id=self.creator_id,
            language=self.language,
            genres=self.genres or [],
            chapters=self.chapters or [],
        )


def _chapter_shape(chapters: list[Chapter]) -> np.ndarray:
    """Relative chapter-length profile resampled to 10 buckets, so two shows with
    the same episode rhythm match even at different total runtimes."""
    if not chapters:
        return np.zeros(10, dtype=np.float32)
    lengths = np.asarray([max(1, chapter.duration_seconds) for chapter in chapters], dtype=np.float32)
    lengths = lengths / lengths.sum()
    positions = np.linspace(0, len(lengths) - 1, num=10)
    return np.interp(positions, np.arange(len(lengths)), lengths).astype(np.float32)


def _chapter_structure_similarity(left: list[Chapter], right: list[Chapter]) -> float:
    if not left or not right:
        return 0.0
    count_ratio = min(len(left), len(right)) / max(len(left), len(right))
    shape_left, shape_right = _chapter_shape(left), _chapter_shape(right)
    shape_similarity = cosine(shape_left.tolist(), shape_right.tolist())
    return round(0.5 * count_ratio + 0.5 * shape_similarity, 6)


#: A draft needs at least this many content words before verbatim overlap is measurable.
#: Twelve tokens yields eight 5-grams, which is enough for the containment test in
#: `verbatim_overlap` to mean something. This floor used to be 60, chosen with a
#: full-length script in mind -- but the live catalog stores loglines with a median of
#: 98 characters (~16 tokens), so 60 switched the verbatim detector off for nearly
#: every real upload. A byte-identical re-upload of "WhatsApp Se Aayi Maut" under a new
#: title and blurb was scored `clear` at 0.40 because of it.
_MIN_SHINGLE_TOKENS = 12


def applicable_signals(draft: ContentItem) -> set[str]:
    """Which signals can meaningfully be measured for this draft.

    A creator screening a one-paragraph premise has no transcript and no chapter
    markers, so `lexical_shingle` and `chapter_structure` are structurally zero.
    Leaving them in the weighted blend silently penalises the draft for being early
    -- a verbatim copy of an existing premise would score ~0.35 and pass as `clear`.
    Instead we drop the signals that cannot apply and renormalise over the rest.
    """
    signals = {"narrative_arc", "semantic", "title", "description"}
    if len(content_tokens(draft.transcript)) >= _MIN_SHINGLE_TOKENS:
        signals.add("lexical_shingle")
    if draft.chapters:
        signals.add("chapter_structure")
    return signals


class SimilarityService:
    def __init__(
        self,
        settings: Settings,
        intelligence: ContentIntelligenceService,
        llm: LlmService,
    ) -> None:
        self._settings = settings
        self._intelligence = intelligence
        self._llm = llm

    async def screen(
        self,
        candidate: SimilarityCandidate,
        catalog: list[ContentItem],
        profiles: dict[str, ContentProfile],
        *,
        top_k: int = 5,
        exclude_content_id: str | None = None,
        use_llm: bool = True,
        explain: bool = True,
    ) -> SimilarityReport:
        """Screen a draft against the catalog and return a full, auditable report."""
        draft_item = candidate.as_content_item()
        draft_profile = await self._intelligence.analyse(draft_item, use_llm=use_llm)

        matches = self.compare_all(
            draft_item, draft_profile, catalog, profiles, exclude_content_id=exclude_content_id
        )
        matches.sort(key=lambda match: match.combined_score, reverse=True)
        top_matches = matches[:top_k]

        top_score = top_matches[0].combined_score if top_matches else 0.0
        kind = top_matches[0].duplicate_kind if top_matches else DuplicateKind.NONE
        # A title collision can sit outside the top-scoring match, so look across all of
        # them rather than only the leader.
        title_collision = next(
            (match for match in matches if match.signals.title >= 1.0), None
        )
        risk = self._verdict(
            top_score, kind, title_collision, top_matches[0] if top_matches else None
        )
        if title_collision is not None and title_collision not in top_matches:
            # The reviewer must see the colliding title even when it did not win on score.
            top_matches.append(title_collision)

        report = SimilarityReport(
            candidate_title=candidate.title,
            risk=risk,
            originality_score=round(1.0 - top_score, 4),
            top_score=top_score,
            duplicate_kind=kind,
            matches=top_matches,
            weights=self._settings.similarity_weights.as_dict(),
            applied_signals=sorted(applicable_signals(draft_item)),
            thresholds={
                "block": self._settings.similarity_block_threshold,
                "review": self._settings.similarity_review_threshold,
                "exact_shingle": _EXACT_SHINGLE_THRESHOLD,
                "near_duplicate_arc": _NEAR_ARC_THRESHOLD,
                "arc_alone_review": _ARC_ALONE_REVIEW,
                "near_duplicate_semantic": _NEAR_SEMANTIC_THRESHOLD,
                "series_variant_semantic": _VARIANT_SEMANTIC_THRESHOLD,
            },
            candidates_compared=len(matches),
            computed_at=utcnow(),
        )
        report.explanation = await self._explain(report, use_llm=use_llm and explain)
        return report

    # --- signal computation -------------------------------------------------

    def compare_all(
        self,
        draft_item: ContentItem,
        draft_profile: ContentProfile,
        catalog: list[ContentItem],
        profiles: dict[str, ContentProfile],
        *,
        exclude_content_id: str | None = None,
    ) -> list[SimilarityMatch]:
        draft_title_key = normalise_title(draft_item.title)
        draft_title_tokens = set(content_tokens(draft_item.title))
        draft_description_tokens = set(content_tokens(draft_item.description))
        draft_shingles = shingles(draft_item.transcript or draft_item.description)
        applicable = applicable_signals(draft_item)

        matches: list[SimilarityMatch] = []
        for item in catalog:
            if item.content_id == exclude_content_id or item.content_id == draft_item.content_id:
                continue
            profile = profiles.get(item.content_id)
            signals = SimilaritySignals(
                narrative_arc=(
                    cosine(draft_profile.arc_embedding, profile.arc_embedding) if profile else 0.0
                ),
                semantic=cosine(draft_profile.embedding, profile.embedding) if profile else 0.0,
                lexical_shingle=verbatim_overlap(
                    draft_shingles, shingles(item.transcript or item.description)
                ),
                title=self._title_signal(
                    draft_title_key, draft_title_tokens, item.title, draft_item.title
                ),
                description=jaccard(draft_description_tokens, set(content_tokens(item.description))),
                chapter_structure=_chapter_structure_similarity(draft_item.chapters, item.chapters),
            )
            combined = self._combine(signals, applicable)
            kind = self._classify(signals, draft_title_key, item.title, draft_item.title)
            matches.append(
                SimilarityMatch(
                    content_id=item.content_id,
                    title=item.title,
                    creator_id=item.creator_id,
                    language=item.language,
                    combined_score=combined,
                    signals=signals,
                    duplicate_kind=kind,
                    rationale=self._rationale(signals, kind),
                )
            )
        return matches

    def _combine(self, signals: SimilaritySignals, applicable: set[str] | None = None) -> float:
        """Weighted blend over the applicable signals, renormalised to sum to 1."""
        weights = self._settings.similarity_weights.as_dict()
        names = applicable if applicable is not None else set(weights)
        values = signals.model_dump()
        divisor = sum(weights[name] for name in names) or 1.0
        total = sum(weights[name] * values[name] for name in names) / divisor
        return round(min(1.0, total), 4)

    @staticmethod
    def _title_signal(
        draft_key: str, draft_tokens: set[str], other_title: str, draft_title: str = ""
    ) -> float:
        """1.0 when the season/part-stripped titles are identical, else token Jaccard.

        This is the signal that catches the 'Solo Leveling' / 'Solo Leveling Season 3'
        / 'Solo Leveling The End' re-upload family.
        """
        other_key = normalise_title(other_title)
        if draft_key and draft_key == other_key:
            # Same series name, but do they cover the same episodes? "Yakshini 701 to
            # 800" and "Yakshini 801 to 900" normalise identically because the digits
            # are stripped, yet they are consecutive parts, not a re-upload.
            mine, theirs = episode_range(draft_title), episode_range(other_title)
            if mine and theirs and not ranges_overlap(mine, theirs):
                return 0.35
            return 1.0
        if draft_key and other_key and (draft_key in other_key or other_key in draft_key):
            return 0.85
        return jaccard(draft_tokens, set(content_tokens(other_title)))

    @staticmethod
    def _classify(
        signals: SimilaritySignals, draft_key: str, other_title: str, draft_title: str = ""
    ) -> DuplicateKind:
        mine, theirs = episode_range(draft_title), episode_range(other_title)
        if mine and theirs and not ranges_overlap(mine, theirs):
            # Consecutive parts of one series. Publishing episode 801-900 after
            # 701-800 is the normal thing to do, not a duplicate upload.
            return DuplicateKind.NONE
        if signals.lexical_shingle >= _EXACT_SHINGLE_THRESHOLD:
            return DuplicateKind.EXACT_DUPLICATE
        if (
            draft_key
            and draft_key == normalise_title(other_title)
            and signals.semantic >= _VARIANT_SEMANTIC_THRESHOLD
        ):
            return DuplicateKind.SERIES_VARIANT
        if (
            signals.narrative_arc >= _NEAR_ARC_THRESHOLD
            and signals.semantic >= _NEAR_SEMANTIC_THRESHOLD
        ):
            return DuplicateKind.NEAR_DUPLICATE
        return DuplicateKind.NONE

    @staticmethod
    def _rationale(signals: SimilaritySignals, kind: DuplicateKind) -> str:
        if kind is DuplicateKind.EXACT_DUPLICATE:
            return f"{signals.lexical_shingle:.0%} of 5-word sequences are shared — verbatim overlap."
        if kind is DuplicateKind.SERIES_VARIANT:
            return (
                "Title is identical once season/part/language markers are removed, and the "
                f"content matches semantically at {signals.semantic:.2f}."
            )
        if kind is DuplicateKind.NEAR_DUPLICATE:
            return (
                f"Story skeleton matches at {signals.narrative_arc:.2f} despite different wording — "
                "same premise, conflict and progression."
            )
        if signals.title >= 1.0:
            return (
                "Titles are identical once season/part/language markers are stripped. The "
                "content signals are below the duplication thresholds, so this is a title "
                "collision to review rather than a confirmed copy."
            )
        strongest = max(
            signals.model_dump().items(), key=lambda pair: pair[1], default=("none", 0.0)
        )
        return f"No duplicate pattern; strongest signal was {strongest[0]} at {strongest[1]:.2f}."

    def _verdict(
        self,
        top_score: float,
        kind: DuplicateKind,
        title_collision: SimilarityMatch | None = None,
        top_match: SimilarityMatch | None = None,
    ) -> RiskLevel:
        # A confirmed exact copy or series re-upload is a block regardless of the blend,
        # because those two signals are unambiguous on their own.
        if kind in (DuplicateKind.EXACT_DUPLICATE, DuplicateKind.SERIES_VARIANT):
            return RiskLevel.BLOCK
        if top_score >= self._settings.similarity_block_threshold:
            return RiskLevel.BLOCK
        if kind is DuplicateKind.NEAR_DUPLICATE:
            return RiskLevel.REVIEW
        if top_score >= self._settings.similarity_review_threshold:
            return RiskLevel.REVIEW
        # A strong story-skeleton match, even when nothing else agrees. This is the
        # rewritten-copy case: different title, different words, same story.
        if title_collision is None and top_match is not None:
            if top_match.signals.narrative_arc >= _ARC_ALONE_REVIEW:
                return RiskLevel.REVIEW

        # "Ashen Throne Season 5" against an existing "Ashen Throne" is the exact
        # pattern this system was asked to catch. The titles are identical once
        # season/part/language markers are stripped, which on its own warrants a human
        # look -- even when the supplied draft is too short for the content signals to
        # reach the review threshold. It is a review, not a block: two unrelated
        # stories are allowed to share a title.
        if title_collision is not None:
            return RiskLevel.REVIEW
        return RiskLevel.CLEAR

    # --- explanation --------------------------------------------------------

    async def _explain(self, report: SimilarityReport, *, use_llm: bool) -> str:
        deterministic = self._deterministic_explanation(report)
        if not use_llm or not self._llm.available or not report.matches:
            return deterministic
        rendered = "\n".join(
            f"- {match.title} (id={match.content_id}, creator={match.creator_id}): "
            f"combined={match.combined_score}, "
            f"arc={match.signals.narrative_arc}, semantic={match.signals.semantic}, "
            f"shingle={match.signals.lexical_shingle}, title={match.signals.title}"
            for match in report.matches
        )
        result = await self._llm.complete_text(
            _EXPLANATION_PROMPT.format(
                title=report.candidate_title,
                risk=report.risk.value,
                top_score=report.top_score,
                kind=report.duplicate_kind.value,
                matches=rendered,
            ),
            max_tokens=260,
        )
        return result.text if result.ok and result.text else deterministic

    @staticmethod
    def _deterministic_explanation(report: SimilarityReport) -> str:
        if not report.matches:
            return "No catalog items were available to compare against, so no similarity was measured."
        top = report.matches[0]
        verdicts = {
            RiskLevel.BLOCK: "Upload is blocked pending human review.",
            RiskLevel.REVIEW: "Upload is flagged for human review.",
            RiskLevel.CLEAR: "No duplication pattern detected.",
        }
        return (
            f"Closest catalog item is '{top.title}' at combined similarity {top.combined_score:.2f} "
            f"(arc {top.signals.narrative_arc:.2f}, semantic {top.signals.semantic:.2f}, "
            f"verbatim {top.signals.lexical_shingle:.2f}, title {top.signals.title:.2f}). "
            f"{top.rationale} {verdicts[report.risk]}"
        )

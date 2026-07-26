"""Blend: one shared feed for two listeners.

This is a *group* recommender, and group recommendation is not the same problem as
single-user recommendation with two inputs averaged together. Averaging is the
obvious move and it is wrong in a specific, visible way: the member with more
listening history has a longer taste vector, denser co-occurrence neighbours and a
live sequence signal, so their scores are systematically larger. Average the two and
the feed quietly becomes the heavier listener's feed. The other person opens it, sees
nothing they recognise, and stops using it.

So the aggregation here does three things instead:

1.  **Per-member scoring reuses the production ranker.** Every candidate is scored by
    `RankingService` once per member, with that member's own profile. No separate
    "blend model" that could drift from what the rest of the product does -- the same
    eight signals, the same weights, the same explanations.

2.  **Per-member normalisation before combining.** Each member's raw scores are
    rescaled against that member's own score distribution over the same candidate
    set. This is what makes the two numbers comparable at all. Without it the
    combination step is comparing a heavy listener's 0.61 against a light listener's
    0.24 as though they meant the same thing; they do not.

3.  **Balanced aggregation, not mean.** `alpha * mean + (1 - alpha) * min`. The `min`
    term is "least misery" from the group-recommendation literature (Masthoff): it
    refuses to promote an item one member would clearly not want. The mean term stops
    least-misery on its own from selecting only inoffensive middle-of-the-road items,
    which is its known failure mode.

On top of that the selection pass enforces **representation**: if the running feed has
drifted to one member, the next slot is taken by the other member's best remaining
candidate. A blend where one person recognises nothing has failed regardless of what
the scores say.

Every item reports `lean` -- who it came from, as a signed number -- so the interface
can show the attribution rather than asserting that the feed is fair.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import ContentItem, UserProfile
from app.services.ranking import RankingContext, RankingService
from app.services.vectors import cosine

logger = get_logger(__name__)

#: Weight on the mean in `alpha * mean + (1 - alpha) * min`. At 1.0 this is a plain
#: average and the heavier listener wins; at 0.0 it is pure least-misery and the feed
#: collapses to whatever neither member objects to. 0.65 keeps the feed opinionated
#: while still letting one strong objection sink an item.
DEFAULT_ALPHA = 0.65

#: An item is "shared" when neither member's normalised score exceeds the other's by
#: more than this. Below it, the two are close enough that calling the item one
#: person's pick would be inventing a distinction the numbers do not support.
_SHARED_BAND = 0.12

#: How far representation may drift before the next slot is forced to the
#: under-represented member. 0.34 allows a 2:1 run, not 3:1.
_REPRESENTATION_FLOOR = 0.34


@dataclass(frozen=True)
class BlendMember:
    user_id: str
    display_name: str
    email: str
    profile: UserProfile


@dataclass
class BlendedItem:
    item: ContentItem
    score: float
    #: -1.0 = entirely the first member's taste, +1.0 = entirely the second's, 0 = shared.
    lean: float
    owner: str
    per_member: dict[str, float]
    raw_per_member: dict[str, float]
    reason: str


def taste_match(left: UserProfile, right: UserProfile) -> dict[str, float | str]:
    """How alike two listeners are, as a number we can defend.

    Three independent views, because any one of them is easy to fool. Two people who
    both listen to horror have a high genre overlap and may still want completely
    different stories; two people with similar embeddings may have overlapping taste
    but never have finished the same title.
    """
    vector = cosine(left.taste_vector, right.taste_vector) if left.taste_vector and right.taste_vector else 0.0
    genre = _affinity_overlap(left.genre_affinity, right.genre_affinity)
    language = _affinity_overlap(left.language_affinity, right.language_affinity)

    shared = set(left.positive_content_ids) & set(right.positive_content_ids)
    union = set(left.positive_content_ids) | set(right.positive_content_ids)
    library = len(shared) / len(union) if union else 0.0

    # Weighted toward the embedding, which is the only one of the three that reflects
    # what the stories are actually about rather than how they are labelled.
    overall = 0.5 * vector + 0.25 * genre + 0.15 * language + 0.10 * library
    return {
        "overall": round(overall, 4),
        "taste_vector": round(vector, 4),
        "genre_overlap": round(genre, 4),
        "language_overlap": round(language, 4),
        "shared_library": round(library, 4),
        "shared_titles": len(shared),
        "basis": (
            "0.50 taste-vector cosine + 0.25 genre overlap + 0.15 language overlap "
            "+ 0.10 shared finished titles"
        ),
    }


def _affinity_overlap(left: dict[str, float], right: dict[str, float]) -> float:
    """Agreement between two affinity maps, by strength *and* by breadth.

    Cosine alone is degenerate against these profiles. The profile builder min-max
    normalises affinity, so each listener ends up with exactly one genre at 1.0 and
    the rest at 0.0. Two people who both listen to crime-detective score a flat 0.0
    the moment it is not the single top genre for both -- which is not what anyone
    means by "do we overlap".

    So the strength view (cosine over the weights) is averaged with a breadth view
    (Jaccard over the genres each has engaged with at all). Breadth survives the
    normalisation; strength still decides between two pairs with the same breadth.
    """
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    a = [float(left.get(key, 0.0)) for key in keys]
    b = [float(right.get(key, 0.0)) for key in keys]
    strength = cosine(a, b)
    shared = set(left) & set(right)
    breadth = len(shared) / len(keys)
    return round(0.5 * strength + 0.5 * breadth, 6)


def _normalise(scores: dict[str, float]) -> dict[str, float]:
    """Rescale one member's scores across the shared candidate set to [0, 1].

    Min-max against that member's own spread, so "this member's best candidate" maps
    to 1.0 for a heavy and a light listener alike. A flat distribution (every
    candidate scored the same, which happens for a cold-start member) collapses to
    0.5 rather than dividing by zero -- a member with no opinion should neither veto
    nor drive the feed.
    """
    if not scores:
        return {}
    values = list(scores.values())
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return {key: 0.5 for key in scores}
    span = high - low
    return {key: (value - low) / span for key, value in scores.items()}


class BlendService:
    def __init__(self, settings: Settings, ranking: RankingService) -> None:
        self._settings = settings
        self._ranking = ranking

    def blend(
        self,
        members: list[BlendMember],
        context: RankingContext,
        *,
        limit: int = 18,
        alpha: float = DEFAULT_ALPHA,
        language: str | None = None,
    ) -> dict:
        if len(members) != 2:
            raise ValueError("A blend is between exactly two listeners.")
        first, second = members

        candidates = self._candidate_pool(members, context, language)
        if not candidates:
            return self._empty(members, alpha)

        # Score every candidate for each member with the production ranker, then
        # normalise within member so the two columns are comparable.
        raw = {
            member.user_id: self._ranking.score_for(member.profile, candidates, context)
            for member in members
        }
        normalised = {user_id: _normalise(scores) for user_id, scores in raw.items()}

        scored: list[BlendedItem] = []
        for item in candidates:
            left = normalised[first.user_id].get(item.content_id, 0.0)
            right = normalised[second.user_id].get(item.content_id, 0.0)
            combined = alpha * ((left + right) / 2.0) + (1.0 - alpha) * min(left, right)
            gap = right - left
            owner = "shared" if abs(gap) <= _SHARED_BAND else (
                second.user_id if gap > 0 else first.user_id
            )
            scored.append(
                BlendedItem(
                    item=item,
                    score=round(combined, 6),
                    lean=round(gap, 4),
                    owner=owner,
                    per_member={first.user_id: round(left, 4), second.user_id: round(right, 4)},
                    raw_per_member={
                        first.user_id: round(raw[first.user_id][item.content_id], 6),
                        second.user_id: round(raw[second.user_id][item.content_id], 6),
                    },
                    reason=self._reason(first, second, left, right, owner),
                )
            )

        selected = self._select_with_representation(scored, members, limit)
        return self._render(selected, members, context, alpha, len(candidates))

    # --- candidate pool -----------------------------------------------------

    def _candidate_pool(
        self, members: list[BlendMember], context: RankingContext, language: str | None
    ) -> list[ContentItem]:
        """Everything neither member has already finished together.

        Note the asymmetry: an item only *one* member has heard stays in. That is the
        point of a blend -- "the one you loved that they have not heard yet" is the
        best thing it can surface. Only items both have already been through are
        dropped, along with the duplicate re-uploads the similarity gate flagged.
        """
        heard_by_all = set.intersection(
            *[set(member.profile.interacted_content_ids) for member in members]
        )
        exclude = heard_by_all | context.suppressed
        return [
            item
            for item in context.catalog.values()
            if item.content_id not in exclude
            and (language is None or item.language == language)
        ]

    # --- selection ----------------------------------------------------------

    def _select_with_representation(
        self, scored: list[BlendedItem], members: list[BlendMember], limit: int
    ) -> list[BlendedItem]:
        """Greedy by blended score, with a floor on each member's representation.

        Pure greedy is correct on the objective and wrong on the product: the member
        whose taste happens to align with the catalog takes the whole feed. Before
        each pick we check whether either member has fallen below the floor and, if
        so, hand them the slot. Shared items count for both, so a genuinely
        well-matched pair never triggers the override at all.
        """
        pool = sorted(scored, key=lambda entry: entry.score, reverse=True)
        first, second = members[0].user_id, members[1].user_id
        chosen: list[BlendedItem] = []
        credit = {first: 0.0, second: 0.0}

        while pool and len(chosen) < limit:
            total = credit[first] + credit[second]
            owed: str | None = None
            if total >= 2:  # nothing to balance until the feed has a shape
                for user_id in (first, second):
                    if credit[user_id] / total < _REPRESENTATION_FLOOR:
                        owed = user_id
                        break

            pick = None
            if owed is not None:
                # Their own best candidate first. A shared item satisfies the check but
                # only moves the balance by half a slot, so it cannot correct a real
                # drift -- taking one here is how the feed stays lopsided.
                pick = next((entry for entry in pool if entry.owner == owed), None)
                pick = pick or next(
                    (entry for entry in pool if entry.owner == "shared"), None
                )
            pick = pick or pool[0]

            pool.remove(pick)
            chosen.append(pick)
            if pick.owner == "shared":
                credit[first] += 0.5
                credit[second] += 0.5
            else:
                credit[pick.owner] += 1.0

        return chosen

    # --- presentation -------------------------------------------------------

    @staticmethod
    def _reason(
        first: BlendMember, second: BlendMember, left: float, right: float, owner: str
    ) -> str:
        if owner == "shared":
            return f"Both of you rank this highly ({left:.0%} / {right:.0%})."
        if owner == first.user_id:
            return f"{first.display_name} leans into this one ({left:.0%} vs {right:.0%})."
        return f"{second.display_name} leans into this one ({right:.0%} vs {left:.0%})."

    def _render(
        self,
        selected: list[BlendedItem],
        members: list[BlendMember],
        context: RankingContext,
        alpha: float,
        pool_size: int,
    ) -> dict:
        counts = {member.user_id: 0 for member in members}
        shared = 0
        for entry in selected:
            if entry.owner == "shared":
                shared += 1
            else:
                counts[entry.owner] = counts.get(entry.owner, 0) + 1

        return {
            "items": [
                {
                    "content_id": entry.item.content_id,
                    "title": entry.item.title,
                    "description": entry.item.description,
                    "language": entry.item.language,
                    "genres": entry.item.genres,
                    "creator_id": entry.item.creator_id,
                    "duration_seconds": entry.item.duration_seconds,
                    "score": entry.score,
                    "lean": entry.lean,
                    "owner": entry.owner,
                    "per_member": entry.per_member,
                    "raw_per_member": entry.raw_per_member,
                    "reason": entry.reason,
                }
                for entry in selected
            ],
            "mix": {
                "shared": shared,
                **{member.user_id: counts[member.user_id] for member in members},
            },
            "candidate_pool_size": pool_size,
            "provenance": context.provenance.value,
            "method": {
                "aggregation": f"{alpha:.2f} x mean + {1 - alpha:.2f} x least-misery(min)",
                "alpha": alpha,
                "normalisation": "per-member min-max over the shared candidate pool",
                "representation_floor": _REPRESENTATION_FLOOR,
                "shared_band": _SHARED_BAND,
                "scorer": "the production RankingService — same 8 signals and weights as /recommendations",
                "why_not_average": (
                    "A plain average is dominated by whichever member has more listening "
                    "history, because their raw scores are larger. Normalising per member "
                    "first, then blending mean with least-misery, keeps both tastes in play."
                ),
            },
        }

    def _empty(self, members: list[BlendMember], alpha: float) -> dict:
        return {
            "items": [],
            "mix": {"shared": 0, **{member.user_id: 0 for member in members}},
            "candidate_pool_size": 0,
            "provenance": "real",
            "method": {"aggregation": f"{alpha:.2f} x mean + {1 - alpha:.2f} x least-misery(min)"},
        }

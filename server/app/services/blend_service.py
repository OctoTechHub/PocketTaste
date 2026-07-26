"""Application service for blends: resolve people, then hand off to the algorithm.

`BlendService` in `blend.py` is pure scoring — it takes two profiles and a ranking
context and returns a ranked feed. This is the layer that knows about accounts,
emails and storage, so the algorithm stays testable without a database.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.clock import utcnow
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.data.repositories import (
    BlendRepository,
    UserAccountRepository,
    UserProfileRepository,
)
from app.domain.models import Blend, UserProfile
from app.services.blend import BlendMember, BlendService, taste_match

logger = get_logger(__name__)


class BlendApplicationService:
    def __init__(
        self,
        blends: BlendRepository,
        accounts: UserAccountRepository,
        users: UserProfileRepository,
        algorithm: BlendService,
    ) -> None:
        self._blends = blends
        self._accounts = accounts
        self._users = users
        self._algorithm = algorithm

    async def create(self, *, owner_id: str, partner_email: str) -> tuple[Blend, bool]:
        """Start a blend with the person at this address.

        Returns `(blend, created)`. Adding someone twice returns the existing blend
        rather than erroring — the button is idempotent, which is what a person
        pressing it twice expects.
        """
        partner = await self._accounts.get_by_email(partner_email)
        if partner is None:
            raise NotFoundError(
                f"No listener is registered with {partner_email.strip().lower()}.",
                details={"email": partner_email.strip().lower(), "invited": False},
            )
        if partner.user_id == owner_id:
            raise ValidationError("You cannot blend with yourself.")
        if not partner.is_active:
            raise ConflictError(f"{partner.display_name}'s account is not active.")

        existing = await self._blends.between(owner_id, partner.user_id)
        if existing is not None:
            return existing, False

        blend = Blend(
            blend_id=f"bld_{uuid4().hex[:12]}",
            member_ids=sorted([owner_id, partner.user_id]),
            created_by=owner_id,
        )
        await self._blends.upsert(blend)
        logger.info("Blend %s created by %s with %s", blend.blend_id, owner_id, partner.user_id)
        return blend, True

    async def list_for(self, user_id: str) -> list[dict]:
        blends = await self._blends.for_member(user_id)
        return [await self._describe(blend, viewer_id=user_id) for blend in blends]

    async def get(self, blend_id: str, *, viewer_id: str) -> Blend:
        blend = await self._blends.get(blend_id)
        if blend is None:
            raise NotFoundError(f"No blend with id '{blend_id}'.")
        if viewer_id not in blend.member_ids:
            # Deliberately the same error as a missing blend: a blend id should not be
            # a probe for who else uses the product.
            raise NotFoundError(f"No blend with id '{blend_id}'.")
        return blend

    async def remove(self, blend_id: str, *, viewer_id: str) -> None:
        await self.get(blend_id, viewer_id=viewer_id)
        await self._blends.delete(blend_id)

    async def describe(self, blend_id: str, *, viewer_id: str) -> dict:
        return await self._describe(await self.get(blend_id, viewer_id=viewer_id), viewer_id)

    async def feed(self, blend_id: str, *, viewer_id: str, context, limit: int, language=None) -> dict:
        blend = await self.get(blend_id, viewer_id=viewer_id)
        members = await self._members(blend, viewer_id=viewer_id)
        result = self._algorithm.blend(members, context, limit=limit, language=language)
        await self._blends.upsert(blend.model_copy(update={"last_viewed_at": utcnow()}))
        return {
            "blend_id": blend.blend_id,
            "members": [self._member_payload(member, viewer_id) for member in members],
            "taste_match": taste_match(members[0].profile, members[1].profile),
            **result,
        }

    # --- internals ----------------------------------------------------------

    async def _members(self, blend: Blend, *, viewer_id: str) -> list[BlendMember]:
        """Members ordered viewer-first, so the interface always knows which side is 'you'."""
        ordered = [viewer_id] + [uid for uid in blend.member_ids if uid != viewer_id]
        members: list[BlendMember] = []
        for user_id in ordered:
            account = await self._accounts.get(user_id)
            if account is None:
                raise NotFoundError(f"Blend member '{user_id}' no longer exists.")
            profile = await self._users.get(user_id) or UserProfile(user_id=user_id)
            members.append(
                BlendMember(
                    user_id=user_id,
                    display_name=account.display_name,
                    email=account.email,
                    profile=profile,
                )
            )
        return members

    async def _describe(self, blend: Blend, viewer_id: str) -> dict:
        members = await self._members(blend, viewer_id=viewer_id)
        return {
            "blend_id": blend.blend_id,
            "created_at": blend.created_at,
            "created_by": blend.created_by,
            "last_viewed_at": blend.last_viewed_at,
            "members": [self._member_payload(member, viewer_id) for member in members],
            "taste_match": taste_match(members[0].profile, members[1].profile),
        }

    @staticmethod
    def _member_payload(member: BlendMember, viewer_id: str) -> dict:
        return {
            "user_id": member.user_id,
            "display_name": member.display_name,
            "email": member.email,
            "is_you": member.user_id == viewer_id,
            "is_cold_start": member.profile.is_cold_start,
            "events_observed": member.profile.events_observed,
            # Zero-affinity genres are in the map because the listener touched them
            # once, not because they like them. Showing them as "top genres" turns
            # noise into a claim about someone's taste.
            "top_genres": [
                [genre, round(weight, 4)]
                for genre, weight in sorted(
                    member.profile.genre_affinity.items(), key=lambda pair: -pair[1]
                )[:3]
                if weight > 0
            ],
        }

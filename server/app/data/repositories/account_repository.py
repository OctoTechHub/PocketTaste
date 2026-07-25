"""Account persistence. The only place credentials are read or written."""

from __future__ import annotations

from app.core.clock import utcnow
from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository
from app.domain.models import UserAccount


class UserAccountRepository(BaseRepository[UserAccount]):
    collection_name = Collections.ACCOUNTS
    model_type = UserAccount
    key_field = "user_id"

    @staticmethod
    def normalise_email(email: str) -> str:
        """Emails are matched case-insensitively; store and query the lowered form."""
        return email.strip().lower()

    async def get_by_email(self, email: str) -> UserAccount | None:
        document = await self.collection.find_one({"email": self.normalise_email(email)})
        if document is None:
            return None
        document.pop("_id", None)
        return UserAccount.model_validate(document)

    async def email_exists(self, email: str) -> bool:
        return (
            await self.collection.count_documents({"email": self.normalise_email(email)}, limit=1)
            > 0
        )

    async def record_login(self, user_id: str) -> None:
        await self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"last_login_at": utcnow()}, "$inc": {"login_count": 1}},
        )

    async def list_accounts(self, limit: int = 100) -> list[UserAccount]:
        return await self.find({}, limit=limit, sort=[("created_at", 1)])

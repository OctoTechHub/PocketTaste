"""Registration, login and token issue.

Deliberate choices:

* Login returns the same error whether the email is unknown or the password is
  wrong, and still runs a hash comparison for a missing account. Otherwise response
  timing and wording turn the endpoint into an account-enumeration oracle.
* `password_hash` never leaves this layer — every outbound payload goes through
  `UserAccount.public()`.
* A real account and a simulated listener can never collide: accounts get a `u_`
  prefix, the simulator uses `listener_`.
"""

from __future__ import annotations

import re
from uuid import uuid4

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import ConflictError, PocketTasteError, ValidationError
from app.core.logging import get_logger
from app.core.security import (
    InvalidTokenError,
    TokenPair,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.data.repositories import UserAccountRepository
from app.domain.models import UserAccount

logger = get_logger(__name__)

#: Prefix for real accounts, so they are distinguishable from simulated listeners at
#: a glance in the event log.
ACCOUNT_PREFIX = "u_"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")

#: A dummy hash to compare against when the account does not exist, so a failed
#: lookup costs the same wall-clock time as a wrong password.
_DUMMY_HASH = hash_password("timing-equalisation-placeholder")


class AuthenticationError(PocketTasteError):
    status_code = 401
    code = "authentication_failed"


class AuthService:
    def __init__(self, settings: Settings, accounts: UserAccountRepository) -> None:
        self._settings = settings
        self._accounts = accounts

    # --- registration -------------------------------------------------------

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str = "",
        roles: list[str] | None = None,
    ) -> UserAccount:
        normalised = UserAccountRepository.normalise_email(email)
        if not _EMAIL_PATTERN.match(normalised):
            raise ValidationError("That does not look like a valid email address.")
        if len(password) < self._settings.min_password_length:
            raise ValidationError(
                f"Password must be at least {self._settings.min_password_length} characters."
            )
        if await self._accounts.email_exists(normalised):
            raise ConflictError("An account with that email already exists.")

        account = UserAccount(
            user_id=f"{ACCOUNT_PREFIX}{uuid4().hex[:12]}",
            email=normalised,
            display_name=(display_name.strip() or normalised.split("@")[0]).title(),
            password_hash=hash_password(password),
            roles=roles or ["listener"],
            created_at=utcnow(),
        )
        await self._accounts.upsert(account)
        logger.info("Registered account %s (%s)", account.user_id, account.email)
        return account

    # --- login --------------------------------------------------------------

    async def authenticate(self, *, email: str, password: str) -> UserAccount:
        account = await self._accounts.get_by_email(email)
        # Always hash, even with no account, so timing does not leak existence.
        expected = account.password_hash if account else _DUMMY_HASH
        matches = verify_password(password, expected)

        if account is None or not matches:
            raise AuthenticationError("Incorrect email or password.")
        if not account.is_active:
            raise AuthenticationError("This account is disabled.")

        await self._accounts.record_login(account.user_id)
        logger.info("Login: %s", account.email)
        return account

    async def set_password(self, *, email: str, password: str) -> UserAccount:
        """Replace an account's password. Used by the onboarding script.

        There is no 'old password' argument because this is an operator action, not a
        user-facing change-password flow — that would need the current password.
        """
        if len(password) < self._settings.min_password_length:
            raise ValidationError(
                f"Password must be at least {self._settings.min_password_length} characters."
            )
        account = await self._accounts.get_by_email(email)
        if account is None:
            raise ValidationError(f"No account for {email}.")

        account.password_hash = hash_password(password)
        await self._accounts.upsert(account)
        logger.info("Password reset for %s", account.email)
        return account

    def issue_token(self, account: UserAccount) -> TokenPair:
        return create_access_token(
            account.user_id,
            self._settings.jwt_signing_key,
            expires_minutes=self._settings.access_token_minutes,
        )

    # --- token verification -------------------------------------------------

    async def resolve_token(self, token: str) -> UserAccount:
        try:
            user_id = decode_access_token(token, self._settings.jwt_signing_key)
        except InvalidTokenError as exc:
            raise AuthenticationError(str(exc)) from exc

        account = await self._accounts.get(user_id)
        if account is None:
            raise AuthenticationError("Account no longer exists.")
        if not account.is_active:
            raise AuthenticationError("This account is disabled.")
        return account

    # --- introspection ------------------------------------------------------

    def describe(self) -> dict:
        return {
            "scheme": "bearer",
            "algorithm": "HS256",
            "password_hashing": "scrypt (n=16384, r=8, p=1), per-password salt",
            "access_token_minutes": self._settings.access_token_minutes,
            "secret_configured": self._settings.jwt_secret_configured,
            "warning": (
                None
                if self._settings.jwt_secret_configured
                else "JWT_SECRET is not set; a random key is generated per process, so "
                "every token is invalidated on restart. Set it in .env."
            ),
        }

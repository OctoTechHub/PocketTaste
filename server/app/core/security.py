"""Password hashing and bearer tokens.

Passwords use **scrypt** from the standard library. It is memory-hard, so it resists
GPU cracking in a way PBKDF2 does not, and it needs no third-party dependency. The
cost parameters and the per-password salt are stored alongside the hash, so they can
be raised later without invalidating existing credentials.

Tokens are HS256 JWTs. Short-lived, signed with a server secret, and carrying only
the subject and issue/expiry times — no personal data rides in the payload.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.clock import utcnow
from app.core.logging import get_logger

logger = get_logger(__name__)

# scrypt cost parameters. n=2**14 keeps a single verification around ~50-80ms, which
# is slow enough to matter for an attacker and fast enough for a login request.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised for a malformed, expired or wrongly-signed token."""


def hash_password(password: str) -> str:
    """Return `scrypt$n$r$p$salt$key`, all hex. Self-describing so cost can change."""
    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_BYTES
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification. Returns False rather than raising on a bad hash."""
    try:
        scheme, n, r, p, salt_hex, key_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(key_hex)),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, bytes.fromhex(key_hex))


@dataclass(slots=True)
class TokenPair:
    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime


def create_access_token(subject: str, secret: str, *, expires_minutes: int) -> TokenPair:
    issued = utcnow()
    expires = issued + timedelta(minutes=expires_minutes)
    payload = {
        "sub": subject,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
        "typ": "access",
    }
    return TokenPair(
        access_token=jwt.encode(payload, secret, algorithm=_ALGORITHM),
        token_type="bearer",
        expires_in=expires_minutes * 60,
        expires_at=expires,
    )


def decode_access_token(token: str, secret: str) -> str:
    """Return the subject (user id). Raises InvalidTokenError on any problem."""
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Token is invalid.") from exc
    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError("Token has no subject.")
    return str(subject)


def generate_password(length: int = 14) -> str:
    """A readable but strong password for onboarding. Ambiguous glyphs removed."""
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))

"""Authentication: hashing, tokens, and the guarantees the API depends on."""

from __future__ import annotations

import time

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_password,
    hash_password,
    verify_password,
)
from app.domain.models import UserAccount

SECRET = "test-secret-not-used-anywhere-real"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_password_round_trips():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False


def test_hash_is_salted_so_identical_passwords_differ():
    first, second = hash_password("same-password"), hash_password("same-password")
    assert first != second
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)


def test_hash_never_contains_the_plaintext():
    encoded = hash_password("MySecretValue123")
    assert "MySecretValue123" not in encoded


def test_hash_is_self_describing_so_cost_can_be_raised_later():
    scheme, n, r, p, salt, key = hash_password("x").split("$")
    assert scheme == "scrypt"
    assert int(n) >= 2**14 and int(r) == 8 and int(p) == 1
    assert len(bytes.fromhex(salt)) == 16
    assert len(bytes.fromhex(key)) == 32


@pytest.mark.parametrize("garbage", ["", "not-a-hash", "scrypt$bad", "md5$1$1$1$aa$bb", "$$$$$"])
def test_malformed_hashes_return_false_rather_than_raising(garbage):
    assert verify_password("anything", garbage) is False


def test_generated_passwords_are_strong_and_unambiguous():
    passwords = {generate_password() for _ in range(50)}
    assert len(passwords) == 50                      # no collisions
    assert all(len(p) == 14 for p in passwords)
    # Glyphs that are easy to misread when a password is transcribed.
    assert not any(set(p) & set("lIO01o") for p in passwords)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def test_token_round_trips_to_its_subject():
    token = create_access_token("u_abc123", SECRET, expires_minutes=60)
    assert token.token_type == "bearer"
    assert token.expires_in == 3600
    assert decode_access_token(token.access_token, SECRET) == "u_abc123"


def test_token_signed_with_another_secret_is_rejected():
    token = create_access_token("u_abc123", SECRET, expires_minutes=60)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token.access_token, "a-different-secret")


def test_expired_token_is_rejected():
    from datetime import timedelta

    import jwt

    from app.core.clock import utcnow

    expired = jwt.encode(
        {
            "sub": "u_abc",
            "iat": int((utcnow() - timedelta(hours=2)).timestamp()),
            "exp": int((utcnow() - timedelta(hours=1)).timestamp()),
        },
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError, match="expired"):
        decode_access_token(expired, SECRET)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "not.a.jwt.at.all"])
def test_malformed_tokens_are_rejected(garbage):
    with pytest.raises(InvalidTokenError):
        decode_access_token(garbage, SECRET)


def test_token_without_a_subject_is_rejected():
    import jwt

    from app.core.clock import utcnow

    token = jwt.encode({"iat": int(utcnow().timestamp())}, SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError, match="subject"):
        decode_access_token(token, SECRET)


def test_unsigned_none_algorithm_token_is_rejected():
    """The classic JWT bypass: swap alg to 'none' and drop the signature."""
    import base64
    import json

    def b64(payload: dict) -> str:
        raw = json.dumps(payload).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'u_admin'})}."
    with pytest.raises(InvalidTokenError):
        decode_access_token(forged, SECRET)


# ---------------------------------------------------------------------------
# Account model
# ---------------------------------------------------------------------------


def test_public_view_never_exposes_the_credential():
    account = UserAccount(
        user_id="u_1",
        email="krish@gmail.com",
        display_name="Krish",
        password_hash=hash_password("secret-value"),
    )
    public = account.public()
    assert "password_hash" not in public
    assert "secret-value" not in str(public)
    assert public["email"] == "krish@gmail.com"
    assert public["roles"] == ["listener"]


def test_emails_are_matched_case_insensitively():
    from app.data.repositories import UserAccountRepository

    assert UserAccountRepository.normalise_email("  Krish@GMAIL.com ") == "krish@gmail.com"


def test_account_response_schema_has_no_credential_field():
    """Belt and braces: the response model itself cannot carry a hash."""
    from app.domain.schemas import AccountResponse

    assert "password_hash" not in AccountResponse.model_fields
    assert "password" not in AccountResponse.model_fields


def test_activity_payload_cannot_carry_a_user_id():
    """user_id must come from the token, never the body, or one caller could write
    events into another listener's history."""
    import pydantic

    from app.domain.schemas import ActivityCreate

    assert "user_id" not in ActivityCreate.model_fields
    with pytest.raises(pydantic.ValidationError):
        ActivityCreate(event_type="play", user_id="u_someone_else")


def test_my_recommendation_request_cannot_carry_a_user_id():
    import pydantic

    from app.domain.schemas import MyRecommendationRequest

    assert "user_id" not in MyRecommendationRequest.model_fields
    with pytest.raises(pydantic.ValidationError):
        MyRecommendationRequest(limit=5, user_id="u_someone_else")

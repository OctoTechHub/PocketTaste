"""Account registration, sign-in and the authenticated listener's own view."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import ContainerDep, CurrentAccount, StorageDep
from app.domain.schemas import (
    AccountResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(container, account) -> TokenResponse:
    token = container.auth.issue_token(account)
    return TokenResponse(
        access_token=token.access_token,
        token_type=token.token_type,
        expires_in=token.expires_in,
        expires_at=token.expires_at,
        account=AccountResponse(**account.public()),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and sign in",
)
async def register(payload: RegisterRequest, container: StorageDep) -> TokenResponse:
    account = await container.auth.register(
        email=payload.email, password=payload.password, display_name=payload.display_name
    )
    return _token_response(container, account)


@router.post("/login", response_model=TokenResponse, summary="Sign in and get a bearer token")
async def login(payload: LoginRequest, container: StorageDep) -> TokenResponse:
    """Returns the same error for an unknown email and a wrong password, on purpose —
    distinguishing them would turn this into an account-enumeration oracle."""
    account = await container.auth.authenticate(email=payload.email, password=payload.password)
    return _token_response(container, account)


@router.get("/me", response_model=AccountResponse, summary="The signed-in account")
async def me(account: CurrentAccount) -> AccountResponse:
    return AccountResponse(**account.public())


@router.get("/scheme", summary="How authentication works here")
async def scheme(container: ContainerDep) -> dict:
    return container.auth.describe() | {
        "flow": [
            "POST /auth/register or /auth/login -> access_token",
            "Send 'Authorization: Bearer <token>' on authenticated routes",
        ],
        "authenticated_routes": {
            "POST /activity, /activity/batch": "events are attributed to the token holder",
            "GET /me/*": "the signed-in listener's own profile and recommendations",
            "POST /catalog": "uploads are attributed to the signed-in creator",
            "POST /copilot/outline": "drafting is attributed to the signed-in creator",
        },
        "note": (
            "user_id is never accepted from a request body on these routes. It comes from "
            "the token, so a caller cannot write events into someone else's history."
        ),
    }

"""FastAPI dependency accessors. The container lives on `app.state`."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container
from app.core.errors import DependencyUnavailableError
from app.domain.models import UserAccount
from app.services.auth_service import AuthenticationError

#: auto_error=False so a missing header raises our own 401 shape rather than
#: FastAPI's, keeping every error response consistent.
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer token from POST /auth/login")


def get_container(request: Request) -> Container:
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:
        raise DependencyUnavailableError("Application container is not initialised.")
    return container


def require_storage(request: Request) -> Container:
    """For routes that cannot function without MongoDB."""
    container = get_container(request)
    if not container.gateway.connected:
        raise DependencyUnavailableError(
            "MongoDB is not connected. Set DB_URL in server/.env and restart.",
            details={"database": container.settings.mongo_db_name},
        )
    return container


async def get_current_account(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserAccount:
    """Resolve the bearer token to a live account, or 401."""
    container = require_storage(request)
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token. Sign in via POST /auth/login.")
    return await container.auth.resolve_token(credentials.credentials)


async def get_optional_account(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserAccount | None:
    """For endpoints that personalise when signed in but still work anonymously."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        container = require_storage(request)
        return await container.auth.resolve_token(credentials.credentials)
    except (AuthenticationError, DependencyUnavailableError):
        return None


ContainerDep = Annotated[Container, Depends(get_container)]
StorageDep = Annotated[Container, Depends(require_storage)]
CurrentAccount = Annotated[UserAccount, Depends(get_current_account)]
OptionalAccount = Annotated[UserAccount | None, Depends(get_optional_account)]

"""Domain errors and their HTTP translation. Services raise these, never HTTPException."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class PocketTasteError(Exception):
    """Base class for every error this service raises deliberately."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(PocketTasteError):
    status_code = 404
    code = "not_found"


class ConflictError(PocketTasteError):
    status_code = 409
    code = "conflict"


class ValidationError(PocketTasteError):
    status_code = 422
    code = "validation_error"


class DependencyUnavailableError(PocketTasteError):
    status_code = 503
    code = "dependency_unavailable"


class InsufficientDataError(PocketTasteError):
    """Raised instead of inventing numbers when the sample is empty."""

    status_code = 409
    code = "insufficient_data"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PocketTasteError)
    async def _handle(_: Request, exc: PocketTasteError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Reshape FastAPI's default `{"detail": [...]}` into our own envelope.

        Without this, a schema violation (e.g. a field too short) reaches the
        client as a bare pydantic error list under `detail`, which every other
        error path here does not use — so generic error-message extraction on the
        client silently drops the actual reason and shows "Request failed".
        """
        errors = exc.errors()
        summary = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
            for error in errors
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": summary or "Request validation failed.",
                    "details": {"errors": errors},
                }
            },
        )

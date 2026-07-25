"""PocketTaste API entrypoint.

    uvicorn app.main:app --reload --port 4000

Multi-stage recommendation + conversational discovery for long-form audio.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import router

app = FastAPI(title="PocketTaste API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.client_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {"service": "PocketTaste", "docs": "/docs", "api": "/api/health"}

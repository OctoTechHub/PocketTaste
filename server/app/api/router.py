"""Single place where every router is mounted."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    activity,
    analytics,
    auth,
    blend,
    catalog,
    copilot,
    creator,
    discovery,
    evaluation,
    health,
    insights,
    me,
    pipeline,
    recommendations,
    similarity,
)

api_router = APIRouter()

for module in (
    health,
    auth,
    blend,
    catalog,
    activity,
    me,
    analytics,
    similarity,
    recommendations,
    discovery,
    insights,
    pipeline,
    evaluation,
    copilot,
    creator,
):
    api_router.include_router(module.router)

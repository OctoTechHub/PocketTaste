"""Request bodies for the write/query endpoints."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.domain.models import EventType


class DiscoverRequest(BaseModel):
    query: str
    user_id: Optional[str] = None


class EventRequest(BaseModel):
    user_id: str
    series_id: str
    type: EventType
    episode_index: Optional[int] = None
    completion_pct: Optional[float] = None
    coins: Optional[int] = None
    value: Optional[float] = None
    session_id: Optional[str] = None

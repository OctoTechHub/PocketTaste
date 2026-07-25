"""Time access, isolated so tests and the simulator can reason about it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Mongo returns naive datetimes; normalise everything back to aware UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def days_between(later: datetime, earlier: datetime) -> float:
    return max(0.0, (as_utc(later) - as_utc(earlier)).total_seconds() / 86400.0)


def days_ago(days: float) -> datetime:
    return utcnow() - timedelta(days=days)

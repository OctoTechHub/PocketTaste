"""In-memory read cache for the two things every request needs: the catalog and
the item-item co-occurrence index.

The catalog is immutable at runtime; the co-occurrence index is invalidated
whenever new behavior is logged.
"""
from __future__ import annotations

from app.data.repositories import event_repository, series_repository
from app.domain.models import Series
from app.services.candidate_service import build_cooccurrence

_catalog: list[Series] | None = None
_cooccurrence: dict[str, dict[str, int]] | None = None


def get_catalog() -> list[Series]:
    global _catalog
    if _catalog is None:
        _catalog = series_repository.find_all()
    return _catalog


def get_cooccurrence() -> dict[str, dict[str, int]]:
    global _cooccurrence
    if _cooccurrence is None:
        _cooccurrence = build_cooccurrence(event_repository.find_all())
    return _cooccurrence


def invalidate_context() -> None:
    """Call after logging events so the co-occurrence index rebuilds lazily."""
    global _cooccurrence
    _cooccurrence = None


def invalidate_catalog() -> None:
    global _catalog, _cooccurrence
    _catalog = None
    _cooccurrence = None

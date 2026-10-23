"""Validate temporal scope before drawing a claim relation."""

from datetime import date
from typing import Protocol


class _Scoped(Protocol):
    scope_start: str | None
    scope_end: str | None


def _bounds(row: _Scoped) -> tuple[date, date] | None:
    if not row.scope_start or not row.scope_end:
        return None
    start = date.fromisoformat(row.scope_start)
    end = date.fromisoformat(row.scope_end)
    return (start, end) if start <= end else None


def has_valid_temporal_scope(row: _Scoped) -> bool:
    return _bounds(row) is not None


def scopes_overlap(left: _Scoped, right: _Scoped) -> bool:
    left_bounds = _bounds(left)
    right_bounds = _bounds(right)
    return bool(
        left_bounds and right_bounds
        and max(left_bounds[0], right_bounds[0]) <= min(left_bounds[1], right_bounds[1])
    )

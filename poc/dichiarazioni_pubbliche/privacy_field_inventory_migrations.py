"""Versioned private migration table registration for the DP-304 census."""

from __future__ import annotations

from pathlib import Path


_MIGRATIONS = (
    (
        "20261022-add-atomic-monthly-dispatch.sql",
        {"dp514_monthly_dispatch_policy", "dp514_monthly_dispatch_reservation"},
        "PRIVACY_DP514_MONTHLY_TABLE_DRIFT",
    ),
    (
        "20261025-add-dp515-watch-pg.sql",
        {"dp515_watch_source", "dp515_watch_attempt"},
        "PRIVACY_DP515_WATCH_TABLE_DRIFT",
    ),
    (
        "20261026-add-camera-private-parse-attestation.sql",
        {"private_camera_parse_attestation"},
        "PRIVACY_DP449_CAMERA_PARSE_TABLE_DRIFT",
    ),
)


def register_versioned_privacy_migrations(
    root: Path, tables: dict, parse_fields, error_type: type[ValueError]
) -> tuple[dict, dict]:
    """Add only explicitly reviewed opt-in table sets to the private census."""
    loaded = []
    for filename, expected, error in _MIGRATIONS:
        path = root / "db" / "migrations" / filename
        found = parse_fields(path.read_text(encoding="utf-8"))
        if set(found) != expected or (set(found) & set(tables)):
            raise error_type(error)
        tables.update(found)
        loaded.append(found)
    return loaded[0], loaded[1]

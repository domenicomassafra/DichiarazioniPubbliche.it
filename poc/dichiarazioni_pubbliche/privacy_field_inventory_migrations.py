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
        "20261026-add-autonomous-nightly-audit.sql",
        {"autonomous_nightly_audit_run", "autonomous_nightly_audit_result",
         "autonomous_nightly_audit_complete"},
        "PRIVACY_DP413E_NIGHTLY_TABLE_DRIFT",
    ),
)


def register_versioned_privacy_migrations(
    root: Path, tables: dict, parse_fields, error_type: type[ValueError]
) -> tuple[dict, ...]:
    """Add only explicitly reviewed opt-in table sets to the private census."""
    loaded = []
    for filename, expected, error in _MIGRATIONS:
        path = root / "db" / "migrations" / filename
        found = parse_fields(path.read_text(encoding="utf-8"))
        if set(found) != expected or (set(found) & set(tables)):
            raise error_type(error)
        tables.update(found)
        loaded.append(found)
    return tuple(loaded)


def privacy_schema_origin(table: str, column: str, monthly: dict, watch: dict, nightly: dict) -> str:
    """Trace private columns to the reviewed schema or versioned migration."""
    if table == "public_schema_contract":
        return "20260926_PUBLIC_SCHEMA_CONTRACT_MIGRATION"
    if table == "claim_relation_candidate" and column == "policy_version":
        return "20260926_RELATION_POLICY_MIGRATION"
    if table in monthly:
        return "20261022_DP514_MONTHLY_MIGRATION"
    if table in watch:
        return "20261025_DP515_WATCH_MIGRATION"
    if table in nightly:
        return "20261026_DP413E_NIGHTLY_MIGRATION"
    return "CANONICAL_SCHEMA_V1"

#!/usr/bin/env python3
"""DP-304 inventory contract check; --generate updates tracked private metadata only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.privacy_field_inventory import (  # noqa: E402
    FieldInventoryError, LivePrivacyFieldStore, compare_live_columns,
    make_inventory, canonical_inventory, check_inventory,
    read_account_sqlite_columns, compare_account_sqlite_columns,
    compare_host_surface_metadata,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Intentionally refresh inventory after schema review")
    parser.add_argument("--verify-live-db", action="store_true", help="Read-only PostgreSQL metadata comparison, never a legal clearance")
    parser.add_argument("--database-url", default=None, help="Optional PostgreSQL DSN/database; omitted uses PGDATABASE")
    parser.add_argument("--verify-account-db", type=Path, help="Read-only optional account SQLite catalog comparison")
    parser.add_argument("--verify-host-metadata", type=Path, help="Sanitized MiniPC field-name/counter JSON readback, not journal message contents")
    args = parser.parse_args(argv)
    source = ROOT / "db/schema.v1.sql"
    target = ROOT / "config/privacy-field-inventory.v1.json"
    try:
        if args.generate:
            target.write_text(canonical_inventory(make_inventory(source.read_text(encoding="utf-8"))), encoding="utf-8")
        result = check_inventory(source, target)
        if args.verify_live_db:
            actual = json.loads(target.read_text(encoding="utf-8"))
            comparison = compare_live_columns(
                actual, LivePrivacyFieldStore(database_url=args.database_url).read_columns()
            )
            result["live_catalog"] = comparison
        if args.verify_account_db is not None:
            actual = json.loads(target.read_text(encoding="utf-8"))
            result["account_sqlite_catalog"] = compare_account_sqlite_columns(
                actual, read_account_sqlite_columns(args.verify_account_db)
            )
        if args.verify_host_metadata is not None:
            observed = json.loads(args.verify_host_metadata.read_text(encoding="utf-8"))
            actual = json.loads(target.read_text(encoding="utf-8"))
            result["host_runtime_metadata"] = compare_host_surface_metadata(actual, observed)
        print(json.dumps(result, sort_keys=True))
        return 0 if all(
            result[key]["live_matches_inventory"]
            for key in ("live_catalog", "account_sqlite_catalog") if key in result
        ) and ("host_runtime_metadata" not in result or result["host_runtime_metadata"]["host_metadata_covered"]) else 2
    except (FieldInventoryError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

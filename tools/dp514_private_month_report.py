#!/usr/bin/env python3
"""Read an explicit local DP514 month read-only, without authority or IDs."""
from __future__ import annotations

import argparse
import json
import sqlite3
import stat
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    SQLiteMonthlyReservationStore, _MONTH_PATTERN,
)


class ReadOnlyBudgetStore(SQLiteMonthlyReservationStore):
    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("MONTHLY_REPORT_DB_INVALID")
        uri = "file:" + quote(str(path.absolute()), safe="/") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=3)
        conn.execute("PRAGMA query_only=ON")
        return conn


def redacted_month_report(path: Path, period: str) -> dict[str, object]:
    if not isinstance(period, str) or _MONTH_PATTERN.fullmatch(period) is None:
        raise ValueError("MONTHLY_REPORT_PERIOD_INVALID")
    store = ReadOnlyBudgetStore(path)
    before = store.read(period)
    report = store.reconciliation_report(period)
    state = store.read(period)
    # The separate public API to the existing reconciler opens its own read
    # transaction. Detect a concurrent persisted CAS instead of displaying
    # a mixture of pre/post observation totals as a coherent operator report.
    if before != state:
        raise ValueError("MONTHLY_REPORT_CHANGED_DURING_READ")
    return {
        "contract_version": "dp514-private-accounting-readonly-v1",
        "period": period, "state_revision": state.revision,
        "state_sha256": state.fingerprint(),
        "reserved_attempts": len(state.reservations),
        "observed_attempts": report.observed_attempts,
        "held_eur": str(report.held_total_eur),
        "provisional_observed_eur": str(report.provisional_observed_eur),
        "settled_eur_recorded": str(report.settled_eur),
        "unknown_attempts": report.unknown_attempts,
        "over_bound_attempts": report.over_bound_attempts,
        "unknown_liability": report.unknown_liability,
        "authoritative_billed_eur": None, "invoice_attested": False,
        "dispatch_authorized": False, "publication_authority": False,
        "data_class": "PRIVATE_SYNTHETIC_ACCOUNTING_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private synthetic accounting readback, not an invoice")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--period", required=True)
    args = parser.parse_args(argv)
    try:
        report = redacted_month_report(args.db, args.period)
    except (sqlite3.Error, OSError, ValueError):
        print("DP514_PRIVATE_MONTH_READ_UNAVAILABLE", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

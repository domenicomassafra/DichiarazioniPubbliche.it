#!/usr/bin/env python3
"""Show which private daily-ingestion stage is actually blocked on this host.

Run on the MiniPC as the authorized database user; no runtime modification.
Does not print source names, links, transcript text, secret or private IDs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.daily_pipeline_health import (  # noqa: E402
    DAILY_PIPELINE_COUNTS_SQL, classify_daily_pipeline,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    )
    parser.add_argument("--expect-populated", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = PsqlRuntime(database_url=args.database_url).run(DAILY_PIPELINE_COUNTS_SQL).splitlines()
        if len(rows) != 1:
            raise ValueError("DAILY_PIPELINE_QUERY_ROW_COUNT_INVALID")
        report = classify_daily_pipeline(json.loads(rows[0]), today=date.today())
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        # DB exceptions may include sensitive schema/identifiers; only surface
        # a bounded machine code, never raw stderr/DSN or SQL.
        print(json.dumps({
            "state": "BLOCKED_READBACK_UNAVAILABLE",
            "publication_authority": False,
            "private_only": True,
        }, sort_keys=True))
        return 2
    print(json.dumps(report.as_dict(), sort_keys=True))
    if args.expect_populated and report.reasons:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

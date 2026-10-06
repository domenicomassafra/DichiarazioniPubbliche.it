#!/usr/bin/env python3
"""Fail-closed M7 preflight.

This checker validates the engineering state only. It can report NO-GO or, once
mechanical blockers disappear, PENDING-OWNER. It never returns a launch authorization.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.launch_preflight import repository_launch_preflight  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expect-no-go",
        action="store_true",
        help="succeed only when the repository is correctly still NO-GO",
    )
    args = parser.parse_args()
    result = repository_launch_preflight(ROOT)
    print(
        f"launch-preflight disposition={result.disposition} "
        f"blockers={len(result.blockers)} receipt_sha256={result.receipt_sha256}"
    )
    for blocker in result.blockers:
        print(f"  - {blocker}")
    if result.launchable:
        print("FAIL: engineering preflight must never authorize launch", file=sys.stderr)
        return 1
    if args.expect_no_go and result.disposition != "NO-GO":
        print(
            "FAIL: repository no longer reports NO-GO; review M7 evidence and owner authority explicitly",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

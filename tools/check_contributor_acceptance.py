#!/usr/bin/env python3
"""DP-602 — deterministic contributor acceptance, single entry point.

Runs every deterministic, credential-free, PostgreSQL-free repository check and
reports one verdict. This is what a contributor runs before opening a PR, and
what CI runs in the `backend-minimal` and `clean-clone` jobs.

Guarantees:
  * no network data source, no paid provider, no PostgreSQL, no credentials;
  * a pure function of the committed tree, so a clean clone gives the same verdict;
  * fail closed: any sub-check failure is a non-zero exit.

Usage:
    python3 tools/check_contributor_acceptance.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, list[str]]] = [
    ("repository contract (tickets/links/json/templates/hygiene/license)",
     ["python3", "tools/check_repository_contract.py"]),
    ("fixture/data licensing inventory (DP-603)",
     ["python3", "tools/check_licensing_inventory.py", "--check-hashes"]),
    ("licensing inventory freshness (DP-603)",
     ["python3", "tools/generate_fixture_inventory.py", "--check"]),
    ("version/changelog consistency (DP-604)",
     ["python3", "tools/check_version_consistency.py", "--allow-no-release"]),
    ("local issue/label governance contract (DP-606)",
     ["python3", "tools/check_issue_workflow.py"]),
    ("draft public HTTP client contract (DP-607)",
     ["python3", "-m", "unittest", "tests.test_public_http_client", "-v"]),
    ("M7 no-false-launch preflight (DP-702/DP-705)",
     ["python3", "tools/check_launch_preflight.py", "--expect-no-go"]),
    ("DP-223 false-attribution/fabricated-quote release gate",
     ["python3", "-m", "dichiarazioni_pubbliche.false_attribution_benchmark"]),
]


def main() -> int:
    failures: list[str] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "poc")
    for label, cmd in CHECKS:
        print(f"==> {label}")
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        out = (result.stdout or "").rstrip()
        err = (result.stderr or "").rstrip()
        if out:
            print(out)
        if result.returncode != 0:
            if err:
                print(err, file=sys.stderr)
            failures.append(label)
        print()

    if failures:
        print(f"FAIL: contributor acceptance failed ({len(failures)} check(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: contributor acceptance satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

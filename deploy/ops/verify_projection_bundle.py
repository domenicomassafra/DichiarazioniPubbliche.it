#!/usr/bin/env python3
"""Verify a generated public projection bundle is internally consistent.

Stdlib only. This is the cheap, always-runnable half of the DP-502 restore
guarantee: it checks that the served bundle actually matches its own
``dataset_sha256`` and contains nothing the public contract forbids.

It deliberately does *not* need a database, so it can run on the public host
where the operational database is not reachable. The authoritative
backup/restore round trip remains ``deploy/ops/restore_drill.sh``.

Usage:
  deploy/ops/verify_projection_bundle.py BUNDLE_DIR
  deploy/ops/verify_projection_bundle.py BUNDLE_DIR --expect-sha256 SHA

Exit codes: 0 verified, 1 mismatch/violation, 2 could not run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


# Keys the public contract must never carry, regardless of projection version.
FORBIDDEN_KEYS = {
    "raw_text",
    "canonical_text",
    "excerpt",
    "transcript_text",
    "evidence_body",
    "raw_error",
    "last_error",
    "api_key",
    "authorization",
}



def dossier_filename(finding_id: str) -> str:
    """Mirror of public_projection._dossier_filename (sha256 of finding_id, 24 hex).

    Reimplemented rather than imported so this script stays runnable on a
    public host that has no database access and may not have ``poc`` on its
    path. The value is pinned by
    ``tests/test_ops_restore_drill.py::test_bundle_filename_matches_projection``.
    """
    return hashlib.sha256(finding_id.encode()).hexdigest()[:24]


PROJECTION_SERVE_EXTENSIONS = {".json", ".jsonld", ".html"}


def recompute_dataset_sha256(dossiers: list[dict]) -> str:
    """Recompute the digest the same way public_projection.build_public_projection does."""
    canonical = json.dumps(
        dossiers, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def find_forbidden_keys(value: object, path: str = "$") -> list[str]:
    """Recursively locate any contract-forbidden key in the payload."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                found.append(f"{path}.{key}")
            found.extend(find_forbidden_keys(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_forbidden_keys(item, f"{path}[{index}]"))
    return found


def verify(bundle: Path, expect_sha256: str | None) -> tuple[int, list[str]]:
    problems: list[str] = []

    index = bundle / "index.json"
    if not index.is_file():
        return 2, [f"bundle has no index.json: {index}"]
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return 2, [f"index.json unreadable: {exc}"]
    if not isinstance(payload, dict):
        return 2, ["index.json is not a JSON object"]

    recorded = payload.get("dataset_sha256")
    if not isinstance(recorded, str) or len(recorded) != 64:
        problems.append(f"index.json has no valid dataset_sha256: {recorded!r}")
        recorded = None

    dossiers = payload.get("dossiers")
    if not isinstance(dossiers, list):
        problems.append("index.json has no dossiers array")
        dossiers = []

    if recorded and not problems:
        actual = recompute_dataset_sha256(dossiers)
        if actual != recorded:
            problems.append(
                f"dataset_sha256 mismatch: recorded={recorded} recomputed={actual}"
            )
        if expect_sha256 and expect_sha256 != recorded:
            problems.append(
                f"dataset_sha256 differs from expected: "
                f"expected={expect_sha256} found={recorded}"
            )

    if payload.get("dossier_count") != len(dossiers):
        problems.append(
            f"dossier_count={payload.get('dossier_count')} but "
            f"{len(dossiers)} dossiers present"
        )

    forbidden = find_forbidden_keys(payload)
    if forbidden:
        problems.append(
            "public bundle carries private keys: " + ", ".join(sorted(forbidden)[:10])
        )

    if payload.get("methodology", {}).get("aggregate_person_score") is not False:
        problems.append("methodology.aggregate_person_score is not explicitly false")

    # Every file under claims/ must correspond to a dossier in the index.
    claims = bundle / "claims"
    if claims.is_dir():
        expected = {
            dossier_filename(str(dossier["finding_id"]))
            for dossier in dossiers
            if isinstance(dossier, dict) and dossier.get("finding_id")
        }
        present = {
            claim_file.stem
            for claim_file in claims.iterdir()
            if claim_file.is_file() and claim_file.suffix in PROJECTION_SERVE_EXTENSIONS
        }
        orphans = present - expected
        if orphans:
            problems.append(
                "stale projection files not in index.json: "
                + ", ".join(sorted(orphans)[:10])
            )

    return (1 if problems else 0), problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a public projection bundle matches its own digest."
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--expect-sha256", default=None)
    args = parser.parse_args(argv)

    code, problems = verify(args.bundle, args.expect_sha256)
    if code == 2:
        print(f"BUNDLE VERIFY: BLOCKED - {problems[0]}", file=sys.stderr)
        return 2
    if code == 1:
        print("BUNDLE VERIFY: FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"BUNDLE VERIFY: OK ({args.bundle})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

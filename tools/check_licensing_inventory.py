#!/usr/bin/env python3
"""DP-603 — fixture/data licensing inventory checker.

Deterministic, stdlib-only, no network, no credentials. Compares tracked
fixture/data/visual assets against the machine-readable inventory and fails closed.

JSON is used rather than YAML so the check has zero third-party dependencies and
runs identically on a contributor's machine and in CI.

Usage:
    python3 tools/check_licensing_inventory.py [--inventory PATH] [--check-hashes]

Exit codes:
    0  inventory is consistent
    1  inventory is inconsistent (a real finding, printed in detail)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "docs" / "licensing" / "fixture-inventory.v1.json"

# Path prefixes / suffixes that constitute a tracked fixture, data, or visual asset.
CANDIDATE_PREFIXES = (
    "data/public/",
    "poc/content/",
    "poc/fixtures/",
    "poc/benchmarks/",
    "research/results/",
    "research/content-audits/",
    "research/source-candidates/",
    "tests/fixtures/",
    "web/src/data/",
    "docs/ux/prototypes-v3/generated/",
    "docs/ux/prototypes-v3/generated-style-02/",
    "docs/ux/reference/",
)
CANDIDATE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".woff", ".woff2", ".ttf", ".otf")

# Binary/asset extensions that must never be tracked (raw/private boundary).
FORBIDDEN_TRACKED_SUFFIXES = (
    ".mp4", ".m4a", ".mp3", ".wav", ".webm", ".mov", ".avi", ".mkv", ".env",
    ".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db", ".dump",
)

REQUIRED_FIELDS = (
    "asset_id", "path_or_locator", "artifact_kind", "origin", "source_reference",
    "retrieved_at", "content_hash", "license_or_terms", "license_evidence",
    "attribution", "modifications", "personal_data", "redistribution_status",
    "public_projection_status", "owner_and_review", "blocker",
)

VALID_KINDS = {"synthetic", "derived", "public-source", "third-party", "owner-local", "reference"}
VALID_REDISTRIBUTION = {"allowed", "private-only", "metadata-only", "blocked", "pending-review"}

# A releasable row must not have UNKNOWN/missing rights evidence.
RELEASABLE_REDISTRIBUTION = {"allowed"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [p for p in out.split("\0") if p]


def is_candidate(path: str) -> bool:
    if path.endswith(CANDIDATE_SUFFIXES):
        return path.startswith(CANDIDATE_PREFIXES) or path.startswith("docs/ux/") or path.startswith("web/")
    return path.startswith(CANDIDATE_PREFIXES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--check-hashes", action="store_true",
                        help="recompute and compare sha256 for every hashed row")
    args = parser.parse_args(argv)

    problems: list[str] = []

    if not args.inventory.is_file():
        print(f"FAIL: inventory file not found: {args.inventory}")
        return 1
    inv = json.loads(args.inventory.read_text(encoding="utf-8"))
    rows = inv.get("assets", [])
    by_id: dict[str, dict] = {}
    by_path: dict[str, dict] = {}

    for row in rows:
        asset_id = row.get("asset_id")
        path = row.get("path_or_locator")
        if asset_id in by_id:
            problems.append(f"duplicate asset_id: {asset_id}")
        by_id[asset_id] = row
        if path in by_path:
            problems.append(f"duplicate path_or_locator: {path}")
        by_path[path] = row

        for field in REQUIRED_FIELDS:
            if field not in row:
                problems.append(f"{asset_id}: missing required field '{field}'")

        kind = row.get("artifact_kind")
        if kind not in VALID_KINDS:
            problems.append(f"{asset_id}: invalid artifact_kind {kind!r}")

        red = row.get("redistribution_status")
        if red not in VALID_REDISTRIBUTION:
            problems.append(f"{asset_id}: invalid redistribution_status {red!r}")

        # Fail closed: a releasable row may not carry UNKNOWN/missing rights.
        if red in RELEASABLE_REDISTRIBUTION:
            lic = str(row.get("license_or_terms", ""))
            ev = str(row.get("license_evidence", ""))
            if not lic or lic.upper() in {"UNKNOWN", "TBD", "NONE"}:
                problems.append(f"{asset_id}: redistribution=allowed but license_or_terms is UNKNOWN")
            if not ev or ev.upper() in {"UNKNOWN", "TBD", "NONE"}:
                problems.append(f"{asset_id}: redistribution=allowed but license_evidence is missing")
            if not row.get("retrieved_at"):
                problems.append(f"{asset_id}: redistribution=allowed but retrieved_at is missing")

        # owner-local material must not be committable.
        if kind == "owner-local" and red in RELEASABLE_REDISTRIBUTION:
            problems.append(f"{asset_id}: owner-local artifact cannot be redistribution=allowed")

    # Cross-check: every tracked candidate must have a row; every hashed path must exist.
    for path in tracked_files():
        if path.endswith(FORBIDDEN_TRACKED_SUFFIXES):
            problems.append(f"forbidden tracked file (raw/private/credential class): {path}")
        if is_candidate(path) and path.endswith("/README.md"):
            continue  # directory READMEs are policy, not assets
        if is_candidate(path) and path not in by_path:
            problems.append(f"tracked candidate asset has no inventory row: {path}")

    for row in rows:
        if row.get("artifact_kind") == "owner-local":
            continue  # recorded by hash/locator, not expected in-tree
        path = row.get("path_or_locator", "")
        if path.startswith("http") or not path:
            continue
        disk = ROOT / path
        if not disk.is_file():
            problems.append(f"{row.get('asset_id')}: path does not exist in tree: {path}")

    # Optional hash verification.
    if args.check_hashes:
        for row in rows:
            path = row.get("path_or_locator", "")
            expected = row.get("content_hash", "")
            if not expected or expected.upper() in {"UNKNOWN", "TBD"}:
                continue
            if path.startswith("http") or not path:
                continue
            if row.get("artifact_kind") == "owner-local":
                continue
            disk = ROOT / path
            if disk.is_file():
                actual = sha256(disk)
                if actual != expected:
                    problems.append(
                        f"{row.get('asset_id')}: content_hash mismatch for {path} "
                        f"(expected {expected[:12]}…, got {actual[:12]}…)"
                    )

    if problems:
        print(f"FAIL: licensing inventory inconsistent ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"OK: licensing inventory consistent — {len(rows)} asset row(s), "
          f"{len(tracked_files())} tracked file(s) scanned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

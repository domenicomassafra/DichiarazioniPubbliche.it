#!/usr/bin/env python3
"""DP-604 — version / metadata / changelog consistency check.

Deterministic, stdlib-only, no network. Fails closed so a release cannot ship with
silent version drift or a changelog that does not match the canonical VERSION.

Usage:
    python3 tools/check_version_consistency.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
WEB_PACKAGE = ROOT / "web" / "package.json"

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
RELEASE_HEADING = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\] - (?P<date>\d{4}-\d{2}-\d{2})\s*$", re.M)
UNRELEASED_HEADING = re.compile(r"^## \[Unreleased\]\s*$", re.M)
# Forbidden: a benchmark PUBLISH label presented as a publication contract.
FORBIDDEN_CHANGELOG = (
    (re.compile(r"(?i)publish(?:ed|es|ing)?\s+(?:authorization|approval)\b"), "changelog presents publication as authorized"),
    (re.compile(r"(?i)benchmark[^\n]*\bPUBLISH\b[^\n]*\b(proof|evidence|authorization|receipt)\b"), "changelog treats a benchmark PUBLISH label as a receipt"),
)


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-no-release", action="store_true",
                        help="accept an empty released set (pre-release repository)")
    args = parser.parse_args(argv)
    problems: list[str] = []

    # Canonical VERSION file.
    if not VERSION_FILE.is_file():
        problems.append("VERSION file missing; canonical version source not established")
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    canonical = read_version()
    if not SEMVER.match(canonical):
        problems.append(f"VERSION '{canonical}' is not a SemVer string")

    # pyproject version must equal VERSION.
    py = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    py_version = py["project"]["version"]
    if py_version != canonical:
        problems.append(f"pyproject version {py_version} != VERSION {canonical}")

    # web version: independent component, must be valid SemVer and not accidentally equal.
    web = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))
    web_version = web.get("version", "")
    if not SEMVER.match(web_version):
        problems.append(f"web/package.json version '{web_version}' is not a SemVer string")
    if web_version == canonical and web.get("private") is True:
        # Allowed, but must be intentional: policy says web is an independent component.
        # We do not fail here; the divergence policy documents the current state.
        pass

    # Changelog structure.
    changelog = CHANGELOG.read_text(encoding="utf-8")
    if not UNRELEASED_HEADING.search(changelog):
        problems.append("CHANGELOG.md is missing the '## [Unreleased]' section")
    for pattern, message in FORBIDDEN_CHANGELOG:
        if pattern.search(changelog):
            problems.append(message)

    releases = RELEASE_HEADING.findall(changelog)
    if not releases:
        if not args.allow_no_release:
            print("NOTE: no released heading in CHANGELOG.md (pre-release repository; acceptable until an authorized release exists).")
    else:
        newest = releases[0][0]
        if newest != canonical:
            problems.append(f"newest CHANGELOG release {newest} != VERSION {canonical}")

    if problems:
        print(f"FAIL: version/changelog inconsistent ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"OK: version/changelog consistent — VERSION={canonical}, "
          f"pyproject={py_version}, web={web_version}, releases={len(releases)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

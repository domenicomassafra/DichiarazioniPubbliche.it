#!/usr/bin/env python3
"""DP-603: generate the tracked fixture inventory from curated ROW_DECISIONS.

Unknown assets fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from dp312_gold_fixture_rights import dp312_gold_row
from dp441_screenshot_rights import dp441_screenshot_rows
from dp349_visual_rights import dp349_visual_rows
from dp79_visual_rights import dp79_visual_rows
from fixture_rights import fixture_rows
from corpus_fixture_rights import corpus_fixture_rows
from dp238_bhl_gold_fixture_rights import dp238_bhl_gold_row
from dp420_usability_fixture_rights import dp420_usability_fixture_row
from fixture_inventory_candidates import is_candidate
from web_project_asset_rights import web_project_asset_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "licensing" / "fixture-inventory.v1.json"
SCHEMA_VERSION = "fixture-inventory/v1"
POLICY_VERSION = "DP-603@2026-09-26"

REVIEW_DATE = "2026-09-26"
OWNER = "Dichiarazioni Pubbliche maintainers (owner: repo principal)"

CODE_LICENSE = "Apache-2.0"
FIXTURE_POLICY = "DICHIARAZIONI-PUBBLICHE-FIXTURE-POLICY-1.0"

# Curated asset rights.
ROW_DECISIONS: dict[str, dict] = {
    **web_project_asset_rows(CODE_LICENSE, FIXTURE_POLICY, REVIEW_DATE),
    **dp441_screenshot_rows(FIXTURE_POLICY),
    **dp349_visual_rows(FIXTURE_POLICY),
    **dp79_visual_rows(FIXTURE_POLICY),
    **fixture_rows(FIXTURE_POLICY, REVIEW_DATE, CODE_LICENSE),
    **corpus_fixture_rows(FIXTURE_POLICY, REVIEW_DATE, CODE_LICENSE),
}
ROW_DECISIONS.update(dp312_gold_row(FIXTURE_POLICY) | dp238_bhl_gold_row())
ROW_DECISIONS.update(dp420_usability_fixture_row(CODE_LICENSE))

# Curated visual references with computed hashes.
VISUAL_GENERATED_STYLE3 = "docs/ux/prototypes-v3/generated/style3"
VISUAL_GENERATED_STYLE02 = "docs/ux/prototypes-v3/generated-style-02/png"
VISUAL_REFERENCE = "docs/ux/reference/p6.2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def visual_decision(path: str) -> dict:
    if path.startswith(VISUAL_GENERATED_STYLE3) or path.startswith(VISUAL_GENERATED_STYLE02):
        return dict(
            artifact_kind="reference",
            origin="Dichiarazioni Pubbliche contributors (generated from GPT Image prompt packs in docs/ux/prototypes-v3/)",
            source_reference="generated in-repo; prompt packs at docs/ux/prototypes-v3/*.prompt.md",
            retrieved_at=REVIEW_DATE,
            license_or_terms=CODE_LICENSE,
            license_evidence="LICENSE (project-authored generated visual)",
            attribution="Project-authored generated mockup. Mockup text/verdicts/names are placeholders, not factual content.",
            modifications="Rendered from in-repo design prompt; not a screenshot of any real product.",
            personal_data="none; generated placeholder text",
            redistribution_status="allowed",
            public_projection_status="internal design reference; not a public artifact",
            blocker=None,
        )
    if path.startswith(VISUAL_REFERENCE):
        return dict(
            artifact_kind="reference",
            origin="unknown (imported from a local Downloads folder on 2026-09-23)",
            source_reference="UNKNOWN",
            retrieved_at="2026-09-23",
            license_or_terms="UNKNOWN",
            license_evidence="UNKNOWN",
            attribution="Provenance unknown. Visual reference only; not product authority (docs/ux/reference/p6.2/README.md).",
            modifications="None; imported as a visual reference for composition/density/typography review.",
            personal_data="unknown origin; no content is approved as factual",
            redistribution_status="pending-review",
            public_projection_status="internal design reference; never a public artifact",
            blocker="UNKNOWN origin/license. Owner decision required before redistribution. Consider removing from the tree if not needed.",
        )
    raise KeyError(path)


def build_rows() -> list[dict]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    tracked = [p for p in tracked if p]
    # Include curated new rows before commit without changing Git's index.
    tracked_set = set(tracked)
    tracked.extend(
        path
        for path in ROW_DECISIONS
        if path not in tracked_set and (ROOT / path).is_file()
    )

    rows: list[dict] = []
    covered: set[str] = set()
    uncovered: list[str] = []

    for path in tracked:
        decision = None
        if path in ROW_DECISIONS:
            decision = ROW_DECISIONS[path]
        elif path.startswith(VISUAL_GENERATED_STYLE3) and path.endswith(".png"):
            decision = visual_decision(path)
        elif path.startswith(VISUAL_GENERATED_STYLE02) and path.endswith(".png"):
            decision = visual_decision(path)
        elif path.startswith(VISUAL_REFERENCE) and path.endswith(".png"):
            decision = visual_decision(path)
        if decision is None:
            if is_candidate(path) and not path.endswith("/README.md"):
                uncovered.append(path)
            continue

        disk = ROOT / path
        content_hash = sha256(disk) if disk.is_file() else "UNKNOWN"
        row = {
            "asset_id": _asset_id(path),
            "path_or_locator": path,
            **decision,
            "content_hash": content_hash,
            "owner_and_review": {
                "owner": OWNER,
                "reviewer": OWNER,
                "review_date": decision.get("review_date", REVIEW_DATE),
                "re_review_trigger": (
                    "any change to the artifact hash, source reference, or platform terms; "
                    "and at each release gate"
                ),
            },
        }
        # stable field order for a clean diff
        ordered = {k: row[k] for k in REQUIRED_ORDER}
        rows.append(ordered)
        covered.add(path)

    if uncovered:
        joined = "\n  - ".join(uncovered)
        raise ValueError(
            "tracked candidate asset(s) have no curated ROW_DECISIONS entry:\n  - " + joined
        )

    return sorted(rows, key=lambda r: r["path_or_locator"])


def _asset_id(path: str) -> str:
    return path.replace("/", ":")


REQUIRED_ORDER = [
    "asset_id", "path_or_locator", "artifact_kind", "origin", "source_reference",
    "retrieved_at", "content_hash", "license_or_terms", "license_evidence",
    "attribution", "modifications", "personal_data", "redistribution_status",
    "public_projection_status", "owner_and_review", "blocker",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the on-disk inventory is stale")
    args = parser.parse_args(argv)

    try:
        rows = build_rows()
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    inv = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_by": "tools/generate_fixture_inventory.py",
        "generated_on": date.today().isoformat(),
        "code_license": CODE_LICENSE,
        "note": (
            "Machine-readable fixture/data licensing inventory (DP-603). Rights are curated "
            "human decisions, not inferred from the Apache-2.0 code license. UNKNOWN license "
            "rows are blocked/pending-review and must NOT be shipped in a release or public "
            "projection until owner/legal review. Enforced by tools/check_licensing_inventory.py."
        ),
        "asset_count": len(rows),
        "assets": rows,
    }

    payload = json.dumps(inv, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    if args.check:
        if not OUT.is_file():
            print("FAIL: inventory missing; run tools/generate_fixture_inventory.py")
            return 1
        current = OUT.read_text(encoding="utf-8")
        # generated_on changes daily; ignore it in the staleness comparison.
        import re

        def strip(text: str) -> str:
            return re.sub(r'"generated_on": "[^"]+"', '"generated_on": ""', text)

        if strip(current) != strip(payload):
            print("FAIL: inventory is stale; re-run tools/generate_fixture_inventory.py")
            return 1
        print("OK: inventory is up to date.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload, encoding="utf-8")
    print(f"wrote {OUT} with {len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

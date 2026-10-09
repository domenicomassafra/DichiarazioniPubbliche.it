#!/usr/bin/env python3
"""DP-606 read-only hosted label backup and deterministic rollback proof.

No network call other than a GitHub GET via `gh api`; no POST/PATCH/DELETE,
branch-policy change, issue change, project mutation or token is serialized.
The returned target is a proposed local state, *never* automatically applied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".github" / "labels.v1.json"
REMOTE = "domenicomassafra/DichiarazioniPubbliche.it"
NAME = re.compile(r"^[^\x00-\x1f]{1,50}$")
COLOR = re.compile(r"^[0-9a-fA-F]{6}$")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def labels_by_name(rows: object) -> dict[str, dict[str, str]]:
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError("DP606_HOSTED_LABELS_INVALID")
    normalized: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("DP606_HOSTED_LABEL_INVALID")
        name, color, description = (row.get(k) for k in ("name", "color", "description"))
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("DP606_HOSTED_LABEL_NAME_INVALID")
        if not isinstance(color, str) or not COLOR.fullmatch(color):
            raise ValueError("DP606_HOSTED_LABEL_COLOR_INVALID")
        if description is None:
            description = ""
        if not isinstance(description, str) or len(description) > 256:
            raise ValueError("DP606_HOSTED_LABEL_DESCRIPTION_INVALID")
        if name in normalized:
            raise ValueError("DP606_HOSTED_LABEL_DUPLICATE")
        normalized[name] = {"name": name, "color": color.lower(), "description": description}
    return normalized


def proposed_overlay(hosted: object, manifest: object) -> dict[str, object]:
    existing = labels_by_name(hosted)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "dichiarazioni-pubbliche-labels-v1":
        raise ValueError("DP606_MANIFEST_VERSION_INVALID")
    records = manifest.get("labels")
    if not isinstance(records, list):
        raise ValueError("DP606_MANIFEST_LABELS_INVALID")
    target = {name: dict(row) for name, row in existing.items()}
    proposed: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("DP606_MANIFEST_ENTRY_INVALID")
        if record.get("public_allowed") is False:
            # Never create the private security marker as a public GitHub label.
            continue
        if record.get("public_allowed") is not True:
            raise ValueError("DP606_MANIFEST_PUBLIC_GATE_INVALID")
        checked = labels_by_name([record])
        name = next(iter(checked))
        if name in proposed:
            raise ValueError("DP606_MANIFEST_DUPLICATE")
        proposed.add(name)
        target[name] = checked[name]
    if not proposed:
        raise ValueError("DP606_MANIFEST_EMPTY")
    changes = [
        {"name": name, "action": "create" if name not in existing else "update"}
        for name in sorted(proposed)
        if existing.get(name) != target[name]
    ]
    # No existing label is deleted; any rollback must also restore previously
    # existing descriptions/colors, not just remove newly created names.
    restored = dict(target)
    for name in target.keys() - existing.keys():
        del restored[name]
    for name, original in existing.items():
        restored[name] = original
    if digest(restored) != digest(existing):
        raise RuntimeError("DP606_ROLLBACK_MISMATCH")
    return {
        "contract_version": "dp606-label-rollback-v1",
        "remote_mutation_performed": False,
        "before_sha256": digest(existing),
        "proposed_sha256": digest(target),
        "rollback_sha256": digest(restored),
        "manifest_sha256": digest(manifest),
        "before_count": len(existing),
        "after_count": len(target),
        "change_count": len(changes),
        "changes": changes,
        "rollback_matches_before": True,
        "hosted_projects_and_protection": "NOT_VERIFIED_BY_LABEL_BACKUP",
    }


def _gh_get(uri: str) -> object:
    proc = subprocess.run(
        ["gh", "api", uri], capture_output=True, text=True, check=False, timeout=20,
    )
    if proc.returncode:
        raise RuntimeError("DP606_GITHUB_READ_UNAVAILABLE")
    try:
        return json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError("DP606_GITHUB_RESULT_INVALID") from None


def capture_public_labels() -> list[dict[str, str]]:
    all_rows: list[dict[str, Any]] = []
    for page in range(1, 21):
        rows = _gh_get(f"repos/{REMOTE}/labels?per_page=100&page={page}")
        if not isinstance(rows, list):
            raise RuntimeError("DP606_GITHUB_LABEL_LIST_INVALID")
        all_rows.extend(rows)
        if len(rows) < 100:
            return list(labels_by_name(all_rows).values())
    raise RuntimeError("DP606_GITHUB_LABEL_PAGE_LIMIT")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only DP-606 label backup and rollback dry-run")
    parser.add_argument("--capture-live", action="store_true")
    parser.add_argument("--snapshot-file", type=Path)
    parser.add_argument("--output-snapshot", type=Path)
    args = parser.parse_args()
    if args.capture_live == bool(args.snapshot_file):
        parser.error("Choose exactly one of --capture-live or --snapshot-file")
    if bool(args.output_snapshot) != args.capture_live:
        parser.error("--output-snapshot is required only with --capture-live")
    if args.capture_live:
        rows = capture_public_labels()
        payload = canonical({"remote": REMOTE, "labels": rows}) + b"\n"
        # Never overwrite a previous hosted baseline; owner-readable only.
        fd = os.open(args.output_snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(payload)
    else:
        snapshot = json.loads(args.snapshot_file.read_text(encoding="utf8"))
        if not isinstance(snapshot, dict) or snapshot.get("remote") != REMOTE:
            raise ValueError("DP606_REMOTE_MISMATCH")
        rows = snapshot.get("labels")
    manifest = json.loads(MANIFEST.read_text(encoding="utf8"))
    receipt = proposed_overlay(rows, manifest)
    receipt["remote"] = REMOTE
    print(canonical(receipt).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

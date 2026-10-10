#!/usr/bin/env python3
"""DP-606: capture GitHub rules/branch/project governance WITHOUT mutation.

The snapshot may contain repository governance metadata, so it is owner-only,
must live outside the checkout, and is never an authorization to apply changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

REMOTE = "domenicomassafra/DichiarazioniPubbliche.it"
ROOT = Path(__file__).resolve().parents[1]
PROJECT_QUERY = (
    'query { repository(owner:"domenicomassafra",name:"DichiarazioniPubbliche.it") '
    '{ projectsV2(first:1) { totalCount } } }'
)


def _gh_json(arguments: list[str], *, allow_404: bool = False) -> Any:
    # Fixed arguments only, no shell or echo of API responses/errors containing
    # potentially sensitive project names or token permission details.
    process = subprocess.run(
        ["gh", "api", *arguments], capture_output=True, text=True,
        timeout=25, check=False,
    )
    if process.returncode:
        if allow_404 and "HTTP 404" in process.stderr:
            return None
        if arguments and arguments[0] == "graphql" and (
            "read:project" in process.stderr or "INSUFFICIENT_SCOPES" in process.stderr
        ):
            raise RuntimeError("DP606_PROJECT_SCOPE_MISSING")
        raise RuntimeError("DP606_HOSTED_READ_FAILED")
    try:
        return json.loads(process.stdout)
    except ValueError:
        raise RuntimeError("DP606_HOSTED_JSON_INVALID") from None


def capture_governance() -> dict[str, Any]:
    repo = _gh_json([f"repos/{REMOTE}"])
    if (
        not isinstance(repo, dict) or repo.get("full_name") != REMOTE
        or repo.get("default_branch") != "main"
        or repo.get("visibility") not in ("public", "private", "internal")
    ):
        raise ValueError("DP606_REMOTE_IDENTITY_OR_BRANCH_DRIFT")
    rulesets = _gh_json([f"repos/{REMOTE}/rulesets?per_page=100"])
    if not isinstance(rulesets, list) or len(rulesets) >= 100:
        raise ValueError("DP606_RULESET_LIST_UNBOUNDED")
    ids: set[int] = set()
    rules: list[dict[str, Any]] = []
    for rule in rulesets:
        rule_id = rule.get("id") if isinstance(rule, dict) else None
        if not isinstance(rule_id, int) or isinstance(rule_id, bool) or rule_id <= 0 or rule_id in ids:
            raise ValueError("DP606_RULESET_ID_INVALID")
        ids.add(rule_id)
        # Retrieve full rule bodies so an owner can review future rollback;
        # the summary list alone is insufficient to reconstruct a ruleset.
        full = _gh_json([f"repos/{REMOTE}/rulesets/{rule_id}"])
        if not isinstance(full, dict) or full.get("id") != rule_id:
            raise ValueError("DP606_RULESET_READ_INCONSISTENT")
        rules.append(full)
    rules.sort(key=lambda rule: rule["id"])

    protection = _gh_json([f"repos/{REMOTE}/branches/main/protection"], allow_404=True)
    if protection is not None and not isinstance(protection, dict):
        raise ValueError("DP606_BRANCH_PROTECTION_INVALID")

    project_status = "UNVERIFIED_PROJECT_READ_FAILED"
    project_count = None
    # A missing read:project grant is not equivalent to zero projects. Fail
    # closed on this scope while still preserving the verified branch snapshot.
    try:
        projects = _gh_json(["graphql", "-f", f"query={PROJECT_QUERY}"])
        if isinstance(projects, dict) and projects.get("errors") and any(
            error.get("type") == "INSUFFICIENT_SCOPES"
            for error in projects["errors"] if isinstance(error, dict)
        ):
            raise RuntimeError("DP606_PROJECT_SCOPE_MISSING")
        if not isinstance(projects, dict) or projects.get("errors"):
            raise ValueError("DP606_PROJECT_READ_UNAVAILABLE")
        project_count = projects["data"]["repository"]["projectsV2"]["totalCount"]
        if not isinstance(project_count, int) or isinstance(project_count, bool) or project_count < 0:
            raise ValueError("DP606_PROJECT_COUNT_INVALID")
        project_status = "EMPTY" if project_count == 0 else "NEEDS_SEPARATE_PROJECT_EXPORT"
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        if str(exc) == "DP606_PROJECT_SCOPE_MISSING":
            project_status = "UNVERIFIED_MISSING_READ_PROJECT_SCOPE"

    return {
        "contract": "dp606-hosted-governance-backup-v1",
        "remote": REMOTE,
        "branch": "main",
        "visibility": repo["visibility"],
        "hosted_mutation_performed": False,
        "protection": {"status": "ABSENT" if protection is None else "PRESENT", "data": protection},
        "rulesets": rules,
        "projects": {"status": project_status, "count": project_count},
        "governance_export_complete": project_status == "EMPTY",
        "rollback_executed": False,
        "owner_review_required": True,
    }


def write_private_snapshot(destination: Path, payload: dict[str, Any]) -> str:
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError("DP606_PRIVATE_SNAPSHOT_OUTSIDE_REPO_REQUIRED")
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    # O_EXCL prevents accidental replacement of a prior live governance receipt.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only hosted governance snapshot for DP-606")
    parser.add_argument("--output-snapshot", type=Path, required=True)
    args = parser.parse_args()
    data = capture_governance()
    digest = write_private_snapshot(args.output_snapshot, data)
    # Never print actual hosted rule bodies, owner metadata or credential details.
    print(json.dumps({
        "remote": REMOTE,
        "backup_sha256": digest,
        "protection": data["protection"]["status"],
        "ruleset_count": len(data["rulesets"]),
        "projects": data["projects"]["status"],
        "governance_export_complete": data["governance_export_complete"],
        "hosted_mutation_performed": False,
        "rollback_executed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

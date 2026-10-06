#!/usr/bin/env python3
"""DP-606 local issue/label governance validator.

Pure repository check: no GitHub API, credentials, network, issues, labels or project
mutations. Repo-local tickets remain authoritative while hosted synchronization is
unconfigured.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = ROOT / ".github" / "labels.v1.json"
POLICY_PATH = ROOT / ".github" / "triage-policy.v1.json"
TICKETS = ROOT / "docs" / "tickets"
DP_ID = re.compile(r"^DP-(\d{3})$")
DP_TITLE = re.compile(r"^(DP-\d{3}):\s+.+")
FORBIDDEN_BODY_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\b(?:raw transcript|private evidence|reviewer note)\s*:\s*\S+"),
)


@dataclass(frozen=True)
class MockIssue:
    title: str
    ticket_id: str
    body: str
    labels: tuple[str, ...]
    security_report: bool = False


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top level must be an object")
    return value


def _ticket_exists(ticket_id: str) -> bool:
    return any(path.name.startswith(f"{ticket_id}-") for path in TICKETS.glob("DP-*.md"))


def validate_manifest() -> list[str]:
    problems: list[str] = []
    manifest = _load(LABELS_PATH)
    if manifest.get("schema_version") != "dichiarazioni-pubbliche-labels-v1":
        problems.append("labels: unsupported schema_version")
    groups = manifest.get("groups")
    labels = manifest.get("labels")
    transitions = manifest.get("state_transitions")
    if not isinstance(groups, dict) or not isinstance(labels, list) or not isinstance(transitions, dict):
        return problems + ["labels: groups/labels/state_transitions shape invalid"]
    ids: set[str] = set()
    names: set[str] = set()
    state_names: set[str] = set()
    for row in labels:
        if not isinstance(row, dict):
            problems.append("labels: label row is not an object")
            continue
        required = {"id", "name", "group", "description", "color", "public_allowed"}
        if set(row) != required:
            problems.append(f"labels: {row.get('id', '<unknown>')} keyset invalid")
            continue
        label_id = str(row["id"])
        name = str(row["name"])
        group = str(row["group"])
        if label_id in ids:
            problems.append(f"labels: duplicate id {label_id}")
        if name in names:
            problems.append(f"labels: duplicate name {name}")
        ids.add(label_id)
        names.add(name)
        if group not in groups:
            problems.append(f"labels: {name} has unknown group {group}")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", str(row["color"])):
            problems.append(f"labels: {name} color invalid")
        if group == "state":
            state_names.add(name)
    if set(transitions) != state_names:
        problems.append("labels: state transition sources do not equal state labels")
    for source, targets in transitions.items():
        if not isinstance(targets, list) or any(target not in state_names for target in targets):
            problems.append(f"labels: transition from {source} has unknown target")
        if source in targets:
            problems.append(f"labels: self-transition not allowed for {source}")
    security = next((row for row in labels if row.get("name") == "security-private"), None)
    if not security or security.get("public_allowed") is not False:
        problems.append("labels: security-private must be public_allowed=false")
    return problems


def validate_policy() -> list[str]:
    problems: list[str] = []
    policy = _load(POLICY_PATH)
    if policy.get("schema_version") != "dichiarazioni-pubbliche-triage-v1":
        problems.append("triage: unsupported schema_version")
    if policy.get("canonical_backlog") != "PLAN.md" or policy.get("ticket_directory") != "docs/tickets":
        problems.append("triage: repo-local backlog authority changed")
    if policy.get("security_path") != "SECURITY.md":
        problems.append("triage: private security path must be SECURITY.md")
    if policy.get("remote_mutation_enabled") is not False:
        problems.append("triage: remote mutation must remain disabled in local manifest")
    allowed = set(policy.get("allowed_automation_actions") or [])
    forbidden = set(policy.get("forbidden_automation_actions") or [])
    human = set(policy.get("human_only_actions") or [])
    if allowed & forbidden or allowed & human:
        problems.append("triage: automation action sets overlap")
    must_forbid = {
        "auto-close", "auto-merge", "auto-publish", "auto-approve-evidence",
        "auto-approve-finding", "set-legal-status", "set-rights-approved",
        "fetch-issue-url", "copy-private-security-report",
    }
    if not must_forbid <= forbidden:
        problems.append("triage: forbidden automation boundary incomplete")
    return problems


def validate_templates() -> list[str]:
    problems: list[str] = []
    for name in ("bug_report.yml", "feature_request.yml"):
        text = (ROOT / ".github" / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8")
        if 'title: "DP-###:' not in text:
            problems.append(f"templates: {name} must scaffold the DP-### title prefix")
        if "id: ticket" not in text or "required: true" not in text:
            problems.append(f"templates: {name} must require ticket linkage")
        if "SECURITY.md" not in text:
            problems.append(f"templates: {name} must direct security reports to SECURITY.md")
        if "private/raw" not in text and "private raw" not in text:
            problems.append(f"templates: {name} lacks private-data warning")
    config = (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    if "blank_issues_enabled: false" not in config:
        problems.append("templates: blank issues must stay disabled")
    pr = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    if "DP-###" not in pr or "No raw/private" not in pr:
        problems.append("templates: PR template governance contract incomplete")
    return problems


def _label_map() -> tuple[dict[str, dict], dict[str, dict]]:
    manifest = _load(LABELS_PATH)
    rows = manifest["labels"]
    return ({str(row["name"]): row for row in rows}, manifest["groups"])


def validate_mock_issue(issue: MockIssue) -> tuple[str, ...]:
    problems: list[str] = []
    title_match = DP_TITLE.match(issue.title.strip())
    if not title_match:
        problems.append("ISSUE_TITLE_TICKET_PREFIX_REQUIRED")
    ticket_id = issue.ticket_id.strip()
    if not DP_ID.fullmatch(ticket_id) or not _ticket_exists(ticket_id):
        problems.append("ISSUE_TICKET_LINK_INVALID")
    elif title_match and title_match.group(1) != ticket_id:
        problems.append("ISSUE_TITLE_TICKET_MISMATCH")
    if issue.security_report:
        problems.append("SECURITY_REPORT_MUST_USE_PRIVATE_PATH")
    if any(pattern.search(issue.body) for pattern in FORBIDDEN_BODY_PATTERNS):
        problems.append("ISSUE_BODY_PRIVATE_OR_SECRET_SHAPED")
    labels, groups = _label_map()
    seen_groups: dict[str, list[str]] = {}
    for label in issue.labels:
        row = labels.get(label)
        if row is None:
            problems.append(f"ISSUE_LABEL_UNKNOWN:{label}")
            continue
        if row["public_allowed"] is not True:
            problems.append(f"ISSUE_LABEL_NOT_PUBLIC:{label}")
        seen_groups.setdefault(str(row["group"]), []).append(label)
    for group, names in seen_groups.items():
        if groups[group].get("mutually_exclusive") is True and len(names) > 1:
            problems.append(f"ISSUE_LABEL_GROUP_CONFLICT:{group}")
    return tuple(problems)


def validate_state_transition(source: str, target: str) -> tuple[str, ...]:
    manifest = _load(LABELS_PATH)
    transitions = manifest["state_transitions"]
    if source not in transitions:
        return ("STATE_SOURCE_UNKNOWN",)
    if target not in transitions:
        return ("STATE_TARGET_UNKNOWN",)
    if target not in transitions[source]:
        return ("STATE_TRANSITION_FORBIDDEN",)
    return ()


def self_test() -> list[str]:
    problems: list[str] = []
    valid = MockIssue(
        title="DP-606: validate local issue workflow",
        ticket_id="DP-606",
        body="Sanitized local workflow fixture.",
        labels=("maintenance", "needs-triage", "release", "no-auto-publication"),
    )
    if validate_mock_issue(valid):
        problems.append("mock: valid issue rejected")
    cases: Iterable[tuple[MockIssue, str]] = (
        (MockIssue("bug: no ticket", "DP-606", "safe", ("bug",)), "ISSUE_TITLE_TICKET_PREFIX_REQUIRED"),
        (MockIssue("DP-999: bad", "DP-999", "safe", ("bug",)), "ISSUE_TICKET_LINK_INVALID"),
        (MockIssue("DP-606: mismatch", "DP-605", "safe", ("bug",)), "ISSUE_TITLE_TICKET_MISMATCH"),
        (MockIssue("DP-606: security", "DP-606", "safe", ("security-private",), True), "SECURITY_REPORT_MUST_USE_PRIVATE_PATH"),
        (MockIssue("DP-606: conflict", "DP-606", "safe", ("ready", "blocked")), "ISSUE_LABEL_GROUP_CONFLICT:state"),
        (MockIssue("DP-606: secret", "DP-606", "raw transcript: secret", ("bug",)), "ISSUE_BODY_PRIVATE_OR_SECRET_SHAPED"),
    )
    for issue, expected in cases:
        if expected not in validate_mock_issue(issue):
            problems.append(f"mock: expected rejection missing: {expected}")
    if validate_state_transition("needs-triage", "ready"):
        problems.append("mock: valid transition rejected")
    if "STATE_TRANSITION_FORBIDDEN" not in validate_state_transition("closed", "ready"):
        problems.append("mock: closed transition unexpectedly allowed")
    return problems


def main() -> int:
    problems = validate_manifest() + validate_policy() + validate_templates() + self_test()
    if problems:
        print(f"FAIL: issue workflow contract violated ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("OK: DP-606 local issue/label workflow contract satisfied (remote mutation disabled).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

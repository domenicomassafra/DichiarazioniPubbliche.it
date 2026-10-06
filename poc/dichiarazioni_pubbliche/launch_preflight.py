from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


LAUNCH_PREFLIGHT_VERSION = "launch-preflight-v1"

_PLAN_ROW = re.compile(r"^\| (DP-\d{3}) \| ([^|]+) \|", re.MULTILINE)
_LEGAL_ROW = re.compile(
    r"^\| (Q-306-\d{2})(?: \([^|]+\))? \|.*?\| `(OPEN|BLOCKED|DECIDED)` \|",
    re.MULTILINE,
)


REQUIRED_TICKETS: tuple[str, ...] = tuple(
    dict.fromkeys(
        [
            "DP-105",
            *[f"DP-{number}" for number in range(201, 208)],
            *[f"DP-{number}" for number in range(215, 225)],
            *[f"DP-{number}" for number in range(301, 311)],
            *[f"DP-{number}" for number in range(401, 411)],
            *[f"DP-{number}" for number in range(501, 507)],
            "DP-510",
            "DP-511",
            *[f"DP-{number}" for number in range(601, 606)],
            *[f"DP-{number}" for number in range(701, 705)],
        ]
    )
)

CONDITIONAL_SURFACE_TICKETS = ("DP-507", "DP-508")

REQUIRED_RELEASE_ARTIFACTS: Mapping[str, str] = {
    "prelaunch_closure": "docs/release/prelaunch-closure-v1.json",
    "launch_set": "docs/release/launch-set-v1.json",
    "launch_rehearsal": "docs/release/launch-rehearsal-v1.json",
    "release_authority": "docs/release/release-authority-v1.json",
}


@dataclass(frozen=True)
class LaunchPreflightResult:
    disposition: str
    blockers: tuple[str, ...]
    ticket_statuses: Mapping[str, str]
    legal_statuses: Mapping[str, str]
    missing_artifacts: tuple[str, ...]
    receipt_sha256: str
    version: str = LAUNCH_PREFLIGHT_VERSION

    @property
    def launchable(self) -> bool:
        # Engineering preflight never has authority to launch. If all mechanical
        # blockers disappear it can only hand off to the explicitly authorized owner.
        return False


def parse_plan_statuses(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for ticket_id, status in _PLAN_ROW.findall(text):
        normalized = " ".join(status.strip().upper().replace("_", " ").split())
        if ticket_id in statuses and statuses[ticket_id] != normalized:
            raise ValueError(f"LAUNCH_PLAN_DUPLICATE_STATUS:{ticket_id}")
        statuses[ticket_id] = normalized
    return statuses


def parse_legal_statuses(text: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for question_id, status in _LEGAL_ROW.findall(text):
        if question_id in statuses and statuses[question_id] != status:
            raise ValueError(f"LAUNCH_LEGAL_DUPLICATE_STATUS:{question_id}")
        statuses[question_id] = status
    return statuses


def evaluate_launch_preflight(
    *,
    plan_statuses: Mapping[str, str],
    legal_statuses: Mapping[str, str],
    artifact_presence: Mapping[str, bool],
    conditional_surface_decisions: Mapping[str, str] | None = None,
) -> LaunchPreflightResult:
    blockers: list[str] = []
    ticket_snapshot: dict[str, str] = {}

    for ticket_id in REQUIRED_TICKETS:
        status = str(plan_statuses.get(ticket_id, "MISSING")).strip().upper()
        ticket_snapshot[ticket_id] = status
        if status != "DONE":
            blockers.append(f"TICKET_NOT_DONE:{ticket_id}:{status}")

    decisions = conditional_surface_decisions or {}
    for ticket_id in CONDITIONAL_SURFACE_TICKETS:
        status = str(plan_statuses.get(ticket_id, "MISSING")).strip().upper()
        ticket_snapshot[ticket_id] = status
        decision = str(decisions.get(ticket_id, "UNDECIDED")).strip().upper()
        if status == "DONE":
            continue
        if decision != "NOT_APPLICABLE":
            blockers.append(f"CONDITIONAL_SURFACE_UNDECIDED:{ticket_id}:{status}")

    legal_snapshot = dict(sorted((str(k), str(v).upper()) for k, v in legal_statuses.items()))
    if not legal_snapshot:
        blockers.append("LEGAL_DECISION_REGISTER_EMPTY")
    for question_id, status in legal_snapshot.items():
        if status != "DECIDED":
            blockers.append(f"LEGAL_DECISION_NOT_CLOSED:{question_id}:{status}")

    missing_artifacts = tuple(
        sorted(name for name in REQUIRED_RELEASE_ARTIFACTS if not artifact_presence.get(name, False))
    )
    blockers.extend(f"RELEASE_ARTIFACT_MISSING:{name}" for name in missing_artifacts)

    canonical_blockers = tuple(sorted(set(blockers)))
    disposition = "NO-GO" if canonical_blockers else "PENDING-OWNER"
    receipt_payload = {
        "version": LAUNCH_PREFLIGHT_VERSION,
        "disposition": disposition,
        "blockers": list(canonical_blockers),
        "ticket_statuses": dict(sorted(ticket_snapshot.items())),
        "legal_statuses": legal_snapshot,
        "missing_artifacts": list(missing_artifacts),
    }
    receipt_sha256 = hashlib.sha256(
        json.dumps(
            receipt_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return LaunchPreflightResult(
        disposition=disposition,
        blockers=canonical_blockers,
        ticket_statuses=dict(sorted(ticket_snapshot.items())),
        legal_statuses=legal_snapshot,
        missing_artifacts=missing_artifacts,
        receipt_sha256=receipt_sha256,
    )


def repository_launch_preflight(root: Path) -> LaunchPreflightResult:
    root = Path(root)
    plan = parse_plan_statuses((root / "PLAN.md").read_text(encoding="utf-8"))
    legal = parse_legal_statuses(
        (root / "docs" / "policy" / "legal-closure-register.md").read_text(encoding="utf-8")
    )
    artifact_presence = {
        name: (root / relative_path).is_file()
        for name, relative_path in REQUIRED_RELEASE_ARTIFACTS.items()
    }
    conditional_decisions_path = root / "docs" / "release" / "conditional-surfaces-v1.json"
    conditional_decisions: dict[str, str] = {}
    if conditional_decisions_path.is_file():
        parsed = json.loads(conditional_decisions_path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("LAUNCH_CONDITIONAL_SURFACE_FILE_INVALID")
        raw = parsed.get("decisions")
        if not isinstance(raw, dict):
            raise ValueError("LAUNCH_CONDITIONAL_SURFACE_DECISIONS_INVALID")
        conditional_decisions = {str(key): str(value) for key, value in raw.items()}
    return evaluate_launch_preflight(
        plan_statuses=plan,
        legal_statuses=legal,
        artifact_presence=artifact_presence,
        conditional_surface_decisions=conditional_decisions,
    )


__all__ = [
    "CONDITIONAL_SURFACE_TICKETS",
    "LAUNCH_PREFLIGHT_VERSION",
    "LaunchPreflightResult",
    "REQUIRED_RELEASE_ARTIFACTS",
    "REQUIRED_TICKETS",
    "evaluate_launch_preflight",
    "parse_legal_statuses",
    "parse_plan_statuses",
    "repository_launch_preflight",
]

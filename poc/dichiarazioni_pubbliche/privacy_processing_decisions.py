"""DP-304: auditable, fail-closed processing decisions for each release data family.

The field inventory classifies technical fields; it cannot supply a GDPR basis,
approve a retention schedule, or attest that operator and processor controls exist.
This separate register makes those missing decisions explicit at release preflight.
No decision here alone grants publication or account activation.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping


PROCESSING_DECISIONS_VERSION = "privacy-processing-decisions-v1"
PROCESSING_FAMILIES: Mapping[str, str] = {
    "PUBLIC_STATEMENTS": "REVIEWED_PUBLIC_ROLE_STATEMENTS_AND_FINDINGS",
    "SOURCE_COPIES": "PRIVATE_SOURCE_CAPTURE_AND_EVIDENCE_PROVENANCE",
    "PERSON_IDENTITIES": "BOUNDED_PUBLIC_ROLE_ATTRIBUTION",
    "RIGHTS_REQUESTS": "PRIVATE_ACCESS_CORRECTION_RESTRICTION_AND_DELETION_CASES",
    "OPERATIONAL_LOGS": "PRIVATE_SECURITY_AND_SERVICE_DIAGNOSTICS",
    "BACKUPS": "PRIVATE_INTEGRITY_AND_DISASTER_RECOVERY",
    "OPTIONAL_ACCOUNTS": "OPTIONAL_PRIVATE_READER_OIDC_MEMBERSHIP",
}
_BASIS_CODES = frozenset(f"GDPR_ART_6_1_{letter}" for letter in "ABCDEF")
_DECISION_FIELDS = frozenset({
    "purpose", "status", "lawful_basis", "necessity_receipt",
    "notice_receipt", "retention_receipt", "access_receipt",
    "owner_decision_url", "owner_decision_date",
    "independent_review_model", "independent_review_receipt",
    "independent_review_sha", "independent_review_outcome",
})
_EVIDENCE_FIELDS = (
    "necessity_receipt", "notice_receipt", "retention_receipt", "access_receipt",
    "owner_decision_url",
)
_RECEIPT_URL = re.compile(
    r"https://github\.com/domenicomassafra/"
    r"DichiarazioniPubbliche\.it/issues/[1-9]\d*#issuecomment-[1-9]\d*\Z"
)
_REVIEWED_SHA = re.compile(r"[0-9a-f]{40}\Z")
_INDEPENDENT_REVIEWER = "SOL_6_1_HIGH_PI_AGENT"
_SPECIAL_EXCLUSIONS = {
    "special_category": "EXCLUDE_UNLESS_SEPARATELY_REVIEWED",
    "criminal_allegations": "EXCLUDE_UNLESS_SEPARATELY_REVIEWED",
    "minors_victims": "EXCLUDE_UNLESS_SEPARATELY_REVIEWED",
}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("PRIVACY_REGISTER_DUPLICATE_KEY")
        result[key] = value
    return result


def evaluate_processing_decisions(
    register: Mapping[str, Any],
    *,
    account_activation_approved: bool = False,
) -> tuple[str, ...]:
    """Return bounded release blockers. Partial decisions never grant approval."""
    if not isinstance(register, dict) or set(register) != {
        "version", "families", "special_handling",
    } or register.get("version") != PROCESSING_DECISIONS_VERSION:
        return ("PRIVACY_REGISTER_SCHEMA_INVALID",)
    if register.get("special_handling") != _SPECIAL_EXCLUSIONS:
        return ("PRIVACY_SPECIAL_HANDLING_NOT_FAIL_CLOSED",)
    families = register["families"]
    if not isinstance(families, dict) or set(families) != set(PROCESSING_FAMILIES):
        return ("PRIVACY_FAMILY_COVERAGE_INVALID",)
    blockers: list[str] = []
    for family, purpose in PROCESSING_FAMILIES.items():
        row = families[family]
        if not isinstance(row, dict) or set(row) != _DECISION_FIELDS or row["purpose"] != purpose:
            blockers.append(f"PRIVACY_FAMILY_SCHEMA_INVALID:{family}")
            continue
        status = row["status"]
        if family == "OPTIONAL_ACCOUNTS" and status == "EXCLUDED":
            # The source-owned activation flag must also remain false. Accounts
            # cannot be activated by editing this evidence register.
            if account_activation_approved:
                blockers.append("PRIVACY_EXCLUDED_ACCOUNT_ACTIVATION_CONFLICT")
            continue
        if status != "APPROVED":
            blockers.append(f"PRIVACY_PURPOSE_NOT_APPROVED:{family}")
            continue
        if not isinstance(row["lawful_basis"], str) or row["lawful_basis"] not in _BASIS_CODES:
            blockers.append(f"PRIVACY_LAWFUL_BASIS_MISSING:{family}")
        if any(
            not isinstance(row[key], str)
            or _RECEIPT_URL.fullmatch(row[key]) is None
            for key in _EVIDENCE_FIELDS
        ):
            blockers.append(f"PRIVACY_EVIDENCE_MISSING:{family}")
        if (
            row["independent_review_model"] != _INDEPENDENT_REVIEWER
            or row["independent_review_outcome"] != "APPROVE"
            or not isinstance(row["independent_review_receipt"], str)
            or _RECEIPT_URL.fullmatch(row["independent_review_receipt"]) is None
            or row["independent_review_receipt"] == row["owner_decision_url"]
            or not isinstance(row["independent_review_sha"], str)
            or _REVIEWED_SHA.fullmatch(row["independent_review_sha"]) is None
        ):
            blockers.append(f"PRIVACY_INDEPENDENT_REVIEW_MISSING:{family}")
        stamp = row["owner_decision_date"]
        try:
            if not isinstance(stamp, str) or date.fromisoformat(stamp).isoformat() != stamp:
                raise ValueError("invalid date")
        except ValueError:
            blockers.append(f"PRIVACY_OWNER_DATE_MISSING:{family}")
    return tuple(sorted(blockers))


def repository_processing_decisions(root: Path) -> tuple[str, ...]:
    """Read canonical policy and activation inventory; fail closed on absent input."""
    path = root / "docs/policy/privacy-processing-decisions-v1.json"
    inventory_path = root / "config/privacy-field-inventory.v1.json"
    try:
        register = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        activation = inventory["account_sqlite_activation_approved"]
        if type(activation) is not bool:
            return ("PRIVACY_ACCOUNT_ACTIVATION_STATE_INVALID",)
    except (OSError, ValueError, KeyError, TypeError):
        return ("PRIVACY_PROCESSING_REGISTER_OR_INVENTORY_UNAVAILABLE",)
    return evaluate_processing_decisions(
        register, account_activation_approved=activation,
    )

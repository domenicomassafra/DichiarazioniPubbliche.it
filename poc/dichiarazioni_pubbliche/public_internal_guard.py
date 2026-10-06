from __future__ import annotations

import re
from typing import Any


_INTERNAL_REASON_CODES = frozenset(
    {
        "ALL_ACCEPTED_HIGH_RISK_GATES_PASS",
        "NO_HIGH_RISK_SIGNAL_DETECTED_NOT_A_SAFETY_CERTIFICATION",
    }
)


def _normalized_key(value: object) -> tuple[str, str]:
    raw = str(value or "")
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw)
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", snake).strip("_").lower()
    return snake, snake.replace("_", "")


def _forbidden_key(value: object) -> bool:
    normalized, compact = _normalized_key(value)
    if "high_risk" in normalized or "highrisk" in compact:
        return True
    if normalized in {
        "risk_score",
        "risk_scores",
        "risk_note",
        "risk_notes",
        "risk_reason",
        "risk_reasons",
        "risk_reason_code",
        "risk_reason_codes",
        "private_reason",
        "private_reasons",
        "private_note",
        "private_notes",
        "internal_reason",
        "internal_reasons",
        "internal_note",
        "internal_notes",
        "actor_ref",
        "review_actor_ref",
        "reviewer_actor_ref",
        "reviewer_ref",
        "credential_fingerprint",
        "credential_fingerprints",
        "credential_hash",
        "credential_hashes",
        "credential_id",
        "reviewer_credential_id",
        "secret_hex",
        "mac_sha256",
        "identity_authority_receipt_id",
        "reviewer_identity_receipt_id",
        "identity_authority_binding_sha256",
        "authority_version",
        "reviewer_key_version",
    }:
        return True
    if normalized.endswith("_actor_ref") or normalized.endswith("_reviewer_ref"):
        return True
    if "credential" in normalized and (
        "fingerprint" in normalized or "hash" in normalized
    ):
        return True
    return False


def forbidden_public_internal_paths(value: Any, path: str = "") -> tuple[str, ...]:
    """Locate private high-risk/reviewer/credential material in a public candidate.

    The public projection is intentionally whitelist-based. This guard covers the few
    intentionally open nested maps (for example correction changed-fields) and also
    protects callers that validate a hand-built public dossier directly.
    """

    found: list[str] = []
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            current = f"{path}.{key}" if path else key
            if _forbidden_key(key):
                found.append(current)
                continue
            found.extend(forbidden_public_internal_paths(item, current))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(forbidden_public_internal_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        normalized = value.strip().upper()
        if normalized.startswith("HOLD_HIGH_RISK_") or normalized in _INTERNAL_REASON_CODES:
            found.append(path or "<value>")
    return tuple(found)


__all__ = ["forbidden_public_internal_paths"]

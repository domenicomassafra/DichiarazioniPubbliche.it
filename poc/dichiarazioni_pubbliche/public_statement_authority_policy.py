"""Current, revocable validation rules for v3 public authority evidence."""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from typing import Mapping
from .public_statement_authority_common import (
    _AUTHORITY_KINDS, _SHA256, _digest, _valid_https_url,
    validate_statement_binding,
)

def _authority_event_material(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "statement_id": row["statement_id"],
        "version_id": row["version_id"],
        "authority_kind": row["authority_kind"],
        "event_sequence": row["event_sequence"],
        "previous_event_id": row.get("previous_event_id"),
        "previous_integrity_sha256": row.get("previous_integrity_sha256"),
        "decision_id": row["decision_id"],
        "review_event_id": row["review_event_id"],
        "status": row["status"],
        "binding": row["binding"],
        "payload": row["payload"],
        "review_evidence": row["review_evidence"],
        "reviewer_ref": row["reviewer_ref"],
        "reviewed_at": row["reviewed_at"],
        "expires_at": row.get("expires_at"),
    }


def _valid_authority_chain(rows: list[dict[str, object]]) -> bool:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or type(row.get("event_sequence")) is not int:
            return False
        kind = row.get("authority_kind")
        if kind not in _AUTHORITY_KINDS:
            return False
        try:
            binding = validate_statement_binding(row.get("binding"))
        except (TypeError, ValueError, AttributeError):
            return False
        if (binding["statement_id"] != row.get("statement_id")
                or binding["version_id"] != row.get("version_id")):
            return False
        grouped.setdefault(str(kind), []).append(row)
    for kind_rows in grouped.values():
        previous_id = None
        previous_hash = None
        ordered = sorted(kind_rows, key=lambda item: item.get("event_sequence", 0))
        for expected_sequence, row in enumerate(ordered, start=1):
            integrity = row.get("integrity_sha256")
            if (row.get("event_sequence") != expected_sequence
                    or row.get("previous_event_id") != previous_id
                    or row.get("previous_integrity_sha256") != previous_hash
                    or type(integrity) is not str
                    or _SHA256.fullmatch(integrity) is None
                    or row.get("event_id") != "public-statement-authority:" + integrity
                    or _digest(_authority_event_material(row)) != integrity):
                return False
            previous_id = row["event_id"]
            previous_hash = integrity
    return True


def _validate_approved_payload(
    kind: str, payload: Mapping[str, object], expires_at: str | None,
    *, now: datetime | None = None,
) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("DP468_AUTHORITY_PAYLOAD_INVALID")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("DP468_AUTHORITY_CLOCK_INVALID")
    if expires_at is None:
        raise ValueError("DP468_AUTHORITY_EXPIRY_REQUIRED")
    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expiry.tzinfo is None or expiry <= current or expiry > current + timedelta(days=31):
        raise ValueError("DP468_AUTHORITY_EXPIRY_INVALID")
    if kind == "RIGHTS":
        if (payload.get("use_scope") != "PUBLIC_EXACT_EXCERPT"
                or payload.get("policy_version") != "dp468-public-quote-rights-v1"
                or payload.get("jurisdiction") != "IT"
                or type(payload.get("license_id")) is not str
                or not payload["license_id"].strip()
                or not _valid_https_url(payload.get("terms_url"))
                or _SHA256.fullmatch(str(payload.get("terms_sha256") or "")) is None
                or payload.get("attribution_required") is not True
                or type(payload.get("attribution_text")) is not str
                or not payload["attribution_text"].strip()
                or type(payload.get("source_rights_ref")) is not str
                or not payload["source_rights_ref"].strip()):
            raise ValueError("DP468_PUBLIC_RIGHTS_GRANT_INVALID")
    elif kind == "PRIVACY":
        required = (
            "necessity_ref", "balancing_ref", "notice_receipt", "contact_channel_ref",
            "access_receipt", "retention_policy_version", "purpose",
            "data_minimization_ref",
        )
        special = payload.get("special_category_data")
        if (payload.get("lawful_basis") != "GDPR_ART_6_1_F"
                or type(special) is not bool
                or payload.get("third_party_data_cleared") is not True
                or any(type(payload.get(key)) is not str or not payload[key].strip()
                       for key in required)):
            raise ValueError("DP468_PUBLIC_PRIVACY_DECISION_INVALID")
        if special:
            if (payload.get("special_category_condition") != "GDPR_ART_9_2_E"
                    or payload.get("manifestly_made_public_by_subject") is not True):
                raise ValueError("DP468_PUBLIC_PRIVACY_SPECIAL_CATEGORY_INVALID")
        elif (payload.get("special_category_condition") not in (None, "")
              or payload.get("manifestly_made_public_by_subject") is not False):
            raise ValueError("DP468_PUBLIC_PRIVACY_SPECIAL_CATEGORY_INVALID")
    elif kind == "RETENTION":
        due = payload.get("review_due_at")
        if (payload.get("policy_version") != "dp468-public-statement-retention-v1"
                or payload.get("retention_class") != "PUBLIC_HISTORICAL_STATEMENT"
                or payload.get("source_capture_scope") != "PRIVATE_ONLY"
                or type(payload.get("deletion_trigger")) is not str
                or not payload["deletion_trigger"].strip()
                or type(due) is not str):
            raise ValueError("DP468_PUBLIC_RETENTION_DECISION_INVALID")
        parsed_due = datetime.fromisoformat(due.replace("Z", "+00:00"))
        if (parsed_due.tzinfo is None or parsed_due <= current
                or parsed_due > current + timedelta(days=366)):
            raise ValueError("DP468_PUBLIC_RETENTION_REVIEW_DATE_INVALID")
    elif kind == "ATTRIBUTION":
        if any(type(payload.get(key)) is not str or not payload[key].strip()
               for key in ("speaker_name", "official_person_uri", "public_role_source_url")):
            raise ValueError("DP468_PUBLIC_ATTRIBUTION_INVALID")
        if not _valid_https_url(payload["official_person_uri"]) or not _valid_https_url(payload["public_role_source_url"]):
            raise ValueError("DP468_PUBLIC_ATTRIBUTION_INVALID")
    elif kind == "CONTEXT":
        if (payload.get("speech_act") not in {
                "DIRECT_ASSERTION", "OPINION", "REPORTED_QUOTE", "CRITICISM", "IRONY",
            } or type(payload.get("endorsed")) is not bool
                or type(payload.get("source_session_ref")) is not str
                or not payload["source_session_ref"].strip()):
            raise ValueError("DP468_PUBLIC_CONTEXT_INVALID")
    elif kind == "WORDING":
        if (payload.get("method") != "SOURCE_TEXT_VERIFIED"
                or payload.get("language") != "it"
                or payload.get("source_kind") != "WRITTEN"):
            raise ValueError("DP468_PUBLIC_WORDING_INVALID")
    elif kind == "PUBLICATION":
        if (type(payload.get("automatic_authorization_ref")) is not str
                or not payload["automatic_authorization_ref"].strip()
                or type(payload.get("release_pin_id")) is not str
                or not payload["release_pin_id"].strip()
                or payload.get("readback_required") is not True):
            raise ValueError("DP468_PUBLICATION_DECISION_INVALID")

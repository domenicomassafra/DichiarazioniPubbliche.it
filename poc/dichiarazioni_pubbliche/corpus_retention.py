from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord
from dichiarazioni_pubbliche.policy.privacy_policy import DataClass, RetentionDecision, retention_decision


CAPTURE_LIFECYCLE_VERSION = "capture-lifecycle-v1"


@dataclass(frozen=True)
class CaptureUseDecision:
    allowed: bool
    code: str


@dataclass(frozen=True)
class LocalBodyPurgeReceipt:
    eligible: bool
    deleted: bool
    code: str
    body_ref: str
    content_sha256: str
    bytes_observed: int = 0
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def body_purge_decision(capture: ContentCaptureRecord) -> CaptureUseDecision:
    """DP-118 / DP-304: no period is invented; only explicit EPHEMERAL can purge."""
    if capture.hold_status != "NONE":
        return CaptureUseDecision(False, f"HOLD_ACTIVE:{capture.hold_status}")
    if capture.status == "PURGED_BODY":
        return CaptureUseDecision(False, "ALREADY_PURGED")
    if capture.status == "PURGE_PENDING":
        return CaptureUseDecision(False, "PURGE_ALREADY_PENDING")
    if capture.status != "CAPTURED":
        return CaptureUseDecision(False, f"CAPTURE_STATUS_BLOCKED:{capture.status}")
    decision = retention_decision(
        DataClass.EPHEMERAL if capture.retention_class == "EPHEMERAL" else DataClass.OPERATIONAL_PRIVATE,
        legal_hold_active=False,
        is_ephemeral=capture.retention_class == "EPHEMERAL",
    )
    if decision is not RetentionDecision.EPHEMERAL_PURGE_ELIGIBLE:
        return CaptureUseDecision(False, f"RETENTION_NOT_PURGEABLE:{capture.retention_class}")
    if not capture.body_ref:
        return CaptureUseDecision(False, "BODY_REF_MISSING")
    return CaptureUseDecision(True, "EPHEMERAL_PURGE_ELIGIBLE")


def capture_downstream_use_decision(
    capture: ContentCaptureRecord,
    *,
    requires_body: bool,
) -> CaptureUseDecision:
    """Private research use gate; this is not a public-rights decision."""
    if capture.hold_status != "NONE":
        return CaptureUseDecision(False, f"HOLD_ACTIVE:{capture.hold_status}")
    if capture.status == "QUARANTINED":
        return CaptureUseDecision(False, "CAPTURE_QUARANTINED")
    if capture.status == "PURGE_PENDING":
        return CaptureUseDecision(False, "BODY_PURGE_IN_PROGRESS")
    if requires_body and capture.status == "PURGED_BODY":
        return CaptureUseDecision(False, "BODY_PURGED")
    if requires_body and not capture.body_ref:
        return CaptureUseDecision(False, "BODY_REF_MISSING")
    return CaptureUseDecision(True, "PRIVATE_USE_ALLOWED")


def archive_transition_decision(
    current: str,
    target: str,
    *,
    provider: str | None,
    receipt: Mapping[str, Any] | None = None,
) -> CaptureUseDecision:
    allowed = {
        "NOT_REQUESTED": {"REQUESTED"},
        "REQUESTED": {"PENDING", "SUCCEEDED", "FAILED"},
        "PENDING": {"SUCCEEDED", "FAILED"},
        "FAILED": {"REQUESTED"},
        "SUCCEEDED": set(),
    }
    if current not in allowed or target not in allowed:
        return CaptureUseDecision(False, "ARCHIVE_STATUS_INVALID")
    if target not in allowed[current]:
        return CaptureUseDecision(False, f"ARCHIVE_TRANSITION_INVALID:{current}->{target}")
    if not isinstance(provider, str) or not provider.strip():
        return CaptureUseDecision(False, "ARCHIVE_PROVIDER_REQUIRED")
    if target in {"SUCCEEDED", "FAILED"} and not receipt:
        return CaptureUseDecision(False, "ARCHIVE_COMPLETION_RECEIPT_REQUIRED")
    return CaptureUseDecision(True, "ARCHIVE_TRANSITION_ALLOWED")


def _safe_local_target(storage_root: Path, body_ref: str) -> tuple[Path | None, str | None]:
    root = storage_root.resolve()
    rel = Path(body_ref)
    if rel.is_absolute() or ".." in rel.parts or "://" in body_ref:
        return None, "BODY_REF_NOT_LOCAL_RELATIVE"
    current = root
    for part in rel.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            return None, "BODY_REF_SYMLINK_REFUSED"
    try:
        target = (root / rel).resolve(strict=True)
    except FileNotFoundError:
        return None, "BODY_FILE_MISSING"
    try:
        target.relative_to(root)
    except ValueError:
        return None, "BODY_REF_OUTSIDE_ROOT"
    if not target.is_file() or target.is_symlink():
        return None, "BODY_FILE_INVALID"
    return target, None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def purge_local_capture_body(
    capture: ContentCaptureRecord,
    *,
    storage_root: Path,
    dry_run: bool = True,
) -> LocalBodyPurgeReceipt:
    decision = body_purge_decision(capture)
    body_ref = capture.body_ref or ""
    if not decision.allowed:
        return LocalBodyPurgeReceipt(
            False, False, decision.code, body_ref, capture.content_sha256, dry_run=dry_run
        )
    target, error = _safe_local_target(storage_root, body_ref)
    if target is None:
        return LocalBodyPurgeReceipt(
            False, False, error or "BODY_REF_INVALID", body_ref, capture.content_sha256, dry_run=dry_run
        )
    observed_hash = _sha256_file(target)
    if observed_hash != capture.content_sha256:
        return LocalBodyPurgeReceipt(
            False,
            False,
            "BODY_HASH_MISMATCH",
            body_ref,
            capture.content_sha256,
            bytes_observed=target.stat().st_size,
            dry_run=dry_run,
        )
    size = target.stat().st_size
    if dry_run:
        return LocalBodyPurgeReceipt(
            True, False, "DRY_RUN_ELIGIBLE", body_ref, capture.content_sha256, size, True
        )
    target.unlink()
    return LocalBodyPurgeReceipt(
        True, True, "BODY_DELETED", body_ref, capture.content_sha256, size, False
    )


def lifecycle_event_id(capture_id: str, event_type: str, operation_key: str) -> str:
    for value in (capture_id, event_type, operation_key):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("CAPTURE_LIFECYCLE_ID_INPUT_REQUIRED")
    material = "\x1f".join((capture_id.strip(), event_type.strip(), operation_key.strip()))
    return "capture-event:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def json_param(value: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(value or {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


START_CAPTURE_BODY_PURGE_SQL_V1 = r"""
WITH current AS (
    SELECT id, content_sha256, body_ref, retention_class, hold_status, status
    FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), eligible AS (
    SELECT * FROM current
    WHERE retention_class='EPHEMERAL' AND hold_status='NONE'
      AND status='CAPTURED' AND body_ref IS NOT NULL
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'BODY_PURGE_REQUESTED', :'actor_ref',
           jsonb_build_object('status', status, 'body_ref', body_ref, 'content_sha256', content_sha256),
           jsonb_build_object('status', 'PURGE_PENDING'), :'receipt'::jsonb
    FROM eligible
    ON CONFLICT (id) DO NOTHING
    RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='BODY_PURGE_REQUESTED'
      AND receipt=:'receipt'::jsonb
), updated AS (
    UPDATE content_capture c SET status='PURGE_PENDING'
    WHERE c.id=:'capture_id' AND c.status='CAPTURED'
      AND EXISTS (SELECT 1 FROM event_ok)
    RETURNING c.id
)
SELECT CASE
    WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN (SELECT hold_status FROM current) <> 'NONE' THEN 'HOLD_ACTIVE'
    WHEN (SELECT retention_class FROM current) <> 'EPHEMERAL' THEN 'RETENTION_NOT_EPHEMERAL'
    WHEN (SELECT status FROM current) = 'PURGED_BODY' THEN 'ALREADY_PURGED'
    WHEN (SELECT status FROM current) = 'PURGE_PENDING' AND EXISTS(SELECT 1 FROM event_ok) THEN 'PURGE_READY'
    WHEN (SELECT status FROM current) = 'PURGE_PENDING' THEN 'PURGE_PENDING'
    WHEN (SELECT status FROM current) <> 'CAPTURED' THEN 'CAPTURE_NOT_READY'
    WHEN (SELECT body_ref FROM current) IS NULL THEN 'BODY_REF_MISSING'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'PURGE_READY'
    ELSE 'CONFLICT'
END;
""".strip()


FINALIZE_CAPTURE_BODY_PURGE_SQL_V1 = r"""
WITH current AS (
    SELECT id, content_sha256, body_ref, status, purge_receipt
    FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), eligible AS (
    SELECT * FROM current
    WHERE status='PURGE_PENDING'
      AND body_ref=:'expected_body_ref'
      AND content_sha256=:'expected_sha256'
      AND :'purge_receipt'::jsonb <> '{}'::jsonb
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'BODY_PURGED', :'actor_ref',
           jsonb_build_object('status', status, 'body_ref', body_ref, 'content_sha256', content_sha256),
           jsonb_build_object('status', 'PURGED_BODY', 'body_ref', NULL), :'purge_receipt'::jsonb
    FROM eligible
    ON CONFLICT (id) DO NOTHING
    RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='BODY_PURGED'
      AND receipt=:'purge_receipt'::jsonb
), updated AS (
    UPDATE content_capture c
    SET status='PURGED_BODY', body_ref=NULL, body_purged_at=now(),
        purge_reason=:'purge_reason', purge_receipt=:'purge_receipt'::jsonb
    WHERE c.id=:'capture_id' AND c.status='PURGE_PENDING'
      AND c.body_ref=:'expected_body_ref' AND c.content_sha256=:'expected_sha256'
      AND EXISTS (SELECT 1 FROM event_ok)
    RETURNING c.id
)
SELECT CASE
    WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN :'purge_receipt'::jsonb='{}'::jsonb THEN 'PURGE_RECEIPT_REQUIRED'
    WHEN (SELECT status FROM current)='PURGED_BODY'
         AND (SELECT purge_receipt FROM current)=:'purge_receipt'::jsonb
         AND EXISTS(SELECT 1 FROM event_ok) THEN 'PURGED'
    WHEN (SELECT status FROM current)='PURGED_BODY' THEN 'ALREADY_PURGED'
    WHEN (SELECT status FROM current)<>'PURGE_PENDING' THEN 'PURGE_NOT_PENDING'
    WHEN (SELECT body_ref FROM current)<>:'expected_body_ref' THEN 'BODY_REF_CHANGED'
    WHEN (SELECT content_sha256 FROM current)<>:'expected_sha256' THEN 'BODY_HASH_CHANGED'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'PURGED'
    ELSE 'CONFLICT'
END;
""".strip()


FAIL_CAPTURE_BODY_PURGE_SQL_V1 = r"""
WITH current AS (
    SELECT id, status FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'BODY_PURGE_FAILED', :'actor_ref',
           jsonb_build_object('status', status), jsonb_build_object('status', 'QUARANTINED'),
           :'failure_receipt'::jsonb
    FROM current WHERE status='PURGE_PENDING' AND :'failure_receipt'::jsonb <> '{}'::jsonb
    ON CONFLICT (id) DO NOTHING RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='BODY_PURGE_FAILED'
      AND receipt=:'failure_receipt'::jsonb
), updated AS (
    UPDATE content_capture SET status='QUARANTINED'
    WHERE id=:'capture_id' AND status='PURGE_PENDING'
      AND EXISTS(SELECT 1 FROM event_ok)
    RETURNING id
)
SELECT CASE
    WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN :'failure_receipt'::jsonb='{}'::jsonb THEN 'FAILURE_RECEIPT_REQUIRED'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'QUARANTINED'
    WHEN (SELECT status FROM current)='QUARANTINED' AND EXISTS(SELECT 1 FROM event_ok) THEN 'QUARANTINED'
    ELSE 'CONFLICT'
END;
""".strip()


REQUEST_CAPTURE_ARCHIVE_SQL_V1 = r"""
WITH current AS (
    SELECT id, archive_status, archive_provider FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), eligible AS (
    SELECT * FROM current WHERE archive_status IN ('NOT_REQUESTED','FAILED')
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'ARCHIVE_REQUESTED', :'actor_ref',
           jsonb_build_object('archive_status', archive_status, 'archive_provider', archive_provider),
           jsonb_build_object('archive_status', 'REQUESTED', 'archive_provider', :'archive_provider'),
           :'request_receipt'::jsonb
    FROM eligible WHERE NULLIF(:'archive_provider','') IS NOT NULL
    ON CONFLICT (id) DO NOTHING RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='ARCHIVE_REQUESTED'
), updated AS (
    UPDATE content_capture
    SET archive_status='REQUESTED', archive_provider=:'archive_provider',
        archive_requested_at=now(), archive_completed_at=NULL, archive_receipt='{}'::jsonb
    WHERE id=:'capture_id' AND archive_status IN ('NOT_REQUESTED','FAILED')
      AND EXISTS(SELECT 1 FROM event_ok)
    RETURNING id
)
SELECT CASE
    WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN NULLIF(:'archive_provider','') IS NULL THEN 'ARCHIVE_PROVIDER_REQUIRED'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'ARCHIVE_REQUESTED'
    WHEN (SELECT archive_status FROM current)='REQUESTED'
         AND (SELECT archive_provider FROM current)=:'archive_provider'
         AND EXISTS(SELECT 1 FROM event_ok) THEN 'ARCHIVE_REQUESTED'
    ELSE 'CONFLICT'
END;
""".strip()


MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1 = r"""
WITH current AS (
    SELECT id, archive_status, archive_provider FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'ARCHIVE_PENDING', :'actor_ref',
           jsonb_build_object('archive_status', archive_status),
           jsonb_build_object('archive_status', 'PENDING'), :'receipt'::jsonb
    FROM current
    WHERE archive_status='REQUESTED' AND :'receipt'::jsonb <> '{}'::jsonb
    ON CONFLICT (id) DO NOTHING RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='ARCHIVE_PENDING'
      AND receipt=:'receipt'::jsonb
), updated AS (
    UPDATE content_capture SET archive_status='PENDING'
    WHERE id=:'capture_id' AND archive_status='REQUESTED'
      AND EXISTS(SELECT 1 FROM event_ok)
    RETURNING id
)
SELECT CASE
    WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN :'receipt'::jsonb='{}'::jsonb THEN 'ARCHIVE_PENDING_RECEIPT_REQUIRED'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'PENDING'
    WHEN (SELECT archive_status FROM current)='PENDING' AND EXISTS(SELECT 1 FROM event_ok) THEN 'PENDING'
    ELSE 'CONFLICT'
END;
""".strip()


COMPLETE_CAPTURE_ARCHIVE_SQL_V1 = r"""
WITH current AS (
    SELECT id, archive_status, archive_provider, archive_receipt FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), eligible AS (
    SELECT * FROM current
    WHERE archive_status IN ('REQUESTED','PENDING')
      AND :'outcome' IN ('SUCCEEDED','FAILED')
      AND :'archive_receipt'::jsonb <> '{}'::jsonb
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id,
           CASE WHEN :'outcome'='SUCCEEDED' THEN 'ARCHIVE_SUCCEEDED' ELSE 'ARCHIVE_FAILED' END,
           :'actor_ref', jsonb_build_object('archive_status', archive_status),
           jsonb_build_object('archive_status', :'outcome'), :'archive_receipt'::jsonb
    FROM eligible
    ON CONFLICT (id) DO NOTHING RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id'
      AND event_type=CASE WHEN :'outcome'='SUCCEEDED' THEN 'ARCHIVE_SUCCEEDED' ELSE 'ARCHIVE_FAILED' END
      AND receipt=:'archive_receipt'::jsonb
), updated AS (
    UPDATE content_capture SET archive_status=:'outcome', archive_completed_at=now(),
        archive_receipt=:'archive_receipt'::jsonb
    WHERE id=:'capture_id' AND archive_status IN ('REQUESTED','PENDING')
      AND EXISTS(SELECT 1 FROM event_ok)
    RETURNING id
)
SELECT CASE
    WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN :'outcome' NOT IN ('SUCCEEDED','FAILED') THEN 'ARCHIVE_OUTCOME_INVALID'
    WHEN :'archive_receipt'::jsonb='{}'::jsonb THEN 'ARCHIVE_RECEIPT_REQUIRED'
    WHEN EXISTS(SELECT 1 FROM updated) THEN :'outcome'
    WHEN (SELECT archive_status FROM current)=:'outcome'
         AND (SELECT archive_receipt FROM current)=:'archive_receipt'::jsonb
         AND EXISTS(SELECT 1 FROM event_ok) THEN :'outcome'
    ELSE 'CONFLICT'
END;
""".strip()


SET_CAPTURE_HOLD_SQL_V1 = r"""
WITH current AS (
    SELECT id, hold_status FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'HOLD_SET', :'actor_ref',
           jsonb_build_object('hold_status', hold_status),
           jsonb_build_object('hold_status', :'hold_status'), :'receipt'::jsonb
    FROM current
    WHERE :'hold_status' IN ('LEGAL_HOLD','RIGHTS_HOLD','PRIVACY_HOLD','COPYRIGHT_HOLD','DISPUTE_HOLD')
    ON CONFLICT (id) DO NOTHING RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='HOLD_SET'
      AND new_state->>'hold_status'=:'hold_status'
), updated AS (
    UPDATE content_capture SET hold_status=:'hold_status'
    WHERE id=:'capture_id' AND EXISTS(SELECT 1 FROM event_ok)
    RETURNING id
)
SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN :'hold_status' NOT IN ('LEGAL_HOLD','RIGHTS_HOLD','PRIVACY_HOLD','COPYRIGHT_HOLD','DISPUTE_HOLD') THEN 'HOLD_STATUS_INVALID'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'HOLD_SET'
    WHEN (SELECT hold_status FROM current)=:'hold_status' AND EXISTS(SELECT 1 FROM event_ok) THEN 'HOLD_SET'
    ELSE 'CONFLICT' END;
""".strip()


RELEASE_CAPTURE_HOLD_SQL_V1 = r"""
WITH current AS (
    SELECT id, hold_status FROM content_capture WHERE id=:'capture_id' FOR UPDATE
), event_insert AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, actor_ref, previous_state, new_state, receipt
    )
    SELECT :'event_id', id, 'HOLD_RELEASED', :'actor_ref',
           jsonb_build_object('hold_status', hold_status), jsonb_build_object('hold_status', 'NONE'), :'receipt'::jsonb
    FROM current WHERE hold_status <> 'NONE' AND :'receipt'::jsonb <> '{}'::jsonb
    ON CONFLICT (id) DO NOTHING RETURNING capture_id
), event_ok AS (
    SELECT capture_id FROM event_insert
    UNION ALL
    SELECT capture_id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type='HOLD_RELEASED'
      AND receipt=:'receipt'::jsonb
), updated AS (
    UPDATE content_capture SET hold_status='NONE'
    WHERE id=:'capture_id' AND EXISTS(SELECT 1 FROM event_ok)
    RETURNING id
)
SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
    WHEN :'receipt'::jsonb='{}'::jsonb THEN 'HOLD_RELEASE_RECEIPT_REQUIRED'
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'HOLD_RELEASED'
    WHEN (SELECT hold_status FROM current)='NONE' AND EXISTS(SELECT 1 FROM event_ok) THEN 'HOLD_RELEASED'
    WHEN (SELECT hold_status FROM current)='NONE' THEN 'NO_HOLD'
    ELSE 'CONFLICT' END;
""".strip()


__all__ = [
    "CAPTURE_LIFECYCLE_VERSION",
    "COMPLETE_CAPTURE_ARCHIVE_SQL_V1",
    "CaptureUseDecision",
    "FAIL_CAPTURE_BODY_PURGE_SQL_V1",
    "FINALIZE_CAPTURE_BODY_PURGE_SQL_V1",
    "LocalBodyPurgeReceipt",
    "MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1",
    "RELEASE_CAPTURE_HOLD_SQL_V1",
    "REQUEST_CAPTURE_ARCHIVE_SQL_V1",
    "SET_CAPTURE_HOLD_SQL_V1",
    "START_CAPTURE_BODY_PURGE_SQL_V1",
    "archive_transition_decision",
    "body_purge_decision",
    "capture_downstream_use_decision",
    "json_param",
    "lifecycle_event_id",
    "purge_local_capture_body",
]

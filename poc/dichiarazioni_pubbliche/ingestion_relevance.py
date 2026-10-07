from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from dichiarazioni_pubbliche.policy.intent_policy import normalize_label
from dichiarazioni_pubbliche.policy.privacy_policy import (
    PRIVACY_POLICY_VERSION,
    REQUIRED_RELEVANCE_REASONS,
)


INGESTION_RELEVANCE_CONTRACT_VERSION = "privacy-ingestion-relevance-v1"
INGESTION_RELEVANCE_BINDING_VERSION = "content-acquisition-binding-v1"
INGESTION_ACQUISITION_PERMIT_CONTRACT_VERSION = "privacy-ingestion-acquisition-permit-v1"
INGESTION_OPERATION_KINDS = frozenset(
    {"SCHEDULER_INGEST", "RESEARCH_DISCOVERY", "CURATED_WRITTEN", "CAPTURE_FETCH"}
)
_ADVISORY_LOCK_SEED = 30402

_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_AUDIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_RELEVANCE_REASONS = (
    "PUBLIC_ROLE",
    "PUBLIC_INTEREST_FUNCTION",
    "OFFICIAL_RECORD",
    "DOCUMENTED_PUBLIC_ACTIVITY",
)
_REASON_BY_NORMALIZED = {
    normalize_label(reason): reason for reason in _CANONICAL_RELEVANCE_REASONS
}
if frozenset(_REASON_BY_NORMALIZED) != REQUIRED_RELEVANCE_REASONS:
    raise RuntimeError("INGESTION_RELEVANCE_REASON_POLICY_DRIFT")

RunSql = Callable[..., str]


class IngestionRelevanceBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestionRelevanceAuthority:
    authority_id: str
    contract_version: str
    binding_version: str
    content_ref: str
    content_binding_sha256: str
    relevance_reason: str
    privacy_policy_version: str
    reviewer_ref: str
    audit_ref: str
    reviewed_at: str
    review_sequence: int
    supersedes_authority_id: str | None
    authority_integrity_sha256: str


@dataclass(frozen=True)
class IngestionRelevanceReplay:
    allowed: bool
    authority: IngestionRelevanceAuthority | None
    blocker: str | None
    current_binding_sha256: str


@dataclass(frozen=True)
class IngestionAcquisitionPermit:
    permit_id: str
    contract_version: str
    authority_id: str
    content_ref: str
    content_binding_sha256: str
    operation_kind: str
    operation_ref: str
    permit_integrity_sha256: str


def _json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_ref(value: object, code: str) -> str:
    text = str(value or "")
    if not _REF.fullmatch(text):
        raise ValueError(code)
    return text


def _bounded_audit_ref(value: object, code: str) -> str:
    text = str(value or "")
    if not _AUDIT_REF.fullmatch(text):
        raise ValueError(code)
    return text


def _reviewed_at(value: object) -> str:
    text = str(value or "")
    if not text or len(text) > 64 or "\x00" in text:
        raise ValueError("INGESTION_RELEVANCE_REVIEWED_AT_INVALID")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("INGESTION_RELEVANCE_REVIEWED_AT_INVALID") from exc
    if parsed.tzinfo is None:
        raise ValueError("INGESTION_RELEVANCE_REVIEWED_AT_INVALID")
    return parsed.isoformat()


def canonical_relevance_reason(value: object) -> str:
    normalized = normalize_label(value)
    canonical = _REASON_BY_NORMALIZED.get(normalized)
    if canonical is None:
        raise ValueError("INGESTION_RELEVANCE_REASON_INVALID")
    return canonical


def deterministic_ingestion_operation_ref(operation_kind: object, *parts: object) -> str:
    kind = str(operation_kind or "").strip().upper()
    if kind not in INGESTION_OPERATION_KINDS:
        raise ValueError("INGESTION_OPERATION_KIND_INVALID")
    digest = _json_sha256([str(part) for part in parts])
    return f"ingestion-op:{kind.lower()}:{digest}"


def canonical_content_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 4096 or "\x00" in raw:
        raise ValueError("INGESTION_RELEVANCE_URL_INVALID")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("INGESTION_RELEVANCE_URL_INVALID")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("INGESTION_RELEVANCE_URL_INVALID")
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("INGESTION_RELEVANCE_URL_INVALID") from exc
    if port == 443:
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit(("https", netloc, path, parsed.query, ""))


def content_relevance_binding_sha256(content_ref: object, canonical_url: object) -> str:
    content = _bounded_ref(content_ref, "INGESTION_RELEVANCE_CONTENT_REF_INVALID")
    url = canonical_content_url(canonical_url)
    return _json_sha256(
        {
            "binding_version": INGESTION_RELEVANCE_BINDING_VERSION,
            "content_ref": content,
            "canonical_url": url,
        }
    )


def _integrity_material(record: IngestionRelevanceAuthority) -> dict[str, object]:
    return {
        "contract_version": record.contract_version,
        "binding_version": record.binding_version,
        "content_ref": record.content_ref,
        "content_binding_sha256": record.content_binding_sha256,
        "relevance_reason": record.relevance_reason,
        "privacy_policy_version": record.privacy_policy_version,
        "reviewer_ref": record.reviewer_ref,
        "audit_ref": record.audit_ref,
        "reviewed_at": record.reviewed_at,
        "review_sequence": record.review_sequence,
        "supersedes_authority_id": record.supersedes_authority_id,
    }


def _record_from_row(row: object) -> IngestionRelevanceAuthority:
    if not isinstance(row, dict):
        raise ValueError("INGESTION_RELEVANCE_ROW_INVALID")
    record = IngestionRelevanceAuthority(
        authority_id=_bounded_ref(row.get("authority_id"), "INGESTION_RELEVANCE_ROW_INVALID"),
        contract_version=str(row.get("contract_version") or ""),
        binding_version=str(row.get("binding_version") or ""),
        content_ref=_bounded_ref(row.get("content_ref"), "INGESTION_RELEVANCE_ROW_INVALID"),
        content_binding_sha256=str(row.get("content_binding_sha256") or ""),
        relevance_reason=str(row.get("relevance_reason") or ""),
        privacy_policy_version=str(row.get("privacy_policy_version") or ""),
        reviewer_ref=_bounded_audit_ref(
            row.get("reviewer_ref"), "INGESTION_RELEVANCE_ROW_INVALID"
        ),
        audit_ref=_bounded_audit_ref(row.get("audit_ref"), "INGESTION_RELEVANCE_ROW_INVALID"),
        reviewed_at=_reviewed_at(row.get("reviewed_at_text")),
        review_sequence=int(row.get("review_sequence")),
        supersedes_authority_id=(
            None
            if row.get("supersedes_authority_id") is None
            else _bounded_ref(
                row.get("supersedes_authority_id"), "INGESTION_RELEVANCE_ROW_INVALID"
            )
        ),
        authority_integrity_sha256=str(row.get("authority_integrity_sha256") or ""),
    )
    if not _HEX64.fullmatch(record.content_binding_sha256):
        raise ValueError("INGESTION_RELEVANCE_ROW_INVALID")
    if not _HEX64.fullmatch(record.authority_integrity_sha256):
        raise ValueError("INGESTION_RELEVANCE_ROW_INVALID")
    if record.review_sequence < 1:
        raise ValueError("INGESTION_RELEVANCE_ROW_INVALID")
    return record


def _load_lineage(run_sql: RunSql, content_ref: str) -> tuple[IngestionRelevanceAuthority, ...]:
    raw = run_sql(
        """
        SELECT COALESCE(json_agg(row_to_json(row_data) ORDER BY review_sequence)::text, '[]')
        FROM (
            SELECT
                authority_id, contract_version, binding_version, content_ref,
                content_binding_sha256, relevance_reason, privacy_policy_version,
                reviewer_ref, audit_ref, reviewed_at_text, review_sequence,
                supersedes_authority_id, authority_integrity_sha256
            FROM privacy_ingestion_relevance_authority
            WHERE content_ref = :'content_ref'
            ORDER BY review_sequence
        ) row_data;
        """,
        content_ref=content_ref,
    )
    rows = json.loads(raw or "[]")
    if not isinstance(rows, list):
        raise ValueError("INGESTION_RELEVANCE_ROW_INVALID")
    return tuple(_record_from_row(row) for row in rows)


def _lineage_blocker(records: tuple[IngestionRelevanceAuthority, ...]) -> str | None:
    previous: IngestionRelevanceAuthority | None = None
    for index, record in enumerate(records, start=1):
        if record.review_sequence != index:
            return "INGESTION_RELEVANCE_SEQUENCE_INVALID"
        if previous is None:
            if record.supersedes_authority_id is not None:
                return "INGESTION_RELEVANCE_ROOT_INVALID"
        elif record.supersedes_authority_id != previous.authority_id:
            return "INGESTION_RELEVANCE_CHAIN_INVALID"
        if _json_sha256(_integrity_material(record)) != record.authority_integrity_sha256:
            return "INGESTION_RELEVANCE_INTEGRITY_INVALID"
        previous = record
    return None


def _permit_integrity_material(permit: IngestionAcquisitionPermit) -> dict[str, object]:
    return {
        "contract_version": permit.contract_version,
        "authority_id": permit.authority_id,
        "content_ref": permit.content_ref,
        "content_binding_sha256": permit.content_binding_sha256,
        "operation_kind": permit.operation_kind,
        "operation_ref": permit.operation_ref,
    }


def _permit_from_row(row: object) -> IngestionAcquisitionPermit:
    if not isinstance(row, dict):
        raise ValueError("INGESTION_ACQUISITION_PERMIT_ROW_INVALID")
    permit = IngestionAcquisitionPermit(
        permit_id=_bounded_ref(row.get("permit_id"), "INGESTION_ACQUISITION_PERMIT_ROW_INVALID"),
        contract_version=str(row.get("contract_version") or ""),
        authority_id=_bounded_ref(
            row.get("authority_id"), "INGESTION_ACQUISITION_PERMIT_ROW_INVALID"
        ),
        content_ref=_bounded_ref(
            row.get("content_ref"), "INGESTION_ACQUISITION_PERMIT_ROW_INVALID"
        ),
        content_binding_sha256=str(row.get("content_binding_sha256") or ""),
        operation_kind=str(row.get("operation_kind") or ""),
        operation_ref=_bounded_ref(
            row.get("operation_ref"), "INGESTION_ACQUISITION_PERMIT_ROW_INVALID"
        ),
        permit_integrity_sha256=str(row.get("permit_integrity_sha256") or ""),
    )
    if permit.contract_version != INGESTION_ACQUISITION_PERMIT_CONTRACT_VERSION:
        raise ValueError("INGESTION_ACQUISITION_PERMIT_ROW_INVALID")
    if permit.operation_kind not in INGESTION_OPERATION_KINDS:
        raise ValueError("INGESTION_ACQUISITION_PERMIT_ROW_INVALID")
    if not _HEX64.fullmatch(permit.content_binding_sha256):
        raise ValueError("INGESTION_ACQUISITION_PERMIT_ROW_INVALID")
    if not _HEX64.fullmatch(permit.permit_integrity_sha256):
        raise ValueError("INGESTION_ACQUISITION_PERMIT_ROW_INVALID")
    if _json_sha256(_permit_integrity_material(permit)) != permit.permit_integrity_sha256:
        raise ValueError("INGESTION_ACQUISITION_PERMIT_INTEGRITY_INVALID")
    return permit


def replay_current_ingestion_relevance(
    run_sql: RunSql,
    *,
    content_ref: object,
    canonical_url: object,
) -> IngestionRelevanceReplay:
    content = _bounded_ref(content_ref, "INGESTION_RELEVANCE_CONTENT_REF_INVALID")
    binding = content_relevance_binding_sha256(content, canonical_url)
    try:
        records = _load_lineage(run_sql, content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return IngestionRelevanceReplay(False, None, "INGESTION_RELEVANCE_ROW_INVALID", binding)
    if not records:
        return IngestionRelevanceReplay(False, None, "INGESTION_RELEVANCE_MISSING", binding)
    blocker = _lineage_blocker(records)
    if blocker:
        return IngestionRelevanceReplay(False, None, blocker, binding)
    current = records[-1]
    if current.contract_version != INGESTION_RELEVANCE_CONTRACT_VERSION:
        return IngestionRelevanceReplay(
            False, current, "INGESTION_RELEVANCE_CONTRACT_STALE", binding
        )
    if current.binding_version != INGESTION_RELEVANCE_BINDING_VERSION:
        return IngestionRelevanceReplay(
            False, current, "INGESTION_RELEVANCE_BINDING_VERSION_STALE", binding
        )
    if current.privacy_policy_version != PRIVACY_POLICY_VERSION:
        return IngestionRelevanceReplay(
            False, current, "INGESTION_RELEVANCE_POLICY_STALE", binding
        )
    if current.content_binding_sha256 != binding:
        return IngestionRelevanceReplay(
            False, current, "INGESTION_RELEVANCE_CONTENT_STALE", binding
        )
    try:
        reason = canonical_relevance_reason(current.relevance_reason)
    except ValueError:
        return IngestionRelevanceReplay(
            False, current, "INGESTION_RELEVANCE_REASON_INVALID", binding
        )
    if reason != current.relevance_reason:
        return IngestionRelevanceReplay(
            False, current, "INGESTION_RELEVANCE_REASON_NONCANONICAL", binding
        )
    return IngestionRelevanceReplay(True, current, None, binding)


def require_current_ingestion_relevance(
    run_sql: RunSql,
    *,
    content_ref: object,
    canonical_url: object,
) -> IngestionRelevanceAuthority:
    replay = replay_current_ingestion_relevance(
        run_sql,
        content_ref=content_ref,
        canonical_url=canonical_url,
    )
    if not replay.allowed or replay.authority is None:
        raise IngestionRelevanceBlocked(replay.blocker or "INGESTION_RELEVANCE_BLOCKED")
    return replay.authority


def require_ingestion_acquisition_permit(
    run_sql: RunSql,
    *,
    permit_id: object,
    content_ref: object,
    canonical_url: object,
    operation_kind: object,
    operation_ref: object,
) -> IngestionAcquisitionPermit:
    permit_ref = _bounded_ref(permit_id, "INGESTION_ACQUISITION_PERMIT_ID_INVALID")
    content = _bounded_ref(content_ref, "INGESTION_RELEVANCE_CONTENT_REF_INVALID")
    binding = content_relevance_binding_sha256(content, canonical_url)
    kind = str(operation_kind or "").strip().upper()
    if kind not in INGESTION_OPERATION_KINDS:
        raise ValueError("INGESTION_OPERATION_KIND_INVALID")
    op_ref = _bounded_ref(operation_ref, "INGESTION_OPERATION_REF_INVALID")
    raw = run_sql(
        """
        WITH lock_row AS (
            SELECT pg_advisory_xact_lock(
                hashtextextended(:'content_ref', :'lock_seed'::bigint)
            )
        ), row_data AS (
            SELECT
                permit.permit_id, permit.contract_version, permit.authority_id,
                permit.content_ref, permit.content_binding_sha256,
                permit.operation_kind, permit.operation_ref,
                permit.permit_integrity_sha256
            FROM privacy_ingestion_acquisition_permit permit
            JOIN privacy_ingestion_relevance_authority authority
              ON authority.authority_id = permit.authority_id
            CROSS JOIN lock_row
            WHERE permit.permit_id = :'permit_id'
              AND permit.content_ref = :'content_ref'
              AND authority.content_ref = permit.content_ref
              AND authority.content_binding_sha256 = permit.content_binding_sha256
              AND authority.contract_version = :'authority_contract_version'
              AND authority.binding_version = :'binding_version'
              AND authority.privacy_policy_version = :'privacy_policy_version'
              AND NOT EXISTS (
                  SELECT 1
                  FROM privacy_ingestion_relevance_authority successor
                  WHERE successor.supersedes_authority_id = authority.authority_id
              )
        )
        SELECT COALESCE(row_to_json(row_data)::text, '')
        FROM row_data;
        """,
        permit_id=permit_ref,
        content_ref=content,
        lock_seed=_ADVISORY_LOCK_SEED,
        authority_contract_version=INGESTION_RELEVANCE_CONTRACT_VERSION,
        binding_version=INGESTION_RELEVANCE_BINDING_VERSION,
        privacy_policy_version=PRIVACY_POLICY_VERSION,
    )
    if not raw:
        existing = run_sql(
            """
            SELECT CASE WHEN EXISTS(
                SELECT 1
                FROM privacy_ingestion_acquisition_permit
                WHERE permit_id = :'permit_id'
            ) THEN 'STALE' ELSE 'MISSING' END;
            """,
            permit_id=permit_ref,
        )
        if existing == "STALE":
            raise IngestionRelevanceBlocked("INGESTION_ACQUISITION_PERMIT_STALE")
        raise IngestionRelevanceBlocked("INGESTION_ACQUISITION_PERMIT_MISSING")
    try:
        permit = _permit_from_row(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IngestionRelevanceBlocked("INGESTION_ACQUISITION_PERMIT_INVALID") from exc
    if (
        permit.content_ref != content
        or permit.content_binding_sha256 != binding
        or permit.operation_kind != kind
        or permit.operation_ref != op_ref
    ):
        raise IngestionRelevanceBlocked("INGESTION_ACQUISITION_PERMIT_BINDING_MISMATCH")
    return permit


def issue_ingestion_acquisition_permit(
    run_sql: RunSql,
    *,
    content_ref: object,
    canonical_url: object,
    operation_kind: object,
    operation_ref: object,
) -> IngestionAcquisitionPermit:
    content = _bounded_ref(content_ref, "INGESTION_RELEVANCE_CONTENT_REF_INVALID")
    binding = content_relevance_binding_sha256(content, canonical_url)
    kind = str(operation_kind or "").strip().upper()
    if kind not in INGESTION_OPERATION_KINDS:
        raise ValueError("INGESTION_OPERATION_KIND_INVALID")
    op_ref = _bounded_ref(operation_ref, "INGESTION_OPERATION_REF_INVALID")
    replay = replay_current_ingestion_relevance(
        run_sql,
        content_ref=content,
        canonical_url=canonical_url,
    )
    if not replay.allowed or replay.authority is None:
        raise IngestionRelevanceBlocked(replay.blocker or "INGESTION_RELEVANCE_BLOCKED")
    authority = replay.authority
    permit_material = {
        "contract_version": INGESTION_ACQUISITION_PERMIT_CONTRACT_VERSION,
        "authority_id": authority.authority_id,
        "content_ref": content,
        "content_binding_sha256": binding,
        "operation_kind": kind,
        "operation_ref": op_ref,
    }
    integrity = _json_sha256(permit_material)
    permit = IngestionAcquisitionPermit(
        permit_id=f"ingestion-permit:{integrity}",
        permit_integrity_sha256=integrity,
        **permit_material,
    )
    raw = run_sql(
        """
        WITH lock_row AS (
            SELECT pg_advisory_xact_lock(
                hashtextextended(:'content_ref', :'lock_seed'::bigint)
            )
        ), current_authority AS (
            SELECT authority.authority_id
            FROM privacy_ingestion_relevance_authority authority
            CROSS JOIN lock_row
            WHERE authority.authority_id = :'authority_id'
              AND authority.content_ref = :'content_ref'
              AND authority.content_binding_sha256 = :'content_binding_sha256'
              AND authority.contract_version = :'authority_contract_version'
              AND authority.binding_version = :'binding_version'
              AND authority.privacy_policy_version = :'privacy_policy_version'
              AND authority.relevance_reason = :'relevance_reason'
              AND NOT EXISTS (
                  SELECT 1
                  FROM privacy_ingestion_relevance_authority successor
                  WHERE successor.supersedes_authority_id = authority.authority_id
              )
        ), inserted AS (
            INSERT INTO privacy_ingestion_acquisition_permit (
                permit_id, contract_version, authority_id, content_ref,
                content_binding_sha256, operation_kind, operation_ref,
                permit_integrity_sha256
            )
            SELECT
                :'permit_id', :'permit_contract_version', authority_id, :'content_ref',
                :'content_binding_sha256', :'operation_kind', :'operation_ref',
                :'permit_integrity_sha256'
            FROM current_authority
            ON CONFLICT (permit_id) DO NOTHING
            RETURNING permit_id
        )
        SELECT COALESCE(
            (SELECT permit_id FROM inserted LIMIT 1),
            (
                SELECT existing.permit_id
                FROM privacy_ingestion_acquisition_permit existing
                JOIN current_authority ON true
                WHERE existing.permit_id = :'permit_id'
                  AND existing.authority_id = :'authority_id'
                  AND existing.content_ref = :'content_ref'
                  AND existing.content_binding_sha256 = :'content_binding_sha256'
                  AND existing.operation_kind = :'operation_kind'
                  AND existing.operation_ref = :'operation_ref'
                  AND existing.permit_integrity_sha256 = :'permit_integrity_sha256'
                LIMIT 1
            ),
            ''
        );
        """,
        content_ref=content,
        lock_seed=_ADVISORY_LOCK_SEED,
        authority_id=authority.authority_id,
        content_binding_sha256=binding,
        authority_contract_version=INGESTION_RELEVANCE_CONTRACT_VERSION,
        binding_version=INGESTION_RELEVANCE_BINDING_VERSION,
        privacy_policy_version=PRIVACY_POLICY_VERSION,
        relevance_reason=authority.relevance_reason,
        permit_id=permit.permit_id,
        permit_contract_version=permit.contract_version,
        operation_kind=permit.operation_kind,
        operation_ref=permit.operation_ref,
        permit_integrity_sha256=permit.permit_integrity_sha256,
    )
    if raw != permit.permit_id:
        raise IngestionRelevanceBlocked("INGESTION_RELEVANCE_CHANGED_DURING_PERMIT")
    return require_ingestion_acquisition_permit(
        run_sql,
        permit_id=permit.permit_id,
        content_ref=content,
        canonical_url=canonical_url,
        operation_kind=kind,
        operation_ref=op_ref,
    )


def append_ingestion_relevance_authority(
    run_sql: RunSql,
    *,
    content_ref: object,
    canonical_url: object,
    relevance_reason: object,
    reviewer_ref: object,
    audit_ref: object,
    reviewed_at: object,
    supersedes_authority_id: object | None = None,
) -> IngestionRelevanceAuthority:
    content = _bounded_ref(content_ref, "INGESTION_RELEVANCE_CONTENT_REF_INVALID")
    binding = content_relevance_binding_sha256(content, canonical_url)
    reason = canonical_relevance_reason(relevance_reason)
    reviewer = _bounded_audit_ref(reviewer_ref, "INGESTION_RELEVANCE_REVIEWER_REF_INVALID")
    audit = _bounded_audit_ref(audit_ref, "INGESTION_RELEVANCE_AUDIT_REF_INVALID")
    reviewed = _reviewed_at(reviewed_at)
    lineage = _load_lineage(run_sql, content)
    blocker = _lineage_blocker(lineage)
    if blocker:
        raise ValueError(blocker)
    if lineage:
        latest = lineage[-1]
        if supersedes_authority_id is None:
            raise ValueError("INGESTION_RELEVANCE_SUPERSESSION_REQUIRED")
        supplied_parent = _bounded_ref(
            supersedes_authority_id, "INGESTION_RELEVANCE_SUPERSEDES_INVALID"
        )
        if supplied_parent != latest.authority_id:
            raise ValueError("INGESTION_RELEVANCE_SUPERSEDES_NOT_LATEST")
        sequence = latest.review_sequence + 1
        parent_id: str | None = latest.authority_id
    else:
        if supersedes_authority_id is not None:
            raise ValueError("INGESTION_RELEVANCE_SUPERSEDES_MISSING")
        sequence = 1
        parent_id = None
    material = {
        "contract_version": INGESTION_RELEVANCE_CONTRACT_VERSION,
        "binding_version": INGESTION_RELEVANCE_BINDING_VERSION,
        "content_ref": content,
        "content_binding_sha256": binding,
        "relevance_reason": reason,
        "privacy_policy_version": PRIVACY_POLICY_VERSION,
        "reviewer_ref": reviewer,
        "audit_ref": audit,
        "reviewed_at": reviewed,
        "review_sequence": sequence,
        "supersedes_authority_id": parent_id,
    }
    integrity = _json_sha256(material)
    record = IngestionRelevanceAuthority(
        authority_id=f"privacy-ingestion-relevance:{integrity}",
        authority_integrity_sha256=integrity,
        **material,
    )
    raw = run_sql(
        """
        WITH lock_row AS (
            SELECT pg_advisory_xact_lock(
                hashtextextended(:'content_ref', :'lock_seed'::bigint)
            )
        ), latest AS (
            SELECT current.authority_id, current.review_sequence
            FROM privacy_ingestion_relevance_authority current
            CROSS JOIN lock_row
            WHERE current.content_ref = :'content_ref'
            ORDER BY current.review_sequence DESC
            LIMIT 1
        ), inserted AS (
            INSERT INTO privacy_ingestion_relevance_authority (
                authority_id, contract_version, binding_version, content_ref,
                content_binding_sha256, relevance_reason, privacy_policy_version,
                reviewer_ref, audit_ref, reviewed_at_text, review_sequence,
                supersedes_authority_id, authority_integrity_sha256
            )
            SELECT
                :'authority_id', :'contract_version', :'binding_version', :'content_ref',
                :'content_binding_sha256', :'relevance_reason', :'privacy_policy_version',
                :'reviewer_ref', :'audit_ref', :'reviewed_at_text', :'review_sequence'::integer,
                NULLIF(:'supersedes_authority_id',''), :'authority_integrity_sha256'
            WHERE (
                (NULLIF(:'supersedes_authority_id','') IS NULL AND NOT EXISTS(SELECT 1 FROM latest))
                OR
                (
                    NULLIF(:'supersedes_authority_id','') IS NOT NULL
                    AND (SELECT authority_id FROM latest) = NULLIF(:'supersedes_authority_id','')
                    AND (SELECT review_sequence FROM latest) + 1 = :'review_sequence'::integer
                )
            )
            RETURNING authority_id
        )
        SELECT COALESCE((SELECT authority_id FROM inserted LIMIT 1), '');
        """,
        authority_id=record.authority_id,
        contract_version=record.contract_version,
        binding_version=record.binding_version,
        content_ref=record.content_ref,
        content_binding_sha256=record.content_binding_sha256,
        relevance_reason=record.relevance_reason,
        privacy_policy_version=record.privacy_policy_version,
        reviewer_ref=record.reviewer_ref,
        audit_ref=record.audit_ref,
        reviewed_at_text=record.reviewed_at,
        review_sequence=record.review_sequence,
        supersedes_authority_id=record.supersedes_authority_id or "",
        authority_integrity_sha256=record.authority_integrity_sha256,
        lock_seed=_ADVISORY_LOCK_SEED,
    )
    if raw != record.authority_id:
        raise IngestionRelevanceBlocked("INGESTION_RELEVANCE_CHANGED_DURING_APPEND")
    replay = replay_current_ingestion_relevance(
        run_sql,
        content_ref=record.content_ref,
        canonical_url=canonical_url,
    )
    if not replay.allowed or replay.authority != record:
        raise RuntimeError(replay.blocker or "INGESTION_RELEVANCE_PERSISTENCE_FAILED")
    return record


__all__ = [
    "INGESTION_ACQUISITION_PERMIT_CONTRACT_VERSION",
    "INGESTION_OPERATION_KINDS",
    "INGESTION_RELEVANCE_BINDING_VERSION",
    "INGESTION_RELEVANCE_CONTRACT_VERSION",
    "IngestionAcquisitionPermit",
    "IngestionRelevanceAuthority",
    "IngestionRelevanceBlocked",
    "IngestionRelevanceReplay",
    "append_ingestion_relevance_authority",
    "canonical_content_url",
    "canonical_relevance_reason",
    "content_relevance_binding_sha256",
    "deterministic_ingestion_operation_ref",
    "issue_ingestion_acquisition_permit",
    "replay_current_ingestion_relevance",
    "require_current_ingestion_relevance",
    "require_ingestion_acquisition_permit",
]

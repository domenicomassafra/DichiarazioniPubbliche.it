from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Mapping

from dichiarazioni_pubbliche.domain_vocabulary import CLAIM_TYPE_VERSION, ClaimType


CAPTURE_STATUSES = frozenset({"CAPTURED", "QUARANTINED", "PURGE_PENDING", "PURGED_BODY"})
CAPTURE_RETENTION_CLASSES = frozenset({"POLICY_PENDING", "EPHEMERAL", "DURABLE_PRIVATE", "DURABLE_PROVENANCE"})
CAPTURE_HOLD_STATUSES = frozenset({"NONE", "LEGAL_HOLD", "RIGHTS_HOLD", "PRIVACY_HOLD", "COPYRIGHT_HOLD", "DISPUTE_HOLD"})
CAPTURE_ARCHIVE_STATUSES = frozenset({"NOT_REQUESTED", "REQUESTED", "PENDING", "SUCCEEDED", "FAILED"})
COLLECTION_STATUSES = frozenset({"ACTIVE", "PAUSED", "ARCHIVED"})
COLLECTION_CONTENT_STATUSES = frozenset({"INCLUDED", "REJECTED", "REMOVED"})
PASSAGE_SELECTOR_TYPES = frozenset({"TEXT_POSITION", "PAGE_RANGE", "MEDIA_SEGMENT_REF"})
STATEMENT_CANDIDATE_STATUSES = frozenset(
    {"CANDIDATE", "APPROVED", "REJECTED", "HELD", "SUPERSEDED"}
)
CLAIM_CANDIDATE_STATUSES = frozenset(
    {"CANDIDATE", "DUPLICATE", "PROMOTED", "REJECTED", "HELD"}
)
NON_FACTUAL_CLAIM_TYPES = frozenset({"RHETORICAL_GENERALIZATION", "VALUE_JUDGMENT"})

_SECRET_METADATA_KEYS = frozenset({
    "authorization", "proxy_authorization", "cookie", "set_cookie", "api_key",
    "access_token", "refresh_token", "password", "secret", "client_secret",
})


def _normalized_key(value: object) -> str:
    return str(value).strip().casefold().replace("-", "_")


def _secret_metadata_path(value: Any, prefix: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            clean = _normalized_key(key)
            path = f"{prefix}.{clean}" if prefix else clean
            if clean in _SECRET_METADATA_KEYS:
                return path
            nested = _secret_metadata_path(child, path)
            if nested:
                return nested
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            nested = _secret_metadata_path(child, f"{prefix}[{index}]")
            if nested:
                return nested
    return None


def _reject_secret_metadata(value: Any, field_name: str) -> None:
    path = _secret_metadata_path(value)
    if path:
        raise ValueError(f"CORPUS_{field_name.upper()}_SECRET_KEY_FORBIDDEN:{path}")


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"CORPUS_{field_name.upper()}_REQUIRED")
    return value.strip()


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"CORPUS_{field_name.upper()}_INVALID")
    stripped = value.strip()
    return stripped or None


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"CORPUS_{field_name.upper()}_INVALID")
    return dict(value)


def _sha256(value: Any, field_name: str) -> str:
    text = _required_str(value, field_name).lower()
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise ValueError(f"CORPUS_{field_name.upper()}_INVALID_SHA256")
    return text


def _aware_iso_datetime(value: Any, field_name: str) -> str:
    text = _required_str(value, field_name)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"CORPUS_{field_name.upper()}_INVALID_DATETIME") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"CORPUS_{field_name.upper()}_TIMEZONE_REQUIRED")
    return text


def deterministic_corpus_id(prefix: str, *parts: str) -> str:
    prefix = _required_str(prefix, "id_prefix")
    clean = [_required_str(part, "id_part") for part in parts]
    digest = hashlib.sha256("\x1f".join(clean).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


@dataclass(frozen=True)
class ContentCaptureRecord:
    id: str
    content_id: str
    observed_at: str
    final_url: str
    content_sha256: str
    retrieval_method: str
    retrieval_version: str
    media_type: str | None = None
    body_ref: str | None = None
    parser_method: str | None = None
    parser_version: str | None = None
    rights_status: str = "UNKNOWN"
    retention_class: str = "POLICY_PENDING"
    hold_status: str = "NONE"
    archive_status: str = "NOT_REQUESTED"
    archive_provider: str | None = None
    archive_requested_at: str | None = None
    archive_completed_at: str | None = None
    archive_receipt: dict[str, Any] = field(default_factory=dict)
    body_purged_at: str | None = None
    purge_reason: str | None = None
    purge_receipt: dict[str, Any] = field(default_factory=dict)
    status: str = "CAPTURED"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_str(self.id, "capture_id")
        _required_str(self.content_id, "content_id")
        _aware_iso_datetime(self.observed_at, "observed_at")
        _required_str(self.final_url, "final_url")
        _sha256(self.content_sha256, "content_sha256")
        _required_str(self.retrieval_method, "retrieval_method")
        _required_str(self.retrieval_version, "retrieval_version")
        if self.retention_class not in CAPTURE_RETENTION_CLASSES:
            raise ValueError("CORPUS_CAPTURE_RETENTION_CLASS_INVALID")
        if self.hold_status not in CAPTURE_HOLD_STATUSES:
            raise ValueError("CORPUS_CAPTURE_HOLD_STATUS_INVALID")
        if self.archive_status not in CAPTURE_ARCHIVE_STATUSES:
            raise ValueError("CORPUS_CAPTURE_ARCHIVE_STATUS_INVALID")
        if self.status not in CAPTURE_STATUSES:
            raise ValueError("CORPUS_CAPTURE_STATUS_INVALID")
        if not isinstance(self.archive_receipt, Mapping):
            raise ValueError("CORPUS_ARCHIVE_RECEIPT_INVALID")
        if not isinstance(self.purge_receipt, Mapping):
            raise ValueError("CORPUS_PURGE_RECEIPT_INVALID")
        _reject_secret_metadata(self.archive_receipt, "archive_receipt")
        _reject_secret_metadata(self.purge_receipt, "purge_receipt")
        _reject_secret_metadata(self.metadata, "metadata")
        if self.archive_status != "NOT_REQUESTED":
            if not _optional_str(self.archive_provider, "archive_provider") or self.archive_requested_at is None:
                raise ValueError("CORPUS_ARCHIVE_REQUEST_RECEIPT_INCOMPLETE")
            _aware_iso_datetime(self.archive_requested_at, "archive_requested_at")
        if self.archive_status in {"SUCCEEDED", "FAILED"}:
            if self.archive_completed_at is None or not self.archive_receipt:
                raise ValueError("CORPUS_ARCHIVE_COMPLETION_RECEIPT_INCOMPLETE")
            _aware_iso_datetime(self.archive_completed_at, "archive_completed_at")
        if self.status == "PURGED_BODY":
            if self.body_ref is not None or self.body_purged_at is None or not _optional_str(self.purge_reason, "purge_reason") or not self.purge_receipt:
                raise ValueError("CORPUS_PURGED_BODY_RECEIPT_INCOMPLETE")
            _aware_iso_datetime(self.body_purged_at, "body_purged_at")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("CORPUS_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PassageRecord:
    id: str
    content_id: str
    selector_type: str
    text_sha256: str
    extraction_method: str
    extraction_version: str
    capture_id: str | None = None
    canonical_segment_id: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    private_text: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_str(self.id, "passage_id")
        _required_str(self.content_id, "content_id")
        _sha256(self.text_sha256, "text_sha256")
        _required_str(self.extraction_method, "extraction_method")
        _required_str(self.extraction_version, "extraction_version")
        if self.selector_type not in PASSAGE_SELECTOR_TYPES:
            raise ValueError("CORPUS_PASSAGE_SELECTOR_TYPE_INVALID")
        if (self.capture_id is None) == (self.canonical_segment_id is None):
            raise ValueError("CORPUS_PASSAGE_EXACTLY_ONE_SOURCE_REQUIRED")
        if self.selector_type == "TEXT_POSITION":
            if self.capture_id is None or self.start_char is None or self.end_char is None:
                raise ValueError("CORPUS_PASSAGE_TEXT_POSITION_REQUIRED")
            if self.start_char < 0 or self.end_char <= self.start_char:
                raise ValueError("CORPUS_PASSAGE_TEXT_POSITION_INVALID")
        if self.selector_type == "PAGE_RANGE":
            if self.capture_id is None or self.page_start is None or self.page_end is None:
                raise ValueError("CORPUS_PASSAGE_PAGE_RANGE_REQUIRED")
            if self.page_start < 1 or self.page_end < self.page_start:
                raise ValueError("CORPUS_PASSAGE_PAGE_RANGE_INVALID")
        if self.selector_type == "MEDIA_SEGMENT_REF" and self.canonical_segment_id is None:
            raise ValueError("CORPUS_PASSAGE_MEDIA_SEGMENT_REQUIRED")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("CORPUS_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchCollectionRecord:
    id: str
    slug: str
    name: str
    scope_text: str
    policy_version: str
    status: str = "ACTIVE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("id", "slug", "name", "scope_text", "policy_version"):
            _required_str(getattr(self, field_name), field_name)
        if self.status not in COLLECTION_STATUSES:
            raise ValueError("CORPUS_COLLECTION_STATUS_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("CORPUS_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CollectionContentRecord:
    collection_id: str
    content_id: str
    inclusion_method: str
    inclusion_version: str
    status: str = "INCLUDED"
    rationale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("collection_id", "content_id", "inclusion_method", "inclusion_version"):
            _required_str(getattr(self, field_name), field_name)
        if self.status not in COLLECTION_CONTENT_STATUSES:
            raise ValueError("CORPUS_COLLECTION_CONTENT_STATUS_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("CORPUS_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StatementCandidateRecord:
    id: str
    content_id: str
    passage_ids: tuple[str, ...]
    statement_text_hash: str
    normalized_statement: str
    extraction_version: str
    speaker_person_id: str | None = None
    statement_at: str | None = None
    attribution_method: str | None = None
    extraction_model: str | None = None
    status: str = "CANDIDATE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_str(self.id, "statement_candidate_id")
        _required_str(self.content_id, "content_id")
        _sha256(self.statement_text_hash, "statement_text_hash")
        _required_str(self.normalized_statement, "normalized_statement")
        _required_str(self.extraction_version, "extraction_version")
        if not isinstance(self.passage_ids, tuple) or not self.passage_ids:
            raise ValueError("CORPUS_STATEMENT_PASSAGE_IDS_REQUIRED")
        for passage_id in self.passage_ids:
            _required_str(passage_id, "passage_id")
        if self.statement_at is not None:
            _aware_iso_datetime(self.statement_at, "statement_at")
        if self.status not in STATEMENT_CANDIDATE_STATUSES:
            raise ValueError("CORPUS_STATEMENT_STATUS_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("CORPUS_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["passage_ids"] = list(self.passage_ids)
        return data


@dataclass(frozen=True)
class ClaimCandidateRecord:
    id: str
    statement_candidate_id: str
    content_id: str
    normalized_claim: str
    proposed_claim_type: str
    extraction_version: str
    claim_type_version: str = CLAIM_TYPE_VERSION
    temporal_scope: dict[str, Any] = field(default_factory=dict)
    check_worthy: bool = True
    extraction_model: str | None = None
    status: str = "CANDIDATE"
    promoted_claim_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("id", "statement_candidate_id", "content_id", "normalized_claim", "extraction_version"):
            _required_str(getattr(self, field_name), field_name)
        if self.claim_type_version != CLAIM_TYPE_VERSION:
            raise ValueError("CORPUS_CLAIM_TYPE_VERSION_MISMATCH")
        try:
            ClaimType(self.proposed_claim_type)
        except ValueError as exc:
            raise ValueError("CORPUS_PROPOSED_CLAIM_TYPE_INVALID") from exc
        if not isinstance(self.check_worthy, bool):
            raise ValueError("CORPUS_CHECK_WORTHY_INVALID")
        if self.proposed_claim_type in NON_FACTUAL_CLAIM_TYPES and self.check_worthy:
            raise ValueError("CORPUS_NON_FACTUAL_NOT_CHECK_WORTHY")
        if self.status not in CLAIM_CANDIDATE_STATUSES:
            raise ValueError("CORPUS_CLAIM_STATUS_INVALID")
        if (self.status == "PROMOTED") != (self.promoted_claim_id is not None):
            raise ValueError("CORPUS_PROMOTION_STATE_INVALID")
        if not isinstance(self.temporal_scope, Mapping):
            raise ValueError("CORPUS_TEMPORAL_SCOPE_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("CORPUS_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _strict_record(data: Any, cls: type, allowed: set[str] | frozenset[str]):
    if isinstance(data, cls):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    if not isinstance(data, Mapping):
        raise ValueError(f"CORPUS_RECORD_INVALID_TYPE: expected Mapping or {cls.__name__}")
    unknown = set(data) - set(allowed)
    if unknown:
        raise ValueError(f"CORPUS_RECORD_UNKNOWN_FIELDS: {sorted(unknown)}")
    try:
        return cls(**dict(data))
    except TypeError as exc:
        raise ValueError(f"CORPUS_RECORD_MISSING_FIELDS: {exc}") from exc


def normalize_content_capture(data: Any) -> ContentCaptureRecord:
    return _strict_record(data, ContentCaptureRecord, ContentCaptureRecord.__dataclass_fields__.keys())


def normalize_passage(data: Any) -> PassageRecord:
    return _strict_record(data, PassageRecord, PassageRecord.__dataclass_fields__.keys())


def normalize_research_collection(data: Any) -> ResearchCollectionRecord:
    return _strict_record(data, ResearchCollectionRecord, ResearchCollectionRecord.__dataclass_fields__.keys())


def normalize_collection_content(data: Any) -> CollectionContentRecord:
    return _strict_record(data, CollectionContentRecord, CollectionContentRecord.__dataclass_fields__.keys())


def normalize_statement_candidate(data: Any) -> StatementCandidateRecord:
    if isinstance(data, Mapping) and isinstance(data.get("passage_ids"), list):
        data = dict(data)
        data["passage_ids"] = tuple(data["passage_ids"])
    return _strict_record(data, StatementCandidateRecord, StatementCandidateRecord.__dataclass_fields__.keys())


def normalize_claim_candidate(data: Any) -> ClaimCandidateRecord:
    return _strict_record(data, ClaimCandidateRecord, ClaimCandidateRecord.__dataclass_fields__.keys())


def records_to_json(records: list[Any]) -> str:
    payload = []
    for record in records:
        if not hasattr(record, "to_dict"):
            raise ValueError("CORPUS_JSON_RECORD_INVALID")
        payload.append(record.to_dict())
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


INSERT_CONTENT_CAPTURE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO content_capture (
        id, content_id, observed_at, final_url, media_type, content_sha256, body_ref,
        retrieval_method, retrieval_version, parser_method, parser_version,
        rights_status, retention_class, hold_status, archive_status, archive_provider,
        archive_requested_at, archive_completed_at, archive_receipt, body_purged_at,
        purge_reason, purge_receipt, status, metadata
    ) VALUES (
        :'id', :'content_id', :'observed_at'::timestamptz, :'final_url',
        NULLIF(:'media_type',''), :'content_sha256', NULLIF(:'body_ref',''),
        :'retrieval_method', :'retrieval_version', NULLIF(:'parser_method',''),
        NULLIF(:'parser_version',''), :'rights_status', :'retention_class', :'hold_status',
        :'archive_status', NULLIF(:'archive_provider',''), NULLIF(:'archive_requested_at','')::timestamptz,
        NULLIF(:'archive_completed_at','')::timestamptz, :'archive_receipt'::jsonb,
        NULLIF(:'body_purged_at','')::timestamptz, NULLIF(:'purge_reason',''), :'purge_receipt'::jsonb,
        :'status', :'metadata'::jsonb
    )
    ON CONFLICT DO NOTHING
    RETURNING id
), existing AS (
    SELECT id
    FROM content_capture
    WHERE content_id = :'content_id'
      AND content_sha256 = :'content_sha256'
      AND final_url = :'final_url'
      AND retrieval_method = :'retrieval_method'
      AND retrieval_version = :'retrieval_version'
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()

INSERT_PASSAGE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO passage (
        id, content_id, capture_id, canonical_segment_id, selector_type,
        start_char, end_char, page_start, page_end, text_sha256, private_text,
        language, extraction_method, extraction_version, metadata
    ) VALUES (
        :'id', :'content_id', NULLIF(:'capture_id',''), NULLIF(:'canonical_segment_id',''),
        :'selector_type', NULLIF(:'start_char','')::integer, NULLIF(:'end_char','')::integer,
        NULLIF(:'page_start','')::integer, NULLIF(:'page_end','')::integer,
        :'text_sha256', NULLIF(:'private_text',''), NULLIF(:'language',''),
        :'extraction_method', :'extraction_version', :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM passage
    WHERE id = :'id'
      AND content_id = :'content_id'
      AND capture_id IS NOT DISTINCT FROM NULLIF(:'capture_id','')
      AND canonical_segment_id IS NOT DISTINCT FROM NULLIF(:'canonical_segment_id','')
      AND selector_type = :'selector_type'
      AND start_char IS NOT DISTINCT FROM NULLIF(:'start_char','')::integer
      AND end_char IS NOT DISTINCT FROM NULLIF(:'end_char','')::integer
      AND page_start IS NOT DISTINCT FROM NULLIF(:'page_start','')::integer
      AND page_end IS NOT DISTINCT FROM NULLIF(:'page_end','')::integer
      AND text_sha256 = :'text_sha256'
      AND private_text IS NOT DISTINCT FROM NULLIF(:'private_text','')
      AND language IS NOT DISTINCT FROM NULLIF(:'language','')
      AND extraction_method = :'extraction_method'
      AND extraction_version = :'extraction_version'
      AND metadata = :'metadata'::jsonb
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()


INSERT_RESEARCH_COLLECTION_SQL_V1 = """
WITH inserted AS (
    INSERT INTO research_collection (
        id, slug, name, scope_text, policy_version, status, metadata
    ) VALUES (
        :'id', :'slug', :'name', :'scope_text', :'policy_version', :'status', :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM research_collection
    WHERE id = :'id' AND slug = :'slug' AND name = :'name'
      AND scope_text = :'scope_text' AND policy_version = :'policy_version'
      AND status = :'status' AND metadata = :'metadata'::jsonb
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()


INSERT_COLLECTION_CONTENT_SQL_V1 = """
WITH inserted AS (
    INSERT INTO research_collection_content (
        collection_id, content_id, inclusion_method, inclusion_version, status, rationale, metadata
    ) VALUES (
        :'collection_id', :'content_id', :'inclusion_method', :'inclusion_version',
        :'status', NULLIF(:'rationale',''), :'metadata'::jsonb
    )
    ON CONFLICT (collection_id, content_id) DO NOTHING
    RETURNING collection_id, content_id
), existing AS (
    SELECT collection_id FROM research_collection_content
    WHERE collection_id = :'collection_id' AND content_id = :'content_id'
      AND inclusion_method = :'inclusion_method'
      AND inclusion_version = :'inclusion_version'
      AND status = :'status'
      AND rationale IS NOT DISTINCT FROM NULLIF(:'rationale','')
      AND metadata = :'metadata'::jsonb
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()


INSERT_STATEMENT_CANDIDATE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO statement_candidate (
        id, content_id, speaker_person_id, statement_text_hash, normalized_statement,
        statement_at, attribution_method, extraction_model, extraction_version, status, metadata
    ) VALUES (
        :'id', :'content_id', NULLIF(:'speaker_person_id',''), :'statement_text_hash',
        :'normalized_statement', NULLIF(:'statement_at','')::timestamptz,
        NULLIF(:'attribution_method',''), NULLIF(:'extraction_model',''),
        :'extraction_version', :'status', :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, content_id
), linked AS (
    INSERT INTO statement_candidate_passage (statement_candidate_id, passage_id, content_id)
    SELECT inserted.id, passage_id.value, inserted.content_id
    FROM inserted
    CROSS JOIN LATERAL jsonb_array_elements_text(:'passage_ids'::jsonb) passage_id(value)
    JOIN passage p ON p.id = passage_id.value AND p.content_id = inserted.content_id
    ON CONFLICT DO NOTHING
    RETURNING statement_candidate_id
), existing AS (
    SELECT candidate.id
    FROM statement_candidate candidate
    WHERE candidate.id = :'id'
      AND candidate.content_id = :'content_id'
      AND candidate.speaker_person_id IS NOT DISTINCT FROM NULLIF(:'speaker_person_id','')
      AND candidate.statement_text_hash = :'statement_text_hash'
      AND candidate.normalized_statement = :'normalized_statement'
      AND candidate.statement_at IS NOT DISTINCT FROM NULLIF(:'statement_at','')::timestamptz
      AND candidate.attribution_method IS NOT DISTINCT FROM NULLIF(:'attribution_method','')
      AND candidate.extraction_model IS NOT DISTINCT FROM NULLIF(:'extraction_model','')
      AND candidate.extraction_version = :'extraction_version'
      AND candidate.metadata = :'metadata'::jsonb
      AND NOT EXISTS (
          SELECT value FROM jsonb_array_elements_text(:'passage_ids'::jsonb) requested(value)
          EXCEPT
          SELECT passage_id FROM statement_candidate_passage
          WHERE statement_candidate_id = candidate.id
      )
      AND NOT EXISTS (
          SELECT passage_id FROM statement_candidate_passage
          WHERE statement_candidate_id = candidate.id
          EXCEPT
          SELECT value FROM jsonb_array_elements_text(:'passage_ids'::jsonb) requested(value)
      )
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()


INSERT_CLAIM_CANDIDATE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO claim_candidate (
        id, statement_candidate_id, content_id, normalized_claim, proposed_claim_type,
        claim_type_version, temporal_scope, check_worthy, extraction_model,
        extraction_version, status, promoted_claim_id, metadata
    ) VALUES (
        :'id', :'statement_candidate_id', :'content_id', :'normalized_claim',
        :'proposed_claim_type', :'claim_type_version', :'temporal_scope'::jsonb,
        :'check_worthy'::boolean, NULLIF(:'extraction_model',''), :'extraction_version',
        :'status', NULLIF(:'promoted_claim_id',''), :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM claim_candidate
    WHERE id = :'id'
      AND statement_candidate_id = :'statement_candidate_id'
      AND content_id = :'content_id'
      AND normalized_claim = :'normalized_claim'
      AND proposed_claim_type = :'proposed_claim_type'
      AND claim_type_version = :'claim_type_version'
      AND temporal_scope = :'temporal_scope'::jsonb
      AND check_worthy = :'check_worthy'::boolean
      AND extraction_model IS NOT DISTINCT FROM NULLIF(:'extraction_model','')
      AND extraction_version = :'extraction_version'
      AND metadata = :'metadata'::jsonb
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()


__all__ = [
    "CAPTURE_ARCHIVE_STATUSES", "CAPTURE_HOLD_STATUSES", "CAPTURE_RETENTION_CLASSES",
    "CAPTURE_STATUSES", "CLAIM_CANDIDATE_STATUSES", "COLLECTION_CONTENT_STATUSES",
    "COLLECTION_STATUSES", "PASSAGE_SELECTOR_TYPES", "STATEMENT_CANDIDATE_STATUSES",
    "ClaimCandidateRecord", "CollectionContentRecord", "ContentCaptureRecord",
    "PassageRecord", "ResearchCollectionRecord", "StatementCandidateRecord",
    "INSERT_CLAIM_CANDIDATE_SQL_V1", "INSERT_COLLECTION_CONTENT_SQL_V1",
    "INSERT_CONTENT_CAPTURE_SQL_V1", "INSERT_PASSAGE_SQL_V1",
    "INSERT_RESEARCH_COLLECTION_SQL_V1", "INSERT_STATEMENT_CANDIDATE_SQL_V1",
    "deterministic_corpus_id", "normalize_claim_candidate", "normalize_collection_content",
    "normalize_content_capture", "normalize_passage", "normalize_research_collection",
    "normalize_statement_candidate", "records_to_json",
]

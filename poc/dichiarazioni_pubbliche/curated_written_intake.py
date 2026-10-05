from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.claim_contract import validate_atomic_claim
from dichiarazioni_pubbliche.claim_promotion import (
    PromotionRequest,
    promote_claim_candidate,
)
from dichiarazioni_pubbliche.corpus_repository import (
    ClaimCandidateRecord,
    ContentCaptureRecord,
    INSERT_CLAIM_CANDIDATE_SQL_V1,
    INSERT_CONTENT_CAPTURE_SQL_V1,
    INSERT_PASSAGE_SQL_V1,
    INSERT_STATEMENT_CANDIDATE_SQL_V1,
    PassageRecord,
    StatementCandidateRecord,
    deterministic_corpus_id,
)
from dichiarazioni_pubbliche.domain_vocabulary import CLAIM_TYPE_VERSION
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.review_admin import deterministic_review_event_id
from dichiarazioni_pubbliche.text_provenance import make_text_provenance_candidate


@dataclass(frozen=True)
class PreparedPromotionCapture:
    capture_id: str
    observed_at: str
    final_url: str
    content_sha256: str
    retrieval_method: str
    retrieval_version: str
    rights_status: str
    retention_class: str
    body_ref: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PreparedClaim:
    claim_id: str
    content_id: str
    person_id: str
    normalized_claim: str
    claim_type: str
    statement_date: str
    check_worthy: bool
    quote_sha256: str
    provenance_id: str
    source_ref: dict[str, Any]
    metadata: dict[str, Any]
    private_quote_text: str = field(repr=False, compare=False, default="")
    quote_start_char: int | None = None
    quote_end_char: int | None = None


@dataclass(frozen=True)
class PreparedContent:
    content_id: str
    source_id: str
    source_name: str
    source_url: str
    canonical_url: str
    title: str
    published_at: str
    person_id: str
    metadata: dict[str, Any]
    claims: tuple[PreparedClaim, ...]
    promotion_capture: PreparedPromotionCapture | None = None


@dataclass(frozen=True)
class PreparedBatch:
    batch_id: str
    extraction_model: str
    extraction_version: str
    contents: tuple[PreparedContent, ...]


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"CURATED_INTAKE_{field.upper()}_REQUIRED")
    return value.strip()


def _url(value: object, field: str) -> str:
    candidate = _required_text(value, field)
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"CURATED_INTAKE_{field.upper()}_INVALID")
    return candidate


def _mapping(value: object, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"CURATED_INTAKE_{field.upper()}_INVALID")
    return dict(value)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def prepare_curated_written_batch(payload: Mapping[str, Any]) -> PreparedBatch:
    batch_id = _required_text(payload.get("batch_id"), "batch_id")
    extraction_model = _required_text(payload.get("extraction_model"), "extraction_model")
    extraction_version = _required_text(
        payload.get("extraction_version"), "extraction_version"
    )
    raw_contents = payload.get("contents")
    if not isinstance(raw_contents, list) or not raw_contents:
        raise ValueError("CURATED_INTAKE_CONTENTS_REQUIRED")

    seen_content_ids: set[str] = set()
    seen_claim_ids: set[str] = set()
    prepared_contents: list[PreparedContent] = []

    for raw_content in raw_contents:
        if not isinstance(raw_content, Mapping):
            raise ValueError("CURATED_INTAKE_CONTENT_INVALID")
        content_id = _required_text(raw_content.get("id"), "content_id")
        if content_id in seen_content_ids:
            raise ValueError("CURATED_INTAKE_CONTENT_ID_DUPLICATE")
        seen_content_ids.add(content_id)
        source = _mapping(raw_content.get("source"), "source")
        source_id = _required_text(source.get("id"), "source_id")
        source_name = _required_text(source.get("name"), "source_name")
        source_url = _url(source.get("url"), "source_url")
        canonical_url = _url(raw_content.get("url"), "canonical_url")
        title = _required_text(raw_content.get("title"), "title")
        published_at = _required_text(raw_content.get("published_at"), "published_at")
        person_id = _required_text(raw_content.get("person_id"), "person_id")
        content_metadata = _mapping(raw_content.get("metadata"), "content_metadata")
        promotion_capture = None
        raw_promotion_capture = raw_content.get("promotion_capture")
        if raw_promotion_capture is not None:
            capture = _mapping(raw_promotion_capture, "promotion_capture")
            capture_record = ContentCaptureRecord(
                id=_required_text(capture.get("id"), "promotion_capture_id"),
                content_id=content_id,
                observed_at=_required_text(capture.get("observed_at"), "promotion_capture_observed_at"),
                final_url=_url(capture.get("final_url") or canonical_url, "promotion_capture_final_url"),
                content_sha256=_required_text(capture.get("content_sha256"), "promotion_capture_content_sha256"),
                retrieval_method=_required_text(capture.get("retrieval_method"), "promotion_capture_retrieval_method"),
                retrieval_version=_required_text(capture.get("retrieval_version"), "promotion_capture_retrieval_version"),
                body_ref=(str(capture.get("body_ref")).strip() if capture.get("body_ref") else None),
                rights_status=str(capture.get("rights_status") or "UNKNOWN"),
                retention_class=str(capture.get("retention_class") or "DURABLE_PROVENANCE"),
                metadata=_mapping(capture.get("metadata"), "promotion_capture_metadata"),
            )
            promotion_capture = PreparedPromotionCapture(
                capture_id=capture_record.id,
                observed_at=capture_record.observed_at,
                final_url=capture_record.final_url,
                content_sha256=capture_record.content_sha256,
                retrieval_method=capture_record.retrieval_method,
                retrieval_version=capture_record.retrieval_version,
                rights_status=capture_record.rights_status,
                retention_class=capture_record.retention_class,
                body_ref=capture_record.body_ref,
                metadata=dict(capture_record.metadata),
            )

        raw_claims = raw_content.get("claims")
        if not isinstance(raw_claims, list) or not raw_claims:
            raise ValueError("CURATED_INTAKE_CLAIMS_REQUIRED")
        claims: list[PreparedClaim] = []
        for raw_claim in raw_claims:
            if not isinstance(raw_claim, Mapping):
                raise ValueError("CURATED_INTAKE_CLAIM_INVALID")
            claim_id = _required_text(raw_claim.get("id"), "claim_id")
            if claim_id in seen_claim_ids:
                raise ValueError("CURATED_INTAKE_CLAIM_ID_DUPLICATE")
            seen_claim_ids.add(claim_id)
            normalized_claim = _required_text(
                raw_claim.get("normalized_claim"), "normalized_claim"
            )
            claim_type = _required_text(raw_claim.get("claim_type"), "claim_type")
            statement_date = _required_text(
                raw_claim.get("statement_date"), "statement_date"
            )
            check_worthy = raw_claim.get("check_worthy")
            if not isinstance(check_worthy, bool):
                raise ValueError("CURATED_INTAKE_CHECK_WORTHY_INVALID")
            quote_text = _required_text(raw_claim.get("quote_text"), "quote_text")
            quote_sha256 = _sha256_text(quote_text)
            quote_start_char = raw_claim.get("quote_start_char")
            quote_end_char = raw_claim.get("quote_end_char")
            if (quote_start_char is None) != (quote_end_char is None):
                raise ValueError("CURATED_INTAKE_QUOTE_POSITION_PAIR_REQUIRED")
            if quote_start_char is not None:
                if (
                    not isinstance(quote_start_char, int)
                    or isinstance(quote_start_char, bool)
                    or not isinstance(quote_end_char, int)
                    or isinstance(quote_end_char, bool)
                    or quote_start_char < 0
                    or quote_end_char <= quote_start_char
                ):
                    raise ValueError("CURATED_INTAKE_QUOTE_POSITION_INVALID")
            if promotion_capture is not None and quote_start_char is None:
                raise ValueError("CURATED_PROMOTION_QUOTE_POSITION_REQUIRED")
            claim_metadata = _mapping(raw_claim.get("metadata"), "claim_metadata")
            claim_metadata = {
                **claim_metadata,
                "intake_batch": batch_id,
                "provenance_channel": "written_source_quote",
            }
            source_ref = {
                "url": canonical_url,
                "title": title,
                "published_at": published_at,
            }
            provenance = make_text_provenance_candidate(
                claim_id=claim_id,
                content_id=content_id,
                person_id=person_id,
                selector_type="TEXT_QUOTE_HASH",
                quote_sha256=quote_sha256,
                attribution_method="SOURCE_QUOTE",
                source_ref=source_ref,
            )
            validate_atomic_claim(
                claim_id=claim_id,
                content_id=content_id,
                normalized_claim=normalized_claim,
                claim_type=claim_type,
                statement_date=statement_date,
                check_worthy=check_worthy,
                source_text_provenance_ids=(provenance.candidate_id,),
                metadata=claim_metadata,
            )
            claims.append(
                PreparedClaim(
                    claim_id=claim_id,
                    content_id=content_id,
                    person_id=person_id,
                    normalized_claim=normalized_claim,
                    claim_type=claim_type,
                    statement_date=statement_date,
                    check_worthy=check_worthy,
                    quote_sha256=quote_sha256,
                    provenance_id=provenance.candidate_id,
                    source_ref=source_ref,
                    metadata=claim_metadata,
                    private_quote_text=quote_text,
                    quote_start_char=quote_start_char,
                    quote_end_char=quote_end_char,
                )
            )

        prepared_contents.append(
            PreparedContent(
                content_id=content_id,
                source_id=source_id,
                source_name=source_name,
                source_url=source_url,
                canonical_url=canonical_url,
                title=title,
                published_at=published_at,
                person_id=person_id,
                metadata={**content_metadata, "intake_batch": batch_id},
                claims=tuple(claims),
                promotion_capture=promotion_capture,
            )
        )

    return PreparedBatch(
        batch_id=batch_id,
        extraction_model=extraction_model,
        extraction_version=extraction_version,
        contents=tuple(prepared_contents),
    )


def _upsert_source(store: QueueRuntimeStore, content: PreparedContent) -> str:
    return store.run(
        """
        WITH inserted AS (
            INSERT INTO source (
                id, canonical_name, source_type, canonical_url, language, country_code
            ) VALUES (
                :'source_id', :'source_name', 'MEDIA', :'source_url', 'it', 'IT'
            )
            ON CONFLICT (id) DO NOTHING
            RETURNING id
        ), existing AS (
            SELECT id FROM source
            WHERE id = :'source_id'
              AND canonical_name = :'source_name'
              AND canonical_url = :'source_url'
        )
        SELECT CASE
            WHEN EXISTS(SELECT 1 FROM inserted) THEN 'inserted'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'existing'
            ELSE 'conflict'
        END;
        """,
        source_id=content.source_id,
        source_name=content.source_name,
        source_url=content.source_url,
    )


def _upsert_content(store: QueueRuntimeStore, content: PreparedContent) -> str:
    return store.run(
        """
        WITH eligible AS (
            SELECT id FROM person WHERE id = :'person_id' AND is_public_figure = true
        ), inserted AS (
            INSERT INTO content_item (
                id, source_id, source_external_id, canonical_url, title, language,
                published_at, rights_status, processing_status, metadata
            )
            SELECT
                :'content_id', :'source_id', :'content_id', :'canonical_url', :'title',
                'it', :'published_at'::timestamptz, 'UNKNOWN', 'REVIEW_REQUIRED',
                :'metadata'::jsonb
            FROM eligible
            ON CONFLICT (id) DO NOTHING
            RETURNING id
        ), existing AS (
            SELECT item.id FROM content_item item
            JOIN eligible ON true
            WHERE item.id = :'content_id'
              AND item.source_id = :'source_id'
              AND item.canonical_url = :'canonical_url'
        )
        SELECT CASE
            WHEN EXISTS(SELECT 1 FROM inserted) THEN 'inserted'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'existing'
            ELSE 'conflict'
        END;
        """,
        content_id=content.content_id,
        source_id=content.source_id,
        canonical_url=content.canonical_url,
        title=content.title,
        published_at=content.published_at,
        person_id=content.person_id,
        metadata=json.dumps(content.metadata, ensure_ascii=False, separators=(",", ":")),
    )


def _upsert_claim(
    store: QueueRuntimeStore,
    batch: PreparedBatch,
    claim: PreparedClaim,
) -> str:
    temporal_scope = {"statement_date": claim.statement_date}
    return store.run(
        """
        WITH eligible AS (
            SELECT item.id FROM content_item item
            JOIN person speaker ON speaker.id = :'person_id'
            WHERE item.id = :'content_id' AND speaker.is_public_figure = true
        ), inserted AS (
            INSERT INTO atomic_claim (
                id, content_id, speaker_person_id, normalized_claim, claim_type,
                claim_type_version, temporal_scope, check_worthy, extraction_model,
                extraction_version, metadata
            )
            SELECT
                :'claim_id', :'content_id', :'person_id', :'normalized_claim',
                :'claim_type', :'claim_type_version', :'temporal_scope'::jsonb,
                :'check_worthy'::boolean, :'extraction_model', :'extraction_version',
                :'metadata'::jsonb
            FROM eligible
            ON CONFLICT (id) DO NOTHING
            RETURNING id
        ), existing AS (
            SELECT claim.id FROM atomic_claim claim
            JOIN eligible ON eligible.id = claim.content_id
            WHERE claim.id = :'claim_id'
              AND claim.speaker_person_id = :'person_id'
              AND claim.normalized_claim = :'normalized_claim'
              AND claim.claim_type = :'claim_type'
              AND claim.claim_type_version = :'claim_type_version'
              AND claim.temporal_scope = :'temporal_scope'::jsonb
              AND claim.check_worthy = :'check_worthy'::boolean
              AND claim.extraction_model = :'extraction_model'
              AND claim.extraction_version = :'extraction_version'
              AND claim.metadata = :'metadata'::jsonb
        )
        SELECT CASE
            WHEN EXISTS(SELECT 1 FROM inserted) THEN 'inserted'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'existing'
            ELSE 'conflict'
        END;
        """,
        claim_id=claim.claim_id,
        content_id=claim.content_id,
        person_id=claim.person_id,
        normalized_claim=claim.normalized_claim,
        claim_type=claim.claim_type,
        claim_type_version=CLAIM_TYPE_VERSION,
        temporal_scope=json.dumps(temporal_scope, separators=(",", ":")),
        check_worthy=str(claim.check_worthy).lower(),
        extraction_model=batch.extraction_model,
        extraction_version=batch.extraction_version,
        metadata=json.dumps(claim.metadata, ensure_ascii=False, separators=(",", ":")),
    )


def apply_curated_written_batch(
    store: QueueRuntimeStore,
    batch: PreparedBatch,
    *,
    actor_ref: str,
    approve_attribution: bool,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "batch_id": batch.batch_id,
        "approve_attribution": approve_attribution,
        "contents": [],
    }
    for content in batch.contents:
        source_state = _upsert_source(store, content)
        content_state = _upsert_content(store, content)
        if source_state == "conflict" or content_state == "conflict":
            raise RuntimeError(
                f"CURATED_INTAKE_CONTENT_CONFLICT:{content.content_id}"
            )
        content_receipt = {
            "content_id": content.content_id,
            "source_state": source_state,
            "content_state": content_state,
            "claims": [],
        }
        for claim in content.claims:
            claim_state = _upsert_claim(store, batch, claim)
            if claim_state == "conflict":
                raise RuntimeError(f"CURATED_INTAKE_CLAIM_CONFLICT:{claim.claim_id}")
            provenance = make_text_provenance_candidate(
                claim_id=claim.claim_id,
                content_id=claim.content_id,
                person_id=claim.person_id,
                selector_type="TEXT_QUOTE_HASH",
                quote_sha256=claim.quote_sha256,
                attribution_method="SOURCE_QUOTE",
                source_ref=claim.source_ref,
            )
            if not store.insert_claim_text_provenance(
                candidate_id=provenance.candidate_id,
                claim_id=provenance.claim_id,
                content_id=provenance.content_id,
                person_id=provenance.person_id,
                selector_type=provenance.selector_type,
                quote_sha256=provenance.quote_sha256,
                source_sha256=provenance.source_sha256,
                start_char=provenance.start_char,
                end_char=provenance.end_char,
                attribution_method=provenance.attribution_method,
                attribution_version=provenance.attribution_version,
                source_ref=provenance.source_ref,
                metadata={"intake_batch": batch.batch_id},
            ):
                raise RuntimeError(
                    f"CURATED_INTAKE_PROVENANCE_REFUSED:{claim.claim_id}"
                )
            provenance_status = "CANDIDATE"
            if approve_attribution:
                reason = f"curated written-source quote checked for {batch.batch_id}"
                event_id = deterministic_review_event_id(
                    entity_type="CLAIM_TEXT_PROVENANCE",
                    entity_id=provenance.candidate_id,
                    action="APPROVED",
                    actor_ref=actor_ref,
                    reason=reason,
                )
                if not store.approve_claim_text_provenance_with_review(
                    candidate_id=provenance.candidate_id,
                    event_id=event_id,
                    actor_ref=actor_ref,
                    reason=reason,
                ):
                    raise RuntimeError(
                        f"CURATED_INTAKE_PROVENANCE_APPROVAL_REFUSED:{claim.claim_id}"
                    )
                provenance_status = "APPROVED"
            content_receipt["claims"].append(
                {
                    "claim_id": claim.claim_id,
                    "claim_state": claim_state,
                    "quote_sha256": claim.quote_sha256,
                    "provenance_id": provenance.candidate_id,
                    "provenance_status": provenance_status,
                    "check_worthy": claim.check_worthy,
                }
            )
        receipt["contents"].append(content_receipt)
    return receipt


_APPROVE_COMPAT_STATEMENT_SQL = """
WITH current AS (
    SELECT id, status FROM statement_candidate WHERE id=:'entity_id' FOR UPDATE
), logged AS (
    INSERT INTO review_event (id, entity_type, entity_id, action, actor_ref, reason, metadata)
    SELECT :'event_id', 'STATEMENT_CANDIDATE', id, 'APPROVED', :'actor_ref',
           NULLIF(:'reason',''), :'metadata'::jsonb
    FROM current WHERE status IN ('CANDIDATE','APPROVED')
    ON CONFLICT (id) DO NOTHING
    RETURNING entity_id
), review_ok AS (
    SELECT entity_id FROM logged
    UNION ALL
    SELECT entity_id FROM review_event
    WHERE id=:'event_id' AND entity_type='STATEMENT_CANDIDATE'
      AND entity_id=:'entity_id' AND action='APPROVED'
), updated AS (
    UPDATE statement_candidate target
    SET status='APPROVED'
    WHERE target.id=:'entity_id'
      AND target.status IN ('CANDIDATE','APPROVED')
      AND EXISTS (SELECT 1 FROM review_ok)
    RETURNING target.id
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM updated) THEN 'APPROVED' ELSE 'CONFLICT' END;
""".strip()

_REVIEW_COMPAT_CLAIM_SQL = """
WITH current AS (
    SELECT id FROM claim_candidate
    WHERE id=:'entity_id' AND status IN ('CANDIDATE','DUPLICATE','PROMOTED')
), inserted AS (
    INSERT INTO review_event (id, entity_type, entity_id, action, actor_ref, reason, metadata)
    SELECT :'event_id', 'CLAIM_CANDIDATE', id, 'APPROVED', :'actor_ref',
           NULLIF(:'reason',''), :'metadata'::jsonb
    FROM current
    ON CONFLICT (id) DO NOTHING
    RETURNING entity_id
), existing AS (
    SELECT entity_id FROM review_event
    WHERE id=:'event_id' AND entity_type='CLAIM_CANDIDATE'
      AND entity_id=:'entity_id' AND action='APPROVED'
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) OR EXISTS(SELECT 1 FROM existing)
    THEN 'APPROVED' ELSE 'CONFLICT'
END;
""".strip()


def _compat_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _compat_state(raw: str, *, object_name: str) -> str:
    state = str(raw or "").strip().upper()
    if state not in {"INSERTED", "EXISTING"}:
        raise RuntimeError(f"CURATED_PROMOTION_{object_name}_CONFLICT")
    return state


def _insert_promotion_capture(store: object, content: PreparedContent) -> str:
    prepared = content.promotion_capture
    if prepared is None:
        raise ValueError("CURATED_PROMOTION_CAPTURE_REQUIRED")
    record = ContentCaptureRecord(
        id=prepared.capture_id,
        content_id=content.content_id,
        observed_at=prepared.observed_at,
        final_url=prepared.final_url,
        content_sha256=prepared.content_sha256,
        retrieval_method=prepared.retrieval_method,
        retrieval_version=prepared.retrieval_version,
        body_ref=prepared.body_ref,
        rights_status=prepared.rights_status,
        retention_class=prepared.retention_class,
        metadata={**prepared.metadata, "intake_batch": content.metadata.get("intake_batch")},
    )
    raw = store.run(
        INSERT_CONTENT_CAPTURE_SQL_V1,
        id=record.id,
        content_id=record.content_id,
        observed_at=record.observed_at,
        final_url=record.final_url,
        media_type=record.media_type or "",
        content_sha256=record.content_sha256,
        body_ref=record.body_ref or "",
        retrieval_method=record.retrieval_method,
        retrieval_version=record.retrieval_version,
        parser_method=record.parser_method or "",
        parser_version=record.parser_version or "",
        rights_status=record.rights_status,
        retention_class=record.retention_class,
        hold_status=record.hold_status,
        archive_status=record.archive_status,
        archive_provider=record.archive_provider or "",
        archive_requested_at=record.archive_requested_at or "",
        archive_completed_at=record.archive_completed_at or "",
        archive_receipt=_compat_json(record.archive_receipt),
        body_purged_at=record.body_purged_at or "",
        purge_reason=record.purge_reason or "",
        purge_receipt=_compat_json(record.purge_receipt),
        status=record.status,
        metadata=_compat_json(record.metadata),
    )
    return _compat_state(raw, object_name="CAPTURE")


def _prepare_promotion_candidate_records(
    batch: PreparedBatch,
    content: PreparedContent,
    claim: PreparedClaim,
) -> tuple[PassageRecord, StatementCandidateRecord, ClaimCandidateRecord]:
    capture = content.promotion_capture
    if capture is None:
        raise ValueError("CURATED_PROMOTION_CAPTURE_REQUIRED")
    if claim.quote_start_char is None or claim.quote_end_char is None:
        raise ValueError("CURATED_PROMOTION_QUOTE_POSITION_REQUIRED")
    passage_id = deterministic_corpus_id(
        "passage",
        content.content_id,
        capture.capture_id,
        str(claim.quote_start_char),
        str(claim.quote_end_char),
        claim.quote_sha256,
    )
    passage = PassageRecord(
        id=passage_id,
        content_id=content.content_id,
        capture_id=capture.capture_id,
        selector_type="TEXT_POSITION",
        start_char=claim.quote_start_char,
        end_char=claim.quote_end_char,
        text_sha256=claim.quote_sha256,
        private_text=claim.private_quote_text,
        language="it",
        extraction_method="CURATED_SOURCE_QUOTE",
        extraction_version=batch.extraction_version,
        metadata={"intake_batch": batch.batch_id, "legacy_requested_claim_id": claim.claim_id},
    )
    statement_id = deterministic_corpus_id(
        "statement-candidate", content.content_id, passage.id, claim.quote_sha256
    )
    statement = StatementCandidateRecord(
        id=statement_id,
        content_id=content.content_id,
        passage_ids=(passage.id,),
        statement_text_hash=claim.quote_sha256,
        normalized_statement=claim.normalized_claim,
        speaker_person_id=claim.person_id,
        statement_at=None,
        attribution_method="SOURCE_QUOTE",
        extraction_model=batch.extraction_model,
        extraction_version=batch.extraction_version,
        status="CANDIDATE",
        metadata={"intake_batch": batch.batch_id, "legacy_requested_claim_id": claim.claim_id},
    )
    candidate_id = deterministic_corpus_id(
        "claim-candidate", claim.claim_id, statement.id, batch.extraction_version
    )
    candidate = ClaimCandidateRecord(
        id=candidate_id,
        statement_candidate_id=statement.id,
        content_id=content.content_id,
        normalized_claim=claim.normalized_claim,
        proposed_claim_type=claim.claim_type,
        temporal_scope={"statement_date": claim.statement_date},
        check_worthy=claim.check_worthy,
        extraction_model=batch.extraction_model,
        extraction_version=batch.extraction_version,
        status="CANDIDATE",
        metadata={**claim.metadata, "legacy_requested_claim_id": claim.claim_id},
    )
    return passage, statement, candidate


def _insert_compat_passage(store: object, record: PassageRecord) -> str:
    raw = store.run(
        INSERT_PASSAGE_SQL_V1,
        id=record.id,
        content_id=record.content_id,
        capture_id=record.capture_id or "",
        canonical_segment_id=record.canonical_segment_id or "",
        selector_type=record.selector_type,
        start_char="" if record.start_char is None else record.start_char,
        end_char="" if record.end_char is None else record.end_char,
        page_start="" if record.page_start is None else record.page_start,
        page_end="" if record.page_end is None else record.page_end,
        text_sha256=record.text_sha256,
        private_text=record.private_text or "",
        language=record.language or "",
        extraction_method=record.extraction_method,
        extraction_version=record.extraction_version,
        metadata=_compat_json(record.metadata),
    )
    return _compat_state(raw, object_name="PASSAGE")


def _insert_compat_statement(store: object, record: StatementCandidateRecord) -> str:
    raw = store.run(
        INSERT_STATEMENT_CANDIDATE_SQL_V1,
        id=record.id,
        content_id=record.content_id,
        speaker_person_id=record.speaker_person_id or "",
        statement_text_hash=record.statement_text_hash,
        normalized_statement=record.normalized_statement,
        statement_at=record.statement_at or "",
        attribution_method=record.attribution_method or "",
        extraction_model=record.extraction_model or "",
        extraction_version=record.extraction_version,
        status=record.status,
        metadata=_compat_json(record.metadata),
        passage_ids=_compat_json(list(record.passage_ids)),
    )
    return _compat_state(raw, object_name="STATEMENT")


def _insert_compat_claim_candidate(store: object, record: ClaimCandidateRecord) -> str:
    raw = store.run(
        INSERT_CLAIM_CANDIDATE_SQL_V1,
        id=record.id,
        statement_candidate_id=record.statement_candidate_id,
        content_id=record.content_id,
        normalized_claim=record.normalized_claim,
        proposed_claim_type=record.proposed_claim_type,
        claim_type_version=record.claim_type_version,
        temporal_scope=_compat_json(record.temporal_scope),
        check_worthy=str(record.check_worthy).lower(),
        extraction_model=record.extraction_model or "",
        extraction_version=record.extraction_version,
        status=record.status,
        promoted_claim_id=record.promoted_claim_id or "",
        metadata=_compat_json(record.metadata),
    )
    return _compat_state(raw, object_name="CLAIM_CANDIDATE")


def _approve_compat_candidates(
    store: object,
    *,
    statement: StatementCandidateRecord,
    candidate: ClaimCandidateRecord,
    actor_ref: str,
    batch_id: str,
) -> tuple[str, str]:
    statement_reason = f"curated promotion-ready statement checked for {batch_id}"
    statement_event = deterministic_review_event_id(
        entity_type="STATEMENT_CANDIDATE",
        entity_id=statement.id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=statement_reason,
    )
    statement_state = store.run(
        _APPROVE_COMPAT_STATEMENT_SQL,
        entity_id=statement.id,
        event_id=statement_event,
        actor_ref=actor_ref,
        reason=statement_reason,
        metadata=_compat_json({"intake_batch": batch_id}),
    )
    if str(statement_state).strip().upper() != "APPROVED":
        raise RuntimeError("CURATED_PROMOTION_STATEMENT_REVIEW_CONFLICT")

    claim_reason = f"curated promotion-ready claim checked for {batch_id}"
    claim_event = deterministic_review_event_id(
        entity_type="CLAIM_CANDIDATE",
        entity_id=candidate.id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=claim_reason,
    )
    claim_state = store.run(
        _REVIEW_COMPAT_CLAIM_SQL,
        entity_id=candidate.id,
        event_id=claim_event,
        actor_ref=actor_ref,
        reason=claim_reason,
        metadata=_compat_json({"intake_batch": batch_id}),
    )
    if str(claim_state).strip().upper() != "APPROVED":
        raise RuntimeError("CURATED_PROMOTION_CLAIM_REVIEW_CONFLICT")
    return statement_event, claim_event


def apply_curated_written_batch_via_promotion(
    store: object,
    batch: PreparedBatch,
    *,
    actor_ref: str,
) -> dict[str, Any]:
    """Ingest promotion-ready curated written records through DP-117.

    Historical manifests without whole-capture hashes and exact quote offsets remain on
    the legacy direct replay path; this adapter refuses to fabricate those provenance
    fields. New promotion-ready curated records create Corpus candidates, explicit review
    events and then call the single ClaimCandidate -> AtomicClaim seam.
    """
    for content in batch.contents:
        if content.promotion_capture is None:
            raise ValueError("CURATED_PROMOTION_CAPTURE_REQUIRED")
        for claim in content.claims:
            if claim.quote_start_char is None or claim.quote_end_char is None:
                raise ValueError("CURATED_PROMOTION_QUOTE_POSITION_REQUIRED")

    receipt: dict[str, Any] = {
        "batch_id": batch.batch_id,
        "mode": "CLAIM_CANDIDATE_PROMOTION_V1",
        "contents": [],
    }
    for content in batch.contents:
        source_state = _upsert_source(store, content)
        content_state = _upsert_content(store, content)
        if source_state == "conflict" or content_state == "conflict":
            raise RuntimeError(f"CURATED_PROMOTION_CONTENT_CONFLICT:{content.content_id}")
        capture_state = _insert_promotion_capture(store, content)
        content_receipt = {
            "content_id": content.content_id,
            "source_state": source_state,
            "content_state": content_state,
            "capture_state": capture_state,
            "claims": [],
        }
        for claim in content.claims:
            passage, statement, candidate = _prepare_promotion_candidate_records(
                batch, content, claim
            )
            passage_state = _insert_compat_passage(store, passage)
            statement_state = _insert_compat_statement(store, statement)
            candidate_state = _insert_compat_claim_candidate(store, candidate)
            statement_event, claim_event = _approve_compat_candidates(
                store,
                statement=statement,
                candidate=candidate,
                actor_ref=actor_ref,
                batch_id=batch.batch_id,
            )
            promotion = promote_claim_candidate(
                store,
                PromotionRequest(
                    candidate_id=candidate.id,
                    provenance_channel="WRITTEN",
                    actor_ref=actor_ref,
                    reason=f"curated promotion-ready claim checked for {batch.batch_id}",
                ),
            )
            if not promotion.promoted:
                raise RuntimeError(
                    f"CURATED_PROMOTION_REFUSED:{claim.claim_id}:{promotion.reason_code}"
                )
            content_receipt["claims"].append(
                {
                    "legacy_requested_claim_id": claim.claim_id,
                    "candidate_id": candidate.id,
                    "passage_id": passage.id,
                    "passage_state": passage_state,
                    "statement_state": statement_state,
                    "candidate_state": candidate_state,
                    "statement_review_event": statement_event,
                    "claim_review_event": claim_event,
                    "promotion_id": promotion.promotion_id,
                    "target_claim_id": promotion.target_claim_id,
                    "promotion_action": promotion.action,
                    "promotion_reason_code": promotion.reason_code,
                    "promotion_replayed": promotion.replayed,
                    "provenance_refs": list(promotion.provenance_refs),
                }
            )
        receipt["contents"].append(content_receipt)
    return receipt


__all__ = [
    "PreparedBatch",
    "PreparedClaim",
    "PreparedContent",
    "PreparedPromotionCapture",
    "apply_curated_written_batch",
    "apply_curated_written_batch_via_promotion",
    "prepare_curated_written_batch",
]

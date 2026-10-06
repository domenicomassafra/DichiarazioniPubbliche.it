from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping

from dichiarazioni_pubbliche.existing_factcheck import ExistingFactCheckRecord
from dichiarazioni_pubbliche.policy.excerpt_policy import (
    ExcerptDecision,
    ExcerptRequest,
    RightsStatus,
    decide_excerpt,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


EXISTING_FACTCHECK_MIRROR_VERSION = "existing-factcheck-mirror-v1"


class ExistingFactCheckMirrorError(ValueError):
    pass


@dataclass(frozen=True)
class PersistedFactCheckMirror:
    mirror_id: str
    lineage_id: str
    upstream_record_id: str
    version_id: str
    source_version: str
    source_content_sha256: str
    supersedes_version_id: str | None
    version_state: str
    provider_id: str
    source_external_id: str
    review_url: str
    rights_status: str
    research_assignment_id: str
    discovery_attempt_id: str
    discovery_hit_id: str
    provider_receipt_sha256: str
    normalized_record_sha256: str
    normalized_record: dict[str, Any]
    persistence_version: str = EXISTING_FACTCHECK_MIRROR_VERSION


@dataclass(frozen=True)
class FactCheckMirrorPublicMetadata:
    lineage_id: str
    version_id: str
    source_version: str
    version_state: str
    provider_id: str
    review_url: str
    review_publisher_name: str | None
    review_publisher_site: str | None
    review_date: str | None
    persistence_version: str = EXISTING_FACTCHECK_MIRROR_VERSION


def _text(value: object, field: str, *, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExistingFactCheckMirrorError(f"FACTCHECK_MIRROR_{field}_REQUIRED")
    if len(text) > maximum or "\x00" in text:
        raise ExistingFactCheckMirrorError(f"FACTCHECK_MIRROR_{field}_INVALID")
    return text


def _sha256_text(value: object, field: str) -> str:
    text = _text(value, field, maximum=64).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ExistingFactCheckMirrorError(f"FACTCHECK_MIRROR_{field}_INVALID")
    return text


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _deterministic_id(prefix: str, *parts: str) -> str:
    return f"{prefix}:" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _rights(value: RightsStatus | str) -> str:
    try:
        return RightsStatus(str(value)).value
    except ValueError as exc:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_RIGHTS_STATUS_INVALID") from exc


def public_mirror_metadata(mirror: PersistedFactCheckMirror) -> FactCheckMirrorPublicMetadata:
    """Return metadata/link-only public material; private ClaimReview body never crosses."""

    record = mirror.normalized_record
    return FactCheckMirrorPublicMetadata(
        lineage_id=mirror.lineage_id,
        version_id=mirror.version_id,
        source_version=mirror.source_version,
        version_state=mirror.version_state,
        provider_id=mirror.provider_id,
        review_url=mirror.review_url,
        review_publisher_name=(
            str(record.get("review_publisher_name")).strip()
            if record.get("review_publisher_name")
            else None
        ),
        review_publisher_site=(
            str(record.get("review_publisher_site")).strip()
            if record.get("review_publisher_site")
            else None
        ),
        review_date=(
            str(record.get("review_date")).strip() if record.get("review_date") else None
        ),
    )


def decide_mirror_excerpt(
    mirror: PersistedFactCheckMirror,
    request: ExcerptRequest,
) -> ExcerptDecision:
    """Apply DP-305 to the exact persisted mirror version without granting rights.

    The caller cannot upgrade rights by passing ``CLEARED``: the persisted mirror rights
    state replaces the request value. Exact URL/version/hash bindings must already match.
    A later rights clearance belongs in DP-305's versioned rights registry, not in this
    append-only mirror lineage.
    """

    if str(request.source_url or "").strip() != mirror.review_url:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXCERPT_SOURCE_URL_MISMATCH")
    if str(request.content_id or "").strip() != mirror.version_id:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXCERPT_CONTENT_ID_MISMATCH")
    if str(request.segment_id or "").strip() != mirror.mirror_id:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXCERPT_SEGMENT_ID_MISMATCH")
    if str(request.transcript_variant_id or "").strip() != mirror.source_version:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXCERPT_SOURCE_VERSION_MISMATCH")
    if str(request.source_content_sha256 or "").lower() != mirror.source_content_sha256:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXCERPT_SOURCE_HASH_MISMATCH")
    if str(request.observed_source_sha256 or "").lower() != mirror.source_content_sha256:
        raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXCERPT_OBSERVED_HASH_MISMATCH")
    return decide_excerpt(replace(request, rights_status=mirror.rights_status))


class ExistingFactCheckMirrorStore(PsqlRuntime):
    def mirror_for_discovery_hit(
        self, discovery_hit_id: str
    ) -> PersistedFactCheckMirror | None:
        hit_id = _text(discovery_hit_id, "DISCOVERY_HIT_ID")
        raw = self.run(
            "SELECT id FROM existing_factcheck_mirror WHERE discovery_hit_id=:'hit_id';",
            hit_id=hit_id,
        )
        return self.read_mirror(raw) if raw else None

    def accepted_discovery_hits(
        self,
        *,
        run_id: str,
        query_id: str,
        adapter_id: str,
    ) -> tuple[dict[str, Any], ...]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'attempt_id', attempt.id,
                'hit_id', hit.id,
                'external_id', hit.external_id,
                'canonical_url', hit.canonical_url,
                'disposition', hit.disposition
            ) ORDER BY hit.ordinal, hit.id)::text, '[]')
            FROM research_discovery_attempt attempt
            JOIN research_discovery_hit hit
              ON hit.attempt_id=attempt.id
             AND hit.run_id=attempt.run_id
             AND hit.query_id=attempt.query_id
            WHERE attempt.run_id=:'run_id'
              AND attempt.query_id=:'query_id'
              AND attempt.adapter_id=:'adapter_id'
              AND attempt.status='HEALTHY'
              AND hit.disposition IN ('NEW_CONTENT', 'EXISTING_CONTENT')
              AND hit.external_id IS NOT NULL;
            """,
            run_id=run_id,
            query_id=query_id,
            adapter_id=adapter_id,
        )
        parsed = json.loads(raw or "[]")
        if not isinstance(parsed, list):
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_DISCOVERY_HITS_INVALID")
        return tuple(dict(row) for row in parsed if isinstance(row, Mapping))

    def _retrieval_binding(
        self,
        *,
        discovery_attempt_id: str,
        discovery_hit_id: str,
    ) -> dict[str, Any]:
        raw = self.run(
            """
            SELECT json_build_object(
                'attempt_id', attempt.id,
                'attempt_status', attempt.status,
                'adapter_id', attempt.adapter_id,
                'adapter_version', attempt.adapter_version,
                'provider_receipt', attempt.provider_receipt,
                'run_id', attempt.run_id,
                'query_id', attempt.query_id,
                'query_metadata', query.metadata,
                'hit_id', hit.id,
                'hit_disposition', hit.disposition,
                'hit_url', hit.canonical_url,
                'hit_external_id', hit.external_id
            )::text
            FROM research_discovery_attempt attempt
            JOIN research_discovery_query query ON query.id=attempt.query_id
            JOIN research_discovery_hit hit
              ON hit.id=:'hit_id'
             AND hit.attempt_id=attempt.id
             AND hit.run_id=attempt.run_id
             AND hit.query_id=attempt.query_id
            WHERE attempt.id=:'attempt_id';
            """,
            attempt_id=discovery_attempt_id,
            hit_id=discovery_hit_id,
        )
        if not raw:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_DISCOVERY_BINDING_MISSING")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_DISCOVERY_BINDING_INVALID")
        return value

    def persist_mirror(
        self,
        record: ExistingFactCheckRecord,
        *,
        upstream_record_id: str,
        source_external_id: str,
        source_version: str,
        source_content_sha256: str,
        research_assignment_id: str,
        discovery_attempt_id: str,
        discovery_hit_id: str,
        rights_status: RightsStatus | str = RightsStatus.UNKNOWN,
        supersedes_source_version: str | None = None,
    ) -> PersistedFactCheckMirror:
        upstream = _text(upstream_record_id, "UPSTREAM_RECORD_ID")
        external = _text(source_external_id, "SOURCE_EXTERNAL_ID")
        version = _text(source_version, "SOURCE_VERSION")
        content_sha = _sha256_text(source_content_sha256, "SOURCE_CONTENT_SHA256")
        assignment = _text(research_assignment_id, "RESEARCH_ASSIGNMENT_ID")
        attempt_id = _text(discovery_attempt_id, "DISCOVERY_ATTEMPT_ID")
        hit_id = _text(discovery_hit_id, "DISCOVERY_HIT_ID")
        rights = _rights(rights_status)
        supersedes = (
            _text(supersedes_source_version, "SUPERSEDES_SOURCE_VERSION")
            if supersedes_source_version is not None
            else None
        )
        provider = _text(record.provider_id, "PROVIDER_ID")
        review_url = _text(record.review_url, "REVIEW_URL")

        binding = self._retrieval_binding(
            discovery_attempt_id=attempt_id,
            discovery_hit_id=hit_id,
        )
        if binding.get("attempt_status") != "HEALTHY":
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_DISCOVERY_ATTEMPT_NOT_HEALTHY")
        if binding.get("hit_disposition") not in {"NEW_CONTENT", "EXISTING_CONTENT"}:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_DISCOVERY_HIT_NOT_ACCEPTED")
        if str(binding.get("adapter_id") or "") != provider:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_PROVIDER_BINDING_MISMATCH")
        if str(binding.get("hit_url") or "") != review_url:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_REVIEW_URL_BINDING_MISMATCH")
        bound_external = str(binding.get("hit_external_id") or "").strip()
        if bound_external and bound_external != external:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXTERNAL_ID_BINDING_MISMATCH")
        query_metadata = binding.get("query_metadata")
        if not isinstance(query_metadata, Mapping):
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_QUERY_METADATA_INVALID")
        if str(query_metadata.get("lane") or "") != "EXISTING_FACT_CHECK":
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_RESEARCH_LANE_MISMATCH")
        if str(query_metadata.get("research_assignment_id") or "") != assignment:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_ASSIGNMENT_BINDING_MISMATCH")

        provider_receipt = binding.get("provider_receipt")
        if not isinstance(provider_receipt, Mapping):
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_PROVIDER_RECEIPT_INVALID")
        receipt_sha = _fingerprint(dict(provider_receipt))
        normalized_record = asdict(record)
        normalized_sha = _fingerprint(normalized_record)

        lineage_id = _deterministic_id("factcheck-lineage", upstream)
        self.run(
            """
            INSERT INTO existing_factcheck_lineage (id, upstream_record_id)
            VALUES (:'lineage_id', :'upstream_record_id')
            ON CONFLICT (upstream_record_id) DO NOTHING;
            """,
            lineage_id=lineage_id,
            upstream_record_id=upstream,
        )
        saved_lineage = self.run(
            "SELECT id FROM existing_factcheck_lineage WHERE upstream_record_id=:'upstream_record_id';",
            upstream_record_id=upstream,
        )
        if saved_lineage != lineage_id:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_LINEAGE_CONFLICT")

        existing_raw = self.run(
            """
            SELECT json_build_object(
                'id', version.id,
                'source_content_sha256', version.source_content_sha256,
                'supersedes_version_id', version.supersedes_version_id,
                'supersedes_source_version', parent.source_version
            )::text
            FROM existing_factcheck_version version
            LEFT JOIN existing_factcheck_version parent ON parent.id=version.supersedes_version_id
            WHERE version.lineage_id=:'lineage_id' AND version.source_version=:'source_version';
            """,
            lineage_id=lineage_id,
            source_version=version,
        )
        if existing_raw:
            existing = json.loads(existing_raw)
            if existing.get("source_content_sha256") != content_sha:
                raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_SOURCE_VERSION_HASH_CONFLICT")
            if supersedes is not None and existing.get("supersedes_source_version") != supersedes:
                raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_SUPERSEDES_CONFLICT")
            version_id = str(existing["id"])
        else:
            current_raw = self.run(
                """
                SELECT json_build_object('id', current.id, 'source_version', current.source_version)::text
                FROM existing_factcheck_version current
                WHERE current.lineage_id=:'lineage_id'
                  AND NOT EXISTS (
                      SELECT 1 FROM existing_factcheck_version child
                      WHERE child.supersedes_version_id=current.id
                  )
                ORDER BY current.created_at DESC, current.id DESC
                LIMIT 1;
                """,
                lineage_id=lineage_id,
            )
            current = json.loads(current_raw) if current_raw else None
            if current is None:
                if supersedes is not None:
                    raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_SUPERSEDES_VERSION_MISSING")
                parent_id = None
            else:
                if supersedes is None:
                    raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_SUPERSEDES_REQUIRED")
                if str(current.get("source_version") or "") != supersedes:
                    raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_SUPERSEDES_NOT_CURRENT")
                parent_id = str(current["id"])
            version_id = _deterministic_id("factcheck-version", lineage_id, version, content_sha)
            try:
                self.run(
                    """
                    INSERT INTO existing_factcheck_version (
                        id, lineage_id, source_version, source_content_sha256, supersedes_version_id
                    ) VALUES (
                        :'id', :'lineage_id', :'source_version', :'source_content_sha256',
                        NULLIF(:'supersedes_version_id','')
                    );
                    """,
                    id=version_id,
                    lineage_id=lineage_id,
                    source_version=version,
                    source_content_sha256=content_sha,
                    supersedes_version_id=parent_id or "",
                )
            except RuntimeError as exc:
                raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_VERSION_CONFLICT") from exc

        mirror_id = _deterministic_id("factcheck-mirror", provider, external, version)
        existing_mirror_raw = self.run(
            """
            SELECT json_build_object(
                'id', id,
                'version_id', version_id,
                'review_url', review_url,
                'rights_status', rights_status,
                'research_assignment_id', research_assignment_id,
                'discovery_attempt_id', discovery_attempt_id,
                'discovery_hit_id', discovery_hit_id,
                'provider_receipt_sha256', provider_receipt_sha256,
                'normalized_record_sha256', normalized_record_sha256
            )::text
            FROM existing_factcheck_mirror
            WHERE provider_id=:'provider_id'
              AND source_external_id=:'source_external_id'
              AND source_version=:'source_version';
            """,
            provider_id=provider,
            source_external_id=external,
            source_version=version,
        )
        expected = {
            "id": mirror_id,
            "version_id": version_id,
            "review_url": review_url,
            "rights_status": rights,
            "research_assignment_id": assignment,
            "discovery_attempt_id": attempt_id,
            "discovery_hit_id": hit_id,
            "provider_receipt_sha256": receipt_sha,
            "normalized_record_sha256": normalized_sha,
        }
        if existing_mirror_raw:
            if json.loads(existing_mirror_raw) != expected:
                raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXTERNAL_ID_CONFLICT")
        else:
            try:
                self.run(
                    """
                    INSERT INTO existing_factcheck_mirror (
                        id, version_id, provider_id, source_external_id, source_version,
                        review_url, rights_status, research_assignment_id,
                        discovery_attempt_id, discovery_hit_id, provider_receipt_sha256,
                        normalized_record_sha256, normalized_record
                    ) VALUES (
                        :'id', :'version_id', :'provider_id', :'source_external_id', :'source_version',
                        :'review_url', :'rights_status', :'research_assignment_id',
                        :'discovery_attempt_id', :'discovery_hit_id', :'provider_receipt_sha256',
                        :'normalized_record_sha256', :'normalized_record'::jsonb
                    );
                    """,
                    **expected,
                    provider_id=provider,
                    source_external_id=external,
                    source_version=version,
                    normalized_record=_canonical_json(normalized_record),
                )
            except RuntimeError as exc:
                raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_EXTERNAL_ID_CONFLICT") from exc
        return self.read_mirror(mirror_id)

    def read_mirror(self, mirror_id: str) -> PersistedFactCheckMirror:
        mirror = _text(mirror_id, "MIRROR_ID")
        raw = self.run(
            """
            SELECT json_build_object(
                'mirror_id', mirror.id,
                'lineage_id', lineage.id,
                'upstream_record_id', lineage.upstream_record_id,
                'version_id', version.id,
                'source_version', version.source_version,
                'source_content_sha256', version.source_content_sha256,
                'supersedes_version_id', version.supersedes_version_id,
                'version_state', CASE WHEN EXISTS (
                    SELECT 1 FROM existing_factcheck_version child
                    WHERE child.supersedes_version_id=version.id
                ) THEN 'HISTORICAL' ELSE 'CURRENT' END,
                'provider_id', mirror.provider_id,
                'source_external_id', mirror.source_external_id,
                'review_url', mirror.review_url,
                'rights_status', mirror.rights_status,
                'research_assignment_id', mirror.research_assignment_id,
                'discovery_attempt_id', mirror.discovery_attempt_id,
                'discovery_hit_id', mirror.discovery_hit_id,
                'provider_receipt_sha256', mirror.provider_receipt_sha256,
                'normalized_record_sha256', mirror.normalized_record_sha256,
                'normalized_record', mirror.normalized_record
            )::text
            FROM existing_factcheck_mirror mirror
            JOIN existing_factcheck_version version ON version.id=mirror.version_id
            JOIN existing_factcheck_lineage lineage ON lineage.id=version.lineage_id
            WHERE mirror.id=:'mirror_id';
            """,
            mirror_id=mirror,
        )
        if not raw:
            raise ExistingFactCheckMirrorError("FACTCHECK_MIRROR_NOT_FOUND")
        row = json.loads(raw)
        return PersistedFactCheckMirror(**row)


__all__ = [
    "EXISTING_FACTCHECK_MIRROR_VERSION",
    "ExistingFactCheckMirrorError",
    "ExistingFactCheckMirrorStore",
    "FactCheckMirrorPublicMetadata",
    "PersistedFactCheckMirror",
    "decide_mirror_excerpt",
    "public_mirror_metadata",
]

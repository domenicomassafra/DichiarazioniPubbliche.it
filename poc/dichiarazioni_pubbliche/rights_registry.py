"""DP-305 private versioned rights registry.

This module persists operator/counsel-supplied rights metadata only. It never infers a
clearance, never stores a rights-receipt body, and never authorizes an excerpt or any public
output. Public excerpt decisions remain the responsibility of ``policy.excerpt_policy``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from dichiarazioni_pubbliche.policy.excerpt_policy import RightsStatus
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


PRIVATE_RIGHTS_RECORD_VERSION = "private-rights-record-v1"
MAX_POLICY_CODES = 32
_MACHINE_CODE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,127}$")


class PrivateRightsRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class RightsSubject:
    source_family: str
    locator_kind: str
    locator_value: str
    content_id: str | None = None
    evidence_id: str | None = None
    transcript_segment_id: str | None = None
    canonical_segment_id: str | None = None
    passage_id: str | None = None


@dataclass(frozen=True)
class PrivateRightsRecord:
    id: str
    subject_fingerprint: str
    source_family: str
    locator_kind: str
    locator_value: str
    content_id: str | None
    evidence_id: str | None
    transcript_segment_id: str | None
    canonical_segment_id: str | None
    passage_id: str | None
    rights_status: str
    rights_receipt_ref: str | None
    permitted_uses: tuple[str, ...]
    attribution_requirements: tuple[str, ...]
    reviewed_at: str | None
    expires_at: str | None
    reviewer_ref: str | None
    policy_version: str
    record_visibility: str
    supersedes_id: str | None
    version_state: str
    record_version: str = PRIVATE_RIGHTS_RECORD_VERSION


def _text(value: object, field: str, *, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise PrivateRightsRegistryError(f"RIGHTS_REGISTRY_{field}_REQUIRED")
    if len(text) > maximum or "\x00" in text:
        raise PrivateRightsRegistryError(f"RIGHTS_REGISTRY_{field}_INVALID")
    return text


def _optional_text(value: object | None, field: str, *, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _opaque_ref(value: object | None) -> str | None:
    ref = _optional_text(value, "RIGHTS_RECEIPT_REF", maximum=512)
    if ref is None:
        return None
    if any(char.isspace() for char in ref):
        raise PrivateRightsRegistryError("RIGHTS_REGISTRY_RIGHTS_RECEIPT_REF_INVALID")
    return ref


def _timestamp(value: object | None, field: str) -> str | None:
    if value is None:
        return None
    text = _text(value, field, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PrivateRightsRegistryError(f"RIGHTS_REGISTRY_{field}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PrivateRightsRegistryError(f"RIGHTS_REGISTRY_{field}_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc).isoformat()


def _codes(values: Iterable[object], field: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in values:
        value = _text(raw, field, maximum=128).upper()
        if not _MACHINE_CODE.fullmatch(value):
            raise PrivateRightsRegistryError(f"RIGHTS_REGISTRY_{field}_INVALID")
        if value not in normalized:
            normalized.append(value)
    if len(normalized) > MAX_POLICY_CODES:
        raise PrivateRightsRegistryError(f"RIGHTS_REGISTRY_{field}_TOO_MANY")
    return tuple(sorted(normalized))


def _rights(value: RightsStatus | str) -> str:
    try:
        return value.value if isinstance(value, RightsStatus) else RightsStatus(str(value)).value
    except ValueError as exc:
        raise PrivateRightsRegistryError("RIGHTS_REGISTRY_RIGHTS_STATUS_INVALID") from exc


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def normalize_rights_subject(subject: RightsSubject) -> RightsSubject:
    segment_refs = tuple(
        value
        for value in (
            subject.transcript_segment_id,
            subject.canonical_segment_id,
            subject.passage_id,
        )
        if value is not None
    )
    if len(segment_refs) > 1:
        raise PrivateRightsRegistryError("RIGHTS_REGISTRY_SEGMENT_BINDING_AMBIGUOUS")
    return RightsSubject(
        source_family=_text(subject.source_family, "SOURCE_FAMILY", maximum=128),
        locator_kind=_text(subject.locator_kind, "LOCATOR_KIND", maximum=64).upper(),
        locator_value=_text(subject.locator_value, "LOCATOR_VALUE", maximum=2048),
        content_id=_optional_text(subject.content_id, "CONTENT_ID", maximum=512),
        evidence_id=_optional_text(subject.evidence_id, "EVIDENCE_ID", maximum=512),
        transcript_segment_id=_optional_text(
            subject.transcript_segment_id, "TRANSCRIPT_SEGMENT_ID", maximum=512
        ),
        canonical_segment_id=_optional_text(
            subject.canonical_segment_id, "CANONICAL_SEGMENT_ID", maximum=512
        ),
        passage_id=_optional_text(subject.passage_id, "PASSAGE_ID", maximum=512),
    )


def rights_subject_fingerprint(subject: RightsSubject) -> str:
    normalized = normalize_rights_subject(subject)
    return _fingerprint(
        {
            "source_family": normalized.source_family,
            "locator_kind": normalized.locator_kind,
            "locator_value": normalized.locator_value,
            "content_id": normalized.content_id,
            "evidence_id": normalized.evidence_id,
            "transcript_segment_id": normalized.transcript_segment_id,
            "canonical_segment_id": normalized.canonical_segment_id,
            "passage_id": normalized.passage_id,
        }
    )


class PrivateRightsRegistryStore(PsqlRuntime):
    def _validate_target_relationships(self, subject: RightsSubject) -> None:
        if subject.content_id is None:
            return
        if subject.transcript_segment_id is not None:
            found = self.run(
                """
                SELECT segment.id
                FROM transcript_segment segment
                JOIN transcript_variant variant ON variant.id=segment.variant_id
                WHERE segment.id=:'segment_id' AND variant.content_id=:'content_id';
                """,
                segment_id=subject.transcript_segment_id,
                content_id=subject.content_id,
            )
            if found != subject.transcript_segment_id:
                raise PrivateRightsRegistryError(
                    "RIGHTS_REGISTRY_TRANSCRIPT_SEGMENT_CONTENT_MISMATCH"
                )
        if subject.canonical_segment_id is not None:
            found = self.run(
                """
                SELECT id FROM canonical_transcript_segment
                WHERE id=:'segment_id' AND content_id=:'content_id';
                """,
                segment_id=subject.canonical_segment_id,
                content_id=subject.content_id,
            )
            if found != subject.canonical_segment_id:
                raise PrivateRightsRegistryError(
                    "RIGHTS_REGISTRY_CANONICAL_SEGMENT_CONTENT_MISMATCH"
                )
        if subject.passage_id is not None:
            found = self.run(
                """
                SELECT id FROM passage
                WHERE id=:'passage_id' AND content_id=:'content_id';
                """,
                passage_id=subject.passage_id,
                content_id=subject.content_id,
            )
            if found != subject.passage_id:
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_PASSAGE_CONTENT_MISMATCH")

    @staticmethod
    def _record_material(
        *,
        subject: RightsSubject,
        subject_fingerprint: str,
        rights_status: str,
        rights_receipt_ref: str | None,
        permitted_uses: tuple[str, ...],
        attribution_requirements: tuple[str, ...],
        reviewed_at: str | None,
        expires_at: str | None,
        reviewer_ref: str | None,
        policy_version: str,
        supersedes_id: str | None,
    ) -> dict[str, object]:
        return {
            "record_version": PRIVATE_RIGHTS_RECORD_VERSION,
            "subject_fingerprint": subject_fingerprint,
            "source_family": subject.source_family,
            "locator_kind": subject.locator_kind,
            "locator_value": subject.locator_value,
            "content_id": subject.content_id,
            "evidence_id": subject.evidence_id,
            "transcript_segment_id": subject.transcript_segment_id,
            "canonical_segment_id": subject.canonical_segment_id,
            "passage_id": subject.passage_id,
            "rights_status": rights_status,
            "rights_receipt_ref": rights_receipt_ref,
            "permitted_uses": list(permitted_uses),
            "attribution_requirements": list(attribution_requirements),
            "reviewed_at": reviewed_at,
            "expires_at": expires_at,
            "reviewer_ref": reviewer_ref,
            "policy_version": policy_version,
            "record_visibility": "PRIVATE",
            "supersedes_id": supersedes_id,
        }

    def _read(self, record_id: str) -> PrivateRightsRecord | None:
        raw = self.run(
            """
            SELECT json_build_object(
                'id', record.id,
                'subject_fingerprint', record.subject_fingerprint,
                'source_family', record.source_family,
                'locator_kind', record.locator_kind,
                'locator_value', record.locator_value,
                'content_id', record.content_id,
                'evidence_id', record.evidence_id,
                'transcript_segment_id', record.transcript_segment_id,
                'canonical_segment_id', record.canonical_segment_id,
                'passage_id', record.passage_id,
                'rights_status', record.rights_status,
                'rights_receipt_ref', record.rights_receipt_ref,
                'permitted_uses', to_json(record.permitted_uses),
                'attribution_requirements', to_json(record.attribution_requirements),
                'reviewed_at', CASE WHEN record.reviewed_at IS NULL THEN NULL ELSE record.reviewed_at::text END,
                'expires_at', CASE WHEN record.expires_at IS NULL THEN NULL ELSE record.expires_at::text END,
                'reviewer_ref', record.reviewer_ref,
                'policy_version', record.policy_version,
                'record_visibility', record.record_visibility,
                'supersedes_id', record.supersedes_id,
                'record_version', record.record_version,
                'version_state', CASE WHEN EXISTS (
                    SELECT 1 FROM private_source_rights_record child
                    WHERE child.supersedes_id=record.id
                ) THEN 'HISTORICAL' ELSE 'CURRENT' END
            )::text
            FROM private_source_rights_record record
            WHERE record.id=:'record_id';
            """,
            record_id=record_id,
        )
        if not raw:
            return None
        value = json.loads(raw)
        return PrivateRightsRecord(
            id=str(value["id"]),
            subject_fingerprint=str(value["subject_fingerprint"]),
            source_family=str(value["source_family"]),
            locator_kind=str(value["locator_kind"]),
            locator_value=str(value["locator_value"]),
            content_id=value.get("content_id"),
            evidence_id=value.get("evidence_id"),
            transcript_segment_id=value.get("transcript_segment_id"),
            canonical_segment_id=value.get("canonical_segment_id"),
            passage_id=value.get("passage_id"),
            rights_status=str(value["rights_status"]),
            rights_receipt_ref=value.get("rights_receipt_ref"),
            permitted_uses=tuple(value.get("permitted_uses") or ()),
            attribution_requirements=tuple(value.get("attribution_requirements") or ()),
            reviewed_at=_timestamp(value.get("reviewed_at"), "PERSISTED_REVIEWED_AT"),
            expires_at=_timestamp(value.get("expires_at"), "PERSISTED_EXPIRES_AT"),
            reviewer_ref=value.get("reviewer_ref"),
            policy_version=str(value["policy_version"]),
            record_visibility=str(value["record_visibility"]),
            supersedes_id=value.get("supersedes_id"),
            version_state=str(value["version_state"]),
            record_version=str(value["record_version"]),
        )

    def read_record(self, record_id: str) -> PrivateRightsRecord | None:
        return self._read(_text(record_id, "RECORD_ID", maximum=512))

    def read_current(self, subject: RightsSubject) -> PrivateRightsRecord | None:
        normalized = normalize_rights_subject(subject)
        subject_fp = rights_subject_fingerprint(normalized)
        raw = self.run(
            """
            SELECT current.id
            FROM private_source_rights_record current
            WHERE current.subject_fingerprint=:'subject_fingerprint'
              AND NOT EXISTS (
                  SELECT 1 FROM private_source_rights_record child
                  WHERE child.supersedes_id=current.id
              )
            ORDER BY current.created_at DESC, current.id DESC;
            """,
            subject_fingerprint=subject_fp,
        )
        ids = [value for value in raw.splitlines() if value]
        if len(ids) > 1:
            raise PrivateRightsRegistryError("RIGHTS_REGISTRY_MULTIPLE_CURRENT_RECORDS")
        return self._read(ids[0]) if ids else None

    def record_rights(
        self,
        *,
        subject: RightsSubject,
        policy_version: str,
        rights_status: RightsStatus | str = RightsStatus.UNKNOWN,
        rights_receipt_ref: str | None = None,
        permitted_uses: Iterable[object] = (),
        attribution_requirements: Iterable[object] = (),
        reviewed_at: str | None = None,
        expires_at: str | None = None,
        reviewer_ref: str | None = None,
        supersedes_record_id: str | None = None,
    ) -> PrivateRightsRecord:
        normalized = normalize_rights_subject(subject)
        self._validate_target_relationships(normalized)
        subject_fp = rights_subject_fingerprint(normalized)
        status = _rights(rights_status)
        receipt_ref = _opaque_ref(rights_receipt_ref)
        uses = _codes(permitted_uses, "PERMITTED_USE")
        attribution = _codes(attribution_requirements, "ATTRIBUTION_REQUIREMENT")
        reviewed = _timestamp(reviewed_at, "REVIEWED_AT")
        expires = _timestamp(expires_at, "EXPIRES_AT")
        reviewer = _optional_text(reviewer_ref, "REVIEWER_REF", maximum=256)
        policy = _text(policy_version, "POLICY_VERSION", maximum=128)
        supersedes = _optional_text(
            supersedes_record_id, "SUPERSEDES_RECORD_ID", maximum=512
        )

        if (reviewed is None) != (reviewer is None):
            raise PrivateRightsRegistryError("RIGHTS_REGISTRY_REVIEW_BINDING_INCOMPLETE")
        if reviewed is not None and expires is not None:
            if datetime.fromisoformat(expires) < datetime.fromisoformat(reviewed):
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_EXPIRY_BEFORE_REVIEW")
        if status not in {RightsStatus.UNKNOWN.value, RightsStatus.UNRESOLVED.value}:
            if receipt_ref is None:
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_RIGHTS_RECEIPT_REF_REQUIRED")
        if status == RightsStatus.CLEARED.value and (reviewed is None or reviewer is None):
            raise PrivateRightsRegistryError("RIGHTS_REGISTRY_CLEARED_REVIEW_REQUIRED")

        material = self._record_material(
            subject=normalized,
            subject_fingerprint=subject_fp,
            rights_status=status,
            rights_receipt_ref=receipt_ref,
            permitted_uses=uses,
            attribution_requirements=attribution,
            reviewed_at=reviewed,
            expires_at=expires,
            reviewer_ref=reviewer,
            policy_version=policy,
            supersedes_id=supersedes,
        )
        record_id = "private-rights:" + _fingerprint(material)
        existing = self._read(record_id)
        if existing is not None:
            if self._material_from_record(existing) != material:
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_REPLAY_CONFLICT")
            return existing

        current = self.read_current(normalized)
        if current is None:
            if supersedes is not None:
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_SUPERSEDES_TARGET_MISSING")
        else:
            if supersedes is None:
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_SUPERSEDES_REQUIRED")
            if supersedes != current.id:
                raise PrivateRightsRegistryError("RIGHTS_REGISTRY_SUPERSEDES_NOT_CURRENT")

        try:
            self.run(
                """
                INSERT INTO private_source_rights_record (
                    id, subject_fingerprint, source_family, locator_kind, locator_value,
                    content_id, evidence_id, transcript_segment_id, canonical_segment_id,
                    passage_id, rights_status, rights_receipt_ref, permitted_uses,
                    attribution_requirements, reviewed_at, expires_at, reviewer_ref,
                    policy_version, record_visibility, supersedes_id, record_version
                ) VALUES (
                    :'id', :'subject_fingerprint', :'source_family', :'locator_kind', :'locator_value',
                    NULLIF(:'content_id',''), NULLIF(:'evidence_id',''),
                    NULLIF(:'transcript_segment_id',''), NULLIF(:'canonical_segment_id',''),
                    NULLIF(:'passage_id',''), :'rights_status', NULLIF(:'rights_receipt_ref',''),
                    ARRAY(SELECT jsonb_array_elements_text(:'permitted_uses'::jsonb)),
                    ARRAY(SELECT jsonb_array_elements_text(:'attribution_requirements'::jsonb)),
                    NULLIF(:'reviewed_at','')::timestamptz, NULLIF(:'expires_at','')::timestamptz,
                    NULLIF(:'reviewer_ref',''), :'policy_version', 'PRIVATE',
                    NULLIF(:'supersedes_id',''), :'record_version'
                )
                ON CONFLICT (id) DO NOTHING;
                """,
                id=record_id,
                subject_fingerprint=subject_fp,
                source_family=normalized.source_family,
                locator_kind=normalized.locator_kind,
                locator_value=normalized.locator_value,
                content_id=normalized.content_id or "",
                evidence_id=normalized.evidence_id or "",
                transcript_segment_id=normalized.transcript_segment_id or "",
                canonical_segment_id=normalized.canonical_segment_id or "",
                passage_id=normalized.passage_id or "",
                rights_status=status,
                rights_receipt_ref=receipt_ref or "",
                permitted_uses=_stable_json(list(uses)),
                attribution_requirements=_stable_json(list(attribution)),
                reviewed_at=reviewed or "",
                expires_at=expires or "",
                reviewer_ref=reviewer or "",
                policy_version=policy,
                supersedes_id=supersedes or "",
                record_version=PRIVATE_RIGHTS_RECORD_VERSION,
            )
        except RuntimeError as exc:
            raise PrivateRightsRegistryError("RIGHTS_REGISTRY_INSERT_CONFLICT") from exc

        saved = self._read(record_id)
        if saved is None or self._material_from_record(saved) != material:
            raise PrivateRightsRegistryError("RIGHTS_REGISTRY_PERSISTED_RECORD_MISMATCH")
        return saved

    @staticmethod
    def _material_from_record(record: PrivateRightsRecord) -> dict[str, object]:
        return {
            "record_version": record.record_version,
            "subject_fingerprint": record.subject_fingerprint,
            "source_family": record.source_family,
            "locator_kind": record.locator_kind,
            "locator_value": record.locator_value,
            "content_id": record.content_id,
            "evidence_id": record.evidence_id,
            "transcript_segment_id": record.transcript_segment_id,
            "canonical_segment_id": record.canonical_segment_id,
            "passage_id": record.passage_id,
            "rights_status": record.rights_status,
            "rights_receipt_ref": record.rights_receipt_ref,
            "permitted_uses": list(record.permitted_uses),
            "attribution_requirements": list(record.attribution_requirements),
            "reviewed_at": record.reviewed_at,
            "expires_at": record.expires_at,
            "reviewer_ref": record.reviewer_ref,
            "policy_version": record.policy_version,
            "record_visibility": record.record_visibility,
            "supersedes_id": record.supersedes_id,
        }


__all__ = [
    "MAX_POLICY_CODES",
    "PRIVATE_RIGHTS_RECORD_VERSION",
    "PrivateRightsRecord",
    "PrivateRightsRegistryError",
    "PrivateRightsRegistryStore",
    "RightsSubject",
    "normalize_rights_subject",
    "rights_subject_fingerprint",
]

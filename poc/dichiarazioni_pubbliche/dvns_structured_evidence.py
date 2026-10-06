from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from dichiarazioni_pubbliche.structured_evidence import (
    STRUCTURED_EVIDENCE_VERSION,
    StructuredEvidenceBatch,
    StructuredEvidenceError,
    normalize_structured_evidence_payload,
)


DVNS_ADAPTER_VERSION = "dvns-structured-evidence-adapter-v1"
DVNS_SOURCE_SCHEMA_VERSION = "dvns-style-readonly-evidence-v1"
DVNS_AUTHORITY_SCOPE = "STRUCTURED_EVIDENCE_CANDIDATE_ONLY"

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "provider_id",
        "source_version",
        "rights_status",
        "availability_status",
        "fetch_state",
        "blocker",
        "records",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "external_id",
        "source_url",
        "metric",
        "value_state",
        "value_numeric",
        "value_text",
        "unit",
        "reference_period",
        "publication_date",
        "observed_at",
        "effective_from",
        "effective_to",
        "dimensions",
        "source_roles",
        "field_provenance",
        "private_fields",
    }
)
_BASE_PROVENANCE_FIELDS = frozenset(
    {
        "external_id",
        "source_version",
        "source_url",
        "metric",
        "value_state",
        "observed_at",
    }
)
_OPTIONAL_PROVENANCE_FIELDS = (
    "unit",
    "reference_period",
    "publication_date",
    "effective_from",
    "effective_to",
)


class DvnsStructuredEvidenceError(StructuredEvidenceError):
    pass


@dataclass(frozen=True)
class DvnsRecordProvenance:
    record_id: str
    external_id: str
    source_version: str
    source_url: str
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class DvnsStructuredEvidenceImport:
    provider_id: str
    source_schema_version: str
    source_version: str
    rights_status: str
    availability_status: str
    replay_id: str
    normalized_batch: StructuredEvidenceBatch
    provenance: tuple[DvnsRecordProvenance, ...]
    authority_scope: str = DVNS_AUTHORITY_SCOPE
    adapter_version: str = DVNS_ADAPTER_VERSION


def _strict_keys(value: Mapping[str, Any], allowed: frozenset[str], code: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise DvnsStructuredEvidenceError(f"{code}:{','.join(sorted(str(key) for key in unknown))}")


def _text(value: Any, name: str, *, maximum: int = 4096) -> str:
    if isinstance(value, bool):
        raise DvnsStructuredEvidenceError(f"DVNS_{name}_REQUIRED")
    text = str(value or "").strip()
    if not text:
        raise DvnsStructuredEvidenceError(f"DVNS_{name}_REQUIRED")
    if len(text) > maximum:
        raise DvnsStructuredEvidenceError(f"DVNS_{name}_TOO_LONG")
    return text


def _optional_text(value: Any, *, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > maximum:
        raise DvnsStructuredEvidenceError("DVNS_OPTIONAL_TEXT_TOO_LONG")
    return text


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(str(_canonical_value(item)) for item in value)
    return value


def _sha(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _canonical_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _provenance_fields(
    record: Mapping[str, Any],
    *,
    value_state: str,
) -> tuple[tuple[str, str], ...]:
    raw = record.get("field_provenance")
    if not isinstance(raw, Mapping):
        raise DvnsStructuredEvidenceError("DVNS_FIELD_PROVENANCE_REQUIRED")

    required = set(_BASE_PROVENANCE_FIELDS)
    if value_state == "PRESENT":
        if record.get("value_numeric") is not None:
            required.add("value_numeric")
        else:
            required.add("value_text")
    for field in _OPTIONAL_PROVENANCE_FIELDS:
        if _optional_text(record.get(field)) is not None:
            required.add(field)
    roles = record.get("source_roles") or ()
    if roles:
        required.add("source_roles")
    dimensions = record.get("dimensions") or {}
    if not isinstance(dimensions, Mapping):
        raise DvnsStructuredEvidenceError("DVNS_DIMENSIONS_INVALID")
    required.update(f"dimensions.{key}" for key in dimensions)

    actual = {str(key) for key in raw}
    missing = required - actual
    extra = actual - required
    if missing:
        raise DvnsStructuredEvidenceError(
            "DVNS_FIELD_PROVENANCE_MISSING:" + ",".join(sorted(missing))
        )
    if extra:
        raise DvnsStructuredEvidenceError(
            "DVNS_FIELD_PROVENANCE_UNKNOWN:" + ",".join(sorted(extra))
        )

    normalized: list[tuple[str, str]] = []
    for target in sorted(required):
        selector = _text(raw.get(target), "FIELD_PROVENANCE_SELECTOR", maximum=512)
        lowered = selector.lower()
        if "private_fields" in lowered or lowered.startswith("private."):
            raise DvnsStructuredEvidenceError("DVNS_PRIVATE_PROVENANCE_FORBIDDEN")
        normalized.append((target, selector))
    return tuple(normalized)


def _normalized_row(record: Mapping[str, Any], source_version: str) -> dict[str, Any]:
    return {
        "source_record_id": _text(record.get("external_id"), "EXTERNAL_ID", maximum=512),
        "source_version": source_version,
        "source_url": record.get("source_url"),
        "metric": record.get("metric"),
        "value_state": record.get("value_state"),
        "value_numeric": record.get("value_numeric"),
        "value_text": record.get("value_text"),
        "unit": record.get("unit"),
        "reference_period": record.get("reference_period"),
        "publication_date": record.get("publication_date"),
        "observed_at": record.get("observed_at"),
        "effective_from": record.get("effective_from"),
        "effective_to": record.get("effective_to"),
        "dimensions": record.get("dimensions") or {},
        "source_roles": record.get("source_roles") or (),
    }


def import_dvns_structured_evidence(
    payload: Mapping[str, Any],
    *,
    expected_provider_id: str | None = None,
    max_records: int = 1000,
) -> DvnsStructuredEvidenceImport:
    if not isinstance(payload, Mapping):
        raise DvnsStructuredEvidenceError("DVNS_PAYLOAD_INVALID")
    _strict_keys(payload, _TOP_LEVEL_FIELDS, "DVNS_PAYLOAD_UNKNOWN_FIELD")

    source_schema_version = _text(payload.get("schema_version"), "SCHEMA_VERSION", maximum=128)
    if source_schema_version != DVNS_SOURCE_SCHEMA_VERSION:
        raise DvnsStructuredEvidenceError("DVNS_SCHEMA_VERSION_UNSUPPORTED")

    provider_id = _text(payload.get("provider_id"), "PROVIDER_ID", maximum=256)
    if expected_provider_id is not None and provider_id != expected_provider_id:
        raise DvnsStructuredEvidenceError("DVNS_PROVIDER_ID_MISMATCH")
    source_version = _text(payload.get("source_version"), "SOURCE_VERSION", maximum=256)
    rights_status = _text(payload.get("rights_status"), "RIGHTS_STATUS", maximum=128)
    availability_status = _text(
        payload.get("availability_status"), "AVAILABILITY_STATUS", maximum=128
    )
    fetch_state = _text(payload.get("fetch_state"), "FETCH_STATE", maximum=64).upper()
    blocker = _optional_text(payload.get("blocker"), maximum=512)
    records = payload.get("records")
    if not isinstance(records, list):
        raise DvnsStructuredEvidenceError("DVNS_RECORDS_REQUIRED")
    if not 1 <= int(max_records) <= 100_000:
        raise DvnsStructuredEvidenceError("DVNS_MAX_RECORDS_INVALID")
    if len(records) > int(max_records):
        raise DvnsStructuredEvidenceError("DVNS_RECORD_LIMIT_EXCEEDED")

    if fetch_state != "SUCCEEDED":
        normalized_batch = normalize_structured_evidence_payload(
            {
                "schema_version": STRUCTURED_EVIDENCE_VERSION,
                "provider_id": provider_id,
                "fetch_state": fetch_state,
                "blocker": blocker,
                "records": records,
            },
            expected_provider_id=provider_id,
            max_records=max_records,
        )
        replay_payload = {
            "provider_id": provider_id,
            "source_schema_version": source_schema_version,
            "source_version": source_version,
            "rights_status": rights_status,
            "availability_status": availability_status,
            "fetch_state": fetch_state,
            "blocker": blocker,
            "records": [],
            "adapter_version": DVNS_ADAPTER_VERSION,
        }
        replay_id = "dvns-replay:" + _sha(replay_payload)
        receipt = {
            **normalized_batch.provider_receipt,
            "source_schema_version": source_schema_version,
            "source_version": source_version,
            "rights_status": rights_status,
            "availability_status": availability_status,
            "replay_id": replay_id,
            "dvns_adapter_version": DVNS_ADAPTER_VERSION,
        }
        normalized_batch = StructuredEvidenceBatch(
            provider_id=normalized_batch.provider_id,
            schema_version=normalized_batch.schema_version,
            fetch_state=normalized_batch.fetch_state,
            values=normalized_batch.values,
            provider_receipt=receipt,
            blocker=normalized_batch.blocker,
        )
        return DvnsStructuredEvidenceImport(
            provider_id=provider_id,
            source_schema_version=source_schema_version,
            source_version=source_version,
            rights_status=rights_status,
            availability_status=availability_status,
            replay_id=replay_id,
            normalized_batch=normalized_batch,
            provenance=(),
        )

    accepted_rows: list[dict[str, Any]] = []
    provenance_by_record_id: dict[str, DvnsRecordProvenance] = {}
    fingerprint_by_record_id: dict[str, str] = {}

    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            raise DvnsStructuredEvidenceError("DVNS_RECORD_INVALID")
        _strict_keys(raw_record, _RECORD_FIELDS, "DVNS_RECORD_UNKNOWN_FIELD")
        private_fields = raw_record.get("private_fields")
        if private_fields is not None and not isinstance(private_fields, Mapping):
            raise DvnsStructuredEvidenceError("DVNS_PRIVATE_FIELDS_INVALID")

        normalized_row = _normalized_row(raw_record, source_version)
        single = normalize_structured_evidence_payload(
            {
                "schema_version": STRUCTURED_EVIDENCE_VERSION,
                "provider_id": provider_id,
                "fetch_state": "SUCCEEDED",
                "blocker": None,
                "records": [normalized_row],
            },
            expected_provider_id=provider_id,
            max_records=1,
        )
        value = single.values[0]
        provenance_fields = _provenance_fields(
            raw_record,
            value_state=value.value_state,
        )
        public_fingerprint = _sha(
            {
                "record": {
                    "record_id": value.record_id,
                    "source_record_id": value.source_record_id,
                    "source_version": value.source_version,
                    "source_url": value.source_url,
                    "metric": value.metric,
                    "value_state": value.value_state,
                    "value_numeric": value.value_numeric,
                    "value_text": value.value_text,
                    "unit": value.unit,
                    "reference_period": value.reference_period,
                    "publication_date": value.publication_date,
                    "observed_at": value.observed_at,
                    "effective_from": value.effective_from,
                    "effective_to": value.effective_to,
                    "dimensions": value.dimensions,
                    "source_roles": value.source_roles,
                },
                "field_provenance": dict(provenance_fields),
            }
        )
        previous = fingerprint_by_record_id.get(value.record_id)
        if previous is not None:
            if previous != public_fingerprint:
                raise DvnsStructuredEvidenceError("DVNS_DUPLICATE_RECORD_CONFLICT")
            continue

        fingerprint_by_record_id[value.record_id] = public_fingerprint
        accepted_rows.append(normalized_row)
        provenance_by_record_id[value.record_id] = DvnsRecordProvenance(
            record_id=value.record_id,
            external_id=value.source_record_id,
            source_version=value.source_version,
            source_url=value.source_url,
            fields=provenance_fields,
        )

    normalized_batch = normalize_structured_evidence_payload(
        {
            "schema_version": STRUCTURED_EVIDENCE_VERSION,
            "provider_id": provider_id,
            "fetch_state": "SUCCEEDED",
            "blocker": None,
            "records": accepted_rows,
        },
        expected_provider_id=provider_id,
        max_records=max_records,
    )
    replay_payload = {
        "provider_id": provider_id,
        "source_schema_version": source_schema_version,
        "source_version": source_version,
        "rights_status": rights_status,
        "availability_status": availability_status,
        "fetch_state": "SUCCEEDED",
        "records": [
            {"record_id": record_id, "fingerprint": fingerprint_by_record_id[record_id]}
            for record_id in sorted(fingerprint_by_record_id)
        ],
        "adapter_version": DVNS_ADAPTER_VERSION,
    }
    replay_id = "dvns-replay:" + _sha(replay_payload)
    receipt = {
        **normalized_batch.provider_receipt,
        "source_schema_version": source_schema_version,
        "source_version": source_version,
        "rights_status": rights_status,
        "availability_status": availability_status,
        "replay_id": replay_id,
        "deduplicated_record_count": len(records) - len(accepted_rows),
        "dvns_adapter_version": DVNS_ADAPTER_VERSION,
    }
    normalized_batch = StructuredEvidenceBatch(
        provider_id=normalized_batch.provider_id,
        schema_version=normalized_batch.schema_version,
        fetch_state=normalized_batch.fetch_state,
        values=normalized_batch.values,
        provider_receipt=receipt,
        blocker=normalized_batch.blocker,
    )
    provenance = tuple(
        provenance_by_record_id[value.record_id] for value in normalized_batch.values
    )
    return DvnsStructuredEvidenceImport(
        provider_id=provider_id,
        source_schema_version=source_schema_version,
        source_version=source_version,
        rights_status=rights_status,
        availability_status=availability_status,
        replay_id=replay_id,
        normalized_batch=normalized_batch,
        provenance=provenance,
    )


__all__ = [
    "DVNS_ADAPTER_VERSION",
    "DVNS_AUTHORITY_SCOPE",
    "DVNS_SOURCE_SCHEMA_VERSION",
    "DvnsRecordProvenance",
    "DvnsStructuredEvidenceError",
    "DvnsStructuredEvidenceImport",
    "import_dvns_structured_evidence",
]

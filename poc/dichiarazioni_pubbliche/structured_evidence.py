from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


STRUCTURED_EVIDENCE_VERSION = "structured-evidence-v1"
SUPPORTED_SCHEMA_VERSIONS = frozenset({"structured-evidence-v1"})
VALUE_STATES = frozenset({"PRESENT", "MISSING", "NOT_APPLICABLE"})
FETCH_STATES = frozenset({"SUCCEEDED", "BLOCKED", "FAILED", "DEGRADED"})


class StructuredEvidenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "STRUCTURED_EVIDENCE_ERROR").strip().upper()[:120]
        super().__init__(self.code)


def _required_text(value: Any, name: str, *, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text:
        raise StructuredEvidenceError(f"{name}_REQUIRED")
    if len(text) > maximum:
        raise StructuredEvidenceError(f"{name}_TOO_LONG")
    return text


def _optional_text(value: Any, *, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:maximum]


def _https_url(value: Any) -> str:
    raw = _required_text(value, "STRUCTURED_SOURCE_URL")
    parsed = urlsplit(raw)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise StructuredEvidenceError("STRUCTURED_SOURCE_URL_INVALID")
    return raw


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise StructuredEvidenceError(f"{name}_INVALID")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise StructuredEvidenceError(f"{name}_INVALID") from exc
    if not result.is_finite():
        raise StructuredEvidenceError(f"{name}_INVALID")
    return result


@dataclass(frozen=True)
class StructuredEvidenceValue:
    record_id: str
    source_record_id: str
    source_version: str
    source_url: str
    metric: str
    value_state: str
    value_numeric: Decimal | None
    value_text: str | None
    unit: str | None
    reference_period: str | None
    publication_date: str | None
    observed_at: str
    effective_from: str | None
    effective_to: str | None
    dimensions: tuple[tuple[str, str], ...]
    source_roles: tuple[str, ...]
    adapter_version: str = STRUCTURED_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        if self.value_state not in VALUE_STATES:
            raise StructuredEvidenceError("STRUCTURED_VALUE_STATE_INVALID")
        if self.value_state == "PRESENT":
            if (self.value_numeric is None) == (self.value_text is None):
                raise StructuredEvidenceError("STRUCTURED_PRESENT_REQUIRES_EXACTLY_ONE_VALUE")
        elif self.value_numeric is not None or self.value_text is not None:
            raise StructuredEvidenceError("STRUCTURED_ABSENT_STATE_HAS_VALUE")


@dataclass(frozen=True)
class StructuredEvidenceBatch:
    provider_id: str
    schema_version: str
    fetch_state: str
    values: tuple[StructuredEvidenceValue, ...]
    provider_receipt: dict[str, Any]
    blocker: str | None = None

    @property
    def usable_candidate_batch(self) -> bool:
        return self.fetch_state == "SUCCEEDED" and self.blocker is None


def deterministic_structured_record_id(
    *,
    provider_id: str,
    source_record_id: str,
    source_version: str,
    metric: str,
    reference_period: str | None,
    dimensions: Iterable[tuple[str, str]],
) -> str:
    payload = {
        "provider_id": provider_id,
        "source_record_id": source_record_id,
        "source_version": source_version,
        "metric": metric,
        "reference_period": reference_period,
        "dimensions": sorted((str(k), str(v)) for k, v in dimensions),
        "adapter_version": STRUCTURED_EVIDENCE_VERSION,
    }
    return "structured-evidence:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _normalize_row(provider_id: str, row: Mapping[str, Any]) -> StructuredEvidenceValue:
    source_record_id = _required_text(row.get("source_record_id"), "SOURCE_RECORD_ID")
    source_version = _required_text(row.get("source_version"), "SOURCE_VERSION")
    source_url = _https_url(row.get("source_url"))
    metric = _required_text(row.get("metric"), "METRIC", maximum=512)
    observed_at = _required_text(row.get("observed_at"), "OBSERVED_AT", maximum=128)
    value_state = _required_text(row.get("value_state"), "VALUE_STATE", maximum=64).upper()
    if value_state not in VALUE_STATES:
        raise StructuredEvidenceError("STRUCTURED_VALUE_STATE_INVALID")

    raw_numeric = row.get("value_numeric")
    raw_text = row.get("value_text")
    value_numeric: Decimal | None = None
    value_text: str | None = None
    if value_state == "PRESENT":
        numeric_present = raw_numeric is not None
        text_present = raw_text is not None and str(raw_text).strip() != ""
        if numeric_present == text_present:
            raise StructuredEvidenceError("STRUCTURED_PRESENT_REQUIRES_EXACTLY_ONE_VALUE")
        if numeric_present:
            # Explicitly preserve 0: None is missing; Decimal("0") is a real observed value.
            value_numeric = _decimal(raw_numeric, "VALUE_NUMERIC")
        else:
            value_text = _required_text(raw_text, "VALUE_TEXT", maximum=8192)
    elif raw_numeric is not None or (raw_text is not None and str(raw_text).strip()):
        raise StructuredEvidenceError("STRUCTURED_ABSENT_STATE_HAS_VALUE")

    raw_dimensions = row.get("dimensions") or {}
    if not isinstance(raw_dimensions, Mapping):
        raise StructuredEvidenceError("STRUCTURED_DIMENSIONS_INVALID")
    if len(raw_dimensions) > 32:
        raise StructuredEvidenceError("STRUCTURED_DIMENSIONS_TOO_MANY")
    dimensions = tuple(
        sorted(
            (
                _required_text(key, "DIMENSION_KEY", maximum=128),
                _required_text(value, "DIMENSION_VALUE", maximum=512),
            )
            for key, value in raw_dimensions.items()
        )
    )
    roles_raw = row.get("source_roles") or ()
    if not isinstance(roles_raw, (list, tuple, set)):
        raise StructuredEvidenceError("STRUCTURED_SOURCE_ROLES_INVALID")
    roles = tuple(
        sorted(
            {
                _required_text(role, "SOURCE_ROLE", maximum=128)
                for role in roles_raw
            }
        )
    )
    record_id = deterministic_structured_record_id(
        provider_id=provider_id,
        source_record_id=source_record_id,
        source_version=source_version,
        metric=metric,
        reference_period=_optional_text(row.get("reference_period"), maximum=128),
        dimensions=dimensions,
    )
    return StructuredEvidenceValue(
        record_id=record_id,
        source_record_id=source_record_id,
        source_version=source_version,
        source_url=source_url,
        metric=metric,
        value_state=value_state,
        value_numeric=value_numeric,
        value_text=value_text,
        unit=_optional_text(row.get("unit"), maximum=128),
        reference_period=_optional_text(row.get("reference_period"), maximum=128),
        publication_date=_optional_text(row.get("publication_date"), maximum=128),
        observed_at=observed_at,
        effective_from=_optional_text(row.get("effective_from"), maximum=128),
        effective_to=_optional_text(row.get("effective_to"), maximum=128),
        dimensions=dimensions,
        source_roles=roles,
    )


def normalize_structured_evidence_payload(
    payload: Mapping[str, Any],
    *,
    expected_provider_id: str | None = None,
    max_records: int = 1000,
) -> StructuredEvidenceBatch:
    if not 1 <= int(max_records) <= 100_000:
        raise StructuredEvidenceError("STRUCTURED_MAX_RECORDS_INVALID")
    schema_version = _required_text(
        payload.get("schema_version"),
        "SCHEMA_VERSION",
        maximum=128,
    )
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise StructuredEvidenceError("STRUCTURED_SCHEMA_VERSION_UNSUPPORTED")
    provider_id = _required_text(payload.get("provider_id"), "PROVIDER_ID", maximum=256)
    if expected_provider_id is not None and provider_id != expected_provider_id:
        raise StructuredEvidenceError("STRUCTURED_PROVIDER_ID_MISMATCH")
    fetch_state = _required_text(payload.get("fetch_state"), "FETCH_STATE", maximum=64).upper()
    if fetch_state not in FETCH_STATES:
        raise StructuredEvidenceError("STRUCTURED_FETCH_STATE_INVALID")
    blocker = _optional_text(payload.get("blocker"), maximum=512)
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise StructuredEvidenceError("STRUCTURED_RECORDS_REQUIRED")
    if len(rows) > int(max_records):
        raise StructuredEvidenceError("STRUCTURED_RECORD_LIMIT_EXCEEDED")

    if fetch_state != "SUCCEEDED":
        if not blocker:
            raise StructuredEvidenceError("STRUCTURED_NON_SUCCESS_BLOCKER_REQUIRED")
        if rows:
            raise StructuredEvidenceError("STRUCTURED_NON_SUCCESS_RECORDS_FORBIDDEN")
        return StructuredEvidenceBatch(
            provider_id=provider_id,
            schema_version=schema_version,
            fetch_state=fetch_state,
            values=(),
            provider_receipt={
                "provider_id": provider_id,
                "schema_version": schema_version,
                "fetch_state": fetch_state,
                "record_count": 0,
            },
            blocker=blocker,
        )

    values = tuple(_normalize_row(provider_id, row) for row in rows if isinstance(row, Mapping))
    if len(values) != len(rows):
        raise StructuredEvidenceError("STRUCTURED_RECORD_INVALID")
    # Success with an empty dataset is a legitimate result only when explicitly represented
    # as such by the provider. It is not used to disguise an outage because outages must use
    # BLOCKED/FAILED/DEGRADED plus a blocker.
    return StructuredEvidenceBatch(
        provider_id=provider_id,
        schema_version=schema_version,
        fetch_state=fetch_state,
        values=values,
        provider_receipt={
            "provider_id": provider_id,
            "schema_version": schema_version,
            "fetch_state": fetch_state,
            "record_count": len(values),
            "adapter_version": STRUCTURED_EVIDENCE_VERSION,
        },
        blocker=None,
    )


__all__ = [
    "FETCH_STATES",
    "STRUCTURED_EVIDENCE_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "VALUE_STATES",
    "StructuredEvidenceBatch",
    "StructuredEvidenceError",
    "StructuredEvidenceValue",
    "deterministic_structured_record_id",
    "normalize_structured_evidence_payload",
]

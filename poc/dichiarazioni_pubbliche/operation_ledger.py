from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping


OPERATION_LEDGER_VERSION = "operation-ledger-v1"
BILLING_BASES = frozenset(
    {
        "MEASURED_PROVIDER_COST",
        "ESTIMATED_ONLY",
        "EXTERNAL_PLAN",
        "ZERO_COST",
        "UNKNOWN",
    }
)


def deterministic_operation_key(
    *,
    operation: str,
    input_fingerprint: str,
    provider_id: str,
    model_id: str | None = None,
) -> str:
    payload = {
        "operation": str(operation or "").strip(),
        "input_fingerprint": str(input_fingerprint or "").strip(),
        "provider_id": str(provider_id or "").strip(),
        "model_id": str(model_id or "").strip(),
        "version": OPERATION_LEDGER_VERSION,
    }
    if not payload["operation"] or not payload["input_fingerprint"] or not payload["provider_id"]:
        raise ValueError("OPERATION_KEY_FIELDS_REQUIRED")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "provider-operation:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OperationUsageReceipt:
    receipt_id: str | None
    operation_key: str
    attempt: int
    provider_id: str
    model_id: str | None
    operation: str
    status: str
    billing_basis: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: Decimal | None = None
    estimated_cost_usd: Decimal | None = None
    measured_cost_usd: Decimal | None = None
    total_tokens: int | None = None
    input_seconds: Decimal | None = None
    request_count: int = 1
    claim_id: str | None = None
    content_id: str | None = None
    source_id: str | None = None
    collection_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.operation_key or "").strip():
            raise ValueError("OPERATION_RECEIPT_KEY_REQUIRED")
        if self.receipt_id is not None and not str(self.receipt_id).strip():
            raise ValueError("OPERATION_RECEIPT_ID_INVALID")
        if self.attempt < 1:
            raise ValueError("OPERATION_RECEIPT_ATTEMPT_INVALID")
        if not str(self.provider_id or "").strip() or not str(self.operation or "").strip():
            raise ValueError("OPERATION_RECEIPT_PROVIDER_OPERATION_REQUIRED")
        if self.billing_basis not in BILLING_BASES:
            raise ValueError("OPERATION_RECEIPT_BILLING_BASIS_INVALID")
        if self.estimated_cost_usd is not None and self.estimated_cost_usd < 0:
            raise ValueError("OPERATION_RECEIPT_ESTIMATE_INVALID")
        if self.measured_cost_usd is not None and self.measured_cost_usd < 0:
            raise ValueError("OPERATION_RECEIPT_MEASURED_COST_INVALID")
        if self.total_tokens is not None and self.total_tokens < 0:
            raise ValueError("OPERATION_RECEIPT_TOKENS_INVALID")
        if self.input_seconds is not None and self.input_seconds < 0:
            raise ValueError("OPERATION_RECEIPT_SECONDS_INVALID")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("OPERATION_RECEIPT_DURATION_INVALID")
        if self.request_count < 0:
            raise ValueError("OPERATION_RECEIPT_REQUEST_COUNT_INVALID")
        if self.billing_basis == "MEASURED_PROVIDER_COST" and self.measured_cost_usd is None:
            raise ValueError("OPERATION_RECEIPT_MEASURED_COST_REQUIRED")
        if self.billing_basis == "ESTIMATED_ONLY" and self.estimated_cost_usd is None:
            raise ValueError("OPERATION_RECEIPT_ESTIMATE_REQUIRED")
        if self.billing_basis == "ZERO_COST":
            if self.measured_cost_usd not in {None, Decimal("0")}:
                raise ValueError("OPERATION_RECEIPT_ZERO_COST_CONFLICT")
            if self.estimated_cost_usd not in {None, Decimal("0")}:
                raise ValueError("OPERATION_RECEIPT_ZERO_COST_CONFLICT")


@dataclass(frozen=True)
class OperationLedgerSummary:
    operation_count: int
    attempt_count: int
    measured_cost_usd: Decimal
    estimated_only_cost_usd: Decimal
    external_plan_operation_count: int
    unknown_cost_operation_count: int
    zero_cost_operation_count: int
    total_tokens: int
    input_seconds: Decimal
    request_count: int

    @property
    def cost_complete(self) -> bool:
        return self.unknown_cost_operation_count == 0


def aggregate_operation_receipts(
    receipts: Iterable[OperationUsageReceipt],
) -> OperationLedgerSummary:
    rows = tuple(receipts)
    # Multiple attempts for one operation are retained as usage evidence, but a completed
    # operation identity counts once in operation_count. This avoids double-counting
    # logical work while still exposing retry/attempt consumption.
    operation_keys = {row.operation_key for row in rows}
    measured = Decimal("0")
    estimated_only = Decimal("0")
    external_keys: set[str] = set()
    unknown_keys: set[str] = set()
    zero_keys: set[str] = set()
    total_tokens = 0
    input_seconds = Decimal("0")
    request_count = 0

    for row in rows:
        if row.billing_basis == "MEASURED_PROVIDER_COST":
            measured += row.measured_cost_usd or Decimal("0")
        elif row.billing_basis == "ESTIMATED_ONLY":
            estimated_only += row.estimated_cost_usd or Decimal("0")
        elif row.billing_basis == "EXTERNAL_PLAN":
            external_keys.add(row.operation_key)
        elif row.billing_basis == "UNKNOWN":
            unknown_keys.add(row.operation_key)
        elif row.billing_basis == "ZERO_COST":
            zero_keys.add(row.operation_key)

        total_tokens += row.total_tokens or 0
        input_seconds += row.input_seconds or Decimal("0")
        request_count += row.request_count

    return OperationLedgerSummary(
        operation_count=len(operation_keys),
        attempt_count=len(rows),
        measured_cost_usd=measured,
        estimated_only_cost_usd=estimated_only,
        external_plan_operation_count=len(external_keys),
        unknown_cost_operation_count=len(unknown_keys),
        zero_cost_operation_count=len(zero_keys),
        total_tokens=total_tokens,
        input_seconds=input_seconds,
        request_count=request_count,
    )


def operation_usage_receipt_from_row(
    row: Mapping[str, Any],
) -> OperationUsageReceipt:
    receipt_id = str(row.get("receipt_id") or row.get("id") or "").strip() or None
    operation_key = str(row.get("operation_key") or "").strip()
    if not operation_key:
        if not receipt_id:
            raise ValueError("OPERATION_RECEIPT_KEY_REQUIRED")
        operation_key = "legacy:" + receipt_id
    estimated_raw = row.get("estimated_cost_usd")
    measured_raw = row.get("measured_cost_usd")
    estimated = (
        None if estimated_raw in (None, "") else Decimal(str(estimated_raw))
    )
    measured = None if measured_raw in (None, "") else Decimal(str(measured_raw))
    billing_basis = str(row.get("billing_basis") or "ESTIMATED_ONLY").strip()
    if billing_basis == "ESTIMATED_ONLY" and estimated is None:
        billing_basis = "UNKNOWN"
    return OperationUsageReceipt(
        receipt_id=receipt_id,
        operation_key=operation_key,
        attempt=int(row.get("attempt") or 1),
        provider_id=str(row.get("provider_id") or "").strip(),
        model_id=str(row.get("model_id") or "").strip() or None,
        operation=str(row.get("operation") or "").strip(),
        status=str(row.get("status") or "").strip(),
        billing_basis=billing_basis,
        started_at=str(row.get("started_at") or "").strip() or None,
        completed_at=str(row.get("completed_at") or "").strip() or None,
        duration_seconds=(
            None
            if row.get("duration_seconds") in (None, "")
            else Decimal(str(row["duration_seconds"]))
        ),
        estimated_cost_usd=estimated,
        measured_cost_usd=measured,
        total_tokens=(
            None
            if row.get("total_tokens") in (None, "")
            else int(row["total_tokens"])
        ),
        input_seconds=(
            None
            if row.get("input_seconds") in (None, "")
            else Decimal(str(row["input_seconds"]))
        ),
        request_count=int(row.get("request_count") or 0),
        claim_id=str(row.get("claim_id") or "").strip() or None,
        content_id=str(row.get("content_id") or "").strip() or None,
        source_id=str(row.get("source_id") or "").strip() or None,
        collection_id=str(row.get("collection_id") or "").strip() or None,
    )


def filter_operation_receipts(
    receipts: Iterable[OperationUsageReceipt],
    *,
    claim_id: str | None = None,
    content_id: str | None = None,
    source_id: str | None = None,
    collection_id: str | None = None,
    provider_id: str | None = None,
    operation: str | None = None,
) -> tuple[OperationUsageReceipt, ...]:
    filters = {
        "claim_id": claim_id,
        "content_id": content_id,
        "source_id": source_id,
        "collection_id": collection_id,
        "provider_id": provider_id,
        "operation": operation,
    }
    return tuple(
        row
        for row in receipts
        if all(
            expected is None or getattr(row, field_name) == expected
            for field_name, expected in filters.items()
        )
    )


__all__ = [
    "BILLING_BASES",
    "OPERATION_LEDGER_VERSION",
    "OperationLedgerSummary",
    "OperationUsageReceipt",
    "aggregate_operation_receipts",
    "deterministic_operation_key",
    "filter_operation_receipts",
    "operation_usage_receipt_from_row",
]

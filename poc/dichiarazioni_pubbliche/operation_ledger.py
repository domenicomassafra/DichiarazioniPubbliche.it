from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
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
    local_energy_basis: str | None = None
    cash_cost_uncertainty: str | None = None

    def __post_init__(self) -> None:
        if not str(self.operation_key or "").strip():
            raise ValueError("OPERATION_RECEIPT_KEY_REQUIRED")
        if self.receipt_id is not None and not str(self.receipt_id).strip():
            raise ValueError("OPERATION_RECEIPT_ID_INVALID")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("OPERATION_RECEIPT_ATTEMPT_INVALID")
        if not str(self.provider_id or "").strip() or not str(self.operation or "").strip():
            raise ValueError("OPERATION_RECEIPT_PROVIDER_OPERATION_REQUIRED")
        if self.billing_basis not in BILLING_BASES:
            raise ValueError("OPERATION_RECEIPT_BILLING_BASIS_INVALID")
        if self.estimated_cost_usd is not None and (
            not self.estimated_cost_usd.is_finite() or self.estimated_cost_usd < 0
        ):
            raise ValueError("OPERATION_RECEIPT_ESTIMATE_INVALID")
        if self.measured_cost_usd is not None and (
            not self.measured_cost_usd.is_finite() or self.measured_cost_usd < 0
        ):
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
        if self.local_energy_basis not in (None, "UNKNOWN", "ESTIMATED", "MEASURED"):
            raise ValueError("OPERATION_RECEIPT_LOCAL_ENERGY_BASIS_INVALID")
        if self.cash_cost_uncertainty not in (None, "UNKNOWN"):
            raise ValueError("OPERATION_RECEIPT_CASH_COST_UNCERTAINTY_INVALID")

    @property
    def cash_uncertain(self) -> bool:
        # Raw classifications stay immutable; none attests a free bill or plan.
        return (
            self.cash_cost_uncertainty == "UNKNOWN"
            or self.billing_basis in {"UNKNOWN", "EXTERNAL_PLAN", "ZERO_COST"}
            or (self.billing_basis == "ESTIMATED_ONLY" and self.estimated_cost_usd == 0)
            or (self.billing_basis == "MEASURED_PROVIDER_COST" and self.measured_cost_usd == 0)
        )


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
    unknown_local_energy_operation_count: int = 0

    @property
    def cost_complete(self) -> bool:
        return (
            self.unknown_cost_operation_count == 0
            and self.unknown_local_energy_operation_count == 0
        )


def aggregate_operation_receipts(
    receipts: Iterable[OperationUsageReceipt],
) -> OperationLedgerSummary:
    rows, _ = _unique_operation_attempts(receipts)
    # Count each operation once while preserving each retry's usage.
    operation_keys = {row.operation_key for row in rows}
    measured = Decimal("0")
    estimated_only = Decimal("0")
    external_keys: set[str] = set()
    unknown_keys: set[str] = set()
    zero_keys: set[str] = set()
    unknown_energy_keys: set[str] = set()
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
        if row.cash_cost_uncertainty == "UNKNOWN":
            unknown_keys.add(row.operation_key)
        if row.local_energy_basis in (None, "UNKNOWN"):
            unknown_energy_keys.add(row.operation_key)

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
        unknown_local_energy_operation_count=len(unknown_energy_keys),
    )


def _unique_operation_attempts(
    receipts: Iterable[OperationUsageReceipt],
) -> tuple[tuple[OperationUsageReceipt, ...], int]:
    """Deduplicate exact reads; reject conflicting attempts without rewriting rows."""
    by_attempt: dict[tuple[str, int], OperationUsageReceipt] = {}
    by_receipt: dict[str, OperationUsageReceipt] = {}
    duplicates = 0
    for row in receipts:
        if not isinstance(row, OperationUsageReceipt):
            raise ValueError("OPERATION_RECEIPT_INVALID")
        identity = (row.operation_key, row.attempt)
        prior = by_attempt.get(identity)
        receipt_prior = by_receipt.get(row.receipt_id) if row.receipt_id is not None else None
        if prior is not None:
            if prior != row:
                if prior.receipt_id != row.receipt_id:
                    raise ValueError("OPERATION_ATTEMPT_ID_CONFLICT")
                raise ValueError("OPERATION_RECEIPT_REPLAY_CONFLICT")
            duplicates += 1
            continue
        if receipt_prior is not None:
            raise ValueError("OPERATION_RECEIPT_REPLAY_CONFLICT")
        by_attempt[identity] = row
        if row.receipt_id is not None:
            by_receipt[row.receipt_id] = row
    return tuple(by_attempt.values()), duplicates


_BILLING_REF = re.compile(r"[A-Za-z0-9_:/.-]{1,180}\Z", re.ASCII)
_BILLING_STATUS = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)


@dataclass(frozen=True)
class BillingStatementLine:
    """Unattested statement comparison candidate; never upgrades receipt basis."""

    line_id: str
    receipt_id: str
    operation_key: str
    attempt: int
    provider_id: str
    currency: str
    amount: Decimal
    source_reference: str
    observed_at: str

    def __post_init__(self) -> None:
        for field in ("line_id", "receipt_id", "operation_key", "provider_id", "source_reference"):
            value = getattr(self, field)
            if not isinstance(value, str) or not _BILLING_REF.fullmatch(value):
                raise ValueError("BILLING_LINE_REFERENCE_INVALID")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("BILLING_LINE_ATTEMPT_INVALID")
        if (not isinstance(self.currency, str) or
                not re.fullmatch(r"[A-Z]{3}", self.currency, re.ASCII)):
            raise ValueError("BILLING_LINE_CURRENCY_INVALID")
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite() or self.amount < 0:
            raise ValueError("BILLING_LINE_AMOUNT_INVALID")
        try:
            when = datetime.fromisoformat(self.observed_at)
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise ValueError("BILLING_LINE_OBSERVATION_TIME_INVALID") from None


@dataclass(frozen=True)
class OperationBillingAttempt:
    """Allowlisted immutable private receipt metadata, never a paid approval."""

    receipt_id: str | None
    attempt: int
    status: str
    billing_basis: str
    recorded_measured_usd: Decimal | None
    provisional_estimated_usd: Decimal | None
    cash_uncertainty: bool
    local_energy_basis: str | None
    comparison_status: str


@dataclass(frozen=True)
class OperationBillingGroup:
    operation_key: str
    provider_id: str
    operation: str
    attempt_count: int
    attempts: tuple[OperationBillingAttempt, ...]
    private_only: bool = True
    publication_authority: bool = False


@dataclass(frozen=True)
class OperationBillingReconciliation:
    """Non-authorizing private readout over unmodified usage receipts."""

    operation_count: int
    attempt_count: int
    duplicate_receipt_replays: int
    duplicate_billing_line_replays: int
    recorded_measured_usd: Decimal
    provisional_estimated_usd: Decimal
    unknown_cash_attempts: int
    external_plan_attempts: int
    zero_cost_attempts: int
    unknown_energy_attempts: int
    matched_unverified_billing_lines: int
    disputed_billing_lines: int
    unmatched_billing_lines: int
    uncomparable_currency_lines: int
    groups: tuple[OperationBillingGroup, ...] = ()
    # Receipt basis and caller-supplied statement lines are not invoice proof.
    authoritative_billed_usd: None = None
    plan_quota_consumed: None = None
    subscription_allocation_eur: None = None
    measured_energy_wh: None = None
    invoice_attested: bool = False
    authorizes_dispatch: bool = False

    @property
    def cost_complete(self) -> bool:
        # No independently authenticated provider statement, billing authority,
        # quota entitlement or energy measurement is present in this seam.
        return False


def reconcile_operation_billing(
    receipts: Iterable[OperationUsageReceipt],
    statement_lines: Iterable[BillingStatementLine] = (),
) -> OperationBillingReconciliation:
    """Compare attempts to unverified statements without billing attestation or FX."""
    rows, duplicate_receipts = _unique_operation_attempts(receipts)
    by_attempt = {(r.operation_key, r.attempt): r for r in rows}
    grouped: dict[str, list[OperationUsageReceipt]] = {}
    for r in rows:
        if any(
            not isinstance(label, str) or not _BILLING_REF.fullmatch(label)
            for label in (r.operation_key, r.provider_id, r.operation, r.receipt_id)
        ):
            raise ValueError("OPERATION_RECONCILIATION_IDENTIFIER_INVALID")
        prior = grouped.get(r.operation_key)
        if prior is not None and (
            prior[0].provider_id != r.provider_id
            or prior[0].model_id != r.model_id
            or prior[0].operation != r.operation
        ):
            raise ValueError("OPERATION_KEY_SCOPE_CONFLICT")
        grouped.setdefault(r.operation_key, []).append(r)
    seen_line_ids: dict[str, BillingStatementLine] = {}
    seen_invoice_attempts: set[tuple[str, int, str]] = set()
    comparison: dict[tuple[str, int], str] = {}
    duplicate_lines = matched = disputed = unmatched = foreign_currency = 0
    for line in statement_lines:
        if not isinstance(line, BillingStatementLine):
            raise ValueError("BILLING_LINE_INVALID")
        prior = seen_line_ids.get(line.line_id)
        if prior is not None:
            if prior != line:
                raise ValueError("BILLING_LINE_REPLAY_CONFLICT")
            duplicate_lines += 1
            continue
        statement_identity = (line.operation_key, line.attempt, line.receipt_id)
        if statement_identity in seen_invoice_attempts:
            # One attempt could legitimately have split invoice lines, but
            # without a verified line-allocation rule it cannot be matched
            # more than once or added as an independent settled amount.
            raise ValueError("BILLING_ATTEMPT_MULTIPLE_LINES_UNVERIFIED")
        seen_invoice_attempts.add(statement_identity)
        seen_line_ids[line.line_id] = line
        original = by_attempt.get((line.operation_key, line.attempt))
        if (original is None or original.receipt_id != line.receipt_id
                or original.provider_id != line.provider_id):
            unmatched += 1
        elif line.currency != "USD":
            foreign_currency += 1
            comparison[(line.operation_key, line.attempt)] = "FX_REQUIRED"
        elif (original.billing_basis != "MEASURED_PROVIDER_COST"
              or original.measured_cost_usd != line.amount):
            disputed += 1
            comparison[(line.operation_key, line.attempt)] = "AMOUNT_DISPUTED"
        else:
            matched += 1
            comparison[(line.operation_key, line.attempt)] = "MATCHED_UNVERIFIED"

    groups = tuple(
        OperationBillingGroup(
            operation_key=key,
            provider_id=items[0].provider_id,
            operation=items[0].operation,
            attempt_count=len(items),
            attempts=tuple(
                OperationBillingAttempt(
                    receipt_id=r.receipt_id, attempt=r.attempt,
                    status=(r.status if isinstance(r.status, str)
                        and _BILLING_STATUS.fullmatch(r.status)
                        else "UNRECOGNIZED_STATUS"),
                    billing_basis=r.billing_basis,
                    recorded_measured_usd=(r.measured_cost_usd
                        if r.billing_basis == "MEASURED_PROVIDER_COST" else None),
                    provisional_estimated_usd=(r.estimated_cost_usd
                        if r.billing_basis == "ESTIMATED_ONLY" else None),
                    cash_uncertainty=r.cash_uncertain,
                    local_energy_basis=r.local_energy_basis or "UNKNOWN",
                    comparison_status=comparison.get(
                        (r.operation_key, r.attempt), "NO_STATEMENT_LINE"),
                )
                for r in sorted(items, key=lambda item: item.attempt)
            ),
        )
        for key, items in sorted(grouped.items())
    )

    return OperationBillingReconciliation(
        operation_count=len({r.operation_key for r in rows}),
        attempt_count=len(rows),
        duplicate_receipt_replays=duplicate_receipts,
        duplicate_billing_line_replays=duplicate_lines,
        recorded_measured_usd=sum((r.measured_cost_usd for r in rows
                                   if r.billing_basis == "MEASURED_PROVIDER_COST"), Decimal("0")),
        provisional_estimated_usd=sum((r.estimated_cost_usd for r in rows
                                      if r.billing_basis == "ESTIMATED_ONLY"), Decimal("0")),
        unknown_cash_attempts=sum(r.cash_uncertain for r in rows),
        external_plan_attempts=sum(r.billing_basis == "EXTERNAL_PLAN" for r in rows),
        zero_cost_attempts=sum(r.billing_basis == "ZERO_COST" for r in rows),
        unknown_energy_attempts=sum(r.local_energy_basis in (None, "UNKNOWN") for r in rows),
        matched_unverified_billing_lines=matched,
        disputed_billing_lines=disputed,
        unmatched_billing_lines=unmatched,
        uncomparable_currency_lines=foreign_currency,
        groups=groups,
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
        attempt=int(1 if row.get("attempt") is None else row["attempt"]),
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
        local_energy_basis=str(row.get("local_energy_basis") or "").strip() or None,
        cash_cost_uncertainty=str(row.get("cash_cost_uncertainty") or "").strip() or None,
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
    "BillingStatementLine", "OperationBillingAttempt", "OperationBillingGroup",
    "OperationBillingReconciliation", "reconcile_operation_billing",
    "BILLING_BASES",
    "OPERATION_LEDGER_VERSION",
    "OperationLedgerSummary",
    "OperationUsageReceipt",
    "aggregate_operation_receipts",
    "deterministic_operation_key",
    "filter_operation_receipts",
    "operation_usage_receipt_from_row",
]

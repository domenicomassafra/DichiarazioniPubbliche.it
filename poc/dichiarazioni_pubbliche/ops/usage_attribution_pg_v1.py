"""DP-513: disposable PostgreSQL, *read-only* empirical-usage attribution.

This reader joins the real canonical provider_receipt and the opt-in DP-512
immutable classification events. It cross-checks the existing queue-store
consumer and operation-ledger reconciliation, rather than inventing another
billing table. No provider invoices, account access, device meter readings or
pricing evidence exist in this seam. MEASURED means *recorded* and unverified.
No external HTTP, billing mutation, job admission, provider or cloud calls.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from dichiarazioni_pubbliche.operation_ledger import (
    OperationUsageReceipt,
    operation_usage_receipt_from_row,
    reconcile_operation_billing,
)
from dichiarazioni_pubbliche.ops.billing_pg_fence_v1 import DisposableBillingPgFence
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore

_SAFE_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_VALID_STATUS = {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "TIMEOUT"}


@dataclass(frozen=True)
class AttributedUsageAttempt:
    operation_fingerprint: str
    receipt_fingerprint: str
    provider_id: str
    model_id: str | None
    attempt: int
    status: str
    day_utc: str | None
    billing_basis: str
    billing_confidence: str
    recorded_measured_usd: Decimal | None
    provisional_estimated_usd: Decimal | None
    source_reference_present: bool
    classification_revision: int
    classification_history_count: int
    has_content_link: bool
    has_source_link: bool
    local_energy_basis: str
    invoice_attested: bool = False
    refund_attested: bool = False
    dispatch_authorized: bool = False


@dataclass(frozen=True)
class PrivatePgUsageAttribution:
    attempts: tuple[AttributedUsageAttempt, ...]
    attempt_count: int
    operation_count: int
    provider_count: int
    recorded_measured_usd: Decimal
    provisional_estimated_usd: Decimal
    unknown_cash_attempts: int
    external_plan_attempts: int
    source_reference_missing_attempts: int
    canonical_ledger_parity: bool = True
    account_entitlement_status: str = "UNVERIFIED"
    confirmed_refund_usd: None = None
    invoice_attested: bool = False
    refund_attested: bool = False
    dispatch_authorized: bool = False


# One PostgreSQL READ ONLY repeatable-read snapshot obtains both the immutable
# original fingerprint used by DP-512 and the canonical ledger projection.
# Raw provider_receipt.receipt/ledger_scope, account identifiers, URLs, prompt,
# transcript or request payloads NEVER leave PostgreSQL via this reader.
_SNAPSHOT_SQL = r"""
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT COALESCE(json_agg(json_build_object(
  'ledger', json_build_object(
    'receipt_id',r.id,
    'operation_key',COALESCE(r.operation_key,'legacy:'||r.id),
    'attempt',r.attempt,
    'provider_id',r.provider_id,
    'model_id',r.model_id,
    'operation',r.operation,
    'status',r.status,
    'billing_basis',CASE
      WHEN r.billing_basis='ESTIMATED_ONLY' AND r.estimated_cost_usd IS NULL
      THEN 'UNKNOWN' ELSE r.billing_basis END,
    'estimated_cost_usd',r.estimated_cost_usd,
    'measured_cost_usd',r.measured_cost_usd,
    'total_tokens',r.total_tokens,
    'input_seconds',r.input_seconds,
    'started_at',r.started_at::text,
    'completed_at',r.completed_at::text,
    'duration_seconds',CASE
      WHEN r.started_at IS NOT NULL AND r.completed_at IS NOT NULL
      THEN EXTRACT(EPOCH FROM (r.completed_at-r.started_at))
      ELSE NULL END,
    'request_count',r.request_count,
    'claim_id',NULLIF(r.ledger_scope->>'claim_id',''),
    'content_id',r.content_id,
    'source_id',c.source_id,
    'collection_id',NULLIF(r.ledger_scope->>'collection_id',''),
    'local_energy_basis',NULLIF(r.receipt->>'local_energy_basis',''),
    'cash_cost_uncertainty',NULLIF(r.receipt->>'cash_cost_uncertainty','')
  ),
  'original_fingerprint', md5(to_jsonb(r)::text),
  'state_revision', st.revision,
  'state_original_fingerprint', st.original_fingerprint,
  'history_count', (SELECT COUNT(*) FROM dp512_pg_event ev WHERE ev.receipt_id=r.id),
  'latest', (SELECT json_build_object(
      'revision',ev.revision,
      'original_fingerprint',ev.original_fingerprint,
      'asserted_basis',ev.asserted_basis,
      'asserted_usd',ev.asserted_usd,
      'source_reference_present',ev.evidence_reference_fingerprint IS NOT NULL,
      'result_json', ev.result_json
    ) FROM dp512_pg_event ev WHERE ev.receipt_id=r.id
    ORDER BY ev.revision DESC LIMIT 1)
) ORDER BY COALESCE(r.started_at,r.completed_at),r.id)::text,'[]')
FROM provider_receipt r
LEFT JOIN content_item c ON c.id=r.content_id
LEFT JOIN dp512_pg_state st ON st.receipt_id=r.id;
COMMIT;
"""


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_id(value: str | None) -> bool:
    return isinstance(value, str) and bool(_SAFE_LABEL.fullmatch(value))


def _same_consumer_record(
    row: OperationUsageReceipt, other: OperationUsageReceipt
) -> bool:
    """Full equality on the existing typed ledger consumer contract."""
    return row == other


def _assert_dp512_fence(
    record: dict, receipt: OperationUsageReceipt
) -> tuple[int, int, bool]:
    """Read-only check against the *actual canonical* original receipt bytes."""
    rev = record["state_revision"]
    last = record["latest"]
    count = record["history_count"]
    if rev is None and last is None and count == 0:
        return 0, 0, False
    if (
        type(rev) is not int
        or rev < 1
        or type(count) is not int
        or count != rev
        or not isinstance(last, dict)
        or last.get("revision") != rev
        or last.get("original_fingerprint") != record["original_fingerprint"]
        or record["state_original_fingerprint"] != record["original_fingerprint"]
        or not isinstance(last.get("result_json"), dict)
    ):
        raise ValueError("DP513_CANONICAL_RECEIPT_DRIFT")
    result = last["result_json"]
    expected_basis = receipt.billing_basis
    if expected_basis == "MEASURED_PROVIDER_COST":
        expected_amount = receipt.measured_cost_usd
    elif expected_basis == "ESTIMATED_ONLY":
        expected_amount = receipt.estimated_cost_usd
    else:
        expected_amount = None
    asserted = last.get("asserted_usd")
    try:
        money_same = (expected_amount is None and asserted is None) or (
            expected_amount is not None
            and asserted is not None
            and Decimal(str(asserted)) == expected_amount
        )
    except (ValueError, ArithmeticError):
        money_same = False
    if (
        last.get("asserted_basis") != expected_basis
        or not money_same
        or result.get("invoice_attested") is not False
        or result.get("dispatch_authorized") is not False
        or result.get("receipt_id") != receipt.receipt_id
        or result.get("revision") != rev
        or result.get("basis") != expected_basis
        or result.get("source_reference_present")
        is not last.get("source_reference_present")
    ):
        raise ValueError("DP513_CANONICAL_RECEIPT_DRIFT")
    return rev, count, bool(last["source_reference_present"])


class DisposablePgUsageAttribution:
    """Read-only fixture-bound PG attribution, no provider or invoice authority."""

    def __init__(self, dsn: str):
        # Reuse DP-512's strict localhost + dp512_test_* DSN gate, but never
        # call install_disposable_schema() or record() here.
        self._billing_client = DisposableBillingPgFence(dsn)
        self._dsn = dsn

    def _snapshot_document(self) -> list[dict]:
        """A bounded, independent PG read-only canonical+DP-512 snapshot.

        Including the full original-row fingerprint means even private receipt
        JSON/ledger_scope edits (which the queue projection intentionally omits)
        change this readback. The DP-512 event revision/metadata similarly
        detects appended billing corrections invisible to the queue consumer.
        """
        try:
            document = json.loads(self._billing_client._run(_SNAPSHOT_SQL))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("DP513_PG_SNAPSHOT_INVALID") from exc
        if not isinstance(document, list) or len(document) > 10000:
            raise ValueError("DP513_PG_SNAPSHOT_INVALID")
        return document

    def read(
        self,
        *,
        _consumer: Callable[[], tuple[OperationUsageReceipt, ...]] | None = None,
    ) -> PrivatePgUsageAttribution:
        """Read one canonical PG snapshot and require exact consumer parity.

        The optional _consumer is a test-only seam for a concurrent mutation
        between the snapshot and the queue's independent connection.
        """
        document = self._snapshot_document()
        canonical: list[OperationUsageReceipt] = []
        for entry in document:
            if not isinstance(entry, dict) or not isinstance(entry.get("ledger"), dict):
                raise ValueError("DP513_PG_SNAPSHOT_INVALID")
            try:
                canonical.append(operation_usage_receipt_from_row(entry["ledger"]))
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise ValueError("DP513_PG_SNAPSHOT_INVALID") from exc

        # Do not trust an independent consumer read if a writer committed
        # between the snapshot and its query. No snapshot can confer live
        # entitlement/charge authority, even if the parity test succeeds.
        consumer = tuple(
            _consumer()
            if _consumer is not None
            else QueueExecutionCostStore(self._dsn).operation_ledger_receipts()
        )
        if len(consumer) != len(canonical) or not all(
            _same_consumer_record(a, b)
            for a, b in zip(canonical, consumer, strict=True)
        ):
            raise ValueError("DP513_CANONICAL_READ_DRIFT")
        # The independent queue consumer does not project private receipt JSON,
        # ledger_scope extras or append-only DP-512 event revisions. A second
        # real PostgreSQL snapshot must match the initial *complete* row hashes
        # and billing history; otherwise a concurrent committed edit could be
        # mistaken for a current report despite typed ledger parity. This is
        # bounded readback consistency, NOT a durable lease over future writes.
        if self._snapshot_document() != document:
            raise ValueError("DP513_CANONICAL_READ_DRIFT")
        try:
            summary = reconcile_operation_billing(tuple(canonical))
        except ValueError as exc:
            code = str(exc)
            if "ATTEMPT" in code or "RECEIPT_REPLAY" in code:
                raise ValueError("DP513_CANONICAL_ATTEMPT_CONFLICT") from exc
            raise ValueError("DP513_CANONICAL_LEDGER_INVALID") from exc
        attempts: list[AttributedUsageAttempt] = []
        missing_source_reference = 0
        for entry, receipt in zip(document, canonical, strict=True):
            if (
                not _safe_id(receipt.provider_id)
                or not _safe_id(receipt.operation_key)
                or not _safe_id(receipt.receipt_id)
                or (receipt.model_id is not None and not _safe_id(receipt.model_id))
            ):
                raise ValueError("DP513_CANONICAL_IDENTITY_INVALID")
            revision, event_count, reference = _assert_dp512_fence(entry, receipt)
            basis = receipt.billing_basis
            confidence = {
                "UNKNOWN": "UNPRICED",
                "ESTIMATED_ONLY": "PROVISIONAL_ESTIMATE",
                "EXTERNAL_PLAN": "PLAN_QUOTA_UNVERIFIED",
                "ZERO_COST": "RECORDED_ZERO_UNVERIFIED",
            }.get(
                basis,
                "RECORDED_MEASURED_REFERENCE_UNVERIFIED"
                if reference
                else "RECORDED_MEASURED_REFERENCE_MISSING",
            )
            if basis == "MEASURED_PROVIDER_COST" and not reference:
                missing_source_reference += 1
            day = None
            if receipt.completed_at is not None:
                try:
                    date = datetime.fromisoformat(receipt.completed_at)
                    if date.tzinfo is None or date.utcoffset() is None:
                        raise ValueError("missing timezone")
                    day = date.astimezone(timezone.utc).date().isoformat()
                except ValueError as exc:
                    raise ValueError("DP513_RECEIPT_TIME_INVALID") from exc
            attempts.append(
                AttributedUsageAttempt(
                    operation_fingerprint=_fingerprint(receipt.operation_key),
                    receipt_fingerprint=_fingerprint(receipt.receipt_id),
                    provider_id=receipt.provider_id,
                    model_id=receipt.model_id,
                    attempt=receipt.attempt,
                    status=receipt.status
                    if receipt.status in _VALID_STATUS
                    else "UNRECOGNIZED_STATUS",
                    day_utc=day,
                    billing_basis=basis,
                    billing_confidence=confidence,
                    recorded_measured_usd=(
                        receipt.measured_cost_usd
                        if basis == "MEASURED_PROVIDER_COST"
                        else None
                    ),
                    provisional_estimated_usd=(
                        receipt.estimated_cost_usd
                        if basis == "ESTIMATED_ONLY"
                        else None
                    ),
                    source_reference_present=reference,
                    classification_revision=revision,
                    classification_history_count=event_count,
                    has_content_link=receipt.content_id is not None,
                    has_source_link=receipt.source_id is not None,
                    # Caller/receipt-supplied energy is never meter proof.
                    local_energy_basis="UNKNOWN",
                )
            )
        return PrivatePgUsageAttribution(
            attempts=tuple(attempts),
            attempt_count=summary.attempt_count,
            operation_count=summary.operation_count,
            provider_count=len({item.provider_id for item in attempts}),
            recorded_measured_usd=summary.recorded_measured_usd,
            provisional_estimated_usd=summary.provisional_estimated_usd,
            unknown_cash_attempts=summary.unknown_cash_attempts,
            external_plan_attempts=summary.external_plan_attempts,
            source_reference_missing_attempts=missing_source_reference,
        )


__all__ = [
    "AttributedUsageAttempt",
    "PrivatePgUsageAttribution",
    "DisposablePgUsageAttribution",
]

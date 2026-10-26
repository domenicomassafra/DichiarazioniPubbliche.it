"""Canonical D receipt for an investigated source that made zero provider requests.

The reservation belongs to the durable DP-319 attempt store. This adapter
records only observable *local* work in the existing PostgreSQL D ledger; it
cannot authorize a provider request, infer an Antigravity entitlement or settle
an unverified provider bill.
"""

from __future__ import annotations

import hashlib
import json

from dichiarazioni_pubbliche.investigation_attempts_store_v1 import (
    InvestigationReservation,
    InvestigationSourceRecord,
)
from dichiarazioni_pubbliche.operation_ledger import deterministic_operation_key
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

_OPERATION = "DP319_PRIVATE_SOURCE_INSPECTION"
_PROVIDER = "local:no-provider"


class PrivateDReceiptLedger(PsqlRuntime):
    def record_zero_attempt(
        self,
        *,
        attempt: InvestigationReservation,
        source: InvestigationSourceRecord,
        content_id: str,
        rights_record_id: str,
    ) -> str:
        """Idempotently attest zero external requests for this bounded attempt.

        The caller must have already persisted a reservation and verified the
        exact current right. Every replay checks the complete immutable receipt.
        A failed write keeps the SQLite reservation pending (unknown effects).
        """
        if (
            attempt.source_sha256 != source.source_sha256
            or attempt.source_version != source.source_version
            or attempt.source_id != source.source_id
            or attempt.candidate_id != source.candidate_id
            or attempt.source_revision != source.revision
            or attempt.material_fingerprint != source.material_fingerprint
            or source.rights_status != "CLEARED"
            or source.policy_status != "ALLOWED"
            or attempt.dispatch_authorized
            or attempt.publication_authority
            or not content_id
            or not rights_record_id
        ):
            raise ValueError("DP319_D_SOURCE_RESERVATION_MISMATCH")
        receipt_id = (
            "receipt:"
            + hashlib.sha256(
                ("dp319-d-zero-v1\0" + attempt.attempt_id).encode()
            ).hexdigest()
        )
        operation_key = deterministic_operation_key(
            operation=_OPERATION,
            input_fingerprint=attempt.plan_fingerprint + ":" + source.source_sha256,
            provider_id=_PROVIDER,
        )
        scope = {
            "attempt_id": attempt.attempt_id,
            "plan_fingerprint": attempt.plan_fingerprint,
            "source_sha256": source.source_sha256,
            "source_version": source.source_version,
        }
        proof = {
            "schema": "dp319-d-zero-v1",
            "rights_record_id": rights_record_id,
            "provider_dispatch_count": 0,
            "quota_units_consumed": 0,
            "reason": "LOCAL_PINNED_SOURCE_INSPECTION",
        }
        raw = self.run(
            """
            BEGIN;
            SET LOCAL lock_timeout = '2500ms';
            SELECT pg_advisory_xact_lock(hashtextextended(:'receipt_id', 0));
            INSERT INTO provider_receipt (
                id, content_id, provider_id, operation, operation_key, attempt,
                started_at, completed_at, estimated_cost_usd, measured_cost_usd,
                billing_basis, request_count, ledger_scope, status, receipt
            ) VALUES (
                :'receipt_id', :'content_id', :'provider_id', :'operation',
                :'operation_key', 1, now(), now(), 0, 0, 'ZERO_COST', 0,
                :'scope'::jsonb, 'COMPLETED', :'proof'::jsonb
            ) ON CONFLICT (id) DO NOTHING;
            SELECT row_to_json(r)::text FROM (
                SELECT id, content_id, provider_id, model_id, request_id,
                       input_bytes, input_seconds, total_tokens,
                       operation, operation_key,
                       attempt, estimated_cost_usd, measured_cost_usd,
                       billing_basis, request_count, ledger_scope, status, receipt
                FROM provider_receipt WHERE id=:'receipt_id'
            ) r;
            COMMIT;
            """,
            receipt_id=receipt_id,
            content_id=content_id,
            provider_id=_PROVIDER,
            operation=_OPERATION,
            operation_key=operation_key,
            scope=json.dumps(scope, sort_keys=True),
            proof=json.dumps(proof, sort_keys=True),
            execution_timeout_seconds=5.0,
        )
        rows = [line for line in raw.splitlines() if line.startswith("{")]
        if len(rows) != 1:
            raise ValueError("DP319_D_RECEIPT_NOT_CONFIRMED")
        persisted = json.loads(rows[0])
        expected = {
            "id": receipt_id,
            "content_id": content_id,
            "provider_id": _PROVIDER,
            "model_id": None,
            "request_id": None,
            "input_bytes": None,
            "input_seconds": None,
            "total_tokens": None,
            "operation": _OPERATION,
            "operation_key": operation_key,
            "attempt": 1,
            "estimated_cost_usd": 0,
            "measured_cost_usd": 0,
            "billing_basis": "ZERO_COST",
            "request_count": 0,
            "ledger_scope": scope,
            "status": "COMPLETED",
            "receipt": proof,
        }
        if persisted != expected:
            raise ValueError("DP319_D_RECEIPT_CONFLICT")
        return receipt_id

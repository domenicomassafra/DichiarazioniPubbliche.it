"""DP-319C2: bounded subscription dispatch fenced by canonical PostgreSQL D.

The caller supplies fresh, private rights and OmniRoute route readbacks.
No local observation can establish the 12 subscription entitlements by itself.
Each durable reservation is pessimistically pending-unknown before the POST;
only the process that inserted it may invoke the provider, exactly once.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from dichiarazioni_pubbliche.investigation_attempts_store_v1 import (
    InvestigationReservation,
    InvestigationSourceRecord,
)
from dichiarazioni_pubbliche.operation_ledger import deterministic_operation_key
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime

_MODEL = "antigravity/gemini-3.8-flash-tiered"
_FINGERPRINT = re.compile(r"[a-f0-9]{64}\Z")
_PRIVATE_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}\Z")
_OPERATION = "DP319_SUBSCRIPTION_SOURCE_INSPECTION"


@dataclass(frozen=True)
class SubscriptionGate:
    """Verified private readback, supplied by the authorized OmniRoute consumer."""

    model: str
    account_scope: str
    authorized_connection_fingerprints: tuple[str, ...]
    observed_connection_fingerprints: tuple[str, ...]
    subscription_only: bool
    paid_fallback_disabled: bool
    quota_remaining: int | None
    quota_upper_bound: int
    valid_until: datetime
    evidence_ref: str
    quota_window_id: str = "subscription-window:current"

    def blocker(self) -> str | None:
        accounts = self.authorized_connection_fingerprints
        if (
            self.model != _MODEL
            or not self.account_scope.startswith("subscription:")
            or not _PRIVATE_REF.fullmatch(self.account_scope)
            or len(accounts) != 12
            or len(set(accounts)) != 12
            or any(not _FINGERPRINT.fullmatch(value) for value in accounts)
            or set(accounts) != set(self.observed_connection_fingerprints)
            or len(self.observed_connection_fingerprints) != 12
            or not self.subscription_only
            or not self.paid_fallback_disabled
            or not _PRIVATE_REF.fullmatch(self.evidence_ref)
            or not _PRIVATE_REF.fullmatch(self.quota_window_id)
        ):
            return "SUBSCRIPTION_ROUTE_UNVERIFIED"
        if self.valid_until.tzinfo is None or self.valid_until <= datetime.now(
            timezone.utc
        ):
            return "SUBSCRIPTION_QUOTA_UNATTESTED"
        if (
            type(self.quota_remaining) is not int
            or type(self.quota_upper_bound) is not int
        ):
            return "SUBSCRIPTION_QUOTA_UNATTESTED"
        if self.quota_remaining <= 0:
            return "SUBSCRIPTION_QUOTA_EXHAUSTED"
        if self.quota_upper_bound <= 0 or self.quota_remaining < self.quota_upper_bound:
            return "SUBSCRIPTION_QUOTA_UNATTESTED"
        return None


@dataclass(frozen=True)
class SubscriptionOutcome:
    status: str
    reason_code: str
    receipt_id: str | None
    provider_billing_reconciled: bool = False
    dispatch_authorized: bool = False
    new_child_task_count: int = 0


def _receipt(
    response: object,
    model: str,
    *,
    quota_verified: bool,
) -> tuple[str, int, dict[str, object]]:
    """Only metering fields of an authenticated response enter the private ledger."""
    if not isinstance(response, dict) or response.get("model") != model:
        raise ValueError("SUBSCRIPTION_RESPONSE_UNVERIFIED")
    request_id = response.get("id")
    usage = response.get("usage")
    if (
        not isinstance(request_id, str)
        or not request_id.strip()
        or not isinstance(usage, dict)
    ):
        raise ValueError("SUBSCRIPTION_RESPONSE_UNVERIFIED")
    fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in fields):
        raise ValueError("SUBSCRIPTION_USAGE_UNVERIFIED")
    if usage["total_tokens"] < usage["prompt_tokens"] + usage["completion_tokens"]:
        raise ValueError("SUBSCRIPTION_USAGE_UNVERIFIED")
    quota = response.get("quota")
    units = None
    unit = None
    ref = None
    if isinstance(quota, dict):
        candidate = quota.get("units_consumed")
        if (
            quota_verified
            and type(candidate) is int
            and 0 <= candidate <= 1_000_000
            and quota.get("unit") == "subscription-quota-unit"
            and isinstance(quota.get("receipt_ref"), str)
            and quota["receipt_ref"].strip()
        ):
            units = candidate
            unit = quota["unit"]
            ref = quota["receipt_ref"]
    proof = {
        "schema": "dp319-d-subscription-v1",
        "quota_units_consumed": units,
        "quota_unit": unit,
        "quota_evidence_ref": ref,
        "provider_billing_reconciled": units is not None,
        "usage": {key: usage[key] for key in fields},
    }
    return request_id, usage["total_tokens"], proof


class SubscriptionDDispatch(PsqlRuntime):
    def run_once(
        self,
        *,
        source: InvestigationSourceRecord,
        attempt: InvestigationReservation,
        content_id: str,
        rights_record_id: str,
        gate: SubscriptionGate,
        current_rights: Callable[[], bool],
        send: Callable[[], dict[str, object]],
        verify_usage_evidence: Callable[[dict[str, object]], bool] | None = None,
    ) -> SubscriptionOutcome:
        """Fence one authorized operation; uncertain replays never invoke send.

        current_rights must re-read the grant for this exact source version and
        OMNIROUTE_MODEL_EXTRACTION_PRIVATE use. The consumer must build gate
        from a fresh key-scoped OmniRoute readback of these exact subscriptions,
        bind send to that gateway/key, and verify_usage_evidence against the
        original provider usage record. A caller without that evidence must
        leave the route closed; missing quota metering is never treated as zero.
        """

        def hold(reason: str, receipt_id: str | None = None) -> SubscriptionOutcome:
            return SubscriptionOutcome("WAIT_EXTERNAL", reason, receipt_id)

        if (
            source.rights_status != "CLEARED"
            or source.policy_status != "ALLOWED"
            or attempt.source_sha256 != source.source_sha256
            or attempt.source_version != source.source_version
            or attempt.source_id != source.source_id
            or attempt.candidate_id != source.candidate_id
            or attempt.source_revision != source.revision
            or attempt.material_fingerprint != source.material_fingerprint
            or attempt.publication_authority
            or attempt.dispatch_authorized is not True
            or not content_id
            or not rights_record_id
        ):
            return hold("SUBSCRIPTION_SOURCE_RESERVATION_MISMATCH")
        receipt_id = (
            "receipt:"
            + hashlib.sha256(
                (
                    "dp319-d-subscription-v1\0"
                    + attempt.attempt_id
                    + "\0"
                    + source.source_sha256
                    + "\0"
                    + source.source_version
                ).encode()
            ).hexdigest()
        )
        key = deterministic_operation_key(
            operation=_OPERATION,
            input_fingerprint=attempt.plan_fingerprint
            + ":"
            + source.source_sha256
            + ":"
            + source.source_version,
            provider_id="omniroute",
            model_id=gate.model,
        )
        scope = {
            "attempt_id": attempt.attempt_id,
            "plan_fingerprint": attempt.plan_fingerprint,
            "source_sha256": source.source_sha256,
            "source_version": source.source_version,
            "rights_record_id": rights_record_id,
            "account_scope": gate.account_scope,
            "quota_window_id": gate.quota_window_id,
            "quota_upper_bound": gate.quota_upper_bound,
            "evidence_ref": gate.evidence_ref,
        }
        pending = {
            "schema": "dp319-d-subscription-v1",
            "quota_units_consumed": None,
            "provider_billing_reconciled": False,
            "effects": "UNKNOWN",
        }
        # Existing completed receipts must be replayable even if a subscription
        # has subsequently exhausted its quota or the old snapshot has expired.
        try:
            exists = self.run(
                "SELECT count(*) FROM provider_receipt WHERE id=:'id';",
                id=receipt_id,
                execution_timeout_seconds=5.0,
            ).strip()
        except (OSError, RuntimeError, ValueError):
            return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)
        if exists == "1":
            try:
                if current_rights() is not True:
                    return hold("SOURCE_RIGHTS_REVOKED", receipt_id)
            except Exception:
                return hold("SOURCE_RIGHTS_UNAVAILABLE", receipt_id)
            return self._readback(receipt_id, scope, hold)
        if exists != "0":
            return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)
        reason = gate.blocker()
        if reason:
            return hold(reason)
        try:
            if current_rights() is not True:
                return hold("SOURCE_RIGHTS_REVOKED")
        except Exception:
            return hold("SOURCE_RIGHTS_UNAVAILABLE")
        try:
            reserved = self.run(
                """
                BEGIN;
                SET LOCAL lock_timeout='2500ms';
                SELECT pg_advisory_xact_lock(hashtextextended(:'account_scope' || ':' || :'window', 0));
                WITH admissible AS (
                    SELECT NOT EXISTS(SELECT 1 FROM provider_receipt WHERE id=:'id')
                      AND NOT EXISTS(
                          SELECT 1 FROM provider_receipt
                          WHERE provider_id='omniroute' AND status='PENDING_UNKNOWN'
                            AND ledger_scope->>'account_scope'=:'account_scope'
                            AND ledger_scope->>'quota_window_id'=:'window'
                      )
                      AND COALESCE((
                        SELECT SUM(GREATEST(
                            (ledger_scope->>'quota_upper_bound')::integer,
                            COALESCE((receipt->>'quota_units_consumed')::integer, 0)
                        ))
                        FROM provider_receipt
                        WHERE provider_id='omniroute'
                          AND ledger_scope->>'account_scope'=:'account_scope'
                          AND ledger_scope->>'quota_window_id'=:'window'
                      ), 0) + :'upper'::integer <= :'remaining'::integer AS ok
                ), inserted AS (
                    INSERT INTO provider_receipt (
                        id, content_id, provider_id, model_id, operation, operation_key,
                        attempt, started_at, billing_basis, request_count,
                        ledger_scope, status, receipt
                    )
                    SELECT :'id', :'content_id', 'omniroute', :'model', :'operation',
                           :'operation_key', 1, now(), 'EXTERNAL_PLAN', 0,
                           :'scope'::jsonb, 'PENDING_UNKNOWN', :'pending'::jsonb
                    FROM admissible WHERE ok
                    ON CONFLICT (id) DO NOTHING RETURNING id
                )
                SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'RESERVED'
                            WHEN EXISTS(SELECT 1 FROM provider_receipt WHERE id=:'id')
                                 THEN 'REPLAY_HELD'
                            WHEN EXISTS(
                                SELECT 1 FROM provider_receipt
                                WHERE provider_id='omniroute' AND status='PENDING_UNKNOWN'
                                  AND ledger_scope->>'account_scope'=:'account_scope'
                                  AND ledger_scope->>'quota_window_id'=:'window'
                            ) THEN 'PREVIOUS_UNKNOWN'
                            ELSE 'QUOTA_REACHED' END;
                COMMIT;
                """,
                id=receipt_id,
                account_scope=gate.account_scope,
                window=gate.quota_window_id,
                upper=gate.quota_upper_bound,
                remaining=gate.quota_remaining,
                content_id=content_id,
                model=gate.model,
                operation=_OPERATION,
                operation_key=key,
                scope=json.dumps(scope, sort_keys=True),
                pending=json.dumps(pending, sort_keys=True),
                execution_timeout_seconds=5.0,
            ).splitlines()
        except (OSError, RuntimeError, ValueError):
            return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)
        decisions = [
            line
            for line in reserved
            if line in ("RESERVED", "REPLAY_HELD", "PREVIOUS_UNKNOWN", "QUOTA_REACHED")
        ]
        if decisions == ["PREVIOUS_UNKNOWN"]:
            return hold("SUBSCRIPTION_PENDING_UNKNOWN_EFFECTS")
        if decisions == ["QUOTA_REACHED"]:
            return hold("SUBSCRIPTION_QUOTA_EXHAUSTED")
        if decisions == ["REPLAY_HELD"]:
            return self._readback(receipt_id, scope, hold)
        if decisions != ["RESERVED"]:
            return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)

        # Reservation is already durable. Revocation or an exception here leaves
        # PENDING_UNKNOWN forever; recovery must never resend this attempt.
        try:
            if gate.blocker() is not None:
                return hold("SUBSCRIPTION_QUOTA_UNATTESTED", receipt_id)
            if current_rights() is not True:
                return hold("SOURCE_RIGHTS_REVOKED", receipt_id)
        except Exception:
            return hold("SOURCE_RIGHTS_UNAVAILABLE", receipt_id)
        try:
            response = send()
        except Exception as exc:
            reason = (
                "SUBSCRIPTION_QUOTA_EXHAUSTED"
                if any(
                    token in str(exc).upper()
                    for token in ("HTTP_429", "QUOTA_EXHAUSTED", "RESOURCE_EXHAUSTED")
                )
                else "SUBSCRIPTION_PROVIDER_UNAVAILABLE"
            )
            return hold(reason, receipt_id)
        try:
            quota_verified = False
            if verify_usage_evidence is not None:
                try:
                    quota_verified = verify_usage_evidence(response) is True
                except Exception:
                    quota_verified = False
            request_id, tokens, proof = _receipt(
                response,
                gate.model,
                quota_verified=quota_verified,
            )
            updated = self.run(
                """
                UPDATE provider_receipt
                SET request_id=:'request_id', total_tokens=:'tokens'::bigint,
                    request_count=1, completed_at=now(), status='COMPLETED',
                    receipt=:'proof'::jsonb
                WHERE id=:'id' AND status='PENDING_UNKNOWN'
                  AND ledger_scope=:'scope'::jsonb
                RETURNING id;
                """,
                id=receipt_id,
                scope=json.dumps(scope, sort_keys=True),
                request_id=request_id,
                tokens=tokens,
                proof=json.dumps(proof, sort_keys=True),
                execution_timeout_seconds=5.0,
            )
            if updated.strip() != receipt_id:
                return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)
            return SubscriptionOutcome(
                "RECONCILED",
                "OK",
                receipt_id,
                provider_billing_reconciled=bool(proof["provider_billing_reconciled"]),
            )
        except (ValueError, RuntimeError, OSError):
            return hold("SUBSCRIPTION_RECEIPT_UNVERIFIED", receipt_id)

    def _readback(
        self,
        receipt_id: str,
        scope: dict[str, object],
        hold: Callable[[str, str | None], SubscriptionOutcome],
    ) -> SubscriptionOutcome:
        try:
            raw = self.run(
                "SELECT row_to_json(r)::text FROM (SELECT ledger_scope,status,receipt,"
                " provider_id,model_id,operation,billing_basis,request_id,"
                " request_count,total_tokens "
                "FROM provider_receipt WHERE id=:'id') r;",
                id=receipt_id,
                execution_timeout_seconds=5.0,
            )
            rows = [
                json.loads(line) for line in raw.splitlines() if line.startswith("{")
            ]
            if len(rows) != 1:
                return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)
            old = rows[0]
            for field in (
                "attempt_id",
                "plan_fingerprint",
                "source_sha256",
                "source_version",
                "rights_record_id",
                "account_scope",
            ):
                if old["ledger_scope"].get(field) != scope[field]:
                    return hold("SUBSCRIPTION_RECEIPT_CONFLICT", receipt_id)
            if old["status"] != "COMPLETED":
                return hold("SUBSCRIPTION_PENDING_UNKNOWN_EFFECTS", receipt_id)
            proof = old["receipt"]
            usage = proof.get("usage") if isinstance(proof, dict) else None
            if (
                old["provider_id"] != "omniroute"
                or old["model_id"] != _MODEL
                or old["operation"] != _OPERATION
                or old["billing_basis"] != "EXTERNAL_PLAN"
                or old["request_count"] != 1
                or not isinstance(old["request_id"], str)
                or not old["request_id"].strip()
                or not isinstance(usage, dict)
                or proof.get("schema") != "dp319-d-subscription-v1"
                or any(
                    type(usage.get(field)) is not int or usage[field] < 0
                    for field in ("prompt_tokens", "completion_tokens", "total_tokens")
                )
                or old["total_tokens"] != usage["total_tokens"]
                or usage["total_tokens"]
                < usage["prompt_tokens"] + usage["completion_tokens"]
                or (
                    proof.get("provider_billing_reconciled") is True
                    and (
                        type(proof.get("quota_units_consumed")) is not int
                        or proof["quota_units_consumed"] < 0
                        or proof.get("quota_unit") != "subscription-quota-unit"
                        or not isinstance(proof.get("quota_evidence_ref"), str)
                        or not proof["quota_evidence_ref"].strip()
                    )
                )
            ):
                return hold("SUBSCRIPTION_RECEIPT_CONFLICT", receipt_id)
            return SubscriptionOutcome(
                "RECONCILED",
                "REPLAY",
                receipt_id,
                provider_billing_reconciled=proof.get("provider_billing_reconciled")
                is True,
            )
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            return hold("SUBSCRIPTION_LEDGER_UNAVAILABLE", receipt_id)

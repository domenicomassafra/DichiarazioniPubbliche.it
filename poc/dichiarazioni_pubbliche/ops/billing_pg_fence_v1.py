"""DP-512: isolated PostgreSQL CAS of canonical provider_receipt classification.

This is a *disposable test DB only* ledger. It re-reads the real canonical
provider_receipt row under a PostgreSQL row lock, never rewrites that row, and
appends a private classification event. Billed-measured here means **recorded
by the old writer**, NOT attested against provider invoices. Nothing authorizes
work, debits budget, verifies invoice origin or issues money.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.operation_ledger import BILLING_BASES


_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}\Z")
_REF = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,255}\Z")
_MICRO = Decimal("0.000001")

_DDL = r"""
BEGIN;
DO $do$
BEGIN
 IF current_database() NOT LIKE 'dp512_test_%' THEN
  RAISE EXCEPTION 'BILLING_DISPOSABLE_DATABASE_REQUIRED';
 END IF;
 IF to_regclass('public.provider_receipt') IS NULL THEN
  RAISE EXCEPTION 'BILLING_CANONICAL_PROVIDER_RECEIPT_MISSING';
 END IF;
END $do$;
CREATE TABLE IF NOT EXISTS dp512_pg_state (
  receipt_id text PRIMARY KEY REFERENCES provider_receipt(id),
  revision integer NOT NULL CHECK (revision >= 0),
  original_fingerprint text NOT NULL CHECK(length(original_fingerprint)=32)
);
CREATE TABLE IF NOT EXISTS dp512_pg_event (
  event_id text PRIMARY KEY,
  receipt_id text NOT NULL REFERENCES dp512_pg_state(receipt_id),
  revision integer NOT NULL CHECK(revision > 0),
  expected_revision integer NOT NULL,
  original_fingerprint text NOT NULL,
  asserted_basis text NOT NULL,
  asserted_usd numeric(12,6),
  evidence_reference_fingerprint text,
  result_json jsonb NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (receipt_id, revision)
);
CREATE OR REPLACE FUNCTION dp512_pg_immutable_event() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
 RAISE EXCEPTION 'append-only dp512 event';
END $fn$;
DROP TRIGGER IF EXISTS dp512_event_append_only ON dp512_pg_event;
CREATE TRIGGER dp512_event_append_only
 BEFORE UPDATE OR DELETE ON dp512_pg_event
 FOR EACH ROW EXECUTE FUNCTION dp512_pg_immutable_event();

CREATE OR REPLACE FUNCTION dp512_pg_record(
 p_receipt text, p_event text, p_revision integer, p_basis text,
 p_asserted numeric, p_evidence text
) RETURNS jsonb LANGUAGE plpgsql AS $fn$
DECLARE
 original provider_receipt%ROWTYPE;
 original_hash text;
 current_row dp512_pg_state%ROWTYPE;
 previous dp512_pg_event%ROWTYPE;
 expected_value numeric(12,6);
 evidence_hash text;
 result jsonb;
 receipt_count integer;
BEGIN
 IF current_database() NOT LIKE 'dp512_test_%' THEN
  RAISE EXCEPTION 'BILLING_DISPOSABLE_DATABASE_REQUIRED';
 END IF;
 SELECT * INTO original FROM provider_receipt WHERE id=p_receipt FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'BILLING_CANONICAL_RECEIPT_MISSING'; END IF;
 IF original.operation_key IS NULL OR btrim(original.operation_key)=''
    OR original.attempt < 1 THEN
  RAISE EXCEPTION 'BILLING_CANONICAL_IDENTITY_INVALID';
 END IF;
 SELECT count(*) INTO receipt_count FROM provider_receipt
    WHERE operation_key=original.operation_key AND attempt=original.attempt;
 IF receipt_count <> 1 THEN
  RAISE EXCEPTION 'BILLING_CANONICAL_ATTEMPT_AMBIGUOUS';
 END IF;
 original_hash := md5(to_jsonb(original)::text);
 IF p_basis IS DISTINCT FROM original.billing_basis THEN
  RAISE EXCEPTION 'BILLING_CLASSIFICATION_CONFLICT';
 END IF;
 IF p_basis='MEASURED_PROVIDER_COST' THEN
   expected_value := original.measured_cost_usd;
   IF p_evidence IS NULL THEN RAISE EXCEPTION 'BILLING_PROVENANCE_REQUIRED'; END IF;
 ELSIF p_basis='ESTIMATED_ONLY' THEN
   expected_value := original.estimated_cost_usd;
   IF expected_value IS NULL THEN
    RAISE EXCEPTION 'BILLING_ESTIMATE_UNAVAILABLE';
   END IF;
 ELSE
   expected_value := NULL;
 END IF;
 IF p_basis NOT IN ('UNKNOWN','ESTIMATED_ONLY',
   'MEASURED_PROVIDER_COST','EXTERNAL_PLAN','ZERO_COST')
   OR p_asserted IS DISTINCT FROM expected_value THEN
  RAISE EXCEPTION 'BILLING_CLASSIFICATION_CONFLICT';
 END IF;
 evidence_hash := CASE WHEN p_evidence IS NULL THEN NULL ELSE md5(p_evidence) END;
 INSERT INTO dp512_pg_state(receipt_id,revision,original_fingerprint)
 VALUES(p_receipt,0,original_hash) ON CONFLICT DO NOTHING;
 SELECT * INTO current_row FROM dp512_pg_state
  WHERE receipt_id=p_receipt FOR UPDATE;
 IF current_row.original_fingerprint <> original_hash THEN
  RAISE EXCEPTION 'BILLING_ORIGINAL_DRIFT';
 END IF;
 SELECT * INTO previous FROM dp512_pg_event WHERE event_id=p_event;
 IF FOUND THEN
  IF previous.receipt_id<>p_receipt
     OR previous.expected_revision<>p_revision
     OR previous.asserted_basis<>p_basis
     OR previous.asserted_usd IS DISTINCT FROM p_asserted
     OR previous.evidence_reference_fingerprint IS DISTINCT FROM evidence_hash
     OR previous.original_fingerprint<>original_hash THEN
    RAISE EXCEPTION 'BILLING_EVENT_REPLAY_CONFLICT';
  END IF;
  RETURN previous.result_json;
 END IF;
 IF current_row.revision<>p_revision THEN
  RAISE EXCEPTION 'BILLING_REVISION_CONFLICT';
 END IF;
 result := jsonb_build_object(
  'revision',p_revision+1,
  'basis',p_basis,
  'recorded_usd',CASE WHEN expected_value IS NULL THEN NULL
    ELSE to_char(expected_value,'FM999999999990.000000') END,
  'cash_status',CASE
   WHEN p_basis='MEASURED_PROVIDER_COST' THEN 'RECORDED_MEASURED_UNVERIFIED'
   WHEN p_basis='ESTIMATED_ONLY' THEN 'ESTIMATE_NOT_BILL'
   WHEN p_basis='EXTERNAL_PLAN' THEN 'PLAN_ENTITLEMENT_UNVERIFIED'
   WHEN p_basis='ZERO_COST' THEN 'RECORDED_ZERO_UNVERIFIED'
   ELSE 'UNPRICED' END,
  'attempt',original.attempt,
  'receipt_id',p_receipt,
  'operation_fingerprint',md5(original.operation_key),
  'source_reference_present',evidence_hash IS NOT NULL,
  'invoice_attested',false,
  'zero_cost_verified',false,
  'dispatch_authorized',false,
  'cash_settled',false,
  -- The nested receipt is private, untrusted JSON. Never echo arbitrary
  -- strings or legacy labels through the sanitized classification result.
  'local_energy_basis',CASE
    WHEN original.receipt->>'local_energy_basis' IN ('UNKNOWN','ESTIMATED','MEASURED')
      THEN original.receipt->>'local_energy_basis'
    ELSE 'UNKNOWN' END
 );
 INSERT INTO dp512_pg_event(
  event_id,receipt_id,revision,expected_revision,original_fingerprint,
  asserted_basis,asserted_usd,evidence_reference_fingerprint,result_json)
 VALUES(p_event,p_receipt,p_revision+1,p_revision,original_hash,
        p_basis,p_asserted,evidence_hash,result);
 UPDATE dp512_pg_state SET revision=revision+1 WHERE receipt_id=p_receipt
  AND revision=p_revision;
 IF NOT FOUND THEN RAISE EXCEPTION 'BILLING_REVISION_CONFLICT'; END IF;
 RETURN result;
END $fn$;
COMMIT;
"""


def _label(value: object, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"BILLING_{name}_INVALID")
    return value


def _money(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError("BILLING_AMOUNT_INVALID")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("BILLING_AMOUNT_INVALID") from exc
    if not number.is_finite() or number < 0 or number > Decimal("999999.999999"):
        raise ValueError("BILLING_AMOUNT_INVALID")
    if number != number.quantize(_MICRO):
        raise ValueError("BILLING_AMOUNT_PRECISION_INVALID")
    return f"{number:.6f}"


class DisposableBillingPgFence:
    """A tightly scoped psql client for a local test database only."""

    def __init__(self, dsn: str):
        u = urlsplit(dsn)
        if (
            u.scheme not in {"postgresql", "postgres"}
            or u.hostname not in {"127.0.0.1", "localhost"}
            or not u.path.startswith("/dp512_test_")
            or u.query
            or u.fragment
        ):
            raise ValueError("BILLING_DISPOSABLE_DSN_REQUIRED")
        if shutil.which("psql") is None:
            raise RuntimeError("BILLING_PSQL_MISSING")
        self.dsn = dsn

    def _run(self, sql: str, **params: str) -> str:
        command = [
            "psql",
            "-X",
            "-q",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            self.dsn,
        ]
        for k, v in params.items():
            command.extend(["-v", f"{k}={v}"])
        result = subprocess.run(
            command,
            input=sql,
            text=True,
            capture_output=True,
            timeout=25,
            check=False,
        )
        if result.returncode != 0:
            msg = result.stderr
            for code in (
                "BILLING_CANONICAL_RECEIPT_MISSING",
                "BILLING_CANONICAL_IDENTITY_INVALID",
                "BILLING_CANONICAL_ATTEMPT_AMBIGUOUS",
                "BILLING_CLASSIFICATION_CONFLICT",
                "BILLING_PROVENANCE_REQUIRED",
                "BILLING_ESTIMATE_UNAVAILABLE",
                "BILLING_ORIGINAL_DRIFT",
                "BILLING_EVENT_REPLAY_CONFLICT",
                "BILLING_REVISION_CONFLICT",
                "BILLING_DISPOSABLE_DATABASE_REQUIRED",
            ):
                if code in msg:
                    raise ValueError(code) from None
            raise RuntimeError("BILLING_PG_TRANSACTION_FAILED") from None
        return result.stdout.strip()

    def install_disposable_schema(self) -> None:
        self._run(_DDL)

    def record(
        self,
        *,
        receipt_id: str,
        event_id: str,
        expected_revision: int,
        asserted_basis: str,
        asserted_usd: str | Decimal | int | None,
        evidence_ref: str | None,
    ) -> dict[str, object]:
        _label(receipt_id, "RECEIPT_ID")
        _label(event_id, "EVENT_ID")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("BILLING_REVISION_INVALID")
        if asserted_basis not in BILLING_BASES:
            raise ValueError("BILLING_BASIS_INVALID")
        if evidence_ref is not None and (
            not isinstance(evidence_ref, str) or not _REF.fullmatch(evidence_ref)
        ):
            raise ValueError("BILLING_EVIDENCE_REFERENCE_INVALID")
        money = "" if asserted_usd is None else _money(asserted_usd)
        output = self._run(
            "SELECT dp512_pg_record(:'receipt', :'event', :'revision'::integer,"
            " :'basis', NULLIF(:'money','')::numeric,"
            " NULLIF(:'evidence',''))::text;",
            receipt=receipt_id,
            event=event_id,
            revision=str(expected_revision),
            basis=asserted_basis,
            money=money,
            evidence=evidence_ref or "",
        )
        result = json.loads(output)
        if (
            not isinstance(result, dict)
            or result.get("dispatch_authorized") is not False
        ):
            raise RuntimeError("BILLING_PG_RESULT_UNSAFE")
        return result


__all__ = ["DisposableBillingPgFence"]

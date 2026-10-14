"""DP-514 isolated canonical PostgreSQL liability reference, never spend authority.

Reads the actual DP-512 source-of-truth provider_receipt/classification ledger
and independently reconciles DP-513 operation-attribution rows. The added
append-only observations/refund claims are *unverified* local receipts: no
claim releases budget or establishes a provider invoice, FX or entitlement.
No live writer, scheduler, model, account, provider or MiniPC calls this seam.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from dichiarazioni_pubbliche.ops.billing_pg_fence_v1 import DisposableBillingPgFence
from dichiarazioni_pubbliche.ops.cost_policy import monthly_period
from dichiarazioni_pubbliche.ops.usage_attribution_pg_v1 import DisposablePgUsageAttribution

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_ERR = re.compile(r"DP514_[A-Z_]+")
_MICRO = Decimal("0.000001")
_CI_DISPOSABLE_DSN = re.compile(
    r"postgresql://postgres@127\.0\.0\.1:[1-9][0-9]{0,4}/dp512_test_[a-z0-9_]+\Z"
)
_CI_SQLSTATE = re.compile(r"\b(?:ERROR|FATAL|PANIC):\s+([A-Z0-9]{5}):")
# Only fixed diagnostic identifiers leave this process; raw psql stderr stays private.
_CI_SQLSTATE_CATEGORIES = {
    "57014": "QUERY_CANCELED",
    "55P03": "LOCK_UNAVAILABLE",
    "40P01": "DEADLOCK",
    "40001": "SERIALIZATION",
    "08001": "CONNECTION",
    "08006": "CONNECTION",
    "57P01": "SERVER_SHUTDOWN",
    "23505": "CONSTRAINT",
    "23503": "CONSTRAINT",
    "42P01": "SCHEMA",
    "42501": "ACCESS",
    "22012": "ARITHMETIC",
}
_CI_OPERATIONS = frozenset({"SNAPSHOT", "APPEND", "SCHEMA_INSTALL"})

# Opt-in only on the disposable CI connection, never on an owner/production DB.
# Each snapshot gets an independent private marker. Concurrent snapshots must
# never read each other's lock/wait state or emit the marker in diagnostics.
_CI_WAIT_APP_PREFIX = "dp514_ci_snapshot_"
_CI_WAIT_APP_RE = re.compile(r"dp514_ci_snapshot_[0-9a-f]{32}\Z")
_CI_WAIT_STATES = frozenset({"active", "idle", "idle_in_transaction", "other"})
_CI_WAIT_TYPES = frozenset({
    "NONE", "Lock", "LWLock", "IO", "Client", "IPC", "Timeout",
    "Activity", "BufferPin", "Extension", "OTHER",
})
_CI_WAIT_EVENTS = frozenset({
    "NONE", "OTHER", "relation", "transactionid", "tuple", "advisory",
    "extend", "object", "virtualxid", "page", "spectoken",
    "DataFileRead", "DataFileWrite", "WALWrite", "WALSync", "PgSleep",
    "ClientRead", "ClientWrite", "BufferPin",
})
_CI_WAIT_SQL = """
SELECT concat_ws('|',
  CASE a.state WHEN 'active' THEN 'active' WHEN 'idle' THEN 'idle'
    WHEN 'idle in transaction' THEN 'idle_in_transaction' ELSE 'other' END,
  COALESCE(a.wait_event_type, 'NONE'), COALESCE(a.wait_event, 'NONE'),
  CASE WHEN EXISTS (SELECT 1 FROM pg_locks l
    WHERE l.pid = a.pid AND NOT l.granted) THEN '1' ELSE '0' END,
  CASE WHEN cardinality(pg_blocking_pids(a.pid)) > 0 THEN '1' ELSE '0' END)
FROM pg_stat_activity a
WHERE a.datname = current_database()
  AND a.application_name = '{app_name}'
  AND a.pid <> pg_backend_pid()
  AND a.backend_type = 'client backend'
LIMIT 2
"""


def _ci_wait_valid(row: object) -> bool:
    return (
        isinstance(row, tuple) and len(row) == 5
        and all(isinstance(value, str) for value in row)
        and row[0] in _CI_WAIT_STATES
        and row[1] in _CI_WAIT_TYPES
        and row[2] in _CI_WAIT_EVENTS
        and row[3] in {"0", "1"} and row[4] in {"0", "1"}
    )


def _ci_wait_probe(dsn: str, app_name: str) -> tuple[str, str, str, str, str] | None:
    """Accept a sample only when exactly one backend has this private marker."""
    if (_CI_DISPOSABLE_DSN.fullmatch(dsn) is None
        or not isinstance(app_name, str)
        or _CI_WAIT_APP_RE.fullmatch(app_name) is None):
        return None
    try:
        result = subprocess.run(
            ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
             "-d", dsn, "-c", _CI_WAIT_SQL.format(app_name=app_name)],
            capture_output=True, text=True, timeout=1, check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        return None
    if result.returncode != 0 or not isinstance(result.stdout, str) or len(result.stdout) > 128:
        return None
    # A second matching activity row is ambiguous even when its wait fields
    # differ. Never select an arbitrary backend by LIMIT 1 or row ordering.
    lines = result.stdout.splitlines()
    if len(lines) != 1:
        return None
    row = tuple(lines[0].strip().split("|"))
    if len(row) == 5 and row[0] in _CI_WAIT_STATES and row[3] in {"0", "1"} and row[4] in {"0", "1"}:
        # PostgreSQL may add wait-event names in future releases. Collapse
        # unknown names to a constant, never propagate server strings.
        row = (row[0], row[1] if row[1] in _CI_WAIT_TYPES else "OTHER",
               row[2] if row[2] in _CI_WAIT_EVENTS else "OTHER", row[3], row[4])
    return row if _ci_wait_valid(row) else None


def _ci_wait_summary(samples: list[tuple[str, str, str, str, str]]) -> str:
    """Reduce samples to a fixed allowlisted line with no SQL, IDs or raw data."""
    safe = [row for row in samples[-16:] if _ci_wait_valid(row)]
    if not safe:
        return "status=NO_SAMPLE samples=0"
    # The latest sample represents the last observed state. Earlier lock waits
    # are historical evidence, never a substitute for a subsequently cleared wait.
    selected = safe[-1]
    state, wait_type, wait_event, ungranted, blocker = selected
    historical_blocker_seen = int(any(
        row[3] == "1" or row[4] == "1" for row in safe[:-1]
    ))
    return (
        f"status=OBSERVED samples={len(safe)} state={state} "
        f"wait_type={wait_type} wait_event={wait_event} "
        f"ungranted_lock={ungranted} blocker={blocker} "
        f"historical_blocker_seen={historical_blocker_seen}"
    )


class _CiWaitWitness:
    """Read-only, bounded background sampler while the snapshot is in flight."""

    def __init__(self, dsn: str, app_name: str):
        self._dsn = dsn
        self._app_name = app_name
        self._stop = threading.Event()
        self._samples: list[tuple[str, str, str, str, str]] = []
        self._thread = threading.Thread(target=self._collect, daemon=True)

    def _collect(self) -> None:
        while not self._stop.wait(0.5):
            try:
                row = _ci_wait_probe(self._dsn, self._app_name)
            except Exception:
                # A diagnostic thread must never leak a subprocess error or
                # turn a valid financial snapshot into an application error.
                return
            if row is not None:
                if len(self._samples) == 16:
                    self._samples.pop(0)
                self._samples.append(row)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> list[tuple[str, str, str, str, str]]:
        self._stop.set()
        self._thread.join(timeout=1.1)
        return list(self._samples)

_DDL = r"""
BEGIN;
DO $guard$ BEGIN
  IF current_database() NOT LIKE 'dp512_test_%'
     OR to_regclass('public.provider_receipt') IS NULL
     OR to_regclass('public.dp512_pg_state') IS NULL
     OR to_regclass('public.dp512_pg_event') IS NULL
  THEN RAISE EXCEPTION 'DP514_DISPOSABLE_CANONICAL_REQUIRED'; END IF;
END $guard$;
CREATE TABLE IF NOT EXISTS dp514_pg_state (
  receipt_id text PRIMARY KEY REFERENCES provider_receipt(id),
  revision integer NOT NULL CHECK(revision > 0),
  original_fingerprint text NOT NULL CHECK(length(original_fingerprint)=32)
);
CREATE TABLE IF NOT EXISTS dp514_pg_event (
  event_id text PRIMARY KEY,
  receipt_id text NOT NULL REFERENCES dp514_pg_state(receipt_id),
  revision integer NOT NULL CHECK(revision > 0),
  expected_revision integer NOT NULL CHECK(expected_revision >= 0),
  original_fingerprint text NOT NULL,
  billing_revision integer NOT NULL CHECK(billing_revision > 0),
  kind text NOT NULL CHECK(kind IN ('OBSERVED','REFUND_CLAIM')),
  asserted_usd numeric(12,6),
  cash_settled boolean NOT NULL DEFAULT false CHECK(cash_settled=false),
  refund_attested boolean NOT NULL DEFAULT false CHECK(refund_attested=false),
  dispatch_authorized boolean NOT NULL DEFAULT false CHECK(dispatch_authorized=false),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(receipt_id, revision)
);
CREATE OR REPLACE FUNCTION dp514_pg_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'DP514_APPEND_ONLY'; END $$;
DROP TRIGGER IF EXISTS dp514_event_immutable ON dp514_pg_event;
CREATE TRIGGER dp514_event_immutable BEFORE UPDATE OR DELETE ON dp514_pg_event
 FOR EACH ROW EXECUTE FUNCTION dp514_pg_immutable();
DROP TRIGGER IF EXISTS dp514_state_no_delete ON dp514_pg_state;
CREATE TRIGGER dp514_state_no_delete BEFORE DELETE ON dp514_pg_state
 FOR EACH ROW EXECUTE FUNCTION dp514_pg_immutable();

CREATE OR REPLACE FUNCTION dp514_pg_append(
  p_receipt text, p_event text, p_revision integer, p_kind text, p_usd numeric)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
  original provider_receipt%ROWTYPE;
  original_hash text;
  billing dp512_pg_state%ROWTYPE;
  billing_last dp512_pg_event%ROWTYPE;
  state_row dp514_pg_state%ROWTYPE;
  prior dp514_pg_event%ROWTYPE;
  expected_usd numeric(12,6);
  receipt_count integer;
BEGIN
  IF current_database() NOT LIKE 'dp512_test_%' THEN
    RAISE EXCEPTION 'DP514_DISPOSABLE_CANONICAL_REQUIRED';
  END IF;
  -- A globally unique event ID can race between *different* canonical
  -- receipt row locks; lock the event namespace before inspecting/replaying.
  PERFORM pg_advisory_xact_lock(hashtextextended('dp514:' || p_event, 0));
  -- Locks also serialize with the canonical DP-512 classification CAS.
  SELECT * INTO original FROM provider_receipt WHERE id=p_receipt FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'DP514_RECEIPT_UNKNOWN'; END IF;
  IF original.operation_key IS NULL OR original.attempt < 1 THEN
    RAISE EXCEPTION 'DP514_ATTEMPT_INVALID';
  END IF;
  SELECT COUNT(*) INTO receipt_count FROM provider_receipt
   WHERE operation_key=original.operation_key AND attempt=original.attempt;
  IF receipt_count<>1 THEN RAISE EXCEPTION 'DP514_AMBIGUOUS_ATTEMPT'; END IF;
  original_hash := md5(to_jsonb(original)::text);
  SELECT * INTO billing FROM dp512_pg_state
   WHERE receipt_id=p_receipt FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'DP514_CLASSIFICATION_MISSING'; END IF;
  SELECT * INTO billing_last FROM dp512_pg_event
   WHERE receipt_id=p_receipt ORDER BY revision DESC LIMIT 1;
  IF billing.original_fingerprint <> original_hash
    OR billing_last.revision IS DISTINCT FROM billing.revision
    OR billing_last.original_fingerprint IS DISTINCT FROM original_hash
    OR billing_last.asserted_basis IS DISTINCT FROM original.billing_basis
    OR billing_last.asserted_usd IS DISTINCT FROM
      (CASE original.billing_basis
       WHEN 'MEASURED_PROVIDER_COST' THEN original.measured_cost_usd
       WHEN 'ESTIMATED_ONLY' THEN original.estimated_cost_usd
       ELSE NULL END)
  THEN RAISE EXCEPTION 'DP514_CANONICAL_DRIFT'; END IF;
  expected_usd := CASE original.billing_basis
    WHEN 'MEASURED_PROVIDER_COST' THEN original.measured_cost_usd
    WHEN 'ESTIMATED_ONLY' THEN original.estimated_cost_usd ELSE NULL END;
  IF p_kind='OBSERVED' THEN
    IF p_usd IS DISTINCT FROM expected_usd THEN
      RAISE EXCEPTION 'DP514_AMOUNT_CONFLICT';
    END IF;
  ELSIF p_kind='REFUND_CLAIM' THEN
    -- A self-reported refund is an audit claim; never a negative spend.
    IF expected_usd IS NULL OR p_usd IS NULL
       OR p_usd > expected_usd THEN
      RAISE EXCEPTION 'DP514_REFUND_UNSUPPORTED';
    END IF;
  ELSE RAISE EXCEPTION 'DP514_EVENT_KIND_INVALID'; END IF;

  SELECT * INTO state_row FROM dp514_pg_state
   WHERE receipt_id=p_receipt FOR UPDATE;
  IF FOUND AND state_row.original_fingerprint <> original_hash THEN
    RAISE EXCEPTION 'DP514_CANONICAL_DRIFT';
  END IF;
  SELECT * INTO prior FROM dp514_pg_event WHERE event_id=p_event;
  IF FOUND THEN
    IF prior.receipt_id<>p_receipt
      OR prior.expected_revision<>p_revision
      OR prior.kind<>p_kind OR prior.asserted_usd IS DISTINCT FROM p_usd
      OR prior.original_fingerprint<>original_hash
      OR prior.billing_revision<>billing.revision THEN
       RAISE EXCEPTION 'DP514_EVENT_REPLAY_CONFLICT';
    END IF;
    RETURN jsonb_build_object(
      'revision',prior.revision,'receipt_id',prior.receipt_id,
      'kind',prior.kind,'recorded_usd',prior.asserted_usd::text,
      'invoice_attested',false,'refund_attested',false,
      'dispatch_authorized',false);
  END IF;
  IF coalesce(state_row.revision,0)<>p_revision THEN
    RAISE EXCEPTION 'DP514_REVISION_CONFLICT';
  END IF;
  INSERT INTO dp514_pg_state(receipt_id,revision,original_fingerprint)
   VALUES(p_receipt,1,original_hash)
   ON CONFLICT(receipt_id) DO UPDATE SET revision=p_revision+1
   WHERE dp514_pg_state.revision=p_revision
     AND dp514_pg_state.original_fingerprint=original_hash;
  IF NOT FOUND THEN RAISE EXCEPTION 'DP514_REVISION_CONFLICT'; END IF;
  INSERT INTO dp514_pg_event(
    event_id,receipt_id,revision,expected_revision,original_fingerprint,
    billing_revision,kind,asserted_usd
  ) VALUES(
    p_event,p_receipt,p_revision+1,p_revision,original_hash,
    billing.revision,p_kind,p_usd
  );
  RETURN jsonb_build_object(
    'revision',p_revision+1,'receipt_id',p_receipt,'kind',p_kind,
    'recorded_usd',p_usd::text,'invoice_attested',false,
    'refund_attested',false,'dispatch_authorized',false);
END $$;
COMMIT;
"""

# One real PG REPEATABLE READ snapshot. Raw receipt JSON and private scope are
# deliberately excluded; the next independent DP-513 read checks ledger parity.
# In a freshly bootstrapped disposable database, missing table statistics can
# inflate this one-row query's estimated cost above jit_above_cost. Avoid JIT
# compilation inside this bounded snapshot transaction; do not change session
# defaults, financial behavior, or the existing statement/lock timeout gates.
_SNAPSHOT = r"""
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL jit=off;
SELECT COALESCE(json_agg(json_build_object(
  'id',r.id,'operation_key',r.operation_key,'attempt',r.attempt,
  'basis',CASE WHEN r.billing_basis='ESTIMATED_ONLY' AND
    r.estimated_cost_usd IS NULL THEN 'UNKNOWN'
    ELSE r.billing_basis END,'status',r.status,
  'started',r.started_at::text,'completed',r.completed_at::text,
  'estimated',r.estimated_cost_usd::text,
  'measured',r.measured_cost_usd::text,
  'fingerprint',md5(to_jsonb(r)::text),
  'billing_revision',b.revision,
  'billing_fingerprint',b.original_fingerprint,
  'liability_revision',l.revision,
  'liability_fingerprint',l.original_fingerprint,
  'event_count',(SELECT count(*) FROM dp514_pg_event ev WHERE ev.receipt_id=r.id),
  'latest_event',(SELECT json_build_object(
    'revision',ev.revision,'kind',ev.kind,'asserted',ev.asserted_usd::text,
    'billing_revision',ev.billing_revision,'original_fingerprint',ev.original_fingerprint)
   FROM dp514_pg_event ev WHERE ev.receipt_id=r.id
   ORDER BY ev.revision DESC LIMIT 1),
  'refund_claims', (SELECT count(*) FROM dp514_pg_event ev
    WHERE ev.receipt_id=r.id AND ev.kind='REFUND_CLAIM'),
  'refund_claim_usd', (SELECT coalesce(sum(ev.asserted_usd),0)::text
    FROM dp514_pg_event ev WHERE ev.receipt_id=r.id AND ev.kind='REFUND_CLAIM'),
  'observation_events',(SELECT count(*) FROM dp514_pg_event ev
    WHERE ev.receipt_id=r.id AND ev.kind='OBSERVED')
) ORDER BY coalesce(r.started_at,r.completed_at),r.id)::text,'[]')
FROM provider_receipt r
LEFT JOIN dp512_pg_state b ON b.receipt_id=r.id
LEFT JOIN dp514_pg_state l ON l.receipt_id=r.id;
COMMIT;
"""


@dataclass(frozen=True)
class MonthlyLiabilityPeriod:
    period: str
    attempts: int
    recorded_measured_usd: Decimal
    provisional_estimated_usd: Decimal
    unknown_attempts: int
    refund_claim_events: int
    billed_eur: None = None
    refunded_eur: None = None
    provisional_eur: None = None
    reserved_maximum_eur: None = None
    subscription_allocation_eur: None = None
    incremental_energy_eur: None = None
    invoice_attested: bool = False


@dataclass(frozen=True)
class MonthlyLiabilityReport:
    months: tuple[MonthlyLiabilityPeriod, ...]
    total_attempts: int
    unknown_attempts: int
    prior_unknown_attempts: int
    plan_or_unpriced_attempts: int
    recorded_measured_usd: Decimal
    provisional_estimated_usd: Decimal
    unverified_refund_claim_usd: Decimal
    refund_claim_events: int
    observation_events: int
    hold_new_spend: bool
    billed_eur: None = None
    refunded_eur: None = None
    invoice_attested: bool = False
    refund_attested: bool = False
    dispatch_authorized: bool = False
    usd_daily_caps_verified: bool = False
    fx_attested: bool = False


def _money(value: str | Decimal | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError("DP514_AMOUNT_INVALID")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("999999.999999"):
            raise ValueError
        if amount != amount.quantize(_MICRO):
            raise ValueError
    except (ValueError, InvalidOperation):
        raise ValueError("DP514_AMOUNT_INVALID") from None
    return format(amount, ".6f")


class DisposableMonthlyLiabilityPg:
    """PG17-only local test seam; strict DP-512 disposable DSN inherited."""

    def __init__(self, dsn: str):
        self._billing = DisposableBillingPgFence(dsn)
        self._reader = DisposablePgUsageAttribution(dsn)
        self._dsn = dsn

    def _run(self, sql: str, *, _family: str = "OTHER", **params: str) -> str:
        # This opt-in exists only for ephemeral CI PostgreSQL fixtures. Never
        # include SQL, DSNs, stderr, receipt IDs, or provider payloads in logs.
        diagnose = (
            os.environ.get("CI") == "true"
            and os.environ.get("DP514_CI_PG_DIAGNOSTIC") == "1"
            and _CI_DISPOSABLE_DSN.fullmatch(self._dsn) is not None
        )
        watch = (
            diagnose and _family == "SNAPSHOT"
            and os.environ.get("DP514_CI_PG_WAIT_WITNESS") == "1"
        )
        args = ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", self._dsn]
        if diagnose:
            args.extend(["-v", "VERBOSITY=verbose"])
        for key, value in params.items():
            if not re.fullmatch("[a-z_]+", key):
                raise ValueError("DP514_PARAMETER_INVALID")
            args.extend(["-v", f"{key}={value}"])
        started = time.monotonic()
        app_name = _CI_WAIT_APP_PREFIX + secrets.token_hex(16) if watch else None
        witness = _CiWaitWitness(self._dsn, app_name) if app_name is not None else None
        if witness is not None:
            try:
                witness.start()
            except RuntimeError:
                # Monitoring is diagnostic only; it never controls the query.
                witness = None
        samples: list[tuple[str, str, str, str, str]] = []
        try:
            completed = subprocess.run(
                args, input="SET statement_timeout='10000ms'; "
                "SET lock_timeout='8000ms';\n" + sql,
                capture_output=True, text=True, timeout=25, check=False,
                **({"env": {**os.environ, "PGAPPNAME": app_name}}
                   if witness is not None else {}),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("DP514_PG_UNAVAILABLE") from None
        finally:
            if witness is not None:
                samples = witness.stop()
        if completed.returncode:
            err = _ERR.search(completed.stderr)
            if err:
                raise ValueError(err.group(0)) from None
            if diagnose:
                match = _CI_SQLSTATE.search(completed.stderr[:4096])
                state = (match.group(1) if match and
                         match.group(1) in _CI_SQLSTATE_CATEGORIES else "UNKNOWN")
                category = _CI_SQLSTATE_CATEGORIES.get(state, "UNKNOWN")
                family = _family if _family in _CI_OPERATIONS else "OTHER"
                code = completed.returncode
                exit_code = code if type(code) is int and -255 <= code <= 255 else "UNKNOWN"
                elapsed_ms = min(25000, max(0, int((time.monotonic() - started) * 1000)))
                print(
                    "DP514_CI_PG_DIAGNOSTIC"
                    f" operation={family} exit_code={exit_code}"
                    f" sqlstate={state} category={category} elapsed_ms={elapsed_ms}",
                    file=sys.stderr,
                )
                if state == "57014" and witness is not None and _family == "SNAPSHOT":
                    print("DP514_CI_PG_WAIT_WITNESS " + _ci_wait_summary(samples),
                          file=sys.stderr)
            raise RuntimeError("DP514_PG_TRANSACTION_FAILED") from None
        return completed.stdout.strip()

    def install_disposable_schema(self) -> None:
        self._run(_DDL, _family="SCHEMA_INSTALL")

    def append(
        self, *, receipt_id: str, event_id: str, expected_revision: int,
        kind: str, amount_usd: str | Decimal | int | None,
    ) -> dict[str, object]:
        if not isinstance(receipt_id, str) or not _ID.fullmatch(receipt_id):
            raise ValueError("DP514_RECEIPT_ID_INVALID")
        if not isinstance(event_id, str) or not _ID.fullmatch(event_id):
            raise ValueError("DP514_EVENT_ID_INVALID")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("DP514_REVISION_INVALID")
        if kind not in {"OBSERVED", "REFUND_CLAIM"}:
            raise ValueError("DP514_EVENT_KIND_INVALID")
        data = self._run(
            "BEGIN; SELECT dp514_pg_append(:'receipt',:'event',:'revision'::integer,"
            " :'kind',NULLIF(:'amount','')::numeric)::text; COMMIT;",
            _family="APPEND", receipt=receipt_id, event=event_id,
            revision=str(expected_revision),
            kind=kind, amount=_money(amount_usd),
        ).splitlines()
        if len(data) != 1:
            raise RuntimeError("DP514_PG_RESULT_INVALID")
        outcome = json.loads(data[0])
        if (not isinstance(outcome, dict)
            or outcome.get("invoice_attested") is not False
            or outcome.get("refund_attested") is not False
            or outcome.get("dispatch_authorized") is not False):
            raise RuntimeError("DP514_PG_RESULT_UNSAFE")
        return outcome

    def _snapshot(self) -> list[dict[str, object]]:
        try:
            rows = json.loads(self._run(_SNAPSHOT, _family="SNAPSHOT"))
        except (ValueError, TypeError) as exc:
            raise ValueError("DP514_SNAPSHOT_INVALID") from exc
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError("DP514_SNAPSHOT_INVALID")
        return rows

    def read(
        self, *, as_of: datetime, timezone_name: str = "Europe/Rome",
        _between=None,
    ) -> MonthlyLiabilityReport:
        """Independent DP-513 parity, bracketed by two exact PG snapshots."""
        current_period = monthly_period(as_of, timezone_name)
        before = self._snapshot()
        usage = self._reader.read()
        if _between is not None:
            _between()
        after = self._snapshot()
        if before != after:
            raise ValueError("DP514_READ_DRIFT")
        by_fp = {a.receipt_fingerprint: a for a in usage.attempts}
        if len(before) != usage.attempt_count or len(by_fp) != len(before):
            raise ValueError("DP514_CANONICAL_PARITY_FAILURE")
        grouped: dict[str, list[dict[str, object]]] = {}
        totals = {"measured": Decimal(0), "estimated": Decimal(0),
                  "refund": Decimal(0)}
        unknown = prior_unknown = plan_unknown = refunds = observations = 0
        unknown_receipt_ids: set[str] = set()
        for row in before:
            if not isinstance(row, dict):
                raise ValueError("DP514_SNAPSHOT_INVALID")
            receipt_id = row.get("id")
            if not isinstance(receipt_id, str):
                raise ValueError("DP514_SNAPSHOT_INVALID")
            entry = by_fp.get(hashlib.sha256(receipt_id.encode()).hexdigest())
            if entry is None or row.get("basis") != entry.billing_basis or (
                row.get("billing_revision") or 0
            ) != entry.classification_revision:
                raise ValueError("DP514_CANONICAL_PARITY_FAILURE")
            if (row["liability_revision"] is None) != (row["latest_event"] is None):
                raise ValueError("DP514_LIABILITY_INTEGRITY")
            if row["liability_revision"] is not None:
                last = row["latest_event"]
                if (not isinstance(last, dict)
                    or row["liability_revision"] != row["event_count"]
                    or row["liability_revision"] != last["revision"]
                    or row["liability_fingerprint"] != row["fingerprint"]
                    or last["original_fingerprint"] != row["fingerprint"]
                    or last["billing_revision"] != row["billing_revision"]):
                    raise ValueError("DP514_LIABILITY_INTEGRITY")
            at_text = row.get("started") or row.get("completed")
            try:
                instant = datetime.fromisoformat(str(at_text))
                period = monthly_period(instant, timezone_name)
            except (ValueError, TypeError):
                period = "UNKNOWN"
            grouped.setdefault(period, []).append(row)
            basis = row["basis"]
            unpriced = (period == "UNKNOWN" or entry.classification_revision == 0
                        or basis in {"UNKNOWN", "EXTERNAL_PLAN", "ZERO_COST"}
                        or (basis == "ESTIMATED_ONLY" and entry.provisional_estimated_usd is None)
                        or (basis == "MEASURED_PROVIDER_COST"
                            and not entry.source_reference_present))
            if unpriced:
                unknown += 1
                unknown_receipt_ids.add(receipt_id)
                plan_unknown += int(basis in {"EXTERNAL_PLAN", "ZERO_COST"})
                if period == "UNKNOWN" or period < current_period:
                    prior_unknown += 1
            if basis == "MEASURED_PROVIDER_COST" and entry.recorded_measured_usd is not None:
                totals["measured"] += entry.recorded_measured_usd
            if basis == "ESTIMATED_ONLY" and entry.provisional_estimated_usd is not None:
                totals["estimated"] += entry.provisional_estimated_usd
            totals["refund"] += Decimal(str(row["refund_claim_usd"]))
            refunds += int(row["refund_claims"])
            observations += int(row["observation_events"])
        months: list[MonthlyLiabilityPeriod] = []
        for period, records in sorted(grouped.items()):
            measured = sum((by_fp[hashlib.sha256(r["id"].encode()).hexdigest()]
                            .recorded_measured_usd or Decimal(0)
                            for r in records), Decimal(0))
            estimated = sum((by_fp[hashlib.sha256(r["id"].encode()).hexdigest()]
                             .provisional_estimated_usd or Decimal(0)
                             for r in records), Decimal(0))
            count_unknown = sum(1 for r in records if r["id"] in unknown_receipt_ids)
            months.append(MonthlyLiabilityPeriod(
                period=period, attempts=len(records), recorded_measured_usd=measured,
                provisional_estimated_usd=estimated, unknown_attempts=count_unknown,
                refund_claim_events=sum(int(r["refund_claims"]) for r in records),
            ))
        # Unverified refund claims never reduce liability, and even an
        # apparent ZERO_COST/included plan cannot prove available cash.
        return MonthlyLiabilityReport(
            months=tuple(months), total_attempts=len(before),
            unknown_attempts=unknown, prior_unknown_attempts=prior_unknown,
            plan_or_unpriced_attempts=plan_unknown,
            recorded_measured_usd=totals["measured"],
            provisional_estimated_usd=totals["estimated"],
            unverified_refund_claim_usd=totals["refund"],
            refund_claim_events=refunds, observation_events=observations,
            # No real FX/owner grant, atomic job/day/provider quota cap or
            # invoice authority is installed: even all-estimated snapshots
            # must never become a boolean green light for paid dispatch.
            hold_new_spend=True,
        )


__all__ = [
    "DisposableMonthlyLiabilityPg", "MonthlyLiabilityPeriod", "MonthlyLiabilityReport",
]

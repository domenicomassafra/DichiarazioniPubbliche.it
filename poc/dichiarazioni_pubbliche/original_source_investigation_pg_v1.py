"""DP-241 opt-in private PostgreSQL CAS tied to canonical Source/Capture/Passage.

The only supported backend is an explicitly disposable, loopback PostgreSQL DB.
Receipt hashes and local rights rows are *not* signed external search or rights
authorities. Nothing dispatches searches, spends money, publishes or writes
operational source rows. An unconfirmed reservation fences replay after a crash.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.original_source_investigation_v1 import (
    RecoveryPlan,
    RecoveryReceipt,
    SourceRecoveryTarget,
    assess_recovery,
    inspect_recovery_timeline,
)


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9.:_-]{0,199}\Z")
_ERROR = re.compile(r"DP241_PG_[A-Z_]+")


def _literal(value: str) -> str:
    if not isinstance(value, str) or "\x00" in value or len(value) > 2048:
        raise ValueError("DP241_PG_INPUT_INVALID")
    return "'" + value.replace("'", "''") + "'"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PgRecoveryState:
    revision: int
    receipts: tuple[RecoveryReceipt, ...]
    decision: object
    pending_attempt_id: str | None
    publication_authority: bool = False
    dispatch_authorized: bool = False


@dataclass(frozen=True)
class PgRecoveryHistory:
    revision: int
    receipts: tuple[RecoveryReceipt, ...]
    pending_attempt_id: str | None
    publication_authority: bool = False
    dispatch_authorized: bool = False


_FIXTURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS dp241_pg_plan(
 plan_id text PRIMARY KEY,
 scope_digest text NOT NULL,
 source_id text NOT NULL REFERENCES source(id),
 content_id text NOT NULL REFERENCES content_item(id),
 capture_id text NOT NULL REFERENCES content_capture(id),
 passage_id text NOT NULL REFERENCES passage(id),
 source_version_sha text NOT NULL,
 passage_sha text NOT NULL,
 source_provenance_sha text NOT NULL CHECK(source_provenance_sha ~ '^[0-9a-f]{64}$'),
 revision bigint NOT NULL DEFAULT 0 CHECK(revision >= 0)
);
CREATE TABLE IF NOT EXISTS dp241_pg_event(
 plan_id text NOT NULL REFERENCES dp241_pg_plan(plan_id),
 event_no bigint NOT NULL CHECK(event_no > 0),
 kind text NOT NULL CHECK(kind IN ('RESERVED','COMPLETED')),
 attempt_id text NOT NULL,
 request_key text NOT NULL,
 result text,
 discovery_sha text,
 spent_usd numeric,
 PRIMARY KEY(plan_id,event_no),
 UNIQUE(plan_id,attempt_id,kind),
 UNIQUE(plan_id,request_key,kind),
 CHECK ((kind='RESERVED' AND result IS NULL AND discovery_sha IS NULL AND spent_usd IS NULL)
     OR (kind='COMPLETED' AND result IS NOT NULL AND discovery_sha ~ '^[0-9a-f]{64}$'
         AND spent_usd >= 0))
);
CREATE UNIQUE INDEX IF NOT EXISTS dp241_pg_discovery_immutable
 ON dp241_pg_event(discovery_sha) WHERE discovery_sha IS NOT NULL;
CREATE OR REPLACE FUNCTION dp241_pg_no_mutation()
 RETURNS trigger LANGUAGE plpgsql AS $dp241$
 BEGIN RAISE EXCEPTION 'DP241_PG_APPEND_ONLY'; END $dp241$;
DROP TRIGGER IF EXISTS dp241_pg_event_immutable ON dp241_pg_event;
CREATE TRIGGER dp241_pg_event_immutable BEFORE UPDATE OR DELETE ON dp241_pg_event
 FOR EACH ROW EXECUTE FUNCTION dp241_pg_no_mutation();
CREATE OR REPLACE FUNCTION dp241_pg_plan_immutable()
 RETURNS trigger LANGUAGE plpgsql AS $dp241$
 BEGIN
   IF TG_OP='DELETE' OR
      (to_jsonb(NEW) - 'revision') IS DISTINCT FROM
      (to_jsonb(OLD) - 'revision') THEN
     RAISE EXCEPTION 'DP241_PG_PLAN_PROVENANCE_IMMUTABLE';
   END IF;
   RETURN NEW;
 END $dp241$;
DROP TRIGGER IF EXISTS dp241_pg_plan_immutable_trigger ON dp241_pg_plan;
CREATE TRIGGER dp241_pg_plan_immutable_trigger
 BEFORE UPDATE OR DELETE ON dp241_pg_plan
 FOR EACH ROW EXECUTE FUNCTION dp241_pg_plan_immutable();
"""

_LEGACY_DISPOSABLE_UPGRADE = """
BEGIN;
DO $dp241$ BEGIN
 IF to_regclass('public.dp241_pg_plan') IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM pg_attribute
      WHERE attrelid=to_regclass('public.dp241_pg_plan')
        AND attname='source_provenance_sha' AND NOT attisdropped) THEN
   LOCK TABLE dp241_pg_plan IN ACCESS EXCLUSIVE MODE;
   -- No historic rights/source fingerprint existed; retroactive approval is
   -- impossible. Keep all old rows/receipts intact and refuse this upgrade.
   IF EXISTS (SELECT 1 FROM dp241_pg_plan) THEN
     RAISE EXCEPTION 'DP241_PG_LEGACY_PLAN_UNPINNED';
   END IF;
   ALTER TABLE dp241_pg_plan ADD COLUMN source_provenance_sha text
      NOT NULL CHECK(source_provenance_sha ~ '^[0-9a-f]{64}$');
 END IF;
END $dp241$;
COMMIT;
"""


class IsolatedOriginalRecoveryPg:
    """Local no-provider adapter. Scope schema installation to disposable PG."""

    def __init__(self, dsn: str, *, allow_disposable_postgres: bool = False):
        parsed = urlsplit(dsn)
        if (
            allow_disposable_postgres is not True
            or parsed.scheme not in {"postgresql", "postgres"}
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or not parsed.port
            or not parsed.path.endswith("/dp241_disposable")
            or parsed.username != "postgres"
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not shutil.which("psql")
        ):
            raise ValueError("DP241_PG_DISPOSABLE_ONLY")
        self._dsn = dsn

    def _sql(self, script: str) -> str:
        result = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", self._dsn],
            input=script, text=True, capture_output=True, timeout=20, check=False,
        )
        if result.returncode:
            match = _ERROR.search(result.stderr)
            if not match and "could not serialize access" in result.stderr:
                raise ValueError("DP241_PG_REVISION_CONFLICT")
            if not match and (
                'column "source_provenance_sha" does not exist' in result.stderr
                or 'record "scope_row" has no field "source_provenance_sha"' in result.stderr
            ):
                raise ValueError("DP241_PG_LEGACY_PLAN_UNPINNED")
            raise ValueError(match.group(0) if match else "DP241_PG_QUERY_FAILED")
        return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""

    def install_fixture_schema(self) -> None:
        """Test-only additive tables, safe empty legacy upgrade, never production.

        A populated v1 ledger has no pinned provenance SHA to authenticate,
        so it cannot be backfilled and remains untouched until discarded.
        """
        self._sql(_LEGACY_DISPOSABLE_UPGRADE)
        self._sql(_FIXTURE_SCHEMA)

    @staticmethod
    def _scope(
        plan: RecoveryPlan, target: SourceRecoveryTarget, source_id: str,
    ) -> tuple[str, str]:
        if (
            not isinstance(plan, RecoveryPlan)
            or not isinstance(target, SourceRecoveryTarget)
            or not isinstance(source_id, str)
            or not _KEY.fullmatch(source_id)
            or not target.capture
            or not target.locator.capture_id
            or not target.locator.passage_id
            or not _SHA.fullmatch(plan.target_version_sha256)
            or not _SHA.fullmatch(target.passage.text_sha256)
        ):
            raise ValueError("DP241_PG_SOURCE_INPUT_INVALID")
        # Reconstruct the actual DP-241 plan, source locator and permissions.
        assess_recovery(plan, target, ())
        if plan.status != "READY_PRIVATE_PLAN":
            raise ValueError("DP241_PG_PLAN_NOT_READY")
        if (
            plan.target_content_id != target.locator.content_id
            or target.locator.capture_id != target.capture.id
            or target.locator.passage_id != target.passage.id
            or target.capture.content_sha256 != plan.target_version_sha256
            or target.passage.capture_id != target.capture.id
        ):
            raise ValueError("DP241_PG_SOURCE_INPUT_INVALID")
        fingerprint = _digest({
            "plan": plan.plan_id,
            "content": plan.target_content_id,
            "capture": target.capture.id,
            "passage": target.passage.id,
            "version": plan.target_version_sha256,
            "passage_sha": target.passage.text_sha256,
            "source": source_id,
        })
        return fingerprint, plan.target_version_sha256

    def _guard(self, plan: RecoveryPlan, target: SourceRecoveryTarget, source_id: str) -> str:
        """One PG transaction rechecks authoritative local lineage and latest rights.

        A cleared capture flag is insufficient: a single unrevoked reviewed
        rights leaf must also permit DISCOVER_METADATA and FETCH. Source/rights
        records are never created or given reviewer authority by this adapter.
        """
        t = target
        return """
        IF NOT EXISTS(
            SELECT 1 FROM source s
            JOIN content_item ci ON ci.source_id=s.id
            JOIN content_capture ca ON ca.content_id=ci.id
            JOIN passage pa ON pa.capture_id=ca.id AND pa.content_id=ci.id
            WHERE s.id={source} AND ci.id={content} AND ca.id={capture}
              AND pa.id={passage} AND ca.content_sha256={version}
              AND pa.text_sha256={passage_sha}
              AND pa.selector_type={selector}
              AND pa.start_char={start} AND pa.end_char={end}
              AND ci.rights_status='CLEARED' AND ca.rights_status='CLEARED'
              AND ca.status='CAPTURED' AND ca.hold_status='NONE'
              AND ca.observed_at=(SELECT MAX(observed_at)
                                  FROM content_capture WHERE content_id=ci.id)
              AND NOT EXISTS (SELECT 1 FROM content_capture competing
                    WHERE competing.content_id=ci.id AND competing.id<>ca.id
                      AND competing.observed_at>=ca.observed_at)
              AND (SELECT count(*) FROM private_source_rights_record rr
                    WHERE rr.passage_id=pa.id
                      AND NOT EXISTS (SELECT 1 FROM private_source_rights_record later
                                      WHERE later.supersedes_id=rr.id))=1
              AND EXISTS (
                 SELECT 1 FROM private_source_rights_record rr
                 WHERE rr.passage_id=pa.id AND rr.rights_status='CLEARED'
                   AND rr.content_id=ci.id
                   AND rr.locator_kind='PASSAGE' AND rr.locator_value=pa.id
                   AND rr.reviewed_at IS NOT NULL AND rr.reviewer_ref IS NOT NULL
                   AND rr.rights_receipt_ref IS NOT NULL
                   AND (rr.expires_at IS NULL OR rr.expires_at > now())
                   AND rr.permitted_uses @> ARRAY['DISCOVER_METADATA','FETCH']::text[]
                   AND NOT EXISTS (SELECT 1 FROM private_source_rights_record later
                                   WHERE later.supersedes_id=rr.id)
              )
        ) THEN RAISE EXCEPTION 'DP241_PG_SOURCE_STALE_OR_HELD'; END IF;
        """.format(
            source=_literal(source_id),
            content=_literal(plan.target_content_id),
            capture=_literal(t.capture.id),
            passage=_literal(t.passage.id),
            version=_literal(plan.target_version_sha256),
            passage_sha=_literal(t.passage.text_sha256),
            selector=_literal(t.passage.selector_type),
            start=int(t.passage.start_char),
            end=int(t.passage.end_char),
        )

    @staticmethod
    def _source_provenance_sql(
        plan: RecoveryPlan, target: SourceRecoveryTarget, source_id: str,
    ) -> str:
        """SHA-256 of *database-observed* immutable lineage and rights epoch.

        Store a digest only; pin actual body references and transcript text.
        """
        return """
        (SELECT encode(sha256(convert_to(jsonb_build_array(
             s.id, s.canonical_name, s.source_type, s.canonical_url,
             s.language, s.country_code, s.metadata,
             ci.id, ci.source_id, ci.source_external_id, ci.canonical_url,
             ci.published_at, ci.content_sha256, ci.metadata,
             ca.id, ca.observed_at, ca.final_url, ca.media_type, ca.body_ref,
             ca.content_sha256, ca.retrieval_method, ca.retrieval_version,
             ca.parser_method, ca.parser_version, ca.metadata,
             pa.id, pa.capture_id, pa.selector_type, pa.start_char,
             pa.end_char, pa.page_start, pa.page_end, pa.text_sha256, pa.private_text,
             pa.extraction_method, pa.extraction_version, pa.metadata,
             rr.id, rr.subject_fingerprint, rr.source_family,
             rr.content_id, rr.passage_id, rr.locator_kind, rr.locator_value,
             rr.supersedes_id, rr.policy_version,
             rr.rights_status, rr.rights_receipt_ref, rr.permitted_uses,
             rr.reviewed_at, rr.expires_at, rr.reviewer_ref,
             (SELECT COALESCE(jsonb_agg(jsonb_build_array(
                        version.id, version.observed_at, version.content_sha256,
                        version.final_url, version.retrieval_method,
                        version.retrieval_version, version.rights_status,
                        version.hold_status, version.status, version.metadata
                       ) ORDER BY version.id), '[]'::jsonb)
                FROM content_capture version WHERE version.content_id=ci.id)
        )::text, 'UTF8')), 'hex')
        FROM source s
        JOIN content_item ci ON ci.source_id=s.id
        JOIN content_capture ca ON ca.content_id=ci.id
        JOIN passage pa ON pa.capture_id=ca.id AND pa.content_id=ci.id
        JOIN private_source_rights_record rr ON rr.passage_id=pa.id
        WHERE s.id={source} AND ci.id={content} AND ca.id={capture}
          AND pa.id={passage}
          AND NOT EXISTS(SELECT 1 FROM private_source_rights_record successor
                         WHERE successor.supersedes_id=rr.id)
        )""".format(
            source=_literal(source_id),
            content=_literal(plan.target_content_id),
            capture=_literal(target.capture.id),
            passage=_literal(target.passage.id),
        )

    @staticmethod
    def _snapshot_query(plan_id: str) -> str:
        pid = _literal(plan_id)
        return """
        SELECT json_build_object(
            'revision',p.revision,
            'events',COALESCE((SELECT json_agg(row_to_json(e) ORDER BY e.event_no)
                FROM (SELECT event_no,kind,attempt_id,request_key,result,
                      discovery_sha,spent_usd FROM dp241_pg_event
                      WHERE plan_id=p.plan_id ORDER BY event_no) e),'[]'::json))
            FROM dp241_pg_plan p WHERE p.plan_id={pid};
        """.format(pid=pid)

    def _operation(
        self, action: str, plan: RecoveryPlan, target: SourceRecoveryTarget,
        source_id: str, *, key: str = "", expected_revision: int = 0,
        observed: RecoveryReceipt | None = None,
    ) -> dict:
        fingerprint, _ = self._scope(plan, target, source_id)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("DP241_PG_REVISION_INVALID")
        if action != "REGISTER" and (not _KEY.fullmatch(key)):
            raise ValueError("DP241_PG_KEY_INVALID")
        if action == "COMPLETE":
            if not isinstance(observed, RecoveryReceipt) or observed.candidate is not None:
                raise ValueError("DP241_PG_RECEIPT_UNATTESTED_CANDIDATE")
            if (
                observed.plan_id != plan.plan_id
                or observed.attempt_id not in {m.attempt_id for m in plan.methods}
                or not _SHA.fullmatch(observed.discovery_receipt_sha256)
                or observed.result not in {
                    "NOT_FOUND", "CHECKED_INSUFFICIENT", "OUTAGE",
                    "RIGHTS_BLOCKED", "COST_BLOCKED",
                }
            ):
                raise ValueError("DP241_PG_RECEIPT_INVALID")
        attempt = (
            observed.attempt_id if observed else
            next((m.attempt_id for m in plan.methods if m.attempt_id), "")
        )
        if action == "RESERVE":
            current = self.read(plan, target, source_id=source_id)
            if current.pending_attempt_id is not None:
                attempt = current.pending_attempt_id
            else:
                attempt = current.decision.proposed_attempt_id or ""
            if not attempt:
                raise ValueError("DP241_PG_NO_READY_ATTEMPT")
        attempt_literal = _literal(attempt)
        plan_literal = _literal(plan.plan_id)
        key_literal = _literal(key)
        source_provenance = self._source_provenance_sql(plan, target, source_id)
        if action == "REGISTER":
            mutation = """
                INSERT INTO dp241_pg_plan(
                  plan_id,scope_digest,source_id,content_id,capture_id,passage_id,
                  source_version_sha,passage_sha,source_provenance_sha)
                VALUES ({plan},{digest},{source},{content},{capture},{passage},
                        {version},{passage_sha},{provenance})
                ON CONFLICT(plan_id) DO NOTHING;
                SELECT * INTO scope_row FROM dp241_pg_plan
                  WHERE plan_id={plan} FOR UPDATE;
                IF scope_row.scope_digest <> {digest} THEN
                    RAISE EXCEPTION 'DP241_PG_PLAN_CONFLICT';
                END IF;
                IF scope_row.source_provenance_sha IS DISTINCT FROM {provenance} THEN
                    RAISE EXCEPTION 'DP241_PG_SOURCE_PROVENANCE_STALE';
                END IF;
            """.format(
                plan=plan_literal, digest=_literal(fingerprint),
                source=_literal(source_id),
                content=_literal(plan.target_content_id),
                capture=_literal(target.capture.id),
                passage=_literal(target.passage.id),
                version=_literal(plan.target_version_sha256),
                passage_sha=_literal(target.passage.text_sha256),
                provenance=source_provenance,
            )
        else:
            mutation = """
                SELECT * INTO scope_row FROM dp241_pg_plan
                  WHERE plan_id={plan} FOR UPDATE;
                IF NOT FOUND THEN RAISE EXCEPTION 'DP241_PG_PLAN_NOT_REGISTERED'; END IF;
                IF scope_row.scope_digest <> {digest} THEN
                    RAISE EXCEPTION 'DP241_PG_PLAN_CONFLICT'; END IF;
                IF scope_row.source_provenance_sha IS DISTINCT FROM {provenance} THEN
                    RAISE EXCEPTION 'DP241_PG_SOURCE_PROVENANCE_STALE'; END IF;
                SELECT * INTO prior_row FROM dp241_pg_event
                 WHERE plan_id={plan} AND request_key={key} AND kind={kind};
                IF FOUND THEN
                    IF prior_row.attempt_id <> {attempt} {receipt_conflict} THEN
                        RAISE EXCEPTION 'DP241_PG_REPLAY_CONFLICT'; END IF;
                ELSE
                    {fresh}
                END IF;
            """
            if action == "RESERVE":
                receipt_conflict = ""
                fresh = """
                   IF scope_row.revision <> {rev} THEN
                       RAISE EXCEPTION 'DP241_PG_REVISION_CONFLICT'; END IF;
                   IF EXISTS (SELECT 1 FROM dp241_pg_event e
                      WHERE e.plan_id={plan} AND e.kind='RESERVED'
                      AND NOT EXISTS (SELECT 1 FROM dp241_pg_event done
                         WHERE done.plan_id=e.plan_id AND done.kind='COMPLETED'
                           AND done.attempt_id=e.attempt_id)) THEN
                       RAISE EXCEPTION 'DP241_PG_UNCONFIRMED_RESERVATION'; END IF;
                   INSERT INTO dp241_pg_event(plan_id,event_no,kind,attempt_id,request_key)
                     VALUES({plan},{rev}+1,'RESERVED',{attempt},{key});
                   UPDATE dp241_pg_plan SET revision=revision+1 WHERE plan_id={plan};
                """.format(
                    rev=expected_revision, plan=plan_literal,
                    attempt=attempt_literal, key=key_literal,
                )
            elif action == "COMPLETE":
                receipt_conflict = "OR prior_row.result <> {result} OR prior_row.discovery_sha <> {sha} OR prior_row.spent_usd <> {spent}".format(
                    result=_literal(observed.result),
                    sha=_literal(observed.discovery_receipt_sha256),
                    spent=str(observed.spent_usd),
                )
                fresh = """
                   IF NOT EXISTS(SELECT 1 FROM dp241_pg_event
                       WHERE plan_id={plan} AND kind='RESERVED'
                         AND request_key={key} AND attempt_id={attempt}) THEN
                       RAISE EXCEPTION 'DP241_PG_NOT_RESERVED'; END IF;
                   IF scope_row.revision <> {rev} THEN
                       RAISE EXCEPTION 'DP241_PG_REVISION_CONFLICT'; END IF;
                   INSERT INTO dp241_pg_event(plan_id,event_no,kind,attempt_id,
                     request_key,result,discovery_sha,spent_usd)
                     VALUES({plan},{rev}+1,'COMPLETED',{attempt},{key},
                            {result},{sha},{spent});
                   UPDATE dp241_pg_plan SET revision=revision+1 WHERE plan_id={plan};
                """.format(
                    plan=plan_literal, rev=expected_revision, attempt=attempt_literal,
                    key=key_literal, result=_literal(observed.result),
                    sha=_literal(observed.discovery_receipt_sha256),
                    spent=str(observed.spent_usd),
                )
            else:
                raise ValueError("DP241_PG_OPERATION_INVALID")
            mutation = mutation.format(
                plan=plan_literal, digest=_literal(fingerprint),
                provenance=source_provenance,
                key=key_literal, kind=_literal("RESERVED" if action == "RESERVE" else "COMPLETED"),
                attempt=attempt_literal, receipt_conflict=receipt_conflict, fresh=fresh,
            )
        script = (
            "BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
            + "SELECT pg_advisory_xact_lock(hashtext(" + plan_literal + "));\n"
            + "DO $dp241$ DECLARE scope_row record; prior_row record; BEGIN\n"
            + self._guard(plan, target, source_id) + mutation
            + "END $dp241$;\n" + self._snapshot_query(plan.plan_id) + "\nCOMMIT;"
        )
        # The advisory-lock SELECT has a blank value; only last non-empty line
        # (the JSON snapshot) is parsed, and no raw source text is emitted.
        return json.loads(self._sql(script))

    @staticmethod
    def _history(raw: dict, plan_id: str) -> PgRecoveryHistory:
        if not isinstance(raw, dict) or type(raw.get("revision")) is not int:
            raise ValueError("DP241_PG_HISTORY_CORRUPT")
        events = raw.get("events", [])
        if len(events) != raw["revision"] or len(events) > 16:
            raise ValueError("DP241_PG_HISTORY_CORRUPT")
        reserves = {}
        done = {}
        receipts = []
        for idx, row in enumerate(events, start=1):
            if row["event_no"] != idx or row["attempt_id"] in done:
                raise ValueError("DP241_PG_HISTORY_CORRUPT")
            attempt = row["attempt_id"]
            if row["kind"] == "RESERVED":
                if attempt in reserves:
                    raise ValueError("DP241_PG_HISTORY_CORRUPT")
                reserves[attempt] = row["request_key"]
            elif row["kind"] == "COMPLETED":
                if reserves.get(attempt) != row["request_key"]:
                    raise ValueError("DP241_PG_HISTORY_CORRUPT")
                receipt = RecoveryReceipt(
                    attempt_id=attempt, plan_id=plan_id, result=row["result"],
                    discovery_receipt_sha256=row["discovery_sha"],
                    spent_usd=Decimal(str(row["spent_usd"])),
                )
                receipts.append(receipt)
                done[attempt] = True
            else:
                raise ValueError("DP241_PG_HISTORY_CORRUPT")
        pending = [attempt for attempt in reserves if attempt not in done]
        if len(pending) > 1:
            raise ValueError("DP241_PG_HISTORY_CORRUPT")
        return PgRecoveryHistory(raw["revision"], tuple(receipts),
                                 pending[0] if pending else None)

    def history(self, plan_id: str) -> PgRecoveryHistory:
        if not isinstance(plan_id, str) or not _KEY.fullmatch(plan_id):
            raise ValueError("DP241_PG_PLAN_INVALID")
        raw = self._sql(self._snapshot_query(plan_id))
        if not raw:
            raise ValueError("DP241_PG_PLAN_NOT_REGISTERED")
        return self._history(json.loads(raw), plan_id)

    def _state(
        self, raw: dict, plan: RecoveryPlan, target: SourceRecoveryTarget,
    ) -> PgRecoveryState:
        prior = self._history(raw, plan.plan_id)
        decision = assess_recovery(plan, target, prior.receipts)
        inspect_recovery_timeline(plan, target, prior.receipts)
        if len(prior.receipts) > plan.max_attempts:
            raise ValueError("DP241_PG_ATTEMPT_CAP")
        if prior.pending_attempt_id is not None:
            if prior.pending_attempt_id != decision.proposed_attempt_id:
                raise ValueError("DP241_PG_PENDING_PLAN_CONFLICT")
        return PgRecoveryState(prior.revision, prior.receipts, decision,
                               prior.pending_attempt_id)

    def register(
        self, plan: RecoveryPlan, target: SourceRecoveryTarget, *, source_id: str,
    ) -> PgRecoveryState:
        return self._state(self._operation("REGISTER", plan, target, source_id), plan, target)

    def read(
        self, plan: RecoveryPlan, target: SourceRecoveryTarget, *, source_id: str,
    ) -> PgRecoveryState:
        self._scope(plan, target, source_id)
        # Same read-time DB revalidation as mutation, but never changes a row.
        script = (
            "BEGIN ISOLATION LEVEL SERIALIZABLE;\nDO $dp241$ BEGIN\n" + self._guard(plan, target, source_id)
            + "IF NOT EXISTS (SELECT 1 FROM dp241_pg_plan WHERE plan_id="
            + _literal(plan.plan_id) + " AND source_provenance_sha="
            + self._source_provenance_sql(plan, target, source_id)
            + ") THEN RAISE EXCEPTION 'DP241_PG_SOURCE_PROVENANCE_STALE'; END IF;\n"
            + "END $dp241$;\n" + self._snapshot_query(plan.plan_id) + "\nCOMMIT;"
        )
        raw = self._sql(script)
        if not raw:
            raise ValueError("DP241_PG_PLAN_NOT_REGISTERED")
        return self._state(json.loads(raw), plan, target)

    def reserve(
        self, plan: RecoveryPlan, target: SourceRecoveryTarget, *,
        source_id: str, key: str, expected_revision: int,
    ) -> PgRecoveryState:
        return self._state(
            self._operation("RESERVE", plan, target, source_id,
                            key=key, expected_revision=expected_revision),
            plan, target,
        )

    def complete(
        self, plan: RecoveryPlan, target: SourceRecoveryTarget, *,
        source_id: str, key: str, expected_revision: int,
        observed: RecoveryReceipt,
    ) -> PgRecoveryState:
        if not isinstance(observed, RecoveryReceipt):
            raise ValueError("DP241_PG_RECEIPT_INVALID")
        before = self.read(plan, target, source_id=source_id)
        if before.pending_attempt_id not in {None, observed.attempt_id}:
            raise ValueError("DP241_PG_RECEIPT_ATTEMPT_CONFLICT")
        if observed not in before.receipts:
            assess_recovery(plan, target, (*before.receipts, observed))
        return self._state(
            self._operation("COMPLETE", plan, target, source_id,
                            key=key, expected_revision=expected_revision, observed=observed),
            plan, target,
        )


__all__ = ["IsolatedOriginalRecoveryPg", "PgRecoveryState", "PgRecoveryHistory"]

"""DP-320 isolated PostgreSQL revocation reference (explicit disposable DB only).

The canonical schema has no RevocationEpoch migration. These additional fixture
tables/functions model DB-clock transaction boundaries using actual PostgreSQL
row locks. No production path, authorizer, release channel, or edge serves this.
Every operation opens an independent psql backend; one SQL statement plus its
transaction atomically validates inputs and writes durable rows. Callers must
still bind *all* material predecessors and hold a served-byte/edge fence.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from urllib.parse import urlsplit

from .revocation_epoch_fence import (
    MaterialEpoch,
    PublicationEpochTicket,
    RevocationFenceHeld,
    VERSION,
    _id,
    _sha,
    _ticket_fingerprint,
    _REASONS,
)


# This DDL must only be installed on a disposable PG database, never on the
# actual operational schema. There is deliberately no migration or DB hook.
_FIXTURE_SQL = r"""
BEGIN;
CREATE TABLE IF NOT EXISTS dp320_pg_source (
  source_id text PRIMARY KEY,
  epoch bigint NOT NULL DEFAULT 0 CHECK (epoch >= 0),
  material_sha256 text NOT NULL CHECK (material_sha256 ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK (status IN ('ACTIVE','HELD'))
);
CREATE TABLE IF NOT EXISTS dp320_pg_revocation (
  event_id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES dp320_pg_source(source_id),
  epoch bigint NOT NULL CHECK (epoch > 0),
  reason text NOT NULL,
  material_sha256 text NOT NULL,
  occurred_at timestamptz NOT NULL,
  UNIQUE (source_id, epoch)
);
CREATE TABLE IF NOT EXISTS dp320_pg_outbox (
  event_id text PRIMARY KEY REFERENCES dp320_pg_revocation(event_id),
  source_id text NOT NULL REFERENCES dp320_pg_source(source_id),
  epoch bigint NOT NULL CHECK (epoch > 0),
  UNIQUE (event_id, epoch)
);
CREATE TABLE IF NOT EXISTS dp320_pg_ack (
  event_id text PRIMARY KEY,
  epoch bigint NOT NULL,
  FOREIGN KEY (event_id, epoch) REFERENCES dp320_pg_outbox(event_id, epoch)
);
CREATE TABLE IF NOT EXISTS dp320_pg_publication (
  release_id text PRIMARY KEY,
  artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  fence_sha256 text NOT NULL CHECK (fence_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE OR REPLACE FUNCTION dp320_pg_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'dp320 ledger is append-only';
END $$;
DROP TRIGGER IF EXISTS dp320_revocation_immutable ON dp320_pg_revocation;
CREATE TRIGGER dp320_revocation_immutable BEFORE UPDATE OR DELETE ON dp320_pg_revocation
  FOR EACH ROW EXECUTE FUNCTION dp320_pg_immutable();
DROP TRIGGER IF EXISTS dp320_outbox_immutable ON dp320_pg_outbox;
CREATE TRIGGER dp320_outbox_immutable BEFORE UPDATE OR DELETE ON dp320_pg_outbox
  FOR EACH ROW EXECUTE FUNCTION dp320_pg_immutable();
DROP TRIGGER IF EXISTS dp320_ack_immutable ON dp320_pg_ack;
CREATE TRIGGER dp320_ack_immutable BEFORE UPDATE OR DELETE ON dp320_pg_ack
  FOR EACH ROW EXECUTE FUNCTION dp320_pg_immutable();

-- Called by issuance and guarded publication/reader in the SAME transaction.
-- Every material row is locked in identical sorted order. At READ COMMITTED,
-- a waiter sees the up-to-date row after a competing revocation commits.
CREATE OR REPLACE FUNCTION dp320_pg_lock_ticket(p_dependencies jsonb)
RETURNS void LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  dependency jsonb;
  current_row dp320_pg_source%ROWTYPE;
  current_id text;
  previous_id text := '';
BEGIN
  IF jsonb_typeof(p_dependencies) IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_dependencies) NOT BETWEEN 1 AND 128 THEN
    RAISE EXCEPTION 'FENCE_TICKET_INVALID';
  END IF;
  FOR dependency IN SELECT value FROM jsonb_array_elements(p_dependencies)
                    ORDER BY value->>'dependency_id' LOOP
    current_id := dependency->>'dependency_id';
    IF current_id IS NULL OR current_id <= previous_id THEN
      RAISE EXCEPTION 'FENCE_DUPLICATE_DEPENDENCY';
    END IF;
    previous_id := current_id;
    SELECT * INTO current_row FROM dp320_pg_source
      WHERE source_id=current_id FOR UPDATE;
    IF NOT FOUND OR current_row.status <> 'ACTIVE'
       OR current_row.epoch <> (dependency->>'epoch')::bigint
       OR current_row.material_sha256 <> dependency->>'material_sha256' THEN
      RAISE EXCEPTION 'FENCE_STALE_OR_HELD';
    END IF;
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION dp320_pg_mint(p_ids jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  dep_id text;
  previous_id text := '';
  current_row dp320_pg_source%ROWTYPE;
  receipt jsonb := '[]'::jsonb;
BEGIN
  IF jsonb_typeof(p_ids) IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_ids) NOT BETWEEN 1 AND 128 THEN
    RAISE EXCEPTION 'FENCE_DEPENDENCY_SCOPE_INVALID';
  END IF;
  FOR dep_id IN SELECT value #>> '{}' FROM jsonb_array_elements(p_ids)
                ORDER BY value #>> '{}' LOOP
    IF dep_id IS NULL OR dep_id <= previous_id THEN
      RAISE EXCEPTION 'FENCE_DUPLICATE_DEPENDENCY';
    END IF;
    previous_id := dep_id;
    SELECT * INTO current_row FROM dp320_pg_source
      WHERE source_id=dep_id FOR UPDATE;
    IF NOT FOUND OR current_row.status <> 'ACTIVE' THEN
      RAISE EXCEPTION 'FENCE_STALE_OR_HELD';
    END IF;
    receipt := receipt || jsonb_build_array(jsonb_build_object(
      'dependency_id', dep_id, 'epoch', current_row.epoch,
      'material_sha256', current_row.material_sha256));
  END LOOP;
  RETURN receipt;
END $$;

CREATE OR REPLACE FUNCTION dp320_pg_publish(
  p_release text, p_artifact text, p_fence text, p_dependencies jsonb)
RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  current_row dp320_pg_publication%ROWTYPE;
BEGIN
  PERFORM dp320_pg_lock_ticket(p_dependencies);
  INSERT INTO dp320_pg_publication(release_id, artifact_sha256, fence_sha256)
  VALUES (p_release, p_artifact, p_fence) ON CONFLICT DO NOTHING;
  SELECT * INTO current_row FROM dp320_pg_publication
    WHERE release_id=p_release FOR UPDATE;
  IF NOT FOUND OR current_row.artifact_sha256 <> p_artifact
     OR current_row.fence_sha256 <> p_fence THEN
    RAISE EXCEPTION 'FENCE_RELEASE_ID_CONFLICT';
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION dp320_pg_check(
  p_release text, p_artifact text, p_fence text, p_dependencies jsonb)
RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  current_row dp320_pg_publication%ROWTYPE;
BEGIN
  PERFORM dp320_pg_lock_ticket(p_dependencies);
  SELECT * INTO current_row FROM dp320_pg_publication
    WHERE release_id=p_release FOR UPDATE;
  IF NOT FOUND OR current_row.artifact_sha256 <> p_artifact
     OR current_row.fence_sha256 <> p_fence THEN
    RAISE EXCEPTION 'FENCE_PUBLIC_ARTIFACT_UNMATCHED';
  END IF;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION dp320_pg_revoke(
  p_source text, p_event text, p_reason text, p_time timestamptz)
RETURNS bigint LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  current_row dp320_pg_source%ROWTYPE;
  old_event dp320_pg_revocation%ROWTYPE;
  next_epoch bigint;
BEGIN
  SELECT * INTO current_row FROM dp320_pg_source
    WHERE source_id=p_source FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'FENCE_UNKNOWN_SOURCE';
  END IF;
  SELECT * INTO old_event FROM dp320_pg_revocation WHERE event_id=p_event;
  IF FOUND THEN
    IF old_event.source_id <> p_source OR old_event.reason <> p_reason
       OR old_event.occurred_at <> p_time THEN
      RAISE EXCEPTION 'FENCE_REPLAY_CONFLICT';
    END IF;
    RETURN old_event.epoch;
  END IF;
  next_epoch := current_row.epoch + 1;
  UPDATE dp320_pg_source SET epoch=next_epoch, status='HELD'
    WHERE source_id=p_source;
  INSERT INTO dp320_pg_revocation(event_id,source_id,epoch,reason,material_sha256,occurred_at)
    VALUES(p_event,p_source,next_epoch,p_reason,current_row.material_sha256,p_time);
  INSERT INTO dp320_pg_outbox(event_id,source_id,epoch)
    VALUES(p_event,p_source,next_epoch);
  RETURN next_epoch;
END $$;

CREATE OR REPLACE FUNCTION dp320_pg_acknowledge(p_event text, p_epoch bigint)
RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM dp320_pg_outbox
                  WHERE event_id=p_event AND epoch=p_epoch) THEN
    RAISE EXCEPTION 'FENCE_OUTBOX_ACK_STALE';
  END IF;
  INSERT INTO dp320_pg_ack(event_id,epoch) VALUES(p_event,p_epoch)
    ON CONFLICT (event_id) DO NOTHING;
  RETURN true;
END $$;
COMMIT;
"""

_ERR = re.compile(r"FENCE_[A-Z_]+")


class IsolatedPostgresRevocationFence:
    """Explicit opt-in experimental database, no production/proxy auto-wiring."""

    def __init__(self, database_url: str) -> None:
        try:
            parsed = urlsplit(database_url)
            if (parsed.scheme not in {"postgresql", "postgres"}
                    or parsed.hostname != "127.0.0.1"
                    or not parsed.port
                    or not parsed.path.startswith("/dp320_test_")
                    or "/" in parsed.path[1:]
                    or parsed.query or parsed.fragment or parsed.password):
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise RevocationFenceHeld("FENCE_ISOLATED_DATABASE_REQUIRED") from exc
        self.database_url = database_url
        self.psql = shutil.which("psql")
        if self.psql is None:
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE")

    def _run(self, sql: str, *, variables: dict[str, str] | None = None,
             expect_json: bool = True) -> object:
        arguments = [self.psql, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                     "-d", self.database_url]
        for key, value in (variables or {}).items():
            if not re.fullmatch(r"[a-z_]+", key):
                raise RevocationFenceHeld("FENCE_VARIABLE_INVALID")
            arguments += ["-v", f"{key}={value}"]
        try:
            bounded_sql = ("SET statement_timeout='10000ms'; "
                           "SET lock_timeout='8000ms'; "
                           "SET idle_in_transaction_session_timeout='10000ms';\n" + sql)
            proc = subprocess.run(arguments, input=bounded_sql, capture_output=True,
                                  text=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE") from exc
        if proc.returncode:
            match = _ERR.search(proc.stderr)
            if match:
                raise RevocationFenceHeld(match.group())
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE")
        if not expect_json:
            return None
        try:
            lines = [line for line in proc.stdout.splitlines() if line]
            if len(lines) != 1:
                raise ValueError("unexpected psql output")
            return json.loads(lines[0])
        except (ValueError, TypeError) as exc:
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE") from exc

    def install_fixture_schema(self) -> None:
        """DDL permitted only in the explicit isolated test database."""
        self._run(_FIXTURE_SQL, expect_json=False)

    def register_fixture_source(self, source_id: str, material_sha256: str) -> None:
        """One-time seed. Does NOT restore held rows on retry."""
        self._run("""INSERT INTO dp320_pg_source(source_id,epoch,material_sha256,status)
            VALUES (:'source',0,:'sha','ACTIVE') ON CONFLICT DO NOTHING;""",
                  variables={"source": _id(source_id), "sha": _sha(material_sha256)},
                  expect_json=False)

    @staticmethod
    def _validate_ticket(ticket: PublicationEpochTicket) -> str:
        if (not isinstance(ticket, PublicationEpochTicket)
                or ticket.version != VERSION or not isinstance(ticket.dependencies, tuple)
                or not 1 <= len(ticket.dependencies) <= 128):
            raise RevocationFenceHeld("FENCE_TICKET_INVALID")
        _id(ticket.release_id)
        previous = ""
        for dep in ticket.dependencies:
            if not isinstance(dep, MaterialEpoch):
                raise RevocationFenceHeld("FENCE_TICKET_INVALID")
            dep_id = _id(dep.dependency_id)
            if dep_id <= previous:
                raise RevocationFenceHeld("FENCE_DUPLICATE_DEPENDENCY")
            previous = dep_id
            _sha(dep.material_sha256)
            if type(dep.epoch) is not int or dep.epoch < 0:
                raise RevocationFenceHeld("FENCE_EPOCH_INVALID")
        if ticket.fingerprint != _ticket_fingerprint(ticket.release_id, ticket.dependencies):
            raise RevocationFenceHeld("FENCE_TICKET_TAMPERED")
        return json.dumps([vars(dep) for dep in ticket.dependencies], separators=(",", ":"))

    def mint(self, *, release_id: str, dependency_ids: tuple[str, ...]) -> PublicationEpochTicket:
        _id(release_id)
        if not isinstance(dependency_ids, tuple) or not 1 <= len(dependency_ids) <= 128:
            raise RevocationFenceHeld("FENCE_DEPENDENCY_SCOPE_INVALID")
        ids = sorted(_id(item) for item in dependency_ids)
        if len(set(ids)) != len(ids):
            raise RevocationFenceHeld("FENCE_DUPLICATE_DEPENDENCY")
        rows = self._run("BEGIN; SELECT dp320_pg_mint(:'ids'::jsonb)::text; COMMIT;",
                         variables={"ids": json.dumps(ids)})
        if not isinstance(rows, list) or len(rows) != len(ids):
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE")
        items = tuple(MaterialEpoch(row["dependency_id"], row["epoch"],
                                    row["material_sha256"]) for row in rows)
        result = PublicationEpochTicket(release_id, items, _ticket_fingerprint(release_id, items))
        self._validate_ticket(result)
        return result

    def publish_reference(self, *, ticket: PublicationEpochTicket, artifact_sha256: str) -> None:
        dependencies = self._validate_ticket(ticket)
        self._run("BEGIN; SELECT to_json(dp320_pg_publish(:'release', :'artifact', "
                  ":'fence', :'deps'::jsonb)); COMMIT;",
                  variables={"release": ticket.release_id, "artifact": _sha(artifact_sha256),
                             "fence": ticket.fingerprint, "deps": dependencies})

    def check_served(self, *, ticket: PublicationEpochTicket, artifact_sha256: str) -> bool:
        dependencies = self._validate_ticket(ticket)
        return self._run("BEGIN; SELECT to_json(dp320_pg_check(:'release', :'artifact', "
                         ":'fence', :'deps'::jsonb)); COMMIT;",
                         variables={"release": ticket.release_id, "artifact": _sha(artifact_sha256),
                                    "fence": ticket.fingerprint, "deps": dependencies}) is True

    def revoke(self, *, source_id: str, event_id: str, reason: str,
               occurred_at: str) -> int:
        _id(source_id)
        _id(event_id)
        if reason not in _REASONS:
            raise RevocationFenceHeld("FENCE_REASON_INVALID")
        try:
            parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError
        except (TypeError, ValueError, AttributeError) as exc:
            raise RevocationFenceHeld("FENCE_TIMESTAMP_INVALID") from exc
        result = self._run("BEGIN; SELECT to_json(dp320_pg_revoke(:'source', :'event', "
                           ":'reason', :'stamp'::timestamptz)); COMMIT;",
                           variables={"source": source_id, "event": event_id,
                                      "reason": reason, "stamp": occurred_at})
        if type(result) is not int or result < 1:
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE")
        return result

    def pending_invalidations(self) -> tuple[tuple[str, str, int], ...]:
        rows = self._run("""SELECT coalesce(json_agg(
            json_build_array(o.event_id,o.source_id,o.epoch)
            ORDER BY o.source_id,o.epoch,o.event_id), '[]'::json)
            FROM dp320_pg_outbox o LEFT JOIN dp320_pg_ack a
              ON a.event_id=o.event_id AND a.epoch=o.epoch
            WHERE a.event_id IS NULL;""")
        if not isinstance(rows, list):
            raise RuntimeError("FENCE_POSTGRES_UNAVAILABLE")
        return tuple(tuple(row) for row in rows)

    def acknowledge(self, *, event_id: str, epoch: int) -> None:
        if type(epoch) is not int or epoch < 1:
            raise RevocationFenceHeld("FENCE_EPOCH_INVALID")
        self._run("BEGIN; SELECT to_json(dp320_pg_acknowledge(:'event', :'epoch'::bigint)); "
                  "COMMIT;", variables={"event": _id(event_id), "epoch": str(epoch)})

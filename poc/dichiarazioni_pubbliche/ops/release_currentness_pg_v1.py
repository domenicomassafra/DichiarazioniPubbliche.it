"""DP-518 isolated private PostgreSQL release-currentness/readback reference.

Only against an explicitly disposable dp320_test_* PostgreSQL with the *real*
canonical schema and DP-320 fixture already installed. Source/epoch locks and
the local release-pointer CAS are genuine PostgreSQL transactions, but NONE of
the readbacks proves deployment, trusted owner signatures, a CDN invalidation,
HTTP bytes, a MiniPC ACK or a public-release grant. No production migrations.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass

from dichiarazioni_pubbliche.revocation_epoch_fence import (
    PublicationEpochTicket,
    RevocationFenceHeld,
    _id,
    _sha,
)
from dichiarazioni_pubbliche.revocation_pg_fence_v1 import IsolatedPostgresRevocationFence

_ERROR = re.compile(r"(DP518_[A-Z_]+|FENCE_[A-Z_]+)")

_FIXTURE_SQL = r"""
BEGIN;
DO $check$ BEGIN
  IF current_database() NOT LIKE 'dp320_test_%'
     OR to_regclass('public.dp320_pg_source') IS NULL
     OR to_regclass('public.dp320_pg_revocation') IS NULL
     OR to_regclass('public.dp320_pg_outbox') IS NULL
     OR to_regclass('public.dp320_pg_ack') IS NULL
     OR to_regclass('public.dp320_pg_publication') IS NULL
  THEN RAISE EXCEPTION 'DP518_CANONICAL_FENCE_REQUIRED'; END IF;
END $check$;
CREATE TABLE IF NOT EXISTS dp518_pg_release (
  release_id text PRIMARY KEY REFERENCES dp320_pg_publication(release_id),
  artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  projection_sha256 text NOT NULL CHECK (projection_sha256 ~ '^[0-9a-f]{64}$'),
  index_sha256 text NOT NULL CHECK (index_sha256 ~ '^[0-9a-f]{64}$'),
  generation_sha256 text NOT NULL CHECK (generation_sha256 ~ '^[0-9a-f]{64}$'),
  fence_sha256 text NOT NULL CHECK (fence_sha256 ~ '^[0-9a-f]{64}$'),
  dependencies jsonb NOT NULL CHECK (jsonb_typeof(dependencies)='array')
);
CREATE TABLE IF NOT EXISTS dp518_pg_current (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  revision bigint NOT NULL CHECK (revision >= 0),
  release_id text REFERENCES dp518_pg_release(release_id),
  CHECK ((revision = 0) = (release_id IS NULL))
);
INSERT INTO dp518_pg_current(singleton,revision,release_id)
 VALUES(true,0,NULL) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS dp518_pg_selection (
  event_id text PRIMARY KEY,
  revision bigint NOT NULL UNIQUE CHECK(revision > 0),
  expected_revision bigint NOT NULL CHECK(expected_revision >= 0),
  release_id text NOT NULL REFERENCES dp518_pg_release(release_id),
  projection_sha256 text NOT NULL,
  index_sha256 text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE OR REPLACE FUNCTION dp518_pg_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'dp518 append-only private receipt'; END $$;
DROP TRIGGER IF EXISTS dp518_release_immutable ON dp518_pg_release;
CREATE TRIGGER dp518_release_immutable BEFORE UPDATE OR DELETE ON dp518_pg_release
 FOR EACH ROW EXECUTE FUNCTION dp518_pg_immutable();
DROP TRIGGER IF EXISTS dp518_selection_immutable ON dp518_pg_selection;
CREATE TRIGGER dp518_selection_immutable BEFORE UPDATE OR DELETE ON dp518_pg_selection
 FOR EACH ROW EXECUTE FUNCTION dp518_pg_immutable();
DROP TRIGGER IF EXISTS dp518_current_no_delete ON dp518_pg_current;
CREATE TRIGGER dp518_current_no_delete BEFORE DELETE ON dp518_pg_current
 FOR EACH ROW EXECUTE FUNCTION dp518_pg_immutable();

-- Exactly every immutable revocation must have its corresponding outbox
-- identity/epoch/source. An ACK is *only* a fixture DB event, not a CDN proof.
CREATE OR REPLACE FUNCTION dp518_pg_outbox_valid() RETURNS boolean
LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(
   SELECT 1 FROM dp320_pg_revocation r
   FULL JOIN dp320_pg_outbox o ON o.event_id=r.event_id
   WHERE r.event_id IS NULL OR o.event_id IS NULL
      OR r.epoch <> o.epoch OR r.source_id <> o.source_id
 ) AND NOT EXISTS(
   SELECT 1 FROM dp320_pg_revocation r
   LEFT JOIN dp320_pg_source s ON s.source_id=r.source_id
   WHERE s.source_id IS NULL OR s.epoch < r.epoch
 ) AND NOT EXISTS(
   SELECT 1 FROM dp320_pg_ack a
   LEFT JOIN dp320_pg_outbox o ON o.event_id=a.event_id
   WHERE o.event_id IS NULL OR o.epoch<>a.epoch
 );
$$;
CREATE OR REPLACE FUNCTION dp518_pg_unacked() RETURNS integer
LANGUAGE sql STABLE AS $$
 SELECT count(*)::integer FROM dp320_pg_outbox o
 LEFT JOIN dp320_pg_ack a ON a.event_id=o.event_id AND a.epoch=o.epoch
 WHERE a.event_id IS NULL;
$$;

-- A private selection receipt, NOT public publication permission.
-- Serialized with DP320 revocation by exactly its sorted source-row locks.
CREATE OR REPLACE FUNCTION dp518_pg_select(
  p_release text, p_artifact text, p_fence text, p_deps jsonb,
  p_projection text, p_index text, p_generation text,
  p_event text, p_expected bigint
) RETURNS jsonb LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  old_release dp518_pg_release%ROWTYPE;
  current_row dp518_pg_current%ROWTYPE;
  previous dp518_pg_selection%ROWTYPE;
BEGIN
  IF current_database() NOT LIKE 'dp320_test_%'
  THEN RAISE EXCEPTION 'DP518_DISPOSABLE_DATABASE_REQUIRED'; END IF;
  -- Must match DP320's exact *already recorded* release and source epochs.
  PERFORM dp320_pg_check(p_release,p_artifact,p_fence,p_deps);
  IF NOT dp518_pg_outbox_valid()
    THEN RAISE EXCEPTION 'DP518_OUTBOX_INTEGRITY_FAILURE'; END IF;
  IF dp518_pg_unacked() <> 0
    THEN RAISE EXCEPTION 'DP518_OUTBOX_PENDING'; END IF;
  INSERT INTO dp518_pg_release(
    release_id,artifact_sha256,projection_sha256,index_sha256,
    generation_sha256,fence_sha256,dependencies
  ) VALUES(p_release,p_artifact,p_projection,p_index,p_generation,p_fence,p_deps)
    ON CONFLICT DO NOTHING;
  SELECT * INTO old_release FROM dp518_pg_release
    WHERE release_id=p_release FOR SHARE;
  IF NOT FOUND OR old_release.artifact_sha256<>p_artifact
    OR old_release.projection_sha256<>p_projection
    OR old_release.index_sha256<>p_index
    OR old_release.generation_sha256<>p_generation
    OR old_release.fence_sha256<>p_fence
    OR old_release.dependencies<>p_deps THEN
    RAISE EXCEPTION 'DP518_RELEASE_ID_CONFLICT';
  END IF;
  SELECT * INTO current_row FROM dp518_pg_current
    WHERE singleton=true FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'DP518_POINTER_MISSING'; END IF;
  -- A reset/rollback of the mutable pointer must not hide a later immutable
  -- selection receipt. This is independent of the caller's expected CAS.
  IF current_row.revision<>(SELECT count(*) FROM dp518_pg_selection)
     OR current_row.revision<>coalesce(
       (SELECT max(revision) FROM dp518_pg_selection),0) THEN
    RAISE EXCEPTION 'DP518_POINTER_HISTORY_DRIFT';
  END IF;
  SELECT * INTO previous FROM dp518_pg_selection WHERE event_id=p_event;
  IF FOUND THEN
    IF previous.release_id<>p_release
       OR previous.expected_revision<>p_expected
       OR previous.projection_sha256<>p_projection
       OR previous.index_sha256<>p_index THEN
      RAISE EXCEPTION 'DP518_SELECTION_REPLAY_CONFLICT';
    END IF;
    IF current_row.release_id IS DISTINCT FROM previous.release_id
       OR current_row.revision<>previous.revision THEN
      RAISE EXCEPTION 'DP518_SELECTION_REPLAY_STALE';
    END IF;
    RETURN jsonb_build_object('revision',previous.revision,
      'private_reference_recorded',true,'publication_authorized',false);
  END IF;
  IF current_row.revision<>p_expected THEN
    RAISE EXCEPTION 'DP518_REVISION_CONFLICT';
  END IF;
  INSERT INTO dp518_pg_selection(
    event_id,revision,expected_revision,release_id,
    projection_sha256,index_sha256
  ) VALUES(p_event,p_expected+1,p_expected,p_release,p_projection,p_index);
  UPDATE dp518_pg_current SET revision=p_expected+1,release_id=p_release
    WHERE singleton=true AND revision=p_expected;
  IF NOT FOUND THEN RAISE EXCEPTION 'DP518_REVISION_CONFLICT'; END IF;
  RETURN jsonb_build_object('revision',p_expected+1,
    'private_reference_recorded',true,'publication_authorized',false);
END $$;

-- Protected readback of a *private* exact release reference. It never returns
-- public current=true. DP320 row locks linearize dependency checks with revoke.
CREATE OR REPLACE FUNCTION dp518_pg_probe(
  p_release text, p_index text, p_projection text, p_expected bigint
) RETURNS jsonb LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  manifest dp518_pg_release%ROWTYPE;
  pointer dp518_pg_current%ROWTYPE;
  selection dp518_pg_selection%ROWTYPE;
  reason_code text := 'PRIVATE_ONLY_NOT_DEPLOYED';
  pending_count integer;
  revocation_count integer;
  ack_count integer;
  source_stamp text;
BEGIN
  IF current_database() NOT LIKE 'dp320_test_%'
    THEN RAISE EXCEPTION 'DP518_DISPOSABLE_DATABASE_REQUIRED'; END IF;
  SELECT * INTO manifest FROM dp518_pg_release WHERE release_id=p_release;
  IF NOT FOUND THEN
    reason_code := 'NO_REFERENCE';
  ELSIF manifest.index_sha256<>p_index
    OR manifest.projection_sha256<>p_projection THEN
    reason_code := 'RELEASE_VERSION_MISMATCH';
  ELSE
    -- This PostgreSQL check does NOT fence any later HTTP/edge response.
    BEGIN
      PERFORM dp320_pg_check(manifest.release_id,manifest.artifact_sha256,
                             manifest.fence_sha256,manifest.dependencies);
    EXCEPTION WHEN OTHERS THEN
      IF reason_code='PRIVATE_ONLY_NOT_DEPLOYED'
        THEN reason_code := 'DEPENDENCY_STALE_OR_HELD'; END IF;
    END;
  END IF;
  SELECT * INTO pointer FROM dp518_pg_current
    WHERE singleton=true FOR UPDATE;
  IF NOT FOUND THEN
    reason_code := 'POINTER_MISSING';
  ELSIF pointer.revision<>p_expected
    OR pointer.release_id IS DISTINCT FROM p_release THEN
    IF reason_code='PRIVATE_ONLY_NOT_DEPLOYED'
      THEN reason_code := 'RELEASE_VERSION_MISMATCH'; END IF;
  ELSIF reason_code='PRIVATE_ONLY_NOT_DEPLOYED' THEN
    SELECT * INTO selection FROM dp518_pg_selection
      WHERE revision=pointer.revision;
    IF NOT FOUND OR selection.release_id<>pointer.release_id
       OR selection.index_sha256<>manifest.index_sha256
       OR selection.projection_sha256<>manifest.projection_sha256
       OR pointer.revision<>(SELECT count(*) FROM dp518_pg_selection)
       OR pointer.revision<>coalesce(
         (SELECT max(revision) FROM dp518_pg_selection),0) THEN
      reason_code := 'SELECTION_INTEGRITY_FAILURE';
    END IF;
  END IF;
  -- Re-read event/outbox/ACK and epochs only AFTER waiting on DP320's
  -- source locks. A revoke that committed while this probe was blocked must
  -- appear in the returned private version/counters, not the pre-wait state.
  SELECT count(*) INTO revocation_count FROM dp320_pg_revocation;
  SELECT count(*) INTO ack_count FROM dp320_pg_ack;
  SELECT dp518_pg_unacked() INTO pending_count;
  SELECT coalesce(jsonb_agg(jsonb_build_array(
     s.source_id,s.epoch,s.material_sha256,s.status
   ) ORDER BY s.source_id)::text,'[]')
    INTO source_stamp FROM dp320_pg_source s;
  IF NOT dp518_pg_outbox_valid() THEN
    reason_code := 'OUTBOX_INTEGRITY_FAILURE';
  ELSIF pending_count > 0 AND reason_code='PRIVATE_ONLY_NOT_DEPLOYED' THEN
    reason_code := 'OUTBOX_PENDING';
  END IF;
  RETURN jsonb_build_object(
    'status',CASE WHEN reason_code='PRIVATE_ONLY_NOT_DEPLOYED'
      THEN 'COHERENT_PRIVATE_REFERENCE' ELSE 'HELD' END,
    'reason',reason_code,
    'pointer_revision',coalesce(pointer.revision,-1),
    'pointer_release',pointer.release_id,
    'source_stamp',source_stamp,
    'revocation_events',revocation_count,
    'pending_invalidations',pending_count,
    'acknowledgements',ack_count,
    'index_hash',manifest.index_sha256,
    'projection_hash',manifest.projection_sha256,
    'generation_hash',manifest.generation_sha256,
    'publication_authorized',false,'host_ack_verified',false,
    'cdn_ack_verified',false
  );
END $$;
COMMIT;
"""


@dataclass(frozen=True)
class PrivateReleaseCurrentness:
    status: str
    reason: str
    opaque_version: str
    revocation_events: int
    pending_invalidations: int
    acknowledgements: int
    publication_authorized: bool = False
    host_ack_verified: bool = False
    cdn_ack_verified: bool = False


class DisposableReleaseCurrentnessPg:
    """Local opt-in fixture, not an operational release-signing service."""

    def __init__(self, dsn: str):
        self._fence = IsolatedPostgresRevocationFence(dsn)
        self.dsn = dsn

    def _run(self, sql: str, **variables: str) -> object:
        args = [self._fence.psql, "-X", "-q", "-A", "-t",
                "-v", "ON_ERROR_STOP=1", "-d", self.dsn]
        for key, value in variables.items():
            if not re.fullmatch(r"[a-z_]+", key):
                raise RevocationFenceHeld("DP518_VARIABLE_INVALID")
            args += ["-v", f"{key}={value}"]
        payload = ("SET statement_timeout='10000ms'; SET lock_timeout='8000ms'; "
                   "SET idle_in_transaction_session_timeout='10000ms';\n" + sql)
        try:
            proc = subprocess.run(args, input=payload, text=True,
                                  capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("DP518_PG_UNAVAILABLE") from exc
        if proc.returncode:
            match = _ERROR.search(proc.stderr)
            if match:
                raise RevocationFenceHeld(match.group()) from None
            raise RuntimeError("DP518_PG_UNAVAILABLE")
        values = [line for line in proc.stdout.splitlines() if line]
        if not values:
            return None
        if len(values) != 1:
            raise RuntimeError("DP518_RESPONSE_INVALID")
        try:
            return json.loads(values[0])
        except (ValueError, TypeError) as exc:
            raise RuntimeError("DP518_RESPONSE_INVALID") from exc

    def install_disposable_schema(self) -> None:
        self._run(_FIXTURE_SQL)

    def select_private_reference(
        self, *, ticket: PublicationEpochTicket, artifact_sha256: str,
        projection_sha256: str, index_sha256: str,
        generation_sha256: str, event_id: str, expected_revision: int,
    ) -> dict[str, object]:
        deps = self._fence._validate_ticket(ticket)
        _id(event_id)
        for item in (artifact_sha256, projection_sha256,
                     index_sha256, generation_sha256):
            _sha(item)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2**31:
            raise RevocationFenceHeld("DP518_REVISION_INVALID")
        received = self._run(
            "BEGIN; SELECT dp518_pg_select(:'release',:'artifact',:'fence',"
            " :'deps'::jsonb,:'projection',:'index',:'generation',"
            " :'event',:'revision'::bigint)::text; COMMIT;",
            release=ticket.release_id, artifact=artifact_sha256,
            fence=ticket.fingerprint, deps=deps, projection=projection_sha256,
            index=index_sha256, generation=generation_sha256,
            event=event_id, revision=str(expected_revision),
        )
        if not isinstance(received, dict) or received.get("publication_authorized") is not False:
            raise RuntimeError("DP518_RESPONSE_UNSAFE")
        return received

    def read_private_reference(
        self, *, release_id: str, index_sha256: str,
        projection_sha256: str, expected_revision: int,
    ) -> PrivateReleaseCurrentness:
        _id(release_id)
        _sha(index_sha256)
        _sha(projection_sha256)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2**31:
            raise RevocationFenceHeld("DP518_REVISION_INVALID")
        received = self._run(
            "BEGIN; SELECT dp518_pg_probe(:'release',:'index',:'projection',"
            " :'revision'::bigint)::text; COMMIT;",
            release=release_id, index=index_sha256,
            projection=projection_sha256, revision=str(expected_revision),
        )
        if not isinstance(received, dict) or any(
            received.get(key) is not False
            for key in ("publication_authorized", "host_ack_verified", "cdn_ack_verified")
        ):
            raise RuntimeError("DP518_RESPONSE_UNSAFE")
        status = received.get("status")
        reason = received.get("reason")
        if status not in {"HELD", "COHERENT_PRIVATE_REFERENCE"} or not isinstance(reason, str):
            raise RuntimeError("DP518_RESPONSE_UNSAFE")
        # Opaque source/version token, private only and NOT an attestation,
        # signature, CDN ETag or credential. Changes on epoch/outbox/ACK/pin.
        fingerprint = hashlib.sha256(
            json.dumps(received, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return PrivateReleaseCurrentness(
            status=status, reason=reason, opaque_version=fingerprint,
            revocation_events=int(received["revocation_events"]),
            pending_invalidations=int(received["pending_invalidations"]),
            acknowledgements=int(received["acknowledgements"]),
        )


__all__ = ["DisposableReleaseCurrentnessPg", "PrivateReleaseCurrentness"]

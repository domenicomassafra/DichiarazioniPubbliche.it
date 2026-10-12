-- DP-419: private, immutable metadata attestation for one specific captured
-- representation and one current canonical Content transcript segment.
-- It records an OPERATOR CLAIM of provenance, NOT capture-derived proof,
-- independently licensed media, attribution, publication or seek permission.
-- Additive; no edits to pre-existing canonical tables or public APIs.
BEGIN;

CREATE TABLE IF NOT EXISTS media_capture_segment_binding (
    id text PRIMARY KEY,
    content_id text NOT NULL REFERENCES content_item(id) ON DELETE RESTRICT,
    capture_id text NOT NULL,
    capture_sha256 text NOT NULL,
    canonical_segment_id text NOT NULL,
    segment_index integer NOT NULL,
    start_ms bigint NOT NULL,
    end_ms bigint NOT NULL,
    canonical_text_sha256 text NOT NULL,
    evidence_sha256 text NOT NULL,
    attestor_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    UNIQUE (capture_id, canonical_segment_id),
    FOREIGN KEY (capture_id, content_id)
      REFERENCES content_capture(id, content_id) ON DELETE RESTRICT,
    FOREIGN KEY (canonical_segment_id, content_id)
      REFERENCES canonical_transcript_segment(id, content_id) ON DELETE RESTRICT,
    CONSTRAINT media_capture_segment_binding_id_valid
      CHECK (id ~ '^[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}$'),
    CONSTRAINT media_capture_segment_binding_capture_hash_valid
      CHECK (capture_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT media_capture_segment_binding_evidence_hash_valid
      CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT media_capture_segment_binding_text_hash_valid
      CHECK (canonical_text_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT media_capture_segment_binding_range_valid
      CHECK (segment_index >= 0 AND start_ms >= 0 AND end_ms > start_ms),
    CONSTRAINT media_capture_segment_binding_attestor_valid
      CHECK (attestor_ref ~ '^[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}$')
);
COMMENT ON TABLE media_capture_segment_binding IS
  'DP419 private operator-attested Capture SHA to canonical Segment interval; never rights, seek, approval or playback authority';

-- Even direct SQL INSERTs cannot fabricate a cross-Content link, a different
-- capture digest, a shifted canonical range, or an active revoked source.
-- This defends the invariant independently of the Python/CAS entrypoint.
CREATE OR REPLACE FUNCTION validate_media_capture_segment_insert()
RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE
  cap content_capture%ROWTYPE;
  segment canonical_transcript_segment%ROWTYPE;
  content content_item%ROWTYPE;
BEGIN
  SELECT * INTO content FROM content_item WHERE id=NEW.content_id FOR SHARE;
  SELECT * INTO cap FROM content_capture
    WHERE id=NEW.capture_id AND content_id=NEW.content_id FOR SHARE;
  SELECT * INTO segment FROM canonical_transcript_segment
    WHERE id=NEW.canonical_segment_id AND content_id=NEW.content_id FOR SHARE;
  IF content.id IS NULL OR cap.id IS NULL OR segment.id IS NULL
     OR cap.content_sha256 <> NEW.capture_sha256
     OR segment.segment_index <> NEW.segment_index
     OR segment.start_ms <> NEW.start_ms OR segment.end_ms <> NEW.end_ms
     OR content.duration_ms IS NULL OR content.duration_ms < NEW.end_ms
  THEN
    RAISE EXCEPTION 'BINDING_SOURCE_MISMATCH' USING ERRCODE='P0001';
  END IF;
  IF cap.status <> 'CAPTURED' OR cap.hold_status <> 'NONE'
      OR cap.body_purged_at IS NOT NULL
      OR cap.rights_status IN ('REVOKED','DENIED','EXPIRED')
      OR content.rights_status IN ('REVOKED','DENIED','EXPIRED')
      OR segment.transcript_status <> 'RESOLVED' OR segment.publication_blocked
  THEN
    RAISE EXCEPTION 'BINDING_SOURCE_HELD' USING ERRCODE='P0001';
  END IF;
  -- A transcript rewrite with unchanged identity/time must invalidate old
  -- evidence; persist ONLY a digest, never its sensitive canonical text.
  IF NEW.canonical_text_sha256 IS NOT NULL
     AND NEW.canonical_text_sha256 <> encode(
       sha256(convert_to(segment.canonical_text,'UTF8')),'hex')
  THEN
    RAISE EXCEPTION 'BINDING_SOURCE_MISMATCH' USING ERRCODE='P0001';
  END IF;
  NEW.canonical_text_sha256 := encode(
    sha256(convert_to(segment.canonical_text,'UTF8')),'hex');
  RETURN NEW;
END;
$body$;
DROP TRIGGER IF EXISTS media_capture_segment_binding_validate_insert ON media_capture_segment_binding;
CREATE TRIGGER media_capture_segment_binding_validate_insert
BEFORE INSERT ON media_capture_segment_binding
FOR EACH ROW EXECUTE FUNCTION validate_media_capture_segment_insert();

CREATE TABLE IF NOT EXISTS media_capture_segment_binding_event (
    event_id text PRIMARY KEY,
    binding_id text NOT NULL REFERENCES media_capture_segment_binding(id) ON DELETE RESTRICT,
    revision integer NOT NULL CHECK (revision > 0),
    event_kind text NOT NULL CHECK (event_kind IN ('ATTEST', 'HOLD', 'REVOKE')),
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    UNIQUE (binding_id, revision),
    CHECK (event_id ~ '^[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}$')
);
CREATE INDEX IF NOT EXISTS media_capture_segment_binding_event_history_idx
  ON media_capture_segment_binding_event(binding_id, revision DESC);

-- Enforce event sequence even when a privileged writer bypasses the Python
-- function: append-only revision 1 is ATTEST; later revisions only HOLD/REVOKE,
-- and REVOKE is final. Binding row lock serializes direct concurrent inserts.
CREATE OR REPLACE FUNCTION validate_media_capture_segment_event_insert()
RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE
  previous_revision integer := 0;
  previous_action text;
BEGIN
  PERFORM 1 FROM media_capture_segment_binding
    WHERE id=NEW.binding_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'BINDING_NOT_FOUND' USING ERRCODE='P0001';
  END IF;
  SELECT revision, event_kind INTO previous_revision,previous_action
    FROM media_capture_segment_binding_event
    WHERE binding_id=NEW.binding_id ORDER BY revision DESC LIMIT 1;
  IF NOT FOUND THEN previous_revision := 0; END IF;
  IF NEW.revision <> previous_revision+1 OR
     (previous_revision=0 AND NEW.event_kind <> 'ATTEST') OR
     (previous_revision>0 AND NEW.event_kind='ATTEST') OR
     previous_action='REVOKE' THEN
    RAISE EXCEPTION 'BINDING_CAS_CONFLICT' USING ERRCODE='P0001';
  END IF;
  RETURN NEW;
END;
$body$;
DROP TRIGGER IF EXISTS media_capture_segment_binding_event_validate_insert
  ON media_capture_segment_binding_event;
CREATE TRIGGER media_capture_segment_binding_event_validate_insert
BEFORE INSERT ON media_capture_segment_binding_event
FOR EACH ROW EXECUTE FUNCTION validate_media_capture_segment_event_insert();

CREATE OR REPLACE FUNCTION media_capture_segment_immutable()
RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
  RAISE EXCEPTION 'BINDING_IMMUTABLE' USING ERRCODE = 'P0001';
END;
$body$;

DROP TRIGGER IF EXISTS media_capture_segment_binding_immutable ON media_capture_segment_binding;
CREATE TRIGGER media_capture_segment_binding_immutable
BEFORE UPDATE OR DELETE ON media_capture_segment_binding
FOR EACH ROW EXECUTE FUNCTION media_capture_segment_immutable();
DROP TRIGGER IF EXISTS media_capture_segment_binding_event_immutable ON media_capture_segment_binding_event;
CREATE TRIGGER media_capture_segment_binding_event_immutable
BEFORE UPDATE OR DELETE ON media_capture_segment_binding_event
FOR EACH ROW EXECUTE FUNCTION media_capture_segment_immutable();

-- The current hold decisions are computed afresh on every read; historical
-- claims never become a rights/seek license, even if CAPTURE rights = CLEARED.
CREATE OR REPLACE FUNCTION inspect_media_capture_segment_binding(p_binding_id text)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $body$
DECLARE
  b media_capture_segment_binding%ROWTYPE;
  e media_capture_segment_binding_event%ROWTYPE;
  reasons text[] := ARRAY['RIGHTS_NOT_INDEPENDENTLY_APPROVED']::text[];
  capture_row content_capture%ROWTYPE;
  segment_row canonical_transcript_segment%ROWTYPE;
  content_row content_item%ROWTYPE;
BEGIN
  SELECT * INTO b FROM media_capture_segment_binding WHERE id = p_binding_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'BINDING_NOT_FOUND' USING ERRCODE = 'P0001'; END IF;
  SELECT * INTO e FROM media_capture_segment_binding_event
    WHERE binding_id = p_binding_id ORDER BY revision DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'BINDING_EVENT_MISSING' USING ERRCODE = 'P0001'; END IF;
  SELECT * INTO capture_row FROM content_capture WHERE id = b.capture_id AND content_id = b.content_id;
  SELECT * INTO segment_row FROM canonical_transcript_segment
    WHERE id = b.canonical_segment_id AND content_id = b.content_id;
  SELECT * INTO content_row FROM content_item WHERE id = b.content_id;
  IF e.event_kind = 'REVOKE' THEN
    reasons := array_append(reasons, 'BINDING_REVOKED');
  ELSIF e.event_kind = 'HOLD' THEN
    reasons := array_append(reasons, 'BINDING_HELD');
  END IF;
  IF capture_row.id IS NULL OR capture_row.content_sha256 IS DISTINCT FROM b.capture_sha256 THEN
    reasons := array_append(reasons, 'CAPTURE_VERSION_CHANGED');
  END IF;
  IF capture_row.status IS DISTINCT FROM 'CAPTURED'
      OR capture_row.body_purged_at IS NOT NULL THEN
    reasons := array_append(reasons, 'CAPTURE_NOT_AVAILABLE');
  END IF;
  IF capture_row.hold_status IS DISTINCT FROM 'NONE' THEN
    reasons := array_append(reasons, 'CAPTURE_ON_HOLD');
  END IF;
  IF capture_row.retention_class IS DISTINCT FROM 'DURABLE_PRIVATE'
      AND capture_row.retention_class IS DISTINCT FROM 'DURABLE_PROVENANCE' THEN
    reasons := array_append(reasons, 'CAPTURE_RETENTION_UNVERIFIED');
  END IF;
  IF capture_row.rights_status IN ('REVOKED', 'DENIED', 'EXPIRED') THEN
    reasons := array_append(reasons, 'CAPTURE_RIGHTS_REVOKED');
  ELSIF capture_row.rights_status IS DISTINCT FROM 'CLEARED' THEN
    reasons := array_append(reasons, 'CAPTURE_RIGHTS_UNKNOWN');
  END IF;
  IF content_row.rights_status IN ('REVOKED', 'DENIED', 'EXPIRED') THEN
    reasons := array_append(reasons, 'CONTENT_RIGHTS_REVOKED');
  ELSIF content_row.rights_status IS DISTINCT FROM 'CLEARED' THEN
    reasons := array_append(reasons, 'CONTENT_RIGHTS_UNKNOWN');
  END IF;
  IF segment_row.id IS NULL OR segment_row.segment_index IS DISTINCT FROM b.segment_index
      OR segment_row.start_ms IS DISTINCT FROM b.start_ms
      OR segment_row.end_ms IS DISTINCT FROM b.end_ms
      OR encode(sha256(convert_to(segment_row.canonical_text,'UTF8')),'hex')
        IS DISTINCT FROM b.canonical_text_sha256 THEN
    reasons := array_append(reasons, 'SEGMENT_VERSION_CHANGED');
  END IF;
  IF segment_row.transcript_status IS DISTINCT FROM 'RESOLVED'
      OR segment_row.publication_blocked IS DISTINCT FROM false THEN
    reasons := array_append(reasons, 'SEGMENT_ON_HOLD');
  END IF;
  IF content_row.duration_ms IS NULL OR content_row.duration_ms < b.end_ms THEN
    reasons := array_append(reasons, 'DURATION_UNVERIFIED');
  END IF;
  RETURN jsonb_build_object(
    'contract_version', 'studio-capture-segment-binding-pg-v1',
    'private_only', true, 'publication_authority', false,
    'rights_clearance', false, 'seek_authorized', false,
    'capture_segment_binding', 'OPERATOR_ATTESTED_METADATA_ONLY',
    'binding_id', b.id, 'content_id', b.content_id,
    'capture_id', b.capture_id, 'capture_sha256', b.capture_sha256,
    'canonical_segment_id', b.canonical_segment_id,
    'segment_index', b.segment_index, 'start_ms', b.start_ms, 'end_ms', b.end_ms,
    'revision', e.revision,
    'binding_state', CASE WHEN e.event_kind = 'ATTEST' THEN 'ATTESTED'
      WHEN e.event_kind = 'REVOKE' THEN 'REVOKED' ELSE 'HELD' END,
    'hold_reasons', to_jsonb(reasons)
  );
END;
$body$;

-- Single-statement, transaction-scoped advisory lock serializes the CAS key.
-- A duplicate event ID replays only with its ORIGINAL entire request digest.
-- No independent provenance evidence is inferred from equal Content IDs.
CREATE OR REPLACE FUNCTION record_media_capture_segment_binding(
  p_binding_id text, p_event_id text, p_expected_revision integer, p_action text,
  p_content_id text, p_capture_id text, p_capture_sha256 text,
  p_segment_id text, p_start_ms bigint, p_end_ms bigint,
  p_evidence_sha256 text, p_attestor_ref text
) RETURNS jsonb LANGUAGE plpgsql VOLATILE AS $body$
DECLARE
  v_request_sha text;
  v_prev media_capture_segment_binding_event%ROWTYPE;
  v_existing media_capture_segment_binding%ROWTYPE;
  v_revision integer;
  v_latest_kind text;
  v_capture content_capture%ROWTYPE;
  v_segment canonical_transcript_segment%ROWTYPE;
  v_content content_item%ROWTYPE;
BEGIN
  IF p_binding_id IS NULL OR p_binding_id !~ '^[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}$'
    OR p_event_id IS NULL OR p_event_id !~ '^[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}$'
    OR p_attestor_ref IS NULL OR p_attestor_ref !~ '^[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}$'
    OR p_content_id IS NULL OR p_capture_id IS NULL OR p_segment_id IS NULL
    OR p_capture_sha256 IS NULL OR p_capture_sha256 !~ '^[0-9a-f]{64}$'
    OR p_evidence_sha256 IS NULL OR p_evidence_sha256 !~ '^[0-9a-f]{64}$'
    OR p_expected_revision IS NULL OR p_expected_revision < 0
    OR p_action IS NULL OR p_action NOT IN ('ATTEST','HOLD','REVOKE')
    OR p_start_ms IS NULL OR p_start_ms < 0
    OR p_end_ms IS NULL OR p_end_ms <= p_start_ms
  THEN
    RAISE EXCEPTION 'BINDING_INPUT_INVALID' USING ERRCODE = 'P0001';
  END IF;
  v_request_sha := encode(sha256(convert_to(jsonb_build_array(
    p_binding_id,p_event_id,p_expected_revision,p_action,p_content_id,
    p_capture_id,p_capture_sha256,p_segment_id,p_start_ms,p_end_ms,
    p_evidence_sha256,p_attestor_ref
  )::text,'UTF8')),'hex');
  PERFORM pg_advisory_xact_lock(hashtextextended(p_binding_id, 419));
  -- Separate binding IDs competing for the SAME Capture/Segment must also
  -- serialize, producing a stable subject conflict instead of unique_violation.
  PERFORM pg_advisory_xact_lock(hashtextextended(
    p_capture_id || chr(31) || p_segment_id, 420));
  SELECT * INTO v_prev FROM media_capture_segment_binding_event
    WHERE event_id = p_event_id;
  IF FOUND THEN
    IF v_prev.binding_id = p_binding_id AND v_prev.request_sha256 = v_request_sha THEN
      RETURN inspect_media_capture_segment_binding(p_binding_id)
        || jsonb_build_object('write_result', 'REPLAY');
    END IF;
    RAISE EXCEPTION 'BINDING_REPLAY_CONFLICT' USING ERRCODE = 'P0001';
  END IF;
  SELECT * INTO v_existing FROM media_capture_segment_binding WHERE id = p_binding_id;
  IF FOUND THEN
    SELECT revision, event_kind INTO v_revision, v_latest_kind
      FROM media_capture_segment_binding_event
      WHERE binding_id = p_binding_id ORDER BY revision DESC LIMIT 1;
    IF v_revision IS DISTINCT FROM p_expected_revision THEN
      RAISE EXCEPTION 'BINDING_CAS_CONFLICT' USING ERRCODE = 'P0001';
    END IF;
    IF v_latest_kind = 'REVOKE' OR p_action = 'ATTEST' THEN
      RAISE EXCEPTION 'BINDING_REVOKED' USING ERRCODE = 'P0001';
    END IF;
    IF ROW(v_existing.content_id,v_existing.capture_id,v_existing.capture_sha256,
      v_existing.canonical_segment_id,v_existing.start_ms,v_existing.end_ms,
      v_existing.evidence_sha256,v_existing.attestor_ref) IS DISTINCT FROM
      ROW(p_content_id,p_capture_id,p_capture_sha256,p_segment_id,p_start_ms,
      p_end_ms,p_evidence_sha256,p_attestor_ref) THEN
      RAISE EXCEPTION 'BINDING_SUBJECT_CONFLICT' USING ERRCODE = 'P0001';
    END IF;
  ELSE
    IF p_expected_revision <> 0 OR p_action <> 'ATTEST' THEN
      RAISE EXCEPTION 'BINDING_CAS_CONFLICT' USING ERRCODE = 'P0001';
    END IF;
    -- FOR SHARE locks prevent rights/state updates racing this attestation.
    SELECT * INTO v_content FROM content_item
      WHERE id=p_content_id FOR SHARE;
    SELECT * INTO v_capture FROM content_capture
      WHERE id=p_capture_id AND content_id=p_content_id FOR SHARE;
    SELECT * INTO v_segment FROM canonical_transcript_segment
      WHERE id=p_segment_id AND content_id=p_content_id FOR SHARE;
    IF v_content.id IS NULL OR v_capture.id IS NULL OR v_segment.id IS NULL
       OR v_capture.content_sha256 <> p_capture_sha256
       OR v_segment.start_ms <> p_start_ms OR v_segment.end_ms <> p_end_ms
       OR v_segment.end_ms <= v_segment.start_ms
       OR v_content.duration_ms IS NULL OR v_segment.end_ms > v_content.duration_ms THEN
      RAISE EXCEPTION 'BINDING_SOURCE_MISMATCH' USING ERRCODE = 'P0001';
    END IF;
    IF v_capture.status <> 'CAPTURED' OR v_capture.hold_status <> 'NONE'
       OR v_capture.body_purged_at IS NOT NULL
       OR v_capture.rights_status IN ('REVOKED','DENIED','EXPIRED')
       OR v_content.rights_status IN ('REVOKED','DENIED','EXPIRED')
       OR v_segment.transcript_status <> 'RESOLVED'
       OR v_segment.publication_blocked THEN
      RAISE EXCEPTION 'BINDING_SOURCE_HELD' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM media_capture_segment_binding
               WHERE capture_id=p_capture_id AND canonical_segment_id=p_segment_id) THEN
      RAISE EXCEPTION 'BINDING_SUBJECT_CONFLICT' USING ERRCODE = 'P0001';
    END IF;
    INSERT INTO media_capture_segment_binding (
      id, content_id, capture_id, capture_sha256, canonical_segment_id,
      segment_index, start_ms, end_ms, evidence_sha256, attestor_ref
    ) VALUES (
      p_binding_id,p_content_id,p_capture_id,p_capture_sha256,p_segment_id,
      v_segment.segment_index,p_start_ms,p_end_ms,p_evidence_sha256,p_attestor_ref
    );
  END IF;
  INSERT INTO media_capture_segment_binding_event(
    event_id,binding_id,revision,event_kind,request_sha256
  ) VALUES (p_event_id,p_binding_id,p_expected_revision+1,p_action,v_request_sha);
  RETURN inspect_media_capture_segment_binding(p_binding_id)
    || jsonb_build_object('write_result','RECORDED');
END;
$body$;

COMMIT;

BEGIN;

-- Private signed agent claims complement, never replace, append-only source
-- rights records. The HMAC key stays outside PostgreSQL; a row is not proof
-- until authenticated against an active local reviewer credential.
CREATE TABLE IF NOT EXISTS private_camera_parse_attestation (
    receipt_id text PRIMARY KEY,
    rights_record_id text NOT NULL REFERENCES private_source_rights_record(id) ON DELETE RESTRICT,
    content_id text NOT NULL REFERENCES content_item(id) ON DELETE RESTRICT,
    capture_sha256 text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (receipt_id ~ '^camera-parse-receipt:[0-9a-f]{64}$'),
    CHECK (capture_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(payload) = 'object'),
    CHECK (payload->>'contract_version' = 'dp449-camera-private-parse-attestation-v1'),
    CHECK (payload->>'receipt_id' = receipt_id),
    CHECK (payload->>'rights_record_id' = rights_record_id),
    CHECK (payload->>'content_id' = content_id),
    CHECK (payload->>'capture_sha256' = capture_sha256),
    CHECK (payload->>'use' = 'PARSE_TEXT'),
    CHECK (payload->>'issuer_role' = 'PRIVATE_RIGHTS_AGENT'),
    CHECK (payload->>'jurisdiction' = 'IT'),
    CHECK (payload->>'publication_authority' = 'false')
);

CREATE INDEX IF NOT EXISTS private_camera_parse_attestation_lookup
    ON private_camera_parse_attestation(rights_record_id, content_id, capture_sha256, created_at DESC);

CREATE OR REPLACE FUNCTION reject_camera_parse_attestation_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'private_camera_parse_attestation is append-only';
END;
$$;
DROP TRIGGER IF EXISTS private_camera_parse_attestation_immutable ON private_camera_parse_attestation;
CREATE TRIGGER private_camera_parse_attestation_immutable
    BEFORE UPDATE OR DELETE ON private_camera_parse_attestation
    FOR EACH ROW EXECUTE FUNCTION reject_camera_parse_attestation_mutation();
DROP TRIGGER IF EXISTS private_camera_parse_attestation_no_truncate ON private_camera_parse_attestation;
CREATE TRIGGER private_camera_parse_attestation_no_truncate
    BEFORE TRUNCATE ON private_camera_parse_attestation
    FOR EACH STATEMENT EXECUTE FUNCTION reject_camera_parse_attestation_mutation();

COMMIT;

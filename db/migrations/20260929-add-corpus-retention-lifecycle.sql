BEGIN;

ALTER TABLE content_capture
    ADD COLUMN IF NOT EXISTS hold_status text NOT NULL DEFAULT 'NONE',
    ADD COLUMN IF NOT EXISTS archive_status text NOT NULL DEFAULT 'NOT_REQUESTED',
    ADD COLUMN IF NOT EXISTS archive_provider text,
    ADD COLUMN IF NOT EXISTS archive_requested_at timestamptz,
    ADD COLUMN IF NOT EXISTS archive_completed_at timestamptz,
    ADD COLUMN IF NOT EXISTS archive_receipt jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS body_purged_at timestamptz,
    ADD COLUMN IF NOT EXISTS purge_reason text,
    ADD COLUMN IF NOT EXISTS purge_receipt jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_status_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_retention_class_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_hold_status_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_archive_status_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_archive_receipt_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_purge_receipt_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_archive_requested_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_archive_completed_check;
ALTER TABLE content_capture DROP CONSTRAINT IF EXISTS content_capture_purged_body_check;

ALTER TABLE content_capture
    ADD CONSTRAINT content_capture_status_check
        CHECK (status IN ('CAPTURED', 'QUARANTINED', 'PURGE_PENDING', 'PURGED_BODY')),
    ADD CONSTRAINT content_capture_retention_class_check
        CHECK (retention_class IN ('POLICY_PENDING', 'EPHEMERAL', 'DURABLE_PRIVATE', 'DURABLE_PROVENANCE')),
    ADD CONSTRAINT content_capture_hold_status_check
        CHECK (hold_status IN ('NONE', 'LEGAL_HOLD', 'RIGHTS_HOLD', 'PRIVACY_HOLD', 'COPYRIGHT_HOLD', 'DISPUTE_HOLD')),
    ADD CONSTRAINT content_capture_archive_status_check
        CHECK (archive_status IN ('NOT_REQUESTED', 'REQUESTED', 'PENDING', 'SUCCEEDED', 'FAILED')),
    ADD CONSTRAINT content_capture_archive_receipt_check
        CHECK (jsonb_typeof(archive_receipt) = 'object'),
    ADD CONSTRAINT content_capture_purge_receipt_check
        CHECK (jsonb_typeof(purge_receipt) = 'object'),
    ADD CONSTRAINT content_capture_archive_requested_check
        CHECK (archive_status = 'NOT_REQUESTED' OR (archive_provider IS NOT NULL AND archive_requested_at IS NOT NULL)),
    ADD CONSTRAINT content_capture_archive_completed_check
        CHECK (archive_status NOT IN ('SUCCEEDED', 'FAILED') OR (archive_completed_at IS NOT NULL AND archive_receipt <> '{}'::jsonb)),
    ADD CONSTRAINT content_capture_purged_body_check
        CHECK (status <> 'PURGED_BODY' OR (body_ref IS NULL AND body_purged_at IS NOT NULL AND purge_reason IS NOT NULL AND purge_receipt <> '{}'::jsonb));

CREATE TABLE IF NOT EXISTS capture_lifecycle_event (
    id                  text PRIMARY KEY,
    capture_id          text NOT NULL REFERENCES content_capture(id) ON DELETE CASCADE,
    event_type          text NOT NULL,
    event_version       text NOT NULL DEFAULT 'capture-lifecycle-v1',
    actor_ref           text NOT NULL DEFAULT 'local-operator',
    previous_state      jsonb NOT NULL DEFAULT '{}'::jsonb,
    new_state           jsonb NOT NULL DEFAULT '{}'::jsonb,
    receipt             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (event_version = 'capture-lifecycle-v1'),
    CHECK (event_type IN (
        'ARCHIVE_REQUESTED', 'ARCHIVE_PENDING', 'ARCHIVE_SUCCEEDED', 'ARCHIVE_FAILED',
        'BODY_PURGE_REQUESTED', 'BODY_PURGED', 'BODY_PURGE_FAILED',
        'HOLD_SET', 'HOLD_RELEASED', 'RIGHTS_STATUS_CHANGED'
    )),
    CHECK (jsonb_typeof(previous_state) = 'object'),
    CHECK (jsonb_typeof(new_state) = 'object'),
    CHECK (jsonb_typeof(receipt) = 'object')
);

CREATE INDEX IF NOT EXISTS capture_lifecycle_event_capture_idx
    ON capture_lifecycle_event(capture_id, created_at DESC);

COMMIT;

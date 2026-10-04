BEGIN;

ALTER TABLE capture_lifecycle_event
    DROP CONSTRAINT IF EXISTS capture_lifecycle_event_event_type_check;

ALTER TABLE capture_lifecycle_event
    ADD CONSTRAINT capture_lifecycle_event_event_type_check
    CHECK (event_type IN (
        'ARCHIVE_REQUESTED', 'ARCHIVE_PENDING', 'ARCHIVE_SUCCEEDED', 'ARCHIVE_FAILED',
        'BODY_PURGE_REQUESTED', 'BODY_PURGED', 'BODY_PURGE_FAILED',
        'HOLD_SET', 'HOLD_RELEASED', 'RIGHTS_STATUS_CHANGED',
        'CAPTURE_REOBSERVED', 'PARSE_SUCCEEDED', 'PARSE_FAILED', 'BROWSER_FALLBACK_FAILED'
    ));

COMMIT;

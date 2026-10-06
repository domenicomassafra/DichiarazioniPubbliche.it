BEGIN;

-- DP-309: private, append-only reviewed high-risk packet.
--
-- Text bodies are deliberately absent. The packet binds the exact reviewed source/public
-- text through SHA-256 digests and stores only bounded opaque references to privacy,
-- official-record, jurisdiction, effective-time, human-review, and qualified-policy records.
-- A row is evidence of what was reviewed; it is not legal-policy authority or publication
-- authority. Runtime replay must re-run high-risk-assertion-v1 over the current text/input.
CREATE TABLE IF NOT EXISTS private_high_risk_review_packet (
    packet_id                         text PRIMARY KEY,
    contract_version                  text NOT NULL,
    record_ref                        text NOT NULL,
    finding_ref                       text NOT NULL,
    record_version                    text NOT NULL,
    source_text_sha256                text NOT NULL,
    normalized_text_sha256            text NOT NULL,
    source_allegation_framing         boolean NOT NULL,
    normalized_allegation_framing     boolean NOT NULL,
    legal_status_claim                boolean NOT NULL,
    identity_sensitive                boolean NOT NULL,
    sensitive_private                 boolean NOT NULL,
    minor_victim_private_person       boolean NOT NULL,
    identity_resolved                 boolean NOT NULL,
    privacy_allows                    boolean NOT NULL,
    privacy_decision_ref              text,
    privacy_decision_binding_ref      text,
    official_record_state             text NOT NULL,
    official_record_ref               text,
    official_record_approved          boolean NOT NULL,
    jurisdiction_state                text NOT NULL,
    jurisdiction_ref                  text,
    jurisdiction_match                boolean NOT NULL,
    effective_time_state              text NOT NULL,
    effective_time_ref                text,
    effective_time_match              boolean NOT NULL,
    human_review_actor_ref            text,
    human_review_ref                  text,
    human_reviewed_at_text            text,
    human_review_approved             boolean NOT NULL,
    dual_control_approved             boolean NOT NULL,
    qualified_policy_accepted         boolean NOT NULL DEFAULT false,
    policy_decision_ref               text,
    high_risk_policy_version          text NOT NULL,
    input_sha256                      text NOT NULL,
    decision_disposition              text NOT NULL,
    decision_reason_codes             jsonb NOT NULL,
    risk_classes                      jsonb NOT NULL,
    procedural_statuses               jsonb NOT NULL,
    decision_policy_ref               text,
    decision_binding_sha256           text NOT NULL,
    packet_sequence                   integer NOT NULL CHECK (packet_sequence > 0),
    supersedes_packet_id              text REFERENCES private_high_risk_review_packet(packet_id)
                                      ON DELETE RESTRICT,
    packet_integrity_sha256           text NOT NULL,
    record_visibility                 text NOT NULL DEFAULT 'PRIVATE',
    persisted_at                      timestamptz NOT NULL DEFAULT now(),
    CHECK (contract_version = 'high-risk-reviewed-packet-v1'),
    CHECK (length(record_ref) BETWEEN 1 AND 256),
    CHECK (length(finding_ref) BETWEEN 1 AND 256),
    CHECK (length(record_version) BETWEEN 1 AND 256),
    CHECK (source_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (normalized_text_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (decision_binding_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (packet_integrity_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (packet_id = 'high-risk-packet:' || packet_integrity_sha256),
    CHECK ((privacy_decision_ref IS NULL) = (privacy_decision_binding_ref IS NULL)),
    CHECK (privacy_decision_ref IS NULL OR length(privacy_decision_ref) BETWEEN 1 AND 256),
    CHECK (
        privacy_decision_binding_ref IS NULL
        OR length(privacy_decision_binding_ref) BETWEEN 1 AND 256
    ),
    CHECK (official_record_state IN ('APPROVED', 'NOT_APPROVED', 'UNRESOLVED')),
    CHECK (official_record_approved = (official_record_state = 'APPROVED')),
    CHECK (official_record_state <> 'APPROVED' OR official_record_ref IS NOT NULL),
    CHECK (official_record_ref IS NULL OR length(official_record_ref) BETWEEN 1 AND 256),
    CHECK (jurisdiction_state IN ('MATCH', 'MISMATCH', 'UNRESOLVED')),
    CHECK (jurisdiction_match = (jurisdiction_state = 'MATCH')),
    CHECK (jurisdiction_state <> 'MATCH' OR jurisdiction_ref IS NOT NULL),
    CHECK (jurisdiction_ref IS NULL OR length(jurisdiction_ref) BETWEEN 1 AND 256),
    CHECK (effective_time_state IN ('MATCH', 'MISMATCH', 'UNRESOLVED')),
    CHECK (effective_time_match = (effective_time_state = 'MATCH')),
    CHECK (effective_time_state <> 'MATCH' OR effective_time_ref IS NOT NULL),
    CHECK (effective_time_ref IS NULL OR length(effective_time_ref) BETWEEN 1 AND 256),
    CHECK (
        (human_review_actor_ref IS NULL)
        = (human_review_ref IS NULL)
        AND (human_review_ref IS NULL) = (human_reviewed_at_text IS NULL)
    ),
    CHECK (human_review_actor_ref IS NULL OR length(human_review_actor_ref) BETWEEN 1 AND 256),
    CHECK (human_review_ref IS NULL OR length(human_review_ref) BETWEEN 1 AND 256),
    CHECK (human_reviewed_at_text IS NULL OR length(human_reviewed_at_text) BETWEEN 1 AND 64),
    CHECK (NOT human_review_approved OR human_review_actor_ref IS NOT NULL),
    CHECK (
        (qualified_policy_accepted AND policy_decision_ref IS NOT NULL)
        OR (NOT qualified_policy_accepted AND policy_decision_ref IS NULL)
    ),
    CHECK (policy_decision_ref IS NULL OR length(policy_decision_ref) BETWEEN 1 AND 256),
    CHECK (length(high_risk_policy_version) BETWEEN 1 AND 128),
    CHECK (decision_disposition IN ('STANDARD_REVIEW', 'HOLD_HIGH_RISK', 'ELIGIBLE_HIGH_RISK')),
    CHECK (jsonb_typeof(decision_reason_codes) = 'array'),
    CHECK (jsonb_array_length(decision_reason_codes) BETWEEN 1 AND 32),
    CHECK (jsonb_typeof(risk_classes) = 'array'),
    CHECK (jsonb_array_length(risk_classes) <= 16),
    CHECK (jsonb_typeof(procedural_statuses) = 'array'),
    CHECK (jsonb_array_length(procedural_statuses) <= 16),
    CHECK (decision_policy_ref IS NOT DISTINCT FROM policy_decision_ref),
    CHECK (decision_policy_ref IS NULL OR length(decision_policy_ref) BETWEEN 1 AND 256),
    CHECK (record_visibility = 'PRIVATE'),
    CHECK (supersedes_packet_id IS NULL OR supersedes_packet_id <> packet_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS private_high_risk_review_packet_root_idx
    ON private_high_risk_review_packet(record_ref, finding_ref)
    WHERE supersedes_packet_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS private_high_risk_review_packet_one_successor_idx
    ON private_high_risk_review_packet(supersedes_packet_id)
    WHERE supersedes_packet_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS private_high_risk_review_packet_sequence_idx
    ON private_high_risk_review_packet(record_ref, finding_ref, packet_sequence);

CREATE INDEX IF NOT EXISTS private_high_risk_review_packet_current_idx
    ON private_high_risk_review_packet(record_ref, finding_ref, packet_sequence DESC);

CREATE OR REPLACE FUNCTION validate_private_high_risk_review_packet_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent private_high_risk_review_packet%ROWTYPE;
BEGIN
    IF NEW.supersedes_packet_id IS NULL THEN
        IF NEW.packet_sequence <> 1 THEN
            RAISE EXCEPTION 'private_high_risk_review_packet root sequence must be 1';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO parent
    FROM private_high_risk_review_packet
    WHERE packet_id = NEW.supersedes_packet_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'private_high_risk_review_packet supersedes target missing';
    END IF;
    IF parent.record_ref <> NEW.record_ref OR parent.finding_ref <> NEW.finding_ref THEN
        RAISE EXCEPTION 'private_high_risk_review_packet supersedes binding mismatch';
    END IF;
    IF NEW.packet_sequence <> parent.packet_sequence + 1 THEN
        RAISE EXCEPTION 'private_high_risk_review_packet sequence mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS private_high_risk_review_packet_validate_insert
    ON private_high_risk_review_packet;
CREATE TRIGGER private_high_risk_review_packet_validate_insert
BEFORE INSERT ON private_high_risk_review_packet
FOR EACH ROW EXECUTE FUNCTION validate_private_high_risk_review_packet_insert();

CREATE OR REPLACE FUNCTION reject_private_high_risk_review_packet_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'private_high_risk_review_packet is append-only';
END;
$$;

DROP TRIGGER IF EXISTS private_high_risk_review_packet_append_only
    ON private_high_risk_review_packet;
CREATE TRIGGER private_high_risk_review_packet_append_only
BEFORE UPDATE OR DELETE ON private_high_risk_review_packet
FOR EACH ROW EXECUTE FUNCTION reject_private_high_risk_review_packet_mutation();

DROP TRIGGER IF EXISTS private_high_risk_review_packet_no_truncate
    ON private_high_risk_review_packet;
CREATE TRIGGER private_high_risk_review_packet_no_truncate
BEFORE TRUNCATE ON private_high_risk_review_packet
FOR EACH STATEMENT EXECUTE FUNCTION reject_private_high_risk_review_packet_mutation();

COMMIT;

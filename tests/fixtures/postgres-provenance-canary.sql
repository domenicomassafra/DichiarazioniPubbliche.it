INSERT INTO source (
    id, canonical_name, source_type, canonical_url, language, country_code
) VALUES (
    'source:canary', 'Canary Source', 'MEDIA',
    'https://example.test/source', 'it', 'IT'
);

INSERT INTO person (
    id, canonical_name, public_role, country_code
) VALUES (
    'person:canary', 'Canary Person', 'Public role', 'IT'
);

INSERT INTO content_item (
    id, source_id, source_external_id, canonical_url, title, language,
    published_at, processing_status
) VALUES (
    'content:canary', 'source:canary', 'canary-1',
    'https://example.test/content', 'Canary Content', 'it',
    '2026-09-22T10:00:00+00:00', 'READY'
);

INSERT INTO transcript_variant (
    id, content_id, provider_id, source_kind, language, raw_text_sha256,
    raw_text, is_platform_caption
) VALUES (
    'transcript:canary', 'content:canary', 'canary-provider',
    'PLATFORM_CAPTION', 'it',
    repeat('a', 64), 'Valore dieci.', true
);

INSERT INTO transcript_segment (
    id, variant_id, segment_index, start_ms, end_ms, text
) VALUES (
    'segment:canary', 'transcript:canary', 0, 0, 1000, 'Valore dieci.'
);

INSERT INTO canonical_transcript_segment (
    id, content_id, segment_index, start_ms, end_ms, speaker_person_id,
    canonical_text, transcript_status, publication_blocked
) VALUES (
    'canonical-segment:canary', 'content:canary', 0, 0, 1000,
    'person:canary', 'Valore dieci.', 'RESOLVED', false
);

INSERT INTO canonical_segment_candidate (
    canonical_segment_id, transcript_segment_id
) VALUES (
    'canonical-segment:canary', 'segment:canary'
);

INSERT INTO speaker_identity_candidate (
    id, content_id, person_id, start_ms, end_ms, attribution_method,
    attribution_version, source_ref, confidence, status
) VALUES (
    'speaker-candidate:canary', 'content:canary', 'person:canary',
    0, 1000, 'MANUAL_REVIEW', 'canary-v1',
    '{"fixture":"canary"}'::jsonb, 1.0, 'APPROVED'
);

INSERT INTO atomic_claim (
    id, content_id, speaker_person_id, normalized_claim, claim_type,
    temporal_scope, check_worthy, extraction_model, extraction_version
) VALUES (
    'claim:canary', 'content:canary', 'person:canary',
    'Il valore è dieci.', 'NUMERIC_STATISTIC',
    '{"statement_date":"2026-09-22"}'::jsonb, true,
    'fixture', 'canary-v1'
);

INSERT INTO claim_segment (claim_id, segment_id)
VALUES ('claim:canary', 'canonical-segment:canary');

INSERT INTO evidence (
    id, canonical_url, publisher, source_type, publication_date, fetched_at,
    content_sha256, reference_period, rights_status
) VALUES (
    'evidence:canary', 'https://example.test/evidence', 'Canary Authority',
    'PRIMARY_OFFICIAL', '2026-09-21', now(), repeat('b', 64), '2026',
    'UNKNOWN'
);

INSERT INTO claim_evidence_candidate (
    claim_id, evidence_id, retrieval_method, retrieval_version,
    relation_candidate, status, score, statement_cutoff
) VALUES (
    'claim:canary', 'evidence:canary', 'fixture', 'canary-v1',
    'SUPPORT', 'APPROVED', 1.0, '2026-09-22'
);

INSERT INTO evidence_observation (
    id, evidence_id, observation_type, metric, value_numeric, unit,
    reference_period, extraction_method, extraction_version, source_pointer,
    status
) VALUES (
    'observation:canary', 'evidence:canary', 'METRIC', 'canary_metric',
    10, 'count', '2026', 'STRUCTURED', 'canary-v1',
    '{"fixture":"canary"}'::jsonb, 'APPROVED'
);

INSERT INTO verification_run (
    id, claim_id, verification_kind, verification_version, verification_rule,
    input_fingerprint, statement_cutoff, assessment, evidence_ids,
    observation_ids, blockers, rationale_codes, result
) VALUES (
    'verification:canary', 'claim:canary', 'numeric_exact',
    'deterministic-verification-v2',
    '{"metric":"canary_metric","value":10}'::jsonb,
    repeat('c', 64), '2026-09-22', 'SUPPORTED',
    '["evidence:canary"]'::jsonb,
    '["observation:canary"]'::jsonb,
    '[]'::jsonb, '["CANARY"]'::jsonb, '{}'::jsonb
);

INSERT INTO finding (
    id, claim_id, assessment, rationale, publication_status, policy_version,
    model_bundle, verification_run_id
) VALUES (
    'finding:canary', 'claim:canary', 'SUPPORTED',
    'Canary deterministic finding.', 'POLICY_HOLD', 'canary-policy-v1',
    '{}'::jsonb, 'verification:canary'
);

INSERT INTO finding_evidence (finding_id, evidence_id, relation)
VALUES ('finding:canary', 'evidence:canary', 'VERIFICATION_INPUT');

INSERT INTO review_event (
    id, entity_type, entity_id, action, actor_ref, reason
) VALUES
(
    'review:evidence:canary', 'CLAIM_EVIDENCE_CANDIDATE',
    'claim:canary|evidence:canary|canary-v1', 'APPROVED',
    'canary', 'fixture approval'
),
(
    'review:observation:canary', 'EVIDENCE_OBSERVATION',
    'observation:canary', 'APPROVED', 'canary', 'fixture approval'
),
(
    'review:speaker:canary', 'SPEAKER_IDENTITY_CANDIDATE',
    'speaker-candidate:canary', 'APPROVED', 'canary', 'fixture approval'
);

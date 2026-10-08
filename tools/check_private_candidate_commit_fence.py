#!/usr/bin/env python3
"""DP-214 candidate SQL authority fence: PostgreSQL pg_temp/ROLLBACK canary.

No production table writes, provider calls, source bodies, or approvals.
The synthetic positive case proves SQL wiring, not a real rights grant.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore  # noqa: E402
from dichiarazioni_pubbliche.candidate_extraction import _COMMIT_BATCH_SQL  # noqa: E402
from dichiarazioni_pubbliche.private_candidate_commit_fence import (  # noqa: E402
    PRIVATE_CANDIDATE_COMMIT_AUTHORITY_CTE, PrivateCandidateCommitFence,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402


def fixture_scope() -> PrivateCandidateCommitFence:
    return PrivateCandidateCommitFence(
        collection_id="research:fence-canary",
        content_id="content:fence-canary",
        capture_id="capture:fence-canary",
        passage_id="passage:fence-canary",
        passage_sha256="a" * 64,
        canonical_url="https://example.test/authority-fence",
        source_family="REPORTING",
        rights_record_id="private-rights:fence-canary",
    )


def ephemeral_fence_sql() -> str:
    def probe(label: str) -> str:
        return f"WITH {PRIVATE_CANDIDATE_COMMIT_AUTHORITY_CTE}\nSELECT '{label}|' || count(*)::text FROM commit_authority;\n"

    return f"""
    BEGIN;
    SET LOCAL search_path TO pg_temp, public;
    CREATE TEMP TABLE content_item (id text, canonical_url text, rights_status text);
    CREATE TEMP TABLE research_collection (id text, status text);
    CREATE TEMP TABLE research_collection_content (
        collection_id text, content_id text, status text, metadata jsonb
    );
    CREATE TEMP TABLE content_capture (
        id text, content_id text, status text, rights_status text, hold_status text,
        body_ref text, retention_class text
    );
    CREATE TEMP TABLE passage (id text, content_id text, capture_id text, text_sha256 text);
    CREATE TEMP TABLE private_source_rights_record (
        id text, content_id text, locator_kind text, locator_value text,
        source_family text, rights_status text, record_version text,
        record_visibility text, rights_receipt_ref text, reviewer_ref text,
        reviewed_at timestamptz, expires_at timestamptz, evidence_id text,
        passage_id text, transcript_segment_id text, canonical_segment_id text,
        permitted_uses text[], supersedes_id text
    );
    CREATE TEMP TABLE privacy_ingestion_relevance_authority (
        authority_id text, content_ref text, content_binding_sha256 text,
        contract_version text, binding_version text, privacy_policy_version text,
        record_visibility text, supersedes_authority_id text
    );
    CREATE TEMP TABLE research_discovery_manifest (
        id text, collection_id text, manifest_sha256 text, source_families jsonb, status text
    );
    CREATE TEMP TABLE research_discovery_run (
        id text, manifest_id text, manifest_sha256 text, status text
    );
    CREATE TEMP TABLE research_discovery_query (
        id text, manifest_id text, source_families jsonb, adapter_ids jsonb
    );
    CREATE TEMP TABLE research_discovery_attempt (
        id text, run_id text, query_id text, status text, adapter_id text
    );
    CREATE TEMP TABLE research_discovery_hit (
        id text, content_id text, canonical_url text, source_family text,
        disposition text, run_id text, query_id text, attempt_id text
    );
    INSERT INTO content_item VALUES
        ('content:fence-canary', 'https://example.test/authority-fence', 'CLEARED');
    INSERT INTO research_collection VALUES ('research:fence-canary', 'ACTIVE');
    INSERT INTO research_collection_content VALUES
        ('research:fence-canary', 'content:fence-canary', 'INCLUDED',
          '{{"capture_authorized":true}}');
    INSERT INTO content_capture VALUES
        ('capture:fence-canary', 'content:fence-canary', 'CAPTURED', 'CLEARED',
         'NONE', 'private-body-ref', 'EPHEMERAL');
    INSERT INTO passage VALUES
        ('passage:fence-canary', 'content:fence-canary', 'capture:fence-canary',
         repeat('a',64));
    INSERT INTO private_source_rights_record VALUES
        ('private-rights:fence-canary', 'content:fence-canary', 'URL',
         'https://example.test/authority-fence', 'REPORTING', 'CLEARED',
         'private-rights-record-v1', 'PRIVATE', 'receipt:test', 'reviewer:test',
         now()-interval '1 hour', now()+interval '1 hour', null,null,null,null,
         ARRAY['RESEARCH_CAPTURE_PRIVATE','OMNIROUTE_MODEL_EXTRACTION_PRIVATE'],null);
    INSERT INTO privacy_ingestion_relevance_authority VALUES
        ('relevance:canary','content:fence-canary', :'fence_relevance_binding_sha256',
         'privacy-ingestion-relevance-v1','content-acquisition-binding-v1',
         'privacy-minimization-v1','PRIVATE',null);
    INSERT INTO research_discovery_manifest VALUES
        ('manifest:canary','research:fence-canary',repeat('a',64),'["REPORTING"]','ACTIVE');
    INSERT INTO research_discovery_run VALUES
        ('run:canary','manifest:canary',repeat('a',64),'COMPLETED');
    INSERT INTO research_discovery_query VALUES
        ('query:canary','manifest:canary','["REPORTING"]','["trusted-adapter"]');
    INSERT INTO research_discovery_attempt VALUES
        ('attempt:canary','run:canary','query:canary','HEALTHY','trusted-adapter');
    INSERT INTO research_discovery_hit VALUES
        ('hit:canary','content:fence-canary','https://example.test/authority-fence',
         'REPORTING','NEW_CONTENT','run:canary','query:canary','attempt:canary');
    {probe('valid')}
    UPDATE private_source_rights_record SET rights_status='REVOKED';
    {probe('rights_revoked')}
    UPDATE private_source_rights_record SET rights_status='CLEARED';
    INSERT INTO private_source_rights_record (id,supersedes_id) VALUES
        ('private-rights:successor','private-rights:fence-canary');
    {probe('rights_superseded')}
    DELETE FROM private_source_rights_record WHERE id='private-rights:successor';
    UPDATE private_source_rights_record SET expires_at=now()-interval '1 minute';
    {probe('rights_expired')}
    UPDATE private_source_rights_record SET expires_at=now()+interval '1 hour';
    UPDATE private_source_rights_record SET permitted_uses=ARRAY['RESEARCH_CAPTURE_PRIVATE'];
    {probe('model_use_removed')}
    UPDATE private_source_rights_record SET permitted_uses=
        ARRAY['RESEARCH_CAPTURE_PRIVATE','OMNIROUTE_MODEL_EXTRACTION_PRIVATE'];
    UPDATE research_collection SET status='PAUSED';
    {probe('collection_paused')}
    UPDATE research_collection SET status='ACTIVE';
    UPDATE content_capture SET hold_status='RIGHTS_HOLD';
    {probe('capture_held')}
    UPDATE content_capture SET hold_status='NONE',body_ref=NULL;
    {probe('body_purged')}
    UPDATE content_capture SET body_ref='private-body-ref';
    UPDATE passage SET text_sha256=repeat('b',64);
    {probe('passage_hash_changed')}
    UPDATE passage SET text_sha256=repeat('a',64);
    INSERT INTO privacy_ingestion_relevance_authority (
        authority_id,supersedes_authority_id
    ) VALUES ('relevance:successor','relevance:canary');
    {probe('privacy_superseded')}
    DELETE FROM privacy_ingestion_relevance_authority WHERE authority_id='relevance:successor';
    UPDATE privacy_ingestion_relevance_authority SET content_binding_sha256=repeat('c',64);
    {probe('privacy_binding_stale')}
    UPDATE privacy_ingestion_relevance_authority
      SET content_binding_sha256=:'fence_relevance_binding_sha256';
    UPDATE research_discovery_attempt SET status='FAILED';
    {probe('discovery_attempt_failed')}
    UPDATE research_discovery_attempt SET status='HEALTHY';
    UPDATE research_discovery_query SET source_families='["UNRELATED"]';
    {probe('discovery_source_family_mismatch')}
    UPDATE research_discovery_query SET source_families='["REPORTING"]';
    UPDATE research_collection_content SET metadata='{{"capture_authorized":false}}';
    {probe('membership_authorization_revoked')}
    UPDATE research_collection_content SET metadata='{{"capture_authorized":true}}';
    UPDATE content_item SET rights_status='UNKNOWN';
    {probe('content_rights_revoked')}
    UPDATE content_item SET rights_status='CLEARED';
    INSERT INTO research_collection VALUES ('research:other', 'PAUSED');
    INSERT INTO research_collection_content VALUES
        ('research:other','content:fence-canary','INCLUDED','{{"capture_authorized":true}}');
    {probe('conflicting_collection_paused')}
    ROLLBACK;
    """


_OUTPUT_TABLES = (
    "candidate_extraction_run", "provider_receipt", "statement_candidate",
    "statement_candidate_passage", "claim_candidate", "entity_mention_candidate",
    "entity_resolution_candidate",
)
_WRITTEN_TABLES = (
    "passage", "provider_receipt", "statement_candidate", "statement_candidate_passage",
    "claim_candidate", "entity_mention_candidate", "entity_resolution_candidate",
)


def full_commit_canary_sql() -> str:
    """Execute the *actual full Candidate SQL*, including CTE inserts, on TEMP shadow tables.

    All statements run under the outer fixture's BEGIN/ROLLBACK. Deliberately
    exclude the inner BEGIN/COMMIT from the production transaction template
    so no fixture write can escape the rollback.
    """
    fixture = ephemeral_fence_sql()
    head, separator, _ = fixture.partition("WITH commit_authority AS MATERIALIZED")
    if not separator or "ROLLBACK;" in head:
        raise RuntimeError("CANDIDATE_FULL_COMMIT_FIXTURE_DRIFT")
    head = head.replace(
        "CREATE TEMP TABLE passage (id text, content_id text, capture_id text, text_sha256 text);",
        "CREATE TEMP TABLE passage (LIKE public.passage INCLUDING DEFAULTS);",
    )
    head = head.replace(
        """INSERT INTO passage VALUES
        ('passage:fence-canary', 'content:fence-canary', 'capture:fence-canary',
         repeat('a',64));""",
        """INSERT INTO passage (id,content_id,capture_id,selector_type,start_char,
          end_char,text_sha256,private_text,extraction_method,extraction_version)
        VALUES ('passage:fence-canary','content:fence-canary','capture:fence-canary',
          'TEXT_POSITION',0,12,repeat('a',64),'Canary text.','SYNTHETIC','test-v1');""",
    )
    if "CREATE TEMP TABLE passage (LIKE public.passage" not in head or "INSERT INTO passage VALUES" in head:
        raise RuntimeError("CANDIDATE_FULL_COMMIT_PASSAGE_FIXTURE_DRIFT")
    for table in _OUTPUT_TABLES:
        head += f"\nCREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING DEFAULTS INCLUDING INDEXES);\n"
    head += """
    INSERT INTO candidate_extraction_run (
      id,operation_key,content_id,passage_id,capture_id,input_sha256,
      provider_id,model_id,provider_version,status,lease_owner,lease_until,
      cost_upper_bound_usd,metadata
    ) VALUES (
      :'run_id', 'canary:operation','content:fence-canary','passage:fence-canary',
      'capture:fence-canary',repeat('a',64),'fake-fixture','test-only',
      'test-v1','RUNNING',:'lease_owner',now()+interval '5 minutes',
      0.003,'{"provider_call_state":"STARTED_COST_UPPER_BOUND_RESERVED"}'
    );
    """
    body = _COMMIT_BATCH_SQL.removeprefix("BEGIN;\n")
    if body == _COMMIT_BATCH_SQL or not body.endswith("\nCOMMIT;"):
        raise RuntimeError("CANDIDATE_FULL_COMMIT_SQL_TRANSACTION_DRIFT")
    body = body.removesuffix("\nCOMMIT;")
    def counts(label: str) -> str:
        pairs = " || ',' || ".join(
            f"(SELECT count(*)::text FROM {name})" for name in _WRITTEN_TABLES
        )
        return f"SELECT '{label}|' || {pairs};\n"
    sql = head + "\n"
    for label, setup in (
        ("rights_revoked", "UPDATE private_source_rights_record SET rights_status='REVOKED';"),
        ("capture_held", """UPDATE private_source_rights_record SET rights_status='CLEARED';
          UPDATE content_capture SET hold_status='RIGHTS_HOLD';"""),
        ("discovery_failed", """UPDATE content_capture SET hold_status='NONE';
          UPDATE research_discovery_attempt SET status='FAILED';"""),
        ("passage_stale", """UPDATE research_discovery_attempt SET status='HEALTHY';
          UPDATE passage SET text_sha256=repeat('b',64);"""),
        ("valid", "UPDATE passage SET text_sha256=repeat('a',64);"),
    ):
        sql += setup + "\n" + body + "\n" + counts(label)
    sql += "ROLLBACK;\n"
    return sql


def full_commit_parameters() -> dict[str, str]:
    """No provider calls; all source material and approvals are test-only temp rows."""
    fields = fixture_scope().sql_parameters()
    child = "passage:fence-child"
    fields.update({
        "run_id": "candidate-extraction-run:fence-canary",
        "lease_owner": "test-only-lease",
        "passages": json.dumps([{
            "id": child, "content_id": fields["fence_content_id"],
            "capture_id": fields["fence_capture_id"], "selector_type": "TEXT_POSITION",
            "start_char": 0, "end_char": 11, "text_sha256": "b"*64,
            "private_text": "Canary text", "language": "it",
            "extraction_method": "SYNTHETIC", "extraction_version": "test-v1",
            "metadata": {},
        }]),
        "statements": json.dumps([{
            "id": "statement:fence-canary", "content_id": fields["fence_content_id"],
            "passage_id": child, "speaker_person_id": None,
            "statement_text_hash": "c"*64, "normalized_statement": "Synthetic test",
            "statement_at": None, "attribution_method": "MODEL",
            "extraction_model": "test-only", "extraction_version": "test-v1",
            "metadata": {},
        }]),
        "claims": json.dumps([{
            "id": "claim-candidate:fence-canary", "statement_candidate_id": "statement:fence-canary",
            "content_id": fields["fence_content_id"], "normalized_claim": "Synthetic test claim",
            "proposed_claim_type": "HISTORICAL_CLAIM", "claim_type_version": "test-v1",
            "temporal_scope": {}, "check_worthy": True,
            "extraction_model": "test-only", "extraction_version": "test-v1",
            "metadata": {},
        }]),
        "mentions": json.dumps([{
            "id": "mention:fence-canary", "extraction_run_id": "candidate-extraction-run:fence-canary",
            "content_id": fields["fence_content_id"], "passage_id": child,
            "start_char": 0, "end_char": 6, "mention_text": "Canary",
            "mention_text_sha256": "d"*64, "proposed_entity_type": "PERSON",
            "extraction_method": "MODEL", "metadata": {},
        }]),
        "resolutions": json.dumps([{
            "id": "resolution:fence-canary", "content_id": fields["fence_content_id"],
            "passage_id": child, "mention_text": "Canary",
            "mention_text_sha256": "d"*64, "entity_type": "PERSON",
            "target_person_id": "person:test-only", "target_organization_id": None,
            "target_topic_id": None, "target_event_id": None,
            "resolution_method": "KNOWN_ALIAS", "supporting_features": [],
            "metadata": {},
        }]),
        "provider_receipt_id": "provider-receipt:fence-canary",
        "request_id": "test-only",
        "input_bytes": "12",
        "cost_usd": "0.002",
        "total_tokens": "12",
        "provider_receipt": '{"cost_basis":"test-only"}',
        "statement_count": "1",
        "claim_count": "1",
        "entity_mention_count": "1",
        "entity_resolution_count": "1",
        "fence_required": "true",
    })
    return fields


def check_full_commit_receipts(raw: str) -> dict[str, object]:
    expected = {
        "rights_revoked": [1, 0, 0, 0, 0, 0, 0],
        "capture_held": [1, 0, 0, 0, 0, 0, 0],
        "discovery_failed": [1, 0, 0, 0, 0, 0, 0],
        "passage_stale": [1, 0, 0, 0, 0, 0, 0],
        "valid": [2, 1, 1, 1, 1, 1, 1],
    }
    observed: dict[str, list[int]] = {}
    completed_rows = 0
    for line in raw.splitlines():
        if line.startswith("{"):
            # A successful COMMIT must return the updated run receipt exactly once.
            receipt = json.loads(line)
            if receipt.get("status") != "COMPLETED":
                raise RuntimeError("CANDIDATE_FULL_COMMIT_STATUS_INVALID")
            completed_rows += 1
            continue
        if not line.strip():
            continue
        fields = line.split("|")
        if len(fields) != 2 or fields[0] not in expected or fields[0] in observed:
            raise RuntimeError("CANDIDATE_FULL_COMMIT_RECEIPT_INVALID")
        try:
            observed[fields[0]] = [int(x) for x in fields[1].split(",")]
        except ValueError as exc:
            raise RuntimeError("CANDIDATE_FULL_COMMIT_COUNTS_INVALID") from exc
    if observed != expected or completed_rows != 1:
        raise RuntimeError("CANDIDATE_FULL_COMMIT_ATOMICITY_FAIL")
    return {
        "status": "PASS_ROLLBACK_ONLY",
        "full_commit_sql_executed": True,
        "negative_commits_rejected": 4,
        "positive_synthetic_commit": 1,
        "candidate_receipt_and_run_atomicity": True,
        "publication_authorized": False,
    }


_EXPECTED = {
    "valid": 1,
    "rights_revoked": 0,
    "rights_superseded": 0,
    "rights_expired": 0,
    "model_use_removed": 0,
    "collection_paused": 0,
    "capture_held": 0,
    "body_purged": 0,
    "passage_hash_changed": 0,
    "privacy_superseded": 0,
    "privacy_binding_stale": 0,
    "discovery_attempt_failed": 0,
    "discovery_source_family_mismatch": 0,
    "membership_authorization_revoked": 0,
    "content_rights_revoked": 0,
    "conflicting_collection_paused": 0,
}


def evaluate_receipts(raw: str) -> dict[str, object]:
    results: dict[str, int] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != 2 or parts[0] not in _EXPECTED or parts[0] in results or parts[1] not in {"0", "1"}:
            raise RuntimeError("CANDIDATE_COMMIT_FENCE_CANARY_RECEIPT_INVALID")
        results[parts[0]] = int(parts[1])
    if results != _EXPECTED:
        raise RuntimeError("CANDIDATE_COMMIT_FENCE_CANARY_AUTHORITY_BYPASS")
    return {
        "status": "PASS_ROLLBACK_ONLY",
        "positive_synthetic_probe": 1,
        "revocation_or_mismatch_blocked": len(results) - 1,
        "private_candidates_written": False,
        "publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--full-commit", action="store_true",
                        help="Also execute exact production CTE batch SQL on pg_temp shadow tables")
    args = parser.parse_args(argv)
    capture = CapturePipelineStore(database_url=args.database_url)
    before = capture.read_private_capture_safety_counts()
    observed = PsqlRuntime(database_url=args.database_url).run(
        ephemeral_fence_sql(), **fixture_scope().sql_parameters()
    )
    result = evaluate_receipts(observed)
    if args.full_commit:
        actual = PsqlRuntime(database_url=args.database_url).run(
            full_commit_canary_sql(), **full_commit_parameters()
        )
        result["full_commit"] = check_full_commit_receipts(actual)
    after = capture.read_private_capture_safety_counts()
    if before != after:
        raise RuntimeError("CANDIDATE_COMMIT_FENCE_PROTECTED_COUNTS_CHANGED")
    print(json.dumps({**result, "protected_counts_unchanged": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""DP-310 prerequisite: a duplicate review_event ID must not publish a Finding.

The complete canonical PostgreSQL schema and a synthetic, fully eligible
verification/evidence chain exercise the real publication SQL. No real claim
or production database is touched.
"""

from __future__ import annotations

import json
import socket
import tempfile
import unittest
from pathlib import Path

from tests.test_claim_evidence_retrieval_replay import ROOT, _bin, _cmd

import sys
sys.path.insert(0, str(ROOT / "poc"))
from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore  # noqa: E402


class PublicFindingReviewCollisionPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp310-finding-event-")
        cls.root = Path(cls.tmp.name)
        cls.pgdata = cls.root / "pg"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.pgctl = _bin("pg_ctl")
        _cmd([_bin("initdb"), "-D", str(cls.pgdata), "--username=postgres", "--auth=trust", "--no-locale"])
        _cmd([cls.pgctl, "-D", str(cls.pgdata), "-l", str(cls.root / "postgres.log"),
              "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
        cls.database = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database,
              "-f", str(ROOT / "db/schema.v1.sql")])
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin="""
             INSERT INTO person(id, canonical_name)
             VALUES ('person:fixture','Reviewer fixture speaker');
             INSERT INTO content_item(id,canonical_url,title,processing_status)
             VALUES ('content:fixture','https://example.test/approved-quote',
                     'synthetic licensed-style fixture','PROCESSED');
             INSERT INTO atomic_claim(
                 id,content_id,speaker_person_id,normalized_claim,claim_type,
                 temporal_scope,check_worthy,metadata
             ) VALUES (
                 'claim:fixture','content:fixture','person:fixture','Synthetic percentage is ten',
                 'NUMERIC_STATISTIC','{}'::jsonb,true,
                 '{"speech_mode":"DIRECT_UTTERANCE","context_integrity":{"state":"CLEAR_AUTOMATIC"}}'::jsonb
             );
             INSERT INTO claim_text_provenance(
                 id,claim_id,content_id,person_id,selector_type,
                 quote_sha256,source_sha256,attribution_method,status,source_ref
             ) VALUES (
                 'provenance:fixture','claim:fixture','content:fixture','person:fixture',
                 'TEXT_QUOTE_HASH',repeat('a',64),repeat('b',64),
                 'SOURCE_QUOTE','APPROVED','{"url":"https://example.test/approved-quote"}'::jsonb
             );
             INSERT INTO evidence(id,canonical_url,source_type)
             VALUES ('evidence:fixture','https://example.test/official-evidence','PRIMARY_OFFICIAL');
             INSERT INTO claim_evidence_candidate(
                 claim_id,evidence_id,retrieval_method,retrieval_version,
                 relation_candidate,status
             ) VALUES (
                 'claim:fixture','evidence:fixture','fixture','fixture-v1','SUPPORT','APPROVED'
             );
             INSERT INTO evidence_observation(
                 id,evidence_id,observation_type,value_numeric,
                 extraction_method,extraction_version,status
             ) VALUES (
                 'observation:fixture','evidence:fixture','NUMERIC_VALUE',10,
                 'fixture','fixture-v1','APPROVED'
             );
             INSERT INTO verification_run(
                 id,claim_id,verification_kind,verification_version,
                 input_fingerprint,statement_cutoff,assessment,
                 evidence_ids,observation_ids
             ) VALUES
                 ('verify:collision','claim:fixture','DETERMINISTIC','fixture-v1',
                  repeat('c',64),'2026-09-21','SUPPORTED',
                  '["evidence:fixture"]'::jsonb,'["observation:fixture"]'::jsonb),
                 ('verify:valid','claim:fixture','DETERMINISTIC','fixture-v1',
                  repeat('d',64),'2026-09-21','SUPPORTED',
                  '["evidence:fixture"]'::jsonb,'["observation:fixture"]'::jsonb);
             INSERT INTO finding(
                 id,claim_id,verification_run_id,assessment,rationale,
                 publication_status,policy_version
             ) VALUES
                 ('finding:collision','claim:fixture','verify:collision',
                  'SUPPORTED','Synthetic rationale','POLICY_HOLD','fixture-policy-v1'),
                 ('finding:valid','claim:fixture','verify:valid',
                  'SUPPORTED','Synthetic rationale','POLICY_HOLD','fixture-policy-v1');
             INSERT INTO finding_evidence(finding_id,evidence_id,relation) VALUES
                 ('finding:collision','evidence:fixture','SUPPORT'),
                 ('finding:valid','evidence:fixture','SUPPORT');
             INSERT INTO review_event(id,entity_type,entity_id,action,actor_ref) VALUES
                 ('review:quote','CLAIM_TEXT_PROVENANCE','provenance:fixture','APPROVED','reviewer:fixture'),
                 ('review:evidence','CLAIM_EVIDENCE_CANDIDATE',
                  'claim:fixture|evidence:fixture|fixture-v1','APPROVED','reviewer:fixture'),
                 ('review:observation','EVIDENCE_OBSERVATION','observation:fixture',
                  'APPROVED','reviewer:fixture'),
                 ('review:collision','FINDING','finding:elsewhere',
                  'APPROVED','reviewer:other');
             """)
        cls.store = ReviewPublicationDecisionStore(cls.database)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _cmd([cls.pgctl, "-D", str(cls.pgdata), "-m", "fast", "-w", "stop"])
        finally:
            cls.tmp.cleanup()

    def finding_status(self, finding_id: str) -> str:
        return self.store.run("""
            SELECT publication_status FROM finding WHERE id=:'id'
        """, id=finding_id)

    def test_collided_review_id_does_not_publish_eligible_finding(self):
        self.assertFalse(self.store.publish_finding_with_review(
            finding_id="finding:collision", event_id="review:collision",
            actor_ref="reviewer:forged", reason="invalid approval",
        ))
        self.assertEqual(self.finding_status("finding:collision"), "POLICY_HOLD")

    def test_real_eligible_finding_publishes_only_with_matching_event(self):
        kwargs = dict(finding_id="finding:valid", event_id="review:valid",
                      actor_ref="reviewer:fixture", reason="reviewed")
        self.assertTrue(self.store.publish_finding_with_review(**kwargs))
        self.assertEqual(self.finding_status("finding:valid"), "PUBLISH")
        self.assertTrue(self.store.publish_finding_with_review(**kwargs))
        self.assertFalse(self.store.publish_finding_with_review(
            **{**kwargs, "actor_ref": "reviewer:forged"}
        ))
        self.assertFalse(self.store.publish_finding_with_review(
            **{**kwargs, "reason": "altered approval"}
        ))


if __name__ == "__main__":
    unittest.main()

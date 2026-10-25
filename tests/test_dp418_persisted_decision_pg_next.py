"""DP-418 private, real PostgreSQL decision CAS and attested replay fixtures."""

from __future__ import annotations

import concurrent.futures
import dataclasses
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_candidate_decision_store_pg import (  # noqa: E402
    StudioCandidateDecisionStorePg,
    candidate_decision_request,
)
from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    deterministic_match_run_id,
    deterministic_match_result_id,
)
from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    ReviewRole,
    ReviewStage,
    build_review_event,
)
from dichiarazioni_pubbliche.publication_safety import PublicationSafetyResult  # noqa: E402
from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    HighRiskDecision,
    HighRiskSignals,
)
from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority,
    provision_reviewer_credential,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRegistryStore, RightsSubject,
)


class PersistedDecisionPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_studio_capture_selectors_pg import (
            StudioCaptureSelectorPostgresTests,
        )

        cls.pg = StudioCaptureSelectorPostgresTests
        cls.pg.setUpClass()
        cls.run_id = deterministic_match_run_id("candidate:review", "d" * 64)
        try:
            cls.pg._sql(f"""
                INSERT INTO content_item(id, canonical_url, rights_status)
                VALUES ('content:review','https://fixture.invalid/review','CLEARED');
                INSERT INTO content_capture(id, content_id, observed_at, final_url,
                    content_sha256, retrieval_method, retrieval_version, rights_status)
                VALUES ('capture:review','content:review','2026-10-11T00:00:00Z',
                    'https://fixture.invalid/review',repeat('a',64),'fixture','v1','CLEARED');
                INSERT INTO passage(id, content_id, capture_id, selector_type,
                    start_char, end_char, text_sha256, private_text,
                    extraction_method, extraction_version)
                VALUES ('passage:review','content:review','capture:review','TEXT_POSITION',
                    0,8,repeat('b',64),'PRIVATE fixture text','fixture','v1');
                INSERT INTO statement_candidate(id,content_id,statement_text_hash,
                    normalized_statement,extraction_version)
                VALUES ('statement:review','content:review',repeat('c',64),'PRIVATE','v1');
                INSERT INTO statement_candidate_passage(statement_candidate_id,passage_id,content_id)
                VALUES ('statement:review','passage:review','content:review');
                INSERT INTO claim_candidate(id,statement_candidate_id,content_id,
                    normalized_claim,proposed_claim_type,extraction_version,metadata)
                VALUES ('candidate:review','statement:review','content:review',
                    'PRIVATE claim','HISTORICAL_CLAIM','v1',
                    '{{"parent_passage_id":"passage:review"}}');
                INSERT INTO claim_candidate(id,statement_candidate_id,content_id,
                    normalized_claim,proposed_claim_type,extraction_version,metadata)
                VALUES ('candidate:comparison','statement:review','content:review',
                    'PRIVATE target','HISTORICAL_CLAIM','v1',
                    '{{"parent_passage_id":"passage:review"}}');
                INSERT INTO candidate_match_run(id,claim_candidate_id,input_fingerprint,
                    status,result_count) VALUES
                    ('{cls.run_id}','candidate:review',repeat('d',64),'COMPLETED',0);
            """)
            cls.rights_subject = RightsSubject(
                source_family="SYNTHETIC_DP418", locator_kind="URL",
                locator_value="https://fixture.invalid/review",
                content_id="content:review",
            )
            cls.rights = PrivateRightsRegistryStore(cls.pg.dsn)
            cls.rights.record_rights(
                subject=cls.rights_subject, policy_version="dp418-fixture-v1",
                rights_status="CLEARED", rights_receipt_ref="fixture:reviewed",
                permitted_uses=("RESEARCH_CAPTURE_PRIVATE", "OMNIROUTE_MODEL_EXTRACTION_PRIVATE"),
                reviewed_at="2026-10-12T00:00:00Z",
                expires_at="2026-11-23T00:00:00Z", reviewer_ref="fixture:reviewer",
            )
            cls.store = StudioCandidateDecisionStorePg(cls.pg.dsn)
            cls.store.initialize()
        except Exception:
            cls.pg.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pg"):
            cls.pg.tearDownClass()

    def setUp(self):
        self.pg._sql("""
            TRUNCATE dp418_candidate_decision;
            UPDATE content_item SET rights_status='CLEARED' WHERE id='content:review';
            UPDATE content_capture SET rights_status='CLEARED', hold_status='NONE',
                status='CAPTURED' WHERE id='capture:review';
            UPDATE claim_candidate SET status='CANDIDATE',
                metadata='{"parent_passage_id":"passage:review"}' WHERE id='candidate:review';
            UPDATE candidate_match_run SET status='COMPLETED',result_count=0;
            DELETE FROM candidate_match_result;
        """)
        self.tmp = tempfile.TemporaryDirectory(prefix="dp418-review-authority-")
        self.root = Path(self.tmp.name) / "identity"
        self.identities = {
            name: provision_reviewer_credential(
                self.root,
                credential_id=name,
                actor_ref=f"reviewer:{name}",
                key_version="v1",
            )
            for name in ("alice", "bob")
        }
        self.authority = LocalFileReviewerIdentityAuthority(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def request(
        self,
        *,
        request_key="request:alice",
        decision="HOLD",
        expected_revision=0,
        actor="alice",
        **changes,
    ):
        return candidate_decision_request(
            candidate_id="candidate:review",
            run_id=self.run_id,
            input_fingerprint="d" * 64,
            passage_id="passage:review",
            capture_id="capture:review",
            capture_sha256="a" * 64,
            request_key=request_key,
            decision=decision,
            expected_revision=expected_revision,
            actor_ref=f"reviewer:{actor}",
            **changes,
        )

    def sign(self, request, actor):
        identity = self.identities[actor]
        event = build_review_event(
            record_id="dp418:" + request.candidate_id,
            record_version=request.record_version,
            stage=ReviewStage.PRIMARY,
            role=ReviewRole.DECISION_REVIEWER,
            action={
                "HOLD": "SUPERSEDED",
                "REJECT": "REJECTED",
                "REVIEW_CREATE": "APPROVED",
                "REVIEW_LINK": "APPROVED",
            }[request.decision],
            actor_ref=identity.actor_ref,
            credential_fingerprint=identity.credential_fingerprint,
            reviewed_at="2026-10-12T00:00:00+02:00",
            publication_safety=PublicationSafetyResult(
                disposition="ELIGIBLE",
                reason_codes=(),
                required_proofs=(),
                binding_sha256="a" * 64,
            ),
            high_risk=HighRiskDecision(
                disposition="STANDARD_REVIEW",
                reason_codes=(),
                signals=HighRiskSignals(
                    risk_classes=(), procedural_statuses=(), allegation_framing=False
                ),
                policy_decision_ref=None,
            ),
            high_risk_input_binding_sha256="b" * 64,
        )
        attestation = self.authority.issue(
            event, credential_id=actor, issued_at="2026-10-12T00:01:00+02:00"
        )
        return event, attestation.receipt_id

    def test_actual_pg_receipt_restart_replay_and_missing_identity_hold(self):
        request = self.request(decision="REVIEW_CREATE")
        self.assertEqual(
            self.store.record(
                request, authority=None, review_event=None, authority_receipt_id=None
            )["result_code"],
            "HELD_AUTHORITY",
        )
        self.assertEqual(self.pg_row_count(), 0)
        event, receipt = self.sign(request, "alice")
        first = self.store.record(
            request,
            authority=self.authority,
            review_event=event,
            authority_receipt_id=receipt,
            credential_id="alice",
        )
        self.assertEqual(first["result_code"], "CREATED")
        self.assertFalse(first["promotion_authority"])
        self.assertEqual(first["revision"], 1)
        restarted = StudioCandidateDecisionStorePg(self.pg.dsn)
        replay = restarted.record(
            request,
            authority=LocalFileReviewerIdentityAuthority(self.root),
            review_event=event,
            authority_receipt_id=receipt,
            credential_id="alice",
        )
        self.assertEqual(replay["result_code"], "REPLAY")
        self.assertEqual(replay["receipt_sha256"], first["receipt_sha256"])
        self.assertEqual(
            restarted.read("candidate:review", "request:alice")["receipt_sha256"],
            first["receipt_sha256"],
        )
        self.assertEqual(self.pg_row_count(), 1)

    def pg_row_count(self):
        raw = self.store.run("SELECT count(*) FROM dp418_candidate_decision;")
        return int(raw)

    def test_two_independent_reviewers_race_one_cas_winner(self):
        a = self.request(request_key="request:alice", actor="alice")
        b = self.request(request_key="request:bob", actor="bob")
        ae, ar = self.sign(a, "alice")
        be, br = self.sign(b, "bob")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    self.store.record,
                    r,
                    authority=self.authority,
                    review_event=ev,
                    authority_receipt_id=receipt,
                    credential_id=actor,
                )
                for r, ev, receipt, actor in ((a, ae, ar, "alice"), (b, be, br, "bob"))
            ]
            codes = [f.result(timeout=15)["result_code"] for f in futures]
        self.assertCountEqual(codes, ["CREATED", "REVISION_CONFLICT"])
        self.assertEqual(self.pg_row_count(), 1)

    def test_revoked_rights_cross_scope_and_revoked_reviewer_fail_closed(self):
        original = self.request()
        event, receipt = self.sign(original, "alice")
        forged = dataclasses.replace(original, passage_id="passage:03")
        self.assertEqual(
            self.store.record(
                forged,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "HELD_AUTHORITY",
        )
        self.pg._sql(
            "UPDATE content_capture SET rights_status='REVOKED' WHERE id='capture:review';"
        )
        self.assertEqual(
            self.store.record(
                original,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "HELD_SOURCE",
        )
        self.pg._sql(
            "UPDATE content_capture SET rights_status='CLEARED' WHERE id='capture:review';"
        )
        self.authority.revoke("alice")
        self.assertEqual(
            self.store.record(
                original,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "HELD_AUTHORITY",
        )
        self.assertEqual(self.pg_row_count(), 0)

    def test_immutable_persisted_receipt_even_privileged_update(self):
        request = self.request()
        event, receipt = self.sign(request, "alice")
        self.assertEqual(
            self.store.record(
                request,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "CREATED",
        )
        with self.assertRaises(RuntimeError):
            self.pg._sql("UPDATE dp418_candidate_decision SET decision='REJECT';")
        self.assertEqual(
            self.store.read("candidate:review", "request:alice")["decision"], "HOLD"
        )

    def test_postgresql_rights_writer_commits_while_reviewer_waits_for_row_lock(self):
        request = self.request(decision="REVIEW_CREATE")
        event, receipt = self.sign(request, "alice")
        writer = subprocess.Popen(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "--dbname", self.pg.dsn],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            writer.stdin.write("""
                BEGIN;
                UPDATE content_capture SET rights_status='REVOKED'
                    WHERE id='capture:review';
                SELECT 'LOCKED';
                SELECT pg_sleep(0.35);
                COMMIT;
            """)
            writer.stdin.close()
            self.assertEqual(writer.stdout.readline().strip(), "LOCKED")
            result = self.store.record(
                request,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )
            self.assertEqual(result["result_code"], "HELD_SOURCE")
            self.assertEqual(writer.wait(timeout=5), 0)
            self.assertEqual(self.pg_row_count(), 0)
        finally:
            if writer.poll() is None:
                writer.kill()
                writer.wait(timeout=5)
            writer.stdout.close()
            writer.stderr.close()

    def test_replay_conflict_with_same_key_and_no_stale_new_capture(self):
        request = self.request(decision="HOLD")
        event, receipt = self.sign(request, "alice")
        self.assertEqual(
            self.store.record(
                request,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "CREATED",
        )
        conflicting = self.request(decision="REJECT", expected_revision=1)
        changed_event, changed_receipt = self.sign(conflicting, "alice")
        self.assertEqual(
            self.store.record(
                conflicting,
                authority=self.authority,
                review_event=changed_event,
                authority_receipt_id=changed_receipt,
                credential_id="alice",
            )["result_code"],
            "IDEMPOTENCY_CONFLICT",
        )
        self.assertEqual(self.pg_row_count(), 1)
        self.pg._sql("""
            INSERT INTO content_capture(id, content_id, observed_at, final_url,
                content_sha256, retrieval_method, retrieval_version, rights_status)
            VALUES ('capture:newer','content:review','2026-10-12T00:00:00Z',
                'https://fixture.invalid/newer',repeat('e',64),'fixture','v1','CLEARED');
        """)
        try:
            self.assertEqual(
                self.store.record(
                    request,
                    authority=self.authority,
                    review_event=event,
                    authority_receipt_id=receipt,
                    credential_id="alice",
                )["result_code"],
                "HELD_SOURCE",
            )
            historical = self.store.read("candidate:review", request.request_key)
            self.assertTrue(historical["historical_only"])
            self.assertFalse(historical["promotion_authority"])
        finally:
            self.pg._sql("DELETE FROM content_capture WHERE id='capture:newer';")

    def test_link_requires_a_real_exact_duplicate_result_and_create_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "TARGET_INVALID"):
            self.request(decision="REVIEW_LINK")
        link = self.request(
            decision="REVIEW_LINK",
            target_type="CLAIM_CANDIDATE",
            target_id="candidate:comparison",
        )
        event, receipt = self.sign(link, "alice")
        self.assertEqual(
            self.store.record(
                link,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "HELD_SOURCE",
        )
        result_id = deterministic_match_result_id(
            self.run_id, "CLAIM_CANDIDATE", "candidate:comparison"
        )
        self.pg._sql(f"""
            INSERT INTO candidate_match_result (
                id,run_id,target_type,target_claim_candidate_id,rank,match_class,
                method,lexical_score,disposition)
            VALUES ('{result_id}','{self.run_id}','CLAIM_CANDIDATE',
                'candidate:comparison',1,'DUPLICATE_EXTRACTION',
                'EXACT_NORMALIZED',1.0,'HOLD');
            UPDATE candidate_match_run SET result_count=1 WHERE id='{self.run_id}';
        """)
        # An unapproved same-proposition/duplicate also blocks create intent.
        create = self.request(decision="REVIEW_CREATE", request_key="request:new")
        ev, rc = self.sign(create, "alice")
        self.assertEqual(
            self.store.record(
                create,
                authority=self.authority,
                review_event=ev,
                authority_receipt_id=rc,
                credential_id="alice",
            )["result_code"],
            "HELD_SOURCE",
        )
        self.assertEqual(
            self.store.record(
                link,
                authority=self.authority,
                review_event=event,
                authority_receipt_id=receipt,
                credential_id="alice",
            )["result_code"],
            "CREATED",
        )
        self.assertEqual(
            self.store.read("candidate:review", "request:alice")["target_id"],
            "candidate:comparison",
        )
        self.assertEqual(self.pg_row_count(), 1)


if __name__ == "__main__":
    unittest.main()

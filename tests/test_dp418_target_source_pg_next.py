"""DP418: real independent target source read from disposable canonical PostgreSQL."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_candidate_target_pg import (  # noqa: E402
    StudioCandidateTargetPg,
)
from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    MATCHING_VERSION,
    deterministic_match_result_id,
    deterministic_match_run_id,
    matching_input_fingerprint,
    rank_candidate_matches,
)
from dichiarazioni_pubbliche.studio_candidate_review_ui import (  # noqa: E402
    build_candidate_comparison_read_model,
)
from tests.test_candidate_matching import item  # noqa: E402
from tests.test_studio_candidate_review_handoff import MatchStore, PromotionContext  # noqa: E402


class CandidateTargetPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_studio_capture_selectors_pg import (
            StudioCaptureSelectorPostgresTests,
        )

        cls.fixture = StudioCaptureSelectorPostgresTests
        cls.fixture.setUpClass()
        try:
            cls.fixture._sql("""
                INSERT INTO statement_candidate (
                    id, content_id, statement_text_hash, normalized_statement, extraction_version
                ) VALUES ('statement:foreign', 'content:other', repeat('b', 64),
                    'SECRET FOREIGN WORDING', 'fixture');
                INSERT INTO statement_candidate_passage (
                    statement_candidate_id, passage_id, content_id
                ) VALUES ('statement:foreign', 'passage:03', 'content:other');
                INSERT INTO claim_candidate (
                    id, statement_candidate_id, content_id, normalized_claim,
                    proposed_claim_type, extraction_version, metadata
                ) VALUES
                   ('claimcandidate:target', 'statement:one', 'content:one',
                    'SECRET TARGET WORDS', 'HISTORICAL_CLAIM', 'fixture',
                    '{"parent_passage_id":"passage:01","secret":"SECRET METADATA"}'),
                   ('claimcandidate:foreign', 'statement:foreign', 'content:other',
                    'SECRET FOREIGN CLAIM', 'HISTORICAL_CLAIM', 'fixture',
                    '{"parent_passage_id":"passage:03"}');
                INSERT INTO person(id,canonical_name) VALUES
                    ('person:target', 'SECRET PERSON');
                INSERT INTO atomic_claim (
                    id, content_id, speaker_person_id, normalized_claim, claim_type
                ) VALUES ('claim:with-promotion', 'content:one', 'person:target',
                    'SECRET ATOMIC CLAIM', 'HISTORICAL_CLAIM');
                UPDATE claim_candidate
                  SET status='PROMOTED', promoted_claim_id='claim:with-promotion'
                  WHERE id='claimcandidate:target';
                INSERT INTO claim_candidate_promotion (
                    id, claim_candidate_id, target_claim_id, action,
                    provenance_channel, idempotency_key, actor_ref
                ) VALUES ('promotion:target','claimcandidate:target','claim:with-promotion',
                          'CREATED','WRITTEN','fixture:target', 'SECRET ACTOR');
                INSERT INTO claim_text_provenance (
                    id, claim_id, content_id, person_id, selector_type,
                    quote_sha256, attribution_method
                ) VALUES ('provenance:target','claim:with-promotion','content:one',
                          'person:target','TEXT_QUOTE_HASH',repeat('a',64),'SOURCE_QUOTE');
                CREATE ROLE dp418_reader LOGIN;
                GRANT USAGE ON SCHEMA public TO dp418_reader;
                GRANT SELECT ON content_item, content_capture, passage,
                    statement_candidate, statement_candidate_passage,
                    claim_candidate, claim_candidate_promotion,
                    atomic_claim, claim_text_provenance, claim_segment
                    TO dp418_reader;
            """)
        except Exception:
            cls.fixture.tearDownClass()
            raise
        cls.reader = StudioCandidateTargetPg(
            database_url=cls.fixture.dsn.replace("postgres@", "dp418_reader@")
        )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "fixture"):
            cls.fixture.tearDownClass()

    def tearDown(self):
        self.fixture._sql("""
            UPDATE claim_candidate SET metadata='{"parent_passage_id":"passage:01"}'
                WHERE id='claimcandidate:target';
            UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:one';
            UPDATE content_capture SET rights_status='UNKNOWN',hold_status='NONE',
                status='CAPTURED' WHERE id='capture:aaaaaa';
        """)

    def test_actual_candidate_readback_exact_content_capture_passage_and_privacy(self):
        row = self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")
        self.assertEqual(
            row,
            {
                "member_type": "CLAIM_CANDIDATE",
                "member_id": "claimcandidate:target",
                "content_id": "content:one",
                "passage_id": "passage:01",
                "capture_id": "capture:aaaaaa",
                "capture_sha256": "a" * 64,
                "rights_status": "UNKNOWN",
                "capture_status": "CAPTURED",
                "capture_hold_status": "NONE",
            },
        )
        self.assertEqual(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:foreign")[
                "passage_id"
            ],
            "passage:03",
        )
        self.assertNotIn("SECRET", json.dumps(row))
        self.assertNotIn("private_text", json.dumps(row))
        self.assertIsNone(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:missing")
        )
        self.assertIsNone(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:one")
        )  # no exact parent passage
        # Atomic provenance keys (provenance:target) are NOT Passage IDs.
        self.assertIsNone(
            self.reader.source_context("ATOMIC_CLAIM", "claim:with-promotion")
        )

    def test_forged_parent_passage_and_wrong_type_cannot_bind(self):
        try:
            self.fixture._sql("""
                UPDATE claim_candidate SET metadata='{"parent_passage_id":"passage:03"}'
                WHERE id='claimcandidate:target';
            """)
            self.assertIsNone(
                self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")
            )
            self.fixture._sql("""
                UPDATE claim_candidate SET metadata='{"parent_passage_id":"passage:02"}'
                WHERE id='claimcandidate:target';
            """)
            # Passage belongs to same Content but NOT the target Statement edge.
            self.assertIsNone(
                self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")
            )
        finally:
            self.fixture._sql("""
                UPDATE claim_candidate SET metadata='{"parent_passage_id":"passage:01"}'
                WHERE id='claimcandidate:target';
            """)
        self.assertIsNone(
            self.reader.source_context("ATOMIC_CLAIM", "claimcandidate:target")
        )
        self.assertIsNone(
            self.reader.source_context("CLAIM_CANDIDATE", "claim:with-promotion")
        )
        for typ, name in (
            ("UNTRUSTED", "claimcandidate:target"),
            ("CLAIM_CANDIDATE", "claimcandidate:target\nSELECT"),
        ):
            with self.subTest(typ=typ, name=name), self.assertRaises(ValueError):
                self.reader.source_context(typ, name)

    def test_current_rights_and_capture_hold_deny_false_cleared(self):
        # A legacy content-level APPROVED flag is not a license: no invented clearance.
        self.fixture._sql("""
            UPDATE content_item SET rights_status='APPROVED' WHERE id='content:one';
            UPDATE content_capture SET rights_status='CLEARED' WHERE id='capture:aaaaaa';
        """)
        self.assertEqual(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")[
                "rights_status"
            ],
            "UNKNOWN",
        )
        self.fixture._sql("""
            UPDATE content_item SET rights_status='CLEARED' WHERE id='content:one';
        """)
        self.assertEqual(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")[
                "rights_status"
            ],
            "CLEARED",
        )
        self.fixture._sql("""
            UPDATE content_capture SET rights_status='REVOKED',hold_status='RIGHTS_HOLD'
            WHERE id='capture:aaaaaa';
        """)
        revoked = self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")
        self.assertEqual(revoked["rights_status"], "REVOKED")
        self.assertEqual(revoked["capture_hold_status"], "RIGHTS_HOLD")
        self.fixture._sql("""
            UPDATE content_item SET rights_status='DENIED' WHERE id='content:one';
            UPDATE content_capture SET rights_status='CLEARED' WHERE id='capture:aaaaaa';
        """)
        self.assertEqual(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")[
                "rights_status"
            ],
            "DENIED",
        )

    def test_retention_and_candidate_state_changes_fail_closed(self):
        self.fixture._sql("""
            UPDATE content_capture SET status='PURGE_PENDING' WHERE id='capture:aaaaaa';
        """)
        self.assertIsNone(
            self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")
        )
        self.fixture._sql("""
            UPDATE content_capture SET status='CAPTURED' WHERE id='capture:aaaaaa';
            UPDATE claim_candidate SET status='HELD', promoted_claim_id=NULL
            WHERE id='claimcandidate:target';
        """)
        try:
            self.assertIsNone(
                self.reader.source_context("CLAIM_CANDIDATE", "claimcandidate:target")
            )
        finally:
            self.fixture._sql("""
                UPDATE claim_candidate SET status='PROMOTED',
                promoted_claim_id='claim:with-promotion'
                WHERE id='claimcandidate:target';
            """)

    def test_privileged_dsn_still_read_only_and_ambiguous_forgery_refused(self):
        privileged = StudioCandidateTargetPg(self.fixture.dsn)
        with self.assertRaisesRegex(
            RuntimeError, "DP418_TARGET_STORE_UNAVAILABLE"
        ) as ctx:
            privileged.run(
                "UPDATE content_item SET rights_status='CLEARED' WHERE id='content:one'"
            )
        self.assertNotIn("password", str(ctx.exception).lower())

        class AmbiguousTarget(StudioCandidateTargetPg):
            def run(self, sql, **variables):
                valid = self_fixture_row
                return json.dumps(valid) + "\n" + json.dumps(valid)

        self_fixture_row = {
            "member_type": "CLAIM_CANDIDATE",
            "member_id": "claimcandidate:target",
            "content_id": "content:one",
            "passage_id": "passage:01",
            "capture_id": "capture:aaaaaa",
            "capture_sha256": "a" * 64,
            "content_rights": "UNKNOWN",
            "capture_rights": "UNKNOWN",
            "capture_status": "CAPTURED",
            "capture_hold_status": "NONE",
        }
        with self.assertRaisesRegex(ValueError, "SOURCE_AMBIGUOUS"):
            AmbiguousTarget().source_context("CLAIM_CANDIDATE", "claimcandidate:target")

    def test_select_only_db_role_and_comparison_model_with_real_independent_target(
        self,
    ):
        with self.assertRaises(RuntimeError):
            self.reader.run(
                "UPDATE content_item SET rights_status='CLEARED' WHERE id='content:one'",
            )
        # A valid positive comparison now also needs independently persisted
        # Candidate→Statement→Passage→Capture lineage for the source candidate.
        self.fixture._sql("""
            INSERT INTO claim_candidate (
                id, statement_candidate_id, content_id, normalized_claim,
                proposed_claim_type, extraction_version, metadata
            ) VALUES ('candidate:1', 'statement:one', 'content:one',
                'Il primo evento fu registrato.', 'HISTORICAL_CLAIM', 'fixture',
                '{"parent_passage_id":"passage:01"}')
            ON CONFLICT (id) DO NOTHING;
        """)
        fake_match = MatchStore()
        fake_match.candidate = item(
            "CLAIM_CANDIDATE", "candidate:1", "Il primo evento fu registrato.",
            content_id="content:one", provenance_key="passage:01",
        )
        fake_match.targets = (
            item(
                "CLAIM_CANDIDATE",
                "claimcandidate:target",
                "Il primo evento fu registrato.",
                content_id="content:one",
                provenance_key="passage:01",
            ),
        )
        fake_match.fingerprint = matching_input_fingerprint(
            fake_match.candidate, fake_match.targets
        )
        fake_match.run_id = deterministic_match_run_id(
            "candidate:1", fake_match.fingerprint
        )
        result = rank_candidate_matches(fake_match.candidate, fake_match.targets)[0]
        fake_match.run = {
            "id": fake_match.run_id,
            "claim_candidate_id": "candidate:1",
            "matching_version": MATCHING_VERSION,
            "input_fingerprint": fake_match.fingerprint,
            "status": "COMPLETED",
            "result_count": 1,
        }
        fake_match.rows = (
            {
                "id": deterministic_match_result_id(
                    fake_match.run_id, "CLAIM_CANDIDATE", "claimcandidate:target"
                ),
                "rank": 1,
                "target_type": "CLAIM_CANDIDATE",
                "target_id": "claimcandidate:target",
                "match_class": result.match.match_class,
                "method": result.match.method,
                "matching_version": MATCHING_VERSION,
                "status": "CANDIDATE",
                "lexical_score": result.match.lexical_score,
                "disposition": result.disposition,
                "proposition_cluster_id": result.cluster_id,
                "supporting_features": list(result.supporting_features),
                "contradicting_features": list(result.contradicting_features),
            },
        )
        promotion_context = PromotionContext()
        promotion_context.data.update({
            "content_id": "content:one",
            "passages": [{
                **promotion_context.data["passages"][0],
                "passage_id": "passage:01",
                "capture_id": "capture:aaaaaa",
                "capture_sha256": "a" * 64,
            }],
        })
        packet = build_candidate_comparison_read_model(
            fake_match,
            promotion_context,
            self.reader,
            run_id=fake_match.run_id,
            claim_candidate_id="candidate:1",
        )
        self.assertEqual(len(packet["comparisons"]), 1)
        target = packet["comparisons"][0]
        self.assertEqual(target["source"]["capture_id"], "capture:aaaaaa")
        self.assertEqual(target["operator_status"], "BLOCKED_CANDIDATE_SOURCE_RIGHTS")
        self.assertIn("DP418_CANDIDATE_SOURCE_RIGHTS", packet["promotion_blockers"])
        self.assertFalse(target["comparison_usable"])
        self.assertFalse(packet["review_authority"])
        self.assertFalse(packet["promotion_authority"])
        self.assertNotIn("SECRET", json.dumps(packet))
        self.fixture._sql("""
            UPDATE content_item SET rights_status='CLEARED' WHERE id='content:one';
            UPDATE content_capture SET rights_status='CLEARED' WHERE id='capture:aaaaaa';
        """)
        reviewable = build_candidate_comparison_read_model(
            fake_match,
            promotion_context,
            self.reader,
            run_id=fake_match.run_id,
            claim_candidate_id="candidate:1",
        )
        self.assertEqual(
            reviewable["comparisons"][0]["operator_status"], "OPERATOR_COMPARE_PENDING"
        )
        self.assertTrue(reviewable["comparisons"][0]["comparison_usable"])
        self.assertFalse(reviewable["promotion_authority"])
        self.assertFalse(reviewable["comparisons"][0]["equivalence_approved"])

        class RevokedOnSecondRead(StudioCandidateTargetPg):
            reads = 0

            def source_context(self, member_type, member_id):
                self.reads += 1
                if self.reads == 3:
                    CandidateTargetPgTests.fixture._sql("""
                        UPDATE content_capture SET rights_status='REVOKED'
                        WHERE id='capture:aaaaaa';
                    """)
                return super().source_context(member_type, member_id)

        with self.assertRaisesRegex(ValueError, "DP418_COMPARISON_CHANGED_DURING_READ"):
            build_candidate_comparison_read_model(
                fake_match,
                promotion_context,
                RevokedOnSecondRead(self.reader.database_url),
                run_id=fake_match.run_id,
                claim_candidate_id="candidate:1",
            )


if __name__ == "__main__":
    unittest.main()

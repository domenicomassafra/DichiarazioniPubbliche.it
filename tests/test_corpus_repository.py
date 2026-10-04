import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.corpus_repository import (  # noqa: E402
    ClaimCandidateRecord,
    CollectionContentRecord,
    ContentCaptureRecord,
    INSERT_CLAIM_CANDIDATE_SQL_V1,
    INSERT_COLLECTION_CONTENT_SQL_V1,
    INSERT_CONTENT_CAPTURE_SQL_V1,
    INSERT_PASSAGE_SQL_V1,
    INSERT_RESEARCH_COLLECTION_SQL_V1,
    INSERT_STATEMENT_CANDIDATE_SQL_V1,
    PassageRecord,
    ResearchCollectionRecord,
    StatementCandidateRecord,
    deterministic_corpus_id,
    normalize_claim_candidate,
    normalize_statement_candidate,
    records_to_json,
)
from dichiarazioni_pubbliche.domain_vocabulary import ClaimType  # noqa: E402


HASH_A = hashlib.sha256(b"capture-a").hexdigest()
HASH_B = hashlib.sha256(b"statement-b").hexdigest()


class CorpusRepositoryTests(unittest.TestCase):
    def test_deterministic_id_is_stable_and_namespaced(self):
        a = deterministic_corpus_id("capture", "content:1", HASH_A)
        b = deterministic_corpus_id("capture", "content:1", HASH_A)
        c = deterministic_corpus_id("capture", "content:1", HASH_B)
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("capture:"))
        self.assertNotEqual(a, c)

    def test_content_capture_requires_hash_and_timezone_aware_observation(self):
        rec = ContentCaptureRecord(
            id="capture:1",
            content_id="content:1",
            observed_at="2026-09-29T09:00:00+02:00",
            final_url="https://example.org/a",
            content_sha256=HASH_A,
            retrieval_method="HTTP",
            retrieval_version="safe-fetch-v1",
        )
        self.assertEqual(rec.status, "CAPTURED")
        with self.assertRaisesRegex(ValueError, "TIMEZONE_REQUIRED"):
            ContentCaptureRecord(
                id="capture:bad-time",
                content_id="content:1",
                observed_at="2026-09-29T09:00:00",
                final_url="https://example.org/a",
                content_sha256=HASH_A,
                retrieval_method="HTTP",
                retrieval_version="safe-fetch-v1",
            )
        with self.assertRaisesRegex(ValueError, "INVALID_SHA256"):
            ContentCaptureRecord(
                id="capture:bad-hash",
                content_id="content:1",
                observed_at="2026-09-29T09:00:00+02:00",
                final_url="https://example.org/a",
                content_sha256="not-a-hash",
                retrieval_method="HTTP",
                retrieval_version="safe-fetch-v1",
            )

    def test_passage_requires_exactly_one_provenance_path(self):
        written = PassageRecord(
            id="passage:written",
            content_id="content:1",
            capture_id="capture:1",
            selector_type="TEXT_POSITION",
            start_char=10,
            end_char=30,
            text_sha256=HASH_A,
            extraction_method="READABILITY",
            extraction_version="v1",
        )
        self.assertEqual(written.capture_id, "capture:1")
        media = PassageRecord(
            id="passage:media",
            content_id="content:2",
            canonical_segment_id="canonical:1",
            selector_type="MEDIA_SEGMENT_REF",
            text_sha256=HASH_A,
            extraction_method="CANONICAL_TRANSCRIPT",
            extraction_version="v1",
        )
        self.assertEqual(media.canonical_segment_id, "canonical:1")
        with self.assertRaisesRegex(ValueError, "EXACTLY_ONE_SOURCE"):
            PassageRecord(
                id="passage:none",
                content_id="content:1",
                selector_type="TEXT_POSITION",
                start_char=1,
                end_char=2,
                text_sha256=HASH_A,
                extraction_method="READABILITY",
                extraction_version="v1",
            )
        with self.assertRaisesRegex(ValueError, "EXACTLY_ONE_SOURCE"):
            PassageRecord(
                id="passage:both",
                content_id="content:1",
                capture_id="capture:1",
                canonical_segment_id="canonical:1",
                selector_type="MEDIA_SEGMENT_REF",
                text_sha256=HASH_A,
                extraction_method="TEST",
                extraction_version="v1",
            )

    def test_statement_candidate_requires_nonempty_passage_provenance(self):
        rec = normalize_statement_candidate(
            {
                "id": "statement:1",
                "content_id": "content:1",
                "passage_ids": ["passage:1"],
                "statement_text_hash": HASH_B,
                "normalized_statement": "Una dichiarazione attribuita.",
                "extraction_version": "statement-v1",
            }
        )
        self.assertIsInstance(rec, StatementCandidateRecord)
        self.assertEqual(rec.passage_ids, ("passage:1",))
        with self.assertRaisesRegex(ValueError, "PASSAGE_IDS_REQUIRED"):
            StatementCandidateRecord(
                id="statement:bad",
                content_id="content:1",
                passage_ids=(),
                statement_text_hash=HASH_B,
                normalized_statement="x",
                extraction_version="v1",
            )

    def test_claim_candidate_is_not_atomic_claim_and_fails_closed(self):
        rec = ClaimCandidateRecord(
            id="claim-candidate:1",
            statement_candidate_id="statement:1",
            content_id="content:1",
            normalized_claim="Il dato è 10.",
            proposed_claim_type=ClaimType.NUMERIC_STATISTIC.value,
            extraction_version="claim-candidate-v1",
        )
        self.assertEqual(rec.status, "CANDIDATE")
        self.assertIsNone(rec.promoted_claim_id)
        with self.assertRaisesRegex(ValueError, "PROMOTION_STATE_INVALID"):
            ClaimCandidateRecord(
                id="claim-candidate:bad-promotion",
                statement_candidate_id="statement:1",
                content_id="content:1",
                normalized_claim="Il dato è 10.",
                proposed_claim_type=ClaimType.NUMERIC_STATISTIC.value,
                extraction_version="v1",
                status="PROMOTED",
            )
        with self.assertRaisesRegex(ValueError, "NON_FACTUAL_NOT_CHECK_WORTHY"):
            ClaimCandidateRecord(
                id="claim-candidate:bad-value",
                statement_candidate_id="statement:1",
                content_id="content:1",
                normalized_claim="È una scelta pessima.",
                proposed_claim_type=ClaimType.VALUE_JUDGMENT.value,
                extraction_version="v1",
                check_worthy=True,
            )

    def test_normalizers_reject_unknown_fields(self):
        data = {
            "id": "claim-candidate:1",
            "statement_candidate_id": "statement:1",
            "content_id": "content:1",
            "normalized_claim": "Il dato è 10.",
            "proposed_claim_type": ClaimType.NUMERIC_STATISTIC.value,
            "extraction_version": "v1",
            "political_score": 99,
        }
        with self.assertRaisesRegex(ValueError, "UNKNOWN_FIELDS"):
            normalize_claim_candidate(data)

    def test_private_record_json_is_deterministic(self):
        collection = ResearchCollectionRecord(
            id="research:garlasco",
            slug="garlasco",
            name="Garlasco",
            scope_text="Corpus pilota delimitato.",
            policy_version="research-collection-v1",
        )
        member = CollectionContentRecord(
            collection_id=collection.id,
            content_id="content:1",
            inclusion_method="MANUAL",
            inclusion_version="v1",
        )
        payload1 = records_to_json([collection, member])
        payload2 = records_to_json([collection, member])
        self.assertEqual(payload1, payload2)
        self.assertIn("research:garlasco", payload1)

    def test_capture_replay_identity_ignores_mutable_lifecycle_state(self):
        existing = INSERT_CONTENT_CAPTURE_SQL_V1.split("existing AS (", 1)[1].split(")\nSELECT CASE", 1)[0]
        for field in (
            "archive_status", "hold_status", "body_purged_at", "purge_receipt",
            "purge_reason", "status = :'status'",
        ):
            self.assertNotIn(field, existing)
        for immutable in (
            "content_id = :'content_id'", "content_sha256 = :'content_sha256'",
            "final_url = :'final_url'", "retrieval_method = :'retrieval_method'",
            "retrieval_version = :'retrieval_version'",
        ):
            self.assertIn(immutable, existing)

    def test_repository_sql_distinguishes_insert_replay_and_conflict(self):
        for sql in (
            INSERT_CONTENT_CAPTURE_SQL_V1,
            INSERT_PASSAGE_SQL_V1,
            INSERT_RESEARCH_COLLECTION_SQL_V1,
            INSERT_COLLECTION_CONTENT_SQL_V1,
            INSERT_STATEMENT_CANDIDATE_SQL_V1,
            INSERT_CLAIM_CANDIDATE_SQL_V1,
        ):
            with self.subTest(sql=sql[:48]):
                self.assertIn("ON CONFLICT", sql)
                self.assertIn("existing AS (", sql)
                self.assertIn("'INSERTED'", sql)
                self.assertIn("'EXISTING'", sql)
                self.assertIn("'CONFLICT'", sql)

    def test_candidate_replay_identity_ignores_mutable_review_and_promotion_state(self):
        statement_existing = INSERT_STATEMENT_CANDIDATE_SQL_V1.split("existing AS (", 1)[1].split(")\nSELECT CASE", 1)[0]
        self.assertNotIn("candidate.status = :'status'", statement_existing)

        claim_existing = INSERT_CLAIM_CANDIDATE_SQL_V1.split("existing AS (", 1)[1].split(")\nSELECT CASE", 1)[0]
        self.assertNotIn("status = :'status'", claim_existing)
        self.assertNotIn("promoted_claim_id IS NOT DISTINCT", claim_existing)
        for immutable in (
            "statement_candidate_id = :'statement_candidate_id'",
            "content_id = :'content_id'",
            "normalized_claim = :'normalized_claim'",
            "proposed_claim_type = :'proposed_claim_type'",
            "claim_type_version = :'claim_type_version'",
        ):
            self.assertIn(immutable, claim_existing)

    def test_statement_sql_links_only_passages_from_same_content(self):
        self.assertIn(
            "JOIN passage p ON p.id = passage_id.value AND p.content_id = inserted.content_id",
            INSERT_STATEMENT_CANDIDATE_SQL_V1,
        )
        self.assertIn("statement_candidate_passage", INSERT_STATEMENT_CANDIDATE_SQL_V1)


if __name__ == "__main__":
    unittest.main()

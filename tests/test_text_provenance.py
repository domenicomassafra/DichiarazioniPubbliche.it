import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402
from dichiarazioni_pubbliche.text_provenance import (  # noqa: E402
    TEXT_PROVENANCE_VERSION,
    make_text_provenance_candidate,
)


class CaptureStore(QueueRuntimeStore):
    def __init__(self):
        self.sql = ""
        self.variables = {}

    def run(self, sql, **variables):
        self.sql = sql
        self.variables = variables
        return "true"


class TextProvenanceTests(unittest.TestCase):
    def candidate(self, **overrides):
        values = {
            "claim_id": "claim:text:a",
            "content_id": "content:text:a",
            "person_id": "person:a",
            "selector_type": "TEXT_QUOTE_HASH",
            "quote_sha256": "a" * 64,
            "source_sha256": "b" * 64,
            "attribution_method": "SOURCE_QUOTE",
            "source_ref": {"url": "https://example.test/article"},
        }
        values.update(overrides)
        return make_text_provenance_candidate(**values)

    def test_candidate_is_deterministic_and_stores_no_quote_body(self):
        left = self.candidate()
        right = self.candidate()
        self.assertEqual(left.candidate_id, right.candidate_id)
        self.assertEqual(left.attribution_version, TEXT_PROVENANCE_VERSION)
        self.assertFalse(hasattr(left, "quote"))

    def test_hash_and_position_validation_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "QUOTE_SHA256_INVALID"):
            self.candidate(quote_sha256="not-a-hash")
        with self.assertRaisesRegex(ValueError, "POSITION_REQUIRED"):
            self.candidate(selector_type="TEXT_POSITION_HASH")
        with self.assertRaisesRegex(ValueError, "POSITION_PAIR_REQUIRED"):
            self.candidate(start_char=10)
        with self.assertRaisesRegex(ValueError, "POSITION_INVALID"):
            self.candidate(start_char=10, end_char=5)

    def test_insert_requires_claim_content_and_person_match_in_sql(self):
        store = CaptureStore()
        candidate = self.candidate()
        self.assertTrue(
            store.insert_claim_text_provenance(
                candidate_id=candidate.candidate_id,
                claim_id=candidate.claim_id,
                content_id=candidate.content_id,
                person_id=candidate.person_id,
                selector_type=candidate.selector_type,
                quote_sha256=candidate.quote_sha256,
                source_sha256=candidate.source_sha256,
                start_char=candidate.start_char,
                end_char=candidate.end_char,
                attribution_method=candidate.attribution_method,
                attribution_version=candidate.attribution_version,
                source_ref=candidate.source_ref,
            )
        )
        self.assertIn("claim.content_id = :'content_id'", store.sql)
        self.assertIn("claim.speaker_person_id = :'person_id'", store.sql)
        self.assertIn("'CANDIDATE'", store.sql)
        self.assertIn("OR EXISTS(SELECT 1 FROM existing)", store.sql)

    def test_approval_is_atomic_with_review_ledger(self):
        store = CaptureStore()
        self.assertTrue(
            store.approve_claim_text_provenance_with_review(
                candidate_id="text-provenance:a",
                event_id="review:a",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("'CLAIM_TEXT_PROVENANCE'", store.sql)
        self.assertIn("SET status = 'APPROVED'", store.sql)
        self.assertIn("INSERT INTO review_event", store.sql)
        self.assertIn("provenance.person_id = claim.speaker_person_id", store.sql)
        self.assertLess(store.sql.index("logged AS"), store.sql.index("changed AS"))
        self.assertIn("FROM reviewable", store.sql)


if __name__ == "__main__":
    unittest.main()

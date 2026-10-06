import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.curated_written_intake import (  # noqa: E402
    apply_curated_written_batch,
    apply_curated_written_batch_via_promotion,
    prepare_curated_written_batch,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


def fixture_payload():
    return {
        "batch_id": "test-batch",
        "extraction_model": "test-model",
        "extraction_version": "test-v1",
        "contents": [
            {
                "id": "content:test:one",
                "source": {
                    "id": "source:test",
                    "name": "Test Source",
                    "url": "https://example.test/",
                },
                "url": "https://example.test/article",
                "title": "Test article",
                "published_at": "2026-09-28T12:00:00+02:00",
                "person_id": "person:test",
                "metadata": {"topic": "test"},
                "claims": [
                    {
                        "id": "claim:test:one",
                        "normalized_claim": "A test historical claim.",
                        "claim_type": "HISTORICAL_CLAIM",
                        "statement_date": "2026-09-28",
                        "check_worthy": True,
                        "quote_text": "Exact source quote.",
                        "metadata": {"assertion_kind": "factual"},
                    }
                ],
            }
        ],
    }


def promotion_ready_payload():
    payload = fixture_payload()
    content = payload["contents"][0]
    content["promotion_capture"] = {
        "id": "capture:test:one",
        "observed_at": "2026-09-28T12:05:00+02:00",
        "final_url": "https://example.test/article",
        "content_sha256": hashlib.sha256(b"whole captured article").hexdigest(),
        "retrieval_method": "CURATED_CAPTURE",
        "retrieval_version": "v1",
        "retention_class": "DURABLE_PROVENANCE",
    }
    claim = content["claims"][0]
    claim["quote_start_char"] = 10
    claim["quote_end_char"] = 29
    return payload


class FakePromotionStore:
    def __init__(self, *, duplicate_target=True):
        self.calls = []
        self.duplicate_target = duplicate_target
        self.last_candidate_id = None
        self.candidate_metadata = {}

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        if "INSERT INTO source" in sql:
            return "inserted"
        if "INSERT INTO content_item" in sql:
            return "inserted"
        if "INSERT INTO content_capture" in sql:
            return "INSERTED"
        if "INSERT INTO passage (" in sql:
            return "INSERTED"
        if "INSERT INTO statement_candidate (" in sql:
            return "INSERTED"
        if "INSERT INTO claim_candidate (" in sql:
            self.last_candidate_id = variables["id"]
            self.candidate_metadata = json.loads(variables["metadata"])
            return "INSERTED"
        if "SET status='APPROVED'" in sql:
            return "APPROVED"
        if "'CLAIM_CANDIDATE'" in sql and "review_event" in sql:
            return "APPROVED"
        raise AssertionError(f"unexpected SQL: {sql[:100]}")

    def context(self, candidate_id):
        self.calls.append(("context", {"candidate_id": candidate_id}))
        return {
            "candidate_id": candidate_id,
            "candidate_status": "CANDIDATE",
            "content_id": "content:test:one",
            "normalized_claim": "A test historical claim.",
            "proposed_claim_type": "HISTORICAL_CLAIM",
            "claim_type_version": "atomic-claim-v1",
            "temporal_scope": {"statement_date": "2026-09-28"},
            "check_worthy": True,
            "extraction_model": "test-model",
            "extraction_version": "test-v1",
            "candidate_metadata": dict(self.candidate_metadata),
            "promoted_claim_id": None,
            "statement_candidate_id": "statement:compat",
            "statement_status": "APPROVED",
            "statement_reviewed": True,
            "claim_candidate_reviewed": True,
            "speaker_person_id": "person:test",
            "speaker_is_public": True,
            "statement_text_hash": hashlib.sha256(b"Exact source quote.").hexdigest(),
            "statement_at": None,
            "attribution_method": "SOURCE_QUOTE",
            "canonical_url": "https://example.test/article",
            "title": "Test article",
            "published_at": "2026-09-28T12:00:00+02:00",
            "passage_count": 1,
            "written_count": 1,
            "media_count": 0,
            "passages": [{
                "passage_id": "passage:compat",
                "selector_type": "TEXT_POSITION",
                "start_char": 10,
                "end_char": 29,
                "text_sha256": hashlib.sha256(b"Exact source quote.").hexdigest(),
                "private_text": "Exact source quote.",
                "capture_id": "capture:test:one",
                "capture_sha256": hashlib.sha256(b"whole captured article").hexdigest(),
                "capture_final_url": "https://example.test/article",
                "capture_status": "CAPTURED",
                "capture_hold_status": "NONE",
                "canonical_segment_id": None,
                "segment_status": None,
                "segment_publication_blocked": None,
                "segment_speaker_person_id": None,
            }],
            "duplicate_target_ids": ["claim:test:one"] if self.duplicate_target else [],
            "existing_promotion": None,
        }

    def link_existing(self, **variables):
        self.calls.append(("link_existing", variables))
        return "LINKED_EXISTING"

    def create_written(self, **variables):
        self.calls.append(("create_written", variables))
        return "CREATED"

    def create_media(self, **variables):
        raise AssertionError("curated written compatibility must not call media promotion")


class FakeStore(QueueRuntimeStore):
    def __init__(self):
        self.calls = []

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        if "INSERT INTO source" in sql:
            return "inserted"
        if "INSERT INTO content_item" in sql:
            return "inserted"
        if "INSERT INTO atomic_claim" in sql:
            return "inserted"
        return "true"

    def insert_claim_text_provenance(self, **kwargs):
        self.calls.append(("provenance", kwargs))
        return True

    def approve_claim_text_provenance_with_review(self, **kwargs):
        self.calls.append(("approve", kwargs))
        return True


class CuratedWrittenIntakeTests(unittest.TestCase):
    def test_prepare_hashes_quote_and_does_not_retain_body(self):
        batch = prepare_curated_written_batch(fixture_payload())
        claim = batch.contents[0].claims[0]
        self.assertEqual(len(claim.quote_sha256), 64)
        self.assertFalse(hasattr(claim, "quote_text"))
        self.assertEqual(claim.private_quote_text, "Exact source quote.")
        self.assertTrue(claim.provenance_id.startswith("text-provenance:"))

    def test_value_judgment_must_not_be_check_worthy(self):
        payload = fixture_payload()
        payload["contents"][0]["claims"][0]["claim_type"] = "VALUE_JUDGMENT"
        with self.assertRaisesRegex(ValueError, "NON_FACTUAL_NOT_CHECK_WORTHY"):
            prepare_curated_written_batch(payload)

    def test_duplicate_claim_ids_fail_before_mutation(self):
        payload = fixture_payload()
        payload["contents"][0]["claims"].append(
            dict(payload["contents"][0]["claims"][0])
        )
        with self.assertRaisesRegex(ValueError, "CLAIM_ID_DUPLICATE"):
            prepare_curated_written_batch(payload)

    def test_receipt_contains_hash_but_no_quote_body(self):
        batch = prepare_curated_written_batch(fixture_payload())
        receipt = apply_curated_written_batch(
            FakeStore(), batch, actor_ref="reviewer", approve_attribution=True
        )
        encoded = repr(receipt)
        self.assertNotIn("Exact source quote", encoded)
        claim = receipt["contents"][0]["claims"][0]
        self.assertEqual(claim["provenance_status"], "APPROVED")
        self.assertEqual(len(claim["quote_sha256"]), 64)


    def test_promotion_ready_prepare_requires_real_capture_hash_and_quote_offsets(self):
        batch = prepare_curated_written_batch(promotion_ready_payload())
        content = batch.contents[0]
        claim = content.claims[0]
        self.assertIsNotNone(content.promotion_capture)
        self.assertEqual(len(content.promotion_capture.content_sha256), 64)
        self.assertEqual((claim.quote_start_char, claim.quote_end_char), (10, 29))
        self.assertFalse(hasattr(claim, "quote_text"))
        self.assertEqual(claim.private_quote_text, "Exact source quote.")

    def test_promotion_adapter_refuses_legacy_manifest_before_mutation(self):
        batch = prepare_curated_written_batch(fixture_payload())
        store = FakePromotionStore()
        with self.assertRaisesRegex(ValueError, "CURATED_PROMOTION_CAPTURE_REQUIRED"):
            apply_curated_written_batch_via_promotion(store, batch, actor_ref="reviewer")
        self.assertEqual(store.calls, [])

    def test_promotion_ready_compatibility_links_existing_direct_claim_without_duplicate(self):
        batch = prepare_curated_written_batch(promotion_ready_payload())
        store = FakePromotionStore(duplicate_target=True)
        receipt = apply_curated_written_batch_via_promotion(store, batch, actor_ref="reviewer")
        claim = receipt["contents"][0]["claims"][0]
        self.assertEqual(
            store.candidate_metadata["context_integrity"]["state"],
            "APPROVED_CURATED",
        )
        wording = store.candidate_metadata["wording"]
        self.assertEqual(
            wording["source_occurrence"]["wording_type"],
            "VERBATIM_ORIGINAL",
        )
        self.assertEqual(wording["source_occurrence"]["language"], "it")
        self.assertEqual(
            wording["source_provenance"]["capture_id"],
            "capture:test:one",
        )
        self.assertEqual(
            wording["source_provenance"]["selector_type"],
            "TEXT_POSITION",
        )
        self.assertEqual(receipt["mode"], "CLAIM_CANDIDATE_PROMOTION_V1")
        self.assertEqual(claim["legacy_requested_claim_id"], "claim:test:one")
        self.assertEqual(claim["target_claim_id"], "claim:test:one")
        self.assertEqual(claim["promotion_action"], "LINKED_EXISTING")
        self.assertTrue(any(call[0] == "link_existing" for call in store.calls if isinstance(call[0], str)))
        self.assertFalse(any(call[0] == "create_written" for call in store.calls if isinstance(call[0], str)))

    def test_promotion_ready_new_record_uses_written_promotion_seam(self):
        batch = prepare_curated_written_batch(promotion_ready_payload())
        store = FakePromotionStore(duplicate_target=False)
        receipt = apply_curated_written_batch_via_promotion(store, batch, actor_ref="reviewer")
        claim = receipt["contents"][0]["claims"][0]
        self.assertEqual(
            store.candidate_metadata["context_integrity"]["state"],
            "APPROVED_CURATED",
        )
        self.assertEqual(claim["promotion_action"], "CREATED")
        self.assertEqual(claim["promotion_reason_code"], "PROMOTION_CREATED")
        self.assertTrue(str(claim["target_claim_id"]).startswith("claim:promoted:"))
        self.assertTrue(any(call[0] == "create_written" for call in store.calls if isinstance(call[0], str)))

    def test_curated_foreign_language_is_preserved_in_source_and_content_metadata(self):
        payload = promotion_ready_payload()
        payload["contents"][0]["language"] = "en"
        batch = prepare_curated_written_batch(payload)
        self.assertEqual(batch.contents[0].language, "en")
        store = FakePromotionStore(duplicate_target=True)
        apply_curated_written_batch_via_promotion(
            store,
            batch,
            actor_ref="reviewer",
        )
        wording = store.candidate_metadata["wording"]
        self.assertEqual(wording["source_occurrence"]["language"], "en")
        self.assertEqual(
            wording["source_provenance"]["start_char"],
            10,
        )
        source_call = next(
            call
            for call in store.calls
            if isinstance(call[0], str) and "INSERT INTO source" in call[0]
        )
        content_call = next(
            call
            for call in store.calls
            if isinstance(call[0], str) and "INSERT INTO content_item" in call[0]
        )
        self.assertEqual(source_call[1]["language"], "en")
        self.assertEqual(content_call[1]["language"], "en")

    def test_promotion_capture_requires_offsets_but_legacy_direct_does_not(self):
        payload = promotion_ready_payload()
        del payload["contents"][0]["claims"][0]["quote_start_char"]
        del payload["contents"][0]["claims"][0]["quote_end_char"]
        with self.assertRaisesRegex(ValueError, "CURATED_PROMOTION_QUOTE_POSITION_REQUIRED"):
            prepare_curated_written_batch(payload)
        legacy = prepare_curated_written_batch(fixture_payload())
        self.assertIsNone(legacy.contents[0].promotion_capture)



if __name__ == "__main__":
    unittest.main()

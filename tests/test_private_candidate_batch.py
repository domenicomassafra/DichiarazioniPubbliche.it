import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.private_candidate_batch import (
    VERSION, MODEL_USE, CandidateBatch, CandidateBatchItem, load_candidate_batch,
    preflight_candidate_batch, require_private_passage_state,
)
from test_capture_authorization import record

ITEM = CandidateBatchItem(
    passage_id="passage:reviewed",
    content_id="content:reviewed",
    capture_id="capture:reviewed",
    passage_sha256="a" * 64,
    canonical_url="https://example.test/reviewed",
    source_family="REPORTING",
    rights_record_id="private-rights:reviewed",
)
BATCH = CandidateBatch("research:reviewed", (ITEM,), "b" * 64)


def passage_state(**changes):
    result = dict(
        passage_id=ITEM.passage_id,
        content_id=ITEM.content_id,
        capture_id=ITEM.capture_id,
        passage_sha256=ITEM.passage_sha256,
        capture_status="CAPTURED",
        capture_hold_status="NONE",
        capture_rights_status="CLEARED",
        capture_retention_class="EPHEMERAL",
        body_ref=True,
    )
    result.update(changes)
    return result


class FakeCapture:
    def __init__(self):
        self.collection_status = "ACTIVE"
        self.relevance_allowed = True

    def require_current_ingestion_relevance(self, *, content_ref, canonical_url):
        if not self.relevance_allowed:
            raise RuntimeError("INGESTION_RELEVANCE_STALE")
        return object()

    def read_research_capture_context(self, collection_id, content_id):
        return dict(
            collection_id=collection_id,
            collection_status=self.collection_status,
            membership_status="INCLUDED",
            capture_authorized=True,
            content_id=content_id,
            canonical_url=ITEM.canonical_url,
            accepted_discovery_hits=1,
        )

    def read_operator_capture_content_state(self, content_id):
        return dict(
            id=content_id,
            canonical_url=ITEM.canonical_url,
            rights_status="CLEARED",
            inactive_collection_count=0,
            forbidden_membership_count=0,
        )


class FakeCandidate:
    def __init__(self):
        self.state = passage_state()

    def read_operator_passage_state(self, passage_id):
        return self.state


class FakeRights:
    def __init__(self):
        self.current = record(
            content_id=ITEM.content_id,
            locator_value=ITEM.canonical_url,
            permitted_uses=("RESEARCH_CAPTURE_PRIVATE", MODEL_USE),
        )

    def read_current(self, subject):
        return self.current


class CandidateAuthorizationTests(unittest.TestCase):
    def test_manifest_identity_hash_and_hard_bounds(self):
        raw = {
            "version": VERSION,
            "collection_id": BATCH.collection_id,
            "items": [vars(ITEM)],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch.json"
            path.write_text(json.dumps(raw))
            first = load_candidate_batch(path)
            self.assertEqual(first.items, BATCH.items)
            self.assertEqual(first.sha256, load_candidate_batch(path).sha256)
            self.assertEqual(len(first.sha256), 64)
            for changed in (
                {**raw, "items": []},
                {**raw, "items": [vars(ITEM)] * 17},
                {**raw, "items": [vars(ITEM), vars(ITEM)]},
                {**raw, "items": [{**vars(ITEM), "passage_sha256": "wrong"}]},
                {**raw, "items": [{**vars(ITEM), "canonical_url": "http://example.test"}]},
                {**raw, "items": [{**vars(ITEM), "approved": True}]},
                {**raw, "version": "unknown"},
            ):
                with self.subTest(changed=changed):
                    path.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError):
                        load_candidate_batch(path)

    def test_passage_capture_rights_hold_and_hash_gates(self):
        require_private_passage_state(passage_state(), ITEM)
        for value in (
            None,
            passage_state(content_id="content:wrong"),
            passage_state(capture_id="capture:wrong"),
            passage_state(passage_sha256="0" * 64),
            passage_state(capture_status="QUARANTINED"),
            passage_state(capture_hold_status="RIGHTS_HOLD"),
            passage_state(capture_rights_status="UNKNOWN"),
            passage_state(capture_retention_class="POLICY_PENDING"),
            passage_state(body_ref=False),
        ):
            with self.subTest(row=value):
                with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                    require_private_passage_state(value, ITEM)

    def test_preflight_no_provider_and_revalidation_deny_paused_or_revoked(self):
        capture, candidate, rights = FakeCapture(), FakeCandidate(), FakeRights()
        guards = preflight_candidate_batch(
            BATCH, capture_store=capture, candidate_store=candidate, rights_store=rights
        )
        self.assertEqual(len(guards), 1)
        guards[0]()
        capture.collection_status = "PAUSED"
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "COLLECTION_NOT_ACTIVE"):
            guards[0]()
        capture.collection_status = "ACTIVE"
        rights.current = replace(rights.current, rights_status="REVOKED")
        with self.assertRaises(PrivateCaptureAuthorizationBlocked):
            guards[0]()
        rights.current = replace(rights.current, rights_status="CLEARED",
                                 permitted_uses=("RESEARCH_CAPTURE_PRIVATE",))
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "MODEL_USE_NOT_AUTHORIZED"):
            guards[0]()

    def test_single_passage_provenance_drift_blocks_before_model(self):
        capture, candidate, rights = FakeCapture(), FakeCandidate(), FakeRights()
        guards = preflight_candidate_batch(
            BATCH, capture_store=capture, candidate_store=candidate, rights_store=rights
        )
        candidate.state = passage_state(capture_hold_status="PRIVACY_HOLD")
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "CAPTURE_HELD"):
            guards[0]()

    def test_superseded_ingestion_relevance_halts_model_processing(self):
        capture, candidate, rights = FakeCapture(), FakeCandidate(), FakeRights()
        (guard,) = preflight_candidate_batch(
            BATCH, capture_store=capture, candidate_store=candidate, rights_store=rights,
        )
        capture.relevance_allowed = False
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "RELEVANCE_MISSING_OR_STALE"
        ):
            guard()


if __name__ == "__main__":
    unittest.main()

# ruff: noqa: E402 -- test suite inserts the local poc package before imports.
import hashlib
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
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, STDLIB_HTML_PARSER_VERSION
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
_BATCH_BODY = {"version": VERSION, "collection_id": "research:reviewed", "items": [vars(ITEM)]}
BATCH = CandidateBatch(
    "research:reviewed", (ITEM,),
    hashlib.sha256(json.dumps(_BATCH_BODY, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")).hexdigest(),
)


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
            accepted_discovery_groups=[{"source_family": ITEM.source_family, "hit_count": 1}],
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
    def test_operator_immutable_capture_binding_requires_real_bytes_and_exact_selector(self):
        body = b"Official captured source passage."
        capture_sha = hashlib.sha256(body).hexdigest()
        passage_text = body.decode("utf-8")
        passage_sha = hashlib.sha256(passage_text.encode("utf-8")).hexdigest()
        item = replace(ITEM, passage_sha256=passage_sha)
        batch = CandidateBatch(BATCH.collection_id, (item,), "")
        payload = {"version": VERSION, "collection_id": batch.collection_id,
                   "items": [vars(item)]}
        batch = replace(batch, sha256=hashlib.sha256(json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest())
        binding = dict(
            passage_id=item.passage_id, content_id=item.content_id,
            capture_id=item.capture_id, passage_sha256=passage_sha,
            selector_type="TEXT_POSITION", start_char=0, end_char=len(passage_text),
            passage_text=passage_text, extraction_method="STDLIB_VISIBLE_TEXT",
            extraction_version=STDLIB_HTML_PARSER_VERSION,
            capture_content_sha256=capture_sha,
            capture_media_type="text/plain", capture_charset="utf-8",
            capture_parser_method="STDLIB_VISIBLE_TEXT",
            capture_parser_version=STDLIB_HTML_PARSER_VERSION,
        )

        class BoundCandidate(FakeCandidate):
            def __init__(self):
                super().__init__()
                self.state = passage_state(passage_sha256=passage_sha)
                self.binding = dict(binding)

            def read_private_passage_source_binding(self, passage_id):
                return dict(self.binding)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = CaptureBodyStore(root)
            receipt = store.write(
                capture_id=item.capture_id, body=body, content_sha256=capture_sha,
            )
            binding["capture_body_ref"] = receipt.body_ref
            candidate = BoundCandidate()

            def guarded():
                return preflight_candidate_batch(
                    batch, capture_store=FakeCapture(), candidate_store=candidate,
                    rights_store=FakeRights(), storage_root=root,
                )

            (check,) = guarded()
            check()  # Must revalidate bytes and selector, not just trust preflight.

            tamper_cases = (
                ("shifted", {"start_char": 1, "end_char": len(passage_text) + 1}),
                ("invented", {"passage_text": "A fabricated, same-length passage."}),
                ("missing_charset", {"capture_charset": None}),
                ("wrong_charset", {"capture_charset": "nonsense-charset"}),
                ("missing_parser", {"capture_parser_version": None}),
                ("wrong_parser", {"capture_parser_version": "other-parser"}),
                ("wrong_method", {"extraction_method": "OTHER"}),
                ("wrong_capture_sha", {"capture_content_sha256": "0" * 64}),
                ("wrong_body_ref", {"capture_body_ref": "captures/other.body"}),
                ("wrong_capture_id", {"capture_id": "capture:another"}),
            )
            for label, changes in tamper_cases:
                with self.subTest(label=label):
                    candidate.binding = {**binding, **changes}
                    with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                        guarded()
                    with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                        check()
            candidate.binding = dict(binding)
            # Metadata still claims body available: actual missing/tampered bytes MUST block.
            file_path = store.path(receipt.body_ref)
            file_path.write_bytes(b"corrupted body")
            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                guarded()
            file_path.unlink()
            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                guarded()

    def test_operator_storage_binding_requires_joined_source_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                preflight_candidate_batch(
                    BATCH, capture_store=FakeCapture(), candidate_store=FakeCandidate(),
                    rights_store=FakeRights(), storage_root=Path(temp),
                )

    def test_candidate_manifest_file_is_bounded_before_json_parsing(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "oversized-candidates.json"
            path.write_bytes(b" " * 1_100_000)
            with self.assertRaisesRegex(ValueError, "CANDIDATE_BATCH_FILE_TOO_LARGE"):
                load_candidate_batch(path)

    def test_candidate_passage_body_availability_requires_exact_database_boolean(self):
        for false_or_unknown in (None, False, 0, 1, "true", "false", {}, []):
            with self.subTest(value=false_or_unknown):
                with self.assertRaisesRegex(
                    PrivateCaptureAuthorizationBlocked, "PRIVATE_ANALYSIS_CAPTURE_BODY_UNAVAILABLE",
                ):
                    require_private_passage_state(
                        passage_state(body_ref=false_or_unknown), ITEM,
                    )

    def test_noncanonical_persisted_discovery_locator_never_passes_model_preflight(self):
        capture = FakeCapture()
        original = capture.read_research_capture_context

        def altered_context(collection_id, content_id):
            return {**original(collection_id, content_id),
                    "canonical_url": "https://EXAMPLE.test/reviewed"}

        capture.read_research_capture_context = altered_context
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "PRIVATE_CAPTURE_DISCOVERY_PROVENANCE_INVALID"
        ):
            preflight_candidate_batch(
                BATCH, capture_store=capture, candidate_store=FakeCandidate(), rights_store=FakeRights()
            )

    def test_noncanonical_persisted_content_locator_never_passes_model_preflight(self):
        capture = FakeCapture()
        original = capture.read_operator_capture_content_state

        def altered_content(content_id):
            return {**original(content_id), "canonical_url": "https://EXAMPLE.test/reviewed"}

        capture.read_operator_capture_content_state = altered_content
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "PRIVATE_ANALYSIS_CONTENT_URL_NONCANONICAL"
        ):
            preflight_candidate_batch(
                BATCH, capture_store=capture, candidate_store=FakeCandidate(), rights_store=FakeRights()
            )

    def test_noncanonical_persisted_rights_locator_never_passes_model_preflight(self):
        rights = FakeRights()
        rights.current = replace(rights.current, locator_value="https://EXAMPLE.test/reviewed")
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "PRIVATE_ANALYSIS_RIGHTS_URL_NONCANONICAL"
        ):
            preflight_candidate_batch(
                BATCH, capture_store=FakeCapture(), candidate_store=FakeCandidate(), rights_store=rights
            )

    def test_guard_rechecks_exact_content_and_rights_locators_after_preflight(self):
        capture, candidate, rights = FakeCapture(), FakeCandidate(), FakeRights()
        (guard,) = preflight_candidate_batch(
            BATCH, capture_store=capture, candidate_store=candidate, rights_store=rights
        )
        original_content = capture.read_operator_capture_content_state
        capture.read_operator_capture_content_state = lambda content_id: {
            **original_content(content_id), "canonical_url": "https://EXAMPLE.test/reviewed"
        }
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "PRIVATE_ANALYSIS_CONTENT_URL_NONCANONICAL"
        ):
            guard()
        capture.read_operator_capture_content_state = original_content
        rights.current = replace(rights.current, locator_value="https://EXAMPLE.test/reviewed")
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "PRIVATE_ANALYSIS_RIGHTS_URL_NONCANONICAL"
        ):
            guard()

    def test_loader_rejects_duplicate_json_items_keys_before_authority_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch.json"
            path.write_text(
                '{"version":' + json.dumps(VERSION) +
                ',"collection_id":"research:reviewed","items":' + json.dumps([vars(ITEM)]) +
                ',"items":[]}', encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "CANDIDATE_BATCH_DUPLICATE_JSON_KEY"):
                load_candidate_batch(path)

    def test_loader_rejects_distinct_content_ids_sharing_one_url(self):
        item = {**vars(ITEM), "passage_id": "passage:other", "content_id": "content:other",
                "capture_id": "capture:other"}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch.json"
            path.write_text(json.dumps({
                "version": VERSION, "collection_id": BATCH.collection_id,
                "items": [vars(ITEM), item],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CANDIDATE_BATCH_URL_CONTENT_COLLISION"):
                load_candidate_batch(path)

    def test_direct_batch_duplicate_passage_fails_before_any_store_reads(self):
        capture, candidate, rights = FakeCapture(), FakeCandidate(), FakeRights()
        calls = []
        def should_not_read(*args, **kwargs):
            calls.append("read")
            return None
        capture.read_research_capture_context = should_not_read
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "CANDIDATE_BATCH_PASSAGE_DUPLICATE"
        ):
            preflight_candidate_batch(
                CandidateBatch(BATCH.collection_id, (ITEM, ITEM), BATCH.sha256),
                capture_store=capture, candidate_store=candidate, rights_store=rights,
            )
        self.assertEqual(calls, [])

    def test_direct_batch_stale_digest_blocks_before_store_reads(self):
        capture = FakeCapture()
        calls = []
        def read(*args, **kwargs):
            calls.append("read")
            return None
        capture.read_research_capture_context = read
        altered = replace(ITEM, passage_sha256="c" * 64)
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "MANIFEST_HASH_MISMATCH"):
            preflight_candidate_batch(
                CandidateBatch(BATCH.collection_id, (altered,), BATCH.sha256),
                capture_store=capture, candidate_store=FakeCandidate(), rights_store=FakeRights(),
            )
        self.assertEqual(calls, [])

    def test_multiple_distinct_passages_of_one_content_are_valid_manifest_members(self):
        second = {**vars(ITEM), "passage_id": "passage:second", "passage_sha256": "c" * 64}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch.json"
            path.write_text(json.dumps({
                "version": VERSION, "collection_id": BATCH.collection_id,
                "items": [vars(ITEM), second],
            }), encoding="utf-8")
            loaded = load_candidate_batch(path)
        self.assertEqual(len(loaded.items), 2)
        self.assertEqual({item.content_id for item in loaded.items}, {ITEM.content_id})
        self.assertEqual({item.canonical_url for item in loaded.items}, {ITEM.canonical_url})

    def test_second_rights_read_wrong_locator_cannot_authorize_model_use(self):
        class SwitchingRights(FakeRights):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def read_current(self, subject):
                self.calls += 1
                if self.calls == 1:
                    return self.current
                return replace(self.current, locator_value="https://example.test/other")

        rights = SwitchingRights()
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "RIGHTS_URL_MISMATCH"):
            preflight_candidate_batch(
                BATCH, capture_store=FakeCapture(),
                candidate_store=FakeCandidate(), rights_store=rights,
            )
        self.assertEqual(rights.calls, 2)

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

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    STUDIO_DISCOVERY_TRIAGE_VERSION,
    StudioDiscoveryTriageRequest,
    make_triage_request,
    present_triage_receipt,
)


def request(**overrides):
    return make_triage_request(**{
        "collection_id": "collection:1",
        "hit_id": "hit:1",
        "request_key": "intent:2026-10-09:1",
        "decision": "NEEDS_REVIEW",
        "expected_revision": 0,
        "actor_ref": "reviewer:opaque:1",
    } | overrides)


def row(req=None, **overrides):
    req = req or request()
    return {
        "collection_id": req.collection_id,
        "hit_id": req.hit_id,
        "request_key": req.request_key,
        "decision": req.decision,
        "expected_revision": req.expected_revision,
        "revision": req.expected_revision + 1,
        "payload_sha256": req.payload_sha256,
        "result_code": "CREATED",
    } | overrides


class DiscoveryTriageContractTests(unittest.TestCase):
    def test_immutable_validated_request_and_canonical_fingerprint(self):
        req = request()
        self.assertIsInstance(req, StudioDiscoveryTriageRequest)
        self.assertRegex(req.payload_sha256, r"^[0-9a-f]{64}$")
        serialized = json.dumps({
            "actor_ref": req.actor_ref,
            "collection_id": req.collection_id,
            "decision": req.decision,
            "expected_revision": req.expected_revision,
            "hit_id": req.hit_id,
            "request_key": req.request_key,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        self.assertEqual(req.payload_sha256, hashlib.sha256(serialized).hexdigest())
        self.assertEqual(req, request())
        with self.assertRaises(FrozenInstanceError):
            req.decision = "REJECTED"
        self.assertNotIn(req.actor_ref, repr(req))
        self.assertNotIn(req.request_key, repr(req))

    def test_actor_decision_revision_and_ids_are_all_fingerprinted(self):
        original = request()
        for changed in (
            {"collection_id": "collection:2"}, {"hit_id": "hit:2"},
            {"request_key": "intent:2"}, {"decision": "DEFERRED"},
            {"expected_revision": 1}, {"actor_ref": "reviewer:opaque:2"},
        ):
            with self.subTest(changed=changed):
                self.assertNotEqual(original.payload_sha256, request(**changed).payload_sha256)
        self.assertEqual(replace(original, decision="REJECTED").decision, "REJECTED")
        self.assertNotEqual(replace(original, decision="REJECTED").payload_sha256, original.payload_sha256)

    def test_ids_and_opaque_references_are_bounded_without_coercion(self):
        for key in ("collection_id", "hit_id", "request_key", "actor_ref"):
            for bad in (None, "", "a b", "newline\nsecret", "title?<script>", 17, True, [], "é"):
                with self.subTest(key=key, bad=bad), self.assertRaisesRegex(ValueError, "REFERENCE_INVALID"):
                    request(**{key: bad})
        self.assertEqual(len(request(collection_id="a" * 180).collection_id), 180)
        self.assertEqual(len(request(actor_ref="b" * 128).actor_ref), 128)
        self.assertEqual(len(request(request_key="c" * 128).request_key), 128)
        for key, bound in (
            ("collection_id", 180), ("hit_id", 180),
            ("actor_ref", 128), ("request_key", 128),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "REFERENCE_INVALID"):
                request(**{key: "a" * (bound + 1)})

    def test_decisions_and_revision_types_fail_closed(self):
        for decision in ("APPROVE", "APPROVED", "EXTRACT", "MERGE", "PUBLISH", "LINK", "NEEDS_REVIEW ", None, 1):
            with self.subTest(decision=decision), self.assertRaisesRegex(ValueError, "DECISION_INVALID"):
                request(decision=decision)
        for decision in ("NEEDS_REVIEW", "DEFERRED", "REJECTED"):
            self.assertEqual(request(decision=decision).decision, decision)
        for rev in (-1, True, False, 0.0, "0", None, [], 1.5, 2**63 - 1, 2**63):
            with self.subTest(revision=rev), self.assertRaisesRegex(ValueError, "REVISION_INVALID"):
                request(expected_revision=rev)
        self.assertEqual(request(expected_revision=0).expected_revision, 0)
        self.assertEqual(request(expected_revision=100).expected_revision, 100)
        self.assertEqual(request(expected_revision=2**63 - 2).expected_revision, 2**63 - 2)
        with self.assertRaises(ValueError):
            StudioDiscoveryTriageRequest("collection:1", "hit:1", "key", "PUBLISH", 0, "actor:1")

    def test_success_and_exact_replay_are_validated_and_allowlisted(self):
        req = request()
        for code in ("CREATED", "REPLAY"):
            persisted = row(req, result_code=code,
                            canonical_url="https://private.example/token",
                            title="PRIVATE TITLE", raw_body="DO NOT EXPOSE",
                            metadata={"provider_key": "SECRET"}, actor_ref="PRIVATE ACTOR")
            receipt = present_triage_receipt(persisted, request=req)
            self.assertEqual(receipt["contract_version"], STUDIO_DISCOVERY_TRIAGE_VERSION)
            self.assertEqual(receipt["result_code"], code)
            self.assertEqual(receipt["revision"], 1)
            self.assertTrue(receipt["private_only"])
            self.assertFalse(receipt["publication_authority"])
            self.assertFalse(receipt["triage_action_authorized"])
            self.assertEqual(receipt["payload_sha256"], req.payload_sha256)
            serialized = json.dumps(receipt)
            for forbidden in ("private.example", "PRIVATE TITLE", "DO NOT EXPOSE", "SECRET", "PRIVATE ACTOR", "canonical_url", "metadata"):
                self.assertNotIn(forbidden, serialized)

    def test_replay_cannot_change_actor_decision_revision_or_fingerprint(self):
        req = request()
        original = row(req, result_code="REPLAY")
        for changed_req in (
            request(actor_ref="other:actor"), request(decision="REJECTED"),
            request(expected_revision=1), request(hit_id="hit:2"),
            request(collection_id="collection:2"),
        ):
            with self.subTest(change=changed_req), self.assertRaises(ValueError):
                present_triage_receipt(original, request=changed_req)
        for changed_row in (
            {"decision": "REJECTED"}, {"expected_revision": 1},
            {"revision": 2}, {"revision": 0}, {"revision": None},
            {"payload_sha256": "f" * 64}, {"payload_sha256": "F" * 64},
            {"payload_sha256": True},
        ):
            with self.subTest(change=changed_row), self.assertRaises(ValueError):
                present_triage_receipt(original | changed_row, request=req)

    def test_conflict_result_codes_are_not_misreported_as_success(self):
        req = request()
        conflict = present_triage_receipt(row(req, result_code="IDEMPOTENCY_CONFLICT"), request=req)
        self.assertEqual(conflict["result_code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(conflict["payload_sha256"], req.payload_sha256)
        self.assertFalse(conflict["triage_action_authorized"])
        with self.assertRaisesRegex(ValueError, "REQUEST_ECHO_MISMATCH"):
            present_triage_receipt(
                row(req, result_code="IDEMPOTENCY_CONFLICT", payload_sha256="f" * 64),
                request=req,
            )
        revision_conflict = present_triage_receipt(
            row(req, result_code="REVISION_CONFLICT", revision=9), request=req,
        )
        self.assertEqual(revision_conflict["revision"], 9)
        for bad in (
            {"revision": 0}, {"revision": None},
            {"payload_sha256": "f" * 64}, {"decision": "REJECTED"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                present_triage_receipt(
                    row(req, result_code="REVISION_CONFLICT", **bad), request=req,
                )

    def test_missing_scope_receipt_is_non_authorizing(self):
        req = request()
        result = present_triage_receipt(
            row(req, result_code="SCOPE_NOT_FOUND", revision=None), request=req,
        )
        self.assertEqual(result["result_code"], "SCOPE_NOT_FOUND")
        self.assertIsNone(result["revision"])
        for leaked in (0, 1, 42):
            with self.subTest(leaked=leaked), self.assertRaisesRegex(ValueError, "NOT_FOUND_INVALID"):
                present_triage_receipt(row(req, result_code="SCOPE_NOT_FOUND", revision=leaked), request=req)

    def test_bad_db_rows_fail_closed_without_echoing_untrusted_data(self):
        req = request()
        for corrupted in (
            {"result_code": "PUBLISHED"}, {"result_code": "REPLAY\nsecret"},
            {"hit_id": "hit:wrong"}, {"collection_id": "collection:wrong"},
            {"request_key": "key:wrong"}, {"request_key": "key\nDO NOT EXPOSE"},
            {"decision": "PUBLISH"}, {"expected_revision": True},
            {"revision": "1"}, {"revision": 2**63},
            {"payload_sha256": "SECRET"},
        ):
            with self.subTest(corrupted=corrupted), self.assertRaises(ValueError) as caught:
                present_triage_receipt(row(req, **corrupted), request=req)
            self.assertNotIn("DO NOT EXPOSE", str(caught.exception))
        for malformed in (None, [], "row", 7):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "RECEIPT_INVALID"):
                present_triage_receipt(malformed, request=req)
        with self.assertRaisesRegex(ValueError, "REQUEST_INVALID"):
            present_triage_receipt(row(req), request={"payload_sha256": req.payload_sha256})


if __name__ == "__main__":
    unittest.main()

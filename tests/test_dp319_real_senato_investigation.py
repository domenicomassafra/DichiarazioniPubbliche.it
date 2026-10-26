"""Public DP-319 canary seam: pinned licensed Capture -> durable bounded receipt."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked  # noqa: E402
from dp330_senato_private_capture import (  # noqa: E402
    SOURCE_FAMILY,
    SOURCE_URL,
    POLICY,
)
from dp326_senato_private_discovery import (  # noqa: E402
    CONTENT_BLOB_SHA1,
    CURRENT_COMMIT,
    RIGHTS_RECEIPT,
)

import dp319_senato_private_investigation as canary  # noqa: E402


CONTENT_ID = "content:1f54b0854fd0f25eba9099f7b9f45b119de235a8af10f8e0e0a5d7e8233d6a22"
XML = (
    b'<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03">'
    b'<debate><meta><identification><FRBRWork><FRBRdate date="2025-05-29" '
    b'name="presentazione"/></FRBRWork></identification></meta></debate></akomaNtoso>'
)


def rights_record(*, allowed=True, valid_receipt=True):
    subject = RightsSubject(
        source_family=SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=SOURCE_URL,
        content_id=CONTENT_ID,
    )
    now = datetime.now(timezone.utc)
    return PrivateRightsRecord(
        id="private-rights:test",
        subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=SOURCE_URL,
        content_id=CONTENT_ID,
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref=RIGHTS_RECEIPT if valid_receipt else "licence:unrelated",
        permitted_uses=("DISCOVER_METADATA", "FETCH", "PARSE_TEXT")
        if allowed
        else ("DISCOVER_METADATA",),
        attribution_requirements=("ATTRIBUTION_REQUIRED",),
        reviewed_at=(now - timedelta(days=1)).isoformat(),
        expires_at=(now + timedelta(days=10)).isoformat(),
        reviewer_ref="machine:licence-attestation-v1",
        policy_version=POLICY,
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
    )


class FakeCaptureStore:
    def __init__(self, *, database_url):
        self.database_url = database_url

    def run(self, sql, **kwargs):
        return json.dumps(
            {
                "id": CONTENT_ID,
                "url": SOURCE_URL,
                "source_id": canary.SOURCE_ID,
                "member_status": "INCLUDED",
                "collection_status": "ACTIVE",
                "discovery_hits": 1,
                "rights_status": "CLEARED",
                "membership": {"run_id": "discovery-run:senato-akn-dp326"},
            }
        )

    def find_capture(self, content_id, sha):
        assert (content_id, sha) == (CONTENT_ID, canary.BODY_SHA256)
        return {
            "id": "capture:real-fixture",
            "content_id": CONTENT_ID,
            "status": "CAPTURED",
            "rights_status": "CLEARED",
            "hold_status": "NONE",
            "final_url": SOURCE_URL,
            "content_sha256": canary.BODY_SHA256,
            "body_ref": "captures/fixture.body",
            "media_type": "text/plain",
        }


class RealSenatoInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "private-ledger.sqlite"

    def execute(self, *, rights=True, valid_receipt=True, body=XML):
        class FakeRightsStore:
            def __init__(self, *, database_url):
                pass

            def read_current(self, _subject):
                return rights_record(allowed=rights, valid_receipt=valid_receipt)

        class FakeBodyStore:
            def __init__(self, _path):
                pass

            def read(self, _ref, *, expected_sha256, max_bytes):
                assert expected_sha256 == canary.BODY_SHA256 and max_bytes < 2_000_000
                return body

        hit = type(
            "Hit",
            (),
            {
                "canonical_url": SOURCE_URL,
                "metadata": {"commit": CURRENT_COMMIT, "blob_sha1": CONTENT_BLOB_SHA1},
            },
        )()
        with (
            patch.object(canary, "BODY_SHA256", hashlib.sha256(body).hexdigest()),
            patch.object(canary, "official_verified_hit", return_value=hit),
            patch.object(canary, "PrivateRightsRegistryStore", FakeRightsStore),
            patch.object(canary, "CapturePipelineStore", FakeCaptureStore),
            patch.object(canary, "CaptureBodyStore", FakeBodyStore),
        ):
            return canary.run("fixture-db", self.path, Path(self.tmp.name))

    def test_replay_of_one_authentic_shape_never_repeats_attempt(self):
        initial = self.execute()
        replay = self.execute()
        self.assertEqual(initial["decision"], "EXHAUSTED")
        self.assertEqual(initial["reason_code"], "INVESTIGATION_ATTEMPT_CAP")
        self.assertEqual(initial["source_document_date"], "2025-05-29")
        self.assertEqual(initial["observation"], "SOURCE_INCONCLUSIVE")
        self.assertEqual(initial["source_sha256"], hashlib.sha256(XML).hexdigest())
        self.assertEqual(initial["reservation_count"], 1)
        self.assertEqual(initial["completion_count"], 1)
        self.assertEqual(initial["ledger_revision"], 2)
        self.assertFalse(initial["replay_same_receipt"])
        self.assertTrue(replay["replay_same_receipt"])
        self.assertEqual(replay["attempt_id"], initial["attempt_id"])
        self.assertEqual(replay["ledger_revision"], 2)
        self.assertEqual(replay["spent_usd"], "0")
        self.assertFalse(replay["publication_authority"])
        self.assertFalse(replay["downstream_queue_closed"])

    def test_unpermitted_text_use_fails_before_ledger_is_created(self):
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_NOT_PERMITTED"):
            self.execute(rights=False)
        self.assertFalse(self.path.exists())

    def test_unrelated_license_receipt_fails_before_ledger_is_created(self):
        with self.assertRaisesRegex(
            ValueError, "DP319_SOURCE_LICENSE_RECEIPT_MISMATCH"
        ):
            self.execute(valid_receipt=False)
        self.assertFalse(self.path.exists())

    def test_wrong_xml_is_not_counted_as_a_completed_attempt(self):
        with self.assertRaisesRegex(ValueError, "DP319_PINNED_XML_INVALID"):
            self.execute(body=b"<other/>")
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()

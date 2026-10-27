"""DP-319B Camera private PARSE_TEXT: signed authority at the operator API seam."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority, provision_reviewer_credential,
)
from dichiarazioni_pubbliche.garlasco_camera_pilot import CAMERA_SOURCES  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import RightsSubject, rights_subject_fingerprint  # noqa: E402
from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use  # noqa: E402
from dichiarazioni_pubbliche.camera_parse_authority import CameraParseAuthority  # noqa: E402
from tests.test_dp236_source_use import reviewed  # noqa: E402


NOW = datetime(2026, 10, 26, 18, tzinfo=timezone.utc)
SOURCES = (
    ("content:garlasco:camera:sed0607", CAMERA_SOURCES[0]["url"],
     "2ab7a0739d6ffc766b45526023ab4bd878c0e996fa90aa7d6dec6a3e0cc7de6f"),
    ("content:garlasco:camera:sed0703", CAMERA_SOURCES[1]["url"],
     "09aa5d2b696722819ca44c978b0c4000094fc60152a64fe81e4fb7e41a5df53f"),
)


class FakeRuntime:
    def __init__(self, record, content_id, capture_sha):
        self.record = record
        self.content_id = content_id
        self.capture_sha = capture_sha
        self.receipts = {}

    def read_current(self, subject):
        return self.record

    def run(self, sql, **kwargs):
        if "FROM content_capture" in sql:
            return "1" if (kwargs["content_id"], kwargs["capture_sha256"]) == (
                self.content_id, self.capture_sha
            ) else "0"
        if "INSERT INTO private_camera_parse_attestation" in sql:
            row = json.loads(kwargs["payload"])
            self.receipts.setdefault(row["receipt_id"], row)
            return ""
        if "FROM private_camera_parse_attestation" in sql:
            rows = [
                receipt for receipt in self.receipts.values()
                if (receipt["content_id"], receipt["capture_sha256"],
                    receipt["rights_record_id"]) == (
                        kwargs["content_id"], kwargs["capture_sha256"],
                        kwargs["rights_record_id"]
                    )
            ]
            return json.dumps(rows[-1]) if rows else ""
        raise AssertionError("unexpected SQL operation")


class CameraRightsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "authority"
        provision_reviewer_credential(
            self.root, credential_id="camera-rights-20261026",
            actor_ref="agent:private-rights-reviewer:camera",
            key_version="v1",
        )
        self.authority = LocalFileReviewerIdentityAuthority(self.root)
        self.content_id, self.url, self.sha = SOURCES[0]
        self.subject = RightsSubject(
            source_family="camera_official_stenographic",
            locator_kind="URL", locator_value=self.url, content_id=self.content_id,
        )
        self.record = replace(
            reviewed(), id="private-rights:camera-test",
            subject_fingerprint=rights_subject_fingerprint(self.subject),
            source_family=self.subject.source_family,
            locator_value=self.url, content_id=self.content_id,
            reviewed_at="2026-10-25T00:00:00+00:00",
            policy_version="dp426-camera-article5-private-text-20261025-v1",
            expires_at="2026-11-24T00:00:00+00:00",
        )
        self.runtime = FakeRuntime(self.record, self.content_id, self.sha)
        self.service = CameraParseAuthority(self.runtime, self.authority)

    def _issue(self):
        return self.service.issue(
            content_id=self.content_id, capture_sha256=self.sha,
            credential_id="camera-rights-20261026",
            issued_at=NOW.isoformat(),
        )

    def _inspect(self, *, use="PARSE_TEXT", sha=None, now=NOW):
        return self.service.inspect(
            content_id=self.content_id, capture_sha256=sha or self.sha,
            use=use, now=now,
        )

    def test_unsigned_existing_rights_are_held(self):
        self.assertFalse(self._inspect()["permitted"])
        self.assertEqual(self._inspect()["reason"], "CAMERA_PARSE_SIGNED_RECEIPT_MISSING")

    def test_signed_private_use_is_bound_to_capture_and_current_rights(self):
        receipt = self._issue()
        self.assertTrue(receipt["permitted"])
        result = self._inspect()
        self.assertTrue(result["permitted"])
        self.assertEqual(result["receipt_id"], receipt["receipt_id"])
        self.assertEqual(result["issuer_role"], "PRIVATE_RIGHTS_AGENT")
        self.assertFalse(result["publication_authority"])
        for use in ("EXCERPT_PUBLIC", "FETCH", "STORE_BODY", "ASR_MEDIA"):
            with self.subTest(use=use):
                self.assertFalse(self._inspect(use=use)["permitted"])
        self.assertFalse(self._inspect(sha="f" * 64)["permitted"])

    def test_forged_signature_and_changed_hash_fail_closed(self):
        self._issue()
        row = next(iter(self.runtime.receipts.values()))
        row["mac_sha256"] = "0" * 64
        self.assertEqual(self._inspect()["reason"], "CAMERA_PARSE_AUTHORITY_INVALID")
        row["mac_sha256"] = "a" * 64
        self.assertFalse(self._inspect()["permitted"])

    def test_unreviewed_policy_change_never_inherits_camera_authority(self):
        self._issue()
        self.runtime.record = replace(self.record, policy_version="other-project-policy")
        self.assertEqual(self._inspect()["reason"], "CAMERA_PARSE_AUTHORITY_INVALID")

    def test_expiry_revocation_and_supersession_fail_closed(self):
        self._issue()
        self.assertFalse(self._inspect(now=datetime(2026, 11, 25, tzinfo=timezone.utc))["permitted"])
        self.runtime.record = replace(self.record, version_state="SUPERSEDED")
        self.assertFalse(self._inspect()["permitted"])
        self.runtime.record = self.record
        self.authority.revoke("camera-rights-20261026")
        self.assertEqual(self._inspect()["reason"], "CAMERA_PARSE_AUTHORITY_INVALID")

    def test_real_source_use_guard_cannot_parse_with_opaque_receipt(self):
        from dichiarazioni_pubbliche.private_capture_rights import (
            SourceFamilyUseGuard, SourceUseBlocked,
        )
        guard = SourceFamilyUseGuard(
            read_current=self.runtime.read_current, subject=self.subject,
            rights_record_id=self.record.id, policy_version=self.record.policy_version,
            expected_sha256=self.sha, clock=lambda: NOW,
        )
        with self.assertRaisesRegex(SourceUseBlocked, "CAMERA_PARSE_AUTHORITY_REQUIRED"):
            guard.require("PARSE_TEXT")
        guard.authenticated_parse_check = lambda content, digest: self.service.inspect(
            content_id=content, capture_sha256=digest, use="PARSE_TEXT", now=NOW,
        )["permitted"]
        with self.assertRaisesRegex(SourceUseBlocked, "CAMERA_PARSE_AUTHORITY_DENIED"):
            guard.require("PARSE_TEXT")
        self._issue()
        self.assertTrue(guard.require("PARSE_TEXT").permitted)
        self.assertTrue(guard.require("FETCH").permitted)
        row = next(iter(self.runtime.receipts.values()))
        row["mac_sha256"] = "0" * 64
        with self.assertRaisesRegex(SourceUseBlocked, "CAMERA_PARSE_AUTHORITY_DENIED"):
            guard.require("PARSE_TEXT")

    def test_receipt_binding_cannot_be_moved_to_other_source(self):
        self._issue()
        self.content_id, self.url, self.sha = SOURCES[1]
        self.runtime.content_id = self.content_id
        self.runtime.capture_sha = self.sha
        self.assertFalse(self._inspect()["permitted"])

    def test_source_use_preflight_is_separate_from_opaque_references(self):
        decision = evaluate_source_use(
            self.record, subject=self.subject, rights_record_id=self.record.id,
            policy_version=self.record.policy_version, use="PARSE_TEXT", now=NOW,
        )
        self.assertTrue(decision.permitted)
        self.assertFalse(self._inspect()["permitted"])


if __name__ == "__main__":
    unittest.main()

class CameraRightsHttpTests(unittest.TestCase):
    def setUp(self):
        import threading
        from dichiarazioni_pubbliche.studio_local_api import StudioLocalReaders, StudioLoopbackServer
        self.fixture = CameraRightsTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.server = StudioLoopbackServer(
            0, StudioLocalReaders(None, None, None,
                                  camera_parse_rights=self.fixture.service), "a" * 64,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)

    def _stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self, *, authorize=True, use="PARSE_TEXT", sha=None):
        import http.client
        payload = {
            "content_id": self.fixture.content_id,
            "capture_sha256": sha or self.fixture.sha,
            "use": use,
        }
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if authorize:
            headers["Authorization"] = "Bearer " + "a" * 64
        connection.request(
            "POST", "/v1/rights/camera-parse-text", body=json.dumps(payload), headers=headers,
        )
        response = connection.getresponse()
        code, body = response.status, json.loads(response.read())
        connection.close()
        return code, body

    def test_http_requires_authentication_and_verified_private_rights(self):
        self.assertEqual(self.call(authorize=False)[0], 401)
        code, result = self.call()
        self.assertEqual(code, 200, result)
        self.assertFalse(result["data"]["permitted"])
        self.fixture._issue()
        code, result = self.call()
        self.assertEqual(code, 200, result)
        self.assertTrue(result["data"]["permitted"])
        self.assertFalse(result["data"]["publication_authority"])
        self.assertFalse(self.call(use="EXCERPT_PUBLIC")[1]["data"]["permitted"])
        self.assertFalse(self.call(sha="f" * 64)[1]["data"]["permitted"])
        row = next(iter(self.fixture.runtime.receipts.values()))
        row["mac_sha256"] = "0" * 64
        self.assertFalse(self.call()[1]["data"]["permitted"])

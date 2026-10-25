"""DP419: private real-media byte/rights verification at the playback boundary."""
import hashlib
import json
import tempfile
import unittest
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.media_capture_proof import derive_media_capture_segment
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.studio_media_playback import verified_media_playback

URL = "https://upload.wikimedia.org/wikipedia/commons/example/source.wav"


class FakeCaptureReader:
    def __init__(self, material):
        self.material = material
        self.state = {
            "binding_id": "media-binding:test",
            "binding_state": "ATTESTED",
            "hold_reasons": ["RIGHTS_NOT_INDEPENDENTLY_APPROVED"],
            "capture_sha256": material["capture_sha256"],
        }

    def run(self, sql, **kwargs):
        if "inspect_media_capture_segment_binding" in sql:
            return json.dumps(self.state)
        if "FROM private_source_rights_record" in sql:
            return json.dumps([{"id": "rights:test", "source_family": "WIKIMEDIA_COMMONS",
                                "policy_version": "dp419-real-source-v1"}])
        return json.dumps(self.material)


class FakeRightsReader:
    def __init__(self, record):
        self.record = record

    def read_current(self, subject):
        if self.record is None or rights_subject_fingerprint(subject) != self.record.subject_fingerprint:
            return None
        return self.record


class VerifiedPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp419-player-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        source = root / "source.wav"
        with wave.open(str(source), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x01\x00" * 16000 * 4)
        self.bytes = source.read_bytes()
        self.sha = hashlib.sha256(self.bytes).hexdigest()
        proof = derive_media_capture_segment(
            media_path=source, capture_sha256=self.sha, content_id="content:one",
            capture_id="capture:one", canonical_segment_id="segment:one",
            canonical_text_sha256="a"*64, start_ms=1200, end_ms=3400,
        )
        self.store = CaptureBodyStore(root / "body")
        receipt = self.store.write(
            capture_id="capture:one", body=self.bytes, content_sha256=self.sha,
        )
        self.reader = FakeCaptureReader({
            "binding_id": "media-binding:test", "content_id": "content:one",
            "capture_id": "capture:one", "capture_sha256": self.sha,
            "canonical_segment_id": "segment:one", "canonical_text_sha256": "a"*64,
            "start_ms": 1200, "end_ms": 3400, "evidence_sha256": proof["evidence_sha256"],
            "body_ref": receipt.body_ref, "final_url": URL, "media_type": "audio/wav",
            "source_rights": "CLEARED", "capture_rights": "CLEARED",
            "has_approved_passage": True,
        })
        self.subject = RightsSubject("WIKIMEDIA_COMMONS", "URL", URL, content_id="content:one")
        now = datetime.now(timezone.utc)
        record = PrivateRightsRecord(
            id="rights:test", subject_fingerprint=rights_subject_fingerprint(self.subject),
            source_family="WIKIMEDIA_COMMONS", locator_kind="URL", locator_value=URL,
            content_id="content:one", evidence_id=None, transcript_segment_id=None,
            canonical_segment_id=None, passage_id=None, rights_status="CLEARED",
            rights_receipt_ref="rights-review:fixture",
            permitted_uses=("FETCH", "STORE_BODY", "ASR_MEDIA", "PLAYBACK"),
            attribution_requirements=("CREDIT_SOURCE",),
            reviewed_at=(now - timedelta(hours=1)).isoformat(),
            expires_at=(now + timedelta(days=2)).isoformat(),
            reviewer_ref="agent:fixture", policy_version="dp419-real-source-v1",
            record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
        )
        self.rights = FakeRightsReader(record)

    def play(self):
        return verified_media_playback(
            capture_reader=self.reader, rights_reader=self.rights, body_store=self.store,
            binding_id="media-binding:test",
        )

    def test_authenticated_route_can_receive_verified_bytes_and_exact_time(self):
        media = self.play()
        self.assertEqual(media.body, self.bytes)
        self.assertEqual((media.start_ms, media.end_ms), (1200, 3400))
        self.assertEqual(media.media_type, "audio/wav")

    def test_current_rights_capture_segment_and_body_must_all_still_match(self):
        from dataclasses import replace
        current = self.rights.record
        self.rights.record = replace(current, rights_status="REVOKED")
        with self.assertRaises(ValueError):
            self.play()
        self.rights.record = current
        for bucket, key, wrong in (
            (self.reader.state, "binding_state", "REVOKED"),
            (self.reader.material, "evidence_sha256", "0" * 64),
            (self.reader.material, "has_approved_passage", False),
            (self.reader.material, "capture_sha256", "0" * 64),
            (self.reader.material, "capture_rights", "REVOKED"),
            (self.reader.material, "source_rights", "DENIED"),
        ):
            with self.subTest(key=key, wrong=wrong):
                previous = bucket[key]
                try:
                    bucket[key] = wrong
                    with self.assertRaises(ValueError):
                        self.play()
                finally:
                    bucket[key] = previous

    def test_missing_rights_or_body_ref_is_held(self):
        current = self.rights.record
        self.rights.record = None
        with self.assertRaises(ValueError):
            self.play()
        self.rights.record = current
        self.reader.material["body_ref"] = "../wrong"
        with self.assertRaises(ValueError):
            self.play()


if __name__ == "__main__":
    unittest.main()

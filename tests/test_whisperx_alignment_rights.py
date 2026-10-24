"""DP-165: current DP-305 rights seam and the private operator canary."""
import hashlib
import io
import json
import os
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dichiarazioni_pubbliche.parliamentary_alignment import ParliamentaryIntervention
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.whisperx_alignment_private import (
    AlignmentHold, propose_whisperx_alignment,
)
from dichiarazioni_pubbliche.whisperx_alignment_rights import (
    AlignmentRightsScope, alignment_authorization_guard,
    read_alignment_rights_scope, registry_alignment_authorization_guard,
)

TEXT = "Non aumenteremo 7 tasse."
WORDS = [
    {"word": "Non", "start": .10, "end": .25, "score": .98},
    {"word": "aumenteremo", "start": .25, "end": .80, "score": .95},
    {"word": "7", "start": .85, "end": 1.0, "score": .93},
    {"word": "tasse.", "start": 1.0, "end": 1.4, "score": .91},
]
NOW = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
URL = "https://example.test/private-wav-origin"
CONTENT = "content:dp165-synthetic"


def intervention(**changes):
    values = dict(intervention_id="i1", session_id="s1",
                  official_speaker_ref="ref", official_speaker_name="Demo",
                  transcript_text=TEXT, source_url="https://example.org/",
                  source_version="v1", speaker_resolution_approved=False)
    values.update(changes)
    return ParliamentaryIntervention(**values)


def subject(url=URL, content_id=CONTENT):
    return RightsSubject(source_family="SYNTHETIC_ALIGNMENT", locator_kind="URL",
                         locator_value=url, content_id=content_id)


def record(**changes):
    values = dict(
        id="rights:dp165-synthetic",
        subject_fingerprint=rights_subject_fingerprint(subject()),
        source_family="SYNTHETIC_ALIGNMENT", locator_kind="URL", locator_value=URL,
        content_id=CONTENT, evidence_id=None, transcript_segment_id=None,
        canonical_segment_id=None, passage_id=None, rights_status="CLEARED",
        rights_receipt_ref="receipt:dp165-synthetic", permitted_uses=("ASR_MEDIA",),
        attribution_requirements=(),
        reviewed_at=(NOW - timedelta(days=1)).isoformat(),
        expires_at=(NOW + timedelta(days=1)).isoformat(),
        reviewer_ref="synthetic:operator", policy_version="dp165-policy-v1",
        record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
    )
    values.update(changes)
    return PrivateRightsRecord(**values)


PAYLOAD = {
    "rights_record_id": "rights:dp165-synthetic",
    "rights_policy_version": "dp165-policy-v1",
    "rights_receipt_id": "receipt:dp165-synthetic",
}


class FakeRegistry:
    def __init__(self, reviewed, current):
        self.reviewed, self.current = reviewed, current
        self.reads = 0

    def read_record(self, record_id):
        return self.reviewed

    def read_current(self, current_subject):
        self.reads += 1
        observed = self.current
        if callable(observed):
            return observed(self.reads)
        return observed


UNSET = object()


class AlignmentSourceRightsTests(unittest.TestCase):
    def setUp(self):
        self.store = PsqlRuntime()

    def scope(self, payload=None, reviewed=UNSET):
        registry = FakeRegistry(record() if reviewed is UNSET else reviewed, record())
        with patch(
            "dichiarazioni_pubbliche.whisperx_alignment_rights.PrivateRightsRegistryStore",
            return_value=registry,
        ):
            return read_alignment_rights_scope(
                store=self.store, content_id=CONTENT, canonical_url=URL,
                payload=PAYLOAD if payload is None else payload,
            )

    def guard(self, reviewed=UNSET, current=UNSET):
        registry = FakeRegistry(record() if reviewed is UNSET else reviewed,
                                record() if current is UNSET else current)
        with patch(
            "dichiarazioni_pubbliche.whisperx_alignment_rights.PrivateRightsRegistryStore",
            return_value=registry,
        ):
            scope = read_alignment_rights_scope(
                store=self.store, content_id=CONTENT, canonical_url=URL,
                payload=PAYLOAD,
            )
            guard = registry_alignment_authorization_guard(
                scope, store=self.store, clock=lambda: NOW)
        return guard, registry

    def test_current_reviewed_media_use_permits_alignment_and_rereads_authority(self):
        guard, registry = self.guard()
        for _ in range(3):
            guard()
        self.assertEqual(registry.reads, 3)

    def test_scope_is_required_before_any_registry_read(self):
        for change in (
            {"rights_record_id": None},
            {"rights_policy_version": "  "},
            {"rights_receipt_id": ""},
        ):
            with self.subTest(change=change):
                factory = Mock()
                with patch(
                    "dichiarazioni_pubbliche.whisperx_alignment_rights.PrivateRightsRegistryStore",
                    factory,
                ), self.assertRaisesRegex(AlignmentHold, "SCOPE_REQUIRED"):
                    self.scope(PAYLOAD | change)
                factory.assert_not_called()
        with self.assertRaisesRegex(AlignmentHold, "SCOPE_REQUIRED"):
            read_alignment_rights_scope(store=self.store, content_id="",
                                        canonical_url=URL, payload=PAYLOAD)

    def test_reader_must_be_the_psql_runtime_and_record_must_exist(self):
        with self.assertRaisesRegex(AlignmentHold, "READER_REQUIRED"):
            read_alignment_rights_scope(store=object(), content_id=CONTENT,
                                        canonical_url=URL, payload=PAYLOAD)
        with self.assertRaisesRegex(AlignmentHold, "RECORD_MISSING"):
            self.scope(reviewed=SimpleNamespace(rights_receipt_ref="x"))
        with self.assertRaisesRegex(AlignmentHold, "RECEIPT_MISMATCH"):
            self.scope(PAYLOAD | {"rights_receipt_id": "receipt:unrelated"})
        with self.assertRaisesRegex(AlignmentHold, "RECORD_MISSING"):
            self.scope(reviewed=None)

    def test_revoked_expired_historical_wrong_use_and_policy_fail_closed(self):
        cases = {
            "SOURCE_USE_REVOKED": {"rights_status": "REVOKED"},
            "SOURCE_USE_EXPIRED": {"expires_at": "2020-01-01T00:00:00+00:00"},
            "SOURCE_USE_RECORD_NOT_CURRENT": {"version_state": "HISTORICAL"},
            "SOURCE_USE_NOT_PERMITTED": {"permitted_uses": ("FETCH", "PARSE_TEXT")},
        }
        for code, change in cases.items():
            with self.subTest(code=code):
                guard, _ = self.guard(current=record(**change))
                with self.assertRaisesRegex(AlignmentHold, code):
                    guard()
        guard, _ = self.guard(current=record(policy_version="other-policy"))
        with self.assertRaisesRegex(AlignmentHold, "SOURCE_USE_POLICY_MISMATCH"):
            guard()

    def test_unknown_current_subject_is_not_rights_approval(self):
        guard, _ = self.guard(current=None)
        with self.assertRaisesRegex(AlignmentHold, "SOURCE_USE_RECORD_MISSING"):
            guard()

    def test_guard_without_callable_reader_is_refused(self):
        with self.assertRaisesRegex(AlignmentHold, "READER_REQUIRED"):
            alignment_authorization_guard(self.scope(), read_current=None)
        with self.assertRaisesRegex(AlignmentHold, "SCOPE_REQUIRED"):
            alignment_authorization_guard(object(), read_current=lambda _: record())


class AlignmentAdapterRightsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audio = self.root / "audio"
        self.audio.mkdir()
        self.wav = self.audio / "clip.wav"
        with wave.open(str(self.wav), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\x00\x00" * 32000)
        self.audio_hash = hashlib.sha256(self.wav.read_bytes()).hexdigest()
        model = self.root / "model"
        model.mkdir()
        files = {}
        for name, body in (("config.json", b"{}"), ("model.safetensors", b"weights"),
                           ("LICENSE", b"fixture license")):
            (model / name).write_bytes(body)
            files[name] = hashlib.sha256(body).hexdigest()
        self.receipt = self.root / "receipt.json"
        self.receipt.write_text(json.dumps(dict(
            model_id="synthetic/local-italian-wav2vec2", revision="a" * 40,
            model_dir=str(model), license_spdx="Apache-2.0",
            license_source_url="https://example.org/license/fixture",
            license_reviewed=True, native_notices_reviewed=True, files=files)))

    def run_adapter(self, guard, *, child=None):
        def synthetic_worker(*_args, **kwargs):
            kwargs["stdout"].write(json.dumps({"word_segments": WORDS}).encode("utf-8"))
            return SimpleNamespace(returncode=0)

        with patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_WHISPERX_ENABLED": "1"}), \
             patch("dichiarazioni_pubbliche.whisperx_alignment_private.platform.system",
                   return_value="Linux"), \
             patch("dichiarazioni_pubbliche.whisperx_alignment_private.importlib.metadata.version",
                   return_value="3.8.6"), \
             patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run",
                   side_effect=child or synthetic_worker) as command:
            return propose_whisperx_alignment(
                intervention(), audio_path=str(self.wav), audio_root=self.audio,
                audio_sha256=self.audio_hash, duration_seconds=2.0,
                rights_basis="OWNER_AUTHORIZED", rights_receipt_id="rights:fixture:0001",
                authorization=True, consent_confirmed=False, authorization_guard=guard,
                model_receipt_path=self.receipt, source_variant_id="variant-fixture",
                source_segment_id="segment-fixture",
                source_variant_sha256="a" * 64, source_segment_sha256="b" * 64,
            ), command

    def registry_guard(self, current=UNSET):
        registry = FakeRegistry(record(), record() if current is UNSET else current)
        with patch(
            "dichiarazioni_pubbliche.whisperx_alignment_rights.PrivateRightsRegistryStore",
            return_value=registry,
        ):
            scope = read_alignment_rights_scope(
                store=PsqlRuntime(), content_id=CONTENT, canonical_url=URL,
                payload=PAYLOAD)
            return registry_alignment_authorization_guard(
                scope, store=PsqlRuntime(), clock=lambda: NOW), registry

    def test_adapter_rechecks_live_registry_before_staging_and_after_inference(self):
        guard, registry = self.registry_guard()
        proposal, command = self.run_adapter(guard)
        self.assertEqual(proposal.status, "REVIEW_CANDIDATE")
        self.assertEqual(registry.reads, 3)
        self.assertEqual(command.call_count, 1)
        self.assertTrue(proposal.publication_blocked)
        self.assertFalse(proposal.source_span_review_ready)

    def test_revocation_during_inference_yields_no_candidate(self):
        guard, _ = self.registry_guard(
            current=lambda reads: record(rights_status="REVOKED") if reads > 2 else record())
        with self.assertRaisesRegex(AlignmentHold, "SOURCE_RIGHTS_REVOKED"):
            self.run_adapter(guard)

    def test_missing_current_record_blocks_before_any_model_or_audio_read(self):
        guard, _ = self.registry_guard(current=None)
        with patch("dichiarazioni_pubbliche.whisperx_alignment_private._receipt") as manifest:
            with self.assertRaisesRegex(AlignmentHold, "SOURCE_RIGHTS_REVOKED"):
                self.run_adapter(guard)
        manifest.assert_not_called()


class AlignmentCanaryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        audio = self.root / "audio"
        audio.mkdir()
        self.wav = audio / "clip.wav"
        with wave.open(str(self.wav), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\x00\x00" * 32000)
        model = self.root / "model"
        model.mkdir()
        files = {}
        for name, body in (("config.json", b"{}"), ("model.safetensors", b"weights"),
                           ("LICENSE", b"fixture license")):
            (model / name).write_bytes(body)
            files[name] = hashlib.sha256(body).hexdigest()
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps(dict(
            model_id="synthetic/local-italian-wav2vec2", revision="a" * 40,
            model_dir=str(model), license_spdx="Apache-2.0",
            license_source_url="https://example.org/license/fixture",
            license_reviewed=True, native_notices_reviewed=True, files=files)))
        # The operator canary reads the real wall clock; keep its synthetic
        # grant valid independently of the fixed 2026-10-23 unit-test clock.
        now = datetime.now(timezone.utc)
        reviewed = record(
            reviewed_at=(now - timedelta(days=1)).isoformat(),
            expires_at=(now + timedelta(days=1)).isoformat(),
        )
        self.manifest = {
            "manifest_version": "dp165-alignment-canary-v1",
            "intervention": {
                "intervention_id": "i1", "session_id": "s1",
                "official_speaker_ref": "ref", "official_speaker_name": "Demo",
                "transcript_text": TEXT, "source_url": "https://example.org/",
                "source_version": "v1", "official_start_ms": None,
                "official_end_ms": None,
            },
            "audio": {"path": str(self.wav), "root": str(audio),
                      "sha256": hashlib.sha256(self.wav.read_bytes()).hexdigest(),
                      "duration_seconds": 2.0},
            "source": {"variant_id": "variant-fixture", "segment_id": "segment-fixture",
                       "variant_sha256": "a" * 64, "segment_sha256": "b" * 64},
            "model": {"receipt_path": str(receipt)},
            "rights": {
                "basis": "OWNER_AUTHORIZED", "receipt_id": reviewed.rights_receipt_ref,
                "consent_confirmed": False, "content_id": CONTENT,
                "canonical_url": URL, "record_id": reviewed.id,
                "policy_version": reviewed.policy_version,
                "record": {
                    "source_family": reviewed.source_family,
                    "rights_status": reviewed.rights_status,
                    "permitted_uses": list(reviewed.permitted_uses),
                    "attribution_requirements": [],
                    "reviewed_at": reviewed.reviewed_at,
                    "expires_at": reviewed.expires_at,
                    "reviewer_ref": reviewed.reviewer_ref,
                    "version_state": reviewed.version_state,
                },
            },
            "options": {"language": "it", "overlap_observed": False,
                        "timeout_seconds": 120},
        }
        self.path = self.root / "manifest.json"
        self.write()

    def write(self, manifest=None):
        self.path.write_text(json.dumps(self.manifest if manifest is None else manifest))

    def call(self, *extra):
        from tools.dp165_alignment_canary import main
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--manifest", str(self.path), *extra])
        return code, out.getvalue()

    def test_permitted_attestation_produces_a_private_hold_receipt_only(self):
        def synthetic_worker(*_args, **kwargs):
            kwargs["stdout"].write(json.dumps({"word_segments": WORDS}).encode("utf-8"))
            return SimpleNamespace(returncode=0)

        with patch("dichiarazioni_pubbliche.whisperx_alignment_private.platform.system",
                   return_value="Linux"), \
             patch("dichiarazioni_pubbliche.whisperx_alignment_private.importlib.metadata.version",
                   return_value="3.8.6"), \
             patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run",
                   side_effect=synthetic_worker):
            code, printed = self.call("--enabled")
        self.assertEqual(code, 0)
        receipt = json.loads(printed)
        self.assertEqual(receipt["status"], "REVIEW_CANDIDATE")
        self.assertEqual(receipt["candidate_source_kind"], "UNVERIFIED")
        self.assertTrue(receipt["publication_blocked"])
        self.assertFalse(receipt["source_span_review_ready"])
        # One operator preflight plus the three adapter boundaries.
        self.assertEqual(receipt["rights_guard_reads"], 4)
        self.assertEqual(receipt["rights_authority"], "PINNED_OPERATOR_ATTESTATION")
        for private in (TEXT, str(self.wav), str(self.root)):
            self.assertNotIn(private, printed)

    def test_service_host_gate_refuses_alignment_on_a_non_linux_work_host(self):
        with patch("dichiarazioni_pubbliche.whisperx_alignment_private.platform.system",
                   return_value="Darwin"):
            code, printed = self.call("--enabled")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(printed)["hold_code"], "WHISPERX_HOST_OR_OPT_IN_REQUIRED")
        self.assertNotIn(TEXT, printed)

    def test_revoked_or_expired_attestation_holds_without_running_the_engine(self):
        for change, code_name in (
            ({"rights_status": "REVOKED"}, "SOURCE_USE_REVOKED"),
            ({"expires_at": "2020-01-01T00:00:00+00:00"}, "SOURCE_USE_EXPIRED"),
            ({"permitted_uses": ["FETCH"]}, "SOURCE_USE_NOT_PERMITTED"),
        ):
            with self.subTest(change=change):
                manifest = json.loads(json.dumps(self.manifest))
                manifest["rights"]["record"].update(change)
                self.write(manifest)
                with patch("dichiarazioni_pubbliche.whisperx_alignment_private.platform.system",
                           return_value="Linux"), \
                     patch("dichiarazioni_pubbliche.whisperx_alignment_private.subprocess.run") as child:
                    code, printed = self.call("--enabled")
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(printed)["hold_code"], code_name)
                child.assert_not_called()
        self.write()

    def test_malformed_or_extended_manifest_is_refused_before_rights(self):
        for manifest in (
            {"manifest_version": "dp165-alignment-canary-v1"},
            dict(self.manifest, unexpected=True),
            dict(self.manifest, options={"language": "it"}),
        ):
            with self.subTest(manifest=sorted(manifest)):
                self.write(manifest)
                code, printed = self.call()
                self.assertEqual(code, 3)
                self.assertEqual(json.loads(printed)["status"], "INVALID_MANIFEST")
        self.write()
        self.assertEqual(self.call()[0], 2)


if __name__ == "__main__":
    unittest.main()

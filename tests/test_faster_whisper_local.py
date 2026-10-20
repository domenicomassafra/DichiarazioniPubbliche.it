"""DP-164: synthetic CPU adapter contracts; no model files are downloaded."""
import hashlib
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch

from dichiarazioni_pubbliche.faster_whisper_local import (
    FasterWhisperLocalTranscriber, _parse_result, _verified_model_receipt,
)
from dichiarazioni_pubbliche.local_inference_guard import local_inference_slot
from dichiarazioni_pubbliche.queue_runtime import ContentRecord, ProcessingJob
from dichiarazioni_pubbliche.remote_asr import AsrRequestRejected, AsrTransientError
from dichiarazioni_pubbliche.worker_daemon import ProcessingWorker, WorkerBudget
from tests.test_worker_daemon import FakeResolver, FakeStore, REGISTRY


class FasterWhisperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.audio_root = root / "authorized"
        self.audio_root.mkdir()
        self.audio = self.audio_root / "sample.wav"
        with wave.open(str(self.audio), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 16000)
        self.audio_sha = hashlib.sha256(self.audio.read_bytes()).hexdigest()
        self.model_dir = root / "model"
        self.model_dir.mkdir()
        for name, content in (("LICENSE", b"synthetic test fixture"),
                              ("config.json", b"{}"), ("model.bin", b"not real weights")):
            (self.model_dir / name).write_bytes(content)
        self.model_files = {
            name: hashlib.sha256((self.model_dir / name).read_bytes()).hexdigest()
            for name in ("LICENSE", "config.json", "model.bin")
        }
        self.receipt = {
            "model_id": "Systran/faster-whisper-small",
            "revision": "a" * 40,
            "model_dir": str(self.model_dir),
            "license_spdx": "MIT",
            "license_source_url": "https://example.org/pinned-review",
            "license_reviewed": True,
            "files": self.model_files,
        }
        self.receipt_path = root / "receipt.json"
        self.receipt_path.write_text(json.dumps(self.receipt))
        self.adapter = FasterWhisperLocalTranscriber(
            audio_root=self.audio_root, model_receipt_path=self.receipt_path)
        self.optin = patch.dict(os.environ, {
            "DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_ENABLED": "1",
            "SYNTHETIC_PROVIDER_SECRET": "never-pass-me",
        })
        self.host = patch.multiple(
            "dichiarazioni_pubbliche.faster_whisper_local.platform",
            system=lambda: "Linux", node=lambda: "udodo")

    def params(self):
        return dict(audio_path=str(self.audio), input_sha256=self.audio_sha,
                    rights_basis="OWNER_AUTHORIZED", rights_receipt_id="fixture:authorized:1",
                    authorization=True, consent_confirmed=False,
                    duration_seconds=1.0, language="it")

    def test_manifest_requires_license_pin_full_hash_inventory(self):
        self.assertEqual(_verified_model_receipt(self.receipt_path)[0]["files"], self.model_files)
        (self.model_dir / "extra.json").write_text("{}")
        with self.assertRaisesRegex(AsrRequestRejected, "INVENTORY_INVALID"):
            _verified_model_receipt(self.receipt_path)
        (self.model_dir / "extra.json").unlink()
        (self.model_dir / "model.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(AsrRequestRejected, "HASH_OR_BUDGET_INVALID"):
            _verified_model_receipt(self.receipt_path)
        (self.model_dir / "model.bin").write_bytes(b"not real weights")
        self.receipt["license_reviewed"] = False
        self.receipt_path.write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(AsrRequestRejected, "RIGHTS_UNVERIFIED"):
            _verified_model_receipt(self.receipt_path)

    def test_invalid_timestamps_and_sensitive_numbers_are_held(self):
        receipt, digest = _verified_model_receipt(self.receipt_path)
        for value in (
            {"segments": [{"start": -1, "end": 0.9, "text": "sette"}], "language": "it"},
            {"segments": [{"start": 0, "end": 99, "text": "sette"}], "language": "it"},
            {"segments": [{"start": 0, "end": 0.9, "text": "sette"}], "language": "en"},
        ):
            with self.assertRaises(AsrRequestRejected):
                _parse_result(value, duration=1, language="it", input_sha=self.audio_sha,
                              receipt=receipt, receipt_sha=digest)
        good = _parse_result({
            "segments": [{"start": 0, "end": 0.9, "text": "Il valore è 7,5."}],
            "language": "it",
        }, duration=1, language="it", input_sha=self.audio_sha,
            receipt=receipt, receipt_sha=digest)
        self.assertIn("7,5", good.text)
        self.assertEqual(good.segments[0].end_ms, 900)
        self.assertFalse(good.raw_response["publication_approved"])

    def test_permissions_hash_optin_and_shared_slot_fail_closed(self):
        with self.assertRaisesRegex(AsrRequestRejected, "OPT_IN_OR_HOST_REQUIRED"):
            self.adapter.transcribe(**self.params())
        with self.optin, self.host:
            for override, reason in (
                ({"authorization": False}, "RIGHTS_NOT_AUTHORIZED"),
                ({"rights_receipt_id": ""}, "RIGHTS_NOT_AUTHORIZED"),
                ({"rights_basis": "EXPLICIT_CONSENT"}, "RIGHTS_NOT_AUTHORIZED"),
                ({"input_sha256": "0" * 64}, "INPUT_HASH_MISMATCH"),
                ({"audio_path": None}, "AUDIO_PATH_INVALID"),
                ({"duration_seconds": 31}, "DURATION_INVALID"),
            ):
                with self.subTest(override=override), self.assertRaisesRegex(
                    AsrRequestRejected, reason
                ):
                    self.adapter.transcribe(**(self.params() | override))
            with patch("dichiarazioni_pubbliche.faster_whisper_local.importlib.metadata.version",
                       return_value="1.2.1"):
                with local_inference_slot():
                    with self.assertRaisesRegex(AsrTransientError, "LOCAL_INFERENCE_BUSY"):
                        self.adapter.transcribe(**self.params())

    def test_private_dispatch_receipts_and_no_secrets_to_child(self):
        class Store(FakeStore):
            def content(self, content_id):
                return ContentRecord(content_id, "youtube-pulp-podcast",
                                     "https://example.test/clip", "authorized sample",
                                     "2026-10-20", 1000, "DISCOVERED", {})

            def insert_transcript_variant(self, **kwargs):
                self.variant = kwargs
                return "variant:faster", True

            def insert_transcript_segments(self, **kwargs):
                self.segments = kwargs["segments"]

        class Private:
            def persist_asr_response(self, **kwargs):
                self.response = kwargs

        payload = dict(
            provider_id="faster-whisper-small-local", route="local/faster-whisper-small",
            canonical_url="https://example.test/clip",
            local_audio_path=str(self.audio), audio_sha256=self.audio_sha,
            rights_basis="OWNER_AUTHORIZED", rights_receipt_id="fixture:authorized:1",
            local_audio_authorized=True, consent_confirmed=False,
            duration_seconds=1.0, language="it", estimated_cost_usd=0.0)

        def invoke(changes):
            job = ProcessingJob("job:faster", "content:clip", "TRANSCRIPT_ACQUIRE_ASR",
                                0, payload | changes)
            store, private = Store([job]), Private()
            worker = ProcessingWorker(
                store=store, registry=REGISTRY, resolver=FakeResolver(),
                private_store=private, worker_id="dp164-tests", budget=WorkerBudget(),
                faster_whisper_asr=self.adapter)
            return worker.run(1), store, private

        with self.optin, self.host, patch(
            "dichiarazioni_pubbliche.faster_whisper_local.importlib.metadata.version",
            return_value="1.2.1"
        ), patch("dichiarazioni_pubbliche.faster_whisper_local.subprocess.run") as spawn:
            spawn.return_value.returncode = 0
            spawn.return_value.stdout = json.dumps({
                "segments": [{"start": 0, "end": 0.9, "text": "Il numero è 7,5."}],
                "language": "it"})
            outcome, store, private = invoke({})
            self.assertEqual(outcome.completed, 1)
            self.assertEqual(store.variant["source_kind"], "LOCAL_ASR")
            self.assertEqual(store.variant["provider_id"], "faster-whisper-small-local")
            self.assertEqual(store.variant["metadata"]["model_sha256"],
                             self.model_files["model.bin"])
            self.assertEqual(store.receipts[0]["estimated_cost_usd"], 0.0)
            self.assertEqual(store.followups[0]["job_type"], "TRANSCRIPT_CANONICALIZE")
            self.assertTrue(hasattr(private, "response"))
            self.assertNotIn("PUBLISHED", [event[1] for event in store.status_updates])
            self.assertNotIn("SYNTHETIC_PROVIDER_SECRET", spawn.call_args.kwargs["env"])
            self.assertEqual(spawn.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")
            self.assertEqual(spawn.call_args.kwargs["timeout"], 120)
            self.assertEqual(spawn.call_args.kwargs["preexec_fn"].__name__, "_limits")
            for update, reason in (({"local_audio_authorized": False}, "RIGHTS_NOT_AUTHORIZED"),
                                   ({"audio_sha256": "0" * 64}, "INPUT_HASH_MISMATCH"),
                                   ({"duration_seconds": 40}, "CONTENT_DURATION_MISMATCH")):
                with self.subTest(update=update):
                    result, blocked_store, _ = invoke(update)
                    self.assertEqual(result.blocked, 1)
                    self.assertIn(reason, blocked_store.block_reasons["job:faster"])
                    self.assertFalse(blocked_store.followups)
            with local_inference_slot():
                retried, store, _ = invoke({})
            self.assertEqual(retried.retried, 1)
            self.assertFalse(store.followups)

    def test_worker_failure_and_timeout_never_expose_native_stderr(self):
        with self.optin, self.host, patch(
            "dichiarazioni_pubbliche.faster_whisper_local.importlib.metadata.version",
            return_value="1.2.1"
        ), patch("dichiarazioni_pubbliche.faster_whisper_local.subprocess.run") as spawn:
            spawn.return_value.returncode = 1
            spawn.return_value.stderr = "SYNTHETIC_PROVIDER_SECRET=never-pass-me"
            with self.assertRaisesRegex(AsrRequestRejected, "^FASTER_WHISPER_ENGINE_FAILED$"):
                self.adapter.transcribe(**self.params())
            spawn.side_effect = TimeoutExpired(cmd="faster", timeout=120)
            with self.assertRaisesRegex(AsrRequestRejected, "^FASTER_WHISPER_TIMEOUT$"):
                self.adapter.transcribe(**self.params())


if __name__ == "__main__":
    unittest.main()

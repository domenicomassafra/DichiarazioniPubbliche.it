import hashlib
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.local_asr import (  # noqa: E402
    WhisperCppLocalTranscriber,
    parse_whisper_cpp_json,
)
from dichiarazioni_pubbliche.remote_asr import AsrRequestRejected  # noqa: E402
from dichiarazioni_pubbliche.queue_runtime import ContentRecord, ProcessingJob  # noqa: E402
from dichiarazioni_pubbliche.transcript_contract import (  # noqa: E402
    TranscriptCandidate, reconcile_candidates,
)
from dichiarazioni_pubbliche.worker_daemon import ProcessingWorker, WorkerBudget  # noqa: E402
from tests.test_worker_daemon import FakeResolver, FakeStore, REGISTRY  # noqa: E402


class LocalAsrTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio_root = self.root / "authorized"
        self.audio_root.mkdir()
        self.audio = self.audio_root / "sample.wav"
        with wave.open(str(self.audio), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 16000)
        self.audio_sha = hashlib.sha256(self.audio.read_bytes()).hexdigest()
        self.model = self.root / "ggml-test.bin"
        self.model.write_bytes(b"fixture model bytes")
        self.model_sha = hashlib.sha256(self.model.read_bytes()).hexdigest()
        self.cli = self.root / "whisper-cli"
        self.cli.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            "path=pathlib.Path(sys.argv[sys.argv.index('-of')+1]+'.json')\n"
            "path.write_text(json.dumps({'transcription':[{'offsets':{'from':0,'to':900},'text':'Hello world'}]}))\n"
        )
        self.cli.chmod(0o700)
        self.engine = WhisperCppLocalTranscriber(
            audio_root=self.audio_root, cli_path=self.cli,
            model_path=self.model, model_sha256=self.model_sha,
        )

    def params(self):
        return dict(
            audio_path=str(self.audio), input_sha256=self.audio_sha,
            rights_basis="PUBLIC_DOMAIN", rights_receipt_id="source:example:001",
            authorization=True, consent_confirmed=False,
            duration_seconds=1.0, language="en",
        )

    def test_normalizes_actual_subprocess_json_and_hash_receipts(self):
        result = self.engine.transcribe(**self.params())
        self.assertEqual(result.text, "Hello world")
        self.assertEqual(result.segments[0].end_ms, 900)
        self.assertIn(self.model_sha, result.model_id)
        self.assertTrue(result.request_id.startswith("local:"))

    def test_rejects_missing_authorization_and_unconfirmed_consent(self):
        for patch in (
            {"authorization": False},
            {"rights_receipt_id": ""},
            {"rights_basis": "UNKNOWN"},
            {"rights_basis": "EXPLICIT_CONSENT", "consent_confirmed": False},
        ):
            with self.subTest(patch=patch), self.assertRaisesRegex(
                AsrRequestRejected, "LOCAL_ASR_RIGHTS_NOT_AUTHORIZED"
            ):
                self.engine.transcribe(**(self.params() | patch))

    def test_rejects_hash_mismatch_symlinks_and_unapproved_path(self):
        other = self.root / "outside.wav"
        other.write_bytes(self.audio.read_bytes())
        alias = self.audio_root / "alias.wav"
        alias.symlink_to(self.audio)
        for patch, code in (
            ({"input_sha256": "0" * 64}, "LOCAL_ASR_INPUT_HASH_MISMATCH"),
            ({"audio_path": str(other)}, "LOCAL_ASR_AUDIO_PATH_INVALID"),
            ({"audio_path": str(alias)}, "LOCAL_ASR_AUDIO_PATH_INVALID"),
        ):
            with self.subTest(patch=patch), self.assertRaisesRegex(AsrRequestRejected, code):
                self.engine.transcribe(**(self.params() | patch))

    def test_rejects_model_mismatch_and_unconfigured_runtime(self):
        self.engine.model_sha256 = "0" * 64
        with self.assertRaisesRegex(AsrRequestRejected, "LOCAL_ASR_MODEL_HASH_MISMATCH"):
            self.engine.transcribe(**self.params())
        self.engine.model_path = None
        with self.assertRaisesRegex(AsrRequestRejected, "LOCAL_ASR_RUNTIME_NOT_CONFIGURED"):
            self.engine.transcribe(**self.params())

    def test_engine_failure_and_timeout_block_without_exposing_stderr(self):
        self.cli.write_text("#!/usr/bin/env python3\nimport sys\nprint('SECRET-STDERR', file=sys.stderr)\nsys.exit(4)\n")
        with self.assertRaisesRegex(AsrRequestRejected, "^LOCAL_ASR_ENGINE_FAILED$") as caught:
            self.engine.transcribe(**self.params())
        self.assertNotIn("SECRET", str(caught.exception))
        self.cli.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(2)\n")
        self.engine.timeout_seconds = 0.05
        with self.assertRaisesRegex(AsrRequestRejected, "^LOCAL_ASR_TIMEOUT$"):
            self.engine.transcribe(**self.params())

    def test_rejects_malformed_timestamps_and_excessive_audio(self):
        for offsets in ({"from": 0, "to": 1500}, {"from": -2, "to": 100},
                        {"from": "0", "to": 100}, {"from": 500, "to": 500}):
            with self.subTest(offsets=offsets), self.assertRaisesRegex(
                AsrRequestRejected, "LOCAL_ASR_TIMESTAMPS_INVALID"
            ):
                parse_whisper_cpp_json(
                    {"transcription": [{"offsets": offsets, "text": "test"}]},
                    duration_seconds=1, language="en",
                    model_sha256=self.model_sha, input_sha256=self.audio_sha,
                )
        with self.assertRaisesRegex(AsrRequestRejected, "LOCAL_ASR_DURATION_INVALID"):
            self.engine.transcribe(**(self.params() | {"duration_seconds": 31}))

    def test_worker_persists_local_candidate_with_provenance_and_no_publication(self):
        class Store(FakeStore):
            def content(self, content_id):
                return ContentRecord(
                    content_id, "youtube-pulp-podcast", "https://example.test/clip",
                    "bounded rights-cleared sample", "2026-10-10", 1000,
                    "DISCOVERED", {},
                )

            def insert_transcript_variant(self, **kwargs):
                self.variant = kwargs
                return "variant:local", True

            def insert_transcript_segments(self, **kwargs):
                self.segments = kwargs["segments"]

        class Private:
            def persist_asr_response(self, **kwargs):
                self.response = kwargs

        request = self.params()
        payload = dict(
            provider_id="whisper-cpp-local", route="local/whisper.cpp",
            canonical_url="https://example.test/clip",
            local_audio_path=request["audio_path"],
            audio_sha256=request["input_sha256"],
            rights_basis=request["rights_basis"],
            rights_receipt_id=request["rights_receipt_id"],
            local_audio_authorized=request["authorization"],
            consent_confirmed=request["consent_confirmed"],
            duration_seconds=1.0, language="en", estimated_cost_usd=0.0,
        )

        def run(update):
            job = ProcessingJob("job:local", "content:clip", "TRANSCRIPT_ACQUIRE_ASR", 0, payload | update)
            store = Store([job])
            private = Private()
            worker = ProcessingWorker(
                store=store, registry=REGISTRY, resolver=FakeResolver(),
                private_store=private, worker_id="local-test", budget=WorkerBudget(),
                local_asr=self.engine,
            )
            return worker.run(1), store, private

        summary, store, private = run({})
        self.assertEqual(summary.completed, 1)
        self.assertEqual(store.variant["source_kind"], "LOCAL_ASR")
        self.assertEqual(store.variant["metadata"]["input_audio_sha256"], self.audio_sha)
        self.assertEqual(store.variant["metadata"]["model_sha256"], self.model_sha)
        self.assertEqual(store.segments[0]["end_ms"], 900)
        self.assertEqual(store.receipts[0]["estimated_cost_usd"], 0)
        self.assertEqual(store.followups[0]["job_type"], "TRANSCRIPT_CANONICALIZE")
        self.assertTrue(hasattr(private, "response"))
        self.assertNotIn("PUBLISHED", [event[1] for event in store.status_updates])

        sensitive = reconcile_candidates((TranscriptCandidate(
            candidate_id="segment:local", provider_id="whisper-cpp-local",
            text="Il numero è 7.", start_ms=0, end_ms=900,
            source_kind="LOCAL_ASR",
        ),))
        self.assertTrue(sensitive.publication_blocked)
        self.assertFalse(sensitive.verbatim_eligible)

        for patch, reason in (
            ({"local_audio_authorized": False}, "LOCAL_ASR_RIGHTS_NOT_AUTHORIZED"),
            ({"duration_seconds": "invalid"}, "LOCAL_ASR_CONTENT_DURATION_MISMATCH"),
            ({"audio_sha256": "0" * 64}, "LOCAL_ASR_INPUT_HASH_MISMATCH"),
        ):
            with self.subTest(patch=patch):
                summary, store, private = run(patch)
                self.assertEqual(summary.blocked, 1)
                self.assertEqual(store.block_reasons["job:local"], reason)
                self.assertFalse(store.followups)
                self.assertFalse(store.receipts)


if __name__ == "__main__":
    unittest.main()

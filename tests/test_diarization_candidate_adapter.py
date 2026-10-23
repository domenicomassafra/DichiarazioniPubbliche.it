"""#166 local-only fixtures. These tests do not certify DP-208 or source rights."""

from __future__ import annotations

import hashlib
import functools
import resource
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.diarization_benchmark import (  # noqa: E402
    Decision, SensitiveSpan, Turn,
)
from dichiarazioni_pubbliche.diarization_candidate_adapter import (  # noqa: E402
    CandidateAuthorization, normalize_anonymous_turns, run_offline_candidate,
)
from dichiarazioni_pubbliche.diarization_candidate_benchmark import compare_private_candidate  # noqa: E402
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)


def sha(blob):
    return hashlib.sha256(blob if isinstance(blob, bytes) else blob.encode()).hexdigest()


URL = "https://example.test/synthetic-media"
CONTENT_ID = "content:local-fixture"


class FakePyannote:
    def __init__(self, *rows):
        self.rows = rows
        self.exclusive_speaker_diarization = "DO_NOT_USE_LOSES_OVERLAP"
        self.speaker_diarization = self

    def itertracks(self, *, yield_label):
        assert yield_label
        for start, end, label in self.rows:
            yield SimpleNamespace(start=start, end=end), "track", label


DEFAULT_ROWS = ((0.0, 4.0, "voice-of-person:private"),
                (4.0, 6.0, "speaker:secret-A"),
                (6.0, 10.0, "voice-of-person:private"))


def fixture_runner(_media, _model, *, rows=DEFAULT_ROWS, kind="PYANNOTE_AUDIO"):
    if kind == "DIARIZE_CPU":
        return SimpleNamespace(segments=[
            SimpleNamespace(start=a, end=b, speaker=speaker) for a, b, speaker in rows
        ])
    if kind == "SPOOFED":
        return SimpleNamespace(exclusive_speaker_diarization="unsafe")
    return FakePyannote(*rows)


def runner_with(rows=DEFAULT_ROWS, *, kind="PYANNOTE_AUDIO"):
    return functools.partial(fixture_runner, rows=rows, kind=kind)


def hung_runner(_media, _model):
    while True:
        time.sleep(0.1)


def memory_hog_runner(_media, _model):
    blocks = []
    while True:
        blocks.append(bytearray(8 * 1024 * 1024))


def oversized_stdout_runner(_media, _model):
    sys.stdout.write("x" * (256 * 1024))
    sys.stdout.flush()
    return FakePyannote(*DEFAULT_ROWS)


def permission_guard(*, hash_source, allowed=("STORE_BODY", "ASR_MEDIA"), status="CLEARED"):
    subject = RightsSubject(
        source_family="SYNTHETIC_LOCAL_TEST", locator_kind="URL",
        locator_value=URL, content_id=CONTENT_ID,
    )
    record = PrivateRightsRecord(
        id="rights:synthetic", subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family, locator_kind="URL",
        locator_value=URL, content_id=CONTENT_ID, evidence_id=None,
        transcript_segment_id=None, canonical_segment_id=None, passage_id=None,
        rights_status=status, rights_receipt_ref="synthetic:receipt",
        permitted_uses=allowed, attribution_requirements=(),
        reviewed_at="2026-10-18T00:00:00+00:00",
        expires_at="2027-10-20T00:00:00+00:00", reviewer_ref="synthetic:operator",
        policy_version="test-policy-v1", record_visibility="PRIVATE",
        supersedes_id=None, version_state="CURRENT",
    )
    return SourceFamilyUseGuard(
        read_current=lambda _: record, subject=subject,
        rights_record_id=record.id, policy_version=record.policy_version,
        expected_sha256=hash_source,
        clock=lambda: datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


def sample_permit(*, audio_sha, model_sha, engine="PYANNOTE_AUDIO", decision="GO"):
    return CandidateAuthorization(
        dp208_decision=Decision(decision, (), ("SYNTHETIC_GATE",)),
        decision_receipt_sha256=sha("synthetic-decision"),
        reference_sha256=sha("synthetic-reference"),
        reviewer_ref="synthetic:reviewer", source_rights_receipt_sha256=sha("synthetic-rights"),
        model_terms_receipt_sha256=sha("synthetic-terms"),
        engine_id=engine, engine_version="4.0.7" if engine == "PYANNOTE_AUDIO" else "0.1.2",
        model_id="synthetic:offline-weight-file", model_sha256=model_sha,
        model_license="CC-BY-4.0" if engine == "PYANNOTE_AUDIO" else "APACHE-2.0",
        config_sha256=sha("synthetic-config"), input_sha256=audio_sha,
        # Importing a synthetic fixture in a fresh interpreter may be slower
        # during the full 3k+ unittest suite on an I/O-busy MiniPC.
        max_elapsed_ms=15000, max_peak_rss_bytes=8 * 1024**3,
        max_cache_bytes=4096, max_audio_duration_ms=10000,
    )


class CandidateAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.audio = root / "synthetic.wav"
        self.audio.write_bytes(b"fixture-audio-no-voice")
        self.model_dir = root / "model"
        self.model_dir.mkdir()
        (self.model_dir / "weights.example").write_bytes(b"synthetic-weight-not-real")
        # Independently reconstruct the documented byte/path digest, no import
        # of the production private helper.
        relative = b"weights.example"
        self.model_sha = hashlib.sha256(
            len(relative).to_bytes(4, "big") + relative + b"synthetic-weight-not-real"
        ).hexdigest()
        self.source_sha = sha(self.audio.read_bytes())
        self.permit = sample_permit(audio_sha=self.source_sha, model_sha=self.model_sha)
        self.reference = (
            Turn(0, 4000, "TURN_00", self.source_sha),
            Turn(4000, 6000, "TURN_01", self.source_sha),
            Turn(6000, 10000, "TURN_00", self.source_sha),
        )

    def call(self, *, permit=None, runner=None, rights=None, **overrides):
        args = dict(
            permit=self.permit if permit is None else permit,
            approval_check=lambda _: True,
            media_path=self.audio, model_dir=self.model_dir, duration_ms=10000,
            content_id=CONTENT_ID, source_url=URL,
            source_use_guard=permission_guard(hash_source=self.source_sha),
            offline_runner=runner or runner_with(),
        )
        if rights is not None:
            args["source_use_guard"] = rights
        args.update(overrides)
        return run_offline_candidate(**args)

    def test_preflight_no_go_missing_decision_terms_rights_never_invokes_model(self):
        calls = []
        def engine(*_args):
            calls.append(True)
            return FakePyannote((0, 10, "a"))

        blocked = (
            dict(permit="MISSING"),
            dict(permit=replace(self.permit, dp208_decision=Decision("NO_GO", (), ()))),
            dict(permit=replace(self.permit, model_terms_receipt_sha256="missing")),
            dict(permit=replace(self.permit, model_sha256=sha("different"))),
            dict(permit=replace(self.permit, max_audio_duration_ms=8000)),
            dict(approval_check=lambda _: False),
            dict(approval_check=None),
            dict(rights=permission_guard(hash_source=self.source_sha, status="REVOKED")),
            dict(rights=permission_guard(hash_source=self.source_sha, allowed=("STORE_BODY",))),
            dict(observed_network_calls=1),
        )
        for change in blocked:
            with self.subTest(change=change):
                result = self.call(runner=engine, **change)
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.turns, ())
                self.assertIsNone(result.speaker_person_id)
        self.assertEqual(calls, [])

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_output_anonymization_source_hash_resource_receipt_and_replay(self):
        a = self.call()
        b = self.call()
        self.assertEqual(a.status, "CURRENT_HELD")
        self.assertEqual(a.turns, self.reference)
        self.assertEqual(a.normalized_sha256, b.normalized_sha256)
        self.assertFalse(a.public_quote_eligible)
        self.assertEqual(a.review_state, "POLICY_HOLD")
        self.assertTrue(all(t.speaker_label.startswith("TURN_") for t in a.turns))
        self.assertNotIn("person:", repr(a))
        self.assertEqual(a.resource.engine_version, "4.0.7")
        self.assertEqual(a.resource.network_calls, 0)
        self.assertEqual(a.resource.model_sha256, self.model_sha)
        self.assertGreater(a.resource.peak_rss_bytes, 0)
        self.assertEqual(a.resource.cache_bytes, len(b"synthetic-weight-not-real"))

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_pyannote_overlap_is_preserved_and_abstained(self):
        output = self.call(runner=runner_with(((0.0, 6.2, "secret-first"),
                                               (5.9, 10.0, "secret-other"))))
        self.assertEqual(output.overlap_intervals_ms, ((5900, 6200),))
        self.assertEqual(output.abstention_intervals_ms, ((5900, 6200),))
        self.assertIn("OVERLAP_REVIEW_REQUIRED", output.codes)
        self.assertNotIn("secret-first", repr(output))
        self.assertEqual(output.review_state, "POLICY_HOLD")

    def test_model_tamper_audio_tamper_or_symlink_blocks_before_inference(self):
        calls = []
        engine = lambda *_: calls.append(True)
        self.audio.write_bytes(b"changed")
        self.assertEqual(self.call(runner=engine).codes, ("AUDIO_HASH_DRIFT",))
        self.audio.write_bytes(b"fixture-audio-no-voice")
        (self.model_dir / "weights.example").write_bytes(b"changed")
        self.assertEqual(self.call(runner=engine).codes, ("MODEL_HASH_DRIFT",))
        (self.model_dir / "weights.example").write_bytes(b"synthetic-weight-not-real")
        (self.model_dir / "alias").symlink_to(self.audio)
        self.assertEqual(self.call(runner=engine).codes, ("LOCAL_MODEL_UNAVAILABLE_OR_OVER_BUDGET",))
        self.assertEqual(calls, [])

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_invalid_time_spoofed_output_and_empty_abstain_fail_closed(self):
        for result in (
            FakePyannote((-1.0, 2.0, "A")),
            FakePyannote((2.0, 1.0, "A")),
            FakePyannote((0.0, float("nan"), "A")),
            FakePyannote((0.0, 11.0, "A")),
            SimpleNamespace(exclusive_speaker_diarization="unsafe"),
        ):
            with self.subTest(result=result):
                runner = runner_with(kind="SPOOFED") if not isinstance(result, FakePyannote) else runner_with(result.rows)
                self.assertEqual(self.call(runner=runner).status, "ERROR_HELD")
        self.assertEqual(self.call(runner=runner_with(())).status, "ABSTAIN_HELD")
        self.assertEqual(self.call(runner=runner_with(())).abstention_intervals_ms, ((0, 10000),))
        seven_speakers = FakePyannote(*(
            (float(i), float(i + 1), f"anonymous-{i}") for i in range(7)
        ))
        self.assertEqual(self.call(runner=runner_with(seven_speakers.rows)).status, "ERROR_HELD")

    def test_cpu_memory_overrun_suppresses_turns_even_with_favorable_output(self):
        result = self.call(permit=replace(self.permit, max_peak_rss_bytes=1024))
        self.assertEqual(result.status, "ERROR_HELD")
        self.assertTrue(any(code in result.codes for code in (
            "ENGINE_FAILED_OR_LIMIT", "ENGINE_PROCESS_START_FAILED",
            "ENGINE_ADDRESS_SPACE_LIMIT_UNAVAILABLE",
        )))
        self.assertEqual(result.turns, ())

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_runner_hang_is_killed_before_wall_deadline(self):
        start = time.monotonic()
        result = self.call(runner=hung_runner, permit=replace(self.permit, max_elapsed_ms=200))
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertEqual(result.status, "ERROR_HELD")
        self.assertIn("ENGINE_TIMEOUT", result.codes)
        self.assertEqual(result.turns, ())

    def test_memory_hog_is_bounded_in_child_only(self):
        start = time.monotonic()
        parent_as = resource.getrlimit(resource.RLIMIT_AS)
        # The child imports the test module before it allocates, so a deadline
        # sized for the allocation alone races the import on a slow or loaded
        # host and reports ENGINE_TIMEOUT instead of the memory containment.
        result = self.call(runner=memory_hog_runner, permit=replace(
            self.permit, max_peak_rss_bytes=128 * 1024 * 1024, max_elapsed_ms=5000,
        ))
        self.assertLess(time.monotonic() - start, 8.0)
        self.assertEqual(result.status, "ERROR_HELD")
        self.assertEqual(result.turns, ())
        if sys.platform == "linux":
            self.assertEqual(result.codes, ("ENGINE_FAILED_OR_LIMIT",))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), parent_as)

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_FSIZE required")
    def test_stdout_flood_cannot_escape_result_size_cap(self):
        result = self.call(runner=oversized_stdout_runner)
        self.assertEqual(result.status, "ERROR_HELD")
        self.assertEqual(result.turns, ())
        self.assertEqual(result.codes, ("ENGINE_FAILED_OR_LIMIT",))

    def test_local_closure_never_executes_inline(self):
        called = []
        def unsafe_runner(*_args):
            called.append(True)
            return FakePyannote(*DEFAULT_ROWS)
        result = self.call(runner=unsafe_runner)
        self.assertEqual(result.status, "ERROR_HELD")
        self.assertEqual(result.turns, ())
        self.assertEqual(called, [])

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_bounded_dp208_retains_policy_hold_and_never_identity(self):
        result = self.call(permit=replace(
            self.permit, dp208_decision=Decision("GO_BOUNDED", (), ("SENSITIVE_SPAN_UNCERTAIN",)),
        ))
        self.assertEqual(result.status, "CURRENT_HELD")
        self.assertIn("DP208_BOUNDED_POLICY_HOLD", result.codes)
        self.assertIsNone(result.speaker_person_id)

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_diarize_cpu_output_never_promotes_unmapped_label(self):
        rows = SimpleNamespace(segments=[
            SimpleNamespace(start=0.0, end=4.0, speaker="John Doe"),
            SimpleNamespace(start=4.0, end=10.0, speaker="Jane Doe"),
        ])
        result = self.call(
            permit=sample_permit(audio_sha=self.source_sha, model_sha=self.model_sha, engine="DIARIZE_CPU"),
            runner=runner_with(((0.0, 4.0, "John Doe"), (4.0, 10.0, "Jane Doe")), kind="DIARIZE_CPU"),
        )
        self.assertEqual(result.status, "CURRENT_HELD")
        self.assertEqual([t.speaker_label for t in result.turns], ["TURN_00", "TURN_01"])
        self.assertNotIn("Doe", repr(result))

    @unittest.skipUnless(sys.platform == "linux", "Linux RLIMIT_AS required for execution")
    def test_baseline_vs_candidate_f1_der_swap_overlap_critical_and_sensitive(self):
        perfect = self.call()
        evaluated = compare_private_candidate(
            reference=self.reference, baseline=(Turn(0, 10000, "TURN_00", self.source_sha),),
            candidate=perfect, inserted_clip_start_ms=4000, inserted_clip_end_ms=6000,
            resource_budget_ok=True,
        )
        self.assertEqual(evaluated.status, "CONTRACT_ONLY_HELD")
        self.assertEqual(evaluated.candidate_with_collar.der, 0)
        self.assertEqual(evaluated.candidate_with_collar.speaker_change_f1, 1)
        self.assertGreater(evaluated.baseline_with_collar.der, 0)
        self.assertEqual(evaluated.proposed_decision, "GO")
        self.assertFalse(evaluated.publication_authority)
        self.assertIsNotNone(evaluated.receipt_sha256)

        swapped = self.call(runner=runner_with(((0, 4000 / 1000, "first"), (4, 6, "second"),
                                                (6, 8, "first"), (8, 10, "second"))))
        report = compare_private_candidate(
            reference=self.reference, baseline=self.reference, candidate=swapped,
            inserted_clip_start_ms=4000, inserted_clip_end_ms=6000,
            sensitive_spans=(SensitiveSpan(8500, 9000, "NUMBER"),),
            resource_budget_ok=True,
        )
        self.assertGreater(report.candidate_with_collar.confusion_ms, 0)
        self.assertTrue(report.sensitive_hold)
        self.assertIn("NUMBER_SPEAKER_CONFUSION", report.reason_codes)

        overlap_ref = (*self.reference, Turn(5500, 6200, "TURN_00", self.source_sha))
        report = compare_private_candidate(
            reference=overlap_ref, baseline=overlap_ref, candidate=perfect,
            inserted_clip_start_ms=4000, inserted_clip_end_ms=6000,
            resource_budget_ok=True,
        )
        self.assertEqual(report.proposed_decision, "NO_GO")
        self.assertIn("REFERENCE_OVERLAP_MISSED", report.reason_codes)
        blocked = compare_private_candidate(
            reference=self.reference, baseline=self.reference, candidate=perfect,
            inserted_clip_start_ms=4000, inserted_clip_end_ms=6000,
            resource_budget_ok=False,
        )
        self.assertEqual(blocked.status, "BLOCKED")
        too_many = tuple(Turn(i * 1000, (i + 1) * 1000, f"TURN_{i:02d}", self.source_sha)
                         for i in range(7))
        self.assertEqual(compare_private_candidate(
            reference=too_many, baseline=too_many, candidate=perfect,
            inserted_clip_start_ms=4000, inserted_clip_end_ms=6000,
            resource_budget_ok=True,
        ).status, "BLOCKED")


    def test_symlinked_parent_of_media_or_model_is_refused(self):
        link = self.audio.parent / "external-parent"
        link.symlink_to(self.audio.parent, target_is_directory=True)
        self.assertEqual(self.call(media_path=link / self.audio.name).codes, ("AUDIO_NOT_LOCAL",))
        self.assertEqual(self.call(model_dir=link / "model").codes, ("AUDIO_NOT_LOCAL",))

    @unittest.skipUnless(sys.platform == "linux", "Linux isolation required")
    def test_revoked_rights_after_runner_blocked(self):
        guard = permission_guard(hash_source=self.source_sha)
        original_reader = guard.read_current
        seen = 0

        def mutable_record(subject):
            nonlocal seen
            seen += 1
            record = original_reader(subject)
            return replace(record, rights_status="REVOKED") if seen >= 3 else record

        guard.read_current = mutable_record
        result = self.call(rights=guard)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.codes, ("SOURCE_USE_REVOKED",))
        self.assertEqual(result.turns, ())

    @unittest.skipUnless(sys.platform == "linux", "Linux namespace required")
    def test_sandbox_host_files_hidden(self):
        import shutil
        import subprocess
        from dichiarazioni_pubbliche.diarization_candidate_process import (
            RunnerIsolationError, _real_sandbox_prefix,
        )

        if not shutil.which("bwrap") or not Path("/usr/bin/python3").exists():
            with self.assertRaisesRegex(RunnerIsolationError, "ENGINE_NETNS_REQUIRED"):
                _real_sandbox_prefix(self.audio, self.model_dir)
            return
        script = ("from pathlib import Path; print("
                  f"Path('/etc/passwd').exists(), Path({str(self.audio)!r}).is_file(), "
                  f"Path({str(self.model_dir)!r}).is_dir())")
        probe = subprocess.run(
            [*_real_sandbox_prefix(self.audio, self.model_dir), "--", sys.executable, "-c", script],
            check=True, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(probe.stdout.strip(), "False True True")


if __name__ == "__main__":
    unittest.main()

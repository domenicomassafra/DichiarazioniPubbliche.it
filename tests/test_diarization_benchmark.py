import hashlib
import sys
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.diarization_benchmark import (  # noqa: E402
    ResourceReceipt,
    SensitiveSpan,
    Turn,
    compute_metrics,
    decide,
    evaluate_safety,
    receipt_fingerprint,
)


INPUT = hashlib.sha256(b"synthetic-cleared-audio-v1").hexdigest()
MODEL = hashlib.sha256(b"synthetic-engine").hexdigest()
CONFIG = hashlib.sha256(b"collar=250").hexdigest()


def turn(start, end, label):
    return Turn(start, end, label, INPUT)


REFERENCE = (
    turn(0, 4000, "TURN_00"),
    turn(4000, 6000, "TURN_01"),
    turn(6000, 10000, "TURN_00"),
)


class DiarizationBenchmarkTests(unittest.TestCase):
    def resource(self, **overrides):
        values = dict(
            engine_id="synthetic",
            engine_version="1",
            model_id="fixture",
            model_sha256=MODEL,
            config_sha256=CONFIG,
            input_sha256=INPUT,
            elapsed_ms=100,
            peak_rss_bytes=1024,
            cache_bytes=0,
            license_status="APPROVED",
            network_calls=0,
        )
        values.update(overrides)
        return ResourceReceipt(**values)

    def test_exact_anonymous_turns_have_zero_der_and_perfect_change_f1(self):
        metrics = compute_metrics(REFERENCE, REFERENCE)
        self.assertEqual(metrics.der, 0)
        self.assertEqual(metrics.speaker_change_f1, 1)
        self.assertEqual(metrics.missed_speech_ms, 0)
        self.assertEqual(metrics.false_alarm_ms, 0)
        self.assertEqual(metrics.confusion_ms, 0)

    def test_label_permutation_is_not_identity_error(self):
        hypothesis = (
            turn(0, 4000, "TURN_09"),
            turn(4000, 6000, "TURN_08"),
            turn(6000, 10000, "TURN_09"),
        )
        self.assertEqual(compute_metrics(REFERENCE, hypothesis).der, 0)

    def test_missing_speech_false_alarm_and_confusion_are_separate(self):
        missing = (turn(0, 4000, "TURN_00"), turn(6000, 10000, "TURN_00"))
        self.assertEqual(compute_metrics(REFERENCE, missing).missed_speech_ms, 2000)

        false_alarm_reference = (turn(1000, 4000, "TURN_00"),)
        false_alarm_hypothesis = (turn(0, 4000, "TURN_00"),)
        self.assertEqual(
            compute_metrics(false_alarm_reference, false_alarm_hypothesis).false_alarm_ms,
            1000,
        )

        confused = (turn(0, 10000, "TURN_00"),)
        self.assertGreater(compute_metrics(REFERENCE, confused).confusion_ms, 0)

    def test_boundary_collar_matches_200ms_drift_but_not_300ms(self):
        within = (
            turn(0, 4200, "TURN_00"),
            turn(4200, 6200, "TURN_01"),
            turn(6200, 10000, "TURN_00"),
        )
        outside = (
            turn(0, 4300, "TURN_00"),
            turn(4300, 6300, "TURN_01"),
            turn(6300, 10000, "TURN_00"),
        )
        self.assertEqual(compute_metrics(REFERENCE, within).speaker_change_recall, 1)
        self.assertEqual(compute_metrics(REFERENCE, within).boundary_mean_abs_error_ms, 200)
        self.assertEqual(compute_metrics(REFERENCE, outside).speaker_change_recall, 0)

    def test_inserted_clip_merge_is_critical_failure(self):
        merged = (turn(0, 10000, "TURN_00"),)
        safety = evaluate_safety(
            REFERENCE,
            merged,
            inserted_clip_start_ms=4000,
            inserted_clip_end_ms=6000,
        )
        self.assertFalse(safety.inserted_clip_separate)
        decision = decide(
            baseline=compute_metrics(REFERENCE, merged),
            candidate=compute_metrics(REFERENCE, merged),
            safety=safety,
            resources=self.resource(),
            resource_budget_ok=True,
            license_approved=True,
        )
        self.assertEqual(decision.decision, "NO_GO")
        self.assertIn("CRITICAL_INSERTED_CLIP_MERGED", decision.failed_gates)

    def test_sensitive_span_confusion_forces_bounded_hold(self):
        candidate = (
            turn(0, 4000, "TURN_00"),
            turn(4000, 5900, "TURN_01"),
            turn(5900, 10000, "TURN_00"),
        )
        safety = evaluate_safety(
            REFERENCE,
            candidate,
            inserted_clip_start_ms=4000,
            inserted_clip_end_ms=6000,
            sensitive_spans=(SensitiveSpan(5950, 6050, "NUMBER"),),
        )
        self.assertTrue(safety.sensitive_span_hold_required)
        self.assertTrue(any(code.startswith("NUMBER_") for code in safety.sensitive_span_codes))

    def test_decision_has_go_bounded_and_no_go_paths_without_composite_score(self):
        perfect = compute_metrics(REFERENCE, REFERENCE)
        clear = evaluate_safety(
            REFERENCE,
            REFERENCE,
            inserted_clip_start_ms=4000,
            inserted_clip_end_ms=6000,
        )
        go = decide(
            baseline=perfect,
            candidate=perfect,
            safety=clear,
            resources=self.resource(),
            resource_budget_ok=True,
            license_approved=True,
        )
        self.assertEqual(go.decision, "GO")
        bounded_safety = clear.__class__(True, True, ("NUMBER_TURN_UNCERTAIN",))
        bounded = decide(
            baseline=perfect,
            candidate=perfect,
            safety=bounded_safety,
            resources=self.resource(),
            resource_budget_ok=True,
            license_approved=True,
        )
        self.assertEqual(bounded.decision, "GO_BOUNDED")
        no_go = decide(
            baseline=perfect,
            candidate=perfect,
            safety=clear,
            resources=self.resource(network_calls=1),
            resource_budget_ok=True,
            license_approved=True,
        )
        self.assertEqual(no_go.decision, "NO_GO")
        self.assertFalse(hasattr(no_go, "score"))

    def test_resource_receipt_refuses_biometric_identity_features(self):
        with self.assertRaisesRegex(ValueError, "BIOMETRIC_IDENTITY_FORBIDDEN"):
            self.resource(identity_features_present=True)

    def test_timestamp_hash_and_timebase_fail_closed(self):
        for kwargs in (
            {"start_ms": -1, "end_ms": 10, "speaker_label": "TURN_00", "input_sha256": INPUT},
            {"start_ms": 10, "end_ms": 10, "speaker_label": "TURN_00", "input_sha256": INPUT},
            {"start_ms": 0, "end_ms": 10, "speaker_label": "Mario Rossi", "input_sha256": INPUT},
            {"start_ms": 0, "end_ms": 10, "speaker_label": "TURN_00", "input_sha256": "bad"},
            {"start_ms": 0, "end_ms": 10, "speaker_label": "TURN_00", "input_sha256": INPUT, "timebase": "SECONDS"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Turn(**kwargs)

    def test_receipt_fingerprint_is_deterministic_and_input_sensitive(self):
        receipt = asdict(self.resource())
        first = receipt_fingerprint(receipt)
        second = receipt_fingerprint(dict(reversed(list(receipt.items()))))
        self.assertEqual(first, second)
        changed = dict(receipt)
        changed["input_sha256"] = "f" * 64
        self.assertNotEqual(first, receipt_fingerprint(changed))


if __name__ == "__main__":
    unittest.main()

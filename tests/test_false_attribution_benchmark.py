from __future__ import annotations

import copy
import hashlib
import json
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.false_attribution_benchmark import (  # noqa: E402
    DEFAULT_FIXTURE,
    REQUIRED_CLASSES,
    FixtureDriftError,
    load_fixture,
    main,
    run_benchmark,
)


def _fixture_digest(payload: dict) -> str:
    material = copy.deepcopy(payload)
    material.pop("integrity", None)
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FalseAttributionBenchmarkFixtureTests(unittest.TestCase):
    def test_fixture_is_versioned_hand_labeled_and_covers_every_required_class(self):
        fixture = load_fixture()
        self.assertEqual(fixture["schema_version"], "dp-223-adversarial-benchmark/v1")
        self.assertRegex(fixture["fixture_version"], r"^\d{4}-\d{2}-\d{2}\.\d+$")
        self.assertIn("independent hand-labeled", fixture["provenance"]["labeling"])
        self.assertFalse(fixture["provenance"]["network_required"])
        self.assertFalse(fixture["provenance"]["provider_required"])

        variants = {name: set() for name in REQUIRED_CLASSES}
        for case in fixture["cases"]:
            variants[case["class"]].add(case["variant"])
            expected = case["expected"]
            self.assertEqual(expected["source_id"], case["source"]["source_id"])
            self.assertEqual(expected["source_sha256"], case["source"]["sha256"])
            self.assertEqual(expected["span_start"], case["span"]["start"])
            self.assertEqual(expected["span_end"], case["span"]["end"])
            self.assertEqual(expected["span_sha256"], case["span"]["sha256"])
            self.assertIn(
                expected["publication_state"],
                {"PUBLIC", "HELD", "OMITTED", "UNRESOLVED"},
            )
            self.assertIn(
                expected["wording_type"],
                {
                    "VERBATIM_ORIGINAL",
                    "REPORTED_QUOTE",
                    "PARAPHRASE",
                    "SUMMARY",
                    "TRANSLATION",
                },
            )

        self.assertEqual(set(variants), set(REQUIRED_CLASSES))
        self.assertTrue(
            all(value == {"ADVERSARIAL", "CONTROL"} for value in variants.values())
        )

    def test_source_or_expected_hash_drift_invalidates_authored_approvals(self):
        base = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            source_drift = copy.deepcopy(base)
            source_drift["cases"][0]["source"]["text"] += " Mutazione."
            source_drift["integrity"]["fixture_sha256"] = _fixture_digest(source_drift)
            source_path = Path(tmp) / "source-drift.json"
            source_path.write_text(json.dumps(source_drift), encoding="utf-8")
            with self.assertRaisesRegex(FixtureDriftError, "DP223_SOURCE_HASH_DRIFT"):
                load_fixture(source_path)

            approval_drift = copy.deepcopy(base)
            approval_drift["cases"][0]["expected"]["source_sha256"] = "0" * 64
            approval_drift["integrity"]["fixture_sha256"] = _fixture_digest(
                approval_drift
            )
            approval_path = Path(tmp) / "approval-drift.json"
            approval_path.write_text(json.dumps(approval_drift), encoding="utf-8")
            with self.assertRaisesRegex(
                FixtureDriftError, "DP223_EXPECTED_APPROVAL_DRIFT"
            ):
                load_fixture(approval_path)


class FalseAttributionBenchmarkExecutionTests(unittest.TestCase):
    def test_release_gate_is_zero_tolerance_and_metrics_remain_separate(self):
        report = run_benchmark()
        self.assertTrue(report.release_gate_passed)
        self.assertTrue(report.benchmark_passed)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(report.metrics["known_false_public_attribution"], 0)
        self.assertEqual(report.metrics["fabricated_public_quote"], 0)
        self.assertEqual(report.metrics["context_review_escape_count"], 0)
        self.assertEqual(report.metrics["stale_provenance_escape_count"], 0)
        for key in (
            "correct_public_occurrences",
            "correct_holds_or_abstentions",
            "false_holds",
            "unresolved_cases",
            "quote_span_exact_match_rate",
            "speaker_span_coverage_rate",
        ):
            self.assertIn(key, report.metrics)
        for forbidden in ("trust_score", "quality_score", "composite_score"):
            self.assertNotIn(forbidden, report.metrics)

    def test_replay_is_byte_for_byte_deterministic_as_structured_output(self):
        first = run_benchmark().to_dict()
        second = run_benchmark().to_dict()
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(second, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def test_cli_runs_without_network_or_provider_calls(self):
        def deny_network(*_args, **_kwargs):
            raise AssertionError("DP-223 benchmark attempted a network call")

        output = StringIO()
        with mock.patch.object(socket, "create_connection", side_effect=deny_network):
            with redirect_stdout(output):
                exit_code = main(["--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["benchmark_passed"])
        self.assertEqual(payload["metrics"]["known_false_public_attribution"], 0)
        self.assertEqual(payload["metrics"]["fabricated_public_quote"], 0)

    def test_real_gate_families_are_exercised_by_the_fixture(self):
        fixture = load_fixture()
        self.assertEqual(
            {case["gate"] for case in fixture["cases"]},
            {
                "quote_binding",
                "context_integrity",
                "wording",
                "translation",
                "public_attribution",
                "citation_assurance",
                "original_source",
                "excerpt_rights",
                "challenger_readiness",
            },
        )


if __name__ == "__main__":
    unittest.main()

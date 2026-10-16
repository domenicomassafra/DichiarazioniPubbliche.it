"""DP-244: readable inventory must not silently equate polls with coverage."""

import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "source_coverage_report",
    Path(__file__).resolve().parents[1] / "tools" / "source_coverage_report.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class SourceCoverageReportTests(unittest.TestCase):
    def test_unknown_windows_and_healthy_attempts_are_not_full_coverage(self):
        row = {
            "source_id": "source:official",
            "canonical_name": "Camera | archivio",
            "source_type": "OFFICIAL",
            "language": "it",
            "attempts": 2,
            "first_attempt_date": "2026-10-12",
            "last_attempt_date": "2026-10-16",
            "healthy_attempts": 1,
            "blocked_attempts": 1,
            "other_attempts": 0,
            "content_rows": 4,
            "capture_rows": 0,
        }
        report = module.render_report(
            module.validate_inventory([row]),
            generated_at="2026-10-16T21:00:00+00:00",
        )
        self.assertIn("Camera \\| archivio", report)
        self.assertIn("2026-10-12 → 2026-10-16", report)
        self.assertIn("Nessun intervallo è dichiarato *coperto integralmente*", report)
        self.assertIn("periodi non enumerati", report)

    def test_missing_source_poll_keeps_explicit_gap(self):
        row = {
            "source_id": "source:missing",
            "canonical_name": "Senza poll",
            "source_type": "UNKNOWN",
            "language": None,
            "attempts": 0,
            "first_attempt_date": None,
            "last_attempt_date": None,
            "healthy_attempts": 0,
            "blocked_attempts": 0,
            "other_attempts": 0,
            "content_rows": 0,
            "capture_rows": 0,
        }
        self.assertIn(
            "nessuna osservazione",
            module.render_report(
                module.validate_inventory([row]),
                generated_at="test",
            ),
        )
        with self.assertRaisesRegex(ValueError, "WINDOW_INVALID"):
            module.validate_inventory([{**row, "first_attempt_date": "2026-10-16"}])
        with self.assertRaisesRegex(ValueError, "ATTEMPTS_INVALID"):
            module.validate_inventory(
                [
                    {
                        **row,
                        "attempts": 1,
                        "last_attempt_date": "2026-10-16",
                        "first_attempt_date": "2026-10-16",
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()

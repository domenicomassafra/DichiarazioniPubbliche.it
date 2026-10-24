"""DP-244 canary must gate each pinned version by its own licence."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import dp244_refresh_cycle_canary as canary


class CanaryVersionRightsTests(unittest.TestCase):
    def run_with_historical_terms(self, historical_terms: bytes):
        calls: list[str] = []

        def fake_http(url: str, headers: tuple[tuple[str, str], ...]):
            calls.append(url)
            if url == canary.README_URL:
                return canary.HttpResult(200, url, b"Licenza: CC BY 4.0")
            if url == canary.PREVIOUS_README_URL:
                return canary.HttpResult(200, url, historical_terms)
            if url == canary.PREVIOUS_URL:
                return canary.HttpResult(200, url, b"<akn>2025</akn>", '"old-etag"')
            if url == canary.CURRENT_URL:
                if any(key.lower() == "if-none-match" for key, _ in headers):
                    return canary.HttpResult(304, url)
                return canary.HttpResult(200, url, b"<akn>2026</akn>", '"new-etag"')
            if url == canary.MISSING_URL:
                return canary.HttpResult(404, url)
            raise AssertionError(f"unexpected source URL {url}")

        output = io.StringIO()
        with tempfile.TemporaryDirectory() as scratch:
            with patch.object(canary, "bounded_http_get", side_effect=fake_http):
                with contextlib.redirect_stdout(output):
                    try:
                        outcome = canary.main(["--store", str(Path(scratch) / "captures")])
                    except SystemExit as error:
                        outcome = str(error)
        return outcome, output.getvalue(), calls

    def test_historical_version_with_wrong_license_is_held_before_body_fetch(self):
        outcome, _, calls = self.run_with_historical_terms(
            b"Licenza priva di concessione corrente"
        )
        self.assertIn("DP244_CANARY_RIGHTS_", str(outcome))
        self.assertNotIn(canary.PREVIOUS_URL, calls)
        self.assertIn(canary.PREVIOUS_README_URL, calls)

    def test_historical_version_attests_own_license_and_keeps_public_hold(self):
        outcome, output, calls = self.run_with_historical_terms(b"Licenza: CC BY 3.0")
        self.assertEqual(outcome, 0)
        result = json.loads(output)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["source"]["current_licence_id"], "CC-BY-4.0")
        self.assertEqual(result["source"]["previous_licence_id"], "CC-BY-3.0")
        self.assertEqual(result["source"]["changed_step"], "REPLAY_AUTHENTIC_PINNED_BYTES")
        self.assertIsNone(result["coverage"]["public_freshness_descriptor"])
        self.assertFalse(result["coverage"]["dispatch_authorized"])
        self.assertIn(canary.PREVIOUS_URL, calls)


if __name__ == "__main__":
    unittest.main()

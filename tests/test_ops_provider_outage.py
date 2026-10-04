import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.provider_outage_drill import OutageClaimClient  # noqa: E402


class ProviderOutageClientTests(unittest.TestCase):
    def test_missing_credential_is_unhealthy_and_explicit(self):
        probe = OutageClaimClient("credential").probe()
        self.assertFalse(probe.healthy)
        self.assertEqual(probe.reason, "OMNIROUTE_API_KEY_MISSING")
        self.assertIsNone(probe.http_status)

    def test_http_failure_is_unhealthy_and_explicit(self):
        probe = OutageClaimClient("http").probe()
        self.assertFalse(probe.healthy)
        self.assertTrue(probe.reason.startswith("OMNIROUTE_HTTP_"))
        self.assertEqual(probe.http_status, 400)

    def test_extract_is_a_loud_invariant_violation_during_outage(self):
        client = OutageClaimClient("http")
        with self.assertRaisesRegex(RuntimeError, "DRILL_INVARIANT_VIOLATION"):
            client.extract()
        self.assertEqual(client.extract_calls, 1)

    def test_shell_driver_uses_real_worker_drill_module(self):
        script = (ROOT / "deploy" / "ops" / "provider_outage_drill.sh").read_text()
        self.assertIn("dichiarazioni_pubbliche.ops.provider_outage_drill", script)
        self.assertIn("--database-url", script)
        self.assertNotIn("switch provider", script.lower())


if __name__ == "__main__":
    unittest.main()

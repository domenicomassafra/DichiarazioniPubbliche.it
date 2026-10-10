import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.conditional_surface_absence import verify_surface_absence
from dichiarazioni_pubbliche.launch_preflight import repository_launch_preflight
from dichiarazioni_pubbliche.public_api import PublicApiRequestHandler, build_server
import dichiarazioni_pubbliche.conditional_surface_absence as gate


class ConditionalSurfaceAbsenceTests(unittest.TestCase):
    def test_current_absence_reduces_only_conditional_blockers(self):
        verify_surface_absence(ROOT)
        result = repository_launch_preflight(ROOT)
        self.assertEqual(result.disposition, "NO-GO")
        self.assertNotIn("CONDITIONAL_SURFACE_UNDECIDED:DP-507:FUTURE", result.blockers)
        self.assertNotIn("CONDITIONAL_SURFACE_UNDECIDED:DP-508:FUTURE", result.blockers)
        self.assertTrue(any(value.startswith("LEGAL_DECISION_NOT_CLOSED:") for value in result.blockers))
        self.assertTrue(any(value.startswith("TICKET_NOT_DONE:") for value in result.blockers))
        self.assertFalse(result.launchable)

    def test_surface_change_or_public_mutation_handler_revokes_exemption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "web/src/pages").mkdir(parents=True)
            verify_surface_absence(root)
            (root / "web/src/pages/contribuisci.astro").write_text("future intake", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PUBLIC_MUTATION_PAGE"):
                verify_surface_absence(root)
        with patch.object(PublicApiRequestHandler, "do_POST", lambda self: None):
            with self.assertRaisesRegex(ValueError, "PUBLIC_MUTATION_HANDLER"):
                verify_surface_absence(ROOT)
        with patch.object(gate, "_ALLOWED_PATHS", gate._ALLOWED_PATHS | {"/v1/admin/approve"}):
            with self.assertRaisesRegex(ValueError, "PRIVATE_STUDIO_PATH"):
                verify_surface_absence(ROOT)
        with patch.object(gate, "_ALLOWED_PATHS",
                          gate._PRIVATE_STUDIO_READ_PATHS - gate._STUDIO_PENDING_READ_ONLY_ADDITIONS):
            verify_surface_absence(ROOT)

    def test_actual_default_public_http_refuses_admin_intake_and_account_mutation(self):
        with build_server(None, host="127.0.0.1", port=0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path in ("/api/v1/intake", "/v1/admin/approve", "/moderazione/",
                             "/contribuisci/", "/account/auth/google"):
                    with self.subTest(path=path):
                        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                        try:
                            connection.request("POST", path, body=b"{}", headers={
                                "Content-Length": "2", "Content-Type": "application/json"
                            })
                            response = connection.getresponse()
                            body = response.read(2048)
                            self.assertIn(response.status, {404, 405})
                            self.assertNotIn(b'"publication_authority":true', body)
                            self.assertNotIn(b'"action_authorized":true', body)
                        finally:
                            connection.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)

    def test_conditional_decision_is_exact_and_not_approval(self):
        receipt = json.loads((ROOT / "docs/release/conditional-surfaces-v1.json").read_text())
        self.assertEqual(receipt["decisions"], {
            "DP-507": "NOT_APPLICABLE", "DP-508": "NOT_APPLICABLE"
        })
        self.assertIs(receipt["safety"]["legal_or_release_approval_granted"], False)
        self.assertIs(receipt["safety"]["revalidation_required_before_exposure"], True)


if __name__ == "__main__":
    unittest.main()

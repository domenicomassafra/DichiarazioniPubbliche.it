import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import REQUIRED_SOURCE_FAMILIES, _safe_url  # noqa: E402


class GarlascoDiscoveryLeadsTests(unittest.TestCase):
    def test_discovery_pool_is_real_url_only_and_never_claims_approval(self):
        path = ROOT / "config/garlasco-public-discovery-leads.v1.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "garlasco-public-discovery-leads-v1")
        self.assertEqual(data["state"], "UNREVIEWED_CANDIDATES_ONLY")
        candidates = data["candidates"]
        self.assertGreaterEqual(len(candidates), 5)
        self.assertLess(len(candidates), 100)
        self.assertEqual(len({row["id"] for row in candidates}), len(candidates))
        self.assertEqual(len({row["url"] for row in candidates}), len(candidates))
        for row in candidates:
            self.assertTrue(_safe_url(row["url"]), row["id"])
            self.assertIn(row["proposed_family"], REQUIRED_SOURCE_FAMILIES)
            self.assertEqual(row["rights_status"], "UNKNOWN")
            self.assertEqual(row["provenance_status"], "UNVERIFIED_IN_DATABASE")
            self.assertIs(row["candidate_only"], True)
            self.assertIs(row["capture_authorized"], False)
            self.assertFalse(urlsplit(row["url"]).username)
            self.assertNotIn("discovery_ref", row, "search leads cannot fake a persisted discovery hit")
        for locator in data["source_locator_only"]:
            self.assertTrue(_safe_url(locator["url"]))
            self.assertIs(locator["count_as_logical_item"], False)


if __name__ == "__main__":
    unittest.main()

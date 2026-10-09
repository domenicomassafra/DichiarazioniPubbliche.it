"""Public URL hints are candidate-only inputs, never accepted provenance."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_pilot_readiness import (  # noqa: E402
    ReadinessReportError,
    load_unreviewed_public_leads,
)


class GarlascoLeadIdentityGuardTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(
            (ROOT / "config/garlasco-public-discovery-leads.v1.json").read_text(encoding="utf-8")
        )

    def load_document(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "leads.json"
            path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
            return load_unreviewed_public_leads(path)

    def test_original_unreviewed_leads_still_count_as_unapproved_only(self):
        summary = self.load_document(self.document)
        self.assertEqual(summary["unreviewed_file_candidates"], 6)
        self.assertEqual(summary["file_leads_counted_in_pilot"], 0)

    def test_same_canonical_url_cannot_inflate_candidate_count_with_new_id(self):
        second = self.document["candidates"][1]
        second["url"] = self.document["candidates"][0]["url"]
        with self.assertRaisesRegex(ReadinessReportError, "PILOT_LEADS_URL_DUPLICATE"):
            self.load_document(self.document)

    def test_source_locator_cannot_relabel_an_existing_content_candidate(self):
        self.document["source_locator_only"][0]["url"] = self.document["candidates"][0]["url"]
        with self.assertRaisesRegex(ReadinessReportError, "PILOT_LEADS_URL_DUPLICATE"):
            self.load_document(self.document)

    def test_duplicate_json_keys_cannot_override_unreviewed_rights_state(self):
        payload = json.dumps(self.document)
        payload = payload.replace('"state": "UNREVIEWED_CANDIDATES_ONLY",',
                                  '"state": "ACTIVE", "state": "UNREVIEWED_CANDIDATES_ONLY",', 1)
        with self.assertRaisesRegex(ReadinessReportError, "PILOT_LEADS_DUPLICATE_JSON_KEY"):
            self.load_document(payload)


if __name__ == "__main__":
    unittest.main()

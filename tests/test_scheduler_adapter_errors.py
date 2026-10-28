"""Full-source regression for typed adapter error categories."""

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_scheduler_daemon import FakeStore, NOW
from dichiarazioni_pubbliche.scheduler_daemon import RuntimeBudget, run_registry
from dichiarazioni_pubbliche.source_adapters import SourceAdapterError


class AdapterErrorReceiptTests(unittest.TestCase):
    def test_full_source_preserves_sanitized_adapter_categories(self):
        sources = [
            {"id": "youtube-pulp-podcast", "kind": "youtube_channel", "poll_minutes": 30},
            {"id": "youtube-second", "kind": "youtube_channel", "poll_minutes": 30},
        ]
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps({"schema_version": 1, "sources": sources}))
            for category, expected_status in (
                ("ACCESS_RESTRICTED", "BLOCKED"),
                ("TIMEOUT", "FAILED"),
                ("MISSING_ID", "BLOCKED"),
            ):
                with self.subTest(category=category):
                    store = FakeStore()

                    def discover(source):
                        if source["id"] == "youtube-pulp-podcast":
                            raise SourceAdapterError(category, "private detail must not escape")
                        return []

                    result = run_registry(
                        registry_path, store, source_id=None, limit=20,
                        force=True, full_source=True,
                        now=NOW, budget=RuntimeBudget(), discover=discover,
                    )
                    self.assertEqual(result[0].status, expected_status)
                    self.assertEqual(result[0].error_category, category)
                    self.assertEqual(result[0].error, category)
                    self.assertEqual(result[1].status, "HEALTHY")
                    receipt = store.get_source_poll_source(result.run_id, "youtube-pulp-podcast")
                    self.assertEqual(receipt["error_category"], category)
                    self.assertEqual(store.failures[-1], ("youtube-pulp-podcast", category))


if __name__ == "__main__":
    unittest.main()

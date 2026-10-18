"""DP-515 regression for the scheduled registry polling entrypoint."""

import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.scheduler_daemon import (  # noqa: E402
    RuntimeBudget,
    SourceHealthState,
    run_registry,
)
from dichiarazioni_pubbliche.source_watcher import DiscoveredContent  # noqa: E402
from test_scheduler_daemon import FakeStore, NOW, SOURCE, content  # noqa: E402


class IncrementalTimerTests(unittest.TestCase):
    def test_registry_timer_discovers_delta_and_skips_non_due_ticks(self):
        store = FakeStore()
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        registry_path = Path(tempdir.name) / "registry.json"
        registry_path.write_text(json.dumps({"sources": [SOURCE]}))
        first_item = content()
        next_item = DiscoveredContent(
            source_id=first_item.source_id,
            platform=first_item.platform,
            external_id="episode-65",
            title="Nuova pubblicazione verificabile",
            canonical_url="https://example.test/episode-65",
            published_at="2026-09-22T00:30:00+00:00",
            author=first_item.author,
        )
        calls = []

        def discover(_source):
            calls.append(True)
            return [first_item] if len(calls) == 1 else [first_item, next_item]

        def tick(minutes):
            return run_registry(
                registry_path,
                store,
                source_id=None,
                force=False,
                limit=20,
                now=NOW + timedelta(minutes=minutes),
                budget=RuntimeBudget(),
                discover=discover,
            )[0]

        first = tick(0)
        self.assertEqual(first.jobs_enqueued, 1)
        store.health_state = SourceHealthState(NOW, 0)
        self.assertEqual(tick(5).status, "SKIPPED_NOT_DUE")
        self.assertEqual(len(calls), 1)

        changed = tick(30)
        self.assertEqual(changed.jobs_enqueued, 1)
        self.assertEqual(changed.duplicate_jobs, 1)
        self.assertEqual(len(store.jobs), 2)
        store.health_state = SourceHealthState(NOW + timedelta(minutes=30), 0)
        self.assertEqual(tick(35).status, "SKIPPED_NOT_DUE")
        unchanged = tick(60)
        self.assertEqual(unchanged.jobs_enqueued, 0)
        self.assertEqual(unchanged.duplicate_jobs, 2)
        self.assertEqual(len(store.jobs), 2)
        self.assertEqual(len(store.locators), 2)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()

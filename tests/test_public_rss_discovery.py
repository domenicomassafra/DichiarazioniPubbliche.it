"""Official metadata-only feed discovery without inferred acquisition rights."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.source_adapters import (
    SourceAdapterError, discover_source, discover_source_result,
)
from dichiarazioni_pubbliche.scheduler_daemon import (
    RuntimeBudget, run_registry,
)
from tests.test_scheduler_daemon import FakeStore

RSS = """<rss version="2.0"><channel><title>Ente</title>
<item><guid>stable-1</guid><link>https://example.org/doc/1</link>
<title>Comunicazione uno</title><pubDate>Fri, 09 Oct 2026 12:00:00 GMT</pubDate>
<description>Do not copy this body</description></item>
<item><guid>stable-2</guid><link>https://example.org/doc/2</link>
<title>Comunicazione due</title><pubDate>Fri, 09 Oct 2026 13:00:00 GMT</pubDate>
</item></channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><title>Ente</title>
<entry><id>tag:example.org,2026:item-1</id><title>Rilascio</title>
<link rel="alternate" href="https://example.org/doc/3"/>
<published>2026-10-09T13:00:00Z</published></entry></feed>"""
RDF = """<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="https://example.org/"><title>Ente</title></channel>
<item rdf:about="https://example.org/id/one"><title>Atto</title>
<link>https://example.org/doc/4</link><dc:date>2026-10-09T13:00:00Z</dc:date>
</item></rdf:RDF>"""


class PublicRssTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "official-source", "name": "Fonte pubblica",
            "kind": "public_rss", "poll_minutes": 1440,
            "max_items_per_poll": 1, "rights_status": "RIGHTS_HOLD",
            "discovery_url": "https://example.org/rss.xml",
            "content_policy": {"metadata_only": True},
        }

    def test_rss_atom_rdf_all_keep_stable_locator_and_family(self):
        for xml, stable_id, suffix in (
            (RSS, "stable-1", "/1"),
            (ATOM, "tag:example.org,2026:item-1", "/3"),
            (RDF, "https://example.org/id/one", "/4"),
        ):
            with self.subTest(stable_id=stable_id):
                with patch("dichiarazioni_pubbliche.source_watcher.fetch_text") as network:
                    rows = discover_source(self.source, feed_xml=xml)
                network.assert_not_called()
                self.assertEqual(rows[0].external_id, stable_id)
                self.assertEqual(rows[0].source_kind, "public_rss")
                self.assertEqual(rows[0].platform, "public_rss")
                self.assertTrue(rows[0].canonical_url.endswith(suffix))
                self.assertIn("2026-10-09", rows[0].published_at)
                self.assertIsNone(rows[0].media_url)
                self.assertIsNone(rows[0].description)

    def test_feed_limit_replay_and_missing_id_fail_closed(self):
        first = discover_source(self.source, feed_xml=RSS, limit=1)
        second = discover_source(self.source, feed_xml=RSS, limit=1)
        self.assertEqual(first, second)
        self.assertEqual(first.omitted_items, 1)
        self.assertEqual(len(first), 1)
        unsafe = RSS.replace("<guid>stable-1</guid>", "<guid></guid>").replace(
            "<link>https://example.org/doc/1</link>", "<link></link>"
        )
        self.assertEqual(discover_source_result(self.source, feed_xml=unsafe).status, "BLOCKED")
        self.assertEqual(discover_source_result(self.source, feed_xml=unsafe).error_category, "MISSING_ID")

    def test_unsafe_urls_rejected_and_oversize_blocked(self):
        unsafe = RSS.replace("https://example.org/doc/1", "https://127.0.0.1/private")
        self.assertEqual(discover_source_result(self.source, feed_xml=unsafe).error_category, "SSRF_REJECTED")
        self.assertEqual(discover_source_result(self.source, feed_xml="<rss/>").error_category, "MALFORMED_RESPONSE")
        self.assertEqual(discover_source_result(self.source, feed_xml=RSS, max_response_bytes=10).status, "FAILED")

    def test_full_source_receipt_is_discovery_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            registry = Path(root) / "sources.json"
            registry.write_text(json.dumps({"schema_version": 1, "sources": [self.source]}))
            store = FakeStore()
            store.relevance_allowed = False  # No content acquisition authority.
            calls = []

            def discover(source):
                calls.append(source["id"])
                return discover_source(source, feed_xml=RSS)

            kwargs = dict(
                source_id=None, force=False, full_source=True,
                limit=20, budget=RuntimeBudget(),
                now=datetime(2026, 10, 10, tzinfo=timezone.utc),
                discover=discover,
            )
            run = run_registry(registry, store, **kwargs)
            self.assertEqual(run.status, "COMPLETED")
            self.assertEqual(run[0].status, "BLOCKED")
            self.assertEqual(run[0].error_category, "RIGHTS_HOLD")
            self.assertEqual(run.counters["discovered"], 1)
            self.assertEqual(run.counters["omitted_items"], 1)
            self.assertEqual(run.counters["content_upserts"], 0)
            self.assertEqual(run.counters["jobs_enqueued"], 0)
            self.assertEqual(store.jobs, [])
            self.assertEqual(store.content_ids, [])
            replay = run_registry(registry, store, **kwargs)
            self.assertEqual(replay.status, "SKIPPED_ALREADY_COMPLETED")
            self.assertEqual(calls, [self.source["id"]])

    def test_production_registry_official_endpoints_rights_hold(self):
        registry = json.loads((ROOT / "config/source-registry.v1.json").read_text())
        for source_id, domain in (
            ("official-camera-temi", "documenti.camera.it"),
            ("official-consilium-press", "www.consilium.europa.eu"),
        ):
            source = next(s for s in registry["sources"] if s["id"] == source_id)
            self.assertEqual(source["kind"], "public_rss")
            self.assertEqual(source["rights_status"], "RIGHTS_HOLD")
            self.assertTrue(source["content_policy"]["metadata_only"])
            self.assertIn(domain, source["discovery_url"])
            self.assertLessEqual(source["max_items_per_poll"], 20)
            self.assertGreaterEqual(source["poll_minutes"], 720)


if __name__ == "__main__":
    unittest.main()

"""#167: feedparser and stdlib feed parsing obey the same discovery contract."""

import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche import feed_parsing
from dichiarazioni_pubbliche.source_adapters import (
    discover_source, discover_source_result, scheduler_ingest_plan,
)
from tests.test_public_rss_discovery import ATOM, RDF, RSS
from tests.test_source_adapters import RSS_FEED, YOUTUBE_FEED


def source(kind):
    return {
        "id": "test-source",
        "kind": kind,
        "discovery_url": "https://feeds.example.org/updates.xml",
        "rights_status": "RIGHTS_HOLD",
        "max_items_per_poll": 1,
        "poll_minutes": 1440,
    }


class FeedparserContractTests(unittest.TestCase):
    def test_parity_for_existing_rss1_rss2_atom_itunes_youtube(self):
        fixtures = (
            ("public_rss", RSS),
            ("public_rss", RDF),
            ("public_rss", ATOM),
            ("podcast_rss", RSS_FEED),
            ("youtube_channel", YOUTUBE_FEED),
        )
        backend = feed_parsing._feedparser
        for kind, xml in fixtures:
            with self.subTest(kind=kind, xml=xml[:50]):
                with patch.object(feed_parsing, "_feedparser", None):
                    fallback = discover_source(source(kind), feed_xml=xml)
                self.assertGreaterEqual(len(fallback), 1)
                self.assertEqual(fallback[0].source_kind, kind)
                self.assertFalse(scheduler_ingest_plan(fallback[0])["download_media"])
                if backend is not None:
                    with patch.object(feed_parsing, "_feedparser", backend):
                        parsed = discover_source(source(kind), feed_xml=xml)
                    self.assertEqual([asdict(row) for row in parsed], [asdict(row) for row in fallback])

    def test_rfc822_timezone_guid_enclosure_and_itunes_duration(self):
        xml = RSS_FEED.replace(
            "Mon, 21 Sep 2026 11:00:00 -0000",
            "Mon, 21 Sep 2026 11:00:00 -0500",
        ).replace("<itunes:duration>4919</itunes:duration>",
                  "<itunes:duration>01:21:59</itunes:duration>").replace(
            "<guid isPermaLink=\"false\">episode-64</guid>",
            "<guid isPermaLink=\"false\">non-url-guid-64</guid>",
        ).replace(
            "<enclosure url=", "<link>https://episodes.example.org/64</link><enclosure url="
        )
        item = discover_source(source("podcast_rss"), feed_xml=xml)[0]
        self.assertEqual(item.external_id, "non-url-guid-64")
        self.assertEqual(item.canonical_url, "https://episodes.example.org/64")
        self.assertEqual(item.media_url, "https://traffic.megaphone.fm/episode-64.mp3")
        self.assertEqual(item.media_type, "audio/mpeg")
        self.assertEqual(item.duration_seconds, 4919)
        self.assertEqual(item.published_at, "2026-09-21T16:00:00+00:00")
        self.assertEqual(item.source_kind, "podcast_rss")

    def test_atom_updated_and_entry_author_preserved(self):
        atom = ATOM.replace(
            "<published>2026-10-09T13:00:00Z</published>",
            "<updated>2026-10-09T13:00:00+02:00</updated>"
            "<author><name>Redazione ente</name></author>",
        )
        result = discover_source(source("public_rss"), feed_xml=atom)
        self.assertEqual(result[0].external_id, "tag:example.org,2026:item-1")
        self.assertEqual(result[0].published_at, "2026-10-09T11:00:00+00:00")
        self.assertEqual(result[0].author, "Redazione ente")
        self.assertIsNone(result[0].media_url)
        self.assertIsNone(result[0].description)

    def test_invalid_feeds_never_recover_as_valid(self):
        rss_without_id = RSS_FEED.replace(
            '<guid isPermaLink="false">episode-64</guid>', ""
        ).replace('<enclosure url="https://traffic.megaphone.fm/episode-64.mp3"', '<enclosure url=""')
        cases = (
            ("public_rss", "<rss><channel><item></rss>", "MALFORMED_RESPONSE"),
            ("podcast_rss", "<rss><channel><item></rss>", "MALFORMED_RESPONSE"),
            ("youtube_channel", "<feed><entry></feed>", "MALFORMED_RESPONSE"),
            ("public_rss", '<!DOCTYPE rss [<!ENTITY x "unsafe">]>' + RSS, "MALFORMED_RESPONSE"),
            ("public_rss", "<html><body>not a feed</body></html>", "MALFORMED_RESPONSE"),
            ("podcast_rss", rss_without_id, "MISSING_ID"),
            ("public_rss", RSS.replace("https://example.org/doc/1", "http://127.0.0.1/a"), "SSRF_REJECTED"),
            ("podcast_rss", RSS_FEED.replace("https://traffic.megaphone.fm/episode-64.mp3", "https://127.0.0.1/audio"), "SSRF_REJECTED"),
            ("youtube_channel", YOUTUBE_FEED.replace("https://www.youtube.com/watch?v=QaE00l6JZ8w", "http://localhost/watch"), "SSRF_REJECTED"),
        )
        backend = feed_parsing._feedparser
        for parser in (None, backend):
            for kind, xml, category in cases:
                with self.subTest(parser=bool(parser), kind=kind, category=category):
                    with patch.object(feed_parsing, "_feedparser", parser):
                        result = discover_source_result(source(kind), feed_xml=xml)
                    self.assertEqual(result.items, ())
                    self.assertEqual(result.error_category, category)
                    self.assertNotEqual(result.status, "OK")

    def test_payload_size_limit_and_fetcher_are_bounded_for_every_family(self):
        for kind, xml in (
            ("public_rss", RSS),
            ("podcast_rss", RSS_FEED),
            ("youtube_channel", YOUTUBE_FEED),
        ):
            with self.subTest(kind=kind):
                self.assertEqual(
                    discover_source_result(source(kind), feed_xml=xml, max_response_bytes=5).error_category,
                    "MALFORMED_RESPONSE",
                )
                with patch("dichiarazioni_pubbliche.source_watcher.fetch_text") as fetch:
                    fetch.return_value = xml
                    result = discover_source_result(source(kind), max_response_bytes=5)
                self.assertEqual(result.error_category, "MALFORMED_RESPONSE")
                fetch.assert_called_once()

    def test_item_cap_and_receipt_counts_stay_deterministic(self):
        items = "".join(
            f"<item><guid>stable-{idx}</guid><link>https://example.org/{idx}</link>"
            f"<title>{idx}</title></item>" for idx in range(23)
        )
        feed = f"<rss version='2.0'><channel><title>Ente</title>{items}</channel></rss>"
        first = discover_source(source("public_rss"), feed_xml=feed, limit=999)
        second = discover_source(source("public_rss"), feed_xml=feed, limit=999)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertEqual(first.omitted_items, 3)

    def test_feedparser_bozo_and_silent_entry_drop_are_fail_closed(self):
        if feed_parsing._feedparser is None:
            self.skipTest("feedparser optional dependency is not installed")

        class Parsed(dict):
            @property
            def entries(self):
                return self["entries"]

        class BrokenBackend:
            @staticmethod
            def parse(_xml):
                return Parsed(bozo=True, version="rss20", entries=[])

        class DroppingBackend:
            @staticmethod
            def parse(_xml):
                return Parsed(bozo=False, version="rss20", entries=[])

        for backend in (BrokenBackend, DroppingBackend):
            with patch.object(feed_parsing, "_feedparser", backend):
                self.assertEqual(
                    discover_source_result(source("public_rss"), feed_xml=RSS).error_category,
                    "MALFORMED_RESPONSE",
                )


if __name__ == "__main__":
    unittest.main()

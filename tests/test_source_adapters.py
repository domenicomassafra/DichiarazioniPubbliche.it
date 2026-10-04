import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.scheduler import (
    cluster_discoveries,
    deterministic_content_id,
    deterministic_job_id,
    plan_initial_job,
    provisional_content_key,
)
from dichiarazioni_pubbliche.source_adapters import (
    DiscoveredContent,
    SourceAdapterError,
    discover_source,
    discover_source_result,
    get_source_adapter,
    scheduler_ingest_plan,
)


YOUTUBE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>QaE00l6JZ8w</yt:videoId>
    <title>Beppe Grillo a Pulp Podcast. | Pulp Podcast #64</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=QaE00l6JZ8w"/>
    <author><name>Pulp Podcast</name></author>
    <published>2026-09-21T10:00:00+00:00</published>
  </entry>
</feed>
"""

RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>PULP PODCAST</title>
    <item>
      <title>Beppe Grillo a Pulp Podcast | Pulp Podcast #64</title>
      <description>Minutaggio: 0:00 introduzione ospite</description>
      <pubDate>Mon, 21 Sep 2026 11:00:00 -0000</pubDate>
      <itunes:duration>4919</itunes:duration>
      <guid isPermaLink="false">episode-64</guid>
      <enclosure url="https://traffic.megaphone.fm/episode-64.mp3"
                 length="0" type="audio/mpeg"/>
    </item>
  </channel>
</rss>
"""


class SourceAdapterContractTests(unittest.TestCase):
    def test_all_families_share_normalized_contract(self):
        cases = [
            (
                {
                    "id": "youtube",
                    "kind": "youtube_channel",
                    "discovery_url": "https://www.youtube.com/feeds/videos.xml?channel_id=x",
                },
                YOUTUBE_FEED,
                "youtube",
                "QaE00l6JZ8w",
            ),
            (
                {
                    "id": "podcast",
                    "kind": "podcast_rss",
                    "discovery_url": "https://feeds.example.test/podcast.xml",
                },
                RSS_FEED,
                "podcast_rss",
                "episode-64",
            ),
        ]
        for source, feed, platform, external_id in cases:
            item = discover_source(source, feed_xml=feed)[0]
            self.assertIsInstance(item, DiscoveredContent)
            self.assertEqual(item.source_kind, source["kind"])
            self.assertEqual(item.platform, platform)
            self.assertEqual(item.external_id, external_id)
            self.assertTrue(item.canonical_url.startswith("https://"))
            self.assertTrue(item.title)
            self.assertEqual(
                scheduler_ingest_plan(item)["download_media"],
                False,
            )

        creator = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {
                "posts": [
                    {
                        "platform": "instagram",
                        "post_id": "post-1",
                        "canonical_url": "https://www.instagram.com/creator/reel/post-1/",
                        "published_at": "2026-09-21T10:00:00+00:00",
                        "title": "Public update",
                        "media_type": "video",
                    }
                ]
            },
        }
        item = discover_source(creator)[0]
        self.assertEqual(item.source_kind, "public_creator_accounts")
        self.assertEqual(item.platform, "instagram")
        self.assertEqual(item.external_id, "post-1")
        self.assertEqual(item.media_type, "video")

    def test_limit_and_discovery_adapter_cap_are_shared(self):
        posts = [
            {
                "platform": "tiktok",
                "post_id": f"post-{index}",
                "canonical_url": f"https://www.tiktok.com/@creator/video/post-{index}",
                "published_at": "2026-09-21T10:00:00+00:00",
                "title": f"Post {index}",
            }
            for index in range(25)
        ]
        source = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {"posts": posts},
        }
        bounded = discover_source(source, limit=100)
        self.assertEqual(len(bounded), 20)
        self.assertEqual(bounded.omitted_items, 5)
        self.assertEqual(len(discover_source(source, limit=3)), 3)

    def test_rss_discovery_does_not_fetch_or_download_media(self):
        source = {
            "id": "podcast",
            "kind": "podcast_rss",
            "discovery_url": "https://feeds.example.test/podcast.xml",
        }
        with patch("dichiarazioni_pubbliche.source_watcher.fetch_text") as fetch:
            items = discover_source(source, feed_xml=RSS_FEED)
        fetch.assert_not_called()
        self.assertEqual(items[0].media_type, "audio/mpeg")
        self.assertFalse(scheduler_ingest_plan(items[0])["download_media"])

    def test_creator_adapter_never_fetches_or_downloads(self):
        source = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {
                "posts": [
                    {
                        "platform": "tiktok",
                        "post_id": "post-1",
                        "canonical_url": "https://www.tiktok.com/@creator/video/post-1",
                        "published_at": "2026-09-21T10:00:00+00:00",
                    }
                ]
            },
        }
        with patch("dichiarazioni_pubbliche.source_watcher.fetch_text") as fetch:
            with patch("urllib.request.urlopen") as urlopen:
                items = discover_source(source)
        fetch.assert_not_called()
        urlopen.assert_not_called()
        self.assertEqual(len(items), 1)

    def test_creator_missing_id_and_ssrf_are_explicitly_blocked(self):
        missing = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {
                "posts": [
                    {
                        "platform": "instagram",
                        "canonical_url": "https://www.instagram.com/creator/reel/no-id/",
                    }
                ]
            },
        }
        private = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {
                "posts": [
                    {
                        "platform": "instagram",
                        "post_id": "post-1",
                        "canonical_url": "https://127.0.0.1/reel/post-1/",
                    }
                ]
            },
        }
        with self.assertRaises(SourceAdapterError) as missing_error:
            discover_source(missing)
        self.assertEqual(missing_error.exception.category, "MISSING_ID")
        self.assertEqual(discover_source_result(missing).status, "BLOCKED")
        with self.assertRaises(SourceAdapterError) as ssrf_error:
            discover_source(private)
        self.assertEqual(ssrf_error.exception.category, "SSRF_REJECTED")
        self.assertEqual(discover_source_result(private).status, "BLOCKED")

    def test_restricted_creator_post_is_blocked(self):
        source = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {
                "posts": [
                    {
                        "platform": "instagram",
                        "post_id": "post-1",
                        "canonical_url": "https://www.instagram.com/creator/reel/post-1/",
                        "access": "restricted",
                    }
                ]
            },
        }
        result = discover_source_result(source)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.error_category, "ACCESS_RESTRICTED")

    def test_cross_post_identity_and_job_id_are_deterministic(self):
        source = {
            "id": "creator",
            "kind": "public_creator_accounts",
            "public_metadata": {
                "posts": [
                    {
                        "platform": "instagram",
                        "post_id": "post-1",
                        "canonical_url": "https://www.instagram.com/creator/reel/post-1/",
                        "published_at": "2026-09-21T10:00:00+00:00",
                        "title": "Same public statement",
                    },
                    {
                        "platform": "tiktok",
                        "post_id": "post-2",
                        "canonical_url": "https://www.tiktok.com/@creator/video/post-2",
                        "published_at": "2026-09-21T10:00:00+00:00",
                        "title": "Same public statement",
                    },
                ]
            },
        }
        items = discover_source(source)
        clusters = cluster_discoveries(items)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)
        key = provisional_content_key(items[0])
        self.assertEqual(key, provisional_content_key(items[1]))
        first = plan_initial_job(items[0], scheduler_ingest_plan(items[0]))
        second = plan_initial_job(items[1], scheduler_ingest_plan(items[1]))
        self.assertEqual(first.content_key, second.content_key)
        self.assertEqual(
            deterministic_job_id(first.job_type, first.content_key),
            deterministic_job_id(second.job_type, second.content_key),
        )

    def test_registry_three_family_canary_clusters_pulp_episode_64(self):
        registry = json.loads(
            (ROOT / "config" / "source-registry.v1.json").read_text()
        )
        sources = {source["id"]: source for source in registry["sources"]}
        self.assertEqual(
            {source["kind"] for source in sources.values()},
            {"youtube_channel", "podcast_rss", "public_creator_accounts"},
        )

        youtube_source = sources["youtube-pulp-podcast"]
        rss_source = sources["podcast-pulp-podcast"]
        creator_source = sources["social-raffagiulians"]
        self.assertNotIn("podcast_rss_url", youtube_source)
        self.assertNotIn("discovery_preference", youtube_source)
        self.assertEqual(
            youtube_source["discovery_url"],
            "https://www.youtube.com/feeds/videos.xml?channel_id=UCY99TnBJ8xyat2lpeN_hcEA",
        )
        self.assertEqual(
            rss_source["discovery_url"],
            "https://feeds.megaphone.fm/SONY4300078217",
        )

        youtube = discover_source(youtube_source, feed_xml=YOUTUBE_FEED)[0]
        rss = discover_source(rss_source, feed_xml=RSS_FEED)[0]
        creator_metadata = json.loads(
            (ROOT / creator_source["public_metadata_fixture"]).read_text()
        )
        creator = discover_source(creator_source, metadata=creator_metadata)[0]
        self.assertEqual(
            {youtube.source_kind, rss.source_kind, creator.source_kind},
            {"youtube_channel", "podcast_rss", "public_creator_accounts"},
        )
        self.assertEqual(creator.platform, "instagram")
        self.assertEqual(creator.published_at, "")

        clusters = cluster_discoveries([youtube, rss])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(
            {item.platform for item in clusters[0].items},
            {"youtube", "podcast_rss"},
        )
        self.assertEqual(
            {(item.platform, item.external_id) for item in clusters[0].items},
            {("youtube", "QaE00l6JZ8w"), ("podcast_rss", "episode-64")},
        )
        jobs = [
            plan_initial_job(item, scheduler_ingest_plan(item))
            for item in (youtube, rss)
        ]
        self.assertEqual(len({job.job_id for job in jobs}), 1)
        self.assertEqual(
            {job.job_type for job in jobs},
            {"TRANSCRIPT_RESOLVE_PLATFORM"},
        )
        self.assertTrue(
            all(
                scheduler_ingest_plan(item)["download_media"] is False
                for item in (youtube, rss)
            )
        )
        self.assertEqual(
            len({deterministic_content_id(job.content_key) for job in jobs}),
            1,
        )

    def test_unknown_kind_is_explicitly_unsupported(self):
        result = discover_source_result({"id": "unknown", "kind": "web_crawler"})
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.error_category, "UNSUPPORTED")
        with self.assertRaises(SourceAdapterError):
            get_source_adapter("web_crawler")

    def test_approved_fixture_path_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "creator.json"
            path.write_text(
                json.dumps(
                    {
                        "posts": [
                            {
                                "platform": "instagram",
                                "post_id": "fixture-1",
                                "canonical_url": "https://www.instagram.com/creator/reel/fixture-1/",
                                "title": "Fixture",
                            }
                        ]
                    }
                )
            )
            source = {
                "id": "creator",
                "kind": "public_creator_accounts",
                "public_metadata_fixture": str(path),
            }
            self.assertEqual(discover_source(source)[0].external_id, "fixture-1")


if __name__ == "__main__":
    unittest.main()

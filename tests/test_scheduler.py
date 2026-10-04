import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.scheduler import (
    cluster_discoveries,
    deterministic_content_id,
    definitive_content_key,
    deterministic_job_id,
    plan_initial_job,
    provisional_content_key,
)
from dichiarazioni_pubbliche.source_watcher import DiscoveredContent


def item(platform: str, external_id: str, title: str, published_at: str):
    return DiscoveredContent(
        source_id="youtube-pulp-podcast",
        platform=platform,
        external_id=external_id,
        title=title,
        canonical_url=f"https://example.test/{external_id}",
        published_at=published_at,
        author="PULP PODCAST",
    )


class SchedulerTests(unittest.TestCase):
    def test_rss_and_youtube_same_episode_cluster_together(self):
        rss = item(
            "podcast_rss",
            "3ef3726c-b596-11f1-9e3d-d31a12201256",
            "Beppe Grillo a Pulp Podcast | Pulp Podcast #64",
            "2026-09-21T11:00:00+00:00",
        )
        youtube = item(
            "youtube",
            "QaE00l6JZ8w",
            "Beppe Grillo a Pulp Podcast. | Pulp Podcast #64",
            "2026-09-21T10:00:00+00:00",
        )
        clusters = cluster_discoveries([rss, youtube])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)

    def test_job_id_is_idempotent(self):
        content = item(
            "youtube",
            "QaE00l6JZ8w",
            "Beppe Grillo a Pulp Podcast. | Pulp Podcast #64",
            "2026-09-21T10:00:00+00:00",
        )
        key = provisional_content_key(content)
        self.assertEqual(
            deterministic_job_id("TRANSCRIPT_ACQUIRE_CAPTION", key),
            deterministic_job_id("TRANSCRIPT_ACQUIRE_CAPTION", key),
        )
        self.assertEqual(
            deterministic_content_id(key),
            deterministic_content_id(key),
        )

    def test_missing_timestamp_never_collapses_distinct_items(self):
        first = item("youtube", "video-a", "Weekly Update", "")
        second = item("youtube", "video-b", "Weekly Update", "")
        self.assertNotEqual(
            provisional_content_key(first),
            provisional_content_key(second),
        )
        self.assertEqual(len(cluster_discoveries([first, second])), 2)

    def test_caption_plan_creates_caption_job(self):
        content = item(
            "youtube",
            "QaE00l6JZ8w",
            "Beppe Grillo a Pulp Podcast. | Pulp Podcast #64",
            "2026-09-21T10:00:00+00:00",
        )
        job = plan_initial_job(content, {"action": "ACQUIRE_CAPTION"})
        self.assertEqual(job.job_type, "TRANSCRIPT_ACQUIRE_CAPTION")
        self.assertEqual(job.payload["external_id"], "QaE00l6JZ8w")

    def test_definitive_key_uses_content_hash(self):
        digest = "a" * 64
        self.assertEqual(definitive_content_key(digest), f"sha256:{digest}")


if __name__ == "__main__":
    unittest.main()

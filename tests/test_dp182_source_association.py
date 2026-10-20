"""F3: podcast episodes resolve only across a reviewed YouTube association."""
import sys
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.platform_transcript import YouTubeResolver
from dichiarazioni_pubbliche.source_associations import (
    SourceAssociationBlocked, select_podcast_youtube_association,
)
from dichiarazioni_pubbliche.source_watcher import parse_podcast_rss
from dichiarazioni_pubbliche.worker_errors import BlockedJob
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers

CHANNEL = "UCY99TnBJ8xyat2lpeN_hcEA"
CATALOG = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"
VIDEO = "Vid00000064"
RSS = """<rss version="2.0"><channel><title>Pulp Podcast</title>
<item><title>Pulp Podcast #64 | intervista</title><guid>ep64</guid>
<enclosure url="https://podcasts.example.org/ep64.mp3" type="audio/mpeg"/></item>
</channel></rss>"""


def atom(*entries, channel=CHANNEL):
    rows = "".join(f"<entry><yt:videoId>{video}</yt:videoId>"
                   f"<title>{title}</title></entry>" for video, title in entries)
    return ("<feed xmlns='http://www.w3.org/2005/Atom' "
            "xmlns:yt='http://www.youtube.com/xml/schemas/2015'>"
            f"<yt:channelId>{channel}</yt:channelId>{rows}</feed>")


def fetched(xml, url=CATALOG):
    return SimpleNamespace(body=xml.encode(), charset=None, final_url=url)


def registry(*, status="APPROVED", channel=CHANNEL, approved=True):
    association = {
        "id": "pulp-podcast-youtube-v1", "version": 1,
        "podcast_source_id": "podcast-pulp-podcast",
        "youtube_source_id": "youtube-pulp-podcast", "youtube_channel_id": channel,
        "status": status,
        "policy_version": "source-association-v1",
        "approval_ref": "review:synthetic-182" if approved else "",
        "reviewer_ref": "reviewer:synthetic" if approved else "",
    }
    return {
        "schema_version": 1, "source_associations_version": 1,
        "source_associations": [association],
        "sources": [
            {"id": "podcast-pulp-podcast", "kind": "podcast_rss",
             "discovery_url": "https://podcasts.example.org/feed.xml"},
            {"id": "youtube-pulp-podcast", "kind": "youtube_channel",
             "channel_id": CHANNEL,
             "channel_url": f"https://www.youtube.com/channel/{CHANNEL}",
             "discovery_url": CATALOG},
        ],
    }


class AssociationOfflineTests(unittest.TestCase):
    def test_legacy_resolver_refuses_podcast_rss_without_fetch(self):
        with patch("dichiarazioni_pubbliche.platform_transcript.fetch_text") as fetch:
            with self.assertRaisesRegex(ValueError, "YOUTUBE_SOURCE_KIND_REQUIRED"):
                YouTubeResolver().resolve("Pulp Podcast #64", registry()["sources"][0])
        fetch.assert_not_called()

    def test_rss_and_atom_are_distinct_sources_with_approved_explicit_mapping(self):
        episode = parse_podcast_rss(RSS, "podcast-pulp-podcast")[0]
        self.assertEqual(episode.title, "Pulp Podcast #64 | intervista")
        assoc, source = select_podcast_youtube_association(registry(), episode.source_id)
        self.assertEqual(source["id"], "youtube-pulp-podcast")
        self.assertEqual(assoc.youtube_channel_id, CHANNEL)
        checks = []
        resolver = YouTubeResolver()
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom(
            ("Vid00000065", "Pulp Podcast #65 | intervista"),
            (VIDEO, "Pulp Podcast #64 | ospite"),
        ))) as fetch, patch.object(resolver, "_flat_candidates", side_effect=AssertionError("flat")):
            match = resolver.resolve_associated(episode.title, source, association=assoc,
                                                check_fetch=lambda url: checks.append(url))
        fetch.assert_called_once_with(CATALOG, allow_redirects=False)
        self.assertEqual(checks, [CATALOG, CATALOG])
        self.assertEqual(match.video_id, VIDEO)
        self.assertEqual(match.canonical_url, f"https://www.youtube.com/watch?v={VIDEO}")

    def test_missing_unapproved_ambiguous_and_channel_drift_hold_before_fetch(self):
        sources = registry()
        for mutated in (
            {**sources, "source_associations": []},
            registry(status="PENDING"),
            registry(approved=False),
            {**sources, "source_associations": sources["source_associations"] * 2},
            registry(channel="UC_NOT_A_MATCH"),
        ):
            with self.subTest(mutated=mutated["source_associations"]):
                with self.assertRaises(SourceAssociationBlocked):
                    select_podcast_youtube_association(mutated, "podcast-pulp-podcast")

    def test_mismatched_channel_or_episode_cannot_make_a_locator(self):
        assoc, source = select_podcast_youtube_association(registry(), "podcast-pulp-podcast")
        resolver = YouTubeResolver()
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom(
            ("Vid00000065", "Pulp Podcast #65 | intervista"),
        ))):
            self.assertIsNone(resolver.resolve_associated("Pulp Podcast #64", source,
                        association=assoc, check_fetch=lambda _: None))
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom(
            (VIDEO, "Pulp Special #64"),
        ))):
            self.assertIsNone(resolver.resolve_associated("Pulp Podcast #64", source,
                        association=assoc, check_fetch=lambda _: None))
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom(
            (VIDEO, "Pulp Podcast #64"), channel="UC_not_the_expected_one"))):
            with self.assertRaises(SourceAssociationBlocked):
                resolver.resolve_associated("Pulp Podcast #64", source,
                        association=assoc, check_fetch=lambda _: None)

    def test_http_redirect_is_refused_before_second_network_request(self):
        import socket
        from email.message import Message
        from dichiarazioni_pubbliche.source_watcher import fetch_bytes

        destinations = []
        def public_dns(host, port, type=None):
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP,
                     "", ("93.184.216.34", port))]
        class Redirect:
            status = code = 302
            msg = "Found"
            headers = Message()
            headers["Location"] = "https://redirect.example.org/other.xml"
            def info(self): return self.headers
            def getcode(self): return 302
            def geturl(self): return CATALOG
            def read(self, *args): return b""
            def close(self): pass
        def network(_handler, connection_type, request, **kwargs):
            destinations.append(request.get_full_url())
            return Redirect()
        with patch("dichiarazioni_pubbliche.source_watcher.urllib.request.AbstractHTTPHandler.do_open",
                   new=network):
            with self.assertRaisesRegex(ValueError, "DISCOVERY_REDIRECT_FORBIDDEN"):
                fetch_bytes(CATALOG, resolver=public_dns, allow_redirects=False)
        self.assertEqual(destinations, [CATALOG])

    def test_redirect_to_an_unreviewed_feed_blocks_even_when_body_matches(self):
        assoc, source = select_podcast_youtube_association(registry(), "podcast-pulp-podcast")
        checks = []
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes",
                   return_value=fetched(atom((VIDEO, "Pulp Podcast #64")),
                                        url="https://other.example.test/feed.xml")):
            with self.assertRaisesRegex(SourceAssociationBlocked,
                                         "YOUTUBE_ASSOCIATED_REDIRECT_UNAUTHORIZED"):
                YouTubeResolver().resolve_associated("Pulp Podcast #64", source,
                    association=assoc, check_fetch=lambda url: checks.append(url))
        self.assertEqual(checks, [CATALOG])

    def _worker(self):
        handler = TranscriptAsrJobHandlers()
        handler.registry = registry()
        handler._source = lambda source_id: handler.registry["sources"][0]
        handler._require_current_ingestion_relevance = Mock()
        handler._enqueue_asr = Mock()
        handler._probe_and_enqueue_caption = Mock()
        handler._require_podcast_asr_clearance = Mock()
        handler.store = Mock()
        handler.resolver = YouTubeResolver()
        rights = SimpleNamespace(rights_record_id="rights:synthetic", require=Mock(
            return_value=SimpleNamespace(decision_fingerprint="sha256:synth")))
        handler._caption_rights_guard = Mock(return_value=rights)
        content = SimpleNamespace(source_id="podcast-pulp-podcast", content_id="content:64",
                                  title="Pulp Podcast #64", canonical_url="https://podcasts.example.org/ep64.mp3")
        job = SimpleNamespace(payload={"platform": "podcast_rss"})
        return handler, job, content

    def test_worker_rechecks_feed_and_video_rights_and_provenance_before_locator(self):
        handler, job, content = self._worker()
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom(
            (VIDEO, "Pulp Podcast #64"),
        ))) as fetch:
            handler.resolve_platform(job, content)
        fetch.assert_called_once_with(CATALOG, allow_redirects=False)
        self.assertEqual(handler._caption_rights_guard.call_count, 3)
        self.assertEqual(handler._caption_rights_guard.call_args.args[1],
                         f"https://www.youtube.com/watch?v={VIDEO}")
        handler.store.upsert_locator.assert_called_once()
        metadata = handler.store.upsert_locator.call_args.kwargs["metadata"]
        self.assertEqual(metadata["podcast_source_id"], "podcast-pulp-podcast")
        self.assertEqual(metadata["youtube_source_id"], "youtube-pulp-podcast")
        self.assertEqual(metadata["youtube_channel_id"], CHANNEL)
        self.assertEqual(metadata["source_association_id"], "pulp-podcast-youtube-v1")
        self.assertEqual(metadata["source_association_version"], 1)
        self.assertEqual(metadata["podcast_canonical_url"], content.canonical_url)
        self.assertEqual(metadata["youtube_catalog_url"], CATALOG)
        self.assertEqual(metadata["youtube_catalog_sha256"], hashlib.sha256(
            atom((VIDEO, "Pulp Podcast #64")).encode()).hexdigest())
        self.assertIn("youtube_rights_fingerprints", metadata)
        handler._probe_and_enqueue_caption.assert_called_once()
        handler._enqueue_asr.assert_not_called()

    def test_missing_relevance_or_association_never_fetches_or_dispatches_asr(self):
        handler, job, content = self._worker()
        handler._require_current_ingestion_relevance.side_effect = BlockedJob("INGESTION_RELEVANCE_MISSING")
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes") as fetch:
            with self.assertRaisesRegex(BlockedJob, "INGESTION_RELEVANCE_MISSING"):
                handler.resolve_platform(job, content)
        fetch.assert_not_called()
        handler._caption_rights_guard.assert_not_called()
        handler._enqueue_asr.assert_not_called()
        handler._require_current_ingestion_relevance.side_effect = None
        handler.registry["source_associations"] = []
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes") as fetch:
            with self.assertRaises(BlockedJob):
                handler.resolve_platform(job, content)
        fetch.assert_not_called()
        handler._enqueue_asr.assert_not_called()

    def test_rights_revoke_while_feed_fetches_blocks_locator_and_asr(self):
        handler, job, content = self._worker()
        seen = []
        def rights(content, url):
            seen.append(url)
            if len(seen) == 2:
                raise BlockedJob("SOURCE_USE_REVOKED")
            return SimpleNamespace(rights_record_id="rights:synthetic", require=Mock(
                return_value=SimpleNamespace(decision_fingerprint="sha256:synth")))
        handler._caption_rights_guard.side_effect = rights
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom(
            (VIDEO, "Pulp Podcast #64"),
        ))) as fetch:
            with self.assertRaisesRegex(BlockedJob, "SOURCE_USE_REVOKED"):
                handler.resolve_platform(job, content)
        fetch.assert_called_once()
        handler.store.upsert_locator.assert_not_called()
        handler._probe_and_enqueue_caption.assert_not_called()
        handler._enqueue_asr.assert_not_called()

    def test_bounded_catalog_without_absence_review_cannot_dispatch_asr(self):
        handler, job, content = self._worker()
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes",
                   return_value=fetched(atom())):
            with self.assertRaisesRegex(BlockedJob, "YOUTUBE_COPY_ABSENCE_UNREVIEWED"):
                handler.resolve_platform(job, content)
        handler._require_podcast_asr_clearance.assert_not_called()
        handler._enqueue_asr.assert_not_called()

    def test_empty_catalog_requires_separate_podcast_asr_media_rights(self):
        handler, job, content = self._worker()
        handler.registry["source_associations"][0]["asr_absence_reviews"] = [{
            "content_id": content.content_id, "episode_marker": "pulp podcast#64",
            "status": "APPROVED", "approval_ref": "absence:synthetic-64",
            "reviewer_ref": "reviewer:synthetic",
        }]
        handler._require_podcast_asr_clearance.side_effect = BlockedJob("SOURCE_USE_NOT_PERMITTED")
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom())):
            with self.assertRaisesRegex(BlockedJob, "SOURCE_USE_NOT_PERMITTED"):
                handler.resolve_platform(job, content)
        handler._enqueue_asr.assert_not_called()
        handler._require_podcast_asr_clearance.side_effect = None
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes", return_value=fetched(atom())):
            handler.resolve_platform(job, content)
        handler._require_podcast_asr_clearance.assert_called_with(content)
        handler._enqueue_asr.assert_called_once_with(content, reason="PLATFORM_COPY_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()

"""Regression at the worker boundary for contradictory YouTube Atom identities."""
import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche.feed_parsing import parse_feed, _feedparser
from dichiarazioni_pubbliche.worker_errors import BlockedJob
from tests import test_dp182_source_association as dp182
from tests.test_dp182_source_association import CHANNEL, VIDEO, atom, fetched


class AtomIdentityBoundaryTests(unittest.TestCase):
    def test_conflicting_entry_fields_hold_before_locator_caption_and_asr(self):
        base = atom((VIDEO, "Pulp Podcast #64"))
        tag = f"<yt:videoId>{VIDEO}</yt:videoId>"
        cases = {
            "two_titles": base.replace(
                "<title>Pulp Podcast #64</title>",
                "<title>Pulp Podcast #64</title><title>Pulp Podcast #65</title>"),
            "atom_id_conflict": base.replace(
                tag, tag + "<id>yt:video:Alt00000064</id>"),
            "two_atom_ids": base.replace(
                tag, tag + f"<id>yt:video:{VIDEO}</id><id>yt:video:Alt00000064</id>"),
            "entry_channel_conflict": base.replace(
                tag, tag + "<yt:channelId>UC_unapproved_other</yt:channelId>"),
            "two_entry_channels": base.replace(
                tag, tag + f"<yt:channelId>{CHANNEL}</yt:channelId>"
                "<yt:channelId>UC_unapproved_other</yt:channelId>"),
        }
        for label, xml in cases.items():
            with self.subTest(label=label):
                handler, job, content = dp182.AssociationOfflineTests()._worker()
                with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes",
                           return_value=fetched(xml)):
                    with self.assertRaises(BlockedJob):
                        handler.resolve_platform(job, content)
                handler.store.upsert_locator.assert_not_called()
                handler._probe_and_enqueue_caption.assert_not_called()
                handler._enqueue_asr.assert_not_called()

    def test_valid_id_entry_channel_and_utf8_title_still_resolve(self):
        handler, job, content = dp182.AssociationOfflineTests()._worker()
        tag = f"<yt:videoId>{VIDEO}</yt:videoId>"
        xml = atom((VIDEO, "Pulp Podcast #64 — Città")).replace(
            tag, tag + f"<id>yt:video:{VIDEO}</id>"
            f"<yt:channelId>{CHANNEL}</yt:channelId>")
        with patch("dichiarazioni_pubbliche.podcast_youtube_resolution.fetch_bytes",
                   return_value=fetched(xml)):
            handler.resolve_platform(job, content)
        handler.store.upsert_locator.assert_called_once()
        handler._probe_and_enqueue_caption.assert_called_once()
        handler._enqueue_asr.assert_not_called()

    def test_strict_parser_parity_with_optional_feedparser(self):
        xml = atom((VIDEO, "Pulp Podcast #64"))
        tag = f"<yt:videoId>{VIDEO}</yt:videoId>"
        invalid = (
            (xml.replace(tag, tag + "<yt:videoId>Alt00000064</yt:videoId>"),
             "YOUTUBE_ENTRY_VIDEO_ID_AMBIGUOUS"),
            (atom((VIDEO, "Pulp Podcast #64"), (VIDEO, "Pulp Podcast #65")),
             "YOUTUBE_ENTRY_TITLE_CONFLICT"),
            (xml.replace("<title>Pulp Podcast #64</title>",
                         "<title>Pulp Podcast #64</title><title>Pulp Podcast #65</title>"),
             "YOUTUBE_ENTRY_TITLE_AMBIGUOUS"),
            (xml.replace(tag, tag + "<id>yt:video:Alt00000064</id>"),
             "YOUTUBE_ENTRY_ATOM_ID_CONFLICT"),
            (xml.replace(tag, tag + f"<id>yt:video:{VIDEO}</id>"
                         "<id>yt:video:Alt00000064</id>"),
             "YOUTUBE_ENTRY_ATOM_ID_CONFLICT"),
            (xml.replace(tag, tag + "<yt:channelId>UC_unapproved_other</yt:channelId>"),
             "YOUTUBE_ENTRY_CHANNEL_CONFLICT"),
        )
        for parser in (None, _feedparser):
            with patch("dichiarazioni_pubbliche.feed_parsing._feedparser", parser):
                for payload, reason in invalid:
                    with self.subTest(reason=reason, optional=bool(parser)):
                        with self.assertRaisesRegex(ValueError, reason):
                            parse_feed(payload, "youtube")
                good = xml.replace(
                    tag, tag + f"<id>yt:video:{VIDEO}</id>"
                    f"<yt:channelId>{CHANNEL}</yt:channelId>")
                self.assertEqual(parse_feed(good, "youtube")[0].youtube_id, VIDEO)

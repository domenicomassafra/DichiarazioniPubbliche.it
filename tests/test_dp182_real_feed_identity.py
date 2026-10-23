"""#182: real YouTube feed channel spellings and the bounded private canary."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.podcast_youtube_canary import (
    CanaryRefused, resolve_episode,
)
from dichiarazioni_pubbliche.podcast_youtube_channel_identity import (
    canonical_channel_id, same_channel,
)
from dichiarazioni_pubbliche.podcast_youtube_resolution import resolve_associated
from dichiarazioni_pubbliche.source_associations import (
    SourceAssociationBlocked, select_podcast_youtube_association,
)
from dichiarazioni_pubbliche.feed_parsing import parse_feed
from dichiarazioni_pubbliche.source_watcher import parse_youtube_feed

CANONICAL = "UCY99TnBJ8xyat2lpeN_hcEA"
FEED_FORM = CANONICAL[2:]  # what videos.xml reports for the channel itself
CATALOG = f"https://www.youtube.com/feeds/videos.xml?channel_id={CANONICAL}"
FEED = "https://feeds.megaphone.fm/SONY4300078217"
VIDEO = "TpbFntO68Iw"
EPISODE = "Ignazio Benito La Russa a Pulp Podcast. | Pulp Podcast #68"
GUID = "992be98a-cb99-11f1-90b0-533d180ba42d"


def atom(*entries, channel=FEED_FORM, entry_channel=CANONICAL):
    rows = "".join(
        f"<entry><id>yt:video:{video}</id><yt:videoId>{video}</yt:videoId>"
        + (f"<yt:channelId>{entry_channel}</yt:channelId>" if entry_channel else "")
        + f"<title>{title}</title></entry>"
        for video, title in entries
    )
    return ("<feed xmlns='http://www.w3.org/2005/Atom' "
            "xmlns:yt='http://www.youtube.com/xml/schemas/2015'>"
            + (f"<yt:channelId>{channel}</yt:channelId>" if channel else "")
            + f"{rows}</feed>")


def rss(*items, channel="PULP PODCAST"):
    rows = "".join(
        f"<item><title>{title}</title><guid>{guid}</guid>"
        f"<pubDate>Mon, 19 Oct 2026 11:00:00 -0000</pubDate>"
        f"<enclosure url='https://traffic.megaphone.fm/{guid}.mp3' type='audio/mpeg'/>"
        "</item>"
        for title, guid in items
    )
    return f"<rss version='2.0'><channel><title>{channel}</title>{rows}</channel></rss>"


def fetched(body, url=CATALOG):
    return SimpleNamespace(body=body.encode(), charset=None, final_url=url)


def registry(*, status="APPROVED", channel=CANONICAL, associations=True):
    return {
        "schema_version": 1, "source_associations_version": 1,
        "source_associations": [{
            "id": "pulp-podcast-youtube-v1", "version": 1,
            "podcast_source_id": "podcast-pulp-podcast",
            "youtube_source_id": "youtube-pulp-podcast",
            "youtube_channel_id": channel, "status": status,
            "policy_version": "source-association-v1",
            "approval_ref": "docs/evidence/dp182/README.md#approval-record",
            "reviewer_ref": "ai-review:test",
        }] if associations else [],
        "sources": [
            {"id": "podcast-pulp-podcast", "kind": "podcast_rss",
             "discovery_url": FEED},
            {"id": "youtube-pulp-podcast", "kind": "youtube_channel",
             "channel_id": CANONICAL,
             "channel_url": f"https://www.youtube.com/channel/{CANONICAL}",
             "discovery_url": CATALOG},
        ],
    }


def rights(**overrides):
    decision = {
        "id": "dp182-rights-metadata-test", "status": "APPROVED",
        "reviewer_ref": "ai-review:test", "approved_at": "2026-10-23T10:30:00Z",
        "hosts": ["feeds.megaphone.fm", "www.youtube.com"],
        "scopes": ["FETCH", "STORE_METADATA"],
        "constraints": {"expires_at": "2026-11-23T00:00:00Z"},
    }
    decision.update(overrides)
    return decision


def fetcher(atom_xml=None, rss_xml=None, *, atom_url=CATALOG, rss_url=FEED):
    bodies = {
        rss_url: rss_xml if rss_xml is not None else rss((EPISODE, GUID)),
        atom_url: atom_xml if atom_xml is not None else atom((VIDEO, EPISODE)),
    }

    def fetch(url, allow_redirects=True):
        assert allow_redirects is False, "the canary never follows redirects"
        return fetched(bodies[url], url)

    return fetch


class YouTubeChannelIdentityTests(unittest.TestCase):
    def test_both_documented_feed_spellings_are_one_channel(self):
        self.assertTrue(same_channel(FEED_FORM, CANONICAL))
        self.assertFalse(same_channel(CANONICAL.lower(), CANONICAL))
        self.assertFalse(same_channel(FEED_FORM, "UCY99TnBJ8xyat2lpeN_hcEB"))
        self.assertFalse(same_channel("UC_not_the_expected_one", CANONICAL))
        self.assertFalse(same_channel("", CANONICAL))
        self.assertFalse(same_channel(None, CANONICAL))
        self.assertEqual(canonical_channel_id(CANONICAL), CANONICAL)
        for invalid in (FEED_FORM, CANONICAL[:-1], f"{CANONICAL}x", "uc" f"{FEED_FORM}"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                canonical_channel_id(invalid)

    def test_real_shaped_feed_resolves_the_exact_episode(self):
        assoc, source = select_podcast_youtube_association(registry(), "podcast-pulp-podcast")
        xml = atom((VIDEO, EPISODE), ("1X2gHHC_7gw", "La Russa Core."))
        candidate = resolve_associated(
            None, EPISODE, source, association=assoc, check_fetch=lambda _: None,
            fetch_catalog=lambda url, allow_redirects=True: fetched(xml, url),
        )
        self.assertEqual(candidate.video_id, VIDEO)
        self.assertEqual(len(parse_youtube_feed(xml, "youtube-pulp-podcast")), 2)

    def test_feed_level_near_miss_or_other_channel_holds_before_a_locator(self):
        assoc, source = select_podcast_youtube_association(registry(), "podcast-pulp-podcast")
        for channel in (None, "UCY99TnBJ8xyat2lpeN_hcE_", "UCotherChannel000000000x"):
            xml = atom((VIDEO, EPISODE), channel=channel)
            with self.subTest(channel=channel), self.assertRaisesRegex(
                SourceAssociationBlocked, "YOUTUBE_ASSOCIATED_CHANNEL_UNVERIFIED",
            ):
                resolve_associated(
                    None, EPISODE, source, association=assoc,
                    check_fetch=lambda _: None,
                    fetch_catalog=lambda url, allow_redirects=True: fetched(xml, url),
                )

    def test_entry_channel_that_is_another_channel_conflicts_with_the_feed(self):
        for entry_channel in ("UCotherChannel000000000x", "UCY99TnBJ8xyat2lpeN_hcEB"):
            with self.subTest(entry_channel=entry_channel):
                with self.assertRaisesRegex(ValueError, "YOUTUBE_ENTRY_CHANNEL_CONFLICT"):
                    parse_feed(atom((VIDEO, EPISODE), entry_channel=entry_channel), "youtube")


class CanaryTests(unittest.TestCase):
    def test_rights_expiry_and_future_review_block_before_any_fetch(self):
        now = lambda: datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
        cases = (
            (rights(constraints={}), "CANARY_RIGHTS_EXPIRY_MISSING"),
            (rights(constraints={"expires_at": "invalid"}), "CANARY_RIGHTS_DATE_INVALID"),
            (rights(constraints={"expires_at": "2026-10-23T11:00:00Z"}), "CANARY_RIGHTS_EXPIRED"),
            (rights(approved_at="2026-10-24T00:00:00Z"), "CANARY_RIGHTS_REVIEW_IN_FUTURE"),
        )
        def no_fetch(*args, **kwargs):
            self.fail("An invalid rights decision must block before any network access")
        for decision, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(CanaryRefused, reason):
                resolve_episode(
                    registry=registry(), podcast_source_id="podcast-pulp-podcast",
                    rights=decision, guid=GUID, fetcher=no_fetch, clock=now,
                )

    def test_expiration_is_rechecked_after_fetch_before_using_bytes(self):
        calls = 0
        def advancing_fetch(url, allow_redirects=True):
            nonlocal calls
            calls += 1
            return fetched(rss((EPISODE, GUID)), url)
        def clock():
            return datetime(2026, 10, 23 if calls == 0 else 24, 12, tzinfo=timezone.utc)
        decision = rights(constraints={"expires_at": "2026-10-23T23:59:59Z"})
        with self.assertRaisesRegex(CanaryRefused, "CANARY_RIGHTS_EXPIRED"):
            resolve_episode(
                registry=registry(), podcast_source_id="podcast-pulp-podcast",
                rights=decision, guid=GUID, fetcher=advancing_fetch, clock=clock,
            )
        self.assertEqual(calls, 1)

    def test_real_episode_resolves_with_hashes_and_no_side_effects(self):
        receipt = resolve_episode(
            registry=registry(), podcast_source_id="podcast-pulp-podcast",
            rights=rights(), guid=GUID, fetcher=fetcher(),
        )
        self.assertEqual(receipt["decision"], "RESOLVED")
        self.assertEqual(receipt["youtube"]["video_id"], VIDEO)
        self.assertEqual(receipt["podcast"]["guid"], GUID)
        self.assertEqual(receipt["podcast"]["series"], "pulp podcast")
        self.assertEqual(receipt["podcast"]["episode_number"], 68)
        self.assertEqual(receipt["youtube"]["catalog_sha256"],
                         hashlib.sha256(fetcher()(CATALOG, allow_redirects=False).body).hexdigest())
        self.assertEqual(receipt["rights"]["asr_granted"], False)
        self.assertEqual(receipt["publication"], "HOLD")
        self.assertEqual(set(receipt["side_effects"].values()), {0})
        json.dumps(receipt)

    def test_metadata_only_rights_are_mandatory(self):
        for decision in (
            rights(status="PENDING"), rights(scopes=["FETCH"]),
            rights(scopes=["FETCH", "STORE_METADATA", "ASR_MEDIA"]),
            rights(hosts=["example.org"]), rights(hosts=[]),
            rights(reviewer_ref=""), rights(id=""),
        ):
            with self.subTest(decision=decision):
                with self.assertRaises(CanaryRefused):
                    resolve_episode(
                        registry=registry(), podcast_source_id="podcast-pulp-podcast",
                        rights=decision, guid=GUID, fetcher=fetcher(),
                    )

    def test_unapproved_association_or_redirect_never_reaches_a_locator(self):
        for mutated in (registry(associations=False), registry(status="PENDING"),
                        registry(channel="UCotherChannel000000000x")):
            with self.subTest(mutated=mutated["source_associations"]):
                with self.assertRaises(CanaryRefused):
                    resolve_episode(
                        registry=mutated, podcast_source_id="podcast-pulp-podcast",
                        rights=rights(), guid=GUID, fetcher=fetcher(),
                    )
        redirecting = lambda url, allow_redirects=True: fetched(  # noqa: E731
            atom((VIDEO, EPISODE)), url + "&redirected=1",
        )
        with self.assertRaisesRegex(CanaryRefused, "CANARY_REDIRECT_UNAUTHORIZED"):
            resolve_episode(
                registry=registry(), podcast_source_id="podcast-pulp-podcast",
                rights=rights(), guid=GUID, fetcher=redirecting,
            )

    def test_ambiguous_or_unmarked_episodes_are_refused(self):
        twice = fetcher(rss_xml=rss((EPISODE, GUID), (EPISODE, "other-guid")))
        with self.assertRaisesRegex(CanaryRefused, "CANARY_EPISODE_AMBIGUOUS"):
            resolve_episode(registry=registry(), podcast_source_id="podcast-pulp-podcast",
                            rights=rights(), title=EPISODE, fetcher=twice)
        unmarked = fetcher(rss_xml=rss(("Pulp Special senza numero", GUID)))
        with self.assertRaisesRegex(CanaryRefused, "CANARY_EPISODE_MARKER_MISSING"):
            resolve_episode(registry=registry(), podcast_source_id="podcast-pulp-podcast",
                            rights=rights(), title="Pulp Special senza numero",
                            fetcher=unmarked)
        with self.assertRaisesRegex(CanaryRefused, "CANARY_EPISODE_SELECTOR_MISSING"):
            resolve_episode(registry=registry(), podcast_source_id="podcast-pulp-podcast",
                            rights=rights(), fetcher=fetcher())

    def test_a_clip_for_the_same_episode_never_becomes_the_locator(self):
        clips = fetcher(atom_xml=atom(("1X2gHHC_7gw", "La Russa Core.")))
        with self.assertRaisesRegex(CanaryRefused, "CANARY_YOUTUBE_COPY_UNPROVEN"):
            resolve_episode(registry=registry(), podcast_source_id="podcast-pulp-podcast",
                            rights=rights(), guid=GUID, fetcher=clips)
        ambiguous = fetcher(atom_xml=atom((VIDEO, EPISODE), ("Alt00000068", EPISODE)))
        with self.assertRaisesRegex(CanaryRefused, "YOUTUBE_ASSOCIATED_EPISODE_AMBIGUOUS"):
            resolve_episode(registry=registry(), podcast_source_id="podcast-pulp-podcast",
                            rights=rights(), guid=GUID, fetcher=ambiguous)


if __name__ == "__main__":
    unittest.main()

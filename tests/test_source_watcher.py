import sys
import socket
import ssl
import unittest
from email.message import Message
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.source_watcher import (
    DiscoveredContent,
    fetch_bytes,
    filter_discovered_content,
    get_source,
    load_registry,
    parse_podcast_rss,
    parse_youtube_feed,
    plan_ingest,
    select_italian_caption,
    validate_discovery_url,
)


YOUTUBE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns="http://www.w3.org/2005/Atom">
  <title>Pulp Podcast</title>
  <entry>
    <id>yt:video:QaE00l6JZ8w</id>
    <yt:videoId>QaE00l6JZ8w</yt:videoId>
    <title>Beppe Grillo a Pulp Podcast. | Pulp Podcast #64</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=QaE00l6JZ8w"/>
    <author><name>Pulp Podcast</name></author>
    <published>2026-09-21T10:00:00+00:00</published>
  </entry>
</feed>
"""

YOUTUBE_FEED_WITH_SHORT = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>MGy8Gewu7E0</yt:videoId>
    <title>SI TORNA in PALESTRA…..#adv @McFIT</title>
    <link rel="alternate" href="https://www.youtube.com/shorts/MGy8Gewu7E0"/>
    <author><name>Pulp Podcast</name></author>
    <published>2026-09-21T17:07:27+00:00</published>
  </entry>
  <entry>
    <yt:videoId>QaE00l6JZ8w</yt:videoId>
    <title>Beppe Grillo a Pulp Podcast. | Pulp Podcast #64</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=QaE00l6JZ8w"/>
    <author><name>Pulp Podcast</name></author>
    <published>2026-09-21T10:00:00+00:00</published>
  </entry>
</feed>
"""

PODCAST_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>PULP PODCAST</title>
    <item>
      <title>Beppe Grillo a Pulp Podcast | Pulp Podcast #64</title>
      <description>Minutaggio: 0:00 introduzione ospite</description>
      <pubDate>Mon, 21 Sep 2026 11:00:00 -0000</pubDate>
      <itunes:duration>4919</itunes:duration>
      <guid isPermaLink="false">3ef3726c-b596-11f1-9e3d-d31a12201256</guid>
      <enclosure url="https://traffic.megaphone.fm/SONY7440405958.mp3"
                 length="0" type="audio/mpeg"/>
    </item>
  </channel>
</rss>
"""


class SourceWatcherTests(unittest.TestCase):
    def test_dns_rebinding_is_rejected_before_any_socket_connect(self):
        # The initial operator URL validates to public IP; by the time urllib
        # opens the socket the DNS answer is private. No live network is used.
        dns_reads = []

        def rebinding_resolver(host, port, type=None):
            dns_reads.append(host)
            ip = "93.184.216.34" if len(dns_reads) == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

        def connection_boundary(handler, connection_type, request, **kwargs):
            connection = connection_type(request.host, timeout=1, **kwargs)
            connection.connect()
            self.fail("a private peer was reached before SSRF refusal")

        with patch("dichiarazioni_pubbliche.source_watcher.socket.getaddrinfo", side_effect=lambda host, port, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))]), \
             patch("dichiarazioni_pubbliche.source_watcher.socket.socket", side_effect=AssertionError("private socket attempted")) as socket_open, \
             patch("dichiarazioni_pubbliche.source_watcher.urllib.request.AbstractHTTPHandler.do_open", new=connection_boundary):
            with self.assertRaisesRegex(ValueError, "DISCOVERY_URL_NONPUBLIC_IP"):
                fetch_bytes("https://rebind.example.test/feed", resolver=rebinding_resolver)
        socket_open.assert_not_called()
        self.assertGreaterEqual(len(dns_reads), 2)

    def test_https_proxy_environment_cannot_change_connection_destination(self):
        public_dns = lambda host, port, type=None: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))
        ]
        destinations = []

        class Response:
            status = 200
            code = 200
            msg = "OK"
            headers = Message()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def geturl(self): return "https://example.test/feed"
            def getcode(self): return 200
            def info(self): return self.headers
            def read(self, limit): return b"ok"

        def connection_boundary(handler, connection_type, request, **kwargs):
            destinations.append((request.host, request.get_full_url(), request.has_proxy()))
            return Response()

        with patch.dict("os.environ", {"https_proxy": "http://127.0.0.1:3128", "HTTPS_PROXY": "http://127.0.0.1:3128", "no_proxy": "", "NO_PROXY": ""}), \
             patch("dichiarazioni_pubbliche.source_watcher.urllib.request.AbstractHTTPHandler.do_open", new=connection_boundary):
            fetched = fetch_bytes("https://example.test/feed", resolver=public_dns)
        self.assertEqual(fetched.body, b"ok")
        self.assertEqual(destinations, [("example.test", "https://example.test/feed", False)])

    def test_https_transport_pins_public_socket_peer_and_preserves_verified_hostname(self):
        connections, tls_names = [], []

        class FakeSocket:
            def settimeout(self, value): self.timeout = value
            def connect(self, sockaddr):
                self.peer = sockaddr
                connections.append(sockaddr)
            def getpeername(self): return self.peer
            def close(self): pass

        class Response:
            code = status = 200
            msg = "OK"
            headers = Message()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def geturl(self): return "https://example.test/feed"
            def getcode(self): return 200
            def info(self): return self.headers
            def read(self, limit): return b"ok"

        public_dns = lambda host, port, type=None: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))
        ]

        def fake_tls(context, raw_socket, server_hostname):
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            tls_names.append(server_hostname)
            return raw_socket

        def boundary(handler, connection_type, request, **kwargs):
            connection = connection_type(request.host, timeout=3, **kwargs)
            connection.connect()
            connection.close()
            return Response()

        with patch("dichiarazioni_pubbliche.source_watcher.socket.socket", side_effect=lambda *args: FakeSocket()), \
             patch.object(ssl.SSLContext, "wrap_socket", new=fake_tls), \
             patch("dichiarazioni_pubbliche.source_watcher.urllib.request.AbstractHTTPHandler.do_open", new=boundary), \
             patch("dichiarazioni_pubbliche.source_watcher.socket.getaddrinfo", side_effect=AssertionError("socket connect must not resolve hostname again")):
            fetched = fetch_bytes("https://example.test/feed", resolver=public_dns)
        self.assertEqual(fetched.body, b"ok")
        self.assertEqual(connections, [("93.184.216.34", 443)])
        self.assertEqual(tls_names, ["example.test"])

    def test_socket_peer_mismatch_is_rejected_before_tls(self):
        attempts = []

        class SwappedPeer:
            def settimeout(self, value): pass
            def connect(self, address): attempts.append(address)
            def getpeername(self): return ("127.0.0.1", 443)
            def close(self): pass

        public_dns = lambda host, port, type=None: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))
        ]

        def boundary(handler, connection_type, request, **kwargs):
            connection = connection_type(request.host, timeout=3, **kwargs)
            connection.connect()
            self.fail("mismatched peer was allowed into TLS")

        with patch("dichiarazioni_pubbliche.source_watcher.socket.socket", side_effect=lambda *args: SwappedPeer()), \
             patch.object(ssl.SSLContext, "wrap_socket", side_effect=AssertionError("TLS with wrong peer")), \
             patch("dichiarazioni_pubbliche.source_watcher.urllib.request.AbstractHTTPHandler.do_open", new=boundary):
            with self.assertRaisesRegex(ValueError, "DISCOVERY_URL_PEER_MISMATCH"):
                fetch_bytes("https://example.test/feed", resolver=public_dns)
        self.assertEqual(attempts, [("93.184.216.34", 443)])

    def test_dns_mixed_public_private_addresses_fail_closed_before_any_connect(self):
        public_dns = lambda host, port, type=None: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port)),
        ]
        with patch("dichiarazioni_pubbliche.source_watcher.socket.socket") as socket_open:
            with self.assertRaisesRegex(ValueError, "DISCOVERY_URL_NONPUBLIC_IP"):
                fetch_bytes("https://example.test/feed", resolver=public_dns)
        socket_open.assert_not_called()

    def test_redirect_to_private_dns_is_blocked_before_followup_transport(self):
        destinations = []

        def resolver(host, port, type=None):
            ip = "127.0.0.1" if host == "internal.example.test" else "93.184.216.34"
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

        class Redirect:
            status = code = 302
            msg = "Found"
            headers = Message()
            headers["Location"] = "https://internal.example.test/admin"
            def info(self): return self.headers
            def getcode(self): return 302
            def geturl(self): return "https://example.test/start"
            def read(self, *args): return b""
            def close(self): pass

        def boundary(handler, connection_type, request, **kwargs):
            destinations.append(request.get_full_url())
            return Redirect()

        with patch("dichiarazioni_pubbliche.source_watcher.urllib.request.AbstractHTTPHandler.do_open", new=boundary):
            with self.assertRaisesRegex(ValueError, "DISCOVERY_URL_NONPUBLIC_IP"):
                fetch_bytes("https://example.test/start", resolver=resolver)
        self.assertEqual(destinations, ["https://example.test/start"])

    def test_discovery_url_refuses_ssrf_shapes(self):
        public_dns = lambda host, port, type=None: [
            (2, 1, 6, "", ("93.184.216.34", port))
        ]
        private_dns = lambda host, port, type=None: [
            (2, 1, 6, "", ("127.0.0.1", port))
        ]
        self.assertEqual(
            validate_discovery_url(
                "https://example.test/feed", resolver=public_dns
            ),
            "https://example.test/feed",
        )
        with self.assertRaisesRegex(ValueError, "HTTPS_REQUIRED"):
            validate_discovery_url(
                "http://example.test/feed", resolver=public_dns
            )
        with self.assertRaisesRegex(ValueError, "AUTHORITY_REFUSED"):
            validate_discovery_url(
                "https://user:pass@example.test/feed", resolver=public_dns
            )
        with self.assertRaisesRegex(ValueError, "NONPUBLIC_IP"):
            validate_discovery_url(
                "https://example.test/feed", resolver=private_dns
            )

    def test_fetch_bytes_returns_bounded_response_metadata(self):
        public_dns = lambda host, port, type=None: [(2, 1, 6, "", ("93.184.216.34", port))]

        class Response:
            status = 200
            def __init__(self):
                self.headers = Message()
                self.headers["Content-Type"] = "text/html; charset=utf-8"
                self.headers["Content-Length"] = "12"
                self.headers["ETag"] = '"abc"'
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return b"<p>Hello</p>"
            def geturl(self): return "https://example.test/page"
            def getcode(self): return 200

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dichiarazioni_pubbliche.source_watcher.urllib.request.build_opener", return_value=Opener()):
            result = fetch_bytes(
                "https://example.test/page", resolver=public_dns, max_response_bytes=1024
            )
        self.assertEqual(result.body, b"<p>Hello</p>")
        self.assertEqual(result.media_type, "text/html")
        self.assertEqual(result.charset, "utf-8")
        self.assertEqual(result.content_length, 12)
        self.assertEqual(result.etag, '"abc"')

    def test_fetch_bytes_enforces_size_limit(self):
        public_dns = lambda host, port, type=None: [(2, 1, 6, "", ("93.184.216.34", port))]

        class Response:
            status = 200
            def __init__(self):
                self.headers = Message()
                self.headers["Content-Type"] = "text/plain"
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return b"123456"
            def geturl(self): return "https://example.test/page"
            def getcode(self): return 200

        class Opener:
            def open(self, request, timeout): return Response()

        with patch("dichiarazioni_pubbliche.source_watcher.urllib.request.build_opener", return_value=Opener()):
            with self.assertRaisesRegex(ValueError, "RESPONSE_TOO_LARGE"):
                fetch_bytes("https://example.test/page", resolver=public_dns, max_response_bytes=5)

    def test_parse_youtube_feed(self):
        items = parse_youtube_feed(YOUTUBE_FEED, "youtube-pulp-podcast")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].external_id, "QaE00l6JZ8w")
        self.assertEqual(items[0].author, "Pulp Podcast")

    def test_selects_original_italian_auto_caption(self):
        metadata = {
            "subtitles": {},
            "automatic_captions": {
                "it-orig": [{"ext": "vtt", "url": "https://example.test/it.vtt"}],
                "en": [{"ext": "vtt", "url": "https://example.test/en.vtt"}],
            },
        }
        selected = select_italian_caption(metadata)
        self.assertEqual(selected["kind"], "automatic_caption")
        self.assertEqual(selected["language"], "it-orig")

    def test_parse_podcast_rss(self):
        items = parse_podcast_rss(PODCAST_RSS, "youtube-pulp-podcast")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].platform, "podcast_rss")
        self.assertEqual(items[0].duration_seconds, 4919)
        self.assertEqual(items[0].media_type, "audio/mpeg")
        self.assertTrue(items[0].media_url.endswith("SONY7440405958.mp3"))

    def test_caption_plan_never_downloads_video(self):
        registry = load_registry()
        source = get_source(registry, "youtube-pulp-podcast")
        content = DiscoveredContent(
            source_id=source["id"],
            platform="youtube",
            external_id="QaE00l6JZ8w",
            title="Beppe Grillo a Pulp Podcast. | Pulp Podcast #64",
            canonical_url="https://www.youtube.com/watch?v=QaE00l6JZ8w",
            published_at="2026-09-21T10:00:00+00:00",
            author="Pulp Podcast",
        )
        metadata = {
            "subtitles": {},
            "automatic_captions": {
                "it-orig": [{"ext": "vtt", "url": "https://example.test/it.vtt"}]
            },
        }
        plan = plan_ingest(source, content, youtube_metadata=metadata)
        self.assertEqual(plan["action"], "ACQUIRE_CAPTION")
        self.assertFalse(plan["download_media"])

    def test_pulp_policy_filters_promotional_shorts(self):
        registry = load_registry()
        source = get_source(registry, "youtube-pulp-podcast")
        raw = parse_youtube_feed(
            YOUTUBE_FEED_WITH_SHORT,
            "youtube-pulp-podcast",
        )
        filtered = filter_discovered_content(source, raw)
        self.assertEqual([row.external_id for row in filtered], ["QaE00l6JZ8w"])

    def test_podcast_plan_is_audio_first_and_never_downloads_video(self):
        registry = load_registry()
        source = get_source(registry, "youtube-pulp-podcast")
        content = parse_podcast_rss(PODCAST_RSS, source["id"])[0]
        plan = plan_ingest(source, content)
        self.assertEqual(plan["action"], "RESOLVE_PLATFORM_TRANSCRIPT_THEN_AUDIO")
        self.assertFalse(plan["download_media"])
        self.assertTrue(plan["prefer_audio_only"])
        self.assertTrue(plan["podcast_audio_url_available"])


if __name__ == "__main__":
    unittest.main()

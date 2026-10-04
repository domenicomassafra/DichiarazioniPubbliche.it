import os
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.evidence_runtime import (  # noqa: E402
    EvidenceCache,
    EvidencePolicyError,
    EvidenceRateLimited,
    FileRateLimiter,
    SafeEvidenceFetcher,
    deterministic_evidence_id,
    normalized_url,
    validate_evidence_url,
)


SOURCE = {
    "id": "official-test",
    "allowed_hosts": ["example.com"],
    "allowed_path_prefixes": ["/official/"],
}


def public_dns(host, port, type=None):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


def private_dns(host, port, type=None):
    return [(2, 1, 6, "", ("127.0.0.1", port))]


class EvidenceRuntimeTests(unittest.TestCase):
    def test_partial_http_body_is_refused_when_content_length_is_known(self):
        class FakeResponse:
            status = 200

            def __init__(self):
                self.headers = Message()
                self.headers["Content-Type"] = "text/plain"
                self.headers["Content-Length"] = "10"

            def geturl(self):
                return "https://example.com/official/x"

            def read(self, limit):
                return b"short"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class FakeOpener:
            def open(self, request, timeout):
                return FakeResponse()

        registry = {
            "defaults": {"cache_ttl_seconds": 0, "max_response_bytes": 1024},
            "sources": [
                {
                    **SOURCE,
                    "publisher": "Test",
                    "evidence_class": "PRIMARY_OFFICIAL",
                    "authoritative": True,
                    "accepted_content_types": ["text/plain"],
                    "allowed_methods": ["GET"],
                    "rate_limit": {"requests": 10, "window_seconds": 60},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = SafeEvidenceFetcher(
                registry=registry,
                cache=EvidenceCache(Path(tmp) / "cache"),
                rate_limiter=FileRateLimiter(Path(tmp) / "rate.json"),
                resolver=public_dns,
            )
            with patch(
                "dichiarazioni_pubbliche.evidence_runtime.urllib.request.build_opener",
                return_value=FakeOpener(),
            ):
                with self.assertRaisesRegex(
                    EvidencePolicyError, "RESPONSE_INCOMPLETE"
                ):
                    fetcher.fetch(
                        "official-test",
                        "https://example.com/official/x",
                    )
            self.assertEqual(
                list((Path(tmp) / "cache" / "sha256").glob("*/*")),
                [],
            )

    def test_url_policy_refuses_ssrf_shapes(self):
        with self.assertRaisesRegex(EvidencePolicyError, "HTTPS_REQUIRED"):
            validate_evidence_url(
                SOURCE, "http://example.com/official/x", resolver=public_dns
            )
        with self.assertRaisesRegex(EvidencePolicyError, "HOST_NOT_ALLOWLISTED"):
            validate_evidence_url(
                SOURCE, "https://evil.test/official/x", resolver=public_dns
            )
        with self.assertRaisesRegex(EvidencePolicyError, "PATH_NOT_ALLOWLISTED"):
            validate_evidence_url(
                SOURCE, "https://example.com/private/x", resolver=public_dns
            )
        with self.assertRaisesRegex(EvidencePolicyError, "NONPUBLIC_IP"):
            validate_evidence_url(
                SOURCE, "https://example.com/official/x", resolver=private_dns
            )

    def test_normalization_drops_fragment_not_query(self):
        self.assertEqual(
            normalized_url("HTTPS://EXAMPLE.COM/official/x?a=1#frag"),
            "https://example.com/official/x?a=1",
        )

    def test_rate_limiter_is_persistent_and_fail_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            limiter = FileRateLimiter(Path(tmp) / "rate.json")
            limiter.acquire("s", requests=2, window_seconds=60, now=1000)
            limiter.acquire("s", requests=2, window_seconds=60, now=1001)
            with self.assertRaises(EvidenceRateLimited):
                limiter.acquire("s", requests=2, window_seconds=60, now=1002)
            self.assertEqual(os.stat(Path(tmp) / "rate.json").st_mode & 0o777, 0o600)

    def test_cache_is_content_addressed_and_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = EvidenceCache(Path(tmp) / "evidence")
            body = b"official evidence bytes"
            path = cache.store(
                "official-test",
                "https://example.com/official/x",
                body,
                {
                    "final_url": "https://example.com/official/x",
                    "fetched_epoch": 1000,
                    "fetched_at": "2026-09-22T00:00:00+00:00",
                    "http_status": 200,
                    "content_type": "text/html",
                    "response_bytes": len(body),
                    "etag": None,
                    "last_modified": None,
                    "authoritative": True,
                    "evidence_class": "PRIMARY_OFFICIAL",
                    "publisher": "Test",
                },
            )
            self.assertEqual(path.read_bytes(), body)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(cache.root).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(cache.root / "sha256").st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(cache.root / "url").st_mode & 0o777, 0o700)
            index = cache.load_index(
                "official-test", "https://example.com/official/x"
            )
            self.assertIsNotNone(index)
            self.assertEqual(index["content_sha256"], path.parent.name)

    def test_evidence_id_versions_mutable_url_by_content_hash(self):
        left = deterministic_evidence_id(
            "s", "https://example.com/official/x", "a" * 64
        )
        right = deterministic_evidence_id(
            "s", "https://example.com/official/x", "b" * 64
        )
        self.assertNotEqual(left, right)

    def test_cache_key_distinguishes_post_bodies(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = EvidenceCache(Path(tmp) / "evidence")
            a = cache.index_path(
                "s",
                "https://example.com/official/search",
                method="POST",
                request_body_sha256="a" * 64,
            )
            b = cache.index_path(
                "s",
                "https://example.com/official/search",
                method="POST",
                request_body_sha256="b" * 64,
            )
            self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()

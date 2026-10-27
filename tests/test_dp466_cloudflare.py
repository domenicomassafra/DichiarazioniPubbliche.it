"""Cache invalidation is not acknowledged until public edge readback is safe."""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))


class FakeResponse:
    def __init__(self, code, payload, headers=None):
        self.status = code
        self.body = io.BytesIO(payload)
        self.headers = headers or {}

    def read(self, limit=-1):
        return self.body.read(limit)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class CorrectionPurgeTests(unittest.TestCase):
    def test_purge_ack_requires_every_public_url_withdrawn(self):
        from dichiarazioni_pubbliche.cloudflare_correction_purge import CloudflareCorrectionPurge

        calls = []

        def fetch(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(json.loads(request.data), {"purge_everything": True})
                return FakeResponse(200, b'{"success":true,"errors":[],"result":{"id":"purge-1"}}')
            return FakeResponse(503, b'{"error":"PUBLIC_PROJECTION_UNAVAILABLE"}', {"Cache-Control": "no-store"})

        with patch("urllib.request.urlopen", side_effect=fetch):
            purger = CloudflareCorrectionPurge(zone_id="a" * 32, token="fixture-token", site_origin="https://dichiarazionipubbliche.it")
            self.assertTrue(purger("finding:123"))
        self.assertEqual(len(calls), 4)
        self.assertIn("https://dichiarazionipubbliche.it/", calls)
        self.assertIn("https://dichiarazionipubbliche.it/api/v1/index.json", calls)

    def test_200_from_old_cdn_is_never_accepted(self):
        from dichiarazioni_pubbliche.cloudflare_correction_purge import CloudflareCorrectionPurge

        responses = iter([
            FakeResponse(200, b'{"success":true,"errors":[]}'),
            FakeResponse(200, b"stale HTML", {"Cache-Control": "public, max-age=3600"}),
        ])
        with patch("urllib.request.urlopen", side_effect=lambda *args, **kwargs: next(responses)):
            purger = CloudflareCorrectionPurge(zone_id="a" * 32, token="fixture-token", site_origin="https://dichiarazionipubbliche.it")
            self.assertFalse(purger("finding:123"))

    def test_missing_purge_ack_does_not_probe(self):
        from dichiarazioni_pubbliche.cloudflare_correction_purge import CloudflareCorrectionPurge

        with patch("urllib.request.urlopen", return_value=FakeResponse(200, b'{"success":false,"errors":[{"code":123}]}')) as fetch:
            purger = CloudflareCorrectionPurge(zone_id="a" * 32, token="fixture-token", site_origin="https://dichiarazionipubbliche.it")
            self.assertFalse(purger("finding:123"))
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()

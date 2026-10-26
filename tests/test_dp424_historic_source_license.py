"""DP-424: historical Senate versions retain their independently checked licence."""

import unittest

from dichiarazioni_pubbliche.senato_akoma_corpus_handoff import (
    SenatoAkomaParser,
    prepare_senato_corpus_handoff,
    verify_senato_handoff_roundtrip,
)
from tests.test_senato_akoma_stenographic import URL, blob_sha, fixture
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


class HistoricSenatoLicenseTest(unittest.TestCase):
    def test_historical_license_follows_attested_version(self):
        raw = fixture()
        prepared = prepare_senato_corpus_handoff(
            raw, source_raw_url=URL, expected_blob_sha1=blob_sha(raw),
            content_id="content:dp424-test",
            observed_at="2026-10-25T19:00:00Z",
            source_license_id="CC-BY-3.0",
        )
        self.assertEqual(prepared.source.source_license_id, "CC-BY-3.0")
        self.assertTrue(prepared.source.source_license_url.endswith("/README.MD"))
        self.assertEqual(prepared.capture.metadata["source_license_url"],
                         prepared.source.source_license_url)
        self.assertEqual(prepared.capture.metadata["source_license_id"], "CC-BY-3.0")
        verify_senato_handoff_roundtrip(prepared, raw)
        parsed = SenatoAkomaParser(
            source_raw_url=URL, expected_blob_sha1=blob_sha(raw),
            source_license_id="CC-BY-3.0",
        ).parse(FetchedBytes(
            body=raw, final_url=URL, status_code=200,
            media_type="text/plain", charset="utf-8",
            content_length=len(raw),
        ))
        self.assertEqual(parsed.status, "SUCCEEDED")
        self.assertEqual(parsed.metadata["source_license_id"], "CC-BY-3.0")

    def test_unsupported_license_identifier_fails_closed(self):
        with self.assertRaises(ValueError):
            SenatoAkomaParser(
                source_raw_url=URL, expected_blob_sha1=blob_sha(fixture()),
                source_license_id="UNVERIFIED",
            )


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tools"))

from dp326_senato_private_discovery import (
    CONTENT_BLOB_SHA1, DOCUMENT_PATH, LICENSE_SHA256, NOTICE_SHA256,
    SOURCE_URL, SenatoMetadataAdapter, verified_metadata_hit,
    verified_terms_evidence, senato_discovery_manifest,
)


class SenatoPrivateMetadataTests(unittest.TestCase):
    def setUp(self):
        self.license = {
            "repository_commit_membership": "CONFIRMED_BY_GITHUB_API",
            "source_license_notice": "CC-BY-4.0",
            "license_notice_sha256": NOTICE_SHA256,
            "license_document_sha256": LICENSE_SHA256,
        }
        self.document = {
            "path": DOCUMENT_PATH,
            "sha": CONTENT_BLOB_SHA1,
            "type": "file",
            "size": 201,
            "download_url": SOURCE_URL,
        }

    def test_exact_official_file_and_licence_produce_one_private_discovery_hit(self):
        hit = verified_metadata_hit(self.license, self.document)
        self.assertEqual(hit.canonical_url, SOURCE_URL)
        self.assertEqual(hit.source_family, "senato_open_data_akn")
        self.assertEqual(hit.metadata["license_id"], "CC-BY-4.0")
        manifest = senato_discovery_manifest()
        adapter = SenatoMetadataAdapter(hit)
        request = type("Request", (), {"query": manifest.queries[0]})()
        result = adapter.discover(request)
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0], hit)
        self.assertEqual(str(result.cost_usd), "0")

    def test_missing_or_changed_license_or_blob_cannot_become_a_hit(self):
        for key, value in (
            ("license_notice_sha256", "0" * 64),
            ("source_license_notice", "CC-BY-3.0"),
            ("repository_commit_membership", "UNVERIFIED"),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "DP326_OFFICIAL_LICENSE_UNVERIFIED"):
                    verified_metadata_hit({**self.license, key: value}, self.document)
        for key, value in (
            ("sha", "f" * 40),
            ("path", "Leg19/other.xml"),
            ("download_url", "https://example.com/other"),
            ("type", "dir"),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "DP326_OFFICIAL_DOCUMENT_UNVERIFIED"):
                    verified_metadata_hit(self.license, {**self.document, key: value})

    def test_adapter_refuses_same_url_with_tampered_source_or_license(self):
        from dataclasses import replace
        hit = verified_metadata_hit(self.license, self.document)
        for candidate in (
            replace(hit, source_id="source:other"),
            replace(hit, metadata={**hit.metadata, "license_notice_sha256": "f" * 64}),
        ):
            with self.assertRaisesRegex(ValueError, "DP326_ADAPTER_SOURCE_UNVERIFIED"):
                SenatoMetadataAdapter(candidate)

    def test_machine_license_attestation_is_scoped_to_metadata(self):
        evidence = verified_terms_evidence(self.license)
        from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import attest_licence_use
        decision = attest_licence_use(evidence)
        self.assertEqual(decision.status, "APPROVED")
        self.assertTrue(decision.private_only)
        self.assertFalse(decision.publication_authorized)
        self.assertEqual(senato_discovery_manifest().max_results, 1)


if __name__ == "__main__":
    unittest.main()

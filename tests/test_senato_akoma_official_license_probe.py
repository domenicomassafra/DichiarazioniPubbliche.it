"""DP-233 independent official immutable-commit license evidence checks.

No live fetch inside unit tests, no owner/source rights approval.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from tools import senato_akoma_official_readonly_smoke as smoke


class OfficialSourceRightsEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.api = f"https://api.github.com/repos/{smoke.REPOSITORY}/commits/{smoke.COMMIT}"
        self.notice = (
            f"https://raw.githubusercontent.com/{smoke.REPOSITORY}/{smoke.COMMIT}/README.MD"
        )
        self.license = (
            f"https://raw.githubusercontent.com/{smoke.REPOSITORY}/{smoke.COMMIT}/LICENSE.MD"
        )
        self.commit = {
            "sha": smoke.COMMIT, "url": self.api,
            "html_url": f"https://github.com/{smoke.REPOSITORY}/commit/{smoke.COMMIT}",
        }
        self.docs = {
            self.api: json.dumps(self.commit).encode(),
            self.notice: b"# Senate Dataset\n\n## Licenza ##\n\nCC BY 4.0\n",
            self.license: b"Creative Commons Attribution 4.0 International Public License",
        }

    def probe(self):
        def fetched(url, *, max_bytes=smoke.MAX_SOURCE_BYTES):
            self.assertIn(url, {self.api, self.notice, self.license})
            self.assertLessEqual(max_bytes, smoke.MAX_METADATA_BYTES)
            if url not in self.docs:
                raise ValueError("DP233_OFFICIAL_SOURCE_MISSING")
            result = self.docs[url]
            if len(result) > max_bytes:
                raise ValueError("DP233_OFFICIAL_RAW_SOURCE_SIZE_INVALID")
            return result

        with patch.object(smoke, "_fetch", side_effect=fetched) as caller:
            result = smoke.verify_pinned_official_license()
        self.assertEqual(caller.call_count, 3)
        return result

    def test_commit_scoped_license_receipts_do_not_authorize_any_rights(self):
        receipt = self.probe()
        self.assertEqual(receipt["repository_commit_membership"], "CONFIRMED_BY_GITHUB_API")
        self.assertEqual(receipt["source_license_notice"], "CC-BY-4.0")
        self.assertFalse(receipt["license_observation_is_owner_approval"])
        self.assertTrue(receipt["rights_review_required"])
        self.assertEqual(receipt["license_document_sha256"], hashlib.sha256(self.docs[self.license]).hexdigest())
        self.assertIn(smoke.COMMIT, receipt["license_document_url"])
        for bad in ("license_granted", "approval", "right_to_publish", "source_body"):
            self.assertNotIn(bad, receipt)

    def test_foreign_commit_or_repository_receipt_fails_closed(self):
        for diff in ({"sha": "a" * 40}, {"url": "https://api.github.com/elsewhere"},
                     {"html_url": "https://github.com/other/commit/fake"},
                     {"sha": None}):
            self.docs[self.api] = json.dumps(self.commit | diff).encode()
            with self.subTest(diff=diff), self.assertRaisesRegex(ValueError, "MEMBERSHIP_UNVERIFIED"):
                self.probe()
        self.docs[self.api] = b"not-json"
        with self.assertRaisesRegex(ValueError, "COMMIT_RECEIPT_INVALID"):
            self.probe()

    def test_missing_or_other_license_prohibited(self):
        for url, altered in (
            (self.notice, b"## Licenza ##\nCC BY 3.0\n"),
            (self.notice, b"CC BY 4.0\n"),
            (self.license, b"Creative Commons Attribution 3.0"),
        ):
            original = self.docs[url]
            self.docs[url] = altered
            with self.subTest(url=url, altered=altered), self.assertRaisesRegex(
                ValueError, "LICENSE_RECEIPT_MISMATCH"
            ):
                self.probe()
            self.docs[url] = original
        self.docs[self.license] = b"\xff"
        with self.assertRaisesRegex(ValueError, "LICENSE_RECEIPT_INVALID"):
            self.probe()


if __name__ == "__main__":
    unittest.main()

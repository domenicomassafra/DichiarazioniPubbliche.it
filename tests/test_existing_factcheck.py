import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.existing_factcheck import (  # noqa: E402
    ExistingFactCheckError,
    GoogleFactCheckAdapter,
    normalize_google_factcheck_response,
)


PAYLOAD = {
    "claims": [
        {
            "text": "The example claim.",
            "claimant": "Example Person",
            "claimDate": "2026-09-01T00:00:00Z",
            "claimReview": [
                {
                    "publisher": {"name": "Example Check", "site": "check.example"},
                    "url": "https://check.example/review/1",
                    "title": "Review title",
                    "reviewDate": "2026-09-02T00:00:00Z",
                    "textualRating": "False",
                    "languageCode": "en",
                }
            ],
        }
    ],
    "nextPageToken": "next-1",
}


class ExistingFactCheckTests(unittest.TestCase):
    def test_normalization_preserves_external_rating_as_text_only(self):
        result = normalize_google_factcheck_response(PAYLOAD)
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.claim_text, "The example claim.")
        self.assertEqual(record.textual_rating, "False")
        self.assertFalse(hasattr(record, "assessment"))
        self.assertFalse(hasattr(record, "verdict"))

    def test_unsafe_review_url_is_dropped(self):
        payload = json.loads(json.dumps(PAYLOAD))
        payload["claims"][0]["claimReview"][0]["url"] = "javascript:alert(1)"
        result = normalize_google_factcheck_response(payload)
        self.assertEqual(result.records, ())

    def test_search_is_bounded_and_receipt_does_not_leak_api_key(self):
        captured = {}

        def transport(url, *, timeout_seconds):
            captured["url"] = url
            captured["timeout"] = timeout_seconds
            return json.dumps(PAYLOAD).encode()

        adapter = GoogleFactCheckAdapter("secret-api-key", transport=transport)
        result = adapter.search(
            "example claim",
            language_code="it",
            max_age_days=365,
            page_size=7,
        )
        params = parse_qs(urlsplit(captured["url"]).query)
        self.assertEqual(params["query"], ["example claim"])
        self.assertEqual(params["languageCode"], ["it"])
        self.assertEqual(params["pageSize"], ["7"])
        self.assertEqual(params["key"], ["secret-api-key"])
        receipt_text = json.dumps(result.provider_receipt, sort_keys=True)
        self.assertNotIn("secret-api-key", receipt_text)
        self.assertNotIn("example claim", receipt_text)
        self.assertIn("query_sha256", result.provider_receipt)

    def test_missing_key_and_unbounded_page_size_fail_closed(self):
        with self.assertRaisesRegex(ExistingFactCheckError, "FACTCHECK_API_KEY_REQUIRED"):
            GoogleFactCheckAdapter("")
        adapter = GoogleFactCheckAdapter("key", transport=lambda *_args, **_kwargs: b"{}")
        with self.assertRaisesRegex(ExistingFactCheckError, "FACTCHECK_PAGE_SIZE_INVALID"):
            adapter.search("query", page_size=1000)

    def test_query_or_publisher_is_required(self):
        adapter = GoogleFactCheckAdapter("key", transport=lambda *_args, **_kwargs: b"{}")
        with self.assertRaisesRegex(
            ExistingFactCheckError,
            "FACTCHECK_QUERY_OR_PUBLISHER_REQUIRED",
        ):
            adapter.search("")


if __name__ == "__main__":
    unittest.main()

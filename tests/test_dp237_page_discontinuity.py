"""Exact written source span must not silently merge adjacent pages."""

import unittest

from dichiarazioni_pubbliche.original_source_resolver import resolve_exact_source_locator
from tests.test_dp237_exact_locator import capture, sha, written_locator, written_passage


class PageDiscontinuityTests(unittest.TestCase):
    def test_hash_matching_cross_page_quote_is_blocked(self):
        canonical = "Prima pagina.\fSeconda pagina."
        source_body = canonical.encode("utf-8")
        passage = written_passage(
            end_char=len(canonical), private_text=canonical, text_sha256=sha(canonical),
        )
        source_capture = capture(content_sha256=sha(source_body))
        quote = "pagina.\fSeconda"
        start = canonical.index(quote)
        locator = written_locator(
            capture_sha256=source_capture.content_sha256, quote_start=start,
            quote_end=start + len(quote), quote_sha256=sha(quote),
        )
        result = resolve_exact_source_locator(
            locator, passage=passage, capture=source_capture,
            source_body=source_body, canonical_text=canonical, quote_text=quote,
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.blockers, ("LOCATOR_QUOTE_DISCONTINUITY",))


if __name__ == "__main__":
    unittest.main()

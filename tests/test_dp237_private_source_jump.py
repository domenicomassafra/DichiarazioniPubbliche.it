"""Private source navigation may be proposed only for independently pinned bytes."""

from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.original_source_resolver import (
    resolve_exact_source_locator, resolve_reviewed_original_source,
    OriginalSourceResolution,
)
from dichiarazioni_pubbliche.private_source_jump import private_written_source_jump as verified_jump
from tests.test_dp237_exact_locator import (
    SOURCE_HTML,
    QUOTE,
    capture,
    page_fixture,
    written,
    written_locator,
)


def private_written_source_jump(**options):
    """A reviewed original and a same-URL live read are required for navigation."""
    doc = options["capture"]
    options.setdefault("observed_live_url", doc.final_url)
    options.setdefault("original_source", resolve_reviewed_original_source(
        doc.content_id,
        families=[{"id": "family:reviewed", "status": "APPROVED",
                   "root_content_id": doc.content_id}], edges=(),
    ))
    return verified_jump(**options)


class PrivateSourceJumpTests(unittest.TestCase):
    def test_verified_pdf_page_opens_real_browser_page(self):
        pdf, doc, page, locator, page_text, excerpt = page_fixture()
        doc = replace(
            doc, final_url="https://ntrs.nasa.gov/file.pdf", rights_status="CLEARED"
        )
        result = resolve_exact_source_locator(
            locator,
            passage=page,
            capture=doc,
            source_body=pdf,
            page_text=page_text,
            quote_text=excerpt,
        )
        self.assertEqual(result.status, "LOCATED")
        jump = private_written_source_jump(
            locator=locator,
            resolution=result,
            capture=doc,
            observed_live_sha256=doc.content_sha256,
            quote_text=excerpt,
        )
        self.assertEqual(jump.status, "READY_PAGE")
        self.assertEqual(jump.url, "https://ntrs.nasa.gov/file.pdf#page=2")
        self.assertEqual(jump.precision, "PAGE")
        self.assertEqual(jump.reason, "PDF_PAGE_ONLY")

    def test_browser_text_fragment_preserves_exact_quote_without_script(self):
        doc = replace(
            capture(), final_url="https://www.senato.it/speech", rights_status="CLEARED"
        )
        resolution = written(capture=doc)
        jump = private_written_source_jump(
            locator=written_locator(),
            resolution=resolution,
            capture=doc,
            observed_live_sha256=hashlib.sha256(SOURCE_HTML).hexdigest(),
            quote_text=QUOTE,
        )
        self.assertEqual(jump.status, "BEST_EFFORT_TEXT")
        self.assertEqual(
            jump.url, "https://www.senato.it/speech#:~:text=No%2C%20non%20aumenta."
        )
        self.assertEqual(jump.reason, "BROWSER_TEXT_FRAGMENT_UNCONFIRMED")

    def test_rejects_stale_and_mismatched_version_before_offering_jump(self):
        pdf, doc, page, locator, page_text, excerpt = page_fixture()
        doc = replace(
            doc, final_url="https://ntrs.nasa.gov/file.pdf", rights_status="CLEARED"
        )
        resolution = resolve_exact_source_locator(
            locator,
            passage=page,
            capture=doc,
            source_body=pdf,
            page_text=page_text,
            quote_text=excerpt,
        )
        for observed in (None, "0" * 64, "unknown", doc.content_sha256.upper()):
            with self.subTest(observed=observed):
                jump = private_written_source_jump(
                    locator=locator,
                    resolution=resolution,
                    capture=doc,
                    observed_live_sha256=observed,
                    quote_text=excerpt,
                )
                self.assertEqual(jump.status, "UNAVAILABLE")
                self.assertIsNone(jump.url)
                self.assertEqual(jump.reason, "LIVE_SOURCE_VERSION_UNCONFIRMED")
        stale = replace(resolution, status="STALE")
        self.assertEqual(
            private_written_source_jump(
                locator=locator,
                resolution=stale,
                capture=doc,
                observed_live_sha256=doc.content_sha256,
                quote_text=excerpt,
            ).reason,
            "EXACT_LOCATOR_NOT_VERIFIED",
        )

    def test_observation_url_and_approved_root_must_match_original(self):
        doc = replace(
            capture(), final_url="https://www.senato.it/speech",
            rights_status="CLEARED",
        )
        valid = written(capture=doc)
        common = dict(
            locator=written_locator(), resolution=valid, capture=doc,
            observed_live_sha256=doc.content_sha256, quote_text=QUOTE,
        )
        different_address = private_written_source_jump(
            **common, observed_live_url="https://archive.example/speech",
        )
        self.assertEqual(different_address.status, "UNAVAILABLE")
        self.assertEqual(different_address.reason, "LIVE_SOURCE_URL_MISMATCH")
        copy_chain = OriginalSourceResolution(
            content_id=doc.content_id, status="RESOLVED",
            root_content_id="content:other-original",
            path_content_ids=(doc.content_id, "content:other-original"),
            path_edge_ids=("edge:approved",),
        )
        unverified_root = private_written_source_jump(
            **common, original_source=copy_chain,
        )
        self.assertEqual(unverified_root.status, "UNAVAILABLE")
        self.assertEqual(unverified_root.reason, "REVIEWED_ORIGINAL_SOURCE_NOT_VERIFIED")
        self.assertEqual(
            private_written_source_jump(**common, original_source=None).reason,
            "REVIEWED_ORIGINAL_SOURCE_NOT_VERIFIED",
        )

    def test_refuses_authenticated_private_and_potentially_secret_urls(self):
        doc = replace(capture(), rights_status="CLEARED")
        resolution = written()
        unsafe = (
            "https://private.example/fetch?token=secret",
            "https://name:password@www.senato.it/speech",
            "https://127.0.0.1/speech",
            "http://www.senato.it/speech",
            "https://localhost.local/speech",
            "https://www.senato.it/speech#secret",
            "https://www.senato.it:8443/speech",
            "javascript:alert(1)",
        )
        for url in unsafe:
            with self.subTest(url=url):
                result = private_written_source_jump(
                    locator=written_locator(),
                    resolution=resolution,
                    capture=replace(doc, final_url=url),
                    observed_live_sha256=doc.content_sha256,
                    quote_text=QUOTE,
                )
                self.assertEqual(result.status, "UNAVAILABLE")
                self.assertIsNone(result.url)

    def test_held_capture_and_unverified_quote_cannot_be_opened(self):
        doc = replace(
            capture(), rights_status="CLEARED", final_url="https://www.senato.it/speech"
        )
        valid = written(capture=doc)
        for modified in (
            replace(doc, hold_status="RIGHTS_HOLD"),
            replace(doc, status="QUARANTINED"),
        ):
            with self.subTest(status=modified.status, hold=modified.hold_status):
                result = private_written_source_jump(
                    locator=written_locator(),
                    resolution=valid,
                    capture=modified,
                    observed_live_sha256=doc.content_sha256,
                    quote_text=QUOTE,
                )
                self.assertEqual(result.status, "UNAVAILABLE")
                self.assertIsNone(result.url)

        tampered = replace(written_locator(), quote_sha256="f" * 64)
        bad_quote = private_written_source_jump(
            locator=tampered,
            resolution=valid,
            capture=doc,
            observed_live_sha256=doc.content_sha256,
            quote_text=QUOTE,
        )
        self.assertEqual(bad_quote.reason, "EXACT_LOCATOR_NOT_VERIFIED")
        wrong_quote = private_written_source_jump(
            locator=written_locator(),
            resolution=valid,
            capture=doc,
            observed_live_sha256=doc.content_sha256,
            quote_text="testo inventato",
        )
        self.assertEqual(wrong_quote.reason, "TEXT_FRAGMENT_UNSUPPORTED")
        rights_denied = private_written_source_jump(
            locator=written_locator(),
            resolution=valid,
            capture=replace(doc, rights_status="DENIED"),
            observed_live_sha256=doc.content_sha256,
            quote_text=QUOTE,
        )
        self.assertEqual(rights_denied.reason, "CAPTURE_NOT_AVAILABLE")


if __name__ == "__main__":
    unittest.main()

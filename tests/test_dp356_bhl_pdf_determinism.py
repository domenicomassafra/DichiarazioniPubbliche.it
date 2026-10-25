"""A stable authentic-scan derivative must not change Capture identity over time."""

import io
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

try:
    from PIL import Image
except ImportError:  # Pillow is optional outside document-pdf-test deployments.
    Image = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from dp356_bhl_private_gold import render_image_only_pdf, sha


@unittest.skipUnless(Image is not None, "optional Pillow document-pdf-test profile unavailable")
class StableImageDerivativeTests(unittest.TestCase):
    def test_same_source_image_has_same_pdf_identity_across_creation_times(self):
        image = Image.new("RGB", (8, 8), (23, 56, 97))
        webp = io.BytesIO()
        image.save(webp, "WEBP")
        first_time, next_day = time.gmtime(0), time.gmtime(86400)
        with patch("PIL.PdfImagePlugin.time.gmtime", return_value=first_time):
            first = render_image_only_pdf(webp.getvalue())
        with patch("PIL.PdfImagePlugin.time.gmtime", return_value=next_day):
            second = render_image_only_pdf(webp.getvalue())
        self.assertEqual(sha(first), sha(second))


if __name__ == "__main__":
    unittest.main()

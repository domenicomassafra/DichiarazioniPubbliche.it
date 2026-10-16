"""Public Camera attribution and exact private readback, including mismatch holds."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_t4_p02_owner_acceptance import (  # noqa: E402
    CAMERA_URL, LEAD_ID, EXCERPT_FIRST, EXCERPT_LAST, verify_source,
)


class OwnerAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.inventory = [{"id": LEAD_ID, "url": CAMERA_URL,
                           "speaker_label_from_official_record": "Vittoria Baldino",
                           "video_session_url": "https://webtv.camera.it/evento/30272/589615"}]
        self.source = (
            '<p id="sed0607.stenografico.tit00100.sub00010.int00340" class="intervento">'
            '<a title="Vai alla scheda personale: BALDINO Vittoria">VITTORIA BALDINO</a> parla.</p>'
            '<p id="iv.289" class="interventoVirtuale">Premessa. '
            f'{EXCERPT_FIRST}, come il caso Garlasco, dicendo che '
            f'{EXCERPT_LAST} Segue.</p>'
        ).encode("utf-8")

    def test_official_source_to_held_private_candidate_has_exact_roundtrip(self):
        result = verify_source(self.source, self.inventory, observed_at="2026-10-17T00:00:00+00:00")
        self.assertEqual(result["private_candidate_status"], "HELD")
        self.assertEqual(result["speaker_as_recorded"], "Vittoria Baldino")
        self.assertEqual(result["official_speaker_id"], "camera:persona:307435")
        self.assertTrue(result["private_temp_deleted"])
        self.assertFalse(result["published"])
        self.assertGreater(result["quote_character_count"], 50)

    def test_misattribution_and_source_edit_fail_closed(self):
        for source, reason in (
            (self.source.replace(b"BALDINO Vittoria", b"ROSSI Mario"), "CAMERA_SPEAKER_CONTEXT_MISMATCH"),
            (self.source.replace(b"Garlasco", b"sostituito"), "CAMERA_QUOTE_SCOPE_MISMATCH"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                verify_source(source, self.inventory, observed_at="2026-10-17T00:00:00+00:00")

    def test_unlinked_catalog_source_cannot_be_ingested(self):
        with self.assertRaisesRegex(ValueError, "CAMERA_CATALOG_BINDING_MISMATCH"):
            verify_source(self.source, [], observed_at="2026-10-17T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()

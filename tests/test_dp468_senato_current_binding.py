"""Source and candidate version replay for Senato's exact approved quote."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dichiarazioni_pubbliche.senato_public_v3_source import SenatoPublicV3Source
from test_dp468_senato_public_v3_source import setup

class SenatoCurrentBindingTests(unittest.TestCase):
    def test_current_statement_binding_reconstructs_exact_approved_span_and_rechecks(self):
        raw, pins, _, record = setup()
        approved = {**record, "status": "APPROVED"}
        source = SenatoPublicV3Source(
            pins, read_original_bytes=lambda: raw,
            read_current_candidates=lambda: [approved],
        )
        binding = source.current_statement_binding(
            approved["statement_id"], approved["version_id"],
        )
        self.assertEqual(binding["statement_id"], approved["statement_id"])
        self.assertEqual(binding["version_id"], approved["version_id"])
        self.assertEqual(binding["content_id"], pins.content_id)
        self.assertEqual(binding["source_version"], pins.xml_sha256)
        self.assertEqual(binding["source_sha256"], pins.canonical_text_sha256)
        self.assertEqual(binding["quote_sha256"], approved["quote_sha256"])
        self.assertEqual(binding["person_id"], approved["person_id"])
        self.assertEqual(binding["speaker_name"], approved["speaker_name"])
        self.assertEqual(binding["span_start"], approved["start_char"])
        self.assertEqual(binding["span_end"], approved["end_char"])
        self.assertEqual(binding["source_url"], pins.source_raw_url)
        self.assertTrue(binding["source_title"].startswith("Resoconto stenografico Senato "))
        self.assertRegex(binding["statement_date"], r"^\d{4}-\d{2}-\d{2}$")

        for change in (
            {"quote_sha256": "0" * 64},
            {"start_char": approved["start_char"] + 1},
            {"source_version": "f" * 64},
            {"status": "HELD"},
        ):
            with self.subTest(change=change):
                changed = SenatoPublicV3Source(
                    pins, read_original_bytes=lambda: raw,
                    read_current_candidates=lambda: [{**approved, **change}],
                )
                self.assertIsNone(changed.current_statement_binding(
                    approved["statement_id"], approved["version_id"],
                ))

        swapped = SenatoPublicV3Source(
            pins, read_original_bytes=lambda: raw,
            read_current_candidates=Mock(side_effect=[
                [approved], [{**approved, "speaker_name": "changed"}],
            ]),
        )
        self.assertIsNone(swapped.current_statement_binding(
            approved["statement_id"], approved["version_id"],
        ))


if __name__ == "__main__":
    unittest.main()

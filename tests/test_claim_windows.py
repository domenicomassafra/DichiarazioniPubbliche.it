import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_windows import (  # noqa: E402
    CanonicalSegmentInput,
    build_claim_windows,
)


def segment(
    index: int,
    start_ms: int,
    end_ms: int,
    text: str,
    *,
    blocked: bool = False,
    signature=(),
):
    return CanonicalSegmentInput(
        segment_id=f"segment:{index}",
        segment_index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        transcript_status="TRANSCRIPT_UNCERTAIN" if blocked else "RESOLVED",
        publication_blocked=blocked,
        sensitive_signature=tuple(signature),
    )


class ClaimWindowsTests(unittest.TestCase):
    def test_windows_are_bounded_and_keep_segment_mapping(self):
        rows = [
            segment(0, 0, 10_000, "Prima frase."),
            segment(1, 10_000, 20_000, "Seconda frase."),
            segment(2, 50_000, 60_000, "Dopo una pausa lunga."),
        ]
        windows = build_claim_windows(rows, max_window_seconds=45, max_gap_seconds=15)
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].segment_ids, ("segment:0", "segment:1"))
        self.assertIn("[seg=0 ", windows[0].text)
        self.assertEqual(windows[1].segment_ids, ("segment:2",))

    def test_sensitive_declarative_window_is_high_priority_but_only_marks_presence(self):
        windows = build_claim_windows(
            [
                segment(
                    0,
                    0,
                    2_000,
                    "Il valore è 10 milioni.",
                    blocked=True,
                    signature=("NUMBER:10 milioni",),
                )
            ]
        )
        self.assertEqual(windows[0].priority, "HIGH")
        self.assertTrue(windows[0].contains_publication_blocked_segments)
        self.assertEqual(windows[0].publication_blocked_segment_count, 1)
        self.assertEqual(windows[0].sensitive_categories, ("NUMBER",))

    def test_hash_changes_when_segment_text_changes(self):
        left = build_claim_windows([segment(0, 0, 1000, "Versione A")])[0]
        right = build_claim_windows([segment(0, 0, 1000, "Versione B")])[0]
        self.assertNotEqual(left.input_sha256, right.input_sha256)

    def test_queue_payload_does_not_duplicate_transcript_text(self):
        window = build_claim_windows([segment(0, 0, 1000, "Testo privato")])[0]
        payload = window.queue_payload(
            source_id="source",
            variant_id="variant",
            model="model",
            prompt_version="v1",
        )
        self.assertNotIn("text", payload)
        self.assertIn("segment_ids", payload)
        self.assertIn("input_sha256", payload)


if __name__ == "__main__":
    unittest.main()

"""#166 regression: current-rights checks also need post-inference input integrity."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche import diarization_candidate_adapter as adapter
from tests.test_diarization_candidate_adapter import CandidateAdapterTests


class PostInferenceIntegrityTests(unittest.TestCase):
    def test_mutated_or_disappeared_inputs_never_return_turns_with_stale_hashes(self):
        # Only synthetic media/model files change after the original preflight.
        for input_kind in ("audio_changed", "model_changed", "audio_removed", "model_removed", "audio_link", "model_link"):
            with self.subTest(input_kind=input_kind):
                fixture = CandidateAdapterTests(
                    "test_preflight_no_go_missing_decision_terms_rights_never_invokes_model"
                )
                fixture.setUp()
                try:
                    def changed_during_inference(*args, **kwargs):
                        if input_kind == "audio_changed":
                            fixture.audio.write_bytes(b"different recording")
                        elif input_kind == "model_changed":
                            (fixture.model_dir / "weights.example").write_bytes(b"different weights")
                        elif input_kind == "audio_removed":
                            fixture.audio.unlink()
                        elif input_kind == "model_removed":
                            (fixture.model_dir / "weights.example").unlink()
                        elif input_kind == "audio_link":
                            other = fixture.audio.with_name("synthetic-other.wav")
                            other.write_bytes(fixture.audio.read_bytes())
                            fixture.audio.unlink()
                            fixture.audio.symlink_to(other)
                        else:
                            weight = fixture.model_dir / "weights.example"
                            other = fixture.audio.with_name("synthetic-other-weight")
                            other.write_bytes(weight.read_bytes())
                            weight.unlink()
                            weight.symlink_to(other)
                        return fixture.reference, (), 10, 4096

                    with patch.object(adapter, "execute_candidate", side_effect=changed_during_inference):
                        receipt = fixture.call()
                    self.assertNotEqual(receipt.status, "CURRENT_HELD")
                    self.assertEqual(receipt.turns, ())
                    self.assertIsNone(receipt.normalized_sha256)
                    self.assertFalse(receipt.public_quote_eligible)
                finally:
                    fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()

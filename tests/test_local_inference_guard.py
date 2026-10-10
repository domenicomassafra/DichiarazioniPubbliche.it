import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

import dichiarazioni_pubbliche.local_claim_ollama as ollama  # noqa: E402
import dichiarazioni_pubbliche.local_inference_guard as guard  # noqa: E402


class LocalInferenceGuardTests(unittest.TestCase):
    def test_exclusive_cross_process_slot_is_nonblocking_and_reusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(guard, "LOCK_PATH", Path(tmp) / "state" / "cpu.lock"):
                with guard.local_inference_slot():
                    with self.assertRaisesRegex(guard.LocalInferenceBusy, "LOCAL_INFERENCE_BUSY"):
                        with guard.local_inference_slot():
                            self.fail("second CPU job must never run")
                with guard.local_inference_slot():
                    pass

    def test_busy_slot_refuses_ollama_before_any_model_or_transcript_request(self):
        client = ollama.LocalOllamaClaimClient(expected_model_digest="a" * 64)
        source = "[seg=0 0:00.000-0:01.000] Il prezzo è 10 euro."
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(guard, "LOCK_PATH", Path(tmp) / "cpu.lock"):
                with guard.local_inference_slot(), patch.object(ollama, "_request") as request:
                    with self.assertRaisesRegex(guard.LocalInferenceBusy, "LOCAL_INFERENCE_BUSY"):
                        client.extract(window_text=source, allowed_segment_indices=(0,))
                    request.assert_not_called()


if __name__ == "__main__":
    unittest.main()

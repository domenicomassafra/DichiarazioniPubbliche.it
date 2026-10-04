import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.asr_router import ProviderState, plan_asr


class AsrRouterTests(unittest.TestCase):
    def test_normal_content_uses_proven_remote_primary_only(self):
        plan = plan_asr(duration_seconds=600, risk_class="NORMAL")
        self.assertEqual(plan.primary.provider_id, "groq-whisper-large-v3-turbo")
        self.assertIsNone(plan.secondary)
        self.assertFalse(plan.publication_requires_agreement)

    def test_sensitive_span_uses_independent_second_opinion(self):
        plan = plan_asr(duration_seconds=30, risk_class="SENSITIVE")
        self.assertEqual(plan.primary.provider_id, "groq-whisper-large-v3-turbo")
        self.assertIsNotNone(plan.secondary)
        self.assertNotEqual(plan.primary.provider_id, plan.secondary.provider_id)
        self.assertTrue(plan.publication_requires_agreement)

    def test_quota_exhaustion_falls_back_to_local_proven_model(self):
        states = {
            "groq-whisper-large-v3-turbo": ProviderState(
                "groq-whisper-large-v3-turbo",
                quota_audio_seconds_remaining=0,
            )
        }
        plan = plan_asr(
            duration_seconds=60,
            risk_class="NORMAL",
            states=states,
        )
        self.assertEqual(plan.primary.provider_id, "faster-whisper-small-local")

    def test_unproven_large_local_model_is_not_selected(self):
        states = {
            "groq-whisper-large-v3-turbo": ProviderState(
                "groq-whisper-large-v3-turbo",
                healthy=False,
            ),
            "faster-whisper-small-local": ProviderState(
                "faster-whisper-small-local",
                healthy=False,
            ),
        }
        with self.assertRaisesRegex(RuntimeError, "NO_ELIGIBLE_PRIMARY_ASR"):
            plan_asr(duration_seconds=30, states=states)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.asr_router import ProviderState, plan_asr
from dichiarazioni_pubbliche.queue_runtime import ContentRecord
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers
from dichiarazioni_pubbliche.worker_errors import BlockedJob


class AsrRouterTests(unittest.TestCase):
    def test_generic_url_dispatch_never_admits_private_local_routes(self):
        class Handler(TranscriptAsrJobHandlers):
            def _require_current_ingestion_relevance(self, content):
                pass

        handler = Handler()
        handler.store = Mock()
        content = ContentRecord("content:test", "source:test", "https://example.test/audio",
                                "audio", "2026-10-20", 1000, "DISCOVERED", {})
        with patch("dichiarazioni_pubbliche.worker_handlers_transcript.plan_asr",
                   side_effect=RuntimeError("NO_ELIGIBLE_PRIMARY_ASR")) as route:
            with self.assertRaises(BlockedJob):
                handler._enqueue_asr(content, reason="CAPTION_MISSING")
            states = route.call_args.kwargs["states"]
            self.assertFalse(states["faster-whisper-small-local"].enabled)
            self.assertFalse(states["whisper-cpp-local"].enabled)
            handler.store.enqueue_followup.assert_not_called()

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

    def test_quota_exhaustion_does_not_enqueue_unverified_private_local_audio(self):
        states = {
            "groq-whisper-large-v3-turbo": ProviderState(
                "groq-whisper-large-v3-turbo",
                quota_audio_seconds_remaining=0,
            )
        }
        with self.assertRaisesRegex(RuntimeError, "NO_ELIGIBLE_PRIMARY_ASR"):
            plan_asr(duration_seconds=60, risk_class="NORMAL", states=states)

    def test_proven_small_stays_manual_even_when_enabled_in_router_state(self):
        states = {
            "groq-whisper-large-v3-turbo": ProviderState(
                "groq-whisper-large-v3-turbo", healthy=False,
            ),
            "faster-whisper-small-local": ProviderState(
                "faster-whisper-small-local", enabled=True,
            ),
        }
        with self.assertRaisesRegex(RuntimeError, "NO_ELIGIBLE_PRIMARY_ASR"):
            plan_asr(duration_seconds=10, states=states)

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

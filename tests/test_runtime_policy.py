import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class RuntimePolicyTests(unittest.TestCase):
    def test_runtime_loaders_prefer_v1_configs(self):
        from dichiarazioni_pubbliche import asr_router, source_watcher

        self.assertEqual(
            source_watcher.load_registry(),
            json.loads((ROOT / "config" / "source-registry.v1.json").read_text()),
        )
        self.assertEqual(
            asr_router.load_policy(),
            json.loads((ROOT / "config" / "transcription-policy.v1.json").read_text()),
        )

    def test_runtime_loaders_require_v1_when_default_primary_is_absent(self):
        from dichiarazioni_pubbliche import asr_router, source_watcher

        self.assertFalse(hasattr(source_watcher, "FALLBACK_REGISTRY"))
        self.assertFalse(hasattr(asr_router, "FALLBACK_POLICY"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(
                source_watcher,
                "PRIMARY_REGISTRY",
                root / "source-registry.v1.json",
            ):
                with self.assertRaises(FileNotFoundError):
                    source_watcher.load_registry()
            with patch.object(
                asr_router,
                "PRIMARY_POLICY",
                root / "transcription-policy.v1.json",
            ):
                with self.assertRaises(FileNotFoundError):
                    asr_router.load_policy()
        self.assertEqual(
            asr_router.load_policy()["name"],
            "transcription-policy-v1",
        )

    def test_transcription_policy_never_persists_downloaded_video(self):
        policy = json.loads(
            (ROOT / "config" / "transcription-policy.v1.json").read_text()
        )
        retention = policy["retention"]
        self.assertFalse(retention["persist_downloaded_video"])
        self.assertFalse(retention["persist_extracted_audio"])
        self.assertTrue(retention["persist_full_canonical_transcript"])
        self.assertTrue(retention["delete_media_after_successful_persistence"])

    def test_transcription_policy_holds_unresolved_sensitive_disagreement(self):
        policy = json.loads(
            (ROOT / "config" / "transcription-policy.v1.json").read_text()
        )
        self.assertTrue(
            policy["reconciliation"]["agreement_required_for_sensitive_tokens"]
        )
        self.assertEqual(
            policy["reconciliation"]["unresolved_publication_action"],
            "POLICY_HOLD",
        )

    def test_pulp_is_registered_as_caption_first_source(self):
        registry = json.loads(
            (ROOT / "config" / "source-registry.v1.json").read_text()
        )
        pulp = next(
            source
            for source in registry["sources"]
            if source["id"] == "youtube-pulp-podcast"
        )
        self.assertEqual(pulp["channel_id"], "UCY99TnBJ8xyat2lpeN_hcEA")
        self.assertTrue(pulp["content_policy"]["manual_captions_first"])
        self.assertTrue(
            pulp["content_policy"][
                "download_media_only_if_transcript_missing_or_low_confidence"
            ]
        )
        self.assertTrue(pulp["content_policy"]["full_video_is_ephemeral"])


if __name__ == "__main__":
    unittest.main()

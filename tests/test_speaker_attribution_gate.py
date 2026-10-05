import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


class CaptureStore(QueueRuntimeStore):
    def __init__(self):
        self.sql = ""

    def run(self, sql, **variables):
        self.sql = sql
        return "false"


class SpeakerAttributionGateTests(unittest.TestCase):
    def test_candidate_approval_allows_only_strong_attribution_methods(self):
        store = CaptureStore()
        self.assertFalse(
            store.approve_speaker_identity_with_review(
                candidate_id="speaker:1",
                event_id="review:1",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("c.attribution_method IN", store.sql)
        self.assertIn("'MANUAL_REVIEW'", store.sql)
        self.assertIn("'TRANSCRIPT_LABEL'", store.sql)
        self.assertIn("'OFFICIAL_RECORD'", store.sql)
        self.assertNotIn("c.attribution_method IN ('SOURCE_METADATA'", store.sql)
        self.assertNotIn("c.attribution_method IN ('PLATFORM_CREDIT'", store.sql)

    def test_finding_publication_requires_strong_speaker_proof_covering_segment(self):
        store = CaptureStore()
        self.assertFalse(
            store.publish_finding_with_review(
                finding_id="finding:1",
                event_id="review:1",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("speaker.attribution_method IN", store.sql)
        self.assertIn("speaker.person_id =", store.sql)
        self.assertIn("claim.speaker_person_id", store.sql)
        self.assertIn("segment.start_ms >=", store.sql)
        self.assertIn("speaker.start_ms", store.sql)
        self.assertIn("segment.end_ms <= speaker.end_ms", store.sql)
        self.assertIn("'SPEAKER_IDENTITY_CANDIDATE'", store.sql)


if __name__ == "__main__":
    unittest.main()

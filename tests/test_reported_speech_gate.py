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


class ReportedSpeechGateTests(unittest.TestCase):
    def test_finding_publication_refuses_non_direct_atomic_claim_metadata(self):
        store = CaptureStore()
        self.assertFalse(
            store.publish_finding_with_review(
                finding_id="finding:reported",
                event_id="review:reported",
                actor_ref="reviewer",
                reason="checked",
            )
        )
        self.assertIn("claim.metadata->>'speech_mode'", store.sql)
        self.assertIn("'DIRECT_UTTERANCE'", store.sql)
        self.assertIn("claim.metadata#>>'{context_integrity,state}'", store.sql)


if __name__ == "__main__":
    unittest.main()

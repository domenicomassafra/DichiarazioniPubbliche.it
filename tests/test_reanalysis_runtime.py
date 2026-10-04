import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.reanalysis_runtime import (  # noqa: E402
    deterministic_reanalysis_job_id,
    deterministic_reanalysis_trigger,
)


class ReanalysisRuntimeTests(unittest.TestCase):
    def test_same_event_is_idempotent_but_new_hash_retriggers(self):
        left = deterministic_reanalysis_trigger(
            claim_id="claim:a",
            trigger_type="EVIDENCE_HASH_CHANGED",
            source_type="evidence",
            source_id="https://example.test/a",
            source_hash="a" * 64,
        )
        same = deterministic_reanalysis_trigger(
            claim_id="claim:a",
            trigger_type="EVIDENCE_HASH_CHANGED",
            source_type="evidence",
            source_id="https://example.test/a",
            source_hash="a" * 64,
        )
        changed = deterministic_reanalysis_trigger(
            claim_id="claim:a",
            trigger_type="EVIDENCE_HASH_CHANGED",
            source_type="evidence",
            source_id="https://example.test/a",
            source_hash="b" * 64,
        )
        self.assertEqual(left.trigger_id, same.trigger_id)
        self.assertNotEqual(left.trigger_id, changed.trigger_id)
        self.assertEqual(
            deterministic_reanalysis_job_id(left.trigger_id),
            deterministic_reanalysis_job_id(same.trigger_id),
        )

    def test_unknown_trigger_type_is_refused(self):
        with self.assertRaisesRegex(ValueError, "TYPE_INVALID"):
            deterministic_reanalysis_trigger(
                claim_id="claim:a",
                trigger_type="DO_RANDOM_THING",
                source_type="x",
                source_id="y",
            )


if __name__ == "__main__":
    unittest.main()

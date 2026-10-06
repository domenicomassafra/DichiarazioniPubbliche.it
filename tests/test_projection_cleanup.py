from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.challenge_persistence import (  # noqa: E402
    ChallengeHoldDisposition,
    ChallengeHoldResult,
)
from dichiarazioni_pubbliche.correction_propagation import CorrectionPropagationReceipt  # noqa: E402
from dichiarazioni_pubbliche.projection_cleanup import (  # noqa: E402
    ProjectionArtifact,
    cleanup_dp431_stale_artifacts,
    cleanup_takedown_current_artifacts,
)


class ProjectionCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="dp303-cleanup-")
        self.root = Path(self.tmp.name)
        (self.root / "claims").mkdir()
        (self.root / "history").mkdir()
        (self.root / "private").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _file(self, relative: str, text: str = "x") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_authoritative_takedown_hold_removes_only_current_projection_owned_files(self):
        current = self._file("claims/current.json")
        historical = self._file("history/finding-v1.json")
        private = self._file("private/operator-note.txt", "PRIVATE_SENTINEL")
        artifacts = [
            ProjectionArtifact("route:current:finding:f1", "claims/current.json", "finding", "f1", "CURRENT", True),
            ProjectionArtifact("route:historical:finding:f1", "history/finding-v1.json", "finding", "f1", "HISTORICAL", True),
            ProjectionArtifact("private:f1", "private/operator-note.txt", "finding", "f1", "CURRENT", False),
        ]
        hold = ChallengeHoldResult(ChallengeHoldDisposition.HOLD, "f1", "v1", request_id="r1", event_id="e1")
        receipt = cleanup_takedown_current_artifacts(self.root, finding_id="f1", hold=hold, artifacts=artifacts)
        self.assertFalse(current.exists())
        self.assertTrue(historical.exists())
        self.assertTrue(private.exists())
        self.assertTrue(receipt.complete)

    def test_non_authoritative_hold_cannot_delete(self):
        current = self._file("claims/current.json")
        clear = ChallengeHoldResult(ChallengeHoldDisposition.CLEAR, "f1", "v1")
        receipt = cleanup_takedown_current_artifacts(
            self.root, finding_id="f1", hold=clear,
            artifacts=[ProjectionArtifact("a", "claims/current.json", "finding", "f1", "CURRENT")],
        )
        self.assertTrue(current.exists())
        self.assertEqual(receipt.blockers, ("TAKEDOWN_HOLD_NOT_AUTHORITATIVE",))

    def test_dp431_cleanup_deletes_only_mapped_projection_owned_stale_or_orphan_artifacts(self):
        stale = self._file("public/stale.html")
        orphan = self._file("public/orphan.json")
        private = self._file("private/keep.txt")
        receipt = CorrectionPropagationReceipt(
            status="HOLD", old_projection_fingerprint="1" * 64, new_projection_fingerprint="2" * 64,
            observed_projection_fingerprints=("2" * 64,), affected_finding_ids=("f1",),
            affected_content_ids=(), affected_person_ids=(), affected_topic_ids=(),
            current_finding_ids=(), historical_finding_ids=("f1",),
            stale_artifacts=("route:stale",), orphan_artifacts=("route:orphan",),
            missing_artifacts=(), blockers=("ROUTE_STATIC_STALE_ENTITY",), receipt_sha256="3" * 64,
        )
        result = cleanup_dp431_stale_artifacts(
            self.root, receipt=receipt,
            artifact_map={
                "route:stale": ProjectionArtifact("route:stale", "public/stale.html", "finding", "f1", "CURRENT", True),
                "route:orphan": ProjectionArtifact("route:orphan", "public/orphan.json", "finding", "f1", "CURRENT", True),
                "private": ProjectionArtifact("private", "private/keep.txt", "finding", "f1", "CURRENT", False),
            },
        )
        self.assertTrue(result.complete)
        self.assertFalse(stale.exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(private.exists())

    def test_path_traversal_is_fail_closed(self):
        hold = ChallengeHoldResult(ChallengeHoldDisposition.HOLD, "f1", "v1", request_id="r", event_id="e")
        result = cleanup_takedown_current_artifacts(
            self.root, finding_id="f1", hold=hold,
            artifacts=[ProjectionArtifact("escape", "../outside", "finding", "f1", "CURRENT", True)],
        )
        self.assertIn("PROJECTION_CLEANUP_PATH_INVALID", result.blockers)


if __name__ == "__main__":
    unittest.main()

"""DP-242 private handoff must refuse subclass-controlled current rights data."""

import unittest
from dataclasses import asdict

from dichiarazioni_pubbliche.studio_machine_candidate_handoff_v1 import (
    CurrentBatchStudioItem, _batch_snapshot_valid,
)


def current():
    return CurrentBatchStudioItem(
        passage_id="passage:one", content_id="content:one", capture_id="capture:one",
        source_sha256="a" * 64, passage_sha256="b" * 64,
        selector_fingerprint="selector:v1", speaker_candidate_id="person:one",
        identity_review_status="REVIEWED_SAME_PERSON", speech_role="DIRECT_SPEAKER",
        speech_act="DIRECT_ASSERTION", context_version="context:v1",
        context_review_id="review:context", rights_status="CLEARED",
        rights_evidence_sha256="c" * 64,
        source_revision=1, identity_revision=1, rights_revision=1,
    )


class CurrentSourceRightsInputBoundaryTests(unittest.TestCase):
    def test_exact_current_snapshot_is_accepted_as_private_metadata(self):
        self.assertTrue(_batch_snapshot_valid(current()))

    def test_subclass_that_can_relabel_rights_is_never_a_current_snapshot(self):
        class ChangingRightsSnapshot(CurrentBatchStudioItem):
            def __getattribute__(self, name):
                if name == "rights_status":
                    data = object.__getattribute__(self, "__dict__")
                    reads = data.setdefault("_rights_reads", 0)
                    data["_rights_reads"] = reads + 1
                    return "CLEARED" if reads == 0 else "REVOKED"
                return super().__getattribute__(name)

        untrusted = ChangingRightsSnapshot(**asdict(current()))
        self.assertFalse(_batch_snapshot_valid(untrusted))

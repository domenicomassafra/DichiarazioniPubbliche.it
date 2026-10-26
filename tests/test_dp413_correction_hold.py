"""DP #413: a pending correction removes the old public finding at intake."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.challenge_persistence import (  # noqa: E402
    PrivateChallengeLedgerStore,
    ChallengeHoldDisposition,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import ChallengeState  # noqa: E402


class CorrectionHoldTests(unittest.TestCase):
    def test_pending_correction_is_a_public_hold_until_rejected(self):
        store = PrivateChallengeLedgerStore("postgresql://fixture/unused")
        current = ChallengeState.REANALYSIS_PENDING

        def read_sql(query, **_):
            # A production ledger contains one CORRECTION; a TAKEDOWN-only
            # projection must see no rows and would incorrectly report CLEAR.
            return json.dumps(["request:correction"]) if "'CORRECTION'" in query else "[]"

        def replay(_):
            return SimpleNamespace(
                blockers=(),
                request=SimpleNamespace(
                    target_record_version="version:1",
                    request_id="request:correction",
                ),
                current_state=current,
                events=(SimpleNamespace(event_id="correction:1"),),
            )

        with (
            patch.object(store, "_current_record_version", return_value="version:1"),
            patch.object(store, "run", side_effect=read_sql),
            patch.object(store, "replay_request", side_effect=replay),
        ):
            observed = store.current_hold_for_finding("finding:corrected")
            self.assertEqual(observed.disposition, ChallengeHoldDisposition.HOLD)
            self.assertEqual(observed.event_id, "correction:1")
            current = ChallengeState.REJECTED
            self.assertEqual(
                store.current_hold_for_finding("finding:corrected").disposition,
                ChallengeHoldDisposition.CLEAR,
            )
            current = ChallengeState.PUBLIC_VERSIONED
            self.assertEqual(
                store.current_hold_for_finding("finding:corrected").disposition,
                ChallengeHoldDisposition.CLEAR,
            )

    def test_completed_correction_survives_new_record_version_but_active_one_does_not(self):
        store = PrivateChallengeLedgerStore("postgresql://fixture/unused")
        state = ChallengeState.PUBLIC_VERSIONED

        def replay(_):
            return SimpleNamespace(
                blockers=(),
                request=SimpleNamespace(target_record_version="version:1", request_id="correction:1"),
                current_state=state,
                events=(SimpleNamespace(event_id="event:1"),),
            )

        with (
            patch.object(store, "_current_record_version", return_value="version:2"),
            patch.object(store, "run", return_value=json.dumps(["correction:1"])),
            patch.object(store, "replay_request", side_effect=replay),
        ):
            self.assertEqual(store.current_hold_for_finding("finding:1").disposition,
                             ChallengeHoldDisposition.CLEAR)
            state = ChallengeState.REANALYSIS_PENDING
            self.assertEqual(store.current_hold_for_finding("finding:1").disposition,
                             ChallengeHoldDisposition.UNKNOWN)


if __name__ == "__main__":
    unittest.main()

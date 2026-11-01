"""Independent fail-closed challenge request and correction ledger tests."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dichiarazioni_pubbliche.public_statement_authority import PublicStatementChallengeStore
from dp468_authority_support import MemoryPostgres

class PublicStatementChallengeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.db = MemoryPostgres()
        self.store = PublicStatementChallengeStore(store=self.db)

    def open(self):
        return self.store.open_request(
            statement_id="statement:senato:1",
            version_id="version:senato:1",
            intake_ref="intake:public-correction:1",
            requester_ref_sha256="a" * 64,
            reason_sha256="b" * 64,
            created_at=self.now.isoformat(),
            actor_ref="intake:public",
        )

    def test_open_request_holds_until_valid_terminal_rejection(self):
        request = self.open()
        self.assertTrue(self.store.current_hold("statement:senato:1", "version:senato:1"))
        self.store.append_event(
            request_id=request, status="TRIAGED", reason_code="REVIEW_STARTED",
            actor_ref="reviewer:one", occurred_at=(self.now + timedelta(minutes=1)).isoformat(),
        )
        self.store.append_event(
            request_id=request, status="NEEDS_INFO", reason_code="NEED_SOURCE",
            actor_ref="reviewer:one", occurred_at=(self.now + timedelta(minutes=2)).isoformat(),
        )
        self.store.append_event(
            request_id=request, status="REJECTED", reason_code="CLAIM_NOT_SUBSTANTIATED",
            actor_ref="reviewer:two", occurred_at=(self.now + timedelta(minutes=3)).isoformat(),
        )
        self.assertFalse(self.store.current_hold("statement:senato:1", "version:senato:1"))
        with self.assertRaisesRegex(ValueError, "DP468_CHALLENGE_ALREADY_CLOSED"):
            self.store.append_event(
                request_id=request, status="TRIAGED", reason_code="REOPEN",
                actor_ref="reviewer:one", occurred_at=(self.now + timedelta(minutes=4)).isoformat(),
            )

    def test_correction_and_retraction_keep_the_old_version_held(self):
        request = self.open()
        self.store.append_event(
            request_id=request, status="TRIAGED", reason_code="REVIEW_STARTED",
            actor_ref="reviewer:one", occurred_at=(self.now + timedelta(minutes=1)).isoformat(),
        )
        self.store.append_event(
            request_id=request, status="CORRECTED", reason_code="NEW_VERSION_REQUIRED",
            actor_ref="reviewer:two", occurred_at=(self.now + timedelta(minutes=2)).isoformat(),
        )
        self.assertTrue(self.store.current_hold("statement:senato:1", "version:senato:1"))
        with self.assertRaisesRegex(ValueError, "DP468_CHALLENGE_ALREADY_CLOSED"):
            self.store.append_event(
                request_id=request, status="RETRACTED", reason_code="RETRACT",
                actor_ref="reviewer:two", occurred_at=(self.now + timedelta(minutes=3)).isoformat(),
            )

    def test_invalid_transition_and_tampered_chain_fail_closed(self):
        request = self.open()
        with self.assertRaisesRegex(ValueError, "DP468_CHALLENGE_TRANSITION_INVALID"):
            self.store.append_event(
                request_id=request, status="CORRECTED", reason_code="INVALID",
                actor_ref="reviewer:one", occurred_at=(self.now + timedelta(minutes=1)).isoformat(),
            )
        self.db.challenge_events[0]["reason_code"] = "TAMPERED"
        self.assertIsNone(self.store.current_hold("statement:senato:1", "version:senato:1"))



if __name__ == "__main__":
    unittest.main()

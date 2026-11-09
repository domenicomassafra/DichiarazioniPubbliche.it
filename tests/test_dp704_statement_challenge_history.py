"""#704 review: historical challenge growth must not fail closed forever."""

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.public_statement_authority import PublicStatementChallengeStore  # noqa: E402
from dichiarazioni_pubbliche.statement_correction_intake import StatementCorrectionIntake  # noqa: E402
from dp468_authority_support import MemoryPostgres  # noqa: E402


def open_challenge(store, db, index, *, statement_id, version_id, created_at):
    requester = "d" * 63 + format(index % 16, "x")
    request_id = store.open_request(
        statement_id=statement_id, version_id=version_id,
        intake_ref="intake:historical:" + str(index),
        requester_ref_sha256=requester, reason_sha256="e" * 64,
        created_at=created_at, actor_ref="oidc:" + requester,
    )
    return request_id, db


class PublicStatementChallengeHistoryTests(unittest.TestCase):
    def ledger(self):
        db = MemoryPostgres()
        return db, PublicStatementChallengeStore(store=db)

    def test_cleared_history_keeps_an_unrelated_challenged_version_fenced(self):
        db, store = self.ledger()
        start = datetime.now(timezone.utc).replace(microsecond=0)
        open_challenge(store, db, 0, statement_id="statement:1",
                       version_id="statement-version:1",
                       created_at=start.isoformat())
        for index in range(1, 26):
            request_id, _ = open_challenge(
                store, db, index,
                statement_id="statement:history:%d" % index,
                version_id="statement-version:history:%d" % index,
                created_at=(start + timedelta(seconds=index)).isoformat(),
            )
            store.append_event(
                request_id=request_id, status="REJECTED", reason_code="NO_CHANGE_REQUIRED",
                actor_ref="reviewer:one",
                occurred_at=(start + timedelta(minutes=index)).isoformat(),
            )
        inventory = store.challenged_statements()
        self.assertEqual(len(inventory), 26)
        self.assertEqual(store.challenged_statements(limit=10)[0],
                         ("statement:1", "statement-version:1"))
        self.assertEqual(len(store.challenged_statements(limit=10)), 10)
        # Historical, already cleared targets are paginated, never dropped: a
        # small page size cannot turn the ledger's age into a public outage.
        history = frozenset(
            ("statement:history:%d" % index, "statement-version:history:%d" % index)
            for index in range(1, 26))
        self.assertTrue(store.public_release_clear(history, page_size=7))
        # An open challenge still fences the version it names, at any page size.
        self.assertFalse(store.public_release_clear(
            frozenset({("statement:1", "statement-version:1")}), page_size=100))
        # A corrected release that no longer serves the challenged version is
        # clear even while the challenge itself stays open.
        self.assertTrue(store.public_release_clear(
            frozenset({("statement:1", "statement-version:1-corrected")}), page_size=100))

    def test_a_second_cleared_challenge_requires_a_newer_release(self):
        db, store = self.ledger()
        start = datetime.now(timezone.utc).replace(microsecond=0)
        target = ("statement:repeat", "statement-version:repeat")
        for index, opened_at in enumerate((start, start + timedelta(minutes=2))):
            request_id, _ = open_challenge(
                store, db, index, statement_id=target[0], version_id=target[1],
                created_at=opened_at.isoformat(),
            )
            store.append_event(
                request_id=request_id, status="REJECTED", reason_code="NO_CHANGE_REQUIRED",
                actor_ref="reviewer:one",
                occurred_at=(opened_at + timedelta(seconds=10)).isoformat(),
            )
        self.assertFalse(store.current_hold(*target))
        intake = StatementCorrectionIntake("projection.json", "fingerprint", store)
        first_release = (start + timedelta(minutes=1)).isoformat()
        self.assertFalse(store.public_release_clear(
            frozenset({target}), may_serve_cleared=intake._served_after_challenge(first_release)))
        new_release = (start + timedelta(minutes=3)).isoformat()
        self.assertTrue(store.public_release_clear(
            frozenset({target}), may_serve_cleared=intake._served_after_challenge(new_release)))


if __name__ == "__main__":
    unittest.main()

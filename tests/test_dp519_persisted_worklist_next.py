"""DP-519 real local SQLite restart/CAS worklist, never editorial authority."""
from __future__ import annotations

import tempfile
import os
import sqlite3
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.test_dp519_visual_operator_capacity import NOW, digest, event, exception, work
from dichiarazioni_pubbliche.studio_visual_worklist import SQLiteVisualWorklist


class DurableVisualWorklistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp519-private-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "visual.sqlite"
        self.one = SQLiteVisualWorklist(self.path)
        self.two = SQLiteVisualWorklist(self.path)
        self.item = work("a")

    def test_persisted_snapshot_event_replay_restart_and_report(self):
        first = self.one.upsert_item(self.item, expected_revision=0)
        self.assertEqual(first["revision"], 1)
        self.assertFalse(first["publication_authority"])
        self.assertEqual(self.two.upsert_item(self.item, expected_revision=1)["revision"], 1)
        decision = event(self.item, eid="durable", minutes=7)
        receipt = self.two.append_reported_event(decision, expected_work_revision=1)
        self.assertEqual(receipt["state"], "RECORDED_UNVERIFIED_OPERATOR_TIME")
        self.assertFalse(receipt["text_review_authority"])
        self.assertEqual(self.one.append_reported_event(decision, expected_work_revision=1), receipt)
        report = SQLiteVisualWorklist(self.path).private_report(now=NOW)
        self.assertEqual(report.ledger_event_count, 1)
        self.assertEqual(report.actual_minutes_this_week, 7)
        self.assertEqual(report.rows[0].state, "NO_IMAGE_SELECTED")
        self.assertFalse(report.image_approval_authority)
        self.assertEqual(self.one.event_count(), 1)

    def test_stale_source_version_cas_and_forced_no_image(self):
        self.one.upsert_item(self.item, expected_revision=0)
        changed = replace(self.item, source_version_sha256=digest("new-capture"),
                          source_rights_state="REVOKED")
        self.two.upsert_item(changed, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_WORK_REVISION_CONFLICT"):
            self.one.upsert_item(self.item, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_WORK_REVISION_CONFLICT"):
            self.one.append_reported_event(event(self.item), expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_SOURCE_STALE"):
            self.one.append_reported_event(event(self.item), expected_work_revision=2)
        self.assertEqual(self.two.private_report(now=NOW).rows[0].state,
                         "HELD_RIGHTS_NO_IMAGE")
        self.assertEqual(self.two.event_count(), 0)

    def test_future_work_and_future_operator_minutes_are_rejected(self):
        future = datetime.now(timezone.utc) + timedelta(days=365)
        future_item = replace(self.item, created_at=future,
                              expires_at=future + timedelta(days=1))
        with self.assertRaisesRegex(ValueError, "DP519_FUTURE_WORK_INVALID"):
            self.one.upsert_item(future_item, expected_revision=0)
        self.assertEqual(self.one.private_report(now=NOW).rows, ())

        self.one.upsert_item(self.item, expected_revision=0)
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_TIME_INVALID"):
            self.two.append_reported_event(
                event(self.item, eid="future", completed=future),
                expected_work_revision=1,
            )
        self.assertEqual(self.two.event_count(), 0)

    def test_conflicting_event_id_and_chain_fail_closed_without_partial_write(self):
        self.one.upsert_item(self.item, expected_revision=0)
        e1 = event(self.item, eid="unique", minutes=7)
        self.one.append_reported_event(e1, expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_ID_CONFLICT"):
            self.two.append_reported_event(replace(e1, actor_id="owner:other"),
                                           expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_CHAIN_CONFLICT"):
            self.two.append_reported_event(event(self.item, eid="next", completed=NOW + timedelta(minutes=15)),
                                           expected_work_revision=1)
        self.assertEqual(self.one.event_count(), 1)

    def test_missing_work_and_revised_snapshot_idempotency(self):
        with self.assertRaisesRegex(ValueError, "DP519_WORK_REVISION_CONFLICT"):
            self.one.upsert_item(self.item, expected_revision=5)
        with self.assertRaisesRegex(ValueError, "DP519_WORK_NOT_FOUND"):
            self.two.append_reported_event(event(self.item), expected_work_revision=1)
        self.one.upsert_item(self.item, expected_revision=0)
        with self.assertRaisesRegex(ValueError, "DP519_WORK_REVISION_CONFLICT"):
            self.two.upsert_item(replace(self.item, estimated_minutes=20), expected_revision=0)
        self.assertEqual(self.one.event_count(), 0)

    def test_history_cannot_be_relabelled_to_another_person_or_reason(self):
        self.one.upsert_item(self.item, expected_revision=0)
        self.one.append_reported_event(event(self.item), expected_work_revision=1)
        # Work keys are stable identities; historical handling minutes must not
        # suddenly be attributed to another person, image task or reason.
        for replacement in (replace(self.item, person_id="person:another"),
                            replace(self.item, reason_code="IMAGE_LICENSE"),
                            replace(self.item, content_id="content:another")):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(
                ValueError, "DP519_WORK_IDENTITY_CONFLICT"
            ):
                self.two.upsert_item(replacement, expected_revision=1)
        self.assertEqual(self.one.private_report(now=NOW).median_minutes_by_reason,
                         {"IMAGE_IDENTITY": 7})

    def test_private_file_and_immutable_database_event_rows(self):
        self.assertEqual(os.stat(self.path).st_mode & 0o077, 0)
        self.one.upsert_item(self.item, expected_revision=0)
        self.one.append_reported_event(event(self.item), expected_work_revision=1)
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute("DELETE FROM visual_time_event WHERE event_id='event:e1'")
        self.assertEqual(self.two.event_count(), 1)


    def test_private_exception_budget_survives_restart_and_exact_replay(self):
        item = work("x")
        self.one.upsert_item(item, expected_revision=0)
        pending = exception("x", minutes=14)
        receipt = self.one.append_exception(pending, expected_work_revision=1)
        self.assertEqual(receipt["state"], "RECORDED_UNRESOLVED_EXCEPTION")
        self.assertFalse(receipt["text_review_authority"])
        self.assertFalse(receipt["publication_authority"])
        self.assertEqual(self.two.append_exception(pending, expected_work_revision=1), receipt)
        report = SQLiteVisualWorklist(self.path).private_report(now=NOW)
        self.assertEqual(report.exception_estimated_minutes, 14)
        self.assertEqual(len(report.exceptions), 1)
        self.assertEqual(report.exceptions[0].state, "WAIT_QUALIFIED_EXTERNAL_AUTHORITY")
        self.assertFalse(report.exceptions[0].text_review_authority)
        self.assertEqual(self.two.exception_count(), 1)

    def test_exception_conflict_duplicate_and_foreign_attempt_fail_closed(self):
        item = work("x")
        self.one.upsert_item(item, expected_revision=0)
        pending = exception("x")
        self.one.append_exception(pending, expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_ID_CONFLICT"):
            self.two.append_exception(replace(pending, estimated_minutes=3),
                                      expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_DUPLICATE_QUESTION"):
            self.two.append_exception(replace(pending, exception_id="exception:again"),
                                      expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_ATTEMPT_NOT_IN_WORK"):
            self.two.append_exception(replace(pending, exception_id="exception:forged",
                                              prior_attempt_hashes=(digest("unknown"),)),
                                      expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_WORK_REVISION_INVALID"):
            self.two.append_exception(replace(pending, exception_id="exception:stale"),
                                      expected_work_revision=0)
        self.assertEqual(self.one.exception_count(), 1)
        self.assertEqual(self.one.private_report(now=NOW).exception_estimated_minutes, 10)

    def test_exception_attempt_history_cannot_be_erased_or_sql_rewritten(self):
        item = work("x")
        self.one.upsert_item(item, expected_revision=0)
        self.one.append_exception(exception("x"), expected_work_revision=1)
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_ATTEMPT_HISTORY_CONFLICT"):
            self.two.upsert_item(replace(item, automated_attempt_hashes=()),
                                 expected_revision=1)
        revised = replace(item, source_version_sha256=digest("new-version"),
                          source_rights_state="REVOKED")
        self.assertEqual(self.two.upsert_item(revised, expected_revision=1)["revision"], 2)
        with self.assertRaisesRegex(ValueError, "DP519_WORK_REVISION_CONFLICT"):
            self.two.append_exception(replace(exception("x"), exception_id="exception:stale"),
                                      expected_work_revision=1)
        self.assertEqual(self.one.private_report(now=NOW).exception_estimated_minutes, 10)
        with sqlite3.connect(self.path) as db:
            for statement in (
                "DELETE FROM visual_exception WHERE exception_id='exception:x'",
                "UPDATE visual_exception SET document='{}' WHERE exception_id='exception:x'",
            ):
                with self.subTest(statement=statement), self.assertRaises(sqlite3.DatabaseError):
                    db.execute(statement)
        self.assertEqual(self.two.exception_count(), 1)


if __name__ == "__main__":
    unittest.main()

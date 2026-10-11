"""DP-319 real SQLite source-version receipts; never performs provider work."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.investigation_attempts_store_v1 import (  # noqa: E402
    InvestigationSourceRecord,
    InvestigationSQLiteStore,
    STORE_VERSION,
    _hash,
    _json,
)
from tests.test_dp319_investigation_attempts import (  # noqa: E402
    assignment,
    spec,
)
from dichiarazioni_pubbliche.investigation_attempts_v1 import (  # noqa: E402
    InvestigationObservation,
)


def source(
    *,
    revision=1,
    version="capture:v1",
    fingerprint="source-version-sha:a",
    rights="CLEARED",
    policy="ALLOWED",
    sha="a" * 64,
):
    return InvestigationSourceRecord(
        need_id="need:original",
        source_id="source:official:existing",
        candidate_id="candidate:existing:original",
        material_fingerprint=fingerprint,
        source_version=version,
        source_sha256=sha,
        rights_status=rights,
        policy_status=policy,
        revision=revision,
    )


def observed(reservation, *, status="NO_MATCH", spent="0.01", **changes):
    base = dict(
        attempt_id=reservation.attempt_id,
        material_fingerprint=reservation.material_fingerprint,
        assignment_id=reservation.assignment_id,
        lane=reservation.lane,
        result=status,
        lineage_id=None,
        source_version=None,
        source_sha256=None,
        review_event_id=None,
        spent_usd=Decimal(spent),
    )
    base.update(changes)
    return InvestigationObservation(**base)


class DurableInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private-investigations.sqlite"
        self.db = InvestigationSQLiteStore(self.path)
        self.source = source()
        self.s = spec()
        self.assignments = (assignment(), assignment("PRIMARY_SOURCE"))
        self.db.record_source(self.source, expected_revision=0)
        self.db.register(self.s, self.assignments, self.source)

    def test_reservation_is_durable_before_work_and_never_duplicates_after_restart(
        self,
    ):
        read = self.db.read(self.s, self.assignments, self.source)
        self.assertEqual(read.decision.status, "READY_PRIVATE_PROPOSAL")
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="cost:event:1",
            expected_revision=0,
        )
        self.assertEqual(first.revision, 1)
        self.assertEqual(first.decision.status, "WAIT_EXTERNAL")
        self.assertEqual(
            first.decision.reason_code, "INVESTIGATION_UNCONFIRMED_RESERVATION"
        )
        self.assertIsNone(first.decision.proposed_attempt_id)
        self.assertEqual(len(first.reservations), 1)
        self.assertEqual(first.observations, ())
        resumed = InvestigationSQLiteStore(self.path)
        self.assertEqual(resumed.read(self.s, self.assignments, self.source), first)
        self.assertEqual(
            resumed.reserve(
                self.s,
                self.assignments,
                self.source,
                key="cost:event:1",
                expected_revision=0,
            ),
            first,
        )
        with self.assertRaisesRegex(ValueError, "UNCONFIRMED_RESERVATION"):
            resumed.reserve(
                self.s,
                self.assignments,
                self.source,
                key="cost:event:other",
                expected_revision=first.revision,
            )
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            resumed.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0]),
                key="cost:event:1",
                expected_revision=0,
            )
        final = resumed.complete(
            self.s,
            self.assignments,
            self.source,
            observation=observed(first.reservations[0]),
            key="cost:event:1",
            expected_revision=first.revision,
        )
        self.assertEqual(final.revision, 2)
        self.assertEqual(final.decision.status, "READY_PRIVATE_PROPOSAL")
        self.assertNotEqual(
            final.decision.proposed_attempt_id, first.reservations[0].attempt_id
        )
        self.assertEqual(len(final.observations), 1)
        self.assertEqual(final.decision.spent_usd, Decimal("0.01"))
        self.assertEqual(
            resumed.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0]),
                key="cost:event:1",
                expected_revision=1,
            ),
            final,
        )
        with self.assertRaisesRegex(ValueError, "COMPLETION_REPLAY_CONFLICT"):
            resumed.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0], status="OUTAGE"),
                key="cost:event:1",
                expected_revision=final.revision,
            )

    def test_freshness_independent_source_rights_and_policy_revocation_fail_closed(
        self,
    ):
        old = self.db.read(self.s, self.assignments, self.source)
        revoked = source(revision=2, rights="REVOKED")
        self.db.record_source(revoked, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE"):
            self.db.reserve(
                self.s,
                self.assignments,
                self.source,
                key="old:source",
                expected_revision=0,
            )
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE"):
            self.db.read(self.s, self.assignments, self.source)
        with self.assertRaisesRegex(ValueError, "SPEC_RIGHTS_MISMATCH"):
            self.db.register(self.s, self.assignments, revoked)
        self.assertEqual(
            self.db.history(self.s, self.assignments).revision, old.revision
        )
        with self.assertRaisesRegex(ValueError, "SOURCE_REVISION_CONFLICT"):
            self.db.record_source(source(revision=2), expected_revision=1)

        later = source(revision=3, policy="BLOCKED")
        self.db.record_source(later, expected_revision=2)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE"):
            self.db.reserve(
                self.s,
                self.assignments,
                self.source,
                key="stale:policy",
                expected_revision=0,
            )
        with self.assertRaisesRegex(ValueError, "POLICY_BLOCKED"):
            self.db.register(self.s, self.assignments, later)

    def test_partial_failure_then_new_material_version_reopens_without_recycling_receipt(
        self,
    ):
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="v1:a",
            expected_revision=0,
        )
        after_failure = self.db.complete(
            self.s,
            self.assignments,
            self.source,
            observation=observed(first.reservations[0], status="OUTAGE", spent="0"),
            key="v1:a",
            expected_revision=first.revision,
        )
        self.assertEqual(after_failure.decision.status, "WAIT_EXTERNAL")
        newer = source(
            revision=2,
            fingerprint="source-version-sha:b",
            version="capture:v2",
            sha="b" * 64,
        )
        self.db.record_source(newer, expected_revision=1)
        new_spec = spec(material_fingerprint=newer.material_fingerprint)
        fresh = self.db.register(new_spec, self.assignments, newer)
        self.assertEqual(fresh.revision, 0)
        self.assertEqual(fresh.decision.prior_attempt_count, 0)
        self.assertNotEqual(
            fresh.decision.plan_fingerprint, after_failure.decision.plan_fingerprint
        )
        self.assertEqual(self.db.history(self.s, self.assignments), after_failure)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE"):
            self.db.reserve(
                self.s,
                self.assignments,
                self.source,
                key="v1:repeat",
                expected_revision=2,
            )
        next_start = self.db.reserve(
            new_spec,
            self.assignments,
            newer,
            key="v2:a",
            expected_revision=0,
        )
        self.assertEqual(next_start.revision, 1)

    def test_cross_source_candidate_and_foreign_assignment_are_refused_atomically(self):
        for forged in (
            replace(self.source, source_id="source:other"),
            replace(self.source, candidate_id="candidate:other"),
            replace(self.source, source_sha256="b" * 64),
            replace(self.source, source_version="capture:other"),
        ):
            with (
                self.subTest(forged=forged),
                self.assertRaisesRegex(ValueError, "SOURCE_STALE"),
            ):
                self.db.reserve(
                    self.s,
                    self.assignments,
                    forged,
                    key="foreign:test",
                    expected_revision=0,
                )
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="proper:attempt",
            expected_revision=0,
        )
        receipt = observed(first.reservations[0])
        for change in (
            {"assignment_id": "assignment:other"},
            {"lane": "CHALLENGER"},
            {"material_fingerprint": "source-version-sha:foreign"},
            {"attempt_id": "investigation-attempt:forged"},
        ):
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, "OBSERVATION_MISMATCH"),
            ):
                self.db.complete(
                    self.s,
                    self.assignments,
                    self.source,
                    observation=replace(receipt, **change),
                    key="proper:attempt",
                    expected_revision=1,
                )
        self.assertEqual(
            self.db.read(self.s, self.assignments, self.source).revision, 1
        )
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_REVIEW"):
            self.db.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(
                    first.reservations[0],
                    status="REVIEWED_SOURCE_CANDIDATE",
                    lineage_id="l:1",
                    source_version=self.source.source_version,
                    source_sha256=self.source.source_sha256,
                    review_event_id="review:fictional",
                ),
                key="proper:attempt",
                expected_revision=1,
            )

    def test_two_writers_cannot_reserve_same_attempt_or_oversubscribe_budget(self):
        barrier = Barrier(2)

        def writer(key):
            store = InvestigationSQLiteStore(self.path)
            barrier.wait(timeout=5)
            try:
                return store.reserve(
                    self.s, self.assignments, self.source, key=key, expected_revision=0
                ).revision
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(writer, "race:1")
            two = pool.submit(writer, "race:2")
            result = (one.result(timeout=10), two.result(timeout=10))
        self.assertEqual(
            sorted(map(str, result)), ["1", "INVESTIGATION_REVISION_CONFLICT"]
        )
        after = self.db.read(self.s, self.assignments, self.source)
        self.assertEqual(after.revision, 1)
        self.assertEqual(len(after.reservations), 1)
        self.assertEqual(after.observations, ())

    def test_atomic_failed_completion_keeps_pending_reservation_on_restart(self):
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="fault:attempt",
            expected_revision=0,
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute("""
                CREATE TRIGGER dp319_fail_revision BEFORE UPDATE OF revision ON dp319_scopes
                BEGIN SELECT RAISE(ABORT, 'fault-injected'); END;
            """)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "fault-injected"):
            self.db.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0]),
                key="fault:attempt",
                expected_revision=1,
            )
        resumed = InvestigationSQLiteStore(self.path).read(
            self.s, self.assignments, self.source
        )
        self.assertEqual(resumed, first)
        with sqlite3.connect(self.path) as connection:
            connection.execute("DROP TRIGGER dp319_fail_revision")
        self.assertEqual(
            self.db.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0]),
                key="fault:attempt",
                expected_revision=1,
            ).revision,
            2,
        )

    def test_restart_new_python_process_recovers_exact_plan_and_pending_reservation(
        self,
    ):
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="restart:one",
            expected_revision=0,
        )
        script = """
import json,sys
from pathlib import Path
from dichiarazioni_pubbliche.investigation_attempts_store_v1 import InvestigationSQLiteStore
db=InvestigationSQLiteStore(Path(sys.argv[1]))
snapshot=db.resume(sys.argv[2],source_revision=1)
print(json.dumps({'revision':snapshot.revision,'reservations':len(snapshot.reservations),
    'status':snapshot.decision.status,'pending':len(snapshot.observations)}))
"""
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, "PYTHONPATH": str(root / "poc") + os.pathsep + str(root)}
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(self.path),
                first.decision.plan_fingerprint,
            ],
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
            env=env,
        )
        self.assertIn('"revision": 1', result.stdout)
        self.assertIn('"status": "WAIT_EXTERNAL"', result.stdout)
        self.assertIn('"reservations": 1', result.stdout)

    def test_revocation_between_reservation_and_completion_preserves_pending_and_history(
        self,
    ):
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="pending:outage",
            expected_revision=0,
        )
        revoked = source(revision=2, rights="REVOKED")
        self.db.record_source(revoked, expected_revision=1)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE"):
            self.db.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0]),
                key="pending:outage",
                expected_revision=1,
            )
        persisted = self.db.history(self.s, self.assignments)
        self.assertEqual(persisted.revision, 1)
        self.assertEqual(
            persisted.decision.reason_code, "INVESTIGATION_UNCONFIRMED_RESERVATION"
        )
        self.assertEqual(persisted.observations, ())
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE"):
            self.db.resume(first.decision.plan_fingerprint, source_revision=1)
        # No counter, reviewed candidate, or public authority is inferred.
        self.assertFalse(persisted.publication_authority)
        self.assertFalse(persisted.dispatch_authorized)

    def test_replay_event_with_rehashed_foreign_attempt_id_is_rejected_on_read(self):
        first = self.db.reserve(
            self.s,
            self.assignments,
            self.source,
            key="tamper:attempt",
            expected_revision=0,
        )
        # Force a syntactically valid but forged receipt with a consistent SHA
        # in disposable SQLite, simulating administrative repair gone wrong.
        foreign = "investigation-attempt:" + "f" * 64
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT event_json FROM dp319_events").fetchone()
            import json

            receipt = json.loads(row[0])
            receipt["attempt_id"] = foreign
            payload = _json(receipt)
            checksum = _hash(
                {
                    "schema": STORE_VERSION,
                    "plan": first.decision.plan_fingerprint,
                    "seq": 1,
                    "kind": "RESERVED",
                    "payload": payload,
                }
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "ATTEMPT_APPEND_ONLY"):
                connection.execute("UPDATE dp319_events SET attempt_id=?", (foreign,))
            connection.execute("DROP TRIGGER dp319_event_immutable_update")
            connection.execute(
                "UPDATE dp319_events SET attempt_id=?,event_json=?,checksum=?",
                (foreign, payload, checksum),
            )
        with self.assertRaisesRegex(ValueError, "INTEGRITY_INVALID"):
            self.db.read(self.s, self.assignments, self.source)

    def test_finished_attempt_does_not_infer_sufficient_evidence_or_fake_owner(self):
        first = self.db.reserve(
            self.s, self.assignments, self.source, key="coverage:a", expected_revision=0
        )
        one = self.db.complete(
            self.s,
            self.assignments,
            self.source,
            observation=observed(first.reservations[0], status="SOURCE_INCONCLUSIVE"),
            key="coverage:a",
            expected_revision=1,
        )
        self.assertEqual(one.decision.status, "READY_PRIVATE_PROPOSAL")
        second = self.db.reserve(
            self.s, self.assignments, self.source, key="coverage:b", expected_revision=2
        )
        two = self.db.complete(
            self.s,
            self.assignments,
            self.source,
            observation=observed(second.reservations[-1], status="NO_MATCH"),
            key="coverage:b",
            expected_revision=3,
        )
        self.assertEqual(two.revision, 4)
        self.assertEqual(two.decision.status, "EXHAUSTED")
        self.assertEqual(two.decision.reason_code, "INVESTIGATION_ATTEMPT_CAP")
        self.assertEqual(two.decision.independent_reviewed_lineages, 0)
        self.assertFalse(two.decision.publication_authority)
        self.assertEqual(
            self.db.resume(two.decision.plan_fingerprint, source_revision=1), two
        )

    def test_actual_spend_is_bounded_by_assignment_cap_and_metadata_is_unreviewed(self):
        first = self.db.reserve(
            self.s, self.assignments, self.source, key="budget:one", expected_revision=0
        )
        with self.assertRaisesRegex(ValueError, "COST_CAP"):
            self.db.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(first.reservations[0], spent="0.04"),
                key="budget:one",
                expected_revision=1,
            )
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_REVIEW"):
            self.db.complete(
                self.s,
                self.assignments,
                self.source,
                observation=observed(
                    first.reservations[0], lineage_id="person:fictional"
                ),
                key="budget:one",
                expected_revision=1,
            )
        self.assertEqual(
            self.db.read(self.s, self.assignments, self.source).revision, 1
        )


if __name__ == "__main__":
    unittest.main()

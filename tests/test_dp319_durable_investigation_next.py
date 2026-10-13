"""DP-319 real SQLite source-version receipts; never performs provider work."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from unittest.mock import patch
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
from dichiarazioni_pubbliche import investigation_attempts_store_v1 as store_module  # noqa: E402
from dichiarazioni_pubbliche.investigation_attempts_v1 import (  # noqa: E402
    propose_investigation as current_propose_investigation,
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



def legacy_v1_propose_investigation(**kwargs):
    """Exact pre-PR14 planner fingerprint material, on the real SQLite writer.

    The original proposal hash did NOT include rights_status, assignment
    question/host/status/blockers/temporal/authority. Retain a self-contained
    format fixture: CI must not depend on historical Git refs being present.
    """
    scope = kwargs["spec"]
    active = sorted(
        (row for row in kwargs["assignments"] if row.coverage_need_id == scope.need_id),
        key=lambda row: row.assignment_id,
    )
    old_fp = _hash({
        "need": scope.need_id, "fingerprint": scope.material_fingerprint,
        "question": scope.question_kind, "question_text": scope.question,
        "family": scope.source_family, "max_attempts": scope.max_attempts,
        "cost_cap_usd": str(scope.cost_cap_usd),
        "assignments": [dict(
            id=row.assignment_id, lane=row.lane, plan_version=row.plan_version,
            adapters=list(row.adapter_ids), stop=list(row.stop_conditions),
            max_queries=row.max_queries, max_results=row.max_results,
            cost_cap=str(row.cost_cap_usd),
        ) for row in active],
        "version": "investigation-attempt-v1",
    })
    # A prior v1 receipt is legitimate only for the v1 proposal. Translate
    # its ID solely while driving today's decision logic in this test fixture.
    # Actual persisted IDs/events remain byte-for-byte old-v1 records.
    modern = current_propose_investigation(
        **{**kwargs, "observations": ()},
    )
    def old_attempt_for(assignment_id):
        return "investigation-attempt:" + _hash({
            "plan": old_fp, "assignment": assignment_id,
            "material": scope.material_fingerprint,
        })
    def new_attempt_for(assignment_id):
        return "investigation-attempt:" + _hash({
            "plan": modern.plan_fingerprint, "assignment": assignment_id,
            "material": scope.material_fingerprint,
        })
    normalized = []
    for record in kwargs["observations"]:
        if record.attempt_id != old_attempt_for(record.assignment_id):
            raise ValueError("INVESTIGATION_OBSERVATION_UNBOUND_ATTEMPT")
        normalized.append(replace(
            record, attempt_id=new_attempt_for(record.assignment_id),
        ))
    old = current_propose_investigation(
        **{**kwargs, "observations": tuple(normalized)},
    )
    return replace(
        old,
        plan_fingerprint=old_fp,
        proposed_attempt_id=(
            "investigation-attempt:" + _hash({
                "plan": old_fp, "assignment": old.assignment_id,
                "material": scope.material_fingerprint,
            })
            if old.proposed_attempt_id is not None else None
        ),
    )


class LegacyFingerprintUpgradeTests(unittest.TestCase):
    """Real committed old-v1 SQLite rows, then current planner on same file."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private-investigations.sqlite"
        self.db = InvestigationSQLiteStore(self.path)
        self.s = spec()
        self.assignments = (assignment(), assignment("PRIMARY_SOURCE"))
        self.source = source()
        self.db.record_source(self.source, expected_revision=0)

    def persist_old(self, *, completed=False):
        with patch.object(
            store_module, "propose_investigation",
            side_effect=legacy_v1_propose_investigation,
        ):
            self.db.register(self.s, self.assignments, self.source)
            old = self.db.reserve(
                self.s, self.assignments, self.source,
                key="old:cost-bearing:one", expected_revision=0,
            )
            self.assertEqual(
                old.decision.plan_fingerprint,
                "c09add7844bdf58a703745e58abcfb5c13b9d284ed236fc038f5c7823a1adcf1",
            )
            self.assertEqual(
                old.reservations[0].attempt_id,
                "investigation-attempt:8c07e2c411852c7c2492c9789e00a9cbfae99760bce1bbb4ae5e6ec99ee93f39",
            )
            if completed:
                old = self.db.complete(
                    self.s, self.assignments, self.source,
                    observation=observed(old.reservations[0]),
                    key="old:cost-bearing:one", expected_revision=old.revision,
                )
        return old

    def rows(self):
        with sqlite3.connect(self.path) as conn:
            return (
                conn.execute(
                    "SELECT plan_fingerprint,scope_json,source_json,revision "
                    "FROM dp319_scopes ORDER BY plan_fingerprint"
                ).fetchall(),
                conn.execute(
                    "SELECT plan_fingerprint,attempt_id,key,kind,event_json,checksum "
                    "FROM dp319_events ORDER BY plan_fingerprint,event_no"
                ).fetchall(),
            )

    def test_old_pending_cannot_register_second_scope_or_reserve_same_work(self):
        old = self.persist_old()
        self.assertEqual(old.decision.status, "WAIT_EXTERNAL")
        self.assertEqual(len(old.reservations), 1)
        before = self.rows()
        # Old history is intentionally not silently rewritten/resumed.
        with self.assertRaisesRegex(ValueError, "INTEGRITY_INVALID"):
            self.db.resume(old.decision.plan_fingerprint, source_revision=1)
        with self.assertRaisesRegex(ValueError, "LEGACY_FINGERPRINT_CONFLICT"):
            self.db.register(self.s, self.assignments, self.source)
        self.assertEqual(self.rows(), before)

    def test_old_completed_also_fences_same_source_replayed_scope(self):
        old = self.persist_old(completed=True)
        self.assertEqual(len(old.observations), 1)
        before = self.rows()
        with self.assertRaisesRegex(ValueError, "LEGACY_FINGERPRINT_CONFLICT"):
            self.db.register(self.s, self.assignments, self.source)
        self.assertEqual(self.rows(), before)

    def test_old_scope_blocks_new_constraints_on_identical_source(self):
        self.persist_old()
        before = self.rows()
        changed = (
            replace(self.assignments[0], temporal_constraints={"since": "2026-09"}),
            replace(self.assignments[0], authority_scope={"jurisdiction": "IT"}),
            replace(self.assignments[0], question="New narrower question"),
        )
        for new in changed:
            with self.subTest(new=new):
                with self.assertRaisesRegex(ValueError, "LEGACY_FINGERPRINT_CONFLICT"):
                    self.db.register(
                        self.s, (new, self.assignments[1]), self.source
                    )
                self.assertEqual(self.rows(), before)

    def test_legacy_pending_survives_rights_epoch_change_for_same_bytes(self):
        self.persist_old()
        old_rows = self.rows()
        self.db.record_source(
            replace(self.source, revision=2, rights_status="REVOKED"),
            expected_revision=1,
        )
        reapproved = replace(self.source, revision=3)
        self.db.record_source(reapproved, expected_revision=2)
        with self.assertRaisesRegex(ValueError, "LEGACY_FINGERPRINT_CONFLICT"):
            self.db.register(self.s, self.assignments, reapproved)
        self.assertEqual(self.rows(), old_rows)

    def test_legacy_scope_does_not_fence_unrelated_need_and_source(self):
        self.persist_old()
        separate = replace(
            self.source, need_id="need:other", source_id="source:other",
            candidate_id="candidate:other", material_fingerprint="source-version-sha:c",
            source_sha256="c" * 64,
        )
        self.db.record_source(separate, expected_revision=0)
        other_plan = spec(
            need_id="need:other", material_fingerprint=separate.material_fingerprint,
        )
        other_assignments = (
            replace(assignment(), coverage_need_id="need:other",
                    assignment_id="assignment:unrelated"),
        )
        accepted = self.db.register(other_plan, other_assignments, separate)
        self.assertEqual(accepted.decision.status, "READY_PRIVATE_PROPOSAL")
        self.assertEqual(len(self.rows()[0]), 2)
        self.assertEqual(len(self.rows()[1]), 1)

    def test_genuine_new_material_version_can_register_after_old_scope(self):
        self.persist_old()
        newer = source(
            revision=2, version="capture:v2",
            fingerprint="source-version-sha:b", sha="b" * 64,
        )
        self.db.record_source(newer, expected_revision=1)
        fresh = self.db.register(
            spec(material_fingerprint=newer.material_fingerprint),
            self.assignments, newer,
        )
        self.assertEqual(fresh.decision.status, "READY_PRIVATE_PROPOSAL")
        self.assertEqual(len(self.rows()[0]), 2)
        self.assertEqual(len(self.rows()[1]), 1)



class ModernCrossScopeCostFenceTests(unittest.TestCase):
    """Modern-v2 scope changes cannot reissue work already cost-reserved."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private-investigations.sqlite"
        self.db = InvestigationSQLiteStore(self.path)
        self.source = source()
        self.s = spec()
        self.a = (assignment(), assignment("PRIMARY_SOURCE"))
        self.db.record_source(self.source, expected_revision=0)
        self.db.register(self.s, self.a, self.source)

    def changed(self, *, key="temporal"):
        overrides = {
            "temporal": {"temporal_constraints": {"start": "2026-09-01"}},
            "authority": {"authority_scope": {"jurisdiction": "IT"}},
            "question": {"question": "Different reviewed source scope"},
        }
        return (replace(self.a[0], **overrides[key]), self.a[1])

    def snapshot(self):
        with sqlite3.connect(self.path) as conn:
            return (
                conn.execute(
                    "SELECT plan_fingerprint,scope_json,source_json,revision "
                    "FROM dp319_scopes ORDER BY plan_fingerprint"
                ).fetchall(),
                conn.execute(
                    "SELECT plan_fingerprint,event_no,attempt_id,key,kind,event_json,checksum "
                    "FROM dp319_events ORDER BY plan_fingerprint,event_no"
                ).fetchall(),
            )

    def test_cost_reserved_modern_scope_fences_changed_time_authority_and_question(self):
        first = self.db.reserve(
            self.s, self.a, self.source, key="modern:first", expected_revision=0,
        )
        self.assertEqual(first.decision.status, "WAIT_EXTERNAL")
        before = self.snapshot()
        for choice in ("temporal", "authority", "question"):
            with self.subTest(choice=choice):
                with self.assertRaisesRegex(ValueError, "SOURCE_SCOPE_ALREADY_RESERVED"):
                    self.db.register(self.s, self.changed(key=choice), self.source)
                self.assertEqual(self.snapshot(), before)
        self.assertEqual(
            self.db.reserve(
                self.s, self.a, self.source, key="modern:first", expected_revision=0,
            ), first,
        )

    def test_completed_modern_scope_still_fences_changed_authority(self):
        first = self.db.reserve(
            self.s, self.a, self.source, key="modern:completed", expected_revision=0,
        )
        final = self.db.complete(
            self.s, self.a, self.source,
            key="modern:completed", expected_revision=first.revision,
            observation=observed(first.reservations[0]),
        )
        self.assertEqual(len(final.observations), 1)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "SOURCE_SCOPE_ALREADY_RESERVED"):
            self.db.register(self.s, self.changed(key="authority"), self.source)
        self.assertEqual(self.snapshot(), before)

    def test_pre_registered_two_modern_scopes_cannot_both_reserve(self):
        # Registering a future scope was safe before any cost-bearing event;
        # at reservation time the immutable source-level fence is rechecked.
        b = self.changed()
        accepted = self.db.register(self.s, b, self.source)
        self.assertEqual(accepted.decision.status, "READY_PRIVATE_PROPOSAL")
        first = self.db.reserve(
            self.s, self.a, self.source, key="modern:A", expected_revision=0,
        )
        self.assertEqual(len(first.reservations), 1)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "SOURCE_SCOPE_ALREADY_RESERVED"):
            self.db.reserve(
                self.s, b, self.source, key="modern:B", expected_revision=0,
            )
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.snapshot()[1]), 1)

    def test_concurrent_modern_scopes_admit_at_most_one_reservation(self):
        b = self.changed(key="authority")
        self.db.register(self.s, b, self.source)
        barrier = Barrier(2)

        def run(assignments, key):
            reader = InvestigationSQLiteStore(self.path)
            barrier.wait(timeout=10)
            try:
                state = reader.reserve(
                    self.s, assignments, self.source,
                    key=key, expected_revision=0,
                )
                return ("RESERVED", len(state.reservations))
            except ValueError as error:
                return ("BLOCKED", str(error))

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, self.a, "modern:racer:A")
            second = pool.submit(run, b, "modern:racer:B")
            outcomes = (first.result(timeout=15), second.result(timeout=15))
        self.assertEqual(sum(item[0] == "RESERVED" for item in outcomes), 1)
        self.assertEqual(sum(item[0] == "BLOCKED" for item in outcomes), 1)
        self.assertTrue(any(
            "SOURCE_SCOPE_ALREADY_RESERVED" in item[1]
            for item in outcomes if item[0] == "BLOCKED"
        ))
        self.assertEqual(len(self.snapshot()[1]), 1)

    def _expect_corrupted_source_json_to_fail_closed(self, corrupt):
        original = self.db.reserve(
            self.s, self.a, self.source, key="modern:corrupt", expected_revision=0,
        )
        fingerprint = original.decision.plan_fingerprint
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "UPDATE dp319_scopes SET source_json=? WHERE plan_fingerprint=?",
                (corrupt, fingerprint),
            )
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "INTEGRITY_INVALID"):
            self.db.register(self.s, self.changed(key="authority"), self.source)
        self.assertEqual(self.snapshot(), before)

    def test_valid_json_array_in_persisted_source_cannot_bypass_scope_fence(self):
        self._expect_corrupted_source_json_to_fail_closed("[]")

    def test_valid_json_missing_source_sha_cannot_bypass_scope_fence(self):
        raw = {**asdict(self.source)}
        raw.pop("source_sha256")
        self._expect_corrupted_source_json_to_fail_closed(_json(raw))

    def test_cost_free_changed_modern_plan_can_register_and_new_version_can_reserve(self):
        b = self.changed()
        self.assertEqual(
            self.db.register(self.s, b, self.source).decision.status,
            "READY_PRIVATE_PROPOSAL",
        )
        # Only a genuinely changed material/source version can reopen after
        # an actual reservation on the old immutable version.
        old = self.db.reserve(
            self.s, self.a, self.source, key="modern:old", expected_revision=0,
        )
        self.assertEqual(len(old.reservations), 1)
        next_version = source(
            revision=2, version="capture:v2", fingerprint="source-version-sha:b",
            sha="b" * 64,
        )
        self.db.record_source(next_version, expected_revision=1)
        newer_spec = spec(material_fingerprint=next_version.material_fingerprint)
        self.db.register(newer_spec, b, next_version)
        fresh = self.db.reserve(
            newer_spec, b, next_version, key="modern:new", expected_revision=0,
        )
        self.assertEqual(len(fresh.reservations), 1)



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

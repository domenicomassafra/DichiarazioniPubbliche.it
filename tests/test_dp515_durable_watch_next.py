"""DP-515: real disposable SQLite watch attempts; never HTTP or child dispatch."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchObservation,
    WatchPolicy,
    WatchReadiness,
    WatchState,
    policy_fingerprint,
)
from dichiarazioni_pubbliche.source_watch_store_v1 import LocalSourceWatchStore


NOW = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
H1 = "a" * 64
H2 = "b" * 64
MODIFIED = "Fri, 09 Oct 2026 08:00:00 GMT"


def policy():
    return WatchPolicy(
        source_id="official:senate:1",
        locator_id="official:senate:feed",
        source_family="OFFICIAL_RSS",
        corpus_id="corpus:private",
        corpus_cutoff="2026-10-01",
        policy_revision="operator-r1",
        enabled=True,
    )


def readiness(p, **changes):
    options = dict(
        source_id=p.source_id,
        policy_fingerprint=policy_fingerprint(p),
        corpus_id=p.corpus_id,
        rights_status="READY",
        rights_receipt="fixture:rights:1",
        capability_status="READY",
        capability_receipt="fixture:capability:1",
        budget_status="READY",
        budget_receipt="fixture:budget:1",
        remaining_children=1,
    )
    return WatchReadiness(**(options | changes))


def observation(
    *,
    at=NOW + timedelta(seconds=1),
    hash_value=H2,
    version="v2",
    etag='"new"',
    status=200,
):
    return WatchObservation(
        observed_at=at,
        status_code=status,
        content_sha256=hash_value if status == 200 else None,
        source_version=version if status == 200 else None,
        etag=etag if status == 200 else None,
        last_modified=MODIFIED if status == 200 else None,
    )


class DurableWatchTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.db = Path(scratch.name) / "watch.sqlite"
        self.conn = sqlite3.connect(self.db, isolation_level=None, timeout=2)
        self.addCleanup(lambda: self.conn.close())
        self.store = LocalSourceWatchStore(self.conn)
        self.store.init_isolated_fixture_schema()
        self.p = policy()
        self.s = WatchState(
            source_id=self.p.source_id,
            policy_fingerprint=policy_fingerprint(self.p),
            revision=3,
            etag='"old"',
            last_modified=MODIFIED,
            source_version="v1",
            content_sha256=H1,
            last_attempted_at=NOW - timedelta(days=1),
            last_successful_observed_at=NOW - timedelta(days=1),
            last_attempt_id="prior",
        )
        self.store.register_fixture_source(self.p, self.s, readiness(self.p))

    def begin(self, key="poll:one", at=NOW):
        return self.store.begin_poll(self.p.source_id, attempt_id=key, attempted_at=at)

    def finish(self, item=None, key="poll:one"):
        return self.store.commit_observation(
            self.p.source_id,
            attempt_id=key,
            observation=item or observation(),
        )

    def reopen(self):
        self.conn.close()
        self.conn = sqlite3.connect(self.db, isolation_level=None, timeout=2)
        self.store = LocalSourceWatchStore(self.conn)

    def test_conditional_304_durable_unchanged_restart_and_exact_retry(self):
        plan = self.begin()
        self.assertTrue(plan.allowed)
        self.assertEqual(plan.state_revision, 3)
        self.assertEqual(
            plan.conditional_headers,
            (
                ("If-None-Match", '"old"'),
                ("If-Modified-Since", MODIFIED),
            ),
        )
        reply = WatchObservation(
            observed_at=NOW + timedelta(seconds=1), status_code=304
        )
        result = self.finish(reply)
        self.assertEqual(result.disposition, "UNCHANGED")
        self.assertEqual(result.next_state.source_version, "v1")
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())
        self.reopen()
        self.assertEqual(self.store.read_state(self.p.source_id), result.next_state)
        self.assertEqual(self.finish(reply), result)
        self.assertEqual(self.store.committed_attempt_count(self.p.source_id), 1)
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            self.finish(observation())

    def test_changed_hash_persists_one_review_proposal_without_child_job(self):
        result = self.finish_after_begin()
        self.assertEqual(result.disposition, "CHANGED")
        self.assertEqual(len(result.children), 1)
        proposal = result.children[0]
        self.assertEqual(proposal.observed_source_version, "v2")
        self.assertEqual(proposal.previous_source_version, "v1")
        self.assertEqual(proposal.observed_sha256, H2)
        self.assertEqual(len(self.store.private_proposals(self.p.source_id)), 1)
        self.reopen()
        self.assertEqual(self.finish(), result)
        later = self.begin("poll:two", NOW + timedelta(minutes=1))
        self.assertEqual(later.conditional_headers[0], ("If-None-Match", '"new"'))
        later_result = self.finish(
            observation(at=NOW + timedelta(minutes=1, seconds=1)),
            key="poll:two",
        )
        self.assertEqual(later_result.disposition, "UNCHANGED")
        self.assertEqual(len(self.store.private_proposals(self.p.source_id)), 1)
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE '%job%'"
            ).fetchone()[0],
            0,
        )
        with self.assertRaisesRegex(ValueError, "STATE_REVISION_CONFLICT"):
            self.store.commit_observation(
                self.p.source_id,
                attempt_id="poll:one",
                observation=observation(),
            )

    def test_persisted_newer_version_is_not_rolled_back_by_stale_200(self):
        p_recent = replace(
            self.p,
            source_id="official:senate:recent",
            locator_id="official:senate:recent-feed",
        )
        recent = replace(
            self.s,
            source_id=p_recent.source_id,
            policy_fingerprint=policy_fingerprint(p_recent),
            content_sha256=H2,
            source_version="v2",
            etag='"new"',
            last_modified="Sat, 10 Oct 2026 08:00:00 GMT",
        )
        self.store.register_fixture_source(p_recent, recent, readiness(p_recent))
        plan = self.store.begin_poll(
            p_recent.source_id,
            attempt_id="poll:old",
            attempted_at=NOW,
        )
        self.assertTrue(plan.allowed)
        result = self.store.commit_observation(
            p_recent.source_id,
            attempt_id="poll:old",
            observation=observation(hash_value=H1, version="v1", etag='"old"'),
        )
        self.assertEqual(result.disposition, "UNAVAILABLE")
        self.assertEqual(result.reason, "LAST_MODIFIED_REGRESSED")
        self.assertEqual(result.children, ())
        self.assertTrue(result.needs_source_review)
        self.assertEqual(self.store.private_proposals(p_recent.source_id), ())
        self.reopen()
        saved = self.store.read_state(p_recent.source_id)
        self.assertEqual(saved.content_sha256, H2)
        self.assertEqual(saved.source_version, "v2")
        self.assertEqual(saved.etag, '"new"')
        self.assertEqual(saved.last_modified, recent.last_modified)
        self.assertEqual(
            saved.last_successful_observed_at, recent.last_successful_observed_at
        )
        self.assertGreater(saved.retry_not_before, NOW)

    def finish_after_begin(self):
        self.begin()
        return self.finish()

    def test_revoked_rights_between_plan_and_commit_retains_old_version(self):
        self.begin()
        self.store.update_fixture_readiness(
            readiness(self.p, rights_status="REVOKED"), expected_gate_revision=0
        )
        with self.assertRaisesRegex(ValueError, "GATE_CHANGED"):
            self.begin()
        result = self.finish()
        self.assertEqual(result.disposition, "BLOCKED")
        self.assertEqual(result.reason, "RIGHTS_NOT_READY")
        self.assertEqual(result.children, ())
        self.assertEqual(result.next_state.content_sha256, H1)
        self.assertEqual(result.next_state.etag, '"old"')
        self.assertEqual(
            result.next_state.last_successful_observed_at, NOW - timedelta(days=1)
        )
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())
        denied = self.begin("poll:two", NOW + timedelta(minutes=2))
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "RIGHTS_NOT_READY")
        with self.assertRaisesRegex(ValueError, "GATE_REVISION_CONFLICT"):
            self.store.update_fixture_readiness(
                readiness(self.p), expected_gate_revision=0
            )

    def test_revocation_after_change_hides_held_proposal_and_prevents_replay(self):
        self.finish_after_begin()
        self.assertEqual(len(self.store.private_proposals(self.p.source_id)), 1)
        self.store.update_fixture_readiness(
            readiness(self.p, rights_status="REVOKED"), expected_gate_revision=0
        )
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())
        with self.assertRaisesRegex(ValueError, "RIGHTS_NOT_READY"):
            self.finish()
        # Restoration cannot quietly resurrect a proposal from the revoked epoch.
        self.store.update_fixture_readiness(readiness(self.p), expected_gate_revision=1)
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())
        with self.assertRaisesRegex(ValueError, "GATE_CHANGED"):
            self.finish()

    def test_revoke_and_restore_before_observation_cannot_reuse_old_ready_gate(self):
        self.begin()
        self.store.update_fixture_readiness(
            readiness(self.p, rights_status="REVOKED"), expected_gate_revision=0
        )
        self.store.update_fixture_readiness(readiness(self.p), expected_gate_revision=1)
        with self.assertRaisesRegex(ValueError, "GATE_CHANGED"):
            self.finish()
        with self.assertRaisesRegex(ValueError, "GATE_CHANGED"):
            self.begin()
        self.assertEqual(self.store.committed_attempt_count(self.p.source_id), 0)
        self.assertEqual(self.store.read_state(self.p.source_id), self.s)
        with self.assertRaisesRegex(ValueError, "GATE_REVISION_CONFLICT"):
            self.store.abandon_stale_attempt(
                self.p.source_id,
                attempt_id="poll:one",
                expected_state_revision=3,
                expected_gate_revision=1,
            )
        self.store.abandon_stale_attempt(
            self.p.source_id,
            attempt_id="poll:one",
            expected_state_revision=3,
            expected_gate_revision=2,
        )
        with self.assertRaisesRegex(ValueError, "STATE_REVISION_CONFLICT"):
            self.finish()
        plan = self.begin("poll:new-after-hold", NOW + timedelta(minutes=1))
        self.assertTrue(plan.allowed)
        self.assertEqual(self.store.read_state(self.p.source_id), self.s)

    def test_rate_limit_backoff_persists_without_invented_success_or_child(self):
        self.begin()
        throttled = WatchObservation(
            observed_at=NOW + timedelta(seconds=2),
            status_code=429,
            retry_after_seconds=120,
        )
        result = self.finish(throttled)
        self.assertEqual(result.disposition, "UNAVAILABLE")
        self.assertEqual(result.reason, "HTTP_429")
        self.assertEqual(result.next_state.content_sha256, H1)
        self.assertEqual(
            result.next_state.last_successful_observed_at, NOW - timedelta(days=1)
        )
        self.reopen()
        backoff = self.begin("poll:early", NOW + timedelta(seconds=30))
        self.assertEqual(backoff.reason, "SOURCE_BACKOFF")
        self.assertFalse(backoff.allowed)
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())

    def test_out_of_order_and_active_attempt_retry_are_source_serialized(self):
        first = self.begin()
        self.assertEqual(self.begin(), first)
        with self.assertRaisesRegex(ValueError, "ATTEMPT_IN_FLIGHT"):
            self.begin("poll:other", NOW + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            self.store.begin_poll(
                self.p.source_id,
                attempt_id="poll:one",
                attempted_at=NOW + timedelta(seconds=1),
            )
        self.finish()
        older = self.begin("poll:older", NOW - timedelta(seconds=1))
        self.assertFalse(older.allowed)
        self.assertEqual(older.reason, "ATTEMPT_OUT_OF_ORDER")

    def test_crashed_poll_same_gate_expires_with_atomic_cas_and_restarts(self):
        self.begin()
        self.reopen()
        with self.assertRaisesRegex(ValueError, "ATTEMPT_IN_FLIGHT"):
            self.begin("poll:replacement", NOW + timedelta(minutes=6))
        with self.assertRaisesRegex(ValueError, "LEASE_NOT_EXPIRED"):
            self.store.expire_stale_attempt(
                self.p.source_id,
                attempt_id="poll:one",
                as_of=NOW + timedelta(seconds=299),
                expected_state_revision=3,
                expected_gate_revision=0,
            )
        with self.assertRaisesRegex(ValueError, "STATE_REVISION_CONFLICT"):
            self.store.expire_stale_attempt(
                self.p.source_id,
                attempt_id="poll:one",
                as_of=NOW + timedelta(minutes=5),
                expected_state_revision=4,
                expected_gate_revision=0,
            )
        self.store.expire_stale_attempt(
            self.p.source_id,
            attempt_id="poll:one",
            as_of=NOW + timedelta(minutes=5),
            expected_state_revision=3,
            expected_gate_revision=0,
        )
        self.assertEqual(self.store.read_state(self.p.source_id), self.s)
        self.assertEqual(self.store.committed_attempt_count(self.p.source_id), 0)
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())
        with self.assertRaisesRegex(ValueError, "STATE_REVISION_CONFLICT"):
            self.finish()
        with self.assertRaisesRegex(ValueError, "STATE_REVISION_CONFLICT"):
            self.begin()
        self.reopen()
        plan = self.begin("poll:replacement", NOW + timedelta(minutes=5, seconds=1))
        self.assertTrue(plan.allowed)
        self.assertEqual(
            self.finish(
                observation(at=NOW + timedelta(minutes=5, seconds=2)),
                key="poll:replacement",
            ).disposition,
            "CHANGED",
        )

    def test_pinned_lease_cannot_be_shortened_on_replay_or_expired_twice(self):
        self.store.begin_poll(
            self.p.source_id,
            attempt_id="poll:custom",
            attempted_at=NOW,
            lease_seconds=600,
        )
        self.reopen()
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            self.store.begin_poll(
                self.p.source_id,
                attempt_id="poll:custom",
                attempted_at=NOW,
                lease_seconds=30,
            )
        with self.assertRaisesRegex(ValueError, "LEASE_NOT_EXPIRED"):
            self.store.expire_stale_attempt(
                self.p.source_id,
                attempt_id="poll:custom",
                as_of=NOW + timedelta(minutes=5),
                expected_state_revision=3,
                expected_gate_revision=0,
            )
        self.store.expire_stale_attempt(
            self.p.source_id,
            attempt_id="poll:custom",
            as_of=NOW + timedelta(minutes=10),
            expected_state_revision=3,
            expected_gate_revision=0,
        )
        with self.assertRaisesRegex(ValueError, "LEASE_NOT_ACTIVE"):
            self.store.expire_stale_attempt(
                self.p.source_id,
                attempt_id="poll:custom",
                as_of=NOW + timedelta(minutes=11),
                expected_state_revision=3,
                expected_gate_revision=0,
            )

    def test_late_observation_cannot_claim_success_after_lease_deadline(self):
        self.store.begin_poll(
            self.p.source_id,
            attempt_id="poll:short",
            attempted_at=NOW,
            lease_seconds=30,
        )
        for second in (30, 31):
            with self.subTest(second=second):
                with self.assertRaisesRegex(ValueError, "LEASE_EXPIRED"):
                    self.store.commit_observation(
                        self.p.source_id,
                        attempt_id="poll:short",
                        observation=observation(at=NOW + timedelta(seconds=second)),
                    )
        self.assertEqual(self.store.read_state(self.p.source_id), self.s)
        self.assertEqual(self.store.committed_attempt_count(self.p.source_id), 0)
        self.store.expire_stale_attempt(
            self.p.source_id,
            attempt_id="poll:short",
            as_of=NOW + timedelta(seconds=31),
            expected_state_revision=3,
            expected_gate_revision=0,
        )

    def test_lease_expiration_requires_valid_inputs_and_current_gate(self):
        for invalid in (0, -1, True, 86401, 2.5):
            with self.subTest(duration=invalid):
                with self.assertRaisesRegex(ValueError, "LEASE_DURATION_INVALID"):
                    self.store.begin_poll(
                        self.p.source_id,
                        attempt_id="poll:one",
                        attempted_at=NOW,
                        lease_seconds=invalid,
                    )
        self.begin()
        with self.assertRaisesRegex(ValueError, "LEASE_AS_OF_TZ_REQUIRED"):
            self.store.expire_stale_attempt(
                self.p.source_id,
                attempt_id="poll:one",
                as_of=NOW.replace(tzinfo=None),
                expected_state_revision=3,
                expected_gate_revision=0,
            )
        self.store.update_fixture_readiness(
            readiness(self.p, rights_status="REVOKED"),
            expected_gate_revision=0,
        )
        with self.assertRaisesRegex(ValueError, "GATE_REVISION_CONFLICT"):
            self.store.expire_stale_attempt(
                self.p.source_id,
                attempt_id="poll:one",
                as_of=NOW + timedelta(minutes=10),
                expected_state_revision=3,
                expected_gate_revision=0,
            )
        self.store.expire_stale_attempt(
            self.p.source_id,
            attempt_id="poll:one",
            as_of=NOW + timedelta(minutes=10),
            expected_state_revision=3,
            expected_gate_revision=1,
        )
        denied = self.begin("poll:after-expiry", NOW + timedelta(minutes=11))
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "RIGHTS_NOT_READY")
        self.assertEqual(self.store.private_proposals(self.p.source_id), ())

    def test_two_connections_racing_expiry_and_commit_have_one_winner(self):
        self.begin()
        barrier = Barrier(2)

        def compete(action):
            connection = sqlite3.connect(self.db, isolation_level=None, timeout=3)
            try:
                other = LocalSourceWatchStore(connection)
                barrier.wait(timeout=3)
                try:
                    if action == "commit":
                        other.commit_observation(
                            self.p.source_id,
                            attempt_id="poll:one",
                            observation=observation(),
                        )
                    else:
                        other.expire_stale_attempt(
                            self.p.source_id,
                            attempt_id="poll:one",
                            as_of=NOW + timedelta(minutes=5),
                            expected_state_revision=3,
                            expected_gate_revision=0,
                        )
                    return action
                except ValueError as exc:
                    return str(exc)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [
                future.result(timeout=5)
                for future in (
                    executor.submit(compete, "commit"),
                    executor.submit(compete, "expire"),
                )
            ]
        self.assertEqual(sum(result in {"commit", "expire"} for result in results), 1)
        status = self.conn.execute(
            "SELECT status FROM dp515_watch_attempt WHERE source_id=? AND attempt_id=?",
            (self.p.source_id, "poll:one"),
        ).fetchone()[0]
        self.assertEqual(status, "COMMITTED" if "commit" in results else "ABANDONED")
        self.assertEqual(
            self.store.committed_attempt_count(self.p.source_id),
            int(status == "COMMITTED"),
        )
        self.assertEqual(
            len(self.store.private_proposals(self.p.source_id)),
            int(status == "COMMITTED"),
        )

    def test_failed_child_proposal_insert_rolls_back_state_and_replays_after_restart(
        self,
    ):
        self.begin()
        self.conn.execute(
            "CREATE TRIGGER dp515_abort BEFORE INSERT ON dp515_watch_proposal "
            "BEGIN SELECT RAISE(ABORT, 'injected crash'); END"
        )
        with self.assertRaisesRegex(sqlite3.DatabaseError, "injected crash"):
            self.finish()
        self.assertEqual(self.store.read_state(self.p.source_id), self.s)
        self.assertEqual(self.store.committed_attempt_count(self.p.source_id), 0)
        self.conn.execute("DROP TRIGGER dp515_abort")
        self.reopen()
        self.assertEqual(self.finish().disposition, "CHANGED")
        self.assertEqual(self.store.committed_attempt_count(self.p.source_id), 1)
        self.assertEqual(len(self.store.private_proposals(self.p.source_id)), 1)

    def test_policy_fingerprint_and_gate_scope_cannot_be_rebound(self):
        other = replace(self.p, policy_revision="operator-r2")
        with self.assertRaisesRegex(ValueError, "POLICY_SCOPE_MISMATCH"):
            self.store.register_fixture_source(other, self.s, readiness(other))
        with self.assertRaisesRegex(ValueError, "GATE_SCOPE_MISMATCH"):
            self.store.update_fixture_readiness(
                readiness(self.p, corpus_id="foreign"), expected_gate_revision=0
            )
        self.conn.execute(
            "UPDATE dp515_watch_source SET policy_sha256=? WHERE source_id=?",
            ("0" * 64, self.p.source_id),
        )
        with self.assertRaisesRegex(ValueError, "POLICY_FINGERPRINT_MISMATCH"):
            self.begin()

    def test_two_real_connections_cannot_begin_two_parallel_attempts(self):
        barrier = Barrier(2)

        def compete(attempt_id):
            connection = sqlite3.connect(self.db, isolation_level=None, timeout=3)
            try:
                other = LocalSourceWatchStore(connection)
                barrier.wait(timeout=3)
                try:
                    return other.begin_poll(
                        self.p.source_id, attempt_id=attempt_id, attempted_at=NOW
                    ).reason
                except ValueError as exc:
                    return str(exc)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(compete, "poll:worker:a")
            b = executor.submit(compete, "poll:worker:b")
            results = {a.result(timeout=5), b.result(timeout=5)}
        self.assertEqual(results, {"CHECK_READY", "WATCH_STORE_ATTEMPT_IN_FLIGHT"})
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM dp515_watch_attempt "
                "WHERE source_id=? AND status='IN_FLIGHT'",
                (self.p.source_id,),
            ).fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()

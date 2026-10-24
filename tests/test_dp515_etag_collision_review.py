"""DP-515: a persisted conflicting ETag must request private source review."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchState,
    policy_fingerprint,
)
from dichiarazioni_pubbliche.source_watch_store_v1 import LocalSourceWatchStore
from tests.test_dp515_durable_watch_next import (
    H1,
    H2,
    MODIFIED,
    NOW,
    observation,
    policy,
    readiness,
)


class ConflictingETagReviewTests(unittest.TestCase):
    def test_changed_bytes_under_reused_etag_raise_private_source_review(self):
        p = policy()
        state = WatchState(
            source_id=p.source_id,
            policy_fingerprint=policy_fingerprint(p),
            revision=3,
            etag='"old"',
            last_modified=MODIFIED,
            source_version="v1",
            content_sha256=H1,
            last_attempted_at=NOW - timedelta(days=1),
            last_successful_observed_at=NOW - timedelta(days=1),
            last_attempt_id="prior",
        )
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        database = Path(scratch.name) / "watch.sqlite"
        conn = sqlite3.connect(database, isolation_level=None, timeout=2)
        store = LocalSourceWatchStore(conn)
        store.init_isolated_fixture_schema()
        store.register_fixture_source(p, state, readiness(p))

        plan = store.begin_poll(p.source_id, attempt_id="poll:one", attempted_at=NOW)
        self.assertTrue(plan.allowed)
        collision = observation(hash_value=H2, version="v2", etag='"old"')
        decision = store.commit_observation(
            p.source_id, attempt_id="poll:one", observation=collision,
        )
        self.assertEqual(decision.disposition, "UNAVAILABLE")
        self.assertEqual(decision.reason, "ETAG_CONTENT_CONFLICT")
        self.assertTrue(decision.needs_source_review)
        self.assertEqual(decision.children, ())
        self.assertEqual(decision.next_state.content_sha256, H1)
        self.assertEqual(
            decision.next_state.last_successful_observed_at,
            NOW - timedelta(days=1),
        )
        self.assertGreater(decision.next_state.retry_not_before, NOW)
        conn.close()

        with sqlite3.connect(database, isolation_level=None, timeout=2) as reopened:
            durable = LocalSourceWatchStore(reopened)
            self.assertEqual(
                durable.commit_observation(
                    p.source_id, attempt_id="poll:one", observation=collision,
                ),
                decision,
            )
            self.assertEqual(durable.private_proposals(p.source_id), ())
            plan = durable.begin_poll(
                p.source_id,
                attempt_id="poll:retry-too-soon",
                attempted_at=NOW + timedelta(seconds=3),
            )
            self.assertEqual(plan.reason, "SOURCE_BACKOFF")


if __name__ == "__main__":
    unittest.main()

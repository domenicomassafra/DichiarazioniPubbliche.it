"""Policy-denied legacy source ticks remain bounded without false health success."""

import unittest
from datetime import timedelta
from unittest import mock

from dichiarazioni_pubbliche.scheduler_daemon import (
    PollOutcome, PsqlStore, RuntimeBudget, SourceHealthState, SourceRunContext,
    poll_source,
)
from tests.test_scheduler_daemon import FakeStore, NOW, SOURCE, content


class PolicyCooldownTests(unittest.TestCase):
    def test_relevance_denial_cools_down_without_health_failure_or_child(self):
        class PolicyStore(FakeStore):
            def __init__(self):
                super().__init__()
                self.policy_blocks = []

            def mark_policy_block(self, source_id, error):
                self.policy_blocks.append((source_id, error))
                self.health_state = SourceHealthState(NOW, 0)

        store = PolicyStore()
        store.relevance_allowed = False
        discoveries = []

        def discover(source):
            discoveries.append(source["id"])
            return [content()]

        first = poll_source(SOURCE, store, now=NOW, budget=RuntimeBudget(),
                            discover=discover)
        self.assertEqual(first.status, "BLOCKED")
        self.assertEqual(first.error_category, "INGESTION_RELEVANCE_MISSING")
        self.assertEqual(store.policy_blocks, [(SOURCE["id"], "INGESTION_RELEVANCE_MISSING")])
        self.assertEqual(store.failures, [])
        self.assertEqual(store.successes, [])
        self.assertEqual(store.jobs, [])
        self.assertEqual(store.health_state.consecutive_failures, 0)

        second = poll_source(SOURCE, store, now=NOW + timedelta(minutes=5),
                             budget=RuntimeBudget(), discover=discover)
        self.assertEqual(second.status, "SKIPPED_NOT_DUE")
        self.assertEqual(discoveries, [SOURCE["id"]])
        self.assertEqual(store.policy_blocks, [(SOURCE["id"], "INGESTION_RELEVANCE_MISSING")])

        # Policy stays denied even when the normal (bounded) source interval lapses.
        third = poll_source(SOURCE, store, now=NOW + timedelta(minutes=30),
                            budget=RuntimeBudget(), discover=discover)
        self.assertEqual(third.status, "BLOCKED")
        self.assertEqual(len(discoveries), 2)
        self.assertEqual(store.jobs, [])

    def test_postgres_receipt_uses_policy_block_not_provider_failure(self):
        context = SourceRunContext(
            "source-poll:synthetic", "source-due", NOW.date().isoformat(),
            "a" * 64,
        )
        blocked = PollOutcome(
            SOURCE["id"], "BLOCKED", error_category="INGESTION_RELEVANCE_MISSING",
        )
        with mock.patch.object(PsqlStore, "_run", return_value="") as query:
            PsqlStore().record_source_poll_source(
                SOURCE, blocked, context=context, started_at=NOW,
                completed_at=NOW, failure_category="INGESTION_RELEVANCE_MISSING",
            )
        sql = query.call_args.args[0]
        self.assertIn("'POLICY_BLOCKED'", sql)
        self.assertIn("consecutive_failures = 0", sql)
        self.assertIn("checked_at = now()", sql)
        self.assertNotIn("source_health.consecutive_failures + 1", sql)
        self.assertNotIn("last_success_at = now()", sql)
        self.assertEqual(query.call_args.kwargs["error"], "INGESTION_RELEVANCE_MISSING")

    def test_technical_failure_still_uses_exponential_health_failure(self):
        with mock.patch.object(PsqlStore, "_run", return_value="") as query:
            PsqlStore().mark_failure(SOURCE["id"], "TIMEOUT")
        sql = query.call_args.args[0]
        self.assertIn("'DEGRADED'", sql)
        self.assertIn("source_health.consecutive_failures + 1", sql)
        self.assertNotIn("'POLICY_BLOCKED'", sql)

    def test_policy_block_single_source_sql_preserves_success_timestamp(self):
        with mock.patch.object(PsqlStore, "_run", return_value="") as query:
            PsqlStore().mark_policy_block(SOURCE["id"], "INGESTION_RELEVANCE_MISSING")
        sql = query.call_args.args[0]
        self.assertIn("'POLICY_BLOCKED'", sql)
        self.assertNotIn("last_success_at =", sql)
        self.assertIn("checked_at = now()", sql)
        self.assertEqual(query.call_args.kwargs["source_id"], SOURCE["id"])


if __name__ == "__main__":
    unittest.main()

"""Regression cases for persisted full-source receipt integrity."""

from pathlib import Path


class ReceiptIntegrityCases:
    def test_rights_blocked_child_is_written_and_read_back(self):
        self.write_registry([{
            "id": "official-rss", "kind": "public_rss", "name": "Public feed"
        }])
        store = self.fake_store_type()
        first = self.run_full(store, lambda source: [])
        self.assertEqual(first.status, "COMPLETED")
        rows = store.list_source_poll_sources(first.run_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "BLOCKED")
        self.assertEqual(rows[0]["error_category"], "RIGHTS_HOLD")
        replay = self.run_full(store, lambda source: [])
        self.assertEqual(replay.status, "SKIPPED_ALREADY_COMPLETED")
        self.assertEqual(replay[0].status, "BLOCKED")

    def test_daily_units_and_receipt_schema_are_present(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.service").read_text()
        timer = (root / "deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.timer").read_text()
        schema = (root / "db/schema.v1.sql").read_text()
        migration = (root / "db/migrations/20260925-add-source-poll-run-receipts.sql").read_text()
        self.assertIn("--full-source", service)
        self.assertIn("OnCalendar=daily", timer)
        for sql in (schema, migration):
            self.assertIn("CREATE TABLE IF NOT EXISTS source_poll_run", sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS source_poll_run_source", sql)
            self.assertIn("id                      text PRIMARY KEY", sql)
            self.assertIn("mode                    text NOT NULL", sql)
            self.assertIn("run_date                date NOT NULL", sql)
            self.assertIn("effective_config_hash", sql)
            self.assertIn("error_category", sql)
            self.assertIn("jobs_enqueued", sql)

    def test_missing_child_after_commit_never_completes_parent(self):
        class LostReceiptStore(self.fake_store_type):
            def commit_source_poll(self, source, items, **kwargs):
                result = super().commit_source_poll(source, items, **kwargs)
                self.source_poll_runs[kwargs["context"].run_id]["sources"].pop(source["id"])
                return result

        store = LostReceiptStore()
        result = self.run_full(store, lambda source: [self.item(source["id"], 1)])
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(store.source_poll_runs[result.run_id]["status"], "FAILED")
        self.assertEqual(store.source_poll_runs[result.run_id]["error_category"], "RECEIPT_COUNT_MISMATCH")

    def test_receipt_insert_error_is_persisted_on_parent(self):
        class RejectedReceiptStore(self.fake_store_type):
            def record_source_poll_source(self, source, outcome, **kwargs):
                if source["id"] == "unsupported-source":
                    raise RuntimeError("CHECK constraint source_poll_run_source_status_check")
                return super().record_source_poll_source(source, outcome, **kwargs)

        store = RejectedReceiptStore()
        result = self.run_full(store, lambda source: [self.item(source["id"], 1)])
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(store.source_poll_runs[result.run_id]["status"], "FAILED")
        self.assertEqual(store.source_poll_runs[result.run_id]["error_category"], "RECEIPT_WRITE_FAILED")

    def test_incomplete_completed_replay_becomes_explicit_failure(self):
        store = self.fake_store_type()
        first = self.run_full(store, lambda source: [self.item(source["id"], 1)])
        del store.source_poll_runs[first.run_id]["sources"]["youtube-second"]
        replay = self.run_full(
            store,
            lambda source: (_ for _ in ()).throw(AssertionError("unexpected discovery")),
        )
        self.assertEqual(replay.status, "FAILED")
        self.assertEqual(store.source_poll_runs[first.run_id]["status"], "FAILED")
        self.assertEqual(store.source_poll_runs[first.run_id]["error_category"], "RECEIPT_COUNT_MISMATCH")

    def test_parent_update_failure_is_not_swallowed(self):
        class RejectedParentStore(self.fake_store_type):
            def complete_source_poll_run(self, **values):
                raise RuntimeError("database write rejected")

        with self.assertRaisesRegex(RuntimeError, "database write rejected"):
            self.run_full(RejectedParentStore(), lambda source: [self.item(source["id"], 1)])

    def test_rejected_completed_update_persists_parent_failure(self):
        class GuardedStore(self.fake_store_type):
            def complete_source_poll_run(self, **values):
                if values["status"] == "COMPLETED":
                    raise RuntimeError("completion rejected")
                return super().complete_source_poll_run(**values)

        store = GuardedStore()
        with self.assertRaisesRegex(RuntimeError, "completion rejected"):
            self.run_full(store, lambda source: [self.item(source["id"], 1)])
        parent = next(iter(store.source_poll_runs.values()))
        self.assertEqual(parent["status"], "FAILED")
        self.assertEqual(parent["error_category"], "RECEIPT_WRITE_FAILED")

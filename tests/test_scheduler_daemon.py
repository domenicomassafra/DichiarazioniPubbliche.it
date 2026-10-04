import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.scheduler_daemon import (
    PollOutcome,
    RuntimeBudget,
    SourceHealthState,
    canonical_registry_policy_hash,
    poll_source,
    run_registry,
    scheduler_ingest_plan,
    source_due,
    utc_run_date,
)
from dichiarazioni_pubbliche.source_watcher import DiscoveredContent


NOW = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)


def content(platform: str = "podcast_rss") -> DiscoveredContent:
    return DiscoveredContent(
        source_id="youtube-pulp-podcast",
        platform=platform,
        external_id="episode-64",
        title="Beppe Grillo a Pulp Podcast | Pulp Podcast #64",
        canonical_url="https://example.test/episode-64",
        published_at="2026-09-21T11:00:00+00:00",
        author="PULP PODCAST",
    )


class FakeStore:
    def __init__(self):
        self.health_state = SourceHealthState(None, 0)
        self.global_cost = 0.0
        self.source_cost = 0.0
        self.content_ids = []
        self.jobs = []
        self.successes = []
        self.failures = []
        self.locators = {}
        self.source_poll_runs = {}
        self.source_poll_sources = {}
        self._source_poll_runs = self.source_poll_runs

    def upsert_source(self, source):
        self.source = source

    def health(self, source_id):
        return self.health_state

    def cost_today(self, source_id=None):
        return self.source_cost if source_id else self.global_cost

    def resolve_content_id(self, platform, external_id, fallback_id):
        return self.locators.get((platform, external_id), fallback_id)

    def upsert_content(self, item, content_id):
        self.content_ids.append(content_id)
        self.locators[(item.platform, item.external_id)] = content_id

    def enqueue(self, job, content_id):
        pair = (job.job_id, content_id)
        if pair in self.jobs:
            return False
        self.jobs.append(pair)
        return True

    def mark_success(self, source_id, last_item_at):
        self.successes.append((source_id, last_item_at))

    def mark_failure(self, source_id, error):
        self.failures.append((source_id, error))

    def get_source_poll_run(self, run_id):
        value = self.source_poll_runs.get(run_id)
        return dict(value) if value else None

    def start_source_poll_run(
        self, *, run_id, mode, run_date, effective_config_hash, diagnostic
    ):
        value = self.source_poll_runs.get(run_id)
        if value and value["status"] == "COMPLETED":
            return "COMPLETED"
        self.source_poll_runs[run_id] = {
            "run_id": run_id,
            "mode": mode,
            "run_date": run_date,
            "effective_config_hash": effective_config_hash,
            "status": "RUNNING",
            "diagnostic": diagnostic,
            "started_at": NOW.isoformat(),
            "completed_at": None,
            "sources": {},
        }
        return "RUNNING"

    def get_source_poll_source(self, run_id, source_id):
        run = self.source_poll_runs.get(run_id)
        value = run.get("sources", {}).get(source_id) if run else None
        return dict(value) if value else None

    def list_source_poll_sources(self, run_id):
        run = self.source_poll_runs.get(run_id)
        return [dict(value) for _, value in sorted((run or {}).get("sources", {}).items())]

    def source_poll_day_status(self, *, run_date, source_ids, exclude_run_id):
        result = {}
        for run in self.source_poll_runs.values():
            if run["run_date"] != run_date or run["run_id"] == exclude_run_id:
                continue
            if run["status"] not in {"COMPLETED", "FAILED"}:
                continue
            for source_id, value in run.get("sources", {}).items():
                if source_id in source_ids:
                    result[source_id] = {
                        "run_id": run["run_id"],
                        "status": value["status"],
                    }
        return result

    def _record_receipt(self, run_id, outcome, context):
        run = self.source_poll_runs[run_id]
        run["sources"][outcome.source_id] = {
            "receipt_id": outcome.receipt_id,
            "run_id": run_id,
            "source_id": outcome.source_id,
            "mode": context.mode,
            "run_date": context.run_date,
            "effective_config_hash": context.effective_config_hash,
            "diagnostic": context.diagnostic,
            "status": outcome.status,
            "discovered": outcome.discovered,
            "content_upserts": outcome.content_upserts,
            "jobs_enqueued": outcome.jobs_enqueued,
            "duplicate_jobs": outcome.duplicate_jobs,
            "budget_blocked": outcome.budget_blocked,
            "omitted_items": outcome.omitted_items,
            "error": outcome.error,
            "error_category": outcome.error_category,
            "started_at": NOW.isoformat(),
            "completed_at": NOW.isoformat(),
        }

    def record_source_poll_source(
        self,
        source,
        outcome,
        *,
        context,
        started_at,
        completed_at,
        failure_category="",
    ):
        if failure_category:
            self.mark_failure(source["id"], failure_category)
        self._record_receipt(context.run_id, outcome, context)

    def commit_source_poll(
        self,
        source,
        items,
        *,
        context,
        max_new_jobs,
        cost_blocked,
        latest,
        omitted_items,
        started_at,
    ):
        upserts = 0
        jobs = 0
        duplicates = 0
        blocked = 0
        latest_value = latest
        for item in items:
            key = f"{item.source_id}:{item.platform}:{item.external_id}:{item.title}"
            fallback = f"content:{key}"
            content_id = self.resolve_content_id(item.platform, item.external_id, fallback)
            self.upsert_content(item, content_id)
            upserts += 1
            if item.published_at > latest_value:
                latest_value = item.published_at
            if cost_blocked or jobs >= max_new_jobs:
                blocked += 1
                continue
            from dichiarazioni_pubbliche.scheduler import plan_initial_job
            from dichiarazioni_pubbliche.scheduler_daemon import scheduler_ingest_plan
            if self.enqueue(plan_initial_job(item, scheduler_ingest_plan(item)), content_id):
                jobs += 1
            else:
                duplicates += 1
        self.mark_success(source["id"], latest_value)
        outcome = PollOutcome(
            source["id"],
            "BUDGET_BLOCKED" if blocked else "HEALTHY",
            discovered=len(items),
            content_upserts=upserts,
            jobs_enqueued=jobs,
            duplicate_jobs=duplicates,
            budget_blocked=blocked,
            omitted_items=omitted_items,
            error_category="BUDGET_BLOCKED" if blocked else None,
            receipt_id=f"source-poll-source:{context.run_id}:{source['id']}",
        )
        self._record_receipt(context.run_id, outcome, context)
        return {
            "content_upserts": upserts,
            "jobs_enqueued": jobs,
            "duplicate_jobs": duplicates,
            "budget_blocked": blocked,
            "latest": latest_value,
            "health_committed": True,
        }

    def complete_source_poll_run(self, **values):
        self.source_poll_runs[values["run_id"]].update(
            {
                "status": values["status"],
                "source_count": values["source_count"],
                "discovered": values["discovered"],
                "content_upserts": values["content_upserts"],
                "jobs_enqueued": values["jobs_enqueued"],
                "duplicate_jobs": values["duplicate_jobs"],
                "budget_blocked": values["budget_blocked"],
                "omitted_items": values["omitted_items"],
                "error_category": values["error_category"] or None,
                "completed_at": values["completed_at"].isoformat(),
            }
        )


SOURCE = {
    "id": "youtube-pulp-podcast",
    "name": "Pulp Podcast",
    "kind": "youtube_channel",
    "poll_minutes": 30,
}


class SchedulerDaemonTests(unittest.TestCase):
    def test_source_due_honors_poll_interval(self):
        health = SourceHealthState(NOW - timedelta(minutes=29), 0)
        self.assertFalse(source_due(health, poll_minutes=30, now=NOW))
        health = SourceHealthState(NOW - timedelta(minutes=30), 0)
        self.assertTrue(source_due(health, poll_minutes=30, now=NOW))

    def test_failures_apply_exponential_backoff(self):
        health = SourceHealthState(NOW - timedelta(minutes=119), 2)
        self.assertFalse(source_due(health, poll_minutes=30, now=NOW))
        health = SourceHealthState(NOW - timedelta(minutes=120), 2)
        self.assertTrue(source_due(health, poll_minutes=30, now=NOW))

    def test_scheduler_never_downloads_or_probes_media(self):
        self.assertEqual(
            scheduler_ingest_plan(content("youtube"))["action"],
            "PROBE_PLATFORM_TRANSCRIPT",
        )
        self.assertFalse(scheduler_ingest_plan(content("youtube"))["download_media"])

    def test_poll_is_idempotent_at_queue_boundary(self):
        store = FakeStore()
        budget = RuntimeBudget()
        discover = lambda source: [content()]
        first = poll_source(
            SOURCE, store, now=NOW, budget=budget, force=True, discover=discover
        )
        second = poll_source(
            SOURCE, store, now=NOW, budget=budget, force=True, discover=discover
        )
        self.assertEqual(first.jobs_enqueued, 1)
        self.assertEqual(second.jobs_enqueued, 0)
        self.assertEqual(second.duplicate_jobs, 1)
        self.assertEqual(store.content_ids[0], store.content_ids[1])

    def test_daily_budget_blocks_enqueue_but_keeps_discovery(self):
        store = FakeStore()
        store.global_cost = 5.0
        outcome = poll_source(
            SOURCE,
            store,
            now=NOW,
            budget=RuntimeBudget(max_cost_usd_per_day=5.0),
            force=True,
            discover=lambda source: [content()],
        )
        self.assertEqual(outcome.content_upserts, 1)
        self.assertEqual(outcome.jobs_enqueued, 0)
        self.assertEqual(outcome.budget_blocked, 1)

    def test_existing_locator_wins_when_feed_metadata_changes(self):
        store = FakeStore()
        first = content()
        changed = DiscoveredContent(
            source_id=first.source_id,
            platform=first.platform,
            external_id=first.external_id,
            title="Titolo corretto dopo la pubblicazione",
            canonical_url=first.canonical_url,
            published_at="2026-09-22T11:00:00+00:00",
            author=first.author,
        )
        poll_source(
            SOURCE,
            store,
            now=NOW,
            budget=RuntimeBudget(),
            force=True,
            discover=lambda source: [first],
        )
        original_id = store.content_ids[-1]
        poll_source(
            SOURCE,
            store,
            now=NOW,
            budget=RuntimeBudget(),
            force=True,
            discover=lambda source: [changed],
        )
        self.assertEqual(store.content_ids[-1], original_id)

    def test_source_failure_is_recorded_without_crashing_other_sources(self):
        store = FakeStore()

        def fail(source):
            raise TimeoutError("feed timed out")

        outcome = poll_source(
            SOURCE,
            store,
            now=NOW,
            budget=RuntimeBudget(),
            force=True,
            discover=fail,
        )
        self.assertEqual(outcome.status, "FAILED")
        self.assertEqual(len(store.failures), 1)


class FullSourceSchedulerTests(unittest.TestCase):
    def test_all_adapter_families_are_dispatchable(self):
        from dichiarazioni_pubbliche.scheduler_daemon import SUPPORTED_SOURCE_KINDS

        self.assertEqual(
            set(SUPPORTED_SOURCE_KINDS),
            {"youtube_channel", "podcast_rss", "public_creator_accounts"},
        )

    def setUp(self):
        self.sources = [
            dict(SOURCE),
            {
                "id": "youtube-second",
                "name": "Second",
                "kind": "youtube_channel",
                "poll_minutes": 30,
            },
            {
                "id": "unsupported-source",
                "name": "Unsupported",
                "kind": "web_crawler",
            },
        ]
        self.tempdir = tempfile.TemporaryDirectory()
        self.registry_path = Path(self.tempdir.name) / "registry.json"
        self.write_registry(self.sources)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_registry(self, sources):
        self.registry_path.write_text(
            json.dumps({"schema_version": 1, "sources": sources})
        )

    @staticmethod
    def item(source_id, index):
        return DiscoveredContent(
            source_id=source_id,
            platform="youtube",
            external_id=f"{source_id}-item-{index}",
            title=f"Episode {index}",
            canonical_url=f"https://example.test/{source_id}/{index}",
            published_at="2026-09-25T00:00:00+00:00",
        )

    def run_full(self, store, discover, *, now=NOW, budget=None, force=True):
        return run_registry(
            self.registry_path,
            store,
            source_id=None,
            force=force,
            limit=20,
            budget=budget or RuntimeBudget(),
            now=now,
            full_source=True,
            discover=discover,
        )

    def test_full_source_covers_registry_and_replay_is_a_noop(self):
        store = FakeStore()
        calls = []

        def discover(source):
            calls.append(source["id"])
            return [self.item(source["id"], 1)]

        first = self.run_full(store, discover)
        self.assertEqual(first.status, "COMPLETED")
        self.assertEqual(len(first), 3)
        self.assertEqual(
            {row.source_id: row.status for row in first},
            {
                "youtube-pulp-podcast": "HEALTHY",
                "youtube-second": "HEALTHY",
                "unsupported-source": "SKIPPED_UNSUPPORTED",
            },
        )
        self.assertEqual(calls, ["youtube-pulp-podcast", "youtube-second"])
        first_job_count = len(store.jobs)

        second = self.run_full(
            store,
            lambda source: (_ for _ in ()).throw(
                AssertionError("completed replay performed discovery")
            ),
        )
        self.assertEqual(second.status, "SKIPPED_ALREADY_COMPLETED")
        self.assertEqual(len(second), len(first))
        self.assertEqual(
            {row.source_id for row in second},
            {row.source_id for row in first},
        )
        self.assertEqual(len(store.jobs), first_job_count)
        self.assertEqual(
            set(store.source_poll_runs[first.run_id]["sources"]),
            {row.source_id for row in first},
        )
        child = store.get_source_poll_source(first.run_id, "youtube-pulp-podcast")
        self.assertEqual(child["mode"], "full-source")
        self.assertEqual(child["run_date"], utc_run_date(NOW))
        self.assertEqual(child["effective_config_hash"], first.effective_config_hash)
        self.assertTrue(child["receipt_id"])

    def test_changed_registry_policy_creates_a_distinct_run(self):
        store = FakeStore()
        first = self.run_full(
            store,
            lambda source: [self.item(source["id"], 1)]
            if source["id"] != "unsupported-source"
            else [],
        )
        self.sources[0]["poll_minutes"] = 31
        self.write_registry(self.sources)
        second = self.run_full(
            store,
            lambda source: [self.item(source["id"], 1)]
            if source["id"] != "unsupported-source"
            else [],
        )
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertNotEqual(
            first.effective_config_hash,
            second.effective_config_hash,
        )
        self.assertEqual(canonical_registry_policy_hash({"sources": []}), canonical_registry_policy_hash({"sources": []}))

    def test_full_source_isolates_failure_and_records_sanitized_error(self):
        store = FakeStore()

        def discover(source):
            if source["id"] == "youtube-pulp-podcast":
                raise ValueError("malformed feed with secret=do-not-store")
            if source["id"] == "unsupported-source":
                raise AssertionError("unsupported source was discovered")
            return [self.item(source["id"], 1)]

        result = self.run_full(store, discover)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result[0].status, "FAILED")
        self.assertEqual(result[0].error_category, "MALFORMED_RESPONSE")
        self.assertNotIn("secret", result[0].error)
        self.assertEqual(result[1].status, "HEALTHY")
        self.assertIn("youtube-pulp-podcast", store._source_poll_runs[result.run_id]["sources"])

    def test_full_source_cap_is_shared_across_sources(self):
        self.sources = [
            {
                "id": "source-one",
                "name": "One",
                "kind": "youtube_channel",
                "poll_minutes": 30,
            },
            {
                "id": "source-two",
                "name": "Two",
                "kind": "youtube_channel",
                "poll_minutes": 30,
            },
        ]
        self.write_registry(self.sources)
        store = FakeStore()
        result = self.run_full(
            store,
            lambda source: [self.item(source["id"], index) for index in range(15)],
            budget=RuntimeBudget(max_new_jobs_per_run=20),
        )
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(sum(row.jobs_enqueued for row in result), 20)
        self.assertEqual(sum(row.budget_blocked for row in result), 10)
        self.assertEqual(sum(row.discovered for row in result), 30)
        self.assertEqual(len(store.jobs), 20)

    def test_full_source_hard_cap_cannot_be_raised_by_configuration(self):
        store = FakeStore()
        result = self.run_full(
            store,
            lambda source: [self.item(source["id"], index) for index in range(25)],
            budget=RuntimeBudget(max_new_jobs_per_run=100),
        )
        self.assertEqual(sum(row.jobs_enqueued for row in result), 20)
        self.assertEqual(sum(row.omitted_items for row in result), 10)
        self.assertEqual(len(store.jobs), 20)

    def test_changed_identity_obeys_per_source_daily_limit(self):
        store = FakeStore()
        calls = []
        first = self.run_full(
            store,
            lambda source: calls.append(source["id"]) or [self.item(source["id"], 1)]
            if source["id"] != "unsupported-source"
            else [],
            force=False,
        )
        self.assertEqual(first.status, "COMPLETED")
        self.sources[0]["poll_minutes"] = 31
        self.write_registry(self.sources)
        second = self.run_full(
            store,
            lambda source: calls.append(source["id"]) or [],
            force=False,
        )
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(second[0].status, "SKIPPED_DAILY_LIMIT")
        self.assertEqual(calls, ["youtube-pulp-podcast", "youtube-second"])

    def test_due_backoff_is_preserved_in_full_source_mode(self):
        store = FakeStore()
        store.health_state = SourceHealthState(NOW - timedelta(minutes=1), 0)
        result = self.run_full(
            store,
            lambda source: (_ for _ in ()).throw(
                AssertionError("not-due source was discovered")
            ),
            force=False,
        )
        self.assertEqual(result[0].status, "SKIPPED_NOT_DUE")
        self.assertEqual(result[0].error_category, "NOT_DUE")

    def test_daily_units_and_receipt_schema_are_present(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.service").read_text()
        timer = (root / "deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.timer").read_text()
        schema = (root / "db/schema.v1.sql").read_text()
        migration = (
            root / "db/migrations/20260925-add-source-poll-run-receipts.sql"
        ).read_text()
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


if __name__ == "__main__":
    unittest.main()

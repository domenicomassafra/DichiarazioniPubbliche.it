import sys
import unittest
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_discovery import (  # noqa: E402
    ConfiguredRegistryDiscoveryAdapter,
    DiscoveryAdapterError,
    DiscoveryAdapterRequest,
    DiscoveryAdapterResult,
    DiscoveryHitCandidate,
    DiscoveryManifestError,
    canonicalize_discovery_url,
    load_discovery_manifest,
    run_discovery_manifest,
)


def manifest_payload(**limit_overrides):
    limits = {
        "max_results": 4,
        "max_results_per_host": 2,
        "cost_cap_usd": "1.000000",
    }
    limits.update(limit_overrides)
    return {
        "schema_version": 1,
        "id": "manifest:test:v1",
        "collection_id": "collection:test",
        "date_window": {
            "from": "2025-01-01T00:00:00+00:00",
            "to": "2026-12-31T23:59:59+00:00",
        },
        "limits": limits,
        "seeds": [{"kind": "term", "value": "garlasco"}],
        "source_families": ["web", "public_creator_accounts"],
        "queries": [
            {
                "id": "query:test:1",
                "query": "Garlasco DNA",
                "source_families": ["web"],
                "adapter_ids": ["search-a"],
                "max_results": 4,
            }
        ],
        "metadata": {"purpose": "test"},
    }


@dataclass
class StaticAdapter:
    adapter_id: str
    hits: tuple[DiscoveryHitCandidate, ...] = ()
    status: str = "OK"
    upper: Decimal = Decimal("0")
    cost: Decimal = Decimal("0")
    error_category: str | None = None
    provider_receipt: dict | None = None
    adapter_version: str = "static-test-v1"
    supported_families: frozenset[str] = frozenset({"web"})
    calls: int = 0
    require_manifest_persisted: bool = False
    store: object | None = None

    def cost_upper_bound_usd(self, request: DiscoveryAdapterRequest) -> Decimal:
        return self.upper

    def discover(self, request: DiscoveryAdapterRequest) -> DiscoveryAdapterResult:
        self.calls += 1
        if self.require_manifest_persisted and not getattr(self.store, "persisted", False):
            raise AssertionError("adapter called before manifest persisted")
        if self.status == "RAISE":
            raise DiscoveryAdapterError(self.error_category or "UPSTREAM_FAILURE")
        return DiscoveryAdapterResult(
            hits=self.hits,
            status=self.status,
            cost_usd=self.cost,
            error_category=self.error_category,
            provider_receipt=self.provider_receipt or {"request_id": f"req-{self.calls}"},
        )


class FakeStore:
    def __init__(self, existing_urls=()):
        self.persisted = False
        self.manifests = {}
        self.runs = {}
        self.attempts = {}
        self.hits = []
        self.content_urls = set(existing_urls)
        self.calls = []

    def persist_manifest(self, manifest):
        self.calls.append(("persist_manifest", manifest.id))
        self.persisted = True
        previous = self.manifests.get(manifest.id)
        if previous and previous.manifest_sha256 != manifest.manifest_sha256:
            raise RuntimeError("DISCOVERY_MANIFEST_CONFLICT")
        self.manifests[manifest.id] = manifest
        return "PERSISTED"

    def start_run(self, manifest, run_id):
        self.calls.append(("start_run", run_id))
        if run_id in self.runs:
            row = self.runs[run_id]
            return {
                "state": "EXISTING",
                "status": row["status"],
                "manifest_id": manifest.id,
                "manifest_sha256": manifest.manifest_sha256,
            }
        self.runs[run_id] = {
            "run_id": run_id,
            "manifest_id": manifest.id,
            "manifest_sha256": manifest.manifest_sha256,
            "status": "RUNNING",
        }
        return {
            "state": "STARTED",
            "status": "RUNNING",
            "manifest_id": manifest.id,
            "manifest_sha256": manifest.manifest_sha256,
        }

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def reconcile_running_attempts(self, run_id):
        reconciled = 0
        for (rid, _, _), row in self.attempts.items():
            if rid == run_id and row["status"] == "RUNNING":
                row.update(
                    status="BLOCKED",
                    error_category="ATTEMPT_RECONCILIATION_REQUIRED",
                )
                reconciled += 1
        return reconciled

    def resume_state(self, run_id):
        accepted = [
            row
            for row in self.hits
            if row["run_id"] == run_id
            and row["disposition"] in {"NEW_CONTENT", "EXISTING_CONTENT"}
        ]
        host_counts = {}
        query_counts = {}
        for row in accepted:
            host_counts[row["host"]] = host_counts.get(row["host"], 0) + 1
            query_counts[row["query_id"]] = query_counts.get(row["query_id"], 0) + 1
        cost = sum(
            (
                Decimal(str(row.get("cost_usd") or 0))
                for (rid, _, _), row in self.attempts.items()
                if rid == run_id and row["status"] != "RUNNING"
            ),
            Decimal("0"),
        )
        return {
            "accepted_urls": [row["canonical_url"] for row in accepted],
            "host_counts": host_counts,
            "query_counts": query_counts,
            "accepted_total": len(accepted),
            "cost_usd": str(cost),
        }

    def start_attempt(self, **kwargs):
        self.calls.append(("start_attempt", kwargs["attempt_id"]))
        key = (kwargs["run_id"], kwargs["query_id"], kwargs["adapter_id"])
        if key in self.attempts:
            row = self.attempts[key]
            return {"state": "EXISTING", **row}
        row = {
            "id": kwargs["attempt_id"],
            "status": "RUNNING",
            "cost_usd": Decimal("0"),
            "raw_hits": 0,
            "accepted_hits": 0,
            "rejected_hits": 0,
            "omitted_hits": 0,
            "error_category": None,
            "provider_receipt": {},
        }
        self.attempts[key] = row
        return {"state": "STARTED", **row}

    def finish_attempt(self, **kwargs):
        self.calls.append(("finish_attempt", kwargs["attempt_id"], kwargs["status"]))
        for key, row in self.attempts.items():
            if row["id"] == kwargs["attempt_id"]:
                row.update(kwargs)
                return kwargs["status"]
        raise AssertionError("attempt not found")

    def record_hit(self, **kwargs):
        candidate = kwargs["candidate"]
        canonical_url, host = canonicalize_discovery_url(candidate.canonical_url)
        disposition = kwargs.get("policy_disposition") or (
            "EXISTING_CONTENT" if canonical_url in self.content_urls else "NEW_CONTENT"
        )
        if disposition == "NEW_CONTENT":
            self.content_urls.add(canonical_url)
        row = {
            "run_id": kwargs["run_id"],
            "query_id": kwargs["query"].id,
            "ordinal": kwargs["ordinal"],
            "canonical_url": canonical_url,
            "host": host,
            "disposition": disposition,
            "reason_code": kwargs.get("reason_code") or None,
        }
        self.hits.append(row)
        return {"state": "INSERTED", "disposition": disposition, "content_id": canonical_url}

    def complete_run(self, run_id):
        attempts = [row for (rid, _, _), row in self.attempts.items() if rid == run_id]
        healthy = sum(row["status"] == "HEALTHY" for row in attempts)
        blocked = sum(row["status"] in {"BLOCKED", "BUDGET_BLOCKED"} for row in attempts)
        failed = sum(row["status"] == "FAILED" for row in attempts)
        if not attempts:
            status = "BLOCKED"
        elif healthy == len(attempts):
            status = "COMPLETED"
        elif healthy:
            status = "PARTIAL"
        elif failed and not blocked:
            status = "FAILED"
        elif blocked and not failed:
            status = "BLOCKED"
        else:
            status = "PARTIAL"
        run_hits = [h for h in self.hits if h["run_id"] == run_id]
        accepted = [h for h in run_hits if h["disposition"] in {"NEW_CONTENT", "EXISTING_CONTENT"}]
        from dichiarazioni_pubbliche.research_discovery import DiscoveryRunReceipt
        receipt = DiscoveryRunReceipt(
            run_id=run_id,
            manifest_id=self.runs[run_id]["manifest_id"],
            manifest_sha256=self.runs[run_id]["manifest_sha256"],
            status=status,
            attempt_count=len(attempts),
            healthy_attempts=healthy,
            blocked_attempts=blocked,
            failed_attempts=failed,
            raw_hits=sum(int(row.get("raw_hits") or 0) for row in attempts),
            accepted_hits=len(accepted),
            new_content=sum(h["disposition"] == "NEW_CONTENT" for h in accepted),
            existing_content=sum(h["disposition"] == "EXISTING_CONTENT" for h in accepted),
            rejected_hits=len(run_hits) - len(accepted),
            cost_usd=sum((Decimal(str(row.get("cost_usd") or 0)) for row in attempts), Decimal("0")),
            error_category=None if status == "COMPLETED" else f"DISCOVERY_{status}",
        )
        self.runs[run_id] = {
            **self.runs[run_id],
            **receipt.__dict__,
            "cost_usd": str(receipt.cost_usd),
        }
        return receipt


class ResearchDiscoveryTests(unittest.TestCase):
    def test_manifest_is_versioned_hashed_and_bounded(self):
        manifest = load_discovery_manifest(manifest_payload())
        self.assertEqual(len(manifest.manifest_sha256), 64)
        self.assertEqual(manifest.max_results, 4)
        self.assertEqual(manifest.max_results_per_host, 2)
        self.assertEqual(manifest.queries[0].ordinal, 0)
        self.assertEqual(manifest.queries[0].adapter_ids, ("search-a",))
        self.assertEqual(
            manifest.manifest_sha256,
            load_discovery_manifest(manifest_payload()).manifest_sha256,
        )
        self.assertEqual(manifest.coverage_need_ids, ())

    def test_manifest_hash_and_contract_include_optional_coverage_needs(self):
        payload = manifest_payload()
        payload["coverage_need_ids"] = ["coverage-need:a", "coverage-need:b"]
        manifest = load_discovery_manifest(payload)
        self.assertEqual(
            manifest.coverage_need_ids,
            ("coverage-need:a", "coverage-need:b"),
        )
        self.assertNotEqual(
            manifest.manifest_sha256,
            load_discovery_manifest(manifest_payload()).manifest_sha256,
        )

    def test_manifest_rejects_unbounded_or_out_of_scope_query(self):
        with self.assertRaisesRegex(DiscoveryManifestError, "MAX_RESULTS_OUT_OF_RANGE"):
            load_discovery_manifest(manifest_payload(max_results=201))
        with self.assertRaisesRegex(DiscoveryManifestError, "MAX_RESULTS_INVALID"):
            load_discovery_manifest(manifest_payload(max_results="not-a-number"))
        with self.assertRaisesRegex(DiscoveryManifestError, "MAX_RESULTS_INVALID"):
            load_discovery_manifest(manifest_payload(max_results=1.5))
        payload = manifest_payload()
        payload["queries"][0]["source_families"] = ["not-in-manifest"]
        with self.assertRaisesRegex(DiscoveryManifestError, "FAMILY_OUTSIDE_MANIFEST"):
            load_discovery_manifest(payload)

    def test_url_canonicalization_is_https_fragment_free_and_refuses_private_literal(self):
        url, host = canonicalize_discovery_url("https://Example.COM:443/path?q=1#frag")
        self.assertEqual(url, "https://example.com/path?q=1")
        self.assertEqual(host, "example.com")
        with self.assertRaisesRegex(DiscoveryManifestError, "HTTPS_REQUIRED"):
            canonicalize_discovery_url("http://example.com/")
        with self.assertRaisesRegex(DiscoveryManifestError, "NONPUBLIC_IP"):
            canonicalize_discovery_url("https://127.0.0.1/test")
        with self.assertRaisesRegex(DiscoveryManifestError, "LOCAL_HOSTNAME"):
            canonicalize_discovery_url("https://service.internal/test")

    def test_manifest_is_persisted_before_adapter_execution(self):
        manifest = load_discovery_manifest(manifest_payload())
        store = FakeStore()
        adapter = StaticAdapter(
            "search-a",
            hits=(DiscoveryHitCandidate("https://one.example/a", "Garlasco DNA", "2026-01-01T00:00:00Z", "web"),),
            require_manifest_persisted=True,
            store=store,
        )
        receipt = run_discovery_manifest(manifest, store, {"search-a": adapter}, run_id="run:1")
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(store.calls[0], ("persist_manifest", manifest.id))
        self.assertEqual(adapter.calls, 1)

    def test_same_manifest_separate_runs_reuse_content_identity(self):
        manifest = load_discovery_manifest(manifest_payload())
        store = FakeStore()
        hit = DiscoveryHitCandidate("https://one.example/a", "Garlasco DNA", "2026-01-01T00:00:00Z", "web")
        adapter = StaticAdapter("search-a", hits=(hit,))
        first = run_discovery_manifest(manifest, store, {"search-a": adapter}, run_id="run:first")
        second = run_discovery_manifest(manifest, store, {"search-a": adapter}, run_id="run:second")
        self.assertEqual(first.new_content, 1)
        self.assertEqual(second.existing_content, 1)
        self.assertEqual(len(store.runs), 2)
        self.assertEqual(len(store.content_urls), 1)

    def test_existing_url_is_marked_existing_not_duplicated(self):
        manifest = load_discovery_manifest(manifest_payload())
        store = FakeStore(existing_urls={"https://one.example/a"})
        adapter = StaticAdapter(
            "search-a",
            hits=(DiscoveryHitCandidate("https://one.example/a", "Garlasco", "2026-01-01T00:00:00Z", "web"),),
        )
        receipt = run_discovery_manifest(manifest, store, {"search-a": adapter}, run_id="run:existing")
        self.assertEqual(receipt.new_content, 0)
        self.assertEqual(receipt.existing_content, 1)
        self.assertEqual(store.hits[0]["disposition"], "EXISTING_CONTENT")

    def test_host_and_total_limits_persist_rejected_dispositions(self):
        payload = manifest_payload(max_results=2, max_results_per_host=1)
        payload["queries"][0]["max_results"] = 2
        manifest = load_discovery_manifest(payload)
        hits = (
            DiscoveryHitCandidate("https://a.example/1", "Garlasco 1", "2026-01-01T00:00:00Z", "web"),
            DiscoveryHitCandidate("https://a.example/2", "Garlasco 2", "2026-01-02T00:00:00Z", "web"),
            DiscoveryHitCandidate("https://b.example/1", "Garlasco 3", "2026-01-03T00:00:00Z", "web"),
            DiscoveryHitCandidate("https://c.example/1", "Garlasco 4", "2026-01-04T00:00:00Z", "web"),
        )
        store = FakeStore()
        receipt = run_discovery_manifest(manifest, store, {"search-a": StaticAdapter("search-a", hits=hits)}, run_id="run:limits")
        self.assertEqual(receipt.accepted_hits, 2)
        self.assertEqual(receipt.rejected_hits, 2)
        dispositions = [row["disposition"] for row in store.hits]
        self.assertIn("HOST_LIMIT", dispositions)
        self.assertIn("RESULT_LIMIT", dispositions)

    def test_duplicate_within_run_does_not_consume_second_result_slot(self):
        manifest = load_discovery_manifest(manifest_payload())
        hits = (
            DiscoveryHitCandidate("https://a.example/1", "Garlasco", "2026-01-01T00:00:00Z", "web"),
            DiscoveryHitCandidate("https://a.example/1#copy", "Garlasco", "2026-01-01T00:00:00Z", "web"),
            DiscoveryHitCandidate("https://b.example/2", "Garlasco", "2026-01-02T00:00:00Z", "web"),
        )
        store = FakeStore()
        receipt = run_discovery_manifest(manifest, store, {"search-a": StaticAdapter("search-a", hits=hits)}, run_id="run:dupe")
        self.assertEqual(receipt.accepted_hits, 2)
        self.assertEqual(store.hits[1]["disposition"], "DUPLICATE_WITHIN_RUN")

    def test_date_window_rejects_unknown_and_outside_dates(self):
        manifest = load_discovery_manifest(manifest_payload())
        hits = (
            DiscoveryHitCandidate("https://a.example/no-date", "Garlasco", None, "web"),
            DiscoveryHitCandidate("https://b.example/old", "Garlasco", "2024-01-01T00:00:00Z", "web"),
            DiscoveryHitCandidate("https://c.example/in", "Garlasco", "2026-01-01T00:00:00Z", "web"),
        )
        store = FakeStore()
        receipt = run_discovery_manifest(manifest, store, {"search-a": StaticAdapter("search-a", hits=hits)}, run_id="run:dates")
        self.assertEqual(receipt.accepted_hits, 1)
        self.assertEqual([h["disposition"] for h in store.hits].count("OUTSIDE_DATE_WINDOW"), 2)

    def test_precall_cost_cap_blocks_adapter_without_calling_it(self):
        payload = manifest_payload(cost_cap_usd="0.500000")
        manifest = load_discovery_manifest(payload)
        adapter = StaticAdapter("search-a", upper=Decimal("0.600000"))
        receipt = run_discovery_manifest(manifest, FakeStore(), {"search-a": adapter}, run_id="run:budget")
        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(receipt.blocked_attempts, 1)
        self.assertEqual(adapter.calls, 0)

    def test_provider_failure_is_failed_not_empty_success(self):
        manifest = load_discovery_manifest(manifest_payload())
        adapter = StaticAdapter("search-a", status="RAISE", error_category="RATE_LIMITED")
        receipt = run_discovery_manifest(manifest, FakeStore(), {"search-a": adapter}, run_id="run:failed")
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failed_attempts, 1)
        self.assertEqual(receipt.raw_hits, 0)

    def test_unknown_cost_after_adapter_exception_blocks_later_provider_calls(self):
        payload = manifest_payload()
        payload["queries"][0]["adapter_ids"] = ["search-a", "search-b"]
        manifest = load_discovery_manifest(payload)
        failing = StaticAdapter("search-a", status="RAISE", error_category="RATE_LIMITED")
        later = StaticAdapter(
            "search-b",
            hits=(
                DiscoveryHitCandidate(
                    "https://later.example/1",
                    "Garlasco",
                    "2026-01-01T00:00:00Z",
                    "web",
                ),
            ),
        )
        store = FakeStore()
        receipt = run_discovery_manifest(
            manifest,
            store,
            {"search-a": failing, "search-b": later},
            run_id="run:cost-uncertain",
        )
        self.assertEqual(receipt.status, "PARTIAL")
        self.assertEqual(receipt.failed_attempts, 1)
        self.assertEqual(receipt.blocked_attempts, 1)
        self.assertEqual(failing.calls, 1)
        self.assertEqual(later.calls, 0)
        statuses = {
            key[2]: (row["status"], row.get("error_category"))
            for key, row in store.attempts.items()
            if key[0] == "run:cost-uncertain"
        }
        self.assertEqual(statuses["search-b"], ("BUDGET_BLOCKED", "COST_STATE_UNCERTAIN"))

    def test_one_healthy_and_one_missing_adapter_is_partial(self):
        payload = manifest_payload()
        payload["queries"][0]["adapter_ids"] = ["search-a", "missing-search"]
        manifest = load_discovery_manifest(payload)
        adapter = StaticAdapter(
            "search-a",
            hits=(DiscoveryHitCandidate("https://a.example/1", "Garlasco", "2026-01-01T00:00:00Z", "web"),),
        )
        receipt = run_discovery_manifest(manifest, FakeStore(), {"search-a": adapter}, run_id="run:partial")
        self.assertEqual(receipt.status, "PARTIAL")
        self.assertEqual(receipt.healthy_attempts, 1)
        self.assertEqual(receipt.blocked_attempts, 1)

    def test_sensitive_provider_receipt_fails_closed(self):
        manifest = load_discovery_manifest(manifest_payload())
        adapter = StaticAdapter(
            "search-a",
            hits=(DiscoveryHitCandidate("https://a.example/1", "Garlasco", "2026-01-01T00:00:00Z", "web"),),
            provider_receipt={"access_token": "should-never-persist"},
        )
        store = FakeStore()
        receipt = run_discovery_manifest(manifest, store, {"search-a": adapter}, run_id="run:secret")
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.accepted_hits, 0)
        self.assertFalse(store.hits)

    def test_raw_body_provider_receipt_fails_closed(self):
        manifest = load_discovery_manifest(manifest_payload())
        adapter = StaticAdapter(
            "search-a",
            hits=(
                DiscoveryHitCandidate(
                    "https://a.example/1",
                    "Garlasco",
                    "2026-01-01T00:00:00Z",
                    "web",
                ),
            ),
            provider_receipt={"raw_response": "must-never-persist"},
        )
        store = FakeStore()
        receipt = run_discovery_manifest(
            manifest, store, {"search-a": adapter}, run_id="run:raw-receipt"
        )
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.accepted_hits, 0)
        self.assertFalse(store.hits)

    def test_adapter_family_mismatch_blocks_without_provider_call(self):
        manifest = load_discovery_manifest(manifest_payload())
        adapter = StaticAdapter("search-a")
        adapter.supported_families = frozenset({"podcast_rss"})
        store = FakeStore()
        receipt = run_discovery_manifest(
            manifest, store, {"search-a": adapter}, run_id="run:family-mismatch"
        )
        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(receipt.blocked_attempts, 1)
        self.assertEqual(adapter.calls, 0)

    def test_adapter_result_bound_exceeded_fails_before_hit_persistence(self):
        manifest = load_discovery_manifest(manifest_payload())
        hits = tuple(
            DiscoveryHitCandidate(
                f"https://bulk.example/{index}",
                "Garlasco",
                "2026-01-01T00:00:00Z",
                "web",
            )
            for index in range(101)
        )
        adapter = StaticAdapter("search-a", hits=hits)
        store = FakeStore()
        receipt = run_discovery_manifest(
            manifest, store, {"search-a": adapter}, run_id="run:adapter-overflow"
        )
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failed_attempts, 1)
        self.assertFalse(store.hits)
        attempt = next(iter(store.attempts.values()))
        self.assertEqual(attempt["error_category"], "ADAPTER_RESULT_BOUND_EXCEEDED")

    def test_invalid_timestamp_is_rejected_without_crashing_attempt(self):
        manifest = load_discovery_manifest(manifest_payload())
        adapter = StaticAdapter(
            "search-a",
            hits=(
                DiscoveryHitCandidate(
                    "https://a.example/1",
                    "Garlasco",
                    "not-a-date",
                    "web",
                ),
            ),
        )
        store = FakeStore()
        receipt = run_discovery_manifest(
            manifest,
            store,
            {"search-a": adapter},
            run_id="run:bad-date",
        )
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(receipt.accepted_hits, 0)
        self.assertEqual(receipt.rejected_hits, 1)
        self.assertEqual(store.hits[0]["disposition"], "REJECTED_POLICY")
        self.assertEqual(store.hits[0]["reason_code"], "PUBLISHED_AT_INVALID")

    def test_raw_body_or_secret_hit_metadata_is_rejected_and_not_retained(self):
        manifest = load_discovery_manifest(manifest_payload())
        adapter = StaticAdapter(
            "search-a",
            hits=(
                DiscoveryHitCandidate(
                    "https://a.example/1",
                    "Garlasco",
                    "2026-01-01T00:00:00Z",
                    "web",
                    metadata={"raw_body": "must not persist"},
                ),
                DiscoveryHitCandidate(
                    "https://b.example/1",
                    "Garlasco",
                    "2026-01-02T00:00:00Z",
                    "web",
                    metadata={"api_key": "must not persist"},
                ),
            ),
        )
        store = FakeStore()
        receipt = run_discovery_manifest(
            manifest,
            store,
            {"search-a": adapter},
            run_id="run:bad-metadata",
        )
        self.assertEqual(receipt.accepted_hits, 0)
        self.assertEqual(receipt.rejected_hits, 2)
        self.assertEqual(
            [row["reason_code"] for row in store.hits],
            ["HIT_METADATA_INVALID", "HIT_METADATA_INVALID"],
        )

    def test_existing_running_attempt_is_reconciled_without_recalling_adapter(self):
        manifest = load_discovery_manifest(manifest_payload())
        store = FakeStore()
        adapter = StaticAdapter(
            "search-a",
            hits=(
                DiscoveryHitCandidate(
                    "https://a.example/1",
                    "Garlasco",
                    "2026-01-01T00:00:00Z",
                    "web",
                ),
            ),
        )
        store.persist_manifest(manifest)
        store.start_run(manifest, "run:crash")
        store.start_attempt(
            attempt_id="attempt:crash",
            run_id="run:crash",
            query_id="query:test:1",
            adapter_id="search-a",
            adapter_version="static-test-v1",
            cost_upper_bound_usd=Decimal("0"),
        )

        receipt = run_discovery_manifest(
            manifest,
            store,
            {"search-a": adapter},
            run_id="run:crash",
        )

        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(receipt.blocked_attempts, 1)
        self.assertEqual(adapter.calls, 0)
        self.assertFalse(store.hits)

    def test_resume_state_preserves_already_consumed_host_and_result_limits(self):
        payload = manifest_payload(max_results=2, max_results_per_host=1)
        payload["queries"][0]["max_results"] = 2
        manifest = load_discovery_manifest(payload)
        store = FakeStore()
        adapter = StaticAdapter(
            "search-a",
            hits=(
                DiscoveryHitCandidate(
                    "https://same.example/a",
                    "Garlasco",
                    "2026-01-01T00:00:00Z",
                    "web",
                ),
            ),
        )
        first = run_discovery_manifest(
            manifest,
            store,
            {"search-a": adapter},
            run_id="run:resume-seed",
        )
        self.assertEqual(first.accepted_hits, 1)

        # Simulate a resumable run with one completed attempt/hit and a second query
        # still eligible. The resumed query must inherit the consumed host/result budget.
        payload["id"] = "manifest:test:resume:v1"
        payload["queries"].append(
            {
                "id": "query:test:2",
                "query": "Garlasco followup",
                "source_families": ["web"],
                "adapter_ids": ["search-b"],
                "max_results": 2,
            }
        )
        resume_manifest = load_discovery_manifest(payload)
        resume_store = FakeStore()
        resume_store.persist_manifest(resume_manifest)
        resume_store.start_run(resume_manifest, "run:resume")
        resume_store.content_urls.add("https://same.example/a")
        resume_store.hits.append(
            {
                "run_id": "run:resume",
                "query_id": "query:test:1",
                "ordinal": 0,
                "canonical_url": "https://same.example/a",
                "host": "same.example",
                "disposition": "EXISTING_CONTENT",
                "reason_code": None,
            }
        )
        completed_key = ("run:resume", "query:test:1", "search-a")
        resume_store.attempts[completed_key] = {
            "id": "attempt:completed",
            "status": "HEALTHY",
            "cost_usd": Decimal("0"),
            "raw_hits": 1,
            "accepted_hits": 1,
            "rejected_hits": 0,
            "omitted_hits": 0,
            "error_category": None,
            "provider_receipt": {},
        }
        followup = StaticAdapter(
            "search-b",
            hits=(
                DiscoveryHitCandidate(
                    "https://same.example/b",
                    "Garlasco followup",
                    "2026-01-02T00:00:00Z",
                    "web",
                ),
                DiscoveryHitCandidate(
                    "https://other.example/c",
                    "Garlasco followup",
                    "2026-01-03T00:00:00Z",
                    "web",
                ),
            ),
        )

        receipt = run_discovery_manifest(
            resume_manifest,
            resume_store,
            {"search-a": adapter, "search-b": followup},
            run_id="run:resume",
        )
        self.assertEqual(receipt.accepted_hits, 2)
        self.assertEqual(followup.calls, 1)
        followup_rows = [row for row in resume_store.hits if row["query_id"] == "query:test:2"]
        self.assertEqual(followup_rows[0]["disposition"], "HOST_LIMIT")
        self.assertEqual(followup_rows[1]["disposition"], "NEW_CONTENT")

    def test_manifest_metadata_rejects_secret_like_keys(self):
        payload = manifest_payload()
        payload["metadata"] = {"api_key": "never-store-this"}
        with self.assertRaisesRegex(DiscoveryManifestError, "SENSITIVE_KEY"):
            load_discovery_manifest(payload)

    def test_configured_registry_adapter_uses_explicit_seed_and_metadata_only_posts(self):
        payload = manifest_payload()
        payload["source_families"] = ["public_creator_accounts"]
        payload["seeds"] = [{"kind": "source_id", "value": "social-raffagiulians"}]
        payload["date_window"] = {}
        payload["queries"][0].update(
            {
                "query": "creator public posts",
                "source_families": ["public_creator_accounts"],
                "adapter_ids": ["configured_registry"],
                "seeds": [{"kind": "source_id", "value": "social-raffagiulians"}],
            }
        )
        manifest = load_discovery_manifest(payload)
        adapter = ConfiguredRegistryDiscoveryAdapter(ROOT / "config" / "source-registry.v1.json")
        request = DiscoveryAdapterRequest(
            manifest_id=manifest.id,
            manifest_sha256=manifest.manifest_sha256,
            run_id="run:registry",
            query=manifest.queries[0],
            date_from=None,
            date_to=None,
            remaining_cost_usd=manifest.cost_cap_usd,
        )
        result = adapter.discover(request)
        self.assertEqual(result.status, "OK")
        self.assertEqual(len(result.hits), 2)
        self.assertEqual({hit.source_family for hit in result.hits}, {"public_creator_accounts"})
        self.assertEqual({hit.source_id for hit in result.hits}, {"social-raffagiulians"})


if __name__ == "__main__":
    unittest.main()

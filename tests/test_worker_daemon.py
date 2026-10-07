import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.platform_transcript import (  # noqa: E402
    CaptionProbe,
    PlatformAccessRestricted,
    VideoCandidate,
)
from dichiarazioni_pubbliche.claim_runtime import (  # noqa: E402
    ClaimExtractionResult,
    ClaimRuntimeProbe,
    ExtractedAtomicClaim,
)
from dichiarazioni_pubbliche.evidence_runtime import (  # noqa: E402
    EvidenceFetchReceipt,
    EvidenceFetchResult,
    EvidenceRateLimited,
)
from dichiarazioni_pubbliche.queue_runtime import (  # noqa: E402
    ContentRecord,
    CostSnapshot,
    ProcessingJob,
)
from dichiarazioni_pubbliche.worker_daemon import (  # noqa: E402
    ProcessingWorker,
    WorkerBudget,
    WorkerProcessLock,
)


class FakePrivateStore:
    def persist_caption(self, **kwargs):
        return Path("/private")


class FakeResolver:
    def __init__(self, candidate=None, probe=None):
        self.candidate = candidate
        self.probe = probe

    def resolve(self, title, source):
        return self.candidate

    def probe_caption(self, url):
        if isinstance(self.probe, Exception):
            raise self.probe
        return self.probe


class FakeClaimClient:
    model = "test-model"
    prompt_version = "claim-extract-test"
    max_output_tokens = 100

    def __init__(self, *, healthy=True, claims=()):
        self.healthy = healthy
        self.claims = tuple(claims)
        self.probes = 0
        self.extracts = 0

    def probe(self):
        self.probes += 1
        return ClaimRuntimeProbe(
            healthy=self.healthy,
            reason="OK" if self.healthy else "OMNIROUTE_HTTP_400:test",
            latency_seconds=0.01,
            http_status=200 if self.healthy else 400,
        )

    def extract(self, *, window_text, allowed_segment_indices):
        self.extracts += 1
        return ClaimExtractionResult(
            claims=self.claims,
            request_id="request:test",
            latency_seconds=0.02,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            observed_cost_usd=0.0,
        )


class FakeEvidenceFetcher:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.registry = {
            "sources": [
                {
                    "id": "official-test",
                    "publisher": "Official Test",
                    "evidence_class": "PRIMARY_OFFICIAL",
                    "authoritative": True,
                }
            ]
        }
        self.calls = []

    def fetch(self, source_id, url):
        self.calls.append((source_id, url))
        if self.error is not None:
            raise self.error
        return self.result

    def request(self, source_id, url, *, method, body=None, content_type=None):
        self.calls.append((source_id, method, url, body, content_type))
        if self.error is not None:
            raise self.error
        return self.result


class FakeStore:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.states = {}
        self.block_reasons = {}
        self.followups = []
        self.status_updates = []
        self.receipts = []
        self.locators = []
        self.bulk_jobs = []
        self.canonical_rows = []
        self.inserted_claim_rows = []
        self.evidence_rows = []
        self.evidence_links = []
        self.evidence_observations = []
        self.approved_evidence_rows = []
        self.evidence_set_assessments = []
        self.coverage_needs = []
        self.verification_runs = []
        self.finding_drafts = []
        self.relation_candidates = []
        self.reanalysis_triggers = []
        self.reanalysis_transitions = []
        self.latest_finding = None
        self.verification_template = None

    def reap_expired(self, max_attempts):
        return 0

    def claim(self, worker_id, lease_seconds):
        return self.jobs.pop(0) if self.jobs else None

    def content(self, content_id):
        return ContentRecord(
            content_id=content_id,
            source_id="youtube-pulp-podcast",
            canonical_url="https://example.test/audio.mp3",
            title="Beppe Grillo a Pulp Podcast | Pulp Podcast #64",
            published_at="2026-09-21",
            duration_ms=4_919_000,
            processing_status="DISCOVERED",
            metadata={},
        )

    def cost_snapshot(self, source_id):
        return CostSnapshot(0.0, 0.0)

    def renew(self, *args, **kwargs):
        return True

    def upsert_locator(self, content_id, **kwargs):
        self.locators.append((content_id, kwargs))

    def enqueue_followup(self, **kwargs):
        self.followups.append(kwargs)
        return "job:followup", True

    def enqueue_jobs_bulk(self, jobs):
        self.bulk_jobs.extend(jobs)
        return len(jobs)

    def canonical_segments(self, content_id):
        return list(self.canonical_rows)

    def insert_atomic_claims(self, claims):
        self.inserted_claim_rows.extend(claims)
        return len(claims)

    def claim_count(self, content_id):
        return len(self.inserted_claim_rows)

    def unfinished_sibling_jobs(self, **kwargs):
        exclude = kwargs.get("exclude_job_id")
        if exclude == "__no_such_job__":
            return sum(1 for state in self.states.values() if state != "COMPLETED")
        return 0

    def upsert_evidence(self, **kwargs):
        self.evidence_rows.append(kwargs)
        return True

    def link_claim_evidence(self, **kwargs):
        self.evidence_links.append(kwargs)
        return True

    def insert_evidence_observation(self, **kwargs):
        self.evidence_observations.append(kwargs)
        return True

    def claim_context(self, claim_id):
        return {
            "claim_id": claim_id,
            "content_id": "content:pulp64",
            "normalized_claim": "Il valore è 10.",
            "claim_type": "NUMERIC_STATISTIC",
            "temporal_scope": {},
            "metadata": {},
            "statement_date": "2026-09-21",
        }

    def approved_verification_evidence(self, claim_id):
        return list(self.approved_evidence_rows)

    def source_intelligence_relations(self):
        return []

    def insert_evidence_set_assessment(self, **kwargs):
        self.evidence_set_assessments.append(kwargs)
        return True

    def coverage_collection_ids_for_claim(self, claim_id):
        return []

    def upsert_coverage_need(self, **kwargs):
        self.coverage_needs.append(kwargs)
        return "CREATED"

    def insert_verification_run(self, **kwargs):
        self.verification_runs.append(kwargs)
        return True

    def latest_finding_id(self, claim_id, exclude_finding_id=None):
        if self.latest_finding == exclude_finding_id:
            return None
        return self.latest_finding

    def insert_finding_draft(self, draft):
        self.finding_drafts.append(draft)
        return True

    def insert_relation_candidate(self, row):
        self.relation_candidates.append(row)
        return True

    def insert_reanalysis_trigger(self, row):
        self.reanalysis_triggers.append(row)
        return True

    def advance_reanalysis_trigger(self, trigger_id, *, status, enqueued_job_id=None):
        self.reanalysis_transitions.append(
            (trigger_id, status, enqueued_job_id)
        )
        return True

    def latest_verification_template(self, claim_id):
        return self.verification_template

    def update_content_status(self, content_id, status, metadata_patch=None):
        self.status_updates.append((content_id, status, metadata_patch or {}))

    def record_receipt(self, **kwargs):
        self.receipts.append(kwargs)
        return "receipt:test"

    def complete(self, job_id, worker_id):
        self.states[job_id] = "COMPLETED"
        return True

    def block(self, job_id, worker_id, reason):
        self.states[job_id] = "BLOCKED"
        self.block_reasons[job_id] = reason
        return True

    def defer(self, job_id, worker_id, reason, delay_seconds):
        self.states[job_id] = "QUEUED"
        return True

    def retry(self, job_id, worker_id, error, delay_seconds, max_attempts):
        self.states[job_id] = "QUEUED"
        return "QUEUED"

    def state_counts(self):
        counts = {}
        for state in self.states.values():
            counts[state] = counts.get(state, 0) + 1
        return counts


REGISTRY = {
    "sources": [
        {
            "id": "youtube-pulp-podcast",
            "name": "Pulp Podcast",
            "kind": "youtube_channel",
        }
    ]
}


def job(job_type, payload=None):
    return ProcessingJob(
        job_id=f"job:{job_type}",
        content_id="content:pulp64",
        job_type=job_type,
        attempt=0,
        payload=payload or {},
    )


class WorkerDaemonTests(unittest.TestCase):
    def make_worker(
        self,
        store,
        resolver=None,
        budget=None,
        claim_client=None,
        claim_rate=None,
        evidence_fetcher=None,
    ):
        return ProcessingWorker(
            store=store,
            registry=REGISTRY,
            resolver=resolver or FakeResolver(),
            private_store=FakePrivateStore(),
            worker_id="test-worker",
            budget=budget or WorkerBudget(),
            claim_client=claim_client,
            claim_max_usd_per_1k_total_tokens=claim_rate,
            evidence_fetcher=evidence_fetcher,
        )

    def test_podcast_resolution_enqueues_caption_without_media(self):
        candidate = VideoCandidate(
            "QaE00l6JZ8w",
            "Beppe Grillo a Pulp Podcast. | Pulp Podcast #64",
            "https://www.youtube.com/watch?v=QaE00l6JZ8w",
        )
        store = FakeStore(
            [
                job(
                    "TRANSCRIPT_RESOLVE_PLATFORM",
                    {"platform": "podcast_rss", "estimated_cost_usd": 0},
                )
            ]
        )
        worker = self.make_worker(
            store,
            FakeResolver(candidate, CaptionProbe("automatic_caption", "it-orig")),
        )
        summary = worker.run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(store.followups[0]["job_type"], "TRANSCRIPT_ACQUIRE_CAPTION")
        self.assertEqual(store.locators[0][1]["platform"], "youtube")
        self.assertEqual(store.receipts[0]["estimated_cost_usd"], 0.0)

    def test_claim_prepare_missing_variant_blocks(self):
        store = FakeStore([job("CLAIM_EXTRACT")])
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(summary.retried, 0)
        self.assertEqual(store.states["job:CLAIM_EXTRACT"], "BLOCKED")

    def test_claim_parent_blocks_without_materializing_windows_when_runtime_disabled(self):
        store = FakeStore(
            [
                job(
                    "CLAIM_EXTRACT",
                    {
                        "variant_id": "transcript:v1",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        store.canonical_rows = [
            {
                "id": "canonical:0",
                "segment_index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "canonical_text": "Il valore è 10 milioni.",
                "transcript_status": "TRANSCRIPT_UNCERTAIN",
                "publication_blocked": True,
                "sensitive_signature": ["NUMBER:10 milioni"],
            },
            {
                "id": "canonical:1",
                "segment_index": 1,
                "start_ms": 1000,
                "end_ms": 2000,
                "canonical_text": "La seconda frase è ordinaria.",
                "transcript_status": "RESOLVED",
                "publication_blocked": False,
                "sensitive_signature": [],
            },
        ]
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.completed, 0)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(store.bulk_jobs, [])
        self.assertEqual(store.states["job:CLAIM_EXTRACT"], "BLOCKED")
        self.assertEqual(
            store.status_updates[-1][2]["claim_window_materialized"],
            False,
        )

    def test_claim_parent_fans_out_only_after_real_capability_gates(self):
        store = FakeStore(
            [
                job(
                    "CLAIM_EXTRACT",
                    {
                        "variant_id": "transcript:v1",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        store.canonical_rows = [
            {
                "id": "canonical:0",
                "segment_index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "canonical_text": "Il valore è 10 milioni.",
                "transcript_status": "TRANSCRIPT_UNCERTAIN",
                "publication_blocked": True,
                "sensitive_signature": ["NUMBER:10 milioni"],
            }
        ]
        client = FakeClaimClient()
        worker = self.make_worker(
            store,
            claim_client=client,
            claim_rate=0.0,
        )
        summary = worker.run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(client.probes, 1)
        self.assertEqual(len(store.bulk_jobs), 1)
        self.assertEqual(store.bulk_jobs[0]["job_type"], "CLAIM_EXTRACT_WINDOW")
        self.assertEqual(store.bulk_jobs[0]["state"], "QUEUED")
        self.assertNotIn("text", store.bulk_jobs[0]["payload"])

    def test_claim_parent_failed_canary_blocks_without_provider_downgrade(self):
        store = FakeStore(
            [
                job(
                    "CLAIM_EXTRACT",
                    {
                        "variant_id": "transcript:v1",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        client = FakeClaimClient(healthy=False)
        summary = self.make_worker(
            store,
            claim_client=client,
            claim_rate=0.0,
        ).run(1)

        self.assertEqual(summary.blocked, 1)
        self.assertEqual(summary.completed, 0)
        self.assertEqual(client.probes, 1)
        self.assertEqual(client.extracts, 0)
        self.assertEqual(store.bulk_jobs, [])
        self.assertTrue(
            store.block_reasons["job:CLAIM_EXTRACT"].startswith(
                "CLAIM_EXTRACTION_CANARY_FAILED:"
            )
        )

    def test_claim_parent_blocks_when_cost_model_is_missing(self):
        store = FakeStore(
            [
                job(
                    "CLAIM_PREPARE",
                    {
                        "variant_id": "transcript:v1",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        client = FakeClaimClient()
        summary = self.make_worker(
            store,
            claim_client=client,
            claim_rate=None,
        ).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(client.probes, 0)
        self.assertEqual(store.bulk_jobs, [])

    def test_claim_window_persists_atomic_claim_and_receipt(self):
        store = FakeStore(
            [
                job(
                    "CLAIM_EXTRACT_WINDOW",
                    {
                        "input_sha256": "",
                        "segment_indices": [0],
                        "estimated_cost_usd": 0.0,
                    },
                )
            ]
        )
        store.canonical_rows = [
            {
                "id": "canonical:0",
                "segment_index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "canonical_text": "Il prezzo è 10 euro.",
                "transcript_status": "TRANSCRIPT_UNCERTAIN",
                "publication_blocked": True,
                "sensitive_signature": ["NUMBER:10 euro"],
            }
        ]
        from dichiarazioni_pubbliche.claim_windows import build_claim_windows, canonical_segment_from_row

        window = build_claim_windows(
            [canonical_segment_from_row(store.canonical_rows[0])]
        )[0]
        store.jobs[0] = job(
            "CLAIM_EXTRACT_WINDOW",
            {
                "input_sha256": window.input_sha256,
                "segment_indices": [0],
                "estimated_cost_usd": 0.0,
            },
        )
        client = FakeClaimClient(
            claims=(
                ExtractedAtomicClaim(
                    normalized_claim="Il prezzo è 10 euro.",
                    claim_type="PRICE_STATISTIC",
                    check_worthy=True,
                    numeric_sensitive=True,
                    speaker="",
                    source_timestamp="0:00",
                    source_segment_indices=(0,),
                ),
            )
        )
        summary = self.make_worker(
            store,
            claim_client=client,
            claim_rate=0.0,
        ).run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(client.extracts, 1)
        self.assertEqual(len(store.inserted_claim_rows), 1)
        self.assertEqual(
            store.inserted_claim_rows[0]["segment_ids"],
            ["canonical:0"],
        )
        self.assertTrue(store.inserted_claim_rows[0]["id"].startswith("claim:"))
        self.assertIsNone(
            store.inserted_claim_rows[0]["temporal_scope"]["statement_date"]
        )
        self.assertEqual(store.receipts[-1]["operation"], "CLAIM_EXTRACT")
        self.assertEqual(store.receipts[-1]["measured_cost_usd"], 0.0)
        self.assertEqual(store.receipts[-1]["estimated_cost_usd"], 0.0)
        self.assertEqual(store.receipts[-1]["total_tokens"], 15)
        self.assertEqual(store.status_updates[-1][1], "CLAIMS_EXTRACTED")

    def test_claim_window_blocks_when_job_statement_date_is_invalid(self):
        store = FakeStore(
            [
                job(
                    "CLAIM_EXTRACT_WINDOW",
                    {
                        "input_sha256": "",
                        "segment_indices": [0],
                        "estimated_cost_usd": 0.0,
                    },
                )
            ]
        )
        store.canonical_rows = [
            {
                "id": "canonical:0",
                "segment_index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "canonical_text": "Il prezzo è 10 euro.",
                "transcript_status": "RESOLVED",
                "publication_blocked": False,
                "sensitive_signature": [],
            }
        ]
        from dichiarazioni_pubbliche.claim_windows import (
            build_claim_windows,
            canonical_segment_from_row,
        )

        window = build_claim_windows(
            [canonical_segment_from_row(store.canonical_rows[0])]
        )[0]
        store.jobs[0] = job(
            "CLAIM_EXTRACT_WINDOW",
            {
                "input_sha256": window.input_sha256,
                "segment_indices": [0],
                "statement_date": "not-a-date",
                "estimated_cost_usd": 0.0,
            },
        )
        client = FakeClaimClient(
            claims=(
                ExtractedAtomicClaim(
                    normalized_claim="Il prezzo è 10 euro.",
                    claim_type="PRICE_STATISTIC",
                    check_worthy=True,
                    numeric_sensitive=True,
                    speaker="",
                    source_timestamp="0:00",
                    source_segment_indices=(0,),
                ),
            )
        )
        summary = self.make_worker(
            store,
            claim_client=client,
            claim_rate=0.0,
        ).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(store.inserted_claim_rows, [])

    def test_evidence_fetch_persists_ledger_and_zero_cost_receipt(self):
        receipt = EvidenceFetchReceipt(
            source_id="official-test",
            canonical_url="https://example.com/official/a",
            final_url="https://example.com/official/a",
            fetched_at="2026-09-22T12:00:00+00:00",
            http_status=200,
            content_type="text/html",
            content_sha256="a" * 64,
            response_bytes=123,
            etag=None,
            last_modified=None,
            from_cache=False,
            cache_age_seconds=None,
            authoritative=True,
            evidence_class="PRIMARY_OFFICIAL",
            publisher="Official Test",
        )
        fetcher = FakeEvidenceFetcher(
            EvidenceFetchResult(receipt=receipt, body_path=Path("/private/body"))
        )
        store = FakeStore(
            [
                job(
                    "EVIDENCE_FETCH_URL",
                    {
                        "evidence_source_id": "official-test",
                        "url": "https://example.com/official/a",
                        "claim_id": "claim:a",
                        "relation_candidate": "UNKNOWN",
                        "retrieval_version": "v1",
                        "valid_from": "2026-01-01",
                        "valid_until": "2026-10-01",
                        "record_status": "SUPERSEDED",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(
            store,
            evidence_fetcher=fetcher,
        ).run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(len(store.evidence_rows), 1)
        self.assertEqual(len(store.evidence_links), 1)
        self.assertEqual(store.evidence_links[0]["claim_id"], "claim:a")
        self.assertEqual(store.receipts[-1]["operation"], "EVIDENCE_FETCH")
        self.assertEqual(store.receipts[-1]["estimated_cost_usd"], 0.0)
        self.assertEqual(
            store.receipts[-1]["ledger_scope"],
            {"claim_id": "claim:a"},
        )
        self.assertIsNone(store.evidence_rows[0]["excerpt"])
        self.assertEqual(store.evidence_rows[0]["valid_from"], "2026-01-01")
        self.assertEqual(store.evidence_rows[0]["valid_until"], "2026-10-01")
        self.assertEqual(store.evidence_rows[0]["record_status"], "SUPERSEDED")

    def test_evidence_rate_limit_defers_without_consuming_retry(self):
        fetcher = FakeEvidenceFetcher(
            error=EvidenceRateLimited("official-test", 17.2)
        )
        store = FakeStore(
            [
                job(
                    "EVIDENCE_FETCH_URL",
                    {
                        "evidence_source_id": "official-test",
                        "url": "https://example.com/official/a",
                        "claim_id": "claim:a",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(
            store,
            evidence_fetcher=fetcher,
        ).run(1)
        self.assertEqual(summary.deferred, 1)
        self.assertEqual(summary.retried, 0)
        self.assertEqual(store.states["job:EVIDENCE_FETCH_URL"], "QUEUED")

    def test_official_query_is_compiled_before_fetch(self):
        receipt = EvidenceFetchReceipt(
            source_id="normattiva-opendata",
            canonical_url=(
                "https://api.normattiva.it/t/normattiva.api/"
                "bff-opendata/v1/api/v1/ricerca/semplice"
            ),
            final_url=(
                "https://api.normattiva.it/t/normattiva.api/"
                "bff-opendata/v1/api/v1/ricerca/semplice"
            ),
            fetched_at="2026-09-22T12:00:00+00:00",
            http_status=200,
            content_type="application/json",
            content_sha256="b" * 64,
            response_bytes=321,
            etag=None,
            last_modified=None,
            from_cache=False,
            cache_age_seconds=None,
            authoritative=False,
            evidence_class="OFFICIAL_LEGAL_INFORMATIONAL",
            publisher="Normattiva Open Data",
        )
        fetcher = FakeEvidenceFetcher(
            EvidenceFetchResult(receipt=receipt, body_path=Path("/private/body"))
        )
        fetcher.registry["sources"].append(
            {
                "id": "normattiva-opendata",
                "publisher": "Normattiva Open Data",
                "evidence_class": "OFFICIAL_LEGAL_INFORMATIONAL",
                "authoritative": False,
            }
        )
        store = FakeStore(
            [
                job(
                    "EVIDENCE_QUERY_OFFICIAL",
                    {
                        "evidence_source_id": "normattiva-opendata",
                        "query_kind": "SIMPLE_SEARCH",
                        "query_params": {
                            "text": "imposta automobilistica",
                            "page_size": 5,
                        },
                        "claim_id": "claim:a",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(
            store,
            evidence_fetcher=fetcher,
        ).run(1)
        self.assertEqual(summary.completed, 1)
        call = fetcher.calls[0]
        self.assertEqual(call[0], "normattiva-opendata")
        self.assertEqual(call[1], "POST")
        self.assertIn(b'"testoRicerca":"imposta automobilistica"', call[3])
        self.assertEqual(
            store.evidence_links[0]["retrieval_method"],
            "NORMATTIVA_SIMPLE_SEARCH",
        )

    def test_evidence_observation_is_always_candidate_on_ingest(self):
        store = FakeStore(
            [
                job(
                    "EVIDENCE_OBSERVE",
                    {
                        "evidence_id": "evidence:a",
                        "observation_type": "METRIC",
                        "metric": "tax_rate",
                        "value_numeric": 10,
                        "unit": "percent",
                        "reference_period": "2026",
                        "dimensions": {},
                        "extraction_method": "MANUAL_STRUCTURED",
                        "extraction_version": "v1",
                        "source_pointer": {"table": "A", "row": 1},
                        "status": "APPROVED",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(len(store.evidence_observations), 1)
        self.assertEqual(store.evidence_observations[0]["status"], "CANDIDATE")

    def test_verification_creates_only_policy_hold_finding(self):
        store = FakeStore(
            [
                job(
                    "VERIFY_CLAIM",
                    {
                        "claim_id": "claim:a",
                        "verification_kind": "numeric_exact",
                        "verification_rule": {
                            "metric": "tax_rate",
                            "value": 10,
                            "reference_period": "2026",
                        },
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        store.approved_evidence_rows = [
            {
                "evidence_id": "evidence:a",
                "observation_id": "observation:a",
                "publication_date": "2026-09-01",
                "metric": "tax_rate",
                "value_numeric": 10,
                "value_text": None,
                "unit": "percent",
                "reference_period": "2026",
                "source_id": "istat-sdmx",
                "independence_group": "istat-sdmx:2026",
                "rights_status": "UNKNOWN",
                "dimensions": {},
                "authoritative": True,
                "status": "APPROVED",
                "metadata": {"evidence_source_id": "istat-sdmx"},
            }
        ]
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(
            store.evidence_set_assessments[0]["assessment"],
            "SUFFICIENT_FOR_RULE",
        )
        self.assertEqual(store.verification_runs[0]["assessment"], "SUPPORTED")
        self.assertEqual(
            store.finding_drafts[0]["publication_status"],
            "POLICY_HOLD",
        )
        self.assertNotEqual(
            store.finding_drafts[0]["publication_status"],
            "PUBLISH",
        )

    def test_verification_without_approved_observation_needs_more_evidence(self):
        store = FakeStore(
            [
                job(
                    "VERIFY_CLAIM",
                    {
                        "claim_id": "claim:a",
                        "verification_kind": "numeric_exact",
                        "verification_rule": {
                            "metric": "tax_rate",
                            "value": 10,
                        },
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(store.verification_runs, [])
        self.assertEqual(store.finding_drafts, [])
        self.assertEqual(
            store.evidence_set_assessments[0]["assessment"],
            "INSUFFICIENT_PRIMARY_SOURCE",
        )
        self.assertTrue(
            store.evidence_set_assessments[0]["coverage_need_candidates"]
        )
        self.assertTrue(store.coverage_needs)
        self.assertTrue(
            all(row["atomic_claim_id"] == "claim:a" for row in store.coverage_needs)
        )
        self.assertTrue(
            all(row["source_intelligence_assessment_id"] for row in store.coverage_needs)
        )

    def test_verification_blocks_tampered_statement_date(self):
        store = FakeStore(
            [
                job(
                    "VERIFY_CLAIM",
                    {
                        "claim_id": "claim:a",
                        "verification_kind": "numeric_exact",
                        "verification_rule": {
                            "metric": "tax_rate",
                            "value": 10,
                        },
                        "statement_date": "2026-09-22",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(store.verification_runs, [])
        self.assertEqual(
            store.block_reasons["job:VERIFY_CLAIM"],
            "VERIFICATION_STATEMENT_DATE_MISMATCH",
        )

    def test_relation_job_only_persists_candidate(self):
        store = FakeStore(
            [
                job(
                    "CLASSIFY_CLAIM_RELATION",
                    {
                        "prior": {
                            "claim_id": "claim:a",
                            "statement_date": "2025-01-01",
                            "proposition_key": "policy-x",
                            "topic_key": "policy",
                            "stance": "SUPPORT",
                            "scope_start": "2025-01-01",
                            "scope_end": "2025-12-31",
                        },
                        "later": {
                            "claim_id": "claim:b",
                            "statement_date": "2025-06-01",
                            "proposition_key": "policy-x",
                            "topic_key": "policy",
                            "stance": "OPPOSE",
                            "scope_start": "2025-01-01",
                            "scope_end": "2025-12-31",
                        },
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(len(store.relation_candidates), 1)
        self.assertEqual(
            store.relation_candidates[0]["relation_type"],
            "CONTRADICTION_CANDIDATE",
        )
        self.assertEqual(store.relation_candidates[0]["status"], "CANDIDATE")

    def test_reanalysis_reuses_latest_verification_rule_without_mutating_old_finding(self):
        store = FakeStore(
            [
                job(
                    "REANALYZE_CLAIM",
                    {
                        "claim_id": "claim:a",
                        "trigger_id": "reanalysis:a",
                        "estimated_cost_usd": 0,
                    },
                )
            ]
        )
        store.latest_finding = "finding:old"
        store.verification_template = {
            "verification_kind": "numeric_exact",
            "verification_rule": {"metric": "tax_rate", "value": 10},
            "statement_cutoff": "2026-09-21",
            "verification_version": "deterministic-verification-v1",
        }
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(store.followups[0]["job_type"], "VERIFY_CLAIM")
        self.assertEqual(
            store.followups[0]["payload"]["reanalysis_trigger_id"],
            "reanalysis:a",
        )
        self.assertEqual(store.latest_finding, "finding:old")
        self.assertEqual(
            store.reanalysis_transitions[-1][1],
            "ENQUEUED",
        )

    def test_members_only_youtube_falls_back_to_rss_asr_without_retry(self):
        candidate = VideoCandidate(
            "members-only",
            "RISPONDIAMO a SHY | Pulp Special #20",
            "https://www.youtube.com/watch?v=members-only",
        )
        store = FakeStore(
            [
                job(
                    "TRANSCRIPT_RESOLVE_PLATFORM",
                    {"platform": "podcast_rss", "estimated_cost_usd": 0},
                )
            ]
        )
        worker = self.make_worker(
            store,
            FakeResolver(
                candidate,
                PlatformAccessRestricted("members-only content"),
            ),
        )
        summary = worker.run(1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.retried, 0)
        self.assertEqual(store.followups[0]["job_type"], "TRANSCRIPT_ACQUIRE_ASR")
        self.assertEqual(store.receipts[0]["status"], "ACCESS_RESTRICTED")

    def test_budget_cap_defers_before_dispatch(self):
        store = FakeStore(
            [job("TRANSCRIPT_ACQUIRE_ASR", {"estimated_cost_usd": 0.50})]
        )
        summary = self.make_worker(
            store,
            budget=WorkerBudget(max_cost_usd_per_job=0.25),
        ).run(1)
        self.assertEqual(summary.deferred, 1)
        self.assertEqual(summary.blocked, 0)
        self.assertEqual(store.states["job:TRANSCRIPT_ACQUIRE_ASR"], "QUEUED")

    def test_asr_without_runtime_key_blocks_without_network(self):
        store = FakeStore(
            [
                job(
                    "TRANSCRIPT_ACQUIRE_ASR",
                    {
                        "provider_id": "groq-whisper-large-v3-turbo",
                        "route": "groq/whisper-large-v3-turbo",
                        "canonical_url": "https://example.test/audio.mp3",
                        "estimated_cost_usd": 0.05,
                    },
                )
            ]
        )
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(store.states["job:TRANSCRIPT_ACQUIRE_ASR"], "BLOCKED")
        self.assertEqual(
            store.status_updates[-1][2]["runtime_blocker"],
            "GROQ_API_KEY_MISSING",
        )

    def test_unknown_job_type_fails_closed(self):
        store = FakeStore([job("DO_SOMETHING_UNKNOWN")])
        summary = self.make_worker(store).run(1)
        self.assertEqual(summary.blocked, 1)
        self.assertEqual(store.states["job:DO_SOMETHING_UNKNOWN"], "BLOCKED")

    def test_process_lock_prevents_parallel_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "worker.lock"
            first = WorkerProcessLock(path)
            second = WorkerProcessLock(path)
            self.assertTrue(first.acquire())
            try:
                self.assertFalse(second.acquire())
            finally:
                first.release()
            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()

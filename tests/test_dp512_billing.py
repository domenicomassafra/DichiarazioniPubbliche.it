"""Offline DP-512 regressions: an estimate is not an observed bill."""

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_extraction import (  # noqa: E402
    CandidateExtractionStore,
    OmniRouteCandidateExtractionClient,
    PreparedExtractionBatch,
    ProviderExtractionRequest,
    ProviderExtractionResult,
    _COMMIT_BATCH_SQL,
    _FINISH_NO_CANDIDATES_SQL,
    load_candidate_extraction_config,
)
from dichiarazioni_pubbliche.operation_ledger import (  # noqa: E402
    aggregate_operation_receipts,
    operation_usage_receipt_from_row,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore  # noqa: E402
from dichiarazioni_pubbliche.research_discovery import (  # noqa: E402
    ResearchDiscoveryStore,
    _discovery_billing,
    load_discovery_manifest,
)
from dichiarazioni_pubbliche.worker_handlers_transcript import TranscriptAsrJobHandlers  # noqa: E402


class DP512BillingTests(unittest.TestCase):
    def test_discovery_adapter_estimates_are_never_verified_provider_bills(self):
        cases = (
            ("0.125000", "0.500000", "ESTIMATED_ONLY", "0.500000"),
            ("0", "0.500000", "ESTIMATED_ONLY", "0.500000"),
            ("0.600000", "0.500000", "ESTIMATED_ONLY", "0.600000"),
            (None, "0.500000", "UNKNOWN", "0.500000"),
            ("0", "0", "UNKNOWN", "0.000000"),
            (None, "0", "UNKNOWN", "0.000000"),
        )
        for reported, upper_bound, expected_basis, expected_estimate in cases:
            with self.subTest(reported=reported, upper_bound=upper_bound):
                basis, estimate, measured = _discovery_billing(
                    known_cost_usd=None if reported is None else Decimal(reported),
                    cost_upper_bound_usd=Decimal(upper_bound),
                )
                self.assertEqual(basis, expected_basis)
                self.assertEqual(estimate, Decimal(expected_estimate))
                self.assertIsNone(measured)

    def test_discovery_writer_retains_unverified_adapter_amount_without_measured_charge(self):
        payload = {
            "schema_version": 1,
            "id": "manifest:dp512", "collection_id": "collection:dp512",
            "seeds": [{"kind": "term", "value": "public record"}],
            "source_families": ["web"],
            "limits": {"max_results": 2, "max_results_per_host": 2, "cost_cap_usd": "1"},
            "queries": [{
                "id": "query:dp512", "query": "public record", "source_families": ["web"],
                "adapter_ids": ["search-a"], "max_results": 2,
            }],
        }
        manifest = load_discovery_manifest(payload)
        store = object.__new__(ResearchDiscoveryStore)
        recorded = []

        def fake_run(sql, **params):
            recorded.append(params)
            return params["receipt_id"]

        store.run = fake_run
        fields = dict(
            manifest=manifest, query=manifest.queries[0], run_id="run:dp512",
            attempt_id="attempt:dp512", adapter_id="search-a",
            adapter_version="search-a:v1", status="HEALTHY",
            cost_upper_bound_usd=Decimal("0.5"), known_cost_usd=Decimal("0.125"),
        )
        first = store.record_operation_receipt(**fields)
        second = store.record_operation_receipt(**fields)
        self.assertEqual(first, second)
        self.assertEqual(recorded[0], recorded[1])
        params = recorded[0]
        self.assertEqual(params["billing_basis"], "ESTIMATED_ONLY")
        self.assertEqual(params["estimated_cost_usd"], "0.500000")
        self.assertEqual(params["measured_cost_usd"], "")
        nested = json.loads(params["receipt"])
        self.assertEqual(nested["adapter_reported_cost_usd"], "0.125000")
        self.assertNotIn("invoice_reference", nested)

    def test_discovery_zero_upper_bound_exception_stays_unknown_in_ledger(self):
        basis, estimate, measured = _discovery_billing(
            known_cost_usd=None, cost_upper_bound_usd=Decimal("0"),
        )
        receipt = operation_usage_receipt_from_row({
            "receipt_id": "receipt:zero-unverified", "operation_key": "op:zero-unverified",
            "attempt": 1, "provider_id": "search-a", "operation": "RESEARCH_DISCOVERY",
            "status": "FAILED", "billing_basis": basis,
            "estimated_cost_usd": str(estimate), "measured_cost_usd": measured,
        })
        summary = aggregate_operation_receipts((receipt,))
        self.assertEqual(summary.unknown_cost_operation_count, 1)
        self.assertEqual(summary.zero_cost_operation_count, 0)
        self.assertFalse(summary.cost_complete)

    def test_provider_response_cost_is_unverified_not_billed(self):
        client = OmniRouteCandidateExtractionClient(
            api_key="offline-placeholder", model_id="test/model",
            config=load_candidate_extraction_config(),
            cost_rate_usd_per_1k_total_tokens="0.5",
        )
        request = ProviderExtractionRequest(
            operation_key="op:test", run_id="run:test", passage_id="passage:test",
            content_id="content:test", text="Test original.", language="it",
            alias_hints=(), max_statements=2, max_claims_per_statement=2,
            max_entity_mentions_per_statement=2,
            cost_upper_bound_usd=Decimal("0.25"),
        )
        base_response = {
            "id": "request:test",
            "choices": [{"message": {"content": '{"statements":[]}'}}],
        }
        cases = (
            ({**base_response, "usage": {"total_tokens": 10}, "cost_usd": 0.04},
             Decimal("0.04"), "provider_response_unverified"),
            ({**base_response, "usage": {"total_tokens": 100}},
             Decimal("0.05"), "token_rate_estimate"),
            (base_response, Decimal("0.25"), "upper_bound_estimate"),
        )
        for response, amount, basis in cases:
            with self.subTest(basis=basis), patch.object(
                client, "_post", return_value=(response, 0.001)
            ):
                result = client.extract(request)
            self.assertEqual(result.cost_usd, amount)
            self.assertEqual(result.receipt["cost_basis"], basis)
            self.assertNotIn("MEASURED_PROVIDER_COST", str(result.receipt))

    def test_successful_candidate_commit_keeps_measured_null(self):
        self.assertIn("NULL, 'ESTIMATED_ONLY'", _COMMIT_BATCH_SQL)
        self.assertNotIn(":'cost_usd'::numeric, 'MEASURED_PROVIDER_COST'", _COMMIT_BATCH_SQL)
        store = object.__new__(CandidateExtractionStore)
        observed = {}

        def fake_run(sql, **kwargs):
            observed.update({"sql": sql, **kwargs})
            return json.dumps({"status": "COMPLETED", "id": "run:test"})

        store.run = fake_run
        result = ProviderExtractionResult(
            payload={"statements": []},
            request_id="request:test",
            latency_seconds=0.5,
            usage={"total_tokens": 20},
            cost_usd=Decimal("0.02"),
            receipt={"cost_basis": "token_rate_estimate"},
        )
        store.commit_batch(
            run_id="run:test",
            lease_owner="worker:test",
            batch=PreparedExtractionBatch((), (), (), ()),
            context=SimpleNamespace(text="Original source text"),
            provider=SimpleNamespace(provider_version="test:v1"),
            provider_result=result,
            provider_receipt_id="receipt:test",
            request_id="request:test",
            actual_cost=Decimal("0.02"),
        )
        nested = json.loads(observed["provider_receipt"])
        self.assertEqual(nested["billing_classification"], "ESTIMATED_ONLY")
        self.assertEqual(nested["provider_cost_input_usd"], "0.02")
        self.assertEqual(nested["cost_basis"], "token_rate_estimate")
        self.assertEqual(observed["cost_usd"], "0.02")
        self.assertEqual(observed["total_tokens"], 20)
        self.assertNotIn("raw_text", str(nested))

    def test_failed_zero_upper_bound_never_fabricates_zero_cost(self):
        self.assertIn("WHEN :'cost_usd'::numeric > 0 THEN 'UNKNOWN'", _FINISH_NO_CANDIDATES_SQL)
        self.assertIn("ELSE 'ESTIMATED_ONLY'", _FINISH_NO_CANDIDATES_SQL)
        self.assertNotIn("ELSE 'ZERO_COST'", _FINISH_NO_CANDIDATES_SQL)
        store = object.__new__(CandidateExtractionStore)
        seen = {}

        def fake_run(sql, **params):
            seen.update(params)
            return '{"status":"FAILED","id":"run:test"}'

        store.run = fake_run
        store.finish_without_candidates(
            run_id="run:test", lease_owner="worker:test", status="FAILED",
            error_category="PROVIDER_FAILURE", call_count=1, cost_usd=Decimal("0"),
            input_bytes=5, provider_receipt_id="receipt:test", request_id=None,
            provider_receipt={"error_category": "PROVIDER_FAILURE"},
            receipt_status="FAILED", record_provider_receipt=True,
        )
        self.assertEqual(
            json.loads(seen["provider_receipt"])["cash_cost_uncertainty"], "UNKNOWN"
        )
        uncertain = operation_usage_receipt_from_row({
            "receipt_id": "receipt:test", "operation_key": "op:failed", "attempt": 1,
            "provider_id": "omniroute", "operation": "CANDIDATE_EXTRACT",
            "status": "FAILED", "billing_basis": "ESTIMATED_ONLY",
            "estimated_cost_usd": "0", "cash_cost_uncertainty": "UNKNOWN",
        })
        summary = aggregate_operation_receipts((uncertain,))
        self.assertEqual(summary.unknown_cost_operation_count, 1)
        self.assertFalse(summary.cost_complete)

    def test_local_asr_cash_is_estimated_and_energy_is_unknown(self):
        class Store:
            def insert_transcript_variant(self, **kwargs):
                return "variant:test", True

            def insert_transcript_segments(self, **kwargs):
                self.segments = kwargs

            def record_receipt(self, **kwargs):
                self.provider_receipt = kwargs

            def enqueue_followup(self, **kwargs):
                self.followup = kwargs

            def update_content_status(self, *args):
                self.status = args

        class PrivateStore:
            def persist_asr_response(self, **kwargs):
                self.saved = kwargs

        handler = TranscriptAsrJobHandlers()
        handler.store = Store()
        handler.private_store = PrivateStore()
        result = SimpleNamespace(
            language="en", text="Hello", text_sha256="h" * 64,
            model_id="local:model", request_id="request:local",
            raw_response={}, duration_seconds=2,
            segments=(SimpleNamespace(segment_index=0, start_ms=0, end_ms=2000, text="Hello"),),
        )
        handler._persist_asr_result(
            SimpleNamespace(job_id="job:test", payload={"estimated_cost_usd": 0}),
            SimpleNamespace(content_id="content:test", source_id="source:test"),
            result,
            provider_id="local-asr", source_kind="LOCAL_ASR",
            audio_transport="LOCAL_FILE", input_sha256="a" * 64,
            model_sha256="b" * 64, rights_receipt_id="rights:test", input_bytes=64,
        )
        canonical = handler.store.provider_receipt
        self.assertEqual(canonical["billing_basis"], "ESTIMATED_ONLY")
        self.assertIsNone(canonical.get("measured_cost_usd"))
        self.assertEqual(canonical["receipt"]["billing_basis"], "LOCAL_COMPUTE_UNMETERED")
        self.assertEqual(canonical["receipt"]["local_energy_basis"], "UNKNOWN")
        self.assertIsNone(canonical["receipt"]["local_energy_wh"])
        self.assertFalse(canonical["receipt"]["publication_approved"])

    def test_ledger_keeps_local_energy_unknown_across_attempts_and_legacy_rows(self):
        def row(receipt_id, attempt, billing_basis, estimated, energy=None, measured=None):
            return operation_usage_receipt_from_row({
                "receipt_id": receipt_id, "operation_key": "provider-operation:test",
                "attempt": attempt, "provider_id": "local", "model_id": "model",
                "operation": "AUDIO_TRANSCRIPTION", "status": "SUCCESS",
                "billing_basis": billing_basis, "estimated_cost_usd": estimated,
                "measured_cost_usd": measured,
                "local_energy_basis": energy, "request_count": 1,
            })

        rows = (
            row("receipt:1", 1, "ESTIMATED_ONLY", "0", "UNKNOWN"),
            row("receipt:2", 2, "ESTIMATED_ONLY", "0", "UNKNOWN"),
        )
        summary = aggregate_operation_receipts(rows)
        self.assertEqual(summary.operation_count, 1)
        self.assertEqual(summary.attempt_count, 2)
        self.assertEqual(summary.unknown_local_energy_operation_count, 1)
        self.assertFalse(summary.cost_complete)
        historic = row("receipt:legacy", 3, "MEASURED_PROVIDER_COST", "0.25", measured="0.10")
        # A legacy billed receipt is preserved as originally recorded; no
        # speculative retrospective reclassification is allowed.
        self.assertEqual(historic.billing_basis, "MEASURED_PROVIDER_COST")

    def test_queue_read_model_extracts_only_energy_classification(self):
        store = object.__new__(QueueExecutionCostStore)
        seen = {}

        def fake_run(sql, **params):
            seen.update({"sql": sql, **params})
            return "[]"

        store.run = fake_run
        self.assertEqual(store.operation_ledger_receipts(), ())
        self.assertIn("r.receipt->>'local_energy_basis'", seen["sql"])
        self.assertIn("r.receipt->>'cash_cost_uncertainty'", seen["sql"])
        self.assertNotIn("'receipt', r.receipt", seen["sql"])


if __name__ == "__main__":
    unittest.main()

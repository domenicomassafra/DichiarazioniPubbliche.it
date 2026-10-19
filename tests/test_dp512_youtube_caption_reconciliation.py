"""Source-backed YouTube caption zero-fee tests; no external requests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.operation_ledger import (  # noqa: E402
    operation_usage_receipt_from_row,
)
from dichiarazioni_pubbliche.ops.youtube_caption_reconciliation_v1 import (  # noqa: E402
    read_youtube_caption_reconciliation,
)
from dichiarazioni_pubbliche.queue_store import QueueExecutionCostStore  # noqa: E402
from dichiarazioni_pubbliche.youtube_caption_receipts import (  # noqa: E402
    record_caption_receipt,
)
from dichiarazioni_pubbliche.worker_handlers_transcript import (  # noqa: E402
    TranscriptAsrJobHandlers,
)
from dichiarazioni_pubbliche.platform_transcript import (  # noqa: E402
    CaptionProbe,
    VideoCandidate,
)


def youtube_row(n, operation="CAPTION_PROBE", basis="ESTIMATED_ONLY", **changes):
    row = {
        "receipt_id": f"receipt:{n}",
        "operation_key": f"operation:{n}",
        "attempt": 1,
        "provider_id": "youtube",
        "model_id": None,
        "operation": operation,
        "status": "SUCCESS",
        "billing_basis": basis,
        "estimated_cost_usd": "0",
        "measured_cost_usd": None,
        "total_tokens": None,
        "local_energy_basis": "UNKNOWN",
    }
    row.update(changes)
    return operation_usage_receipt_from_row(row)


class YouTubeCaptionBillingTests(unittest.TestCase):
    def test_63_legacy_receipts_reconcile_without_rewriting_canonical_rows(self):
        originals = tuple(
            youtube_row(n, "CAPTION_PROBE" if n < 46 else "CAPTION_CAPTURE")
            for n in range(63)
        )

        class Store:
            def operation_ledger_receipts(self, **filters):
                self.filters = filters
                return originals + (originals[0],)

        store = Store()
        report = read_youtube_caption_reconciliation(
            store, since="2026-09-01T00:00:00+02:00",
            until="2026-10-20T00:00:00+02:00",
        )
        self.assertEqual(store.filters["provider_id"], "youtube")
        self.assertEqual(report["attempt_count"], 63)
        self.assertEqual(report["caption_probe_attempts"], 46)
        self.assertEqual(report["caption_capture_attempts"], 17)
        self.assertEqual(report["duplicate_receipt_replays"], 1)
        self.assertEqual(report["historical_estimated_only_attempts"], 63)
        self.assertEqual(report["assessed_zero_provider_fee_attempts"], 63)
        self.assertEqual(report["unreconciled_youtube_caption_attempts"], 0)
        self.assertEqual(report["unmeasured_local_energy_attempts"], 63)
        self.assertEqual(report["youtube_data_api_v3_quota_units"], 0)
        self.assertFalse(report["canonical_receipts_modified"])
        self.assertFalse(report["paid_dispatch_authorized"])
        self.assertEqual(originals[0].billing_basis, "ESTIMATED_ONLY")

    def test_any_nonzero_money_or_unknown_route_fails_closed(self):
        invalid = (
            {"estimated_cost_usd": "0.01"},
            {"measured_cost_usd": "0.02", "billing_basis": "MEASURED_PROVIDER_COST"},
            {"model_id": "model:paid"},
            {"operation": "DATA_API_SEARCH"},
            {"billing_basis": "UNKNOWN"},
            {"total_tokens": 12},
        )
        for index, fields in enumerate(invalid):
            with self.subTest(fields=fields):
                class Store:
                    def operation_ledger_receipts(self, **_):
                        return (youtube_row(index, **fields),)

                with self.assertRaisesRegex(ValueError, "YOUTUBE_CAPTION_BILLING_EVIDENCE_CONFLICT"):
                    read_youtube_caption_reconciliation(
                        Store(), since="2026-09-01T00:00:00+00:00",
                        until="2026-10-20T00:00:00+00:00",
                    )

    def test_canonical_writer_rejects_nonzero_no_model_youtube_caption(self):
        class Store(QueueExecutionCostStore):
            def run(self, *_args, **kwargs):
                self.variables = kwargs
                return "receipt:good"

        store = Store()
        params = dict(
            job_id="job:a", content_id="content:a", provider_id="youtube",
            model_id=None, operation="CAPTION_CAPTURE", request_id=None,
            input_bytes=123, input_seconds=None, estimated_cost_usd=0.0,
            billing_basis="ZERO_COST", status="SUCCESS", receipt={},
        )
        for override in (
            {"estimated_cost_usd": 0.01},
            {"measured_cost_usd": 0.2},
            {"billing_basis": "ESTIMATED_ONLY"},
            {"billing_basis": "EXTERNAL_PLAN"},
        ):
            with self.subTest(override=override):
                with self.assertRaisesRegex(ValueError, "YOUTUBE_CAPTION_MONETARY_COST_FORBIDDEN"):
                    record_caption_receipt(store, **(params | override))
        record_caption_receipt(store, **params)
        self.assertEqual(store.variables["billing_basis"], "ZERO_COST")
        self.assertEqual(store.variables["estimated_cost_usd"], 0.0)

    def test_actual_caption_probe_writer_records_source_provenance(self):
        class Store:
            def renew(self, *_args, **_kwargs):
                return True

            def require_current_ingestion_relevance(self, **_kwargs):
                return None

            def record_receipt(self, **kwargs):
                self.receipt = kwargs

            def enqueue_followup(self, **kwargs):
                self.followup = kwargs

            def update_content_status(self, *_args):
                return None

        handler = TranscriptAsrJobHandlers()
        handler.store = Store()
        handler.resolver = SimpleNamespace(probe_caption=lambda _: CaptionProbe("manual_caption", "it"))
        handler.worker_id = "local-test"
        handler.lease_seconds = 20
        handler._probe_and_enqueue_caption(
            SimpleNamespace(job_id="job:1", attempt=1),
            SimpleNamespace(
                content_id="content:1",
                source_id="source:1",
                canonical_url="https://www.youtube.com/watch?v=vid1",
            ),
            VideoCandidate("vid1", "title", "https://www.youtube.com/watch?v=vid1"),
        )
        receipt = handler.store.receipt
        self.assertEqual(receipt["billing_basis"], "ZERO_COST")
        self.assertIsNone(receipt["model_id"])
        self.assertEqual(receipt["receipt"]["access_path"], "YT_DLP_PUBLIC_CAPTION")
        self.assertEqual(receipt["receipt"]["local_energy_basis"], "UNKNOWN")
        self.assertEqual(receipt["receipt"]["youtube_data_api_v3_quota_units"], 0)


if __name__ == "__main__":
    unittest.main()

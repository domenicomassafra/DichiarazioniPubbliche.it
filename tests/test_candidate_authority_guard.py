import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.candidate_extraction import extract_passage_candidates
from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from test_candidate_extraction import FakeProvider, FakeStore, valid_payload


class GuardBoundaryTests(unittest.TestCase):
    def test_rejected_initial_authority_never_starts_run_or_calls_provider(self):
        store, provider = FakeStore(), FakeProvider(valid_payload())

        def reject():
            raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_RIGHTS_REVOKED")

        with self.assertRaises(PrivateCaptureAuthorizationBlocked):
            extract_passage_candidates(
                passage_id="passage:parent", store=store, provider=provider,
                max_cost_usd="1", authorization_guard=reject
            )
        self.assertEqual(store.start_calls, [])
        self.assertEqual(provider.calls, 0)

    def test_revocation_just_before_provider_finishes_blocked_no_call(self):
        store, provider = FakeStore(), FakeProvider(valid_payload(), upper=Decimal("0.003"))
        checks = 0

        def guard():
            nonlocal checks
            checks += 1
            if checks >= 4:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_RIGHTS_REVOKED")

        receipt = extract_passage_candidates(
            passage_id="passage:parent", store=store, provider=provider,
            max_cost_usd="1", authorization_guard=guard,
        )
        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(receipt.call_count, 0)
        self.assertEqual(receipt.cost_usd, Decimal(0))
        self.assertEqual(provider.calls, 0)
        self.assertFalse(store.committed_batches)

    def test_revocation_after_provider_call_reserves_cost_and_blocks_candidate_commit(self):
        store, provider = FakeStore(), FakeProvider(valid_payload(), upper=Decimal("0.003"), cost=Decimal("0.002"))
        checks = 0

        def guard():
            nonlocal checks
            checks += 1
            if checks >= 5:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_RIGHTS_REVOKED")

        receipt = extract_passage_candidates(
            passage_id="passage:parent", store=store, provider=provider,
            max_cost_usd="1", authorization_guard=guard,
        )
        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(receipt.call_count, 1)
        self.assertEqual(receipt.cost_usd, Decimal("0.003"))
        self.assertEqual(provider.calls, 1)
        self.assertFalse(store.committed_batches)

    def test_continuing_authority_keeps_normal_candidate_contract(self):
        store, provider = FakeStore(), FakeProvider(valid_payload())
        calls = []
        receipt = extract_passage_candidates(
            passage_id="passage:parent", store=store, provider=provider,
            max_cost_usd="1", authorization_guard=lambda: calls.append("checked")
        )
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(provider.calls, 1)
        self.assertGreaterEqual(len(calls), 6)
        self.assertEqual(len(store.committed_batches), 1)


if __name__ == "__main__":
    unittest.main()

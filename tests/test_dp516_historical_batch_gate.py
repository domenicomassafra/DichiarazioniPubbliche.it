"""DP-516 source-only adversarial plans. Fixtures never attest a real pilot."""

import sys
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from tests.test_dp243_historical_corpus_preflight import NOW, two  # noqa: E402
from tests.test_dp243_historical_corpus_preflight import entry, manifest  # noqa: E402
from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    BudgetPolicy,
    CostSnapshot,
    MonthlyBudgetState,
    MonthlyEurPolicy,
    MonthlyFxQuote,
)
from dichiarazioni_pubbliche.incremental_source_watch import (  # noqa: E402
    WatchPolicy,
    WatchReadiness,
    WatchState,
    policy_fingerprint,
)
from dichiarazioni_pubbliche.historical_batch_gate_v1 import (  # noqa: E402
    BatchCost,
    BatchPilotAcceptance,
    BatchWatch,
    CompletedCapture,
    create_checkpoint,
    plan_historical_batch,
)

PERIOD = "2026-10@Europe/Rome"


def resources(manifests=None):
    manifests = manifests or two()
    costs = tuple(
        BatchCost(e.content_id, "CLAIM_EXTRACT", Decimal("0.05"))
        for m in manifests
        for e in m.entries
    )
    watches = []
    for m in manifests:
        for e in m.entries:
            policy = WatchPolicy(
                source_id=e.content_id,
                locator_id=e.content_id,
                source_family=e.source_family,
                corpus_id=m.collection_id,
                corpus_cutoff="2026-10-11",
                policy_revision="test:1",
                enabled=True,
            )
            readiness = WatchReadiness(
                source_id=e.content_id,
                policy_fingerprint=policy_fingerprint(policy),
                corpus_id=m.collection_id,
                rights_status="READY",
                rights_receipt="test:rights",
                capability_status="READY",
                capability_receipt="test:cap",
                budget_status="READY",
                budget_receipt="test:budget",
                remaining_children=1,
            )
            watches.append(
                BatchWatch(e.content_id, policy, WatchState(e.content_id), readiness)
            )
    return costs, tuple(watches)


def pilot(*, decision="GO_FOR_SCALING", scope="history:it-de", **changes):
    return replace(
        BatchPilotAcceptance(
            ticket="DP-443",
            decision=decision,
            scope_id=scope,
            signed_receipt_ref="pilot:synthetic:signed",
            signer_ref="synthetic:reviewer",
            signature="synthetic-signature-bytes",
            runtime_host="MiniPC",
            runtime_commit="a1b2c3d4e5f6",
            real_source_readback_sha256="a" * 64,
            correction_readback_sha256="b" * 64,
            rights_readback_sha256="c" * 64,
        ),
        **changes,
    )


def trusted(*_args):
    """An intentionally fake acceptance verifier, never real authorization."""
    return True


def plan(
    *,
    manifests=None,
    pilot_proof=None,
    verifier=trusted,
    costs=None,
    watches=None,
    checkpoint=None,
    policy=None,
    state=None,
    fx=None,
    **changes,
):
    manifests = manifests or two()
    dcosts, dwatches = resources(manifests)
    policy = policy or MonthlyEurPolicy(
        version="synthetic:budget:v1", cap_eur=Decimal("1.00"), enabled=True
    )
    state = state or MonthlyBudgetState(
        period=PERIOD, policy_version=policy.version, revision=0
    )
    fx = (
        fx
        if fx is not None
        else MonthlyFxQuote(
            Decimal("0.90"), "test:fx:ref", "synthetic:fx", NOW - timedelta(minutes=5)
        )
    )
    return plan_historical_batch(
        manifests=manifests,
        at=NOW,
        scope_id="history:it-de",
        pilot=pilot_proof if pilot_proof is not None else pilot(),
        verify_pilot=verifier,
        costs=dcosts if costs is None else costs,
        watches=dwatches if watches is None else watches,
        monthly_policy=policy,
        monthly_state=state,
        fx_quote=fx,
        legacy_policy=BudgetPolicy(),
        legacy_snapshots={
            e.content_id: CostSnapshot(0, 0) for m in manifests for e in m.entries
        },
        checkpoint=checkpoint,
        **changes,
    )


class HistoricalBatchGateTests(unittest.TestCase):
    def test_no_external_verifier_or_unsigned_pilot_blocks_before_budget(self):
        for kwargs in (
            {"verifier": None},
            {"pilot_proof": pilot(signature="")},
            {"pilot_proof": pilot(decision="NO_GO")},
        ):
            with self.subTest(kwargs=kwargs):
                result = plan(**kwargs)
                self.assertEqual(result.status, "HELD")
                self.assertFalse(result.dispatch_authorized)
                self.assertEqual(result.proposals, ())
                self.assertIsNone(result.proposed_budget_state)

    def test_positive_callback_means_consistency_only_never_signed_acceptance_claim(
        self,
    ):
        result = plan()
        self.assertEqual(result.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(result.proposals), 2)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.pilot_accepted_by_system)
        self.assertFalse(result.public_eligible)
        self.assertEqual(result.coverage_state, "SCOPED_UNVERIFIED")
        self.assertIsNotNone(result.proposed_budget_state)

    def test_forged_scope_and_untrusted_false_verifier_fail_closed(self):
        for kwargs in (
            {"pilot_proof": pilot(scope="other")},
            {"verifier": lambda *_: False},
            {"verifier": lambda *_: (_ for _ in ()).throw(RuntimeError("unavailable"))},
        ):
            result = plan(**kwargs)
            self.assertEqual(result.status, "HELD")
            self.assertEqual(result.proposals, ())

    def test_unknown_rights_from_dp243_blocks_all_or_nothing(self):
        m = list(two())
        bad = replace(m[1].entries[0], rights_record=None)
        m[1] = replace(m[1], entries=(bad,))
        result = plan(manifests=tuple(m))
        self.assertIn("DP243_ENTRY_HELD", result.holds)
        self.assertEqual(result.proposals, ())
        self.assertIsNone(result.proposed_budget_state)

    def test_unknown_cost_policy_expired_fx_or_monthly_cap_blocks_all(self):
        costs, _ = resources()
        scenarios = (
            {"costs": costs[:1]},
            {"costs": (replace(costs[0], upper_bound_usd=None), costs[1])},
            {"policy": MonthlyEurPolicy("synthetic:budget:v1", Decimal("1.00"))},
            {
                "policy": MonthlyEurPolicy(
                    "synthetic:budget:v1", Decimal("0.06"), enabled=True
                )
            },
            {"fx_quote": None},
        )
        for changed in scenarios:
            with self.subTest(changed=changed):
                # Distinguish explicit None FX from default fixture helper.
                if changed == {"fx_quote": None}:
                    result = plan(
                        fx=MonthlyFxQuote(
                            Decimal("0.9"), "fx", "synthetic", NOW - timedelta(days=2)
                        )
                    )
                else:
                    result = plan(**changed)
                self.assertEqual(result.status, "HELD")
                self.assertEqual(result.proposals, ())

    def test_watch_readiness_and_backoff_block_private_batch(self):
        _, watches = resources()
        bad = replace(
            watches[0], readiness=replace(watches[0].readiness, budget_status="UNKNOWN")
        )
        decision = plan(watches=(bad, watches[1]))
        self.assertEqual(decision.status, "HELD")
        self.assertTrue(any("WATCH_" in code for code in decision.holds))
        self.assertEqual(decision.proposals, ())

    def test_duplicate_capture_and_person_source_key_stable_under_order(self):
        first = plan()
        second = plan(manifests=tuple(reversed(two())))
        self.assertEqual(first.batch_id, second.batch_id)
        self.assertEqual(first.proposals, second.proposals)
        self.assertEqual(
            len({p.item_key for p in first.proposals}), len(first.proposals)
        )
        self.assertEqual(first.proposed_budget_state, second.proposed_budget_state)

    def test_checkpoint_halfway_crash_skips_only_trusted_committed(self):
        initial = plan()
        first = initial.proposals[0]
        receipt = CompletedCapture(
            item_key=first.item_key,
            person_id=first.person_id,
            content_id=first.content_id,
            source_family=first.source_family,
            capture_sha256=first.capture_sha256,
            persisted_receipt_sha256="e" * 64,
        )
        checkpoint = create_checkpoint(
            batch_id=initial.batch_id,
            manifest_fingerprint=initial.manifest_fingerprint,
            completed=(receipt,),
            revision=3,
        )
        held = plan(checkpoint=checkpoint)
        self.assertEqual(held.status, "HELD")
        self.assertIn("CHECKPOINT_EXTERNAL_TRUST_REQUIRED", held.holds)
        resume = plan(checkpoint=checkpoint, verify_checkpoint=lambda *_: True)
        self.assertEqual(resume.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(resume.proposals), 1)
        self.assertNotEqual(resume.proposals[0].item_key, first.item_key)
        self.assertFalse(resume.dispatch_authorized)

    def test_checkpoint_tamper_mixed_batch_and_failed_state_block(self):
        initial = plan()
        checkpoint = create_checkpoint(
            initial.batch_id, initial.manifest_fingerprint, (), revision=1
        )
        for changed in (
            replace(checkpoint, integrity_sha256="0" * 64),
            replace(checkpoint, batch_id="batch:wrong"),
            replace(checkpoint, failed=True),
        ):
            with self.subTest(changed=changed):
                result = plan(checkpoint=changed, verify_checkpoint=lambda *_: True)
                self.assertEqual(result.status, "HELD")
                self.assertEqual(result.proposals, ())

    def test_failed_external_pilot_verifier_never_commits_cost_proposal(self):
        first = plan()
        denied = plan(verifier=lambda *_: False)
        self.assertIsNone(denied.proposed_budget_state)
        self.assertEqual(first.proposed_budget_state.revision, 2)

    def test_checkpoint_foreign_person_and_capture_cannot_claim_done(self):
        baseline = plan()
        first = baseline.proposals[0]
        receipt = CompletedCapture(
            item_key=first.item_key,
            person_id="synthetic:other-person",
            content_id=first.content_id,
            source_family=first.source_family,
            capture_sha256=first.capture_sha256,
            persisted_receipt_sha256="e" * 64,
        )
        state = create_checkpoint(
            baseline.batch_id, baseline.manifest_fingerprint, (receipt,), revision=1
        )
        decision = plan(checkpoint=state, verify_checkpoint=lambda *_: True)
        self.assertEqual(decision.proposals, ())
        self.assertIn("CHECKPOINT_FOREIGN_ITEM", decision.holds)
        other_receipt = replace(
            receipt, person_id=first.person_id, capture_sha256="f" * 64
        )
        state = create_checkpoint(
            baseline.batch_id,
            baseline.manifest_fingerprint,
            (other_receipt,),
            revision=1,
        )
        self.assertIn(
            "CHECKPOINT_FOREIGN_ITEM",
            plan(checkpoint=state, verify_checkpoint=lambda *_: True).holds,
        )

    def test_duplicate_replay_checkpoint_and_new_revision_no_double_budget(self):
        baseline = plan()
        records = tuple(
            sorted(
                (
                    CompletedCapture(
                        p.item_key,
                        p.person_id,
                        p.content_id,
                        p.source_family,
                        p.capture_sha256,
                        "e" * 64,
                    )
                    for p in baseline.proposals
                ),
                key=lambda record: record.item_key,
            )
        )
        state = create_checkpoint(
            baseline.batch_id, baseline.manifest_fingerprint, records, revision=2
        )
        decision = plan(checkpoint=state, verify_checkpoint=lambda *_: True)
        self.assertEqual(decision.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(decision.proposals, ())
        self.assertIsNone(decision.proposed_budget_state)
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_DUPLICATE"):
            create_checkpoint(
                baseline.batch_id,
                baseline.manifest_fingerprint,
                (records[0], records[0]),
                revision=3,
            )

    def test_same_capture_in_archive_copy_cannot_be_double_charged(self):
        root = entry()
        copy = entry(
            content_id="synthetic:archive",
            kind="ARCHIVE_COPY",
            origin_content_id=root.content_id,
            origin_sha256=root.source_version_sha256,
        )
        manifests = (manifest("MUSSOLINI", (root, copy)), two()[1])
        decision = plan(manifests=manifests)
        self.assertEqual(decision.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(decision.proposals), 2)
        self.assertEqual(
            {p.content_id for p in decision.proposals},
            {root.content_id, two()[1].entries[0].content_id},
        )

    def test_watch_says_unchanged_without_committed_capture_requires_checkpoint(self):
        _, watches = resources()
        unchanged = replace(
            watches[0],
            state=replace(
                watches[0].state,
                policy_fingerprint=policy_fingerprint(watches[0].policy),
                content_sha256=two()[0].entries[0].source_version_sha256,
                last_successful_observed_at=NOW - timedelta(hours=1),
            ),
        )
        result = plan(watches=(unchanged, watches[1]))
        self.assertEqual(result.status, "HELD")
        self.assertIn("WATCH_OBSERVED_CAPTURE_NOT_CHECKPOINTED", result.holds)
        self.assertEqual(result.proposals, ())

    def test_revisions_require_dp243_revalidation_before_batch(self):
        first = two()[0]
        changed = replace(first.entries[0], exact_locator=None)
        manifests = (replace(first, entries=(changed,)), two()[1])
        result = plan(manifests=manifests)
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.proposals, ())


if __name__ == "__main__":
    unittest.main()

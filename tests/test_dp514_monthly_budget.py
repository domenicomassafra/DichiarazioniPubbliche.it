"""DP-514 isolated monthly EUR reservation contract; no live dispatch/store."""

import sys
from concurrent.futures import ThreadPoolExecutor
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Lock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.cost_policy import (  # noqa: E402
    BudgetPolicy,
    CostSnapshot,
    MonthlyBudgetState,
    MonthlyEurPolicy,
    MonthlyFxQuote,
    monthly_budget_preflight,
    monthly_period,
)


class MonthlyBudgetTests(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        self.policy = MonthlyEurPolicy(
            version="owner-test-v1", cap_eur=Decimal("10"), enabled=True,
            timezone_name="Europe/Rome",
        )
        self.state = MonthlyBudgetState(
            period=monthly_period(self.time, self.policy.timezone_name),
            policy_version=self.policy.version, revision=0,
        )
        self.fx = MonthlyFxQuote(
            rate_eur_per_usd=Decimal("0.9000"), reference="offline-quote-1",
            source="test-explicit-rate", observed_at=self.time - timedelta(hours=1),
        )
        self.usd_policy = BudgetPolicy()
        self.usd_snapshot = CostSnapshot(0, 0)

    def decide(self, **kwargs):
        fields = {
            "policy": self.policy, "state": self.state,
            "attempt_id": "job:1:attempt:1", "operation": "CLAIM_EXTRACT",
            "upper_bound_usd": Decimal("0.20"), "billing_basis": "ESTIMATED_ONLY",
            "at": self.time, "fx_quote": self.fx,
            "legacy_policy": self.usd_policy,
            "legacy_snapshot": self.usd_snapshot,
            "expected_revision": self.state.revision,
        }
        fields.update(kwargs)
        return monthly_budget_preflight(**fields)

    def test_disabled_by_default_and_never_grants_dispatch(self):
        self.assertFalse(MonthlyEurPolicy(version="planned", cap_eur=Decimal("10")).enabled)
        disabled = self.decide(policy=replace(self.policy, enabled=False))
        self.assertFalse(disabled.eligible)
        self.assertEqual(disabled.reason, "MONTHLY_POLICY_DISABLED")
        permitted = self.decide()
        self.assertTrue(permitted.eligible)
        self.assertEqual(permitted.reason, "MONTHLY_RESERVATION_PROPOSED")
        self.assertFalse(permitted.dispatch_authorized)
        self.assertEqual(permitted.expected_revision, 0)
        self.assertEqual(permitted.proposed_state.revision, 1)
        self.assertEqual(permitted.proposed_state.reservations[0].held_eur, Decimal("0.180000"))
        self.assertEqual(permitted.proposed_state.held_total_eur, Decimal("0.180000"))
        self.assertEqual(self.state.revision, 0)
        self.assertEqual(self.state.reservations, ())
        self.assertEqual(permitted.proposed_state.reservations[0].fx_reference, "offline-quote-1")
        self.assertEqual(permitted.proposed_state.reservations[0].fx_rate_eur_per_usd, Decimal("0.9000"))
        self.assertEqual(len(permitted.expected_state_sha256), 64)

    def test_tight_monthly_cap_proposes_one_then_defers_next(self):
        tight = replace(self.policy, cap_eur=Decimal("0.25"))
        first = self.decide(policy=tight)
        self.assertTrue(first.eligible)
        second = self.decide(
            policy=tight, state=first.proposed_state, expected_revision=1,
            attempt_id="job:2:attempt:1",
        )
        self.assertFalse(second.eligible)
        self.assertEqual(second.reason, "MONTHLY_CAP_REACHED")
        self.assertIsNone(second.proposed_state)

    def test_stale_compare_revision_and_replay_never_create_second_hold(self):
        first = self.decide()
        # A different worker read revision zero before the first proposal
        # reached a hypothetical *external atomic* compare-and-swap store.
        second_proposal = self.decide(attempt_id="job:2:attempt:1")
        self.assertTrue(second_proposal.eligible)
        self.assertEqual(first.expected_revision, second_proposal.expected_revision)
        self.assertFalse(second_proposal.dispatch_authorized)
        stale = self.decide(
            state=first.proposed_state, attempt_id="job:2:attempt:1",
            expected_revision=0,
        )
        self.assertFalse(stale.eligible)
        self.assertEqual(stale.reason, "MONTHLY_STATE_REVISION_STALE")
        replay = self.decide(
            state=first.proposed_state, attempt_id="job:1:attempt:1",
            expected_revision=1,
        )
        self.assertFalse(replay.eligible)
        self.assertEqual(replay.reason, "MONTHLY_RESERVATION_ALREADY_RECORDED")
        self.assertIsNone(replay.proposed_state)
        conflict = self.decide(
            state=first.proposed_state, attempt_id="job:1:attempt:1",
            upper_bound_usd=Decimal("0.19"), expected_revision=1,
        )
        self.assertEqual(conflict.reason, "MONTHLY_ATTEMPT_ID_CONFLICT")

    def test_two_worker_proposals_require_atomic_external_compare_and_swap(self):
        """An *example* atomic owner accepts one proposal; the pure gate accepts both.

        This is not a database/prod concurrency claim. Real persistence must
        provide an equivalent transaction before any operation is dispatched.
        """
        tight = replace(self.policy, cap_eur=Decimal("0.18"))
        barrier = Barrier(2)
        lock = Lock()
        current = [self.state]
        outcomes = []

        def worker(attempt_id):
            stale_snapshot = current[0]
            proposal = self.decide(
                state=stale_snapshot, policy=tight,
                attempt_id=attempt_id, expected_revision=stale_snapshot.revision,
            )
            self.assertTrue(proposal.eligible)
            barrier.wait(timeout=5)
            with lock:  # only this hypothetical owner has the atomic CAS
                if (current[0].revision, current[0].fingerprint()) == (
                    proposal.expected_revision, proposal.expected_state_sha256
                ):
                    current[0] = proposal.proposed_state
                    outcomes.append("CAS_COMMITTED")
                else:
                    outcomes.append("CAS_CONFLICT")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, f"job:{n}:attempt:1") for n in (1, 2)]
            for future in futures:
                future.result()
        self.assertCountEqual(outcomes, ("CAS_COMMITTED", "CAS_CONFLICT"))
        self.assertEqual(current[0].held_total_eur, Decimal("0.180000"))
        self.assertEqual(current[0].revision, 1)
        rejected = self.decide(
            state=current[0], policy=tight, expected_revision=1,
            attempt_id="job:3:attempt:1",
        )
        self.assertEqual(rejected.reason, "MONTHLY_CAP_REACHED")

    def test_existing_usd_caps_are_separate_and_restrictive(self):
        for snapshot, amount, reason in (
            (CostSnapshot(0, 0), Decimal("0.30"), "JOB_COST_CAP_REACHED"),
            (CostSnapshot(4.95, 0), Decimal("0.20"), "GLOBAL_DAILY_BUDGET_REACHED"),
            (CostSnapshot(0, 0.90), Decimal("0.20"), "SOURCE_DAILY_BUDGET_REACHED"),
        ):
            with self.subTest(reason=reason):
                decision = self.decide(legacy_snapshot=snapshot, upper_bound_usd=amount)
                self.assertFalse(decision.eligible)
                self.assertEqual(decision.reason, reason)

    def test_unknown_zero_plan_billed_or_non_finite_cost_hold(self):
        for basis, amount in (
            ("UNKNOWN", None), ("UNKNOWN", Decimal("0.10")),
            ("EXTERNAL_PLAN", Decimal("0")), ("MEASURED_PROVIDER_COST", Decimal("0.10")),
            ("ESTIMATED_ONLY", None), ("ESTIMATED_ONLY", Decimal("0")),
            ("ZERO_COST", Decimal("0")), ("ESTIMATED_ONLY", Decimal("-0.1")),
            ("ESTIMATED_ONLY", Decimal("NaN")),
        ):
            with self.subTest(basis=basis, amount=amount):
                d = self.decide(billing_basis=basis, upper_bound_usd=amount)
                self.assertFalse(d.eligible)
                self.assertIsNone(d.proposed_state)

    def test_unknown_prior_liability_blocks_even_with_room_in_cap(self):
        d = self.decide(state=replace(self.state, unknown_liability=True))
        self.assertEqual(d.reason, "MONTHLY_UNKNOWN_LIABILITY")
        self.assertFalse(d.eligible)

    def test_fresh_documented_fx_required_no_guessed_conversion(self):
        self.assertEqual(self.decide(fx_quote=None).reason, "MONTHLY_FX_REQUIRED")
        self.assertEqual(
            self.decide(
                fx_quote=replace(self.fx, observed_at=self.time - timedelta(days=2))
            ).reason,
            "MONTHLY_FX_STALE",
        )
        self.assertEqual(
            self.decide(
                fx_quote=replace(self.fx, observed_at=self.time + timedelta(seconds=1))
            ).reason,
            "MONTHLY_FX_FROM_FUTURE",
        )
        self.assertTrue(self.decide(policy=replace(self.policy, cap_eur=Decimal("0.18"))).eligible)
        rounded = self.decide(
            fx_quote=replace(self.fx, rate_eur_per_usd=Decimal("0.900001")),
            policy=replace(self.policy, cap_eur=Decimal("0.180000")),
        )
        self.assertEqual(rounded.reason, "MONTHLY_CAP_REACHED")

    def test_timezone_midnight_dst_and_calendar_boundary_are_explicit(self):
        rome = "Europe/Rome"
        utc = "UTC"
        previous = datetime(2026, 10, 31, 22, 59, tzinfo=timezone.utc)
        next_month_rome = previous + timedelta(minutes=1)
        self.assertEqual(monthly_period(previous, rome), "2026-10@Europe/Rome")
        self.assertEqual(monthly_period(next_month_rome, rome), "2026-11@Europe/Rome")
        self.assertEqual(monthly_period(next_month_rome, utc), "2026-10@UTC")
        # Spring transition UTC 01:00 jumps Rome 02:00 -> 03:00;
        # October repeated wall hour does not roll a month.
        self.assertEqual(
            monthly_period(datetime(2026, 3, 29, 1, 15, tzinfo=timezone.utc), rome),
            "2026-03@Europe/Rome",
        )
        self.assertEqual(
            monthly_period(datetime(2026, 10, 25, 1, 15, tzinfo=timezone.utc), rome),
            "2026-10@Europe/Rome",
        )
        self.assertEqual(
            self.decide(
                at=next_month_rome,
                fx_quote=replace(self.fx, observed_at=next_month_rome),
            ).reason,
            "MONTHLY_PERIOD_MISMATCH",
        )

    def test_snapshot_policy_conflict_and_invalid_state_fail_closed(self):
        self.assertEqual(
            self.decide(policy=replace(self.policy, version="new-policy")).reason,
            "MONTHLY_POLICY_VERSION_MISMATCH",
        )
        with self.assertRaises(ValueError):
            replace(self.state, settled_eur=Decimal("-0.1"))
        with self.assertRaises(ValueError):
            replace(self.state, revision=-1)
        with self.assertRaises(ValueError):
            MonthlyFxQuote(
                rate_eur_per_usd=Decimal("NaN"), reference="r",
                source="s", observed_at=self.time,
            )
        with self.assertRaises(ValueError):
            monthly_period(self.time.replace(tzinfo=None), "UTC")
        with self.assertRaises(ValueError):
            monthly_period(self.time, "Unknown/Timezone")


if __name__ == "__main__":
    unittest.main()

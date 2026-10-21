"""DP-516 rejects untrusted metadata hooks before planning synthetic work."""

import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.historical_batch_gate_v1 import (
    BatchCheckpoint,
    BatchCost,
    BatchPilotAcceptance,
    BatchWatch,
    CompletedCapture,
    create_checkpoint,
)
from dichiarazioni_pubbliche.incremental_source_watch import WatchReadiness

from tests.test_dp516_historical_batch_gate import pilot, plan, resources


class PoisonCost(BatchCost):
    def __getattribute__(self, key):
        if key == "content_id":
            raise AssertionError("DP516_COST_SUBCLASS_READ")
        return object.__getattribute__(self, key)


class PoisonWatch(BatchWatch):
    def __getattribute__(self, key):
        if key == "content_id":
            raise AssertionError("DP516_WATCH_SUBCLASS_READ")
        return object.__getattribute__(self, key)


class ForgedReadiness(WatchReadiness):
    def __getattribute__(self, key):
        if key == "rights_status":
            return "READY"
        return object.__getattribute__(self, key)


class LieReady(str):
    def __eq__(self, other):
        return other == "READY" if isinstance(other, str) else False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash("READY")


class SpoofPilot(BatchPilotAcceptance):
    def __getattribute__(self, key):
        if key == "decision":
            return "GO_FOR_SCALING"
        return object.__getattribute__(self, key)


class PoisonReceipt(CompletedCapture):
    def __getattribute__(self, key):
        if key == "item_key":
            raise AssertionError("DP516_CHECKPOINT_RECEIPT_READ")
        return object.__getattribute__(self, key)


class PoisonCheckpoint(BatchCheckpoint):
    def __getattribute__(self, key):
        if key == "batch_id":
            raise AssertionError("DP516_CHECKPOINT_SUBCLASS_READ")
        return object.__getattribute__(self, key)


class MetadataBoundaryTests(unittest.TestCase):
    def assert_held(self, result, blocker):
        self.assertEqual(result.status, "HELD")
        self.assertIn(blocker, result.holds)
        self.assertEqual(result.proposals, ())
        self.assertIsNone(result.proposed_budget_state)
        self.assertFalse(result.dispatch_authorized)

    def test_cost_and_watch_dataclass_subclasses_cannot_read_fields(self):
        costs, watches = resources()
        for field, values, cls, reason in (
            ("costs", costs, PoisonCost, "BATCH_COST_DUPLICATE_OR_INVALID"),
            ("watches", watches, PoisonWatch, "BATCH_WATCH_DUPLICATE_OR_INVALID"),
        ):
            with self.subTest(field=field):
                hostile = cls(**values[0].__dict__)
                decision = plan(**{field: (hostile, values[1])})
                self.assert_held(decision, reason)

    def test_revoked_nested_readiness_subclass_cannot_spoof_ready(self):
        _, watches = resources()
        revoked = replace(watches[0].readiness, rights_status="REVOKED")
        control = plan(watches=(replace(watches[0], readiness=revoked), watches[1]))
        self.assert_held(control, "WATCH_RIGHTS_NOT_READY")
        hostile = ForgedReadiness(**revoked.__dict__)
        decision = plan(watches=(replace(watches[0], readiness=hostile), watches[1]))
        self.assert_held(decision, "BATCH_WATCH_DUPLICATE_OR_INVALID")

    def test_revoked_string_subclass_cannot_spoof_ready(self):
        _, watches = resources()
        forged = replace(watches[0].readiness, rights_status=LieReady("REVOKED"))
        self.assertEqual(str(forged.rights_status), "REVOKED")
        decision = plan(watches=(replace(watches[0], readiness=forged), watches[1]))
        self.assert_held(decision, "BATCH_WATCH_DUPLICATE_OR_INVALID")

    def test_spoofed_pilot_and_checkpoint_subclasses_hold_without_hooks(self):
        fake_no_go = SpoofPilot(**replace(pilot(), decision="NO_GO").__dict__)
        self.assert_held(
            plan(pilot_proof=fake_no_go),
            "DP443_PILOT_SIGNED_ACCEPTANCE_REQUIRED",
        )
        hostile_checkpoint = PoisonCheckpoint(
            "batch:test", "a" * 64, (), 0, False, "b" * 64
        )
        self.assert_held(plan(checkpoint=hostile_checkpoint), "CHECKPOINT_INVALID")

    def test_checkpoint_receipt_subclass_rejected_before_field_access(self):
        receipt = PoisonReceipt(
            "item:test",
            "person:test",
            "content:test",
            "source:test",
            "a" * 64,
            "b" * 64,
        )
        with self.assertRaisesRegex(ValueError, "DP516_CHECKPOINT_SHAPE_INVALID"):
            create_checkpoint("batch:test", "c" * 64, (receipt,), revision=0)

    def test_cyclic_exact_readiness_record_is_held(self):
        _, watches = resources()
        cyclic = replace(watches[0].readiness)
        object.__setattr__(cyclic, "source_id", cyclic)
        decision = plan(watches=(replace(watches[0], readiness=cyclic), watches[1]))
        self.assert_held(decision, "BATCH_WATCH_DUPLICATE_OR_INVALID")

    def test_unmodified_records_still_propose_private_review(self):
        costs, watches = resources()
        result = plan(costs=costs, watches=watches)
        self.assertEqual(result.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(result.proposals), 2)
        self.assertFalse(result.dispatch_authorized)

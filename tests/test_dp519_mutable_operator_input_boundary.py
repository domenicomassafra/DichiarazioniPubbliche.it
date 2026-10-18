"""DP-519 refuses mutable subclass metadata that can change after validation."""

import unittest
from dataclasses import asdict

from dichiarazioni_pubbliche.visual_operator_capacity_v1 import (
    VisualDecisionEvent, VisualException, VisualWorkItem, reconcile_visual_capacity,
)
from tests.test_dp519_visual_operator_capacity import NOW, event, exception, work


class MutableOperatorInputBoundaryTests(unittest.TestCase):
    def test_changed_work_estimate_cannot_bypass_bounded_plan(self):
        class MutableWork(VisualWorkItem):
            def __getattribute__(self, name):
                if name == "estimated_minutes":
                    values = object.__getattribute__(self, "__dict__")
                    count = values.setdefault("_reads", 0)
                    values["_reads"] = count + 1
                    return 12 if count == 0 else 300
                return super().__getattribute__(name)

        item = MutableWork(**asdict(work()))
        with self.assertRaisesRegex(ValueError, "DP519_WORK_ITEM_INVALID"):
            reconcile_visual_capacity((item,), (), (), now=NOW)

    def test_mutable_operator_receipt_cannot_change_after_time_validation(self):
        class MutableEvent(VisualDecisionEvent):
            pass

        item = work()
        forged = MutableEvent(**asdict(event(item)))
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_INVALID"):
            reconcile_visual_capacity((item,), (forged,), (), now=NOW)

    def test_mutable_exception_cannot_change_authority_or_attempts(self):
        class MutableException(VisualException):
            pass

        item = work("x")
        forged = MutableException(**asdict(exception("x")))
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_INVALID"):
            reconcile_visual_capacity((item,), (), (forged,), now=NOW)

"""DP-319 refuses subclass-controlled source/rights inputs before persistence."""

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from dichiarazioni_pubbliche.investigation_attempts_store_v1 import (
    InvestigationSourceRecord, InvestigationSQLiteStore, _assert_inputs,
)
from dichiarazioni_pubbliche.investigation_attempts_v1 import InvestigationObservation, InvestigationSpec
from dichiarazioni_pubbliche.research_plan import ResearchAssignment
from tests.test_dp319_durable_investigation_next import observed, source
from tests.test_dp319_investigation_attempts import assignment, spec


class StoreInputTypeBoundaryTests(unittest.TestCase):
    def test_subclassed_source_cannot_be_recorded_as_independent_rights(self):
        class MutableSource(InvestigationSourceRecord):
            pass

        with tempfile.TemporaryDirectory() as tmp:
            store = InvestigationSQLiteStore(Path(tmp) / "ledger.sqlite")
            forged = MutableSource(**asdict(source()))
            with self.assertRaisesRegex(ValueError, "INVESTIGATION_STORE_SOURCE_INVALID"):
                store.record_source(forged, expected_revision=0)

    def test_subclassed_spec_and_assignment_cannot_bind_cost_scope(self):
        class MutableSpec(InvestigationSpec):
            pass

        class MutableAssignment(ResearchAssignment):
            pass

        original_spec = spec()
        original_assignment = assignment()
        current = source()
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_STORE_INPUT_INVALID"):
            _assert_inputs(MutableSpec(**asdict(original_spec)), (original_assignment,), current)
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_STORE_ASSIGNMENTS_INVALID"):
            _assert_inputs(original_spec, (MutableAssignment(**asdict(original_assignment)),), current)

    def test_subclassed_completion_cannot_change_cost_or_result_during_audit(self):
        class MutableObservation(InvestigationObservation):
            pass

        with tempfile.TemporaryDirectory() as tmp:
            store = InvestigationSQLiteStore(Path(tmp) / "ledger.sqlite")
            current = source()
            claim = spec()
            assignments = (assignment(),)
            store.record_source(current, expected_revision=0)
            store.register(claim, assignments, current)
            reserved = store.reserve(
                claim, assignments, current, key="request:cost:one", expected_revision=0,
            )
            proof = MutableObservation(**asdict(observed(reserved.reservations[0])))
            with self.assertRaisesRegex(ValueError, "INVESTIGATION_STORE_OBSERVATION_INVALID"):
                store.complete(
                    claim, assignments, current,
                    observation=proof, key="request:cost:one",
                    expected_revision=reserved.revision,
                )

"""DP-242: persisted Studio readback to held machine handoff, never approval."""

import json
import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.multi_person_batch_v1 import (
    PrivateBatchResult,
    build_private_batch_receipt_index,
)

from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import (
    DiscoveryInboxWorkflow,
)
from dichiarazioni_pubbliche.studio_machine_candidate_handoff_v1 import (
    CurrentBatchStudioItem,
    preview_private_batch_machine_handoff,
    preview_candidate_machine_handoff,
    preview_discovery_machine_exception,
)
from tests.test_dp240_multi_person_batch import (
    manifest as dp240_manifest,
    plan as dp240_plan,
    reviewed_contexts as dp240_contexts,
)
from tests.test_studio_discovery_inbox_workflow import FakeRuntime, row
from tests.test_studio_candidate_review_handoff import MatchStore, PromotionContext


class DiscoveryPreviewTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime([row()])
        self.workflow = DiscoveryInboxWorkflow(self.runtime)
        self.original = self.workflow.list_rows(collection_id="collection:01")["rows"][
            0
        ]

    def preview(self, **changes):
        args = dict(
            collection_id="collection:01",
            hit_id="hit:01",
            request_key="task:01",
            expected_revision=0,
            expected_snapshot_sha256=self.original["snapshot_sha256"],
        )
        return preview_discovery_machine_exception(self.workflow, **(args | changes))

    def test_private_bounded_real_selected_sql_twice_and_stable_replay(self):
        receipt = self.preview()
        self.assertEqual(receipt["status"], "HELD_EXCEPTION")
        self.assertEqual(receipt["action"], "REVALIDATE_RIGHTS_AND_AUTHORITY")
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertFalse(receipt["publication_authority"])
        self.assertEqual(receipt["provenance"]["hit_id"], "hit:01")
        self.assertEqual(len(self.runtime.calls), 3)
        self.assertTrue(
            all("selected_ids" in bindings for _, bindings in self.runtime.calls[-2:])
        )
        self.assertNotIn("task:01", json.dumps(receipt))
        self.assertNotIn("PRIVATE QUERY", json.dumps(receipt))
        self.assertEqual(receipt, self.preview())

    def test_refuses_stale_revision_snapshot_wrong_scope_and_revoked_rights(self):
        for args, code in (
            (dict(expected_revision=1), "REVISION_CONFLICT"),
            (dict(expected_snapshot_sha256="f" * 64), "SNAPSHOT_CHANGED"),
            (dict(collection_id="other"), "SCOPE_NOT_FOUND"),
            (dict(hit_id="other"), "SCOPE_NOT_FOUND"),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, code):
                self.preview(**args)
        self.runtime.rows[0]["rights_state"] = "REVOKED"
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_CHANGED"):
            self.preview()

    def test_mutation_between_rechecks_fails_closed(self):
        class Mutating(FakeRuntime):
            def run(self, sql, **params):
                result = super().run(sql, **params)
                if (
                    "selected_ids" in params
                    and sum("selected_ids" in p for _, p in self.calls) == 1
                ):
                    self.rows[0]["manifest_state"] = "SUPERSEDED"
                return result

        runtime = Mutating([row()])
        snap = DiscoveryInboxWorkflow(runtime).list_rows(collection_id="collection:01")[
            "rows"
        ][0]
        with self.assertRaisesRegex(ValueError, "CHANGED_DURING_PREFLIGHT"):
            preview_discovery_machine_exception(
                DiscoveryInboxWorkflow(runtime),
                collection_id="collection:01",
                hit_id="hit:01",
                request_key="task:01",
                expected_revision=0,
                expected_snapshot_sha256=snap["snapshot_sha256"],
            )

    def test_identity_exception_specific_and_bulk_injection_denied(self):
        runtime = FakeRuntime([row(disposition="AMBIGUOUS_CONTENT_IDENTITY")])
        snap = DiscoveryInboxWorkflow(runtime).list_rows(collection_id="collection:01")[
            "rows"
        ][0]
        result = preview_discovery_machine_exception(
            DiscoveryInboxWorkflow(runtime),
            collection_id="collection:01",
            hit_id="hit:01",
            request_key="task:01",
            expected_revision=0,
            expected_snapshot_sha256=snap["snapshot_sha256"],
        )
        self.assertEqual(result["action"], "INVESTIGATE_CONTENT_IDENTITY")
        for args in (
            {"hit_id": "hit:01,hit:02"},
            {"request_key": "../path"},
            {"expected_revision": True},
        ):
            with self.assertRaises(ValueError):
                self.preview(**args)


class CandidatePreviewTests(unittest.TestCase):
    def setUp(self):
        self.match = MatchStore()
        self.promotion = PromotionContext()
        self.capture_sha = self.promotion.data["passages"][0]["capture_sha256"]
        self.args = dict(
            run_id=self.match.run_id,
            claim_candidate_id="candidate:1",
            result_id=self.match.rows[0]["id"],
            request_key="task:02",
            expected_content_id="content:1",
            expected_capture_sha256=self.capture_sha,
            expected_input_fingerprint=self.match.fingerprint,
        )

    def preview(self, **changes):
        return preview_candidate_machine_handoff(
            self.match, self.promotion, **(self.args | changes)
        )

    def test_current_match_is_held_until_new_machine_authority(self):
        result = self.preview()
        self.assertEqual(result["status"], "HELD_MACHINE_AUTHORITY_UNAVAILABLE")
        self.assertEqual(result["source"]["capture_sha256"], self.capture_sha)
        self.assertFalse(result["dispatch_authorized"])
        self.assertFalse(result["human_review_approved"])
        self.assertFalse(result["machine_review_approved"])
        self.assertNotIn("task:02", json.dumps(result))
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(result, self.preview())

    def test_mismatched_provenance_and_stale_run_refused(self):
        for arg in (
            {"expected_content_id": "content:wrong"},
            {"expected_capture_sha256": "f" * 64},
            {"expected_input_fingerprint": "f" * 64},
            {"result_id": "result:wrong"},
        ):
            with self.subTest(arg=arg), self.assertRaises(ValueError):
                self.preview(**arg)
        self.match.run["status"] = "RUNNING"
        with self.assertRaises(ValueError):
            self.preview()

    def test_rights_hold_segment_block_and_multi_passage_are_held(self):
        for change in (
            {"capture_hold_status": "RIGHTS"},
            {"capture_status": "PURGED_BODY"},
            {"segment_publication_blocked": True},
        ):
            self.promotion.data["passages"][0].update(change)
            self.assertEqual(self.preview()["status"], "HELD_SOURCE_OR_ATTRIBUTION")
            self.promotion = PromotionContext()
        self.promotion.data["passages"].append(dict(self.promotion.data["passages"][0]))
        self.assertEqual(self.preview()["status"], "HELD_SOURCE_OR_ATTRIBUTION")

    def test_invalid_actor_or_source_lineage_cannot_appear_machine_eligible(self):
        """Machine-unavailable is reserved for a coherent, source-bound candidate."""
        for field, value in (
            ("speaker_is_public", False),
            ("speaker_person_id", ""),
            ("speaker_person_id", "   "),
            ("statement_candidate_id", None),
            ("passage_count", 2),
            ("passage_count", True),
            ("written_count", 0),
            ("media_count", 1),
        ):
            with self.subTest(field=field, value=value):
                self.promotion = PromotionContext()
                self.promotion.data[field] = value
                result = self.preview()
                self.assertEqual(result["status"], "HELD_SOURCE_OR_ATTRIBUTION")
                self.assertEqual(result["action"], "INVESTIGATE_SOURCE_OR_ATTRIBUTION")
                self.assertFalse(result["dispatch_authorized"])
        for field, value in (
            ("passage_id", None),
            ("capture_id", None),
            ("canonical_segment_id", "segment:unexpected"),
        ):
            with self.subTest(field=field, value=value):
                self.promotion = PromotionContext()
                self.promotion.data["passages"][0][field] = value
                result = self.preview()
                self.assertEqual(result["status"], "HELD_SOURCE_OR_ATTRIBUTION")
                self.assertFalse(result["dispatch_authorized"])

    def test_legacy_editorial_flags_do_not_become_machine_authority(self):
        self.promotion.data["claim_candidate_reviewed"] = False
        self.promotion.data["statement_reviewed"] = False
        result = self.preview()
        self.assertEqual(result["status"], "HELD_MACHINE_AUTHORITY_UNAVAILABLE")
        self.assertFalse(result["human_review_approved"])
        self.assertFalse(result["machine_review_approved"])
        self.assertFalse(result["dispatch_authorized"])


class DP240BatchMachineHandoffTests(unittest.TestCase):
    """Private DP-240 receipts are input evidence, never machine permission."""

    @staticmethod
    def fixture():
        batch = dp240_manifest()
        contexts = dp240_contexts(batch)
        contexts["passage:0"] = replace(
            contexts["passage:0"],
            speaker_candidate_id="person-candidate:anna:a",
        )
        contexts["passage:1"] = replace(
            contexts["passage:1"],
            speaker_candidate_id="person-candidate:anna:b",
        )
        contexts["passage:2"] = replace(
            contexts["passage:2"],
            speech_role="QUOTED_SPEAKER",
            speech_act="REPORTED_QUOTE",
        )
        planned = dp240_plan(batch, contexts)
        first, second = planned.items[:2]
        result = (
            PrivateBatchResult(
                first.passage_id,
                first.content_id,
                first.capture_id,
                first.passage_sha256,
                "CANDIDATE_EXTRACTED",
                None,
                "fixture:de:v1",
            ),
            PrivateBatchResult(
                second.passage_id,
                second.content_id,
                second.capture_id,
                second.passage_sha256,
                "FAILED",
                "PRIVATE PROVIDER SECRET",
                None,
            ),
        )
        index = build_private_batch_receipt_index(planned, result)
        currents = {
            item.passage_id: CurrentBatchStudioItem(
                passage_id=item.passage_id,
                content_id=item.content_id,
                capture_id=item.capture_id,
                source_sha256=item.source_sha256,
                passage_sha256=item.passage_sha256,
                selector_fingerprint=item.selector_fingerprint,
                speaker_candidate_id=item.speaker_candidate_id,
                identity_review_status=item.identity_review_status,
                speech_role=item.speech_role,
                speech_act=item.speech_act,
                context_version=item.context_version,
                context_review_id=item.context_review_id,
                rights_status=item.rights_status,
                rights_evidence_sha256="a" * 64,
                source_revision=3,
                identity_revision=5,
                rights_revision=7,
            )
            for item in planned.items
        }
        return planned, index, currents

    def test_mixed_person_homonym_partial_failure_and_quote_get_independent_actions(
        self,
    ):
        plan, index, current = self.fixture()
        preview = preview_private_batch_machine_handoff(
            plan,
            index,
            current_items=current,
            request_key="operator:dp240:1",
            expected_receipt_sha256=index.receipt_sha256,
        )
        self.assertEqual(preview["family"], "DP240_PRIVATE_CANDIDATE_BATCH")
        self.assertEqual(len(preview["items"]), 3)
        self.assertEqual(
            [row["status"] for row in preview["items"]],
            [
                "HELD_MACHINE_AUTHORITY_UNAVAILABLE",
                "HELD_EXTRACTION_FAILED",
                "HELD_SOURCE_OR_ATTRIBUTION",
            ],
        )
        self.assertEqual(
            [row["action"] for row in preview["items"]],
            [
                "AWAIT_INDEPENDENT_B_MACHINE_AUTHORITY",
                "INVESTIGATE_FAILED_EXTRACTION",
                "INVESTIGATE_QUOTED_SPEAKER_NOT_ENDORSEMENT",
            ],
        )
        self.assertEqual(preview["summary"]["exception_count"], 2)
        self.assertEqual(preview["summary"]["authority_pending_count"], 1)
        self.assertNotEqual(
            preview["items"][0]["source"]["speaker_candidate_id"],
            preview["items"][1]["source"]["speaker_candidate_id"],
        )
        self.assertEqual(preview["items"][0]["source"]["content_id"], "content:0")
        self.assertEqual(preview["items"][1]["source"]["language_tag"], "de")
        self.assertEqual(preview["items"][2]["source"]["speech_role"], "QUOTED_SPEAKER")
        self.assertEqual(preview["items"][0]["source"]["rights_revision"], 7)
        self.assertEqual(preview["items"][0]["source"]["source_revision"], 3)
        self.assertEqual(
            preview,
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items=current,
                request_key="operator:dp240:1",
                expected_receipt_sha256=index.receipt_sha256,
            ),
        )
        self.assertFalse(preview["dispatch_authorized"])
        self.assertFalse(preview["publication_authority"])
        self.assertFalse(preview["machine_review_approved"])
        self.assertFalse(preview["human_review_approved"])
        self.assertNotIn("PRIVATE PROVIDER SECRET", json.dumps(preview))
        self.assertNotIn("operator:dp240:1", json.dumps(preview))

    def test_current_source_rights_and_identity_drift_are_separately_actionable(self):
        plan, index, current = self.fixture()
        tampered = {
            **current,
            "passage:0": replace(
                current["passage:0"],
                source_sha256="f" * 64,
            ),
            "passage:1": replace(
                current["passage:1"],
                rights_status="REVOKED",
            ),
            "passage:2": replace(
                current["passage:2"],
                speaker_candidate_id="person-candidate:other",
            ),
        }
        preview = preview_private_batch_machine_handoff(
            plan,
            index,
            current_items=tampered,
            request_key="operator:dp240:2",
            expected_receipt_sha256=index.receipt_sha256,
        )
        self.assertEqual(
            [row["status"] for row in preview["items"]],
            [
                "HELD_STALE_SOURCE",
                "HELD_SOURCE_RIGHTS",
                "HELD_IDENTITY_CHANGED",
            ],
        )
        self.assertEqual(
            [row["action"] for row in preview["items"]],
            [
                "REFRESH_CAPTURE_PASSAGE_AND_REPLAN",
                "REVALIDATE_SOURCE_RIGHTS",
                "RECHECK_SPEAKER_PERSON_AND_CONTEXT",
            ],
        )
        self.assertEqual(preview["summary"]["exception_count"], 3)
        missing = preview_private_batch_machine_handoff(
            plan,
            index,
            current_items={"passage:0": current["passage:0"]},
            request_key="operator:dp240:missing",
            expected_receipt_sha256=index.receipt_sha256,
        )
        self.assertEqual(missing["items"][1]["status"], "HELD_CURRENT_READBACK_MISSING")
        no_rights_proof = dict(current)
        no_rights_proof["passage:0"] = replace(
            current["passage:0"],
            rights_evidence_sha256=None,
        )
        rights = preview_private_batch_machine_handoff(
            plan,
            index,
            current_items=no_rights_proof,
            request_key="operator:dp240:rights",
            expected_receipt_sha256=index.receipt_sha256,
        )
        self.assertEqual(rights["items"][0]["status"], "HELD_RIGHTS_EVIDENCE_MISSING")

    def test_scope_lookalike_cannot_borrow_content_or_capture_and_changes_intent(self):
        plan, index, current = self.fixture()
        borrowed = dict(current)
        borrowed["passage:0"] = replace(
            current["passage:0"],
            content_id="content:1",
            capture_id="capture:1",
        )
        unsafe = preview_private_batch_machine_handoff(
            plan,
            index,
            current_items=borrowed,
            request_key="operator:dp240:s",
            expected_receipt_sha256=index.receipt_sha256,
        )
        self.assertEqual(unsafe["items"][0]["status"], "HELD_SOURCE_SCOPE_MISMATCH")
        self.assertNotEqual(
            unsafe["items"][0]["intent_fingerprint"],
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items=current,
                request_key="operator:dp240:s",
                expected_receipt_sha256=index.receipt_sha256,
            )["items"][0]["intent_fingerprint"],
        )
        with self.assertRaisesRegex(
            ValueError, "STUDIO_MACHINE_BATCH_CURRENT_SCOPE_INVALID"
        ):
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items={
                    **current,
                    "foreign:passage": current["passage:0"],
                },
                request_key="operator:dp240:s",
                expected_receipt_sha256=index.receipt_sha256,
            )

    def test_unobserved_and_held_rows_never_become_machine_handoff(self):
        plan, _, current = self.fixture()
        index = build_private_batch_receipt_index(plan, ())
        preview = preview_private_batch_machine_handoff(
            plan,
            index,
            current_items=current,
            request_key="operator:dp240:empty",
            expected_receipt_sha256=index.receipt_sha256,
        )
        self.assertEqual(
            [row["status"] for row in preview["items"]],
            [
                "HELD_EXTRACTION_UNOBSERVED",
                "HELD_EXTRACTION_UNOBSERVED",
                "HELD_SOURCE_OR_ATTRIBUTION",
            ],
        )
        self.assertFalse(preview["enqueued"])

    def test_forged_receipt_and_stale_replay_refused(self):
        plan, index, current = self.fixture()
        with self.assertRaisesRegex(
            ValueError, "STUDIO_MACHINE_BATCH_RECEIPT_SHA256_INVALID"
        ):
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items=current,
                request_key="operator:dp240:no-pin",
            )
        with self.assertRaisesRegex(ValueError, "RECEIPT_"):
            preview_private_batch_machine_handoff(
                plan,
                replace(index, receipt_sha256="0" * 64),
                current_items=current,
                request_key="operator:dp240:t",
                expected_receipt_sha256=index.receipt_sha256,
            )
        with self.assertRaisesRegex(ValueError, "RECEIPT_PLAN_MISMATCH"):
            other = dp240_plan(dp240_manifest(reverse=True))
            preview_private_batch_machine_handoff(
                other,
                index,
                current_items=current,
                request_key="operator:dp240:t",
                expected_receipt_sha256=index.receipt_sha256,
            )
        with self.assertRaisesRegex(ValueError, "STUDIO_MACHINE_REQUEST_KEY_INVALID"):
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items=current,
                request_key="../invalid",
                expected_receipt_sha256=index.receipt_sha256,
            )
        with self.assertRaisesRegex(ValueError, "STUDIO_MACHINE_BATCH_RECEIPT_STALE"):
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items=current,
                request_key="operator:dp240:t",
                expected_receipt_sha256="f" * 64,
            )

    def test_current_snapshot_change_mid_preflight_is_not_an_actionable_receipt(self):
        plan, index, snapshots = self.fixture()

        class ChangedOnSecondRead(dict):
            def __init__(self, data):
                super().__init__(data)
                self.calls = 0

            def get(self, key, default=None):
                if key == "passage:0":
                    self.calls += 1
                    if self.calls == 2:
                        return replace(super().get(key), rights_status="REVOKED")
                return super().get(key, default)

        with self.assertRaisesRegex(
            ValueError, "STUDIO_MACHINE_BATCH_CHANGED_DURING_PREFLIGHT"
        ):
            preview_private_batch_machine_handoff(
                plan,
                index,
                current_items=ChangedOnSecondRead(snapshots),
                expected_receipt_sha256=index.receipt_sha256,
                request_key="operator:dp240:race",
            )


if __name__ == "__main__":
    unittest.main()

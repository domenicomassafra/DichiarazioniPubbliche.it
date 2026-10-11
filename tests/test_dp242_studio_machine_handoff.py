"""DP-242: persisted Studio readback to held machine handoff, never approval."""

import json
import unittest

from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import (
    DiscoveryInboxWorkflow,
)
from dichiarazioni_pubbliche.studio_machine_candidate_handoff_v1 import (
    preview_candidate_machine_handoff,
    preview_discovery_machine_exception,
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


if __name__ == "__main__":
    unittest.main()

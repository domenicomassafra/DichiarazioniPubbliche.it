"""DP231 private multi-Content metadata release reconciliation: real Python fixtures."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    projection_dataset_sha256,
    validate_public_bundle,
)
from dichiarazioni_pubbliche.private_source_metadata_review_v1 import (  # noqa: E402
    metadata_snapshot_sha256,
)
from test_dp231_private_metadata_reconciliation_20261014 import captured, real_public  # noqa: E402
from test_public_schema import valid_content  # noqa: E402


def release_with_standalone():
    projection = real_public()
    projection["generated_at"] = "2026-10-14T12:00:00Z"
    extra = valid_content()
    extra.update(content_id="content:standalone", slug="standalone", finding_ids=[])
    projection["contents"].append(extra)
    projection["dataset_sha256"] = projection_dataset_sha256(projection)
    validate_public_bundle(projection)
    return projection


class PrivateMetadataCohortTests(unittest.TestCase):
    def plan(self, previous=None, current=None, before=None, after=None, **kw):
        from dichiarazioni_pubbliche.private_source_metadata_cohort_v1 import (
            plan_private_metadata_cohort,
        )

        prev = previous if previous is not None else {"content:a": captured()}
        curr = current if current is not None else {"content:a": captured()}
        old_proj = before if before is not None else real_public()
        new_proj = after if after is not None else real_public()
        args = dict(
            previous=prev,
            current=curr,
            previous_metadata_pins={
                key: metadata_snapshot_sha256(item) for key, item in prev.items()
            },
            current_metadata_pins={
                key: metadata_snapshot_sha256(item) for key, item in curr.items()
            },
            previous_public_projection=old_proj,
            current_public_projection=new_proj,
            expected_previous_public_sha256=old_proj["dataset_sha256"],
            expected_current_public_sha256=new_proj["dataset_sha256"],
            expected_previous_generated_at=old_proj["generated_at"],
            expected_current_generated_at=new_proj["generated_at"],
            source_policies={
                key: ("APPROVED", "APPROVED") for key in set(prev) | set(curr)
            },
            private_opt_in=True,
        )
        args.update(kw)
        return plan_private_metadata_cohort(**args)

    def test_real_capture_public_projection_unchanged_no_grants(self):
        result = self.plan()
        self.assertEqual(result.status, "IDLE_PRIVATE_REVIEW_PENDING")
        self.assertEqual(result.cohort_count, 1)
        self.assertEqual(result.unchanged_count, 1)
        self.assertEqual(result.changed_count, 0)
        self.assertEqual(result.review_items[0].status, "UNCHANGED_REVIEW_PENDING")
        self.assertEqual(result, self.plan())
        self.assertTrue(result.private_only)
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.source_approval_authority)
        self.assertFalse(result.factual_verification)
        self.assertEqual(result.capture_calls, 0)
        self.assertEqual(result.provider_calls, 0)
        self.assertNotIn("content:a", repr(result))
        self.assertNotIn("https://", repr(result))

    def test_real_standalone_content_and_dossier_join_across_batch(self):
        projection = release_with_standalone()
        prev = {
            "content:a": captured(),
            "content:standalone": captured(content_id="content:standalone"),
        }
        current = dict(reversed(tuple(prev.items())))
        result = self.plan(prev, current, before=projection, after=projection)
        self.assertEqual(result.cohort_count, 2)
        self.assertEqual(result.unchanged_count, 2)
        self.assertEqual(result.status, "IDLE_PRIVATE_REVIEW_PENDING")
        self.assertEqual(
            len({row.opaque_content_ref for row in result.review_items}), 2
        )

    def test_field_drift_unsafe_conflict_and_policy_hold_are_bucketed(self):
        projection = release_with_standalone()
        previous = {
            "content:a": captured(),
            "content:standalone": captured(content_id="content:standalone"),
        }
        changed = captured(title="UNAPPROVED_PRIVATE_TITLE")
        current = dict(previous)
        current["content:a"] = changed
        result = self.plan(
            previous,
            current,
            before=projection,
            after=projection,
            source_policies={
                "content:a": ("APPROVED", "APPROVED"),
                "content:standalone": ("REVOKED", "PENDING"),
            },
        )
        self.assertEqual(result.changed_count, 2)
        self.assertEqual(result.held_count, 1)
        self.assertEqual(result.status, "MANUAL_COHORT_RECHECK_REQUIRED")
        self.assertIn(
            "WITHHELD_SOURCE_POLICY", {item.status for item in result.review_items}
        )
        self.assertIn("REVIEW_REQUIRED", {item.status for item in result.review_items})
        self.assertNotIn("UNAPPROVED_PRIVATE_TITLE", repr(result))

    def test_new_public_content_and_removed_public_content_require_manual_review(self):
        previous = real_public()
        current = release_with_standalone()
        first = {"content:a": captured()}
        second = dict(
            first, **{"content:standalone": captured(content_id="content:standalone")}
        )
        delta = self.plan(first, second, before=previous, after=current)
        self.assertEqual(delta.added_count, 1)
        self.assertEqual(delta.review_items[0].status, "NEW_CONTENT_METADATA_REVIEW")
        self.assertFalse(delta.publication_authority)
        retired_release = copy.deepcopy(previous)
        retired_release["generated_at"] = "2026-10-15T12:00:00Z"
        reversed_delta = self.plan(second, first, before=current, after=retired_release)
        self.assertEqual(reversed_delta.retired_count, 1)
        self.assertIn(
            "RETIRED_CONTENT_REVIEW",
            {item.status for item in reversed_delta.review_items},
        )
        self.assertFalse(reversed_delta.absence_of_original_established)

    def test_new_public_content_url_rebind_across_releases_is_held(self):
        old = real_public()
        current = copy.deepcopy(old)
        current["generated_at"] = "2026-10-14T12:00:00Z"
        current["dossiers"][0]["source"]["url"] = "https://unreviewed.example.test/new"
        current["dataset_sha256"] = projection_dataset_sha256(current)
        validate_public_bundle(current)
        result = self.plan(before=old, after=current)
        self.assertEqual(result.status, "MANUAL_COHORT_RECHECK_REQUIRED")
        self.assertIn(
            "PUBLIC_SOURCE_LOCATOR_CHANGED_HOLD",
            {item.status for item in result.review_items},
        )
        self.assertNotIn("unreviewed.example", repr(result))

    def test_wrong_dataset_pin_missing_id_missing_policy_and_mutable_classes_refused(
        self,
    ):
        with self.assertRaisesRegex(ValueError, "COHORT_PUBLIC_PIN_MISMATCH"):
            self.plan(expected_current_public_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "COHORT_METADATA_PINS_MISMATCH"):
            self.plan(current_metadata_pins={"content:a": "0" * 64})
        with self.assertRaisesRegex(ValueError, "COHORT_SOURCE_POLICY_MISMATCH"):
            self.plan(source_policies={})
        with self.assertRaisesRegex(ValueError, "COHORT_PRIVATE_OPT_IN_REQUIRED"):
            self.plan(private_opt_in=False)
        held = self.plan(
            current={"content:secret": captured(content_id="content:secret")}
        )
        self.assertIn(
            "PRIVATE_CONTENT_NOT_PUBLIC_HOLD",
            {item.status for item in held.review_items},
        )
        self.assertEqual(held.status, "MANUAL_COHORT_RECHECK_REQUIRED")
        self.assertNotIn("content:secret", repr(held))

    def test_public_canonical_content_dossier_conflict_must_fail_closed(self):
        projected = real_public()
        document = valid_content()
        document.update(
            content_id="content:a",
            slug="content-a",
            finding_ids=[],
            url="https://other.example.test/fake",
        )
        projected["contents"].append(document)
        projected["generated_at"] = "2026-10-14T12:00:00Z"
        projected["dataset_sha256"] = projection_dataset_sha256(projected)
        validate_public_bundle(projected)
        with self.assertRaisesRegex(
            ValueError, "COHORT_PUBLIC_CONTENT_IDENTITY_AMBIGUOUS"
        ):
            self.plan(after=projected)

    def test_changed_same_code_private_conflict_requires_review_but_no_url_echo(self):
        from dichiarazioni_pubbliche.source_metadata_enrichment import (
            build_metadata_enrichment,
        )

        def blocked(url):
            return build_metadata_enrichment(
                content_id="content:a",
                parsed_metadata={"canonical_url_candidates": [url]},
                content_identity={"canonical_url": "https://example.test/source"},
            )

        prev = {"content:a": blocked("http://example.test/SECRET_A")}
        next_ = {"content:a": blocked("http://example.test/SECRET_B")}
        result = self.plan(prev, next_)
        self.assertEqual(result.status, "MANUAL_COHORT_RECHECK_REQUIRED")
        self.assertIn(
            "metadata_conflict_evidence", result.review_items[0].changed_fields
        )
        self.assertNotIn("SECRET_A", repr(result))
        self.assertNotIn("SECRET_B", repr(result))

    def test_same_private_conflict_repeated_twice_requires_recheck(self):
        from dichiarazioni_pubbliche.source_metadata_enrichment import (
            build_metadata_enrichment,
        )

        private_url = "http://example.test/PRIVATE_NEVER_ECHO"

        def blocked(values):
            return build_metadata_enrichment(
                content_id="content:a",
                parsed_metadata={"canonical_url_candidates": values},
                content_identity={"canonical_url": "https://example.test/source"},
            )

        output = self.plan(
            {"content:a": blocked([private_url])},
            {"content:a": blocked([private_url, private_url])},
        )
        self.assertEqual(output.status, "MANUAL_COHORT_RECHECK_REQUIRED")
        self.assertIn(
            "metadata_conflict_evidence", output.review_items[0].changed_fields
        )
        self.assertNotIn("PRIVATE_NEVER_ECHO", repr(output))

    def test_release_time_rollback_cannot_mark_stale_recheck_idle(self):
        earlier = real_public()
        later = copy.deepcopy(earlier)
        earlier["generated_at"] = "2026-10-14T10:00:00Z"
        later["generated_at"] = "2026-10-13T09:00:00Z"
        with self.assertRaisesRegex(ValueError, "COHORT_PUBLIC_RELEASE_TIME_ROLLBACK"):
            self.plan(before=earlier, after=later)

    def test_inventory_order_invariance(self):
        projection = release_with_standalone()
        a, b = captured(), captured(content_id="content:standalone")
        first = {"content:a": a, "content:standalone": b}
        last = {"content:standalone": b, "content:a": a}
        self.assertEqual(
            self.plan(first, first, before=projection, after=projection),
            self.plan(last, last, before=projection, after=projection),
        )

    def test_missing_current_metadata_must_not_claim_public_content_retired(self):
        result = self.plan({"content:a": captured()}, {})
        self.assertEqual(
            result.review_items[0].status, "MISSING_CURRENT_METADATA_REVIEW"
        )
        self.assertEqual(result.retired_count, 0)
        self.assertEqual(result.changed_count, 1)

    def test_newly_captured_metadata_must_not_claim_new_public_content(self):
        result = self.plan({}, {"content:a": captured()})
        self.assertEqual(result.review_items[0].status, "NEW_METADATA_RECORD_REVIEW")
        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.changed_count, 1)

    def test_same_generation_different_dataset_cannot_auto_accept(self):
        older = real_public()
        current = copy.deepcopy(older)
        current["dossiers"][0]["source"]["url"] = "https://alternate.example.test/new"
        current["dataset_sha256"] = projection_dataset_sha256(current)
        with self.assertRaisesRegex(ValueError, "COHORT_PUBLIC_GENERATION_CONFLICT"):
            self.plan(before=older, after=current)

    def test_new_public_content_without_any_private_metadata_is_not_silent_idle(self):
        older = real_public()
        newer = release_with_standalone()
        source = {"content:a": captured()}
        result = self.plan(source, source, before=older, after=newer)
        self.assertEqual(result.cohort_count, 2)
        self.assertEqual(result.status, "MANUAL_COHORT_RECHECK_REQUIRED")
        self.assertIn(
            "UNSCOPED_PUBLIC_CONTENT_REVIEW",
            {row.status for row in result.review_items},
        )
        self.assertEqual(result.held_count, 1)
        self.assertFalse(result.source_approval_authority)

    def test_public_content_missing_both_metadata_inventories_is_pending_not_clean(
        self,
    ):
        source = real_public()
        result = self.plan({}, {}, before=source, after=source)
        self.assertEqual(result.cohort_count, 1)
        self.assertEqual(
            result.review_items[0].status, "UNSCOPED_PUBLIC_CONTENT_REVIEW"
        )
        self.assertEqual(result.status, "MANUAL_COHORT_RECHECK_REQUIRED")

    def test_revoked_policy_cannot_swap_after_validated_preflight(self):
        from dichiarazioni_pubbliche import private_source_metadata_cohort_v1 as cohort

        policy = {"content:a": ("REVOKED", "PENDING")}
        original = cohort._canonical_url

        def malicious_postvalidation_swap(*args):
            policy["content:a"] = ("APPROVED", "APPROVED")
            return original(*args)

        with patch.object(
            cohort, "_canonical_url", side_effect=malicious_postvalidation_swap
        ):
            result = self.plan(source_policies=policy)
        self.assertEqual(result.review_items[0].status, "WITHHELD_SOURCE_POLICY")
        self.assertEqual(result.held_count, 1)
        self.assertEqual(result.status, "MANUAL_COHORT_RECHECK_REQUIRED")

    def test_public_addition_with_early_private_metadata_is_supported(self):
        old, new = real_public(), release_with_standalone()
        inventory = {
            "content:a": captured(),
            "content:standalone": captured(content_id="content:standalone"),
        }
        result = self.plan(inventory, inventory, before=old, after=new)
        self.assertEqual(result.added_count, 1)
        self.assertIn(
            "NEW_CONTENT_METADATA_REVIEW", {row.status for row in result.review_items}
        )

    def test_public_retirement_with_retained_private_metadata_is_supported(self):
        old, new = release_with_standalone(), real_public()
        new["generated_at"] = "2026-10-15T12:00:00Z"
        inventory = {
            "content:a": captured(),
            "content:standalone": captured(content_id="content:standalone"),
        }
        result = self.plan(inventory, inventory, before=old, after=new)
        self.assertEqual(result.retired_count, 1)
        self.assertIn(
            "RETIRED_CONTENT_REVIEW", {row.status for row in result.review_items}
        )
        self.assertFalse(result.absence_of_original_established)


if __name__ == "__main__":
    unittest.main()

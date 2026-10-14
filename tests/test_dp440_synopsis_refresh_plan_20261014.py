"""Offline DP440 regeneration planning only; no semantic or publishing authority."""

from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402
from test_dp440_public_synopsis import bundle, intersection, prepare, sentence  # noqa: E402

NOW = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)


class SynopsisRefreshPlanTests(unittest.TestCase):
    def plan(
        self,
        previous_bundle=None,
        current_bundle=None,
        reviewed=None,
        current_membership=None,
        **overrides,
    ):
        from dichiarazioni_pubbliche.public_synopsis_refresh_plan_v1 import (
            plan_synopsis_refresh,
        )

        original = previous_bundle if previous_bundle is not None else bundle()
        current = (
            current_bundle if current_bundle is not None else copy.deepcopy(original)
        )
        old_review = reviewed if reviewed is not None else prepare(original)
        proof = (
            current_membership
            if current_membership is not None
            else intersection(current)
        )
        args = dict(
            previous_bundle=original,
            current_bundle=current,
            previous_synopsis=old_review,
            current_membership=proof,
            expected_previous_dataset_sha256=original["dataset_sha256"],
            expected_current_dataset_sha256=current["dataset_sha256"],
            expected_previous_synopsis_sha256=old_review.fingerprint,
            now=NOW,
        )
        args.update(overrides)
        return plan_synopsis_refresh(**args)

    def test_unchanged_corpus_never_automatically_publish_or_verify(self):
        result = self.plan()
        self.assertEqual(result.status, "NO_CHANGE_REVIEW_PENDING")
        self.assertEqual(result.changed_citation_keys, ())
        self.assertEqual(result.removed_citation_keys, ())
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.semantic_entailment_verified)
        self.assertFalse(result.source_rights_authority)
        self.assertTrue(result.private_only)
        self.assertIsNone(result.verdict)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result.source_body_count, 0)
        self.assertEqual(result, self.plan())

    def test_rights_or_topic_revocation_blocks_prior_citation_reuse(self):
        baseline = bundle()
        for status in ("REVOKED", "PENDING", "HELD"):
            with self.subTest(status=status):
                result = self.plan(
                    baseline,
                    baseline,
                    current_membership=intersection(baseline, status=status),
                )
                self.assertEqual(result.status, "WITHHELD_REVIEW_REQUIRED")
                self.assertIn("TOPIC_MEMBERSHIP_NOT_CURRENT", result.reason_codes)
                self.assertFalse(result.publication_authority)

    def test_correction_and_source_supersession_invalidate_exact_citation(self):
        baseline = bundle()
        for change in (
            {"original_text": "new corrected original"},
            {"source_sha256": "f" * 64},
            {"source_version": "source-version:revised"},
            {"statement_date": "2026-10-08"},
        ):
            with self.subTest(change=change):
                current = copy.deepcopy(baseline)
                current["statements"][0].update(change)
                if "original_text" in change:
                    from hashlib import sha256

                    current["statements"][0]["quote_sha256"] = sha256(
                        change["original_text"].encode()
                    ).hexdigest()
                current["dataset_sha256"] = projection_dataset_sha256(current)
                result = self.plan(baseline, current)
                self.assertEqual(result.status, "RECHECK_REQUIRED")
                self.assertEqual(
                    result.changed_citation_keys,
                    (("statement:1", "statement-version:1"),),
                )
                self.assertIn("CITED_SOURCE_MATERIAL_CHANGED", result.reason_codes)
                self.assertNotEqual(
                    result.snapshot_sha256, self.plan(baseline).snapshot_sha256
                )

    def test_removed_citation_no_hallucinated_source(self):
        baseline = bundle()
        current = copy.deepcopy(baseline)
        current["statements"] = current["statements"][1:]
        current["dataset_sha256"] = projection_dataset_sha256(current)
        result = self.plan(baseline, current)
        self.assertEqual(result.status, "RECHECK_REQUIRED")
        self.assertEqual(
            result.removed_citation_keys, (("statement:1", "statement-version:1"),)
        )
        self.assertNotIn("original_text", repr(result))

    def test_repinning_private_unapproved_metadata_never_mints_rights(self):
        baseline = bundle()
        first = prepare(baseline)
        with self.assertRaisesRegex(ValueError, "REFRESH_PIN_MISMATCH"):
            self.plan(baseline, baseline, expected_previous_dataset_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "REFRESH_PIN_MISMATCH"):
            self.plan(baseline, baseline, expected_previous_synopsis_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "REFRESH_REVIEW_INVALID"):
            self.plan(baseline, baseline, reviewed=replace(first, provider_calls=1))
        with self.assertRaisesRegex(ValueError, "REFRESH_REVIEW_INVALID"):
            self.plan(
                baseline,
                baseline,
                reviewed=replace(
                    first, sentences=({"PRIVATE_RAW_TRANSCRIPT": "DO NOT SHOW"},)
                ),
            )

    def test_current_projection_drift_hold_even_if_old_citation_unchanged(self):
        old = bundle()
        current = copy.deepcopy(old)
        current["generated_at"] = "2026-10-11T12:30:00+00:00"
        current["dataset_sha256"] = projection_dataset_sha256(current)
        result = self.plan(old, current)
        self.assertEqual(result.status, "RECHECK_REQUIRED")
        self.assertEqual(result.changed_citation_keys, ())
        self.assertIn("SOURCE_PROJECTION_TIMESTAMP_CHANGED", result.reason_codes)

    def test_expired_membership_requires_new_owner_review_even_unchanged_hash(self):
        old = bundle()
        result = self.plan(
            old,
            old,
            current_membership=intersection(
                old, currentness_valid_until="2026-10-11T15:00:00+00:00"
            ),
        )
        self.assertEqual(result.status, "WITHHELD_REVIEW_REQUIRED")
        self.assertIn("TOPIC_MEMBERSHIP_EXPIRED", result.reason_codes)

    def test_removed_topic_membership_does_not_reuse_old_citation(self):
        old = bundle()
        key = (old["statements"][0]["statement_id"], old["statements"][0]["version_id"])
        proof = intersection(old)
        narrowed = replace(proof, statement_versions=(proof.statement_versions[1],))
        result = self.plan(old, old, current_membership=narrowed)
        self.assertEqual(result.status, "RECHECK_REQUIRED")
        self.assertEqual(result.removed_citation_keys, (key,))
        self.assertIn("CITED_STATEMENT_REMOVED_OR_TOPIC_REVOKED", result.reason_codes)

    def test_same_approved_original_may_support_multiple_reviewed_sentences(self):
        current = bundle()
        old = prepare(
            current,
            sentences=(
                sentence(current, review_event_id="review:sentence:one"),
                sentence(current, review_event_id="review:sentence:two"),
                sentence(current, index=1, review_event_id="review:sentence:three"),
            ),
        )
        self.assertEqual(old.status, "READY_READ_MODEL")
        result = self.plan(current, current, reviewed=old)
        self.assertEqual(result.status, "NO_CHANGE_REVIEW_PENDING")
        self.assertEqual(result.changed_citation_keys, ())

    def test_invalid_shapes_and_untrusted_input_never_echo_private_text(self):
        old = bundle()
        with self.assertRaisesRegex(ValueError, "REFRESH_TIMESTAMP_INVALID"):
            self.plan(old, old, now=datetime(2026, 10, 11))
        with self.assertRaisesRegex(ValueError, "REFRESH_REVIEW_INVALID"):
            review = prepare(old)
            self.plan(
                old,
                old,
                reviewed=replace(
                    review,
                    sentences=tuple(list(review.sentences) + [{"text": "private"}]),
                ),
            )


if __name__ == "__main__":
    unittest.main()

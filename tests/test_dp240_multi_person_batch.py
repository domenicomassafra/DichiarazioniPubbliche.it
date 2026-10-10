"""DP-240 source-only mixed Person/Content isolation fixtures."""

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.multi_person_batch_v1 import (  # noqa: E402
    PrivateBatchResult,
    ReviewedPassageContext,
    _stable_hash,
    plan_isolated_candidate_batch,
    reconcile_isolated_private_results,
)
from dichiarazioni_pubbliche.private_candidate_batch import (  # noqa: E402
    CandidateBatch, CandidateBatchItem, _batch_digest,
)


def manifest(count=3, *, reverse=False):
    items = tuple(CandidateBatchItem(
        passage_id=f"passage:{i}", content_id=f"content:{i}", capture_id=f"capture:{i}",
        passage_sha256=hex(i + 1)[2:].rjust(64, "0"),
        canonical_url=f"https://example.test/primary/{i}",
        source_family=f"source-family:{i}", rights_record_id=f"rights:{i}",
    ) for i in range(count))
    if reverse:
        items = tuple(reversed(items))
    original = CandidateBatch("collection:synthetic", items, "")
    return replace(original, sha256=_batch_digest(original))


def reviewed_contexts(batch):
    return {item.passage_id: ReviewedPassageContext(
        passage_id=item.passage_id, capture_id=item.capture_id,
        source_sha256="a" * 64, passage_sha256=item.passage_sha256,
        selector_fingerprint="selector:written:0-20", content_id=item.content_id,
        source_family=item.source_family, language_tag="de" if item.passage_id.endswith("1") else "it",
        speaker_candidate_id=f"person-candidate:{item.passage_id}",
        identity_review_status="CANDIDATE_MATCH", speech_role="DIRECT_SPEAKER",
        speech_act="DIRECT_ASSERTION", context_version="context:v1",
        context_review_id=f"context-review:{item.passage_id}",
        rights_status="CLEARED", estimated_tokens=200,
    ) for item in batch.items}


def plan(batch=None, contexts=None, **kwargs):
    batch = batch or manifest()
    return plan_isolated_candidate_batch(
        batch, contexts if contexts is not None else reviewed_contexts(batch),
        total_token_cap=kwargs.pop("total_token_cap", 600),
        provider_capability_ready=kwargs.pop("provider_capability_ready", True),
        **kwargs,
    )


class MixedPersonPrivateBatchTests(unittest.TestCase):
    def test_three_contents_three_person_candidates_never_share_source_partition(self):
        result = plan()
        self.assertEqual(len(result.items), 3)
        self.assertEqual(result.proposed_group_count, 3)
        self.assertEqual(result.total_estimated_tokens, 600)
        self.assertTrue(all(item.status == "PRIVATE_EXTRACTION_PROPOSED" for item in result.items))
        self.assertTrue(all(not item.public_attribution_authority for item in result.items))
        self.assertFalse(result.dispatch_authorized)
        self.assertEqual(result.provider_calls, 0)

    def test_batch_manifest_order_does_not_change_source_bound_plan_fingerprint(self):
        ordered = plan(manifest())
        reversed_manifest = manifest(reverse=True)
        reversed_plan = plan(reversed_manifest)
        self.assertEqual(ordered.plan_sha256, reversed_plan.plan_sha256)
        self.assertEqual(ordered.items, reversed_plan.items)
        self.assertNotEqual(ordered.manifest_sha256, reversed_plan.manifest_sha256)

    def test_wrong_content_capture_or_source_sha_assignment_fails_before_plan(self):
        batch = manifest()
        for change in (dict(content_id="content:other"), dict(capture_id="capture:other"),
                       dict(source_family="source-family:other"), dict(passage_sha256="f" * 64)):
            ctx = reviewed_contexts(batch)
            ctx["passage:0"] = replace(ctx["passage:0"], **change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "CROSS_SOURCE_REFERENCE"):
                plan(batch, ctx)

    def test_cross_speaker_reported_quote_criticism_held_no_endorsement(self):
        batch = manifest()
        for change in (
            dict(speech_role="QUOTED_SPEAKER", speech_act="REPORTED_QUOTE"),
            dict(speech_role="REPORTER", speech_act="OPINION"),
            dict(speech_act="CRITICISM"), dict(speech_act="IRONY"),
        ):
            ctx = reviewed_contexts(batch)
            ctx["passage:1"] = replace(ctx["passage:1"], **change)
            result = plan(batch, ctx)
            self.assertEqual(result.items[1].status, "HELD")
            self.assertEqual(result.items[1].reason_code, "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT")
            self.assertTrue(all(not row.public_attribution_authority for row in result.items))

    def test_homonyms_or_ambiguous_identity_never_promote_automatically(self):
        batch = manifest()
        for change in (dict(speaker_candidate_id=None), dict(identity_review_status="UNRESOLVED"),
                       dict(speech_role="UNRESOLVED"), dict(speech_act="UNKNOWN")):
            ctx = reviewed_contexts(batch)
            ctx["passage:0"] = replace(ctx["passage:0"], **change)
            result = plan(batch, ctx)
            self.assertEqual(result.items[0].reason_code, "MULTIPERSON_SPEAKER_AMBIGUOUS")

    def test_no_rights_or_no_context_review_holds_only_matching_item(self):
        batch = manifest()
        ctx = reviewed_contexts(batch)
        ctx["passage:0"] = replace(ctx["passage:0"], rights_status="REVOKED")
        ctx["passage:2"] = replace(ctx["passage:2"], context_review_id=None)
        result = plan(batch, ctx)
        self.assertEqual([row.status for row in result.items], ["HELD", "PRIVATE_EXTRACTION_PROPOSED", "HELD"])
        self.assertEqual(result.total_estimated_tokens, 200)

    def test_capability_missing_and_token_budget_hold_without_fake_bill(self):
        unavailable = plan(provider_capability_ready=False)
        self.assertEqual(unavailable.total_estimated_tokens, 0)
        self.assertTrue(all(row.reason_code == "MULTIPERSON_PROVIDER_CAPABILITY_UNAVAILABLE" for row in unavailable.items))
        limited = plan(total_token_cap=220)
        self.assertEqual([row.status for row in limited.items], ["PRIVATE_EXTRACTION_PROPOSED", "HELD", "HELD"])
        self.assertEqual(limited.total_estimated_tokens, 200)
        self.assertEqual(limited.items[1].reason_code, "MULTIPERSON_BATCH_TOKEN_CAP")

    def test_missing_or_extra_context_rejected_instead_of_silent_drop(self):
        batch = manifest()
        ctx = reviewed_contexts(batch)
        del ctx["passage:1"]
        with self.assertRaisesRegex(ValueError, "CARDINALITY"):
            plan(batch, ctx)
        ctx = reviewed_contexts(batch)
        ctx["foreign"] = ctx["passage:1"]
        with self.assertRaisesRegex(ValueError, "CARDINALITY"):
            plan(batch, ctx)

    def test_partial_provider_result_is_private_unverified_only(self):
        batch = manifest()
        planned = plan(batch)
        first = planned.items[0]
        last = planned.items[2]
        observations = (
            PrivateBatchResult(first.passage_id, first.content_id, first.capture_id, first.passage_sha256,
                               "CANDIDATE_EXTRACTED", None, "extractor:test:v1"),
            PrivateBatchResult(last.passage_id, last.content_id, last.capture_id, last.passage_sha256,
                               "FAILED", "PROVIDER_UNAVAILABLE", None),
        )
        result = reconcile_isolated_private_results(planned, observations)
        self.assertEqual(result.statuses, (("passage:0", "PRIVATE_CANDIDATE_UNVERIFIED"),
                                          ("passage:1", "HELD"), ("passage:2", "FAILED")))
        self.assertEqual((result.private_candidate_count, result.held_count, result.failed_count), (1, 1, 1))
        self.assertFalse(result.publication_authority)
        self.assertEqual(result, reconcile_isolated_private_results(planned, tuple(reversed(observations))))

    def test_wrong_source_from_model_and_held_row_fake_success_rejected(self):
        planned = plan()
        first = planned.items[0]
        observed = PrivateBatchResult(first.passage_id, "content:foreign", first.capture_id,
                                      first.passage_sha256, "CANDIDATE_EXTRACTED", None, "test:v1")
        with self.assertRaisesRegex(ValueError, "SOURCE_MISMATCH"):
            reconcile_isolated_private_results(planned, (observed,))
        held = plan(provider_capability_ready=False)
        observed = replace(observed, content_id=first.content_id)
        with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_SUCCESS"):
            reconcile_isolated_private_results(held, (observed,))

    def test_conflicting_replay_and_unbounded_batch_rejected(self):
        planned = plan()
        item = planned.items[0]
        row = PrivateBatchResult(item.passage_id, item.content_id, item.capture_id, item.passage_sha256,
                                 "FAILED", "OFFLINE", None)
        self.assertEqual(reconcile_isolated_private_results(planned, (row, row)).failed_count, 1)
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            reconcile_isolated_private_results(planned, (row, replace(row, failure_reason="TIMEOUT")))
        with self.assertRaisesRegex(ValueError, "SIZE_INVALID"):
            plan(manifest(17))

    def test_reconciliation_rejects_manipulated_plan_hash_items_and_counts(self):
        original = plan()
        for mutated in (
            replace(original, plan_sha256="0" * 64),
            replace(original, collection_id="other:collection"),
            replace(original, items=original.items[:2]),
            replace(original, items=(replace(original.items[0], passage_sha256="e" * 64), *original.items[1:])),
        ):
            with self.subTest(mutated=mutated), self.assertRaisesRegex(ValueError, "TAMPERED|COUNTS"):
                reconcile_isolated_private_results(mutated, ())

    def test_rehashed_plan_cannot_assert_authority_duplicate_or_fake_counts(self):
        original = plan()
        item = original.items[0]
        for change in (
            dict(provider_calls=1), dict(dispatch_authorized=True),
            dict(total_estimated_tokens=0), dict(proposed_group_count=2),
            dict(items=(item, item, original.items[2])),
            dict(items=(replace(item, public_attribution_authority=True), *original.items[1:])),
            dict(items=(replace(item, reason_code="MULTIPERSON_CONTEXT_UNREVIEWED"), *original.items[1:])),
            dict(items=(replace(item, status="HELD"), *original.items[1:])),
        ):
            mutated = replace(original, **change)
            mutated = replace(mutated, plan_sha256=_stable_hash({
                "version": mutated.version, "collection": mutated.collection_id,
                "items": [vars(row) for row in mutated.items],
            }))
            with self.subTest(change=change), self.assertRaisesRegex(
                ValueError, "AUTHORITY|COUNTS|DUPLICATE|ITEM_INVALID|STATUS_INVALID"
            ):
                reconcile_isolated_private_results(mutated, ())

    def test_same_source_distinct_passages_stay_distinct_partitions(self):
        batch = manifest(2)
        contexts = reviewed_contexts(batch)
        contexts["passage:1"] = replace(contexts["passage:1"],
            content_id="content:1", capture_id="capture:1", source_family="source-family:1",
            speaker_candidate_id=contexts["passage:0"].speaker_candidate_id,
            language_tag="it")
        original = plan(batch, contexts)
        self.assertNotEqual(original.items[0].partition_id, original.items[1].partition_id)

    def test_unbounded_observations_and_unjustified_result_metadata_rejected(self):
        original = plan()
        item = original.items[0]
        observed = PrivateBatchResult(item.passage_id, item.content_id, item.capture_id,
                                      item.passage_sha256, "HELD", None, None)
        with self.assertRaisesRegex(ValueError, "RESULT_INPUT_INVALID"):
            reconcile_isolated_private_results(original, (observed,) * 65)
        for invalid in (
            replace(observed, failure_reason="pretend review"),
            replace(observed, extraction_version="pretend-version"),
            replace(observed, result="FAILED", failure_reason="OFFLINE", extraction_version="fake"),
            replace(observed, result="CANDIDATE_EXTRACTED", extraction_version=" "),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reconcile_isolated_private_results(original, (invalid,))


if __name__ == "__main__":
    unittest.main()

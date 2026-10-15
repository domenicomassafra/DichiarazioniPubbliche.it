"""DP-240 source-only mixed Person/Content isolation fixtures."""

import sys
import json
import unittest
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.multi_person_batch_v1 import (  # noqa: E402
    PrivateBatchResult,
    ReviewedPassageContext,
    _stable_hash,
    build_private_batch_receipt_index,
    export_private_batch_receipt_index,
    load_private_batch_receipt_index,
    lookup_private_batch_item_receipt,
    plan_isolated_candidate_batch,
    reconcile_isolated_private_results,
)
from dichiarazioni_pubbliche.private_candidate_batch import (  # noqa: E402
    CandidateBatch,
    CandidateBatchItem,
    _batch_digest,
)


def manifest(count=3, *, reverse=False):
    items = tuple(
        CandidateBatchItem(
            passage_id=f"passage:{i}",
            content_id=f"content:{i}",
            capture_id=f"capture:{i}",
            passage_sha256=hex(i + 1)[2:].rjust(64, "0"),
            canonical_url=f"https://example.test/primary/{i}",
            source_family=f"source-family:{i}",
            rights_record_id=f"rights:{i}",
        )
        for i in range(count)
    )
    if reverse:
        items = tuple(reversed(items))
    original = CandidateBatch("collection:synthetic", items, "")
    return replace(original, sha256=_batch_digest(original))


def reviewed_contexts(batch):
    return {
        item.passage_id: ReviewedPassageContext(
            passage_id=item.passage_id,
            capture_id=item.capture_id,
            source_sha256="a" * 64,
            passage_sha256=item.passage_sha256,
            selector_fingerprint="selector:written:0-20",
            content_id=item.content_id,
            source_family=item.source_family,
            language_tag="de" if item.passage_id.endswith("1") else "it",
            speaker_candidate_id=f"person-candidate:{item.passage_id}",
            identity_review_status="CANDIDATE_MATCH",
            speech_role="DIRECT_SPEAKER",
            speech_act="DIRECT_ASSERTION",
            context_version="context:v1",
            context_review_id=f"context-review:{item.passage_id}",
            rights_status="CLEARED",
            estimated_tokens=200,
        )
        for item in batch.items
    }


def plan(batch=None, contexts=None, **kwargs):
    batch = batch or manifest()
    return plan_isolated_candidate_batch(
        batch,
        contexts if contexts is not None else reviewed_contexts(batch),
        total_token_cap=kwargs.pop("total_token_cap", 600),
        provider_capability_ready=kwargs.pop("provider_capability_ready", True),
        **kwargs,
    )


def rehash_plan(original):
    return replace(
        original,
        plan_sha256=_stable_hash(
            {
                "version": original.version,
                "collection": original.collection_id,
                "manifest_sha256": original.manifest_sha256,
                "items": [vars(row) for row in original.items],
            }
        ),
    )


class MixedPersonPrivateBatchTests(unittest.TestCase):
    def test_receipt_index_durable_json_roundtrip_replay_and_corruption_refused(self):
        planned = plan()
        first, second, _ = planned.items
        observation = PrivateBatchResult(
            first.passage_id, first.content_id, first.capture_id,
            first.passage_sha256, "FAILED", "NETWORK_TIMEOUT", None,
        )
        initial = build_private_batch_receipt_index(planned, (observation,))
        persisted = json.loads(json.dumps(export_private_batch_receipt_index(planned, initial)))
        recovered = load_private_batch_receipt_index(planned, persisted)
        self.assertEqual(initial, recovered)
        subsequent = PrivateBatchResult(
            second.passage_id, second.content_id, second.capture_id,
            second.passage_sha256, "CANDIDATE_EXTRACTED", None, "fixture:de:v2",
        )
        combined = build_private_batch_receipt_index(
            planned, (subsequent,), previous_index=recovered,
        )
        self.assertEqual(
            load_private_batch_receipt_index(
                planned,
                json.loads(json.dumps(export_private_batch_receipt_index(planned, combined))),
            ), combined,
        )
        self.assertEqual(combined.failed_count, 1)
        self.assertEqual(combined.private_candidate_count, 1)
        for tampered in (
            {**persisted, "receipt_sha256": "0" * 64},
            {**persisted, "items": [
                {**persisted["items"][0], "source_sha256": "f" * 64},
                *persisted["items"][1:],
            ]},
            {**persisted, "items": [*persisted["items"], persisted["items"][0]]},
            {**persisted, "publication_authority": True},
            {**persisted, "observed_count": True},
            {**persisted, "items": [dict(persisted["items"][0],
                hidden_private_text="source secret"), *persisted["items"][1:]]},
        ):
            with self.subTest(tampered=tampered), self.assertRaisesRegex(
                ValueError, "RECEIPT_(?:INTEGRITY|PROVENANCE)_INVALID",
            ):
                load_private_batch_receipt_index(planned, tampered)
        # In-memory dataclass serialization uses the same lossless, read-only
        # schema as JSON; it never stores raw source words or model output.
        self.assertEqual(json.loads(json.dumps(asdict(initial))), persisted)
        self.assertNotIn("private_text", json.dumps(persisted))

    def test_receipt_index_isolates_multiple_contents_languages_and_homonyms(self):
        batch = manifest()
        contexts = reviewed_contexts(batch)
        contexts["passage:0"] = replace(
            contexts["passage:0"],
            speaker_candidate_id="person-candidate:anna:source-a",
        )
        contexts["passage:1"] = replace(
            contexts["passage:1"],
            speaker_candidate_id="person-candidate:anna:source-b",
            speech_role="QUOTED_SPEAKER",
            speech_act="REPORTED_QUOTE",
        )
        contexts["passage:2"] = replace(
            contexts["passage:2"], rights_status="REVOKED",
        )
        planned = plan(batch, contexts)
        first = planned.items[0]
        observation = PrivateBatchResult(
            first.passage_id, first.content_id, first.capture_id, first.passage_sha256,
            "CANDIDATE_EXTRACTED", None, "extractor:de-it:v1",
        )
        indexed = build_private_batch_receipt_index(planned, (observation,))
        self.assertEqual([row.status for row in indexed.items], [
            "PRIVATE_CANDIDATE_UNVERIFIED", "HELD", "HELD",
        ])
        self.assertEqual(indexed.observed_count, 1)
        self.assertEqual(indexed.pending_count, 0)
        self.assertEqual(indexed.failed_count, 0)
        self.assertEqual(indexed.held_count, 2)
        self.assertEqual(indexed.private_candidate_count, 1)
        self.assertEqual(indexed.items[0].language_tag, "it")
        self.assertEqual(indexed.items[1].language_tag, "de")
        self.assertNotEqual(
            indexed.items[0].speaker_candidate_id,
            indexed.items[1].speaker_candidate_id,
        )
        self.assertEqual(indexed.items[1].reason_code,
                         "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT")
        self.assertEqual(indexed.items[1].speech_role, "QUOTED_SPEAKER")
        self.assertEqual(indexed.items[1].speech_act, "REPORTED_QUOTE")
        self.assertEqual(indexed.items[1].identity_review_status, "CANDIDATE_MATCH")
        self.assertEqual(indexed.items[2].rights_status, "REVOKED")
        self.assertEqual(indexed.items[2].reason_code,
                         "MULTIPERSON_SOURCE_RIGHTS_HELD")
        for expected in planned.items:
            item = lookup_private_batch_item_receipt(
                planned, indexed, passage_id=expected.passage_id,
                content_id=expected.content_id,
                capture_id=expected.capture_id,
                source_sha256=expected.source_sha256,
            )
            self.assertEqual(item.partition_id, expected.partition_id)
            self.assertEqual(item.source_family, expected.source_family)
            self.assertEqual(item.selector_fingerprint, expected.selector_fingerprint)
            self.assertEqual(item.passage_sha256, expected.passage_sha256)
            self.assertFalse(item.public_attribution_authority)
        with self.assertRaisesRegex(ValueError, "RECEIPT_SOURCE_MISMATCH"):
            lookup_private_batch_item_receipt(
                planned, indexed, passage_id=first.passage_id,
                content_id=planned.items[1].content_id,
                capture_id=first.capture_id, source_sha256=first.source_sha256,
            )
        self.assertEqual(indexed, build_private_batch_receipt_index(planned, (observation, observation)))

    def test_partial_failure_index_retry_only_completes_previous_unobserved_item(self):
        planned = plan()
        first, second, third = planned.items
        failure = PrivateBatchResult(
            first.passage_id, first.content_id, first.capture_id, first.passage_sha256,
            "FAILED", "PROVIDER_UNAVAILABLE", None,
        )
        successful = PrivateBatchResult(
            third.passage_id, third.content_id, third.capture_id, third.passage_sha256,
            "CANDIDATE_EXTRACTED", None, "extractor:it:v1",
        )
        partial = build_private_batch_receipt_index(planned, (failure,))
        self.assertEqual([r.status for r in partial.items],
                         ["FAILED", "UNOBSERVED", "UNOBSERVED"])
        self.assertEqual(partial.pending_count, 2)
        self.assertEqual(partial.failed_count, 1)
        completed = build_private_batch_receipt_index(
            planned, (successful,), previous_index=partial,
        )
        self.assertEqual([r.status for r in completed.items],
                         ["FAILED", "UNOBSERVED", "PRIVATE_CANDIDATE_UNVERIFIED"])
        self.assertEqual(completed.pending_count, 1)
        self.assertEqual(completed.failed_count, 1)
        self.assertEqual(completed.private_candidate_count, 1)
        self.assertNotEqual(partial.receipt_sha256, completed.receipt_sha256)
        self.assertEqual(
            completed,
            build_private_batch_receipt_index(
                planned, (failure, successful, successful), previous_index=partial,
            ),
        )
        self.assertEqual(
            completed,
            build_private_batch_receipt_index(planned, (), previous_index=completed),
        )
        # Even a later legitimate-looking provider result cannot silently
        # rewrite a committed failure without a separately scoped retry run.
        revised = replace(failure, result="CANDIDATE_EXTRACTED",
                          failure_reason=None, extraction_version="extractor:retry:v2")
        with self.assertRaisesRegex(ValueError, "RECEIPT_REPLAY_CONFLICT"):
            build_private_batch_receipt_index(
                planned, (revised,), previous_index=completed,
            )
        with self.assertRaisesRegex(ValueError, "RECEIPT_REPLAY_CONFLICT"):
            build_private_batch_receipt_index(
                planned, (replace(failure, failure_reason="OTHER"),),
                previous_index=completed,
            )

    def test_receipt_index_rejects_foreign_plan_forgery_and_reordered_provenance(self):
        planned = plan()
        first = planned.items[0]
        observation = PrivateBatchResult(
            first.passage_id, first.content_id, first.capture_id, first.passage_sha256,
            "FAILED", "TIMEOUT", None,
        )
        index = build_private_batch_receipt_index(planned, (observation,))
        changes = (
            replace(index, receipt_sha256="0" * 64),
            replace(index, items=tuple(reversed(index.items))),
            replace(index, items=(replace(index.items[0], content_id="content:foreign"), *index.items[1:])),
            replace(index, items=(replace(index.items[0], failure_reason="FORGED"), *index.items[1:])),
            replace(index, items=(replace(index.items[0], speaker_candidate_id="person-candidate:other"), *index.items[1:])),
            replace(index, items=(replace(index.items[0], status="PRIVATE_CANDIDATE_UNVERIFIED"), *index.items[1:])),
            replace(index, observed_count=0),
        )
        for corrupted in changes:
            with self.subTest(corrupted=corrupted), self.assertRaisesRegex(
                ValueError, "RECEIPT_(?:INTEGRITY|PROVENANCE|COUNTS|ORDER)_INVALID",
            ):
                build_private_batch_receipt_index(planned, (), previous_index=corrupted)
        unrelated = plan(manifest(reverse=True))
        with self.assertRaisesRegex(ValueError, "RECEIPT_PLAN_MISMATCH"):
            build_private_batch_receipt_index(unrelated, (), previous_index=index)

    def test_rehashed_plan_cannot_override_rights_or_quoted_speaker_context(self):
        original = plan()
        item = original.items[0]
        cases = (
            {"rights_status": "REVOKED"},
            {"identity_review_status": "UNRESOLVED"},
            {"speech_role": "QUOTED_SPEAKER", "speech_act": "REPORTED_QUOTE"},
            {"context_review_id": None},
        )
        for change in cases:
            changed = rehash_plan(replace(
                original, items=(replace(item, **change), *original.items[1:]),
            ))
            with self.subTest(change=change), self.assertRaisesRegex(
                ValueError, "PLAN_STATUS_INVALID",
            ):
                build_private_batch_receipt_index(changed, ())

    def test_three_contents_three_person_candidates_never_share_source_partition(self):
        result = plan()
        self.assertEqual(len(result.items), 3)
        self.assertEqual(result.proposed_group_count, 3)
        self.assertEqual(result.total_estimated_tokens, 600)
        self.assertTrue(
            all(item.status == "PRIVATE_EXTRACTION_PROPOSED" for item in result.items)
        )
        self.assertTrue(
            all(not item.public_attribution_authority for item in result.items)
        )
        self.assertFalse(result.dispatch_authorized)
        self.assertEqual(result.provider_calls, 0)

    def test_batch_manifest_order_preserves_rows_but_has_distinct_lineage(self):
        ordered = plan(manifest())
        retried = plan(manifest())
        reversed_manifest = manifest(reverse=True)
        reversed_plan = plan(reversed_manifest)
        self.assertEqual(ordered.plan_sha256, retried.plan_sha256)
        self.assertEqual(ordered.items, reversed_plan.items)
        self.assertNotEqual(ordered.manifest_sha256, reversed_plan.manifest_sha256)
        self.assertNotEqual(ordered.plan_sha256, reversed_plan.plan_sha256)

    def test_original_manifest_digest_is_bound_into_replay_plan(self):
        original = plan()
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            reconcile_isolated_private_results(
                replace(original, manifest_sha256="f" * 64), ()
            )

    def test_rehashed_reordered_plan_is_not_canonical(self):
        original = plan()
        reordered = rehash_plan(replace(original, items=tuple(reversed(original.items))))
        with self.assertRaisesRegex(ValueError, "ORDER_INVALID"):
            reconcile_isolated_private_results(reordered, ())

    def test_rehashed_cross_person_partition_swap_cannot_borrow_source_lineage(self):
        original = plan()
        first, second, third = original.items
        self.assertNotEqual(first.speaker_candidate_id, second.speaker_candidate_id)
        # All other Content/Capture/Passage/Person fields stay untouched;
        # a recomputed SHA must not make another Person's partition canonical.
        swapped = rehash_plan(replace(original, items=(
            replace(first, partition_id=second.partition_id),
            replace(second, partition_id=first.partition_id),
            third,
        )))
        with self.assertRaisesRegex(ValueError, "MULTIPERSON_PLAN_PARTITION_MISMATCH"):
            reconcile_isolated_private_results(swapped, ())

    def test_rehashed_source_family_swap_cannot_reuse_foreign_partition(self):
        original = plan()
        first, second, third = original.items
        self.assertNotEqual(first.source_family, second.source_family)
        # A source family determines extraction policy and source isolation.
        # Recomputing only the outer plan SHA must not let an item keep its
        # original partition after silently borrowing another source family.
        swapped = rehash_plan(replace(original, items=(
            replace(first, source_family=second.source_family),
            replace(second, source_family=first.source_family),
            third,
        )))
        with self.assertRaisesRegex(ValueError, "MULTIPERSON_PLAN_PARTITION_MISMATCH"):
            reconcile_isolated_private_results(swapped, ())

        # A genuinely different upstream source-family manifest is a new
        # source partition even when its Passage and speaker IDs are equal.
        upstream = manifest()
        changed = replace(upstream, items=(
            replace(upstream.items[0], source_family="source-family:official-other"),
            *upstream.items[1:],
        ))
        changed = replace(changed, sha256=_batch_digest(changed))
        actual = plan(changed, reviewed_contexts(changed))
        self.assertNotEqual(original.items[0].partition_id, actual.items[0].partition_id)
        self.assertEqual(original.items[1].partition_id, actual.items[1].partition_id)
        self.assertNotEqual(original.plan_sha256, actual.plan_sha256)

        # Old source-family-unbound v1 plans cannot be silently upgraded by
        # supplying only their old version label and recomputed outer SHA.
        legacy = rehash_plan(replace(original, version="multi-person-candidate-isolation-v1"))
        with self.assertRaisesRegex(ValueError, "MULTIPERSON_PLAN_SCHEMA_INVALID"):
            reconcile_isolated_private_results(legacy, ())

    def test_rehashed_identity_review_or_context_receipt_swap_cannot_reuse_partition(self):
        original = plan()
        first, second, third = original.items
        # Both items remain eligible for a private proposal, but assigning
        # source B's review credential to A would change the claimed speaker
        # provenance without changing the current partition identifier.
        for updated in (
            replace(first, context_review_id=second.context_review_id),
            replace(first, identity_review_status="REVIEWED_SAME_PERSON"),
        ):
            with self.subTest(updated=updated):
                changed = rehash_plan(replace(original, items=(updated, second, third)))
                with self.assertRaisesRegex(ValueError, "MULTIPERSON_PLAN_PARTITION_MISMATCH"):
                    reconcile_isolated_private_results(changed, ())

    def test_rehashed_ready_plan_requires_a_nonempty_person_candidate(self):
        original = plan()
        for speaker in (None, "", "  "):
            mutated = replace(
                original,
                items=(
                    replace(original.items[0], speaker_candidate_id=speaker),
                    *original.items[1:],
                ),
            )
            with self.subTest(speaker=speaker), self.assertRaisesRegex(
                ValueError, "PLAN_(ITEM|STATUS)_INVALID"
            ):
                reconcile_isolated_private_results(rehash_plan(mutated), ())

    def test_provider_capability_gate_rejects_truthy_nonboolean_value(self):
        with self.assertRaisesRegex(ValueError, "CAPABILITY_INVALID"):
            plan(provider_capability_ready="false")

    def test_wrong_content_capture_or_source_sha_assignment_fails_before_plan(self):
        batch = manifest()
        for change in (
            dict(content_id="content:other"),
            dict(capture_id="capture:other"),
            dict(source_family="source-family:other"),
            dict(passage_sha256="f" * 64),
        ):
            ctx = reviewed_contexts(batch)
            ctx["passage:0"] = replace(ctx["passage:0"], **change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, "CROSS_SOURCE_REFERENCE"),
            ):
                plan(batch, ctx)

    def test_cross_speaker_reported_quote_criticism_held_no_endorsement(self):
        batch = manifest()
        for change in (
            dict(speech_role="QUOTED_SPEAKER", speech_act="REPORTED_QUOTE"),
            dict(speech_role="REPORTER", speech_act="OPINION"),
            dict(speech_act="CRITICISM"),
            dict(speech_act="IRONY"),
        ):
            ctx = reviewed_contexts(batch)
            ctx["passage:1"] = replace(ctx["passage:1"], **change)
            result = plan(batch, ctx)
            self.assertEqual(result.items[1].status, "HELD")
            self.assertEqual(
                result.items[1].reason_code, "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT"
            )
            self.assertTrue(
                all(not row.public_attribution_authority for row in result.items)
            )

    def test_homonyms_or_ambiguous_identity_never_promote_automatically(self):
        batch = manifest()
        for change in (
            dict(speaker_candidate_id=None),
            dict(identity_review_status="UNRESOLVED"),
            dict(speech_role="UNRESOLVED"),
            dict(speech_act="UNKNOWN"),
        ):
            ctx = reviewed_contexts(batch)
            ctx["passage:0"] = replace(ctx["passage:0"], **change)
            result = plan(batch, ctx)
            self.assertEqual(
                result.items[0].reason_code, "MULTIPERSON_SPEAKER_AMBIGUOUS"
            )

    def test_no_rights_or_no_context_review_holds_only_matching_item(self):
        batch = manifest()
        ctx = reviewed_contexts(batch)
        ctx["passage:0"] = replace(ctx["passage:0"], rights_status="REVOKED")
        ctx["passage:2"] = replace(ctx["passage:2"], context_review_id=None)
        result = plan(batch, ctx)
        self.assertEqual(
            [row.status for row in result.items],
            ["HELD", "PRIVATE_EXTRACTION_PROPOSED", "HELD"],
        )
        self.assertEqual(result.total_estimated_tokens, 200)

    def test_capability_missing_and_token_budget_hold_without_fake_bill(self):
        unavailable = plan(provider_capability_ready=False)
        self.assertEqual(unavailable.total_estimated_tokens, 0)
        self.assertTrue(
            all(
                row.reason_code == "MULTIPERSON_PROVIDER_CAPABILITY_UNAVAILABLE"
                for row in unavailable.items
            )
        )
        limited = plan(total_token_cap=220)
        self.assertEqual(
            [row.status for row in limited.items],
            ["PRIVATE_EXTRACTION_PROPOSED", "HELD", "HELD"],
        )
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
            PrivateBatchResult(
                first.passage_id,
                first.content_id,
                first.capture_id,
                first.passage_sha256,
                "CANDIDATE_EXTRACTED",
                None,
                "extractor:test:v1",
            ),
            PrivateBatchResult(
                last.passage_id,
                last.content_id,
                last.capture_id,
                last.passage_sha256,
                "FAILED",
                "PROVIDER_UNAVAILABLE",
                None,
            ),
        )
        result = reconcile_isolated_private_results(planned, observations)
        self.assertEqual(
            result.statuses,
            (
                ("passage:0", "PRIVATE_CANDIDATE_UNVERIFIED"),
                ("passage:1", "HELD"),
                ("passage:2", "FAILED"),
            ),
        )
        self.assertEqual(
            (result.private_candidate_count, result.held_count, result.failed_count),
            (1, 1, 1),
        )
        self.assertFalse(result.publication_authority)
        self.assertEqual(
            result,
            reconcile_isolated_private_results(planned, tuple(reversed(observations))),
        )

    def test_wrong_source_from_model_and_held_row_fake_success_rejected(self):
        planned = plan()
        first = planned.items[0]
        observed = PrivateBatchResult(
            first.passage_id,
            "content:foreign",
            first.capture_id,
            first.passage_sha256,
            "CANDIDATE_EXTRACTED",
            None,
            "test:v1",
        )
        with self.assertRaisesRegex(ValueError, "SOURCE_MISMATCH"):
            reconcile_isolated_private_results(planned, (observed,))
        held = plan(provider_capability_ready=False)
        observed = replace(observed, content_id=first.content_id)
        with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_SUCCESS"):
            reconcile_isolated_private_results(held, (observed,))

    def test_held_item_cannot_claim_provider_failure_or_override_hold(self):
        held = plan(provider_capability_ready=False)
        item = held.items[0]
        failed = PrivateBatchResult(
            item.passage_id,
            item.content_id,
            item.capture_id,
            item.passage_sha256,
            "FAILED",
            "PROVIDER_UNAVAILABLE",
            None,
        )
        with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_RESULT"):
            reconcile_isolated_private_results(held, (failed,))
        self.assertEqual(
            reconcile_isolated_private_results(held, ()).statuses[0],
            (item.passage_id, "HELD"),
        )

    def test_conflicting_replay_and_unbounded_batch_rejected(self):
        planned = plan()
        item = planned.items[0]
        row = PrivateBatchResult(
            item.passage_id,
            item.content_id,
            item.capture_id,
            item.passage_sha256,
            "FAILED",
            "OFFLINE",
            None,
        )
        self.assertEqual(
            reconcile_isolated_private_results(planned, (row, row)).failed_count, 1
        )
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            reconcile_isolated_private_results(
                planned, (row, replace(row, failure_reason="TIMEOUT"))
            )
        with self.assertRaisesRegex(ValueError, "SIZE_INVALID"):
            plan(manifest(17))

    def test_reconciliation_rejects_manipulated_plan_hash_items_and_counts(self):
        original = plan()
        for mutated in (
            replace(original, plan_sha256="0" * 64),
            replace(original, collection_id="other:collection"),
            replace(original, items=original.items[:2]),
            replace(
                original,
                items=(
                    replace(original.items[0], passage_sha256="e" * 64),
                    *original.items[1:],
                ),
            ),
        ):
            with (
                self.subTest(mutated=mutated),
                self.assertRaisesRegex(ValueError, "TAMPERED|COUNTS"),
            ):
                reconcile_isolated_private_results(mutated, ())

    def test_rehashed_plan_cannot_assert_authority_duplicate_or_fake_counts(self):
        original = plan()
        item = original.items[0]
        for change in (
            dict(provider_calls=1),
            dict(dispatch_authorized=True),
            dict(total_estimated_tokens=0),
            dict(proposed_group_count=2),
            dict(items=(item, item, original.items[2])),
            dict(
                items=(
                    replace(item, public_attribution_authority=True),
                    *original.items[1:],
                )
            ),
            dict(
                items=(
                    replace(item, reason_code="MULTIPERSON_CONTEXT_UNREVIEWED"),
                    *original.items[1:],
                )
            ),
            dict(items=(replace(item, status="HELD"), *original.items[1:])),
        ):
            mutated = replace(original, **change)
            mutated = rehash_plan(mutated)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(
                    ValueError, "AUTHORITY|COUNTS|DUPLICATE|ITEM_INVALID|STATUS_INVALID"
                ),
            ):
                reconcile_isolated_private_results(mutated, ())

    def test_same_source_distinct_passages_stay_distinct_partitions(self):
        original = manifest(2)
        first, second = original.items
        # Two exact Passages from ONE Content/Capture/source are still separate
        # source-bound extraction units (the earlier fixture used two sources).
        second = replace(
            second,
            content_id=first.content_id,
            capture_id=first.capture_id,
            canonical_url=first.canonical_url,
            source_family=first.source_family,
        )
        batch = replace(original, items=(first, second), sha256="")
        batch = replace(batch, sha256=_batch_digest(batch))
        contexts = reviewed_contexts(batch)
        contexts["passage:1"] = replace(
            contexts["passage:1"],
            speaker_candidate_id=contexts["passage:0"].speaker_candidate_id,
            language_tag="it",
        )
        planned = plan(batch, contexts)
        self.assertEqual(planned.items[0].source_sha256, planned.items[1].source_sha256)
        self.assertEqual(planned.items[0].capture_id, planned.items[1].capture_id)
        self.assertNotEqual(
            planned.items[0].partition_id, planned.items[1].partition_id
        )

    def test_unbounded_observations_and_unjustified_result_metadata_rejected(self):
        original = plan()
        item = original.items[0]
        observed = PrivateBatchResult(
            item.passage_id,
            item.content_id,
            item.capture_id,
            item.passage_sha256,
            "HELD",
            None,
            None,
        )
        with self.assertRaisesRegex(ValueError, "RESULT_INPUT_INVALID"):
            reconcile_isolated_private_results(original, (observed,) * 65)
        for invalid in (
            replace(observed, failure_reason="pretend review"),
            replace(observed, extraction_version="pretend-version"),
            replace(
                observed,
                result="FAILED",
                failure_reason="OFFLINE",
                extraction_version="fake",
            ),
            replace(observed, result="CANDIDATE_EXTRACTED", extraction_version=" "),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reconcile_isolated_private_results(original, (invalid,))


if __name__ == "__main__":
    unittest.main()

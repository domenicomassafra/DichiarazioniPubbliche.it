"""DP-519 synthetic/private visual-operator capacity contract tests."""

from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from dichiarazioni_pubbliche.visual_operator_capacity_v1 import (
    VisualWorkItem,
    VisualDecisionEvent,
    VisualException,
    reconcile_visual_capacity,
)


NOW = datetime(2026, 10, 11, 14, tzinfo=timezone.utc)


def digest(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def work(
    name="a",
    *,
    reason="IMAGE_IDENTITY",
    rights="CLEARED",
    identity="MATCH_REVIEWED",
    image=True,
    age_days=2,
    estimate=12,
):
    return VisualWorkItem(
        work_key=f"visual:{name}",
        content_id=f"content:{name}",
        person_id=f"person:{name}",
        reason_code=reason,
        asset_sha256=digest(f"image:{name}") if image else None,
        source_version_sha256=digest("version:" + name),
        preview_ref="private:preview:" + name if image else None,
        source_rights_state=rights,
        person_identity_state=identity,
        created_at=NOW - timedelta(days=age_days),
        expires_at=NOW + timedelta(days=3),
        estimated_minutes=estimate,
        automated_attempt_hashes=(digest("attempt:" + name),),
    )


def event(
    item,
    eid="e1",
    *,
    action="NO_IMAGE",
    minutes=7,
    actor="owner:1",
    completed=NOW,
    previous=None,
    asset=None,
    version=None,
):
    return VisualDecisionEvent(
        event_id="event:" + eid,
        work_key=item.work_key,
        actor_id=actor,
        action=action,
        source_version_sha256=version or item.source_version_sha256,
        asset_sha256=asset,
        started_at=completed - timedelta(minutes=minutes),
        completed_at=completed,
        prior_event_id=previous,
    )


def exception(name="x", *, attempts=True, minutes=10):
    return VisualException(
        exception_id="exception:" + name,
        work_key="visual:" + name,
        question_code="SOURCE_RIGHTS_REVIEW_NEEDED",
        prior_attempt_hashes=(digest("attempt:" + name),) if attempts else (),
        estimated_minutes=minutes,
        authority_state="UNRESOLVED",
    )


class VisualOperatorCapacityTests(unittest.TestCase):
    def test_empty_and_missing_images_never_create_human_work_or_public_authority(self):
        missing = work("missing", reason="IMAGE_MISSING", image=False)
        report = reconcile_visual_capacity((missing,), (), (), now=NOW)
        self.assertEqual(report.rows[0].state, "NO_IMAGE_FALLBACK")
        self.assertEqual(report.rows[0].public_alt_text, "")
        self.assertEqual(report.future_estimated_minutes, 0)
        self.assertEqual(report.actual_minutes_this_week, 0)
        self.assertFalse(report.publication_authority)
        self.assertFalse(report.text_review_authority)
        self.assertFalse(report.image_approval_authority)
        self.assertTrue(report.rows[0].text_only_record_unblocked_by_missing_image)
        self.assertEqual(reconcile_visual_capacity((), (), (), now=NOW).rows, ())

    def test_rights_unknown_and_identity_ambiguous_fail_closed_without_auto_image(self):
        rights = work("rights", rights="UNKNOWN")
        person = work("person", identity="AMBIGUOUS")
        report = reconcile_visual_capacity((rights, person), (), (), now=NOW)
        self.assertEqual(
            {r.work_key: r.state for r in report.rows},
            {
                "visual:rights": "HELD_RIGHTS_NO_IMAGE",
                "visual:person": "HELD_IDENTITY_NO_IMAGE",
            },
        )
        self.assertTrue(all(not r.image_eligible for r in report.rows))
        self.assertTrue(all(r.public_alt_text == "" for r in report.rows))
        self.assertTrue(
            all(r.text_only_record_unblocked_by_missing_image for r in report.rows)
        )

    def test_visual_selection_is_private_candidate_never_authenticity_or_publication(
        self,
    ):
        item = work()
        chosen = event(item, action="CHOOSE_CANDIDATE", asset=item.asset_sha256)
        report = reconcile_visual_capacity((item,), (chosen,), (), now=NOW)
        row = report.rows[0]
        self.assertEqual(row.state, "PRIVATE_IMAGE_CANDIDATE_ONLY")
        self.assertFalse(row.image_eligible)
        self.assertFalse(report.image_approval_authority)
        self.assertEqual(row.last_action, "CHOOSE_CANDIDATE")
        self.assertEqual(report.actual_minutes_this_week, 7)
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_SELECTED_ASSET_MISMATCH"):
            reconcile_visual_capacity(
                (item,), (replace(chosen, asset_sha256=digest("other")),), (), now=NOW
            )

    def test_no_image_selection_is_final_fallback_with_measured_minutes(self):
        item = work()
        receipt = event(item)
        report = reconcile_visual_capacity((item,), (receipt,), (), now=NOW)
        self.assertEqual(report.rows[0].state, "NO_IMAGE_SELECTED")
        self.assertEqual(report.rows[0].public_alt_text, "")
        self.assertFalse(report.rows[0].image_eligible)
        self.assertEqual(report.future_estimated_minutes, 0)
        self.assertEqual(report.actual_minutes_this_week, 7)

    def test_idempotent_duplicate_work_and_receipt_replay_do_not_double_charge(self):
        item = work()
        receipt = event(item)
        report = reconcile_visual_capacity(
            (item, item), (receipt, receipt), (), now=NOW
        )
        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.ledger_event_count, 1)
        self.assertEqual(report.actual_minutes_this_week, 7)
        self.assertEqual(
            report, reconcile_visual_capacity((item,), (receipt,), (), now=NOW)
        )
        with self.assertRaisesRegex(ValueError, "DP519_WORK_KEY_CONFLICT"):
            reconcile_visual_capacity(
                (item, replace(item, source_rights_state="REVOKED")), (), (), now=NOW
            )
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_REPLAY_CONFLICT"):
            reconcile_visual_capacity(
                (item,), (receipt, replace(receipt, action="DEFER")), (), now=NOW
            )

    def test_stale_version_and_revoked_rights_withdraw_candidate_but_keep_history(self):
        item = work()
        receipt = event(item, action="CHOOSE_CANDIDATE", asset=item.asset_sha256)
        updated = replace(item, source_version_sha256=digest("new version"))
        stale = reconcile_visual_capacity((updated,), (receipt,), (), now=NOW)
        self.assertEqual(stale.rows[0].state, "STALE_IMAGE_VERSION_HOLD")
        self.assertTrue(stale.rows[0].withdrawal_review_required)
        self.assertEqual(stale.ledger_event_count, 1)
        revoked = reconcile_visual_capacity(
            (replace(item, source_rights_state="REVOKED"),), (receipt,), (), now=NOW
        )
        self.assertEqual(revoked.rows[0].state, "HELD_RIGHTS_NO_IMAGE")
        self.assertTrue(revoked.rows[0].withdrawal_review_required)
        self.assertFalse(revoked.image_approval_authority)

    def test_replay_chain_must_be_linear_and_actual_time_cannot_overlap(self):
        item = work()
        first = event(item, "a", action="DEFER", completed=NOW - timedelta(hours=2))
        second = event(item, "b", action="NO_IMAGE", previous=first.event_id)
        report = reconcile_visual_capacity((item,), (second, first), (), now=NOW)
        self.assertEqual(report.ledger_event_count, 2)
        self.assertEqual(report.actual_minutes_this_week, 14)
        self.assertEqual(report.rows[0].last_action, "NO_IMAGE")
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_CHAIN_INVALID"):
            reconcile_visual_capacity(
                (item,), (first, replace(second, prior_event_id=None)), (), now=NOW
            )
        overlapping = event(work("other"), "c", completed=NOW)
        with self.assertRaisesRegex(ValueError, "DP519_ACTOR_TIME_OVERLAP"):
            reconcile_visual_capacity(
                (item, work("other")), (second, first, overlapping), (), now=NOW
            )

    def test_iso_week_actual_minutes_separate_from_future_estimate_and_median(self):
        a, b, c = work("a", estimate=12), work("b", estimate=20), work("c", estimate=25)
        current = event(a, "current", minutes=9)
        last_week = event(b, "past", minutes=13, completed=NOW - timedelta(days=7))
        report = reconcile_visual_capacity((a, b, c), (current, last_week), (), now=NOW)
        self.assertEqual(report.actual_minutes_this_week, 9)
        self.assertEqual(sum(report.actual_minutes_by_week.values()), 22)
        self.assertEqual(report.future_estimated_minutes, 25)
        self.assertEqual(report.median_minutes_by_reason["IMAGE_IDENTITY"], 11)
        self.assertEqual(report.weekly_planning_minutes, 300)

    def test_over_capacity_pauses_optional_work_and_prefers_no_photo_without_fake_review(
        self,
    ):
        a, b = work("a", estimate=20), work("b", estimate=30)
        event_a = event(a, minutes=295)
        report = reconcile_visual_capacity((a, b), (event_a,), (), now=NOW)
        self.assertEqual(report.actual_minutes_this_week, 295)
        self.assertEqual(report.available_planning_minutes, 5)
        self.assertEqual(report.rows[1].state, "CAPACITY_NO_IMAGE_OPTION")
        self.assertFalse(report.rows[1].image_eligible)
        self.assertEqual(report.ledger_event_count, 1)
        self.assertEqual(report.future_estimated_minutes, 30)
        self.assertEqual(report.older_unresolved_count, 0)

    def test_capacity_reservations_follow_priority_independent_of_input_order(self):
        a, b = work("a", estimate=25, age_days=5), work("b", estimate=25, age_days=1)
        first = reconcile_visual_capacity(
            (a, b), (), (), now=NOW, weekly_planning_minutes=40
        )
        replay = reconcile_visual_capacity(
            (b, a), (), (), now=NOW, weekly_planning_minutes=40
        )
        self.assertEqual(first, replay)
        self.assertEqual(
            [(r.work_key, r.state) for r in first.rows],
            [
                (a.work_key, "WAIT_VISUAL_OPERATOR"),
                (b.work_key, "CAPACITY_NO_IMAGE_OPTION"),
            ],
        )
        self.assertEqual(first.future_estimated_minutes, 50)
        self.assertEqual(first.available_planning_minutes, 40)

    def test_expired_selected_image_requires_withdrawal_not_a_valid_candidate(self):
        item = work()
        picked = event(item, action="CHOOSE_CANDIDATE", asset=item.asset_sha256)
        expired = replace(item, expires_at=NOW - timedelta(minutes=1))
        outcome = reconcile_visual_capacity((expired,), (picked,), (), now=NOW)
        self.assertEqual(outcome.rows[0].state, "EXPIRED_IMAGE_HOLD")
        self.assertTrue(outcome.rows[0].withdrawal_review_required)
        self.assertFalse(outcome.rows[0].image_eligible)

    def test_week_crossing_receipt_is_split_into_actual_iso_weeks(self):
        # 2026-10-12 Mon 00:00 UTC is the ISO week boundary.
        clock = datetime(2026, 10, 12, 0, 11, tzinfo=timezone.utc)
        item = replace(work(), expires_at=clock + timedelta(days=1))
        receipt = event(item, completed=clock, minutes=20)
        result = reconcile_visual_capacity((item,), (receipt,), (), now=clock)
        self.assertEqual(result.actual_minutes_by_week["2026-W41"], 9)
        self.assertEqual(result.actual_minutes_by_week["2026-W42"], 11)
        self.assertEqual(result.actual_minutes_this_week, 11)

    def test_exception_same_work_and_question_cannot_duplicate_owner_task(self):
        item = work("x")
        a = exception()
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_DUPLICATE_QUESTION"):
            reconcile_visual_capacity(
                (item,), (), (a, replace(a, exception_id="exception:again")), now=NOW
            )
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_QUESTION_INVALID"):
            reconcile_visual_capacity(
                (item,),
                (),
                (replace(a, question_code="FACTUAL_VERDICT_APPROVE"),),
                now=NOW,
            )

    def test_preview_requires_private_ref_and_historical_choice_withdrawal_survives_defer(
        self,
    ):
        item = work()
        with self.assertRaisesRegex(ValueError, "DP519_PRIVATE_PREVIEW_REQUIRED"):
            reconcile_visual_capacity(
                (replace(item, preview_ref="https://outside.example/photo"),),
                (),
                (),
                now=NOW,
            )
        picked = event(
            item,
            "picked",
            action="CHOOSE_CANDIDATE",
            asset=item.asset_sha256,
            completed=NOW - timedelta(hours=2),
        )
        deferred = event(item, "defer", action="DEFER", previous=picked.event_id)
        revoked = replace(item, source_rights_state="REVOKED")
        result = reconcile_visual_capacity((revoked,), (picked, deferred), (), now=NOW)
        self.assertEqual(result.rows[0].state, "HELD_RIGHTS_NO_IMAGE")
        self.assertTrue(result.rows[0].withdrawal_review_required)

    def test_expiry_age_reason_priority_deterministic(self):
        urgent = replace(
            work("urgent", age_days=12), expires_at=NOW + timedelta(minutes=1)
        )
        recent = work("recent", age_days=1)
        report = reconcile_visual_capacity((recent, urgent), (), (), now=NOW)
        self.assertEqual(report.rows[0].work_key, urgent.work_key)
        self.assertEqual(report.older_unresolved_count, 1)
        self.assertEqual(
            report, reconcile_visual_capacity((urgent, recent), (), (), now=NOW)
        )

    def test_exception_requires_attempt_receipts_exact_question_and_limited_count(self):
        item = work("x")
        with self.assertRaisesRegex(
            ValueError, "DP519_EXCEPTION_PRIOR_ATTEMPTS_REQUIRED"
        ):
            reconcile_visual_capacity(
                (item,), (), (exception(attempts=False),), now=NOW
            )
        report = reconcile_visual_capacity((item,), (), (exception(),), now=NOW)
        self.assertEqual(len(report.exceptions), 1)
        self.assertEqual(
            report.exceptions[0].state, "WAIT_QUALIFIED_EXTERNAL_AUTHORITY"
        )
        self.assertFalse(report.exceptions[0].text_review_authority)
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_UNBOUNDED"):
            reconcile_visual_capacity((item,), (), (exception(),) * 9, now=NOW)

    def test_exception_attempts_must_belong_to_the_same_work_item(self):
        item = work("x")
        other = work("other")
        forged = replace(
            exception("x"),
            prior_attempt_hashes=other.automated_attempt_hashes,
        )
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_ATTEMPT_NOT_IN_WORK"):
            reconcile_visual_capacity((item, other), (), (forged,), now=NOW)
        uninvestigated = replace(item, automated_attempt_hashes=())
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_ATTEMPT_NOT_IN_WORK"):
            reconcile_visual_capacity((uninvestigated,), (), (exception("x"),), now=NOW)
        mixed = replace(
            item,
            automated_attempt_hashes=(digest("attempt:x"), digest("other-verified")),
        )
        partially_forged = replace(
            exception("x"),
            prior_attempt_hashes=(digest("attempt:x"), digest("unknown")),
        )
        with self.assertRaisesRegex(ValueError, "DP519_EXCEPTION_ATTEMPT_NOT_IN_WORK"):
            reconcile_visual_capacity((mixed,), (), (partially_forged,), now=NOW)
        # An accepted subset means a concrete investigation is linked to this
        # work, while unrelated recorded attempts are left in its history.
        report = reconcile_visual_capacity((mixed,), (), (exception("x"),), now=NOW)
        self.assertEqual(len(report.exceptions), 1)
        self.assertFalse(report.exceptions[0].text_review_authority)

    def test_median_tracks_case_handling_total_not_each_split_receipt(self):
        a, b, c = work("a"), work("b"), work("c")
        a_start = event(
            a,
            "a-first",
            action="DEFER",
            minutes=3,
            completed=NOW - timedelta(hours=3),
        )
        a_finish = event(
            a,
            "a-second",
            minutes=7,
            previous=a_start.event_id,
            completed=NOW - timedelta(hours=2),
        )
        b_once = event(b, "b", minutes=20, completed=NOW - timedelta(hours=1))
        c_once = event(c, "c", minutes=40, completed=NOW)
        report = reconcile_visual_capacity(
            (c, b, a), (a_finish, c_once, b_once, a_start), (), now=NOW
        )
        self.assertEqual(report.ledger_event_count, 4)
        self.assertEqual(report.actual_minutes_this_week, 70)
        # One 10-minute case, one 20-minute case, one 40-minute case.
        self.assertEqual(report.median_minutes_by_reason["IMAGE_IDENTITY"], 20)
        self.assertEqual(
            report,
            reconcile_visual_capacity(
                (a, b, c), (a_start, b_once, c_once, a_finish), (), now=NOW
            ),
        )

    def test_invalid_time_negative_duration_forged_fields_and_bounded_inputs_rejected(
        self,
    ):
        item = work()
        bad = event(item)
        variants = (
            replace(bad, started_at=bad.completed_at + timedelta(minutes=1)),
            replace(bad, completed_at=NOW + timedelta(days=2)),
            replace(bad, actor_id="fake\nactor"),
        )
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    reconcile_visual_capacity((item,), (value,), (), now=NOW)
        with self.assertRaisesRegex(ValueError, "DP519_INPUT_UNBOUNDED"):
            reconcile_visual_capacity(
                tuple(work(str(n)) for n in range(65)), (), (), now=NOW
            )
        with self.assertRaisesRegex(ValueError, "DP519_EVENT_FOREIGN_WORK"):
            reconcile_visual_capacity((item,), (event(work("foreign")),), (), now=NOW)


if __name__ == "__main__":
    unittest.main()

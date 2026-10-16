"""DP-439: genuine pinned opinion releases compared only in private memory."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "poc"), str(ROOT / "tests")]

from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3  # noqa: E402
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402
from test_dp439_person_topic_v3 import event, fixture, identity, make  # noqa: E402


def releases():
    """Approved, original-dated actual projection: Aug retired, Oct added."""
    source, _, _, roster = fixture()
    for owner, printed_date in zip(
        source.subjects, ("2026-08-24", "2026-09-13", "2026-10-03"), strict=True
    ):
        owner.row["statement_date"] = printed_date
        for gate in owner.gates.values():
            gate["statement_date"] = printed_date
    bundle = source.build()
    bundle["topics"] = [
        {
            "topic_id": f"topic:{slug}",
            "slug": slug,
            "canonical_name": "Economia",
            "scope_text": "Topic approvato sintetico",
            "entity_version": "topic-version:1",
            "review_event_ids": [f"review:topic:{slug}"],
            "memberships": [],
        }
        for slug in ("economia", "economica")
    ]
    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
    people = build_public_people_v3(
        roster,
        [identity(person) for person in roster],
        [],
        [],
        public_bundle=bundle,
        current_public_dataset_sha256=bundle["dataset_sha256"],
        allow_public_person_v3=True,
    )
    original = (
        event(bundle, 0, "topic:economia"),
        event(bundle, 1, "topic:economia"),
        event(bundle, 1, "topic:economica"),
    )
    retired = replace(
        original[0],
        status="REVOKED",
        revision=2,
        review_event_id="review:membership:retirement:2",
    )
    new = event(bundle, 2, "topic:economia")
    before = make(bundle, people, original)
    after = make(bundle, people, (*original, retired, new))
    return before, after, bundle, people


def compare(before, after, bundle, people, **overrides):
    from dichiarazioni_pubbliche.private_person_topic_trend_v1 import (
        inspect_private_person_topic_monthly_changes,
    )

    arguments = {
        "earlier_read_model": before,
        "later_read_model": after,
        "expected_earlier_join_sha256": before["dataset_sha256"],
        "expected_earlier_statement_sha256": bundle["dataset_sha256"],
        "expected_earlier_people_sha256": people["dataset_sha256"],
        "expected_later_join_sha256": after["dataset_sha256"],
        "expected_later_statement_sha256": bundle["dataset_sha256"],
        "expected_later_people_sha256": people["dataset_sha256"],
        "earlier_as_of": date(2026, 10, 11),
        "later_as_of": date(2026, 10, 12),
        "earlier_snapshot_created_at": "2026-10-11T14:30:00+00:00",
        "later_snapshot_created_at": "2026-10-11T16:30:00+00:00",
        "allow_offline_review": True,
    }
    arguments.update(overrides)
    return inspect_private_person_topic_monthly_changes(**arguments)


class PrivatePersonTopicTrendTests(unittest.TestCase):
    def setUp(self):
        self.before, self.after, self.bundle, self.people = releases()

    def review(self, **kwargs):
        return compare(self.before, self.after, self.bundle, self.people, **kwargs)

    def test_three_actual_original_months_and_retired_new_visibility(self):
        result = self.review()
        self.assertEqual(result["status"], "CHANGED")
        self.assertEqual(result["earlier_record_count"], 3)
        self.assertEqual(result["later_record_count"], 3)
        self.assertEqual(result["earlier_unique_statement_count"], 2)
        self.assertEqual(result["later_unique_statement_count"], 2)
        self.assertEqual(result["newly_visible_intersection_count"], 1)
        self.assertEqual(result["no_longer_visible_intersection_count"], 1)
        self.assertEqual(result["newly_visible_unique_statement_count"], 1)
        self.assertEqual(result["no_longer_visible_unique_statement_count"], 1)
        self.assertEqual(
            [
                (
                    r["month"],
                    r["earlier_record_count"],
                    r["later_record_count"],
                    r["newly_visible_intersection_count"],
                    r["no_longer_visible_intersection_count"],
                )
                for r in result["periods"]
            ],
            [
                ("2026-10", 0, 1, 1, 0),
                ("2026-09", 2, 2, 0, 0),
                ("2026-08", 1, 0, 0, 1),
            ],
        )
        self.assertEqual(result["periods"][1]["earlier_unique_statement_count"], 1)
        self.assertEqual(result["periods"][1]["later_unique_statement_count"], 1)
        self.assertIn("NOT_EVENT_DATE", result["change_time_meaning"])
        for field in (
            "publication_authority",
            "rights_authority",
            "absence_of_statements_established",
        ):
            self.assertIs(result[field], False)
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result, self.review())
        serialized = json.dumps(result)
        for excluded in (
            "Alex Demo",
            "person:A",
            "topic:economia",
            "original",
            "review:membership",
            "https://",
        ):
            self.assertNotIn(excluded, serialized)

    def test_same_original_with_two_topics_counts_as_one_and_topic_change_not_new_original(
        self,
    ):
        original, later = copy.deepcopy(self.before), copy.deepcopy(self.after)
        # A new approved Topic intersection for statement:2, already visible
        # elsewhere, changes intersection counts without inventing a new original.
        from test_dp439_person_topic_v3 import published

        _, bundle, people, _, decisions = published()
        before = make(bundle, people, (decisions[0], decisions[1]))
        after = make(bundle, people, (decisions[0], decisions[1], decisions[2]))
        result = compare(before, after, bundle, people)
        self.assertEqual(result["newly_visible_intersection_count"], 1)
        self.assertEqual(result["newly_visible_unique_statement_count"], 0)
        self.assertEqual(result["later_record_count"], 3)
        self.assertEqual(result["later_unique_statement_count"], 2)
        self.assertEqual(original, self.before)
        self.assertEqual(later, self.after)

    def test_exact_person_topic_id_filters_and_private_unknown_never_echo(self):
        result = self.review(person_id="person:A", topic_id="topic:economia")
        self.assertEqual(result["earlier_record_count"], 2)
        self.assertEqual(result["later_record_count"], 1)
        self.assertEqual(result["no_longer_visible_intersection_count"], 1)
        unknown = self.review(person_id="person:PRIVATE_SENTINEL")
        self.assertEqual(unknown["status"], "NO_MATCH")
        self.assertEqual(unknown["periods"], [])
        self.assertNotIn("PRIVATE_SENTINEL", repr(unknown))
        with self.assertRaises(ValueError):
            self.review(topic_id="../../private")

    def test_fixed_month_window_and_identical_release(self):
        sep = self.review(first_month="2026-09", last_month="2026-09")
        self.assertEqual([r["month"] for r in sep["periods"]], ["2026-09"])
        self.assertEqual(sep["status"], "UNCHANGED")
        self.assertEqual(sep["newly_visible_intersection_count"], 0)
        empty = self.review(first_month="2026-07", last_month="2026-07")
        self.assertEqual(empty["status"], "NO_MATCH")
        self.assertFalse(empty["absence_of_statements_established"])
        unchanged = self.review(
            later_read_model=self.before,
            expected_later_join_sha256=self.before["dataset_sha256"],
        )
        self.assertEqual(unchanged["status"], "UNCHANGED")
        self.assertEqual(unchanged["no_longer_visible_intersection_count"], 0)

    def test_as_of_must_follow_snapshots_and_order_cannot_reverse(self):
        with self.assertRaisesRegex(ValueError, "TEMPORAL_SNAPSHOT_IN_FUTURE"):
            self.review(earlier_as_of=date(2026, 10, 5))
        with self.assertRaisesRegex(ValueError, "TEMPORAL_SNAPSHOT_IN_FUTURE"):
            self.review(later_as_of=date(2026, 10, 5), earlier_as_of=date(2026, 10, 1))
        with self.assertRaisesRegex(ValueError, "TREND_DATE_ORDER_INVALID"):
            self.review(earlier_as_of=date(2026, 10, 13))
        with self.assertRaisesRegex(ValueError, "TREND_DATE_ORDER_INVALID"):
            self.review(earlier_as_of="2026-10-10")

    def test_each_snapshot_has_own_creation_gate_and_releases_must_be_chronological(
        self,
    ):
        # A recomputed digest creates an internally consistent synthetic read
        # model, but only the separately supplied SHA is accepted by the reader.
        from dichiarazioni_pubbliche.public_person_topic_v3 import (
            _digest,
            _public_material,
        )

        def changed_generated_at(model, when):
            row = copy.deepcopy(model)
            row["generated_at"] = when
            row["dataset_sha256"] = _digest(_public_material(row))
            return row

        future = changed_generated_at(self.after, "2026-10-14T12:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "TEMPORAL_SNAPSHOT_IN_FUTURE"):
            self.review(
                later_read_model=future,
                expected_later_join_sha256=future["dataset_sha256"],
                later_as_of=date(2026, 10, 13),
            )
        # The join's generated_at is the SOURCE projection timestamp. Only
        # an independent JOIN-creation receipt prevents false backdating.
        with self.assertRaisesRegex(ValueError, "TREND_SNAPSHOT_IN_FUTURE"):
            self.review(later_snapshot_created_at="2026-10-13T08:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "TREND_CREATION_PROVENANCE_INVALID"):
            self.review(earlier_snapshot_created_at="2026-10-10T16:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "TREND_CREATION_RECEIPT_INVALID"):
            self.review(earlier_snapshot_created_at="2026-10-11T14:30:00")
        prior_is_newer = changed_generated_at(self.before, "2026-10-12T12:00:00+00:00")
        later_is_older = changed_generated_at(self.after, "2026-10-11T12:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "TREND_SNAPSHOT_ORDER_INVALID"):
            self.review(
                earlier_read_model=prior_is_newer,
                later_read_model=later_is_older,
                expected_earlier_join_sha256=prior_is_newer["dataset_sha256"],
                expected_later_join_sha256=later_is_older["dataset_sha256"],
                earlier_as_of=date(2026, 10, 12),
                later_as_of=date(2026, 10, 13),
                earlier_snapshot_created_at="2026-10-12T13:00:00+00:00",
                later_snapshot_created_at="2026-10-11T14:30:00+00:00",
            )
        # A later JOIN may lawfully consume an older SOURCE projection (e.g.
        # rollback). Its independent join-created receipts, not source dates,
        # define the historical ordering.
        permissible_rollback = self.review(
            earlier_read_model=prior_is_newer,
            later_read_model=later_is_older,
            expected_earlier_join_sha256=prior_is_newer["dataset_sha256"],
            expected_later_join_sha256=later_is_older["dataset_sha256"],
            earlier_as_of=date(2026, 10, 12),
            later_as_of=date(2026, 10, 13),
            earlier_snapshot_created_at="2026-10-12T13:00:00+00:00",
            later_snapshot_created_at="2026-10-12T14:00:00+00:00",
        )
        self.assertEqual(permissible_rollback["status"], "CHANGED")

    def test_signed_sha_tampering_explicit_optin_and_detached_read(self):
        for overrides in (
            {"allow_offline_review": False},
            {"expected_earlier_join_sha256": "0" * 64},
            {"expected_later_statement_sha256": "0" * 64},
            {"expected_earlier_people_sha256": "0" * 64},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.review(**overrides)
        tampered = copy.deepcopy(self.after)
        tampered["data"][0]["statement"]["original"]["text"] = "SECRET_SENTINEL"
        with self.assertRaises(ValueError):
            self.review(later_read_model=tampered)
        original = copy.deepcopy(self.after)
        forged = copy.deepcopy(original["data"][0])
        forged["person_id"] = "person:PRIVATE_SENTINEL"

        class SwappedOnLateRead(dict):
            reads = 0

            def __getitem__(self, key):
                if key == "data":
                    self.reads += 1
                    if self.reads >= 4:
                        return [forged]
                return super().__getitem__(key)

        bad = SwappedOnLateRead(original)
        view = self.review(later_read_model=bad, person_id="person:PRIVATE_SENTINEL")
        self.assertEqual(view["status"], "NO_MATCH")
        self.assertEqual(view["newly_visible_intersection_count"], 0)
        self.assertNotIn("PRIVATE_SENTINEL", repr(view))

    def test_immutable_original_identity_date_drift_across_snapshots_refused(self):
        # Both releases have valid, independently pinned source+People joins,
        # but a historical original under the same version ID moved months.
        source, _, _, roster = fixture()
        source.subjects[0].row["statement_date"] = "2026-09-01"
        for gate in source.subjects[0].gates.values():
            gate["statement_date"] = "2026-09-01"
        changed = source.build()
        changed["topics"] = copy.deepcopy(self.bundle["topics"])
        changed["dataset_sha256"] = projection_dataset_sha256(changed)
        people = build_public_people_v3(
            roster,
            [identity(p) for p in roster],
            [],
            [],
            public_bundle=changed,
            current_public_dataset_sha256=changed["dataset_sha256"],
            allow_public_person_v3=True,
        )
        different = make(changed, people, (event(changed, 0, "topic:economia"),))
        with self.assertRaisesRegex(ValueError, "TREND_ORIGINAL_IDENTITY_DRIFT"):
            self.review(
                later_read_model=different,
                expected_later_join_sha256=different["dataset_sha256"],
                expected_later_statement_sha256=changed["dataset_sha256"],
                expected_later_people_sha256=people["dataset_sha256"],
            )
        # A narrower facet must not hide contradictory original-version data.
        with self.assertRaisesRegex(ValueError, "TREND_ORIGINAL_IDENTITY_DRIFT"):
            self.review(
                person_id="person:B",
                later_read_model=different,
                expected_later_join_sha256=different["dataset_sha256"],
                expected_later_statement_sha256=changed["dataset_sha256"],
                expected_later_people_sha256=people["dataset_sha256"],
            )

    def test_bad_windows_are_bounded_and_no_future_original_month(self):
        for window in (
            {"first_month": "2026-00"},
            {"last_month": "2026-11"},
            {"first_month": "2026-10", "last_month": "2026-08"},
            {"first_month": "2000-01", "last_month": "2026-10"},
        ):
            with self.subTest(window=window), self.assertRaises(ValueError):
                self.review(**window)
        self.assertEqual(
            self.review(first_month="2026-08", last_month="2026-10")["periods"][0][
                "month"
            ],
            "2026-10",
        )


if __name__ == "__main__":
    unittest.main()

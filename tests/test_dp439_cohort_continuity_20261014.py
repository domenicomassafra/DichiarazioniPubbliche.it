"""DP-439 release-chain continuity: real public joins, private count-only audit."""

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

from test_dp439_temporal_trends_20261014 import releases  # noqa: E402
from test_dp439_person_topic_v3 import event, fixture, identity, make  # noqa: E402
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3  # noqa: E402
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402


def cohort_releases():
    """August original: visible -> revoked -> explicitly reapproved in a third join."""
    before, after, bundle, people = releases()
    old_a = event(bundle, 0, "topic:economia")
    old_b = event(bundle, 1, "topic:economia")
    old_b_other_topic = event(bundle, 1, "topic:economica")
    new_c = event(bundle, 2, "topic:economia")
    revoke_a = replace(
        old_a,
        status="REVOKED",
        revision=2,
        review_event_id="review:membership:retirement:2",
    )
    restore_a = replace(
        old_a,
        status="APPROVED",
        revision=3,
        review_event_id="review:membership:restore:3",
    )
    restored = make(
        bundle, people, (old_a, old_b, old_b_other_topic, revoke_a, new_c, restore_a)
    )
    return before, after, restored, bundle, people


def entries(*models):
    return [
        {
            "read_model": model,
            "expected_join_sha256": model["dataset_sha256"],
            "expected_statement_sha256": model["source_dataset_sha256"],
            "expected_people_sha256": model["person_dataset_sha256"],
            "as_of": date(2026, 10, 11 + index),
            "snapshot_created_at": f"2026-10-{11 + index:02d}T{14 + index:02d}:30:00+00:00",
        }
        for index, model in enumerate(models)
    ]


class CohortContinuityTests(unittest.TestCase):
    def setUp(self):
        self.before, self.after, self.restored, self.bundle, self.people = (
            cohort_releases()
        )

    def audit(self, *models, **overrides):
        from dichiarazioni_pubbliche.private_person_topic_cohort_v1 import (
            audit_private_person_topic_cohort,
        )

        settings = {
            "releases": entries(*models),
            "allow_offline_review": True,
        }
        settings.update(overrides)
        return audit_private_person_topic_cohort(**settings)

    def test_three_pinned_releases_reappearance_is_manual_hold(self):
        result = self.audit(self.before, self.after, self.restored)
        self.assertEqual(result["status"], "MANUAL_VISIBILITY_RECHECK_REQUIRED")
        self.assertEqual(result["release_count"], 3)
        self.assertEqual(result["transition_count"], 2)
        self.assertEqual(result["reappeared_intersection_count"], 1)
        self.assertEqual(result["reappeared_original_count"], 1)
        self.assertEqual(result["transitions"][0]["removed_intersection_count"], 1)
        self.assertEqual(result["transitions"][1]["reappeared_intersection_count"], 1)
        self.assertEqual(result["transitions"][1]["reappeared_original_count"], 1)
        self.assertEqual(result["last_unique_statement_count"], 3)
        self.assertEqual(
            result["change_time_meaning"],
            "VISIBILITY_DIFFERENCE_BETWEEN_SNAPSHOTS_NOT_EVENT_DATE",
        )
        for key in (
            "publication_authority",
            "rights_authority",
            "absence_of_statements_established",
            "automatic_approval",
        ):
            self.assertIs(result[key], False)
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result, self.audit(self.before, self.after, self.restored))
        material = json.dumps(result)
        for secret in (
            "person:A",
            "topic:economia",
            "statement:",
            "review:membership",
            "Alex Demo",
            "https://",
            "quote_sha256",
            "source_url",
        ):
            self.assertNotIn(secret, material)

    def test_two_releases_match_original_monthly_delta(self):
        result = self.audit(self.before, self.after)
        self.assertEqual(result["status"], "CHANGED")
        self.assertEqual(result["reappeared_intersection_count"], 0)
        self.assertEqual(result["transitions"][0]["added_intersection_count"], 1)
        self.assertEqual(result["transitions"][0]["removed_intersection_count"], 1)
        self.assertEqual(result["transitions"][0]["added_original_count"], 1)
        self.assertEqual(result["transitions"][0]["removed_original_count"], 1)
        self.assertEqual(result["last_record_count"], 3)
        self.assertEqual(result["last_unique_statement_count"], 2)

    def test_no_match_filter_private_id_never_echoes(self):
        result = self.audit(
            self.before,
            self.after,
            self.restored,
            person_id="person:PRIVATE_COHORT_SENTINEL",
        )
        self.assertEqual(result["status"], "NO_MATCH")
        self.assertEqual(result["last_record_count"], 0)
        self.assertNotIn("PRIVATE_COHORT_SENTINEL", repr(result))

    def test_subclass_filter_cannot_hide_revived_intersection_as_no_match(self):
        class DeceptivePersonId(str):
            def __eq__(self, other):
                return False

        normal = self.audit(
            self.before, self.after, self.restored, person_id="person:A"
        )
        self.assertEqual(normal["status"], "MANUAL_VISIBILITY_RECHECK_REQUIRED")
        self.assertGreater(normal["reappeared_intersection_count"], 0)
        for filter_name, filter_value in (
            ("person_id", DeceptivePersonId("person:A")),
            ("topic_id", DeceptivePersonId("topic:economia")),
            ("person_id", 42),
        ):
            with self.subTest(filter_name=filter_name, filter_value=filter_value):
                with self.assertRaisesRegex(ValueError, "COHORT_FILTER_INVALID"):
                    self.audit(
                        self.before,
                        self.after,
                        self.restored,
                        **{filter_name: filter_value},
                    )

    def test_repeated_join_after_different_release_is_replay_not_restore(self):
        with self.assertRaisesRegex(ValueError, "COHORT_RELEASE_REPLAY"):
            self.audit(self.before, self.after, self.before)

    def test_wrong_independent_sha_is_not_repaired_from_payload(self):
        bad = entries(self.before, self.after)
        bad[0]["expected_join_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.audit(self.before, self.after, releases=bad)

    def test_creation_order_and_source_time_are_checked_for_all_releases(self):
        bad = entries(self.before, self.after, self.restored)
        bad[2]["snapshot_created_at"] = "2026-10-11T12:30:00Z"
        with self.assertRaisesRegex(ValueError, "COHORT_CREATION_ORDER_INVALID"):
            self.audit(self.before, self.after, self.restored, releases=bad)
        future = entries(self.before, self.after, self.restored)
        future[2]["as_of"] = date(2026, 10, 10)
        with self.assertRaisesRegex(ValueError, "COHORT_DATE_ORDER_INVALID"):
            self.audit(self.before, self.after, self.restored, releases=future)

    def test_reject_unapproved_number_or_mapping_subclasses_and_oversize(self):
        with self.assertRaisesRegex(ValueError, "COHORT_EXPLICIT_OPT_IN_REQUIRED"):
            self.audit(self.before, self.after, allow_offline_review=1)
        with self.assertRaisesRegex(ValueError, "COHORT_RELEASES_INVALID"):
            self.audit(self.before, releases=entries(self.before))
        with self.assertRaisesRegex(ValueError, "COHORT_RELEASES_INVALID"):
            self.audit(
                self.before, self.after, releases=entries(self.before, self.after) * 7
            )

        class ChangingDescriptor(dict):
            pass

        bad = entries(self.before, self.after)
        bad[1] = ChangingDescriptor(bad[1])
        with self.assertRaisesRegex(ValueError, "COHORT_RELEASE_DESCRIPTOR_INVALID"):
            self.audit(self.before, self.after, releases=bad)

    def test_noncooperative_read_mapping_frozen_before_validation(self):
        class SwitchAfterDigest(dict):
            def __init__(self, source):
                super().__init__(copy.deepcopy(source))
                self.lookups = 0

            def __getitem__(self, key):
                self.lookups += 1
                if self.lookups >= 3 and key == "data":
                    raise AssertionError("A postvalidation live read occurred")
                return super().__getitem__(key)

        bad = entries(self.before, self.after)
        adversarial = SwitchAfterDigest(self.after)
        bad[1]["read_model"] = adversarial
        result = self.audit(self.before, self.after, releases=bad)
        self.assertEqual(result["status"], "CHANGED")
        self.assertEqual(adversarial.lookups, 0)

    def test_source_date_filter_keeps_distinct_originals(self):
        result = self.audit(
            self.before,
            self.after,
            self.restored,
            first_month="2026-09",
            last_month="2026-09",
        )
        self.assertEqual(result["status"], "UNCHANGED")
        self.assertEqual(result["last_record_count"], 2)
        self.assertEqual(result["last_unique_statement_count"], 1)
        self.assertEqual(result["reappeared_original_count"], 0)

    def test_intersection_reappears_but_original_remained_via_other_topic(self):
        a = event(self.bundle, 1, "topic:economia")
        b = event(self.bundle, 1, "topic:economica")
        c = event(self.bundle, 2, "topic:economia")
        both = make(self.bundle, self.people, (a, b))
        one = make(self.bundle, self.people, (a,))
        rejoin = make(self.bundle, self.people, (a, b, c))
        result = self.audit(both, one, rejoin)
        self.assertEqual(result["status"], "MANUAL_VISIBILITY_RECHECK_REQUIRED")
        self.assertEqual(result["reappeared_intersection_count"], 1)
        self.assertEqual(result["reappeared_original_count"], 0)
        self.assertEqual(result["transitions"][-1]["added_original_count"], 1)

    def test_three_release_identity_drift_even_when_middle_release_hides_original(self):
        source, _, _, roster = fixture()
        source.subjects[0].row["statement_date"] = "2026-09-01"
        for gate in source.subjects[0].gates.values():
            gate["statement_date"] = "2026-09-01"
        altered_bundle = source.build()
        altered_bundle["topics"] = copy.deepcopy(self.bundle["topics"])
        altered_bundle["dataset_sha256"] = projection_dataset_sha256(altered_bundle)
        altered_people = build_public_people_v3(
            roster,
            [identity(person) for person in roster],
            [],
            [],
            public_bundle=altered_bundle,
            current_public_dataset_sha256=altered_bundle["dataset_sha256"],
            allow_public_person_v3=True,
        )
        after_gap = make(
            altered_bundle,
            altered_people,
            (event(altered_bundle, 0, "topic:economia"),),
        )
        with self.assertRaisesRegex(ValueError, "COHORT_ORIGINAL_IDENTITY_DRIFT"):
            self.audit(
                self.before,
                self.after,
                after_gap,
                releases=entries(self.before, self.after, after_gap),
                person_id="person:B",
            )

    def test_same_utc_created_instant_cannot_encode_new_release(self):
        pinned = entries(self.before, self.after)
        pinned[1]["snapshot_created_at"] = pinned[0]["snapshot_created_at"]
        with self.assertRaisesRegex(ValueError, "COHORT_CREATION_ORDER_INVALID"):
            self.audit(self.before, self.after, releases=pinned)


if __name__ == "__main__":
    unittest.main()

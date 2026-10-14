"""Synthetic real-Python public v3 Persona×Tema temporal browsing only."""

from __future__ import annotations

import copy
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from test_dp439_person_topic_v3 import published, make  # noqa: E402


class PrivateTemporalExploreTests(unittest.TestCase):
    def setUp(self):
        _, self.bundle, self.people, _, self.decisions = published()
        self.join = make(self.bundle, self.people, self.decisions)

    def view(self, **kwargs):
        from dichiarazioni_pubbliche.private_person_topic_temporal_v1 import (
            prepare_temporal_preview,
        )

        args = dict(
            read_model=self.join,
            expected_join_sha256=self.join["dataset_sha256"],
            expected_statement_sha256=self.bundle["dataset_sha256"],
            expected_people_sha256=self.people["dataset_sha256"],
            as_of=date(2026, 10, 11),
            allow_offline_preview=True,
        )
        args.update(kwargs)
        return prepare_temporal_preview(**args)

    def test_real_public_join_facet_counts_do_not_double_count_statement(self):
        result = self.view()
        self.assertEqual(result["status"], "READY_PRIVATE_PREVIEW")
        self.assertEqual(result["record_count"], 4)
        self.assertEqual(result["unique_statement_count"], 3)
        self.assertEqual(
            result["periods"],
            [
                {
                    "month": "2026-10",
                    "record_count": 4,
                    "unique_statement_count": 3,
                    "public_person_count": 2,
                    "public_topic_count": 2,
                },
            ],
        )
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["rights_authority"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertNotIn("original_text", repr(result))
        self.assertEqual(result, self.view())

    def test_approved_person_topic_intersection_and_empty_unknown_no_echo(self):
        filtered = self.view(person_id="person:A", topic_id="topic:economia")
        self.assertEqual(filtered["record_count"], 2)
        self.assertEqual(filtered["unique_statement_count"], 2)
        self.assertEqual(filtered["periods"][0]["public_person_count"], 1)
        self.assertEqual(filtered["periods"][0]["public_topic_count"], 1)
        unknown = self.view(person_id="PRIVATE_PERSON_SENTINEL")
        self.assertEqual(unknown["status"], "NO_MATCH")
        self.assertEqual(unknown["periods"], [])
        self.assertNotIn("PRIVATE_PERSON_SENTINEL", repr(unknown))

    def test_date_range_months_and_zero_corpus_honesty(self):
        self.assertEqual(
            self.view(first_month="2026-09", last_month="2026-09")["periods"], []
        )
        self.assertEqual(
            self.view(first_month="2026-10", last_month="2026-10")["record_count"], 4
        )
        empty = self.view(topic_id="topic:unpublished")
        self.assertEqual(empty["status"], "NO_MATCH")
        self.assertFalse(empty["absence_of_statements_established"])

    def test_cannot_read_snapshot_from_future_as_a_historical_as_of_view(self):
        # The original opinion dates predate Oct 11, but the validated public
        # join was assembled on Oct 11. No Oct 5 as-of view can use that future
        # snapshot and misleadingly imply historically available coverage.
        with self.assertRaisesRegex(ValueError, "TEMPORAL_SNAPSHOT_IN_FUTURE"):
            self.view(as_of=date(2026, 10, 5))

    def test_revoked_membership_and_private_identifiers_never_inherit_old_pin(self):
        from dataclasses import replace
        from dichiarazioni_pubbliche.public_person_topic_v3 import (
            membership_manifest_sha256,
            build_public_person_topic_v3,
        )

        events = tuple(
            replace(
                d,
                status="REVOKED",
                revision=d.revision + 1,
                membership_id=d.membership_id + ":withdrawn",
            )
            for d in self.decisions
        )
        withdrawn = build_public_person_topic_v3(
            public_bundle=self.bundle,
            public_people=self.people,
            membership_decisions=events,
            current_public_dataset_sha256=self.bundle["dataset_sha256"],
            current_people_dataset_sha256=self.people["dataset_sha256"],
            current_membership_manifest_sha256=membership_manifest_sha256(events),
            now=__import__("datetime").datetime(
                2026, 10, 11, 16, tzinfo=__import__("datetime").timezone.utc
            ),
            coverage_note="Solo opinioni nel corpus pubblico; non esaustivo.",
            allow_person_topic_v3=True,
        )
        self.assertEqual(withdrawn["result_count"], 0)
        with self.assertRaisesRegex(ValueError, "TEMPORAL_PIN_MISMATCH"):
            self.view(read_model=withdrawn)
        current = self.view(
            read_model=withdrawn, expected_join_sha256=withdrawn["dataset_sha256"]
        )
        self.assertEqual(current["status"], "NO_MATCH")
        self.assertEqual(current["record_count"], 0)

    def test_stale_issuer_pins_mutability_and_invalid_months_fail_closed(self):
        mutated = copy.deepcopy(self.join)
        mutated["data"][0]["person_id"] = "PRIVATE_PERSON_SENTINEL"
        with self.assertRaisesRegex(ValueError, "TEMPORAL_STALE_OR_TAMPERED"):
            self.view(read_model=mutated)
        with self.assertRaisesRegex(ValueError, "TEMPORAL_PIN_MISMATCH"):
            self.view(expected_people_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "TEMPORAL_EXPLICIT_OPT_IN"):
            self.view(allow_offline_preview=False)
        for invalid in (
            "2026-00",
            "2026-13",
            "2026-1",
            "2026-10-01",
            "PRIVATE",
            "2026-11",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "TEMPORAL_MONTH_INVALID"):
                    self.view(first_month=invalid)

    def test_noncooperative_read_model_data_swap_after_digest_cannot_inject_private_count(
        self,
    ):
        # Independent reviewer P2: the inherited DP439 filter validates one
        # digest then accesses the caller's mutable `data` again. This fake
        # Mapping swaps in a private-looking row on the fourth read.
        original = copy.deepcopy(self.join)
        forged = copy.deepcopy(original["data"][0])
        forged["person_id"] = "PRIVATE_PERSON_SENTINEL"

        class SwitchAfterDigest(dict):
            reads = 0

            def __getitem__(self, key):
                if key == "data":
                    self.reads += 1
                    if self.reads >= 4:
                        return [forged]
                return super().__getitem__(key)

        attack = SwitchAfterDigest(original)
        result = self.view(read_model=attack, person_id="PRIVATE_PERSON_SENTINEL")
        self.assertEqual(result["status"], "NO_MATCH")
        self.assertEqual(result["record_count"], 0)
        self.assertNotIn("PRIVATE_PERSON_SENTINEL", repr(result))


if __name__ == "__main__":
    unittest.main()

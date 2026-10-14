"""DP-439 opt-in Person × Topic opinion join; synthetic independent review only."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "poc"), str(ROOT / "tests")]

from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3  # noqa: E402
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402
from dichiarazioni_pubbliche.public_person_topic_v3 import (  # noqa: E402
    ReviewedTopicMembership, build_public_person_topic_v3,
    filter_public_person_topic_v3, membership_manifest_sha256,
)
from test_dp437_public_opinion_api import ReviewedSyntheticOpinions  # noqa: E402
from test_dp438_public_person import person, identity  # noqa: E402

NOW = datetime(2026, 10, 11, 14, tzinfo=timezone.utc)


def topic(topic_id: str, slug: str, name: str) -> dict:
    return {
        "topic_id": topic_id, "slug": slug, "canonical_name": name,
        "scope_text": "Raccolta sintetica delimitata", "entity_version": "topic-version:1",
        "review_event_ids": [f"review:topic:{topic_id}"], "memberships": [],
    }


def fixture():
    source = ReviewedSyntheticOpinions()
    # Two people with the same display name but distinct reviewed stable IDs.
    first = person("person:A", slug="persona-a", name="Alex Demo")
    second = person("person:B", slug="persona-b", name="Alex Demo")
    first["disambiguator"] = "Ente A"
    second["disambiguator"] = "Ente B"
    bundle = source.build()
    bundle["topics"] = [
        topic("topic:economia", "economia", "Economia"),
        topic("topic:economica", "economica", "Economia"),
    ]
    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
    people = build_public_people_v3(
        [first, second], [identity(first), identity(second)], [], [],
        public_bundle=bundle, current_public_dataset_sha256=bundle["dataset_sha256"],
        allow_public_person_v3=True,
    )
    return source, bundle, people, [first, second]


def event(bundle: dict, index: int, topic_id: str, *, revision: int = 1,
          status: str = "APPROVED") -> ReviewedTopicMembership:
    record = bundle["statements"][index]
    return ReviewedTopicMembership(
        membership_id=f"membership:{record['statement_id']}:{topic_id}",
        revision=revision, status=status,
        review_event_id=f"review:membership:{record['statement_id']}:{topic_id}:{revision}",
        statement_id=record["statement_id"], version_id=record["version_id"],
        person_id=record["person_id"], topic_id=topic_id,
        topic_entity_version="topic-version:1",
        content_id=record["content_id"], quote_sha256=record["quote_sha256"],
        source_sha256=record["source_sha256"], public_dataset_sha256=bundle["dataset_sha256"],
        reviewed_at="2026-10-11T13:00:00+00:00",
        valid_until="2026-10-12T13:00:00+00:00",
    )


def published(events=None):
    source, bundle, people, roster = fixture()
    decisions = tuple(events if events is not None else (
        event(bundle, 0, "topic:economia"),
        event(bundle, 1, "topic:economia"),
        event(bundle, 1, "topic:economica"),
        event(bundle, 2, "topic:economia"),
    ))
    return source, bundle, people, roster, decisions


def make(bundle, people, decisions, **overrides):
    arguments = {
        "public_bundle": bundle,
        "public_people": people,
        "membership_decisions": decisions,
        "current_public_dataset_sha256": bundle["dataset_sha256"],
        "current_people_dataset_sha256": people["dataset_sha256"],
        "current_membership_manifest_sha256": membership_manifest_sha256(decisions),
        "now": NOW, "allow_person_topic_v3": True,
        "coverage_note": "Solo le opinioni pubbliche raccolte nel corpus autorizzato; copertura non esaustiva.",
    }
    arguments.update(overrides)
    return build_public_person_topic_v3(**arguments)


class PersonTopicV3Tests(unittest.TestCase):
    def test_two_people_two_similar_topics_multiple_approved_memberships_exact_join(self):
        _, bundle, people, _, decisions = published()
        result = make(bundle, people, decisions)
        self.assertEqual(result["result_count"], 4)
        filtered = filter_public_person_topic_v3(
            result, expected_dataset_sha256=result["dataset_sha256"],
            person_id="person:A", topic_id="topic:economia",
        )
        self.assertEqual([r["statement_id"] for r in filtered["data"]], ["statement:2", "statement:1"])
        self.assertEqual([r["statement_date"] for r in filtered["data"]], ["2026-10-02", "2026-10-01"])
        for row in filtered["data"]:
            self.assertEqual(row["person_id"], "person:A")
            self.assertEqual(row["topic_id"], "topic:economia")
            self.assertEqual(row["person_route"], "/persone/persona-a/")
            self.assertEqual(row["topic_route"], "/temi/economia/")
            self.assertEqual(row["statement"]["original"]["wording_type"], "VERBATIM_ORIGINAL")
            self.assertEqual(row["statement"]["person"]["id"], "person:A")
            self.assertIsNone(row["statement"]["finding_id"])
            self.assertEqual(row["statement_route"], f"/dichiarazioni/{row['statement_id'].replace(':', '-')}/")
        cross = filter_public_person_topic_v3(
            result, expected_dataset_sha256=result["dataset_sha256"], topic_id="topic:economica",
        )
        self.assertEqual([r["statement_id"] for r in cross["data"]], ["statement:2"])
        self.assertEqual(cross["data"][0]["topic_route"], "/temi/economica/")
        self.assertEqual(len([r for r in result["data"] if r["statement_id"] == "statement:2"]), 2)
        self.assertNotIn("review:membership", json.dumps(result))
        self.assertNotIn("review_provenance", json.dumps(result))
        self.assertNotIn("raw_transcript", json.dumps(result))
        self.assertEqual(make(bundle, people, tuple(reversed(decisions))), result)

    def test_no_topic_inferred_from_name_source_or_text_and_homonyms_do_not_merge(self):
        _, bundle, people, _, _ = published()
        decisions = (event(bundle, 0, "topic:economia"),)
        result = make(bundle, people, decisions)
        filtered = filter_public_person_topic_v3(
            result, expected_dataset_sha256=result["dataset_sha256"], person_id="person:B",
        )
        self.assertEqual(filtered["data"], [])
        self.assertEqual(filtered["result_count"], 0)
        self.assertNotIn("person:B", json.dumps(filtered))
        self.assertEqual([r["person_id"] for r in result["data"]], ["person:A"])
        self.assertEqual(filter_public_person_topic_v3(
            result, expected_dataset_sha256=result["dataset_sha256"], topic_id="topic:economica",
        )["data"], [])

    def test_revoked_topic_membership_and_source_rights_withdrawal_disappear(self):
        source, bundle, people, roster, decisions = published()
        initial = make(bundle, people, decisions)
        revoked = event(bundle, 0, "topic:economia", revision=2, status="REVOKED")
        after_topic = make(bundle, people, (*decisions, revoked))
        self.assertEqual(after_topic["result_count"], 3)
        self.assertNotIn("statement:1", json.dumps(after_topic))
        self.assertNotEqual(after_topic["dataset_sha256"], initial["dataset_sha256"])
        source.subjects[1].gates["rights"]["status"] = "REVOKED"
        later = source.build()
        later["topics"] = copy.deepcopy(bundle["topics"])
        later["dataset_sha256"] = projection_dataset_sha256(later)
        later_people = build_public_people_v3(
            roster, [identity(row) for row in roster], [], [],
            public_bundle=later, current_public_dataset_sha256=later["dataset_sha256"],
            allow_public_person_v3=True,
        )
        # Stale bundle/current source mismatch fails closed, even when internally valid.
        with self.assertRaises(ValueError):
            make(bundle, people, decisions,
                 current_public_dataset_sha256=later["dataset_sha256"])
        # Exact membership decisions refer to the old release and cannot
        # silently authorize even the surviving original on the new snapshot.
        self.assertEqual(make(later, later_people, decisions)["data"], [])
        self.assertEqual(make(later, later_people, decisions)["result_count"], 0)

    def test_revoked_membership_cannot_be_reissued_under_a_new_lineage_id(self):
        _, bundle, people, _, _ = published()
        approved = event(bundle, 0, "topic:economia")
        revoked = replace(
            event(bundle, 0, "topic:economia", revision=2, status="REVOKED"),
            reviewed_at="2026-10-11T13:10:00+00:00",
        )
        reissued = replace(
            event(bundle, 0, "topic:economia", revision=3),
            membership_id="membership:replacement:statement:1:topic:economia",
            reviewed_at="2026-10-11T13:20:00+00:00",
        )
        self.assertEqual(make(bundle, people, (approved, revoked))["data"], [])
        # A higher revision cannot escape a revocation by changing the
        # supposedly immutable membership identity for the same subject.
        with self.assertRaises(ValueError):
            make(bundle, people, (approved, revoked, reissued))

    def test_revocation_cannot_be_undone_by_backdated_higher_revision(self):
        _, bundle, people, _, _ = published()
        approved = event(bundle, 0, "topic:economia")
        revoked = replace(
            event(bundle, 0, "topic:economia", revision=2, status="REVOKED"),
            reviewed_at="2026-10-11T13:40:00+00:00",
        )
        backdated = replace(
            event(bundle, 0, "topic:economia", revision=3),
            reviewed_at="2026-10-11T13:20:00+00:00",
        )
        self.assertEqual(make(bundle, people, (approved, revoked))["data"], [])
        # The later adjudication is REVOKED in real event time. Sorting solely
        # on revision would mistakenly publish the older APPROVED decision.
        with self.assertRaises(ValueError):
            make(bundle, people, (approved, revoked, backdated))
        reinstated = replace(backdated, reviewed_at="2026-10-11T13:50:00+00:00")
        self.assertEqual(
            [row["statement_id"] for row in make(
                bundle, people, (approved, revoked, reinstated),
            )["data"]],
            ["statement:1"],
        )

    def test_invalid_or_expired_authority_fingerprint_hash_quote_or_person_holds(self):
        _, bundle, people, _, decisions = published()
        cases = [
            {"current_membership_manifest_sha256": "0" * 64},
            {"current_people_dataset_sha256": "0" * 64},
            {"current_public_dataset_sha256": "0" * 64},
            {"allow_person_topic_v3": False},
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                make(bundle, people, decisions, **change)
        for bad in (
            replace(decisions[0], quote_sha256="f" * 64),
            replace(decisions[0], source_sha256="f" * 64),
            replace(decisions[0], person_id="person:B"),
            replace(decisions[0], content_id="content:private"),
            replace(decisions[0], topic_entity_version="topic-version:old"),
            replace(decisions[0], valid_until="2026-10-11T12:59:59+00:00"),
            replace(decisions[0], reviewed_at="2026-10-10T00:00:00+00:00"),
        ):
            with self.subTest(bad=bad):
                result = make(bundle, people, (bad,))
                self.assertEqual(result["data"], [])
        # Reuse of an external review event for two memberships must not
        # count as two independent approvals.
        duplicate_review = replace(decisions[1], review_event_id=decisions[0].review_event_id)
        with self.assertRaises(ValueError):
            make(bundle, people, (decisions[0], duplicate_review))
        for reused in (
            bundle["topics"][0]["review_event_ids"][0],
            next(iter(bundle["statements"][0]["review_provenance"].values())),
        ):
            with self.subTest(reused_independent_review=reused), self.assertRaises(ValueError):
                make(bundle, people, (replace(decisions[0], review_event_id=reused),))
        # A stale same-key revision cannot win against a later HOLD.
        held = event(bundle, 0, "topic:economia", revision=2, status="HELD")
        self.assertEqual(make(bundle, people, (decisions[0], held))["data"], [])
        with self.assertRaises(ValueError):
            make(bundle, people, (decisions[0], decisions[0]))

    def test_private_held_and_unendorsed_are_never_public_counts(self):
        source, bundle, people, _, _ = published()
        source.subjects[0].gates["context"]["endorsed"] = False
        source.subjects[2].gates["context"].update({"speech_act": "REPORTED_QUOTE", "endorsed": False})
        current = source.build()
        current["topics"] = copy.deepcopy(bundle["topics"])
        current["dataset_sha256"] = projection_dataset_sha256(current)
        p1 = person("person:A", slug="persona-a", name="Alex Demo")
        p1["disambiguator"] = "Ente A"
        # person:B is NOT approved in this snapshot.
        current_people = build_public_people_v3(
            [p1], [identity(p1)], [], [],
            public_bundle=current, current_public_dataset_sha256=current["dataset_sha256"],
            allow_public_person_v3=True,
        )
        approvals = (
            event(current, 0, "topic:economia"),
            event(current, 1, "topic:economia"),
            event(current, 2, "topic:economia"),
        )
        result = make(current, current_people, approvals)
        self.assertEqual([item["statement_id"] for item in result["data"]], ["statement:2"])
        self.assertEqual(result["result_count"], 1)
        empty = make(current, current_people, ())
        self.assertEqual(empty["data"], [])
        self.assertEqual(empty["result_count"], 0)
        self.assertEqual(empty["status"], "EMPTY_PUBLIC_INTERSECTION")

    def test_removed_approved_topic_or_identity_rebuilds_without_private_hints(self):
        _, bundle, people, roster, decisions = published()
        initial = make(bundle, people, decisions)
        self.assertEqual(initial["result_count"], 4)
        # The Topic is removed by a new approved projection release. Neither
        # its old ID nor the previously approved text may be replayed.
        current = copy.deepcopy(bundle)
        current["topics"] = [row for row in current["topics"]
                             if row["topic_id"] != "topic:economica"]
        current["dataset_sha256"] = projection_dataset_sha256(current)
        fresh_people = build_public_people_v3(
            roster, [identity(row) for row in roster], [], [],
            public_bundle=current, current_public_dataset_sha256=current["dataset_sha256"],
            allow_public_person_v3=True,
        )
        fresh_decisions = tuple(replace(
            item, public_dataset_sha256=current["dataset_sha256"],
        ) for item in decisions)
        updated = make(current, fresh_people, fresh_decisions)
        self.assertEqual(updated["result_count"], 3)
        self.assertNotIn("topic:economica", json.dumps(updated))
        self.assertNotEqual(updated["dataset_sha256"], initial["dataset_sha256"])
        # With a Person publication revoked upstream, the public Person
        # collection itself omits that identity even if its Statements remain.
        surviving = build_public_people_v3(
            [roster[0]], [identity(roster[0])], [], [],
            public_bundle=current, current_public_dataset_sha256=current["dataset_sha256"],
            allow_public_person_v3=True,
        )
        new = make(current, surviving, fresh_decisions)
        self.assertEqual([r["person_id"] for r in new["data"]], ["person:A", "person:A"])
        self.assertNotIn("person:B", json.dumps(new))

    def test_empty_corpus_is_distinct_from_populated_no_match_and_input_status_tamper(self):
        _, bundle, people, _, decisions = published()
        model = make(bundle, people, decisions)
        wrong = filter_public_person_topic_v3(
            model, expected_dataset_sha256=model["dataset_sha256"],
            person_id="person:A", topic_id="topic:not-published",
        )
        self.assertEqual(wrong["status"], "NO_MATCH")
        self.assertEqual(wrong["result_count"], 0)
        self.assertEqual(wrong["data"], [])
        bad = copy.deepcopy(model)
        bad["status"] = "EMPTY_PUBLIC_CORPUS"
        with self.assertRaises(ValueError):
            filter_public_person_topic_v3(
                bad, expected_dataset_sha256=model["dataset_sha256"])
        with self.assertRaises(ValueError):
            filter_public_person_topic_v3(
                model, expected_dataset_sha256=model["dataset_sha256"],
                topic_id="topic:unsafe/../x",
            )
        source, _, _, roster = fixture()
        for owner in source.subjects:
            owner.gates["publication"]["status"] = "REVOKED"
        empty_bundle = source.build()
        empty_bundle["topics"] = copy.deepcopy(bundle["topics"])
        empty_bundle["dataset_sha256"] = projection_dataset_sha256(empty_bundle)
        empty_people = build_public_people_v3(
            roster, [identity(person) for person in roster], [], [],
            public_bundle=empty_bundle,
            current_public_dataset_sha256=empty_bundle["dataset_sha256"],
            allow_public_person_v3=True,
        )
        empty = make(empty_bundle, empty_people, ())
        self.assertEqual(empty["status"], "EMPTY_PUBLIC_CORPUS")
        self.assertEqual(empty["result_count"], 0)
        self.assertFalse(empty["data"])
        # Two different public empty states must themselves be hash-bound:
        # absence of any public Statement is not the same as an approved
        # public corpus with no independently approved intersection.
        no_match = make(bundle, people, ())
        self.assertEqual(no_match["status"], "EMPTY_PUBLIC_INTERSECTION")
        forged_empty = copy.deepcopy(no_match)
        forged_empty["status"] = "EMPTY_PUBLIC_CORPUS"
        with self.assertRaises(ValueError):
            filter_public_person_topic_v3(
                forged_empty, expected_dataset_sha256=no_match["dataset_sha256"])

    def test_tampered_source_snapshot_and_query_fingerprint_fail_closed(self):
        _, bundle, people, _, decisions = published()
        original = make(bundle, people, decisions)
        changed = copy.deepcopy(bundle)
        changed["statements"][0]["original_text"] = "La mia fonte privata."
        # Even recomputing the projection hash cannot fake quote-hash approval.
        changed["dataset_sha256"] = projection_dataset_sha256(changed)
        with self.assertRaises(ValueError):
            make(changed, people, decisions,
                 current_public_dataset_sha256=changed["dataset_sha256"])
        with self.assertRaises(ValueError):
            filter_public_person_topic_v3(original, expected_dataset_sha256="0" * 64)
        forged = copy.deepcopy(original)
        forged["data"][0]["statement"]["original"]["text"] = "Falso"
        with self.assertRaises(ValueError):
            filter_public_person_topic_v3(
                forged, expected_dataset_sha256=original["dataset_sha256"])
        # Input mutation does not update the previously built deterministic result.
        bundle["statements"][0]["original_text"] = "Privato diverso"
        self.assertNotIn("Privato diverso", json.dumps(original))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.public_api import API_BASE_PATH, dispatch, load_index  # noqa: E402
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_public_bundle,
)
from tests.test_public_projection import FakeSource, valid_row  # noqa: E402


def topic_row(
    *,
    topic_id: str = "topic:health-policy",
    slug: str = "politiche-sanitarie",
    name: str = "Politiche sanitarie",
    claim_id: str = "claim:a",
) -> dict:
    return {
        "topic_id": topic_id,
        "slug": slug,
        "canonical_name": name,
        "scope_text": "Decisioni pubbliche relative all'organizzazione dei servizi sanitari.",
        "entity_version": "knowledge-entity-v1",
        "review_event_ids": [f"review:{topic_id}"],
        "memberships": [
            {
                "membership_id": f"membership:{topic_id}:{claim_id}",
                "claim_id": claim_id,
                "source_resolution_candidate_id": "resolution:private-provenance-id",
                "review_event_ids": [f"review:membership:{topic_id}:{claim_id}"],
            }
        ],
    }


class TopicSource(FakeSource):
    def __init__(self, rows, topics):
        super().__init__(rows)
        self._topics = topics

    def projectable_topics(self):
        return self._topics


class PublicTopicProjectionTests(unittest.TestCase):
    def test_old_public_v2_bundle_without_topics_stays_valid(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        # Builder now emits the additive topic/content collections, but a
        # pre-DP-430/pre-DP-434 bundle without those optional keys remains a
        # valid v2 input with its historical dossiers-only fingerprint.
        payload.pop("topics")
        payload.pop("contents")
        payload["dataset_sha256"] = projection_dataset_sha256(payload)
        self.assertIs(validate_public_bundle(payload), payload)

    def test_reviewed_topic_and_membership_publish_with_projectable_finding(self):
        payload = build_public_projection(
            TopicSource([valid_row()], [topic_row()]),
            generated_at="2026-10-05T12:00:00+00:00",
        )
        self.assertEqual(len(payload["topics"]), 1)
        topic = payload["topics"][0]
        self.assertEqual(topic["topic_id"], "topic:health-policy")
        self.assertEqual(topic["slug"], "politiche-sanitarie")
        self.assertEqual(topic["memberships"][0]["claim_id"], "claim:a")
        self.assertEqual(topic["memberships"][0]["finding_ids"], ["finding:a"])
        self.assertIn("review_event_ids", topic)
        self.assertNotIn("retrieval_score", json.dumps(topic))

    def test_private_nonprojectable_claim_membership_does_not_leak(self):
        topic = topic_row(claim_id="claim:private")
        payload = build_public_projection(TopicSource([valid_row()], [topic]))
        self.assertEqual(len(payload["topics"]), 1)
        self.assertEqual(payload["topics"][0]["memberships"], [])
        text = json.dumps(payload["topics"][0])
        self.assertNotIn("claim:private", text)
        self.assertNotIn("resolution:private-provenance-id", text)

    def test_similar_topic_labels_remain_distinct_by_id_and_slug(self):
        payload = build_public_projection(
            TopicSource(
                [valid_row()],
                [
                    topic_row(topic_id="topic:health", slug="sanita", name="Sanità"),
                    topic_row(
                        topic_id="topic:health-policy",
                        slug="politiche-sanitarie",
                        name="Politiche sanitarie",
                    ),
                ],
            )
        )
        self.assertEqual(
            {(topic["topic_id"], topic["slug"]) for topic in payload["topics"]},
            {
                ("topic:health", "sanita"),
                ("topic:health-policy", "politiche-sanitarie"),
            },
        )

    def test_invalid_topic_fails_closed_without_removing_valid_findings(self):
        malformed = topic_row(slug="NOT A PUBLIC SLUG")
        payload = build_public_projection(TopicSource([valid_row()], [malformed]))
        self.assertEqual(payload["dossier_count"], 1)
        self.assertEqual(payload["topics"], [])

    def test_bundle_rejects_topic_membership_pointing_to_wrong_claim(self):
        payload = build_public_projection(TopicSource([valid_row()], [topic_row()]))
        payload["topics"][0]["memberships"][0]["claim_id"] = "claim:other"
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(payload)


class PublicTopicApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        payload = build_public_projection(TopicSource([valid_row()], [topic_row()]))
        self.path = Path(self.tmp.name) / "index.json"
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_topics_endpoint_is_first_class_resource_not_claim_type_facet(self):
        response = dispatch("GET", f"{API_BASE_PATH}/topics", projection_path=str(self.path))
        self.assertEqual(response.status, 200)
        item = json.loads(response.body)["data"][0]
        self.assertEqual(item["topic_id"], "topic:health-policy")
        self.assertEqual(item["canonical_name"], "Politiche sanitarie")
        self.assertEqual(item["finding_count"], 1)
        self.assertNotIn("topic", item)

    def test_people_distinguish_claim_types_from_subject_topic_ids(self):
        index = load_index(str(self.path))
        person = next(iter(index.people.values()))
        self.assertEqual(person["claim_types"], ["NUMERIC_STATISTIC"])
        self.assertEqual(person["topic_ids"], ["topic:health-policy"])

    def test_claim_type_filter_and_legacy_topic_alias_match(self):
        claim_type = dispatch(
            "GET",
            f"{API_BASE_PATH}/findings?claim_type=NUMERIC_STATISTIC",
            projection_path=str(self.path),
        )
        legacy = dispatch(
            "GET",
            f"{API_BASE_PATH}/findings?topic=NUMERIC_STATISTIC",
            projection_path=str(self.path),
        )
        self.assertEqual(claim_type.status, 200)
        self.assertEqual(legacy.status, 200)
        self.assertEqual(
            json.loads(claim_type.body)["data"],
            json.loads(legacy.body)["data"],
        )


class PublicTopicSchemaMigrationTests(unittest.TestCase):
    def test_schema_and_migration_make_topic_publication_explicitly_reviewed(self):
        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        migration = (
            ROOT / "db" / "migrations" / "20261005-add-public-topic-memberships.sql"
        ).read_text()
        for sql in (schema, migration):
            self.assertIn("claim_topic_membership", sql)
            self.assertIn("'TOPIC'", sql)
            self.assertIn("'CLAIM_TOPIC_MEMBERSHIP'", sql)
            self.assertNotIn("truth_score", sql.lower())
            self.assertNotIn("ideology", sql.lower())

    def test_backup_restore_inventory_contains_topic_membership(self):
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        restore = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py"
        ).read_text()
        self.assertIn("claim_topic_membership", backup)
        self.assertIn('"claim_topic_membership"', restore)


if __name__ == "__main__":
    unittest.main()

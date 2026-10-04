import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.knowledge_repository import (  # noqa: E402
    APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1,
    ENTITY_IDENTIFIER_VERSION,
    ENTITY_RESOLUTION_VERSION,
    EventRecord,
    EntityIdentifierRecord,
    INSERT_ENTITY_IDENTIFIER_SQL_V1,
    INSERT_ENTITY_RESOLUTION_CANDIDATE_SQL_V1,
    INSERT_EVENT_SQL_V1,
    INSERT_TOPIC_SQL_V1,
    KNOWN_ALIAS_LOOKUP_SQL_V1,
    SUPERSEDE_EVENT_SQL_V1,
    SUPERSEDE_TOPIC_SQL_V1,
    TopicRecord,
    make_resolution_candidate,
    normalized_alias,
    propose_alias_matches,
    resolve_exact_identifier,
)


class KnowledgeRepositoryTests(unittest.TestCase):
    def test_alias_normalization_is_unicode_case_and_whitespace_stable(self):
        self.assertEqual(normalized_alias("  Garlasco\tCaso  "), "garlasco caso")
        self.assertEqual(normalized_alias("SEMPIO"), "sempio")

    def test_exact_stable_identifier_is_the_only_auto_link_path(self):
        identifier = EntityIdentifierRecord(
            id="identifier:1",
            entity_type="PERSON",
            entity_id="person:sempio",
            identifier_kind="OFFICIAL_PERSON_ID",
            identifier_value="P-123",
            authority="COURT_RECORD",
            source_ref={"record": "r1"},
        )
        decision = resolve_exact_identifier(
            entity_type="PERSON",
            authority="COURT_RECORD",
            identifier_kind="OFFICIAL_PERSON_ID",
            identifier_value="P-123",
            identifiers=[identifier],
        )
        self.assertEqual(decision.decision, "AUTO_LINK")
        self.assertEqual(decision.entity_id, "person:sempio")
        self.assertEqual(decision.reason, "ACTIVE_EXACT_IDENTIFIER_V1")

    def test_identifier_ambiguity_fails_closed(self):
        rows = [
            EntityIdentifierRecord(
                id=f"identifier:{n}",
                entity_type="PERSON",
                entity_id=f"person:{n}",
                identifier_kind="EXT",
                identifier_value="same",
                authority="TEST",
                source_ref={"n": n},
            )
            for n in (1, 2)
        ]
        decision = resolve_exact_identifier(
            entity_type="PERSON", authority="TEST", identifier_kind="EXT",
            identifier_value="same", identifiers=rows,
        )
        self.assertEqual(decision.decision, "AMBIGUOUS")
        self.assertIsNone(decision.entity_id)

    def test_same_name_different_people_produces_two_candidates_not_merge(self):
        entities = [
            {"entity_type": "PERSON", "entity_id": "person:1", "canonical_name": "Mario Rossi", "aliases": []},
            {"entity_type": "PERSON", "entity_id": "person:2", "canonical_name": "Mario Rossi", "aliases": ["M. Rossi"]},
        ]
        decisions = propose_alias_matches(
            mention_text="Mario Rossi", entity_type="PERSON", entities=entities
        )
        self.assertEqual([d.decision for d in decisions], ["CANDIDATE", "CANDIDATE"])
        self.assertEqual({d.entity_id for d in decisions}, {"person:1", "person:2"})

    def test_alias_match_never_auto_links(self):
        decisions = propose_alias_matches(
            mention_text="M. Rossi",
            entity_type="PERSON",
            entities=[
                {"entity_type": "PERSON", "entity_id": "person:1", "canonical_name": "Mario Rossi", "aliases": ["M. Rossi"]}
            ],
        )
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].decision, "CANDIDATE")
        self.assertEqual(decisions[0].reason, "KNOWN_ALIAS_REQUIRES_REVIEW")

    def test_resolution_candidate_preserves_support_and_contradiction_features(self):
        candidate = make_resolution_candidate(
            content_id="content:1",
            passage_id="passage:1",
            mention_text="Mario Rossi",
            entity_type="PERSON",
            target_id="person:1",
            resolution_method="CONTEXT_MATCH",
            supporting_features=[{"code": "ROLE_MATCH", "value": "avvocato"}],
            contradicting_features=[{"code": "DATE_ROLE_CONFLICT", "value": "2001"}],
            retrieval_score=0.61,
        )
        self.assertEqual(candidate.resolution_version, ENTITY_RESOLUTION_VERSION)
        self.assertEqual(candidate.status, "CANDIDATE")
        self.assertEqual(candidate.supporting_features[0]["code"], "ROLE_MATCH")
        self.assertEqual(candidate.contradicting_features[0]["code"], "DATE_ROLE_CONFLICT")
        self.assertEqual(candidate.target_columns()["target_person_id"], "person:1")

    def test_invalid_model_or_biometric_style_method_is_refused(self):
        with self.assertRaisesRegex(ValueError, "RESOLUTION_METHOD_INVALID"):
            make_resolution_candidate(
                content_id="content:1",
                mention_text="Mario Rossi",
                entity_type="PERSON",
                target_id="person:1",
                resolution_method="FACE_EMBEDDING",
            )

    def test_topic_and_event_supersession_are_lineage_records(self):
        old = TopicRecord(id="topic:old", slug="dna", canonical_name="DNA", scope_text="old")
        new = TopicRecord(
            id="topic:new", slug="dna-v2", canonical_name="DNA forense",
            scope_text="new", supersedes_id=old.id,
        )
        self.assertEqual(new.supersedes_id, "topic:old")
        event = EventRecord(
            id="event:new", slug="garlasco-2007", canonical_name="Omicidio di Garlasco",
            scope_text="evento", supersedes_id="event:old",
        )
        self.assertEqual(event.supersedes_id, "event:old")
        with self.assertRaisesRegex(ValueError, "SELF_SUPERSESSION"):
            TopicRecord(
                id="topic:self", slug="self", canonical_name="Self", scope_text="x",
                supersedes_id="topic:self",
            )

    def test_repository_sql_is_idempotent_and_review_atomic(self):
        for sql in (
            INSERT_TOPIC_SQL_V1, INSERT_EVENT_SQL_V1, INSERT_ENTITY_IDENTIFIER_SQL_V1,
            INSERT_ENTITY_RESOLUTION_CANDIDATE_SQL_V1,
        ):
            self.assertIn("ON CONFLICT", sql)
            self.assertIn("existing AS (", sql)
            self.assertIn("'CONFLICT'", sql)
        self.assertIn("INSERT INTO review_event", APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1)
        self.assertIn("'ENTITY_RESOLUTION_CANDIDATE'", APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1)
        self.assertIn("UPDATE entity_resolution_candidate", APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1)
        self.assertIn("EXISTS (SELECT 1 FROM review_ok)", APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1)

    def test_alias_lookup_covers_all_entity_families(self):
        for token in ("person_alias", "organization_alias", "topic_alias", "event_alias"):
            self.assertIn(token, KNOWN_ALIAS_LOOKUP_SQL_V1)
        self.assertIn("WHERE entity_type=:'entity_type'", KNOWN_ALIAS_LOOKUP_SQL_V1)

    def test_supersede_sql_inserts_new_then_marks_old(self):
        for sql in (SUPERSEDE_TOPIC_SQL_V1, SUPERSEDE_EVENT_SQL_V1):
            self.assertIn("supersedes_id", sql)
            self.assertIn("status='SUPERSEDED'", sql)
            self.assertIn("EXISTS (SELECT 1 FROM inserted)", sql)

    def test_identifier_contract_is_versioned(self):
        row = EntityIdentifierRecord(
            id="identifier:1", entity_type="TOPIC", entity_id="topic:dna",
            identifier_kind="CANONICAL_TOPIC_KEY", identifier_value="dna-forense",
            authority="DICHIARAZIONI_PUBBLICHE", source_ref={"policy": "topic-v1"},
        )
        self.assertEqual(row.identifier_version, ENTITY_IDENTIFIER_VERSION)
        self.assertEqual(row.target_columns()["topic_id"], "topic:dna")


if __name__ == "__main__":
    unittest.main()

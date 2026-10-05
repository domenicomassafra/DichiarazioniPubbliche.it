import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.speaker_runtime import (  # noqa: E402
    PUBLICATION_CAPABLE_ATTRIBUTION_METHODS,
    deterministic_speaker_candidate_id,
    make_speaker_candidate,
    speaker_method_is_publication_capable,
)


class SpeakerRuntimeTests(unittest.TestCase):
    def test_candidate_id_is_deterministic(self):
        kwargs = dict(
            content_id="content:a",
            person_id="person:a",
            start_ms=0,
            end_ms=1000,
            attribution_method="MANUAL_REVIEW",
            source_ref={"source": "review"},
        )
        self.assertEqual(
            deterministic_speaker_candidate_id(**kwargs),
            deterministic_speaker_candidate_id(**kwargs),
        )

    def test_biometric_methods_are_refused(self):
        with self.assertRaises(ValueError):
            make_speaker_candidate(
                content_id="content:a",
                person_id="person:a",
                start_ms=0,
                end_ms=1000,
                attribution_method="VOICEPRINT",
            )

    def test_invalid_interval_is_refused(self):
        with self.assertRaises(ValueError):
            make_speaker_candidate(
                content_id="content:a",
                person_id="person:a",
                start_ms=2000,
                end_ms=1000,
                attribution_method="MANUAL_REVIEW",
            )

    def test_only_strong_reviewed_methods_are_publication_capable(self):
        self.assertEqual(
            PUBLICATION_CAPABLE_ATTRIBUTION_METHODS,
            frozenset({"MANUAL_REVIEW", "TRANSCRIPT_LABEL", "OFFICIAL_RECORD"}),
        )
        for method in ("MANUAL_REVIEW", "TRANSCRIPT_LABEL", "OFFICIAL_RECORD"):
            self.assertTrue(speaker_method_is_publication_capable(method))
        for method in ("SOURCE_METADATA", "PLATFORM_CREDIT", "DIARIZATION_CLUSTER"):
            self.assertFalse(speaker_method_is_publication_capable(method))

    def test_weak_metadata_methods_can_be_candidates_but_not_publication_authority(self):
        for method in ("SOURCE_METADATA", "PLATFORM_CREDIT"):
            candidate = make_speaker_candidate(
                content_id="content:a",
                person_id="person:a",
                start_ms=0,
                end_ms=1000,
                attribution_method=method,
            )
            self.assertEqual(candidate.attribution_method, method)
            self.assertFalse(
                speaker_method_is_publication_capable(candidate.attribution_method)
            )


class PersonRoleSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "db" / "schema.v1.sql").read_text()

    @staticmethod
    def _block(sql, table):
        start = sql.index("CREATE TABLE IF NOT EXISTS " + table)
        end = sql.index(");", start)
        return sql[start:end]

    def test_person_roles_are_scoped_and_rank_free(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("person_id           text NOT NULL REFERENCES person(id)", block)
        self.assertIn("organization_id", block)
        lowered = block.lower()
        for token in ("truth_score", "reliability", "ranking", "fitness"):
            self.assertNotIn(token, lowered)

    def test_public_role_facts_require_provenance(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("source_ref", block)
        self.assertIn("CHECK (is_public_role = false OR source_ref IS NOT NULL)", block)

    def test_role_history_is_correction_lineage_not_person_judgement(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("supersedes_id", block)
        self.assertIn("CHECK (status IN ('ACTIVE', 'SUPERSEDED'))", block)
        self.assertIn("daterange(start_date, end_date, '[)'::text) WITH &&", block)


if __name__ == "__main__":
    unittest.main()

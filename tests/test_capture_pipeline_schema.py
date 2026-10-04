import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CapturePipelineSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-capture-pipeline-events.sql").read_text()

    def test_pipeline_events_are_append_only_lifecycle_events(self):
        for sql in (self.schema, self.migration):
            for event in (
                "CAPTURE_REOBSERVED", "PARSE_SUCCEEDED", "PARSE_FAILED", "BROWSER_FALLBACK_FAILED"
            ):
                self.assertIn(f"'{event}'", sql)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS capture_parser_status", self.schema)

    def test_migration_only_replaces_event_type_constraint(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertIn("drop constraint if exists capture_lifecycle_event_event_type_check", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update content_capture", lowered)
        self.assertNotIn("insert into passage", lowered)

    def test_public_projection_still_has_no_capture_or_private_passage_path(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        for forbidden in ("content_capture", "capture_lifecycle_event", "private_text", "body_ref"):
            self.assertNotIn(forbidden, projection)


if __name__ == "__main__":
    unittest.main()

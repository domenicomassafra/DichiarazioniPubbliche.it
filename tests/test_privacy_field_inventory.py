import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.privacy_field_inventory import (
    FieldInventoryError, LivePrivacyFieldStore, check_inventory, classify_field,
    compare_live_columns, make_inventory, parse_schema_fields,
)
from dichiarazioni_pubbliche import public_schema
from tools.check_privacy_field_inventory import main


class PrivacyFieldInventoryTests(unittest.TestCase):
    def test_canonical_complete_technical_inventory_passes(self):
        status = check_inventory(
            ROOT / "db/schema.v1.sql",
            ROOT / "config/privacy-field-inventory.v1.json",
        )
        self.assertGreaterEqual(status["table_count"], 90)
        self.assertGreaterEqual(status["field_count"], 1100)
        self.assertGreaterEqual(status["public_schema_group_count"], 10)
        self.assertGreaterEqual(status["public_schema_field_count"], 70)
        self.assertEqual(len(status["inventory_sha256"]), 64)

    def test_every_persisted_field_denies_direct_public_projection(self):
        source = make_inventory((ROOT / "db/schema.v1.sql").read_text())
        rows = [value for table in source["fields"].values() for value in table.values()]
        self.assertTrue(rows)
        self.assertTrue(all(row["public_allowlist_decision"] == "DENY_DIRECT_DB_PROJECTION" for row in rows))
        self.assertTrue(all(row["retention_behavior"] == "NO_UNAPPROVED_AUTOMATIC_DELETION" for row in rows))
        self.assertTrue(all(row["access_role"] == "AUTHENTICATED_PRIVATE_OPERATOR" for row in rows))
        self.assertFalse(source["retention_periods_approved"])
        self.assertFalse(source["public_projection_authorized"])
        self.assertEqual(
            source["fields"]["claim_relation_candidate"]["policy_version"]["schema_origin"],
            "20260926_RELATION_POLICY_MIGRATION",
        )
        self.assertEqual(len(source["fields"]["public_schema_contract"]), 7)

    def test_high_risk_and_sensitive_fields_never_classified_public(self):
        self.assertEqual(classify_field("private_reply", "submitter_contact"), "HIGH_RISK_IDENTITY")
        self.assertEqual(classify_field("canonical_transcript_segment", "sensitive_signature"), "SENSITIVE_CANDIDATE")
        self.assertEqual(classify_field("transcript_variant", "raw_text"), "OPERATIONAL_PRIVATE")
        self.assertEqual(classify_field("person", "id"), "PUBLIC_CORE")

    def test_every_public_allowlist_group_is_in_inventory_and_requires_review(self):
        inventory = make_inventory((ROOT / "db/schema.v1.sql").read_text())
        groups = inventory["public_projection_fields"]
        for key, value in vars(public_schema).items():
            if key.endswith("_ALLOWED_KEYS") and isinstance(value, frozenset):
                with self.subTest(group=key):
                    self.assertEqual(set(groups[key]), set(value))
                    self.assertTrue(all(
                        row["public_allowlist_decision"] == "CONDITIONAL_VIA_PUBLIC_SCHEMA_AND_REVIEW"
                        for row in groups[key].values()
                    ))

    def test_schema_change_fails_without_explicit_inventory_update(self):
        source = (ROOT / "db/schema.v1.sql").read_text()
        with tempfile.TemporaryDirectory() as d:
            schema = Path(d) / "schema.sql"
            schema.write_text(source.replace("    canonical_name  text NOT NULL,", "    new_sensitive_data text,\n    canonical_name  text NOT NULL,", 1))
            with self.assertRaisesRegex(FieldInventoryError, "SCHEMA_OR_POLICY_DRIFT"):
                check_inventory(schema, ROOT / "config/privacy-field-inventory.v1.json")

    def test_unrecognized_ddl_never_silently_skipped(self):
        invalid = """CREATE TABLE IF NOT EXISTS test (
    id text PRIMARY KEY,
    secret SOME_NEW_TYPE
);
"""
        with self.assertRaisesRegex(FieldInventoryError, "UNRECOGNIZED_TYPE"):
            parse_schema_fields(invalid)
        with self.assertRaisesRegex(FieldInventoryError, "UNTERMINATED"):
            parse_schema_fields("CREATE TABLE IF NOT EXISTS x (\n    id text PRIMARY KEY,\n")

    def test_live_column_drift_is_explicit_not_silent(self):
        inventory = {"fields": {"person": {"id": {}, "canonical_name": {}}}}
        matching = compare_live_columns(inventory, (("person", "id"), ("person", "canonical_name")))
        self.assertTrue(matching["live_matches_inventory"])
        missing = compare_live_columns(inventory, (("person", "id"), ("person", "new_unreviewed")))
        self.assertEqual(missing["missing_from_live"], 1)
        self.assertEqual(missing["unclassified_live_fields"], 1)
        self.assertFalse(missing["public_projection_authorized"])
        with self.assertRaisesRegex(FieldInventoryError, "DUPLICATE_COLUMN"):
            compare_live_columns(inventory, (("person", "id"), ("person", "id")))

    def test_catalog_query_is_metadata_only_read_only(self):
        class Probe(LivePrivacyFieldStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "person\tid\nperson\tcanonical_name\n"

        store = Probe()
        self.assertEqual(len(store.read_columns()), 2)
        self.assertIn("BEGIN READ ONLY;", store.sql)
        self.assertIn("information_schema.columns", store.sql)
        self.assertNotIn("private_text", store.sql)
        self.assertNotIn("content_item", store.sql)

    def test_cli_default_is_check_only(self):
        self.assertEqual(main([]), 0)


if __name__ == "__main__":
    unittest.main()

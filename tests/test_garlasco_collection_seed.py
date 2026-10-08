import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_collection_seed import (  # noqa: E402
    _SEED_SQL, apply_paused_seed, prepare_seed_variables,
)
from dichiarazioni_pubbliche.garlasco_pilot_inventory import build_live_inventory  # noqa: E402
from tests.test_garlasco_pilot_inventory import FakeReadOnly  # noqa: E402


class GarlascoCollectionSeedTests(unittest.TestCase):
    def setUp(self):
        self.reader = FakeReadOnly()
        self.inventory = build_live_inventory(self.reader)
        self.sha = self.inventory.receipt()["seed_sha256"]

    def test_exact_sha_and_18_unknown_rights_and_source_identity_are_required(self):
        variables = prepare_seed_variables(self.inventory, expected_sha=self.sha)
        rows = json.loads(variables["expected_items"])
        self.assertEqual(len(rows), 18)
        self.assertTrue(all(row["source_id"] == "source:test-news" for row in rows))
        self.assertTrue(all(row["rights_status"] == "UNKNOWN" for row in rows))
        self.assertEqual(len(json.loads(variables["expected_claims"])), 30)
        self.assertEqual(variables["pre_public_findings"], "2")
        self.assertNotIn("PRIVATE", json.dumps(variables))
        with self.assertRaisesRegex(ValueError, "SHA_MISMATCH"):
            prepare_seed_variables(self.inventory, expected_sha="0" * 64)
        with self.assertRaisesRegex(ValueError, "SHA_INVALID"):
            prepare_seed_variables(self.inventory, expected_sha="!bad!")

        self.inventory.summary["captures"] = 1
        with self.assertRaisesRegex(ValueError, "PRECONDITIONS_NOT_MET"):
            prepare_seed_variables(self.inventory, expected_sha=self.sha)

    def test_transaction_sql_only_two_guarded_inserts_and_no_public_mutation(self):
        upper = _SEED_SQL.upper()
        self.assertIn("LOCK TABLE ATOMIC_CLAIM, CONTENT_ITEM IN SHARE MODE NOWAIT", upper)
        self.assertIn("ON CONFLICT (ID) DO NOTHING", upper)
        self.assertIn("ON CONFLICT (COLLECTION_ID,CONTENT_ID) DO NOTHING", upper)
        self.assertIn("STATUS <> 'PAUSED'", upper)
        self.assertIn("CAPTURE_AUTHORIZED", upper)
        self.assertIn("RIGHTS_CLEARANCE", upper)
        self.assertIn("DP214_BASELINE_CONTENT_IDENTITY_OR_RIGHTS_DRIFT", upper)
        self.assertIn("DP214_COLLECTION_AUTHORITY_CONFLICT", upper)
        self.assertIn("DP214_SEED_POSTFLIGHT_MISMATCH", upper)
        self.assertTrue(_SEED_SQL.endswith("COMMIT;"))
        for term in (
            "UPDATE ", "DELETE FROM", "TRUNCATE ", "CREATE TABLE",
            "INSERT INTO CONTENT_ITEM", "INSERT INTO ATOMIC_CLAIM",
            "INSERT INTO FINDING", "INSERT INTO CONTENT_CAPTURE",
            "INSERT INTO PASSAGE", "INSERT INTO RESEARCH_DISCOVERY",
        ):
            self.assertNotIn(term, upper)

    def test_rollback_and_real_apply_have_different_atomic_suffixes(self):
        calls = []
        def fake_exec(args, **opts):
            calls.append((args, opts))
            return SimpleNamespace(
                returncode=0, stderr="", stdout=json.dumps({
                    "collection_id": "research:garlasco",
                    "status": "PAUSED",
                    "linked_historical_content": 18,
                    "baseline_claims": 30,
                    "publication_authority": False,
                    "capture_authorized": False,
                    "pilot_complete": False,
                }),
            )
        with patch("dichiarazioni_pubbliche.garlasco_collection_seed.subprocess.run", side_effect=fake_exec):
            dry = apply_paused_seed(self.reader, expected_sha=self.sha, rollback_test=True)
            self.assertEqual(dry.status, "ROLLBACK_TEST_PASSED")
            result = apply_paused_seed(self.reader, expected_sha=self.sha)
            self.assertEqual(result.status, "PAUSED_PRIVATE_BASELINE_ONLY")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][1]["input"].endswith("ROLLBACK;"))
        self.assertTrue(calls[1][1]["input"].endswith("COMMIT;"))
        self.assertEqual(calls[0][1]["timeout"], 15)
        self.assertIn("ON_ERROR_STOP=1", calls[1][0])
        self.assertEqual(calls[1][1]["env"]["PGCONNECT_TIMEOUT"], "3")
        self.assertNotEqual(dry.status, result.status)

    def test_db_transaction_error_cannot_expose_private_sql_or_credentials(self):
        with patch("dichiarazioni_pubbliche.garlasco_collection_seed.subprocess.run", return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="password=PRIVATE query with names"
        )):
            with self.assertRaisesRegex(RuntimeError, "^DP214_SEED_TRANSACTION_REJECTED$") as ctx:
                apply_paused_seed(self.reader, expected_sha=self.sha)
        self.assertIsNone(ctx.exception.__cause__)
        self.assertNotIn("PRIVATE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues  # noqa: E402


class FakeOperatorQueues(StudioOperatorQueues):
    def __init__(self, rows=(), error=None):
        self.rows = rows
        self.error = error
        self.calls = []

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        if self.error:
            raise self.error
        return "\n".join(json.dumps(row) for row in self.rows)


class StudioQueueTests(unittest.TestCase):
    def test_collections_persisted_states_bounded_pagination(self):
        store = FakeOperatorQueues([{
            "id": "collection:garlasco", "status": "ACTIVE",
            "included_content_count": 30, "name": "SECRET CASE TITLE", "scope_text": "PRIVATE",
        }])
        result = store.list_collections(limit=1)
        self.assertEqual(result["results"], [{
            "id": "collection:garlasco", "state": "ACTIVE",
            "included_content_count": 30,
        }])
        self.assertEqual(result["next_after_id"], "collection:garlasco")
        self.assertFalse(result["publication_authority"])
        sql, variables = store.calls[0]
        self.assertIn("research_collection_content", sql)
        self.assertIn("member.status='INCLUDED'", sql)
        self.assertEqual(variables, {"limit": 1, "after_id": ""})
        self.assertNotIn("SECRET CASE TITLE", json.dumps(result))

    def test_discovery_persisted_provenance_and_reason_only(self):
        store = FakeOperatorQueues([{
            "id": "discovery:hit1", "run_id": "discovery:run1",
            "content_id": "content:1", "disposition": "REJECTED_POLICY",
            "reason_code": "RIGHTS_REVIEW_REQUIRED",
            "canonical_url": "https://private.example/secret",
            "title": "SECRET DATA",
        }])
        result = store.list_discovery(limit=2, after_id="discovery:hit0")
        self.assertEqual(result["results"][0]["reason_code"], "RIGHTS_REVIEW_REQUIRED")
        self.assertEqual(result["results"][0]["run_id"], "discovery:run1")
        self.assertIsNone(result["next_after_id"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertIn("research_discovery_hit", store.calls[0][0])
        self.assertNotIn("canonical_url", store.calls[0][0])

    def test_invalid_limit_cursor_state_duplicates_and_secret_fields_fail_closed(self):
        for kwargs in ({"limit": 0}, {"limit": 31}, {"limit": True}, {"after_id": "x\nSECRET"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FakeOperatorQueues().list_collections(**kwargs)
        with self.assertRaisesRegex(ValueError, "COLLECTION_ROW_INVALID"):
            FakeOperatorQueues([{"id": "collection:1", "status": "DELETED", "included_content_count": 1}]).list_collections()
        with self.assertRaisesRegex(ValueError, "COLLECTION_ROW_INVALID"):
            FakeOperatorQueues([{"id": "collection:1", "status": "ACTIVE", "included_content_count": -1}]).list_collections()
        with self.assertRaisesRegex(ValueError, "STUDIO_DISCOVERY_REASON_INVALID"):
            FakeOperatorQueues([{
                "id": "hit:1", "run_id": "run:1", "disposition": "NEW_CONTENT",
                "reason_code": "<script>SECRET",
            }]).list_discovery()
        with self.assertRaisesRegex(ValueError, "STUDIO_DISCOVERY_ROW_INVALID"):
            FakeOperatorQueues([{
                "id": "hit:1", "run_id": "run:1", "disposition": "APPROVED",
            }]).list_discovery()
        with self.assertRaisesRegex(ValueError, "STUDIO_DISCOVERY_ROW_INVALID"):
            FakeOperatorQueues([{
                "id": "hit:1", "run_id": "run:1", "disposition": "NEW_CONTENT",
            }, {
                "id": "hit:1", "run_id": "run:1", "disposition": "NEW_CONTENT",
            }]).list_discovery()

    def test_db_error_and_oversize_fail_without_raw_db_message(self):
        with self.assertRaisesRegex(RuntimeError, "^STUDIO_COLLECTION_STORE_UNAVAILABLE$") as ctx:
            FakeOperatorQueues(error=OSError("PASSWORD=SECRET")).list_collections()
        self.assertIsNone(ctx.exception.__cause__)
        self.assertNotIn("SECRET", str(ctx.exception))
        with self.assertRaisesRegex(ValueError, "ROWS_INVALID"):
            FakeOperatorQueues([{"id": "one", "status": "ACTIVE"}] * 300).list_collections(limit=30)
        with self.assertRaisesRegex(ValueError, "ROWS_INVALID"):
            FakeOperatorQueues([{"id": "one", "status": "ACTIVE"}] * 300).list_discovery(limit=30)


if __name__ == "__main__":
    unittest.main()

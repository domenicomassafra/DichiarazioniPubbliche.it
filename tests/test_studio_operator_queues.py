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
    def test_members_exact_collection_and_bounded_cursor_no_private_source(self):
        store = FakeOperatorQueues([{
            "collection_id": "research:garlasco", "state": "PAUSED",
            "members": [
                {"content_id": "content:garlasco:001", "source_id": "source:one",
                 "rights_status": "UNKNOWN", "processing_status": "REVIEW_REQUIRED",
                 "title": "SECRET PRIVATE TITLE", "canonical_url": "https://secret.example"},
                {"content_id": "content:garlasco:002", "source_id": "source:two",
                 "rights_status": "UNKNOWN", "processing_status": "REVIEW_REQUIRED"},
            ],
        }])
        result = store.list_collection_members(collection_id="research:garlasco", limit=2)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["state"], "PAUSED")
        self.assertEqual(result["next_after_id"], "content:garlasco:002")
        self.assertEqual(result["results"][0]["source_id"], "source:one")
        self.assertFalse(result["results"][0]["capture_authorized"])
        self.assertFalse(result["publication_authority"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("canonical_url", json.dumps(result))
        sql, variables = store.calls[0]
        self.assertIn("member.status='INCLUDED'", sql)
        self.assertIn("content.id=member.content_id", sql)
        self.assertEqual(variables["collection_id"], "research:garlasco")
        self.assertEqual(variables["limit"], 2)
        for payload in (
            [{"collection_id": "research:other", "state": "PAUSED", "members": []}],
            [{"collection_id": "research:garlasco", "state": "EXPOSED", "members": []}],
            [{"collection_id": "research:garlasco", "state": "PAUSED", "members": [
                {"content_id": "content:garlasco:1", "rights_status": "<private>",
                 "processing_status": "READY"}
            ]}],
            [{"collection_id": "research:garlasco", "state": "PAUSED", "members": [
                {"content_id": "content:garlasco:1", "rights_status": "UNKNOWN",
                 "processing_status": "REVIEW_REQUIRED"},
                {"content_id": "content:garlasco:1", "rights_status": "UNKNOWN",
                 "processing_status": "REVIEW_REQUIRED"},
            ]}],
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                FakeOperatorQueues(payload).list_collection_members(collection_id="research:garlasco")
        with self.assertRaises(ValueError):
            FakeOperatorQueues([]).list_collection_members(collection_id="research:garlasco")
        with self.assertRaises(ValueError):
            FakeOperatorQueues([{"collection_id": "research:garlasco", "state": "PAUSED", "members": []}]).list_collection_members(
                collection_id="research:garlasco", after_id="content:1\nSELECT * FROM private"
            )

    def test_exact_included_member_source_claim_graph_and_fail_closed(self):
        valid = {
            "collection_id": "research:garlasco", "collection_state": "PAUSED",
            "content_id": "content:garlasco:001", "source_id": "source:one",
            "source_exists": True, "rights_status": "UNKNOWN",
            "processing_status": "REVIEW_REQUIRED",
            "capture_count": 0, "passage_count": 0,
            "statement_candidate_count": 0, "claim_candidate_count": 0,
            "atomic_claim_count": 2,
            "claims": [
                {"id": "claim:garlasco:001", "speaker_person_id": "person:one",
                 "claim_type": "HISTORICAL_CLAIM", "normalized_claim": "SECRET"},
                {"id": "claim:garlasco:002", "speaker_person_id": "person:one",
                 "claim_type": "VALUE_JUDGMENT"},
            ],
            "title": "PRIVATE",
        }
        store = FakeOperatorQueues([valid])
        result = store.inspect_collection_member(collection_id="research:garlasco", content_id="content:garlasco:001", limit=2)
        self.assertEqual([x["id"] for x in result["claims"]], ["claim:garlasco:001", "claim:garlasco:002"])
        self.assertEqual(result["source_id"], "source:one")
        self.assertEqual(result["next_after_claim_id"], "claim:garlasco:002")
        self.assertIn("CONTENT_RIGHTS_NOT_APPROVED", result["blockers"])
        self.assertIn("NO_PERSISTED_PASSAGE", result["blockers"])
        self.assertIn("REVIEW_AUTHORITY_NOT_EVALUATED", result["blockers"])
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["capture_authorized"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("normalized_claim", json.dumps(result))
        sql, args = store.calls[0]
        self.assertIn("member.status='INCLUDED'", sql)
        self.assertIn("member.content_id=:'content_id'", sql)
        self.assertIn("claim.content_id=content.id", sql)
        self.assertIn("JOIN research_collection collection", sql)
        self.assertEqual(args["limit"], 2)
        for wrong in (
            valid | {"collection_id": "research:wrong"},
            valid | {"content_id": "content:wrong"},
            valid | {"source_exists": False},
            valid | {"capture_count": -1},
            valid | {"claims": list(reversed(valid["claims"]))},
            valid | {"claims": [valid["claims"][0], valid["claims"][0]]},
            valid | {"claims": [valid["claims"][0] | {"claim_type": "<script>"}]},
        ):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                FakeOperatorQueues([wrong]).inspect_collection_member(
                    collection_id="research:garlasco", content_id="content:garlasco:001"
                )
        with self.assertRaises(ValueError):
            FakeOperatorQueues([]).inspect_collection_member(
                collection_id="research:garlasco", content_id="content:garlasco:001"
            )
        with self.assertRaisesRegex(RuntimeError, "STORE_UNAVAILABLE"):
            FakeOperatorQueues(error=RuntimeError("SECRET PG QUERY")).inspect_collection_member(
                collection_id="research:garlasco", content_id="content:garlasco:001"
            )

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

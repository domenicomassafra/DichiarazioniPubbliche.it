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
    @staticmethod
    def _provenance_row():
        return {
            "collection_id": "research:garlasco", "collection_state": "PAUSED",
            "content_id": "content:garlasco:one", "claim_id": "claim:garlasco:one",
            "speaker_person_id": "person:one", "rights_status": "UNKNOWN",
            "processing_status": "REVIEW_REQUIRED",
            "capture_count": 0, "passage_count": 0, "provenance_count": 1,
            "provenance": [{
                "id": "provenance:1", "claim_id": "claim:garlasco:one",
                "content_id": "content:garlasco:one", "person_id": "person:one",
                "status": "APPROVED", "selector_type": "TEXT_QUOTE_HASH",
                "quote_sha256": "a" * 64, "source_sha256": None,
                "start_char": None, "end_char": None,
                "attribution_method": "SOURCE_QUOTE",
                "source_ref": {"url": "https://secret.example/private"},
                "metadata": {"private_text": "DO NOT EXPOSE"},
            }],
        }

    def test_provenance_exact_claim_binding_and_rights_never_inferred(self):
        store = FakeOperatorQueues([self._provenance_row()])
        data = store.inspect_claim_provenance(
            collection_id="research:garlasco", content_id="content:garlasco:one",
            claim_id="claim:garlasco:one", limit=1,
        )
        self.assertEqual(data["provenance_record_count"], 1)
        self.assertEqual(data["records"][0]["status"], "APPROVED")
        self.assertEqual(data["next_after_id"], "provenance:1")
        self.assertIn("CONTENT_RIGHTS_NOT_APPROVED", data["blockers"])
        self.assertIn("ATTRIBUTION_REVIEW_AUTHORITY_NOT_REEVALUATED", data["blockers"])
        self.assertFalse(data["rights_clearance"])
        self.assertFalse(data["review_authority_evaluated"])
        self.assertFalse(data["publication_authority"])
        self.assertFalse(data["records"][0]["rights_clearance"])
        self.assertNotIn("secret", json.dumps(data).lower())
        self.assertNotIn("source_ref", json.dumps(data))
        sql, variables = store.calls[0]
        self.assertIn("member.status='INCLUDED'", sql)
        self.assertIn("claim.content_id=content.id", sql)
        self.assertIn("provenance.claim_id=claim.id", sql)
        self.assertIn("claim.id=:'claim_id'", sql)
        self.assertNotIn("provenance.source_ref", sql)
        self.assertNotIn("provenance.metadata", sql)
        self.assertEqual(variables["limit"], 1)
        self.assertEqual(variables["after_id"], "")

    def test_provenance_absent_blockers_are_explicit(self):
        row = self._provenance_row() | {"provenance_count": 0, "provenance": []}
        data = FakeOperatorQueues([row]).inspect_claim_provenance(
            collection_id="research:garlasco",
            content_id="content:garlasco:one", claim_id="claim:garlasco:one",
        )
        self.assertIn("CLAIM_TEXT_PROVENANCE_MISSING", data["blockers"])
        self.assertEqual(data["records"], [])
        self.assertIsNone(data["next_after_id"])

    def test_provenance_all_forged_cross_claim_states_and_positions_fail_closed(self):
        base = self._provenance_row()
        cases = [
            base | {"collection_id": "research:other"},
            base | {"content_id": "content:other"},
            base | {"claim_id": "claim:other"},
            base | {"collection_state": "PUBLISHED"},
            base | {"capture_count": -1},
            base | {"provenance_count": 0},
            base | {"provenance": base["provenance"] * 2},
            base | {"provenance": [base["provenance"][0] | {"person_id": "person:wrong"}]},
            base | {"provenance": [base["provenance"][0] | {"claim_id": "claim:wrong"}]},
            base | {"provenance": [base["provenance"][0] | {"content_id": "content:wrong"}]},
            base | {"provenance": [base["provenance"][0] | {"status": "READY_TO_PUBLISH"}]},
            base | {"provenance": [base["provenance"][0] | {"selector_type": "UNVERIFIED"}]},
            base | {"provenance": [base["provenance"][0] | {"quote_sha256": "not-a-hash"}]},
            base | {"provenance": [base["provenance"][0] | {"start_char": 20, "end_char": 10}]},
            base | {"provenance": [base["provenance"][0] | {"start_char": True, "end_char": 20}]},
            base | {"provenance": [base["provenance"][0] | {"selector_type": "TEXT_POSITION_HASH"}]},
            base | {"provenance": [base["provenance"][0] | {"attribution_method": "MODEL_APPROVAL"}]},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                FakeOperatorQueues([case]).inspect_claim_provenance(
                    collection_id="research:garlasco", content_id="content:garlasco:one",
                    claim_id="claim:garlasco:one", limit=1,
                )
        with self.assertRaises(ValueError):
            FakeOperatorQueues([]).inspect_claim_provenance(
                collection_id="research:garlasco", content_id="content:garlasco:one",
                claim_id="claim:garlasco:one",
            )
        with self.assertRaisesRegex(RuntimeError, "STUDIO_PROVENANCE_STORE_UNAVAILABLE") as ctx:
            FakeOperatorQueues(error=RuntimeError("PASSWORD PRIVATE")).inspect_claim_provenance(
                collection_id="research:garlasco", content_id="content:garlasco:one",
                claim_id="claim:garlasco:one",
            )
        self.assertNotIn("PRIVATE", str(ctx.exception))
        with self.assertRaises(ValueError):
            FakeOperatorQueues([base]).inspect_claim_provenance(
                collection_id="research:garlasco", content_id="content:garlasco:one",
                claim_id="claim:garlasco:one", after_id="provenance:1\nSECRET",
            )

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

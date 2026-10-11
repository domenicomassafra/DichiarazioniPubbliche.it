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
    def test_passage_candidate_path_metadata_sanitization_and_cursor_guard(self):
        store = FakeOperatorQueues([{
            "collection_id": "research:pilot", "collection_state": "PAUSED",
            "content_id": "content:one", "source_id": "source:one", "source_exists": True,
            "rights_status": "UNKNOWN", "processing_status": "REVIEW_REQUIRED",
            "capture_id": "capture:aaaaaa", "capture_sha256": "a" * 64,
            "capture_state": "CAPTURED", "capture_hold_state": "NONE",
            "passage_id": "passage:01", "passage_hash": "f" * 64,
            "selector_type": "TEXT_POSITION", "start_char": 2, "end_char": 16,
            "page_start": None, "page_end": None, "cursor_valid": True,
            "candidates": [{
                "id": "statement:one", "content_id": "content:one",
                "status": "CANDIDATE", "speaker_person_id": None,
                "statement_text_hash": "a" * 64,
                "claim_count": 1, "claim_candidates": [{
                    "id": "claimcandidate:one", "content_id": "content:one",
                    "statement_candidate_id": "statement:one", "status": "CANDIDATE",
                    "promoted_claim_id": None, "promotion_id": None,
                    "normalized_claim": "TOP SECRET PRIVATE CLAIM",
                }],
                "normalized_statement": "TOP SECRET PRIVATE STATEMENT",
            }],
            "metadata": {"cookies": "TOP SECRET"},
        }])
        view = store.inspect_collection_passage_candidates(
            collection_id="research:pilot", content_id="content:one",
            capture_id="capture:aaaaaa", passage_id="passage:01", limit=1,
        )
        self.assertEqual(view["source_id"], "source:one")
        self.assertEqual(view["capture_sha256"], "a" * 64)
        self.assertEqual(view["passage"]["id"], "passage:01")
        self.assertEqual(view["passage"]["start_char"], 2)
        self.assertEqual(view["candidates"][0]["id"], "statement:one")
        self.assertEqual(view["candidates"][0]["claim_candidates"][0]["id"], "claimcandidate:one")
        self.assertEqual(view["next_after_statement_id"], "statement:one")
        self.assertIn("CONTENT_RIGHTS_NOT_APPROVED", view["blockers"])
        self.assertFalse(view["rights_clearance"])
        self.assertFalse(view["publication_authority"])
        self.assertNotIn("TOP SECRET", json.dumps(view))
        sql, variables = store.calls[0]
        self.assertIn("member.status='INCLUDED'", sql)
        self.assertIn("passage.capture_id=capture.id", sql)
        self.assertIn("link.content_id=content.id", sql)
        self.assertIn("claim_candidate.statement_candidate_id=selected.id", sql)
        self.assertNotIn("private_text", sql)
        self.assertEqual(variables["limit"], 1)

        bad = dict(store.rows[0], cursor_valid=False, candidates=[])
        with self.assertRaisesRegex(ValueError, "CURSOR_SCOPE_INVALID"):
            FakeOperatorQueues([bad]).inspect_collection_passage_candidates(
                collection_id="research:pilot", content_id="content:one",
                capture_id="capture:aaaaaa", passage_id="passage:01",
                after_statement_id="statement:outside",
            )
        for alteration in (
            {"content_id": "content:other"},
            {"capture_id": "capture:other"},
            {"passage_id": "passage:other"},
            {"capture_sha256": "not-a-hash"},
            {"capture_hold_state": "INVALID_PRIVATE"},
            {"selector_type": "MEDIA_SEGMENT_REF"},
            {"candidates": [dict(store.rows[0]["candidates"][0], content_id="content:other")]},
            {"candidates": [dict(store.rows[0]["candidates"][0], claim_candidates=[
                dict(store.rows[0]["candidates"][0]["claim_candidates"][0], content_id="content:other")])]},
            {"candidates": [dict(store.rows[0]["candidates"][0], claim_candidates=[
                dict(store.rows[0]["candidates"][0]["claim_candidates"][0],
                     status="PROMOTED", promoted_claim_id="claim:unproven")])]},
        ):
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                FakeOperatorQueues([store.rows[0] | alteration]).inspect_collection_passage_candidates(
                    collection_id="research:pilot", content_id="content:one",
                    capture_id="capture:aaaaaa", passage_id="passage:01",
                )
        for limit in (0, True, 31):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                FakeOperatorQueues().inspect_collection_passage_candidates(
                    collection_id="research:pilot", content_id="content:one",
                    capture_id="capture:aaaaaa", passage_id="passage:01", limit=limit,
                )
        with self.assertRaisesRegex(RuntimeError, "^STUDIO_COLLECTION_PASSAGE_STORE_UNAVAILABLE$") as err:
            FakeOperatorQueues(error=OSError("SECRET POSTGRES PASSWORD")).inspect_collection_passage_candidates(
                collection_id="research:pilot", content_id="content:one",
                capture_id="capture:aaaaaa", passage_id="passage:01",
            )
        self.assertNotIn("SECRET", str(err.exception))

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

    def test_collection_navigation_cursors_must_match_persisted_parent(self):
        """A cursor from another collection/content/claim must not silently skip rows."""
        members = {
            "collection_id": "research:garlasco", "state": "PAUSED",
            "members": [], "cursor_valid": False,
        }
        queue = FakeOperatorQueues([members])
        with self.assertRaisesRegex(ValueError, "CURSOR_SCOPE_INVALID"):
            queue.list_collection_members(
                collection_id="research:garlasco", after_id="content:other"
            )
        self.assertIn("anchor.collection_id=collection.id", queue.calls[0][0])
        self.assertIn("anchor.status='INCLUDED'", queue.calls[0][0])
        self.assertIn("anchor.content_id=:'after_id'", queue.calls[0][0])
        good = FakeOperatorQueues([members | {"cursor_valid": True}])
        self.assertEqual(good.list_collection_members(
            collection_id="research:garlasco", after_id="content:included"
        )["results"], [])

        member = {
            "collection_id": "research:garlasco", "collection_state": "PAUSED",
            "content_id": "content:garlasco:001", "source_id": "source:one",
            "source_exists": True, "rights_status": "UNKNOWN",
            "processing_status": "REVIEW_REQUIRED", "capture_count": 0,
            "passage_count": 0, "statement_candidate_count": 0,
            "claim_candidate_count": 0, "atomic_claim_count": 1, "claims": [],
            "claim_cursor_valid": False,
        }
        queue = FakeOperatorQueues([member])
        with self.assertRaisesRegex(ValueError, "CURSOR_SCOPE_INVALID"):
            queue.inspect_collection_member(
                collection_id="research:garlasco", content_id="content:garlasco:001",
                after_claim_id="claim:other-content",
            )
        self.assertIn("anchor.content_id=content.id", queue.calls[0][0])
        self.assertIn("anchor.id=:'after_claim_id'", queue.calls[0][0])
        good = FakeOperatorQueues([member | {"claim_cursor_valid": True}])
        self.assertEqual(good.inspect_collection_member(
            collection_id="research:garlasco", content_id="content:garlasco:001",
            after_claim_id="claim:included",
        )["claims"], [])

        provenance = self._provenance_row() | {
            "provenance": [], "provenance_cursor_valid": False,
        }
        queue = FakeOperatorQueues([provenance])
        with self.assertRaisesRegex(ValueError, "CURSOR_SCOPE_INVALID"):
            queue.inspect_claim_provenance(
                collection_id="research:garlasco", content_id="content:garlasco:one",
                claim_id="claim:garlasco:one", after_id="provenance:another-claim",
            )
        sql = queue.calls[0][0]
        self.assertIn("anchor.claim_id=claim.id", sql)
        self.assertIn("anchor.content_id=content.id", sql)
        self.assertIn("anchor.person_id=claim.speaker_person_id", sql)
        self.assertIn("anchor.id=:'after_id'", sql)
        good = FakeOperatorQueues([provenance | {"provenance_cursor_valid": True}])
        self.assertEqual(good.inspect_claim_provenance(
            collection_id="research:garlasco", content_id="content:garlasco:one",
            claim_id="claim:garlasco:one", after_id="provenance:included",
        )["records"], [])

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


class StudioQueuePersistedCursorTests(unittest.TestCase):
    """Run cursor authority gates against a disposable PostgreSQL corpus."""

    @classmethod
    def setUpClass(cls):
        from tests.test_studio_capture_selectors_pg import StudioCaptureSelectorPostgresTests

        cls.fixture = StudioCaptureSelectorPostgresTests
        cls.fixture.setUpClass()
        try:
            cls.fixture._sql("""
                INSERT INTO research_collection (id, slug, name, scope_text, policy_version, status)
                VALUES ('research:other', 'other-cursor', 'PRIVATE OTHER', 'SECRET', 'v1', 'PAUSED');
                INSERT INTO research_collection_content (
                    collection_id, content_id, inclusion_method, inclusion_version
                ) VALUES ('research:other', 'content:other', 'MANUAL_REVIEW', 'v1');
                INSERT INTO person (id, canonical_name) VALUES ('person:cursor', 'PRIVATE PERSON');
                INSERT INTO atomic_claim (
                    id, content_id, speaker_person_id, normalized_claim, claim_type
                ) VALUES
                    ('claim:cursor-one', 'content:one', 'person:cursor', 'SECRET ONE', 'HISTORICAL_CLAIM'),
                    ('claim:cursor-other', 'content:other', 'person:cursor', 'SECRET OTHER', 'HISTORICAL_CLAIM');
                INSERT INTO claim_text_provenance (
                    id, claim_id, content_id, person_id, selector_type,
                    quote_sha256, attribution_method, status
                ) VALUES
                    ('provenance:cursor-one', 'claim:cursor-one', 'content:one',
                     'person:cursor', 'TEXT_QUOTE_HASH', repeat('a', 64), 'SOURCE_QUOTE', 'CANDIDATE'),
                    ('provenance:cursor-other', 'claim:cursor-other', 'content:other',
                     'person:cursor', 'TEXT_QUOTE_HASH', repeat('b', 64), 'SOURCE_QUOTE', 'CANDIDATE');
            """)
        except Exception:
            cls.fixture.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "fixture"):
            cls.fixture.tearDownClass()

    def test_cross_parent_cursors_and_revoked_membership_fail_closed(self):
        from dichiarazioni_pubbliche.studio_local_api import _StudioQueueReader

        reader = _StudioQueueReader(self.fixture.dsn)
        for request in (
            lambda: reader.list_collection_members(
                collection_id="research:pilot", after_id="content:other", limit=1),
            lambda: reader.inspect_collection_member(
                collection_id="research:pilot", content_id="content:one",
                after_claim_id="claim:cursor-other", limit=1),
            lambda: reader.inspect_claim_provenance(
                collection_id="research:pilot", content_id="content:one",
                claim_id="claim:cursor-one", after_id="provenance:cursor-other", limit=1),
        ):
            with self.subTest(request=request), self.assertRaisesRegex(ValueError, "CURSOR_SCOPE_INVALID"):
                request()

        valid = reader.list_collection_members(
            collection_id="research:pilot", after_id="content:one", limit=1)
        claim_page = reader.inspect_collection_member(
            collection_id="research:pilot", content_id="content:one",
            after_claim_id="claim:cursor-one", limit=1)
        provenance_page = reader.inspect_claim_provenance(
            collection_id="research:pilot", content_id="content:one",
            claim_id="claim:cursor-one", after_id="provenance:cursor-one", limit=1)
        self.assertEqual(valid["results"], [])
        self.assertEqual(claim_page["claims"], [])
        self.assertEqual(provenance_page["records"], [])
        for result in (valid, claim_page, provenance_page):
            self.assertNotIn("SECRET", json.dumps(result))
            self.assertFalse(result["publication_authority"])

        self.fixture._sql("""
            UPDATE research_collection_content SET status='REMOVED'
            WHERE collection_id='research:pilot' AND content_id='content:one';
        """)
        with self.assertRaisesRegex(ValueError, "CURSOR_SCOPE_INVALID"):
            reader.list_collection_members(
                collection_id="research:pilot", after_id="content:one", limit=1)


class StudioQueuePersistedPassageCandidatesTests(unittest.TestCase):
    """Actual schema.v1 PostgreSQL graph: included Collection→Capture→Passage→Candidates."""

    @classmethod
    def setUpClass(cls):
        from tests.test_studio_capture_selectors_pg import StudioCaptureSelectorPostgresTests

        cls.fixture = StudioCaptureSelectorPostgresTests
        cls.fixture.setUpClass()
        try:
            cls.fixture._sql("""
                INSERT INTO statement_candidate (
                    id, content_id, statement_text_hash, normalized_statement, extraction_version
                ) VALUES ('statement:two', 'content:one', repeat('b', 64), 'PRIVATE second', 'v1');
                INSERT INTO statement_candidate_passage (
                    statement_candidate_id, passage_id, content_id
                ) VALUES ('statement:two', 'passage:01', 'content:one');
                INSERT INTO claim_candidate (
                    id, statement_candidate_id, content_id, normalized_claim,
                    proposed_claim_type, extraction_version
                ) VALUES ('claimcandidate:two', 'statement:two', 'content:one',
                          'PRIVATE claim 2', 'HISTORICAL_CLAIM', 'v1');
                INSERT INTO research_collection (id, slug, name, scope_text, policy_version, status)
                VALUES ('research:outside', 'outside-416', 'PRIVATE', 'PRIVATE', 'v1', 'PAUSED');
                INSERT INTO research_collection_content (
                    collection_id, content_id, inclusion_method, inclusion_version
                ) VALUES ('research:outside', 'content:other', 'MANUAL_REVIEW', 'v1');
                INSERT INTO person (id, canonical_name)
                VALUES ('person:dp416', 'PRIVATE PERSON');
                INSERT INTO atomic_claim (
                    id, content_id, speaker_person_id, normalized_claim, claim_type
                ) VALUES ('claim:dp416', 'content:one', 'person:dp416',
                          'PRIVATE PROMOTED CLAIM', 'HISTORICAL_CLAIM');
                UPDATE claim_candidate SET status='PROMOTED', promoted_claim_id='claim:dp416'
                WHERE id='claimcandidate:one';
                INSERT INTO claim_candidate_promotion (
                    id, claim_candidate_id, target_claim_id, action,
                    provenance_channel, idempotency_key, actor_ref
                ) VALUES ('promotion:dp416', 'claimcandidate:one', 'claim:dp416',
                          'CREATED', 'WRITTEN', 'idempotency:dp416-fixture', 'fixture:dp416');
            """)
        except Exception:
            cls.fixture.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "fixture"):
            cls.fixture.tearDownClass()

    def test_private_real_passage_candidate_drilldown_pagination_and_isolation(self):
        from dichiarazioni_pubbliche.studio_local_api import _StudioQueueReader

        reader = _StudioQueueReader(self.fixture.dsn)
        first = reader.inspect_collection_passage_candidates(
            collection_id="research:pilot", content_id="content:one",
            capture_id="capture:aaaaaa", passage_id="passage:01", limit=1,
        )
        self.assertEqual([x["id"] for x in first["candidates"]], ["statement:one"])
        self.assertEqual(first["candidates"][0]["claim_candidates"][0]["id"], "claimcandidate:one")
        self.assertEqual(first["candidates"][0]["claim_candidates"][0]["recorded_promoted_claim_id"],
                         "claim:dp416")
        self.assertEqual(first["candidates"][0]["claim_candidates"][0]["promotion_receipt_id"],
                         "promotion:dp416")
        self.assertFalse(first["candidates"][0]["claim_candidates"][0]["promotion_authority_evaluated"])
        self.assertFalse(first["publication_authority"])
        self.assertTrue(first["next_after_statement_id"])
        second = reader.inspect_collection_passage_candidates(
            collection_id="research:pilot", content_id="content:one",
            capture_id="capture:aaaaaa", passage_id="passage:01", limit=1,
            after_statement_id=first["next_after_statement_id"],
        )
        self.assertEqual([x["id"] for x in second["candidates"]], ["statement:two"])
        self.assertEqual(second["candidates"][0]["claim_candidates"][0]["id"], "claimcandidate:two")
        self.assertIsNotNone(second["next_after_statement_id"])
        last = reader.inspect_collection_passage_candidates(
            collection_id="research:pilot", content_id="content:one",
            capture_id="capture:aaaaaa", passage_id="passage:01", limit=1,
            after_statement_id=second["next_after_statement_id"],
        )
        self.assertEqual(last["candidates"], [])
        self.assertIsNone(last["next_after_statement_id"])
        for output in (first, second, last):
            for forbidden in ("PRIVATE", "SECRET", "normalized_statement", "normalized_claim",
                              "final_url", "body_ref", "metadata", "private_text"):
                self.assertNotIn(forbidden, json.dumps(output))
        try:
            self.fixture._sql("""
                UPDATE content_item SET rights_status='REVOKED'
                WHERE id='content:one';
            """)
            withheld = reader.inspect_collection_passage_candidates(
                collection_id="research:pilot", content_id="content:one",
                capture_id="capture:aaaaaa", passage_id="passage:01",
            )
            self.assertEqual(withheld["rights_status"], "REVOKED")
            self.assertIn("CONTENT_RIGHTS_NOT_APPROVED", withheld["blockers"])
            self.assertFalse(withheld["rights_clearance"])
            self.assertFalse(withheld["publication_authority"])
        finally:
            self.fixture._sql("""
                UPDATE content_item SET rights_status='UNKNOWN'
                WHERE id='content:one';
            """)
        for wrong in (
            {"collection_id": "research:outside"},
            {"content_id": "content:other"},
            {"capture_id": "capture:bbbbbb"},
            {"capture_id": "capture:cccccc"},
            {"passage_id": "passage:03"},
            {"after_statement_id": "statement:foreign"},
        ):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                reader.inspect_collection_passage_candidates(**{
                    "collection_id": "research:pilot", "content_id": "content:one",
                    "capture_id": "capture:aaaaaa", "passage_id": "passage:01",
                    **wrong,
                })
        try:
            self.fixture._sql("""
                UPDATE research_collection_content SET status='REMOVED'
                WHERE collection_id='research:pilot' AND content_id='content:one';
            """)
            with self.assertRaises(ValueError):
                reader.inspect_collection_passage_candidates(
                    collection_id="research:pilot", content_id="content:one",
                    capture_id="capture:aaaaaa", passage_id="passage:01",
                )
        finally:
            self.fixture._sql("""
                UPDATE research_collection_content SET status='INCLUDED'
                WHERE collection_id='research:pilot' AND content_id='content:one';
            """)


if __name__ == "__main__":
    unittest.main()

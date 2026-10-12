"""DP417 candidate inbox: canonical PostgreSQL, not synthetic counters.

No rights grant, reviewer credential, or external provider is used.
"""
from __future__ import annotations

import json
import unittest

from tests.test_dp417_queue_family_next import PersistedCaptureQueueTests
from dichiarazioni_pubbliche.studio_candidate_triage_queue_pg import read_candidate_triage_queue


class CandidateTriageQueuePgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PersistedCaptureQueueTests.setUpClass.__func__(cls)
        cls.store.run("""
            INSERT INTO passage (id,content_id,capture_id,selector_type,start_char,
                                 end_char,text_sha256,private_text,extraction_method,
                                 extraction_version)
            VALUES ('passage:one','content:one','capture:one-new','TEXT_POSITION',
                    0,17,repeat('1',64),'PRIVATE_UNREVIEWED_BODY','TEST','v1'),
                   ('passage:stale','content:one','capture:one-old','TEXT_POSITION',
                    0,17,repeat('2',64),'PRIVATE_STALE_BODY','TEST','v1');
            INSERT INTO statement_candidate (id,content_id,statement_text_hash,
                normalized_statement,extraction_version,status)
            VALUES ('candidate:current','content:one',repeat('3',64),
                    'PRIVATE_CURRENT_WORDS','v1','CANDIDATE'),
                   ('candidate:stale','content:one',repeat('4',64),
                    'PRIVATE_STALE_WORDS','v1','HELD'),
                   ('candidate:unlinked','content:unchanged',repeat('5',64),
                    'PRIVATE_UNLINKED_WORDS','v1','CANDIDATE'),
                   ('candidate:foreign','content:other',repeat('6',64),
                    'PRIVATE_FOREIGN_WORDS','v1','HELD');
            INSERT INTO statement_candidate_passage (statement_candidate_id,passage_id,content_id)
            VALUES ('candidate:current','passage:one','content:one'),
                   ('candidate:stale','passage:stale','content:one');
        """)

    @classmethod
    def tearDownClass(cls):
        PersistedCaptureQueueTests.tearDownClass.__func__(cls)

    def setUp(self):
        PersistedCaptureQueueTests.setUp(self)
        self.store.run("""
            UPDATE research_collection SET status='ACTIVE' WHERE id='collection:one';
            UPDATE content_item SET rights_status='UNKNOWN'
                WHERE id IN ('content:one','content:unchanged');
            UPDATE statement_candidate SET status='CANDIDATE'
                WHERE id='candidate:current';
        """)

    def test_current_stale_and_missing_provenance_visible_without_private_text(self):
        packet = read_candidate_triage_queue(self.store, collection_id="collection:one")
        self.assertTrue(packet["private_only"])
        self.assertFalse(packet["triage_action_authorized"])
        self.assertFalse(packet["publication_authority"])
        self.assertEqual(
            [row["candidate_id"] for row in packet["rows"]],
            ["candidate:current", "candidate:stale", "candidate:unlinked"],
        )
        self.assertEqual(packet["rows"][0]["passage_id"], "passage:one")
        self.assertEqual(packet["rows"][0]["capture_id"], "capture:one-new")
        self.assertIn("CANDIDATE_NEEDS_REVIEW", packet["rows"][0]["blockers"])
        self.assertIn("SOURCE_REFERENCE_MISSING", packet["rows"][0]["blockers"],
                      "a candidate without canonical source cannot be a ready queue item")
        self.assertEqual(packet["rows"][0]["state"], "BLOCKED")
        self.assertIn("PASSAGE_CAPTURE_NOT_LATEST", packet["rows"][1]["blockers"])
        self.assertEqual(packet["rows"][1]["capture_id"], "capture:one-old",
                         "a stale Passage must open its real original Capture, not the latest one")
        self.assertIn("PASSAGE_PROVENANCE_MISSING", packet["rows"][2]["blockers"])
        self.assertEqual(packet["rows"][2]["passage_id"], None)
        for private_value in (
            "PRIVATE_UNREVIEWED_BODY", "PRIVATE_STALE_BODY",
            "PRIVATE_CURRENT_WORDS", "PRIVATE_UNLINKED_WORDS",
        ):
            self.assertNotIn(private_value, json.dumps(packet))
        self.assertNotIn("private.example", json.dumps(packet))

    def test_revocation_during_page_turn_refuses_old_snapshot_and_new_page_is_blocked(self):
        first = read_candidate_triage_queue(self.store, collection_id="collection:one", limit=1)
        self.assertEqual(first["rows"][0]["candidate_id"], "candidate:current")
        self.assertEqual(len(first["snapshot_sha256"]), 64)
        next_cursor = first["next_after_candidate_id"]
        current = read_candidate_triage_queue(
            self.store, collection_id="collection:one", limit=1,
            after_candidate_id=next_cursor, expected_snapshot_sha256=first["snapshot_sha256"],
        )
        self.assertEqual(current["rows"][0]["candidate_id"], "candidate:stale")
        self.store.run("UPDATE content_item SET rights_status='REVOKED' WHERE id='content:one'")
        try:
            with self.assertRaisesRegex(ValueError, "STUDIO_CANDIDATE_QUEUE_SNAPSHOT_STALE"):
                read_candidate_triage_queue(
                    self.store, collection_id="collection:one", limit=1,
                    after_candidate_id=next_cursor,
                    expected_snapshot_sha256=first["snapshot_sha256"],
                )
            newly = read_candidate_triage_queue(self.store, collection_id="collection:one")
            self.assertTrue(all("CONTENT_RIGHTS_REVOKED" in row["blockers"]
                                for row in newly["rows"][:2]))
        finally:
            self.store.run("UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:one'")

    def test_collection_inclusion_and_unpinned_cursor_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "SNAPSHOT"):
            read_candidate_triage_queue(
                self.store, collection_id="collection:one", after_candidate_id="candidate:current",
            )
        with self.assertRaises(ValueError):
            read_candidate_triage_queue(
                self.store, collection_id="collection:other",
                after_candidate_id="candidate:current",
                expected_snapshot_sha256="a"*64,
            )
        self.store.run("""UPDATE research_collection_content SET status='REMOVED'
                          WHERE collection_id='collection:one' AND content_id='content:one'""")
        try:
            packet = read_candidate_triage_queue(self.store, collection_id="collection:one")
            self.assertEqual([r["candidate_id"] for r in packet["rows"]], ["candidate:unlinked"])
        finally:
            self.store.run("""UPDATE research_collection_content SET status='INCLUDED'
                              WHERE collection_id='collection:one' AND content_id='content:one'""")

    def test_current_capture_quarantine_blocks_candidate_even_when_provenance_matches(self):
        self.store.run("UPDATE content_capture SET status='QUARANTINED' WHERE id='capture:one-new'")
        try:
            packet = read_candidate_triage_queue(self.store, collection_id="collection:one")
            candidate = next(r for r in packet["rows"] if r["candidate_id"] == "candidate:current")
            self.assertEqual(candidate["state"], "BLOCKED")
            self.assertIn("CURRENT_CAPTURE_QUARANTINED", candidate["blockers"])
        finally:
            self.store.run("UPDATE content_capture SET status='CAPTURED' WHERE id='capture:one-new'")


if __name__ == "__main__":
    unittest.main()

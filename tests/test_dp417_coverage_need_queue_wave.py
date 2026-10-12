"""DP417: real PostgreSQL Collection Coverage Need triage and stale snapshots."""
from __future__ import annotations

import json
import unittest

from tests.test_dp417_queue_family_next import PersistedCaptureQueueTests
from dichiarazioni_pubbliche.studio_coverage_need_queue_pg import read_coverage_need_queue


class CoverageNeedQueuePgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PersistedCaptureQueueTests.setUpClass.__func__(cls)
        cls.store.run("""
        INSERT INTO content_item(id,canonical_url) VALUES
          ('content:satisfied','https://private.example/satisfied');
        INSERT INTO coverage_need(id,collection_id,need_type,requirement_kind,
          requirement_fingerprint,question,status,attempt_count,max_attempts,
          blocker_code,resolved_at,satisfied_by_content_id)
        VALUES
        ('need:active','collection:one','PRIMARY_SOURCE','ROLE_ANY',repeat('a',64),
         'PRIVATE_SENSITIVE_QUESTION','OPEN',0,2,NULL,NULL,NULL),
        ('need:blocked','collection:one','INDEPENDENT_SOURCE','MIN_INDEPENDENT_LINEAGES',repeat('b',64),
         'PRIVATE_BLOCKED_QUESTION','BLOCKED',2,2,'RIGHTS_HOLD',now(),NULL),
        ('need:searching','collection:one','TEMPORAL_GAP','TEMPORAL_CUTOFF',repeat('c',64),
         'PRIVATE_SEARCHING_QUESTION','SEARCHING',1,2,NULL,NULL,NULL),
        ('need:foreign','collection:other','PRIMARY_SOURCE','ROLE_ANY',repeat('d',64),
         'PRIVATE_FOREIGN_QUESTION','OPEN',0,2,NULL,NULL,NULL),
        ('need:satisfied','collection:one','OTHER','OTHER',repeat('e',64),
         'PRIVATE_SATISFIED_QUESTION','SATISFIED',1,2,NULL,now(),'content:satisfied');
        INSERT INTO coverage_need_event(id,coverage_need_id,event_type,to_status)
        VALUES ('event:open','need:active','CREATED','OPEN');
        """)

    @classmethod
    def tearDownClass(cls):
        PersistedCaptureQueueTests.tearDownClass.__func__(cls)

    def setUp(self):
        PersistedCaptureQueueTests.setUp(self)
        self.store.run("""
          UPDATE research_collection SET status='ACTIVE' WHERE id='collection:one';
          UPDATE coverage_need SET status='OPEN',attempt_count=0,resolved_at=NULL,
            blocker_code=NULL WHERE id='need:active';
        """)

    def test_persisted_open_search_blocked_have_exact_safe_retry_codes(self):
        result = read_coverage_need_queue(self.store, collection_id='collection:one')
        self.assertEqual([r['need_id'] for r in result['rows']],
                         ['need:active','need:blocked','need:searching'])
        self.assertFalse(result['triage_action_authorized'])
        self.assertFalse(result['rights_clearance'])
        self.assertIn('NEED_OPEN', result['rows'][0]['blockers'])
        self.assertIn('SOURCE_RIGHTS_HOLD', result['rows'][1]['blockers'])
        self.assertIn('SEARCH_IN_PROGRESS', result['rows'][2]['blockers'])
        self.assertNotIn('PRIVATE_', json.dumps(result))
        self.assertNotIn('private.example', json.dumps(result))
        self.assertNotIn('question', json.dumps(result))
        self.assertEqual(result['rows'][0]['event_id'], 'event:open')

    def test_event_append_or_status_change_between_pages_fences_snapshot(self):
        first = read_coverage_need_queue(self.store, collection_id='collection:one', limit=1)
        self.assertEqual(first['next_after_need_id'], 'need:active')
        second = read_coverage_need_queue(self.store, collection_id='collection:one', limit=1,
            after_need_id=first['next_after_need_id'],
            expected_snapshot_sha256=first['snapshot_sha256'])
        self.assertEqual(second['rows'][0]['need_id'], 'need:blocked')
        self.store.run("""
          INSERT INTO coverage_need_event(id,coverage_need_id,event_type,from_status,to_status)
          VALUES ('event:late','need:active','OBSERVED_AGAIN','OPEN','OPEN');
        """)
        try:
            with self.assertRaisesRegex(ValueError, 'STUDIO_COVERAGE_NEED_SNAPSHOT_STALE'):
                read_coverage_need_queue(self.store, collection_id='collection:one', limit=1,
                    after_need_id=first['next_after_need_id'],
                    expected_snapshot_sha256=first['snapshot_sha256'])
        finally:
            self.store.run("DELETE FROM coverage_need_event WHERE id='event:late'")

    def test_cursor_cannot_cross_collection_or_be_unpinned(self):
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_REQUIRED'):
            read_coverage_need_queue(self.store,collection_id='collection:one',
                                     after_need_id='need:active')
        with self.assertRaises(ValueError):
            read_coverage_need_queue(self.store, collection_id='collection:other',
                after_need_id='need:active', expected_snapshot_sha256='a'*64)
        with self.assertRaises(ValueError):
            read_coverage_need_queue(self.store, collection_id='collection:one',limit=0)


if __name__ == '__main__':
    unittest.main()

"""DP417: a changed Capture queue cannot silently continue a stale PG page."""
from __future__ import annotations

import unittest

from tests.test_dp417_queue_family_next import PersistedCaptureQueueTests
from dichiarazioni_pubbliche.studio_discovery_triage_reader import read_capture_triage_queue
from dichiarazioni_pubbliche.studio_local_api import _dispatch, StudioLocalReaders


class CaptureQueueSnapshotWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PersistedCaptureQueueTests.setUpClass.__func__(cls)
        cls.store.run("""
            INSERT INTO content_item (id, canonical_url, title, rights_status)
            VALUES ('content:next', 'https://private.example/next', 'SECRET NEXT', 'UNKNOWN');
            INSERT INTO research_collection_content
              (collection_id, content_id, inclusion_method, inclusion_version, status)
            VALUES ('collection:one', 'content:next', 'MANUAL', 'v1', 'INCLUDED');
            INSERT INTO content_capture
              (id, content_id, observed_at, final_url, content_sha256,
               retrieval_method, retrieval_version, status, rights_status)
            VALUES ('capture:next-old','content:next','2026-10-01T09:00:00Z',
                    'https://private.example/next',repeat('7',64),'HTTP','v1','CAPTURED','UNKNOWN'),
                   ('capture:next-new','content:next','2026-10-02T09:00:00Z',
                    'https://private.example/next',repeat('8',64),'HTTP','v1','CAPTURED','UNKNOWN');
        """)

    @classmethod
    def tearDownClass(cls):
        PersistedCaptureQueueTests.tearDownClass.__func__(cls)

    def setUp(self):
        PersistedCaptureQueueTests.setUp(self)
        self.store.run("UPDATE content_capture SET rights_status='UNKNOWN' WHERE id='capture:next-new';")

    def test_real_pg_rights_change_between_pages_refuses_stale_snapshot(self):
        first = read_capture_triage_queue(self.store, collection_id='collection:one', limit=1)
        self.assertEqual([item['capture_id'] for item in first['results']], ['capture:next-new'])
        self.assertRegex(first['snapshot_sha256'], r'^[0-9a-f]{64}$')
        second = read_capture_triage_queue(self.store, collection_id='collection:one', limit=1,
            after_capture_id=first['next_after_capture_id'],
            expected_snapshot_sha256=first['snapshot_sha256'])
        self.assertEqual([row['capture_id'] for row in second['results']], ['capture:one-new'])
        self.assertEqual(second['snapshot_sha256'], first['snapshot_sha256'])
        self.store.run("UPDATE content_capture SET rights_status='REVOKED' WHERE id='capture:one-new';")
        try:
            with self.assertRaisesRegex(ValueError, 'STUDIO_CAPTURE_QUEUE_SNAPSHOT_STALE'):
                read_capture_triage_queue(self.store, collection_id='collection:one', limit=1,
                    after_capture_id=first['next_after_capture_id'],
                    expected_snapshot_sha256=first['snapshot_sha256'])
        finally:
            self.store.run("UPDATE content_capture SET rights_status='UNKNOWN' WHERE id='capture:one-new';")

    def test_real_pg_new_current_capture_invalidates_previous_page(self):
        first = read_capture_triage_queue(self.store, collection_id='collection:one', limit=1)
        self.store.run("""
            INSERT INTO content_capture (id,content_id,observed_at,final_url,content_sha256,
              retrieval_method,retrieval_version,status,rights_status)
            VALUES ('capture:next-replaced','content:next','2026-10-03T09:00:00Z',
              'https://private.example/next', repeat('9',64),'HTTP','v1','CAPTURED','UNKNOWN');
        """)
        try:
            with self.assertRaisesRegex(ValueError, 'STUDIO_CAPTURE_QUEUE_SNAPSHOT_STALE'):
                read_capture_triage_queue(self.store, collection_id='collection:one', limit=1,
                    after_capture_id=first['next_after_capture_id'],
                    expected_snapshot_sha256=first['snapshot_sha256'])
        finally:
            self.store.run("DELETE FROM content_capture WHERE id='capture:next-replaced';")

    def test_real_pg_content_rights_revocation_is_a_blocked_capture_exception(self):
        # This Content has just ONE perfectly healthy Capture. A Content-level
        # revocation must appear in the operator queue even if its Capture row
        # itself never changed status or rights.
        self.store.run("UPDATE content_item SET rights_status='REVOKED' WHERE id='content:unchanged';")
        try:
            page = read_capture_triage_queue(self.store, collection_id='collection:one', limit=10)
            current = next((r for r in page['results'] if r['capture_id']=='capture:unchanged'), None)
            self.assertIsNotNone(current, 'revoked Content hidden by healthy Capture status')
            self.assertEqual(current['state'], 'BLOCKED')
            self.assertIn('CONTENT_RIGHTS_REVOKED', current['blockers'])
        finally:
            self.store.run("UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:unchanged';")

    def test_content_rights_revocation_during_pagination_rejects_stale_page(self):
        first = read_capture_triage_queue(self.store, collection_id='collection:one', limit=1)
        self.store.run("UPDATE content_item SET rights_status='REVOKED' WHERE id='content:one';")
        try:
            with self.assertRaisesRegex(ValueError, 'STUDIO_CAPTURE_QUEUE_SNAPSHOT_STALE'):
                read_capture_triage_queue(self.store, collection_id='collection:one', limit=1,
                    after_capture_id=first['next_after_capture_id'],
                    expected_snapshot_sha256=first['snapshot_sha256'])
        finally:
            self.store.run("UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:one';")

    def test_api_requires_snapshot_for_paginated_query(self):
        class Queues:
            def list_capture_triage_queue(self, **values):
                return values
        readers = StudioLocalReaders(corpus=None,captures=None,candidates=None,queues=Queues())
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT'):
            _dispatch(readers, '/v1/discovery/capture-queue',
                {'collection_id':'collection:one', 'after_capture_id':'capture:next-new'})
        result = _dispatch(readers, '/v1/discovery/capture-queue',
            {'collection_id':'collection:one', 'after_capture_id':'capture:next-new',
             'expected_snapshot_sha256':'a'*64})
        self.assertEqual(result['expected_snapshot_sha256'], 'a'*64)

"""DP-419 source-only Capture -> canonical Segment attestation, real disposable PG.

No source media/provider, URL or rights verification is performed by this fixture.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'poc'))

from tests.test_studio_capture_selectors_pg import StudioCaptureSelectorPostgresTests  # noqa: E402
from dichiarazioni_pubbliche.studio_media_capture_binding_pg import (  # noqa: E402
    PgMediaCaptureBindingStore,
)


class DP419MediaCaptureBindingPgNext(StudioCaptureSelectorPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sql((ROOT / 'db/migrations/031_media_capture_segment_binding.sql').read_text())
        cls._sql((ROOT / 'db/migrations/031_media_capture_segment_binding.sql').read_text())
        cls._sql("UPDATE content_item SET duration_ms=4000 WHERE id='content:one';")

    @classmethod
    def tearDownClass(cls):
        try:
            cls._sql("UPDATE content_item SET duration_ms=NULL WHERE id='content:one';")
        finally:
            super().tearDownClass()

    def setUp(self):
        self.store = PgMediaCaptureBindingStore(self.dsn)
        # Test-admin cleanup in this *disposable* PG only. Operational DML
        # UPDATE/DELETE remain immutable; no production database is touched.
        self._sql("TRUNCATE media_capture_segment_binding_event, "
                  "media_capture_segment_binding;")

    def claim(self, **override):
        args = dict(
            binding_id='media-binding:one',
            event_id='binding-event:one',
            expected_revision=0,
            action='ATTEST',
            content_id='content:one',
            capture_id='capture:aaaaaa',
            capture_sha256='a' * 64,
            canonical_segment_id='canonical:one',
            start_ms=1200,
            end_ms=3400,
            evidence_sha256='e' * 64,
            attestor_ref='local-operator:fixture',
        )
        args.update(override)
        return self.store.record(**args)

    def test_persisted_binding_exact_source_and_replay_after_restart(self):
        first = self.claim()
        self.assertEqual(first['write_result'], 'RECORDED')
        self.assertEqual(first['revision'], 1)
        self.assertEqual(first['binding_state'], 'ATTESTED')
        self.assertEqual(first['capture_id'], 'capture:aaaaaa')
        self.assertEqual(first['capture_sha256'], 'a' * 64)
        self.assertEqual(first['canonical_segment_id'], 'canonical:one')
        self.assertEqual(first['start_ms'], 1200)
        self.assertEqual(first['end_ms'], 3400)
        self.assertFalse(first['seek_authorized'])
        self.assertFalse(first['rights_clearance'])
        self.assertFalse(first['publication_authority'])
        self.assertIn('RIGHTS_NOT_INDEPENDENTLY_APPROVED', first['hold_reasons'])
        self.assertIn('CAPTURE_RETENTION_UNVERIFIED', first['hold_reasons'])
        restarted = PgMediaCaptureBindingStore(self.dsn)
        self.assertEqual(restarted.inspect(binding_id='media-binding:one')['revision'], 1)
        self.assertEqual(self.claim()['write_result'], 'REPLAY')
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding_event"), '1')
        for forbidden in ('SECRET', 'https://', 'body_ref', 'canonical_text',
                          'private_text', 'final_url', 'archive_receipt', 'bearer'):
            self.assertNotIn(forbidden, json.dumps(first))

    @classmethod
    def _sql_text(cls, sql):
        import subprocess
        p = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1','--dbname',cls.dsn],
                           input=sql, text=True, capture_output=True, check=True)
        return p.stdout.strip()

    def test_wrong_exact_ids_sha_time_and_cross_content_rejected(self):
        for wrong in (
            dict(content_id='content:other'),
            dict(capture_id='capture:bbbbbb', capture_sha256='b' * 64),
            dict(capture_id='capture:cccccc', capture_sha256='a' * 64),
            dict(capture_sha256='0' * 64),
            dict(canonical_segment_id='canonical:unknown'),
            dict(start_ms=1201),
            dict(end_ms=3399),
            dict(end_ms=4001),
            dict(evidence_sha256='0'*63+'G'),
            dict(binding_id='bad id!'),
        ):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(
                (ValueError, RuntimeError), r'BINDING_',
            ):
                self.claim(**wrong)
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding"), '0')

    def test_idempotent_event_collision_and_cas_stale(self):
        self.claim()
        with self.assertRaisesRegex(RuntimeError, 'BINDING_REPLAY_CONFLICT'):
            self.claim(evidence_sha256='d'*64)
        with self.assertRaisesRegex(RuntimeError, 'BINDING_CAS_CONFLICT'):
            self.claim(event_id='binding-event:second')
        with self.assertRaisesRegex(RuntimeError, 'BINDING_SUBJECT_CONFLICT'):
            self.claim(binding_id='media-binding:other', event_id='binding-event:other')
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding_event"), '1')

    def test_revocation_append_only_and_replay_not_permission(self):
        self.claim()
        removed = self.claim(action='REVOKE', expected_revision=1, event_id='binding-event:revoke')
        self.assertEqual(removed['revision'], 2)
        self.assertEqual(removed['binding_state'], 'REVOKED')
        self.assertFalse(removed['seek_authorized'])
        self.assertEqual(self.claim(action='REVOKE', expected_revision=1,
                                    event_id='binding-event:revoke')['write_result'], 'REPLAY')
        with self.assertRaisesRegex(RuntimeError, 'BINDING_CAS_CONFLICT|BINDING_REVOKED'):
            self.claim(event_id='binding-event:again',expected_revision=2,action='ATTEST')
        with self.assertRaisesRegex(RuntimeError,'BINDING_IMMUTABLE'):
            self._sql("UPDATE media_capture_segment_binding SET start_ms=999 "
                      "WHERE id='media-binding:one';")
        with self.assertRaisesRegex(RuntimeError,'BINDING_IMMUTABLE'):
            self._sql("DELETE FROM media_capture_segment_binding_event "
                      "WHERE event_id='binding-event:one';")

    def test_hold_event_and_current_capture_source_revocation_recheck(self):
        self.claim()
        hold = self.claim(event_id='binding-event:hold',action='HOLD',expected_revision=1)
        self.assertEqual(hold['binding_state'], 'HELD')
        self.assertIn('BINDING_HELD',hold['hold_reasons'])
        self.assertFalse(hold['seek_authorized'])
        self._sql("UPDATE content_capture SET rights_status='REVOKED',hold_status='RIGHTS_HOLD'"
                  " WHERE id='capture:aaaaaa';")
        try:
            reread=self.store.inspect(binding_id='media-binding:one')
            self.assertIn('CAPTURE_RIGHTS_REVOKED',reread['hold_reasons'])
            self.assertIn('CAPTURE_ON_HOLD',reread['hold_reasons'])
            with self.assertRaisesRegex(RuntimeError,'BINDING_SOURCE_HELD'):
                self.claim(binding_id='media-binding:revoked',event_id='binding-event:revoked')
        finally:
            self._sql("UPDATE content_capture SET rights_status='UNKNOWN',hold_status='NONE'"
                      " WHERE id='capture:aaaaaa';")
        self._sql("UPDATE content_item SET rights_status='REVOKED' WHERE id='content:one';")
        try:
            self.assertIn('CONTENT_RIGHTS_REVOKED',
                          self.store.inspect(binding_id='media-binding:one')['hold_reasons'])
        finally:
            self._sql("UPDATE content_item SET rights_status='UNKNOWN' WHERE id='content:one';")

    def test_current_capture_hash_and_canonical_time_mutations_invalidate(self):
        self.claim()
        self._sql("UPDATE canonical_transcript_segment SET start_ms=1230"
                  " WHERE id='canonical:one';")
        try:
            result=self.store.inspect(binding_id='media-binding:one')
            self.assertIn('SEGMENT_VERSION_CHANGED',result['hold_reasons'])
            with self.assertRaisesRegex(RuntimeError,'BINDING_SOURCE_MISMATCH'):
                self.claim(binding_id='media-binding:changed',event_id='binding-event:changed')
        finally:
            self._sql("UPDATE canonical_transcript_segment SET start_ms=1200"
                      " WHERE id='canonical:one';")
        # Same Segment ID, index and milliseconds but changed canonical words:
        # original attestation must still be considered stale. Digest stays DB-private.
        self._sql("UPDATE canonical_transcript_segment SET canonical_text='SECRET corrected media'"
                  " WHERE id='canonical:one';")
        try:
            result=self.store.inspect(binding_id='media-binding:one')
            self.assertIn('SEGMENT_VERSION_CHANGED',result['hold_reasons'])
            self.assertNotIn('SECRET',json.dumps(result))
        finally:
            self._sql("UPDATE canonical_transcript_segment "
                      "SET canonical_text='SECRET canonical audio transcript' "
                      "WHERE id='canonical:one';")
        self._sql("UPDATE content_capture SET content_sha256=repeat('f',64) "
                  "WHERE id='capture:aaaaaa';")
        try:
            self.assertIn('CAPTURE_VERSION_CHANGED',
                          self.store.inspect(binding_id='media-binding:one')['hold_reasons'])
        finally:
            self._sql("UPDATE content_capture SET content_sha256=repeat('a',64)"
                      " WHERE id='capture:aaaaaa';")

    def test_race_exactly_one_initial_cas_winner(self):
        def attempt(i):
            try:
                return self.claim(event_id=f'binding-event:race:{i}')['write_result']
            except RuntimeError as exc:
                return str(exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            answers=list(pool.map(attempt,range(8)))
        self.assertEqual(answers.count('RECORDED'),1, answers)
        self.assertTrue(all(answer=='RECORDED' or 'BINDING_CAS_CONFLICT' in answer
                            for answer in answers),answers)
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding_event"),'1')

    def test_competing_binding_ids_same_capture_segment_are_serialized(self):
        def attempt(i):
            try:
                return self.claim(binding_id=f'media-binding:distinct:{i}',
                                  event_id=f'binding-event:distinct:{i}')['write_result']
            except RuntimeError as exc:
                return str(exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            responses=list(pool.map(attempt,range(5)))
        self.assertEqual(responses.count('RECORDED'), 1, responses)
        self.assertEqual(responses.count('BINDING_SUBJECT_CONFLICT'), 4, responses)
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding"), '1')

    def test_raw_sql_insert_cannot_bypass_exact_capture_sha_or_segment_range(self):
        # Composite FKs by themselves are insufficient: BEFORE INSERT must
        # defend canonical source-version and interval even on direct SQL.
        for capture_hash,start_ms,expected in (
            ('f'*64,1200,'BINDING_SOURCE_MISMATCH'),
            ('a'*64,1201,'BINDING_SOURCE_MISMATCH'),
        ):
            sql = f"""
                INSERT INTO media_capture_segment_binding
                  (id,content_id,capture_id,capture_sha256,canonical_segment_id,
                   segment_index,start_ms,end_ms,evidence_sha256,attestor_ref)
                VALUES ('media-binding:direct','content:one','capture:aaaaaa',
                  '{capture_hash}','canonical:one',2,{start_ms},3400,
                  repeat('e',64),'local-operator:fixture');"""
            with self.subTest(capture_hash=capture_hash,start_ms=start_ms), self.assertRaisesRegex(
                RuntimeError, expected,
            ):
                self._sql(sql)
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding"),'0')

    def test_raw_event_insert_cannot_skip_cas_revision_or_resurrect_revoke(self):
        self.claim()
        with self.assertRaisesRegex(RuntimeError, 'BINDING_CAS_CONFLICT'):
            self._sql("""INSERT INTO media_capture_segment_binding_event
                (event_id,binding_id,revision,event_kind,request_sha256)
                VALUES('binding-event:skip','media-binding:one',3,'HOLD',repeat('f',64));""")
        self.claim(event_id='binding-event:revoke',action='REVOKE',expected_revision=1)
        with self.assertRaisesRegex(RuntimeError,'BINDING_CAS_CONFLICT'):
            self._sql("""INSERT INTO media_capture_segment_binding_event
                (event_id,binding_id,revision,event_kind,request_sha256)
                VALUES('binding-event:resurrect','media-binding:one',3,'ATTEST',repeat('f',64));""")
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding_event"),'2')

    def test_transaction_rollback_leaves_no_binding_or_event(self):
        result=self.store.record_in_transaction(
            operation=self.claim_args_for_rollback(),
            force_rollback=True,
        )
        self.assertEqual(result['write_result'],'RECORDED')
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding"),'0')
        self.assertEqual(self._sql_text("SELECT count(*) FROM media_capture_segment_binding_event"),'0')

    def claim_args_for_rollback(self):
        return dict(binding_id='media-binding:one',event_id='binding-event:one',
                    expected_revision=0,action='ATTEST',content_id='content:one',
                    capture_id='capture:aaaaaa',capture_sha256='a'*64,
                    canonical_segment_id='canonical:one',start_ms=1200,end_ms=3400,
                    evidence_sha256='e'*64,attestor_ref='local-operator:fixture')


if __name__ == '__main__':
    unittest.main()

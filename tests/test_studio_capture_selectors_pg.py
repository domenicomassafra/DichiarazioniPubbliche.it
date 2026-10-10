"""DP-419: real isolated PostgreSQL source-bound private selector read."""

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'poc'))

from dichiarazioni_pubbliche.studio_capture_inspector import inspect_capture_passage_selectors  # noqa: E402
from dichiarazioni_pubbliche.studio_media_selector import inspect_candidate_media_selector  # noqa: E402
from dichiarazioni_pubbliche.studio_local_api import _StudioCaptureReader  # noqa: E402


class StudioCaptureSelectorPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'psql')}
        if any(value is None for value in required.values()):
            raise unittest.SkipTest('isolated PostgreSQL binaries unavailable')
        cls.tmp = tempfile.TemporaryDirectory(prefix='dp419-pg-')
        cls.root = Path(cls.tmp.name)
        cls.data = cls.root / 'data'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.started = False
        try:
            cls._run(['initdb', '-D', str(cls.data), '--username=postgres',
                      '--auth=trust', '--no-locale', '--encoding=UTF8'])
            cls._run(['pg_ctl', '-D', str(cls.data), '-l', str(cls.root / 'postgres.log'),
                      '-o', f'-F -p {cls.port} -h 127.0.0.1 -k {cls.root}', '-w', 'start'])
            cls.started = True
            cls.dsn = f'postgresql://postgres@127.0.0.1:{cls.port}/postgres'
            cls._sql((ROOT / 'db' / 'schema.v1.sql').read_text())
            cls._sql('''
              INSERT INTO content_item (id, canonical_url) VALUES
                ('content:one', 'https://source.test/one'),
                ('content:other', 'https://source.test/other');
              INSERT INTO content_capture (
                id, content_id, observed_at, final_url, content_sha256,
                retrieval_method, retrieval_version, body_ref, metadata
              ) VALUES (
                'capture:aaaaaa', 'content:one', '2026-10-08T09:00:00Z',
                'https://source.test/one', repeat('a', 64), 'fixture', 'v1',
                '/private/SECRET-body', '{"private_auth": "SECRET"}'::jsonb
              ), (
                'capture:bbbbbb', 'content:other', '2026-10-08T09:00:00Z',
                'https://source.test/other', repeat('b', 64), 'fixture', 'v1',
                NULL, '{}'::jsonb
              );
              INSERT INTO passage (
                id, content_id, capture_id, selector_type, start_char, end_char,
                text_sha256, private_text, extraction_method, extraction_version,
                metadata
              ) VALUES
                ('passage:01', 'content:one', 'capture:aaaaaa', 'TEXT_POSITION',
                 2, 16, repeat('f', 64), 'SECRET first passage', 'fixture', 'v1',
                 '{"cookie": "SECRET"}'::jsonb),
                ('passage:02', 'content:one', 'capture:aaaaaa', 'TEXT_POSITION',
                 20, 30, repeat('e', 64), 'SECRET second passage', 'fixture', 'v1',
                 '{}'::jsonb),
                ('passage:03', 'content:other', 'capture:bbbbbb', 'TEXT_POSITION',
                 0, 9, repeat('d', 64), 'SECRET other content', 'fixture', 'v1',
                 '{}'::jsonb);
              INSERT INTO canonical_transcript_segment (
                id, content_id, segment_index, start_ms, end_ms,
                canonical_text, transcript_status, publication_blocked
              ) VALUES (
                'canonical:one', 'content:one', 2, 1200, 3400,
                'SECRET canonical audio transcript', 'RESOLVED', false
              );
              INSERT INTO passage (
                id, content_id, canonical_segment_id, selector_type,
                text_sha256, private_text, extraction_method, extraction_version
              ) VALUES (
                'passage:media', 'content:one', 'canonical:one',
                'MEDIA_SEGMENT_REF', repeat('c', 64),
                'SECRET audio passage', 'fixture', 'v1'
              );
              INSERT INTO statement_candidate (
                id, content_id, statement_text_hash, normalized_statement,
                extraction_version
              ) VALUES (
                'statement:one', 'content:one', repeat('a', 64),
                'SECRET statement', 'fixture-v1'
              );
              INSERT INTO statement_candidate_passage (
                  statement_candidate_id, passage_id, content_id
              ) VALUES ('statement:one', 'passage:media', 'content:one');
              INSERT INTO statement_candidate_passage (
                  statement_candidate_id, passage_id, content_id
              ) VALUES ('statement:one', 'passage:01', 'content:one');
              INSERT INTO claim_candidate (
                  id, statement_candidate_id, content_id, normalized_claim,
                  proposed_claim_type, extraction_version
              ) VALUES ('claimcandidate:one', 'statement:one', 'content:one',
                        'SECRET unreviewed claim', 'HISTORICAL_CLAIM', 'fixture-v1');
              INSERT INTO source (id, canonical_name, source_type, canonical_url)
              VALUES ('source:one', 'SECRET original', 'NEWS', 'https://secret.example/source');
              UPDATE content_item SET source_id='source:one' WHERE id='content:one';
              INSERT INTO research_collection (id, slug, name, scope_text, policy_version, status)
              VALUES ('research:pilot', 'pilot', 'SECRET case name', 'SECRET scope', 'v1', 'PAUSED');
              INSERT INTO research_collection_content (
                  collection_id, content_id, inclusion_method, inclusion_version
              ) VALUES ('research:pilot', 'content:one', 'MANUAL_REVIEW', 'v1');
              INSERT INTO content_capture (
                  id, content_id, observed_at, final_url, content_sha256,
                  retrieval_method, retrieval_version
              ) VALUES ('capture:cccccc', 'content:one', '2026-10-09T10:00:00Z',
                        'https://SECRET.example/other', repeat('c', 64), 'fixture', 'v1');
            ''')
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def _run(cls, args, *, input_text=None):
        proc = subprocess.run(args, input=input_text, text=True, capture_output=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr[:1000])

    @classmethod
    def _sql(cls, sql):
        cls._run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                  '--dbname', cls.dsn], input_text=sql)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'started', False):
            cls._run(['pg_ctl', '-D', str(cls.data), '-m', 'fast', '-w', 'stop'])
            cls.started = False
        if hasattr(cls, 'tmp'):
            cls.tmp.cleanup()

    def test_exact_capture_hash_sql_page_and_private_material_exclusion(self):
        store = _StudioCaptureReader(self.dsn)
        first = inspect_capture_passage_selectors(
            store, content_id='content:one', capture_hash='a' * 64, limit=1)
        self.assertEqual([row['id'] for row in first['selectors']], ['passage:01'])
        self.assertTrue(first['has_more'])
        second = inspect_capture_passage_selectors(
            store, content_id='content:one', capture_hash='a' * 64,
            limit=1, after_id=first['next_after_id'])
        self.assertEqual([row['id'] for row in second['selectors']], ['passage:02'])
        self.assertFalse(second['has_more'])
        self.assertEqual(second['selectors'][0]['start_char'], 20)
        self.assertFalse(second['rights_clearance'])
        for forbidden in ('SECRET', 'private_text', 'cookie', 'body_ref', 'final_url'):
            self.assertNotIn(forbidden, json.dumps((first, second)))
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_CAPTURE_VERSION_MISSING'):
            inspect_capture_passage_selectors(
                store, content_id='content:one', capture_hash='b' * 64)
        self.assertEqual(store.list_passage_selectors('capture:bbbbbb',
            limit=20, after_id=None)[0]['content_id'], 'content:other')

    def test_persisted_candidate_media_passage_maps_to_exact_segment_time(self):
        store = _StudioCaptureReader(self.dsn)
        actual = inspect_candidate_media_selector(
            store, content_id='content:one', statement_candidate_id='statement:one',
            passage_id='passage:media')
        self.assertEqual(actual['canonical_segment']['id'], 'canonical:one')
        self.assertEqual(actual['canonical_segment']['segment_index'], 2)
        self.assertEqual((actual['canonical_segment']['start_ms'],
                          actual['canonical_segment']['end_ms']), (1200, 3400))
        self.assertFalse(actual['rights_clearance'])
        self.assertFalse(actual['attribution_authority'])
        self.assertFalse(actual['publication_authority'])
        for secret in ('SECRET', 'canonical_text', 'normalized_statement',
                       'private_text', 'speaker_person_id'):
            self.assertNotIn(secret, json.dumps(actual))
        for changes in (
            {'content_id': 'content:other'},
            {'statement_candidate_id': 'statement:missing'},
            {'passage_id': 'passage:01'},
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(
                RuntimeError, 'STUDIO_MEDIA_LINK_MISSING',
            ):
                inspect_candidate_media_selector(store, **({
                    'content_id': 'content:one',
                    'statement_candidate_id': 'statement:one',
                    'passage_id': 'passage:media',
                } | changes))

    def test_persisted_collection_source_capture_passage_candidate_claim_chain(self):
        """Actual SQL under disposable PostgreSQL; no fixture HTML data masking joins."""
        store = _StudioCaptureReader(self.dsn)
        page1 = store.list_collection_captures(
            collection_id='research:pilot', content_id='content:one', limit=1)
        self.assertEqual(page1['source_id'], 'source:one')
        self.assertEqual([x['id'] for x in page1['captures']], ['capture:aaaaaa'])
        self.assertEqual(page1['captures'][0]['content_sha256'], 'a' * 64)
        self.assertTrue(page1['has_more'])
        page2 = store.list_collection_captures(
            collection_id='research:pilot', content_id='content:one', limit=1,
            after_id=page1['next_after_id'])
        self.assertEqual([x['id'] for x in page2['captures']], ['capture:cccccc'])
        self.assertFalse(page2['has_more'])
        self.assertFalse(page2['rights_clearance'])
        selector = inspect_capture_passage_selectors(
            store, content_id='content:one', capture_hash=page1['captures'][0]['content_sha256'])
        self.assertEqual(selector['selectors'][0]['id'], 'passage:01')
        linked = store.list_collection_passage_candidates(
            collection_id='research:pilot', content_id='content:one', passage_id='passage:01')
        self.assertEqual(linked['source_id'], 'source:one')
        self.assertEqual(linked['candidates'][0]['statement_candidate_id'], 'statement:one')
        self.assertEqual(linked['candidates'][0]['claim_candidates'][0]['id'], 'claimcandidate:one')
        self.assertIsNone(linked['candidates'][0]['claim_candidates'][0]['promoted_claim_id'])
        self.assertFalse(linked['rights_clearance'])
        media = store.list_collection_passage_candidates(
            collection_id='research:pilot', content_id='content:one', passage_id='passage:media')
        self.assertEqual(media['selector_type'], 'MEDIA_SEGMENT_REF')
        for obj in (page1, page2, linked, media):
            for forbidden in ('SECRET', 'private_text', 'normalized_claim',
                              'canonical_url', 'scope_text', 'final_url', 'body_ref'):
                self.assertNotIn(forbidden, json.dumps(obj))
        with self.assertRaisesRegex(ValueError, 'STUDIO_CAPTURE_COLLECTION_MEMBER_NOT_FOUND'):
            store.list_collection_captures(collection_id='research:pilot', content_id='content:other')
        with self.assertRaisesRegex(ValueError, 'STUDIO_PASSAGE_NOT_IN_INCLUDED_COLLECTION'):
            store.list_collection_passage_candidates(collection_id='research:pilot',
                content_id='content:one', passage_id='passage:03')
        with self.assertRaisesRegex(ValueError, 'STUDIO_PASSAGE_NOT_IN_INCLUDED_COLLECTION'):
            store.list_collection_passage_candidates(collection_id='research:pilot',
                content_id='content:other', passage_id='passage:03')


if __name__ == '__main__':
    unittest.main()

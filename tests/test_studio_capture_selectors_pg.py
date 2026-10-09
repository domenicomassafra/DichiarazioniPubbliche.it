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


if __name__ == '__main__':
    unittest.main()

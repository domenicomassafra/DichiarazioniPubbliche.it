"""DP-237: authenticated Studio source jump on disposable real PostgreSQL."""

import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore
from dichiarazioni_pubbliche.source_watcher import FetchedBytes
from dichiarazioni_pubbliche.studio_exact_source_jump import read_studio_exact_source_jump
from dichiarazioni_pubbliche.studio_local_api import (
    StudioLocalReaders, _StudioCaptureReader,
)
from tests.test_dp237_studio_exact_source_jump import TEXT, SHA, QUOTE, URL

ROOT = Path(__file__).resolve().parents[1]


class ExactJumpPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if any(shutil.which(name) is None for name in ("psql", "initdb", "pg_ctl")):
            raise unittest.SkipTest("disposable PostgreSQL tools unavailable")
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp237-studio-pg-")
        cls.root = Path(cls.tmp.name)
        cls.data = cls.root / "db"
        cls.started = False
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.dsn = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        try:
            cls.command(["initdb", "-D", str(cls.data), "--username=postgres",
                         "--auth=trust", "--no-locale", "--encoding=UTF8"])
            cls.command(["pg_ctl", "-D", str(cls.data), "-l", str(cls.root / "postgres.log"),
                         "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
            cls.started = True
            cls.sql((ROOT / "db/schema.v1.sql").read_text())
            store = CaptureBodyStore(cls.root / "private")
            cls.body_ref = store.write(
                capture_id="capture:one", body=TEXT, content_sha256=SHA,
            ).body_ref
            cls.store = CaptureBodyStore.open_existing_readonly(cls.root / "private")
            cls.sql(f"""
              INSERT INTO source (id, canonical_name, source_type, canonical_url)
              VALUES ('source:one', 'NASA NTRS', 'OFFICIAL', '{URL}');
              INSERT INTO content_item (id, source_id, canonical_url, rights_status)
              VALUES ('content:one', 'source:one', '{URL}', 'CLEARED');
              INSERT INTO research_collection (id, slug, name, scope_text, policy_version)
              VALUES ('collection:one', 'dp237', 'DP237', 'source proof', 'v1');
              INSERT INTO research_collection_content
                (collection_id, content_id, inclusion_method, inclusion_version)
              VALUES ('collection:one', 'content:one', 'MANUAL_REVIEW', 'v1');
              INSERT INTO content_capture
                (id, content_id, observed_at, final_url, media_type, content_sha256,
                 body_ref, retrieval_method, retrieval_version, parser_method,
                 parser_version, rights_status, metadata)
              VALUES ('capture:one', 'content:one', '2026-10-19T00:00:00Z', '{URL}',
                 'text/plain', '{SHA}', '{cls.body_ref}', 'SAFE_HTTP', 'v1',
                 'NATIVE_DOCUMENT_TEXT', 'document-native-text-v1',
                 'CLEARED', '{{"page_count":1}}'::jsonb);
              INSERT INTO passage
                (id, content_id, capture_id, selector_type, start_char, end_char,
                 text_sha256, private_text, extraction_method, extraction_version)
              VALUES ('passage:one', 'content:one', 'capture:one', 'TEXT_POSITION',
                 0, {len(TEXT)}, '{SHA}', 'Primo. No, non aumenta. Ultimo.',
                 'NATIVE_DOCUMENT_TEXT', 'document-native-text-v1');
              INSERT INTO content_derivation_family (id, root_content_id, status)
              VALUES ('family:one', 'content:one', 'APPROVED');
              INSERT INTO private_source_rights_record(
                id, subject_fingerprint, source_family, locator_kind,
                locator_value, content_id, rights_status, rights_receipt_ref,
                permitted_uses, reviewed_at, reviewer_ref, expires_at, policy_version)
              VALUES ('rights:one', repeat('1', 64), 'NASA NTRS', 'URL', '{URL}',
                'content:one', 'CLEARED', 'fixture:receipt',
                ARRAY['FETCH','STORE_BODY','PARSE_TEXT'], '2026-10-19T00:00:00Z',
                'fixture:reviewer', '2027-10-19T00:00:00Z', 'v1');
            """)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def command(cls, args, *, input_text=None):
        result = subprocess.run(args, input=input_text, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr[:800])

    @classmethod
    def sql(cls, statement):
        cls.command(["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
                     "--dbname", cls.dsn], input_text=statement)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            cls.command(["pg_ctl", "-D", str(cls.data), "-m", "fast", "-w", "stop"])
            cls.started = False
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_readonly_real_postgres_source_and_revocation(self):
        readers = StudioLocalReaders(
            corpus=None, captures=_StudioCaptureReader(self.dsn), candidates=None,
            body_store=self.store,
        )
        request = {
            "collection_id": "collection:one", "content_id": "content:one",
            "capture_id": "capture:one", "passage_id": "passage:one",
            "quote_text": QUOTE,
        }
        # Use a real DB snapshot and stored private file. Network observation
        # is stubbed at the module seam; a separate live smoke proves NASA.
        def fake(*_args, **_kwargs):
            return FetchedBytes(TEXT, URL, 200, "text/plain", "utf-8", len(TEXT))
        result = read_studio_exact_source_jump(
            readers.captures, readers.body_store, **request,
            fetch=fake,
        )
        self.assertEqual(result["status"], "BEST_EFFORT_TEXT")
        self.assertTrue(result["url"].startswith(URL))
        self.sql("UPDATE content_capture SET hold_status='RIGHTS_HOLD' WHERE id='capture:one';")
        held = read_studio_exact_source_jump(
            readers.captures, readers.body_store, **request,
            fetch=fake,
        )
        self.assertEqual(held["reason"], "CAPTURE_RIGHTS_OR_BODY_BLOCKED")
        self.assertIsNone(held["url"])
        self.sql("UPDATE content_capture SET hold_status='NONE' WHERE id='capture:one';")
        self.sql("""
          INSERT INTO private_source_rights_record(
            id, subject_fingerprint, source_family, locator_kind,
            locator_value, content_id, rights_status, rights_receipt_ref,
            permitted_uses, reviewed_at, reviewer_ref, policy_version, supersedes_id)
          SELECT 'rights:revoked', subject_fingerprint, source_family, locator_kind,
            locator_value, content_id, 'REVOKED', 'fixture:revocation',
            permitted_uses, now(), 'fixture:reviewer', 'v2', id
          FROM private_source_rights_record WHERE id='rights:one';
        """)
        revoked = read_studio_exact_source_jump(
            readers.captures, readers.body_store, **request, fetch=fake,
        )
        self.assertEqual(revoked["reason"], "SOURCE_BINDING_OR_RIGHTS_INVALID")
        self.assertIsNone(revoked["url"])

    def test_rights_must_bind_exact_capture_url_and_expire(self):
        # The registry is append-only: create independent real SQL fixtures,
        # instead of mutating reviewed source rights in place.
        readers = _StudioCaptureReader(self.dsn)
        for suffix, allowed_url, expiry in (
            ("foreign", "https://different.example/other", "2027-10-19T00:00:00Z"),
            ("no-expiry", URL, None),
            ("no-store", URL, "2027-10-19T00:00:00Z"),
        ):
            expires = f"'{expiry}'" if expiry else "NULL"
            fingerprint_char = {"foreign": "2", "no-expiry": "3", "no-store": "4"}[suffix]
            permitted = ("ARRAY['FETCH','PARSE_TEXT']" if suffix == "no-store"
                         else "ARRAY['FETCH','STORE_BODY','PARSE_TEXT']")
            self.sql(f"""
              INSERT INTO content_item(id, source_id, canonical_url, rights_status)
              VALUES ('content:{suffix}', 'source:one', '{URL}', 'CLEARED');
              INSERT INTO research_collection_content
                (collection_id, content_id, inclusion_method, inclusion_version)
              VALUES ('collection:one', 'content:{suffix}', 'MANUAL_REVIEW', 'v1');
              INSERT INTO content_capture
                (id, content_id, observed_at, final_url, media_type, content_sha256,
                 body_ref, retrieval_method, retrieval_version, parser_method,
                 parser_version, rights_status, metadata)
              SELECT 'capture:{suffix}', 'content:{suffix}', observed_at,
                final_url, media_type, content_sha256, body_ref,
                retrieval_method, retrieval_version, parser_method,
                parser_version, rights_status, metadata
              FROM content_capture WHERE id='capture:one';
              INSERT INTO passage
                (id, content_id, capture_id, selector_type, start_char, end_char,
                 text_sha256, private_text, extraction_method, extraction_version)
              SELECT 'passage:{suffix}', 'content:{suffix}', 'capture:{suffix}',
                selector_type, start_char, end_char, text_sha256, private_text,
                extraction_method, extraction_version
              FROM passage WHERE id='passage:one';
              INSERT INTO content_derivation_family(id, root_content_id, status)
              VALUES ('family:{suffix}', 'content:{suffix}', 'APPROVED');
              INSERT INTO private_source_rights_record(
                id, subject_fingerprint, source_family, locator_kind,
                locator_value, content_id, rights_status, rights_receipt_ref,
                permitted_uses, reviewed_at, reviewer_ref, expires_at, policy_version)
              VALUES ('rights:{suffix}', repeat('{fingerprint_char}', 64), 'NASA NTRS', 'URL',
                '{allowed_url}', 'content:{suffix}', 'CLEARED', 'fixture:receipt',
                {permitted}, '2026-10-19T00:00:00Z',
                'fixture:reviewer', {expires}, 'v1');
            """)
            result = read_studio_exact_source_jump(
                readers, self.store, collection_id="collection:one",
                content_id=f"content:{suffix}", capture_id=f"capture:{suffix}",
                passage_id=f"passage:{suffix}", quote_text=QUOTE,
                fetch=lambda *_a, **_k: FetchedBytes(
                    TEXT, URL, 200, "text/plain", "utf-8", len(TEXT)
                ),
            )
            with self.subTest(suffix=suffix):
                self.assertEqual(result["reason"], "SOURCE_BINDING_OR_RIGHTS_INVALID")
                self.assertIsNone(result["url"])


if __name__ == "__main__":
    unittest.main()

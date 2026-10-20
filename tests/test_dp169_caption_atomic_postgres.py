"""#169: isolated PostgreSQL proof for the caption/raw-text revocation fence."""
from __future__ import annotations

import hashlib
import select
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRegistryStore, RightsSubject,
)
from dichiarazioni_pubbliche.youtube_caption_variant_store import insert_rights_bound_caption_variant

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.youtube.com/watch?v=QaE00l6JZ8w"
POLICY = "dp169-fixture-policy-v1"


class CaptionAtomicPostgresTests(unittest.TestCase):
    @classmethod
    def _run(cls, args, *, text_input=None):
        result = subprocess.run(args, input=text_input, text=True, capture_output=True, timeout=45)
        if result.returncode:
            raise RuntimeError(f"isolated Postgres command failed: {result.stderr[-400:]}")
        return result.stdout.strip()

    @classmethod
    def setUpClass(cls):
        pg_config = shutil.which("pg_config")
        binary_dir = None
        if pg_config is not None:
            result = subprocess.run([pg_config, "--bindir"], capture_output=True,
                                    text=True, timeout=5)
            if result.returncode == 0:
                binary_dir = Path(result.stdout.strip())
        tools = {}
        for item in ("initdb", "pg_ctl", "psql"):
            candidate = binary_dir / item if binary_dir is not None else None
            tools[item] = shutil.which(item) or (
                str(candidate) if candidate is not None and candidate.is_file() else None
            )
        if any(not binary for binary in tools.values()):
            raise unittest.SkipTest("ephemeral PostgreSQL binaries unavailable")
        cls.pg_ctl = tools["pg_ctl"]
        cls.psql = tools["psql"]
        cls.temp = tempfile.TemporaryDirectory(prefix="dp169-rights-postgres-")
        root = Path(cls.temp.name)
        cls.data = root / "cluster"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.started = False
        try:
            cls._run([tools["initdb"], "-D", str(cls.data), "--username=postgres",
                      "--auth=trust", "--no-locale", "--encoding=UTF8"])
            cls._run([tools["pg_ctl"], "-D", str(cls.data), "-l", str(root / "postgres.log"),
                      "-o", f"-F -p {port} -h 127.0.0.1 -k {root}", "-w", "start"])
            cls.started = True
            cls.dsn = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            cls._run([tools["psql"], "-X", "-v", "ON_ERROR_STOP=1",
                      "--dbname", cls.dsn, "-f", str(ROOT / "db/schema.v1.sql")])
            cls.store = QueueRuntimeStore(cls.dsn)
            cls.registry = PrivateRightsRegistryStore(cls.dsn)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            cls._run([cls.pg_ctl, "-D", str(cls.data), "-m", "fast", "-w", "stop"])
            cls.started = False
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def setUp(self):
        self.content_id = f"content:dp169:atomic:{self._testMethodName}"
        self.subject = RightsSubject("YOUTUBE", "URL", URL, content_id=self.content_id)
        self.store.run("INSERT INTO content_item(id, canonical_url) VALUES (:'id', :'url')",
                       id=self.content_id, url=URL)
        now = datetime.now(timezone.utc)
        self.expires_at = now + (timedelta(seconds=7) if
                                 self._testMethodName == "test_expired_while_waiting_for_rights_lock"
                                 else timedelta(days=1))
        self.record = self.registry.record_rights(
            subject=self.subject, policy_version=POLICY, rights_status="CLEARED",
            rights_receipt_ref="fixture:authorized-for-synthetic-only",
            permitted_uses=("FETCH", "STORE_BODY"),
            reviewed_at=(now - timedelta(days=1)).isoformat(),
            expires_at=self.expires_at.isoformat(),
            reviewer_ref="fixture:qualified-reviewer",
        )
        self.guard = SourceFamilyUseGuard(
            read_current=self.registry.read_current, subject=self.subject,
            rights_record_id=self.record.id, policy_version=POLICY,
        )
        self.guard.require("FETCH")
        self.guard.require("STORE_BODY")

    def insert(self, text="synthetic-caption-only"):
        return insert_rights_bound_caption_variant(
            self.store, self.guard, content_id=self.content_id,
            provider_id="youtube", source_kind="YOUTUBE_MANUAL_CAPTION",
            language="it", raw_text=text,
            raw_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            is_platform_caption=True, is_manual_caption=True, metadata={"fixture": True},
            segments=[{"segment_index": 0, "start_ms": 0, "end_ms": 1000,
                       "text": text, "metadata": {}}],
        )

    def count(self):
        return int(self.store.run("SELECT count(*) FROM transcript_variant WHERE content_id=:'id'",
                                  id=self.content_id))

    def segment_count(self):
        return int(self.store.run(
            "SELECT count(*) FROM transcript_segment s "
            "JOIN transcript_variant v ON v.id=s.variant_id "
            "WHERE v.content_id=:'id'", id=self.content_id))

    def revoke(self):
        self.registry.record_rights(
            subject=self.subject, policy_version=POLICY, rights_status="REVOKED",
            rights_receipt_ref="fixture:revoked",
            permitted_uses=(), reviewed_at=datetime.now(timezone.utc).isoformat(),
            reviewer_ref="fixture:qualified-reviewer", supersedes_record_id=self.record.id,
        )

    def test_authorized_atomic_insert_and_revoked_followup_is_denied(self):
        variant, inserted = self.insert()
        self.assertTrue(inserted)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.store.run(
            "SELECT count(*) FROM transcript_segment WHERE text='synthetic-caption-only'"), "1")
        self.assertEqual(self.insert()[0], variant)
        self.revoke()
        with self.assertRaises(SourceUseBlocked):
            self.insert("text-must-not-appear")
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.store.run(
            "SELECT count(*) FROM transcript_variant WHERE raw_text='text-must-not-appear'"), "0")
        self.assertEqual(self.store.run(
            "SELECT count(*) FROM transcript_segment WHERE text='text-must-not-appear'"), "0")

    def test_revocation_committed_after_preflight_before_sql_cannot_insert(self):
        # Guard is already approved in setUp; supersession occurs just before
        # the actual insert transaction gets its row lock.
        self.revoke()
        with self.assertRaises(SourceUseBlocked):
            self.insert("revoked-before-insert")
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.segment_count(), 0)

    def test_expired_while_waiting_for_rights_lock(self):
        # A SQL transaction may begin while a permit is valid and then wait
        # on FOR UPDATE past expires_at. Transaction-start time is no longer
        # an acceptable timestamp for the eventual raw-text INSERT.
        self.assertGreater((self.expires_at - datetime.now(timezone.utc)).total_seconds(), 3)
        locker = subprocess.Popen(
            [self.psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "--dbname", self.dsn],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        try:
            locker.stdin.write(
                "BEGIN;\n"
                f"SELECT id FROM private_source_rights_record WHERE id='{self.record.id}' FOR UPDATE;\n"
            )
            locker.stdin.flush()
            ready, _, _ = select.select([locker.stdout], [], [], 8)
            self.assertTrue(ready, "locker did not acquire the rights row")
            self.assertEqual(locker.stdout.readline().strip(), self.record.id)
            entered_sql = threading.Event()
            original_run = self.store.run_literal

            def observed_sql(statement):
                entered_sql.set()
                return original_run(statement)

            self.store.run_literal = observed_sql
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.insert, "must-not-persist-after-expiry")
                self.assertTrue(entered_sql.wait(8), "caption SQL did not start")
                self.assertFalse(future.done(), "caption bypassed the rights row lock")
                time.sleep(max(0, (self.expires_at - datetime.now(timezone.utc)).total_seconds() + 0.5))
                locker.stdin.write("COMMIT;\n")
                locker.stdin.flush()
                locker.stdin.close()
                self.assertEqual(locker.wait(timeout=12), 0)
                with self.assertRaises(SourceUseBlocked):
                    future.result(timeout=12)
            self.assertEqual(self.count(), 0)
            self.assertEqual(self.segment_count(), 0)
        finally:
            if locker.poll() is None:
                locker.kill()
                locker.wait(timeout=5)
            locker.stdout.close()
            locker.stderr.close()

    def test_concurrent_revocation_with_parent_row_lock_prevents_raw_text_insert(self):
        # The revoker locks the reviewed parent, then an authorized capture
        # waits for the same row; after the revocation commits, the capture's
        # later statement must see the successor and insert no raw_text.
        proc = subprocess.Popen(
            [self.psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "--dbname", self.dsn],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        try:
            proc.stdin.write(
                "BEGIN;\n"
                f"SELECT id FROM private_source_rights_record WHERE id='{self.record.id}' FOR UPDATE;\n"
            )
            proc.stdin.flush()
            ready, _, _ = select.select([proc.stdout], [], [], 8)
            self.assertTrue(ready, "revoker could not acquire parent lock")
            self.assertEqual(proc.stdout.readline().strip(), self.record.id)
            child = "private-rights:dp169:concurrent-revocation"
            sql = f"""
                INSERT INTO private_source_rights_record (
                    id, subject_fingerprint, source_family, locator_kind,
                    locator_value, content_id, rights_status, rights_receipt_ref,
                    permitted_uses, reviewed_at, reviewer_ref, policy_version,
                    supersedes_id
                ) SELECT
                    '{child}', subject_fingerprint, source_family, locator_kind,
                    locator_value, content_id, 'REVOKED', 'fixture:revoked',
                    ARRAY[]::text[], now(), 'fixture:qualified-reviewer',
                    policy_version, id
                FROM private_source_rights_record WHERE id='{self.record.id}';
            """
            entered_sql = threading.Event()
            original_run = self.store.run_literal
            def observed_sql(statement):
                entered_sql.set()
                return original_run(statement)
            self.store.run_literal = observed_sql
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.insert, "must-not-persist-on-concurrent-revoke")
                self.assertTrue(entered_sql.wait(8), "caption SQL did not start")
                self.assertFalse(future.done(), "caption bypassed the revoker's row lock")
                proc.stdin.write(sql + "\nCOMMIT;\n")
                proc.stdin.flush()
                proc.stdin.close()
                self.assertEqual(proc.wait(timeout=12), 0)
                with self.assertRaises(SourceUseBlocked):
                    future.result(timeout=12)
            self.assertEqual(self.count(), 0)
            self.assertEqual(self.segment_count(), 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()

"""DP-519: disposable canonical PG, private read-only Studio workload and revocation."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_operator_workload_pg_v1 import (  # noqa: E402
    IsolatedStudioOperatorWorkloadPg,
)


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise unittest.SkipTest("disposable PostgreSQL binary unavailable: " + name)
    return path


def execute(args, *, sql=None):
    proc = subprocess.run(
        args,
        input=sql,
        text=True,
        capture_output=True,
        timeout=50,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr[-1600:])
    return proc.stdout.strip()


class StudioOperatorWorkloadPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ("initdb", "pg_ctl", "psql"):
            executable(name)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp519-pg-")
        cls.data = Path(cls.tmp.name) / "data"
        cls.running = False
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        try:
            execute(
                [
                    executable("initdb"),
                    "-D",
                    str(cls.data),
                    "--username=postgres",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--no-locale",
                ]
            )
            execute(
                [
                    executable("pg_ctl"),
                    "-D",
                    str(cls.data),
                    "-w",
                    "-l",
                    str(Path(cls.tmp.name) / "server.log"),
                    "-o",
                    f"-F -p {cls.port} -h 127.0.0.1 -k {cls.tmp.name}",
                    "start",
                ]
            )
            cls.running = True
            admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            execute(
                [executable("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", admin],
                sql="CREATE DATABASE dp519_disposable;",
            )
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp519_disposable"
            execute(
                [executable("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
                sql=(ROOT / "db/schema.v1.sql").read_text(),
            )
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "running", False):
            execute(
                [
                    executable("pg_ctl"),
                    "-D",
                    str(cls.data),
                    "-m",
                    "immediate",
                    "-w",
                    "stop",
                ]
            )
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def sql(cls, code):
        return execute(
            [executable("psql"), "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
            sql=code,
        )

    def setUp(self):
        self.sql("""
SET session_replication_role=replica;
TRUNCATE private_source_rights_record, statement_candidate_passage,
 claim_candidate, statement_candidate, passage, content_capture,
 research_collection_content, research_collection, content_item, source CASCADE;
SET session_replication_role=origin;
INSERT INTO source(id,canonical_name,source_type)
 VALUES ('src:1','Synthetic source','WEB');
INSERT INTO research_collection(id,slug,name,scope_text,policy_version)
 VALUES ('col:alpha','alpha','Synthetic alpha','Private','v1'),
        ('col:beta','beta','Synthetic beta','Private','v1');
INSERT INTO content_item(id,source_id,canonical_url,rights_status,processing_status)
 VALUES ('content:1','src:1','https://fixture.invalid/one','CLEARED','DISCOVERED'),
        ('content:2','src:1','https://fixture.invalid/two','CLEARED','DISCOVERED'),
        ('content:3','src:1','https://fixture.invalid/three','CLEARED','DISCOVERED'),
        ('content:secret','src:1','https://fixture.invalid/private','CLEARED','DISCOVERED');
INSERT INTO research_collection_content(
 collection_id,content_id,inclusion_method,inclusion_version,status)
 VALUES ('col:alpha','content:1','FIXTURE','v1','INCLUDED'),
        ('col:alpha','content:2','FIXTURE','v1','INCLUDED'),
        ('col:alpha','content:3','FIXTURE','v1','INCLUDED'),
        ('col:beta','content:secret','FIXTURE','v1','INCLUDED'),
        ('col:alpha','content:secret','FIXTURE','v1','REMOVED');
INSERT INTO content_capture(id,content_id,observed_at,final_url,
 content_sha256,retrieval_method,retrieval_version,rights_status)
 VALUES ('capture:one','content:1','2026-10-10T10:00:00Z',
   'https://fixture.invalid/one',repeat('a',64),'FIXTURE','v1','CLEARED'),
        ('capture:two','content:2','2026-10-10T10:00:00Z',
   'https://fixture.invalid/two',repeat('b',64),'FIXTURE','v1','CLEARED');
INSERT INTO passage(id,content_id,capture_id,selector_type,start_char,end_char,
 text_sha256,private_text,extraction_method,extraction_version)
 VALUES ('passage:one','content:1','capture:one','TEXT_POSITION',0,12,
    repeat('c',64),'DO NOT LEAK TRANSCRIPT','FIXTURE','v1'),
        ('passage:two','content:2','capture:two','TEXT_POSITION',0,12,
    repeat('d',64),'DO NOT LEAK SECOND QUOTE','FIXTURE','v1');
INSERT INTO statement_candidate(
 id,content_id,statement_text_hash,normalized_statement,extraction_version,status)
 VALUES ('statement:1','content:1',repeat('e',64),
    'DO NOT LEAK NORMALIZED STATEMENT','v1','CANDIDATE');
INSERT INTO statement_candidate_passage(statement_candidate_id,passage_id,content_id)
 VALUES ('statement:1','passage:one','content:1');
INSERT INTO claim_candidate(id,statement_candidate_id,content_id,normalized_claim,
 proposed_claim_type,extraction_version,status)
 VALUES ('claim:1','statement:1','content:1',
    'DO NOT LEAK NORMALIZED CLAIM','CURRENT_POLICY','v1','CANDIDATE');
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,permitted_uses,reviewed_at,reviewer_ref,policy_version)
 VALUES ('rights:1',repeat('1',64),'FIXTURE','URL','https://fixture.invalid/one',
   'content:1','CLEARED','fixture:receipt',
   ARRAY['FETCH','PARSE_TEXT'],'2026-10-10T00:00:00Z','fixture:reviewer','v1'),
        ('rights:2',repeat('2',64),'FIXTURE','URL','https://fixture.invalid/two',
   'content:2','CLEARED','fixture:receipt',
   ARRAY['FETCH','PARSE_TEXT'],'2026-10-10T00:00:00Z','fixture:reviewer','v1'),
        ('rights:3',repeat('3',64),'FIXTURE','URL','https://fixture.invalid/three',
   'content:3','CLEARED','fixture:receipt',
   ARRAY['FETCH','PARSE_TEXT'],'2026-10-10T00:00:00Z','fixture:reviewer','v1');
""")
        self.store = IsolatedStudioOperatorWorkloadPg(
            self.dsn,
            allow_disposable_postgres=True,
        )

    def read(self, **changes):
        return self.store.read(
            collection_id="col:alpha",
            verify_authenticated_operator=lambda _: True,
            **changes,
        )

    def test_scoped_operator_worklist_counts_no_private_text_or_fabricated_go(self):
        response = self.read()
        self.assertEqual(response["total_members"], 3)
        self.assertEqual(response["capture_count"], 2)
        self.assertEqual(response["passage_count"], 2)
        self.assertEqual(response["statement_candidate_count"], 1)
        self.assertEqual(response["claim_candidate_count"], 1)
        self.assertEqual(response["blocked_members"], 1)
        self.assertEqual(response["review_only_members"], 2)
        self.assertEqual(response["rows"][0]["content_rights_state"], "CLEARED")
        self.assertEqual(response["rows"][0]["current_rights_state"], "CLEARED")
        self.assertEqual(response["rows"][0]["capture_state"], "CAPTURED")
        self.assertEqual(response["rows"][0]["capture_hold_state"], "NONE")
        self.assertEqual(
            response["blocked_queue"],
            [
                {
                    "content_id": "content:3",
                    "reason": "CAPTURE_MISSING",
                    "next_action": "REVIEW_CAPTURE_AVAILABILITY",
                }
            ],
        )
        self.assertEqual(
            [row["reason"] for row in response["rows"]],
            [
                "PRIVATE_TRIAGE_REQUIRED",
                "STATEMENT_CANDIDATE_MISSING",
                "CAPTURE_MISSING",
            ],
        )
        rendered = repr(response)
        for secret in ("DO NOT LEAK", "https://fixture.invalid", "fixture:receipt"):
            self.assertNotIn(secret, rendered)
        for key in (
            "dispatch_authorized",
            "publication_authority",
            "text_review_authority",
            "image_approval_authority",
            "source_rights_attested",
        ):
            self.assertIs(response[key], False)

    def test_auth_guard_collection_isolation_and_rejected_members(self):
        with self.assertRaisesRegex(ValueError, "OPERATOR_AUTH_REQUIRED"):
            self.store.read(collection_id="col:alpha")
        with self.assertRaisesRegex(ValueError, "OPERATOR_AUTH_REQUIRED"):
            self.store.read(
                collection_id="col:alpha", verify_authenticated_operator=lambda _: False
            )
        with self.assertRaisesRegex(ValueError, "ID_INVALID"):
            self.store.read(
                collection_id="col:alpha';DROP TABLE source;--",
                verify_authenticated_operator=lambda _: True,
            )
        other = self.store.read(
            collection_id="col:beta", verify_authenticated_operator=lambda _: True
        )
        self.assertEqual(other["total_members"], 1)
        self.assertEqual(other["rows"][0]["content_id"], "content:secret")
        self.assertNotIn("content:secret", repr(self.read()))
        self.assertEqual(self.sql("SELECT count(*) FROM source;"), "1")

    def test_repeatable_keyset_cursor_restart_and_cross_collection_rejection(self):
        first = self.read(limit=1)
        self.assertEqual([r["content_id"] for r in first["rows"]], ["content:1"])
        self.assertIsNotNone(first["next_cursor"])
        reopened = IsolatedStudioOperatorWorkloadPg(
            self.dsn, allow_disposable_postgres=True
        )
        second = reopened.read(
            collection_id="col:alpha",
            limit=1,
            after=first["next_cursor"],
            verify_authenticated_operator=lambda _: True,
        )
        self.assertEqual([r["content_id"] for r in second["rows"]], ["content:2"])
        third = self.read(limit=1, after=second["next_cursor"])
        self.assertEqual([r["content_id"] for r in third["rows"]], ["content:3"])
        self.assertIsNone(third["next_cursor"])
        with self.assertRaisesRegex(ValueError, "CURSOR_INVALID"):
            self.store.read(
                collection_id="col:beta",
                after=first["next_cursor"],
                verify_authenticated_operator=lambda _: True,
            )

    def test_revocation_between_pages_refuses_stale_snapshot(self):
        first = self.read(limit=1)
        self.sql("""
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,policy_version,supersedes_id)
 VALUES ('rights:1:revoked',repeat('1',64),'FIXTURE','URL',
  'https://fixture.invalid/one','content:1','REVOKED',
  'fixture:revoked','v1','rights:1');
""")
        now = self.read()
        self.assertEqual(now["rows"][0]["reason"], "CURRENT_RIGHTS_NOT_READY")
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_CHANGED"):
            self.read(limit=1, after=first["next_cursor"])

    def test_conflicting_current_rights_leaves_block_before_candidate_triage(self):
        self.assertEqual(self.read()["rows"][0]["state"], "REVIEW_ONLY")
        self.sql("""
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,policy_version)
 VALUES ('rights:conflict',repeat('9',64),'FIXTURE','URL',
    'https://fixture.invalid/one','content:1','REVOKED','fixture:hold','v1');
""")
        result = self.read()
        self.assertEqual(result["rows"][0]["state"], "BLOCKED")
        self.assertEqual(result["rows"][0]["reason"], "RIGHTS_MISSING_OR_AMBIGUOUS")
        self.assertEqual(result["rows"][0]["current_rights_state"], "AMBIGUOUS")
        self.assertEqual(
            result["blocked_queue"][0]["next_action"], "RESOLVE_SOURCE_RIGHTS"
        )
        self.assertFalse(result["publication_authority"])

    def test_latest_rights_expired_or_missing_permitted_use_is_held(self):
        self.sql("""
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,permitted_uses,reviewed_at,reviewer_ref,
 policy_version,expires_at)
 VALUES ('rights:expired',repeat('8',64),'FIXTURE','URL',
    'https://fixture.invalid/private','content:secret','CLEARED',
    'fixture:old',ARRAY['FETCH','PARSE_TEXT'],'2025-10-10T00:00:00Z',
    'fixture:reviewer','v1','2026-01-01T00:00:00Z');
""")
        other = self.store.read(
            collection_id="col:beta", verify_authenticated_operator=lambda _: True
        )
        self.assertEqual(other["rows"][0]["reason"], "CURRENT_RIGHTS_NOT_READY")
        self.sql("""
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,permitted_uses,reviewed_at,reviewer_ref,
 policy_version,supersedes_id)
 VALUES ('rights:1:restricted',repeat('1',64),'FIXTURE','URL',
    'https://fixture.invalid/one','content:1','CLEARED',
    'fixture:restricted',ARRAY['FETCH']::text[],'2026-10-10T00:00:00Z',
    'fixture:reviewer','v1','rights:1');
""")
        self.assertEqual(self.read()["rows"][0]["reason"], "CURRENT_RIGHTS_NOT_READY")

    def test_more_than_bounded_collection_members_refuses_truncated_completeness(self):
        self.sql("""
INSERT INTO content_item(id,source_id,canonical_url,rights_status)
 SELECT 'overflow:' || lpad(i::text,4,'0'),'src:1',
        'https://fixture.invalid/' || i,'UNKNOWN'
 FROM generate_series(1,498) i;
INSERT INTO research_collection_content(
  collection_id,content_id,inclusion_method,inclusion_version)
 SELECT 'col:alpha','overflow:' || lpad(i::text,4,'0'),'FIXTURE','v1'
 FROM generate_series(1,498) i;
""")
        with self.assertRaisesRegex(ValueError, "SCOPE_TOO_LARGE"):
            self.read()

    def test_current_latest_capture_and_candidate_scoping(self):
        before = self.read()
        self.assertEqual(before["rows"][0]["claim_candidates"], 1)
        self.sql("""
INSERT INTO content_capture(id,content_id,observed_at,final_url,
 content_sha256,retrieval_method,retrieval_version,rights_status,
 hold_status)
 VALUES ('capture:one:latest','content:1','2026-10-12T00:00:00Z',
 'https://fixture.invalid/one',repeat('f',64),'FIXTURE','v2',
 'CLEARED','RIGHTS_HOLD');
""")
        after = self.read()
        self.assertEqual(after["rows"][0]["capture_id"], "capture:one:latest")
        self.assertEqual(after["rows"][0]["reason"], "CAPTURE_HELD")
        self.assertEqual(after["rows"][0]["capture_hold_state"], "RIGHTS_HOLD")
        self.assertEqual(after["rows"][0]["statement_candidates"], 0)
        self.assertEqual(after["rows"][0]["claim_candidates"], 0)
        self.assertEqual(after["rows"][0]["passage_count"], 0)

    def test_held_candidate_or_collection_paused_is_actionable_block(self):
        self.sql("UPDATE claim_candidate SET status='HELD' WHERE id='claim:1';")
        self.assertEqual(self.read()["rows"][0]["reason"], "CANDIDATE_HELD")
        self.sql("UPDATE research_collection SET status='PAUSED' WHERE id='col:alpha';")
        view = self.read()
        self.assertEqual(view["blocked_members"], 3)
        self.assertTrue(
            all(row["reason"] == "COLLECTION_NOT_ACTIVE" for row in view["rows"])
        )

    def test_bounded_page_concurrent_writer_and_read_snapshot(self):
        self.assertEqual(self.read(limit=1)["total_members"], 3)
        with ThreadPoolExecutor(max_workers=2) as pool:
            reader = pool.submit(self.read, limit=1)
            revoke = pool.submit(
                self.sql,
                "UPDATE content_capture SET hold_status='RIGHTS_HOLD' "
                "WHERE id='capture:two';",
            )
            result = reader.result()
            revoke.result()
        self.assertEqual(result["total_members"], 3)
        self.assertEqual(self.read()["rows"][1]["reason"], "CAPTURE_HELD")
        with self.assertRaisesRegex(ValueError, "PAGE_INVALID"):
            self.read(limit=500)
        with self.assertRaisesRegex(ValueError, "DISPOSABLE_ONLY"):
            IsolatedStudioOperatorWorkloadPg(
                self.dsn.replace("dp519_disposable", "postgres"),
                allow_disposable_postgres=True,
            )


if __name__ == "__main__":
    unittest.main()

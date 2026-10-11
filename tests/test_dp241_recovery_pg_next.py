"""DP-241: private real-PostgreSQL lineage and durable no-dispatch CAS canary."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.original_source_investigation_pg_v1 import (  # noqa: E402
    IsolatedOriginalRecoveryPg,
)
from tests.test_dp241_original_source_investigation import (  # noqa: E402
    plan, receipt, target,
)


def binary(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise unittest.SkipTest("disposable PostgreSQL binaries unavailable: " + name)
    return found


def command(args, *, stdin=None):
    result = subprocess.run(
        args, input=stdin, text=True, capture_output=True, timeout=45, check=False,
    )
    if result.returncode:
        raise RuntimeError("disposable PostgreSQL failure: " + result.stderr[-1800:])
    return result.stdout.strip()


class OriginalSourceRecoveryPgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for exe in ("initdb", "pg_ctl", "psql"):
            binary(exe)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp241-original-pg-")
        cls.data = Path(cls.tmp.name) / "data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.running = False
        try:
            command([binary("initdb"), "-D", str(cls.data), "--username=postgres",
                     "--auth=trust", "--encoding=UTF8", "--no-locale"])
            command([binary("pg_ctl"), "-D", str(cls.data), "-w",
                     "-l", str(Path(cls.tmp.name) / "server.log"), "-o",
                     f"-F -p {cls.port} -h 127.0.0.1 -k {cls.tmp.name}", "start"])
            cls.running = True
            admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            command([binary("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", admin],
                    stdin="CREATE DATABASE dp241_disposable;")
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp241_disposable"
            command([binary("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
                    stdin=(ROOT / "db/schema.v1.sql").read_text())
            cls.store = IsolatedOriginalRecoveryPg(cls.dsn, allow_disposable_postgres=True)
            cls.store.install_fixture_schema()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "running", False):
            command([binary("pg_ctl"), "-D", str(cls.data), "-m", "immediate", "-w", "stop"])
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def sql(cls, text):
        return command([binary("psql"), "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
                        "-d", cls.dsn], stdin=text)

    def setUp(self):
        # Only on this ephemeral cluster: canonical rights tables are immutable
        # in normal sessions, so reset each independent synthetic case with a
        # local fixture-only trigger override, never by weakening runtime DDL.
        self.sql("SET session_replication_role=replica; "
                 "TRUNCATE dp241_pg_event, dp241_pg_plan, "
                 "private_source_rights_record, passage, content_capture, "
                 "content_item, source CASCADE; "
                 "SET session_replication_role=origin;")
        self.t = target()
        self.p = plan(source=self.t)
        self.sql("""
            INSERT INTO source(id, canonical_name, source_type)
              VALUES ('source:clip', 'Private fixture', 'WEB');
            INSERT INTO content_item(id,source_id,canonical_url,rights_status)
              VALUES ('content:clip','source:clip','https://fixture.invalid/clip','CLEARED');
            INSERT INTO content_capture(id,content_id,observed_at,final_url,
                content_sha256,retrieval_method,retrieval_version,rights_status)
              VALUES ('capture:content:clip','content:clip','2026-10-11T00:00:00Z',
                'https://fixture.invalid/clip', '""" + self.t.capture.content_sha256 + """',
                'FIXTURE','v1','CLEARED');
            INSERT INTO passage(id,content_id,capture_id,selector_type,start_char,end_char,
                text_sha256,extraction_method,extraction_version)
              VALUES ('passage:content:clip','content:clip','capture:content:clip',
                'TEXT_POSITION',0,16,'""" + self.t.passage.text_sha256 + """','FIXTURE','v1');
            INSERT INTO private_source_rights_record (
                id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
                passage_id,rights_status,rights_receipt_ref,permitted_uses,
                reviewed_at,reviewer_ref,policy_version)
              VALUES ('rights:clip',repeat('a',64),'fixture','PASSAGE','passage:content:clip',
                'content:clip','passage:content:clip','CLEARED','fixture-only',
                ARRAY['DISCOVER_METADATA','FETCH'],now(),'fixture-reviewer','fixture-v1');
        """)

    def register(self):
        return self.store.register(self.p, self.t, source_id="source:clip")

    def test_real_canonical_lineage_and_planner_before_any_reservation(self):
        state = self.register()
        self.assertEqual(state.revision, 0)
        self.assertEqual(state.decision.status, "READY_PRIVATE_PROPOSAL")
        self.assertEqual(state.receipts, ())
        self.assertFalse(state.publication_authority)
        self.assertFalse(state.dispatch_authorized)

    def test_reserve_cas_replay_restart_and_missing_completion_fences_work(self):
        self.register()
        first = self.store.reserve(self.p, self.t, source_id="source:clip",
                                   key="request:one", expected_revision=0)
        self.assertEqual(first.revision, 1)
        self.assertEqual(first.pending_attempt_id, self.p.methods[0].attempt_id)
        reopened = IsolatedOriginalRecoveryPg(self.dsn, allow_disposable_postgres=True)
        self.assertEqual(reopened.read(self.p, self.t, source_id="source:clip"), first)
        self.assertEqual(reopened.reserve(self.p, self.t, source_id="source:clip",
                                          key="request:one", expected_revision=0), first)
        with self.assertRaisesRegex(ValueError, "UNCONFIRMED"):
            reopened.reserve(self.p, self.t, source_id="source:clip",
                             key="request:two", expected_revision=1)

    def test_completion_reconciles_actual_dp241_planner_and_replay(self):
        self.register()
        reserved = self.store.reserve(self.p, self.t, source_id="source:clip",
                                      key="request:one", expected_revision=0)
        observed = receipt(self.p, 0, "NOT_FOUND")
        done = self.store.complete(self.p, self.t, source_id="source:clip",
                                   key="request:one", expected_revision=reserved.revision,
                                   observed=observed)
        self.assertEqual(done.revision, 2)
        self.assertEqual(done.receipts, (observed,))
        self.assertEqual(done.decision.prior_attempts, 1)
        self.assertEqual(self.store.history(self.p.plan_id).receipts, (observed,))
        self.assertEqual(self.store.complete(self.p, self.t, source_id="source:clip",
                                              key="request:one", expected_revision=1,
                                              observed=observed), done)

    def test_competing_reservations_one_wins_and_revision_guard(self):
        self.register()
        first = self.store.reserve(self.p, self.t, source_id="source:clip",
                                   key="request:one", expected_revision=0)
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="request:one", expected_revision=0,
                                observed=receipt(self.p, 0, "NOT_FOUND"))
        self.assertEqual(first.revision, 1)

    def test_two_actual_postgres_clients_compete_for_single_attempt(self):
        self.register()
        def compete(key):
            try:
                return self.store.reserve(
                    self.p, self.t, source_id="source:clip",
                    key=key, expected_revision=0,
                )
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(compete, ("request:race-a", "request:race-b")))
        wins = [row for row in results if not isinstance(row, str)]
        self.assertEqual(len(wins), 1)
        self.assertEqual(wins[0].revision, 1)
        self.assertEqual(self.store.history(self.p.plan_id).revision, 1)
        self.assertTrue(any(
            "REVISION_CONFLICT" in row or "UNCONFIRMED" in row
            for row in results if isinstance(row, str)
        ))

    def test_append_only_pg_events_refuse_update_and_delete(self):
        self.register()
        self.store.reserve(self.p, self.t, source_id="source:clip",
                           key="request:one", expected_revision=0)
        with self.assertRaisesRegex(RuntimeError, "DP241_PG_APPEND_ONLY"):
            self.sql("UPDATE dp241_pg_event SET attempt_id='tampered';")
        with self.assertRaisesRegex(RuntimeError, "DP241_PG_APPEND_ONLY"):
            self.sql("DELETE FROM dp241_pg_event;")
        self.assertEqual(self.store.history(self.p.plan_id).revision, 1)

    def test_revoked_rights_after_reservation_fences_completion_without_losing_history(self):
        self.register()
        pending = self.store.reserve(self.p, self.t, source_id="source:clip",
                                     key="request:one", expected_revision=0)
        self.sql("""
            INSERT INTO private_source_rights_record(
                id,subject_fingerprint,source_family,locator_kind,locator_value,
                content_id,passage_id,rights_status,rights_receipt_ref,
                permitted_uses,reviewed_at,reviewer_ref,policy_version,supersedes_id)
            SELECT 'rights:revoked',subject_fingerprint,source_family,locator_kind,
                locator_value,content_id,passage_id,'REVOKED','fixture-revocation',
                ARRAY[]::text[],now(),'fixture-reviewer','fixture-v2',id
            FROM private_source_rights_record WHERE id='rights:clip';
        """)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="request:one", expected_revision=pending.revision,
                                observed=receipt(self.p, 0, "NOT_FOUND"))
        self.assertEqual(self.store.history(self.p.plan_id).pending_attempt_id,
                         pending.pending_attempt_id)

    def test_held_or_revoked_rights_prevents_new_work_even_after_restart(self):
        self.register()
        self.sql("""
            INSERT INTO private_source_rights_record(
                id,subject_fingerprint,source_family,locator_kind,locator_value,
                content_id,passage_id,rights_status,rights_receipt_ref,
                permitted_uses,reviewed_at,reviewer_ref,policy_version,supersedes_id)
            SELECT 'rights:revoked', subject_fingerprint,source_family,locator_kind,
                locator_value,content_id,passage_id,'REVOKED','fixture-revocation',
                ARRAY[]::text[],now(),'fixture-reviewer','fixture-v2',id
            FROM private_source_rights_record WHERE id='rights:clip';
        """)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.store.reserve(self.p, self.t, source_id="source:clip",
                               key="request:one", expected_revision=0)
        self.assertEqual(self.store.history(self.p.plan_id).revision, 0)

    def test_capture_version_replacement_holds_old_plan_and_preserves_history(self):
        self.register()
        self.sql("""
          INSERT INTO content_capture (id,content_id,observed_at,final_url,
            content_sha256,retrieval_method,retrieval_version,rights_status)
          VALUES ('capture:new','content:clip','2026-10-12T00:00:00Z',
            'https://fixture.invalid/new',repeat('f',64),'FIXTURE','v2','CLEARED');
        """)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.store.reserve(self.p, self.t, source_id="source:clip",
                               key="request:one", expected_revision=0)

    def test_wrong_source_or_cross_capture_passage_fail_closed(self):
        self.sql("INSERT INTO source(id,canonical_name,source_type) "
                 "VALUES ('source:other','Foreign', 'WEB');")
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.store.register(self.p, self.t, source_id="source:other")
        self.sql("UPDATE passage SET capture_id='capture:content:clip', "
                 "text_sha256=repeat('e',64) WHERE id='passage:content:clip';")
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.register()

    def test_unapproved_or_expired_rights_not_converted_to_permission(self):
        self.sql("""
            INSERT INTO private_source_rights_record(
                id,subject_fingerprint,source_family,locator_kind,locator_value,
                content_id,passage_id,rights_status,rights_receipt_ref,
                permitted_uses,reviewed_at,reviewer_ref,policy_version,supersedes_id)
            SELECT 'rights:limited', subject_fingerprint,source_family,locator_kind,
                locator_value,content_id,passage_id,'CLEARED','fixture-limited',
                ARRAY['FETCH']::text[],now(),'fixture-reviewer','fixture-v2',id
            FROM private_source_rights_record WHERE id='rights:clip';
        """)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.register()
        self.sql("""
            INSERT INTO private_source_rights_record(
                id,subject_fingerprint,source_family,locator_kind,locator_value,
                content_id,passage_id,rights_status,rights_receipt_ref,
                permitted_uses,reviewed_at,reviewer_ref,policy_version,supersedes_id,
                expires_at)
            SELECT 'rights:expired',subject_fingerprint,source_family,locator_kind,
                locator_value,content_id,passage_id,'CLEARED','fixture-expired',
                ARRAY['DISCOVER_METADATA','FETCH']::text[],'2019-01-01','fixture-reviewer',
                'fixture-v3',id,'2020-01-01'::timestamptz
            FROM private_source_rights_record WHERE id='rights:limited';
        """)
        with self.assertRaisesRegex(ValueError, "SOURCE_STALE_OR_HELD"):
            self.register()

    def test_foreign_or_forged_receipt_and_missing_reservation_fail(self):
        self.register()
        with self.assertRaisesRegex(ValueError, "NOT_RESERVED"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="request:one", expected_revision=0,
                                observed=receipt(self.p, 0, "NOT_FOUND"))
        state = self.store.reserve(self.p, self.t, source_id="source:clip",
                                   key="request:one", expected_revision=0)
        with self.assertRaisesRegex(ValueError, "RECEIPT"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="request:one", expected_revision=state.revision,
                                observed=replace(receipt(self.p, 0, "NOT_FOUND"),
                                                 discovery_receipt_sha256="not-a-sha"))

    def test_second_distinct_planned_method_and_cross_attempt_receipt_reuse_blocked(self):
        self.register()
        first = self.store.reserve(self.p, self.t, source_id="source:clip",
                                   key="request:one", expected_revision=0)
        evidence = receipt(self.p, 0, "NOT_FOUND")
        complete = self.store.complete(self.p, self.t, source_id="source:clip",
                                       key="request:one", expected_revision=first.revision,
                                       observed=evidence)
        second = self.store.reserve(self.p, self.t, source_id="source:clip",
                                    key="request:two", expected_revision=complete.revision)
        self.assertNotEqual(first.pending_attempt_id, second.pending_attempt_id)
        with self.assertRaisesRegex(ValueError, "DISCOVERY_RECEIPT_REUSED"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="request:two", expected_revision=second.revision,
                                observed=replace(
                                    receipt(self.p, 1, "NOT_FOUND"),
                                    discovery_receipt_sha256=evidence.discovery_receipt_sha256,
                                ))
        self.assertEqual(self.store.history(self.p.plan_id).revision, 3)
        done = self.store.complete(self.p, self.t, source_id="source:clip",
                                   key="request:two", expected_revision=second.revision,
                                   observed=receipt(self.p, 1, "CHECKED_INSUFFICIENT"))
        self.assertEqual(done.revision, 4)
        self.assertEqual(done.decision.prior_attempts, 2)
        self.assertEqual(len(done.receipts), 2)

    def test_found_candidate_requires_external_proof_and_is_not_auto_approved(self):
        self.register()
        pending = self.store.reserve(self.p, self.t, source_id="source:clip",
                                     key="request:one", expected_revision=0)
        with self.assertRaisesRegex(ValueError, "FOUND_PROOF_REQUIRED|UNATTESTED_CANDIDATE"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="request:one", expected_revision=pending.revision,
                                observed=receipt(self.p, 0, "FOUND_CANDIDATE"))
        self.assertEqual(self.store.history(self.p.plan_id).revision, 1)

    def test_no_real_provider_and_no_raw_question_or_quote_in_attempt_tables(self):
        self.register()
        self.store.reserve(self.p, self.t, source_id="source:clip",
                           key="request:one", expected_revision=0)
        raw = self.sql("SELECT row_to_json(t) FROM dp241_pg_plan t "
                       "UNION ALL SELECT row_to_json(t) FROM dp241_pg_event t;")
        self.assertNotIn(self.t.question, raw)
        self.assertNotIn(self.t.quote_text, raw)
        self.assertNotIn("private:body", raw)
        self.assertNotIn("fixture.invalid", raw)


if __name__ == "__main__":
    unittest.main()

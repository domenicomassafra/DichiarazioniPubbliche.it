"""DP-516: disposable PostgreSQL, canonical Source/Capture/rights checkpoint tests."""

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

from dichiarazioni_pubbliche.historical_batch_checkpoint_pg_v1 import (  # noqa: E402
    IsolatedHistoricalCheckpointPg,
)
from dichiarazioni_pubbliche.historical_batch_gate_v1 import CompletedCapture  # noqa: E402
from tests.test_dp516_historical_batch_gate import plan  # noqa: E402
from tests.test_dp243_historical_corpus_preflight import two  # noqa: E402


def binary(name):
    found = shutil.which(name)
    if not found:
        raise unittest.SkipTest("disposable PostgreSQL binaries missing: " + name)
    return found


def command(args, *, input=None):
    result = subprocess.run(
        args,
        input=input,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout.strip()


class HistoricalCheckpointPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ("initdb", "pg_ctl", "psql"):
            binary(name)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp516-historical-pg-")
        cls.data = Path(cls.tmp.name) / "data"
        cls.running = False
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        try:
            command(
                [
                    binary("initdb"),
                    "-D",
                    str(cls.data),
                    "--username=postgres",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--no-locale",
                ]
            )
            command(
                [
                    binary("pg_ctl"),
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
            command(
                [binary("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", admin],
                input="CREATE DATABASE dp516_disposable;",
            )
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp516_disposable"
            command(
                [binary("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
                input=(ROOT / "db/schema.v1.sql").read_text(),
            )
            cls.store = IsolatedHistoricalCheckpointPg(
                cls.dsn,
                allow_disposable_postgres=True,
            )
            cls.store.install_fixture_schema()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "running", False):
            command(
                [binary("pg_ctl"), "-D", str(cls.data), "-m", "immediate", "-w", "stop"]
            )
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def sql(cls, query):
        return command(
            [binary("psql"), "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
            input=query,
        )

    def setUp(self):
        self.sql("""
SET session_replication_role=replica;
TRUNCATE dp516_pg_version, dp516_pg_batch, private_source_rights_record,
 passage, content_capture, content_item, source, person CASCADE;
SET session_replication_role=origin;
""")
        self.manifests = two()
        self.decision = plan(manifests=self.manifests)
        self.assertEqual(self.decision.status, "PRIVATE_REVIEW_PLAN")
        for m in self.manifests:
            e = m.entries[0]
            self.sql(f"""
INSERT INTO person(id,canonical_name) VALUES('{m.person_id}','Fixture person');
INSERT INTO source(id,canonical_name,source_type,language)
 VALUES('origin:{m.person_id}','Private fixture','WEB','{e.original_language}');
INSERT INTO content_item(id,source_id,canonical_url,rights_status,language)
 VALUES('{e.content_id}','origin:{m.person_id}','{e.locator_url}',
        'CLEARED','{e.original_language}');
INSERT INTO content_capture(
 id,content_id,observed_at,final_url,content_sha256,
 retrieval_method,retrieval_version,rights_status)
 VALUES('capture:{e.content_id}','{e.content_id}','{e.observed_at.isoformat()}',
        '{e.locator_url}','{e.source_version_sha256}','FIXTURE','v1','CLEARED');
INSERT INTO passage(id,content_id,capture_id,selector_type,start_char,end_char,
    text_sha256,language,extraction_method,extraction_version)
 VALUES('{e.exact_locator.passage_id}','{e.content_id}','capture:{e.content_id}',
        'TEXT_POSITION',0,10,'{"d" * 64}','{e.original_language}','FIXTURE','v1');
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,permitted_uses,reviewed_at,expires_at,
 reviewer_ref,policy_version)
 VALUES('{e.rights_record_id}','{e.rights_record.subject_fingerprint}',
        '{e.source_family}','URL','{e.locator_url}','{e.content_id}',
        'CLEARED','fixture-only',ARRAY['FETCH','STORE_BODY','PARSE_TEXT',
        'TRANSLATE'], '2026-10-10T00:00:00Z','2027-10-10T00:00:00Z',
        'fixture:reviewer','{e.rights_policy_version}');
""")

    def one(self, i=0):
        p = self.decision.proposals[i]
        receipt = CompletedCapture(
            p.item_key,
            p.person_id,
            p.content_id,
            p.source_family,
            p.capture_sha256,
            "e" * 64,
        )
        return dict(
            manifests=self.manifests,
            decision=self.decision,
            proposal=p,
            scope_id="history:it-de",
            capture=receipt,
            source_id=f"origin:{p.person_id}",
            capture_id=f"capture:{p.content_id}",
            original_quote_sha256="d" * 64,
            expected_revision=i,
        )

    def test_actual_canonical_pg_two_people_restart_planner_and_no_dispatch(self):
        first = self.store.append(**self.one())
        self.assertEqual(first.checkpoint.revision, 1)
        self.assertFalse(first.dispatch_authorized)
        self.assertFalse(first.pilot_accepted_by_system)
        self.assertFalse(first.publication_authority)
        restarted = IsolatedHistoricalCheckpointPg(
            self.dsn, allow_disposable_postgres=True
        )
        self.assertEqual(restarted.read(self.decision.batch_id), first.checkpoint)
        resumed = plan(
            checkpoint=first.checkpoint, verify_checkpoint=restarted.verify_current
        )
        self.assertEqual(resumed.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(resumed.proposals), 1)
        self.assertFalse(resumed.dispatch_authorized)
        second = restarted.append(**self.one(1))
        self.assertEqual(second.checkpoint.revision, 2)
        self.assertEqual(len(second.checkpoint.completed), 2)
        self.assertNotEqual(
            second.checkpoint.completed[0].person_id,
            second.checkpoint.completed[1].person_id,
        )
        self.assertEqual(self.sql("SELECT count(*) FROM dp516_pg_version;"), "2")

    def test_identical_replay_and_conflicting_receipt_never_overwrite(self):
        first = self.store.append(**self.one())
        duplicate = self.store.append(**self.one())
        self.assertTrue(duplicate.replayed)
        self.assertEqual(duplicate.checkpoint, first.checkpoint)
        wrong = self.one()
        wrong["capture"] = replace(wrong["capture"], persisted_receipt_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            self.store.append(**wrong)
        self.assertEqual(self.sql("SELECT count(*) FROM dp516_pg_version;"), "1")
        with self.assertRaisesRegex(RuntimeError, "APPEND_ONLY"):
            self.sql("DELETE FROM dp516_pg_version;")

    def test_stale_revision_foreign_person_and_manifest_refused(self):
        self.store.append(**self.one())
        bad = self.one(1)
        bad["expected_revision"] = 0
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            self.store.append(**bad)
        foreign = self.one(1)
        foreign["capture"] = replace(
            foreign["capture"], person_id=self.one()["capture"].person_id
        )
        with self.assertRaisesRegex(ValueError, "SOURCE_SCOPE_INVALID"):
            self.store.append(**foreign)
        changed = self.one(1)
        changed["manifests"] = tuple(reversed(self.manifests))
        # Reordered manifests have the same canonical fingerprint.
        self.assertEqual(self.store.append(**changed).checkpoint.revision, 2)
        with self.assertRaisesRegex(ValueError, "MANIFEST_DRIFT"):
            self.store.append(**{**self.one(), "manifests": self.manifests[:1]})

    def test_current_rights_revoke_and_source_version_drift_fail_closed(self):
        completed = self.store.append(**self.one())
        p = self.one()["proposal"]
        self.sql(
            f"UPDATE content_item SET rights_status='REVOKED' WHERE id='{p.content_id}';"
        )
        with self.assertRaisesRegex(ValueError, "LINEAGE_OR_RIGHTS_STALE"):
            self.store.read(self.decision.batch_id)
        self.assertFalse(
            self.store.verify_current(completed.checkpoint, self.decision.batch_id)
        )
        self.sql(
            f"UPDATE content_item SET rights_status='CLEARED' WHERE id='{p.content_id}';"
        )
        self.sql(
            f"UPDATE content_capture SET content_sha256='{'f' * 64}' "
            f"WHERE content_id='{p.content_id}';"
        )
        with self.assertRaisesRegex(ValueError, "LINEAGE_OR_RIGHTS_STALE"):
            self.store.append(**self.one(1))

    def test_append_only_rights_supersession_invalidates_prior_checkpoint(self):
        first = self.store.append(**self.one())
        entry = next(
            e
            for m in self.manifests
            for e in m.entries
            if e.content_id == self.one()["proposal"].content_id
        )
        self.sql(f"""
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,policy_version,supersedes_id)
 VALUES('rights:revoked:{entry.content_id}',
        '{entry.rights_record.subject_fingerprint}',
        '{entry.source_family}','URL','{entry.locator_url}','{entry.content_id}',
        'REVOKED','fixture:revocation','{entry.rights_policy_version}',
        '{entry.rights_record_id}');
""")
        with self.assertRaisesRegex(ValueError, "LINEAGE_OR_RIGHTS_STALE"):
            self.store.append(**self.one())
        with self.assertRaisesRegex(ValueError, "LINEAGE_OR_RIGHTS_STALE"):
            self.store.read(self.decision.batch_id)
        self.assertFalse(
            self.store.verify_current(first.checkpoint, self.decision.batch_id)
        )
        self.assertEqual(self.sql("SELECT count(*) FROM dp516_pg_version;"), "1")

    def test_parallel_live_rights_leaves_make_readback_ambiguous(self):
        first = self.store.append(**self.one())
        entry = next(
            e
            for m in self.manifests
            for e in m.entries
            if e.content_id == self.one()["proposal"].content_id
        )
        self.sql(f"""
INSERT INTO private_source_rights_record(
 id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
 rights_status,rights_receipt_ref,permitted_uses,reviewed_at,
 reviewer_ref,policy_version)
 VALUES('rights:parallel:{entry.content_id}',repeat('f',64),
        '{entry.source_family}','URL','{entry.locator_url}','{entry.content_id}',
        'CLEARED','synthetic:second:rights',ARRAY['FETCH','STORE_BODY','PARSE_TEXT'],
        '2026-10-10T00:00:00Z','fixture:reviewer','{entry.rights_policy_version}');
""")
        with self.assertRaisesRegex(ValueError, "LINEAGE_OR_RIGHTS_STALE"):
            self.store.read(self.decision.batch_id)
        self.assertFalse(
            self.store.verify_current(first.checkpoint, self.decision.batch_id)
        )
        self.assertEqual(self.sql("SELECT count(*) FROM dp516_pg_version;"), "1")

    def test_checkpoint_head_rollback_or_corrupt_history_never_passes_readback(self):
        first = self.store.append(**self.one())
        self.sql(
            f"UPDATE dp516_pg_batch SET revision=0 "
            f"WHERE batch_id='{self.decision.batch_id}';"
        )
        with self.assertRaisesRegex(ValueError, "HISTORY_TAMPERED"):
            self.store.read(self.decision.batch_id)
        self.assertFalse(
            self.store.verify_current(first.checkpoint, self.decision.batch_id)
        )
        self.assertEqual(self.sql("SELECT count(*) FROM dp516_pg_version;"), "1")

    def test_original_vs_translated_italian_quote_are_separately_pinned(self):
        german = next(
            i
            for i, p in enumerate(self.decision.proposals)
            if p.original_language == "de"
        )
        row = self.one(german)
        row["expected_revision"] = 0
        with self.assertRaisesRegex(ValueError, "TRANSLATION_SEPARATION_REQUIRED"):
            self.store.append(
                **{
                    **row,
                    "translated_quote_sha256": "d" * 64,
                    "translation_language": "it",
                    "translation_method": "fixture:reviewer",
                }
            )
        with self.assertRaisesRegex(ValueError, "TRANSLATION_SEPARATION_REQUIRED"):
            self.store.append(**{**row, "translated_quote_sha256": "f" * 64})
        valid = {
            **row,
            "translated_quote_sha256": "f" * 64,
            "translation_language": "it",
            "translation_method": "fixture:reviewer",
        }
        receipt = self.store.append(**valid)
        self.assertEqual(receipt.checkpoint.revision, 1)
        self.assertEqual(
            self.sql(
                "SELECT quote_sha||':'||translation_sha||':'||original_language"
                "||':'||translation_language FROM dp516_pg_version;"
            ),
            "d" * 64 + ":" + "f" * 64 + ":de:it",
        )
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            self.store.append(**{**valid, "translated_quote_sha256": "a" * 64})

    def test_parallel_writers_one_cas_winner_and_stale_retry_rejected(self):
        self.store.append(**self.one())
        other = self.one(1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(self.store.append, **other) for _ in range(2)]
            results = [job.result() for job in jobs]
        self.assertEqual([row.checkpoint.revision for row in results], [2, 2])
        self.assertEqual(sum(not row.replayed for row in results), 1)
        self.assertEqual(self.sql("SELECT count(*) FROM dp516_pg_version;"), "2")

    def test_no_source_license_pilot_or_full_coverage_inferred(self):
        with self.assertRaisesRegex(ValueError, "DISPOSABLE_ONLY"):
            IsolatedHistoricalCheckpointPg(
                self.dsn.replace("dp516_disposable", "postgres"),
                allow_disposable_postgres=True,
            )
        with self.assertRaisesRegex(ValueError, "PRIVATE_PLAN_REQUIRED"):
            denied = replace(self.decision, status="HELD", proposals=())
            self.store.append(**{**self.one(), "decision": denied})
        self.assertIsNone(self.store.read(self.decision.batch_id))


if __name__ == "__main__":
    unittest.main()

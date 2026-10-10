"""Real SQL negative acceptance for private DP-209→215 provenance/readiness.

Disposable localhost PostgreSQL only. The synthetic fixture lives in its own
schema; this test never contacts the runtime MiniPC or an external source.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.private_pipeline_reconciliation import (  # noqa: E402
    PrivatePipelineReconciliationStore,
)


class PrivatePipelineReconciliationPostgresTests(unittest.TestCase):
    """The actual read-only SQL query, not a mock of database row materialization."""

    SCHEMA = "dp_chain_accept_local"

    @classmethod
    def _command(cls, args: list[str], *, input_text: str | None = None,
                 scoped: bool = False) -> str:
        environment = os.environ.copy()
        if scoped:
            environment["PGOPTIONS"] = f"-c search_path={cls.SCHEMA},public"
        else:
            environment.pop("PGOPTIONS", None)
        result = subprocess.run(
            args, text=True, capture_output=True, input=input_text,
            env=environment, check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr[-2500:])
        return result.stdout.strip()

    @classmethod
    def _sql(cls, statement: str, *, scoped: bool = True) -> str:
        return cls._command(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "--dbname", cls.url],
            input_text=statement, scoped=scoped,
        )

    @classmethod
    def setUpClass(cls) -> None:
        required = ("initdb", "pg_ctl", "psql")
        if any(not shutil.which(command) for command in required):
            raise unittest.SkipTest("isolated local PostgreSQL unavailable")
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp214-215-pg-")
        cls.data = Path(cls.tmp.name) / "pgdata"
        cls.started = False
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        try:
            cls._command([
                "initdb", "-D", str(cls.data), "--username=postgres",
                "--auth=trust", "--encoding=UTF8", "--no-locale",
            ])
            cls._command([
                "pg_ctl", "-D", str(cls.data), "-l", str(Path(cls.tmp.name) / "postgres.log"),
                "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.tmp.name}", "-w", "start",
            ])
            cls.started = True
            cls._sql((ROOT / "db/schema.v1.sql").read_text(encoding="utf-8"), scoped=False)
            cls._sql(f"CREATE SCHEMA {cls.SCHEMA}", scoped=False)
            cls._sql((ROOT / "tests/fixtures/private_pipeline_reconciliation.sql").read_text(encoding="utf-8"))
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "started", False):
            cls._command(["pg_ctl", "-D", str(cls.data), "-m", "fast", "-w", "stop"])
            cls.started = False
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def setUp(self) -> None:
        self._sql("""
            UPDATE research_discovery_manifest SET status='ACTIVE';
            UPDATE research_discovery_run SET status='COMPLETED', manifest_sha256=repeat('d',64);
            UPDATE research_discovery_attempt SET status='HEALTHY', adapter_id='synthetic-adapter';
            UPDATE research_discovery_hit SET source_id=CASE
               WHEN content_id='synthetic:content-2' THEN 'synthetic:source-2'
               ELSE 'synthetic:source-1' END;
            UPDATE statement_candidate SET status='CANDIDATE';
            UPDATE private_source_rights_record SET rights_status='CLEARED', reviewed_at=now()-interval '1 hour';
        """)

    def _read(self) -> dict:
        # PsqlRuntime subprocess inherits exactly the disposable schema scope.
        with patch.dict(os.environ, {"PGOPTIONS": f"-c search_path={self.SCHEMA},public"}):
            return PrivatePipelineReconciliationStore(database_url=self.url).read_collection(
                collection_id="synthetic:collection", limit=3,
            )

    def _first(self) -> dict:
        return next(item for item in self._read()["items"]
                    if item["content_id"] == "synthetic:content-1")

    def test_valid_private_chain_still_requires_human_review(self):
        item = self._first()
        self.assertTrue(item["private_review_queue_eligible"])
        self.assertEqual(item["state"], "REVIEW_READY_PRIVATE_NOT_APPROVED")
        self.assertFalse(item["publication_authority"])
        self.assertEqual(item["discovery_count"], 1)

    def test_failed_attempt_and_superseded_manifest_revoke_discovery_and_rights_family(self):
        for table, mutation in (
            ("attempt", "UPDATE research_discovery_attempt SET status='FAILED'"),
            ("manifest", "UPDATE research_discovery_manifest SET status='SUPERSEDED'"),
            ("run_digest", "UPDATE research_discovery_run SET manifest_sha256=repeat('e',64)"),
            ("adapter", "UPDATE research_discovery_attempt SET adapter_id='wrong-adapter'"),
            ("wrong_source", "UPDATE research_discovery_hit SET source_id='synthetic:source-2' WHERE content_id='synthetic:content-1'"),
        ):
            with self.subTest(table=table):
                self._sql(mutation)
                result = self._first()
                self.assertFalse(result["private_review_queue_eligible"])
                self.assertEqual(result["discovery_count"], 0)
                self.assertIn("DISCOVERY_PROVENANCE_NOT_PERSISTED", result["blockers"])
                self.assertIn("RIGHTS_HOLD_CURRENT_GRANT_MISSING", result["blockers"])
                self.setUp()

    def test_rejected_statement_blocks_candidate_private_review(self):
        self._sql("UPDATE statement_candidate SET status='REJECTED' WHERE id='synthetic:statement-1'")
        result = self._first()
        self.assertFalse(result["private_review_queue_eligible"])
        self.assertIn("STATEMENT_NOT_PENDING_REVIEW", result["blockers"])

    def test_future_dated_rights_review_does_not_authorize_private_chain(self):
        self._sql("UPDATE private_source_rights_record SET reviewed_at=now()+interval '1 day'")
        result = self._first()
        self.assertFalse(result["private_review_queue_eligible"])
        self.assertIn("RIGHTS_HOLD_CURRENT_GRANT_MISSING", result["blockers"])


if __name__ == "__main__":
    unittest.main()

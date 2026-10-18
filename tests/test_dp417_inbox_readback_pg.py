"""Real isolated PostgreSQL regression for DP-417 readback lineage drift.

No MiniPC writes: reuse the ephemeral, full-schema PG fixture and tear it down.
"""

import json
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.dp417_inbox_readback import READBACK_SQL

SCHEMA = Path(__file__).resolve().parents[1] / "db/schema.v1.sql"


class Dp417ReadbackPostgresTests(unittest.TestCase):
    @classmethod
    def sql(cls, statement):
        return subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "--dbname", cls.url],
            input=statement, text=True, capture_output=True, check=False,
        )

    @classmethod
    def require_sql(cls, statement):
        result = cls.sql(statement)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    @classmethod
    def setUpClass(cls):
        missing = [cmd for cmd in ("initdb", "pg_ctl", "psql") if not shutil.which(cmd)]
        if missing:
            raise unittest.SkipTest("isolated PostgreSQL unavailable")
        cls.tmp = tempfile.TemporaryDirectory(prefix="qa-dp417-readback-")
        cls.data_dir = Path(cls.tmp.name) / "pgdata"
        cls.started = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            init = subprocess.run(
                ["initdb", "-D", str(cls.data_dir), "--username=postgres",
                 "--auth=trust", "--encoding=UTF8", "--no-locale"],
                text=True, capture_output=True, check=False,
            )
            if init.returncode:
                raise AssertionError(init.stderr)
            startup = subprocess.run(
                ["pg_ctl", "-D", str(cls.data_dir),
                 "-l", str(Path(cls.tmp.name) / "postgres.log"),
                 "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.tmp.name}",
                 "-w", "start"], text=True, capture_output=True, check=False,
            )
            if startup.returncode:
                raise AssertionError(startup.stderr)
            cls.started = True
            cls.url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            cls.require_sql(SCHEMA.read_text())
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            subprocess.run(
                ["pg_ctl", "-D", str(cls.data_dir), "-m", "fast", "-w", "stop"],
                capture_output=True, check=False,
            )
            cls.started = False
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_readback_detects_triage_scope_drift_after_hit_reparenting(self):
        """A later FK-valid Hit update cannot erase a prior Collection annotation."""
        prefix = "qa-readback:" + self._testMethodName
        self.require_sql(
            f"""
            INSERT INTO research_collection (id,slug,name,scope_text,policy_version)
            VALUES ('{prefix}:c1','{prefix}:slug1','C1','private','v1'),
                   ('{prefix}:c2','{prefix}:slug2','C2','private','v1');
            INSERT INTO research_discovery_manifest
              (id,collection_id,manifest_sha256,max_results,max_results_per_host,cost_cap_usd)
            VALUES ('{prefix}:m1','{prefix}:c1',repeat('a',64),10,5,0),
                   ('{prefix}:m2','{prefix}:c2',repeat('b',64),10,5,0);
            INSERT INTO research_discovery_query
              (id,manifest_id,ordinal,query_text,source_families,adapter_ids,max_results)
            VALUES ('{prefix}:q1','{prefix}:m1',0,'test','[]','[]',10),
                   ('{prefix}:q2','{prefix}:m2',0,'test','[]','[]',10);
            INSERT INTO research_discovery_run (id,manifest_id,manifest_sha256,status)
            VALUES ('{prefix}:r1','{prefix}:m1',repeat('a',64),'COMPLETED'),
                   ('{prefix}:r2','{prefix}:m2',repeat('b',64),'COMPLETED');
            INSERT INTO research_discovery_attempt
              (id,run_id,query_id,adapter_id,adapter_version,status)
            VALUES ('{prefix}:a1','{prefix}:r1','{prefix}:q1','test','v1','HEALTHY'),
                   ('{prefix}:a2','{prefix}:r2','{prefix}:q2','test','v1','HEALTHY');
            INSERT INTO research_discovery_hit
              (id,run_id,attempt_id,query_id,hit_key,ordinal,canonical_url,source_host,
               source_family,disposition)
            VALUES ('{prefix}:hit','{prefix}:r1','{prefix}:a1','{prefix}:q1',
                    repeat('c',64),0,'https://example.test/item','example.test',
                    'OFFICIAL','NEW_CONTENT');
            INSERT INTO research_discovery_triage_decision
              (collection_id,hit_id,revision,expected_revision,request_key,decision,
               payload_sha256,actor_ref)
            VALUES ('{prefix}:c1','{prefix}:hit',1,0,'{prefix}:request',
                    'NEEDS_REVIEW',repeat('d',64),'reviewer:qa');
            """,
        )
        original = json.loads(self.require_sql(READBACK_SQL))
        self.require_sql(
            "UPDATE research_discovery_hit SET "
            f"run_id='{prefix}:r2',attempt_id='{prefix}:a2',query_id='{prefix}:q2' "
            f"WHERE id='{prefix}:hit';",
        )
        drifted = json.loads(self.require_sql(READBACK_SQL))
        self.assertEqual(drifted["invalid_lineage_hits"],
                         original["invalid_lineage_hits"] + 1)
        self.assertEqual(drifted["hits"], original["hits"])

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class OriginalSourcePostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    database_url: str
    store: QueueRuntimeStore
    server_started = False

    @classmethod
    def _run_command(cls, args, *, input_text=None):
        proc = subprocess.run(
            args,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(
                f"command failed ({proc.returncode}): {' '.join(args)}\n{detail}"
            )
        return proc.stdout

    @classmethod
    def setUpClass(cls):
        tools = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in tools.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp225-original-source-")
        root = Path(cls.postgres_tmp.name)
        cls.data_dir = root / "data"
        cls.port = _free_tcp_port()
        try:
            cls._run_command(
                [
                    tools["initdb"] or "initdb",
                    "-D",
                    str(cls.data_dir),
                    "--username=postgres",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--no-locale",
                ]
            )
            cls._run_command(
                [
                    tools["pg_ctl"] or "pg_ctl",
                    "-D",
                    str(cls.data_dir),
                    "-l",
                    str(root / "postgres.log"),
                    "-o",
                    f"-F -p {cls.port} -h 127.0.0.1 -k {root}",
                    "-w",
                    "start",
                ]
            )
            cls.server_started = True
            admin_url = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            cls._run_command(
                [
                    tools["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    admin_url,
                    "-c",
                    "CREATE DATABASE dp225_original_source;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp225_original_source"
            )
            cls._run_command(
                [
                    tools["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.database_url,
                    "-f",
                    str(ROOT / "db" / "schema.v1.sql"),
                ]
            )
            cls._run_command(
                [
                    tools["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.database_url,
                    "-c",
                    """
                    INSERT INTO research_collection(id,slug,name,scope_text,policy_version)
                    VALUES ('collection:dp225','dp225','DP-225 canary','Synthetic isolated canary','test-v1');
                    INSERT INTO content_item(id,canonical_url) VALUES
                      ('content:root','https://example.test/root'),
                      ('content:copy','https://example.test/copy'),
                      ('content:leaf','https://example.test/leaf');
                    INSERT INTO content_derivation_family(id,root_content_id,status)
                    VALUES ('family:dp225','content:root','APPROVED');
                    INSERT INTO content_derivation_candidate(
                      id,family_id,derived_content_id,origin_content_id,relation_type,
                      derivation_method,status
                    ) VALUES
                      ('edge:copy-root','family:dp225','content:copy','content:root',
                       'REPUBLICATION','MANUAL_REVIEW','APPROVED'),
                      ('edge:leaf-copy','family:dp225','content:leaf','content:copy',
                       'SYNDICATION','MANUAL_REVIEW','APPROVED');
                    INSERT INTO coverage_need(
                      id,collection_id,need_type,requirement_kind,requirement_fingerprint,
                      question,status,max_attempts
                    ) VALUES (
                      'coverage:dp225','collection:dp225','PRIMARY_SOURCE','ROLE_ANY',
                      repeat('a',64),'Find the reviewed original source.','OPEN',3
                    );
                    """,
                ]
            )
            cls.store = QueueRuntimeStore(cls.database_url)
        except Exception:
            if cls.server_started:
                subprocess.run(
                    [
                        tools["pg_ctl"] or "pg_ctl",
                        "-D",
                        str(cls.data_dir),
                        "-m",
                        "fast",
                        "-w",
                        "stop",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                cls.server_started = False
            cls.postgres_tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.server_started:
            cls._run_command(
                [
                    shutil.which("pg_ctl") or "pg_ctl",
                    "-D",
                    str(cls.data_dir),
                    "-m",
                    "fast",
                    "-w",
                    "stop",
                ]
            )
            cls.server_started = False
        cls.postgres_tmp.cleanup()

    def test_database_backed_reviewed_derivation_resolves_and_only_root_satisfies(self):
        leaf = self.store.coverage_need_original_source_preflight(
            coverage_need_id="coverage:dp225",
            content_id="content:leaf",
        )
        self.assertFalse(leaf["accepted"])
        self.assertEqual(leaf["root_content_id"], "content:root")
        self.assertEqual(
            leaf["path_content_ids"],
            ["content:leaf", "content:copy", "content:root"],
        )
        self.assertEqual(
            leaf["path_edge_ids"],
            ["edge:leaf-copy", "edge:copy-root"],
        )
        with self.assertRaisesRegex(ValueError, "DERIVED_CONTENT_NOT_ORIGINAL_ROOT"):
            self.store.satisfy_coverage_need(
                coverage_need_id="coverage:dp225",
                event_id="coverage-event:dp225:derived",
                content_id="content:leaf",
            )

        root = self.store.coverage_need_original_source_preflight(
            coverage_need_id="coverage:dp225",
            content_id="content:root",
        )
        self.assertTrue(root["accepted"])
        self.assertEqual(root["root_content_id"], "content:root")
        self.assertEqual(root["path_content_ids"], ["content:root"])
        self.assertEqual(root["path_edge_ids"], [])
        self.assertEqual(
            self.store.satisfy_coverage_need(
                coverage_need_id="coverage:dp225",
                event_id="coverage-event:dp225:root",
                content_id="content:root",
            ),
            "SATISFIED",
        )

        raw = self.store.run(
            "SELECT json_build_object('status',status,'content',satisfied_by_content_id,"
            "'metadata',metadata)::text FROM coverage_need WHERE id='coverage:dp225';"
        )
        persisted = json.loads(raw)
        self.assertEqual(persisted["status"], "SATISFIED")
        self.assertEqual(persisted["content"], "content:root")
        receipt = persisted["metadata"]["original_source_resolution"]
        self.assertEqual(receipt["root_content_id"], "content:root")
        self.assertEqual(receipt["path_content_ids"], ["content:root"])
        self.assertEqual(receipt["path_edge_ids"], [])


if __name__ == "__main__":
    unittest.main()

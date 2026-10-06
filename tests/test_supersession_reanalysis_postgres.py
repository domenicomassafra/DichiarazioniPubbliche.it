import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402
from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    SourceSnapshot,
    evaluate_reobservation,
)
from dichiarazioni_pubbliche.supersession_reanalysis import (  # noqa: E402
    SupersessionReanalysisError,
)
from dichiarazioni_pubbliche.supersession_reanalysis_runtime import (  # noqa: E402
    consume_reviewed_supersession_reanalysis,
)


SHA_A = hashlib.sha256(b"law version 1").hexdigest()
SHA_B = hashlib.sha256(b"law version 2").hexdigest()
NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _snapshots() -> tuple[SourceSnapshot, SourceSnapshot]:
    previous = SourceSnapshot(
        source_id="source:official:law:1",
        observed_at=NOW,
        availability="AVAILABLE",
        content_sha256=SHA_A,
        source_version="law-v1",
        etag='"law-v1"',
        canonical_url="https://example.test/law/1",
        rights_status="CLEARED",
    )
    current = replace(
        previous,
        observed_at=NOW.replace(hour=21),
        content_sha256=SHA_B,
        source_version="law-v2",
        supersedes_version="law-v1",
        etag='"law-v2"',
    )
    return previous, current


class SupersessionReanalysisPostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    database_url: str
    port: int
    store: PsqlRuntime
    server_started = False

    @classmethod
    def _run_command(cls, args: list[str], *, input_text: str | None = None) -> str:
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
    def setUpClass(cls) -> None:
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )

        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp227-postgres-")
        root = Path(cls.postgres_tmp.name)
        cls.data_dir = root / "data"
        cls.port = _free_tcp_port()
        try:
            cls._run_command(
                [
                    required["initdb"] or "initdb",
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
                    required["pg_ctl"] or "pg_ctl",
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
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    admin_url,
                    "-c",
                    "CREATE DATABASE dp227_supersession;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp227_supersession"
            )
            cls._run_command(
                [
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.database_url,
                    "-f",
                    str(ROOT / "db" / "schema.v1.sql"),
                ]
            )
            cls.store = PsqlRuntime(cls.database_url)
        except Exception:
            if cls.server_started:
                subprocess.run(
                    [
                        required["pg_ctl"] or "pg_ctl",
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
    def tearDownClass(cls) -> None:
        pg_ctl = shutil.which("pg_ctl") or "pg_ctl"
        if cls.server_started:
            cls._run_command(
                [
                    pg_ctl,
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

    def setUp(self) -> None:
        self.store.run(
            """
            DELETE FROM processing_job;
            DELETE FROM reanalysis_trigger;
            DELETE FROM finding;
            DELETE FROM atomic_claim;
            DELETE FROM content_item;

            INSERT INTO content_item (id, canonical_url, title)
            VALUES ('content:dp227', 'https://example.test/dp227', 'DP-227 fixture');

            INSERT INTO atomic_claim (
                id, content_id, normalized_claim, claim_type, temporal_scope
            ) VALUES
                ('claim:a', 'content:dp227', 'Version A applies.',
                 'LEGAL_POLICY_STATUS', '{"statement_date":"2026-09-01"}'::jsonb),
                ('claim:b', 'content:dp227', 'Version B applies.',
                 'LEGAL_POLICY_STATUS', '{"statement_date":"2026-09-02"}'::jsonb),
                ('claim:other', 'content:dp227', 'Unrelated claim.',
                 'LEGAL_POLICY_STATUS', '{"statement_date":"2026-09-03"}'::jsonb);

            INSERT INTO finding (
                id, claim_id, assessment, rationale, publication_status, policy_version
            ) VALUES
                ('finding:1', 'claim:a', 'SUPPORTED', 'A rationale.', 'PUBLISH', 'policy-v1'),
                ('finding:2', 'claim:b', 'SUPPORTED', 'B rationale.', 'DISPUTED', 'policy-v1'),
                ('finding:other', 'claim:other', 'SUPPORTED', 'Other rationale.',
                 'CORRECTED', 'policy-v1');
            """
        )

    def _consume(self, **overrides):
        previous, current = _snapshots()
        decision = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 5),
            load_bearing_for_evidence=True,
        )
        values = {
            "decision": decision,
            "previous": previous,
            "current": current,
            "review_event_id": "review:supersession:law-v1:law-v2",
            "review_action": "APPROVED",
            "reviewed_entity_ref": decision.event_key,
            "previous_valid_from": "2024-01-01",
            "previous_valid_until": "2026-10-01",
            "current_valid_from": "2026-10-01",
            "current_valid_until": None,
            "affected_claim_ids": ("claim:b", "claim:a", "claim:a"),
            "affected_finding_ids": ("finding:2", "finding:1", "finding:1"),
        }
        values.update(overrides)
        return consume_reviewed_supersession_reanalysis(self.store, **values)

    def test_reviewed_supersession_persists_one_trigger_and_job_per_claim_idempotently(self):
        publication_before = self.store.run(
            "SELECT json_object_agg(id, publication_status ORDER BY id)::text FROM finding;"
        )

        first = self._consume()
        second = self._consume()

        self.assertEqual(first, second)
        self.assertEqual(first.affected_claim_ids, ("claim:a", "claim:b"))
        self.assertEqual(first.affected_finding_ids, ("finding:1", "finding:2"))
        self.assertEqual(first.reviewed_entity_ref, first.decision_event_key)
        self.assertEqual(first.persisted_trigger_count, 2)
        self.assertEqual(first.persisted_job_count, 2)

        persisted = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                    'trigger_count', (SELECT count(*) FROM reanalysis_trigger),
                    'job_count', (
                        SELECT count(*) FROM processing_job
                        WHERE job_type = 'REANALYZE_CLAIM'
                    ),
                    'triggers', (
                        SELECT json_agg(json_build_object(
                            'id', id,
                            'claim_id', claim_id,
                            'source_id', source_id,
                            'status', status,
                            'enqueued_job_id', enqueued_job_id,
                            'metadata', metadata
                        ) ORDER BY claim_id)
                        FROM reanalysis_trigger
                    ),
                    'jobs', (
                        SELECT json_agg(json_build_object(
                            'id', id,
                            'content_id', content_id,
                            'state', state,
                            'payload', payload
                        ) ORDER BY payload->>'claim_id')
                        FROM processing_job
                        WHERE job_type = 'REANALYZE_CLAIM'
                    )
                )::text;
                """
            )
        )
        self.assertEqual(persisted["trigger_count"], 2)
        self.assertEqual(persisted["job_count"], 2)

        for trigger in persisted["triggers"]:
            self.assertEqual(trigger["source_id"], first.request_id)
            self.assertEqual(trigger["status"], "ENQUEUED")
            self.assertEqual(
                trigger["metadata"]["reviewed_entity_ref"], first.decision_event_key
            )
            self.assertEqual(
                trigger["metadata"]["decision_event_key"], first.decision_event_key
            )
            self.assertEqual(
                trigger["metadata"]["affected_finding_ids"],
                ["finding:1", "finding:2"],
            )
            self.assertIn(trigger["enqueued_job_id"], first.reanalysis_job_ids)

        for job in persisted["jobs"]:
            self.assertEqual(job["content_id"], "content:dp227")
            self.assertEqual(job["state"], "QUEUED")
            self.assertEqual(job["payload"]["request_id"], first.request_id)
            self.assertEqual(
                job["payload"]["reviewed_entity_ref"], first.decision_event_key
            )
            self.assertEqual(
                job["payload"]["decision_event_key"], first.decision_event_key
            )
            self.assertEqual(
                job["payload"]["affected_finding_ids"],
                ["finding:1", "finding:2"],
            )

        publication_after = self.store.run(
            "SELECT json_object_agg(id, publication_status ORDER BY id)::text FROM finding;"
        )
        self.assertEqual(publication_before, publication_after)

    def test_review_target_mismatch_fails_before_persistence(self):
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "REVIEW_TARGET_MISMATCH",
        ):
            self._consume(reviewed_entity_ref="0" * 64)

        self.assertEqual(self.store.run("SELECT count(*)::text FROM reanalysis_trigger;"), "0")
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM processing_job WHERE job_type='REANALYZE_CLAIM';"
            ),
            "0",
        )

    def test_unrelated_finding_binding_rolls_back_entire_request(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "DP227_SUPERSESSION_REANALYSIS_RUNTIME_CONFLICT",
        ):
            self._consume(affected_finding_ids=("finding:1", "finding:other"))

        self.assertEqual(self.store.run("SELECT count(*)::text FROM reanalysis_trigger;"), "0")
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM processing_job WHERE job_type='REANALYZE_CLAIM';"
            ),
            "0",
        )


if __name__ == "__main__":
    unittest.main()

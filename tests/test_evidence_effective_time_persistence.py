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
from dichiarazioni_pubbliche.source_intelligence import (  # noqa: E402
    assess_evidence_set,
    evidence_item_from_row,
    load_source_intelligence_contract,
)


MIGRATION = ROOT / "db" / "migrations" / "20261007-add-evidence-effective-time-state.sql"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pg_bin(name: str) -> str:
    direct = shutil.which(name)
    if direct:
        return direct
    pg_config = shutil.which("pg_config")
    if pg_config:
        bindir = subprocess.run(
            [pg_config, "--bindir"], text=True, capture_output=True, check=True
        ).stdout.strip()
        candidate = Path(bindir) / name
        if candidate.is_file():
            return str(candidate)
    raise unittest.SkipTest(f"PostgreSQL tool unavailable: {name}")


def _run(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{detail}"
        )
    return result.stdout


class EvidenceEffectiveTimePersistencePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for name in ("initdb", "pg_ctl", "psql"):
            _pg_bin(name)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp227-evidence-effective-time-")
        cls.root = Path(cls.tmp.name)
        cls.data_dir = cls.root / "data"
        cls.port = _free_port()
        cls.pg_ctl = _pg_bin("pg_ctl")
        _run(
            [
                _pg_bin("initdb"),
                "-D",
                str(cls.data_dir),
                "--username=postgres",
                "--auth=trust",
                "--encoding=UTF8",
                "--no-locale",
            ]
        )
        _run(
            [
                cls.pg_ctl,
                "-D",
                str(cls.data_dir),
                "-l",
                str(cls.root / "postgres.log"),
                "-o",
                f"-F -p {cls.port} -h 127.0.0.1 -k {cls.root}",
                "-w",
                "start",
            ]
        )
        cls.admin_url = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
        for database in ("fresh", "legacy"):
            _run(
                [
                    _pg_bin("psql"),
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.admin_url,
                    "-c",
                    f"CREATE DATABASE {database};",
                ]
            )
        cls.fresh_url = f"postgresql://postgres@127.0.0.1:{cls.port}/fresh"
        cls.legacy_url = f"postgresql://postgres@127.0.0.1:{cls.port}/legacy"

        _run(
            [
                _pg_bin("psql"),
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                cls.fresh_url,
                "-f",
                str(ROOT / "db" / "schema.v1.sql"),
            ]
        )
        legacy_schema = """
        CREATE TABLE evidence (
            id text PRIMARY KEY,
            canonical_url text NOT NULL,
            publisher text,
            source_type text NOT NULL,
            publication_date date,
            fetched_at timestamptz,
            observed_at timestamptz NOT NULL DEFAULT now(),
            content_sha256 text,
            excerpt text,
            reference_period text,
            independence_group text,
            rights_status text NOT NULL DEFAULT 'UNKNOWN',
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        INSERT INTO evidence(id, canonical_url, source_type)
        VALUES ('evidence:legacy', 'https://example.test/legacy', 'PRIMARY_OFFICIAL');
        """
        _run(
            [
                _pg_bin("psql"),
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                cls.legacy_url,
            ],
            input_text=legacy_schema,
        )
        for database_url in (cls.fresh_url, cls.legacy_url):
            for _ in range(2):
                _run(
                    [
                        _pg_bin("psql"),
                        "-X",
                        "-v",
                        "ON_ERROR_STOP=1",
                        "--dbname",
                        database_url,
                        "-f",
                        str(MIGRATION),
                    ]
                )
        cls.store = QueueRuntimeStore(cls.fresh_url)

    @classmethod
    def tearDownClass(cls) -> None:
        _run([cls.pg_ctl, "-D", str(cls.data_dir), "-m", "fast", "-w", "stop"])
        cls.tmp.cleanup()

    @classmethod
    def _shape(cls, database_url: str) -> dict[str, object]:
        query = """
        SELECT json_build_object(
          'columns', (
            SELECT json_agg(json_build_object(
              'name', column_name,
              'type', data_type,
              'nullable', is_nullable,
              'default', column_default
            ) ORDER BY column_name)
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='evidence'
              AND column_name IN ('valid_from','valid_until','record_status')
          ),
          'constraints', (
            SELECT json_agg(json_build_object(
              'name', conname,
              'definition', pg_get_constraintdef(oid)
            ) ORDER BY conname)
            FROM pg_constraint
            WHERE conrelid='public.evidence'::regclass
              AND conname IN (
                'evidence_effective_interval_check',
                'evidence_record_status_check'
              )
          )
        )::text;
        """
        raw = _run(
            [
                _pg_bin("psql"),
                "-X",
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                database_url,
                "-c",
                query,
            ]
        ).strip()
        return json.loads(raw)

    def test_fresh_schema_and_replayed_migration_have_identical_contract(self) -> None:
        self.assertEqual(self._shape(self.fresh_url), self._shape(self.legacy_url))
        migrated = _run(
            [
                _pg_bin("psql"),
                "-X",
                "-At",
                "--dbname",
                self.legacy_url,
                "-c",
                "SELECT valid_from::text,valid_until::text,record_status FROM evidence WHERE id='evidence:legacy';",
            ]
        ).strip()
        self.assertEqual(migrated, "||ACTIVE")

    def test_upsert_preserves_unknown_dates_and_stale_state_is_monotonic(self) -> None:
        self.store.upsert_evidence(
            evidence_id="evidence:dp227:unknown-dates",
            canonical_url="https://example.test/dp227/unknown-dates",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            fetched_at="2026-10-07T09:00:00+00:00",
            content_sha256="0" * 64,
        )
        unknown_dates = self.store.run(
            """
            SELECT COALESCE(valid_from::text,'NULL') || '|' ||
                   COALESCE(valid_until::text,'NULL') || '|' || record_status
            FROM evidence WHERE id='evidence:dp227:unknown-dates';
            """
        )
        self.assertEqual(unknown_dates, "NULL|NULL|ACTIVE")

        created = self.store.upsert_evidence(
            evidence_id="evidence:dp227:persisted",
            canonical_url="https://example.test/dp227/persisted",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            valid_from="2026-01-01",
            valid_until=None,
            record_status="SUPERSEDED",
            fetched_at="2026-10-07T10:00:00+00:00",
            content_sha256="a" * 64,
            reference_period="2026-07",
            independence_group="istat-sdmx:2026",
            metadata={"evidence_source_id": "istat-sdmx", "authoritative": True},
        )
        self.assertTrue(created)

        self.store.upsert_evidence(
            evidence_id="evidence:dp227:persisted",
            canonical_url="https://example.test/dp227/persisted",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            fetched_at="2026-10-07T11:00:00+00:00",
            content_sha256="a" * 64,
            reference_period="2026-07",
            independence_group="istat-sdmx:2026",
            metadata={"reobserved": True},
        )
        first = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                  'valid_from',valid_from::text,
                  'valid_until',valid_until::text,
                  'record_status',record_status
                )::text FROM evidence WHERE id='evidence:dp227:persisted';
                """
            )
        )
        self.assertEqual(
            first,
            {
                "valid_from": "2026-01-01",
                "valid_until": None,
                "record_status": "SUPERSEDED",
            },
        )

        self.store.upsert_evidence(
            evidence_id="evidence:dp227:persisted",
            canonical_url="https://example.test/dp227/persisted",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            valid_until="2026-10-01",
            record_status="RETIRED",
            fetched_at="2026-10-07T12:00:00+00:00",
            content_sha256="a" * 64,
            reference_period="2026-07",
            independence_group="istat-sdmx:2026",
        )
        second = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                  'valid_from',valid_from::text,
                  'valid_until',valid_until::text,
                  'record_status',record_status
                )::text FROM evidence WHERE id='evidence:dp227:persisted';
                """
            )
        )
        self.assertEqual(
            second,
            {
                "valid_from": "2026-01-01",
                "valid_until": "2026-10-01",
                "record_status": "RETIRED",
            },
        )

        self.store.upsert_evidence(
            evidence_id="evidence:dp227:persisted",
            canonical_url="https://example.test/dp227/persisted",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            valid_from="2026-01-01",
            valid_until="2026-10-01",
            record_status="ACTIVE",
            fetched_at="2026-10-07T12:30:00+00:00",
            content_sha256="a" * 64,
        )
        after_downgrade_attempt = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                  'valid_from',valid_from::text,
                  'valid_until',valid_until::text,
                  'record_status',record_status
                )::text FROM evidence WHERE id='evidence:dp227:persisted';
                """
            )
        )
        self.assertEqual(after_downgrade_attempt, second)

        with self.assertRaisesRegex(ValueError, "record_status"):
            self.store.upsert_evidence(
                evidence_id="evidence:dp227:bad-status",
                canonical_url="https://example.test/dp227/bad-status",
                publisher="Synthetic Authority",
                source_type="PRIMARY_OFFICIAL",
                record_status="UNKNOWN",
                fetched_at="2026-10-07T12:00:00+00:00",
                content_sha256="b" * 64,
            )

        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_EFFECTIVE_TIME_CONFLICT"):
            self.store.upsert_evidence(
                evidence_id="evidence:dp227:persisted",
                canonical_url="https://example.test/dp227/persisted",
                publisher="Synthetic Authority",
                source_type="PRIMARY_OFFICIAL",
                publication_date="2026-09-01",
                valid_from="2025-12-31",
                fetched_at="2026-10-07T13:00:00+00:00",
                content_sha256="a" * 64,
            )
        after_conflict = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                  'valid_from',valid_from::text,
                  'valid_until',valid_until::text,
                  'record_status',record_status
                )::text FROM evidence WHERE id='evidence:dp227:persisted';
                """
            )
        )
        self.assertEqual(after_conflict, second)

        for field, kwargs in (
            ("EVIDENCE_VALID_FROM", {"valid_from": "2026-1-1"}),
            ("EVIDENCE_VALID_UNTIL", {"valid_until": "not-a-date"}),
            (
                "EVIDENCE_EFFECTIVE_INTERVAL_INVALID",
                {"valid_from": "2026-10-01", "valid_until": "2026-10-01"},
            ),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    self.store.upsert_evidence(
                        evidence_id=f"evidence:dp227:{field.lower()}",
                        canonical_url="https://example.test/dp227/invalid-date",
                        publisher="Synthetic Authority",
                        source_type="PRIMARY_OFFICIAL",
                        fetched_at="2026-10-07T12:00:00+00:00",
                        content_sha256="d" * 64,
                        **kwargs,
                    )

    def test_persisted_superseded_without_end_fails_temporal_cutoff(self) -> None:
        self.store.run(
            """
            INSERT INTO content_item(id,canonical_url,title)
            VALUES ('content:dp227:persisted','https://example.test/dp227/content','DP227 persisted');
            INSERT INTO atomic_claim(
              id,content_id,normalized_claim,claim_type,temporal_scope,check_worthy
            ) VALUES (
              'claim:dp227:persisted','content:dp227:persisted','Synthetic metric is 63.2.',
              'NUMERIC_STATISTIC','{"statement_date":"2026-09-04"}'::jsonb,true
            );
            """
        )
        self.store.upsert_evidence(
            evidence_id="evidence:dp227:no-end",
            canonical_url="https://example.test/dp227/no-end",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            valid_from="2026-01-01",
            valid_until=None,
            record_status="SUPERSEDED",
            fetched_at="2026-10-07T10:00:00+00:00",
            content_sha256="c" * 64,
            reference_period="2026-07",
            independence_group="istat-sdmx:2026",
            metadata={"evidence_source_id": "istat-sdmx", "authoritative": True},
        )
        self.store.run(
            """
            INSERT INTO claim_evidence_candidate(
              claim_id,evidence_id,retrieval_method,retrieval_version,relation_candidate,status
            ) VALUES (
              'claim:dp227:persisted','evidence:dp227:no-end','SYNTHETIC','v1','SUPPORT','APPROVED'
            );
            INSERT INTO evidence_observation(
              id,evidence_id,observation_type,metric,value_numeric,unit,reference_period,
              extraction_method,extraction_version,status
            ) VALUES (
              'observation:dp227:no-end','evidence:dp227:no-end','NUMERIC_VALUE',
              'employment_rate_pct',63.2,'percent','2026-07','SYNTHETIC','v1','APPROVED'
            );
            """
        )
        rows = self.store.approved_verification_evidence("claim:dp227:persisted")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["valid_from"], "2026-01-01")
        self.assertIsNone(rows[0]["valid_until"])
        self.assertEqual(rows[0]["record_status"], "SUPERSEDED")

        contract = load_source_intelligence_contract()
        item = evidence_item_from_row(rows[0], contract)
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM",
            target_id="claim:dp227:persisted",
            claim_type="NUMERIC_STATISTIC",
            statement_date="2026-09-04",
            claim_requirements={
                "metric": "employment_rate_pct",
                "unit": "percent",
                "reference_period": "2026-07",
            },
            evidence=(item,),
            contract=contract,
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn(
            "SUPERSEDED_VERSION_WITHOUT_VALID_UNTIL",
            {row["reason"] for row in result.rejected_evidence},
        )

    def test_expired_state_persists_without_inventing_end_and_cannot_downgrade(self) -> None:
        self.store.upsert_evidence(
            evidence_id="evidence:dp227:expired",
            canonical_url="https://example.test/dp227/expired",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            valid_from="2026-01-01",
            valid_until=None,
            record_status="EXPIRED",
            fetched_at="2026-10-07T10:00:00+00:00",
            content_sha256="e" * 64,
        )
        initial = self.store.run(
            """
            SELECT valid_from::text || '|' || COALESCE(valid_until::text,'NULL') || '|' || record_status
            FROM evidence WHERE id='evidence:dp227:expired';
            """
        )
        self.assertEqual(initial, "2026-01-01|NULL|EXPIRED")

        self.store.upsert_evidence(
            evidence_id="evidence:dp227:expired",
            canonical_url="https://example.test/dp227/expired",
            publisher="Synthetic Authority",
            source_type="PRIMARY_OFFICIAL",
            publication_date="2026-09-01",
            record_status="ACTIVE",
            fetched_at="2026-10-07T11:00:00+00:00",
            content_sha256="e" * 64,
        )
        replay = self.store.run(
            """
            SELECT valid_from::text || '|' || COALESCE(valid_until::text,'NULL') || '|' || record_status
            FROM evidence WHERE id='evidence:dp227:expired';
            """
        )
        self.assertEqual(replay, "2026-01-01|NULL|EXPIRED")


if __name__ == "__main__":
    unittest.main()

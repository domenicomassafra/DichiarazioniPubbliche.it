from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.excerpt_policy import RightsStatus  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRegistryError,
    PrivateRightsRegistryStore,
    RightsSubject,
)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class PrivateRightsRegistryPostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    port: int
    fresh_database_url: str
    migration_database_url: str
    store: PrivateRightsRegistryStore
    migration_store: PrivateRightsRegistryStore
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
    def _psql(cls, database_url: str, sql: str) -> str:
        psql = shutil.which("psql") or "psql"
        return cls._run_command(
            [
                psql,
                "-X",
                "-qAt",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                database_url,
            ],
            input_text=sql,
        ).strip()

    @classmethod
    def _apply_file(cls, database_url: str, path: Path) -> None:
        psql = shutil.which("psql") or "psql"
        cls._run_command(
            [
                psql,
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                database_url,
                "-f",
                str(path),
            ]
        )

    @classmethod
    def setUpClass(cls) -> None:
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp305-rights-registry-")
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
            cls._psql(
                admin_url,
                "CREATE DATABASE dp305_rights_fresh; CREATE DATABASE dp305_rights_migration;",
            )
            cls.fresh_database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp305_rights_fresh"
            )
            cls.migration_database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp305_rights_migration"
            )
            migration = (
                ROOT
                / "db"
                / "migrations"
                / "20261006-add-private-rights-registry.sql"
            )
            cls._apply_file(cls.fresh_database_url, ROOT / "db" / "schema.v1.sql")
            cls._apply_file(cls.fresh_database_url, migration)
            cls._apply_file(cls.fresh_database_url, migration)
            cls._seed_legacy_dependencies()
            cls._apply_file(cls.migration_database_url, migration)
            cls._apply_file(cls.migration_database_url, migration)
            cls._seed_fresh_targets()
            cls._seed_migration_targets()
            cls.store = PrivateRightsRegistryStore(cls.fresh_database_url)
            cls.migration_store = PrivateRightsRegistryStore(cls.migration_database_url)
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
    def _seed_legacy_dependencies(cls) -> None:
        cls._psql(
            cls.migration_database_url,
            """
            CREATE TABLE content_item (id text PRIMARY KEY, canonical_url text NOT NULL);
            CREATE TABLE evidence (id text PRIMARY KEY, canonical_url text NOT NULL);
            CREATE TABLE transcript_variant (
                id text PRIMARY KEY,
                content_id text NOT NULL REFERENCES content_item(id)
            );
            CREATE TABLE transcript_segment (
                id text PRIMARY KEY,
                variant_id text NOT NULL REFERENCES transcript_variant(id)
            );
            CREATE TABLE canonical_transcript_segment (
                id text PRIMARY KEY,
                content_id text NOT NULL REFERENCES content_item(id)
            );
            CREATE TABLE passage (
                id text PRIMARY KEY,
                content_id text NOT NULL REFERENCES content_item(id)
            );
            """,
        )

    @classmethod
    def _seed_fresh_targets(cls) -> None:
        raw_hash = hashlib.sha256(b"fixture transcript").hexdigest()
        cls._psql(
            cls.fresh_database_url,
            f"""
            INSERT INTO content_item (id, canonical_url)
            VALUES
              ('content:dp305:one', 'https://source.example/item/one'),
              ('content:dp305:two', 'https://source.example/item/two');
            INSERT INTO evidence (id, canonical_url, source_type)
            VALUES ('evidence:dp305:one', 'https://source.example/evidence/one', 'OFFICIAL_RECORD');
            INSERT INTO transcript_variant (
                id, content_id, provider_id, source_kind, raw_text_sha256, raw_text
            ) VALUES (
                'variant:dp305:one', 'content:dp305:one', 'fixture-provider', 'OFFICIAL',
                '{raw_hash}', 'fixture transcript'
            );
            INSERT INTO transcript_segment (
                id, variant_id, segment_index, start_ms, end_ms, text
            ) VALUES (
                'segment:dp305:one', 'variant:dp305:one', 0, 0, 1000, 'fixture transcript'
            );
            """,
        )

    @classmethod
    def _seed_migration_targets(cls) -> None:
        cls._psql(
            cls.migration_database_url,
            """
            INSERT INTO content_item (id, canonical_url)
            VALUES
              ('content:dp305:migration', 'https://source.example/migration'),
              ('content:dp305:migration-two', 'https://source.example/migration-two');
            INSERT INTO evidence (id, canonical_url)
            VALUES ('evidence:dp305:migration', 'https://source.example/evidence/migration');
            INSERT INTO transcript_variant (id, content_id)
            VALUES ('variant:dp305:migration', 'content:dp305:migration');
            INSERT INTO transcript_segment (id, variant_id)
            VALUES ('segment:dp305:migration', 'variant:dp305:migration');
            """,
        )

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

    def subject(self, suffix: str, *, content_id="content:dp305:one", segment_id="segment:dp305:one"):
        return RightsSubject(
            source_family="SYNTHETIC_DP305_SOURCE",
            locator_kind="URL",
            locator_value=f"https://source.example/rights/{suffix}",
            content_id=content_id,
            evidence_id="evidence:dp305:one",
            transcript_segment_id=segment_id,
        )

    def test_default_record_is_unknown_private_and_source_bound(self):
        record = self.store.record_rights(
            subject=self.subject("default"),
            policy_version="dp305-rights-registry-v1",
        )
        self.assertEqual(record.rights_status, RightsStatus.UNKNOWN.value)
        self.assertEqual(record.record_visibility, "PRIVATE")
        self.assertIsNone(record.rights_receipt_ref)
        self.assertEqual(record.permitted_uses, ())
        self.assertEqual(record.attribution_requirements, ())
        self.assertEqual(record.version_state, "CURRENT")
        self.assertEqual(record.content_id, "content:dp305:one")
        self.assertEqual(record.evidence_id, "evidence:dp305:one")
        self.assertEqual(record.transcript_segment_id, "segment:dp305:one")
        self.assertEqual(record.record_version, PRIVATE_RIGHTS_RECORD_VERSION)

    def test_database_defaults_are_unknown_and_private_without_runtime_override(self):
        row = self._psql(
            self.migration_database_url,
            """
            INSERT INTO private_source_rights_record (
                id, subject_fingerprint, source_family, locator_kind, locator_value,
                policy_version
            ) VALUES (
                'private-rights:db-default', repeat('a', 64), 'SYNTHETIC_DB_DEFAULT',
                'URL', 'https://source.example/db-default', 'dp305-rights-registry-v1'
            )
            RETURNING rights_status || '|' || record_visibility;
            """,
        )
        self.assertEqual(row, "UNKNOWN|PRIVATE")

    def test_exact_replay_is_idempotent(self):
        values = dict(
            subject=self.subject("replay"),
            policy_version="dp305-rights-registry-v1",
        )
        first = self.store.record_rights(**values)
        second = self.store.record_rights(**values)
        self.assertEqual(first, second)
        count = self.store.run(
            "SELECT count(*) FROM private_source_rights_record WHERE subject_fingerprint=:'fp';",
            fp=first.subject_fingerprint,
        )
        self.assertEqual(count, "1")

    def test_new_decision_requires_explicit_current_supersession_and_preserves_history(self):
        subject = self.subject("supersession")
        first = self.store.record_rights(
            subject=subject,
            policy_version="dp305-rights-registry-v1",
        )
        with self.assertRaisesRegex(PrivateRightsRegistryError, "SUPERSEDES_REQUIRED"):
            self.store.record_rights(
                subject=subject,
                policy_version="dp305-rights-registry-v2",
                rights_status=RightsStatus.RIGHTS_HOLD,
                rights_receipt_ref="rights-receipt:synthetic:hold:1",
            )

        second = self.store.record_rights(
            subject=subject,
            policy_version="dp305-rights-registry-v2",
            rights_status=RightsStatus.RIGHTS_HOLD,
            rights_receipt_ref="rights-receipt:synthetic:hold:1",
            permitted_uses=("SOURCE_LINK_PRIVATE",),
            attribution_requirements=("SOURCE_NAME", "SOURCE_URL"),
            reviewed_at="2026-10-06T10:00:00+02:00",
            expires_at="2026-11-06T10:00:00+02:00",
            reviewer_ref="reviewer:synthetic:rights:1",
            supersedes_record_id=first.id,
        )
        self.assertEqual(second.rights_status, RightsStatus.RIGHTS_HOLD.value)
        self.assertEqual(second.supersedes_id, first.id)
        self.assertEqual(second.permitted_uses, ("SOURCE_LINK_PRIVATE",))
        self.assertEqual(second.attribution_requirements, ("SOURCE_NAME", "SOURCE_URL"))
        self.assertEqual(self.store.read_record(first.id).version_state, "HISTORICAL")
        self.assertEqual(self.store.read_current(subject).id, second.id)

        historical_replay = self.store.record_rights(
            subject=subject,
            policy_version="dp305-rights-registry-v1",
        )
        self.assertEqual(historical_replay.id, first.id)
        self.assertEqual(historical_replay.version_state, "HISTORICAL")

        with self.assertRaisesRegex(PrivateRightsRegistryError, "SUPERSEDES_NOT_CURRENT"):
            self.store.record_rights(
                subject=subject,
                policy_version="dp305-rights-registry-v3",
                rights_status=RightsStatus.BLOCKED,
                rights_receipt_ref="rights-receipt:synthetic:block:2",
                supersedes_record_id=first.id,
            )

    def test_clearance_cannot_be_recorded_without_explicit_receipt_and_review(self):
        subject = self.subject("clearance-guard")
        with self.assertRaisesRegex(PrivateRightsRegistryError, "RIGHTS_RECEIPT_REF_REQUIRED"):
            self.store.record_rights(
                subject=subject,
                policy_version="dp305-rights-registry-v1",
                rights_status=RightsStatus.CLEARED,
            )
        with self.assertRaisesRegex(PrivateRightsRegistryError, "CLEARED_REVIEW_REQUIRED"):
            self.store.record_rights(
                subject=subject,
                policy_version="dp305-rights-registry-v1",
                rights_status=RightsStatus.CLEARED,
                rights_receipt_ref="rights-receipt:synthetic:clearance:unreviewed",
            )

    def test_receipt_ref_is_opaque_bounded_and_no_body_is_persisted(self):
        with self.assertRaisesRegex(PrivateRightsRegistryError, "RIGHTS_RECEIPT_REF_INVALID"):
            self.store.record_rights(
                subject=self.subject("receipt-whitespace"),
                policy_version="dp305-rights-registry-v1",
                rights_status=RightsStatus.BLOCKED,
                rights_receipt_ref="this is not an opaque receipt reference",
            )
        columns = self.store.run(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='private_source_rights_record'
            ORDER BY ordinal_position;
            """
        ).splitlines()
        self.assertIn("rights_receipt_ref", columns)
        for forbidden in (
            "rights_receipt",
            "rights_receipt_body",
            "legal_reasoning",
            "notes",
            "publication_authorized",
            "excerpt_approved",
        ):
            self.assertNotIn(forbidden, columns)

    def test_segment_must_belong_to_bound_content(self):
        with self.assertRaisesRegex(
            PrivateRightsRegistryError,
            "TRANSCRIPT_SEGMENT_CONTENT_MISMATCH",
        ):
            self.store.record_rights(
                subject=self.subject(
                    "segment-content-mismatch",
                    content_id="content:dp305:two",
                    segment_id="segment:dp305:one",
                ),
                policy_version="dp305-rights-registry-v1",
            )

    def test_append_only_database_triggers_refuse_update_delete_and_truncate(self):
        record = self.store.record_rights(
            subject=self.subject("append-only"),
            policy_version="dp305-rights-registry-v1",
        )
        for sql in (
            f"UPDATE private_source_rights_record SET policy_version='tampered' WHERE id='{record.id}';",
            f"DELETE FROM private_source_rights_record WHERE id='{record.id}';",
            "TRUNCATE private_source_rights_record;",
        ):
            with self.assertRaises(RuntimeError):
                self.store.run_literal(sql)
        self.assertIsNotNone(self.store.read_record(record.id))

    def test_migration_database_has_same_defaults_and_runtime_contract(self):
        subject = RightsSubject(
            source_family="SYNTHETIC_DP305_MIGRATION",
            locator_kind="URL",
            locator_value="https://source.example/rights/migration",
            content_id="content:dp305:migration",
            evidence_id="evidence:dp305:migration",
            transcript_segment_id="segment:dp305:migration",
        )
        record = self.migration_store.record_rights(
            subject=subject,
            policy_version="dp305-rights-registry-v1",
        )
        self.assertEqual(record.rights_status, "UNKNOWN")
        self.assertEqual(record.record_visibility, "PRIVATE")
        replay = self.migration_store.record_rights(
            subject=subject,
            policy_version="dp305-rights-registry-v1",
        )
        self.assertEqual(record, replay)

    def test_fresh_schema_and_additive_migration_share_registry_contract(self):
        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261006-add-private-rights-registry.sql"
        ).read_text()
        markers = (
            "CREATE TABLE IF NOT EXISTS private_source_rights_record",
            "rights_status               text NOT NULL DEFAULT 'UNKNOWN'",
            "record_visibility           text NOT NULL DEFAULT 'PRIVATE'",
            "rights_receipt_ref",
            "permitted_uses",
            "attribution_requirements",
            "reviewed_at",
            "expires_at",
            "reviewer_ref",
            "policy_version",
            "supersedes_id",
            "CREATE UNIQUE INDEX IF NOT EXISTS private_source_rights_record_one_successor",
            "CREATE TRIGGER private_source_rights_record_append_only",
            "CREATE TRIGGER private_source_rights_record_no_truncate",
        )
        for sql in (schema, migration):
            for marker in markers:
                self.assertIn(marker, sql)

        fresh_columns = self._psql(
            self.fresh_database_url,
            """
            SELECT string_agg(column_name || ':' || data_type, ',' ORDER BY ordinal_position)
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='private_source_rights_record';
            """,
        )
        migration_columns = self._psql(
            self.migration_database_url,
            """
            SELECT string_agg(column_name || ':' || data_type, ',' ORDER BY ordinal_position)
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='private_source_rights_record';
            """,
        )
        self.assertEqual(fresh_columns, migration_columns)
        lowered = migration.lower()
        for destructive in ("drop table", "drop column", "delete from", "update private_source_rights_record"):
            self.assertNotIn(destructive, lowered)


if __name__ == "__main__":
    unittest.main()

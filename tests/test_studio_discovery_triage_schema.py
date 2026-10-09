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

from dichiarazioni_pubbliche.studio_discovery_triage_store import (  # noqa: E402
    StudioDiscoveryTriageStore,
)

MIGRATION = ROOT / "db/migrations/20261009-add-discovery-triage-decisions.sql"
SCHEMA = ROOT / "db/schema.v1.sql"


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class DiscoveryTriageSchemaTests(unittest.TestCase):
    """Real isolated PostgreSQL proof; neither MiniPC nor production is touched."""

    @classmethod
    def command(cls, *args, input_text=None):
        return subprocess.run(
            list(args), input=input_text, capture_output=True, text=True, check=False,
        )

    @classmethod
    def sql(cls, sql, *, database=None):
        return cls.command(
            "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
            "--dbname", database or cls.url, input_text=sql,
        )

    @classmethod
    def require_sql(cls, sql, *, database=None):
        result = cls.sql(sql, database=database)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    @classmethod
    def setUpClass(cls):
        missing = [binary for binary in ("initdb", "pg_ctl", "psql")
                   if not shutil.which(binary)]
        if missing:
            raise unittest.SkipTest("local PostgreSQL unavailable: " + ", ".join(missing))
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp417-discovery-triage-")
        cls.data_dir = Path(cls.tmp.name) / "pgdata"
        cls.port = _port()
        cls.started = False
        try:
            init = cls.command(
                "initdb", "-D", str(cls.data_dir), "--username=postgres",
                "--auth=trust", "--encoding=UTF8", "--no-locale",
            )
            if init.returncode:
                raise RuntimeError(init.stderr)
            started = cls.command(
                "pg_ctl", "-D", str(cls.data_dir),
                "-l", str(Path(cls.tmp.name) / "postgres.log"),
                "-o", f"-F -p {cls.port} -h 127.0.0.1 -k {cls.tmp.name}",
                "-w", "start",
            )
            if started.returncode:
                raise RuntimeError(started.stderr)
            cls.started = True
            admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            cls.require_sql(
                "CREATE DATABASE dp417_fresh; CREATE DATABASE dp417_migration;",
                database=admin,
            )
            cls.url = f"postgresql://postgres@127.0.0.1:{cls.port}/dp417_migration"
            cls.fresh_url = f"postgresql://postgres@127.0.0.1:{cls.port}/dp417_fresh"
            cls.require_sql(
                """
                CREATE TABLE research_collection (id text PRIMARY KEY);
                CREATE TABLE research_discovery_manifest (
                    id text PRIMARY KEY,
                    collection_id text NOT NULL REFERENCES research_collection(id)
                );
                CREATE TABLE research_discovery_query (
                    id text PRIMARY KEY,
                    manifest_id text NOT NULL REFERENCES research_discovery_manifest(id)
                );
                CREATE TABLE research_discovery_run (
                    id text PRIMARY KEY,
                    manifest_id text NOT NULL REFERENCES research_discovery_manifest(id)
                );
                CREATE TABLE research_discovery_attempt (
                    id text PRIMARY KEY,
                    run_id text NOT NULL REFERENCES research_discovery_run(id),
                    query_id text NOT NULL REFERENCES research_discovery_query(id)
                );
                CREATE TABLE research_discovery_hit (
                    id text PRIMARY KEY,
                    run_id text NOT NULL REFERENCES research_discovery_run(id),
                    attempt_id text NOT NULL REFERENCES research_discovery_attempt(id),
                    query_id text NOT NULL REFERENCES research_discovery_query(id),
                    disposition text NOT NULL
                );
                INSERT INTO research_collection VALUES ('collection:one'), ('collection:two');
                INSERT INTO research_discovery_manifest VALUES
                  ('manifest:one', 'collection:one'), ('manifest:two', 'collection:two');
                INSERT INTO research_discovery_query VALUES
                  ('query:one', 'manifest:one'), ('query:two', 'manifest:two');
                INSERT INTO research_discovery_run VALUES
                  ('run:one', 'manifest:one'), ('run:two', 'manifest:two');
                INSERT INTO research_discovery_attempt VALUES
                  ('attempt:one', 'run:one', 'query:one'),
                  ('attempt:two', 'run:two', 'query:two');
                """
            )
            for db in (cls.url, cls.fresh_url):
                if db == cls.fresh_url:
                    cls.require_sql(SCHEMA.read_text(), database=db)
                cls.require_sql(MIGRATION.read_text(), database=db)
                cls.require_sql(MIGRATION.read_text(), database=db)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            cls.command("pg_ctl", "-D", str(cls.data_dir), "-m", "fast", "-w", "stop")
            cls.started = False
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def setUp(self):
        # Each test writes only its own fixture IDs into the isolated cluster.
        prefix = self._testMethodName
        self.hit = "hit:" + prefix
        self.other = "hit:other:" + prefix
        self.invalid_attempt = "hit:bad-attempt:" + prefix
        self.invalid_query = "hit:bad-query:" + prefix
        self.require_sql(
            f"""
            INSERT INTO research_discovery_hit VALUES
              ('{self.hit}', 'run:one', 'attempt:one', 'query:one', 'NEW_CONTENT'),
              ('{self.other}', 'run:one', 'attempt:one', 'query:one', 'NEW_CONTENT'),
              ('{self.invalid_attempt}', 'run:one', 'attempt:two', 'query:one', 'NEW_CONTENT'),
              ('{self.invalid_query}', 'run:one', 'attempt:one', 'query:two', 'NEW_CONTENT');
            """
        )

    def insert(self, hit=None, *, collection="collection:one", key="request:one",
               revision=1, expected=0, decision="NEEDS_REVIEW",
               digest="a" * 64, actor="reviewer:fixture", raw_key=None):
        request_key = raw_key if raw_key is not None else f"{self._testMethodName}:{key}"
        return self.sql(
            "INSERT INTO research_discovery_triage_decision "
            "(collection_id, hit_id, revision, expected_revision, request_key, "
            "decision, payload_sha256, actor_ref) VALUES "
            f"('{collection}', '{hit or self.hit}', {revision}, {expected}, "
            f"'{request_key}', '{decision}', '{digest}', '{actor}');"
        )

    def assert_failed(self, result, fragment):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(fragment, result.stderr)

    def test_fresh_schema_migration_replay_and_migration_content_match(self):
        start = "-- DP-417: private Discovery Hit triage history."
        end = "-- Runtime still owns actor authentication"
        migration = MIGRATION.read_text()
        schema = SCHEMA.read_text()
        self.assertEqual(
            schema[schema.index(start):schema.index(end, schema.index(start))],
            migration[migration.index(start):migration.index(end, migration.index(start))],
        )
        for db in (self.url, self.fresh_url):
            self.assertEqual(
                self.require_sql(
                    "SELECT count(*) FROM pg_trigger WHERE tgrelid = "
                    "'research_discovery_triage_decision'::regclass AND NOT tgisinternal;",
                    database=db,
                ), "3"
            )

    def test_append_only_history_preserves_disposition(self):
        self.assertEqual(self.insert().returncode, 0)
        self.assertEqual(
            self.require_sql(
                "SELECT disposition FROM research_discovery_hit "
                f"WHERE id = '{self.hit}';"
            ), "NEW_CONTENT"
        )
        result = self.insert(revision=2, expected=1, key="request:two", decision="DEFERRED")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.require_sql(
                "SELECT string_agg(decision, ',' ORDER BY revision) "
                "FROM research_discovery_triage_decision "
                f"WHERE hit_id = '{self.hit}';"
            ), "NEEDS_REVIEW,DEFERRED"
        )
        for verb in (
            "UPDATE research_discovery_triage_decision SET decision = 'REJECTED'",
            "DELETE FROM research_discovery_triage_decision",
            "TRUNCATE research_discovery_triage_decision",
        ):
            self.assert_failed(self.sql(verb + ";"), "append-only")
        self.assert_failed(
            self.sql(f"DELETE FROM research_discovery_hit WHERE id = '{self.hit}';"),
            "foreign key constraint",
        )

    def test_lineage_scope_and_attempt_query_validation_fail_closed(self):
        self.assert_failed(
            self.insert(collection="collection:two"), "scope mismatch"
        )
        self.assert_failed(
            self.insert(hit=self.invalid_attempt), "scope mismatch"
        )
        self.assert_failed(
            self.insert(hit=self.invalid_query), "scope mismatch"
        )
        self.assert_failed(self.insert(hit="missing-hit"), "scope mismatch")
        self.assertEqual(
            self.require_sql(
                "SELECT count(*) FROM research_discovery_triage_decision "
                f"WHERE hit_id IN ('{self.hit}', '{self.invalid_attempt}', "
                f"'{self.invalid_query}');"
            ), "0"
        )

    def test_revision_cas_and_global_replay_key_collision(self):
        self.assert_failed(
            self.insert(revision=2, expected=1), "revision conflict"
        )
        self.assertEqual(self.insert().returncode, 0)
        self.assert_failed(self.insert(key="request:two"), "revision conflict")
        self.assert_failed(self.insert(revision=3, expected=2, key="request:three"),
                           "revision conflict")
        # Duplicate keys never append again; runtime must compare the stored
        # request and payload before reporting idempotent replay as successful.
        self.assert_failed(self.insert(), "revision conflict")
        self.assert_failed(self.insert(hit=self.other), "duplicate key value")
        self.assertEqual(
            self.require_sql(
                "SELECT count(*) FROM research_discovery_triage_decision "
                f"WHERE hit_id = '{self.hit}';"
            ), "1"
        )

    def test_only_safe_decisions_digest_actor_and_request_key_accepted(self):
        self.assert_failed(self.insert(decision="PROMOTE"), "check constraint")
        self.assert_failed(self.insert(decision="PUBLISH"), "check constraint")
        self.assert_failed(self.insert(digest="invalid"), "check constraint")
        self.assert_failed(self.insert(actor="private actor"), "check constraint")
        self.assert_failed(self.insert(raw_key="invalid key"), "check constraint")
        self.assertEqual(self.insert(decision="REJECTED").returncode, 0)

    def test_two_competing_first_writes_only_one_commits(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self.insert, key=f"parallel:{index}")
                for index in range(2)
            ]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sum(result.returncode == 0 for result in results), 1)
        self.assertEqual(
            self.require_sql(
                "SELECT count(*) FROM research_discovery_triage_decision "
                f"WHERE hit_id = '{self.hit}';"
            ), "1"
        )

    def record(self, *, hit=None, collection="collection:one", key="request:one",
               decision="NEEDS_REVIEW", expected=0, actor="reviewer:fixture"):
        """Exercise the real psql-backed store against our migrated PG cluster."""
        return StudioDiscoveryTriageStore(database_url=self.url).record(
            collection_id=collection,
            hit_id=hit or self.hit,
            request_key=f"{self._testMethodName}:{key}",
            decision=decision,
            expected_revision=expected,
            actor_ref=actor,
        )

    def assert_private_receipt(self, receipt):
        self.assertTrue(receipt["private_only"])
        for authority in (
            "publication_authority", "triage_action_authorized",
            "capture_authorized", "actor_attested",
        ):
            self.assertIs(receipt[authority], False, authority)
        for sensitive_field in (
            "canonical_url", "query_text", "title", "provider_receipt",
            "source_body", "credential", "actor_ref",
        ):
            self.assertNotIn(sensitive_field, receipt)

    def test_real_store_replay_conflicts_and_next_revision(self):
        created = self.record(actor="operator:unattested")
        self.assertEqual((created["result_code"], created["revision"]), ("CREATED", 1))
        self.assert_private_receipt(created)

        replay = self.record(actor="operator:unattested")
        self.assertEqual((replay["result_code"], replay["revision"]), ("REPLAY", 1))
        self.assertEqual(replay["payload_sha256"], created["payload_sha256"])
        self.assert_private_receipt(replay)

        for changes in (
            {"decision": "DEFERRED"},
            {"actor": "operator:other"},
            {"expected": 1},
            {"hit": self.other},
        ):
            with self.subTest(changes=changes):
                conflict = self.record(**({"actor": "operator:unattested"} | changes))
                self.assertEqual(conflict["result_code"], "IDEMPOTENCY_CONFLICT")
                self.assert_private_receipt(conflict)

        stale = self.record(key="request:stale", expected=0)
        self.assertEqual((stale["result_code"], stale["revision"]),
                         ("REVISION_CONFLICT", 1))
        self.assert_private_receipt(stale)

        second = self.record(key="request:next", expected=1,
                             decision="DEFERRED", actor="operator:unattested")
        self.assertEqual((second["result_code"], second["revision"]), ("CREATED", 2))
        self.assert_private_receipt(second)
        self.assertEqual(self.record(key="request:next", expected=1,
                                     decision="DEFERRED", actor="operator:unattested")
                         ["result_code"], "REPLAY")
        self.assertEqual(
            self.require_sql(
                "SELECT string_agg(revision::text || ':' || decision, ',' "
                "ORDER BY revision) FROM research_discovery_triage_decision "
                f"WHERE hit_id = '{self.hit}'"
            ), "1:NEEDS_REVIEW,2:DEFERRED",
        )
        self.assertEqual(
            self.require_sql(
                f"SELECT disposition FROM research_discovery_hit WHERE id = '{self.hit}'"
            ), "NEW_CONTENT",
        )

    def test_real_store_wrong_collection_redacts_revision_and_replay(self):
        created = self.record()
        self.assertEqual(created["revision"], 1)
        # A known key or guessed Hit from another Collection must not reveal
        # its revision or distinguish an existing review from a missing Hit.
        for hit, key in (
            (self.hit, "request:one"),
            (self.hit, "request:guess"),
            ("missing:hit", "request:guess"),
        ):
            with self.subTest(hit=hit, key=key):
                hidden = self.record(hit=hit, collection="collection:two", key=key)
                self.assertEqual(hidden["result_code"], "SCOPE_NOT_FOUND")
                self.assertIsNone(hidden["revision"])
                self.assert_private_receipt(hidden)

        self.assertEqual(
            self.require_sql("SELECT count(*) FROM research_discovery_triage_decision "
                             f"WHERE hit_id = '{self.hit}'"), "1",
        )

    def test_real_store_inconsistent_lineage_fails_closed_without_leaking_details(self):
        # Store scope now agrees with the migration trigger's Attempt/Query
        # coherence checks, before attempting a write or revealing revisions.
        for hit in (self.invalid_attempt, self.invalid_query):
            with self.subTest(hit=hit):
                refused = self.record(hit=hit, key="request:inconsistent")
                self.assertEqual(refused["result_code"], "SCOPE_NOT_FOUND")
                self.assertIsNone(refused["revision"])
                self.assert_private_receipt(refused)
                self.assertEqual(
                    self.require_sql(
                        "SELECT count(*) FROM research_discovery_triage_decision "
                        f"WHERE hit_id = '{hit}'"
                    ), "0",
                )

    def test_real_store_concurrent_competing_requests_and_unattested_actor(self):
        # Any syntactically valid actor_ref is only an annotation. The store
        # has no external identity authority, even for an admin-looking actor.
        forged_actor = "credential:superadmin"
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [
                pool.submit(self.record, key=f"race:{index}",
                            actor=forged_actor, expected=0)
                for index in range(5)
            ]
            receipts = [future.result(timeout=15) for future in futures]
        self.assertEqual([receipt["result_code"] for receipt in receipts].count("CREATED"), 1)
        self.assertEqual([receipt["result_code"] for receipt in receipts].count("REVISION_CONFLICT"), 4)
        for receipt in receipts:
            self.assertEqual(receipt["revision"], 1)
            self.assert_private_receipt(receipt)
        self.assertEqual(
            self.require_sql("SELECT count(*) FROM research_discovery_triage_decision "
                             f"WHERE hit_id = '{self.hit}'"), "1",
        )
        self.assertEqual(
            self.require_sql("SELECT actor_ref FROM research_discovery_triage_decision "
                             f"WHERE hit_id = '{self.hit}'"), forged_actor,
        )

    def test_real_store_against_full_schema_and_real_migration(self):
        # In addition to the legacy dependency fixture used above, check one
        # write against the complete schema.v1.sql with the migration replayed.
        # Neither the private URL nor the title may appear in the store receipt.
        digest = "b" * 64
        self.require_sql(
            f"""
            INSERT INTO research_collection
                (id, slug, name, scope_text, policy_version)
            VALUES ('collection:full', 'full-dp417', 'Fixture', 'fixture', 'v1');
            INSERT INTO research_discovery_manifest
                (id, collection_id, manifest_sha256, max_results,
                 max_results_per_host, cost_cap_usd)
            VALUES ('manifest:full', 'collection:full', '{digest}', 5, 5, 0);
            INSERT INTO research_discovery_query
                (id, manifest_id, ordinal, query_text, source_families,
                 adapter_ids, max_results)
            VALUES ('query:full', 'manifest:full', 0, 'private-test-query',
                    '["REPORTING"]'::jsonb, '["fixture"]'::jsonb, 5);
            INSERT INTO research_discovery_run
                (id, manifest_id, manifest_sha256)
            VALUES ('run:full', 'manifest:full', '{digest}');
            INSERT INTO research_discovery_attempt
                (id, run_id, query_id, adapter_id, adapter_version)
            VALUES ('attempt:full', 'run:full', 'query:full', 'fixture', 'v1');
            INSERT INTO research_discovery_hit
                (id, run_id, attempt_id, query_id, hit_key, ordinal,
                 canonical_url, source_host, title, source_family, disposition)
            VALUES ('hit:full', 'run:full', 'attempt:full', 'query:full',
                    '{digest}', 0, 'https://private-fixture.invalid/item',
                    'private-fixture.invalid', 'private-test-title',
                    'REPORTING', 'NEW_CONTENT');
            """,
            database=self.fresh_url,
        )
        payload = dict(
            collection_id="collection:full", hit_id="hit:full",
            request_key="request:full", decision="NEEDS_REVIEW",
            expected_revision=0, actor_ref="fake-admin:fixture",
        )
        store = StudioDiscoveryTriageStore(database_url=self.fresh_url)
        created = store.record(**payload)
        self.assertEqual((created["result_code"], created["revision"]), ("CREATED", 1))
        self.assert_private_receipt(created)
        self.assertEqual(store.record(**payload)["result_code"], "REPLAY")
        self.assertEqual(
            self.require_sql("SELECT count(*) FROM research_discovery_triage_decision "
                             "WHERE hit_id = 'hit:full'", database=self.fresh_url), "1",
        )

    def test_real_store_parallel_exact_replays_append_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.record, key="request:same", expected=0)
                       for _ in range(4)]
            receipts = [future.result(timeout=15) for future in futures]
        self.assertEqual(
            sorted(receipt["result_code"] for receipt in receipts),
            ["CREATED", "REPLAY", "REPLAY", "REPLAY"],
        )
        self.assertEqual({receipt["revision"] for receipt in receipts}, {1})
        self.assertEqual(len({receipt["payload_sha256"] for receipt in receipts}), 1)
        for receipt in receipts:
            self.assert_private_receipt(receipt)
        self.assertEqual(
            self.require_sql("SELECT count(*) FROM research_discovery_triage_decision "
                             f"WHERE hit_id = '{self.hit}'"), "1",
        )


if __name__ == "__main__":
    unittest.main()

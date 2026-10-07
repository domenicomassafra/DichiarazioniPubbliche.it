import hashlib
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

from dichiarazioni_pubbliche.provenance_quarantine import (  # noqa: E402
    ActorAuthorization,
    BoundedDependencyGraph,
    HoldPermission,
    HoldScopeTarget,
    InMemoryProvenanceHoldRegistry,
    PublicDependencyRecord,
    RevalidationProof,
)
from dichiarazioni_pubbliche.provenance_quarantine_persistence import (  # noqa: E402
    ProvenanceHoldPersistenceStore,
)
from dichiarazioni_pubbliche.ingestion_relevance import (  # noqa: E402
    append_ingestion_relevance_authority,
)
from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    SourceSnapshot,
    evaluate_reobservation,
)
from dichiarazioni_pubbliche.source_revalidation_persistence import (  # noqa: E402
    SourceRevalidationPersistenceStore,
    persist_revalidation_with_hold,
)


NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
SHA_A = hashlib.sha256(b"source-a").hexdigest()
SHA_B = hashlib.sha256(b"source-b").hexdigest()
SOURCE_ID = "source:dp511:persisted"
CONTENT_ID = "content:dp511:persisted"
FINDING_ID = "finding:dp510:persisted"
PROVIDER_ID = "official-provider"


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def actors():
    return (
        ActorAuthorization("operator", frozenset({HoldPermission.ACTIVATE})),
        ActorAuthorization("reviewer", frozenset({HoldPermission.REVIEW_UNHOLD})),
        ActorAuthorization("revalidator", frozenset({HoldPermission.REVALIDATE})),
    )


def refs(*, source_version="source:v1"):
    return {
        "source_version": source_version,
        "provenance_version": "provenance:v1",
        "policy_version": "policy:v1",
        "review_version": "review:v1",
    }


def graph(scope, load_refs):
    return BoundedDependencyGraph(
        records=(
            PublicDependencyRecord(
                public_id=FINDING_ID,
                dependencies=(scope,),
                load_bearing_refs=load_refs,
            ),
            PublicDependencyRecord(
                public_id="finding:unrelated",
                dependencies=(HoldScopeTarget.finding("finding:unrelated"),),
                load_bearing_refs=load_refs,
            ),
        )
    )


def snapshot(**overrides):
    values = dict(
        source_id=SOURCE_ID,
        observed_at=NOW,
        availability="AVAILABLE",
        content_sha256=SHA_A,
        source_version="v1",
        etag='"a"',
        canonical_url="https://example.test/source",
        rights_status="CLEARED",
    )
    values.update(overrides)
    return SourceSnapshot(**values)


class ProvenanceRevalidationPersistencePostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    server_started = False
    database_counter = 0

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
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp510-511-ledgers-")
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
            cls.admin_url = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "server_started", False):
            subprocess.run(
                ["pg_ctl", "-D", str(cls.data_dir), "-m", "immediate", "stop"],
                capture_output=True,
                text=True,
                check=False,
            )
        if hasattr(cls, "postgres_tmp"):
            cls.postgres_tmp.cleanup()

    def setUp(self):
        type(self).database_counter += 1
        self.database = f"dp510_511_{type(self).database_counter}"
        self._run_command(
            ["psql", "-X", "-qAt", "--dbname", self.admin_url, "-c", f"CREATE DATABASE {self.database};"]
        )
        self.database_url = (
            f"postgresql://postgres@127.0.0.1:{self.port}/{self.database}"
        )
        self._run_command(
            ["psql", "-X", "-q", "--dbname", self.database_url, "-f", str(ROOT / "db/schema.v1.sql")]
        )
        self.holds = ProvenanceHoldPersistenceStore(self.database_url)
        self.revalidation = SourceRevalidationPersistenceStore(self.database_url)
        self._run_command(
            [
                "psql",
                "-X",
                "-qAt",
                "--dbname",
                self.database_url,
                "-c",
                (
                    "INSERT INTO source (id, canonical_name, source_type, canonical_url) "
                    f"VALUES ('{SOURCE_ID}', 'Synthetic source', 'OFFICIAL', 'https://example.test/source'); "
                    "INSERT INTO content_item (id, source_id, canonical_url, processing_status) "
                    f"VALUES ('{CONTENT_ID}', '{SOURCE_ID}', 'https://example.test/source', 'PROCESSED');"
                ),
            ]
        )
        append_ingestion_relevance_authority(
            self.revalidation.run,
            content_ref=CONTENT_ID,
            canonical_url="https://example.test/source",
            relevance_reason="OFFICIAL_RECORD",
            reviewer_ref="reviewer:dp304",
            audit_ref="audit:dp304:source-revalidation",
            reviewed_at="2026-10-06T12:00:00+00:00",
        )

    def tearDown(self):
        self._run_command(
            [
                "psql",
                "-X",
                "-qAt",
                "--dbname",
                self.admin_url,
                "-c",
                (
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname='{self.database}' AND pid <> pg_backend_pid();"
                ),
            ]
        )
        self._run_command(
            [
                "psql",
                "-X",
                "-qAt",
                "--dbname",
                self.admin_url,
                "-c",
                f"DROP DATABASE {self.database};",
            ]
        )

    def _scalar(self, sql):
        return self._run_command(
            ["psql", "-X", "-qAt", "--dbname", self.database_url, "-c", sql]
        ).strip()

    def test_persisted_hold_survives_restart_and_requires_exact_current_revalidation(self):
        scope = HoldScopeTarget.finding(FINDING_ID)
        load_refs = refs()
        current_graph = graph(scope, load_refs)
        binding = RevalidationProof(load_refs).binding_sha256
        registry = InMemoryProvenanceHoldRegistry(actors=actors())
        activation = registry.activate(
            request_id="hold:activate",
            hold_id="hold:durable",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=scope,
            graph=current_graph,
        )
        self.assertEqual(self.holds.persist_registry(registry=registry, graph=current_graph), 1)
        self.assertFalse(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=binding,
            )
        )
        self.assertTrue(
            self.holds.allows_publication(
                public_id="finding:unrelated",
                current_publication_binding_sha256=binding,
            )
        )

        restored = self.holds.restore_registry(actors=actors())
        replay = restored.activate(
            request_id="hold:activate",
            hold_id="hold:durable",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=scope,
            graph=current_graph,
        )
        self.assertEqual(replay, activation)
        self.assertEqual(self.holds.persist_registry(registry=restored, graph=current_graph), 0)

        restored.reviewed_unhold(
            request_id="hold:review",
            hold_id="hold:durable",
            actor_id="reviewer",
            review_code="FIX_REVIEWED",
            graph=current_graph,
        )
        self.holds.persist_registry(registry=restored, graph=current_graph)
        self.assertFalse(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=binding,
            )
        )

        restored = self.holds.restore_registry(actors=actors())
        restored.revalidate(
            request_id="hold:revalidate",
            hold_id="hold:durable",
            actor_id="revalidator",
            proof=RevalidationProof(load_refs),
            graph=current_graph,
        )
        self.holds.persist_registry(registry=restored, graph=current_graph)
        self.assertTrue(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=binding,
            )
        )

        changed_refs = refs(source_version="source:v2")
        changed_graph = graph(scope, changed_refs)
        changed_binding = RevalidationProof(changed_refs).binding_sha256
        self.holds.append_dependency_graph(changed_graph)
        self.assertFalse(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=changed_binding,
            )
        )

    def test_source_drift_persists_immutable_captures_observations_and_targeted_hold(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=13),
            content_sha256=SHA_B,
            source_version="v2",
            etag='"b"',
        )
        decision = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 6),
            load_bearing_for_evidence=True,
        )
        scope = HoldScopeTarget.source(
            provider_id=PROVIDER_ID,
            source_id=SOURCE_ID,
            source_version="v1",
        )
        load_refs = refs(source_version="source:v2")
        current_graph = graph(scope, load_refs)
        registry = InMemoryProvenanceHoldRegistry(actors=actors())

        receipt = persist_revalidation_with_hold(
            store=self.revalidation,
            hold_store=self.holds,
            previous=previous,
            current=current,
            decision=decision,
            content_id=CONTENT_ID,
            provider_id=PROVIDER_ID,
            actor_id="operator",
            graph=current_graph,
            registry=registry,
        )
        self.assertIsNotNone(receipt.hold_id)
        self.assertNotEqual(receipt.previous_capture_id, receipt.current_capture_id)
        self.assertEqual(
            self._scalar(
                f"SELECT count(*) FROM content_capture WHERE content_id='{CONTENT_ID}';"
            ),
            "2",
        )
        self.assertEqual(
            self._scalar(
                f"SELECT count(*) FROM source_revalidation_snapshot_durable WHERE source_id='{SOURCE_ID}';"
            ),
            "2",
        )
        self.assertEqual(len(self.revalidation.history_for_source(SOURCE_ID)), 1)
        self.assertFalse(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=RevalidationProof(load_refs).binding_sha256,
            )
        )
        captures_before_release = self._scalar(
            "SELECT string_agg(content_sha256, ',' ORDER BY content_sha256) "
            "FROM content_capture;"
        )

        replay = persist_revalidation_with_hold(
            store=self.revalidation,
            hold_store=self.holds,
            previous=previous,
            current=current,
            decision=decision,
            content_id=CONTENT_ID,
            provider_id=PROVIDER_ID,
            actor_id="operator",
            graph=current_graph,
            registry=registry,
        )
        self.assertEqual(replay, receipt)
        self.assertEqual(
            self._scalar("SELECT count(*) FROM source_revalidation_event_durable;"), "1"
        )
        self.assertEqual(self._scalar("SELECT count(*) FROM provenance_hold_event_durable;"), "1")

        restored = self.holds.restore_registry(actors=actors())
        restored.reviewed_unhold(
            request_id="source:reviewed-unhold",
            hold_id=receipt.hold_id,
            actor_id="reviewer",
            review_code="SOURCE_V2_REVIEWED",
            graph=current_graph,
        )
        self.holds.persist_registry(registry=restored, graph=current_graph)
        restored = self.holds.restore_registry(actors=actors())
        restored.revalidate(
            request_id="source:revalidated",
            hold_id=receipt.hold_id,
            actor_id="revalidator",
            proof=RevalidationProof(load_refs),
            graph=current_graph,
        )
        self.holds.persist_registry(registry=restored, graph=current_graph)
        self.assertEqual(
            self._scalar(
                "SELECT string_agg(content_sha256, ',' ORDER BY content_sha256) "
                "FROM content_capture;"
            ),
            captures_before_release,
        )
        self.assertTrue(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=RevalidationProof(load_refs).binding_sha256,
            )
        )

    def test_version_only_reobservation_appends_snapshot_without_rewriting_same_bytes_capture(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=13),
            source_version="v2",
        )
        decision = evaluate_reobservation(previous, current, as_of=date(2026, 10, 6))
        persisted = self.revalidation.persist_reobservation(
            previous=previous,
            current=current,
            decision=decision,
            content_id=CONTENT_ID,
        )
        self.assertEqual(persisted.previous_capture_id, persisted.current_capture_id)
        self.assertEqual(self._scalar("SELECT count(*) FROM content_capture;"), "1")
        self.assertEqual(self._scalar("SELECT count(*) FROM source_revalidation_snapshot_durable;"), "2")

    def test_revalidation_capture_without_current_relevance_is_omitted(self):
        unreviewed_content_id = "content:dp511:unreviewed"
        self.revalidation.run(
            """
            INSERT INTO content_item (id, source_id, canonical_url, processing_status)
            VALUES (:'content_id', :'source_id', 'https://example.test/source', 'PROCESSED');
            """,
            content_id=unreviewed_content_id,
            source_id=SOURCE_ID,
        )
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=13),
            content_sha256=SHA_B,
            source_version="v2",
        )
        decision = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 6),
        )
        with self.assertRaisesRegex(RuntimeError, "INGESTION_RELEVANCE_MISSING"):
            self.revalidation.persist_reobservation(
                previous=previous,
                current=current,
                decision=decision,
                content_id=unreviewed_content_id,
            )
        self.assertEqual(
            self._scalar(
                "SELECT count(*) FROM content_capture "
                f"WHERE content_id='{unreviewed_content_id}';"
            ),
            "0",
        )

    def test_hold_and_source_ledgers_are_append_only_and_detect_privileged_tamper(self):
        scope = HoldScopeTarget.finding(FINDING_ID)
        load_refs = refs()
        current_graph = graph(scope, load_refs)
        binding = RevalidationProof(load_refs).binding_sha256
        registry = InMemoryProvenanceHoldRegistry(actors=actors())
        registry.activate(
            request_id="hold:tamper",
            hold_id="hold:tamper",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=scope,
            graph=current_graph,
        )
        self.holds.persist_registry(registry=registry, graph=current_graph)

        for sql in (
            "UPDATE provenance_dependency_graph_snapshot SET snapshot_version='changed';",
            "DELETE FROM provenance_hold_event_durable;",
            "TRUNCATE provenance_hold_event_durable;",
        ):
            proc = subprocess.run(
                ["psql", "-X", "-qAt", "--dbname", self.database_url, "-c", sql],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)

        self._run_command(
            [
                "psql",
                "-X",
                "-qAt",
                "--dbname",
                self.database_url,
                "-c",
                (
                    "SET session_replication_role=replica; "
                    "UPDATE provenance_hold_event_durable SET reason_code='PRIVILEGED_TAMPER' "
                    "WHERE event_sequence=1; "
                    "SET session_replication_role=origin;"
                ),
            ]
        )
        self.assertFalse(
            self.holds.allows_publication(
                public_id=FINDING_ID,
                current_publication_binding_sha256=binding,
            )
        )

    def test_additive_migration_is_replay_safe_on_fresh_schema(self):
        migration = ROOT / "db/migrations/20261006-add-provenance-hold-source-revalidation-ledgers.sql"
        for _ in range(2):
            self._run_command(
                ["psql", "-X", "-q", "--dbname", self.database_url, "-f", str(migration)]
            )
        self.assertEqual(
            self._scalar(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name IN ("
                "'provenance_dependency_graph_snapshot',"
                "'provenance_hold_event_durable',"
                "'source_revalidation_snapshot_durable',"
                "'source_revalidation_event_durable');"
            ),
            "4",
        )


if __name__ == "__main__":
    unittest.main()

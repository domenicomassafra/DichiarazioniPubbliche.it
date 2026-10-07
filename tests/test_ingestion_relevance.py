import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore,
    CapturePipelineError,
    CapturePipelineStore,
    capture_content,
)
from dichiarazioni_pubbliche.curated_written_intake import (  # noqa: E402
    apply_curated_written_batch,
    prepare_curated_written_batch,
)
from dichiarazioni_pubbliche.ingestion_relevance import (  # noqa: E402
    IngestionRelevanceBlocked,
    append_ingestion_relevance_authority,
    deterministic_ingestion_operation_ref,
    issue_ingestion_acquisition_permit,
    require_current_ingestion_relevance,
    require_ingestion_acquisition_permit,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime, QueueRuntimeStore  # noqa: E402
from dichiarazioni_pubbliche.scheduler import (  # noqa: E402
    deterministic_content_id,
    provisional_content_key,
)
from dichiarazioni_pubbliche.research_discovery import (  # noqa: E402
    DiscoveryHitCandidate,
    DiscoveryManifest,
    DiscoveryQuery,
    DiscoverySeed,
    ResearchDiscoveryStore,
)
from dichiarazioni_pubbliche.scheduler_daemon import (  # noqa: E402
    PsqlStore as SchedulerPsqlStore,
    SourceRunContext,
)
from dichiarazioni_pubbliche.source_watcher import DiscoveredContent, FetchedBytes  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _curated_payload() -> dict:
    return {
        "batch_id": "dp304-relevance-batch",
        "extraction_model": "test-model",
        "extraction_version": "test-v1",
        "contents": [
            {
                "id": "content:dp304:curated",
                "source": {
                    "id": "source:dp304",
                    "name": "DP304 Source",
                    "url": "https://example.test/",
                },
                "url": "https://example.test/curated",
                "title": "Curated item",
                "published_at": "2026-10-07T18:00:00+02:00",
                "person_id": "person:dp304",
                "claims": [
                    {
                        "id": "claim:dp304",
                        "normalized_claim": "A bounded factual claim.",
                        "claim_type": "HISTORICAL_CLAIM",
                        "statement_date": "2026-10-07",
                        "check_worthy": True,
                        "quote_text": "A bounded factual claim.",
                    }
                ],
            }
        ],
    }


class IngestionRelevancePersistenceTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    port: int
    database_url: str
    store: PsqlRuntime
    server_started = False

    @classmethod
    def _run_command(cls, args: list[str]) -> str:
        proc = subprocess.run(args, text=True, capture_output=True, check=False)
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
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp304-ingestion-relevance-")
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
                    "CREATE DATABASE dp304_ingestion_relevance;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp304_ingestion_relevance"
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
            migration = (
                ROOT
                / "db"
                / "migrations"
                / "20261007-add-privacy-ingestion-relevance-authority.sql"
            )
            for _ in range(2):
                cls._run_command(
                    [
                        required["psql"] or "psql",
                        "-X",
                        "-v",
                        "ON_ERROR_STOP=1",
                        "--dbname",
                        cls.database_url,
                        "-f",
                        str(migration),
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
            cls.postgres_tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.server_started:
            pg_ctl = shutil.which("pg_ctl") or "pg_ctl"
            subprocess.run(
                [pg_ctl, "-D", str(cls.data_dir), "-m", "fast", "-w", "stop"],
                text=True,
                capture_output=True,
                check=False,
            )
        cls.postgres_tmp.cleanup()

    def test_authority_binding_supersession_and_permit_are_append_only(self):
        first = append_ingestion_relevance_authority(
            self.store.run,
            content_ref="content:dp304:authority",
            canonical_url="https://example.test/a",
            relevance_reason="PUBLIC_ROLE",
            reviewer_ref="reviewer:dp304",
            audit_ref="audit:dp304:a",
            reviewed_at="2026-10-07T18:00:00+02:00",
        )
        current = require_current_ingestion_relevance(
            self.store.run,
            content_ref="content:dp304:authority",
            canonical_url="https://example.test/a",
        )
        self.assertEqual(current.authority_id, first.authority_id)

        operation_ref = deterministic_ingestion_operation_ref(
            "CAPTURE_FETCH", "content:dp304:authority", "capture-a"
        )
        permit = issue_ingestion_acquisition_permit(
            self.store.run,
            content_ref="content:dp304:authority",
            canonical_url="https://example.test/a",
            operation_kind="CAPTURE_FETCH",
            operation_ref=operation_ref,
        )

        second = append_ingestion_relevance_authority(
            self.store.run,
            content_ref="content:dp304:authority",
            canonical_url="https://example.test/b",
            relevance_reason="OFFICIAL_RECORD",
            reviewer_ref="reviewer:dp304",
            audit_ref="audit:dp304:b",
            reviewed_at="2026-10-07T18:05:00+02:00",
            supersedes_authority_id=first.authority_id,
        )
        self.assertEqual(second.review_sequence, 2)
        with self.assertRaisesRegex(IngestionRelevanceBlocked, "CONTENT_STALE"):
            require_current_ingestion_relevance(
                self.store.run,
                content_ref="content:dp304:authority",
                canonical_url="https://example.test/a",
            )
        with self.assertRaisesRegex(
            IngestionRelevanceBlocked, "INGESTION_ACQUISITION_PERMIT_STALE"
        ):
            require_ingestion_acquisition_permit(
                self.store.run,
                permit_id=permit.permit_id,
                content_ref="content:dp304:authority",
                canonical_url="https://example.test/a",
                operation_kind="CAPTURE_FETCH",
                operation_ref=operation_ref,
            )
        with self.assertRaisesRegex(IngestionRelevanceBlocked, "CONTENT_STALE"):
            issue_ingestion_acquisition_permit(
                self.store.run,
                content_ref="content:dp304:authority",
                canonical_url="https://example.test/a",
                operation_kind="CAPTURE_FETCH",
                operation_ref=deterministic_ingestion_operation_ref(
                    "CAPTURE_FETCH", "content:dp304:authority", "capture-after-stale"
                ),
            )
        with self.assertRaises(RuntimeError):
            self.store.run(
                "UPDATE privacy_ingestion_relevance_authority "
                "SET reviewer_ref='changed' WHERE authority_id=:'authority_id';",
                authority_id=second.authority_id,
            )
        with self.assertRaises(RuntimeError):
            self.store.run("TRUNCATE privacy_ingestion_acquisition_permit;")

    def test_missing_and_noncanonical_reason_fail_before_authorization(self):
        with self.assertRaisesRegex(IngestionRelevanceBlocked, "INGESTION_RELEVANCE_MISSING"):
            require_current_ingestion_relevance(
                self.store.run,
                content_ref="content:dp304:missing",
                canonical_url="https://example.test/missing",
            )
        before = self.store.run(
            "SELECT count(*)::text FROM privacy_ingestion_relevance_authority "
            "WHERE content_ref='content:dp304:invalid-reason';"
        )
        with self.assertRaisesRegex(ValueError, "INGESTION_RELEVANCE_REASON_INVALID"):
            append_ingestion_relevance_authority(
                self.store.run,
                content_ref="content:dp304:invalid-reason",
                canonical_url="https://example.test/invalid-reason",
                relevance_reason="IS_PUBLIC_FIGURE",
                reviewer_ref="reviewer:dp304",
                audit_ref="audit:dp304:invalid",
                reviewed_at="2026-10-07T18:10:00+02:00",
            )
        after = self.store.run(
            "SELECT count(*)::text FROM privacy_ingestion_relevance_authority "
            "WHERE content_ref='content:dp304:invalid-reason';"
        )
        self.assertEqual((before, after), ("0", "0"))

    def test_supersession_between_precheck_and_permit_is_blocked_deterministically(self):
        first = append_ingestion_relevance_authority(
            self.store.run,
            content_ref="content:dp304:race",
            canonical_url="https://example.test/race-a",
            relevance_reason="DOCUMENTED_PUBLIC_ACTIVITY",
            reviewer_ref="reviewer:dp304",
            audit_ref="audit:dp304:race-a",
            reviewed_at="2026-10-07T18:15:00+02:00",
        )
        permit_sql_reached = threading.Event()
        release_permit_sql = threading.Event()

        def paused_run(sql: str, **variables: object) -> str:
            if "INSERT INTO privacy_ingestion_acquisition_permit" in sql:
                permit_sql_reached.set()
                if not release_permit_sql.wait(timeout=10):
                    raise RuntimeError("test permit pause timeout")
            return self.store.run(sql, **variables)

        operation_ref = deterministic_ingestion_operation_ref(
            "CAPTURE_FETCH", "content:dp304:race", "race"
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                issue_ingestion_acquisition_permit,
                paused_run,
                content_ref="content:dp304:race",
                canonical_url="https://example.test/race-a",
                operation_kind="CAPTURE_FETCH",
                operation_ref=operation_ref,
            )
            self.assertTrue(permit_sql_reached.wait(timeout=10))
            append_ingestion_relevance_authority(
                self.store.run,
                content_ref="content:dp304:race",
                canonical_url="https://example.test/race-b",
                relevance_reason="OFFICIAL_RECORD",
                reviewer_ref="reviewer:dp304",
                audit_ref="audit:dp304:race-b",
                reviewed_at="2026-10-07T18:16:00+02:00",
                supersedes_authority_id=first.authority_id,
            )
            release_permit_sql.set()
            with self.assertRaisesRegex(
                IngestionRelevanceBlocked, "INGESTION_RELEVANCE_CHANGED_DURING_PERMIT"
            ):
                future.result(timeout=10)
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM privacy_ingestion_acquisition_permit "
                "WHERE operation_ref=:'operation_ref';",
                operation_ref=operation_ref,
            ),
            "0",
        )

    def test_scheduler_commit_rechecks_permit_atomically_after_supersession(self):
        item = DiscoveredContent(
            source_id="source:dp304:atomic",
            platform="youtube",
            external_id="atomic-video",
            title="Atomic relevance guard",
            canonical_url="https://example.test/atomic-video",
            published_at="2026-10-07T18:20:00+00:00",
            author="Example",
        )
        content_id = deterministic_content_id(provisional_content_key(item))
        append_ingestion_relevance_authority(
            self.store.run,
            content_ref=content_id,
            canonical_url=item.canonical_url,
            relevance_reason="DOCUMENTED_PUBLIC_ACTIVITY",
            reviewer_ref="reviewer:dp304",
            audit_ref="audit:dp304:scheduler-a",
            reviewed_at="2026-10-07T20:20:00+02:00",
        )

        class SupersedingStore(SchedulerPsqlStore):
            def issue_ingestion_acquisition_permit(self, **kwargs):
                permit = super().issue_ingestion_acquisition_permit(**kwargs)
                append_ingestion_relevance_authority(
                    self._run,
                    content_ref=kwargs["content_ref"],
                    canonical_url=kwargs["canonical_url"],
                    relevance_reason="OFFICIAL_RECORD",
                    reviewer_ref="reviewer:dp304",
                    audit_ref="audit:dp304:scheduler-b",
                    reviewed_at="2026-10-07T20:21:00+02:00",
                    supersedes_authority_id=permit.authority_id,
                )
                return permit

        scheduler_store = SupersedingStore(self.database_url)
        with self.assertRaisesRegex(RuntimeError, "INGESTION_ACQUISITION_PERMIT_STALE"):
            scheduler_store.commit_source_poll(
                {
                    "id": item.source_id,
                    "name": "Atomic source",
                    "kind": "youtube_channel",
                },
                [item],
                context=SourceRunContext(
                    run_id="source-poll-run:dp304:atomic",
                    mode="full-source",
                    run_date="2026-10-07",
                    effective_config_hash="b" * 64,
                ),
                max_new_jobs=1,
                cost_blocked=False,
                latest=item.published_at or "",
                omitted_items=0,
                started_at=datetime(2026, 10, 7, 18, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM content_item WHERE id=:'content_id';",
                content_id=content_id,
            ),
            "0",
        )
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM source WHERE id=:'source_id';",
                source_id=item.source_id,
            ),
            "0",
        )
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM processing_job WHERE content_id=:'content_id';",
                content_id=content_id,
            ),
            "0",
        )

    def test_fresh_schema_contains_replay_safe_migration_contract(self):
        migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261007-add-privacy-ingestion-relevance-authority.sql"
        ).read_text().strip()
        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        self.assertIn(migration, schema)


class IngestionRelevanceSeamTests(unittest.TestCase):
    def test_scheduler_blocks_before_content_persistence_or_enqueue(self):
        class MissingAuthorityStore(SchedulerPsqlStore):
            def __init__(self):
                self.calls = []

            def _run(self, sql: str, **variables: object) -> str:
                self.calls.append((sql, variables))
                if "FROM content_locator" in sql:
                    return ""
                if "FROM privacy_ingestion_relevance_authority" in sql:
                    return "[]"
                raise AssertionError("scheduler mutated before relevance authority")

        item = DiscoveredContent(
            source_id="source:dp304",
            platform="youtube",
            external_id="video-1",
            title="Relevant candidate",
            canonical_url="https://example.test/video-1",
            published_at="2026-10-07T16:00:00+00:00",
            author="Example",
        )
        store = MissingAuthorityStore()
        with self.assertRaisesRegex(IngestionRelevanceBlocked, "INGESTION_RELEVANCE_MISSING"):
            store.commit_source_poll(
                {"id": "source:dp304", "name": "Source", "kind": "youtube_channel"},
                [item],
                context=SourceRunContext(
                    run_id="source-poll-run:dp304",
                    mode="full-source",
                    run_date="2026-10-07",
                    effective_config_hash="a" * 64,
                ),
                max_new_jobs=1,
                cost_blocked=False,
                latest="",
                omitted_items=0,
                started_at=datetime(2026, 10, 7, 16, tzinfo=timezone.utc),
            )
        self.assertFalse(
            any("INSERT INTO content_item" in sql for sql, _ in store.calls)
        )
        self.assertFalse(
            any("enqueue_processing_job" in sql for sql, _ in store.calls)
        )

    def test_research_discovery_blocks_before_content_or_hit_persistence(self):
        class MissingAuthorityStore(ResearchDiscoveryStore):
            def __init__(self):
                self.calls = []

            def _relevance_content_ref(self, **kwargs):
                return kwargs["new_content_id"]

            def run(self, sql: str, **variables: object) -> str:
                self.calls.append((sql, variables))
                if "FROM content_item" in sql or "FROM content_locator" in sql:
                    return str(variables.get("new_content_id") or "")
                if "FROM privacy_ingestion_relevance_authority" in sql:
                    return "[]"
                raise AssertionError("discovery mutated before relevance authority")

        query = DiscoveryQuery(
            id="query:dp304",
            ordinal=0,
            query_text="bounded query",
            source_families=("web",),
            adapter_ids=("adapter:test",),
            seeds=(DiscoverySeed("url", "https://example.test/"),),
            max_results=1,
        )
        manifest = DiscoveryManifest(
            id="manifest:dp304",
            collection_id="collection:dp304",
            queries=(query,),
            seeds=query.seeds,
            source_families=("web",),
            date_from=None,
            date_to=None,
            max_results=1,
            max_results_per_host=1,
            cost_cap_usd=Decimal("1"),
            metadata={},
            manifest_sha256="a" * 64,
        )
        store = MissingAuthorityStore()
        with self.assertRaisesRegex(IngestionRelevanceBlocked, "INGESTION_RELEVANCE_MISSING"):
            store.record_hit(
                manifest=manifest,
                query=query,
                run_id="run:dp304",
                attempt_id="attempt:dp304",
                ordinal=0,
                candidate=DiscoveryHitCandidate(
                    canonical_url="https://example.test/discovered",
                    title="Discovered",
                ),
            )
        self.assertFalse(
            any("INSERT INTO content_item" in sql for sql, _ in store.calls)
        )
        self.assertFalse(
            any("INSERT INTO research_discovery_hit" in sql for sql, _ in store.calls)
        )

    def test_curated_written_blocks_before_source_or_content_mutation(self):
        class MissingAuthorityStore(QueueRuntimeStore):
            def __init__(self):
                self.calls = []

            def run(self, sql: str, **variables: object) -> str:
                self.calls.append((sql, variables))
                if "FROM privacy_ingestion_relevance_authority" in sql:
                    return "[]"
                raise AssertionError("curated intake mutated before relevance authority")

        store = MissingAuthorityStore()
        batch = prepare_curated_written_batch(_curated_payload())
        with self.assertRaisesRegex(IngestionRelevanceBlocked, "INGESTION_RELEVANCE_MISSING"):
            apply_curated_written_batch(
                store,
                batch,
                actor_ref="reviewer:dp304",
                approve_attribution=False,
            )
        self.assertFalse(any("INSERT INTO source" in sql for sql, _ in store.calls))
        self.assertFalse(any("INSERT INTO content_item" in sql for sql, _ in store.calls))

    def test_capture_blocks_before_network_fetch(self):
        class MissingAuthorityStore(CapturePipelineStore):
            def __init__(self):
                self.calls = []

            def run(self, sql: str, **variables: object) -> str:
                self.calls.append((sql, variables))
                if "FROM privacy_ingestion_relevance_authority" in sql:
                    return "[]"
                raise AssertionError("capture mutated before relevance authority")

        class CountingFetcher:
            def __init__(self):
                self.calls = 0

            def __call__(self, url, *, max_response_bytes):
                self.calls += 1
                return FetchedBytes(
                    body=b"<p>should not fetch</p>",
                    final_url=url,
                    status_code=200,
                    media_type="text/html",
                    charset="utf-8",
                    content_length=23,
                    etag=None,
                    last_modified=None,
                )

        store = MissingAuthorityStore()
        fetcher = CountingFetcher()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                CapturePipelineError, "INGESTION_RELEVANCE_MISSING"
            ):
                capture_content(
                    content_id="content:dp304:capture",
                    url="https://example.test/capture",
                    store=store,
                    body_store=CaptureBodyStore(Path(tmp)),
                    observed_at="2026-10-07T18:30:00+02:00",
                    fetcher=fetcher,
                )
        self.assertEqual(fetcher.calls, 0)


if __name__ == "__main__":
    unittest.main()

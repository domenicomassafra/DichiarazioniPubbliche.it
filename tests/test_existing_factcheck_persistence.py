from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claimreview_interop import (  # noqa: E402
    ClaimReviewInteropError,
    build_claimreview_interop,
)
from dichiarazioni_pubbliche.existing_factcheck import ExistingFactCheckRecord  # noqa: E402
from dichiarazioni_pubbliche.existing_factcheck_persistence import (  # noqa: E402
    ExistingFactCheckMirrorError,
    ExistingFactCheckMirrorStore,
    decide_mirror_excerpt,
    public_mirror_metadata,
)
from dichiarazioni_pubbliche.existing_factcheck_runtime import (  # noqa: E402
    ExistingFactCheckDiscoveryAdapter,
    ExistingFactCheckLookupResult,
    ExistingFactCheckMirrorCandidate,
    ExistingFactCheckRelevanceReview,
    ExistingFactCheckRuntimeError,
    run_existing_factcheck_assignment,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    EXCERPT_PUBLIC_USE_REQUIRED,
    ExcerptDisposition,
    ExcerptRequest,
    RightsStatus,
)
from dichiarazioni_pubbliche.public_projection import PublicProjectionStore  # noqa: E402
from dichiarazioni_pubbliche.research_plan import (  # noqa: E402
    ResearchAssignment,
    discovery_manifest_from_assignments,
)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def mirror_record(
    *,
    provider_id: str = "google-factcheck-tools",
    rating: str = "False",
) -> ExistingFactCheckRecord:
    return ExistingFactCheckRecord(
        record_id=f"existing-factcheck:{provider_id}:synthetic",
        provider_id=provider_id,
        claim_text="Synthetic reviewed claim body that must remain private by default.",
        claimant="Example claimant",
        claim_date="2026-09-01",
        review_publisher_name="Example Fact Check",
        review_publisher_site="factcheck.example",
        review_url="https://factcheck.example/reviews/claim-123",
        review_title="Synthetic review title",
        review_date="2026-09-02",
        textual_rating=rating,
        language_code="en",
    )


def source_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class ExistingFactCheckMirrorPostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    database_url: str
    admin_url: str
    store: ExistingFactCheckMirrorStore
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
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp232-factcheck-mirror-")
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
            cls._run_command(
                [
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.admin_url,
                    "-c",
                    "CREATE DATABASE dp232_factcheck_mirror;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp232_factcheck_mirror"
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
            cls._run_command(
                [
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.database_url,
                    "-f",
                    str(
                        ROOT
                        / "db"
                        / "migrations"
                        / "20261006-add-existing-factcheck-mirror-lineage.sql"
                    ),
                ]
            )
            cls.store = ExistingFactCheckMirrorStore(cls.database_url)
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
    def tearDownClass(cls):
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

    @classmethod
    def _recreate_fixture_database(cls) -> None:
        """Rebuild this append-only mirror fixture from the current schema."""

        psql = shutil.which("psql") or "psql"
        for statement in (
            "DROP DATABASE dp232_factcheck_mirror;",
            "CREATE DATABASE dp232_factcheck_mirror;",
        ):
            cls._run_command(
                [
                    psql,
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.admin_url,
                    "-c",
                    statement,
                ]
            )
        for path in (
            ROOT / "db" / "schema.v1.sql",
            ROOT / "db" / "migrations" / "20261006-add-existing-factcheck-mirror-lineage.sql",
            ROOT / "db" / "migrations" / "20261006-add-existing-factcheck-claim-binding.sql",
            ROOT / "db" / "migrations" / "20261006-add-existing-factcheck-claim-binding.sql",
        ):
            cls._run_command(
                [
                    psql,
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.database_url,
                    "-f",
                    str(path),
                ]
            )
        cls.store = ExistingFactCheckMirrorStore(cls.database_url)

    def setUp(self):
        self._recreate_fixture_database()

    def seed_retrieval(
        self,
        *,
        provider_id: str,
        external_id: str,
        suffix: str,
        assignment_id: str = "research-assignment:factcheck:1",
        lane: str = "EXISTING_FACT_CHECK",
        review_url: str = "https://factcheck.example/reviews/claim-123",
        atomic_claim_id: str | None = "claim:dp232:1",
    ) -> tuple[str, str]:
        collection_id = f"collection:dp232:{suffix}"
        coverage_need_id = f"coverage:dp232:{suffix}"
        manifest_id = f"manifest:dp232:{suffix}"
        query_id = f"query:dp232:{suffix}"
        run_id = f"run:dp232:{suffix}"
        attempt_id = f"attempt:dp232:{suffix}"
        hit_id = f"hit:dp232:{suffix}"
        hit_key = hashlib.sha256(f"{provider_id}:{external_id}:{suffix}".encode()).hexdigest()
        if atomic_claim_id is not None:
            self.store.run(
                """
                INSERT INTO content_item (id, canonical_url, processing_status)
                VALUES ('content:dp232:claim', 'https://example.test/dp232-claim', 'DISCOVERED')
                ON CONFLICT (id) DO NOTHING;
                INSERT INTO atomic_claim (
                    id, content_id, normalized_claim, claim_type, check_worthy
                ) VALUES (
                    :'atomic_claim_id', 'content:dp232:claim',
                    'Synthetic DP-232 claim.', 'NUMERIC_STATISTIC', true
                )
                ON CONFLICT (id) DO NOTHING;
                """,
                atomic_claim_id=atomic_claim_id,
            )
        self.store.run(
            """
            INSERT INTO research_collection (id, slug, name, scope_text, policy_version)
            VALUES (:'collection_id', :'slug', 'DP-232 fixture', 'fixture', 'test-v1');
            INSERT INTO coverage_need (
                id, collection_id, atomic_claim_id, need_type, requirement_kind,
                requirement_fingerprint, question, status, attempt_count, max_attempts
            ) VALUES (
                :'coverage_need_id', :'collection_id', NULLIF(:'atomic_claim_id',''),
                'INDEPENDENT_SOURCE', 'OTHER', :'requirement_fingerprint',
                'Was this claim already reviewed?', 'OPEN', 0, 3
            );
            INSERT INTO research_discovery_manifest (
                id, collection_id, manifest_sha256, max_results, max_results_per_host,
                cost_cap_usd, coverage_need_ids, status
            ) VALUES (
                :'manifest_id', :'collection_id', :'manifest_sha256', 10, 3, 0,
                :'coverage_need_ids'::jsonb, 'ACTIVE'
            );
            INSERT INTO research_discovery_query (
                id, manifest_id, ordinal, query_text, source_families, adapter_ids,
                max_results, metadata
            ) VALUES (
                :'query_id', :'manifest_id', 0, 'synthetic query', '["factcheck"]'::jsonb,
                :'adapter_ids'::jsonb, 10, :'query_metadata'::jsonb
            );
            INSERT INTO research_discovery_run (
                id, manifest_id, manifest_sha256, status
            ) VALUES (:'run_id', :'manifest_id', :'manifest_sha256', 'COMPLETED');
            INSERT INTO research_discovery_attempt (
                id, run_id, query_id, adapter_id, adapter_version, status, provider_receipt,
                completed_at
            ) VALUES (
                :'attempt_id', :'run_id', :'query_id', :'provider_id', 'fixture-v1', 'HEALTHY',
                :'provider_receipt'::jsonb, now()
            );
            INSERT INTO research_discovery_hit (
                id, run_id, attempt_id, query_id, hit_key, ordinal, canonical_url,
                source_host, source_family, external_id, disposition, metadata
            ) VALUES (
                :'hit_id', :'run_id', :'attempt_id', :'query_id', :'hit_key', 0,
                :'review_url', 'factcheck.example', 'factcheck', :'external_id',
                'NEW_CONTENT', '{}'::jsonb
            );
            """,
            collection_id=collection_id,
            slug=f"dp232-{suffix}",
            coverage_need_id=coverage_need_id,
            atomic_claim_id=atomic_claim_id or "",
            requirement_fingerprint=hashlib.sha256(
                f"{coverage_need_id}:{atomic_claim_id or 'collection-only'}".encode()
            ).hexdigest(),
            manifest_id=manifest_id,
            manifest_sha256=hashlib.sha256(manifest_id.encode()).hexdigest(),
            coverage_need_ids=json.dumps([coverage_need_id]),
            query_id=query_id,
            adapter_ids=json.dumps([provider_id]),
            query_metadata=json.dumps(
                {
                    "research_assignment_id": assignment_id,
                    "coverage_need_id": coverage_need_id,
                    "lane": lane,
                    "plan_version": "research-plan-v1",
                },
                sort_keys=True,
            ),
            run_id=run_id,
            attempt_id=attempt_id,
            provider_id=provider_id,
            provider_receipt=json.dumps(
                {
                    "query_sha256": hashlib.sha256(b"synthetic query").hexdigest(),
                    "page_size": 10,
                },
                sort_keys=True,
            ),
            hit_id=hit_id,
            hit_key=hit_key,
            review_url=review_url,
            external_id=external_id,
        )
        return attempt_id, hit_id

    def persist(
        self,
        *,
        provider_id: str = "google-factcheck-tools",
        external_id: str = "mirror:claim-123",
        source_version: str = "claimreview-v1",
        source_content_sha256: str | None = None,
        upstream_record_id: str = "claimreview:factcheck.example:claim-123",
        rights_status: RightsStatus | str = RightsStatus.UNKNOWN,
        supersedes_source_version: str | None = None,
        suffix: str = "one",
        record: ExistingFactCheckRecord | None = None,
        assignment_id: str = "research-assignment:factcheck:1",
    ):
        attempt_id, hit_id = self.seed_retrieval(
            provider_id=provider_id,
            external_id=external_id,
            suffix=suffix,
            assignment_id=assignment_id,
        )
        return self.store.persist_mirror(
            record or mirror_record(provider_id=provider_id),
            upstream_record_id=upstream_record_id,
            source_external_id=external_id,
            source_version=source_version,
            source_content_sha256=(
                source_content_sha256 or source_hash(f"{upstream_record_id}:{source_version}")
            ),
            research_assignment_id=assignment_id,
            discovery_attempt_id=attempt_id,
            discovery_hit_id=hit_id,
            rights_status=rights_status,
            supersedes_source_version=supersedes_source_version,
        )

    def excerpt_request(self, mirror, *, caller_rights=RightsStatus.CLEARED):
        return ExcerptRequest(
            excerpt_text="Synthetic reviewed claim body that must remain private by default.",
            rights_status=caller_rights,
            permitted_public_uses=(EXCERPT_PUBLIC_USE_REQUIRED,),
            rights_reviewed_on="2026-10-06",
            today="2026-10-06",
            source_url=mirror.review_url,
            content_id=mirror.version_id,
            segment_id=mirror.mirror_id,
            transcript_variant_id=mirror.source_version,
            timestamp_start_seconds=0.0,
            timestamp_end_seconds=5.0,
            source_content_sha256=mirror.source_content_sha256,
            observed_source_sha256=mirror.source_content_sha256,
            excerpt_review_approved=True,
            profile_approved=True,
            max_excerpt_chars=200,
        )

    def test_exact_replay_is_idempotent_and_binds_dp228_dp209_receipt(self):
        attempt_id, hit_id = self.seed_retrieval(
            provider_id="google-factcheck-tools",
            external_id="mirror:claim-123",
            suffix="replay",
        )
        values = dict(
            record=mirror_record(),
            upstream_record_id="claimreview:factcheck.example:claim-123",
            source_external_id="mirror:claim-123",
            source_version="claimreview-v1",
            source_content_sha256=source_hash("claimreview-v1"),
            research_assignment_id="research-assignment:factcheck:1",
            discovery_attempt_id=attempt_id,
            discovery_hit_id=hit_id,
            rights_status=RightsStatus.UNKNOWN,
        )
        first = self.store.persist_mirror(**values)
        second = self.store.persist_mirror(**values)
        self.assertEqual(first, second)
        self.assertEqual(first.discovery_attempt_id, attempt_id)
        self.assertEqual(first.discovery_hit_id, hit_id)
        self.assertEqual(first.atomic_claim_id, "claim:dp232:1")
        self.assertEqual(first.research_assignment_id, "research-assignment:factcheck:1")
        self.assertRegex(first.provider_receipt_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_mirror;"),
            "1",
        )

    def test_same_upstream_claimreview_across_providers_is_one_lineage(self):
        first = self.persist(suffix="google")
        second = self.persist(
            provider_id="cimple-claimreview",
            external_id="cimple:mirror:claim-123",
            suffix="cimple",
            record=mirror_record(provider_id="cimple-claimreview"),
        )
        self.assertEqual(first.lineage_id, second.lineage_id)
        self.assertEqual(first.version_id, second.version_id)
        self.assertNotEqual(first.mirror_id, second.mirror_id)
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_lineage;"),
            "1",
        )
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_version;"),
            "1",
        )
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_mirror;"),
            "2",
        )

    def test_new_version_requires_explicit_supersession_and_preserves_history(self):
        old = self.persist(suffix="old")
        with self.assertRaisesRegex(ExistingFactCheckMirrorError, "SUPERSEDES_REQUIRED"):
            self.persist(
                source_version="claimreview-v2",
                source_content_sha256=source_hash("claimreview-v2"),
                suffix="missing-supersedes",
            )
        new = self.persist(
            source_version="claimreview-v2",
            source_content_sha256=source_hash("claimreview-v2"),
            supersedes_source_version="claimreview-v1",
            suffix="new",
        )
        old_after = self.store.read_mirror(old.mirror_id)
        self.assertEqual(old_after.version_state, "HISTORICAL")
        self.assertEqual(new.version_state, "CURRENT")
        self.assertEqual(new.supersedes_version_id, old.version_id)
        self.assertEqual(old.source_content_sha256, source_hash("claimreview:factcheck.example:claim-123:claimreview-v1"))
        self.assertEqual(new.source_content_sha256, source_hash("claimreview-v2"))

    def test_conflicting_same_external_id_and_version_fails_closed(self):
        attempt_id, hit_id = self.seed_retrieval(
            provider_id="google-factcheck-tools",
            external_id="mirror:conflict",
            suffix="conflict",
        )
        values = dict(
            upstream_record_id="claimreview:factcheck.example:conflict",
            source_external_id="mirror:conflict",
            source_version="v1",
            source_content_sha256=source_hash("conflict-v1"),
            research_assignment_id="research-assignment:factcheck:1",
            discovery_attempt_id=attempt_id,
            discovery_hit_id=hit_id,
            rights_status=RightsStatus.UNKNOWN,
        )
        self.store.persist_mirror(mirror_record(), **values)
        with self.assertRaisesRegex(ExistingFactCheckMirrorError, "EXTERNAL_ID_CONFLICT"):
            self.store.persist_mirror(
                mirror_record(rating="Changed wrapper rating"),
                **values,
            )

    def test_wrong_dp228_lane_or_assignment_fails_closed(self):
        attempt_id, hit_id = self.seed_retrieval(
            provider_id="google-factcheck-tools",
            external_id="mirror:wrong-lane",
            suffix="wrong-lane",
            lane="PRIMARY_SOURCE",
        )
        with self.assertRaisesRegex(ExistingFactCheckMirrorError, "RESEARCH_LANE_MISMATCH"):
            self.store.persist_mirror(
                mirror_record(),
                upstream_record_id="claimreview:factcheck.example:wrong-lane",
                source_external_id="mirror:wrong-lane",
                source_version="v1",
                source_content_sha256=source_hash("wrong-lane"),
                research_assignment_id="research-assignment:factcheck:1",
                discovery_attempt_id=attempt_id,
                discovery_hit_id=hit_id,
            )

    def test_real_dp228_to_dp209_compiler_preserves_assignment_binding(self):
        assignment = ResearchAssignment(
            assignment_id="research-assignment:factcheck:compiled",
            coverage_need_id="coverage:dp232:compiled",
            lane="EXISTING_FACT_CHECK",
            question="Was this claim already reviewed?",
            adapter_ids=("google-factcheck-tools",),
            max_queries=1,
            max_results=5,
            max_results_per_host=2,
            cost_cap_usd=Decimal("0"),
            temporal_constraints={},
            authority_scope={},
            stop_conditions=("REQUIREMENT_SATISFIED",),
        )
        manifest = discovery_manifest_from_assignments(
            (assignment,),
            collection_id="collection:dp232:compiled",
            lane_source_families={"EXISTING_FACT_CHECK": ("factcheck",)},
        )
        self.assertEqual(len(manifest.queries), 1)
        query = manifest.queries[0]
        self.assertEqual(query.id, assignment.assignment_id)
        self.assertEqual(query.metadata["research_assignment_id"], assignment.assignment_id)
        self.assertEqual(query.metadata["lane"], "EXISTING_FACT_CHECK")
        self.assertEqual(query.adapter_ids, ("google-factcheck-tools",))
        self.assertEqual(query.max_results, 5)

    def _runtime_assignment(
        self,
        *,
        adapter_ids=("google-factcheck-tools",),
        lane="EXISTING_FACT_CHECK",
        max_queries=2,
        max_results=2,
        max_results_per_host=1,
        cost_cap_usd=Decimal("0.250000"),
    ):
        return ResearchAssignment(
            assignment_id="research-assignment:factcheck:runtime",
            coverage_need_id="coverage:dp232:runtime",
            lane=lane,
            question="Was the runtime claim already reviewed?",
            adapter_ids=adapter_ids,
            max_queries=max_queries,
            max_results=max_results,
            max_results_per_host=max_results_per_host,
            cost_cap_usd=cost_cap_usd,
            temporal_constraints={},
            authority_scope={},
            stop_conditions=(
                "REQUIREMENT_SATISFIED",
                "MAX_ATTEMPTS_REACHED",
                "COST_CAP_REACHED",
            ),
        )

    def _runtime_collection(self, suffix="runtime"):
        collection_id = f"collection:dp232:{suffix}"
        self.store.run(
            """
            INSERT INTO content_item (id, canonical_url, processing_status)
            VALUES ('content:dp232:runtime', 'https://example.test/dp232-runtime', 'DISCOVERED')
            ON CONFLICT (id) DO NOTHING;
            INSERT INTO atomic_claim (
                id, content_id, normalized_claim, claim_type, check_worthy
            ) VALUES (
                'claim:dp232:runtime', 'content:dp232:runtime',
                'Synthetic DP-232 runtime claim.', 'NUMERIC_STATISTIC', true
            )
            ON CONFLICT (id) DO NOTHING;
            INSERT INTO research_collection (id, slug, name, scope_text, policy_version)
            VALUES (:'id', :'slug', 'DP-232 runtime', 'runtime fixture', 'test-v1');
            INSERT INTO coverage_need (
                id, collection_id, atomic_claim_id, need_type, requirement_kind,
                requirement_fingerprint, question, status, attempt_count, max_attempts
            ) VALUES (
                'coverage:dp232:runtime', :'id', 'claim:dp232:runtime',
                'INDEPENDENT_SOURCE', 'OTHER',
                :'fingerprint', 'Was the runtime claim already reviewed?', 'OPEN', 0, 3
            );
            """,
            id=collection_id,
            slug=f"dp232-{suffix}",
            fingerprint=hashlib.sha256(
                f"coverage:dp232:runtime:{suffix}".encode()
            ).hexdigest(),
        )
        return collection_id

    def _runtime_candidate(self, *, external_id="mirror:runtime:1"):
        return ExistingFactCheckMirrorCandidate(
            record=mirror_record(),
            upstream_record_id="claimreview:factcheck.example:runtime-1",
            source_external_id=external_id,
            source_version="claimreview-runtime-v1",
            source_content_sha256=source_hash("claimreview-runtime-v1"),
        )

    def _runtime_relevance_review(self, *, external_id="mirror:runtime:1"):
        return ExistingFactCheckRelevanceReview(
            provider_id="google-factcheck-tools",
            source_external_id=external_id,
            relevance_reason="DOCUMENTED_PUBLIC_ACTIVITY",
            reviewer_ref="reviewer:dp304:existing-factcheck",
            audit_ref="audit:dp304:existing-factcheck",
            reviewed_at="2026-10-07T20:00:00+02:00",
        )

    def test_runtime_executes_persisted_dp228_dp209_bounds_and_appends_unknown_rights_mirror(self):
        collection_id = self._runtime_collection("runtime-bounds")
        assignment = self._runtime_assignment()
        seen = []

        def lookup(request):
            seen.append(request)
            return ExistingFactCheckLookupResult(
                candidates=(self._runtime_candidate(),),
                provider_receipt={
                    "query_sha256": hashlib.sha256(request.query_text.encode()).hexdigest(),
                    "page_size": request.page_size,
                },
                cost_usd=Decimal("0.125000"),
            )

        adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=Decimal("0.200000"),
            lookup=lookup,
        )
        result = run_existing_factcheck_assignment(
            assignment,
            collection_id=collection_id,
            database_url=self.database_url,
            adapters={"google-factcheck-tools": adapter},
            relevance_reviews=(self._runtime_relevance_review(),),
            run_id="run:dp232:runtime-bounds",
        )

        self.assertEqual(result.run.status, "COMPLETED")
        self.assertFalse(result.publication_authority)
        self.assertEqual(len(result.mirrors), 1)
        self.assertEqual(result.mirrors[0].rights_status, RightsStatus.UNKNOWN.value)
        self.assertEqual(result.mirrors[0].atomic_claim_id, "claim:dp232:runtime")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].query_text, assignment.question)
        self.assertEqual(seen[0].page_size, assignment.max_results)
        self.assertEqual(seen[0].remaining_cost_usd, assignment.cost_cap_usd)
        self.assertEqual(seen[0].research_assignment_id, assignment.assignment_id)

        persisted = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                    'max_results', manifest.max_results,
                    'max_results_per_host', manifest.max_results_per_host,
                    'cost_cap_usd', manifest.cost_cap_usd::text,
                    'query_text', query.query_text,
                    'query_max_results', query.max_results,
                    'remaining_attempts', query.metadata->>'remaining_attempts',
                    'assignment_id', query.metadata->>'research_assignment_id',
                    'lane', query.metadata->>'lane',
                    'attempt_cost_upper', attempt.cost_upper_bound_usd::text,
                    'attempt_cost', attempt.cost_usd::text,
                    'attempt_status', attempt.status,
                    'receipt_page_size', attempt.provider_receipt->>'page_size'
                )::text
                FROM research_discovery_manifest manifest
                JOIN research_discovery_query query ON query.manifest_id=manifest.id
                JOIN research_discovery_run run ON run.manifest_id=manifest.id
                JOIN research_discovery_attempt attempt ON attempt.run_id=run.id
                WHERE run.id='run:dp232:runtime-bounds';
                """
            )
        )
        self.assertEqual(persisted["max_results"], assignment.max_results)
        self.assertEqual(persisted["max_results_per_host"], assignment.max_results_per_host)
        self.assertEqual(Decimal(persisted["cost_cap_usd"]), assignment.cost_cap_usd)
        self.assertEqual(persisted["query_text"], assignment.question)
        self.assertEqual(persisted["query_max_results"], assignment.max_results)
        self.assertEqual(int(persisted["remaining_attempts"]), assignment.max_queries)
        self.assertEqual(persisted["assignment_id"], assignment.assignment_id)
        self.assertEqual(persisted["lane"], "EXISTING_FACT_CHECK")
        self.assertEqual(Decimal(persisted["attempt_cost_upper"]), Decimal("0.200000"))
        self.assertEqual(Decimal(persisted["attempt_cost"]), Decimal("0.125000"))
        self.assertEqual(persisted["attempt_status"], "HEALTHY")
        self.assertEqual(int(persisted["receipt_page_size"]), assignment.max_results)

    def test_runtime_replay_same_run_is_idempotent_without_second_lookup(self):
        collection_id = self._runtime_collection("runtime-replay")
        assignment = self._runtime_assignment()
        calls = []

        def lookup(request):
            calls.append(request)
            return ExistingFactCheckLookupResult(
                candidates=(self._runtime_candidate(),),
                provider_receipt={"page_size": request.page_size},
            )

        first_adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=0,
            lookup=lookup,
        )
        first = run_existing_factcheck_assignment(
            assignment,
            collection_id=collection_id,
            database_url=self.database_url,
            adapters={"google-factcheck-tools": first_adapter},
            relevance_reviews=(self._runtime_relevance_review(),),
            run_id="run:dp232:runtime-replay",
        )

        second_adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=0,
            lookup=lambda request: self.fail("completed DP-209 run must not call lookup again"),
        )
        second = run_existing_factcheck_assignment(
            assignment,
            collection_id=collection_id,
            database_url=self.database_url,
            adapters={"google-factcheck-tools": second_adapter},
            relevance_reviews=(self._runtime_relevance_review(),),
            run_id="run:dp232:runtime-replay",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(first.mirrors, second.mirrors)
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_mirror;"),
            "1",
        )

    def test_runtime_missing_relevance_authority_blocks_without_hit_or_mirror(self):
        collection_id = self._runtime_collection("runtime-relevance-missing")
        assignment = self._runtime_assignment()
        calls = []

        def lookup(request):
            calls.append(request)
            return ExistingFactCheckLookupResult(
                candidates=(self._runtime_candidate(),),
                provider_receipt={"page_size": request.page_size},
            )

        adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=0,
            lookup=lookup,
        )
        result = run_existing_factcheck_assignment(
            assignment,
            collection_id=collection_id,
            database_url=self.database_url,
            adapters={"google-factcheck-tools": adapter},
            run_id="run:dp232:runtime-relevance-missing",
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result.run.status, "BLOCKED")
        self.assertEqual(result.mirrors, ())
        self.assertEqual(
            self.store.run("SELECT count(*) FROM research_discovery_hit;"),
            "0",
        )
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_mirror;"),
            "0",
        )

    def test_runtime_cost_cap_blocks_prelookup_and_persists_no_mirror(self):
        collection_id = self._runtime_collection("runtime-cost")
        assignment = self._runtime_assignment(cost_cap_usd=Decimal("0.100000"))
        calls = []
        adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=Decimal("0.200000"),
            lookup=lambda request: calls.append(request),
        )
        result = run_existing_factcheck_assignment(
            assignment,
            collection_id=collection_id,
            database_url=self.database_url,
            adapters={"google-factcheck-tools": adapter},
            run_id="run:dp232:runtime-cost",
        )
        self.assertEqual(calls, [])
        self.assertEqual(result.run.status, "BLOCKED")
        self.assertEqual(result.mirrors, ())
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_mirror;"),
            "0",
        )

    def test_runtime_overbound_lookup_fails_closed_without_mirror(self):
        collection_id = self._runtime_collection("runtime-overbound")
        assignment = self._runtime_assignment(max_results=1, max_results_per_host=1)

        def lookup(request):
            return ExistingFactCheckLookupResult(
                candidates=(
                    self._runtime_candidate(external_id="mirror:runtime:1"),
                    self._runtime_candidate(external_id="mirror:runtime:2"),
                ),
                provider_receipt={"page_size": request.page_size},
            )

        adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=0,
            lookup=lookup,
        )
        result = run_existing_factcheck_assignment(
            assignment,
            collection_id=collection_id,
            database_url=self.database_url,
            adapters={"google-factcheck-tools": adapter},
            run_id="run:dp232:runtime-overbound",
        )
        self.assertEqual(result.run.status, "FAILED")
        self.assertEqual(result.mirrors, ())
        self.assertEqual(
            self.store.run("SELECT count(*) FROM existing_factcheck_mirror;"),
            "0",
        )

    def test_runtime_refuses_lane_or_adapter_permission_expansion_before_lookup(self):
        collection_id = self._runtime_collection("runtime-permissions")
        adapter = ExistingFactCheckDiscoveryAdapter(
            provider_id="google-factcheck-tools",
            adapter_version="existing-factcheck-offline-v1",
            source_family="existing_factcheck",
            cost_upper_bound_usd=0,
            lookup=lambda request: self.fail("invalid runtime input must not reach lookup"),
        )
        with self.assertRaisesRegex(ExistingFactCheckRuntimeError, "LANE_REQUIRED"):
            run_existing_factcheck_assignment(
                self._runtime_assignment(lane="PRIMARY_SOURCE"),
                collection_id=collection_id,
                database_url=self.database_url,
                adapters={"google-factcheck-tools": adapter},
            )
        with self.assertRaisesRegex(ExistingFactCheckRuntimeError, "PERMISSION_EXPANSION"):
            run_existing_factcheck_assignment(
                self._runtime_assignment(),
                collection_id=collection_id,
                database_url=self.database_url,
                adapters={
                    "google-factcheck-tools": adapter,
                    "not-permitted": adapter,
                },
            )

    def test_unknown_or_blocked_rights_cannot_be_upgraded_by_excerpt_caller(self):
        unknown = self.persist(suffix="unknown-rights", rights_status=RightsStatus.UNKNOWN)
        unknown_decision = decide_mirror_excerpt(
            unknown,
            self.excerpt_request(unknown, caller_rights=RightsStatus.CLEARED),
        )
        self.assertEqual(unknown_decision.disposition, ExcerptDisposition.PROHIBITED)

        blocked = self.persist(
            provider_id="cimple-claimreview",
            external_id="cimple:blocked",
            upstream_record_id="claimreview:factcheck.example:blocked",
            suffix="blocked-rights",
            rights_status=RightsStatus.BLOCKED,
            record=mirror_record(provider_id="cimple-claimreview"),
        )
        blocked_decision = decide_mirror_excerpt(
            blocked,
            self.excerpt_request(blocked, caller_rights=RightsStatus.CLEARED),
        )
        self.assertEqual(blocked_decision.disposition, ExcerptDisposition.PROHIBITED)

    def test_public_boundary_is_metadata_link_only_and_not_claimreview_input(self):
        mirror = self.persist(suffix="public-boundary")
        public = public_mirror_metadata(mirror)
        encoded = json.dumps(dataclasses.asdict(public), sort_keys=True)
        for private in (
            "claim_text",
            "textual_rating",
            "review_title",
            "claimant",
            "normalized_record",
            "Synthetic reviewed claim body",
            "False",
        ):
            self.assertNotIn(private, encoded)
        self.assertIn("https://factcheck.example/reviews/claim-123", encoded)
        self.assertIn("Example Fact Check", encoded)
        with self.assertRaisesRegex(ClaimReviewInteropError, "FINDING_REQUIRED"):
            build_claimreview_interop(dataclasses.asdict(public))

        projection_store = PublicProjectionStore(self.database_url)
        self.assertEqual(projection_store.projectable_findings(), [])
        projection_source = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py"
        ).read_text(encoding="utf-8")
        self.assertIn("existing_factcheck_mirror", projection_source)
        self.assertIn("existing_factcheck_version", projection_source)
        self.assertIn("AS existing_factchecks", projection_source)
        self.assertIn("WHERE mirror.atomic_claim_id = claim.id", projection_source)

    def test_collection_only_claim_binding_remains_private_and_unprojectable(self):
        attempt_id, hit_id = self.seed_retrieval(
            provider_id="google-factcheck-tools",
            external_id="mirror:collection-only",
            suffix="collection-only",
            atomic_claim_id=None,
        )
        mirror = self.store.persist_mirror(
            mirror_record(),
            upstream_record_id="claimreview:factcheck.example:collection-only",
            source_external_id="mirror:collection-only",
            source_version="claimreview-v1",
            source_content_sha256=source_hash("claimreview:collection-only:v1"),
            research_assignment_id="research-assignment:factcheck:1",
            discovery_attempt_id=attempt_id,
            discovery_hit_id=hit_id,
        )
        self.assertIsNone(mirror.atomic_claim_id)

    def test_materialized_claim_binding_is_restrictive_and_immutable(self):
        mirror = self.persist(suffix="claim-fk")
        self.assertEqual(mirror.atomic_claim_id, "claim:dp232:1")
        with self.assertRaises(RuntimeError):
            self.store.run("DELETE FROM atomic_claim WHERE id='claim:dp232:1';")
        self.assertEqual(
            self.store.read_mirror(mirror.mirror_id).atomic_claim_id,
            "claim:dp232:1",
        )


if __name__ == "__main__":
    unittest.main()

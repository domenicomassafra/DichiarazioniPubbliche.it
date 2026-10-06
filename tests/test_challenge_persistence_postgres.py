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

from dichiarazioni_pubbliche.challenge_persistence import (  # noqa: E402
    ChallengeHoldDisposition,
    ChallengePersistenceError,
    PrivateChallengeLedgerStore,
)
from dichiarazioni_pubbliche.challenge_intake import (  # noqa: E402
    ChallengeLaunchProfile,
    ChallengeServiceReason,
    ChallengeServiceState,
    submit_challenge,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import (  # noqa: E402
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
)
from dichiarazioni_pubbliche.policy.intake_policy import (  # noqa: E402
    RateLimitProfile,
    RateLimitState,
    RateScope,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class PrivateChallengeLedgerPostgresTests(unittest.TestCase):
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
        return cls._run_command(
            [
                shutil.which("psql") or "psql",
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
        cls._run_command(
            [
                shutil.which("psql") or "psql",
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
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp303-challenge-ledger-")
        root = Path(cls.postgres_tmp.name)
        cls.data_dir = root / "data"
        cls.port = _free_tcp_port()
        migration = ROOT / "db" / "migrations" / "20261006-add-private-challenge-ledger.sql"
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
                "CREATE DATABASE dp303_challenge_fresh; "
                "CREATE DATABASE dp303_challenge_migration;",
            )
            cls.fresh_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp303_challenge_fresh"
            )
            cls.migration_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp303_challenge_migration"
            )
            cls._apply_file(cls.fresh_url, ROOT / "db" / "schema.v1.sql")
            cls._apply_file(cls.fresh_url, migration)
            cls._apply_file(cls.fresh_url, migration)
            cls._psql(
                cls.migration_url,
                "CREATE TABLE finding (id text PRIMARY KEY); "
                "INSERT INTO finding(id) VALUES ('finding:migration');",
            )
            cls._apply_file(cls.migration_url, migration)
            cls._apply_file(cls.migration_url, migration)
            cls._seed_fresh_content()
            cls.store = PrivateChallengeLedgerStore(cls.fresh_url)
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
    def _seed_fresh_content(cls) -> None:
        cls._psql(
            cls.fresh_url,
            """
            INSERT INTO content_item(id, canonical_url)
            VALUES ('content:dp303', 'https://example.test/dp303');
            """,
        )

    @classmethod
    def tearDownClass(cls) -> None:
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

    def setUp(self) -> None:
        # Append-only ledgers cannot be reset. Each test owns a distinct target Finding.
        suffix = self._testMethodName.replace("_", "-")
        self.claim_id = f"claim:dp303:{suffix}"
        self.finding_id = f"finding:dp303:{suffix}"
        self._psql(
            self.fresh_url,
            f"""
            INSERT INTO atomic_claim(
                id, content_id, normalized_claim, claim_type, temporal_scope,
                check_worthy, metadata
            ) VALUES (
                '{self.claim_id}', 'content:dp303', 'DP-303 fixture claim {suffix}',
                'CURRENT_POLICY', '{{}}'::jsonb, true, '{{}}'::jsonb
            );
            INSERT INTO finding(
                id, claim_id, assessment, rationale, publication_status,
                policy_version, model_bundle
            ) VALUES (
                '{self.finding_id}', '{self.claim_id}', 'SUPPORTED', 'fixture rationale',
                'PUBLISH', 'policy:dp303:v1', '{{}}'::jsonb
            );
            """,
        )

    def _init(
        self,
        suffix: str,
        *,
        kind: ChallengeKind = ChallengeKind.TAKEDOWN,
        role: ChallengeRole = ChallengeRole.INTAKE_ADAPTER,
        prior_decision_ref: str | None = None,
    ):
        return self.store.initiate_request(
            kind=kind,
            target_finding_id=self.finding_id,
            source_request_ref=f"challenge:test:{suffix}",
            actor_ref=f"actor:{suffix}",
            actor_role=role,
            reason=f"Private challenge reason {suffix}",
            prior_decision_ref=prior_decision_ref,
        )

    def _to_triage(self, suffix: str):
        root = self._init(suffix)
        moved = self.store.transition_request(
            root.request.request_id,
            actor_ref="dp303-intake-adapter",
            actor_role=ChallengeRole.INTAKE_ADAPTER,
            reason=f"Private challenge reason {suffix}",
        )
        self.assertEqual(moved.event.to_state, ChallengeState.TRIAGE_PENDING)
        return root.request.request_id

    def test_takedown_hold_requires_explicit_reviewed_transition(self):
        request_id = self._to_triage("reviewed-hold")
        held = self.store.transition_request(
            request_id,
            actor_ref="reviewer:triage",
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            reason="Reviewed private takedown request",
            challenge_review_approved=True,
        )
        self.assertEqual(held.event.to_state, ChallengeState.PUBLIC_HOLD_APPROVED)
        hold = self.store.current_hold_for_finding(self.finding_id)
        self.assertEqual(hold.disposition, ChallengeHoldDisposition.HOLD)
        self.assertFalse(hold.blocked)
        self.assertEqual(hold.request_id, request_id)

        with self.assertRaises(RuntimeError):
            self.store.run(
                "UPDATE private_challenge_event SET to_state='REFERRED' "
                "WHERE event_id=:'event_id';",
                event_id=held.event.event_id,
            )

    def test_unreviewed_takedown_cannot_create_hold(self):
        request_id = self._to_triage("unreviewed")
        referred = self.store.transition_request(
            request_id,
            actor_ref="reviewer:triage:unreviewed",
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            reason="No reviewed hold approval",
            challenge_review_approved=False,
        )
        self.assertEqual(referred.event.to_state, ChallengeState.REFERRED)
        replay = self.store.replay_request(request_id)
        self.assertEqual(replay.current_state, ChallengeState.REFERRED)

    def test_public_submitter_can_initiate_but_cannot_advance(self):
        root = self._init(
            "public-submitter",
            role=ChallengeRole.PUBLIC_SUBMITTER,
        )
        self.assertEqual(root.event.to_state, ChallengeState.PRIVATE_RECEIVED)
        with self.assertRaisesRegex(
            ChallengePersistenceError, "CHALLENGE_PUBLIC_SUBMITTER_TRANSITION_FORBIDDEN"
        ):
            self.store.transition_request(
                root.request.request_id,
                actor_ref="public:submitter",
                actor_role=ChallengeRole.PUBLIC_SUBMITTER,
                reason="Public submitter cannot triage",
            )
        self.assertEqual(len(self.store.replay_request(root.request.request_id).events), 1)

    def test_stale_finding_binding_fails_hold_read_closed(self):
        request_id = self._to_triage("stale")
        self.store.transition_request(
            request_id,
            actor_ref="reviewer:triage:stale",
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            reason="Reviewed before target changed",
            challenge_review_approved=True,
        )
        self.store.run(
            "UPDATE finding SET rationale='fixture rationale changed' "
            "WHERE id=:'finding_id';",
            finding_id=self.finding_id,
        )
        result = self.store.current_hold_for_finding(self.finding_id)
        self.assertEqual(result.disposition, ChallengeHoldDisposition.UNKNOWN)
        self.assertTrue(result.blocked)
        self.assertIn("CHALLENGE_HOLD_RECORD_VERSION_STALE", result.blockers)

        # Restore only the mutable Finding fixture, never the append-only challenge ledger.
        self.store.run(
            "UPDATE finding SET rationale='fixture rationale' WHERE id=:'finding_id';",
            finding_id=self.finding_id,
        )

    def test_malformed_direct_hold_event_is_unknown_not_authoritative(self):
        request_id = self._to_triage("malformed")
        replay = self.store.replay_request(request_id)
        parent = replay.events[-1]
        fake_hash = "f" * 64
        self.store.run(
            """
            INSERT INTO private_challenge_event (
                event_id, event_version, request_id, challenge_kind, event_sequence,
                from_state, to_state, actor_ref, actor_role, reason, policy_version,
                target_record_version, transition_context, previous_event_id,
                previous_integrity_sha256, event_integrity_sha256
            ) VALUES (
                :'event_id', 'private-challenge-event-v1', :'request_id', 'TAKEDOWN',
                :'sequence'::integer, 'TRIAGE_PENDING', 'PUBLIC_HOLD_APPROVED',
                'dp303-intake-adapter', 'INTAKE_ADAPTER', 'malformed direct hold',
                'challenge-workflow-v1', :'record_version',
                '{"challenge_review_approved":true}'::jsonb, :'previous_event_id',
                :'previous_integrity', :'integrity'
            );
            """,
            event_id=f"challenge-event:{fake_hash}",
            request_id=request_id,
            sequence=parent.sequence + 1,
            record_version=replay.request.target_record_version,
            previous_event_id=parent.event_id,
            previous_integrity=parent.event_integrity_sha256,
            integrity=fake_hash,
        )
        result = self.store.current_hold_for_finding(self.finding_id)
        self.assertEqual(result.disposition, ChallengeHoldDisposition.UNKNOWN)
        self.assertTrue(result.blocked)
        self.assertTrue(
            {"CHALLENGE_EVENT_INTEGRITY_INVALID", "CHALLENGE_EVENT_POLICY_REPLAY_INVALID"}
            & set(result.blockers)
        )

    def test_appeal_records_separation_context_without_editing_prior_decision(self):
        root = self._init(
            "appeal-exception",
            kind=ChallengeKind.APPEAL,
            prior_decision_ref="review:prior:opaque",
        )
        pending = self.store.transition_request(
            root.request.request_id,
            actor_ref="dp303-intake-adapter",
            actor_role=ChallengeRole.INTAKE_ADAPTER,
            reason="Route private appeal to independent review",
        )
        self.assertEqual(
            pending.event.to_state, ChallengeState.INDEPENDENT_REVIEW_PENDING
        )
        decided = self.store.transition_request(
            root.request.request_id,
            actor_ref="reviewer:same",
            actor_role=ChallengeRole.APPEAL_REVIEWER,
            reason="Explicit staffing exception recorded",
            challenge_review_approved=True,
            original_reviewer_id="reviewer:same",
            separation_exception_recorded=True,
            reanalysis_trigger_processed=True,
            target_finding_review_approved=True,
        )
        self.assertEqual(decided.event.to_state, ChallengeState.UPHELD)
        self.assertTrue(decided.event.transition_context["separation_exception_recorded"])
        replay = self.store.replay_request(root.request.request_id)
        self.assertEqual(replay.request.prior_decision_ref, "review:prior:opaque")
        self.assertEqual(replay.current_state, ChallengeState.UPHELD)

    def test_exact_initiation_replay_is_idempotent(self):
        first = self._init("idempotent")
        second = self._init("idempotent")
        self.assertEqual(first.request.request_id, second.request.request_id)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(len(self.store.replay_request(first.request.request_id).events), 1)

    def test_all_three_request_kinds_have_distinct_typed_roots(self):
        rows = []
        for kind in ChallengeKind:
            root = self.store.initiate_request(
                kind=kind,
                target_finding_id=self.finding_id,
                source_request_ref=f"challenge:test:typed:{kind.value.lower()}",
                actor_ref="dp303-intake-adapter",
                actor_role=ChallengeRole.INTAKE_ADAPTER,
                reason=f"Private {kind.value.lower()} request",
                prior_decision_ref=(
                    "review:prior:typed" if kind is ChallengeKind.APPEAL else None
                ),
            )
            rows.append((root.request.kind, root.event.to_state))
        self.assertEqual(
            rows,
            [
                (ChallengeKind.CORRECTION, ChallengeState.PRIVATE_RECEIVED),
                (ChallengeKind.TAKEDOWN, ChallengeState.PRIVATE_RECEIVED),
                (ChallengeKind.APPEAL, ChallengeState.PRIVATE_RECEIVED),
            ],
        )

    def test_actor_and_reason_bounds_fail_before_persistence(self):
        with self.assertRaisesRegex(ChallengePersistenceError, "CHALLENGE_ACTOR_REF_INVALID"):
            self.store.initiate_request(
                kind=ChallengeKind.TAKEDOWN,
                target_finding_id=self.finding_id,
                source_request_ref="challenge:test:actor-bound",
                actor_ref="x" * 257,
                actor_role=ChallengeRole.INTAKE_ADAPTER,
                reason="bounded reason",
            )
        with self.assertRaisesRegex(ChallengePersistenceError, "CHALLENGE_REASON_INVALID"):
            self.store.initiate_request(
                kind=ChallengeKind.TAKEDOWN,
                target_finding_id=self.finding_id,
                source_request_ref="challenge:test:reason-bound",
                actor_ref="actor:bounded",
                actor_role=ChallengeRole.INTAKE_ADAPTER,
                reason="x" * 8001,
            )

    def test_real_intake_adapter_persists_takedown_and_appeal_private_states(self):
        runtime = QueueRuntimeStore(self.fresh_url)
        profile = lambda kind: ChallengeLaunchProfile(  # noqa: E731 - compact fixture
            configured=True,
            enabled=True,
            enabled_kinds=frozenset({kind}),
            rate_profile=RateLimitProfile(
                scope=RateScope.GLOBAL,
                limit=5,
                window_seconds=3600,
                configured=True,
            ),
        )
        takedown = submit_challenge(
            runtime,
            {
                "kind": "TAKEDOWN",
                "target_finding_id": self.finding_id,
                "reason": "Private takedown request for triage.",
            },
            launch_profile=profile(ChallengeKind.TAKEDOWN),
            rate_state=RateLimitState(),
        )
        appeal = submit_challenge(
            runtime,
            {
                "kind": "APPEAL",
                "target_finding_id": self.finding_id,
                "prior_decision_id": "review:prior:intake",
                "reason": "Private appeal request for independent review.",
            },
            launch_profile=profile(ChallengeKind.APPEAL),
            rate_state=RateLimitState(),
        )
        self.assertEqual(takedown.state, ChallengeServiceState.TRIAGE_PENDING_PRIVATE)
        self.assertEqual(appeal.state, ChallengeServiceState.INDEPENDENT_REVIEW_PENDING_PRIVATE)
        self.assertEqual(takedown.reason, ChallengeServiceReason.OK.value)
        self.assertEqual(appeal.reason, ChallengeServiceReason.OK.value)
        self.assertIsNotNone(takedown.receipt_id)
        self.assertIsNotNone(appeal.receipt_id)
        self.assertTrue(takedown.is_bounded())
        self.assertTrue(appeal.is_bounded())

    def test_fresh_schema_and_replay_safe_migration_have_same_private_contract(self):
        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        migration = (
            ROOT / "db" / "migrations" / "20261006-add-private-challenge-ledger.sql"
        ).read_text()
        markers = (
            "CREATE TABLE IF NOT EXISTS private_challenge_request",
            "CREATE TABLE IF NOT EXISTS private_challenge_event",
            "target_record_version",
            "event_integrity_sha256",
            "private_challenge_event_one_successor_idx",
            "private_challenge_request_append_only",
            "private_challenge_event_append_only",
            "private_challenge_event_no_truncate",
        )
        for sql in (schema, migration):
            for marker in markers:
                self.assertIn(marker, sql)

        query = """
            SELECT string_agg(
                table_name || '.' || column_name,
                ',' ORDER BY table_name, ordinal_position
            )
            FROM information_schema.columns
            WHERE table_name IN ('private_challenge_request','private_challenge_event');
        """
        self.assertEqual(
            self._psql(self.fresh_url, query),
            self._psql(self.migration_url, query),
        )


if __name__ == "__main__":
    unittest.main()

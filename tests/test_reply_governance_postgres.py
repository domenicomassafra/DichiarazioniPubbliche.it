from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.challenge_persistence import (  # noqa: E402
    ChallengePersistenceError,
    PrivateChallengeLedgerStore,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import (  # noqa: E402
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
)
from dichiarazioni_pubbliche.public_intake_abuse import (  # noqa: E402
    InMemoryIntakeRateStore,
    IntakeAbuseProfile,
    guard_validated_intake,
)
from dichiarazioni_pubbliche.policy.intake_policy import validate_intake_payload  # noqa: E402
from dichiarazioni_pubbliche.reply_governance import (  # noqa: E402
    ReplyGovernanceError,
    ReplyGovernanceStore,
    RetentionAction,
)
from dichiarazioni_pubbliche.projection_cleanup import (  # noqa: E402
    ProjectionArtifact,
    cleanup_takedown_current_artifacts,
)
from dichiarazioni_pubbliche.rights_complaint_bridge import (  # noqa: E402
    RightsComplaintBridge,
    RightsComplaintBridgeError,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRegistryStore,
    RightsSubject,
)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ReplyGovernancePostgresTests(unittest.TestCase):
    server_started = False

    @classmethod
    def _run(cls, args, *, input_text=None):
        proc = subprocess.run(args, input=input_text, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip())
        return proc.stdout

    @classmethod
    def _psql(cls, url: str, sql: str) -> str:
        return cls._run(
            [shutil.which("psql") or "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "--dbname", url],
            input_text=sql,
        ).strip()

    @classmethod
    def _apply(cls, url: str, path: Path) -> None:
        cls._run(
            [shutil.which("psql") or "psql", "-X", "-v", "ON_ERROR_STOP=1", "--dbname", url, "-f", str(path)]
        )

    @classmethod
    def setUpClass(cls) -> None:
        tools = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, value in tools.items() if value is None]
        if missing:
            raise unittest.SkipTest("ephemeral PostgreSQL requires: " + ", ".join(missing))
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp302-305-governance-")
        root = Path(cls.tmp.name)
        cls.data = root / "data"
        cls.port = _free_tcp_port()
        cls._run([tools["initdb"], "-D", str(cls.data), "--username=postgres", "--auth=trust", "--encoding=UTF8", "--no-locale"])
        cls._run([tools["pg_ctl"], "-D", str(cls.data), "-l", str(root / "postgres.log"), "-o", f"-F -p {cls.port} -h 127.0.0.1 -k {root}", "-w", "start"])
        cls.server_started = True
        admin = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
        cls._psql(admin, "CREATE DATABASE dp_governance_fresh; CREATE DATABASE dp_governance_migration;")
        cls.url = f"postgresql://postgres@127.0.0.1:{cls.port}/dp_governance_fresh"
        cls.migration_url = f"postgresql://postgres@127.0.0.1:{cls.port}/dp_governance_migration"
        cls._apply(cls.url, ROOT / "db" / "schema.v1.sql")
        migration = ROOT / "db" / "migrations" / "20261006-add-reply-governance-ledgers.sql"
        cls._apply(cls.url, migration)
        cls._apply(cls.url, migration)
        cls._psql(cls.migration_url, "CREATE TABLE finding (id text PRIMARY KEY); INSERT INTO finding VALUES ('finding:migration');")
        cls._apply(cls.migration_url, migration)
        cls._apply(cls.migration_url, migration)
        cls.governance = ReplyGovernanceStore(cls.url)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.server_started:
            cls._run([shutil.which("pg_ctl") or "pg_ctl", "-D", str(cls.data), "-m", "fast", "-w", "stop"])
        cls.tmp.cleanup()

    def setUp(self) -> None:
        suffix = self._testMethodName.replace("_", "-")
        self.content_id = f"content:gov:{suffix}"
        self.claim_id = f"claim:gov:{suffix}"
        self.finding_id = f"finding:gov:{suffix}"
        self.reply_id = f"reply:gov:{suffix}"
        self._psql(
            self.url,
            f"""
            INSERT INTO content_item(id,canonical_url) VALUES ('{self.content_id}','https://example.test/{suffix}');
            INSERT INTO atomic_claim(id,content_id,normalized_claim,claim_type,temporal_scope,check_worthy,metadata)
            VALUES ('{self.claim_id}','{self.content_id}','fixture {suffix}','CURRENT_POLICY','{{}}'::jsonb,true,'{{}}'::jsonb);
            INSERT INTO finding(id,claim_id,assessment,rationale,publication_status,policy_version,model_bundle)
            VALUES ('{self.finding_id}','{self.claim_id}','SUPPORTED','fixture','PUBLISH','policy:test','{{}}'::jsonb);
            INSERT INTO right_of_reply(id,finding_id,body,status,public_visibility)
            VALUES ('{self.reply_id}','{self.finding_id}','PRIVATE_BODY_SENTINEL','RECEIVED','PRIVATE');
            """,
        )

    def _guard_receipt(self):
        payload = {
            "finding_id": self.finding_id,
            "body": "Bounded reply body",
            "submitter_name": None,
            "submitter_role": None,
            "evidence_urls": [],
            "request_fingerprint": "test-client-fingerprint",
        }
        validation = validate_intake_payload(payload, launch_profile_configured=True, intake_enabled=True)
        return validation, guard_validated_intake(
            validation,
            pseudonymous_bucket_key="bucket:" + "a" * 64,
            profile=IntakeAbuseProfile(
                configured=True, window_seconds=60, bucket_limit=5, global_quota=10,
                duplicate_window_seconds=60, duplicate_limit=2, duplicate_capacity=10,
            ),
            rate_store=InMemoryIntakeRateStore(),
            clock=lambda: datetime(2026, 10, 6, 19, 0, tzinfo=timezone.utc),
            launch_profile_enabled=True,
        )

    def test_abuse_decision_is_durable_attributable_bounded_and_append_only(self):
        validation, receipt = self._guard_receipt()
        first = self.governance.record_abuse_decision(
            receipt=receipt, request_fingerprint_sha256=validation.source_hash, actor_ref="intake-guard:local"
        )
        second = self.governance.record_abuse_decision(
            receipt=receipt, request_fingerprint_sha256=validation.source_hash, actor_ref="intake-guard:local"
        )
        self.assertEqual(first, second)
        raw = self._psql(
            self.url,
            "SELECT row_to_json(e)::text FROM private_intake_abuse_event e WHERE event_id='" + first.event_id + "';",
        )
        self.assertNotIn("Bounded reply body", raw)
        self.assertNotIn(validation.source_hash, raw)
        self.assertIn("intake-guard:local", raw)
        self.assertIn(receipt.reason.value, raw)
        with self.assertRaises(RuntimeError):
            self._psql(self.url, "UPDATE private_intake_abuse_event SET actor_ref='tamper';")

    def test_composed_abuse_guard_records_the_decision_before_returning(self):
        payload = {
            "finding_id": self.finding_id,
            "body": "Bounded reply body",
            "submitter_name": None,
            "submitter_role": None,
            "evidence_urls": [],
            "request_fingerprint": "composed-client-fingerprint",
        }
        validation = validate_intake_payload(
            payload,
            launch_profile_configured=True,
            intake_enabled=True,
        )
        receipt, audit = self.governance.guard_and_record_abuse_decision(
            validation=validation,
            pseudonymous_bucket_key="bucket:" + "c" * 64,
            profile=IntakeAbuseProfile(
                configured=True,
                window_seconds=60,
                bucket_limit=5,
                global_quota=10,
                duplicate_window_seconds=60,
                duplicate_limit=2,
                duplicate_capacity=10,
            ),
            rate_store=InMemoryIntakeRateStore(),
            clock=lambda: datetime(2026, 10, 6, 19, 0, tzinfo=timezone.utc),
            actor_ref="intake-guard:composed",
            launch_profile_enabled=True,
        )
        self.assertEqual(audit.decision_state, receipt.state.value)
        self.assertEqual(
            self._psql(
                self.url,
                "SELECT count(*) FROM private_intake_abuse_event "
                f"WHERE event_id='{audit.event_id}';",
            ),
            "1",
        )

    def test_legal_hold_blocks_purge_until_explicit_parameterized_release(self):
        hold = self.governance.record_retention_decision(
            reply_id=self.reply_id, action=RetentionAction.LEGAL_HOLD_SET,
            actor_ref="operator:privacy", reason_code="LEGAL_HOLD", policy_decision_ref="policy:hold:opaque",
        )
        self.assertEqual(hold.action, RetentionAction.LEGAL_HOLD_SET)
        self.assertEqual(
            self.governance.record_retention_decision(
                reply_id=self.reply_id, action=RetentionAction.LEGAL_HOLD_SET,
                actor_ref="operator:privacy", reason_code="LEGAL_HOLD", policy_decision_ref="policy:hold:opaque",
            ),
            hold,
        )
        self.assertEqual(len(self.governance.replay_retention(self.reply_id).events), 1)
        with self.assertRaisesRegex(ReplyGovernanceError, "REPLY_RETENTION_LEGAL_HOLD_ACTIVE"):
            self.governance.record_retention_decision(
                reply_id=self.reply_id, action=RetentionAction.PURGE_APPROVED,
                actor_ref="operator:privacy", reason_code="RETENTION_PURGE", policy_decision_ref="policy:purge:opaque",
            )
        self.governance.record_retention_decision(
            reply_id=self.reply_id, action=RetentionAction.LEGAL_HOLD_RELEASE,
            actor_ref="operator:privacy", reason_code="LEGAL_HOLD_RELEASE", policy_decision_ref="policy:release:opaque",
        )
        self.governance.record_retention_decision(
            reply_id=self.reply_id, action=RetentionAction.PURGE_APPROVED,
            actor_ref="operator:privacy", reason_code="RETENTION_PURGE", policy_decision_ref="policy:purge:opaque",
        )
        executed = self.governance.purge_unpublished_reply(reply_id=self.reply_id, actor_ref="operator:privacy")
        self.assertEqual(executed.action, RetentionAction.PURGE_EXECUTED)
        self.assertEqual(self._psql(self.url, f"SELECT count(*) FROM right_of_reply WHERE id='{self.reply_id}';"), "0")
        replay = self.governance.replay_retention(self.reply_id)
        self.assertTrue(replay.purged)
        self.assertFalse(replay.legal_hold_active)
        self.assertEqual(self.governance.purge_unpublished_reply(reply_id=self.reply_id, actor_ref="operator:privacy"), executed)

    def test_published_reply_is_never_retention_purge_candidate(self):
        self._psql(self.url, f"UPDATE right_of_reply SET status='PUBLISHED', public_visibility='PUBLIC' WHERE id='{self.reply_id}';")
        with self.assertRaisesRegex(ReplyGovernanceError, "REPLY_RETENTION_PUBLISHED_REPLY_FORBIDDEN"):
            self.governance.record_retention_decision(
                reply_id=self.reply_id, action=RetentionAction.PURGE_APPROVED,
                actor_ref="operator:privacy", reason_code="RETENTION_PURGE", policy_decision_ref="policy:purge:opaque",
            )

    def test_challenge_exact_concurrent_initiation_has_one_root_and_no_fork(self):
        def invoke(_):
            store = PrivateChallengeLedgerStore(self.url)
            return store.initiate_request(
                kind=ChallengeKind.TAKEDOWN, target_finding_id=self.finding_id,
                source_request_ref="concurrency:exact", actor_ref="intake:concurrent",
                actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Concurrent private request",
            )
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(invoke, range(8)))
        self.assertEqual(sum(result.created for result in results), 1)
        request_id = results[0].request.request_id
        replay = PrivateChallengeLedgerStore(self.url).replay_request(request_id)
        self.assertFalse(replay.blockers)
        self.assertEqual(len(replay.events), 1)

    def test_concurrent_challenge_transition_has_single_successor(self):
        store = PrivateChallengeLedgerStore(self.url)
        root = store.initiate_request(
            kind=ChallengeKind.TAKEDOWN, target_finding_id=self.finding_id,
            source_request_ref="concurrency:transition", actor_ref="intake:root",
            actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Concurrent transition root",
        )
        outcomes = []
        def invoke(index):
            try:
                result = PrivateChallengeLedgerStore(self.url).transition_request(
                    root.request.request_id, actor_ref=f"intake:worker:{index}",
                    actor_role=ChallengeRole.INTAKE_ADAPTER, reason=f"Route to triage {index}",
                )
                return ("OK", result.event.event_id)
            except ChallengePersistenceError as exc:
                return ("BLOCKED", str(exc))
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(invoke, range(2)))
        replay = store.replay_request(root.request.request_id)
        self.assertFalse(replay.blockers)
        self.assertEqual(len(replay.events), 2)
        self.assertEqual(replay.current_state, ChallengeState.TRIAGE_PENDING)
        self.assertEqual(sum(kind == "OK" for kind, _ in outcomes), 1)
        self.assertTrue(all(kind == "OK" or detail in {"CHALLENGE_CONCURRENT_TRANSITION", "ROLE_NOT_AUTHORIZED"} for kind, detail in outcomes))

    def test_exact_challenge_transition_retry_returns_same_event_without_advancing(self):
        store = PrivateChallengeLedgerStore(self.url)
        root = store.initiate_request(
            kind=ChallengeKind.TAKEDOWN, target_finding_id=self.finding_id,
            source_request_ref="replay:transition", actor_ref="intake:retry",
            actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Retry transition",
        )
        first = store.transition_request(
            root.request.request_id, actor_ref="intake:retry",
            actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Route retry to triage",
        )
        second = store.transition_request(
            root.request.request_id, actor_ref="intake:retry",
            actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Route retry to triage",
        )
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.event, first.event)
        replay = store.replay_request(root.request.request_id)
        self.assertEqual(len(replay.events), 2)
        self.assertEqual(replay.current_state, ChallengeState.TRIAGE_PENDING)

    def test_rights_complaint_routes_to_reviewed_dp303_hold_and_replays(self):
        rights = PrivateRightsRegistryStore(self.url)
        record = rights.record_rights(
            subject=RightsSubject(
                source_family="fixture", locator_kind="URL",
                locator_value=f"https://example.test/{self._testMethodName}", content_id=self.content_id,
            ),
            policy_version="rights-policy:test",
        )
        bridge = RightsComplaintBridge(self.url)
        first = bridge.submit(
            finding_id=self.finding_id, rights_record_id=record.id,
            complaint_ref="complaint:opaque:1", actor_ref="rights-intake:1",
        )
        self.assertEqual(first.event.to_state, ChallengeState.TRIAGE_PENDING)
        replay = bridge.submit(
            finding_id=self.finding_id, rights_record_id=record.id,
            complaint_ref="complaint:opaque:1", actor_ref="rights-intake:1",
        )
        self.assertEqual(replay.request.request_id, first.request.request_id)
        self.assertFalse(replay.created)
        self.assertEqual(replay.event.to_state, ChallengeState.TRIAGE_PENDING)
        held = bridge.approve_hold(first.request.request_id, reviewer_actor_ref="reviewer:rights:2")
        self.assertEqual(held.event.to_state, ChallengeState.PUBLIC_HOLD_APPROVED)
        self.assertEqual(bridge.current_hold(self.finding_id).disposition.value, "HOLD")
        held_replay = bridge.approve_hold(
            first.request.request_id,
            reviewer_actor_ref="reviewer:rights:2",
        )
        self.assertFalse(held_replay.created)
        self.assertEqual(held_replay.event, held.event)
        complaint_replay = bridge.submit(
            finding_id=self.finding_id, rights_record_id=record.id,
            complaint_ref="complaint:opaque:1", actor_ref="rights-intake:1",
        )
        self.assertFalse(complaint_replay.created)
        self.assertEqual(complaint_replay.event, held.event)

    def test_rights_complaint_cannot_hold_unrelated_finding(self):
        rights = PrivateRightsRegistryStore(self.url)
        record = rights.record_rights(
            subject=RightsSubject(
                source_family="fixture", locator_kind="URL",
                locator_value=f"https://example.test/{self._testMethodName}", content_id=self.content_id,
            ),
            policy_version="rights-policy:test",
        )
        other_content = self.content_id + ":other"
        other_claim = self.claim_id + ":other"
        other_finding = self.finding_id + ":other"
        self._psql(
            self.url,
            f"""
            INSERT INTO content_item(id,canonical_url) VALUES ('{other_content}','https://example.test/other/{self._testMethodName}');
            INSERT INTO atomic_claim(id,content_id,normalized_claim,claim_type,temporal_scope,check_worthy,metadata)
            VALUES ('{other_claim}','{other_content}','other fixture','CURRENT_POLICY','{{}}'::jsonb,true,'{{}}'::jsonb);
            INSERT INTO finding(id,claim_id,assessment,rationale,publication_status,policy_version,model_bundle)
            VALUES ('{other_finding}','{other_claim}','SUPPORTED','fixture','PUBLISH','policy:test','{{}}'::jsonb);
            """,
        )
        bridge = RightsComplaintBridge(self.url)
        with self.assertRaisesRegex(
            RightsComplaintBridgeError,
            "RIGHTS_COMPLAINT_RECORD_NOT_BOUND_TO_FINDING",
        ):
            bridge.submit(
                finding_id=other_finding,
                rights_record_id=record.id,
                complaint_ref="complaint:opaque:unrelated",
                actor_ref="rights-intake:unrelated",
            )

    def test_reviewed_takedown_cleanup_removes_public_file_but_preserves_private_history(self):
        store = PrivateChallengeLedgerStore(self.url)
        root = store.initiate_request(
            kind=ChallengeKind.TAKEDOWN, target_finding_id=self.finding_id,
            source_request_ref="cleanup:reviewed", actor_ref="intake:cleanup",
            actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Private cleanup request",
        )
        pending = store.transition_request(
            root.request.request_id, actor_ref="intake:cleanup",
            actor_role=ChallengeRole.INTAKE_ADAPTER, reason="Route cleanup to triage",
        )
        self.assertEqual(pending.event.to_state, ChallengeState.TRIAGE_PENDING)
        held = store.transition_request(
            root.request.request_id, actor_ref="reviewer:cleanup",
            actor_role=ChallengeRole.TRIAGE_REVIEWER, reason="Reviewed takedown hold",
            challenge_review_approved=True,
        )
        self.assertEqual(held.event.to_state, ChallengeState.PUBLIC_HOLD_APPROVED)
        hold = store.current_hold_for_finding(self.finding_id)
        with tempfile.TemporaryDirectory(prefix="dp303-public-cleanup-") as tmp:
            root_path = Path(tmp)
            public_file = root_path / "claims" / "current.html"
            private_file = root_path / "private" / "audit.txt"
            public_file.parent.mkdir(parents=True)
            private_file.parent.mkdir(parents=True)
            public_file.write_text("PUBLIC_CURRENT")
            private_file.write_text("PRIVATE_AUDIT")
            receipt = cleanup_takedown_current_artifacts(
                root_path,
                finding_id=self.finding_id,
                hold=hold,
                artifacts=(
                    ProjectionArtifact(
                        "route:current:finding", "claims/current.html", "finding",
                        self.finding_id, "CURRENT", True,
                    ),
                    ProjectionArtifact(
                        "private:audit", "private/audit.txt", "finding",
                        self.finding_id, "CURRENT", False,
                    ),
                ),
            )
            self.assertTrue(receipt.complete)
            self.assertFalse(public_file.exists())
            self.assertTrue(private_file.exists())
        self.assertEqual(
            self._psql(self.url, f"SELECT count(*) FROM finding WHERE id='{self.finding_id}';"),
            "1",
        )
        replay = store.replay_request(root.request.request_id)
        self.assertFalse(replay.blockers)
        self.assertEqual(len(replay.events), 3)

    def test_fresh_schema_and_replay_safe_migration_share_governance_contract(self):
        query = """
            SELECT string_agg(table_name || '.' || column_name, ',' ORDER BY table_name, ordinal_position)
            FROM information_schema.columns
            WHERE table_name IN ('private_intake_abuse_event','private_reply_retention_event');
        """
        self.assertEqual(self._psql(self.url, query), self._psql(self.migration_url, query))
        for table in ("private_intake_abuse_event", "private_reply_retention_event"):
            with self.assertRaises(RuntimeError):
                self._psql(self.url, f"TRUNCATE {table};")


if __name__ == "__main__":
    unittest.main()

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.privacy_policy import (  # noqa: E402
    DataClass,
    PRIVACY_POLICY_VERSION,
    PrivateAccessPurpose,
    PrivateAccessRequest,
    PrivateAccessRole,
    RightsRequestKind,
    build_private_access_audit,
    decide_private_access,
)
from dichiarazioni_pubbliche.privacy_runtime import (  # noqa: E402
    RIGHTS_CASE_CONTRACT_VERSION,
    PrivacyRightsAccessStore,
    RightsCaseEventType,
    _json_sha256,
)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class PrivacyRightsAccessPersistenceTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    port: int
    database_url: str
    store: PrivacyRightsAccessStore
    server_started = False

    @classmethod
    def _run_command(cls, args: list[str]) -> str:
        proc = subprocess.run(args, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\n{detail}")
        return proc.stdout

    @classmethod
    def setUpClass(cls) -> None:
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp304-privacy-runtime-")
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
                    "CREATE DATABASE dp304_privacy_runtime;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp304_privacy_runtime"
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
            # The additive migration must also be replay-safe against the fresh schema.
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
                        str(
                            ROOT
                            / "db"
                            / "migrations"
                            / "20261007-add-privacy-rights-access-ledgers.sql"
                        ),
                    ]
                )
            cls.store = PrivacyRightsAccessStore(cls.database_url)
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
        suffix = self._testMethodName.replace("test_", "")
        self.content_id = f"content:dp304:{suffix}"
        self.claim_id = f"claim:dp304:{suffix}"
        self.finding_id = f"finding:dp304:{suffix}"
        self.evidence_id = f"evidence:dp304:{suffix}"
        self.private_sentinel = f"PRIVATE_DP304_BODY_SENTINEL_{suffix}"
        self.store.run(
            """
            INSERT INTO content_item (id, canonical_url, title, processing_status)
            VALUES (:'content_id', :'url', 'DP-304 synthetic', 'PROCESSED');
            INSERT INTO atomic_claim (
                id, content_id, normalized_claim, claim_type, check_worthy,
                extraction_version, metadata
            ) VALUES (
                :'claim_id', :'content_id', 'Synthetic public history.',
                'CURRENT_POLICY', true, 'dp304-test-v1', '{}'::jsonb
            );
            INSERT INTO finding (
                id, claim_id, assessment, rationale, publication_status, policy_version
            ) VALUES (
                :'finding_id', :'claim_id', 'SUPPORTED', 'Synthetic rationale.',
                'PUBLISH', 'dp304-test-v1'
            );
            INSERT INTO evidence (
                id, canonical_url, source_type, excerpt, rights_status
            ) VALUES (
                :'evidence_id', :'evidence_url', 'SYNTHETIC_FIXTURE',
                :'private_sentinel', 'UNKNOWN'
            );
            """,
            content_id=self.content_id,
            url=f"https://example.test/{suffix}",
            claim_id=self.claim_id,
            finding_id=self.finding_id,
            evidence_id=self.evidence_id,
            evidence_url=f"https://example.test/evidence/{suffix}",
            private_sentinel=self.private_sentinel,
        )

    def test_rights_case_is_private_append_only_and_never_mutates_public_history(self):
        before = self.store.run(
            "SELECT row_to_json(finding)::text FROM finding WHERE id=:'finding_id';",
            finding_id=self.finding_id,
        )
        requester = "private-subject@example.test"
        opened = self.store.open_rights_case(
            subject_ref="person:dp304:subject",
            target_record_ref=self.finding_id,
            request_kind=RightsRequestKind.DELETION,
            affects_published_version=True,
            requester_ref=requester,
            opened_at="2026-10-07T16:00:00+02:00",
        )
        self.assertEqual(opened.latest_event_type, RightsCaseEventType.OPEN_PRIVATE.value)
        reviewed = self.store.append_rights_review_hold(
            case_id=opened.case_id,
            actor_ref="reviewer:dp304",
            occurred_at="2026-10-07T16:05:00+02:00",
        )
        self.assertEqual(
            reviewed.latest_event_type,
            RightsCaseEventType.PUBLIC_HISTORY_HOLD_REQUIRED.value,
        )
        self.assertEqual(reviewed.latest_event_sequence, 2)

        after = self.store.run(
            "SELECT row_to_json(finding)::text FROM finding WHERE id=:'finding_id';",
            finding_id=self.finding_id,
        )
        self.assertEqual(after, before)
        persisted = self.store.run(
            "SELECT row_to_json(row)::text FROM (SELECT * FROM privacy_rights_case "
            "WHERE case_id=:'case_id') row;",
            case_id=opened.case_id,
        )
        self.assertNotIn(requester, persisted)
        self.assertEqual(json.loads(persisted)["record_visibility"], "PRIVATE")
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM privacy_rights_case_event WHERE case_id=:'case_id';",
                case_id=opened.case_id,
            ),
            "2",
        )
        with self.assertRaises(RuntimeError):
            self.store.run(
                "UPDATE privacy_rights_case_event SET actor_ref='changed' "
                "WHERE case_id=:'case_id';",
                case_id=opened.case_id,
            )
        with self.assertRaises(RuntimeError):
            self.store.run(
                "DELETE FROM privacy_rights_case WHERE case_id=:'case_id';",
                case_id=opened.case_id,
            )
        with self.assertRaises(RuntimeError):
            self.store.run("TRUNCATE privacy_rights_case_event;")

    def test_rights_case_conflict_retry_and_concurrent_replay_fail_closed(self):
        opened_at = "2026-10-07T16:20:00+02:00"
        conflicting_material = {
            "contract_version": RIGHTS_CASE_CONTRACT_VERSION,
            "subject_ref": "person:dp304:expected",
            "target_record_ref": self.finding_id,
            "request_kind": RightsRequestKind.ACCESS.value,
            "affects_published_version": False,
            "requester_ref_sha256": None,
            "privacy_policy_version": PRIVACY_POLICY_VERSION,
            "opened_at_text": opened_at,
        }
        digest = _json_sha256(conflicting_material)
        case_id = f"privacy-rights-case:{digest}"
        self.store.run(
            """
            INSERT INTO privacy_rights_case (
                case_id, contract_version, subject_ref, target_record_ref,
                request_kind, affects_published_version, requester_ref_sha256,
                privacy_policy_version, opened_at_text, case_integrity_sha256
            ) VALUES (
                :'case_id', 'privacy-rights-case-v1', 'person:dp304:wrong',
                :'target_record_ref', 'ACCESS', false, NULL, :'privacy_policy_version',
                :'opened_at_text', :'case_integrity_sha256'
            );
            """,
            case_id=case_id,
            target_record_ref=self.finding_id,
            privacy_policy_version=PRIVACY_POLICY_VERSION,
            opened_at_text=opened_at,
            case_integrity_sha256=digest,
        )
        with self.assertRaisesRegex(RuntimeError, "PRIVACY_RIGHTS_CASE_CONFLICT"):
            self.store.open_rights_case(
                subject_ref="person:dp304:expected",
                target_record_ref=self.finding_id,
                request_kind=RightsRequestKind.ACCESS,
                affects_published_version=False,
                opened_at=opened_at,
            )
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM privacy_rights_case_event WHERE case_id=:'case_id';",
                case_id=case_id,
            ),
            "0",
        )

        replay = self.store.open_rights_case(
            subject_ref="person:dp304:replay",
            target_record_ref=self.finding_id,
            request_kind=RightsRequestKind.RESTRICTION,
            affects_published_version=False,
            opened_at="2026-10-07T16:21:00+02:00",
        )
        replay_again = self.store.open_rights_case(
            subject_ref="person:dp304:replay",
            target_record_ref=self.finding_id,
            request_kind=RightsRequestKind.RESTRICTION,
            affects_published_version=False,
            opened_at="2026-10-07T16:21:00+02:00",
        )
        self.assertEqual(replay_again, replay)
        first_hold = self.store.append_rights_review_hold(
            case_id=replay.case_id,
            actor_ref="reviewer:dp304:replay",
            occurred_at="2026-10-07T16:22:00+02:00",
        )
        retried_hold = self.store.append_rights_review_hold(
            case_id=replay.case_id,
            actor_ref="reviewer:dp304:replay",
            occurred_at="2026-10-07T16:22:00+02:00",
        )
        self.assertEqual(retried_hold, first_hold)
        self.assertEqual(retried_hold.latest_event_sequence, 2)

        concurrent = self.store.open_rights_case(
            subject_ref="person:dp304:concurrent",
            target_record_ref=self.finding_id,
            request_kind=RightsRequestKind.OBJECTION,
            affects_published_version=False,
            opened_at="2026-10-07T16:23:00+02:00",
        )
        barrier = threading.Barrier(2)

        class RacingStore(PrivacyRightsAccessStore):
            def _rights_event_matches_replay(self, **kwargs):
                matched = super()._rights_event_matches_replay(**kwargs)
                if not matched:
                    barrier.wait(timeout=5)
                return matched

        stores = (RacingStore(self.database_url), RacingStore(self.database_url))
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    store.append_rights_review_hold,
                    case_id=concurrent.case_id,
                    actor_ref="reviewer:dp304:concurrent",
                    occurred_at="2026-10-07T16:24:00+02:00",
                )
                for store in stores
            ]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0].latest_event_sequence, 2)
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM privacy_rights_case_event WHERE case_id=:'case_id';",
                case_id=concurrent.case_id,
            ),
            "2",
        )

    def test_private_inspection_requires_authority_and_audit_never_copies_body(self):
        allowed_request = PrivateAccessRequest(
            actor_ref="reviewer:dp304",
            role=PrivateAccessRole.DECISION_REVIEWER,
            purpose=PrivateAccessPurpose.RIGHTS_REQUEST,
            data_class=DataClass.OPERATIONAL_PRIVATE,
            requested_fields=("excerpt",),
        )
        allowed = self.store.inspect_private_field(
            table_name="evidence",
            field_name="excerpt",
            record_ref=self.evidence_id,
            request=allowed_request,
            occurred_at="2026-10-07T16:10:00+02:00",
        )
        self.assertTrue(allowed.allowed)
        self.assertTrue(allowed.found)
        self.assertEqual(allowed.value, self.private_sentinel)

        audit = self.store.run(
            "SELECT row_to_json(row)::text FROM (SELECT * FROM private_access_audit_event "
            "WHERE event_id=:'event_id') row;",
            event_id=allowed.audit_event_id,
        )
        self.assertNotIn(self.private_sentinel, audit)
        self.assertNotIn('"excerpt"', audit)
        audit_row = json.loads(audit)
        self.assertEqual(audit_row["outcome"], "ALLOW_READ_ONLY")
        self.assertEqual(audit_row["requested_field_count"], 1)
        self.assertEqual(audit_row["record_visibility"], "PRIVATE")

        denied_request = PrivateAccessRequest(
            actor_ref="public-user",
            role="PUBLIC_USER",
            purpose=PrivateAccessPurpose.RIGHTS_REQUEST,
            data_class=DataClass.OPERATIONAL_PRIVATE,
            requested_fields=("excerpt",),
        )
        denied = self.store.inspect_private_field(
            table_name="evidence",
            field_name="excerpt",
            record_ref=self.evidence_id,
            request=denied_request,
            occurred_at="2026-10-07T16:11:00+02:00",
        )
        self.assertFalse(denied.allowed)
        self.assertIsNone(denied.value)
        denied_audit = self.store.run(
            "SELECT row_to_json(row)::text FROM (SELECT * FROM private_access_audit_event "
            "WHERE event_id=:'event_id') row;",
            event_id=denied.audit_event_id,
        )
        self.assertNotIn(self.private_sentinel, denied_audit)
        self.assertEqual(json.loads(denied_audit)["outcome"], "DENY")

        with self.assertRaises(RuntimeError):
            self.store.run(
                "UPDATE private_access_audit_event SET outcome='DENY' "
                "WHERE event_id=:'event_id';",
                event_id=allowed.audit_event_id,
            )
        with self.assertRaises(RuntimeError):
            self.store.run("TRUNCATE private_access_audit_event;")

    def test_private_inspection_rejects_audit_conflict_and_invalid_timestamp(self):
        request = PrivateAccessRequest(
            actor_ref="reviewer:dp304:audit-conflict",
            role=PrivateAccessRole.DECISION_REVIEWER,
            purpose=PrivateAccessPurpose.RIGHTS_REQUEST,
            data_class=DataClass.OPERATIONAL_PRIVATE,
            requested_fields=("excerpt",),
        )
        occurred_at = "2026-10-07T16:25:00+02:00"
        decision = decide_private_access(request)
        receipt = build_private_access_audit(
            request,
            decision,
            record_ref=self.evidence_id,
            occurred_at=occurred_at,
        )
        digest = _json_sha256(receipt.__dict__)
        event_id = f"private-access-audit:{digest}"
        self.store.run(
            """
            INSERT INTO private_access_audit_event (
                event_id, contract_version, privacy_policy_version, actor_ref,
                record_ref, purpose_ref, outcome, occurred_at_text,
                requested_field_count, legal_hold_active, event_integrity_sha256
            ) VALUES (
                :'event_id', 'private-access-audit-v1', :'privacy_policy_version',
                'attacker:preseed', :'record_ref', 'RIGHTS_REQUEST', 'DENY',
                :'occurred_at_text', 1, false, :'event_integrity_sha256'
            );
            """,
            event_id=event_id,
            privacy_policy_version=PRIVACY_POLICY_VERSION,
            record_ref=self.evidence_id,
            occurred_at_text=occurred_at,
            event_integrity_sha256=digest,
        )
        with self.assertRaisesRegex(RuntimeError, "PRIVATE_ACCESS_AUDIT_CONFLICT"):
            self.store.inspect_private_field(
                table_name="evidence",
                field_name="excerpt",
                record_ref=self.evidence_id,
                request=request,
                occurred_at=occurred_at,
            )
        self.assertEqual(
            self.store.run(
                "SELECT actor_ref || '|' || outcome FROM private_access_audit_event "
                "WHERE event_id=:'event_id';",
                event_id=event_id,
            ),
            "attacker:preseed|DENY",
        )

        with self.assertRaisesRegex(ValueError, "PRIVATE_ACCESS_OCCURRED_AT_INVALID"):
            self.store.inspect_private_field(
                table_name="evidence",
                field_name="excerpt",
                record_ref=self.evidence_id,
                request=request,
                occurred_at="not-a-timestamp",
            )

    def test_private_inspection_rejects_field_or_classification_downgrade(self):
        base = dict(
            actor_ref="reviewer:dp304",
            role=PrivateAccessRole.DECISION_REVIEWER,
            purpose=PrivateAccessPurpose.RIGHTS_REQUEST,
            requested_fields=("excerpt",),
        )
        wrong_class = self.store.inspect_private_field(
            table_name="evidence",
            field_name="excerpt",
            record_ref=self.evidence_id,
            request=PrivateAccessRequest(data_class=DataClass.PUBLIC_CORE, **base),
            occurred_at="2026-10-07T16:12:00+02:00",
        )
        self.assertFalse(wrong_class.allowed)
        self.assertIn("PRIVATE_FIELD_CLASSIFICATION_MISMATCH", wrong_class.reasons)

        unknown = self.store.inspect_private_field(
            table_name="evidence",
            field_name="metadata",
            record_ref=self.evidence_id,
            request=PrivateAccessRequest(
                data_class=DataClass.OPERATIONAL_PRIVATE,
                **{**base, "requested_fields": ("metadata",)},
            ),
            occurred_at="2026-10-07T16:13:00+02:00",
        )
        self.assertFalse(unknown.allowed)
        self.assertIn("PRIVATE_FIELD_NOT_ALLOWLISTED", unknown.reasons)


if __name__ == "__main__":
    unittest.main()

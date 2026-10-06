import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.privacy_policy import (  # noqa: E402
    DataClass,
    ProjectionInput,
    PublicationDecision,
)
from dichiarazioni_pubbliche.privacy_decision_persistence import (  # noqa: E402
    PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION,
    PrivacyPublicationDecisionStore,
    projection_input_sha256,
)
import dichiarazioni_pubbliche.privacy_decision_persistence as privacy_persistence  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def public_core(
    *,
    text: str = "Public role record",
    relevance: str | None = "PUBLIC_ROLE",
) -> ProjectionInput:
    return ProjectionInput(
        field_name="normalized_claim",
        data_class=DataClass.PUBLIC_CORE,
        text_value=text,
        relevance_reason=relevance,
    )


def safe_text(*, approved: bool) -> ProjectionInput:
    return ProjectionInput(
        field_name="approved_notice_text",
        data_class=DataClass.PUBLIC_SAFE_TEXT,
        text_value="Approved bounded notice",
        relevance_reason="OFFICIAL_RECORD",
        explicitly_approved=approved,
    )


class PrivacyDecisionPersistencePostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    migration_store: PrivacyPublicationDecisionStore
    fresh_store: PrivacyPublicationDecisionStore
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
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp304-privacy-decision-")
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
            for database in ("dp304_privacy_migration", "dp304_privacy_fresh"):
                cls._run_command(
                    [
                        required["psql"] or "psql",
                        "-X",
                        "-v",
                        "ON_ERROR_STOP=1",
                        "--dbname",
                        admin_url,
                        "-c",
                        f"CREATE DATABASE {database};",
                    ]
                )
            migration_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp304_privacy_migration"
            )
            fresh_url = f"postgresql://postgres@127.0.0.1:{cls.port}/dp304_privacy_fresh"
            cls._run_command(
                [
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    migration_url,
                    "-f",
                    str(
                        ROOT
                        / "db"
                        / "migrations"
                        / "20261006-add-privacy-publication-decision-ledger.sql"
                    ),
                ]
            )
            cls._run_command(
                [
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    migration_url,
                    "-f",
                    str(
                        ROOT
                        / "db"
                        / "migrations"
                        / "20261006-add-privacy-publication-decision-ledger.sql"
                    ),
                ]
            )
            cls._run_command(
                [
                    required["psql"] or "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    fresh_url,
                    "-f",
                    str(ROOT / "db" / "schema.v1.sql"),
                ]
            )
            cls.migration_store = PrivacyPublicationDecisionStore(migration_url)
            cls.fresh_store = PrivacyPublicationDecisionStore(fresh_url)
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

    def append(
        self,
        suffix: str,
        *,
        record_version: str = "finding-version:1",
        inputs: ProjectionInput | None = None,
        supersedes_decision_id: str | None = None,
        store: PrivacyPublicationDecisionStore | None = None,
    ):
        target = store or self.migration_store
        return target.append_review(
            subject_ref=f"person:dp304:{suffix}",
            record_ref=f"finding:dp304:{suffix}",
            record_version=record_version,
            inputs=inputs or public_core(),
            reviewer_ref=f"reviewer:dp304:{suffix}",
            audit_ref=f"audit:dp304:{suffix}",
            reviewed_at="2026-10-06T10:30:00+02:00",
            supersedes_decision_id=supersedes_decision_id,
        )

    def replay(
        self,
        suffix: str,
        *,
        record_version: str = "finding-version:1",
        inputs: ProjectionInput | None = None,
        store: PrivacyPublicationDecisionStore | None = None,
    ):
        target = store or self.migration_store
        return target.replay_current(
            subject_ref=f"person:dp304:{suffix}",
            record_ref=f"finding:dp304:{suffix}",
            current_record_version=record_version,
            inputs=inputs or public_core(),
        )

    def test_missing_allowable_review_fails_closed_to_hold(self):
        replay = self.replay("missing")

        self.assertEqual(replay.decision.decision, PublicationDecision.HOLD_FOR_REVIEW)
        self.assertEqual(replay.blockers, ("PRIVACY_DECISION_MISSING",))
        self.assertIsNone(replay.decision_ref)
        self.assertFalse(replay.allowed)

    def test_unknown_data_class_is_prohibited_even_when_review_is_missing(self):
        inputs = ProjectionInput(
            field_name="normalized_claim",
            data_class="UNKNOWN",
            text_value="Public record",
            relevance_reason="PUBLIC_ROLE",
        )
        replay = self.replay("unknown-class", inputs=inputs)

        self.assertEqual(replay.decision.decision, PublicationDecision.PROHIBIT)
        self.assertIn("UNKNOWN_DATA_CLASS", replay.decision.reasons)
        self.assertIn("PRIVACY_DECISION_MISSING", replay.decision.reasons)
        self.assertFalse(replay.allowed)

    def test_public_figure_status_alone_never_authorizes(self):
        inputs = public_core(relevance="IS_PUBLIC_FIGURE")
        record = self.append("public-figure-only", inputs=inputs)
        replay = self.replay("public-figure-only", inputs=inputs)

        self.assertEqual(record.decision_action, PublicationDecision.HOLD_FOR_REVIEW.value)
        self.assertEqual(replay.decision.decision, PublicationDecision.HOLD_FOR_REVIEW)
        self.assertIn("PUBLIC_INTEREST_RELEVANCE_MISSING", replay.decision.reasons)
        self.assertFalse(replay.allowed)

    def test_safe_text_requires_explicit_approval_in_persisted_review(self):
        held = safe_text(approved=False)
        held_record = self.append("safe-held", inputs=held)
        held_replay = self.replay("safe-held", inputs=held)
        self.assertEqual(held_record.decision_action, PublicationDecision.HOLD_FOR_REVIEW.value)
        self.assertIn("SAFE_TEXT_NOT_APPROVED", held_replay.decision.reasons)

        approved = safe_text(approved=True)
        approved_record = self.append("safe-approved", inputs=approved)
        approved_replay = self.replay("safe-approved", inputs=approved)
        self.assertEqual(approved_record.decision_action, PublicationDecision.ALLOW.value)
        self.assertTrue(approved_replay.allowed)
        self.assertEqual(approved_replay.decision_ref, approved_record.decision_id)

    def test_exact_input_digest_changes_and_body_is_not_persisted(self):
        inputs = public_core(text="Bounded private review input body")
        record = self.append("digest", inputs=inputs)
        self.assertEqual(record.input_sha256, projection_input_sha256(inputs))
        self.assertEqual(
            record.text_value_sha256,
            hashlib.sha256(inputs.text_value.encode("utf-8")).hexdigest(),
        )

        stored = self.migration_store.run(
            "SELECT row_to_json(row)::text FROM (SELECT * FROM privacy_publication_decision "
            "WHERE decision_id=:'decision_id') row;",
            decision_id=record.decision_id,
        )
        self.assertNotIn(inputs.text_value, stored)
        self.assertNotIn("text_value", json.loads(stored))

        changed = public_core(text="Changed review input body")
        replay = self.replay("digest", inputs=changed)
        self.assertEqual(replay.decision.decision, PublicationDecision.HOLD_FOR_REVIEW)
        self.assertEqual(replay.blockers, ("PRIVACY_DECISION_INPUT_STALE",))

    def test_projection_replay_reuses_reviewed_classification_for_current_text(self):
        inputs = public_core(text="Current public role record")
        record = self.append("projection-current-text", inputs=inputs)
        replay = self.migration_store.replay_current_text_field(
            subject_ref="person:dp304:projection-current-text",
            record_ref="finding:dp304:projection-current-text",
            current_record_version="finding-version:1",
            field_name="normalized_claim",
            current_text_value=inputs.text_value or "",
        )
        self.assertTrue(replay.allowed)
        self.assertEqual(replay.decision_ref, record.decision_id)

        stale = self.migration_store.replay_current_text_field(
            subject_ref="person:dp304:projection-current-text",
            record_ref="finding:dp304:projection-current-text",
            current_record_version="finding-version:1",
            field_name="normalized_claim",
            current_text_value="Changed public role record",
        )
        self.assertFalse(stale.allowed)
        self.assertEqual(stale.blockers, ("PRIVACY_DECISION_INPUT_STALE",))

    def test_supersession_is_append_only_and_old_record_version_becomes_stale(self):
        first = self.append("supersession", record_version="finding-version:1")
        second = self.append(
            "supersession",
            record_version="finding-version:2",
            supersedes_decision_id=first.decision_id,
        )

        current = self.replay("supersession", record_version="finding-version:2")
        self.assertTrue(current.allowed)
        self.assertEqual(current.decision_ref, second.decision_id)
        stale = self.replay("supersession", record_version="finding-version:1")
        self.assertEqual(stale.decision.decision, PublicationDecision.HOLD_FOR_REVIEW)
        self.assertEqual(stale.blockers, ("PRIVACY_DECISION_RECORD_VERSION_STALE",))

        count = self.migration_store.run(
            "SELECT count(*)::text FROM privacy_publication_decision "
            "WHERE subject_ref=:'subject_ref' AND record_ref=:'record_ref';",
            subject_ref="person:dp304:supersession",
            record_ref="finding:dp304:supersession",
        )
        self.assertEqual(count, "2")
        with self.assertRaises(RuntimeError):
            self.migration_store.run(
                "UPDATE privacy_publication_decision SET reviewer_ref='reviewer:changed' "
                "WHERE decision_id=:'decision_id';",
                decision_id=first.decision_id,
            )

    def test_policy_version_change_makes_prior_allow_stale(self):
        self.append("policy-stale")

        with patch.object(
            privacy_persistence,
            "PRIVACY_POLICY_VERSION",
            "privacy-minimization-v2-test",
        ):
            replay = self.replay("policy-stale")

        self.assertEqual(replay.decision.decision, PublicationDecision.HOLD_FOR_REVIEW)
        self.assertEqual(replay.blockers, ("PRIVACY_DECISION_POLICY_VERSION_STALE",))
        self.assertFalse(replay.allowed)

    def test_hash_valid_shape_with_fabricated_integrity_is_prohibited_on_replay(self):
        zero = "0" * 64
        one = "1" * 64
        self.migration_store.run(
            """
            INSERT INTO privacy_publication_decision (
                decision_id, contract_version, subject_ref, record_ref, record_version,
                field_name, data_class, relevance_reason, explicitly_approved,
                is_published_version, is_ephemeral, text_value_sha256, input_sha256,
                privacy_policy_version, decision_action, decision_reasons,
                reviewer_ref, audit_ref, reviewed_at_text, review_sequence,
                decision_integrity_sha256
            ) VALUES (
                :'decision_id', :'contract_version', :'subject_ref', :'record_ref', 'finding-version:1',
                'normalized_claim', 'PUBLIC_CORE', 'PUBLIC_ROLE', false,
                false, false, :'text_hash', :'input_hash', 'privacy-minimization-v1',
                'ALLOW', '["PUBLIC_CORE"]'::jsonb, 'reviewer:tampered', 'audit:tampered',
                '2026-10-06T10:30:00+02:00', 1, :'integrity'
            );
            """,
            decision_id=f"privacy-decision:{zero}",
            contract_version=PRIVACY_PUBLICATION_DECISION_CONTRACT_VERSION,
            subject_ref="person:dp304:tampered",
            record_ref="finding:dp304:tampered",
            text_hash=one,
            input_hash=one,
            integrity=zero,
        )

        replay = self.replay("tampered")
        self.assertEqual(replay.decision.decision, PublicationDecision.PROHIBIT)
        self.assertEqual(replay.blockers, ("PRIVACY_DECISION_TAMPERED",))
        self.assertFalse(replay.allowed)

    def test_fresh_schema_has_same_contract_and_can_replay_allow(self):
        record = self.append("fresh-schema", store=self.fresh_store)
        replay = self.replay("fresh-schema", store=self.fresh_store)

        self.assertTrue(replay.allowed)
        self.assertEqual(replay.decision_ref, record.decision_id)

        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261006-add-privacy-publication-decision-ledger.sql"
        ).read_text()
        for sql in (schema, migration):
            for marker in (
                "CREATE TABLE IF NOT EXISTS privacy_publication_decision",
                "input_sha256",
                "privacy_policy_version",
                "supersedes_decision_id",
                "record_visibility",
                "CREATE TRIGGER privacy_publication_decision_append_only",
                "CREATE TRIGGER privacy_publication_decision_no_truncate",
            ):
                self.assertIn(marker, sql)


if __name__ == "__main__":
    unittest.main()

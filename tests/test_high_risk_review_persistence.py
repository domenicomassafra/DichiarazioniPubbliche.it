import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    HighRiskDecision,
    evaluate_high_risk_candidate,
)
from dichiarazioni_pubbliche.high_risk_review_persistence import (  # noqa: E402
    HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION,
    HighRiskReviewedPacketInput,
    HighRiskReviewedPacketStore,
    high_risk_packet_input_sha256,
)


MIGRATION = ROOT / "db" / "migrations" / "20261006-add-high-risk-reviewed-packet.sql"


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def held_input(
    *,
    source_text: str = "La procura comunica che Mario Rossi è indagato.",
    normalized_text: str = "Mario Rossi è indagato.",
) -> HighRiskReviewedPacketInput:
    return HighRiskReviewedPacketInput(
        source_text=source_text,
        normalized_text=normalized_text,
        legal_status_claim=True,
        identity_resolved=True,
        privacy_allows=True,
        privacy_decision_ref="privacy-decision:dp309:1",
        privacy_decision_binding_ref="privacy-binding:dp309:1",
        official_record_state="APPROVED",
        official_record_ref="evidence:official-record:dp309:1",
        jurisdiction_state="MATCH",
        jurisdiction_ref="jurisdiction-review:it:dp309:1",
        effective_time_state="MATCH",
        effective_time_ref="effective-time:dp309:1",
        human_review_actor_ref="reviewer:dp309:primary:1",
        human_review_ref="human-review:dp309:1",
        human_reviewed_at="2026-10-06T11:20:00+02:00",
        human_review_approved=True,
        dual_control_approved=True,
        qualified_policy_accepted=False,
        policy_decision_ref=None,
    )


class HighRiskReviewPersistencePostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    migration_store: HighRiskReviewedPacketStore
    fresh_store: HighRiskReviewedPacketStore
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
    def setUpClass(cls):
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp309-high-risk-packet-")
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
                "CREATE DATABASE dp309_packet_migration; CREATE DATABASE dp309_packet_fresh;",
            )
            cls.migration_database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp309_packet_migration"
            )
            cls.fresh_database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp309_packet_fresh"
            )
            cls._apply_file(cls.migration_database_url, MIGRATION)
            cls._apply_file(cls.migration_database_url, MIGRATION)
            cls._apply_file(cls.fresh_database_url, ROOT / "db" / "schema.v1.sql")
            cls._apply_file(cls.fresh_database_url, MIGRATION)
            cls._apply_file(cls.fresh_database_url, MIGRATION)
            cls.migration_store = HighRiskReviewedPacketStore(cls.migration_database_url)
            cls.fresh_store = HighRiskReviewedPacketStore(cls.fresh_database_url)
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

    def append(
        self,
        suffix: str,
        *,
        inputs: HighRiskReviewedPacketInput | None = None,
        record_version: str = "finding-record-version-v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        supersedes_packet_id: str | None = None,
        store: HighRiskReviewedPacketStore | None = None,
    ):
        target = store or self.migration_store
        return target.append_reviewed_packet(
            record_ref=f"record:dp309:{suffix}",
            finding_ref=f"finding:dp309:{suffix}",
            record_version=record_version,
            inputs=inputs or held_input(),
            supersedes_packet_id=supersedes_packet_id,
        )

    def replay(
        self,
        suffix: str,
        *,
        inputs: HighRiskReviewedPacketInput | None = None,
        record_version: str = "finding-record-version-v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        store: HighRiskReviewedPacketStore | None = None,
    ):
        target = store or self.migration_store
        return target.replay_current(
            record_ref=f"record:dp309:{suffix}",
            finding_ref=f"finding:dp309:{suffix}",
            current_record_version=record_version,
            inputs=inputs or held_input(),
        )

    def test_missing_dp307_acceptance_persists_and_replays_hold(self):
        record = self.append("dp307-hold")
        replay = self.replay("dp307-hold")

        self.assertEqual(record.decision_disposition, "HOLD_HIGH_RISK")
        self.assertFalse(record.qualified_policy_accepted)
        self.assertIsNone(record.policy_decision_ref)
        self.assertIn("HOLD_HIGH_RISK_QUALIFIED_POLICY_REQUIRED", record.decision_reason_codes)
        self.assertEqual(replay.packet_ref, record.packet_id)
        self.assertEqual(replay.blockers, ())
        self.assertEqual(replay.decision.disposition, "HOLD_HIGH_RISK")
        self.assertFalse(replay.publication_allowed)

    def test_exact_text_inputs_are_hash_bound_and_bodies_are_not_persisted(self):
        source = "Secondo la procura, Rossi avrebbe commesso una frode privata sintetica."
        normalized = "Rossi ha commesso una frode sintetica."
        inputs = held_input(source_text=source, normalized_text=normalized)
        record = self.append("text-hash", inputs=inputs)

        self.assertEqual(record.input_sha256, high_risk_packet_input_sha256(inputs))
        self.assertEqual(record.source_text_sha256, hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(
            record.normalized_text_sha256,
            hashlib.sha256(normalized.encode()).hexdigest(),
        )
        self.assertTrue(record.source_allegation_framing)
        self.assertFalse(record.normalized_allegation_framing)
        self.assertIn("HOLD_HIGH_RISK_ALLEGATION_FRAMING_LOST", record.decision_reason_codes)

        stored = self.migration_store.run(
            "SELECT row_to_json(row)::text FROM (SELECT * FROM private_high_risk_review_packet "
            "WHERE packet_id=:'packet_id') row;",
            packet_id=record.packet_id,
        )
        self.assertNotIn(source, stored)
        self.assertNotIn(normalized, stored)
        columns = json.loads(
            self.migration_store.run(
                "SELECT COALESCE(json_agg(column_name ORDER BY ordinal_position), '[]'::json)::text "
                "FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='private_high_risk_review_packet';"
            )
        )
        self.assertNotIn("source_text", columns)
        self.assertNotIn("normalized_text", columns)

    def test_projection_hash_bound_replay_requires_current_source_and_privacy_refs(self):
        inputs = held_input()
        record = self.append("projection-hash-bound", inputs=inputs)
        replay = self.migration_store.replay_current_hash_bound(
            record_ref="record:dp309:projection-hash-bound",
            finding_ref="finding:dp309:projection-hash-bound",
            current_record_version=record.record_version,
            current_source_text_sha256=hashlib.sha256(
                inputs.source_text.encode("utf-8")
            ).hexdigest(),
            current_normalized_text=inputs.normalized_text,
            privacy_decision_ref=inputs.privacy_decision_ref,
            privacy_decision_binding_ref=inputs.privacy_decision_binding_ref,
        )
        self.assertEqual(replay.blockers, ())
        self.assertEqual(replay.packet_ref, record.packet_id)
        self.assertEqual(replay.decision, self.replay("projection-hash-bound").decision)

        stale = self.migration_store.replay_current_hash_bound(
            record_ref="record:dp309:projection-hash-bound",
            finding_ref="finding:dp309:projection-hash-bound",
            current_record_version=record.record_version,
            current_source_text_sha256="0" * 64,
            current_normalized_text=inputs.normalized_text,
            privacy_decision_ref=inputs.privacy_decision_ref,
            privacy_decision_binding_ref=inputs.privacy_decision_binding_ref,
        )
        self.assertIn("HIGH_RISK_PACKET_SOURCE_TEXT_STALE", stale.blockers)
        self.assertIsNone(stale.packet_ref)

    def test_current_input_or_record_version_change_is_stale(self):
        self.append("stale")
        changed = held_input(normalized_text="Mario Rossi è stato assolto.")
        input_replay = self.replay("stale", inputs=changed)
        self.assertEqual(input_replay.blockers, ("HIGH_RISK_PACKET_INPUT_STALE",))
        self.assertIsNone(input_replay.packet_ref)
        self.assertFalse(input_replay.publication_allowed)

        version_replay = self.replay(
            "stale",
            record_version="finding-record-version-v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        self.assertEqual(
            version_replay.blockers,
            ("HIGH_RISK_PACKET_RECORD_VERSION_STALE",),
        )

    def test_self_consistent_old_output_is_rejected_when_canonical_evaluator_diverges(self):
        record = self.append("replay-mismatch")

        def changed_evaluator(**kwargs):
            current = evaluate_high_risk_candidate(**kwargs)
            return HighRiskDecision(
                disposition=current.disposition,
                reason_codes=tuple((*current.reason_codes, "SIMULATED_CANONICAL_POLICY_CHANGE")),
                signals=current.signals,
                policy_decision_ref=current.policy_decision_ref,
                version=current.version,
            )

        with patch(
            "dichiarazioni_pubbliche.high_risk_review_persistence.evaluate_high_risk_candidate",
            side_effect=changed_evaluator,
        ):
            replay = self.replay("replay-mismatch")
        self.assertEqual(
            replay.blockers,
            ("HIGH_RISK_PACKET_POLICY_REPLAY_MISMATCH",),
        )
        self.assertIsNone(replay.packet_ref)
        self.assertNotEqual(replay.decision_binding_sha256, record.decision_binding_sha256)
        self.assertFalse(replay.publication_allowed)

    def test_hash_shaped_fabricated_packet_is_detected_as_tampered(self):
        source = self.append("tamper-source")
        zero = "0" * 64
        self.migration_store.run(
            """
            INSERT INTO private_high_risk_review_packet
            SELECT
                :'packet_id', contract_version, :'record_ref', :'finding_ref', record_version,
                source_text_sha256, normalized_text_sha256,
                source_allegation_framing, normalized_allegation_framing,
                legal_status_claim, identity_sensitive, sensitive_private,
                minor_victim_private_person, identity_resolved, privacy_allows,
                privacy_decision_ref, privacy_decision_binding_ref,
                official_record_state, official_record_ref, official_record_approved,
                jurisdiction_state, jurisdiction_ref, jurisdiction_match,
                effective_time_state, effective_time_ref, effective_time_match,
                human_review_actor_ref, human_review_ref, human_reviewed_at_text,
                human_review_approved, dual_control_approved,
                qualified_policy_accepted, policy_decision_ref, high_risk_policy_version,
                input_sha256, decision_disposition, decision_reason_codes, risk_classes,
                procedural_statuses, decision_policy_ref, decision_binding_sha256,
                1, NULL, :'integrity', record_visibility, now()
            FROM private_high_risk_review_packet
            WHERE packet_id=:'source_packet_id';
            """,
            packet_id=f"high-risk-packet:{zero}",
            record_ref="record:dp309:tampered",
            finding_ref="finding:dp309:tampered",
            integrity=zero,
            source_packet_id=source.packet_id,
        )
        replay = self.replay("tampered")
        self.assertEqual(replay.blockers, ("HIGH_RISK_PACKET_TAMPERED",))
        self.assertIsNone(replay.packet_ref)
        self.assertFalse(replay.publication_allowed)

    def test_supersession_is_explicit_append_only_and_history_is_preserved(self):
        first = self.append("supersession")
        with self.assertRaisesRegex(ValueError, "HIGH_RISK_PACKET_SUPERSESSION_REQUIRED"):
            self.append(
                "supersession",
                record_version="finding-record-version-v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            )
        second = self.append(
            "supersession",
            record_version="finding-record-version-v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            supersedes_packet_id=first.packet_id,
        )
        self.assertEqual(second.packet_sequence, 2)
        self.assertEqual(second.supersedes_packet_id, first.packet_id)
        replay = self.replay(
            "supersession",
            record_version="finding-record-version-v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        self.assertEqual(replay.packet_ref, second.packet_id)
        count = self.migration_store.run(
            "SELECT count(*)::text FROM private_high_risk_review_packet "
            "WHERE record_ref='record:dp309:supersession';"
        )
        self.assertEqual(count, "2")
        for sql in (
            "UPDATE private_high_risk_review_packet SET record_version='tampered' "
            f"WHERE packet_id='{first.packet_id}';",
            f"DELETE FROM private_high_risk_review_packet WHERE packet_id='{first.packet_id}';",
            "TRUNCATE private_high_risk_review_packet;",
        ):
            with self.assertRaises(RuntimeError):
                self.migration_store.run_literal(sql)

    def test_qualified_policy_cannot_be_inferred_from_an_opaque_ref(self):
        with self.assertRaisesRegex(ValueError, "QUALIFIED_POLICY_REF_REQUIRED"):
            self.append(
                "policy-no-ref",
                inputs=replace(held_input(), qualified_policy_accepted=True),
            )
        with self.assertRaisesRegex(ValueError, "UNACCEPTED_POLICY_REF_FORBIDDEN"):
            self.append(
                "policy-ref-no-acceptance",
                inputs=replace(
                    held_input(),
                    policy_decision_ref="decision:dp307:future:synthetic",
                ),
            )

    def test_review_state_refs_are_required_for_positive_states(self):
        with self.assertRaisesRegex(ValueError, "OFFICIAL_RECORD_REF_REQUIRED"):
            self.append(
                "official-ref",
                inputs=replace(held_input(), official_record_ref=None),
            )
        with self.assertRaisesRegex(ValueError, "JURISDICTION_REF_REQUIRED"):
            self.append(
                "jurisdiction-ref",
                inputs=replace(held_input(), jurisdiction_ref=None),
            )
        with self.assertRaisesRegex(ValueError, "EFFECTIVE_TIME_REF_REQUIRED"):
            self.append(
                "effective-ref",
                inputs=replace(held_input(), effective_time_ref=None),
            )
        with self.assertRaisesRegex(ValueError, "HUMAN_REVIEW_BINDING_INCOMPLETE"):
            self.append(
                "human-review-ref",
                inputs=replace(held_input(), human_review_ref=None),
            )
        with self.assertRaisesRegex(ValueError, "HUMAN_REVIEW_APPROVAL_REF_REQUIRED"):
            self.append(
                "human-review-approval-ref",
                inputs=replace(
                    held_input(),
                    human_review_actor_ref=None,
                    human_review_ref=None,
                    human_reviewed_at=None,
                    human_review_approved=True,
                ),
            )

    def test_future_qualified_packet_waits_only_for_dp310_dual_control(self):
        inputs = replace(
            held_input(),
            qualified_policy_accepted=True,
            policy_decision_ref="decision:dp307:synthetic-future:legal-status-v1",
            dual_control_approved=False,
        )
        record = self.append("dp310-boundary", inputs=inputs)
        replay = self.replay("dp310-boundary", inputs=inputs)

        self.assertEqual(
            record.decision_reason_codes,
            ("HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED",),
        )
        self.assertEqual(
            replay.decision.reason_codes,
            ("HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED",),
        )
        self.assertEqual(replay.blockers, ())
        self.assertFalse(replay.publication_allowed)

    def test_fresh_schema_and_migration_share_private_packet_contract(self):
        record = self.append("fresh", store=self.fresh_store)
        replay = self.replay("fresh", store=self.fresh_store)
        self.assertEqual(replay.packet_ref, record.packet_id)
        self.assertFalse(replay.publication_allowed)

        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        migration = MIGRATION.read_text()
        markers = (
            "CREATE TABLE IF NOT EXISTS private_high_risk_review_packet",
            "normalized_text_sha256",
            "privacy_decision_binding_ref",
            "official_record_state",
            "effective_time_state",
            "human_review_actor_ref",
            "qualified_policy_accepted",
            "input_sha256",
            "decision_binding_sha256",
            "supersedes_packet_id",
            "record_visibility",
            "CREATE TRIGGER private_high_risk_review_packet_append_only",
            "CREATE TRIGGER private_high_risk_review_packet_no_truncate",
        )
        for sql in (schema, migration):
            for marker in markers:
                self.assertIn(marker, sql)

        migration_columns = self._psql(
            self.migration_database_url,
            "SELECT string_agg(column_name || ':' || data_type, ',' ORDER BY ordinal_position) "
            "FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name='private_high_risk_review_packet';",
        )
        fresh_columns = self._psql(
            self.fresh_database_url,
            "SELECT string_agg(column_name || ':' || data_type, ',' ORDER BY ordinal_position) "
            "FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name='private_high_risk_review_packet';",
        )
        self.assertEqual(fresh_columns, migration_columns)
        self.assertEqual(record.contract_version, HIGH_RISK_REVIEW_PACKET_CONTRACT_VERSION)


if __name__ == "__main__":
    unittest.main()

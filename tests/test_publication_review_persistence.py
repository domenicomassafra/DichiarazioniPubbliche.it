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

from dichiarazioni_pubbliche.policy.challenge_workflow import (  # noqa: E402
    ChallengeContext,
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
    evaluate_transition,
)
from dichiarazioni_pubbliche.publication_eligibility import (  # noqa: E402
    evaluate_publication_eligibility,
)
from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    ReviewRole,
    ReviewStage,
    build_review_event,
    evaluate_publication_review,
)
from dichiarazioni_pubbliche.publication_review_persistence import (  # noqa: E402
    PublicationReviewPersistenceStore,
    build_identity_attestation,
)
from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority,
    provision_reviewer_credential,
)
from tests.test_publication_review_control import high_risk, safety  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class StaticAuthority:
    def __init__(self, *attestations):
        self.by_id = {item.receipt_id: item for item in attestations}

    def resolve(self, receipt_id: str):
        return self.by_id.get(receipt_id)


def review_event(
    *,
    record_id: str,
    actor_ref: str,
    credential: str,
    stage=ReviewStage.PRIMARY,
    role=ReviewRole.DECISION_REVIEWER,
    previous=None,
):
    risk = high_risk("LEGAL")
    safety_result = safety()
    return build_review_event(
        record_id=record_id,
        record_version="finding-version:1",
        stage=stage,
        role=role,
        action="APPROVED",
        actor_ref=actor_ref,
        credential_fingerprint=credential,
        reviewed_at=(
            "2026-10-06T00:10:00+02:00"
            if previous is None
            else "2026-10-06T00:15:00+02:00"
        ),
        publication_safety=safety_result,
        high_risk=risk,
        high_risk_input_binding_sha256="b" * 64,
        previous_event=previous,
    )


def attestation(event, receipt_id):
    return build_identity_attestation(
        event,
        receipt_id=receipt_id,
        authority_version="test-operator-authority-v1",
        issued_at="2026-10-06T00:09:00+02:00",
    )


class PublicationReviewPersistencePostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    database_url: str
    store: PublicationReviewPersistenceStore
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
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp310-review-ledger-")
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
                    "CREATE DATABASE dp310_review_ledger;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp310_review_ledger"
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
                        / "20261006-add-publication-review-attested-ledger.sql"
                    ),
                ]
            )
            cls.store = PublicationReviewPersistenceStore(cls.database_url)
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

    def _direct_insert(self, event, *, receipt_id, authority_binding):
        self.store.run(
            """
            INSERT INTO publication_review_event_durable (
                event_id, record_id, record_version, sequence,
                previous_event_id, previous_integrity_sha256,
                actor_ref, credential_fingerprint, policy_version, reviewed_at_text,
                event_json, integrity_sha256,
                identity_authority_receipt_id, identity_authority_binding_sha256
            ) VALUES (
                :'event_id', :'record_id', :'record_version', :'sequence'::integer,
                NULLIF(:'previous_event_id',''), NULLIF(:'previous_integrity_sha256',''),
                :'actor_ref', :'credential_fingerprint', :'policy_version', :'reviewed_at_text',
                :'event_json'::jsonb, :'integrity_sha256',
                :'authority_receipt_id', :'authority_binding_sha256'
            );
            """,
            event_id=event.event_id,
            record_id=event.record_id,
            record_version=event.record_version,
            sequence=event.sequence,
            previous_event_id=event.previous_event_id or "",
            previous_integrity_sha256=event.previous_integrity_sha256 or "",
            actor_ref=event.actor_ref,
            credential_fingerprint=event.credential_fingerprint,
            policy_version=event.policy_version,
            reviewed_at_text=event.reviewed_at,
            event_json=json.dumps(event.__dict__, default=str, sort_keys=True),
            integrity_sha256=event.integrity_sha256,
            authority_receipt_id=receipt_id,
            authority_binding_sha256=authority_binding,
        )

    def test_exact_actor_object_policy_and_chain_are_durable_and_replayable(self):
        record_id = "finding:durable-replay"
        primary = review_event(
            record_id=record_id,
            actor_ref="reviewer:primary",
            credential="1" * 64,
        )
        independent = review_event(
            record_id=record_id,
            actor_ref="reviewer:independent",
            credential="2" * 64,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            previous=primary,
        )
        first = attestation(primary, "authority-receipt:durable:1")
        second = attestation(independent, "authority-receipt:durable:2")
        authority = StaticAuthority(first, second)
        self.store.append_attested_event(
            primary, authority_receipt_id=first.receipt_id, authority=authority
        )
        self.store.append_attested_event(
            independent, authority_receipt_id=second.receipt_id, authority=authority
        )

        replay = self.store.replay_attested_chain(record_id, authority=authority)
        self.assertTrue(replay.authority_verified)
        self.assertEqual(replay.events, (primary, independent))
        self.assertEqual(replay.events[0].actor_ref, "reviewer:primary")
        self.assertEqual(replay.events[0].record_version, "finding-version:1")
        self.assertEqual(replay.events[0].policy_version, primary.policy_version)

        risk = high_risk("LEGAL")
        result = evaluate_publication_review(
            record_id=record_id,
            record_version="finding-version:1",
            publication_safety=safety(),
            high_risk=risk,
            high_risk_input_binding_sha256="b" * 64,
            events=replay.events,
        )
        self.assertTrue(result.dual_control_satisfied)

    def test_missing_identity_authority_fails_closed(self):
        replay = self.store.replay_attested_chain(
            "finding:anything",
            authority=None,
        )
        self.assertEqual(replay.events, ())
        self.assertEqual(replay.blockers, ("REVIEW_IDENTITY_AUTHORITY_UNAVAILABLE",))

    def test_database_rows_are_append_only_for_normal_sql_writers(self):
        record_id = "finding:append-only"
        primary = review_event(
            record_id=record_id,
            actor_ref="reviewer:append",
            credential="3" * 64,
        )
        proof = attestation(primary, "authority-receipt:append-only")
        authority = StaticAuthority(proof)
        self.store.append_attested_event(
            primary,
            authority_receipt_id=proof.receipt_id,
            authority=authority,
        )
        for sql in (
            "UPDATE publication_review_event_durable SET actor_ref='forged' "
            f"WHERE event_id='{primary.event_id}';",
            "DELETE FROM publication_review_event_durable "
            f"WHERE event_id='{primary.event_id}';",
            "TRUNCATE publication_review_event_durable;",
        ):
            with self.subTest(sql=sql.split()[0]):
                with self.assertRaises(RuntimeError):
                    self.store.run_literal(sql)
                count = self.store.run(
                    "SELECT count(*) FROM publication_review_event_durable "
                    "WHERE event_id=:'event_id';",
                    event_id=primary.event_id,
                )
                self.assertEqual(count, "1")

    def test_hash_valid_fabricated_database_history_is_not_identity_authority(self):
        record_id = "finding:fabricated-history"
        primary = review_event(
            record_id=record_id,
            actor_ref="reviewer:fake-primary",
            credential="4" * 64,
        )
        independent = review_event(
            record_id=record_id,
            actor_ref="reviewer:fake-independent",
            credential="5" * 64,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            previous=primary,
        )
        self._direct_insert(
            primary,
            receipt_id="forged-authority-receipt:1",
            authority_binding="a" * 64,
        )
        self._direct_insert(
            independent,
            receipt_id="forged-authority-receipt:2",
            authority_binding="b" * 64,
        )
        replay = self.store.replay_attested_chain(
            record_id,
            authority=StaticAuthority(),
        )
        self.assertEqual(replay.events, ())
        self.assertIn("REVIEW_IDENTITY_AUTHORITY_RECEIPT_UNKNOWN", replay.blockers)

    def test_copying_a_real_authority_receipt_cannot_authorize_a_different_event(self):
        record_id = "finding:copied-receipt"
        primary = review_event(
            record_id=record_id,
            actor_ref="reviewer:real",
            credential="6" * 64,
        )
        proof = attestation(primary, "authority-receipt:real")
        authority = StaticAuthority(proof)
        self.store.append_attested_event(
            primary,
            authority_receipt_id=proof.receipt_id,
            authority=authority,
        )
        forged = review_event(
            record_id=record_id,
            actor_ref="reviewer:forged-second",
            credential="7" * 64,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            previous=primary,
        )
        self._direct_insert(
            forged,
            receipt_id=proof.receipt_id,
            authority_binding=proof.binding_sha256,
        )
        replay = self.store.replay_attested_chain(record_id, authority=authority)
        self.assertEqual(replay.events, ())
        self.assertIn("REVIEW_IDENTITY_AUTHORITY_EVENT_MISMATCH", replay.blockers)

    def test_dp303_reviewer_separation_uses_the_same_durable_actor_identity(self):
        record_id = "finding:dp303-identity"
        primary = review_event(
            record_id=record_id,
            actor_ref="reviewer:dp303-shared",
            credential="8" * 64,
        )
        proof = attestation(primary, "authority-receipt:dp303")
        authority = StaticAuthority(proof)
        self.store.append_attested_event(
            primary,
            authority_receipt_id=proof.receipt_id,
            authority=authority,
        )
        replay = self.store.replay_attested_chain(record_id, authority=authority)
        durable_actor = replay.events[0].actor_ref
        decision = evaluate_transition(
            ChallengeContext(
                kind=ChallengeKind.APPEAL,
                current_state=ChallengeState.INDEPENDENT_REVIEW_PENDING,
                actor_role=ChallengeRole.APPEAL_REVIEWER,
                actor_id=durable_actor,
                original_reviewer_id=durable_actor,
                challenge_review_approved=True,
                target_finding_review_approved=True,
                reanalysis_trigger_processed=True,
            )
        )
        self.assertNotIn(
            decision.next_state,
            {ChallengeState.UPHELD, ChallengeState.OVERTURNED},
        )

    def test_dp303_appeal_and_correction_append_without_rewriting_attested_history(self):
        with tempfile.TemporaryDirectory(prefix="dp310-dp303-authority-") as authority_tmp:
            authority_root = Path(authority_tmp) / "authority"
            original_identity = provision_reviewer_credential(
                authority_root,
                credential_id="original-v1",
                actor_ref="reviewer:dp303-original",
                key_version="v1",
                secret_hex="a1" * 32,
            )
            appeal_identity = provision_reviewer_credential(
                authority_root,
                credential_id="appeal-v1",
                actor_ref="reviewer:dp303-appeal",
                key_version="v1",
                secret_hex="a2" * 32,
            )
            authority = LocalFileReviewerIdentityAuthority(authority_root)

            original = review_event(
                record_id="finding:dp303-history:v1",
                actor_ref=original_identity.actor_ref,
                credential=original_identity.credential_fingerprint,
            )
            original_receipt = authority.issue(
                original,
                credential_id=original_identity.credential_id,
                issued_at="2026-10-06T00:20:00+02:00",
            )
            self.store.append_attested_event(
                original,
                authority_receipt_id=original_receipt.receipt_id,
                authority=authority,
            )
            original_receipt_path = (
                authority_root / "receipts" / f"{original_receipt.receipt_id}.json"
            )
            original_receipt_bytes = original_receipt_path.read_bytes()
            original_row_before = self.store.run(
                """
                SELECT row_to_json(row)::text
                FROM (
                  SELECT event_id,record_id,record_version,sequence,actor_ref,
                         credential_fingerprint,policy_version,reviewed_at_text,
                         event_json,integrity_sha256,identity_authority_receipt_id,
                         identity_authority_binding_sha256,persisted_at
                  FROM publication_review_event_durable
                  WHERE event_id=:'event_id'
                ) row;
                """,
                event_id=original.event_id,
            )

            replay = self.store.replay_attested_chain(
                original.record_id,
                authority=authority,
            )
            self.assertTrue(replay.authority_verified)
            durable_original_actor = replay.events[0].actor_ref

            same_actor_appeal = evaluate_transition(
                ChallengeContext(
                    kind=ChallengeKind.APPEAL,
                    current_state=ChallengeState.INDEPENDENT_REVIEW_PENDING,
                    actor_role=ChallengeRole.APPEAL_REVIEWER,
                    actor_id=durable_original_actor,
                    original_reviewer_id=durable_original_actor,
                    challenge_review_approved=True,
                    target_finding_review_approved=True,
                    reanalysis_trigger_processed=True,
                )
            )
            self.assertNotIn(
                same_actor_appeal.next_state,
                {ChallengeState.UPHELD, ChallengeState.OVERTURNED},
            )

            separate_actor_appeal = evaluate_transition(
                ChallengeContext(
                    kind=ChallengeKind.APPEAL,
                    current_state=ChallengeState.INDEPENDENT_REVIEW_PENDING,
                    actor_role=ChallengeRole.APPEAL_REVIEWER,
                    actor_id=appeal_identity.actor_ref,
                    original_reviewer_id=durable_original_actor,
                    challenge_review_approved=True,
                    target_finding_review_approved=True,
                    reanalysis_trigger_processed=True,
                )
            )
            self.assertTrue(separate_actor_appeal.allowed)
            self.assertEqual(separate_actor_appeal.next_state, ChallengeState.UPHELD)

            appeal_review = review_event(
                record_id="appeal:dp303-history:1",
                actor_ref=appeal_identity.actor_ref,
                credential=appeal_identity.credential_fingerprint,
            )
            corrected_review = review_event(
                record_id="finding:dp303-history:v2",
                actor_ref=appeal_identity.actor_ref,
                credential=appeal_identity.credential_fingerprint,
            )
            appeal_receipt = authority.issue(
                appeal_review,
                credential_id=appeal_identity.credential_id,
                issued_at="2026-10-06T00:25:00+02:00",
            )
            corrected_receipt = authority.issue(
                corrected_review,
                credential_id=appeal_identity.credential_id,
                issued_at="2026-10-06T00:30:00+02:00",
            )
            self.store.append_attested_event(
                appeal_review,
                authority_receipt_id=appeal_receipt.receipt_id,
                authority=authority,
            )
            self.store.append_attested_event(
                corrected_review,
                authority_receipt_id=corrected_receipt.receipt_id,
                authority=authority,
            )

            original_row_after = self.store.run(
                """
                SELECT row_to_json(row)::text
                FROM (
                  SELECT event_id,record_id,record_version,sequence,actor_ref,
                         credential_fingerprint,policy_version,reviewed_at_text,
                         event_json,integrity_sha256,identity_authority_receipt_id,
                         identity_authority_binding_sha256,persisted_at
                  FROM publication_review_event_durable
                  WHERE event_id=:'event_id'
                ) row;
                """,
                event_id=original.event_id,
            )
            self.assertEqual(original_row_after, original_row_before)
            self.assertEqual(original_receipt_path.read_bytes(), original_receipt_bytes)
            self.assertEqual(
                self.store.run(
                    "SELECT count(*)::text FROM publication_review_event_durable "
                    "WHERE record_id IN (:'original',:'appeal',:'corrected');",
                    original=original.record_id,
                    appeal=appeal_review.record_id,
                    corrected=corrected_review.record_id,
                ),
                "3",
            )
            self.assertEqual(
                self.store.replay_attested_chain(
                    original.record_id,
                    authority=LocalFileReviewerIdentityAuthority(authority_root),
                ).events,
                (original,),
            )

    def test_local_file_authority_persists_two_distinct_reviewers_across_restart(self):
        with tempfile.TemporaryDirectory(prefix="dp311-local-authority-") as authority_tmp:
            authority_root = Path(authority_tmp) / "authority"
            primary_identity = provision_reviewer_credential(
                authority_root,
                credential_id="primary-v1",
                actor_ref="reviewer:local-primary",
                key_version="v1",
                secret_hex="91" * 32,
            )
            independent_identity = provision_reviewer_credential(
                authority_root,
                credential_id="independent-v1",
                actor_ref="reviewer:local-independent",
                key_version="v1",
                secret_hex="92" * 32,
            )
            authority = LocalFileReviewerIdentityAuthority(authority_root)
            record_id = "finding:local-authority-restart"
            primary = review_event(
                record_id=record_id,
                actor_ref=primary_identity.actor_ref,
                credential=primary_identity.credential_fingerprint,
            )
            independent = review_event(
                record_id=record_id,
                actor_ref=independent_identity.actor_ref,
                credential=independent_identity.credential_fingerprint,
                stage=ReviewStage.INDEPENDENT,
                role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
                previous=primary,
            )
            primary_receipt = authority.issue(
                primary,
                credential_id=primary_identity.credential_id,
                issued_at="2026-10-06T00:09:00+02:00",
            )
            independent_receipt = authority.issue(
                independent,
                credential_id=independent_identity.credential_id,
                issued_at="2026-10-06T00:14:00+02:00",
            )
            self.store.append_attested_event(
                primary,
                authority_receipt_id=primary_receipt.receipt_id,
                authority=authority,
            )
            self.store.append_attested_event(
                independent,
                authority_receipt_id=independent_receipt.receipt_id,
                authority=authority,
            )

            # Revocation blocks new approvals but does not erase historical verification.
            authority.revoke(primary_identity.credential_id)
            restarted = LocalFileReviewerIdentityAuthority(authority_root)
            replay = self.store.replay_attested_chain(record_id, authority=restarted)
            self.assertTrue(replay.authority_verified)
            self.assertEqual(replay.events, (primary, independent))
            self.assertNotEqual(
                replay.events[0].credential_fingerprint,
                replay.events[1].credential_fingerprint,
            )
            result = evaluate_publication_review(
                record_id=record_id,
                record_version="finding-version:1",
                publication_safety=safety(),
                high_risk=high_risk("LEGAL"),
                high_risk_input_binding_sha256="b" * 64,
                events=replay.events,
            )
            self.assertTrue(result.dual_control_satisfied)

    def test_runtime_eligibility_consumes_only_authority_attested_durable_replay(self):
        with tempfile.TemporaryDirectory(prefix="dp310-eligibility-authority-") as authority_tmp:
            authority_root = Path(authority_tmp) / "authority"
            primary_identity = provision_reviewer_credential(
                authority_root,
                credential_id="eligibility-primary-v1",
                actor_ref="reviewer:eligibility-primary",
                key_version="v1",
                secret_hex="b1" * 32,
            )
            independent_identity = provision_reviewer_credential(
                authority_root,
                credential_id="eligibility-independent-v1",
                actor_ref="reviewer:eligibility-independent",
                key_version="v1",
                secret_hex="b2" * 32,
            )
            authority = LocalFileReviewerIdentityAuthority(authority_root)
            record_id = "finding:attested-eligibility"
            primary = review_event(
                record_id=record_id,
                actor_ref=primary_identity.actor_ref,
                credential=primary_identity.credential_fingerprint,
            )
            independent = review_event(
                record_id=record_id,
                actor_ref=independent_identity.actor_ref,
                credential=independent_identity.credential_fingerprint,
                stage=ReviewStage.INDEPENDENT,
                role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
                previous=primary,
            )
            primary_receipt = authority.issue(
                primary,
                credential_id=primary_identity.credential_id,
                issued_at="2026-10-06T00:40:00+02:00",
            )
            independent_receipt = authority.issue(
                independent,
                credential_id=independent_identity.credential_id,
                issued_at="2026-10-06T00:45:00+02:00",
            )
            self.store.append_attested_event(
                primary,
                authority_receipt_id=primary_receipt.receipt_id,
                authority=authority,
            )
            self.store.append_attested_event(
                independent,
                authority_receipt_id=independent_receipt.receipt_id,
                authority=authority,
            )

            result = evaluate_publication_eligibility(
                record_id=record_id,
                record_version="finding-version:1",
                publication_safety=safety(),
                high_risk=high_risk("LEGAL"),
                high_risk_input_binding_sha256="b" * 64,
                review_store=self.store,
                review_authority=LocalFileReviewerIdentityAuthority(authority_root),
            )
            self.assertEqual(result.disposition, "ELIGIBLE_FOR_PROJECTION_REVALIDATION")
            self.assertEqual(
                result.counted_review_event_ids,
                (primary.event_id, independent.event_id),
            )
            for private_field in (
                "actor_ref",
                "credential_fingerprint",
                "identity_authority_receipt_id",
                "secret_hex",
                "mac_sha256",
            ):
                self.assertFalse(hasattr(result, private_field))

            missing_authority = evaluate_publication_eligibility(
                record_id=record_id,
                record_version="finding-version:1",
                publication_safety=safety(),
                high_risk=high_risk("LEGAL"),
                high_risk_input_binding_sha256="b" * 64,
                review_store=self.store,
                review_authority=None,
            )
            self.assertEqual(missing_authority.disposition, "HOLD_FOR_PUBLICATION_REVIEW")
            self.assertIn("REVIEW_IDENTITY_AUTHORITY_UNAVAILABLE", missing_authority.blockers)
            self.assertEqual(missing_authority.counted_review_event_ids, ())

    def test_runtime_eligibility_rejects_hash_valid_database_fabrication_without_receipts(self):
        with tempfile.TemporaryDirectory(prefix="dp310-fabricated-authority-") as authority_tmp:
            authority_root = Path(authority_tmp) / "authority"
            provision_reviewer_credential(
                authority_root,
                credential_id="real-v1",
                actor_ref="reviewer:real-authority",
                key_version="v1",
                secret_hex="c1" * 32,
            )
            authority = LocalFileReviewerIdentityAuthority(authority_root)
            record_id = "finding:forged-eligibility"
            primary = review_event(
                record_id=record_id,
                actor_ref="reviewer:forged-primary",
                credential="d1" * 32,
            )
            independent = review_event(
                record_id=record_id,
                actor_ref="reviewer:forged-independent",
                credential="d2" * 32,
                stage=ReviewStage.INDEPENDENT,
                role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
                previous=primary,
            )
            self._direct_insert(
                primary,
                receipt_id="forged-authority-receipt:eligibility:1",
                authority_binding="e1" * 32,
            )
            self._direct_insert(
                independent,
                receipt_id="forged-authority-receipt:eligibility:2",
                authority_binding="e2" * 32,
            )

            result = evaluate_publication_eligibility(
                record_id=record_id,
                record_version="finding-version:1",
                publication_safety=safety(),
                high_risk=high_risk("LEGAL"),
                high_risk_input_binding_sha256="b" * 64,
                review_store=self.store,
                review_authority=authority,
            )
            self.assertEqual(result.disposition, "HOLD_FOR_PUBLICATION_REVIEW")
            self.assertIn("REVIEW_IDENTITY_AUTHORITY_RECEIPT_UNKNOWN", result.blockers)
            self.assertEqual(result.counted_review_event_ids, ())

    def test_fresh_schema_and_additive_migration_share_the_durable_ledger_contract(self):
        schema = (ROOT / "db" / "schema.v1.sql").read_text()
        migration = (
            ROOT
            / "db"
            / "migrations"
            / "20261006-add-publication-review-attested-ledger.sql"
        ).read_text()
        for sql in (schema, migration):
            for marker in (
                "CREATE TABLE IF NOT EXISTS publication_review_event_durable",
                "identity_authority_receipt_id",
                "identity_authority_binding_sha256",
                "CREATE UNIQUE INDEX IF NOT EXISTS publication_review_event_durable_previous_idx",
                "CREATE TRIGGER publication_review_event_durable_append_only",
                "CREATE TRIGGER publication_review_event_durable_no_truncate",
            ):
                self.assertIn(marker, sql)


if __name__ == "__main__":
    unittest.main()

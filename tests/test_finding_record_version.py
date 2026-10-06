import hashlib
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.finding_record_version import (  # noqa: E402
    FINDING_RECORD_VERSION_CONTRACT,
    FindingRecordVersionStore,
)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class FindingRecordVersionPostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    database_url: str
    port: int
    store: FindingRecordVersionStore
    server_started = False

    @classmethod
    def _run_command(cls, args: list[str], *, input_text: str | None = None) -> str:
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
    def setUpClass(cls) -> None:
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )

        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="finding-record-version-")
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
                    "CREATE DATABASE finding_record_version_test;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/finding_record_version_test"
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
            cls.store = FindingRecordVersionStore(cls.database_url)
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
    def tearDownClass(cls) -> None:
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

    def setUp(self) -> None:
        self._reset_and_seed()

    def _reset_and_seed(self) -> None:
        self.store.run_literal(
            """
            DELETE FROM finding_assertion_citation
            WHERE id IN ('citation:material', 'citation:limitation');
            DELETE FROM finding_assertion
            WHERE id IN ('assertion:material', 'assertion:limitation');
            DELETE FROM finding_evidence
            WHERE finding_id = 'finding:record-version';
            DELETE FROM finding
            WHERE id = 'finding:record-version';
            DELETE FROM verification_run
            WHERE id = 'verification:record-version';
            DELETE FROM evidence_observation
            WHERE id IN ('observation:a', 'observation:b');
            DELETE FROM evidence
            WHERE id IN ('evidence:a', 'evidence:b');
            DELETE FROM atomic_claim
            WHERE id = 'claim:record-version';
            DELETE FROM content_item
            WHERE id = 'content:record-version';
            """
        )
        rationale = "Synthetic finding rationale."
        rationale_hash = hashlib.sha256(rationale.encode("utf-8")).hexdigest()
        limitation = "Synthetic limitation."
        limitation_hash = hashlib.sha256(limitation.encode("utf-8")).hexdigest()
        self.store.run(
            """
            INSERT INTO content_item (
                id, canonical_url, title, language, processing_status
            ) VALUES (
                'content:record-version', 'https://example.test/finding-version',
                'Synthetic Finding Version Source', 'it', 'PROCESSED'
            );

            INSERT INTO atomic_claim (
                id, content_id, normalized_claim, claim_type,
                temporal_scope, check_worthy, extraction_version, metadata
            ) VALUES (
                'claim:record-version', 'content:record-version',
                'Il valore sintetico è 10.', 'NUMERIC_STATISTIC',
                '{"statement_date":"2026-10-01"}'::jsonb,
                true, 'candidate-extraction-v1',
                '{"context_integrity":{"state":"CLEAR_AUTOMATIC"}}'::jsonb
            );

            INSERT INTO evidence (
                id, canonical_url, publisher, source_type, observed_at,
                content_sha256, rights_status
            ) VALUES
                (
                    'evidence:a', 'https://example.test/evidence-a', 'Authority A',
                    'PRIMARY_OFFICIAL', '2026-10-02T10:00:00+00:00', repeat('a', 64),
                    'UNKNOWN'
                ),
                (
                    'evidence:b', 'https://example.test/evidence-b', 'Authority B',
                    'PRIMARY_OFFICIAL', '2026-10-02T11:00:00+00:00', repeat('b', 64),
                    'UNKNOWN'
                );

            INSERT INTO evidence_observation (
                id, evidence_id, observation_type, value_text,
                extraction_method, extraction_version, status
            ) VALUES
                (
                    'observation:a', 'evidence:a', 'TEXT_VALUE', '10',
                    'SYNTHETIC_FIXTURE', 'fixture-v1', 'APPROVED'
                ),
                (
                    'observation:b', 'evidence:b', 'TEXT_VALUE', '10',
                    'SYNTHETIC_FIXTURE', 'fixture-v1', 'APPROVED'
                );

            INSERT INTO verification_run (
                id, claim_id, verification_kind, verification_version,
                verification_rule, input_fingerprint, statement_cutoff, assessment,
                evidence_ids, observation_ids, blockers, rationale_codes, result
            ) VALUES (
                'verification:record-version', 'claim:record-version', 'DETERMINISTIC',
                'deterministic-verification-v2',
                '{"rule":"synthetic","threshold":10}'::jsonb, repeat('c', 64),
                '2026-10-01', 'SUPPORTED',
                '["evidence:b","evidence:a"]'::jsonb,
                '["observation:b","observation:a"]'::jsonb,
                '[]'::jsonb, '["SYNTHETIC_ACCEPTANCE"]'::jsonb,
                '{"matched":true,"value":10}'::jsonb
            );

            INSERT INTO finding (
                id, claim_id, assessment, rationale, publication_status,
                policy_version, model_bundle, verification_run_id
            ) VALUES (
                'finding:record-version', 'claim:record-version', 'SUPPORTED',
                :'rationale', 'POLICY_HOLD', 'finding-policy-v1',
                '{"deterministic":true,"verification_input_fingerprint":"fixture"}'::jsonb,
                'verification:record-version'
            );

            INSERT INTO finding_evidence (finding_id, evidence_id, relation)
            VALUES
                ('finding:record-version', 'evidence:b', 'VERIFICATION_INPUT'),
                ('finding:record-version', 'evidence:a', 'VERIFICATION_INPUT');

            INSERT INTO finding_assertion (
                id, finding_id, assertion_text, assertion_text_sha256,
                assertion_type, material, required_relation, metadata
            ) VALUES
                (
                    'assertion:material', 'finding:record-version', :'rationale',
                    :'rationale_hash', 'RATIONALE_MATERIAL', true, 'SUPPORT',
                    '{"verification_run_id":"verification:record-version"}'::jsonb
                ),
                (
                    'assertion:limitation', 'finding:record-version', :'limitation',
                    :'limitation_hash', 'LIMITATION', false, 'LIMITATION',
                    '{"verification_run_id":"verification:record-version"}'::jsonb
                );

            INSERT INTO finding_assertion_citation (
                id, assertion_id, evidence_id, observation_id, relation, metadata
            ) VALUES
                (
                    'citation:material', 'assertion:material', 'evidence:a',
                    'observation:a', 'SUPPORT',
                    '{"verification_run_id":"verification:record-version"}'::jsonb
                ),
                (
                    'citation:limitation', 'assertion:limitation', 'evidence:b',
                    'observation:b', 'LIMITATION',
                    '{"verification_run_id":"verification:record-version"}'::jsonb
                );
            """,
            rationale=rationale,
            rationale_hash=rationale_hash,
            limitation=limitation,
            limitation_hash=limitation_hash,
        )

    def _version(self):
        return self.store.current_record_version("finding:record-version")

    def test_current_version_is_versioned_and_deterministic_across_store_replay(self):
        first = self._version()
        replayed = FindingRecordVersionStore(self.database_url).current_record_version(
            "finding:record-version"
        )
        self.assertEqual(first, replayed)
        self.assertEqual(first.contract_version, FINDING_RECORD_VERSION_CONTRACT)
        self.assertEqual(len(first.fingerprint_sha256), 64)
        self.assertEqual(
            first.record_version,
            f"{FINDING_RECORD_VERSION_CONTRACT}:{first.fingerprint_sha256}",
        )

    def test_caller_cannot_supply_a_record_version_or_fingerprint_as_authority(self):
        with self.assertRaises(TypeError):
            self.store.current_record_version(  # type: ignore[call-arg]
                "finding:record-version",
                record_version="caller:forged",
            )
        with self.assertRaises(ValueError) as ctx:
            self.store.current_record_version("finding:missing")
        self.assertIn("FINDING_RECORD_VERSION_NOT_FOUND", str(ctx.exception))

    def test_finding_verification_evidence_and_assertion_mutations_change_version(self):
        mutations = (
            (
                "finding rationale",
                "UPDATE finding SET rationale='Changed rationale' "
                "WHERE id='finding:record-version';",
            ),
            (
                "finding assessment",
                "UPDATE finding SET assessment='FACTUALLY_FALSE' "
                "WHERE id='finding:record-version';",
            ),
            (
                "publication status",
                "UPDATE finding SET publication_status='PUBLISH' "
                "WHERE id='finding:record-version';",
            ),
            (
                "finding policy version",
                "UPDATE finding SET policy_version='finding-policy-v2' "
                "WHERE id='finding:record-version';",
            ),
            (
                "finding model bundle",
                "UPDATE finding SET model_bundle=jsonb_build_object('deterministic', false) "
                "WHERE id='finding:record-version';",
            ),
            (
                "verification input fingerprint",
                "UPDATE verification_run SET input_fingerprint=repeat('d',64) "
                "WHERE id='verification:record-version';",
            ),
            (
                "verification version",
                "UPDATE verification_run SET verification_version='deterministic-verification-v3' "
                "WHERE id='verification:record-version';",
            ),
            (
                "verification assessment",
                "UPDATE verification_run SET assessment='FACTUALLY_FALSE' "
                "WHERE id='verification:record-version';",
            ),
            (
                "verification evidence set",
                "UPDATE verification_run SET evidence_ids='[\"evidence:a\"]'::jsonb "
                "WHERE id='verification:record-version';",
            ),
            (
                "finding evidence relation",
                "UPDATE finding_evidence SET relation='CONTEXT' "
                "WHERE finding_id='finding:record-version' AND evidence_id='evidence:a';",
            ),
            (
                "assertion text without stored hash rewrite",
                "UPDATE finding_assertion SET assertion_text='Tampered assertion text' "
                "WHERE id='assertion:material';",
            ),
            (
                "assertion required relation",
                "UPDATE finding_assertion SET required_relation='CONTEXT' "
                "WHERE id='assertion:material';",
            ),
            (
                "assertion verification binding",
                "UPDATE finding_assertion SET metadata="
                "jsonb_build_object('verification_run_id','verification:changed') "
                "WHERE id='assertion:material';",
            ),
            (
                "citation relation",
                "UPDATE finding_assertion_citation SET relation='CONTEXT' "
                "WHERE id='citation:material';",
            ),
            (
                "citation verification binding",
                "UPDATE finding_assertion_citation SET metadata="
                "jsonb_build_object('verification_run_id','verification:changed') "
                "WHERE id='citation:material';",
            ),
            (
                "citation bound hashes",
                "UPDATE finding_assertion_citation "
                "SET passage_text_sha256=repeat('e',64), source_content_sha256=repeat('f',64) "
                "WHERE id='citation:material';",
            ),
            (
                "verification link removal",
                "UPDATE finding SET verification_run_id=NULL "
                "WHERE id='finding:record-version';",
            ),
        )
        for label, sql in mutations:
            with self.subTest(label=label):
                self._reset_and_seed()
                before = self._version().record_version
                self.store.run_literal(sql)
                after = self._version().record_version
                self.assertNotEqual(before, after)

    def test_reordering_set_like_verification_refs_does_not_change_version(self):
        before = self._version().record_version
        self.store.run_literal(
            """
            UPDATE verification_run
            SET evidence_ids='["evidence:a","evidence:b"]'::jsonb,
                observation_ids='["observation:a","observation:b"]'::jsonb
            WHERE id='verification:record-version';
            """
        )
        self.assertEqual(before, self._version().record_version)

    def test_source_and_policy_freshness_owned_by_dp308_do_not_duplicate_record_version(self):
        before = self._version().record_version
        self.store.run_literal(
            """
            UPDATE evidence
            SET content_sha256=repeat('f',64), rights_status='CLEARED'
            WHERE id='evidence:a';
            UPDATE atomic_claim
            SET metadata=jsonb_set(
                metadata,
                '{context_integrity,state}',
                '"REVIEW_REQUIRED"'::jsonb,
                true
            )
            WHERE id='claim:record-version';
            """
        )
        self.assertEqual(before, self._version().record_version)


if __name__ == "__main__":
    unittest.main()

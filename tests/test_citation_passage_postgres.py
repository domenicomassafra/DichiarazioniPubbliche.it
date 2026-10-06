import hashlib
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

from dichiarazioni_pubbliche.citation_assurance import assertion_text_sha256  # noqa: E402
from dichiarazioni_pubbliche.citation_passage_runtime import (  # noqa: E402
    PASSAGE_CITATION_BINDING_VERSION,
    deterministic_passage_citation_id,
    persist_unstructured_passage_citation,
)
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    PublicProjectionStore,
    build_public_projection,
)
from dichiarazioni_pubbliche.wording_contract import wording_contract_metadata  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class CitationPassagePostgresTests(unittest.TestCase):
    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    port: int
    runtime_database_url: str
    migration_database_url: str
    admin_url: str
    store: PublicProjectionStore
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
    def _psql(cls, database_url: str, sql: str) -> str:
        psql = shutil.which("psql") or "psql"
        return cls._run_command(
            [
                psql,
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
        psql = shutil.which("psql") or "psql"
        cls._run_command(
            [
                psql,
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
        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp224-postgres-")
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
            cls._psql(
                cls.admin_url,
                "CREATE DATABASE dp224_runtime; CREATE DATABASE dp224_migration;",
            )
            cls.runtime_database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp224_runtime"
            )
            cls.migration_database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp224_migration"
            )
            migration = (
                ROOT
                / "db"
                / "migrations"
                / "20261006-add-passage-citation-hash-binding.sql"
            )
            cls._seed_legacy_migration_database()
            cls._apply_file(cls.migration_database_url, migration)
            cls._apply_file(cls.migration_database_url, migration)
            cls.store = PublicProjectionStore(cls.runtime_database_url)
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
    def _seed_legacy_migration_database(cls) -> None:
        cls._psql(
            cls.migration_database_url,
            """
            CREATE TABLE finding_assertion (
                id text PRIMARY KEY,
                finding_id text NOT NULL,
                required_relation text NOT NULL
            );
            CREATE TABLE finding_evidence (
                finding_id text NOT NULL,
                evidence_id text NOT NULL
            );
            CREATE TABLE evidence (
                id text PRIMARY KEY,
                content_sha256 text
            );
            CREATE TABLE evidence_observation (
                id text PRIMARY KEY,
                evidence_id text NOT NULL
            );
            CREATE TABLE content_capture (
                id text PRIMARY KEY,
                content_id text NOT NULL,
                content_sha256 text NOT NULL
            );
            CREATE TABLE passage (
                id text PRIMARY KEY,
                content_id text NOT NULL,
                capture_id text,
                text_sha256 text NOT NULL,
                private_text text
            );
            CREATE TABLE finding_assertion_citation (
                id text PRIMARY KEY,
                assertion_id text NOT NULL,
                evidence_id text NOT NULL,
                observation_id text,
                passage_id text,
                relation text NOT NULL,
                citation_version text NOT NULL DEFAULT 'finding-citation-v1',
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb
            );
            """,
        )

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

    @classmethod
    def _recreate_runtime_database(cls) -> None:
        """Rebuild the whole runtime fixture instead of truncating protected ledgers."""

        cls._psql(
            cls.admin_url,
            "DROP DATABASE dp224_runtime; CREATE DATABASE dp224_runtime;",
        )
        cls._apply_file(cls.runtime_database_url, ROOT / "db" / "schema.v1.sql")
        cls._apply_file(
            cls.runtime_database_url,
            ROOT / "db" / "migrations" / "20261006-add-passage-citation-hash-binding.sql",
        )
        cls.store = PublicProjectionStore(cls.runtime_database_url)

    def setUp(self) -> None:
        self._recreate_runtime_database()
        self._seed_unstructured_dossier()

    def _seed_unstructured_dossier(self) -> None:
        normalized_claim = "Il provvedimento sintetico è in vigore."
        source_wording = "La persona sintetica afferma che il provvedimento è in vigore."
        evidence_text = "Il provvedimento sintetico entra in vigore il 1 settembre 2026."
        rationale = "The approved source states that the synthetic measure is in force."
        quote_sha256 = hashlib.sha256(source_wording.encode("utf-8")).hexdigest()
        passage_sha256 = hashlib.sha256(evidence_text.encode("utf-8")).hexdigest()
        source_sha256 = hashlib.sha256(
            ("official-record-v1\n" + evidence_text).encode("utf-8")
        ).hexdigest()
        wording = wording_contract_metadata(
            occurrence_id="statement:dp224-passage",
            source_text_sha256=quote_sha256,
            normalized_claim=normalized_claim,
            language="it",
            derivation_version="candidate-extraction-v1",
        )
        self.store.run(
            """
            INSERT INTO person (id, canonical_name)
            VALUES ('person:dp224', 'Persona sintetica DP-224');

            INSERT INTO content_item (
                id, canonical_url, title, language, published_at, processing_status
            ) VALUES
                (
                    'content:dp224-claim', 'https://example.test/dp224-claim',
                    'DP-224 synthetic claim', 'it',
                    '2026-09-21T10:00:00+00:00', 'PROCESSED'
                ),
                (
                    'content:dp224-evidence', 'https://example.test/dp224-evidence',
                    'DP-224 synthetic official record', 'it',
                    '2026-09-01T10:00:00+00:00', 'PROCESSED'
                );

            INSERT INTO content_capture (
                id, content_id, observed_at, final_url, media_type,
                content_sha256, retrieval_method, retrieval_version,
                rights_status, retention_class, status
            ) VALUES (
                'capture:dp224-evidence', 'content:dp224-evidence',
                '2026-09-22T09:00:00+00:00',
                'https://example.test/dp224-evidence', 'text/html',
                :'source_sha256', 'SYNTHETIC_FIXTURE', 'fixture-v1',
                'CLEARED', 'DURABLE_PROVENANCE', 'CAPTURED'
            );

            INSERT INTO passage (
                id, content_id, capture_id, selector_type, start_char, end_char,
                text_sha256, private_text, language, extraction_method,
                extraction_version
            ) VALUES (
                'passage:dp224-evidence', 'content:dp224-evidence',
                'capture:dp224-evidence', 'TEXT_POSITION', 0,
                char_length(:'evidence_text'), :'passage_sha256', :'evidence_text',
                'it', 'SYNTHETIC_FIXTURE', 'fixture-v1'
            );

            INSERT INTO atomic_claim (
                id, content_id, speaker_person_id, normalized_claim, claim_type,
                temporal_scope, check_worthy, extraction_version, metadata
            ) VALUES (
                'claim:dp224', 'content:dp224-claim', 'person:dp224',
                :'normalized_claim', 'LEGAL_POLICY_STATUS',
                '{"statement_date":"2026-09-21"}'::jsonb,
                true, 'candidate-extraction-v1',
                jsonb_build_object(
                    'speech_mode', 'DIRECT_UTTERANCE',
                    'context_integrity', jsonb_build_object(
                        'state', 'CLEAR_AUTOMATIC',
                        'quote_sha256', :'quote_sha256'
                    ),
                    'wording', :'wording'::jsonb
                )
            );

            INSERT INTO claim_text_provenance (
                id, claim_id, content_id, person_id, selector_type, quote_sha256,
                source_sha256, attribution_method, status, source_ref
            ) VALUES (
                'text-provenance:dp224', 'claim:dp224', 'content:dp224-claim',
                'person:dp224', 'TEXT_QUOTE_HASH', :'quote_sha256',
                repeat('c', 64), 'SOURCE_QUOTE', 'APPROVED',
                '{"url":"https://example.test/dp224-claim"}'::jsonb
            );

            INSERT INTO evidence (
                id, canonical_url, publisher, source_type, publication_date,
                observed_at, content_sha256, rights_status
            ) VALUES (
                'evidence:dp224', 'https://example.test/dp224-evidence',
                'Synthetic Official Record', 'PRIMARY_OFFICIAL', '2026-09-01',
                '2026-09-22T09:00:00+00:00', :'source_sha256', 'UNKNOWN'
            );

            INSERT INTO claim_evidence_candidate (
                claim_id, evidence_id, retrieval_method, retrieval_version,
                relation_candidate, status, statement_cutoff
            ) VALUES (
                'claim:dp224', 'evidence:dp224', 'SYNTHETIC_FIXTURE', 'fixture-v1',
                'SUPPORT', 'APPROVED', '2026-09-21'
            );

            INSERT INTO verification_run (
                id, claim_id, verification_kind, verification_version,
                input_fingerprint, statement_cutoff, assessment, evidence_ids,
                observation_ids, blockers, rationale_codes
            ) VALUES (
                'verification:dp224', 'claim:dp224', 'DOCUMENT_STATUS', 'fixture-v1',
                repeat('d', 64), '2026-09-21', 'SUPPORTED',
                '["evidence:dp224"]'::jsonb, '[]'::jsonb,
                '[]'::jsonb, '["SYNTHETIC_UNSTRUCTURED_SOURCE"]'::jsonb
            );

            INSERT INTO finding (
                id, claim_id, assessment, rationale, publication_status,
                policy_version, verification_run_id, created_at
            ) VALUES (
                'finding:dp224', 'claim:dp224', 'SUPPORTED', :'rationale', 'PUBLISH',
                'policy-v1', 'verification:dp224', '2026-09-22T10:00:00+00:00'
            );

            INSERT INTO finding_evidence (finding_id, evidence_id, relation)
            VALUES ('finding:dp224', 'evidence:dp224', 'VERIFICATION_INPUT');

            INSERT INTO finding_assertion (
                id, finding_id, assertion_text, assertion_text_sha256,
                assertion_type, material, required_relation
            ) VALUES (
                'assertion:dp224', 'finding:dp224', :'rationale', :'assertion_sha256',
                'RATIONALE_MATERIAL', true, 'SUPPORT'
            );

            INSERT INTO review_event (id, entity_type, entity_id, action, created_at)
            VALUES
                (
                    'review:provenance-dp224', 'CLAIM_TEXT_PROVENANCE',
                    'text-provenance:dp224', 'APPROVED', '2026-09-22T10:01:00+00:00'
                ),
                (
                    'review:evidence-dp224', 'CLAIM_EVIDENCE_CANDIDATE',
                    'claim:dp224|evidence:dp224|fixture-v1', 'APPROVED',
                    '2026-09-22T10:02:00+00:00'
                ),
                (
                    'review:finding-dp224', 'FINDING', 'finding:dp224', 'APPROVED',
                    '2026-09-22T10:05:00+00:00'
                );
            """,
            source_sha256=source_sha256,
            passage_sha256=passage_sha256,
            evidence_text=evidence_text,
            normalized_claim=normalized_claim,
            quote_sha256=quote_sha256,
            wording=json.dumps(wording, ensure_ascii=False, separators=(",", ":")),
            rationale=rationale,
            assertion_sha256=assertion_text_sha256(rationale),
        )
        self.passage_sha256 = passage_sha256
        self.source_sha256 = source_sha256
        self.evidence_text = evidence_text

    def _bind(self):
        return persist_unstructured_passage_citation(
            self.store,
            assertion_id="assertion:dp224",
            evidence_id="evidence:dp224",
            passage_id="passage:dp224-evidence",
            relation="SUPPORT",
            passage_text_sha256=self.passage_sha256,
            source_content_sha256=self.source_sha256,
        )

    def _projection(self) -> dict:
        return build_public_projection(
            self.store,
            generated_at="2026-09-22T12:00:00+00:00",
        )

    def test_migration_upgrades_v1_shape_and_replays(self):
        columns = set(
            filter(
                None,
                self._psql(
                    self.migration_database_url,
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='finding_assertion_citation'
                    ORDER BY column_name;
                    """,
                ).splitlines(),
            )
        )
        self.assertIn("passage_text_sha256", columns)
        self.assertIn("source_content_sha256", columns)
        function_count = self._psql(
            self.migration_database_url,
            """
            SELECT count(*)::text
            FROM pg_proc
            WHERE proname='finding_assertion_passage_binding_valid';
            """,
        )
        self.assertEqual(function_count, "1")

    def test_exact_binding_is_idempotent_and_projects_without_private_body(self):
        first = self._bind()
        second = self._bind()
        self.assertEqual(first, second)
        self.assertEqual(first.binding_version, PASSAGE_CITATION_BINDING_VERSION)
        self.assertEqual(
            first.citation_id,
            deterministic_passage_citation_id(
                assertion_id="assertion:dp224",
                evidence_id="evidence:dp224",
                passage_id="passage:dp224-evidence",
                relation="SUPPORT",
                passage_text_sha256=self.passage_sha256,
                source_content_sha256=self.source_sha256,
            ),
        )
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM finding_assertion_citation "
                "WHERE assertion_id='assertion:dp224';"
            ),
            "1",
        )
        self.assertEqual(
            self.store.run(
                "SELECT finding_assertion_passage_binding_valid(:'citation_id')::text;",
                citation_id=first.citation_id,
            ),
            "true",
        )
        projection = self._projection()
        self.assertEqual(projection["dossier_count"], 1)
        encoded = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn(self.evidence_text, encoded)
        self.assertNotIn("private_text", encoded)
        self.assertNotIn("passage:dp224-evidence", encoded)

    def test_passage_hash_tamper_fails_closed_at_projection(self):
        self._bind()
        self.store.run_literal(
            "UPDATE passage SET text_sha256=repeat('0',64) "
            "WHERE id='passage:dp224-evidence';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self.assertEqual(self._projection()["dossier_count"], 0)

    def test_private_passage_body_tamper_fails_closed_without_exposure(self):
        self._bind()
        self.store.run_literal(
            "UPDATE passage SET private_text='tampered private body' "
            "WHERE id='passage:dp224-evidence';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        projection = self._projection()
        self.assertEqual(projection["dossier_count"], 0)
        self.assertNotIn("tampered private body", json.dumps(projection))

    def test_source_hash_tamper_fails_closed_at_projection(self):
        self._bind()
        self.store.run_literal(
            "UPDATE content_capture SET content_sha256=repeat('0',64) "
            "WHERE id='capture:dp224-evidence';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self.assertEqual(self._projection()["dossier_count"], 0)

    def test_evidence_hash_tamper_fails_closed_at_projection(self):
        self._bind()
        self.store.run_literal(
            "UPDATE evidence SET content_sha256=repeat('0',64) "
            "WHERE id='evidence:dp224';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self.assertEqual(self._projection()["dossier_count"], 0)

    def test_structured_observation_cannot_use_unstructured_passage_bypass(self):
        self.store.run_literal(
            """
            INSERT INTO evidence_observation (
                id, evidence_id, observation_type, value_text,
                extraction_method, extraction_version, status
            ) VALUES (
                'observation:dp224-structured', 'evidence:dp224', 'TEXT_VALUE',
                'structured', 'SYNTHETIC_FIXTURE', 'fixture-v1', 'APPROVED'
            );
            """
        )
        with self.assertRaisesRegex(
            ValueError,
            "DP224_PASSAGE_CITATION_BINDING_NOT_ELIGIBLE",
        ):
            self._bind()
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM finding_assertion_citation "
                "WHERE assertion_id='assertion:dp224';"
            ),
            "0",
        )

    def test_wrong_source_hash_is_rejected_before_persistence(self):
        with self.assertRaisesRegex(
            ValueError,
            "DP224_PASSAGE_CITATION_BINDING_NOT_ELIGIBLE",
        ):
            persist_unstructured_passage_citation(
                self.store,
                assertion_id="assertion:dp224",
                evidence_id="evidence:dp224",
                passage_id="passage:dp224-evidence",
                relation="SUPPORT",
                passage_text_sha256=self.passage_sha256,
                source_content_sha256="0" * 64,
            )
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM finding_assertion_citation "
                "WHERE assertion_id='assertion:dp224';"
            ),
            "0",
        )


if __name__ == "__main__":
    unittest.main()

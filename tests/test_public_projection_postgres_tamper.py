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
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    PublicProjectionStore,
    ProductionPublicProjectionStore,
    build_public_projection,
)
from dichiarazioni_pubbliche.wording_contract import wording_contract_metadata  # noqa: E402


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class PublicProjectionPostgresTamperTests(unittest.TestCase):
    """DP-223 persisted-tamper acceptance against the real projection SQL path."""

    postgres_tmp: tempfile.TemporaryDirectory
    data_dir: Path
    port: int
    database_url: str
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
    def setUpClass(cls) -> None:
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest(
                "ephemeral PostgreSQL acceptance requires: " + ", ".join(missing)
            )

        cls.postgres_tmp = tempfile.TemporaryDirectory(prefix="dp223-postgres-")
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
                    "CREATE DATABASE dp223_tamper;",
                ]
            )
            cls.database_url = (
                f"postgresql://postgres@127.0.0.1:{cls.port}/dp223_tamper"
            )
            cls.store = PublicProjectionStore(cls.database_url)
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

    @classmethod
    def _recreate_fixture_database(cls) -> None:
        """Reset the global fixture by rebuilding the disposable database.

        The production schema contains append-only ledgers whose no-TRUNCATE guards
        are part of the contract. Recreating this dedicated test database keeps a
        whole-schema fixture isolated without depending on a list of protected tables.
        """

        psql = shutil.which("psql") or "psql"
        for statement in (
            "DROP DATABASE dp223_tamper;",
            "CREATE DATABASE dp223_tamper;",
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
        cls._run_command(
            [
                psql,
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                cls.database_url,
                "-f",
                str(ROOT / "db" / "schema.v1.sql"),
            ]
        )
        cls.store = PublicProjectionStore(cls.database_url)

    def setUp(self) -> None:
        self._recreate_fixture_database()
        self._seed_valid_dossier()

    def _seed_valid_dossier(self) -> None:
        normalized_claim = "Il valore sintetico è 10."
        source_wording = "La fonte sintetica dichiara che il valore osservato è 10."
        rationale = "Supported by the approved synthetic record."
        quote_sha256 = hashlib.sha256(source_wording.encode("utf-8")).hexdigest()
        wording = wording_contract_metadata(
            occurrence_id="statement:dp223-persisted",
            source_text_sha256=quote_sha256,
            normalized_claim=normalized_claim,
            language="it",
            derivation_version="candidate-extraction-v1",
        )
        self.store.run(
            """
            INSERT INTO person (id, canonical_name)
            VALUES
                ('person:dp223-a', 'Persona sintetica A'),
                ('person:dp223-b', 'Persona sintetica B');

            INSERT INTO content_item (
                id, canonical_url, title, language, published_at, processing_status
            ) VALUES (
                'content:dp223', 'https://example.test/dp223-source',
                'DP-223 synthetic source', 'it',
                '2026-09-21T10:00:00+00:00', 'PROCESSED'
            );

            INSERT INTO atomic_claim (
                id, content_id, speaker_person_id, normalized_claim, claim_type,
                temporal_scope, check_worthy, extraction_version, metadata
            ) VALUES (
                'claim:dp223', 'content:dp223', 'person:dp223-a', :'normalized_claim',
                'NUMERIC_STATISTIC',
                '{"statement_date":"2026-09-21","valid_from":null,"valid_until":null}'::jsonb,
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
                'text-provenance:dp223', 'claim:dp223', 'content:dp223',
                'person:dp223-a', 'TEXT_QUOTE_HASH', :'quote_sha256',
                repeat('c', 64), 'SOURCE_QUOTE', 'APPROVED',
                '{"url":"https://example.test/dp223-source"}'::jsonb
            );

            INSERT INTO evidence (
                id, canonical_url, publisher, source_type, publication_date,
                observed_at, content_sha256, reference_period, rights_status
            ) VALUES (
                'evidence:dp223', 'https://example.test/dp223-evidence',
                'Synthetic Authority', 'PRIMARY_OFFICIAL', '2026-09-01',
                '2026-09-22T10:00:00+00:00', repeat('a', 64), '2026', 'UNKNOWN'
            );

            INSERT INTO claim_evidence_candidate (
                claim_id, evidence_id, retrieval_method, retrieval_version,
                relation_candidate, status, statement_cutoff
            ) VALUES (
                'claim:dp223', 'evidence:dp223', 'SYNTHETIC_FIXTURE', 'fixture-v1',
                'SUPPORT', 'APPROVED', '2026-09-21'
            );

            INSERT INTO evidence_observation (
                id, evidence_id, observation_type, value_text, extraction_method,
                extraction_version, status
            ) VALUES (
                'observation:dp223', 'evidence:dp223', 'TEXT_VALUE', '10',
                'SYNTHETIC_FIXTURE', 'fixture-v1', 'APPROVED'
            );

            INSERT INTO verification_run (
                id, claim_id, verification_kind, verification_version,
                input_fingerprint, statement_cutoff, assessment, evidence_ids,
                observation_ids, blockers, rationale_codes
            ) VALUES (
                'verification:dp223', 'claim:dp223', 'DETERMINISTIC', 'fixture-v1',
                repeat('d', 64), '2026-09-21', 'SUPPORTED',
                '["evidence:dp223"]'::jsonb, '["observation:dp223"]'::jsonb,
                '[]'::jsonb, '["SYNTHETIC_ACCEPTANCE"]'::jsonb
            );

            INSERT INTO finding (
                id, claim_id, assessment, rationale, publication_status,
                policy_version, verification_run_id, created_at
            ) VALUES (
                'finding:dp223', 'claim:dp223', 'SUPPORTED', :'rationale', 'PUBLISH',
                'policy-v1', 'verification:dp223', '2026-09-22T10:00:00+00:00'
            );

            INSERT INTO finding_evidence (finding_id, evidence_id, relation)
            VALUES ('finding:dp223', 'evidence:dp223', 'VERIFICATION_INPUT');

            INSERT INTO finding_assertion (
                id, finding_id, assertion_text, assertion_text_sha256,
                assertion_type, material, required_relation
            ) VALUES (
                'assertion:dp223', 'finding:dp223', :'rationale', :'assertion_sha256',
                'RATIONALE_MATERIAL', true, 'SUPPORT'
            );

            INSERT INTO finding_assertion_citation (
                id, assertion_id, evidence_id, observation_id, relation
            ) VALUES (
                'citation:dp223', 'assertion:dp223', 'evidence:dp223',
                'observation:dp223', 'SUPPORT'
            );

            INSERT INTO review_event (id, entity_type, entity_id, action, created_at)
            VALUES
                (
                    'review:provenance-dp223', 'CLAIM_TEXT_PROVENANCE',
                    'text-provenance:dp223', 'APPROVED', '2026-09-22T10:01:00+00:00'
                ),
                (
                    'review:evidence-dp223', 'CLAIM_EVIDENCE_CANDIDATE',
                    'claim:dp223|evidence:dp223|fixture-v1', 'APPROVED',
                    '2026-09-22T10:02:00+00:00'
                ),
                (
                    'review:observation-dp223', 'EVIDENCE_OBSERVATION',
                    'observation:dp223', 'APPROVED', '2026-09-22T10:03:00+00:00'
                ),
                (
                    'review:finding-dp223', 'FINDING', 'finding:dp223', 'APPROVED',
                    '2026-09-22T10:05:00+00:00'
                );
            """,
            normalized_claim=normalized_claim,
            quote_sha256=quote_sha256,
            wording=json.dumps(wording, ensure_ascii=False, separators=(",", ":")),
            rationale=rationale,
            assertion_sha256=assertion_text_sha256(rationale),
        )

    def _projection(self) -> dict:
        return build_public_projection(
            self.store,
            generated_at="2026-09-22T12:00:00+00:00",
        )

    def _assert_not_public(self) -> None:
        projection = self._projection()
        self.assertEqual(projection["dossier_count"], 0)
        self.assertEqual(projection["dossiers"], [])

    def test_valid_persisted_dossier_projects_before_tamper(self):
        rows = self.store.projectable_findings()
        self.assertEqual(len(rows), 1)
        projection = self._projection()
        self.assertEqual(projection["dossier_count"], 1)
        self.assertEqual(projection["omitted_count"], 0)
        self.assertEqual(projection["dossiers"][0]["finding_id"], "finding:dp223")
        self.assertEqual(
            projection["dossiers"][0]["speaker"]["id"], "person:dp223-a"
        )

    def test_production_projection_omits_legacy_candidate_without_current_private_gates(self):
        production = ProductionPublicProjectionStore(self.database_url)
        self.assertEqual(len(production.projectable_findings()), 1)
        projection = build_public_projection(
            production,
            generated_at="2026-09-22T12:00:00+00:00",
        )
        self.assertEqual(projection["dossier_count"], 0)
        self.assertEqual(projection["omitted_count"], 1)

    def test_direct_status_tamper_is_omitted_by_persisted_query(self):
        self.store.run_literal(
            "UPDATE finding SET publication_status = 'POLICY_HOLD' "
            "WHERE id = 'finding:dp223';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self._assert_not_public()

    def test_direct_person_tamper_breaks_persisted_provenance_binding(self):
        self.store.run_literal(
            "UPDATE atomic_claim SET speaker_person_id = 'person:dp223-b' "
            "WHERE id = 'claim:dp223';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self._assert_not_public()

    def test_direct_quote_hash_tamper_is_omitted_by_public_projection(self):
        self.store.run_literal(
            """
            UPDATE atomic_claim
            SET metadata = jsonb_set(
                metadata,
                '{context_integrity,quote_sha256}',
                to_jsonb(repeat('0', 64)),
                false
            )
            WHERE id = 'claim:dp223';
            """
        )
        self.assertEqual(len(self.store.projectable_findings()), 1)
        projection = self._projection()
        self.assertEqual(projection["dossier_count"], 0)
        self.assertEqual(projection["omitted_count"], 1)

    def test_reported_speech_mode_tamper_is_not_publicly_attributed(self):
        self.store.run_literal(
            """
            UPDATE atomic_claim
            SET metadata = jsonb_set(
                metadata,
                '{speech_mode}',
                '"REPORTED_SPEECH"'::jsonb,
                true
            )
            WHERE id = 'claim:dp223';
            """
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self._assert_not_public()

    def test_context_review_state_tamper_is_omitted_from_projection(self):
        self.store.run_literal(
            """
            UPDATE atomic_claim
            SET metadata = jsonb_set(
                metadata,
                '{context_integrity,state}',
                '"NEEDS_CONTEXT_REVIEW"'::jsonb,
                false
            )
            WHERE id = 'claim:dp223';
            """
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self._assert_not_public()

    def test_direct_provenance_tamper_is_omitted_by_persisted_query(self):
        self.store.run_literal(
            "UPDATE claim_text_provenance SET status = 'REJECTED' "
            "WHERE id = 'text-provenance:dp223';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self._assert_not_public()

    def test_direct_material_assertion_citation_tamper_is_omitted(self):
        self.store.run_literal(
            "UPDATE finding_assertion_citation SET relation = 'CONTEXT' "
            "WHERE id = 'citation:dp223';"
        )
        self.assertEqual(self.store.projectable_findings(), [])
        self._assert_not_public()

    def test_public_attribution_gate_rejects_person_link_tamper_without_identity_review(self):
        source_wording = "La fonte sintetica dichiara che il valore osservato è 10."
        source_hash = hashlib.sha256(source_wording.encode("utf-8")).hexdigest()
        mention = "Persona sintetica A"
        mention_hash = hashlib.sha256(mention.encode("utf-8")).hexdigest()
        self.store.run(
            """
            UPDATE atomic_claim
            SET metadata = jsonb_set(
                jsonb_set(
                    metadata,
                    '{context_integrity,quote_start}',
                    '0'::jsonb,
                    true
                ),
                '{context_integrity,quote_end}',
                to_jsonb(:'quote_end'::integer),
                true
            )
            WHERE id = 'claim:dp223';

            INSERT INTO transcript_variant (
                id, content_id, provider_id, source_kind, language,
                raw_text_sha256, raw_text, is_manual_caption
            ) VALUES (
                'transcript:dp222', 'content:dp223', 'official-fixture',
                'OFFICIAL_TRANSCRIPT', 'it', :'source_hash', :'source_wording', true
            );
            INSERT INTO transcript_segment (
                id, variant_id, segment_index, start_ms, end_ms, text
            ) VALUES (
                'transcript-segment:dp222', 'transcript:dp222', 0, 0, 1000,
                :'source_wording'
            );
            INSERT INTO canonical_transcript_segment (
                id, content_id, segment_index, start_ms, end_ms,
                speaker_person_id, canonical_text, transcript_status,
                publication_blocked, created_at, updated_at
            ) VALUES (
                'segment:dp222', 'content:dp223', 0, 0, 1000,
                'person:dp223-a', :'source_wording', 'RESOLVED', false,
                '2026-09-22T10:00:00+00:00', '2026-09-22T10:00:00+00:00'
            );
            INSERT INTO canonical_segment_candidate (
                canonical_segment_id, transcript_segment_id
            ) VALUES ('segment:dp222', 'transcript-segment:dp222');
            INSERT INTO claim_segment (claim_id, segment_id)
            VALUES ('claim:dp223', 'segment:dp222');

            DELETE FROM review_event
            WHERE entity_type = 'CLAIM_TEXT_PROVENANCE'
              AND entity_id = 'text-provenance:dp223';
            DELETE FROM claim_text_provenance
            WHERE id = 'text-provenance:dp223';

            INSERT INTO speaker_identity_candidate (
                id, content_id, person_id, start_ms, end_ms,
                attribution_method, attribution_version, source_ref,
                confidence, status
            ) VALUES (
                'speaker-candidate:dp222-a', 'content:dp223', 'person:dp223-a',
                0, 1000, 'MANUAL_REVIEW', 'speaker-attribution-v1',
                '{"private_alias":"speaker-a"}'::jsonb, 0.9900, 'APPROVED'
            );
            INSERT INTO entity_identifier (
                id, entity_type, person_id, identifier_kind, identifier_value,
                authority, identifier_version, source_ref, status
            ) VALUES (
                'identifier:dp222-a', 'PERSON', 'person:dp223-a',
                'OFFICIAL_PERSON_ID', 'PRIVATE-ID-A', 'OFFICIAL_REGISTER',
                'entity-identifier-v1', '{"private":"identifier-source"}'::jsonb,
                'ACTIVE'
            );
            INSERT INTO entity_resolution_candidate (
                id, content_id, mention_text, mention_text_sha256, entity_type,
                target_person_id, resolution_method, resolution_version,
                supporting_features, contradicting_features, retrieval_score, status
            ) VALUES (
                'resolution:dp222-a', 'content:dp223', :'mention', :'mention_hash',
                'PERSON', 'person:dp223-a', 'MANUAL_REVIEW', 'entity-resolution-v1',
                '[{"code":"IDENTIFIER_ID","value":"identifier:dp222-a"},'
                ' {"code":"KNOWN_ALIAS","value":"PRIVATE_ALIAS_A"}]'::jsonb,
                '[]'::jsonb, 0.987654, 'APPROVED'
            );
            INSERT INTO organization (id, canonical_name)
            VALUES ('org:dp222', 'Organizzazione sintetica');
            INSERT INTO person_role_interval (
                id, person_id, organization_id, role, start_date, end_date,
                is_public_role, source_ref, status
            ) VALUES (
                'role:dp222-a', 'person:dp223-a', 'org:dp222', 'Deputato',
                '2026-01-01', NULL, true,
                '{"private":"role-source"}'::jsonb, 'ACTIVE'
            );
            INSERT INTO review_event (id, entity_type, entity_id, action, created_at)
            VALUES
                (
                    'review:speaker-dp222-a', 'SPEAKER_IDENTITY_CANDIDATE',
                    'speaker-candidate:dp222-a', 'APPROVED',
                    '2026-09-22T10:01:00+00:00'
                ),
                (
                    'review:resolution-dp222-a', 'ENTITY_RESOLUTION_CANDIDATE',
                    'resolution:dp222-a', 'APPROVED', '2026-09-22T10:02:00+00:00'
                ),
                (
                    'review:role-dp222-a', 'PERSON_ROLE_INTERVAL',
                    'role:dp222-a', 'APPROVED', '2026-09-22T10:03:00+00:00'
                );
            """,
            quote_end=len(source_wording),
            source_hash=source_hash,
            source_wording=source_wording,
            mention=mention,
            mention_hash=mention_hash,
        )

        rows = self.store.projectable_findings()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["public_attribution_input"]["resolution_candidates"][0][
                "retrieval_score"
            ],
            0.987654,
        )
        projection = self._projection()
        self.assertEqual(projection["dossier_count"], 1)
        dossier = projection["dossiers"][0]
        self.assertEqual(dossier["speaker"]["id"], "person:dp223-a")
        self.assertEqual(dossier["speaker"]["public_role"], "Deputato")
        encoded = json.dumps(projection, ensure_ascii=False)
        for forbidden in (
            "PRIVATE_ALIAS_A",
            "PRIVATE-ID-A",
            "identifier-source",
            "role-source",
            "retrieval_score",
            "supporting_features",
            "contradicting_features",
        ):
            self.assertNotIn(forbidden, encoded)

        self.store.run(
            """
            UPDATE atomic_claim
            SET speaker_person_id = 'person:dp223-b'
            WHERE id = 'claim:dp223';
            UPDATE canonical_transcript_segment
            SET speaker_person_id = 'person:dp223-b'
            WHERE id = 'segment:dp222';
            INSERT INTO speaker_identity_candidate (
                id, content_id, person_id, start_ms, end_ms,
                attribution_method, attribution_version, source_ref, status
            ) VALUES (
                'speaker-candidate:dp222-b', 'content:dp223', 'person:dp223-b',
                0, 1000, 'MANUAL_REVIEW', 'speaker-attribution-v1',
                '{"tampered":true}'::jsonb, 'APPROVED'
            );
            INSERT INTO review_event (id, entity_type, entity_id, action, created_at)
            VALUES (
                'review:speaker-dp222-b', 'SPEAKER_IDENTITY_CANDIDATE',
                'speaker-candidate:dp222-b', 'APPROVED',
                '2026-09-22T10:04:00+00:00'
            );
            INSERT INTO entity_resolution_candidate (
                id, content_id, mention_text, mention_text_sha256, entity_type,
                target_person_id, resolution_method, resolution_version,
                supporting_features, contradicting_features, status
            ) VALUES (
                'resolution:dp222-b', 'content:dp223', :'mention', :'mention_hash',
                'PERSON', 'person:dp223-b', 'MANUAL_REVIEW', 'entity-resolution-v1',
                '[]'::jsonb, '[]'::jsonb, 'APPROVED'
            );
            """,
            mention=mention,
            mention_hash=mention_hash,
        )
        tampered_rows = self.store.projectable_findings()
        self.assertEqual(len(tampered_rows), 1)
        self.assertEqual(
            tampered_rows[0]["public_attribution_input"]["resolution_candidates"],
            [],
        )
        tampered_projection = self._projection()
        self.assertEqual(tampered_projection["dossier_count"], 0)
        self.assertEqual(tampered_projection["omitted_count"], 1)


if __name__ == "__main__":
    unittest.main()

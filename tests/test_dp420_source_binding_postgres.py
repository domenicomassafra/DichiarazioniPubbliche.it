"""DP-420: exact source and coverage bindings on disposable PostgreSQL."""

import unittest

from dichiarazioni_pubbliche.studio_readonly_db import StudioReadOnlyDb
from dichiarazioni_pubbliche.studio_usability_acceptance import read_verified_task_bindings


class StudioUsabilityBindingPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_dp417_queue_family_next import PersistedCaptureQueueTests

        cls.pg = PersistedCaptureQueueTests
        cls.pg.setUpClass()
        try:
            cls.pg.store.run("""
                INSERT INTO research_collection
                    (id, slug, name, scope_text, policy_version, status)
                VALUES ('research:garlasco', 'garlasco', 'Garlasco', 'PRIVATE', 'v1', 'ACTIVE');
                INSERT INTO coverage_need
                    (id, collection_id, need_type, requirement_kind,
                     requirement_fingerprint, question)
                VALUES ('coverage-need:real', 'research:garlasco',
                        'PRIMARY_SOURCE', 'ROLE_ANY', repeat('f',64), 'Missing source');
                INSERT INTO source (id, canonical_name, source_type)
                VALUES ('source:camera', 'Camera fixture', 'NEWS');
                INSERT INTO content_item (id, source_id, canonical_url)
                VALUES ('content:camera', 'source:camera', 'https://fixture.invalid/camera'),
                       ('content:historic', 'source:camera', 'https://fixture.invalid/historic');
                INSERT INTO research_collection_content
                    (collection_id, content_id, inclusion_method, inclusion_version)
                VALUES ('research:garlasco', 'content:camera', 'FIXTURE', 'v1'),
                       ('research:garlasco', 'content:historic', 'FIXTURE', 'v1');
                INSERT INTO person (id, canonical_name)
                VALUES ('person:roberta-bruzzone', 'Fixture speaker'),
                       ('person:unrelated', 'Unrelated fixture speaker');
                INSERT INTO atomic_claim
                    (id, content_id, speaker_person_id, normalized_claim, claim_type)
                VALUES ('claim:garlasco:bruzzone:2025-03-13:dna-y-13-loci',
                        'content:historic', 'person:roberta-bruzzone',
                        'Synthetic claim fixture', 'HISTORICAL_CLAIM'),
                       ('claim:unrelated', 'content:camera', 'person:unrelated',
                        'Wrong original claim fixture', 'HISTORICAL_CLAIM');
                INSERT INTO content_capture
                    (id, content_id, observed_at, final_url, content_sha256,
                     retrieval_method, retrieval_version)
                VALUES ('capture:camera', 'content:camera', '2026-10-25T10:00:00Z',
                        'https://fixture.invalid/camera', repeat('a',64), 'FIXTURE', 'v1'),
                       ('capture:historic', 'content:historic', '2026-10-25T10:00:00Z',
                        'https://fixture.invalid/historic', repeat('d',64), 'FIXTURE', 'v1');
                INSERT INTO passage
                    (id, content_id, capture_id, selector_type, start_char, end_char,
                     text_sha256, private_text, extraction_method, extraction_version)
                VALUES ('passage:camera', 'content:camera', 'capture:camera',
                        'TEXT_POSITION', 0, 12, repeat('b',64), 'Synthetic excerpt',
                        'FIXTURE', 'v1'),
                       ('passage:historic', 'content:historic', 'capture:historic',
                        'TEXT_POSITION', 0, 12, repeat('e',64), 'Synthetic quote',
                        'FIXTURE', 'v1');
                INSERT INTO private_source_rights_record
                    (id, subject_fingerprint, source_family, locator_kind, locator_value,
                     content_id, rights_status, rights_receipt_ref, permitted_uses,
                     reviewed_at, reviewer_ref, policy_version)
                VALUES ('private-rights:camera', repeat('c',64), 'FIXTURE', 'URL',
                        'https://fixture.invalid/camera', 'content:camera', 'CLEARED',
                        'fixture:receipt', ARRAY['FETCH','STORE_BODY','RESEARCH_CAPTURE_PRIVATE'],
                        '2026-10-25T00:00:00Z', 'fixture:reviewer', 'v1'),
                       ('private-rights:historic', repeat('9',64), 'FIXTURE', 'URL',
                        'https://fixture.invalid/historic', 'content:historic', 'CLEARED',
                        'fixture:receipt', ARRAY['FETCH','STORE_BODY','RESEARCH_CAPTURE_PRIVATE'],
                        '2026-10-25T00:00:00Z', 'fixture:reviewer', 'v1');
            """)
        except BaseException:
            cls.pg.tearDownClass()
            raise
        cls.reader = StudioReadOnlyDb(database_url=cls.pg.url)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pg"):
            cls.pg.tearDownClass()

    def test_coverage_need_cannot_validate_unrelated_source_capture(self):
        records = {"source-capture": {
            "status": "PASS", "source_id": "source:invented",
            "capture_id": "capture:invented", "rights_record_id": "private-rights:invented",
            "coverage_need_id": "coverage-need:real",
        }}
        self.assertEqual(read_verified_task_bindings(self.reader, records), set())

    def test_coverage_gap_still_accepts_its_exact_collection_need(self):
        records = {"coverage-gap": {
            "status": "PASS", "coverage_need_id": "coverage-need:real",
        }}
        self.assertEqual(read_verified_task_bindings(self.reader, records), {"coverage-gap"})

    def test_search_result_cannot_borrow_an_unrelated_source_with_valid_rights(self):
        records = {"find-dna": {
            "status": "PASS", "source_id": "source:camera",
            "capture_id": "capture:camera", "passage_id": "passage:camera",
            "rights_record_id": "private-rights:camera",
        }}
        self.assertEqual(read_verified_task_bindings(self.reader, records), set())

    def test_unknown_task_cannot_verify_a_real_capture(self):
        records = {"invented-task": {
            "status": "PASS", "source_id": "source:camera",
            "capture_id": "capture:camera", "passage_id": "passage:camera",
            "rights_record_id": "private-rights:camera",
        }}
        with self.assertRaisesRegex(ValueError, "DP420_OBSERVATIONS_INVALID"):
            read_verified_task_bindings(self.reader, records)

    def test_non_search_source_task_can_use_same_rights_cleared_capture(self):
        records = {"source-capture": {
            "status": "PASS", "source_id": "source:camera",
            "capture_id": "capture:camera", "rights_record_id": "private-rights:camera",
        }}
        self.assertEqual(read_verified_task_bindings(self.reader, records), {"source-capture"})

    def test_search_result_accepts_current_capture_on_its_own_content(self):
        records = {"find-dna": {
            "status": "PASS", "source_id": "source:camera",
            "capture_id": "capture:historic", "passage_id": "passage:historic",
            "rights_record_id": "private-rights:historic",
            "expected_result_ids": ["claim:invented"],
        }}
        self.assertEqual(read_verified_task_bindings(self.reader, records), {"find-dna"})

    def test_person_search_requires_speaker_claim_on_the_captured_content(self):
        record = {
            "status": "PASS", "source_id": "source:camera",
            "capture_id": "capture:camera", "passage_id": "passage:camera",
            "rights_record_id": "private-rights:camera",
        }
        self.assertEqual(read_verified_task_bindings(self.reader, {"find-bruzzone": record}), set())
        record.update(capture_id="capture:historic", passage_id="passage:historic",
                      rights_record_id="private-rights:historic")
        self.assertEqual(read_verified_task_bindings(self.reader, {"find-bruzzone": record}),
                         {"find-bruzzone"})


if __name__ == "__main__":
    unittest.main()

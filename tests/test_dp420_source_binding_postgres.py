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


if __name__ == "__main__":
    unittest.main()

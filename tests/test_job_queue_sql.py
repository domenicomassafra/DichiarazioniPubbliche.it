import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class JobQueueSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "db" / "job_queue.v1.sql").read_text()

    def test_queue_supports_lease_recovery(self):
        self.assertIn("renew_processing_job_lease", self.sql)
        self.assertIn("reap_expired_processing_jobs", self.sql)
        self.assertIn("LEASE_EXPIRED", self.sql)

    def test_queue_can_defer_without_retry_and_block_external_dependencies(self):
        self.assertIn("defer_processing_job", self.sql)
        self.assertIn("block_processing_job", self.sql)
        self.assertIn("unblock_processing_job", self.sql)

if __name__ == "__main__":
    unittest.main()

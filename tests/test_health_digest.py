import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.health_digest import (  # noqa: E402
    build_health_digest,
    error_category,
    write_private_json,
)


class FakeDb:
    def run(self, sql):
        if "FROM processing_job" in sql and "GROUP BY job_type" in sql:
            return '[{"job_type":"CLAIM_EXTRACT","state":"BLOCKED","count":2}]'
        if "'oldest_queued_seconds'" in sql:
            return '{"queued":0,"oldest_queued_seconds":0}'
        if "state IN ('BLOCKED', 'DEAD_LETTER')" in sql:
            return (
                '[{"last_error":"OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED: detail",'
                '"count":2}]'
            )
        if "FROM source_health" in sql:
            return (
                '[{"source_id":"s","status":"HEALTHY","consecutive_failures":0,'
                '"checked_at":"2026-09-22","last_success_at":"2026-09-22"}]'
            )
        if "FROM content_item" in sql and "GROUP BY processing_status" in sql:
            return '[{"processing_status":"CLAIM_EXTRACTION_BLOCKED","count":2}]'
        if "FROM provider_receipt" in sql:
            return (
                '[{"provider_id":"youtube","operation":"CAPTION_PROBE",'
                '"status":"SUCCESS","count":2,"cost_usd":0}]'
            )
        if "'variants'" in sql:
            return (
                '{"variants":2,"raw_segments":10,"canonical_segments":10,'
                '"publication_blocked_segments":3}'
            )
        if "'atomic_claims'" in sql:
            return (
                '{"atomic_claims":4,"check_worthy_claims":3,'
                '"claim_types":{"CURRENT_POLICY":2,"VALUE_JUDGMENT":2}}'
            )
        if "'evidence_records'" in sql:
            return (
                '{"evidence_records":5,"claim_candidates":7,'
                '"approved_candidates":2,'
                '"candidate_statuses":{"APPROVED":2,"RETRIEVED":5},'
                '"source_types":{"PRIMARY_OFFICIAL":5}}'
            )
        if "'evidence_observations'" in sql:
            return (
                '{"evidence_observations":3,'
                '"observation_statuses":{"APPROVED":2,"CANDIDATE":1},'
                '"verification_runs":2,'
                '"verification_assessments":{"SUPPORTED":1,"UNRESOLVED":1},'
                '"findings":2,'
                '"finding_publication_statuses":{"POLICY_HOLD":1,"UNRESOLVED":1},'
                '"relation_candidates":1,'
                '"relation_candidate_statuses":{"CANDIDATE":1},'
                '"reanalysis_triggers":1,'
                '"reanalysis_statuses":{"ENQUEUED":1},'
                '"review_events":2,'
                '"review_actions":{"APPROVED":2}}'
            )
        if "'public_people'" in sql:
            return (
                '{"public_people":2,"speaker_candidates":3,'
                '"speaker_candidate_statuses":{"APPROVED":2,"CANDIDATE":1},'
                '"speaker_assigned_segments":8,"speaker_assigned_claims":3}'
            )
        raise AssertionError(sql)


class HealthDigestTests(unittest.TestCase):
    def test_error_category_never_emits_raw_detail(self):
        self.assertEqual(
            error_category("OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED: private detail"),
            "OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED",
        )
        self.assertEqual(error_category("some arbitrary text"), "OTHER")

    def test_digest_is_aggregate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            digest = build_health_digest(
                FakeDb(),
                private_root=Path(tmp),
                now=datetime(2026, 9, 22, tzinfo=timezone.utc),
            )
        self.assertEqual(digest["estimated_cost_usd_today"], 0.0)
        self.assertEqual(
            digest["blockers"][0]["category"],
            "OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED",
        )
        self.assertFalse(digest["privacy"]["contains_transcript_text"])
        self.assertEqual(digest["claims"]["atomic_claims"], 4)
        self.assertEqual(digest["evidence"]["claim_candidates"], 7)
        self.assertEqual(digest["verification"]["verification_runs"], 2)
        self.assertEqual(
            digest["verification"]["finding_publication_statuses"]["POLICY_HOLD"],
            1,
        )
        self.assertEqual(digest["verification"]["review_events"], 2)
        self.assertEqual(digest["identity"]["speaker_assigned_claims"], 3)

    def test_health_file_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "health.json"
            write_private_json(path, {"ok": True})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()

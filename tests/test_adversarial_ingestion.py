import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.evidence_runtime import deterministic_evidence_id  # noqa: E402
from dichiarazioni_pubbliche.scheduler import provisional_content_key  # noqa: E402
from dichiarazioni_pubbliche.source_watcher import DiscoveredContent  # noqa: E402
from dichiarazioni_pubbliche.verification_runtime import (  # noqa: E402
    VerificationAssessment,
    VerificationEvidence,
    VerificationRequest,
    verify,
)


FIXTURE = ROOT / "tests" / "fixtures" / "adversarial-ingestion-v1.json"
REQUIRED_CLASSES = {
    "duplicate",
    "near_duplicate",
    "conflicting_sources",
    "changed_page",
    "deleted_page",
    "missing_timestamp",
    "speaker_ambiguity",
    "clip_transcript_mismatch",
    "out_of_order_correction",
    "partial_fetch",
    "replayed_job",
}


def content(external_id: str, title: str, published_at: str) -> DiscoveredContent:
    return DiscoveredContent(
        source_id="source:test",
        platform="youtube",
        external_id=external_id,
        title=title,
        canonical_url=f"https://example.test/{external_id}",
        published_at=published_at,
    )


class AdversarialIngestionFixtureTests(unittest.TestCase):
    def test_fixture_covers_every_required_adversarial_class(self):
        payload = json.loads(FIXTURE.read_text())
        classes = {row["class"] for row in payload["cases"]}
        self.assertEqual(classes, REQUIRED_CLASSES)

    def test_duplicate_and_near_duplicate_keys_are_deterministic(self):
        exact = content("a", "Weekly Update #1", "2026-09-22T10:00:00+00:00")
        replay = content("a", "Weekly Update #1", "2026-09-22T10:00:00+00:00")
        near = content("b", "Weekly Update — #1", "2026-09-22T11:00:00+00:00")
        self.assertEqual(
            provisional_content_key(exact),
            provisional_content_key(replay),
        )
        self.assertEqual(
            provisional_content_key(exact),
            provisional_content_key(near),
        )

    def test_missing_timestamp_prefers_under_dedup_to_false_merge(self):
        first = content("a", "Weekly Update", "")
        second = content("b", "Weekly Update", "")
        self.assertNotEqual(
            provisional_content_key(first),
            provisional_content_key(second),
        )

    def test_changed_page_versions_evidence_without_overwriting_prior_hash(self):
        first = deterministic_evidence_id(
            "source:test", "https://example.test/data", "a" * 64
        )
        changed = deterministic_evidence_id(
            "source:test", "https://example.test/data", "b" * 64
        )
        self.assertNotEqual(first, changed)

    def test_conflicting_authoritative_sources_fail_closed(self):
        request = VerificationRequest(
            "claim:a",
            "2026-09-22",
            "numeric_exact",
            {"metric": "x", "value": 10},
            source_intelligence_status="SUFFICIENT_FOR_RULE",
            source_intelligence_assessment_id="assessment:conflict",
        )
        rows = [
            VerificationEvidence(
                evidence_id="e:a",
                publication_date="2026-09-21",
                metric="x",
                value_numeric=10,
                suitable=True,
                authoritative=True,
            ),
            VerificationEvidence(
                evidence_id="e:b",
                publication_date="2026-09-21",
                metric="x",
                value_numeric=11,
                suitable=True,
                authoritative=True,
            ),
        ]
        self.assertEqual(
            verify(request, rows).assessment,
            VerificationAssessment.UNRESOLVED,
        )


if __name__ == "__main__":
    unittest.main()

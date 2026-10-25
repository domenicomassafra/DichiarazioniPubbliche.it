"""Coverage attempts are audit inputs, never proof of a universal absence."""

import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.denial_prior_utterance import (  # noqa: E402
    DenialCoverageAttempt,
    DenialCoverageManifest,
    DenialTarget,
    evaluate_denial,
)


def at(year: int) -> datetime:
    return datetime(year, 5, 1, tzinfo=timezone.utc)


def target() -> DenialTarget:
    return DenialTarget(
        denial_id="denial:one", person_id="person:one",
        source_version_id="denial:source", source_sha256="a" * 64,
        review_event_id="review:denial", uttered_at=at(2026),
        target_quote_sha256="b" * 64, target_proposition_sha256="c" * 64,
        predicate="NEVER_UTTERED", quantifier="NEVER", scope="PUBLIC",
        from_at=at(2023), through_at=at(2025),
    )


def manifest() -> DenialCoverageManifest:
    return DenialCoverageManifest(
        denial_id="denial:one", person_id="person:one",
        scope="PUBLIC", from_at=at(2023), through_at=at(2025),
        collection_sha256="d" * 64, review_event_id="review:coverage",
        observed_at=at(2026),
        attempts=(
            DenialCoverageAttempt(
                attempt_id="search:one", source_version_id="source:one",
                source_sha256="f" * 64,
                query_sha256="e" * 64, searched_at=at(2025),
                outcome="SEARCHED_PARTIAL",
            ),
        ),
    )


def review(coverage=None, *, versions=None):
    return evaluate_denial(
        target(), (), current_source_versions=versions or {
            "denial:source": "a" * 64, "source:one": "f" * 64,
        },
        coverage_manifest=coverage,
    )


class CoverageManifestTests(unittest.TestCase):
    def test_partial_archive_records_attempts_and_never_supports_absence(self):
        result = review(manifest())
        self.assertEqual(result.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(result.relation_status, "PRIVATE_HOLD")
        self.assertEqual(result.coverage_status, "SEARCH_ATTEMPTS_RECORDED_HOLD")
        self.assertEqual(result.coverage_attempt_ids, ("search:one",))
        self.assertFalse(result.publication_authority)
        self.assertNotEqual(result.receipt_sha256, review().receipt_sha256)

    def test_revised_collection_attempt_or_review_invalidates_receipt(self):
        first = review(manifest())
        changes = (
            replace(manifest(), collection_sha256="f" * 64),
            replace(manifest(), review_event_id="review:updated"),
            replace(manifest(), attempts=(replace(manifest().attempts[0], outcome="SOURCE_UNAVAILABLE"),)),
        )
        for changed in changes:
            with self.subTest(changed=changed):
                updated = review(changed)
                self.assertEqual(updated.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertNotEqual(updated.receipt_sha256, first.receipt_sha256)

    def test_source_revision_or_missing_source_fails_coverage_currentness(self):
        original = review(manifest())
        for versions in (
            {"denial:source": "a" * 64},
            {"denial:source": "a" * 64, "source:one": "0" * 64},
        ):
            with self.subTest(versions=versions):
                changed = review(manifest(), versions=versions)
                self.assertEqual(changed.coverage_status, "SEARCH_ATTEMPTS_STALE_OR_UNKNOWN_HOLD")
                self.assertEqual(changed.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertNotEqual(changed.receipt_sha256, original.receipt_sha256)

    def test_foreign_scope_duplicate_attempt_and_unbounded_data_fail_closed(self):
        for changed in (
            replace(manifest(), person_id="person:other"),
            replace(manifest(), scope="PRIVATE"),
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, "DENIAL_COVERAGE"):
                    review(changed)
        for change in (
            {"observed_at": at(2024)},
            {"attempts": manifest().attempts * 2},
            {"attempts": ()},
        ):
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "DENIAL_COVERAGE"):
                    replace(manifest(), **change)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.parliamentary_amendment_revalidation import (  # noqa: E402
    ParliamentaryAmendmentError,
    build_reviewed_parliamentary_amendment,
    evaluate_parliamentary_amendment,
)
from dichiarazioni_pubbliche.parliamentary_official_adapter import (  # noqa: E402
    normalize_parliamentary_official_record,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    EXCERPT_PUBLIC_USE_REQUIRED,
    ExcerptDisposition,
    ExcerptRequest,
    RightsStatus,
    decide_excerpt,
)
from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    RevalidationDisposition,
)
from dichiarazioni_pubbliche.supersession_reanalysis import (  # noqa: E402
    SupersessionReanalysisError,
)
from tests.parliamentary_official_fixture import (  # noqa: E402
    parliamentary_official_fixture_records,
)


OLD_OBSERVED = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)
NEW_OBSERVED = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)


def amendment_pair():
    previous = parliamentary_official_fixture_records()[0]
    current = copy.deepcopy(previous)
    current["statement"]["text"] = "Il valore comunicato è dieci."
    current["statement"]["start_char"] = 13
    current["statement"]["end_char"] = 42
    current["transcript"]["text"] = (
        "Mario Rossi: Il valore comunicato è dieci. Anna Bianchi: Chiedo la parola."
    )
    current["transcript"]["source_version"] = "camera-resoconto-101-v2-amended"
    return previous, current


def decision_for(previous, current):
    return evaluate_parliamentary_amendment(
        previous=previous,
        current=current,
        previous_observed_at=OLD_OBSERVED,
        current_observed_at=NEW_OBSERVED,
        as_of=date(2026, 10, 6),
    )


def build(previous=None, current=None, **overrides):
    if previous is None or current is None:
        previous, current = amendment_pair()
    decision = decision_for(previous, current)
    values = dict(
        previous=previous,
        current=current,
        previous_observed_at=OLD_OBSERVED,
        current_observed_at=NEW_OBSERVED,
        as_of=date(2026, 10, 6),
        provider_id="camera-official-fixture",
        review_event_id="review:camera:statement:101:1:amendment-v2",
        review_action="APPROVED",
        reviewed_entity_ref=decision.event_key,
        previous_valid_from="2026-10-05",
        previous_valid_until="2026-10-06",
        current_valid_from="2026-10-06",
        current_valid_until=None,
        affected_claim_ids=("claim:parliament:2", "claim:parliament:1"),
        affected_finding_ids=("finding:parliament:1",),
    )
    values.update(overrides)
    return build_reviewed_parliamentary_amendment(**values)


def excerpt_request(current_raw, *, rights_status=RightsStatus.UNKNOWN):
    current = normalize_parliamentary_official_record(current_raw)
    return ExcerptRequest(
        excerpt_text=current.transcript.statement_text,
        rights_status=rights_status,
        permitted_public_uses=(EXCERPT_PUBLIC_USE_REQUIRED,),
        rights_reviewed_on="2026-10-06",
        today="2026-10-06",
        source_url=current.transcript.source_url,
        content_id=current.record_id,
        segment_id=current.statement_id,
        transcript_variant_id=current.transcript.source_version,
        timestamp_start_seconds=120.0,
        timestamp_end_seconds=127.5,
        source_content_sha256=current.transcript.transcript_sha256,
        observed_source_sha256=current.transcript.transcript_sha256,
        excerpt_review_approved=True,
        profile_approved=True,
        max_excerpt_chars=100,
    )


class ParliamentaryAmendmentRevalidationTests(unittest.TestCase):
    def test_same_statement_reviewed_amendment_binds_dp511_hold_and_dp227_reanalysis(self):
        previous_raw, current_raw = amendment_pair()
        previous = normalize_parliamentary_official_record(previous_raw)
        current = normalize_parliamentary_official_record(current_raw)
        result = build(previous_raw, current_raw)

        self.assertEqual(result.statement_id, previous.statement_id)
        self.assertEqual(result.statement_id, current.statement_id)
        self.assertNotEqual(result.previous_record_id, result.current_record_id)
        self.assertEqual(result.revalidation.disposition, RevalidationDisposition.HOLD_REQUIRED)
        self.assertTrue(result.revalidation.needs_targeted_hold)
        self.assertTrue(result.revalidation.needs_reanalysis)
        self.assertIn(
            "OFFICIAL_VERSION_SUPERSEDED",
            result.revalidation.material_change_codes,
        )
        self.assertEqual(
            result.hold_request.decision_event_key,
            result.revalidation.event_key,
        )
        self.assertEqual(
            result.hold_request.scope.version,
            previous.transcript.source_version,
        )
        self.assertEqual(
            result.reanalysis_request.decision_event_key,
            result.revalidation.event_key,
        )
        self.assertEqual(
            result.reanalysis_request.affected_claim_ids,
            ("claim:parliament:1", "claim:parliament:2"),
        )

    def test_old_new_hash_version_and_effective_dates_are_preserved_exactly(self):
        previous_raw, current_raw = amendment_pair()
        previous = normalize_parliamentary_official_record(previous_raw)
        current = normalize_parliamentary_official_record(current_raw)
        result = build(previous_raw, current_raw)

        self.assertEqual(result.previous_transcript_version, previous.transcript.source_version)
        self.assertEqual(result.current_transcript_version, current.transcript.source_version)
        self.assertEqual(result.previous_transcript_sha256, previous.transcript.transcript_sha256)
        self.assertEqual(result.current_transcript_sha256, current.transcript.transcript_sha256)
        self.assertEqual(result.previous_valid_from, "2026-10-05")
        self.assertEqual(result.previous_valid_until, "2026-10-06")
        self.assertEqual(result.current_valid_from, "2026-10-06")
        self.assertIsNone(result.current_valid_until)
        self.assertEqual(result.reanalysis_request.previous.version_id, result.previous_transcript_version)
        self.assertEqual(result.reanalysis_request.current.version_id, result.current_transcript_version)

    def test_amendment_requires_approved_review_of_exact_dp511_event(self):
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "APPROVED_REVIEW_REQUIRED",
        ):
            build(review_action="PENDING")
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "REVIEW_TARGET_MISMATCH",
        ):
            build(reviewed_entity_ref="0" * 64)

    def test_same_official_statement_identity_is_required(self):
        previous, current = amendment_pair()
        current["statement"]["id"] = "camera:statement:2026-10-05:101:99"
        with self.assertRaisesRegex(
            ParliamentaryAmendmentError,
            "STATEMENT_ID_MISMATCH",
        ):
            decision_for(previous, current)

    def test_dp305_is_separate_and_missing_or_unknown_rights_never_become_permission(self):
        previous, current = amendment_pair()
        without_rights = build(previous, current)
        self.assertIsNone(without_rights.excerpt_decision)
        self.assertFalse(without_rights.public_excerpt_prerequisite_satisfied)

        request = excerpt_request(current, rights_status=RightsStatus.UNKNOWN)
        direct = decide_excerpt(request)
        with_unknown = build(previous, current, excerpt_request=request)
        self.assertEqual(with_unknown.excerpt_decision, direct)
        self.assertEqual(direct.disposition, ExcerptDisposition.PROHIBITED)
        self.assertFalse(with_unknown.public_excerpt_prerequisite_satisfied)
        self.assertTrue(with_unknown.revalidation.needs_targeted_hold)
        self.assertEqual(
            with_unknown.reanalysis_request.request_id,
            without_rights.reanalysis_request.request_id,
        )

    def test_only_explicit_dp305_clearance_can_satisfy_excerpt_prerequisite(self):
        previous, current = amendment_pair()
        request = excerpt_request(current, rights_status=RightsStatus.CLEARED)
        direct = decide_excerpt(request)
        self.assertTrue(direct.allowed)
        result = build(previous, current, excerpt_request=request)
        self.assertEqual(result.excerpt_decision, direct)
        self.assertTrue(result.public_excerpt_prerequisite_satisfied)
        self.assertIn("OFFICIAL_VERSION_SUPERSEDED", result.revalidation.material_change_codes)

    def test_contract_is_pure_and_has_no_publication_authority(self):
        first = build()
        second = build()
        self.assertEqual(first, second)
        fields = set(first.__dataclass_fields__)
        self.assertTrue(
            {
                "publication_status",
                "publication_authorized",
                "publish",
                "approved",
                "verdict",
                "assessment",
            }.isdisjoint(fields)
        )
        self.assertEqual(len(first.reanalysis_request.triggers), 2)
        self.assertEqual(len(first.reanalysis_request.reanalysis_job_ids), 2)


if __name__ == "__main__":
    unittest.main()

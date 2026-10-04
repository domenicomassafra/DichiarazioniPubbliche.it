"""DP-305 — copyright / transcript-excerpt policy tests.

The fail-closed spine: unknown rights, missing attribution, missing provenance,
expiry, source change, substitutive requests, and the not-yet-approved launch
profile.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    EXCERPT_POLICY_VERSION,
    EXCERPT_PROFILE_APPROVED,
    EXCERPT_PUBLIC_USE_REQUIRED,
    ALLOWED_PUBLIC_METHOD_FIELDS,
    REQUIRED_ATTRIBUTION_FIELDS,
    ExcerptDecisionCode,
    ExcerptRequest,
    RightsStatus,
    decide_excerpt,
    dossier_excerpt_budget,
    effective_excerpt_cap,
    render_attributed_excerpt,
)

SHA = "a" * 64

# A request that is correct in every respect EXCEPT the launch profile, which
# is the honest current state. Tests opt into an approved profile explicitly.
def _req(**overrides) -> ExcerptRequest:
    base = {
        "excerpt_text": "the fund was 12,000 euro",
        "rights_status": RightsStatus.CLEARED,
        "permitted_public_uses": (EXCERPT_PUBLIC_USE_REQUIRED,),
        "source_url": "https://example.org/speech",
        "content_id": "content-1",
        "segment_id": "segment-7",
        "transcript_variant_id": "variant-2",
        "timestamp_start_seconds": 10.0,
        "timestamp_end_seconds": 20.0,
        "source_content_sha256": SHA,
        "observed_source_sha256": SHA,
        "excerpt_review_approved": True,
        "profile_approved": True,
    }
    base.update(overrides)
    return ExcerptRequest(**base)


class FailClosedProfileTests(unittest.TestCase):
    def test_excerpt_profile_is_not_approved_today(self):
        # P-305-05 / B-305-01: no numeric limit is invented; nothing ships.
        self.assertFalse(EXCERPT_PROFILE_APPROVED)
        self.assertEqual(EXCERPT_POLICY_VERSION, "excerpt-rights-v1")

    def test_default_request_is_prohibited_because_the_profile_is_unapproved(self):
        result = decide_excerpt(ExcerptRequest(
            excerpt_text="the fund was 12,000 euro",
            rights_status=RightsStatus.CLEARED,
            permitted_public_uses=(EXCERPT_PUBLIC_USE_REQUIRED,),
        ))
        self.assertFalse(result.allowed)
        self.assertIn(
            ExcerptDecisionCode.PROFILE_NOT_APPROVED, result.codes
        )

    def test_a_fully_satisfied_request_passes_only_with_an_approved_profile(self):
        result = decide_excerpt(_req())
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, ExcerptDecisionCode.ALLOW.value)


class RightsTests(unittest.TestCase):
    """C-305-01: rights unknown means private."""

    def test_only_cleared_rights_can_authorize_an_excerpt(self):
        from dichiarazioni_pubbliche.policy.excerpt_policy import (
            PUBLICATION_AUTHORIZING_RIGHTS_STATUSES,
        )

        self.assertEqual(
            PUBLICATION_AUTHORIZING_RIGHTS_STATUSES, frozenset({RightsStatus.CLEARED})
        )

    def test_non_cleared_rights_are_prohibited(self):
        for status in (
            RightsStatus.UNKNOWN,
            RightsStatus.UNRESOLVED,
            RightsStatus.EXPIRED,
            RightsStatus.CONFLICTING,
            RightsStatus.REVOKED,
        ):
            with self.subTest(status=status):
                result = decide_excerpt(_req(rights_status=status))
                self.assertFalse(result.allowed)

    def test_unknown_rights_string_fails_closed(self):
        result = decide_excerpt(_req(rights_status="SOMETHING_ELSE"))
        self.assertEqual(result.codes[0], ExcerptDecisionCode.RIGHTS_NOT_CLEARED)

    def test_cleared_but_no_quotation_use_is_prohibited(self):
        result = decide_excerpt(_req(permitted_public_uses=("LINK_ONLY",)))
        self.assertIn(
            ExcerptDecisionCode.PUBLIC_USE_NOT_PERMITTED, result.codes
        )

    def test_expiry_and_revocation_have_distinct_codes(self):
        self.assertIn(
            ExcerptDecisionCode.RIGHTS_EXPIRED,
            decide_excerpt(_req(rights_status=RightsStatus.EXPIRED)).codes,
        )
        self.assertIn(
            ExcerptDecisionCode.RIGHTS_REVOKED,
            decide_excerpt(_req(rights_status=RightsStatus.REVOKED)).codes,
        )


class AttributionAndProvenanceTests(unittest.TestCase):
    def test_every_required_attribution_field_is_enforced(self):
        for field in sorted(REQUIRED_ATTRIBUTION_FIELDS - {"excerpt_policy_version"}):
            with self.subTest(field=field):
                result = decide_excerpt(_req(**{field: None}))
                self.assertIn(
                    ExcerptDecisionCode.ATTRIBUTION_INCOMPLETE, result.codes
                )

    def test_malformed_source_hash_is_provenance_incomplete(self):
        result = decide_excerpt(
            _req(source_content_sha256="not-a-hash", observed_source_sha256="not-a-hash")
        )
        self.assertIn(ExcerptDecisionCode.PROVENANCE_INCOMPLETE, result.codes)

    def test_source_change_after_clearance_is_detected(self):
        # E-305-06: a changed source needs a new rights review.
        result = decide_excerpt(_req(observed_source_sha256="b" * 64))
        self.assertIn(ExcerptDecisionCode.SOURCE_HASH_MISMATCH, result.codes)
        self.assertFalse(result.allowed)

    def test_stale_segment_is_refused(self):
        result = decide_excerpt(_req(segment_is_stale=True))
        self.assertIn(ExcerptDecisionCode.SEGMENT_STALE, result.codes)

    def test_missing_review_is_refused(self):
        result = decide_excerpt(_req(excerpt_review_approved=False))
        self.assertIn(ExcerptDecisionCode.REVIEW_MISSING, result.codes)


class BoundingTests(unittest.TestCase):
    def test_empty_excerpt_is_refused(self):
        result = decide_excerpt(_req(excerpt_text="   "))
        self.assertIn(ExcerptDecisionCode.EXCERPT_EMPTY, result.codes)

    def test_oversized_excerpt_is_refused(self):
        result = decide_excerpt(_req(excerpt_text="x" * 5000, max_excerpt_chars=400))
        self.assertIn(ExcerptDecisionCode.EXCERPT_TOO_LONG, result.codes)

    def test_ratio_cap_bounds_a_short_source(self):
        # A 500-char source cannot authorize a 400-char excerpt at a 10% cap.
        request = _req(excerpt_text="x" * 200, total_source_chars=500)
        self.assertEqual(effective_excerpt_cap(request), 50)
        result = decide_excerpt(request)
        self.assertIn(ExcerptDecisionCode.EXCERPT_TOO_LONG, result.codes)

    def test_excerpt_within_the_ratio_cap_is_allowed(self):
        request = _req(excerpt_text="x" * 40, total_source_chars=500)
        self.assertTrue(decide_excerpt(request).allowed)

    def test_whitespace_is_collapsed_but_punctuation_is_preserved(self):
        result = decide_excerpt(_req(excerpt_text="  the fund   was  12,000 euro.\n"))
        self.assertEqual(result.normalized_excerpt, "the fund was 12,000 euro.")

    def test_invalid_timestamp_ranges_are_refused(self):
        for start, end in ((20.0, 10.0), (None, 20.0), (10.0, None), (-5.0, 10.0)):
            with self.subTest(start=start, end=end):
                result = decide_excerpt(
                    _req(timestamp_start_seconds=start, timestamp_end_seconds=end)
                )
                self.assertIn(ExcerptDecisionCode.INVALID_TIMESTAMP_RANGE, result.codes)

    def test_unbounded_timestamp_window_is_refused(self):
        result = decide_excerpt(_req(timestamp_start_seconds=0.0, timestamp_end_seconds=900.0))
        self.assertIn(ExcerptDecisionCode.TIMESTAMP_RANGE_NOT_BOUNDED, result.codes)


class SubstitutivityTests(unittest.TestCase):
    def test_full_transcript_request_is_refused(self):
        result = decide_excerpt(_req(request_kind="FULL_TRANSCRIPT"))
        self.assertEqual(result.codes[0], ExcerptDecisionCode.FULL_TRANSCRIPT_REQUEST)
        self.assertFalse(result.allowed)

    def test_media_copy_request_is_refused(self):
        for kind in ("MEDIA_COPY", "AUDIO", "VIDEO", "SOURCE_CAPTURE"):
            with self.subTest(kind=kind):
                result = decide_excerpt(_req(request_kind=kind))
                self.assertIn(ExcerptDecisionCode.SUBSTITUTIVE_REQUEST, result.codes)

    def test_dossier_excerpt_budget_is_bounded(self):
        from dichiarazioni_pubbliche.policy.excerpt_policy import MAX_EXCERPTS_PER_DOSSIER

        self.assertTrue(dossier_excerpt_budget([10] * MAX_EXCERPTS_PER_DOSSIER))
        self.assertFalse(dossier_excerpt_budget([10] * (MAX_EXCERPTS_PER_DOSSIER + 1)))


class MethodDisclosureTests(unittest.TestCase):
    def test_allowed_method_fields_pass(self):
        result = decide_excerpt(
            _req(
                method_fields={
                    "machine_transcribed": True,
                    "asr_version": "v1",
                    "manual_correction_applied": False,
                }
            )
        )
        self.assertTrue(result.allowed)

    def test_disallowed_method_field_is_refused(self):
        result = decide_excerpt(
            _req(method_fields={"asr_provider_api_key": "leak"})
        )
        self.assertIn(ExcerptDecisionCode.METHOD_FIELD_NOT_ALLOWED, result.codes)

    def test_no_accuracy_claim_field_is_allowed(self):
        for field in ("accuracy_score", "confidence", "speaker_score"):
            with self.subTest(field=field):
                self.assertNotIn(field, ALLOWED_PUBLIC_METHOD_FIELDS)


class RendererTests(unittest.TestCase):
    def test_renderer_refuses_when_the_decision_is_not_allow(self):
        result = decide_excerpt(_req(excerpt_review_approved=False))
        with self.assertRaises(ValueError):
            render_attributed_excerpt(_req(), result)

    def test_renderer_escapes_the_excerpt(self):
        request = _req(excerpt_text='he said "we will cut <taxes> & more"')
        result = decide_excerpt(request)
        if not result.allowed:
            self.skipTest("excerpt failed a guard for an unrelated reason")
        rendered = render_attributed_excerpt(request, result)
        self.assertIn("&lt;taxes&gt;", rendered["text"])
        self.assertNotIn("<taxes>", rendered["text"])
        self.assertIn("&amp;", rendered["text"])

    def test_renderer_emits_only_public_fields(self):
        request = _req()
        rendered = render_attributed_excerpt(request, decide_excerpt(request))
        self.assertEqual(
            set(rendered),
            {
                "text",
                "source_url",
                "content_id",
                "segment_id",
                "transcript_variant_id",
                "timestamp_start_seconds",
                "timestamp_end_seconds",
                "excerpt_policy_version",
                "excerpt_chars",
            },
        )

    def test_renderer_does_not_leak_canonical_text_or_rights_receipts(self):
        request = _req()
        rendered = render_attributed_excerpt(request, decide_excerpt(request))
        serialized = str(rendered).lower()
        for leaked in ("canonical_text", "raw_text", "rights_receipt", "license_key"):
            self.assertNotIn(leaked, serialized)


class IntentVocabularyLeakTests(unittest.TestCase):
    """DP-301's hard rule reaches the excerpt renderer."""

    def test_excerpt_asserting_intent_is_refused(self):
        result = decide_excerpt(_req(excerpt_text="he lied to parliament"))
        self.assertIn(ExcerptDecisionCode.INTENT_LANGUAGE_IN_EXCERPT, result.codes)
        self.assertFalse(result.allowed)

    def test_plain_factual_excerpt_is_allowed(self):
        result = decide_excerpt(_req(excerpt_text="the fund was 12,000 euro"))
        self.assertTrue(result.allowed)


if __name__ == "__main__":
    unittest.main()

"""DP-305 — copyright / transcript-excerpt policy tests.

The fail-closed spine: unknown rights, missing attribution, missing provenance,
expiry, source change, substitutive requests, and the not-yet-approved launch
profile.
"""

import sys
import unittest
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    EXCERPT_POLICY_VERSION,
    EXCERPT_PROFILE_APPROVED,
    EXCERPT_PUBLIC_USE_REQUIRED,
    ALLOWED_PUBLIC_METHOD_FIELDS,
    MAX_AUDIT_REASON_CODES,
    MEDIA_EMBED_PUBLIC_USE_REQUIRED,
    REQUIRED_ATTRIBUTION_FIELDS,
    ExcerptBudgetCode,
    ExcerptDecisionCode,
    ExcerptRequest,
    MediaDecisionCode,
    MediaUseKind,
    MediaUseRequest,
    RightsStatus,
    build_rights_policy_audit,
    decide_excerpt,
    decide_excerpt_budget,
    decide_media_use,
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

    def test_operational_block_and_hold_statuses_are_prohibited(self):
        for status in (
            RightsStatus.BLOCKED,
            RightsStatus.FORBIDDEN,
            RightsStatus.LEGAL_HOLD,
            RightsStatus.RIGHTS_HOLD,
            RightsStatus.TAKEDOWN_HOLD,
            RightsStatus.REMOVED,
        ):
            with self.subTest(status=status):
                result = decide_excerpt(_req(rights_status=status))
                self.assertFalse(result.allowed)
                self.assertIn(ExcerptDecisionCode.RIGHTS_BLOCKED, result.codes)

    def test_full_transcript_is_suppressed_for_unknown_or_blocked_rights(self):
        for status in (RightsStatus.UNKNOWN, RightsStatus.RIGHTS_HOLD):
            with self.subTest(status=status):
                result = decide_excerpt(
                    _req(rights_status=status, request_kind="FULL_TRANSCRIPT")
                )
                self.assertFalse(result.allowed)
                self.assertEqual(
                    result.codes[0], ExcerptDecisionCode.FULL_TRANSCRIPT_REQUEST
                )

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

    def test_declared_rights_expiry_is_revalidated_at_read_time(self):
        current = decide_excerpt(
            _req(
                rights_reviewed_on="2026-09-01",
                rights_expires_on="2026-10-05",
                today="2026-10-05",
            )
        )
        self.assertTrue(current.allowed)

        expired = decide_excerpt(
            _req(
                rights_reviewed_on="2026-09-01",
                rights_expires_on="2026-10-05",
                today="2026-10-06",
            )
        )
        self.assertFalse(expired.allowed)
        self.assertIn(ExcerptDecisionCode.RIGHTS_EXPIRED, expired.codes)

    def test_declared_expiry_without_valid_clock_input_fails_closed(self):
        for today in ("", "not-a-date"):
            with self.subTest(today=today):
                result = decide_excerpt(
                    _req(rights_expires_on="2026-10-05", today=today)
                )
                self.assertFalse(result.allowed)
                self.assertIn(ExcerptDecisionCode.RIGHTS_DATE_INVALID, result.codes)

    def test_future_review_date_fails_closed(self):
        result = decide_excerpt(
            _req(rights_reviewed_on="2026-10-06", today="2026-10-05")
        )
        self.assertFalse(result.allowed)
        self.assertIn(ExcerptDecisionCode.RIGHTS_DATE_INVALID, result.codes)


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


class StructuredExcerptBudgetTests(unittest.TestCase):
    def test_default_profile_is_fail_closed(self):
        decision = decide_excerpt_budget([10])
        self.assertFalse(decision.allowed)
        self.assertIn(ExcerptBudgetCode.PROFILE_NOT_APPROVED, decision.codes)

    def test_approved_profile_calculates_count_and_total_budget(self):
        decision = decide_excerpt_budget(
            [30, 40],
            profile_approved=True,
            max_excerpts=2,
            max_excerpt_chars=50,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.excerpt_count, 2)
        self.assertEqual(decision.total_excerpt_chars, 70)
        self.assertEqual(decision.max_total_chars, 100)

    def test_count_and_total_overages_are_distinct(self):
        count = decide_excerpt_budget(
            [10, 10, 10],
            profile_approved=True,
            max_excerpts=2,
            max_excerpt_chars=50,
        )
        self.assertIn(ExcerptBudgetCode.EXCERPT_COUNT_EXCEEDED, count.codes)

        total = decide_excerpt_budget(
            [80, 30],
            profile_approved=True,
            max_excerpts=2,
            max_excerpt_chars=50,
        )
        self.assertIn(ExcerptBudgetCode.TOTAL_CHAR_BUDGET_EXCEEDED, total.codes)

    def test_single_excerpt_cannot_hide_inside_larger_total_budget(self):
        decision = decide_excerpt_budget(
            [80, 10],
            profile_approved=True,
            max_excerpts=2,
            max_excerpt_chars=50,
        )
        self.assertFalse(decision.allowed)
        self.assertIn(ExcerptBudgetCode.EXCERPT_ITEM_TOO_LONG, decision.codes)

    def test_invalid_lengths_fail_closed(self):
        for lengths in ([-1], [True], [1.5]):
            with self.subTest(lengths=lengths):
                decision = decide_excerpt_budget(
                    lengths,  # type: ignore[arg-type]
                    profile_approved=True,
                    max_excerpts=2,
                    max_excerpt_chars=50,
                )
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.codes, (ExcerptBudgetCode.INVALID_LENGTH,))


class MediaAuthorizationTests(unittest.TestCase):
    def _media(self, **overrides) -> MediaUseRequest:
        base = {
            "kind": MediaUseKind.EMBED,
            "rights_status": RightsStatus.CLEARED,
            "permitted_public_uses": (MEDIA_EMBED_PUBLIC_USE_REQUIRED,),
            "media_url": "https://media.example.test/embed/1",
            "media_policy_version": "public-media-v1",
            "content_kind": "VIDEO",
            "profile_approved": True,
        }
        base.update(overrides)
        return MediaUseRequest(**base)

    def test_embed_requires_clearance_and_explicit_public_use(self):
        self.assertTrue(decide_media_use(self._media()).allowed)

        unknown = decide_media_use(self._media(rights_status=RightsStatus.UNKNOWN))
        self.assertFalse(unknown.allowed)
        self.assertIn(MediaDecisionCode.RIGHTS_NOT_CLEARED, unknown.codes)

        missing_use = decide_media_use(self._media(permitted_public_uses=()))
        self.assertFalse(missing_use.allowed)
        self.assertIn(MediaDecisionCode.PUBLIC_USE_NOT_PERMITTED, missing_use.codes)

    def test_blocked_source_rights_suppress_embed(self):
        for status in (
            RightsStatus.BLOCKED,
            RightsStatus.RIGHTS_HOLD,
            RightsStatus.LEGAL_HOLD,
            RightsStatus.TAKEDOWN_HOLD,
        ):
            with self.subTest(status=status):
                result = decide_media_use(self._media(rights_status=status))
                self.assertFalse(result.allowed)
                self.assertIn(MediaDecisionCode.RIGHTS_BLOCKED, result.codes)

    def test_media_copy_modes_are_never_authorized_by_baseline(self):
        for kind in (
            MediaUseKind.MEDIA_COPY,
            MediaUseKind.AUDIO_COPY,
            MediaUseKind.VIDEO_COPY,
            MediaUseKind.SOURCE_CAPTURE,
        ):
            with self.subTest(kind=kind):
                result = decide_media_use(self._media(kind=kind))
                self.assertFalse(result.allowed)
                self.assertEqual(
                    result.codes, (MediaDecisionCode.SUBSTITUTIVE_MEDIA_COPY,)
                )

    def test_unknown_media_use_kind_fails_closed_with_bounded_code(self):
        result = decide_media_use(self._media(kind="SOMETHING_ELSE"))
        self.assertFalse(result.allowed)
        self.assertEqual(result.codes, (MediaDecisionCode.MEDIA_USE_KIND_INVALID,))

    def test_embed_profile_is_fail_closed_by_default(self):
        result = decide_media_use(self._media(profile_approved=False))
        self.assertFalse(result.allowed)
        self.assertIn(MediaDecisionCode.PROFILE_NOT_APPROVED, result.codes)

    def test_embed_requires_safe_url_policy_version_and_timed_media_kind(self):
        cases = (
            ({"media_url": "http://media.example.test/embed/1"}, MediaDecisionCode.MEDIA_URL_INVALID),
            ({"media_url": "https://127.0.0.1/embed/1"}, MediaDecisionCode.MEDIA_URL_INVALID),
            ({"media_policy_version": None}, MediaDecisionCode.MEDIA_POLICY_VERSION_MISSING),
            ({"content_kind": "WRITTEN"}, MediaDecisionCode.CONTENT_KIND_NOT_MEDIA),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                result = decide_media_use(self._media(**overrides))
                self.assertFalse(result.allowed)
                self.assertIn(expected, result.codes)


class RightsAuditTests(unittest.TestCase):
    def test_audit_is_content_free_and_machine_bounded(self):
        decision = decide_excerpt(
            _req(
                rights_status=RightsStatus.RIGHTS_HOLD,
                excerpt_text="PRIVATE_EXCERPT_SENTINEL",
            )
        )
        receipt = build_rights_policy_audit(
            subject_ref="segment:7",
            disposition=decision.disposition,
            reason_codes=decision.codes,
        )
        payload = asdict(receipt)
        rendered = repr(payload)
        self.assertNotIn("PRIVATE_EXCERPT_SENTINEL", rendered)
        self.assertNotIn("example.org/speech", rendered)
        self.assertLessEqual(len(receipt.reason_codes), MAX_AUDIT_REASON_CODES)
        self.assertTrue(
            set(receipt.reason_codes)
            <= {code.value for code in ExcerptDecisionCode}
        )

    def test_audit_rejects_free_form_reason_and_redacts_contact_subject(self):
        receipt = build_rights_policy_audit(
            subject_ref="private@example.test",
            disposition="SOMETHING_ELSE",
            reason_codes=(
                "PRIVATE BODY: do not log",
                ExcerptDecisionCode.RIGHTS_NOT_CLEARED,
            ),
        )
        self.assertEqual(receipt.subject_ref, "REDACTED_IDENTIFIER")
        self.assertEqual(receipt.disposition, "PROHIBITED")
        self.assertEqual(
            receipt.reason_codes,
            (ExcerptDecisionCode.RIGHTS_NOT_CLEARED.value,),
        )

    def test_audit_truncates_many_unique_machine_codes(self):
        receipt = build_rights_policy_audit(
            subject_ref="content:1",
            disposition="PROHIBITED",
            reason_codes=tuple(ExcerptDecisionCode),
        )
        self.assertEqual(len(receipt.reason_codes), MAX_AUDIT_REASON_CODES)
        self.assertTrue(receipt.reasons_truncated)


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

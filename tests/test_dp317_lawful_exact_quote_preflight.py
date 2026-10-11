"""DP-317 source-only quote-rights consistency: adversarial offline fixtures."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.lawful_exact_quote_preflight_v1 import (  # noqa: E402
    ExactQuoteRequest,
    ScopedQuoteRightsClaim,
    evaluate_exact_quote_preflight,
    quote_scope_fingerprint,
)
from dichiarazioni_pubbliche.quote_binding import (  # noqa: E402
    verify_written_quote_binding,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
TEXT = "One bounded original quotation."


def SHA(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


URL = "https://example.invalid/source/1"
SUBJECT = RightsSubject(
    source_family="FAMILY_A",
    locator_kind="URL",
    locator_value=URL,
    content_id="content-1",
)


def request(**changes):
    value = ExactQuoteRequest(
        subject=SUBJECT,
        capture_id="capture-1",
        capture_version="v1",
        capture_sha256=SHA("original-capture"),
        representation_sha256=SHA(TEXT),
        quotation_sha256=SHA(TEXT),
        context_sha256=SHA("context-around-quote"),
        selector_start=3,
        selector_end=3 + len(TEXT),
        representation="WRITTEN_ORIGINAL",
        text_role="SOURCE_ORIGINAL",
        source_language="it",
        displayed_language="it",
        public_use="STATEMENT",
        purpose="PUBLIC_QUOTATION",
        jurisdiction="IT",
        attribution_ref="private:attribution-1",
        translation_parent_sha256=None,
        representation_derivation_ref="private:text-extraction-v1",
    )
    return replace(value, **changes)


def scoped(req=None, **changes):
    req = req or request()
    value = ScopedQuoteRightsClaim(
        documented_scope=req,
        scope_fingerprint=quote_scope_fingerprint(req),
        decision_version="dp317-v1",
        status="CASE_REVIEWED",
        legal_basis="CASE_SPECIFIC_PERMISSION",
        source_terms_ref="private:immutable-source-terms",
        source_terms_version="terms-v3",
        lawful_basis_receipt_ref="private:rightsholder-receipt",
        qualified_reviewer_ref="private:qualified-reviewer",
        owner_decision_ref="private:owner-public-review",
        reviewed_at="2026-10-10T10:00:00+00:00",
        effective_at="2026-10-10T10:00:00+00:00",
        expires_at="2026-11-10T10:00:00+00:00",
        max_quotation_chars=len(TEXT),
        necessity_ref="private:necessity-and-context-review",
        attribution_required=True,
        conditions_satisfied=True,
        version_state="CURRENT",
        revocation_state="CURRENT",
        revocation_epoch=3,
    )
    return replace(value, **changes)


def private_rights(**changes):
    value = PrivateRightsRecord(
        id="rights:1",
        subject_fingerprint=rights_subject_fingerprint(SUBJECT),
        source_family="FAMILY_A",
        locator_kind="URL",
        locator_value=URL,
        content_id="content-1",
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref="private:capture-grant",
        permitted_uses=("STORE_BODY",),
        attribution_requirements=(),
        reviewed_at="2026-10-10T10:00:00+00:00",
        expires_at="2026-11-10T10:00:00+00:00",
        reviewer_ref="private:source-review",
        policy_version="source-policy-v1",
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )
    return replace(value, **changes)


def binding(req=None):
    req = req or request()
    return verify_written_quote_binding(
        statement_text_sha256=req.quotation_sha256,
        passage_text_sha256=req.quotation_sha256,
        private_text=TEXT,
        selector_type="TEXT_POSITION",
        start_char=req.selector_start,
        end_char=req.selector_end,
        source_sha256=req.representation_sha256,
    )


def check(req=None, claim=None, record=None, quoted_binding=None, **changes):
    req = req or request()
    if claim is None:
        claim = scoped(req)
    if record is None:
        record = private_rights()
    if quoted_binding is None:
        quoted_binding = binding(req)
    options = dict(
        request=req,
        rights_claim=claim,
        private_rights_record=record,
        binding=quoted_binding,
        private_rights_record_id="rights:1",
        private_rights_policy_version="source-policy-v1",
        current_revocation_epoch=3,
        now=NOW,
    )
    options.update(changes)
    return evaluate_exact_quote_preflight(**options)


class LawfulExactQuotePreflightTests(unittest.TestCase):
    def test_consistent_fixture_still_cannot_approve_public_quote(self):
        result = check()
        self.assertEqual(result.status, "HELD")
        self.assertTrue(result.source_only_consistent)
        self.assertFalse(result.public_quote_permitted)
        self.assertEqual(
            result.reason_code, "EXTERNAL_QUALIFIED_AND_LIVE_PROOF_REQUIRED"
        )
        self.assertEqual(len(result.scope_fingerprint), 64)
        self.assertNotIn(TEXT, repr(result))
        self.assertNotIn(URL, repr(result))
        self.assertNotIn("rightsholder-receipt", repr(result))
        self.assertEqual(result.required_external_gates, ("DP-307", "DP-320", "DP-443"))

    def test_same_claim_cannot_expand_to_adjacent_family_capture_use_representation(
        self,
    ):
        base = request()
        variations = (
            {"subject": replace(SUBJECT, source_family="FAMILY_B")},
            {
                "subject": replace(
                    SUBJECT, locator_value="https://example.invalid/other"
                )
            },
            {"subject": replace(SUBJECT, content_id="content-2")},
            {"capture_id": "capture-2"},
            {"capture_version": "v2"},
            {"capture_sha256": SHA("other-bytes")},
            {"representation_sha256": SHA("edition")},
            {"quotation_sha256": SHA("different-text")},
            {"context_sha256": SHA("clipped-context")},
            {"selector_start": 2},
            {"selector_end": base.selector_end + 1},
            {"representation": "OFFICIAL_TRANSCRIPT"},
            {"text_role": "IDENTIFIED_TRANSLATION"},
            {"displayed_language": "de"},
            {"source_language": "de"},
            {"public_use": "API"},
            {"purpose": "COMMERCIAL_REUSE"},
            {"jurisdiction": "DE"},
            {"attribution_ref": "private:different"},
            {"representation_derivation_ref": "private:other-derivation"},
        )
        for fields in variations:
            with self.subTest(fields=fields):
                result = check(
                    req=replace(base, **fields),
                    claim=scoped(base),
                    quoted_binding=binding(base),
                )
                self.assertFalse(result.source_only_consistent)
                self.assertFalse(result.public_quote_permitted)

    def test_private_metadata_only_and_revoke_or_expiry_cannot_mint_public_rights(self):
        for fields in (
            {"permitted_uses": ("DISCOVER_METADATA",)},
            {"rights_status": "UNKNOWN"},
            {"rights_status": "REVOKED"},
            {"expires_at": "2026-10-11T12:00:00+00:00"},
            {"version_state": "HISTORICAL"},
            {"locator_value": "https://example.invalid/other"},
            {"record_visibility": "PUBLIC"},
        ):
            with self.subTest(fields=fields):
                result = check(record=private_rights(**fields))
                self.assertFalse(result.source_only_consistent)
                self.assertFalse(result.public_quote_permitted)
        self.assertEqual(
            check(record=private_rights(rights_status="REVOKED")).reason_code,
            "SOURCE_USE_REVOKED",
        )

    def test_expired_conflicting_unreviewed_revoked_or_unbounded_claims_hold(self):
        for changes in (
            {"status": "UNKNOWN"},
            {"status": "DENIED"},
            {"status": "WITHDRAWN"},
            {"legal_basis": "PUBLIC_DOMAIN"},
            {"legal_basis": "BECAUSE_PUBLIC_FIGURE"},
            {"lawful_basis_receipt_ref": None},
            {"source_terms_ref": None},
            {"qualified_reviewer_ref": None},
            {"owner_decision_ref": None},
            {"reviewed_at": "2026-10-12T00:00:00+00:00"},
            {"effective_at": "2026-10-12T00:00:00+00:00"},
            {"expires_at": "2026-10-11T12:00:00+00:00"},
            {"max_quotation_chars": len(TEXT) - 1},
            {"max_quotation_chars": 0},
            {"necessity_ref": None},
            {"attribution_required": False},
            {"conditions_satisfied": False},
            {"version_state": "HISTORICAL"},
            {"revocation_state": "REVOKED"},
            {"revocation_state": "UNKNOWN"},
            {"revocation_epoch": 2},
            {"decision_version": "unknown-version"},
        ):
            with self.subTest(changes=changes):
                result = check(claim=scoped(**changes))
                self.assertFalse(result.source_only_consistent)
                self.assertFalse(result.public_quote_permitted)

    def test_missing_binding_forged_flag_or_source_hash_does_not_clear(self):
        valid = binding()
        for candidate in (
            None,
            replace(valid, status="BLOCKED"),
            replace(valid, source_sha256=SHA("another-source")),
            replace(valid, statement_text_sha256=SHA("another-quote")),
            replace(valid, end_char=valid.end_char + 1),
            replace(valid, version="fake-quote-binding"),
        ):
            with self.subTest(candidate=candidate):
                result = (
                    check(quoted_binding=candidate)
                    if candidate is not None
                    else (
                        evaluate_exact_quote_preflight(
                            request=request(),
                            rights_claim=scoped(),
                            private_rights_record=private_rights(),
                            binding=None,
                            private_rights_record_id="rights:1",
                            private_rights_policy_version="source-policy-v1",
                            current_revocation_epoch=3,
                            now=NOW,
                        )
                    )
                )
                self.assertFalse(result.source_only_consistent)

    def test_rights_row_documented_scope_and_representation_derivation_are_checked(
        self,
    ):
        req = request()
        self.assertEqual(
            check(
                claim=scoped(req, documented_scope=replace(req, public_use="API"))
            ).reason_code,
            "QUOTE_RIGHTS_DOCUMENTED_SCOPE_MISMATCH",
        )
        self.assertEqual(
            check(
                req=replace(req, representation_derivation_ref=None),
                claim=scoped(replace(req, representation_derivation_ref=None)),
            ).reason_code,
            "QUOTE_REPRESENTATION_DERIVATION_MISSING",
        )

    def test_translation_is_identified_and_bound_to_distinct_parent(self):
        translated = request(
            representation="EDITORIAL_TRANSLATION",
            text_role="IDENTIFIED_TRANSLATION",
            source_language="de",
            displayed_language="it",
            translation_parent_sha256=SHA("German wording"),
        )
        self.assertTrue(
            check(req=translated, claim=scoped(translated)).source_only_consistent
        )
        for invalid in (
            replace(translated, text_role="SOURCE_ORIGINAL"),
            replace(translated, translation_parent_sha256=None),
            replace(
                translated, translation_parent_sha256=translated.representation_sha256
            ),
            replace(translated, displayed_language="de"),
            replace(request(), displayed_language="de"),
        ):
            with self.subTest(invalid=invalid):
                self.assertFalse(
                    check(req=invalid, claim=scoped(invalid)).source_only_consistent
                )

    def test_film_audio_screenshot_embed_never_inherit_transcript_text_license(self):
        for representation in ("FILM_CLIP", "AUDIO_CLIP", "SCREENSHOT", "EMBED"):
            req = request(representation=representation)
            with self.subTest(representation=representation):
                result = check(req=req, claim=scoped(req))
                self.assertEqual(
                    result.reason_code, "QUOTE_NON_TEXT_REPRESENTATION_HELD"
                )
        transcript = request(representation="OFFICIAL_TRANSCRIPT")
        self.assertTrue(
            check(req=transcript, claim=scoped(transcript)).source_only_consistent
        )
        asr = request(representation="ASR_TRANSCRIPT")
        self.assertTrue(check(req=asr, claim=scoped(asr)).source_only_consistent)
        self.assertFalse(
            check(req=transcript, claim=scoped(request())).source_only_consistent
        )

    def test_revocation_epoch_has_to_be_current_and_clock_timezone_strict(self):
        self.assertEqual(
            check(current_revocation_epoch=4).reason_code,
            "QUOTE_REVOCATION_EPOCH_MISMATCH",
        )
        self.assertFalse(check(now=datetime(2026, 10, 11, 12)).source_only_consistent)
        self.assertFalse(check(current_revocation_epoch=None).source_only_consistent)
        self.assertFalse(
            check(
                record=private_rights(), private_rights_record_id="other"
            ).source_only_consistent
        )

    def test_quoted_length_never_uses_blanket_threshold_or_death_date(self):
        req = request()
        result = check(
            claim=scoped(
                req,
                legal_basis="SOURCE_SPECIFIC_LICENCE",
                max_quotation_chars=len(TEXT) + 1,
            ),
        )
        self.assertTrue(result.source_only_consistent)
        self.assertFalse(result.public_quote_permitted)
        self.assertFalse(
            check(
                claim=scoped(req, max_quotation_chars=9999, source_terms_version="")
            ).source_only_consistent,
        )


if __name__ == "__main__":
    unittest.main()

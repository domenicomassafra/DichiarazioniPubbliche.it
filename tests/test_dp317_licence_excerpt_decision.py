"""DP-317 licence-granted excerpt decision: adversarial and positive fixtures."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import (  # noqa: E402
    AttributionStatement,
    LicenceExcerptDecision,
    LiveRevocationAuthority,
    MAX_LICENCE_EXCERPT_CHARS,
    SourceTermsEvidence,
    attest_licence_use,
    decide_licence_excerpt,
    licence_decision_receipt,
    render_attribution,
)
from dichiarazioni_pubbliche.lawful_exact_quote_preflight_v1 import (  # noqa: E402
    ExactQuoteRequest,
    ScopedQuoteRightsClaim,
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

NOW = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)
TEXT = "Lo statement pubblico usa un passaggio originale e verificabile."
URL = "https://commission.europa.eu/about/organisation/president_en"
TERMS_URL = "https://commission.europa.eu/legal-notice_en"


def SHA(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


SUBJECT = RightsSubject(
    source_family="EC_OFFICIAL_COMMISSION_PROFILE",
    locator_kind="URL",
    locator_value=URL,
    content_id="commission-president-profile-en",
)


def request(**changes):
    value = ExactQuoteRequest(
        subject=SUBJECT,
        capture_id="capture-ec-president",
        capture_version="html-2026-10-23",
        capture_sha256=SHA("captured-html"),
        representation_sha256=SHA(TEXT + "-representation"),
        quotation_sha256=SHA(TEXT),
        context_sha256=SHA("context"),
        selector_start=0,
        selector_end=len(TEXT),
        representation="WRITTEN_ORIGINAL",
        text_role="SOURCE_ORIGINAL",
        source_language="en",
        displayed_language="en",
        public_use="STATEMENT",
        purpose="PUBLIC_QUOTATION",
        jurisdiction="IT",
        attribution_ref="private:ec-attribution",
        translation_parent_sha256=None,
        representation_derivation_ref="private:html-text-extraction-v1",
    )
    return replace(value, **changes)


def scoped(req=None, **changes):
    req = req or request()
    value = ScopedQuoteRightsClaim(
        documented_scope=req,
        scope_fingerprint=quote_scope_fingerprint(req),
        decision_version="dp317-v1",
        status="CASE_REVIEWED",
        legal_basis="SOURCE_SPECIFIC_LICENCE",
        source_terms_ref=TERMS_URL,
        source_terms_version="legal-notice-2026-10-23",
        lawful_basis_receipt_ref="private:licence-document-digest",
        qualified_reviewer_ref="private:machine-licence-attestation",
        owner_decision_ref="private:owner-release-2026-10-23",
        reviewed_at="2026-10-23T08:00:00+00:00",
        effective_at="2026-10-23T08:00:00+00:00",
        expires_at="2026-11-23T08:00:00+00:00",
        max_quotation_chars=req.selector_end - req.selector_start,
        necessity_ref="private:necessity-review",
        attribution_required=True,
        conditions_satisfied=True,
        version_state="CURRENT",
        revocation_state="CURRENT",
        revocation_epoch=7,
    )
    return replace(value, **changes)


def rights(**changes):
    value = PrivateRightsRecord(
        id="rights:ec-president",
        subject_fingerprint=rights_subject_fingerprint(SUBJECT),
        source_family=SUBJECT.source_family,
        locator_kind="URL",
        locator_value=URL,
        content_id=SUBJECT.content_id,
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref="private:licence-attestation",
        permitted_uses=("STORE_BODY",),
        attribution_requirements=(),
        reviewed_at="2026-10-23T08:00:00+00:00",
        expires_at="2026-11-23T08:00:00+00:00",
        reviewer_ref="machine:licence-attestation",
        policy_version="source-policy-v1",
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )
    return replace(value, **changes)


def evidence(**changes):
    value = SourceTermsEvidence(
        terms_url=TERMS_URL,
        terms_document_sha256=SHA("european-commission-legal-notice"),
        terms_version="legal-notice-2026-10-23",
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        rightsholder="European Commission",
        markers=("Attribution 4.0 International", "CC BY 4.0"),
    )
    return replace(value, **changes)


def attribution(**changes):
    value = AttributionStatement(
        creator="European Commission",
        work_title="President of the European Commission",
        source_url=URL,
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        modified=False,
    )
    return replace(value, **changes)


def binding(req=None, text=TEXT):
    req = req or request()
    return verify_written_quote_binding(
        statement_text_sha256=req.quotation_sha256,
        passage_text_sha256=req.quotation_sha256,
        private_text=text,
        selector_type="TEXT_POSITION",
        start_char=req.selector_start,
        end_char=req.selector_end,
        source_sha256=req.representation_sha256,
    )


class FakeAuthority(LiveRevocationAuthority):
    """Test authority whose epoch is read at decision time."""

    def __init__(self, epoch=7, ref="registry:revocation-epoch"):
        self.epoch = epoch
        self.ref = ref
        self.reads = 0

    def current_epoch(self):
        self.reads += 1
        return self.epoch

    def authority_ref(self):
        return self.ref


class NonIntAuthority(FakeAuthority):
    def current_epoch(self):
        self.reads += 1
        return True


class RaisingAuthority(FakeAuthority):
    def current_epoch(self):
        raise RuntimeError("store offline")


_UNSET = object()


def decide(req=None, claim=None, record=None, terms=None, statement=None,
           authority=_UNSET, text=TEXT, quoted=None, **changes):
    req = req or request()
    options = dict(
        request=req,
        binding=quoted if quoted is not None else binding(req, text),
        rights_claim=claim if claim is not None else scoped(req),
        private_rights_record=record if record is not None else rights(),
        private_rights_record_id="rights:ec-president",
        private_rights_policy_version="source-policy-v1",
        terms_evidence=terms if terms is not None else evidence(),
        attribution=statement if statement is not None else attribution(),
        live_revocation=FakeAuthority() if authority is _UNSET else authority,
        private_quote_text=text,
        now=NOW,
    )
    options.update(changes)
    return decide_licence_excerpt(**options)


class LicenceExcerptDecisionTests(unittest.TestCase):
    def test_verified_licence_permits_one_private_attributed_excerpt(self):
        result = decide()
        self.assertEqual(result.status, "PERMITTED")
        self.assertEqual(result.reason_code, "LICENCE_GRANT_VERIFIED_WITH_CONDITIONS")
        self.assertTrue(result.permitted)
        self.assertEqual(result.licence_id, "CC-BY-4.0")
        self.assertEqual(result.quote_chars, len(TEXT))
        self.assertLessEqual(result.max_quote_chars, MAX_LICENCE_EXCERPT_CHARS)
        self.assertTrue(result.private_only)
        self.assertFalse(result.publication_authorized)
        self.assertFalse(result.web_projection_enabled)
        self.assertIn("European Commission", result.attribution_text)
        self.assertIn("CC-BY-4.0", result.attribution_text)
        self.assertIn("testo non modificato", result.attribution_text)
        self.assertIn("European Commission", result.private_rendered_text)
        self.assertEqual(len(result.scope_fingerprint), 64)
        self.assertEqual(result.revocation_epoch, 7)

    def test_receipt_is_deterministic_and_binds_scope_and_licence(self):
        first = decide()
        second = decide()
        self.assertEqual(first, second)
        receipt = licence_decision_receipt(first, request())
        self.assertEqual(receipt, licence_decision_receipt(second, request()))
        self.assertEqual(len(receipt), 64)
        self.assertNotEqual(receipt, licence_decision_receipt(first, request(
            quotation_sha256=SHA("other"))))

    def test_private_rendering_requires_the_exact_text_used_by_verified_binding(self):
        # The metadata-only binding proves TEXT, not a different caller-supplied
        # body. Keeping the same length defeats a superficial length check.
        original_binding = binding()
        unlicensed_wording = "X" * len(TEXT)
        authority = FakeAuthority()
        result = decide(
            quoted=original_binding,
            text=unlicensed_wording,
            authority=authority,
        )
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "LICENCE_EXCERPT_TEXT_BINDING_MISMATCH")
        self.assertIsNone(result.private_rendered_text)
        self.assertFalse(result.permitted)
        self.assertEqual(authority.reads, 0)

    def test_quote_text_is_escaped_in_the_private_rendering(self):
        hostile = '<script>alert("x")</script>'
        req = request(quotation_sha256=SHA(hostile),
                      selector_end=len(hostile))
        result = decide(req=req, text=hostile)
        self.assertEqual(result.status, "PERMITTED")
        self.assertNotIn("<script>", result.private_rendered_text)
        self.assertIn("&lt;script&gt;", result.private_rendered_text)

    def test_either_identifying_marker_is_enough_but_some_marker_is_required(self):
        short = decide(terms=evidence(markers=("CC BY 4.0",)))
        self.assertEqual(short.status, "PERMITTED")
        result = decide(terms=evidence(markers=("Some other licence notice",)))
        self.assertEqual(result.status, "PROHIBITED")
        self.assertEqual(result.reason_code, "LICENCE_MARKERS_NOT_OBSERVED")
        self.assertIsNone(result.private_rendered_text)

    def test_unverifiable_licence_identifier_is_prohibited(self):
        result = decide(terms=evidence(licence_id="ALL-RIGHTS-RESERVED"))
        self.assertEqual(result.status, "PROHIBITED")
        self.assertEqual(result.reason_code, "LICENCE_ID_NOT_VERIFIABLE")

    def test_case_specific_permission_is_not_upgraded_to_a_licence_grant(self):
        result = decide(claim=scoped(legal_basis="CASE_SPECIFIC_PERMISSION"))
        self.assertEqual(result.status, "PROHIBITED")
        self.assertEqual(result.reason_code, "LICENCE_GRANT_NOT_ESTABLISHED")
        self.assertIsNone(result.private_rendered_text)

    def test_revoked_claim_is_prohibited(self):
        result = decide(claim=scoped(revocation_state="REVOKED"))
        self.assertEqual(result.status, "PROHIBITED")
        self.assertEqual(result.reason_code, "LICENCE_DECISION_REVOKED")

    def test_terms_binding_must_match_the_hashed_document_version(self):
        result = decide(claim=scoped(source_terms_ref="https://example.org/other"))
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "LICENCE_TERMS_BINDING_MISMATCH")

    def test_expired_decision_is_re_evaluated_at_read_time(self):
        result = decide(claim=scoped(expires_at="2026-10-22T08:00:00+00:00"))
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "QUOTE_RIGHTS_EXPIRED_OR_NOT_EFFECTIVE")

    def test_live_revocation_is_read_and_must_match_the_claim(self):
        authority = FakeAuthority(epoch=8)
        result = decide(authority=authority)
        self.assertEqual(authority.reads, 1)
        self.assertEqual(result.status, "PROHIBITED")
        self.assertEqual(result.reason_code, "LIVE_REVOCATION_DIVERGED_FROM_CLAIM")

    def test_revocation_after_permit_revokes_the_next_read(self):
        authority = FakeAuthority(epoch=7)
        self.assertEqual(decide(authority=authority).status, "PERMITTED")
        authority.epoch = 9
        self.assertEqual(decide(authority=authority).status, "PROHIBITED")
        self.assertEqual(authority.reads, 2)

    def test_missing_or_broken_revocation_authority_never_permits(self):
        cases = (
            (None, "LIVE_REVOCATION_AUTHORITY_REQUIRED"),
            (NonIntAuthority(), "LIVE_REVOCATION_EPOCH_INVALID"),
            (RaisingAuthority(), "LIVE_REVOCATION_UNAVAILABLE"),
            (FakeAuthority(ref="  "), "LIVE_REVOCATION_AUTHORITY_REF_INVALID"),
        )
        for authority, expected in cases:
            with self.subTest(reason=expected):
                result = decide(authority=authority)
                self.assertEqual(result.status, "HELD")
                self.assertEqual(result.reason_code, expected)
                self.assertIsNone(result.private_rendered_text)

    def test_tampered_wording_is_refused_before_the_licence_is_consulted(self):
        req = request(quotation_sha256=SHA("altered wording"))
        result = decide(req=req, text=TEXT)
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "QUOTE_BINDING_UNVERIFIED")

    def test_excerpt_over_the_non_substitution_bound_is_held(self):
        long_text = "x" * (MAX_LICENCE_EXCERPT_CHARS + 1)
        req = request(quotation_sha256=SHA(long_text), selector_end=len(long_text))
        result = decide(req=req, text=long_text)
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "LICENCE_EXCERPT_BOUNDARY_EXCEEDED")

    def test_attribution_must_name_the_rightsholder_and_the_locator(self):
        for statement, expected in (
            (attribution(creator="  "), "ATTRIBUTION_FIELDS_INCOMPLETE"),
            (attribution(creator="Someone"), "ATTRIBUTION_RIGHTSHOLDER_MISMATCH"),
            (attribution(source_url="https://example.org/x"), "ATTRIBUTION_LOCATOR_MISMATCH"),
            (attribution(modified=True), "ATTRIBUTION_MODIFIED_TEXT_NOT_SUPPORTED"),
            (attribution(licence_url="https://creativecommons.org/licenses/by/3.0/"),
             "ATTRIBUTION_LICENCE_MISMATCH"),
        ):
            with self.subTest(expected=expected):
                result = decide(statement=statement)
                self.assertEqual(result.status, "HELD")
                self.assertIsNone(result.private_rendered_text)

    def test_primitive_subclasses_and_foreign_types_are_rejected(self):
        class Lie(str):
            def __eq__(self, other):
                return True

            def __hash__(self):
                return hash("CC BY 4.0")

        class Markers(tuple):
            def __iter__(self):
                return iter(("Attribution 4.0 International", "CC BY 4.0"))

        class Evidence(SourceTermsEvidence):
            pass

        cases = (
            (evidence(markers=(Lie("unrelated"),)), "LICENCE_MARKERS_INVALID"),
            (evidence(markers=Markers(("CC BY 4.0", "Attribution 4.0 International"))),
             "LICENCE_MARKERS_INVALID"),
            (Evidence(**evidence().__dict__), "LICENCE_TERMS_EVIDENCE_INVALID"),
            (evidence(terms_document_sha256="A" * 64), "LICENCE_TERMS_DIGEST_INVALID"),
        )
        for terms, expected in cases:
            with self.subTest(expected=expected):
                result = decide(terms=terms)
                self.assertEqual(result.status, "PROHIBITED")
                self.assertEqual(result.reason_code, expected)

    def test_render_attribution_is_stable_plain_text(self):
        statement = attribution()
        self.assertEqual(
            render_attribution(statement, as_html=False),
            render_attribution(statement, as_html=True).replace("&amp;", "&"),
        )
        self.assertIn(URL, render_attribution(statement, as_html=False))

    def test_decision_object_has_no_publication_authority_switches(self):
        fields = LicenceExcerptDecision.__dataclass_fields__
        self.assertEqual(fields["publication_authorized"].default, False)
        self.assertEqual(fields["web_projection_enabled"].default, False)
        self.assertEqual(fields["private_only"].default, True)


class LicenceUseAttestationTests(unittest.TestCase):
    def test_verified_licence_attests_private_use_only(self):
        result = attest_licence_use(evidence())
        self.assertEqual(result.status, "APPROVED")
        self.assertEqual(result.reason_code, "LICENCE_VERIFIED_FOR_PRIVATE_USE")
        self.assertEqual(result.licence_id, "CC-BY-4.0")
        self.assertTrue(result.attribution_required)
        self.assertTrue(result.private_only)
        self.assertFalse(result.publication_authorized)

    def test_missing_markers_or_broken_evidence_hold_the_attestation(self):
        for terms, expected in (
            (evidence(markers=("Unrelated notice",)), "LICENCE_MARKERS_NOT_OBSERVED"),
            (evidence(licence_id="UNKNOWN"), "LICENCE_ID_NOT_VERIFIABLE"),
            (None, "LICENCE_TERMS_EVIDENCE_INVALID"),
        ):
            with self.subTest(expected=expected):
                result = attest_licence_use(terms)
                self.assertEqual(result.status, "HELD")
                self.assertEqual(result.reason_code, expected)
                self.assertFalse(result.publication_authorized)

    def test_cc0_does_not_require_attribution(self):
        result = attest_licence_use(evidence(
            licence_id="CC0-1.0",
            licence_url="https://creativecommons.org/publicdomain/zero/1.0/",
            markers=("CC0 1.0 Universal", "CC0 1.0"),
        ))
        self.assertEqual(result.status, "APPROVED")
        self.assertFalse(result.attribution_required)


if __name__ == "__main__":
    unittest.main()

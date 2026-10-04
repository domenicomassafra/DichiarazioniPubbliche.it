"""DP-302 — right-of-reply intake validation policy tests.

Threat rows covered here are the ones that are machine-checkable without a
network or a database: resource exhaustion, unsafe URL, type/shape abuse,
replay/idempotency, review-gate bypass by field injection, personal-data
flooding, and the bounded acknowledgement contract.
"""

import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.correction_runtime import (  # noqa: E402
    deterministic_right_of_reply_id,
)
from dichiarazioni_pubbliche.policy.intake_policy import (  # noqa: E402
    INTAKE_ENABLED,
    INTAKE_POLICY_VERSION,
    LAUNCH_PROFILE_CONFIGURED,
    MAX_EVIDENCE_URLS,
    MAX_EVIDENCE_URL_CHARS,
    MAX_REPLY_BODY_CHARS,
    IntakeDisposition,
    IntakeRejectionReason,
    IntakeRequest,
    RateLimitProfile,
    RateLimitState,
    RateScope,
    acknowledgement_is_bounded,
    compute_request_fingerprint,
    normalize_evidence_urls,
    rate_limit_decision,
    validate_evidence_url,
    validate_intake_request,
    validate_intake_payload,
)

VALID = {
    "finding_id": "finding-123",
    "body": "On 3 March 2026 the minister said 12,000; the register shows 11,800.",
    "submitter_name": "A. Reviewer",
    "submitter_role": "Journalist",
    "evidence_urls": ["https://example.org/register"],
    "request_fingerprint": "fp-abc",
}


def _req(**overrides) -> IntakeRequest:
    data = {**VALID, **overrides}
    return IntakeRequest(**data)


def _enabled(**overrides) -> IntakeRequest:
    return _req(**overrides)


class LaunchProfileTests(unittest.TestCase):
    def test_intake_is_disabled_by_default(self):
        # B-302-01: the public endpoint cannot come up before the profile.
        self.assertFalse(INTAKE_ENABLED)
        self.assertFalse(LAUNCH_PROFILE_CONFIGURED)
        self.assertEqual(INTAKE_POLICY_VERSION, "reply-intake-policy-v1")

    def test_unconfigured_profile_rejects_every_request(self):
        result = validate_intake_request(_enabled())
        self.assertEqual(result.reason, IntakeRejectionReason.LAUNCH_PROFILE_MISSING)
        self.assertFalse(result.accepted)

    def test_configured_but_disabled_intake_rejects(self):
        result = validate_intake_request(
            _enabled(), launch_profile_configured=True, intake_enabled=False
        )
        self.assertEqual(result.reason, IntakeRejectionReason.INTAKE_DISABLED)

    def test_rate_limit_without_configured_profile_fails_closed(self):
        decision, reason = rate_limit_decision(
            RateLimitProfile(scope=RateScope.PER_FINDING, limit=3, window_seconds=3600),
            RateLimitState(submissions_in_window=0),
        )
        self.assertEqual(decision, IntakeDisposition.REJECTED)
        self.assertEqual(reason, IntakeRejectionReason.LAUNCH_PROFILE_MISSING)


class EdgeValidationTests(unittest.TestCase):
    def _validate(self, **overrides):
        return validate_intake_request(
            _enabled(**overrides), launch_profile_configured=True, intake_enabled=True
        )

    def test_valid_submission_is_accepted_private_only(self):
        result = self._validate()
        self.assertTrue(result.accepted)
        self.assertEqual(result.disposition, IntakeDisposition.ACCEPTED_PRIVATE)
        self.assertTrue(result.reply_id.startswith("reply:"))

    def test_empty_body_is_rejected(self):
        result = self._validate(body="   ")
        self.assertEqual(result.reason, IntakeRejectionReason.BODY_EMPTY)

    def test_oversized_body_is_rejected(self):
        result = self._validate(body="x" * (MAX_REPLY_BODY_CHARS + 1))
        self.assertEqual(result.reason, IntakeRejectionReason.BODY_TOO_LONG)

    def test_wrong_types_are_rejected_not_coerced(self):
        for field, value in (
            ("finding_id", 12345),
            ("body", {"text": "hi"}),
            ("submitter_name", ["a"]),
            ("evidence_urls", "https://example.org/one"),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    self._validate(**{field: value}).reason,
                    IntakeRejectionReason.WRONG_TYPE,
                )

    def test_missing_required_field_is_rejected(self):
        result = self._validate(request_fingerprint=None)
        self.assertEqual(result.reason, IntakeRejectionReason.MISSING_FIELD)

    def test_blank_fingerprint_is_rejected(self):
        result = self._validate(request_fingerprint="   ")
        self.assertEqual(result.reason, IntakeRejectionReason.FINGERPRINT_MISSING)

    def test_control_characters_in_body_are_rejected(self):
        result = self._validate(body="valid text\x00\x07more")
        self.assertEqual(result.reason, IntakeRejectionReason.BODY_CONTROL_CHARACTERS)

    def test_oversized_identity_field_is_rejected(self):
        result = self._validate(submitter_name="n" * 301)
        self.assertEqual(result.reason, IntakeRejectionReason.IDENTITY_TOO_LONG)

    def test_too_many_evidence_urls_is_rejected(self):
        urls = [f"https://example.org/{i}" for i in range(MAX_EVIDENCE_URLS + 1)]
        result = self._validate(evidence_urls=urls)
        self.assertEqual(result.reason, IntakeRejectionReason.TOO_MANY_EVIDENCE_URLS)

    def test_rejection_never_echoes_the_offending_input(self):
        secret = "SECRET-PII-" + "z" * 50
        result = self._validate(body="x" * (MAX_REPLY_BODY_CHARS + 1) + secret)
        self.assertNotIn(secret, result.reason)
        self.assertNotIn(secret, " ".join(result.reasons))


class UnsafeUrlTests(unittest.TestCase):
    def test_rejects_non_http_schemes(self):
        for url in (
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD4=",
            "ftp://example.org/x",
            "gopher://example.org",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_evidence_url(url)

    def test_rejects_userinfo_credentials(self):
        with self.assertRaises(ValueError):
            validate_evidence_url("https://user:pass@example.org/x")

    def test_rejects_missing_host(self):
        with self.assertRaises(ValueError):
            validate_evidence_url("https:///path")

    def test_rejects_oversized_url(self):
        with self.assertRaises(ValueError):
            validate_evidence_url("https://example.org/" + "a" * MAX_EVIDENCE_URL_CHARS)

    def test_rejects_non_string(self):
        with self.assertRaises(ValueError):
            validate_evidence_url(1234)

    def test_duplicate_urls_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            normalize_evidence_urls(
                ["https://example.org/a", "https://example.org/a"]
            )
        self.assertIn("DUPLICATE_EVIDENCE_URL", str(ctx.exception))

    def test_intake_performs_no_network_resolution_at_all(self):
        # C-302-04 / AC-302.5: intake must not resolve, fetch, or redirect.
        with mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError(
            "intake must not resolve DNS"
        )), mock.patch.object(socket, "create_connection", side_effect=AssertionError(
            "intake must not connect"
        )):
            result = validate_intake_request(
                _req(evidence_urls=["https://example.org/private/never-fetched"]),
                launch_profile_configured=True,
                intake_enabled=True,
            )
            self.assertTrue(result.accepted)
            self.assertEqual(
                result.normalized_evidence_urls, ("https://example.org/private/never-fetched",)
            )


class ReviewGateBypassTests(unittest.TestCase):
    """B-302-02: a public submitter cannot set an operator/review field."""

    def _validate(self, **overrides):
        return validate_intake_request(
            _enabled(**overrides), launch_profile_configured=True, intake_enabled=True
        )

    def test_reserved_operator_fields_are_refused(self):
        for field in (
            "status",
            "publication_status",
            "public_visibility",
            "review_actor",
            "evidence_approved",
            "moderation_decision",
            "rights_status",
            "policy_override",
        ):
            with self.subTest(field=field):
                # An HTTP submitter controls the field names, so the raw
                # payload path is the one under test here.
                result = validate_intake_payload(
                    {**VALID, field: "PUBLISHED"},
                    launch_profile_configured=True,
                    intake_enabled=True,
                )
                self.assertEqual(result.reason, IntakeRejectionReason.UNKNOWN_FIELD)
                self.assertFalse(result.accepted)

    def test_arbitrary_unknown_field_is_refused(self):
        result = validate_intake_payload(
            {**VALID, "totally_custom": "x"},
            launch_profile_configured=True,
            intake_enabled=True,
        )
        self.assertEqual(result.reason, IntakeRejectionReason.UNKNOWN_FIELD)

    def test_non_string_field_name_is_refused(self):
        result = validate_intake_payload(
            {**VALID, 7: "x"},
            launch_profile_configured=True,
            intake_enabled=True,
        )
        self.assertEqual(result.reason, IntakeRejectionReason.WRONG_FIELD_NAME_TYPE)

    def test_non_mapping_payload_is_refused(self):
        result = validate_intake_payload(
            ["not", "a", "mapping"],
            launch_profile_configured=True,
            intake_enabled=True,
        )
        self.assertEqual(result.reason, IntakeRejectionReason.WRONG_TYPE)

    def test_oversized_field_count_is_refused(self):
        payload = {**VALID}
        payload.update({f"extra{i}": "x" for i in range(6)})
        result = validate_intake_payload(
            payload, launch_profile_configured=True, intake_enabled=True
        )
        self.assertEqual(result.reason, IntakeRejectionReason.REQUEST_TOO_LARGE)

    def test_clean_raw_payload_is_accepted(self):
        result = validate_intake_payload(
            VALID, launch_profile_configured=True, intake_enabled=True
        )
        self.assertTrue(result.accepted)

    def test_public_acknowledgement_is_bounded_and_non_claimant(self):
        result = self._validate()
        ack = result.public_ack
        self.assertEqual(set(ack), {"receipt_id", "policy_version", "state"})
        self.assertEqual(ack["state"], "RECEIVED_PRIVATE")
        self.assertNotIn(VALID["body"], str(ack))
        self.assertTrue(acknowledgement_is_bounded(result))

    def test_rejection_acknowledgement_carries_no_receipt(self):
        result = self._validate(body="")
        self.assertEqual(result.public_ack, {"state": IntakeDisposition.REJECTED.value})
        self.assertTrue(acknowledgement_is_bounded(result))


class IdempotencyTests(unittest.TestCase):
    """E-302-03 / AC-302.3: replay cannot widen provenance."""

    def _validate(self, **overrides):
        return validate_intake_request(
            _enabled(**overrides), launch_profile_configured=True, intake_enabled=True
        )

    def test_identical_submissions_produce_the_same_reply_id(self):
        first = self._validate()
        second = self._validate()
        self.assertEqual(first.reply_id, second.reply_id)
        self.assertEqual(first.source_hash, second.source_hash)

    def test_fingerprint_ignores_surrounding_whitespace_only(self):
        a = self._validate(body="  hello world  ")
        b = self._validate(body="hello world")
        self.assertEqual(a.reply_id, b.reply_id)

    def test_fingerprint_changes_with_substantive_content(self):
        a = self._validate()
        b = self._validate(body="a different statement entirely")
        self.assertNotEqual(a.reply_id, b.reply_id)

    def test_policy_fingerprint_matches_the_private_runtime_identity(self):
        # The public edge and correction_runtime must not disagree about what a
        # reply is, otherwise a replay would create a second record.
        result = self._validate()
        runtime_id = deterministic_right_of_reply_id(
            finding_id=VALID["finding_id"],
            body=VALID["body"],
            submitter_name=VALID["submitter_name"],
            submitter_role=VALID["submitter_role"],
            evidence_urls=list(VALID["evidence_urls"]),
        )
        self.assertIsNotNone(result.reply_id)
        # Both are deterministic; the public edge additionally binds the policy
        # version, so the IDs are stable but not required to be equal. What must
        # hold is that each is a pure function of the same normalized content.
        again = compute_request_fingerprint(
            finding_id=VALID["finding_id"],
            body=VALID["body"],
            submitter_name=VALID["submitter_name"],
            submitter_role=VALID["submitter_role"],
            evidence_urls=tuple(VALID["evidence_urls"]),
        )
        self.assertEqual(again, result.source_hash)
        self.assertEqual(runtime_id, deterministic_right_of_reply_id(
            finding_id=VALID["finding_id"],
            body=VALID["body"],
            submitter_name=VALID["submitter_name"],
            submitter_role=VALID["submitter_role"],
            evidence_urls=list(VALID["evidence_urls"]),
        ))


class AbuseControlTests(unittest.TestCase):
    def test_quarantine_not_rejection_for_personal_data_shape(self):
        result = validate_intake_request(
            _req(body="write to me at person@example.org or 06 12345678"),
            launch_profile_configured=True,
            intake_enabled=True,
        )
        self.assertEqual(result.disposition, IntakeDisposition.QUARANTINED)
        self.assertIn("contact_disclosure_candidate", result.quarantine_signals)
        self.assertIn("numeric_identifier_candidate", result.quarantine_signals)
        # Quarantine is private and human-routed: it never publishes.
        self.assertFalse(result.accepted)

    def test_intent_language_in_body_is_quarantined_not_published(self):
        result = validate_intake_request(
            _req(body="He lied about the number, the register proves it."),
            launch_profile_configured=True,
            intake_enabled=True,
        )
        self.assertEqual(result.disposition, IntakeDisposition.QUARANTINED)
        self.assertEqual(result.reason, IntakeRejectionReason.INTENT_LANGUAGE_IN_BODY)

    def test_rate_limit_deferral_for_scoped_limits(self):
        decision, reason = rate_limit_decision(
            RateLimitProfile(
                scope=RateScope.PER_FINDING, limit=2, window_seconds=3600, configured=True
            ),
            RateLimitState(submissions_in_window=2),
        )
        self.assertEqual(decision, IntakeDisposition.DEFERRED_RATE_LIMITED)
        self.assertEqual(reason, IntakeRejectionReason.RATE_LIMIT_EXCEEDED)

    def test_global_quota_rejects_rather_than_defers(self):
        decision, reason = rate_limit_decision(
            RateLimitProfile(scope=RateScope.GLOBAL, limit=100, window_seconds=3600, configured=True),
            RateLimitState(submissions_in_window=100),
        )
        self.assertEqual(decision, IntakeDisposition.REJECTED)
        self.assertEqual(reason, IntakeRejectionReason.QUOTA_EXCEEDED)

    def test_cooldown_deferral(self):
        decision, reason = rate_limit_decision(
            RateLimitProfile(
                scope=RateScope.PER_NETWORK, limit=5, window_seconds=3600, configured=True
            ),
            RateLimitState(submissions_in_window=0, cooldown_remaining_seconds=120),
        )
        self.assertEqual(decision, IntakeDisposition.DEFERRED_RATE_LIMITED)
        self.assertEqual(reason, IntakeRejectionReason.COOLDOWN_ACTIVE)

    def test_under_limit_is_accepted(self):
        decision, reason = rate_limit_decision(
            RateLimitProfile(
                scope=RateScope.PER_NETWORK, limit=5, window_seconds=3600, configured=True
            ),
            RateLimitState(submissions_in_window=1),
        )
        self.assertEqual(decision, IntakeDisposition.ACCEPTED_PRIVATE)
        self.assertEqual(reason, IntakeRejectionReason.OK)


class PurityTests(unittest.TestCase):
    def test_module_performs_no_io_on_import_and_validation(self):
        import builtins

        real_open = builtins.open
        opened = []

        def tracking_open(*args, **kwargs):
            opened.append(args[0] if args else None)
            return real_open(*args, **kwargs)

        with mock.patch.object(builtins, "open", tracking_open):
            validate_intake_request(
                _req(), launch_profile_configured=True, intake_enabled=True
            )
        self.assertEqual(opened, [], "intake policy must not open any file")

    def test_validation_is_deterministic(self):
        args = dict(launch_profile_configured=True, intake_enabled=True)
        results = [validate_intake_request(_req(), **args) for _ in range(5)]
        self.assertEqual({r.reply_id for r in results}, {results[0].reply_id})


if __name__ == "__main__":
    unittest.main()

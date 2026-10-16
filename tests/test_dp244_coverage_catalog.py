"""DP-244 source-only bounded coverage, never proof of global completeness."""

import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.coverage_catalog_v1 import (  # noqa: E402
    CoverageObservation, CoverageUnit, build_source_coverage,
    public_freshness_descriptor,
)

NOW = datetime(2026, 10, 11, 17, tzinfo=timezone.utc)
SHA = "a" * 64


def unit(**changes):
    return replace(CoverageUnit(
        unit_id="coverage:synthetic", source_family="OFFICIAL_TEST_FAMILY",
        source_id="source:synthetic", collection_id="private:collection",
        language="de", source_format="text/xml", expected_content_class="OFFICIAL_RECORD",
        interval_start=datetime(1930, 1, 1, tzinfo=timezone.utc),
        interval_end=datetime(1940, 1, 1, tzinfo=timezone.utc),
        mode="HISTORICAL_BACKFILL", policy_version="policy:approved-test",
        max_staleness_seconds=86400,
    ), **changes)


def observation(**changes):
    return replace(CoverageObservation(
        attempt_id="attempt:1", source_id="source:synthetic",
        policy_version="policy:approved-test", scope_fingerprint=unit().scope_fingerprint(),
        attempted_at=NOW - timedelta(minutes=5),
        status="UNCHANGED", source_version="version:1", content_sha256=SHA,
        observation_receipt_id="receipt:official:test:1",
        enumerated_scope_review_id="review:scope:1",
        enumeration_complete_within_scope=True, rights_status="CLEARED",
    ), **changes)


def reconcile(rows=(), **changes):
    return build_source_coverage(
        unit(), tuple(rows), now=NOW, rights_ready=True,
        budget_ready=True, capability_ready=True, **changes,
    )


class CoverageCatalogTests(unittest.TestCase):
    def test_unknown_unwatched_has_no_worldwide_completeness_claim(self):
        result = reconcile()
        self.assertEqual(result.state, "NOT_COVERED")
        self.assertIsNone(result.last_successful_observed_at)
        self.assertIsNone(public_freshness_descriptor(result, public_scope_review_id="review:public"))
        self.assertFalse(result.dispatch_authorized)

    def test_scope_reviewed_not_global_makes_bounded_freshness(self):
        result = reconcile((observation(),), baseline_sha256=SHA)
        self.assertEqual(result.state, "CURRENT_WITHIN_OBSERVED_SCOPE")
        self.assertEqual(result.delta_proposal, "NONE")
        self.assertEqual(result, reconcile((observation(), observation()), baseline_sha256=SHA))
        descriptor = public_freshness_descriptor(result, public_scope_review_id="review:public")
        self.assertEqual(descriptor["source_family"], "OFFICIAL_TEST_FAMILY")
        self.assertIn("non garantito", descriptor["coverage_limit"])
        self.assertNotIn("private:collection", str(descriptor))
        self.assertNotIn("source:synthetic", str(descriptor))

    def test_future_scope_end_cannot_be_attested_complete_by_earlier_observation(self):
        # Even a source enumeration flagged complete cannot cover dates which
        # had not yet occurred when the receipt was obtained.  An unchecked
        # source subscription must not produce a public currentness descriptor.
        future_window = unit(
            interval_start=NOW - timedelta(days=1),
            interval_end=NOW + timedelta(days=2),
            mode="INCREMENTAL_SUBSCRIPTION",
            max_staleness_seconds=7 * 86400,
        )
        early = observation(
            scope_fingerprint=future_window.scope_fingerprint(),
            attempted_at=NOW,
        )
        premature = build_source_coverage(
            future_window, (early,), now=NOW,
            baseline_sha256=SHA, rights_ready=True,
            budget_ready=True, capability_ready=True,
        )
        self.assertEqual(premature.state, "PARTIAL")
        self.assertEqual(premature.reason_code, "COVERAGE_INTERVAL_NOT_YET_OBSERVED")
        self.assertFalse(premature.dispatch_authorized)
        self.assertIsNone(public_freshness_descriptor(premature, public_scope_review_id="review:public"))

        # The same exact reviewed scope becomes eligible only with a later
        # independently supplied success at or beyond its declared end.
        later = replace(
            early, attempt_id="attempt:after-window",
            observation_receipt_id="receipt:official:test:after-window",
            enumerated_scope_review_id="review:scope:after-window",
            attempted_at=NOW + timedelta(days=3),
        )
        settled = build_source_coverage(
            future_window, (early, later), now=NOW + timedelta(days=3),
            baseline_sha256=SHA, rights_ready=True,
            budget_ready=True, capability_ready=True,
        )
        self.assertEqual(settled.state, "CURRENT_WITHIN_OBSERVED_SCOPE")

    def test_success_without_independent_scope_enumeration_is_partial(self):
        row = observation(enumeration_complete_within_scope=False, enumerated_scope_review_id=None)
        result = reconcile((row,))
        self.assertEqual(result.state, "PARTIAL")
        self.assertIsNone(public_freshness_descriptor(result, public_scope_review_id="review:public"))

    def test_changed_source_requires_reanalysis_and_real_cost_rights_gates(self):
        row = observation(status="CHANGED", source_version="version:2", content_sha256="b" * 64)
        result = reconcile((row,), baseline_sha256=SHA)
        self.assertEqual(result.state, "STALE")
        self.assertEqual(result.delta_proposal, "REVIEW_CHANGED_SOURCE")
        self.assertFalse(result.dispatch_authorized)
        limited = build_source_coverage(unit(), (row,), now=NOW, baseline_sha256=SHA,
                                        rights_ready=True, budget_ready=False, capability_ready=True)
        self.assertEqual(limited.delta_proposal, "NONE")
        self.assertEqual(limited.reason_code, "COVERAGE_CHANGE_CHILD_GATES_NOT_READY")

    def test_first_changed_observation_without_derived_baseline_cannot_claim_public_freshness(self):
        # A reviewed enumeration can attest the bounded source scope, but a CHANGED
        # body still cannot attest that downstream derived readers used its bytes.
        changed = observation(status="CHANGED", source_version="version:2", content_sha256="b" * 64)
        pending = reconcile((changed,))
        self.assertEqual(pending.state, "STALE")
        self.assertEqual(pending.reason_code, "COVERAGE_CHANGED_SOURCE_REANALYSIS_PENDING")
        self.assertEqual(pending.delta_proposal, "REVIEW_CHANGED_SOURCE")
        self.assertIsNone(public_freshness_descriptor(pending, public_scope_review_id="review:public"))

        # Re-observation of the same bytes is cheap, not evidence of reanalysis.
        unchanged_again = replace(
            changed, attempt_id="attempt:2", status="UNCHANGED",
            attempted_at=NOW, observation_receipt_id="receipt:official:test:2",
        )
        self.assertEqual(reconcile((changed, unchanged_again)).state, "STALE")

        # A matching reviewed baseline clears the hold; a first UNCHANGED
        # enumeration remains a legitimate source-coverage CURRENT observation.
        reviewed = reconcile((changed,), baseline_sha256="b" * 64)
        self.assertEqual(reviewed.state, "CURRENT_WITHIN_OBSERVED_SCOPE")
        self.assertIsNotNone(public_freshness_descriptor(reviewed, public_scope_review_id="review:public"))
        first_unchanged = reconcile((observation(),))
        self.assertEqual(first_unchanged.state, "CURRENT_WITHIN_OBSERVED_SCOPE")

        # A later CHANGED status can be only a new version label. When the
        # already observed body is identical it needs no new derived work.
        initial = observation()
        relabeled = replace(
            initial, attempt_id="attempt:2", status="CHANGED", source_version="version:2",
            attempted_at=NOW, observation_receipt_id="receipt:official:test:2",
        )
        self.assertEqual(reconcile((initial, relabeled)).state, "CURRENT_WITHIN_OBSERVED_SCOPE")
        self.assertEqual(reconcile((initial, relabeled)).delta_proposal, "NONE")

    def test_newer_revoked_rights_never_reopen_changed_source_work(self):
        changed = observation(
            attempt_id="attempt:1", attempted_at=NOW - timedelta(minutes=20),
            status="CHANGED", content_sha256="b" * 64, source_version="version:2",
        )
        revoked = observation(
            attempt_id="attempt:2", attempted_at=NOW,
            status="RIGHTS_BLOCKED", rights_status="REVOKED",
            source_version=None, content_sha256=None, observation_receipt_id=None,
            enumerated_scope_review_id=None, enumeration_complete_within_scope=False,
        )
        result = reconcile((changed, revoked), baseline_sha256=SHA)
        self.assertEqual(result.state, "UNKNOWN")
        self.assertEqual(result.reason_code, "COVERAGE_RIGHTS_UNKNOWN_OR_BLOCKED")
        self.assertEqual(result.delta_proposal, "NONE")
        self.assertIsNone(public_freshness_descriptor(result, public_scope_review_id="review:public"))

    def test_successive_changed_hashes_do_not_become_current_without_baseline(self):
        old = observation(attempt_id="attempt:1", attempted_at=NOW - timedelta(minutes=20))
        newer = observation(
            attempt_id="attempt:2", status="UNCHANGED",
            content_sha256="b" * 64, source_version="version:2",
        )
        result = reconcile((old, newer))
        self.assertEqual(result.state, "STALE")
        self.assertEqual(result.delta_proposal, "REVIEW_CHANGED_SOURCE")
        self.assertEqual(result.observed_source_version, "version:2")
        self.assertIsNone(public_freshness_descriptor(result, public_scope_review_id="review:public"))
        # A reviewed derived baseline for the newest body resolves uncertainty.
        reviewed = reconcile((old, newer), baseline_sha256="b" * 64)
        self.assertEqual(reviewed.state, "CURRENT_WITHIN_OBSERVED_SCOPE")
        self.assertEqual(reviewed.delta_proposal, "NONE")
        # A new source version with identical body is cheap and does not reanalyse.
        same_body = replace(newer, content_sha256=SHA)
        self.assertEqual(reconcile((old, same_body)).delta_proposal, "NONE")

    def test_observation_fingerprint_is_stable_across_time_and_receipt_sensitive(self):
        row = observation()
        first = reconcile((row,), baseline_sha256=SHA)
        one_hour_later = build_source_coverage(
            unit(), (row,), now=NOW + timedelta(hours=1), baseline_sha256=SHA,
            rights_ready=True, budget_ready=True, capability_ready=True,
        )
        self.assertEqual(first.observation_fingerprint, one_hour_later.observation_fingerprint)
        other_receipt = replace(row, observation_receipt_id="receipt:official:test:2")
        self.assertNotEqual(first.observation_fingerprint,
                            reconcile((other_receipt,), baseline_sha256=SHA).observation_fingerprint)

    def test_outage_attempt_does_not_replace_last_good_observation(self):
        previous = observation(attempt_id="attempt:1", attempted_at=NOW - timedelta(minutes=20))
        failed = observation(attempt_id="attempt:2", status="OUTAGE", attempted_at=NOW,
                             source_version=None, content_sha256=None, observation_receipt_id=None,
                             enumerated_scope_review_id=None,
                             enumeration_complete_within_scope=False)
        result = reconcile((previous, failed), baseline_sha256=SHA)
        self.assertEqual(result.state, "STALE")
        self.assertEqual(result.last_successful_observed_at, previous.attempted_at.isoformat())
        self.assertEqual(result.last_attempted_at, NOW.isoformat())

    def test_latest_outage_keeps_outage_reason_even_if_previous_body_changed(self):
        changed = observation(status="CHANGED", content_sha256="b" * 64)
        outage = observation(
            attempt_id="attempt:outage", attempted_at=NOW, status="OUTAGE",
            source_version=None, content_sha256=None, observation_receipt_id=None,
            enumerated_scope_review_id=None, enumeration_complete_within_scope=False,
        )
        result = reconcile((changed, outage), baseline_sha256=SHA)
        self.assertEqual(result.state, "STALE")
        self.assertEqual(result.reason_code, "COVERAGE_RECENT_ATTEMPT_UNVERIFIED")
        self.assertEqual(result.delta_proposal, "NONE")

    def test_rights_unknown_and_expired_source_not_current(self):
        for rights in ("UNKNOWN", "EXPIRED", "REVOKED", "DENIED"):
            row = observation(rights_status=rights,
                              enumeration_complete_within_scope=False,
                              enumerated_scope_review_id=None)
            with self.subTest(rights=rights):
                result = reconcile((row,))
                self.assertEqual(result.state, "UNKNOWN")
                self.assertFalse(result.dispatch_authorized)

    def test_old_success_is_stale_even_without_latest_failure(self):
        old = observation(attempted_at=NOW - timedelta(days=5))
        result = reconcile((old,), baseline_sha256=SHA)
        self.assertEqual(result.state, "STALE")

    def test_strict_scope_and_replay_conflicts_are_rejected(self):
        a = observation()
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            reconcile((a, replace(a, content_sha256="c" * 64)))
        with self.assertRaisesRegex(ValueError, "MIXED_SCOPE"):
            reconcile((replace(a, source_id="source:other"),))
        with self.assertRaisesRegex(ValueError, "FUTURE_OBSERVATION"):
            reconcile((replace(a, attempted_at=NOW + timedelta(days=1)),))

    def test_independent_scopes_cannot_reuse_another_units_review_receipt(self):
        row = observation()
        changes = (
            {"interval_start": datetime(1935, 1, 1, tzinfo=timezone.utc)},
            {"collection_id": "private:other-collection"},
            {"language": "it"},
            {"mode": "INCREMENTAL_SUBSCRIPTION"},
        )
        for changed_scope in changes:
            with self.subTest(changed_scope=changed_scope):
                with self.assertRaisesRegex(ValueError, "MIXED_SCOPE"):
                    build_source_coverage(unit(**changed_scope), (row,), now=NOW,
                                          rights_ready=True)

    def test_longer_staleness_policy_cannot_reuse_short_window_source_receipt(self):
        # A source review bound to a 60s freshness contract cannot be relabeled
        # as 365 days while keeping the old receipt's scope fingerprint.
        short_policy = unit(max_staleness_seconds=60)
        receipt = observation(scope_fingerprint=short_policy.scope_fingerprint())
        short = build_source_coverage(
            short_policy, (receipt,), now=NOW, baseline_sha256=SHA,
            rights_ready=True,
        )
        self.assertEqual(short.state, "STALE")
        relaxed_policy = unit(max_staleness_seconds=365 * 86400)
        self.assertNotEqual(short_policy.scope_fingerprint(), relaxed_policy.scope_fingerprint())
        with self.assertRaisesRegex(ValueError, "COVERAGE_MIXED_SCOPE"):
            build_source_coverage(
                relaxed_policy, (receipt,), now=NOW, baseline_sha256=SHA,
                rights_ready=True,
            )

    def test_backfill_and_subscription_modes_do_not_fabricate_shared_coverage(self):
        one = reconcile((observation(),))
        subscription_unit = unit(mode="INCREMENTAL_SUBSCRIPTION")
        subscription_observation = observation(scope_fingerprint=subscription_unit.scope_fingerprint())
        subscription = build_source_coverage(
            subscription_unit, (subscription_observation,), now=NOW, rights_ready=True)
        self.assertEqual(one.mode, "HISTORICAL_BACKFILL")
        self.assertEqual(subscription.mode, "INCREMENTAL_SUBSCRIPTION")
        self.assertNotEqual(subscription.observation_fingerprint, one.observation_fingerprint)

    def test_incomplete_scope_cannot_be_self_attested_by_error(self):
        with self.assertRaisesRegex(ValueError, "UNREVIEWED_COMPLETENESS"):
            observation(status="OUTAGE", source_version=None, content_sha256=None,
                        observation_receipt_id=None, rights_status="UNKNOWN")


if __name__ == "__main__":
    unittest.main()

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.incremental_source_watch import (  # noqa: E402
    WatchCommittedAttempt,
    WatchCoverageSnapshot,
    WatchObservation,
    WatchPolicy,
    WatchReadiness,
    WatchState,
    build_private_watch_daily_digest,
    plan_watch_poll,
    policy_fingerprint,
    reconcile_watch_observation,
)


T0 = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)
SHA_A = hashlib.sha256(b"official source a").hexdigest()
SHA_B = hashlib.sha256(b"official source b").hexdigest()


def policy(**changes):
    args = dict(
        source_id="official:one", locator_id="official:one:feed",
        source_family="OFFICIAL_RSS", corpus_id="pilot:historical",
        corpus_cutoff="2026-10-01", policy_revision="operator-approved-r1",
        enabled=True,
    )
    args.update(changes)
    return WatchPolicy(**args)


def gate(p, **changes):
    args = dict(
        source_id=p.source_id, corpus_id=p.corpus_id,
        policy_fingerprint=policy_fingerprint(p),
        rights_status="READY", rights_receipt="rights:1",
        capability_status="READY", capability_receipt="runtime:1",
        budget_status="READY", budget_receipt="cost:1",
        remaining_children=1,
    )
    args.update(changes)
    return WatchReadiness(**args)


def state(p, **changes):
    args = dict(
        source_id=p.source_id,
        policy_fingerprint=policy_fingerprint(p),
        revision=4, content_sha256=SHA_A, source_version="record-v1",
        etag='"etag-a"', last_modified="Fri, 09 Oct 2026 10:00:00 GMT",
        last_attempted_at=T0 - timedelta(hours=1),
        last_successful_observed_at=T0 - timedelta(hours=1),
        last_attempt_id="last-attempt",
    )
    args.update(changes)
    return WatchState(**args)


def response(**changes):
    args = dict(
        observed_at=T0 + timedelta(seconds=2),
        status_code=200, content_sha256=SHA_A,
        source_version="record-v1", etag='"etag-a"',
        last_modified="Fri, 09 Oct 2026 10:00:00 GMT",
    )
    args.update(changes)
    return WatchObservation(**args)


def check(p, s, *, g=None, at=T0, attempt_id="poll-42", outcome=None, after_gate=None):
    g = g or gate(p)
    planned = plan_watch_poll(p, s, g, attempted_at=at, attempt_id=attempt_id)
    assert planned.allowed, planned.reason
    decision = reconcile_watch_observation(p, s, after_gate or g, planned, outcome or response())
    return planned, decision


class IncrementalWatchTests(unittest.TestCase):
    def test_daily_private_health_digest_replays_real_attempts_and_exposes_unknowns(self):
        today = date(2026, 10, 11)
        p = policy()
        prior = state(p, last_attempted_at=T0 - timedelta(days=1),
                      last_successful_observed_at=T0 - timedelta(days=1))
        before_success = gate(p)
        first_plan, first = check(
            p, prior, at=T0, outcome=WatchObservation(
                observed_at=T0 + timedelta(seconds=2), status_code=304,
            ),
        )
        new_version = response(
            observed_at=T0 + timedelta(minutes=10, seconds=2),
            content_sha256=SHA_B, source_version="record-v2", etag='"etag-b"',
        )
        second_plan, second = check(
            p, first.next_state, at=T0 + timedelta(minutes=10),
            attempt_id="amended", outcome=new_version,
        )
        throttle = response(observed_at=T0 + timedelta(hours=1, seconds=2),
                            status_code=429, content_sha256=None, retry_after_seconds=120)
        third_plan, third = check(
            p, second.next_state, at=T0 + timedelta(hours=1),
            attempt_id="throttle", outcome=throttle,
        )
        p_new = policy(source_id="official:new", locator_id="official:new:feed")
        empty = WatchState(source_id=p_new.source_id)
        new_plan, new = check(p_new, empty, attempt_id="first-new", outcome=response())
        self.assertEqual(new.disposition, "CHANGED")

        p_rights = policy(source_id="official:rights", locator_id="official:rights:feed")
        rights_prior = state(p_rights, last_attempted_at=T0 - timedelta(days=1),
                             last_successful_observed_at=T0 - timedelta(days=1))
        revoked = gate(p_rights, rights_status="REVOKED")
        rights_plan, rights_decision = check(
            p_rights, rights_prior, attempt_id="rights-attempt",
            outcome=response(content_sha256=SHA_B, etag='"etag-b"', source_version="record-v2"),
            after_gate=revoked,
        )
        p_paused = policy(source_id="official:paused", locator_id="official:paused:feed", enabled=False)
        p_budget = policy(source_id="official:budget", locator_id="official:budget:feed")
        budget_prior = state(p_budget, last_attempted_at=T0 - timedelta(days=1),
                             last_successful_observed_at=T0 - timedelta(days=1))
        snapshots = (
            WatchCoverageSnapshot(p, third.next_state, before_success),
            WatchCoverageSnapshot(p_new, new.next_state, gate(p_new)),
            WatchCoverageSnapshot(p_rights, rights_decision.next_state, revoked),
            WatchCoverageSnapshot(p_paused, WatchState(source_id=p_paused.source_id)),
            WatchCoverageSnapshot(p_budget, budget_prior,
                                  gate(p_budget, budget_status="CAPPED")),
        )
        receipts = (
            WatchCommittedAttempt(p.source_id, prior, before_success, before_success,
                                  first_plan, WatchObservation(
                                      observed_at=T0 + timedelta(seconds=2), status_code=304,
                                  ), first, measured_cost_micro_eur=100),
            WatchCommittedAttempt(p.source_id, first.next_state, before_success, before_success,
                                  second_plan, new_version, second, measured_cost_micro_eur=200),
            WatchCommittedAttempt(p.source_id, second.next_state, before_success, before_success,
                                  third_plan, throttle, third),
            WatchCommittedAttempt(p_new.source_id, empty, gate(p_new), gate(p_new),
                                  new_plan, response(), new, measured_cost_micro_eur=0),
            WatchCommittedAttempt(p_rights.source_id, rights_prior, gate(p_rights), revoked,
                                  rights_plan, response(content_sha256=SHA_B, etag='"etag-b"',
                                                        source_version="record-v2"), rights_decision),
        )
        digest = build_private_watch_daily_digest(
            day=today, as_of=T0 + timedelta(hours=1, seconds=10),
            snapshots=snapshots, committed_attempts=tuple(reversed(receipts)),
        )
        self.assertEqual((digest.attempts, digest.new, digest.modified, digest.unchanged,
                          digest.unavailable, digest.blocked, digest.rate_limited),
                         (5, 1, 1, 1, 1, 1, 1))
        self.assertEqual((digest.metered_cost_micro_eur, digest.unknown_cost_attempts), (300, 2))
        self.assertEqual((digest.watched_sources, digest.unwatched_sources), (4, 1))
        by_source = {item.source_id: item for item in digest.sources}
        changed = by_source[p.source_id]
        self.assertEqual(changed.last_successful_observed_at,
                         T0 + timedelta(minutes=10, seconds=2))
        self.assertEqual(changed.last_attempted_at, T0 + timedelta(hours=1))
        self.assertEqual(changed.last_disposition, "UNAVAILABLE")
        self.assertEqual(changed.consecutive_failures, 1)
        self.assertIn("SOURCE_BACKOFF", changed.known_gaps)
        self.assertIn("SOURCE_FAILURES_RECORDED", changed.known_gaps)
        self.assertIn("CORPUS_CUTOFF_LIMITED", changed.known_gaps)
        self.assertEqual(by_source[p_paused.source_id].watch_status, "NOT_WATCHED")
        self.assertEqual(by_source[p_budget.source_id].watch_status, "BLOCKED")
        self.assertIn("BUDGET_BLOCKED", by_source[p_budget.source_id].known_gaps)
        self.assertIn("RIGHTS_BLOCKED", by_source[p_rights.source_id].known_gaps)
        self.assertEqual(by_source[p_rights.source_id].last_successful_observed_at,
                         rights_prior.last_successful_observed_at)
        self.assertEqual(by_source[p_new.source_id].daily_new, 1)

        for bad in (
            receipts + (receipts[0],),
            tuple(r for r in receipts if r is not receipts[1]),
            (replace(receipts[1], decision=replace(second, disposition="UNCHANGED")),)
            + receipts[:1] + receipts[2:],
            (replace(receipts[3], source_id=p.source_id),) + receipts[:3] + receipts[4:],
            (replace(receipts[3], measured_cost_micro_eur=-1),) + receipts[:3] + receipts[4:],
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "DAILY_WATCH_"):
                    build_private_watch_daily_digest(day=today,
                                                     as_of=T0 + timedelta(hours=1, seconds=10),
                                                     snapshots=snapshots, committed_attempts=bad)

        with self.assertRaisesRegex(ValueError, "DAILY_WATCH_UNACCOUNTED_ATTEMPT"):
            build_private_watch_daily_digest(
                day=today, as_of=T0 + timedelta(hours=1, seconds=10), snapshots=snapshots,
                committed_attempts=(),
            )

    def test_daily_digest_rejects_future_receipts_and_preserves_utc_day_boundary(self):
        p = policy()
        before = state(p, last_attempted_at=T0 - timedelta(days=1),
                       last_successful_observed_at=T0 - timedelta(days=1))
        plan, decision = check(p, before, outcome=response())
        receipt = WatchCommittedAttempt(p.source_id, before, gate(p), gate(p),
                                        plan, response(), decision)
        snapshot = WatchCoverageSnapshot(p, decision.next_state, gate(p))
        with self.assertRaisesRegex(ValueError, "DAILY_WATCH_FUTURE_RECEIPT"):
            build_private_watch_daily_digest(day=T0.date(), as_of=T0 + timedelta(seconds=1),
                                             snapshots=(WatchCoverageSnapshot(p, before, gate(p)),),
                                             committed_attempts=(receipt,))
        with self.assertRaisesRegex(ValueError, "DAILY_WATCH_FUTURE_STATE"):
            build_private_watch_daily_digest(day=T0.date(), as_of=T0 + timedelta(seconds=1),
                                             snapshots=(snapshot,), committed_attempts=())
        with self.assertRaisesRegex(ValueError, "DAILY_WATCH_OUTSIDE_DAY"):
            build_private_watch_daily_digest(day=T0.date() - timedelta(days=1),
                                             as_of=T0 + timedelta(hours=1),
                                             snapshots=(WatchCoverageSnapshot(p, before, gate(p)),),
                                             committed_attempts=(receipt,))
        with self.assertRaisesRegex(ValueError, "DAILY_WATCH_DUPLICATE_SOURCE"):
            build_private_watch_daily_digest(day=T0.date(), as_of=T0 + timedelta(hours=1),
                                             snapshots=(snapshot, snapshot), committed_attempts=(receipt,))
        with self.assertRaisesRegex(ValueError, "DAILY_WATCH_SNAPSHOT_OUTSIDE_DAY"):
            build_private_watch_daily_digest(day=T0.date() - timedelta(days=1),
                                             as_of=T0 + timedelta(hours=1),
                                             snapshots=(snapshot,), committed_attempts=())

    def test_default_disabled_and_no_plan_headers(self):
        p = WatchPolicy(
            "source", "locator", "FAMILY", "corpus", "2026-10-01", "r1",
        )
        plan = plan_watch_poll(
            p, WatchState(source_id="source"), gate(p),
            attempt_id="attempt", attempted_at=T0,
        )
        self.assertFalse(plan.allowed)
        self.assertEqual(plan.reason, "WATCH_DISABLED")
        self.assertEqual(plan.conditional_headers, ())
        # An operator can always disable an already-active watch. Re-enabling
        # after a policy revision still requires a deliberate state migration.
        active = policy()
        stop = plan_watch_poll(
            replace(active, enabled=False), state(active), gate(active),
            attempt_id="shutdown-check", attempted_at=T0,
        )
        self.assertEqual(stop.reason, "WATCH_DISABLED")
        self.assertFalse(stop.allowed)

    def test_conditional_etag_last_modified_and_valid_304_no_children(self):
        p = policy()
        s = state(p)
        planned, d = check(
            p, s, outcome=WatchObservation(observed_at=T0 + timedelta(seconds=2), status_code=304),
        )
        self.assertEqual(
            planned.conditional_headers,
            (("If-None-Match", '"etag-a"'), ("If-Modified-Since", "Fri, 09 Oct 2026 10:00:00 GMT")),
        )
        self.assertEqual(d.disposition, "UNCHANGED")
        self.assertEqual(d.reason, "HTTP_304")
        self.assertEqual(d.children, ())
        self.assertEqual(d.next_state.content_sha256, SHA_A)
        self.assertEqual(d.next_state.last_attempted_at, T0)
        self.assertEqual(d.next_state.last_successful_observed_at, T0 + timedelta(seconds=2))
        self.assertEqual(d.next_state.revision, s.revision + 1)
        replay = plan_watch_poll(
            p, d.next_state, gate(p), attempt_id="poll-42", attempted_at=T0 + timedelta(seconds=3)
        )
        self.assertEqual(replay.reason, "ATTEMPT_ALREADY_RECORDED")

    def test_200_stable_bytes_and_changing_validator_is_unchanged(self):
        p = policy()
        _, d = check(
            p, state(p), outcome=response(etag='"etag-renewed"', last_modified=None),
        )
        self.assertEqual(d.disposition, "UNCHANGED")
        self.assertEqual(d.children, ())
        self.assertEqual(d.next_state.etag, '"etag-renewed"')
        self.assertIsNone(d.next_state.last_modified)

    def test_modified_content_proposes_one_source_bound_child_and_idempotent_resume(self):
        p = policy()
        s = state(p)
        changed = response(content_sha256=SHA_B, etag='"etag-b"', source_version="record-v2")
        plan1, d1 = check(p, s, outcome=changed)
        self.assertEqual(d1.disposition, "CHANGED")
        self.assertTrue(d1.needs_source_review)
        self.assertEqual(len(d1.children), 1)
        child = d1.children[0]
        self.assertEqual(child.stage, "SOURCE_REVALIDATION_REVIEW")
        self.assertEqual(child.previous_source_version, "record-v1")
        self.assertEqual(child.observed_source_version, "record-v2")
        self.assertEqual(child.corpus_id, p.corpus_id)
        self.assertEqual(child.corpus_cutoff, p.corpus_cutoff)
        self.assertEqual(child.source_family, p.source_family)
        self.assertEqual(child.policy_fingerprint, policy_fingerprint(p))
        self.assertEqual(
            check(p, s, outcome=changed)[1].children[0].work_key,
            child.work_key,
        )
        with self.assertRaisesRegex(ValueError, "PLAN_STALE"):
            reconcile_watch_observation(p, d1.next_state, gate(p), plan1, changed)
        _, duplicate = check(
            p, d1.next_state, at=T0 + timedelta(seconds=5), attempt_id="poll-43",
            outcome=replace(changed, observed_at=T0 + timedelta(seconds=8)),
        )
        self.assertEqual(duplicate.disposition, "UNCHANGED")
        self.assertEqual(duplicate.children, ())

    def test_same_bytes_new_explicit_source_version_requires_review(self):
        p = policy()
        _, result = check(
            p, state(p), outcome=response(source_version="record-v2", etag='"etag-b"'),
        )
        self.assertEqual(result.disposition, "CHANGED")
        self.assertEqual(result.children[0].observed_sha256, SHA_A)

    def test_200_older_last_modified_cannot_replace_newer_confirmed_source(self):
        p = policy()
        confirmed = state(
            p, content_sha256=SHA_B, source_version="record-v2",
            etag='"etag-b"', last_modified="Sat, 10 Oct 2026 10:00:00 GMT",
        )
        # Upstream serves an older body and validator after the newer version
        # was confirmed. This is not proof of a new amendment or freshness.
        _, result = check(p, confirmed, outcome=response())
        self.assertEqual(result.disposition, "UNAVAILABLE")
        self.assertEqual(result.reason, "LAST_MODIFIED_REGRESSED")
        self.assertEqual(result.children, ())
        self.assertTrue(result.needs_source_review)
        self.assertEqual(result.next_state.content_sha256, SHA_B)
        self.assertEqual(result.next_state.source_version, "record-v2")
        self.assertEqual(result.next_state.etag, '"etag-b"')
        self.assertEqual(result.next_state.last_modified, confirmed.last_modified)
        self.assertEqual(
            result.next_state.last_successful_observed_at,
            confirmed.last_successful_observed_at,
        )
        self.assertGreater(result.next_state.retry_not_before, T0)

        # A full 200 carrying the same verified body/version is a successful
        # unchanged check even when the server rewrites its validators.
        _, same_body = check(
            p, confirmed, outcome=response(
                content_sha256=SHA_B, source_version="record-v2", etag='"etag-new"',
            ),
        )
        self.assertEqual(same_body.disposition, "UNCHANGED")
        self.assertEqual(same_body.children, ())

    def test_first_200_requires_verifiable_sha_and_proposes_one_child(self):
        p = policy()
        s = WatchState(source_id=p.source_id)
        planned, result = check(p, s, outcome=response())
        self.assertEqual(planned.conditional_headers, ())
        self.assertEqual(result.disposition, "CHANGED")
        self.assertEqual(result.next_state.policy_fingerprint, policy_fingerprint(p))
        self.assertEqual(result.next_state.content_sha256, SHA_A)

    def test_initial_304_cannot_invent_success(self):
        p = policy()
        s = WatchState(source_id=p.source_id)
        _, result = check(
            p, s, outcome=WatchObservation(observed_at=T0, status_code=304),
        )
        self.assertEqual(result.reason, "INVALID_CONDITIONAL_304")
        self.assertIsNone(result.next_state.last_successful_observed_at)
        self.assertEqual(result.children, ())
        with self.assertRaisesRegex(ValueError, "UNSCOPED_HISTORY_INVALID"):
            plan_watch_poll(
                p, WatchState(source_id=p.source_id, revision=2), gate(p),
                attempt_id="bad-state", attempted_at=T0,
            )

    def test_malformed_304_with_inconsistent_validator_does_not_advance(self):
        p = policy()
        s = state(p)
        _, result = check(
            p, s, outcome=response(status_code=304, content_sha256=None,
                                   etag='"different"', source_version="record-v1"),
        )
        self.assertEqual(result.reason, "INVALID_CONDITIONAL_304")
        self.assertEqual(result.next_state.etag, s.etag)
        self.assertEqual(result.next_state.last_successful_observed_at, s.last_successful_observed_at)

    def test_unverified_200_and_stale_etag_with_new_bytes_block(self):
        p = policy()
        for outcome, code in (
            (response(content_sha256=None), "UNVERIFIED_200"),
            (response(content_sha256=SHA_B), "ETAG_CONTENT_CONFLICT"),
            (response(etag="bad newline\nheader"), "MALFORMED_OBSERVATION"),
        ):
            with self.subTest(code=code):
                _, d = check(p, state(p), outcome=outcome)
                self.assertEqual(d.reason, code)
                self.assertEqual(d.disposition, "UNAVAILABLE")
                self.assertEqual(d.children, ())
                self.assertEqual(d.next_state.content_sha256, SHA_A)

    def test_rate_limit_and_unavailable_are_source_local_backoff_and_no_fake_success(self):
        p = policy(base_backoff_seconds=10, max_backoff_seconds=120, circuit_after_failures=2)
        baseline = state(p)
        for code in (429, 503):
            with self.subTest(code=code):
                _, d = check(
                    p, baseline, outcome=response(status_code=code, content_sha256=None,
                                                retry_after_seconds=85),
                )
                self.assertEqual(d.reason, f"HTTP_{code}")
                self.assertEqual(d.children, ())
                self.assertEqual(d.next_state.last_successful_observed_at,
                                 baseline.last_successful_observed_at)
                self.assertGreaterEqual(d.next_state.retry_not_before, T0 + timedelta(seconds=87))
                self.assertEqual(
                    plan_watch_poll(
                        p, d.next_state, gate(p), attempt_id="early",
                        attempted_at=T0 + timedelta(seconds=3),
                    ).reason,
                    "SOURCE_BACKOFF",
                )
        _, first = check(
            p, baseline, outcome=WatchObservation(
                observed_at=T0 + timedelta(seconds=2), status_code=None, transport_error="TIMEOUT",
            ),
        )
        after = first.next_state
        self.assertEqual(after.consecutive_failures, 1)
        _, second = check(
            p, after, at=T0 + timedelta(minutes=3), attempt_id="poll-next",
            outcome=WatchObservation(
                observed_at=T0 + timedelta(minutes=3, seconds=1),
                status_code=503,
            ),
        )
        self.assertEqual(second.next_state.consecutive_failures, 2)
        self.assertGreaterEqual(
            second.next_state.retry_not_before,
            T0 + timedelta(minutes=3, seconds=20),
        )

    def test_readiness_denial_prevents_attempt_and_child_materialization(self):
        p = policy()
        cases = (
            ({"rights_status": "REVOKED"}, "RIGHTS_NOT_READY"),
            ({"capability_status": "ABSENT"}, "CAPABILITY_NOT_READY"),
            ({"budget_status": "CAPPED"}, "BUDGET_NOT_READY"),
            ({"remaining_children": 0}, "CAP_EXHAUSTED"),
            ({"source_id": "wrong"}, "GATE_SCOPE_MISMATCH"),
            ({"corpus_id": "other-corpus"}, "GATE_SCOPE_MISMATCH"),
            ({"rights_receipt": ""}, "RIGHTS_NOT_READY"),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                plan = plan_watch_poll(
                    p, state(p), gate(p, **overrides),
                    attempt_id="poll-42", attempted_at=T0,
                )
                self.assertFalse(plan.allowed)
                self.assertEqual(plan.reason, expected)
                self.assertEqual(plan.conditional_headers, ())

    def test_revoked_rights_or_cap_after_poll_preserves_old_version_for_resume(self):
        p = policy()
        s = state(p)
        changed = response(content_sha256=SHA_B, etag='"etag-b"', source_version="record-v2")
        for overrides, code in (
            ({"rights_status": "REVOKED"}, "RIGHTS_NOT_READY"),
            ({"budget_status": "CAPPED"}, "BUDGET_NOT_READY"),
            ({"capability_status": "MISSING"}, "CAPABILITY_NOT_READY"),
        ):
            with self.subTest(code=code):
                _, result = check(p, s, outcome=changed,
                                  after_gate=gate(p, **overrides))
                self.assertEqual(result.disposition, "BLOCKED")
                self.assertEqual(result.reason, code)
                self.assertEqual(result.children, ())
                self.assertEqual(result.next_state.content_sha256, SHA_A)
                self.assertEqual(result.next_state.source_version, "record-v1")
                _, resumed = check(
                    p, result.next_state, at=T0 + timedelta(seconds=10),
                    attempt_id="resume-after-gates",
                    outcome=replace(changed, observed_at=T0 + timedelta(seconds=12)),
                )
                self.assertEqual(resumed.disposition, "CHANGED")
                self.assertEqual(len(resumed.children), 1)

    def test_independent_source_failures_do_not_block_other_source(self):
        p1 = policy()
        p2 = policy(source_id="official:two", locator_id="official:two:feed")
        _, error = check(
            p1, state(p1), outcome=response(status_code=503, content_sha256=None),
        )
        _, healthy = check(
            p2, state(p2), outcome=response(content_sha256=SHA_B,
                                           source_version="record-v2", etag='"etag-b"'),
        )
        self.assertEqual(error.disposition, "UNAVAILABLE")
        self.assertEqual(healthy.disposition, "CHANGED")
        self.assertNotEqual(error.next_state.source_id, healthy.next_state.source_id)

    def test_policy_and_corpus_drift_fail_closed(self):
        p = policy()
        s = state(p)
        with self.assertRaisesRegex(ValueError, "POLICY_SCOPE_MISMATCH"):
            plan_watch_poll(
                replace(p, corpus_cutoff="2026-10-10"), s, gate(p),
                attempt_id="poll", attempted_at=T0,
            )
        with self.assertRaisesRegex(ValueError, "POLICY_SCOPE_MISMATCH"):
            plan_watch_poll(
                replace(p, policy_revision="r2"), s, gate(p),
                attempt_id="poll", attempted_at=T0,
            )

    def test_attempt_timestamps_and_observation_are_distinct(self):
        p = policy()
        s = state(p)
        future = response(observed_at=T0 + timedelta(minutes=5))
        _, d = check(p, s, outcome=future)
        self.assertEqual(d.next_state.last_attempted_at, T0)
        self.assertEqual(d.next_state.last_successful_observed_at, future.observed_at)
        with self.assertRaisesRegex(ValueError, "OBSERVATION_TIME_INVALID"):
            check(p, s, outcome=response(observed_at=T0 - timedelta(seconds=1)))
        self.assertEqual(
            plan_watch_poll(p, s, gate(p), attempt_id="new", attempted_at=T0 - timedelta(hours=2)).reason,
            "ATTEMPT_OUT_OF_ORDER",
        )
        self.assertEqual(
            plan_watch_poll(
                p, d.next_state, gate(p), attempt_id="overlapping",
                attempted_at=T0 + timedelta(minutes=2),
            ).reason,
            "ATTEMPT_OUT_OF_ORDER",
        )

    def test_invalid_policy_headers_and_forged_plan_fail_closed(self):
        p = policy()
        for bad in (
            replace(p, max_children=2),
            replace(p, base_backoff_seconds=0),
            replace(p, version="unknown-v0"),
        ):
            with self.assertRaises(ValueError):
                policy_fingerprint(bad)
        with self.assertRaisesRegex(ValueError, "WATCH_ETAG_INVALID"):
            plan_watch_poll(
                p, state(p, etag='"evil"\r\nX-Debug: yes'), gate(p),
                attempt_id="one", attempted_at=T0,
            )
        s = state(p)
        planned = plan_watch_poll(p, s, gate(p), attempt_id="one", attempted_at=T0)
        with self.assertRaisesRegex(ValueError, "PLAN_STALE_OR_UNAUTHORIZED"):
            reconcile_watch_observation(
                p, s, gate(p),
                replace(planned, conditional_headers=()), response(),
            )

    def test_forged_attempt_identity_and_clock_cannot_replay_or_regress_state(self):
        p = policy()
        s = state(p)
        planned = plan_watch_poll(p, s, gate(p), attempt_id="poll-42", attempted_at=T0)
        self.assertTrue(planned.allowed)
        for forged in (
            replace(planned, attempt_id=s.last_attempt_id),
            replace(planned, attempt_id="bad\nidentity"),
            replace(planned, attempted_at=s.last_attempted_at),
            replace(planned, attempted_at=T0.replace(tzinfo=None)),
        ):
            with self.subTest(forged=forged):
                with self.assertRaisesRegex(ValueError, "WATCH_PLAN_STALE_OR_UNAUTHORIZED"):
                    reconcile_watch_observation(p, s, gate(p), forged, response())
        # A forged plan can also skip a source-specific retry window.
        delayed = state(p, retry_not_before=T0 - timedelta(minutes=5))
        ready = plan_watch_poll(p, delayed, gate(p), attempt_id="ready", attempted_at=T0)
        self.assertTrue(ready.allowed)
        with self.assertRaisesRegex(ValueError, "WATCH_PLAN_STALE_OR_UNAUTHORIZED"):
            reconcile_watch_observation(
                p, delayed, gate(p),
                replace(ready, attempted_at=T0 - timedelta(minutes=6)), response(),
            )

    def test_200_missing_version_still_matches_existing_hash_version(self):
        p = policy()
        _, d = check(p, state(p), outcome=response(source_version=None))
        self.assertEqual(d.disposition, "UNCHANGED")
        self.assertEqual(d.next_state.source_version, "record-v1")

    def test_future_last_modified_cannot_create_false_freshness_or_poison_next_conditional_poll(self):
        p = policy()
        baseline = state(p)
        # If this future validator is accepted, the next If-Modified-Since
        # can suppress genuine upstream edits until 2035.
        future = "Mon, 01 Jan 2035 00:00:00 GMT"
        for outcome in (
            response(last_modified=future),
            response(content_sha256=SHA_B, source_version="record-v2",
                     etag='"etag-b"', last_modified=future),
        ):
            with self.subTest(outcome=outcome):
                _, result = check(p, baseline, outcome=outcome)
                self.assertEqual(result.disposition, "UNAVAILABLE")
                self.assertEqual(result.reason, "LAST_MODIFIED_IN_FUTURE")
                self.assertEqual(result.children, ())
                self.assertEqual(result.next_state.content_sha256, baseline.content_sha256)
                self.assertEqual(result.next_state.last_modified, baseline.last_modified)
                self.assertEqual(result.next_state.last_successful_observed_at,
                                 baseline.last_successful_observed_at)

        # A legacy persisted state must not emit a conditional request using
        # a Last-Modified timestamp later than its admitted observation.
        poisoned_state = state(p, last_modified=future)
        with self.assertRaisesRegex(ValueError, "WATCH_LAST_MODIFIED_AFTER_OBSERVATION"):
            plan_watch_poll(p, poisoned_state, gate(p),
                            attempted_at=T0, attempt_id="future-validator")

        # An old cache may lack a successful timestamp. A plan admitted after
        # its validator date cannot be moved backwards at reconciliation.
        missing_success = state(p, last_modified=future,
                                last_successful_observed_at=None)
        later = plan_watch_poll(p, missing_success, gate(p),
                                attempted_at=datetime(2036, 1, 1, tzinfo=timezone.utc),
                                attempt_id="later-conditional")
        self.assertTrue(later.allowed)
        with self.assertRaisesRegex(ValueError, "WATCH_PLAN_STALE_OR_UNAUTHORIZED"):
            reconcile_watch_observation(
                p, missing_success, gate(p), replace(later, attempted_at=T0),
                WatchObservation(observed_at=T0 + timedelta(seconds=2), status_code=304),
            )


if __name__ == "__main__":
    unittest.main()

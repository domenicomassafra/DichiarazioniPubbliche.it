#!/usr/bin/env python3
"""DP-515 bounded private watch rehearsal with authenticated Senate AKN versions.

Reuses the source/terms/rights verifier from DP-244 (#330), while the DP-515
SQLite ledger performs actual lease/restart/revocation. Old pinned bytes are
replayed as a simulated response, NOT observed as a live source change.
This has no PostgreSQL/queue/publication authority and meters no paid cost.
"""

from __future__ import annotations

import json
import sys
import sqlite3
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchObservation,
    WatchState,
)
from dichiarazioni_pubbliche.source_watch_store_v1 import LocalSourceWatchStore
from tools import dp244_refresh_cycle_canary as source


CURRENT_SHA = "1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476"
PREVIOUS_SHA = "6afe4c8a1ad2d32a85124ca379966adf7412bfd0894da432871c25f53cb80f14"


def permitted(url: str, readme_url: str, licence_id: str, now: datetime):
    body = source.fetch(readme_url)
    digest = source.sha(body)
    marker = f"CC BY {licence_id.rsplit('-', 1)[1]}"
    evidence = source.SourceTermsEvidence(
        terms_url=readme_url,
        terms_document_sha256=digest,
        terms_version=f"senato-open-data-readme-{digest[:16]}",
        licence_id=licence_id,
        licence_url=f"https://creativecommons.org/licenses/by/{licence_id.rsplit('-', 1)[1]}/",
        rightsholder="Senato della Repubblica",
        markers=(marker,) if marker in body.decode("utf-8", "replace") else (),
    )
    subject = source.RightsSubject(
        source_family=source.SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=url,
        content_id="senato-akn-leg19-01457617",
    )
    guard = source.guard_for(url, source.rights_record(subject, evidence, now))
    return guard, digest


def checked_fetch(guard, url: str, headers=()):
    guard.require("FETCH")
    reply = source.bounded_http_get(url, headers)
    guard.bind_fetched(final_url=reply.final_url)
    guard.require("FETCH")
    return reply


def observe(store, policy, guard, attempt_id, fetch):
    at = datetime.now(UTC)
    plan = store.begin_poll(policy.source_id, attempt_id=attempt_id, attempted_at=at)
    if not plan.allowed:
        raise AssertionError(f"DP515_CANARY_PLAN_HOLD:{plan.reason}")
    reply = fetch(plan.conditional_headers)
    if reply.final_url != policy.locator_id:
        raise AssertionError("DP515_CANARY_LOCATOR_MISMATCH")
    if reply.status_code != 200 and reply.body:
        raise AssertionError("DP515_CANARY_UNEXPECTED_ERROR_BODY")
    observation = WatchObservation(
        observed_at=datetime.now(UTC),
        status_code=reply.status_code,
        content_sha256=source.sha(reply.body) if reply.status_code == 200 else None,
        etag=reply.etag,
        last_modified=reply.last_modified,
        transport_error=reply.transport_error,
        retry_after_seconds=reply.retry_after_seconds,
    )
    result = store.commit_observation(
        policy.source_id, attempt_id=attempt_id, observation=observation,
    )
    return reply, observation, result


def main():
    now = datetime.now(UTC)
    current_guard, current_terms = permitted(
        source.CURRENT_URL, source.README_URL, "CC-BY-4.0", now,
    )
    previous_guard, previous_terms = permitted(
        source.PREVIOUS_URL, source.PREVIOUS_README_URL, "CC-BY-3.0", now,
    )
    missing_guard, _ = permitted(
        source.MISSING_URL, source.README_URL, "CC-BY-4.0", now,
    )
    # The historic locator is fetched only with its own current rights.
    previous = checked_fetch(previous_guard, source.PREVIOUS_URL)
    if previous.status_code != 200 or source.sha(previous.body) != PREVIOUS_SHA:
        raise AssertionError("DP515_CANARY_HISTORICAL_VERSION_MISMATCH")

    policy = source.policy_for(source.CURRENT_URL)
    gate = source.readiness(policy)  # Explicit isolated fixture only; not PG clearance.
    with tempfile.TemporaryDirectory(prefix="dp515-351-disposable-") as scratch:
        path = Path(scratch) / "watch.sqlite"
        conn = sqlite3.connect(path, isolation_level=None, timeout=3)
        store = LocalSourceWatchStore(conn)
        store.init_isolated_fixture_schema()
        store.register_fixture_source(policy, WatchState(policy.source_id), gate)

        current, _, first = observe(
            store, policy, current_guard, "dp515:current",
            lambda headers: checked_fetch(current_guard, source.CURRENT_URL, headers),
        )
        if current.status_code != 200 or source.sha(current.body) != CURRENT_SHA:
            raise AssertionError("DP515_CANARY_CURRENT_VERSION_MISMATCH")
        if first.disposition != "CHANGED":
            raise AssertionError("DP515_CANARY_BASELINE_MISSING")
        unchanged, _, second = observe(
            store, policy, current_guard, "dp515:unchanged",
            lambda headers: checked_fetch(current_guard, source.CURRENT_URL, headers),
        )
        if unchanged.status_code != 304 or second.disposition != "UNCHANGED":
            raise AssertionError("DP515_CANARY_REAL_304_MISSING")

        # Simulated 200 at the present locator carrying authentic old pinned bytes.
        replay, replay_observation, changed = observe(
            store, policy, current_guard, "dp515:historic-replay",
            lambda _: source.HttpResult(
                200, source.CURRENT_URL, previous.body, previous.etag, None,
            ),
        )
        if changed.disposition != "CHANGED" or not changed.needs_source_review:
            raise AssertionError("DP515_CANARY_HISTORICAL_REVIEW_MISSING")
        if source.sha(replay.body) != PREVIOUS_SHA:
            raise AssertionError("DP515_CANARY_REPLAY_HASH_MISMATCH")
        before = len(store.private_proposals(policy.source_id))
        conn.close()
        conn = sqlite3.connect(path, isolation_level=None, timeout=3)
        store = LocalSourceWatchStore(conn)
        if store.commit_observation(
            policy.source_id,
            attempt_id="dp515:historic-replay",
            observation=replay_observation,
        ) != changed:
            raise AssertionError("DP515_CANARY_DURABLE_REPLAY_CHANGED")
        if len(store.private_proposals(policy.source_id)) != before:
            raise AssertionError("DP515_CANARY_DUPLICATE_PROPOSAL")
        if before != 2:
            raise AssertionError("DP515_CANARY_PRIVATE_PROPOSALS_MISSING")

        missing_policy = replace(
            source.policy_for(source.MISSING_URL),
            source_id=f"{source.SOURCE_ID}:missing",
        )
        store.register_fixture_source(
            missing_policy,
            WatchState(missing_policy.source_id),
            source.readiness(missing_policy),
        )
        outage_reply, _, outage = observe(
            store, missing_policy, missing_guard, "dp515:outage",
            lambda headers: checked_fetch(missing_guard, source.MISSING_URL, headers),
        )
        if (outage_reply.status_code != 404 or outage.disposition != "UNAVAILABLE"
                or outage.children or outage.next_state.last_successful_observed_at):
            raise AssertionError("DP515_CANARY_OUTAGE_FRESHNESS_INVALID")
        cooldown = store.begin_poll(
            missing_policy.source_id,
            attempt_id="dp515:outage:too-early",
            attempted_at=datetime.now(UTC),
        )
        if cooldown.reason != "SOURCE_BACKOFF":
            raise AssertionError("DP515_CANARY_OUTAGE_BACKOFF_MISSING")

        store.update_fixture_readiness(
            replace(gate, rights_status="REVOKED"), expected_gate_revision=0,
        )
        if store.private_proposals(policy.source_id):
            raise AssertionError("DP515_CANARY_REVOKED_PROPOSAL_VISIBLE")
        revoked = store.begin_poll(
            policy.source_id, attempt_id="dp515:revoked",
            attempted_at=datetime.now(UTC),
        )
        if revoked.reason != "RIGHTS_NOT_READY":
            raise AssertionError("DP515_CANARY_REVOKED_POLL_ADMITTED")
        conn.close()

    print(json.dumps({
        "verdict": "PASS_PRIVATE_FIXTURE_ONLY",
        "source_id": policy.source_id,
        "source_family": source.SOURCE_FAMILY,
        "current_url": source.CURRENT_URL,
        "previous_url": source.PREVIOUS_URL,
        "current_commit": source.CURRENT_COMMIT,
        "previous_commit": source.PREVIOUS_COMMIT,
        "current_sha256": CURRENT_SHA,
        "previous_sha256": PREVIOUS_SHA,
        "current_readme_sha256": current_terms,
        "previous_readme_sha256": previous_terms,
        "rights": "PER_VERSION_LICENSE_ATTESTED_IN_MEMORY",
        "actual_current_statuses": [current.status_code, unchanged.status_code],
        "historical_change": "SIMULATED_200_WITH_AUTHENTIC_PINNED_BYTES",
        "dispositions": [first.disposition, second.disposition, changed.disposition],
        "outage_status": outage_reply.status_code,
        "outage_reason": outage.reason,
        "outage_retry": cooldown.reason,
        "restarted_replay": "IDENTICAL",
        "private_proposals_before_revocation": before,
        "private_proposals_after_revocation": 0,
        "revoked_poll": revoked.reason,
        "measured_cost_micro_eur": None,
        "postgres_queue_dispatch": "NOT_ATTEMPTED",
        "public_freshness": "HOLD",
        "consumer": "isolated_mac_studio_sqlite",
        "checked_at": datetime.now(UTC).isoformat(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

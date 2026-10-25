"""One authorized source watcher on the native PostgreSQL/held-review boundary.

No body is persisted, no paid provider is called, and no child is runnable.
The production CLI is pinned to the sole currently FETCH-cleared Senato locator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.dp244_conditional_probe import bounded_http_get
from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchObservation, WatchPolicy, WatchReadiness, WatchState, policy_fingerprint,
)
from dichiarazioni_pubbliche.source_watch_pg_queue_adapter import PostgresSourceWatchStore


SENATO_SOURCE = "source:senato-akn-leg19-01457617"
SENATO_LOCATOR = (
    "https://raw.githubusercontent.com/SenatoDellaRepubblica/AkomaNtosoBulkData/"
    "bfac144eb5c54820971bc1020fece11aae56ec90/"
    "Leg19/Atto00055187/resaula/01457617-ra.akn.xml"
)
CAPABILITY = "native:https-bounded-no-provider"
SUBSCRIPTION = "subscription:no-paid-provider"


def bootstrap_senato(store: PostgresSourceWatchStore) -> dict:
    """Register the exact pre-existing current FETCH right, with no new rights."""
    row = store.run(
        """SELECT json_build_object('content_id',c.id,
               'source_family',r.source_family,'rights_id',r.id)::text
           FROM content_item c JOIN private_source_rights_record r
             ON r.content_id=c.id AND r.locator_value=c.canonical_url
           WHERE c.source_id=:'source_id' AND c.canonical_url=:'locator'
             AND r.rights_status='CLEARED' AND r.locator_kind='URL'
             AND r.reviewed_at IS NOT NULL AND r.reviewed_at<=now()
             AND (r.expires_at IS NULL OR r.expires_at>now())
             AND r.permitted_uses @> ARRAY['FETCH']::text[]
             AND NOT EXISTS (
                 SELECT 1 FROM private_source_rights_record successor
                 WHERE successor.supersedes_id=r.id)
           ORDER BY r.reviewed_at DESC LIMIT 1""",
        source_id=SENATO_SOURCE, locator=SENATO_LOCATOR,
    )
    if not row:
        raise ValueError("WATCH_NATIVE_NO_CURRENT_FETCH_RIGHT")
    right = json.loads(row)
    policy = WatchPolicy(
        source_id=SENATO_SOURCE, locator_id=SENATO_LOCATOR,
        source_family=right["source_family"], corpus_id="corpus:leg19",
        corpus_cutoff="2026-12-31", policy_revision="dp515-native-senato-v1",
        enabled=True, max_children=1, base_backoff_seconds=300,
        max_backoff_seconds=21600,
    )
    gate = WatchReadiness(
        source_id=SENATO_SOURCE, policy_fingerprint=policy_fingerprint(policy),
        corpus_id=policy.corpus_id, rights_status="READY",
        rights_receipt=right["rights_id"], capability_status="READY",
        capability_receipt=CAPABILITY, budget_status="READY",
        budget_receipt=SUBSCRIPTION, remaining_children=1,
    )
    store.register_source(policy, WatchState(SENATO_SOURCE), gate,
                          content_id=right["content_id"])
    return {"status": "REGISTERED", "source_id": SENATO_SOURCE,
            "content_id": right["content_id"], "rights_id": right["rights_id"]}


def watch_once(store: PostgresSourceWatchStore, source_id: str, *,
               fetch=bounded_http_get, clock=None) -> dict:
    """Preflight in PG, one bounded conditional HTTPS GET, atomic CAS/queue."""
    now = clock or (lambda: datetime.now(UTC))
    policy, state, _, revision, _ = store._read_source(source_id)
    # Recover an expired lease for this source only, preserving CAS and gates.
    expired = store.run(
        """SELECT attempt_id FROM dp515_watch_attempt
           WHERE source_id=:'source_id' AND status='IN_FLIGHT'
             AND lease_expires_at<=clock_timestamp() LIMIT 1""",
        source_id=source_id,
    )
    if expired:
        store.expire_stale_attempt(
            source_id, attempt_id=expired, as_of=now(),
            expected_state_revision=state.revision, expected_gate_revision=revision,
        )
    started = now()
    attempt_id = "dp515:" + started.strftime("%Y%m%dT%H%M%S%f")
    plan = store.begin_poll(source_id, attempt_id=attempt_id,
                            attempted_at=started, lease_seconds=300)
    if not plan.allowed:
        return {"source_id": source_id, "disposition": "HOLD",
                "reason": plan.reason, "attempt_id": None}
    parsed = urlsplit(policy.locator_id)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise ValueError("WATCH_NATIVE_UNSAFE_LOCATOR")
    response = fetch(policy.locator_id, plan.conditional_headers)
    if response.final_url != policy.locator_id or (
            response.status_code != 200 and response.body):
        raise ValueError("WATCH_NATIVE_REDIRECT_OR_ERROR_BODY")
    observation = WatchObservation(
        observed_at=now(), status_code=response.status_code,
        content_sha256=(hashlib.sha256(response.body).hexdigest()
                        if response.status_code == 200 else None),
        etag=response.etag, last_modified=response.last_modified,
        transport_error=response.transport_error,
        retry_after_seconds=response.retry_after_seconds,
    )
    decision = store.commit_observation(
        source_id, attempt_id=attempt_id, observation=observation,
    )
    return {
        "source_id": source_id, "attempt_id": attempt_id,
        "disposition": decision.disposition, "reason": decision.reason,
        "state_revision": decision.next_state.revision,
        "source_sha256": decision.next_state.content_sha256,
        "review_jobs_proposed": len(decision.children),
        "review_jobs_state": "BLOCKED",
        "fetched_bytes": len(response.body),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true",
                        help="register the already-cleared Senato source once")
    args = parser.parse_args()
    if not os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"):
        parser.error("DICHIARAZIONI_PUBBLICHE_DATABASE_URL required")
    store = PostgresSourceWatchStore(os.environ["DICHIARAZIONI_PUBBLICHE_DATABASE_URL"])
    if args.bootstrap:
        result = bootstrap_senato(store)
    else:
        policy, *_ = store._read_source(SENATO_SOURCE)
        if policy.locator_id != SENATO_LOCATOR:
            raise ValueError("WATCH_NATIVE_SOURCE_NOT_PINNED")
        result = watch_once(store, SENATO_SOURCE)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

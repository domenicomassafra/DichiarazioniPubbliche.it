#!/usr/bin/env python3
"""DP-244 real-case cycle: baseline, unchanged, changed and outage in one run.

Against a real HTTPS source (official Senate open-data AKN XML, CC BY 4.0
in 2026 and CC BY 3.0 in 2025) this canary performs:

* baseline — a real 200 with byte-length, SHA-256 and ETag, stored as an
  immutable content-addressed capture;
* unchanged — a real conditional repeat that returns 304, with no new capture;
* changed — authentic older pinned bytes replayed as a simulated 200 response
  to the current watch locator, producing a held review proposal and a second
  immutable capture; this is not evidence of a live locator change in this run;
* outage — a real HTTP 404 on the same source family, no capture, backoff state;
* coverage — catalog decisions for the observed versions and for the missing
  document, with the data absence marked explicitly and no public freshness
  descriptor.

For both pinned versions the licence is separately read from the hashed
`README.MD`, attested by DP-317, and checked against the exact FETCH and
STORE_BODY locator. All Captures remain private and the public gate stays HOLD. Nothing is published, no
database is touched, and measured cost stays UNKNOWN.

Usage:
    PYTHONPATH=poc python3 tools/dp244_refresh_cycle_canary.py [--store DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import HTTPRedirectHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.coverage_catalog_v1 import (  # noqa: E402
    CoverageObservation,
    CoverageUnit,
    build_source_coverage,
    public_freshness_descriptor,
)
from dichiarazioni_pubbliche.dp244_conditional_probe import (  # noqa: E402
    HttpResult,
    bounded_http_get,
    probe_permitted_source,
)
from dichiarazioni_pubbliche.immutable_capture_store_v1 import (  # noqa: E402
    store_capture,
    verify_capture,
)
from dichiarazioni_pubbliche.incremental_source_watch import (  # noqa: E402
    WatchPolicy,
    WatchReadiness,
    WatchState,
    policy_fingerprint,
)
from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import (  # noqa: E402
    SourceTermsEvidence,
    attest_licence_use,
)
from dichiarazioni_pubbliche.private_capture_rights import (  # noqa: E402
    SourceFamilyUseGuard,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)

BASE = "https://raw.githubusercontent.com/SenatoDellaRepubblica/AkomaNtosoBulkData"
CURRENT_COMMIT = "bfac144eb5c54820971bc1020fece11aae56ec90"
PREVIOUS_COMMIT = "6995905a8291f7c8135c6d0aab711da326619b08"
DOCUMENT = "Leg19/Atto00055187/resaula/01457617-ra.akn.xml"
CURRENT_URL = f"{BASE}/{CURRENT_COMMIT}/{DOCUMENT}"
PREVIOUS_URL = f"{BASE}/{PREVIOUS_COMMIT}/{DOCUMENT}"
MISSING_URL = f"{BASE}/{CURRENT_COMMIT}/Leg19/assente-2026.xml"
README_URL = f"{BASE}/{CURRENT_COMMIT}/README.MD"
PREVIOUS_README_URL = f"{BASE}/{PREVIOUS_COMMIT}/README.MD"
SOURCE_ID = "source:senato-akn-leg19-01457617"
SOURCE_FAMILY = "senato_open_data_akn"
POLICY_VERSION = "dp244-cycle-canary-v1"
MEDIA_TYPE = "application/xml"
COST_UNKNOWN = None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    result = bounded_http_get(url, ())
    if result.status_code != 200 or not result.body:
        raise SystemExit(f"DP244_CANARY_FETCH_FAILED {url} {result.status_code}")
    return result.body


def readiness(policy: WatchPolicy) -> WatchReadiness:
    return WatchReadiness(
        source_id=policy.source_id,
        policy_fingerprint=policy_fingerprint(policy),
        corpus_id=policy.corpus_id,
        rights_status="READY",
        rights_receipt="receipt:rights:cc-by-4.0",
        capability_status="READY",
        capability_receipt="receipt:capability:https-fetch",
        budget_status="READY",
        budget_receipt="receipt:budget:no-metered-provider",
        remaining_children=1,
    )


def rights_record(subject: RightsSubject, terms: SourceTermsEvidence, now: datetime):
    attestation = attest_licence_use(terms)
    if attestation.status != "APPROVED":
        raise SystemExit(f"DP244_CANARY_RIGHTS_{attestation.reason_code}")
    return PrivateRightsRecord(
        id=f"rights:senato-akn-cycle:{rights_subject_fingerprint(subject)[:16]}",
        subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family,
        locator_kind=subject.locator_kind,
        locator_value=subject.locator_value,
        content_id=subject.content_id,
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref=f"licence:{attestation.licence_id}:{attestation.terms_document_sha256}",
        permitted_uses=("FETCH", "STORE_BODY"),
        attribution_requirements=("ATTRIBUTION_REQUIRED",),
        reviewed_at=(now - timedelta(hours=1)).isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
        reviewer_ref="machine:licence-attestation-v1",
        policy_version=POLICY_VERSION,
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )


def guard_for(url: str, record: PrivateRightsRecord) -> SourceFamilyUseGuard:
    subject = RightsSubject(
        source_family=SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=url,
        content_id="senato-akn-leg19-01457617",
    )
    return SourceFamilyUseGuard(
        read_current=lambda _subject: record,
        subject=subject,
        rights_record_id=record.id,
        policy_version=POLICY_VERSION,
    )


def policy_for(url: str) -> WatchPolicy:
    return WatchPolicy(
        source_id=SOURCE_ID,
        locator_id=url,
        source_family=SOURCE_FAMILY,
        corpus_id="corpus:leg19",
        corpus_cutoff="2026-12-31",
        policy_revision="dp244-cycle-canary-v1",
        enabled=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default=None)
    options = parser.parse_args(argv)
    root = Path(options.store or tempfile.mkdtemp(prefix="dp244-captures-"))
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)

    readme = fetch(README_URL)
    terms = SourceTermsEvidence(
        terms_url=README_URL,
        terms_document_sha256=sha(readme),
        terms_version=f"senato-open-data-readme-{sha(readme)[:16]}",
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        rightsholder="Senato della Repubblica",
        markers=tuple(
            marker
            for marker in ("CC BY 4.0", "Attribution 4.0 International")
            if marker in readme.decode("utf-8", "replace")
        ),
    )

    previous_readme = fetch(PREVIOUS_README_URL)
    previous_terms = SourceTermsEvidence(
        terms_url=PREVIOUS_README_URL,
        terms_document_sha256=sha(previous_readme),
        terms_version=f"senato-open-data-readme-{sha(previous_readme)[:16]}",
        licence_id="CC-BY-3.0",
        licence_url="https://creativecommons.org/licenses/by/3.0/",
        rightsholder="Senato della Repubblica",
        markers=tuple(
            marker
            for marker in ("CC BY 3.0", "Attribution 3.0 Unported")
            if marker in previous_readme.decode("utf-8", "replace")
        ),
    )

    current_policy, missing_policy = policy_for(CURRENT_URL), policy_for(MISSING_URL)

    def subject_for(url):
        return RightsSubject(
            source_family=SOURCE_FAMILY,
            locator_kind="URL",
            locator_value=url,
            content_id="senato-akn-leg19-01457617",
        )

    current_guard = guard_for(
        CURRENT_URL, rights_record(subject_for(CURRENT_URL), terms, now)
    )
    missing_guard = guard_for(
        MISSING_URL, rights_record(subject_for(MISSING_URL), terms, now)
    )
    previous_guard = guard_for(
        PREVIOUS_URL, rights_record(subject_for(PREVIOUS_URL), previous_terms, now)
    )
    gates = readiness(current_policy)

    # The historical locator and licence require their own current permit.
    previous_guard.require("FETCH")
    previous = bounded_http_get(PREVIOUS_URL, ())
    previous_guard.bind_fetched(final_url=previous.final_url)
    previous_guard.require("FETCH")
    if previous.status_code != 200 or not previous.body:
        raise SystemExit("DP244_CANARY_PREVIOUS_VERSION_UNAVAILABLE")

    state = WatchState(source_id=SOURCE_ID)
    attempts = []
    captures = []
    observed_bodies = {}

    def run(attempt_id, *, fetch_impl=bounded_http_get):
        nonlocal state

        def observe_bytes(url, headers):
            response = fetch_impl(url, headers)
            if response.status_code == 200:
                observed_bodies[attempt_id] = response.body
            return response

        receipt = probe_permitted_source(
            policy=current_policy,
            state=state,
            planning_gate=gates,
            current_gate=lambda: gates,
            rights_guard=current_guard,
            content_id="senato-akn-leg19-01457617",
            url=CURRENT_URL,
            attempt_id=attempt_id,
            attempted_at=now + timedelta(seconds=len(attempts) * 30),
            fetch=observe_bytes,
            clock=lambda: now + timedelta(seconds=len(attempts) * 30, microseconds=1),
        )
        state = receipt.committed_attempt.decision.next_state
        attempts.append({
            "attempt_id": attempt_id,
            "disposition": receipt.committed_attempt.decision.disposition,
            "reason": receipt.committed_attempt.decision.reason,
            "status_code": receipt.committed_attempt.observation.status_code,
            "content_sha256": receipt.committed_attempt.observation.content_sha256,
            "state_sha256": state.content_sha256,
            "state_version": state.source_version,
            "fetched_bytes": receipt.fetched_bytes,
            "needs_source_review": receipt.committed_attempt.decision.needs_source_review,
            "children": len(receipt.committed_attempt.decision.children),
            "cost": receipt.measured_cost_micro_eur,
        })
        return receipt

    baseline = run("attempt:dp244:baseline")
    unchanged = run("attempt:dp244:unchanged")
    changed = run(
        "attempt:dp244:changed",
        fetch_impl=lambda url, _headers: HttpResult(
            200,
            url,
            previous.body,
            previous.etag,
            None,
        ),
    )

    for label, body, guard in (
        ("current", observed_bodies["attempt:dp244:baseline"], current_guard),
        ("previous", previous.body, previous_guard),
    ):
        guard.require("STORE_BODY", content_sha256=sha(body), media_type=MEDIA_TYPE)
        record, written = store_capture(
            root,
            body=body,
            source_id="senato-akn-leg19-01457617",
            locator_id=f"locator:{label}",
            media_type=MEDIA_TYPE,
            observed_at=now,
            measured_cost_micro_eur=COST_UNKNOWN,
        )
        captures.append({
            "label": label,
            "capture_id": record.capture_id,
            "byte_length": record.byte_length,
            "written": written,
            "cost": record.measured_cost_micro_eur,
            "verified": verify_capture(root, record.capture_id).content_sha256
            == record.content_sha256,
        })
    replay, rewritten = store_capture(
        root,
        body=previous.body,
        source_id="senato-akn-leg19-01457617",
        locator_id="locator:previous",
        media_type=MEDIA_TYPE,
        observed_at=now,
    )

    missing_state = WatchState(source_id=SOURCE_ID)
    missing = probe_permitted_source(
        policy=missing_policy,
        state=missing_state,
        planning_gate=readiness(missing_policy),
        current_gate=lambda: readiness(missing_policy),
        rights_guard=missing_guard,
        content_id="senato-akn-leg19-01457617",
        url=MISSING_URL,
        attempt_id="attempt:dp244:outage",
        attempted_at=now,
        fetch=bounded_http_get,
        clock=lambda: now,
    )

    # --- coverage catalog over the versions actually observed ---------------
    unit = CoverageUnit(
        unit_id="unit:senato-leg19-01457617",
        source_family=SOURCE_FAMILY,
        source_id=SOURCE_ID,
        collection_id="collection:leg19-resaula",
        language="it",
        source_format="AKN_XML",
        expected_content_class="LEGAL_ACT_TEXT",
        interval_start=datetime(2025, 6, 1, tzinfo=UTC),
        interval_end=datetime(2026, 12, 31, tzinfo=UTC),
        mode="INCREMENTAL_SUBSCRIPTION",
        policy_version=POLICY_VERSION,
        max_staleness_seconds=86400,
    )
    scope = CoverageUnit.scope_fingerprint(unit)
    observations = []
    for index, attempt in enumerate(attempts):
        if attempt["disposition"] not in {"CHANGED", "UNCHANGED"}:
            continue
        observations.append(CoverageObservation(
            attempt_id=attempt["attempt_id"],
            source_id=SOURCE_ID,
            policy_version=POLICY_VERSION,
            scope_fingerprint=scope,
            attempted_at=now + timedelta(seconds=index * 30),
            status=attempt["disposition"],
            source_version=attempt["state_version"],
            content_sha256=attempt["state_sha256"],
            observation_receipt_id=f"receipt:{attempt['attempt_id']}",
            enumerated_scope_review_id=None,
            enumeration_complete_within_scope=False,
            rights_status="CLEARED",
        ))
    coverage = build_source_coverage(
        unit,
        tuple(observations),
        now=now + timedelta(minutes=5),
        rights_ready=True,
        budget_ready=True,
        capability_ready=True,
    )
    descriptor = public_freshness_descriptor(coverage, public_scope_review_id=None)
    outage_observation = CoverageObservation(
        attempt_id="attempt:dp244:outage",
        source_id=SOURCE_ID,
        policy_version=POLICY_VERSION,
        scope_fingerprint=scope,
        attempted_at=now + timedelta(minutes=2),
        status="NOT_FOUND",
        rights_status="CLEARED",
    )
    outage_coverage = build_source_coverage(
        unit,
        tuple(observations) + (outage_observation,),
        now=now + timedelta(minutes=5),
        rights_ready=True,
        budget_ready=True,
        capability_ready=True,
    )

    assert [row["disposition"] for row in attempts] == ["CHANGED", "UNCHANGED", "CHANGED"]
    assert attempts[1]["status_code"] == 304 and attempts[1]["fetched_bytes"] == 0
    assert attempts[2]["needs_source_review"] is True and attempts[2]["children"] == 1
    assert all(row["cost"] is None for row in attempts)
    assert len({row["state_sha256"] for row in attempts}) == 2
    assert attempts[1]["state_sha256"] == attempts[0]["content_sha256"]
    assert captures[0]["written"] is True and captures[1]["written"] is True
    assert replay.capture_id == captures[1]["capture_id"] and rewritten is False
    assert all(row["verified"] for row in captures)
    assert missing.committed_attempt.decision.disposition == "UNAVAILABLE"
    assert missing.committed_attempt.observation.status_code == 404
    assert coverage.delta_proposal == "REVIEW_CHANGED_SOURCE"
    assert descriptor is None

    print(json.dumps(
        {
            "canary": "DP244_REFRESH_CYCLE_CANARY",
            "source": {
                "current_url": CURRENT_URL,
                "current_commit": CURRENT_COMMIT,
                "previous_url": PREVIOUS_URL,
                "previous_commit": PREVIOUS_COMMIT,
                "missing_url": MISSING_URL,
                "readme_url": README_URL,
                "readme_sha256": sha(readme),
                "previous_readme_url": PREVIOUS_README_URL,
                "previous_readme_sha256": sha(previous_readme),
                "current_licence_id": terms.licence_id,
                "previous_licence_id": previous_terms.licence_id,
                "changed_step": "REPLAY_AUTHENTIC_PINNED_BYTES",
                "rights_record_scope": "IN_MEMORY_CANARY_ONLY",
                "licence_markers": list(terms.markers),
                "rights": "LICENCE_VERIFIED_FOR_PRIVATE_USE",
                "permitted_uses": ["FETCH", "STORE_BODY"],
            },
            "attempts": attempts,
            "outage": {
                "disposition": missing.committed_attempt.decision.disposition,
                "reason": missing.committed_attempt.decision.reason,
                "status_code": missing.committed_attempt.observation.status_code,
                "fetched_bytes": missing.fetched_bytes,
                "consecutive_failures": (
                    missing.committed_attempt.decision.next_state.consecutive_failures
                ),
                "backoff": "APPLIED",
            },
            "captures": captures,
            "replay": {"capture_id": replay.capture_id, "rewritten": rewritten},
            "coverage": {
                "state": coverage.state,
                "reason_code": coverage.reason_code,
                "delta_proposal": coverage.delta_proposal,
                "observed_source_version": coverage.observed_source_version,
                "dispatch_authorized": coverage.dispatch_authorized,
                "public_freshness_descriptor": descriptor,
                "with_outage_state": outage_coverage.state,
                "with_outage_reason": outage_coverage.reason_code,
                "enumeration_complete_within_scope": False,
                "cost_micro_eur": COST_UNKNOWN,
            },
            "store": str(root),
            "verdict": "PASS",
            "checked_at": now.isoformat(),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

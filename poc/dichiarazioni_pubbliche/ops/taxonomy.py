"""Health and error taxonomy for Dichiarazioni Pubbliche (DP-504).

One table that answers the only question a 3am operator has: *given this
state, what do I do, and what must I not do?*

Pure by construction. It maps existing vocabulary -- ``error_category`` output
from ``health_digest``, ``processing_job.state`` values, ``source_health.status``
values, and the SLO statuses from ``ops/slo`` -- onto owner, action, and the
product invariants that make certain "fixes" forbidden. The "forbidden
remedies" field is not decoration: several of the most tempting 3am reflexes
in this system (switch model, lower the bar, regenerate the projection) are
precisely the ones that turn an outage into a permanent correctness bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


# --- Existing vocabularies, mirrored as literals so the taxonomy can be
# validated against the runtime without importing the runtime.

JOB_STATES = (
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "RETRYING",
    "DEFERRED",
    "BLOCKED",
    "DEAD_LETTER",
)

SOURCE_HEALTH_STATES = ("HEALTHY", "DEGRADED", "FAILED", "UNKNOWN")

SEVERITIES = ("INFO", "NOTICE", "WARNING", "CRITICAL", "OUTAGE")

# Blocker categories the runtime actually emits. Kept explicit so a new
# category shows up as a taxonomy gap rather than as an unowned alert.
KNOWN_BLOCKER_CATEGORIES = (
    "OMNIROUTE_API_KEY_MISSING",
    "OMNIROUTE_HTTP",
    "GROQ_API_KEY_MISSING",
    "ASR",
    "CLAIM_EXTRACTION_CREDENTIAL_MISSING",
    "CLAIM_EXTRACTION_COST_MODEL_MISSING",
    "CLAIM_EXTRACTION_CANARY_FAILED",
    "CLAIM_EXTRACT",
    "EVIDENCE",
    "TRANSCRIPT",
    "SOURCE",
    "COST",
    "BUDGET",
    "RATE",
    "RUNTIME",
    "PROVIDER",
    "NO_HANDLER",
    "OTHER",
)


@dataclass(frozen=True)
class TaxonomyEntry:
    state: str
    severity: str
    meaning: str
    operator_action: str
    forbidden_remedies: tuple[str, ...]
    invariants: tuple[str, ...]
    page: bool


def _entry(
    state: str,
    severity: str,
    meaning: str,
    action: str,
    forbidden: tuple[str, ...],
    invariants: tuple[str, ...],
    page: bool,
) -> TaxonomyEntry:
    return TaxonomyEntry(
        state=state,
        severity=severity,
        meaning=meaning,
        operator_action=action,
        forbidden_remedies=forbidden,
        invariants=invariants,
        page=page,
    )


_NO_DOWNGRADE = (
    "Do not switch provider or model to unblock the queue.",
    "Do not lower validation thresholds or accept partial model output.",
    "Do not hand-edit the database to move a job to COMPLETED.",
)

_NO_FABRICATION = (
    "Do not fabricate, reconstruct, or regenerate a provider receipt.",
    "Do not publish a dossier that has not passed the projection gate.",
)


ENTRIES: tuple[TaxonomyEntry, ...] = (
    # --- Queue job states --------------------------------------------------
    _entry(
        "QUEUED",
        "INFO",
        "Executable work waiting for a worker pass.",
        "None. This is the normal resting state of the queue.",
        (),
        (),
        False,
    ),
    _entry(
        "RUNNING",
        "NOTICE",
        "A worker holds a lease on this job.",
        (
            "None immediately. If RUNNING persists longer than the lease "
            "seconds, the reaper will return it; if it persists across several "
            "reaper cycles, check for a wedged worker process."
        ),
        ("Do not delete or force-complete a RUNNING job; let the lease expire.",),
        ("Each stage persists enough provenance to reproduce its output.",),
        False,
    ),
    _entry(
        "COMPLETED",
        "INFO",
        "The stage ran to its deterministic conclusion.",
        "None.",
        (),
        (),
        False,
    ),
    _entry(
        "RETRYING",
        "NOTICE",
        "Transient failure; the worker will retry with exponential backoff.",
        (
            "None while the attempt count stays below max_attempts. Watch the "
            "trend, not the individual job."
        ),
        ("Do not reset attempt counters to suppress the retry signal.",),
        (),
        False,
    ),
    _entry(
        "DEFERRED",
        "WARNING",
        (
            "Work is executable but deliberately postponed: budget cap reached, "
            "provider rate limit, or upstream 429."
        ),
        (
            "Read the DEFERRED reason category. If it is a budget or rate "
            "category, the system is behaving as designed and will resume by "
            "itself after the window rolls; take no action."
        ),
        _NO_DOWNGRADE,
        ("Budget caps fail closed.",),
        False,
    ),
    _entry(
        "BLOCKED",
        "WARNING",
        (
            "A precondition that the operator controls is missing: a credential, "
            "a cost model, a passing canary, a registered source, or provenance."
        ),
        (
            "Read the BLOCKED reason category and act on that category only "
            "(see the blocker table). BLOCKED is terminal for the current "
            "configuration and will not self-heal."
        ),
        _NO_DOWNGRADE + _NO_FABRICATION,
        (
            "Provider failure is an explicit blocked state.",
            "Do not materialize downstream child jobs when the downstream "
            "capability is unavailable.",
        ),
        False,
    ),
    _entry(
        "DEAD_LETTER",
        "CRITICAL",
        (
            "A job exhausted its retries. The system has stopped pretending it "
            "can make progress unattended."
        ),
        (
            "Identify the job type and its last error, fix the underlying cause, "
            "then requeue deliberately from the review/admin surface. Do not "
            "bulk-requeue dead letters."
        ),
        _NO_DOWNGRADE,
        (
            "Provider failure is an explicit blocked state.",
            "A job is never silently dropped; exhaustion is reported, not hidden.",
        ),
        True,
    ),
    # --- Source health -----------------------------------------------------
    _entry(
        "HEALTHY",
        "INFO",
        "The source polled successfully within its cadence.",
        "None.",
        (),
        (),
        False,
    ),
    _entry(
        "DEGRADED",
        "WARNING",
        "Consecutive failures are backing off, but the source still works.",
        (
            "Check whether the failure is network, adapter, or the upstream "
            "platform changing its markup. Unrelated sources continue meanwhile."
        ),
        ("Do not disable the source to make the digest green.",),
        ("Broken source adapter degrades one source, not the system.",),
        False,
    ),
    _entry(
        "FAILED",
        "CRITICAL",
        "The source has exhausted its backoff and is not producing content.",
        (
            "Confirm the upstream source is still live and still permitted. If "
            "it is gone, retire it in the registry explicitly rather than "
            "leaving it in permanent failure."
        ),
        ("Do not silently drop a failing source from the registry.",),
        ("Broken source adapter degrades one source, not the system.",),
        True,
    ),
    # --- Blocked-job reason categories -------------------------------------
    _entry(
        "OMNIROUTE_API_KEY_MISSING",
        "WARNING",
        "No claim-extraction credential is configured for the worker.",
        (
            "Expected in the current runtime. Leave the jobs BLOCKED. When a "
            "credential becomes available, configure it and run the claim canary "
            "before unblocking anything."
        ),
        _NO_DOWNGRADE,
        ("Provider failure is an explicit blocked state.",),
        False,
    ),
    _entry(
        "OMNIROUTE_HTTP",
        "CRITICAL",
        "The claim route is reachable but rejects or fails real requests.",
        (
            "Treat as an upstream provider fault. Leave jobs BLOCKED and check "
            "whether the official runtime artifact has been superseded; do not "
            "substitute a different route or model."
        ),
        _NO_DOWNGRADE,
        ("Provider failure is an explicit blocked state.",),
        True,
    ),
    _entry(
        "GROQ_API_KEY_MISSING",
        "WARNING",
        "No ASR credential; audio-source content cannot be transcribed.",
        "Expected in the current runtime. Leave the jobs BLOCKED.",
        _NO_DOWNGRADE,
        ("Provider failure is an explicit blocked state.",),
        False,
    ),
    _entry(
        "CLAIM_EXTRACTION_CANARY_FAILED",
        "CRITICAL",
        "The non-trivial canary on the claim route did not pass.",
        (
            "This gate is the reason the pipeline is not silently producing bad "
            "claims. Leave claim fan-out disabled and report the canary result."
        ),
        _NO_DOWNGRADE,
        ("Fail closed under uncertainty, missing provenance, provider failure.",),
        True,
    ),
    _entry(
        "CLAIM_EXTRACTION_COST_MODEL_MISSING",
        "WARNING",
        "No explicit per-1k-token cost ceiling is configured for claim extraction.",
        (
            "Configure DICHIARAZIONI_PUBBLICHE_CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS explicitly. "
            "Zero is allowed only after verifying genuinely zero marginal cost."
        ),
        ("Do not set a cost model to an arbitrarily large value to unblock work.",),
        ("Budget caps fail closed.",),
        False,
    ),
    _entry(
        "COST",
        "NOTICE",
        "A budget cap was reached; paid lanes are deferred, not dropped.",
        "None. Verify the cap value is intentional and let the window roll.",
        ("Do not raise the cap to clear a backlog without a cost decision.",),
        ("Budget caps fail closed.",),
        False,
    ),
    _entry(
        "EVIDENCE",
        "WARNING",
        "Evidence acquisition failed for policy, rate, or transport reasons.",
        (
            "Check the source-specific category. A blocked evidence fetch is a "
            "correct outcome when policy refuses the URL; never substitute an "
            "unfetched URL for the refused one."
        ),
        (
            "Never record an evidence URL as fetched when it was not.",
            "Never widen the host/path allowlist at 3am to unblock a fetch.",
        ),
        ("Evidence URLs must be validated by code, not invented.",),
        False,
    ),
    _entry(
        "TRANSCRIPT",
        "WARNING",
        "A transcript could not be resolved, reconciled, or attributed.",
        (
            "Uncertain transcript content must remain publication_blocked. "
            "Resolve by adding an independent second transcription, never by "
            "editing canonical segment text."
        ),
        ("Do not edit canonical transcript text to unblock a claim.",),
        ("Fail closed under uncertainty, missing provenance.",),
        False,
    ),
    _entry(
        "SOURCE",
        "WARNING",
        "A source, platform copy, or locator is unavailable or unsupported.",
        (
            "An access-restricted upstream copy (for example members-only) is a "
            "correct terminal state. Do not attempt to work around an "
            "entitlement."
        ),
        ("Do not attempt to bypass an access restriction.",),
        (),
        False,
    ),
    # --- SLO statuses ------------------------------------------------------
    _entry(
        "SLO_OK",
        "INFO",
        "Measured value is within its objective.",
        "None.",
        (),
        (),
        False,
    ),
    _entry(
        "SLO_AT_RISK",
        "NOTICE",
        "Measured value is past 75% of the way to breaching its objective.",
        (
            "No page. Review during the daily digest; if the trend continues it "
            "will breach on its own."
        ),
        (),
        (),
        False,
    ),
    _entry(
        "SLO_UNKNOWN",
        "WARNING",
        "A required measurement was not available to the collector.",
        (
            "The collector or the underlying query is broken, not the product. "
            "Fix the measurement before trusting any green status."
        ),
        ("Do not treat UNKNOWN as OK.",),
        ("Fail closed under uncertainty.",),
        False,
    ),
    _entry(
        "SLO_BREACH",
        "CRITICAL",
        "A measured value exceeded its objective.",
        "Follow the SLO's own action field in the digest.",
        (),
        ("SLOs are objectives, not publication gates.",),
        True,
    ),
    # --- Source health fallback -------------------------------------------
    _entry(
        "UNKNOWN",
        "WARNING",
        "Source health could not be determined.",
        (
            "Treat an unmeasurable source as unhealthy until a probe proves "
            "otherwise. Fix the probe before trusting any green source."
        ),
        ("Do not treat an unmeasured source as healthy.",),
        ("Fail closed under uncertainty.",),
        False,
    ),
    # --- Declared blocker families lacking their own entry ----------------
    _entry(
        "ASR",
        "WARNING",
        "Speech recognition is unavailable or rejected the audio.",
        (
            "Keep the source in DEFERRED. Retry after the credential or "
            "provider recovers; the deterministic fallback path stays open."
        ),
        (
            "Do not fabricate a transcript to keep a job moving.",
            "Do not publish from an untranscribed source.",
        ),
        ("No publication without a resolved transcript.",),
        False,
    ),
    _entry(
        "CLAIM_EXTRACT",
        "WARNING",
        "Claim extraction produced nothing usable for the window.",
        (
            "Re-run the extraction window with the configured model. An empty "
            "extraction is a valid observation, not a finding."
        ),
        (
            "Do not hand-write claims to fill an empty extraction.",
            "Do not lower the schema-constrained extraction threshold.",
        ),
        ("Claims come from extraction, never from operator authorship.",),
        False,
    ),
    _entry(
        "CLAIM_EXTRACTION_CREDENTIAL_MISSING",
        "WARNING",
        "The claim-extraction provider credential is absent.",
        (
            "Provision the credential. Until then extraction stays blocked and "
            "the dependent jobs stay DEFERRED."
        ),
        ("Do not switch provider or model to unblock extraction.",),
        ("Provider failure is a blocked state, not a quality change.",),
        False,
    ),
    _entry(
        "OTHER",
        "NOTICE",
        "A blocker the taxonomy does not yet own.",
        (
            "Triage the raw category and add a taxonomy entry for it. An "
            "unrecognised blocker is visible on purpose; do not silence it."
        ),
        ("Do not drop an unrecognised blocker to quiet the digest.",),
        ("Fail closed under uncertainty.",),
        False,
    ),
)


def get(state: str) -> TaxonomyEntry:
    for entry in ENTRIES:
        if entry.state == state:
            return entry
    raise KeyError(state)


def classify_blocker_category(category: str) -> TaxonomyEntry:
    """Map an ``error_category`` string onto a taxonomy entry.

    Unknown categories deliberately fall back to ``OTHER`` semantics rather
    than being dropped, so a newly emitted blocker is always visible.
    """
    key = str(category or "OTHER").strip() or "OTHER"
    if key in {entry.state for entry in ENTRIES}:
        return get(key)
    for entry in ENTRIES:
        if entry.state in KNOWN_BLOCKER_CATEGORIES and key.startswith(entry.state):
            return entry
    return get("OTHER")


def classify_source_status(status: str) -> TaxonomyEntry:
    key = str(status or "UNKNOWN").strip().upper() or "UNKNOWN"
    if key in {entry.state for entry in ENTRIES}:
        return get(key)
    return get("UNKNOWN")


def actionable(blockers: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Turn raw digest blockers into operator-ready, de-duplicated actions.

    ``blockers`` is the ``health_digest`` blockers list: ``{"category", "count"}``.
    Output rows are ordered by severity then count, and repeated categories are
    merged, so the operator sees one line per distinct cause rather than one
    line per job. That merge is the single most important noise control in the
    system: 1,467 identical blocked children are one operator action, not 1,467
    alerts.
    """
    merged: dict[str, int] = {}
    for row in blockers or ():
        key = str(row.get("category") or "OTHER")
        merged[key] = merged.get(key, 0) + int(row.get("count") or 0)

    order = {"OUTAGE": 0, "CRITICAL": 1, "WARNING": 2, "NOTICE": 3, "INFO": 4}
    out = []
    for category, count in merged.items():
        entry = classify_blocker_category(category)
        out.append(
            {
                "category": category,
                "count": count,
                "severity": entry.severity,
                "meaning": entry.meaning,
                "operator_action": entry.operator_action,
                "forbidden_remedies": list(entry.forbidden_remedies),
                "page": entry.page,
            }
        )
    out.sort(key=lambda row: (order.get(row["severity"], 99), -row["count"], row["category"]))
    return tuple(out)


def validate_taxonomy(entries: tuple[TaxonomyEntry, ...] = ENTRIES) -> tuple[str, ...]:
    """Structural self-check; empty tuple means the taxonomy is coherent."""
    defects: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.state in seen:
            defects.append(f"duplicate_state:{entry.state}")
        seen.add(entry.state)
        if entry.severity not in SEVERITIES:
            defects.append(f"{entry.state}:unknown_severity:{entry.severity}")
        if not entry.meaning:
            defects.append(f"{entry.state}:no_meaning")
        if not entry.operator_action:
            defects.append(f"{entry.state}:no_action")
        for job_state in JOB_STATES:
            pass  # coverage asserted below, not per-entry
        if not entry.invariants and entry.severity in {"CRITICAL", "OUTAGE"}:
            defects.append(f"{entry.state}:critical_without_invariant")
    covered = {entry.state for entry in entries}
    for job_state in JOB_STATES:
        if job_state not in covered:
            defects.append(f"uncovered_job_state:{job_state}")
    for source_state in SOURCE_HEALTH_STATES:
        if source_state not in covered:
            defects.append(f"uncovered_source_state:{source_state}")
    for slo_status in ("SLO_OK", "SLO_AT_RISK", "SLO_UNKNOWN", "SLO_BREACH"):
        if slo_status not in covered:
            defects.append(f"uncovered_slo_status:{slo_status}")
    return tuple(defects)

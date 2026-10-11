# DP-319 — Indagine attiva dei casi dubbi con coda minima

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-213, DP-215, DP-225, DP-228

## Problem
 Mettere `PENDING` o `QUEUED_FOR_HUMAN_REVIEW` non risolve dubbi su originalità, speaker, quote, chronology, evidence. Niente review testuale umana ordinaria e nessun budget infinito; un'assenza di risultati da corpus incompleto non è una prova negativa.

## Outcome
 Per ogni blocker preciso, un `InvestigationAttemptLedger` privato e deduplicato pianifica/risolve ricerche ammesse per fonte, stop condition e budget e produce `RESOLVED`, `CHECKED_INSUFFICIENT`, `CONFLICT`, `EXHAUSTED`, `WAIT_EXTERNAL` + residual reason, escalation piccola/rapida solo se deve decidere un owner/qualified authority.

## Traceability & constraints
 R23/R12/R13/Q9/Q14, forte autonomia. Nessun provider switch/paid canary automatico fuori policy.

## Scope
 Typed question (speaker, original, date, rights, contextual speech, primary evidence, jurisdiction, version) → ordered plan using DP-228, DP-225, archive alternative, long-form scene, official metadata, captions/ASR alternatives where permitted → approved source/resolution and refusal receipts → dedup/version+attempt budget → terminal outcome, read-only Studio oversight and reopen signal on new source. Research success alone **non** grants review/rights/publication. Collapsing dependent source copies prevents false independent corroboration.

## Non-goals
 Endless scraping, collecting unauthorised corpora, empty queue success, blocking every case until owner edits every paragraph.

## Dependencies and sequencing
 Source access permits from A and measured cost/cap from D; negative unavailable authority gets external question to owner/legal with exact scope, no retry loop. Existing DP-228 research-plan compiler reused.

## Acceptance criteria

- [ ] `AC-319.1`: All actionable hold codes map to a concrete question, allowed source/attempt family, cap/time/stop reason; unresolved external legal authority never recast as completed factual check.
- [ ] `AC-319.2`: Replay of identical source and plan never repeats cost-bearing attempt; new relevant version can reopen one bounded attempt, old receipt preserved.
- [ ] `AC-319.3`: Failure after original/full-context/official/independent-source alternatives records coverage and `CHECKED_INSUFFICIENT` or `EXHAUSTED` distinct from `NOT_CHECKED`; never labels false by search absence.
- [ ] `AC-319.4`: Real closed case has source→hash→reason→downstream proof and leaves exception queue; genuine legal/visual/identity edge receives one limited owner task with evidence and no false reviewer availability.
- [ ] `AC-319.5`: Provider outage, cost cap, revoked rights and stale plan block new child tasks and mark resumable state; D ledger reconciles exact consumed work.

## Validation / proof
 Simulated retries, changed sources, sourced independently vs mirrors, budget exhaustion, qualified-owner blocking; future MiniPC replay receipts from real authorized sources.
## Documentation, data, and migration impact
 Append-only attempt/counter receipts referencing existing discovery/coverage source tables, no parallel scheduler.
## Completion receipt
 The earlier planning-only receipt is superseded only for the narrow offline slice below.

## 2026-10-11 — Private bounded attempt planner (partial)

New `investigation_attempts_v1.py` consumes existing `ResearchAssignment`
objects and exact `CoverageNeed`/material versions to propose one deterministic,
deduplicated, budget- and rights-gated private attempt **without executing it**.
Receipts distinguish `WAIT_EXTERNAL` (outage, permission, cost/capability),
`CHECKED_INSUFFICIENT`, `EXHAUSTED` and `RESOLVED_PRIVATE_CANDIDATE`; absence
does not produce a negative factual verdict, one copied lineage is not
independent corroboration and a source-version change reopens only the new
bounded scope. Existing adapter IDs are required: no fabricated URL or query.
Offline focused tests cover idempotent replay and conflict, material freshness,
reviewed source hash and unknown-rights negative cases. No MiniPC job queue,
atomic Postgres ledger, real researcher/owner review, source fetch or provider
cost has been accepted. **No original DP-319 acceptance criterion is fully
closed**; this is source-only, with all public and real investigation gates held.

## 2026-10-11 — Readiness and immutable plan-scope hardening

The source-only preflight previously treated a nonempty string such as
`budget_ready="false"` or `capability_ready="false"` as truthy, which could
issue `READY_PRIVATE_PROPOSAL` without actual Boolean gate approval.
Further, an attempt-ID fingerprint omitted the exact investigation question,
attempt maximum and monetary ceiling. Identically identified attempts could
therefore be replayed under a different question or budget policy.

The RED regression reported **5 failures** across these cases. The preflight
now rejects non-Boolean readiness values with
`INVESTIGATION_READINESS_INVALID` and binds those plan dimensions in the
deterministic fingerprint; a changed plan yields a different attempt ID
rather than silently replaying an old cost-bearing decision. **13/13** focused
tests GREEN, scoped Ruff and diff-check PASS. This only constructs a private
proposal: the actual worker must check durable budget, grants and current
rights against a real transaction; no source fetch or cost was performed.
Real queue and MiniPC run remain absent; **all AC-319.1–.5 stay unchecked,
ticket IN PROGRESS**.

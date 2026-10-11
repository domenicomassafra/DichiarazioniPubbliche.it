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

## 2026-10-12 — Append-only private SQLite source/version and attempt receipts

The new opt-in `investigation_attempts_store_v1.py` stores one separately
supplied **local** source/Content candidate registration per Coverage Need:
exact `source_id`, `candidate_id`, `source_version`, source SHA-256, material
fingerprint, rights, use policy and monotonic registry revision. Source epoch
rows are append-only with a revision CAS; `reserve`, `complete`, `read` and
process restart revalidate the latest independently registered local record.
Revoked/expired rights, blocked policy, changed source hash, foreign candidate,
stale material/version and a stale registry revision cannot silently create
new work or complete old attempts. Restoring a previous version or changing
the associated source/candidate ID is not treated as same-source continuity.

The existing `investigation_attempts_v1.py` pure planner is reused verbatim.
Its canonical fingerprint and proposed attempt ID are checked at registration
and reconstructed for every stored reservation against earlier completed
observations. SQLite persists immutable private `RESERVED` and `COMPLETED`
events, with an exact plan, assignment/lane, material version, source and
candidate binding, idempotency key and attempt checksum. `BEGIN IMMEDIATE`,
event uniqueness and an atomic revision CAS ensure two independent writers
cannot reserve the same proposed attempt twice. An unfinished reservation
remains `WAIT_EXTERNAL / INVESTIGATION_UNCONFIRMED_RESERVATION` across restart:
even when its actual external effects are unknown, it **cannot be reissued**
automatically. Only a matching first terminal observation, recorded append-only
within original caps and provenance, changes the state. Identical replay is
read-only; a different result, foreign assignment or forged attempt is refused.
Newer relevant material receives its own attempt scope; earlier receipts remain
available through explicit historical readback. `resume` reconstructs the
original persisted plan from a fingerprint in a separate Python interpreter.

The private ledger deliberately refuses caller-claimed
`REVIEWED_SOURCE_CANDIDATE` and invented source-review event authority, because
no independently verified real reviewer/source authorization is connected.
`NO_MATCH`, `SOURCE_INCONCLUSIVE`, `OUTAGE` and similar negative/blocked
observations remain private status observations, not factual disproof. The
reported `spent_usd` is checked against the specific ResearchAssignment and
plan cap but is **not an independently reconciled D billing record**. Source
registration itself requires a trusted upstream local source/rights/policy
record supplied by the caller; the SHA/checksum protects local consistency,
not authenticity of that record. Nothing here fetches, dispatches, publishes,
spends money or adds a PostgreSQL production migration.

New `tests/test_dp319_durable_investigation_next.py` covers **11/11** real
temporary SQLite cases including restart in a fresh Python interpreter,
simultaneous writers, append-only trigger enforcement, tampered/rehashed
attempt refusal, simulated transaction failure after INSERT but before CAS
with full rollback, cross-Content-candidate/source version mismatch, a source
rights revocation *between* reservation and completion, rights/policy epoch
freshness, OUTAGE replan, bounded cost, exhaustion with no false evidence
conclusion, and independent new-version recovery with old history preserved.
Tests first failed with missing durable implementation (RED), then GREEN;
full focused-plus-adjacent DP-319/DP-241/DP-228/research/coverage suite
**88/88 PASS**, scoped Ruff lint/format, targeted `compileall` and
`git diff --check` PASS on Mac.

**No original `AC-319.1–.5` is marked complete.** A real authorized source
registry, D provider/cost execution receipts, checked baseline coverage,
MiniPC persisted replay, trusted human/qualified authority and downstream
case lifecycle remain unproved. `IN PROGRESS`; release **NO-GO**.

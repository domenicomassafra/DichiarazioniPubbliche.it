# Architecture Deepening Review — 2026-09-22

Ticket: DP-003
Method: module depth, locality, leverage, adapter seams, deletion test, test surface.

## Executive result

The current system does **not** justify a greenfield rewrite. Several modules are already
deep and should be protected. Two areas show real architectural friction and should be
refactored only after the M1 domain/schema contracts settle:

1. the persistence surface concentrated in `QueueRuntimeStore`;
2. the job-domain handlers concentrated in `ProcessingWorker`.

The security-critical public projection is large but deep: its small interface hides a
large publication-policy implementation. Splitting it by file size would make locality
worse, not better.

## Candidate A — Deepen PostgreSQL persistence modules

Recommendation: **Strong, sequenced after M1 schema convergence**.

### Files

- `poc/dichiarazioni_pubbliche/queue_runtime.py`
- consumers in `worker_daemon.py`, `review_admin.py`, `health_digest.py`
- relevant queue/runtime/review tests

### Problem

`QueueRuntimeStore` is about 2,400 lines and exposes one class for unrelated domains:

- queue lease/retry/defer/block;
- person and speaker review;
- content/locators;
- transcripts/canonical segments;
- claims;
- evidence and observations;
- verification/findings/relations;
- reanalysis;
- reply/correction publication;
- provider receipts and cost snapshots.

This is not merely a large implementation behind a small interface. The interface itself
is broad, so understanding or changing one domain requires navigating unrelated SQL
contracts. That is poor locality and a divergent-change smell.

### Deletion test

Deleting the class would not concentrate complexity into a simpler place; its many
responsibilities would simply spill into callers. The useful abstraction is not
"database access" as one module but several domain-persistence modules sharing one
PostgreSQL execution primitive.

### Direction

After M1 settles the domain schema, group persistence by responsibility, for example:

```text
Postgres runtime primitive
  ├─ JobQueueStore
  ├─ TranscriptStore
  ├─ ClaimEvidenceStore
  └─ ReviewPublicationStore
```

These are concrete modules, not speculative backend interfaces. Do **not** add protocol/
repository abstractions until a second persistence implementation creates a real seam.

### Benefits

- SQL invariants live beside the domain that owns them;
- review/publication code stops sharing a huge mutation surface with ordinary queue work;
- focused tests can instantiate the smallest relevant store;
- future schema migrations touch fewer unrelated call sites;
- lower cognitive load for contributors and coding agents.

### Risk

Doing this before DP-101..DP-106 would create churn because the schema vocabulary is
about to converge. Therefore architecture says **refactor later, not rewrite now**.

## Candidate B — Separate worker orchestration from domain job handlers

Recommendation: **Strong after Candidate A**.

### Files

- `poc/dichiarazioni_pubbliche/worker_daemon.py`
- domain runtime modules used by its handlers
- `tests/test_worker_daemon.py`

### Problem

`ProcessingWorker` is about 1,700 lines. It is simultaneously:

- the queue runner;
- budget/preflight logic;
- transcript resolver/caption/ASR handler;
- canonicalization handler;
- claim-window and extraction handler;
- evidence fetch/query/persist handler;
- verification/relation/reanalysis handler;
- job-type dispatcher.

The `process()` dispatch is a valid orchestration seam. The problem is that all handler
implementations live on the same class, so adding a job in one domain edits the same
module as unrelated domains. This produces divergent change and weak locality.

### Direction

Keep a small queue runner/dispatcher and move cohesive job families behind deep handler
modules, likely:

```text
ProcessingWorker
  └─ dispatch(job)
       ├─ TranscriptJobs
       ├─ ClaimEvidenceJobs
       └─ VerificationReviewJobs
```

Handlers should use the narrowed persistence modules from Candidate A. Avoid one class per
job type; that would replace one monolith with shallow indirection.

### Benefits

- one domain feature changes one handler module;
- unit tests can exercise job families without constructing the entire worker;
- queue execution/retry semantics become easier to review independently from domain work;
- provider adapters remain replaceable without changing the queue engine.

## Candidate C — Keep the public projection deep

Recommendation: **Keep; harden contract, do not split by responsibility**.

### Files

- `poc/dichiarazioni_pubbliche/public_projection.py`
- `tests/test_public_projection.py`

### Observation

`PublicProjectionStore` has one major public operation, `projectable_findings`, backed by
a large SQL query. The rest of the module sanitizes and renders a bounded public bundle.
The interface is much smaller than the implementation: this is the shape of a deep
module.

The large query centralizes cross-domain publication invariants: speaker provenance,
evidence/review lineage, transcript freshness, correction/reply policy, and verification
consistency. Scattering those checks across repositories would weaken locality at the
most security-sensitive boundary.

### Improvement instead of split

- formalize public schema v1 in DP-105;
- maintain adversarial projection tests;
- consider moving the SQL text to a versioned resource only if readability improves
  without separating the invariants from the projection module;
- keep one fail-closed projection entry point.

## Candidate D — Keep evidence runtime and deterministic verifier cohesive

Recommendation: **Keep**.

`evidence_runtime.py` already has meaningful deep classes (`EvidenceCache`,
`SafeEvidenceFetcher`, persistent rate limiter) around a clear network trust boundary.
`verification_runtime.py` is a cohesive set of deterministic rules and immutable-ish
input/output records. Splitting either further today would mostly add interfaces without
new leverage.

## Candidate E — Keep review CLI thin; narrow its store later

Recommendation: **Worth improving only as a consequence of Candidate A**.

`review_admin.py` is not the core architectural problem. Its functions are bounded CLI/
application operations and already delegate persistence. Once review/publication SQL is
owned by a narrow store, the CLI benefits automatically. A separate rewrite adds little.

## Before / after system shape

### Current

```text
CLI / scheduler / worker / projection
          |        |         |
          |    ProcessingWorker (many domains)
          |        |
          +------ QueueRuntimeStore (almost all PostgreSQL mutations)
                   |
                PostgreSQL

PublicProjectionStore (separate, deep publication read boundary)
```

### Target after domain convergence

```text
Scheduler ---- JobQueueStore
                    |
Small ProcessingWorker dispatcher
  |        |        |
  v        v        v
Transcript  Claim+Evidence  Verification+Review job modules
  |        |        |
  v        v        v
TranscriptStore  ClaimEvidenceStore  ReviewPublicationStore
          \          |          /
             shared PostgreSQL primitive

PublicProjectionStore  <--- remains one deep, fail-closed read boundary
```

## Decision

Do not rewrite the application. Preserve the working domain modules and public projection.
First stabilize M1 contracts, then perform two bounded structural refactors with behavior-
preserving tests and MiniPC acceptance.

This review creates two follow-up tickets: DP-107 and DP-108.

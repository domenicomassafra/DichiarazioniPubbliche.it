# DP-108 — Separate worker orchestration from domain job handlers

Status: IN PROGRESS
Milestone: M1  
Depends on: DP-107

## Problem

`ProcessingWorker` owns queue execution plus implementations for transcript, claims,
evidence, verification, relations, reanalysis, and ASR job families.

## Outcome

Keep a small worker/dispatcher and move cohesive job families into a few deep handler
modules backed by DP-107's narrowed stores.

## Acceptance criteria

- queue claim/renew/retry/defer/block semantics stay centralized and unchanged;
- transcript/ASR jobs are one cohesive handler family;
- claim/evidence jobs are one cohesive handler family;
- verification/relation/reanalysis jobs are one cohesive handler family;
- no one-class-per-job shallow architecture;
- focused handler tests plus full suite/benchmark pass;
- production queue behavior and cost/block semantics unchanged on MiniPC.

## Non-goals

Microservices, a new queue product, provider changes, or schema redesign.

## Preparatory tranche — 2026-10-05

`worker_dispatch.py` now defines a closed, immutable catalog for the 14 job types handled
by the current `ProcessingWorker.process` chain. Each entry points to the existing
`ProcessingWorker` handler callable and carries explicit deep-family and capability
metadata. The three families are transcript/ASR, claim/evidence, and
verification/relation/reanalysis; aliases such as `CLAIM_PREPARE` and `CLAIM_EXTRACT`
share the same existing callable rather than duplicating business logic.

The dispatch boundary rejects unregistered job types with `NO_HANDLER:<job_type>` before
handler invocation. Contract tests also prove that dispatch itself does not perform queue
claim/renew/retry/defer/block/complete, budget preflight, content lookup, or completion
finalization; those orchestration responsibilities remain outside the registered handler
set, matching the current worker ordering.

Local proof on the shared checkout: the new dispatch contract suite passes 6/6, including
automatic parity with the job-type comparisons in the current `ProcessingWorker.process`;
the existing worker suite passes 21/21. Full `compileall` over `poc`/`tests` and
`git diff --check` also pass.

This is preparatory DP-108 work only. `worker_daemon.py` and its tests have concurrent
changes, so the production `process` caller is not migrated in this tranche. DP-107 is
also still in progress. Production integration, deep handler-module moves, full-suite /
benchmark proof, and MiniPC queue acceptance remain open acceptance work.

## Production caller and handler integration — 2026-10-06

The current production worker now uses the dispatch boundary. `ProcessingWorker.process`
keeps content lookup and budget enforcement in the orchestrator, then calls
`dispatch_processing_worker_job`; an unregistered job type still becomes a fail-closed
`BlockedJob`. `ProcessingWorker.run` continues to own queue claim, lease recovery,
retry/defer/block/complete transitions, and claim-content completion finalization, so handler
extraction does not move queue lifecycle semantics into domain code.

The 14 registered jobs now live in exactly three cohesive handler modules:
`TranscriptAsrJobHandlers`, `ClaimEvidenceJobHandlers`, and
`VerificationRelationReanalysisJobHandlers`. `worker_daemon.py` has been reduced to worker
construction and orchestration dependencies. The dispatch contract verifies catalog parity,
deep-family ownership, fail-closed unknown jobs, and that dispatch itself performs no queue or
budget orchestration.

The provider-downgrade security invariant moved with the claim handler instead of remaining as
a stale source-code anchor in the orchestrator. The threat register and regression matrix now
point at `worker_handlers_claim_evidence.py`, where `_claim_runtime_blocker` emits
`CLAIM_EXTRACTION_CANARY_FAILED`. A behavioral worker test proves an unhealthy claim canary
produces a blocked job with zero extraction calls and zero claim-window fan-out; no fallback
provider/model path is introduced.

Local proof: the combined operation-ledger/store/runtime/dispatch/worker/threat matrix passes
**83/83**, `python3 -m compileall -q poc tests` passes, benchmark passes **5/5**, and
`git diff --check` passes. The repository-wide run executed **1705** tests and exposed the same
two integration failures described in DP-107; the DP-107/108-related operation-ledger source
assertion is now fixed and passes, while the independently reproducible restore-inventory
failure belongs to concurrent schema/ops work.

DP-108 remains **IN PROGRESS** pending a green repository-wide integration run after that
external restore inventory is reconciled and the required MiniPC production queue/cost/block
acceptance. No provider or MiniPC evidence is inferred from local mocks.

## Metadata-only scheduler compatibility — 2026-10-06

The MiniPC health read-back exposed two historical `CONTENT_TRIAGE` jobs blocked as
`NO_HANDLER:CONTENT_TRIAGE`. This was a real scheduler/dispatcher compatibility gap: DP-206
intentionally schedules `CONTENT_TRIAGE` for `DISCOVERY_ONLY` creator metadata, while the
initial DP-108 closed catalog covered only the 14 job types from the old worker branch chain.

`CONTENT_TRIAGE` is now the fifteenth registered job and remains inside the existing
ingestion/transcript deep family rather than creating a fourth shallow handler family. Its
handler accepts only `ingest_action=DISCOVERY_ONLY`, performs no network/provider/transcript/
claim work, preserves the content's `DISCOVERED` processing state, and records only bounded
metadata that the metadata-only triage completed. Any other action fails closed.

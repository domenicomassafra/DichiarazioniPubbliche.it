# DP-109 — Governed collection-readiness command and audit report

Status: DONE
Milestone: M1  
Depends on: DP-101..DP-108

## Problem

Before kicking off data collection, operators must know whether every stage of the pipeline
is ready to run or blocked by missing credentials, unavailable provider runtimes, or unconfigured
components. Without a deterministic, fail-closed check, workers risk spinning, failing jobs,
or running child fan-outs when prerequisite capabilities (e.g. claim extraction DP-201..203,
remote ASR DP-204) are absent.

## Outcome

Provide a pure, governed collection-readiness report and CLI entry point that evaluates
the readiness of all pipeline stages from a small closed status vocabulary:
`READY`, `BLOCKED_EXTERNAL`, `DEFERRED`, and `UNCONFIGURED`.

The report must fail closed: unknown capabilities or missing configurations yield
`BLOCKED_EXTERNAL` or `UNCONFIGURED`, never `READY`. Missing prerequisite capabilities
name their exact next action and must not imply downstream child work can run.

## Acceptance criteria

- Pure function evaluates bounded configuration, capability flags, and queue status counts;
- Small closed status set: `READY`, `BLOCKED_EXTERNAL`, `DEFERRED`, `UNCONFIGURED`;
- No network calls, provider calls, or DB writes;
- Fail-closed behavior on unknown capability or missing source/config;
- Missing remote ASR credential reports `BLOCKED_EXTERNAL` naming DP-204 next action;
- Missing claim extraction capability reports `BLOCKED_EXTERNAL` naming DP-201 next action and does not imply downstream child jobs may run;
- Deterministic human-readable report and machine-readable output across calls;
- CLI entry point exits non-zero whenever any stage is not `READY`.

## Implementation receipt

- Implemented pure readiness evaluator `evaluate_collection_readiness` in `poc/dichiarazioni_pubbliche/collection_readiness.py`.
- Defined closed status vocabulary: `READY`, `BLOCKED_EXTERNAL`, `DEFERRED`, `UNCONFIGURED`.
- Evaluates pipeline stages: `SOURCE_DISCOVERY`, `TRANSCRIPT_ACQUISITION`, `REMOTE_ASR`, `CLAIM_EXTRACTION`, `EVIDENCE_RETRIEVAL`, `DETERMINISTIC_VERIFICATION`, `RELATION_ANALYSIS`, and `PUBLIC_PROJECTION`.
- Emits explicit blocking reasons and actionable next actions (specifically referencing DP-204 for ASR, DP-201 for claim extraction).
- CLI entry point prints deterministic table/report and exits 1 if any stage is not READY.
- Unit test suite in `tests/test_collection_readiness.py` covering all acceptance criteria.

## Closure receipt — 2026-09-27

- The focused readiness suite passes 7/7 on both the Mac source authority and the
  MiniPC runtime mirror.
- The current report remains fail-closed for the real external provider blockers:
  missing/failed claim-extraction capability and remote-ASR capability are not promoted
  to READY merely because deterministic repository tests pass.
- No provider, network, database-write, or production-queue action is required by this
  command; its result is a governed readiness report, exactly as scoped by this ticket.

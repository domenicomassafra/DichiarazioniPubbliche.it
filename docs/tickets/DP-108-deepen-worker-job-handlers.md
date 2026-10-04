# DP-108 — Separate worker orchestration from domain job handlers

Status: FUTURE  
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

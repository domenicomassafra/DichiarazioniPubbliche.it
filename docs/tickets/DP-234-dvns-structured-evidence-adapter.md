# DP-234 — DVNS/read-only structured evidence adapter

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-215, DP-228; external source contract/API availability

## Problem

The DVNS sister-platform audit identified useful structured-source patterns: explicit
provenance dates, source policy, zero-vs-missing semantics, fail-closed refresh and
generated-artifact receipts. The AGPL repository is not a default code donor, and
Dichiarazioni Pubbliche currently has no direct read-only adapter for any future approved
DVNS data/API contract.

## Outcome

Define and implement a narrow provider-neutral structured-evidence adapter that can consume
approved DVNS-style records through an API/export/shared permissive schema without
importing the sister application's runtime or AGPL source code into this core.

## Acceptance criteria

- [x] Provider-neutral contract distinguishes PRESENT numeric zero from MISSING and
  NOT_APPLICABLE states.
- [x] Publication date, reference period, observed-at and effective interval remain
  separate fields.
- [x] Every normalized value retains HTTPS source URL, source record ID/version,
  deterministic adapter record ID and bounded provider receipt.
- [ ] DP-215 source role/authority scope determines what the record can establish.
- [x] Provider/source BLOCKED/FAILED/DEGRADED states require an explicit blocker and cannot
  carry records or masquerade as empty-success evidence.
- [x] Unsupported schema version is rejected fail closed.
- [x] The normalized record contract contains no approval, assessment or verdict field;
  existing Evidence/Observation review remains downstream authority.
- [x] No AGPL implementation code is copied into the permissively licensed core; this is an
  independently implemented provider-neutral contract.
- [ ] Wire an approved DVNS/API/export provider into this contract and DP-228/DP-215.
- [ ] Add source-specific schema/rights mapping under an
  explicit compatible licensing decision.
- [ ] MiniPC canary is required before any production source family uses the adapter.

## Completion receipt

Provider-neutral structured-evidence contract + focused tests added 2026-10-05. A real
DVNS/API/export integration remains blocked on an approved external/shared contract and
source-specific rights/schema review.

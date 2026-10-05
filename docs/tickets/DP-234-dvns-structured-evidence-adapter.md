# DP-234 — DVNS/read-only structured evidence adapter

Status: FUTURE
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

- [ ] Adapter contract distinguishes value zero from missing/null/not-applicable.
- [ ] Publication date, reference period, observed-at and effective date remain separate.
- [ ] Every structured value retains source URL/record ID/version and retrieval receipt.
- [ ] DP-215 source role/authority scope determines what the record can establish.
- [ ] Provider/source outage yields BLOCKED/degraded state, never empty-success evidence.
- [ ] Schema drift is detected and fails closed before observations are approved.
- [ ] Existing evidence/observation review remains mandatory; adapter output is only a
  candidate input.
- [ ] No AGPL implementation code is copied into the permissively licensed core without an
  explicit compatible licensing decision.
- [ ] MiniPC canary is required before any production source family uses the adapter.

## Completion receipt

Blocked on an approved external/shared contract; architecture is intentionally read-only.

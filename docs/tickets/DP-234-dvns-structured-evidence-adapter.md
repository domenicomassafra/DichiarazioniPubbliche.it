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
- [x] DP-215 source role/authority scope determines what the record can establish.
- [x] Provider/source BLOCKED/FAILED/DEGRADED states require an explicit blocker and cannot
  carry records or masquerade as empty-success evidence.
- [x] Unsupported schema version is rejected fail closed.
- [x] The normalized record contract contains no approval, assessment or verdict field;
  existing Evidence/Observation review remains downstream authority.
- [x] No AGPL implementation code is copied into the permissively licensed core; this is an
  independently implemented provider-neutral contract.
- [x] A pure/offline DVNS-style adapter seam preserves stable external IDs, source/schema
  versions, exact field selectors, HTTPS source URLs and opaque rights/availability status;
  explicitly private input fields are excluded from normalized records, receipts and replay
  identity.
- [x] Replay identity is deterministic and input-order independent; exact duplicate records
  collapse, while conflicting content under the same stable record identity, schema drift and
  unknown public/provenance fields fail closed.
- [x] The DVNS-style seam is read-only and candidate-only: it has no upstream write/fetch
  client, rejects verdict/publication-authority input fields and cannot confer publication
  authority.
- [ ] Wire an approved DVNS/API/export provider into this contract and DP-228/DP-215.
- [ ] Add source-specific schema/rights mapping under an
  explicit compatible licensing decision.
- [ ] MiniPC canary is required before any production source family uses the adapter.

## Completion receipt

Provider-neutral structured-evidence contract plus a synthetic, offline DVNS-style adapter
fixture and focused replay/provenance/privacy tests added 2026-10-05. The adapter input schema
is an internal seam, not a claim about the current DVNS API/export schema. A real DVNS/API/export
integration remains blocked on an approved external/shared contract, compatible licensing,
source-specific rights/schema review and MiniPC canary.

DP-215 bridge proof 2026-10-06: a pure candidate-only suitability bridge binds each imported
record to an explicit `SourceProfile`, granted evidence role and exact `AuthorityScope`; imported
self-declared roles cannot grant authority. Exact metric/unit/dimension, authority-scope,
reference-period, publication-cutoff and effective-interval compatibility are retained as
pre-assessment metadata. `BLOCKED`/`FAILED`/`DEGRADED` fetch, rights, availability or profile
access state holds the candidate before compatibility is evaluated. The bridge contains no
verdict, approval, publication, network or database authority. Focused bridge tests: **7/7 PASS**;
DVNS/structured-evidence/DP-215 regression set: **44/44 PASS**; `compileall` and `git diff --check`
PASS. Complete shared suite: **1552/1552 PASS**; deterministic benchmark: **5/5 PASS**.

Final dependency-free runtime proof on 2026-10-06 runs the provider-neutral structured-evidence,
offline DVNS import and DP-215 suitability bridge as **26/26 PASS** in an isolated MiniPC
`/tmp` bundle with production/provider credentials removed. This proves the current seam on the
runtime authority but closes none of the three external ACs: there is still no approved
DVNS/API/export provider wired into DP-228/DP-215, no source-specific compatible-license/rights
decision, and therefore no production source family on which a meaningful MiniPC provider
canary can run. The synthetic contract remains candidate-only and confers no source approval.

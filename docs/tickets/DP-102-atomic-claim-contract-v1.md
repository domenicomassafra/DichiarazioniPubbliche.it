# DP-102 — Atomic Claim contract v1

Status: DONE
Milestone: M1
Depends on: M0

## Problem

Claim-type vocabulary exists across config, docs, SQL, fixtures, and extractor output and
needs one authoritative contract before a stable API exists.

## Outcome

Define Atomic Claim v1: identity, normalized proposition, original-segment provenance,
speaker requirements, temporal scope, claim type, check-worthiness, and extraction
metadata.

## Acceptance criteria

- one canonical claim-type enumeration and semantics;
- schema/config/runtime/tests use the same vocabulary;
- opinion/rhetoric/non-checkable content cannot accidentally enter factual verification;
- temporal scope rules are machine-testable;
- claim identity/replay rules remain idempotent and do not widen provenance;
- public-safe claim representation is documented.

## Runtime proof

MiniPC migration/compatibility proof if persistent schema changes.

## Implementation receipt — 2026-09-24

- Added the canonical Python claim-type registry and Atomic Claim v1 validator.
- Enforced non-factual claim types as non-check-worthy at the provider response boundary.
- Added deterministic identity, temporal-scope, and segment-provenance checks.
- Codex review required and applied: the extraction prompt now states the mandatory non-factual check-worthiness rule.
- Integrated the canonical validator into `ProcessingWorker.extract_claim_window`: provider output now requires a substantiated job statement date when supplied, canonical taxonomy, exact segment mapping, bounded temporal scope, and the replay-compatible deterministic identity before persistence.
- Codex review corrections: claim replay keeps the pre-existing identity algorithm; unresolved statement dates are never replaced with content publication dates; conflicting persisted claims fail closed instead of silently retaining a different classification.
- Public-safe claim representation is versioned under `claim_contract`: statement/validity scope, check-worthiness, speaker-approval requirement, and public segment identifiers only; extraction metadata and raw transcript/evidence bodies remain excluded.
- Local acceptance: 44 focused contract/runtime/worker/queue/projection tests and the full 199-test suite pass; benchmark 5/5 and `git diff --check` pass.
- MiniPC proof on 2026-09-24: synchronized the five runtime files and five focused test files to `/home/udodo/src/DichiarazioniPubbliche.it`; `compileall`, the full 199-test suite, and benchmark 5/5 pass on the runtime host. No schema migration or production-data mutation was required.

# DP-521 — Bind the source freshness allowance to its exact observation scope

Status: DONE
Milestone: M5 — Reliability, security, operations, and data lifecycle
Depends on: DP-244

## Problem

The pure, opt-in DP-244 private coverage catalog bound a source observation
receipt to an exact policy **version** but omitted the actual
`max_staleness_seconds` decision input from `CoverageUnit.scope_fingerprint()`.
An unchanged receipt from a reviewed 60-second freshness window could be
replayed by passing a 365-day allowance, without a new scope fingerprint.
The same old observation then appeared `CURRENT_WITHIN_OBSERVED_SCOPE`
instead of `STALE`, despite no new authoritative source observation.
That is a scope-bound replay/integrity defect.

## Outcome

An observation accepted under one exact freshness allowance cannot be
silently reused under another allowance without independently revalidating
the source scope and generating a new matching receipt. Stale data must
never become current merely by expanding a caller-supplied time window.

## Scope

- Bind the validated integer `max_staleness_seconds` into the existing
  private `CoverageUnit.scope_fingerprint()` alongside the policy version,
  source, collection, language, format and interval.
- An exact reviewed observation from the old/short unit remains `STALE`;
  an attempted replay against the relaxed unit is explicitly rejected.
- Keep the parent DP-244 collection/source coverage acceptance unchanged.

## Non-goals

This bounded bug fix is not a new crawler, scheduler, rights attestation,
external observer, database migration, production MiniPC rollout or
authorization to publish a freshness indicator. It does not finish
DP-244 AC-244.1–.6.

## Dependencies and sequencing

The existing DP-244 pure source-only model, validation and deterministic
fixtures are sufficient. No provider, legal grant, external corpus or
privileged runtime is needed to prove that a previously accepted source
receipt must not be valid for a different freshness-policy window.
Provider rights and live acceptance remain separate requirements in DP-244.

## Acceptance criteria

- [x] **AC-521.1**: The 60-second policy applied to a permitted,
  independently fixture-bound observation from five minutes earlier
  evaluates `STALE`, without claiming external source freshness.
- [x] **AC-521.2**: Reinterpreting the same observation under a 365-day
  policy produces a different `scope_fingerprint()` and explicitly
  refuses the replay with `COVERAGE_MIXED_SCOPE`, rather than returning
  currentness.
- [x] **AC-521.3**: A regression test first proves the original RED
  acceptance error and then GREEN after the minimal fix, with all
  existing focused and adjacent coverage/source-watch tests passing.
- [x] **AC-521.4**: The source-only bug fix updates only the owned DP-244
  pure model, test, and parent documentation. Scope hashes issued by
  older opt-in fixtures are not silently accepted, no production
  fetch/deploy/DB mutation occurs, and Git integration runs under one
  coordinator's staging lease.

## Validation / proof

Test:
`tests.test_dp244_coverage_catalog.CoverageCatalogTests.test_longer_staleness_policy_cannot_reuse_short_window_source_receipt`.

Observed **RED** against pre-fix source: `AssertionError: ValueError
not raised`. The full original 60-second policy was `STALE`; the
old unit scope hash remained equal to the relaxed one. The source
fix adds a single `self.max_staleness_seconds` value to the exact
scope-fingerprint tuple. **GREEN**:
`tests.test_dp244_coverage_catalog` **18/18 PASS**; combined
`tests.test_dp244_coverage_catalog`,
`tests.test_dp515_incremental_watch`, `tests.test_source_watcher`:
**55/55 PASS**. Scoped Ruff, targeted compileall and `git diff --check`
PASS. This is not proof of live source rights or actual page freshness.

## Documentation, data, and migration impact

Changes only deterministic source scope hashes for new opt-in
private observation receipts. Any older in-memory/fixture receipt
reused under this changed algorithm fails closed until re-attested;
no database migration or host runtime was performed. Actual
rights/source/provider/collection releases remain governed by DP-244.

## Completion receipt — 2026-10-15

Real source-side validation bug reproduced RED and corrected GREEN.
**DP-521 DONE** with the specific, independent, synthetic-but-
falsifiable algorithmic acceptance checks above. Parent **DP-244
IN PROGRESS**, all six original source coverage acceptance criteria
remain unchecked, requiring authenticated rights, observation
ledger/conditional HTTP and MiniPC canary evidence.
This new technical-ticket closure must not be represented as an
original DP-244 or pre-existing backlog ticket DONE.

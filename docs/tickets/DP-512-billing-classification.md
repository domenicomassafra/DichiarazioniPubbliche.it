# DP-512 — Truthful operation billing classification and retrospective reconciliation

Status: IN PROGRESS
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-230, DP-506

## Problem
 Canonical receipt/replay exists but some cost writers may mark an upper bound as MEASURED_PROVIDER_COST, nested local-compute labels are outside the ledger vocabulary, and zero-rate metadata may be mistaken for a confirmed zero bill. Aggregate cost_snapshot converts missing values to zero. A monthly cap and empirical comparison cannot trust that denominator.

## Outcome
 Every provider/local attempt is reconstructable and accurately labeled: billed measured currency/amount from provider invoice or verified usage API; estimated-only upper bound; bundled plan/quota consumption; verified zero marginal fee; unknown unpriced; local machine energy as a separate measured/estimated/unknown dimension. Accurate per-attempt charges and per-logical-operation result coexist.

## Traceability & constraints
 R29/R30/R31/R39, Q9–Q14; DP-230 prior DONE and DP-506 prior DONE untouched historically. Official provider billing and plan limits are authorities only when actually read, not from a guessed token-price table. Privacy-preserving receipts must not contain prompt, tokens, raw audio, identities or credentials.

## Scope
 Adapt current provider_receipt/operation_ledger/queue_store writers/consumers and migration if necessary. Store version, provider/model/account-scope identifier (pseudonymous), operation_key, attempt, status, source/content/collection/claim/job/time, input/output tokens separately where provider reports them, reported quota units and unit type, audio seconds, latency, bill currency, invoice/usage reference, measured amount provenance and observed timestamp, estimate/rate/version, API vs subscription vs local compute, failures/retries, reset window. Keep raw immutable historic amount/basis and append an audit-marked correction/reclassification event; unknown legacy stays UNKNOWN and is NOT retroactively revalued as zero or spent. True external-plan calls carry quota/limit/reset but no fabricated USD measured amount. Translate legacy LOCAL_COMPUTE_UNMETERED to an explicitly unknown local-energy dimension while preserving raw nested receipt. Ensure queue preflight uses safe outstanding upper bounds when charge is unreported.

## Non-goals
 Changing provider, purchasing capacity, charging API, treating packaged subscription spend as per-token invoice, or inventing energy telemetry. No reclassification without field-level provenance.

## Dependencies and sequencing
 Requires ledger receipt replay; implement prior to empirical attribution DP-513 and before final EUR cap DP-514. If authoritative cost source is unavailable, preserve UNKNOWN and conservative cap. Existing operation ids stay stable; do not fork a separate cost database.

## Acceptance criteria

- [ ] `AC-512.1`: Positive: an observed billed provider attempt has measured_cost and source reference; estimated unit-rate attempt has ESTIMATED_ONLY, not MEASURED; included-plan quota has EXTERNAL_PLAN; local work has independent energy unknown/measured.
- [ ] `AC-512.2`: Negative: zero-rate configured Antigravity estimate, Groq assumed rate, missing billing/refund/retry metadata and unobserved local Wh never yield ZERO_COST/MEASURED_PROVIDER_COST by inference.
- [ ] `AC-512.3`: Attempt 1 retry/failure and attempt 2 success preserve one operation identity, two usage attempts and correct billed usage/quotes; same attempt replay is idempotent.
- [ ] `AC-512.4`: Legacy receipts are preserved with versioned correction history, no doubling; summaries show separately known billed, estimates, unallocated/unknown, plan quota and energy.
- [ ] `AC-512.5`: Atomic reserved upper bounds plus observed billing reconciliation protect budget; UNKNOWN blocks paid dispatch and generates one bounded operator action, never a free path.
- [ ] `AC-512.6`: MiniPC isolated PostgreSQL replay, worker/scheduler/health consumer parity and redaction pass, including month timezone boundary and concurrent attempts.

## Validation / proof
 Synthetic cases for measured vs estimate vs plan vs unknown vs true marginal-zero; real existing schema writer integration with isolated disposable DB; fixture of failed/retried duplicate receipt; queue daily-source totals and private health digest; backfill preview showing before/after counts/hashes with no destructive migration; MiniPC isolated test of candidate when implemented. For empirical bill matching require a future authorized usage statement, not a test sample. Document proof source and observation date.

## Documentation, data, and migration impact
 Incremental version/column or typed usage subrecord only where current schema cannot represent required dimensions, additive and replay-safe; update operation ledger glossary, cost policy, runbook and tests; redact account identifiers. Retain DP-230 completion receipt unchanged.

## Completion receipt
 Not implemented; planning only. Future completion binds commit, exact writer/consumer test results, migration hash, legacy reclassification count, MiniPC readback and residual UNKNOWN.

## 2026-10-11 — First implementation slice

Current operation writer misclassification was repaired in `candidate_extraction.py`/`operation_ledger.py`/`queue_store.py`/`worker_handlers_transcript.py` (commit `c6d55c7`). A provider estimate no longer masquerades as MEASURED billed spend; absent local energy cannot silently become zero, with focused replay tests. Live billing/FX reconciliation, missing historical revisions, cross-worker reservations and MiniPC authoritative ledger acceptance remain open.

## 2026-10-11 — Discovery adapter cost truth and reservation slice (source only)

The existing `research_discovery.py` writer treated `DiscoveryAdapterResult.cost_usd` as a measured provider charge despite the adapter contract having **no** invoice, verified usage API source, billing observation time or account/plan reference; it also treated a zero upper bound as verified `ZERO_COST`, even on provider failure. These assertions existed in the older discovery tests and are now corrected. In fresh receipts, positive adapter bounds are `ESTIMATED_ONLY`, missing/zero bounds are `UNKNOWN`, and `measured_cost_usd` remains null. The adapter-reported monetary value is retained only as `adapter_reported_cost_usd` with `cost_basis=adapter_estimate_unverified` in a sanitized receipt. Historic immutable provider receipts and prior billing classifications are not rewritten or silently backfilled.

The single-run discovery cap now reserves the **greater of adapter upper bound and reported estimate** for each invoked attempt, preserving the original reported `research_discovery_attempt.cost_usd` separately. `resume_state` reconstructs the bound from durable attempt `cost_upper_bound_usd` and its linked ledger receipt; a billed-unknown/zero-ceiling attempt blocks further adapter calls in the same process and after restart. Pre-invocation blocked attempts with no ledger receipt are not charged against the reserved bound. No new provider, remote call, database schema or pricing table was used.

Regression receipt: `tests/test_dp512_billing.py` classification/receipt/unknown-zero tests failed before the source fix (7 assertion failures across 3 tests), then passed. `tests/test_research_discovery.py` reproduced the zero-bound follow-up dispatch (two failures) and under-reserved discounted report (follow-up adapter incorrectly called), plus a missing persisted reservation field on restart. After the fixes, `PYTHONPATH=poc python3 -m unittest tests.test_dp512_billing tests.test_research_discovery -q` passed **42 tests** and `python3 -m compileall -q poc tests` and `git diff --check` passed on the Mac checkout. These are synthetic/local contract tests; they are not invoice evidence or MiniPC PostgreSQL acceptance.

Extended Mac regression: 99 tests passed across `test_dp512_billing`, `test_research_discovery`, `test_research_discovery_schema`, `test_operation_ledger`, `test_operation_ledger_schema`, `test_ops_cost_policy`, `test_queue_store`, and `test_dp514_monthly_budget`; `git diff --check` passed. The deterministic benchmark passed 5/5. The unrestricted unittest discovery run was interrupted after stalling in the unrelated PostgreSQL setup of `test_provenance_revalidation_persistence`; it is **not** a full-suite PASS. No isolated MiniPC/PostgreSQL billing replay was performed.

DP-512 remains **IN PROGRESS** with every AC unchecked. Outstanding: invoice/usage/plan/quota provenance and refunds; true measured/unknown/plan/local-energy separation across all writers; immutable append-only reclassification events for historical rows; crash-safe and cross-worker atomic budget reservations; independently verified PostgreSQL replay and MiniPC worker/health consumer parity, FX and timezone boundaries, and authorized provider bill matching. A zero-rate estimate still never proves free provider capacity or subscription entitlement.

## 2026-10-11 — PostgreSQL receipt rejection at unknown zero ceiling

An isolated local PostgreSQL replay of `test_existing_factcheck_persistence`
reproduced three actual writer failures: the adapter correctly tagged an
unpriced attempt as `UNKNOWN`, with reported upper bound zero, but the SQL
constraint rejected any UNKNOWN receipt without a positive monetary estimate.
The failed receipt also broke exception handling for blocked/failing lookups.
The canonical DDL now permits an UNKNOWN receipt with zero *estimated ceiling*
without changing it to `ZERO_COST` or fabricating a nominal bill. The additive
replay-safe migration `20261011-allow-unknown-discovery-ceiling.sql` drops the
obsolete strict named check on existing databases, retaining all nonnegative,
measured and ZERO_COST constraints. Local isolated PostgreSQL tests and schema
tests are **GREEN: 21/21**, after RED: 3 errors. No MiniPC production migration
was applied; older databases and owner-authorized migration readback remain
pending. `UNKNOWN` does not authorize billing, provider dispatch or publication.
The remaining original DP-512 AC remain unchecked.

## 2026-10-11 — Immutable attempt reconciliation, source-only readout

The existing `operation_ledger.py` aggregator counted any repeated immutable
`provider_receipt` row **twice** (including its measured/provisional monetary
amount, tokens and requests). The PostgreSQL schema indexes
`(operation_key, attempt)` but does not enforce that pair as UNIQUE, so two
different receipt IDs could also claim the same attempt without triggering
an explicit conflict in this consumer. Missing invoice provenance was not
distinguishable from an externally verified bill in an aggregate number.

The read-only operation-ledger consumer now normalizes **exact** receipt
replays idempotently by receipt ID and `(operation_key, attempt)`, and rejects
changed contents under a reused receipt ID or competing IDs for the same
logical attempt. A new `reconcile_operation_billing` report accepts the
existing `QueueExecutionCostStore.operation_ledger_receipts` result directly.
It retains failed + retried provider attempts as separate charges, separates
**recorded measured-labeled USD** from **provisional estimated USD**, unknown
cash liability, external-plan attempts, explicit zero-cost attempts and
unknown local energy. Plan quota quantities, subscription allocations,
measured energy and independently confirmed billed amount remain `None`
instead of fabricated zeros or allocation rules.

The report additionally groups the **real consumer's** receipt identities by
logical operation, ordered attempt and provider, with allowlisted status,
original billing basis, optional recorded/provisional amount, cost uncertainty,
energy basis and `NO_STATEMENT_LINE` / `MATCHED_UNVERIFIED` /
`AMOUNT_DISPUTED` / `FX_REQUIRED` per-attempt comparison. Mixed provider/model
or operation under one logical operation key now raises a scope conflict
instead of presenting an incoherent grouped charge. This is a private,
non-publishing summary and does not include provider receipt JSON, source
bodies, URLs, prompts, tokens or account credentials. Untrusted free-form
receipt status strings are rendered only as `UNRECOGNIZED_STATUS`, never
echoed into the grouped report; malformed receipt/provider/operation IDs
fail closed instead of exposing private metadata.

Optional synthetic/manual statement lines bind exact receipt ID, operation
key, attempt and provider, and are replay-idempotent. Disagreeing USD amounts,
missing attempt identities, mixed currency without FX and multiple distinct
statement lines for one attempt are separately disputed/uncomparable or held.
Even a numerical match is **MATCHED_UNVERIFIED**, not provider invoice proof:
no API/provider source authentication, plan entitlement, monetary adjustment,
cost threshold, refund, cash settlement or dispatch authority is inferred
from caller-provided references. The immutable original receipt is never
modified or retrospectively reclassified. NaN/Infinity and zero attempt
numbers are rejected rather than becoming a free or valid charge.

TDD RED→GREEN: the new reconciliation API initially failed import; the
multiple-distinct-invoice-lines adversarial test subsequently failed until
the no-double-attribution fence was implemented. Tests exercise the **real
queue-store receipt consumer method with synthetic persisted rows**, without
changing `queue_store.py` or the private digest. Final targeted local run:
**61/61 PASS** across the DP-512 reconciliation, operation ledger, earlier
DP-512 billing, queue store, queue runtime and health-digest suites; compileall and
`git diff --check` PASS. This is neither a real invoice nor PostgreSQL/MiniPC
billing acceptance. In particular, the existing `health_digest.py` still
groups `cost_usd` using fallback arithmetic that does not express true UNKNOWN
or authenticated billing; it was inspected **read-only** under this worker's
strict ownership. No source schema, migration, provider, MiniPC, commit, push
or paid dispatch was modified.

**DP-512 remains IN PROGRESS; all AC-512.1–.6 unchecked.** Remaining gates:
authoritative invoice/usage API account-scope evidence and FX/provenance,
durable append-only corrections and refunds, transactionally reserved budgets,
actual provider-plan quota/local-energy observation, digest/worker parity,
safe historic backfill preview and MiniPC isolated PostgreSQL replay.

# DP-512 — Truthful operation billing classification and retrospective reconciliation

Status: FUTURE
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

# DP-513 — Bounded empirical GPT-6/Antigravity/Groq/local-capacity pilot

Status: FUTURE
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-512, DP-506

## Problem
 The owner has a temporary high GPT-6 allowance through Codex/ChatGPT-web, with no demonstrated equivalent API entitlement. Antigravity CLI usage/quota, Groq remote ASR, local model audio and electricity each have different units/resets. A single assumed price cannot predict reliable daily throughput or the EUR10 target.

## Outcome
 Produce a repeatable per-day, per-provider-account, per-model/task, source/content/person/topic/job experiment ledger under a bounded approved workload. Report provider availability and capability, quota units/resets/retries and actual incremental/full costs with confidence labels; pick a sustainable routing proposal without changing the production route or quality criteria automatically.

## Traceability & constraints
 R29/R30/R31/R34/R39. First candidate path uses GPT-6 in supported native Codex/ChatGPT-web interfaces when the owner has observed access; this is an interactive/account-bound tool capability, NOT evidence of API credentials, daemon invocation, automated entitlement, unlimited tokens, use permission for unrelated API endpoints, or guaranteed persistence. Antigravity (CLI/native usage command and plans) and Groq (speech-to-text usage/fees) must be verified at experiment time; spoken “Grok” does not mean xAI. Local energy has explicit measurement method/baseline. No automatic provider fallback on failure.

## Scope
 Pre-register fixed representative workload strata: text official/article/PDF, historical German original+Italian translation check, multi-person source, medium/long audio, successful fact-check with credible external reference, insufficient-evidence case and retry/outage. For each bounded daily sample capture input version/hash, model+route+access interface, request/attempt count, tokens in/out where exposed, quota/credits and units, before/after percentage/count, exact reset time or unknown, latency, audio seconds, cache hit, failure/quality/abstention, marginal billed receipt, subscription treatment, energy idle/load Wh/kWh if meter supported, sample energy methodology/uncertainty, human operator minutes and source/public success. Daily active users not the billing denominator. If device Wh cannot be observed, declare UNKNOWN instead of estimating from TDP as measured. Compare modes only on same held dataset and safety/semantic fidelity gates (false attribution AND false verdict separately). Daily report includes cost per stage, successful Content, approved Statement and published Finding; skipped/held items stay in denominator by attempt and separate safe outcome.

## Non-goals
 API trials based on ChatGPT subscription claims, xAI switch, surprise cloud account, paid provider execution now, automatic production integration, assuming any model supports infinite context or all languages.

## Dependencies and sequencing
 FIRST-FULL-PILOT before comparative/capacity trials; DP-201 path must separately satisfy the official canary; source rights first. Approval for each billed provider, max budget, account terms and cost ceiling is a specific future activation event. Repeat across enough reset cycles to observe real variation; no arbitrary invented “N days proves forever” promise.

## Acceptance criteria

- [ ] `AC-513.1`: Plan and data are frozen before first call; actual enabled GPT-6 Codex/web mode and account entitlements are read back, or native access is recorded UNSUPPORTED/UNKNOWN and remains a manual route.
- [ ] `AC-513.2`: Native Antigravity usage observation preserves account/model quota dimension and reset without treating percentages as tokens; Groq reports audio duration and real measured invoice only when available.
- [ ] `AC-513.3`: Before/after quota reading, retries, latency, failures and exact source/content/job join keys exist for each attempt; absent measurement is UNKNOWN, not 0.
- [ ] `AC-513.4`: Real local-energy meter protocol contains idle baseline, measured period and Wh result plus attribution caveats; missing meter is UNKNOWN.
- [ ] `AC-513.5`: Quality/rights/privacy gates fail closed; no provider replacement permitted by price alone, no new child jobs on blocked capabilities, no unapproved cost.
- [ ] `AC-513.6`: Report distinguishes observation dates, free/included-plan usage, billed incremental cash, allocated subscription and machine energy; publishes no false plan guarantee or experimental prompt/source body.
- [ ] `AC-513.7`: Reproduce bounded replay and compare full attempted denominator, uncertainty interval and quota reset cycles; MiniPC operation ledger readback and per-day digest agree.

## Validation / proof
 Prior offline replay first; subsequent separately authorized actual usage snapshots/cost invoice and signed workload. Reconcile attempts/time windows with DP-512, verify provider official documentation effective at trial time, audit quality against externally established reference—not the same generator grading itself. Candidate route remains held until release authority.

## Documentation, data, and migration impact
 Append-only private trial manifest and result/uncertainty ledger; no credentials, model prompt bodies or personal details in public logs. New measurement fields reuse operation receipts.

## Completion receipt
 Not implemented; planning only; future receipts identify account-interface capability, source and day, observed quota reset, invoiced vs estimated classes, energy provenance, quality and NO-GO/GO-for-proposal disposition.

## 2026-10-12 — Real disposable PostgreSQL canonical usage/readback parity (offline)

An isolated **read-only** candidate consumer was implemented in
`poc/dichiarazioni_pubbliche/ops/usage_attribution_pg_v1.py`, with real
PostgreSQL 17 integration tests in
`tests/test_dp513_usage_attribution_pg_next.py`. The source and tests
for DP-512 remain untouched and are reused as read-only dependencies /
disposable test fixtures. The new tests initialize a real temporary PG17
server with the complete **canonical `db/schema.v1.sql`**, seed
`provider_receipt` rows and use the existing DP-512 append-only
classification CAS fixture to produce revisioned receipt events.
No independent usage/provider reader was invented or asserted to be an
authenticated invoice.

The new reader obtains one PostgreSQL **REPEATABLE READ, READ ONLY**
snapshot of canonical provider receipts, their exact original-row
fingerprints and current DP-512 classification history. It uses the
existing `operation_usage_receipt_from_row` and
`reconcile_operation_billing` for source-aligned typed parsing and
aggregation, then independently calls the real
`QueueExecutionCostStore.operation_ledger_receipts()` consumer.
Disagreeing readbacks (including a canonical mutation between the
snapshot and consumer query) refuse attribution rather than silently
mixing revisions. Canonical duplicate `(operation_key, attempt)`
receipts, contradictory providers under one logical operation,
tampered post-CAS originals and malformed correction histories also
fail closed. Failed first attempts and successful retries remain
separate in the attempt denominator, while an append-only correction
revises metadata without counting an attempt twice. Parallel competing
DP-512 CAS corrections produce one winner, and fresh reader instances
reconstruct the same revisioned result.

The result is a **private, bounded, sanitized attribution only**:
opaque hashes for receipt/operation keys, provider/model allowlist,
UTC observation day, attempt outcome, source/content-link presence,
classification revision, recorded measured-labeled versus provisional
estimated USD, UNKNOWN cash liability, external-plan counts and
missing billing-reference counts. A measured-labeled row with a
locally supplied DP-512 reference is
`RECORDED_MEASURED_REFERENCE_UNVERIFIED`; without one it is
`RECORDED_MEASURED_REFERENCE_MISSING`. **Neither is an authenticated
bill.** A provider/receipt JSON refund claim cannot reduce the
recorded amount or create a verified refund. Estimates of exactly
zero remain estimates, unknown cost is never made free, external-plan
quota is not converted into USD, and unknown local Wh remains UNKNOWN.
No raw provider JSON, prompt/source bodies, URLs, account token,
invoice reference or receipt reference is exposed by the report.

**TDD RED→GREEN:** the new tests initially failed on the nonexistent
module. A subsequent fixture error was fixed solely in the new test
file (the original DP-512 fixture remained unchanged). Final new
adversarial coverage: **15/15 real PostgreSQL tests PASS**. Combined
`tests.test_dp513_usage_attribution_pg_next`,
`tests.test_dp512_billing_pg_fence_next`,
`tests.test_operation_ledger` and `tests.test_dp512_billing`:
**45/45 PASS**. Ruff lint/format, targeted compileall and
`git diff --check` PASS. No provider request, billed spend, web/cloud,
MiniPC, production migration, cost reservation, model routing,
official quota snapshot, currency conversion or dispatch occurred.

**Status remains FUTURE for the empirical provider pilot; all
AC-513.1–513.7 remain unchecked.** The actual preregistered workload,
owner-approved provider access, account/native capability and quota
readback, audio/energy meter, empirical before/after billing,
subscription treatment, independent quality ground truth, multiple
reset cycles and MiniPC owner acceptance are still missing. The
offline report has no invoice, refund, entitlement, or dispatch
authority; provider-dependent production rollout is **NO-GO**.

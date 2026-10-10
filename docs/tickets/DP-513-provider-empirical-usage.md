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

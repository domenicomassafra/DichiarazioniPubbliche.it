# Native packet D — operations, empirical costs, history, accounts, release

Packet status: PROPOSAL FOR PRIME INTEGRATION; planning-only, 2026-10-10.
Ownership: worker D. Canonical tickets, PLAN, decisions, status edits, commit and any cross-lane resolution belong exclusively to prime. The temporary D-NEW keys below are NOT reserved DP identifiers. No provider call, trial, build, database, runtime, release, credential, account or public exposure is authorized by this packet.

## Grounding, conflict resolution and historical receipts

Authoritative context: PRODUCT.md (especially the 2026-10-10 owner clarification and account extension), CONTEXT.md, ARCHITECTURE.md, PLAN.md, AGENTS.md, Task D and R24/R25/R27/R29–R34/R37–R39 in the complete master prompt. Current Git readback on the start of D review: main at 4b10829, ahead of origin/main by nine, initially clean; this is a document-planning baseline, not a MiniPC release candidate. At the recorded 2026-10-10 reconnaissance the live public API was DRAFT, the projection contained zero dossiers/search records, the MiniPC mirror had drift/missing files, real capture/statement/claim stores were empty, and preflight was NO-GO. A healthy HTTPS host, active timers, or CI cannot close that gap.

Current canonical states, which must not be silently reduced or upgraded:

| Ticket | Existing status | Already evidenced / preserve verbatim meaning | Still open / proposed treatment |
|---|---|---|---|
| DP-507 | FUTURE, M5 | Local operator-only admin boundary; later 2026-10-10 public-member Google OIDC code and noindex pages are preparatory, explicitly not admin authorization | Preserve all original conditional admin/AuthN/AuthZ/CSRF/roles/negative-auth/MiniPC ACs; trigger immediately BEFORE the first remotely reachable admin/review/moderation/queue/publication mutation endpoint. Admin stays unexposed. Reader Google login is separate D-NEW-06. |
| DP-508 | FUTURE, M5 | 2026-10-05 isolated public_intake_abuse seam: 15/15 local unit tests, 54/54 combined intake-policy tests, pseudonymous buckets, size/rate/replay controls; no live public intake | Preserve original size/type, SSRF, anti-abuse, privacy, retention, escalation, disable/rollback, no-publication and MiniPC ACs. Trigger immediately BEFORE enabling any public correction/reply/intake submit endpoint. Account membership and informational pages do not trigger intake. |
| DP-701 | IN PROGRESS, M7 | Owner selected brand; 2026-10-03 technical rename to Dichiarazioni Pubbliche / dichiarazioni_pubbliche completed on Mac and MiniPC; DNS apex/www 2026-10-06 read-back; repository/local route collision guards green; canonical 99-table restore distinct from rebrand rollback | AC-701.3/.4/.6/.9/.10 historically checked. AC-701.1/.2/.5/.7/.8 open: controlled registrar/handles, qualified trademark/name clearance, collision dispositions, DP-307 legal copy, prior-identity rollback proof. The prior rename rollback preimage was deleted; do not manufacture it from canonical post-rename backups. Owner/qualified risk disposition or genuinely recovered preimage must resolve this gate explicitly before v1. |
| DP-702 | FUTURE, M7, active dependency | DP-501..506 and DP-510/511 technical DONE receipts; DP-223 59/59 false-attribution technical benchmark at cited candidate; security/projection, restore/retention and operations candidate-bound receipts. AC-702-3/5/6/7/8/12 historically checked. | Preserve remaining AC-702.1/.2/.4/.9/.10/.11/.13/.14: qualified Q-306/DP-307 decisions, conditional surface inventory, chosen public profile/contact, full composite failure matrix, live-current release candidate safety rerun. DO NOT convert technical proof into qualified legal approval. Explicit informational-preview legal scope distinct from editorial v1. |
| DP-703 | IN PROGRESS, M7 | Pure launch-set/snapshot candidate only; AC-703.3 provider fail-closed and AC-703-11 no public side effect checked; no real included/approved production source set | Preserve at least THREE approved source families through shared M2 contracts for final stable-v1 AC-703.2, plus rights/privacy/provenance/disclosure, live MiniPC, projection and rollback. Do not replace this criterion with a one-source pilot. Distinguish the real 100-item Garlasco tracer required by DP-214 from a smaller FIRST end-to-end pilot; both remain separately accountable. Historic Hitler/Mussolini bulk belongs only AFTER pilot acceptance. |
| DP-704 | FUTURE, M7 | Comprehensive stage/failure/correction/rollback design exists, but no integrated approved MiniPC rehearsal or accepted rollback receipt | Preserve AC-704.1–.13 as open (including future real source→public→correction path, failure matrix, attribution integrity, replay, MiniPC public/private readback, owner decision); update its target path for exact original quotation and non-factual Statement in concert with B/C. Full pilot/rehearsal and stable launch are different acceptance levels. |
| DP-705 | FUTURE, M7 | Side-effect-free launch preflight exists and AC-705.1 (NO-GO honesty) checked; no authorized public v1 release | Preserve AC-705.2–.12 open: version identity, DP-701–704 accepted packets, clean candidate, schema/migration/runtime, public/privacy/correction, rehearsed rollback, monitoring, owner sign-off. No tag, push, static-site refresh or public DNS success equals v1. |

Canonical DP-701 contains the specific 2026-10-07 receipt for a 94-table canonical restore which expressly does not satisfy the old→new→old brand compatibility AC-701.7. Later DP-502/DP-702 receipts report 99-table candidate-bound restore and source/projection parity after migrations; both histories must remain dated and scoped, never overwrite one with the other.

DONE baseline to preserve rather than reopen mechanically:

- DP-230 (M2) = DONE canonical operation-key/attempt ledger and 2026-10-06 MiniPC replay of attempt 1 + attempt 2 as ONE logical operation, TWO attempts and measured 0.3 in a synthetic canary. Its receipt is about schema/replay/reconstruction, not the future empirical correctness of every writer's billing basis. Delta D-NEW-01.
- DP-501 = DONE technical threat matrix (2026-10-06 candidate and MiniPC receipts). DP-502 = DONE disposable backup/restore; latest ingestion-relevance migration receipt 2026-10-08 has 99/99 table count parity and preserved projection fingerprint; future account SQLite needs a distinct backup/erasure treatment. DP-503 = DONE fail-closed technical retention; qualified periods remain DP-304/307. DP-504 = DONE health/SLO UNKNOWN classification with MiniPC private digest. DP-505 = DONE PAGE/NO_PAGE matrix and operator runbook MiniPC acceptance. DP-506 = DONE cost/outage per-job/per-source-day/global-day guards and 2026-10-06 isolated MiniPC missing-OmniRoute canary (BLOCKED, zero new claims/finding/spend/provider invocations). None of those receipts proves the EUR10/month target or provider quota availability. DP-509/510/511 are DONE security/provenance-quarantine/rights-supersession source-drift engineering; material change or revocation triggers new candidate-scoped replay, not false reopening of earlier AC.
- DP-601 package/dev environment, DP-602 CI, DP-603 licensing inventory, DP-604 **release/version POLICY**, DP-605 clean-clone documentation, DP-606 safe label automation, and DP-607 NO-BUILD SDK/MCP-for-v1 decision are DONE under their historic scope. DP-604's 12/12 implemented policy ACs do not authorize a v1.0.0 tag, signing destination, approved host, or DP-705 launch. DP-603's code/fixture inventory does not license a new source family, media clip or public quote.
- DP-302/303 correction/reply lifecycle, DP-308/309/310 publication safety/high-risk/review separation, DP-431 projection cleanup, DP-511 rights drift all have valuable earlier DONE scope. New cross-surface concurrent revocation and actual public-host cache/rollback/correction readback belong to D-NEW-07, with substantive transactional behavior owned by B and serializers/UI by C.

Concrete seams already inspected, suitable for future reuse: operation_ledger.py (billing bases MEASURED_PROVIDER_COST, ESTIMATED_ONLY, EXTERNAL_PLAN, ZERO_COST, UNKNOWN; operation_key/attempt; filters content/source/collection); queue_store.py cost_snapshot; ops/cost_policy.py; worker_daemon.py; candidate_extraction.py; worker_handlers_transcript.py; research_discovery.py; scheduler.py, scheduler_daemon.py, queue_runtime.py; daily_pipeline_health.py/health_digest.py, source_watcher.py, ops/retention_policy.py, ops/restore_drill.py; public_account.py and docs/release/account-oidc-activation.md; docs/ops/operator-runbook.md. No new message bus, vector database, hosted workflow engine or parallel pipeline is warranted without measured evidence.

Observed SPECIFIC economics defect candidates requiring implementation tests, not declarations of a production incident:

1. candidate_extraction.py around the receipt_insert SQL uses upper bound and a separately supplied cost_usd but hardcodes billing_basis MEASURED_PROVIDER_COST. Confirm whether that amount originates in actual provider billing before using this category. If it is upper-bound/token×rate derived, store ESTIMATED_ONLY or EXTERNAL_PLAN/UNKNOWN appropriately, retaining the prior raw receipt and reversible classification migration.
2. worker_handlers_transcript.py embeds LOCAL_COMPUTE_UNMETERED in its local-ASR nested receipt, but operation_ledger.py does not define that billing basis; queue_store.py cost_snapshot aggregates measured-or-estimated cost and COALESCEs missing sums to zero. The digest cannot infer zero-energy or zero-real-cost from this. A nested annotation is not an observed Wh/kWh reading.
3. research_discovery.py _discovery_billing treats known_cost_usd=0 and upper_bound=0 as ZERO_COST; zero-rate configured estimates and true observed no-charge provider operations must be distinguished. Treat UNKNOWN or EXTERNAL_PLAN unless reliable billing/zero-marginal-charge proof exists.
4. worker_daemon.py and ops/cost_policy.py default USD0.25/job, USD1/source/day, USD5/global-day; USD5/day could exceed EUR10/month many times. They are historical circuit breakers, not the owner’s proposed monthly target. Aggregate/retry/reservation race, account quota reset and cross-currency conversion require explicit tests. A first-time source without known cost is BLOCKED, not authorized free work.

## Proposed precise updates to seven existing ticket files (prime owns editing)

### DP-507 — keep FUTURE, admin conditional; preserve all existing ACs

Problem delta: A public reader account with Google OIDC is a membership/login boundary, separate from Studio/admin. The future autonomous verification design may also create a machine publication authority, but it must not reuse an anonymous member account, forge reviewer identities or expose admin API ahead of security acceptance.

Outcome delta: A versioned surface inventory records each HTTP route as public read, opt-in account utility, authenticated member mutation, public intake, private Studio, or remotely exposed privileged mutation. DP-507 activates only for the last category; D-NEW-06 owns the reader-account rollout. Before admin exposure: signed/authorized actor identity, least privilege by role and action, CSRF/origin/session/cookie policy, rate/lockout/abuse, audit without private leakage, revocation/replay and MiniPC negative cases. If a machine authority migrates editorial governance, B explicitly owns its independent policy and legitimacy; this is no grant from Google login.

Proposed new AC, appended unchecked: (a) a route inventory proves disabled privileged endpoints on actual selected public deployment and links exact re-review trigger; (b) member cookie, anonymous caller, replayed/stale privileged request cannot approve, submit moderation, unblock jobs, modify rights, publish or issue correction; (c) opt-in member account remains independent of operator identity even when sharing the same hostname; (d) before any exposed privileged route the exact MiniPC/security runbook and rollback/readback are green. No need to implement a dormant admin HTTP API just to close this conditional ticket.

Dependencies: hard on the actual future approved admin-surface implementation/security boundary (which does not yet exist); coordinate DP-501/702, B's authority migration and D-NEW-06. Completion proof: effective proxy route/auth matrix, positive authorized canary only if a route exists, negative unauthorized, endpoint shutdown and public read availability; absent surface signed NOT_APPLICABLE-for-current-profile decision with re-open trigger.

### DP-508 — keep FUTURE, intake conditional; preserve all existing ACs/receipt

Problem delta: Registering a reader is not submitting a public correction or reply. A future owner-approved intake endpoint must stay out of live public routing until abuse/privacy/retention/operator response decisions and composite MiniPC proof are complete.

Proposed new unchecked AC: (a) real route-level switch inventory and negative external POST/URL/SSRF tests before exposure; (b) replay/duplicate-burst behavior, atomic buckets, per-user plus global bounds and outage of rate store fail closed; (c) user-supplied narrative/media/URL never gets server-side fetch, direct publication or Studio identity/authority via member login; (d) consent/privacy/contact/retention/legal hold/deletion decision and precise escalation owner; (e) disable route and replay pending submissions without dropping audit/private state. Reactivation requires DP-302/303, DP-304/307/702, scoped DP-508, and MiniPC rollback acceptance; rollout independent of D-NEW-06.

### DP-701 — retain IN PROGRESS and all prior checked/unchecked ACs

Delta to owner decision: document external registrar ownership/expiry and handle disposition in controlled receipts; qualified mark/name risk review and public copy legal acceptance; case-insensitive external collision checks and disposition; avoid requiring an impossible fabricated rebrand preimage. B-701-07 must be answered explicitly: recover authentic pre-cutover snapshot and exercise compatibility OR seek owner/qualified acceptance of a formal superseding rollback requirement limited to the currently deployed canonical identity, explaining the lost evidence and residual legacy-link risk. This is a proposed owner decision, NOT automatic waiver of AC-701.7. DP-705 still NO-GO unless the accepted release policy and DP-701 state are consistent. Do not claim domain purchase solely from DNS (2026-10-05 owner report is distinct).

New unchecked AC proposal: exact domain/host/redirect/registrar and published identity are rebound to the selected immutable release candidate before GO-PUBLIC; no private receipts or old redirects leak into search/sitemap/cache. Compatibility evidence must state which historical identities CAN and CANNOT be recovered.

### DP-702 — retain FUTURE; active legal/privacy/security release dependency

Extend applicability matrix with: standalone Google member SQLite classes, Google as identity provider, cookies/callback and account erasure; three distinct profiles (informational preview, private full-slice pilot, stable editorial/public v1); autonomous text fact-check/publication machine authority version/policy; non-factual Statement and exact verbatim rights by source; concurrent revocation/cached public artifacts; operator visual QA and public contacts; measured provider/energy accounting and unknown costs. Capture Q-306/DP-307 qualified dispositions without copying private advice into Git.

New unchecked AC proposal: (a) release profile records applicable policy question, reviewer/owner/date and excluded disabled surfaces; (b) current exact-quote, process-legal, non-factual, high-risk and automation rules have machine regression proofs on SAME candidate as DP-704; (c) composite end-to-end failure matrix covers cost exhaustion, missing quota, account-origin abuse, correction/takedown cache, concurrent revocation and public history; (d) a material content/source/model/policy/deployment change invalidates dated authority; (e) no fake reviewer dual-signoff and no general human fact-check staffing dependency. Existing AC-702.3/5/6/7/8/12 remain historically checked for stated candidate/scope; AC-702.14 awaits the final candidate.

### DP-703 — retain IN PROGRESS, stable-v1 three-family criterion remains open

Differentiate THREE dataset stages in its manifest: FIRST-PILOT represents a very small rights-cleared diverse end-to-end set proving acquisition→wording→statement→fact-check/position→Person×Topic→correction; PRODUCTION-LAUNCH represents three approved source families under the exact existing AC-703.2; HISTORICAL-BACKFILL represents approved post-pilot permanent material with separate budgets/coverage (D-NEW-05). DP-214's distinct Garlasco 100-real-Content tracer remains outstanding; never relabel the small pilot as its AC-214.4 success or change the 100 threshold silently. If staged acceptance changes the order of 100-item work, record the proposed sequencing and owner approval; 100-item acceptance obligation persists.

New unchecked AC proposal: (a) first slice uses multiple real representative people/languages/claim kinds when source-rights permit, including an opinion-only Statement and one exact-wording citation with lawful display decision, German semantic/translation checks where historical sources selected; (b) no large historic import launches before all stages of the end-to-end FIRST-PILOT are accepted and certified on MiniPC; (c) stable-v1 launches only when at least three genuinely approved source families traverse the shared path or stay explicitly held according to existing M2 criterion, plus real candidate public projection/correction; (d) item-by-item rights source-family policy, snapshot content hashes, freshness and incomplete coverage caveats; (e) no editorials guessed from language, source visibility or age of historical subject. D-NEW-05 owns batch throttling, source continuity and periodic refresh; A owns source rights/catalog.

### DP-704 — retain FUTURE; replace schematic success case with complete product rehearsal

Preserve all AC-704.1–.13 and their historical negative paths. The integrated success path now includes immutable source wording and quote source-span proof, adaptive cited context, non-factual Statement without obligatory Finding, a real factual verification with credibly established reference, same-person/cross-person relation distinction, Person×Topic citation/summary, public corrected/withdrawn version and revised collection visibility. A historical speech subject with no new material is still refreshable by newly discovered archive/version. The final rehearsal is on exact approved launch-set candidate; first FULL-PILOT acceptance is separately recorded earlier.

New unchecked AC proposal: (a) distinguish private FIRST-PILOT milestone and stable release candidate IDs; (b) actual public-reader HTML/API/search/sitemap/cache readback of quote, translation labeling, correction and removal, not just generated file hash; (c) concurrent revoke-versus-promotion/publication, in-flight worker and static build, rollback and stale CDN responses must be exercised with B/C/D-NEW-07; (d) provider-unavailable but safe public read remains available; (e) cost ledger/unknown quota/caps and operator incident digest reconstruct the same job attempts; (f) clean reference data/gold external to tested model; (g) rollback has signed before/after database/public/read state and no private leakage. Rehearsal GO-WITH-HOLDS never confers GO-PUBLIC.

### DP-705 — retain FUTURE; v1 authority and release operation are still open

Add the three profile gate matrix below, live contractual readback and a post-release watch. Immutable candidate bind: commit, migration order, source/rights manifest, signed policy, model route/quota profile, operation ledger period, MiniPC mirror manifest, public projection/API/web build, cache, exact public URL, error budget, incident contact, backup and reversible readback. The release decision includes a rollback threshold, after-deploy monitoring owner, duration/window justified by SLO, and a signoff independent of scripted preflight. D-NEW-07 supplies immediate retraction/revocation across distributed consumers; D-NEW-04 supplies sustainable monitoring after accepted production release.

New unchecked AC proposal: (a) informational-preview, pilot, stable-v1 statuses remain distinct in release manifest and UI disclosure; (b) exact MiniPC mirror/build/schema/projection parity and legal decisions are read back after rollout, including live SEO/API/cache; (c) any new unauthorized secret, unknown cost, stale policy, missing source rights, failed correction or rollback forces NO-GO or automatic hold/rollback under preauthorized runbook, never success via re-labeling; (d) a post-release monitored sample includes relevant source changes, correction propagation, quota reset, queue age, cost and explicit coverage gaps; (e) no release solely from origin/main push, DNS success or empty informational preview. Preserve DP-705 release/signing owner final decision and every original open AC.

## Release profiles (additional classification, not relaxed v1 gates)

| Profile | Legitimate deliverable | Mandatory evidence | Explicitly not proven |
|---|---|---|---|
| INFO-PREVIEW | Static informational public pages + method/empty states with clear “no approved public corpus yet” messaging; no new account/intake; existing six public pages may remain independently refreshed under their specific approval | Exact web artifact commit/hash, safe projection fingerprint/empty disclosure, noindex private routes, contact/privacy applicability, host readback, security/rollback of informational static bundle | Full Fact-check, source rights, stable schema/v1.0.0, approved corpus, authorized account, integrated correction, model pipeline |
| FIRST-FULL-PILOT | Small bounded real-source acceptance of integrated mission, private or isolated as authorization allows, multi-person/source-language representative cases, exact quote rights and correction | Source/right/policy IDs, source→public-projection and Reader UI consumer, opinion/fact distinctions, real attribution, credible gold, false-attribution/verdict checks, exception/rollback, MiniPC exact candidate, bounded cost receipt | 100-item DP-214 tracer unless separately actually completed; three-family stable launch; production mega-historical ingestion; provider quotas/bill all month; public rollout |
| STABLE-V1 | Fully governed public reader and selected source set, required M2/M3/M4/M5/M6/M7 gates closed, three source families, full correction and release operations | DP-701..705 accepted, current Q-306/307 legal/rights, accepted machine publication authority if used, release-signed exact candidate, full MiniPC failure matrix/restore, real public/private/cache readback, operator monitoring | Unlimited/real-time corpus, infallible fact-check, all source languages pre-proven, free operating cost, unrelated admin/intake/account enablement |

Authority rules apply to each actual enabled feature; INFO-PREVIEW never becomes a semantic substitute for STABLE-V1. No profile allows unapproved quote rights, unsafe personal data, leaked raw source bodies, or auto-publication on a model verdict. Profile transitions require versioned decision/replay and go/no-go; missing legal/rights/quality evidence blocks that feature. Q-306 qualified decisions remain external, not a scripted flag. The historical migration to future autonomous editorial verification must be versioned and proven by B before any runtime gate change.

## New ticket proposals — full integration templates (all AC unchecked)

### D-NEW-01 — Truthful operation billing classification and retrospective reconciliation

Status: FUTURE (design-ready), target milestone M5 extension / cross M2 ledger; assignment of actual milestone/DP ID by prime.
Depends on (hard proposed): DP-230, DP-506. Coordinate DP-209, DP-214, DP-201..204, D-NEW-02, B's provider/authority lanes.

**Problem:** Canonical receipt/replay exists but some cost writers may mark an upper bound as MEASURED_PROVIDER_COST, nested local-compute labels are outside the ledger vocabulary, and zero-rate metadata may be mistaken for a confirmed zero bill. Aggregate cost_snapshot converts missing values to zero. A monthly cap and empirical comparison cannot trust that denominator.

**Outcome:** Every provider/local attempt is reconstructable and accurately labeled: billed measured currency/amount from provider invoice or verified usage API; estimated-only upper bound; bundled plan/quota consumption; verified zero marginal fee; unknown unpriced; local machine energy as a separate measured/estimated/unknown dimension. Accurate per-attempt charges and per-logical-operation result coexist.

**Traceability & constraints:** R29/R30/R31/R39, Q9–Q14; DP-230 prior DONE and DP-506 prior DONE untouched historically. Official provider billing and plan limits are authorities only when actually read, not from a guessed token-price table. Privacy-preserving receipts must not contain prompt, tokens, raw audio, identities or credentials.

**Scope:** Adapt current provider_receipt/operation_ledger/queue_store writers/consumers and migration if necessary. Store version, provider/model/account-scope identifier (pseudonymous), operation_key, attempt, status, source/content/collection/claim/job/time, input/output tokens separately where provider reports them, reported quota units and unit type, audio seconds, latency, bill currency, invoice/usage reference, measured amount provenance and observed timestamp, estimate/rate/version, API vs subscription vs local compute, failures/retries, reset window. Keep raw immutable historic amount/basis and append an audit-marked correction/reclassification event; unknown legacy stays UNKNOWN and is NOT retroactively revalued as zero or spent. True external-plan calls carry quota/limit/reset but no fabricated USD measured amount. Translate legacy LOCAL_COMPUTE_UNMETERED to an explicitly unknown local-energy dimension while preserving raw nested receipt. Ensure queue preflight uses safe outstanding upper bounds when charge is unreported.

**Non-goals:** Changing provider, purchasing capacity, charging API, treating packaged subscription spend as per-token invoice, or inventing energy telemetry. No reclassification without field-level provenance.

**Dependencies / sequencing:** Requires ledger receipt replay; implement prior to empirical attribution D-NEW-02 and before final EUR cap D-NEW-03. If authoritative cost source is unavailable, preserve UNKNOWN and conservative cap. Existing operation ids stay stable; do not fork a separate cost database.

**Acceptance criteria (future AC identifiers assign by prime):**
- [ ] D-NEW-01.A1 Positive: an observed billed provider attempt has measured_cost and source reference; estimated unit-rate attempt has ESTIMATED_ONLY, not MEASURED; included-plan quota has EXTERNAL_PLAN; local work has independent energy unknown/measured.
- [ ] D-NEW-01.A2 Negative: zero-rate configured Antigravity estimate, Groq assumed rate, missing billing/refund/retry metadata and unobserved local Wh never yield ZERO_COST/MEASURED_PROVIDER_COST by inference.
- [ ] D-NEW-01.A3 Attempt 1 retry/failure and attempt 2 success preserve one operation identity, two usage attempts and correct billed usage/quotes; same attempt replay is idempotent.
- [ ] D-NEW-01.A4 Legacy receipts are preserved with versioned correction history, no doubling; summaries show separately known billed, estimates, unallocated/unknown, plan quota and energy.
- [ ] D-NEW-01.A5 Atomic reserved upper bounds plus observed billing reconciliation protect budget; UNKNOWN blocks paid dispatch and generates one bounded operator action, never a free path.
- [ ] D-NEW-01.A6 MiniPC isolated PostgreSQL replay, worker/scheduler/health consumer parity and redaction pass, including month timezone boundary and concurrent attempts.

**Validation/proof:** Synthetic cases for measured vs estimate vs plan vs unknown vs true marginal-zero; real existing schema writer integration with isolated disposable DB; fixture of failed/retried duplicate receipt; queue daily-source totals and private health digest; backfill preview showing before/after counts/hashes with no destructive migration; MiniPC isolated test of candidate when implemented. For empirical bill matching require a future authorized usage statement, not a test sample. Document proof source and observation date.

**Documentation/data/migration:** Incremental version/column or typed usage subrecord only where current schema cannot represent required dimensions, additive and replay-safe; update operation ledger glossary, cost policy, runbook and tests; redact account identifiers. Retain DP-230 completion receipt unchanged.

**Completion receipt:** Not implemented; planning only. Future completion binds commit, exact writer/consumer test results, migration hash, legacy reclassification count, MiniPC readback and residual UNKNOWN.

### D-NEW-02 — Bounded empirical GPT-6/Antigravity/Groq/local-capacity pilot

Status: FUTURE (design-ready); target M5 empirical operation after FIRST-FULL-PILOT acceptance, not pre-pilot paid trial.
Depends on (hard proposed): D-NEW-01 and accepted FIRST-FULL-PILOT milestone; coordinate DP-201..204, DP-214, DP-506, D-NEW-03. Explicit owner budget/provider consent before any paid live experiment.

**Problem:** The owner has a temporary high GPT-6 allowance through Codex/ChatGPT-web, with no demonstrated equivalent API entitlement. Antigravity CLI usage/quota, Groq remote ASR, local model audio and electricity each have different units/resets. A single assumed price cannot predict reliable daily throughput or the EUR10 target.

**Outcome:** Produce a repeatable per-day, per-provider-account, per-model/task, source/content/person/topic/job experiment ledger under a bounded approved workload. Report provider availability and capability, quota units/resets/retries and actual incremental/full costs with confidence labels; pick a sustainable routing proposal without changing the production route or quality criteria automatically.

**Traceability & constraints:** R29/R30/R31/R34/R39. First candidate path uses GPT-6 in supported native Codex/ChatGPT-web interfaces when the owner has observed access; this is an interactive/account-bound tool capability, NOT evidence of API credentials, daemon invocation, automated entitlement, unlimited tokens, use permission for unrelated API endpoints, or guaranteed persistence. Antigravity (CLI/native usage command and plans) and Groq (speech-to-text usage/fees) must be verified at experiment time; spoken “Grok” does not mean xAI. Local energy has explicit measurement method/baseline. No automatic provider fallback on failure.

**Scope:** Pre-register fixed representative workload strata: text official/article/PDF, historical German original+Italian translation check, multi-person source, medium/long audio, successful fact-check with credible external reference, insufficient-evidence case and retry/outage. For each bounded daily sample capture input version/hash, model+route+access interface, request/attempt count, tokens in/out where exposed, quota/credits and units, before/after percentage/count, exact reset time or unknown, latency, audio seconds, cache hit, failure/quality/abstention, marginal billed receipt, subscription treatment, energy idle/load Wh/kWh if meter supported, sample energy methodology/uncertainty, human operator minutes and source/public success. Daily active users not the billing denominator. If device Wh cannot be observed, declare UNKNOWN instead of estimating from TDP as measured. Compare modes only on same held dataset and safety/semantic fidelity gates (false attribution AND false verdict separately). Daily report includes cost per stage, successful Content, approved Statement and published Finding; skipped/held items stay in denominator by attempt and separate safe outcome.

**Non-goals:** API trials based on ChatGPT subscription claims, xAI switch, surprise cloud account, paid provider execution now, automatic production integration, assuming any model supports infinite context or all languages.

**Dependencies / sequencing:** FIRST-FULL-PILOT before comparative/capacity trials; DP-201 path must separately satisfy the official canary; source rights first. Approval for each billed provider, max budget, account terms and cost ceiling is a specific future activation event. Repeat across enough reset cycles to observe real variation; no arbitrary invented “N days proves forever” promise.

**Acceptance criteria:**
- [ ] D-NEW-02.A1 Plan and data are frozen before first call; actual enabled GPT-6 Codex/web mode and account entitlements are read back, or native access is recorded UNSUPPORTED/UNKNOWN and remains a manual route.
- [ ] D-NEW-02.A2 Native Antigravity usage observation preserves account/model quota dimension and reset without treating percentages as tokens; Groq reports audio duration and real measured invoice only when available.
- [ ] D-NEW-02.A3 Before/after quota reading, retries, latency, failures and exact source/content/job join keys exist for each attempt; absent measurement is UNKNOWN, not 0.
- [ ] D-NEW-02.A4 Real local-energy meter protocol contains idle baseline, measured period and Wh result plus attribution caveats; missing meter is UNKNOWN.
- [ ] D-NEW-02.A5 Quality/rights/privacy gates fail closed; no provider replacement permitted by price alone, no new child jobs on blocked capabilities, no unapproved cost.
- [ ] D-NEW-02.A6 Report distinguishes observation dates, free/included-plan usage, billed incremental cash, allocated subscription and machine energy; publishes no false plan guarantee or experimental prompt/source body.
- [ ] D-NEW-02.A7 Reproduce bounded replay and compare full attempted denominator, uncertainty interval and quota reset cycles; MiniPC operation ledger readback and per-day digest agree.

**Validation/proof:** Prior offline replay first; subsequent separately authorized actual usage snapshots/cost invoice and signed workload. Reconcile attempts/time windows with D-NEW-01, verify provider official documentation effective at trial time, audit quality against externally established reference—not the same generator grading itself. Candidate route remains held until release authority.

**Documentation/data/migration:** Append-only private trial manifest and result/uncertainty ledger; no credentials, model prompt bodies or personal details in public logs. New measurement fields reuse operation receipts.

**Completion receipt:** Not implemented; planning only; future receipts identify account-interface capability, source and day, observed quota reset, invoiced vs estimated classes, energy provenance, quality and NO-GO/GO-for-proposal disposition.

### D-NEW-03 — EUR10-month planning envelope with atomic multi-interval dispatch caps

Status: FUTURE; target M5 operations evolution before unattended paid background processing.
Depends on (hard proposed): D-NEW-01, D-NEW-02 for calibration; DP-506. Coordinate D-NEW-04, DP-504/505.

**Problem:** USD5 global/day, USD1/source/day, USD0.25/job protect short-term dispatch but are not EUR10/month. USD token estimates can be stale and two workers can pass a non-atomic budget read concurrently. Quota reset and billed invoice may not align with local month; unknown charges cannot prove an economical release.

**Outcome:** Versioned owner-selected monthly **planning** ceiling around EUR10 in addition to existing short caps; actual EUR cash + optional allocated fixed plan + local incremental energy reported separately. Dispatch reserves conservative maximum charge atomically before every chargeable attempt across same billing scope. Cap breach pauses affected work with digest/explicit resume rules; no provider swap, silent overage or cap increase.

**Traceability & constraints:** R30/R31; Q9–Q14. EUR10 is a target subject to empirical measured capacity, not a guaranteed spend, a verified quote, or automatic authorization to buy subscriptions. Cost of electricity is a distinct quantity; optional cost conversion requires known EUR/kWh and measured incremental Wh, else UNKNOWN. FX conversion records source/rate/date/original amount and provisional vs invoice reconciliation. Pre-existing DP-506 caps remain active, never erased.

**Scope:** Policy defines calendar month/timezone explicitly (Europe/Rome or other owner-approved billing boundary, not inferred from provider reset); per-provider invoice period and quota reset tracked separately. Maintain reserved/pending/settled/estimated/unknown buckets; preflight must check all per-job/source-day/global-day/month/provider quotas and failure backoff. Optimistic stale daily snapshots are insufficient for atomic dispatch: reservation + attempt binding, idempotent settled/refunded/released transitions, concurrent claims, crash recovery and expired reservation reconciliation. Provide budget allocation among pilot, important corrections, incremental discovery and bulk so a historical run cannot starve urgent retraction; operator can pause/resume under documented audited threshold. Unknown paid cost blocks prior to dispatch. A verified included-plan no marginal bill can still have quota cap and electricity cost; it is NOT unlimited.

**Non-goals:** Forcing a supposedly measured invoice from modeled rate, auto-buying capacity, raising daily caps without owner signoff, treating subscription prepayments as universally zero marginal cost.

**Dependencies / sequencing:** D-NEW-01 classification first. D-NEW-02 calibrates feasible budget; implementation could test reservation primitive with synthetic costs earlier, but activating unattended paid quota requires owner acceptance of policy and trial. D-NEW-04 uses these caps.

**Acceptance criteria:**
- [ ] D-NEW-03.A1 EUR-month reports show total paid EUR, reserved maximum, provisional FX, subscription allocations and incremental energy separately; unknown values remain visibly unknown.
- [ ] D-NEW-03.A2 At overlapping scheduler/worker dispatch times a tight final EUR cap admits at most the reservations the cap covers; no duplicated retry charge or overspend via lease expiry/replay.
- [ ] D-NEW-03.A3 A late actual invoice amount, refund or reset reclassifies settlement with immutable adjustment receipt; breach/uncertainty pauses subsequent jobs and pages according to severity, no unapproved overage.
- [ ] D-NEW-03.A4 Midnight daily, DST/timezone month change and provider reset tests preserve accounting and safe deferral (provider quota can reset without falsely resetting project month).
- [ ] D-NEW-03.A5 Existing USD day/source/job guards still operate; when any guard disagrees the restrictive applicable guard wins.
- [ ] D-NEW-03.A6 Costs UNKNOWN, source policy expired or provider outage preserve held work and suppress child jobs; health digest signals pause, cause, owner and earliest legitimate retry.
- [ ] D-NEW-03.A7 MiniPC isolated concurrent queue/ledger + restart/reconcile drill records pre/post reserved/spent and zero unauthorized/public output; owner-approved monthly threshold is versioned.

**Validation/proof:** Synthetic concurrent reservation and double-failure/restart cases, late provider invoice, 31-day month/DST, FX unavailable, quota reset different from financial period; isolated PostgreSQL on MiniPC; no live provider trial as part of structural check. Report confidence and residual unknown.

**Documentation/data/migration:** Add only necessary reservation/settlement tables and trace IDs to existing operation ledger/queue schema, with migration apply/replay. Update policy, runbook and private digest, no new billing SaaS.

**Completion receipt:** Not implemented; planning only. Future candidate/policy/FX reference, monthly threshold authority, concurrent proof, MiniPC receipt and residual estimate/unknown must be recorded.

### D-NEW-04 — Economical incremental source monitoring with coverage and safe backoff

Status: FUTURE; target M5/M7+ recurring operations after accepted source path. If needed before release, launch only a clearly bounded canary.
Depends on (hard proposed): DP-209, DP-210, DP-211, DP-511, D-NEW-01, D-NEW-03 and accepted source/rights policy. Coordinate A source catalog/coverage needs, B reanalysis, C public freshness, DP-504/505.

**Problem:** Source polling exists, but permanent historical corpus and public-interest changes require adaptive, economical monitoring. Reprocessing unchanged content daily would exhaust quotas; missing/disabled sources, parser drift and inaccessible upstream material must not be misrepresented as full coverage.

**Outcome:** Versioned opt-in watch policies by source, Person, Topic and relevant Event, with per-family cadence and conditional fetch/metadata-first stages. New/amended/removed source versions enqueue only bounded, rights-authorized affected work. An auditable digest shows last successful observation, attempted checks, coverage basis/unknown gaps and source health. Ongoing monitoring is different from initial backfill.

**Traceability & constraints:** R24/R25/R32/R33/R38, Q10. Discovery by continuity AND new significant events, not viral/political rankings. No autonomous new full-site crawl, private-life mining, unsupported generic model URL guesses or publishing discoveries directly.

**Scope:** Extend existing source_watcher/scheduler/coverage_needs/queue_runtime/DP-511. Use configured source seeds/identities/robots/access policy, ETag/Last-Modified when supported, content-hash/version checks, source-family lineage/dedup and explicit event relevance rules. Work item identity includes source/locator/version/policy and stage; repeated unchanged check is cheap metadata, not full LLM/ASR. Bounded source/person/topic discovery permits a new person through standard identity/rights acceptance; relevance cannot be an ideological score. Separate high-priority correction/rights/supersession reanalysis from regular polling and paused historical backfill, with explicit cost quotas and fairness. Retry exponential backoff plus jitter, source-level outage circuit breaker, cap pause, lease expiration and dead-letter/manual concise exception queue. Enqueue downstream child only when capability and rights/cost guards are READY; failure is isolated per source. Public freshness is based on last successful *observed/approved* update with corpus/cutoff/version and coverage limitations, never “the whole world is up to date.”

**Non-goals:** Guaranteed real-time social monitoring, complete web coverage, new Kafka/Kubernetes/crawler cluster, daily re-verification of unchanged entire corpus, person ranking.

**Dependencies / sequencing:** A defines source-family coverage, B defines exactly which change invalidates findings/corrected statements, C consumes sanitized freshness metadata. D-NEW-03 budget and DP-511 invalidation are hard gates. Initial mini-corpus full path must be accepted before scaling recurring data.

**Acceptance criteria:**
- [ ] D-NEW-04.A1 Repeated unchanged ETag/hash source poll creates no duplicate Content/Capture or expensive child job; receipts record checked vs changed vs unavailable.
- [ ] D-NEW-04.A2 Changed version/new primary source and withdrawn/expired rights trigger bounded, source-linked review/reanalysis and public freshness/hold updates with hashes, idempotent restarts.
- [ ] D-NEW-04.A3 Broken provider, source 429/timeout, bad conditional response, source-specific license change or budget exhaustion blocks only affected work and never fabricates a fresh check.
- [ ] D-NEW-04.A4 Coverage rows distinguish watched/not watched, last attempted/successful date, source families, known gaps and corpus cutoff; same-person chronology stays ordered even for late discovered material.
- [ ] D-NEW-04.A5 Quota reset/backoff/lease/replay, two workers on same changed Content, and no-child-without-capability tests pass.
- [ ] D-NEW-04.A6 Private daily health ledger gives counts of attempts, new/modified/unchanged, blocked, costs, coverage, freshness and correction lag without leaking private content.
- [ ] D-NEW-04.A7 Real MiniPC bounded source/candidate replay and public cache/readback are accepted before enabling unattended production watch.

**Validation/proof:** Local fake feed with 200 unchanged/304/429/new/amended/withdrawn, isolated queue restarts and cost-cap tests; one genuinely approved source-family MiniPC canary later. Deterministic expected number of downstream jobs; no live provider/background schedule now.

**Documentation/data/migration:** Reuse source registry/health, discovery run, coverage needs and operation ledger, adding only conditional-validator/version/watch state where absent; private watch rule + public safe freshness projection. Rollback pauses the watcher, preserves source history, leaves unrelated public readers available.

**Completion receipt:** Not implemented; planning only. Future policy hash, source-version before/after, job/no-child counts, MiniPC digest and public freshness/projection fingerprints.

### D-NEW-05 — Historical permanent corpus backfill with bounded batches and refresh

Status: FUTURE; target post-acceptance historical expansion, not current first pilot.
Depends on (hard proposed): FIRST-FULL-PILOT accepted, DP-214 source/corpus acceptance as relevant, DP-703 rights/manifest contract, D-NEW-03 monthly spend cap and DP-511 source drift/revalidation. D-NEW-04 full continuing watcher is a soft coordination dependency, not a prerequisite for initial approved bulk. Coordinate A corpus/language/rights and B attribution/cross-era verification, C Person/Topic/Trace consumer.

**Problem:** The intended historical corpus of Hitler, Mussolini and other public figures is product content retained for future research, but source rights, authentic quote context, German translation and end-to-end workflow are not yet accepted. Bulk acquisition before the pilot would turn unapproved archive availability and quota abundance into false ingestion/publication authority.

**Outcome:** A permanent, progressively covered and refreshable corpus collection driven by signed source-family authorization and bounded batch manifests; each item retains original language, rights/provenance/attribution, changes, covered gaps, dated observations and an explicit publish/hold outcome. Additional source discoveries enrich prior historical persons rather than silently replacing old findings.

**Traceability & constraints:** R24/R27/R28/R30/R32/R33, owner decisions Q10. Archivioluce and Bundesarchiv are discovery leads only; no automatic download/license grant or endorsement inference. German original quotes and linked identified Italian translations; documented propaganda quotations require speaker-vs-cited-author and speech-act safeguards (B). Source publication date, historical utterance date and newly digitized/observed date are different.

**Scope:** Preflight rights/access/domain/media type, versioned source-of-record inventory, per-Content stable ID, immutable Capture/Passage hashes, explicit local-vs-official chronology, translation assurance, scope-limited source family rules. Stage metadata→rights→capture→transcription/OCR→attribution/context→candidate→finding/position→projection under queue/cost gates. Chunk and batch by source/version with dedup and lineage; no assumed infinite GPT-6 context. First import is bounded to owner-approved source families and item/time/cost envelope; resume exactly from committed checkpoint; multi-person runs are permitted with person/role isolation checks. Later discovery triggers append-only reanalysis and corrections, not full rewrite; maintain coverage-status, recheck cycle and source gone/offline state.

**Non-goals:** Importing all media from cited historical archives, unlimited backfill, political ranking, auto-publishing all found phrases, “all quotes of a person” completeness claims or image generation.

**Dependencies / sequencing:** FIRST-FULL-PILOT acceptance must include full source→public→correction chain; DP-214 distinct 100 real items and DP-703 three launch families remain preserved. Trial monthly quota/cost calibration precedes scale. If source-family rights unavailable, prioritize rights-resolvable alternative sources, record attempts and leave that item HELD; do not substitute a public paraphrase for missing lawful exact wording.

**Acceptance criteria:**
- [ ] D-NEW-05.A1 Preflight refuses all bulk when first full pilot lacks signed acceptance, source-family rights remain unknown, or monthly budget/quota cannot reserve work; zero side effects beyond sanitized failed manifest receipt.
- [ ] D-NEW-05.A2 Approved bounded batch across multiple people and German/Italian contexts preserves source/capture/utterance/observation times, exact original, translation label, author/speaker/quotation distinction and immutable hashes; no cross-person attribution.
- [ ] D-NEW-05.A3 Resume/retry after halfway crash produces zero duplicate source/capture/Statement/Finding/public routes, retains prior checkpoint, and never reprocesses unchanged copies expensively.
- [ ] D-NEW-05.A4 A newly digitized, corrected, removed, right-revoked or more complete archived source supersedes or triggers analysis with preserved history and public omission/correction when required.
- [ ] D-NEW-05.A5 Coverage UI/manifest states fraction scanned only against enumerated approved sources, original language/source-family and last observation; it never asserts all historical sources exhausted.
- [ ] D-NEW-05.A6 MiniPC pilot-level approved source, held-rights negative, high-risk quotation negative and source change/reanalysis pass before each separately authorized larger batch.

**Validation/proof:** Frozen three-source-family candidate with authoritative rights references; fixture source changes/duplicate lineage and synthetic cost cap; later real authorized archive canary plus MiniPC manifest and downstream public readback. Comparative false attribution/translation/false verdict gold in B/C.

**Documentation/data/migration:** Reuse existing corpus/capture/source-health/matching/retention stores, private batch manifest/checkpoint and source/coverage policies. Public output remains selective, rights-bound, translated visibly and fail closed.

**Completion receipt:** Not implemented; planning only. Future immutable batch/candidate, item counts, provenance/rights audit, energy/cost, interruptions/replay, accepted public-record hashes, held reasons and next refresh date.

### D-NEW-06 — Reader Google sign-up/login/logout/delete MiniPC activation

Status: FUTURE; target utility/account surface, independently gated from the first public source path.
Depends on (hard proposed): DP-304/DP-307/DP-501/DP-702 applicable qualified decisions and exact account host security acceptance. Coordinate DP-507 (admin distinct), DP-508 (intake distinct), C UX accessibility, DP-502/503 backup and retention.

**Problem:** public_account.py and the static /accedi/ + /account/ pages contain a local opt-in Google OIDC contract, but account routes were live 404 at 2026-10-10 reconnaissance; real OAuth consent, privacy/retention/secret setup and MiniPC host acceptance are absent. Showing the presence of local source as a publicly working login would mislead users.

**Outcome:** Owner-approved Google first-time registration and recurring login, same-origin session, logout, account deletion/erasure with clear privacy and availability/error UX, disabled by default unless all gate inputs are present. No member identity can become editor, Studio admin, verifier, public source subject, or right-of-reply approver. Unauthenticated readers continue to read approved projection.

**Traceability & constraints:** R37/R25, 2026-10-10 owner account request. Existing docs/release/account-oidc-activation.md is implementation evidence; future legal/profile acceptance still absent. Google OIDC client secret, signed ID-token validation, PKCE S256/state/nonce, exact HTTPS origin, secure HttpOnly cookie, CSRF, one-time flow, 5/min browser and 120/min global throttling are existing local design, not proof of production protection. Privacy applies to separate SQLite account store, WAL, backups/logs and erasure, not only PostgreSQL.

**Scope:** Real owner Google Cloud web OAuth client and exact redirect registered outside Git, approved consent/legal basis, account-specific notices/contacts, retention/erasure/backups, rate-limit failure controls, 127.0.0.1 private service behind explicitly configured same-origin proxy, consistent logout/delete all sessions, no-store/cache/header checks, mobile/keyboard/screen-reader treatment, security runbook/circuit-breaker. Test genuine registration/re-login under owner-provided test identity and deleted/revoked session readback. Disabled states show unavailable without broken fake “sign in” CTA. Privacy deletion waits for qualified backup retention decision; no dishonest claim of erasing immutable off-host snapshots instantly.

**Non-goals:** Admin interface, contributor intake, paid accounts, bookmark/feed/chat, person verification, allowing Google account to bypass source rights or publication policy.

**Dependencies / sequencing:** An account may be enabled when approved independently of stable editorial v1 if its own legal/security/host gates are signed; it must never be mistaken for approval of source ingestion or public intake. If accounts are not selected for a given release profile, record signed disabled applicability/trigger while preserving the roadmap commitment. Coordinator maps hard dependency accurately without forcing all of DP-702 stable-v1 closure when qualified scope can approve the account separately.

**Acceptance criteria:**
- [ ] D-NEW-06.A1 Real owner-authorized new Google member signs up then re-logs as same stable Google sub (email changes do not duplicate identity), with exact origin/callback and protected headers.
- [ ] D-NEW-06.A2 Invalid/replayed state, nonce, signature, issuer/audience, cookie, CSRF, hostile origin, cross-site request and expired session all deny mutation and never create/store identity.
- [ ] D-NEW-06.A3 Member session grants zero Studio/review/admin/publication/intake capability; static pages and API responses expose no PII to public build, indexing, CDN or cache.
- [ ] D-NEW-06.A4 Logout invalidates one session, account deletion invalidates ALL sessions and the member row; retained WAL/backups/logs follow the signed erasure timetable and auditable completion/refusal.
- [ ] D-NEW-06.A5 Credentials, private DB, proxy origins, rate stores, HTTPS, no-store and loopback/MiniPC route readback all pass; absent/incomplete config disables service.
- [ ] D-NEW-06.A6 Mobile 320/390/768, keyboard, reduced motion, zoom, screen-reader and disabled/error flow are accepted; unauthenticated public-reader routes remain operational.
- [ ] D-NEW-06.A7 Rollback disables account endpoints without touching public projection or losing existing private audit in violation of retention; owner/security/legal approval references are current.

**Validation/proof:** Reuse existing local OIDC tests and adversarial loopback harness, then future permitted real Google test-account MiniPC canary; inspect proxy and headers/cookie behavior, SQLite 0600/dir 0700, backup/restore/erase, public host URL and reverse proxy. Retain sanitized evidence only, never tokens, secret or email.

**Documentation/data/migration:** Single owner-approved account launch/runbook and private SQLite data/retention registry, no new Postgres membership grant; alias to existing account OIDC activation document. Public route/SEO and privacy-policy updates under their existing owners.

**Completion receipt:** Not implemented/activated remotely; planning only. Future exact signed owner scope, Google registration/redirect, runtime hash, account lifecycle + erasure results, MiniPC before/after route/public readback and rollback record.

### D-NEW-07 — Revocation/correction distribution and immutable MiniPC release readback

Status: FUTURE; target mandatory FULL-PILOT and STABLE-V1 safety acceptance.
Depends on (hard proposed): DP-303, DP-308, DP-431, DP-510, DP-511, DP-502, plus B's forthcoming concurrent revocation authority ticket and C's updated public exact-wording serializers. Coordinate DP-704/705. Prime to resolve exact B/C new IDs.

**Problem:** Source-rights/provenance revocation can race capture, candidate promotion, a running worker, snapshot generation and CDN/public API caching. DP-431 stale-artifact cleanup on regeneration and DP-511 revalidation do not themselves prove immediate safe visibility on the actually served MiniPC host/CDN. A Mac green projection rebuild cannot attest distributed withdrawal.

**Outcome:** One documented, reproducible release-and-withdrawal operation ties private authority-event version to public projection generation and every served consumer; on revocation or accepted correction the public site/API/search/sitemap/index/JSON-LD/RDF/cache becomes safe within an explicit tested window or fails closed. All prior private history remains append-only and recoverable, including rollbacks.

**Traceability & constraints:** R24/R25/R38 and R39; B owns linearizable revoke/write-fence mechanism and rights review, C owns public schema/quote exactness/index removals; D owns deploy/cache/operational replay. No false public account, no auto-publication. No invented propagation latency guarantee; first measure and set a justified SLO before claiming one.

**Scope:** Transaction epoch/version/hash and revocation fence per protected dependency, checked by all operations at persistence/promotion/publication and projection read; durable dependency graph from public Statement/Finding/Quote/Person×Topic/Content/Trace to source rights, attribution, findings, review and correction versions; release manifest binds source code sha, migration/policy, MiniPC mirror hash, data/projection/public bundle/cache generation. Atomic/static pointer or equivalent supported deployment requires final public readback; older cache generations get explicit invalidation or denial/no-store by class. If cache purge fails, public route blocks/omits unsafe material until proven. Revision may remove stale projection-owned files but cannot delete origin evidence, retained legal holds, appeal/private reply or prior signed correction history. Provider outage does not prevent safe withdraw.

**Non-goals:** New event bus, polling every user client, exposing raw revocation ledger publicly, changing B's qualified legal policy or bypassing publication gate for a “fresh” correction.

**Dependencies / sequencing:** B first specifies exact lock/order/authority across external writers; C supplies consumer manifest for exact quote/translation/summary/navigation; D exercises release/correction under existing hosting topology. DP-704 rehearses complete path, DP-705 binds it to selected candidate. Pilot acceptance before bulk; revocation tests required even before first public factual record.

**Acceptance criteria:**
- [ ] D-NEW-07.A1 Simultaneous revoke vs capture/claim promotion/review/public-build resolves to one documented epoch; no later unauthorized candidate can republish revoked quote, including stale worker/retry.
- [ ] D-NEW-07.A2 A materially changed/expired source right, attribution or evidence decision identifies all affected public rows and sanitized outputs including old static files, API/search/sitemap/JSON-LD/RDF, browser cache/CDN and Persona×Topic summary.
- [ ] D-NEW-07.A3 Exact MiniPC code/migration/source/version/projection hash readback and public live host readback agree; stale bundle/cache is unavailable or omits affected content, never returns old quote under 200.
- [ ] D-NEW-07.A4 Correction/reply reanalysis and withdrawal preserve private immutable receipts and properly version public history without exposing private complaint data.
- [ ] D-NEW-07.A5 Partial deploy/purge failure and rollback restore a known-safe read state with before/after checksums, not stale released wording; emergency hold works even with LLM/provider offline.
- [ ] D-NEW-07.A6 Alert/health digest records withdrawal reason class, content count, delivery lag, cache failure, owner and action with zero private payload. Measured lag sets candidate release SLO; no unmeasured bound is declared passed.
- [ ] D-NEW-07.A7 Rehearsal is repeated against exact approved source/rights/release candidate after material migration/safety change; operator and owner accept verified rollback.

**Validation/proof:** Isolated PostgreSQL race harness with two workers plus external rights writer, deterministic priority barriers, negative stale epochs; regenerated public artifact before/after hash lists; MiniPC candidate, actual configured reverse proxy/CDN smoke after hold/correction and TTL/cache readback; release rollback restoration and public/private isolation. No actual production mutation in planning.

**Documentation/data/migration:** Bind existing revocation/DP-510/DP-511, projection cleanup/DP-431, source lineage, exact quote source-span and release manifest. Add only necessary fencing/generation fields with migration and rollback; immutable operator receipt and private contact route.

**Completion receipt:** Not implemented; planning only. Future race run ID, code/mirror/projection/cache fingerprints, live GET/search/sitemap results, measured delay and signed rollback.

### D-NEW-08 — Operator visual-quality capacity and exception time budget

Status: FUTURE; target limited pilot operator workflow, no implicit human reviewer staffing.
Depends on (hard proposed): DP-417 (Studio queue) and A/B's active ambiguity investigation/exception-policy ticket; C's correct-image fallback/alt text design. Coordinate DP-504/505.

**Problem:** No ordinary textual editorial reviewer exists. The owner estimated up to approximately five hours/week for quick mainly visual checks; current queue states could imply humans will approve all text/verdicts. A staff-time-free pipeline claim is invalid without measuring exceptions.

**Outcome:** One bounded operator worklist for decisions that genuinely require visual inspection (e.g. person-image correctness/licensing, image/no-image, attribution of visual caption where approved) and narrowly escalated unresolved evidence-policy decisions after automated attempt logs. It measures actual owner time and backlog without treating those minutes as textual verdict approval.

**Traceability & constraints:** R23/R34, R25. The 5h/week is planning availability, not a guaranteed staffing SLA, two independent reviewers, or a text-review throughput forecast. Automated process-text verification belongs to B, not visual operator queue. Reviewer independence/qualified legal authority cannot be invented from a single owner's approvals.

**Scope:** Deterministic queue reasons, visual asset provenance/source/rights and preview reference, one-click choose correct authorised image or none, append-only actor/action/time/asset decision, bounded duplicate grouping, expiry/priorities, short notes, no auto-contact. Per-case handling time and weekly rolling total; explicit opt-out/no-image fallback and public alt text. Separate “investigate source/claim” exception queue with automated prior attempts/evidence hypotheses, cost budget and only escalation of a concrete unresolved question. High-risk/dual-control unresolved remains held until B's accepted machine authority or qualified actor really satisfies its own rule.

**Non-goals:** Human fact-check on every claim, simulated second signer, replacing source authenticity with thumbnail judgment, image generation, fixed throughput promises.

**Dependencies / sequencing:** A/B specify meaningful exception conditions, C owns visual UI and safe no-image behavior. Use current Studio operator queues/annotation pattern, not create parallel editorial app. No launch-time assumption that owner is available every day.

**Acceptance criteria:**
- [ ] D-NEW-08.A1 Real image-choice sample yields licensed/identity-correct image or explicit none; absent/uncertain right or ambiguous person fails closed and does not block text-only authorized public record solely for lack of photo.
- [ ] D-NEW-08.A2 Queue items have reason, attempted automated investigation, required human decision and bounded time budget; no submission implies factual Finding verification.
- [ ] D-NEW-08.A3 Count/operator minutes/week, older unresolved items and per-reason median are reported; excess demand pauses optional image work or opts for no image without fabricating reviews or overriding policy.
- [ ] D-NEW-08.A4 Replay, stale source image rights and duplicate tasks preserve append-only audit and trigger correct public image withdrawal/readback with D-NEW-07.
- [ ] D-NEW-08.A5 MiniPC candidate and C public consumers prove no orphan/unlicensed image and zero text-verdict permissions from visual approval.

**Validation/proof:** Frozen identity/image/license/ambiguous cases, simulated owner time entries and duplicate reviews; actual operator sample before asserting capacity. Private redacted receipt, no raw photos stored in public test logs.

**Documentation/data/migration:** Extend Studio queue/prior image rights records if necessary; runbook for “none” and measured workload. Preserve no human ordinary reviewer premise.

**Completion receipt:** Not implemented; planning only. Future fixture/genuine visual acceptance, weekly measured minutes, queue age and public image omission/readback.

## Dependency and phase proposal for prime

| Phase and frontier | Primary work | Required proof before next |
|---|---|---|
| Phase 0 — ticket authority | R24/25/27/29–34/37–39 mapped to D-NEW and existing IDs; B revocation/verification, A source and C public output interface; preserve Q-306 and DP-701 dispositions | One DAG with real DP IDs, no cycles, no orphan AC, qualified external owner actions explicit |
| Phase 1–2 — first complete private source pilot | A source rights/capture and B autonomous semantics/context with C exact public Statement/Person×Topic/correction, D release/readback D-NEW-07 | Actually accepted MiniPC real bounded source→reader→correction, complete negative gates and source rights; NO bulk |
| Phase 3 — operational pilot acceptance | DP-704 partial first-pilot run or distinct acceptance proof as coordinator specifies; D-NEW-01 billing semantics, DP-506 caps, D-NEW-08 bounded visual acceptance, then an owner-bounded initial D-NEW-02 cost measurement and D-NEW-03 structural EUR cap proof before chargeable bulk | Quality, cost-attempt capture, privacy/public proof, correction, rollback, zero misattribution; owner scope accepted; no invented entitlement or paid trial |
| Phase 4 — permanent historic initial batches | D-NEW-05 subject to actual cost/quota and rights preflights, DP-214 separate 100-item tracer and DP-703 eventual three-family stable set | Versioned rights manifest, initial measured throughput, retry/cost bounds and active restrictive monthly cap; every public historical Statement exact source wording |
| Phase 5 — economics and recurring pipeline | Extend D-NEW-02 into provider comparisons/reset-cycle characterization, refine D-NEW-03 cap calibration and enable D-NEW-04 optimized incremental monitoring | True account access and quota units, measured vs estimates, approved EUR policy, energy method, source freshness |
| Phase 6 — stable-v1 cutover and ongoing monitoring | DP-701 qualified identity; DP-702 Q-306/307 and account/intake applicability; DP-703 real three-family launch set; full DP-704 rehearsal; DP-705 release sign-off; D-NEW-07 public/cache readback + D-NEW-04 health | GO-PUBLIC from authorized owner and actual MiniPC host, signed full rollback, production source and corrections. D-NEW-06 Google accounts activate only when their own independent external gate clears. |

Phase 4/5 ordering follows the master prompt's bulk-before-broad-provider-comparison roadmap. Initial cost measurement and monthly dispatch controls are necessary safety preflights for chargeable bulk, so a tightly scoped calibration after FULL-PILOT can occur at Phase 3, followed by extended comparisons in Phase 5. Neither paid trial nor large unattended historical import can precede FULL-PILOT acceptance. No full historical coverage or billing claim from a few pilot items. Maintain the 100-real-Content DP-214 and final three-family DP-703 thresholds until explicit owner policy change; the staged FIRST-PILOT adds a smaller *prerequisite* rather than replacing either. Product must show cross-person/same-person comparisons and correction in early full slice, not postpone its whole mission to Phase 6.

## Coverage and handoff to other lanes

| Requirement | D assignment | Cross-lane contract |
|---|---|---|
| R24 correction/reply/revoke everywhere | DP-704/705 + D-NEW-04/05/07/08 | B authoritative revocation and append-only event semantics; C serialized quote/history/nav; D cache and runtime readback |
| R25 private/public isolation, concurrent fences | DP-507/508/702/704 + D-NEW-06/07 | B epoch/transaction fencing across all writers; C public allowlist, no private membership/state leakage; D proxy/cache/host boundary |
| R27 permanent multilang historic subject refresh | DP-703 + D-NEW-05 | A source family and German OCR/transcript/rights provenance; B context/policy/translation; C Reader timeline |
| R29 GPT-6 native first, compare provider later | D-NEW-01/02 | A/B real quality/ASR/extraction milestones; no imagined GPT-6 API |
| R30 EUR10 target empirically and energy | DP-506 prior scope + D-NEW-01/02/03 | Finance units measured/estimated/unknown, real access and full attempt denominator |
| R31 ledger, caps, reset/outage | DP-230/504/505/506 DONE + D-NEW-01/03/04 | A worker source demand, B abstention on outage, no child when disabled |
| R32 cheap recurring vs bulk | D-NEW-04 and D-NEW-05 | A discovery/capture receipt, B reanalysis trigger, C freshness |
| R33 source/subject continuity, new events | D-NEW-04/05 | A source selection + discovery; B uncertainty/coverage; C disclosed cutoff |
| R34 zero text reviewers, ~5h visual | D-NEW-08, DP-702/704 exception bounds | B machine gate transition without fake dual reviewer; C image/no-image UI |
| R37 Google accounts / conditional intake/admin | DP-507/508 + D-NEW-06 | C access/UX; privacy/legal qualified Q-306, user cannot approve |
| R38 MiniPC release/drift/readback | DP-701–705 + D-NEW-07 | C web/index/cache contract, B revocation/test candidates, D mirrors and restore |
| R39 credible benchmark, failure abstention | DP-702/704 + D-NEW-02/07 | B primary benchmark/gold, D cost/quality correlations and actual host replay |

Critical asks for prime: resolve cross-lane ticket IDs before introducing Depends on pure DP tokens; preserve status table and historic checked ACs; status of account login local READY versus live BLOCKED is not DP-507 completion; stage cap measurement after integrated pipeline acceptance; do not file every shared revocation requirement twice. Separate hard ticket dependencies (only DP IDs) from external qualified decision, owner approval, route permission or milestone prerequisites, because the current repository checker parses pure DP tokens in Depends on.

## Remaining external owners and known gaps

- **EXTERNAL/PENDING-OWNER:** qualified Q-306/DP-307 Italy/EU privacy/rights/editorial decisions and counsel; DP-701 mark/registrar/handle/disclosure, selected public contact and domain+host ownership; selected source-family rights, disclosure and excerpt legal basis; future provider accounts/terms and paid trial ceiling; actual Google OAuth consent/client secret and member SQLite retention/backup-erasure; public release/signing authority. No model-generated counsel/legal “approval.”
- **BLOCKED implementation/acceptance:** meaningful approved provider route (DP-201..204) and full pilot real rights data; source/corpus DP-214 100-item manifest (18 included with UNKNOWN rights historically), DP-703 three approved families; actual MiniPC full source→public→correction; coherent mirror parity and rollback, live output; end-to-end revocation across cache; corrected billing classifications, measured energy and monthly reservation. Some are future capability tickets, not obligations to alter code now.
- **Immutable residual:** DP-701's missing pre-rename rollback bundle cannot be recreated by wishful proof. If owner chooses formally accepted canonical-only recovery policy it must be reflected in qualified decision and changed AC/dependency explicitly, not unchecked hidden gate.
- **Data limits:** current Groq route is ASR and named GROQ, not xAI Grok; Antigravity usage command gives quota/reset rather than guaranteed comparable token prices; native GPT-6 ChatGPT/Codex availability must be observed on exact user interface and is distinct from any API. Local electricity unknown without meter/baseline. A fixed EUR10 prediction from zero real workload is not a fact.

## Validation of packet (worker scope)

Read-only repository and exact tickets/code seams inspected; no source, test, DB, provider or runtime mutation. This packet is solely a planning handoff, so existing completed feature ACs remain checked only in their own historical tickets. All proposed D-NEW acceptance checkboxes are unchecked. Prime must assign actual DP IDs, deduplicate with A/B/C and migrate the material into canonical docs/tickets + PLAN/coverage matrix, then run documentary checks and mark this native packet absorbed. Git commit and the external Prompt2Prompt response are prime-only.

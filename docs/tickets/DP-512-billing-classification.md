# DP-512 — Truthful operation billing classification and retrospective reconciliation

Status: IN PROGRESS

## Active workflow — 2026-10-15, owner-requested independent ticket closure

The owner requested one Codex subagent on another original ticket while CoS
works. A bounded acceptance crosswalk found no fully closable original among
DP-215/229/233/304/422 without existing source/legal/runtime approvals. The
remaining executable DP-512.4/.6 digest gap is explicitly documented below:
health aggregation currently combines estimates with recorded measured labels
and turns UNKNOWN into zero. Root grants this worker path ownership of this
ticket, `health_digest.py`, `test_health_digest.py` and, if needed, a separate
real-PostgreSQL consumer regression. CoS retains Git/index/ref ownership and
`PLAN.md`; root reconciles the shared plan after settlement.

Skill source: `/Users/domenico/.codex/skills/code-implement/SKILL.md`, including
its Ponytail ladder. Step: reproduce the digest misclassification, then reuse
the existing queue-store receipt reader and `reconcile_operation_billing`
instead of adding another billing model, SQL writer or datastore. Existing
implementation at the current integrator revision is adopted unchanged for
receipt replay/conflict and unverified-billing semantics. No additional
dependency or external-provider integration is needed for this consumer fix.
Frontier: implementation, review, local/MiniPC disposable proof and full
Python verification complete. Root owns publication in the independent
checkout `/Users/domenico/Code/DP-512-health-review-20261015`, branch
`fix/dp512-health-cost-unknown-20261015`; the CoS checkout/index is preserved.
The single requested Codex subagent is settled; no disposable server remains.
Full closure remains blocked on the original independent billing evidence,
corrections/refunds, reservations and authoritative MiniPC acceptance. No
AC/status, source rights, production data or activation is authorized by this
slice. The existing PR billing/merge gates remain; root publishes an
independent review branch without using the CoS index/ref lease.

Ponytail source actually read before design is the maintained donor fusion
inside the canonical `code-implement` skill: upstream
`DietrichGebert/ponytail`, revision
`14a0d79548d4de8fc2de95c1b94bb0de63a739d3`,
`skills/ponytail/SKILL.md` (MIT). The skill's separate `internal ponytail`
locator was not found in the enabled Codex/Agent Skills or DStack package
skill trees; no separate internal file load is claimed. The fused ladder was
applied directly: existing canonical receipt reader/reconciliation, no new
dependency, writer, migration, service or billing authority.
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

## 2026-10-12 — Canonical PostgreSQL provider-receipt CAS, disposable only

Added an opt-in, deliberately **disposable-local-PostgreSQL-only** billing
classification seam in `poc/dichiarazioni_pubbliche/ops/billing_pg_fence_v1.py`
and 13 actual PG17 tests in `tests/test_dp512_billing_pg_fence_next.py`.
The tests launch a temporary PostgreSQL server and apply the **full actual
`db/schema.v1.sql`**, then insert canonical `provider_receipt` fixtures.
An independent client reads the unchanged production-named canonical
`provider_receipt` rows with `SELECT ... FOR UPDATE` and validates exact
`(operation_key, attempt)` uniqueness. A private `dp512_pg_state` CAS row
stores a fingerprint of all original receipt columns, and
`dp512_pg_event` appends immutable classification/correction events under
the same database transaction. Revision conflicts, same-event altered
payload, changed canonical receipts and duplicate canonical logical attempts
fail closed. A PostgreSQL trigger prevents rewriting or deleting original
classification events. This adapter does **not** alter canonical receipt
rows, install a real migration or create a worker/provider bill.

For a canonical `UNKNOWN` attempt with zero estimated ceiling, the
result remains `UNPRICED` with no measured charge or dispatch authority;
zero-valued `ESTIMATED_ONLY` is **still an estimate**. A canonical
`MEASURED_PROVIDER_COST` requires the exact recorded amount and a
source-reference token, but the reference is only locally supplied: the
result is `RECORDED_MEASURED_UNVERIFIED`, with `invoice_attested=false`.
The source-reference token is not emitted; a checksum is retained privately.
`EXTERNAL_PLAN` retains unknown bill and independent unknown energy:
no subscription entitlement or dollar charge is inferred. Monetary NaN,
negative amounts, unrepresentable fractional precision, estimated-to-measured
upgrades and event-key reuse across attempts are denied.

The tests verify failed attempt 1 and successful retry attempt 2 share a
canonical operation key and remain separate charges. Crucially the real
`QueueExecutionCostStore.operation_ledger_receipts()` **PostgreSQL consumer**
reads these canonical rows, then existing `reconcile_operation_billing`
keeps UNKNOWN separate from provisional estimated USD and does not count a
retry as a duplicate. Two independent PG clients racing the same revision
produce exactly one committed event; restart/new client idempotently replays
the identical event and a correction appends a second immutable event.
Synthetic provider receipt bodies containing private prompt/credential/URL
values remain unchanged in canonical private PG yet absent from the output.
No real invoice, provider plan, usage API, currency conversion, budget debit
or MiniPC runtime was used.

**RED→GREEN:** before implementation the new suite failed to import its
missing adapter. With the isolated PG17 schema the 13 new real-database
positive/adversarial tests are **GREEN**; Ruff lint/format also pass.
These rows demonstrate a meaningful canonical PG consumer integration and
transaction boundary, but not a qualified provider invoice or automated
reservation. **All AC-512.1–6 remain unchecked; DP-512 IN PROGRESS /
unattended billing-dependent dispatch NO-GO.** The remaining requirements
include production-owned additive migration, authenticated billing/account
and refund line matching, actual plan quota/energy, FX, budget reservation
under shared writer locks, MiniPC test and worker/health parity.

## 2026-10-14 — Fail-closed local energy label in disposable classification result

An actual disposable PostgreSQL 17 reproduction found that
`dp512_pg_record()` returned the full untrusted value of
`provider_receipt.receipt->>'local_energy_basis'` inside its otherwise
redacted private classification JSON. A synthetic canonical UNKNOWN
receipt containing `PRIVATE_TOKEN_PROVIDER_USAGE_VALUE` in that nested
field returned the marker verbatim, although the original DP-512 ledger
contract accepts only `UNKNOWN`, `ESTIMATED` and `MEASURED`. A historical
`LOCAL_COMPUTE_UNMETERED` label likewise escaped unnormalized instead
of expressing unknown energy. Neither value is defensible accounting
metadata or safe to copy to a private consumer/report.

The isolated PostgreSQL classification SQL now uses an explicit three-value
allowlist, returning `UNKNOWN` for missing, invalid or historical labels.
It preserves the immutable canonical receipt JSON unchanged and retains the
existing permitted `UNKNOWN`, `ESTIMATED` and `MEASURED` values. This fix
does **not** infer observed Wh, authenticate energy telemetry, establish a
cash amount, classify a bill as paid or activate dispatch. It changes only
the sanitized `local_energy_basis` field in the disposable classification
result; original fingerprint, append-only CAS/replay and all other monetary
fields remain on their existing paths.

Real disposable PostgreSQL test was **RED** before the change
(`PRIVATE_TOKEN_PROVIDER_USAGE_VALUE` surfaced instead of `UNKNOWN`),
then **GREEN** with raw receipt preservation, no private-marker leakage,
no invoice/dispatch authority and canonical-label roundtrips. The wider
DP-512/513/514 + policy suite passed **101/101** on the Mac including
isolated real PostgreSQL fixtures; scoped compileall, Ruff F821/F823 and
`git diff --check` pass. This is a source-only redaction/integrity
correction, not proof of real billing source rights or MiniPC runtime
acceptance. **DP-512 remains IN PROGRESS; AC-512.1–.6 stay unchecked.**
Authoritative invoice/usage and provider-plan evidence, exact corrections,
reconciliation, atomic dispatch reservations and MiniPC consumer parity
remain subject to their independent acceptance gates.

## 2026-10-15 — Truthful private health consumer, original ticket remains open

The owner-requested independent Codex worker fixed the already documented
health-consumer gap under AC-512.4/.6. The real digest now delegates its
receipt query to `QueueExecutionCostStore.operation_ledger_receipts` and its
classification/replay/conflict semantics to `reconcile_operation_billing`.
An exact repeated receipt is counted once; conflicting attempt identities
refuse a digest. Private digest schema v2 separately reports recorded
measured-labeled USD, provisional estimated USD, unknown cash attempts,
external-plan attempts, zero-cost labels and unknown energy. Billed USD,
plan quota and measured Wh remain null; invoice attestation and dispatch
authority remain false. `estimated_cost_usd_today` now contains estimates
only. The compatibility provider-group `cost_usd` is explicitly labelled
`RECORDED_OR_ESTIMATED_NOT_AUTHENTICATED`, for known budget-risk arithmetic.
Unknown cash or unallocated external-plan liability makes cost SLOs UNKNOWN;
a known sum already over the objective continues to show BREACH.

The reader uses an explicit half-open UTC day, with the existing canonical
started-at/else-completed-at timestamp semantics, rather than the database
session timezone or `now()` fallback. Undated receipts are not allocated to
a day by this reader; this slice does not claim exhaustive historic backfill.
Provider/operation/status grouping is retained and explicitly labelled as
**not source attribution**; true per-source attribution remains a separate
consumer-parity limitation. Only allowlisted aggregate data leaves the
reconciliation report: no receipt/operation identity, raw provider body,
untrusted status detail or credentials enters the digest.

Independent parent review found missing `local_energy_basis` still counted
as zero unknown-energy attempts. There is no attested not-applicable state
in this receipt model. The smallest canonical correction now counts absent
and explicit UNKNOWN energy consistently in both ledger aggregators, and
normalizes the report's absent energy label to UNKNOWN. Explicit ESTIMATED
and MEASURED labels stay distinct, and the immutable original receipt stays
unchanged. This is a read-model correction, not observed energy telemetry.

Fresh proof on the final code bytes:

- Five new health regressions first produced two failures/three errors; the
  final health module passes 8/8, including known BREACH with another UNKNOWN
  attempt, unknown-zero ceiling, exact replay/conflict and UTC offset handling.
- The missing-energy adversarial case first failed `1 != 2`; the final
  ledger regression covers missing, UNKNOWN, ESTIMATED and MEASURED without
  changing the original legacy value.
- `PYTHONPATH=poc python3 -B -m unittest tests.test_health_digest
  tests.test_operation_ledger tests.test_operation_ledger_schema
  tests.test_dp512_billing tests.test_dp512_reconciliation tests.test_ops_slo
  tests.test_queue_store tests.test_dp512_health_digest_20261015
  tests.test_dp512_billing_pg_fence_next -q`: **91/91 PASS**, exit 0,
  8.019 seconds. This includes 15 real disposable PostgreSQL cases.
- The new two-case consumer regression uses the full canonical schema and
  actual SQL/Python digest, proving UTC month-boundary inclusion/exclusion,
  unchanged canonical row hashes, UNKNOWN/recorded-cost separation and
  redaction. The same exact test ran on MiniPC: **2/2 PASS**, exit 0,
  2.406 seconds. All 255 bundled source/support files were SHA-256 verified
  before execution, with provider/production credentials absent. The test
  used its own temporary server, random port and disposable database only.
  PostgreSQL consumers were confirmed zero and the bundle was removed.
- MiniPC-tested SHA-256: `health_digest.py`
  `108bb3c04e4cdd6d9e9ef029a6799e39d22eee24aaf378169c617065a4d2971d`;
  `operation_ledger.py`
  `e33429896fdfb0629f96f25e37dc8cc845bf6a154e146ba6a1edb2cd7a7b19b3`;
  consumer test
  `9dd3602c1e828bb782fd9a87cd5b1b2a22ba05038192a595c7f8db31451b314a`.
- Ruff, scoped compilation and `git diff --check` PASS. No affected checked-in
  admission/source pin was found in the bounded config/tools/release/tests
  references to the two changed source files. No domain/publication behavior
  changed, so no new semantic benchmark is asserted.
- Local `code-review` Standards/Spec serial passes and independent parent
  review resolved the missing-energy finding; no remaining consequential
  finding in this eight-file slice. The parent separately reran 48/48
  focused checks. No new subagents, GitHub review or paid API were invoked.

The first CoS shared-checkout full suite was interrupted after this worker's
08:37 source/test overlay appeared. Its replacement detached run at committed
`25c94d1` excludes these DP-512 bytes. **Neither run proves this change.** A
single integrated full suite on the final stable DP-512 code was subsequently
started by root, log `/tmp/dp512-root-final-full-20261015.log`, and is
**FULL_RESULT_PENDING** at worker handoff (superseded by the final receipt below). No full suite was started by this
worker. The MiniPC proof above is an isolated candidate consumer test, **not
installation of the changed digest**, production ledger acceptance or a
complete AC-512.6 pass. No deployment, production data, provider call or
public/editorial state changed.

Original acceptance remains open:

| Original criterion | Proven slice / exact remaining gate | Closure owner and observable input |
|---|---|---|
| AC-512.1 | Synthetic classes and disposable canonical receipts; no independently observed authenticated billed attempt/plan allocation/energy. | Billing/account operator supplies authorized provider usage/invoice evidence and applicable measurements. |
| AC-512.2 | UNKNOWN/zero estimate and absent-energy negatives now reach the digest truthfully; real zero-fee/billing authentication remains unproven. | Billing/account operator supplies exact observed provenance; unknown stays unknown. |
| AC-512.3 | Existing canonical attempt replay/CAS tests pass; truthful real failed/retried billed attempts remain unobserved. | Runtime/billing operator provides authorized joined attempt and billing receipts. |
| AC-512.4 | Digest separates recorded/provisional/unknown/plan/energy and preserves original receipts; canonical historical correction/refund events and a complete safe backfill preview remain absent. | Ledger/billing integration owner delivers auditable immutable corrections/refunds and preview. |
| AC-512.5 | Digest UNKNOWN cannot imply healthy zero; no dispatch/reservation behavior was changed. | Queue/budget owner proves canonical atomic reservations, observed reconciliation and bounded operator action. |
| AC-512.6 | MiniPC disposable actual digest+PostgreSQL month-boundary/redaction 2/2 proven. Installed worker/scheduler/health parity, source attribution, concurrent attempts and original release/readback remain open. | Runtime operator installs the accepted revision and exercises the remaining original parity/concurrency matrix. |

**Status stays IN PROGRESS; AC-512.1–.6 remain unchecked; zero ticket closures.**
The fresh reporter remains 162 total / 90 DONE / 72 non-DONE, READY=0,
PLAN/files agree. The bounded alternative-closure scan found existing external
frontiers on DP-215.9 (selected real Garlasco sources/SI/rights), DP-229.8
(independently attested challenger/incorporation/qualified waiver authority),
DP-233.10 (approved parliamentary source-family rights), DP-304.1 (complete
approved field/purpose/retention and qualified review), and DP-422.1
(approved populated projection, declared dependencies and live route readback).
No extra hardening or fabricated closure was substituted for these inputs.

Handoff: root/prime acquires these eight owned paths only:
`poc/dichiarazioni_pubbliche/health_digest.py`,
`poc/dichiarazioni_pubbliche/operation_ledger.py`,
`tests/test_health_digest.py`, `tests/test_operation_ledger.py`,
`tests/test_operation_ledger_schema.py`, `tests/test_dp512_reconciliation.py`,
`tests/test_dp512_health_digest_20261015.py`, and this ticket. CoS retains the
index/ref/commit/push lease and PLAN/receipt ownership. At this handoff the
slice is **BLOCKED_UNPUSHED** on that integration lease and pending final suite;
root owns acquisition, focused review, coherent commit/push/readback and plan
reconciliation. PR creation remains held by the existing automatic-review
billing guard; PR/CI/merge and installed-consumer gates remain distinct.


## 2026-10-15 — Root final verification and review-branch delivery

The single requested Codex subagent finished and its eight-file result was
acquired and reviewed. Full Python over the final source/test candidate:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover
-s tests -q` completed **3690/3690 PASS in 542.708 s**, log
`/tmp/dp512-root-final-full-20261015.log`. The terminal session was unavailable
on later readback, so no recovered process exit-code claim is made; the log
contains the complete unittest `Ran 3690 tests` / `OK` result and successful
restore drill. No test process remains. The seven source/test files in the
publication checkout were byte-compared with that candidate; the later
changes are documentation only. CoS's separate **3681/3681** isolated run
was on source `25c94d1`, excluding DP-512, and is not used as proof here.

Publication starts from CoS's settled documentation head
`63f60e9`, preserving all three code fixes and its receipt unchanged. Root
uses the separate review checkout/branch named in Active workflow, stages
only the eight delivered files plus this tranche's PLAN checkpoint, and
pushes that branch with actual remote SHA readback. This supersedes the
worker-handoff BLOCKED_UNPUSHED lease condition once remote equality is
verified; it does not claim main integration or deployment. Shared integrator
DP-512 WIP is retained byte-identical, owned by this tranche, pending
prime integration; no reset, stash, clean or foreign staging is performed.

Local Standards/Spec review has zero remaining consequential findings after
the missing-energy correction. Repository contract, focused tests,
MiniPC candidate proof and whitespace checks remain green. PR readiness:
UNKNOWN liability stays explicit in health JSON and cost SLOs, already
provable overspend remains BREACH, and no receipt/operation identities or
provider payloads enter the new aggregate. No billing/dispatch authority,
schema migration or installed runtime change is introduced.

`PR_HELD_AUTOREVIEW_BILLING_GUARD` remains active until the linked account's
personal and repository settings are verified OFF or the owner accepts the
possible consumption. Do not open a PR solely to trigger reviews. Once
unblocked, review this branch against the existing integrator (or include
its parent tranche when targeting main), run required CI/review-thread/merge
gates, then prove installed consumers separately. DP-512 remains IN PROGRESS
for the six original criteria and their missing evidence in the table above.

Source commit `52df2048bff55fac19af6e4cce12f4f9091575ea` was pushed to
`refs/heads/fix/dp512-health-cost-unknown-20261015`; local HEAD and actual
remote ref were read back equal. `verify_main_delivery.py --review-check`
returned `REMOTE_BRANCH_SAVED`, with clean publication checkout. Main
remained `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe` and CoS integrator
remained `63f60e9dc54938957c849959cd3b66d411935495`. No PR was opened,
no merge/deploy occurred. The subsequent receipt checkpoint changes only
PLAN and this ticket; the tested source hashes above remain unchanged.
Root retains recovery/integration ownership of the eight shared-checkout
DP-512 WIP files, saved on this remote branch, until the prime acquires the
exact committed slice. The independent review checkout is clean and its
branch is intentionally retained for that integration. No stash or worker
process remains in the publication checkout.

## 2026-10-15 — Chat On Steroids CoS02 integrator acquisition

The newly assigned CoS02 prime acquired the seven source/test files as exact
byte matches of the already published `70a5ef8` review checkout, then replaced
the integrator's older ticket receipt with the complete previously delivered
ticket. The integrator retains the historical commits and their original
acceptance states; this handoff is not a second implementation claim.

The new prime reran 91/91 focused unittest checks, scoped Ruff, compileall
and whitespace verification on these integrator bytes. No billing provider,
production database, user data, source publication or paid dispatch was used.
Technical DP-512 acquisition does not close AC-512.1–.6: independently
authenticated billing/refund provenance, atomic production reservations,
approved historic correction replay and installed MiniPC consumer parity
remain subject to real evidence and separate review/release gates.

### CoS02 local two-axis code-review correction — source-cost SLO

Spec review exposed that `build_slo_measurements` interpreted the largest
provider/operation/status billing group as the cost of a *source*. The canonical
receipt reader does not return a source-authoritative allocation, and the
digest already sets `provider_grouping_is_source_attribution=False`. Therefore
the old per-source ratio could falsely report `OK` for provider groups without
any source attribution, or falsely name a source-level `BREACH`. A new
no-uncertainty regression plus the existing known-global-breach case both
failed before the correction (respectively `OK` and `BREACH` rather than
`UNKNOWN` for the source-cost SLO). The source-cost measurement now remains
`UNKNOWN` until source-bound cost provenance is available; known global
budget overspend continues to report `BREACH`. The operator action no longer
claims that a provider grouping identifies the editorial source. This is a
fail-closed consumer refactor, not a new authenticated billing statement or
completion of AC-512.4/.5.

TDD/verification on the corrected integrator: two regressions RED (source-cost
`OK`/`BREACH` without a source identity), then the complete health/SLO/
operation-ledger/reconciliation selection **45/45 GREEN**; scoped Ruff and
repository contract PASS; whitespace check PASS. Serial code-review axes:
Standards found no remaining consequential issue in the bounded correction
(no new writer, store, schema, dependency, data exposure or provider access).
Spec review confirmed fail-closed UNKNOWN per-source and known global BREACH,
with all six original DP-512 AC still open. External source allocation, real
billing and installed consumer acceptance were not fabricated.

## 2026-10-15 — CoS02 continuation: append-only refund/correction candidates

The original AC-512.4 gap was missing historic adjustment receipts, not
permission to rewrite canonical provider_receipt or treat caller-provided
statement references as invoices. Reused the existing disposable PostgreSQL
classification/CAS seam (ops/billing_pg_fence_v1.py) rather than creating
another billing authority, provider path, dispatcher or production migration.
The new DisposableBillingPgFence.adjust accepts only a previously classified
**recorded-measured** canonical attempt, version/revision, bounded positive
amount, exact event/kind and operator-supplied evidence reference. It records
REFUND, CORRECTION_UP or CORRECTION_DOWN under an append-only trigger;
each event shares the existing per-receipt revision lock and stores a fingerprint
of unchanged original receipt bytes. Resulting balances are explicitly named
unverified_net_recorded_usd: neither the reference nor its checksum
authenticates a provider statement, authorizes spend, or confirms cash settlement.
No canonical receipt or public data are rewritten, and no provider credentials
or free-form bill bodies are returned.

Three real canonical-schema PostgreSQL tests first failed RED because the
adjust interface did not exist. After implementing exact immutable event
replay, restart behavior, negative/over-credit rejection, concurrent client
CAS and redaction, all **18/18 PostgreSQL fence tests passed**. A separate
review found a consequential double-credit alias: reusing one source reference
as REFUND then as CORRECTION_DOWN could pass an event-kind-scoped uniqueness
check. One adversarial regression failed RED; the reference uniqueness is now
receipt-wide irrespective of event kind, enforced both by table constraint and
re-application index for existing disposable test schemas. Final scoped
billing, digest and ledger regressions: **38/38 PASS**, Ruff and whitespace
checks PASS. The next full-source suite and MiniPC disposable readback must be
recorded separately against their exact SHA, not inferred from this focused
test. No production migration/install, bill matching, reserve/debit authority,
real refund, invoice attestation or ticket DONE is claimed.

**Original AC-512.4 remains OPEN** for independently observed, authenticated
provider/statement correction evidence, full historic backfill preview,
integration into authorized production canonical migration/consumers and
actual reconciliation. AC-512.1–.3 and .5–.6 remain OPEN for the previously
specified billing, reservations and installed-consumer proofs. This is a
substantive independently testable technical slice, not a new ticket or
substitute for real money movement.

### CoS02 final security/standards review before delivery

The local two-axis Standards/Spec review identified an additional security
regression opportunity in the existing subprocess seam: libpq credentials
embedded in a password-bearing DSN would be exposed as part of the native
psql argv. A new negative test was RED (constructor incorrectly accepted
the URI); the same disposable fence now rejects DSNs with URL passwords.
Authentication for a properly configured localhost test server can still use
the native libpq credential mechanism without sending passwords in CLI
arguments. The final scoped reconciliation/billing/health set is **39/39
PASS**, with scoped Ruff and diff checks PASS. The new adjustment API,
database schema and ticket remain source-only/disposable; no authenticated
invoice, external provider charge, live migration or cash refund has been
produced by this change.

## 2026-10-15 — CoS02 cumulative PR review: adjustment lineage
Independent two-axis review of Draft PR #25 reproduced a P1 cross-consumer regression: append-only DP-512 adjustment advanced shared CAS state without appending a classification event, so DP-513 and DP-514 incorrectly rejected a valid refund candidate. Isolated PostgreSQL RED tests covered classify → observe → adjust → replay/observe/read. The corrected readouts verify contiguous immutable revisions from **both** DP-512 event families and their original fingerprints; DP-514 observations bind to the latest classification revision, not the unrelated adjustment revision. Unverified credits never reduce attested spend or authorize dispatch; reclassification still invalidates stale observations. These are disposable source tests, not real invoice, bill matching, production migration, worker install or finished AC-512.1–6.

## 2026-10-15 — Draft PR #25 health consumer review corrections
Three existing PR review comments reproduced genuine source bugs: inferred `ZERO_COST` receipts without attested free usage falsely returned healthy global spend; legacy receipts with neither timestamp disappeared from the UTC daily read due to NULL comparisons; binary-float summation of exact decimal costs `0.1 + 0.2` breached a 60% warning boundary with a 0.5 USD cap. Three RED regressions cover those cases. The digest treats unverified zero-cost as **cash uncertainty**, preserves decimal monetary aggregation through the SLO decision, and retains the canonical half-open UTC timestamp filter **without inventing a date** for legacy undated receipts. A separate count of permanently undated receipts makes the daily cash SLO `UNKNOWN` until their liability is independently resolved, while excluding them from fabricated daily totals. These are offline/disposable safeguards, not authenticated invoices, provider zero-cost attestation, a source-approved daily budget, installed consumer parity or original AC-512 closure.

An independent subsequent review reproduced two further false-OK cases for `ESTIMATED_ONLY` zero upper bounds and locally recorded `MEASURED_PROVIDER_COST=0`, both without independently attested free usage; both now remain cash-uncertain. It also found a fractional budget ratio just above 60% rounded to exactly 0.6 when converted to float before the SLO evaluator. The evaluator now accepts `Decimal` for the exact threshold decision, converting only the informational `measured` field to JSON number afterward. Undated historical receipts are separately counted, never attributed to the current or an invented historical day; authenticated dating/backfill is still required. No provider bill, refund or actual zero-cost confirmation is asserted.

## 2026-10-15 — CoS02 NEXT 14:33 MiniPC admission checkpoint (source-only)

The shipped source candidate in Draft PR #25 is commit `27c21ba5485983eea0b45e29782f8d73b32df863` (not merged or installed). The read-only merge-thread/check gate passed on that commit with completed CI and zero unresolved threads, but this does **not** grant deployment, publication or original acceptance. A read-only exact-commit-to-MiniPC-mirror inventory checked 189 changed paths and found **36 DRIFT, 153 MISSING, zero MATCH**; a single-file overlay cannot claim coherent worker/scheduler/health parity. No live service restart, production migration or billing dispatch was performed.

The exact Git-archive candidate was instead extracted in an owner-private, non-runtime temporary directory on `minipc` and run with a cleared inherited environment and disposable local PostgreSQL. `tests.test_dp512_billing_pg_fence_next`, `tests.test_dp513_usage_attribution_pg_next`, `tests.test_dp514_monthly_liability_pg_next` and `tests.test_dp512_health_digest_20261015` passed **57/57**, exit 0. This proves the new source can run its isolated billing tests on Linux, **not** the installed consumer or a billed provider transaction. Canonical production PostgreSQL was queried only in read-only mode: **63** existing provider receipts, all `ESTIMATED_ONLY`, **0** non-null measured costs, **0** permanently undated receipts, **0** populated `operation_key`/`request_id` fields, and **no `dp512_pg_state` table**. No invoice, source-verifiable attempt join, usage statement, refund, shared live reservation, migrated fence or independent cash-zero attestation was inferred from these counts. **All AC-512.1–6 remain unchecked; DP-512 stays IN PROGRESS.** Before live activation: review and admit the cumulative source/mirror transition and rollback with actual writer/consumer parity, then reconcile authentic provider billing and budget authorities without fabricating history or relaxing UNKNOWN/hold.

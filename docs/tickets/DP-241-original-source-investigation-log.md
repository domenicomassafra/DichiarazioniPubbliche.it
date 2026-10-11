# DP-241 — Active original-source recovery and finite investigation log

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-209, DP-213, DP-225, DP-228

## Problem

Existing reviewed original-source resolution follows known derivation edges but does not by itself guarantee active research when identity, time, montage or full wording is uncertain. A queue labeled pending is not an investigation; many copies of one clip are not corroboration.

## Outcome

A bounded, accountable Source Recovery attempt plan seeks the exact original or fuller context through several distinct approved methods and records why each attempt succeeded, failed, exhausted budget or remained unresolved, then opens a narrow exception with a concrete question. Newly found versions trigger revalidation, not silent historical overwrite.

## Traceability & constraints

R05/R10/R23, Q09–Q11, B owns factual uncertainty and final machine authority; no invented query/URL, no uncontrolled crawling or copyright assumptions.

## Scope

Reuse DP-225 original-source resolver, DP-228 scoped research plan, DP-213 Coverage Needs and DP-511 source revalidation. Deduplicated attempts to find longer originals, official primary record, transcript alternative, original poster, contemporary archive, metadata, independent copy and missing context. Record explicitly validated query/URL, expected evidence role, family/lineage, discovery receipt, legal fetch guard, success selector/hash, evidence of why likely original, attempt cap/cost, next retry triggers and temporal relevance.

## Non-goals

A blanket truth verdict, web-wide research engine, model-generated citation URL, unbounded paid search or production publication.

## Dependencies and sequencing

Hard core discovery/coverage/resolver/research plan. Soft B clarification/insufficiency, DP-236 rights, D attempt budgets, source-family approval external.

## Acceptance criteria


- [ ] `AC-241.1`: A failed shortened/edited clip case yields a versioned plan with at least two genuinely distinct permitted lookup strategies and exact target question; attempts are provenance-bound and deduplicated by original lineage.
- [ ] `AC-241.2`: A found longer primary source binds new immutable Capture/version, candidate context and exact locator; does not upgrade uncertain attribution without B's evidence gate.
- [ ] `AC-241.3`: Copies of the same source count as one derivation lineage, and a wrong person/changed date/unsupported claim holds despite many matching URLs.
- [ ] `AC-241.4`: Missing search/fetch permit, exhausted budget, outage and not-found record different actionable reason codes with retry/new-evidence triggers; no endless loop or guessed success.
- [ ] `AC-241.5`: Repeated identical attempts do not regenerate costly work; materially changed sources trigger DP-511 reanalysis/hold provenance and preserve historical records.
- [ ] `AC-241.6`: MiniPC pilot logs and private Studio display exact attempts, unresolved question, remaining source-family gaps and next allowed action without public privacy leak.

## Validation / proof

Bounded real authorized clip/text or independently built rights-allowed test source; source resolver before/after hash, distinct upstream lineage, attempt counts/cost/outage simulation, persisted MiniPC Coverage Need receipt, exact negative.

## Documentation, data, and migration impact

Add attempt-level facts to existing discovery/Coverage Need histories or one narrow additive log; retain immutable query/fetch receipts and caps. D owns background execution timing.

## Completion receipt

**2026-10-11 — bounded source-only partial prototype, NOT a real investigation:**
`poc/dichiarazioni_pubbliche/original_source_investigation_v1.py` and
`tests/test_dp241_original_source_investigation.py` add opt-in private
source-recovery planning/reconciliation over existing DP-228 ResearchAssignment,
DP-237 exact source/Capture/Passage resolver, DP-225 root-derivation resolver
and DP-236 per-operation source use decisions. The plan requires two distinct
permitted method families (not two mirrors/adapters of the same method), exact
source/version/quote selector, reviewed query references, bounded attempt/US-dollar
caps and deterministic no-dispatch identity. Result reconciliation distinguishes
NOT_FOUND, CHECKED_INSUFFICIENT, OUTAGE, RIGHTS_BLOCKED and COST_BLOCKED,
collapses provenance duplicates, rejects wrong person/date/unsupported fuller
quote, holds changed source versions for DP-511 reanalysis, and validates plan
integrity and receipt replay. **16/16 synthetic focused tests PASS** at the
initial source checkpoint; later integrity regressions are recorded below.
The stored references, `APPROVED` lineage/rights annotations and receipt hashes
are caller-supplied in this standalone fixture, not real authorities or proof
that lookup/search occurred. No source was fetched, no query was executed, no
provider used, no audit ledger persisted, and no Studio/MiniPC readback performed.
**All AC-241.1–.6 remain open** until end-to-end verified source, permission,
persistence, independent review and MiniPC acceptance.

**2026-10-11 — bounded receipt replay and attempt-cap integrity follow-up:**
Two public-contract regressions failed against the previous reconciler:
(1) three different attempt receipts for a plan capped at two could still
produce `VERIFIED_PRIVATE_SOURCE_CANDIDATE` if the third carried a valid
synthetic candidate, and (2) the same immutable discovery receipt SHA-256
could be attributed to two distinct planned attempt IDs, falsely counting
independent checks. `assess_recovery` now rejects those inputs before candidate
assessment with `DP241_RECEIPT_ATTEMPT_CAP_EXCEEDED` and
`DP241_DISCOVERY_RECEIPT_REUSED`, while identical receipt replay under the
same attempt ID remains idempotent. **18/18 focused DP-241 tests PASS; 51/51
adjacent resolver/research/rights/source tests PASS**; Python compilation PASS.
Scoped Ruff check and `git diff --check` PASS.
These are synthetic local receipts only; neither external attempts nor source
permissions were executed or verified. Status stays IN PROGRESS and all six
acceptance criteria stay open pending independent operational proof.

**2026-10-11 — private provenance-linked attempt timeline and append-only local
journal (second wave, no network or production write):** The existing read-only
`assess_recovery` validated the overall plan and source-recovery receipts but
exposed no attempt-by-attempt operator view, source-family gaps or durable
history. `inspect_recovery_timeline` now reuses that validated reconciliation
and projects each planned method in deterministic **plan order** (not inferred
attempt chronology), including its exact assignment/attempt ID, source-family
ID, validated-query reference and digest, two per-operation permission digests,
distinct discovery receipt SHA-256, result, spent USD and remaining/untried
source-family gaps. The case is bound to the existing Coverage Need, logical
Content, immutable Capture ID/version SHA, Passage ID/selector and locator
fingerprint. It carries the reason code and next manual trigger, distinguishing
not-found, rights/cost/outage waits, DP-511 source-version staleness, held
wrong-speaker/date/context candidates and private original-root **candidates**.
Two receipts resolving to one derived-source root count as **one** root, not
independent confirmation; conflicting/reused receipts still fail closed via
`assess_recovery`. All dispatch, independent-receipt, human-review and public
authority flags are false.

An **opt-in, owner-created** local `LocalSourceRecoveryTimelineJournal(root)`
persists those metadata-only snapshots under a private 0700 root and per-plan
0700 directory, using deterministic content-addressed 0600 JSON files,
`O_EXCL` plus fsync, exact per-plan readback, SHA-256 filename/content
agreement and a 32-snapshot cap. Recording identical receipts is idempotent;
changed decisions append a separate immutable snapshot without overwriting
older states. Root/case/file ownership, permissions, symlinks and tamper
checks fail closed. `recorded_local_at` is the *local file recording time*,
**not** the external attempt time or evidence of successful fetch. Since
human-authored questions can include private source quotations, **only their
SHA-256** is persisted in the journal; the original question must be looked
up in an independently authorized Coverage Need. No raw query, source body,
passage text, URL, headers, credential or candidate proof object is stored.

**TDD receipt:** missing timeline and journal APIs were RED; synthetic tests
became GREEN for exact per-attempt lineage/replay, stalled source version,
hold on mismatched person, duplicate-root collapse, a private question/token,
immutable snapshots/reopen, tampered-file replay, unsafe permissions and
symlinks. **25/25 focused** and **85/85** focused+adjacent (DP-225 source
resolver + disposable PostgreSQL, source preflight, DP-228 research plans,
DP-236 rights, DP-319 attempt logs and source span) pass on the local Mac.
These remain **caller-supplied** synthetic rights/receipts and source IDs;
the journal is a private operator-workflow prerequisite, not an attested
fetch/rights audit ledger or proof of external query execution.

**AC-241.1–.6 remain OPEN.** AC-241.1/.3/.4/.5 have partial deterministic
planning and honest readback, but not real legal/authorized multi-method
attempts, independent lineage/identity review, a persisted DP-511 external
mutation/reanalysis receipt or budget-provider transaction. AC-241.2 needs
a genuine new immutable Capture/Passage/context after source review, not a
fixture. AC-241.6 needs an authorized Studio frontend/runtime integration and
MiniPC pilot log with real unresolved question/source-family gaps and privacy
acceptance. No provider search/fetch, MiniPC change, public projection,
publication or reviewer authority was introduced.

### 2026-10-12 — disposable canonical PostgreSQL source and attempt CAS slice

Added `poc/dichiarazioni_pubbliche/original_source_investigation_pg_v1.py`
and `tests/test_dp241_recovery_pg_next.py`. The explicit opt-in adapter
exercises real canonical PostgreSQL `source`, `content_item`,
`content_capture`, `passage` and `private_source_rights_record` tables in a
disposable loopback cluster. The target is checked against the exact
Source→Content→Capture→Passage join, capture SHA, passage SHA, selector and
character span. A current **single unrevoked rights leaf** must be CLEARED,
reviewed, unexpired, and allow `DISCOVER_METADATA` plus `FETCH`. Cleared
capture metadata alone grants nothing. Newer/ambiguous Capture versions,
holds, denied/expired/revoked rights and foreign references block mutations.

The adapter's disposable-only tables persist plan identity and append-only
`RESERVED`/`COMPLETED` events. Transitions use SERIALIZABLE PostgreSQL
transactions, per-plan advisory locking, expected revision CAS and
request-key replay. Reservation persists before hypothetical billable
work; crash/restart without a completion receipt fences duplicate work.
Identical receipt replay is idempotent; conflicting completions and reused
discovery SHA across attempts are rejected. Readback reconstructs receipts
using existing `assess_recovery` and `inspect_recovery_timeline`, retaining
the original DP-241 family/cost constraints. Stored data contains bounded
IDs, result codes, digest and spend metadata, never questions, original
quotes, URL, private source bodies or credentials.

**Authorization boundary:** this is a disposable PostgreSQL analogue of the
existing DP-319 durable reservation/replay contract, not a replacement for
the independent DP-319 SQLite store or a production common scheduler.
`install_fixture_schema()` is restricted to explicitly opted-in loopback
`dp241_disposable`. Synthetic fixture rights/reviewer references do **not**
prove qualified approval or independent search/fetch; `FOUND_CANDIDATE`
requires external original-source proof and is not emitted by this adapter.
No provider, network search, real spend, publication or MiniPC data mutation.

**Validation:** real PostgreSQL source join, competing reservers, restart,
idempotent and conflicting replay, immutable event trigger, two separate
planned methods, reused discovery receipt, missing/forged original proof,
version replacement, rights revocation even after reservation, cross-source
identity, expired/incomplete rights, and absence of secret text from attempt
tables. This is technical preflight only; no authentic DP-511 reanalysis,
Studio readback, original newly captured source or MiniPC source-family
investigation is claimed. **All AC-241.1–.6 stay unchecked, IN PROGRESS.**

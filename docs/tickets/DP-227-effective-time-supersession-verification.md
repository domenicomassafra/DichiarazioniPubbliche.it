# DP-227 — Effective-time, interval and supersession verification

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-215, DP-210

## Problem

Statement-date cutoff prevents future evidence from judging an earlier statement, but that
does not prove which law, policy, dataset, office or record version was actually effective
at the relevant time.

## Outcome

Add first-class deterministic verification for valid-from, valid-to, reference period,
superseded version, observed date and publication date. A source can be authentic yet
temporally inapplicable.

## Acceptance criteria

- [x] Pure selector prevents a version effective after the claim time from proving earlier
  status.
- [x] Reviewed superseded-at state prevents the old version from masquerading as current.
- [x] Open-ended and bounded intervals use explicit start-inclusive/end-exclusive semantics.
- [x] Publication date, observation date, effective interval and reference period remain
  separate.
- [x] Conflicting overlapping approved versions become UNRESOLVED.
- [x] DP-215 TEMPORAL_CUTOFF now consumes persisted evidence valid_from/valid_until and
  applies start-inclusive/end-exclusive version-at-time semantics before verification.
- [x] SUPERSEDED/RETIRED evidence without a reliable valid_until fails closed rather than
  being treated as current merely because its publication date is old enough.
- [x] Reanalysis is triggered when a load-bearing source receives a reviewed supersession.
- [x] Full suite and MiniPC canary cover law, policy and statistical fixtures.

## Completion receipt

Local effective-version selector plus real Source Intelligence/verification-path
valid_from/valid_until integration added 2026-10-05. The local executable contract separates
HISTORICAL, CURRENT and explicit LATER_OUTCOME scopes; offline law/policy/statistical
fixtures prove that reference/observation metadata cannot backdate future publication,
stale records cannot become current truth, and incompatible authority overlap fails closed.

The local `supersession-reanalysis-v1` bridge now proves the reviewed-supersession trigger
contract without changing shared queue/schema state. It accepts only an `APPROVED` review
explicitly bound to the exact revalidation `event_key` for a DP-511 `HOLD_REQUIRED`
load-bearing `OFFICIAL_VERSION_SUPERSEDED` decision, verifies the immutable before/after
snapshot refs and decision event key, and binds old/new
source/version/content hash/effective intervals plus the affected claim/finding IDs into one
deterministic reanalysis request. Exact replay returns the same request, per-claim reanalysis
trigger and job IDs; any bound version/hash/date/dependency change creates a different
request identity. The bridge is pure and performs no finding/publication mutation.

The persisted runtime consumer now closes the reanalysis AC without modifying the concurrently
dirty queue/schema files. `supersession_reanalysis_runtime.py` invokes the canonical bridge and
atomically writes exactly one existing-schema `reanalysis_trigger` plus one canonical
`REANALYZE_CLAIM` `processing_job` per affected claim. Trigger metadata and job payload retain
the exact `review_event_id`, `reviewed_entity_ref`, DP-511 `event_key`, immutable before/after
snapshot/version/hash/effective-time bindings and affected Finding IDs. Exact replay is
idempotent: the same request reuses the same trigger/job IDs and creates no duplicate rows;
pre-existing or relationally invalid claim/finding bindings fail closed and roll back the
whole request. A disposable PostgreSQL acceptance test proves two affected claims persist as
two triggers + two queued jobs, replay remains 2 + 2, an unrelated Finding binding rolls back,
and existing Finding `publication_status` values are unchanged. This consumer only schedules
reanalysis; it has no Finding/publication mutation path. Focused contract + PostgreSQL runtime
acceptance is 16/16 PASS.

Final acceptance 2026-10-06: the integrated repository suite is **1567/1567 PASS** with the
restore drill exact. An isolated MiniPC `/tmp` bundle ran current `test_effective_time`,
`test_supersession_reanalysis` and `test_supersession_reanalysis_postgres` with production
PostgreSQL environment variables removed and its own PostgreSQL 18 temporary cluster:
**27/27 PASS**. The effective-time fixture covers historical law, superseded/current policy,
future/historical statistics, later-outcome statistics and conflicting authorities; the
persisted consumer proves exact reviewed-event binding, idempotent per-claim trigger/job
creation, Finding-ID audit retention, unrelated-binding rollback and unchanged publication
status. The temporary cluster/bundle/processes were removed afterward. No production
DB/provider/deploy/config path was touched.

## Canonical evidence effective-time persistence reconciliation — 2026-10-07

A later integrated audit found that the verification read path had been temporarily masking a
schema gap: `approved_verification_evidence()` exposed `valid_from=NULL`, `valid_until=NULL` and
`record_status=ACTIVE` because those fields were not actually persisted on `evidence`. That
fallback has been removed. The canonical `evidence` table now stores nullable `valid_from` and
`valid_until` dates plus a bounded `record_status` (`ACTIVE`, `SUPERSEDED`, `RETIRED`, `EXPIRED`), and the
new additive `20261007-add-evidence-effective-time-state.sql` migration is replay-safe.

Unknown effective dates remain SQL `NULL`; no date is inferred from publication, fetch,
observation or reference-period metadata. `QueueRuntimeStore.upsert_evidence()` validates exact
ISO dates and start-inclusive/end-exclusive interval ordering before persistence. A previously
unknown endpoint may be filled once, but a later conflicting non-null effective date fails closed
with `EVIDENCE_EFFECTIVE_TIME_CONFLICT` and leaves the persisted row unchanged. Version state is
monotonic for the generic evidence upsert: `ACTIVE` may advance to `SUPERSEDED`, `RETIRED` or
`EXPIRED`; stale `SUPERSEDED`/`EXPIRED` state cannot be replayed back to `ACTIVE`, and either may
advance to terminal `RETIRED`. `EXPIRED` does not imply or manufacture an expiry date: without a
persisted `valid_until` it remains stale and fails closed; with an explicit `valid_until`, the
normal start-inclusive/end-exclusive interval semantics apply.

The evidence-fetch worker now passes `valid_from`, `valid_until` and `record_status` from the
bounded job payload into canonical persistence. The verification read path consumes those actual
persisted columns. A disposable-PostgreSQL acceptance test creates both an updated fresh schema
and a pre-migration legacy `evidence` table, applies the migration twice, and proves the resulting
effective-time column/constraint contract is identical. The same acceptance proves legacy rows
retain unknown dates as `NULL`, persisted stale state survives replay, conflicting intervals are
refused without mutation, and a persisted `SUPERSEDED` record with no reliable `valid_until`
reaches DP-215 Source Intelligence and is rejected with
`SUPERSEDED_VERSION_WITHOUT_VALID_UNTIL`.

Focused DP-227/queue/worker acceptance after this reconciliation is **92/92 PASS**; compileall and
`git diff --check` pass. This reconciliation changes no publication decision, does not invent an
effective date, and does not touch production DB/provider/deploy/config paths.

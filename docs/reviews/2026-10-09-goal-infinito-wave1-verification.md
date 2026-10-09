# GOAL INFINITO — wave 1 integration checkpoint — 2026-10-09

This is an execution receipt, not a second backlog. Continue to use
`PLAN.md`, `docs/tickets/DP-*.md` and
`docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md` as authorities.

## Repository and work preserved

- Incoming `main`/`origin/main` was `774efdd`, with **25 pre-existing dirty
  DP-417 files** and one separate untracked master handoff. No reset, clean,
  stash, migration, public release or production overwrite occurred.
- Commit **`ed02f31`** selectively integrates precisely those 25 DP-417
  files: append-only Collection/Hit triage ledger, scoped CAS/idempotency,
  authenticated local reviewer intent receipt, safe read-only Studio history,
  schema/migration, privacy and backup/restore inventory, and tests.
- Commit **`4037ef7`** hardens DP-214 private Capture batches against a
  duplicate canonical locator under different logical Content IDs; adds
  a regression test and ticket note. This is not a real Capture or new AC.
- The original `2026-10-09-goal-infinito-tutti-ticket.md` remains a separate
  untracked pre-existing file; do not delete or silently rewrite it.

## Acceptance already verified in this wave

- `tools/check_repository_contract.py --only tickets`: PASS.
- Release preflight `--expect-no-go`: **NO-GO, 41 blockers**.
- DP-417 focused Python/isolated PostgreSQL/Studio API tests: **65/65 PASS**.
- DP-417 exact SQL on actual MiniPC PostgreSQL using `pg_temp` and final
  `ROLLBACK`: **7/7 PASS**, zero production row writes, no migration.
- DP-214 Capture/Candidate/Discovery guard regressions: **20/20 PASS**.
- Mac-side complete Python suite: **1,993/1,993 PASS**, run to completion
  under heavy host load; includes isolated PostgreSQL and restore drills.
- Privacy/backup/restore focused tests: **29/29 PASS**, including the new
  ledger in the verified restored-table inventory.
- Local privacy inventory: **100 tables / 1,247 fields**, 11 public groups
  and 89 named public keys, technical-only, *not* legal clearance.
- Deterministic benchmark: **5/5 PASS**.
- `git diff --check`: PASS at integration.
- Astro static check: **81 files, zero errors/warnings/hints**.
- Demo-only static web build: **32 pages**, PASS, with no deployed changes.
- Git `main` and `origin/main`: **`4037ef7`**, two sequential selective
  commits pushed by the sole integrator.
- GitHub CI run **`37925634204`: 11/11 jobs SUCCESS** across all Linux/macOS
  Python versions, clean-clone smoke, backend unit/regression/benchmark,
  repository policy, and frontend. This validates source, not MiniPC deploy:
  https://github.com/domenicomassafra/DichiarazioniPubbliche.it/actions/runs/37925634204

The initial no-env Astro build correctly refused to use a nonconfigured
public projection. A second build uses the explicitly opt-in demo-only
`DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1` flag. This is neither
a production-data build nor a deployment.

## Live and external blockers

- Authoritative MiniPC, read-only: **0 Discovery Hits / 0 Captures / 0
  Passages / 0 Statement Candidates / 0 Claim Candidates** at this wave.
  Prior readback contains 18 PAUSED Garlasco historical members and 30
  historical Atomic Claims; it does not prove the new funnel.
- DP-417 migration **NOT DEPLOYED**; an HMAC intent remains an annotation,
  not action/reviewer/rights/publication authority. Durable HMAC-to-ledger
  linkage, real nonempty Inbox, multi-queue transitions and safe bulk
  acceptance are still open.
- DP-214 needs genuine, rights-processable source material and review
  authority, then persisted Discovery→Capture→Passage→Candidate→match/replay,
  toward 100 unique Content from five families. DP-215.9 depends on that
  real corpus. No fixture can close these AC.
- DP-307 still needs an actual qualified reviewer and 16 Q-306 dispositions;
  provider credentials/cost authorization, human assistive QA, owner scope
  decisions and release signatures remain external blockers.
- Two agent workers were requested simultaneously and assigned disjoint
  scopes. Both browser worker start attempts **failed**; neither edited the
  workspace. Do not reopen repeated tabs without fixing the agent startup.

## Next reproducible work

1. Mac full suite and GitHub CI are both verified GREEN; do not rerun the
   expensive complete suite without new source changes or a relevant failure.
2. Confirm `git status --short --branch` and reconcile unexpected changes;
   only the two handoff/checkpoint files should remain untracked. MiniPC
   deployment mirror has no `tools/report_research_pilot.py`, so do not
   interpret its missing command as a successful fresh pilot readback.
3. Run the approved source/rights inspection read-only; never mark rights
   `CLEARED` merely from a public URL. Prepare an exact authorized first
   DiscoveryHit→Capture→Passage→Candidate→match tracer if genuine reviewed
   source receipts exist; otherwise prioritize independent engineering AC.
4. Continue automatically from the canonical dependency graph after the
   complete GitHub CI **11/11 PASS** receipt; neither public release nor
   production database migration is authorized by this CI.

**Current ticket state from checked canonical backlog:** 125 total, 86 DONE,
24 IN PROGRESS, 6 BLOCKED, 9 FUTURE; 39 open. Nothing in this wave
authorizes changing those statuses or shipping v1.

## Wave 2 — append-only signed receipt linkage (source-only)

- The new **`attestation_receipt_id`** private optional column binds a
  credential-verified `record_attested` insertion and exact replay to the
  off-database HMAC receipt. Direct unsigned record primitives cannot
  replay a signed event as their own; stale key/conflict remains fail-closed.
  Nullable is deliberate for the existing explicitly **unattested** direct
  DB primitive, not a reviewer approval route. SQL cannot itself verify
  the HMAC or credential status.
- The existing, as-yet-unapplied migration and the fresh schema were updated
  together. The new receipt reference is unique and format constrained;
  append-only update/delete/truncate triggers remain in force.
- Updated privacy inventory: **100 tables / 1,248 private+public-schema fields**;
  `attestation_receipt_id` is `OPERATIONAL_PRIVATE`, direct projection DENY.
- **31/31** focused PostgreSQL/schema/attestation/privacy tests PASS;
  independently **64/64** authority/contract/reader/API/backup/restore tests
  PASS. Full repository contract, Python compileall and `git diff --check`
  PASS; launch preflight remains **NO-GO / 41 blockers**.
- Actual authoritative MiniPC PostgreSQL **pg_temp / ROLLBACK** CAS replay
  checks remain **7/7 PASS**, with **0 production rows modified**.
- Wave 2 code has no provider calls, no rights grants, no production migration,
  no public projection/data or publish path. Keep DP-417 IN PROGRESS and
  preserve every outstanding AC until independently proved.

## Wave 3 — DP-214 research readiness consistency

- Source-readiness Collection summary and bounded members now come from
  **one PostgreSQL MVCC SELECT**, with safe scope, JSON, count and overflow
  refusal instead of independent query snapshots.
- **14/14** local readiness/provenance tests PASS after the extra negative
  cases, `compileall`, ticket contract and `git diff --check` PASS.
- On the actual MiniPC PostgreSQL, the *new SQL* was sent from Mac source
  using `default_transaction_read_only=on`: `research:garlasco` remained
  **PAUSED, 18/18 members, zero Discovery Runs, zero unlinked Hits**.
  No code was deployed to the MiniPC, no source text fetched and no data
  or rights decision modified.
- Source commit: **`98df288`**, pushed to `origin/main`; GitHub CI
  **`37929778112` succeeded 11/11 jobs**. DP-214/215 remain IN PROGRESS.

## Wave 4 — DP-307 legal release gate completeness

- The existing release preflight now always expects **all 16 Q-306**
  decision IDs, fails closed for missing entries even if remaining rows
  say DECIDED, and treats `DEFERRED`/`EVIDENCE_COLLECTED` as blockers.
- Same-ID duplicate legal status table rows fail closed, including identical
  duplicates. **10/10** focused release-gate tests PASS.
- Canonical current register: 14 OPEN, 2 BLOCKED; preflight still
  **NO-GO / 41 blockers** with the same receipt hash. This is neither
  reviewer/owner approval nor a release.

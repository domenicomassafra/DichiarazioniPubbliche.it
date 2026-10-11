# 2026-10-12 — Durable private workflows, billing rollover, read-only v3 consumers

## Starting point and integrity

Baseline was clean local and remote main
61b794194afbc8847e1ff4c5f4bdb4d0a96922f3, with one Studio worktree
and no stash. Original backlog: 162 tickets, 90 DONE, 52 IN PROGRESS,
6 BLOCKED and 14 FUTURE (72 not DONE); release engineering preflight
remains **NO-GO with 49 blockers**. No earlier DP-416/417/418/440/516/518/519,
DP-312/313 or DP-507 code was repeated in this tranche.

## Integrated vertical slices

* **DP-514 — billing cross-period integrity:** Real SQLite test showed
  a globally reused paid job attempt could reserve against October and
  November as distinct ledger rows. A previous month's UNKNOWN or over-bound
  bill exposure also stopped blocking new reservations at month rollover.
  New immutable globally keyed attempt ledger backfills existing state,
  serializes attempt CAS with month state, rejects duplicate cross-month
  reservations, and carries prior unknown liabilities into newer periods.
  Tests include concurrent different-month writers, interrupted state update
  and restart. 43 original + new cost-focused tests passed.
* **DP-514 — private accounting CLI:** The explicitly opt-in
  tools/dp514_private_month_report.py reads an existing SQLite file with
  sqlite mode=ro and PRAGMA query_only, returning redacted aggregate held,
  provisional, unknown and over-bound accounting. It refuses a missing DB,
  symlink or foreign period; double-read checks changing CAS revisions
  before displaying a report. Combined cost/CLI focused suite **46 PASS**;
  all approval/invoice/dispatch flags remain false. No caller identity,
  provider receipt or source contents are printed.
* **DP-242 — private machine handoff persistence:** LocalPersistedBatchMachineHandoff
  rechecks separate, actually persisted Source, Capture, Passage and rights
  snapshots under SQLite BEGIN IMMEDIATE; a Passage revision CAS and
  immutable request receipt are committed together. Same-key lost-response
  recovery after restart is idempotent; stale/revoked/foreign/failed
  writes refuse the transition, no B request dispatched. **49 adjacent
  tests PASS** in prime recheck.
* **DP-439 — opt-in pinned Person×Topic consumer:** The new TypeScript reader
  validates current pinned Statement, Person and Topic identities,
  exact versioned citation/date/source/locator, rights/currentness and
  deterministic URL query/pagination. A genuine Python fixture drives
  an isolated Astro SSR route positive and withdrawn/expired negatives.
  **8 Python tests PASS** and Astro check on **106 files has zero errors,
  warnings or hints**. No production route or editorial approval was added.
* **DP-240 — restartable multi-person receipts:** Separate persistent SQLite
  plan and item-bound observations with global batch revision CAS,
  per-Passage source/Content/Capture/SHA/selector/Person identity, durable
  restart/resume and immutable terminal FAILED/HELD observations. Reconciliation
  reuses existing pure DP-240 implementation and cannot elevate public
  permissions. **58 DP-240+DP-242 tests PASS** in prime independent run;
  worker also reported 70 adjacent passing.
* **DP-320 — actual PostgreSQL reference revocation fence:** The isolated
  PostgreSQL 17 adapter uses sorted row-level FOR UPDATE locks across
  dependency epochs, material hashes, release-reference writes and checked
  public-read references; one transaction durably records epoch increment,
  immutable revocation event and append-only outbox. Same-event replay is
  idempotent, changed receipt/conflicting retry fails, and no restoration
  occurs after outbox acknowledgment. A genuine disposable canonical-schema
  PostgreSQL cluster exercised two different revocation/write lock orders,
  killed uncommitted writer, read retry, stale release rejection and
  restart/outbox persistence. **18/18 PostgreSQL+existing SQLite tests
  PASS** in independent prime replay. The schema/functions are installed
  only in an explicit test database named dp320_test_* on loopback, never
  migrated into MiniPC production; no live dependency writer/CDN calls it.
* **DP-515 — durable incremental watches:** Private disposable SQLite
  Source/WatchState/attempt ledger wraps the ETag/Last-Modified planner and
  observation reconciler. BEGIN IMMEDIATE source-revision/policy/gate CAS
  serializes independent workers. 304 produces no child work, 429 stores
  backoff, changed source hashes create held (not queued) reanalysis proposals.
  Revoked rights prevent in-flight completion and invalidate proposals after
  restart; restoration cannot replay a prior epoch. **46/46 focused plus
  adjacent watch tests PASS**. No actual HTTP, paid work or runtime scheduler.
* **DP-438 — zero-statement Person private consumer:** New opt-in v3
  TypeScript consumer validates genuine Python Person/Statement/source/index
  and independently pinned sitemap candidate set. Approved zero-statements,
  an opinion without Finding, homonyms, dated roles and generic unavailable
  private/held/unknown identity are distinguished without leaking private
  membership. A self-rehashed falsely empty archive fails bidirectional
  source checks. **26/26 Python tests PASS**, isolated Astro SSR and 109
  frontend files/0 diagnostics PASS. No public route/live rights approval.
* **DP-319 — durable investigation attempts:** Isolated append-only SQLite
  source epoch, rights/policy, reservation and completion journal with revision
  CAS, deterministic planner input validation and restart. A crash after
  reservation cannot silently repeat cost-bearing attempts; rights/version
  changes invalidate stale keys, and no false reviewer availability is
  invented. **24/24 focused plus adjacent investigation tests PASS**.
* **DP-409 — release-pinned static-search withdrawal:** RED showed a stale
  self-rehashed index could rebind its old public rows to a newer projection.
  The new opt-in search reader demands independent release ID, epoch,
  projection/index SHA, generation instant and expiry, checked both before
  and after search. Two actual isolated Astro static builds went from one
  fictional Finding to zero; stale/mixed/rehashed/cross-epoch artifacts fail.
  Legacy v2 compatibility is preserved. No production CDN or signed pin
  issuer is being claimed.

## Host inventory and deployment isolation

Mac Studio: one authoritative Git worktree and zero stash before this wave;
current concurrent WIP partitioned by strict ownership. MacBook Air was
reachable by SSH and had no checkout named DichiarazioniPubbliche.it under
the bounded searched Code, Projects, src, Work or Codex directories. MiniPC
web/tunnel services were active; its non-Git deployment mirror
/home/udodo/src/DichiarazioniPubbliche.it was unchanged (approximately
34,652 KiB). MateBook Linux was *not reachable* despite previous receipt:
Tailscale reports both MateBook peers offline and a fresh BatchMode SSH
attempt timed out. We cannot attest its current Git/worktree/stash/WIP;
no cleanup was attempted anywhere. **Space newly recovered: 0 bytes.**

## Safety, limitations and remaining requirements

All new ledger stores are opt-in local private fixture/reference seams.
Their durable persistence does not authenticate upstream licensed-source
rights, provider execution, machine-B/qualified human approval, billing
invoices or publication authorization. Public Person×Topic consumer remains
isolated from the live public route and requires an independent pinned
release/rights authority. No MiniPC production data, services, deploy
mirror, provider quota, paid call, public projection or legal status was
modified. Original AC remain OPEN where end-to-end real evidence is absent;
NO-GO must remain in force.

## Post-freeze integration checks

The complete source-only Python test suite **after all eleven code/test
commits were frozen**:

- `PYTHONPATH=poc PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -q`
  completed **3,076/3,076 PASS** in 206.990 s, including actual disposable
  PostgreSQL revocation races, local SQLite restart/concurrency fixtures and
  the repository restore drill. This is 57 more tests than the previously
  attested 3,019-test baseline.
- `python3 -m compileall -q poc tests`, repository contract and scoped
  Ruff checks passed. Privacy/schema field inventory remained **1,248 fields
  / 100 tables**, fingerprint `4291a376e8eed760b9d6c2972ba907375de6ece52b2063719950c37439f2e31f`,
  explicitly `TECHNICAL_ONLY_NOT_LEGAL_CLOSURE`.
- Deterministic benchmark **5/5 PASS**, `check_launch_preflight.py
  --expect-no-go` **NO-GO / 49 blockers** (receipt
  `96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`).
- `npm run check` passed **109 Astro/TypeScript files, 0 diagnostics**,
  search index checks PASS, DP-438/439/440 Python-fixture-to-TypeScript
  isolated static SSR checks PASS, and DP-409 two independent old/new
  generated static asset builds with withdrawal negative PASS.
- Local explicit **demo-only** Astro build and route-contract checks passed.
  Generated demo routes and fixtures were not deployed, installed or
  authorized to publish.

The eventual remote main SHA and GitHub Actions on that SHA must be
verified independently after the final handoff commit; historical CI 11/11
on 61b7941 is **not** evidence for this new tranche.

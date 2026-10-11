# 2026-10-11 — Private Studio operations, incremental source health and opt-in v3 reader consistency

## Verified baseline and concrete changes

Starting verified clean `main=origin/main=aca8809fadb9ae8441913296c139889aba1fa232`.
Five independent, scoped functional slices were implemented and locally committed
without an authorized public/MiniPC deployment:

| Commit | Original ticket | Functional delivery | Proof and remaining boundary |
|---|---|---|---|
| `da56998` | DP-422 | Opt-in single-release cross-reader preflight for pinned Person, Person×Topic and Statement search v3; exact quote/source/version/locator matching and route inventories | Synthetic Python→TS 3 original Statements/4 memberships/2 Persons; revocation 3→2; separate rehashed text/missing-record split-brain rejected; Astro check 102 files/0 diagnostics. Not a release authority or public route |
| `7fb3bdb` | DP-416 | PostgreSQL read-only Collection→Content/Source→exact Capture→Passage→Statement/Claim Candidate and persisted promotion reference | 43/43 private Studio/PG tests; scoped source IDs, paging/foreign-parent rejection. No real Garlasco Passage/Candidate, UI/browser acceptance or approved rights |
| `3b50e62` | DP-418 | Reviewer-facing read-only candidate comparison with independent source/Capture verification and explicit duplicate/same/related/uncertain dispositions | 67/67 related tests; forged/stale Target and alternate Capture duplicate refused. No persisted reviewer decision, mutation authority or physical accessibility acceptance |
| `2dcb5a1` | DP-417 | New Collection-scoped latest-Capture exception queue, rights/hold/archive blockers and retry conditions with a genuine read-only PostgreSQL transaction and anchored cursor | Prime 25/25 adjacent tests; worker 37/37 broader set; disposable PostgreSQL SELECT-only user. Review reproduced RED→GREEN a single rights-REVOKED Capture silently omitted. No triage write/approval/API route |
| `1979ce8` | DP-515 | Pure private daily source-watch digest with bounded, replayed committed attempts, new/modified/unchanged/429, readiness/coverage gaps and known/unknown metered cost | Prime 73/73 watcher/backfill/monthly-budget tests; worker 80/80 related tests. No runtime polling, real cost/permission receipts, DB/lease CAS or actual dispatch |

All original DP-416/417/418/422/515 acceptance criteria requiring qualified
rights/review, real public records, actual MiniPC/browser/operator workflow,
transactional authorization or cross-system revocation **remain OPEN**.
No new ticket was marked DONE for passing synthetic or isolated source tests.
All new read models/fixtures are private or explicitly opt-in; review receipts,
source-rights clearance, production publishing and automatic provider dispatch
are **never granted** by these changes.

## Integration checks

On the integrated local tree: `python3 -m compileall -q poc tests` PASS;
scoped Ruff F821/F823 PASS; repository contract PASS; privacy field inventory
unchanged at 1,248 fields across 100 tables, status
`TECHNICAL_ONLY_NOT_LEGAL_CLOSURE`; deterministic benchmark **5/5 PASS**.
`web/npm run check` reports 102 files, **0 errors/warnings/hints**;
`web/npm run check:search` PASS; isolated demo build explicitly enabled by
`DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1` and
`npm run check:routes` PASS: 34 HTML routes, 8/8 canonical families, 16
compatibility aliases and 618 valid internal links.
The same route checker explicitly says `AC-422.1 live acceptance NOT_ATTESTED`.
The ordinary build without an approved external projection intentionally
refuses to materialize public records.

## Four-host reconciliation (read-only)

Mac Studio: single scoped checkout `main`, clean before this wave; no WIP
overwritten. MacBook Air: reachable, no DichiarazioniPubbliche Git checkout
found in bounded Code/Codex/src/tmp roots (not a full-filesystem proof).
**MateBook Linux is newly reachable** over strict-key batch SSH; bounded
Code/Projects/etc. roots contain other projects but no DP checkout;
this corrects the earlier *unreachable* report, not a claim of exhaustive
cleanup. MiniPC: `/home/udodo/src/DichiarazioniPubbliche.it` is a ~34,652
KiB **non-Git deploy mirror**, retained unchanged. The correct *user*
`dichiarazioni-pubbliche-web.service` and Cloudflare tunnel are active;
checking the system-level unit alone would falsely suggest web inactivity.
No production write, deployment, service restart, credential access or new
cleanup was performed; **0 additional bytes recovered/claimed** in this wave.

## Launch and unresolved external acceptance

`python3 tools/report_ticket_status.py`: **90 DONE / 72 non-DONE** (52 IN
PROGRESS, 6 BLOCKED, 14 FUTURE). `python3 tools/check_launch_preflight.py
--expect-no-go`: **NO-GO/49**, receipt SHA-256
`96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`.
Qualified Q-306 legal decisions, source-item use/quotation rights, public
editorial source/person/topic memberships, governed review authority, live
MiniPC public-v3 readback, authenticated Studio UI/real data and accessibility
remain separate blockers. Do not conflate code test success with any of them.

See the five original ticket receipts for exact source paths and negative tests.
GitHub remote and exact-SHA CI result must be recorded only after final
fast-forward push and successful jobs, not inferred from the previous
`aca8809` CI run.

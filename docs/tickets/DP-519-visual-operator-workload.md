# DP-519 — Operator visual-quality capacity and exception time budget

Status: IN PROGRESS

### 2026-10-12 — Private token-authorized PostgreSQL workload HTTP readback

The new isolated canonical PostgreSQL worklist adapter can now be mounted
explicitly into a StudioLocalReaders instance and consumed on
/v1/operator/workload. The **ordinary Studio server does not instantiate**
this adapter and returns unavailable without the opt-in disposable reader.
The shared loopback HTTP handler authenticates its own bearer, Host and Origin
before invoking the collection-scoped reader. The exact collection/limit/cursor
schema, read-only PostgreSQL snapshot and stale cursor denial remain owned by
the source adapter, not copied into a secondary query path.

A true disposable PostgreSQL→Studio HTTP test checks denied anonymous and
cross-origin reads, a first bounded Collection page, a different Collection
scope, revoked Capture immediately moving its row to a blocked reason, no
transcript/URL leakage, malformed limits/cursors/unknown scopes and absence
of any publication/text/dispatch authority. All 22 focused PG and HTTP tests
PASS. This is an **operator-token, single-workspace canary**, not an
independent multi-tenant identity or permission system; the exact local DB
adapter refuses production/non-disposable DSNs. Real owner work time,
licensed image decisions, human review, MiniPC wiring and original
AC-519.1–5 remain OPEN. Release NO-GO.

The Collections panel now offers a session-scoped private
workload form with exact Collection ID, bounded limit,
snapshot-checked continuation cursor and a live-status summary.
Validated Content rows show only current rights/hold reason
and source-free Capture/Passage/Claim Candidate counts;
selecting a row opens the existing persisted Capture inspector.
The client does not render unknown response fields and clears
rows, cursor and Collection ID when the token changes or
the operator signs out. The real Node Studio DOM async
regression validates response contract, button navigation
and privacy scrubbing; an additional authenticated HTTP
test asserts that the default server with NO adapter returns
503 rather than falling back to a production database.
The combined real PG/HTTP suites **23/23 PASS**; only the
explicit disposable canary seam is supplied by this tranche.
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-417, DP-304

## Problem
 No ordinary textual editorial reviewer exists. The owner estimated up to approximately five hours/week for quick mainly visual checks; current queue states could imply humans will approve all text/verdicts. A staff-time-free pipeline claim is invalid without measuring exceptions.

## Outcome
 One bounded operator worklist for decisions that genuinely require visual inspection (e.g. person-image correctness/licensing, image/no-image, attribution of visual caption where approved) and narrowly escalated unresolved evidence-policy decisions after automated attempt logs. It measures actual owner time and backlog without treating those minutes as textual verdict approval.

## Traceability & constraints
 R23/R34, R25. The 5h/week is planning availability, not a guaranteed staffing SLA, two independent reviewers, or a text-review throughput forecast. Automated process-text verification belongs to B, not visual operator queue. Reviewer independence/qualified legal authority cannot be invented from a single owner's approvals.

## Scope
 Deterministic queue reasons, visual asset provenance/source/rights and preview reference, one-click choose correct authorised image or none, append-only actor/action/time/asset decision, bounded duplicate grouping, expiry/priorities, short notes, no auto-contact. Per-case handling time and weekly rolling total; explicit opt-out/no-image fallback and public alt text. Separate “investigate source/claim” exception queue with automated prior attempts/evidence hypotheses, cost budget and only escalation of a concrete unresolved question. High-risk/dual-control unresolved remains held until B's accepted machine authority or qualified actor really satisfies its own rule.

## Non-goals
 Human fact-check on every claim, simulated second signer, replacing source authenticity with thumbnail judgment, image generation, fixed throughput promises.

## Dependencies and sequencing
 A/B specify meaningful exception conditions, C owns visual UI and safe no-image behavior. Use current Studio operator queues/annotation pattern, not create parallel editorial app. No launch-time assumption that owner is available every day.

## Acceptance criteria

- [ ] `AC-519.1`: Real image-choice sample yields licensed/identity-correct image or explicit none; absent/uncertain right or ambiguous person fails closed and does not block text-only authorized public record solely for lack of photo.
- [ ] `AC-519.2`: Queue items have reason, attempted automated investigation, required human decision and bounded time budget; no submission implies factual Finding verification.
- [ ] `AC-519.3`: Count/operator minutes/week, older unresolved items and per-reason median are reported; excess demand pauses optional image work or opts for no image without fabricating reviews or overriding policy.
- [ ] `AC-519.4`: Replay, stale source image rights and duplicate tasks preserve append-only audit and trigger correct public image withdrawal/readback with DP-518.
- [ ] `AC-519.5`: MiniPC candidate and C public consumers prove no orphan/unlicensed image and zero text-verdict permissions from visual approval.

## Validation / proof
 Frozen identity/image/license/ambiguous cases, simulated owner time entries and duplicate reviews; actual operator sample before asserting capacity. Private redacted receipt, no raw photos stored in public test logs.

## Documentation, data, and migration impact
 Extend Studio queue/prior image rights records if necessary; runbook for “none” and measured workload. Preserve no human ordinary reviewer premise.

## Completion receipt
**2026-10-11 local private source-only capacity reconciliation — IN PROGRESS.**
`visual_operator_capacity_v1.py` accepts a bounded operator-only metadata
worklist of asset hashes/preview IDs, provenance/rights/identity state and
per-image options. It reconciles immutable, idempotent, chained reported time
events (including events across ISO week boundaries), rejects overlapping
actor time and duplicate exception questions, separates actual minutes from
future estimates and measured per-reason median, and prioritizes work by
expiry/age and a five-hour **planning** allowance, not a promised SLA.
Overcapacity defers optional image inspection; no-image and unknown rights/
ambiguous-person paths stay text-independent. Stale/expired selected images
trigger held withdrawal-review rather than reusing an old photo. Choosing an
image is only a PRIVATE CANDIDATE, not verified licensing or source-person
identity; `image_eligible`, `publication_authority` and
`text_review_authority` remain false. Source/test commit `084a77a`, **16**
synthetic DP-519 tests plus **10** existing Studio operator queue tests PASS;
Ruff lint/format PASS. All AC-519 remain unchecked: no authenticated owner
receipts or genuinely measured staff time, no persisted Studio queue, licensed
real image, approved identity/alt text, MiniPC/public display or DP-518 live
withdrawal readback. No human text reviewer is asserted or impersonated.

## 2026-10-11 follow-up — source-owned exception and time-accounting fixes

Two adversarial unit tests first failed on `main` `8b50e355`:

1. An exception could cite any syntactically valid 64-character digest as a
   `prior_attempt_hash`, including a receipt belonging to another work item
   or a wholly unrecorded attempt. Thus its purported prerequisite automated
   investigation was not traceable to its own worklist record. The private
   reconciler now requires **every** cited prior attempt to be present in that
   work item's bounded `automated_attempt_hashes`. An item with no recorded
   attempts cannot escalate using fabricated hashes. Caller-side identity and
   tamper-proof attestation of these input hashes remain external requirements.
2. `median_minutes_by_reason` counted each chained event as a separate case.
   A case handled in 3+7 minutes and two independent cases taking 20 and 40
   minutes yielded an incorrect median of 13.5 from four event durations.
   The new calculation aggregates events for each `work_key`, then computes
   the per-reason median of case totals (**20 minutes** in this fixture).
   Actual event totals, ISO-week splits, replay counts and budget arithmetic
   remain based on the original immutable event intervals. The data remains
   **self-reported** operator time, not authenticated staffing evidence.

`tests/test_dp519_visual_operator_capacity.py` adds both regressions,
including cross-work forgeries, a missing investigation, mixed real/fake
attempts, accepted subset receipts, input-order invariance, and preservation
of weekly/event totals. RED: **2 failed / 19 run**, with the bogus attempt
accepted and median `13.5`. GREEN: **19/19 pass**, no additional dependency.
Ruff check and format, `python3 -m compileall -q poc tests` and
`git diff --check` pass locally. This is a source-only improvement of
the exception gate and capacity report, not a real operator acceptance.

**All AC-519.1–.5 remain unchecked and ticket IN PROGRESS.** Real licensed
image/identity judgement, real owner-minutes and identity attestations,
persisted Studio consumption, public no-image/withdrawal and DP-518 readback,
qualified authority and MiniPC proof remain external. Nothing here approves
source rights, a factual Finding, or an image for publication.

Broad regression attempt: `PYTHONPATH=poc python3 -m unittest discover -s
tests -q` completed **2,878 tests in 152.668 s with four errors** outside
DP-519. One was an import of `SQLiteMonthlyReservationStore` in an
in-progress DP-514 SQLite reservation test; three were
`test_existing_factcheck_persistence` cases failing on operational discovery
receipt database writes. These errors are not represented as green and were
left for their owning workstreams. The independently run
`tests.test_studio_operator_queues` (10/10) and DP-519 (19/19) suites pass.

## 2026-10-11 — Durable private visual worklist and time journal (next wave)

Introduced `poc/dichiarazioni_pubbliche/studio_visual_worklist.py`, an opt-in
`SQLiteVisualWorklist` backed by a private owner-readable **0600** SQLite file.
It gives real transactionally persisted operator work-item snapshots and
reported time decisions across process restart. Each work item carries a
monotone revision updated by SQLite `BEGIN IMMEDIATE` compare-and-swap;
independent connections cannot overwrite a concurrent source/version/rights
change. Time events are append-only with database UPDATE/DELETE refusal
triggers. Identical event replay is idempotent; conflicting ID, stale source,
wrong revision, invalid cross-case chain and overlapping recorded actor time
fail closed. The existing deterministic workload report reconstructs weekly
reported minutes, median by reason and safe no-image fallback from these
persisted records.

Independent review uncovered a new provenance problem: updating an existing
`work_key` to a different Person, Content or reason after time had been
recorded relabeled past work minutes. The three identity-swap cases were
**RED**; stable work-key identity checks now reject each (**GREEN**).
Tests also cover two DB connections, restart, source-rights revocation,
conflicting replay, immutable SQL rows and private file permissions:
**25/25** new + existing DP-519 tests PASS. Scoped Ruff F821/F823 and
`git diff --check` PASS.

This is **reported, unverified** work time, not authenticated actor/qualified
editorial acceptance. No licence or identity decision is manufactured; all
receipts retain `publication_authority=false`,
`image_approval_authority=false`, `text_review_authority=false`.
There is no production Studio route, signed source/version truth, licensed
real-image sample, public withdrawal, or MiniPC visual operator canary.
**DP-519 stays IN PROGRESS, AC-519.1–.5 all unchecked and release NO-GO.**

## 2026-10-12 — Disposable PostgreSQL private Studio workload read

Added a separate **read-only** adapter
`poc/dichiarazioni_pubbliche/studio_operator_workload_pg_v1.py` and a
canonical PostgreSQL canary
`tests/test_dp519_studio_operator_workload_pg_next.py`. The adapter
requires a collection-scoped operator-authentication callback at each
request; it refuses missing/failed verification and constrains the local
testing DSN to loopback `dp519_disposable`. The callback is a **caller-side
contract, not an authenticated actor or production permission by itself**;
the real Studio HTTP entrypoint must provide independently checked session
identity, authorization and access logging before using this seam.

One `REPEATABLE READ READ ONLY` transaction reads only an INCLUDED
Collection membership and the attached Content, most recent Capture,
Passages and their linked Statement/Claim Candidates. It counts retained
Captures and current-Capture Passages/Candidates without joining records
from other Collections or reporting obsolete-Capture candidates as current.
It also reads the latest unsuperseded Content-scoped rights leaf and
Capture/content rights and hold metadata; missing, ambiguous, expired,
revoked or insufficient rights produce a **blocked operator reason**, never
permission. The private response gives a page-scoped blocked queue with
specific inspection actions, aggregate scoped counts, allowlisted
current-rights/Capture-hold status values and review-only rows.
It exposes no private Passage text, normalized candidate text, original
source URLs, rights receipt identifiers, operator notes or secrets.

Pages are ordered by stable Content ID with a bounded keyset cursor.
Each cursor binds Collection ID and a digest of the entire observed
Collection status/row snapshot; if revocation, new Capture, candidate,
Collection membership or rights change occurs between page requests,
the next page **refuses** instead of mixing versions. Every read enforces
at most 500 INCLUDED Content rows and at most 20 rows per page; oversized
scope returns a hold instead of suggesting incomplete coverage. The
adapter contains no writes, database migrations, audit-time recording,
operator decision submission, image selection, provider work or release.
`dispatch_authorized`, `publication_authority`,
`image_approval_authority`, `text_review_authority` and
`source_rights_attested` remain false.

Real disposable PostgreSQL tests cover restart, auth refusal, different
Collections and excluded membership, missing Capture, current/obsolete
Capture candidates, current rights revocation/expiry/missing uses and
ambiguous parallel rights, held candidates, PAUSED Collection, stable
keyset/replay, source mutation between pages, concurrent read/revoke,
boundedness and zero source-text exposure. An adversarial RED→GREEN
demonstration removed the `rights_leaf_count != 1` guard: a conflicting
live REVOKED rights leaf alongside CLEARED incorrectly returned
`REVIEW_ONLY`; restoring the guard produces `BLOCKED`.

This is a local private readiness view, **not** a real visual-image review
queue, authentically measured owner workload, licensed/identity-correct
image, qualified textual approval, public withdrawal or MiniPC rehearsal.
The earlier SQLite event journal remains separate and unchanged. All
`AC-519.1–.5` remain **unchecked**, ticket **IN PROGRESS** and release
**NO-GO** until those external proofs and the authorized Studio HTTP
integration exist.

**Verification:** 10 new real disposable-PostgreSQL tests and the 19
existing DP-519 capacity plus 13 Studio operator-queue tests passed together
(**42/42 PASS**). The separate rights-ambiguity sabotage was **RED** on real
PostgreSQL and returned **GREEN** after the required current-rights-leaf
check was restored. Scoped Ruff lint and formatting, Python compilation and
`git diff --check` passed. No runtime deployment, real operator-minute
recording, external source authorization, source text export or provider
action was performed.

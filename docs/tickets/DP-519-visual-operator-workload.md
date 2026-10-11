# DP-519 — Operator visual-quality capacity and exception time budget

Status: IN PROGRESS
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

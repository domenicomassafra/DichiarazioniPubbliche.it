# DP02 — Four-ticket continuation / native dispatch and actual outcome

Date/time: **2026-10-15, 10:32 Europe/Rome**.
Owner mandate: continue resolving as many original tickets as possible,
start four independent native CoS agents immediately, do not stop before
at least one ticket is finished, update the exact response file.

## Actual worker start and owner paths

Native run: `2c718367-87ff-4705-9bdb-b8a58226c0f7`.
The coordinator requested **four independent ticket assignments**:
DP-238, DP-239, DP-240 and DP-244. Reusing sleeping workers was
attempted first; the worker command transport is not proof of startup.

| Requested assignment | Observed native outcome | Actual execution owner |
|---|---|---|
| DP-238 PDF/OCR | `worker-1` failed two revival attempts without a browser claim. `worker-7` replacement invitation failed: opened chat never picked up task. **0 real DP-238 worker starts.** | Prime executed scoped source/test/doc fix |
| DP-239 multilingual | `worker-2` eventually woke, reported real scoped RED→GREEN, then `agents finish` and sleeping. | worker-2, code integration prime |
| DP-240 multi-person | `worker-3` eventually woke, reported real scoped RED→GREEN, then `agents finish` and sleeping. | worker-3, code integration prime |
| DP-244 coverage | `worker-6` invite failed at startup: browser never picked up task. **0 real worker starts.** | Prime executed scoped source/test/doc fix |

**Actual subordinate first turns: 2/4 requested assignments**;
the other two tickets were executed directly by prime, not falsely
counted as subagent successes. Failed chats were not repeatedly spawned
in a saturated browser queue; all started workers finished. Models on
observed native worker records: `gpt-6-thinking`, reasoning `high`.
Each worker or prime owned distinct paths. Shared Git index/ref, PLAN
and this receipt remained under the prime lease. The eight concurrent
DP-512 dirty/untracked paths were never staged, edited, reset or cleaned.

## Original-ticket AC crosswalk and proven technical patches

| Original | Before → after | Actual source/test outcome | Remaining original acceptance |
|---|---|---|---|
| **DP-238** | IN PROGRESS → IN PROGRESS | `document_pdf_extraction.py`, `test_dp238_born_digital_pdf.py`, ticket. Real generated PDF bytes returned with `HTTP 206` previously accepted as `SUCCEEDED` using an isolated successful parser-worker response. **RED**, now exact HTTP 200 required; HTTP 206 `FAILED/DOCUMENT_SOURCE_STATUS_INVALID`, zero canonical text/spans. Single targeted GREEN and adjacent native document tests **12/12 PASS**. | AC-238.1–6 OPEN: approved scan/machine-text sources, independently measured OCR fidelity, provenance/role review, real persistence and MiniPC readback. |
| **DP-239** | IN PROGRESS → IN PROGRESS | `multilingual_derivation.py`, `test_dp239_multilingual_derivation.py`, ticket. German U+2212 mathematical minus was dropped in number comparison: `−12` and `12` treated equal, `−12` and `-12` treated different; RED in four subcases. Lexer accepts U+2212 and numeric canonicalizer retains its negative sign. **20/20 focused**, **59/59 selected adjacent** PASS. | AC-239.1–6 OPEN: independently approved German/Italian meaning-risk Gold, derivative source rights, consumer/provenance and real MiniPC data. |
| **DP-240** | IN PROGRESS → IN PROGRESS | `multi_person_batch_v1.py`, `test_dp240_multi_person_batch.py`, `test_dp240_durable_batch_next.py`, ticket. Source-family/context-review/identity-review/rights swaps across Person/Content could preserve partition ID even after whole-plan digest recompute. RED pure and disposable SQLite; GREEN binds partition to those values and explicitly bumps private manifest VERSION from v1 to v2 to prevent silent reinterpretation. **81/81 worker tests**, **46/46 prime focused tests** PASS. | AC-240.1–6 OPEN: independently approved multi-Person source/rights, measured isolation-vs-mixed cost/false-attribution baseline, persistent real reviewed candidates, MiniPC/Studio. Old v1 private plans need approved rehydration; no production migration performed. |
| **DP-244** | IN PROGRESS → IN PROGRESS | `coverage_catalog_v1.py`, `test_dp244_coverage_catalog.py`, ticket. Old scope hash omitted exact `max_staleness_seconds`: a 60-second observation could be reused with 365 days and show false currentness. RED `ValueError not raised`, GREEN different fingerprint/`COVERAGE_MIXED_SCOPE`, with original short-window state `STALE`. **18/18** focused and **55/55** adjacent with DP515 watcher PASS. | AC-244.1–6 OPEN: real rights and observations, stored conditional fetch/delta/cost ledger, scoped public freshness release and authentic MiniPC canary. |

Three original technical repairs plus the DP-244 bug closure are all
source-only. **No original DP-238/239/240/244 ticket was falsely set DONE.**
Only `DP-521`, a **new bounded technical bug ticket** based on the
reproduced DP-244 receipt-scope defect, was fully DONE with all
four standalone checks. This changes backlog to **164 total /
92 DONE / 52 IN PROGRESS / 6 BLOCKED / 14 FUTURE /
72 original not-DONE / READY=0**. PLAN/ticket parity verified.
The previous `DP-520` DONE remains unchanged. This is not a claim
that any of the 72 previously open original tickets has closed.

## Exact Git integration and local test evidence

Single coordinator staged only the independently owned code/test/ticket
paths, committing and pushing in original-ticket units:

- `cda1fcee76987ebfd75ee568819960acefeb00ae` —
  `fix(dp521): bind observed coverage to exact freshness allowance`
  (DP244 source/test/ticket + standalone DONE ticket/PLAN).
- `e2ebff65f32e55d01f6cd51c60f5ae2c940bca58` —
  `fix(dp239): retain unicode minus in translation numeric comparisons`.
- `0ca9ab15f8519997cb065e4722a8fe40b1531cd8` —
  `fix(dp240): bind private batch partitions to source review and rights`.
- `f3cf0139a4ba56803f1c33de4b359d0aad111369` —
  `fix(dp238): refuse HTTP partial responses as complete PDF capture`.

Prime independently ran the combined **96/96 focused tests PASS** on
source SHA `f3cf0139a4ba56803f1c33de4b359d0aad111369`:
`tests.test_dp238_document_extraction`, the exact HTTP 206 PDF
regression, `test_dp239_multilingual_derivation`,
`test_dp240_multi_person_batch`, `test_dp240_durable_batch_next`
and `test_dp244_coverage_catalog`. Deterministic benchmark
**5/5 PASS**, scoped Ruff **PASS**, repository contract **PASS**,
`git diff --check` **PASS**. Worker-owned targeted compile and
Ruff checks also PASS.

**Important negative proof:** the broader real subprocess PDF suite
completed **23 tests with four FAIL**, all
`DOCUMENT_PDF_WORKER_UNAVAILABLE` under severe host load (at
10:29 CEST host load averages **190.86, 199.30, 139.03**), including
real two-page, annotation and mixed-image workers. These failures
are **not** represented as passes or diagnosed as caused by the
new HTTP guard: that guard is tested in a controlled parser-response
fixture prior to child dispatch. The full repository Python suite is
**NOT RUN on new SHA** due high host load and the already observed
four native PDF-worker failures; do not reuse historical 3683/3683
PASS from the earlier source SHA `ea5a16d`. True native PDF worker
behavior under normal load remains unverified for this tranche.

GitHub branch CI on source SHA `f3cf013` was shown `success`
in run `38706103169`, but this push workflow historically runs
repository contract only (full web/backend/clone jobs skipped), so
it is **not** full PR CI. No PR was opened; automatic paid-review
settings remain unverified, `PR_HELD_AUTOREVIEW_BILLING_GUARD`.
No `@codex review`, merge, main push, production DB, provider,
source fetch, secret, MiniPC deployment or public release.
`origin/main` remains `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`;
branch and remote `integrate/dp-20261014-all-lanes` exact SHA
require readback again after this documentary commit.

## Launch gates, changed source and transport

Read-only status reporter file agreement PASS; release preflight
**NO-GO/49**, receipt SHA
`96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`.
The original 72 not-DONE require, as applicable, qualified
source/legal/privacy evidence, independent semantic/OCR gold,
authenticated real source versions, budget/PG and real MiniPC/operator
acceptance. Nothing in these patches supplies it.

Canonical product answer is this file plus PLAN's current lane
checkpoint. Append this exact file to the existing ControlCenter
local `02-WAVE-001-COS.response.md` under
`/Users/domenico/ControlCenter/src/controlcenter-ops/tasks/20260929-main-release-closure/310-prompt-to-prompt-20261015/`,
preserving its preceding two receipts. Ops Git index/ref remains
**PENDING_CORE07_OPS_LEASE**; do not stage/commit/push shared Ops
without the corresponding single-writer lease.

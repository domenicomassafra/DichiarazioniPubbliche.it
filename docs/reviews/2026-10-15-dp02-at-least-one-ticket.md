# Lane 02 — Owner continuation: genuine ticket closure and three source fixes

Timestamp: 2026-10-15 09:15 CEST (Europe/Rome).
Disposition: **DP-520 DONE (new bounded source-only bug ticket); original release NO-GO**.
Branch: `integrate/dp-20261014-all-lanes`.

## Requested outcome and distinctions

The owner instructed the lane to continue fixing as many tickets as possible
until **at least one ticket** was completely finished. This continuation
examined the canonical 72 not-DONE **original** tickets and did not
reinterpret missing physical/legal acceptances as automatic PASS.

A reproducible fail-closed defect in the existing DP-237 exact media locator
was formally scoped as **new independent technical ticket DP-520**, with
bounded acceptance, source tests, code review and a completed branch push.
It is now **DONE**. Original DP-237 remains **IN PROGRESS**: this newly
closed bug ticket does **not** reduce the 72 unresolved *original*
items. Current ticket snapshot **163 total / 91 DONE / 72 not-DONE /
0 READY**, PLAN/ticket statuses agree. This distinction is intentional
and must be visible in any report to the owner.

## Native worker acquisition and ownership

Chat On Steroids run `61da321a-66a0-4122-9085-8a75a0aafceb`.
Three previously sleeping GPT-6 High native workers were reused, each
had an actual turn, owned disjoint paths, reported results, and called
`agents finish`:

| Worker | Original ticket | Consequential RED→GREEN result | Original status |
|---|---|---|---|
| worker-1 | DP-237 (also scouted DP-215/234/241) | Negative `MEDIA_SEGMENT_REF.variant_end_char` formerly passed Python negative slicing. Now fails closed before quote/segment binding. | IN PROGRESS; AC-237.1–6 OPEN, real licensed source and Studio/MiniPC proof missing |
| worker-2 | DP-318 (scouted DP-229/315/320/508) | Same immutable source-part ID with two incompatible source SHA versions formerly allowed `CROSS_PERSON_AGREEMENT`; now HOLD/`SOURCE_PART_REVISION_CONFLICT`. | IN PROGRESS; AC-318.1–5 OPEN, independently reviewed source/identity/relations and public MiniPC readback missing |
| worker-3 | DP-407 (scouted DP-422/409/412/410) | Content media moment link formerly concatenated `#intro#t=150`; now replaces URL fragment with `#t=150`, retaining existing query/path. | IN PROGRESS; AC-407.4/.7 OPEN, projection semantics and actual AT/MiniPC approval missing |

Fourth independent new invitation, `worker-5` (DP-516/519), **FAILED
at startup** because the opened chat did not report back. It did
not perform a proven first turn; no repeated spawn or fictitious
work/product evidence. Earlier `worker-4` is a previous continuation's
failed startup, not a fourth new participant. Actual operative workers
this time **3/4**. Shared Git index/ref remained with prime, with
explicitly scoped stage paths only. No worker edited Ops, PLAN, or the
simultaneous, foreign DP-512 WIP.

## Exact source patches and validation

1. **DP-237 + new DP-520 DONE**: `poc/dichiarazioni_pubbliche/original_source_resolver.py`,
   `tests/test_dp237_exact_locator.py`, parent ticket. One-line strict
   end > start guard; adversarial signed-media negative alias RED→GREEN
   while correct source locator remains LOCATED. Worker 68 focused/
   adjacent plus 59 public/contract tests PASS, benchmark 5/5, Ruff,
   compile and diff-check PASS. Prime independently ran 24 actual
   resolver/locator tests PASS and 63 combined DP237/DP318 controls PASS.
   Scoped source commit `e4dffdf33ee2e2a587ec89660bb5d39dea266de9`.
   New ticket `docs/tickets/DP-520-negative-media-variant-offset-regression.md`
   has its own checked criteria/receipt; PLAN status agrees. Ticket closure
   commit `ef8e0d808757e4ee32de4c369f1dd1480e5a0f66`.
   Neither commit deploys to MiniPC or changes original DP-237 acceptance.
2. **DP-318**: `relation_runtime.py`, focused DP318 wave test, original
   ticket. Exact same source part but different source hash holds before
   private cross-person/same-person relations; positive different-part
   control remains candidate with publication_authority=false. Worker
   79/79 tests PASS, Ruff/compile/diff PASS; prime included in combined
   63-test PASS cohort. Source commit
   `3d3c174c24aa582a3777891fc2c879a448defe79`.
3. **DP-407**: `web/src/components/ContentRecord.astro`, actual
   `web/scripts/check-content-v3-currentness-wave-close.mjs`, original
   ticket. Red Astro build/HTML test for an approved fixture source URL
   with query and `#intro`; GREEN with a single `#t` media fragment.
   Regressions retain currentness, withdrawal and privacy checks.
   Worker `npm run check`: 0 errors/0 warnings (one unrelated hint).
   Prime independently reran actual staged-Astro/Chrome script:
   **PASS / exit 0**; script syntax/diff check PASS.
   Source commit `ea5a16de4177b110e6e2e39845e2c3aed27cbdba`.

These are three genuine and independently scoped source repairs. None
signs rights, approves a Person, creates evidence, overrides a legal
decision or claims actual production rollout. The 72 originally open
tickets remain governed by their exact original AC; `READY=0`.

## Integration, reviews and final gates

Before new patches, branch SHA `63f60e9dc54938957c849959cd3b66d411935495`;
after commits source + scoped ticket closure, `ea5a16d` was the
last code SHA. `git push origin HEAD:refs/heads/integrate/dp-20261014-all-lanes`
accepted each exact owned commit; check current final SHA and remote
ref again after publishing this receipt. Canonical `main` remains
`33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`.
No PR, no merge, no paid review, no deploy.

The earlier `3681/3681 PASS` was on source SHA `25c94d1`, and was not
borrowed as evidence for this cohort. A fresh full Python run in a
**detached isolated source worktree at exact SHA
`ea5a16de4177b110e6e2e39845e2c3aed27cbdba`** completed:
**3,683/3,683 PASS, 456.338 s, exit 0, no FAILED/ERROR**.
Command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m
unittest discover -s tests -q`; log:
`/tmp/dp02-wave002-exact-full-20261015.log`. SQLite and HTTP
`ResourceWarning`s are non-fatal and not concealed.
Additional independently run exact-SHA proofs: Astro `npm run check`
**129 files / 0 errors / 0 warnings / 1 nonblocking hint**;
`node --check` owned checker PASS; scoped Ruff PASS;
`tools/check_repository_contract.py` PASS; deterministic benchmark
**5/5 PASS**; git diff check PASS. The temporary `web/node_modules`
symlink was unlinked (its installed target was not touched), the
detached worktree checked clean and was removed without `--force`.
Only the two original Git worktrees remain.

Simultaneous other-agent WIP DP-512 in `health_digest.py`,
`operation_ledger.py`, several tests and `docs/tickets/DP-512...`
was **not staged, reset, overwritten or cleaned**. Source diff review
was scoped to the three new code/test/ticket bundles and the new
DP-520 ticket. This is not a complete review of the older
`main...integrator` changes or a true PR review gate.

Launch preflight stays **NO-GO/49** (legal Q-306 decisions,
missing release artifacts and ticket gates). `PR_HELD_AUTOREVIEW_BILLING_GUARD`
holds until actual GitHub-linked account/repo Automatic review OFF
readback or authorized alternative and full merge gates.

## Response transport

The updated continuation is mirrored into the **existing** local
`/Users/domenico/ControlCenter/src/controlcenter-ops/tasks/20260929-main-release-closure/310-prompt-to-prompt-20261015/02-WAVE-001-COS.response.md`
after final checks. This shared Ops repository belongs to Core07 for
exclusive Git index/ref/commit/push: a local file update is permitted
within its owned response path, but **Ops Git publication remains
PENDING_CORE07_OPS_LEASE**. No force or bulk stage of foreign WIP.

## Exact next owner unblock

Source-use rights, independent Gold and observed captures for the B
workflow; qualified legal/privacy approvals; canonical PG/budget
authority; approved public Person/Content projection/pin; authenticated
MiniPC deployment/readback; real screen reader/zoom reviewer evidence.
Do not declare DP-237/318/407 DONE, public release-ready, or production
source freshness from these deterministic source fixes.

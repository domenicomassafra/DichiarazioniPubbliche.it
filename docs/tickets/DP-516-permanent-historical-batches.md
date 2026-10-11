# DP-516 — Historical permanent corpus backfill with bounded batches and refresh

Status: IN PROGRESS
Milestone: M7 — stable v1 launch
Depends on: DP-210, DP-215, DP-703, DP-511, DP-514, DP-443

## Problem
 The intended historical corpus of Hitler, Mussolini and other public figures is product content retained for future research, but source rights, authentic quote context, German translation and end-to-end workflow are not yet accepted. Bulk acquisition before the pilot would turn unapproved archive availability and quota abundance into false ingestion/publication authority.

## Outcome
 A permanent, progressively covered and refreshable corpus collection driven by signed source-family authorization and bounded batch manifests; each item retains original language, rights/provenance/attribution, changes, covered gaps, dated observations and an explicit publish/hold outcome. Additional source discoveries enrich prior historical persons rather than silently replacing old findings.

## Traceability & constraints
 R24/R27/R28/R30/R32/R33, owner decisions Q10. Archivioluce and Bundesarchiv are discovery leads only; no automatic download/license grant or endorsement inference. German original quotes and linked identified Italian translations; documented propaganda quotations require speaker-vs-cited-author and speech-act safeguards (B). Source publication date, historical utterance date and newly digitized/observed date are different.

## Scope
 Preflight rights/access/domain/media type, versioned source-of-record inventory, per-Content stable ID, immutable Capture/Passage hashes, explicit local-vs-official chronology, translation assurance, scope-limited source family rules. Stage metadata→rights→capture→transcription/OCR→attribution/context→candidate→finding/position→projection under queue/cost gates. Chunk and batch by source/version with dedup and lineage; no assumed infinite GPT-6 context. First import is bounded to owner-approved source families and item/time/cost envelope; resume exactly from committed checkpoint; multi-person runs are permitted with person/role isolation checks. Later discovery triggers append-only reanalysis and corrections, not full rewrite; maintain coverage-status, recheck cycle and source gone/offline state.

## Non-goals
 Importing all media from cited historical archives, unlimited backfill, political ranking, auto-publishing all found phrases, “all quotes of a person” completeness claims or image generation.

## Dependencies and sequencing
 FIRST-FULL-PILOT acceptance must include full source→public→correction chain; DP-214 distinct 100 real items and DP-703 three launch families remain preserved. Trial monthly quota/cost calibration precedes scale. If source-family rights unavailable, prioritize rights-resolvable alternative sources, record attempts and leave that item HELD; do not substitute a public paraphrase for missing lawful exact wording.

## Acceptance criteria

- [ ] `AC-516.1`: Preflight refuses all bulk when first full pilot lacks signed acceptance, source-family rights remain unknown, or monthly budget/quota cannot reserve work; zero side effects beyond sanitized failed manifest receipt.
- [ ] `AC-516.2`: Approved bounded batch across multiple people and German/Italian contexts preserves source/capture/utterance/observation times, exact original, translation label, author/speaker/quotation distinction and immutable hashes; no cross-person attribution.
- [ ] `AC-516.3`: Resume/retry after halfway crash produces zero duplicate source/capture/Statement/Finding/public routes, retains prior checkpoint, and never reprocesses unchanged copies expensively.
- [ ] `AC-516.4`: A newly digitized, corrected, removed, right-revoked or more complete archived source supersedes or triggers analysis with preserved history and public omission/correction when required.
- [ ] `AC-516.5`: Coverage UI/manifest states fraction scanned only against enumerated approved sources, original language/source-family and last observation; it never asserts all historical sources exhausted.
- [ ] `AC-516.6`: MiniPC pilot-level approved source, held-rights negative, high-risk quotation negative and source change/reanalysis pass before each separately authorized larger batch.

## Validation / proof
 Frozen three-source-family candidate with authoritative rights references; fixture source changes/duplicate lineage and synthetic cost cap; later real authorized archive canary plus MiniPC manifest and downstream public readback. Comparative false attribution/translation/false verdict gold in B/C.

## Documentation, data, and migration impact
 Reuse existing corpus/capture/source-health/matching/retention stores, private batch manifest/checkpoint and source/coverage policies. Public output remains selective, rights-bound, translated visibly and fail closed.

## Completion receipt
**2026-10-11 source-only implementation checkpoint — IN PROGRESS, no backfill.**
`historical_batch_gate_v1.py` builds a deterministic, bounded private review
plan from DP-243 scoped IT/DE historical entries, DP-515 source-watch state,
DP-514 EUR/month and legacy USD policy, and an external DP-443 signed pilot
*claim*. Absent/invalid pilot, rights, watch readiness, budget, changed source
or failed/untrusted checkpoint refuse all proposals and budget reservations.
Unique per-Person/source/Content/Capture work keys, replay fingerprint,
reanalysis and private dedup checks prevent a synthetic retry plan from
silently promoting a different Person or archive. A supplied verifier callback
does **not** authenticate real release authority: `pilot_accepted_by_system`,
`dispatch_authorized`, `public_eligible` all stay false. Source/test commit
`46628d1`, 15 focused synthetic tests and **49** selected DP-516/243/515
tests PASS; Ruff lint+format PASS. This is not real acquisition or an
independently signed DP-443 GO: all AC-516.1–.6 remain unchecked. No MiniPC
readback, source licenses, durable checkpoint/budget CAS, real media or public
projection acceptance yet.

## 2026-10-11 — Checkpoint/archive overlap regression (source-only)

Found a reproducible resume defect: with one trusted synthetic checkpoint for
an original Capture, the batch loop skipped the committed original **before**
recording its cost-dedup identity. An otherwise identical `ARCHIVE_COPY` could
then be proposed as a second paid unit after a halfway crash. The new
`test_resume_committed_primary_cannot_charge_identical_archive_copy` initially
**FAILED**, exposing a redundant archive proposal. The planner now marks a
committed source/capture lineage as deduplicated before continuing, so the
resume proposes only still-uncommitted work. The regression now **PASSES**.

Local source-only proof: 51 DP-243/DP-515/DP-516 tests pass, compilation and
`git diff --check` pass, with synthetic rights/cost/checkpoint receipts only.
No real checkpoint verification, atomic reservation, source acquisition,
provider call, MiniPC replay or public correction/readback was performed.
Status remains **IN PROGRESS**, AC-516.1–.6 remain unchecked, and scaling
remains **NO-GO** pending the existing external acceptance gates.

## 2026-10-11 — Post-checkpoint source-watch revocation and version fence

Source-only review found a distinct fail-open after the checkpoint/archive
dedup fix above. The private planner skipped completed source/Capture units
and duplicate archive copies before consulting their *current* DP-515
source-watch metadata. A previously trusted checkpoint could therefore
return `PRIVATE_REVIEW_PLAN` when that item's watch rights had since changed
to `REVOKED`, or when its watch recorded a newer source-content hash.
The same gap allowed a **not-yet-completed** item with an observed different
source hash to propose paid work against the old manifest-pinned version.

Four adversarial regression tests were added with literal **RED** outcomes
(the old planner returned `PRIVATE_REVIEW_PLAN` instead of `HELD`):

- Resuming a committed Capture after its scoped watch reports revoked rights.
- Resuming a committed Capture when the watch has observed new source bytes,
  with a positive control for unchanged re-observation without second charge.
- Deduplicating an otherwise-identical archive copy whose **own** watch rights
  have been revoked.
- Proposing an uncommitted item after its watch has observed different bytes.

Now every checkpoint/dedup-skipped item rechecks the scoped, versioned watch
contract, current rights readiness and source-content hash without scheduling
a poll or reserving additional funds. Any invalid scope, missing rights
readback, revoked rights or different source hash fails the **whole** batch
closed, with zero proposals and no hypothetical budget update. Pending items
with newer observed hashes are also held for a new DP-243 manifest/source
version instead of processing stale pinned bytes. The existing checkpoint
checksum and cost dedup still work; a matching successfully observed Capture
does not create another paid work unit.

**GREEN:** `PYTHONPATH=poc python3 -m unittest
tests.test_dp243_historical_corpus_preflight tests.test_dp515_incremental_watch
tests.test_dp516_historical_batch_gate -q` completed **56/56 PASS**.
`ruff check`, `ruff format --check`, Python compilation and
`git diff --check` also pass on the DP-516 files.

This is a deterministic, **private source-only planning refusal**. The
readiness strings and receipts remain caller supplied, not independently
attested; the function still has no acquisition, mutation, budget reservation,
publication or withdrawal authority. All **AC-516.1–.6 remain OPEN** and
the ticket stays **IN PROGRESS**. DP-443 signed real pilot acceptance,
authoritative source-specific rights/license evidence, durable checkpoint
and budget CAS, actual German/Italian multi-person attribution/translation,
source-correction/withdrawal readback, comprehensive coverage UI and MiniPC
proof are still required before a separately authorized historical batch.

## 2026-10-11 — Durable isolated checkpoint CAS with immutable revisions

`historical_batch_checkpoint_store.py` adds an opt-in **SQLite** private
transactional checkpoint journal for the existing DP-516 `BatchCheckpoint`
model. A preauthorized caller can append a separately verified, immutable
Capture receipt under `BEGIN IMMEDIATE` compare-and-swap; the journal stores
every revision append-only with SQL UPDATE/DELETE refusal triggers. Two
independent connections, restart after the first committed Capture, identical
retry, a stale expected revision, a reused item key with changed receipt and
a foreign manifest fingerprint are covered. Failure leaves prior versions
intact; no completed Capture is silently replaced.

`tests/test_dp516_durable_checkpoint_next.py` first failed to import the
new persistence boundary (**RED**). It and existing historical batch tests
then passed **23/23** (**GREEN**), along with adjacent private visual
operator persistence tests for a combined **48/48**; lint/compilation pass.
This is materially different from the old source-only proposed checkpoint:
a committed local revision can now survive a crash and be independently
read back from a fresh connection, though it is still **not** the authoritative
MiniPC production store.

The `verify_persisted_capture` callback must come from a separately
authenticated source/Capture ledger; a test callback returning `True`
does **not** prove real source rights, signature or completed capture. The
journal does not reserve EUR or USD budget, dispatch jobs, certify a DP-443
pilot, download archival sources or publish any result. Multi-person real
German/Italian source/attribution acceptance, production transactional
budget coordination, source-revocation readbacks, MiniPC and release remain
OPEN. **DP-516 stays IN PROGRESS, AC-516.1–.6 unchecked, release NO-GO.**

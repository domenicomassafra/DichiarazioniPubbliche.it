# DP-242 — Studio source-to-candidate machine handoff and exception lifecycle

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-416, DP-417, DP-418, DP-419

## Problem

Studio inbox/collection is increasingly capable at read-only inspection and annotation, yet a queued record can stop at `QUEUED_FOR_HUMAN_REVIEW`. The owner has no ordinary human editorial reviewer. Existing annotation signature and review/promotion rights cannot be converted into fake machine/human approvals.

## Outcome

A private operator can inspect and re-run the real ingestion→source recovery→candidate analysis pipeline; eligible rows are sent to the future governed autonomous machine authority (B), while hard provenance/rights uncertainties run bounded research or land in a **small actionable exception queue** with no pretend approval/publication.

## Traceability & constraints

R11/R23/R25/R26/Q14, B owns machine review/final verification/publishing and current gate migration; A owns Studio/source/candidate state transitions only. Private loopback API credentials distinct from public reader/account.

## Scope

Real persisted rows across Discovery, changed Capture, entity matches, statements/claims, Coverage Needs and held rows; inspect source rights/span/attempt chronology, preview allowed reversible actions, idempotency/CAS checks, asynchronous step progress and negative outcomes. Integrate existing `DiscoveryInboxWorkflow`, triage ledger, `studio_candidate_review` handoff and rights/source selectors with B's explicit new authority API/receipt. Clear boundaries between annotation, research plan, verified candidate and autonomous decision.

## Non-goals

Auto-approve persons based on a model's confidence, reintroduce routine textual reviewers, bypass B publication policy, bulk publish or expose Studio remotely through OAuth.

## Dependencies and sequencing

Hard DP-416/417/418/419 actual persisted paths; soft DP-235, DP-241 source state, B machine approval contract and transactional revocation, D background scheduler. Real transition remains blocked if authority API is unavailable, not silently simulated.

**Milestone reconciliation (2026-10-11): M4.** This is the private Studio/API operator handoff, with all four hard UI/workflow prerequisites in M4. M2 source/Capture/Candidate inputs remain prerequisites to a real demonstration; placing the ticket in M4 does not complete the authority or MiniPC acceptance criteria.

## Acceptance criteria


- [ ] `AC-242.1`: Each real queue family has bounded provenance/rights/identity/action currentness and a specific machine-action or investigation/exception decision; no generic "ready" without state.
- [ ] `AC-242.2`: Review/analysis handoff records exact source/Capture/Passage/Person candidate/rights snapshots and authority-version fingerprint; stale snapshot or source revocation forbids transition.
- [ ] `AC-242.3`: Same action key replays identically, conflicting/stale revision fails, incompatible bulk groups cannot share a permission or promote across families.
- [ ] `AC-242.4`: Safe eligible path reaches real candidate analysis and governed B API/receipt, including evidence of resumed downstream output; missing B authority produces explicit blocked state instead of human-reviewed=true.
- [ ] `AC-242.5`: Negatives (secret, cross-collection, rights revoked, wrong source, publisher mismatch, provider unavailable) preserve private isolation and no public Finding/PUBLISH increase.
- [ ] `AC-242.6`: MiniPC operator real-source path plus keyboard-accessible 320–1440 viewport/readback verified, including retry, bounded queue and exception processing.

## Validation / proof

Real authorized run with actual persisted Discovery Hit + Candidate; state-machine and CAS adversarial fixture; loopback authenticated HTTP, MiniPC DB/authority receipt, no-public-change counters. Mocked/historical Garlasco zero-Hit paths do not close AC.

## Documentation, data, and migration impact

Reuse real ledger/private API, B owns machine signature trust and cutover. Append-only provenance and safe readers; never expose machine score/person opinions.

## Completion receipt

**2026-10-11 — Source-only preflight implemented, acceptance still OPEN.**
`studio_machine_candidate_handoff_v1.py` reuses the actual DP-417
collection-scoped PostgreSQL Hit selector/normalizer and DP-418 persisted
match-currentness readback. The operator-only preview re-reads exact Hit
provenance, manifest/revision/currentness and source/Capture/Passage fingerprints;
it refuses changed or cross-collection inputs, bounds the selection to one
object and reports actionable `HELD_EXCEPTION` or
`HELD_MACHINE_AUTHORITY_UNAVAILABLE`/`HELD_SOURCE_OR_ATTRIBUTION`. It hashes an
idempotency *intent fingerprint* but does not persist it or claim CAS.

Additionally, the existing authenticated, explicit opt-in loopback Studio API
exposes `POST /v1/discovery/machine-preview` and
`POST /v1/candidate/machine-preview` with exact field allowlists, token,
origin/host checks, localhost-only bind and `Cache-Control: no-store, private`.
The SQL session remains read-only; direct HTTP negatives cover missing bearer,
hostile Origin, injected approval field and revoked Capture. HTTP route commit
`74b5d56`; **34** tests PASS in the focused + existing API/Studio suite.

Focused plus existing Studio regressions: **26 PASS** in
`tests.test_dp242_studio_machine_handoff`,
`tests.test_studio_discovery_inbox_workflow`, and
`tests.test_studio_candidate_review_handoff`; `ruff check` PASS. Source commit
`d2d1729`. These receipts are local synthetic tests, not a real executed
machine transition. All AC-242 boxes remain unchecked: no governed B API,
credentialed HTTP receipt, persisted exception lifecycle, actual source
end-to-end path or MiniPC/UI acceptance. The old human review spool is left
unchanged and never impersonated.

**2026-10-11 — Additional candidate preflight lineage guard (source-only;
DP-242 still IN PROGRESS).** Adversarial test against the original
`preview_candidate_machine_handoff` showed **7 RED subcases**: a non-public
Person, missing Statement Candidate link, a mismatch between declared and
actual Passage counts (including a boolean count), contradictory written/media
counts, and a missing Capture reference could all yield
`HELD_MACHINE_AUTHORITY_UNAVAILABLE`. That state implied a coherent source
preflight even though the persisted promotion inputs lacked the required
actor/source lineage. The source preflight now reserves this status for a
single written Passage tied to a real Capture, declared as exactly one written
and zero media occurrence, with a linked Statement Candidate and a public
speaker. Malformed inputs return `HELD_SOURCE_OR_ATTRIBUTION` and the existing
investigation action; additional negatives cover whitespace speaker IDs,
unexpected media segment IDs and missing Passage IDs. The prior source/Capture
revision and fingerprint rechecks remain in place. The fix does not inherit
human editorial flags as machine permission; its explicit no-authority fields
and deterministic, preview-only intent receipts remain unchanged.

The newly added regression was proven RED before the fix and GREEN afterward;
**30 local focused/adjacent tests PASS** (DP-242 pure and loopback HTTP,
DP-417 Inbox, DP-418 Candidate), with `ruff check`, `compileall` and
`git diff --check` PASS. These are synthetic local readback assertions.
There is still no persisted
idempotency ledger or transactional CAS, independent B API/signature/rights
attestation, real candidate execution/downstream receipt, MiniPC real-source
acceptance or keyboard/UI proof. Therefore **all AC-242 boxes remain open**;
no publish/dispatch/review authority is asserted.

## 2026-10-11 — DP-240 mixed-Person batch → private Studio exception preview

Added a distinct read-only `preview_private_batch_machine_handoff` entry
point and `CurrentBatchStudioItem` source/identity/rights snapshot contract
in the **existing** DP-242 module; DP-240's source and tests were not changed.
This consumes the new `PrivateBatchReceiptIndex` only after its DP-240
`export_private_batch_receipt_index` revalidates the exact ordered
manifest/plan, source lineage, duplicate/replay rules, item statuses, count
integrity and no-authority flags. A **separately supplied, pinned current
receipt SHA-256 is mandatory**: absence, malformed pin or a superseded
receipt refuses the whole preview. The private read side also requires
independently fetched current per-Passage Content, Capture, original source
and Passage hashes, selector, Person **candidate** reference, context version/
review reference, speech role/act, identity review status, rights status,
rights evidence hash and source/identity/rights revisions. Missing/invalid,
foreign, revoked, or changed source/identity/rights snapshots cannot be
classified as clean machine-handoff preflights. Any readback that changes
while the preview is constructed invalidates the whole result; this double
read is **not** a transactional database lock.

Each record has an exact Capture→Passage→source hash and partition, separate
language and candidate Person IDs (including same-name homonyms), a
deterministic per-item intent fingerprint, one actionable sanitized reason
and operator action. Example negative states include
`HELD_CURRENT_READBACK_MISSING`, `HELD_SOURCE_SCOPE_MISMATCH`,
`HELD_STALE_SOURCE`, `HELD_SOURCE_RIGHTS`,
`HELD_RIGHTS_EVIDENCE_MISSING`, `HELD_IDENTITY_CHANGED`,
`HELD_EXTRACTION_FAILED` and `HELD_EXTRACTION_UNOBSERVED`.
Quote/reporting-role and attribution ambiguity retain explicit investigation
actions. Only an unchanged, separately source-checked
`PRIVATE_CANDIDATE_UNVERIFIED` receipt reaches
`HELD_MACHINE_AUTHORITY_UNAVAILABLE` with
`AWAIT_INDEPENDENT_B_MACHINE_AUTHORITY`—**not** a real authority receipt,
dispatch or human review. Arbitrary provider failure payloads are reduced
to a boolean recorded flag, never rendered as source/private text.

Five new adversarial test methods were RED initially because the batch
handoff and current-source interface did not exist, then GREEN for mixed
IT/DE Persons/Contents, homonyms, quoted speech, partial failures,
unobserved retries, changed/revoked rights, missing rights evidence,
missing/changed current identity/source, wrong Capture/Content,
stale/missing receipt pin, forged DP-240 checksum/replay, invalid request
keys and a mid-preview readback mutation. No source, reviewer, Person
identity or B credentials were forged. Final local validation:
`PYTHONPATH=poc python3 -m unittest
tests.test_dp242_studio_machine_handoff
tests.test_dp242_studio_machine_http
tests.test_dp240_multi_person_batch
tests.test_studio_discovery_inbox_workflow
tests.test_studio_candidate_review_handoff -q`: **61/61 PASS**;
`ruff check`, `ruff format --check`, targeted Python compilation and
`git diff --check` PASS. No live network, provider, persisted DB write,
MiniPC, Cloudflare, publication or authorization used.

**All AC-242.1–.6 remain OPEN, status IN PROGRESS.** This is an
offline caller-supplied source-only operator proposal contract, not actual
authenticated Studio lookup, persistent idempotency/CAS/exceptions,
independently qualified source/rights/currentness attestation,
reviewed Person attribution, B machine authority API/receipt, downstream
candidate extraction, MiniPC replay, measured latency, live counter
invariance or keyboard/viewport proof. A future real adapter must obtain
the independent snapshots and pinned receipt from trusted storage and
recheck under a transactional fence. No public machine acceptance implied.

## 2026-10-12 — Disposable SQLite persisted DP-240 → DP-242 held handoff

Added a **separate opt-in local persistence seam** in the existing
`studio_machine_candidate_handoff_v1.py`:
`LocalPersistedBatchMachineHandoff`. It creates only `dp242_*` **isolated
SQLite fixture tables**, with distinct Source, Capture, Passage, Capture
rights and immutable held handoff rows; this is **not** a migration or adapter
for the canonical PostgreSQL production schema. The caller must supply an
already persisted, independently pinned DP-240 batch plan and exportable
receipt plus an independently read Source/Capture/Passage/rights snapshot pin,
Capture SHA-256 and expected per-Passage handoff revision. The adapter
re-reads the normalized SQLite rows in a `BEGIN IMMEDIATE` transaction,
checks source collection, exact Content→Capture→Passage relationships,
source/passage/selector hashes, capture byte hash and hold/status, rights
status/evidence/revision, Person candidate/context/identity metadata,
immutable DP-240 receipt and current SQLite snapshot hash. Only a
`PRIVATE_CANDIDATE_UNVERIFIED` item with a coherent source may persist a
`HELD_MACHINE_AUTHORITY_UNAVAILABLE` receipt; no B authority is created.

The actual SQLite write CAS increments the Passage handoff revision and
inserts the private immutable, checksum-bound, request-key-unique receipt
in **one transaction**. Same-key retries on a reopened database return
identical committed metadata while source/rights are current; a changed
request key body conflicts, independently reused stale revision fails, a
failed INSERT rolls back the revision update, and two concurrent SQLite
connections contending for one expected revision yield exactly one
durable winner. Changed/revoked rights block even a prior key replay;
wrong collection, Source/Capture/Passage content, selector, source hash,
Capture hash, identity revision or source snapshot pin fail closed. No
text/provider failure reason, reviewer identity or publication grant is
persisted. Tests use a real **disposable on-disk SQLite database**, not a
mocked store and not MiniPC/production storage.

**TDD:** the new seven-method regression suite initially failed to import
the absent persistence adapter (RED). After implementation, the complete
focused set `test_dp242_persisted_handoff_next`,
`test_dp242_studio_machine_handoff`, `test_dp242_studio_machine_http`,
`test_dp240_multi_person_batch` and
`test_studio_candidate_review_handoff` ran **58/58 PASS** (GREEN).
`ruff check`, `ruff format --check` and `git diff --check` passed.
An unrelated existing candidate-review SQLite resource warning did not
fail tests. No live candidate extraction, provider, authentic B
signature/receipt, real PG17 authority fence, public projection, MiniPC,
Studio UI/API edit or production deployment was attempted. This private
durable `HELD` record is **not an executable downstream B job**.

**Status remains IN PROGRESS; AC-242.1–.6 all OPEN.** Real PostgreSQL
Source/Capture/Passage integration, separately qualified source rights,
machine B authority and resumption, end-to-end authorized source proof,
UI/keyboard/MiniPC acceptance and production writer serialization must
still be demonstrated independently. No false human review or operator
publication capability was created.

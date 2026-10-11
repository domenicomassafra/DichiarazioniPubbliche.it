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

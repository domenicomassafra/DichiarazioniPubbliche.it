# DP-240 — Bounded multi-person candidate batch with cross-source identity isolation

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-211, DP-212, DP-218, DP-222

## Problem

Existing `private_candidate_batch` accepts 1–16 Passage items, but that is neither multi-person semantic acceptance nor an efficiency benchmark. Multi-speaker sessions, interviews, reported speeches and homonyms may contaminate outputs; a very large model window does not remove attribution risk.

## Outcome

Deterministic, budgeted batch planning and candidate extraction over several Contents, languages and Persons with per-span source identity, role and context intact, per-item replay/failures and independently observed precision/cost compared with bounded single-source baseline.

## Traceability & constraints

R07/R11/R26/Q12, DP-219/220 nested quote/context. No biometric identity, no automatic cluster equality by topic or lexical similarity. Source roles and languages are not person IDs.

## Scope

Reuse existing Capture/Passage Candidate batch rather than replace it. Partition by capture version, source family, context continuity, speaker/author candidate and language; preserve source→span→Person/role candidate mapping per output. Freeze batch fingerprint, per-item allocation, per-stage token/audio budget, cross-item leakage detectors, fallbacks, job retries, and per-item ledger. Compare baseline isolated runs against bounded mixed batch and do not impose an unsupported universal 1-person limit.

## Non-goals

Unlimited context windows, one-person-only policy, face/voice matching, direct publication and B's final machine reviewer authority.

## Dependencies and sequencing

Hard original extraction/matching/speaker contract. Soft DP-235 source set, DP-239 language, B semantic attribution, D quota measurement. Runtime provider access still explicit gate.

## Acceptance criteria


- [ ] `AC-240.1`: Versioned batch manifest contains at least two distinct approved Persons or unresolved speaker candidates, more than one Content and exact Passage selectors/source hashes; items cannot silently borrow another's source ID.
- [ ] `AC-240.2`: Explicit adversarial wrong-speaker/quoted-voice/homonym examples yield separate held candidates, with per-segment source/speaker/author context and no public attribution.
- [ ] `AC-240.3`: Each output Statement/Claim Candidate maps to its own source spans, extraction version and original wording; no stitched cross-source verbatim or forced speaker ID.
- [ ] `AC-240.4`: Duplicate items, reordered batch, partial provider failure, retry and same idempotency key preserve cardinality/lineage and do not convert failed items to success.
- [ ] `AC-240.5`: Source-level token/cost/latency/memory and false-attribution rates are measured against a preregistered isolated baseline; approve larger batch sizes only based on observed benefit and non-regression.
- [ ] `AC-240.6`: MiniPC persisted replay and Studio operator inspection prove each candidate's correct original Content, Person candidate and hold reason; unrelated corpus/public counts remain unchanged.

## Validation / proof

Attributed gold annotated independently; mixed Italian/German where permitted, official multi-speaker AKN fixture only as a *negative/candidate* baseline until rights clearance; per-item replay receipt, false attribution confusion matrix, D budget counters, MiniPC readback.

## Documentation, data, and migration impact

Reuse `private_candidate_batch`, candidate matching, DP-218/222; change only necessary per-item provenance keys, migration additive if needed; no second claim table.

## Completion receipt

**2026-10-11 — partial local implementation, NOT acceptance:** added
`poc/dichiarazioni_pubbliche/multi_person_batch_v1.py` and
`tests/test_dp240_multi_person_batch.py`. The private, no-provider planner
reuses the existing immutable candidate-batch manifest, enforces exact
Content/Capture/Passage/source SHA and selector context, distinct Passage
partitions, candidate speaker roles, rights/context holds, and bounded token
allocation. Reconciliation records per-item partial/failed/held observations
as private-only, never as a published attribution. Plan fingerprint, cardinality,
count consistency, per-item provenance and reserved authorization fields are
rechecked before replay; checksum is **not** a signature or evidence of
upstream approval. Adversarial cases cover quote vs endorsement, homonyms,
cross-source mismatches, held-item fabricated success, plan tampering, duplicate
and conflicting replay, unbounded input and retries. **15/15 focused tests PASS**;
**27/27 candidate-batch regression tests PASS**, `compileall` and `git diff
--check` PASS. Test contexts are synthetic; no actual candidate or provider
call, published Statement, measured cost/latency/false-attribution baseline,
independent gold, durable store or MiniPC/Studio operator readback exists.
**AC-240.1–.6 remain open** pending those corresponding end-to-end proofs.

# DP-418 — studio candidate promotion cluster review

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-117, DP-212, DP-414

## Problem

Matching/promotion decisions are too consequential to live only in logs or implicit model output.

## Outcome

Implement a candidate review surface that compares source wording/passages, normalized proposition, match candidates, cluster features and promotion blockers before an explicit approve/link/create/reject action.

## Scope

- Side-by-side source context + candidate proposition + candidate existing claims/clusters.
- Expose supporting/contradicting match features and algorithm/version; do not render score as truth confidence.
- Promotion action calls DP-117 and displays durable receipt/result.
- Rejection/hold/split-cluster actions preserve candidate history.

## Non-goals

- No person/source trust score.
- No one-click auto-publish.
- No equivalence approval based solely on vector similarity.

## Dependencies and sequencing

DP-117, DP-212, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-418.1:** Reviewer can distinguish duplicate extraction, same proposition, related proposition and uncertain cases.
- [ ] **AC-418.2:** Promotion blocker is visible before mutation.
- [ ] **AC-418.3:** Replay/refresh shows the persisted decision, not reconstructed model state.
- [ ] **AC-418.4:** Keyboard and 200% zoom workflow remains operable.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Private Studio review UI; promotion service is backend authority.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Persisted match-run read-only inspection — 2026-10-08

`studio_candidate_review.py` reads an existing DP-212 `candidate_match_run`
and its persisted `candidate_match_result` rows using the canonical
`CandidateMatchingStore.get_run/load_results` methods. It requires an exact run
and candidate binding, completed state, bounded count, valid fingerprint,
deterministic rank and match class/disposition consistency. It returns only
bounded IDs, match classes and feature **codes**, never raw match features,
private candidate/source text, numeric similarity scores or reviewer notes.

The response explicitly states `currentness=UNVERIFIED`,
`review_authority=false`, `publication_authority=false` and
`promotion_enabled=false`: a persisted matching suggestion is **not** a
currentness decision, review decision or promotion permit. No database mutation,
cluster materialization, HTTP endpoint or public build change is introduced.

This is an internal read-only prerequisite, not the completed DP-418 workflow.
The authenticated private Studio UI, exact source/passage comparison, blocker
before mutation, canonical currentness/authority checks, review/approval replay
and keyboard/MiniPC acceptance all remain open. Synthetic focused tests cover
normal, missing/stale/conflicting and private-feature-leak paths.

Follow-up 2026-10-08: persisted match-run inspection now has a token-
authenticated local read-only HTTP/HTML transport with PostgreSQL
transaction-level read-only enforcement and bounded network/DB timeouts.
No write endpoint exists. Matching currentness and reviewer authority
remain unverified, so the UI cannot promote, accept or merge candidates.

### 2026-10-09 persisted match-read binding and safe feature semantics

The read-only inspector now checks deterministic DP-212 run/result
identities against the requested candidate, run, target type and
target ID. It rejects duplicate targets, noninteger/boolean ranks,
unrecognized matching methods and unexpected structured feature
codes before returning a private Studio suggestion. Existing
ClaimType/temporal-scope contradiction codes can force `HOLD`
even when lexical similarity yielded `SAME_PROPOSITION`; the
inspector refuses a persisted `PROPOSE_CLUSTER` in that case.
This keeps the audit from repeating altered suggestion rows as if
they were valid matching output. Focused RED→GREEN tests exercise
cross-run IDs, retargeting and conflicting scope, with the actual
DP-212 matching algorithm remaining authoritative.

`currentness=UNVERIFIED`, `review_authority=false`,
`publication_authority=false` and disabled promotion are
unchanged. No persisted review mutation, source rights, real
MiniPC match canary, keyboard workflow or authority acceptance
is introduced; DP-418 stays IN PROGRESS.

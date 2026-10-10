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

### 2026-10-09 Wave 14 — persisted matching version and result-state binding

The read-only Studio inspector displayed the current `matching_version`
constant without validating `candidate_match_run.matching_version` or
each persisted `candidate_match_result.matching_version/status`. A stale
row could therefore appear to use the current algorithm even when it did
not. The SQL reader now returns these actual persisted fields and the
inspector refuses missing/mismatched versions and non-`CANDIDATE` status
before presenting a suggestion. Six adversarial RED subtests became
GREEN. Its output still declares `currentness=UNVERIFIED`, no reviewer
or publication authority and disabled promotion. This is not real
reviewer authorization or a closed DP-418 runtime acceptance.

### 2026-10-09 Wave 19 — stored class feature integrity

The read-only inspector previously checked known feature code names,
match class and method, but not whether the classifier's persisted
explanatory feature signature actually justified that class. An altered
row could show SAME_PROPOSITION without exact normalized or lexical/context
support, DUPLICATE_EXTRACTION without same-selector support, or another
class without its canonical evidence code. Duplicated codes and mutually
inconsistent ClaimType/time evidence were also accepted.

The narrow fail-closed check follows the existing deterministic DP-212
classifier without reprocessing private source words. Duplicate requires
same selector and exact normalized text; exact same proposition requires
exact normalized text; lexical same proposition requires high overlap
plus shared entities or topics; related, different and uncertain require
their own primary supporting/contradicting codes. Duplicate and
contradictory feature codes are refused. Eight adversarial RED subtests
and seven canonical positive signatures became GREEN.

This validates persisted feature codes, not the underlying private
text, mutable feature values, reviewer currentness, cluster equivalence
or authority. No score, source body, promotion, cluster write or public
output is exposed. DP-418 stays IN PROGRESS.

### 2026-10-10 — Currentness/blocker and persisted handoff readback

The operator-local authenticated `/v1/candidate/review-readiness` exposes
the existing deterministic DP-212 input/result replay and current DP-117
promotion blockers **before mutation**. Optional read-only
`/v1/candidate/handoff-receipt` loads an immutable previously enqueued
candidate review request from an explicitly configured owner-private 0700
spool, enforces exact Candidate/Run binding, and redacts reviewer identity
and credential references. It cannot approve, promote, record a decision
or claim persisted request currentness; the spool defaults to disabled.
Mac full test suite 2266/2266 and isolated MiniPC focused 44/44 passed;
benchmark 5/5. No live candidate/match/capture data is present on MiniPC.
Actual reviewer decision readback, rights and keyboard/200% acceptance
remain open; no AC is marked complete by this metadata-only prerequisite.

### 2026-10-10 — persisted review-currentness and duplicate classification guard

DP-117's persisted preflight and each promotion mutation previously used
`EXISTS(review_event ... action='APPROVED')`, which treated an old approval
as current even when a later REJECTED or QUARANTINED event existed. The
canonical context and all three SQL mutation branches now require the
**latest event by `created_at DESC, id DESC`** for the exact candidate or
statement identity to be APPROVED. The preflight propagates this state to
Studio blockers and remains a read-only preview until DP-117 revalidates.

Matching an identical normalized proposition is insufficient to prove the
same source extraction. The preflight exposes it as
`same_proposition_target_ids`, separately from approved, matched
`DUPLICATE_EXTRACTION` cluster edges. A same-proposition target now blocks
promotion with `PROMOTION_SAME_PROPOSITION_REVIEW_REQUIRED`, and the
`LINKED_EXISTING` mutation refuses the previous exact-wording shortcut or
SAME_PROPOSITION cluster edges. New-claim mutation SQL continues to refuse
creation while a known equivalent or duplicate target exists. Studio displays
the distinction and refuses a direct `REVIEW_LINK` handoff for a mere
SAME_PROPOSITION model suggestion; review request storage remains private
and grants no promotion/review/publication authority.

Persisted promotion replay now checks its exact candidate ID, promotion
version, deterministic receipt/key, selected provenance channel, candidate
status/target and a single bounded provenance reference before returning an
existing receipt. Inconsistent rows report `PROMOTION_REPLAY_CONFLICT`.

Focused tests cover revoked approvals, same-proposition preflight, replay
conflicts, Studio blockers and review-link handoff refusal. Two tests on an
isolated real PostgreSQL database using `db/schema.v1.sql` confirm the
latest persisted review actions and the actual distinction between exact
proposition and reviewed duplicate cluster members.

These changes are prerequisites only. Original AC-418.1–AC-418.4 stay open:
the reviewer still lacks the full authenticated compare/decision workflow,
the complete channel/rights blocker preview, independently persisted human
decision readback, and measured 200%-zoom/keyboard acceptance. Concurrent
review-event writers are not serialized with all DP-117 SQL transactions;
the statement snapshot checks the latest committed event visible when its
query starts, and additional transaction-authority design is still needed
before claiming a universal race-free legal/human approval gate. No MiniPC
live runtime acceptance or public enablement is asserted.

# DP-310 — Independent publication review and dual-control for high-risk records

Status: DONE
Milestone: M3 — Editorial, correction, privacy, and legal policy
Depends on: DP-308, DP-309; coordinate with DP-301..DP-307

## Problem

An explicit review event is necessary but does not by itself prevent one operator from
extracting, interpreting and publishing the same high-risk item without a second check.
For the most reputationally sensitive records, a simple self-approval path leaves an
avoidable single-point-of-failure.

## Outcome

Add a versioned review-separation policy. Ordinary records retain the existing explicit
review gate; records classified `HIGH/LEGAL` by DP-309 require a second eligible reviewer
who did not author the final attribution/verification decision. If no second reviewer is
available, the safe result is a hold, not self-certification.

## Scope

- Define review roles/actions without introducing user accounts unless an admin HTTP
  surface actually exists; local/operator identity may remain the v1 mechanism.
- Record actor, action, previous-stage actor(s), policy version, timestamp, reason codes and
  the exact source/claim/finding versions reviewed.
- Prevent the same actor from satisfying both required high-risk approvals.
- Re-review is required after load-bearing quote/speaker/context/evidence/finding changes.
- Correction/appeal workflows preserve their DP-303 separation requirements and may have
  stricter independent-review rules.
- The system never invents independence: if staffing/identity cannot prove separation, it
  reports `REVIEW_SEPARATION_UNAVAILABLE` and holds publication.

## Non-goals

- No claim that two reviewers guarantee legal correctness.
- No public display of reviewer personal data beyond approved governance disclosure.
- No forced second reviewer for every low-risk internal action.
- No weakening of existing provenance/verification/publication gates.

## Acceptance criteria

- [x] **AC-310.1:** `HIGH/LEGAL` candidates cannot reach public projection with one actor
  satisfying both required review stages.
- [x] **AC-310.2:** Low-risk records still require the existing explicit review but do not
  gain unnecessary bureaucracy unless policy says otherwise.
- [x] **AC-310.3:** Actor identity, reviewed object versions and policy version are durable
  and replayable without storing secrets/private notes in public output.
- [x] **AC-310.4:** Material source/quote/speaker/context/evidence/finding changes stale the
  relevant approval(s) and require re-review.
- [x] **AC-310.5:** Missing/ambiguous operator identity or lack of an eligible second reviewer
  produces a hold and a clear next action.
- [x] **AC-310.6:** Direct status/DB tampering cannot synthesize the required review chain.
- [x] **AC-310.7:** Correction/appeal reviewer-separation semantics remain compatible with
  DP-303 and never rewrite history.
- [x] **AC-310.8:** DP-308 includes review-separation as a mandatory invariant for the
  applicable risk class.
- [x] **AC-310.9:** Full suite, DP-223 benchmark and MiniPC canary pass.

## Validation / proof

Test same-actor rejection, different-actor approval, unavailable-second-reviewer hold,
stale approval after source/claim change, correction/appeal path and direct persistence
tampering. Run standard checks and MiniPC read-back.

## Documentation, data, and migration impact

Reuse the append-only review ledger where possible. If actor/review-stage constraints need
new persistence, use additive schema and document the operator identity model without
prematurely building DP-507's future admin auth surface.

### 2026-10-10 legacy public-writer review-event collision maintenance

Disposable PostgreSQL RED tests exposed a defect below the independently
attested DP-310 projection gate: direct Finding, reply and correction
writers could move a record to PUBLISH/PUBLIC even if their
\`review_event\` insert was skipped by an unrelated event-ID collision.
The repaired SQL gates each public status transition on the new matching
event, with idempotency only for an already-public record and the
unchanged event/entity/actor/reason. A correction cannot mark the prior
Finding CORRECTED without its own receipt. See
[\`public-review-event-publication-fence-20261010.md\`](../ops/public-review-event-publication-fence-20261010.md).
This is additional source integrity, not a substitute for qualified
reviewer identity, legal sign-off or launch authorization.

## Completion receipt

Local `publication-review-control-v1` now provides the dependency-safe pure review contract
over DP-308 `publication-safety-v1` and DP-309 `high-risk-assertion-v1`. `STANDARD` records
retain one explicit `DECISION_REVIEWER` approval and do not acquire dual-control semantics.
`HIGH/LEGAL` records require a second `INDEPENDENT_PUBLICATION_REVIEWER`; actor identity and
opaque credential fingerprint must both differ, and the independent reviewer must also be
separate from supplied upstream decision actors/credentials. A recorded separation exception
remains audit evidence only and never satisfies dual control.

Review events are immutable, policy/version bound and hash chained with existing
`APPROVED`/`REJECTED`/`SUPERSEDED` action vocabulary. Later decisions append to the chain;
they do not rewrite earlier approvals. Events bind the exact finding version, DP-308 safety
profile/binding and a deterministic DP-309 decision/input binding. Any changed
source/quote/speaker/context/evidence/finding safety reference, record version, or high-risk
input binding requires re-review. Missing second review produces `REVIEW_SEPARATION_UNAVAILABLE`
with `OBTAIN_INDEPENDENT_PUBLICATION_REVIEW`; duplicate actor/credential and explicit
exceptions produce `OBTAIN_SEPARATE_REVIEWER`.

Focused tests cover HIGH and LEGAL two-person review, STANDARD single review, duplicate actor
and credential, wrong role, upstream-author separation, explicit exception, stale safety and
high-risk bindings, append-only rejection, content tamper and exact-event replay. The result is
review completeness only and exposes no publication-authority flag. AC-310.1 and AC-310.6 are
closed by the mandatory production projection composition described below; at that receipt stage AC-310.9 remained open
for the full-suite/benchmark/MiniPC proof.
AC-310.8 is now closed by `publication-eligibility-v1`. That final pure composition seam
recomputes the DP-310 result from exact review events and binds the DP-308 safety receipt,
DP-309 decision/input binding, review policy/risk class and counted event IDs. `HIGH/LEGAL`
candidates with only one review remain held with explicit review-separation blockers; the
composition result is only readiness for projection-time revalidation and creates no
publication-authority flag. The local hash chain intentionally does not claim that it can
authenticate a wholly fabricated database history without a durable identity authority.

Persistence/identity hardening proof 2026-10-06: an additive private
`publication_review_event_durable` ledger plus `publication_review_persistence.py` now preserves
the exact actor ref, opaque credential fingerprint, reviewed record ID/version, review policy
version and full DP-310 event payload. Ordinary SQL `UPDATE`, `DELETE` and `TRUNCATE` operations
are rejected by append-only triggers as defense in depth. Replay is stricter than the database:
every event must resolve an opaque identity-authority receipt from a caller-owned
`ReviewerIdentityAuthority`, and that attestation must bind the exact event integrity digest,
actor/credential, reviewed object/version and policy version. Missing authority, unknown receipt,
receipt reuse against a different event, or a mismatched stored authority binding fails closed.

Disposable PostgreSQL proof: **6/6 PASS**. It proves exact durable replay of a valid two-reviewer
chain; missing authority hold; normal-writer append-only enforcement; rejection of a completely
fabricated but internally hash-valid two-event database history; rejection of a copied genuine
authority receipt on a different fabricated event; and preservation of the same actor identity
used by DP-303 appeal-separation semantics. Existing DP-310 pure review + DP-303 policy tests:
**49/49 PASS**; `py_compile` and scoped `git diff --check` PASS.

DP-311 now supplies the concrete local reviewer identity authority separately from DP-507's
future remote admin surface. Durable replay therefore resolves each event through an off-DB
authority receipt bound to the actor, opaque credential fingerprint, exact event integrity digest,
reviewed record/version and policy version. The durable ledger stores only the opaque receipt ID
and binding; reviewer secret material and receipt MACs remain outside PostgreSQL. This closes
AC-310.3 without introducing a public serializer field or a remote identity surface.

The end-to-end publication boundary now consumes the attested path. `ProductionPublicProjectionStore`
treats the legacy SQL row as a candidate only; before serialization it recomputes DP-308 safety,
replays the current DP-309 reviewed packet, and invokes `evaluate_publication_eligibility()` over
the durable DP-310 ledger plus the DP-311 off-DB authority. A missing authority, one-reviewer
`HIGH/LEGAL` chain, fabricated hash-valid DB history, copied receipt, stale binding or same-actor
chain therefore returns a hold and the candidate is omitted. This closes AC-310.1 and AC-310.6
without treating mutable `review_event` status as publication authority.

AC-310.7 closure proof 2026-10-06 uses the concrete DP-311
`LocalFileReviewerIdentityAuthority` with the durable PostgreSQL ledger. The focused acceptance
appends an attested original Finding review, derives DP-303's `original_reviewer_id` from durable
replay, proves that the same actor cannot reach an `UPHELD` or `OVERTURNED` appeal outcome, and
proves that a separately credentialed reviewer can reach the allowed `UPHELD` path. It then
appends distinct attested appeal-review and corrected-Finding review records. After those later
events, the original durable row — including `persisted_at`, event JSON, integrity hash,
authority receipt ID and authority binding — is unchanged, and the original local-authority
receipt file is byte-for-byte unchanged. A fresh authority instance still replays the original
record as exactly the original event.

Focused proof: `tests.test_publication_review_persistence` **9/9 PASS**,
`tests.test_policy_challenge` **36/36 PASS**, and `tests.test_reviewer_identity_authority`
**9/9 PASS**. The later production-projection composition supersedes the earlier projection-gap
note above. At that receipt stage AC-310.9 remained open for full-suite/benchmark/MiniPC acceptance.

Authority-backed runtime eligibility proof 2026-10-06: `publication_eligibility.py` now exposes
one runtime `evaluate_publication_eligibility()` seam that accepts a concrete
`PublicationReviewPersistenceStore` plus `ReviewerIdentityAuthority`, performs
`replay_attested_chain()` itself, and only then recomputes the DP-308/309/310 eligibility result.
The caller can no longer feed this runtime API a completion boolean or a self-consistent in-memory
review hash chain. The raw-event composer remains private as a deterministic unit-policy helper.
Missing authority produces `REVIEW_IDENTITY_AUTHORITY_UNAVAILABLE`; a hash-valid two-event ledger
fabricated directly in PostgreSQL with invented receipt IDs produces
`REVIEW_IDENTITY_AUTHORITY_RECEIPT_UNKNOWN`, stays `HOLD_FOR_PUBLICATION_REVIEW`, and counts zero
review events. A genuine two-reviewer local-authority chain replays after authority restart and
returns `ELIGIBLE_FOR_PROJECTION_REVALIDATION` without exposing actor, credential, receipt, secret
or MAC fields in the eligibility result. Focused reviewer/admin/control/eligibility/persistence
tests: **44/44 PASS**; `compileall` and scoped `git diff --check` PASS.

Canonical Finding record-version proof 2026-10-06: the private
`finding_record_version.py` store now supplies the current DP-310 `record_version` as
`finding-record-version-v1:<sha256>` directly from PostgreSQL. The public API of that store accepts
only a Finding ID; there is no caller-supplied fingerprint/material/version argument. Reopening the
store against the same database reproduces the same value, while current mutations to the Finding
rationale/assessment-publication envelope, policy/model/version references, verification input or
version/evidence set, `finding_evidence` edges, assertion text/relation/version binding, or citation
relation/bound hashes change the version and therefore cannot match an earlier DP-310 review event.
The existing deterministic `finding_id` remains the Finding's stable creation identity from
`finding_runtime`; `record_version` is the separate fingerprint of the current reviewed snapshot.

The producer owns the reviewed Finding snapshot and its direct persisted verification/evidence/
assertion/citation topology. It intentionally does not duplicate DP-308's proof of the referenced
objects: current source/transcript/person/context state, evidence content/freshness/suitability,
privacy, rights and challenge holds stay in the safety binding, while DP-309 risk/policy state stays
in the high-risk binding. `public_projection.py` now consumes this producer through the production
revalidation boundary and requires DP-310/311 eligibility before serialization. Focused disposable
PostgreSQL record-version proof remains **5/5 PASS**. The current focused publication boundary is
**139/139 PASS** across safety/eligibility/review/authority, projection/persisted tamper and
hold/revalidation tests. At that receipt stage AC-310.9 remained open for full-suite, DP-223 benchmark and MiniPC acceptance.

Final closure receipt at clean HEAD `5a86666b` (2026-10-06): AC-310.9 is satisfied by the clean
archived commit's **1720/1720** full suite, deterministic benchmark **5/5**, focused
DP-223/projection/citation **22/22**, isolated MiniPC M3 review/safety canary (**346 tests** +
benchmark **5/5**) and PostgreSQL rerun **69/69** with PostgreSQL 18 explicitly on PATH. Temporary
trees were deleted; no production DB/provider was used. All DP-310 engineering ACs are closed
without claiming legal correctness or any DP-307 disposition.

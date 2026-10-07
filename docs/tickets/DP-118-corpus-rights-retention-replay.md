# DP-118 — corpus rights retention replay

Status: DONE
Milestone: M1R — Research corpus and knowledge convergence
Depends on: DP-113; DP-304/305 policy inputs; retention runtime

## Problem

A large private corpus retains more third-party material than the current claim-first flow. Bodies, snapshots and archive receipts need explicit rights/retention classes and replay semantics before scaling collection.

## Outcome

Define and implement corpus body-retention, purge, archive-state and replay policies that preserve audit metadata/hashes while respecting rights/privacy decisions and never leak bodies into Public.

## Scope

- Classify capture metadata vs body/object bytes vs passage excerpts.
- Define retention status, purge-body behavior, archive requested/pending/succeeded/failed states and receipts.
- Preserve hash/provenance after an allowed body purge.
- Integrate source/rights holds and takedown/reanalysis hooks without deleting required audit history.
- Add private/public leak tests, secret scans and replay fixtures.

## Non-goals

- No legal conclusion beyond accepted DP-304/305/307 decisions.
- No public full-text corpus.
- No cookie/credential retention in corpus metadata.

## Dependencies and sequencing

DP-113; DP-304/305 policy inputs; retention runtime

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-118.1:** Purging body bytes leaves the required provenance/hash receipt without a dangling public reference.
- [x] **AC-118.2:** Archive failure is explicit and cannot appear succeeded.
- [x] **AC-118.3:** Rights hold blocks downstream use according to policy.
- [x] **AC-118.4:** Public bundle contains no raw capture body/private passage text.
- [x] **AC-118.5:** Replay from retained artifacts is deterministic where policy permits.

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

Retention/runtime + possible schema fields; policy-dependent rows remain BLOCKED rather than guessed.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `cfb64a5` (`feat: add corpus retention lifecycle`).

Implemented technical lifecycle only; **no legal retention period or rights conclusion was
invented**. `RETENTION_PERIODS_APPROVED` remains false and DP-304/305/306/307 remain the
legal/policy authority.

Delivered:
- additive capture lifecycle fields for hold/archive/purge state plus append-only
  `capture_lifecycle_event`;
- explicit archive states `NOT_REQUESTED -> REQUESTED -> PENDING -> SUCCEEDED/FAILED`;
  terminal states require non-empty receipts and failure never masquerades as success;
- body purge is allowed only for explicit `EPHEMERAL` captures with no active
  legal/rights/privacy/copyright/dispute hold; `POLICY_PENDING` remains non-purgeable;
- prepare -> verified filesystem delete -> finalize design, with replay-safe operation
  receipts; failed deletion quarantines instead of marking `PURGED_BODY`;
- local body purge is dry-run by default, requires a relative path inside the configured
  storage root, refuses symlinks/path escape, and verifies bytes against the persisted
  SHA-256 before deletion;
- successful purge preserves capture/hash/lifecycle provenance and clears only body
  reference/state as contracted;
- capture metadata/archive/purge receipts recursively reject explicit credential-bearing
  keys such as authorization/cookie/api_key/access_token/password/client_secret while
  allowing non-secret metrics such as token counts;
- `Passage.private_text` remains private and has no invented automatic retention period;
- backup/restore inventory includes lifecycle receipts; Public projection has no capture
  body/lifecycle/private-text read path.

Local proof:
- focused lifecycle/schema/retention tests PASS;
- full suite: **775/775 PASS**;
- deterministic benchmark: **5/5 PASS**;
- compileall and `git diff --check`: PASS;
- tempfile proof performed actual hash-verified delete and proved dry-run, hash mismatch,
  path traversal and symlink refusal.

MiniPC canary proof before production:
- isolated `dp118_canary` was built from the pre-DP-118 `fd00096` schema; migration and
  replay passed;
- lifecycle replay returned stable outcomes: HOLD_SET, HOLD_RELEASED, ARCHIVE_REQUESTED,
  PENDING, FAILED, PURGE_READY and PURGED;
- a hold blocked purge; archive failure retained its failure receipt; final purge state was
  `PURGED_BODY` with `body_ref=null` while the original SHA-256 remained intact;
- eight lifecycle events were inspectable and the schema was then fully dropped.

Production MiniPC proof:
- source/migration hashes matched Mac source;
- pre-rollout backup `20260929T090947Z`, readable dump 10,035,899 bytes;
- migration applied with `ON_ERROR_STOP` and replayed idempotently; legacy state remained
  49 Content / 30 Atomic Claims / 9 Findings / 2 PUBLISH;
- production canary deliberately did **not** fake a body deletion: copyright hold blocked
  purge; archive moved REQUESTED -> PENDING -> FAILED with explicit canary receipt; purge
  preparation then an expected no-body failure produced `BODY_PURGE_FAILED` and
  `QUARANTINED`, never `PURGED_BODY`; all canary rows were removed and read back at zero;
- post-rollout backup `20260929T091040Z`, readable dump 10,040,985 bytes, manifest includes
  `content_capture` and `capture_lifecycle_event`;
- MiniPC full suite: **775/775 PASS**; benchmark **5/5 PASS**; final production counts still
  49 Content / 30 Atomic Claims / 9 Findings / 2 PUBLISH / 0 captures / 0 lifecycle events.

Residual legal/policy blockers are intentionally unchanged. This ticket proves safe
engineering behavior under unresolved periods/rights; it does not close DP-304/305/306/307.
### 2026-09-29 backup rotation regression follow-up

During the later DP-115 rollout, the backup rotation path exposed a defect not exercised by
the original DP-118 receipt: when more than KEEP valid sets existed, the loop retained the
oldest sets and removed the newest one, then could still emit a false `BACKUP OK`. This was
fixed in commit `eb731b6`. The corrected script deletes the oldest excess sets, protects the
current set, handles same-second directory collisions, validates KEEP, and fail-closes if
the current dump disappears or becomes unreadable after rotation. Dedicated local and
MiniPC tests cover the regression. A real replacement backup `20260929T094221Z` survived
rotation and remained readable. This follow-up strengthens DP-118/DP-502 operational proof;
it does not change the capture-retention policy semantics above.

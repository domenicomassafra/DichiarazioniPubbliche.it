# DP-311 — Local reviewer identity authority and attested review receipts

Status: DONE
Milestone: M3 — Editorial, correction, privacy, and legal policy
Depends on: DP-310; coordinate with DP-303 and DP-507

## Problem

DP-310 correctly refuses to treat the review database or its hash chain as reviewer
identity authority. The current local review CLI still accepts an arbitrary `--actor` string,
and the new durable review ledger deliberately requires an external
`ReviewerIdentityAuthority`. DP-507 does not fill this gap: it is reserved for a future
remotely reachable admin HTTP surface and must remain `FUTURE` while review stays local.

Without a concrete local authority, durable actor separation cannot be replayed honestly and
a privileged database writer could fabricate an internally coherent review history.

## Outcome

Provide a local/operator-only v1 identity authority outside PostgreSQL. Reviewer credentials
are private files controlled independently from the database; signed/MACed opaque receipts
bind one concrete reviewer credential to one exact DP-310 review event. PostgreSQL stores
only the receipt identifier/binding already defined by DP-310. No secret, private credential
material, or reviewer personal data becomes public output.

## Scope

- Use separate high-entropy reviewer credentials stored outside the repository and database.
- Derive an opaque credential fingerprint from credential material; callers cannot supply an
  arbitrary fingerprint or actor and have it accepted.
- Bind each authority receipt to actor, credential fingerprint, exact review-event integrity
  hash, record ID/version, policy version, authority/key version and issuance time.
- Verification must work after process restart from the configured private authority store.
- Unknown, revoked, malformed, permission-unsafe, copied or tampered credentials/receipts fail
  closed.
- Rotation may retain verification-only material for historical receipts while preventing a
  revoked credential from issuing new approvals.
- Keep this local-only. Any remote/admin HTTP exposure still activates DP-507 first.

## Non-goals

- No web accounts, sessions, OAuth, CSRF mechanism, or remote admin endpoint.
- No claim that filesystem/root compromise can be solved by an application-level receipt.
- No reviewer name/email disclosure on public surfaces.
- No weakening of DP-310 dual control or DP-303 appeal separation.

## Acceptance criteria

- [x] **AC-311.1:** An authority-backed reviewer credential resolves actor identity and
  credential fingerprint; caller-supplied actor/fingerprint mismatches are rejected.
- [x] **AC-311.2:** An issued receipt is cryptographically bound to the exact DP-310 event,
  reviewed object/version and policy version and verifies after authority restart.
- [x] **AC-311.3:** Credential/receipt secrets are absent from PostgreSQL, logs, public
  projection, API, HTML, JSON-LD, RDF and search artifacts.
- [x] **AC-311.4:** Unknown, revoked, permission-unsafe, copied or tampered authority material
  fails closed and cannot satisfy DP-310 replay.
- [x] **AC-311.5:** Two-reviewer HIGH/LEGAL proof requires two distinct authority-backed
  credential fingerprints; a duplicate credential cannot satisfy separation under two actor
  labels.
- [x] **AC-311.6:** Local review tooling can create/use an authority receipt without accepting
  a free-form identity as publication authority; no remote surface is introduced.
- [x] **AC-311.7:** DP-310 durable replay and DP-303 reviewer-separation paths consume the same
  verified local identity semantics without rewriting historical events.
- [x] **AC-311.8:** Full suite and an isolated MiniPC restart/tamper/revocation canary pass.

## Validation / proof

Use only temporary high-entropy synthetic credentials in tests. Exercise issue -> persist ->
restart -> resolve/replay, copied receipt, altered event, duplicate credential under another
actor, revocation, unsafe file permissions and database-only fabrication. MiniPC proof must use
an isolated private `/tmp` authority directory and disposable PostgreSQL where persistence is
required; it must not read or modify production reviewer credentials.

## Documentation, security, and migration impact

The authority store is private operational state and must be documented in the operator
runbook/backup policy before production use. It is intentionally separate from DP-507. No
public-schema field or database secret column is permitted. If the implementation needs new
database state beyond DP-310's opaque receipt ID/binding, that state must be additive and
must not become the trust root.

## Local implementation receipt — 2026-10-06

`reviewer_identity_authority.py` implements a local/off-DB HMAC authority backed by a private
filesystem root. Reviewer credentials use distinct 256-bit secrets and derive opaque SHA-256
credential fingerprints. The authority requires private file modes, rejects the same
fingerprint under different actors, refuses caller/event actor or fingerprint mismatch, and
will not sign a DP-310 event whose canonical event ID/integrity digest is invalid.

Receipt HMAC plus the existing DP-310 identity-attestation binding covers the exact event
integrity digest, reviewed record/version, policy version, actor/fingerprint, authority/key
version and issuance time. Tampered/copied receipts, unsafe permissions and unknown material
fail closed. Revocation blocks new issuance while retained key material can verify historical
receipts after restart.

`reviewer_identity_admin.py` adds local-only `provision`, `show`, `revoke`, `attest-event` and
`resolve` commands. `attest-event` has no free-form actor/fingerprint authority option and
introduces no HTTP listener, account or session surface, so DP-507 remains `FUTURE`.

Disposable PostgreSQL proof uses the concrete file authority with two distinct reviewers:
issue -> append -> revoke one credential -> construct a new authority instance -> replay ->
DP-310 dual control remains satisfied from exact historical receipts. The public internal
guard also rejects authority receipt/binding, receipt MAC and secret-key material across the
existing public serializers. Focused authority + DP-310 persistence/control/composition tests
are green.

## AC-311.8 MiniPC acceptance — 2026-10-06

The isolated acceptance ran on MiniPC host `udodo` (`Linux 7.0.0-27-generic`, `x86_64`) with
Python `3.14.4` and PostgreSQL server/client `18.6`. All canary state lived under
`/tmp/dp311-ac8-w11`; the authority and PostgreSQL cluster/database were synthetic and
disposable. The canary process ran under a scrubbed environment containing only `HOME`, `LANG`,
`LC_ALL`, `PATH`, and `PYTHONPATH`; no production database, reviewer-authority, provider, or
application environment variable was present.

The private authority root was mode `0700` and contained exactly two synthetic reviewer
credentials and two HMAC-backed receipts. The initial durable ledger contained exactly two
valid review events. A fresh Python process constructed a new authority instance and persistence
store, replayed exactly those two distinct reviewer identities/credential fingerprints, and
reached `ELIGIBLE_FOR_PROJECTION_REVALIDATION`. The canary then proved fail-closed behavior for
receipt tamper, event tamper, copied receipt use against a different valid event, duplicate secret
material under another actor, revoked credential issuance, unsafe credential permissions, unsafe
authority-root permissions, and a hash-valid database-only fabricated two-reviewer history with
unknown authority receipts. Historical receipts remained verifiable after revocation.

The operator backup/recovery requirement is also exercised rather than documented only: the
synthetic authority root was copied to a separate private backup directory, the active authority
root was removed, the backup was restored into a fresh `0700` root, and another fresh Python
process successfully verified the historical receipts and replayed the same two-reviewer chain
from the disposable PostgreSQL ledger. Actual synthetic credential secrets were absent from the
durable database rows. This matches the already documented operator procedure in
`docs/ops/operator-runbook.md` and backup boundary in
`docs/18-storage-retention-and-open-data.md`; no vendor-specific secret store is asserted.

MiniPC focused authority/admin/control/eligibility/persistence/DP-303 policy validation:
**80/80 PASS**. Local full Python suite: **1632/1632 PASS** in `32.669s`, including the repository
restore drill with `publication_review_event_durable` restored exactly. Local focused validation,
`compileall`, and scoped `git diff --check` also pass. After acceptance, the disposable MiniPC
PostgreSQL process and `/tmp/dp311-ac8-w11` tree are removed, as are the local `/tmp` canary
bundle/scripts. No production reviewer credential, production database/config, provider, remote
auth surface, public projection/schema/API, or web state is read or modified by this acceptance.

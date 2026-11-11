# DP-413B — persistent autonomous runner (private)

Issue: [#464](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/464).
The production seam is `PersistentRunner.run(record_id, now=..., provider_revision=...)`.
It reuses `AutonomousOperations` and **requires** trusted capture,
challenge, public surface and one authenticated editorial review adapter.
Records with documented uncertainty require a second independent reviewer
and a third auditor; the nightly sample always requires its independent auditor.
It does not accept an operator-supplied JSON packet as publication authority.

## Storage and retry

`SQLiteRunJournal(path)` uses a private 0600 SQLite database, an exclusive
cross-process lock and append-only hash-linked run events. Agent completion
receipts preserve the actual OmniRoute request ID, returned model, model/prompt
policy versions, source snapshot SHA, statement SHA and rights-attestation SHA.
A completed run is skipped across restarts only while the input fingerprint,
challenge status, reviewer identities/model IDs and public readback agree.
An incomplete run is retried. Supply `provider_revision` from authenticated
route/account/quota state; changing the revision triggers a HOLD retry after
restored provider availability. The caller must schedule the run when source,
challenge or provider admission inputs change.

Before applying a public PUBLISH decision, `AutonomousOperations` also requires
`verify_provider_execution(review)` for **every review actually required** by
decision 49 and for the independent nightly auditor. Each reviewed completion
must carry a unique provider request
ID, an allowed exact returned model, prompt digest and token usage; missing
or rejected witness yields HOLD and immediate withdrawal. The verifier must
read independent, authenticated OmniRoute request history and enforce the
DP-scoped key, Pro account, remaining upstream quota, route and non-billed
usage. An HTTP response or the same journal's checksum is not such a witness.
The offline tests provide an explicit simulated witness; those passes do not
authorize publication.

The runner reuses a stored `PUBLISH` checkpoint only when its optional
`current_verified_packet(record_id, version_id)` returns a freshly verified
`AutonomousProofPacket` for the current candidate. Wire the existing
`JournalReviewPacketReader` here, with an independently authenticated
provider witness; unchanged source/hash/visibility alone cannot replay a
publication. Without this reader the runner rechecks the decision and withdraws
on missing witness. The checkpoint fingerprint includes the witness-policy
version, so earlier unauthenticated PUBLISH results are not reused.

## Provider admission and identity

`OmniRouteAgentReview(model_id=...)` makes one constrained completion for
an exact allowlisted Gemini 3.8 Flash tiered, 3 Flash or 2.5 Pro model at
the **local** OmniRoute gateway. Its required model-aware
`subscription_gate(model_id)` must independently verify the DP key's
currently authorized and independently verified Antigravity Pro account IDs,
route allowlist, remaining quota and no paid-route fallback before *each* POST.
If no such authenticated
capability exists, the review fails and `AutonomousOperations` records HOLD.
A gateway model substitution, missing provider completion ID, duplicate ID,
missing usage or unacceptable source/rights citations also prevents approval.
Never set the gate to an unverified constant in production.

The review adapter sends a unique \`X-OmniRoute-Session-Id\` for each completion
and persists the tag with the provider response ID. The read-only
\`OmniRouteExecutionAuthority\` validates journal receipts against independently
authenticated OmniRoute management \`/api/keys\`,
\`/api/usage/call-logs\` (including stored request and response bodies), and
\`/api/usage/route-explain\`. It requires one matching session, the DP key's
restricted models and connections, an exact request digest, actual response
ID/verdict/usage, the direct selected route and authenticated attribution of
nearby fallback entries. Unreadable, incomplete or ambiguous management
history is HOLD. Provide a separate management credential and an eligible
connection allowlist obtained from the upstream subscription authority; never
use a credential embedded in a publication record.

This witness verifies an **execution**, not the Google subscription entitlement,
remaining upstream quota, non-billing or legal rights. The quota gate stays
mandatory and closed until those provider facts are independently attested.
On MiniPC (11 November), \`omniroute quota status --json\` reported
\`quotaMonitoring.status=unknown\`, \`authoritative=0\`, \`configured=0\`,
\`pools.count=0\`; the read-only \`/api/usage/quota\` had 31 Antigravity
connections with no reported quota total, and no DP-named scoped key was
present. These observations permit no provider POST or publication.

## Durable review readback for Statement v3

`JournalReviewPacketReader` in `autonomous_review_reader.py` reconstructs
an `AutonomousProofPacket` from one witnessed editorial receipt for ordinary
records, or two distinct-agent receipts plus the third auditor for explicit
uncertainty, previously persisted by `OmniRouteAgentReview`. Bind it as the callable
`read_current_autonomous_evidence` on `SenatoPublicV3Source`, supplying a
separate authenticated `read_current_candidate(statement_id, version_id)`
that rechecks the exact Capture, rights and identity before and after the
journal read. Supply `verify_provider_execution(receipt)` from a **separate
authenticated OmniRoute execution authority** that verifies the real request
ID, DP key/connection scope, paid-route exclusion, model, response, prompt and
evidence binding and actual usage. The journal alone is self-asserted storage:
direct `append_review` calls can fabricate complete-looking receipts. Without
this independent witness, the reader always returns no packet, even if two
rows have valid hashes and metadata. A hardcoded `True` is not a production
execution witness. The reader also requires current source/quote/rights hashes, policy and
prompt versions, model-response identity, per-stage citations and real
gateway completion IDs, and rejects ambiguous or tampered receipts.

This is an available **fail-closed reader component**, not a wired production
caller or an implementation of the authenticated OmniRoute execution authority.
It cannot authenticate an owner-defined DP key, create upstream completions,
approve privacy, clear a challenge or issue a release pin. The journal's
private write authority must be limited to the genuine OmniRoute adapter;
test fixtures are not release evidence. A missing upstream service yields
no packet and therefore HOLD.

## Dependencies before activation

- [#458](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/458)
  supplies the authentic, original-source packet and its independent rights
  authority. It was OPEN when this tranche was authored.
- The 2 November 2026 read-only inventory listed 3.8 Flash tiered, 3 Flash
  and 2.5 Pro on 13/13 active Google AI Pro connections. The original 3.7
  Flash and 3.1 Pro IDs appeared on 0/13. The 3 November policy reconciliation
  selects the three available IDs and revokes old model receipts. The owner
  authorized all legitimately available Google AI Pro connections on 2 November,
  subject to independent entitlement verification. No DP-scoped
  `allowedConnections` key, authoritative quota or verified upstream execution
  witness has yet been demonstrated. An allowlist/test fixture is **not** a
  live editorial review or escalation/audit; HOLD until subscription, quota and
  no-fallback proofs exist.
- The existing MiniPC public consumer is on v2. Bind these adapters to its
  separately authenticated DB/readback and withdrawal controls, and install
  through the candidate/verify/swap/rollback runbook after independent review.
  Do not publish a v3 candidate before the real readback and cache-fence prove
  every served surface has the same approved version.

## Focused checks

```sh
python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- uv run --no-project --with pytest --with pyyaml python -m pytest -q tests/test_dp413b_persistent_runner.py tests/test_dp413b_agent_review.py
```

The gateway fixtures exercise parsing and identity contracts. They are **not**
two actual model executions and do not satisfy #464's live acceptance.
Run `tests.test_dp413_persisted_review_reader` for receipt-replay and
revocation regressions before connecting a real candidate source.

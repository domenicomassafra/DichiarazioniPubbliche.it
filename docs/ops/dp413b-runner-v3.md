# DP-413B — persistent autonomous runner (private)

Issue: [#464](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/464).
The production seam is `PersistentRunner.run(record_id, now=..., provider_revision=...)`.
It reuses `AutonomousOperations` and **requires** trusted capture,
challenge, public surface, and two independent provider-review adapters.
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

## Provider admission and identity

`OmniRouteAgentReview(model_id=...)` makes one constrained completion for
an exact owner-allowlisted Gemini 3.8 Flash, 3.7 Flash or 3.1 Pro model at
the **local** OmniRoute gateway. Its required model-aware
`subscription_gate(model_id)` must independently verify the DP key's
12 authorized Antigravity Pro account IDs, the particular model's entitlement,
route allowlist, remaining quota and no paid-route fallback before *each* POST.
If no such authenticated
capability exists, the review fails and `AutonomousOperations` records HOLD.
A gateway model substitution, missing provider completion ID, duplicate ID,
missing usage or unacceptable source/rights citations also prevents approval.
Never set the gate to an unverified constant in production.

## Durable review readback for Statement v3

`JournalReviewPacketReader` in `autonomous_review_reader.py` reconstructs
an `AutonomousProofPacket` only from two exact-model, distinct-agent receipts
previously persisted by `OmniRouteAgentReview`. Bind it as the callable
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
- The owner approved three distinct models on 31 October 2026 and, on
  1 November, authorized all 13 then-configured Google AI Pro connections,
  subject to verifying each account's legitimate subscription. The prior
  read-only gateway metadata listed 3.8 Flash on 13/13 connections, 3.7 Flash
  on 0/13 and 3.1 Pro on 0/13. No DP-scoped `allowedConnections` key or
  ownership/entitlement proof for all 13 is yet demonstrated.
  Thus an allowlist/test fixture is **not** a live two-model review or third
  audit; HOLD until subscribed provider, quota and no-fallback proofs exist.
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

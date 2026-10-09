# DP-417 private Discovery triage — operator acceptance boundaries

This is **source-only**, not deployed. The new table is not present in the
MiniPC production schema. Do not point the CLI at live PostgreSQL unless
the additive migration, backups, reviewer governance and rollback procedure
are separately approved and verified. No public or remote write endpoint
exists.

## Local credential and exact annotation

The CLI only accepts three non-authoritative states: `NEEDS_REVIEW`,
`DEFERRED`, `REJECTED`. `REJECTED` is an annotation **not** the actual
rejection/disposition of a Discovery Hit, source or claim. It neither
promotes nor publishes anything. A Collection-scoped provenance record
must exist and the request must supply the current expected revision,
starting at zero.

Provision a private reviewer credential via the existing local credential
administration instructions. The root is owned by the operator and mode
0700, its credential files mode 0600; credentials live **outside Git**.
Do not pass HMAC secrets in arguments, environment dumps or logs.

After the migration is approved in an isolated DB, an operator can invoke:

```sh
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.studio_discovery_triage_store \
  --collection-id research:fixture --hit-id hit:fixture \
  --request-key operator-generated-unique-id --decision NEEDS_REVIEW \
  --expected-revision 0 --actor-ref reviewer:example \
  --authority-root "$HOME/.config/dichiarazioni-pubbliche/reviewer-authority" \
  --credential-id example-reviewer --confirm-private-annotation
```

The CLI uses PostgreSQL connection settings already authorized for the
invoking operator, signs the exact request under `DP417_TRIAGE_V1` to a
no-replacement, owner-only `triage-receipts/` file, verifies current
credential status, then attempts one CAS transaction. The response
distinguishes `CREATED`, `REPLAY`, `IDEMPOTENCY_CONFLICT`,
`REVISION_CONFLICT`, and `SCOPE_NOT_FOUND`. Conflicting or wrong-scope
requests are not applied. A revoked credential cannot issue or verify new
attestations. A verified credential alone is not source-rights or reviewer
policy authority, and replay does not re-authorize any downstream action.

## Read-only inspection

`/v1/discovery/triage-history` needs an authenticated local Studio bearer
token and exact Collection + Hit ID. Optional `limit` is 1–30 and
`after_revision` is a nonnegative integer. Returns safe revision/decision
rows and explicit blockers, excluding operator identifiers, URLs, source
bodies, queries and raw metadata. There is **no** corresponding HTTP POST
write route, and local API DB sessions are forced read-only. The operator
CLI is separate from the Studio listener.

## Residual release gates

Before treating this as an operational review workflow, verify governance
for reviewer identity, denial/appeal and signed decisions, current rights,
genuine Discovery Hits, safe state machine and bulk transitions, migration
read-back, and protected backup/restore on real deployed data. The local
privacy inventory labels all nine persisted ledger fields
`OPERATIONAL_PRIVATE` and denies direct public projection. Neither this
runbook nor a passing canary marks DP-417 complete.

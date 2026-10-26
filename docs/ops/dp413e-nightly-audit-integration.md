# DP-413E — nightly audit integration contract

The v3 policy in `autonomous_operations.py` selects 10% of the **currently
published, version-bound** records per UTC audit day, rounding upward for a
nonempty corpus. An empty eligible corpus produces zero selections. The
`NightlyAuditCoordinator` freezes the denominator and selection in
`autonomous_nightly_audit_run`, writes every `AUDIT_PASS`/`AUDIT_HOLD` with the
source-version, rights and third-review metadata, and completes the run only
after durable readback. A retry uses the original manifest and processes only
missing sample members. It must run with an exclusive scheduler/DB lease; the
immutable per-day keys make outcomes idempotent but do not serialize external
public-surface mutations.

## Production binding required from #464 and authentic packet from #458

Provide the coordinator with trusted PostgreSQL-backed adapters for the
operational `RunReceipt` journal, the correction authority, immutable current
packets, capture, challenge, both original independent model reviewers, public
surface publication/withdrawal/readback, and the third independent reviewer.
The adapters must verify upstream execution identity, original media/content
and current source-use authorization; stored JSON or self-declared hashes are
not an independent authority. The model/agent identities must meet the existing
v3 policy, using only authorized OmniRoute routes. A changed or revoked review
fails closed and must remove public eligibility across all served surfaces.

Do not enable the nightly timer without these adapters. Neither #464 nor #458
had shipped a real eligible publication on 2026-10-26, so a real third-model
night run and its natural UTC nightly execution cannot yet be shown. Never
promote a private `content_publication_candidate` to a published record merely
to increase the denominator.

Once the upstream runner is ready, schedule one UTC-nightly oneshot job with
`Persistent=true` and retry failures after a bounded delay. The job must call
`NightlyAuditCoordinator(PgNightlyAuditLedger(PsqlRuntime(...))).run(...)`
using a durably loaded current journal and correction ledger, with a protected
single-instance lock. Do not supply synthetic receipts to the live coordinator.

Apply `db/migrations/20261026-add-autonomous-nightly-audit.sql` before updating
the consumer's `deploy/ops/backup.sh` table inventory, otherwise the automatic
backup preflight correctly detects schema drift and refuses incomplete dumps.
After a natural run, verify the private readback with:

```sh
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.nightly_audit_pg
```

The command reports immutable run IDs, exact UTC timestamps, the sample and
denominator, HOLD/PASS results, reviewer IDs and rights/source/version evidence,
plus daily published/HOLD/correction metrics. `NO_RUN` and `INCOMPLETE` return
nonzero and must never be presented as audit success. Review the deployed
consumer and the distinct public-surface withdrawal authority before closure.

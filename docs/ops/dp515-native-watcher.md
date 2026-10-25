# DP-515 native single-source watcher

The existing user systemd source-poll unit now runs the PostgreSQL-backed
native_source_watch module. Its timer runs once per six hours. The separate
daily full-source unit belongs to the older ingestion pipeline and is untouched.

## Scope

The only permitted source is source:senato-akn-leg19-01457617, pinned to the
Senato BulkData commit bfac144eb5c54820971bc1020fece11aae56ec90.
The bootstrap command looks up the existing Content and exact current,
unexpired, unsuperseded FETCH right from private_source_rights_record.
It inserts only one dp515_watch_source, and creates no new rights,
Collection, provider, approval or monetary records.

The readiness references native:https-bounded-no-provider and
subscription:no-paid-provider. These describe the HTTPS-only route and the
owner decision of 25 October 2026: the quota of subscribed accounts limits
model work, and this watcher has no model/provider dispatch path.

Each admitted poll performs one redirect-free HTTPS GET, an 8-second HTTP
timeout and a 512 KiB body limit. Only SHA-256, conditional headers,
readiness and observation metadata are persisted; no body or public data is
stored. The 300-second lease, CAS/rights epoch, single-source timer and
backoff control concurrency, frequency and replay. A changed response
creates at most one SOURCE_REVALIDATION_REVIEW job, always BLOCKED. An
unchanged 200/304, denial, conflict or revocation creates no job.

## MiniPC promotion and rollback

Stage the native runner, PostgreSQL adapter, current incremental watcher,
SQL migration, source-poll service and timer on the MiniPC; compare all
SHA-256 against main. Back up the original two systemd units and the
earlier incremental watcher, and take
a native pg_dump before applying the additive migration via psql
--single-transaction -v ON_ERROR_STOP=1. Never change other queue jobs,
sources, rights records, service timers, or the public projection.

Stop only the source-poll timer and confirm its service inactive, promote the
six staged files, use the existing service environment to invoke the native
watcher with --bootstrap once, then systemctl --user daemon-reload and start
a controlled one-shot canary. Read back dp515_watch_source,
dp515_watch_attempt and processing_job before/after, including each job
state. Start the timer after verification, and check the active ExecStart
and timer. The other timers continue independently.

For rollback, stop that same timer, restore only its saved service, timer
and previous runtime file, reload the daemon and start the timer again.
Read back the original ExecStart and service health. Keep the additive
PostgreSQL watcher tables and BLOCKED review ledger intact for provenance;
they cannot dispatch by themselves. Do not drop a production table or row
to force a rollback. The private schema dump remains available for diagnosis.

For a revocation canary, insert a temporary superseding right inside an
explicit transaction, check admission is denied and job state/count stays
unchanged, and ROLLBACK. This does not grant or revoke the actual current
permission and is distinct from a permanent rights decision.

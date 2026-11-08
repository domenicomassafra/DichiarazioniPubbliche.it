# DP-413 — unattended tick over the autonomous authorities

Issue: [#413](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/413).
`autonomous_pipeline.AutonomousPipeline.run()` is the composition a scheduler
calls: it enumerates the private records that must be re-evaluated, runs the
existing persistent runner per record, runs the nightly third audit at most
once per UTC day and reports the day's counts. It grants no authority of its
own: capture, challenge, both independent reviewers, the public surface, the
third auditor, the provider-execution witness and the correction ledger stay
separate and fail closed.

## One tick

```python
pipeline = AutonomousPipeline(
    operations=operations,              # AutonomousOperations with its own witness
    runner=runner,                      # PersistentRunner over the same journal
    queue=record_queue,                 # current_record_ids() -> tuple[str, ...]
    corrections=correction_ledger,      # () -> tuple[CorrectionMetricEvent, ...]
    limit=25,                           # bounded provider spend per tick
    audit_ledger=nightly_ledger,        # optional, all three or none
    packet_authority=persisted_packets,
    third=third_reviewer,
)
report = pipeline.run(now=instant, provider_revision=..., audit_day=instant.date())
```

`TickReport.status` is `TICK_OK`, `RECORD_RUN_FAILED`, `QUEUE_UNAVAILABLE`, `QUEUE_INVALID`,
`AUDIT_UNAVAILABLE`, `AUDIT_REJECTED`, `AUDIT_FAILED`, `METRICS_UNAVAILABLE` or
`METRICS_INVALID`; `reason_codes` names each cause, `runs` holds the durable
per-record receipts, `deferred` lists the records beyond `limit`, and `failed`
lists records whose run raised (for example an unconfirmed withdrawal). A
failed or deferred record never hides the others, and an unavailable queue
produces no model work.

`metrics` is `daily_metrics(journal.all_events(), ...)`. An unavailable
correction ledger leaves `metrics` empty instead of reporting a fabricated
zero, and an unconfigured or failing audit leaves `audit` as `None` with the
matching status. Nothing in a tick authorizes publication: a record is public
only because the existing policy, witnesses and surface readback said so.

`SQLiteRunJournal.all_events()` returns the whole corpus in append order after
validating the hash chain, which is what the nightly denominator, the frozen
sample and the daily counts need; `events(record_id)` keeps its per-record
view.

## Dependencies before activation

Wire only authenticated authorities: the persisted candidate/rights reader,
the challenge ledger, the two `OmniRouteAgentReview` adapters with their
model-aware subscription gate, the runtime's own separate
`verify_provider_execution`, the public publish/withdraw/readback surface and
the third auditor. A local journal, a fixture witness or a hardcoded `True` is
not production evidence; without them the tick reports HOLD and publishes
nothing. The DP key scope, authoritative quota and three upstream execution
witnesses from ControlCenter
[#1496](https://github.com/domenicomassafra/ControlCenter/issues/1496), source
rights from
[#468](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/468)
and the public v3 consumer from
[#98](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/98)
are still required before any real record is published.

## Focused checks

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest \
  tests.test_dp413_pipeline tests.test_dp413b_persistent_runner \
  tests.test_dp413_nightly_audit tests.test_autonomous_operations -v
```

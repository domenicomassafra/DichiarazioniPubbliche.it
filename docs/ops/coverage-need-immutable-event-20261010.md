# DP-213 / DP-214 dependency: Coverage Need event atomicity

Date: 2026-10-10. Source: isolated disposable PostgreSQL, actual
\`ClaimEvidenceObservationStore\` SQL; MiniPC read-only inventory.
No acquisition, provider call, public projection, migration or prod write.

## Real failure reproduced before repair

Three independent PostgreSQL RED fixtures showed the same failure:

- \`record_coverage_need_attempt\` incremented attempt_count despite
  collision with an existing \`coverage_need_event.id\` belonging to
  another need; a same-ID retry could consume the next attempt as well.
- \`satisfy_coverage_need\` closed an OPEN need as SATISFIED even when
  no matching event could be appended.
- \`block_coverage_need\` closed an OPEN need as BLOCKED with no
  corresponding event when its event ID was already taken.

This made the DP-213 discovery/research retry ledger untrustworthy:
research might stop or appear complete without a historical event.

## Atomic source fix

All three SQL writers now lock the exact current need, attempt the
immutable \`coverage_need_event\` insert **first** and mutate status,
attempt count, evidence links and any associated source-assessment
metadata only when the event insert returns the new event ID.

The insert and update are part of one PostgreSQL statement. An invalid
status constraint or other failure rolls back both effects. Global
event-ID collisions leave the need unchanged. A same-ID retry cannot
spend budget twice; legitimate first attempts, explicit satisfied
evidence and blocking decisions are still persisted and idempotent.

## Verification

\`tests/test_coverage_need_event_collision_postgres.py\` executes the
real runtime store against the canonical \`coverage_need\` and
\`coverage_need_event\` PostgreSQL DDL on an isolated local cluster.
Initially four RED cases; after repair six GREEN cases cover collision
fences, valid attempts/satisfaction/blocking and exact replay.
The existing private original-source preflight remains in place.

Authoritative MiniPC PostgreSQL read-only aggregates today: zero
Coverage Need rows, zero events, zero SATISFIED and zero BLOCKED; no
production data was modified or retroactively invented. The production
mirror has not received this source patch as part of this work.

This addresses event correctness, not actual coverage: DP-214 remains
18/100 Garlasco contents with required source rights and real
Discovery/Capture still absent.

## Additional root cause closed: creation and assessment refresh

The initial collision audit also identified two related paths in
\`upsert_coverage_need\`: creating a new OPEN Coverage Need or refreshing
its associated source-intelligence assessment was permitted even if
\`ON CONFLICT DO NOTHING\` had swallowed the corresponding
\`CREATED\` / \`OBSERVED_AGAIN\` receipt.

Two additional real PostgreSQL RED cases were added. Both event inserts
now **fail the SQL statement on a conflicting event ID**, which rolls
back the newly created need or the assessment refresh atomically.
Existing exact upsert replays still return EXISTING because no new
event is needed. Healthy creation and the first actual assessment
refresh still produce their own receipts.

Coverage Need proof now covers **9/9** real database cases across
CREATED, OBSERVED_AGAIN, SEARCH_ATTEMPT, SATISFIED and BLOCKED events.
The absence of any durable Garlasco Coverage Need on the MiniPC remains
a separate real-data/corpus blocker.

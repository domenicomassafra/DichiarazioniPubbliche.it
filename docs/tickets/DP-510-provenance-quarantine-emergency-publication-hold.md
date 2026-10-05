# DP-510 — Provenance quarantine and emergency publication hold

Status: FUTURE  
Milestone: M5 — Reliability, security, operations, and data lifecycle  
Depends on: DP-308; coordinate with DP-501, DP-504, DP-505, DP-431

## Problem

If a bug is discovered in one transcript provider, source adapter, attribution method,
Capture, Person mapping or policy version, waiting for each individual record to be manually
corrected can leave known-unsafe public output online. The system needs a targeted emergency
hold that stops affected projection without destroying provenance or broadening operator
authority into arbitrary deletion.

## Outcome

Implement an append-only, auditable quarantine/hold mechanism that can invalidate public
eligibility by precise dependency scope and regenerate the public projection fail closed.

## Scope

- Support bounded hold targets such as Source/source profile, Content/Capture, transcript
  variant, canonical segment range, speaker-attribution method/version, Person-resolution
  decision, evidence source/requirement profile, policy version, Finding or explicit set of
  record IDs.
- Every hold records actor, reason code, scope, start time, policy/incident ID and review
  state; free-form notes remain private.
- Projection-time DP-308 evaluation checks active holds and omits affected records.
- Dependency traversal must be deterministic and bounded; a hold may quarantine affected
  dependents but cannot silently delete/mutate them.
- Release requires an explicit reviewed unhold/revalidation event, not expiry-by-forgetting.
- Provide dry-run impact preview: number/IDs of affected public records/artifacts before
  activation where operationally possible.
- Integrate alert/digest/runbook semantics through DP-505 and propagation through DP-431.

## Non-goals

- No arbitrary censorship/edit button or unlogged deletion.
- No automatic legal takedown decision; DP-303/DP-306/DP-307 own legal/policy authority.
- No global site shutdown as the only control when a narrow dependency hold is sufficient.
- No overwriting historical evidence to remove an embarrassing error.

## Acceptance criteria

- [ ] **AC-510.1:** An active hold on a load-bearing dependency makes every affected public
  record non-projectable on regeneration while preserving private history.
- [ ] **AC-510.2:** A hold on one source/provider/version does not suppress unrelated
  records whose dependency graph does not include it.
- [ ] **AC-510.3:** Hold scope/impact is inspectable and replayable; direct status edits do
  not substitute for the required event.
- [ ] **AC-510.4:** Release/unhold requires explicit revalidation against current source,
  provenance, policy and review versions.
- [ ] **AC-510.5:** Stale public files/index entries are cleaned through DP-431; partial
  cleanup failure leaves the affected surface fail-closed and alerts the operator.
- [ ] **AC-510.6:** Emergency hold/unhold operations never delete Capture, transcript,
  evidence, review or correction history.
- [ ] **AC-510.7:** A dry-run/impact receipt can identify the bounded affected public set
  before activation for test/canary cases.
- [ ] **AC-510.8:** Security regression proves an unauthorized/public caller cannot create
  or clear holds.
- [ ] **AC-510.9:** MiniPC incident canary proves hold -> projection omission -> reviewed
  revalidation -> safe restore with exact before/after fingerprints.

## Validation / proof

Exercise holds for source family, transcript variant, speaker method, person mapping and
single Finding; verify unaffected records. Include unauthorized/tampered events and failed
projection cleanup. Run standard checks, security matrix and MiniPC canary.

## Documentation, data, and migration impact

Likely additive append-only hold/event persistence plus operator CLI/runbook. Do not expose
private reason bodies publicly. Update incident/recovery docs and DP-704 rehearsal matrix.

## Completion receipt

Pending DP-308 and implementation.


# DP-417 — studio discovery inbox

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-209, DP-212, DP-414

## Problem

Newly discovered material needs triage. Without an Inbox, automation either stops at logs or silently makes decisions that should be reviewable.

## Outcome

Implement persisted triage queues for new content, duplicate/existing hits, changed captures, unresolved entities, statement candidates, already-covered claim candidates, Coverage Needs and blocked/quarantined items.

## Scope

- Queues derive from database state/query contracts rather than copied counters.
- Row actions: inspect, link/merge candidate, reject, add to collection, extract, promote when eligible, open/target Coverage Need.
- Bulk actions only where semantics are safely identical and reversible.
- Show provider/rights/budget blocks with stable reason codes.

## Non-goals

- No inbox-zero gamification.
- No mass approval of identity/claims from one similarity threshold.
- No automatic publication button.

## Dependencies and sequencing

DP-209, DP-212, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-417.1:** Every queue row has an inspectable provenance path.
- [ ] **AC-417.2:** Action replay is idempotent or explicitly conflict-detected.
- [ ] **AC-417.3:** Blocked rows explain the exact blocker and retry/unblock condition.
- [ ] **AC-417.4:** Bulk actions cannot cross incompatible review states.

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

Private Studio workflow over real processing state.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Read-only blocked-state inspector — 2026-10-08

`StudioReadOnlyWorkspace.tsx` now supports source-bound inbox row selection,
`ready/blocked` filters, explicit provenance display and fail-closed blocker
explanations for the fixture. No triage action is enabled: it would be unsafe to
turn a UI click into a review/merge/promotion without current persisted authority,
idempotency, rights and state-transition verification. Real queue reads, replay,
bulk-action compatibility, runtime canary and full acceptance criteria remain open.

Follow-up 2026-10-08: token-authenticated local Discovery endpoint now
reads paged persisted discovery-hit IDs, run IDs, exact disposition,
optional Content ID and safe blocker code. It excludes raw source URL,
query, title, provider receipt and private body. The local browser has
a read-only Inbox form. No reject, merge, promote, publish, bulk mutation,
review authority or idempotency acceptance is introduced.

### Scoped per-Hit provenance inspection — 2026-10-09

The authenticated loopback Studio adds `/v1/discovery/inspect` and a
read-only Inbox form accepting the exact Collection ID and Discovery Hit ID.
The SQL traverses persisted Hit -> Run -> Attempt -> Query -> Manifest ->
Collection, checking run/attempt lineage, active manifest, digest,
source-family/adapter scope, URL-to-Content equality and Collection
membership. A mismatched Collection/Hit pair is not found; there is no
cross-collection inspection by guessing an ID.

The response allowlists **IDs, safe status codes, specific blocker codes
and suggested unblock conditions**, not source URLs, titles, query text,
provider receipts, source bodies, model prompts or other private metadata.
The suggestions are not authorizations. No action to merge, reject,
extract, promote, publish or bulk-modify is enabled.
Even a fully matching synthetic Discovery lineage remains blocked by
`PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED` and
`DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE`; the response reports
lineage checks separately from those mandatory missing authorities.

Focused unit tests prove valid lineage, rejected/mismatched provenance,
blocked/capture-unapproved cases, malformed payload refusal, no private
fields in replies, loopback dispatch and local browser form. A MiniPC
PostgreSQL `pg_temp` canary exercises the **actual SQL** with one
synthetic valid row and then a failed Discovery Attempt, with all
temporary state rolled back and production counters unchanged.
Live `research:garlasco` has no persisted Discovery Hits to inspect.

**Partial only:** this adds an inspectable provenance path and exact
unblock guidance **for Discovery Hit rows**, not for every DP-417 queue
type. AC-417.1/.3 stay open until other queue families are implemented
and runtime-proven. Durable review transitions, idempotent action replay,
bulk-state compatibility and real source-family review remain open.

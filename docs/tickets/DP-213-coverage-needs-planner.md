# DP-213 — coverage needs planner

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-211, DP-212

## Problem

A corpus can be large but still incomplete. Today missing authoritative/original material is encoded informally in notes instead of driving reproducible follow-up discovery.

## Outcome

Persist and operationalize Coverage Needs so collections can state exactly which primary/original/independent/temporal/attribution sources are missing and which later discovery satisfies them.

## Scope

- Create coverage-need runtime/repository over the DP-113 schema extension if not already included.
- Generate needs from explicit policy/rules and reviewed extraction outcomes; model suggestions remain candidates.
- Link needs to collection and optional claim/candidate scope.
- Allow discovery manifests to target open needs.
- Record SATISFIED/BLOCKED/WAIVED with source links/review trail.

## Non-goals

- No claim verdict from a missing source.
- No arbitrary political priority score.
- No infinite autonomous searching.

## Dependencies and sequencing

DP-211, DP-212

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-213.1:** A missing official record produces an inspectable OPEN need.
- [x] **AC-213.2:** A matching captured authoritative source can satisfy the need with explicit link.
- [x] **AC-213.3:** Blocked access remains BLOCKED and stops bounded retries.
- [x] **AC-213.4:** Satisfied needs survive replay and remain historically auditable.

2026-10-09 safety follow-up: Coverage Need construction now refuses implicit
boolean/string/float coercion of retry counts or independence minima, wrong
candidate/role/scope types and exhausted Discovery hints. Duplicate semantic
need candidates collapse deterministically within the exact Collection while
distinct Collections keep independent needs. Legacy opaque Content/Claim and
Collection IDs remain supported; no external source was fetched and no
production need row was changed. This is additional input-integrity coverage
for the existing DONE source contract, not a new real-corpus acceptance.

Mac-side verification 2026-10-01 (all four ACs proven on source authority;
MiniPC migration replay/tracer still required before DONE, see below):

- AC-213.1: `test_missing_official_role_becomes_open_official_record_need` PASS.
- AC-213.2: `test_satisfaction_requires_explicit_link` PASS.
- AC-213.3: `test_terminal_states_are_explicit_and_bounded` +
  `test_discovery_hint_refuses_terminal_need` PASS; `max_attempts` defaults to 3
  and is hard-bounded to 1..10 (`COVERAGE_NEED_MAX_ATTEMPTS_INVALID`).
- AC-213.4: `test_collection_scope_is_part_of_identity_and_replay_stable` +
  `test_params_have_deterministic_event_ids` PASS; schema tests prove private
  need/event tables, explicit satisfaction links, backup inclusion and that the
  public projection never reads coverage-need state.
- Focused suite `test_coverage_needs + test_coverage_needs_schema`: all PASS;
  complete deterministic suite: **968/968 PASS**; benchmark **5/5 PASS**;
  `compileall` PASS; `git diff --check` PASS.

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

Private workflow only; useful bridge between research and evidence retrieval.

### 2026-10-10 collision/replay integrity maintenance

Disposable PostgreSQL RED tests exposed that a reused
\`coverage_need_event.id\` could still consume research attempts or
mark a need SATISFIED/BLOCKED even though \`ON CONFLICT DO NOTHING\`
had suppressed the corresponding event. These three operations now
append the event first and gate the corresponding state transition on
the newly inserted event in the same SQL statement. Six real database
cases verify refusal on collision and successful, idempotent normal
attempt/satisfaction/blocking. See
[\`coverage-need-immutable-event-20261010.md\`](../ops/coverage-need-immutable-event-20261010.md).
This is post-DONE correctness maintenance, not a new or silently
approved DP-214 source or a production deployment.

The continuation also proved RED→GREEN that both initial CREATED
events and OBSERVED_AGAIN assessment-refresh receipts must be
atomic with their associated rows. A conflicting event ID now raises
and rolls back that operation instead of silently creating/updating
an unreceipted need. Nine isolated PostgreSQL tests now cover the
complete five-event family without changing production data.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Mac-side implementation + verification recorded 2026-10-01 (see AC section above).

### MiniPC runtime proof 2026-10-01 (against Mac source `b099543`)

Mirror parity: 12/12 key-file SHA-256 digests byte-identical between
`/Users/domenico/Code/DichiarazioniPubbliche.it` and
`/home/udodo/src/DichiarazioniPubbliche.it` (`coverage_needs.py 74ff5460…`,
`source_intelligence.py 87e536cc…`, `queue_runtime.py 9c113f54…`,
`worker_daemon.py 500dfa71…`, `research_discovery.py 2c6ed5b3…`,
`public_projection.py 034af7c1…`, `schema.v1.sql ba156ffd…`,
`20260930-add-coverage-needs.sql 91eb21b0…`,
`20260930-add-source-intelligence.sql c43990fa…`,
`tools/coverage_need.py 79b075b4…`, `tools/sync_source_intelligence.py a8b8a9fa…`,
`config/source-intelligence.v1.json 5408e87a…`).

Pre-migration baseline: atomic_claim 30 / evidence 17 / verification_run 9 /
finding 9 / review_event 49 / processing_job 112 / right_of_reply 0 /
correction 0 (identical to the DP-211 production read-back).

Governed pre-migration backup `20261001T154412Z`: **10,168,368-byte** dump
(`deploy/ops/backup.sh`, `BACKUP OK`, 7 sets kept). Note: governed DP-502
rotation removed `20260929T104721Z`, `20260929T105031Z`, `20260930T123059Z`
and `20260930T123520Z` (the last two were cited in the DP-211 receipt; their
counts/digests remain recorded in that ticket).

Migration replay with `ON_ERROR_STOP=1`, both files, idempotent COMMIT:
`20260930-add-coverage-needs.sql` (ALTERs + COMMIT) and
`20260930-add-source-intelligence.sql`
(`relation "verification_run_source_intelligence_idx" already exists, skipping`,
COMMIT).

Isolated tracer in schema `dp213_215_canary` (canonical `schema.v1.sql`
applied, real `QueueRuntimeStore`/`SourceIntelligenceStore`, dropped after;
tracer script removed from `/tmp` after the green run):

- contract sync: profiles 13 / requirements 26 / roles 19 / rules 92 /
  scopes 10 — exactly the production shape;
- `materialize_coverage_need_specs` → upsert `CREATED`, exact replay →
  `EXISTING`, still 1 row (AC-213.4);
- OPEN need searchable with `remaining_attempts: 3`; attempt recorded;
  satisfy with explicit `source_profile_id` → `SATISFIED` + `resolved_at`;
  terminal need no longer searchable (AC-213.1/213.2);
- second need → `BLOCKED` with `ACCESS_OR_RIGHTS_BLOCKED`; satisfy without
  link rejected (`COVERAGE_NEED_SATISFACTION_LINK_REQUIRED`); block without
  code rejected (`COVERAGE_NEED_BLOCKER_REQUIRED`); duplicate
  collection+fingerprint insert rejected by `coverage_need_identity_idx`
  (AC-213.3);
- production `coverage_need`/`coverage_need_event`/`evidence_set_assessment`
  stayed 0/0/0 and `atomic_claim` stayed 30 throughout; canary dropped,
  `to_regclass` NULL after.

Zero-side-effect proof: per-table sorted COPY data of all 8 protected tables
byte-identical between pre-proof backup `20261001T154412Z` and post-proof live
(atomic_claim `f1d53492…`, evidence `da22e570…`, verification_run `c2aa6fc6…`,
finding `fa29b63e…`, review_event `515f1f1e…`, processing_job `ae2f9875…`,
right_of_reply + correction empty both sides). SI/coverage counts unchanged:
13/19/10/0/26/92/0/0/0.

MiniPC suite: **968/968 PASS**; deterministic benchmark **5/5 PASS**.
No live-provider calls made or required (deterministic paths only).

Governed post-migration backup `20261001T160005Z`: **10,168,365-byte** dump,
`BACKUP OK` (rotation removed `20260930T133555Z`, 7 sets kept).

DP-213 creates no verification/finding/publication rows and does not promote.
Marked DONE 2026-10-01.

Original pending note: record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

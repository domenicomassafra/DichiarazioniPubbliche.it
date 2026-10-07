# DP-214 — garlasco research collection tracer bullet

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-117, DP-209..213

## Problem

The architecture is not proven until a messy real-world corpus can be collected, searched, deduplicated and promoted without corrupting existing claims or creating public side effects.

## Outcome

Build the first real `research:garlasco` collection using a bounded set of 100 real Content items across direct interviews/articles, video/podcast, official/procedural material where available, secondary reporting and deliberate duplicate/derivation examples.

## Scope

- Create a versioned source/query manifest and ingest exactly the bounded pilot set.
- Read back Captures, Passages, entity candidates, Statement/Claim Candidates, clusters and Coverage Needs.
- Link/dedupe against the 30 existing Bruzzone/Lucarelli Garlasco Atomic Claims.
- Review a stratified sample of entity matches and proposition clusters.
- Run idempotent replay and record cost/capture/search metrics.
- Promote at least a small approved candidate slice through DP-117 only when provenance is sufficient; do not publish automatically.

## Non-goals

- No claim that 100 items are exhaustive coverage.
- No “who is more truthful” comparison.
- No automatic guilt/culpability inference.
- No public release of raw corpus bodies.

## Dependencies and sequencing

DP-117, DP-209..213

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-214.1:** 100 logical items have discovery/source provenance and successful items have immutable capture receipts.
- [ ] **AC-214.2:** Duplicate/derivation examples are surfaced without deleting source records.
- [ ] **AC-214.3:** Existing 30 claims remain unique and discoverable/linkable.
- [ ] **AC-214.4:** Search benchmark can answer the agreed Garlasco research questions with measured Recall@K.
- [ ] **AC-214.5:** Open authoritative-source gaps are Coverage Needs.
- [ ] **AC-214.6:** Replay leaves logical counts stable except for intentionally new Capture versions.
- [ ] **AC-214.7:** Public Finding/PUBLISH counts do not increase merely from ingestion.
- [ ] **AC-214.8:** MiniPC read-back and private/public leak checks pass.

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

Real private production corpus on MiniPC. Rights/retention policy governs body storage; no public launch.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Local preflight/replay contract implemented in `garlasco_tracer.py`. It refuses a pilot
manifest unless it contains exactly 100 unique HTTPS logical items, discovery provenance,
rights state, all five required source-family classes and an explicit 30-claim baseline. A
replay receipt fails closed if logical item IDs/claims change or ingestion changes the public
Finding count; additional immutable Capture versions may be recorded without redefining a
logical item. Manifest hashing is deterministic and material-sensitive.

Read-only MiniPC reinspection on 2026-10-07 resolves the old **27-vs-30** baseline mismatch:
the authoritative PostgreSQL database now contains exactly **30** `claim:garlasco:*` Atomic
Claims. That recovery does not create the tracer-bullet corpus. The same current runtime has
**0** Research Collections, therefore no `research:garlasco` row or membership; the 18 current
Garlasco Content records linked by those claims have **0** `content_capture`, **0** `passage`,
**0** Statement Candidate, **0** Claim Candidate and **0** collection Coverage Need rows.
All 18 current Garlasco Content rows remain `rights_status=UNKNOWN`. No real 100-item Garlasco
manifest was found in the repository, current MiniPC `/tmp`, runtime mirror or the searched
operator-state/backups paths; the former curated intake manifest documented at
`/tmp/garlasco-curated-2026-09-28.json` is no longer present.

The current MiniPC global corpus-search benchmark still passes **13/13 (100% case recall)**,
which confirms the existing claims remain searchable. It is not a `research:garlasco`
collection-scoped tracer run and therefore does not close AC-214.4 or substitute for AC-214.1,
.2, .5, .6, .7 or .8. None of AC-214.1..8 is marked complete from this inspection.

The exact remaining data blocker is the real bounded pilot itself: a versioned 100-item manifest
with the five required source-family classes, discovery provenance and rights state, persisted as
`research:garlasco` and then processed through DP-209..213/117 so the required captures,
passages, candidates, derivation/duplicate examples, Coverage Needs, replay and MiniPC leak/public
count checks can be read back. No synthetic collection or fixture is accepted as a substitute.

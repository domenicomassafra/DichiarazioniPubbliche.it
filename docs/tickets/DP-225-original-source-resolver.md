# DP-225 — Reviewed original-source resolver over derivation families

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-115, DP-215

## Problem

Derivation families and approved edges prevent source amplification, but there was no small,
deterministic operation that resolves a derived Content item to its reviewed original/root.

## Outcome

Resolve only through approved derivation edges, fail closed on conflicting origins, cycles,
unknown derivation and expected-root mismatch, and expose a replayable path/receipt that
Source Intelligence and Coverage Needs can consume.

## Acceptance criteria

- [x] Multi-hop approved derivation resolves to the reviewed root.
- [x] Candidate/model-suggested but unapproved edges never establish origin.
- [x] Conflicting approved origins fail closed.
- [x] UNKNOWN_DERIVATION cannot be promoted to original-source proof.
- [x] Cycles fail closed.
- [x] Family scoping prevents cross-family resolution.
- [x] PRIMARY_SOURCE / ORIGINAL_MEDIA / ATTRIBUTION_GAP Coverage Need satisfaction performs
  a runtime preflight against approved derivation families before accepting a Content link.
- [x] A reviewed derived copy resolves to its root but is refused as the satisfying Content;
  no approved family means unresolved rather than self-original by absence of evidence.
- [ ] Feed resolved original-root/path receipts into DP-215 assessment metadata and Studio
  inspection.
- [ ] Add database-backed/MiniPC canary using approved derivation rows.

## Implementation receipt

Local resolver + QueueRuntime Coverage Need original-source gate + focused tests added
2026-10-05. DP-215 metadata/Studio surfacing and a real PostgreSQL/MiniPC proof remain
open, so the ticket is not DONE.

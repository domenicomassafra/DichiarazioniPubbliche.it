# DP-225 — Reviewed original-source resolver over derivation families

Status: DONE
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
- [x] Feed resolved original-root/path receipts into DP-215 assessment metadata and Studio
  inspection.
- [x] Add database-backed/MiniPC canary using approved derivation rows.

## Implementation receipt

Local resolver + QueueRuntime Coverage Need original-source gate + focused tests added
2026-10-05. The 2026-10-06 closure pass now persists the bounded resolved root/path receipt
on the Coverage Need event/metadata and the linked DP-215 `evidence_set_assessment`; for an
`ATTRIBUTION_GAP` it also retains the ClaimCandidate/assessment target without copying source
text or rewriting the historical candidate.

Final machine proof on 2026-10-06 adds `tests/test_original_source_postgres.py`, which boots a
disposable PostgreSQL database from the canonical schema, inserts a synthetic but database-
validated `APPROVED` three-level derivation family, proves that the derived leaf resolves through
the exact edge/content path to the reviewed root but cannot satisfy a `PRIMARY_SOURCE` Coverage
Need, then proves only the reviewed root can satisfy it and that the bounded resolution receipt is
persisted. Local PostgreSQL acceptance is **1/1 PASS**; the combined resolver/preflight/PostgreSQL
set is **16/16 PASS** on an isolated MiniPC `/tmp` bundle with production DB/provider credentials
removed and automatic cleanup. This closes the database/MiniPC AC without claiming any live
source-family approval.

The same bounded `status` / `need_type` / `root_content_id` / `path_content_ids` /
`path_edge_ids` receipt shape is now a validated optional field on the private Studio Verify
view model and is rendered as an explicit "Origine revisionata" inspection block with source ref,
root and edge/content path. Studio validation rejects empty paths, edge/content length drift and a
root that does not terminate the content path. The fixture remains explicitly fixture-only and
public builds still omit Studio routes by default, so this inspection contract creates no public
source claim. Mac Astro check is **79 files, 0 errors/warnings/hints**; the explicit Studio fixture
build emits **36 pages** and `check-studio-v3` passes. The same isolated MiniPC acceptance is
green: DB resolver set **16/16 PASS**, Astro check 79 clean files, 36-page Studio fixture build,
and Studio contract check PASS.

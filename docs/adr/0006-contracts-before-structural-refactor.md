# ADR 0006 — Stabilize domain contracts before structural refactor

Status: Accepted  
Date: 2026-09-22

## Context

An architecture review found real locality problems in the broad PostgreSQL store and
multi-domain worker class, while also finding that the public projection and several
domain runtimes are already deep modules. M1 will change/settle important domain/schema
contracts.

## Decision

Do not perform a greenfield rewrite and do not refactor persistence/worker structure
before M1 domain contracts converge.

After DP-101..DP-106:

1. DP-107 narrows the concrete PostgreSQL persistence surface into a few deep domain
   stores sharing one execution primitive;
2. DP-108 keeps a small worker dispatcher and groups job implementations into a few deep
   domain handler modules.

Do not add generic repository interfaces until a second backend creates a real seam.
Keep the public projection as one deep fail-closed read boundary.

## Consequences

- Current working code remains the behavioral baseline.
- M1 avoids refactor churn while terminology/schema are still converging.
- Future refactors are behavior-preserving and test-driven rather than aesthetic rewrites.
- Large file size alone is not accepted as a refactor justification.

## Evidence

See `docs/reviews/architecture-deepening-2026-09-22.md`.

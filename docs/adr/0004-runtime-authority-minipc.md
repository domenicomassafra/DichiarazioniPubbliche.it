# ADR 0004 — MiniPC is backend runtime authority

Status: Accepted  
Date: 2026-09-22

## Context

Development occurs on the Mac, while the long-running PostgreSQL, timers, worker, and
deployment mirror run on the MiniPC. Confusing development proof with runtime proof has
caused false closure in other projects.

## Decision

The Mac Git checkout is source authority. The MiniPC is runtime authority for backend
claims. Runtime-affecting work is not complete until the ticket's MiniPC acceptance is
observed. The MiniPC mirror is deployment output, not a second Git authority.

## Consequences

- CI/local tests remain necessary but not sufficient for runtime completion.
- Deployment receipts belong in the ticket/operational docs, not in Git state on MiniPC.

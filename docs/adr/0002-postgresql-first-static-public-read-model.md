# ADR 0002 — PostgreSQL-first runtime and static public read model

Status: Accepted  
Date: 2026-09-22

## Context

The project should be inexpensive and low-maintenance while still preserving a temporal
graph, queue state, provenance, and public machine-readable records.

## Decision

Use PostgreSQL as the canonical operational store and initial job queue. Generate a
bounded public projection that can be hosted/cached statically or behind a thin API.
Do not introduce separate graph/vector/streaming infrastructure until a measured use case
cannot be served cleanly by the existing stack.

## Consequences

- Operational complexity stays low.
- Public reads do not depend on LLM/provider availability.
- Graph-like relations live relationally until query evidence proves a dedicated graph
  store is justified.

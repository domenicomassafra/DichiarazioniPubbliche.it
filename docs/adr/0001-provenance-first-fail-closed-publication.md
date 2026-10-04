# ADR 0001 — Provenance-first, fail-closed publication

Status: Accepted  
Date: 2026-09-22

## Context

Dichiarazioni Pubbliche handles reputationally sensitive public-statement records. A model answer or mutable
status field is not a sufficient publication basis.

## Decision

Retrieval, approval, verification, finding creation, and publication remain separate
stages. Public projection revalidates required provenance and review events at read-model
generation time. Missing, stale, inconsistent, or ambiguous provenance causes omission
or a non-public state, never a weaker automatic verdict.

## Consequences

- Temporary under-publication is preferred to stale/unsafe publication.
- Review events must be explicit and append-only.
- Tests must exercise tampered/stale persisted state, not only happy-path helpers.
- Public projection has its own strict schema and allowlist.

## Alternatives considered

- Trusting current status columns: rejected because state can drift from review history.
- LLM confidence threshold as publication gate: rejected because confidence is neither a
  reproducible proof nor a policy authorization.

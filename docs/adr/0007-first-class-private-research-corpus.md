# ADR 0007 — First-class private Research Corpus before verification

- Status: Accepted
- Date: 2026-09-29

## Context

The existing architecture persists Content and then quickly converges on transcripts,
Atomic Claims, evidence and Findings. Real research needs to retain discovered material,
immutable observed versions, passages, candidate statements, candidate propositions,
entity-resolution decisions, duplicate/derivation relations and coverage gaps even when
none of them will become a public fact-check.

Continuing to make Atomic Claim the first durable research object would either discard
useful context or overload the claim/evidence model with pre-verification uncertainty.

## Decision

Introduce a first-class private Research Corpus before Atomic Claim.

The corpus has additive objects for bounded discovery provenance, immutable Content
Captures, Passages, Research Collections, Statement Candidates, Claim Candidates,
entity-resolution candidates, Proposition Clusters, source-derivation relations and
Coverage Needs.

`Content` remains logical identity. `ContentCapture` is an immutable observed version.
Candidates are promoted, never mutated, into the existing Atomic Claim domain through an
explicit idempotent promotion contract. Corpus membership is never evidence and corpus
records are private by default.

The existing verification/publication model remains authoritative after promotion.
Direct-to-Atomic-Claim paths remain compatibility paths during expand-migrate-contract.

## Alternatives considered

### Keep Atomic Claim as the first durable object

Rejected. It cannot represent useful non-claim passages, unresolved attribution,
duplicate source material, source versions or research gaps without corrupting the
meaning of Atomic Claim.

### Replace the app with a donor research platform

Rejected. Aleph, Meedan Check, Pender, Alegre, Loki and other donors each solve useful
parts, but adopting a monolith would increase operational/licensing coupling and still
not provide Dichiarazioni Pubbliche's provenance/publication semantics.

### Store the corpus only as files/search indexes

Rejected. Core research state such as identity, promotion, review and collection
membership needs transactional, queryable provenance in PostgreSQL. Large/rights-sensitive
capture bodies may remain object/file artifacts referenced by hashes.

## Consequences

Positive:
- mass collection no longer implies mass fact-check creation;
- research becomes searchable/replayable;
- exact source versions and passage provenance survive extraction;
- candidate dedupe/entity resolution can happen before verification cost;
- Studio can be built against persisted research state.

Costs/risks:
- more private data requires explicit retention/rights controls;
- new candidate/review states increase domain surface;
- current intake paths need gradual migration;
- search/dedupe quality now needs its own benchmarks.

## Review trigger

Revisit only if a real corpus pilot shows that the candidate/capture layer creates more
operational complexity than it removes, or if a simpler representation can satisfy the
same provenance, search, replay and promotion acceptance criteria.

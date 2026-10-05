# DP-433 — Linked-data/RDF interoperability projection

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-105, DP-403, DP-430, DP-432

## Problem

CIMPLE demonstrates the interoperability value of stable URIs, ClaimReview mapping, RDF
vocabulary and SPARQL-friendly data. Dichiarazioni Pubbliche already emits bounded
ClaimReview JSON-LD, but does not have a complete stable-URI/RDF export contract for
people, statements, topics, sources, findings and provenance.

## Outcome

Generate a deterministic read-only linked-data projection from the approved public schema.
Keep PostgreSQL and the static public projection authoritative; RDF is an interoperability
artifact, not a second database or a reason to introduce Virtuoso.

## Acceptance criteria

- [ ] Stable public URI rules exist for Person, Statement, Topic, Source/Content and
  versioned Finding resources.
- [ ] Existing ClaimReview JSON-LD maps to the same canonical Statement/Finding identities.
- [ ] RDF export represents provenance/correction/supersession without exposing private
  transcript/evidence bodies or internal review notes.
- [ ] Vocabulary reuses schema.org and an explicit small provenance mapping; custom terms
  are versioned and documented only where necessary.
- [ ] Export is deterministic from one projection fingerprint and can be regenerated
  offline without provider/LLM/database access on the public request path.
- [ ] A validation fixture proves URI stability, no person scores, no raw private data and
  correction versioning.
- [ ] No SPARQL server, triplestore or new always-on infrastructure is required for v1.
- [ ] If a public SPARQL service is ever proposed, it requires a separate measured ticket
  and security/cost review.

## Completion receipt

Pending core public-resource stabilization.

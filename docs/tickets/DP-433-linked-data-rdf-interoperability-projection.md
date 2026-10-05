# DP-433 — Linked-data/RDF interoperability projection

Status: IN PROGRESS
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

- [x] Stable HTTPS URI rules exist for Person, Statement, Topic, Content, Evidence,
  Organization, Correction, Dataset and Finding resources.
- [x] Existing ClaimReview JSON-LD now uses the same canonical Statement/Finding/Person/
  Organization identities as the linked-data export.
- [x] Deterministic N-Triples export represents evidence citation and finding
  correction/supersession without exposing private
  transcript/evidence bodies or internal review notes.
- [x] Vocabulary reuses schema.org + PROV-O with a small versioned project vocabulary for
  assessment/publication/evidence metadata; custom terms
  are versioned and documented only where necessary.
- [x] Export is deterministic from one validated projection fingerprint and can be regenerated
  offline without provider/LLM/database access on the public request path.
- [x] Validation fixtures prove URI stability, no person scores, no raw transcript/review
  fields, topic links and
  correction versioning.
- [x] No SPARQL server, triplestore or new always-on infrastructure is required for v1.
- [ ] If a public SPARQL service is ever proposed, it requires a separate measured ticket
  and security/cost review.
- [x] Static public bundle now writes index.nt plus a fingerprinted
  linked-data-receipt.json; rebuild overwrites stale top-level linked-data artifacts.
- [ ] Add web-host content type/discoverability metadata (application/n-triples,
  sitemap/data page or Link relation) and one deployed read-back before DONE.

## Completion receipt

Pure linked-data projection, stable URI contract, ClaimReview identity convergence and
static index.nt + receipt build wiring added 2026-10-05. Web-host content type/
discoverability and deployed read-back remain open.

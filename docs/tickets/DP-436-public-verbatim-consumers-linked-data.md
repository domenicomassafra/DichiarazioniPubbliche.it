# DP-436 — Verbatim search, cards, relations and linked-data consumers

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-435, DP-402, DP-403, DP-433

## Problem

The current public consumers present normalized paraphrases as quotations in several cards, titles, Trace/Content views and search. A correct Statement detail does not make the whole product faithful to Q15–Q20.

## Outcome

Every authorized public representation of a Statement uses the same literal approved source words, separately labeled summary/translation, source context and version; withdrawing that record removes it from current public views.

## Traceability & constraints

R02, R03, R04, R15, R24, R36; Q15–Q20. Keep DP-305 no-private-body and rights gates, static no-LLM readers, historical v2 receipts. Implementation not authorized in this planning phase.

## Scope

Migrate Home, Explore, Person, Topic, Content, Trace, search index, metadata, HTML, JSON-LD, RDF, sitemap and API to the DP-435 first-class Statement contract. Distinguish original quote, identified Italian translation, normalized internal proposition and separate summary in every consumer. Preserve canonical/legacy URLs, version fingerprints and correction/retraction propagation. The projection explicitly bounds the approved excerpt and never publishes full captures/raw transcripts/private notes.

## Non-goals

No live public chatbot, new full-text copyright grant, fake source samples, or replacement of DP-435's provenance and rights decision.

## Dependencies and sequencing

Hard: DP-435, DP-402/403, DP-433. Coordinate DP-405..409, DP-422, DP-429, DP-431. Expand public schema then migrate all consumers before removing legacy wording behavior; reject mixed incompatible versions rather than silently defaulting to paraphrase.

## Acceptance criteria

- [ ] `AC-436.1`: Given one authorized original Statement, every surfaced quote is byte/meaning-faithful to its approved span and refers to the same source version/hash; translation and summary never appear as words the Person literally said.
- [ ] `AC-436.2`: Cards, page headings, API, search, JSON-LD, RDF and sitemap agree on public IDs, language, quote meaning, locator and dataset fingerprint; no operational body leaks.
- [ ] `AC-436.3`: Correction, rights expiry/revocation or stale capture removes/updates the affected current record in static HTML, API, index, linked data and cache without revealing held/private membership.
- [ ] `AC-436.4`: Identical safe replay generates byte-stable public data; incompatible legacy clients fail closed; real approved MiniPC URL/API readback proves version parity and no per-request LLM.

## Validation / proof

Future acceptance: cross-format snapshot/diff, spoofed paraphrase/translation negative tests, raw-body scanner, source rights revocation under cache race, original-versus-output hash checks and live authorized MiniPC consumer readback. Fixture and historical CI are not source approval.

## Documentation, data, and migration impact

Update schema/API consumer contracts and source map after implementation; incremental expand/migrate/contract of search and linked data with compatibility version and rollback, keeping previous signed receipts intact.

## Completion receipt

2026-10-10: planning only, **not implemented**; all new AC unchecked.

## 2026-10-11 — First implementation slice

Opt-in v3 Statement serializations in `public_api.py` and `linked_data.py` (commit `4a7afbf`) plus isolated web `statementV3.ts`/`VerbatimStatementRecord.astro` (commits `caa5c5c`, `ce60baf`). Original quote, locator/source, summary/translation and optional Finding have distinct types. 13 backend consumer tests and synthetic web statement test pass; existing v2 endpoints/routes unchanged. No real v3 HTTP route, public-host cache/revocation, source rights or MiniPC proof.

# ADR 0009 — No public Case/Collection page for the current Garlasco pilot

- Status: Accepted
- Date: 2026-10-17
- Decision scope: DP-421; the current release and available Garlasco evidence

## Context

The existing public information architecture already exposes reviewed people,
topics, original statements, content and published findings through their
separate contracts. A private Research Collection holds a different class of
material: discovery leads, versions, passages, unpublished candidates,
annotation state and review work. A new public `/casi` page would need
legitimately publishable content and an independently tested reader purpose.

The 2026-10-17 MiniPC read-only check for DP-420 observed:

- The versioned historical Garlasco lexical search benchmark passed **13/13**
  queries at top 5, with observed p95 **111.172 ms**. This measures retrieval of
  known historic claims, not the usability of a public Case page or source
  quotation navigation.
- Private operator search of `Garlasco` within `research:garlasco` returned
  **17** metadata results, with source/Content identifiers but no reproduced
  source documents.
- The persisted collection is **PAUSED**. It includes **18** Content records,
  all **18** lacking cleared source rights; it has **0** Capture, **0** Passage,
  **0** Statement/Claim Candidate and **0** Coverage Need records. The first
  10 collection-navigation records confirm no Capture edge to follow.
- A proposed 100-item pilot is missing **82** items and accepted discovery
  provenance in all five required source families. Six unreviewed lead URLs
  and a homepage locator do not fill these gaps.

These observations do not establish that the reader needs a distinct Case
object, that alleged facts were verified, or that source material can lawfully
be displayed. There is no accepted operator study of exact quotation and
duplicate navigation yet; DP-420 remains open on those criteria.

## Decision

**NO-GO for a dedicated public Case/Collection page or projection in the
current release.** Preserve the existing public information architecture,
routes and data contracts. Keep the entire Research Collection
private. Do not relabel an unpublished candidate or unverified allegation as a
published finding, use a case page to expose private source URLs/passages, or
make a guilt/reliability/personality ranking from the private collection.

This is a decision to **defer the new public surface**, not an assertion that
the current private Garlasco workflow has completed its source, legal, or
usability acceptance. Readers can continue using existing public Topic,
Person, Content and Statement/Trace navigation for legitimately published
material; there is no automatic case grouping of those records.

## Alternatives considered

- **Publish the private Research Collection as a Case** — rejected because
  rights, privacy, provenance, review and correction boundaries are different.
- **Introduce an empty or speculative Case page now** — rejected because a
  placeholder cannot answer validated reader tasks and may imply complete
  factual coverage where none exists.
- **Reuse existing public views and revisit with genuine evidence** — chosen.

## Consequences and reconsideration

There is **no application route, schema, API, migration, permission, indexing
or deployment change** from this ADR. Existing public links remain stable.

Reconsider only after DP-214 source provenance, rights and citation readiness
and DP-420's real operator usability tasks identify a distinct public reader
need, with measurable quote navigation, duplicate context and correction
behavior. Any future GO requires a new reviewed sanitized projection contract
containing exclusively approved public source identifiers and versioned
correction/withdrawal behavior, with no private Studio data by default.

Evidence: `docs/tickets/DP-420-garlasco-studio-usability-search-acceptance.md`
(historical requirements), GitHub Issues #74 (2026-10-17 MiniPC checks),
`tests/fixtures/corpus-search-benchmark-v1.json`, and read-only MiniPC
`garlasco_pilot_inventory`, `report_research_pilot` and
`read_collection_navigation` outputs observed for this decision.

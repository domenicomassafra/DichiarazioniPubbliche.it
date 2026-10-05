# DP-429 — Explore page v4

Status: FUTURE  
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-409, DP-425

## Problem

Explore is the universal discovery hub for the public registry, but DP-409 primarily owns
the deterministic search/index contract. The v4 redesign also needs a dedicated page
implementation slice for hierarchy, result-type switching, filters, URL-restorable state,
responsive behavior and the visual treatment shown in the selected redesign.

Without a separate UI owner, search/index work risks absorbing page-design scope while
the rest of the public product drifts away from the shared Entry/index grammar.

## Outcome

Implement `/esplora/` as the canonical v4 discovery surface. A reader can search the
published registry, switch among public object types, progressively refine results,
restore/share the current query state, and open the correct canonical destination without
learning internal data vocabulary.

## Scope

- v4 Explore header, search field and result-count hierarchy;
- result-type switcher for `Tutto`, `Dichiarazioni`, `Persone`, `Temi`, and
  `Contenuti`;
- bounded filters for the fields approved by DP-409/public schema;
- desktop compact filter row and phone `Filtri` sheet;
- deterministic result rows for each public object type;
- query/filter/sort state represented in the URL and restored on reload/back navigation;
- empty, invalid-query, unavailable-index and filter-transition states;
- contextual links only to canonical Statement/Person/Topic/Content/Trace destinations.

## Non-goals

- a second search backend or hosted search service;
- semantic/RAG/LLM query interpretation;
- standalone profession/category landing pages;
- popularity, recommendation or person ranking;
- infinite-scroll news feed;
- exposing private/held/candidate records;
- changing DP-409's index schema/ranking contract from the UI.

## Dependencies and sequencing

- **DP-409** owns the static search artifact, matching and deterministic ordering;
- **DP-425** owns the v4 Entry/index components and responsive contracts;
- **DP-405..DP-408/DP-427** own the destination page jobs;
- **DP-422** owns final legacy-route/canonical-route cutover after this page lands.

## Traceability & constraints

- **Traces to:** US-36-05, US-36-07, DEC-36-03, DEC-36-06, AC-36.6, AC-36.8,
  AC-409.3, AC-409.4, AC-409.8.
- **Constraints:** one universal discovery hub; deterministic/public-safe results only;
  no provider/LLM call; filter state shareable; phone UI may not squeeze the desktop filter
  row into the viewport.

## Acceptance criteria

- [ ] `/esplora/` is the only universal public search/filter hub;
- [ ] search and every supported filter operate only on DP-409's approved public index;
- [ ] result-type switching changes the result set without inventing separate landing-page
  taxonomies;
- [ ] every result row exposes the minimum useful context and opens the deterministic
  canonical route for its object type;
- [ ] query, filter and sort state survive reload, browser back/forward and copied URLs;
- [ ] no-match, invalid-query and unavailable-index states are explicit and recoverable;
- [ ] phone uses one clear filter affordance/sheet with practical touch targets and no
  horizontal page scroll;
- [ ] keyboard, screen-reader, 200% zoom and reduced-motion behavior preserve search,
  filtering, result count and selected-state semantics;
- [ ] no query is sent to an LLM/provider or written to raw telemetry.

## Validation / proof

`cd web && npm run check && npm run build`; run DP-409 deterministic query fixtures;
capture desktop + phone screenshots for default/results/no-results/filter-open states;
verify URL restoration/back navigation; keyboard/focus/200%-zoom pass; inspect network
requests for zero provider/LLM traffic; `git diff --check`.

## Documentation, data, and migration impact

Update the maintained Explore mockup and any public-navigation copy only after the v4
direction is selected. No database migration; search artifact ownership remains DP-409.

## Completion receipt

Pending implementation.

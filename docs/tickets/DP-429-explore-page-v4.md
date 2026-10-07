# DP-429 — Explore page v4

Status: IN PROGRESS
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

- [x] `/esplora/` is the only universal public search/filter hub;
- [x] search and every supported filter operate only on DP-409's approved public index;
- [x] result-type switching changes the result set without inventing separate landing-page
  taxonomies;
- [x] every result row exposes the minimum useful context and opens the deterministic
  canonical route for its object type;
- [x] query, filter and sort state survive reload, browser back/forward and copied URLs;
- [x] no-match, invalid-query and unavailable-index states are explicit and recoverable;
- [x] phone uses one clear filter affordance/sheet with practical touch targets and no
  horizontal page scroll;
- [ ] keyboard, screen-reader, 200% zoom and reduced-motion behavior preserve search,
  filtering, result count and selected-state semantics;
- [x] no query is sent to an LLM/provider or written to raw telemetry.

## Validation / proof

`cd web && npm run check && npm run build`; run DP-409 deterministic query fixtures;
capture desktop + phone screenshots for default/results/no-results/filter-open states;
verify URL restoration/back navigation; keyboard/focus/200%-zoom pass; inspect network
requests for zero provider/LLM traffic; `git diff --check`.

## Documentation, data, and migration impact

Update the maintained Explore mockup and any public-navigation copy only after the v4
direction is selected. No database migration; search artifact ownership remains DP-409.

## Completion receipt

Local implementation now consumes only the verified `search-index.v1.json` contract from
DP-409. `/esplora/` exposes a real radiogroup switcher for Tutto/Dichiarazioni/Persone/Temi/
Contenuti with deterministic counts, bounded assessment/sort filters, explicit result rows and
recoverable invalid/no-match/unavailable states. Query/filter/sort serialization is factored
into pure helpers with invalid-value fallback tests; the client listens to `popstate` and pushes
discrete filter changes while query typing replaces the current URL, so copied/reloaded history
states have one canonical encoding. Search is entirely in-browser against the verified static
artifact and the built client contains no database/provider runtime marker.

`npm run check:search`, Astro check, static build, public-quality checker and `git diff --check`
pass. The route builds with exactly one `h1`, canonical `/esplora/`, a skip link, explicit labels
and a semantic radio group. A real local Chrome headless run against the built static site proved
hydration with 12 records, switch to `Persone` with 3 records and `?tipo=person`, browser Back
restoring `Tutto`, and a 375px mobile viewport with `scrollWidth=innerWidth` plus a 44px filter
target. The native `<dialog>` opened with focus inside it and Escape closed it and returned focus to
the filter button. Reduced-motion media emulation was observed by the page; the reload/interactions
made only same-origin requests, with zero provider/LLM request. The same browser check now covers
no-match recovery, overlong-query alert semantics, keyboard radio focus/selected state, a 640 px
200%-equivalent reflow viewport and the correction-history `#storia` destination. It also proves
exact 200% Chrome browser zoom through a temporary per-host zoom profile: `outerWidth=1280`,
`innerWidth=640`, `devicePixelRatio=2`, `visualViewport.scale=1`, no horizontal overflow and the
same usable search/filter controls. Actual screen-reader semantics remain DP-410 acceptance, so
the combined accessibility AC stays open. The same current-tree browser matrix was rehearsed on
MiniPC Chrome 150: 19 canonical routes scanned, zero external requests, reduced-motion behavior
preserved, phone `375/375` viewport/scroll width and 44 px filter target, plus exact 200% browser
zoom with `innerWidth=640`, `outerWidth=1280`, `devicePixelRatio=2`,
`visualViewport.scale=1`, `scrollWidth=635` and a 44 px filter target. No real
screen-reader/manual visual acceptance is inferred from these automated checks.

The final approved empty production shape is now a first-class QA case rather than a fixture
failure. With zero search records, Explore still hydrates, serializes keyboard filter state,
opens/closes the filter dialog with focus restoration, exposes the overlong-query alert, respects
reduced motion, stays within the 375 px phone viewport and exact 200% browser zoom, and performs
zero external/provider requests. Populated demo QA still requires result/history links. The mixed
accessibility AC remains unchecked solely because real screen-reader judgment is still required.

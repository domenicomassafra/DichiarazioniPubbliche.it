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

## Post-grilling planning reconciliation — 2026-10-10

Remain IN PROGRESS. Explore needs independent Person and Topic URL filters whose intersection is approved Statement IDs, not a chatbot or one inferred opinion profile (DP-439); optional precomputed sourced synopsis is separate (DP-440). Correct messages distinguish zero total approved corpus, filters returning no match and unavailable/stale projection. Cards must never turn normalized paraphrases into exact quotes (DP-436). Preserve existing search and 320–1440/200% QA receipts but AC-429 manual screen reader remains open. All historical AC checkboxes and dated receipts preserved; no runtime change or acceptance inferred from this planning update.

### 2026-10-11 — limited Explorer hardening, source-only

Commits `df6fa42`, `5c72563`, `f8b2b6e` add Person×Topic filtered public-index search, reject unpublished topic facet references and visually/semantically label old `PARAPHRASE` Finding titles as **not literal quotes**. The empty/filtered-no-match/unavailable paths remain distinct; historical paraphrase bodies are not transformed into quotations. Focused search, design, Astro (0 diagnostics) and isolated projection boundary checks pass locally. No real device AT check, owner-selected redesign, live approved corpus or MiniPC release/readback; no old manual accessibility AC closed.

### 2026-10-11 — Approved-empty Explore accessibility regression

Source/UI commit `cf70a4f` adds a **visible and ARIA live atomic result count**
(`0 risultati pubblicati`) to `/esplora/` when the approved public index has
zero records. The lede no longer promises an unavailable search interaction.
`tests/dp429_explore_accessibility_regression.mjs` builds a fresh, isolated
real Astro projection/index with zero approved records, verifies its dataset
fingerprint, heading/accessible count/links, and absence of dummy or private
search results. The optional real Chrome QA subrun passed keyboard,
reduced-motion and 200%-browser-zoom checks; web Astro check reported zero
diagnostics and isolated build PASS. This deliberately does not change the
populated search UI/index or serve a public release. Actual screen-reader
acceptance/selected design and MiniPC/public proof remain OPEN; the final
mixed accessibility AC is not checked and ticket stays IN PROGRESS.

### 2026-10-11 — Populated result status and filter disclosure

The populated Explore island now presents an atomic `role="status"` result
count matching the approved-empty page. A rejected overlong query is labelled
`Ricerca non eseguita` instead of falsely showing zero matches. The native
filter dialog's trigger has explicit `aria-controls` and `aria-expanded`
values following open, Escape and close. Existing radio selected-state/focus
and deterministic routes are preserved. The isolated
`tests/dp429_explore_accessibility_regression.mjs` builds both approved-empty
and expressly local populated demo states; optional Chrome QA now covers
live status/disclosure and keyboard transitions. Both builds plus Chrome QA
PASS, `npm run check:search` PASS, Astro check zero diagnostics; see DP-409.

The mixed keyboard/screen-reader/200%-zoom/reduced-motion criterion stays
**unchecked**, because real VoiceOver/NVDA (or equivalent) judgment and manual
visual/owner acceptance remain outstanding. Status remains IN PROGRESS.
No MiniPC deployment or public release is represented by this receipt.

### 2026-10-12 — Search-clear focus regression (bounded source tranche)

Owner: serial DP integrator, `fix/dp429-clear-search-focus-20261012`.
Scope: `web/src/components/ExploreClient.tsx`, existing browser QA in
`web/scripts/check-browser-qa.mjs`, and this ticket only. AC: on populated
approved-index search, keyboard-activating `Pulisci ricerca` clears the query,
restores focus to the stable search input when the conditional button unmounts,
and preserves the accessible result count and same-origin search boundary.
Use the native React input ref and the current real-Chrome QA harness (no new
dependency, service, abstraction, editorial/public dataset or deployment).
Reuse search: existing `useRef`/`.focus()` in ExploreClient's filter dialog and
its CDP keyboard/accessibility suite; DStack/owner-code search found no more
specific component helper, and native focus is sufficient. AC-429 manual AT,
MiniPC live proof and publication acceptance remain open independently.

Source and browser proof: the initial real-Chrome test failed on the clear
control; after the native `useRef<HTMLInputElement>` focus restoration the
existing isolated `DP429_BROWSER=1` test passes with keyboard Space activation,
unmounted clear button, returned input focus, URL `q` reset and restored result
count. Both approved-empty and explicitly local populated-fixture artifacts were
built independently; fixture data were not published. Fresh `npm run check`
(0 diagnostics), `check:search` (PASS), `check:quality` (PASS), and
`check:design:a11y` (8 PASS) are source/static evidence, not live MiniPC,
screen-reader, manual owner or editorial acceptance. At the 2026-10-12
checkpoint, delivery was `PUSHED_FOR_REVIEW` with PR creation held because the
external automatic-review billing setting was not yet confirmed OFF.

**2026-10-13 owner update:** the owner explicitly confirmed automatic code
reviews are disabled everywhere and instructed removal of that blocker. The
historical `PR_HELD_AUTOREVIEW_BILLING_GUARD` is therefore **RESOLVED by owner
attestation**, not an open ticket or an outstanding PR-creation prerequisite.
The accessible ChatGPT settings independently showed the visible personal
switches OFF but did not expose the historically linked GitHub identity;
do not misrepresent owner confirmation as a provider-account readback. Normal
local review, actual PR CI, native review threads, manual accessibility and
editorial/publication gates remain separate and applicable. No automatic
Codex review or extra-credit review is requested by this change.

MiniPC real-Chrome 155 isolated-source follow-up, 2026-10-12: the approved-empty
canary passed 18 route checks, exact 200% zoom, keyboard and zero external
requests; a populated local-only canary exposed a late `<dialog>` close event
that could reset the filter trigger's `aria-expanded` after immediate reopen.
The owned fix synchronizes disclosure to the dialog's observed open state on
`close`, preserving focus restoration only for a truly closed dialog; the
existing browser suite now explicitly covers rapid keyboard reopen. After the
fix, `DP429_BROWSER=1 node tests/dp429_explore_accessibility_regression.mjs`
passed on Mac, with Astro 0 diagnostics, search checks and 8 design-a11y checks
PASS. **MiniPC isolated Chrome 155 replay: PASS** for the populated 12-record
fictional fixture (including rapid filter reopen, clear-button keyboard focus,
URL/results restoration, zero external requests); the approved-empty isolated
build independently passed 18 routes, exact 200% browser zoom on six pages,
keyboard, reduced motion and zero external requests. Temporary canary files
were cleaned; MiniPC live service stayed active and deployed Explore HTML SHA
`e9e4358ca5ddffab4c5c3d851a809a75d0bd2ddd26db5a356507c3d6a3aca3ef`
remained unchanged. Neither fixture is a public dataset, deployment or sign-off.

### 2026-10-13 — Independent PR review: delayed-close race regression

An independent native Chat On Steroids worker reviewed PR #3 at
`58ec0f0e932e66af64205a37a46e2d013c5587f5` and identified a coverage gap:
the existing keyboard test reopened the filter dialog only **after** the native
`close` event had been consumed. The browser test now intentionally calls
`dialog.close()` and reopens it synchronously in the same JavaScript task,
proves the delayed native `close` event arrives while the dialog is open,
and checks `aria-expanded="true"` plus focus remaining inside it after React
handles that event. The worker demonstrated **RED** against the previous
`17ad6db` handler (`aria-expanded="false"` while the dialog was open), then
**GREEN** on the corrected component with real Chrome; the existing
`DP429_BROWSER=1` approved-empty and local-populated QA still passes.
This is strengthened source/regression proof, not a manual screen-reader
acceptance or permission to merge/deploy/publicly publish content.

## Owner round aggiuntivo — 13 ottobre 2026

Q1 suggerimenti espliciti di ricerca, query originale preservata. Q2 Esplora iniziale per data recente della dichiarazione, distinto da data di aggiunta. Q3 filtri/sezioni per cronologia, pertinenza ed esiti documentati di verifica della singola proposizione. “Più giuste/sbagliate” è richiesta UX da affinare su stati approvati, non autorizza punteggi/ranking delle persone, booleani da opinioni o comparazione non calibrata. Distinguere SUPPORTED/FACTUALLY_FALSE da NOT_CHECKED/insufficient/conflict/non-factual; sorting quantitativo richiede criterio adeguato, altrimenti usare filtro per categoria.

Decisione/ricerca futura registrata: nessuna implementazione o acceptance nuova, status e criteri originali invariati.

### 2026-10-13 — Opt-in suggestions from the approved public index (source-only)

New deterministic `ExploreClient` suggestions are offered **only after zero matches**
and only from the current verified public search index, with at most four bounded
near-word proposals. They use the already approved public vocabulary, respect
record-kind and Person/Topic/result-state filters, never query private tables
or a provider, and preserve the exact original query including whitespace in
the input and shareable URL. A visible button explicitly selects a suggested
query and returns keyboard focus to search. No automatic spelling correction,
person ranking or inference of an outcome from an opinion is performed.

Test `web/scripts/check-dp429-public-query-suggestions-20261013.mjs` was
**RED** before the component export existed, then **GREEN**. Astro check has
zero errors/warnings, `check:search` and `check:design:a11y` pass; an isolated
local demo build and real Chrome QA pass with 12 fictional records, 21
scanned routes, zero external requests, genuine 200% browser zoom and phone
reflow. This is technical pre-merge test evidence only, not real source,
editorial, MiniPC deployment or manual assistive-technology acceptance.

**Q2 remains blocked** pending DP-409/public-projection support for a separately
verified date of the original Statement and an archive-addition timestamp:
the current v2 `published_at` field is finding/source publication, **not**
necessarily the date of the declaration. The interface now labels the known
date boundary rather than falsely claiming chronological Statement sorting.
The original DP-429 acceptance and manual/accessibility gate remain open;
ticket stays **IN PROGRESS**.

## 2026-10-14 — Mobile Explore active facets and public intersection counts

Implemented a substantial v4 Explore refinement on an isolated source branch:
the current verified static search index now drives an accessible group of
individually removable **active type, outcome, order, Person and Topic chips**.
Each action updates only its selected URL facet, retaining the user's exact
query and unrelated Person/Topic filters; the filter trigger receives focus
when the removed chip disappears. Every chip has an explicit accessible
`Rimuovi filtro` action, at least 44px touch height, wrapping text and phone/
200%-zoom reflow. The filter sheet additionally shows bounded approved
Finding counts per Person and Topic, recomputed with other selected filters
held fixed. Topic membership comes **only** from approved public index
`finding.topic_ids`; a source title, arbitrary matching name or private
candidate does not create membership. Unknown URL Person/Topic IDs never
appear as raw text in visible or accessible chip labels, and only actually
indexed public Person/Topic options receive counts.

`check-dp429-public-query-suggestions-20261013.mjs` was first **RED** on the
missing active chip projection. After implementation it is **GREEN**, now also
checking exact single-facet removal with URL/query preservation, invisible
unknown facet IDs, four independently labeled public record kinds and
candidate-count intersections across multiple Topic IDs. `npm run check`
reports 0 errors, 0 warnings, and one **preexisting DP-429 unused `require`
hint**; `npm run check:search` passes. The isolated empty-public/demo browser
QA passes keyboard/AX/phone reflow, genuine 200% zoom and zero external
requests; the production projection boundary still rejects renamed demo
fixtures and keeps explicit demo runs `noindex`.

The v2 artifact lacks a verified original Statement date and archive-addition
date. This implementation does **not** invent those fields, change DP-409's
search schema, expose first-class v3 claims without public release authority,
or grant search relevance/person scoring. It introduces no database, provider,
paid service, new public rights decision or MiniPC deploy.

**DP-429 remains IN PROGRESS and all original AC checkboxes stay unchanged.**
Manual screen-reader/physical/owner acceptance and main PR+CI release gate
remain external requirements.

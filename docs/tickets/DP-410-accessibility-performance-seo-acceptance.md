# DP-410 — Accessibility, performance, and SEO acceptance

Status: IN PROGRESS

Milestone: M4 — public product/API
Depends on: DP-405, DP-406, DP-407, DP-408, DP-409, DP-422, DP-425, DP-426, DP-427, DP-428, DP-429

## Problem

The public product is a provenance record, not a visual demo. It must remain readable
and operable with keyboard, touch, assistive technology, zoom, reduced motion, slow
networks, and provider outages. It must also expose crawlable, honest metadata without
turning Studio fixtures or private operational state into public search results.

This ticket is a quality gate across the canonical v3 public template family. It is not a cosmetic
polish pass and does not authorize a new hosting, analytics, or search service.

## Outcome

Define and run the cross-surface acceptance matrix for:

- semantic structure and WCAG 2.2 AA behavior;
- responsive and text-zoom resilience;
- performance under a static-first request path;
- SEO/metadata for public routes and explicit non-indexing for private surfaces;
- offline/provider-independent behavior and fail-closed states;
- neutrality and absence of raw/private content.

A ticket cannot be marked production-ready when its required public surface has not
passed this gate.

## Contract gate

- **DP-105** must close the public schema and v1/v2 compatibility decision;
- **DP-405..DP-409, DP-426..DP-428** must provide the real route/fixture surfaces; this ticket may define
  quality criteria before they are implemented but cannot certify placeholders;
- **DP-425** must provide the selected v4 consolidated token/component contract;
- **DP-401** must provide the static/read adapter used for runtime proof;
- current `dichiarazioni-pubbliche-public-v2` fixtures are development inputs only until DP-105 closes.

## Scope

### Accessibility contract

Every public route must meet WCAG 2.2 AA expectations and the UX-v2 rules:

- one meaningful `h1` per page and a logical heading hierarchy;
- semantic landmarks, lists, tables, headings, and form labels;
- keyboard access to every link, control, disclosure, filter, media action, dialog, and
  timeline marker;
- visible `:focus-visible` indication that does not rely on color alone;
- no keyboard trap, hover-only information, or focus-order divergence from reading order;
- body text remains readable at 200% browser zoom and dynamic text expansion;
- standalone controls have a practical 44px touch target at phone widths;
- finding/assessment/relation states always include text, with color and icon secondary;
- source links have descriptive labels and safe external-link behavior;
- dates/times have machine-readable values and understandable visible labels;
- loading, empty, unresolved, blocked, correction, and error states are announced without
  stealing focus;
- reduced motion preserves every state and action;
- text and interactive contrast meets WCAG AA, including focus/hover/selected states;
- no raw transcript/evidence body is exposed through an accessibility tree, hidden DOM,
  alt text, or disclosure.

The private Studio must meet the same keyboard/focus/contrast requirements, but it is
excluded from public SEO and must be explicitly non-indexable.

### Performance and resilience contract

Measure on a cold static preview and the MiniPC deployment mirror, not on a developer
machine with warm caches:

- no public page requests an LLM, model provider, evidence provider, PostgreSQL, or
  operational filesystem on the request path;
- public pages render from static HTML/public projection data; interactive islands load
  only when their bounded interaction is used;
- target LCP is at most 2.0 seconds, CLS at most 0.10, and INP at most 200 ms on the
  agreed representative mobile profile with a cold cache;
- initial public-route JavaScript is at most 120 KiB compressed per route, excluding
  explicitly documented media/font assets; a route that needs more must justify and
  measure the exception before acceptance;
- images/media have bounded dimensions, no layout-shifting placeholders, and no
  autoplay;
- search/index and client interactions meet DP-409's deterministic bounds;
- provider-offline mode is a normal pass condition, not an error state;
- a failed or incompatible projection produces a bounded unavailable state and never a
  stale unsafe record.

Budgets are acceptance targets, not a reason to add a CDN, cache vendor, worker, or
rewrite system. If a target cannot be met with the current stack, record the measurement
and open a bounded performance ticket.

### SEO and discovery contract

For every public route:

- `lang` is correct (`it` for the current product copy), title and description are
  specific, and a canonical URL/path is emitted;
- exactly one meaningful `h1` and crawlable internal links describe the actual record;
- public JSON-LD, when emitted, is valid and points to the same finding version as the
  HTML; no numeric rating, person score, or unapproved relation is present;
- route state that is empty, unresolved, or unavailable has honest metadata and does not
  masquerade as a rich result;
- correction/right-of-reply history is linked when public-safe and append-only;
- the static route manifest, sitemap/robots policy required by DP-401, and canonical
  links do not expose draft, held, private, or stale routes;
- `/studio/**`, demo-only routes, and private operational pages are `noindex` and absent
  from public sitemap/feed output;
- `llms.txt` and OpenAPI links remain versioned and valid under DP-403/DP-404.

No SEO tactic may add hidden text, keyword stuffing, fake ratings, person ranking, or
private content.

### Neutrality and safety audit

The acceptance matrix must include a rendered-output inspection for:

- no person/party truth, reliability, ideology, competence, or political score;
- no ranking or recommendation;
- no inference of intent from contradiction;
- no provider/model output presented as evidence or publication;
- no raw transcript, evidence body, private reply/correction, secret, or internal error;
- no simulated “AI is researching” activity without a persisted state;
- explicit `unresolved`, `needs-more-evidence`, `under-review`, `blocked`, and
  `correction` states that look intentional.

## Non-goals

- choosing a CDN, hosting vendor, domain, or analytics platform;
- a new performance-monitoring service, real-user monitoring, or ad-tracking;
- a visual redesign, new component library, or new navigation architecture;
- a chatbot, LLM, MCP server, or public submission path;
- legal/privacy policy changes not owned by M3;
- a claim that WCAG/SEO tooling alone proves editorial or publication correctness;
- adding a new framework solely to satisfy a visual benchmark;
- changing the public schema or operational pipeline from this quality ticket.

## Dependencies and gates

- **DP-405..DP-409:** real public routes and states;
- **DP-425:** consolidated v4 tokens/components, including focus, status, and motion;
- **DP-401:** static/read adapter and hosting proof;
- **DP-402..DP-404:** HTTP, OpenAPI, and discovery metadata;
- **DP-105:** public contract and fail-closed data boundary;
- **ADR 0001/0002:** projection-only public reads, no LLM request path.

## Traceability & constraints

- **Traces to:** US-36-07, AC-36.8, AC-36.10 and the acceptance criteria of every
  page-owner ticket in the v4 implementation map.
- **Constraints:** WCAG 2.2 AA target, static-first public request path, honest metadata,
  no private/raw leakage, no quality claim based on automated tooling alone.

## Acceptance criteria

- [ ] `AC-410.1`: Given the five public templates and their populated, empty, loading,
  unresolved, blocked, correction, and error states, when the accessibility matrix runs,
  then all required keyboard, focus, semantic, contrast, zoom, touch, and reduced-motion
  checks pass on phone and desktop.
- [ ] `AC-410.2`: Given a user who cannot perceive color or uses a screen reader, when
  they inspect any finding/relation state, then the same meaning and action are available
  through text and semantics.
- [ ] `AC-410.3`: Given a cold static preview and MiniPC mirror, when the performance
  matrix runs, then LCP, CLS, INP, initial JavaScript, media layout, and no-network/LLM
  checks meet the stated budgets or have a recorded, separately ticketed exception.
- [ ] `AC-410.4`: Given providers are offline, when each public route is loaded and
  interacted with, then existing public records remain available and no provider/LLM
  request or fabricated fallback appears.
- [ ] `AC-410.5`: Given each public route, when metadata/JSON-LD/canonical/sitemap
  output is inspected, then it is honest, versioned, and points to the same public
  finding version; Studio/demo/private routes are excluded.
- [ ] `AC-410.6`: Given a correction, reply, relation, or stale projection, when the
  route is rendered, then history/version semantics remain visible and the route fails
  closed when required provenance is absent.
- [ ] `AC-410.7`: Given rendered HTML, client assets, and accessibility tree snapshots,
  when scanned, then no raw/private content, score, ranking, intent inference, secret, or
  fake activity is present.
- [ ] `AC-410.8`: Given the collision/dependency audit runs, then DP-410 remains a
  cross-surface quality gate and does not take ownership of routes, schema, API, or
  design-system decisions owned by other tickets.

## Validation / proof

The implementation receipt must include the standard repository checks:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run build
cd .. && git diff --check
```

Then attach a route/state matrix with, for each route, the fixture/projection fingerprint,
viewport, browser/assistive-technology path, automated accessibility result, manual
keyboard/zoom check, performance measurements, metadata/canonical result, and the
neutrality/private-content inspection. Use a local checker such as axe or pa11y when
available; a new contributor-only checker is allowed only if pinned and does not add
runtime infrastructure. Manual checks remain required for screen-reader semantics and
meaningful focus order.

Run a collision/dependency audit that parses ticket headers, the PLAN graph, route owners,
schema owners, and public-contract references. It must report zero duplicate IDs, zero
unresolved hard gates hidden behind DONE, and zero dependency cycles.

Runtime completion requires the matrix against the MiniPC deployment mirror, not only a
Mac static build. Record the deployment mirror commit/fingerprint, route responses,
performance profile, accessibility evidence, and provider-offline result. Any route not
exercised remains `PENDING`, not passed.

## Documentation, data, and migration impact

- document the quality matrix and exceptions in the relevant ticket/ADR only after the
  gate result is reproducible;
- update DP-401 hosting metadata and DP-404 discovery links when the canonical route
  manifest changes;
- no database migration is introduced;
- no new infrastructure is introduced by default;
- do not edit `PLAN.md`.

## Completion receipt

Local cross-surface automation started 2026-10-05. `web/scripts/check-public-quality.mjs`
inspects the actual static build rather than source templates: the current demo matrix has
32 rendered HTML pages, each with `lang=it`, description, canonical path, main landmark,
skip link and exactly one `h1`; it scans rendered HTML for private/provider/score markers and
client JavaScript for database/provider runtime markers. All current JavaScript assets are
under the 120 KiB compressed budget; the largest demo-build asset is 65,821 bytes gzip.
The ordinary public build emits no `/studio/**` routes or Studio fixture markers at all; an
explicit Studio fixture build remains `noindex,nofollow`. Demo-projection public routes are
also `noindex,nofollow`, while production public layouts emit `index,follow`. The quality
checker now requires exactly one `main` landmark per rendered page, preventing nested-main
regressions. Astro check, design check, deterministic search check, static build and the
quality checker pass locally.

`web/scripts/check-browser-qa.mjs` adds rendered-browser evidence without treating it as a
screen-reader substitute. On Explore it verifies the accessibility-tree searchbox,
radiogroup and filter button; keyboard selection/focus and dialog Escape/focus restoration;
empty and overlong-query announcements; reduced-motion behavior; 375 px mobile reflow and a
640 px 200%-equivalent reflow viewport with no horizontal page overflow and a 44 px filter
target. It then scans the accessibility trees of all 19 canonical non-legacy demo routes for
private/provider/score markers and records zero external requests across the run.

This is partial evidence only. AC-410.1/.2 still require the manual keyboard, focus, zoom,
touch, contrast and assistive-technology matrix; AC-410.3 still needs cold-browser LCP/CLS/INP
on the representative mobile profile and MiniPC mirror; AC-410.4..7 require the full real-route
state matrix and deployed inspection. Dependency owners DP-409/DP-429 and the remaining public
surface gates stay authoritative.

# DP-422 — Public Product Architecture v3 route/template migration

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-405, DP-406, DP-407, DP-408, DP-409, DP-426, DP-427, DP-428, DP-429

## Problem

The repository still contains legacy public route/vocabulary families from the pre-v3
product (`Fact-check`, `Record`, `ContentAudit`, `Compare`). The redesigned page
owners can land independently, but without one cutover ticket the site can ship duplicate
URLs, inconsistent canonical metadata, stale navigation or broken deep links.

## Outcome

Integrate and cut over the real public frontend from the legacy Fact-check / Record /
ContentAudit / Compare route vocabulary to the canonical statement-centered architecture
in `docs/35-public-product-architecture-v3.md`. Page implementation lives in the
page-owner tickets; DP-422 owns deterministic canonical routing, redirects, integration
and final route-set verification without weakening the fail-closed public projection boundary.

## Canonical public templates

1. Home — `/`
2. Explore — `/esplora/`
3. Statement — `/dichiarazioni/{slug}/`
4. Person archive — `/persone/{slug}/`
5. Topic dossier — `/temi/{slug}/`
6. Content — `/contenuti/{slug}/`
7. Trace — `/tracce/{id}/`
8. Method — `/metodo/`
9. shared utility-document grammar for `/correzioni/`, `/dati/` and `/progetto/`

`/contribuisci/` remains gated by DP-508 and the relevant legal/intake policy closure.

The maintained visual references are the nine mockups in `prototypes/final-hybrid/`.

## Scope

- replace public-facing `Fact-check`, `Record`, `ContentAudit` and `Compare` wording with
  the v3 vocabulary while keeping internal/API names where they are contractual;
- integrate the distinct Person and Topic page jobs delivered by DP-405/DP-406;
- make the DP-427 Statement route the canonical shareable object;
- integrate the DP-407 Content template for timed and written sources;
- integrate the DP-408 chronology-first Trace route;
- integrate the DP-426 Home/shell, DP-429 Explore, and DP-428 Method/utility routes;
- add canonical URLs and legacy redirects only when identifier mapping is deterministic;
- preserve stable machine IDs in the public contract even when human URLs use slugs.

## Dependencies and sequencing

- page ownership remains with DP-405..DP-409 and DP-426..DP-429;
- DP-425 owns the v4 visual/component system;
- DP-401 owns the static hosting/deploy contract;
- DP-402/DP-403 own public API/resource contracts;
- this ticket runs after page owners so redirects/canonical integration are proved against
  real targets, not placeholders.

## Traceability & constraints

- **Traces to:** DEC-36-03, DEC-36-06, AC-36.6, AC-36.9, AC-36.10 and the canonical route
  map in `docs/35-public-product-architecture-v3.md`.
- **Constraints:** no duplicate canonical public objects; no unsafe best-effort redirects;
  public navigation stays minimal; projection-only reads; no provider/LLM request path.

## Acceptance criteria

- [ ] `AC-422.1` The real public route set contains all canonical v3 primary templates and
  no new public template without a distinct page job.
- [ ] `AC-422.2` Legacy public URLs resolve through deterministic canonical redirects (or
  remain explicit aliases until such redirects are safe); no content becomes unreachable.
- [ ] `AC-422.3` Public navigation is `Esplora`, `Metodo`, and search; Person/Topic/Content/
  Trace remain contextual result/entity types rather than permanent nav clutter.
- [ ] `AC-422.4` Person and Topic pages have visibly different information architectures.
- [ ] `AC-422.5` Content supports both timed media and written locators without fabricating
  timestamps.
- [ ] `AC-422.6` Statement and Trace preserve source links, time, version/correction history
  and the no-intent-inference rule.
- [ ] `AC-422.7` Public pages continue to consume only the approved fail-closed projection;
  no LLM/provider call appears in a public request path.
- [ ] `AC-422.8` Desktop and mobile QA match the selected v4 design contract and the
  maintained `prototypes/final-hybrid/` page families.
- [ ] `AC-422.9` Astro check/build, Python boundary tests and legacy-route/canonical-route
  tests pass from a clean clone.

## Non-goals

- login, follows, bookmarks, notifications or personalized feeds;
- popularity/ranking dashboards;
- public Studio/corpus surfaces;
- a first-class Organization page before a concrete repeated public user job exists;
- launching public intake before DP-508 and legal gates close.

## Validation / proof

- enumerate the built route set and verify every canonical v3 route family is present;
- verify every legacy public URL either redirects deterministically or remains an explicit
  documented compatibility alias with canonical metadata;
- crawl internal links and report zero broken canonical destinations;
- verify sitemap/canonical/robots output contains no private/Studio/demo route;
- run `cd web && npm run check && npm run build`;
- run public projection/boundary tests and `git diff --check`;
- capture representative redirect/canonical receipts from the MiniPC deployment mirror.

## Documentation, data, and migration impact

Update public-route documentation, redirect/canonical policy and the final-hybrid route
mapping. This ticket does not change the operational schema; identifier migrations remain
owned by their domain/public-contract tickets.

## Completion receipt

Pending all page-owner tickets and integration proof.

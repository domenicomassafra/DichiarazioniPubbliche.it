# DP-422 — Public Product Architecture v3 route/template migration

Status: IN PROGRESS
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

- [x] `AC-422.1` The real public route set contains all canonical v3 primary templates and
  no new public template without a distinct page job.
- [x] `AC-422.2` Legacy public URLs resolve through deterministic canonical redirects (or
  remain explicit aliases until such redirects are safe); no content becomes unreachable.
- [x] `AC-422.3` Public navigation is `Esplora`, `Metodo`, and search; Person/Topic/Content/
  Trace remain contextual result/entity types rather than permanent nav clutter.
- [x] `AC-422.4` Person and Topic pages have visibly different information architectures.
- [x] `AC-422.5` Content supports both timed media and written locators without fabricating
  timestamps.
- [x] `AC-422.6` Statement and Trace preserve source links, time, version/correction history
  and the no-intent-inference rule.
- [x] `AC-422.7` Public pages continue to consume only the approved fail-closed projection;
  no LLM/provider call appears in a public request path.
- [ ] `AC-422.8` Desktop and mobile QA match the selected v4 design contract and the
  maintained `prototypes/final-hybrid/` page families.
- [x] `AC-422.9` Astro check/build, Python boundary tests and legacy-route/canonical-route
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

Local route integration is now executable. `web/scripts/check-route-contract.mjs` enumerates
the built site and requires every v3 family (`/`, `/esplora/`, `/dichiarazioni/`, `/persone/`,
`/temi/`, `/contenuti/`, `/tracce/`, `/metodo/` plus utility documents). The current demo build
passes with 32 HTML routes. Sixteen legacy Fact-check/Record/Content/Compare URLs remain explicit
compatibility aliases for now; each must emit a deterministic canonical target in the v3 family,
and every target must exist in the same build. The checker also crawls 443 same-site HTML links
with zero broken static destinations. The ordinary public build now materializes zero
`/studio/**` routes; the four private Studio workspaces exist only in the explicit Studio
fixture build. SiteHeader exposes only Esplora, Metodo and search as permanent public navigation.

The static quality/client scan finds no database/provider runtime marker in the public request
path. The route checker now enforces the distinct Person chronology/no-person-score IA versus
the Topic dossier/context IA; local Chrome screenshots visually confirm the two layouts differ.
Content locator acceptance is exercised twice: the ordinary demo build has three timed-locator
pages, while the DP-407 fixture build has two timed pages plus one written `Passaggio 420–612`
page. Written selection is labeled `Passaggio selezionato` and the checker rejects a fabricated
clock timestamp. Statement pages must expose the source, version state and `#storia`; Trace pages
must expose chronology, original-source links and the explicit no-intent boundary. These checks
close AC-422.4 through AC-422.6 locally. The full selected-v4 desktop/mobile visual comparison
remains open under AC-422.8; DP-408, DP-409 and DP-429 remain completion gates.

Clean-clone acceptance was rerun on 2026-10-06 from a fresh clone of `HEAD` with no dirty files:
`npm ci`, `astro check` (0 errors/warnings/hints), the explicit demo build and
`check-route-contract.mjs` all pass. The route receipt is 32 HTML routes, 16 compatibility
aliases, 443 same-site links, three timed locator pages and zero written-locator pages for that
fixture. The projection/schema/API boundary set also passes **153/153** tests from the clean
clone. This closes AC-422.9 independently of the shared dirty integration tree. AC-422.8 remains
open for the selected-v4 desktop/mobile visual comparison; DP-408, DP-409 and DP-429 remain
completion gates.

The final approved-empty production shape is now covered explicitly as well. Against fingerprint
`501348d9638e...`, the route checker expects exactly the six static canonical pages and rejects any
fabricated Statement/Person/Topic/Content/Trace or legacy alias when the search index has zero
records. The same checker retains the full populated-fixture assertions above. This is machine
route-contract evidence only; it does not close AC-422.8's manual comparison with the selected v4
visual references.

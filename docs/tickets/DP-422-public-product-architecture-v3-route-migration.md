# DP-422 — Public Product Architecture v3 route/template migration

Status: READY
Milestone: M4 — Public product, API, and hosting
Depends on: DP-105, DP-412

## Goal

Move the real public frontend from the legacy Fact-check / Record / ContentAudit /
Compare route vocabulary to the canonical statement-centered architecture in
`docs/35-public-product-architecture-v3.md` without weakening the fail-closed public
projection boundary.

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

## Required migration

- replace public-facing `Fact-check`, `Record`, `ContentAudit` and `Compare` wording with
  the v3 vocabulary while keeping internal/API names where they are contractual;
- implement the distinct Person and Topic page jobs rather than a single generic Record
  template;
- make Statement the canonical shareable object;
- support one Content template for timed and written sources without fake timestamps;
- implement Trace as chronology-first reviewed relations, with side-by-side comparison
  only as a secondary interaction;
- keep Home, Explore and Method visually within the frozen design system;
- add Corrections, Data & API and Project as restrained utility documents;
- add canonical URLs and legacy redirects only when identifier mapping is deterministic;
- preserve stable machine IDs in the public contract even when human URLs use slugs.

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
- [ ] `AC-422.8` Desktop and mobile QA match the frozen design system and the permanent
  `prototypes/final-hybrid/` page families.
- [ ] `AC-422.9` Astro check/build, Python boundary tests and legacy-route/canonical-route
  tests pass from a clean clone.

## Non-goals

- login, follows, bookmarks, notifications or personalized feeds;
- popularity/ranking dashboards;
- public Studio/corpus surfaces;
- a first-class Organization page before a concrete repeated public user job exists;
- launching public intake before DP-508 and legal gates close.

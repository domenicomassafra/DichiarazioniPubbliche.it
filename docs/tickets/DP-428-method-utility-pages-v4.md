# DP-428 — Method + trust/utility document pages v4

Status: DONE
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-425

## Problem

Method exists, but Corrections, Data & API and Project are still missing as real public routes. Trust content should be easy to find without becoming a second product shell or multiplying bespoke page templates.

## Outcome

Implement Method plus one shared Utility document grammar for Corrections, Data & API and Project, with Privacy/Accessibility able to reuse the same grammar when their policy content is ready.

## Scope

- Method anchored sections for publication, provenance, findings, uncertainty, corrections/right of reply, longitudinal relations, AI boundaries and data/open source;
- `/correzioni/` chronological append-only public log;
- `/dati/` human entry point for public machine-readable resources/licensing;
- `/progetto/` mission, governance, repository, independence/funding disclosure, responsibility and contact;
- one shared responsive document grammar and contextual links back into live records.

## Non-goals

- generic company marketing pages;
- a developer dashboard;
- public intake forms;
- a blog/newsroom;
- changing editorial/legal policy itself.

## Traceability & constraints

- **Traces to:** US-36-06, DEC-36-03, AC-36.7, AC-36.10, AC-422.1.
- **Constraints:** utility pages remain secondary navigation, document-like, source-linked and compatible with static/projection-only hosting.

## Acceptance criteria

- [ ] Method, Corrections, Data & API and Project routes exist with distinct content jobs;
- [ ] all utility routes reuse one document grammar rather than bespoke page systems;
- [ ] Corrections is chronological/version-aware and not a news feed;
- [ ] Data & API links to actual public contracts/resources and does not expose operational internals;
- [ ] Project states governance/responsibility/open-source facts without fabricated claims;
- [ ] mobile/keyboard/zoom behavior meets the shared design contract.

## Validation / proof

`cd web && npm run check && npm run build`; route screenshots at desktop/phone; link/metadata/canonical checks; `git diff --check`.

## Documentation, data, and migration impact

Adds canonical trust/utility public routes. No data migration unless existing public correction projection needs an already-approved read adapter.

## Completion receipt

- Added one shared `UtilityDocument.astro` grammar and reused it for `/metodo/`,
  `/correzioni/`, `/dati/`, and `/progetto/`; no page-specific visual system or token set
  was introduced.
- Method now documents publication gates, provenance/source paths, statement-local
  findings, uncertainty, append-only corrections/replies, reviewed longitudinal
  relations, AI/automation boundaries, and public data/code paths.
- Corrections reads only the approved public projection, sorts projected correction
  records chronologically, links back to canonical Statement routes, and has a deliberate
  empty-snapshot state rather than a fake feed.
- Data & API links only to implemented public API resources (`openapi.json`, schema,
  findings, index) and states the code/content-rights boundary.
- Project uses repository facts already present in the repo (canonical GitHub remote and
  Apache-2.0 code license) and explicitly leaves unresolved responsibility/funding/contact
  disclosures unresolved instead of inventing them.
- Visual receipts: `prototypes/v4-implementation/dp428/` contains desktop and phone
  screenshots for all four routes; representative desktop/mobile receipts were manually
  inspected.
- Validation: `npm run check:design` PASS; `npm run check` 0 errors/warnings/hints;
  `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build` PASS with all four
  routes emitted; `git diff --check` PASS.

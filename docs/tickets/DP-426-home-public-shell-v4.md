# DP-426 — Home + public shell v4

Status: DONE
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-425

## Problem

Home and the global shell are the first proof of the brand and discovery model. The current surface is coherent but must be rebuilt against the selected v4 direction, canonical Segno mark, one primary search action and v3 trust/navigation hierarchy.

## Outcome

Implement the redesigned public header/footer and Home as a complete tracer-bullet slice using only approved public projection data and the shared v2 design-system contract.

## Scope

- global public header with canonical brand mark, `Esplora`, `Metodo`, search and minimal trust/footer navigation;
- first viewport purpose + universal search;
- restrained recent-statement stream;
- one strong original-content/source example;
- short method/trust path without marketing-feature clutter;
- intentional desktop/phone composition and real empty/unavailable states.

## Non-goals

- signup/login CTA;
- testimonials, KPI walls, popular people/topics, trending feeds or newsletter wall;
- new route families;
- live provider/LLM request path.

## Traceability & constraints

- **Traces to:** US-36-01, US-36-05, US-36-06, DEC-36-02, DEC-36-07, AC-36.1, AC-36.6, AC-36.10.
- **Constraints:** one primary conversion, no fabricated proof, global nav remains minimal, projection-only reads.

## Acceptance criteria

- [ ] first viewport communicates product purpose and exposes search as the dominant action;
- [ ] the header mark follows the canonical Segno geometry contract;
- [ ] recent statements and the featured source use real public object grammar and canonical routes;
- [ ] footer exposes trust/utility links without turning them into primary-nav clutter;
- [ ] mobile is intentionally recomposed with no horizontal overflow and usable touch targets;
- [ ] provider-offline mode does not change the page's usefulness.

## Validation / proof

`cd web && npm run check && npm run build`; desktop + phone screenshots; keyboard/focus and 200% zoom proof; `git diff --check`; inspect network/runtime path for zero provider/LLM calls.

## Documentation, data, and migration impact

Update Home/public-shell mockup receipt and affected navigation docs. No data migration.

## Completion receipt

- Rebuilt the public shell around the v3 navigation hierarchy: cobalt-square Segno mark,
  `Esplora`, `Metodo`, compact `Cerca`, and a footer limited to Method, Corrections,
  Data & API, Project and the confirmed canonical GitHub repository. The permanent
  `Fact-check` nav item is removed; Studio navigation remains separate.
- Rebuilt Home against Ledger Spine: one product-purpose statement, one dominant public
  search stage, recent Statement rows, one original-source example, and a restrained
  trust path. The old numbered/poster composition and three-column marketing path grid
  are no longer used by Home.
- Home Statement rows now point to the canonical `/dichiarazioni/` route and suppress raw
  `claim_type` taxonomy labels in the public recent stream.
- The source example links to the actual original source already in the public projection;
  it no longer exposes the internal `ContentAudit` label or invents a Content route before
  DP-407 is ready.
- Search remains a real GET form over already-published records; its submit action is
  explicit text and its focus-within state uses the existing Segno/focus grammar.
- Added a deliberate no-record Home state. Public usefulness remains projection-only and
  no provider/LLM request path was added.
- Visual receipts: `prototypes/v4-implementation/dp426/home-desktop.png` and
  `home-mobile.png`; desktop and narrow/mobile compositions were manually inspected.
- Validation: `npm run check:design` PASS; `npm run check` 0 errors/warnings/hints;
  explicit demo-projection static build PASS; `git diff --check` PASS.

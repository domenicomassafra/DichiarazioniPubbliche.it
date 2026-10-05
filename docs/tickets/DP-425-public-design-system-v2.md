# DP-425 — Public design system v2 + component contract

Status: DONE
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-424

## Problem

DP-412 froze a solid visual foundation, but the v4 redesign will change composition, public component anatomy and responsive behavior. Implementation should not copy page-specific CSS from visual prototypes or let each route invent its own states.

## Outcome

Translate the selected v4 direction into a reusable, agent-readable Public design-system/component update while preserving the existing brand thesis and token discipline.

## Scope

- reconcile selected v4 composition with existing tokens before adding any new token;
- define the three composition archetypes: Entry/index, Record, Trust document;
- define component anatomy and state contracts for public header/search, statement row, finding word+mark, source/evidence item, Segno selection, chronology/tape, disclosure, filter sheet and utility document;
- define phone/desktop recomposition rules and all interactive states;
- update the visual rubric/proof expectations used by page implementation tickets.

## Non-goals

- a second visual brand;
- route implementation;
- Studio density redesign;
- dependency/library replacement without measured need;
- ad-hoc per-page token values.

## Dependencies and sequencing

Blocked by the selected redesign direction. Page implementation may not call itself visually complete until this contract lands.

## Traceability & constraints

- **Traces to:** DEC-36-02, DEC-36-03, DEC-36-08, AC-36.5, AC-36.8, AC-422.8.
- **Constraints:** semantic tokens, accessible keyboard/focus states, reduced motion, metadata floor, no shadow/gradient, one Segno grammar, public spacious density.

## Acceptance criteria

- [ ] every v4 visual rule needed by the key screens is represented by a reusable token/layout/component contract;
- [ ] no page needs a private design vocabulary to reproduce the selected direction;
- [ ] default/hover/focus-visible/active/selected/disabled/loading/empty/error states are defined where relevant;
- [ ] phone and desktop composition rules are explicit and preserve DOM/reading order;
- [ ] the contract can reproduce the selected visual proofs without arbitrary hard-coded values.

## Validation / proof

Run the design-system checks plus `cd web && npm run check`, `npm run build`, and `git diff --check` when implementation files change. Attach a component inventory and screenshot proof against the selected v4 key screens.

## Documentation, data, and migration impact

May update `DESIGN.md`/consumable design-system docs only where the selected v4 direction genuinely supersedes the existing contract. No data migration.

## Completion receipt

- Frozen the Public v4 composition/component contract in
  `docs/ux/design-system-v2.md`, while keeping the DP-412/v1 token, primitive,
  accessibility, contrast, motion and Studio contracts authoritative.
- Reconciled Ledger Spine with the existing system with **zero new tokens**. The Home
  search Segno is now focus-within only; Statement/Trace keep it only for actual current
  selection/open state.
- Defined Entry/index, Record and Trust-document archetypes plus reusable contracts for
  PublicHeader, SearchStage, StatementRow, FindingSummary, SourceEvidenceItem,
  SourcePath, ChronologyIndex, EvidenceTape, Disclosure, FilterSheet and UtilityDocument.
- Defined desktop/phone DOM-order rules and the relevant default, hover, focus-visible,
  active, selected/open, disabled, loading, empty and error states.
- Attached the component inventory and mapped it to the DP-424 Home/Statement/Trace
  desktop/phone visual proofs under `prototypes/v4-ledger-spine/`.
- Validation: `npm run check:design` PASS; `npm run check` PASS with 0 errors/warnings;
  the fail-closed build correctly refused to run without a public projection, then
  `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build` PASS for the explicit
  local demo path; staged `git diff --check` PASS.

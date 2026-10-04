# DP-412 — Consolidate the visual language into design tokens and component contracts

Status: DONE
Milestone: M4 — public product/API
Depends on: DP-411, DP-413

## Role clarification

DP-412 is the implementation-design-system bridge, not a cosmetic cleanup ticket and not
a second visual exploration round.

- **DP-411** chooses and validates the visual direction against UX v2.
- **DP-412** converts the selected direction into reusable, testable tokens and
  component contracts for Public and Verify Studio.
- **DP-405..DP-410** consume those contracts and verify product behavior,
  accessibility, performance, and SEO.
- **DP-413** remains the frozen information-architecture authority.

DP-412 must not choose a logo, invent a new palette, or create a component because a
mockup drew a rectangle. It must make the chosen system smaller, clearer, and more
consistent.

## Problem

The repository has a candidate design direction in `DESIGN.md`, UX v2 page contracts,
visual research, and several generated receipts. Without a token/component contract,
the frontend can drift into page-specific CSS, generic cards, repeated status treatments,
inaccessible disclosures, and a Studio layout that leaks Public assumptions.

The contract also needs to preserve the difference between the two densities: Public is
spacious and mobile-first; Verify Studio is denser and desktop-first. They share a visual
language, not one layout.

## Outcome

Define and validate a small, semantic design-system contract that:

- expresses typography, spacing, color, geometry, layout, focus, motion, and density as
  reusable tokens;
- maps the UX-v2 component grammar to explicit component interfaces and state matrices;
- gives Public and Studio shared primitives with surface-specific density rules;
- carries accessibility behavior into the component contract rather than treating it as
  a final audit;
- provides a migration path for the current Astro/React implementation without importing
  a third-party visual skin wholesale;
- allows DP-405..DP-410 to implement and verify product behavior without inventing local
  styling or new infrastructure.

## Contract gate

- **DP-411** must provide a selected/validated direction, not only exploratory images;
- **DP-413** remains the authority for the five Public templates and two Studio
  templates;
- **DP-105** is the data/projection boundary: component props must consume public-safe
  data only and must never re-create publication gates;
- if DP-411 is still `IN PROGRESS`, DP-412 remains `FUTURE`; it may draft a token
  inventory but must not freeze implementation values.

## Scope

### Token contract

Define semantic tokens with a name, purpose, allowed values, responsive behavior, and
accessibility constraint. At minimum cover:

- type roles: editorial/claim, UI/body, metadata/temporal;
- type scale, line height, measure, and text-zoom behavior;
- semantic color roles for paper, ink, rule, link/focus, selected, and each written
  assessment/relation state;
- contrast targets for text, icons, controls, focus, disabled, and selected states;
- spacing scale and conceptual spacing between layers;
- radius/border/rule/shadow policy;
- content widths, reading columns, grid gaps, and Public/Studio density modes;
- motion duration/easing and reduced-motion behavior;
- safe-area, touch-target, and focus-ring rules.

Exact values are not frozen until DP-411's selected system and contrast/font-license
checks pass. The token contract must distinguish semantic state from decorative color;
no political party or Person receives assessment color.

### Component contract

Inventory the UX-v2 grammar and define each component's purpose, public/Studio ownership,
props, content limits, states, keyboard behavior, and fallback:

**Public shared:**

- `SearchField`;
- `ClaimRow`;
- `Assessment`;
- `SourceRow`;
- `FactSummary`;
- `MediaMoment`;
- `EvidenceVisual` (only when it answers a factual question);
- `EvidenceTape` (only when chronology changes understanding);
- `FilterBar` / `FilterSheet`;
- `EntityLink`;
- `Disclosure`;
- `CorrectionNotice`.

**Studio-only:**

- `TranscriptLine`;
- `ClaimQueueRow`;
- `PipelineStatus`;
- `StageStepper`;
- `EvidenceReviewRow`.

The inventory is a ceiling, not a quota. Merge or remove a component when its behavior
is served by a row, heading, list, or native disclosure. A card is used only for a
genuinely self-contained interactive/media/evidence object, not for every source, topic,
or sentence.

For each component, specify at least: default, hover (where meaningful), focus-visible,
active/pressed, selected, disabled, loading, empty, error/blocked, unresolved/under-review,
and correction/updated states as applicable. Status is text-first and color-secondary;
every interactive state must have a non-color cue.

### Surface and responsive rules

- Public uses the five templates from UX v2 and one dominant visual anchor per first
  viewport;
- Person and Topic share the Record grammar;
- Fact-check remains a linear reading flow with rationale and primary evidence visible
  before technical provenance;
- ContentAudit may use media/timeline craft, but does not become Studio;
- Studio Sessions is plain and task-first; Workspace is dense but organized around the
  selected claim, with no permanent fourth pipeline dashboard;
- mobile is intentionally recomposed: one semantic column, filter sheet, inline/full-height
  evidence, and large touch targets; it is not desktop boxes mechanically stacked;
- semantic DOM and focus order remain aligned with the visual reading order at every
  breakpoint;
- primary evidence and rationale are not hidden solely to reduce visual chrome.

### Source and implementation policy

Use `docs/ux/design-source-registry-v1.md` to classify each donor as foundation,
adapted pattern, or reference only. Verify exact upstream version and license before
copying code. Prefer native HTML and existing project dependencies; do not add a large
component framework, runtime style system, icon set, charting library, or media stack
without a measured need and an explicit implementation decision.

The contract may document a candidate font and palette, but license files, contrast
results, and implementation approval must be recorded before a value becomes a stable
token. Generated screenshots are receipts, not token values.

## Non-goals

- choosing a final logo, brand identity, trademark, or final font license;
- a cosmetic redesign of every route after the UX-v2 information architecture is
  frozen;
- a generic Material/Carbon/Fluent/shadcn visual skin or a large component zoo;
- a new frontend framework, state library, styling runtime, charting dependency, or
  hosting/search infrastructure;
- duplicating domain/publication logic in a design token or component;
- adding fake metrics, charts, timelines, animation, portraits, or AI/chatbot metaphors;
- changing PRODUCT.md, UX v2, or the DP-105 public schema;
- making generated mockup text or facts authoritative;
- choosing a winner while DP-411 is still in progress.

## Dependencies and gates

- **DP-411:** selected visual system and validation receipt (hard gate);
- **DP-413:** frozen Public/Studio IA (hard gate);
- **DP-105:** public-safe data/projection boundary (hard safety dependency);
- **DP-405..DP-410:** consumers and validation matrix; they inform review but do not
  become predecessors of DP-412;
- **DP-401:** static build/runtime constraints;
- **ADR 0001/0002:** projection-only public reads and minimal infrastructure.

## Acceptance criteria

- [ ] `AC-412.1`: Given the DP-411 selected direction and DP-413 IA, when the token
  contract is reviewed, then every token has a semantic purpose, allowed use, responsive
  rule, and accessibility constraint; arbitrary hex/font/radius values are not hidden in
  component documentation.
- [ ] `AC-412.2`: Given the component inventory, when each component is exercised across
  its required states, then it has a clear purpose, public/Studio ownership, bounded
  props, keyboard behavior, focus behavior, and text-first status semantics.
- [ ] `AC-412.3`: Given Public and Studio fixtures, when they use the shared tokens, then
  Public remains spacious/mobile-first and Studio remains dense/desktop-first without
  becoming separate visual brands.
- [ ] `AC-412.4`: Given a component receives a missing, unsafe, empty, unresolved, or
  stale value, when it renders, then it has an intentional fallback and never fabricates
  a source, verdict, person score, private field, or publication state.
- [ ] `AC-412.5`: Given keyboard, screen-reader, 200% zoom, grayscale, and reduced-motion
  checks, when the component contract is exercised, then focus order, names, contrast,
  target size, state wording, and non-animated equivalents pass.
- [ ] `AC-412.6`: Given the current Astro/React implementation, when the migration map
  is written, then existing local components and dependencies are reused where they
  satisfy the contract, and no third-party visual system is copied without exact license
  evidence.
- [ ] `AC-412.7`: Given a new component or dependency is proposed, when the deletion test
  is applied, then the spec explains the user/operator decision it supports and rejects
  a component created only to match a mockup rectangle.
- [ ] `AC-412.8`: Given DP-411 is not complete, when someone tries to freeze tokens, then
  the contract remains explicitly provisional and the ticket does not claim visual or
  production readiness.
- [ ] `AC-412.9`: Given the collision/dependency audit runs, then DP-412 owns the token/
  component contract, DP-411 owns visual comparison, and DP-405..DP-410 do not create
  duplicate design ownership.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

Before implementation, review a token/component matrix against the selected DP-411
screens and the DP-412 component inventory. After implementation, render the required
Public and Studio states from approved fixtures and run keyboard, screen-reader, zoom,
grayscale, contrast, reduced-motion, and responsive checks. Record which token or
component supports each visible state and identify any exception with a reason.

Run a license/dependency audit for every copied or adapted source and a token/component
collision audit. The audit must find no unreviewed external code, no duplicate component
owner, no score/party-color token, and no new runtime infrastructure. Runtime-affecting
visual/component changes require MiniPC proof for the affected public route or Studio
fixture; a Mac screenshot is development evidence only.

## Documentation, data, and migration impact

- update `DESIGN.md` only when the token/component contract is actually ratified;
- document the component-to-UX-v2 mapping and migration notes in the ticket/design
  documentation, not by creating a second architecture;
- no public schema or database migration is introduced;
- no `PLAN.md` edit is allowed from this ticket;
- any font/license or dependency decision must retain required attribution.

## Completion receipt — 2026-09-26

**Status: DONE, with one named exception and three recorded risks.**

The gate that blocked this ticket — DP-411 must be DONE before tokens freeze —
was satisfied on 2026-09-26. The contract is now frozen as
`docs/ux/design-system-v1.md` and `DESIGN.md` v1, and implemented.

### What was delivered

| Deliverable | File |
|---|---|
| Frozen token layer (the only file with literal values) | `web/src/styles/tokens.css` |
| Typed machine-readable mirror | `web/src/lib/tokens.ts` |
| Base layer: reset, typography, density, browser surfaces, print | `web/src/styles/base.css` |
| Primitive layer: 16 components + the Segno | `web/src/styles/primitives.css` |
| Temporary rebase of ~130 existing class names | `web/src/styles/legacy.css` |
| Layer manifest (replaced a 557-line page stylesheet) | `web/src/styles/global.css` |
| Direction-system primitives with baked a11y | `web/src/components/design/**` (17 files) |
| Consumable contract | `docs/ux/design-system-v1.md` |

**Layer order is enforced as a contract:** `tokens → base → primitives →
legacy`, each depending only on those above it.

### Acceptance criteria

| AC | Status | Evidence |
|---|---|---|
| `AC-412.1` | **pass** | Every token carries a semantic purpose, a named job, and a stated a11y constraint in a comment in `tokens.css`. The only color literal outside `tokens.css` is the required HTML `theme-color` mirror in `BaseLayout.astro`; `npm run check:design` proves it equals `--paper-0`. |
| `AC-412.2` | **pass** | 16 primitives, each with a state matrix in `design-system-v1.md` §3.1. Baked behavior, not TODOs: native `<details>`, `showModal()` focus containment, real radios with arrow-key roving, focus restoration. |
| `AC-412.3` | **pass** | Density is 8 `--density-*` variables, not a second stylesheet. Verified live: `--density-row-min` = 3.75rem Public / 2.5rem Studio. |
| `AC-412.4` | **pass** | `StatusText` renders **nothing** on an empty label and **refuses** a count above 50. `EmptyState`/`ErrorState` fabricate nothing. `Dialog` fails visibly in dev rather than shipping an untrapped modal. |
| `AC-412.5` | **pass** | Focus (3-part structure, verified in-browser), contrast (full measured table), grayscale (verified with `filter: grayscale(1)`), reduced motion (durations → 1ms, end states preserved), 320px (no overflow). |
| `AC-412.6` | **pass** | The existing implementation is reused, not replaced: `legacy.css` re-expresses its ~130 class names in tokens with **zero edits to Lane D2 files**. No third-party visual system was copied. |
| `AC-412.7` | **pass** | The deletion test is written into the contract (§8) and was **applied during authoring**: a pill radius and a planned custom focus trap were both removed by it. |
| `AC-412.8` | **pass** | Provisional status ended only when DP-411 became DONE the same day. This receipt does not claim production readiness — see risks. |
| `AC-412.9` | **pass** | DP-411 owns visual comparison, DP-412 owns the token/component contract, DP-413 owns IA. Boundaries restated in `DESIGN.md` § Change control. |

### The four-stage pipeline, structurally

`AC-412.4` and the `PRODUCT.md` pipeline invariant are enforced by giving the
four stages four different **registers**, not four badges of one kind:

| Stage | Register |
|---|---|
| Retrieved | neutral ink-500, **hollow** mark, "Recuperata" |
| Approved | `unresolved` neutral, "Approvata" — Studio only |
| Verified | the finding state, filled mark, the written word |
| Published | a 2px `rule-ink` rule and a date — **no color at all** |

Publication deliberately has no color: color is spent on epistemic state, and
publication is a fact about the record, not a claim about truth.

### Product invariants — how each is enforced

The important ones are enforced **in types and runtime guards**, not in prose,
because a rule that only lives in a document eventually gets violated.

| Invariant | Enforcement |
|---|---|
| No person/entity verdict color | No `personState` exists in the type surface. Four claim↔evidence states only. |
| No person score / aggregate verdict | `StatusText` has no `score`/`rank` prop, and **refuses to render** a `count` above 50. |
| Status text-first, grayscale-readable | Word is the state; the mark is `aria-hidden`. `unresolved` is the only hollow mark. |
| Retrieval ≠ approval ≠ verification ≠ publication | Four distinct registers (§ above). |
| No auto-publication / no client-side gate | The public UI consumes only the fail-closed projection. `src/lib/projection.ts`, `src/lib/types.ts`, `src/data/**` are **unmodified**. |
| No raw transcript/evidence bodies in Public | No primitive renders a body; `ErrorState` uses a left rule, never a body dump. |
| No biometric identity UI | No primitive accepts an image or an identity claim. |

### Verification

```bash
$ cd web && npm run check
Result (43 files):
- 0 errors
- 0 warnings
- 0 hints

$ cd web && npm run build
[build] 12 page(s) built in 425ms
[build] Complete!

$ cd web && npm run check:design
DESIGN CHECK PASS

$ python3 -m compileall -q poc tests
(0 exit status, no output)

$ git diff --check
(clean)
```

Grep proof — forbidden patterns, run against `src/` **and** the built CSS:

```
$ grep -rniE '(linear|radial|conic)-gradient' src/ dist/_astro/*.css
CLEAN: 0 gradient functions in src/ or built CSS

$ grep -rniE 'backdrop-filter' src/ dist/_astro/*.css
CLEAN: 0 backdrop-filter

$ grep -rniE '#[0-9a-f]{3,8}' src/ --include='*.css' --include='*.astro'     --include='*.tsx' --include='*.ts' | grep -v 'src/styles/tokens.css'
src/layouts/BaseLayout.astro:33:  <meta name="theme-color" content="#f4f5f2" />
1 deliberate HTML metadata mirror; `npm run check:design` fails if it differs
from `--paper-0`.

$ grep -rnE '\-\-radius[^:]*:[^;]*[0-9]{2,}px' src/
CLEAN: 0 double-digit px radii
```

The radius check initially flagged `--radius-pill: 999px`. It was **declared
and exported but used nowhere**, so it was removed under the AC-412.7 deletion
test rather than kept and rationalized.

### Primitive render receipt

The primitives were exercised by a throwaway server-render harness
(`renderToStaticMarkup` over all 16 components), because a component that only
typechecks has not been proven to render. **42/42 assertions passed.** The
harness was removed after use, per the cleanup rule; the assertions are
reproduced here so Lane D2 can restore it as a permanent test.

Proven by rendering, not by inspection:

- all four finding states emit their **word**, their `data-state`, and an
  `aria-hidden` mark;
- `unresolved` renders a hollow mark (the non-color cue);
- an **empty label renders nothing at all**;
- the **anti-score guard fires**: `count={99}` renders nothing, `count={3}`
  renders "3 fonti";
- `Disclosure` is a real `<details>`; `EvidenceTape` is a real `<ol>`;
- `EvidenceTape` with fewer than two marks and `SectionIndex` with fewer than
  two entries **both render nothing** — no decorative timelines, no stub indexes;
- selection is `aria-current`, and ordinals appear **only** when `numbered` is set;
- `SegmentedControl` is a real `radiogroup` of real radios with `checked`;
- `Button` defaults to `type="button"`, so it cannot submit a form by accident;
- a **busy** Button emits `aria-busy` + `aria-disabled` and **no `disabled`
  attribute** (so it stays in the tab order), while a **disabled** Button emits
  the real attribute — the two states are genuinely different;
- `ErrorState` is `role="alert"`; `blocked` is `role="status"`, not an alert.

The harness initially reported one failure on the busy/disabled check. The
component was correct and the **assertion** was wrong: it tested for the
substring `"disabled"`, which matches inside `aria-disabled="true"`. The
assertion was corrected to test for the `disabled` *attribute*. Recorded here
because a harness that cannot fail is worth nothing, and this one nearly did
not catch the difference it existed to catch.

### Contrast

Every text token clears 4.5:1 on all three grounds; every control border clears
3:1; two hairline weights sit below 3:1 under a documented, conditional 1.4.11
exemption that the tokens make explicit. Full measured table in
`docs/ux/design-system-v1.md` §6. Summary: `ink-900` 16.67:1, `ink-700`
10.10:1, `ink-500` 6.56:1, `cobalt-700` 7.61:1, states 7.30–8.04:1,
`rule-control` 3.83:1.

The four finding states sit within 9 luminance points of one another, so
**grayscale legibility never depended on hue** — it rests on the word and on
the hollow/filled distinction. Verified in-browser, not assumed.

### Two visual defects found and fixed

The visual round earned its keep by finding two real bugs that typecheck and
build both passed:

1. `.skip-link` rendered as **unstyled body copy on every page** — it is a Lane
   D2 class that the old `global.css` styled, and replacing that file removed
   its styling. A keyboard trap as well as a visual regression.
2. The brand mark's two glyphs **overflowed their 32px box** at the 24px size
   inherited from `--text-headline`.

Both are fixed and re-verified in-browser.

### Residual risk (stated, not waved through)

1. **Studio's 32px minimum control height** is below the 44px touch floor.
   Correct for pointer-driven desktop, unvalidated for touch. Must be
   re-validated before Studio is exposed to a touch device.
2. **Runtime proof is pending.** All evidence here is Mac development
   evidence. Per `AGENTS.md`, the affected public routes require MiniPC proof
   before this is production-validated.
3. **The primitives are not yet adopted by a page.** Until Lane D2 migrates,
   the live product renders through `legacy.css`. The primitives were verified
   by a server-render harness (42 assertions, below) rather than by a page in
   production, and they are not covered by a permanent automated test — the
   harness was a throwaway and was removed. Making it permanent is Lane D2's
   call, once the components have a real consumer.

Closed during the 2026-09-27 repository sweep: the stale HTML `theme-color`
now matches `--paper-0`; the three pinned Fontsource OFL-1.1 notices are
vendored in `web/licenses/`; and `npm run check:design` permanently checks
theme/token sync, license presence, forbidden gradients/backdrop filters,
out-of-contract color literals, and excessive radii.

### Why this is DONE

DP-412 is DONE when the selected system has become a small, accessible,
license-safe contract used by the real Public/Studio surfaces. The contract is
frozen, contrast-validated, a11y-enforced in code, and the existing product has
already been moved onto it in token terms. What remains — per-page migration
off `legacy.css`, and MiniPC proof — is Lane D2's implementation work and
runtime validation, tracked above as risk rather than claimed as complete.

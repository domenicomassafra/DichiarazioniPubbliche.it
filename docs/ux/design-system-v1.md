# Dichiarazioni Pubbliche — Design System v1

Status: **frozen** — implementation authority for `web/`
Date: 2026-09-26
Supersedes: `DESIGN.md` v0.2 (candidate)
Owner ticket: DP-412 · Direction ticket: DP-411

This is the consumable contract. `DESIGN.md` says *what the world is*; this
file says *what every token and component is, precisely enough to build against
and review against*. A component that violates this file is wrong even if it
looks right.

`PRODUCT.md` and `docs/32-public-ux-architecture-v2.md` remain authoritative for
product truth and information architecture. This file cannot change either.

---

## 1. The frozen direction

**A civic ledger, not a dashboard.** The product is an Italian public record:
something a citizen reads and a researcher cites. It is set like a document
that a serious editorial team would publish, and it behaves like an index that
a reference work would be.

Three commitments carry the whole system:

1. **Typography is the layout engine.** An asymmetric ledger grid, a real
   serif/sans/mono voice separation, and a strict fluid type scale. Structure
   comes from type size, weight, and alignment — not from boxes, fills, or
   borders. If a page could be reconstructed by drawing rectangles, it is wrong.
2. **The Segno is the only brand gesture.** A 2px cobalt rail marking whatever
   currently holds attention. It is one geometric element doing five jobs
   (selected, focused-within, open, active moment, active rail item), so a
   reader learns it once. It is always cobalt and never a finding-state hue: a
   selection cue that borrowed verdict color would let a reader confuse
   "you are here" with a verdict.
3. **Hairline is the entire depth system.** There are no shadows. An object is
   elevated by a change of ground plus a 1px control-grade rule. Radii stay at
   0–3px because the world is printed, not plastic.

**Why this is distinctive.** The default for a fact-check product is a card grid
with colored verdict pills and a KPI strip; the default for a "modern" record
product is a dark analytics console with a shader background. Both are
rejected by the invariants in `PRODUCT.md` (no scores, no dashboards, no
government scenery) *and* by the craft floor. What remains, built honestly, is
a typography-led editorial system where the finding state is a **word** and the
brand gesture is a **rule**, not a color. That combination — Newsreader at
display scale against a cool bone ground, a single cobalt 2px rail, zero
shadows, zero gradients — is not reachable by reaching for a component library,
which is precisely why it will not decay into one.

### What was rejected, and what survives of it

| Source | Rejected | Kept |
|---|---|---|
| P3 — Quiet Research Index | The literal prototype | Interaction grammar: search, rows, evidence adjacency, progressive disclosure |
| P2 — Italian Modernist Ledger | Poster pastiche, decorative dates, geometric marks with no product meaning | Asymmetric grid, typographic identity, small cobalt gesture, deliberate date rails |
| P4 — Visual Journalism | Charts on records that do not need them, infographic walls, bespoke art direction | One evidence visual per record, and only when it answers a factual question |
| P5 — Temporal Evidence Tape | A timeline on every page, status-colored person history, thin ticks | The tape as a navigation rail, concentrated in ContentAudit, corrections, Studio |

The earlier "P3 baseline → P2 identity → P4/P5 modules" hierarchy is retained
and now has implementation force: P3 governs interaction, P2 governs structure,
and P4/P5 are conditional modules with named mounting points.

---

## 2. Token inventory

The token layer is `web/src/styles/tokens.css`. Its machine-readable mirror is
`web/src/lib/tokens.ts`. **Both must change together** — the TS file is a
mirror, not a second source of truth.

### 2.1 Grounding rule

> `tokens.css` is the only file in `web/src` that may contain a literal color
> value. A hex anywhere else is a contract violation, not a style choice.

Verified by grep in §7.

### 2.2 Color

| Token | Value | Purpose | Measured |
|---|---|---|---:|
| `--paper-0` | `#f4f5f2` | Primary reading ground | — |
| `--paper-1` | `#e9ebe6` | Grouped band | gray gap 11 |
| `--paper-2` | `#dfe2dc` | Recessed well | gray gap 20 |
| `--paper-selected` | `#d3e0f7` | Resting selection ground | gray gap 22 |
| `--paper-raised` | `#ffffff` | Bounded object ground | — |
| `--ink-inverse` | `#0e1524` | The one high-emphasis band | — |
| `--ink-900` | `#0e1524` | Primary ink | 16.67:1 |
| `--ink-700` | `#333c4f` | Secondary ink | 10.10:1 |
| `--ink-500` | `#4e5869` | Tertiary ink (last text step) | 6.56:1 |
| `--rule-hairline` | `#c4c9c1` | Content separator (1.4.11 exempt) | 1.54:1 |
| `--rule-hairline-strong` | `#a8afa6` | Emphasised separator | 2.05:1 |
| `--rule-control` | `#767e74` | **The only legal control border** | 3.83:1 |
| `--rule-control-strong` | `#666e64` | Hovered/pressed control border | 4.82:1 |
| `--cobalt-600` | `#1457d9` | Interactive accent | 5.65:1 |
| `--cobalt-700` | `#0f46b0` | Link, Segno, hover | 7.61:1 |
| `--cobalt-800` | `#0b3890` | Pressed, focus ring | 9.68:1 |
| `--cobalt-200` | `#a8c6ff` | Focus ring on ink | 10.58:1 |
| `--focus-ring-color` | `#0b3890` | Focus indicator | 9.68:1 |

Ratios are against `--paper-0` unless stated. Full table in §6.

**The `--rule-hairline` exemption is conditional.** WCAG 1.4.11 exempts
decorative and text-adjacent separators. A hairline is therefore legal between
two rows and illegal as the only boundary of a control. `rule-control` exists
for exactly that case, and no component may substitute one for the other.

### 2.3 Finding states

Four scales, each four steps. `-700` is the only step permitted to render status
text. `-600` is for marks and hairlines. `-100` is a resting ground and never
carries text alone. `-200` is for the inverse ground.

| State | `-700` text | `-100` ground | On paper-0 | Grayscale cue |
|---|---|---|---:|---|
| `supported` | `#0f5c41` | `#c9e5d8` | 7.30:1 | filled mark |
| `contradicted` | `#8e2028` | `#f2d2d4` | 8.04:1 | filled mark |
| `imprecise` | `#6b4700` | `#eddfbe` | 7.60:1 | filled mark |
| `unresolved` | `#34506b` | `#d4dee9` | 7.66:1 | **hollow mark** |

**The four states are about a claim and its evidence. Never about a person,
party, or entity.** There is deliberately no `personState`, no `neutral`, no
`error`, and no `success` in this vocabulary. A system failure is an
`ErrorState`, a different vocabulary entirely — keeping them apart is what stops
a provider outage from being rendered as a verdict.

`unresolved` is a first-class state, never an absence. It is drawn hollow so
the filled/hollow distinction survives grayscale with no hue at all.

### 2.4 Typography

Three roles, not three decorative families:

| Role | Family | Governs | Banned use |
|---|---|---|---|
| Claim | Newsreader Variable | claims, answers, titles, headings, all prose in the claim voice | UI labels, controls |
| UI | IBM Plex Sans Variable | navigation, controls, labels, structure, data | display voice of a claim |
| Data | IBM Plex Mono | time, identifiers, tabular measurement **only** | "technical credibility" texture |

All three are self-hosted from `@fontsource*` (already dependencies; no new
packages). The mono budget is the strictest: it is a measurement face, and
using it as texture is the most common way a record product starts to look
like a terminal.

| Step | Size | Leading | Voice | Use |
|---|---|---|---|---|
| `display` | `clamp(2.75rem, 1.35rem+5.6vw, 5rem)` | 0.98 | claim | Home/Metodo title only. Capped at 6rem. |
| `title` | `clamp(2rem, 1.25rem+3.1vw, 3.125rem)` | 1.03 | claim | Page and Fact-check title |
| `headline` | `clamp(1.5rem, 1.2rem+1.25vw, 2rem)` | 1.08 | claim | Section heading |
| `subhead` | `clamp(1.25rem, 1.1rem+0.62vw, 1.5rem)` | 1.18 | claim | Row claim, pane title |
| `lede` | `clamp(1.125rem, 1.02rem+0.44vw, 1.3125rem)` | 1.42 | ui | The concise answer, page lede |
| `body` | `clamp(1rem, 0.97rem+0.14vw, 1.0625rem)` | 1.6 | ui | Public body |
| `body-quiet` | 0.9375rem | 1.5 | ui | Studio dense reading |
| `label` | 0.875rem | 1.3 | ui | Controls, field labels |
| `meta` | 0.8125rem | 1.35 | ui | **The metadata floor** |

**11px gray micro-metadata is banned.** The floor is 13px at `--ink-500`,
which still measures 6.56:1. Micro-typography as a crutch is the single
clearest sign of a template product.

Tracking: display `-0.022em`, heading `-0.014em`, body `0`, label `+0.005em`,
data `+0.01em`. Floor is `-0.04em`; the display value sits above it.

Measures: claim `34ch` (a checked statement is read, not scanned), prose
`68ch`, brief `46ch`, data `92ch`. Fluid sizes are correct here and forbidden
in Studio's dense panes, which use the fixed `body-quiet`.

### 2.5 Space, geometry, layout

Spacing base is 4. Steps 1–11 (4px → 160px). The scale is not uniform, and the
non-uniformity is the point: it encodes conceptual layering.

| Layer | Steps | Meaning |
|---|---|---|
| within a control | 1–3 | 4–12px |
| within a row | 3–5 | 12–24px |
| between rows | 5–6 | 24–32px |
| between sections | 7–8 | 48–64px |
| between bands | 10–11 | 120–160px |

More space above a heading than below it, always.

Geometry: `--radius-mark: 1px` (the finding square), `--radius-control: 3px`.
There is **no pill radius** — an earlier draft had one, nothing used it, and it
was cut under the deletion test. Elevation: `--elevation-none`,
`--elevation-hairline`, `--elevation-hairline-selected`, `--elevation-overlay`.
No offset shadows exist in the system.

Layout widths: shell `78rem` (1248px), reading `44rem` (704px), rail `19rem`
(304px), document `48rem` (768px), studio shell `93.75rem` (1500px). Grid is
12 columns. `--page-inset` is the one responsive layout value.

### 2.6 Density

Two densities, one language. Every spacing and height decision resolves
through a `--density-*` variable, so Public stays spacious and Studio stays
dense without either becoming a separate visual brand.

| Variable | Public | Studio |
|---|---:|---:|
| `--density-row-min` | 3.75rem | 2.5rem |
| `--density-row-pad-y` | 1rem | 0.5rem |
| `--density-control-min` | 2.75rem | 2rem |
| `--density-block-gap` | 1.5rem | 0.75rem |
| `--density-section-gap` | 4rem | 2rem |
| `--density-band-gap` | 7.5rem | 3rem |
| `--density-type-body` | `body` | `body-quiet` |
| `--density-measure` | prose | data |

**Density never changes type family, type scale, palette, geometry, or motion
budget.** It changes rhythm and target size only.

Studio is set with `body.is-studio` (the class `BaseLayout.astro` already
applies) so no Lane D2 file needed editing. `[data-density='studio']` is the
forward-looking form.

**Known exception:** `--density-control-min` is 2rem (32px) in Studio, below
the 44px touch floor. This is documented, not accidental: Studio is
desktop-first and pointer-driven. It is **not** a licence to ship 32px touch
targets on Public, and it must be re-validated before any Studio surface is
exposed to a touch-primary device. See §9 residual risk.

### 2.7 Motion

| Token | Value | Use |
|---|---|---|
| `--duration-fast` | 120ms | press, hover, hairline change |
| `--duration-standard` | 180ms | selection move, disclosure, sheet enter |
| `--duration-slow` | 260ms | dialog enter, large surface change |
| `--ease-enter` | `cubic-bezier(0,0,.2,1)` | things arriving |
| `--ease-exit` | `cubic-bezier(.4,0,1,1)` | things leaving |
| `--ease-move` | `cubic-bezier(.2,0,0,1)` | things moving |

The one authored transition in the system is `--transition-select`: the Segno
and selection ground moving to a newly selected claim. Everything else is a
control color change or an overlay entrance.

**Motion explains a state change and nothing else.** No page-load
choreography, no decorative loops, no fake streaming progress, no parallax.

`prefers-reduced-motion: reduce` sets all three durations to `1ms`. The *end
state is never removed* — reduced motion reaches the same result instantly, so
no information is lost. The two infinite animations (skeleton sweep, button
spinner) become static fills, and the spinner keeps a visible border.

### 2.8 Focus

A three-part structure, never a single outline: 2px ring, 2px offset, and a
brightness change. The offset is what makes focus survive both a light ground
and a dense surface, and it is a **non-color** cue.

`--focus-ring-color-inverse` is required wherever a control sits on
`--ink-inverse`, or the ring would vanish into its own background.

---

## 3. Component contracts

Implemented in `web/src/components/design/`, exported from `index.ts`.
The inventory is a **ceiling, not a quota**.

### Shared primitives

| Component | Purpose | Ownership | Key a11y behavior |
|---|---|---|---|
| `Surface` | The only container. 5 grounds + `bounded` opt-in | both | `as` prop so headings stay headings |
| `Hairline` | Separator / elevation | both | `aria-hidden` when decorative |
| `Row` | The repeated object: ClaimRow, SourceRow, TranscriptLine, ClaimQueueRow | both | stretched real anchor; `as="li"` keeps a real list |
| `StatusText` | The finding state | both | mark `aria-hidden`; no word → no render |
| `SectionIndex` | Long-document margin nav | Public | `nav` + named; `aria-current`; real anchors |
| `Disclosure` | Secondary material | both | native `<details>`; Enter/Space free |
| `Dialog` / `Sheet` | One component, two placements | both | `showModal()`, named, focus restored |
| `SegmentedControl` | Value choice | both | real `radiogroup` of radios; arrow keys free |
| `TextField` | Search / single text input | both | real form; hidden label; `aria-describedby` |
| `Button` | 3 intents | both | `type="button"` default; `busy` ≠ `disabled` |
| `Skeleton` | Loading | both | `aria-hidden`; region is `aria-busy` |
| `EmptyState` | Nothing here, and what to do | both | real content |
| `ErrorState` | System failure | both | `role="alert"` / `role="status"` |
| `EvidenceTape` | Chronology nav | Public + Studio | real `<ol>`; `aria-current`; filled/hollow |
| `FocusRing` | Group-level ring | both | `focusin`/`focusout` + `relatedTarget` |
| `VisuallyHidden` | Present to AT, absent visually | both | `clip-path`, stays focusable |

### 3.1 State matrices

**`StatusText` — the safety-critical one**

| State | Word | Mark | Color | Notes |
|---|---|---|---|---|
| default | required | filled | `-700` on paper | Grayscale-legible |
| empty label | — | — | — | **Renders nothing** (invariant) |
| `count` > 50 | — | — | — | **Refuses to render** (anti-score guard) |
| `quiet` | required | filled | ink-500, regular | Studio dense rows |
| inverse ground | required | filled | `-200` | Automatic |
| unresolved | "Non risolta" | **hollow** | `-700` | Filled/hollow is the non-color cue |

**`Row`**

| State | Ground | Segno | Focus | Notes |
|---|---|---|---|---|
| default | `paper-0` | — | 2px ring, inset | hairline bottom |
| hover | `paper-1` | — | — | Non-color: ground shift |
| selected | `paper-selected` | cobalt 2px | — | Wins over hover |
| selected+hover | 78% sel | cobalt 2px | — | Selection never lost |
| non-interactive | `paper-0` | — | — | `data-interactive="false"` |
| focus-visible | — | — | 2px ring, inset | `:focus-visible` only |

**`Button`**

| Intent | Default | Hover | Active | Disabled | Busy |
|---|---|---|---|---|---|
| `primary` | ink ground, paper text | cobalt-800 | ink-inverse | paper-1, ink-500 | `aria-busy` + spinner |
| `secondary` | raised + control rule | paper-1, stronger rule | paper-2 | paper-1, hairline rule | same |
| `quiet` | cobalt-700, no box | underline | — | ink-500 | same |

A **busy** button is `aria-disabled`, not `disabled`: it stays focusable and
discoverable, and its accessible name is preserved unless the caller supplies
`busyLabel`. A spinner that replaces the label destroys the name mid-action.

**`SegmentedControl`**

| State | Ground | Underline | Announced |
|---|---|---|---|
| unselected | raised | — | — |
| unselected hover | paper-1 | — | — |
| selected | paper-selected | cobalt 2px | `aria-checked` + live region |
| focused | — | — | ring on the label via `:focus-within` |
| disabled | paper-1 | — | `disabled` on the input |

**`Disclosure`**

| State | Indicator | Announced |
|---|---|---|
| closed | chevron 45° | native collapsed |
| open | chevron 225° | native expanded |
| focus-visible | 2px ring, inset | native |
| reduced motion | no animation, same end state | native |

**`Dialog` / `Sheet`**

| Concern | Behavior |
|---|---|
| Open | `showModal()` → focus trap + inert + top layer, for free |
| Named | `aria-labelledby` at the visible title; **title required** |
| Initial focus | `data-autofocus` → close button → first focusable → self |
| Escape | native `cancel`, routed through `onClose` |
| Backdrop click | closes only if the press *started* on the backdrop, so a text drag does not dismiss |
| Close | focus returns to the invoker, or `[data-dialog-return-focus]` |
| Reduced motion | no animation, same end state |

**`EvidenceTape`**

| State | Dot | Rail item | Announced |
|---|---|---|---|
| default | hollow, `rule-control` | ink-500 | mark's `aria-label` |
| hover | `rule-control-strong` | ink-900 | — |
| current | **filled cobalt** + ring | cobalt-800, semibold | `aria-current` |
| reduced motion | same, no transition | — | — |

Renders **nothing** below two marks: a one-mark "timeline" is a decorative
graphic and is banned.

**`TextField`**

| State | Behavior |
|---|---|
| default | raised ground, `rule-control` border |
| focus-within | cobalt border + inset cobalt Segno |
| invalid | `contradict-700` border, `aria-invalid`, `role="alert"` error |
| hint | `aria-describedby`, suppressed when an error replaces it |
| error text | names the problem **and** the recovery |

**`Skeleton` / `EmptyState` / `ErrorState`**

| State | Behavior |
|---|---|
| Skeleton | Occupies the real content's box. No layout shift on arrival. |
| `SkeletonRegion` | `aria-busy` + label; announced once, not per bar |
| `EmptyState` | Names what would be here and what to do. Never "no results". |
| `ErrorState` `error` | `role="alert"`. Left rule in `contradict-700`, never a fill. |
| `ErrorState` `blocked` | `role="status"`. Left rule in `unresolved-700`. Normal state. |

`ErrorState` never uses a finding-state *word*. A reader must never confuse
"the system could not load this" with "this claim is false".

### 3.2 The four-stage pipeline stays structurally distinct

`PRODUCT.md` requires that evidence retrieval ≠ approval ≠ verification ≠
publication remain visually and structurally distinct. The system enforces
this by giving the pipeline **four different visual registers**, not four
badges of the same kind:

| Stage | Register | Where |
|---|---|---|
| Retrieved | neutral ink-500, hollow mark, "Recuperata" | Source row |
| Approved | `unresolved` neutral, "Approvata" | EvidenceReviewRow, Studio only |
| Verified | the finding state, filled mark, the word | `StatusText` on the public row |
| Published | a 2px `rule-ink` bottom rule + a date, no color | Row chrome |

Publication has **no color of its own** — it is a rule and a date. That is
deliberate: color is spent on epistemic state, and publication is a fact about
the record, not a claim about truth. A Studio action that publishes is a
`primary` Button in a `Dialog` whose title names the action, never a row
affordance.

---

## 4. Composition rules

### 4.1 Clarity budget

One dominant visual anchor per Public first viewport. Never combine more than
**two** of: large display headline, large media, evidence visual, tape, dense
table, strongly colored state treatment. If three appear, simplify first.

### 4.2 Visual-noise limits

- At most one state treatment per repeated row.
- No icon before every text link.
- No persistent uppercase micro-label layer.
- No repeated soft pills as page texture.
- Fewer separators: whitespace does more work than rules.
- No chart + tape + large media in an ordinary Fact-check.

### 4.3 The mobile rule

Mobile is **recomposed, not stacked**. Filters become a `Sheet`. The rail
becomes inline content or a Disclosure. The tape becomes horizontally
scrollable with large touch marks. The claim row becomes statement-first with
metadata below. Type steps down through `clamp()`; the measure stays 65–75ch.
Verified: no horizontal overflow at 320px.

### 4.4 Reading order and DOM

Semantic DOM order matches visual reading order at every breakpoint, including
under the asymmetric grid. The grid is CSS-only; content order never changes.
This is why `Row` uses a real stretched anchor rather than an absolutely
positioned click handler.

---

## 5. Accessibility contract

| Requirement | Where it lives |
|---|---|
| Semantic HTML first | Components are `<details>`, `<dialog>`, `<fieldset>`, `<ol>`, real anchors |
| Visible focus, 3-part structure | `base.css :focus-visible` + `--focus-ring-color-inverse` |
| Keyboard for every control | Native where possible; `SegmentedControl` uses real radios |
| 44px touch targets | `--target-min`; Studio's 32px is a documented exception |
| Status never color-alone | Word first; `unresolved` hollow mark; live region |
| Grayscale readable | Verified in-browser; word carries state |
| Table semantics | `role="table"`/`<table>` keep real semantics + tabular numerals |
| No hover-only information | Every hover state duplicates an available state |
| 200% zoom | Fluid type; no fixed-px text containers |
| Reduced motion | Durations → 1ms; end states preserved |
| Target size | `--target-min` on every standalone control |
| Print | Grounds → white, ink → black, URLs expanded |

**What is NOT in the contract, and why:** there is no custom focus trap. Native
`showModal()` provides containment, inertness, Escape, and top-layer stacking;
only focus *restoration* is ours (`useRestoreFocus`, ~20 lines). Adopting Radix
for that half would cost more than it returns. The registry nominates Radix as
the ADAPT donor; this is the recorded decision not to, with reasons.

---

## 6. Contrast table

All ratios computed with the WCAG 2.1 relative-luminance formula against
`--paper-0` (`#f4f5f2`) unless stated.

### Text on paper grounds (WCAG 1.4.3, body ≥ 4.5:1)

| Token | Value | Role | `paper-0` | `paper-1` | `paper-2` | Class |
|---|---|---|---:|---:|---:|---|
| `--ink-900` | `#0e1524` | Primary ink | 16.67 | 15.19 | 13.94 | **AA** |
| `--ink-700` | `#333c4f` | Secondary ink | 10.10 | 9.21 | 8.45 | **AA** |
| `--ink-500` | `#4e5869` | Tertiary ink | 6.56 | 5.98 | 5.49 | **AA** |
| `--cobalt-600` | `#1457d9` | Interactive accent | 5.65 | 5.15 | 4.73 | **AA** |
| `--cobalt-700` | `#0f46b0` | Link / Segno | 7.61 | 6.93 | 6.36 | **AA** |
| `--cobalt-800` | `#0b3890` | Pressed / focus | 9.68 | 8.82 | 8.10 | **AA** |
| `--support-700` | `#0f5c41` | supported | 7.30 | 6.66 | 6.11 | **AA** |
| `--contradict-700` | `#8e2028` | contradicted | 8.04 | 7.33 | 6.72 | **AA** |
| `--imprecise-700` | `#6b4700` | imprecise | 7.60 | 6.92 | 6.35 | **AA** |
| `--unresolved-700` | `#34506b` | unresolved | 7.66 | 6.98 | 6.41 | **AA** |
| `--rule-control` | `#767e74` | Control border (1.4.11) | 3.83 | 3.49 | 3.21 | **AA** |
| `--rule-control-strong` | `#666e64` | Hovered control border | 4.82 | 4.40 | 4.03 | **AA** |

Every text token clears 4.5:1 on **all three** grounds, so no component can
place prose on a band and silently drop below AA.

### Status text on its own resting ground (1.4.3)

| State | Tint | Ink | Ratio |
|---|---|---|---:|
| supported | `#c9e5d8` (`--support-100`) | `#0e1524` | 13.62 |
| contradicted | `#f2d2d4` (`--contradict-100`) | `#0e1524` | 12.98 |
| imprecise | `#eddfbe` (`--imprecise-100`) | `#0e1524` | 13.81 |
| unresolved | `#d4dee9` (`--unresolved-100`) | `#0e1524` | 13.40 |

### On the inverse ground `--ink-inverse` (`#0e1524`)

| Token | Value | Role | Ratio |
|---|---|---|---:|
| `--ink-inverse-100` | `#f4f5f2` | Primary text on ink | 16.67 |
| `--ink-inverse-300` | `#b9c2d4` | Secondary text on ink | 10.19 |
| `--cobalt-200` | `#a8c6ff` | Focus ring on ink | 10.58 |
| `--support-200` | `#8fd6b6` | supported on ink | 10.82 |
| `--contradict-200` | `#f0a9ad` | contradicted on ink | 9.54 |
| `--imprecise-200` | `#e3c88a` | imprecise on ink | 11.20 |
| `--unresolved-200` | `#a8c0d8` | unresolved on ink | 9.72 |

### Below threshold, deliberately

| Token | Value | on `paper-0` | Justification |
|---|---|---:|---|
| `--rule-hairline` | `#c4c9c1` | 1.54 | 1.4.11 exempts decorative and text-adjacent separators. **Illegal as a control's only edge.** |
| `--rule-hairline-strong` | `#a8afa6` | 2.05 | Same exemption. Used for the tape track, which is a graphic, not a control. |

### Grayscale separation

| State | Value | Gray luminance | Δ vs `paper-0` (244) |
|---|---|---:|---:|
| `--support-700` | `#0f5c41` | 66 | 179 |
| `--contradict-700` | `#8e2028` | 66 | 179 |
| `--imprecise-700` | `#6b4700` | 74 | 171 |
| `--unresolved-700` | `#34506b` | 75 | 170 |

The four states sit within 9 luminance points of each other, so **grayscale
distinction does not rest on these values at all**. It rests on two things: the
word carries the state, and `unresolved` alone uses a hollow mark. Verified in
-browser with `filter: grayscale(1)`.

---

## 7. Migration map

### Layer order (a contract, not a preference)

```
tokens.css       literals. The ONLY file that may contain a hex.
base.css         reset, document typography, density, browser surfaces, print.
primitives.css   the design-system components. No literals.
legacy.css       TEMPORARY. Aliases the existing pages' class names onto tokens.
global.css       four @imports. Nothing else.
```

Each layer may only depend on the ones above it.

### `legacy.css` — the rebase, and its deletion plan

Lane D2 owns `web/src/pages/**` and `web/src/components/*.{astro,tsx}`. Rather
than leave the existing product on the old system, `legacy.css` re-expresses
the ~130 class names those files already use in terms of the frozen tokens.
The whole product therefore adopts the new visual world with **zero edits to a
file this lane does not own**.

`legacy.css` is temporary and must shrink to nothing. Per-group deletion:

| Group | Classes | Delete when | Replace with |
|---|---|---|---|
| Chrome | `.site-header`, `.brand*`, `.main-nav`, `.masthead-note`, `.site-footer` | Header/footer rebuilt | `Surface`, `Button` |
| Type | `.eyebrow`, `.display-title`, `.page-title`, `.claim-title`, `.section-title*`, `.lede` | Page headings migrated | `h1`–`h4` + type tokens |
| Rows | `.claim-row*`, `.explore-row*`, `.moment-row*`, `.transcript-line`, `.queue-row*`, `.session-row`, `.source-row*` | Rows migrated | `Row` |
| State | `.assessment*` | Assessment migrated | `StatusText` |
| Search | `.search-field*`, `.search-icon`, `.search-note` | Search migrated | `TextField` |
| Bands | `.page-section*`, `.home-*`, `.explore-*`, `.fact-*`, `.record-*`, `.audit-*`, `.media-*`, `.method-*` | Page migrated | `Surface`, `SectionIndex` |
| Studio | `.studio-*`, `.workspace-*`, `.pane-header`, `.is-studio` density block | Studio migrated | density vars + `Row` |
| States | `.no-results` | — | `EmptyState` / `ErrorState` |
| Media | `.media-poster`, `.audit-player`, `.studio-media` | Media integrated | keep; they are surface, not primitive |

The former Lane D2 compatibility exceptions are closed: `BaseLayout.astro`
uses the current paper value for `theme-color`, and all skip-link/visually
hidden consumers now use the canonical `dp-skip-link` /
`dp-visually-hidden` primitives. Their duplicate legacy definitions were
removed.

### Per-page migration order

1. `SiteHeader` / `BaseLayout` (unblocks the chrome for everything else)
2. `ClaimRow` + `Assessment` (appear on four surfaces; highest leverage)
3. `SearchField` → `TextField` (Home + Explore)
4. `fact-check` → `SectionIndex`, `Disclosure`, `StatusText`
5. `esplora` → `SegmentedControl`, `Dialog`/`Sheet` for mobile filters
6. `contenuti` → `EvidenceTape`
7. `studio/*` → density vars, `Row`, `Dialog`

Each step is independently shippable and independently reviewable.

---

## 8. Deletion test (binding on new components)

A new component or dependency is admitted only if this is answerable:

1. **What user or operator decision does it support?** If the answer names a
   mockup rectangle, it is rejected.
2. **Can a row, a heading, a list, or a native element serve it?** If yes, it
   is rejected.
3. **Is it owned by exactly one lane?** Duplicate owners are rejected.
4. **Does it need a new dependency?** If the platform does not already do it,
   the answer must justify a runtime cost, and the registry entry must be
   cleared with exact license evidence.

Two components were **removed by this test during authoring**: the pill radius
(unused), and a planned custom focus trap (the platform already does it).

---

## 9. Residual risk

Stated plainly, because the ticket requires it.

1. **Studio's 32px minimum control height** is below the 44px touch floor.
   Correct for a pointer-driven desktop surface, unvalidated for touch. Must be
   re-validated before Studio is exposed to a touch device.
2. **Runtime proof is pending.** All verification in this document is Mac
   development evidence. Per `AGENTS.md`, the affected public routes require
   MiniPC proof before the change can be called production-validated.
3. **The primitives are built but not yet adopted by any page.** They are
   consumable and typecheck-clean, but until Lane D2 migrates, the live product
   renders through `legacy.css`. The new components are exercised by typecheck
   and build only, not by a rendering test.

Two earlier release risks are now closed in-repo: `BaseLayout.astro` mirrors
`--paper-0` for the HTML `theme-color`, and the three pinned Fontsource
OFL-1.1 notices are vendored under `web/licenses/`. `npm run check:design`
guards both facts and rejects visual literals/effects that bypass the token
contract.

---

## 10. Change control

Token or component changes require: updating `tokens.css` **and** `tokens.ts`
together, recomputing the §6 table if any color moved, re-running the §7 grep
proof, and recording the reason here.

Design-system *visual* decisions belong to DP-411; *contract* decisions belong
to DP-412; product truth belongs to `PRODUCT.md` and cannot be changed by
either. The boundaries are not advisory.

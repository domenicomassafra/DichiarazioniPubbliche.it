# Dichiarazioni Pubbliche — Design System v1

Status: **frozen — design system of record**
Date: 2026-09-26
Supersedes: Design System Candidate v0.2 (2026-09-23)

The consumable contract — every token value, every component state matrix, the
contrast table, the migration map — is
**[`docs/ux/design-system-v1.md`](docs/ux/design-system-v1.md)**. This file
states the durable visual decisions and the reasoning behind them. It is the
authority a reviewer reads; the contract is the authority a builder reads.

`PRODUCT.md` and `docs/35-public-product-architecture-v3.md` are authoritative for
product truth and public information architecture. `docs/32-public-ux-architecture-v2.md`
is retained as superseded design history. Neither canonical authority can be changed by
a design ticket.

---

## The thesis

**A civic ledger, not a dashboard.**

Dichiarazioni Pubbliche is an Italian public record: something a citizen reads and a
researcher cites. It is set like a document a serious editorial team would
publish and it behaves like an index a reference work would be. It is not an
analytics console with a serif font applied to it.

That distinction is load-bearing. A fact-check product's default is a card grid
with colored verdict pills and a KPI strip; a "modern" record product's default
is a dark dashboard with a shader behind it. Both are excluded twice over —
once by the product invariants in `PRODUCT.md` (no scores, no rankings, no
auto-publication, no government scenery) and once by the craft floor. What
survives that double exclusion, built honestly, is a typography-led editorial
system, and it is specific enough to be recognizable without a logo.

---

## The three commitments

Everything else is derived from these.

### 1. Typography is the layout engine

Structure comes from type size, weight, alignment, and whitespace. It does not
come from boxes, fills, or borders. An asymmetric ledger grid lets a page be
composed like a document and read like an index.

- **The serif carries every claim, answer, and title**, because those are the
  words being examined. It is the voice of the record.
- **The sans carries structure** — navigation, controls, labels, the word UI
  itself.
- **The mono is spent only on time, identifiers, and tabular measurement**, the
  three cases where a reader compares characters column-wise. It is the most
  easily abused face in the system; using it as "technical texture" is how a
  record product starts to look like a terminal.

A strict fluid scale, one step per level, no step landing between two others.
Display is capped at 6rem: past that a title is a poster. Measures are fixed by
role — 34ch for a checked statement (read, not scanned), 68ch for prose, 92ch
for genuinely tabular content.

**The metadata floor is 13px.** 11px gray micro-metadata is banned outright: it
is the clearest single sign of a template product, and it fails readers who need
magnification for the one text that carries provenance.

### 2. The Segno is the only brand gesture

A 2px cobalt rail marking whatever currently holds attention. One geometric
element, five jobs: **selected row, focused-within field, open disclosure,
active moment on the tape, active item in a margin rail**. A reader learns it
once and then knows, anywhere in the product, where attention lives.

It is always cobalt and **never a finding-state hue**. This is the system's
most important neutrality decision: a selection cue that borrowed verdict color
would let a reader confuse "you are here" with "this claim is false", which is
the exact confusion `PRODUCT.md` exists to prevent.

The brand mark is the same geometry rotated — a cobalt square in the header —
so the gesture is reinforced by the identity rather than sitting beside it.

### 3. Hairline is the entire depth system

There are no shadows. An object is elevated by a change of ground plus a 1px
control-grade rule. Radii stay at 0–3px, because the world is printed, not
plastic. Universal 12–24px rounding is the fastest route from "a public record"
to "a template", and it is banned.

Three rule weights, each with a named job. The distinction that matters: a
`rule-hairline` is a content separator and is legitimately below 3:1 (WCAG
1.4.11 exempts decorative separators); a `rule-control` is a control's only edge
and must clear 3:1. Conflating them is a real failure, so the tokens make the
distinction explicit.

---

## Surface grammar

The order of visual weight, always:

1. **the statement / the factual question**
2. **the concise finding**
3. **the evidence that explains it**
4. **time, provenance, and method — when they materially aid comprehension**

Lists are the default for repeated public records. A card is a decision, not a
default: a genuinely self-contained interactive object, a media item, a bounded
evidence object, an overlay. Not a source, not a topic, not a sentence.

### Clarity budget

One dominant visual anchor per Public first viewport. Never combine more than
**two** of: large display headline, large media, evidence visual, tape, dense
table, strongly colored state treatment. Three means simplify before polishing.

### The finding state is a word

The single most safety-critical surface in the product. A state is rendered as
**a written word** plus a small square mark. The mark reinforces; it never
carries. An empty label renders nothing at all, because a state with no word is
not a state.

Four states describe a claim and its evidence — supported, contradicted,
imprecise, unresolved. They are never about a person, party, or entity. There
is no `neutral`, no `error`, no `success` in this vocabulary, because a system
failure is a different kind of fact and mixing the two would let a provider
outage render as a verdict.

**`unresolved` is a first-class state, never an absence.** It draws a hollow
mark while the other three draw filled ones, so the distinction survives a
grayscale printout with no hue at all — and all four states sit within 9
luminance points of each other, so grayscale legibility never depended on hue in
the first place.

### The pipeline has four registers, not four badges

`PRODUCT.md` requires that evidence retrieval ≠ approval ≠ verification ≠
publication stay structurally distinct. The system gives them four different
*kinds* of mark: neutral and hollow, neutral and labelled, the finding state
and filled, and — for publication — **a rule and a date with no color at all**.
Color is spent on epistemic state; publication is a fact about the record, not
a claim about truth, so it gets geometry instead.

### Evidence Tape

A navigation rail, not a causal graph. A mark is a dated event; connecting marks
would assert causation the record does not support. Marks are neutral until
selected, because a color-coded timeline turns chronology into a verdict
distribution. Renders nothing below two marks — a one-mark timeline is a
decorative graphic, and decorative graphics are banned.

### Motion

Three durations (120/180/260ms), three easings, no bounce, no spring, and
**one authored transition**: the Segno and selection ground moving to a newly
selected claim. Everything else is a control color change or an overlay
entrance.

Motion explains a state change and does nothing else. No page-load
choreography, no decorative loops, no fake streaming progress, no parallax.
`prefers-reduced-motion` sets every duration to 1ms while **preserving every
end state**, so no information is lost — reduced motion is the same result,
reached instantly.

---

## Two densities, one language

Public is spacious and mobile-first. Studio is denser and desktop-first. They
share a visual language and differ in **rhythm and target size only** — never in
type family, type scale, palette, geometry, or motion budget.

Every spacing and height decision resolves through a `--density-*` variable, so
this is a token difference rather than a second stylesheet. That is what keeps
Studio from drifting into a separate visual brand while doing a genuinely
different job.

One documented exception: Studio's minimum control height is 32px, below the
44px touch floor. It is correct for a pointer-driven desktop surface and is
recorded as a live risk in the contract, not waved through.

---

## The color discipline

The palette is derived from the existing paper/ink/cobalt vocabulary and
**extended for contrast**, then every shipped pair measured. Results:

- All three paper grounds are separated by a deliberate luminance gap, so
  nested surfaces never collapse into each other.
- Every text token clears 4.5:1 on **all three** grounds, so prose on a band
  cannot silently drop below AA.
- Every control border clears 3:1 (1.4.11).
- The two hairline weights sit below 3:1 under a documented, conditional
  exemption — and the tokens make the condition explicit.

Cobalt is reserved for selection, focus, and links. It is not a status hue,
and no status hue doubles as a brand cue. The whole system is one accent on
three neutrals plus four epistemic states.

There is no gradient anywhere. The system ships **zero** `linear-gradient`,
`radial-gradient`, and `conic-gradient` declarations, no `backdrop-filter`
decoration layer, and no shadow scale. Verified by grep, not asserted.

---

## Composition

### Mobile is recomposed, not stacked

One semantic column, filters as a `Sheet`, the margin rail as inline content or
a `Disclosure`, the tape horizontally scrollable with large touch marks, the row
statement-first with metadata below. No mechanically stacked desktop boxes.
Verified: no horizontal overflow at 320px.

### Reading order equals DOM order

At every breakpoint, including under the asymmetric grid. The grid is CSS-only;
content order never changes. This is why rows use a real stretched anchor
rather than an absolutely positioned click handler — the link stays
copyable, middle-clickable, and the accessible name stays the claim.

### Keyboard and the platform first

`<details>` for disclosure, `<dialog>` + `showModal()` for overlays, real radios
for the segmented control, real anchors for the index, native `<ol>` for the
tape. Where the platform already solves a problem correctly, the system uses it
rather than vendoring a library to reimplement it worse. The only custom
behavior is focus *restoration* on dialog close, which is ~20 lines — recorded
in the contract as a deliberate decision not to adopt Radix, with reasons.

### Browser surfaces ship too

Scrollbars, the caret, text selection, placeholder color, autofill, and
tabular numerals are themed from the palette. These are the parts nobody draws
and everybody ships, and they are the cheapest signal that a page was built
rather than assembled.

---

## Explicit non-goals

These are refusals, not deferrals. Reaching for one means the direction was
not actually decided.

- no generic shadcn-looking product, and no Material/Carbon/Fluent skin;
- no Aceternity/Magic-UI effect identity;
- no background shader or gradient system;
- no KPI cards on Public;
- no person scorecards, verdict totals, or rankings anywhere;
- no government, courthouse, seal, flag, or institutional scenery;
- no visual effect without a product job;
- no 11px gray micro-metadata;
- no universal 12–24px rounded cards;
- no icon before every text link;
- no uppercase kicker above a heading — the heading carries its own weight;
- no section numbers unless the sequence carries information the reader needs;
- no nested cards;
- no component that exists only because a mockup drew a rectangle.

---

## Change control

Visual-direction decisions belong to **DP-411**. Token and component contracts
belong to **DP-412**. Product truth belongs to `PRODUCT.md` and is not
changeable by either.

Changing a token value requires updating `web/src/styles/tokens.css` **and**
`web/src/lib/tokens.ts` together, recomputing the contrast table in the
contract, and re-running the grep proof. The tokens file is the only file in
`web/src` permitted to contain a literal color value; that rule is what makes
the contrast table trustworthy rather than aspirational.

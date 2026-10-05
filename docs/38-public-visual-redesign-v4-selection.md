# Dichiarazioni Pubbliche — Public Visual Redesign v4 Selection

Date: 2026-10-05
Owner ticket: DP-424
Status: selected direction

This document compares the v4 composition directions for the three key Public screens:
Home, Statement and Trace. It is downstream of `docs/37-public-marketing-brand-context.md`
and preserves the visual commitments in `DESIGN.md`: civic ledger, Newsreader + IBM Plex,
paper/ink/cobalt, hairlines, the Segno, no shadows/gradients, no person scores, and one
dominant visual anchor per first viewport.

## Incumbent audit

The current `prototypes/final-hybrid/` family is a strong baseline: typography carries the
interface, repeated records are rows rather than card grids, findings are written words,
and the Public surface already feels calmer than a news site or SaaS dashboard.

Three concrete gaps justify the v4 pass:

1. the header still uses a quotation-mark gesture instead of the cobalt square/Segno
   geometry frozen in `DESIGN.md`;
2. Home's large slogan and side search split attention instead of making discovery the
   unmistakable primary conversion;
3. Statement is clear but reads as “document plus metadata rail”; source, finding and
   original context can form a tighter first-view reading path;
4. Trace is a competent vertical timeline, but the signature longitudinal capability is
   not yet expressed as a recognizable selection/inspection interaction.

## Direction A — Ledger Spine — SELECTED

**Idea:** one cobalt attention spine moves through the product: it marks the Home search
entry, the currently inspected source/context row on Statement, and the selected moment on
Trace. Typography remains the dominant structure; the spine is an interaction grammar,
not decoration.

### Home

- compact explanatory hero rather than poster-scale slogan;
- the universal search becomes the full-width dominant object directly under the promise;
- recent Statements immediately prove the product with exact wording/source/finding rows;
- Method remains a secondary trust path, not a competing CTA.

### Statement

- exact wording + speaker/source/time remain the first visual anchor;
- the concise finding is pulled directly into the first reading sequence instead of
  living as a detached right-rail summary;
- original source/context is presented as an inspectable path with the active source
  moment carrying the Segno;
- technical provenance stays progressive.

### Trace

- chronology becomes an explicit selectable index of reviewed events;
- one event is selected with the Segno + selection ground and reveals its context in the
  reading pane;
- event findings remain local to each Statement and never recolor the chronology;
- no connecting causal graph, score distribution or deception language.

**Mobile posture:** the same DOM/reading order recomposes into one column. Search stays
first on Home; Statement source context becomes an inline disclosure; Trace inserts the
selected detail directly after the active chronological event.

**Strengths:** strongest fit with the existing brand thesis; makes the Segno useful rather
than decorative; gives Trace a signature interaction; low conceptual cost for the other
record pages; keeps lists, source paths and typography as the main vocabulary.

**Risk:** if overused, the cobalt rail could become ornament. DP-425 must limit it to
selected/focused/current/open states exactly as `DESIGN.md` requires.

## Direction B — Index Ledger

**Idea:** lean harder into reference-work/index behavior. Metadata columns become more
prominent and the Public product reads almost like a highly designed catalogue.

### Home

- masthead + search at top;
- immediately below, a dense index with fixed date/person/type columns;
- minimal narrative copy.

### Statement

- narrow reading column with a parallel fixed metadata column;
- evidence and source entries use strongly aligned tabular rows;
- finding summary sits in a compact register above the prose.

### Trace

- chronology is a date-led table: date / wording / relation / source;
- selecting a row expands details beneath it.

**Mobile posture:** columns collapse into labelled key/value groups and expanded rows.

**Strengths:** excellent scanability and reuse; high information integrity; very low risk
of marketing/SaaS visual drift.

**Risks:** too dense for first-time citizens, weaker emotional/brand recall, can feel like
an archive database rather than a public product, and makes Trace less distinctive.

## Direction C — Source Window

**Idea:** make original source context the dominant compositional anchor. The record feels
like a window into the exact interview/video/article moment first, with verification
layered beside it.

### Home

- search remains available but a featured source/content example anchors the first
  viewport;
- recent Statements appear as moments extracted from that source plus the wider record.

### Statement

- source moment/media/excerpt shares the first viewport with the exact statement;
- finding and evidence follow immediately below.

### Trace

- each chronological event emphasizes its original source snapshot/locator;
- selection swaps the source/context view while preserving chronology.

**Mobile posture:** source context follows the exact wording and never precedes it in DOM
order.

**Strengths:** strongest proof of source-first behavior and resistance to out-of-context
reading; excellent for video/audio/content-led Statements.

**Risks:** overweights media relative to written sources, competes with the Statement as
the canonical shareable object, and can turn Home into a media feature instead of a search
entry point.

## Review matrix

Scores are 1–5, where 5 is strongest fit. They compare composition, not product truth.

| Criterion | A Ledger Spine | B Index Ledger | C Source Window |
|---|---:|---:|---:|
| Product/marketing fit | 5 | 4 | 3 |
| Civic-ledger brand fit | 5 | 5 | 4 |
| First-time clarity | 5 | 3 | 4 |
| Search/discovery primacy | 5 | 5 | 3 |
| Statement reading path | 5 | 4 | 4 |
| Trace distinctiveness | 5 | 3 | 4 |
| Accessibility/mobile recomposition | 5 | 4 | 4 |
| Reuse across Person/Topic/Content | 5 | 5 | 3 |
| Implementation cost | 4 | 4 | 3 |

## Decision

Select **Direction A — Ledger Spine**.

It is the only direction that simultaneously makes successful discovery the obvious Home
conversion, tightens Statement without turning it into a dashboard, and gives Trace a
distinctive longitudinal interaction using a gesture the design system already owns. It
therefore improves composition without inventing a second visual brand.

Direction B is rejected as the default because its density is better suited to Explore or
research-heavy list states than to the whole Public product. Direction C is rejected as
the default because source media should prove a record, not become the universal first
visual anchor.

## Selected-screen contract

### Home signature move

The **search spine**: the primary search surface is marked by the cobalt Segno and sits in
the main reading flow immediately after the one-sentence promise. No competing CTA is
allowed in the same hierarchy.

### Statement signature move

The **inspectable source path**: exact wording -> source/time -> concise finding ->
verification/evidence -> active original-context row. The Segno marks the currently
inspected source/context item, never the finding state.

### Trace signature move

The **selected chronology**: a neutral chronological index of reviewed events where the
current event alone receives the Segno/selection ground and reveals its source/context.
The timeline itself never becomes a verdict visualization.

## Visual proof

The selected direction is rendered from `prototypes/v4-ledger-spine/build.py`.

Desktop receipts:

- `prototypes/v4-ledger-spine/home-desktop.png`;
- `prototypes/v4-ledger-spine/statement-desktop.png`;
- `prototypes/v4-ledger-spine/trace-desktop.png`.

Phone receipts:

- `prototypes/v4-ledger-spine/home-mobile.png`;
- `prototypes/v4-ledger-spine/statement-mobile.png`;
- `prototypes/v4-ledger-spine/trace-mobile.png`.

The prototype uses the same real fixture shapes already present in the maintained Public
mockups. It is a composition proof, not evidence for the truth of those illustrative
fixture statements.

## Hand-off to DP-425

DP-425 must translate this selected direction into reusable contracts rather than copying
prototype CSS. In particular it must freeze:

- Segno use limits and states;
- Entry/index, Record and Trust-document composition rules;
- Home search-stage anatomy;
- Statement source-path anatomy;
- Trace chronology/selection anatomy;
- phone recomposition rules that preserve DOM/reading order;
- all keyboard/focus/reduced-motion/empty/loading/error states before page tickets claim
  visual completion.

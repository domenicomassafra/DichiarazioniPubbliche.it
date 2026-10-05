# Dichiarazioni Pubbliche — Public Design System v2

Status: **frozen public composition contract**
Date: 2026-10-05
Owner ticket: DP-425
Direction: DP-424 — Ledger Spine

This document is the Public v4 composition and composite-component contract. It extends,
and does not duplicate, `docs/ux/design-system-v1.md`.

- **v1 remains authoritative** for token values, type, finding states, primitives,
  focus, motion, contrast, density, elevation and Studio behavior.
- **v2 is authoritative** for Public v4 composition archetypes, composite anatomy,
  responsive recomposition and the way those existing primitives are assembled on the
  canonical Public routes.
- `PRODUCT.md` and `docs/35-public-product-architecture-v3.md` remain authoritative for
  product truth and information architecture.
- `docs/38-public-visual-redesign-v4-selection.md` records the selected visual direction;
  this file turns that direction into implementation rules.

If a visual prototype contains a literal that differs from v1, the token wins. The
prototype is composition evidence, not a second token source.

---

## 1. Reconciliation decision: zero new tokens

DP-424 does **not** justify a new palette, spacing step, radius, type step, shadow,
gradient, motion value or breakpoint token.

The selected direction can be expressed with the existing v1 inventory:

| v4 need | Existing contract |
|---|---|
| paper reading ground | `--paper-0` |
| selected event ground | `--paper-selected` |
| bounded source/control ground | `--paper-raised` |
| primary/secondary/meta ink | `--ink-900` / `--ink-700` / `--ink-500` |
| interaction + Segno | `--cobalt-600..800` |
| separators | `--rule-hairline` / `--rule-hairline-strong` |
| interactive borders | `--rule-control` / `--rule-control-strong` |
| serif/sans/mono roles | `--font-claim` / `--font-ui` / `--font-data` |
| display/title/row/body/meta scale | existing `--text-*` steps |
| Public rhythm | existing `--density-*` Public values |
| reading/shell/rail measures | `--width-reading` / `--width-shell` / `--width-rail` |
| touch floor | `--target-min` |
| focus | existing 3-part focus contract |
| state change motion | existing duration/easing tokens |

**Binding rule:** implementation work for DP-426–DP-429 and DP-405–DP-409 must not copy
literal values from `prototypes/v4-ledger-spine/`. It composes the existing tokens and
primitives described here.

### Prototype normalization

The DP-424 prototype used a visible resting cobalt rail beside the Home search to make the
direction obvious in a static screenshot. v2 normalizes that gesture to the existing Segno
semantics: **the search receives the Segno on `:focus-within`, not merely because it is on
Home**. The field can still be the dominant first-viewport object through scale, placement,
ground and whitespace. This prevents the brand gesture from becoming decoration.

The Statement source context and Trace event may show the Segno at rest because they are
actual current selections.

---

## 2. The three Public composition archetypes

Every canonical Public route must begin from one of these archetypes. A page can mount a
special module inside an archetype; it may not invent a fourth layout grammar.

### 2.1 Entry / index

**Routes:** Home and Explore.

**User job:** enter the record quickly, then scan repeated public objects.

**DOM order:**

1. `PublicHeader`;
2. page promise/title;
3. `SearchStage`;
4. optional result-type controls / progressive filters;
5. result or proof list;
6. secondary trust path;
7. `PublicFooter`.

**Desktop:** the search occupies the main reading flow; it does not become a narrow
sidebar. Repeated records are rows. Explore may add a compact control row before results,
but the results stay the visual mass.

**Phone:** same DOM order. The search action may move below the input within the form.
Advanced filters move into `FilterSheet`; primary result-type choice remains visible when
it materially changes the result set.

**Home-specific rule:** one sentence explains the product, universal search is the
primary conversion, recent Statements prove the product, and Method is secondary. No
signup CTA, KPI strip, people grid, topic mosaic, testimonial band or generic AI hero.

### 2.2 Record

**Routes:** Statement, Person, Topic, Content and Trace.

**User job:** understand one durable public object and follow its source/history paths.

**DOM order:**

1. `PublicHeader`;
2. `RecordHeader` — public type label, canonical title/wording, core identity metadata;
3. the record's primary interpretive block, if any;
4. main record content in reading order;
5. contextual/source/provenance material;
6. related record paths;
7. `PublicFooter`.

Desktop may place contextual material in the rail **only when that does not change the DOM
reading order**. Phone turns the rail into inline content or a native `Disclosure`.

Record pages share structure, not information architecture. Person remains a chronology,
Topic a dossier, Content a source container, Statement a verification record, and Trace a
reviewed longitudinal thread.

### 2.3 Trust document

**Routes:** Method, Corrections, Data & API and Project.

**User job:** understand how the record is made, corrected, governed or consumed.

**DOM order:** title + brief -> document sections -> supporting navigation/actions.

Use `--width-document` for prose. A `SectionIndex` may occupy the margin on desktop and
must become an inline jump list or disclosure on phone. These pages do not inherit Record
finding chrome just because they discuss findings.

No hero illustration, marketing card grid or product-feature tiles are needed. Trust is
carried by precise prose, examples, policies and links to the public record.

---

## 3. Public composite inventory

The v1 primitive inventory remains the ceiling underneath these composites. A composite
is an assembly contract, not permission to duplicate a primitive's CSS.

| Composite | Built from | Public job | Primary owners |
|---|---|---|---|
| `PublicHeader` | semantic header/nav + `Disclosure` where useful | identity, Explore, Method, Search | DP-426 |
| `SearchStage` | `TextField`, optional `Button`, links | enter the public index | DP-426, DP-429 |
| `StatementRow` | `Row` + `StatusText` | repeated claim-first record | DP-426, DP-405, DP-406, DP-429 |
| `FindingSummary` | `StatusText` + concise answer copy | state + bounded conclusion for one Statement/event | DP-427, DP-408 |
| `SourceEvidenceItem` | semantic anchor/list item + row anatomy | source, date, publisher/type, locator | DP-427, DP-407 |
| `SourcePath` | source item + selected/open Segno | expose original context without a detached metadata box | DP-427, DP-407 |
| `ChronologyIndex` | `<ol>` + real buttons + selected Segno | select reviewed events on Trace | DP-408 |
| `EvidenceTape` | existing v1 primitive | compact timed-media chronology/navigation | DP-407 |
| `PublicDisclosure` | existing `Disclosure` | technical provenance / secondary material | DP-427, DP-428 |
| `FilterSheet` | `Dialog` placement=`sheet` + controls | progressive phone filtering | DP-405, DP-406, DP-429 |
| `UtilityDocument` | document measure + optional `SectionIndex` | Method/Corrections/Data/Project | DP-428 |
| `PublicFooter` | semantic footer/nav | trust/utilities | DP-426 |

No `Card`, `Badge`, `Score`, `KPI`, `PersonStatus`, `TruthMeter`, `Trend`, `AIAnswer`,
`ChatBox` or generic `Timeline` is admitted by v2.

### Existing primitive reuse

The following already exist in `web/src/components/design/` and should be reused rather
than re-authored: `Surface`, `Hairline`, `Row`, `StatusText`, `SectionIndex`, `Disclosure`,
`Dialog`/`Sheet`, `SegmentedControl`, `TextField`, `Button`, `Skeleton`, `EmptyState`,
`ErrorState`, `EvidenceTape`, `FocusRing`, and `VisuallyHidden`.

The v4 page tickets may add only the composites whose semantics cannot be represented by
those primitives. If a composite becomes a thin one-use wrapper, delete it and compose
the primitives directly.

---

## 4. Composite contracts

## 4.1 `PublicHeader`

### Anatomy

- home link containing the cobalt square brand mark and “Dichiarazioni Pubbliche”;
- primary nav: **Esplora**, **Metodo**;
- compact **Cerca** path;
- optional quiet masthead note (“Registro pubblico delle dichiarazioni” / “Fonti · tempo ·
  correzioni”);
- phone menu only when needed for the same destinations.

`Fact-check`, Persone, Temi, Contenuti and Tracce are not permanent main-nav items. They
are object types and contextual destinations owned by Explore and record pages.

### States

- active route: text emphasis plus cobalt structural cue; `aria-current="page"`;
- hover: ink/link change only;
- focus-visible: v1 focus ring, never underline alone;
- phone menu open: native expanded state; no second navigation taxonomy.

The brand mark is the cobalt square described by `DESIGN.md`, not text such as `A/A`, a
quotation mark, or an icon package glyph.

## 4.2 `SearchStage`

### Anatomy

1. visible contextual heading such as “Cerca nel registro”;
2. `TextField` with an accessible label and real search form;
3. submit action;
4. optional short hint/examples;
5. optional `Esplora tutto` path.

### Behavior and states

| State | Contract |
|---|---|
| default | `paper-raised` control ground, control-grade border; no resting Segno |
| hover | stronger control rule on the actual interactive target |
| focus-within | **Segno appears** + existing focus treatment; search remains a real form |
| active/submit | existing `Button` active state; no streaming/generation affordance |
| disabled | only when search truly cannot be used; explain why outside the field |
| loading | result region gets `aria-busy`; do not replace the input with a spinner |
| empty | `EmptyState` names what was searched and how to broaden it |
| error | `ErrorState` / field error names the system problem and recovery |

Home may make the SearchStage wider and more prominent than Explore, but it does not get
a new token set.

## 4.3 `StatementRow`

Use `Row` rather than a card.

Required reading order: date/time when useful -> exact statement -> person + source
metadata -> local `StatusText` -> real destination link. The finding always belongs to
the Statement, never to the person.

### Desktop

Lead/date may occupy a fixed ledger column; claim gets the flexible reading column;
finding may occupy a trailing column. Do not repeat a decorative arrow if the stretched
real anchor already communicates the destination.

### Phone

Statement first, metadata immediately below it, date folded into metadata when horizontal
space is scarce, finding after the claim/meta block. Never hide the finding merely to make
the row fit; if the first viewport proof omits it visually, the implementation still keeps
it in the row's semantic reading sequence.

States inherit `Row`: default, hover, selected, selected+hover, focus-visible and
non-interactive. Loading/empty/error belong to the containing list, not to each row.

## 4.4 `FindingSummary`

The component has exactly two semantic parts:

1. the written finding word rendered by `StatusText`;
2. a concise answer/rationale summary in ordinary text.

Optional publication/version metadata is separate. There is no numeric confidence,
truth percentage, severity meter, person aggregate or status-only color block.

The summary can sit below a Statement header or inside selected Trace/Content detail. It
does not become a reusable “verdict card.”

## 4.5 `SourceEvidenceItem`

### Anatomy

- source/evidence index or source type when useful;
- publisher/title;
- short approved descriptor;
- publication date when available;
- real source/locator destination;
- external-destination affordance when appropriate.

Use an anchor when the whole item has one destination. Use `Row` only when it genuinely
shares Row semantics; do not nest interactive controls inside a stretched row anchor.

Missing provenance is explicit (“Fonte non disponibile” / equivalent bounded public
copy) and must never be replaced by a fabricated URL, source title or locator.

## 4.6 `SourcePath`

The SourcePath is the v4 Statement/Content composition that keeps original context close
to the finding.

### Anatomy

- section heading (“Contesto originale” or source-type equivalent);
- concise explanation only when the source path is not self-evident;
- current source/content moment;
- timestamp/paragraph/section locator;
- source destination;
- optional person/content/version context below, separated by hairlines.

The currently inspected item may use `paper-selected` + Segno. A non-selected source item
does not. Technical provenance belongs in `Disclosure`, not in a permanent metadata wall.

## 4.7 `ChronologyIndex`

This is the v4 Trace signature component. It is **not** a causal graph and does not replace
`EvidenceTape` for timed media.

### Semantic shape

```text
section[aria-labelledby]
  ol
    li
      button(date + event wording + event type)
    ...
  selected-detail-region
```

Exactly one event may be current. The button receives `aria-current="true"`; the event
also gets `paper-selected` + Segno. Other events remain neutral even when their Statements
have different findings.

### Desktop

Chronology index occupies the narrower ledger column; selected detail occupies the
reading column. The detail exposes exact wording, person/source/date, local finding,
bounded “cosa cambia” explanation and source path.

### Phone

The selected detail is placed **immediately after the current event in DOM order**. Do not
render a detached detail pane after the entire list and use CSS `order` to fake the visual
position: assistive technology and keyboard reading order must match the screen.

### States

| State | Contract |
|---|---|
| default | paper ground, neutral ink, no status hue |
| hover | neutral ground shift / stronger control rule |
| focus-visible | v1 focus ring on the real button |
| active | pressed control state only |
| selected/current | `paper-selected` + cobalt Segno + `aria-current` |
| disabled | normally not admitted; published events should remain inspectable |
| loading | chronology region `aria-busy`, stable skeleton geometry |
| empty | no fake one-event timeline; explain that no reviewed trace exists |
| error | system `ErrorState`, never a finding word |

No line or arrow may imply one event caused another. Chronology is ordering plus reviewed
relation metadata, not intent inference.

## 4.8 `EvidenceTape`

Keep the existing v1 component for Content timed-media moments and other compact temporal
navigation with at least two marks. It remains neutral until current. v4 does not turn it
into a colored outcome distribution.

On phone the tape may scroll horizontally, but every mark keeps a `--target-min` hit area,
real button semantics and an accessible full label.

## 4.9 `PublicDisclosure`

Use the existing native `Disclosure` for technical provenance, long method caveats and
secondary source details. Open state owns a Segno; closed state does not. Summary text must
describe what will be revealed, not say only “Dettagli”.

Nothing required to interpret the primary finding may be hidden behind a disclosure.

## 4.10 `FilterSheet`

Desktop filters may be inline when they remain short and legible. On phone, secondary
filters move into the existing `Dialog`/Sheet behavior.

Required behavior: visible title, initial focus, native Escape/cancel, focus restoration,
Apply and Reset actions with real labels, and no filter change hidden behind hover.

Filter choice is not a status, so selected filters use selection semantics rather than
finding hues.

## 4.11 `UtilityDocument`

Method, Corrections, Data & API and Project share document grammar, not identical content.

- title uses claim/title voice only when it is genuinely a heading, not as decoration;
- intro uses `--measure-brief` or document measure;
- body stays within `--width-document`;
- sections use whitespace first, hairlines only for real grouping;
- optional `SectionIndex` is contextual navigation;
- code/API examples may use mono only for actual code/data;
- corrections are chronological public history, not a feed of “mistakes”.

Loading/empty/error states use the shared state components. Data/API examples must be real
contract examples, not invented usage metrics.

---

## 5. Cross-component state matrix

This matrix is the minimum implementation/review checklist. “N/A” means the component
does not invent a fake form of that state.

| Component | hover | focus-visible | active | selected/open | disabled | loading | empty | error |
|---|---|---|---|---|---|---|---|---|
| PublicHeader link | yes | yes | yes | active route | N/A | N/A | N/A | N/A |
| SearchStage | field/action | yes | submit | focus-within Segno | when truly blocked | result region | shared EmptyState | field/shared ErrorState |
| StatementRow | yes | yes | link press | optional selected | N/A for published link | list region | list EmptyState | list ErrorState |
| FindingSummary | N/A | links only | links only | N/A | N/A | parent region | omit only when product contract permits | system error is separate |
| SourceEvidenceItem | yes | yes | link press | current only inside SourcePath | unavailable source is non-link, not disabled UI | parent region | explicit absence copy | parent ErrorState |
| SourcePath | links | links | links | current/open Segno | N/A | stable region | explicit unavailable context | ErrorState |
| ChronologyIndex | yes | yes | button press | current event | normally N/A | aria-busy + skeleton | no fake timeline | ErrorState |
| EvidenceTape | yes | yes | button press | current mark | N/A | parent region | renders nothing <2 marks | parent ErrorState |
| Disclosure | summary hover | yes | native | open Segno | N/A | child region | N/A | child ErrorState |
| FilterSheet | controls | yes | yes | selected controls | yes where unavailable | action busy | “nessun filtro” is not an error | visible recovery |
| UtilityDocument | links | links | links | SectionIndex current | N/A | document region | explicit when meaningful | ErrorState |

**Finding states and system states remain separate vocabularies.** A source fetch failure
must never render “Contraddetta”; an unresolved Statement must never render as an error.

---

## 6. Responsive and DOM rules

The v1 rule remains: **mobile is recomposed, not stacked**. v2 makes the expected
recomposition explicit per archetype.

### Public-wide invariants

- canonical content order in the DOM is the order a screen reader should encounter it;
- CSS Grid may change columns but may not make a later semantic region appear to come
  earlier than it does in the DOM;
- no horizontal page overflow at 320px;
- every standalone touch target is at least `--target-min`;
- metadata never drops below `--text-meta`;
- no interaction exists only on hover;
- `prefers-reduced-motion` reaches the same end state without animation;
- hidden phone simplification may remove duplicated decoration, never source/finding text
  required to understand the record.

### Entry/index

Desktop: title/brief -> wide SearchStage -> controls/results.

Phone: title/brief -> SearchStage with full-width input/action -> visible primary type
choice -> results -> filter-sheet trigger. Result rows become statement-first.

### Record

Desktop: RecordHeader -> primary interpretive block -> reading column + contextual rail.

Phone: RecordHeader -> primary interpretive block -> context/source material at its
semantic insertion point -> verification/body -> related/history. Context is not pushed to
the very bottom merely because it was a desktop rail.

### Trace

Desktop: chronology index + selected-detail reading pane.

Phone: chronological event -> current event -> its detail -> following events. This must
be implemented by semantic rendering, not visual-only reordering.

### Trust document

Desktop: document + optional margin index.

Phone: document first; jump/index becomes inline before the sections it navigates or a
native disclosure.

---

## 7. Copy and public-vocabulary guardrails

Components must not smuggle legacy/internal taxonomy into the new IA.

### Public vocabulary

Prefer: Dichiarazione, Persona, Tema, Contenuto, Traccia nel tempo, Verifica, Fonte,
Contesto originale, Metodo, Correzioni, Dati & API, Progetto.

### Private/legacy vocabulary banned from primary Public chrome

`Fact-check` as a permanent nav destination, `ContentAudit`, raw finding/relation IDs,
pipeline stage names, provider/model names, “AI-powered”, model confidence and internal
review labels.

Internal concepts may appear in Method/Data documentation when explaining the system and
when doing so is actually useful; they are not page-template labels.

---

## 8. Visual proof rubric for page tickets

DP-426–DP-429 and DP-405–DP-410 may not call a Public page visually complete from a
desktop happy-path screenshot alone.

Each page ticket must provide, where applicable:

1. desktop proof at the Public shell width;
2. phone proof at a narrow viewport, with no horizontal overflow;
3. keyboard focus proof for the page's primary interactive surface;
4. selected/open proof when the page has Segno state;
5. empty state for search/list surfaces;
6. system error state where a runtime dependency can fail;
7. loading state where content can arrive asynchronously;
8. 200% zoom sanity check on the page's primary job;
9. reduced-motion check for authored state transitions;
10. `npm run check:design`, `npm run check`, `npm run build`, and route-specific tests.

Screenshot review asks five questions:

- Is there exactly one dominant first-viewport task?
- Is the Statement/source/evidence reading path obvious without decorative UI?
- Is every finding a word and local to a Statement/event?
- Is the Segno attached only to actual focus/selection/open/current state?
- Does the phone version preserve the semantic order rather than merely hide desktop
  columns?

---

## 9. DP-424 proof mapping

The selected proof is stored under `prototypes/v4-ledger-spine/`.

| Proof | v2 contracts demonstrated |
|---|---|
| Home desktop/phone | Entry/index, PublicHeader, SearchStage, StatementRow |
| Statement desktop/phone | Record, RecordHeader, FindingSummary, SourceEvidenceItem, SourcePath |
| Trace desktop/phone | Record, ChronologyIndex, selected Segno, local FindingSummary, source detail |

The proof is intentionally narrower than the final site. Person, Topic, Content, Explore
and trust documents reuse these contracts and their own page jobs from
`docs/35-public-product-architecture-v3.md`; they must not be forced into one of the three
screens by visual imitation.

---

## 10. Implementation ownership and deletion test

DP-425 freezes the contract; page tickets own adoption.

- DP-426: PublicHeader, PublicFooter, Home/SearchStage shell.
- DP-427: Statement RecordHeader, FindingSummary, SourcePath, source/evidence list.
- DP-405: Person record composition + StatementRow chronology.
- DP-406: Topic dossier composition.
- DP-407: Content + existing EvidenceTape/source moment behavior.
- DP-408: ChronologyIndex + Trace selected detail.
- DP-409/DP-429: static index + complete Explore/SearchStage/filter behavior.
- DP-428: UtilityDocument family.
- DP-410: final accessibility/performance/SEO/mobile gate.

Before adding a new component during those tickets, answer:

1. Which user decision/job does it support?
2. Why can the existing v1 primitive or a v2 composite not express it?
3. Does it introduce a new visual/state vocabulary?
4. Can it be deleted without losing semantics?

If the answer to (2) is weak or (3) is yes, do not add it.

---

## 11. What v2 deliberately does not change

- no token literal changes;
- no finding-state change;
- no Studio density change;
- no font change;
- no new dependency;
- no new route;
- no account/login/follow/save UI;
- no person score, ranking, verdict aggregation or trend dashboard;
- no shadow or gradient;
- no live LLM interaction in a Public request path.

This is a compositional evolution of the same civic-ledger system, not a rebrand of the
rebrand.

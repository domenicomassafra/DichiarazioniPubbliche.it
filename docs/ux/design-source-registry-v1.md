# Dichiarazioni Pubbliche — Design Source Registry v1

Date: 2026-09-23  
Status: research/implementation-source registry; every source must be re-checked before
vendoring code

## Why this exists

The goal is not a bookmark list. Before creating a common UI element from scratch, Agli
Atti should search a curated set of high-quality sources for proven behavior, accessibility
and implementation patterns.

Registry fields:

`source -> role -> component/pattern -> stack -> use mode -> license -> Dichiarazioni Pubbliche mapping`

Use modes:

- **FOUNDATION** — candidate behavioral/code foundation;
- **ADAPT** — borrow anatomy/interaction, restyle/rewrite for Dichiarazioni Pubbliche;
- **REFERENCE** — visual/UX reference only unless a specific artifact license is verified.

## Preferred sources

| Source | Role | Useful for Dichiarazioni Pubbliche | Mode | License / caution |
|---|---|---|---|---|
| shadcn/ui | open-code component foundation | Button, Input, Sheet, Dialog, Popover, Tabs, Tooltip, Dropdown, Command, Skeleton | FOUNDATION / ADAPT | open source/open code; use official `ui.shadcn.com`, not random registries |
| Radix Primitives | accessible headless behavior | Dialog, Popover, Tooltip, Tabs, Select, Dropdown, Collapsible | FOUNDATION | open-source primitives; strong focus/keyboard semantics |
| Origin UI | component variation donor | search inputs, filters, select, pagination, timeline, table, stepper, date controls | ADAPT | MIT; copy only selected components, then normalize to our tokens |
| TanStack Table | table/list state engine | Studio tables, sortable/filterable evidence lists if needed | FOUNDATION | headless; styling/semantics remain ours |
| GOV.UK Design System | content/disclosure guidance | Details, accordion decision rules, heading/list clarity | REFERENCE / ADAPT | use as behavior/content guidance; do not make Dichiarazioni Pubbliche look governmental |
| USWDS | accessibility/content guidance | typography legibility, accordions, focus/touch guidance | REFERENCE / ADAPT | public-service clarity, not visual branding |
| IBM Carbon | dense enterprise interaction reference | data-table keyboard behavior, compact/tall density concepts | REFERENCE | do not adopt Carbon visual skin wholesale |
| Vidstack | media-player foundation | accessible player, captions, chapters, keyboard, YouTube/Vimeo/native media | FOUNDATION candidate | MIT according to current docs; verify exact version before adoption |
| Observable Plot | evidence visualization | small time series, comparisons, directly labeled charts | FOUNDATION candidate | ISC; good default before reaching for D3 |
| D3 / Visx | bespoke visual fallback | unusual evidence visuals where Plot is insufficient | FOUNDATION candidate | only when justified by a factual question |
| Motion / Motion Primitives | restrained state transition patterns | selected-row transitions, disclosure/sheet motion, small state changes | ADAPT | Motion Primitives MIT; no decorative marketing effects |
| Lucide | icon baseline | search, filter, source, media, calendar, correction, disclosure icons | FOUNDATION candidate | ISC; consistent stroke language |
| 21st.dev | discovery index | tables, timelines, search, filters, media, empty states | REFERENCE | multi-author registry; artifact-by-artifact license review required |
| shadcn.io | discovery index | pattern census, charts, search/table variations | REFERENCE | third-party; free/pro licensing differs, verify exact resource before use |
| Component Gallery / Design System Gallery | comparative pattern research | compare same component across systems | REFERENCE | research index, not a dependency |
| Mobbin / Refero / Pageflows / UI Sources | real-product UX research | search/filter flows, mobile sheets, media detail, dense workspaces | REFERENCE | reproduce interaction principles, not proprietary visual assets |

## Research verification — 2026-09-23

Current upstream checks supporting the registry choices:

- **shadcn/ui** explicitly positions itself as open code for building your own component
  library/design system rather than a visual package to keep pristine; its current catalog
  includes the primitives we need such as Dialog, Sheet, Popover, Tabs, Tooltip, Table,
  Data Table and Command: <https://ui.shadcn.com/>.
- **Radix Primitives** remains an unstyled accessible primitive layer with focus management,
  keyboard navigation and WAI-ARIA-oriented behavior for Dialog, Tabs, Tooltip, Select,
  Popover and related controls: <https://www.radix-ui.com/primitives>.
- **Origin UI** currently exposes broad copy-paste families directly relevant to this
  product — including 59 Input, 51 Select, 20 Table, 20 Tabs, 17 Stepper and 12 Timeline
  examples — and its upstream repository states MIT licensing:
  <https://originui.com/>.
- **TanStack Table** remains headless: it supplies filtering, sorting, pagination,
  selection and other table state while leaving markup and visual design under our
  control: <https://tanstack.com/table/>.
- **Vidstack** provides customizable accessible media-player primitives, captions,
  keyboard behavior, chapters and multiple providers; current docs state MIT licensing:
  <https://vidstack.io/>.
- **Observable Plot** is a concise open-source visualization grammar suitable for standard
  evidence charts before reaching for lower-level custom D3 work; upstream declares ISC:
  <https://observablehq.com/plot/>.
- **Motion Primitives** supplies open-source Motion/Tailwind interaction examples and is
  MIT licensed. We use it as a restrained motion-pattern donor, not as an animated brand
  layer: <https://motion-primitives.com/docs>.
- **GOV.UK** and **USWDS** both explicitly warn against hiding content in accordions when
  most users need to see it. That directly supports Dichiarazioni Pubbliche's rule that rationale and
  primary sources stay visible: <https://design-system.service.gov.uk/components/accordion/>
  and <https://designsystem.digital.gov/components/accordion/>.
- **21st.dev** is useful as a very broad multi-author discovery registry rather than a
  canonical dependency. Exact components need artifact-level code/license review before
  use: <https://21st.dev/community/components>.
- **shadcn.io** is a third-party ecosystem around shadcn/ui, not the official shadcn/ui
  site. It is useful for discovery, but its free/pro resources have different licensing
  conditions and therefore remain REFERENCE unless the exact artifact is cleared:
  <https://www.shadcn.io/>.

## Component-by-component donor map

### Search

Dichiarazioni Pubbliche component: `SearchField`

Study first:

1. shadcn/ui Input + Command anatomy;
2. Origin UI input/search variations;
3. GOV.UK/USWDS plain search clarity;
4. real-product search flows in Refero/Mobbin.

Decision:

- public search remains one rectangular field with conventional magnifier;
- no prompt-composer styling;
- optional submit arrow/button only when it improves keyboard/mobile clarity;
- autocomplete/results popover is a later behavior, not visual decoration.

### Filter controls

Dichiarazioni Pubbliche: `FilterBar`, `FilterSheet`, select/popover controls.

Study first:

- Origin UI Select/Popover/Date controls;
- Radix Popover/Select/Dialog;
- shadcn Sheet;
- real mobile filters in Mobbin/Pageflows.

Decision:

- desktop shows only high-value filters;
- mobile uses one `Filtri (N)` trigger -> sheet;
- active filters remain visible as compact text/chips but do not become the page texture.

### Tabs / mode navigation

Dichiarazioni Pubbliche: Record modes, Explore result types, Studio transcript/details modes.

Study first:

- Radix Tabs keyboard model;
- GOV.UK guidance on when **not** to use tabs;
- Origin UI tabs variations.

Decision:

- use real tabs only when switching same-page panels quickly;
- use links/anchors when the destination is navigational/document structure;
- no nested tabs.

### Dialog / Sheet / Popover

Use Radix/shadcn behavior as the preferred reference for focus trap, dismissal, screen
reader naming and keyboard behavior.

Applications:

- mobile FilterSheet;
- source detail sheet;
- bounded evidence preview;
- confirmation dialogs for private Studio actions.

Never use modal dialogs for normal public reading.

### Disclosure / Accordion

Study GOV.UK Details + Accordion and USWDS guidance first.

Decision:

- `Details`-style disclosure for one or two secondary sections;
- accordions only when several optional peer sections exist;
- primary rationale and primary sources are **never** hidden merely to shorten the page;
- no nested accordions.

### Tables and dense rows

Dichiarazioni Pubbliche: mostly custom list rows; true tables only when data is genuinely tabular.

Study:

- TanStack Table for state logic;
- Carbon for keyboard/accessibility and density reference;
- Origin UI table variants for small interaction patterns.

Decision:

- Public ClaimRow remains semantic list/article content unless columns genuinely represent
  comparable tabular data;
- Studio evidence tables may use TanStack logic with Dichiarazioni Pubbliche markup;
- sortable columns expose `aria-sort` and persistent sorted state.

### Status / Assessment

Do not import a third-party badge aesthetic.

Build a custom text-first `Assessment` using our semantic tokens. A small square/dot/rule
may reinforce state but never replace the word.

Avoid the repeated rounded-pill wall visible in generic SaaS libraries.

### Evidence visualization

Dichiarazioni Pubbliche: `EvidenceVisual`.

Preferred order:

1. static semantic HTML/table if it explains the comparison best;
2. Observable Plot for standard charts;
3. custom SVG/D3/Visx only for a genuinely bespoke explanation.

Every visual needs:

- one factual question/takeaway;
- direct labels where possible;
- a source note;
- text/table fallback;
- no decorative animation.

### Evidence Tape / Timeline

Dichiarazioni Pubbliche: `EvidenceTape`.

Reference sources:

- Origin UI timeline variants for anatomy only;
- 21st.dev timeline census for breadth;
- Motion/Motion Primitives for selection/cursor transitions;
- Descript/Factiverse patterns from the existing research for media synchronization.

Decision:

- implement as a custom Dichiarazioni Pubbliche component;
- do not vendor a generic colorful timeline component;
- chronological marks stay neutral unless a selected item exposes its Assessment locally;
- few touchable marks on mobile.

### Media player

Candidate foundation: Vidstack.

Reasons:

- accessible player primitives;
- captions, keyboard controls, chapters, thumbnails and multiple providers;
- fully styleable rather than forcing a video-site skin.

Dichiarazioni Pubbliche-specific layer adds:

- claim markers;
- jump-to-claim;
- synchronized transcript selection;
- bounded public clip/moment behavior.

### Transcript

`TranscriptLine` is custom.

Borrow behavior, not appearance, from media/research tools:

- timestamp gutter;
- selected range highlight;
- keyboard jump;
- selected claim and player cursor stay synchronized.

### Motion

Use Motion/Motion Primitives as implementation references for predictable transitions.

Allowed donor patterns:

- animated height/disclosure;
- layout-group row selection;
- sheet/dialog transitions;
- cursor position interpolation.

Reject:

- glowing borders;
- particle backgrounds;
- animated text reveals;
- cursor gimmicks;
- marketing marquees;
- parallax.

## Source tiers

### Tier A — first-choice behavior/code research

- shadcn/ui official;
- Radix Primitives;
- Origin UI;
- TanStack Table;
- Vidstack;
- Observable Plot;
- Lucide;
- GOV.UK / USWDS accessibility guidance.

### Tier B — specialist donor research

- Motion Primitives;
- Carbon;
- D3 / Visx;
- real-product pattern libraries (Mobbin, Refero, Pageflows, UI Sources).

### Tier C — discovery only

- 21st.dev;
- shadcn.io;
- Magic UI;
- Aceternity;
- React Bits;
- Uiverse;
- CodePen/Codrops.

Tier C is valuable for discovering patterns but is **not** an aesthetic authority for Agli
Atti. Highly animated/marketing-oriented components must pass the product-job and anti-slop
gates before consideration.

## License gate

Before code is copied into the repository, record:

```text
source_url
upstream_repository
exact_component_or_file
upstream_commit_or_version
license
copyright_notice_required
modified_by_dichiarazioni_pubbliche
local_destination
```

Do not copy premium, unclear-license or account-gated component code. Use such sources only
as visual/interaction references until explicit permission is verified.

## Registry expansion

The attached research list already demonstrates why this should become a structured
registry rather than a set of bookmarks: the useful universe spans copy-paste components,
motion, design systems, UX pattern libraries, data visualization, icons, forms and media.

Future registry work should add machine-readable fields for:

`category`, `stack`, `free/open/freemium`, `component_type`, `style`, `motion`,
`accessibility`, `source_code_copyable`, `registry_or_mcp`, `license`, `url`,
`last_verified`, and `approved_use_mode`.

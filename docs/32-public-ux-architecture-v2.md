# Dichiarazioni Pubbliche — Public UX Architecture v2

Date: 2026-09-23  
Status: current for Public; the two-template private Studio constraint is superseded by
DP-414 / the Research Corpus architecture; PRODUCT.md and ADRs remain authoritative

## Why v2 exists

The first visual concepts and IA research proved useful, but they also exposed a common
failure mode: too many cards, panels, counters, badges and micro-dashboards made Agli
Atti look like an AI concept render rather than a deliberate public product.

This v2 reduces the product before visual polish. It defines the minimum page hierarchy,
the minimum reusable component grammar and the boundary between the public product and
the private Verify Studio.

The design objective is **clarity through omission**.

## One product model, seven primary screens

### Public — five templates

1. **Home** — understand, search, see recent checks.
2. **Explore** — search and filter the public record.
3. **Fact-check** — understand one finding and inspect its evidence.
4. **Record** — one reusable chronological template for Person or Topic.
5. **ContentAudit** — inspect a verified video/podcast/content item over time.

### Private Verify Studio — historical two-template baseline

6. **Sessions** — create/find/resume analyses.
7. **Workspace** — media/transcript, claims, evidence and review for one analysis.

This remains useful as the Verify mode inside Studio, but is no longer the complete
private information architecture. Corpus search, Discovery Inbox and Research Collection
workspaces are specified by DP-414 after the first-class Research Corpus contract lands.

Method, corrections, about, contribution and similar informational pages are normal
documents, not separate product architectures.

## Navigation

Public primary navigation:

```text
Dichiarazioni Pubbliche        Fact-check   Esplora   Metodo        Cerca
```

`Persone`, `Temi` and `Video/Podcast` are exploration modes and links within the public
record. They do not need to consume permanent top-level navigation slots.

Private Studio navigation:

```text
Verify Studio        Sessioni        + Nuova verifica
```

Secondary operator/admin capabilities appear contextually. Avoid an enterprise sidebar
until the product genuinely requires one.

## 1. Home

The homepage has exactly four jobs:

1. explain Dichiarazioni Pubbliche in one sentence;
2. search existing public checks;
3. show a small recent-check stream;
4. show one distinctive ContentAudit/media example and paths to Explore/Method.

Recommended mobile-first order:

```text
Dichiarazioni Pubbliche                                   Search / Menu

Verifica ciò che viene detto.
Fact-checking di dichiarazioni, video, podcast e articoli. Con le fonti.

[ Cerca una verifica __________________ ]

Ultime verifiche

date · topic
"checked statement"
finding state                                           ->
-----------------------------------------------------------
date · topic
"checked statement"
finding state                                           ->
-----------------------------------------------------------
date · topic
"checked statement"
finding state                                           ->

Tutte le verifiche ->

Sotto la lente
[ one media/content audit feature ]
[ compact claim-moment timeline ]
Esplora l'analisi ->

Esplora il record
Persone · Temi · Video e podcast

Come verifichiamo ->
```

### Home exclusions

Do not add:

- KPI walls;
- rankings or "most checked" people;
- simultaneous people + topics mini-dashboards;
- decorative charts;
- manifesto quotations competing with the main purpose;
- a generic hero photo simply to fill half the viewport;
- a chatbot pretending that search equals a new live analysis;
- four symmetric verdict cards simply because they compose well visually.

The homepage search searches **already published public records**. A future
`Proponi una verifica` action is a separate queue/intake feature.

## 2. Explore

Explore owns archive complexity so the homepage does not have to.

Structure:

```text
Esplora

[ Cerca dichiarazioni, persone, temi, video... ]

Tutto · Fact-check · Persone · Temi · Video/Podcast

[ Filtri (3) ]                        Più recenti v

date
checked statement
speaker/source · topic                  finding state  ->
-----------------------------------------------------------
...
```

Desktop may add a compact persistent filter rail when the corpus justifies it. Mobile
uses one `Filtri` control that opens a sheet/drawer and shows the active-filter count.

Avoid permanent filter walls before the user has chosen to filter.

## 3. Fact-check

This is the most important public reading template.

The content hierarchy is fixed:

1. claim/original wording;
2. speaker/origin, source, date and timestamp when applicable;
3. finding state;
4. one-sentence answer;
5. explanation/rationale;
6. key observations/numbers only when material;
7. reviewed sources;
8. original media moment;
9. context and limitations;
10. verification method/provenance;
11. corrections/right-of-reply;
12. reviewed longitudinal relations.

The default layout should read like an excellent evidence-backed article, not an admin
dashboard. On desktop a restrained side rail may hold source/media context, but the main
reading flow remains linear and mobile-compatible.

### Progressive disclosure

Primary evidence remains one deliberate interaction away. Technical provenance IDs,
verification versions and review-event IDs are available in a secondary disclosure.

Do not hide the actual rationale or primary sources in an accordion merely to make the
page shorter.

## 4. Record — Person or Topic

Person and Topic use the same underlying page grammar instead of becoming two separate
mini-products.

### Person header

- name;
- current/relevant public role context;
- optional bounded biography/role-history link.

### Topic header

- topic name;
- one-line scope/definition when necessary.

### Shared body

```text
Verifiche · Nel tempo · Media   (context-dependent tabs/filters)

[ topic/date/type filters ]

chronological ClaimRow stream

optional neutral chronology/navigation
```

### Record exclusions

Do not show:

- truth percentages;
- reliability grades;
- supported/contradicted totals as a performance score;
- streaks;
- rankings;
- colorful timelines that visually turn a person's history into a scorecard;
- decorative counters such as "142 statements / 39 checks / 12 topics / 5 years" when
  they do not help the user complete a task.

Finding status belongs to each individual fact-check row. The person's chronology itself
stays visually neutral.

## 5. ContentAudit

ContentAudit is the signature media-first public surface.

### Public desktop

```text
content title / source / date / duration

[ media player ]

----o---------o---o----------------o------
  03:41     12:20 14:05          34:12

claim moments

03:41  checked statement                 finding state ->
12:20  checked statement                 finding state ->
14:05  checked statement                 finding state ->
```

Selecting a moment exposes that claim's concise finding and sources. It does **not** keep
video, full transcript, all claims, all evidence and all provenance permanently visible
at once.

### Public mobile

Player, compact timeline and claim-moment list stack vertically. A claim opens its normal
Fact-check detail or a near-full-screen detail sheet.

Raw/full transcript remains an operational/private object unless separate policy allows
a bounded public excerpt.

## 6. Verify Studio — Sessions

Sessions is intentionally boring.

```text
Verify Studio                                      + Nuova verifica

[ Cerca sessioni ]

In corso
source/content title             pipeline stage / claim progress ->
...

Recenti
...
```

Do not add weekly insight dashboards, "source reliability %", activity gamification,
template marketplaces or decorative analytics unless a later operator need proves them
necessary.

## 7. Verify Studio — Workspace

The Workspace is the one intentionally dense screen.

Wide layout:

```text
source/media/transcript | claims | selected claim/evidence/review
```

The selected claim is the organizing unit.

### Left

- media/source;
- timeline;
- synchronized transcript or extracted text;
- jump to the exact source segment.

### Center

- claim queue;
- timestamp/source location;
- compact pipeline state;
- check-worthy/review state when persisted.

### Right

- exact original wording;
- normalized claim;
- reviewed/retrieved evidence separated by state;
- structured observations;
- verification state/rationale;
- review actions.

### Pipeline status

Do not dedicate a permanent fourth dashboard column to the pipeline. Use a compact header
summary such as:

```text
Transcript complete · 14 claims · Evidence 8/14 · Verified 5/14
```

Detailed worker/provider state opens on demand.

Analysis, review and publication remain visually and technically separate.

## Minimal component grammar

Public v1 should be achievable with roughly ten strong conceptual components:

1. `ClaimRow` — main unit for lists, Explore and Record.
2. `Assessment` — state of one fact-check, text/icon first, color secondary.
3. `SourceRow` — publisher/source, descriptor, date/reference period, link.
4. `FactSummary` — checked statement + concise result.
5. `MediaMoment` — media/timestamp/source context.
6. `Timeline` — neutral chronological navigation.
7. `FilterBar` / mobile `FilterSheet`.
8. `EntityLink` — Person/Topic/Source link.
9. `Disclosure` — secondary method/provenance/context details.
10. `CorrectionNotice` — explicit version-aware correction/reply history.

Studio adds only:

11. `TranscriptLine`.
12. `ClaimQueueRow`.
13. `PipelineStatus`.

Do not create a component because a generated mockup drew a rectangle around something.

## Surface grammar — less chrome, more typography

Default presentation priority:

1. typography;
2. whitespace;
3. dividers/alignment;
4. background grouping only when necessary;
5. borders/cards only when the object is actually self-contained or interactive.

Avoid making every source, statistic, topic and sentence a floating rounded card.

Lists are the default for comparable records. Cards are reserved for genuinely discrete
visual objects such as a featured media item or a bounded interactive unit.

## Status and color

- finding state is always expressed in words;
- icons may reinforce but not replace text;
- color is secondary and must work in grayscale/color-blind use;
- political identity never receives finding colors;
- a Person Record never aggregates finding colors into an implicit score;
- unresolved/needs-more-evidence/under-review must look intentional, not broken.

## Mobile rules

Mobile is not desktop stacked mechanically.

- one content column;
- no persistent sidebars;
- filter controls collapse to a sheet;
- evidence and provenance open inline or full-height;
- media moments remain tappable without exposing the full transcript;
- primary claim, state, rationale and source path fit before secondary metadata;
- avoid sticky UI that leaves too little reading space.

## Design-language evaluation before implementation

Visual concept generation is now subordinate to this architecture.

The previous A/B/C generated images are **exploratory receipts only**. They are not
accepted design directions and should not be implemented literally.

Future image generation should compare visual languages against the *same v2 page
contracts*, ideally:

- Home desktop + mobile;
- Fact-check desktop + mobile;
- ContentAudit desktop + mobile;
- Studio Workspace desktop.

The winner is the system that makes these contracts clearer with the least decorative
UI, not the one that displays the most features in one screenshot.

## Acceptance

Before frontend implementation begins:

- every visible element on Home has one of the four defined jobs;
- Public uses only the five templates above;
- Person and Topic demonstrably share Record grammar;
- no person-level visual scoring can be inferred from aggregate UI;
- Fact-check remains comprehensible as a linear mobile reading flow;
- ContentAudit is media-first without becoming the Studio;
- Studio has exactly Sessions + Workspace as primary screens;
- no KPI/dashboard element exists without a real operator/user decision it supports;
- generated concepts do not override provenance/publication rules;
- all public pages can be rendered exclusively from the fail-closed public projection.

# Dichiarazioni Pubbliche — UI/UX Deep Design Research v3

Date: 2026-09-23  
Status: current visual-research brief; subordinate to `PRODUCT.md` and
`docs/32-public-ux-architecture-v2.md`

## Decision this research supports

Choose a distinctive, usable, durable visual/interaction language for the **whole Agli
Atti product**, not merely a homepage mood.

The system must work across the same frozen UX-v2 architecture:

- Public: Home, Explore, Fact-check, Record, ContentAudit;
- private Verify Studio: Sessions, Workspace;
- mobile variants of the public reading/search flows.

The research deliberately happens **before** `DESIGN.md`, final tokens, frontend code or
component-library selection. The output is five materially different prototypes that can
be generated screen-by-screen with GPT Image and judged against the same product jobs.

---

## What was read before proposing directions

The design pass was grounded in the local DStack/OpenCode skill corpus rather than
starting from visual taste alone.

Materially relevant skills inspected:

- `ui-ux-pro-max`;
- `site-architecture`;
- `design-variant-exploration`;
- `design-md`;
- `design-system`;
- `frontend-design`;
- `visual-critique`;
- `brand-guidelines`;
- `stitch-design`;
- `canvas-design`;
- `ui-styling`;
- `composition-patterns`;
- `mobile-webapp-pwa`;
- `accessibility-runtime-audit`;
- `page-cro`;
- `customer-research`;
- `deep-research`;
- gstack `design-consultation`;
- gstack `design-shotgun`;
- gstack `design-review`;
- gstack `plan-design-review`;
- Matt Pocock `prototype`.

### Skill-level consensus

The useful consensus is unusually strong:

1. **Screen job before styling.** Every screen must have a dominant user task and a
   first/second/third visual priority.
2. **Composition before components.** Starting from a card library produces generic UI.
3. **Subtraction is the default.** If an element cannot justify its pixels, remove it.
4. **Variants must be genuinely different.** Palette swaps are not exploration.
5. **Responsive is not stacking.** Phone flows must be intentionally recomposed.
6. **Accessibility is behavior.** Focus, keyboard, touch targets, contrast, reduced
   motion, long text, loading/error/empty states are design inputs.
7. **Motion explains change.** It must not simulate AI activity or decorate routine work.
8. **Trust is pixel-level.** Source visibility, state wording, corrections and predictable
   navigation matter more than trust slogans.
9. **Use real content shapes.** Fake metrics/testimonials and filler dashboards are design
   failures, even when visually polished.
10. **A repeated card grid is a warning sign.** A card is appropriate only when the object
    is genuinely self-contained/interactive.

### Important negative finding from automated design-system search

`ui-ux-pro-max` was also run against four Dichiarazioni Pubbliche query families. It was useful for
accessibility and interaction constraints but not reliable as an art director: the
"data journalism" query suggested cyberpunk/Fira Code and the media workspace query
suggested a vibrant pink startup treatment. These recommendations conflict with product
trust, political neutrality and the user's explicit anti-AI-slop preference.

Therefore its quantitative/accessibility guidance is retained; its aesthetic matches are
treated as search hints, not authority.

---

## Research landscape

The design research intentionally extends beyond fact-checking competitors. Copying only
fact-checkers would inherit their category assumptions.

### A. Public fact-checking products

Reviewed previously and retained as category evidence:

- Pagella Politica;
- Facta;
- Newtral;
- Full Fact;
- PolitiFact;
- Snopes;
- AFP Fact Check;
- Maldita;
- Africa Check;
- Google Fact Check Explorer.

#### Table stakes worth keeping

- checked statement visible before long prose;
- speaker/origin, source and date close to the claim;
- sources directly accessible;
- methodology and correction policy easy to find;
- archive/search/filter support as the corpus grows;
- mobile-readable fact-check detail.

#### Category defaults to reject

- verdict as the entire visual identity;
- truth meters, grades and theatrical stamps;
- politician scorecards;
- walls of same-size article cards;
- party colors carrying structural meaning;
- generic news homepage density;
- long prose before the user knows what is being checked.

Pagella Politica is especially useful as a **market/category comparator** but not as the
design destination. Its methodology emphasizes exact wording, sources that readers can
revisit, time-appropriate evidence and review. Those trust properties matter more than
copying its visual verdict conventions.

### B. Public-service design: GOV.UK, USWDS, NHS patterns

These systems are valuable not because Dichiarazioni Pubbliche should look governmental, but because
they are ruthless about comprehension.

Important transferable rules:

- ordinary headings and lists beat an accordion when most users need the information;
- Details/Accordion/Tabs should hide only genuinely secondary information;
- summary lists are for key/value facts, not every list;
- summary cards are useful for repeated structured entities/actions, not small amounts of
  related metadata;
- conventional navigation/search is usually preferable to clever navigation;
- semantic HTML and source order must survive responsive layout.

This reinforces the UX-v2 decision to keep primary rationale and primary sources visible
and reserve disclosure for technical provenance.

### C. Editorial/public-interest systems: BBC GEL, ProPublica, Rest of World

#### BBC GEL

Useful principles:

- readable typography is an accessibility primitive;
- body measure around 60–70 characters is preferable to full-width prose;
- typography scales with user settings rather than fixed-pixel assumptions;
- headings and document order provide real navigation;
- visual grid order should not diverge from semantic/focus order;
- icons support text; they do not replace it;
- avoid text over complex photography.

#### ProPublica

The 2026 redesign is interesting because the structural change is more important than a
new coat of paint. Investigations can package their reporting with methodology, visual
explainers and supporting materials, while still preserving focus on the reporting.

Transferable idea for Dichiarazioni Pubbliche:

> A Fact-check may have supporting evidence, methodology, media and correction history,
> but those should feel like one coherent record rather than four dashboard widgets.

#### Rest of World

Rest of World demonstrates a useful **role-based typography system** rather than one font
used everywhere. Its current style guide separates story, brand and UI typography and
uses a mono face for system labels/data. Its product team has also written about using a
small flexible set of editorial blocks instead of an over-engineered homepage matrix.

Transferable ideas:

- typography can distinguish editorial voice from system metadata;
- a small flexible grammar creates variety without component explosion;
- visual stories may have locally expressive art direction while remaining recognizably
  part of the same publication.

### D. Data/visual journalism: Our World in Data, The Pudding, Reuters Graphics, The Markup

#### Our World in Data

The strongest structural lesson is its explicit use of:

`overview first -> zoom/filter -> details on demand`

The product also introduced concise Data Insights built around one takeaway, one chart,
short explanation and links to explore deeper.

For Dichiarazioni Pubbliche this suggests:

- one-sentence finding before evidence complexity;
- key numbers only when they actually explain the finding;
- Explore owns filtering complexity;
- Fact-check detail owns explanation;
- technical provenance remains deeper but discoverable.

#### The Pudding

The Pudding's strongest work treats interaction as explanation. Motion/interaction earns
its place when it produces an "oh, that makes sense" moment, not merely because the web
can animate.

For Dichiarazioni Pubbliche:

- ContentAudit is the best candidate for one signature explanatory interaction;
- the rest of the product should not become a visual-essay playground;
- one memorable interaction is stronger than many micro-animations.

#### Reuters Graphics

Reuters frames visual journalism as a way to simplify complex information and add
context. The transferable lesson is that data visualization belongs where it clarifies a
specific factual question, not as permanent dashboard decoration.

#### The Markup

The Markup's design guidance explicitly prioritizes clear/traditional graphics over
experimental ones when clarity wins, and its "show your work" philosophy publishes
methodology/data so findings can be interrogated.

This maps unusually well to Dichiarazioni Pubbliche: provenance should be **inspectable without becoming
the default visual burden**.

### E. Research/evidence tools: Elicit, Consensus, scite

These products solve a different problem from fact-checkers but are closer to our
evidence interaction model.

#### Elicit

- evidence workflows are staged;
- screening/extraction decisions remain auditable;
- extracted statements can be tied to supporting quotations/figures;
- iteration is normal, not an exception.

#### scite

An especially strong lesson from its Assistant redesign: references are grouped with the
response they support rather than pooled separately, and the search strategy is made more
visible.

For Dichiarazioni Pubbliche this suggests:

- sources should be close to the rationale/observation they support;
- a giant undifferentiated "Sources" box is weaker than contextual evidence linkage;
- search strategy belongs in Studio/provenance, not as visual clutter in Public.

#### Consensus

Search is the front door; advanced filters appear only when users ask for refinement.
That validates Explore as the complexity owner and argues against permanent filter rails
on Home/mobile.

### F. Media/transcript tools: Descript, Full Fact AI, Factiverse Gather/Live

#### Descript

The central interaction insight is simple: transcript text can become a navigation
surface for media rather than a passive dump.

#### Full Fact AI

It demonstrates the value of a professional surface distinct from the public editorial
site: monitoring, search, alerts, live claims and actions serve operator work.

#### Factiverse Gather / Live

The closest functional comparator to Verify Studio:

- paste/watch a video or podcast;
- transcript + claim extraction;
- sources around each claim;
- jump directly to the source moment;
- filter/search while investigating.

The Dichiarazioni Pubbliche opportunity is to make the workspace **less generic-AI** and more clearly
connected to persistent provenance, explicit review and a public historical record.

### G. Italian design heritage: Olivetti / Giovanni Pintori

This is not a request for a retro website. It is useful as a counterweight to generic US
SaaS aesthetics.

The relevant traits are:

- confident asymmetric composition;
- information expressed through simple geometric relations;
- typography as a structural object;
- a small number of strong colors used deliberately;
- technical subject matter made culturally sophisticated rather than bureaucratic.

The danger is pastiche: typewriters, fake paper texture, 1950s cosplay and ornamental
nostalgia would immediately weaken a contemporary evidence product.

### H. Source-grounded answer systems: NotebookLM, Perplexity, scite

These products are useful because they expose an important distinction: a research answer
can be concise while its evidence remains immediately inspectable.

#### NotebookLM

Google's current NotebookLM organizes work into three stable areas — **Sources, Chat,
Studio** — and can link citations back to the transcript of a YouTube source. The useful
lesson is not "make Dichiarazioni Pubbliche a chat app". It is that source management, synthesis and
derived output can remain spatially distinct without forcing users through separate
products.

Transfer to Dichiarazioni Pubbliche:

- Verify Studio should give transcript/source, claim and evidence/review stable spatial
  homes;
- opening a source should preserve the current claim context rather than navigating the
  operator away from the investigation;
- Public should borrow the **source traceability**, not the chat-centric interaction.

#### Perplexity

Perplexity makes the source behind an answer a core interaction and explicitly describes
its search products around cited, inspectable results. This reinforces one Dichiarazioni Pubbliche rule:

> a concise answer and a transparent evidence trail are complements, not competing UI.

Do not copy the omnibox/chat metaphor. Dichiarazioni Pubbliche Public is a record/search product, and
Verify Studio is an evidence workflow, not an open-ended assistant conversation.

#### scite

scite's redesign moved references next to the response they support and made search
strategy more visible. This is especially relevant to Fact-check and Verify Studio:

- evidence should resolve close to the observation/rationale it supports;
- search strategy is useful operator/provenance information but should not dominate the
  public reading page;
- "all sources" remains available, but it should not be the only evidence model.

### I. Inspection products: The Markup Blacklight

Blacklight is a strong adjacent product reference because its journey is extremely clear:

`enter URL -> run bounded analysis -> receive structured report -> inspect methodology and limitations`

It does not require a dashboard home or a conversational UI to make a technically complex
analysis approachable. The tool also states limitations explicitly instead of presenting
an automated result as final truth.

Transfer to the future Dichiarazioni Pubbliche verification intake:

- one obvious input can be enough;
- analysis state should use real persisted stages, not theatrical "AI researching";
- the result should be a structured inspection/report;
- caveats and unresolved states must look first-class rather than like failure.

### J. Reading/reference tools: Readwise Reader

Reader demonstrates that dense research software can remain usable when the **document is
the primary object** and secondary functions live in margins/panels. It also invests in
keyboard navigation and uses side panels only when the viewport can afford them.

Transfer to Dichiarazioni Pubbliche:

- text/transcript itself can be a navigation surface;
- wide-screen Studio may expose contextual evidence in a side region while preserving a
  dominant reading/investigation object;
- keyboard shortcuts are appropriate for the private operator workspace, not Public;
- on mobile the side panel becomes a deliberate secondary surface rather than a squeezed
  desktop rail.

### K. Accessibility/product continuity: USWDS + BBC GEL

USWDS explicitly treats accessibility as usability for the broadest possible audience and
recommends simple layouts, large targets, keyboard/touch support, visible contrast and no
color-only meaning. BBC GEL similarly treats legible typography, headings, focus and
document structure as foundations rather than polish.

These references strengthen several non-negotiables for Dichiarazioni Pubbliche:

- reading/focus order must remain logical even when desktop composition becomes asymmetric;
- body type cannot be shrunk to create visual sophistication;
- every status needs words, not color alone;
- media must never autoplay merely to make ContentAudit look alive;
- controls must remain usable at text zoom and with keyboard/touch;
- expressive prototype directions P2/P4/P5 do not get accessibility exceptions.

### L. Flexible editorial systems: Rest of World

Rest of World's public style guide separates **Story, Brand and UI** typography roles,
which is a stronger mental model than choosing one fashionable font family and using it
everywhere. Its homepage team also described preferring a small flexible set of editorial
blocks over an over-engineered matrix designed for every possible scenario.

Transfer to Dichiarazioni Pubbliche:

- quote/original statement, explanatory prose, metadata and UI labels may legitimately
  use different typographic roles;
- the home should be composed from a very small number of strong blocks;
- variation comes from content and hierarchy, not a growing zoo of component variants;
- a coherent system can allow ContentAudit to feel more expressive than Explore without
  becoming a separate brand.

### Screenshot-level observations

Visual references inspected during this pass reinforced the written research:

- **NotebookLM**: the Sources / Chat / Studio split works because column roles are stable
  and visually quiet; the risk for Dichiarazioni Pubbliche would be copying Chat as the dominant center;
- **Elicit**: systematic-review screens make stage/progress and inclusion/exclusion
  decisions legible through rows and tables rather than decorative dashboards;
- **Descript**: transcript text and timeline share selection state, proving that media and
  text can be navigated as one object;
- **Blacklight**: a technically complex scanner can begin with one URL input and produce
  a comprehensible report without an analytics dashboard.

These screenshots are research references only and are intentionally not vendored into
the public repository.

---

## The category-reflex check

### Obvious category default

If a generic design team received "AI fact-checking platform", it would probably make:

- white/gray SaaS shell;
- blue/purple gradient;
- large rounded search field;
- verdict pills in green/yellow/red;
- three- or four-column card grid;
- avatars of politicians;
- metric cards;
- AI sparkle/scan animation;
- transcript/evidence dashboard with a sidebar;
- lots of 12px muted text.

That is precisely the visual language to avoid.

### EUREKA

**Fact-checking products usually make the verdict the memorable object; research tools
usually make the AI/search workflow the memorable object. Dichiarazioni Pubbliche has a better object:
the trace from the exact public statement to the evidence and through time.**

Therefore the signature system should be built around a **verifiable trail**, not a
verdict meter and not an AI assistant.

Conceptually:

```text
ORIGINAL MOMENT
      |
      v
CHECKED CLAIM
      |
      v
EVIDENCE / OBSERVATIONS
      |
      v
FINDING
      |
      v
CORRECTION / REPLY / LATER RELATED STATEMENT
```

Each visual direction below interprets this trail differently.

---

## The one memorable thing

When someone closes Dichiarazioni Pubbliche after first use, the intended memory is:

> **"Qui posso vedere esattamente cosa è stato detto e la traccia delle prove."**

Not:

- "the green/red site";
- "the AI checker";
- "the politicians dashboard";
- "the legal archive".

---

## Product-wide visual/interaction constraints shared by all five prototypes

These are fixed. A visual direction that needs to violate them is rejected rather than
"adapted".

### Information hierarchy

- claim/original moment before verdict decoration;
- concise answer before methodology;
- relevant sources before technical IDs;
- one dominant action per region;
- no more than 4–5 persistent top-level public navigation items;
- public text measure roughly 60–70 characters on wide screens;
- long metadata never competes with the claim.

### Shapes/components

- no universal rounded-card container grammar;
- lists/rows/dividers are the default for comparable records;
- cards reserved for genuinely self-contained visual/media objects;
- pills reserved for compact states/filters, not every noun;
- icon circles and decorative badges require functional meaning;
- no glassmorphism, glow, blurred gradient blobs or fake paper texture.

### Status

- state is always written in words;
- color is secondary;
- no aggregate state visualization around a Person;
- no green/red "truth performance" timeline;
- uncertain/under-review states must look intentional rather than broken.

### Typography

- typography does most of the brand work;
- body text is never tiny to create artificial sophistication;
- metadata may use a separate face/width/weight but remains legible;
- all-caps is rare and limited to genuine short labels;
- tabular numbers for dates/timestamps/data where useful.

### Mobile

- 44px minimum touch areas;
- no hover dependencies;
- filters become one visible control + sheet/drawer;
- Fact-check remains a linear reading experience;
- ContentAudit does not expose four simultaneous panes;
- no persistent bottom nav unless testing proves app-like repeated navigation needs it;
- safe areas and dynamic text expansion must survive.

### Motion

- 150–300ms for ordinary state transitions;
- no entrance choreography for ordinary records;
- ContentAudit may use restrained timeline/media synchronization;
- Studio may animate the arrival of **persisted** claims/evidence/state changes;
- reduced-motion produces a complete non-animated experience;
- never animate fake "searching the web" activity.

### Accessibility/trust

- visible focus;
- semantic reading/focus order matches visual order;
- primary state has text/icon redundancy;
- correction history visibly version-aware;
- source link labels describe destination;
- primary evidence never hidden solely for visual cleanliness;
- public output remains useful with all AI providers offline.

---

## Screen jobs — fixed across every prototype

The five directions are compared against identical jobs.

| Screen | First job | Second job | Must not become |
|---|---|---|---|
| Home | understand + find a check | discover recent/featured work | news portal / feature grid |
| Explore | search/filter public record | scan comparable results | facet wall |
| Fact-check | understand the answer | inspect evidence/context | admin dashboard |
| Record | browse chronology for Person/Topic | filter/jump in time | scorecard |
| ContentAudit | navigate claims inside media | open one finding/evidence trail | transcript dump |
| Sessions | resume/start operator work | understand current state | analytics dashboard |
| Workspace | investigate selected claim | move through evidence/review | four-pane control room |

---

## Five prototype directions

All five are deliberately plausible. The exercise fails if one is obviously a joke or if
two look like siblings.

### P1 — Civic Editorial

**Thesis:** the rigor of a public-service interface with the reading quality of an
independent publication.

Research DNA:

- BBC GEL legibility;
- GOV.UK restraint and progressive disclosure;
- ProPublica supporting-material architecture;
- IFCN-style replicability/transparency;
- no direct visual copying.

Visual system:

- warm off-white ground, near-black ink, one strong cobalt/royal-blue brand accent;
- editorial serif for claims/headlines; humanist/grotesk sans for UI/body metadata;
- source/timestamp numerals in tabular sans or restrained mono;
- almost square corners; 0–4px radius;
- thin rules and key-line alignment instead of shadows;
- photography/media only where it is actual source context.

Signature move:

**evidence marginalia** — small numbered source markers sit naturally beside the exact
sentence/observation they substantiate and resolve into a clean source list.

Why it could win:

- feels credible without looking governmental;
- easy to implement/accessibilize;
- strong long-form fact-check detail;
- least likely to age badly.

Risk:

- without careful art direction it can drift into "nice newspaper".

Generation failure to reject:

- cream lifestyle-magazine page with decorative photography;
- giant serif marketing headline that pushes the actual product below the fold;
- source cards floating in rounded boxes instead of true marginalia/rows.

### P2 — Italian Modernist Ledger

**Thesis:** contemporary Italian information design: precise, asymmetric and cultured,
with Olivetti/Pintori as attitude rather than costume.

Research DNA:

- Olivetti/Pintori confidence and geometric communication;
- Swiss/Italian grid discipline;
- Rest of World role-based type system;
- contemporary product ergonomics.

Visual system:

- bone/cream background, black type;
- limited signal colors: vermilion, ultramarine, muted teal, ochre — never all at equal
  strength;
- bold modern grotesk plus a compact mono for timestamps/data; optional restrained serif
  only for long reading;
- asymmetric 12-column grid;
- sharp edges, hairlines, deliberate empty space;
- large numbers/dates occasionally become composition anchors;
- status represented by small geometric signal + label, not pill clouds.

Signature move:

**the ledger strip** — a thin numbered or dated rail that organizes statement, source,
evidence and history using simple geometric marks.

Why it could win:

- gives Dichiarazioni Pubbliche a genuinely Italian design identity without legal imagery;
- memorable even in grayscale;
- avoids looking like another US SaaS/news template.

Risk:

- too much asymmetry could hurt scan speed; retro pastiche is an automatic rejection.

Generation failure to reject:

- Bauhaus poster cosplay, primary-color confetti or fake 1950s print texture;
- oversized section numbers that damage scan order;
- asymmetry that changes semantic/keyboard order or makes mobile incoherent.

### P3 — Quiet Research Index

**Thesis:** the fastest serious way to find a claim and inspect the evidence, closer to a
great reference/research tool than a media homepage.

Research DNA:

- Consensus search front door;
- Elicit auditable evidence workflows;
- scite contextual references/search strategy;
- Google Fact Check Explorer compact retrieval;
- GOV.UK list clarity.

Visual system:

- bright neutral background, cool gray structure, deep ink/navy text, restrained teal or
  blue link/accent;
- highly legible sans UI/body with a contrasting bookish serif reserved for the checked
  statement;
- dense-but-calm rows, almost no decorative imagery;
- evidence is inline/contextual rather than a grid of source cards;
- powerful search/filter interactions progressively disclosed.

Signature move:

**inline evidence anchors** — rationale sentences carry unobtrusive numbered markers that
open the exact supporting source/observation; sources are grouped by what they establish.

Why it could win:

- exceptional usability and trust;
- Explore and Studio can share interaction concepts cleanly;
- minimal AI aesthetic risk.

Risk:

- may feel too academic/tool-like unless Home and ContentAudit add enough brand warmth.

Generation failure to reject:

- gray enterprise SaaS table with no memorable brand anchor;
- permanent left sidebar merely because research products often have one;
- chat/search box taking over the entire product metaphor.

### P4 — Visual Journalism

**Thesis:** every verification has one visual explanatory idea; Dichiarazioni Pubbliche feels like an
editorial product built by a strong graphics desk, not a CMS template.

Research DNA:

- The Pudding's "interaction earns the insight" approach;
- ProPublica flexible story packaging;
- Reuters Graphics contextual visualization;
- The Markup clarity/show-your-work discipline;
- Rest of World story-specific art direction.

Visual system:

- neutral global shell, but each major Fact-check/ContentAudit may receive one controlled
  story accent color tied to the evidence visualization, never the speaker/party;
- expressive editorial serif/sans pair;
- composition changes according to evidence type: number comparison, timeline, map,
  source excerpt, media moment;
- large whitespace, occasional full-bleed evidence visual;
- Home remains sparse: one lead visual investigation + compact checks.

Signature move:

**one evidence visual per record** — a chart/timeline/media comparison that explains the
central finding without requiring decorative dashboards.

Why it could win:

- strongest chance of feeling designed rather than templated;
- highly shareable/recognizable ContentAudit pages;
- makes complex context understandable.

Risk:

- editorial/design effort per record is higher; must have graceful text-only fallback.

Generation failure to reject:

- infographic wall or chart gallery;
- ornamental data visualization with no explanatory question;
- every page receiving bespoke art direction and therefore losing system continuity.

### P5 — Temporal Evidence Tape

**Thesis:** time is the interface. Dichiarazioni Pubbliche's unique memory becomes visible through one
continuous, restrained chronological language across public records and Studio.

Research DNA:

- Descript text/media synchronization;
- Factiverse jump-to-claim workspace;
- Our World in Data overview/filter/detail structure;
- public-record chronology;
- neutral data-viz discipline.

Visual system:

- very light neutral background, deep ink, one cool blue plus one warm signal accent;
- precise sans plus editorial serif for quoted/original statements;
- thin temporal rails, ticks and connectors replace most cards;
- timestamps/dates receive unusually strong hierarchy;
- Record timelines remain neutral: status appears only when an individual finding is
  opened/selected.

Signature move:

**evidence tape** — a horizontal/vertical temporal rail connects source moment, evidence
reference dates, publication/review and later correction/related claim. It is not a node
graph and not always visible; it appears when chronology matters.

Why it could win:

- makes the "memory" moat instantly tangible;
- ContentAudit and Studio gain a shared interaction language;
- unusual without requiring visual gimmicks.

Risk:

- timeline overuse can become complex or imply causal relations. The rail must remain
  secondary on simple fact-checks.

Generation failure to reject:

- sci-fi HUD/timeline aesthetic;
- thin unreadable ticks and connectors everywhere;
- temporal rails appearing on screens where chronology does not help the current task;
- color-coded time marks that accidentally become a person-level performance history.

---

## Comparison matrix before image generation

| Direction | Public reading | Explore/search | ContentAudit | Studio | Distinctiveness | Implementation risk |
|---|---:|---:|---:|---:|---:|---:|
| P1 Civic Editorial | very strong | strong | strong | good | medium-high | low |
| P2 Italian Modernist Ledger | strong | strong | strong | strong | very high | medium |
| P3 Quiet Research Index | strong | very strong | good | very strong | medium | low |
| P4 Visual Journalism | very strong | medium | very strong | good | very high | high |
| P5 Temporal Evidence Tape | strong | strong | exceptional | exceptional | very high | medium-high |

This table is a hypothesis, **not a winner selection**. Image generation and later
interactive prototyping must test it.

---

## GPT Image generation protocol

The biggest problem with earlier generations was asking the model to present multiple
screens as a stylish design-board image. That optimized the **packaging**, not the
product.

New rule: generate **actual full-screen UI only**.

Every prototype package contains prompts for the same surfaces. Each image request must:

- render one screen only;
- use a flat straight-on browser/app viewport;
- fill the entire image with the interface;
- have no device mockup;
- have no Figma canvas;
- have no case-study captions outside the UI;
- have no arrows explaining the design;
- have no floating brand board, palette swatches or typography samples;
- have no surrounding desk/background;
- use realistic Dichiarazioni Pubbliche content shapes but avoid treating placeholder political facts
  as real factual claims;
- prioritize layout fidelity over perfect long-form text rendering.

### Generation order

Round 1 — visual-language discriminator:

1. Home desktop for P1–P5.
2. Fact-check desktop for P1–P5.

Reject any direction that fails both before spending more image-generation effort.

Round 2 — product-system proof for the best 2–3:

3. ContentAudit desktop;
4. Explore desktop;
5. Record desktop;
6. Studio Workspace desktop;
7. Home mobile;
8. Fact-check mobile.

Round 3 — only for finalists:

- Sessions;
- edge states: unresolved evidence, correction notice, empty search, blocked provider;
- dark mode only if it materially improves the chosen system;
- motion storyboard for ContentAudit/Studio.

---

## Evaluation — stricter than the previous rubric

In addition to `docs/ux/evaluation-rubric.md`, reject a generated direction when any of
these is true:

### AI-slop gates

- more than half the meaningful objects are rounded cards;
- three equal feature cards appear simply to fill space;
- repeated pill badges become the main visual texture;
- generic blue/purple SaaS gradient or glow appears;
- decorative circular icons precede every heading;
- tiny gray metadata is used to fake sophistication;
- fake KPI panels appear on Public or Sessions;
- politician portraits dominate Home/Record for visual drama;
- every state is green/yellow/red candy coloring;
- a giant chatbot or AI orb becomes the product metaphor.

### Designer-quality gates

- interface remains strong with shadows disabled;
- first three seconds reveal exactly one visual anchor;
- each screen can be summarized as one job;
- at least one meaningful key-line/alignment relationship is visible;
- type hierarchy works in grayscale;
- whitespace separates conceptual layers, not just components;
- mobile recomposes rather than stacking desktop boxes;
- long/empty/error states could fit without breaking the visual thesis;
- no element exists only because "modern websites have it";
- Public and Studio feel related without pretending they need the same density.

---

## What is deliberately *not* decided yet

- final logo;
- final verdict vocabulary;
- final type licenses/fonts;
- final palette tokens;
- React/component library;
- exact breakpoint values;
- whether Public has dark mode;
- final navigation labels after usability testing;
- final motion system;
- which direction wins.

Those decisions belong after visual comparison, not before it.

---

## Research source index

Primary/reference URLs used in this pass:

- https://design-system.service.gov.uk/components/accordion/
- https://design-system.service.gov.uk/components/details/
- https://design-system.service.gov.uk/components/tabs/
- https://design-system.service.gov.uk/components/summary-list/
- https://bbc.github.io/gel/
- https://bbc.github.io/gel/foundations/typography/
- https://bbc.github.io/gel/foundations/grids/
- https://ourworldindata.org/owid-entry-redesign
- https://ourworldindata.org/launching-data-insights
- https://www.propublica.org/article/why-propublica-redesign
- https://restofworld.org/style-guide/
- https://restofworld.org/inside/homepage-redesign/
- https://restofworld.org/inside/visual-style-guide/
- https://designsystem.digital.gov/design-principles/
- https://designsystem.digital.gov/documentation/accessibility/
- https://pudding.cool/pudding-cup/
- https://reutersagency.com/content/content-types/graphics/
- https://themarkup.org/about
- https://design.themarkup.org/
- https://elicit.com/solutions/systematic-review
- https://elicit.com/blog/introducing-research-agent-workflows
- https://scite.ai/blog/major_updates_to_scite_assistant
- https://www.perplexity.ai/hub/products/search
- https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-new-features-december-2024/
- https://blog.google/innovation-and-ai/products/notebooklm-audio-video-sources/
- https://themarkup.org/blacklight
- https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector
- https://docs.readwise.io/reader/docs
- https://docs.readwise.io/reader/docs/faqs/highlights-tags-notes
- https://help.consensus.app/en/articles/9922799-advanced-search-filters
- https://www.descript.com/blog/article/descript-storyboard-whats-new-for-podcasters
- https://fullfact.org/blog/2025/feb/how-ai-can-help-fact-checkers/
- https://www.factiverse.ai/solutions/live
- https://www.factiverse.ai/solutions/gather
- https://pagellapolitica.it/progetto
- https://pagellapolitica.it/correzioni-rettifiche-aggiornamenti
- https://www.newtral.es/zona-verificacion/fact-check/
- https://ifcncodeofprinciples.poynter.org/the-commitments
- https://www.moma.org/artists/4629-giovanni-pintori
- https://a-g-i.org/user/giovannipintori/

Competitor screenshots/visual references are research references only. They should not be
vendored into the public OSS repository unless rights allow it; use links/screenshots in
private design research instead.

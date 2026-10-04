# Competitive UX Research v1 — Fact-checking, Verification and Live Analysis

Date: 2026-09-23  
Status: design research, not canonical product policy

## Research question

What should Dichiarazioni Pubbliche look and feel like if it must be immediately understood as a
fact-checking product, remain trustworthy and neutral, avoid looking like legal software,
and also support a private real-time verification studio for links, articles, video,
podcasts, audio and pasted text?

## Key conclusion

There should **not** be one interface trying to serve every use case.

The competitive landscape splits into two distinct UX families:

1. **Public editorial / evidence products** — Pagella Politica, Newtral, Full Fact,
   PolitiFact, Snopes, AFP Fact Check, Maldita, Africa Check, FactCheck.org.
2. **Professional/live verification tools** — Full Fact AI, Factiverse Live/Gather,
   ClaimBuster, Google Fact Check Explorer as an adjacent search utility.

Dichiarazioni Pubbliche needs both families under one brand system:

- **Dichiarazioni Pubbliche Public** — calm, readable, source-first, consumer friendly, mobile-first;
- **Dichiarazioni Pubbliche Verify Studio** — private at first, denser, desktop-first, real-time,
  showing transcript, claims, evidence acquisition and review states.

Trying to make the public site look like a newsroom dashboard would hurt comprehension.
Trying to make the Studio look like an article website would waste the live workflow.

---

## Competitor matrix

### Pagella Politica — Italy

Current product pattern:

- editorial homepage with politics/news explainers plus a dedicated fact-check section;
- fact-check list centered on politician, quote, source and date;
- filtering by politician/party;
- strong local recognition and explicit methodology/corrections pages.

Useful lessons:

- Italians immediately understand the product when the words **fact-checking** and the
  original statement are visible;
- quote/source/date is an effective compact card anatomy;
- public methodology and corrections are trust surfaces, not footer trivia.

Do not copy:

- the general-news homepage density as the main Dichiarazioni Pubbliche identity;
- person-level scorecard framing or yearly "reliability" summaries;
- party color as a primary visual system.

References:

- https://pagellapolitica.it/
- https://pagellapolitica.it/fact-checking
- https://pagellapolitica.it/manifesto

### Facta — Italy

Current product pattern:

- visually strong magazine/editorial homepage;
- broad misinformation and internet-culture coverage;
- large imagery, typographic identity and article-first navigation.

Useful lessons:

- fact-checking does not need to look bureaucratic;
- strong editorial art direction can make verification feel culturally current.

Do not copy:

- article-first information architecture for the core Dichiarazioni Pubbliche record;
- magazine hierarchy that hides claim/evidence structure.

Reference:

- https://www.facta.news/

### Newtral — Spain

Current product pattern:

- dedicated Verification Zone;
- cards distinguish fact-checks, fakes, context and reader questions;
- filters include person, political party, rating and date;
- fact-check article surfaces original claim, person, role, verdict and reading time near
  the top;
- redesign explicitly optimized card layouts for mobile and supports dark/light display.

Useful lessons:

- the **claim itself belongs above the fold**, not buried in prose;
- faceted filters are valuable once the archive grows;
- a compact claim + status + speaker block scans quickly;
- dark/light can be part of a serious editorial product without looking like developer
  tooling.

Do not copy:

- overly verdict-color-driven identity;
- a taxonomy so editorially broad that users cannot tell fact-check from explainer.

References:

- https://www.newtral.es/zona-verificacion/fact-check/
- https://www.newtral.es/newtral-nueva-portada/20230307/

### Full Fact — United Kingdom

Public product:

- calm institutional editorial site;
- recent fact checks, quick checks, explainers, government tracking, training and policy;
- emphasizes evidence and corrections rather than spectacle.

Professional product:

- Full Fact AI has workflow concepts such as Home, Search, Alerts, Live and Actions;
- real-time transcription can surface known/repeated claims during live events;
- long video/podcast monitoring helps fact-checkers jump to potentially relevant moments.

Useful lessons:

- strongest precedent for **two surfaces under one fact-checking organization**;
- public calm + professional density can coexist;
- "quick check" and "full context" can be two depths of the same evidence system;
- live tooling should expose useful states, not pretend every machine output is a final
  published verdict.

Dichiarazioni Pubbliche opportunity:

- connect the private live workflow to a persistent public historical record more tightly
  than a normal newsroom tool.

References:

- https://fullfact.org/
- https://fullfact.org/quick-checks/
- https://fullfact.org/ai/
- https://fullfact.org/blog/2025/feb/how-ai-can-help-fact-checkers/

### Factiverse — Norway / international

Current product pattern:

- probably the closest product-level comparator to the proposed Verify Studio;
- Live transcribes audio/video, detects claims, attributes them to speakers, searches
  sources and produces rapid analysis;
- Gather lets users jump from a claim to the moment it was said and filter/search source
  evidence;
- Text/Editor workflows analyze pasted or authored text and return supporting/disputing
  sources.

Useful lessons:

- video + transcript + detected-claim + evidence is a proven workspace pattern;
- real-time status is itself useful even before final verification;
- source selection/filtering belongs in the analyst workspace;
- a final structured report is a natural result of live analysis.

Dichiarazioni Pubbliche differentiation:

- stronger append-only provenance/review history;
- explicit separation retrieval -> approval -> verification -> publication;
- persistent longitudinal memory of the same person's claims over years;
- correction/right-of-reply lifecycle tied to the public record;
- no automatic public verdict simply because the live tool produced an answer.

References:

- https://www.factiverse.ai/solutions/live
- https://www.factiverse.ai/solutions/gather
- https://www.factiverse.ai/solutions/text

### PolitiFact — United States

Current product pattern:

- highly recognizable Truth-O-Meter;
- statement cards and ratings are extremely scannable;
- people, promises and topic/archive navigation are first-class;
- methodology emphasizes original wording, context, timing and sources.

Useful lessons:

- make the *object being checked* visually unmistakable;
- a consistent compact claim component creates strong recognizability;
- people and promise archives can create longitudinal product value.

Do not copy:

- meter/gauge gamification;
- scorecarding people;
- humorous/loaded verdict decoration such as a theatrical lowest tier;
- visual patterns that encourage users to interpret a person's aggregate record as a
  political recommendation.

Reference:

- https://www.politifact.com/article/2018/feb/12/principles-truth-o-meter-politifacts-methodology-i/

### Snopes — United States

Current product pattern:

- broad consumer rumors/viral-content coverage;
- strong brand recognition and image-led story cards;
- topics, collections, archives and search are prominent.

Useful lessons:

- verification can be approachable and consumer-facing rather than institutional;
- image/video misinformation needs visual-first cards.

Do not copy:

- content/advertising/membership density;
- a generic media-site homepage that hides provenance and structured claim relationships.

Reference:

- https://www.snopes.com/

### AFP Fact Check — international

Current product pattern:

- topic/region navigation;
- visual cards work well for manipulated media;
- bold false-context labels often sit directly over the media object.

Useful lessons:

- when the object is an image or video, show it prominently;
- region/topic filters can scale a global archive.

Do not copy:

- make binary FALSE stamping the central identity of Dichiarazioni Pubbliche;
- allow verdict color to overpower evidence/uncertainty/context.

Reference:

- https://factcheck.afp.com/

### Maldita.es — Spain

Current product pattern:

- a highly filterable "bulo" archive;
- topic and rating facets;
- categories such as false, alert, context and true;
- service mentality around users sending suspicious content.

Useful lessons:

- powerful archive filters become important quickly;
- **context** and **alert** are useful product states beyond true/false;
- user-submitted suspicious content can be a first-class acquisition channel.

Do not copy:

- expose every taxonomy dimension at once on the first screen;
- use a giant filter panel before the user understands what Dichiarazioni Pubbliche does.

Reference:

- https://maldita.es/malditobulo/

### Africa Check — Africa

Current product pattern:

- strong methodology and replicability emphasis;
- verification process explicitly begins by confirming the exact wording and asking for
  evidence before judging the claim;
- sources and corrections are treated as part of trust.

Useful lessons:

- show enough method that readers can independently retrace the result;
- "what exactly was said?" should be a visible stage in the product.

Reference:

- https://www.africacheck.org/how-we-fact-check

### Google Fact Check Explorer — adjacent utility

Current product pattern:

- search-first, almost no editorial chrome;
- compact result contains claimant, claim, rating, publisher and date;
- optimized for retrieval rather than storytelling.

Useful lessons:

- the public archive should have a brutally simple universal search path;
- claim search results should remain compact and comparable.

Dichiarazioni Pubbliche differentiation:

- owned provenance and longitudinal relations rather than aggregation only;
- direct path from a content item to its transcript moments, evidence and correction
  history.

Reference:

- https://toolbox.google.com/factcheck/explorer

### ClaimBuster — research / live fact-checking precedent

Current/historical pattern:

- live debate interface combines video, transcript, check-worthy claims and analysis;
- claim-checking utility visibly stages web search -> evidence analysis -> verdict.

Useful lessons:

- multi-panel live analysis is conceptually correct for an operator workflow;
- explicit stages reduce the illusion that a verdict appears magically.

Do not copy:

- research-dashboard visual clutter;
- large scatterplots/check-worthiness scores as default user-facing UI.

Reference:

- https://idir.claimbuster.org/claimcheck/

---

## Cross-competitor patterns worth adopting

### 1. Put the claim before the article

The user should not need to read three paragraphs to discover what is being checked.

Canonical public card anatomy should trend toward:

```text
original statement / concise checked claim
speaker or origin
source + date + timestamp
assessment state
one-line finding
evidence/source affordance
```

### 2. Evidence must be one interaction away

The strongest trust pattern across serious fact-checkers is transparent sourcing.
Dichiarazioni Pubbliche can go further by showing structured observations and provenance without
exposing private/raw operational data.

### 3. Separate browse, search and verify

They are three different intents:

- **Browse** — what has been checked recently?
- **Search** — has this already been checked / what has this person said?
- **Verify** — analyze a new input.

Do not make one overloaded search box pretend to solve all three.

### 4. Context is a first-class result

Binary true/false often loses the most useful part of a verification. Dichiarazioni Pubbliche should
visually distinguish supported, contradicted, missing-context, unresolved and pending
without creating a theatrical meter.

### 5. The process should be visible in Studio, compressed in Public

Public readers need the evidence trail but not every worker event. Studio users benefit
from seeing acquisition, transcription, claim detection, evidence search, verification,
review and publication state separately.

### 6. Mobile-first public, desktop-first Studio

Public pages need excellent phone reading. Live video/transcript/evidence triage is
inherently more productive on a wide screen. Responsive Studio is useful; mobile parity
should not force a weak desktop workspace.

### 7. Avoid color = truth

Use semantic color sparingly and redundantly with icon/text. A person's identity, party
or ideological grouping must never inherit verdict color. Status must remain readable in
grayscale and accessible to color-blind users.

---

## Recommended product information architecture

### Public

Primary navigation:

```text
Dichiarazioni Pubbliche
Fact-check   Esplora   Persone   Temi   Metodo   Cerca
```

Optional later:

```text
Proponi una verifica
```

but this queues a request; it does not pretend to be an immediate public LLM execution.

### Private Verify Studio

Primary navigation:

```text
Studio
Nuova verifica   In corso   Coda   Record   Revisioni
```

Input types:

- pasted claim/text;
- article/site URL;
- YouTube/video URL;
- podcast/audio URL;
- uploaded file;
- later live stream.

Workspace lifecycle:

```text
Acquire
  -> Transcript / extract
  -> Detect claims
  -> Select check-worthy claims
  -> Search/fetch evidence
  -> Extract observations
  -> Verify
  -> Review
  -> Ready for publication / hold
```

No stage visually implies publication until the explicit publication gate passes.

---

## Design principles for Dichiarazioni Pubbliche

1. **Fact-check first, archive second.** A new visitor understands the product in five
   seconds without knowing what a "public record graph" is.
2. **Calm authority, not courtroom authority.** Avoid legal-document clichés, scales,
   stamps, parchment, gavels, seals and bureaucratic grey interfaces.
3. **Modern editorial, not newspaper cosplay.** Strong typography and whitespace without
   reproducing a newspaper homepage.
4. **Evidence is visual structure.** Sources, dates, timestamps and provenance are
   components, not footnotes.
5. **Original wording is sacred.** The exact source quote/media moment remains visually
   distinguishable from the normalized claim.
6. **Status without spectacle.** Avoid meters, grades, flames, scoreboards and person
   reliability donuts.
7. **Show uncertainty elegantly.** Pending, unresolved and context-needed states must look
   intentional rather than like errors.
8. **Motion explains state.** Animations in Studio show the pipeline moving; they never
   simulate certainty or fake research activity.
9. **Longitudinal memory is the moat.** Timeline and comparison patterns should become a
   recognizable part of the brand.
10. **One brand, two densities.** Public is spacious; Studio is information-dense. The
    typography, spacing scale, iconography and status grammar remain shared.

---

## Four visual directions to prototype

Detailed generation prompts live in `docs/ux/concepts/`.

### Direction A — Editorial Evidence

Public-first. Elegant, warm, modern editorial product. Large claim cards, generous white
space, strong typography, subtle evidence metadata, almost no dashboard chrome.

Best question answered:

> Can Dichiarazioni Pubbliche feel like a premium fact-checking publication without looking like a
> normal news site?

### Direction B — Evidence Record Explorer

Public-first. More product-like and distinctive: search/record/timeline/provenance are the
visual identity. Still approachable, but less magazine-like.

Best question answered:

> Can the "memory" moat become visible without making the product look legal or academic?

### Direction C — Live Verification Studio

Private/operator-first. Video/transcript on the left, detected claims in the center,
evidence/review on the right, with restrained live motion and explicit pipeline states.

Best question answered:

> What should the daily tool feel like when a full podcast or debate is being analyzed?

### Direction D — Media Timeline

Hybrid public/content-audit direction. Media player plus synchronized transcript and a
claim/evidence timeline. Designed around the strongest unique content format rather than
the homepage.

Best question answered:

> Can a fact-checked video/podcast page become Dichiarazioni Pubbliche's signature visual object?

---

## What we should not decide from one mockup

- final logo;
- final typeface;
- exact verdict taxonomy;
- final color tokens;
- public account/monetization surfaces;
- graph visualization technology;
- mobile Studio parity.

Mockups should first decide **information hierarchy, density, interaction model and brand
temperature**.

## Prototype sequence

1. Generate one desktop hero screen for A, B, C and D using the fixed prompts.
2. Evaluate blind against `docs/ux/evaluation-rubric.md`.
3. Keep the best two directions; do not average all four immediately.
4. Generate the same key screen in both finalists to compare apples-to-apples:
   - public fact-check detail;
   - public homepage/search;
   - private Verify Studio live run;
   - mobile fact-check detail.
5. Only then build a small design-system token set and interactive prototype.
6. Validate with real Dichiarazioni Pubbliche content fixtures, not lorem ipsum.

## Current hypothesis

The likely end state is not one winner replacing all others. A strong system may combine:

- **A** for public editorial rhythm;
- **B** for search/timeline/record identity;
- **C** for private operations;
- **D** for ContentAudit pages.

The purpose of image generation is to discover which visual language can unify those
surfaces without making them identical.

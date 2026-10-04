# Dichiarazioni Pubbliche — Public Product Architecture v3

Date: 2026-10-03
Status: **canonical public product architecture**; supersedes the public page/route guidance in `docs/32-public-ux-architecture-v2.md`
Scope: Public website only. Studio remains a separate operator product.

## Why this re-alignment exists

The current public architecture simplified the interface successfully, but it over-simplified the domain in two places:

1. it made **Fact-check** the apparent primary object even though the product is a record of public statements;
2. it forced **Person** and **Topic** into one generic `Record` grammar even though people, topics, and source contents answer different user questions.

It also leaks internal/product vocabulary into the public site (`ContentAudit`, `Compare`, `Record`) instead of using language a reader naturally understands.

The new architecture therefore starts from one public mental model:

> **Dichiarazione → Fonte → Verifica → Traccia nel tempo**

A person, topic or content item is an entry point into that model, not a scorecard, dashboard or competing mini-product.

## Brand/product thesis

**Dichiarazioni Pubbliche is the searchable memory of what is said in public.**

It covers public-interest statements by politicians, journalists, presenters, commentators, creators, influencers, entrepreneurs, experts and other public figures. Politics is one domain among many.

The brand remains documentary, precise and source-first. The site must not look like:

- a political newspaper;
- a social network of public figures;
- a ratings/rankings product;
- a generic fact-check magazine;
- a research dashboard exposed to the public;
- a government portal.

The visual system in `DESIGN.md` remains valid: civic ledger, Newsreader + IBM Plex, paper/ink/cobalt, hairlines, the Segno, minimal cards, no KPI walls.

## New public site map

```text
/                                      Home
/esplora/                              Explore — universal search/index
/dichiarazioni/{slug}/                 Statement — canonical shareable object
/persone/{slug}/                       Person archive
/temi/{slug}/                          Topic dossier
/contenuti/{slug}/                     Source/content page
/tracce/{id}/                          Longitudinal trace / reviewed relation thread
/metodo/                               Method

/correzioni/                           Global corrections log (trust utility)
/dati/                                 Data & API landing (developer utility)
/progetto/                              About / governance / open-source project
/contribuisci/                         Suggest source/statement or correction (only when intake gates are ready)
```

`/correzioni`, `/dati`, `/progetto`, and `/contribuisci` are utility/trust documents. They do not become primary product templates or permanent top-nav clutter.

### Legacy route migration

```text
/fact-check/{slug}        -> /dichiarazioni/{slug}
/record/person/{id}       -> /persone/{slug-or-id}
/record/{slug}            -> /persone/{slug-or-id} when it is the legacy Person alias
/contents/{id}            -> /contenuti/{slug-or-id}
/contenuti/{slug}         -> stays /contenuti/{slug} but adopts the new public page contract
/compare/{id}             -> /tracce/{id}
```

Use canonical redirects only after identifier/redirect policy is stable. Preserve machine-readable stable IDs in the public contract even when the human URL uses a readable slug.

## Global navigation

Primary header:

```text
Dichiarazioni Pubbliche        Esplora        Metodo        Cerca
```

Do **not** put `Fact-check`, `Persone`, `Temi`, `Contenuti`, or `Tracce` permanently in the main navigation. They are result/entity types inside Explore and contextual paths from other pages.

Explore exposes the object model explicitly:

```text
Tutto · Dichiarazioni · Persone · Temi · Contenuti
```

Footer / trust navigation:

```text
Metodo · Correzioni · Dati & API · Progetto · Contribuisci · Privacy · GitHub
```

## Page contracts

## 1. Home — keep, simplify, broaden

**Question answered:** What is this, and can I find the thing I remember being said?

Keep the current sparse direction. It has exactly four jobs:

1. explain the product in one clear sentence;
2. expose universal search;
3. show a short recent-statement stream;
4. show one strong source/content example and the path to Method.

Do not add people grids, popular topics, category mosaics, KPIs, charts, rankings, or a news homepage feed.

The recent stream should deliberately mix public domains over time (politics, media, business, culture, science/technology, society, sport when relevant) so the product never visually collapses into politics-only.

## 2. Explore — keep, but make it the universal index

**Question answered:** What is already in the public record?

Explore owns discovery complexity. One search field, one result-type switch, progressively disclosed filters.

### Result modes

- **Tutto** — mixed exact matches grouped by object type, not an infinite soup;
- **Dichiarazioni** — claim-first rows;
- **Persone** — name + approved public role context + short indication of available public record, no verdict totals;
- **Temi** — topic name + scope + recent related statements;
- **Contenuti** — source title + publisher/source type/date + number of published statement moments only when useful.

### Statement filters

Start with only:

- period;
- person;
- topic;
- source/content type;
- finding state;
- sort.

Desktop may show a compact filter row/rail. Mobile exposes one `Filtri` control. Query and active filters remain URL-addressable.

## 3. Statement page — replace `Fact-check` with the canonical product object

Public label: **Dichiarazione**.
Suggested route: `/dichiarazioni/{slug}/`.

**Question answered:** What exactly was said, what do we know about it, and how can I verify the verification?

This becomes the main shareable page and the center of the site.

### Required hierarchy

1. **What was said**
   - exact/original wording or bounded attributable quotation;
   - normalized/checkable formulation when different, explicitly labelled;
   - speaker/origin;
   - role context valid for the statement date when available;
   - source/content title, date and timestamp/locator;
   - direct path to original source.

2. **In brief**
   - written finding state for this statement only;
   - one-sentence answer/rationale;
   - publication/update date.

3. **Verification**
   - explanation in ordinary prose;
   - key numbers/observations only when they materially help;
   - limitations and uncertainty visible, not buried.

4. **Sources**
   - reviewed sources grouped by what they establish where useful;
   - evidence markers linked from the explanation;
   - supporting and contradicting/context evidence remain distinguishable without theatrical red/green treatment.

5. **Original context**
   - timestamped player moment for audio/video;
   - paragraph/quote locator for written content;
   - link to the full Content page.

6. **Trace over time**
   - only reviewed related statements: clarification, update, same proposition, correction, position-change/contradiction candidate;
   - show 2–4 contextual entries inline, then link to a dedicated `/tracce/{id}` when a real thread exists.

7. **Corrections and replies**
   - append-only public history;
   - right-of-reply when approved/public;
   - version date and material change summary.

8. **Method & provenance**
   - compact disclosure for policy/version/technical provenance;
   - never let internal IDs dominate the reading experience.

### What disappears

- `Fact-check` as a top-level brand category;
- giant verdict badge as the visual protagonist;
- technical rail full of IDs;
- generic related-content recommendations;
- person-level interpretation.

`Fact-check` remains valid terminology in Method, structured data/SEO, and editorial metadata when useful. It is not the primary public page name.

## 4. Person page — split from Topic; it is an archive, not a profile or scorecard

Public label: **Archivio di {Nome}** or simply the person's name with `Persona` as context.
Suggested route: `/persone/{slug}/`.

**Question answered:** What public statements from this person are in the verified record, and how do they connect over time?

### Header

- canonical name;
- small approved portrait only when useful for disambiguation, never hero celebrity imagery;
- current/relevant public role context;
- role history when approved and time-bounded;
- one sentence explaining scope and no-person-score rule.

### Body

1. **Dichiarazioni** — chronological claim-first list;
2. filters: topic, period, content/source type, claim type;
3. **Nel tempo** — reviewed clarifications/updates/changes that form actual threads, not aggregate verdict distributions;
4. **Contenuti** — interviews, videos, podcasts, articles, speeches etc. that have published statements attached;
5. **Correzioni e repliche** — only when public history exists.

### Optional navigation aids

A compact topic index may help jump/filter the archive, but it must not become `top topics` performance analytics. Counts are navigational only when they materially help.

### Never show

truth percentage, reliability score, supported/false totals, streaks, leaderboard rank, ideology classification, or “most controversial” gamification.

## 5. Topic page — a dossier, not the Person template with a different title

Public label: **Tema** / topic name.
Suggested route: `/temi/{slug}/`.

**Question answered:** What has been publicly claimed about this subject, what does the topic include, and where are the main source trails?

### Header

- topic name;
- concise approved scope/definition;
- related/sub-topics only when taxonomy supports them.

### Body

1. **Dichiarazioni sul tema** — chronological or relevance-sorted public statements;
2. **Tracce nel tempo** — reviewed proposition/clarification/update threads relevant to the topic;
3. **Contenuti e fonti** — important source/content items from which published statements come;
4. **Persone collegate** — an alphabetical or contextual index for navigation, never ranked by volume or finding state;
5. **Sottotemi / temi collegati** — descriptive navigation, not automatic ideology inference.

A Topic page should feel more like a research dossier; a Person page should feel more like a personal chronology. They share tokens and row components, not the same information architecture.

## 6. Content page — replace public `ContentAudit` vocabulary

Public label: **Contenuto** or the actual source type (`Video`, `Podcast`, `Articolo`, `Intervista`, `Discorso`, `Post`).
Suggested route: `/contenuti/{slug}/`.

**Question answered:** In this original piece of public content, which statements have a published record and where exactly were they made?

`ContentAudit` remains an internal capability / Studio concept, not the public page name.

### Universal header

- source/content title;
- publisher/program/channel/author when public;
- publication date;
- content type;
- duration for timed media;
- source/original/archive link.

### Media mode

For video/audio:

- player;
- restrained evidence tape only when ≥2 published moments exist;
- chronological list of published statement moments;
- selected moment shows concise finding + source path;
- link into the canonical Statement page for full verification.

### Written mode

For article/post/document:

- safe bounded excerpt/locator;
- paragraph/section anchors instead of fake timestamps;
- list of published statements derived from the content;
- author/publisher context where approved.

### Do not show

full private transcript, every extracted candidate, raw model output, four simultaneous panes, or a Studio-like evidence workspace.

## 7. Trace page — replace generic `Compare`

Public label: **Traccia nel tempo**.
Suggested route: `/tracce/{id}/`.

**Question answered:** How did closely related public statements evolve, clarify, update or conflict over time?

This is the signature longitudinal feature and should embody the brand line **“La parola lascia una traccia.”**

### Structure

- one sentence defining the reviewed relation/thread;
- chronological sequence, not comparison cards by default;
- each event shows exact statement, person, context, date, source and its own finding state when one exists;
- correction/reply events live in the same chronology when relevant;
- relation type is explicit (`chiarimento`, `aggiornamento`, `stessa proposizione`, `cambio di posizione candidato`, `contraddizione candidata`) and never presented as proof of intent;
- source links at every event;
- optional two-item side-by-side comparison only as a secondary tool when the user explicitly selects two events.

Do not create a dedicated Trace URL for every trivial relation. Small relations stay inline on Statement/Person/Topic pages; promote to a page when the thread has independent explanatory value.

## 8. Method — keep

**Question answered:** How does Dichiarazioni Pubbliche decide what may be published and how can the reader retrace it?

Keep the current document-like direction. Add direct anchored sections for:

- what counts as a public statement;
- sources and provenance;
- finding states;
- uncertainty/non-publication;
- corrections and right of reply;
- longitudinal relations and why contradiction does not imply intent;
- AI/automation boundaries;
- data/API/open-source transparency.

Method should link to live examples in the record rather than adding decorative process cards.

## Supporting trust and utility pages

### Corrections

A chronological public log of material corrections, re-analyses and public replies. It is a trust surface, not a news feed.

### Data & API

Human entry point for JSON/JSON-LD/OpenAPI, feeds and licensing. Keep raw machine contracts out of the primary reader UI.

### Project

Mission, governance, open-source repository, funding/independence disclosures, contact and editorial responsibility.

### Contribute / Suggest

Only when DP-508 abuse controls/intake policy are ready. Separate:

- suggest a public statement/source for review;
- submit a correction;
- exercise right of reply.

They must not share one ambiguous “send us something” form.

## Feature placement map

| Feature | Home | Explore | Statement | Person | Topic | Content | Trace | Method |
|---|---|---|---|---|---|---|---|---|
| Universal search | primary | primary | compact | compact | compact | compact | compact | compact |
| Advanced filters | no | yes | no | scoped | scoped | no | no | no |
| Finding state | row only | row only | primary but restrained | per row | per row | per moment | per event | explanatory |
| Source/provenance | summary | metadata | full | linked | linked | primary | per event | policy |
| Timeline | no | sort/filter | related trace | chronology | topic threads | media moments | primary | no |
| Corrections/replies | no | filter/link | full | linked | linked | linked | events | policy |
| Media player | feature only | no | original moment | no | no | when timed | no | no |
| Full technical provenance | no | no | disclosure | no | no | no | disclosure | explanation |
| Person portrait | no/rare | disambiguation | small context | optional small | no | contextual only | small context | no |
| Account/follow/save | no | no | no | no | no | no | no | no |

## Product features deliberately deferred

Do not add these to the public v1 merely because polished websites often have them:

- login/account system;
- follow people/topics;
- bookmarks/favorites;
- notifications;
- personalized feed;
- comments;
- public chat/LLM assistant;
- popularity/trending scores;
- “most false / most checked / most controversial” rankings;
- dashboards/statistics pages;
- separate institution pages before the public Organization contract has a real user job;
- separate source/publisher profiles unless repeated use proves they need a first-class resource;
- generic category landing pages that simply duplicate Explore filters.

These features can be reconsidered only after a concrete repeated user task justifies them.

## Editorial taxonomy

Do not organize the brand around professions such as “politicians vs influencers”. A person may have several roles over time and the site should not create social tribes.

Use three independent descriptive axes:

1. **Topic** — politics, economy, technology, health, culture, society, science, sport, environment, etc.;
2. **Content/source type** — TV, podcast, article, social post, video, speech/event, official act/document;
3. **Public role context** — time-bounded role shown on a Person/Statement where approved.

The first two are useful filters. The third is context, not a category badge system.

## Vocabulary rebrand

| Internal/current | Public wording |
|---|---|
| Fact-check | Dichiarazione / Verifica |
| Fact-check page | Scheda della dichiarazione (route `/dichiarazioni/...`) |
| Record | Archivio / record only in technical copy |
| Person Record | Archivio di {Nome} / Persona |
| Topic Record | Tema / Dossier del tema |
| ContentAudit | Contenuto; “Dentro la fonte” as section language |
| Compare | Traccia nel tempo |
| Relation | Relazione revisionata / Chiarimento / Aggiornamento / etc. |
| Claim type enum | human Italian label, never raw enum |
| Finding | Esito / verifica in public prose; `finding` stays in API/contracts |
| Source moment | Momento originale / posizione nella fonte |

## Global hierarchy rule

Every public page must answer one question in the first viewport:

- **Home:** what is this / where do I search?
- **Explore:** what is already in the record?
- **Statement:** what was said and what do we know?
- **Person:** what from this person is in the record?
- **Topic:** what has been claimed about this subject?
- **Content:** what in this source was checked and where?
- **Trace:** how did related statements evolve over time?
- **Method:** how does the record earn trust?

If a screen cannot be summarized by one of these questions, it is probably either a utility document, an Explore filter, or a Studio feature—not a new public template.

## Permanent mockup set

The maintained visual prototype set is intentionally finite. A new public page does not
earn its own permanent mockup merely because it has a route.

The permanent mockups are:

1. `home` — Home;
2. `explore` — universal index/search;
3. `statement` — canonical Statement page;
4. `person` — Person archive;
5. `topic` — Topic dossier;
6. `content` — Content page, using the timed-media variant as the most demanding case;
7. `trace` — longitudinal Trace page;
8. `method` — Method document;
9. `utility` — shared document grammar for Corrections, Data & API and Project.

`Contribute` does not receive a permanent mockup until DP-508 and the relevant legal/intake
gates make the route eligible to exist publicly. Edge states (empty search, unresolved
statement, correction notice, blocked intake) are states of these templates, not new page
families.

The source-of-record prototype directory is `prototypes/final-hybrid/`. Legacy prototype
names such as `fact-check`, `record`, `content-audit`, and `compare` are not canonical and
must not remain as the maintained final set after the v3 cutover.

## Implementation order

Implementation of this cutover is tracked by `DP-422`. The architecture and permanent
mockup set are frozen here even while the current Astro routes still expose legacy aliases.

1. Keep Home, Explore, Method as the visual baseline.
2. Rename/rebuild Fact-check as canonical Statement page.
3. Split the shared Record grammar into distinct Person and Topic page contracts while reusing low-level components.
4. Rename/rebuild public ContentAudit as a universal Content page supporting timed and written sources.
5. Replace Compare with Trace and embed small relations inline before creating dedicated thread pages.
6. Add Corrections + Data/API + Project utility documents.
7. Add Contribute only after public-intake abuse/legal gates close.
8. Add redirects/canonical URLs and update structured data/API docs.
9. Re-run mobile/accessibility/visual QA against the frozen design system.

## Acceptance criteria for the re-alignment

The v3 architecture is successful when:

- the user never needs to understand `finding`, `ContentAudit`, `Record`, or relation IDs to navigate;
- the canonical shareable object is a Statement, not a person score or generic article;
- Person and Topic pages have visibly different jobs and hierarchies;
- one Content template handles video, audio and written material without fake timestamps;
- longitudinal relations have a clear, brand-aligned home in Trace without implying intent;
- politics is visually and structurally one domain among many;
- search is global and Explore owns filtering complexity;
- no page duplicates another page's job;
- no login, personalization, trend ranking or dashboard is required for v1;
- every public claim remains source-linked, time-aware, versioned and compatible with the fail-closed public projection.

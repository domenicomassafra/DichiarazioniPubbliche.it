# Dichiarazioni Pubbliche — Public Redesign v4

Date: 2026-10-05  
Status: design implementation brief; subordinate to `PRODUCT.md`, `DESIGN.md`, and `docs/35-public-product-architecture-v3.md`

## Why this brief exists

The public product architecture is already stable enough to implement, but the current visual prototype set still reflects several pre-v3 habits:

- the header/brand mark shown in the frozen mockups does not consistently express the `Segno` contract in `DESIGN.md`;
- Home, Statement, Trace and Explore are visually coherent, but their different user jobs are not yet differentiated enough;
- Trace is a signature product capability but currently reads more like a restrained document timeline than a memorable product interaction;
- Statement gives strong typographic weight to the quotation, but source/context, finding and verification could form a tighter reading path;
- several public labels still resemble older finding/content vocabulary;
- mobile proof exists as a contract but not yet as a complete v4 screen family.

This is a redesign brief, not permission to weaken the public-record invariants or invent new public product surfaces.

## Design skill synthesis

The redesign follows the installed design/marketing skill set:

- `site-architecture`: every page must earn its existence through a distinct user job; keep the public hierarchy shallow and contextual;
- `product-marketing-context` + `page-cro`: Home needs one primary action and obvious trust/discovery paths, not many equal CTAs;
- `frontend-design`: design the page around its job, use real content, one signature move, and preserve route/content/SEO/accessibility truth;
- `design-system`: reuse explicit tokens and component contracts; redesign composition before inventing new components;
- `brand-guidelines`: brand promise and visual character must steer UI without fighting the implementation system;
- `design-impeccable`: select a surface mode, inspect incumbent truth, apply one coherent visual stance, and verify desktop/mobile together;
- `ui-ux-pro-max`: one primary action per screen, mobile-first recomposition, strong hierarchy, predictable navigation, no color-only meaning.

## Public surface modes

The site is not one generic page family.

| Surface | Mode | Primary job |
|---|---|---|
| Home | Persuade + Read | explain the public value and start search |
| Explore | Operate-lite | search/filter the public record efficiently |
| Statement | Read | understand what was said, what is known, and why |
| Person | Read/index | inspect one person's chronology without scoring |
| Topic | Read/dossier | understand one subject through claims, sources and traces |
| Content | Read/media | return to the original source and exact published moments |
| Trace | Read + focused interaction | understand reviewed change over time |
| Method | Read | understand how publication earns trust |
| Utility | Read/document | corrections, data/API, project, privacy/accessibility |

Studio remains an Operate surface and is outside this redesign.

## User stories

### US-36-01 — First visit
As a first-time visitor, I can understand in the first viewport what Dichiarazioni Pubbliche is and immediately search for a person, statement, topic or content item.

### US-36-02 — Verify a statement
As a reader arriving from search/social/a citation, I can identify the exact statement, speaker, time/source, concise finding, rationale and evidence path without first learning internal vocabulary.

### US-36-03 — Return to original context
As a skeptical reader, I can jump from a published statement to the exact original video/audio/text location and back to the verification.

### US-36-04 — Follow change over time
As a reader comparing public positions, I can understand a reviewed sequence of statements, clarifications, corrections or updates without the UI implying intent, deception or a person-level score.

### US-36-05 — Discover the record
As a user who remembers only part of a person, phrase, topic or source, I can search and progressively refine results without navigating separate category silos.

### US-36-06 — Trust the process
As a reader evaluating the project itself, I can find Method, Corrections, Data & API and Project information without those utility pages competing with the main product navigation.

### US-36-07 — Mobile parity
As a phone user, I get the same semantic reading path and actions with recomposed layouts, usable touch targets and no desktop rail simply stacked below the content.

## Design decisions

### DEC-36-01 — Keep the civic-ledger thesis, increase product specificity
Retain Newsreader + IBM Plex, paper/ink/cobalt, hairlines, sparse surfaces, no shadows/gradients and no dashboard chrome. The redesign changes composition, hierarchy and interaction emphasis rather than replacing the brand with a new aesthetic category.

### DEC-36-02 — The Segno becomes the recognisable interaction grammar
Use the cobalt Segno for focus/selection/current moment/open disclosure. The header mark must match the `DESIGN.md` geometry contract instead of introducing a separate quotation-mark identity.

### DEC-36-03 — Three public composition archetypes
Use only three high-level composition grammars:
1. **Entry/index** — Home + Explore;
2. **Record** — Statement + Person + Topic + Content + Trace;
3. **Trust document** — Method + Utility.

They share tokens/components but may not share identical information architecture.

### DEC-36-04 — Statement is the canonical shareable object
The first viewport should bind quotation, speaker/source/time and concise finding. Verification, evidence and original context follow in one obvious reading path. Technical provenance remains progressive disclosure.

### DEC-36-05 — Trace gets the strongest signature interaction
Trace uses a chronology-first evidence rail built from the Segno grammar. Selecting an event changes emphasis and reveals context; it never paints the whole timeline with verdict colors and never infers intent.

### DEC-36-06 — Explore owns discovery complexity
No standalone profession/category landing pages are added. Search/result type switches and progressive filters remain in Explore. Person/Topic/Content/Trace are contextual destinations.

### DEC-36-07 — Home has one primary conversion
The main conversion is successful discovery: start a search or enter Explore. Method is the trust path. No signup CTA, testimonial strip, feature grid, KPI wall, newsletter wall or fabricated social proof.

### DEC-36-08 — Mobile is recomposed
At phone widths, secondary rails become inline disclosures, filters become a sheet, media/tape interactions become touch-first, and the dominant content remains first in DOM/reading order.

## Acceptance criteria

- **AC-36.1:** Home's first viewport communicates product purpose and exposes search with one dominant action.
- **AC-36.2:** Statement's first viewport exposes exact wording, speaker, source/time and concise finding without internal vocabulary.
- **AC-36.3:** Content exposes exact published moments/locators without leaking private transcript/candidates or inventing timestamps for written sources.
- **AC-36.4:** Trace has a distinct chronology-first interaction and no visual language that implies deception, causation or person scoring.
- **AC-36.5:** Person and Topic are visibly different information architectures while sharing system tokens and low-level components.
- **AC-36.6:** Explore remains the only universal discovery/filter hub and every result type has a deterministic canonical route.
- **AC-36.7:** Method and Utility pages use one shared document grammar and remain secondary to the public product.
- **AC-36.8:** Desktop and phone designs pass the frozen typography, contrast, focus, touch, motion and no-horizontal-overflow constraints.
- **AC-36.9:** No new public template is introduced without a distinct user job.
- **AC-36.10:** The final implementation retains projection-only reads and no provider/LLM calls in the public request path.

## Visual proof order

Do not redesign all pages at once.

1. Home — proves brand, entry and search.
2. Statement — proves the canonical record reading path.
3. Trace — proves the signature longitudinal feature.
4. Explore — proves discovery density and controls.
5. Derive Person, Topic and Content from the chosen record grammar.
6. Derive Method + Utility from the chosen document grammar.
7. Verify mobile recomposition and edge states before calling the redesign complete.

The permanent mockup family remains nine screens; the v4 pass replaces their composition after a direction is approved rather than creating more permanent page families.

## Implementation ticket coverage

Every public redesign surface has one explicit implementation owner:

| Scope | Ticket owner |
|---|---|
| Marketing/brand context | DP-423 |
| Visual direction selection | DP-424 |
| Design system/component contract | DP-425 |
| Home + public shell | DP-426 |
| Statement | DP-427 |
| Person | DP-405 |
| Topic | DP-406 |
| Content | DP-407 |
| Trace | DP-408 |
| Static search/index contract | DP-409 |
| Explore page UI | DP-429 |
| Method + Corrections/Data/Project utility grammar | DP-428 |
| Canonical-route cutover + redirects | DP-422 |
| Cross-surface accessibility/performance/SEO acceptance | DP-410 |

There is intentionally no separate implementation ticket for profession/category pages,
login, rankings, a blog, a newsroom, or personalized feeds because v4 does not authorize
those public jobs.

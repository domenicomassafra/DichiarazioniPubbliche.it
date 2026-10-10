# DP-422 — Public Product Architecture v3 route/template migration

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-405, DP-406, DP-407, DP-408, DP-409, DP-426, DP-427, DP-428, DP-429

## Problem

The repository still contains legacy public route/vocabulary families from the pre-v3
product (`Fact-check`, `Record`, `ContentAudit`, `Compare`). The redesigned page
owners can land independently, but without one cutover ticket the site can ship duplicate
URLs, inconsistent canonical metadata, stale navigation or broken deep links.

## Outcome

Integrate and cut over the real public frontend from the legacy Fact-check / Record /
ContentAudit / Compare route vocabulary to the canonical statement-centered architecture
in `docs/35-public-product-architecture-v3.md`. Page implementation lives in the
page-owner tickets; DP-422 owns deterministic canonical routing, redirects, integration
and final route-set verification without weakening the fail-closed public projection boundary.

## Canonical public templates

1. Home — `/`
2. Explore — `/esplora/`
3. Statement — `/dichiarazioni/{slug}/`
4. Person archive — `/persone/{slug}/`
5. Topic dossier — `/temi/{slug}/`
6. Content — `/contenuti/{slug}/`
7. Trace — `/tracce/{id}/`
8. Method — `/metodo/`
9. shared utility-document grammar for `/correzioni/`, `/dati/` and `/progetto/`

`/contribuisci/` remains gated by DP-508 and the relevant legal/intake policy closure.

The maintained visual references are the nine mockups in `prototypes/final-hybrid/`.

## Scope

- replace public-facing `Fact-check`, `Record`, `ContentAudit` and `Compare` wording with
  the v3 vocabulary while keeping internal/API names where they are contractual;
- integrate the distinct Person and Topic page jobs delivered by DP-405/DP-406;
- make the DP-427 Statement route the canonical shareable object;
- integrate the DP-407 Content template for timed and written sources;
- integrate the DP-408 chronology-first Trace route;
- integrate the DP-426 Home/shell, DP-429 Explore, and DP-428 Method/utility routes;
- add canonical URLs and legacy redirects only when identifier mapping is deterministic;
- preserve stable machine IDs in the public contract even when human URLs use slugs.

## Dependencies and sequencing

- page ownership remains with DP-405..DP-409 and DP-426..DP-429;
- DP-425 owns the v4 visual/component system;
- DP-401 owns the static hosting/deploy contract;
- DP-402/DP-403 own public API/resource contracts;
- this ticket runs after page owners so redirects/canonical integration are proved against
  real targets, not placeholders.

## Traceability & constraints

- **Traces to:** DEC-36-03, DEC-36-06, AC-36.6, AC-36.9, AC-36.10 and the canonical route
  map in `docs/35-public-product-architecture-v3.md`.
- **Constraints:** no duplicate canonical public objects; no unsafe best-effort redirects;
  public navigation stays minimal; projection-only reads; no provider/LLM request path.

## Acceptance criteria

- [ ] `AC-422.1` The real public route set contains all canonical v3 primary templates and
  no new public template without a distinct page job.
- [x] `AC-422.2` Legacy public URLs resolve through deterministic canonical redirects (or
  remain explicit aliases until such redirects are safe); no content becomes unreachable.
- [x] `AC-422.3` Public navigation is `Esplora`, `Metodo`, and search; Person/Topic/Content/
  Trace remain contextual result/entity types rather than permanent nav clutter.
- [x] `AC-422.4` Person and Topic pages have visibly different information architectures.
- [x] `AC-422.5` Content supports both timed media and written locators without fabricating
  timestamps.
- [x] `AC-422.6` Statement and Trace preserve source links, time, version/correction history
  and the no-intent-inference rule.
- [x] `AC-422.7` Public pages continue to consume only the approved fail-closed projection;
  no LLM/provider call appears in a public request path.
- [x] `AC-422.8` Desktop and mobile QA match the selected v4 design contract and the
  maintained `prototypes/final-hybrid/` page families.
- [x] `AC-422.9` Astro check/build, Python boundary tests and legacy-route/canonical-route
  tests pass from a clean clone.

## Non-goals

- login, follows, bookmarks, notifications or personalized feeds;
- popularity/ranking dashboards;
- public Studio/corpus surfaces;
- a first-class Organization page before a concrete repeated public user job exists;
- launching public intake before DP-508 and legal gates close.

## Validation / proof

- enumerate the built route set and verify every canonical v3 route family is present;
- verify every legacy public URL either redirects deterministically or remains an explicit
  documented compatibility alias with canonical metadata;
- crawl internal links and report zero broken canonical destinations;
- verify sitemap/canonical/robots output contains no private/Studio/demo route;
- run `cd web && npm run check && npm run build`;
- run public projection/boundary tests and `git diff --check`;
- capture representative redirect/canonical receipts from the MiniPC deployment mirror.

## Documentation, data, and migration impact

Update public-route documentation, redirect/canonical policy and the final-hybrid route
mapping. This ticket does not change the operational schema; identifier migrations remain
owned by their domain/public-contract tickets.

## Completion receipt

Local route integration is now executable. `web/scripts/check-route-contract.mjs` enumerates
the built site and requires every v3 family (`/`, `/esplora/`, `/dichiarazioni/`, `/persone/`,
`/temi/`, `/contenuti/`, `/tracce/`, `/metodo/` plus utility documents). The current demo build
passes with 32 HTML routes. Sixteen legacy Fact-check/Record/Content/Compare URLs remain explicit
compatibility aliases for now; each must emit a deterministic canonical target in the v3 family,
and every target must exist in the same build. The checker also crawls 443 same-site HTML links
with zero broken static destinations. The ordinary public build now materializes zero
`/studio/**` routes; the four private Studio workspaces exist only in the explicit Studio
fixture build. SiteHeader exposes only Esplora, Metodo and search as permanent public navigation.

The static quality/client scan finds no database/provider runtime marker in the public request
path. The route checker now enforces the distinct Person chronology/no-person-score IA versus
the Topic dossier/context IA; local Chrome screenshots visually confirm the two layouts differ.
Content locator acceptance is exercised twice: the ordinary demo build has three timed-locator
pages, while the DP-407 fixture build has two timed pages plus one written `Passaggio 420–612`
page. Written selection is labeled `Passaggio selezionato` and the checker rejects a fabricated
clock timestamp. Statement pages must expose the source, version state and `#storia`; Trace pages
must expose chronology, original-source links and the explicit no-intent boundary. These checks
close AC-422.4 through AC-422.6 locally. The full selected-v4 desktop/mobile visual comparison
remains open under AC-422.8; DP-408, DP-409 and DP-429 remain completion gates.

Clean-clone acceptance was rerun on 2026-10-06 from a fresh clone of `HEAD` with no dirty files:
`npm ci`, `astro check` (0 errors/warnings/hints), the explicit demo build and
`check-route-contract.mjs` all pass. The route receipt is 32 HTML routes, 16 compatibility
aliases, 443 same-site links, three timed locator pages and zero written-locator pages for that
fixture. The projection/schema/API boundary set also passes **153/153** tests from the clean
clone. This closes AC-422.9 independently of the shared dirty integration tree. AC-422.8 remains
open for the selected-v4 desktop/mobile visual comparison; DP-408, DP-409 and DP-429 remain
completion gates.

The final approved-empty production shape is now covered explicitly as well. Against fingerprint
`501348d9638e...`, the route checker expects exactly the six static canonical pages and rejects any
fabricated Statement/Person/Topic/Content/Trace or legacy alias when the search index has zero
records. The same checker retains the full populated-fixture assertions above. This is machine
route-contract evidence only; it does not close AC-422.8's manual comparison with the selected v4
visual references.

### 2026-10-10 — literal DP-422.8 desktop/phone closure audit (still open)

At Mac `f0357ba`, an explicit demo-projection `npm run build` emitted **32 pages**;
`npm run check` reported **0 errors/warnings/hints**, and `npm run check:routes`
reported **16** deterministic compatibility aliases and **443** valid internal links.
The real Chrome `npm run check:browser` now audits **all nine canonical page
families** at **1440×900 desktop**, **375×812 phone**, and **exact 200% browser
zoom** (1280 outer / 640 CSS / DPR 2), without horizontal overflow. It also
exercises grayscale Person rendering, the accessible Person heading, keyboard
opening/closing of Person phone filters with focus restoration, and detects
external/provider requests (**0**). All browser assertions pass. This is a
fuller route QA matrix, not a real VoiceOver human session.

Visual evidence (the 18 desktop/phone, nine zoom, grayscale and three annotated
comparison PNGs) is retained outside Git at
`/Users/domenico/ControlCenter/_local/dp422-qa-20261010/screenshots/`.
Comparing each desktop family with the frozen
`prototypes/final-hybrid/{home,explore,statement,person,topic,content,trace,method,utility}.png`
shows remaining significant visual differences: Home uses a stacked oversized
hero/search composition where the reference places search alongside the
introductory statement; Method renders a centered, oversized trust-document
opening rather than the reference's two-column explanatory/document layout;
the Corrections utility route uses an oversized standalone hero instead of
the reference's compact shared utility-document composition. These are
layout differences, not merely different demo text. The Content reference
shows a player, but the current public fixture correctly refuses to fabricate
a media player without a separately approved playable source; that boundary
must be kept when reconciling the design.

Read-only MiniPC runtime on 2026-10-10: `dichiarazioni-pubbliche-web.service`
is active, and the approved public search index fingerprint is
`501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`
with **zero** public search records. All six canonical static routes return
HTTP 200; the explicit demo Person and Statement routes return **404**, as
required by fail-closed production. Consequently the dynamic screenshot
matrix exercises **local demo** content only; no demonstration figure was
promoted into the approved projection. A native VoiceOver user pass was not
available in this Mac session and is not claimed.

**Closure decision: keep AC-422.8 unchecked and DP-422 IN PROGRESS.** The
selected-v4 desktop composition differences have not been reconciled by their
page owners; populated routes cannot yet be observed from the approved
production projection, and dependency completion for DP-408/409/429 remains
open. The additional browser QA cannot by itself certify the literal visual
contract or complete the dependent ticket graph. No production deployment,
rights change, migration or ticket closure was performed.

### 2026-10-10 — AC-422.8 actual implementation and acceptance (supersedes previous visual hold)

The three concrete composition defects above were corrected in live Public
templates rather than waived: `index.astro` now places the search alongside
the source-first Home introduction under the frozen brand line “La parola
lascia una traccia”; `UtilityDocument.astro`, `metodo.astro`,
`primitives.css` and `legacy.css` render the shared two-column trust document
with a contextual Method index and compact Corrections/Data/Project document
headings. On phone, the contextual rail follows the introduction in DOM order
and precedes the body; it is not visually reordered with CSS. The Corrections
page also replaces raw Finding version IDs with the canonical public Statement
history link, maintaining the append-only version path.

Manual inspection of the new 1440px desktop and 375px phone Chrome receipts
against the nine frozen `prototypes/final-hybrid` reference families confirms
that the Home hero/search, Method document/side index and utility-document
compositions now follow the maintained page jobs. The runtime-dependent
Content reference's playable-media panel is **conditional**: no player is
invented when rights and playable source URL are absent from the approved
projection. Source path and approved public locators remain accessible. The
visual check accepts this required data/rights difference; it does not treat
the separate demo text/people as approved production data.

The strengthened `web/scripts/check-browser-qa.mjs` now asserts real layout
geometry for Home/Method/Utility on desktop and phone, full-nine-family
desktop/phone and exact 200% zoom, Person grayscale/keyboard/AX checks,
without-color/reduced-motion behavior and zero external/provider fetches.
Twenty-seven family/viewport captures, plus the earlier comparison proofs,
are held **outside Git** under
`/Users/domenico/ControlCenter/_local/dp422-qa-20261010/layout-fix/`.
Astro check/build, route/canonical, design, correction-consistency and
public-quality checks pass. The existing released MiniPC approved projection
remains intentionally empty; no dynamic Person/Statement/Topic/Content/Trace
or fake fixture has been published, and no human VoiceOver test is claimed
for the separate DP-410/429 accessibility acceptance.

**AC-422.8 is now complete for its defined local visual/route QA contract.**
DP-422 itself stays **IN PROGRESS** because its declared downstream
integration dependencies DP-408 (BLOCKED reviewed live Trace), DP-409 and
DP-429 (manual AT and upstream gates) remain unfinished; the accepted
projection has no dynamic records for the final production route integration
proof. No status or approval of those tickets is inferred here. No
production deployment, commits or changes to `PLAN.md` were performed.

### 2026-10-10 — independently pinned live MiniPC readback and clean-clone E2E

This follow-up checks the original AC-422.1–.9 against the actual runtime,
without recasting the **9/9 locally checked AC** as completion of the declared
dependencies. Added `tools/check_dp422_live_readback.py` and adversarial
`tests/test_dp422_live_readback.py` (5 negative/positive cases). The CLI
executes its own source on MiniPC via a **single read-only SSH session**: no
file write, site rebuild, fixture import, runtime promotion or service restart.
It requires an **externally pinned** approved projection fingerprint, so an
inconsistent or silently replaced index/API cannot self-certify.

Actual `minipc` same-origin `127.0.0.1:18090` readback on the approved
fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`
returns `PASS_APPROVED_EMPTY_ONLY`: 6 informational canonical routes HTTP 200,
8 explicit demo/private/legacy routes HTTP 404, index/API/health/four public
resource-list fingerprints identical and empty, 6 sitemap canonical URLs,
safe robots/meta/canonical headings/navigation, and 1 actual static stylesheet
fetched successfully. The checker **always** reports
`production_dynamic_route_approval=false` and `dp422_done=false` in this mode;
a six-page site can never impersonate a populated v3 route cutover.

Clean Git clone at committed `1e15db5` (independent of the 10 intentionally
dirty frontend WIP files): `npm ci` PASS; Astro check 0 diagnostics; build
against the exact approved-empty MiniPC public JSON emitted 8 HTML pages
(6 canonical informational + 2 noindex Account utilities); route/quality/
design/correction checkers PASS with **0 legacy aliases and 121 internal
links**. The same clean clone was rebuilt with the isolated **fictional**
DP-407 schema-valid fixture for integration testing only: 56 HTML pages, 27
legacy aliases, 872 internal links, 2 timed Content locator pages, 1 written
locator page, 2 versioned correction/reply results; route/quality/correction/
`check:m4-grammar` all PASS. Actual Chrome `check:browser` PASS for nine v3
page families desktop/phone, keyboard, reduced motion, real 200% zoom, and
**zero external/provider requests**. This fixture stayed on the local Mac
clean clone and was **never** promoted to MiniPC or public production.

**Literal closing gate still absent:** the present approved projection has
zero public dossiers, Topic memberships and reviewed Trace relations. Its
true runtime therefore cannot supply representative canonical/legacy dynamic
route readback required by this ticket's Validation/Proof, notwithstanding the
complete clean-clone **structural** acceptance. Furthermore its explicit
Depends-on set contains unresolved DP-405/406/407/408/409/429: DP-405.3 needs
an approved first-class zero-record Person (not representable by the current
dossier-derived route set); DP-406/408 need real approved Topic/relation
canaries; DP-409/429 and adjacent M4 surfaces retain independent human AT
checks. These cannot be closed by a demo, an empty HTTP 200 or the presence
of checkmarks. **DP-422 remains IN PROGRESS — no false DONE, no `PLAN.md`
status change.** Once editorially approved dynamic resources exist, rerun
the published canonical/legacy/API/readback contract against that exact
fingerprint, complete the declared dependencies, and then change status.

### 2026-10-10 — final AC-422.1 literal production-state correction

The earlier **9/9 checked** bookkeeping inadvertently treated an isolated
fictional fixture's dynamic routes as proof of the **real public route set**
required by the literal AC-422.1. The committed route templates are present
and clean-clone/Chrome fixture integration passes, but the real MiniPC
approved-empty projection intentionally generates only the six public
informational routes (plus separately noindex Account utility pages). It
does **not** contain published canonical Statement/Person/Topic/Content/Trace
resources or their canonical/legacy readback. Thus **AC-422.1 is re-opened**
until one independently approved populated projection exercises the real
canonical route-family set with immutable fingerprint and live HTTP readback.
AC-422.2–.9 retain their existing independently proven *local/structural*
acceptance; this correction claims neither downstream ticket completion nor
site launch. **DP-422 and PLAN remain IN PROGRESS; no fake runtime GO.**

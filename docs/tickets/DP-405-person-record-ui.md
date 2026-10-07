# DP-405 — Person archive UI

Status: IN PROGRESS

Milestone: M4 — public product/API
Depends on: DP-105, DP-425

## Problem

A Person record must let a reader understand what a public figure said and which
reviewed findings exist over time without turning the person into a scorecard. The
current frontend has a basic route, but the public resource, dated Role Interval
semantics, complete state behavior, and accessibility proof are not yet a stable product
contract.

DP-105 ratified `dichiarazioni-pubbliche-public-v2`. The route must prefer approved dated
`public_roles` when present and treat legacy `public_role` as compatibility input only;
the frontend must not infer a missing interval.

## Outcome

Implement the v3 Person archive. A reader can scan one person's neutral chronology,
filter published statements, open canonical Statement/Content/Trace destinations, and
inspect role context valid for the relevant statement date. The page is rendered only
from the approved public projection/API and remains useful when all providers are offline.

## Contract gate

- DP-105 is the hard data and identifier gate;
- `docs/35-public-product-architecture-v3.md` is the canonical IA gate;
- DP-425 is the v4 visual-token/component gate; Person reuses low-level system
  components but must not collapse into the Topic dossier information architecture;
- no role or biography may be inferred when the stable contract does not provide an
  approved, time-bounded value.

## Scope

### Public route and rendering

The existing `/record/<person>/` route is a demo/baseline alias. DP-105 and DP-401 are
complete; preserve safe legacy links until DP-422 performs the canonical route cutover so
this ticket does not create duplicate public records or ad-hoc redirects.

The canonical route is `/persone/{slug-or-id}/` with deterministic identifier mapping.
The route renders:

1. Person identity and the approved public role context relevant to the displayed
   chronology;
2. a short neutral scope statement when the contract supplies one;
3. a chronological list of published finding versions;
4. topic, date, claim-type, and media/source filters defined by the shared Record
   grammar;
5. links to each Statement, Content, and reviewed Trace when those links are
   public and present in the contract;
6. a correction/right-of-reply link when the public history contains one.

The route may reuse row/tokens/components with DP-406, but Person and Topic must remain
visibly different page jobs: Person is a chronology; Topic is a dossier.

### Role and time semantics

- Prefer a dated Role Interval resolved as of the statement or publication date;
- show the interval source/reference link when the public contract provides it;
- if no approved interval applies, omit the role rather than inventing one;
- treat a legacy `public_role` value as compatibility input only until DP-105 declares its
  semantics; it must not create a timeless current-role assertion;
- never use role text as a truth, reliability, ideology, or political classification;
- never display a person-level aggregate, streak, rank, or verdict total.

### Chronology and filtering

- default order is statement time/publication time descending, with a stable finding ID
  tie-breaker;
- filters are ordinary public controls with visible labels and a reset action;
- filter state is represented in the URL so a result can be shared and restored;
- desktop may expose a compact filter bar; mobile uses one `Filtri` control and a sheet;
- filtering operates on public-safe fields only and does not query the operational DB;
- an omitted or unsafe dossier is absent from counts and chronology; the UI must not
  reveal that it was omitted.

### Required states

| State | Required behavior |
|---|---|
| Populated | Show claim-first rows, source/date context, and a direct path to evidence. |
| Empty public history | Explain that no public checks are currently available for this Person; link to Explore and Method; do not show a fake row or a “0 reliability” message. |
| Unknown Person | Return a public 404/empty route state with a useful Explore link; do not distinguish an unknown ID from a private ID. |
| Contract mismatch | Fail the static build or show a bounded unavailable state; do not fall back to demo data in production. |
| Stale/missing projection | Show a deliberate unavailable state with no cached unsafe record; preserve navigation. |
| Loading/filter update | Keep the current filter context visible and announce result-count changes without replacing the reading order. |
| Correction/reply | Show version-aware history and link to the relevant finding; never overwrite the original. |

## Non-goals

- a Person dashboard, profile score, reliability grade, ideology classifier, or ranking;
- private biography reconstruction, CV/resume scraping, or unrelated private-life data;
- biometric identification or inference from an image/voice;
- a separate Person search algorithm (DP-409 owns the shared index);
- a second design system or a new navigation shell (DP-425/public architecture v3 own those seams);
- raw transcript/evidence bodies, provider/model output, or private replies;
- live LLM calls, auto-publication, or public intake;
- changing DP-105's public schema from the frontend.

## Dependencies and gates

- **DP-105:** hard public Person resource, role-interval, identifier, and compatibility
  gate;
- **Public architecture v3:** Person archive IA and no-scorecard rules;
- **DP-425:** final v4 token/component contract for production acceptance;
- **DP-402/DP-403:** if the page uses HTTP resources rather than build-time projection,
  the route must use their stable contract and examples;
- **DP-407/DP-408:** linked Content/Trace surfaces, not duplicated data;
- **ADR 0001/0002:** projection-only reads and no LLM request path.

## Traceability & constraints

- **Traces to:** US-36-05, US-36-07, DEC-36-03, AC-36.5, AC-36.8, AC-36.10.
- **Constraints:** Person is chronology-first, not a scorecard/profile dashboard; no
  inferred timeless role; approved projection only; reuse DP-425 components without
  copying Topic's dossier IA.

## Acceptance criteria

- [x] `AC-405.1`: Given an approved Person resource with several published finding
  versions, when the route renders on desktop or mobile, then it shows a neutral,
  claim-first chronology with source/date context and a direct Statement path.
- [x] `AC-405.2`: Given a dated Role Interval, when a row is displayed, then the role is
  resolved for that row's relevant time and linked to its public provenance; when no
  approved interval exists, the role is omitted.
- [ ] `AC-405.3`: Given a Person with no public records, when the route renders, then the
  empty state explains the public-data boundary, offers Explore/Method navigation, and
  contains no placeholder, score, or hidden omission count.
- [x] `AC-405.4`: Given an unsafe, stale, tampered, or contract-incompatible projection,
  when the build or request runs, then the Person page fails closed and does not use the
  demo fixture or a stale browser record.
- [x] `AC-405.5`: Given a correction or approved right of reply, when the history is
  present, then the page links both finding versions and preserves the original record;
  private or unreviewed history is absent.
- [ ] `AC-405.6`: Given any page state, when rendered without color, when zoomed to
  200%, and when navigated by keyboard, then headings, rows, links, filters, and status
  labels remain understandable and operable.
- [x] `AC-405.7`: Given the visual implementation, when compared with architecture v3
  and DP-425, then Person reads as a chronology, is visibly distinct from Topic, has one
  dominant task, and does not introduce a Person-only component zoo or dashboard chrome.
- [x] `AC-405.8`: Given the collision/dependency audit runs, then DP-405 is the only
  owner of the Person route, DP-406 owns Topic, and DP-425's shared component ownership
  is not duplicated.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

A fixture matrix must cover populated, empty, unknown, missing/invalid projection, dated
role present, dated role absent, correction, and reply states. Exercise the actual static
route on phone and desktop widths, keyboard-only navigation, 200% zoom, reduced motion,
and a screen-reader pass over headings, chronology, filters, and status labels. Verify
that no operational database/provider/LLM request occurs during the build or public read.

Runtime-affecting completion requires the route to be served from the MiniPC deployment
mirror through DP-401 and the approved public projection. Record the route, projection
fingerprint, representative HTML output, and a no-score/raw-content inspection.

## Documentation, data, and migration impact

- consume the ratified DP-105 public Person/role fields; any new role-time schema belongs
  to the domain/public-schema owner, not this UI ticket;
- update the shared component contract through DP-425, not a Person-only CSS
  appendix;
- no migration is introduced by the UI ticket; role migrations belong to DP-101/DP-105;
- do not edit `PLAN.md`.

## Completion receipt

- Added canonical `/persone/{slug}/` static routes and moved both legacy Person aliases
  onto the same `PersonRecord.astro` implementation with canonical metadata pointing to
  `/persone/`; DP-422 still owns eventual redirect/removal of the aliases.
- Person is chronology-first and score-free. Rows link to canonical Statements and expose
  approved Trace/history paths only when those records exist in the public projection.
- Approved dated `public_roles` are used only when an interval covers the row's relevant
  public date; if no approved interval applies, role context is omitted rather than
  inferred from the legacy timeless role string.
- Added bounded source/type/date filters with shareable URL state and an announced result
  count. Desktop uses the inline filter bar; narrow screens expose one `Filtri` control and
  a bounded sheet-like panel with an explicit close action.
- Public claim-type codes are rendered through human Italian labels instead of exposing
  raw underscore taxonomy in the repeated row/filter UI.
- Unknown/private-only people remain indistinguishable at the static route boundary: no
  route is emitted without at least one projectable public dossier. Contract-invalid or
  stale projection state still fails the static build through the existing loader.
- Local visual receipts: `prototypes/v4-implementation/dp405/person-desktop.png` and
  `person-mobile.png`, manually inspected against the real component tree.
- Local validation: full Python suite **986/986 PASS**, restore verification PASS,
  `npm run check:design` PASS, `npm run check` 0 diagnostics, explicit projection builds
  PASS, and `git diff --check` PASS.
- MiniPC proof on 2026-10-05: authoritative source was synchronized without deleting
  runtime-local state; `compileall`, `npm ci`, design check and Astro check passed; a
  production build against projection fingerprint
  `8c430c1bb36ad8135c313247d6cf276ffc6fea6c2f998e31f9d55aa02da85383` emitted
  `/persone/person-selvaggia-lucarelli/`; the active same-origin service returned HTTP 200.
  Representative HTML contains the Person name, chronology heading and explicit no-score
  boundary, while `person_score`, `reliability_score`, `leaderboard`, `raw_text`,
  `transcript_text`, and `evidence_body` are absent.

### Bookkeeping audit — 2026-10-07

The previous `DONE` header was too strong for the literal acceptance text and is now
`IN PROGRESS`. The receipt proves AC-405.2, AC-405.4, AC-405.7 and AC-405.8. Four criteria remain
open rather than being inferred from adjacent evidence:

- AC-405.1 requires a Person fixture/runtime route with several published finding versions;
  the recorded demo/runtime receipts do not prove that exact state.
- AC-405.3 requires an approved Person route with zero public records to render a deliberate
  empty state, while the current implementation intentionally emits no Person route without at
  least one projectable dossier.
- AC-405.5 requires the Person surface to prove both finding versions for correction/reply
  history; the current receipt proves a link to Statement history, not that stronger literal
  surface behavior.
- AC-405.6 requires Person-specific without-color, exact 200% zoom and keyboard acceptance;
  the current cross-surface browser automation is Explore-centric and is not substituted for
  that missing Person matrix.

No current implementation or historical receipt is rewritten into a pass for the remaining
zero-record and manual-accessibility cases.

### Populated chronology/history refresh — 2026-10-07

The current DP-407 public-schema fixture also supplies a deterministic populated Person
acceptance case. Its canonical `/persone/person-demo-maintenance/` page renders **12 published
finding rows** for the same approved Person, with chronology, source labels and per-finding
assessment labels. The fixture contains one approved correction and one approved right of reply;
the Person surface renders the corresponding version-aware `Correzioni e repliche` links to the
Statement history instead of replacing the original chronology entry. The populated snapshot
passes route/quality/correction consistency plus browser and performance QA with zero external
requests.

This closes AC-405.1 and AC-405.5. AC-405.3 remains open because the public projection currently
does not emit a Person resource/route with zero public records; filter-result emptiness is not
substituted for that stronger state. AC-405.6 remains open because automated keyboard/zoom/AX
inspection is not substituted for the required real screen-reader/manual acceptance.

# DP-427 — Canonical Statement page v4

Status: DONE
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-425, DP-105

## Problem

Statement is the canonical shareable object, but the current public implementation still uses the legacy Fact-check route/vocabulary and the existing visual hierarchy separates quotation, finding, source and context more than the v4 reading path should.

## Outcome

Implement `/dichiarazioni/{slug}/` as the canonical v4 Statement page: exact wording, speaker/source/time, concise finding, verification, evidence, original context, reviewed trace links and version/correction history in one source-first reading flow.

## Scope

- canonical statement route/template;
- first viewport binds statement + attribution/source/time + concise finding;
- verification prose with contextual evidence markers;
- reviewed sources grouped by what they establish when useful;
- original media/text locator;
- reviewed trace preview where it has explanatory value;
- corrections/replies/version and progressive technical provenance.

## Non-goals

- person score/ranking;
- giant verdict badge or theatrical stamp;
- generic related-content recommendations;
- raw transcript/model output;
- live analysis/chat.

## Traceability & constraints

- **Traces to:** US-36-02, US-36-03, DEC-36-04, AC-36.2, AC-36.10, AC-422.4, AC-422.6.
- **Constraints:** source-first, finding belongs to statement only, append-only history, fail closed, no internal vocabulary required to read the page.

## Acceptance criteria

- [ ] canonical `/dichiarazioni/{slug}/` renders only approved public projection data;
- [ ] first viewport exposes wording, speaker, source/time and concise written finding;
- [ ] evidence and rationale can be retraced to reviewed source links;
- [ ] timed and written original contexts use the appropriate locator semantics;
- [ ] corrections/replies preserve version history instead of silently rewriting;
- [ ] phone/desktop hierarchy remains understandable without color and at 200% zoom.

## Validation / proof

Standard Python/public-projection tests plus `cd web && npm run check && npm run build`, desktop/phone screenshot comparison against selected v4 proof, keyboard/screen-reader pass and no-provider-request inspection.

## Documentation, data, and migration impact

Update canonical route references and Statement mockup. Redirect ownership remains in DP-422.

## Completion receipt

- Added the canonical `/dichiarazioni/{slug}/` static route backed only by the approved
  public projection. Legacy `/fact-check/{slug}/` remains available for DP-422 cutover but
  now declares the canonical Statement URL.
- The first viewport binds exact wording, speaker, source/date/locator, written finding
  state and concise rationale. Timed sources expose a bounded time locator; approved
  written-source provenance is represented by the public selector rather than a fake
  timestamp.
- Added the v4 source-first reading path: verification, reviewed evidence links, original
  source context, reviewed Trace links, correction/reply history, and technical
  provenance behind progressive disclosure.
- Public reply/correction rendering consumes only records that already survived the
  projection publication gate; no raw transcript/model output is exposed.
- Internal Statement links in `ClaimRow`, Explore, Content moments and legacy Compare now
  point to `/dichiarazioni/`; Compare copy no longer says “Apri il fact-check”.
- Extended the web `PublicDossier` type with the already-ratified public
  `source.text_provenance` shape so written-source locators can render without inventing
  fields.
- Visual receipts: `prototypes/v4-implementation/dp427/statement-desktop.png` and
  `statement-mobile.png`; both were manually inspected after a real static build.
- Validation: `python3 -m compileall -q poc tests` PASS; 44 focused public-schema /
  public-projection tests PASS; `npm run check:design` PASS; `npm run check` 0
  errors/warnings/hints; explicit demo-projection static build PASS with all three
  `/dichiarazioni/` routes emitted; `git diff --check` PASS.

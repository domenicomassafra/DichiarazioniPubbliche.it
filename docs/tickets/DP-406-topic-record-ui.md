# DP-406 — Topic record UI

Status: READY

Milestone: M4 — public product/API
Depends on: DP-105, DP-413

## Problem

A Topic record is the neutral archive for claims and evidence around a subject over time.
It must not become a people leaderboard, a partisan taxonomy, or a second Explore page.
The public resource, topic identifier, scope, and relation semantics are not yet stable
while DP-105 remains open.

## Outcome

Implement the Topic half of the shared Record template from UX v2. A reader can
understand what a topic covers, scan a chronological set of public finding versions,
filter the record, and open a fact-check or reviewed comparison without inferring a
political position or person-level score.

## Contract gate

- DP-105 is the hard data and identifier gate;
- DP-413 is the frozen information-architecture gate;
- DP-412 is the final visual-token/component gate; fixture work may use the current
  candidate system, but production acceptance must use the consolidated contract;
- a topic must come from the approved public contract. The frontend must not create,
  merge, or rename topics from model output or a generic keyword.

## Scope

### Public route and rendering

The canonical route is `/record/topic/{topic_id}/` (or the exact alias ratified by
DP-105). It renders:

1. topic name and an approved one-line scope/definition when available;
2. a neutral chronological list of public finding versions;
3. topic, date, claim-type, and media/source filters defined by the shared Record
  grammar;
4. links to Fact-check, ContentAudit, and reviewed longitudinal relations when present;
5. correction/right-of-reply links through the linked finding history.

Topic and Person share the Record layout, row anatomy, filter behavior, and responsive
composition. They differ only in the header contract and entity link target.

### Topic semantics and chronology

- topic IDs and labels are stable public identifiers, not free-form model labels;
- a topic definition is descriptive context, never a political classification;
- a claim may be linked to more than one topic only when DP-105 explicitly supports that
  relationship;
- chronology uses statement/publication time with a stable finding ID tie-breaker;
- assessment state belongs to each finding row and is never aggregated across a topic;
- relation links appear only for reviewed public relations from DP-104/DP-105;
- no “supporters,” “opponents,” “most checked,” or person ranking is derived from topic
  membership.

### Required states

| State | Required behavior |
|---|---|
| Populated | Show scope, claim-first rows, source/date context, and evidence path. |
| Empty public history | Explain that no public checks are currently available for this Topic and link to Explore/Method; do not infer a topic from a private row. |
| Unknown Topic | Return a public 404/empty route state with a useful Explore link; do not reveal private existence. |
| Ambiguous label | Resolve only through the stable topic ID; do not silently redirect between similarly named topics. |
| Contract mismatch | Fail the static build or show a bounded unavailable state; never use demo content in production. |
| Stale/missing projection | Omit unsafe records and show a deliberate unavailable state with navigation preserved. |
| Filter update | Keep the selected topic/date/type filters and announce the result count; do not collapse the reading order into an opaque dashboard. |
| Correction/reply | Preserve the original finding version and expose only reviewed/public history. |

## Non-goals

- political topic sentiment, ideology, influence, or recommendation scores;
- automatic topic clustering, taxonomy generation, or model-created labels;
- a full-web or general search engine (DP-409 owns bounded public indexing);
- a Topic-only design system or navigation shell;
- raw transcript/evidence bodies, provider output, or private replies;
- a live analysis/chat route or LLM request path;
- public intake, auto-publication, or a claim about a topic's truth;
- duplicating the shared Record component grammar in a second implementation.

## Dependencies and gates

- **DP-105:** hard public Topic resource, identifier, scope, relation, and compatibility
  gate;
- **DP-413:** shared Record IA and neutrality rules;
- **DP-412:** final token/component contract;
- **DP-402/DP-403:** stable read resource and examples, if the page is not built directly
  from the static projection;
- **DP-408:** reviewed relation semantics and comparison route;
- **ADR 0001/0002:** projection-only reads and no LLM request path.

## Acceptance criteria

- [ ] `AC-406.1`: Given an approved Topic with several public finding versions, when the
  route renders on desktop or mobile, then it shows the approved scope and a neutral,
  claim-first chronology with direct evidence paths.
- [ ] `AC-406.2`: Given a topic label that is similar to another topic, when a user opens
  the route by ID, then the page resolves only the requested stable Topic and does not
  merge, redirect, or infer a replacement.
- [ ] `AC-406.3`: Given a Topic with no public records, when the route renders, then the
  empty state explains the public-data boundary and offers Explore/Method navigation
  without a placeholder, score, or hidden omission count.
- [ ] `AC-406.4`: Given a stale, tampered, unsafe, or incompatible projection, when the
  page is built or requested, then it fails closed and does not fall back to demo data or
  a stale record.
- [ ] `AC-406.5`: Given a reviewed relation or correction/reply history, when the page
  links to it, then the target preserves finding-version and review semantics; candidates
  and private records are not rendered.
- [ ] `AC-406.6`: Given any state, when viewed without color, at 200% zoom, and with
  keyboard/screen-reader navigation, then scope, chronology, filters, links, and finding
  states remain understandable and operable.
- [ ] `AC-406.7`: Given the visual implementation, when compared with DP-405, Person and
  Topic demonstrably share the Record grammar and the page has one dominant task with no
  dashboard/KPI/scorecard additions.
- [ ] `AC-406.8`: Given the collision/dependency audit runs, then DP-406 owns only the
  Topic route and shared Record ownership is not duplicated.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

A fixture matrix must cover populated, empty, unknown, ambiguous-label, missing/invalid
projection, multiple-topic, correction, and relation states. Exercise the actual static
route on phone and desktop widths, keyboard-only navigation, 200% zoom, reduced motion,
and a screen-reader pass. Verify no operational database/provider/LLM request occurs.

Runtime-affecting completion requires the route to be served from the MiniPC deployment
mirror through DP-401 and the approved public projection. Record the route, projection
fingerprint, representative HTML output, and a no-score/raw-content inspection.

## Documentation, data, and migration impact

- document the public Topic resource and scope semantics only after DP-105 ratifies them;
- update the shared Record/component contract through DP-412, not a Topic-only appendix;
- no migration is introduced by the UI ticket; topic persistence/schema changes belong
  to their domain tickets;
- do not edit `PLAN.md`.

## Completion receipt

Pending implementation. The route is not DONE while DP-105 is unresolved, even if a
fixture-based Topic page renders in development.

# DP-424 — Public visual redesign v4 concept selection

Status: FUTURE  
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-423, DP-412

## Problem

The current final-hybrid mockups are coherent but still under-express the v3 page jobs and the strongest brand/product gestures. A redesign should improve composition and interaction hierarchy without drifting into generic news, SaaS, government portal or dashboard aesthetics.

## Outcome

Produce and compare a small number of materially distinct redesign directions for Home, Statement and Trace, then select one coherent direction for the rest of Public. The result is a reviewable visual decision, not implementation code.

## Scope

- inspect the incumbent Home/Statement/Trace screenshots and frozen design system;
- create 2–4 materially distinct composition directions while preserving the civic-ledger brand;
- each direction must specify hierarchy, density, Segno behavior, typography emphasis, source/finding treatment, mobile posture and risks;
- compare against product fit, accessibility, content fit, reuse potential and implementation cost;
- select one direction and record rejected alternatives;
- produce desktop and phone proof for the selected direction.

## Non-goals

- changing the public site map;
- adding effects, gradients, glass, shadows, decorative motion or dashboard chrome;
- coding production routes;
- introducing a new component library;
- redesigning Studio.

## Dependencies and sequencing

Blocked by DP-423 so the Home/brand decision is grounded in explicit audience/conversion context. Blocks the v2 design-system/component refresh.

## Traceability & constraints

- **Traces to:** US-36-01, US-36-02, US-36-04, US-36-07, DEC-36-01..08, AC-36.1, AC-36.2, AC-36.4, AC-36.8.
- **Constraints:** preserve paper/ink/cobalt, Newsreader + IBM Plex, Segno, no shadows/gradients, no ranking/person score, one dominant visual anchor per first viewport.

## Acceptance criteria

- [ ] at least two materially different composition directions exist for all three key screens;
- [ ] each uses real/source-backed content shapes rather than fake marketing proof;
- [ ] one direction is explicitly selected with rationale and rejected alternatives are recorded;
- [ ] selected Home, Statement and Trace each have one dominant task and one coherent signature move;
- [ ] selected desktop and mobile proofs preserve semantic reading order and do not rely on color alone.

## Validation / proof

Attach rendered desktop and phone screenshots for Home, Statement and Trace and a design-review matrix against `DESIGN.md`, v3 IA and the v4 brief. No claim of completion without visual proof.

## Documentation, data, and migration impact

Update the maintained prototype direction only after selection. No runtime/data migration.

## Completion receipt

Pending implementation.

# DP-423 — Public product marketing + brand context

Status: READY  
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-400, DP-413

## Problem

The repo has strong product, UX and visual-system contracts but no concise shared product-marketing/brand context artifact. Home copy, trust hierarchy and redesign decisions therefore risk rediscovering audience, job, differentiation and primary conversion logic on every pass.

## Outcome

Create one bounded public-facing context source that states audience/jobs, differentiation, proof, objections, voice, brand promise and the primary conversion action for the public site. It must derive from existing project evidence rather than inventing testimonials, metrics or a new positioning layer.

## Scope

- synthesize existing product/UX/competitive research into reusable marketing context;
- define Home's primary conversion as successful discovery/search, not signup;
- define trust paths and anti-fit/non-goals;
- define verbal brand promise/voice rules that complement rather than duplicate `DESIGN.md`;
- record missing evidence explicitly.

## Non-goals

- new product features or routes;
- campaign/content calendar;
- fabricated social proof, testimonials or usage metrics;
- visual token changes;
- changing `PRODUCT.md` invariants.

## Dependencies and sequencing

None beyond the completed public research/IA baseline. This can start immediately and blocks the visual concept selection.

## Traceability & constraints

- **Traces to:** US-36-01, US-36-06, DEC-36-07, AC-36.1, AC-36.7.
- **Constraints:** no fabricated proof; no signup/account requirement; preserve public-record neutrality and source-first positioning.

## Acceptance criteria

- [ ] one concise reusable marketing context artifact exists and is internally consistent with `PRODUCT.md`;
- [ ] target audiences, jobs, trigger situations, differentiation, objections, anti-fit, voice and proof types are explicit;
- [ ] the public site's primary conversion and trust paths are explicit;
- [ ] assumptions/missing customer evidence are marked rather than inferred as fact.

## Validation / proof

Cross-check the artifact against `PRODUCT.md`, `docs/35-public-product-architecture-v3.md`, `DESIGN.md` and the competitive UX research. `git diff --check` must pass.

## Documentation, data, and migration impact

Documentation only. No runtime/data migration.

## Completion receipt

Pending implementation.

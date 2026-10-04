# DP-413 — Simplify public UX architecture before visual implementation

Status: DONE  
Milestone: M4 research track  
Depends on: DP-400

## Problem

The initial competitive research and generated A/B/C concepts proved useful, but the
mockups accumulated dashboard-like cards, counters, side panels and simultaneous feature
surfaces. That made the product look more like an AI concept board than a deliberately
designed fact-checking product.

## Outcome

Reduce Dichiarazioni Pubbliche to five public page templates, two Verify Studio templates and a small
component grammar before visual implementation or design-system work.

## Acceptance criteria

- Home has only understand/search/recent checks/featured ContentAudit + exploration paths;
- archive complexity lives in Explore;
- one Fact-check page has a strict claim -> answer -> rationale -> evidence hierarchy;
- Person and Topic share a Record template;
- ContentAudit remains distinct from the denser private Studio;
- Studio has Sessions and Workspace as primary screens;
- no aggregate person score, implicit scorecard or decorative KPI wall;
- component grammar is intentionally small;
- typography/whitespace/dividers are preferred over ubiquitous cards;
- mobile hierarchy is specified independently rather than desktop merely stacked.

## Completion receipt

`docs/32-public-ux-architecture-v2.md` is the current implementation guidance.
`docs/31-implementable-ia-design-spec-v1.md` is preserved as superseded design history.
The generated A/B/C concepts are explicitly exploratory and not implementation targets.

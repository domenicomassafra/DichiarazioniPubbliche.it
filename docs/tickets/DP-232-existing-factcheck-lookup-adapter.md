# DP-232 — Existing fact-check lookup adapter

Status: FUTURE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-228, DP-215

## Problem

The research ecosystem selected Google Fact Check Tools and existing ClaimReview corpora
as cheap external lookup sources, but the current evidence planner has no dedicated adapter.

## Outcome

Add a provider-neutral EXISTING_FACT_CHECK research adapter, with Google Fact Check Tools
as one possible implementation and CIMPLE/other ClaimReview corpora as replaceable sources.
Existing fact-checks are secondary/context evidence and discovery aids, not automatic truth
authority.

## Acceptance criteria

- [ ] Adapter returns normalized reviewed-claim text, publisher, review URL/date, rating
  text and original-claim locator when available.
- [ ] Result preserves provider/source identity and retrieval receipt.
- [ ] Existing fact-check verdict/rating never maps directly to our Finding assessment.
- [ ] Same upstream ClaimReview mirrored by several services counts as one derivation
  lineage when identified.
- [ ] Provider/API key absence is explicit BLOCKED/not-configured, not empty success.
- [ ] Query/result/cost limits come from DP-228.
- [ ] Rights/public projection expose only allowed metadata/links.

## Completion receipt

Pending provider/policy selection.

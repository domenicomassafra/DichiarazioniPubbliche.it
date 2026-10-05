# DP-232 — Existing fact-check lookup adapter

Status: IN PROGRESS
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

- [x] Google response normalizer returns reviewed-claim text, publisher, review URL/date,
  textual rating and original claim metadata when available.
- [x] Fixed-endpoint Google adapter supports bounded query, language, publisher, max-age,
  page-size and page-token parameters with injected transport for deterministic tests.
- [x] Provider receipt omits API key/full URL/raw query and retains a query hash.
- [ ] Persist normalized lookup results and retrieval receipt through the DP-228/DP-209
  research lane.
- [x] Result preserves provider/source identity and bounded retrieval receipt.
- [x] Existing fact-check verdict/rating has no field/path mapping directly to our Finding
  assessment.
- [ ] Same upstream ClaimReview mirrored by several services counts as one derivation
  lineage when identified.
- [x] Missing API key fails explicitly before any network request; DP-228 integration must
  map this to its BLOCKED/not-configured state rather than empty success.
- [ ] Query/result/cost limits are inherited from persisted DP-228 assignments; the local
  client already enforces a bounded page size/max-age request contract.
- [ ] Rights/public projection expose only allowed metadata/links.

## Completion receipt

Google Fact Check Tools normalizer + bounded client contract added locally 2026-10-05.
No live API call or key was used. DP-228 persistence/execution, lineage integration and
MiniPC/provider receipt remain open.

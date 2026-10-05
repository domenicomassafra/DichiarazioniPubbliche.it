# DP-430 — First-class public Topic resource contract

Status: READY

Milestone: M4 — public product/API
Depends on: DP-105, DP-114

## Problem

The knowledge layer has reviewed Topic entities, but the authoritative
`dichiarazioni-pubbliche-public-v2` projection does not publish a first-class Topic
resource or approved claim-to-Topic links. The current public API intentionally exposes
`topic` only as a read-only facet derived from `claim_type` and explicitly states that the
projection carries no Topic table.

DP-406 cannot safely implement `/temi/{slug-or-id}/` from that facet. Doing so would turn
an internal claim taxonomy into a public subject taxonomy and would create identifiers,
scope text and membership semantics in the frontend.

## Outcome

Ratify and implement the smallest fail-closed public Topic contract needed by DP-406:
stable Topic identity, approved scope, approved Statement membership, and enough
provenance/version information for a static Topic dossier to resolve without querying an
operational database or model provider.

## Scope

- decide the backward-compatible projection shape/version for public Topic resources;
- expose stable opaque Topic ID plus a deterministic human slug/identifier policy;
- expose approved canonical name and optional approved scope/definition;
- expose only reviewed public claim/finding membership for each Topic, or an equivalent
  bounded relation that the static web build can resolve deterministically;
- expose approved related/sub-topic relationships only when the domain contract supports
  them;
- preserve provenance/review identifiers required to audit Topic identity and membership;
- extend projection validation so malformed, stale, private or unreviewed Topic data fails
  closed;
- update the public API so `/topics` represents the ratified Topic resource rather than
  silently equating Topic with `claim_type`, with an explicit compatibility decision for
  the existing facet behavior;
- provide deterministic fixtures covering multiple Topics, similar labels, zero public
  findings, multi-topic membership when approved, and rejected/private memberships.

## Non-goals

- automatic topic generation, clustering or labeling from model output;
- ideology, sentiment, supporter/opponent or partisan classification;
- person ranking or finding aggregation by Topic;
- a generic tag system;
- UI implementation of the Topic dossier (DP-406 owns that);
- full-web search (DP-409 owns bounded public indexing).

## Dependencies and gates

- **DP-105** supplies the authoritative fail-closed public projection/versioning rules;
- **DP-114** supplies reviewed Topic identity/resolution in the knowledge layer;
- existing publication/review gates remain mandatory: a knowledge-layer Topic is not
  public merely because it exists;
- any schema change must remain compatible with public JSON/JSON-LD/API guarantees or
  explicitly version the contract.

## Acceptance criteria

- [ ] `AC-430.1`: Given an approved Topic, the public projection exposes a stable ID,
  canonical public name, optional approved scope and deterministic route identifier.
- [ ] `AC-430.2`: Given an approved Statement-Topic membership, the projection exposes it
  without deriving membership from free text or `claim_type` in the frontend.
- [ ] `AC-430.3`: Given an unreviewed/private/rejected Topic or membership, it is omitted
  from the public projection and cannot be recovered through the API.
- [ ] `AC-430.4`: Similar Topic labels remain distinct through stable IDs; no fuzzy or
  display-name redirect merges them.
- [ ] `AC-430.5`: Missing, stale, malformed or incompatible Topic data fails closed rather
  than falling back to demo/facet-derived content in production.
- [ ] `AC-430.6`: The public API documents the difference between subject Topics and the
  claim-type taxonomy and does not silently preserve the old conflation.
- [ ] `AC-430.7`: Fixtures/tests cover populated, empty, ambiguous-label, multi-topic,
  private/rejected and tampered/stale cases.

## Validation / proof

At minimum:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check
cd .. && git diff --check
```

If the web/projection runtime is changed, also build against an approved fixture/projection
and prove production mode does not fall back to demo content. Runtime-affecting completion
requires the normal MiniPC/deployment-mirror proof from `AGENTS.md`.

## Documentation, data, and migration impact

- update the canonical public schema/API documentation and examples;
- record the schema/version compatibility decision explicitly;
- additive knowledge persistence is preferred; do not rewrite reviewed historical Topic
  identity or membership to satisfy the UI;
- DP-406 becomes READY only after this ticket is DONE.

## Completion receipt

Pending implementation.

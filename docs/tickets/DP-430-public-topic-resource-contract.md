# DP-430 — First-class public Topic resource contract

Status: DONE

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

- [x] `AC-430.1`: Given an approved Topic, the public projection exposes a stable ID,
  canonical public name, optional approved scope and deterministic route identifier.
- [x] `AC-430.2`: Given an approved Statement-Topic membership, the projection exposes it
  without deriving membership from free text or `claim_type` in the frontend.
- [x] `AC-430.3`: Given an unreviewed/private/rejected Topic or membership, it is omitted
  from the public projection and cannot be recovered through the API.
- [x] `AC-430.4`: Similar Topic labels remain distinct through stable IDs; no fuzzy or
  display-name redirect merges them.
- [x] `AC-430.5`: Missing, stale, malformed or incompatible Topic data fails closed rather
  than falling back to demo/facet-derived content in production.
- [x] `AC-430.6`: The public API documents the difference between subject Topics and the
  claim-type taxonomy and does not silently preserve the old conflation.
- [x] `AC-430.7`: Fixtures/tests cover populated, empty, ambiguous-label, multi-topic,
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

- Added the additive `claim_topic_membership` persistence contract and migration
  `20261005-add-public-topic-memberships.sql`. An ACTIVE knowledge Topic is still private
  by default: public projection requires the latest `TOPIC` review event to be APPROVED,
  and each claim membership independently requires an APPROVED
  `CLAIM_TOPIC_MEMBERSHIP` review event.
- Extended `dichiarazioni-pubbliche-public-v2` with an **optional** top-level `topics`
  collection. Pre-DP-430 v2 bundles without the key remain valid; new builders always emit
  it. This additive compatibility decision is recorded in
  `docs/release/versioning-policy.md`.
- Topic resources contain stable Topic ID, deterministic slug, canonical name, optional
  approved scope, entity version, Topic review IDs, and reviewed claim memberships.
  Memberships are emitted only when their claim has a projectable public finding; private
  claim existence is therefore not leaked through Topic membership.
- New projection fingerprints cover both `dossiers` and `topics`; bundle verification
  keeps the legacy dossiers-only hash algorithm only when the optional `topics` key is
  absent.
- `/api/v1/topics` now represents first-class reviewed subject Topics and never falls back
  to `claim_type`. The draft `topic=` findings filter remains only as an explicitly
  deprecated compatibility alias; `claim_type=` is the canonical filter. Person API
  summaries distinguish deprecated claim-type aliases from `subject_topic_ids`.
- Updated generated OpenAPI/LLM API documentation and the web projection runtime type/
  fail-closed validator. Malformed Topic identity, review provenance, membership, or
  finding/claim linkage is rejected rather than inferred.
- Backup/restore inventories include `claim_topic_membership`.
- Added `tests/test_public_topics.py` covering reviewed publication, old-v2 compatibility,
  similar labels, private/non-projectable membership omission, malformed Topic failure,
  API resource semantics, filter compatibility, and schema/migration/backup coverage.
- Local gates: full Python suite **1039/1039 PASS**, restore verification PASS,
  `npm run check:design` PASS, Astro check **0 errors / 0 warnings / 0 hints**, explicit
  demo build PASS, `git diff --check` PASS.
- MiniPC gate on 2026-10-05: pre-migration database backup saved at
  `/tmp/dp430-pre-migration.sql`; additive migration applied successfully;
  `claim_topic_membership` exists with 0 rows and there are currently 0 approved Topic /
  membership reviews. A fresh real-DB projection verified successfully with
  `topics: []`, was installed after confirming claim artifacts were unchanged, and is
  served by the same-origin service with fingerprint
  `d2a10bbe824cf7b1c2d301b13b6116e3c2ff6d58c9be1f9cff3a3f6c341cc904`.
  `/api/v1/topics` returns HTTP 200 with an empty array instead of synthesizing
  claim-type facets. The live bundle passes `verify_projection_bundle.py`.

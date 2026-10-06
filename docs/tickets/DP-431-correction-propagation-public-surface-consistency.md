# DP-431 — Correction/retraction propagation across every public surface

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-303, DP-402, DP-403, DP-405..DP-409, DP-422, DP-427..DP-429, DP-434

## Problem

DP-303 defines an append-only correction/takedown/appeal workflow and the current static
bundle removes stale projection-owned artifacts, but the redesigned product will expose the
same Statement through multiple derived surfaces: Statement, Person, Topic, first-class
Content, Trace, Explore, API, JSON-LD/RDF, search indexes, canonical metadata and social/SEO
artifacts.

A correction is unsafe if the canonical page updates while an old attribution or wording
remains discoverable elsewhere. This ticket closes that integration gap.

## Outcome

Make every public representation of a corrected, superseded, held or retracted record
derive from one finding-versioned/public-projection state and prove atomic/stale-safe
regeneration. No surface may keep serving a superseded false attribution because its cache
or index was not rebuilt.

## Scope

- Inventory every public projection consumer and generated artifact.
- Define one projection/version fingerprint consumed by Statement, Person, Topic, Content, Trace,
  Explore/search, API/OpenAPI examples, JSON-LD, sitemap/canonical metadata and social
  preview data where present.
- On correction/supersession/hold, rebuild or invalidate all affected derived artifacts.
- Recompute first-class Content `finding_ids`/moments from the corrected projection and keep
  independently reviewed Content metadata only while its own publication assertion remains valid.
- A stale/mismatched derived artifact fails closed (omit/bounded unavailable state), never
  falls back to an operational/private table.
- Preserve append-only public history where policy allows while ensuring the latest
  canonical representation is unambiguous.
- Deep links to historical versions must be explicit historical views, not accidentally
  cached current pages.
- Record a propagation receipt listing affected identifiers/artifacts, old/new projection
  fingerprint and cleanup result.

## Non-goals

- No change to the substantive correction/takedown policy owned by DP-303.
- No silent deletion of private/audit history.
- No CDN/vendor-specific architecture unless the chosen host actually requires it.
- No redirect from a corrected Statement to unrelated content.

## Acceptance criteria

- [ ] **AC-431.1:** One correction/supersession updates Statement, Person, Topic/Trace
  relations, Content finding membership/moments, Explore/search, API and structured metadata
  consistently from the same public projection version.
- [x] **AC-431.2:** Old generated files/index entries are removed or versioned explicitly;
  a rebuild cannot leave an orphan serving the superseded attribution.
- [x] **AC-431.3:** Search results cannot show stale quote/person text after the canonical
  Statement has been corrected/held.
- [ ] **AC-431.4:** JSON-LD/social/canonical metadata use the corrected/held state and cannot
  preserve stale wording independently of the page body.
- [x] **AC-431.5:** Partial build/cache failure fails closed for affected records and emits
  an operator-visible receipt/error instead of mixing old/new versions.
- [ ] **AC-431.6:** Historical version/correction links preserve auditability without
  presenting superseded wording as current fact.
- [ ] **AC-431.7:** A public hold/takedown removes the affected current projection while
  private append-only history remains intact under DP-303/DP-304/DP-305 policy.
- [ ] **AC-431.8:** Mobile/web/API/public static tests and MiniPC/static-host rehearsal prove
  the same version fingerprint across all affected surfaces.

## Validation / proof

Create a synthetic canary Statement, project it, correct its wording/person/source state,
reproject and inspect every route/artifact/index. Include partial-build and stale-file
failure injection. Run Python/public tests, web check/build, `git diff --check`, and the
runtime/static-host read-back required by the implemented architecture.

## Documentation, data, and migration impact

Prefer projection/build/index changes over new domain tables. Update public build/ops docs
and DP-428 Corrections documentation when implemented.

## Completion receipt

Local `correction-propagation-v1` checker/receipt seam added without changing the dirty
public projection/schema/API/web consumers. Given an old and new public projection plus a
search-index manifest, linked-data receipt and route/static manifest, it computes affected
Finding, Content, Person and Topic identifiers and requires every derived artifact to bind
to exactly one new projection fingerprint. Missing artifacts, partial route/static manifests,
mixed fingerprints, stale search text, removed current identities, orphan entries and stale
entity hashes fail closed with a deterministic receipt.

The receipt keeps removed/superseded Finding version IDs in `historical_finding_ids` while
`current_finding_ids` contains only the new projection state. Historical static entries are
optional under policy, but if exposed they must be explicitly `HISTORICAL`, retain the old
Finding entity hash, and still be regenerated under the single new projection fingerprint;
the same historical ID cannot masquerade as a current route/search record. An in-place
mutation of a Finding under the same version ID is also rejected.

Synthetic correction, hold and retraction fixtures prove affected-ID calculation, first-class
Content membership changes, stale/old search entries, stale Content route membership hashes,
historical/current separation, missing/partial artifacts and mixed fingerprint detection.
On the web side, `web/scripts/check-correction-consistency.mjs` now consumes the built static
search index and rendered pages. For every corrected/replied finding in the fixture it requires
the canonical Statement `#storia` anchor, correction/reply content, the correction-register link,
and matching history links from every Person/Topic/Content/Trace surface that links the Statement;
the canary currently covers one corrected finding across four derived surfaces. Explore likewise
links its correction indicator directly to `#storia`.

`web/scripts/dp431_rebuild.py` now provides the actual local static rebuild/invalidation path.
For a changed projection fingerprint it first retires the current served directory and installs a
bounded `HOLD` page with an operator receipt, then runs Astro with `--force` into a clean sibling
staging directory. The staged bundle regenerates `search-index.v1.json`, `index.nt` and
`linked-data-receipt.json`, inventories every generated file under the new projection fingerprint,
builds the DP-431 route/static manifest from files that actually exist, and reuses
`check_correction_propagation` before the staged directory can replace the hold. Statement,
Person, Topic, Content and Trace route families plus their current legacy aliases must exactly
match the new projection; entity pages must contain the current public entity text. Any mismatch
leaves the public directory in `HOLD` with no old search index or entity routes reachable.

`npm run check:rebuild` exercises both a correction and a hold from the demo projection. The
correction replaces one finding version while keeping shared Person/Topic/Content/Trace routes and
proves those pages contain the corrected wording only; the old Statement and old search record are
absent. The hold removes the affected Statement, Person, Content and Trace while retaining only
new-projection routes. A seeded unrelated stale static file is also removed by the clean rebuild.
Four failure injections (`after-invalidate`, stale removed Statement, stale search fingerprint and
partial current route) all fail closed to the hold page and write a `HOLD` operator receipt rather
than publishing a mixed bundle. This local evidence closes AC-431.2, AC-431.3 and AC-431.5.

AC-431.1/.4/.6/.7/.8 remain open for API/structured-metadata convergence where applicable,
historical-view/private-history proof, and the MiniPC/static-host rehearsal with the same
fingerprint across every public surface.

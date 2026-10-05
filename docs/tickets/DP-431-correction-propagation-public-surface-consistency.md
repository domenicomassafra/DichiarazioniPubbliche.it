# DP-431 — Correction/retraction propagation across every public surface

Status: FUTURE  
Milestone: M4 — Public product, API, and hosting  
Depends on: DP-303, DP-402, DP-403, DP-405..DP-409, DP-422, DP-427..DP-429

## Problem

DP-303 defines an append-only correction/takedown/appeal workflow and the current static
bundle removes stale projection-owned artifacts, but the redesigned product will expose the
same Statement through multiple derived surfaces: Statement, Person, Topic, Trace, Explore,
API, JSON-LD, search indexes, canonical metadata and social/SEO artifacts.

A correction is unsafe if the canonical page updates while an old attribution or wording
remains discoverable elsewhere. This ticket closes that integration gap.

## Outcome

Make every public representation of a corrected, superseded, held or retracted record
derive from one finding-versioned/public-projection state and prove atomic/stale-safe
regeneration. No surface may keep serving a superseded false attribution because its cache
or index was not rebuilt.

## Scope

- Inventory every public projection consumer and generated artifact.
- Define one projection/version fingerprint consumed by Statement, Person, Topic, Trace,
  Explore/search, API/OpenAPI examples, JSON-LD, sitemap/canonical metadata and social
  preview data where present.
- On correction/supersession/hold, rebuild or invalidate all affected derived artifacts.
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
  relations, Explore/search, API and structured metadata consistently from the same public
  projection version.
- [ ] **AC-431.2:** Old generated files/index entries are removed or versioned explicitly;
  a rebuild cannot leave an orphan serving the superseded attribution.
- [ ] **AC-431.3:** Search results cannot show stale quote/person text after the canonical
  Statement has been corrected/held.
- [ ] **AC-431.4:** JSON-LD/social/canonical metadata use the corrected/held state and cannot
  preserve stale wording independently of the page body.
- [ ] **AC-431.5:** Partial build/cache failure fails closed for affected records and emits
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

Pending public route implementation and DP-303 integration.


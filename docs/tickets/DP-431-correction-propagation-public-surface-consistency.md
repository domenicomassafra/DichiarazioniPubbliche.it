# DP-431 — Correction/retraction propagation across every public surface

Status: DONE
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

- [x] **AC-431.1:** One correction/supersession updates Statement, Person, Topic/Trace
  relations, Content finding membership/moments, Explore/search, API and structured metadata
  consistently from the same public projection version.
- [x] **AC-431.2:** Old generated files/index entries are removed or versioned explicitly;
  a rebuild cannot leave an orphan serving the superseded attribution.
- [x] **AC-431.3:** Search results cannot show stale quote/person text after the canonical
  Statement has been corrected/held.
- [x] **AC-431.4:** JSON-LD/social/canonical metadata use the corrected/held state and cannot
  preserve stale wording independently of the page body.
- [x] **AC-431.5:** Partial build/cache failure fails closed for affected records and emits
  an operator-visible receipt/error instead of mixing old/new versions.
- [x] **AC-431.6:** Historical version/correction links preserve auditability without
  presenting superseded wording as current fact.
- [x] **AC-431.7:** A public hold/takedown removes the affected current projection while
  private append-only history remains intact under DP-303/DP-304/DP-305 policy.
- [x] **AC-431.8:** Mobile/web/API/public static tests and MiniPC/static-host rehearsal prove
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

The rebuild canary now also drives the read-only `/api/v1` adapter directly from the corrected
or held projection. It requires the API health/detail/Content responses to carry the new dataset
fingerprint, rejects the superseded/held Finding as `404`, and verifies that Content membership
contains only the corrected Finding. The canonical Statement now emits projection-derived social
metadata and JSON-LD with the current Finding identifier/wording/route; the canary rejects stale
title, social URL, JSON-LD identity or wording. Its history block exposes the current Finding ID,
the superseded Finding ID and correction version IDs while derived surfaces continue linking to
the current `#storia` anchor. This closes AC-431.1, AC-431.4 and AC-431.6 locally without creating
a separate historical public route.

### MiniPC rebuild rehearsal — 2026-10-06

The rebuild guard was exercised on the synchronized MiniPC after moving its temporary
acceptance workspace onto the web filesystem (avoiding cross-filesystem `EXDEV` rename
failures). It passes the correction and hold scenario with fingerprints
`00ede66707f0 -> 7f1ef323b7d0` and `8c932ddf05a5`, removes stale
Statement/Person/Topic/Content/Trace/search/static artifacts and keeps all four injected
partial failures fail-closed. This runtime proof closes the DP-431 integration dependency
used by DP-510.

The expanded current-tree canary was then copied to an isolated MiniPC workspace and rerun after
the API/social/JSON-LD/history assertions were added. `npm run check:rebuild` passes there with
the same correction `00ede66707f0 -> 7f1ef323b7d0` and hold `8c932ddf05a5`; search, API health/
detail/Content read-back, Statement canonical/social/JSON-LD metadata and current/superseded
history all converge on the rebuilt projection fingerprint, while all four failure injections
remain fail closed. This closes AC-431.8's MiniPC/static-host rehearsal requirement.

`web/scripts/check_dp431_private_hold.py` supplies the missing AC-431.7 integration proof with an
ephemeral PostgreSQL database and the existing DP-303 private challenge store. It creates a
TAKEDOWN request for the exact demo Finding, advances it through reviewed
`PUBLIC_HOLD_APPROVED`, records the private append-only chain, rebuilds the public bundle with the
same Finding held out, and then replays the private store. Both Mac and MiniPC pass: the held
Statement/search record is absent under public fingerprint `8c932ddf05a5`, while exactly one
private request and three integrity-bound events remain byte/ID/hash-equivalent and the current
private read model still returns authoritative `HOLD`. No correction/takedown policy was changed.

### MiniPC production promotion — 2026-10-06

The current main candidate was promoted to the canonical MiniPC mirror after a verified private
backup. The two new additive migrations were applied twice successfully, the approved public
projection was rebuilt, and the production static bundle was rebuilt from that exact projection.
After restart, the API health fingerprint, static search `projection_sha256`, and the private
linked-data validation receipt all equal
`501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`.
`/index.nt` returns `200 application/n-triples` with the expected validators; the receipt remains
an internal sibling validation artifact rather than a public route. The approved projection is
currently empty, so search correctly contains zero records and no dynamic Statement/Person/Topic/
Content/Trace route is fabricated. This removes the previously recorded live DP-401 static/API
drift and completes the runtime portion of AC-431.8.


## Owner round aggiuntivo — 13 ottobre 2026

Q8 link ordinario alla versione corrente, avviso visibile di correzione materiale e collegamento distinto a storico quando disponibile e consentito. Non ripubblicare contenuto ritirato o privo di diritti nello storico; mantenere coerenza tra pagina/search/API.

Decisione/ricerca futura registrata: nessuna implementazione o acceptance nuova, status e criteri originali invariati.

## 2026-10-13 — Post-closure search-index metadata integrity hardening

An independent source review found a fail-open inconsistency in the already
implemented public correction-propagation checker: while the record title and
projection SHA were current, an index row could carry stale, missing or extra
searchable metadata under the same version. The initial five-field Finding-only
check also skipped absent keys and never compared Person, Topic or Content
metadata. That allowed a stale Person label, role term, Topic scope, Content
subtitle or route to survive a correction without a propagation HOLD.

The checker now reconstructs the complete canonical v1 `PublicSearchRecord`
for **Finding, Person, Topic and Content** from the current approved public
projection, matching `web/src/lib/searchIndex.ts` including current Topic
membership, first occurrence of a Person, first-class/legacy Content,
wording type, date precedence, flags, route and primary/secondary search terms.
Every row must match the complete allowlisted record; missing fields, extra
private terms, stale identity/facets and old route data cause
`SEARCH_INDEX_STALE_METADATA` and a fail-closed HOLD. Previous stale-title,
duplicate, orphan and partial-entry protections remain in force.

Synthetic RED→GREEN regressions cover the original optional-key bypass, all
four record kinds and missing/extra search metadata. The existing correction
fixtures were upgraded to the complete real schema rather than weakened in
production. Real TypeScript `buildSearchIndexMaterial` and an independent
Python fixture constructor agreed on six projection scenarios. On the
integrator's copied final three-file source patch, 66 focused projection and
correction tests, Python compileall, the deterministic 5/5 benchmark, and
`git diff --check` pass. Full suite and independent final review are separate
release evidence. The preexisting `check:rebuild` demo-seed guard currently
rejects a normal public build of demonstration records; its public safety
check has **not** been disabled or bypassed to manufacture acceptance.

This is a **source-only post-closure security improvement**. The historical
6 October MiniPC/static-host acceptance and original `Status: DONE`/AC remain
unchanged; this commit is not a fresh MiniPC promotion, live rights approval,
provider run or production deployment.

## 2026-10-14 — Restore fail-closed local rebuild acceptance coverage

The existing `npm run check:rebuild` fixture harness could not exercise its
actual correction/hold checks because it built known demo records through the
**production** Astro path without explicit demo opt-in. The production guard
properly refused those records before the new strict metadata checker ran.
This was a test-harness incompatibility, not a reason to authorize demo data
for public publication.

`web/scripts/check_dp431_rebuild.py` now enables demo mode **only in its own
temporary directory beneath `web`**, for the seed and a scoped test-only
replacement of the Astro build callback. The production
`web/scripts/dp431_rebuild.py::_run_astro_build` remains unchanged and still
strips demo opt-in. The test asserts the resulting fixture seed, hold/correction
builds all keep `noindex,nofollow`, `robots.txt` Disallow, and no sitemap URLs;
it cannot silently generate a normally crawlable demo site.

The complete `npm run check:rebuild` is GREEN (correction, hold, stale-file
cleanup, current API/search/route/metadata/history parity and four injected
partial failures correctly HOLD). The independent
`node web/scripts/check-production-projection-boundary.mjs` remains GREEN:
renamed demo records without explicit opt-in are still rejected, opt-in local
demo builds stay nonindexable, and empty genuine-shape projection builds work.
`npm run check:search` also passes. Before this test-only follow-up the source
patch had passed **3,445/3,445** full Python unit tests and benchmark **5/5**;
the original DP-431 MiniPC proof/status/AC remain untouched. No live rollout.

## 2026-10-14 — Final remote-branch source-only review and TS/Python parity

Reviewed the **actual committed branch** `b3944cb2ec3694fe0d446dff0cc891443aa8a8ae`
against the unmodified `main` base `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`.
The original worker's three changed test/source files match the integrator
**byte for byte** (`cmp` succeeded independently for each file). No earlier
dirty worker file, stash or other worktree was deleted or overwritten.

The previously unavailable worker review was **not** relabeled as complete.
A bounded in-session **source-only two-axis diff review** checked standards
(no external provider/corpus I/O, fail-closed behavior, bounded prepublication
scope, no new production authorization) and original DP-431 spec semantics
(revocation/correction fingerprint consistency, missing/extra metadata and
all four published object kinds). No reproducible additional P1/P2 appeared
in that reviewed scope; this is **not** a separate qualified editorial,
browser-user or security certification. The independently written
`web/scripts/check_dp431_typescript_python_parity.py` executes the actual
`buildSearchIndexMaterial` JavaScript/TypeScript module, rather than a second
hand-copied TypeScript expectation, on eight bounded Python-generated
projections. Finding, Person, Topic and first-class/legacy Content records
match the canonical Python checker exactly; an unapproved Topic facet,
private search term, missing field and extra key all cause a propagation
HOLD. Result: `DP431_TS_PY_PARITY_PASS`.

Exactly **one complete Python suite** was run for this final committed tree:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`
returned **3,445 tests, OK (368.843 s), exit 0**. The deterministic benchmark
returned **5/5 PASS**. Real `npm run check:rebuild` returned PASS for the
correction/hold/static/API/history matrix and four fail-closed injections;
`node scripts/check-production-projection-boundary.mjs` returned PASS for
demo refusal, non-indexable fixture mode and empty approved-shape build;
`npm run check:search` returned PASS. The demo-only build seam remains inside
the temporary test harness, and `web/src/lib/projection.ts` and the production
rebuild module are unchanged. The new parity script is an additive local
test harness, not an externally qualified independent signer.

**Original DP-431 DONE and all AC unchanged.** No fresh physical MiniPC,
rights, source or public deployment acceptance. PR/CI exact-head and GitHub
auto-review billing OFF remain unverified; branch push is distinct from merge.

## 2026-10-14 — Independent reviewer P2 and first-class empty-Content correction

The independent read-only reviewer of branch `9a83e0e` reproduced one
real **P2 false HOLD** missed by prior synthetic scenario coverage: a public
schema-valid first-class `contents=[]` with dossiers that reference source
Content IDs results in **zero Content search records** from actual TypeScript
`buildSearchIndexMaterial`, yet the DP-431 search completeness check required
legacy Content records because `_current_identity_sets` tracks source lineage
for correction/static-route work. Before the fix, focused regression was
**RED** with `SEARCH_INDEX_PARTIAL` on an otherwise correct search index.

`_check_search_index` now uses the exact expected public search-record keys
for both orphan and completeness checks, not the broader history/static-route
identity set. Route-static/history authority and source Content lineage are
**unchanged**. The same regression is **GREEN** for explicit empty Content;
synthetic private/phantom Content injection still HOLDs as
`SEARCH_INDEX_ORPHAN_ENTRY`, while legacy Content fallback when the collection
is absent still requires genuine canonical records. The independent
Python→real-TypeScript parity matrix now includes the explicit-empty case,
without disabling first-class public Content or weakening production guards.

This is post-DONE source-only hardening; **DP-431 remains DONE with all
original AC and 6 October MiniPC evidence unchanged**, but neither the
reviewer's local tests nor these changes constitute a new MiniPC acceptance,
public publication or source-rights approval. Independent re-review of the
specific correction and final full-suite evidence are recorded separately.

**Post-fix independent review:** reviewer worker-6, STRICT READ-ONLY,
reproduced green first-class `contents=[]` + actual public-schema validator
and real TypeScript materialization; invented private/source Content remained
orphan-HOLD, every missing Finding/Person/Topic remained `SEARCH_INDEX_PARTIAL`,
and omitted source-Content static route still `ROUTE_STATIC_PARTIAL`. **PASS
within bounded source scope, no additional P1/P2**, no code edits by reviewer.
The final updated real TS↔Python parity matrix now covers **9 projections**,
including first-class empty Content; **67 focused tests PASS**. Exactly one
complete post-fix Python suite ran on the final patched source:
**3,446/3,446 PASS, exit 0, 333.829 seconds**. Benchmark deterministic
**5/5 PASS**. End-to-end `npm run check:rebuild` and production-boundary test
both PASS, including four fail-closed injected failures and `noindex` demo
isolation. This does NOT repeat/replace any October 6 physical acceptance.

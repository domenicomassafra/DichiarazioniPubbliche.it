# DP-438 — Person v3 consumer: release candidate and withdrawal

The first-class Person collection is opt-in and fail closed. It is never
populated from private people or from public-v2 dossiers. Build with a
**separately approved, current** Person/Statement/Person×Topic/search release,
verified source provenance, rights, identity and publication status.

## Inputs and surfaces

The release authority supplies two different files:

- `DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_ASSETS_PATH`: the validated
  candidate with `people`, `source`, `join`, `index` and
  `sitemapPersonRoutes`. This is *not* an authority for its own digest.
- `DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH`: independent,
  current release pins for Person/Statement/join/index/Person sitemap
  SHA-256, source generation timestamp, expiry,
  `allowPrivatePersonPreview: true` and
  `publicationAuthorized: true`. Its presence does not authorize a
  release unless issued by the current publication authority with rights and
  review evidence.

The web build enables `DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3=1`
and reads those inputs alongside the existing approved public-v2 projection.
The public-v2 projection must contain **zero dossiers, Topics and Contents**
when v3 is enabled. The build rejects a nonempty legacy projection with
`DP438_LEGACY_PROJECTION_NOT_EMPTY` because those pages, search facets and
sitemap entries use a separate publication authority and could expose
identities withheld by the current Person release. Legacy v2 publication
continues normally when the v3 flag is off. Approved original v3 Statements
are indexed separately from factual Findings and never acquire verdicts.

The generated static files include `/persone/<slug>/` even for zero
Statements, independent approved originals at
`/dichiarazioni/<statement-slug>/`, `search-index.v1.json`,
`sitemap.xml` and `public-people.v3.json`.

To have the Python HTTP host serve the same identities, configure
`DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_API_PATH` to the
**generated** `public-people.v3.json` in the installed static root and
use the **same independently issued** `...PINS_PATH` as the web build.
`/api/v1/people` then exposes this approved collection and
`/api/v1/people/<slug>` exposes approved details. The generated JSON
also carries `release_pins_sha256`, a canonical SHA-256 of the complete
independent pin file. Python rejects any changed source, identity, search,
sitemap, expiry or authorization pin, even if the Person dataset SHA remains
unchanged. The static host checks the root artifact against those current pins,
including requests for previously published paths and pre-redirect requests.
A v3-built static root fails closed if its runtime has `ENABLE=0` or lacks
its current authority. Pins prove consistency; the issuing authority,
rights checks and protected host configuration establish authorization. Python compares its
SHA against the current pins on every request; 404 is identical for
unknown/private/held/revoked identities, 503 for missing/expired/mismatched
publication authority. It does not silently fall back to v2 while enabled.
The same host also returns a non-cacheable 404 for stale static content
during pin withdrawal, including Person/Statement pages, Explore and
search-index/sitemap.

## Candidate, cutover, rollback

1. Build a candidate with the pinned current release and verify static
   Person/Statement pages, search, sitemap, JSON SHA and Python API on a
   **private isolated** listener. Ensure no private/HELD IDs are present.
2. Confirm the independent current release pins and source rights still
   match before cutover. Stage the API runtime environment, exact generated
   JSON path and current pin file in the isolated candidate first; switch
   the served static root and listener to that same verified candidate last.
   Preserve the previous accepted build for rollback. A partial static/env
   swap may deliberately return HTTP 404 for **the entire site** while the
   marker or authority is inconsistent; never allow such a partial swap to
   continue serving stale v3 identities.
3. On identity or rights withdrawal, revoke the current pin first so the
   Python API fails closed; rebuild all pages, JSON/index/sitemap from
   the new authorized release, swap the static root and invalidate any
   previous CDN/static caches before re-enabling public delivery.

The static host cannot retroactively erase a page already cached by a browser
or a CDN. Keep public activation on HOLD until a trusted withdrawal and
cache-purge mechanism and a qualified real-case acceptance have been proven.
Neither the synthetic test fixtures nor the software PR grant GO-PUBLIC.

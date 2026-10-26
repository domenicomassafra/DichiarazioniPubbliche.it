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
The generated static files include `/persone/<slug>/` even for zero
Statements, independent approved originals at
`/dichiarazioni/<statement-slug>/`, `search-index.v1.json`,
`sitemap.xml` and `public-people.v3.json`.

To have the Python HTTP host serve the same identities, configure
`DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_API_PATH` to the
**generated** `public-people.v3.json` in the installed static root and
use the **same independently issued** `...PINS_PATH` as the web build.
`/api/v1/people` then exposes this approved collection and
`/api/v1/people/<slug>` exposes approved details. Python compares its
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
   match immediately before atomic swap of the candidate static tree and
   API environment/pins. Preserve the previous accepted build for rollback.
3. On identity or rights withdrawal, revoke the current pin first so the
   Python API fails closed; rebuild all pages, JSON/index/sitemap from
   the new authorized release, swap the static root and invalidate any
   previous CDN/static caches before re-enabling public delivery.

The static host cannot retroactively erase a page already cached by a browser
or a CDN. Keep public activation on HOLD until a trusted withdrawal and
cache-purge mechanism and a qualified real-case acceptance have been proven.
Neither the synthetic test fixtures nor the software PR grant GO-PUBLIC.

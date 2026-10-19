# MiniSearch donor provenance — issue #174

- Donor: Luca Ongaro, https://github.com/lucaong/minisearch
- npm: `minisearch@7.2.0`, exact dependency in `web/package.json` and lockfile.
- Upstream Git annotated tag: `v7.2.0`, tag object `aba0d53d42deba42f5e8c2d10870f7d64fa400c6`.
- Upstream commit (peeled tag): `3d239d1c3ae7aef1bf5d8945dd7b5f0709f646f5`.
- License: MIT, copyright 2022 Luca Ongaro; upstream `LICENSE.txt` preserved in `MiniSearch-MIT-7.2.0.txt`. Keep this notice with distributions containing MiniSearch.
- Adoption: npm distribution unmodified. Project-specific adapter `web/src/lib/minisearchAdapter.ts` indexes only the already projected public lexical fields and shares no data with an external service.
- Alternatives: retaining bespoke substring matching (minimal bundle, no typo tolerance); Pagefind (static-site search with additional index/build pipeline; not needed for small pinned v2/V3 JSON). No copy of donor source is maintained here.

## Offline measured tradeoff (MiniPC, Node 24.18.0)

Reproduction: `node --experimental-strip-types --expose-gc scripts/benchmark-public-search.mjs`.
Both paths use the same 250 synthetic public text/person/source records, five queries
and 15 rounds (75 operations per path). V3 includes its mandatory index hash,
verbatim quote hashes, structural validation and pin check each time.

| Path | Before p50 / p95 | MiniSearch p50 / p95 | Asset JSON / gzip (unchanged) |
| --- | --- | --- | --- |
| v2 `searchPublicIndex` | 1.778 / 2.273 ms | 1.327 / 2.221 ms | 162,163 / 6,499 bytes |
| V3 `searchPublicStatementsV3` | 21.104 / 30.830 ms | 21.760 / 28.779 ms | 201,509 / 16,078 bytes |

Minimum and maximum times depend on CPU contention and GC; this is a controlled
fixture comparison, not a claim about production traffic. With cache warmed,
250 records yield bounded sub-100-ms browser-side retrieval; rebuilding on every
query instead had measured p95 7.153 ms (v2) and 49.801 ms (V3).
Post-GC heap for this process (including the JS runtime, both fixture assets and
both search paths) increased from about 14.9 MB at the end of the baseline V3
run to about 16.2 MB after V3 MiniSearch; peak standalone browser usage was not
measured.

Measured browser-target minified bundle sizes via
`esbuild src/lib/searchIndex.ts src/lib/publicStatementSearchV3.ts --bundle --minify --format=esm --platform=browser --outdir=...`:

| Entrypoint | Before min / gzip | MiniSearch min / gzip |
| --- | ---: | ---: |
| searchIndex.js | 9,996 / 3,445 B | 28,069 / 9,260 B |
| publicStatementSearchV3.js | 10,415 / 3,661 B | 28,532 / 9,502 B |

Entrypoint sizes overlap because both bundle the shared adapter; these are
standalone comparisons, not additive shipping bytes. MiniSearch adds prefix
and bounded typo retrieval, multiword AND matching and field boosts. A search
for `settore 20` narrows from 11 old substring hits to five token matches
in this fixture (one exact number match plus four source-title matches).
Public v2 and V3 remain subject to the original validation, release pins and
revocation checks, and the experiment is **not authorized for public rollout**
while #69, #79 and #82 remain gated.

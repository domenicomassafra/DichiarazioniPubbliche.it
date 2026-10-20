# Feedparser donor provenance — issue #167

- Upstream: https://github.com/kurtmckee/feedparser
- PyPI release: `feedparser==6.0.14` (2026-07-30).
- GitHub release tag: [v6.0.14](https://github.com/kurtmckee/feedparser/tree/v6.0.14), commit `14425f6851790184fbf7bbd8076de237d5f444f9`.
- License: BSD-2-Clause (package metadata and upstream LICENSE). The dependency is separately installed and carries its own copyright/license files; no feedparser code is copied into the Apache-2.0 project.
- Transitive dependency observed with the pinned release: `feedparser-sgmllib>=2,<3` (resolved 2.1.0 in local validation, license PSF-2.0); it retains its installed license notices. The transitive version is managed by feedparser's published dependency range.

The opt-in `pip install '.[feeds]'` profile enables feedparser for synthetic RSS 1.0/2.0, Atom 1.0, iTunes and YouTube Atom metadata only. No URL is passed to feedparser: the caller supplies an already bounded XML string, and the existing HTTPS/DNS/redirect checks constrain the fetcher. An XML structural gate still rejects malformed documents, DTD declarations and unsupported roots because feedparser tolerates non-well-formed inputs. Stable identifiers, original date offset, explicit alternate links and enclosure policy remain controlled by the feed XML and the project's adapters. A missing optional dependency uses the same conservative stdlib implementation, retaining the dependency-free contributor contract.

No media, transcript or article is fetched during parsing. `DiscoveredContent` only authorizes discovery metadata; rate limits, rights holds, source registry and review/publication gates are unchanged. See `tests/test_feedparser_backend.py` for backend parity, valid/invalid fixtures, SSRF, response and item caps; the CI `feedparser-contract` job exercises the pinned optional dependency independently of the default install.

Synthetic microbenchmark (Mac Studio, Python 3.14, `tests.test_public_rss_discovery.RSS`, `timeit -n 300 -r 3`): stdlib fallback **12.4 µs/feed**, feedparser 6.0.14 plus strict structural validation **322 µs/feed** (best of three, about 26× slower). The extra deliberately remains opt-in; at the configured maximum of 20 items per source it supplies standards-aware metadata handling at a measurable cost. Validated behavior improvement over the former code: `itunes:duration` values in `HH:MM:SS` now resolve to seconds, while the strict input and URL guard rejects ambiguous/malformed entries instead of guessing.

## #182 — RSS podcast to authorized YouTube Atom (2026-10-20)

F3 reuses the already pinned optional `feedparser==6.0.14` donor (BSD-2-Clause,
Git commit `14425f6851790184fbf7bbd8076de237d5f444f9`) plus the strict
stdlib/XML adapter. No new package, copied donor source, YouTube Data API v3
quota, media or live fixture is needed. Upstream explains that permissive
`bozo` parsing does not establish structural validity:
https://feedparser.readthedocs.io/en/stable/bozo.html . Channel catalog gaps
have been observed with yt-dlp, e.g. https://github.com/yt-dlp/yt-dlp/issues/8096
(2023-09-12), so an Atom miss is **not** an exhaustive absence receipt.

The `source_associations_version=1` registry is deliberately empty until
reviewed podcast↔YouTube identity, channel, policy and source-use records exist.
An approved association selects only that YouTube Atom feed, checks the embedded
`yt:channelId`, refuses redirects, revalidates `FETCH` and `STORE_BODY` both
before/after feed access and before a video locator, and records cross-source
IDs/URLs, approval reference and SHA-256 of the catalog bytes. A missing or
unknown association never opens a network connection or dispatches ASR. A
negative episode additionally requires an exact, separately reviewed absence
receipt plus current podcast `FETCH`/`STORE_BODY`/`ASR_MEDIA` permissions before
ASR may be queued. Synthetic tests grant no real approval or publication right.

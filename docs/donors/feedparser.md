# Feedparser donor provenance — issue #167

- Upstream: https://github.com/kurtmckee/feedparser
- PyPI release: `feedparser==6.0.14` (2026-07-30).
- GitHub release tag: [v6.0.14](https://github.com/kurtmckee/feedparser/tree/v6.0.14), commit `14425f6851790184fbf7bbd8076de237d5f444f9`.
- License: BSD-2-Clause (package metadata and upstream LICENSE). The dependency is separately installed and carries its own copyright/license files; no feedparser code is copied into the Apache-2.0 project.
- Transitive dependency observed with the pinned release: `feedparser-sgmllib>=2,<3` (resolved 2.1.0 in local validation, license PSF-2.0); it retains its installed license notices. The transitive version is managed by feedparser's published dependency range.

The opt-in `pip install '.[feeds]'` profile enables feedparser for synthetic RSS 1.0/2.0, Atom 1.0, iTunes and YouTube Atom metadata only. No URL is passed to feedparser: the caller supplies an already bounded XML string, and the existing HTTPS/DNS/redirect checks constrain the fetcher. An XML structural gate still rejects malformed documents, DTD declarations and unsupported roots because feedparser tolerates non-well-formed inputs. Stable identifiers, original date offset, explicit alternate links and enclosure policy remain controlled by the feed XML and the project's adapters. A missing optional dependency uses the same conservative stdlib implementation, retaining the dependency-free contributor contract.

No media, transcript or article is fetched during parsing. `DiscoveredContent` only authorizes discovery metadata; rate limits, rights holds, source registry and review/publication gates are unchanged. See `tests/test_feedparser_backend.py` for backend parity, valid/invalid fixtures, SSRF, response and item caps; the CI `feedparser-contract` job exercises the pinned optional dependency independently of the default install.

Synthetic microbenchmark (Mac Studio, Python 3.14, `tests.test_public_rss_discovery.RSS`, `timeit -n 300 -r 3`): stdlib fallback **12.4 µs/feed**, feedparser 6.0.14 plus strict structural validation **322 µs/feed** (best of three, about 26× slower). The extra deliberately remains opt-in; at the configured maximum of 20 items per source it supplies standards-aware metadata handling at a measurable cost. Validated behavior improvement over the former code: `itunes:duration` values in `HH:MM:SS` now resolve to seconds, while the strict input and URL guard rejects ambiguous/malformed entries instead of guessing.

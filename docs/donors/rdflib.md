# RDFLib donor provenance (developer/CI only, issue #176)

- Upstream: https://github.com/RDFLib/rdflib
- Version: PyPI `rdflib==7.6.0`, released 2026-02-13.
- Exact upstream tag commit: `8b32146a0f9cb748c2068662e50d02b42fc86dfd` (`7.6.0`).
- License: BSD-3-Clause ([LICENSE](https://github.com/RDFLib/rdflib/blob/7.6.0/LICENSE)). Keep upstream's license and copyright notice with its installed distribution. No RDFLib source is vendored into this Apache-2.0 repository. Transitive dependencies retain their own notices in installed package metadata.
- [RDFLib PR #3546](https://github.com/RDFLib/rdflib/pull/3546) for opt-in deterministic N-Triples output merged on 2026-10-16, after this pinned release. The pinned serializer is not assumed to expose the new option.
- Historical reference [CIMPLE knowledge-base](https://github.com/CIMPLE-project/knowledge-base) is not installed or vendored. Its component-specific license was not verified through the root GitHub license endpoint, so no redistribution rights are inferred.

Only `pyproject.toml`'s `dev` extra and the `rdf-contract` CI job install RDFLib. `tests.test_rdflib_validation` parses independently, tests roundtrips and cross-format common semantic triples, and fails on invalid or forged RDF. Standard backend/runtime packaging and public serialization remain stdlib-only; byte hashes, ordering, provenance, visibility and revocation are preserved by untouched serializers and snapshot checks.

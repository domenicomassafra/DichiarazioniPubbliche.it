# ADR 0008 — PostgreSQL-first corpus search and similarity

- Status: Accepted
- Date: 2026-09-29

## Context

The Research Corpus needs mixed search across source metadata, passages, entities,
statement/claim candidates and collections, plus typo tolerance and duplicate/proposition
candidate generation. Donor systems often introduce Elasticsearch/OpenSearch, dedicated
vector databases or graph databases.

Dichiarazioni Pubbliche already uses PostgreSQL as operational truth and has a low-operations constraint.
PostgreSQL provides full-text search and `pg_trgm` index-supported lexical similarity.
Semantic embeddings may be useful, but their incremental value has not yet been measured
on the project's real Italian corpus.

## Decision

Use PostgreSQL as the search source of truth for the first Research Corpus implementation.

Baseline:
- relational/structured filters;
- PostgreSQL full-text search;
- `pg_trgm` lexical similarity and typo/near-duplicate candidate generation;
- stable query contracts and benchmark fixtures.

Embeddings are optional and benchmark-gated. If accepted, store vectors and their
model/version inside PostgreSQL (for example via pgvector) before considering a separate
service. Semantic similarity may nominate candidates but cannot approve identity,
proposition equivalence, evidence or publication.

Do not introduce Elasticsearch/OpenSearch, a standalone vector database, Neo4j or
Virtuoso as primary runtime infrastructure without a new measured need and superseding
ADR. CIMPLE/RDF remains an interoperability/export concern.

## Alternatives considered

### Elasticsearch/OpenSearch from day one

Rejected. It adds deployment, backup, security and consistency surface before corpus
scale/query benchmarks demonstrate a need.

### Dedicated vector database from day one

Rejected. The main early jobs also require exact filters, provenance joins, lexical
matching and transactional review state. Vector recall has not yet proven enough value to
justify a second source of operational state.

### Neo4j/Virtuoso as primary knowledge store

Rejected. Graph/RDF projections are useful for interoperability and analysis, but current
workloads need transactional workflow state, jobs, review, corrections and normal API
access that PostgreSQL already supplies.

## Consequences

Positive:
- one backup/restore/security boundary;
- deterministic lexical fallback if model/embedding services are down;
- lower MiniPC operational burden;
- simpler consistency between search result and review/promotion state.

Costs/risks:
- advanced semantic retrieval may eventually require additional indexing work;
- FTS configuration must be benchmarked for Italian text;
- large-corpus search performance must be measured rather than assumed.

## Measured follow-up — 2026-09-29

DP-116 deployed the PostgreSQL baseline to the MiniPC and measured the versioned Garlasco
search benchmark at 13/13 Recall@5 with repeated p95 about 51-57 ms. Typo retrieval uses
the GIN trigram index in the observed query plan. Embeddings/pgvector therefore remain
disabled: there is no measured retrieval gap that justifies them yet.

## Review trigger

Reopen when the versioned DP-116/DP-420 benchmark shows a material recall/latency gap that
cannot be solved acceptably inside PostgreSQL, or when corpus scale exceeds the tested
operational envelope.

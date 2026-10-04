# Dichiarazioni Pubbliche — Architecture

Status: canonical  
Last updated: 2026-09-29

## Architecture goal

Dichiarazioni Pubbliche is a provenance-first pipeline with a small number of deep modules. The
architecture optimizes for auditability, fail-closed publication, low operating cost,
replaceable external providers, and a public read path that keeps working without live
LLM calls.

## System context

```text
Public sources/platforms
        |
        v
 [bounded discovery] ---> [Discovery Run / Hit provenance]
        |
        v
 [Content registry] ---> [immutable Content Captures] ---> [Passages]
        |                         |                            |
        |                         +----> [transcript variants] |
        |                                  |                  |
        |                                  v                  |
        |                         [Canonical transcript] ------+
        |                                  |
        v                                  v
 [Research Collections]          [attribution candidates]
        |                                  |
        +-----------> [Statement Candidates]
                           |
                           v
                    [Claim Candidates]
                      /      |       \
             entity links  clusters  coverage needs
                           |
                    explicit promotion
                           |
                           v
                      [Atomic Claim]
                           |
                           v
                  [Evidence retrieval/cache]
                           |
                           v
                  [Evidence observations]
                           |
                           v
                 [Deterministic verification]
                           |
                           v
                    [Finding + review]
                           |
                    fail-closed gate
                           |
                           v
                   [Public projection]
                     /      |       \
                  HTML     JSON    JSON-LD
                           |
                reply/correction/reanalysis
```

## Runtime topology

### Development authority

The Git checkout on the Mac is the source-code authority:

`/Users/domenico/Code/DichiarazioniPubbliche.it`

### Runtime authority

The MiniPC is the backend/runtime authority. The deployment mirror is:

`/home/udodo/src/DichiarazioniPubbliche.it`

That mirror is intentionally not a Git checkout. Deployment is synchronized from the
authoritative repo. A runtime feature is not complete until its required acceptance has
been observed on the MiniPC.

### Persistence

- PostgreSQL is the canonical operational store (`dichiarazioni_pubbliche` on MiniPC).
- The private Research Corpus is stored in PostgreSQL as first-class relational records;
  immutable or rights-sensitive capture bodies may live in bounded filesystem/object
  storage referenced by hashes and retention policy.
- Filesystem/object-style storage is used for bounded cached/transient artifacts where
  appropriate.
- PostgreSQL currently also provides the processing queue.
- The public site consumes the public projection, not operational tables.

## Module map

The current `poc/dichiarazioni_pubbliche` package contains production-shaped prototypes. The
target architecture groups them by domain responsibility rather than creating one
microservice per file.

### 1. Discovery and ingestion

Responsibilities:

- source registry and source health;
- polling/discovery;
- content identity/deduplication;
- safe fetch/acquisition policy;
- enqueueing bounded downstream work.

Current implementation includes `source_watcher`, `scheduler`, `scheduler_daemon`, and
parts of `queue_runtime`/`worker_daemon`.

### 2. Research corpus and capture

Responsibilities:

- bounded Discovery Runs and Discovery Hits with query/adapter receipts;
- bounded Coverage Needs for missing primary/original/independent/temporal material;
- logical Content identity separated from immutable observed Content Captures;
- safe parsing/extraction and Passage selectors;
- Research Collections and membership provenance;
- content derivation/source-family relations and duplicate collapse;
- retention, rights and optional archive receipts.

The corpus is private by default. Capturing or indexing a source never creates a public
claim or evidence approval.

`coverage_needs` turns Source Intelligence requirement gaps into replayable private work
items with a finite attempt budget and append-only lifecycle events. Discovery manifests
may carry `coverage_need_ids`; persistence refuses terminal/exhausted needs and verifies
that claim-scoped needs belong to Content included in the target Collection. A satisfied
need remains historical and cannot be silently reopened by later re-assessment.

### 3. Transcript and attribution

Responsibilities:

- platform captions and remote ASR adapters;
- transcript variants and segment provenance;
- canonical transcript construction;
- sensitive-token disagreement handling;
- non-biometric speaker attribution and review.

Written-source attribution is a sibling provenance path: `claim_text_provenance` binds
the public person and claim to a hash/selector in the source Content with explicit
review, without manufacturing transcript segments.

Current implementation includes `caption_adapter`, `platform_transcript`, `remote_asr`,
`asr_router`, `transcript_contract`, and `speaker_runtime`.

### 4. Candidate extraction, resolution and promotion

Responsibilities:

- attributable Statement Candidate extraction from Passages/canonical segments;
- Claim Candidate atomization, check-worthiness and temporal typing;
- entity-resolution candidates for people/organizations/topics/events;
- lexical/semantic duplicate suggestions and Proposition Clusters;
- explicit, idempotent promotion from reviewed candidates to Atomic Claims;
- coverage needs for missing primary/original/independent material.

Candidate similarity, entity matching and clustering never bypass explicit provenance or
promotion policy.

### 5. Claim extraction and promoted-claim compatibility

Responsibilities:

- bounded claim windows;
- schema-constrained atomic claim extraction;
- claim/segment provenance;
- provider receipts and cost/capability gates;
- idempotent replay.

Current implementation includes `claim_windows`, `claim_runtime`, and
`claim_extraction_benchmark`. The existing direct claim-extraction path remains a
compatibility path during expand-migrate-contract. New corpus-native paths should
converge on the promotion contract instead of creating a second Atomic Claim model.
`candidate_matching` adds a deterministic-first, replayable Claim Candidate → corpus
comparison ledger. It reuses DP-115 Proposition Clusters for reviewable equivalence
proposals and DP-116 PostgreSQL lexical/trigram primitives for bounded candidate-pool
generation; it does not auto-approve a cluster, promote a claim, create a Finding or
publish anything.

### 6. Evidence

Responsibilities:

- source intelligence: evidence roles, contextual authority scopes, temporal applicability,
  independence/derivation and rights/access state without global source trust scores;
- versioned claim-type evidence requirement profiles and explicit evidence-set sufficiency/
  conflict/hold rationale;
- allowlisted source policy;
- safe fetching and content-addressed caching;
- deterministic/structured queries;
- candidate linking;
- observation extraction;
- explicit evidence review.

Current implementation includes `evidence_runtime`, `evidence_query`, `evidence_extract`
and `source_intelligence`. `config/source-intelligence.v1.json` maps configured evidence
adapters to explicit roles/authority scopes; `config/evidence-requirements.v1.json`
defines the versioned ClaimType requirement profiles. `source_profile`,
`source_evidence_role`, `source_authority_scope`, `source_relation`,
`evidence_requirement_profile`, `evidence_requirement_rule` and
`evidence_set_assessment` persist the inspectable contract. `source_relation` may cite an
DP-115 `content_derivation_candidate` rather than duplicating content-level derivation.
Existing registry fields such as `authoritative` remain adapter metadata only and are not
consulted by deterministic verification semantics.

### 7. Verification and longitudinal relations

Responsibilities:

- time-bounded reproducible verification;
- rule/version fingerprints;
- finding creation without auto-publication;
- relation candidates;
- re-analysis triggers.

Current implementation includes `verification_runtime`, `finding_runtime`,
`relation_runtime`, and `reanalysis_runtime`. A Verification Run that uses the new path is
linked to the exact `evidence_set_assessment` that admitted its evidence. Missing,
out-of-scope, temporally mismatched, rights-blocked, derivationally unresolved or
conflicting evidence fails closed before deterministic verification; the assessment keeps
structured Coverage Need candidates which `worker_daemon` materializes as DP-213
`coverage_need` records before the verification job is blocked, instead of silently
weakening the rule.

### 8. Editorial policy and public projection

Responsibilities:

- explicit review events;
- publication gates;
- right-of-reply and correction lifecycle;
- sanitized public schema;
- JSON/JSON-LD/HTML generation;
- removal of stale projection-owned artifacts.

Current implementation includes `review_admin`, `correction_runtime`, and
`public_projection`.

### 9. Search and research retrieval

Responsibilities:

- structured filters and PostgreSQL full-text search across corpus metadata/passages;
- trigram similarity for spelling/near-duplicate candidate discovery;
- benchmarked optional embeddings inside PostgreSQL only if they add measurable recall;
- one internal query contract spanning content, passages, candidates, people, topics,
  events and collections;
- deterministic lexical fallback when any semantic provider/index is unavailable.

No separate search engine, vector database or graph database is introduced without a
measured benchmark and an accepted ADR.

### 10. Operations

Responsibilities:

- queue leases/retries/blocked states;
- provider accounting and hard cost caps;
- source and worker health;
- private operational digest;
- retention and transient-media deletion.

Current implementation includes `queue_runtime`, `worker_daemon`, `health_digest`, and
`retention`.

## Architectural seams

External systems must sit behind narrow adapters. A provider name is configuration, not
domain identity. Important seams are:

- content discovery/acquisition adapter;
- capture/parser/archive adapter;
- internal search/matching adapter;
- transcript/ASR adapter;
- claim-extraction adapter;
- evidence-source adapter/query compiler;
- public-storage/hosting adapter;
- notification/operations adapter.

The domain model must remain usable if any one provider is replaced.

## Data-flow rules

1. Each stage persists enough provenance to reproduce or explain its output.
2. Replays are idempotent and must not silently widen provenance.
3. Queue payloads carry identifiers, not large raw transcript/evidence bodies.
4. External content is validated at the acquisition boundary.
5. Review state is represented by append-only review events, not inferred from mutable
   status fields alone.
6. Publication reads from an explicit allowlist/projection query and revalidates
   provenance at projection time.
7. A public record is finding-versioned so corrections never overwrite history.

## Failure strategy

Failure is a modeled state, not an excuse to degrade correctness:

- unavailable provider -> blocked/deferred job, not a fabricated fallback verdict;
- uncertain transcript/speaker -> publication hold;
- insufficient/ambiguous evidence -> unresolved/needs-more-evidence;
- stale review after underlying provenance changes -> public omission until re-reviewed;
- budget exhausted -> queued/blocked work, not a cheaper unsupported conclusion;
- broken source adapter -> source degraded while unrelated sources continue.

## Security boundaries

- outbound evidence/discovery fetches are HTTPS, allowlisted/bounded where policy
  requires it, DNS/redirect validated, and size limited;
- raw transcripts/evidence excerpts are private operational data unless a separate
  publication policy authorizes a bounded excerpt;
- administrative review is local/operator-only until a dedicated authenticated service
  is designed;
- no public database credentials or provider secrets belong in the repository;
- deletion/retention operations fail closed when manifests or durable receipts are
  incomplete.

## Infrastructure rule

The default stack stays deliberately boring: Python, PostgreSQL, files/object storage,
static-ish public output, and stateless workers. New infrastructure requires a benchmark
or operational requirement that cannot be met cleanly by the existing stack.

## Refactor policy

The project should not be rewritten merely to match this document. Existing modules are
kept when they satisfy the intended seam and invariants. Refactors must demonstrate at
least one of: stronger locality, simpler interface, fewer unsafe states, better test
surface, lower operational burden, or removal of duplicated orchestration.

See `PLAN.md` for the staged convergence path.

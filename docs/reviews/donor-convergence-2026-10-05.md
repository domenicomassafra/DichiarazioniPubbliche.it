# Donor convergence audit — 2026-10-05

Status: implementation planning + live gap audit

This audit revisits the September donor analysis after the repository gained the Research
Corpus, Source Intelligence, public projection, correction lifecycle and Trust & Evidence
ticket epic. It distinguishes capabilities that are already real runtime behavior from
donor ideas that remain missing.

## Decision

Do not add Claim Polygraph, Loki, Pender, Alegre, CIMPLE or another fact-checking product
as a second runtime. Keep one PostgreSQL-first Dichiarazioni Pubbliche core and port the
small, testable contracts that add safety or research capability.

The current upstream Claim Polygraph architecture is materially richer than the September
snapshot: it now documents specialist evidence roles, defender/challenger analysis,
deterministic judgment policy, sentence-level citation assurance, readiness control,
durable paid-operation receipts and a canonical investigation cost ledger. Those patterns
are useful; LangGraph, SQLite and its dashboard remain donor implementation choices, not
requirements for this project.

## Current convergence matrix

| Donor pattern | Current repository state | Disposition |
|---|---|---|
| Claim decomposition / check-worthiness | Implemented through bounded Statement/Claim Candidate extraction and explicit non-factual holds | KEEP |
| Query-planning boundary | Bounded assignments now compile directly into the existing DP-209 DiscoveryManifest without adapter/budget expansion; persisted execution receipt integration remains | DP-228 IN PROGRESS |
| Evidence families / independence | Implemented by DP-115 + DP-215 Source Intelligence | KEEP |
| Original-source resolution | Deterministic reviewed-root resolver now gates PRIMARY_SOURCE / ORIGINAL_MEDIA / ATTRIBUTION_GAP Coverage Need satisfaction; DB/MiniPC canary + Studio surfacing remain | DP-225 IN PROGRESS |
| Deterministic judgment/publication policy | Implemented in multiple fail-closed seams; DP-308 will unify the final safety profile | KEEP / DP-308 |
| Citation assurance | Finding rationale assertions/citations are persisted, replay-backfillable, backup/restore load-bearing and enforced fail-closed by public projection; exact Passage binding remains for unstructured evidence | DP-224 IN PROGRESS |
| Numerical verification | Exact/range/historical verification exists; compound delta/ratio/percent-change was missing | DP-226; runtime started 2026-10-05 |
| Temporal verification | Source Intelligence now consumes persisted evidence valid_from/valid_until/status and blocks not-yet-effective, expired or unsafe superseded versions before verification | DP-227 IN PROGRESS |
| Defender/challenger | Pure counter-case packet now separates contradict/limitation/context/update evidence without creating a verdict; execution/persistence remain | DP-229 IN PROGRESS |
| Paid-operation receipts/idempotency | Implemented for discovery/extraction/provider work, but cost/usage aggregation is fragmented | DP-230 |
| Canonical investigation cost ledger | Pure stable operation identity + measured/estimated/external-plan/unknown aggregation exists; persistence adapters remain | DP-230 IN PROGRESS |
| Pender capture/archive state machine | Implemented in DP-210 without Rails/Redis dependency | KEEP |
| Pender metadata/oEmbed/provider parsing | Capture parser now stores bounded canonical/OG/Twitter/oEmbed/JSON-LD metadata candidates; network/provider/conflict policy remains | DP-231 IN PROGRESS |
| Pender concrete archive callbacks | Protocol/state machine exists; source-specific real adapters remain intentionally absent | DP-231, rights/policy gated |
| Alegre similarity service | PostgreSQL lexical/trigram path exists; no reason yet to add Elasticsearch/Kibana/Redis | KEEP; embeddings only if DP-116 benchmark justifies |
| ClaimReview JSON-LD | Implemented in public projection | KEEP |
| CIMPLE URI/RDF projection | Stable HTTPS identities + deterministic N-Triples export now exist over the validated public bundle; static artifact wiring remains | DP-433 IN PROGRESS |
| Google/existing fact-check lookup | Bounded Google Fact Check Tools normalizer/client exists with secret-safe receipt; DP-228 persistence/execution remains | DP-232 IN PROGRESS |
| Open Parliament speech/video alignment | Pure official-intervention/media alignment now exists; Camera/Senato ingestion/persistence remains | DP-233 IN PROGRESS |
| DVNS structured evidence intermediary | Provider-neutral zero/missing/date/schema-drift contract now exists; real external adapter remains blocked on approved contract | DP-234 IN PROGRESS |
| Community Notes transparent status/reason history | Append-only reviews/reason codes already align; consensus ranking is intentionally not adopted as truth authority | KEEP |

## Why the missing pieces matter

### Citation assurance is different from evidence membership

The public projection now requires a versioned material rationale assertion whose exact
text hash matches the Finding and whose SUPPORT citation points to approved Evidence and
an approved Observation in the same verification run. This closes the structured-evidence
path. DP-224 still has one deliberate gap: assertions grounded in unstructured material
must additionally bind to exact Passage/source hashes rather than only an Observation.

### Original-source resolution is different from independence grouping

DP-115 can say that ten articles share one derivation family. DP-225 now walks approved
derivation edges back to an original/root Content and the Coverage Need runtime refuses a
derived copy as satisfaction for PRIMARY_SOURCE / ORIGINAL_MEDIA / ATTRIBUTION_GAP. Missing
or conflicting reviewed roots fail closed.

### Research planning should compile from evidence requirements

Coverage Needs say what is missing. DP-228 now compiles them into bounded provider-neutral
assignments and then into the existing DP-209 DiscoveryManifest. Adapter lists, source
families, result limits and cost caps can only stay equal or narrow during that conversion;
a BLOCKED lane never falls back to generic web search. This ports the useful specialist-role
architecture without importing a multi-agent framework or a second scheduler.

### Challenger is a role, not a vote

DP-229 will require a bounded counter-case for consequential Findings. The challenger may
surface counterevidence, scope limitations, alternative explanations or unresolved gaps;
it cannot vote a verdict into existence. The authoritative decision remains deterministic
verification plus publication policy.

### Cost must be reconstructable, not merely capped

The project already blocks over-budget calls. DP-230 additionally makes cost/usage
reconstructable across retries and providers, separates measured cost from estimates and
unknown/unallocated external-plan usage, and never displays unknown as zero.

## Explicitly not imported

- LangGraph as orchestration authority;
- SQLite/WAL persistence;
- donor dashboards;
- source-quality or truth probability scores;
- Community Notes consensus scoring as factual authority;
- Alegre Elasticsearch/Kibana/Redis stack;
- Pender Rails/Sidekiq/Redis service;
- CIMPLE Virtuoso as primary database.

These would increase operational surface or conflict with the existing domain authority
without solving a demonstrated gap.

## Implementation order

1. DP-224 citation assurance.
2. DP-225 original-source resolver.
3. DP-226 compound numerical verification.
4. DP-227 effective-time/supersession verification.
5. DP-228 claim-specific research-plan compiler.
6. DP-229 challenger/counter-case packet.
7. DP-230 canonical paid-operation/cost ledger.
8. DP-231 metadata/archive adapter enrichment.
9. DP-232 existing fact-check lookup.
10. DP-233 parliamentary source alignment.
11. DP-234 DVNS structured adapter when an approved external contract exists.
12. DP-433 linked-data/RDF projection after public resources stabilize.

DP-223 and DP-308 remain the release-facing adversarial/publication gates that consume the
results of this donor convergence work.

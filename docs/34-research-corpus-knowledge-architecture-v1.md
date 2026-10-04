# Dichiarazioni Pubbliche — Research Corpus & Knowledge Architecture v1

Date: 2026-09-29
Status: current implementation guidance; PRODUCT.md, CONTEXT.md, ARCHITECTURE.md and accepted ADRs remain authoritative

## Executive decision

Dichiarazioni Pubbliche must stop treating `AtomicClaim` as the first durable unit worth keeping.
The project needs a private, provenance-first **Research Corpus** that can retain large
amounts of useful public material even when that material never becomes a fact-check.

The target operating model is:

```text
discover broadly but boundedly
  -> resolve logical content identity
  -> capture immutable observed versions
  -> extract/index passages or canonical media segments
  -> resolve people/topics/events as candidates
  -> extract attributable statement candidates
  -> atomize claim candidates
  -> deduplicate and cluster propositions
  -> expose coverage gaps
  -> explicitly promote selected candidates to Atomic Claim
  -> retrieve/approve evidence
  -> verify
  -> review
  -> project a small public record
```

This is not a replacement for the existing verification architecture. It is the missing
layer in front of it.

## Why the current product feels weak

The current codebase is already strong at the dangerous end of the pipeline: provenance,
Atomic Claims, evidence observations, deterministic verification, append-only Findings,
review, corrections and fail-closed publication. The weakness is earlier.

A research task such as "understand every material public statement around Garlasco" is
not naturally represented by thirty isolated Atomic Claims. Real research contains:

- pages found but not yet read;
- multiple URLs for the same item;
- different captured versions of a page;
- passages that matter but are not independently checkable claims;
- direct quotations and paraphrases;
- a source quoting another source;
- people, institutions, topics and events mentioned in context;
- candidate statements whose speaker attribution still needs review;
- several wordings of substantially the same proposition;
- claims that have already been checked;
- claims not worth checking;
- primary documents still missing;
- copied/syndicated stories that are not independent corroboration;
- unresolved chronology;
- source-rights and retention constraints.

If only the final claim survives, the system loses the research memory needed to search,
compare, revisit, deduplicate and explain how it reached the verification queue.

## Research principles

### 1. Capture first; promote later

Capture and indexing are cheap/private operations. Promotion into the fact-check domain is
intentional. A candidate never becomes public because it exists or because a model is
confident.

### 2. Promote, do not mutate

`StatementCandidate` and `ClaimCandidate` remain durable after promotion. Promotion
creates a provenance edge to an existing or newly created `AtomicClaim`; it does not
rewrite the candidate into a different object.

### 3. Logical identity is separate from observed bytes

`Content` represents a logical public item. `ContentCapture` represents what Dichiarazioni Pubbliche
observed at a specific time. The same article may have several captures with distinct
hashes. This is required for edits, disappearing pages, source preservation and
reproducibility.

### 4. Search and matching are navigation aids

Full-text search, trigrams, embeddings, model similarity, entity matching and proposition
clustering can rank candidates. They do not approve identity, proposition equivalence,
evidence, or publication.

### 5. Source repetition is not source independence

A dozen articles derived from the same agency copy or press release must not become a
dozens-worth evidence signal. Derivation/source-family relations are first-class research
metadata.

### 6. Public remains a projection

The corpus can be large, messy and private. Public remains small, reviewed and bounded.
The research architecture must never become a justification for exposing raw transcripts,
copyrighted source bodies, provider outputs, private notes or unreviewed allegations.

## What the external landscape says

This architecture deliberately composes lessons instead of cloning one product.

### Full Fact AI — monitoring before verification

Full Fact publicly describes a flow that collects news, live-TV speech, podcasts and
social material, converts it to text, splits it into sentence-level units, classifies
claim types, filters by topic and then matches claims against previous fact checks.
The architectural lesson is that **classification and matching reduce the research
surface before expensive verification**.

Source: https://fullfact.org/ai/

### Factiverse Gather — source moment, claim and evidence in one workspace

Gather uses a source-centric workflow: transcribe video/audio, surface claims, connect
supporting/contradicting/context sources, jump from a claim to the exact source moment,
and search transcript and claims together. This validates a dense private workspace, but
Dichiarazioni Pubbliche keeps stronger review/publication separation and durable corpus provenance.

Sources:
- https://www.factiverse.ai/solutions/gather
- https://www.factiverse.ai/solutions/video-audio

### OCCRP Aleph — investigations as workspaces over a corpus

Aleph treats an investigation as a workspace containing documents/entities and supports
cross-referencing, timelines and relationship exploration across large datasets. Agli
Atti should borrow the **bounded research collection** mental model without adopting
Aleph wholesale or turning every relation into a public graph.

Sources:
- https://docs.aleph.occrp.org/
- https://docs.aleph.occrp.org/users/getting-started/key-terms/

### DocumentCloud — primary-document corpus and annotation

DocumentCloud demonstrates that newsroom research benefits from durable primary-source
documents that can be organized, searched, annotated and operated on in bulk. The useful
lesson is not its product shell; it is that the document itself remains a first-class
research object rather than disappearing after extraction.

Source: https://www.documentcloud.org/

### OpenSanctions/yente — matching is not search and matching is explainable

OpenSanctions distinguishes ordinary full-text search from query-by-example entity
matching. Its matching documentation describes supporting and contradicting features.
Dichiarazioni Pubbliche should therefore persist entity-resolution candidates and their features rather
than silently merging people/entities from a fuzzy score.

Sources:
- https://www.opensanctions.org/docs/api/matching/
- https://www.opensanctions.org/matcher/

### Pender — parsing and preservation as adapters

Meedan Pender separates generic/provider-specific link parsing from optional archiving and
uses asynchronous archive callbacks. Dichiarazioni Pubbliche should adapt these boundaries, not import
the Rails service: parser and archiver are replaceable adapters and an archive request
has a state/receipt rather than pretending preservation is instantaneous.

Source: https://github.com/meedan/pender

### CIMPLE — interoperable graph projection, not primary operational storage

CIMPLE demonstrates stable URI design, ClaimReview conversion and an RDF knowledge graph
at large scale. Dichiarazioni Pubbliche should preserve RDF/ClaimReview interoperability as an export
surface while PostgreSQL remains the operational source of truth.

Source: https://github.com/CIMPLE-project/knowledge-base

### Existing donor conclusions that remain valid

The earlier source-level audits remain correct:

- Loki/OpenFactVerification: adapt the decomposition/check-worthiness/query boundaries;
- Claim Polygraph NG: strongest design donor for citation assurance, evidence families,
  independence, temporal/numerical verification, deterministic judgment and cost receipts;
- Pender: parser/archiver boundaries only;
- Alegre: similarity concept, not the heavy runtime;
- CIMPLE: URI/RDF/ClaimReview interoperability, not Virtuoso as primary DB;
- Meedan Check: collaborative annotation/workflow reference, not application foundation;
- AVeriTeC/FEVER-style systems: benchmark/retrieval references, not publication authority;
- Pagella Politica/Facta/Newtral/Full Fact/Africa Check: methodology and public UX lessons;
- Google Fact Check Explorer: compact retrieval lesson, not the product's core information
  architecture.

## Full donor disposition registry

This pass rechecked the complete named donor/reference inventory in
`docs/01-research-ecosystem.md`, `docs/08-deep-landscape-audit.md`,
`docs/10-adoption-matrix.md`, `docs/12-source-level-donor-audit.md`,
`docs/14-donor-extraction-map.md` and the UX competitors in
`docs/30-competitive-ux-research-v1.md`.

The status below is the **current Dichiarazioni Pubbliche implementation disposition**, not a quality
ranking of the upstream projects.

| Donor / reference | Current disposition | Concrete Dichiarazioni Pubbliche use |
|---|---|---|
| Loki / OpenFactVerification | ADAPT / POC | Decompose, check-worthiness, bounded query-generation and retriever boundaries; never its final factuality score as publication authority. |
| Claim Polygraph NG | PRIMARY DESIGN DONOR / ADAPT | Citation assurance, evidence families/independence, original-source resolution, near-duplicate patterns, temporal/numerical verification, deterministic judgment, provider idempotency and cost receipts. |
| Meedan Check | REFERENCE | Collaborative annotation/workflow concepts; do not adopt the full service topology. |
| Meedan Pender | ADAPT PATTERNS | URL normalization, provider parser boundary, archiver adapter/state/callback; do not deploy Rails service by default. |
| Meedan Alegre | REFERENCE ONLY | Similarity/dedup concepts; no Elasticsearch/Kibana/Redis stack in v1. |
| CIMPLE Knowledge Graph | INTEROPERABILITY REFERENCE | URI design, RDF/ClaimReview projection, dataset-release patterns; no Virtuoso primary store. |
| X/Twitter Community Notes | REFERENCE | Auditability/open data/reproducibility lessons; community consensus is not truth authority. |
| InTruth | REFERENCE ONLY | Real-time/BYOK/UX lessons; licensing prevents core dependency. |
| Open Parliament TV | REFERENCE | Parliamentary media normalization/timestamp architecture; re-check code licenses before reuse. |
| Check-IT! | BENCHMARK | Italian political fact-check dataset/evaluation reference; respect access/license terms. |
| DisinfoMM | RESEARCH REFERENCE | Multimodal misinformation research patterns only where the product later handles manipulated media. |
| Pagella Politica | METHODOLOGY + UX REFERENCE | Italian-language fact-check framing, original statement/source/date visibility, method/corrections; explicitly reject person reliability scorecards. |
| Ledsav/fact-checker | REFERENCE | Lightweight implementation ideas only; no foundation role. |
| Openpolis / Openparlamento | DOMAIN/DATA REFERENCE | Italian public-record entities, roles and parliamentary context; no legacy stack adoption. |
| Schema.org Claim / ClaimReview | ADOPT AS EXPORT | Public interoperability from sanitized finding projection, not the operational domain model. |
| AVeriTeC | BENCHMARK | Real-world claim/evidence retrieval, QA evidence and end-to-end evaluation; license limits direct code/data reuse. |
| AIC CTU AVeriTeC | BENCHMARK / REFERENCE | Retrieval/reranking implementation comparison against our benchmark only. |
| HerO | RESEARCH REFERENCE | Claim/evidence reasoning ideas; no runtime adoption without a concrete delta. |
| FEVER | BENCHMARK | Support/refute/not-enough-information evaluation pattern. |
| FEVER-it | BENCHMARK | Italian regression/evaluation material. |
| GEAR | RESEARCH REFERENCE | Graph evidence reasoning concepts; no graph DB implication. |
| FactCheck-AI / FactCheck | BENCHMARK | Structured-fact/RAG/consensus evaluation reference; no consensus-as-publication rule. |
| ClaimBuster Spotter | REFERENCE | Check-worthiness/live-debate task precedent; avoid score-centric public UX. |
| DeReC | REFERENCE | Cheap staged retrieval/classifier cascade patterns. |
| IMRRF | REFERENCE | Retrieval diversity/redundancy ideas for evidence discovery. |
| TrustworthyRAG | SECURITY REFERENCE | Retrieval poisoning/NLI/trust-boundary patterns; RAG output remains untrusted. |
| OpenErrata | UX/ARCH REFERENCE | Provenance/fail-closed exploration; AGPL boundary prevents casual code copying. |
| DoppelCheck | DONOR / REFERENCE | BYOK/direct-provider interaction ideas where licensing permits; not needed for public runtime. |
| FactScope | UX REFERENCE | Mixed/uncertain/open-state presentation. |
| FYI | UX REFERENCE | Quantitative/dataset exploration patterns for evidence inspection. |
| Full Fact AI | PRIMARY WORKFLOW REFERENCE | Monitoring -> atomic units -> claim classification -> topic filtering -> prior-claim matching. |
| Factiverse Gather/Live | PRIMARY STUDIO REFERENCE | Source moment -> transcript -> claim -> evidence workspace, source filters, jump-to-moment, monitoring. |
| Media Cloud | CORPUS/SEARCH REFERENCE | Large news corpus/search patterns; do not inherit AGPL backend stack into core. |
| Miniflux | OPTIONAL INTEGRATION | Mature feed polling if it reduces custom code; existing source watcher may already cover v1 needs. |
| RSSHub | OPTIONAL BOUNDARY SERVICE | Connector coverage only if terms/license/operations justify it; no core code donor. |
| Huginn | REFERENCE | Automation concepts; currently overkill relative to existing scheduler/queue. |
| changedetection.io | HOLD / REFERENCE | Change-detection concept; require current license/fit audit before any dependency. |
| Trafilatura | PREFERRED PARSER CANDIDATE | Main-article extraction/metadata/feed support behind our parser adapter; benchmark on Italian corpus before locking. |
| Newspaper4k | PARSER FALLBACK CANDIDATE | Secondary parser when it materially improves extraction coverage. |
| Playwright | BOUNDED FALLBACK | Dynamic rendering only after normal fetch/parser fails and source policy permits it. |
| ArchiveBox | OPTIONAL PRESERVATION ADAPTER | Evaluate operationally for capture preservation; not required for every source. |
| Perma.cc | OPTIONAL DURABLE-CITATION ADAPTER | Async preservation receipt for selected material, never assumed instantaneous. |
| Monolith | LIGHTWEIGHT PRESERVATION CANDIDATE | Static snapshot fallback where rights/policy allow. |
| youtube-transcript-api | ACQUISITION CANDIDATE | Cheap transcript attempt with explicit unofficial-endpoint failure mode. |
| yt-dlp | MEDIA ACQUISITION TOOL | Bounded media metadata/extraction where terms/policy permit; not a domain dependency. |
| faster-whisper | ASR FALLBACK | Existing self-hosted transcription option, cost/quality benchmark controlled. |
| pyannote.audio | DIARIZATION BENCHMARK | Only if DP-208 proves needed; diarization never becomes biometric identity. |
| diarize | DIARIZATION BENCHMARK | CPU/alternative comparison under DP-208, not default. |
| Sentence Transformers | BENCHMARK-GATED | Embedding/reranking candidate only after DP-116 proves incremental value; store model/version and keep lexical fallback. |
| Google Fact Check Tools / Explorer | LOOKUP INTEGRATION + UX REFERENCE | Existing-check lookup and compact claim retrieval; external fact-check rating is evidence/context, not our automatic verdict. |
| IFCN Code of Principles | METHODOLOGY REFERENCE | Transparency, sourcing, corrections and nonpartisanship process guidance. |
| OCCRP Aleph | PRIMARY CORPUS WORKSPACE REFERENCE | Research Collections, documents/entities, cross-reference and timelines; do not import the whole investigative stack. |
| DocumentCloud | PRIMARY DOCUMENT-CORPUS REFERENCE | Durable primary documents, organization, annotation/search and bulk operations. |
| OpenSanctions/yente | PRIMARY ENTITY-MATCHING REFERENCE | Query-by-example candidate matching with supporting/contradicting features; adapt the explainable-candidate pattern, not sanctions semantics. |

### UX competitor disposition

These are visual/information-architecture references, not code dependencies:

| Product | Adopt | Reject / constrain |
|---|---|---|
| Pagella Politica | original claim/source/date, explicit method/corrections | person truth/reliability scorecard or party-color ranking |
| Facta | contemporary editorial art direction | magazine hierarchy hiding structured claim/evidence relationships |
| Newtral | claim above fold, facets, compact status/source anatomy | verdict-color domination and excessive taxonomy |
| Full Fact Public | calm evidence-led reading, quick/full depth | generic institutional mimicry |
| Factiverse | dense private source/claim/evidence workspace | treating live model output as publication |
| PolitiFact | unmistakable checked statement, longitudinal archives | meters, theatrical verdicts, aggregate person interpretation |
| Snopes | approachable consumer verification, visual media handling | generic high-density media homepage |
| AFP Fact Check | visual-first manipulated-media evidence | binary stamp as whole identity |
| Maldita.es | filterable archive, context/alert states, user intake precedent | giant initial filter wall |
| Africa Check | exact wording, replicability and visible method | none of its methodology is a substitute for our provenance gates |
| Google Fact Check Explorer | brutally simple search/result density | aggregation-only data model |
| ClaimBuster | staged live analysis and visible pipeline | research-dashboard clutter and public check-worthiness scores |

### Adoption rule

A status in this table does not authorize code copying. Every code-level reuse still needs
artifact-level source URL/repository, exact file/version/commit, license/notice review,
local destination, local tests and a donor semantic-delta record. Donor behavior that
conflicts with PRODUCT.md or accepted ADRs is rejected even when the upstream license is
permissive.

## Target data model

The following names are canonical domain targets. Exact SQL lives in DP-113 and related
tickets.

### Discovery

`discovery_run`
- stable id;
- collection/seed scope;
- adapter/provider and version;
- query manifest hash;
- started/completed timestamps;
- budget/cap state;
- status and receipt metadata.

`discovery_hit`
- run id;
- raw locator/url/external id;
- rank/provider metadata;
- normalized locator hash;
- resolved `content_id` when known;
- disposition (`NEW`, `EXISTING`, `REJECTED`, `UNRESOLVED`);
- discovery provenance.

### Corpus

`content_item` remains logical identity.

`content_capture`
- immutable capture id;
- content id;
- observed/fetched time;
- canonical/final URL;
- media/MIME type;
- body/object reference and SHA-256;
- extraction/parser method + version;
- HTTP/source metadata necessary for replay;
- rights/retention class;
- archive state/receipt when used;
- status (`CAPTURED`, `FAILED`, `QUARANTINED`, `PURGED_BODY`).

`passage`
- capture id or canonical media-segment reference;
- selector type;
- character/page/time bounds;
- immutable text hash;
- bounded private text where policy permits;
- language;
- extraction/version;
- searchable text vector generated deterministically;
- metadata.

Do not duplicate canonical transcript text merely to fit written-document abstractions.
Media passages may reference existing canonical transcript segments.

### Research organization

`research_collection`
- stable id/slug;
- name and bounded scope statement;
- status (`ACTIVE`, `PAUSED`, `ARCHIVED`);
- created/updated timestamps;
- policy/config version;
- private by construction.

`research_collection_item`
- collection id;
- typed member id/content id;
- inclusion method/version;
- status/review state;
- rationale/provenance.

`topic`
- stable curated id;
- name/aliases;
- scope definition;
- status/version.

`event`
- stable id;
- label;
- temporal interval;
- location only when public-interest relevant;
- scope/provenance.

`entity_resolution_candidate`
- source mention/passage;
- target entity type/id;
- method/version;
- supporting and contradicting features;
- optional score as retrieval metadata only;
- review status.

### Candidate layer

`statement_candidate`
- source passage(s)/media segment(s);
- attributed person candidate;
- statement date/time;
- normalized bounded statement representation;
- source quote/text hash, never a license to expose full text;
- extraction method/model/version;
- status and review provenance.

`claim_candidate`
- statement candidate id;
- normalized atomic proposition;
- proposed claim type/version;
- temporal scope;
- check-worthiness;
- extraction version;
- status (`CANDIDATE`, `DUPLICATE`, `PROMOTED`, `REJECTED`, `HELD`);
- promotion target id when approved.

`proposition_cluster`
- stable cluster id;
- canonical private label/representative;
- cluster method/version;
- reviewed state.

`proposition_cluster_member`
- candidate/claim member;
- similarity features;
- membership status/review event.

### Source derivation / independence

`content_derivation_candidate`
- source and target content/capture;
- relation (`REPUBLICATION`, `SYNDICATION`, `QUOTATION`, `PRESS_RELEASE_DERIVED`,
  `UNKNOWN_DERIVATION`);
- method/version/features;
- review state.

The existing `evidence.independence_group` remains evidence-layer state. Approved corpus
derivation relations can inform it, but corpus metadata must not silently rewrite an
approved evidence ledger.

### Coverage

`coverage_need`
- collection and optional claim/candidate scope;
- need type (`PRIMARY_SOURCE`, `ORIGINAL_MEDIA`, `OFFICIAL_RECORD`, `EARLIER_VERSION`,
  `INDEPENDENT_SOURCE`, `TEMPORAL_GAP`, `ATTRIBUTION_GAP`, `OTHER`);
- human-readable question;
- priority as operational triage, never political value;
- state (`OPEN`, `SEARCHING`, `SATISFIED`, `BLOCKED`, `WAIVED`);
- satisfied-by links and review trail.

## Promotion contract

Promotion is the safety seam between research and verification.

A `ClaimCandidate` can be promoted only when:

1. its source Content identity is stable;
2. the exact capture/segment provenance exists;
3. attribution is sufficient for the selected path;
4. atomization is valid under the Atomic Claim contract;
5. the candidate is not merely a rhetorical/value statement unless the Atomic Claim
   taxonomy explicitly permits a non-check-worthy record;
6. duplicate search has run against existing claims/candidates;
7. promotion either links to an existing Atomic Claim or creates exactly one new Atomic
   Claim under an idempotency key;
8. no Finding, evidence approval or publication side effect occurs as part of promotion.

The old curated written intake and direct media claim pipeline become compatibility
adapters that can gradually emit/promote candidates through this contract.

## Search architecture

### Baseline: PostgreSQL, not a new search stack

Use one operational database until measured evidence says otherwise.

Phase 1:
- PostgreSQL full-text search (`tsvector`) over title/description/passage/candidate fields;
- normalized exact keys for canonical IDs and locators;
- `pg_trgm` for spelling tolerance and near-duplicate lexical candidates;
- B-tree/GIN/GiST indexes chosen from measured query shapes;
- structured filters for entity/date/source/type/state/collection.

Phase 2, benchmark-gated:
- optional embeddings stored with model/version;
- use pgvector only inside the existing PostgreSQL boundary;
- hybrid retrieval = structured filters + lexical + optional vector recall + reranking;
- embeddings may nominate a cluster/entity relation but never approve it.

Do not add Elasticsearch/OpenSearch, a separate vector DB, Neo4j or Virtuoso to the
runtime merely because a donor uses it.

### Internal query contract

A single internal search request should support:

- free text;
- result kinds: content, passage, statement, claim candidate, atomic claim, person,
  organization, topic, event, collection;
- person/entity filters;
- topic/event filters;
- date/reference-period filters;
- source/source-type/content-type filters;
- candidate/review/check-worthiness states;
- claim type;
- provenance/capture state;
- collection scope;
- sort by relevance/date with stable tie-breakers.

Every hit must retain a jump target to its source/capture/passage context.

### Benchmark before semantic infrastructure

Create a versioned corpus-search benchmark of real operator questions such as:

- `Garlasco DNA unghie Sempio`;
- all Bruzzone statements on footprint 33;
- all Lucarelli statements in a date interval about the Poggi computer;
- source versions that changed after initial capture;
- candidate claims equivalent to an already verified proposition;
- direct/official sources behind a media paraphrase.

Measure Recall@K, duplicate-candidate precision on a reviewed sample, query latency and
operator time-to-source. Add embeddings only when lexical/structured retrieval misses a
material benchmark set and the vector path measurably improves it.

## Discovery architecture

### Bounded, query-manifest driven

A Discovery Run must have a bounded manifest, for example:

```json
{
  "collection_id": "research:garlasco",
  "seeds": ["person:...", "topic:..."],
  "queries": ["..."],
  "source_families": ["official", "news", "video", "podcast"],
  "date_range": {"from": "...", "to": "..."},
  "result_limit": 100,
  "per_host_limit": 20,
  "cost_cap": "...",
  "discovery_version": "..."
}
```

The manifest, not an LLM's unrecorded browsing behavior, defines the replayable search.
Models may propose queries; accepted query text/version must be persisted before use.

### Discovery cascade

Prefer cheaper/deterministic sources first:

1. configured source feeds/APIs/sitemaps where permitted;
2. existing corpus and known locators;
3. structured search/fact-check indexes;
4. web search adapters;
5. browser-rendered extraction only for pages that require it.

All URLs pass existing safe-fetch/SSRF policy before capture.

### Capture cascade

1. normalize locator;
2. resolve or create logical Content;
3. fetch bounded response;
4. persist metadata/hash and immutable Capture receipt;
5. parse main body/metadata;
6. optionally request preservation through an archiver adapter;
7. create Passages;
8. enqueue candidate extraction only when policy/cost gates allow it.

Archive failure must not forge a successful archive receipt and need not destroy a valid
local capture if policy allows retaining it.

## Candidate extraction architecture

Use a cascade rather than one expensive prompt:

1. deterministic segmentation;
2. lightweight entity/alias lookup;
3. cheap heuristics/classifier for statement/check-worthiness candidates;
4. schema-constrained model extraction only over bounded passages/windows;
5. exact/lexical duplicate lookup;
6. optional semantic similarity/reranking when benchmarked;
7. persist candidates and blockers;
8. operator or policy-driven promotion.

The candidate extractor outputs *proposals*, not truth labels.

## Entity resolution

Do not create a new person because a model emitted a name string and do not merge people
because names are similar.

Resolution flow:

```text
mention
  -> exact stable identifiers / known aliases
  -> structured candidate search
  -> feature comparison
       support: exact alias, role, organization, date/context
       contradict: incompatible role/date/context, explicit different identity
  -> candidate set
  -> deterministic high-certainty auto-link only for pre-approved identifier rules
     OR review state
  -> canonical entity relation
```

All model/fuzzy decisions remain inspectable.

## Proposition matching and clustering

Three different questions must stay distinct:

1. Is this text a duplicate extraction from the same statement?
2. Does this candidate express substantially the same proposition as another claim?
3. Is there a longitudinal relation such as contradiction or position change?

Use separate records/rules. A same-proposition cluster does not imply support/refutation;
a contradiction candidate does not imply deception.

Suggested candidate-generation cascade:

- exact normalized proposition/hash;
- same source + overlapping selectors;
- `pg_trgm` lexical similarity;
- shared entities/topic/time scope;
- optional embedding similarity;
- reranking/classification into `SAME_PROPOSITION`, `RELATED`, `DIFFERENT`, `UNCERTAIN`;
- explicit review before a durable approved relation is exposed outside research.

## Dichiarazioni Pubbliche Studio IA v3

Do not build a giant enterprise dashboard. Studio should have a small number of
research tasks and one dominant task per screen.

Primary navigation:

```text
Studio        Cerca corpus        Inbox        Raccolte        Verifica
```

`Revisioni`/publication actions remain contextual to Verify/record review rather than a
permanent sidebar unless usage proves otherwise.

### 1. Corpus search

Job: find something that already exists before collecting or rechecking it.

Desktop anatomy:

```text
query + structured filters
---------------------------------------------------------
compact mixed result list       selected-result inspector
content / passage / statement   source/capture/provenance
claim / person / event          jump-to-passage / relations
```

Mobile is secondary for Studio; it may collapse to result list -> detail navigation.

### 2. Discovery Inbox

Job: decide what to do with newly found material.

Queues are persisted states, not decorative KPIs:

- new content;
- likely duplicate/existing content;
- changed capture/version;
- unresolved entity attribution;
- statement candidates;
- likely already-covered claims;
- open coverage needs;
- blocked/quarantined captures.

The row action is contextual: inspect, merge/link, reject, add to collection, extract,
promote, or open a coverage need.

### 3. Research Collection

Job: understand one bounded case/topic/event.

Wide-screen structure:

```text
collection rail       source/passages/timeline        inspector
filters + corpus      selected document/moment        entities
coverage gaps         candidate highlights            statements/claims
saved views           chronology                      provenance/actions
```

The Collection page must support switching between list/chronology/source-oriented views
without turning the screen into a graph visualization by default.

### 4. Verify

Retain the strongest prior three-pane concept:

```text
source/media/transcript | promoted Atomic Claim | evidence/observations/review
```

Only promoted claims enter this surface. Existing verification/publication gates remain
unchanged.

## Public IA implications

Do not redesign Public from zero yet. The five-template public architecture remains a good
baseline:

- Home;
- Explore;
- Fact-check;
- Record (Person/Topic);
- ContentAudit.

The corpus changes two later decisions:

1. `Explore` can eventually be backed by much richer curated public metadata without
   leaking private corpus material.
2. A public **Case/Collection** surface may become useful, but it must get its own contract
   and must not overload the existing `Published Dossier` term. DP-421 is the decision
   gate after the Garlasco corpus proves what readers actually need.

No more broad visual-system polishing should outrun the Research Studio tracer bullet.
The current visual research is preserved; implementation resumes against real corpus data.

## Garlasco tracer bullet

Garlasco is the first acceptance collection because it already contains real Bruzzone and
Lucarelli claim/provenance data and exposes exactly the problems the corpus must solve.

### Initial bounded corpus target

The first acceptance target is **100 real Content items**, not because 100 is a launch
quota but because it is large enough to expose duplication, source derivation, changed
pages, mixed media, entity ambiguity and search problems while remaining inspectable.

The set should deliberately include:

- direct interviews/articles by or with the two subjects;
- video/podcast material with timestamps where obtainable;
- official/judicial/procedural documents that can legally and technically be captured;
- secondary news reporting;
- duplicate/syndicated/quoted reporting;
- sources that materially changed or disappeared when such examples exist.

### Pilot acceptance

The pilot passes only when:

- all 100 logical items have source/discovery provenance;
- every successfully fetched item has an immutable capture/hash receipt;
- written sources have passage selectors; media uses canonical segment/time provenance;
- duplicate logical content and derivation candidates are surfaced rather than silently
  multiplied;
- entity-resolution candidates are inspectable;
- statement/claim candidates retain exact source linkage;
- the 30 existing Garlasco Atomic Claims can be found/linked without duplication;
- at least a reviewed sample of new candidate clusters has measured precision;
- benchmark search questions achieve the ticketed recall threshold;
- open primary/official-source gaps appear as Coverage Needs;
- replay is idempotent;
- zero new public Findings are created merely by corpus ingestion;
- corpus bodies remain private and public projection leak tests remain green.

After this tracer bullet, scale by coverage/throughput metrics rather than an arbitrary
"thousands of claims" target.

## Metrics that matter

Corpus health:
- capture success/failure by source family;
- immutable capture provenance completeness;
- duplicate logical-content collapse rate;
- changed-version detection rate;
- derivation/source-family review coverage;
- candidate extraction yield and hold/reject reasons;
- entity-resolution reviewed precision;
- proposition-cluster reviewed precision;
- search Recall@K on versioned benchmark;
- median operator time from question to source passage;
- open/satisfied Coverage Needs;
- cost per discovered/captured/processed item;
- replay/idempotency failures.

Verification/public metrics remain claim-level. Never aggregate these into a person-level
truth/reliability ranking.

## Security, rights and abuse boundaries

The Research Corpus increases retained private material, so implementation must explicitly
cover:

- SSRF/DNS/redirect protections inherited from acquisition;
- hostile HTML/PDF/source content treated as untrusted data, not instructions;
- bounded responses and parser resource limits;
- source-specific terms and access policy;
- copyright/excerpt policy and body-retention class;
- purge of body bytes without destroying required audit metadata/hash when policy says so;
- private-by-default corpus ACL/trust boundary;
- no credentials/cookies in Git or corpus metadata;
- no private-life dossiers outside public-interest scope;
- legal/policy holds before public projection.

## Infrastructure decision

Keep:
- PostgreSQL as operational truth and queue;
- existing MiniPC runtime authority;
- bounded filesystem/object storage where capture bodies require it;
- current static/public projection architecture.

Add only when ticketed and measured:
- PostgreSQL FTS + `pg_trgm`;
- optional `pgvector` only after DP-116 benchmark evidence;
- optional archive provider adapter.

Do not add by default:
- Elasticsearch/OpenSearch;
- Neo4j;
- Virtuoso as primary DB;
- a standalone vector database;
- Kafka;
- Kubernetes;
- Meedan Check/Pender/Alegre as full runtime services.

## Delivery strategy

Follow expand-migrate-contract:

1. **Expand** — add corpus/candidate tables and repository APIs without changing public
   behavior or removing direct claim ingestion.
2. **Tracer bullet** — run one real Garlasco path from Discovery Run to candidate
   promotion and existing verification boundary.
3. **Migrate** — make new discovery/intake paths emit corpus records/candidates first;
   adapt curated written intake and media pipelines in bounded slices.
4. **Studio** — implement search/Inbox/Collection/promotion UX on persisted data.
5. **Scale** — increase source coverage after search/dedupe/rights/cost gates prove safe.
6. **Contract** — retire redundant direct-to-claim internal paths only after all callers
   are migrated and compatibility/public tests remain green.

## Ticket dependency map

```text
DP-112 domain contract
  |
  +--> DP-113 persistence -------------------+
          |                                   |
          +--> DP-114 entity/topic/event      +--> DP-116 search
          |        |                          |
          |        +--> DP-115 clusters ------+
          |                  |                |
          |                  +--> DP-117 promotion
          |
          +--> DP-118 retention/replay
                   |
                   v
DP-209 discovery -> DP-210 capture -> DP-211 extraction
                                      |
                         +------------+------------+
                         v                         v
                     DP-212 matching          DP-213 coverage
                         +------------+------------+
                                      v
                                 DP-214 Garlasco
                                      |
             +------------------------+------------------------+
             v                        v                        v
          DP-415 search           DP-416 collection        DP-417 inbox
             |                        |                        |
             +------------+-----------+----------+-------------+
                          v                      v
                     DP-418 review           DP-419 inspector
                          +----------+-----------+
                                     v
                                DP-420 usability
                                     |
                                     v
                                DP-421 public
                          case/collection decision
```

DP-414 (Studio IA/data contract) begins after DP-112/113 and governs DP-415..419.

## What is explicitly not being done now

- no mass crawler before DP-209/210;
- no migration that rewrites the 30 existing Garlasco claims;
- no automatic publication from candidate extraction;
- no new public scoring/leaderboard;
- no public raw corpus browser;
- no full redesign of every public page before Studio corpus acceptance;
- no donor code copy without artifact-level license/provenance review;
- no semantic-search infrastructure without benchmark evidence.

## Research/DStack execution note

The 2026-09-29 planning pass inventoried all 222 installed DStack skill entries under
`~/.config/opencode/library/skills` and deeply reviewed the skills materially governing
this work, including the shared preamble, existing-repo intake, deep research,
competitor/market research, donor semantic delta, site architecture, frontend/design
systems, retrieval, scraping, verification, migrations, security, TDD/E2E/accessibility,
repo delivery, ADRs and docs sync.

The applied DStack rules are visible in this plan:
- reconcile against the real repo before redesigning;
- use donor evidence to adopt/adapt/defer/reject rather than clone blindly;
- prefer tracer-bullet vertical slices;
- use expand-migrate-contract for the wide schema/workflow transition;
- keep every ticket independently provable;
- record hard-to-reverse decisions as ADRs;
- keep runtime claims separate from design/code claims;
- prove runtime-affecting work on MiniPC;
- keep docs and tracker state synchronized with actual implementation.

# Dichiarazioni Pubbliche — Product Constitution

Status: canonical  
Last updated: 2026-09-29

This file defines the product. If a historical note, implementation detail, prototype,
or handoff conflicts with this document, this document wins unless superseded by an ADR.

## Mission

Dichiarazioni Pubbliche is an open-source, Italy-first public-record system for verifiable public
statements.

Its job is to preserve what a public figure said, when and where they said it, the
source and wording that support the attribution, the evidence relevant to a checkable
claim, and the history of later review, correction, reply, clarification, or change.

The product is not a leaderboard of people and it is not a machine that decides who is
"good", "bad", "reliable", or politically preferable.

## Primary users

- citizens who want to inspect the record behind a public claim;
- journalists, researchers, and fact-checkers who need provenance and chronology;
- developers and agents that need stable machine-readable public records;
- public figures or representatives who need a visible correction/right-of-reply path;
- maintainers who need a low-maintenance, auditable pipeline rather than a newsroom.

## Product surfaces

The public product follows the canonical architecture in
`docs/35-public-product-architecture-v3.md`. Its permanent reader-facing templates are:

1. **Home** — explain the product, expose universal search, and show a restrained stream
   of recent public statements plus one strong source/content example.
2. **Explore** — the universal searchable index for statements, people, topics and
   contents, with progressively disclosed filters.
3. **Statement** — the canonical shareable record for one public statement: wording,
   source, finding, verification, evidence, original context and version history.
4. **Person archive** — a chronology of that person's published statements and reviewed
   longitudinal threads, without person-level scores or rankings.
5. **Topic dossier** — a subject-centered view of published statements, related traces,
   relevant contents/sources and navigational person links.
6. **Content** — one original video, podcast, interview, article, speech, post or other
   public source with the published statement moments/locators it contains.
7. **Trace** — a reviewed longitudinal thread showing how closely related statements
   evolved, clarified, updated or conflicted over time without inferring intent.
8. **Method** — the public explanation of provenance, evidence, findings, uncertainty,
   corrections, longitudinal relations and automation boundaries.

Supporting trust/utility documents include Corrections, Data & API, Project and, only
after the intake abuse/legal gates are ready, Contribute. They reuse document grammar and
do not create additional primary product templates.

Dichiarazioni Pubbliche also has one private/operator product with several modes:

9. **Dichiarazioni Pubbliche Studio** — the research and verification workspace. It can discover and
   capture public material into a private Research Corpus, organize bounded Research
   Collections, search passages and entities, triage statement/claim candidates, and
   promote selected candidates into the existing evidence/verification/review pipeline.
   It also accepts pasted text, URLs, articles, video, podcasts/audio and uploaded files.
   Discovery, extraction, matching, analysis completion and candidate promotion never
   equal publication.

The Public product and Studio share one visual language but not one layout: Public is
spacious and mobile-first; Studio is denser and desktop-first because its job is corpus
research, triage, provenance inspection and evidence review.

## Product invariants

These are non-negotiable unless changed explicitly through an ADR and a deliberate
policy review.

### Publication and provenance

- Research-corpus records are private by default. Discovery or capture does not create a
  public claim, finding, or dossier.
- A Statement Candidate or Claim Candidate is not an Atomic Claim. Promotion is an
  explicit, provenance-preserving step and never destroys the candidate record.
- No automatic publication merely because a model produced an answer.
- Evidence retrieval is not evidence approval.
- Evidence approval is not verification.
- Verification is not publication.
- Public output is a projection, never an operational database dump.
- Published statements require approved attribution provenance: timed media claims need speaker
  provenance covering every claim segment; written-source claims need approved text
  provenance bound to the claim, content, person, and immutable quote hash.
- A published finding must be traceable to its claim, transcript provenance, evidence,
  observations, verification rule/version, and review event.
- Corrections and rights of reply are append-only and private by default.
- Historical public records are versioned; material changes are never silent rewrites.
- Written articles/posts/interviews must never be coerced into fake media timestamps just
  to satisfy the publication model.

### Political neutrality and human agency

- No person-level truth, trust, reliability, ideology, competence, or fitness score.
- No ranking of politicians, parties, candidates, or public figures.
- No recommendation of a political choice.
- No inference that a contradiction proves deception or malicious intent.
- A position change is not automatically a lie.
- A false factual claim is not automatically a deliberate falsehood.

### Identity and privacy

- Scope is public figures and public-interest activity, not private-life dossiers.
- Speaker attribution is non-biometric by design.
- No face recognition, voiceprint matching, or biometric identity system.
- Private/raw operational data is not exposed merely because a public projection exists.

### Evidence and time

- Search results, embeddings, similarity scores, entity matches, claim clusters and topic
  suggestions are candidates for navigation/review; none of them independently establish
  identity, equivalence, evidence, truth, or publication eligibility.
- The system must not use future evidence to judge what was knowable at the time of an
  earlier statement unless the finding explicitly concerns a later outcome.
- Official/primary sources are preferred when they are authoritative for the question.
- RAG, embeddings, search indexes, and LLMs are retrieval/reasoning aids, not sources of
  truth.
- URLs, citations, and structured queries used as evidence must be validated by code and
  fetched/observed, not invented by a generic model.
- Reasoned inferences may combine explicit premises, but must preserve assumptions,
  credible alternatives, and disconfirming conditions. Inference is not a substitute
  for evidence or individual identification, and it never publishes by itself.

### Operations and cost

- Public request paths do not call an LLM in v1.
- Work is precomputed and published from a bounded read model.
- Fail closed under uncertainty, missing provenance, provider failure, or budget caps.
- Prefer deterministic logic and cheap stages before expensive model calls.
- Do not introduce Kafka, Kubernetes, Neo4j, a separate vector database, or similar
  infrastructure without measured need.
- The runtime authority for backend claims is the MiniPC; Mac results are development
  evidence, not production proof.

## Scope

### In scope

- public officials and politicians;
- journalists, presenters, commentators, creators, and other public figures when the
  statement is relevant to their public role;
- official/public records and primary evidence;
- public interviews, speeches, podcasts, videos, articles, and other attributable
  content;
- bounded research collections containing captured source versions, passages, entities,
  events, topics, statement candidates and claim candidates;
- factual, numerical, legal/procedural, historical, scientific, quote-attribution,
  promise, prediction, and other explicitly modeled claim types;
- correction, reply, dispute, and re-analysis workflows.

### Out of scope by default

- private citizens;
- irrelevant private-life material;
- political persuasion or voting recommendations;
- global "truthfulness" scores;
- biometric identification;
- autonomous accusations of lying or intent;
- a general-purpose search engine for the whole internet;
- a live public chatbot that spends project tokens per request.

## Definition of a stable v1

Dichiarazioni Pubbliche v1 is stable when a new configured source can produce a public record through
the full pipeline without ad-hoc code or manual database surgery, while every unsafe or
ambiguous branch fails closed. The end-to-end path is:

`discovery -> content -> immutable capture -> passage/transcript -> attribution -> statement candidate -> claim candidate -> explicit promotion -> atomic claim -> evidence -> observation -> verification -> finding -> review -> public projection -> correction/reanalysis`

Most captured material is expected to remain in the private Research Corpus. Stable v1
does not require every passage, statement or candidate to become a fact-check.

The public product must be usable even when all LLM providers are temporarily offline.

## Success measures

We prefer operational and evidence-quality measures over engagement metrics:

- provenance completeness of published records;
- provenance completeness and replayability of captured research material;
- duplicate/derivation collapse and entity-resolution quality on reviewed corpus samples;
- search recall on a versioned corpus benchmark and time-to-source for operator tasks;
- cost per captured/processed content item as well as cost per published finding;
- percentage of unsafe candidates correctly held rather than published;
- reproducibility of deterministic verification;
- correction/reply turnaround and auditability;
- source health and recovery;
- cost per processed content item and per published finding;
- public API/read-model stability;
- maintenance time required per week.

## Non-goal: "automation means no humans"

Automation means routine operation should not require a newsroom. It does not mean the
system may bypass review policy. When a required review or legal decision is unavailable,
the safe result is non-publication.

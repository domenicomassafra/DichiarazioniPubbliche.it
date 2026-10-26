# Dichiarazioni Pubbliche — Product Constitution

Status: canonical  
Last updated: 2026-10-10

This file defines the product. If a historical note, implementation detail, prototype,
or handoff conflicts with this document, this document wins unless superseded by an ADR.

## Mission

Dichiarazioni Pubbliche is an open-source public-record system for verifiable
public statements. An initial Italian audience does not restrict source languages
or public figures to Italy.

Its job is to preserve what a public figure said, when and where they said it, the
source and wording that support the attribution, the evidence relevant to a checkable
claim, and the history of later review, correction, reply, clarification, or change.

The product is not a leaderboard of people and it is not a machine that decides who is
"good", "bad", "reliable", or politically preferable.

**Owner clarification, 2026-10-10:** the reader experience is one integrated
product. Readers must be able to inspect statements and public sources, understand
what factual checks establish or refute and where evidence is insufficient or
uncertain, compare the same proposition or publicly expressed position across
people and over time, and navigate Person and Topic pages to see what particular
people have publicly said about a subject. Source inspection, verification,
cross-person comparison and longitudinal comparison are complementary core
capabilities. A bounded technical pilot validates this experience rather than
replacing it with an archive-only mission. Expressed positions remain attributed
statements; opinions do not acquire a factual true/false verdict merely because
they are included in a comparison.

**Final owner decisions Q15–Q20, 2026-10-10 (target requirements):** a public
Statement displays the exact source words; a normalized proposition/paraphrase
must never replace its declaration text, title-as-quotation, card or comparison
quotation. Paraphrase is allowed in a visibly distinct summary only. Original
wording and identified translations remain separate. The public-v2 implementation
currently projects paraphrase-centered dossiers and wording hashes, not this
target; the new backlog must specify that migration without claiming it is done.
Exact wording does not establish a universal copyright exemption; source-specific
quotation rights remain separate from wording fidelity. A rights-unavailable
record must not be filled with a substitute paraphrase.

Person × Topic combines intersected filters and a dated, source-linked summary
of publicly expressed positions; no chatbot is required. Automate research,
attribution, checks and writing also for public procedural/judicial documents,
preserving the distinction between exact documentary words, reported allegations
and independently established facts. Future source selection prioritizes
continuity and relevant events with disclosed coverage/freshness. The owner
 selects the visual redesign later. The 2026-10-10 planning-only mandate ended
 with the backlog integration. On 2026-10-11 the owner separately authorized
 local source implementation, **not** publication, licensed-source clearance,
 paid-provider trials, bulk collection, deploy or a visual design selection.

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

**Account (owner-requested extension, 2026-10-10):** `/accedi/` and `/account/`
are separate private-by-default utility pages for first-time Google registration,
subsequent login, logout and account deletion. Account membership grants **no**
editorial, moderation, review, Studio, attribution or publication permission and
does not activate public intake. Remote login remains disabled until real Google
OAuth credentials, approved privacy/retention/contact terms and MiniPC security
acceptance are available. Reader pages and the approved public projection do not
require an account.

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

**Superseding owner decision (25 October 2026, #413):** acceptance,
independent review, and publication are autonomous, with no human in the loop.
Publication requires the same source- and version-bound checks performed by
two independent agents using distinct models. Failed or missing proofs leave
the record in HOLD; new evidence triggers re-evaluation. A third agent audits
samples nightly. Corrections or removal requests immediately omit the public
record before autonomous re-examination. Legal, licence, copyright and privacy
reviews are agent decisions with cited sources, not owner sign-offs. The
mechanical safety, provenance and privacy gates below remain mandatory.

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

**Current owner operating constraints, 2026-10-10:** no human editorial reviewer
is available for full fact-check review. The owner proposes approximately five
hours weekly of quick non-textual/visual checks, such as correct Person imagery;
this is distinct from editorial approval of textual attribution or factual
verdicts. Textual analysis and final factual checking are intended to be automated.
In answers Q9–Q14 the owner selected future per-result publication autonomy after
validation, active investigation of ambiguous cases followed by a small exception
queue, withholding unsupported conclusions and explicit insufficient-evidence
results distinct from checks not yet performed. Historical dossiers are
intended as permanent product content; broad collection follows acceptance of
the acquisition/transcription/catalog/ingestion/frontend/verification path.
The product must be designed and evaluated for rigorous automated
fact-checking, preserving uncertainty and stopping unsupported factual conclusions.
There is no established infallibility guarantee. The #413 autonomous target
supersedes human review: implementation must reconcile historical policy
contracts and prove the independent automated gates before cutover.
Investigations may group multiple people and must support other source languages,
with preserved originals and identified Italian translations; no one-person or
Italian-only restriction is approved. Approximately EUR10/month is a tentative
operating-cost target, to be calibrated through measured Antigravity quotas,
audio usage and local-model electricity rather than assumed free/unlimited use.

## Scope

### In scope

- public officials and politicians;
- journalists, hosts/presenters, commentators, influencers/creators, actors, and other public figures when the
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

## Automation and independent review

No person is an acceptance, review, or publication gate (#413, 25 October
2026). The automatic mechanism still runs every binding, source-rights,
identity, privacy and challenge check. Missing rights or independent agent
evidence means HOLD until it can be proved, with the reason retained for retry.

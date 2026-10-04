# Dichiarazioni Pubbliche — Domain Context

Status: canonical  
Last updated: 2026-09-29

This glossary gives stable names to the domain. Code, tickets, ADRs, and documentation
should use these terms consistently.

## Core records

### Source

An origin that can yield public content: an official site, channel, feed, institution,
publisher, podcast, or platform account. A Source has acquisition policy and health; it
is not itself evidence that a claim is true.

### Content

One discoverable public item such as a video, podcast episode, article, speech, or
document. The current implementation calls this `content_item`.

### Locator

A platform-specific identifier or URL that points to Content. Content may have multiple
Locators without becoming multiple Content records.

### Discovery Run

A bounded, reproducible attempt to find relevant public material using configured seeds,
queries, source adapters and budgets. It records the exact discovery strategy and
receipts. Discovery does not imply that a result is relevant, attributable, true, or
publishable.

### Discovery Hit

One candidate URL/item returned by a Discovery Run before or while it is resolved to a
stable Content record. Repeated hits can point to the same Content and remain useful as
discovery provenance.

### Content Capture

An immutable observed version of Content at a particular retrieval time. A Capture binds
the fetched representation to hashes, media type, retrieval method, rights/retention
metadata and optional archive receipt. Content is the logical item; Capture is what the
system actually observed.

### Passage

A bounded, content-addressable portion of a Content Capture used for research,
attribution, search or candidate extraction. Written passages use stable character or
document selectors; media passages may reference existing canonical transcript segments
and time ranges instead of duplicating transcript text.

### Research Collection

A private, bounded workspace around a case, event, topic, person or investigation. It
groups relevant Content, Captures, Passages, candidates and coverage needs without
asserting that every included object is evidence or fact.

### Appearance

The documented participation of a Person in Content, optionally bounded in time and by
role. Appearance is not sufficient on its own to attribute every transcript segment.

### Person

A public figure represented in the record. Person identity is about public-record
disambiguation, not biometric recognition.

### Role Interval

A dated relationship between a Person and an organization, office, publication,
program, or public role. Role intervals are a planned domain capability and must not be
collapsed into one timeless `public_role` string in the long-term model.

### Topic

A stable curated subject identifier with explicit scope and provenance. Model-suggested
labels may become Topic Candidates, but they do not silently create or merge canonical
Topics.

### Event

A bounded real-world occurrence or process used to organize time-sensitive research.
Event membership is a reviewable relation; sharing keywords does not prove that two
records concern the same Event.

### Entity Resolution Candidate

A reviewable proposal that a mention or source identity refers to an existing Person,
Organization, Topic or Event. Matching features and contradictions are preserved so the
decision can be audited. Similarity alone never merges identities.

## Transcript and attribution

### Transcript Variant

One acquired or generated transcript from one provider/source, with its own immutable
hash and provenance.

### Transcript Segment

A bounded piece of a Transcript Variant.

### Canonical Segment

The internal best-supported representation of a time range after comparing available
transcript candidates. Canonical does not mean publicly publishable.

### Speaker Identity Candidate

A non-biometric assertion that a Person spoke during a bounded range, with attribution
method, provenance, status, and review history.

### Speaker Approval

An explicit review event that authorizes a speaker attribution candidate. A claim is not
publicly attributable unless all of its segments have sufficient approved provenance.

## Claim and evidence

### Statement Candidate

A private extraction of an attributable statement from one or more Passages or canonical
media segments. It preserves source wording/selectors, attributed speaker/author
candidates, extraction version and review state. A Statement Candidate may contain
multiple propositions and is not itself an Atomic Claim.

### Claim Candidate

A private normalized proposition derived from a Statement Candidate. It records
check-worthiness, proposed claim type, temporal scope and extraction provenance. It may
be deduplicated or clustered before an explicit promotion creates or links an Atomic
Claim.

### Proposition Cluster

A private grouping of Claim Candidates or Atomic Claims that may express the same or a
closely equivalent proposition. Cluster membership has candidate/reviewed states and
must not be treated as verified equivalence merely because an embedding or lexical score
is high.

### Candidate Match Run

A replayable private comparison of one Claim Candidate against a bounded corpus target
set. It records the exact matching version/input fingerprint and ordered pairwise results.
`SAME_PROPOSITION` or `DUPLICATE_EXTRACTION` may create only reviewable Proposition Cluster
proposals; `UNCERTAIN` is held and never silently merged. Existing Atomic Claims are match
targets, not recreated outputs.

### Source Derivation Relation

A reviewable relation indicating that one Content/Capture substantially republishes,
quotes, syndicates or derives from another source. It helps prevent source amplification:
many downstream articles derived from one origin are not automatically independent
evidence.

### Source Profile

A versioned identity/adapter profile for a configured discovery or evidence source. It
records how the source is addressed, its access/rights state and the evidentiary roles it
can play. A Source Profile has no global trust, reliability, truthfulness, prestige or
political-balance score.

### Evidence Role

A contextual function such as `PRIMARY_RECORD`, `OFFICIAL_STATISTICS`,
`AUTHENTIC_LEGAL_TEXT`, `OFFICIAL_PROCEDURAL_RECORD`, `FIRST_PARTY_STATEMENT`,
`INDEPENDENT_REPORTING`, `EXPERT_SYNTHESIS`, `ARCHIVE_COPY` or
`SECONDARY_REFERENCE`. Roles describe what a source can establish for a bounded question;
they are not publisher rankings.

### Authority Scope

A bounded statement that a Source Profile is first-party or authoritative for a specific
jurisdiction, organization, record/dataset class and optional validity interval. Authority
outside that scope is not implied. Supersession/version rules, authenticity basis,
limitations and required companion roles remain explicit.

### Evidence Requirement Profile

A versioned set of requirements attached to one Claim Type. It describes required roles,
scope/field/temporal matches, independence conditions, conflict checks and review gates.
It defines what evidence is needed to run a verification rule, not what political or
factual outcome the rule should produce.

### Evidence Set Assessment

A private, deterministic assessment of one Claim/Claim Candidate's currently approved
Evidence against its Evidence Requirement Profile. The assessment can be
`SUFFICIENT_FOR_RULE`, a specific insufficiency/mismatch, `CONFLICTING_EVIDENCE`,
`UNRESOLVED_SOURCE_IDENTITY`, `UNRESOLVED_DERIVATION` or `NEEDS_REVIEW`. Missing
requirements emit structured Coverage Need candidates. The assessment is a gate/input to
Verification, never a Finding or verdict.

### Coverage Need

A private structured statement of what research still lacks, such as an official
procedural record, the original interview, a forensic report, an earlier version of a
document, or an independent source family. It may be scoped to a Research Collection,
an Atomic Claim or a Claim Candidate; a later Collection may adopt an existing
claim-scoped need when that Content becomes a member. States are explicit
`OPEN/SEARCHING/SATISFIED/BLOCKED/WAIVED`, search attempts are bounded, and satisfaction
requires a concrete Content, Evidence or Source Profile link. Coverage Needs drive
further discovery; they are not findings, truth assessments or political priorities.

### Atomic Claim

A normalized, independently reviewable proposition extracted from one or more Canonical
Segments. It keeps links back to the original wording and temporal scope.

### Claim Segment

The provenance edge from an Atomic Claim to the Canonical Segments that support the
attribution.

### Claim Text Provenance

The provenance edge for a claim attributed from a written public source rather than a
timed transcript. It binds Claim, Content, Person, an immutable quote hash, an optional
document hash/character position, attribution method, and an explicit review event.
It is an alternative provenance channel to Claim Segment, never a fabricated `0:00`
media segment, and does not expose the source body in the public read model.

### Evidence

A fetched/observed source artifact relevant to a claim. Evidence has URL/source
provenance, observation time, optional publication/reference dates, and content hash.
Evidence is not automatically approved merely because it was fetched.

### Evidence Candidate

A proposed relation between an Atomic Claim and Evidence produced by retrieval. It must
be approved/rejected/quarantined separately from retrieval.

### Evidence Observation

A structured statement extracted from Evidence: for example a number, date, legal
status, or exact phrase. Verification should reason over explicit observations where
possible rather than opaque snippets.

### Inference Candidate

A private, reviewable conclusion derived from explicit premise references rather than
copied directly from one source. It records the inference kind, qualitative support,
assumptions, live alternative hypotheses, and facts that would weaken the conclusion.
An Inference Candidate is not Evidence, does not identify a fact merely because it is
plausible, and cannot itself authorize a Finding or publication.

## Verification and publication

### Verification Run

A reproducible application of a named/versioned verification rule to an Atomic Claim,
an evidence/observation set, an exact Source Intelligence Evidence Set Assessment and a
statement-time cutoff. A Verification Run is analysis; it is not publication authorization.
Legacy adapter metadata such as `authoritative=true` cannot independently make Evidence
eligible for verification.

### Assessment

The claim-level result produced by a Verification Run. It is not a score attached to a
Person.

### Finding

An append-only reviewable record that explains an Assessment, references its
Verification Run and evidence set, and has an independent publication status.

### Review Event

An append-only decision about a reviewable entity. Approval must be explicit; current
state alone must never be treated as sufficient proof that a review happened.

### Public Projection

The bounded, sanitized, fail-closed read model emitted for public consumption. It may
contain JSON, JSON-LD, HTML, and later API responses. Operational/private records do not
become public merely because they exist in PostgreSQL.

### Published Dossier

One finding-versioned public record emitted by the Public Projection, including the
publicly safe claim, provenance identifiers, evidence metadata, assessment, review
history allowed by policy, and related correction/reply information.

The existing term Published Dossier remains a single finding-versioned public record. A
private Research Collection is not a Published Dossier, and any future public
case/collection view must use a distinct contract rather than overloading this term.

## Change and challenge

### Claim Relation Candidate

A proposed longitudinal relation between claims, such as same proposition, position
change candidate, or contradiction candidate. Candidate relation is not a published
accusation.

### Right of Reply

A response submitted against a Finding. It begins private, triggers re-analysis, and is
only exposed after its own publication review and the required parent-finding policy.

### Correction

An append-only record that links a superseding Finding to a previous Finding and states
what changed. Corrections do not rewrite history silently.

### Re-analysis Trigger

An explicit event that asks the system to reconsider a claim because evidence, reply,
correction, relation, or manual review changed the relevant inputs.

## Operational records

### Processing Job

One idempotent queue unit with bounded retries, lease state, cost record, and explicit
blocked/dead-letter behavior.

### Provider Receipt

A record of an external provider operation including provider/model identity, request
metadata, status, and cost estimate where available.

### Source Health

The operational state of one Source: last success, last item, consecutive failures,
degraded status, and error details.

## Required semantic distinctions

These distinctions are part of the domain, not writing style:

- `retrieved evidence != approved evidence`
- `approved evidence != verified claim`
- `evidence != reasoned inference candidate`
- `reasoned inference candidate != verified fact`
- `verified claim != published finding`
- `false claim != deliberate falsehood`
- `position change != lie`
- `contradiction != proof of intent`
- `speaker appearance != approved segment attribution`
- `text appearing on a page != approved text attribution`
- `discovery hit != content identity`
- `content != immutable content capture`
- `research collection membership != evidence`
- `statement candidate != atomic claim`
- `claim candidate != atomic claim`
- `similarity/match score != identity or proposition equivalence`
- `proposition cluster != verified relation`
- `canonical transcript != publishable transcript`
- `public projection != operational database`
- `relation candidate != published relation`

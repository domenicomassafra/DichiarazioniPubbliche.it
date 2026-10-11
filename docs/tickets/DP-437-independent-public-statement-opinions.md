# DP-437 — Independent public Statements for opinions and positions

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-435, DP-104, DP-111, DP-312

## Problem

The public-v2 projection derives dossiers from published factual Findings. Authenticated opinions/positions and non-factual speech acts cannot appear as public Statements without an invented Claim/Finding, defeating the integrated mission.

## Outcome

A source/rights/attribution-approved opinion or other non-factual Statement can be published and read independently of factual verification, while any optional factual Finding remains separately linked and precisely labeled.

## Traceability & constraints

R01, R15, R16, R20; Q9–Q20. An opinion does not get a true/false verdict by default. Human textual review is not the future routine target, but existing review/publication controls remain until explicitly migrated and proven. No person score or inferred hidden belief.

## Scope

Define versioned public Statement identity/lifecycle, time, speaker/author, speech-act/endorsement state, exact quote/source hash, quote rights, optional finding reference and publication decision. Project for Person/Topic/Content with no Finding dependency. Publish states distinguish **not yet checked**, **a completed check with insufficient evidence**, non-factual opinion and an actual sourced factual finding; an internal held or unreviewed candidate is never a public status. Append correction/reply without editing historical original wording.

## Non-goals

No invented factual verdict, generic auto-publishing of candidates, ranking of people, private corpus membership disclosure or Statement-to-Claim semantic merger.

## Dependencies and sequencing

Hard DP-435 original wording, DP-104 relations policy and DP-111 written provenance; coordinate B future speech-act/authority contracts, DP-405/406/409 and DP-431. Qualified source-use and publication authority remain external gates, not automatically inferred by being an opinion.

## Acceptance criteria

- [ ] `AC-437.1`: An approved non-factual Statement with no Finding appears on its canonical page, attributed Person/Topic/Content routes and API with original wording, date and source, and no fabricated verdict.
- [ ] `AC-437.2`: A completed insufficient-evidence factual investigation remains distinguishable from unverified and from opinion; statement-level publication does not silently publish an unreviewed factual claim.
- [ ] `AC-437.3`: Reported speech, quotation under criticism, uncertain speaker, unauthorised rights or private-held candidates create no endorsed public position, badge or private membership count.
- [ ] `AC-437.4`: Later genuine Finding, reply, correction or retraction is append-only/versioned; replay and consumer readback retain original quote and correct current status.

## Validation / proof

Future deterministic and negative fixtures for opinion-only, claim+finding, reported quotes, cancelled approval, rights expiry and privacy isolation; compare HTML/API/search and real rights-authorized MiniPC projection with source/fingerprint. No AC is fulfilled by this ticket being written.

## Documentation, data, and migration impact

Extend CONTEXT vocabulary and the public read model additively; decouple Statement index from Finding-only dossiers with version compatibility. Preserve historical DP-105, DP-221 and DP-305 receipts; no new infra solely for optional Finding.

## Completion receipt

### 2026-10-12 — Opt-in pinned Statement-centric private SSR preview

New `web/src/lib/privateStatementOpinionPreviewV3.ts` consumes the real
independently pinned Person v3 public archive/cross-reader, indexed Statement
and original public source bundle as **one private Statement-ID lookup**.
The host must provide the *current external release pins* before and after
building the returned model; changed release ID/epoch/hash/expiry fails
closed even when the old bytes remain internally self-consistent. A found
record is emitted only when its original Statement still has the exact
Person, quote hash/wording, source SHA/version, Content locator, date,
endorsement and OPINION speech-act, with `finding_id = null`. No Claim
rating, factual conclusion, source paraphrase or automatic public authority
is invented. Unknown/private/HELD/wrong-Person/withdrawn Statement lookup
has one generic UNAVAILABLE response without membership counts.

The new Node check runs a genuine Python approved Statement/Person/Topic
source fixture through the TypeScript consumer into a *temporary Astro SSR*
render, with explicit noindex. Positive original citation, no-Finding,
source-date and locator match; adversarial stale Current pin, independent
revocation in the second read, thrown authority, mutated source bytes and
request without opt-in all fail. Rendering is detached from later source
object mutation. **GREEN** after the consumer was absent; `node
--experimental-strip-types web/scripts/check-private-statement-opinion-preview-v3.mjs`
passes, and `npm run check` reports **111 files, zero diagnostics**.

This is a *private isolated preview*, NOT the public canonical Statement
page/API/Person×Topic+Content production reader, nor proof of approved
rights, real correction/reply propagation, independent editor signoff or
MiniPC readback. Original AC-437.1–.4 remain OPEN; no public route,
provider, production change or authority was installed.

2026-10-10: specification only, **not implemented**, all new AC unchecked.

## 2026-10-11 — First implementation slice

New `PublicStatement` v3 opt-in projection (`2405049`) supports an attributable opinion with nullable Finding, separate checking semantics and source literal approval. Focused schema/projection tests pass. No genuine opinion public page, rights/publication eligibility, person/topic consumer, historical correction or real runtime acceptance; AC remain open.

## 2026-10-11 — Opt-in grouped Person × Content opinion read API (source only)

A distinct pure read-only backend consumer
`list_public_opinions_by_person_content_v3` now operates **only on a
prevalidated, independently governed public Statement v3 bundle**. This is
not an HTTP route, permission grant, production reader or publication
pipeline. It requires explicit `allow_statement_v3=True` and the
`current_public_dataset_sha256` obtained independently from the current
authorized public release; a missing/mismatched fingerprint refuses the
entire request (503). An old internally valid bundle cannot be silently
replayed after rights withdrawal. The input bundle is independently copied
before revalidation and assembly to avoid exposing mutable source rows
after the validation step. No historical v2 dossier or normalized
paraphrase can become an original Statement.

The new function groups currently published, **endorsed OPINION**
Statements first by their explicit `person_id`, then by `content_id`,
with deterministic dated Statement ordering and optional *intersected*
Person/Content ID filters. A group carries only IDs and never infers a
person's identity, current belief or a single common source version;
each entry reuses the **same allowlisted Statement API record** as
`get_public_statement_v3`. Exact original words, date, source URL,
immutable content/version/source/quotation hashes, language and written
or timed locator remain attached per Statement. Summaries/translations
remain distinct; optional `finding_id` is a reference, not a fabricated
opinion verdict. Reported speech, criticism, irony, unendorsed opinions,
factual assertions and private/held/revoked candidates are absent from
this *endorsed-opinion* collection. An empty/unknown/private Person filter
returns the same zero public records and no private membership count.
This restriction does **not** suppress non-endorsed speech in the
separate preexisting v3 Statement archive.

Adversarial `tests/test_dp437_public_opinion_api.py` builds **three
independently five-gated synthetic v3 original Statements** through the
existing source text and review readers. RED before implementation:
new opt-in grouped reader was absent (import failure). GREEN: 7 focused
tests cover Person×Content grouping, multi-Statement date ordering,
verbatim API-detail equality, no Finding or invented score/verdict,
invalid/unknown filters, rights revoked/HELD omission, reported/critical
and non-endorsed exclusion, stale source fingerprint 503, source-version
reapproval, byte-stable replay and separation of mutable input from
serialized output. Adjacent DP-435/436 v3 parity and public API:
**116/116 PASS**; public projection: **48/48 PASS**; deterministic
benchmark: **5/5 PASS**; targeted compileall and `git diff --check`
PASS. No genuine licensed source, private body, provider call or real
MiniPC was used.

**Original AC-437.1–.4 remain unchecked and ticket IN PROGRESS.**
AC-437.1 has source-only Person/Content API read proof, **not** an
approved public HTML/API route, subject Topic integration or real source
rights. AC-437.2 still requires public checking-state distinctions
(unchecked/insufficient-evidence/factual Finding) and their review
authority, which this explicitly opinion-only read model does not
invent. AC-437.3 has negative membership tests only, not complete
cross-consumer/private search evidence. AC-437.4 still needs durable
append-only correction/reply/retraction history, current release/cached
API/index parity and end-to-end source rights revocation. A caller-
supplied fingerprint is not itself proof of authority: an independently
attested release manifest is still external. Public-v2 writer and
`/api/v1` live routing remain unchanged/disabled for v3; no production,
MiniPC, commit or push in this tranche.

# DP-416 — studio research collection workspace

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-113, DP-114, DP-414

## Problem

Research around a case/topic is currently scattered across claims and source notes. Operators need one bounded workspace where sources, chronology, entities, candidates and gaps can be inspected together.

## Outcome

Implement the Research Collection workspace with corpus rail/filters, selected source/passage/timeline view and contextual inspector for entities/statements/claims/provenance/actions.

## Scope

- Collection header contains scope/status, not a truth summary.
- Provide source-oriented and chronology views; graph view is not default.
- Show Coverage Needs and saved filters/views only when persisted.
- Selecting a candidate highlights exact passage/source moment.
- Collection membership actions create reviewed/provenanced edges.

## Non-goals

- No person ranking/statistics.
- No guilt/intent summary.
- No decorative graph/timeline when chronology is not task-relevant.

## Dependencies and sequencing

DP-113, DP-114, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-416.1:** Garlasco pilot can be navigated from collection -> source -> passage -> candidate -> existing/promoted claim.
- [ ] **AC-416.2:** Removing color/icons preserves hierarchy.
- [ ] **AC-416.3:** Large corpus does not require loading all records client-side.
- [ ] **AC-416.4:** Unknown/private/unreviewed public states remain private.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Private Studio UI/API. Must use real corpus fixtures, not lorem ipsum.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

### 2026-10-12 — One consistent authenticated PostgreSQL tree and operator navigation

A distinct local Studio operator path now reads the *whole* bounded
Collection→INCLUDED Content→Source→latest Capture→written Passage→Statement
Candidate locator graph in **one PostgreSQL REPEATABLE READ READ ONLY**
transaction, rather than inviting the operator to combine several
independently timed snapshots. The new
`/v1/collections/navigate` route runs only inside the existing explicitly
started 127.0.0.1 token-authenticated service, requiring collection ID,
limit ≤10 and a cursor whose Content is *currently INCLUDED in that exact
collection*. SQL never selects source URL/title, private texts, raw
Statement/Claim, credentials or receipts, and the presenter strictly
allowlists every nested Source/Capture/Passage/Candidate locator and
position. Latest Capture is selected by persisted observed time then ID,
not by client-supplied hash. Up to three written Passage selectors/candidate
counts per latest Capture are returned with explicit truncation; the
existing exact source-bound `/v1/collections/passage-lineage` remains
the paged Claim Candidate/promoted receipt drilldown.

The local Studio Collections page now has an actual keyboard-reachable
reader: it displays IDs, Capture and Passage/status/counts and click-through
to the existing exact Candidate lineage, preserving token boundaries and
clearing private locators on disconnect, token change or workspace switch.
No raw source body is in HTML/JS or the returned JSON; every item expressly
sets preview/review/publication authorities false, even when the DB marks
rights APPROVED. Bad/removed/foreign pagination cursors and malformed
rights/scope/selector responses are refused instead of rendering a
misleading empty success.

RED→GREEN: new Python tests originally failed with missing navigation
module. A disposable canonical-schema PostgreSQL fixture exercises real
source, two Capture versions, written Passage, Statement Candidate and
Claim Candidate through authenticated HTTP and read-only DB role, including
pagination, post-read revocation, membership removal and privacy negatives.
Existing browser tests additionally cover keyboard jump/cancellation.
This is local synthetic-source acceptance, not a claim that the Garlasco
production corpus has rights-cleared Capture/Passage rows, reviewer or
MiniPC installed UI; AC-416.1–.4 stay OPEN pending authentic runtime and
operator acceptance. No provider, deployment, legal clearance or production
mutation occurred.

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Fixture-only collection inspector — 2026-10-08

The shared read-only Studio client now filters a bounded collection list and displays
the selected scope, source reference and state/blocker code using native button/input
focus semantics. The current fixture is explicit and **not** passed off as a real
persisted collection. No private source, passage, candidate, coverage need or review
link is fabricated. Real DP-214/Garlasco collection navigation, pagination, approved
membership actions, browser accessibility and MiniPC persisted proof remain open;
no AC is checked solely because the fixture renders.

Follow-up 2026-10-08: on-demand token-authenticated loopback-only
Collections endpoint now reads persisted paginated IDs, lifecycle states,
and counts of explicitly INCLUDED collection members (no raw names,
private scope, source bodies or unapproved interpretation). The local
browser can issue this query. Full collection→source→passage→candidate
navigation and Garlasco acceptance remain open.

Follow-up 2026-10-08: `research:garlasco` is now an actual **PAUSED**
PostgreSQL collection holding exactly 18 prior historical Content IDs,
all rights `UNKNOWN`. Private `StudioOperatorQueues.list_collections`
returned `research:garlasco`, `PAUSED`, `included_content_count=18`
in a real MiniPC read-only canary. This advances the real collection
read-back/selection prerequisite, **not** the source→passage→candidate
operator path or a ready public page.

### Private persisted collection→Content→Source/Claim navigation — 2026-10-08

Added bounded, authenticated, **loopback-only** JSON endpoints
`POST /v1/collections/members` and `POST /v1/collections/member`,
backed by `StudioOperatorQueues` and transaction-read-only PostgreSQL.
The former lists only INCLUDED Content IDs, Source IDs and canonical
rights/processing states for a specific persisted collection (limit
1–30, stable keyset cursor). The latter refuses a Content outside
that exact included membership, and returns source existence, counts
of captures/passages/statement/claim candidates, plus up to 30
persisted historical claim IDs/speaker IDs/types with a separate
claim cursor. Neither endpoint selects or exports URL, title,
transcript, quote, private body, source metadata or raw receipt.
No inferred rights or publication/reviewer authority is introduced;
any gaps show stable blocker codes.

The local operator shell now provides an actual Collections → included
Content → detail workflow: native focusable buttons are created from
server-provided IDs with `textContent`, never `innerHTML`. The
static public build and public navigation are unchanged.

**Real MiniPC proofs**:
- 1 PAUSED `research:garlasco` collection; **18/18** included Content
  rows with `rights_status=UNKNOWN`,
  `processing_status=REVIEW_REQUIRED`;
- all 18 details inspected, yielding **10 distinct Source IDs** and
  **30 linked historical Atomic Claims**; Captures/Passages still
  **0/0** and all review/publication flags false;
- exact Content outside included membership refused, missing keys
  rejected, request with no token HTTP 401, cross-origin HTTP 403,
  valid local token HTTP 200, and outside-membership HTTP 422.
- local and MiniPC focused negative tests include order/cursor,
  forged values, missing source, unsafe state and private-field leaks.

This is a *partial historical path*, not AC-416.1 DONE: there are
still **no** persisted Garlasco Passages or Candidates, no exact
passage/time selector, no approved provenance/rights, no real
accessibility/browser evidence, and no reviewed membership mutation.
Keep DP-416 IN PROGRESS, all ACs unchecked. See
`docs/reviews/2026-10-08-studio-garlasco-private-members.md`.

### Historical Claim text-provenance navigation — 2026-10-08

The authenticated, on-demand Studio collection inspector now supports
Content→Atomic Claim→persisted `claim_text_provenance` via
`POST /v1/collections/claim-provenance`. An INCLUDED collection
membership and exact Claim.content_id binding are required inside
the same DB query, not inferred from caller-provided IDs. The
reader returns bounded stable record IDs, stored status, selector
type/hash and optional positions with blocker codes. No original quote,
normalized Claim text, source_ref, source URL, raw reviewer metadata
or private body is emitted.

The local UI has a native Claim-selection button which opens the
private provenance form. Live MiniPC read-back: 30 historical Claims
over 18 Content, 28 APPROVED TEXT_QUOTE_HASH attribution records
and 2 Claims with no provenance record, with no Claim/Content/Person
binding errors. Exact HTTP proof: authorized 200, missing token 401,
wrong Claim 422, cross-origin 403.

APPROVED describes **only the persisted record state**. The API
explicitly returns rights_clearance=false,
review_authority_evaluated=false and publication_authority=false
even for APPROVED records. All 18 Content rights remain UNKNOWN
and no Garlasco Capture/Passage is stored. Full Source→Passage→
Candidate and browser/accessibility acceptance still require
independent evidence. No DP-416 AC closed.
Receipt: `docs/reviews/2026-10-08-studio-garlasco-text-provenance.md`.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** **AC-416.1–.4 OPEN.** Existing loopback read-only MiniPC Collection→18 historical Contents→30 claims; 28 approved-state claim text-provenance hashes are not rights clearance; 0 real Garlasco Capture/Passage/Candidate.

**Target delta and remaining acceptance:** Real persisted Collection→source→capture→exact Passage→Candidate→promoted Claim route; paginated large corpus, no client-side full load; accessible keyboard/color-independent hierarchy; membership changes need reviewed/authorized and safe replay. No unreviewed content in public projection.

**Phase / dependencies:** Phase 2/3; hard DP-214/414 and persisted source/candidate records, soft A-NEW-08/B promotion; Studio owner.

**Related future specifications (separate ownership):** DP-242. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.

### Persisted parent-bound collection cursors — local source proof, 2026-10-11

The existing private, loopback token-authenticated, transaction-read-only Studio
collection readers now reject a page cursor unless its persisted anchor still
belongs to the exact parent being browsed: an `INCLUDED` Collection member for
`/v1/collections/members`, an Atomic Claim of the selected Content for
`/v1/collections/member`, or a text-provenance record bound to the selected
Claim, Content and speaker for `/v1/collections/claim-provenance`. All three
checks execute in the same SQL snapshot as their bounded keyset page. A cursor
from another parent or a removed member fails closed instead of silently
skipping entries. No raw text, URL, private metadata, new authority or extra
query parameter appears in the API response.

Adversarial test was **RED** before the fence (wrong-collection cursor silently
returned an empty page) and **GREEN** after it. Local disposable PostgreSQL
proof exercises three cross-parent cursors, three valid consumed cursors,
membership revocation between pages, private field exclusion and false
publication authority. The existing loopback authentication and read-only DB
session are unchanged; this is a source/fixture proof only, with no MiniPC
read-back, production changes, or real Garlasco Passages/Candidates.

Local checks: `python3 -m compileall -q poc tests` PASS;
`PYTHONPATH=poc python3 -m unittest tests.test_studio_operator_queues
tests.test_studio_local_api tests.test_studio_capture_selectors_pg -q`
**41/41 PASS**; Ruff and `git diff --check` PASS. Broad suite:
`PYTHONPATH=poc python3 -m unittest discover -s tests -q` ran **2,884**
tests in **159.041 s**, with **3 errors** in the separate
`test_existing_factcheck_persistence` operation-receipt write path. These
errors remain failures, with no assertion of overall suite success or DP-416
dependency closure. No code outside the three DP-416-owned files was edited.

**AC-416.1–.4 remain OPEN.** Historical `research:garlasco` still has no real
Capture/Passage/Candidate chain, and keyboard/color-independent hierarchy,
large-corpus performance, reviewed membership actions, rights decisions and
full MiniPC acceptance still require their own proof.

### 2026-10-11 — persisted Collection→Capture→Passage→Candidate private readback (new local seam)

`StudioOperatorQueues.inspect_collection_passage_candidates` now provides a
**functional, optional, read-only** drill-down for a real **INCLUDED** Collection
member, exact Content/Source ID, immutable *written* Capture SHA-256/ID,
persisted Passage selector/hash, linked Statement Candidate IDs, and their
Claim Candidate IDs/statuses. Where a Claim Candidate is `PROMOTED`, it reports
the associated Atomic Claim ID **only if** both the persisted same-Content
claim and corresponding `claim_candidate_promotion` ledger receipt are joined;
neither that status nor the receipt is asserted to grant editor/reviewer or
publication authority. The PostgreSQL join checks membership, Capture→Content,
Passage→Capture/Content, Statement Candidate→Passage/Content and Claim
Candidate→Statement/Content in one DB statement. This is distinct from the
earlier cross-parent cursor proof; the **new** scope is a full candidate
navigation path, not only pagination validation.

The response projects only bounded audit **IDs, hashes, selector coordinates,
persisted states and reason codes**. Statement Candidate pages are keyset-
paginated by exact Passage at 1–30 rows; at most five Claim Candidate IDs are
shown per Statement with the exact persisted count and `truncated` flag when
more exist. The supplied Statement cursor is checked as an existing Passage
link in the same SQL read snapshot. No title, private passage/source text,
canonical or final URL, body ref, provider receipt, actor identity, arbitrary
JSON metadata, score, or model-generated description is read or returned.
Rights/process/capture holds stay visible by state/blocker only, and
`rights_clearance`, `review_authority_evaluated`, `publication_authority`
and per-claim promotion authority remain **false**, even with `APPROVED`
record states. `MEDIA_SEGMENT_REF` remains the separately governed canonical
segment lookup (logical Content, not immutable Capture) and is deliberately
not reinterpreted as a versioned written Passage.

**RED→GREEN evidence:** two new tests were RED with missing
`inspect_collection_passage_candidates`; implementation turned them GREEN.
The concrete PostgreSQL acceptance initializes a **disposable** `schema.v1.sql`
cluster and real synthetic `research:pilot` Collection membership, Source,
Capture, two written Passages, Statement→Passage edges, paginated Statements,
Claim Candidates and one promotion with an actual persisted promotion receipt.
It verifies source/Capture/Passage/claim navigation and keyset follow-up,
cross-Collection/Content/Capture/Passage refusal, foreign cursor rejection,
membership revocation between reads, rights revocation without implicit
clearance, and absence of secret text/URLs. Forged in-memory rows additionally
exercise cross-claim identity, invalid selector/hash/state, missing promotion
receipt, bounded pagination and sanitization of PostgreSQL error text. The
existing local `_StudioQueueReader` automatically inherits this method and
the transaction-read-only database adapter; there is **no** new HTTP endpoint
or browser route and no edit to `studio_local_api.py`.

Mac source-only adjacent proof: `PYTHONPATH=poc python3 -m unittest
tests.test_studio_operator_queues tests.test_studio_local_api
tests.test_studio_capture_selectors_pg -q` **43/43 PASS** at the first
post-implementation checkpoint, with an additional focused negative round
subsequently added. No full-suite or MiniPC runtime acceptance claimed. Ruff
lint, Python compilation and scoped `git diff --check` pass. Ruff format's
baseline check already fails for both historical source/test files at HEAD;
mass reformatting these unrelated areas is intentionally avoided.

**Original AC-416.1–.4 remain OPEN.** Real Garlasco still lacks persisted
Capture/Passage/Candidate rows: the PostgreSQL fixture is an isolated test,
**not** live case evidence. A private Studio operator UI/API wiring, human
keyboard/color-independent/zoom acceptance, large-production-corpus
performance, production MiniPC snapshot and separately reviewed membership /
source-rights decisions are still required. No approval, promotion, database
schema mutation, provider query, production change, push or deployment occurs
through this seam.

### 2026-10-11 — bounded browser Collection→written Passage→Candidate navigation (local UI proof)

The private nonce-bound Studio page now renders clickable, keyset-paginated
Collection IDs and included Content IDs. The existing authenticated
Collection→Content→Capture metadata path now retains the **exact selected
Capture ID and SHA-256**, accepts only written Passage selectors whose
`capture_locator` matches that Capture/Content, and opens the private
`POST /v1/collections/passage-lineage` route with
`collection_id`, `content_id`, `capture_id`, `passage_id`,
`limit` and `after_statement_id`. The candidate inspector exposes only
validated persisted IDs, statement hashes, selector coordinates, statuses,
recorded Claim Candidate→Atomic Claim IDs and promotion receipt IDs.
These recorded links are explicitly **not** permissions to review,
reproduce sources or publish. Native buttons, a focused detail heading,
live status text and textContent-only rendering preserve keyboard
operability and avoid HTML injection.

The same private page now reads the separate
`POST /v1/discovery/capture-queue` endpoint using collection-bound
`after_capture_id` keyset pagination (the actual HTTP API field).
Exceptions appear with persisted IDs, states and blocker codes only.
Malformed response contracts, wrong Capture/Collection binding or
unvalidated pagination fail closed without writing response bodies into
the shared results panel. Changing or clearing the in-memory token
invalidates outstanding requests and scrubs the added private links.
No browser storage, external provider, remote account, rights grant,
capture action, review action or publication path is introduced.

**RED→GREEN receipt:** the new test executing the *real rendered inline
JavaScript* was RED at missing dedicated Collection Passage UI; it is now
GREEN for Collection selection, Content, Capture, exact written Passage,
Statement/Claim Candidate and recorded promoted Claim inspection; both
keyset cursors; keyboard focus; cross-parent/forged response exclusion;
clear-token and token-replacement late-response scrubbing. Existing async
regression also passes. Local focused suite:
`PYTHONPATH=poc python3 -m unittest tests.test_studio_local_page_async
tests.test_studio_local_api tests.test_studio_operator_queues
tests.test_studio_discovery_triage_reader -q` **48/48 PASS** before the
final isolated token-change regression, which separately passed **2/2**;
`ruff check`, targeted `compileall` and `git diff --check` PASS.
A disposable headless Chrome experiment did not complete within its
35-second timeout; it was excluded from the stable tests. Thus native
Chrome/VoiceOver manual accessibility evidence and live HTTP browser
acceptance remain open, as do comprehensive corpus performance and
MiniPC/read-back gates.

**AC-416.1–.4 remain OPEN.** Garlasco has no authorized real persisted
Capture→Passage→Candidate chain; synthetic `research:pilot` fixtures
are development evidence only. No source rights approval, reviewer
authority, production mutation, schema migration, commit, push or deploy
is claimed by this UI slice. The adjacent API file belongs to its
independent worker.

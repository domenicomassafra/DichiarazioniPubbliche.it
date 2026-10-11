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

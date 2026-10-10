# DP-415 — studio corpus search workspace

Status: DONE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-116, DP-414

## Problem

Operators need to search before recollecting or rechecking, but existing public Explore/search is intentionally sanitized and too narrow for private corpus work.

## Outcome

Implement the private Corpus Search workspace with mixed typed results, structured filters, keyboard-accessible query state and a selected-result inspector that jumps to exact source/passages.

## Scope

- Use DP-116 internal query contract, not public search API.
- Result kinds content/passage/statement/claim/person/topic/event/collection with clear type labels.
- Filters by collection/person/topic/event/date/source/type/state/check-worthiness/claim type.
- Persist shareable/local query state only as approved; no secret query payload leakage.
- Selected result shows capture/provenance and source jump without requiring a verification run.

## Non-goals

- No public raw-corpus search.
- No chatbot as primary search UI.
- No search-generated truth answer.

## Dependencies and sequencing

DP-116, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-415.1:** Keyboard-only user can query/filter/open/return while retaining state.
- [x] **AC-415.2:** Known benchmark questions return expected top-K records.
- [x] **AC-415.3:** Private result bodies never enter public build artifacts.
- [x] **AC-415.4:** Provider offline state does not break lexical baseline.

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

Private web/API/runtime; web acceptance + accessibility/runtime proof required.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Read-only preparatory slice — 2026-10-08

`StudioReadOnlyWorkspace.tsx` and `studioReadOnlyWorkflows.ts` add keyboard-native
query, kind filtering, selected-result inspection and explicit fixture/empty-state
wording. The browser runs **only** on explicit fixture opt-in; production static builds
exclude `/studio/*` and do not embed a private corpus. This client-side filter is
not a PostgreSQL query, a verified search result or an authorization boundary.

`studio_operator_search.py` supplies a separate **operator-local** read-only
metadata-only interface over DP-116's `CorpusSearchStore`. It bounds query/filter/
result counts, returns source/content/passage identifiers but never source snippets,
private transcripts, raw query text or provider details, and fails closed on malformed
backend data or errors. It does not create an HTTP listener, public API or automatic
publication path. Run locally as
`PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.studio_operator_search --query '<termine>'`
only with an already-authorized private PostgreSQL environment; do not copy its
output into static files.

AC-415.1 (interactive real private UI and keyboard browser proof), AC-415.2
(actual DP-116 top-K benchmark against the accepted corpus), AC-415.3 (end-to-end
private/public artifact audit), and AC-415.4 (provider-offline live corpus run)
remain **open**. The result is a preparatory, testable vertical slice, not DONE.

### On-demand authenticated operator-local API — 2026-10-08

The operator-only module studio_local_api.py now binds exact 127.0.0.1
**on explicit invocation**, using a protected 0600 token file and five
read-only PostgreSQL-backed endpoints plus a same-origin local HTML page.
The UI has native forms for Corpus, Collections, Inbox, Match and capture
comparison. The browser keeps its token in memory, never cookies/storage,
and all returned database values are rendered with textContent.

Strict Host/Origin and bearer-token checks, no CORS, no external assets,
non-persisted browser credentials, exact URL allowlist, 4KiB JSON requests
and bounded database responses were exercised with negative HTTP tests.
The DB bridge enforces PostgreSQL read-only mode with bounded query,
connection and subprocess timeouts, independently of the HTTP route.
No external service, public route or mutation authority is enabled.

Operator instructions: docs/ops/studio-local-readonly.md. The live Garlasco
top-K, full private source/passage browser flow, rights authorization,
human accessibility testing and real persisted MiniPC acceptance are
still **not proven**. DP-415 remains IN PROGRESS.

### 2026-10-09: local browser disconnect and stale-response boundary (Wave 18)

An operator could previously clear the bearer token while already-rendered
private collection/member links and the media locator stayed visible. A pending
request could also restore a private JSON response after disconnect, or an
older workspace request could overwrite the results of a later query. A
deterministic Node harness executes the actual nonce-scoped Studio inline JS
with deliberately late responses. It first failed on retained private links
(RED); after the fix, clear/disconnect scrubs all derived private locators,
increments a request generation and aborts the active fetch. Late network
completions are ignored by generation even when abort loses a race; workspace
changes and replacement queries invalidate earlier results too (GREEN).

This is a source-only privacy/interaction regression test, **not** a claim of
real browser accessibility, operator consent/rights, MiniPC runtime acceptance
or completion of AC-415.1. No public artifact, credential persistence or
backend mutation was introduced.

### Closure: live private Corpus and keyboard workflow — 2026-10-10

**DP-415 is DONE for its four bounded acceptance criteria and private
metadata-only search contract.** The older partial receipts above are
historical; the operator must still explicitly start the loopback Studio.

- **AC-415.1:** The authenticated loopback Corpus form now exposes DP-116
  filters for result kind, Collection, Source, Person, Topic, Event, date
  bounds, state, claim type and check-worthiness. Requests are transformed
  into the canonical `CorpusSearchRequest` and an allowlisted source-scoped
  response containing *only* kind/Content/Source/Passage/record IDs. Chrome
  headless ran the **actual nonce-bound operator HTML** with native Space
  input: filtered POST with bearer credential, selected-result inspector,
  exact Collection/Content/Source jump via the independently authenticated
  persisted-membership reader, return preserving search form/filter state
  and focus, plus workspace-switch scrubbing of private identifiers. The
  delayed-response harness separately proves token clearing, request
  cancellation/generation rejection, and private extra-field refusal.
  Source/Passage references that have no approved Capture are displayed as
  **opaque locators**, never fabricated content bodies or media players.
- **AC-415.2:** On the authoritative MiniPC PostgreSQL database
  `dichiarazioni_pubbliche`, `CorpusSearchStore` was exercised read-only
  (`PGOPTIONS=default_transaction_read_only=on` with statement timeout) against
  **all 13 real Italian Garlasco benchmark questions**, including trigram
  misspellings. Expected genuine persisted IDs appeared within top five for
  **13/13 cases**. This is acceptance for the current *existing* private
  corpus/claim baseline, not a claim that DP-214 has 100 accepted Contents.
- **AC-415.3:** The MiniPC served private operator endpoint was exercised
  with a new, ephemeral, loopback-only server and ephemeral credential:
  invalid auth **401**, valid auth **200** with exactly two persisted matching
  atomic-claim ID rows, `private_only=true`,
  `publication_authority=false` and the strict ID-only response keyset.
  Public `web/dist` inspection found no private Garlasco identifiers or
  raw source/credential markers; unchanged public index HTML SHA-256 remains
  `60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0`.
  No separate public Studio surface was enabled.
- **AC-415.4:** MiniPC real PostgreSQL top-five benchmark rerun with
  `OMNIROUTE_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, and
  `ANTHROPIC_API_KEY` all removed from the process environment: **13/13**
  expected matches without a provider call or fallback.

**Integration/runtime evidence:** Source commit `54c906cc41255aa0ab613889235adee21ee1962c`
was pushed to `origin/main`. Seven changed source/test paths were promoted
to the existing non-Git MiniPC source mirror after verifying no running
private Studio listener; existing files were backed up in the private
`/home/udodo/src/.dpub-dp415-rollback-20261010-pre-54c906c` directory.
No public service restart, production SQL write, SQL migration or web build
replacement was performed. MiniPC checksum parity for the seven paths was
**7/7 MATCH**. MiniPC **31/31** focused Studio/identity Python tests passed
and the **actual MiniPC Chrome** keyboard/filtered-request/inspector/return
regression passed with `CHROME_BIN=/usr/bin/google-chrome`. Existing public
web and Cloudflare services remained active.

**Strict non-claims:** This ticket closes the private **search** workspace,
not DP-416 Collection→Capture→Passage→Candidate research navigation,
DP-417 triage writes, DP-419 rights-gated source-body/player preview,
DP-420 100-item operator usability, native screen-reader acceptance under
DP-410, qualified legal permission or public launch. Those continue to be
tracked in their distinct still-open tickets; no rights or reviewers were
invented and the production projection remains unchanged.

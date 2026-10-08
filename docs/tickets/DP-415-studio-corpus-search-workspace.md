# DP-415 — studio corpus search workspace

Status: IN PROGRESS
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

- [ ] **AC-415.1:** Keyboard-only user can query/filter/open/return while retaining state.
- [ ] **AC-415.2:** Known benchmark questions return expected top-K records.
- [ ] **AC-415.3:** Private result bodies never enter public build artifacts.
- [ ] **AC-415.4:** Provider offline state does not break lexical baseline.

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

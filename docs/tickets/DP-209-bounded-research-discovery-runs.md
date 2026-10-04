# DP-209 — bounded research discovery runs

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-113, DP-205, DP-206

## Problem

Existing polling discovers configured feeds/channels but cannot represent a bounded research question with multiple saved queries/seeds and auditable result provenance.

## Outcome

Add replayable Discovery Runs driven by persisted query manifests, bounded result/host/cost limits and adapter receipts; resolve hits into existing Content identity without crawling the open web unboundedly.

## Scope

- Version a Discovery Manifest with collection, seeds, queries, source families, date window, result/per-host limits and cost cap.
- Adapters may cover configured feeds/APIs/search providers; model-proposed queries must be persisted before execution.
- Persist every hit/disposition and link to existing/new Content idempotently.
- Use existing safe-fetch/network policy; discovery itself does not download arbitrary media bodies.
- Record provider errors/rate limits/budget blocks honestly.

## Non-goals

- No unbounded recursive crawler.
- No bypass of platform access controls/ToS.
- No extraction/promotion/publication in the discovery step.

## Dependencies and sequencing

DP-113, DP-205, DP-206

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-209.1:** Same manifest/config replay is idempotent at Content identity and preserves separate run receipts.
- [x] **AC-209.2:** Per-host/result/cost bounds are enforced in tests.
- [x] **AC-209.3:** Existing URL/content hits are marked EXISTING rather than duplicated.
- [x] **AC-209.4:** Provider failure yields blocked/partial receipt, not empty-success fiction.

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

Private runtime/queue/source adapters. Requires provider-specific credential/terms handling outside Git.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `8bbd77a` (`feat: add bounded research discovery runs`).

Implemented:
- immutable/versioned `research_discovery_manifest` + ordered query records, persisted
  before any adapter can execute; manifest identity is a canonical JSON SHA-256;
- separate run, attempt and hit ledgers with explicit `COMPLETED`, `PARTIAL`, `BLOCKED`
  and `FAILED` states instead of successful-empty fiction;
- every returned hit is persisted with a disposition (`NEW_CONTENT`,
  `EXISTING_CONTENT`, duplicate, host/result/date/policy rejection, or ambiguous identity);
- hard manifest/query/per-host/result/cost bounds and adapter cost upper-bound checks before
  provider invocation; actual receipts exceeding declared/capped cost fail closed;
- provider receipts and manifest/hit metadata reject credential/secret-like keys; unsafe
  result URLs persist only a hash and rejected disposition, never the raw unsafe URL;
- Content resolution uses canonical URL, configured source/external identity and existing
  `content_locator` identity under an advisory lock; accepted hits join the requested
  private Research Collection and add a locator when platform/external ID is available;
- provider-neutral adapter contract plus `configured_registry`, which reuses the existing
  YouTube/RSS/public-creator source adapters and their existing access/safety policy;
- metadata-only explicitly seeded creator records remain discoverable without browser
  cookies, authenticated sessions or media download;
- crash reconciliation converts a leftover RUNNING attempt to
  `ATTEMPT_RECONCILIATION_REQUIRED` and stops the run without making a second potentially
  paid/external call; safe resume state reconstructs URL/host/query/cost counters from
  durable receipts;
- CLI `tools/run_research_discovery.py`; five new private tables are in backup/restore
  load-bearing inventories; Public projection reads none of them.

Donor application:
- Loki/OpenFactVerification contributed the explicit query-planning boundary, not its
  verdict model or runtime architecture;
- Claim Polygraph contributed durable cost/idempotency/receipt patterns, reimplemented in
  the project domain rather than copied as a service;
- Miniflux/source-polling patterns remain bounded configured discovery; no generalized
  crawler or second scheduler was introduced;
- existing DP-205/206 Source Registry and adapters are reused rather than forked.

Local proof:
- focused DP-209 suite: **24/24 PASS**;
- complete suite: **846/846 PASS**;
- deterministic verification benchmark: **5/5 PASS**;
- compileall over `poc tests tools` and `git diff --check`: PASS.

Isolated MiniPC proof:
- `dp209_canary` was created from the pre-DP-209 production schema; migration applied and
  replayed idempotently; all five discovery tables read back;
- two SQL defects were found by the isolated tracer and fixed before production: psql
  variables inside `DO $$` did not interpolate, so manifest persistence was rewritten as a
  single atomic CTE statement; the hit replay CTE also lacked three RETURNING fields;
- configured creator fixture manifest hash
  `a83559b71025bf8a486ba4509572275239a7a7023e3cf2ca156dbe7f29190007`: first run
  `discovery-run:dp209:first` = 2 raw / 2 accepted / **2 NEW_CONTENT**; second distinct run
  `discovery-run:dp209:second` = 2 raw / 2 accepted / **2 EXISTING_CONTENT**; database
  contained 1 manifest / 2 runs / 2 attempts / 4 hit receipts / 2 Content / 2 collection
  memberships / 2 locators / **0 jobs / 0 claims / 0 evidence / 0 findings**;
- bounded canary `discovery-run:dp209:bounds:v2` returned `PARTIAL`: 3 attempts (1 healthy,
  1 blocked, 1 failed), 4 raw hits, 2 accepted, 2 rejected; hit dispositions proved
  `HOST_LIMIT` and `RESULT_LIMIT`; provider failure persisted `RATE_LIMITED`; a 0.60 USD
  declared upper bound against a 0.50 USD cap persisted `COST_CAP_PRECALL` and the costly
  adapter was called **0 times**;
- crash canary left one attempt RUNNING, replay reconciled it to BLOCKED
  `ATTEMPT_RECONCILIATION_REQUIRED`, overall run BLOCKED, provider calls **0**;
- isolated schema was dropped before the production backup.

Production proof:
- pre-migration baseline: 14 Source / 49 Content / 52 Locator / 0 Research Collections /
  112 Processing Jobs / 30 Atomic Claims / 17 Evidence / 9 Verification Runs / 9 Findings /
  2 PUBLISH; data digest `5276d4c96914381a116974981a635c30`;
- pre-migration backup `20260929T102921Z`: readable **10,062,396-byte** dump;
- migration applied with `ON_ERROR_STOP` and replayed idempotently; all five new tables
  began at zero and every legacy count plus the digest remained unchanged;
- production metadata-only canary used only reserved `.example` URLs: run 1 created 2
  Content; run 2 resolved the same 2 as EXISTING; jobs stayed 112, claims 30, evidence 17,
  verification 9, findings 9 and PUBLISH 2 throughout;
- cleanup removed all canary manifest/run/attempt/hit/collection/content rows and restored
  the exact digest `5276d4c96914381a116974981a635c30`;
- final MiniPC suite: **846/846 PASS**; verification benchmark **5/5**; corpus-search
  benchmark **13/13 Recall@5**, p95 48.295 ms;
- post-migration backup `20260929T103100Z`: readable **10,083,230-byte** dump, 10 valid
  backup sets retained, manifest includes all five discovery tables at count 0 after
  cleanup.

No open-web recursive crawler, browser-cookie path, media body download, model authority,
claim/evidence/verification/finding creation, or public side effect was introduced. Future
search/API adapters must use this same persisted-manifest/cost/receipt contract.

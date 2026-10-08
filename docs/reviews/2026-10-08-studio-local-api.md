# Studio: on-demand read-only loopback API acceptance (2026-10-08)

## Candidate boundary

This tranche adds an **explicitly started** 127.0.0.1-only, token-authenticated,
read-only operator HTTP API and login shell. It is intentionally separate from
the public Astro build, public HTTP API, Cloudflare edge and systemd runtime.
It is not a public/admin mutation surface. Nothing is published, reviewed,
promoted, accepted as legal clearance or authorized by this API.

Exact routes are Corpus search, paginated Collections, paginated Discovery,
persisted candidate-match inspection and two-capture metadata comparison.
Only bounded safe IDs, captured hashes, lifecycle states, feature codes
and enumerated blocker reasons leave the PostgreSQL read layer. No raw
transcript, source body, private source URL, model answer, candidate text,
provider credential or arbitrary metadata appears in response bodies.

The login HTML shell contains no secrets or persisted private material.
It uses a per-response strict CSP nonce, no external assets or storage,
an in-memory token field, same-origin bearer POST, and DOM textContent
for receipts, without HTML insertion. The API rejects unrecognized Host,
cross-Origin, cookies, unauthorized credentials, excess body data,
unknown paths, write verbs, invalid schema and noncanonical/stale rows.
Owner-only token files are refused when missing, symlinked, readable by
group/others or invalid. PostgreSQL is forced transaction-read-only
with 3-second connect/statement budget and an 8-second subprocess limit.

## Local and MiniPC tests

- Full local Python unit/regression suite: **1848/1848 PASS**.
- Focused local read-only Studio API/queues/search/capture/match: **26/26 PASS**.
- Isolated MiniPC source bundle and HTTP/mock test suite with provider/DB
  environment cleared: **26/26 PASS**, then deleted.
- Real MiniPC PostgreSQL connectivity (read-only): **PASS**. Verified
  research_collection COUNT = **0**; no real Garlasco collection is
  being claimed.
- Real MiniPC loopback canary: disposable token and port 0, no persistent
  process/service/DB write. Unauthenticated call returned **401**;
  authenticated collections, discovery and corpus/search returned **200**
  with **0 result references** each. Every receipt indicated
  publication_authority=false. Process was terminated and temp source/token
  deleted.
- Compileall, contributor acceptance, repository ticket/licensing contract,
  deterministic claim/evidence benchmark **5/5** PASS.
- Launch preflight **NO-GO, 41 blockers** (unchanged).

## Exact remaining blockers

The MiniPC real-data probe proves access and empty datasets, **not**
a successful recall benchmark or full operator task. DP-415..419 remain
IN PROGRESS. Missing: approved Garlasco persisted collection/corpus,
Garlasco top-K recall, collection→source→passage→candidate navigation,
rights-gated preview, durable review/currentness and replay authority,
explicit operator roles before expanding beyond local read-only scope,
browser/screen-reader/200%-zoom/manual acceptance and launch legal review.

No new migration, asset/dependency/license, public route, reverse tunnel,
systemd service, database mutation, or production projection is introduced.
The source mirror can be synchronized independently of public deployment.

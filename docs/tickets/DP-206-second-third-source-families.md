# DP-206 — Add second and third source families without code duplication

Status: DONE
Milestone: M2  
Depends on: DP-205 and the existing source registry, queue, transcript, and source-health contracts

## Problem

The current discovery path is centered on `youtube_channel`. It contains reusable
podcast-RSS parsing, but the RSS feed is only a preference inside a YouTube source;
the registry's `public_creator_accounts` entry is explicitly unsupported. As a
result, adding a source family would encourage a second scheduler, a second queue
path, or a second copy of URL validation, deduplication, and health logic.

The next source families must be adapters over the same domain contracts. This
ticket is about adapter reuse and coverage, not about selecting a new political
source or expanding the product's editorial scope.

## Outcome

Expose three first-class discovery families through one narrow adapter contract:

1. the existing `youtube_channel` family;
2. a standalone `podcast_rss` family; and
3. a `public_creator_accounts` family for already-configured public creator metadata.

All three must produce the same normalized `DiscoveredContent`, use the same
source-health, content/locator, deterministic enqueue, budget, and private-receipt
paths, and preserve source-family identity for audit and deduplication. No family
may bypass the shared queue or materialize a downstream job that is not executable.

## Dependencies and authority

Use [PRODUCT.md](../../PRODUCT.md), [CONTEXT.md](../../CONTEXT.md),
[ARCHITECTURE.md](../../ARCHITECTURE.md), and [PLAN.md](../../PLAN.md). The relevant
existing implementation seams are `poc/dichiarazioni_pubbliche/source_watcher.py`,
`poc/dichiarazioni_pubbliche/scheduler.py`, `poc/dichiarazioni_pubbliche/scheduler_daemon.py`,
`poc/dichiarazioni_pubbliche/platform_transcript.py`, `config/source-registry.v0.json`,
and `tests/test_source_watcher.py`. The source-discovery and audio-first decisions
in `docs/19-deployment-scaling-sources-and-ux.md` and
`docs/22-runtime-scheduler-and-omniroute-canary.md` are supporting evidence, not
new authority.

DP-205 must provide the full-source run and shared run/health contract before this
ticket changes adapter behavior. DP-201 through DP-204 remain externally blocked;
adapter acceptance must not call a live claim, ASR, or publication provider.

## Scope

### 1. One adapter seam

Create a small adapter module, preferably `poc/dichiarazioni_pubbliche/source_adapters.py`,
and keep `source_watcher.py` as the compatibility façade for existing callers. An
adapter must provide only:

- a stable family/kind identifier;
- bounded `discover(source, limit)` behavior returning `DiscoveredContent` values;
- source-family-specific ingestion planning that returns the existing scheduler
  actions; and
- sanitized error categories for unsupported, access-restricted, policy-rejected,
  transient, and malformed responses.

Keep the shared `DiscoveredContent` contract, HTTPS/DNS/redirect/size validation,
normalization, `filter_discovered_content`, `provisional_content_key`,
`cluster_discoveries`, `plan_initial_job`, `PsqlStore.upsert_content`, and
`enqueue_processing_job` paths shared. Do not add a family-specific scheduler,
queue table, or copy of the health implementation.

### 2. First-class `podcast_rss`

Reuse `parse_podcast_rss()` and the existing podcast ingest plan. A standalone RSS
source must normalize:

- stable GUID or equivalent external ID;
- canonical item/media URL;
- title, author, publication date, description/chapter metadata, duration, media
  type, and audio URL when the feed supplies them; and
- `platform="podcast_rss"` with bounded values.

The RSS adapter must not download media during discovery. It may enqueue the
existing cheap transcript-resolution step, which can prefer a platform caption and
fall back to the existing URL-first ASR lane only when the capability and cost gates
permit.

### 3. First-class `public_creator_accounts`

Reuse the existing registry entry and its public-post policy. The adapter must use
only explicitly configured public metadata/discovery surfaces and stable public
post IDs. It must normalize `platform="instagram"` or `platform="tiktok"`,
post ID, canonical URL, publication timestamp, title/description, and bounded media
metadata. It must not require browser cookies, private sessions, credentials, or a
new political source selection. Access-restricted or unsupported posts become an
explicit blocked source result, not a successful empty result.

### 4. Cross-family identity and scheduling

- Keep the same `source_id`, locator uniqueness, content clustering, and
  deterministic job-ID rules across families.
- A cross-post that resolves to the same content must add a locator and an
  alternate-platform reference without creating a second public Content record when
  the existing cluster contract proves it is the same item.
- Every family must pass through DP-205's per-source/full-run limits and cost
  gates.
- The adapter result must retain `source_kind`/family metadata without treating a
  platform as domain identity.

## Non-goals

- adding a political source, person, party, or editorial ranking;
- browser automation with real cookies or a generalized social crawler;
- private or deleted-content retrieval;
- downloading or retaining video/audio in the discovery adapter;
- implementing a new transcript, claim, evidence, verification, or publication
  provider;
- changing the public schema or exposing raw platform responses; and
- introducing a new queue, database technology, or service boundary.

## Acceptance criteria

- **AC-206.1 — Three-family registration:** The registry can represent and dispatch
  `youtube_channel`, `podcast_rss`, and `public_creator_accounts` through the same
  adapter lookup, and an unknown kind is explicit `UNSUPPORTED`.
- **AC-206.2 — Shared contract:** A parameterized contract test runs against all
  three families and proves normalized fields, URL policy, bounded limits, source
  health, content/locator upsert, and deterministic enqueue use the same seam.
- **AC-206.3 — RSS behavior:** A podcast RSS fixture preserves GUID, publication
  date, duration, description/chapters, and media URL; discovery performs no media
  download and selects the existing audio-first plan.
- **AC-206.4 — Creator behavior:** A public creator metadata fixture yields stable
  platform/post identity and bounded metadata. Missing, private, or restricted data
  is blocked/rejected without credentials, cookies, or a fabricated content item.
- **AC-206.5 — Cross-post identity:** The same item discovered through two families
  or platforms produces one canonical Content identity and the expected locators;
  replay does not create duplicate jobs.
- **AC-206.6 — Replay and drift:** Replaying an identical feed is idempotent, while
  a changed stable ID or materially changed metadata is versioned/upserted without
  silently widening provenance. A missing publication timestamp cannot collapse
  distinct posts.
- **AC-206.7 — Capability and budget gates:** The adapter can discover and persist
  safe metadata while claim/ASR children remain absent or blocked when the
  downstream capability, credential, or cost cap is unavailable.
- **AC-206.8 — Security:** HTTPS, public-DNS, redirect, userinfo, response-size, and
  timeout checks are shared and tested; no secret, cookie, raw body, or transcript
  enters Git, the queue payload, or public output.
- **AC-206.9 — Regression:** Existing source, scheduler, transcript, queue, and
  runtime-policy tests remain green; focused adapter tests and deterministic
  benchmark pass.
- **AC-206.10 — Runtime proof:** MiniPC source health and full-source receipts show
  one bounded success or explicit block for each family without a live semantic
  provider call.

## Test-first seams

Test through the adapter and persistence boundaries, not parser internals:

1. the shared `discover_source()`/adapter contract for each family;
2. `DiscoveredContent` normalization and existing `cluster_discoveries()` for
   cross-family identity;
3. `poll_source()` and the PostgreSQL store for health, replay, and queue behavior;
4. the existing `PrivateTranscriptStore` boundary to prove discovery does not retain
   media or raw platform responses; and
5. the DP-205 full-source run receipt for per-family coverage.

Use one vertical slice per family. Each slice must first add a red public-contract
test, then the smallest adapter change, then green; do not write all family-specific
helpers before the shared contract is proven. Include SSRF, private IP, userinfo,
oversized feed, malformed XML/JSON, missing stable ID, access restriction,
cross-post, changed metadata, and provider-blocked cases.

## Runtime proof

On the MiniPC, after DP-205's migration and receipt path are available:

1. synchronize the adapter implementation and config to
   `/home/udodo/src/DichiarazioniPubbliche.it`;
2. run the focused tests and the standard checks:

   ```text
   python3 -m compileall -q poc tests
   PYTHONPATH=poc python3 -m unittest discover -s tests -v
   PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
   git diff --check
   ```

3. use bounded, authorized public metadata/feed fixtures or approved canary
   endpoints to exercise one item per family; do not use a live claim, ASR, or
   evidence provider;
4. run the DP-205 full-source mode twice and verify per-family source health,
   locators, deterministic job IDs, zero duplicate jobs on replay, and no new child
   jobs for blocked downstream capabilities;
5. inspect `source_poll_run`, `source_poll_run_source`, and the private health digest
   for the three family results; and
6. verify the MiniPC timer/service exit status and that the queue contains only
   executable cheap first steps.

The receipt must record fixture/canary hashes, family/kind, discovered/upserted/
enqueued/duplicate/blocked counts, source-health transitions, MiniPC commit/mirror
hash, and test output. Mac evidence is not sufficient.

## Blocked conditions

Classify the ticket or affected family as `BLOCKED` when:

- a family has no stable public identifier or canonical URL policy;
- discovery requires credentials, cookies, private access, or an unapproved
  browser session;
- a platform's terms, rate limit, or access policy cannot be respected;
- the shared adapter seam cannot preserve source-family metadata and timestamp
  provenance;
- a source response cannot be bounded and validated before parsing;
- DP-205's run/health/queue proof is unavailable; or
- implementation would require copying the scheduler, queue, or health pipeline.

A family-level block must not stop unrelated families, and it must never be reported
as a successful empty source or cause an automatic fallback to another provider.

## Documentation, data, and migration impact

- Update `config/source-registry.v0.json` only with explicit family metadata,
  discovery URLs, policies, and bounds; do not add credentials or private URLs.
- Add adapter contract documentation to `docs/22-runtime-scheduler-and-omniroute-canary.md`
  and the source section of `docs/19-deployment-scaling-sources-and-ux.md`.
- Reuse existing `source`, `content_item`, `content_locator`, `source_health`, and
  queue tables. Store family/version metadata in existing metadata fields or the
  DP-205 run receipt; avoid a new domain table unless a measured invariant requires
  it.
- No public schema migration is expected.

## Completion receipt

To be filled only after implementation and proof:

- adapter seam and changed existing paths:
- family fixtures/canary hashes and effective registry hash:
- per-family discovery/upsert/enqueue/duplicate/blocked counts:
- cross-post identity and replay evidence:
- focused/full tests, benchmark, and `git diff --check`:
- MiniPC mirror hash, timer/service receipts, and health-digest path:
- license/terms/access decisions and residual blocked families:

## Recorded implementation proof

- `source_adapters.py` now provides one normalized contract for `youtube_channel`,
  `podcast_rss`, and `public_creator_accounts`, with the existing watcher retained as a
  compatibility façade.
- Public creator discovery is metadata-only: no browser cookies, private sessions, media
  download, or authenticated platform calls. Missing identifiers, SSRF shapes, restricted
  visibility, unsupported platforms, and policy rejection fail closed.
- Cross-post identity remains deterministic; RSS discovery is metadata/audio-URL only.
- A bounded public creator canary fixture was discovered on the MiniPC runtime authority.
  It contains no transcript or claim/finding and remains private collection material.

## Three-family MiniPC canary receipt

The MiniPC isolated-schema canary ran the three configured source families without
provider, ASR, claim, or publication work:

- YouTube Pulp: 1 discovered, 1 upsert, 1 `TRANSCRIPT_RESOLVE_PLATFORM` job;
- podcast RSS Pulp: 1 discovered, 1 upsert, 1 duplicate job;
- creator metadata fixture: 2 discovered, 2 upserts, 2 `CONTENT_TRIAGE` jobs;
- total: 3 canonical `content_item` rows, 4 locators, 3 jobs, 0 claims, 0 findings;
- Pulp episode 64 resolved to one canonical content row with both
  `youtube` and `podcast_rss` locators;
- replay produced the same 3/4/3 counts and created no additional jobs;
- the isolated canary schema was dropped and the worker timer was restored afterward.

# DP-409 — Public search and static indexing without new infrastructure

Status: IN PROGRESS

Milestone: M4 — public product/API
Depends on: DP-402, DP-403, DP-405, DP-406, DP-407, DP-408, DP-425

## Problem

Explore needs useful search as the public corpus grows, but the product must not introduce
a search service, vector database, provider call, or live LLM merely to retrieve records.
Search must search already-published public records, preserve provenance boundaries, and
remain understandable when a query has no match or the index is unavailable.

DP-409 is deliberately after the public templates. It is a bounded retrieval/indexing
contract, not a second source of truth.

## Outcome

Generate a deterministic, public-safe search artifact from the approved public
projection/API and let the Explore/search UI query it locally. Search results are linked
rows, not model answers. If a future corpus or latency measurement proves the static
artifact insufficient, open a separately benchmarked ticket rather than silently adding
infrastructure.

## Contract gate

- **DP-105** must ratify the public fields, stable IDs, correction/reply/relation
  semantics, and the v1/v2 compatibility decision;
- **DP-402/DP-403** must define any public resource links and version metadata;
- **DP-405..DP-408** must establish the record and route vocabulary before the index
  duplicates it;
- **DP-425** owns the final v4 shared presentation tokens; search must use the same
  `SearchField`, `ClaimRow`, `Assessment`, and `SourceRow` contracts.

The current operational projection is `dichiarazioni-pubbliche-public-v2`; no index may be published
as stable v1 until DP-105 closes.

## Scope

### Static index artifact

Generate a versioned artifact such as `/search-index.v1.json` or the path ratified by
DP-105. Each record contains only bounded public-safe fields:

- stable record and finding IDs;
- record kind (`finding`, `content`, `person`, `topic`, or the DP-105 vocabulary);
- claim/original wording or bounded public label;
- speaker/public-role context when approved;
- topic labels and source title/publisher when present;
- publication/statement date;
- written assessment;
- canonical public route;
- correction/reply indicator that points to the public finding history.

The artifact must exclude draft/held findings, unreviewed relation candidates, private
replies/corrections, raw transcript/evidence bodies, provider receipts, internal errors,
credentials, person scores, ranking fields, and arbitrary model output. Its schema,
normalization rules, and generation timestamp are explicit and versioned.

The artifact must be generated atomically from the same projection fingerprint used by
the frontend. A failed or incompatible projection build must not leave a previous index
reachable as current.

### Query behavior

- query input is bounded to 200 Unicode characters after normalization;
- empty query returns the default Explore result order, not a fabricated “no results”
  answer;
- matching is deterministic and case/diacritic-insensitive over an allowlist of public
  fields;
- ranking is record-level and deterministic: exact phrase, claim/original wording, then
  source/topic metadata, with stable ID tie-breakers;
- no semantic embedding, LLM, generic web search, or person ranking is used;
- no query is sent to a provider or written to raw telemetry logs;
- query/filter/sort state is represented in the URL and is restorable;
- result rows link to the canonical public route and never expose a hidden operational
  detail;
- filters are bounded and use the same Explore/Record vocabulary as DP-405..DP-408;
- mobile uses one visible `Filtri` control and a sheet, not a permanent filter wall.

A static index may be shipped as a compressed public asset. A server-side search endpoint
is not required for v1. If a later ticket adds one, it must return the same IDs and order
as the artifact and must not become a new data source.

### Required states

| State | Required behavior |
|---|---|
| Default query | Show the approved recent/public Explore order with a clear search field. |
| Matching results | Show claim-first `ClaimRow` results, written finding state, source/date, and a direct route. |
| No matches | Explain that no published record matches, preserve the query and filters, offer reset/Explore paths, and do not suggest a new live analysis. |
| Query too long/invalid | Keep the page usable, announce the bounded-input requirement, and do not send a request or index update. |
| Index missing/stale/incompatible | Fail closed to a deliberate unavailable state; do not silently use demo data or a stale index. |
| Filter transition | Preserve query and active-filter count, keep focus in the search/filter control, and announce result updates. |
| Offline/provider outage | Search the existing static artifact normally; do not show a provider error or invoke an LLM. |

## Non-goals

- Elasticsearch, Solr, Meilisearch, a vector database, a graph database, or a hosted
  search product;
- semantic, fuzzy, embedding, RAG, or LLM query interpretation;
- crawling the whole web or searching private/held/operational records;
- public writes, live analysis, chatbot search, or an API key;
- changing the public schema or adding fields to the operational database solely for
  search;
- person/party ranking, “most checked”, or political recommendations;
- indexing raw transcript/evidence bodies;
- a second API contract or a server-side search endpoint without a measured need.

## Dependencies and gates

- **DP-105:** hard public fields, IDs, safety, and compatibility gate;
- **DP-402/DP-403:** resource links, examples, and version metadata;
- **DP-405..DP-408:** canonical result vocabulary and route ownership;
- **DP-425:** shared v4 search/result component and token contract;
- **DP-401:** static asset hosting and freshness proof;
- **DP-410:** cross-surface accessibility, performance, and SEO gate;
- **ADR 0001/0002:** projection-only reads and no LLM request path.

## Traceability & constraints

- **Traces to:** US-36-05, US-36-07, DEC-36-06, AC-36.6, AC-36.8, AC-36.10.
- **Constraints:** deterministic public-safe local retrieval; no hosted search/vector/LLM
  dependency by default; no private/raw fields; canonical route targets only.

## Acceptance criteria

- [x] `AC-409.1`: Given an approved public projection, when the index is generated, then
  it contains only the allowlisted public fields, stable IDs, canonical routes, and a
  projection fingerprint, with no private/raw/provider/score data.
- [x] `AC-409.2`: Given the same projection and normalization rules, when the index is
  generated twice, then the canonical bytes/fingerprint and result ordering are stable.
- [x] `AC-409.3`: Given a valid query and active filters, when a user searches, then
  results are deterministic, bounded, public, and linked to the canonical route without
  a provider or LLM call.
- [x] `AC-409.4`: Given no match, an empty query, an overlong query, or a filter
  transition, when the UI responds, then it provides the documented empty/validation/
  focus state and never invents a result or analysis offer.
- [x] `AC-409.5`: Given the index is missing, stale, tampered, or built from an
  incompatible schema, when the site is built or opened, then it fails closed and does
  not serve a previous artifact as current or fall back to demo data in production.
- [x] `AC-409.6`: Given corrections, replies, or relation links, when a matching record
  is rendered, then its indicator links to the version-aware public history and does
  not imply a new publication event.
- [x] `AC-409.7`: Given providers are offline, when a user searches the static index,
  then existing public records remain searchable and no live retrieval is attempted.
- [ ] `AC-409.8`: Given keyboard, screen-reader, mobile, 200% zoom, and reduced-motion
  use, when search and filters are operated, then focus, labels, result count, and
  selected state are perceivable and usable.
- [x] `AC-409.9`: Given the collision/dependency audit runs, then DP-409 owns only the
  static search artifact/behavior and does not duplicate DP-402/DP-403's resource
  contract.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

Run deterministic index tests for: no records, one record, exact phrase, diacritics,
punctuation, overlong query, all filters, result ordering, correction/reply links,
projection change, stale artifact, and invalid schema. Compare the generated artifact's
hash and a sample of results across two clean builds.

Measure the representative static corpus and record compressed artifact size, build time,
and local query time. Keep the v1 artifact within 1 MiB compressed and local matching
within 100 ms at the agreed fixture corpus size; if either bound is exceeded, stop and
benchmark a separate design instead of adding infrastructure inside this ticket.

Exercise Explore on phone and desktop, keyboard-only, screen reader, 200% zoom,
reduced motion, empty results, and missing-index failure. Verify query text is not sent
to a provider or emitted in raw logs.

Runtime-affecting completion requires the index and Explore route to be served from the
MiniPC deployment mirror through DP-401 with the approved projection. Record the artifact
fingerprint, size, local timing, representative result IDs, and offline behavior.

## Documentation, data, and migration impact

- document the static index schema, normalization, query limits, and no-infrastructure
  rule with DP-402/DP-403;
- update `llms.txt` only with one link to the index/search documentation after this
  ticket is stable;
- no database migration is introduced;
- no API route is added by default;
- do not edit `PLAN.md`.

## Completion receipt

Local implementation exists as `search-index.v1.json`: deterministic build material derives
only from the approved public projection, carries the projection SHA-256 plus its own
SHA-256, and is revalidated client-side before use. Search normalization is bounded to 200
characters, case/diacritic-insensitive and deterministic across finding/person/topic/content
records. Explore no longer searches full dossier objects directly and never falls back to
demo/stale data when the asset is unavailable or mismatched. The local fixture check covers
ranking, filters, diacritics, overlong input, correction/reply indicators and tamper/stale
rejection; two consecutive demo builds produced identical artifact SHA-256
`4e67d7d23be8137d4b8a8e67b4bcd6a717e2e6ebf49d5c19ba2fbe0ba64c2cd0`. The demo artifact
is 5,168 bytes raw / 1,199 bytes gzip. Astro check, design check and static build pass.

`npm run check:browser` now exercises the rendered Explore route in local headless Chrome:
empty-query hydration, no-match recovery, overlong-query `role=alert`, keyboard radio
transition with retained focus and URL serialization, dialog open/Escape/focus return,
reduced-motion media emulation, 375 px mobile reflow, and a 640 px 200%-equivalent reflow
viewport all pass. The corrected/replied result indicator is also required to target the
Statement `#storia` history anchor. This closes AC-409.4 locally. AC-409.8 remains open for
actual screen-reader/manual accessibility judgment. The browser checker now also launches a separate Chrome 154
profile with an exact per-host zoom factor of `2.0`: a 1280 px outer window becomes a 640 px CSS
viewport, `devicePixelRatio` is `2`, `visualViewport.scale` stays `1` (so this is browser zoom,
not pinch/page scaling), and Explore keeps zero horizontal overflow, a 44 px filter target and a
visible search field. The same proof passes on MiniPC Chrome 150 with `innerWidth=640`,
`scrollWidth=635` and the 44 px target. The 640 px reflow-equivalent check remains as a separate
resilience test.

On 2026-10-06 the current tree was also built on MiniPC against the exact approved projection at
`~/.local/share/dichiarazioni-pubbliche/public/v1/index.json` (fingerprint
`501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`) and served from an isolated
loopback adapter. `/`, `/esplora/`, `/metodo/`, `/search-index.v1.json`, `/api/v1/health` and
`/api/v1/openapi.json` all returned `200`; the approved projection is currently empty, the search
artifact correctly contained zero records, and search/API carried the same fingerprint. A separate
read-only check of the live DP-401 service found its static `web/dist` still built from demo
fingerprint `00ede66707f0...` while the live API reads approved fingerprint `501348d9638e...`, and
`/linked-data-receipt.json` returns `404`; that path is not part of the public contract because the
receipt is the private sibling used to validate the public `/index.nt` export.

The final 2026-10-06 production promotion rebuilt both projection and static output from the same
approved fingerprint. Live API health, `search-index.v1.json` `projection_sha256`, and the internal
linked-data receipt now all equal `501348d9638e...`; `/index.nt`, `/`, `/esplora/`, `/metodo/`,
`/robots.txt`, `/sitemap.xml` and the public API return `200`. The approved projection is empty and
the search index correctly has zero records. `check-public-quality` passes the real production
bundle with 6 HTML documents, 6 sitemap URLs, `index,follow`, and the JavaScript budget intact.
The browser QA now accepts that exact approved-empty state without weakening the populated fixture:
it scans the six emitted routes, hydrates Explore at zero results, exercises keyboard filter/dialog
flows, reduced motion, phone reflow and exact 200% browser zoom, and records zero external/provider
requests. Populated demo acceptance still requires the correction-history link and all populated
route families. AC-409.8 remains open only for actual screen-reader/manual accessibility judgment;
the live-static promotion blocker is closed. Dependency gate DP-408 remains authoritative.

## Post-grilling planning reconciliation — 2026-10-10

Remain IN PROGRESS. The public search index must use first-class Statement IDs, exact approved quote and locator as primary display while explicitly distinguishing summary/translation metadata (DP-436), plus approved zero-record Persons (DP-438) and safe Person×Topic intersection (DP-439). Revoked or private membership must be absent from results, facets, cursor and snippets; empty corpus, populated no-match and stale index are distinct. Existing keyboard/screen-reader AC-409.8 remains OPEN. All historical AC checkboxes and dated receipts preserved; no runtime change or acceptance inferred from this planning update.

### 2026-10-11 — Populated search count/status accessibility hardening

`ExploreClient` now exposes live result counts with atomic `role="status"`
semantics. An overlong URL-provided search announces `Ricerca non eseguita`,
never a misleading `0 risultati`; the existing `role="alert"` still explains
the 200-character bound. Filter open/close state is visible through
`aria-controls`/`aria-expanded`. Isolated Astro regression verifies both
approved-empty and explicitly local populated demo builds. Browser QA verifies
the accessible state, keyboard dialog disclosure, Escape, invalid query,
reduced motion and true 200% browser zoom; no external/provider requests.
`npm run check:search` PASS, Astro check 0 diagnostics and `git diff --check` PASS.

**AC-409.8 remains unchecked:** browser accessibility-tree inspection does not
constitute a real screen-reader/manual assistive-technology acceptance.
DP-408/dependency gates remain. This receipt documents source and local test
evidence only; no new MiniPC/public release or owner sign-off is inferred.

### 2026-10-11 — Standalone opt-in original-Statement search over DP-439 (source-only)

**New isolated artifacts only:** `web/src/lib/publicStatementSearchV3.ts`
and `web/scripts/check-public-statement-search-v3.mjs`. Neither module
is imported by the running public-v2 Explore implementation, writer,
routes, API, index generator, or production asset manifest. No provider
or network request is performed. The v2 Finding/paraphrase index and
its existing AC receipts remain unchanged.

The new pure static builder consumes the actual *precomputed* DP-439
first-class opinion Statement × independently reviewed Person ×
separately approved Topic intersection. It **rejects v2** and requires
three exact independently provided current release fingerprints:
DP-439 intersection, source Statement-v3, and approved Person-v3.
Before building, it recomputes the Python DP-439 canonical material
SHA-256 (including status, count and approved rows) using sorted-key
canonical UTF-8 JSON. It does **not** issue or authorize any of these
fingerprints. The returned versioned public-safe artifact has a
separately pinned `index_sha256`, which its validator requires from
the authenticated release manifest (not copied from the artifact).
Rehashing a forged browser asset does not make it an authorized release.

Each public Statement appears **once**, even when separately reviewed
membership attaches two Topics, with its distinct approved Topic ID
facets and canonical Topic routes. The allowlist preserves public
Statement/Person stable IDs and canonical routes, original verbatim
text, language, quote SHA-256, exact written/timed locator, published
source Content ID/title/URL/version/source SHA-256, dated original
record and nullable Finding reference. Secondary search terms are
restricted to the **already published Person name and source title**.
It does not index inferred Topic labels, statement summaries,
translations as source quotations, private membership/review rows,
provider receipts, factual assessments, political/person scores, or
private corpus bodies. The materializer checks original quote bytes
against the pinned quote hash, rejects unsafe cross-origin Statement
URLs and invalid locators, and keeps a disjoint snapshot of source
objects. It never computes a factual verdict from an opinion.

Pure `serializePublicStatementSearchV3Url` and
`parsePublicStatementSearchV3Url` retain shareable `q`, `persona`,
`tema`, and `ordine` without duplicate/unsafe URL parameter
acceptance. `searchPublicStatementsV3` revalidates the pinned static
asset on every query, then applies exact Person/Topic intersection
and bounded 200-codepoint normalized-search vocabulary. Empty query
uses stable recent order; matching is case/diacritic-insensitive over
original words first and approved source/person labels second, with
deterministic date/Statement-ID tie breaking. It distinguishes
`NO_MATCH`, `QUERY_TOO_LONG`, `EMPTY_PUBLIC_CORPUS`, and
`EMPTY_PUBLIC_INTERSECTION` from a stale/unavailable index that
throws instead of using demo data or an old artifact.

**RED→GREEN proof:** the Node checker first failed with
`ERR_MODULE_NOT_FOUND` for this new, previously nonexistent search
module. It now invokes Python's *actual* independent DP-439 synthetic
fixture, receives **4 reviewed Person×Topic rows** and builds **3
unique published original Statement hits**, verifies one two-Topic
Statement, date ordering, URL roundtrip, original-text/source search,
multi-Person and two similar Topic IDs, homonym-proof stable IDs,
missing/private matches, overlong query, disallowed Topic label
inference, no private data keys and byte-identical replay. It uses
an additional real Python five-gate synthetic original with
accented characters, literal tabs/newlines, and leading/trailing
quotation spaces to verify **byte-for-byte verbatim preservation**
and separate diacritic-insensitive lookup (search never normalizes
the displayed original). It uses
real upstream Python synthetic re-projection after rights revocation
to confirm the fresh source contains **2 results**, that the old
asset/source fingerprints fail with new external pins, and that the
empty approved public corpus remains distinct from a populated corpus
with zero authorized intersections. Tampered quote, forged Topic
membership and cross-origin route mutations fail; the checker also
**rehashes** those malicious assets and confirms the independent
release digest still rejects them. This is a **local technical test
fixture**, never an actual rights/publication authority.

Observed local test metrics: approximately **3,023 UTF-8 bytes raw,
909 bytes gzip**, and **0.2 ms/query** for the synthetic three-hit
fixture, well under the static-artifact budget. The new checker runs:
`cd web && node --experimental-strip-types
scripts/check-public-statement-search-v3.mjs`.
`cd web && npm run check` reports **0 errors, 0 warnings,
0 hints**; `git diff --check` passes. These measurements are not a
representative large-corpus performance benchmark.

**DP-409 remains IN PROGRESS; AC-409.8 remains unchecked.** Historical
AC-409.1–.7 and .9 checked evidence describes the existing public-v2
functionality and is not silently promoted into v3 acceptance. A real
independently authenticated current DP-439 release/asset manifest,
atomic static upload and withdrawal propagation, integrated v3
Explore/Person/Topic route and browser-back/focus/a11y support,
real mobile VoiceOver/200% zoom, representative corpus size/latency
and MiniPC positive/negative readback remain external. No frontend
consumer activation, production, MiniPC, commit or push occurred.

### 2026-10-12 — Independent pinned static withdrawal reader (opt-in only)

`web/src/lib/searchIndex.ts` now exports `readPinnedPublicSearch` and its
`PinnedPublicSearchRelease` input, without altering `validateSearchIndex`,
`searchPublicIndex`, the public-v2 Explore consumer, v3 DP-439 reader, build
route, or existing release behavior. This is an optional read-through contract
for a host that **independently supplies authenticated, current** release
pins: release ID, monotone epoch, exact projection and index SHA-256,
generation time, expiry and explicit opt-in. It checks the static JSON's
existing schema/derived digest and *additionally* requires the separately
pinned index digest; it verifies the host's current pins **before and after**
query computation and fails closed if any component changes, is missing, or
expires. It never derives its current pin from the untrusted cached asset.

This addresses a distinct verified gap: the historical public-v2
`validateSearchIndex(index, expectedProjectionSha256)` intentionally lacks
an **independent index digest**. A syntactically valid old public finding,
person, content and topic list can be copied under a newer projection SHA,
self-rehashed using `finalizeSearchIndex`, and still pass that legacy
validator because the routes/facets are internally coherent. The opt-in
reader refuses those mixed-release search hits via the independent digest.
The legacy API remains compatible for its existing historical consumers;
the new path requires an actual external pin reader.

**Executable RED→GREEN:** first execution of
`cd web && node --experimental-strip-types
scripts/check-search-withdrawal-next.mjs`
failed with missing `readPinnedPublicSearch` export. After implementation it
passes, building **two real isolated Astro output directories** from
synthetic, non-demo public-v2 projection files with SHA-256 calculated over
the canonical source material. The first build publishes one fictional
finding and its Person search result; the second withdraws the finding
(zero results). Both real `search-index.v1.json` files have distinct
projection/index digests. The test proves that the original validator
accepts a rehashed old-record payload under the new projection SHA, while
the pinned reader refuses that payload, the actual stale old artifact and a
mixed, self-consistent old-record/new-metadata asset. It also checks
current empty read, deterministic historical snapshot, interrupted
two-read pin rotation, changed epoch despite identical digests, missing
host authority, expired pins and unavailable host authority. Isolated
build output and fixture projections are deleted afterwards; no production
source, host or cache was accessed.

The adjacent `check-search-index.mjs`,
`check-public-statement-search-v3.mjs` and
`check-private-person-topic-v3.mjs` all pass; `npm run check` reports
0 errors/0 warnings/0 hints. This remains a **local source-only reference**:
neither the current public-v2 browser nor an operational DP-439 consumer
calls it. It cannot prove atomic CDN deployment, a future rights revocation
after its final pin read, HTTP byte-delivery/edge-cache withdrawal, signed
independent release authority or MiniPC latency. Those require DP-320/518
and host/edge integration. **DP-409 stays IN PROGRESS; AC-409.8 stays open,
and v3 search/public release remains NO-GO.**

### 2026-10-12 — Same-epoch duplicate-key wire tamper guard (opt-in only)

A separate source-only regression found a new byte-level blind spot in the
opt-in pinned v2 reader, distinct from the earlier digest and double-CURRENT
fixes. JSON.parse accepts duplicate JSON object keys, retaining only the
last value. The reader previously authenticated the canonical JSON of the
parsed object, not the exact downloaded body. A first duplicate records field
containing a withdrawn synthetic Finding (or a first nested title field with
withdrawn text) followed by the original good field gives the **same parsed
index, current source/index SHA, release ID and epoch**. The old reader
accepted that ambiguous response although its raw public asset contained
source text absent from the current released index.

The narrowed readPinnedPublicSearch now requires the exact canonical JSON
wire representation emitted by the search-index endpoint, with or without
its one trailing LF, **before** checking the original content hash,
release/epoch and independently re-read post-query pins. This refuses
duplicate keys and noncanonical extra bytes. The existing legacy unpinned
validator, schema, writer and Explore consumer are unchanged.

New web/scripts/check-search-currentness-wave-next.mjs constructs distinct
synthetic withdrawn/current v2 index releases with the real
buildSearchIndexMaterial/finalizeSearchIndex functions. It proves canonical
current search still finds the approved Finding and that both malformed
bodies parse to the exact same released current object. **RED:** the
duplicate top-level records body was accepted. **GREEN:** duplicate
records and nested title now return SEARCH_PINNED_INDEX_NONCANONICAL;
canonical JSON plus LF remains valid. The adjacent check-search-index.mjs
passes, the withdrawal script builds **two isolated Astro output directories
and passes**, npm run check --prefix web reports **118 files, zero
errors/warnings/hints**, and git diff --check passes.

**DP-409 remains IN PROGRESS, AC-409.8 unchecked and other AC states
unchanged.** This guard protects only the opt-in interpretation path; it
cannot stop a compromised host/CDN from directly serving malformed raw
bytes, certify a signed independent CURRENT issuer, or prove physical
screen-reader, atomic revoke/cache, MiniPC or production behavior.
No publication, provider call, route or deploy was introduced.

### 2026-10-13 — Independent 320/390 px actual-zoom search and focus check (PR #3 reconciliation)

Independent source/Chrome review was performed against **clean main
`0fb37c2b9f04ebe667dd25f6ad07d551c461c1ab`** using the pre-existing,
already-built **synthetic/demo** static `web/dist` (12 public-shape search rows).
This is **not** an authorized real corpus, public launch, or proof that the
distributed asset matches the current source tree. Existing unmodified
`cd web && npm run check:browser` passed with zero external/provider requests,
keyboard/dialog checks, reduced motion, a 375 px phone viewport, and exact
200% Chrome browser zoom with 640 CSS px. That checker did **not** exercise
search-field keyboard clear focus at 320/390 CSS px under actual 200% zoom.

The additional focused, non-duplicative probe is
`web/scripts/check-dp409-static-search-zoom-20261013.mjs`. It serves only a
specified existing static bundle on loopback and launches **one temporary
headless Chrome profile** with a per-host browser zoom of 2.0; resizing its
physical window to 640/780 px gives **320/390 CSS px**, with
`devicePixelRatio=2`, `visualViewport.scale=1`, and horizontal `scrollWidth`
of 320/390 px (no overflow). Search field widths were 230/300 px; filter
target height was 44 px at both widths. Keyboard Enter opened the filter
dialog; Escape restored button focus and `aria-expanded=false`; the changed
synthetic Person select value survived closing/reopening and was serialized in
the URL. This latter select change used an explicit DOM `change` event, **not**
a claim of native platform select-keyboard or physical assistive-technology
acceptance. `prefers-reduced-motion` was respected (dialog animation 0.001 s)
and monitored external requests were **zero**.

**Reproduced main focus defect (RED):** when keyboard focus moves to
`Pulisci ricerca` and Enter clears the text, the conditional clear button
unmounts and `document.activeElement` becomes `BODY`, **not** the still-visible
`#client-search` field, at **both** 320 and 390 CSS px. Exact reproducer:
`cd web && DP409_REQUIRE_CLEAR_FOCUS=1 node
scripts/check-dp409-static-search-zoom-20261013.mjs`, **exit 1** with
`DP409: keyboard clear loses focus from search input`; plain invocation exits
0 while explicitly reporting `BROWSER_PROBE_CLEAR_FOCUS_GAP` and
`clear_focus_pass=false`. This observation-only default deliberately does
**not** make the known unmerged defect an implicit main-gating new test.

**Existing ownership / isolated GREEN:** the fix already exists in **Draft
PR #3** (`fix/dp429-clear-search-focus-20261012`, exact reviewed commit
`4564a6f722aad9bd141ab860da36cbe070263033`), where Explore's
`searchInput` ref restores `.focus()` on clear. A separate **immutable
`git archive`** of exactly that PR commit's `web/` files was built with an
explicit local demo projection to a disposable temporary directory; its
artifact, **not** shared `web/dist`, was verified with:
`DP_BROWSER_DIST=<isolated-dist> DP409_REQUIRE_CLEAR_FOCUS=1 node
scripts/check-dp409-static-search-zoom-20261013.mjs`, **exit 0** and
`BROWSER_PROBE_PASS_MANUAL_AT_PENDING`. The exact-zoom, clear-focus,
filter-dialog, state preservation, reduced-motion and no-external-request
checks passed at **both** widths, with `document.activeElement.id`
`client-search` after clearing. The isolated build output/profile were
deleted; no checked-out source, shared dist, provider or DB was changed.

**No duplicate Explore/style patch belongs to DP-409.** Main continues to
exhibit the known focus loss until PR #3 is independently accepted and
integrated; the isolated PR test is not evidence of an already deployed fix.
Physical VoiceOver/screen-reader judgment, real-device assistive technology,
post-merge acceptance, current approved projection and MiniPC readback are
outside this synthetic browser proof. **DP-409 remains IN PROGRESS and
AC-409.8 remains unchecked** pending those independent gates.

### 2026-10-14 — Statement date semantics and archive-addition decision (source-only)

**Confirmed owner intent:** the 13 October DP-429 Q2 decision, reaffirmed in
ControlCenter task 297's 14 October owner packet, separates *dichiarazioni
recenti* (the date the statement was made) from historical statements *recently
added to the archive*. These are two different events. The first is a
Statement chronology; the second needs its own authoritative archive event.

**Current contracts inspected:**

- Running public-v2 search uses `PublicSearchRecord.published_at` as its
  default date key. Finding publication, with source publication as fallback,
  **is not a verified original declaration date**. DP-429's already integrated
  UI labels this boundary correctly; v2 must not be relabeled as a
  chronological original-Statement feed.
- Opt-in v3 `PublicStatementSearchV3` indexes only the independently gated
  `statement_date` calendar day, through the exact Statement-v3 and DP-439
  joined source. Its `recent`/`old` sorts compare that day, with stable
  Statement/version tie-breaks. The `generated_at` release timestamp is
  metadata, never a statement or archive-addition date. A same-day order
  therefore does not claim a particular time of day.
- No approved `archive_added_at` field or historical public-addition event
  exists in the Statement-v3 schema, DP-439 join, v3 index or v2 public
  projection. The 14 October postconsolidation handoff explicitly classifies
  this upstream decision as **not authorized**. No inference from source
  publication, Capture ingestion, index generation or initial discovery is
  sufficient to backfill it.

**Reviewed alternatives awaiting owner decision:**

1. **Explicit archived-at event (if approved upstream):** define
   `archive_added_at` as an attested UTC instant when an approved, eligible
   Statement first became publicly addressable in a published archive release.
   Pin it to a specific publication/release event and preserve withdrawal
   history. Decide whether reinstatement, a corrected version, or a changed
   source requires a distinct event; distinguish the first appearance from the
   latest eligible return. Older Statements lacking a verifiable event receive
   `null`/unknown, never the build timestamp or an invented historic date.
   Source schema, API/read model and search index need a coordinated versioned
   migration, current-release pins and withdrawal checks before Explore can
   offer the separate sort/filter or badge.
2. **No new archived-at field:** continue date-of-declaration sorting only
   where the original Statement date is independently eligible; where
   release comparison is available, present a distinctly named *newly visible
   between these two attested snapshots* indicator with explicit coverage
   window. DP-439 temporal counts already document that snapshot appearance
   does not establish an original archive-addition timestamp. Without two
   reliable snapshots, omit the label/filter instead of guessing.

**PENDING-OWNER / upstream DP-435/DP-437/DP-436 and release authority:**
choose the event semantics, version/reappearance behavior and historical
unknown-data presentation; approve the required authoritative publication
receipt before requesting a first-class archival timestamp. If this decision
is not made, keep archive-added sorting absent. A source-only v3 date field
does not authorize v3 publication, reclassify the existing v2 default sort,
or close DP-429 Q2.

**Focused preventive change:** the isolated
`web/src/lib/publicStatementSearchV3.ts` documents that `statement_date`
drives `recent`/`old`. The independent
`web/scripts/check-public-statement-search-v3.mjs` now asserts no
`archive_added_at`/`declared_at` is silently included and proves an index
with either invented key fails its exact schema validation **even after both
asset and external expected digests are updated**. The authentic synthetic
DP-439 four-membership / three-Statement search and revoked two-Statement
test still pass. This is a regression guard for existing authority, not a
new date feature, DB migration, public v3 release or owner/editorial sign-off.
Local recheck: `node --experimental-strip-types
scripts/check-public-statement-search-v3.mjs` PASS (3 synthetic originals,
2 after rights withdrawal, 909 bytes gzip, about 0.2 ms/query);
`npm run check:search`, `npm run check:statement`,
`npm run check:statement-parity` PASS; the focused upstream
DP-435/DP-439 Python suites pass 20/20, `npm run check` returns
0 errors/0 warnings/1 pre-existing hint in DP-429's suggestion script, and
`git diff --check` PASS. No site rebuild/live test was claimed for
this source-only schema-preservation check.
**DP-409 remains IN PROGRESS, AC-409.8 remains unchecked, with DP-408 and
actual v3/physical-reader release acceptance still open.**

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
actual screen-reader and manual 200% browser-zoom acceptance. Final runtime completion still
requires DP-401/MiniPC serving/read-back with the approved projection; dependency gates
DP-408/DP-425 remain authoritative.

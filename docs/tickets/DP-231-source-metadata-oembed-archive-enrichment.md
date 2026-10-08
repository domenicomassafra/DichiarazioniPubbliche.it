# DP-231 — Pender-style source metadata, oEmbed and archive enrichment

Status: DONE (optional provider contract; production provider lookup disabled)
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-210, DP-118, DP-305

## Problem

DP-210 implemented safe capture, visible-text parsing and an archive adapter state machine,
but the Pender audit also identified high-value metadata/provider behavior not yet ported:
canonical link metadata, OpenGraph/Twitter cards, schema.org/JSON-LD, oEmbed/provider
metadata and asynchronous archive completion receipts.

## Outcome

Enrich Capture metadata with bounded parser outputs and concrete replaceable archive
adapters without running Pender, Rails or Redis as another service.

## Acceptance criteria

- [x] HTML metadata parser extracts bounded canonical URL candidates, OpenGraph/Twitter
  meta fields and bounded schema.org/JSON-LD identity fields without executing scripts.
- [x] oEmbed endpoint candidates are extracted only as bounded HTTPS metadata candidates;
  no external request is made by the parser.
- [x] Map title/description/author/publisher candidates into an explicit metadata contract
  and detect conflicts with source-registry/Content identity.
- [x] Conflicting page/canonical/source-registry identity is explicit and cannot silently
  rewrite Content identity.
- [x] oEmbed/provider network lookups are allowlisted, bounded and optional.
- [x] Extracted metadata is stored as private Capture provenance/context and does not
  independently alter speaker identity, Content identity or factual findings.
- [x] Archive adapters preserve async REQUESTED/PENDING/SUCCEEDED/FAILED semantics and a
  durable archive URL/receipt.
- [x] Rights/access policy can disable metadata/archive operations per source.
- [x] Parser/archive failures preserve the primary Capture.
- [x] No Rails/Redis/Sidekiq runtime dependency is introduced.

## Completion receipt

Local metadata extraction is wired into Capture metadata with focused tests as of
2026-10-05. A pure `source_metadata_enrichment` contract now maps bounded title,
description, author and publisher candidates, validates canonical/oEmbed candidate URLs,
and emits explicit page/Content/source-registry conflicts while keeping both publication
authority and identity mutation disabled. Unsafe/private/credentialed candidate URLs are
discarded and represented only by a digest in conflict metadata. Existing DP-210 tests
also prove parser/archive failure preserves the primary Capture. Provider network lookup remains
open; no oEmbed/provider fetch seam was added by this block.

### Capture enrichment policy + archive receipt follow-up — 2026-10-06

The existing Capture/archive lifecycle already persisted the asynchronous
`REQUESTED -> PENDING -> SUCCEEDED|FAILED` transitions and their completion receipt. The
capture seam now makes the remaining source policy boundary explicit with
`CaptureEnrichmentPolicy`: source `content_policy` can independently disable metadata
enrichment and archive work before either optional operation runs. Metadata-disabled HTML is
still captured and parsed into private Passages, but the default parser does not extract
OpenGraph/oEmbed/JSON-LD metadata and any custom parser metadata is discarded at the Capture
boundary. Archive-disabled sources never invoke the configured archive adapter; the Capture
records `source_archive_policy=DISABLED` while its canonical durable archive state remains
`NOT_REQUESTED`.

A terminal archive `SUCCEEDED` result now additionally requires a credential-free HTTPS
`archive_url` on the default TLS port in its persisted completion receipt. A missing or
unsafe locator is converted to `FAILED` with `ARCHIVE_SUCCESS_LOCATOR_INVALID`, so success
cannot mean only an opaque provider dictionary. Existing request/pending/failure semantics
and primary-Capture preservation remain unchanged.

Focused proof: Capture pipeline + retention + metadata enrichment are **35/35 PASS**;
`python3 -m compileall -q poc tests` and scoped `git diff --check` pass. A repository runtime
dependency search across `pyproject.toml`, `poc/` and `tests/` finds no Rails, Redis or
Sidekiq dependency. The only remaining acceptance item is the optional bounded/allowlisted
oEmbed/provider network lookup; this tranche intentionally does not invent a provider or
network contract.

Final dependency-free acceptance on 2026-10-06 runs Capture + metadata enrichment as **24/24
PASS** locally and **24/24 PASS** in an isolated MiniPC `/tmp` bundle. That proves the parser,
policy-disable, conflict, unsafe-URL and archive-state contracts on the runtime authority without
network access. The remaining AC stays open because the repository still has no owner-selected
oEmbed/provider endpoint, provider-specific allowlist/request budget or approved network lookup
contract; adding a synthetic fetch would not prove that external prerequisite.

### Optional provider-pinned network adapter — 2026-10-08

The first optional network adapter is now implemented in
`poc/dichiarazioni_pubbliche/source_oembed_lookup.py`, using the published
Vimeo `https://vimeo.com/api/oembed.json?url=...` JSON contract. This is an
**engineering-contract completion**, not permission to activate a production
source, proof of a live successful remote response, or approval of any rights.

- `CaptureEnrichmentPolicy.oembed_lookup_enabled` defaults to **false** and
  `capture_enrichment_policy_from_source()` accepts only a source-policy
  Boolean opt-in; disabling metadata disables oEmbed even if the flag is set.
- Only public, exact-host Vimeo numeric-video URLs qualify. The code constructs
  the fixed endpoint itself rather than fetching any HTML-discovered
  `<link rel="alternate">` URL, credentialed URL, unrelated host or raw
  provider-supplied locator. The request is HTTPS, DNS-public-checked,
  redirect-denied, proxy-disabled, 3-second-limited and 8192-byte-capped, with
  JSON-only response acceptance. Future providers need separate review.
- Only bounded title/author/provider candidates and the response digest are
  stored in a **private append-only capture lifecycle event**; HTML embed
  markup, private metadata, arbitrary JSON fields and the raw response are not
  copied. Every candidate explicitly lacks publication or identity authority.
  The original Content Capture and its Passages are immutable across lookup
  success/failure. Replay of an existing Capture skips the network operation.
- A current acquisition permit is revalidated before the optional request.
  If the provider is down, returns an error, changes schema, redirects, or
  returns an oversized/non-JSON response, enrichment fails closed and the
  original successfully captured body/Passages remain intact.
- Focused local suite: **35/35 PASS**; isolated MiniPC `/tmp` canary:
  **35/35 PASS**, cleaned up without production service/DB/provider changes;
  full Mac suite **1822/1822 PASS**, benchmark **5/5 PASS**, compileall and
  `git diff --check` PASS.

The independently published example video `https://vimeo.com/286898202`
returned HTTP 404 from the API when checked on 2026-10-08. That result is
**not** misrepresented as a successful live-provider acceptance: production
source profiles remain unconfigured for this optional lookup. A future real
source activation must pass the source-owner rights/permission and live
endpoint receipt gates separately; `DP-231` does not grant them.

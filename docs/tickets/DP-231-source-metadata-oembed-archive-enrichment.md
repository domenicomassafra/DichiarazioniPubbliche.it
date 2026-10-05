# DP-231 — Pender-style source metadata, oEmbed and archive enrichment

Status: READY
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

- [ ] HTML metadata parser extracts canonical URL, title/description, author/publisher,
  OpenGraph/Twitter and bounded schema.org/JSON-LD fields without executing scripts.
- [ ] Conflicting page/canonical/source-registry identity is explicit and cannot silently
  rewrite Content identity.
- [ ] oEmbed/provider lookups are allowlisted, bounded and optional.
- [ ] Metadata is provenance/context, not speaker identity or factual evidence by itself.
- [ ] Archive adapters preserve async REQUESTED/PENDING/SUCCEEDED/FAILED semantics and a
  durable archive URL/receipt.
- [ ] Rights/access policy can disable metadata/archive operations per source.
- [ ] Parser/archive failures preserve the primary Capture.
- [ ] No Rails/Redis/Sidekiq runtime dependency is introduced.

## Completion receipt

Pending implementation.

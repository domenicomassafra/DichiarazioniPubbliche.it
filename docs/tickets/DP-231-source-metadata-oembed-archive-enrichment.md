# DP-231 — Pender-style source metadata, oEmbed and archive enrichment

Status: IN PROGRESS
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
- [ ] Map title/description/author/publisher candidates into an explicit metadata contract
  and detect conflicts with source-registry/Content identity.
- [ ] Conflicting page/canonical/source-registry identity is explicit and cannot silently
  rewrite Content identity.
- [ ] oEmbed/provider network lookups are allowlisted, bounded and optional.
- [x] Extracted metadata is stored as private Capture provenance/context and does not
  independently alter speaker identity, Content identity or factual findings.
- [ ] Archive adapters preserve async REQUESTED/PENDING/SUCCEEDED/FAILED semantics and a
  durable archive URL/receipt.
- [ ] Rights/access policy can disable metadata/archive operations per source.
- [ ] Parser/archive failures preserve the primary Capture.
- [ ] No Rails/Redis/Sidekiq runtime dependency is introduced.

## Completion receipt

Local metadata extraction is wired into Capture metadata with focused tests as of
2026-10-05. Provider lookup, identity-conflict policy, concrete archive adapter and MiniPC
proof remain open.

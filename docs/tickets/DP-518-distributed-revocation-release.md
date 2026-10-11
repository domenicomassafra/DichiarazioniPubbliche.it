# DP-518 — Revocation/correction distribution and immutable MiniPC release readback

Status: IN PROGRESS
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-303, DP-308, DP-431, DP-510, DP-511, DP-502

## Problem
 Source-rights/provenance revocation can race capture, candidate promotion, a running worker, snapshot generation and CDN/public API caching. DP-431 stale-artifact cleanup on regeneration and DP-511 revalidation do not themselves prove immediate safe visibility on the actually served MiniPC host/CDN. A Mac green projection rebuild cannot attest distributed withdrawal.

## Outcome
 One documented, reproducible release-and-withdrawal operation ties private authority-event version to public projection generation and every served consumer; on revocation or accepted correction the public site/API/search/sitemap/index/JSON-LD/RDF/cache becomes safe within an explicit tested window or fails closed. All prior private history remains append-only and recoverable, including rollbacks.

## Traceability & constraints
 R24/R25/R38 and R39; B owns linearizable revoke/write-fence mechanism and rights review, C owns public schema/quote exactness/index removals; D owns deploy/cache/operational replay. No false public account, no auto-publication. No invented propagation latency guarantee; first measure and set a justified SLO before claiming one.

## Scope
 Transaction epoch/version/hash and revocation fence per protected dependency, checked by all operations at persistence/promotion/publication and projection read; durable dependency graph from public Statement/Finding/Quote/Person×Topic/Content/Trace to source rights, attribution, findings, review and correction versions; release manifest binds source code sha, migration/policy, MiniPC mirror hash, data/projection/public bundle/cache generation. Atomic/static pointer or equivalent supported deployment requires final public readback; older cache generations get explicit invalidation or denial/no-store by class. If cache purge fails, public route blocks/omits unsafe material until proven. Revision may remove stale projection-owned files but cannot delete origin evidence, retained legal holds, appeal/private reply or prior signed correction history. Provider outage does not prevent safe withdraw.

## Non-goals
 New event bus, polling every user client, exposing raw revocation ledger publicly, changing B's qualified legal policy or bypassing publication gate for a “fresh” correction.

## Dependencies and sequencing
 B first specifies exact lock/order/authority across external writers; C supplies consumer manifest for exact quote/translation/summary/navigation; D exercises release/correction under existing hosting topology. DP-704 rehearses complete path, DP-705 binds it to selected candidate. Pilot acceptance before bulk; revocation tests required even before first public factual record.

## Acceptance criteria

- [ ] `AC-518.1`: Simultaneous revoke vs capture/claim promotion/review/public-build resolves to one documented epoch; no later unauthorized candidate can republish revoked quote, including stale worker/retry.
- [ ] `AC-518.2`: A materially changed/expired source right, attribution or evidence decision identifies all affected public rows and sanitized outputs including old static files, API/search/sitemap/JSON-LD/RDF, browser cache/CDN and Persona×Topic summary.
- [ ] `AC-518.3`: Exact MiniPC code/migration/source/version/projection hash readback and public live host readback agree; stale bundle/cache is unavailable or omits affected content, never returns old quote under 200.
- [ ] `AC-518.4`: Correction/reply reanalysis and withdrawal preserve private immutable receipts and properly version public history without exposing private complaint data.
- [ ] `AC-518.5`: Partial deploy/purge failure and rollback restore a known-safe read state with before/after checksums, not stale released wording; emergency hold works even with LLM/provider offline.
- [ ] `AC-518.6`: Alert/health digest records withdrawal reason class, content count, delivery lag, cache failure, owner and action with zero private payload. Measured lag sets candidate release SLO; no unmeasured bound is declared passed.
- [ ] `AC-518.7`: Rehearsal is repeated against exact approved source/rights/release candidate after material migration/safety change; operator and owner accept verified rollback.

## Validation / proof
 Isolated PostgreSQL race harness with two workers plus external rights writer, deterministic priority barriers, negative stale epochs; regenerated public artifact before/after hash lists; MiniPC candidate, actual configured reverse proxy/CDN smoke after hold/correction and TTL/cache readback; release rollback restoration and public/private isolation. No actual production mutation in planning.

## Documentation, data, and migration impact
 Bind existing revocation/DP-510/DP-511, projection cleanup/DP-431, source lineage, exact quote source-span and release manifest. Add only necessary fencing/generation fields with migration and rollback; immutable operator receipt and private contact route.

## Completion receipt
**2026-10-11 — bounded offline consistency checker implemented; no MiniPC acceptance.**
`poc/dichiarazioni_pubbliche/distributed_withdrawal_audit_v1.py`
models exact release/code/mirror/schema/policy/bundle hashes, structural DP-320
material epochs and per-record dependencies for all twelve Statement/list/
Person×Topic/Content/Trace/search/sitemap/JSON/API/RDF/HTML/edge consumers.
It rejects unknown/duplicate consumers, incomplete public surface inventories,
host/generation drift, old HTTP 200 quote responses, redirects and outages.
Even fully consistent caller-supplied 404/readback remains explicitly
`CONSISTENT_UNATTESTED`, with `release_authorized=False` and
`withdrawal_verified_on_live_host=False` because neither hashes nor local
responses certify trusted MiniPC/CDN origin. An isolated SQLite DP-320 test
shows that revoking source rights disables the former publication ticket while
the untrusted readback may remain unchanged.

Source/test commit `8bd5cc5`: **11 targeted DP-518 tests** and the existing
**7 DP-320 tests** PASS, Ruff PASS. This does not implement the actual
multi-writer PostgreSQL fence, HTTP/CDN invalidation, atomic deployment pointer,
provider-outage hold, measured propagation time, signed owner acceptance or
verified rollback. **AC-518.1–.7 remain open** and release remains NO-GO.

**2026-10-11 — follow-up: offline release identity and disjoint dependency regression.**
The offline checker now requires a separately supplied `ReleaseReadback` with
the exact release/host, code, MiniPC mirror, migration, policy, generation,
DP-320 fence and canonical public-artifact inventory SHA-256. Missing or
malformed release readback refuses the audit; discrepancies fail closed as
`READBACK_UNTRUSTED_OR_DRIFT` / `RELEASE_IDENTITY_READBACK_DRIFT`. This
detects self-consistent 404 probe sets paired with an altered release or
rollback inventory, a gap in the initial checker, but **does not attest**
where the supplied readback came from. The release ID is not yet a durable,
signed, operator-approved immutable deployment reference. A live 404 remains
insufficient to prove all browser/CDN caches have been invalidated.

For simultaneous revocation of unrelated dependencies across different
public entities, the consumer graph now requires exact per-entity dependency
coverage rather than every entity depending on all globally revoked sources.
The disjoint case passes, while missing dependency on one surface and
cached `200` from `CACHE_EDGE` are rejected. Code-only tests remain
independent of any MiniPC/rights source, transactional provider, HTTP
fetch or production mutation. Acceptance `AC-518.1` through `AC-518.7`
remain unchecked; real owner/source approval, MiniPC release/readback,
cache purge and rollback rehearsal are external blockers, release NO-GO.

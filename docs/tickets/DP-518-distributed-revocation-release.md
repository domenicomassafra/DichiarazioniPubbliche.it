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

**2026-10-11 — third-wave multi-revocation graph coverage regression, source-only.**
The offline audit previously derived affected entities from the union of
whatever revoked dependencies happened to be present in the supplied
public-artifact inventory. With two independently revoked dependencies
(`rights:1`, `source:1`), an inventory linking only `rights:1` across all
twelve consumers, and valid caller-supplied release identity/readback plus
404s everywhere, it falsely returned `CONSISTENT_UNATTESTED`. In
`test_multi_revocation_cannot_claim_consistency_when_one_dependency_is_unmapped`
this was verified **RED** on the original source. The private checker now
requires *each* requested revocation to map to a public entity in the
per-release dependency graph before attempting consumer consistency. An
unmapped dependency instead produces `INCOMPLETE_PUBLIC_COVERAGE` and
`REVOCATION_NOT_LINKED_TO_PUBLIC_ENTITY`. The existing disjoint two-entity
test still passes; no unrelated entity inherits another entity's revocation.

**GREEN proof:** DP-518 + DP-320 focused suites **25/25 PASS**, Ruff lint
PASS, targeted Python compilation and `git diff --check` PASS. The existing
source/test files had unrelated baseline Ruff-format suggestions before this
change; no blanket reformat was applied. This strengthens the *offline*
absence-of-coverage failure path only. As before,
`withdrawal_verified_on_live_host`, `cache_purge_verified`, and
`release_authorized` are always false. Original **AC-518.1–.7 remain
unchecked**, status **IN PROGRESS**; signed/current MiniPC source and
release attestations, immutable fence/CAS, real public/CDN cache responses,
measured propagation, qualified authority, rollback and owner acceptance
remain to be provided without pretending local metadata is host proof.

**2026-10-12 — fourth-wave local static-release consumer readback, source-only.**
Added a distinct *filesystem-backed* rehearsal, `audit_local_static_withdrawal`,
to the existing private DP-518 audit module. It reads real local static output
bytes and checks the complete explicit route inventory for all twelve consumer
types rather than trusting synthetic caller-supplied HTTP statuses. The local
fixture produces separate HTML, JSON/API, search, sitemap, JSON-LD, RDF,
navigation, trace, Person×Topic and simulated edge-cache paths for two entities
(24 routes). The public document root contains public fixture content only;
release/code/mirror/migration/policy/generation hashes, canonical artifact
inventory checksum and exact DP-320 dependency epochs live in a **separate
private sidecar receipt** which the reader refuses to open from the public root.
Paths must be complete, unique, relative and free of symlink traversal.

**RED:** the new functional regression suite could not import this operation.
An additional private-receipt separation regression also failed before the
control file was moved outside the served fixture root. **GREEN:** deletion of
all revoked surfaces permits `CONSISTENT_UNATTESTED`; a surviving old HTML,
API/search/sitemap/RDF or edge-cache file is observed from actual bytes as an
unsafe 200-equivalent; old-release rollback receipt, stale current epoch,
tampered dependency epoch, missing receipt, altered unaffected search bytes,
incomplete route inventory and symlink escape fail closed. Restoring the known
safe fixture receipt and removing the stale restored output returns the local
rehearsal to `CONSISTENT_UNATTESTED`, without deleting source history.
**Proof:** seven new functional tests, sixteen original DP-518 and eleven
DP-320 tests, **34/34 PASS**; Ruff, targeted compilation and `git diff --check`
PASS. Source and receipt remain private synthetic fixtures. The operation
only reads and hashes local files: no real static build, writer/publisher,
atomic live pointer, CDN/cache purge, MiniPC, signed release attestation,
independent source rights or latency was exercised. Its local cache path is
only a test double for edge bytes. `release_authorized`,
`withdrawal_verified_on_live_host` and `cache_purge_verified` remain false;
**AC-518.1–.7 open, release NO-GO**.

## 2026-10-12 — Canonical PG private release currentness reference (partial)

Source-only, independently opt-in adapter
`poc/dichiarazioni_pubbliche/ops/release_currentness_pg_v1.py`
and `tests/test_dp518_release_currentness_pg_next.py` now consume the
**actual canonical PostgreSQL schema** with the previously installed
DP-320 disposable `dp320_pg_source`, `dp320_pg_revocation`,
`dp320_pg_outbox`, `dp320_pg_ack`, and `dp320_pg_publication`
tables/functions. The new `dp518_pg_release`, `dp518_pg_current`,
and append-only `dp518_pg_selection` are **fixture-only** DDL,
guarded by the local `dp320_test_*` database name. There is **no
production migration** or real MiniPC/CDN/edge write.

The private `select_private_reference` transaction locks the full
sorted DP-320 dependency epoch/hash set and validates the exact
already-recorded DP-320 release/artifact/fence, verifies revocation
event→outbox identity/epoch/source completeness and absence of local
pending ACKs, binds exact generation/projection/index digests in an
immutable local release reference, then CAS-updates a monotone single
private pointer. The separate append-only selection receipt makes
replay idempotent only for the same original event while it remains
the selected reference; old revision, different event payload,
release-ID collision, missing DP-320 publication, deleted receipt,
pointer rollback, or incomplete partial write is rejected. A PostgreSQL
trigger-induced failure after event insert rolls back the entire
selection event and pointer update.

`read_private_reference` requires the exact expected release ID,
index digest, projection digest and pointer revision. It calls the
DP-320 database read fence under the same transaction: a concurrent
revocation commits on one side of the source row lock, and the old
release is never returned as coherent after it. In particular the
test caught a genuine first-implementation readback defect where
outbox counters were sampled **before** waiting on that source row
lock; those counters and the private epoch/version token are now
sampled **after** the lock/wait. A rights withdrawal, correction,
source-hash drift, stale index pin, unacknowledged unrelated outbox,
outbox corruption or manually rolled-back release pointer returns
`HELD` with a source-ID-free reason and opaque version token.
An ACK stored in the DP-320 **local fixture ledger** may clear a
pending flag, but never reactivates a revoked dependency or proves
an actual host purge. A coherent private reference returns
`COHERENT_PRIVATE_REFERENCE` (not a public `CURRENT` claim) with
`publication_authorized=False`, `host_ack_verified=False` and
`cdn_ack_verified=False` **in every case**.

**TDD RED→GREEN:** new test first failed to import the absent module.
Subsequent real disposable PG17 fixture tests covered restart,
same-event replay/conflicting payload, switch/rollback, correction and
rights revocation before/after acknowledgement, broken outbox,
material-hash drift, second-release revision collision, actual
uncommitted-selection-vs-revocation and revocation-vs-reader locking,
atomic rollback and append-only receipt tampering. Final **14 new
PG tests** plus **8 existing DP-320 PG tests**, **22/22 PASS**,
scoped Ruff, compileall and `git diff --check` PASS.

This is a **private consistency reference only**: it neither owns the
complete DP-518 public dependency inventory, signs source/owner
authority nor propagates an atomic deployment generation, actual
HTTP/asset/edge response denial, trusted cache purge ACK, release
readback on the MiniPC or measured withdrawal SLO. No public
consumer is wired to it, and it cannot attest any future byte sent
after the transaction commits. **AC-518.1–7 remain all unchecked;
DP-518 remains IN PROGRESS and public release NO-GO.**

## 2026-10-14 — Unlisted stale route in local release root (partial)

**RED reproduced:** the existing `audit_local_static_withdrawal` validated
the twelve declared consumer paths for each entity, but did not enumerate
actual files beyond that inventory. After a local reanalysis/withdrawal, an
older `person:revoked/statement-old.html` left in the selected public root
could still be served as an old quote while all 24 declared paths were safe;
the local audit incorrectly returned `CONSISTENT_UNATTESTED`. An unlisted
symlink to an outside file was likewise ignored. Both focused tests failed
against the pre-fix checker.

The checker now streams every directory entry **only within the selected
local public release root**, refuses unlisted HTML/API/JSON/linked-data and
other public-file paths as `READBACK_UNTRUSTED_OR_DRIFT` with a sanitized
`LOCAL_UNINVENTORIED_PUBLIC_FILE` code, and rejects symlinks and inaccessible
or nonregular paths. An explicit 10,000-entry ceiling fails closed if the
candidate tree is too large to audit. Conventional build assets (`_astro`,
`assets`, `static`, `images`, `fonts`) are tolerated only for known CSS/JS,
image, font and other static-build extensions; an extra `search-old.json`
under `_astro` is still rejected. A site with other public informational HTML
must include it in the actual release inventory before this offline checker
can claim local consistency.

**GREEN source-only evidence:** 28/28 local and distributed DP-518 tests,
22/22 adjacent disposable PostgreSQL DP-518/DP-320 tests, scoped Ruff,
compilation and `git diff --check` PASS. The selected root, sidecar receipt,
asset classification and all values remain caller-provided local rehearsal
inputs. Asset names/extensions do not attest the contents of an actual
compiled JS bundle or browser/CDN cache. No runtime/public host, physical
purge, authoritative immutable release pointer, source rights acceptance,
latency measurement or rollback-owner evidence was obtained. All original
**AC-518.1–7 remain open**, status **IN PROGRESS** and public release **NO-GO**.

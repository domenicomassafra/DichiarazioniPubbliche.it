# DP-320 — Revoca e correzione transazionali fino all'ultimo lettore

Status: IN PROGRESS
Milestone: M3 — editorial, correction, privacy, and legal policy
Depends on: DP-303, DP-308, DP-431, DP-510, DP-511, DP-117

## Problem
 `private_candidate_commit_fence` non serializza tutte le revoche esterne; la regen public cleanup non prova assenza di stale version su build servita/search/API/cache e transaction races. Material update può arrivare fra last review, candidacy, artifact publish e URL read.

## Outcome
 `RevocationEpoch/PublicationFence` referenziato in tutti i write/promotion/projection steps per record e source lineage; revoca, complaint, rights expiry, new challenger, privacy hold, version correction e supersession invalidano tutte le approvals derivate, con ritiro pubblico verificabile entro bound operativo **misurato**.

## Traceability & constraints
 R24/R25, Q14/Q16, append-only history, no raw private exposure. Minimize destructive ops; tests isolated then no-live promotion until D cutover.

## Scope
 Per source/capture/passage/statement/candidate/claim/evidence/Finding/relation/public view map per-revision material hash + revocation state/epoch; transaction or advisory lock + compare-and-swap at commit/revalidation with durable outbox for invalidation; C projection and search artefact generation/read-time recheck; D cache/sitemap/live CDN purge/swap/host rollback, correction notice and reproducible previous version. Revocation has priority over auto-publish; fail closed under timeout/unknown ack.

## Non-goals
 Silent deletion of historical evidence/appeal, public leak of complaint body, assumption that static regeneration alone instantly clears caches.

## Dependencies and sequencing
 Requires DP-316 for auto-approved records; can test old reviewer path independently. D owns release/ETAs/edge response, C owns public surfaces; B defines transaction authority and material dependencies.

## Acceptance criteria

- [ ] `AC-320.1`: Barrier races revoke vs Capture persist, Candidate, DP-117 promotion, evidence review, Finding, C generation and serving; after epoch increment no stale writer can create eligible public state.
- [ ] `AC-320.2`: Rights/relevance/reanalysis/reviewer reset and source version change invalidate all affected edges, latest public projection and stored approvals with reason ID, without erasing original lineage.
- [ ] `AC-320.3`: Bounded public data surfaces—HTML/JSON-LD/RDF/API/search/feeds/sitemap/linked card and cached served build—show authorized hold, omission or versioned correction after revocation; stale responses fail test; no hidden complaint/PII leak.
- [ ] `AC-320.4`: Exact repeat revoke and outbox retries idempotent; partition/crash/restart readback and rollback preserve hold; subsequent qualified restoration requires a fresh exact authority, not stale retry.
- [ ] `AC-320.5`: D MiniPC rehearsal logs measured end-to-end revocation latency with cache policy/projection version; threshold chosen by accepted risk/operational requirements before release, not fabricated by planning.

## Validation / proof
 Deterministic concurrent transactions with barriers on disposable PostgreSQL, frontend/edge simulated-cache stale fixture, isolated MiniPC fresh-source→publish→revocation→negative-readback, crash-restart/rollback.
## Documentation, data, and migration impact
 Additive epochs/queue/event link and component consumption contract; don't mutate existing DONE receipts.
## Completion receipt
 Historical planning receipt; now superseded only in the limited source-only slice below.

## 2026-10-11 — Local transactional reference contract (partial)

Added opt-in `poc/dichiarazioni_pubbliche/revocation_epoch_fence.py` with
`tests/test_dp320_revocation_epoch_fence.py`: one bounded immutable material-
dependency set/fingerprint per release, explicit monotone revocation epoch,
SQLite `BEGIN IMMEDIATE` compare-and-swap fixture for competing revoke versus
public-artifact-reference commit, durable append-only revocation event/outbox,
idempotent event replay and current-epoch checks on an isolated simulated
reader. Seven focused tests pass, including source-rights invalidation after
prior release and restart/transaction races. No real rights or publication
authority is created by the fixture and no writer automatically restores a
revoked subject. All original acceptance criteria remain **unchecked**:
runtime PostgreSQL migrations/CAS, complete material lineage graph, actual
public HTML/API/search/edge/TTL purge/swap and measured MiniPC withdrawal
latency have not been implemented or verified. NO-GO public activation.

## 2026-10-11 — Isolated read/revoke race fix (source only)

The original SQLite `check_served` verified each material epoch and then
queried `epoch_publication` without holding a transaction. A second connection
could commit a revocation between those reads; the first could still return
`True` for the old artifact **after** the revocation commit. A deterministic
threaded test paused the read exactly before the publication lookup and
confirmed the unsafe ordering (RED). `check_served` now holds a SQLite
`BEGIN IMMEDIATE` transaction for the full epoch + immutable artifact-reference
comparison, releasing it on success or failure. An in-flight revoker waits
until the read transaction completes (GREEN); a subsequent stale read refuses.
The rejected-read case also verifies rollback unlocks the connection for revoke.

This is a local transactional reference only. Its lock ends before HTTP bytes
are delivered; it does not supply a production PostgreSQL read fence, a
distributed cache denial/purge, a signed release identity, a real-source
approval or an attested MiniPC rollback/latency receipt. **AC-320.1–.5
remain unchecked, release remains NO-GO.**

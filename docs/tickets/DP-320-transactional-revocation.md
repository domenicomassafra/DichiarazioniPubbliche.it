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

## 2026-10-11 — Atomic multi-dependency ticket mint (source-only)

Another distinct revocation race was reproduced in the isolated SQLite
reference. `mint()` read each source's status/epoch independently without a
transaction, whereas only `publish_reference` and `check_served` held
revocation-serializing locks. A second connection could therefore commit a
rights revocation **after** `mint()` had read `rights:1` but **before** its
next `source:1` read, causing `mint()` to return an apparently newly issued
ticket already stale at return. This is not authority to publish—the
downstream transactional write/read fences still reject that ticket—but
the mint receipt itself incorrectly claimed a consistent current snapshot.

A deterministic barrier test pauses mint at its second SELECT and attempts a
concurrent revocation with a zero-timeout SQLite connection. Before the fix,
the revocation incorrectly committed during mint (**RED**); after wrapping the
complete dependency read and fingerprint issuance in `BEGIN IMMEDIATE` with
commit/rollback, the revoker receives a lock error until the mint completes
(**GREEN**). The test then revokes successfully and confirms the minted
ticket cannot be published. A second regression confirms a failed mint of an
unknown dependency releases its lock and does not prevent subsequent
revocation or suppress the durable invalidation outbox.

**Local proof:** `PYTHONPATH=poc python3 -m unittest
tests.test_dp320_revocation_epoch_fence
tests.test_dp518_distributed_withdrawal_audit -q`: **27/27 PASS**;
`ruff check`, Python compilation and `git diff --check` PASS. The two
DP-320 files already had pre-existing Ruff formatter differences on HEAD,
so unrelated lines were not mass-reformatted.

The result is a SQLite **reference contract**, not a real source-rights
verifier, PostgreSQL writer fence, approved material graph, MiniPC host
admission, edge/cache withdrawal, immutable deployment readback or measured
withdrawal SLO. No real source, CDN, database or release was changed.
**Status remains IN PROGRESS, all AC-320.1–.5 remain unchecked and public
release remains NO-GO** pending the original external gates.

## 2026-10-12 — Disposable PostgreSQL transactional fence (partial)

An independent opt-in PostgreSQL reference now lives only in
`poc/dichiarazioni_pubbliche/revocation_pg_fence_v1.py`, with adversarial
`tests/test_dp320_revocation_pg_next.py`. The test starts its own PostgreSQL 17
cluster, loads the actual `db/schema.v1.sql`, creates a separate
`dp320_test_fence` database and explicitly installs private `dp320_pg_*` tables
and functions there. Database names outside `dp320_test_*` or non-loopback
connections are refused. No canonical migration or production data changes.

PG transactions lock all ticket dependencies in stable order, compare the
current material hash/epoch/ACTIVE state for mint, artifact-reference commit
and checked read, and serialize revocation against these operations using
`SELECT ... FOR UPDATE`. Revocation increments the epoch and creates an immutable
event and an outbox row in the same transaction. Outbox acknowledgments are
independent append-only rows; retries with the same event and exact source,
reason and instant return the persisted epoch, conflicting replays are denied.
There is no automatic restoration path. Local DB timeouts cap blocked calls.

Seven genuine PostgreSQL tests cover stale reference/reader rejection after
revocation, persisted outbox across reconnect, same-event idempotent retry and
conflict, a killed uncommitted PostgreSQL session followed by restart/replay,
immutable event/outbox, material-hash change, and both lock orders: a waiting
publication/reader after revocation and an already inserted uncommitted
publication before revocation. The original SQLite reference tests also pass.

**Remaining:** this is an isolated database contract. Real source/Capture/
Passage/claim/review approval writers and public projections/search/HTML/API
do not call this fence; the dependency graph, allowed restore authority,
cache/CDN purge and byte-delivery window remain unverified. No MiniPC timing,
rollback or D cutover evidence exists. **All AC-320.1–.5 stay unchecked,
ticket IN PROGRESS and launch NO-GO.**

## 2026-10-14 — Seven-surface, revocation-fenced offline reference

Added a substantial **opt-in SQLite-only reference consumer**
`revocation_served_surfaces_v1.py` and adversarial tests. One immutable
release ticket, material epoch and **independently supplied manifest pin**
bind seven simulated public-surface references: HTML, API, SEARCH, FEED,
SITEMAP, LINKED_CARD and JSON_LD. Each surface has its own bounded exact
fixture-bytes SHA-256 and belongs to one completely enumerated cohort.
`seal()` transactionally inserts root publication plus seven individual
surface hash rows under `BEGIN IMMEDIATE`, refusing conflicting replacements.
Even a single-surface `check_one()` validates the full stored cohort under
the same release ticket and manifest before comparing its observed digest.
This fixture computes reference eligibility but **never serves or stores
surface body bytes**, issues rights authority, publishes URLs, or calls a
network/provider/production database.

The new test file first failed **RED** with missing module import; once the
consumer was implemented, **40/40 targeted + adjacent DP-320/DP-518 tests
PASS**. Fixtures exercise missing/duplicate/mixed-epoch surfaces, tampered
payloads/digests, wrong issuer fingerprint, forged source ID, partial or
cross-release cohorts, conflicting release overwrite, revoked rights,
privacy hold, correction/supersession, outbox acknowledgment, idempotent
event replay, no automatic rights restoration, SQLite restart and two-
connection read/revoke and seal/revoke races. The bounded 100-read SQLite
reference microbenchmark (~0.013 seconds) is a **local microtest, not public
withdrawal latency or a delivery SLO**. Ruff, compilation, diff checks,
independent review and full Python suite are scoped to the source branch.

**Not a production revocation integration:** Capture/Evidence/Finding writers,
authenticated editorial/rights authority, production PostgreSQL, cache/CDN
purge/swap, actual served HTML/API/search/feeds, cross-host epoch issuer,
post-reference-check HTTP byte delivery and MiniPC latency are all missing.
The code does not and cannot prove that previously transmitted bytes have
been withdrawn. **DP-320 stays IN PROGRESS, all original AC-320.1–5 remain
unchecked, and public activation remains NO-GO.**

**Independent post-implementation review (worker-6, read-only): PASS within
this limited SQLite source contract, no additional reproducible P1/P2.**
The reviewer inspected exact new source SHA-256
`5553cf49d9bed8d0cd360e0fd9b6f9623dd6ccfe6ce2d9b314cf80f7a1232478`
and test SHA-256
`73619934422f1e00eb5502a822efba42d2ff6198a9abb08778ae3adaf5c60428`
against the canonical DP-320 epoch module and ticket. Independently reran
**40/40** targeted/adjacent tests, and separately reproduced rejection of
self-rehashed/re-pinned modified bytes, altered root publication SHA,
missing JSON-LD while checking HTML, an extra unsupported surface and
tampered ticket fingerprint; source and file lint/diff checks PASS. The
reviewer made no changes to source, Git, DB production or provider state.

The reviewer also identified explicit **unresolved scope**: the original
AC-320.3 mentions RDF, which is **not** present in the deliberately bounded
seven-surface fixture; an exotic malformed nested Python ticket can raise a
generic `AttributeError` rather than the stable refusal class (still denies
and does not return data). These are not silently treated as accepted public
behavior or proof of an actual HTTP edge fence. The full Python suite,
publication SHA and source-only ticket receipt are recorded separately.

**Cross-feature fixture smoke (Mac, provider-free):** a disposable in-memory
SQLite session consumed the real synthetic DP-439 Python `published()` and
`make()` Person×Topic/Statement materializers, bound their output bytes to
seven different simulated surface hashes and to independent synthetic source
and rights dependencies. `seal()` and `check_all()` accepted the current
release; after one `RIGHTS_WITHDRAWN` event on the rights dependency, **all
seven `check_one()` calls refused with `FENCE_STALE_OR_HELD`**, and the
durable outbox exposed the expected one event. Result:
`DP320_DP439_REAL_PYTHON_FIXTURE_PASS`. This is an isolated supplementary
one-off fixture, not permanent operational wiring or a live rights judgment.

**Final branch validation:** exactly one complete source-branch Python suite
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`
returned **3,452/3,452 tests PASS, exit 0, 315.034 seconds** against this
final new DP-320 source/test. The deterministic benchmark was **5/5 PASS**;
targeted new and adjacent DP-320/DP-518 regressions **40/40 PASS**. Ruff
check, Ruff format check and `git diff --cached --check` PASS. Existing
DP-429 empty/demo isolated browser, DP-431 actual TS↔Python/parity/rebuild,
DP-438 pinned reader and DP-439 offline Astro SSR checks were rerun on their
independently saved source-only branches, not represented as an integrated
public release or branch PR CI. Original DP-320 acceptance remains OPEN.

## 2026-10-14 — Opt-in eighth RDF reference and single-corpus DP-431 search fence

New source-only additive extension of the **already published** DP-320 seven-
surface SQLite prototype. The immutable original `ALL_SURFACES` contract
remains exactly seven entries; a separately requested `include_rdf=True`
selects the explicitly versioned *eight*-surface cohort, adding `RDF` after
JSON-LD. Legacy seven-element manifest SHAs and seeded releases remain valid
only as their original seven-element cohort and **cannot silently become an
eight-element approval**. The root manifest fingerprint covers the full
selected cohort, each exact public fixture bytes SHA and their source epoch;
one `BEGIN IMMEDIATE` transaction seals/rechecks the complete bounded set.
If the stored RDF row disappears or is corrupted, checking unrelated SEARCH
or HTML also refuses. A mixed seven/eight or privately re-pinned corrected
RDF document cannot bypass the original immutable release reference.

The new deterministic fixtures now generate BOTH Search Index v1 and N-Triples
using **one and the same real Python `build_public_projection` synthetic
public-v2 dataset**, not two unrelated samples. The unmodified DP-431
`check_correction_propagation` source verifies the same index/projection
receipt; the same corpus serializes actual `projection_ntriples`. Neither
fixture contains real political person/source permissions or editorial
material. The new test begins **RED** with missing `EXTENDED_SURFACES`; then
**47/47** combined new RDF/source-search + unchanged seven-surface DP-320/
DP-518 tests PASS. All eight surface reads refuse after each independent
synthetic `RIGHTS_WITHDRAWN`, `PRIVACY_HOLD`, `CORRECTION` and
`SOURCE_SUPERSEDED` event; root outbox shows one immutable revocation.
Wrong/missing RDF, malicious rehash/re-pin and release-conflict readbacks
reject. A genuine two-connection SQLite test proves an RDF reference read
holds its transaction against a racing rights revoker, with a subsequent stale
read refused; malformed nested ticket metadata returns a fixed safe denial
instead of an uncontrolled Python attribute error. This is reference-level
admission only; it provides no HTTP bytes, source approval, real PostgreSQL
writer integration, CDN/edge invalidation, authorized public RDF route,
live source role, physical MiniPC proof or measured withdrawal latency.

**All AC-320.1–5 remain OPEN; ticket Status remains IN PROGRESS and real
public launch remains NO-GO.** Focused results are source-only, while a new
complete suite and independent final review require separate receipts.

**Review-status receipt:** previously successful independent worker-6 could
not be revived for this new revision (two separate startup failures), and a
new worker-8 independent invitation also failed before receiving source
inputs. **NO independent PASS on the new RDF diff is claimed.** Prime's
bounded real-source source-only audit and complete focused test matrix are
author self-review; the true external/independent review gate is still
**PENDING** before any PR/production release. Neither prior reviewer PASS on
the original seven-surface SHA nor current source-only tests are substitutes.

**Definitive local suite (source-only, not CI):** a disposable **uncommitted,
detached test worktree** over clean canonical main copied the exact final
DP-320 eight-surface source and new test, the already published seven-surface
regression test, and the two disjoint new DP-440 files byte-for-byte. ONE
full Python unittest discovery on this combined exact source overlay returned
**3,469/3,469 PASS, exit 0, 298.492 seconds**. Independent file SHA/byte
comparison before the run confirmed the delivery source copies. The
deterministic benchmark **5/5 PASS**, Ruff check/format and compileall PASS;
DP-320 new+adjacent targeted **47/47 PASS**. This is neither exact-head GitHub
PR CI nor an independently reviewed release; operational rights and all
original acceptance remain OPEN.

**2026-10-14 post-ship source-only review of exact published `af9fb892`:**
Prime (the implementer, **not** an independent reviewer) re-inspected the
actual diff against parent `38bb8707`. The unchanged seven-surface contract
and new opt-in RDF eighth surface use distinct complete manifest shapes;
`_complete_metadata` checks bounded bodies, ticket dependencies and exact
surface order, `seal` and `_read` both perform `BEGIN IMMEDIATE` followed by
the canonical ticket epoch check and full stored-cohort manifest readback.
Inspectors reran the real shared-public-projection Python Search Index/RDF
fixture, the four revoke reasons, missing RDF blocking an unrelated HTML or
SEARCH check, rehashed/re-pinned RDF denial, legacy seven/eight refusal,
malformed nested ticket rejection and the separate-connection read/revoker
barrier: **47/47 scoped tests PASS**, no newly reproduced P1/P2 in this
source-only contract. It cannot fence HTTP bytes sent after commit, purge
distributed caches or certify editorial rights. **Independent diff review
remains PENDING**; no external reviewer ACK, PR CI or full acceptance inferred.

**Final revalidation of the three separate source lanes:** one completed
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc:tests python3 -B -m unittest discover -s tests -q`
on an isolated detached main overlay with SHA/byte-identical DP-320, DP-440
and new DP-439 source/test files returned **3,476/3,476 PASS, exit 0,
330.917 seconds**; Ruff check/format and deterministic benchmark **5/5
PASS**. An earlier run on a pre-final DP-439 source was intentionally
stopped, **exit 143 and not represented as success**, to add a genuine
temporal as-of RED→GREEN regression before this definitive completed run.
This remains local source validation, not PR CI, independent approval or
any physical/rights/provider acceptance.

## 2026-10-14 — Independent P2 discovery: actual TypeScript SEARCH bytes

Independent reviewer worker-9 identified a consequential P2 in the prior
**test contract**, not an observed live authorization bypass: the fixture
sealed the smaller DP-431 Python *metadata-only* search receipt as `SEARCH`.
That lacks required `projection_schema_version`, `generated_at`, full
per-record route/term fields and the independently checked `index_sha256`;
the actual production TypeScript `validateSearchIndex` refuses it. It also
incorrectly counted a legacy Content search row when explicit
`contents=[]` prohibits fallback. Hence prior SQLite tests did **not** prove
that the SEARCH bytes were accepted by the actual frontend reader.

New deterministic RED requires full canonical Search Index v1 fields; it
failed on the published surrogate. The corrected fixture locally executes
the real `buildSearchIndexMaterial`, `finalizeSearchIndex` and
`validateSearchIndex` TypeScript via Node with no HTTP/provider/source-body
access. Its input is the same real synthetic Python public-v2 projection
used for DP-431 Python metadata and linked-data N-Triples. The final
sealed `SEARCH` bytes come from **the validated TS asset**; the Python
metadata receipt is only compared on shared public Finding/Person/Topic
fields, and explicit `contents=[]` is verified to produce no TS Content
records even though the metadata guard can still track Content lineage.
The 8-surface SQLite checks, real TS validation, four revoke reasons and
adjacent DP-320/DP-518 regressions are now **48/48 PASS**. A further
independent re-review of this corrected diff was requested; do not infer
its result from the initial finding. No HTTP/CDN revocation, real route,
PostgreSQL/MiniPC, rights or editorial acceptance is claimed.

**Final independent source-only re-review:** worker-9, read-only, reran the corrected actual TypeScript Search Index v1 fixture (builder + finalizer + validator) and checked six canonical top-level fields, complete public record fields, and no fabricated Content search record when `contents=[]`. Separately replayed the RDF/SQLite eight-surface and legacy-seven tests; its DP-320 subset **39/39 PASS**, prime's wider DP-320/DP-518 **48/48 PASS**. No remaining reproduced P1/P2 in this *bounded test/source contract*. Reviewer made no Git, source, provider or host changes. Historical HTTP/CDN bytes, production PostgreSQL, source rights, public routes and MiniPC remain outside acceptance.

**Final post-review codefreeze validation:** one completed full Python unittest discovery on a detached main worktree containing exact byte-identical DP-320, DP-440, DP-439 and DP-314 source/test files returned **3,503/3,503 PASS, exit 0, 306.597 s**. Deterministic benchmark **5/5 PASS**, Ruff/check/format PASS. Exact TS Search Index builder, finalizer and validator and corrected `contents=[]` regression are included. A prefinal full-suite attempt was deliberately terminated **exit 143** after the reviewer found a further DP-440 source mutation problem; it is NOT counted as PASS. Reviewer independently rechecked the corrected bounded DP320 tests; no CI/production/physical acceptance inferred.

## 2026-10-14 — DP-431 + DP-320 integrator: explicit empty Content SEARCH parity

This is a **new separate isolated integration branch** based on the published
DP-320 RDF/SEARCH fence with three exact source/test paths imported from the
clean published DP-431 search-metadata integrator, **not** from the still-dirty
DP-431 worker worktree. In the combined real sources, DP-431 correctly treats
`contents=[]` as a first-class **empty** Search Content catalog and the actual
TypeScript `buildSearchIndexMaterial` → `finalizeSearchIndex` →
`validateSearchIndex` consumer similarly returns two records (Finding and
Person) for the approved-shaped synthetic fixture. The older DP-320 test
mistakenly expected `>=3` metadata records from its pre-DP-431 fallback.

Actual combined **RED**: `test_dp320_rdf_search_integration_20261014.py`
returned exit 1, **8/8 failed** at that stale minimum-record assertion. No
HTTP/CDN bypass was observed. The integration fixture now refuses fabricated
legacy Content rows and requires an exact `(kind,id)` identity set plus the
full shared metadata-field parity against the actual TypeScript asset, with
an explicit new regression for `contents=[]`. Combined **GREEN** after this
test-contract fix: DP-320 RDF/SEARCH **9/9**, DP-431 integrity **7/7**,
DP-320 SQLite served-surface **13/13**, all exit 0. `git diff --check` and
Ruff lint pass; published DP-431 source and pre-existing tests retain their
prior formatting (no mass refactor). Exact remote SHA, post-fix independent
review and final combined Python suite must be recorded separately when done.

This is a **local synthetic/offline source integration receipt only**:
historical CDN HTTP withdrawals, real PostgreSQL, MiniPC, rights clearance,
source approval, editorial correctness, PR CI and deploy remain unverified.
Original DP-320 Status/AC are unchanged; no direct merge to `main`.

**2026-10-14 — Independent post-integrator review, final suite, and remote
receipt.** Integration source/test SHA prior to this documentation-only
followup `52a5568a488eb91b24fee40318e84c62fabb37c0` passed independent
strict READONLY `worker-10` review: DP-320 real RDF/SEARCH **9/9**,
DP-431 integrity **7/7**, served surfaces **13/13**, correction propagation
**12/12** = **41/41 PASS**. The reviewer confirmed canonical production TS
builder/finalizer/validator repeatedly and full Python metadata record
equality for explicit `contents=[]` (2 Finding/Person records), legacy absent
`contents` (3 with fallback Content), and approved first-class Content
(3 records), including stale metadata denial; imported DP-431 source/test
blobs equal their published original commit `089461ab9572f06ed77b6696fa1bd7bf0d55163e`.
No new P1/P2 reproduced in this bounded fixture contract. Actual final
detached 30-file combined Python suite **3,572/3,572 PASS, exit 0,
384.450 seconds**; benchmark **5/5**, patch/test Ruff lint and new test
format PASS. Historic imported DP-431 files remain nonformatted and one
historic inherited DP-314 test has Ruff F401: no global lint PASS claimed.
Source/test manifest SHA-256
`15badae206c51cfda9976c86d8eaf6fce10b0e8ccc3ff12480a376db21d3320f`.
This is not proof of live HTTP/CDN rights withdrawal, PostgreSQL, source
approval, publication, full MiniPC test, PR CI or physical readiness.
**Status IN PROGRESS and original AC unchanged**; no PR or main merge.

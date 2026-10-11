# DP-417 — studio discovery inbox

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-209, DP-212, DP-414

## Problem

Newly discovered material needs triage. Without an Inbox, automation either stops at logs or silently makes decisions that should be reviewable.

## Outcome

Implement persisted triage queues for new content, duplicate/existing hits, changed captures, unresolved entities, statement candidates, already-covered claim candidates, Coverage Needs and blocked/quarantined items.

## Scope

- Queues derive from database state/query contracts rather than copied counters.
- Row actions: inspect, link/merge candidate, reject, add to collection, extract, promote when eligible, open/target Coverage Need.
- Bulk actions only where semantics are safely identical and reversible.
- Show provider/rights/budget blocks with stable reason codes.

## Non-goals

- No inbox-zero gamification.
- No mass approval of identity/claims from one similarity threshold.
- No automatic publication button.

## Dependencies and sequencing

DP-209, DP-212, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-417.1:** Every queue row has an inspectable provenance path.
- [ ] **AC-417.2:** Action replay is idempotent or explicitly conflict-detected.
- [ ] **AC-417.3:** Blocked rows explain the exact blocker and retry/unblock condition.
- [ ] **AC-417.4:** Bulk actions cannot cross incompatible review states.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Private Studio workflow over real processing state.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Read-only blocked-state inspector — 2026-10-08

`StudioReadOnlyWorkspace.tsx` now supports source-bound inbox row selection,
`ready/blocked` filters, explicit provenance display and fail-closed blocker
explanations for the fixture. No triage action is enabled: it would be unsafe to
turn a UI click into a review/merge/promotion without current persisted authority,
idempotency, rights and state-transition verification. Real queue reads, replay,
bulk-action compatibility, runtime canary and full acceptance criteria remain open.

Follow-up 2026-10-08: token-authenticated local Discovery endpoint now
reads paged persisted discovery-hit IDs, run IDs, exact disposition,
optional Content ID and safe blocker code. It excludes raw source URL,
query, title, provider receipt and private body. The local browser has
a read-only Inbox form. No reject, merge, promote, publish, bulk mutation,
review authority or idempotency acceptance is introduced.

### Scoped per-Hit provenance inspection — 2026-10-09

The authenticated loopback Studio adds `/v1/discovery/inspect` and a
read-only Inbox form accepting the exact Collection ID and Discovery Hit ID.
The SQL traverses persisted Hit -> Run -> Attempt -> Query -> Manifest ->
Collection, checking run/attempt lineage, active manifest, digest,
source-family/adapter scope, URL-to-Content equality and Collection
membership. A mismatched Collection/Hit pair is not found; there is no
cross-collection inspection by guessing an ID.

The response allowlists **IDs, safe status codes, specific blocker codes
and suggested unblock conditions**, not source URLs, titles, query text,
provider receipts, source bodies, model prompts or other private metadata.
The suggestions are not authorizations. No action to merge, reject,
extract, promote, publish or bulk-modify is enabled.
Even a fully matching synthetic Discovery lineage remains blocked by
`PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED` and
`DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE`; the response reports
lineage checks separately from those mandatory missing authorities.

Focused unit tests prove valid lineage, rejected/mismatched provenance,
blocked/capture-unapproved cases, malformed payload refusal, no private
fields in replies, loopback dispatch and local browser form. A MiniPC
PostgreSQL `pg_temp` canary exercises the **actual SQL** with one
synthetic valid row and then a failed Discovery Attempt, with all
temporary state rolled back and production counters unchanged.
Live `research:garlasco` has no persisted Discovery Hits to inspect.

**Partial only:** this adds an inspectable provenance path and exact
unblock guidance **for Discovery Hit rows**, not for every DP-417 queue
type. AC-417.1/.3 stay open until other queue families are implemented
and runtime-proven. Durable review transitions, idempotent action replay,
bulk-state compatibility and real source-family review remain open.

### Durable private triage annotations — 2026-10-09 (source-only, not deployed)

An additive `research_discovery_triage_decision` ledger now has a matching
fresh schema and migration. It records **non-authoritative, append-only
annotations** (`NEEDS_REVIEW`, `DEFERRED`, `REJECTED`) against a
Collection-scoped Discovery Hit with an opaque actor reference, a canonical
request digest, globally unique idempotency key and per-Hit compare-and-swap
revision. PostgreSQL verifies Hit→Run→Manifest→Collection and
Attempt/Query coherence before inserting, serializes concurrent writes by
transaction advisory lock, and forbids UPDATE/DELETE/TRUNCATE of ledger
records. It does not change a Hit's discovery disposition.

The opt-in, DB-permission-bound CLI module
`dichiarazioni_pubbliche.studio_discovery_triage_store` reports exact
`CREATED`, `REPLAY`, `IDEMPOTENCY_CONFLICT`,
`REVISION_CONFLICT` or `SCOPE_NOT_FOUND` results. A replay must
match the entire stored request and fingerprint; cross-Collection inspection
returns no ledger revision. Inputs and output receipts are allowlisted,
with no source URL, text, provider secret or private metadata. The current
loopback Studio API stays strictly read-only; the CLI is not linked to it.

**Proof:** 21/21 focused Python tests for pure contract, runtime and real
ephemeral PostgreSQL schema/migration (including concurrent insert
competition) pass. A separate ephemeral PostgreSQL writer+real-migration
integration probe passed six outcomes including conflict and cross-scope
redaction. The live MiniPC PostgreSQL accepted a separate
seven-case **pg_temp / ROLLBACK** actual SQL canary: create, replay,
idempotency-key collision, stale revision, next revision, stale revision
again and wrong Collection; zero durable production writes. The migration
has **not** been applied to the MiniPC production schema.

All nine new fields are denied direct public projection by the refreshed
privacy inventory. Backup and restore table inventories include the ledger.
After correcting these two inventory drift failures, the full Python suite
passed **1,962/1,962**; the focused privacy/backup/restore tests passed
**29/29**; `python3 -m compileall -q poc tests` and `git diff --check`
passed. This is local source acceptance, **not** deployment/CI release
acceptance or an authenticated human reviewer acceptance.

### Signed local actor identity + read-only Inbox history — 2026-10-09

The operator-private history reader provides scoped
`/v1/discovery/triage-history` (Collection ID + Discovery Hit ID) on the
authenticated loopback Studio API. It is paged by numeric revision, shows
only safe annotation decision codes/revisions, detects malformed lineage,
refuses guessed cross-Collection Hits, and never leaks reviewer identifiers,
source URLs, text, receipts or credential data. This route is **read-only**,
and will return an unavailable-data error on live databases where the
new ledger migration has not been applied.

Separately, an off-database HMAC attestation module binds each exact
non-authoritative triage request to an **active** local reviewer credential
from the existing 0700 authority root, with a dedicated
`DP417_TRIAGE_V1` domain, a 0600 no-replacement receipt file, exact
actor/scope/revision matching, and verification after revocation. The
`record_attested` runtime verifies this signature before attempting the
append-only annotation. The explicit CLI requires authority root and
credential ID and issues+verifies the local receipt before DB write.
This identity proof **does not authorize** rejection of source material,
rights clearance, Content capture, merging, extraction, approval, promotion
or publication. The primitive `record` API remains an intentionally
unattested test/operator-DB primitive, and its response always reports
`actor_attested=false`.

Real ephemeral PostgreSQL writer tests cover exact replay, stale revisions,
competing/deduplicated concurrent writers, invalid Run→Attempt→Query
lineage, cross-Collection redaction and immutable annotation history.
The reader additionally passed actual migrated ephemeral PostgreSQL
pagination tests; authenticated loopback API tests verify token requirements,
input denial and no private fields. Credentials are never sent through
the HTTP API. MiniPC synthetic SQL checks were repeated with the coherent
Attempt+Query scope and passed **7/7**, pg_temp/ROLLBACK only.
An additional end-to-end isolated PostgreSQL + local private-root test
demonstrates signed annotation CREATED→REPLAY with exactly one durable
event, refused altered intent, and denied post-revocation write.
The focused Studio/triage suites pass **55/55** and this added signed
cross-layer test passes separately.
The MiniPC live DB was queried read-only again: the new table is
`NOT_DEPLOYED` and `research_discovery_hit` still has **0 rows**.
These facts prohibit claiming live triage workflow acceptance.
Final full source test run including the signed PostgreSQL acceptance and
read-only HTTP history: **1,992/1,992 Python tests PASS**. No deployment,
commit, push or migration to production accompanied this acceptance.

**Remaining:** reviewed state-transition authority, durable linkage from
HMAC receipts to ledger decisions, human credential governance, current
private-source rights policy, real safe row actions and reversibility,
multi-family queues, bulk-state compatibility, nonempty real Discovery Hits
and runtime migration/deployment acceptance remain open. DP-417 and all
AC-417.1–.4 stay **IN PROGRESS / unchecked**.

### Signed receipt-to-ledger reference — 2026-10-09 follow-up

An additional `attestation_receipt_id` is persisted in the same append-only
triage row, nullable only for explicitly **unattested** DB primitive writes.
It has a strictly bounded `triage-receipt-<sha256>` shape and unique constraint;
`record_attested` verifies an active credential-bound local receipt before
inserting it. CAS and idempotency replay compare the persisted receipt ID as
well as actor, scope, intent and request digest; attempting to replay a signed
row via the unsigned primitive yields `IDEMPOTENCY_CONFLICT`. It cannot
rewrite, duplicate, strip or substitute the immutable receipt link.

This is a **private, cryptographically verifiable pointer**, not on-DB proof
of the HMAC, complete reviewer governance, rights approval, workflow-action
authority or a public safety sign-off. The reader still deliberately reports
`reviewer_identity_attested=false` because it has no credential authority root
and cannot establish live revocation or reviewer eligibility. Direct public
projection remains denied. Updated migration/schema, privacy classification,
SQL canary and isolated PostgreSQL tests cover this source-only addition.
The new migration still has not been installed on production, and every
AC-417.1–.4 remains unchecked.

### 2026-10-09 attestation read-race hardening

The off-DB triage verifier now opens receipt and credential subdirectories
relative to a previously checked root directory descriptor, checks their
inode identity, and revalidates the receipt HMAC plus current ACTIVE
credential immediately before returning a proof. Deterministic local
regressions reproduced and blocked four race cases: credential revocation,
receipt replacement and two root path swaps. This tightens the private
identity boundary while preserving the append-only receipt contract. It
cannot provide atomic revocation across the separate credential filesystem
and PostgreSQL ledger. This source-only hardening does not deploy the triage
migration, authorize actions or close AC-417.1–.4.

### 2026-10-09 private triage history continuity

The read-only private history now reads `count(*)` together with
`MAX(revision)` in one PostgreSQL statement snapshot. The reader rejects
gaps, truncated pages and malformed counts, checks consecutive revision
numbers relative to the cursor, and keeps the internal count out of API
responses. Local ephemeral PostgreSQL tests verified ordinary pagination,
cross-Collection isolation and detection of a deleted internal event after
temporarily disabling the append-only protection on the **ephemeral test
schema only**; those protections are never disabled in production. This
does not install the pending DP-417 production migration or close its ACs.

### 2026-10-09 stale triage-history lineage privacy correction

An existing append-only history reader regression was reproduced against
**real SQL on an ephemeral PostgreSQL cluster**: two synthetic annotation
rows remained readable (including head revision) after the Hit's
Attempt/Query lineage was deliberately made inconsistent, because its
Collection ID still matched. The scoped reader now gates paginated
selection, MAX(revision) and COUNT(*) on `lineage_ok`, returning
`head_revision=0`, `results=[]` and
`DISCOVERY_LINEAGE_MISMATCH` for incoherent lineage. Its presenter
also rejects false-lineage read results containing private decisions
or revision counts. RED→GREEN tests included actual disposable
PostgreSQL mutation and an adversarial injected response; no live
database write occurred. This does not certify reviewer rights,
other queues, bulk transitions or the uninstalled production
migration. DP-417 remains IN PROGRESS.

### 2026-10-10 — Live MiniPC migration and private Inbox API integration

The previously pending `20261009-add-discovery-triage-decisions.sql` migration
is now **installed** on MiniPC PostgreSQL. A complete pre-migration backup
(SHA-256 `abf9a1ae5d0bc64a2d0e677c36e25693d63823bbaf7e652718dde3611e01d3be`)
was restored into a disposable database and the exact migration applied
**twice**, going from 99 to 100 tables without replay drift. Production
received the same additive migration twice with `ON_ERROR_STOP`. The
post-migration governed backup `20261010T110415Z` passed a full disposable
restore with exact table row-count parity; Cloudflare/web units and public
projection/static artifacts remained unchanged. No live Discovery Hit or
triage review was created.

The source-backed, bounded `DiscoveryInboxWorkflow` read model is now wired
to authenticated **loopback-only** `POST /v1/discovery/inbox`, and a
Collection-scoped form in the operator Studio page. Request shape accepts
exactly `collection_id`, optional `limit<=30` and optional `after_id`;
host/origin, bearer token, HTTP no-store, CSP and read-only PostgreSQL
boundaries are unchanged. Results contain only run/attempt/query/manifest
references, status/currentness, and inspectable blocker/retry codes; no
source URLs, unreviewed text, credentials, write authorization or public
publication authority is supplied.

Focused Mac HTTP/SQL validator/queue tests **40/40 PASS**; real Chrome
private workspace keyboard/regression PASS; repository-contract and
diff checks PASS. MiniPC production read-only Inbox SQL runs successfully
against the new table and reports zero rows, matching zero Discovery Hits
and zero real triage annotations. This proves installed schema and query
readiness, **not** a real reviewed or rights-authorized triage decision.

DP-417 remains IN PROGRESS and AC-417.1–4 unchecked: real authorized
Discovery records, independent reviewer action authority, all queue
families, and atomic safe bulk transitions are still required.

**MiniPC deployed-source read-back:** Four new source/test/document files from
commit `830f9a0162be3e5eb86e37053d2db586457c9827` were checksum-synced
with exact parity and preexisting-file rollback backups. An actual ephemeral
`127.0.0.1` Studio HTTP server reading the real production PostgreSQL returned
**200** for an authenticated Collection-scoped Inbox query with zero records,
**401** without the bearer token and **422** for an unauthorized `publish`
field. The response preserved `no-store, private` and false
publication/action authority. MiniPC focused suites ran **40/40 PASS**
(one skip). Both public static HTML and approved projection SHA-256 stayed
byte-identical, and Cloudflare/web systemd units remained active. No
operational database row was written or review authority inferred.

### 2026-10-10 — Current DB-derived bulk compatibility preview

Authenticated loopback `/v1/discovery/bulk-preview` re-reads 1–10 exact
Collection-scoped Hit IDs in **one SQL snapshot**, checks persisted
run/manifest/attempt lineage and triage ledger revisions, and refuses
missing or mixed review states. Only `NEEDS_REVIEW` or `DEFERRED`
non-authoritative annotation may be previewed. The result is `DRY_RUN_ONLY`,
never a durable action, rights/reviewer permit, promotion or publication.
Tests include ephemeral PostgreSQL, cross-state refusal and HTTP 200/401/422.
Isolated MiniPC source 44/44 focused tests passed without a production write.
Other queue families and actual reviewed transitions are absent, so ACs remain open.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** **AC-417.1–.4 OPEN.** Preserve append-only triage ledger; MiniPC migration **already installed** 2026-10-10 with backup/replay and private loopback inbox HTTP 200/401/422. Current persisted Hit rows zero. `/v1/discovery/bulk-preview` handles 1–10 compatible Hits read-only and explicitly `DRY_RUN_ONLY`.

**Target delta and remaining acceptance:** Finish all genuine queue families (changed capture/entity/candidate/coverage/quarantine) with exact provenance, specific unblock actions, real authorized conflict-detecting durable transitions/replay and state-compatible bulk. A private annotation is not reviewer approval. Wire to future unattended machine research path under B authority rather than assuming a human will empty text queues.

**Phase / dependencies:** Phase 1/2; hard actual discovery/capture/candidate state plus reviewed authority, A-NEW-08; soft B/D; Studio ingest owner.

**Related future specifications (separate ownership):** DP-242, DP-319. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.

### 2026-10-11 — Private triage Run-to-Manifest digest admission fence

The existing database-backed private annotation writer had a demonstrable
provenance gap: its `scope` CTE joined Hit→Run→Manifest→Collection and
Attempt→Query, but did **not** verify the Run's recorded `manifest_sha256`
against the Manifest's digest. Consequently a mismatched Run could still
receive a new `DEFERRED` (or `REJECTED`) private annotation, exposing its
current revision and claiming an in-scope triage action. The already-existing
read-only Inbox recognized this mismatch as `manifest_digest_ok=false`, so
the write admission path was weaker than the inspection path.

The writer now requires matching Run/Manifest digests in the scoped join and
holds `FOR SHARE` locks on Hit, Run, Manifest, Attempt and Query through the
transaction before inserting. A stale/mismatched chain yields generic
`SCOPE_NOT_FOUND` with **null revision**, zero appended rows and no write
authority. The result SQL also masks previously matching idempotency-key
replays' revision and attestation linkage when the *current* provenance scope
has become invalid. Restoring the same digest permits an exact replay of the
original immutable row, not a second annotation. The migrated database's
existing direct-SQL trigger has **not** been modified; this additional guard
applies to the `StudioDiscoveryTriageStore` path, not arbitrary privileged SQL.

Adversarial RED: a real **disposable PostgreSQL** fresh-schema fixture first
accepted the mismatched-manifest new annotation (`CREATED`, expected
`SCOPE_NOT_FOUND`). A follow-up stale exact-replay assertion exposed a second
leak in the SQL's result revision computation; the source correction closed
both facets without weakening normal CAS/replay. GREEN: 30/30 focused
triage store/schema/signed-attestation/history tests PASS, including actual
disposable PostgreSQL writer/reader and competing attempts; `git diff --check`
PASS. No MiniPC, production DB writes, licensed-source review, credential use,
provider calls, approval, promotion, publication, commit, push or deploy.

**AC-417.1–.4 remain unchecked / IN PROGRESS.** This local source fix is not
proof of authenticated reviewer action authority, rights/licensing clearance,
all real queue families, safe bulk transitions, client authorization, current
MiniPC readback or direct-SQL constraint parity. Remaining acceptance still
requires those independent end-to-end/runtime gates.

### 2026-10-11 — NEW private changed/blocked Capture queue family (source-only)

Independent implementation in **only**
`poc/dichiarazioni_pubbliche/studio_discovery_triage_reader.py` plus
NEW `tests/test_dp417_queue_family_next.py`. This is **not** the
earlier Run→Manifest annotation-writer digest admission guard:
that writer/store/ledger, existing HTTP routes and migrations were
left unchanged. A new pure read-only entry point
`read_capture_triage_queue(store, collection_id, limit, after_capture_id)`
uses PostgreSQL `BEGIN TRANSACTION READ ONLY` and one scoped
snapshot. The store must be supplied by the **existing authenticated,
private, read-only Studio context**; this function does not authenticate
an operator, expose a new route or grant actions.

Unlike a cached/fabricated Inbox counter, the SQL joins the **exact
Collection → INCLUDED Collection-Content → Content Capture** path and
orders Capture snapshots per Content by `(observed_at, id)` to derive
the current Capture and persisted **previous_capture_id**. It returns
only exceptions: (a) a changed current Capture with a predecessor, or
(b) the current Capture in `QUARANTINED`/purge/active hold/failed
archive state. A Content with a single ordinary `CAPTURED` row is
**not** invented as a changed Capture; a removed Collection membership
does not expose its past Capture. One persisted latest lifecycle event
ID is attached when present, without reading private event receipts.
No URL, source body, text, query, provider receipt, raw SHA, reviewer
or model output enters the response.

The private output is bounded to **1–30** rows, ordered by exact
Capture ID, with `LIMIT limit+1` pagination and a cursor that must
itself still belong to the *current eligible Collection-scoped queue*.
Foreign, revoked/stale and previous-version cursors fail closed.
Cases are `CHANGED_CAPTURE` with
`CAPTURE_CHANGE_REVIEW_REQUIRED` or `BLOCKED_CAPTURE` with exact
`CAPTURE_QUARANTINED`, `CAPTURE_PURGE_PENDING`,
`CAPTURE_BODY_PURGED`, `CAPTURE_HOLD_ACTIVE`,
`CAPTURE_ARCHIVE_FAILED` or `COLLECTION_NOT_ACTIVE` codes and
explicit *proposed* retry prerequisites. **Every row** retains
`PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED` and
`CAPTURE_REVIEW_AUTHORITY_NOT_EVALUATED`. Read-only,
`triage_action_authorized=false`,
`publication_authority=false`, and `rights_clearance=false`
are immutable response boundaries. No safe bulk approval, automatic
capture retry, merge, promotion or public publication is inferred.

TDD reproduced **RED** on the missing new queue reader/export;
**GREEN 6/6** dedicated cases including actual fresh
**disposable PostgreSQL with canonical `db/schema.v1.sql`** and
synthetic persisted Content/Capture/Collection/Lifecycle rows,
multiple Content versions, quarantined other-Collection Capture,
removed member, unchanged single Capture, rights hold reclassification,
non-active Collection, exact scoped pagination, and stale/foreign
cursor refusal. A real PostgreSQL **SELECT-only role** separately
executed the reader successfully while UPDATE was permission-denied.
Contract tests cover strict argument/results, injected private/source
fields, invalid status, malformed lineage, and generic store failure
without credential leakage. No test was run against production, no
provider was called and all PostgreSQL writes were to a temporary
disposable cluster stopped after the run.
Adjacent scoped Discovery-history/Studio operator-queue/Inbox workflows
plus this new suite: **37/37 PASS** on Mac, including PostgreSQL cases;
targeted Python `compileall` and `git diff --check` also PASS.
These are source-only local tests, not full-suite or live-runtime proof.

**DP-417 stays IN PROGRESS, original AC-417.1–.4 all unchecked.**
This provides real source-level partial evidence for Capture-family
AC-417.1/.3 only, not for every Discovery/entity/candidate/coverage
queue; no current authenticated API/Studio route is wired, no reviewer
or source-rights authority is established, and no durable safe
action/idempotent replay or cross-state bulk action was implemented.
MiniPC data/runtime acceptance and the other queue families remain
separate gates. No commit, push or production change in this tranche.

Prime independent code review (same source-only tranche): the canonical
PostgreSQL schema enforces `UNIQUE(content_id, content_sha256)`, so two
different Capture IDs with identical source bytes cannot be inserted as a
valid re-observation; an initial attempted negative fixture correctly hit
the existing uniqueness constraint and was **not** treated as a reader bug.
An actual missing queue case was then reproduced: a single persisted
Capture with `rights_status=REVOKED`, normal status and no explicit hold
vanished from the new operator queue (**RED**). The reader now includes
`REVOKED`/`EXPIRED`/`DENIED` source-rights statuses even for the first
Capture, emits `BLOCKED_CAPTURE` with precise safe blocker
`CAPTURE_RIGHTS_<status>` and an explicit independent new rights-decision
prerequisite; it grants no clearance or action permission (**GREEN**).
The new disposable-PostgreSQL regression and adjacent focused suites
passed **25/25**; targeted Ruff F821/F823 and diff check passed. This
does not create source-rights authority, authenticated HTTP wiring,
live MiniPC acceptance or any DONE AC.

### 2026-10-11 — Authenticated loopback Capture queue + exact Collection/Passage lineage HTTP

The pre-existing source-only `read_capture_triage_queue()` and
`StudioOperatorQueues.inspect_collection_passage_candidates()` are now
reachable through **two distinct, POST-only, token/Origin/Host-authenticated,
loopback-only, read-only** Studio routes added solely to
`studio_local_api.py`:

- `/v1/discovery/capture-queue` accepts exact `collection_id`, bounded
  `limit=1..30`, optional `after_capture_id`; it reuses the persisted DP-417
  changed/blocked current Capture queue, parent-valid cursor, actual lifecycle
  event ID, predecessor ID and reason/retry prerequisites. It never implies
  rights, triage write, reviewer or publication authority.
- `/v1/collections/passage-lineage` accepts exact `collection_id`,
  `content_id`, `capture_id`, `passage_id`, bounded `limit=1..30`, and optional
  `after_statement_id`. It invokes the already tested DP-416 Collection
  membership→Content/Source→exact immutable written Capture→Passage selector→
  Statement Candidate→Claim Candidate join in a single read-only PostgreSQL
  snapshot. It exposes only persisted references, states, locator hashes and
  bounded pages, not private wording or source URLs. The existing
  `/v1/collections/passage-candidates` route is unchanged and NOT reused as
  a fake capture-specific lineage proof.

Both use the existing `StudioLoopbackServer` bearer-token, exact loopback
Host/Origin, JSON body-size/type, method and no-cache/CORS-denial gates. The
new Capture queue uses `_StudioQueueReader`, which inherits the existing
`_StudioReadOnlyDb` PostgreSQL adapter (`default_transaction_read_only=on`,
statement/lock timeout and generic error sanitization). There is no new
privilege, database writer, authentication cookie, public endpoint, UI change,
machine analysis/approval or production deployment.

**Real local RED→GREEN:** NEW `tests/test_studio_auth_vertical_next.py`
starts an actual `StudioLoopbackServer` on `127.0.0.1`, reuses the canonical
schema-v1 disposable PostgreSQL Capture queue fixture and adds synthetic
persisted Source, written Capture Passage, two Statement Candidates,
Statement–Passage bindings and a Claim Candidate. Initially both routes
returned HTTP **404 (RED)** with a correct token; after wiring they return
HTTP **200 (GREEN)** with authentic PG data. Tests additionally refuse a
missing token (401), foreign/wrong Host and Origin (403), invalid method,
unexpected write-like fields, wrong Collection/Content/Capture/Passage,
foreign/stale page cursor and removed Collection membership (422). Capture
rights revocation becomes `BLOCKED_CAPTURE` with its persisted reason and
never grants triage permission; Content rights revoked/active Capture hold
likewise retain explicit blockers while rights/publication flags remain false.
No fixture privacy token, raw passage/body, URL, source metadata or normalized
candidate statement/claim is returned. An attempted `UPDATE` through the
new endpoints' `_StudioQueueReader` PostgreSQL connection is refused.

The original **AC-417.1–.4 stay OPEN**: this is a genuine private runtime-
shaped read-only HTTP vertical slice, not all Entity/Candidate/Coverage/
quarantine queues, authorized append-only triage transitions/bulk replay, a
reviewer identity or lawful source-usage permit. The real MiniPC has no new
accepted queue/event canary from this tranche; Studio visual/manual
accessibility and approved end-to-end publication are not demonstrated.
The DP-416 Collection→Candidate operator navigation/rights/UI/MiniPC ACs
likewise remain OPEN. DP-418 source-bound persisted review comparisons and
promotion decisions were **not** fabricated or added to these read-only routes.

Final local proof: `PYTHONPATH=poc python3 -m unittest
tests.test_studio_auth_vertical_next tests.test_dp417_queue_family_next
tests.test_studio_operator_queues tests.test_studio_local_api -q` **48/48
PASS**, including the actual temporary PostgreSQL/live localhost HTTP test.
`python3 -m compileall -q poc tests`, targeted Ruff lint and scoped
`git diff --check` PASS. The new test file was Ruff-formatted; the pre-existing
`studio_local_api.py` file itself already failed Ruff format --check at HEAD,
so no unrelated whole-file formatter churn was introduced. No full-suite,
MiniPC, deployment or production-data success is asserted.

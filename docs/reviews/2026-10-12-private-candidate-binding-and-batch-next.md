# 2026-10-12 — Studio Candidate CAS and durable media/history/cost tranche

## Baseline and lanes

Authoritative Mac Studio main/origin-main was exactly
52e4391b31344c35ffdebaed5c8a35fd4bf6bc06, clean
one-worktree, empty stash, 90 DONE/72 pending and NO-GO/49.
Four existing sleeping Chat On Steroids agents were reused with
exclusive paths: DP-419 media Capture/Segment PG migration,
DP-516 historical checkpoint, DP-514 monthly liability and
DP-440 private synopsis browser. Prime owned separate DP-418
Candidate authenticated writer and DP-419 HTTP/UI integration.
Every worker scope froze before prime committed it. No
prior DP-416/417/418/419/440/514 feature was repeated.

## Candidate: from private Collection lineage to signed persistent intent

The previous DP-418 real PostgreSQL receipt writer and
read-only historical Studio inspector lacked a usable signed
POST in the private browser. New opt-in extension to
studio_local_mutation_api adds /v1/candidate/decision-annotate
**only when the independently launched private annotation
service specifies --enable-candidate-review-intent**. The
default read-only Studio and annotation-only listener do not
accept that route. This path requires bearer, loopback
Host/Origin and exact pre-issued off-database DP-310
PublicationReviewEvent+credential identity receipt, and a
source-version-bound CandidateDecisionRequest with expected
revision. Review event JSON and opaque receipt are supplied by
the operator; the browser cannot sign or issue them.

It invokes the existing real DP-418 canonical
Candidate→MatchRun→Passage→Capture SQL row-lock CAS,
immutable event/idempotency and current rights validation.
The private Collections UI can open a current persisted
Claim Candidate, prefill only Collection-bound Claim Candidate,
Passage, Capture ID/SHA and clear prior signature fields. The
operator independently selects the current MatchRun, input
fingerprint, expected revision and signed event; after
CREATED/REPLAY the form prepares the separate read-only
receipt inspector. Missing permissions never convert a
HOLD/REJECT/REVIEW_CREATE/REVIEW_LINK **review intent** into
Claim promotion, factual verification or publication.

Adversarial RED→GREEN caught the null receipt on a rights
withdrawal: after an authentic reviewer event is signed,
Capture can become REVOKED before the PostgreSQL transaction.
The DB rightly returns HELD_SOURCE with no receipt_sha256.
The HTTP/UI now displays this blocked state without fabricating
any receipt or claiming a successful write. Real disposable
PostgreSQL + bearer-token HTTP tests cover signed create,
restart/replay, modified payload, cross-request scope, stale
source, revoked credential, no-token/wrong-token, and
disabled writer. The JavaScript DOM/async regression covers
typed POST, no arbitrary event rendering, logout scrub and
cancelled late responses. A bounded **real Chrome** keyboard
test exercises the new Candidate form, response presentation,
return to private read-only receipt form and logout against
synthetic loopback JSON. Chrome's mocked POST is not a real
reviewer attestation; the PG HTTP suite separately verifies
that authentication boundary.

## Media: actual Capture/Segment metadata with revocable state

DP-419's new additive migration
db/migrations/031_media_capture_segment_binding.sql links
exact Content/Capture SHA and canonical Segment ID/time/hash
with composite foreign keys, database guard triggers and
append-only ATTEST/HOLD/REVOKE events, serializable CAS,
independent writer racing/restart and current source/Capture
revocation readback. It deliberately records an
**operator-supplied metadata assertion**, not proof that a
licensed media file yielded the transcript or voice identity.
It therefore always denies rights clearance, seeking and
publication. The existing canonical Passage FK limitation
is not silently bypassed.

Prime integrated the new SQL STABLE read function into
read-only Studio /v1/media/binding and the private Catture
panel, using exact ID/contract validation, current hold
reasons and strict scope; no public route/media player.
Actual PostgreSQL + bearer HTTP tests show metadata,
revocation after first read, wrong/extra body and denied
anonymous requests; the Node UI test confirms no secret
source/body/URL leak and clearing on logout.

## Operations and v3

DP-514 adds canonical PostgreSQL month liability
attribution and append-only CAS observations against
DP-512 provider receipts and DP-513 operation-ledger
parity; UTC/Rome boundary, late/UNKNOWN liabilities,
refund claims, conflicting receipts and repeat/restart
cannot become an invented EUR invoice or owner spend
authority. No paid attempt dispatched.

DP-516 adds restartable canonical PostgreSQL historical
batch checkpoints over Person, Source, Content Capture,
Passage, version and sole-current-rights leaf with CAS,
strict original-vs-translated digest boundaries and
bounded replay/rollback. It requires a real signed first
DP-443 pilot; all dispatch/publication flags stay false.
No historical item was actually acquired.

DP-440 adds a private noindex synopsis browser reader
which connects the already pinned Person×Topic×Statement
citations into bounded accessible keyboard/fragment
navigation and distinct literal quotes and synopsis
sentences. It executes Python source fixture→TS reader→
isolated Astro SSR and performs independent epoch and
withdrawal checks after rendering. This is not a new
public route or a valid external editorial clearance.

## Independent tests and four-host reconciliation

Worker-local and prime verification included real PG17
fresh schema/additive migration, CAS races, rights
withdrawals and restart tests. The prime separately
verified DP-419 42 PostgreSQL/selector tests, DP-516
51 checkpoint/batch tests, DP-514 44 billing/usage tests,
and DP-418+DP-419 HTTP/Studio gates. Chrome accepted
the new form against a fake private server; no real
credentials were sent.

Mac Studio is the only known authoritative Git checkout.
MacBook Air was reachable; bounded Code/Projects/src/
Work/Documents/Codex scans found no named additional
checkout. MiniPC responded, non-Git mirror measured
34,652 KiB, web and cloudflared user services both
active, **untouched**. MateBook Linux was again Tailscale
offline and strict SSH timed out; its WIP/stash cannot
be represented as verified. No deletion, backup
alteration, publication, service restart or provider
call occurred: newly recovered disk space **0 bytes**.

## Original ACs and external blockers

No original ticket has all external ACs attested by this
Mac-only tranche. DP-418 lacks qualified independent
editorial authority, approved source rights and accepted
downstream promotion; DP-419 lacks independent media
derivation/licensing and actual player seek; DP-516 lacks
real licensed first-pilot acceptance and production
source captures; DP-514 requires authentic invoices,
FX and paid-usage owner authority; DP-440 requires real
reviewed original sources, true CURRENT issuer and
public cache invalidation. Keep **90 DONE / 72
pending, NO-GO/49**, with no MiniPC deployment.

Final full-suite, benchmark, static demo-only build,
privacy/schema fingerprint, remote head SHA and GitHub
Actions conclusion must be independently checked after
the final commit, never copied from baseline 52e4391.

## Mandatory technical schema, privacy and backup reconciliation

The full suite caught an authentic omission introduced by the
new durable DP-419 migration. The static DP-304 privacy scanner
refused `PRIVACY_UNINVENTORIED_MIGRATION_TABLE`: the two media
binding/event tables had not been folded into canonical
`db/schema.v1.sql`. The DDL now declares both tables and exact
Content/Capture composite FK and range constraints; the ordered
031 migration installs the additional immutability, source and
revocation logic. The **regenerated** privacy field inventory
records 102 tables, **1,266 fields** (+2 tables/+18 fields),
SHA `01e103b1886060d2ccbd0eee8e0e0d98b2019fadd5a06b0d17a61a820a67ab03`;
technical result is `TECHNICAL_ONLY_NOT_LEGAL_CLOSURE`, never
qualified lawful basis or public source clearance.

An adversarial full-suite run then reported **three real
regressions** (3,225 test cases): two backup-rotation tests
rejected checked-in schema table inventory drift and the
restore inventory correctly identified the two new tables as
missing. These two durable metadata tables are now explicitly
part of `deploy/ops/backup.sh` TABLES and `LOAD_BEARING_TABLES`
in `ops/restore_verify.py`; the backup script continues to
compare repository and live PG tables and reject missing
tables rather than quietly skipping them. The precise
backup/restore/privacy rerun is **40/40 PASS**, and the
privacy/media PostgreSQL selection was **43/43 PASS** after
schema repair. No production backup or MiniPC mirror was
modified. A fresh complete test suite must determine the
authoritative post-fix count.

## Final clean post-fix technical acceptance

- Full Python suite after inventory and restore repair:
  **3,225/3,225 PASS**, 293.408 seconds, **60 additional
  tests** relative to 52e4391's 3,165. Includes real disposable
  PostgreSQL CAS/concurrency/revocation, authenticated HTTP,
  102-table backup/restore drill, schema/privacy, and
  historical recovery. Nonfatal fixture ResourceWarnings
  are not a user-provider or production error.
- Independent backup/restore/privacy **40/40 PASS**;
  media-binding + privacy PostgreSQL **43/43 PASS**.
  Canonical private field inventory: **102 tables / 1,266
  fields**, SHA `01e103b1886060d2ccbd0eee8e0e0d98b2019fadd5a06b0d17a61a820a67ab03`;
  status technical-only, not legal closure.
- Astro **115 files** zero errors/warnings/hints; new
  DP-440 source/Topic epoch and rights revoked fixture
  Python→TypeScript→isolated noindex Astro SSR PASS;
  public search index checks PASS.
- Explicit demo-only static build **34 HTML pages**, 8/8
  canonical v3 families, 16 aliases, 618 internal links;
  AC-422.1 live acceptance remains NOT_ATTESTED.
- Real Google Chrome keyboard navigation and DP-418 private
  signed form/response/logout on localhost synthetic HTTP
  PASS. Separately, actual PG/HTTP verified externally
  bound reviewer signature + correct HELD_SOURCE without
  invented receipt; DOM async/logout regression PASS.
- Python Ruff, compileall, repository contract, whitespace
  PASS; illustrative benchmark **5/5 PASS**.
- Release preflight **NO-GO/49**, receipt
  `96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`;
  **90 DONE / 72 pendenti**. No legal/editorial/source-use
  authorities or paid-provider invoice were manufactured.

The final GitHub Actions conclusion must be verified on the
new pushed SHA, not borrowed from baseline 52e4391.

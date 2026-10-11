# 2026-10-12 — Private Studio annotations, media evidence, billing, v3 synopsis

## Starting point and concurrent ownership

Mac Studio main and origin/main initially matched
d5ab8e157ff3e9b0991120f4a494f51c5691ba85, checkout clean,
one worktree, no stash. Exactly 90 DONE / 72 pending tickets,
release NO-GO/49. Previous DP-416/418/437 and past tranches were
reused, not duplicated. Four existing subagents were assigned
independent work (DP-419, DP-512, DP-241, DP-440); one agent's
chat revival failed twice without changes, and an existing
sleeping worker was reassigned to DP-241. A completed DP-512
worker took a second independent DP-513 slice. Prime directly
owned authenticated Studio operation/API/UI integration, code
review and final tests. Exclusive file boundaries protected WIP.

## DP-417: real local signed annotation vertical

The canonical StudioLoopbackServer and its _ALLOWED_PATHS remain
read-only; authenticated POST to /v1/discovery/triage-annotate is
404 there. A distinct explicitly started
studio_local_mutation_api server, bound to 127.0.0.1, requires
private token + operator mode flag + independently preissued
HMAC reviewer credential receipt + exact Collection/Hit/actor/
request-key/decision/revision + explicit UI confirmation.
The complementary offline preissue CLI does not touch the DB.
No bearer token alone can mint a proof.

The private Inbox panel now loads canonical persisted Hit rows,
shows scope/current revision and blocker codes, and lets the
operator select a row to open its independent persisted history
and prefill scope/revision only. The user must supply a request
key and genuinely issued receipt. A POST goes through the
existing real PostgreSQL per-Hit advisory lock, expected
revision CAS, append-only history, independent identity
verification and idempotency replay. A restarted listener reads
the same revision/history; foreign Collection, revoked
credential, edited payload, duplicate fields, stale revision,
cross-Origin, absent bearer and unsafe JSON all refuse.
The response is an independent annotation-only API contract
and deliberately omits actor, receipt secret and request key.
Node DOM regressions prove token logout and stale fetch cannot
repopulate private forms/receipts. No capture, content rejection,
candidate merge, reviewer verdict, provider task or publication
is authorized. This is not a deployed MiniPC editor service;
DP-417's original AC remain open.

## DP-419: honest canonical media timeline vs Capture

The new bounded inspector joins actual canonical persisted
Statement Candidate → MEDIA_SEGMENT_REF Passage → canonical
transcript Segment and separately the requested same-Content
Capture ID+SHA from one PostgreSQL read. API
/v1/media/capture-context and the Catture panel show
canonical milliseconds, duration, Capture hash/status,
retention, purge/hold/body metadata and precise hold codes.
They do not return media URLs/text/headers or start playback.
The canonical Passage constraint makes capture_id and
canonical_segment_id mutually exclusive; **no genuine
Segment→Capture source-version binding exists**. This reader
therefore always reports UNPROVEN and seek_authorized=false,
even for apparently cleared rights. Full media playback AC
remains open, not falsely claimed via a same-Content match.

## DP-512 / DP-513: actual PostgreSQL provider-ledger replay

Real disposable PostgreSQL tests use the full canonical
provider_receipt schema. DP-512 tracks raw receipt fingerprint
and classification revisions through append-only CAS, including
two concurrent backend clients and repeated attempts after
restart. Unknown/nonpriced zero bounds are not measured costs;
recorded measured amounts are not accepted as paid invoices
without a real statement reference and authority. DP-513 reads
a read-only repeatable-read canonical provider snapshot and
reconciles it against the existing QueueExecutionCostStore
consumer and operation_ledger report. Fail-closed on cross-
provider logical operation, duplicate (operation,attempt),
stale original bytes or reclassification, consumer drift and
contradictory attempt history. It separates attempts/retries,
unknown cash, estimated provisional charges, recorded
measured-but-unverified, external plans and unknown local
energy without exposing account IDs, tokens, prompts or
raw provider payload. Both tickets' unverified invoice/
empirical production AC remain open.

## DP-440: source-linked private Person×Topic synopsis SSR

The existing Python reviewed synthetic public-v3 synopsis,
Person, Topic membership and Statement source bundles feed a
new private TypeScript cross-reader with independent CURRENT
pins, release ID/epoch and double-read revocation checks.
Each displayed descriptive synopsis sentence resolves to
exact published original OPINION Statement version, person,
Topic membership, literal quote/date/locator/source hash and
URL; the original quotation is distinct from summary prose.
Python → TS → isolated Astro SSR with noindex passed with
source/rights/topic withdrawal and epoch race negatives.
No public website route, LLM, model inference or fake
editorial endorsement was enabled; original AC remain open.

## DP-241: durable source investigation with serializable PostgreSQL CAS

The existing deterministic DP-241 recovery planner now has an
independently gated disposable PostgreSQL store. A serializable
transaction checks the actual canonical Source→Content→latest
Capture→written Passage with exact SHA, selector and single
effective private rights record; per-plan advisory lock,
expected revision CAS and append-only reserved/completed attempt
events permit idempotent restart and independent writer conflict
detection. It refuses expired/revoked rights, changed Capture,
wrong Passage/Source, reused discovery receipts, replay of an
unfinished costly reservation and unsupported source version.
The existing recovery-timeline planner inspects only local
provenance and conservative remaining attempt caps.

Real disposable PostgreSQL + original DP241/DP319 planner:
51/51 tests PASS, including concurrency, crash/restart,
wrong identity/version, append-only trigger and non-disclosure.
This is not a licensed source lookup, production rights
approval, B qualification or provider execution. All original
DP241.1–6 AC remain OPEN.

## Four-host safety verification

Mac Studio: one clean main checkout, no additional worktree or
stash on initial inspection. MacBook Air: reachable, bounded
search of Code, Projects, src, Documents/Codex and tmp
directories revealed no named DP Git clone (not a full-drive
claim). MiniPC: reachable; both existing web and tunnel
user services active; /home/udodo/src/DichiarazioniPubbliche.it
is a 34,652 KiB non-Git deploy mirror, untouched. MateBook
Linux: Tailscale explicitly reports both aliases offline;
strict SSH timed out, so remote WIP and backup state cannot
be verified. No files, processes, worktrees, backups, deploys
or credentials deleted; **newly recovered storage = 0 bytes**.

## Original ticket / launch disposition

No original AC has been deemed closed merely by synthetic
local PostgreSQL or Astro success. Real source use rights,
qualified editorial authority, legal closure, genuine
provider billing/plan and review, public-v3 release,
MiniPC canary and missing Segment→Capture version schema
remain blockers. No paid provider, production DB or
publication was touched. Keep 90 DONE / 72 pending and
NO-GO/49. Record full test, clean Git SHA and final GitHub
Actions run below only after independently verified.

## Post-freeze technical gates

After all seven development commits and worker files froze:

- Mac Studio full Python suite **3,165/3,165 PASS** in
  224.553 seconds (**+66** from d5ab8e1's 3,099).
  It includes genuine disposable PostgreSQL concurrency,
  source-rights/CAS/restart, signed private HTTP, and
  actual PostgreSQL restore drill.
- Focused Studio/API security suite 38/38 PASS;
  DP241 source recovery + adjacent 51/51 PASS;
  DP513 cost attribution + billing 45/45 PASS;
  media/billing 56/56 PASS.
- The actual private Studio inline JavaScript passed Node
  DOM/async regression including signed annotation POST,
  Inbox→history row scope, typed CAS revision, logout
  and late-response scrubbing, and media-context
  non-disclosure. A new headless Chromium/VoiceOver run
  of the added mutation UI was **not** attested; prior
  DP416 Chrome coverage is not substituted for it.
- Compileall, full scoped Ruff lint, whitespace and
  repository contract PASS. Privacy/schema unchanged:
  1,248 fields, 100 tables,
  inventory SHA
  4291a376e8eed760b9d6c2972ba907375de6ece52b2063719950c37439f2e31f,
  TECHNICAL_ONLY_NOT_LEGAL_CLOSURE.
- Benchmark 5/5 PASS on illustrative synthetic inputs.
  Astro **113 files**, zero errors/warnings/hints.
  Python→TypeScript→isolated Astro SSR v3 Person/Topic/
  Opinion/Synopsis consumers including withdraw/epoch
  negatives PASS; search-index checks PASS.
- Explicit demo-only build: 34 HTML pages, 16 aliases,
  618 internal links, 8/8 canonical v3 families; real
  AC-422.1 acceptance NOT_ATTESTED.
- Release preflight **NO-GO / 49 blockers**; SHA
  96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f.

Publish verification must use the new exact Git HEAD
and GitHub Actions run, not d5ab8e1's previous 11/11.

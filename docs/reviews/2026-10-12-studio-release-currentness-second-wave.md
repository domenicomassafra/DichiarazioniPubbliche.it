# 2026-10-12 — Authenticated Studio and private v3 currentness second wave

## Evidence baseline and ownership

The authoritative Mac Studio Git checkout was exactly
`c16d823a87dba5a54d1b1610c7b93c6b910b886c`,
equal to `origin/main`, clean, one worktree and zero stashes at start.
The earlier `d5ab8e1` baseline was NOT reused as current.
Four sleeping Core workers were assigned exclusive file scopes and
each completed a first wave: DP-439 private Person/Topic/Statement
operator session (worker-21), DP-519 real PostgreSQL Collection
worklist (worker-22), DP-410 private Studio keyboard/reflow in
real Chrome (worker-26), DP-518 PostgreSQL release currentness
(worker-34). Worker-21 then completed a separate original DP-409
same-epoch search-index wire-byte correction in a second wave.
Prime independently implemented and integrated the DP-418
reviewer-write PostgreSQL/HTTP fix, the private read-only JSON
guard and the operator workload HTTP and Studio UI navigation.
No overlapping worker file ownership was overwritten.

## Verified operational defects and new useful paths

**DP-418**: The previously committed `HELD_SOURCE` without receipt
worked only if Capture rights were revoked before the *first*
review. New real PostgreSQL/HTTP RED test proved that, if a valid
receipt already existed, a revocation caused `HELD_SOURCE` to
echo that old SHA. A separately signed conflicting request using
the same idempotency key also exposed the other reviewer's SHA.
The SQL CAS now returns a receipt only on an exact `CREATED` or
`REPLAY`, with a Python postcondition that holds and conflicts
cannot return one. A subsequent unified real HTTP test creates
a signed private Candidate decision, reads it from the *same*
operator server, restarts that server, revokes the Capture and
proves that the write stays HELD while the distinct historical
reader shows WITHDRAWN and the original receipt. No Claim was
promoted or publication authorized.

**Studio read security**: The ordinary read-only Studio API
previously used `json.loads` on request bodies, accepting two
different `candidate_id` keys by silently keeping only the last.
Against a real persisted PG receipt this returned 200 on an
ambiguous foreign-then-valid Candidate request (**RED**).
The shared read-only handler now refuses duplicate JSON keys,
including nested objects, before the canonical reader; 422 and
no receipt is the actual **GREEN**. The signed write listener
already used strict duplicate rejection.

**DP-519**: A disposable canonical PostgreSQL 17 worklist now
reads Collection INCLUDED members, latest Capture, linked
Passage/Statement/Claim Candidates, and current source-rights
leaf in one bounded `REPEATABLE READ READ ONLY` snapshot.
It offers stable Content-ID keyset pages with revision-sensitive
cursors and actionable rights/hold/capture/candidate reasons;
never raw text, source URL, owner note, simulated owner time,
textual review permission, licensing or authority.
An opt-in `/v1/operator/workload` route on the private Studio
loopback verifies bearer/Origin/Host and input contract before
calling the strict **disposable-only** adapter. With no adapter
the default Studio route refuses (503), never auto-connects
production PostgreSQL. In the Collections panel operators can
now inspect bounded current work and jump from a row to its
existing Capture/Passage/Candidate navigator. Browser session
and token changes clear all worklist metadata.
Real PG/HTTP tests exercise fresh records, different Collection,
revoked Capture, pagination, malformed key/limit, absent
authorization and default-off guard. The callback is scoped by
the single private Studio bearer and is NOT independent qualified
operator identity or per-tenant authorization.

**DP-518**: A disposable canonical PG private release selector
adds durable CAS and row-lock currentness checks over existing
DP-320 revocation, source version, outbox and ACK identity.
Atomic selection/replay/restart and rollback races have tested
negative states; no CDN/host signed ACK, public publication
authority or live MiniPC deployment was fabricated.

**DP-439**: Python original source fixtures now travel through
the previous private original opinion / Person × Topic / dated
synopsis readers into one bounded, noindex SSR operator session
with shareable Person+Topic URL, links and keyboard native
anchor focus. Independent actual-current release inputs are
checked before and after asynchronous work and after render.
Mixed source/version, withdrawn or re-pinned revoked Topic,
late epoch, wrong Person/Topic and expired pins fail closed.
No public route and no ad-hoc inferred stance or person score.

**DP-409**: Opt-in pinned search accepted public JSON asset wire
bytes with duplicate keys. JavaScript's parsed-object SHA
ignored the first duplicate `records` or nested `title`,
which could contain withdrawn text, even while the independent
CURRENT index/projection hashes and release epoch matched.
A RED adversarial synthetic old/current index fixture exposed
the issue. The reader now requires exact canonical serialized
wire bytes (allowing the static endpoint's one LF), rejects
duplicates/noncanonical payloads and preserves the separate
independent pin and race checks. This does NOT attest CDN
integrity for clients directly downloading a compromised asset.

**DP-410**: Actual desktop Google Chrome in an isolated
headless 320px mobile emulation reproduced overflow of the
Candidate signed-event textarea and missing form-result
association. CSS width/overflow, explicit aria-describedby,
status live-region and privacy/noindex/logout improvements
are now exercised by a real keyboard-submit test. This is
NOT VoiceOver, physical iOS or qualified WCAG AA acceptance.

## All 72 pending tickets and 49 launch blockers

Source-of-truth review used the literal original ticket files
and their Status/Depends on/Acceptance criteria, not historical
DONE totals. **52 IN PROGRESS**:
DP-214, 215, 229, 233, 234, 235, 236, 237, 238, 239, 240,
241, 242, 243, 244, 301, 304, 312, 313, 314, 315, 316,
317, 318, 319, 320, 321, 405, 407, 409, 410, 412, 416,
417, 418, 419, 422, 429, 435, 436, 437, 438, 439, 440,
512, 514, 515, 516, 518, 519, 701, 703.

**14 FUTURE**:
DP-208, 307, 420, 421, 441, 442, 443, 507, 508, 513,
517, 702, 704, 705.

**6 BLOCKED**:
DP-201, 202, 203, 204, 406, 408.
These are the 72 original open tickets, not additional invented
development tickets. Per-ticket original AC remains authoritative
and is not closed by private synthetic/local acceptance.
In particular DP-443 depends on genuine signed real-source/
qualified editorial/MiniPC reader acceptance and holds DP-516
bulk acquisition. DP-438/439/440 require real approved v3
public assets, and DP-410 needs physical/AT/cold-performance
and MiniPC acceptance. DP-519 remains a private operator
planning capacity seam without an authenticated human review
or licensed photo. DP-518 needs actual owner/host/edge readback.

Preflight's exact **49 blockers** comprise **29 ticket gates**
(DP-201/202/203/204/214/215/229/301/304/307/405/406/
407/408/409/410/412/416/417/418/419/420/421/422/429/
701/702/703/704), **16 open/blocked legal decisions
Q-306-01–16** and **4 absent release artifacts**
(`launch_rehearsal`, `launch_set`,
`prelaunch_closure`, `release_authority`).
The unchanged result is **90 DONE / 72 pending; NO-GO/49**.
Code-only local evidence cannot remove real permissions,
editorial review, law, or production artifacts from these gates.

## Four-host and data-preservation reconciliation

Mac Studio is authoritative; initially one checkout, no
stash/branch WIP, no generated worktrees. MacBook Air was
reachable; bounded Code/Projects/src/Work/Documents/Codex
search found no second named checkout or unique changes.
MiniPC responded; `/home/udodo/src/DichiarazioniPubbliche.it`
is a **non-Git deployment mirror**, measured **34,652 KiB**,
with web and cloudflared user services active; left intact.
MateBook Linux peers were `Online:false` on Tailscale and
strict SSH timed out; remote files/branches/WIP were NOT
verified and no deletion was attempted. Actual newly
recovered disk space: **0 bytes**. No provider calls, personal
files, logs, backup, rollback, runtime processes, release
deployment or signed live editorial actions were changed.

## Acceptance matrix

Proof spans real disposable PostgreSQL 17 transaction/restart,
CAS races, authentic reviewer identity HTTP, duplicate JSON
scope refusal, private worklist bearer HTTP, real Chrome
320px/focus, Python→TypeScript→Astro SSR v3, static pinned
search adversarial bytes, privacy inventory and backup/restore.
Full-suite/CI should only be declared PASS after the final
actual HEAD and GitHub Actions conclusion are independently
verified. Before any live public operation an independently
approved source-rights review, actual qualified editorial
identity and MiniPC/source/API/search/cache currentness
readback remain mandatory. **Release NO-GO.**

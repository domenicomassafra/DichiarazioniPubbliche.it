# 2026-10-12 — Studio PostgreSQL, authenticated decisions and private opinion preview

## Baseline and work allocation

Started on clean main b239d20f505d0c7bdd825fef0b7bbe852ef64d63,
equal origin/main, one Mac Studio worktree, no stash and 90 DONE /
72 not DONE. Four workers were assigned disjoint independent tasks:
three session startups failed without producing code; the fourth
completed DP-418 PostgreSQL decision CAS. Prime authored DP-416
cross-component Studio navigation, DP-437 private Statement preview,
security reconciliation and DP-418 readback integration.

## DP-416: one transactional private research path

Actual local-token-authenticated Studio endpoint
/v1/collections/navigate runs a single PostgreSQL REPEATABLE READ
READ ONLY snapshot: currently INCLUDED Collection member, Source ID,
Content, latest persisted Capture, bounded written Passage selector
and first Statement Candidate/count. Cursor validity is checked
against current Collection membership; never accept an arbitrary
known Content ID to traverse another Collection. Strict output
validation excludes URLs, titles, private Passage/Statement/Claim
text, metadata, credentials and authority flags. Real Studio
Collections UI pages ≤10 contents, ≤3 passages per latest Capture
and jumps to the already persisted exact Candidate/Claim drilldown
via keyboard buttons; clears private state on token/workspace change.

Synthetic-source tests used actual canonical schema PostgreSQL,
real loopback HTTP/bearer/Origin, source/capture/passage/candidate
fixtures, change of membership and rights, foreign cursors and
secret non-disclosure. Real headless Chrome acceptance exercised
keyboard navigation and clearance. Original AC-416 remain OPEN
because authentic licensed Garlasco pilot and real MiniPC operator
approval are absent.

## DP-418: reviewer-attested durable PG decisions and readback

An opt-in isolated PostgreSQL store requires a genuine existing
DP310 local reviewer credential/attested event and exact current
MatchRun/Candidate/Passage/Capture/Content and rights. Advisory
locking, row-level FOR UPDATE, expected revision CAS, immutable
append-only decision receipts and idempotent retry permit two
reviewers to contend without duplicate decisions. Revoked sources,
missing reviewer authority and mismatched source versions block
creation. These are reviewer-intent records, never actual Claim
promotion, identity resolution or publication rights.

New local Studio /v1/candidate/decision-receipt performs a
READ ONLY repeatable-read PostgreSQL query of exact Candidate,
Run, Capture, Passage and receipt request-key, comparing current
source and Capture status against historical decision. Its
keyboard-accessible Collections UI displays only decision code,
revision, receipt hash, and CURRENT/WITHDRAWN history; no
reviewer identity or raw receipt, and no approval/write action.
Missing private PG schema returns unavailable, not empty success.
Real PG tests exercise saved receipt, source revocation after
review, HTTP auth, foreign scope refusal and redacted output.

## DP-437: pinned original Statement opinion private SSR

New opt-in TypeScript Statement-centered read consumes previously
integrated Person, Statement, indexed Topic and source-v3 readers.
It requires independent current release pins before and after
reading; revoked/rehashed/expired and wrong-person results fail.
One endorsed OPINION with no Finding retains original quote,
source hash/version, locator, date and reviewed wording without
inventing a factual verdict. Unknown/private/held Statements
share a generic unavailable response. Genuine Python approved
fixture passes through the TypeScript reader and an isolated
noindex Astro static build. No new public route or authority.
Original DP-437 AC stay OPEN.

## Adversarial gate regression found and fixed

Whole-suite worker run exposed three genuine RED failures:
the private Studio navigation route was missing from the
conditional public-admin surface absence contract. The narrow
read-only private Studio allowlist was updated, also covering the
new decision-receipt path. This does not grant public
account/admin mutation or any review authority. Targeted
conditional and launch-preflight tests recovered GREEN with
NO-GO/49 and unchanged preflight receipt.

## Four-host audit and no-op cleanup

Mac Studio: primary Git checkout with one worktree and no stash.
MacBook Air: reachable, no DP clone in bounded searched Code,
Projects, src, Work or Codex directories (not a full scan).
MiniPC: reachable, non-Git deploy mirror 34,652 KiB untouched;
user web and tunnel services active. MateBook Linux: Tailscale
reports offline and SSH connection timed out, so no claim
about unseen WIP or its backups. No deletions or deployment:
new space recovered 0 bytes.

## External blockers

No authorized source rights, actual qualified editorial review,
legal closure, real producer B contract, authority to migrate
MiniPC production DB or actual public v3 source release. All
new test authority credentials are isolated synthetic fixtures.
Keep original AC of DP-416, DP-418 and DP-437 OPEN and
release NO-GO/49. Final full-suite and CI must be recorded
against the new final SHA, never copied from b239d20.

## Integrated post-freeze gates

After the source and API/UI review readback were frozen:

- Full Python suite: **3,099/3,099 PASS**, 210.037 seconds,
  including actual PostgreSQL concurrency/races, restarted
  SQLite stores, local authenticated HTTP and full restore
  drill. This is 23 more tests than b239d20 baseline.
- Focused DP-418 decision, Studio readback, conditional
  private-path boundary and launch preflight: 38/38 PASS;
  adjacent decision and safety tests 60/60 PASS.
- Real headless Chrome DP-416 keyboard navigation succeeded
  before the new decision-receipt UI. A separate extended
  Chrome run with that later readback did not complete and
  was stopped without touching other Chrome sessions.
  That extension is NOT claimed browser-certified. An
  executable Node DOM/async fake-HTTP regression of the
  actual new inline Studio script verified historical
  decision display, extra-field non-disclosure and late
  response clearing after token logout. Real PostgreSQL
  bearer-auth HTTP verified the same receipt and revocation.
- Python compileall and scoped Ruff F821/F823 passed;
  repository contract PASS. Privacy/schema inventory
  unchanged: 1,248 fields in 100 tables, SHA
  4291a376e8eed760b9d6c2972ba907375de6ece52b2063719950c37439f2e31f,
  status TECHNICAL_ONLY_NOT_LEGAL_CLOSURE.
- Benchmark 5/5 PASS; engineering preflight NO-GO, 49
  blockers, exact receipt
  96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f.
- Astro/TypeScript 111 files, zero errors/warnings/hints.
  Existing v3 Person/Topic/zero-Person and new v3
  original opinion Python→TS→isolated Astro SSR passes,
  search-index checks PASS. Explicit demo-only Astro
  build succeeds: 34 HTML pages, 8/8 v3 canonical
  route families, 16 aliases, 618 internal links.
  AC-422.1 live acceptance remains NOT_ATTESTED;
  no demo page was deployed or declared public.

The CI outcome on the final published SHA is a separate
post-push check and must never be substituted by the
old b239d20 11/11 success.

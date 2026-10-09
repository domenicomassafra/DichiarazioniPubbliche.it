# GOAL INFINITO — Wave 9: private corpus intake safety

Date: 2026-10-09. Source authority: Mac repository, baseline HEAD
`31e78cbd268c49dea0bfe81adfbc7f382896cea6`. No production deploy,
no schema/migration write, no public release, no external credential
substitution or legal approval in this tranche.

## RED → GREEN implementation, reviewed by PRIME

- **DP-214/210**: private Capture batch preflight now applies the actual
  Capture transport's static destination constraints before database
  lookup, and bounds operator JSON manifest input to 256,000 bytes. It
  does not pretend to validate a DNS connection in pure preflight.
- **DP-214/215**: private Candidate preflight requires exact canonical
  persisted Content and rights locator values before model invocation
  and on subsequent guard calls, matching its downstream commit fence.
- **DP-304**: the independent Capture content-state gate fails closed
  when inactive-Collection or forbidden-membership counts are absent,
  negative or have noninteger types; unknown is never coerced to zero.
- **DP-307**: the canonical release parser rejects duplicate PLAN rows
  even if both statuses are identical. No legal decision or launch token
  is inferred from a technically green parser.
- **DP-211**: a malformed `TEXT_POSITION` parent Passage (missing
  Capture, missing/negative offsets or text length disagreement) is
  held before provider work, replay and Candidate persistence.
- **DP-210/209**: reviewed existing private source_watcher and optional
  Vimeo oEmbed patches. The watcher uses vetted public DNS at the
  actual TCP connect, verified peer, hostname-preserving TLS and no
  environment proxy; oEmbed now uses the same handler instead of an
  ordinary urllib HTTPS socket after URL prevalidation. HTTP 200,
  length, JSON duplicate, sensitive receipt and redirect checks stay
  fail closed.

These are bounded deterministic tests and security guardrails. The
same-length *shifted* Passage selector is not independently bound to
immutable Capture canonical text through the present extraction API.
An exact rights-gated reparse/roundtrip or durable immutable selector
proof remains needed; do not assert AC-214.1/.2/.4-.8 or AC-215.9
from these local tests.

## Current read-only runtime truth

Read-only SSH/PostgreSQL on MiniPC: `research:garlasco` PAUSED;
18 included historical Content out of the required 100, 30 existing
`claim:garlasco:*` Atomic Claims; zero Discovery Hits, Captures,
Passages, Statement Candidates, Claim Candidates, and Garlasco Coverage
Needs. No real source was captured or classified as rights-cleared.
The uninstalled DP-417 triage migration remains uninstalled; no new
review authority was created.

## Gates and outstanding authority

Canonical PLAN: 125 tickets = 86 DONE, 24 IN PROGRESS, 6 BLOCKED,
9 FUTURE (39 open); **zero new ticket closures**. M7 is **NO-GO /
41 blockers**. There are 16 undecided legal Q-306 questions, absent
owned release artifacts, real provider canary/rights/corpus/reviewer
work, and explicit owner authority still pending. Do not fabricate
unavailable receipts or treat a fixture as rights clearance.

Prior successful GitHub CI run on the baseline was `37952717336`.
The next code commit, full-suite proof and matching CI outcome must be
recorded independently; no prior CI run certifies these new patches.

## Local validation of this exact source tranche

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2069/2069 PASS** (148.899 s). Expected fixture-only HTTP/socket
  resource warnings appeared; no test failed.
- Full suite restore drill: **PASS** (100-table fixture restoration);
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`:
  **5/5 PASS**.
- `python3 tools/check_repository_contract.py --only tickets`:
  **PASS**. `git diff --check`: **PASS**.
- `PYTHONPATH=poc python3 tools/check_launch_preflight.py --expect-no-go`:
  **NO-GO/41** (unchanged receipt SHA-256
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`).
- `cd web && npm run check`: **0 errors, 0 warnings, 0 hints**
  (81 Astro files). The normal public build refuses to run without an
  authorized `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH`;
  `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build`
  builds **32 local DEMO pages**. This is a compilation check, explicitly
  **not** production-projection or launch acceptance.

The preexisting handoff file
`docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md` is an operator
input and has not been modified. The original four watcher/oEmbed dirty
files were explicitly reviewed rather than overwritten wholesale.

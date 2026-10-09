# GOAL INFINITO — PRIME checkpoint / next-chat handoff

Authoritative repository: `/Users/domenico/Code/DichiarazioniPubbliche.it`.
Read the original owner handoff **in full** before continuing:
`docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md`. This original
untracked owner file must be preserved, not rewritten or silently committed.
Canonical instructions: `AGENTS.md`, `PRODUCT.md`, `CONTEXT.md`,
`ARCHITECTURE.md`, `PLAN.md`, ADRs, and each `docs/tickets/DP-*.md`.

## Verified completed source waves

1. **Wave 9** — `90a154c8813bfe86ddf5f462cbc8a06ffc63b482`
   (`fix(corpus): fail closed across private discovery and candidate
   boundaries`), fast-forward pushed to GitHub `main`. CI
   **37972323989 SUCCESS, 11/11**. Full suite **2069/2069 PASS**,
   deterministic benchmark **5/5 PASS**, restore drill PASS, ticket
   contract PASS; Astro check 0 diagnostics/81 files and **32-page
   local DEMO** build. Detail:
   `docs/reviews/2026-10-09-goal-infinito-wave9-private-intake-security.md`.
   Actual corrections: static unsafe Capture URLs before DB preflight;
   256-kB JSON bound; exact Candidate Content/rights URL canonical
   equality; strict Capture safety counts; duplicate PLAN ticket refusal;
   parent Passage TEXT_POSITION sanity before model; socket-level
   DNS-pinned HTTPS+peer/TLS/proxy/redirect source fetch and optional
   Vimeo oEmbed. No public build or production deploy.
2. **Wave 10** — `bc274f82e4998de34e9851727ecef0dbc2e4e1a5`
   (`fix(review): hold stale triage lineage and candidate operator inputs`),
   fast-forward pushed to GitHub `main`. CI
   **37973191658 SUCCESS, 11/11**, Ubuntu/macOS Python 3.11–3.14,
   clean-clone, frontend, repository contract. Full source suite
   **2072/2072 PASS**, benchmark **5/5 PASS**, restore drill PASS,
   compileall/contract/diff PASS. Detail:
   `docs/reviews/2026-10-09-goal-infinito-wave10-candidate-operator-continuation.md`.
   Actual corrections: 1-MiB Candidate JSON limit; literal PostgreSQL
   boolean `true` for Capture body-ref availability; private DP-417
   triage decision history withheld when Hit/Attempt/Query lineage
   becomes inconsistent, verified via real disposable PostgreSQL SQL
   and adversarial tests. The DP-417 migration is **not deployed**.

Both GitHub CI runs were checked after completion; never use a green
prior run to certify new edits. `main` was synchronized with
`origin/main` at `bc274f8` before the exploratory Wave 11 work.

## Canonical backlog / release

The PLAN parser identified **125 tickets**: 86 DONE, 24 IN PROGRESS,
6 BLOCKED, 9 FUTURE = **39 OPEN**. These waves added **zero DONE**
ticket statuses or uncertified acceptance. Open IDs:

`DP-201 202 203 204 208 215 214 229 233 234 301 304 307
405 406 407 408 409 410 412 415 416 417 418 419 420 421
422 429 507 508 604 606 607 701 702 703 704 705`
(each ID has the `DP-` prefix). The canonical preflight is
**NO-GO with 41 blockers**, stable receipt SHA-256
`890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`:
19 non-DONE release-gate tickets, 16 outstanding Q-306 legal decisions
(14 OPEN/2 BLOCKED), 4 missing owned release artifacts
(`launch_rehearsal`, `launch_set`, `prelaunch_closure`,
`release_authority`), and 2 undecided conditional surfaces
(DP-507/508). **Do not** publish v1.

## Authoritative MiniPC observation (READ ONLY)

Using SSH `minipc` and PostgreSQL `dichiarazioni_pubbliche`,
inside `BEGIN READ ONLY`/`ROLLBACK`: collection
`research:garlasco` is `PAUSED`; **18/100** included Content,
**0/18** have `rights_status=CLEARED`, **30** historical
`claim:garlasco:*` Atomic Claims; **0** Discovery Hits, Content
Captures, Passages, Statement Candidates, Claim Candidates and
Garlasco Coverage Needs. `to_regclass('public.research_discovery_triage_decision')`
returned NULL: DP-417 production migration is not installed. No
MiniPC data, schema, services, published projection or bodies were
modified in these waves. A SQL read cannot grant legal rights.

## Engineering blockers and precise owner inputs

- **DP-214→215 authentic tracer:** obtain a genuine 100-source bounded
  manifest, source role/lineage/time/scope and **individual rights
  clearance**/private acquisition permits. 18 historical included
  Contents exist but zero are cleared. Never synthesize Discovery
  hits, Sources, rights or Candidate/Match rows to fake acceptance.
- **Exact Capture→Passage parent selector:** current extraction rejects
  absent/negative/internally inconsistent `TEXT_POSITION` offsets.
  A same-length shifted offset can still carry a self-consistent
  Passage body/hash; proof requires a rights-gated re-read of immutable
  Capture body, the exact charset/parser version, independent
  excerpt/coordinate roundtrip, a race-safe DB/commit fence and
  explicit bounded failure. Existing
  `capture_pipeline.verify_passage_roundtrip` is a primitive only.
  No fabricated `verified=true` flag, no unreviewed schema rewrite.
- **DP-211/real provider:** authorized owner must supply approved
  OmniRoute credentials/model and documented token cost cap, with
  cost and privacy authority. A fake/mock model is not a live canary.
- **Legal / privacy / release:** all Q-306-01..16 qualified decisions,
  approved reviewer/owner authorities, the four signed release
  artifacts, real supported accessibility/manual screen-reader proof,
  and permissioned DP-417 production backup/migration/rehearsal.
  Nonempty safe Studio workflow and reviewer action control remain
  distinct from read-only inspector/pure unit tests.

## Worker lanes and unsafe-to-commit local drafts

The original worker-2 legal/privacy agent failed to start and produced
no result. PRIME integrated workers' reviewed Wave 9/10 changes as
sole Git publisher. Subsequent worker-1 **Wave 11 legacy DP-407**
demonstrated an actual Chromium RED→GREEN URL/Space-key/focus
repair in **unmounted** `web/src/components/ContentAuditClient.tsx`
with `prototypes/v4-implementation/dp407/test-content-audit-keyboard-wave11.mjs`.
That component is **not mounted by the current public route** (which
uses `ContentRecord.astro`). Both files were intentionally left
**uncommitted**. The local browser proof is valid for a legacy fixture
but not a public DP-407 acceptance; preserve the dirty draft without
smuggling it into a release commit.

Following PRIME feedback, worker-1 was retasked to the **actually
mounted `web/src/components/ContentRecord.astro`** and an isolated
browser test. That lane **delivered** a genuine RED→GREEN real
`ContentRecord.astro` accessibility correction, validated by
an actual 12-moment generated static route in headless Chromium:
timed marker buttons formerly exposed only `2:30` to the Chrome
accessibility tree; their name now includes the already-public
claim. Deep-link, Space keyboard activation, selected detail,
focus, aria-current/expanded and URL state pass. The exact harness
is `prototypes/v4-implementation/dp407/test-contentrecord-real-wave11.mjs`.

A replacement worker-3 independently hardened DP-418's real
`studio_candidate_review.py` persisted match reader with deterministic
run/target/result ID binding, method/feature allowlists,
typed rank/count, and ClaimType/temporal mismatch HOLD semantics.
The shared local API test previously hard-coded a now-invalid synthetic
run ID and was corrected by PRIME to use the fixture's genuine
`RUN_ID`; adjacent test suite **35/35 PASS**. Do not mistake
this for reviewer/cluster promotion authority. Both lanes are
source-only proof, awaiting Wave 11 full-suite and CI.

## Next tranche order

1. Integrate ONLY verified actual `ContentRecord.astro`, real-route
   browser harness, DP-418 matching-read guard, targeted tests and
   the PRIME-owned local API fixture correction; preserve legacy
   ContentAuditClient draft and original handoff uncommitted.
2. Update the exact relevant ticket and PLAN with proof, run full Python suite,
   benchmark, frontend/browsers/restore/contract/preflight as needed,
   and commit only vetted paths. Push fast-forward only through PRIME;
   confirm new matching CI run before claiming integration.
3. After Wave 11, next DAG ticket priority is DP-214→215 immutable
   Capture/Passage selector binding **only after a safe rights-gated
   source-re-read contract**; otherwise DP-418/419 and provider
   adapters are independently implementable, not publishable.
4. Continue DP-214→215 real corpus only **after** real signed source
   rights/owner intent and actual Collection activation, with
   nonpublishing guards and read-only canary first. Never turn a
   synthetically green fixture into production/legal/release authority.

## Post-checkpoint Wave 12 source-only continuation

On baseline `4f0812e`, three disjoint real defects were reproduced
RED→GREEN and integrated locally before publishing:

- **DP-233**: official parliamentary Source Family excerpt text must be a
  verbatim contiguous slice of its own normalized statement. URL/hash/
  ID/version/timing alone no longer permit a forged/other-speaker quote.
- **DP-419**: a private Capture inspector cannot display `SUCCEEDED`
  archive or `PURGED` body status without the canonical persisted
  archive/purge receipt, timing, and coherent lifecycle prerequisites.
- **DP-215**: missing/blank observation review status no longer defaults
  to `APPROVED`; `UNREVIEWED` is explicitly excluded and logged
  `EVIDENCE_NOT_APPROVED` (canonical SQL approved row still accepted).

Evidence: `docs/reviews/2026-10-09-goal-infinito-wave12-parliament-capture-gates.md`.
The final frozen suite is **2083/2083 PASS**, restored 100-table
fixture PASS, deterministic benchmark **5/5 PASS**, repository
contract/compileall/diff PASS, and release remains **NO-GO/41**.
No genuine source rights, new Garlasco Content or Candidate rows
and no production migration were created. The original owner handoff
and legacy orphan UI WIP remain excluded from git staging.
Record matching Wave12 commit/CI separately after publication.

# GOAL INFINITO — Wave 5: DP-214/215 corpus boundary, DP-212 matching, DP-417 attestation

Date: 2026-10-09, Europe/Rome. Technical implementation receipts; **not a release authority**.

## Starting state and provenance

- Authoritative Mac Git `main` started at `8c0e07c` synced to `origin/main`.
  The earlier 25-file DP-417 source tranche was already integrated in commits
  `ed02f31` and `3e3bc76`. No stale working-tree patch was reapplied.
- Untracked owner handoff `docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md`
  existed before this wave. Preserve it; do not include it in a selective commit.
- Live MiniPC PostgreSQL read-only observations: 50 total Content; PAUSED
  `research:garlasco` with 18 included members, 30 historical
  `claim:garlasco:*` Atomic Claims, 0 Discovery Hits, 0 Captures,
  0 Passages, 0 Statement Candidates, 0 Claim Candidates and 0 Coverage Needs.
  The DP-417 migration is not installed in production.

## Executed engineering waves — no release or live data mutation

1. **DP-212 / DP-214 matching:** reject private cluster proposals for exact
   text with explicitly conflicting ClaimType/reference time. Keep the pair
   reviewable as `HOLD`, preserve comparison features, and version the
   disposition policy inside the run fingerprint to prevent stale replay.
   Verify replay state, Candidate/fingerprint, target set and rank sequence.
2. **DP-214 / DP-215 readiness:** report current exact-family, unexpired,
   reviewed private-capture rights separately from any rights row; count
   active Source Intelligence profile/role/scope and derivation reviews.
   Reject inconsistent provenance/family/count snapshots. Read-only SQL was
   executed against the authoritative MiniPC Garlasco Collection; all 18
   remain missing active Source Intelligence profile/role/scope.
3. **DP-209 / DP-214 Discovery lineage:** refuse a noncanonical persisted
   Content URL despite a DB Hit/Content equality; SQL expression parameters
   now accept only the appropriate Collection, Content and URL identifiers.
4. **DP-214 Capture preflight:** reject duplicated JSON manifest keys and
   enforce bounds, unique Content IDs and canonical locators, version and
   optional fingerprint when callers construct direct `CaptureBatch` objects.
   Invalid batches abort before store reads or network acquisition.
5. **DP-417 triage credential race:** bind child directories to the verified
   root file descriptor and recheck receipt MAC + ACTIVE credential before
   returning an attestation proof. Four race regressions were first observed
   RED on prior code and are GREEN after the fix; this narrows TOCTOU, but
   does not make DB/file credential revocation globally atomic.

The two parallel workers owned disjoint code/test files and made no commit,
push, deploy, production migration or data mutation. Prime reviewed and
integrated their results in the shared `main` working tree. Tests here
exercise fixture/isolated boundaries unless specifically noted as MiniPC
read-only observations, and cannot substitute for a real Garlasco tracer.

## Gates and remaining acceptance

- Canonical backlog unchanged: **125 total; 86 DONE, 24 IN PROGRESS,
  6 BLOCKED, 9 FUTURE; 39 open**. DP-214, DP-215, DP-417 still
  IN PROGRESS; no new ticket AC is closed by safety regressions alone.
- Preflight: **NO-GO, 41 blockers**, receipt
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
  Sixteen Q-306 qualified dispositions, rights/private relevance for genuine
  sources, 82 more authentic Garlasco Contents, provider/cost canary,
  manual assistive QA, owner source/release decisions and four launch
  artifacts remain outstanding.
- No production DP-417 migration, provider calls, source-body captures,
  Claim promotion, public projection writes, release or deployment.
- Prior published source CI before this wave: run `37930628706`, SUCCESS
  on commit `8c0e07c`. A green prior CI does not certify new work.

## Validation and integration

Focused matcher/schema 16/16 PASS; focused Capture/Discovery/Auth 29/29 PASS;
readiness/Studio/Discovery subset 44/44 PASS; deterministic benchmark 5/5
PASS; compileall, repository ticket contract and diff --check PASS.
**Full Python suite 2,016/2,016 PASS (111.98 s)**, including the restore drill
`RESULT: PASS` and privacy inventory `100 tables / 1,248 fields`, technical
classification only. The source commit SHA and its CI must be recorded
separately when observed; do not infer success from prior commits' CI.

## Next steps

1. Finish reviewing worker changes and the full repository suite; make a
   selective Git commit of only wave-owned source/tests/docs once clean.
2. Check GitHub CI for the exact new source SHA after the sole publisher push.
3. Continue from source-family and rights prerequisites to a **real** one-item
   Discovery Hit → Capture → Passage → Candidate → matching/review tracer,
   with explicit operator permissions and zero public effects. No fixture
   can close DP-214.1/.2/.4-.8 or DP-215.9.

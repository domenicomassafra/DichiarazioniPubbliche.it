# Studio DP-415..419 — preparatory slice acceptance receipt (2026-10-08)

## Scope and truth boundary

This change advances **all five DP-415..419 tickets to IN PROGRESS**, not DONE.
The prior public release remains **NO-GO**. No production public projection,
legal decision, source approval, identity approval, provider permission or
publication authority is created by this change.

- The **browser** now has interactive, React-hydrated **fixture-only**
  Corpus search/filter/selection, Inbox status/provenance inspection and
  Collection scope/status inspection. The existing Verify layout still has
  exactly three panes. No action button is wired to persistence or publication.
- The **private operator-side Python modules** use existing DP-116
  `CorpusSearchStore`, DP-212 `CandidateMatchingStore` read methods and
  DP-210 `CapturePipelineStore.find_capture`. They return bounded **metadata
  and references only**. They do not create an HTTP server or static export.
  No raw transcript, candidate text, evidence body, reviewer note, secret,
  URL or database error is included in a receipt.
- Match suggestions are expressly `currentness=UNVERIFIED` with no review
  or publication authority. Version comparisons are only for two known exact
  hashes of the same persisted Content; absent/tampered versions fail closed.
  Missing private view, lack of approved rights or an offline backend never
  becomes fabricated empty-success or permission to promote.

## Candidate verification

| Check | Observed result |
|---|---|
| `PYTHONPATH=poc python3 -m unittest discover -s tests` | **1833/1833 PASS** |
| DP-415/418/419 focused Python tests | **11/11 PASS** |
| MiniPC isolated `/tmp` candidate, no production DB/provider credentials | **11/11 PASS**; directory removed |
| `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` | **5/5 PASS** |
| `python3 -m compileall -q poc tests` | PASS |
| `cd web && npm run check` | **0 errors, 0 warnings, 0 hints** |
| `cd web && npm run check:design` | PASS |
| `cd web && node --experimental-strip-types scripts/check-studio-v3.mjs` | PASS |
| `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build` | **32 routes**, no `dist/studio`; public build noindex |
| Above plus `DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY=1` | **36 routes**, fixture-only Studio explicit; check-studio-v3 PASS |
| Demo checks route/quality/browser/performance | PASS |
| Repository tickets/licensing/contributor acceptance | PASS |
| Launch preflight `--expect-no-go` | **NO-GO, 41 blockers** (unchanged) |
| `git diff --check` | PASS |

The normal production Astro build without an approved
`DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` still correctly refuses
to run. The two demo builds here are test-only and are **not** promotion
artifacts. Browser keyboard/screen-reader/200%-zoom acceptance of the **new
Studio controls** has not yet been demonstrated; public browser checks do
not substitute for it.

## Remaining work (explicitly not accepted)

1. A secure, authenticated operator-only server/runtime binding for each
   Studio view; no private records may enter public static artifacts.
2. Real DP-214/Garlasco corpus and DP-116 top-K queries, persisted
   collection/source/passage/candidate traversal and queue semantics.
3. Durable review-authority/currentness checks and replay-safe actions
   before any candidate promotion or triage mutation.
4. Exact private passage/video selector jump, rights-gated preview and
   live persisted MiniPC canary, plus accessible browser/manual acceptance.

No migrations, secret reads, database writes, running-service restarts,
public API changes or provider calls are part of this tranche.

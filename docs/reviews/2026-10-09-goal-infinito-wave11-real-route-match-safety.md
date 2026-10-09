# GOAL INFINITO — Wave 11 actual Content route and private match-read safety

Date: 2026-10-09. Source baseline:
`bc274f82e4998de34e9851727ecef0dbc2e4e1a5`;
published Wave 10 GitHub CI `37973191658` SUCCESS, 11/11.
PRIME is the only integrator/publisher; two disjoint workers reviewed.
This tranche does **not** install DP-417, modify the real Garlasco
corpus, publish v1 or grant model/legal/reviewer authority.

## DP-407 mounted public Content route, not legacy demo

- File: `web/src/components/ContentRecord.astro` actually imported by
  `/contenuti/{slug}/` and the compatibility Content route. A
  timed source locator button previously had the Chrome accessibility
  name of only its position `2:30`, with no associated published
  statement identity. Real Chromium `Accessibility.getPartialAXTree`
  assertion RED.
- Fix: an `aria-label` combining **existing approved public**
  timestamp and statement claim for each timed locator marker. No
  visual, source URL, private transcript, evidence body, or schema
  change.
- Browser evidence:
  `node prototypes/v4-implementation/dp407/test-contentrecord-real-wave11.mjs`
  builds the true Astro Content route with explicitly passed
  12-moment *fictional public-projection* input; Chromium AX tree
  GREEN, keyboard Space activates marker, aria-current/expanded,
  focus, detail, URL `?momento=`, extra search params and hash
  stay consistent. All browser resources same-origin. Astro check:
  81 files, **0 errors/0 warnings/0 hints**. Design, route and
  public quality contracts passed; 54 HTML routes and 779 links
  in the local snapshot.
- A separate legacy-only `ContentAuditClient.tsx` +
  `test-content-audit-keyboard-wave11.mjs` experiment was
  technically green but **not part of the mounted public route**.
  Those files are deliberately *excluded from this commit*
  and preserved as local uncommitted WIP.
- **AC-407.7 remains OPEN**: automated Chromium accessibility tree
  is not a human screen-reader/200%-zoom acceptance and the local
  fictional fixture is not the MiniPC's authorized public projection.

## DP-418 actual persisted read-only match-inspection security

- Files: `poc/dichiarazioni_pubbliche/studio_candidate_review.py`,
  `tests/test_studio_candidate_review.py`. Inspector requires
  deterministic DP-212 matching run and result IDs bound to the
  exact candidate, target type and target identity; strict integer
  rank/count, unique targets, known matching methods and bounded
  feature *codes*, and consistent cluster-ID/disposition.
- ClaimType/temporal-scope contradictions force safe `HOLD` even
  if lexical matching reports same proposition; a falsified
  `PROPOSE_CLUSTER` row is rejected rather than recommended.
  Numeric scores, full features and private source text remain
  excluded from the allowlisted output.
- PRIME updated one downstream local API test fixture to import
  the new canonical deterministic match `RUN_ID` rather than
  hard-code `candidate-match-run:1`. The cross-contract
  `tests.test_studio_candidate_review`,
  `tests.test_studio_local_api` and
  `tests.test_candidate_matching` suite: **35/35 PASS**.
- The first integrated 2,078-test run started before the independent
  worker identified this adjacent test-fixture dependency and recorded
  **one failure** in `test_studio_local_api` (HTTP 422 vs old
  200 expectation). The strict application behavior was correct;
  the stale synthetic run ID was fixed by PRIME, then the complete
  dependent local API/matching suite passed **35/35**. A **new**
  frozen-code full-suite run is required; never claim the first
  global run passed or that a targeted rerun certifies the whole tree.
- **DP-418 remains IN PROGRESS**. No real currentness check,
  reviewer credential verification, approve/merge/create/reject
  mutation, persisted decision replay or production keyboard
  canary was implemented. `review_authority=false`,
  `publication_authority=false` and `promotion_enabled=false`
  are explicit in the result contract.

## Gate disposition

Full integrated Python suite, restore drill, benchmark, repo
contract, release preflight and matching Wave 11 CI must be
recorded with the eventual commit separately from the two
prior already-green GitHub runs. Until then this is local RED→GREEN
engineering evidence, **zero new ticket DONE**, 39 open, 41
launch blockers and no change to authentic source rights.

## Final local integration verification

The **second** frozen-code full integration rerun, after the
real local-API fixture correction, passed:

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2078/2078 PASS** in 157.708 s. Expected synthetic
  socket/HTTP resource warnings did not produce a failed test.
- Fixture restore drill: **PASS**, 100 tables, source state restored.
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`:
  **5/5 PASS**.
- Repository ticket contract and `compileall`: **PASS**.
- Launch preflight: **NO-GO/41**, same SHA-256
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
- `git diff --check`: **PASS**.
- Actual Content route Chromium AX/browser/keyboard harness:
  **PASS**. Astro 81 files: **0 diagnostics**; web design,
  route and quality checks **PASS**.

The original failed frozen-code run (one stale synthetic fixture)
is explicitly recorded above, not overwritten or passed off as
success. The final successful run is on the corrected source tree.
No new ticket status or acceptance changed.

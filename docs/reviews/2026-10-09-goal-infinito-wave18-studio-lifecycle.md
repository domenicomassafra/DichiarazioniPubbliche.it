# GOAL INFINITO — Wave 18: private Studio lifecycle and Capture time order

Date: 2026-10-09. Scope: DP-415, DP-419. Source: Mac Git checkout.

## Defects observed and reproduced

1. Studio's clear-token button removed only the token and main JSON/status:
   existing collection/member/capture links and the canonical segment locator
   remained in the DOM. In-flight read replies could repopulate private JSON
   after clearing access, and older workspace requests could overwrite newer
   workspace results.
2. The two-hash Capture comparison labeled the caller's first hash "earlier"
   and second hash "later" without comparing \`content_capture.observed_at\`,
   even though the persisted capture contract requires an aware observation time.
   Reversed timestamps (including offset-equivalent instants) could be displayed
   as a false chronology.

## RED→GREEN evidence

- A new Python unittest executes \`tests/studio_local_page_async_regression.cjs\`
  with the actual server-rendered inline JS and a deterministic fake local DOM.
  Delayed fetch replies deliberately ignore aborts. Before the patch the test
  failed \`clear must hide previously fetched private links\`. After the patch,
  it checks token clearing, derived-link/locator removal, stale-response
  rejection, workspace switching and newer-result preservation.
- A new Capture regression first produced six failed cases plus a missing
  \`observed_at\` output error: reversed, equal, malformed and missing times
  had been accepted. The inspector now validates an aware persisted timestamp
  and strictly increasing actual time before displaying earlier/later versions.
- After both fixes: \`PYTHONPATH=poc python3 -m unittest
  tests.test_studio_capture_inspector tests.test_studio_local_api
  tests.test_studio_local_page_async tests.test_studio_capture_selectors_pg -q\`
  returned **31 tests OK**, including the disposable PostgreSQL join/selector
  fixtures. \`python3 -m compileall -q poc tests\` and \`git diff --check\` PASS.
- Deterministic benchmark: **5/5 PASS**. Repository ticket contract: PASS.
  Launch preflight: **NO-GO / 41 blockers**, same SHA-256 receipt
  \`890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399\`.
- Full suite: \`PYTHONPATH=poc python3 -m unittest discover -s tests -q\`
  returned **2113 tests OK** in **177.304 seconds** with exit code 0.
  Restore drill returned **PASS** (100 tables, 1248 technical fields,
  89 public-schema fields). The ResourceWarnings in the captured
  output were non-fatal; no test failures were reported.

## Boundaries and remaining acceptance

No public projection, corpus data, rights state, persistence, provider, DB
schema, or publication gate changed. No MiniPC install/deploy was made.
Deterministic JS harness and local isolated PostgreSQL prove a narrow source
contract; **not** actual operator browser/AT acceptance, rights-approved
preview, live media seeking, or published/reviewer authority. DP-415 and
DP-419 stay IN PROGRESS; the project remains 39 tickets open and release NO-GO.

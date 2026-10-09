# GOAL INFINITO — Wave 15: capture-version Passage navigation

Date: 2026-10-09. Source baseline: `d280eeb9ed59bfc8b6fffe45f424765260da8063`.
Ticket: DP-419 (IN PROGRESS). No approval/publication or MiniPC deployment.

## Confirmed defect / missing operator workflow

The existing authenticated Studio loopback browser compared two persisted
Capture versions but could not inspect even the **bounded written Passage
selectors** belonging to one immutable version. Reusing the generic
`CapturePipelineStore.list_passages` was unsafe for the private HTTP surface:
its SQL returns `private_text` and arbitrary `metadata` and has no limit.
The missing inspector import produced a RED regression before implementation.

## Implementation

- New authenticated POST `/v1/capture/passages` with exact Content ID and
  Capture SHA-256; validates the persisted parent Capture lifecycle/status.
- `_StudioCaptureReader.list_passage_selectors` is a dedicated read-only SQL
  projection with **no** `private_text`, source body, URL or arbitrary metadata;
  stable `ORDER BY id` and limit+1 cursor pagination, maximum 20 per page.
- The pure inspector checks every surfaced locator's Content/Capture binding,
  SHA-256, selector type, character/page range and increasing cursor. Media
  references cannot be misattributed to a version-specific written Capture.
- The local Studio HTML uses keyboard-reachable buttons to navigate from
  either compared Capture to its Passage selectors; results use `textContent`
  and never persist a token. Returned authority flags remain `false`.

## Proof (source-only)

- Focused `tests.test_studio_capture_inspector` and
  `tests.test_studio_local_api`: **25/25 PASS** including HTTP authorization,
  data isolation, cursor bounds, cross-Content/Capture tampering and the
  field-projection-only SQL assertion.
- Independent `tests.test_studio_capture_selectors_pg`: **1/1 PASS** against
  a disposable PostgreSQL server with `db/schema.v1.sql` and 2 isolated
  Contents/Captures, 3 real Passage rows. Verified exact hash and Content
  scoping, two-page navigation, no private text/body field disclosure.
- JavaScript was extracted from the actual rendered HTML and accepted by
  `node --check`.
- Deterministic verification benchmark: **5/5 PASS**.
- Repository ticket contract, Python compileall, diff check: **PASS**.
- `check_launch_preflight --expect-no-go`: **NO-GO, 41 blockers**, receipt
  SHA256 `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.

## Full frozen verification

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2,103/2,103 PASS**, 252.874 seconds, plus fixture HTTP warnings.
  The standalone zsh wrapper printed an error **after** Python finished,
  because `status` is a read-only variable; Python's preserved run log
  explicitly ends `Ran 2103 tests ... OK`. This is not a test failure.
- The suite's restore drill: **PASS**, all 100 tables; resulting technical
  field inventory reports 1,248 fields and 89 public-schema keys.

The coherent selective commit and its GitHub Actions CI are distinct gates;
they cannot be assumed from these local results.

## Still unavailable / not asserted

The media Candidate→`MEDIA_SEGMENT_REF`→canonical transcript time range
requires an independently verified Content-scoped linkage. Rights- and
retention-gated passage previews are still disabled. No live MiniPC Capture
rows, approved source contract, operator browser/AT acceptance, successful
archive provider receipt or reviewer decision was introduced. No DP-419
acceptance criterion is closed solely by synthetic fixtures.

The uncommitted owner ContentAuditClient experiment and owner handoff remain
intentionally untouched and excluded from source delivery.

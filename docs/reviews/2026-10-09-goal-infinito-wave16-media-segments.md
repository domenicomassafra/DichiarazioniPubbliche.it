# GOAL INFINITO — Wave 16: source-bound media Candidate interval locator

Date: 2026-10-09. Baseline: `25b1781bf8021218d6e28969731a17c8892add4e`.
The Wave 15 baseline is independently GitHub CI certified: run
`37988211612`, 11/11 SUCCESS. Wave 16 remains source-only until its own
checks/commit/CI finish.

## Why this cannot reuse the written Capture selector reader

The repository has two distinct Passage source types. Written Passage
selectors bind to a Capture (`capture_id`); `MEDIA_SEGMENT_REF` Passage
selectors bind to one canonical transcript Segment under logical Content
(`canonical_segment_id`). Returning the latter from a Capture-version list
would falsify provenance. A proposed time range must instead be resolved
through the persisted Candidate→Passage→Segment relation.

## Implementation

- Added `studio_media_selector.py`, a pure fail-closed metadata-only reader
  requiring exact Content, Statement Candidate and Passage IDs. Cross-Content,
  cross-Passage, missing/misbound Segment, wrong selector, wrong hash, boolean
  masquerading as milliseconds, nonpositive time ranges and unknown states
  are rejected. Database errors are returned as bounded codes.
- `_StudioCaptureReader.read_candidate_media_selector` queries only ID,
  lifecycle, hash, selector and time interval metadata; it joins the real
  `statement_candidate`, `statement_candidate_passage`, `passage` and
  `canonical_transcript_segment` relations. It **never selects** canonical
  words, normalized statements, passage text, speaker identity or raw metadata.
- Authenticated `/v1/media/segment` requires the exact ID triple, uses the
  existing loopback-only read-only server, returns zero review/attribution/
  rights/publication authority, and never mutates any row.
- The private Studio view displays the persisted canonical time range and
  transcript/blocker state in a keyboard-accessible live region. This is
  **not** a media-player seek or permission to reproduce copyrighted media.

## Observed proof

- RED missing implementation import, then `test_studio_media_selector`:
  **3/3 PASS** including corrupted references and withheld private text.
- Focused read-only Studio HTTP suite together with pure media tests:
  **22/22 PASS**, authenticated route, malformed request and SQL projection.
- `tests.test_studio_capture_selectors_pg`: **2/2 PASS** on a real disposable
  PostgreSQL server and `schema.v1.sql`, including the new persisted Candidate,
  `MEDIA_SEGMENT_REF` Passage and canonical segment (1200–3400 ms), and missing/
  mismatched source-edge rejection. No real provider data was touched.
- Rendered HTML inline JavaScript: `node --check` PASS.

## Frozen source verification

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2109/2109 PASS**, 423.999 seconds, isolated PostgreSQL and HTTP fixtures.
- Restore drill **PASS**: 100/100 tables, 1,248 privacy-field inventory entries,
  89 public-schema fields, exact backup/restore state comparison.
- Deterministic verification benchmark **5/5 PASS**.
- Repository ticket contract, `compileall` and `git diff --check` **PASS**.
- Launch preflight **NO-GO/41**, unchanged receipt SHA-256
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
- Web `npm run check`: **0 errors/warnings/hints** across 81 Astro files.
  Ordinary `npm run build` correctly refuses without authorized public
  projection input; an explicitly local-demo-only build with
  `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1` passed, **32 pages**.

The selective source commit and commit-specific GitHub CI remain distinct
gates; the local results do not constitute a live MiniPC deployment.

## Unresolved gates

DP-419 remains IN PROGRESS, with all AC unchanged. No real player seek, source
preview, approved media-rights/retention policy, accepted reviewer attribution,
MiniPC deployment, browser AT test, or Garlasco Candidate/Passage corpus was
obtained. M7 stays NO-GO until independently resolved.

The owner handoff and unrelated local DP-407/ContentAuditClient WIP remain
unmodified and outside this wave's commit.

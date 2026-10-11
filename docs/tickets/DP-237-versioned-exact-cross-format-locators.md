# DP-237 — Versioned exact locator and cross-format provenance chain

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-210, DP-216, DP-224, DP-225

## Problem

Source URL alone often resolves to a changed page or an adjacent speaker; raw string offsets drift between OCR/parser/transcript versions. Studio's existing metadata inspector lacks full real-source media seek. Public readers later need a precise audited source reference without exposing raw private capture bodies.

## Outcome

A canonical provenance/locator object binds a verifiable original **Content→Capture/TranscriptVariant→Passage/Segment→exact quote span** with checksum, selector/timebase, transform lineage, source version, author/speaker role and alternative official/archival locations. A resolver detects drift/purge/ambiguity and reports what can actually be opened.

## Traceability & constraints

R05/R07/R10, DP-216/218/219/224/225/419. Written locators must not invent `0:00`, media locator must not fake text chars; citation of reported speech stays distinct from endorsement.

## Scope

Compare/version existing `content_capture`, `PassageRecord` (`TEXT_POSITION`, `PAGE_RANGE`, `MEDIA_SEGMENT_REF`), quoted subspan hashes, `claim_text_provenance` and canonical timed segments; link optional original-page selector/paragraph/XPath/PDF page box, media ms and source/time zone. Keep published locator public metadata minimal; full capture/passage private. Align derivation edges for repost/syndicated/translated/archive copies and chronological supersession via DP-511.

## Non-goals

Public corpus dump; guaranteed player seek when source platform has no stable time URI; rights clearance, identity verdict or standalone new search index.

## Dependencies and sequencing

Hard existing quote/capture/citation/original-source contracts; soft DP-419 private inspector, C public source-link surface, B context/rights, D archival refresh; real source selector rights externally.

## Acceptance criteria


- [ ] `AC-237.1`: In immutable written source, page/char/paragraph span resolves to exact original text hash and Content/Capture/version; altered bytes or out-of-range span fails closed.
- [ ] `AC-237.2`: In timed media, canonical transcript variant and segment/timebase resolve and cannot jump to a different speaker or source; unavailable player time is explicitly marked unavailable.
- [ ] `AC-237.3`: Reposts/archive/translation supply original→derived edges without treating a copy as independent original, and retain the unchanged original-language words.
- [ ] `AC-237.4`: Changed Content leaves earlier Capture/locator addressable by version; purge retains hash/selector/receipt metadata and marks excerpt inaccessible.
- [ ] `AC-237.5`: Quoted excerpt cannot cross discontinuity/turn/page/source identity silently; negative stitched quote and wrong-version tests hold.
- [ ] `AC-237.6`: Private Studio MiniPC readback returns exact source jump; safe public projection later consumes a restricted locator only after C/B publication authority.

## Validation / proof

Real permitted article/PDF and one actual timed sample, before/after byte/selector hashes, broken locator and altered source negatives, independently reconstructed MiniPC reference. Record supported and unsupported viewer schemes explicitly.

## Documentation, data, and migration impact

Prefer additive selector metadata preserving old IDs and DP-216 hashes, old API links and immutable Capture versions; no backfill of unreviewed locators with fabricated precision.

## Completion receipt

**IN PROGRESS — source-only implementation; original cross-format and MiniPC acceptance remain open.**

## 2026-10-11 — First implementation slice

Pure opt-in immutable Capture/Passage locator resolver implemented in `original_source_resolver.py` (commit `6bd8532`), covering text position, PDF page and media segment with strict source/version/hash/speaker/timing guards. 11 focused + 10 legacy tests and deterministic benchmark pass. No real parser authentication, source Studio/media seek, rights or MiniPC acceptance; all AC remain unchecked.

## 2026-10-11 — Media speaker binding regression (worker-23)

The opt-in `MEDIA_SEGMENT_REF` resolver previously returned `LOCATED` when the locator's `speaker_person_id` was missing, even if the observed segment identified a speaker, or when both values were whitespace. That allowed an otherwise matching timed excerpt to evade the claim-to-segment speaker comparison. A new negative regression in `tests/test_dp237_exact_locator.py` first failed with two unexpected `LOCATED` results (RED). The media branch now requires a nonblank, explicitly pinned speaker ID equal to the observed segment's ID; otherwise it returns `BLOCKED / LOCATOR_MEDIA_SPEAKER_MISMATCH`. Written selectors and the original media success case retain their behavior.

Local GREEN: `PYTHONPATH=poc python3 -m unittest tests.test_dp237_exact_locator tests.test_dp239_multilingual_derivation tests.test_original_source_resolver tests.test_dp241_original_source_investigation -v` → 55 tests passed. This enforces media locator binding only; it neither authenticates the underlying non-biometric speaker attribution nor supplies a real-media player jump, current source permission, parser authority, publication approval, or MiniPC readback. All six original AC boxes remain open pending the real-source and runtime proofs.

Additional local checks: `python3 -m compileall -q poc tests` PASS; deterministic benchmark 5/5 PASS; `git diff --check` PASS. Repository-wide `unittest discover -s tests -q` was attempted but interrupted after roughly two minutes while waiting in a subprocess from `test_m3_runtime_canaries.py::test_dp303_enabled_correction_runs_real_reanalysis_and_public_projection`; it has **no** PASS/fail result to claim. No commit, deployment or external-source acceptance was performed.

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

**NOT IMPLEMENTED — planning only**.

## 2026-10-11 — First implementation slice

Pure opt-in immutable Capture/Passage locator resolver implemented in `original_source_resolver.py` (commit `6bd8532`), covering text position, PDF page and media segment with strict source/version/hash/speaker/timing guards. 11 focused + 10 legacy tests and deterministic benchmark pass. No real parser authentication, source Studio/media seek, rights or MiniPC acceptance; all AC remain unchecked.

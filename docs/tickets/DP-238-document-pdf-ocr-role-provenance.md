# DP-238 — Document, PDF/OCR and text extraction with role-preserving provenance

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-210, DP-211

## Problem

Textual official records, historical scans and procedural/judicial documents cannot be reduced to a media transcript or machine-readable web paragraphs. Image-only PDFs, old orthography, complex columns, footnotes, stamps and incomplete pages can invert quotations or confuse the reported speaker with the author of the document. `PassageRecord.PAGE_RANGE` exists, but a real OCR source path with measured error/locator fidelity is not proven.

## Outcome

An approved private Capture in a supported written format becomes a faithful, versioned text extraction and page-aligned `Passage` set, with ambiguous/low-confidence spans held before Candidate promotion and no manufactured multimedia timestamps.

## Traceability & constraints

R09/R04/R05/R07, R21–R22 input to B. Allegation in a court filing is a document assertion, not established fact or necessarily a direct quote by the case subject. Protect minors/victims/third parties and handle redactions before any public output.

## Scope

Text HTML, born-digital PDF, scan/image PDF, text/XML (including Senato AKN), optional public document image after acquisition-specific rights. Use content hashes and immutable per-page/fidelity/reading-order transforms; preserve source file, page count, page coordinate or text offsets, OCR engine/version/language/profile, original script, ambiguity/split reading-order evidence, missing pages and editor/redaction marks. Model participant-role hints (`DOCUMENT_AUTHOR`, `REPORTING_AUTHOR`, `QUOTED_SPEAKER`, `WITNESS`, `PARTY_ALLEGATION`, `COURT_FINDING`, `UNKNOWN`) as **candidates**, never evidentiary verdicts, with B owning semantic/judicial classification.

## Non-goals

Universal OCR accuracy, automatic adjudication of guilt, lifting redactions, scraping restricted case files, treating normalized OCR as confirmed exact human speech.

## Dependencies and sequencing

Hard canonical capture/extraction; qualified document fetch/processing permits DP-236 external; soft B procedural truth/risk, DP-237 locators, DP-239 multilingual, D resource budgets.

## Acceptance criteria


- [ ] `AC-238.1`: A real approved machine-readable text and scanned PDF produce versioned page/char selectors whose original-file hashes, extraction method/version, language and ordered page coordinates roundtrip on MiniPC.
- [ ] `AC-238.2`: A frozen reference set includes multi-column, page break, negation, numerals/date, direct quotation, reported speech, redaction and incomplete-page cases with measured character/word error and critical-span failures; thresholds fixed before evaluation.
- [ ] `AC-238.3`: Confidence alone cannot turn corrected OCR into `VERBATIM_ORIGINAL`; uncertain critical span is visibly held and a better original or independently checked span is sought.
- [ ] `AC-238.4`: No speaker/court/party role is inferred merely from the filename or topic; role ambiguity and homonym yield distinct candidate identities and blocker codes.
- [ ] `AC-238.5`: Exact replay creates no duplicate Capture/Passage; corrected OCR or new PDF version creates a new derivation/version with supersession rather than rewriting history.
- [ ] `AC-238.6`: Rights-denied file, parser bomb, corrupt/oversize PDF and malicious embedded metadata cause bounded fail-closed failures with no disclosure in public or model output.

## Validation / proof

Source-specific legal/retention inputs, private real-file gold and critical error matrix, hashes, accepted/held counts, MiniPC memory/time, exact selector/readback and public-leak negative. Independent reference evaluation required; do not mark 100% merely by self-grading model output.

## Documentation, data, and migration impact

Reuse `capture_pipeline` parser interface, `PassageRecord` and existing rights/purge; additive OCR/role fields if demonstrated. Historical paper files never become persistent public raw-body assets automatically.

## Completion receipt

**NOT IMPLEMENTED — planning only**.

## 2026-10-11 — First implementation slice

Commit `c366514`. Added opt-in `document_text_extraction.py` and tests: bounded native UTF-8 text/XML/AKN/HTML parser and source/passage/page hash + selector checks. 11 new and 28 related capture regression tests PASS. PDF native text/OCR, independent fidelity gold, actual source permits and MiniPC acquisition remain absent. No automatic speaker/court role, copyright or verbatim publication is inferred. **All original AC remain unchecked**; this is a local source-only test receipt, not permission for live publication.

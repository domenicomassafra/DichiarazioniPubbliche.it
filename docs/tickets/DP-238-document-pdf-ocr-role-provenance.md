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

## 2026-10-11 — Bounded born-digital PDF extraction, opt-in only

Local commit `4e6a465` adds `document_pdf_extraction.py` and
`tests/test_dp238_born_digital_pdf.py`; `document_passages_from_capture`
requires an explicit PDF parser and separately replays the same Capture bytes,
SHA, method/version, rights state and page selectors. Real generated two-page
born-digital PDF fixtures are parsed using a **separate bounded subprocess**
with optional pypdf backend, a fixed PDF/page/decoded-text envelope and worker
timeout. Blank pages, encrypted PDF, mixed raster images, annotations, overly
long documents, corrupt files, parser errors and unavailable backend fail
closed. Scanned and complex layout PDF still require OCR/qualified review.

Passages are always `UNREVIEWED_PDF_EXTRACTION`, never `VERBATIM_ORIGINAL`;
PDF source page text order is unreviewed, and character selectors reference
the *versioned extracted text*, not authenticated byte positions in a PDF.
The baseline `DocumentTextParser` retains its old fail-closed PDF behavior.
`pyproject.toml` declares optional `document-pdf` and `document-pdf-test`
profiles without installing dependencies in the default stdlib-only profile.
**19 combined focused native-document/PDF tests PASS**, Ruff/compileall and
repository contract PASS. These are in-memory synthetic PDFs, **not** actual
approved source rights, independent OCR/text fidelity gold, real MiniPC
acquisition/readback or public quote permission. AC-238.1–.6 remain open.

## 2026-10-11 — PDF fail-closed integrity regression (local, uncommitted)

Adversarial test first confirmed that an actual generated PDF with raster pixels
inside a `BI`/`ID`/`EI` page-content operator, alongside machine-readable text,
was incorrectly accepted as `SUCCEEDED`: the previous scan checked only `/Image`
XObjects. The bounded pypdf worker now inspects parsed page-content operators and
returns `DOCUMENT_PDF_OCR_REQUIRED` for inline raster images too. A second
regression confirmed a malformed worker-success JSON could embed `\f` within one
page string, manufacturing extra page selectors in the parent. The parent now
rejects that success payload as `DOCUMENT_PDF_WORKER_INVALID`; invalid-Unicode
worker payloads are also tested to remain held. Original-byte SHA attribution,
method/version checks, deterministic capture replay and passage limits continue
through the existing shared adapter without modification.

**RED evidence:** the inline-image regression failed because the parser returned
`SUCCEEDED`; the injected-page-break regression likewise failed before the fix.
**GREEN evidence:** 21 focused native/PDF tests PASS, standalone `ruff check`
PASS, targeted `compileall` PASS, `git diff --check` PASS on the local checkout.
No OCR provider, real source, rights evidence, MiniPC proof, independent fidelity
gold, or public quote acceptance was exercised. All AC-238.1–.6 remain open.

## 2026-10-14 — Isolated PDF worker import-root recovery

The 3,632-test integration run reported eight born-digital PDF failures with
`DOCUMENT_PDF_WORKER_UNAVAILABLE`; the independently focused 10 tests previously
passed. A controlled real generated PDF invocation reproduced this same error
after changing the caller working directory to an unrelated temporary folder and
clearing `PYTHONPATH`: the child returned status 1 with
`ModuleNotFoundError: No module named 'dichiarazioni_pubbliche'` after 0.109 s.
This proves a worker **startup/import** failure independent of the PDF body and
the 5-second timeout, but does not yet prove the exact environmental trigger of
the original integration-run failures.

The subprocess now uses the resolved package parent as its working directory,
fixed at module import, allowing `python -m` to resolve the installed source tree
even when the caller changes cwd or loses the inherited relative `PYTHONPATH`.
There are no relative data-file inputs in the worker entry point or its import
path; the only extraction input remains the bounded PDF bytes over stdin. The
optional `pypdf` import and resource limits remain in the child. Fail-closed
exit codes, parser errors, 5-second wall timeout, 3/4-second CPU limits, and
the 512-MiB memory limit are unchanged.

**RED:** new real-PDF test with unrelated cwd and empty `PYTHONPATH` failed with
`DOCUMENT_PDF_WORKER_UNAVAILABLE`. **GREEN:** that test passed after the fix;
22 adjacent PDF/native-document tests PASS, including adversarial image, role,
rights, source-hash, selector and worker-failure checks. Six additional real
PDF worker invocations under up to three concurrent callers, each with unrelated
cwd and empty `PYTHONPATH`, all returned `SUCCEEDED` (0.40–0.60 s each).
`compileall` and `git diff --check` PASS. Independent source diff review found
no P0/P1 issue. No full-suite rerun was performed concurrently with other
integration work; a clean independent full run is still needed to attribute and
clear the original eight intermittent failures. Original AC-238.1–.6 stay open;
this is source-only, synthetic local evidence without MiniPC or editorial proof.

## 2026-10-15 — Reject partial HTTP PDF as a full immutable source

The opt-in `BornDigitalPDFTextParser.parse()` accepted all status codes
200–299. An HTTP **206 Partial Content** response with a syntactically
valid PDF body could thus be treated as a *complete* source and yield
apparently version-bound page/Passage selectors and content hashes even
when the source server explicitly reported only a byte range.

A real generated PDF and isolated valid child-worker response reproduce
**RED** (the 206 path returned `SUCCEEDED` where a fail-closed result
was required). The status guard now accepts only an exact HTTP 200 as
a complete-document PDF extraction; a 206 returns
`FAILED / DOCUMENT_SOURCE_STATUS_INVALID` with no text or spans,
while a valid 200 response remains a private non-verbatim candidate.
The mocked worker response in this one test separates the HTTP status
invariant from independently tested optional-worker process availability;
it does **not** self-grade PDF fidelity.

**Validation:** the targeted RED test failed before the source fix
(`SUCCEEDED` instead of `FAILED`) and GREEN passed after. Prime reran
`tests.test_dp238_document_extraction` plus this exact adversarial
test: **12/12 PASS**, scoped Ruff/diff checks PASS. A broader
`test_dp238_born_digital_pdf + test_dp238_document_extraction` attempt
ran **23 tests with four failures** caused by the real PDF subprocess
returning `DOCUMENT_PDF_WORKER_UNAVAILABLE`, rather than the
expected parsed status. The shared host showed load averages around
**190/199/139** with numerous busy browser workers: those four tests
are **not PASS**, and the true PDF worker bootstrap under normal
load is unverified by this tranche. The HTTP 206 guard itself is a
pre-worker input validation and is independently green. Do not
promote this result to end-to-end PDF/OCR acceptance.

This source-only fix changes no source rights, review identity, OCR
provider, upstream byte-range assembly, database, public route or MiniPC.
**Original AC-238.1–6 remain OPEN / IN PROGRESS** for approved
machine-readable and scanned sources, independent OCR gold, role and
critical-span fidelity, persistent replay and real MiniPC readback.

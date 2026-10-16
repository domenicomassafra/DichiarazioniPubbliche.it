# DP-238 — isolated MiniPC scanned-PDF OCR proof (2026-10-16)

## Scope and authority

The only source used was this owner repository's `PRODUCT.md` (Apache-2.0
project material), SHA-256
`e1fb22f3c8b0b837dc67f84fd135acdb1c8d24e019884e2c7f602fc67e294b9e`.
Three short exact lines were selected from that source **before** OCR, frozen
into an independent reference, rendered to images and embedded in a two-page
**image-only generated PDF**. PDF SHA-256:
`c5fb9cdf3919188ff049e16d10fd244a7f542f37b147983c2171b8b78e289b21`.
The source is authorized for this private software test; this is *not* a real
archival scan, a real external source-family rights grant, a legal/editorial
approval, or a verified published quotation.

MiniPC SSH `minipc`, native Python 3.14.4. Installed native OCR runtime:
Tesseract 5.5.0, `ita` and `eng` language packs, Poppler `pdfinfo` / `pdftoppm`.
Ubuntu apt installed 6 packages, 24.9 MB installed-size estimate; approximately
87 GB available on the filesystem before installation. The live deploy mirror
`/home/udodo/src/DichiarazioniPubbliche.it` lacks both older DP-238 document
parsers and remains untouched. Execution was in a private isolated source
overlay `/tmp/dp238-native-acceptance-20261016`, with in-memory Capture and
Passage candidates; no database, remote fetch, queue, public service, rights
registry, or publication operation was invoked.

## Measured native result

| Operation | Result |
| --- | --- |
| Real owner-source text, two pages | `SUCCEEDED`, 2 deterministic private Passage selectors, original text/page SHA replay exact |
| Real rendered image-only PDF, two pages | `SUCCEEDED`, Tesseract 5.5.0, 22 OCR words, 2 private OCR Passage selectors |
| OCR wall time on MiniPC | 1,478 ms for the first two-page run; includes isolated worker and renderer |
| Independent OCR reference | normalized per-page character error rate **3.57%** / **0%**; predeclared upper bound **8%** passed on both pages |
| Critical text | negative `no automatic publication`, `private by default` retained in native OCR output |
| Quote and identity authority | every OCR candidate retains `UNREVIEWED_OCR_EXTRACTION`, `verbatim_reviewed=false`, `HELD_INDEPENDENT_REVIEW_REQUIRED`, no trusted role identity |
| Denied rights | replay refused with `DOCUMENT_CAPTURE_OR_EXTRACTION_MISMATCH` |
| Source-version stability | two independent replays returned the exact same private Passage IDs; a changed PDF byte version and distinct Capture produced disjoint Passage IDs (in-memory proof only) |
| Parser-negative native scans | generated JavaScript-bearing PDF `DOCUMENT_PDF_UNSUPPORTED`; incomplete third page `DOCUMENT_INCOMPLETE_PAGE`; five pages `DOCUMENT_OCR_PAGE_LIMIT`; encrypted PDF `DOCUMENT_OCR_PROCESS_FAILED`; all fail closed with no private text |
| Public disclosures | none attempted or authorized |

The first Linux run returned `DOCUMENT_OCR_PROCESS_FAILED`: Poppler writes
PNG bytes to standard output when **no output-prefix argument** is provided.
An explicit trailing `-` wrote zero stdout bytes. The source adapter was
corrected to call `pdftoppm` without that argument; rerunning the same input
successfully extracted the two pages. A later source-only hardening pass pins
Tesseract's actual engine version in the effective parser version and refuses
JavaScript/Form/Suspects flags from Poppler metadata. The native negative
matrix above was rerun after this hardening, with the positive method version
`poppler-tesseract-private-ocr-candidate-v1/tesseract-5.5.0`.
The final native in-memory consumer reran two original Passage replays, verified
rights denial and changed-source IDs, and finished those reads in 8,833 ms.

## Current original acceptance

DP-238 remains **IN PROGRESS** with AC-238.1–6 **unchecked**. These readings
prove the *native MiniPC engine and private ephemeral consumer* work on
owner-controlled surrogate material; they do not prove the live installed
service, independently acquired and cleared official/historical scanned source,
real persisted Capture/Passage readback, real multi-column/redaction/low-quality
gold, true supersession in PostgreSQL, or public-leak negative of a real source.
The reference is tiny and visually generated, so its measured CER does not
establish OCR quality on authentic scanned archival documents.

Next acceptance step: obtain a source-specific permissible authentic scanned
PDF and independently transcribed gold, then run the bounded OCR through the
existing governed Capture→Passage persistence path on MiniPC. Verify source
rights, current source hash, exact selector and independent readback, critical
span holds, version supersession, and public-body non-disclosure before checking
any original acceptance criterion.

## 2026-10-16 — Independent same-PR security review follow-up

During a fresh review of the exact original adapter, a source-boundary order
defect was reproduced: `document_passages_from_capture` called the PDF/OCR
parser (including its native subprocess) **before** rejecting a revoked
capture, mismatched source hash or changed final URL. The call eventually
failed closed without returning passages, but it still unnecessarily processed
unapproved bytes.

Added a regression with three rejected captures and a subprocess spy. Before
the fix all **three** cases failed because OCR was invoked once. The adapter
now checks Capture status, rights clearance, source SHA, URL, media type and
stored parse status **before** replay. The later parser/version/result
identity comparison remains unchanged. After the fix, 27 focused native
document/PDF/OCR tests PASS; Ruff and `git diff --check` PASS. This verifies
that unauthorised bytes do not reach the worker **through this adapter**; it
does not grant any source rights or substitute for upstream authorization,
real-file gold or installed MiniPC Capture/Passage acceptance.

### Hold-state regression in same rights boundary

The corpus retention gate also forbids downstream private use under an active
legal, rights or privacy hold, even if a Capture's rights_status remains CLEARED.
The OCR adapter previously failed to inspect `capture.hold_status`; a new
three-state regression was RED because each held Capture still invoked its
native subprocess. The same preflight now requires `hold_status == NONE`
before any parse/replay, matching the existing corpus downstream-use fence.
Rejected holds create no Passage and launch no native OCR through this adapter.

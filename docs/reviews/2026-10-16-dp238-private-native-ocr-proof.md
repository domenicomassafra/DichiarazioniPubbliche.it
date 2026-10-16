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

## 2026-10-16 — canonical Capture→PostgreSQL Passage OCR integration (PR100 follow-up)

The prior isolated real OCR exercise proved the DP238 in-memory adapter but
not the writer that `capture_content` actually invokes. Independent review
identified a reproducible loss: `capture_pipeline._persist_fetched_capture`
persisted `_passage_records`, which keeps hashes and IDs but drops page number,
page SHA, OCR word pixel boxes and the mandatory critical-span HOLD.

The canonical pipeline now uses `document_passages_from_capture` for the exact
built-in native-document, born-digital PDF and scanned-OCR parser types. It
requires a current source-use guard and explicit `CLEARED` rights and stored
selector metadata; an existing non-captured, rights-uncleared, held or purged
Capture blocks processing. The adapter replays immutable source bytes and
checks the stored Capture/parser version before any Passage insert. General
media/HTML writer behavior remains unchanged.

**RED→GREEN**: two new canonical writer regressions first failed with 1
native-worker call instead of the required source+replay, missing stored page
metadata, and an unauthorized `UNKNOWN`-rights write. Both now pass. A third
test exercises actual local PostgreSQL `CapturePipelineStore` SQL rather than
an in-memory fake. The same targeted PostgreSQL test was executed on the
MiniPC with the existing **real** two-page rasterized owner-repository PDF,
Poppler/Tesseract 5.5.0 and an ephemeral PostgreSQL 18 cluster initialized
and stopped by the test. It passed exact private page/box/HOLD SQL readback,
unchanged replay (`EXISTING`), a rights-HOLD negative, and zero
Statement/Claim Candidates.

This is persistent private *isolated test* acceptance with a synthetic
test-only source rights/relevance receipt for owner-controlled material. The
production PostgreSQL database, its source rights registry and the live web
service were untouched. It does **not** certify an independent rights grant
for an archival source, difficult-scanned reference quality, installed
MiniPC mirror deployment or public disclosure assurance. DP-238 AC-238.1–6
remain unchecked; a genuinely approved archival source and independent gold
are still required for original closure, even though this bounded synthetic
engineering exercise needs no additional source.

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

### 14:25 CEST — OCR pixel-box provenance across a 4,000-character Passage split

Direct review of the existing DP-238 private adapter found a further concrete
AC-238.1/AC-238.5 locator gap: OCR word coordinates were attached to a Passage
only when the word was *entirely contained* in its character range. A valid
word crossing the deterministic `MAX_PASSAGE_CHARS=4000` split silently
disappeared from the `ocr_word_boxes` lists of **both** Passages.
The new real adapter regression inserts a word beginning at offset 3998 and
ending beyond 4000; it was **RED** (zero pixel boxes in the first Passage).

The repaired metadata projection keeps the original absolute word offsets,
pixel box, page and OCR confidence on **both intersected Passages**, explicitly
setting `crosses_passage_boundary=true`. Completely contained boxes are still
retained with `false`. This prevents silent loss of provenance while allowing
downstream private reviewers to hold a partial word and join adjacent Passages.
No OCR text is promoted to verified quotation. The scoped regression is GREEN
after this minimal change. Real archival/fidelity gold and live consumer
acceptance remain outstanding, and all original DP-238 AC remain unchecked.

### 2026-10-16 14:43–14:55 CEST — actual public-use archival scan, native MiniPC PostgreSQL

To exercise the existing original DP-238 AC against a **real** source rather
than only the owner-authored surrogate, CoS02 retrieved the official NASA NTRS
record `19640005616`, *Talk given at Huntsville, Alabama during Engineers
Week (engineering challenges of the 1960s)*:

- Catalog `https://ntrs.nasa.gov/citations/19640005616`; official API
  `https://ntrs.nasa.gov/api/citations/19640005616` returned
  `copyright.determinationType=GOV_PUBLIC_USE_PERMITTED`,
  `copyright.containsThirdPartyMaterial=false`. Metadata response 2,274
  bytes, SHA256 `d6f68fd0ac3b2c237b6fcb25eadc361709b997385e8570c89480c47138667a66`.
  This is a source-specific **public-use** catalog indication, not a blanket
  license for other records, downstream public quotations or a qualified
  independent fidelity determination.
- Exact official file
  `https://ntrs.nasa.gov/api/citations/19640005616/downloads/19640005616.pdf`,
  HTTP 200 application/pdf, length 670,233 bytes, ETag
  `0fcd221b9805723a72a7b141cff58a19`, SHA256
  `9b25371659441c501cf2f48591e7b9bb582fa72c6ddc4d6794c56eb9eb1b9cbb`.
  Real Poppler on MiniPC: **20 pages**, one 2,544×3,300 gray CCITT scan
  image/page at 300 dpi, no form/JavaScript/encryption/suspect flag.
- The defensive OCR adapter intentionally permits at most **4 pages**.
  To retain this guard, an owner-only derived two-page selection was made using
  `pdfseparate` and `pdfunite` with pages 1–2, 74,965 bytes, SHA256
  `b4cadc4f1c18201af63250e74f42b993872f87e22b06e0b80a19ac3c01bdf399`.
  Private URI `urn:dp238-private:nasa-19640005616:pages-1-2:<derivative SHA>`
  distinguishes the transform from the NASA HTTP origin. Parent catalog URL,
  20-page source hash, derivative hash and transformation identifier are
  carried in the owner-only Capture metadata. Thus the 2-page hash is **not
  asserted to be the original downloaded PDF**.

Native MiniPC Poppler + Tesseract 5.5.0 (`ita+eng`) on the source-derived
two pages: `SCANNED_PDF_OCR_CANDIDATE` **SUCCEEDED**, two private Passages
for pages 1 and 2, **404 candidate words**, 201+203 image-location word boxes;
parser version carries the actual Tesseract version, no text/role/public-quote
authority was promoted. The private adapter was taken from the **same pushed
PR100 head `08a7f3e`** via a separate isolated staging tree.

The canonical `content_capture` and `passage` PostgreSQL 18 DDL, with
disposable parent stubs and socket-only temporary cluster, produced
**`PASS_DISPOSABLE_MINIPC_PG`**: Capture+2 Passages `INSERTED` initially,
the same 3 `EXISTING` on replay, readback `1|2|2|2|2`
(one Capture, two Passages, both OCR-unreviewed and Tesseract-versioned);
the `LEGAL_HOLD`, `RIGHTS_HOLD` and `PRIVACY_HOLD` negatives each
prevented the OCR subprocess from starting. Verified output carries
`live_database_touched=false`, `live_service_touched=false` and
`public_projection_authorized=false`. No public route or provider was used.

**Limits:** this is a genuine public-use scan and **real disposable database
consumer**, but *not* the installed operational Capture→Passage consumer or
a persisted source authorized for production. A separately transcribed
multi-column/negation/redaction gold with frozen thresholds has not been
independently obtained, and the four-page max excludes the unmodified
20-page document. The speech document does not establish the political/
judicial-role corpus sample. Original **AC-238.1–6 remain OPEN** until each
criterion is proved on the actual intended installed product.

#### Companion official machine-readable text, real MiniPC readback

The *same* record lists and serves a separate official
`/api/citations/19640005616/downloads/19640005616.txt` with HTTP 200,
`text/plain; charset=utf-8`, 25,865 bytes, ETag
`3607b94b8c3a6075179ef68362d1b220`, source SHA256
`2602b9879601f16588ef5b799d6bc54b28ba065d9dc22f5ba077a4a1ae5e4cf1`.
`DocumentTextParser` parses the exact UTF-8 bytes with
`document-native-text-v1`, obtaining seven private 4,000-character-bounded
Passages over a single plain-text page selector. On the **native MiniPC**,
the current `08a7f3e` adapter read those actual bytes from a separate
isolated source staging folder; two full replays returned **equal sets of
seven deterministic Passage IDs**, all `verbatim_reviewed=false`, no
public projection, process exit 0:
`PASS_MINIPC_AUTHENTIC_OFFICIAL_TEXT`.

Do not equate this NASA-provided text with a transcription independently
checked by humans against the 20-page raster source. It is a distinct
machine-readable product/source version, and its exact parser hash does not
validate the OCR errors or map its one text selector to the cropped two-page
PDF. The original AC-238.1 now has real source-specific **text and scan**
private-host partial proof; independently verified gold, full installed
Capture↔Passage consumer, historical role-sensitive matrix, and explicit
public non-disclosure remain pending.

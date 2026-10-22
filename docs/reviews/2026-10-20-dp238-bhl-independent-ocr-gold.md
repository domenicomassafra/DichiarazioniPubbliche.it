# DP-238 / #102 — independent real-image OCR gold, private proof (20 October 2026)

## Scope and source rights

PR [#100](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/pull/100)
already delivered bounded private scanned-PDF OCR, rights preflight, immutable
Capture/Passage metadata and critical-span HOLD. PR
[#204](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/pull/204)
already delivered private source-page navigation. Neither is repeated here.

For an **independent technical OCR reference**, selected one real historical
page from *Birds of Great Britain and Ireland*, volume 2, Arthur G. Butler
(1908), American Museum of Natural History Library scan:

- BHL [bibliography 8651](https://www.biodiversitylibrary.org/bibliography/8651),
  volume 2: `Copyright Status: NOT_IN_COPYRIGHT` (item-specific, checked on
  20 October 2026). Page ID `8992356`; no court, journalist, or speaker role
  is inferred from this bibliographic description.
- [IMPACT-BHL ground-truth repository](https://github.com/impactcentre/groundtruth-bhl)
  and [FineBooks packaging](https://huggingface.co/datasets/finebooks/bhl-impact-gt):
  independent expert-corrected OCR/PAGE XML produced in the 2011–2012 IMPACT /
  BHL-Europe collaboration, **CC-BY 3.0**. Attribution: *IMPACT Centre of
  Competence & Biodiversity Heritage Library (2012), IMPACT-BHL ground truth*.
  The gold precedes and is independent of our Tesseract extraction. Its own
  original OCR-assisted transcription and later human QA are **not** proof of
  independent double-key transcription for this specific page.
- Dataset revision `f57bb9e58785a3f9266c05880092ec76720450e5`, barcode
  `birdsofgreatbrit02butl`, one dataset row with `PageID=8992356` and
  matching scan/PAGE XML. The packaging explicitly maps images and PAGE XML
  to the same page and documents the scan-to-PageID derivation. Access image:
  [BHL WebP rendition](https://huggingface.co/datasets/finebooks/bhl-impact-gt/resolve/f57bb9e58785a3f9266c05880092ec76720450e5/images/birdsofgreatbrit02butl/birdsofgreatbrit02butl_0017_full.webp).
  Independent local inspection confirms the WebP is `2293 × 3062` pixels,
  exactly matching PAGE XML's declared `imageWidth`/`imageHeight`. The XML
  has 81 text regions; this checks geometry, not each transcription line.

These are permissions and sources for this **one isolated test**. They are not
publication/excerpt clearance for Dichiarazioni Pubbliche; no real source was
registered as CLEARED in the live source-use registry. Image, gold and OCR text
were held under `/tmp/dp238-102-gold-20261020` for private validation, outside
the repository, public static projection and production database.

## Immutable source and gold identities

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Published BHL-aligned WebP scan (image) | 139,448 | `4c4b38f3b29d4946ad8b54d4a15113262aec2a07994bc7f3b8309b55b8a1ef53` |
| Expert-corrected reference, plaintext | 2,449 | `24f0fcd6ed46aa20ed7658833606a7bf318921df7e80e7ce571aa5205881a039` |
| Expert-corrected PAGE XML | 28,474 | `a6425cf6a88982929157d2f550594abaa8387249e87f312e2838253181521691` |
| **Locally converted** one-page image-only PDF | 366,501 | `c72d2f580cb7baec451b83a39e56a6f8e32247e7fc2147f05ec77cfee2c09515` |

PDF creation: Pillow image-to-PDF at `resolution=120.0` on the downloaded
WebP. **The PDF is a local derivative** and must never be linked as if it were
a byte-identical original BHL PDF. The input image and expert reference have
separate SHA-256 checks; no model output was used to compose or adjust gold.

Before the first OCR attempt, `predeclared-acceptance.json` in the same
private folder fixed **CER ≤ 8%**, **WER ≤ 20%**, and exact preservation of
`not being recognized`, `85`, `81`, `73`. Normalization: Unicode NFKC,
casefold, collapse whitespace, retain punctuation and numerals. These are
experimental limits for this one page, **not** a project-wide release gate.
They have not been changed after observing the extraction.

## Native MiniPC proof and RED → GREEN regression

Executed the existing `ScannedPDFOCRParser` on the MiniPC in an isolated
source overlay, under `flock /tmp/dp238-ocr-gold.lock`, with **Poppler** and
**Tesseract 5.5.0**, `ita+eng/psm3/120dpi/scale2500`:

1. **Original parser:** valid unencrypted image-only PDF returned
   `FAILED/DOCUMENT_PDF_CORRUPT` after ~4.45 s. `pdfinfo` verified one page,
   `Encrypted: no`, `JavaScript: no`, `Form: none`, `Suspects: no`. Direct
   `_extract_ocr_pages` reproduced `ValueError: Invalid OCR character`.
2. **Cause:** Tesseract TSV's OCR word started with a literal `"`. The default
   `csv.DictReader` treated the quote as CSV field quoting, incorrectly joined
   subsequent *tab-delimited word rows* into a multiline field. A focused
   regression using real TSV semantics failed RED with that same error.
3. **Fix:** `csv.DictReader(..., delimiter="\t", quoting=csv.QUOTE_NONE)`
   preserves OCR quotes literally; both balanced and unbalanced quotes have
   regression coverage. Bumped the private OCR derivation method version
   from `...-v1` to `...-v2` to prevent old Captures silently replaying a
   different parser's result. The focused test then passed GREEN.
4. **Same frozen real BHL source:** the corrected adapter returned
   `SUCCEEDED`, one explicit page selector, **572 word boxes**, 4.402 s,
   Tesseract 5.5.0, `verbatim_reviewed=false`, source semantic fidelity
   `INDEPENDENT_IMAGE_GOLD_REQUIRED` and critical spans
   `HELD_INDEPENDENT_REVIEW_REQUIRED`.

| Frozen benchmark comparison | Measured | Threshold | Result |
| --- | ---: | ---: | --- |
| Character error rate (whole-page Levenshtein) | **61.3559%** | ≤ 8% | FAIL |
| Word error rate (whole-page Levenshtein) | **68.4859%** | ≤ 20% | FAIL |
| Negation `not being recognized` | Preserved | Must preserve | PASS |
| Exact numerals `85`, `81`, `73` | `85`, `73` preserved; **`81` missing** | All preserved | FAIL |

The scan has **two-column table-of-contents layout**. The very high whole-page
edit rates likely combine column/reading-order mismatch and recognition errors;
the missing critical number is an independent reason to hold. The benchmark
is intentionally order-sensitive and is **not** a layout-aligned per-line CER.
No post-hoc rearrangement or manual editing of the gold or OCR text was used to
improve the score. Exact result: **`HOLD_PRIVATE_GOLD_FAILURE`**. Neither OCR
confidence nor this external reference automatically grants quote authority.

**Repeatability limitation observed after the first success:** the same
immutable PDF, gold, parser and lock were run again under a MiniPC load
average of approximately `19.01` (15:19 local). This second run failed
closed as `DOCUMENT_OCR_PROCESS_FAILED` in 14.351 seconds: Tesseract's bounded
native subprocess hit its 12-second timeout. It produced **no** word boxes
or candidate output; the benchmark remained `HOLD_PRIVATE_GOLD_FAILURE`.
Consequently, the first-run accuracy figures above are authentic but **native
repeatability is not proven**. This load-related timeout hypothesis has not
been independently isolated and is not grounds to relax the OCR resource
guard or certify the original acceptance.

Local Python verification after the fix:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest \
  tests.test_dp238_ocr_tsv_quoting tests.test_dp238_scanned_ocr \
  tests.test_dp238_document_extraction -q
# Ran 23 tests — OK
```

## Remaining acceptance boundary

- This is one authentic, openly reusable **historical natural-history** scan
  and one independent expert-reviewed gold page. It is not the original
  DP-238 multi-document acceptance matrix: no judicial allegation-vs-fact,
  reported vs direct speech, role ambiguity/homonym, intentional redaction or
  incomplete-page expert references were certified. NASA's separately
  machine-generated `.txt` from PR #100 remains *not* independent OCR gold.
- The BHL benchmark **failed the frozen thresholds**, so it provides evidence
  for HOLD and shows a parser bug fixed; it does not prove sufficient OCR
  accuracy on difficult source documents.
- The run used temporary source files and **no durable/live Capture→PostgreSQL
  Passage consumer**, no source-use registry writes, no remote OCR service,
  no public projection and no direct quotation. Installed consumer,
  version/supersession and public non-disclosure proof remain on #46.
- The extraction semantics change between parser versions. Existing `...-v1`
  captured extractions must remain pinned to their original parser/version;
  a new reviewable derivation is required under `...-v2`.

The follow-up #102 remains **OPEN**. Owner choice for the larger #46 matrix:
**A)** accept this independently supplied, rights-attributed BHL data as an
experimental technical OCR **HOLD** benchmark and separately commission
role/redaction gold later; or **B)** commission a qualified independent
annotator now for a separately cleared official/judicial scan covering the
remaining six acceptance categories. No public release in either case.

# DP-238 document extraction: upstream adapters and license boundary

Verified on 2026-10-20 for [issue #46](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/46).
The project reuses installed upstream engines through bounded, opt-in parser
adapters; no upstream source, binaries, models or PDF source material are copied
into this repository by the page-navigation change.

| Upstream | License / verification | Pinned provenance and use |
| --- | --- | --- |
| [pypdf](https://github.com/py-pdf/pypdf) | Upstream [LICENSE](https://github.com/py-pdf/pypdf/blob/main/LICENSE) contains the BSD three-condition notice (GitHub API returns `NOASSERTION`, so check the actual license text). | Release [6.21.1](https://github.com/py-pdf/pypdf/releases/tag/6.21.1), 2026-10-17; tag target `1a6de8d43c3a931b1ab3643c8dee2c9b51a32d42`; optional `document-pdf` extra constrains `pypdf>=6,<7`. Only born-digital PDF decoding in the existing isolated worker. |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | [Apache-2.0](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE). | Upstream release [5.5.3](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3), 2026-07-24, target `db0ec62f81b0737fbbe184d8fea40af5738f8eef`; installed MiniPC engine observed as **5.5.0**. The existing adapter records the executed binary's actual version in each extraction version. |
| [Poppler](https://poppler.freedesktop.org/) | **GPL-family licensing**, including GPL-licensed Poppler tools; flag to owner before bundling/distributing any executable. | Installed MiniPC `pdftoppm` **26.01.0** and `pdfinfo`; the existing OCR adapter invokes OS executables. No newly vendored/copyleft donor source or executable. |

The native/private OCR and PDF adapters already exist in
`document_scanned_ocr.py` and `document_pdf_extraction.py`. DP-238 source page
navigation reuses their recorded `page_selectors` and the existing exact
locator/source-hash resolver. An OCR confidence value is an unreviewed candidate,
never proof of verbatim original text or of a quoted person's identity.

The authentic NASA NTRS source-family rights and SHA evidence is recorded in
`docs/reviews/2026-10-16-dp238-private-native-ocr-proof.md` for record
`19640005616`. Its private 1–2-page crop is a derivative with its **own** SHA
and URN. A private PDF page link may only be made for an approved *self-original*
Capture whose live source SHA matches that very Capture; it cannot point a crop
to the parent's different bytes as if they were identical.

An independent human-transcribed gold set for mixed columns, scan defects,
redactions and role-sensitive excerpts is still required for DP-238 acceptance.
The existing synthetic reference and official companion `.txt` cannot be
presented as independently verified OCR ground truth.

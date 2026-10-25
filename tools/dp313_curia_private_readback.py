"""DP-313 bounded offline readback of one official Curia judgment in PRIVATE_HOLD.

The caller supplies a previously downloaded, pinned official HTML response.
The public Curia copyright notice permits reproduction with attribution, but
this technical readback does not register DP extraction/privacy rights, attest
the edition's currentness, persist a Content Capture or authorize publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from dichiarazioni_pubbliche.procedural_document_roles import (
    AssertionKind,
    DocumentPerson,
    DocumentaryRole,
    PrivacyClass,
    ProceduralDocumentSource,
    ProceduralSpanAnnotation,
    ProceduralStatus,
    evaluate_procedural_document,
)

SOURCE_URL = "https://juris.curia.europa.eu/juris/document/document.jsf?docid=312911&doclang=IT"
SOURCE_COPYRIGHT = "https://curia.europa.eu/site/jcms/qua1_6625/"
SOURCE_ECLI = "ECLI:EU:C:2026:519"
SOURCE_SHA256 = "1bcb37cfb1d9f6c949dbe0b57fdb391ad9f5ba89102ba48271c53a25f40a72ae"
JUDGMENT_DATE = "2026-06-25"


class _DocumentText(HTMLParser):
    """Isolate judgment DOM text, excluding changing HTML session controls."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active = False
        self.depth = 0
        self.skip = 0
        self.parts: list[str] = []
        self.found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div" and dict(attrs).get("id") == "document_content":
            self.active = True
            self.found = True
            self.depth = 1
        elif self.active and tag == "div":
            self.depth += 1
        elif self.active and tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if not self.active:
            return
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.active = False
        elif tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if self.active and not self.skip:
            self.parts.append(data)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _official_text(data: bytes) -> str:
    if not isinstance(data, bytes) or not 100 <= len(data) <= 500_000:
        raise ValueError("OFFICIAL_HTML_SIZE_INVALID")
    try:
        html = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("OFFICIAL_HTML_ENCODING_INVALID") from exc
    if SOURCE_ECLI not in html:
        raise ValueError("ECLI_MISMATCH")
    parser = _DocumentText()
    parser.feed(html)
    if not parser.found or parser.active:
        raise ValueError("DOCUMENT_CONTENT_MISSING")
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    if not text:
        raise ValueError("DOCUMENT_CONTENT_MISSING")
    return text


def _fragment(text: str, pattern: str, *, after: int = 0) -> tuple[int, int]:
    matched = re.search(pattern, text[after:])
    if matched is None:
        raise ValueError("OFFICIAL_SPAN_MISSING")
    return after + matched.start(), after + matched.end()


def evaluate_curia_private(
    html: bytes, *, expected_sha256: str = SOURCE_SHA256,
) -> dict[str, object]:
    """Read back three exact source-bound annotations with no automatic review."""
    text = _official_text(html)
    actual_digest = _digest(text)
    if actual_digest != expected_sha256:
        raise ValueError("SOURCE_DIGEST_CHANGED")
    if (
        "SENTENZA DELLA CORTE (Ottava Sezione)" not in text
        or "25 giugno 2026" not in text
        or "Per questi motivi" not in text
    ):
        raise ValueError("OFFICIAL_DOCUMENT_IDENTITY_UNVERIFIED")

    disposition_start = text.index("Per questi motivi")
    allegation = _fragment(text, r"Con la sua impugnazione, VT chiede l’annullamento")
    disposition = _fragment(
        text, r"1\) La sentenza del Tribunale.{0,270}?è annullata\.",
        after=disposition_start,
    )
    prior_decision = _fragment(
        text, r"di non iscrivere il nome di VT",
        after=disposition[1],
    )
    annotations = []
    for (start, end), kind, role, by, quoted, polarity in (
        (allegation, AssertionKind.ALLEGATION, DocumentaryRole.ALLEGATION,
         "person:vt-anonymized", None, "AFFIRMED"),
        (disposition, AssertionKind.FINDING_ORDER, DocumentaryRole.COURT_DECISION,
         "body:cjeu", None, "AFFIRMED"),
        (prior_decision, AssertionKind.QUOTED_TEXT, DocumentaryRole.REPORTER,
         "body:cjeu", "body:epso-board", "NEGATED"),
    ):
        annotations.append(ProceduralSpanAnnotation(
            start_char=start,
            end_char=end,
            page_number=1,  # one normalized HTML document, not a PDF page
            text_sha256=_digest(text[start:end]),
            annotation_review_ref=None,
            assertion_kind=kind,
            speaker_role=role,
            asserted_by_ref=by,
            subject_person_refs=("person:vt-anonymized",),
            procedural_party_refs=("person:vt-anonymized",),
            status=ProceduralStatus.UNKNOWN,
            status_jurisdiction_ref="jurisdiction:eu-cjeu",
            status_effective_date=JUDGMENT_DATE,
            negation_polarity=polarity,
            negation_review_ref=None,
            quoted_author_ref=quoted,
        ))

    source = ProceduralDocumentSource(
        capture_ref="unpersisted-offline-probe:" + actual_digest,
        original_record_ref=SOURCE_URL,
        family_ref="family:curia-c-622-24-p",
        version_ref=SOURCE_ECLI + ":sha256:" + actual_digest,
        source_kind="COURT_ORDER",
        source_text=text,
        source_sha256=actual_digest,
        jurisdiction_ref="jurisdiction:eu-cjeu",
        issued_date=JUDGMENT_DATE,
        effective_date=JUDGMENT_DATE,
        document_author_ref="body:cjeu",
        reporting_body_ref="body:cjeu",
        authenticity_review_ref=None,
        source_format="NATIVE_TEXT",
        version_current=False,  # no attested currentness / later-correction check
        page_ranges=((1, 0, len(text)),),
        language="it",
    )
    decision = evaluate_procedural_document(
        source, (DocumentPerson("person:vt-anonymized", PrivacyClass.UNKNOWN),),
        tuple(annotations),
    )
    if decision.state != "HOLD" or any(row.state != "HOLD" for row in decision.spans):
        raise ValueError("UNEXPECTED_PROCEDURAL_PROMOTION")

    return {
        "state": "PRIVATE_HOLD",
        "ecli": SOURCE_ECLI,
        "source_url": SOURCE_URL,
        "source_copyright": SOURCE_COPYRIGHT,
        "source_sha256": actual_digest,
        "original_record_ref": source.original_record_ref,
        "source_family_ref": source.family_ref,
        "locator_type": "NORMALIZED_OFFICIAL_HTML_CHAR_OFFSETS",
        "source_publication_date": JUDGMENT_DATE,
        "licence_assessment": "CURIA_JUDGMENT_REPRODUCTION_WITH_ATTRIBUTION",
        "rights_registry_current_for_extract": False,
        "authenticity_review_observed": False,
        "privacy_review_observed": False,
        "extraction_authorized": False,
        "publication_authorized": False,
        "span_roles": [
            "PARTY_ALLEGATION", "COURT_DISPOSITION", "PRIOR_DECISION_QUOTATION",
        ],
        "speakers": [row.asserted_by_ref for row in decision.spans],
        "quoted_authors": [row.quoted_author_ref for row in decision.spans],
        "span_states": [row.state for row in decision.spans],
        "span_reason_codes": [list(row.reason_codes) for row in decision.spans],
        "span_locators": [
            {"start_char": row.start_char, "end_char": row.end_char,
             "sha256": row.text_sha256}
            for row in decision.spans
        ],
        "underlying_fact_assessments": [
            row.underlying_fact_assessment for row in decision.spans
        ],
        "binding_sha256": decision.binding_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True,
                        help="Existing official judgment HTML; no fetch or DB write")
    args = parser.parse_args()
    try:
        data = args.html.read_bytes()
        result = evaluate_curia_private(data)
    except (OSError, ValueError) as exc:
        print(json.dumps({"state": "HOLD", "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""DP-313: pure, private, fail-closed procedural document role hypotheses.

Inputs are explicit, source-bound *review annotations*. This module does not
extract judicial truth from arbitrary text, attest authenticity/reviewer identity,
perform OCR, grant rights, authorize publication or decide guilt/innocence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum
from typing import Sequence


PROCEDURAL_DOCUMENT_ROLES_VERSION = "procedural-document-roles-v1"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NEGATIONS = re.compile(r"\b(?:non|mai|nessun[ao]?|not|never|no|nicht|nie|kein(?:e|en)?)\b", re.I)
_PROCEDURAL_WORDS = {
    "INVESTIGATED": re.compile(r"\b(?:indagat[oaie]|investigated)\b", re.I),
    "CHARGED": re.compile(r"\b(?:imputat[oaie]|defendant|charged)\b", re.I),
    "CONVICTED": re.compile(r"\b(?:condannat[oaie]|condanna|convicted|sentenced)\b", re.I),
    "ACQUITTED": re.compile(r"\b(?:assolt[oaie]|assoluzione|acquitted)\b", re.I),
    "DISMISSED": re.compile(r"\b(?:archiviat[oaie]|archiviazione|dismissed)\b", re.I),
}


class DocumentaryRole(StrEnum):
    AUTHOR = "AUTHOR"
    REPORTER = "REPORTER"
    QUOTED = "QUOTED"
    WITNESS = "WITNESS"
    ALLEGATION = "ALLEGATION"
    COURT_DECISION = "COURT_DECISION"


class AssertionKind(StrEnum):
    ALLEGATION = "ALLEGATION"
    TESTIMONY = "TESTIMONY"
    FINDING_ORDER = "FINDING_ORDER"
    DECISION_REASONING = "DECISION_REASONING"
    INSTITUTIONAL_FACT = "INSTITUTIONAL_FACT"
    QUOTED_TEXT = "QUOTED_TEXT"


class ProceduralStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    INVESTIGATED = "INVESTIGATED"
    CHARGED = "CHARGED"
    CONVICTED = "CONVICTED"
    ACQUITTED = "ACQUITTED"
    DISMISSED = "DISMISSED"


class PrivacyClass(StrEnum):
    PUBLIC_FIGURE = "PUBLIC_FIGURE"
    PRIVATE_PERSON = "PRIVATE_PERSON"
    MINOR = "MINOR"
    VICTIM = "VICTIM"
    INCIDENTAL = "INCIDENTAL"
    UNKNOWN = "UNKNOWN"


_ROLE_KINDS = {
    DocumentaryRole.AUTHOR: {AssertionKind.INSTITUTIONAL_FACT, AssertionKind.ALLEGATION},
    DocumentaryRole.REPORTER: {AssertionKind.QUOTED_TEXT, AssertionKind.ALLEGATION},
    DocumentaryRole.QUOTED: {AssertionKind.QUOTED_TEXT},
    DocumentaryRole.WITNESS: {AssertionKind.TESTIMONY},
    DocumentaryRole.ALLEGATION: {AssertionKind.ALLEGATION},
    DocumentaryRole.COURT_DECISION: {
        AssertionKind.FINDING_ORDER, AssertionKind.DECISION_REASONING,
    },
}


@dataclass(frozen=True)
class ProceduralDocumentSource:
    capture_ref: str
    original_record_ref: str
    family_ref: str
    version_ref: str
    source_kind: str
    source_text: str
    source_sha256: str
    jurisdiction_ref: str
    issued_date: str
    effective_date: str
    document_author_ref: str
    reporting_body_ref: str
    authenticity_review_ref: str | None
    source_format: str
    version_current: bool
    supersedes_version_ref: str | None = None
    appeal_state: str = "UNKNOWN"
    page_ranges: tuple[tuple[int, int, int], ...] = ()
    language: str = "it"


@dataclass(frozen=True)
class DocumentPerson:
    person_ref: str
    privacy_class: PrivacyClass
    alias_candidate_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProceduralSpanAnnotation:
    start_char: int
    end_char: int
    page_number: int
    text_sha256: str
    annotation_review_ref: str | None
    assertion_kind: AssertionKind
    speaker_role: DocumentaryRole
    asserted_by_ref: str
    subject_person_refs: tuple[str, ...]
    procedural_party_refs: tuple[str, ...]
    status: ProceduralStatus
    status_jurisdiction_ref: str
    status_effective_date: str
    negation_polarity: str
    negation_review_ref: str | None
    quoted_author_ref: str | None = None
    ocr_original_excerpt: str | None = None
    ocr_original_review_ref: str | None = None
    ocr_confidence: float | None = None


@dataclass(frozen=True)
class ProceduralSpanDecision:
    state: str
    start_char: int
    end_char: int
    page_number: int
    text_sha256: str
    assertion_kind: AssertionKind
    speaker_role: DocumentaryRole
    asserted_by_ref: str
    document_author_ref: str
    reporting_body_ref: str
    quoted_author_ref: str | None
    subject_person_refs: tuple[str, ...]
    procedural_party_refs: tuple[str, ...]
    status: ProceduralStatus
    status_jurisdiction_ref: str
    status_effective_date: str
    negation_polarity: str
    reason_codes: tuple[str, ...]
    annotation_binding_sha256: str
    underlying_fact_assessment: str = "NOT_EVALUATED"

    @property
    def publication_authority(self) -> bool:
        return False

    @property
    def rights_authority(self) -> bool:
        return False


@dataclass(frozen=True)
class ProceduralDocumentDecision:
    state: str
    capture_ref: str
    original_record_ref: str
    family_ref: str
    version_ref: str
    source_sha256: str
    spans: tuple[ProceduralSpanDecision, ...]
    binding_sha256: str
    supersedes_version_ref: str | None
    appeal_state: str
    version: str = PROCEDURAL_DOCUMENT_ROLES_VERSION

    @property
    def publication_authority(self) -> bool:
        return False

    @property
    def rights_authority(self) -> bool:
        return False

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProceduralFamilyAssessment:
    state: str
    observed_family_count: int
    groups: tuple[tuple[str, tuple[str, ...]], ...]
    reason_codes: tuple[str, ...]
    independent_evidence_proven: int = 0
    version: str = PROCEDURAL_DOCUMENT_ROLES_VERSION


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprint(value: object) -> str:
    return _sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _date(value: str, field: str) -> date:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ValueError(f"PROCEDURAL_{field}_DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"PROCEDURAL_{field}_DATE_INVALID") from exc


def _validate_source(source: ProceduralDocumentSource) -> None:
    if not isinstance(source, ProceduralDocumentSource):
        raise ValueError("PROCEDURAL_DOCUMENT_REQUIRED")
    if (
        not isinstance(source.source_text, str)
        or not (0 < len(source.source_text) <= 2_000_000)
        or not isinstance(source.source_sha256, str)
        or not _SHA256_RE.fullmatch(source.source_sha256)
        or _sha256(source.source_text) != source.source_sha256
    ):
        raise ValueError("PROCEDURAL_SOURCE_HASH_MISMATCH")
    if source.source_kind not in {
        "COURT_ORDER", "PROSECUTION_FILING", "WITNESS_STATEMENT", "NEWS_REPORT", "OTHER",
    } or source.source_format not in {"NATIVE_TEXT", "OCR"}:
        raise ValueError("PROCEDURAL_SOURCE_TYPE_UNSUPPORTED")
    if not isinstance(source.language, str):
        raise ValueError("PROCEDURAL_LANGUAGE_INVALID")
    if not isinstance(source.version_current, bool):
        raise ValueError("PROCEDURAL_VERSION_CURRENTNESS_INVALID")
    for field in ("capture_ref", "version_ref", "jurisdiction_ref", "document_author_ref",
                  "reporting_body_ref"):
        value = getattr(source, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"PROCEDURAL_{field.upper()}_REQUIRED")
    _date(source.issued_date, "ISSUED")
    _date(source.effective_date, "EFFECTIVE")
    if source.supersedes_version_ref == source.version_ref:
        raise ValueError("PROCEDURAL_SELF_SUPERSESSION_REFUSED")
    if source.appeal_state not in {"UNKNOWN", "NONE", "PENDING", "FINAL", "SUPERSEDED"}:
        raise ValueError("PROCEDURAL_APPEAL_STATE_INVALID")
    if not isinstance(source.page_ranges, tuple) or len(source.page_ranges) > 10000:
        raise ValueError("PROCEDURAL_PAGE_RANGES_INVALID")
    previous_end = 0
    previous_page = 0
    for page in source.page_ranges:
        if (
            not isinstance(page, tuple)
            or len(page) != 3
            or any(not isinstance(value, int) or isinstance(value, bool) for value in page)
            or page[0] < 1
            or page[0] <= previous_page
            or page[1] != previous_end
            or not page[1] < page[2] <= len(source.source_text)
        ):
            raise ValueError("PROCEDURAL_PAGE_RANGES_INVALID")
        previous_end = page[2]
        previous_page = page[0]
    if source.page_ranges and previous_end != len(source.source_text):
        raise ValueError("PROCEDURAL_PAGE_RANGES_INVALID")


def evaluate_procedural_document(
    source: ProceduralDocumentSource,
    persons: Sequence[DocumentPerson],
    spans: Sequence[ProceduralSpanAnnotation],
) -> ProceduralDocumentDecision:
    """Evaluate source-bound annotations without generating new natural-language claims.

    Source/review refs in this *private* receipt are caller-supplied and remain
    untrusted: neither CANDIDATE_PRIVATE nor a purported official document is
    an authenticity attestation, factual verdict, verified identity or publish grant.
    """
    _validate_source(source)
    if not isinstance(persons, (tuple, list)) or len(persons) > 64:
        raise ValueError("PROCEDURAL_PERSONS_INVALID")
    if not isinstance(spans, (tuple, list)) or not 1 <= len(spans) <= 64:
        raise ValueError("PROCEDURAL_SPANS_INVALID")
    person_by_id: dict[str, DocumentPerson] = {}
    for person in persons:
        if (
            not isinstance(person, DocumentPerson)
            or not isinstance(person.person_ref, str)
            or not person.person_ref.strip()
            or person.person_ref in person_by_id
            or not isinstance(person.privacy_class, PrivacyClass)
            or not isinstance(person.alias_candidate_refs, tuple)
            or any(not isinstance(ref, str) or not ref.strip() for ref in person.alias_candidate_refs)
        ):
            raise ValueError("PROCEDURAL_PERSON_IDENTITY_INPUT_INVALID")
        person_by_id[person.person_ref] = person

    results: list[ProceduralSpanDecision] = []
    previous_end = -1
    for span in spans:
        if not isinstance(span, ProceduralSpanAnnotation):
            raise ValueError("PROCEDURAL_SPAN_ANNOTATION_INVALID")
        if (
            not isinstance(span.start_char, int) or isinstance(span.start_char, bool)
            or not isinstance(span.end_char, int) or isinstance(span.end_char, bool)
            or not (0 <= span.start_char < span.end_char <= len(source.source_text))
            or span.start_char < previous_end
        ):
            raise ValueError("PROCEDURAL_SPAN_RANGE_INVALID")
        previous_end = span.end_char
        if not isinstance(span.subject_person_refs, tuple) or not isinstance(
            span.procedural_party_refs, tuple
        ):
            raise ValueError("PROCEDURAL_PERSON_REFS_INVALID")
        if any(not isinstance(v, str) or not v.strip() for v in (
            *span.subject_person_refs, *span.procedural_party_refs
        )):
            raise ValueError("PROCEDURAL_PERSON_REFS_INVALID")
        excerpt = source.source_text[span.start_char:span.end_char]
        codes: list[str] = []
        if not isinstance(span.text_sha256, str) or (
            span.text_sha256 != _sha256(excerpt)
        ):
            codes.append("SPAN_HASH_MISMATCH")
        if not isinstance(span.page_number, int) or isinstance(span.page_number, bool) or (
            span.page_number < 1
        ):
            codes.append("PAGE_LOCATOR_INVALID")
        if not source.page_ranges:
            codes.append("PAGE_BOUNDARIES_UNVERIFIED")
        elif not any(
            page == span.page_number
            and begin <= span.start_char < span.end_char <= finish
            for page, begin, finish in source.page_ranges
        ):
            codes.append("PAGE_SPAN_BINDING_MISMATCH")
        if not isinstance(span.annotation_review_ref, str) or not span.annotation_review_ref.strip():
            codes.append("ANNOTATION_REVIEW_UNVERIFIED")
        if source.language not in {"it", "en"}:
            codes.append("PROCEDURAL_LANGUAGE_UNCALIBRATED")
        if not isinstance(source.authenticity_review_ref, str) or not (
            source.authenticity_review_ref.strip()
        ):
            codes.append("SOURCE_AUTHENTICITY_UNVERIFIED")
        if not isinstance(source.family_ref, str) or not source.family_ref.strip():
            codes.append("SOURCE_FAMILY_UNRESOLVED")
        if not isinstance(source.original_record_ref, str) or not (
            source.original_record_ref.strip()
        ):
            codes.append("SOURCE_ORIGIN_UNVERIFIED")
        if not source.version_current or source.appeal_state == "SUPERSEDED":
            codes.append("DOCUMENT_CURRENTNESS_UNVERIFIED")
        if source.appeal_state == "PENDING":
            codes.append("APPEAL_PENDING_NONFINAL")
        if (
            not isinstance(span.speaker_role, DocumentaryRole)
            or not isinstance(span.assertion_kind, AssertionKind)
            or span.assertion_kind not in _ROLE_KINDS.get(span.speaker_role, ())
        ):
            codes.append("ROLE_ASSERTION_KIND_MISMATCH")
        if (
            span.speaker_role == DocumentaryRole.COURT_DECISION
            and source.source_kind != "COURT_ORDER"
        ):
            codes.append("NON_COURT_SOURCE_CANNOT_ATTEST_ORDER")
        if span.asserted_by_ref != source.document_author_ref and (
            span.speaker_role in {DocumentaryRole.AUTHOR, DocumentaryRole.COURT_DECISION}
        ):
            codes.append("DOCUMENT_AUTHOR_ROLE_CONFLICT")
        if span.speaker_role == DocumentaryRole.QUOTED and (
            span.quoted_author_ref != span.asserted_by_ref
        ):
            codes.append("QUOTED_AUTHOR_ATTRIBUTION_UNVERIFIED")
        if (
            span.speaker_role == DocumentaryRole.REPORTER
            and span.assertion_kind == AssertionKind.QUOTED_TEXT
            and not span.quoted_author_ref
        ):
            codes.append("QUOTED_AUTHOR_ATTRIBUTION_UNVERIFIED")
        if (
            span.speaker_role == DocumentaryRole.WITNESS
            and span.asserted_by_ref not in person_by_id
        ):
            codes.append("WITNESS_IDENTITY_UNVERIFIED")
        if not isinstance(span.asserted_by_ref, str) or not span.asserted_by_ref.strip():
            codes.append("ASSERTION_SPEAKER_UNVERIFIED")
        if not span.subject_person_refs:
            codes.append("SUBJECT_IDENTITY_UNVERIFIED")
        for person_ref in (span.asserted_by_ref, span.quoted_author_ref):
            if person_ref is None:
                continue
            person = person_by_id.get(person_ref)
            if person is not None and person.privacy_class != PrivacyClass.PUBLIC_FIGURE:
                codes.append("SPEAKER_PRIVACY_REVIEW_REQUIRED")
            if person is not None and len(set(person.alias_candidate_refs)) > 1:
                codes.append("PERSON_ALIAS_COLLISION")
        if span.assertion_kind == AssertionKind.QUOTED_TEXT and (
            span.quoted_author_ref not in person_by_id
        ):
            codes.append("QUOTED_AUTHOR_IDENTITY_UNVERIFIED")
        for person_ref in set((*span.subject_person_refs, *span.procedural_party_refs)):
            if person_ref not in person_by_id:
                codes.append("SUBJECT_IDENTITY_UNVERIFIED")
            else:
                person = person_by_id[person_ref]
                if person.privacy_class != PrivacyClass.PUBLIC_FIGURE:
                    codes.append("SUBJECT_PRIVACY_REVIEW_REQUIRED")
                if len(set(person.alias_candidate_refs)) > 1:
                    codes.append("PERSON_ALIAS_COLLISION")
        if not isinstance(span.status, ProceduralStatus):
            codes.append("PROCEDURAL_STATUS_UNSUPPORTED")
        else:
            # A status mentioned in testimony, a reporter's quotation or a
            # party allegation does not attest that procedural state, even
            # when embedded verbatim in an authentic court order. Keep such
            # words attributable without inheriting the court's authority.
            if span.status != ProceduralStatus.UNKNOWN and (
                span.speaker_role, span.assertion_kind
            ) not in {
                (DocumentaryRole.AUTHOR, AssertionKind.INSTITUTIONAL_FACT),
                (DocumentaryRole.COURT_DECISION, AssertionKind.FINDING_ORDER),
            }:
                codes.append("ASSERTION_ROLE_NOT_STATUS_AUTHORITY")
            hits = {
                status for status, pattern in _PROCEDURAL_WORDS.items()
                if pattern.search(excerpt)
            }
            if len(hits) > 1:
                codes.append("MULTIPLE_PROCEDURAL_STATUS_TERMS_UNRESOLVED")
            if hits and source.source_kind in {"NEWS_REPORT", "OTHER"}:
                codes.append("SECONDARY_SOURCE_NOT_STATUS_AUTHORITY")
            if hits and source.source_kind == "WITNESS_STATEMENT":
                codes.append("WITNESS_SOURCE_NOT_STATUS_AUTHORITY")
            if hits.intersection({"CONVICTED", "ACQUITTED", "DISMISSED"}) and (
                source.source_kind == "PROSECUTION_FILING"
            ):
                codes.append("PROSECUTION_IS_NOT_COURT_DISPOSITION")
            if hits and span.status.value not in hits:
                codes.append("PROCEDURAL_STATUS_LEXICAL_CONFLICT")
            if span.status != ProceduralStatus.UNKNOWN and span.status.value not in hits:
                codes.append("PROCEDURAL_STATUS_SOURCE_SPAN_UNVERIFIED")
            if hits and span.status == ProceduralStatus.UNKNOWN:
                codes.append("PROCEDURAL_STATUS_UNRESOLVED")
            if hits and span.negation_polarity == "NEGATED":
                codes.append("NEGATED_STATUS_NOT_ESTABLISHED")
        if span.status_jurisdiction_ref != source.jurisdiction_ref:
            codes.append("STATUS_JURISDICTION_MISMATCH")
        if _date(span.status_effective_date, "STATUS_EFFECTIVE") > _date(
            source.issued_date, "ISSUED"
        ):
            codes.append("STATUS_EFFECTIVE_AFTER_DOCUMENT")
        if span.negation_polarity not in {"AFFIRMED", "NEGATED", "UNKNOWN"}:
            codes.append("NEGATION_POLARITY_UNSUPPORTED")
        elif span.negation_polarity == "UNKNOWN" or (
            bool(_NEGATIONS.search(excerpt)) != (span.negation_polarity == "NEGATED")
        ):
            codes.append("NEGATION_POLARITY_CONFLICT")
        if _NEGATIONS.search(excerpt) and not span.negation_review_ref:
            codes.append("NEGATION_REVIEW_REQUIRED")
        if source.source_format == "OCR":
            if (
                not isinstance(span.ocr_original_excerpt, str)
                or not span.ocr_original_excerpt
                or not isinstance(span.ocr_original_review_ref, str)
                or not span.ocr_original_review_ref.strip()
                or not isinstance(span.ocr_confidence, (float, int))
                or isinstance(span.ocr_confidence, bool)
                or not 0 <= span.ocr_confidence <= 1
            ):
                codes.append("OCR_ORIGINAL_COMPARISON_REQUIRED")
            elif excerpt != span.ocr_original_excerpt:
                # Strict byte-for-byte test; OCR heuristic confidence is not a
                # substitute for comparing names, dates and critical negation.
                codes.append("OCR_ORIGINAL_MISMATCH")
        payload = asdict(span)
        payload.pop("ocr_original_excerpt", None)
        payload["ocr_original_sha256"] = (
            _sha256(span.ocr_original_excerpt)
            if isinstance(span.ocr_original_excerpt, str) else None
        )
        results.append(ProceduralSpanDecision(
            state="HOLD" if codes else "CANDIDATE_PRIVATE",
            start_char=span.start_char,
            end_char=span.end_char,
            page_number=span.page_number,
            text_sha256=_sha256(excerpt),
            assertion_kind=span.assertion_kind,
            speaker_role=span.speaker_role,
            asserted_by_ref=span.asserted_by_ref,
            document_author_ref=source.document_author_ref,
            reporting_body_ref=source.reporting_body_ref,
            quoted_author_ref=span.quoted_author_ref,
            subject_person_refs=span.subject_person_refs,
            procedural_party_refs=span.procedural_party_refs,
            status=span.status,
            status_jurisdiction_ref=span.status_jurisdiction_ref,
            status_effective_date=span.status_effective_date,
            negation_polarity=span.negation_polarity,
            reason_codes=tuple(dict.fromkeys(codes)),
            annotation_binding_sha256=_fingerprint(payload),
        ))
    input_source = asdict(source)
    input_source.pop("source_text")
    binding = _fingerprint({
        "source": input_source,
        "persons": [asdict(person) for person in persons],
        "decisions": [asdict(row) for row in results],
        "version": PROCEDURAL_DOCUMENT_ROLES_VERSION,
    })
    return ProceduralDocumentDecision(
        state="HOLD" if any(row.state == "HOLD" for row in results) else "CANDIDATE_PRIVATE",
        capture_ref=source.capture_ref,
        original_record_ref=source.original_record_ref,
        family_ref=source.family_ref,
        version_ref=source.version_ref,
        source_sha256=source.source_sha256,
        spans=tuple(results),
        binding_sha256=binding,
        supersedes_version_ref=source.supersedes_version_ref,
        appeal_state=source.appeal_state,
    )


def assess_procedural_independence(
    sources: Sequence[ProceduralDocumentSource],
) -> ProceduralFamilyAssessment:
    """Group declared derivation families; never claim evidentiary independence."""
    if not isinstance(sources, (tuple, list)) or len(sources) > 128:
        raise ValueError("PROCEDURAL_FAMILY_INPUT_INVALID")
    families: dict[str, set[str]] = {}
    origin_to_family: dict[str, str] = {}
    digest_to_family: dict[str, str] = {}
    codes: list[str] = []
    for source in sources:
        _validate_source(source)
        if not isinstance(source.family_ref, str) or not source.family_ref.strip():
            codes.append("SOURCE_FAMILY_UNRESOLVED")
            continue
        families.setdefault(source.family_ref, set()).add(source.capture_ref)
        for index, mapping, code in (
            (source.original_record_ref, origin_to_family, "CROSS_FAMILY_ORIGIN_CONFLICT"),
            (source.source_sha256, digest_to_family, "CROSS_FAMILY_IDENTICAL_BYTES"),
        ):
            if not index:
                codes.append("SOURCE_ORIGIN_UNRESOLVED")
            elif index in mapping and mapping[index] != source.family_ref:
                codes.append(code)
            else:
                mapping[index] = source.family_ref
    groups = tuple(
        (family, tuple(sorted(captures)))
        for family, captures in sorted(families.items())
    )
    return ProceduralFamilyAssessment(
        state="HOLD" if codes else "OBSERVED_LINEAGES_ONLY",
        observed_family_count=len(families),
        groups=groups,
        reason_codes=tuple(dict.fromkeys(codes)),
    )


__all__ = [
    "AssertionKind", "DocumentPerson", "DocumentaryRole",
    "PROCEDURAL_DOCUMENT_ROLES_VERSION", "ProceduralDocumentDecision",
    "ProceduralDocumentSource", "ProceduralFamilyAssessment",
    "ProceduralSpanAnnotation", "ProceduralSpanDecision", "ProceduralStatus",
    "PrivacyClass", "assess_procedural_independence", "evaluate_procedural_document",
]

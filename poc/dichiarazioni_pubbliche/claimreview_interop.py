from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.domain_vocabulary import (
    FINDING_PUBLICATION_STATUS_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.policy.intent_policy import PUBLIC_ASSESSMENTS


CLAIMREVIEW_INTEROP_VERSION = "claimreview-interop-v1"
MAX_CITATIONS = 32
MAX_TEXT_CHARS = 8192

_FORBIDDEN_PRIVATE_KEYS = frozenset(
    {
        "raw_text",
        "private_text",
        "canonical_text",
        "transcript_text",
        "evidence_body",
        "raw_body",
        "provider_prompt",
        "rights_receipt",
        "internal_notes",
        "private_capture_path",
    }
)
_FORBIDDEN_RATING_KEYS = frozenset(
    {"ratingValue", "bestRating", "worstRating", "ratingCount", "reviewAspect"}
)


class ClaimReviewInteropError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "CLAIMREVIEW_INTEROP_INVALID").strip().upper()[:120]
        super().__init__(self.code)


@dataclass(frozen=True)
class FactCheckInteropRecord:
    finding_id: str
    claim_id: str
    assessment: str
    assessment_version: str
    publication_status: str
    publication_status_version: str
    policy_version: str
    verification_run_id: str
    published_at: str
    supersedes_id: str | None
    claimreview: dict[str, Any]
    interop_version: str = CLAIMREVIEW_INTEROP_VERSION
    publication_authority: bool = False


def _required_text(value: object, field: str, *, limit: int = MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClaimReviewInteropError(f"{field.upper()}_REQUIRED")
    return value.strip()[:limit]


def _optional_text(value: object, *, limit: int = MAX_TEXT_CHARS) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] or None


def _public_http_url(value: object, field: str) -> str:
    raw = _required_text(value, field, limit=4096)
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ClaimReviewInteropError(f"{field.upper()}_INVALID") from exc
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
    ):
        raise ClaimReviewInteropError(f"{field.upper()}_INVALID")
    return raw


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(child))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _assert_no_private_fields(dossier: Mapping[str, Any]) -> None:
    normalized = {
        re.sub(r"[-\s]+", "_", key).casefold()
        for key in _walk_keys(dossier)
    }
    if normalized & _FORBIDDEN_PRIVATE_KEYS:
        raise ClaimReviewInteropError("PRIVATE_FIELD_PRESENT")


def _assert_reviewed_public_input(dossier: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    finding = dossier.get("finding")
    if not isinstance(finding, Mapping):
        raise ClaimReviewInteropError("FINDING_REQUIRED")
    publication_status = _required_text(
        finding.get("publication_status"), "publication_status", limit=128
    )
    if publication_status != FindingPublicationStatus.PUBLISH.value:
        raise ClaimReviewInteropError("FINDING_NOT_PUBLISHED")
    reviews = finding.get("publication_review_ids")
    if (
        not isinstance(reviews, Sequence)
        or isinstance(reviews, (str, bytes, bytearray))
        or not reviews
        or not all(isinstance(value, str) and value.strip() for value in reviews)
    ):
        raise ClaimReviewInteropError("PUBLICATION_REVIEW_REQUIRED")
    assessment = _required_text(finding.get("assessment"), "assessment", limit=128)
    try:
        assessment_enum = VerificationAssessment(assessment)
    except ValueError as exc:
        raise ClaimReviewInteropError("ASSESSMENT_NON_CANONICAL") from exc
    if assessment_enum not in PUBLIC_ASSESSMENTS:
        raise ClaimReviewInteropError("ASSESSMENT_NOT_PUBLISHABLE")
    return finding, assessment


def _citation(evidence: Mapping[str, Any]) -> dict[str, Any]:
    evidence_reviews = evidence.get("evidence_review_ids")
    observation_reviews = evidence.get("observation_review_ids")
    if (
        not isinstance(evidence_reviews, Sequence)
        or isinstance(evidence_reviews, (str, bytes, bytearray))
        or not evidence_reviews
        or not isinstance(observation_reviews, Sequence)
        or isinstance(observation_reviews, (str, bytes, bytearray))
        or not observation_reviews
    ):
        raise ClaimReviewInteropError("EVIDENCE_REVIEW_REQUIRED")
    url = _public_http_url(evidence.get("url"), "evidence_url")
    result: dict[str, Any] = {"@type": "CreativeWork", "url": url}
    publisher = _optional_text(evidence.get("publisher"), limit=1024)
    if publisher:
        result["publisher"] = {"@type": "Organization", "name": publisher}
    published = _optional_text(evidence.get("publication_date"), limit=128)
    if published:
        result["datePublished"] = published
    return result


def _sidecars_are_public(dossier: Mapping[str, Any]) -> None:
    replies = dossier.get("rights_of_reply") or []
    if not isinstance(replies, Sequence) or isinstance(replies, (str, bytes, bytearray)):
        raise ClaimReviewInteropError("RIGHTS_OF_REPLY_INVALID")
    for reply in replies:
        if not isinstance(reply, Mapping) or str(reply.get("status") or "") != "PUBLISHED":
            raise ClaimReviewInteropError("UNAPPROVED_REPLY_PRESENT")


def build_claimreview_interop(dossier: Mapping[str, Any]) -> FactCheckInteropRecord:
    """Adapt one already-validated public dossier without granting publication authority.

    This is a pure interoperability transform. It deliberately rechecks the public
    publication/review invariants because callers may accidentally pass an operational
    dossier rather than the validated public projection.
    """
    if not isinstance(dossier, Mapping):
        raise ClaimReviewInteropError("DOSSIER_REQUIRED")
    _assert_no_private_fields(dossier)
    finding, assessment = _assert_reviewed_public_input(dossier)
    _sidecars_are_public(dossier)

    finding_id = _required_text(dossier.get("finding_id"), "finding_id", limit=512)
    claim_id = _required_text(dossier.get("claim_id"), "claim_id", limit=512)
    claim = _required_text(dossier.get("claim"), "claim", limit=MAX_TEXT_CHARS)
    policy_version = _required_text(finding.get("policy_version"), "policy_version", limit=256)
    verification_run_id = _required_text(
        finding.get("verification_run_id"), "verification_run_id", limit=512
    )
    published_at = _required_text(finding.get("published_at"), "published_at", limit=128)
    supersedes_id = _optional_text(finding.get("supersedes_id"), limit=512)

    source = dossier.get("source")
    if not isinstance(source, Mapping):
        raise ClaimReviewInteropError("SOURCE_REQUIRED")
    source_url = _public_http_url(source.get("url"), "source_url")
    source_title = _optional_text(source.get("title"), limit=1024)
    source_published_at = _optional_text(source.get("published_at"), limit=128)

    speaker = dossier.get("speaker")
    if not isinstance(speaker, Mapping):
        raise ClaimReviewInteropError("SPEAKER_REQUIRED")
    provenance = speaker.get("provenance")
    if (
        not isinstance(provenance, Sequence)
        or isinstance(provenance, (str, bytes, bytearray))
        or not provenance
    ):
        raise ClaimReviewInteropError("SPEAKER_REVIEW_REQUIRED")
    speaker_id = _required_text(speaker.get("id"), "speaker_id", limit=512)
    speaker_name = _optional_text(speaker.get("name"), limit=1024) or speaker_id

    evidence = dossier.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes, bytearray)):
        raise ClaimReviewInteropError("EVIDENCE_INVALID")
    citations = [
        _citation(row)
        for row in evidence[:MAX_CITATIONS]
        if isinstance(row, Mapping)
    ]
    if len(citations) != min(len(evidence), MAX_CITATIONS):
        raise ClaimReviewInteropError("EVIDENCE_ENTRY_INVALID")

    reviewed_claim: dict[str, Any] = {
        "@type": "Claim",
        "identifier": claim_id,
        "text": claim,
        "author": {
            "@type": "Person",
            "identifier": speaker_id,
            "name": speaker_name,
        },
        "appearance": {
            "@type": "CreativeWork",
            "url": source_url,
        },
    }
    if source_title:
        reviewed_claim["appearance"]["name"] = source_title
    if source_published_at:
        reviewed_claim["appearance"]["datePublished"] = source_published_at

    additional = [
        {"@type": "PropertyValue", "name": "findingId", "value": finding_id},
        {"@type": "PropertyValue", "name": "claimId", "value": claim_id},
        {"@type": "PropertyValue", "name": "assessment", "value": assessment},
        {
            "@type": "PropertyValue",
            "name": "assessmentVocabularyVersion",
            "value": VERIFICATION_ASSESSMENT_VERSION,
        },
        {
            "@type": "PropertyValue",
            "name": "publicationStatus",
            "value": FindingPublicationStatus.PUBLISH.value,
        },
        {
            "@type": "PropertyValue",
            "name": "publicationStatusVocabularyVersion",
            "value": FINDING_PUBLICATION_STATUS_VERSION,
        },
        {"@type": "PropertyValue", "name": "policyVersion", "value": policy_version},
        {
            "@type": "PropertyValue",
            "name": "verificationRunId",
            "value": verification_run_id,
        },
        {
            "@type": "PropertyValue",
            "name": "interopVersion",
            "value": CLAIMREVIEW_INTEROP_VERSION,
        },
    ]
    if supersedes_id:
        additional.append(
            {
                "@type": "PropertyValue",
                "name": "supersedesFindingId",
                "value": supersedes_id,
            }
        )

    claimreview: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "identifier": finding_id,
        "claimReviewed": claim,
        "itemReviewed": reviewed_claim,
        "author": {"@type": "Organization", "name": "Dichiarazioni Pubbliche"},
        "datePublished": published_at,
        # Claim-level textual vocabulary only. No numeric rating or person score.
        "reviewRating": {"@type": "Rating", "alternateName": assessment},
        "citation": citations,
        "additionalProperty": additional,
    }
    output_keys = _walk_keys(claimreview)
    if output_keys & _FORBIDDEN_RATING_KEYS:
        raise ClaimReviewInteropError("NUMERIC_RATING_FIELD_FORBIDDEN")

    return FactCheckInteropRecord(
        finding_id=finding_id,
        claim_id=claim_id,
        assessment=assessment,
        assessment_version=VERIFICATION_ASSESSMENT_VERSION,
        publication_status=FindingPublicationStatus.PUBLISH.value,
        publication_status_version=FINDING_PUBLICATION_STATUS_VERSION,
        policy_version=policy_version,
        verification_run_id=verification_run_id,
        published_at=published_at,
        supersedes_id=supersedes_id,
        claimreview=copy.deepcopy(claimreview),
    )


__all__ = [
    "CLAIMREVIEW_INTEROP_VERSION",
    "ClaimReviewInteropError",
    "FactCheckInteropRecord",
    "build_claimreview_interop",
]

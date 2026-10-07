from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.domain_vocabulary import (
    ClaimType,
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.public_internal_guard import forbidden_public_internal_paths

PUBLIC_SCHEMA_VERSION = "dichiarazioni-pubbliche-public-v2"

PUBLIC_FINDING_STATUSES = frozenset(
    {
        FindingPublicationStatus.PUBLISH,
        FindingPublicationStatus.DISPUTED,
        FindingPublicationStatus.CORRECTED,
        FindingPublicationStatus.RETRACTED,
    }
)

PUBLISHABLE_ASSESSMENTS = frozenset(
    {
        VerificationAssessment.SUPPORTED,
        VerificationAssessment.FACTUALLY_FALSE,
        VerificationAssessment.OUTDATED_DATA,
    }
)

DOSSIER_REQUIRED_KEYS = frozenset(
    {
        "finding_id",
        "claim_id",
        "claim_type",
        "claim_contract",
        "speaker",
        "source",
        "finding",
        "evidence",
        "corrections",
        "rights_of_reply",
    }
)

DOSSIER_ALLOWED_KEYS = frozenset(
    {
        "finding_id",
        "claim_id",
        "claim",
        "claim_type",
        "claim_contract",
        "speaker",
        "source",
        "finding",
        "evidence",
        "corrections",
        "rights_of_reply",
        "relations",
        "source_methodology",
        "wording",
        "existing_factchecks",
    }
)

EXISTING_FACTCHECK_PUBLIC_KEYS = frozenset(
    {
        "lineage_id",
        "version_id",
        "source_version",
        "version_state",
        "provider_id",
        "review_url",
        "review_publisher_name",
        "review_publisher_site",
        "review_date",
        "persistence_version",
    }
)

SPEAKER_PROVENANCE_PUBLIC_KEYS = frozenset(
    {"candidate_id", "review_event_ids", "provenance_kind", "attribution_method"}
)
TIMED_SPEAKER_PUBLIC_ATTRIBUTION_METHODS = frozenset(
    {"MANUAL_REVIEW", "TRANSCRIPT_LABEL", "OFFICIAL_RECORD"}
)
TEXT_PUBLIC_ATTRIBUTION_METHODS = frozenset(
    {"SOURCE_BYLINE", "SOURCE_QUOTE", "ACCOUNT_OWNER", "OFFICIAL_RECORD", "MANUAL_REVIEW"}
)

PUBLIC_SOURCE_WORDING_TYPES = frozenset({"VERBATIM_ORIGINAL", "REPORTED_QUOTE"})
PUBLIC_DERIVED_WORDING_TYPES = frozenset({"PARAPHRASE", "SUMMARY", "TRANSLATION"})
PUBLIC_TRANSLATION_REVIEW_STATES = frozenset(
    {"NEEDS_REVIEW", "HUMAN_REVIEWED", "REJECTED"}
)
PUBLIC_WORDING_SOURCE_ROLE = "SOURCE_OCCURRENCE"
PUBLIC_WORDING_DERIVED_ROLE = "DERIVED_REPRESENTATION"

WORDING_REQUIRED_KEYS = frozenset(
    {"version", "source_occurrence", "normalized_claim", "representations", "public_provenance"}
)
WORDING_ALLOWED_KEYS = WORDING_REQUIRED_KEYS | {"source_span_disclosure"}
WORDING_SOURCE_REQUIRED_KEYS = frozenset(
    {
        "occurrence_id",
        "wording_type",
        "text_sha256",
        "language",
        "direct_quote_eligible",
        "representation_role",
    }
)
WORDING_SOURCE_ALLOWED_KEYS = WORDING_SOURCE_REQUIRED_KEYS
WORDING_NORMALIZED_REQUIRED_KEYS = frozenset(
    {
        "wording_type",
        "text_sha256",
        "source_occurrence_id",
        "source_wording_type",
        "language",
        "derivation_method",
        "derivation_version",
        "direct_quote_eligible",
        "representation_role",
    }
)
WORDING_NORMALIZED_ALLOWED_KEYS = WORDING_NORMALIZED_REQUIRED_KEYS
WORDING_REPRESENTATION_REQUIRED_KEYS = frozenset(
    {
        "wording_type",
        "text_sha256",
        "source_occurrence_id",
        "source_wording_type",
        "language",
        "source_language",
        "derivation_method",
        "derivation_version",
        "review_state",
        "signal_codes",
        "direct_quote_eligible",
        "representation_role",
    }
)
WORDING_REPRESENTATION_ALLOWED_KEYS = WORDING_REPRESENTATION_REQUIRED_KEYS
WORDING_PROVENANCE_REQUIRED_KEYS = frozenset(
    {"segment_ids", "text_provenance_ids"}
)
WORDING_PROVENANCE_ALLOWED_KEYS = WORDING_PROVENANCE_REQUIRED_KEYS
WORDING_SPAN_DISCLOSURE_REQUIRED_KEYS = frozenset(
    {"version", "source_sha256", "binding_sha256", "omission_count", "omission_marker", "spans"}
)
WORDING_SPAN_DISCLOSURE_ALLOWED_KEYS = WORDING_SPAN_DISCLOSURE_REQUIRED_KEYS
WORDING_SPAN_REQUIRED_KEYS = frozenset({"start_char", "end_char", "text_sha256"})

PROJECTION_BUNDLE_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "generated_at",
        "dataset_sha256",
        "methodology",
        "dossier_count",
        "omitted_count",
        "dossiers",
    }
)

PROJECTION_BUNDLE_ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "generated_at",
        "dataset_sha256",
        "methodology",
        "dossier_count",
        "omitted_count",
        "dossiers",
        "topics",
        "contents",
    }
)

TOPIC_REQUIRED_KEYS = frozenset(
    {
        "topic_id",
        "slug",
        "canonical_name",
        "scope_text",
        "entity_version",
        "review_event_ids",
        "memberships",
    }
)

TOPIC_ALLOWED_KEYS = TOPIC_REQUIRED_KEYS

TOPIC_MEMBERSHIP_REQUIRED_KEYS = frozenset(
    {
        "membership_id",
        "claim_id",
        "finding_ids",
        "review_event_ids",
        "source_resolution_candidate_id",
    }
)

TOPIC_MEMBERSHIP_ALLOWED_KEYS = TOPIC_MEMBERSHIP_REQUIRED_KEYS

CONTENT_REQUIRED_KEYS = frozenset(
    {
        "content_id",
        "slug",
        "url",
        "title",
        "published_at",
        "content_kind",
        "duration_ms",
        "public_media_url",
        "media_policy_version",
        "publication_version",
        "review_event_ids",
        "finding_ids",
    }
)

CONTENT_ALLOWED_KEYS = CONTENT_REQUIRED_KEYS
CONTENT_KINDS = frozenset({"VIDEO", "AUDIO", "WRITTEN", "OTHER"})


def projection_dataset_sha256(bundle: dict[str, Any]) -> str:
    """Return the canonical dataset fingerprint for the collections present.

    Older public-v2 bundles can omit newer additive collections. Their historical
    fingerprint remains defined over the collections that actually exist in that
    bundle; DP-434 bundles include ``contents`` and therefore bind it into the hash.
    """
    material: dict[str, Any] = {"dossiers": bundle.get("dossiers", [])}
    if "topics" in bundle:
        material["topics"] = bundle.get("topics", [])
    if "contents" in bundle:
        material["contents"] = bundle.get("contents", [])
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()

FORBIDDEN_KEY_SUBSTRINGS = (
    "ratingvalue",
    "bestrating",
    "worstrating",
    "reviewrating",
    "numericrating",
    "ratingexplanation",
    "reliability_score",
    "person_score",
    "aggregate_score",
    "political_score",
    "truth_score",
    "trust_score",
    "credibility_score",
    "person_aggregate",
    "aggregate_person_score",
    "speaker_score",
    "speaker_ranking",
    "person_ranking",
    "political_ranking",
    "political_recommendation",
)

FORBIDDEN_EXACT_KEY_NAMES = frozenset(
    {
        "score",
        "scores",
        "rank",
        "ranks",
        "ranking",
        "rankings",
        "rating",
        "ratings",
        "ratingvalue",
        "bestrating",
        "worstrating",
        "reviewrating",
        "numericrating",
        "leaderboard",
        "person_score",
        "person_aggregate",
        "reliability_score",
    }
)

PRIVATE_IDENTITY_KEY_NAMES = frozenset(
    {
        "public_attribution_input",
        "publicattributioninput",
        "retrieval_score",
        "retrievalscore",
        "supporting_features",
        "supportingfeatures",
        "contradicting_features",
        "contradictingfeatures",
        "speaker_label",
        "speakerlabel",
        "identifier_value",
        "identifiervalue",
        "mention_text",
        "mentiontext",
        "resolution_method",
        "resolutionmethod",
        "resolution_version",
        "resolutionversion",
        "confidence",
        "alias",
        "aliases",
    }
)

FORBIDDEN_JSON_KEY_PATTERN = re.compile(
    r'"(?:ratingValue|bestRating|worstRating|ratingExplanation|reviewRating|numericRating|'
    r'reliability_score|person_score|aggregate_score|political_score|truth_score|trust_score|'
    r'credibility_score|person_aggregate|aggregate_person_score|speaker_score|speaker_ranking|'
    r'person_ranking|political_ranking|leaderboard|score|rank|ranking)"\s*:',
    re.IGNORECASE,
)


class PublicSchemaValidationError(ValueError):
    """Raised when a public dossier or projection bundle violates the public contract."""

    pass


def _scan_forbidden_tokens(data: Any, path: str = "") -> None:
    if isinstance(data, dict):
        for raw_k, v in data.items():
            k_str = str(raw_k)
            k_norm = k_str.lower().replace("-", "_")
            k_clean = k_norm.replace("_", "")
            current_path = f"{path}.{k_str}" if path else k_str

            if k_norm in PRIVATE_IDENTITY_KEY_NAMES or k_clean in PRIVATE_IDENTITY_KEY_NAMES:
                raise PublicSchemaValidationError(
                    f"Private identity-resolution field '{current_path}' is forbidden in public schema"
                )
            if (
                k_norm in FORBIDDEN_EXACT_KEY_NAMES
                or k_clean in FORBIDDEN_EXACT_KEY_NAMES
            ):
                raise PublicSchemaValidationError(
                    f"Forbidden rating or scoring field '{current_path}' in public schema"
                )
            for sub in FORBIDDEN_KEY_SUBSTRINGS:
                if sub in k_norm or sub in k_clean:
                    raise PublicSchemaValidationError(
                        f"Forbidden rating or scoring field '{current_path}' (matched '{sub}') in public schema"
                    )
            _scan_forbidden_tokens(v, current_path)
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            _scan_forbidden_tokens(item, f"{path}[{idx}]")


def _validate_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise PublicSchemaValidationError(f"{field} must be a lowercase sha256")
    return value


def _validate_exact_keys(
    value: object,
    *,
    field: str,
    required: frozenset[str],
    allowed: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicSchemaValidationError(f"{field} must be a dictionary")
    unknown = set(value) - allowed
    if unknown:
        raise PublicSchemaValidationError(
            f"unknown {field} key(s): {', '.join(sorted(unknown))}"
        )
    missing = [key for key in required if key not in value]
    if missing:
        raise PublicSchemaValidationError(
            f"missing {field} key(s): {', '.join(sorted(missing))}"
        )
    return value


def _validate_public_wording(
    wording: object,
    *,
    claim_text: str | None,
    source: dict[str, Any],
) -> None:
    contract = _validate_exact_keys(
        wording,
        field="wording",
        required=WORDING_REQUIRED_KEYS,
        allowed=WORDING_ALLOWED_KEYS,
    )
    if contract["version"] != "wording-contract-v1":
        raise PublicSchemaValidationError("wording.version is unsupported")

    source_occurrence = _validate_exact_keys(
        contract["source_occurrence"],
        field="wording.source_occurrence",
        required=WORDING_SOURCE_REQUIRED_KEYS,
        allowed=WORDING_SOURCE_ALLOWED_KEYS,
    )
    occurrence_id = source_occurrence["occurrence_id"]
    if not isinstance(occurrence_id, str) or not occurrence_id.strip():
        raise PublicSchemaValidationError(
            "wording.source_occurrence.occurrence_id must be non-empty"
        )
    source_type = source_occurrence["wording_type"]
    if source_type not in PUBLIC_SOURCE_WORDING_TYPES:
        raise PublicSchemaValidationError(
            "wording.source_occurrence.wording_type is not canonical"
        )
    _validate_sha256(
        source_occurrence["text_sha256"],
        field="wording.source_occurrence.text_sha256",
    )
    source_language = source_occurrence["language"]
    if source_language is not None and (
        not isinstance(source_language, str) or not source_language.strip()
    ):
        raise PublicSchemaValidationError(
            "wording.source_occurrence.language must be a string or None"
        )
    expected_direct = source_type == "VERBATIM_ORIGINAL"
    if source_occurrence["direct_quote_eligible"] is not expected_direct:
        raise PublicSchemaValidationError(
            "wording.source_occurrence direct-quote authority is inconsistent"
        )
    if source_occurrence["representation_role"] != PUBLIC_WORDING_SOURCE_ROLE:
        raise PublicSchemaValidationError(
            "wording.source_occurrence representation_role is invalid"
        )

    normalized = _validate_exact_keys(
        contract["normalized_claim"],
        field="wording.normalized_claim",
        required=WORDING_NORMALIZED_REQUIRED_KEYS,
        allowed=WORDING_NORMALIZED_ALLOWED_KEYS,
    )
    if normalized["wording_type"] != "PARAPHRASE":
        raise PublicSchemaValidationError(
            "wording.normalized_claim must be PARAPHRASE"
        )
    normalized_hash = _validate_sha256(
        normalized["text_sha256"],
        field="wording.normalized_claim.text_sha256",
    )
    if claim_text is None:
        raise PublicSchemaValidationError(
            "wording metadata requires a public normalized claim"
        )
    if hashlib.sha256(claim_text.encode("utf-8")).hexdigest() != normalized_hash:
        raise PublicSchemaValidationError(
            "wording.normalized_claim hash does not match claim"
        )
    if normalized["source_occurrence_id"] != occurrence_id:
        raise PublicSchemaValidationError(
            "wording.normalized_claim source occurrence mismatch"
        )
    if normalized["source_wording_type"] != source_type:
        raise PublicSchemaValidationError(
            "wording.normalized_claim source wording type mismatch"
        )
    if normalized["direct_quote_eligible"] is not False:
        raise PublicSchemaValidationError(
            "wording.normalized_claim cannot be direct-quote eligible"
        )
    if normalized["representation_role"] != PUBLIC_WORDING_DERIVED_ROLE:
        raise PublicSchemaValidationError(
            "wording.normalized_claim representation_role is invalid"
        )
    for key in ("derivation_method", "derivation_version"):
        if not isinstance(normalized[key], str) or not normalized[key].strip():
            raise PublicSchemaValidationError(
                f"wording.normalized_claim.{key} must be non-empty"
            )

    representations = contract["representations"]
    if not isinstance(representations, list) or len(representations) > 16:
        raise PublicSchemaValidationError(
            "wording.representations must be a bounded list"
        )
    for index, representation_raw in enumerate(representations):
        representation = _validate_exact_keys(
            representation_raw,
            field=f"wording.representations[{index}]",
            required=WORDING_REPRESENTATION_REQUIRED_KEYS,
            allowed=WORDING_REPRESENTATION_ALLOWED_KEYS,
        )
        wording_type = representation["wording_type"]
        if wording_type not in PUBLIC_DERIVED_WORDING_TYPES:
            raise PublicSchemaValidationError(
                "wording representation type is not canonical"
            )
        _validate_sha256(
            representation["text_sha256"],
            field=f"wording.representations[{index}].text_sha256",
        )
        if representation["source_occurrence_id"] != occurrence_id:
            raise PublicSchemaValidationError(
                "wording representation source occurrence mismatch"
            )
        if representation["source_wording_type"] != source_type:
            raise PublicSchemaValidationError(
                "wording representation source type mismatch"
            )
        if representation["direct_quote_eligible"] is not False:
            raise PublicSchemaValidationError(
                "derived wording cannot be direct-quote eligible"
            )
        if representation["representation_role"] != PUBLIC_WORDING_DERIVED_ROLE:
            raise PublicSchemaValidationError(
                "wording representation role is invalid"
            )
        for key in ("derivation_method", "derivation_version"):
            if not isinstance(representation[key], str) or not representation[key].strip():
                raise PublicSchemaValidationError(
                    f"wording representation {key} must be non-empty"
                )
        signal_codes = representation["signal_codes"]
        if (
            not isinstance(signal_codes, list)
            or len(signal_codes) > 32
            or not all(isinstance(code, str) and code.strip() for code in signal_codes)
        ):
            raise PublicSchemaValidationError(
                "wording representation signal_codes are invalid"
            )
        if wording_type == "TRANSLATION":
            if representation["source_language"] != source_language:
                raise PublicSchemaValidationError(
                    "translation source language does not match source occurrence"
                )
            if not isinstance(representation["language"], str) or not representation[
                "language"
            ].strip():
                raise PublicSchemaValidationError(
                    "translation target language is required"
                )
            if representation["review_state"] not in PUBLIC_TRANSLATION_REVIEW_STATES:
                raise PublicSchemaValidationError(
                    "translation review_state is not canonical"
                )

    provenance = _validate_exact_keys(
        contract["public_provenance"],
        field="wording.public_provenance",
        required=WORDING_PROVENANCE_REQUIRED_KEYS,
        allowed=WORDING_PROVENANCE_ALLOWED_KEYS,
    )
    segment_ids = provenance["segment_ids"]
    text_ids = provenance["text_provenance_ids"]
    if not isinstance(segment_ids, list) or not isinstance(text_ids, list):
        raise PublicSchemaValidationError(
            "wording.public_provenance channels must be lists"
        )
    if len(segment_ids) > 64 or len(text_ids) > 64:
        raise PublicSchemaValidationError(
            "wording.public_provenance channels are unbounded"
        )
    if not all(isinstance(item, str) and item.strip() for item in segment_ids + text_ids):
        raise PublicSchemaValidationError(
            "wording.public_provenance contains invalid ids"
        )
    public_segment_ids = {
        str(item.get("segment_id")) for item in source.get("segments", [])
    }
    public_text_ids = {
        str(item.get("id")) for item in source.get("text_provenance", [])
    }
    if set(segment_ids) != public_segment_ids or set(text_ids) != public_text_ids:
        raise PublicSchemaValidationError(
            "wording.public_provenance does not match public source provenance"
        )
    if text_ids:
        public_quote_hashes = {
            str(item.get("quote_sha256") or "")
            for item in source.get("text_provenance", [])
        }
        if source_occurrence["text_sha256"] not in public_quote_hashes:
            raise PublicSchemaValidationError(
                "wording source hash does not match public text provenance"
            )

    disclosure_raw = contract.get("source_span_disclosure")
    if disclosure_raw is not None:
        disclosure = _validate_exact_keys(
            disclosure_raw,
            field="wording.source_span_disclosure",
            required=WORDING_SPAN_DISCLOSURE_REQUIRED_KEYS,
            allowed=WORDING_SPAN_DISCLOSURE_ALLOWED_KEYS,
        )
        if disclosure["version"] != "discontinuous-quote-binding-v1":
            raise PublicSchemaValidationError("source span disclosure version is unsupported")
        _validate_sha256(disclosure["source_sha256"], field="source_span_disclosure.source_sha256")
        _validate_sha256(disclosure["binding_sha256"], field="source_span_disclosure.binding_sha256")
        if disclosure["omission_marker"] != " […] ":
            raise PublicSchemaValidationError("source span disclosure omission marker is not canonical")
        spans = disclosure["spans"]
        if not isinstance(spans, list) or not 2 <= len(spans) <= 32:
            raise PublicSchemaValidationError("source span disclosure spans are invalid")
        if disclosure["omission_count"] != len(spans) - 1:
            raise PublicSchemaValidationError("source span disclosure omission count is invalid")
        previous_end: int | None = None
        for index, raw_span in enumerate(spans):
            span = _validate_exact_keys(
                raw_span,
                field=f"wording.source_span_disclosure.spans[{index}]",
                required=WORDING_SPAN_REQUIRED_KEYS,
                allowed=WORDING_SPAN_REQUIRED_KEYS,
            )
            start = span["start_char"]
            end = span["end_char"]
            if (
                not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or start < 0
                or end <= start
                or (previous_end is not None and start <= previous_end)
            ):
                raise PublicSchemaValidationError("source span disclosure span order is invalid")
            _validate_sha256(span["text_sha256"], field="source_span_disclosure.spans.text_sha256")
            previous_end = end


def validate_dossier(dossier: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(dossier, dict):
        raise PublicSchemaValidationError("dossier must be a dictionary")

    unknown_keys = set(dossier.keys()) - DOSSIER_ALLOWED_KEYS
    if unknown_keys:
        raise PublicSchemaValidationError(
            f"unknown top-level key(s) in dossier: {', '.join(sorted(unknown_keys))}"
        )

    missing_keys = [
        k
        for k in DOSSIER_REQUIRED_KEYS
        if k not in dossier or dossier[k] is None
    ]
    if missing_keys:
        raise PublicSchemaValidationError(
            f"missing required key(s) in dossier: {', '.join(sorted(missing_keys))}"
        )

    if not str(dossier["finding_id"]).strip():
        raise PublicSchemaValidationError("finding_id must not be empty")
    if not str(dossier["claim_id"]).strip():
        raise PublicSchemaValidationError("claim_id must not be empty")

    if (
        "claim" in dossier
        and dossier["claim"] is not None
        and not isinstance(dossier["claim"], str)
    ):
        raise PublicSchemaValidationError("claim must be a string or None")

    private_paths = forbidden_public_internal_paths(dossier)
    if private_paths:
        raise PublicSchemaValidationError(
            "dossier contains internal-only material: " + ", ".join(private_paths[:8])
        )

    # Forbidden fields / scoring / person aggregates
    _scan_forbidden_tokens(dossier)
    try:
        serialized = json.dumps(dossier, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise PublicSchemaValidationError(
            f"dossier cannot be serialized to JSON: {exc}"
        ) from exc

    if FORBIDDEN_JSON_KEY_PATTERN.search(serialized):
        raise PublicSchemaValidationError(
            "dossier contains forbidden rating, score, or person aggregate key in serialized JSON"
        )
    for token in (
        '"ratingvalue"',
        '"bestrating"',
        '"worstrating"',
        '"reliability_score"',
        '"person_score"',
        '"person_aggregate"',
    ):
        if token in serialized.lower():
            raise PublicSchemaValidationError(
                f"dossier contains forbidden token {token} in serialized JSON"
            )

    # Claim type canonical check
    claim_type_raw = dossier.get("claim_type")
    try:
        ClaimType(str(claim_type_raw))
    except ValueError as exc:
        raise PublicSchemaValidationError(
            f"unknown or non-canonical claim_type: '{claim_type_raw}'"
        ) from exc

    # Finding assessment & status check
    finding = dossier.get("finding")
    if not isinstance(finding, dict):
        raise PublicSchemaValidationError("finding must be a dictionary")

    assessment_raw = finding.get("assessment")
    try:
        assessment = VerificationAssessment(str(assessment_raw))
    except ValueError as exc:
        raise PublicSchemaValidationError(
            f"unknown assessment: '{assessment_raw}'"
        ) from exc
    if assessment not in PUBLISHABLE_ASSESSMENTS:
        raise PublicSchemaValidationError(
            f"non-publishable assessment: '{assessment_raw}'"
        )

    status_raw = finding.get("publication_status")
    try:
        publication_status = FindingPublicationStatus(str(status_raw))
    except ValueError as exc:
        raise PublicSchemaValidationError(
            f"unknown publication_status: '{status_raw}'"
        ) from exc
    if publication_status not in PUBLIC_FINDING_STATUSES:
        raise PublicSchemaValidationError(
            f"non-public finding publication_status: '{status_raw}'"
        )

    # Sub-structure validations
    if not isinstance(dossier["claim_contract"], dict):
        raise PublicSchemaValidationError("claim_contract must be a dictionary")
    if not isinstance(dossier["speaker"], dict):
        raise PublicSchemaValidationError("speaker must be a dictionary")
    if not str(dossier["speaker"].get("id") or "").strip():
        raise PublicSchemaValidationError("speaker.id must not be empty")
    if (
        not isinstance(dossier["speaker"].get("provenance"), list)
        or not dossier["speaker"]["provenance"]
    ):
        raise PublicSchemaValidationError(
            "speaker.provenance must be a non-empty list"
        )
    for provenance in dossier["speaker"]["provenance"]:
        if not isinstance(provenance, dict):
            raise PublicSchemaValidationError("speaker provenance must be an object")
        unknown_provenance_keys = set(provenance) - SPEAKER_PROVENANCE_PUBLIC_KEYS
        if unknown_provenance_keys:
            raise PublicSchemaValidationError(
                "unknown speaker provenance key(s): "
                + ", ".join(sorted(unknown_provenance_keys))
            )
        if not str(provenance.get("candidate_id") or "").strip():
            raise PublicSchemaValidationError("speaker provenance candidate_id is required")
        review_ids = provenance.get("review_event_ids")
        if (
            not isinstance(review_ids, list)
            or not review_ids
            or not all(isinstance(item, str) and item.strip() for item in review_ids)
        ):
            raise PublicSchemaValidationError(
                "speaker provenance review_event_ids must be non-empty strings"
            )
        provenance_kind = str(provenance.get("provenance_kind") or "")
        if provenance_kind and provenance_kind not in {"TIMED_SPEAKER", "TEXT_ATTRIBUTION"}:
            raise PublicSchemaValidationError("speaker provenance kind is invalid")
        attribution_method = provenance.get("attribution_method")
        if attribution_method is not None:
            if not provenance_kind:
                raise PublicSchemaValidationError(
                    "speaker provenance attribution_method requires provenance_kind"
                )
            method = str(attribution_method)
            allowed_methods = (
                TIMED_SPEAKER_PUBLIC_ATTRIBUTION_METHODS
                if provenance_kind == "TIMED_SPEAKER"
                else TEXT_PUBLIC_ATTRIBUTION_METHODS
            )
            if method not in allowed_methods:
                raise PublicSchemaValidationError(
                    "speaker provenance attribution_method is not publication-safe"
                )
    if not isinstance(dossier["speaker"].get("public_roles"), list):
        raise PublicSchemaValidationError("speaker.public_roles must be a list")

    if not isinstance(dossier["source"], dict):
        raise PublicSchemaValidationError("source must be a dictionary")
    segments = dossier["source"].get("segments")
    text_provenance = dossier["source"].get("text_provenance", [])
    if not isinstance(segments, list) or not isinstance(text_provenance, list):
        raise PublicSchemaValidationError(
            "source provenance channels must be lists"
        )
    if not segments and not text_provenance:
        raise PublicSchemaValidationError(
            "source requires segments or text_provenance"
        )
    wording = dossier.get("wording")
    if wording is not None:
        _validate_public_wording(
            wording,
            claim_text=dossier.get("claim"),
            source=dossier["source"],
        )

    if not isinstance(dossier["evidence"], list) or not dossier["evidence"]:
        raise PublicSchemaValidationError("evidence must be a non-empty list")
    if not isinstance(dossier["corrections"], list):
        raise PublicSchemaValidationError("corrections must be a list")
    if not isinstance(dossier["rights_of_reply"], list):
        raise PublicSchemaValidationError("rights_of_reply must be a list")

    existing_factchecks = dossier.get("existing_factchecks", [])
    if not isinstance(existing_factchecks, list) or len(existing_factchecks) > 64:
        raise PublicSchemaValidationError("existing_factchecks must be a bounded list")
    seen_factcheck_links: set[tuple[str, str, str]] = set()
    for item in existing_factchecks:
        if not isinstance(item, dict):
            raise PublicSchemaValidationError("existing fact-check metadata must be an object")
        unknown_factcheck_keys = set(item) - EXISTING_FACTCHECK_PUBLIC_KEYS
        if unknown_factcheck_keys:
            raise PublicSchemaValidationError(
                "unknown existing fact-check key(s): "
                + ", ".join(sorted(unknown_factcheck_keys))
            )
        required_factcheck_keys = {
            "lineage_id",
            "version_id",
            "source_version",
            "version_state",
            "provider_id",
            "review_url",
            "persistence_version",
        }
        missing_factcheck_keys = [
            key for key in required_factcheck_keys if not str(item.get(key) or "").strip()
        ]
        if missing_factcheck_keys:
            raise PublicSchemaValidationError(
                "missing existing fact-check key(s): "
                + ", ".join(sorted(missing_factcheck_keys))
            )
        if item["version_state"] not in {"CURRENT", "HISTORICAL"}:
            raise PublicSchemaValidationError("existing fact-check version_state is invalid")
        try:
            _validate_public_url(item["review_url"], field="existing_factchecks.review_url")
        except ValueError as exc:
            raise PublicSchemaValidationError("existing fact-check review_url is invalid") from exc
        if item["persistence_version"] != "existing-factcheck-mirror-v1":
            raise PublicSchemaValidationError(
                "existing fact-check persistence_version is not canonical"
            )
        identity = (
            str(item["lineage_id"]),
            str(item["version_id"]),
            str(item["review_url"]),
        )
        if identity in seen_factcheck_links:
            raise PublicSchemaValidationError("duplicate existing fact-check metadata")
        seen_factcheck_links.add(identity)

    return dossier


def validate_topic(topic: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(topic, dict):
        raise PublicSchemaValidationError("topic must be a dictionary")
    unknown = set(topic) - TOPIC_ALLOWED_KEYS
    if unknown:
        raise PublicSchemaValidationError(
            f"unknown topic key(s): {', '.join(sorted(unknown))}"
        )
    missing = [
        key
        for key in TOPIC_REQUIRED_KEYS
        if key not in topic or (key != "scope_text" and topic[key] is None)
    ]
    if missing:
        raise PublicSchemaValidationError(
            f"missing topic key(s): {', '.join(sorted(missing))}"
        )
    for key in ("topic_id", "slug", "canonical_name", "entity_version"):
        if not isinstance(topic[key], str) or not topic[key].strip():
            raise PublicSchemaValidationError(f"topic.{key} must be a non-empty string")
    if topic["scope_text"] is not None and not isinstance(topic["scope_text"], str):
        raise PublicSchemaValidationError("topic.scope_text must be a string or None")
    if not isinstance(topic["review_event_ids"], list) or not topic["review_event_ids"]:
        raise PublicSchemaValidationError("topic.review_event_ids must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in topic["review_event_ids"]):
        raise PublicSchemaValidationError("topic.review_event_ids contains an invalid id")
    if not isinstance(topic["memberships"], list):
        raise PublicSchemaValidationError("topic.memberships must be a list")
    seen_memberships: set[str] = set()
    for membership in topic["memberships"]:
        if not isinstance(membership, dict):
            raise PublicSchemaValidationError("topic membership must be a dictionary")
        unknown_membership = set(membership) - TOPIC_MEMBERSHIP_ALLOWED_KEYS
        if unknown_membership:
            raise PublicSchemaValidationError(
                "unknown topic membership key(s): "
                + ", ".join(sorted(unknown_membership))
            )
        missing_membership = [
            key
            for key in TOPIC_MEMBERSHIP_REQUIRED_KEYS
            if key not in membership
        ]
        if missing_membership:
            raise PublicSchemaValidationError(
                "missing topic membership key(s): "
                + ", ".join(sorted(missing_membership))
            )
        membership_id = membership["membership_id"]
        claim_id = membership["claim_id"]
        if not isinstance(membership_id, str) or not membership_id.strip():
            raise PublicSchemaValidationError("topic membership id must be non-empty")
        if membership_id in seen_memberships:
            raise PublicSchemaValidationError("duplicate topic membership id")
        seen_memberships.add(membership_id)
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise PublicSchemaValidationError("topic membership claim_id must be non-empty")
        if not isinstance(membership["finding_ids"], list) or not membership["finding_ids"]:
            raise PublicSchemaValidationError("topic membership finding_ids must be non-empty")
        if not all(isinstance(item, str) and item.strip() for item in membership["finding_ids"]):
            raise PublicSchemaValidationError("topic membership finding_ids contains an invalid id")
        if not isinstance(membership["review_event_ids"], list) or not membership["review_event_ids"]:
            raise PublicSchemaValidationError("topic membership review_event_ids must be non-empty")
        if not all(isinstance(item, str) and item.strip() for item in membership["review_event_ids"]):
            raise PublicSchemaValidationError("topic membership review_event_ids contains an invalid id")
        source_resolution = membership["source_resolution_candidate_id"]
        if source_resolution is not None and (
            not isinstance(source_resolution, str) or not source_resolution.strip()
        ):
            raise PublicSchemaValidationError(
                "topic membership source_resolution_candidate_id must be a string or None"
            )
    _scan_forbidden_tokens(topic)
    return topic


def _validate_public_url(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicSchemaValidationError(f"{field} must be a non-empty URL string")
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise PublicSchemaValidationError(f"{field} must be a safe public http(s) URL")
    return value


def validate_content(content: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(content, dict):
        raise PublicSchemaValidationError("content must be a dictionary")
    unknown = set(content) - CONTENT_ALLOWED_KEYS
    if unknown:
        raise PublicSchemaValidationError(
            f"unknown content key(s): {', '.join(sorted(unknown))}"
        )
    missing = [
        key
        for key in CONTENT_REQUIRED_KEYS
        if key not in content
        or (
            key
            not in {
                "published_at",
                "duration_ms",
                "public_media_url",
                "media_policy_version",
            }
            and content[key] is None
        )
    ]
    if missing:
        raise PublicSchemaValidationError(
            f"missing content key(s): {', '.join(sorted(missing))}"
        )
    for key in ("content_id", "slug", "title", "publication_version"):
        if not isinstance(content[key], str) or not content[key].strip():
            raise PublicSchemaValidationError(f"content.{key} must be a non-empty string")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", content["slug"]):
        raise PublicSchemaValidationError("content.slug must be a canonical lowercase slug")
    _validate_public_url(content["url"], field="content.url")
    if content["published_at"] is not None and not isinstance(content["published_at"], str):
        raise PublicSchemaValidationError("content.published_at must be a string or None")
    if content["content_kind"] not in CONTENT_KINDS:
        raise PublicSchemaValidationError("content.content_kind is not canonical")
    if content["publication_version"] != "public-content-v1":
        raise PublicSchemaValidationError("content.publication_version is unsupported")
    duration = content["duration_ms"]
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, int) or duration < 0
    ):
        raise PublicSchemaValidationError("content.duration_ms must be a non-negative integer or None")
    if content["content_kind"] not in {"VIDEO", "AUDIO"} and duration is not None:
        raise PublicSchemaValidationError("non-timed content cannot publish duration_ms")
    media_url = content["public_media_url"]
    media_policy = content["media_policy_version"]
    if media_url is not None:
        _validate_public_url(media_url, field="content.public_media_url")
        if content["content_kind"] not in {"VIDEO", "AUDIO"}:
            raise PublicSchemaValidationError("public_media_url requires timed media content")
        if not isinstance(media_policy, str) or not media_policy.strip():
            raise PublicSchemaValidationError("public_media_url requires media_policy_version")
    elif media_policy is not None and (
        not isinstance(media_policy, str) or not media_policy.strip()
    ):
        raise PublicSchemaValidationError("content.media_policy_version must be a string or None")
    if not isinstance(content["review_event_ids"], list) or not content["review_event_ids"]:
        raise PublicSchemaValidationError("content.review_event_ids must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in content["review_event_ids"]):
        raise PublicSchemaValidationError("content.review_event_ids contains an invalid id")
    if not isinstance(content["finding_ids"], list):
        raise PublicSchemaValidationError("content.finding_ids must be a list")
    if len(content["finding_ids"]) != len(set(content["finding_ids"])):
        raise PublicSchemaValidationError("content.finding_ids must not contain duplicates")
    if not all(isinstance(item, str) and item.strip() for item in content["finding_ids"]):
        raise PublicSchemaValidationError("content.finding_ids contains an invalid id")
    _scan_forbidden_tokens(content)
    return content


def validate_public_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise PublicSchemaValidationError("bundle must be a dictionary")

    unknown = set(bundle.keys()) - PROJECTION_BUNDLE_ALLOWED_KEYS
    if unknown:
        raise PublicSchemaValidationError(
            f"unknown bundle key(s): {', '.join(sorted(unknown))}"
        )

    missing = [
        k
        for k in PROJECTION_BUNDLE_REQUIRED_KEYS
        if k not in bundle or bundle[k] is None
    ]
    if missing:
        raise PublicSchemaValidationError(
            f"missing required bundle key(s): {', '.join(sorted(missing))}"
        )

    if bundle["schema_version"] != PUBLIC_SCHEMA_VERSION:
        raise PublicSchemaValidationError(
            f"unexpected schema_version: '{bundle['schema_version']}' (expected '{PUBLIC_SCHEMA_VERSION}')"
        )

    if not isinstance(bundle["methodology"], dict):
        raise PublicSchemaValidationError(
            "bundle methodology must be a dictionary"
        )
    if bundle["methodology"].get("aggregate_person_score") is not False:
        raise PublicSchemaValidationError(
            "bundle methodology must disallow aggregate_person_score"
        )
    if bundle["methodology"].get("claim_level_only") is not True:
        raise PublicSchemaValidationError(
            "bundle methodology must specify claim_level_only = True"
        )

    if not isinstance(bundle["dossiers"], list):
        raise PublicSchemaValidationError("bundle dossiers must be a list")
    if bundle["dossier_count"] != len(bundle["dossiers"]):
        raise PublicSchemaValidationError(
            f"dossier_count mismatch: {bundle['dossier_count']} != {len(bundle['dossiers'])}"
        )

    for dossier in bundle["dossiers"]:
        validate_dossier(dossier)

    topics = bundle.get("topics", [])
    if not isinstance(topics, list):
        raise PublicSchemaValidationError("bundle topics must be a list")
    finding_to_claim = {
        str(dossier["finding_id"]): str(dossier["claim_id"])
        for dossier in bundle["dossiers"]
    }
    seen_topic_ids: set[str] = set()
    seen_topic_slugs: set[str] = set()
    for topic in topics:
        validate_topic(topic)
        if topic["topic_id"] in seen_topic_ids:
            raise PublicSchemaValidationError("duplicate public topic_id")
        if topic["slug"] in seen_topic_slugs:
            raise PublicSchemaValidationError("duplicate public topic slug")
        seen_topic_ids.add(topic["topic_id"])
        seen_topic_slugs.add(topic["slug"])
        for membership in topic["memberships"]:
            for finding_id in membership["finding_ids"]:
                claim_id = finding_to_claim.get(finding_id)
                if claim_id is None:
                    raise PublicSchemaValidationError(
                        "topic membership references a non-public finding"
                    )
                if claim_id != membership["claim_id"]:
                    raise PublicSchemaValidationError(
                        "topic membership finding/claim mismatch"
                    )

    contents = bundle.get("contents", [])
    if not isinstance(contents, list):
        raise PublicSchemaValidationError("bundle contents must be a list")
    public_findings = {
        str(dossier["finding_id"]): str(dossier["source"]["content_id"])
        for dossier in bundle["dossiers"]
    }
    seen_content_ids: set[str] = set()
    seen_content_slugs: set[str] = set()
    for content in contents:
        validate_content(content)
        if content["content_id"] in seen_content_ids:
            raise PublicSchemaValidationError("duplicate public content_id")
        if content["slug"] in seen_content_slugs:
            raise PublicSchemaValidationError("duplicate public content slug")
        seen_content_ids.add(content["content_id"])
        seen_content_slugs.add(content["slug"])
        for finding_id in content["finding_ids"]:
            owner = public_findings.get(finding_id)
            if owner is None:
                raise PublicSchemaValidationError(
                    "content references a non-public finding"
                )
            if owner != content["content_id"]:
                raise PublicSchemaValidationError(
                    "content finding belongs to a different source content_id"
                )

    if "contents" in bundle:
        expected_fingerprint = projection_dataset_sha256(bundle)
        if bundle["dataset_sha256"] != expected_fingerprint:
            raise PublicSchemaValidationError(
                "dataset_sha256 does not match dossiers/topics/contents"
            )

    return bundle


__all__ = [
    "DOSSIER_ALLOWED_KEYS",
    "DOSSIER_REQUIRED_KEYS",
    "PROJECTION_BUNDLE_ALLOWED_KEYS",
    "PROJECTION_BUNDLE_REQUIRED_KEYS",
    "PUBLIC_FINDING_STATUSES",
    "PUBLIC_SCHEMA_VERSION",
    "PUBLISHABLE_ASSESSMENTS",
    "CONTENT_ALLOWED_KEYS",
    "CONTENT_KINDS",
    "CONTENT_REQUIRED_KEYS",
    "TOPIC_ALLOWED_KEYS",
    "TOPIC_MEMBERSHIP_ALLOWED_KEYS",
    "TOPIC_MEMBERSHIP_REQUIRED_KEYS",
    "TOPIC_REQUIRED_KEYS",
    "PublicSchemaValidationError",
    "projection_dataset_sha256",
    "validate_dossier",
    "validate_content",
    "validate_public_bundle",
    "validate_topic",
]

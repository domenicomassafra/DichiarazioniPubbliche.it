from __future__ import annotations

import json
import re
from typing import Any

from dichiarazioni_pubbliche.domain_vocabulary import (
    ClaimType,
    FindingPublicationStatus,
    VerificationAssessment,
)

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
    }
)

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

    if not isinstance(dossier["evidence"], list) or not dossier["evidence"]:
        raise PublicSchemaValidationError("evidence must be a non-empty list")
    if not isinstance(dossier["corrections"], list):
        raise PublicSchemaValidationError("corrections must be a list")
    if not isinstance(dossier["rights_of_reply"], list):
        raise PublicSchemaValidationError("rights_of_reply must be a list")

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

    return bundle


__all__ = [
    "DOSSIER_ALLOWED_KEYS",
    "DOSSIER_REQUIRED_KEYS",
    "PROJECTION_BUNDLE_ALLOWED_KEYS",
    "PROJECTION_BUNDLE_REQUIRED_KEYS",
    "PUBLIC_FINDING_STATUSES",
    "PUBLIC_SCHEMA_VERSION",
    "PUBLISHABLE_ASSESSMENTS",
    "TOPIC_ALLOWED_KEYS",
    "TOPIC_MEMBERSHIP_ALLOWED_KEYS",
    "TOPIC_MEMBERSHIP_REQUIRED_KEYS",
    "TOPIC_REQUIRED_KEYS",
    "PublicSchemaValidationError",
    "validate_dossier",
    "validate_public_bundle",
    "validate_topic",
]

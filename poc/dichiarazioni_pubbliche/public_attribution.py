from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Sequence

from dichiarazioni_pubbliche.knowledge_repository import (
    ENTITY_IDENTIFIER_VERSION,
    ENTITY_RESOLUTION_VERSION,
    EntityIdentifierRecord,
    EntityResolutionCandidateRecord,
)
from dichiarazioni_pubbliche.speaker_runtime import (
    SpeakerIdentityCandidate,
    speaker_method_is_publication_capable,
)


PUBLIC_ATTRIBUTION_VERSION = "public-attribution-v1"


@dataclass(frozen=True)
class RoleInterval:
    interval_id: str
    person_id: str
    organization_id: str
    role: str
    start_date: date
    end_date: date | None
    status: str
    review_event_ids: tuple[str, ...]
    source_ref: Mapping[str, object]

    def covers(self, on_date: date) -> bool:
        return (
            self.status == "ACTIVE"
            and self.start_date <= on_date
            and (self.end_date is None or on_date < self.end_date)
            and bool(self.review_event_ids)
            and bool(self.source_ref)
        )


@dataclass(frozen=True)
class PublicAttributionDecision:
    decision: str
    person_id: str | None
    role_interval_id: str | None
    public_role: str | None
    organization_id: str | None
    attribution_scope: str
    reason_codes: tuple[str, ...]
    version: str = PUBLIC_ATTRIBUTION_VERSION

    @property
    def publication_allowed(self) -> bool:
        return self.decision == "ALLOW"


def _hold(*codes: str) -> PublicAttributionDecision:
    return PublicAttributionDecision(
        decision="HOLD",
        person_id=None,
        role_interval_id=None,
        public_role=None,
        organization_id=None,
        attribution_scope="NONE",
        reason_codes=tuple(codes),
    )


def _active_identifier_map(
    identifiers: Iterable[EntityIdentifierRecord],
) -> dict[str, EntityIdentifierRecord]:
    result: dict[str, EntityIdentifierRecord] = {}
    for row in identifiers:
        if row.identifier_version != ENTITY_IDENTIFIER_VERSION:
            continue
        result[row.id] = row
    return result


def _resolution_identifier_ids(
    resolution: EntityResolutionCandidateRecord,
) -> tuple[str, ...]:
    ids: list[str] = []
    for feature in resolution.supporting_features:
        if feature.get("code") != "IDENTIFIER_ID":
            continue
        value = feature.get("value")
        if isinstance(value, str) and value.strip():
            ids.append(value.strip())
    return tuple(sorted(set(ids)))


def _account_authorship_scope(
    *,
    person_id: str,
    content_id: str,
    occurrence_kind: str,
    speaker_candidate: SpeakerIdentityCandidate,
) -> PublicAttributionDecision | None:
    if speaker_candidate.attribution_method != "PLATFORM_CREDIT":
        return None
    source_ref = speaker_candidate.source_ref
    if occurrence_kind != "AUTHORSHIP":
        return _hold("ACCOUNT_CREDIT_NOT_SPEAKER_IDENTITY")
    if (
        source_ref.get("account_owner_person_id") != person_id
        or source_ref.get("account_content_id") != content_id
        or source_ref.get("authorship_scope") != "SOURCE_AUTHORSHIP"
    ):
        return _hold("ACCOUNT_AUTHORSHIP_SCOPE_UNPROVEN")
    return PublicAttributionDecision(
        decision="ALLOW",
        person_id=person_id,
        role_interval_id=None,
        public_role=None,
        organization_id=None,
        attribution_scope="AUTHORSHIP_ONLY",
        reason_codes=("APPROVED_ACCOUNT_AUTHORSHIP_SCOPE",),
    )


def evaluate_public_attribution(
    *,
    person_id: str,
    content_id: str,
    occurrence_start_ms: int,
    occurrence_end_ms: int,
    statement_date: date,
    speaker_candidate: SpeakerIdentityCandidate,
    resolution_candidates: Sequence[EntityResolutionCandidateRecord],
    identifiers: Sequence[EntityIdentifierRecord] = (),
    role_intervals: Sequence[RoleInterval] = (),
    requested_role_interval_id: str | None = None,
    occurrence_kind: str = "SPEAKER",
) -> PublicAttributionDecision:
    """Evaluate the final public Person binding without display-name authority.

    The gate consumes already reviewed identity artifacts. It never chooses the
    highest-scoring candidate and never derives identity from names, voice, face,
    ideology, or account ownership outside an explicit authorship-only scope.
    """
    if not person_id or not content_id:
        return _hold("PERSON_OR_CONTENT_ID_MISSING")
    if occurrence_start_ms < 0 or occurrence_end_ms < occurrence_start_ms:
        return _hold("OCCURRENCE_INTERVAL_INVALID")
    if speaker_candidate.content_id != content_id:
        return _hold("SPEAKER_CONTENT_MISMATCH")
    if speaker_candidate.person_id != person_id:
        return _hold("SPEAKER_PERSON_MISMATCH")
    if (
        speaker_candidate.start_ms > occurrence_start_ms
        or speaker_candidate.end_ms < occurrence_end_ms
    ):
        return _hold("SPEAKER_PROOF_DOES_NOT_COVER_OCCURRENCE")

    authorship = _account_authorship_scope(
        person_id=person_id,
        content_id=content_id,
        occurrence_kind=occurrence_kind,
        speaker_candidate=speaker_candidate,
    )
    if authorship is not None:
        return authorship

    if occurrence_kind != "SPEAKER":
        return _hold("UNSUPPORTED_ATTRIBUTION_SCOPE")
    if not speaker_method_is_publication_capable(
        speaker_candidate.attribution_method
    ):
        return _hold("SPEAKER_METHOD_NOT_PUBLICATION_CAPABLE")

    approved = [
        row
        for row in resolution_candidates
        if row.entity_type == "PERSON"
        and row.content_id == content_id
        and row.status == "APPROVED"
        and row.resolution_version == ENTITY_RESOLUTION_VERSION
    ]
    approved_targets = {row.target_id for row in approved}
    if len(approved_targets) != 1:
        return _hold(
            "IDENTITY_RESOLUTION_MISSING"
            if not approved_targets
            else "IDENTITY_RESOLUTION_AMBIGUOUS"
        )
    if approved_targets != {person_id}:
        return _hold("IDENTITY_RESOLUTION_PERSON_MISMATCH")

    matching = [row for row in approved if row.target_id == person_id]
    if any(row.contradicting_features for row in matching):
        return _hold("IDENTITY_CONTRADICTING_FEATURES_REQUIRE_REVIEW")

    identifier_map = _active_identifier_map(identifiers)
    referenced_ids = sorted(
        {
            identifier_id
            for row in matching
            for identifier_id in _resolution_identifier_ids(row)
        }
    )
    for identifier_id in referenced_ids:
        identifier = identifier_map.get(identifier_id)
        if identifier is None:
            return _hold("IDENTITY_IDENTIFIER_MISSING")
        if identifier.status != "ACTIVE":
            return _hold("IDENTITY_IDENTIFIER_SUPERSEDED")
        if identifier.entity_type != "PERSON" or identifier.entity_id != person_id:
            return _hold("IDENTITY_IDENTIFIER_PERSON_MISMATCH")

    active_roles = [
        row
        for row in role_intervals
        if row.person_id == person_id and row.covers(statement_date)
    ]
    if requested_role_interval_id:
        requested = [
            row
            for row in active_roles
            if row.interval_id == requested_role_interval_id
        ]
        if len(requested) != 1:
            return PublicAttributionDecision(
                decision="ALLOW",
                person_id=person_id,
                role_interval_id=None,
                public_role=None,
                organization_id=None,
                attribution_scope="SPEAKER_IDENTITY_ONLY",
                reason_codes=("ROLE_AT_STATEMENT_TIME_UNPROVEN",),
            )
        active_roles = requested

    if len(active_roles) > 1:
        return _hold("ROLE_AT_STATEMENT_TIME_AMBIGUOUS")
    if not active_roles:
        return PublicAttributionDecision(
            decision="ALLOW",
            person_id=person_id,
            role_interval_id=None,
            public_role=None,
            organization_id=None,
            attribution_scope="SPEAKER_IDENTITY_ONLY",
            reason_codes=("IDENTITY_APPROVED_ROLE_OMITTED",),
        )

    role = active_roles[0]
    return PublicAttributionDecision(
        decision="ALLOW",
        person_id=person_id,
        role_interval_id=role.interval_id,
        public_role=role.role,
        organization_id=role.organization_id,
        attribution_scope="SPEAKER_WITH_ROLE",
        reason_codes=("IDENTITY_AND_ROLE_AT_TIME_APPROVED",),
    )


__all__ = [
    "PUBLIC_ATTRIBUTION_VERSION",
    "PublicAttributionDecision",
    "RoleInterval",
    "evaluate_public_attribution",
]

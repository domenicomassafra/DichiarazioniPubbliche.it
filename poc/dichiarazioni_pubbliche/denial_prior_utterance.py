"""DP-315: private, source-bound three-track universal denial evaluator.

An attested prior occurrence is not proof of intent or of the truth of X.
No absence can prove a universal negative from a sampled/partial archive.
No result here permits publication or automatically creates a Finding.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from datetime import datetime, timezone


VERSION = "denial-prior-utterance-v1"
SHA = re.compile(r"[0-9a-f]{64}\Z")
ACTS = frozenset({"ASSERTION", "OPINION", "REPORTED_QUOTE", "CRITICISM", "IRONY", "QUESTION", "PERFORMANCE"})
PREDICATES = frozenset({"NEVER_UTTERED", "NEVER_ENDORSED", "NEVER_MEANT"})
SCOPES = frozenset({"PUBLIC", "PRIVATE", "ALL"})


def _present(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise ValueError(f"DENIAL_{field}_INVALID")


def _sha(value: str, field: str) -> None:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"DENIAL_{field}_HASH_INVALID")


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("DENIAL_AWARE_TIME_REQUIRED")
    return value.astimezone(timezone.utc)


def _receipt_fields(record: object) -> dict[str, object]:
    """Bind every typed metadata field, normalizing dates for stable replay."""
    return {
        field.name: (
            _time(value).isoformat() if isinstance(value, datetime) else value
        )
        for field in fields(record)
        for value in (getattr(record, field.name),)
    }


@dataclass(frozen=True)
class DenialTarget:
    denial_id: str
    person_id: str
    source_version_id: str
    source_sha256: str
    review_event_id: str
    uttered_at: datetime
    target_quote_sha256: str
    target_proposition_sha256: str
    predicate: str
    quantifier: str
    scope: str
    from_at: datetime | None
    through_at: datetime | None
    version: str = VERSION

    def __post_init__(self) -> None:
        for key in ("denial_id", "person_id", "source_version_id", "review_event_id"):
            _present(getattr(self, key), key.upper())
        for key in ("source_sha256", "target_quote_sha256", "target_proposition_sha256"):
            _sha(getattr(self, key), key.upper())
        if self.version != VERSION or self.predicate not in PREDICATES or self.quantifier != "NEVER" or self.scope not in SCOPES:
            raise ValueError("DENIAL_SCOPE_OR_PREDICATE_INVALID")
        end = _time(self.uttered_at)
        if self.from_at is not None and _time(self.from_at) >= end:
            raise ValueError("DENIAL_INVALID_BEGIN")
        if self.through_at is not None and _time(self.through_at) > end:
            raise ValueError("DENIAL_INVALID_END")
        if self.from_at is not None and self.through_at is not None and _time(self.from_at) > _time(self.through_at):
            raise ValueError("DENIAL_INVERTED_WINDOW")


@dataclass(frozen=True)
class PriorOccurrence:
    occurrence_id: str
    source_version_id: str
    source_sha256: str
    quote_sha256: str
    proposition_sha256: str
    spoken_at: datetime
    utterer_person_id: str
    quoted_person_id: str | None
    speech_act: str
    endorsed: bool
    publication_scope: str
    review_event_id: str | None
    status: str = "CURRENT"

    def __post_init__(self) -> None:
        for name in ("occurrence_id", "source_version_id", "utterer_person_id"):
            _present(getattr(self, name), name.upper())
        for name in ("source_sha256", "quote_sha256", "proposition_sha256"):
            _sha(getattr(self, name), name.upper())
        if self.quoted_person_id is not None:
            _present(self.quoted_person_id, "QUOTED_PERSON")
        _time(self.spoken_at)
        if self.speech_act not in ACTS or type(self.endorsed) is not bool:
            raise ValueError("DENIAL_SPEECH_ACT_INVALID")
        if self.publication_scope not in {"PUBLIC", "PRIVATE"} or self.status not in {"CURRENT", "SUPERSEDED", "REVOKED", "UNKNOWN"}:
            raise ValueError("DENIAL_OCCURRENCE_STATUS_INVALID")
        if self.review_event_id is not None:
            _present(self.review_event_id, "SOURCE_REVIEW")
        if self.speech_act in {"REPORTED_QUOTE", "CRITICISM", "IRONY", "QUESTION"} and self.endorsed:
            raise ValueError("DENIAL_FALSE_ENDORSEMENT_INVALID")


@dataclass(frozen=True)
class DenialReview:
    denial_id: str
    receipt_sha256: str
    prior_authenticity: str
    prior_endorsement: str
    denial_factual_status: str
    relation_status: str
    reason_code: str
    matched_occurrence_ids: tuple[str, ...]
    prior_proposition_truth: str = "NOT_EVALUATED"
    publication_authority: bool = False
    version: str = VERSION


def evaluate_denial(target: DenialTarget, occurrences: tuple[PriorOccurrence, ...], *,
                    current_source_versions: dict[str, str] | None = None) -> DenialReview:
    """Pure conservative check; missing/unknown source version is never approved."""
    if not isinstance(target, DenialTarget) or not isinstance(occurrences, tuple) or len(occurrences) > 128:
        raise ValueError("DENIAL_INPUT_UNBOUNDED_OR_INVALID")
    if any(not isinstance(row, PriorOccurrence) for row in occurrences):
        raise ValueError("DENIAL_OCCURRENCE_INVALID")
    if not isinstance(current_source_versions, dict):
        current_source_versions = {}
    candidate_ids: list[str] = []
    authenticity = "UNVERIFIED"
    endorsement = "UNKNOWN"
    verdict = "CHECKED_INSUFFICIENT_EVIDENCE"
    relation = "PRIVATE_HOLD"
    reason = "DENIAL_UNIVERSAL_ABSENCE_NOT_PROVABLE"
    target_current = current_source_versions.get(target.source_version_id) == target.source_sha256
    for row in occurrences if target_current else ():
        if not isinstance(row, PriorOccurrence):
            raise ValueError("DENIAL_OCCURRENCE_INVALID")
        if row.utterer_person_id != target.person_id:
            continue
        if _time(row.spoken_at) >= _time(target.uttered_at):
            continue
        if target.from_at and _time(row.spoken_at) < _time(target.from_at):
            continue
        if target.through_at and _time(row.spoken_at) > _time(target.through_at):
            continue
        if target.scope != "ALL" and target.scope != row.publication_scope:
            continue
        if row.quote_sha256 != target.target_quote_sha256 or row.proposition_sha256 != target.target_proposition_sha256:
            continue
        if row.status != "CURRENT" or row.review_event_id is None:
            reason = "DENIAL_PRIOR_REVIEW_OR_CURRENTNESS_MISSING"
            continue
        if current_source_versions.get(row.source_version_id) != row.source_sha256:
            reason = "DENIAL_PRIOR_SOURCE_HASH_STALE_OR_UNKNOWN"
            continue
        candidate_ids.append(row.occurrence_id)
        if row.speech_act in {"REPORTED_QUOTE", "CRITICISM", "IRONY", "QUESTION", "PERFORMANCE"}:
            authenticity = "REVIEWED_ORIGINAL_CONTEXTUAL_ONLY"
            endorsement = "NOT_ESTABLISHED"
            reason = "DENIAL_QUOTED_OR_PERFORMATIVE_CONTEXT"
            continue
        if row.quoted_person_id is not None and row.quoted_person_id != row.utterer_person_id:
            authenticity = "REVIEWED_ORIGINAL_CONTEXTUAL_ONLY"
            endorsement = "NOT_ESTABLISHED"
            reason = "DENIAL_OTHER_PERSON_QUOTED"
            continue
        authenticity = "REVIEWED_ORIGINAL_UTTERANCE"
        endorsement = "REVIEWED_ENDORSED" if row.endorsed else "NOT_ESTABLISHED"
        if target.predicate == "NEVER_UTTERED":
            verdict, relation, reason = "REFUTED_WITH_COUNTEREXAMPLE", "PRIVATE_RELATION_CANDIDATE", "DENIAL_ATTESTED_PRIOR_WORDS"
            break
        if target.predicate == "NEVER_ENDORSED" and row.endorsed:
            verdict, relation, reason = "REFUTED_WITH_COUNTEREXAMPLE", "PRIVATE_RELATION_CANDIDATE", "DENIAL_ATTESTED_PRIOR_ENDORSEMENT"
            break
        if target.predicate == "NEVER_MEANT":
            reason = "DENIAL_INNER_INTENT_UNVERIFIABLE"
    if target.predicate == "NEVER_MEANT":
        verdict, relation, reason = "CHECKED_INSUFFICIENT_EVIDENCE", "PRIVATE_HOLD", "DENIAL_INNER_INTENT_UNVERIFIABLE"
    if not target_current:
        verdict, relation, reason = "CHECKED_INSUFFICIENT_EVIDENCE", "PRIVATE_HOLD", "DENIAL_TARGET_SOURCE_STALE_OR_UNKNOWN"
    material = {
        "target": _receipt_fields(target),
        "occurrences": sorted(
            (_receipt_fields(row) for row in occurrences),
            key=lambda row: (str(row["occurrence_id"]), str(row["source_version_id"])),
        ),
        "matched": sorted(candidate_ids), "verdict": verdict, "reason": reason,
        "known_source_versions": sorted(current_source_versions.items()),
        "version": VERSION,
    }
    receipt_sha256 = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return DenialReview(target.denial_id, receipt_sha256, authenticity, endorsement, verdict,
                        relation, reason, tuple(sorted(set(candidate_ids))))

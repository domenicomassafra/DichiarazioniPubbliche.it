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
    # Detached, validated base-type values are the only source of both the
    # receipt and the decision. A frozen dataclass can still be subclassed or
    # mutated via __dict__; re-reading caller-owned rows after hashing them
    # could turn a revoked/contextual snapshot into an apparent counterexample.
    target = DenialTarget(**{
        field.name: getattr(target, field.name) for field in fields(DenialTarget)
    })
    occurrences = tuple(PriorOccurrence(**{
        field.name: getattr(row, field.name) for field in fields(PriorOccurrence)
    }) for row in occurrences)
    if not isinstance(current_source_versions, dict):
        current_source_versions = {}
    else:
        current_source_versions = dict(current_source_versions)
    # A replay has no meaningful input sequence. Sort by complete typed provenance,
    # including ties on occurrence/source IDs (e.g. a conflicting revocation).
    occurrence_snapshots = tuple(sorted(
        ((_receipt_fields(row), row) for row in occurrences),
        key=lambda entry: (
            str(entry[0]["occurrence_id"]),
            str(entry[0]["source_version_id"]),
            json.dumps(entry[0], sort_keys=True, separators=(",", ":")),
        ),
    ))
    first_by_id: dict[str, dict[str, object]] = {}
    conflicting_ids: set[str] = set()
    for snapshot, row in occurrence_snapshots:
        previous = first_by_id.setdefault(row.occurrence_id, snapshot)
        if previous != snapshot:
            conflicting_ids.add(row.occurrence_id)
    candidate_ids: list[str] = []
    authenticity = "UNVERIFIED"
    endorsement = "UNKNOWN"
    verdict = "CHECKED_INSUFFICIENT_EVIDENCE"
    relation = "PRIVATE_HOLD"
    reason = "DENIAL_UNIVERSAL_ABSENCE_NOT_PROVABLE"
    saw_prior_review_gap = False
    saw_prior_source_gap = False
    saw_contextual = False
    saw_foreign_quotation = False
    target_current = current_source_versions.get(target.source_version_id) == target.source_sha256
    for _snapshot, row in occurrence_snapshots if target_current else ():
        # An occurrence ID is immutable: a CURRENT row cannot approve a second,
        # conflicting REVOKED, amended or differently reviewed representation.
        if row.occurrence_id in conflicting_ids:
            continue
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
            saw_prior_review_gap = True
            continue
        if current_source_versions.get(row.source_version_id) != row.source_sha256:
            saw_prior_source_gap = True
            continue
        candidate_ids.append(row.occurrence_id)
        if row.speech_act in {"REPORTED_QUOTE", "CRITICISM", "IRONY", "QUESTION", "PERFORMANCE"}:
            saw_contextual = True
            if authenticity == "UNVERIFIED":
                authenticity, endorsement = "REVIEWED_ORIGINAL_CONTEXTUAL_ONLY", "NOT_ESTABLISHED"
            continue
        if row.quoted_person_id is not None and row.quoted_person_id != row.utterer_person_id:
            saw_foreign_quotation = True
            if authenticity == "UNVERIFIED":
                authenticity, endorsement = "REVIEWED_ORIGINAL_CONTEXTUAL_ONLY", "NOT_ESTABLISHED"
            continue
        authenticity = "REVIEWED_ORIGINAL_UTTERANCE"
        if row.endorsed:
            endorsement = "REVIEWED_ENDORSED"
        elif endorsement != "REVIEWED_ENDORSED":
            endorsement = "NOT_ESTABLISHED"
        if target.predicate == "NEVER_UTTERED":
            verdict, relation = "REFUTED_WITH_COUNTEREXAMPLE", "PRIVATE_RELATION_CANDIDATE"
        if target.predicate == "NEVER_ENDORSED" and row.endorsed:
            verdict, relation = "REFUTED_WITH_COUNTEREXAMPLE", "PRIVATE_RELATION_CANDIDATE"
    # The strongest reviewed counterexample wins; later contextual rows and
    # incomplete provenance must not overwrite its semantic classification.
    if verdict == "REFUTED_WITH_COUNTEREXAMPLE":
        reason = "DENIAL_ATTESTED_PRIOR_WORDS" if target.predicate == "NEVER_UTTERED" else "DENIAL_ATTESTED_PRIOR_ENDORSEMENT"
    elif conflicting_ids:
        reason = "DENIAL_CONFLICTING_OCCURRENCE_PROVENANCE"
    elif saw_prior_source_gap:
        reason = "DENIAL_PRIOR_SOURCE_HASH_STALE_OR_UNKNOWN"
    elif saw_prior_review_gap:
        reason = "DENIAL_PRIOR_REVIEW_OR_CURRENTNESS_MISSING"
    elif saw_foreign_quotation:
        reason = "DENIAL_OTHER_PERSON_QUOTED"
    elif saw_contextual:
        reason = "DENIAL_QUOTED_OR_PERFORMATIVE_CONTEXT"
    if target.predicate == "NEVER_MEANT":
        verdict, relation, reason = "CHECKED_INSUFFICIENT_EVIDENCE", "PRIVATE_HOLD", "DENIAL_INNER_INTENT_UNVERIFIABLE"
    if not target_current:
        verdict, relation, reason = "CHECKED_INSUFFICIENT_EVIDENCE", "PRIVATE_HOLD", "DENIAL_TARGET_SOURCE_STALE_OR_UNKNOWN"
    material = {
        "target": _receipt_fields(target),
        "occurrences": [snapshot for snapshot, _row in occurrence_snapshots],
        "matched": sorted(candidate_ids), "verdict": verdict, "reason": reason,
        "known_source_versions": sorted(current_source_versions.items()),
        "version": VERSION,
    }
    receipt_sha256 = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return DenialReview(target.denial_id, receipt_sha256, authenticity, endorsement, verdict,
                        relation, reason, tuple(sorted(set(candidate_ids))))

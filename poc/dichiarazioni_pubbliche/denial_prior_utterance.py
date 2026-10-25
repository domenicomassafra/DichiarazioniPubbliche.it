"""DP-315: private, source-bound three-track universal denial evaluator.

An attested prior occurrence is not proof of intent or of the truth of X.
No absence can prove a universal negative from a sampled/partial archive.
No result here permits publication or automatically creates a Finding.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime, timezone

from dichiarazioni_pubbliche.context_integrity import verify_speech_act_context_metadata


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
        if self.speech_act in {"REPORTED_QUOTE", "CRITICISM", "IRONY", "QUESTION", "PERFORMANCE"} and self.endorsed:
            raise ValueError("DENIAL_FALSE_ENDORSEMENT_INVALID")


@dataclass(frozen=True)
class DenialCoverageAttempt:
    """One bounded search attempt, with no claim of exhaustive recall."""

    attempt_id: str
    source_version_id: str
    source_sha256: str
    query_sha256: str
    searched_at: datetime
    outcome: str

    def __post_init__(self) -> None:
        _present(self.attempt_id, "COVERAGE_ATTEMPT_ID")
        _present(self.source_version_id, "COVERAGE_SOURCE_VERSION")
        _sha(self.source_sha256, "COVERAGE_SOURCE")
        _sha(self.query_sha256, "COVERAGE_QUERY")
        _time(self.searched_at)
        if self.outcome not in {"SEARCHED_PARTIAL", "SEARCHED_BOUNDED", "SOURCE_UNAVAILABLE"}:
            raise ValueError("DENIAL_COVERAGE_OUTCOME_INVALID")


@dataclass(frozen=True)
class DenialCoverageManifest:
    """Caller-provided search inventory; its review ref is not source authority."""

    denial_id: str
    person_id: str
    scope: str
    from_at: datetime | None
    through_at: datetime | None
    collection_sha256: str
    review_event_id: str
    observed_at: datetime
    attempts: tuple[DenialCoverageAttempt, ...]

    def __post_init__(self) -> None:
        _present(self.denial_id, "COVERAGE_DENIAL_ID")
        _present(self.person_id, "COVERAGE_PERSON_ID")
        _present(self.review_event_id, "COVERAGE_REVIEW_EVENT")
        _sha(self.collection_sha256, "COVERAGE_COLLECTION")
        observed_at = _time(self.observed_at)
        if self.scope not in SCOPES:
            raise ValueError("DENIAL_COVERAGE_SCOPE_INVALID")
        if self.from_at is not None:
            _time(self.from_at)
        if self.through_at is not None:
            _time(self.through_at)
        if (type(self.attempts) is not tuple or not 1 <= len(self.attempts) <= 128
                or any(type(item) is not DenialCoverageAttempt for item in self.attempts)
                or len({item.attempt_id for item in self.attempts}) != len(self.attempts)
                or any(_time(item.searched_at) > observed_at for item in self.attempts)):
            raise ValueError("DENIAL_COVERAGE_ATTEMPTS_INVALID")


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
    coverage_status: str = "NO_SEARCH_MANIFEST_HOLD"
    coverage_attempt_ids: tuple[str, ...] = ()


def evaluate_denial(target: DenialTarget, occurrences: tuple[PriorOccurrence, ...], *,
                    current_source_versions: dict[str, str] | None = None,
                    prior_source_context: dict[str, tuple[str, Mapping[str, object]]] | None = None,
                    coverage_manifest: DenialCoverageManifest | None = None) -> DenialReview:
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
    coverage_snapshot = None
    coverage_attempt_ids: tuple[str, ...] = ()
    if coverage_manifest is not None:
        if type(coverage_manifest) is not DenialCoverageManifest:
            raise ValueError("DENIAL_COVERAGE_MANIFEST_INVALID")
        # Snapshot all fields, including search attempts, before any decision.
        coverage_data = {
            field.name: getattr(coverage_manifest, field.name)
            for field in fields(DenialCoverageManifest)
        }
        if type(coverage_data["attempts"]) is not tuple:
            raise ValueError("DENIAL_COVERAGE_ATTEMPTS_INVALID")
        coverage_data["attempts"] = tuple(
            DenialCoverageAttempt(**{
                field.name: getattr(attempt, field.name)
                for field in fields(DenialCoverageAttempt)
            })
            for attempt in coverage_data["attempts"]
        )
        coverage = DenialCoverageManifest(**coverage_data)
        if (coverage.denial_id != target.denial_id
                or coverage.person_id != target.person_id
                or coverage.scope != target.scope
                or (None if coverage.from_at is None else _time(coverage.from_at))
                != (None if target.from_at is None else _time(target.from_at))
                or (None if coverage.through_at is None else _time(coverage.through_at))
                != (None if target.through_at is None else _time(target.through_at))):
            raise ValueError("DENIAL_COVERAGE_SCOPE_MISMATCH")
        coverage_attempt_ids = tuple(sorted(item.attempt_id for item in coverage.attempts))
        coverage_snapshot = {
            "denial_id": coverage.denial_id,
            "person_id": coverage.person_id,
            "scope": coverage.scope,
            "from_at": None if coverage.from_at is None else _time(coverage.from_at).isoformat(),
            "through_at": None if coverage.through_at is None else _time(coverage.through_at).isoformat(),
            "collection_sha256": coverage.collection_sha256,
            "review_event_id": coverage.review_event_id,
            "observed_at": _time(coverage.observed_at).isoformat(),
            "attempts": sorted(
                (_receipt_fields(attempt) for attempt in coverage.attempts),
                key=lambda item: item["attempt_id"],
            ),
        }
    if not isinstance(current_source_versions, dict):
        current_source_versions = {}
    else:
        current_source_versions = dict(current_source_versions)
    coverage_sources_current = (
        coverage_snapshot is not None
        and all(current_source_versions.get(item.source_version_id) == item.source_sha256
                for item in coverage.attempts)
    )
    # Optional strict source verification. The legacy metadata-only path remains
    # private, but supplied excerpts must bind exact source/quote bytes, speaker,
    # complete turn, speech act and endorsement before forming a counterexample.
    # Neither text nor reviewer assertions are written to the receipt.
    occurrence_ids = {row.occurrence_id for row in occurrences}
    if prior_source_context is not None:
        if (not isinstance(prior_source_context, dict)
                or len(prior_source_context) > 128
                or any(key not in occurrence_ids for key in prior_source_context)):
            raise ValueError("DENIAL_CONTEXT_INPUT_INVALID")
    supplied_context = dict(prior_source_context) if prior_source_context is not None else None
    unverified_context_ids: set[str] = set()
    context_bindings: list[tuple[str, str, str, str | None]] = []
    if supplied_context is not None:
        for row in occurrences:
            supplied = supplied_context.get(row.occurrence_id)
            source_digest: str | None = None
            result = None
            if (isinstance(supplied, tuple) and len(supplied) == 2
                    and isinstance(supplied[0], str)
                    and len(supplied[0]) <= 120_000
                    and isinstance(supplied[1], Mapping)):
                source_text, metadata = supplied
                source_digest = hashlib.sha256(source_text.encode()).hexdigest()
                try:
                    result = verify_speech_act_context_metadata(
                        metadata, source_text=source_text,
                    )
                except (ValueError, TypeError, KeyError):
                    pass
            valid = (
                result is not None
                and result.state == "CANDIDATE_PRIVATE"
                and result.source_sha256 == row.source_sha256
                and result.quote_sha256 == row.quote_sha256
                and result.utterer_id == row.utterer_person_id
                and result.quoted_author_id == row.quoted_person_id
                and result.speech_act == row.speech_act
                and (not row.endorsed or result.stance == "ENDORSE")
            )
            if not valid:
                unverified_context_ids.add(row.occurrence_id)
            context_bindings.append((
                row.occurrence_id, row.source_sha256,
                result.binding_sha256 if valid else "UNVERIFIED",
                source_digest,
            ))
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
    saw_prior_context_gap = False
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
        if row.occurrence_id in unverified_context_ids:
            saw_prior_context_gap = True
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
    elif saw_prior_context_gap:
        reason = "DENIAL_PRIOR_CONTEXT_UNVERIFIED"
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
    if coverage_snapshot is not None:
        material["coverage_manifest"] = coverage_snapshot
    if supplied_context is not None:
        material["prior_source_context_bindings"] = sorted(context_bindings)
    receipt_sha256 = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return DenialReview(
        target.denial_id, receipt_sha256, authenticity, endorsement, verdict,
        relation, reason, tuple(sorted(set(candidate_ids))),
        coverage_status=("NO_SEARCH_MANIFEST_HOLD" if coverage_snapshot is None
                         else "SEARCH_ATTEMPTS_RECORDED_HOLD" if coverage_sources_current
                         else "SEARCH_ATTEMPTS_STALE_OR_UNKNOWN_HOLD"),
        coverage_attempt_ids=coverage_attempt_ids,
    )

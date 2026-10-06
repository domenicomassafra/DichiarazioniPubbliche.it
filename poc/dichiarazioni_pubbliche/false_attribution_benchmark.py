from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from dichiarazioni_pubbliche.citation_assurance import (
    CitationBinding,
    FindingAssertion,
    assertion_text_sha256,
    assure_material_assertions,
)
from dichiarazioni_pubbliche.context_integrity import assess_context_integrity
from dichiarazioni_pubbliche.countercase import (
    CounterEvidence,
    build_countercase_packet,
    evaluate_challenger_readiness,
)
from dichiarazioni_pubbliche.knowledge_repository import make_resolution_candidate
from dichiarazioni_pubbliche.original_source_resolver import (
    DerivationEdge,
    resolve_reviewed_original_source,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import (
    EXCERPT_PUBLIC_USE_REQUIRED,
    ExcerptDisposition,
    ExcerptRequest,
    decide_excerpt,
)
from dichiarazioni_pubbliche.public_attribution import evaluate_public_attribution
from dichiarazioni_pubbliche.quote_binding import verify_written_quote_binding
from dichiarazioni_pubbliche.speaker_runtime import make_speaker_candidate
from dichiarazioni_pubbliche.transcript_contract import (
    TranscriptCandidate,
    TranscriptStatus,
    reconcile_candidates,
)
from dichiarazioni_pubbliche.wording_contract import (
    SOURCE_WORDING_TYPES,
    TranslationReviewState,
    WordingType,
    assert_direct_quote_eligible,
    assess_translation,
    make_derived_wording,
    make_source_occurrence_wording,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "false-attribution-adversarial-v1.json"
SCHEMA_VERSION = "dp-223-adversarial-benchmark/v1"

REQUIRED_CLASSES = (
    "same_name_people",
    "rapid_host_guest_alternation",
    "narrator_reading_another_quote",
    "politician_quoting_opponent",
    "old_embedded_clip_current_commentary",
    "verified_account_repost_third_party_media",
    "asr_sensitive_token_error",
    "overlapping_or_off_camera_speaker",
    "qualification_clipping",
    "yes_no_without_question",
    "conditional_flattened_to_assertion",
    "paraphrase_or_headline_as_quote",
    "translation_semantic_drift",
    "syndicated_upstream_quote",
    "source_page_updated_after_capture",
    "stale_review_after_source_version_change",
    "finding_assertion_bad_citation",
    "direct_status_person_quote_tampering",
    "rights_hold_or_source_body_unavailable",
    "fabricated_sentence_absent_from_source",
    "challenger_only_countercase",
    "transcript_homophone_disagreement",
    "transcript_punctuation_disagreement",
    "transcript_cross_talk_disagreement",
)


class FixtureDriftError(ValueError):
    """Raised when a versioned benchmark fixture no longer matches its authored hashes."""


@dataclass(frozen=True)
class CaseOutcome:
    publication_state: str
    person_id: str | None
    wording_type: str
    reason_codes: tuple[str, ...]
    quote_exact: bool | None = None
    speaker_span_covered: bool | None = None


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    case_class: str
    variant: str
    expected_publication_state: str
    actual_publication_state: str
    expected_person_id: str | None
    actual_person_id: str | None
    expected_wording_type: str
    actual_wording_type: str
    quote_exact: bool | None
    speaker_span_covered: bool | None
    reason_codes: tuple[str, ...]
    risk_tags: tuple[str, ...]
    passed: bool


@dataclass(frozen=True)
class BenchmarkReport:
    schema_version: str
    fixture_version: str
    fixture_sha256: str
    total_cases: int
    failed_cases: int
    release_gate_passed: bool
    benchmark_passed: bool
    metrics: Mapping[str, int | float]
    class_case_counts: Mapping[str, int]
    cases: tuple[BenchmarkCaseResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fixture_version": self.fixture_version,
            "fixture_sha256": self.fixture_sha256,
            "total_cases": self.total_cases,
            "failed_cases": self.failed_cases,
            "release_gate_passed": self.release_gate_passed,
            "benchmark_passed": self.benchmark_passed,
            "metrics": dict(self.metrics),
            "class_case_counts": dict(self.class_case_counts),
            "cases": [asdict(case) for case in self.cases],
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _canonical_fixture_sha256(raw: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(raw))
    payload.pop("integrity", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_mapping(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return dict(value)


def load_fixture(path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("DP223_FIXTURE_SCHEMA_VERSION_INVALID")

    integrity = _require_mapping(raw.get("integrity"), "DP223_FIXTURE_INTEGRITY_REQUIRED")
    if integrity.get("algorithm") != "sha256-canonical-json-without-integrity":
        raise ValueError("DP223_FIXTURE_INTEGRITY_ALGORITHM_INVALID")
    authored_digest = str(integrity.get("fixture_sha256") or "").lower()
    computed_digest = _canonical_fixture_sha256(raw)
    if authored_digest != computed_digest:
        raise FixtureDriftError("DP223_FIXTURE_HASH_DRIFT")

    required = raw.get("required_classes")
    if not isinstance(required, list) or tuple(required) != REQUIRED_CLASSES:
        raise ValueError("DP223_REQUIRED_CLASSES_MISMATCH")
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("DP223_CASES_REQUIRED")

    seen_ids: set[str] = set()
    variants_by_class: dict[str, set[str]] = {name: set() for name in REQUIRED_CLASSES}
    valid_wording_types = {item.value for item in WordingType}
    for raw_case in cases:
        case = _require_mapping(raw_case, "DP223_CASE_INVALID")
        case_id = str(case.get("id") or "").strip()
        case_class = str(case.get("class") or "").strip()
        variant = str(case.get("variant") or "").strip()
        if not case_id or case_id in seen_ids:
            raise ValueError("DP223_CASE_ID_INVALID_OR_DUPLICATE")
        seen_ids.add(case_id)
        if case_class not in variants_by_class:
            raise ValueError(f"DP223_CASE_CLASS_INVALID:{case_id}")
        if variant not in {"ADVERSARIAL", "CONTROL"}:
            raise ValueError(f"DP223_CASE_VARIANT_INVALID:{case_id}")
        variants_by_class[case_class].add(variant)

        source = _require_mapping(case.get("source"), f"DP223_SOURCE_REQUIRED:{case_id}")
        span = _require_mapping(case.get("span"), f"DP223_SPAN_REQUIRED:{case_id}")
        expected = _require_mapping(case.get("expected"), f"DP223_EXPECTED_REQUIRED:{case_id}")
        source_text = str(source.get("text") or "")
        source_sha = str(source.get("sha256") or "").lower()
        if not source_text or _sha256(source_text) != source_sha:
            raise FixtureDriftError(f"DP223_SOURCE_HASH_DRIFT:{case_id}")
        start = span.get("start")
        end = span.get("end")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
            or end > len(source_text)
        ):
            raise FixtureDriftError(f"DP223_SPAN_RANGE_DRIFT:{case_id}")
        span_text = str(span.get("text") or "")
        span_sha = str(span.get("sha256") or "").lower()
        if source_text[start:end] != span_text or _sha256(span_text) != span_sha:
            raise FixtureDriftError(f"DP223_SPAN_HASH_DRIFT:{case_id}")

        if (
            expected.get("source_id") != source.get("source_id")
            or expected.get("source_sha256") != source_sha
            or expected.get("span_start") != start
            or expected.get("span_end") != end
            or expected.get("span_sha256") != span_sha
        ):
            raise FixtureDriftError(f"DP223_EXPECTED_APPROVAL_DRIFT:{case_id}")
        if expected.get("wording_type") not in valid_wording_types:
            raise ValueError(f"DP223_EXPECTED_WORDING_TYPE_INVALID:{case_id}")
        if expected.get("publication_state") not in {"PUBLIC", "HELD", "OMITTED", "UNRESOLVED"}:
            raise ValueError(f"DP223_EXPECTED_PUBLICATION_STATE_INVALID:{case_id}")

    for case_class, variants in variants_by_class.items():
        if variants != {"ADVERSARIAL", "CONTROL"}:
            raise ValueError(f"DP223_CLASS_CONTROL_COVERAGE_MISSING:{case_class}")
    return raw


def _quote_binding_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    source = _require_mapping(case["source"], "DP223_SOURCE_REQUIRED")
    span = _require_mapping(case["span"], "DP223_SPAN_REQUIRED")
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    proposed_text = str(params.get("proposed_text", span["text"]))
    private_text = str(span["text"]) if params.get("body_available", True) else ""
    try:
        result = verify_written_quote_binding(
            statement_text_sha256=str(params.get("statement_text_sha256") or _sha256(proposed_text)),
            passage_text_sha256=str(params.get("passage_text_sha256") or span["sha256"]),
            private_text=private_text,
            selector_type=str(params.get("selector_type") or "TEXT_POSITION"),
            start_char=int(params.get("start_char", span["start"])),
            end_char=int(params.get("end_char", span["end"])),
            source_sha256=str(params.get("source_sha256") or source["sha256"]),
        )
    except (TypeError, ValueError) as exc:
        return CaseOutcome(
            publication_state="HELD",
            person_id=str(expected.get("person_id") or "") or None,
            wording_type=str(expected["wording_type"]),
            reason_codes=(str(exc),),
            quote_exact=False,
        )
    return CaseOutcome(
        publication_state="PUBLIC" if result.verified else "HELD",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=(result.reason_code,),
        quote_exact=result.verified,
    )


def _context_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    source = _require_mapping(case["source"], "DP223_SOURCE_REQUIRED")
    span = _require_mapping(case["span"], "DP223_SPAN_REQUIRED")
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    try:
        assessment = assess_context_integrity(
            source_text=str(source["text"]),
            source_sha256=str(params.get("source_sha256") or source["sha256"]),
            quote_start=int(params.get("quote_start", span["start"])),
            quote_end=int(params.get("quote_end", span["end"])),
            speech_mode=str(params.get("speech_mode") or "DIRECT_UTTERANCE"),
        )
    except (TypeError, ValueError) as exc:
        return CaseOutcome(
            publication_state="HELD",
            person_id=str(expected.get("person_id") or "") or None,
            wording_type=str(expected["wording_type"]),
            reason_codes=(str(exc),),
            quote_exact=False,
        )
    return CaseOutcome(
        publication_state="PUBLIC" if assessment.clear else "HELD",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=assessment.signal_codes or ("CONTEXT_CLEAR",),
        quote_exact=True,
    )


def _wording_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    span = _require_mapping(case["span"], "DP223_SPAN_REQUIRED")
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    wording_type = WordingType(str(params.get("wording_type") or expected["wording_type"]))
    try:
        if wording_type in SOURCE_WORDING_TYPES:
            wording = make_source_occurrence_wording(
                occurrence_id=str(case["id"]),
                text_sha256=str(span["sha256"]),
                language="it",
                derivation_version="dp-223-fixture-v1",
                wording_type=wording_type,
            )
        else:
            wording = make_derived_wording(
                wording_type=wording_type,
                occurrence_id=str(case["id"]),
                text=str(params.get("derived_text") or span["text"]),
                source_wording_type=WordingType.VERBATIM_ORIGINAL,
                language="it",
                derivation_method="DP223_SYNTHETIC_DERIVATION",
                derivation_version="dp-223-fixture-v1",
            )
        assert_direct_quote_eligible(wording)
    except ValueError as exc:
        return CaseOutcome(
            publication_state="HELD",
            person_id=str(expected.get("person_id") or "") or None,
            wording_type=wording_type.value,
            reason_codes=(str(exc),),
            quote_exact=None,
        )
    return CaseOutcome(
        publication_state="PUBLIC",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=wording_type.value,
        reason_codes=("DIRECT_QUOTE_ELIGIBLE",),
        quote_exact=True,
    )


def _translation_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    assessment = assess_translation(
        source_text=str(params["source_text"]),
        translated_text=str(params["translated_text"]),
        source_language=str(params["source_language"]),
        target_language=str(params["target_language"]),
        method=str(params["method"]),
        human_reviewed=bool(params.get("human_reviewed", False)),
    )
    reviewed = assessment.state is TranslationReviewState.HUMAN_REVIEWED
    return CaseOutcome(
        publication_state="PUBLIC" if reviewed else "HELD",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=WordingType.TRANSLATION.value,
        reason_codes=assessment.signal_codes or ("TRANSLATION_HUMAN_REVIEWED",),
        quote_exact=None,
    )


def _public_attribution_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    speaker_spec = _require_mapping(params["speaker"], "DP223_SPEAKER_INPUT_INVALID")
    speaker = make_speaker_candidate(
        content_id=str(speaker_spec["content_id"]),
        person_id=str(speaker_spec["person_id"]),
        start_ms=int(speaker_spec["start_ms"]),
        end_ms=int(speaker_spec["end_ms"]),
        attribution_method=str(speaker_spec["method"]),
        source_ref=dict(speaker_spec.get("source_ref") or {}),
    )
    resolutions = []
    for index, raw_resolution in enumerate(params.get("resolutions") or []):
        spec = _require_mapping(raw_resolution, "DP223_RESOLUTION_INPUT_INVALID")
        row = make_resolution_candidate(
            content_id=str(params["content_id"]),
            passage_id=f"passage:{case['id']}:{index}",
            mention_text=str(spec.get("mention_text") or "Persona Alfa"),
            entity_type="PERSON",
            target_id=str(spec["target_id"]),
            resolution_method="MANUAL_REVIEW",
            supporting_features=tuple(spec.get("supporting_features") or ()),
            contradicting_features=tuple(spec.get("contradicting_features") or ()),
        )
        resolutions.append(replace(row, status=str(spec.get("status") or "CANDIDATE")))
    decision = evaluate_public_attribution(
        person_id=str(params["requested_person_id"]),
        content_id=str(params["content_id"]),
        occurrence_start_ms=int(params["occurrence_start_ms"]),
        occurrence_end_ms=int(params["occurrence_end_ms"]),
        statement_date=date.fromisoformat(str(params["statement_date"])),
        speaker_candidate=speaker,
        resolution_candidates=tuple(resolutions),
        occurrence_kind=str(params.get("occurrence_kind") or "SPEAKER"),
    )
    return CaseOutcome(
        publication_state="PUBLIC" if decision.publication_allowed else "HELD",
        person_id=decision.person_id,
        wording_type=str(expected["wording_type"]),
        reason_codes=decision.reason_codes,
        quote_exact=True,
        speaker_span_covered=decision.publication_allowed,
    )


def _original_source_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    edges = tuple(
        DerivationEdge(
            edge_id=str(edge.get("id") or edge.get("edge_id") or ""),
            family_id=str(edge.get("family_id") or ""),
            derived_content_id=str(edge.get("derived_content_id") or ""),
            origin_content_id=str(edge.get("origin_content_id") or ""),
            relation_type=str(edge.get("relation_type") or ""),
            status=str(edge.get("status") or "CANDIDATE"),
        )
        for edge in params.get("edges") or []
    )
    resolution = resolve_reviewed_original_source(
        str(params["content_id"]),
        families=tuple(params.get("families") or ()),
        edges=edges,
    )
    return CaseOutcome(
        publication_state="PUBLIC" if resolution.resolved else "UNRESOLVED",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=resolution.blockers or ("ORIGINAL_SOURCE_RESOLVED",),
        quote_exact=True if resolution.resolved else None,
    )


def _citation_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    assertion = FindingAssertion(
        assertion_id=f"finding-assertion:{case['id']}",
        text=str(params["assertion_text"]),
        required_relation="SUPPORT",
    )
    binding = CitationBinding(
        assertion_id=assertion.assertion_id,
        assertion_text_sha256=str(
            params.get("assertion_text_sha256") or assertion_text_sha256(assertion.text)
        ),
        evidence_id=str(params["evidence_id"]),
        relation=str(params["relation"]),
    )
    result = assure_material_assertions(
        (assertion,),
        (binding,),
        approved_evidence_ids=tuple(params.get("approved_evidence_ids") or ()),
    )
    return CaseOutcome(
        publication_state="PUBLIC" if result.passed else "HELD",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=tuple(issue.code for issue in result.issues) or ("CITATION_ASSURED",),
        quote_exact=True,
    )


def _excerpt_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    source = _require_mapping(case["source"], "DP223_SOURCE_REQUIRED")
    span = _require_mapping(case["span"], "DP223_SPAN_REQUIRED")
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    request = ExcerptRequest(
        excerpt_text=str(params.get("excerpt_text") or span["text"]),
        rights_status=str(params.get("rights_status") or "CLEARED"),
        permitted_public_uses=(EXCERPT_PUBLIC_USE_REQUIRED,),
        rights_reviewed_on="2026-01-01",
        today="2026-10-05",
        source_url=f"https://benchmark.invalid/{case['id']}",
        content_id=f"content:{case['id']}",
        segment_id=f"segment:{case['id']}",
        transcript_variant_id=f"transcript:{case['id']}",
        timestamp_start_seconds=1.0,
        timestamp_end_seconds=2.0,
        source_content_sha256=str(source["sha256"]),
        observed_source_sha256=str(params.get("observed_source_sha256") or source["sha256"]),
        segment_is_stale=bool(params.get("segment_is_stale", False)),
        excerpt_review_approved=bool(params.get("excerpt_review_approved", True)),
        request_kind="EXCERPT",
        profile_approved=True,
        max_excerpt_chars=400,
        total_source_chars=1000,
    )
    decision = decide_excerpt(request)
    if decision.allowed:
        state = "PUBLIC"
    elif decision.disposition is ExcerptDisposition.HOLD_FOR_REVIEW:
        state = "HELD"
    else:
        state = "OMITTED"
    return CaseOutcome(
        publication_state=state,
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=tuple(code.value for code in decision.codes),
        quote_exact=True if decision.allowed else None,
    )


def _challenger_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    counter = tuple(
        CounterEvidence(
            evidence_id=str(row["evidence_id"]),
            relation=str(row["relation"]),
            rationale_code=str(row.get("rationale_code") or "DP223_CHALLENGER_CASE"),
            approved=bool(row.get("approved", True)),
            suitable=bool(row.get("suitable", True)),
            independence_group=(
                str(row["independence_group"])
                if row.get("independence_group") is not None
                else None
            ),
        )
        for row in params.get("counterevidence") or ()
    )
    packet = build_countercase_packet(
        claim_id=str(params.get("claim_id") or f"claim:{case['id']}"),
        evidence=counter,
        research_complete=bool(params.get("research_complete", True)),
    )
    incorporated = packet.packet_id if bool(params.get("incorporated_current", False)) else str(
        params.get("incorporated_packet_id") or "countercase:stale"
    )
    reviewed = packet.packet_id if bool(params.get("reviewed_current", False)) else str(
        params.get("reviewed_packet_id") or "countercase:stale"
    )
    readiness = evaluate_challenger_readiness(
        packet,
        incorporated_packet_id=incorporated,
        reviewed_packet_id=reviewed,
        high_risk=bool(params.get("high_risk", False)),
        qualified_policy_waives_challenger=bool(
            params.get("qualified_policy_waives_challenger", False)
        ),
    )
    return CaseOutcome(
        publication_state="PUBLIC" if readiness.ready else "HELD",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=readiness.blockers or ("CHALLENGER_READY",),
        quote_exact=True,
    )


def _transcript_verbatim_outcome(case: Mapping[str, Any]) -> CaseOutcome:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    params = _require_mapping(case.get("input", {}), "DP223_INPUT_INVALID")
    candidates = tuple(
        TranscriptCandidate(
            candidate_id=str(row.get("candidate_id") or f"candidate:{case['id']}:{index}"),
            provider_id=str(row.get("provider_id") or "synthetic-benchmark"),
            text=str(row["text"]),
            start_ms=int(row.get("start_ms", 0)),
            end_ms=int(row.get("end_ms", 2000)),
            source_kind=str(row.get("source_kind") or "ASR"),
        )
        for index, row in enumerate(params.get("candidates") or ())
    )
    segment = reconcile_candidates(
        candidates,
        gazetteer_terms=tuple(str(value) for value in params.get("gazetteer_terms") or ()),
    )
    public = (
        segment.status is TranscriptStatus.RESOLVED
        and not segment.publication_blocked
        and segment.verbatim_eligible
    )
    blockers: list[str] = []
    if segment.status is not TranscriptStatus.RESOLVED:
        blockers.append(f"TRANSCRIPT_{segment.status.value}")
    if segment.publication_blocked:
        blockers.append("TRANSCRIPT_PUBLICATION_BLOCKED")
    if not segment.verbatim_eligible:
        blockers.append("TRANSCRIPT_VERBATIM_AUTHORITY_REQUIRED")
    return CaseOutcome(
        publication_state="PUBLIC" if public else "HELD",
        person_id=str(expected.get("person_id") or "") or None,
        wording_type=str(expected["wording_type"]),
        reason_codes=tuple(blockers) or ("TRANSCRIPT_VERBATIM_VERIFIED",),
        quote_exact=public,
    )


_GATE_HANDLERS = {
    "quote_binding": _quote_binding_outcome,
    "context_integrity": _context_outcome,
    "wording": _wording_outcome,
    "translation": _translation_outcome,
    "public_attribution": _public_attribution_outcome,
    "original_source": _original_source_outcome,
    "citation_assurance": _citation_outcome,
    "excerpt_rights": _excerpt_outcome,
    "challenger_readiness": _challenger_outcome,
    "transcript_verbatim": _transcript_verbatim_outcome,
}


def _case_passed(case: Mapping[str, Any], outcome: CaseOutcome) -> bool:
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    if outcome.publication_state != expected["publication_state"]:
        return False
    if outcome.wording_type != expected["wording_type"]:
        return False
    if expected["publication_state"] == "PUBLIC" and outcome.person_id != expected.get("person_id"):
        return False
    expected_quote_exact = expected.get("quote_exact")
    if expected_quote_exact is not None and outcome.quote_exact is not expected_quote_exact:
        return False
    expected_speaker_covered = expected.get("speaker_span_covered")
    if (
        expected_speaker_covered is not None
        and outcome.speaker_span_covered is not expected_speaker_covered
    ):
        return False
    reason_any = tuple(str(value) for value in expected.get("reason_any") or ())
    if reason_any and not set(reason_any).intersection(outcome.reason_codes):
        return False
    return True


def _evaluate_case(case: Mapping[str, Any]) -> BenchmarkCaseResult:
    gate = str(case.get("gate") or "")
    handler = _GATE_HANDLERS.get(gate)
    if handler is None:
        raise ValueError(f"DP223_GATE_INVALID:{case.get('id')}:{gate}")
    outcome = handler(case)
    expected = _require_mapping(case["expected"], "DP223_EXPECTED_REQUIRED")
    return BenchmarkCaseResult(
        case_id=str(case["id"]),
        case_class=str(case["class"]),
        variant=str(case["variant"]),
        expected_publication_state=str(expected["publication_state"]),
        actual_publication_state=outcome.publication_state,
        expected_person_id=str(expected.get("person_id") or "") or None,
        actual_person_id=outcome.person_id,
        expected_wording_type=str(expected["wording_type"]),
        actual_wording_type=outcome.wording_type,
        quote_exact=outcome.quote_exact,
        speaker_span_covered=outcome.speaker_span_covered,
        reason_codes=outcome.reason_codes,
        risk_tags=tuple(str(tag) for tag in case.get("risk_tags") or ()),
        passed=_case_passed(case, outcome),
    )


def run_benchmark(path: Path = DEFAULT_FIXTURE) -> BenchmarkReport:
    fixture = load_fixture(path)
    results = tuple(_evaluate_case(case) for case in fixture["cases"])
    class_counts = {name: 0 for name in REQUIRED_CLASSES}
    for result in results:
        class_counts[result.case_class] += 1

    false_public_attribution = 0
    fabricated_public_quote = 0
    context_review_escape = 0
    stale_provenance_escape = 0
    for result in results:
        unsafe_publication = (
            result.actual_publication_state == "PUBLIC"
            and result.expected_publication_state != "PUBLIC"
        )
        if result.actual_publication_state == "PUBLIC" and (
            (
                "FALSE_ATTRIBUTION" in result.risk_tags
                and unsafe_publication
            )
            or (
                result.expected_person_id is not None
                and result.actual_person_id != result.expected_person_id
            )
        ):
            false_public_attribution += 1
        if result.actual_publication_state == "PUBLIC" and (
            ("FABRICATED_QUOTE" in result.risk_tags and unsafe_publication)
            or (
                result.actual_wording_type == WordingType.VERBATIM_ORIGINAL.value
                and result.quote_exact is False
            )
        ):
            fabricated_public_quote += 1
        if (
            "CONTEXT_REVIEW" in result.risk_tags
            and result.expected_publication_state != "PUBLIC"
            and result.actual_publication_state == "PUBLIC"
        ):
            context_review_escape += 1
        if (
            "STALE_PROVENANCE" in result.risk_tags
            and result.expected_publication_state != "PUBLIC"
            and result.actual_publication_state == "PUBLIC"
        ):
            stale_provenance_escape += 1

    quote_measured = [item for item in results if item.quote_exact is not None]
    speaker_measured = [item for item in results if item.speaker_span_covered is not None]
    quote_exact_count = sum(item.quote_exact is True for item in quote_measured)
    speaker_covered_count = sum(item.speaker_span_covered is True for item in speaker_measured)
    correct_public = sum(
        item.passed and item.expected_publication_state == "PUBLIC" for item in results
    )
    correct_holds = sum(
        item.passed and item.expected_publication_state != "PUBLIC" for item in results
    )
    false_holds = sum(
        item.expected_publication_state == "PUBLIC"
        and item.actual_publication_state != "PUBLIC"
        for item in results
    )
    unresolved = sum(item.actual_publication_state == "UNRESOLVED" for item in results)
    failed = sum(not item.passed for item in results)
    release_gate = false_public_attribution == 0 and fabricated_public_quote == 0
    metrics: dict[str, int | float] = {
        "known_false_public_attribution": false_public_attribution,
        "fabricated_public_quote": fabricated_public_quote,
        "correct_public_occurrences": correct_public,
        "correct_holds_or_abstentions": correct_holds,
        "false_holds": false_holds,
        "unresolved_cases": unresolved,
        "quote_span_exact_matches": quote_exact_count,
        "quote_span_measured_cases": len(quote_measured),
        "quote_span_exact_match_rate": (
            quote_exact_count / len(quote_measured) if quote_measured else 0.0
        ),
        "speaker_span_covered_cases": speaker_covered_count,
        "speaker_span_measured_cases": len(speaker_measured),
        "speaker_span_coverage_rate": (
            speaker_covered_count / len(speaker_measured) if speaker_measured else 0.0
        ),
        "context_review_escape_count": context_review_escape,
        "stale_provenance_escape_count": stale_provenance_escape,
    }
    return BenchmarkReport(
        schema_version=SCHEMA_VERSION,
        fixture_version=str(fixture["fixture_version"]),
        fixture_sha256=str(fixture["integrity"]["fixture_sha256"]),
        total_cases=len(results),
        failed_cases=failed,
        release_gate_passed=release_gate,
        benchmark_passed=release_gate and failed == 0,
        metrics=metrics,
        class_case_counts=class_counts,
        cases=results,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the DP-223 offline false-attribution/fabricated-quote benchmark"
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_benchmark(args.fixture)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        metrics = report.metrics
        print(
            "DP-223 benchmark: "
            f"cases={report.total_cases}, failed={report.failed_cases}, "
            f"false_attribution={metrics['known_false_public_attribution']}, "
            f"fabricated_quote={metrics['fabricated_public_quote']}, "
            f"release_gate={report.release_gate_passed}, "
            f"benchmark={report.benchmark_passed}"
        )
        for case in report.cases:
            state = "PASS" if case.passed else "FAIL"
            print(
                f"[{state}] {case.case_id} ({case.case_class}/{case.variant}): "
                f"{case.actual_publication_state} [{', '.join(case.reason_codes)}]"
            )
    return 0 if report.benchmark_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BenchmarkCaseResult",
    "BenchmarkReport",
    "DEFAULT_FIXTURE",
    "FixtureDriftError",
    "REQUIRED_CLASSES",
    "SCHEMA_VERSION",
    "load_fixture",
    "main",
    "run_benchmark",
]

"""DP-239 frozen reference comparison for private IT/DE translation risks.

No gold material is bundled. Source-only examples written by implementers are
controls, not independent adjudication. A trusted external verifier must
authenticate the separate annotations and rights before semantic rates count.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

from dichiarazioni_pubbliche.multilingual_derivation import PrivateTranslationDerivation
from dichiarazioni_pubbliche.wording_contract import TranslationReviewState, WordingType


GOLD_CONTRACT_VERSION = "dp239-independent-translation-gold-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RISKS = frozenset({
    "NEGATION_MISMATCH", "NUMBER_MISMATCH", "DATE_MISMATCH",
    "MODALITY_MISMATCH", "JUDICIAL_STATUS_MISMATCH", "ACTOR_ANCHOR_CHANGED",
    "ACTOR_ORDER_CHANGED", "REPORTED_SPEECH_MISMATCH", "QUOTE_MARKER_MISMATCH",
    "QUOTED_SPEAKER_ENDORSEMENT_UNVERIFIED",
})


TRANSLATION_MEANING_RISKS = _RISKS


@dataclass(frozen=True)
class TranslationGoldCase:
    case_id: str
    passage_id: str
    original_quote_sha256: str
    source_version_sha256: str
    translation_sha256: str
    original_language: str
    target_language: str
    original_wording_type: WordingType
    expected_alerts: tuple[str, ...]
    semantic_state: str  # FAITHFUL | MISMATCH | UNRESOLVED
    speaker_person_id: str | None
    reported_author_id: str | None
    endorsement: str  # ENDORSED | NOT_ENDORSED | UNKNOWN
    source_rights_receipt_sha256: str
    adjudication_receipt_sha256: str
    annotator_ids: tuple[str, ...]
    adjudicator_id: str
    reference_version: str


@dataclass(frozen=True)
class TranslationGoldManifest:
    generator_id: str
    model_id: str
    cases: tuple[TranslationGoldCase, ...]
    manifest_sha256: str
    contract_version: str = GOLD_CONTRACT_VERSION


@dataclass(frozen=True)
class TranslationRiskPrediction:
    case_id: str
    translation: PrivateTranslationDerivation
    # Downstream interpretation, independently supplied; translation itself
    # cannot assert the speaker endorsed a reported/quoted sentence.
    attributed_speaker_id: str | None = None
    attributed_reported_author_id: str | None = None
    predicted_endorsement: str = "UNKNOWN"


@dataclass(frozen=True)
class TranslationGoldReport:
    status: str
    manifest_sha256: str
    case_count: int
    matched_predictions: int
    unverified_gold_cases: int
    externally_admitted_cases: int
    detected_critical_alerts: int
    missed_critical_alerts: int
    unexpected_critical_alerts: int
    false_endorsements: int
    wrong_speakers: int
    mismatched_bindings: int
    risk_alert_recall: float | None
    release_eligible: bool = False
    publication_authority: bool = False


def manifest_hash(manifest: TranslationGoldManifest) -> str:
    if not isinstance(manifest, TranslationGoldManifest):
        raise ValueError("DP239_GOLD_MANIFEST_INVALID")
    value = asdict(manifest)
    value.pop("manifest_sha256", None)
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _validate(manifest: TranslationGoldManifest) -> None:
    if (not isinstance(manifest, TranslationGoldManifest)
            or manifest.contract_version != GOLD_CONTRACT_VERSION
            or not isinstance(manifest.cases, tuple)
            or not 1 <= len(manifest.cases) <= 256
            or not isinstance(manifest.generator_id, str)
            or not isinstance(manifest.model_id, str)
            or not manifest.generator_id or not manifest.model_id
            or manifest.generator_id == manifest.model_id
            or not isinstance(manifest.manifest_sha256, str)
            or not _SHA.fullmatch(manifest.manifest_sha256)
            or manifest_hash(manifest) != manifest.manifest_sha256):
        raise ValueError("DP239_GOLD_MANIFEST_INVALID")
    case_ids: set[str] = set()
    for row in manifest.cases:
        if not isinstance(row, TranslationGoldCase) or not isinstance(row.case_id, str) or not row.case_id:
            raise ValueError("DP239_GOLD_CASE_INVALID")
        if row.case_id in case_ids:
            raise ValueError("DP239_GOLD_CASE_DUPLICATE")
        case_ids.add(row.case_id)
        if (not isinstance(row.passage_id, str) or not row.passage_id
                or not isinstance(row.reference_version, str) or not row.reference_version
                or row.original_wording_type not in {WordingType.VERBATIM_ORIGINAL, WordingType.REPORTED_QUOTE}
                or row.semantic_state not in {"FAITHFUL", "MISMATCH", "UNRESOLVED"}
                or row.endorsement not in {"ENDORSED", "NOT_ENDORSED", "UNKNOWN"}
                or not isinstance(row.original_language, str)
                or not isinstance(row.target_language, str)
                or row.original_language.split("-", 1)[0] not in {"it", "de"}
                or row.target_language.split("-", 1)[0] != "it"
                or not isinstance(row.expected_alerts, tuple)
                or len(set(row.expected_alerts)) != len(row.expected_alerts)
                or set(row.expected_alerts) - _RISKS):
            raise ValueError("DP239_GOLD_CASE_INVALID")
        for digest in (row.original_quote_sha256, row.source_version_sha256,
                       row.translation_sha256, row.source_rights_receipt_sha256,
                       row.adjudication_receipt_sha256):
            if not isinstance(digest, str) or not _SHA.fullmatch(digest):
                raise ValueError("DP239_GOLD_HASH_INVALID")
        if (not isinstance(row.annotator_ids, tuple)
                or not 2 <= len(row.annotator_ids) <= 4
                or any(not isinstance(x, str) or not x for x in row.annotator_ids)
                or not isinstance(row.adjudicator_id, str) or not row.adjudicator_id
                or len(set((*row.annotator_ids, row.adjudicator_id))) != len(row.annotator_ids) + 1
                or manifest.generator_id in (*row.annotator_ids, row.adjudicator_id)
                or manifest.model_id in (*row.annotator_ids, row.adjudicator_id)):
            raise ValueError("DP239_GOLD_INDEPENDENCE_CONFLICT")
        if (row.original_wording_type is WordingType.REPORTED_QUOTE
                and row.endorsement == "ENDORSED"):
            raise ValueError("DP239_GOLD_REPORTED_ENDORSEMENT_UNSAFE")


def evaluate_translation_gold(
    manifest: TranslationGoldManifest,
    predictions: tuple[TranslationRiskPrediction, ...],
    *,
    external_attestation_check: Callable[[TranslationGoldCase], bool] | None = None,
) -> TranslationGoldReport:
    """Count risks only for externally admitted annotations.

    Verifier injection is an integration boundary, not evidence of independence
    on its own. Even all-admitted reports remain contract-only and private.
    """
    _validate(manifest)
    if not isinstance(predictions, tuple) or len(predictions) > 256:
        raise ValueError("DP239_GOLD_PREDICTIONS_INVALID")
    cases = {row.case_id: row for row in manifest.cases}
    observed: dict[str, TranslationRiskPrediction] = {}
    for item in predictions:
        if (not isinstance(item, TranslationRiskPrediction)
                or item.case_id not in cases or item.case_id in observed
                or not isinstance(item.translation, PrivateTranslationDerivation)
                or item.predicted_endorsement not in {"ENDORSED", "NOT_ENDORSED", "UNKNOWN"}):
            raise ValueError("DP239_GOLD_PREDICTION_INVALID")
        observed[item.case_id] = item
    eligible: set[str] = set()
    for row in manifest.cases:
        if external_attestation_check is None:
            continue
        try:
            if external_attestation_check(row) is True:
                eligible.add(row.case_id)
        except Exception:
            continue
    found = missed = extra = false_endorsements = wrong_speakers = binding_errors = 0
    for case_id in sorted(eligible):
        row, prediction = cases[case_id], observed.get(case_id)
        if prediction is None:
            missed += len(row.expected_alerts)
            continue
        derived = prediction.translation
        source = derived.original
        if (source.passage_id != row.passage_id
                or source.quote_sha256 != row.original_quote_sha256
                or source.source_version_sha256 != row.source_version_sha256
                or source.language != row.original_language
                or derived.target_language != row.target_language
                or derived.translated_text_sha256 != row.translation_sha256
                or source.source_wording_type != row.original_wording_type
                or source.speaker_person_id != row.speaker_person_id
                or derived.status != "HELD" or derived.method != "MACHINE"
                or derived.review_state != TranslationReviewState.NEEDS_REVIEW
                or derived.public_quote_eligible):
            binding_errors += 1
            missed += len(row.expected_alerts)
            continue
        actual = set(derived.signal_codes) & _RISKS
        expected = set(row.expected_alerts)
        found += len(expected & actual)
        missed += len(expected - actual)
        extra += len(actual - expected)
        wrong_speakers += prediction.attributed_speaker_id not in (None, row.speaker_person_id)
        wrong_speakers += prediction.attributed_reported_author_id not in (None, row.reported_author_id)
        false_endorsements += (prediction.predicted_endorsement == "ENDORSED"
                               and row.endorsement != "ENDORSED")
    return TranslationGoldReport(
        status="BLOCKED_EXTERNAL_GOLD" if len(eligible) != len(cases)
        else "CONTRACT_ONLY_PRIVATE_HOLD",
        manifest_sha256=manifest.manifest_sha256,
        case_count=len(cases), matched_predictions=len(observed),
        unverified_gold_cases=len(cases) - len(eligible),
        externally_admitted_cases=len(eligible),
        detected_critical_alerts=found, missed_critical_alerts=missed,
        unexpected_critical_alerts=extra, false_endorsements=false_endorsements,
        wrong_speakers=wrong_speakers, mismatched_bindings=binding_errors,
        risk_alert_recall=found / (found + missed) if found + missed else None,
    )


__all__ = [
    "GOLD_CONTRACT_VERSION", "TranslationGoldCase", "TranslationGoldManifest",
    "TranslationGoldReport", "TranslationRiskPrediction", "evaluate_translation_gold",
    "manifest_hash",
]

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class TranscriptStatus(StrEnum):
    RESOLVED = "RESOLVED"
    CANDIDATE_DISAGREEMENT = "CANDIDATE_DISAGREEMENT"
    TRANSCRIPT_UNCERTAIN = "TRANSCRIPT_UNCERTAIN"


class VerbatimEvidenceMethod(StrEnum):
    OFFICIAL_TRANSCRIPT = "OFFICIAL_TRANSCRIPT"
    HUMAN_AUDIO_VERIFIED = "HUMAN_AUDIO_VERIFIED"
    PLATFORM_CAPTION = "PLATFORM_CAPTION"
    MULTI_ASR_AGREEMENT = "MULTI_ASR_AGREEMENT"
    SINGLE_ASR = "SINGLE_ASR"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class TranscriptCandidate:
    candidate_id: str
    provider_id: str
    text: str
    start_ms: int
    end_ms: int
    source_kind: str


@dataclass(frozen=True)
class CanonicalTranscriptSegment:
    start_ms: int
    end_ms: int
    canonical_text: str
    status: TranscriptStatus
    candidate_ids: tuple[str, ...]
    sensitive_signatures: tuple[tuple[str, ...], ...]
    publication_blocked: bool
    verbatim_evidence_method: VerbatimEvidenceMethod
    verbatim_eligible: bool


_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?:\s*%|\s*(?:miliardi?|milioni?|euro))?", re.I)
_NEGATIONS = {
    "non",
    "mai",
    "nessuno",
    "nessuna",
    "nessun",
    "niente",
    "né",
}


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = re.sub(r"[^\w%€.,]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalized_number(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace(",", ".")).strip()


def sensitive_signature(
    text: str,
    *,
    gazetteer_terms: tuple[str, ...] = (),
) -> tuple[str, ...]:
    normalized = _normalize_text(text)
    signature: list[str] = []
    for match in _NUMBER.findall(normalized):
        signature.append(f"NUMBER:{_normalized_number(match)}")
    words = set(normalized.split())
    for negation in sorted(_NEGATIONS):
        if negation in words:
            signature.append(f"NEGATION:{negation}")
    for term in gazetteer_terms:
        term_norm = _normalize_text(term)
        if term_norm and term_norm in normalized:
            signature.append(f"TERM:{term_norm}")
    return tuple(signature)


def verbatim_evidence_method(
    candidates: tuple[TranscriptCandidate, ...],
) -> VerbatimEvidenceMethod:
    kinds = {str(candidate.source_kind or "").strip().upper() for candidate in candidates}
    if "HUMAN_AUDIO_VERIFIED" in kinds:
        return VerbatimEvidenceMethod.HUMAN_AUDIO_VERIFIED
    if "OFFICIAL_TRANSCRIPT" in kinds:
        return VerbatimEvidenceMethod.OFFICIAL_TRANSCRIPT
    if len(candidates) > 1:
        return VerbatimEvidenceMethod.MULTI_ASR_AGREEMENT
    only = next(iter(kinds), "")
    if only in {"PLATFORM_CAPTION", "YOUTUBE_AUTO_CAPTION"}:
        return VerbatimEvidenceMethod.PLATFORM_CAPTION
    if len(candidates) == 1:
        return VerbatimEvidenceMethod.SINGLE_ASR
    return VerbatimEvidenceMethod.UNVERIFIED


def reconcile_candidates(
    candidates: tuple[TranscriptCandidate, ...],
    *,
    gazetteer_terms: tuple[str, ...] = (),
) -> CanonicalTranscriptSegment:
    if not candidates:
        raise ValueError("at least one transcript candidate is required")

    start_ms = min(candidate.start_ms for candidate in candidates)
    end_ms = max(candidate.end_ms for candidate in candidates)
    normalized = tuple(_normalize_text(candidate.text) for candidate in candidates)
    signatures = tuple(
        sensitive_signature(candidate.text, gazetteer_terms=gazetteer_terms)
        for candidate in candidates
    )
    evidence_method = verbatim_evidence_method(candidates)
    verbatim_eligible = evidence_method in {
        VerbatimEvidenceMethod.OFFICIAL_TRANSCRIPT,
        VerbatimEvidenceMethod.HUMAN_AUDIO_VERIFIED,
    }

    # A single transcript candidate is useful for ordinary text, but it must
    # never silently become publication-grade truth when a material claim
    # depends on a sensitive token. This is the executable form of the
    # transcript policy: numbers, negations and configured names require an
    # independent candidate before publication can rely on them.
    if len(candidates) == 1 and signatures[0]:
        return CanonicalTranscriptSegment(
            start_ms=start_ms,
            end_ms=end_ms,
            canonical_text=candidates[0].text.strip(),
            status=TranscriptStatus.TRANSCRIPT_UNCERTAIN,
            candidate_ids=(candidates[0].candidate_id,),
            sensitive_signatures=signatures,
            publication_blocked=True,
            verbatim_evidence_method=evidence_method,
            verbatim_eligible=verbatim_eligible,
        )

    if len(set(normalized)) == 1:
        return CanonicalTranscriptSegment(
            start_ms=start_ms,
            end_ms=end_ms,
            canonical_text=candidates[0].text.strip(),
            status=TranscriptStatus.RESOLVED,
            candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
            sensitive_signatures=signatures,
            publication_blocked=False,
            verbatim_evidence_method=evidence_method,
            verbatim_eligible=verbatim_eligible,
        )

    if len(set(signatures)) > 1:
        return CanonicalTranscriptSegment(
            start_ms=start_ms,
            end_ms=end_ms,
            canonical_text=candidates[0].text.strip(),
            status=TranscriptStatus.TRANSCRIPT_UNCERTAIN,
            candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
            sensitive_signatures=signatures,
            publication_blocked=True,
            verbatim_evidence_method=evidence_method,
            verbatim_eligible=verbatim_eligible,
        )

    # We deliberately keep the first raw candidate rather than synthesizing a
    # third sentence. A later semantic reconciler may resolve harmless wording
    # differences, but it must do so explicitly and audibly.
    return CanonicalTranscriptSegment(
        start_ms=start_ms,
        end_ms=end_ms,
        canonical_text=candidates[0].text.strip(),
        status=TranscriptStatus.CANDIDATE_DISAGREEMENT,
        candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
        sensitive_signatures=signatures,
        publication_blocked=False,
        verbatim_evidence_method=evidence_method,
        verbatim_eligible=verbatim_eligible,
    )

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


PUBLICATION_SAFETY_VERSION = "publication-safety-v1"


class ProofState(StrEnum):
    PASSED = "PASSED"
    MISSING = "MISSING"
    STALE = "STALE"
    HOLD = "HOLD"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class WordingMode(StrEnum):
    DIRECT_QUOTE = "DIRECT_QUOTE"
    PARAPHRASE = "PARAPHRASE"
    TRANSLATION = "TRANSLATION"


@dataclass(frozen=True)
class PublicationSafetyInput:
    wording_mode: WordingMode | str
    media_quote: bool
    source_identity: ProofState | str
    exact_wording: ProofState | str
    transcript_verbatim: ProofState | str
    speaker_span: ProofState | str
    speech_origin: ProofState | str
    context_integrity: ProofState | str
    wording_integrity: ProofState | str
    identity_integrity: ProofState | str
    translation_review: ProofState | str
    evidence_suitability: ProofState | str
    citation_assurance: ProofState | str
    privacy: ProofState | str
    rights: ProofState | str
    verification_review: ProofState | str
    finding_review: ProofState | str
    challenge_hold: ProofState | str
    load_bearing_refs: Mapping[str, str]


@dataclass(frozen=True)
class PublicationSafetyResult:
    disposition: str
    reason_codes: tuple[str, ...]
    required_proofs: tuple[str, ...]
    binding_sha256: str
    profile_version: str = PUBLICATION_SAFETY_VERSION

    @property
    def eligible(self) -> bool:
        return self.disposition == "ELIGIBLE"


_COMMON_REQUIRED = (
    "source_identity",
    "speaker_span",
    "speech_origin",
    "context_integrity",
    "wording_integrity",
    "identity_integrity",
    "evidence_suitability",
    "citation_assurance",
    "privacy",
    "rights",
    "verification_review",
    "finding_review",
    "challenge_hold",
)


def _proof(value: ProofState | str, name: str) -> ProofState:
    try:
        return value if isinstance(value, ProofState) else ProofState(str(value))
    except ValueError as exc:
        raise ValueError(f"PUBLICATION_SAFETY_{name.upper()}_INVALID") from exc


def _wording_mode(value: WordingMode | str) -> WordingMode:
    try:
        return value if isinstance(value, WordingMode) else WordingMode(str(value))
    except ValueError as exc:
        raise ValueError("PUBLICATION_SAFETY_WORDING_MODE_INVALID") from exc


def _binding_sha256(refs: Mapping[str, str]) -> str:
    if not isinstance(refs, Mapping) or not refs:
        raise ValueError("PUBLICATION_SAFETY_LOAD_BEARING_REFS_REQUIRED")
    cleaned: dict[str, str] = {}
    for key, value in refs.items():
        name = str(key or "").strip()
        ref = str(value or "").strip()
        if not name or not ref:
            raise ValueError("PUBLICATION_SAFETY_LOAD_BEARING_REF_INVALID")
        if len(name) > 120 or len(ref) > 256:
            raise ValueError("PUBLICATION_SAFETY_LOAD_BEARING_REF_TOO_LONG")
        cleaned[name] = ref
    encoded = json.dumps(
        {
            "profile_version": PUBLICATION_SAFETY_VERSION,
            "refs": cleaned,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def required_proofs(
    wording_mode: WordingMode | str,
    *,
    media_quote: bool,
) -> tuple[str, ...]:
    mode = _wording_mode(wording_mode)
    fields = list(_COMMON_REQUIRED)
    if mode is WordingMode.DIRECT_QUOTE:
        fields.append("exact_wording")
        if media_quote:
            fields.append("transcript_verbatim")
    elif mode is WordingMode.TRANSLATION:
        fields.append("translation_review")
    return tuple(fields)


def _reason(name: str, state: ProofState) -> str:
    if name == "challenge_hold" and state is ProofState.PASSED:
        return ""
    if state is ProofState.MISSING:
        return f"MISSING_{name.upper()}"
    if state is ProofState.STALE:
        return f"STALE_{name.upper()}"
    if state is ProofState.HOLD:
        return f"HOLD_{name.upper()}"
    if state is ProofState.NOT_APPLICABLE:
        return f"MISSING_{name.upper()}"
    return ""


def evaluate_publication_safety(
    value: PublicationSafetyInput,
) -> PublicationSafetyResult:
    mode = _wording_mode(value.wording_mode)
    required = required_proofs(mode, media_quote=bool(value.media_quote))
    binding = _binding_sha256(value.load_bearing_refs)
    states = {
        name: _proof(getattr(value, name), name)
        for name in (
            "source_identity",
            "exact_wording",
            "transcript_verbatim",
            "speaker_span",
            "speech_origin",
            "context_integrity",
            "wording_integrity",
            "identity_integrity",
            "translation_review",
            "evidence_suitability",
            "citation_assurance",
            "privacy",
            "rights",
            "verification_review",
            "finding_review",
            "challenge_hold",
        )
    }

    reasons: list[str] = []
    for name in required:
        state = states[name]
        if state is ProofState.PASSED:
            continue
        code = _reason(name, state)
        if code:
            reasons.append(code)

    # A hold from privacy/rights/challenge remains a hold regardless of caller ordering
    # or otherwise complete verification. We expose codes only, never a confidence score.
    policy_hold = any(
        states[name] is ProofState.HOLD
        for name in ("privacy", "rights", "challenge_hold")
    )
    stale = any(states[name] is ProofState.STALE for name in required)
    missing = any(
        states[name] in {ProofState.MISSING, ProofState.NOT_APPLICABLE}
        for name in required
    )
    if reasons:
        disposition = (
            "POLICY_HOLD"
            if policy_hold
            else "STALE"
            if stale
            else "MISSING_PROOF"
            if missing
            else "HOLD"
        )
    else:
        disposition = "ELIGIBLE"
    return PublicationSafetyResult(
        disposition=disposition,
        reason_codes=tuple(reasons),
        required_proofs=required,
        binding_sha256=binding,
    )


def receipt_is_current(
    result: PublicationSafetyResult,
    current_load_bearing_refs: Mapping[str, str],
) -> bool:
    if result.profile_version != PUBLICATION_SAFETY_VERSION:
        return False
    return result.binding_sha256 == _binding_sha256(current_load_bearing_refs)


__all__ = [
    "PUBLICATION_SAFETY_VERSION",
    "ProofState",
    "PublicationSafetyInput",
    "PublicationSafetyResult",
    "WordingMode",
    "evaluate_publication_safety",
    "receipt_is_current",
    "required_proofs",
]

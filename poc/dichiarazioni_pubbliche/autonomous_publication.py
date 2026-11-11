"""DP #413: deterministic checks for fully automatic statement acceptance.

This is a policy boundary over independently acquired, immutable evidence and
model review receipts. It does not fetch sources, run models, or grant itself
authority to publish: production must replay the original evidence and
independently attest both agent decisions before activating a public version.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.autopublish_contract import load_autopublish_contract


# Owner decision 49 and the 2026-11-11 Gemini route correction invalidate
# receipts produced under the previous model allowlist.
POLICY_VERSION = "autonomous-publication-413-v7-owner49-gemini38"
# Owner correction 2026-11-11: Gemini usage must stay on Antigravity 3.8 Flash.
# Model strings alone never prove subscription, quota, or publication authority.
# Uncertain 2+1 records HOLD until three genuinely distinct models are authorized.
SUBSCRIPTION_REVIEW_MODEL = "antigravity/gemini-3.8-flash-tiered"
APPROVED_REVIEW_MODELS = frozenset({SUBSCRIPTION_REVIEW_MODEL})


def review_model_authorized(model_id: object) -> bool:
    """Require the exact canonical routed ID; no whitespace/case aliases."""
    return type(model_id) is str and model_id in APPROVED_REVIEW_MODELS


def independent_review_models_authorized(first_model: object, second_model: object) -> bool:
    """Require two different model identities, both approved by current policy."""
    if not (review_model_authorized(first_model) and review_model_authorized(second_model)):
        return False
    return first_model != second_model


MIN_ALIGNMENT_CONFIDENCE = 0.95
# Conservative short-excerpt limit; source-specific clearance decides permitted use.
MAX_EXCERPT_CHARS = 300
CHECKS = ("PROVENANCE", "WORDING", "SPEAKER", "PERSON", "RIGHTS_PRIVACY")
_SIGNAL_FAMILIES = {
    "official_channel": "source_metadata",
    "source_title": "source_metadata",
    "diarization": "audio_analysis",
    "source_caption": "editorial_caption",
    "source_text": "editorial_caption",
    "public_record": "external_record",
}
_SHA256 = set("0123456789abcdef")


@dataclass(frozen=True)
class SpeakerSignal:
    kind: str
    evidence_ref: str


@dataclass(frozen=True)
class AutonomousCandidate:
    record_id: str
    record_version_id: str
    source_version: str
    rights_attestation_sha256: str
    source_url: str
    source_kind: str
    snapshot_url: str
    snapshot_sha256: str
    source_text_sha256: str
    captured_at: str
    segment_start: float
    segment_end: float
    quote: str
    transcript_segment: str
    alignment_confidence: float | None
    speaker_id: str
    speaker_signals: tuple[SpeakerSignal, ...]
    public_role_source_url: str | None
    public_context_source_url: str | None
    person_is_minor: bool
    sensitive_third_party_data: bool
    privacy_cleared: bool
    privacy_citation_url: str
    rights_cleared: bool
    rights_citation_url: str
    source_length_chars: int
    contains_editorial_judgment: bool
    # Persisted uncertainty is bound to this candidate's versioned fingerprint.
    # It cannot be cleared by a model output; source authority must resolve it.
    uncertainty_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentReview:
    agent_id: str
    model_id: str
    evidence_sha256: str
    checked_stages: tuple[str, ...]
    accepted: bool
    provider: str | None = None
    provider_request_id: str | None = None
    returned_model: str | None = None
    prompt_sha256: str | None = None
    usage: dict[str, int] | None = None
    session_tag: str | None = None
    stage_citations: dict[str, list[str]] | None = None


@dataclass(frozen=True)
class AutonomousProofPacket:
    candidate: AutonomousCandidate
    primary: AgentReview
    independent: AgentReview | None = None
    third: AgentReview | None = None


@dataclass(frozen=True)
class AutonomousDecision:
    disposition: str
    reason_codes: tuple[str, ...]
    evidence_sha256: str
    policy_version: str = POLICY_VERSION

    @property
    def publishable(self) -> bool:
        return self.disposition == "PUBLISH"


def candidate_fingerprint(candidate: AutonomousCandidate) -> str:
    if not isinstance(candidate, AutonomousCandidate):
        raise TypeError("AUTONOMOUS_CANDIDATE_REQUIRED")
    return hashlib.sha256(
        json.dumps(
            {"version": POLICY_VERSION, "evidence": asdict(candidate)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _SHA256


def _public_https(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(
            (".local", ".internal", ".localhost", ".test", ".invalid")
        ):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host and all(host.split("."))
    except ValueError:
        return False


def _timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (TypeError, ValueError):
        return False


def _provenance(candidate: AutonomousCandidate) -> bool:
    try:
        start = float(candidate.segment_start)
        end = float(candidate.segment_end)
        return (
            bool(candidate.record_id.strip())
            and bool(candidate.record_version_id.strip())
            and bool(candidate.source_version.strip())
            and _sha256(candidate.rights_attestation_sha256)
            and candidate.source_kind in {"TIMED", "WRITTEN"}
            and _public_https(candidate.source_url)
            and _public_https(candidate.snapshot_url)
            and _sha256(candidate.snapshot_sha256)
            and _sha256(candidate.source_text_sha256)
            and _timestamp(candidate.captured_at)
            and (
                (candidate.source_kind == "TIMED" and 0 <= start < end < 86400 * 365)
                or (
                    candidate.source_kind == "WRITTEN"
                    and type(candidate.segment_start) is int
                    and type(candidate.segment_end) is int
                    and type(candidate.source_length_chars) is int
                    and 0 <= start < end <= candidate.source_length_chars
                )
            )
        )
    except (TypeError, ValueError, OverflowError, AttributeError):
        return False


def _wording(candidate: AutonomousCandidate) -> bool:
    try:
        if not candidate.quote.strip() or candidate.quote != candidate.transcript_segment:
            return False
        if candidate.source_kind == "WRITTEN":
            # The source-backed character selector is checked by the consumer;
            # a written document has no acoustic confidence to attest.
            return candidate.alignment_confidence is None
        if type(candidate.alignment_confidence) not in (int, float):
            return False
        confidence = float(candidate.alignment_confidence)
        return MIN_ALIGNMENT_CONFIDENCE <= confidence <= 1
    except (TypeError, ValueError, AttributeError):
        return False


def _speaker(candidate: AutonomousCandidate) -> bool:
    if not candidate.speaker_id.strip():
        return False
    families: set[str] = set()
    references: set[str] = set()
    for signal in candidate.speaker_signals:
        family = _SIGNAL_FAMILIES.get(signal.kind)
        if family and signal.evidence_ref and signal.evidence_ref.strip():
            families.add(family)
            references.add(signal.evidence_ref)
    # A caption and channel title can describe the same upload. Require an
    # independent audio analysis or external public identity record as well.
    return (
        len(families) >= 2 and len(references) >= 2
        and bool(families & {"audio_analysis", "external_record"})
    )


def _person(candidate: AutonomousCandidate) -> bool:
    return (
        candidate.person_is_minor is False
        and (
            _public_https(candidate.public_role_source_url)
            or _public_https(candidate.public_context_source_url)
        )
    )


def _rights_privacy(candidate: AutonomousCandidate) -> bool:
    try:
        length = len(candidate.quote)
        return (
            candidate.sensitive_third_party_data is False
            and candidate.privacy_cleared is True
            and _public_https(candidate.privacy_citation_url)
            and candidate.rights_cleared is True
            and _public_https(candidate.rights_citation_url)
            and candidate.contains_editorial_judgment is False
            and 0 < length <= MAX_EXCERPT_CHARS
            and type(candidate.source_length_chars) is int
            and candidate.source_length_chars > 0
        )
    except (TypeError, AttributeError):
        return False


def _review_accepts(review: AgentReview | None, binding: str) -> bool:
    return (
        isinstance(review, AgentReview)
        and type(review.agent_id) is str
        and bool(review.agent_id.strip())
        and review_model_authorized(review.model_id)
        and review.evidence_sha256 == binding
        and review.checked_stages == CHECKS
        and review.accepted is True
    )


def evaluate_autonomous_publication(
    candidate: AutonomousCandidate,
    primary: AgentReview | None,
    independent: AgentReview | None,
    *,
    active_challenge: bool = False,
    third: AgentReview | None = None,
) -> AutonomousDecision:
    """Apply owner decision 49: one editorial check, 2+1 on actual uncertainty.

    A new immutable capture or a correction changes the evidence fingerprint;
    stale approvals no longer count. Authenticated provider execution is checked
    by the consuming writer and durable packet reader, not by this pure function.
    """
    binding = candidate_fingerprint(candidate)
    try:
        load_autopublish_contract()
        config_error = False
    except ValueError:
        config_error = True
    checks = {
        "PROVENANCE": _provenance(candidate),
        "WORDING": _wording(candidate),
        "SPEAKER": _speaker(candidate),
        "PERSON": _person(candidate),
        "RIGHTS_PRIVACY": _rights_privacy(candidate),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    if config_error:
        reasons.append("AUTOPUBLISH_CONTRACT")
    if active_challenge:
        reasons.append("CHALLENGE_HOLD")
    uncertain = candidate.uncertainty_reasons
    if type(uncertain) is not tuple or any(
        type(code) is not str or not code.strip() or len(code) > 120
        for code in uncertain
    ):
        reasons.append("UNCERTAINTY_STATUS_INVALID")
        uncertain = ("UNKNOWN_UNCERTAINTY",)
    if not _review_accepts(primary, binding):
        reasons.append("EDITORIAL_REVIEW")
    if uncertain or independent is not None:
        if not (
            _review_accepts(independent, binding)
            and isinstance(primary, AgentReview)
            and independent_review_models_authorized(primary.model_id, independent.model_id)
            and primary.agent_id.strip().casefold() != independent.agent_id.strip().casefold()
        ):
            reasons.append("INDEPENDENT_REVIEW")
    if uncertain:
        if not (
            _review_accepts(third, binding)
            and isinstance(primary, AgentReview)
            and isinstance(independent, AgentReview)
            and third.model_id not in {primary.model_id, independent.model_id}
            and third.agent_id.strip().casefold() not in {
                primary.agent_id.strip().casefold(),
                independent.agent_id.strip().casefold(),
            }
        ):
            reasons.append("THIRD_AUDIT")
    elif third is not None:
        # A rejection supplied explicitly is still a HOLD, never ignored.
        if not _review_accepts(third, binding):
            reasons.append("THIRD_AUDIT")
    return AutonomousDecision(
        disposition="HOLD" if reasons else "PUBLISH",
        reason_codes=tuple(reasons),
        evidence_sha256=binding,
    )


__all__ = [
    "AgentReview",
    "AutonomousCandidate",
    "AutonomousDecision",
    "AutonomousProofPacket",
    "SpeakerSignal",
    "candidate_fingerprint",
    "independent_review_models_authorized",
    "review_model_authorized",
    "evaluate_autonomous_publication",
]

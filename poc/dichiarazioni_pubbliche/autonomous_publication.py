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


POLICY_VERSION = "autonomous-publication-413-v1"
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
    alignment_confidence: float
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


@dataclass(frozen=True)
class AgentReview:
    agent_id: str
    model_id: str
    evidence_sha256: str
    checked_stages: tuple[str, ...]
    accepted: bool


@dataclass(frozen=True)
class AutonomousProofPacket:
    candidate: AutonomousCandidate
    primary: AgentReview
    independent: AgentReview


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
            and 0 <= start < end
            and end < 86400 * 365
        )
    except (TypeError, ValueError, OverflowError, AttributeError):
        return False


def _wording(candidate: AutonomousCandidate) -> bool:
    try:
        if type(candidate.alignment_confidence) not in (int, float):
            return False
        confidence = float(candidate.alignment_confidence)
        return (
            bool(candidate.quote.strip())
            and candidate.quote == candidate.transcript_segment
            and MIN_ALIGNMENT_CONFIDENCE <= confidence <= 1
        )
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


def evaluate_autonomous_publication(
    candidate: AutonomousCandidate,
    primary: AgentReview | None,
    independent: AgentReview | None,
    *,
    active_challenge: bool = False,
) -> AutonomousDecision:
    """Publish only when all checks and two different, current agent reviews agree.

    A new immutable capture or a correction changes the evidence fingerprint;
    stale approvals no longer count. The consumer retries when its inputs change.
    """
    binding = candidate_fingerprint(candidate)
    checks = {
        "PROVENANCE": _provenance(candidate),
        "WORDING": _wording(candidate),
        "SPEAKER": _speaker(candidate),
        "PERSON": _person(candidate),
        "RIGHTS_PRIVACY": _rights_privacy(candidate),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    if active_challenge:
        reasons.append("CHALLENGE_HOLD")
    if (
        primary is None
        or independent is None
        or not isinstance(primary, AgentReview)
        or not isinstance(independent, AgentReview)
        or not primary.agent_id.strip()
        or not independent.agent_id.strip()
        or primary.agent_id.strip().casefold() == independent.agent_id.strip().casefold()
        or not primary.model_id.strip()
        or not independent.model_id.strip()
        or primary.model_id.strip().casefold() == independent.model_id.strip().casefold()
        or primary.evidence_sha256 != binding
        or independent.evidence_sha256 != binding
        or primary.checked_stages != CHECKS
        or independent.checked_stages != CHECKS
        or primary.accepted is not True
        or independent.accepted is not True
    ):
        reasons.append("INDEPENDENT_REVIEW")
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
    "evaluate_autonomous_publication",
]

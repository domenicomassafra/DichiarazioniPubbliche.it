"""DP-468 durable, fail-closed authorities for public Statement v3.

Authority events bind an exact statement version to source and quote hashes.
Rights grants are revocable by appending a later RIGHTS event. Privacy and
retention decisions are separate persisted gates. Challenge requests and
their state transitions are private append-only ledgers.

This module never creates an approval from a local journal claim. Model review
gates must match a current JournalReviewPacketReader packet; rights, privacy and
retention events require an independently verified durable review reference.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from .autonomous_publication import (
    AgentReview, AutonomousCandidate, AutonomousProofPacket, CHECKS,
    candidate_fingerprint, independent_review_models_authorized, review_model_authorized,
)
from .claim_runtime import matches_returned_model

_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_AUTHORITY_KINDS = (
    "RIGHTS", "PRIVACY", "RETENTION", "ATTRIBUTION",
    "CONTEXT", "WORDING", "PUBLICATION",
)
_MODEL_REVIEW_KINDS = frozenset({"ATTRIBUTION", "CONTEXT", "WORDING"})
_CHALLENGE_STATES = frozenset({
    "OPEN", "TRIAGED", "NEEDS_INFO", "UPHELD", "CORRECTED", "RETRACTED",
    "REJECTED", "WITHDRAWN", "CLOSED_NO_CHANGE",
})
_CHALLENGE_CLEAR_STATES = frozenset({"REJECTED", "WITHDRAWN", "CLOSED_NO_CHANGE"})
_CHALLENGE_TERMINAL_STATES = _CHALLENGE_CLEAR_STATES | frozenset({"CORRECTED", "RETRACTED"})
_CHALLENGE_TRANSITIONS = {
    "OPEN": frozenset({
        "TRIAGED", "NEEDS_INFO", "UPHELD", "REJECTED", "WITHDRAWN",
        "CLOSED_NO_CHANGE",
    }),
    "TRIAGED": frozenset({
        "NEEDS_INFO", "UPHELD", "CORRECTED", "RETRACTED", "REJECTED",
        "WITHDRAWN", "CLOSED_NO_CHANGE",
    }),
    "NEEDS_INFO": frozenset({
        "TRIAGED", "UPHELD", "CORRECTED", "RETRACTED", "REJECTED",
        "WITHDRAWN", "CLOSED_NO_CHANGE",
    }),
    "UPHELD": frozenset({"CORRECTED", "RETRACTED"}),
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(code)
    return value


def _sha(value: object, code: str) -> str:
    parsed = _text(value, code)
    if _SHA256.fullmatch(parsed) is None:
        raise ValueError(code)
    return parsed


def _iso_datetime(value: object, code: str) -> str:
    parsed = _text(value, code)
    try:
        moment = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(code) from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(code)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _valid_https_url(value: object) -> bool:
    if type(value) is not str:
        return False
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        return (
            parsed.scheme == "https" and bool(host)
            and parsed.username is None and parsed.password is None
            and parsed.fragment == "" and parsed.port in (None, 443)
            and host not in {"localhost", "localhost.localdomain"}
            and not host.endswith((".local", ".internal", ".localhost", ".test", ".invalid"))
            and "." in host
        )
    except ValueError:
        return False


_BINDING_KEYS = frozenset({
    "statement_id", "version_id", "content_id", "source_version",
    "source_sha256", "quote_sha256", "person_id", "speaker_name",
    "statement_date", "span_start", "span_end", "source_url", "source_title",
})


def validate_statement_binding(binding: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(binding, Mapping) or set(binding) != _BINDING_KEYS:
        raise ValueError("DP468_STATEMENT_BINDING_INVALID")
    result = dict(binding)
    for key in (
        "statement_id", "version_id", "content_id", "source_version",
        "person_id", "speaker_name", "source_title",
    ):
        _text(result[key], "DP468_STATEMENT_BINDING_INVALID")
    _sha(result["source_sha256"], "DP468_STATEMENT_BINDING_INVALID")
    _sha(result["quote_sha256"], "DP468_STATEMENT_BINDING_INVALID")
    if (type(result["span_start"]) is not int or type(result["span_end"]) is not int
            or result["span_start"] < 0 or result["span_end"] <= result["span_start"]):
        raise ValueError("DP468_STATEMENT_BINDING_INVALID")
    if (type(result["statement_date"]) is not str
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", result["statement_date"]) is None
            or not _valid_https_url(result["source_url"])):
        raise ValueError("DP468_STATEMENT_BINDING_INVALID")
    try:
        datetime.strptime(result["statement_date"], "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("DP468_STATEMENT_BINDING_INVALID") from exc
    return result


def _review_evidence(
    packet: AutonomousProofPacket, binding: Mapping[str, object],
) -> dict[str, object]:
    if (not isinstance(packet, AutonomousProofPacket)
            or not isinstance(packet.candidate, AutonomousCandidate)):
        raise ValueError("DP468_MODEL_REVIEW_PACKET_REQUIRED")
    candidate = packet.candidate
    parsed_binding = validate_statement_binding(binding)
    try:
        evidence_sha256 = candidate_fingerprint(candidate)
        quote_sha256 = hashlib.sha256(candidate.quote.encode("utf-8")).hexdigest()
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("DP468_MODEL_REVIEW_CANDIDATE_INVALID") from exc
    if (
        candidate.record_id != parsed_binding["statement_id"]
        or candidate.record_version_id != parsed_binding["version_id"]
        or candidate.source_version != parsed_binding["source_version"]
        or candidate.source_text_sha256 != parsed_binding["source_sha256"]
        or quote_sha256 != parsed_binding["quote_sha256"]
        or candidate.speaker_id != parsed_binding["person_id"]
        or candidate.source_url != parsed_binding["source_url"]
        or candidate.source_kind != "WRITTEN"
        or type(candidate.segment_start) is not int
        or type(candidate.segment_end) is not int
        or candidate.segment_start != parsed_binding["span_start"]
        or candidate.segment_end != parsed_binding["span_end"]
        or candidate.alignment_confidence is not None
        or type(candidate.source_length_chars) is not int
        or candidate.source_length_chars < candidate.segment_end
        or not candidate.quote.strip()
        or len(candidate.quote) > 300
        or candidate.person_is_minor is not False
        or candidate.sensitive_third_party_data is not False
        or candidate.privacy_cleared is not True
        or candidate.rights_cleared is not True
        or candidate.contains_editorial_judgment is not False
        or not _valid_https_url(candidate.rights_citation_url)
        or not _valid_https_url(candidate.privacy_citation_url)
    ):
        raise ValueError("DP468_MODEL_REVIEW_CANDIDATE_BINDING_MISMATCH")

    primary, independent = packet.primary, packet.independent
    if not isinstance(primary, AgentReview) or not isinstance(independent, AgentReview):
        raise ValueError("DP468_MODEL_REVIEW_PACKET_REQUIRED")
    primary_agent = _text(primary.agent_id, "DP468_MODEL_REVIEW_RECEIPT_INVALID")
    independent_agent = _text(independent.agent_id, "DP468_MODEL_REVIEW_RECEIPT_INVALID")
    if (not independent_review_models_authorized(
            primary.model_id, independent.model_id,
        ) or primary_agent.casefold() == independent_agent.casefold()):
        raise ValueError("DP468_MODEL_REVIEW_NOT_INDEPENDENT")

    receipts: list[dict[str, object]] = []
    for review in (primary, independent):
        _text(review.agent_id, "DP468_MODEL_REVIEW_RECEIPT_INVALID")
        if (
            review.evidence_sha256 != evidence_sha256
            or review.provider != "omniroute"
            or not matches_returned_model(review.model_id, review.returned_model)
            or review.accepted is not True
            or review.checked_stages != CHECKS
        ):
            raise ValueError("DP468_MODEL_REVIEW_RECEIPT_INVALID")
        request_id = _text(
            review.provider_request_id, "DP468_MODEL_REVIEW_RECEIPT_INVALID",
        )
        prompt_sha256 = _sha(
            review.prompt_sha256, "DP468_MODEL_REVIEW_RECEIPT_INVALID",
        )
        usage = review.usage
        if (not isinstance(usage, Mapping)
                or type(usage.get("prompt_tokens")) is not int
                or usage["prompt_tokens"] <= 0
                or type(usage.get("completion_tokens")) is not int
                or usage["completion_tokens"] < 0):
            raise ValueError("DP468_MODEL_REVIEW_RECEIPT_INVALID")
        receipts.append({
            "agent_id": review.agent_id,
            "model_id": review.model_id,
            "provider": review.provider,
            "provider_request_id": request_id,
            "returned_model": review.returned_model,
            "prompt_sha256": prompt_sha256,
            "usage": {
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
            },
            "accepted": True,
            "checked_stages": list(CHECKS),
            "evidence_sha256": evidence_sha256,
        })
    if receipts[0]["provider_request_id"] == receipts[1]["provider_request_id"]:
        raise ValueError("DP468_MODEL_REVIEW_NOT_INDEPENDENT")
    return {
        "evidence_sha256": evidence_sha256,
        "primary": receipts[0],
        "independent": receipts[1],
    }


def _validate_release_dispositions(
    review_evidence: Mapping[str, object],
    model_evidence: Mapping[str, object],
) -> None:
    if (not isinstance(review_evidence, Mapping)
            or not isinstance(review_evidence.get("evidence_refs"), list)
            or not review_evidence["evidence_refs"]
            or any(type(ref) is not str or not ref.strip()
                   for ref in review_evidence["evidence_refs"])):
        raise ValueError("DP468_EXTERNAL_AUTHORITY_REVIEW_REQUIRED")
    dispositions = review_evidence.get("release_dispositions")
    if not isinstance(dispositions, list) or len(dispositions) != 3:
        raise ValueError("DP468_THREE_RELEASE_DISPOSITIONS_REQUIRED")
    expected_roles = ("PRIMARY_REVIEW", "INDEPENDENT_REVIEW", "THIRD_AUDIT")
    expected_receipts = (
        model_evidence.get("primary"), model_evidence.get("independent"),
    )
    agents: set[str] = set()
    models: set[str] = set()
    requests: set[str] = set()
    evidence_sha256 = model_evidence.get("evidence_sha256")
    for index, disposition in enumerate(dispositions):
        if not isinstance(disposition, Mapping):
            raise ValueError("DP468_RELEASE_DISPOSITION_INVALID")
        required = {
            "role", "agent_id", "model_id", "provider", "provider_request_id",
            "returned_model", "prompt_sha256", "usage", "accepted",
            "checked_stages", "evidence_sha256",
        }
        if set(disposition) != required or disposition.get("role") != expected_roles[index]:
            raise ValueError("DP468_RELEASE_DISPOSITION_INVALID")
        agent = _text(disposition.get("agent_id"), "DP468_RELEASE_DISPOSITION_INVALID")
        model = _text(disposition.get("model_id"), "DP468_RELEASE_DISPOSITION_INVALID")
        request = _text(
            disposition.get("provider_request_id"), "DP468_RELEASE_DISPOSITION_INVALID",
        )
        if (
            disposition.get("provider") != "omniroute"
            or not matches_returned_model(model, disposition.get("returned_model"))
            or disposition.get("accepted") is not True
            or disposition.get("checked_stages") != list(CHECKS)
            or disposition.get("evidence_sha256") != evidence_sha256
            or not review_model_authorized(model)
        ):
            raise ValueError("DP468_RELEASE_DISPOSITION_INVALID")
        _sha(disposition.get("prompt_sha256"), "DP468_RELEASE_DISPOSITION_INVALID")
        usage = disposition.get("usage")
        if (not isinstance(usage, Mapping)
                or type(usage.get("prompt_tokens")) is not int
                or usage["prompt_tokens"] <= 0
                or type(usage.get("completion_tokens")) is not int
                or usage["completion_tokens"] < 0):
            raise ValueError("DP468_RELEASE_DISPOSITION_USAGE_INVALID")
        if agent.casefold() in {value.casefold() for value in agents}:
            raise ValueError("DP468_RELEASE_DISPOSITIONS_NOT_INDEPENDENT")
        if model in models or request in requests:
            raise ValueError("DP468_RELEASE_DISPOSITIONS_NOT_INDEPENDENT")
        agents.add(agent)
        models.add(model)
        requests.add(request)
        if index < 2:
            expected = expected_receipts[index]
            if not isinstance(expected, Mapping) or any(
                disposition.get(key) != expected.get(key)
                for key in (
                    "agent_id", "model_id", "provider", "provider_request_id",
                    "returned_model", "prompt_sha256", "usage", "accepted",
                    "checked_stages", "evidence_sha256",
                )
            ):
                raise ValueError("DP468_RELEASE_DISPOSITION_REVIEW_MISMATCH")


def _model_review_event_id(kind: str, evidence: Mapping[str, object]) -> str:
    return "public-statement-review:" + _digest({"authority_kind": kind, "evidence": evidence})

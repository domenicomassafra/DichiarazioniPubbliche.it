"""DP-468 release dispositions for single-editor and uncertain 2+1 paths."""

from __future__ import annotations
from typing import Mapping

from .autonomous_publication import CHECKS, review_model_authorized
from .claim_runtime import matches_returned_model
from .public_statement_authority_common import _text, _sha


def validate_release_dispositions(
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
    requires_escalation = model_evidence.get("requires_escalation") is True
    if (not isinstance(dispositions, list)
            or len(dispositions) != (3 if requires_escalation else 1)):
        raise ValueError("DP468_RELEASE_DISPOSITIONS_REQUIRED")
    expected_roles = (
        ("PRIMARY_REVIEW", "INDEPENDENT_REVIEW", "THIRD_AUDIT")
        if len(dispositions) == 3 else ("PRIMARY_REVIEW",)
    )
    expected_receipts = (
        model_evidence.get("primary"), model_evidence.get("independent"),
        model_evidence.get("third"),
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

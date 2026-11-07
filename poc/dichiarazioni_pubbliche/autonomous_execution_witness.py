"""DP-413: gate public promotions on independently witnessed provider requests."""

from __future__ import annotations

from typing import Callable

from dichiarazioni_pubbliche.autonomous_publication import AgentReview
from dichiarazioni_pubbliche.claim_runtime import matches_returned_model


def review_execution_witnessed(
    review: AgentReview | None,
    verify_provider_execution: Callable[[AgentReview], bool] | None,
) -> bool:
    """Validate receipt shape then consult a separate authenticated gateway ledger.

    The verifier must independently check the DP key, connection, subscription,
    paid-route exclusion, model, prompt/evidence binding and actual usage.
    Neither a local receipt nor this shape check authenticates an execution.
    """
    if not isinstance(review, AgentReview) or not callable(verify_provider_execution):
        return False
    usage = review.usage
    if (
        review.provider != "omniroute"
        or type(review.provider_request_id) is not str
        or not review.provider_request_id.strip()
        or not matches_returned_model(review.model_id, review.returned_model)
        or type(review.prompt_sha256) is not str
        or len(review.prompt_sha256) != 64
        or any(char not in "0123456789abcdef" for char in review.prompt_sha256)
        or not isinstance(usage, dict)
        or type(usage.get("prompt_tokens")) is not int
        or usage["prompt_tokens"] <= 0
        or type(usage.get("completion_tokens")) is not int
        or usage["completion_tokens"] < 0
    ):
        return False
    try:
        return verify_provider_execution(review) is True
    except Exception:
        return False


__all__ = ["review_execution_witnessed"]

"""Bounded USD cost estimation and operation classification (DP-506/514).

Pure conversion only: no provider request, dispatch, bill, FX or allowance is
authorized here. Cost policy imports and re-exports these existing symbols.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Mapping

# --- Unit economics --------------------------------------------------------
#
# These are *policy inputs*, not market facts. The documented ASR price
# (USD 0.04/audio-hour) was verified upstream on 2026-09-22; claim extraction
# is priced from the operator-configured ceiling, because the actual route
# cost is an operator decision, not a constant. Changing a number here changes
# an operational expectation, so each rate carries the provenance of its value.

USD_PER_AUDIO_HOUR = 0.04
USD_PER_EVIDENCE_REQUEST = 0.0  # evidence retrieval is free, metered by rate limit

RATE_PROVENANCE: Mapping[str, str] = {
    "USD_PER_AUDIO_HOUR": (
        "https://console.groq.com/docs/speech-to-text, verified 2026-09-22; "
        "policy input, not a permanent guarantee"
    ),
    "USD_PER_EVIDENCE_REQUEST": "official evidence retrieval is free; rate-limited instead",
}

# A lane is only allowed to spend if its unit rate is known. Unknown rate ==
# blocked, not free.
PAID_OPERATIONS = ("AUDIO_TRANSCRIPTION", "CLAIM_EXTRACT")

ZERO_COST_OPERATIONS = (
    "TRANSCRIPT_CAPTION",
    "EVIDENCE_FETCH_URL",
    "EVIDENCE_QUERY_OFFICIAL",
    "PUBLIC_PROJECTION_BUILD",
)


def _ceil_paid_estimate_usd(amount: Decimal) -> float | None:
    """Never turn a positive paid estimate into a zero-dollar quote."""
    if not amount.is_finite() or amount < 0:
        return None
    try:
        return float(amount.quantize(Decimal("0.000001"), rounding=ROUND_CEILING))
    except (InvalidOperation, OverflowError):
        return None


def estimate_cost_usd(
    operation: str,
    *,
    input_seconds: float | None = None,
    input_bytes: int | None = None,
    request_count: int = 1,
    max_usd_per_1k_total_tokens: float | None = None,
    total_tokens: int | None = None,
) -> float | None:
    """Best-effort pre-execution cost estimate.

    Returns ``None`` -- meaning *unpriced*, i.e. the caller must block -- when
    the operation has a real marginal cost and the inputs needed to price it
    are missing. It never guesses.
    """
    op = str(operation or "").strip()

    if op in ZERO_COST_OPERATIONS:
        return 0.0

    if op == "AUDIO_TRANSCRIPTION":
        if input_seconds is None or isinstance(input_seconds, bool):
            return None
        try:
            seconds = Decimal(str(input_seconds))
            return _ceil_paid_estimate_usd(
                (seconds / Decimal("3600")) * Decimal(str(USD_PER_AUDIO_HOUR))
            )
        except (InvalidOperation, ValueError, TypeError):
            return None

    if op == "CLAIM_EXTRACT":
        if (max_usd_per_1k_total_tokens is None or total_tokens is None
                or isinstance(max_usd_per_1k_total_tokens, bool)
                or isinstance(total_tokens, bool)):
            return None
        try:
            return _ceil_paid_estimate_usd(
                Decimal(str(total_tokens)) *
                Decimal(str(max_usd_per_1k_total_tokens)) / Decimal("1000")
            )
        except (InvalidOperation, ValueError, TypeError):
            return None

    if op in PAID_OPERATIONS:
        return None

    # An unknown operation is not free. This is the fail-closed default.
    return None

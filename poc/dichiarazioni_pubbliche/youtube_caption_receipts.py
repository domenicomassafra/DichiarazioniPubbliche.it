"""Contract for source-backed public YouTube caption receipt writes."""

from __future__ import annotations

from typing import Any

from dichiarazioni_pubbliche.platform_transcript import CaptionProbe


def caption_source_kind(probe: CaptionProbe) -> str:
    return "YOUTUBE_MANUAL_CAPTION" if probe.kind == "manual_caption" else "YOUTUBE_AUTO_CAPTION"


def segment_rows(capture: Any) -> list[dict[str, Any]]:
    return [
        {
            "segment_index": segment.segment_index,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "text": segment.text,
            "metadata": {},
        }
        for segment in capture.segments
    ]


def record_caption_receipt(store: Any, **kwargs: Any) -> str:
    """Forbid charging a model-less public yt-dlp caption attempt at its writer."""
    if (
        kwargs.get("provider_id") != "youtube"
        or kwargs.get("model_id") is not None
        or kwargs.get("operation") not in {"CAPTION_PROBE", "CAPTION_CAPTURE"}
        or kwargs.get("estimated_cost_usd") != 0
        or kwargs.get("measured_cost_usd") not in (None, 0)
        or kwargs.get("billing_basis") not in (None, "ZERO_COST")
    ):
        raise ValueError("YOUTUBE_CAPTION_MONETARY_COST_FORBIDDEN")
    receipt = kwargs.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("YOUTUBE_CAPTION_RECEIPT_INVALID")
    kwargs["billing_basis"] = "ZERO_COST"
    kwargs["receipt"] = {
        **receipt,
        "access_path": "YT_DLP_PUBLIC_CAPTION",
        "billing_evidence_version": "youtube-caption-yt-dlp-v1",
        "youtube_data_api_v3_quota_units": 0,
        "provider_marginal_cost_usd": "0.000000",
        "local_energy_basis": "UNKNOWN",
    }
    return store.record_receipt(**kwargs)

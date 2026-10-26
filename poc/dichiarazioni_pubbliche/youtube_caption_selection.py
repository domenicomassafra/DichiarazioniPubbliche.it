"""Keep provider ordering and provenance fallbacks in one caption selection seam."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from dichiarazioni_pubbliche import dstack_free_captions
from dichiarazioni_pubbliche.youtube_caption_fallback import yt_dlp_caption_unavailable

if TYPE_CHECKING:
    from dichiarazioni_pubbliche.platform_transcript import (
        CaptionCapture, CaptionProbe, YouTubeResolver,
    )


def capture_caption(
    resolver: YouTubeResolver, video_url: str, probe: CaptionProbe,
) -> CaptionCapture:
    from dichiarazioni_pubbliche.platform_transcript import PlatformAccessRestricted

    free_capture, free_failure_reason = dstack_free_captions.attempt_capture(
        video_url, probe, catalog_path=resolver.free_caption_catalog_path,
        validate_video_id=resolver._youtube_video_id,
    )
    if free_capture is not None:
        return free_capture
    if resolver.use_transcript_api_secondary:
        resolver._youtube_video_id(video_url)
    fallback_reason = ""
    if resolver.use_transcript_api:
        try:
            capture = resolver._capture_transcript_api(video_url, probe)
            if free_failure_reason:
                return replace(capture, provenance={
                    **capture.provenance, "prior_method": "yttranscript.dev",
                    "fallback_reason": "FREE_CAPTION_UNAVAILABLE",
                    "free_attempt_result": free_failure_reason,
                })
            return capture
        except PlatformAccessRestricted:
            raise
        except Exception as exc:
            # Only ordinary adapter/runtime failures permit native recovery.
            fallback_reason = type(exc).__name__
    try:
        capture = resolver._capture_yt_dlp_caption(video_url, probe)
    except PlatformAccessRestricted:
        raise
    except Exception as exc:
        reason = yt_dlp_caption_unavailable(exc)
        if not resolver.use_transcript_api_secondary or reason is None:
            raise
        recovered = resolver._capture_transcript_api(video_url, probe)
        return replace(recovered, provenance={
            **recovered.provenance, "prior_method": "yt-dlp",
            "prior_method_version": "unspecified-external",
            "fallback_reason": reason,
            **({"preceding_free_method": "yttranscript.dev",
                "free_attempt_result": free_failure_reason}
               if free_failure_reason else {}),
        })
    if free_failure_reason:
        return replace(capture, provenance={
            **capture.provenance,
            "prior_method": "yttranscript.dev",
            "fallback_reason": "FREE_CAPTION_UNAVAILABLE",
            "free_attempt_result": free_failure_reason,
        })
    if fallback_reason:
        return replace(capture, provenance={
            **capture.provenance, "prior_method": "youtube-transcript-api",
            "prior_method_version": "1.2.4",
            "fallback_reason": fallback_reason,
        })
    return capture

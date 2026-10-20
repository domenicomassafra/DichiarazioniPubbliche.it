"""Fail-closed classification for the opt-in yt-dlp -> transcript API path.

No request is made here. Only a known missing/malformed *caption* can trigger
another adapter; platform access decisions always stop acquisition.
"""

from __future__ import annotations

_ACCESS_DENIALS = (
    "http error 401", "http error 403", "http error 429", "http error 451",
    "http 401", "http 403", "http 429", "http 451",
    "401 unauthorized", "403 forbidden", "429 too many requests",
    "access denied", "forbidden", "unauthorized", "too many requests",
    "rate limit", "request blocked", "ip block", "blocked your ip", "sign in", "sign-in",
    "log in", "login", "cookies", "private video", "members-only",
    "members only", "age-restrict", "consent", "captcha", "challenge",
    "bot detection", "confirm you're not a bot", "po token", "po_token",
    "unavailable in your country", "geo-restrict", "video unavailable",
    "this video is unavailable", "requested format is not available due to restrictions",
)

_MISSING_CAPTIONS = (
    "no subtitles", "no subtitle", "no captions", "no caption",
    "subtitle not available", "subtitles not available",
    "caption not available", "captions not available",
    "requested subtitle format", "expected one json3 caption, found 0",
    "json3 caption contains no usable segments",
)


def yt_dlp_access_denied(message: str) -> bool:
    """Conservative detector for access refusals in yt-dlp diagnostics."""
    lowered = message.casefold()
    return any(marker in lowered for marker in _ACCESS_DENIALS)


def yt_dlp_caption_unavailable(exc: Exception) -> str | None:
    """Return a safe reason only when another client may be attempted."""
    if isinstance(exc, FileNotFoundError):
        return "YT_DLP_CLIENT_MISSING"
    if isinstance(exc, (RuntimeError, ValueError)):
        message = str(exc).casefold()
        if not yt_dlp_access_denied(message) and any(
            marker in message for marker in _MISSING_CAPTIONS
        ):
            return "YT_DLP_CAPTION_UNAVAILABLE"
    return None


__all__ = ["yt_dlp_access_denied", "yt_dlp_caption_unavailable"]

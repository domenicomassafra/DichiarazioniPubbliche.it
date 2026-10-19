"""Optional bounded public-caption client; no cookies or proxy bypass."""
from __future__ import annotations

from importlib.metadata import version
from time import monotonic
from urllib.parse import urlsplit


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_REQUEST_SECONDS = 20


class TranscriptApiRedirectDenied(RuntimeError):
    """Do not follow a platform redirect to consent/login or a foreign host."""


def new_transcript_client():
    """Construct the pinned donor with bounded connections and response reads."""
    from requests import Session
    from youtube_transcript_api import YouTubeTranscriptApi

    if version("youtube-transcript-api") != "1.2.4":
        raise RuntimeError("TRANSCRIPT_API_VERSION_UNSUPPORTED")

    class BoundedCaptionSession(Session):
        def request(self, method, url, **kwargs):
            # The donor also fetches caption URLs taken from YouTube metadata.
            # Reject a foreign host or redirect before any outbound request.
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https" or parsed.hostname != "www.youtube.com"
                or parsed.username or parsed.password or parsed.port not in (None, 443)
            ):
                raise TranscriptApiRedirectDenied("TRANSCRIPT_API_URL_NOT_ALLOWED")
            kwargs["timeout"] = (3.0, 8.0)
            kwargs["allow_redirects"] = False
            kwargs["stream"] = True
            deadline = monotonic() + _MAX_REQUEST_SECONDS
            response = super().request(method, url, **kwargs)
            try:
                if 300 <= response.status_code < 400:
                    raise TranscriptApiRedirectDenied("TRANSCRIPT_API_REDIRECT_DENIED")
                chunks = []
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES or monotonic() > deadline:
                        raise ValueError("TRANSCRIPT_API_RESPONSE_LIMIT_EXCEEDED")
                    chunks.append(chunk)
                # requests Response exposes .text/.json from its cached content;
                # leave the pinned donor's response interface unchanged.
                response._content = b"".join(chunks)
                response._content_consumed = True
                return response
            finally:
                response.close()

    session = BoundedCaptionSession()
    session.trust_env = False  # No inherited auth/proxy environment.
    return YouTubeTranscriptApi(http_client=session)

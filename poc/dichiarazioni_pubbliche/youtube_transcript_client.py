"""Optional bounded public-caption client; no cookies or proxy bypass."""
from __future__ import annotations

from importlib.metadata import version


def new_transcript_client():
    """Construct the pinned donor with bounded connections and response reads."""
    from requests import Session
    from youtube_transcript_api import YouTubeTranscriptApi

    if version("youtube-transcript-api") != "1.2.4":
        raise RuntimeError("TRANSCRIPT_API_VERSION_UNSUPPORTED")

    class BoundedCaptionSession(Session):
        def request(self, method, url, **kwargs):
            kwargs["timeout"] = (3.0, 8.0)
            return super().request(method, url, **kwargs)

    session = BoundedCaptionSession()
    session.trust_env = False  # No inherited auth/proxy environment.
    return YouTubeTranscriptApi(http_client=session)

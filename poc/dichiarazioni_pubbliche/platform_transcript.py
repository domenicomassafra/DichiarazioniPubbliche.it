from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from dichiarazioni_pubbliche.caption_adapter import (
    CaptionSegment, parse_transcript_api_snippets, parse_youtube_json3,
)
from dichiarazioni_pubbliche.youtube_caption_fallback import (
    yt_dlp_caption_unavailable,
)
from dichiarazioni_pubbliche.youtube_caption_ytdlp import (
    YtDlpAccessDenied, download_youtube_json3,
)
from dichiarazioni_pubbliche.source_watcher import (
    DiscoveredContent,
    fetch_text,
    parse_youtube_feed,
    select_italian_caption,
)


@dataclass(frozen=True)
class VideoCandidate:
    video_id: str
    title: str
    canonical_url: str


@dataclass(frozen=True)
class CaptionProbe:
    kind: str
    language: str


@dataclass(frozen=True)
class CaptionCapture:
    raw_bytes: bytes
    raw_sha256: str
    raw_text: str
    raw_text_sha256: str
    segments: tuple[CaptionSegment, ...]
    probe: CaptionProbe
    provenance: dict[str, str] = field(default_factory=lambda: {
        "method": "yt-dlp", "method_version": "unspecified-external",
        "raw_format": "json3", "access_path": "YT_DLP_PUBLIC_CAPTION",
    })


class PlatformAccessRestricted(RuntimeError):
    """The public client cannot access the platform copy without extra entitlement."""

    def __init__(self, reason: str, *, access_path: str = "YOUTUBE_TRANSCRIPT_API_PUBLIC_CAPTION") -> None:
        super().__init__(reason)
        self.access_path = access_path


_SERIES_EPISODE = re.compile(
    r"\b(pulp\s*podcast|pulp\s*special|pulpland)\s*#\s*(\d+)\b",
    re.IGNORECASE,
)


def _normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _series_episode(value: str) -> tuple[str, int] | None:
    match = _SERIES_EPISODE.search(value)
    if not match:
        return None
    series = re.sub(r"\s+", "", match.group(1).casefold())
    if series in {"pulppodcast", "pulpspecial"}:
        series = f"pulp {series[4:]}"
    return series, int(match.group(2))


def _title_score(left: str, right: str) -> float:
    a = _normalize_title(left)
    b = _normalize_title(right)
    if not a or not b:
        return 0.0
    sequence = SequenceMatcher(None, a, b).ratio()
    at = set(a.split())
    bt = set(b.split())
    token = len(at & bt) / len(at | bt) if at and bt else 0.0
    return max(sequence, token)


def choose_video_candidate(
    title: str,
    candidates: list[VideoCandidate],
    *,
    threshold: float = 0.68,
) -> VideoCandidate | None:
    if not candidates:
        return None
    episode = _series_episode(title)
    if episode is not None:
        marked = [(candidate, _series_episode(candidate.title)) for candidate in candidates]
        exact = [
            candidate
            for candidate, candidate_episode in marked
            if candidate_episode == episode
        ]
        if exact:
            return max(exact, key=lambda candidate: _title_score(title, candidate.title))
        # A known but different episode must never win on title similarity.
        candidates = [candidate for candidate, candidate_episode in marked if candidate_episode is None]
    ranked = sorted(
        (
            (_title_score(title, candidate.title), candidate)
            for candidate in candidates
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if ranked and ranked[0][0] >= threshold:
        return ranked[0][1]
    return None


class YouTubeResolver:
    def __init__(
        self, yt_dlp: str = "yt-dlp", playlist_limit: int = 250,
        *, use_transcript_api: bool | None = None,
        use_transcript_api_secondary: bool | None = None,
        transcript_api_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.yt_dlp = yt_dlp
        self.playlist_limit = max(playlist_limit, 1)
        self._catalog_cache: dict[str, list[VideoCandidate]] = {}
        # Explicit operator opt-in. The default contributor install stays stdlib-only.
        self.use_transcript_api = (
            os.environ.get("DP_YOUTUBE_TRANSCRIPT_API", "").strip() == "1"
            if use_transcript_api is None else use_transcript_api
        )
        self.use_transcript_api_secondary = (
            os.environ.get("DP_YOUTUBE_TRANSCRIPT_API_SECONDARY", "").strip() == "1"
            if use_transcript_api_secondary is None else use_transcript_api_secondary
        )
        if self.use_transcript_api and self.use_transcript_api_secondary:
            raise ValueError("TRANSCRIPT_API_MODES_CONFLICT")
        self._transcript_api_factory = transcript_api_factory

    def _atom_candidates(self, source: dict[str, Any]) -> list[VideoCandidate]:
        url = source.get("discovery_url")
        if not url:
            return []
        rows = parse_youtube_feed(fetch_text(url), source["id"])
        return [
            VideoCandidate(
                video_id=row.external_id,
                title=row.title,
                canonical_url=row.canonical_url,
            )
            for row in rows
        ]

    def _flat_candidates(self, source: dict[str, Any]) -> list[VideoCandidate]:
        source_id = source["id"]
        if source_id in self._catalog_cache:
            return self._catalog_cache[source_id]
        channel_url = str(source.get("channel_url") or "").rstrip("/")
        if not channel_url:
            return []
        proc = subprocess.run(
            [
                self.yt_dlp,
                "--no-cache-dir",
                "--flat-playlist",
                "--playlist-end",
                str(self.playlist_limit),
                "--dump-single-json",
                channel_url + "/videos",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout).strip().splitlines()
            raise RuntimeError(
                (message[-1] if message else "yt-dlp channel catalog failed")[:800]
            )
        payload = json.loads(proc.stdout)
        candidates = []
        for entry in payload.get("entries") or []:
            video_id = str(entry.get("id") or "").strip()
            title = str(entry.get("title") or "").strip()
            if not video_id or not title:
                continue
            candidates.append(
                VideoCandidate(
                    video_id=video_id,
                    title=title,
                    canonical_url=f"https://www.youtube.com/watch?v={video_id}",
                )
            )
        self._catalog_cache[source_id] = candidates
        return candidates

    def resolve(self, title: str, source: dict[str, Any]) -> VideoCandidate | None:
        combined: dict[str, VideoCandidate] = {}
        for candidate in self._atom_candidates(source):
            combined[candidate.video_id] = candidate
        match = choose_video_candidate(title, list(combined.values()))
        if match is not None:
            return match
        for candidate in self._flat_candidates(source):
            combined.setdefault(candidate.video_id, candidate)
        return choose_video_candidate(title, list(combined.values()))

    def metadata(self, video_url: str) -> dict[str, Any]:
        proc = subprocess.run(
            [
                self.yt_dlp,
                "--ignore-config",
                "--no-cache-dir",
                "--skip-download",
                "--dump-single-json",
                video_url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout).strip().splitlines()
            detail = (message[-1] if message else "yt-dlp metadata probe failed")[:800]
            lowered = detail.casefold()
            if any(
                marker in lowered
                for marker in (
                    "available to this channel's members",
                    "members-only content",
                    "private video",
                )
            ):
                raise PlatformAccessRestricted(detail)
            raise RuntimeError(detail)
        return json.loads(proc.stdout)

    def probe_caption(self, video_url: str) -> CaptionProbe | None:
        selected = select_italian_caption(self.metadata(video_url))
        if selected is None:
            return None
        return CaptionProbe(
            kind=str(selected["kind"]),
            language=str(selected["language"]),
        )

    @staticmethod
    def _youtube_video_id(video_url: str) -> str:
        parsed = urlparse(video_url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be",
        } or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError("TRANSCRIPT_API_UNTRUSTED_URL")
        candidate = (
            parsed.path.strip("/") if parsed.hostname == "youtu.be"
            else parse_qs(parsed.query).get("v", [""])[0] if parsed.path == "/watch"
            else ""
        )
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            raise ValueError("TRANSCRIPT_API_INVALID_VIDEO_ID")
        return candidate

    def _capture_transcript_api(self, video_url: str, probe: CaptionProbe) -> CaptionCapture:
        video_id = self._youtube_video_id(video_url)
        if probe.kind not in {"manual_caption", "automatic_caption"} or not probe.language:
            raise ValueError("TRANSCRIPT_API_INVALID_PROBE")
        if self._transcript_api_factory is None:
            from dichiarazioni_pubbliche.youtube_transcript_client import new_transcript_client

            factory = new_transcript_client
        else:
            factory = self._transcript_api_factory
        api = factory()
        try:
            available = api.list(video_id)
            language = probe.language.removesuffix("-orig")
            if probe.kind == "manual_caption":
                transcript = available.find_manually_created_transcript([language])
            else:
                transcript = available.find_generated_transcript([language])
            if transcript.language_code != language or bool(transcript.is_generated) != (
                probe.kind == "automatic_caption"
            ):
                raise ValueError("TRANSCRIPT_API_ORIGIN_MISMATCH")
            fetched = transcript.fetch(preserve_formatting=False)
            if fetched.language_code != language or bool(fetched.is_generated) != transcript.is_generated:
                raise ValueError("TRANSCRIPT_API_FETCH_MISMATCH")
        except Exception as exc:
            # A 429, IP block or challenge is a policy boundary: do not evade it
            # through another client or cookies/proxies.
            # The pinned donor wraps non-429 HTTP errors as YouTubeRequestFailed,
            # removing the original response object. Treat every such failure,
            # entitlement/consent denial and explicit challenge as a hold; falling
            # back to yt-dlp here could circumvent the platform's access decision.
            if getattr(getattr(exc, "response", None), "status_code", None) in {
                401, 403, 429, 451,
            } or type(exc).__name__ in {
                "TooManyRequests", "IpBlocked", "RequestBlocked", "PoTokenRequired",
                "YouTubeRequestFailed", "AgeRestricted", "VideoUnplayable",
                "VideoUnavailable", "FailedToCreateConsentCookie", "TranscriptApiRedirectDenied",
            }:
                raise PlatformAccessRestricted("TRANSCRIPT_API_ACCESS_RESTRICTED") from exc
            raise
        raw_rows = fetched.to_raw_data()
        segments = tuple(parse_transcript_api_snippets(raw_rows))
        raw_bytes = (json.dumps(raw_rows, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        raw_text = "\n".join(segment.text for segment in segments)
        return CaptionCapture(
            raw_bytes=raw_bytes,
            raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            raw_text=raw_text,
            raw_text_sha256=hashlib.sha256(raw_text.encode()).hexdigest(),
            segments=segments,
            probe=probe,
            provenance={
                "method": "youtube-transcript-api", "method_version": "1.2.4",
                "raw_format": "youtube-transcript-api-json-v1",
                "access_path": "YOUTUBE_TRANSCRIPT_API_PUBLIC_CAPTION",
                "video_id": video_id,
            },
        )

    def capture_caption(self, video_url: str, probe: CaptionProbe) -> CaptionCapture:
        if self.use_transcript_api_secondary:
            # Validate scope before invoking either client.
            self._youtube_video_id(video_url)
        fallback_reason = ""
        if self.use_transcript_api:
            try:
                return self._capture_transcript_api(video_url, probe)
            except PlatformAccessRestricted:
                raise
            except Exception as exc:
                # Missing dependency, missing selected track, malformed payload and
                # timeouts all revert to the existing independent JSON3 adapter.
                fallback_reason = type(exc).__name__
        try:
            capture = self._capture_yt_dlp_caption(video_url, probe)
        except PlatformAccessRestricted:
            raise
        except Exception as exc:
            reason = yt_dlp_caption_unavailable(exc)
            if not self.use_transcript_api_secondary or reason is None:
                raise
            recovered = self._capture_transcript_api(video_url, probe)
            return replace(recovered, provenance={
                **recovered.provenance, "prior_method": "yt-dlp",
                "prior_method_version": "unspecified-external",
                "fallback_reason": reason,
            })
        if fallback_reason:
            return replace(capture, provenance={
                **capture.provenance, "prior_method": "youtube-transcript-api",
                "prior_method_version": "1.2.4",
                "fallback_reason": fallback_reason,
            })
        return capture

    def _capture_yt_dlp_caption(self, video_url: str, probe: CaptionProbe) -> CaptionCapture:
        try:
            raw_bytes = download_youtube_json3(
                self.yt_dlp, video_url, probe.language, probe.kind,
            )
        except YtDlpAccessDenied as exc:
            raise PlatformAccessRestricted(
                "YT_DLP_CAPTION_ACCESS_RESTRICTED", access_path="YT_DLP_PUBLIC_CAPTION",
            ) from exc
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        payload = json.loads(raw_bytes)
        segments = tuple(parse_youtube_json3(payload))
        if not segments:
            raise RuntimeError("JSON3 caption contains no usable segments")
        raw_text = "\n".join(segment.text for segment in segments)
        raw_text_sha256 = hashlib.sha256(raw_text.encode()).hexdigest()
        return CaptionCapture(
            raw_bytes=raw_bytes,
            raw_sha256=raw_sha256,
            raw_text=raw_text,
            raw_text_sha256=raw_text_sha256,
            segments=segments,
            probe=probe,
        )


class PrivateTranscriptStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser()

    @staticmethod
    def _atomic_private_write(path: Path, data: bytes) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, path)
            os.chmod(path, 0o600)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _ensure_private_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)

    def persist_caption(
        self,
        *,
        content_id: str,
        variant_id: str,
        capture: CaptionCapture,
        receipt: dict[str, Any],
    ) -> Path:
        content_key = hashlib.sha256(content_id.encode()).hexdigest()[:32]
        variant_key = hashlib.sha256(variant_id.encode()).hexdigest()[:24]
        transcripts = self.root / "transcripts"
        content_dir = transcripts / content_key
        variant_dir = content_dir / variant_key
        captures_dir = variant_dir / "captures"
        directory = captures_dir / capture.raw_sha256[:32]
        for path in (
            self.root,
            transcripts,
            content_dir,
            variant_dir,
            captures_dir,
            directory,
        ):
            self._ensure_private_directory(path)
        filename = (
            "caption.raw.json3" if capture.provenance.get("raw_format", "json3") == "json3"
            else "caption.raw.youtube-transcript-api.json"
        )
        self._atomic_private_write(directory / filename, capture.raw_bytes)
        normalized = {
            "schema_version": 1,
            "content_id": content_id,
            "variant_id": variant_id,
            "segments": [asdict(segment) for segment in capture.segments],
        }
        self._atomic_private_write(
            directory / "segments.json",
            (json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n").encode(),
        )
        self._atomic_private_write(
            directory / "receipt.json",
            (json.dumps({**receipt, "capture_provenance": capture.provenance},
                        ensure_ascii=False, indent=2) + "\n").encode(),
        )
        return directory

    def persist_asr_response(
        self,
        *,
        content_id: str,
        variant_id: str,
        response: dict[str, Any],
        receipt: dict[str, Any],
    ) -> Path:
        content_key = hashlib.sha256(content_id.encode()).hexdigest()[:32]
        variant_key = hashlib.sha256(variant_id.encode()).hexdigest()[:24]
        response_bytes = (
            json.dumps(
                response,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        response_sha256 = hashlib.sha256(response_bytes).hexdigest()
        transcripts = self.root / "transcripts"
        content_dir = transcripts / content_key
        variant_dir = content_dir / variant_key
        runs_dir = variant_dir / "runs"
        directory = runs_dir / response_sha256[:32]
        for path in (
            self.root,
            transcripts,
            content_dir,
            variant_dir,
            runs_dir,
            directory,
        ):
            self._ensure_private_directory(path)
        self._atomic_private_write(
            directory / "asr-response.json",
            response_bytes,
        )
        self._atomic_private_write(
            directory / "receipt.json",
            (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode(),
        )
        return directory


def discovered_from_candidate(
    *,
    source_id: str,
    candidate: VideoCandidate,
    published_at: str = "",
) -> DiscoveredContent:
    return DiscoveredContent(
        source_id=source_id,
        platform="youtube",
        external_id=candidate.video_id,
        title=candidate.title,
        canonical_url=candidate.canonical_url,
        published_at=published_at,
    )

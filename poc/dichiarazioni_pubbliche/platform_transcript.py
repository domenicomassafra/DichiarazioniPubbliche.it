from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.caption_adapter import CaptionSegment, parse_youtube_json3
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


class PlatformAccessRestricted(RuntimeError):
    """The public client cannot access the platform copy without extra entitlement."""


_SERIES_EPISODE = re.compile(
    r"(pulps*podcast|pulps*special|pulpland)s*#s*(d+)",
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
    series = re.sub(r"\s+", " ", match.group(1).casefold()).strip()
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
        exact = [
            candidate
            for candidate in candidates
            if _series_episode(candidate.title) == episode
        ]
        if exact:
            return max(exact, key=lambda candidate: _title_score(title, candidate.title))
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
    def __init__(self, yt_dlp: str = "yt-dlp", playlist_limit: int = 250) -> None:
        self.yt_dlp = yt_dlp
        self.playlist_limit = max(playlist_limit, 1)
        self._catalog_cache: dict[str, list[VideoCandidate]] = {}

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

    def capture_caption(self, video_url: str, probe: CaptionProbe) -> CaptionCapture:
        flag = "--write-subs" if probe.kind == "manual_caption" else "--write-auto-subs"
        with tempfile.TemporaryDirectory(prefix="dichiarazioni-pubbliche-caption-") as tmp:
            template = str(Path(tmp) / "caption.%(ext)s")
            proc = subprocess.run(
                [
                    self.yt_dlp,
                    "--no-cache-dir",
                    "--skip-download",
                    flag,
                    "--sub-langs",
                    probe.language,
                    "--sub-format",
                    "json3",
                    "-o",
                    template,
                    video_url,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                message = (proc.stderr or proc.stdout).strip().splitlines()
                raise RuntimeError(
                    (message[-1] if message else "yt-dlp caption capture failed")[:800]
                )
            paths = sorted(Path(tmp).glob("caption*.json3"))
            if len(paths) != 1:
                raise RuntimeError(
                    f"Expected one JSON3 caption, found {len(paths)}"
                )
            raw_bytes = paths[0].read_bytes()
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
        self._atomic_private_write(directory / "caption.raw.json3", capture.raw_bytes)
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
            (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode(),
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

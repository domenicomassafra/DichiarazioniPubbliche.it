"""Existing independent JSON3 downloader, isolated from caption choice policy."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from dichiarazioni_pubbliche.youtube_caption_fallback import yt_dlp_access_denied


class YtDlpAccessDenied(RuntimeError):
    """Platform denial must be held before trying another adapter."""


def download_youtube_json3(yt_dlp: str, video_url: str, language: str, kind: str) -> bytes:
    flag = "--write-subs" if kind == "manual_caption" else "--write-auto-subs"
    with tempfile.TemporaryDirectory(prefix="dichiarazioni-pubbliche-caption-") as tmp:
        template = str(Path(tmp) / "caption.%(ext)s")
        proc = subprocess.run(
            [yt_dlp, "--ignore-config", "--no-cache-dir", "--proxy", "", "--skip-download",
             flag, "--sub-langs", language, "--sub-format", "json3",
             "-o", template, video_url],
            check=False, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            diagnostic = (proc.stderr or proc.stdout).strip()
            lines = diagnostic.splitlines()
            detail = (lines[-1] if lines else "yt-dlp caption capture failed")[:800]
            if yt_dlp_access_denied(diagnostic):
                raise YtDlpAccessDenied("YT_DLP_CAPTION_ACCESS_RESTRICTED")
            raise RuntimeError(detail)
        paths = sorted(Path(tmp).glob("caption*.json3"))
        if len(paths) != 1:
            raise RuntimeError(f"Expected one JSON3 caption, found {len(paths)}")
        return paths[0].read_bytes()


__all__ = ["YtDlpAccessDenied", "download_youtube_json3"]

"""Byte-verifiable, private Capture -> media interval derivation for DP-419.

This proves that a canonical interval can be decoded from an exact immutable
Capture, not that the transcript words, speaker, license or publication rights
are independently established. It never grants playback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}\Z")
MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_EXCERPT_MS = 30_000
PROOF_VERSION = "capture-decoded-pcm-s16le-16000-v1"


def _exec(args: list[str], *, timeout: int) -> bytes:
    try:
        completed = subprocess.run(
            args, capture_output=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("MEDIA_DECODER_UNAVAILABLE") from None
    if completed.returncode != 0 or len(completed.stdout) > 2_000_000:
        raise ValueError("MEDIA_DECODER_REFUSED")
    return completed.stdout


def derive_media_capture_segment(
    *, media_path: Path, capture_sha256: str, content_id: str, capture_id: str,
    canonical_segment_id: str, canonical_text_sha256: str, start_ms: int,
    end_ms: int,
) -> dict[str, object]:
    """Hash original bytes and a deterministic PCM slice from their actual audio.

    Caller must separately verify legal provenance, source-use rights and the
    words in the canonical transcript. A digest of a decoded interval is never
    by itself playback permission.
    """
    for name in (content_id, capture_id, canonical_segment_id):
        if not isinstance(name, str) or not _ID.fullmatch(name):
            raise ValueError("MEDIA_PROOF_ID_INVALID")
    for digest in (capture_sha256, canonical_text_sha256):
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError("MEDIA_PROOF_HASH_INVALID")
    if (
        type(start_ms) is not int or type(end_ms) is not int
        or start_ms < 0 or end_ms <= start_ms or end_ms - start_ms > MAX_EXCERPT_MS
    ):
        raise ValueError("MEDIA_PROOF_RANGE_INVALID")
    path = Path(media_path)
    demuxer = {".ogg": "ogg", ".wav": "wav"}.get(path.suffix.lower())
    if demuxer is None:
        raise ValueError("MEDIA_PROOF_FORMAT_UNSUPPORTED")
    if path.is_symlink() or not path.is_file():
        raise ValueError("MEDIA_PROOF_FILE_INVALID")
    if not 1 <= path.stat().st_size <= MAX_MEDIA_BYTES:
        raise ValueError("MEDIA_PROOF_SIZE_INVALID")
    digestor = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digestor.update(block)
    if digestor.hexdigest() != capture_sha256:
        raise ValueError("MEDIA_PROOF_CAPTURE_MISMATCH")
    output = _exec([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
        "-f", demuxer, "-show_entries",
        "format=duration:stream=codec_type", "-of", "json", str(path),
    ], timeout=15)
    try:
        probe = json.loads(output)
        duration = float(probe["format"]["duration"])
        has_audio = any(s.get("codec_type") == "audio" for s in probe["streams"])
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("MEDIA_PROOF_PROBE_INVALID") from None
    if not has_audio or not math.isfinite(duration) or duration <= 0:
        raise ValueError("MEDIA_PROOF_AUDIO_UNAVAILABLE")
    if end_ms > round(duration * 1000) + 1:
        raise ValueError("MEDIA_PROOF_DURATION_MISMATCH")
    pcm = _exec([
        "ffmpeg", "-nostdin", "-v", "error",
        "-protocol_whitelist", "file,pipe", "-f", demuxer,
        "-ss", f"{start_ms / 1000:.3f}", "-i", str(path),
        "-t", f"{(end_ms - start_ms) / 1000:.3f}",
        "-map", "0:a:0", "-ac", "1", "-ar", "16000",
        "-f", "s16le", "pipe:1",
    ], timeout=25)
    if not pcm:
        raise ValueError("MEDIA_PROOF_EXCERPT_EMPTY")
    material = {
        "version": PROOF_VERSION,
        "content_id": content_id,
        "capture_id": capture_id,
        "capture_sha256": capture_sha256,
        "canonical_segment_id": canonical_segment_id,
        "canonical_text_sha256": canonical_text_sha256,
        "start_ms": start_ms, "end_ms": end_ms,
        "excerpt_pcm_sha256": hashlib.sha256(pcm).hexdigest(),
    }
    evidence_sha = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        **material,
        "evidence_sha256": evidence_sha,
        "capture_segment_binding": "DECODED_FROM_CAPTURE",
        "derivation_scope": "MEDIA_BYTES_AND_INTERVAL_ONLY",
        "seek_authorized": False,
        "publication_authority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a private original-media Capture interval")
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--capture-sha256", required=True)
    parser.add_argument("--content-id", required=True)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--segment-id", required=True)
    parser.add_argument("--canonical-text-sha256", required=True)
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        proof = derive_media_capture_segment(
            media_path=args.media, capture_sha256=args.capture_sha256,
            content_id=args.content_id, capture_id=args.capture_id,
            canonical_segment_id=args.segment_id,
            canonical_text_sha256=args.canonical_text_sha256,
            start_ms=args.start_ms, end_ms=args.end_ms,
        )
    except (ValueError, OSError):
        print("MEDIA_PROOF_HELD")
        return 2
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

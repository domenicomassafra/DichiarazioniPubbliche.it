from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PurgeResult:
    content_dir: str
    purged: bool
    bytes_freed: int
    reason: str


def _tree_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        p.stat().st_size
        for p in path.rglob("*")
        if p.is_file() and not p.is_symlink()
    )


def _durable_dir_ready(path: Path) -> bool:
    if not path.is_dir() or path.is_symlink():
        return False
    return any(
        item.is_file() and not item.is_symlink()
        for item in path.rglob("*")
    )


def purge_transient_media(content_dir: Path) -> PurgeResult:
    """Delete only transient media after durable text/provenance exists."""
    content_dir = content_dir.resolve()
    manifest_path = content_dir / "manifest.json"
    media_dir = content_dir / "media"

    if not manifest_path.is_file() or manifest_path.is_symlink():
        return PurgeResult(str(content_dir), False, 0, "MANIFEST_MISSING")

    if manifest_path.stat().st_size > 1_048_576:
        return PurgeResult(str(content_dir), False, 0, "MANIFEST_TOO_LARGE")
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return PurgeResult(str(content_dir), False, 0, "MANIFEST_INVALID")
    if not isinstance(manifest, dict):
        return PurgeResult(str(content_dir), False, 0, "MANIFEST_INVALID")
    required = {
        "transcript_status": "complete",
        "content_hash_status": "complete",
        "provenance_status": "complete",
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            return PurgeResult(str(content_dir), False, 0, f"{key.upper()}_NOT_COMPLETE")

    if not _durable_dir_ready(content_dir / "transcripts"):
        return PurgeResult(str(content_dir), False, 0, "TRANSCRIPTS_NOT_DURABLE")
    if not _durable_dir_ready(content_dir / "receipts"):
        return PurgeResult(str(content_dir), False, 0, "RECEIPTS_NOT_DURABLE")

    if not media_dir.exists():
        return PurgeResult(str(content_dir), True, 0, "ALREADY_PURGED")

    if media_dir.is_symlink():
        return PurgeResult(str(content_dir), False, 0, "MEDIA_DIR_SYMLINK_REFUSED")
    if media_dir.parent != content_dir:
        return PurgeResult(str(content_dir), False, 0, "MEDIA_DIR_OUTSIDE_CONTENT_REFUSED")
    if any(path.is_symlink() for path in media_dir.rglob("*")):
        return PurgeResult(str(content_dir), False, 0, "MEDIA_TREE_SYMLINK_REFUSED")

    bytes_freed = _tree_bytes(media_dir)
    shutil.rmtree(media_dir)
    return PurgeResult(str(content_dir), True, bytes_freed, "PURGED")

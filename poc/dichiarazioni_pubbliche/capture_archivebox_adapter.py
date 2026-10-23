"""Opt-in ArchiveBox v0.9.73 process adapter for rights-cleared HTML captures.

Runs ArchiveBox's documented Python add() API in a separate interpreter and its
private collection. ArchiveBox owns capture/extractors, not this application.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

from dichiarazioni_pubbliche.capture_pipeline import (
    ArchiveResult, CapturePipelineError, _validate_capture_target,
)
from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard

ARCHIVEBOX_RELEASE = "0.9.73"
ARCHIVEBOX_COMMIT = "6f5d2f60a01a7ca1171d3b3ddac3310d13c47fab"
ARCHIVEBOX_ADAPTER_VERSION = "archivebox-0.9.73-private-v1"
_MAX_INPUT_BYTES = 4 * 1024 * 1024
_MAX_PROCESS_BYTES = 8192
_SHA = re.compile(r"^[a-f0-9]{64}$")

# Dedicated subprocess: official ArchiveBox Python API, no import into the host
# process, no shell, no ad-hoc snapshot implementation. stdout is JSON only.
_BRIDGE = """
import contextlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path

url, tag = sys.argv[1:]
sys.argv = ["archivebox", "add"]
with open(os.devnull, "w", encoding="utf-8") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
    version = importlib.metadata.version("archivebox")
    if version != "0.9.73":
        raise RuntimeError("ARCHIVEBOX_RELEASE_MISMATCH")
    from archivebox.config.django import setup_django
    setup_django(check_db=True)
    from archivebox.cli.archivebox_add import add
    from archivebox.crawls.models import Crawl
    from archivebox.core.models import Snapshot
    crawl = Crawl.objects.filter(urls=url, tags_str=tag).order_by("created_at").first()
    if crawl is None:
        crawl, _ = add(
            urls=[url], tag=tag, depth=0, max_urls=1, crawl_timeout=60,
            snapshot_max_size=4194304, plugins="readability",
            bg=False, config={"ONLY_NEW": False, "PERMISSIONS": "private"},
        )
    snapshots = list(Snapshot.objects.filter(crawl_id=crawl.id, url=url))
    permissions_private = (
        str(crawl.permissions).lower() == "private"
        and all(str(item.permissions).lower() == "private" for item in snapshots)
    )
    state = str(crawl.status).lower()
    snapshot = snapshots[0] if len(snapshots) == 1 else None
    snapshot_state = str(snapshot.status).lower() if snapshot else "missing"
    if snapshot and snapshot_state == "sealed":
        result = snapshot.archiveresult_set.filter(plugin="readability", status="succeeded").first()
        output = Path(result.output_dir) if result else None
        if not output or not output.is_dir() or not any(
            path.is_file() for path in output.rglob("*")
        ):
            snapshot_state = "incomplete"
    record = {
        "crawl_id": str(crawl.id),
        "snapshot_id": str(snapshot.id) if snapshot else "",
        "snapshot_status": snapshot_state,
        "crawl_status": state,
        "url_matches": bool(snapshot and snapshot.url == url),
        "permissions_private": permissions_private,
        "archivebox_version": version,
    }
print(json.dumps(record, sort_keys=True, separators=(",", ":")))
"""


def _digest_body(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            size += len(chunk)
            if size > _MAX_INPUT_BYTES:
                raise CapturePipelineError("ARCHIVEBOX_INPUT_TOO_LARGE")
            digest.update(chunk)
    return digest.hexdigest(), size


class ArchiveBoxArchiveAdapter:
    """Private ArchiveBox process, explicitly enabled by owner and source use."""

    provider = "archivebox-private"
    synchronous_private_snapshot = True

    def __init__(
        self, *, python_path: Path, private_root: Path, collection_dir: Path,
        source_use_guard: SourceFamilyUseGuard, network_fetch_permitted: bool = False,
        timeout_seconds: float = 90,
    ) -> None:
        if source_use_guard is None:
            raise ValueError("ARCHIVEBOX_SOURCE_USE_GUARD_REQUIRED")
        if type(network_fetch_permitted) is not bool:
            raise ValueError("ARCHIVEBOX_NETWORK_PERMIT_INVALID")
        if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 120:
            raise ValueError("ARCHIVEBOX_TIMEOUT_INVALID")
        self.python_path = Path(python_path).expanduser()
        self.private_root = Path(private_root).expanduser().resolve()
        self.collection_dir = Path(collection_dir).expanduser()
        self.source_use_guard = source_use_guard
        self.network_fetch_permitted = network_fetch_permitted
        self.timeout_seconds = timeout_seconds

    def _failure(self, code: str) -> ArchiveResult:
        return ArchiveResult("FAILED", self.provider, {
            "error_category": code, "adapter_version": ARCHIVEBOX_ADAPTER_VERSION,
        })

    def _require_current_source_uses(self, capture: ContentCaptureRecord) -> None:
        # ArchiveBox re-fetches and extracts the source in its own process.
        # A current ARCHIVE permit alone cannot authorize a revoked FETCH.
        for use in ("FETCH", "STORE_BODY", "PARSE_TEXT", "ARCHIVE"):
            self.source_use_guard.require(
                use, content_sha256=capture.content_sha256,
                media_type=capture.media_type,
            )

    def archive(self, *, capture: ContentCaptureRecord, body_path: Path | None) -> ArchiveResult:
        if not self.network_fetch_permitted:
            return self._failure("ARCHIVEBOX_SOURCE_FETCH_NOT_APPROVED")
        if (capture.status != "CAPTURED" or capture.hold_status != "NONE"
                or capture.media_type not in {"text/html", "application/xhtml+xml"}):
            return self._failure("ARCHIVEBOX_CAPTURE_INELIGIBLE")
        try:
            _validate_capture_target(capture.final_url, final=True)
            self.source_use_guard.bind_capture(
                content_id=capture.content_id, url=capture.final_url,
            )
            self.source_use_guard.bind_fetched(final_url=capture.final_url)
            self._require_current_source_uses(capture)
        except CapturePipelineError:
            return self._failure("ARCHIVEBOX_CAPTURE_URL_INVALID")
        # SourceUseBlocked is allowed to propagate: the pipeline persists its
        # machine code while suppressing source and legal details.
        if body_path is None or body_path.is_symlink() or not body_path.is_file():
            return self._failure("ARCHIVEBOX_BODY_UNAVAILABLE")
        try:
            if not body_path.resolve().is_relative_to(self.private_root / "captures"):
                return self._failure("ARCHIVEBOX_BODY_OUTSIDE_PRIVATE_ROOT")
            observed, size = _digest_body(body_path)
        except (OSError, CapturePipelineError):
            return self._failure("ARCHIVEBOX_BODY_INVALID")
        if size == 0 or observed != capture.content_sha256:
            return self._failure("ARCHIVEBOX_BODY_HASH_MISMATCH")
        if (not self.python_path.is_absolute()
                or not self.python_path.is_file() or not os.access(self.python_path, os.X_OK)):
            return self._failure("ARCHIVEBOX_PYTHON_INVALID")
        if (not self.collection_dir.is_absolute() or self.collection_dir.is_symlink()
                or not self.collection_dir.is_dir()
                or not self.collection_dir.resolve().is_relative_to(self.private_root)
                or stat.S_IMODE(self.collection_dir.stat().st_mode) & 0o077):
            return self._failure("ARCHIVEBOX_COLLECTION_NOT_PRIVATE")

        url_sha = hashlib.sha256(capture.final_url.encode("utf-8")).hexdigest()
        tag = f"dp-{url_sha[:16]}-{observed}"
        env = {
            "PATH": "/usr/bin:/bin", "HOME": str(self.private_root),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
        }
        try:
            result = subprocess.run(
                [str(self.python_path), "-c", _BRIDGE, capture.final_url, tag],
                cwd=self.collection_dir, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=self.timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired:
            return self._failure("ARCHIVEBOX_PROCESS_TIMEOUT")
        except OSError:
            return self._failure("ARCHIVEBOX_PROCESS_UNAVAILABLE")
        if result.returncode != 0 or len(result.stdout) > _MAX_PROCESS_BYTES:
            return self._failure("ARCHIVEBOX_PROCESS_FAILED")
        try:
            data = json.loads(result.stdout)
            if (not isinstance(data, dict)
                    or data.get("archivebox_version") != ARCHIVEBOX_RELEASE
                    or not re.fullmatch(r"[0-9a-f-]{32,36}", str(data.get("crawl_id", "")))
                    or data.get("url_matches") is not True and data.get("snapshot_id")):
                return self._failure("ARCHIVEBOX_RESULT_INVALID")
        except (ValueError, TypeError):
            return self._failure("ARCHIVEBOX_RESULT_INVALID")
        if data.get("permissions_private") is not True:
            return self._failure("ARCHIVEBOX_DONOR_NOT_PRIVATE")
        # Recheck every source use after the independent network fetch.
        self._require_current_source_uses(capture)
        receipt = {
            "adapter_version": ARCHIVEBOX_ADAPTER_VERSION,
            "archivebox_release": ARCHIVEBOX_RELEASE,
            "archivebox_commit": ARCHIVEBOX_COMMIT,
            "archivebox_crawl_id": data["crawl_id"],
            "archivebox_snapshot_id": data.get("snapshot_id") or "",
            "archivebox_status": data.get("snapshot_status") or "missing",
            "source_capture_id": capture.id,
            "source_capture_sha256": observed,
            "original_url_sha256": url_sha,
            "publication_state": "HOLD",
            "plugins": "readability",
        }
        if data.get("snapshot_status") in {"queued", "started", "missing"}:
            return ArchiveResult("PENDING", self.provider, receipt)
        if (data.get("snapshot_status") != "sealed" or data.get("crawl_status") != "sealed"
                or not data.get("snapshot_id")):
            return self._failure("ARCHIVEBOX_SNAPSHOT_INCOMPLETE")

        # Private content-addressed proof. Actual archive bytes remain solely in
        # ArchiveBox's private collection; never synthesize a public archive URL.
        marker = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        marker_sha = hashlib.sha256(marker).hexdigest()
        directory = self.private_root / "archivebox_receipts" / marker_sha[:2]
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = directory / f"{marker_sha}.json"
        if ((self.private_root / "archivebox_receipts").is_symlink()
                or directory.is_symlink() or target.is_symlink()):
            return self._failure("ARCHIVEBOX_RECEIPT_PATH_INVALID")
        try:
            if target.exists():
                if target.read_bytes() != marker:
                    return self._failure("ARCHIVEBOX_RECEIPT_CONFLICT")
            else:
                with target.open("xb") as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(marker)
            if stat.S_IMODE(target.stat().st_mode) & 0o077:
                return self._failure("ARCHIVEBOX_RECEIPT_PERMISSIONS")
        except OSError:
            return self._failure("ARCHIVEBOX_RECEIPT_WRITE_FAILED")
        return ArchiveResult("SUCCEEDED", self.provider, {
            **receipt, "snapshot_kind": "PRIVATE_ARCHIVEBOX",
            "snapshot_ref": f"archivebox_receipts/{marker_sha[:2]}/{marker_sha}.json",
            "snapshot_sha256": marker_sha, "snapshot_bytes": len(marker),
        })

"""Private archive lifecycle and locator validation for capture_pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from typing import TYPE_CHECKING, Any, Callable, Mapping
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked

if TYPE_CHECKING:
    from dichiarazioni_pubbliche.capture_pipeline import ArchiveAdapter, CaptureBodyStore, CapturePipelineStore
    from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord


def _valid_snapshot(body_store: CaptureBodyStore, receipt: Mapping[str, Any]) -> bool:
    """Only an existing, content-addressed private HTML object is a local locator."""
    ref = receipt.get("snapshot_ref")
    digest = receipt.get("snapshot_sha256")
    size = receipt.get("snapshot_bytes")
    if (
        receipt.get("snapshot_kind") != "PRIVATE_HTML" or receipt.get("archive_url")
        or not isinstance(ref, str) or not isinstance(digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", digest) is None
        or ref != f"archives/{digest[:2]}/{digest}.html"
        or type(size) is not int or not 0 < size <= 4 * 1024 * 1024
    ):
        return False
    try:
        raw = body_store.root / ref
        # _path resolves symlinks, so inspect the original entries first.
        if any(node.is_symlink() for node in (
            body_store.root / "archives", raw.parent, raw,
        )):
            return False
        path = body_store._path(ref)
        return (
            path.is_file() and not path.is_symlink()
            and path.stat().st_size == size
            and hashlib.sha256(path.read_bytes()).hexdigest() == digest
        )
    except (OSError, ValueError, TypeError, RuntimeError):
        return False


def _valid_archivebox_snapshot(
    body_store: CaptureBodyStore, receipt: Mapping[str, Any],
    source_sha256: str,
) -> bool:
    """A private ArchiveBox receipt is an immutable local proof, never a public URL."""
    ref, digest, size = (
        receipt.get("snapshot_ref"), receipt.get("snapshot_sha256"),
        receipt.get("snapshot_bytes"),
    )
    if (
        receipt.get("snapshot_kind") != "PRIVATE_ARCHIVEBOX"
        or receipt.get("archive_url")
        or receipt.get("publication_state") != "HOLD"
        or receipt.get("archivebox_status") != "sealed"
        or receipt.get("source_capture_sha256") != source_sha256
        or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
        or ref != f"archivebox_receipts/{digest[:2]}/{digest}.json"
        or type(size) is not int or not 0 < size <= 8192
    ):
        return False
    try:
        path = body_store.root / str(ref)
        if any(node.is_symlink() for node in (
            body_store.root / "archivebox_receipts", path.parent, path,
        )):
            return False
        path = body_store._path(str(ref))
        if (
            not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077
            or path.stat().st_size != size
        ):
            return False
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            return False
        proof = json.loads(raw)
        expected = {
            key: value for key, value in receipt.items()
            if key not in {"snapshot_kind", "snapshot_ref", "snapshot_sha256", "snapshot_bytes"}
        }
        return isinstance(proof, dict) and proof == expected
    except (OSError, TypeError, ValueError, RuntimeError):
        return False


def _valid_remote_archive(receipt: Mapping[str, Any]) -> bool:
    target = str(receipt.get("archive_url") or "").strip()
    try:
        parsed = urlsplit(target)
        return (
            parsed.scheme.lower() == "https" and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and parsed.port in {None, 443}
        )
    except ValueError:
        return False


def archive_capture(
    *, store: CapturePipelineStore, capture: ContentCaptureRecord,
    body_store: CaptureBodyStore, adapter: ArchiveAdapter,
    actor_ref: str, pipeline_version: str,
    safe_mapping: Callable[[Mapping[str, Any] | None, str], dict[str, Any]],
) -> str:
    """Idempotent DB receipt steps; raw provider errors never leak source data."""
    provider = str(adapter.provider or "").strip()
    if not provider:
        return "ARCHIVE_PROVIDER_REQUIRED"
    request_state = store.request_archive(
        capture_id=capture.id, provider=provider, actor_ref=actor_ref,
        receipt={"pipeline": pipeline_version},
    )
    if request_state != "ARCHIVE_REQUESTED":
        return request_state
    synchronous = bool(getattr(adapter, "synchronous_private_snapshot", False))
    if synchronous:
        pending_state = store.mark_archive_pending(
            capture_id=capture.id, provider=provider, actor_ref=actor_ref,
            receipt={"pipeline": pipeline_version, "phase": "PRIVATE_CLI_RUNNING"},
        )
        if pending_state != "PENDING":
            return pending_state
    body_path = body_store.path(capture.body_ref) if capture.body_ref else None
    try:
        result = adapter.archive(capture=capture, body_path=body_path)
        receipt = safe_mapping(result.receipt, "archive_receipt")
        if not receipt:
            receipt = {"code": "ARCHIVE_EMPTY_RECEIPT"}
        status = str(result.status or "").upper()
        if status == "PENDING":
            return store.mark_archive_pending(
                capture_id=capture.id, provider=provider, actor_ref=actor_ref,
                receipt=receipt,
            )
        if status == "SUCCEEDED":
            valid = (
                _valid_archivebox_snapshot(body_store, receipt, capture.content_sha256)
                if receipt.get("snapshot_kind") == "PRIVATE_ARCHIVEBOX"
                else _valid_snapshot(body_store, receipt)
                if "snapshot_ref" in receipt else _valid_remote_archive(receipt)
            )
            if not valid:
                status = "FAILED"
                receipt = {
                    "error_category": "ARCHIVE_SUCCESS_LOCATOR_INVALID",
                    "pipeline": pipeline_version,
                }
        if status not in {"SUCCEEDED", "FAILED"}:
            status = "FAILED"
            receipt = {**receipt, "error_category": "ARCHIVE_STATUS_INVALID"}
        return store.complete_archive(
            capture_id=capture.id, provider=provider, actor_ref=actor_ref,
            outcome=status, receipt=receipt,
        )
    except SourceUseBlocked as exc:
        return store.complete_archive(
            capture_id=capture.id, provider=provider, actor_ref=actor_ref,
            outcome="FAILED",
            receipt={"error_category": exc.code, "pipeline": pipeline_version},
        )
    except Exception:
        return store.complete_archive(
            capture_id=capture.id, provider=provider, actor_ref=actor_ref,
            outcome="FAILED",
            receipt={"error_category": "ARCHIVE_ADAPTER_FAILURE", "pipeline": pipeline_version},
        )

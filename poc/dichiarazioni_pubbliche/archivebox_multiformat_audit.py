"""Offline integrity and budget audit for an owner-authorized ArchiveBox canary.

This reads existing private artifacts only. A passing audit is not source-use
authorization, proof that ArchiveBox was executed, or publication approval.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import stat
import uuid
import zlib
from pathlib import Path
from typing import Any

VERSION = "archivebox-multiformat-canary-v1"
DONOR_TAG = "v0.9.73"
DONOR_COMMIT = "6f5d2f60a01a7ca1171d3b3ddac3310d13c47fab"
KINDS = {"WARC", "PDF", "METADATA"}
SHA = re.compile(r"[a-f0-9]{64}\Z")
IMAGE = re.compile(r"[a-z0-9][a-z0-9/_.-]*:[a-zA-Z0-9_.-]+@sha256:[a-f0-9]{64}\Z")
MAX_MANIFEST = 16384
MAX_ARTIFACT = 32 * 1024 * 1024
MAX_WARC_UNCOMPRESSED = MAX_ARTIFACT
MAGIC = {"WARC": (b"WARC/1.0", b"WARC/1.1"), "PDF": (b"%PDF-",)}


class CanaryAuditError(ValueError):
    """Stable public-safe reason, excluding user-controlled manifest values."""


def _read_json(raw: bytes) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CanaryAuditError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanaryAuditError("INVALID_JSON") from exc
    if not isinstance(data, dict):
        raise CanaryAuditError("NOT_AN_OBJECT")
    return data


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _positive(value: Any) -> bool:
    return type(value) is int and value > 0


def _private_file(root: Path, rel: Any) -> Path:
    if not isinstance(rel, str) or not rel or rel.startswith("/"):
        raise CanaryAuditError("INVALID_RELATIVE_PATH")
    parts = Path(rel).parts
    if not parts or any(part in ("..", ".") for part in parts):
        raise CanaryAuditError("INVALID_RELATIVE_PATH")
    path = root
    for part in parts:
        path /= part
        if path.is_symlink():
            raise CanaryAuditError("SYMLINK_REJECTED")
        if path.exists() and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise CanaryAuditError("ARTIFACT_NOT_PRIVATE")
    if not path.is_file():
        raise CanaryAuditError("ARTIFACT_MISSING")
    if not path.resolve().is_relative_to(root.resolve()):
        raise CanaryAuditError("ARTIFACT_OUTSIDE_ROOT")
    return path


def _fingerprint_file(path: Path, expected_bytes: int) -> tuple[str, bytes]:
    if expected_bytes > MAX_ARTIFACT:
        raise CanaryAuditError("ARTIFACT_TOO_LARGE")
    digest = hashlib.sha256()
    observed = 0
    head = b""
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            if not head:
                head = chunk[:32]
            observed += len(chunk)
            if observed > MAX_ARTIFACT or observed > expected_bytes:
                raise CanaryAuditError("ARTIFACT_SIZE_MISMATCH")
            digest.update(chunk)
    if observed != expected_bytes:
        raise CanaryAuditError("ARTIFACT_SIZE_MISMATCH")
    return digest.hexdigest(), head


def validate(private_root: Path, manifest: Path) -> dict[str, int]:
    """Validate an already produced private canary; perform no archive or network I/O."""
    root = private_root.absolute()
    if not root.is_dir() or root.is_symlink() or stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise CanaryAuditError("PRIVATE_ROOT_INVALID")
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > MAX_MANIFEST:
        raise CanaryAuditError("MANIFEST_INVALID")
    if not manifest.resolve().is_relative_to(root.resolve()):
        raise CanaryAuditError("MANIFEST_OUTSIDE_ROOT")
    if stat.S_IMODE(manifest.stat().st_mode) & 0o077:
        raise CanaryAuditError("MANIFEST_NOT_PRIVATE")
    data = _read_json(manifest.read_bytes())
    if data.get("schema") != VERSION:
        raise CanaryAuditError("SCHEMA_MISMATCH")
    donor, source, receipt, metrics, baseline, rollback = (
        data.get(name) for name in ("donor", "source", "receipt", "metrics", "monolith", "rollback")
    )
    if not all(isinstance(part, dict) for part in (donor, source, receipt, metrics, baseline, rollback)):
        raise CanaryAuditError("REQUIRED_SECTION_MISSING")
    if (donor.get("tag") != DONOR_TAG or donor.get("commit") != DONOR_COMMIT
            or donor.get("license") != "MIT" or not isinstance(donor.get("image"), str)
            or IMAGE.fullmatch(donor["image"]) is None):
        raise CanaryAuditError("DONOR_NOT_PINNED")
    uses = source.get("approved_uses")
    if (source.get("kind") != "SYNTHETIC_HTTPS"
            or not all(_sha(source.get(k)) for k in
                       ("original_url_sha256", "capture_sha256", "rights_decision_sha256"))
            or not isinstance(uses, list) or not all(isinstance(use, str) for use in uses)
            or set(uses) != {"FETCH", "STORE_BODY", "PARSE_TEXT", "ARCHIVE"}
            or len(uses) != 4):
        raise CanaryAuditError("SOURCE_PROOF_INCOMPLETE")
    try:
        uuid.UUID(receipt.get("crawl_id", ""))
        uuid.UUID(receipt.get("snapshot_id", ""))
    except (ValueError, TypeError, AttributeError):
        raise CanaryAuditError("RECEIPT_IDS_INVALID") from None
    if (receipt.get("source_capture_sha256") != source["capture_sha256"]
            or receipt.get("original_url_sha256") != source["original_url_sha256"]
            or receipt.get("publication_state") != "HOLD"
            or receipt.get("retention") != "PRIVATE"
            or receipt.get("archive_url") is not None
            or receipt.get("public_locator") is not None):
        raise CanaryAuditError("RECEIPT_NOT_PRIVATE")
    if (not isinstance(data.get("artifacts"), list)
            or len(data["artifacts"]) != len(KINDS)):
        raise CanaryAuditError("REQUIRED_ARTIFACTS_MISSING")
    observed_kinds: set[str] = set()
    total_bytes = 0
    for artifact in data["artifacts"]:
        if not isinstance(artifact, dict) or artifact.get("kind") not in KINDS:
            raise CanaryAuditError("ARTIFACT_KIND_INVALID")
        kind = artifact["kind"]
        if kind in observed_kinds:
            raise CanaryAuditError("DUPLICATE_ARTIFACT_KIND")
        observed_kinds.add(kind)
        size = artifact.get("bytes")
        if not _positive(size) or not _sha(artifact.get("sha256")):
            raise CanaryAuditError("ARTIFACT_FIELDS_INVALID")
        path = _private_file(root, artifact.get("path"))
        digest, head = _fingerprint_file(path, size)
        if digest != artifact["sha256"]:
            raise CanaryAuditError("ARTIFACT_HASH_MISMATCH")
        if kind == "WARC" and head.startswith(b"\x1f\x8b"):
            try:
                with gzip.open(path, "rb") as stream:
                    head = stream.read(32)
                    # Validate the CRC/trailer by consuming the entire stream;
                    # bound decompression to prevent gzip expansion bombs.
                    uncompressed = len(head)
                    while chunk := stream.read(65536):
                        uncompressed += len(chunk)
                        if uncompressed > MAX_WARC_UNCOMPRESSED:
                            raise CanaryAuditError("WARC_UNCOMPRESSED_TOO_LARGE")
            except (OSError, EOFError, zlib.error):
                raise CanaryAuditError("ARTIFACT_FORMAT_MISMATCH") from None
        if kind in MAGIC and not any(head.startswith(prefix) for prefix in MAGIC[kind]):
            raise CanaryAuditError("ARTIFACT_FORMAT_MISMATCH")
        if kind == "METADATA":
            if size > MAX_MANIFEST:
                raise CanaryAuditError("METADATA_TOO_LARGE")
            metadata = _read_json(path.read_bytes())
            if (metadata.get("crawl_id") != receipt["crawl_id"]
                    or metadata.get("snapshot_id") != receipt["snapshot_id"]
                    or metadata.get("source_capture_sha256") != source["capture_sha256"]
                    or metadata.get("publication_state") != "HOLD"
                    or metadata.get("archive_url") is not None):
                raise CanaryAuditError("METADATA_PROVENANCE_MISMATCH")
        total_bytes += size
    if observed_kinds != KINDS:
        raise CanaryAuditError("REQUIRED_ARTIFACTS_MISSING")
    for key in ("peak_rss_kib", "duration_ms", "disk_bytes", "max_rss_kib",
                "max_duration_ms", "max_disk_bytes"):
        if not _positive(metrics.get(key)):
            raise CanaryAuditError("METRICS_INCOMPLETE")
    if (metrics["peak_rss_kib"] > metrics["max_rss_kib"]
            or metrics["duration_ms"] > metrics["max_duration_ms"]
            or metrics["disk_bytes"] > metrics["max_disk_bytes"]
            or metrics["disk_bytes"] < total_bytes):
        raise CanaryAuditError("BUDGET_EXCEEDED")
    for key in ("peak_rss_kib", "duration_ms", "disk_bytes"):
        if not _positive(baseline.get(key)):
            raise CanaryAuditError("MONOLITH_BASELINE_MISSING")
    if (rollback.get("service_stopped") is not True
            or rollback.get("private_artifacts_preserved") is not True
            or not _sha(rollback.get("run_log_sha256"))
            or not _positive(rollback.get("run_log_bytes"))):
        raise CanaryAuditError("ROLLBACK_UNVERIFIED")
    log_path = _private_file(root, rollback.get("run_log_path"))
    log_digest, _ = _fingerprint_file(log_path, rollback["run_log_bytes"])
    if log_digest != rollback["run_log_sha256"]:
        raise CanaryAuditError("ROLLBACK_LOG_HASH_MISMATCH")
    return {"artifacts": len(KINDS), "artifact_bytes": total_bytes,
            "peak_rss_kib": metrics["peak_rss_kib"],
            "duration_ms": metrics["duration_ms"],
            "baseline_peak_rss_kib": baseline["peak_rss_kib"],
            "baseline_duration_ms": baseline["duration_ms"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = validate(args.private_root, args.manifest)
    except (CanaryAuditError, OSError) as exc:
        code = str(exc) if isinstance(exc, CanaryAuditError) else "FILESYSTEM_ERROR"
        print(f"BLOCKED: {code}")
        return 1
    print(f"PASS: private WARC/PDF/metadata sha256 audit, {summary['artifacts']} artifacts, "
          f"{summary['artifact_bytes']} bytes; runtime source-use proof remains separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

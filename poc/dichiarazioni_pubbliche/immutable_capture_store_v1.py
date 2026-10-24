"""DP-244 content-addressed, write-once private capture store.

The observation adapters never persist bodies: ``dp244_conditional_probe``
returns a receipt and explicitly says the caller owns atomic persistence. This
module is that persistence, and nothing else.

Guarantees
----------
* **Content address.** The file name is the SHA-256 of the bytes, so the same
  bytes can never land under two names and a different body cannot replace an
  existing capture.
* **Write once.** ``O_CREAT | O_EXCL`` plus a mode-0600 receipt file: storing
  identical bytes again is an idempotent read of the existing record, never a
  rewrite; a corrupted file is reported, never repaired in place.
* **No invented metadata.** Byte length and digest are measured here. Cost is
  taken from the caller and stays ``None`` (= unknown) unless measured
  externally; the record never publishes anything.

Pure standard library, no network, no database, no clock of its own.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


CAPTURE_STORE_VERSION = "dp244-immutable-capture-v1"
_MEDIA_TYPE = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CaptureStoreError(ValueError):
    """Stable operator code, never a partial write."""


@dataclass(frozen=True)
class CaptureRecord:
    capture_id: str
    source_id: str
    locator_id: str
    media_type: str
    byte_length: int
    content_sha256: str
    stored_at: str
    receipt_sha256: str
    measured_cost_micro_eur: int | None = None
    private_only: bool = True
    publication_authorized: bool = False
    contract_version: str = CAPTURE_STORE_VERSION


def _label(value: object, field: str) -> str:
    if type(value) is not str or not _LABEL.fullmatch(value):
        raise CaptureStoreError(f"CAPTURE_{field}_INVALID")
    return value


def _root(value: object) -> Path:
    if not isinstance(value, Path):
        raise CaptureStoreError("CAPTURE_ROOT_INVALID")
    return value


def _body(value: object) -> bytes:
    if type(value) is not bytes or not value:
        raise CaptureStoreError("CAPTURE_BODY_INVALID")
    return value


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt_material(record: CaptureRecord) -> dict[str, object]:
    material = asdict(record)
    material.pop("receipt_sha256")
    return material


def _receipt_sha(record: CaptureRecord) -> str:
    return _digest(
        json.dumps(
            _receipt_material(record), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def _write_once(path: Path, data: bytes, mode: int = 0o600) -> bool:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    return True


def store_capture(
    root: Path,
    *,
    body: bytes,
    source_id: str,
    locator_id: str,
    media_type: str,
    observed_at: datetime,
    expected_sha256: str | None = None,
    measured_cost_micro_eur: int | None = None,
) -> tuple[CaptureRecord, bool]:
    """Persist one body once. Returns ``(record, newly_written)``."""
    root = _root(root)
    body = _body(body)
    source_id = _label(source_id, "SOURCE_ID")
    locator_id = _label(locator_id, "LOCATOR_ID")
    if type(media_type) is not str or not _MEDIA_TYPE.match(media_type):
        raise CaptureStoreError("CAPTURE_MEDIA_TYPE_INVALID")
    if (
        type(observed_at) is not datetime
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise CaptureStoreError("CAPTURE_CLOCK_INVALID")
    if expected_sha256 is not None and (
        type(expected_sha256) is not str or expected_sha256 != _digest(body)
    ):
        raise CaptureStoreError("CAPTURE_HASH_MISMATCH")
    if measured_cost_micro_eur is not None and (
        type(measured_cost_micro_eur) is not int or measured_cost_micro_eur < 0
    ):
        raise CaptureStoreError("CAPTURE_COST_INVALID")
    digest = _digest(body)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    body_path = root / f"{digest}.bin"
    written = _write_once(body_path, body)
    existing = body_path.read_bytes()
    if _digest(existing) != digest:
        raise CaptureStoreError("CAPTURE_STORE_CORRUPTED")
    if not written:
        record = verify_capture(root, f"capture:sha256:{digest}")
        if (
            record.source_id != source_id
            or record.locator_id != locator_id
            or record.media_type != media_type
        ):
            raise CaptureStoreError("CAPTURE_PROVENANCE_MISMATCH")
        return record, False
    record = CaptureRecord(
        capture_id=f"capture:sha256:{digest}",
        source_id=source_id,
        locator_id=locator_id,
        media_type=media_type,
        byte_length=len(body),
        content_sha256=digest,
        stored_at=observed_at.astimezone(timezone.utc).isoformat(),
        receipt_sha256="",
        measured_cost_micro_eur=measured_cost_micro_eur,
    )
    record = CaptureRecord(**{**asdict(record), "receipt_sha256": _receipt_sha(record)})
    receipt_path = root / f"{digest}.receipt.json"
    _write_once(
        receipt_path,
        (json.dumps(asdict(record), indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return record, written


def verify_capture(root: Path, capture_id: str) -> CaptureRecord:
    """Re-read one capture from disk and re-derive its digest and receipt."""
    root = _root(root)
    if type(capture_id) is not str or not capture_id.startswith("capture:sha256:"):
        raise CaptureStoreError("CAPTURE_ID_INVALID")
    digest = capture_id.removeprefix("capture:sha256:")
    body_path = root / f"{digest}.bin"
    receipt_path = root / f"{digest}.receipt.json"
    if not body_path.is_file() or not receipt_path.is_file():
        raise CaptureStoreError("CAPTURE_NOT_FOUND")
    if _digest(body_path.read_bytes()) != digest:
        raise CaptureStoreError("CAPTURE_INTEGRITY_FAILED")
    record = CaptureRecord(**json.loads(receipt_path.read_text(encoding="utf-8")))
    if record.receipt_sha256 != _receipt_sha(record):
        raise CaptureStoreError("CAPTURE_RECEIPT_MISMATCH")
    if record.content_sha256 != digest or record.capture_id != capture_id:
        raise CaptureStoreError("CAPTURE_RECEIPT_MISMATCH")
    return record


__all__ = [
    "CAPTURE_STORE_VERSION",
    "CaptureRecord",
    "CaptureStoreError",
    "store_capture",
    "verify_capture",
]

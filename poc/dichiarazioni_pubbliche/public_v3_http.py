"""Opt-in HTTP adapter for an independently pinned, already approved v3 projection.

The v2 public API remains authoritative until both v3 files are configured.
The second file is a release authority pointer: it must be maintained outside
the candidate source and public static root by the trusted release process.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from .public_api import (
    API_VERSION_HEADER, JSON_CONTENT_TYPE, ApiResponse, _bad_request, _not_found,
    _unavailable, canonical_json_bytes, get_public_statement_v3,
    list_public_opinions_by_person_content_v3, list_public_statements_v3,
)

V3_BASE = "/api/v3"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_MAX_BYTES = 16 * 1024 * 1024


def _protected_bytes(path: Path, max_bytes: int) -> bytes:
    """Read a bounded regular file through one no-follow descriptor."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_size > max_bytes):
                raise _unavailable()
            return handle.read(max_bytes + 1)
    except OSError as exc:
        raise _unavailable() from exc


def _current_release(path: Path) -> str:
    try:
        value = _protected_bytes(path, 66).decode("ascii").strip()
    except UnicodeError as exc:
        raise _unavailable() from exc
    if _HASH.fullmatch(value) is None:
        raise _unavailable()
    return value


def _snapshot(path: Path) -> dict:
    try:
        raw = _protected_bytes(path, _MAX_BYTES)
        if len(raw) > _MAX_BYTES:
            raise _unavailable()
        candidate = json.loads(raw)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise _unavailable() from exc
    if not isinstance(candidate, dict):
        raise _unavailable()
    return candidate


def _query(raw: str, allowed: set[str]) -> dict[str, str]:
    if len(raw) > 1024:
        raise _bad_request("Query is too long")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=3, errors="strict")
    except (ValueError, UnicodeError) as exc:
        raise _bad_request("Invalid query") from exc
    if len(pairs) != len({key for key, _ in pairs}) or any(key not in allowed for key, _ in pairs):
        raise _bad_request("Unsupported or duplicate query parameter")
    return dict(pairs)


def serve_public_v3(
    method: str, path: str, *, statement_projection_path: str | Path | None,
    statement_current_fingerprint_path: str | Path | None,
) -> ApiResponse:
    if statement_projection_path is None and statement_current_fingerprint_path is None:
        raise _not_found()
    if not statement_projection_path or not statement_current_fingerprint_path:
        raise _unavailable()
    source = Path(statement_projection_path).absolute()
    authority = Path(statement_current_fingerprint_path).absolute()
    if source == authority or source.resolve() == authority.resolve():
        raise _unavailable()

    url = urlsplit(path)
    if url.path == f"{V3_BASE}/statements":
        params = _query(url.query, set())
        operation = "list"
    elif url.path == f"{V3_BASE}/opinions":
        params = _query(url.query, {"person_id", "content_id"})
        operation = "opinions"
    elif url.path.startswith(f"{V3_BASE}/statements/"):
        params = _query(url.query, set())
        identifier = unquote(url.path[len(f"{V3_BASE}/statements/"):])
        if not _ID.fullmatch(identifier) or "%" in identifier:
            raise _not_found()
        operation = "detail"
    else:
        raise _not_found()
    # Each request must see a currently authorized external release on both
    # sides of validating/serializing the source, including HEAD responses.
    before = _current_release(authority)
    bundle = _snapshot(source)
    if operation == "list":
        payload = list_public_statements_v3(
            bundle, allow_statement_v3=True, current_public_dataset_sha256=before)
    elif operation == "detail":
        payload = get_public_statement_v3(
            bundle, identifier, allow_statement_v3=True,
            current_public_dataset_sha256=before)
    else:
        payload = list_public_opinions_by_person_content_v3(
            bundle, allow_statement_v3=True, current_public_dataset_sha256=before,
            **params)
    body = canonical_json_bytes(payload)
    if _current_release(authority) != before:
        raise _unavailable()
    return ApiResponse(
        200, b"" if method == "HEAD" else body, JSON_CONTENT_TYPE,
        {"Cache-Control": "no-store", "Surrogate-Control": "no-store",
         "X-Content-Type-Options": "nosniff", API_VERSION_HEADER: "v3"},
        content_length=len(body) if method == "HEAD" else None,
    )

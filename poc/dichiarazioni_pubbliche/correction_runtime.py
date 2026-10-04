from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

MAX_REPLY_BODY_CHARS = 20_000
MAX_REPLY_IDENTITY_CHARS = 300
MAX_EVIDENCE_URLS = 32
MAX_EVIDENCE_URL_CHARS = 2_048
MAX_CORRECTION_REASON_CHARS = 8_000
MAX_CHANGED_FIELDS_BYTES = 32_768


def _safe_http_url(value: str) -> str:
    raw = str(value).strip()
    if not raw or len(raw) > MAX_EVIDENCE_URL_CHARS:
        raise ValueError("evidence URL must be 1..2048 characters")
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("unsafe evidence URL")
    return parsed.geturl()


def normalize_evidence_urls(values: list[str]) -> tuple[str, ...]:
    if len(values) > MAX_EVIDENCE_URLS:
        raise ValueError("too many evidence URLs")
    return tuple(dict.fromkeys(_safe_http_url(value) for value in values))


def deterministic_right_of_reply_id(
    *,
    finding_id: str,
    body: str,
    submitter_name: str | None,
    submitter_role: str | None,
    evidence_urls: list[str],
) -> str:
    text = body.strip()
    if not text or len(text) > MAX_REPLY_BODY_CHARS:
        raise ValueError("right-of-reply body must be 1..20000 characters")
    finding = finding_id.strip()
    if not finding:
        raise ValueError("right-of-reply finding_id is required")
    for field_name, value in {
        "submitter_name": submitter_name,
        "submitter_role": submitter_role,
    }.items():
        if value is not None and len(value.strip()) > MAX_REPLY_IDENTITY_CHARS:
            raise ValueError(f"{field_name} must be <= 300 characters")
    normalized_urls = normalize_evidence_urls(evidence_urls)
    material = {
        "finding_id": finding,
        "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "submitter_name": (submitter_name or "").strip(),
        "submitter_role": (submitter_role or "").strip(),
        "evidence_urls": normalized_urls,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "reply:" + hashlib.sha256(encoded).hexdigest()


def right_of_reply_source_hash(
    *,
    body: str,
    evidence_urls: list[str],
) -> str:
    normalized_urls = normalize_evidence_urls(evidence_urls)
    encoded = json.dumps(
        {
            "body": body.strip(),
            "evidence_urls": normalized_urls,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def deterministic_correction_id(
    *,
    finding_id: str,
    previous_finding_id: str,
    reason: str,
    changed_fields: dict[str, object],
) -> str:
    why = reason.strip()
    finding = finding_id.strip()
    previous = previous_finding_id.strip()
    if not finding or not previous:
        raise ValueError("correction finding IDs are required")
    if not why or len(why) > MAX_CORRECTION_REASON_CHARS:
        raise ValueError("correction reason must be 1..8000 characters")
    if finding == previous:
        raise ValueError("correction requires a distinct superseding finding")
    changed_fields_bytes = json.dumps(
        changed_fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(changed_fields_bytes) > MAX_CHANGED_FIELDS_BYTES:
        raise ValueError("correction changed_fields exceeds 32768 bytes")
    encoded = json.dumps(
        {
            "finding_id": finding,
            "previous_finding_id": previous,
            "reason": why,
            "changed_fields": changed_fields,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "correction:" + hashlib.sha256(encoded).hexdigest()

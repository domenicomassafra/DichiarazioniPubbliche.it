from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from dichiarazioni_pubbliche.source_watcher import DiscoveredContent


@dataclass(frozen=True)
class PlannedJob:
    job_id: str
    job_type: str
    content_key: str
    payload: dict


@dataclass(frozen=True)
class DiscoveryCluster:
    content_key: str
    items: tuple[DiscoveredContent, ...]


def _normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _date_bucket(value: str) -> str:
    if not value:
        return "unknown-date"
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        match = re.search(r"\d{4}-\d{2}-\d{2}", value)
        return match.group(0) if match else "unknown-date"


def provisional_content_key(content: DiscoveredContent) -> str:
    title = _normalize_title(content.title)
    day = _date_bucket(content.published_at)
    if day == "unknown-date":
        material = (
            f"{content.source_id}\0{day}\0{title}\0"
            f"{content.platform}\0{content.external_id}"
        ).encode()
    else:
        material = f"{day}\0{title}".encode()
    return "discovery:" + hashlib.sha256(material).hexdigest()


def definitive_content_key(content_sha256: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", content_sha256):
        raise ValueError("content_sha256 must be a 64-character hex SHA-256")
    return "sha256:" + content_sha256.lower()


def deterministic_job_id(job_type: str, content_key: str) -> str:
    digest = hashlib.sha256(f"{job_type}\0{content_key}".encode()).hexdigest()
    return f"job:{digest}"


def deterministic_content_id(content_key: str) -> str:
    digest = hashlib.sha256(content_key.encode()).hexdigest()
    return f"content:{digest}"


def cluster_discoveries(
    items: list[DiscoveredContent],
) -> list[DiscoveryCluster]:
    groups: dict[str, list[DiscoveredContent]] = {}
    for item in items:
        groups.setdefault(provisional_content_key(item), []).append(item)
    return [
        DiscoveryCluster(content_key=key, items=tuple(rows))
        for key, rows in sorted(groups.items())
    ]


def plan_initial_job(
    content: DiscoveredContent,
    ingest_plan: dict,
) -> PlannedJob:
    content_key = provisional_content_key(content)
    action = ingest_plan["action"]
    mapping = {
        "ACQUIRE_CAPTION": "TRANSCRIPT_ACQUIRE_CAPTION",
        "REMOTE_ASR": "TRANSCRIPT_ACQUIRE_ASR",
        "RESOLVE_PLATFORM_TRANSCRIPT_THEN_AUDIO": "TRANSCRIPT_RESOLVE_PLATFORM",
        "PROBE_PLATFORM_TRANSCRIPT": "TRANSCRIPT_RESOLVE_PLATFORM",
        "DISCOVERY_ONLY": "CONTENT_TRIAGE",
    }
    job_type = mapping.get(action, "CONTENT_TRIAGE")
    return PlannedJob(
        job_id=deterministic_job_id(job_type, content_key),
        job_type=job_type,
        content_key=content_key,
        payload={
            "source_id": content.source_id,
            "platform": content.platform,
            "external_id": content.external_id,
            "canonical_url": content.canonical_url,
            "ingest_action": action,
        },
    )

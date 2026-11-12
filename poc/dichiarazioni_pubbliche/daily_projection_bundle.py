"""DP-638 — merge daily records into the public projection bundle."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Sequence

from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_SCHEMA_VERSION,
    projection_dataset_sha256,
    validate_public_bundle,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def merge_bundle(
    bundle: dict[str, Any] | None,
    dossiers: Sequence[dict[str, Any]],
    contents: Sequence[dict[str, Any]],
    topics: Sequence[dict[str, Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge daily records into an existing projection bundle without losing its own."""

    merged = json.loads(json.dumps(bundle)) if bundle else {}
    merged_dossiers = list(merged.get("dossiers") or [])
    seen = {str(item.get("finding_id")) for item in merged_dossiers}
    for dossier in dossiers:
        if str(dossier["finding_id"]) in seen:
            continue
        seen.add(str(dossier["finding_id"]))
        merged_dossiers.append(dossier)
    merged_contents = list(merged.get("contents") or [])
    seen_contents = {str(item.get("content_id")) for item in merged_contents}
    for content in contents:
        if str(content["content_id"]) in seen_contents:
            continue
        seen_contents.add(str(content["content_id"]))
        merged_contents.append(content)
    merged_topics = list(merged.get("topics") or [])
    seen_topics = {str(item.get("topic_id")) for item in merged_topics}
    for topic in topics:
        if str(topic["topic_id"]) in seen_topics:
            continue
        seen_topics.add(str(topic["topic_id"]))
        merged_topics.append(topic)
    merged_dossiers.sort(key=lambda item: (str(item["finding"]["created_at"]), str(item["finding_id"])))
    bundle_out = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": generated_at or _now(),
        "dataset_sha256": "",
        "methodology": {
            "claim_level_only": True,
            "aggregate_person_score": False,
            "requires_publication_gate": True,
            "requires_approved_evidence": True,
            "requires_resolved_transcript": True,
            **(merged.get("methodology") or {}),
        },
        "dossier_count": len(merged_dossiers),
        "omitted_count": int(merged.get("omitted_count") or 0),
        "dossiers": merged_dossiers,
        "contents": merged_contents,
        "topics": merged_topics,
    }
    bundle_out["dataset_sha256"] = projection_dataset_sha256(bundle_out)
    return bundle_out


def write_bundle(path: Path, bundle: dict[str, Any]) -> dict[str, Any]:
    validate_public_bundle(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False, suffix=".tmp"
    ) as handle:
        json.dump(bundle, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(path)
    return bundle

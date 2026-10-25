"""Deterministic serialization of an already validated public API read model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .public_api import PublicIndex


def serialize_public_index(index: PublicIndex) -> dict[str, Any]:
    """Reconstruct the canonical public-v2 bundle from its validated index."""
    payload = {
        "schema_version": index.schema_version,
        "generated_at": index.generated_at,
        "dataset_sha256": index.dataset_sha256,
        "methodology": index.methodology,
        "dossier_count": index.dossier_count,
        "omitted_count": index.omitted_count,
        "dossiers": [entry.dossier for entry in index.entries],
    }
    if index.topics_present:
        payload["topics"] = [
            {
                "topic_id": topic["topic_id"],
                "slug": topic["slug"],
                "canonical_name": topic["canonical_name"],
                "scope_text": topic["scope_text"],
                "entity_version": topic["entity_version"],
                "review_event_ids": topic["review_event_ids"],
                "memberships": topic["memberships"],
            }
            for topic in sorted(
                index.topics.values(),
                key=lambda item: (item["canonical_name"].casefold(), item["topic_id"]),
            )
        ]
    first_class_contents = [
        {
            key: record.get(key)
            for key in (
                "content_id",
                "slug",
                "url",
                "title",
                "published_at",
                "content_kind",
                "duration_ms",
                "public_media_url",
                "media_policy_version",
                "publication_version",
                "review_event_ids",
            )
        }
        | {"finding_ids": [item["finding_id"] for item in record["findings"]]}
        for record in index.records.values()
        if record.get("publication_version") == "public-content-v1"
    ]
    if index.contents_present:
        first_class_contents.sort(key=lambda item: (str(item["title"]).casefold(), str(item["content_id"])))
        payload["contents"] = first_class_contents
    return payload

"""Versioned source configuration for the private DP-638 daily foundation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config" / "daily-sources.v1.json"
SOURCE_KINDS = frozenset({"public_rss", "youtube_channel"})
SOURCE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class DailyConfigError(ValueError):
    """A source configuration violates the versioned daily contract."""


@dataclass(frozen=True)
class SourceSpec:
    id: str
    name: str
    publisher: str
    kind: str
    discovery_url: str
    channel_id: str = ""
    max_items: int = 2

    def adapter_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "publisher": self.publisher,
            "kind": self.kind,
            "discovery_url": self.discovery_url,
            "max_items_per_run": self.max_items,
        }
        if self.channel_id:
            payload["channel_id"] = self.channel_id
        return payload


@dataclass(frozen=True)
class DailyConfig:
    sources: tuple[SourceSpec, ...]
    limits: dict[str, int]
    relevance_rule: dict[str, str]
    raw: dict[str, Any] = field(default_factory=dict)

    def limit(self, key: str, fallback: int) -> int:
        return self.limits.get(key, fallback)


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DailyConfigError(f"DAILY_CONFIG_INVALID_POSITIVE_INTEGER:{field_name}")
    return value


def _validate_discovery_url(value: Any, source_id: str) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DailyConfigError(f"DAILY_CONFIG_DISCOVERY_URL_INVALID:{source_id}")
    return url


def load_config(path: str | Path | None = None) -> DailyConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DailyConfigError("DAILY_CONFIG_UNREADABLE_OR_INVALID_JSON") from exc

    if not isinstance(payload, dict):
        raise DailyConfigError("DAILY_CONFIG_ROOT_MUST_BE_OBJECT")
    version = payload.get("schema_version")
    if isinstance(version, bool) or version != 1:
        raise DailyConfigError("DAILY_SOURCES_SCHEMA_UNSUPPORTED")
    if "models" in payload or "evening" in payload:
        raise DailyConfigError("DAILY_SOURCE_CONFIG_CANNOT_AUTHORIZE_MODELS_OR_DELIVERY")

    limits_payload = payload.get("limits")
    if not isinstance(limits_payload, dict):
        raise DailyConfigError("DAILY_CONFIG_LIMITS_MUST_BE_OBJECT")
    limits = {
        str(key): _positive_int(value, f"limits.{key}")
        for key, value in limits_payload.items()
    }

    rows = payload.get("sources")
    if not isinstance(rows, list):
        raise DailyConfigError("DAILY_CONFIG_SOURCES_MUST_BE_ARRAY")

    sources: list[SourceSpec] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DailyConfigError(f"DAILY_CONFIG_SOURCE_MUST_BE_OBJECT:{index}")
        enabled = row.get("enabled", True)
        if not isinstance(enabled, bool):
            raise DailyConfigError(f"DAILY_CONFIG_SOURCE_ENABLED_INVALID:{index}")
        if not enabled:
            continue

        source_id = str(row.get("id") or "").strip()
        if not SOURCE_ID_RE.fullmatch(source_id) or source_id in seen_ids:
            raise DailyConfigError(f"DAILY_CONFIG_SOURCE_ID_INVALID_OR_DUPLICATE:{index}")
        seen_ids.add(source_id)

        kind = str(row.get("kind") or "").strip()
        if kind not in SOURCE_KINDS:
            raise DailyConfigError(f"DAILY_CONFIG_SOURCE_KIND_INVALID:{source_id}")
        channel_id = str(row.get("channel_id") or "").strip()
        if kind == "youtube_channel" and not channel_id:
            raise DailyConfigError(f"DAILY_CONFIG_YOUTUBE_CHANNEL_ID_REQUIRED:{source_id}")

        discovery_url = _validate_discovery_url(row.get("discovery_url"), source_id)
        if kind == "youtube_channel":
            query_channel_ids = parse_qs(urlsplit(discovery_url).query).get("channel_id", [])
            if query_channel_ids != [channel_id]:
                raise DailyConfigError(f"DAILY_CONFIG_YOUTUBE_URL_CHANNEL_MISMATCH:{source_id}")
        name = str(row.get("name") or source_id).strip()
        publisher = str(row.get("publisher") or row.get("name") or source_id).strip()
        if not name or not publisher:
            raise DailyConfigError(f"DAILY_CONFIG_SOURCE_LABEL_REQUIRED:{source_id}")
        max_items = _positive_int(
            row.get("max_items_per_run", 2), f"sources.{source_id}.max_items_per_run"
        )
        max_per_source = limits.get("max_items_per_source")
        if max_per_source is not None and max_items > max_per_source:
            raise DailyConfigError(f"DAILY_CONFIG_SOURCE_LIMIT_EXCEEDS_GLOBAL:{source_id}")

        sources.append(
            SourceSpec(
                id=source_id,
                name=name,
                publisher=publisher,
                kind=kind,
                discovery_url=discovery_url,
                channel_id=channel_id,
                max_items=max_items,
            )
        )

    if not sources:
        raise DailyConfigError("DAILY_SOURCES_EMPTY")

    relevance_rule = payload.get("relevance_rule") or {}
    if not isinstance(relevance_rule, dict):
        raise DailyConfigError("DAILY_CONFIG_RELEVANCE_RULE_MUST_BE_OBJECT")
    return DailyConfig(
        sources=tuple(sources),
        limits=limits,
        relevance_rule={str(key): str(value) for key, value in relevance_rule.items()},
        raw=payload,
    )

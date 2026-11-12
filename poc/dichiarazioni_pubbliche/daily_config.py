"""DP-638 — the daily machine configuration: sources and models."""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from dichiarazioni_pubbliche.daily_text import DailyMachineError

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config" / "daily-sources.v1.json"

# --------------------------------------------------------------------------

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
            "kind": self.kind,
            "discovery_url": self.discovery_url,
        }
        if self.channel_id:
            payload["channel_id"] = self.channel_id
        return payload


@dataclass(frozen=True)
class DailyConfig:
    sources: tuple[SourceSpec, ...]
    models: dict[str, str]
    limits: dict[str, int]
    relevance_rule: dict[str, str]
    raw: dict[str, Any] = field(default_factory=dict)

    def model(self, key: str, fallback: str = "") -> str:
        return str(self.models.get(key) or fallback)

    def limit(self, key: str, fallback: int) -> int:
        try:
            return int(self.limits.get(key, fallback))
        except (TypeError, ValueError):
            return fallback


def load_config(path: str | Path | None = None) -> DailyConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    payload = json.loads(config_path.read_text("utf-8"))
    if int(payload.get("schema_version", 0)) != 1:
        raise DailyMachineError("DAILY_SOURCES_SCHEMA_UNSUPPORTED")
    sources: list[SourceSpec] = []
    for row in payload.get("sources") or []:
        if not row.get("enabled", True):
            continue
        sources.append(
            SourceSpec(
                id=str(row["id"]),
                name=str(row.get("name") or row["id"]),
                publisher=str(row.get("publisher") or row.get("name") or row["id"]),
                kind=str(row["kind"]),
                discovery_url=str(row["discovery_url"]),
                channel_id=str(row.get("channel_id") or ""),
                max_items=int(row.get("max_items_per_run") or 2),
            )
        )
    if not sources:
        raise DailyMachineError("DAILY_SOURCES_EMPTY")
    return DailyConfig(
        sources=tuple(sources),
        models=dict(payload.get("models") or {}),
        limits=dict(payload.get("limits") or {}),
        relevance_rule=dict(payload.get("relevance_rule") or {}),
        raw=payload,
    )

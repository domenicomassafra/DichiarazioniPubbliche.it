from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit

from dichiarazioni_pubbliche.operation_ledger import deterministic_operation_key
from dichiarazioni_pubbliche.ingestion_relevance import (
    deterministic_ingestion_operation_ref,
)
from dichiarazioni_pubbliche.policy.privacy_policy import PRIVACY_POLICY_VERSION
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.scheduler import deterministic_content_id
from dichiarazioni_pubbliche.source_adapters import SourceAdapterError, discover_source_result
from dichiarazioni_pubbliche.source_watcher import get_source, load_registry


MANIFEST_VERSION = "research-discovery-manifest-v1"
QUERY_VERSION = "research-discovery-query-v1"
RUN_VERSION = "research-discovery-run-v1"
DISCOVERY_LEDGER_OPERATION = "RESEARCH_DISCOVERY"
MAX_QUERIES = 32
MAX_SEEDS = 64
MAX_TOTAL_RESULTS = 200
MAX_QUERY_RESULTS = 100
MAX_PER_HOST = 50
MAX_COST_USD = Decimal("25.000000")
MAX_QUERY_CHARS = 500
MAX_TITLE_CHARS = 1000
MAX_METADATA_BYTES = 16384
SENSITIVE_RECEIPT_KEYS = re.compile(
    r"(?:authorization|cookie|credential|password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)",
    re.I,
)
FORBIDDEN_DISCOVERY_METADATA_KEYS = re.compile(
    r"^(?:raw[_-]?body|raw[_-]?response|body[_-]?text|full[_-]?text|html|transcript|caption[_-]?text)$",
    re.I,
)


class DiscoveryManifestError(ValueError):
    pass


class DiscoveryAdapterError(RuntimeError):
    def __init__(self, category: str, *, blocked: bool = False) -> None:
        self.category = sanitize_category(category)
        self.blocked = bool(blocked)
        super().__init__(self.category)


@dataclass(frozen=True)
class DiscoverySeed:
    kind: str
    value: str


@dataclass(frozen=True)
class DiscoveryQuery:
    id: str
    ordinal: int
    query_text: str
    source_families: tuple[str, ...]
    adapter_ids: tuple[str, ...]
    seeds: tuple[DiscoverySeed, ...]
    max_results: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryManifest:
    id: str
    collection_id: str
    queries: tuple[DiscoveryQuery, ...]
    seeds: tuple[DiscoverySeed, ...]
    source_families: tuple[str, ...]
    date_from: str | None
    date_to: str | None
    max_results: int
    max_results_per_host: int
    cost_cap_usd: Decimal
    metadata: dict[str, Any]
    manifest_sha256: str
    coverage_need_ids: tuple[str, ...] = ()
    manifest_version: str = MANIFEST_VERSION


@dataclass(frozen=True)
class DiscoveryHitCandidate:
    canonical_url: str
    title: str = ""
    published_at: str | None = None
    source_family: str = "web"
    source_id: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryAdapterResult:
    hits: tuple[DiscoveryHitCandidate, ...] = ()
    status: str = "OK"
    cost_usd: Decimal = Decimal("0")
    provider_receipt: dict[str, Any] = field(default_factory=dict)
    error_category: str | None = None
    omitted_hits: int = 0


@dataclass(frozen=True)
class DiscoveryAdapterRequest:
    manifest_id: str
    manifest_sha256: str
    run_id: str
    query: DiscoveryQuery
    date_from: str | None
    date_to: str | None
    remaining_cost_usd: Decimal


@dataclass(frozen=True)
class DiscoveryRunReceipt:
    run_id: str
    manifest_id: str
    manifest_sha256: str
    status: str
    attempt_count: int
    healthy_attempts: int
    blocked_attempts: int
    failed_attempts: int
    raw_hits: int
    accepted_hits: int
    new_content: int
    existing_content: int
    rejected_hits: int
    cost_usd: Decimal
    error_category: str | None = None


class DiscoveryAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    supported_families: frozenset[str]

    def cost_upper_bound_usd(self, request: DiscoveryAdapterRequest) -> Decimal: ...

    def discover(self, request: DiscoveryAdapterRequest) -> DiscoveryAdapterResult: ...


def sanitize_category(value: object) -> str:
    text = str(value or "DISCOVERY_FAILURE").strip().upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return (text or "DISCOVERY_FAILURE")[:80]


def _required_text(value: object, field_name: str, *, limit: int = 2048) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_REQUIRED")
    text = str(value).strip()
    if not text:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_REQUIRED")
    if len(text) > limit:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_TOO_LONG")
    return text


def _json_mapping(value: object, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_INVALID")
    result = dict(value)
    stack = [result]
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            for key, child in node.items():
                if SENSITIVE_RECEIPT_KEYS.search(str(key)):
                    raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_SENSITIVE_KEY")
                if FORBIDDEN_DISCOVERY_METADATA_KEYS.search(str(key)):
                    raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_RAW_BODY_FORBIDDEN")
                if isinstance(child, (Mapping, list, tuple)):
                    stack.append(child)
        elif isinstance(node, (list, tuple)):
            stack.extend(child for child in node if isinstance(child, (Mapping, list, tuple)))
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_METADATA_BYTES:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_TOO_LARGE")
    return result


def _decimal(value: object, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_INVALID") from exc
    if not result.is_finite() or result < 0:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_INVALID")
    return result.quantize(Decimal("0.000001"))


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_INVALID")
    try:
        if isinstance(value, float) and not value.is_integer():
            raise ValueError
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_INVALID") from exc
    return result


def _parse_datetime(value: object, field_name: str) -> datetime | None:
    if value in {None, ""}:
        return None
    text = _required_text(value, field_name, limit=128)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_INVALID") from exc
    if parsed.tzinfo is None:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def canonicalize_discovery_url(value: object) -> tuple[str, str]:
    raw = _required_text(value, "canonical_url", limit=2048)
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise DiscoveryManifestError("DISCOVERY_URL_INVALID") from exc
    if parsed.scheme.lower() != "https":
        raise DiscoveryManifestError("DISCOVERY_URL_HTTPS_REQUIRED")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise DiscoveryManifestError("DISCOVERY_URL_AUTHORITY_INVALID")
    if port not in {None, 443}:
        raise DiscoveryManifestError("DISCOVERY_URL_PORT_REFUSED")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
    ):
        raise DiscoveryManifestError("DISCOVERY_URL_LOCAL_HOSTNAME")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise DiscoveryManifestError("DISCOVERY_URL_NONPUBLIC_IP")
    netloc = host
    path = parsed.path or "/"
    canonical = urlunsplit(("https", netloc, path, parsed.query, ""))
    return canonical, host


def _normalize_string_list(value: object, field_name: str, *, max_items: int = 32) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_REQUIRED")
    if len(value) > max_items:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_TOO_MANY")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _required_text(item, field_name, limit=128)
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    if not out:
        raise DiscoveryManifestError(f"DISCOVERY_{field_name.upper()}_REQUIRED")
    return tuple(out)


def _seed(value: object) -> DiscoverySeed:
    if not isinstance(value, Mapping):
        raise DiscoveryManifestError("DISCOVERY_SEED_INVALID")
    kind = _required_text(value.get("kind"), "seed_kind", limit=32).lower()
    if kind not in {"source_id", "url", "term"}:
        raise DiscoveryManifestError("DISCOVERY_SEED_KIND_INVALID")
    raw = _required_text(value.get("value"), "seed_value", limit=2048)
    if kind == "url":
        raw, _ = canonicalize_discovery_url(raw)
    return DiscoverySeed(kind, raw)


def _seeds(value: object, *, required: bool = False) -> tuple[DiscoverySeed, ...]:
    if value is None:
        if required:
            raise DiscoveryManifestError("DISCOVERY_SEEDS_REQUIRED")
        return ()
    if not isinstance(value, list):
        raise DiscoveryManifestError("DISCOVERY_SEEDS_INVALID")
    if len(value) > MAX_SEEDS:
        raise DiscoveryManifestError("DISCOVERY_SEEDS_TOO_MANY")
    result = tuple(_seed(item) for item in value)
    if required and not result:
        raise DiscoveryManifestError("DISCOVERY_SEEDS_REQUIRED")
    return result


def _seed_payload(seed: DiscoverySeed) -> dict[str, str]:
    return {"kind": seed.kind, "value": seed.value}


def _manifest_hash_payload(
    *,
    manifest_id: str,
    collection_id: str,
    date_from: str | None,
    date_to: str | None,
    max_results: int,
    max_results_per_host: int,
    cost_cap_usd: Decimal,
    seeds: Sequence[DiscoverySeed],
    source_families: Sequence[str],
    coverage_need_ids: Sequence[str],
    queries: Sequence[DiscoveryQuery],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_version": MANIFEST_VERSION,
        "id": manifest_id,
        "collection_id": collection_id,
        "date_from": date_from,
        "date_to": date_to,
        "limits": {
            "max_results": max_results,
            "max_results_per_host": max_results_per_host,
            "cost_cap_usd": str(cost_cap_usd),
        },
        "seeds": [_seed_payload(seed) for seed in seeds],
        "source_families": list(source_families),
        "coverage_need_ids": list(coverage_need_ids),
        "queries": [
            {
                "id": query.id,
                "ordinal": query.ordinal,
                "query_text": query.query_text,
                "source_families": list(query.source_families),
                "adapter_ids": list(query.adapter_ids),
                "seeds": [_seed_payload(seed) for seed in query.seeds],
                "max_results": query.max_results,
                "metadata": query.metadata,
            }
            for query in queries
        ],
        "metadata": dict(metadata),
    }


def load_discovery_manifest(value: Path | Mapping[str, Any]) -> DiscoveryManifest:
    if isinstance(value, Path):
        raw = json.loads(value.read_text())
    else:
        raw = dict(value)
    if raw.get("schema_version") != 1:
        raise DiscoveryManifestError("DISCOVERY_MANIFEST_SCHEMA_UNSUPPORTED")
    manifest_id = _required_text(raw.get("id"), "manifest_id", limit=256)
    collection_id = _required_text(raw.get("collection_id"), "collection_id", limit=256)
    date_window = raw.get("date_window") or {}
    if not isinstance(date_window, Mapping):
        raise DiscoveryManifestError("DISCOVERY_DATE_WINDOW_INVALID")
    date_from_dt = _parse_datetime(date_window.get("from"), "date_from")
    date_to_dt = _parse_datetime(date_window.get("to"), "date_to")
    if date_from_dt and date_to_dt and date_to_dt < date_from_dt:
        raise DiscoveryManifestError("DISCOVERY_DATE_WINDOW_REVERSED")
    date_from, date_to = _iso(date_from_dt), _iso(date_to_dt)

    limits = raw.get("limits") or {}
    if not isinstance(limits, Mapping):
        raise DiscoveryManifestError("DISCOVERY_LIMITS_INVALID")
    max_results = _integer(limits.get("max_results", 50), "max_results")
    max_per_host = _integer(limits.get("max_results_per_host", 5), "max_results_per_host")
    cost_cap = _decimal(limits.get("cost_cap_usd", "0"), "cost_cap_usd")
    if not 1 <= max_results <= MAX_TOTAL_RESULTS:
        raise DiscoveryManifestError("DISCOVERY_MAX_RESULTS_OUT_OF_RANGE")
    if not 1 <= max_per_host <= min(MAX_PER_HOST, max_results):
        raise DiscoveryManifestError("DISCOVERY_MAX_PER_HOST_OUT_OF_RANGE")
    if cost_cap > MAX_COST_USD:
        raise DiscoveryManifestError("DISCOVERY_COST_CAP_OUT_OF_RANGE")

    seeds = _seeds(raw.get("seeds"))
    source_families = _normalize_string_list(raw.get("source_families"), "source_families")
    raw_coverage_need_ids = raw.get("coverage_need_ids")
    coverage_need_ids = (
        ()
        if raw_coverage_need_ids in (None, [])
        else _normalize_string_list(
            raw_coverage_need_ids, "coverage_need_ids", max_items=64
        )
    )
    metadata = _json_mapping(raw.get("metadata"), "manifest_metadata")
    raw_queries = raw.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise DiscoveryManifestError("DISCOVERY_QUERIES_REQUIRED")
    if len(raw_queries) > MAX_QUERIES:
        raise DiscoveryManifestError("DISCOVERY_QUERIES_TOO_MANY")
    queries: list[DiscoveryQuery] = []
    seen_ids: set[str] = set()
    for ordinal, row in enumerate(raw_queries):
        if not isinstance(row, Mapping):
            raise DiscoveryManifestError("DISCOVERY_QUERY_INVALID")
        query_id = _required_text(row.get("id"), "query_id", limit=256)
        if query_id in seen_ids:
            raise DiscoveryManifestError("DISCOVERY_QUERY_ID_DUPLICATE")
        seen_ids.add(query_id)
        text = _required_text(row.get("query"), "query", limit=MAX_QUERY_CHARS)
        families = _normalize_string_list(
            row.get("source_families") or list(source_families), "query_source_families"
        )
        if not set(families).issubset(set(source_families)):
            raise DiscoveryManifestError("DISCOVERY_QUERY_FAMILY_OUTSIDE_MANIFEST")
        adapters = _normalize_string_list(row.get("adapter_ids"), "adapter_ids")
        query_seeds = _seeds(row.get("seeds")) or seeds
        query_limit = _integer(
            row.get("max_results", min(20, max_results)), "query_max_results"
        )
        if not 1 <= query_limit <= min(MAX_QUERY_RESULTS, max_results):
            raise DiscoveryManifestError("DISCOVERY_QUERY_LIMIT_OUT_OF_RANGE")
        queries.append(
            DiscoveryQuery(
                id=query_id,
                ordinal=ordinal,
                query_text=text,
                source_families=families,
                adapter_ids=adapters,
                seeds=query_seeds,
                max_results=query_limit,
                metadata=_json_mapping(row.get("metadata"), "query_metadata"),
            )
        )
    payload = _manifest_hash_payload(
        manifest_id=manifest_id,
        collection_id=collection_id,
        date_from=date_from,
        date_to=date_to,
        max_results=max_results,
        max_results_per_host=max_per_host,
        cost_cap_usd=cost_cap,
        seeds=seeds,
        source_families=source_families,
        coverage_need_ids=coverage_need_ids,
        queries=queries,
        metadata=metadata,
    )
    manifest_sha256 = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return DiscoveryManifest(
        id=manifest_id,
        collection_id=collection_id,
        queries=tuple(queries),
        seeds=seeds,
        source_families=source_families,
        date_from=date_from,
        date_to=date_to,
        max_results=max_results,
        max_results_per_host=max_per_host,
        cost_cap_usd=cost_cap,
        metadata=metadata,
        manifest_sha256=manifest_sha256,
        coverage_need_ids=coverage_need_ids,
    )


def _safe_receipt(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DiscoveryAdapterError("PROVIDER_RECEIPT_INVALID")

    def clean(node: object, *, depth: int = 0) -> Any:
        if depth > 4:
            raise DiscoveryAdapterError("PROVIDER_RECEIPT_TOO_DEEP")
        if isinstance(node, Mapping):
            out: dict[str, Any] = {}
            for key, child in node.items():
                key_text = str(key)[:128]
                if SENSITIVE_RECEIPT_KEYS.search(key_text):
                    raise DiscoveryAdapterError("PROVIDER_RECEIPT_SENSITIVE_KEY")
                if FORBIDDEN_DISCOVERY_METADATA_KEYS.search(key_text):
                    raise DiscoveryAdapterError("PROVIDER_RECEIPT_RAW_BODY_FORBIDDEN")
                out[key_text] = clean(child, depth=depth + 1)
            return out
        if isinstance(node, (list, tuple)):
            if len(node) > 100:
                raise DiscoveryAdapterError("PROVIDER_RECEIPT_TOO_LARGE")
            return [clean(child, depth=depth + 1) for child in node]
        if node is None or isinstance(node, (bool, int, float)):
            return node
        return str(node)[:1000]

    cleaned = clean(value)
    encoded = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_METADATA_BYTES:
        raise DiscoveryAdapterError("PROVIDER_RECEIPT_TOO_LARGE")
    return cleaned


def _hit_key(candidate: DiscoveryHitCandidate, ordinal: int) -> str:
    material = "\x1f".join(
        (
            str(ordinal),
            candidate.canonical_url,
            candidate.source_family,
            candidate.external_id or "",
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _hit_id(attempt_id: str, hit_key: str) -> str:
    return "discovery-hit:" + hashlib.sha256(f"{attempt_id}\x1f{hit_key}".encode()).hexdigest()


def _attempt_id(run_id: str, query_id: str, adapter_id: str) -> str:
    return "discovery-attempt:" + hashlib.sha256(
        f"{run_id}\x1f{query_id}\x1f{adapter_id}".encode()
    ).hexdigest()


def _discovery_operation_key(
    *,
    run_id: str,
    query_id: str,
    adapter_id: str,
    adapter_version: str,
) -> str:
    fingerprint = hashlib.sha256(
        f"{run_id}\x1f{query_id}\x1f{adapter_id}".encode()
    ).hexdigest()
    return deterministic_operation_key(
        operation=DISCOVERY_LEDGER_OPERATION,
        input_fingerprint=fingerprint,
        provider_id=adapter_id,
        model_id=adapter_version,
    )


def _discovery_receipt_id(attempt_id: str) -> str:
    return "receipt:" + hashlib.sha256(
        f"research-discovery\x1f{attempt_id}".encode()
    ).hexdigest()


def _discovery_billing(
    *,
    known_cost_usd: Decimal | None,
    cost_upper_bound_usd: Decimal,
) -> tuple[str, Decimal, Decimal | None]:
    upper = _decimal(cost_upper_bound_usd, "adapter_cost_upper_bound")
    if known_cost_usd is None:
        if upper == 0:
            return "ZERO_COST", Decimal("0"), None
        return "UNKNOWN", upper, None
    measured = _decimal(known_cost_usd, "adapter_cost_usd")
    if measured == 0 and upper == 0:
        return "ZERO_COST", Decimal("0"), None
    return "MEASURED_PROVIDER_COST", upper, measured


def new_discovery_run_id(manifest: DiscoveryManifest, nonce: str | None = None) -> str:
    value = nonce or uuid.uuid4().hex
    return "discovery-run:" + hashlib.sha256(
        f"{manifest.id}\x1f{manifest.manifest_sha256}\x1f{value}".encode()
    ).hexdigest()


def _url_content_id(canonical_url: str) -> str:
    return deterministic_content_id("url:" + hashlib.sha256(canonical_url.encode()).hexdigest())


_PERSIST_MANIFEST_SQL = r"""
WITH query_input AS (
    SELECT
        value->>'id' AS id,
        :'id'::text AS manifest_id,
        (value->>'ordinal')::integer AS ordinal,
        value->>'query_text' AS query_text,
        value->'source_families' AS source_families,
        value->'adapter_ids' AS adapter_ids,
        value->'seeds' AS seeds,
        (value->>'max_results')::integer AS max_results,
        value->'metadata' AS metadata
    FROM jsonb_array_elements(:'queries'::jsonb) value
), manifest_preflight_conflict AS (
    SELECT EXISTS (
        SELECT 1
        FROM research_discovery_manifest saved
        WHERE saved.id=:'id'
          AND NOT (
              saved.collection_id=:'collection_id'
              AND saved.manifest_version='research-discovery-manifest-v1'
              AND saved.manifest_sha256=:'manifest_sha256'
              AND saved.date_from IS NOT DISTINCT FROM NULLIF(:'date_from','')::timestamptz
              AND saved.date_to IS NOT DISTINCT FROM NULLIF(:'date_to','')::timestamptz
              AND saved.max_results=:'max_results'::integer
              AND saved.max_results_per_host=:'max_results_per_host'::integer
              AND saved.cost_cap_usd=:'cost_cap_usd'::numeric
              AND saved.seeds=:'seeds'::jsonb
              AND saved.source_families=:'source_families'::jsonb
              AND saved.coverage_need_ids=:'coverage_need_ids'::jsonb
              AND saved.metadata=:'metadata'::jsonb
          )
    ) AS conflict
), query_preflight_conflict AS (
    SELECT EXISTS (
        SELECT 1
        FROM query_input input
        JOIN research_discovery_query saved ON saved.id=input.id
        WHERE saved.manifest_id<>input.manifest_id
           OR saved.ordinal<>input.ordinal
           OR saved.query_text<>input.query_text
           OR saved.source_families<>input.source_families
           OR saved.adapter_ids<>input.adapter_ids
           OR saved.seeds<>input.seeds
           OR saved.max_results<>input.max_results
           OR saved.query_version<>'research-discovery-query-v1'
           OR saved.metadata<>input.metadata
    ) OR EXISTS (
        SELECT 1
        FROM query_input input
        JOIN research_discovery_query saved
          ON saved.manifest_id=input.manifest_id AND saved.ordinal=input.ordinal
        WHERE saved.id<>input.id
    ) AS conflict
), preflight AS (
    SELECT
        manifest_preflight_conflict.conflict AS manifest_conflict,
        query_preflight_conflict.conflict AS query_conflict
    FROM manifest_preflight_conflict CROSS JOIN query_preflight_conflict
), manifest_inserted AS (
    INSERT INTO research_discovery_manifest (
        id, collection_id, manifest_version, manifest_sha256, date_from, date_to,
        max_results, max_results_per_host, cost_cap_usd, seeds, source_families,
        coverage_need_ids, metadata
    )
    SELECT
        :'id', :'collection_id', 'research-discovery-manifest-v1', :'manifest_sha256',
        NULLIF(:'date_from','')::timestamptz, NULLIF(:'date_to','')::timestamptz,
        :'max_results'::integer, :'max_results_per_host'::integer, :'cost_cap_usd'::numeric,
        :'seeds'::jsonb, :'source_families'::jsonb, :'coverage_need_ids'::jsonb,
        :'metadata'::jsonb
    FROM preflight
    JOIN research_collection collection ON collection.id=:'collection_id'
    WHERE NOT manifest_conflict AND NOT query_conflict
      AND collection.status='ACTIVE'
    ON CONFLICT (id) DO NOTHING
    RETURNING id, collection_id, manifest_version, manifest_sha256, date_from, date_to,
              max_results, max_results_per_host, cost_cap_usd, seeds, source_families,
              coverage_need_ids, metadata
), manifest_current AS (
    SELECT * FROM manifest_inserted
    UNION ALL
    SELECT saved.id, saved.collection_id, saved.manifest_version, saved.manifest_sha256,
           saved.date_from, saved.date_to, saved.max_results, saved.max_results_per_host,
           saved.cost_cap_usd, saved.seeds, saved.source_families, saved.coverage_need_ids,
           saved.metadata
    FROM research_discovery_manifest saved
    WHERE saved.id=:'id' AND NOT EXISTS(SELECT 1 FROM manifest_inserted)
), manifest_ok AS (
    SELECT id FROM manifest_current
    WHERE id=:'id' AND collection_id=:'collection_id'
      AND manifest_version='research-discovery-manifest-v1'
      AND manifest_sha256=:'manifest_sha256'
      AND date_from IS NOT DISTINCT FROM NULLIF(:'date_from','')::timestamptz
      AND date_to IS NOT DISTINCT FROM NULLIF(:'date_to','')::timestamptz
      AND max_results=:'max_results'::integer
      AND max_results_per_host=:'max_results_per_host'::integer
      AND cost_cap_usd=:'cost_cap_usd'::numeric
      AND seeds=:'seeds'::jsonb AND source_families=:'source_families'::jsonb
      AND coverage_need_ids=:'coverage_need_ids'::jsonb
      AND metadata=:'metadata'::jsonb
      AND EXISTS (
          SELECT 1 FROM research_collection collection
          WHERE collection.id=:'collection_id' AND collection.status='ACTIVE'
      )
      AND NOT EXISTS (
          SELECT 1
          FROM jsonb_array_elements_text(:'coverage_need_ids'::jsonb) requested(need_id)
          LEFT JOIN coverage_need need ON need.id=requested.need_id
          WHERE need.id IS NULL
             OR need.status NOT IN ('OPEN','SEARCHING')
             OR need.attempt_count >= need.max_attempts
             OR (
                 need.collection_id IS NOT NULL
                 AND need.collection_id <> :'collection_id'
             )
             OR (
                 need.collection_id IS NULL
                 AND NOT EXISTS (
                     SELECT 1
                     FROM research_collection_content membership
                     WHERE membership.collection_id=:'collection_id'
                       AND membership.status='INCLUDED'
                       AND membership.content_id=COALESCE(
                           (SELECT claim.content_id FROM atomic_claim claim WHERE claim.id=need.atomic_claim_id),
                           (SELECT candidate.content_id FROM claim_candidate candidate WHERE candidate.id=need.claim_candidate_id)
                       )
                 )
             )
      )
), query_inserted AS (
    INSERT INTO research_discovery_query (
        id, manifest_id, ordinal, query_text, source_families, adapter_ids,
        seeds, max_results, query_version, metadata
    )
    SELECT id, manifest_id, ordinal, query_text, source_families, adapter_ids,
           seeds, max_results, 'research-discovery-query-v1', metadata
    FROM query_input
    WHERE EXISTS(SELECT 1 FROM manifest_ok)
      AND NOT EXISTS(SELECT 1 FROM preflight WHERE manifest_conflict OR query_conflict)
    ON CONFLICT (id) DO NOTHING
    RETURNING id, manifest_id, ordinal, query_text, source_families, adapter_ids,
              seeds, max_results, query_version, metadata
), query_current AS (
    SELECT * FROM query_inserted
    UNION ALL
    SELECT saved.id, saved.manifest_id, saved.ordinal, saved.query_text,
           saved.source_families, saved.adapter_ids, saved.seeds, saved.max_results,
           saved.query_version, saved.metadata
    FROM research_discovery_query saved
    JOIN query_input input ON input.id=saved.id
    WHERE NOT EXISTS(SELECT 1 FROM query_inserted inserted WHERE inserted.id=saved.id)
), query_conflicts AS (
    SELECT input.id
    FROM query_input input
    LEFT JOIN query_current saved ON saved.id=input.id
    WHERE saved.id IS NULL
       OR saved.manifest_id<>input.manifest_id
       OR saved.ordinal<>input.ordinal
       OR saved.query_text<>input.query_text
       OR saved.source_families<>input.source_families
       OR saved.adapter_ids<>input.adapter_ids
       OR saved.seeds<>input.seeds
       OR saved.max_results<>input.max_results
       OR saved.query_version<>'research-discovery-query-v1'
       OR saved.metadata<>input.metadata
), counts AS (
    SELECT
        (SELECT count(*) FROM query_input)::integer AS input_count,
        (SELECT count(*) FROM query_current)::integer AS current_count
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM preflight WHERE manifest_conflict OR query_conflict) THEN 'CONFLICT'
    WHEN NOT EXISTS(SELECT 1 FROM manifest_ok) THEN 'CONFLICT'
    WHEN EXISTS(SELECT 1 FROM query_conflicts) THEN 'CONFLICT'
    WHEN counts.input_count<>counts.current_count THEN 'CONFLICT'
    ELSE 'PERSISTED'
END
FROM counts;
""".strip()


_START_RUN_SQL = r"""
WITH inserted AS (
    INSERT INTO research_discovery_run (
        id, manifest_id, manifest_sha256, run_version, status, metadata
    )
    SELECT :'run_id', manifest.id, manifest.manifest_sha256,
           'research-discovery-run-v1', 'RUNNING', :'metadata'::jsonb
    FROM research_discovery_manifest manifest
    JOIN research_collection collection ON collection.id=manifest.collection_id
    WHERE manifest.id=:'manifest_id' AND manifest.manifest_sha256=:'manifest_sha256'
      AND manifest.status='ACTIVE' AND collection.status='ACTIVE'
    ON CONFLICT (id) DO NOTHING
    RETURNING id, status, manifest_id, manifest_sha256
), current AS (
    SELECT 'STARTED'::text AS state, id, status, manifest_id, manifest_sha256 FROM inserted
    UNION ALL
    SELECT 'EXISTING', run.id, run.status, run.manifest_id, run.manifest_sha256
    FROM research_discovery_run run
    WHERE run.id=:'run_id' AND NOT EXISTS(SELECT 1 FROM inserted)
)
SELECT json_build_object(
    'state', current.state,
    'status', current.status,
    'manifest_id', current.manifest_id,
    'manifest_sha256', current.manifest_sha256
)::text
FROM current;
""".strip()


_START_ATTEMPT_SQL = r"""
WITH inserted AS (
    INSERT INTO research_discovery_attempt (
        id, run_id, query_id, adapter_id, adapter_version, status, cost_upper_bound_usd, metadata
    )
    SELECT
        :'attempt_id', run.id, query.id, :'adapter_id', :'adapter_version',
        'RUNNING', :'cost_upper_bound_usd'::numeric, :'metadata'::jsonb
    FROM research_discovery_run run
    JOIN research_discovery_query query
      ON query.id=:'query_id' AND query.manifest_id=run.manifest_id
    WHERE run.id=:'run_id' AND run.status='RUNNING'
    ON CONFLICT (run_id, query_id, adapter_id) DO NOTHING
    RETURNING id, status, cost_usd, raw_hits, accepted_hits, rejected_hits,
              omitted_hits, error_category, provider_receipt
), current AS (
    SELECT 'STARTED'::text AS state, * FROM inserted
    UNION ALL
    SELECT 'EXISTING', saved.id, saved.status, saved.cost_usd, saved.raw_hits,
           saved.accepted_hits, saved.rejected_hits, saved.omitted_hits,
           saved.error_category, saved.provider_receipt
    FROM research_discovery_attempt saved
    WHERE saved.run_id=:'run_id' AND saved.query_id=:'query_id'
      AND saved.adapter_id=:'adapter_id' AND NOT EXISTS(SELECT 1 FROM inserted)
)
SELECT json_build_object(
    'state', current.state,
    'id', current.id,
    'status', current.status,
    'cost_usd', current.cost_usd,
    'raw_hits', current.raw_hits,
    'accepted_hits', current.accepted_hits,
    'rejected_hits', current.rejected_hits,
    'omitted_hits', current.omitted_hits,
    'error_category', current.error_category,
    'provider_receipt', current.provider_receipt
)::text FROM current;
""".strip()


_FINISH_ATTEMPT_SQL = r"""
UPDATE research_discovery_attempt
SET status=:'status',
    cost_usd=:'cost_usd'::numeric,
    raw_hits=:'raw_hits'::integer,
    accepted_hits=:'accepted_hits'::integer,
    rejected_hits=:'rejected_hits'::integer,
    omitted_hits=:'omitted_hits'::integer,
    error_category=NULLIF(:'error_category',''),
    provider_receipt=:'provider_receipt'::jsonb,
    completed_at=now()
WHERE id=:'attempt_id'
RETURNING status;
""".strip()


_RECORD_DISCOVERY_OPERATION_RECEIPT_SQL = r"""
WITH attempt_row AS (
    SELECT
        attempt.id,
        attempt.started_at,
        attempt.completed_at,
        run.manifest_id,
        manifest.collection_id
    FROM research_discovery_attempt attempt
    JOIN research_discovery_run run ON run.id=attempt.run_id
    JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
    WHERE attempt.id=:'attempt_id'
      AND attempt.run_id=:'run_id'
      AND attempt.query_id=:'query_id'
      AND attempt.adapter_id=:'adapter_id'
      AND attempt.adapter_version=:'adapter_version'
      AND run.manifest_id=:'manifest_id'
      AND manifest.collection_id=:'collection_id'
      AND attempt.status<>'RUNNING'
), inserted AS (
    INSERT INTO provider_receipt (
        id, content_id, provider_id, model_id, operation, request_id,
        operation_key, attempt, started_at, completed_at,
        input_bytes, input_seconds, estimated_cost_usd, measured_cost_usd,
        billing_basis, total_tokens, request_count, ledger_scope, status, receipt
    )
    SELECT
        :'receipt_id', NULL, :'adapter_id', :'adapter_version',
        'RESEARCH_DISCOVERY', NULL, :'operation_key', 1,
        attempt_row.started_at, COALESCE(attempt_row.completed_at, now()),
        NULL, NULL, :'estimated_cost_usd'::numeric,
        NULLIF(:'measured_cost_usd','')::numeric, :'billing_basis',
        NULL, 1, :'ledger_scope'::jsonb, :'status', :'receipt'::jsonb
    FROM attempt_row
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), current AS (
    SELECT id FROM inserted
    UNION ALL
    SELECT existing.id
    FROM provider_receipt existing
    WHERE existing.id=:'receipt_id'
      AND NOT EXISTS(SELECT 1 FROM inserted)
      AND existing.content_id IS NULL
      AND existing.provider_id=:'adapter_id'
      AND existing.model_id=:'adapter_version'
      AND existing.operation='RESEARCH_DISCOVERY'
      AND existing.operation_key=:'operation_key'
      AND existing.attempt=1
      AND existing.request_id IS NULL
      AND existing.estimated_cost_usd=:'estimated_cost_usd'::numeric
      AND existing.measured_cost_usd IS NOT DISTINCT FROM
          NULLIF(:'measured_cost_usd','')::numeric
      AND existing.billing_basis=:'billing_basis'
      AND existing.request_count=1
      AND existing.ledger_scope=:'ledger_scope'::jsonb
      AND existing.status=:'status'
      AND existing.receipt=:'receipt'::jsonb
)
SELECT COALESCE((SELECT id FROM current LIMIT 1), 'CONFLICT')::text;
""".strip()


_RECORD_HIT_SQL = r"""
WITH relevance_lock AS (
    SELECT CASE
        WHEN NULLIF(:'permit_content_ref','') IS NOT NULL
        THEN pg_advisory_xact_lock(hashtextextended(:'permit_content_ref', 30402))
        ELSE NULL
    END AS locked
), relevance_guard AS (
    SELECT CASE
        WHEN :'policy_disposition'<>'' THEN true
        ELSE EXISTS (
            SELECT 1
            FROM privacy_ingestion_acquisition_permit permit
            JOIN privacy_ingestion_relevance_authority authority
              ON authority.authority_id = permit.authority_id
            CROSS JOIN relevance_lock
            WHERE permit.permit_id = :'permit_id'
              AND permit.content_ref = :'permit_content_ref'
              AND permit.operation_kind = 'RESEARCH_DISCOVERY'
              AND permit.operation_ref = :'permit_operation_ref'
              AND authority.content_ref = permit.content_ref
              AND authority.content_binding_sha256 = permit.content_binding_sha256
              AND authority.contract_version = 'privacy-ingestion-relevance-v1'
              AND authority.binding_version = 'content-acquisition-binding-v1'
              AND authority.privacy_policy_version = :'privacy_policy_version'
              AND NOT EXISTS (
                  SELECT 1
                  FROM privacy_ingestion_relevance_authority successor
                  WHERE successor.supersedes_authority_id = authority.authority_id
              )
        )
    END AS allowed
    FROM relevance_lock
), lock_row AS (
    SELECT pg_advisory_xact_lock(hashtextextended(:'canonical_url', 0))
), identity_matches AS (
    SELECT array_agg(id ORDER BY id) AS ids, count(*)::integer AS n
    FROM (
        SELECT id FROM content_item CROSS JOIN lock_row
        WHERE canonical_url=:'canonical_url'
        UNION
        SELECT id FROM content_item
        WHERE NULLIF(:'source_id','') IS NOT NULL
          AND NULLIF(:'external_id','') IS NOT NULL
          AND source_id=NULLIF(:'source_id','')
          AND source_external_id=NULLIF(:'external_id','')
        UNION
        SELECT locator.content_id FROM content_locator locator
        WHERE NULLIF(:'platform','') IS NOT NULL
          AND NULLIF(:'external_id','') IS NOT NULL
          AND locator.platform=NULLIF(:'platform','')
          AND locator.external_id=NULLIF(:'external_id','')
    ) matches
), id_collision AS (
    SELECT id, canonical_url FROM content_item
    WHERE id=:'new_content_id'
), inserted_content AS (
    INSERT INTO content_item (
        id, source_id, source_external_id, canonical_url, title, description,
        language, published_at, metadata
    )
    SELECT
        :'new_content_id',
        CASE WHEN EXISTS(SELECT 1 FROM source WHERE id=NULLIF(:'source_id',''))
             THEN NULLIF(:'source_id','') ELSE NULL END,
        NULLIF(:'external_id',''), :'canonical_url', NULLIF(:'title',''), NULL,
        'it', NULLIF(:'published_at','')::timestamptz, :'content_metadata'::jsonb
    FROM identity_matches
    WHERE :'policy_disposition'=''
      AND (SELECT allowed FROM relevance_guard)
      AND :'new_content_id'=:'permit_content_ref'
      AND n=0
      AND NOT EXISTS(SELECT 1 FROM id_collision)
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), resolved AS (
    SELECT
        CASE
            WHEN :'policy_disposition'<>'' THEN :'policy_disposition'
            WHEN identity_matches.n>1 THEN 'AMBIGUOUS_CONTENT_IDENTITY'
            WHEN identity_matches.n=1 THEN 'EXISTING_CONTENT'
            WHEN EXISTS(SELECT 1 FROM inserted_content) THEN 'NEW_CONTENT'
            WHEN EXISTS(
                SELECT 1 FROM id_collision
                WHERE canonical_url=:'canonical_url'
            ) THEN 'EXISTING_CONTENT'
            ELSE 'AMBIGUOUS_CONTENT_IDENTITY'
        END AS disposition,
        CASE
            WHEN :'policy_disposition'<>'' AND identity_matches.n=1 THEN identity_matches.ids[1]
            WHEN :'policy_disposition'<>'' THEN NULL::text
            WHEN identity_matches.n=1 THEN identity_matches.ids[1]
            WHEN EXISTS(SELECT 1 FROM inserted_content) THEN :'new_content_id'
            WHEN EXISTS(
                SELECT 1 FROM id_collision WHERE canonical_url=:'canonical_url'
            ) THEN :'new_content_id'
            ELSE NULL::text
        END AS content_id
    FROM identity_matches
), run_resolved AS (
    SELECT
        CASE
            WHEN resolved.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
             AND resolved.content_id IS NOT NULL
             AND EXISTS (
                 SELECT 1
                 FROM research_discovery_hit prior
                 WHERE prior.run_id=:'run_id'
                   AND prior.content_id=resolved.content_id
                   AND prior.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
             ) THEN 'DUPLICATE_WITHIN_RUN'
            ELSE resolved.disposition
        END AS disposition,
        resolved.content_id
    FROM resolved
), member_insert AS (
    INSERT INTO research_collection_content (
        collection_id, content_id, inclusion_method, inclusion_version, status, rationale, metadata
    )
    SELECT :'collection_id', run_resolved.content_id, 'DISCOVERY_RUN', 'research-discovery-run-v1',
           'INCLUDED', NULLIF(:'rationale',''),
           jsonb_build_object('run_id', :'run_id', 'query_id', :'query_id')
    FROM run_resolved
    WHERE run_resolved.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
      AND run_resolved.content_id IS NOT NULL
      AND (
          :'policy_disposition'<>''
          OR (
              (SELECT allowed FROM relevance_guard)
              AND run_resolved.content_id=:'permit_content_ref'
          )
      )
    ON CONFLICT (collection_id, content_id) DO NOTHING
    RETURNING content_id
), locator_insert AS (
    INSERT INTO content_locator (content_id, platform, external_id, canonical_url, metadata)
    SELECT run_resolved.content_id, NULLIF(:'platform',''), NULLIF(:'external_id',''),
           :'canonical_url', jsonb_build_object('discovery_run_id', :'run_id')
    FROM run_resolved
    WHERE run_resolved.disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
      AND run_resolved.content_id IS NOT NULL
      AND (
          :'policy_disposition'<>''
          OR (
              (SELECT allowed FROM relevance_guard)
              AND run_resolved.content_id=:'permit_content_ref'
          )
      )
      AND NULLIF(:'platform','') IS NOT NULL
      AND NULLIF(:'external_id','') IS NOT NULL
    ON CONFLICT (platform, external_id) DO NOTHING
    RETURNING content_id
), hit_insert AS (
    INSERT INTO research_discovery_hit (
        id, run_id, attempt_id, query_id, hit_key, ordinal, canonical_url,
        source_host, title, published_at, source_family, source_id, external_id,
        disposition, content_id, reason_code, metadata
    )
    SELECT
        :'hit_id', :'run_id', :'attempt_id', :'query_id', :'hit_key', :'ordinal'::integer,
        :'canonical_url', :'source_host', NULLIF(:'title',''),
        NULLIF(:'published_at','')::timestamptz, :'source_family',
        CASE WHEN EXISTS(SELECT 1 FROM source WHERE id=NULLIF(:'source_id',''))
             THEN NULLIF(:'source_id','') ELSE NULL END,
        NULLIF(:'external_id',''), run_resolved.disposition, run_resolved.content_id,
        NULLIF(:'reason_code',''), :'metadata'::jsonb
    FROM run_resolved
    JOIN research_discovery_attempt attempt
      ON attempt.id=:'attempt_id'
     AND attempt.run_id=:'run_id'
     AND attempt.query_id=:'query_id'
     AND attempt.status='RUNNING'
    WHERE (
        :'policy_disposition'<>''
        OR (
            (SELECT allowed FROM relevance_guard)
            AND run_resolved.content_id=:'permit_content_ref'
        )
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, disposition, content_id, canonical_url, hit_key, ordinal
), current AS (
    SELECT 'INSERTED'::text AS state, id, disposition, content_id, canonical_url, hit_key, ordinal
    FROM hit_insert
    UNION ALL
    SELECT 'EXISTING', saved.id, saved.disposition, saved.content_id, saved.canonical_url, saved.hit_key, saved.ordinal
    FROM research_discovery_hit saved
    WHERE saved.id=:'hit_id' AND NOT EXISTS(SELECT 1 FROM hit_insert)
)
SELECT json_build_object(
    'state', CASE
        WHEN current.canonical_url=:'canonical_url' AND current.hit_key=:'hit_key'
         AND current.ordinal=:'ordinal'::integer THEN current.state
        ELSE 'CONFLICT'
    END,
    'disposition', current.disposition,
    'content_id', current.content_id
)::text FROM current;
""".strip()


_RECONCILE_RUNNING_ATTEMPTS_SQL = r"""
WITH updated AS (
    UPDATE research_discovery_attempt
    SET status='BLOCKED', error_category='ATTEMPT_RECONCILIATION_REQUIRED', completed_at=now()
    WHERE run_id=:'run_id' AND status='RUNNING'
    RETURNING id
)
SELECT count(*)::text FROM updated;
""".strip()

_RESUME_STATE_SQL = r"""
WITH accepted AS (
    SELECT canonical_url, source_host, query_id
    FROM research_discovery_hit
    WHERE run_id=:'run_id' AND disposition IN ('NEW_CONTENT','EXISTING_CONTENT')
), host_counts AS (
    SELECT COALESCE(json_object_agg(source_host, n)::text, '{}') AS value
    FROM (SELECT source_host, count(*)::integer AS n FROM accepted GROUP BY source_host) x
), query_counts AS (
    SELECT COALESCE(json_object_agg(query_id, n)::text, '{}') AS value
    FROM (SELECT query_id, count(*)::integer AS n FROM accepted GROUP BY query_id) x
), urls AS (
    SELECT COALESCE(json_agg(canonical_url ORDER BY canonical_url)::text, '[]') AS value FROM accepted
), costs AS (
    SELECT COALESCE(sum(cost_usd),0)::text AS value
    FROM research_discovery_attempt WHERE run_id=:'run_id' AND status<>'RUNNING'
), uncertain_cost AS (
    SELECT EXISTS (
        SELECT 1 FROM research_discovery_attempt attempt
        JOIN provider_receipt receipt
          ON receipt.ledger_scope->>'attempt_id'=attempt.id
        WHERE attempt.run_id=:'run_id'
          AND receipt.ledger_scope->>'run_id'=:'run_id'
          AND receipt.operation='RESEARCH_DISCOVERY'
          AND receipt.billing_basis='UNKNOWN'
    ) AS value
)
SELECT json_build_object(
    'accepted_urls', urls.value::json,
    'host_counts', host_counts.value::json,
    'query_counts', query_counts.value::json,
    'accepted_total', (SELECT count(*) FROM accepted),
    'cost_usd', costs.value,
    'cost_uncertain', uncertain_cost.value
)::text
FROM urls CROSS JOIN host_counts CROSS JOIN query_counts CROSS JOIN costs
CROSS JOIN uncertain_cost;
""".strip()


_COMPLETE_RUN_SQL = r"""
WITH attempts AS (
    SELECT
        count(*)::integer AS attempt_count,
        count(*) FILTER (WHERE status='HEALTHY')::integer AS healthy,
        count(*) FILTER (WHERE status IN ('BLOCKED','BUDGET_BLOCKED'))::integer AS blocked,
        count(*) FILTER (WHERE status='FAILED')::integer AS failed,
        COALESCE(sum(raw_hits),0)::integer AS raw_hits,
        COALESCE(sum(cost_usd),0)::numeric AS cost_usd
    FROM research_discovery_attempt WHERE run_id=:'run_id'
), hits AS (
    SELECT
        count(*) FILTER (WHERE disposition IN ('NEW_CONTENT','EXISTING_CONTENT'))::integer AS accepted,
        count(*) FILTER (WHERE disposition='NEW_CONTENT')::integer AS new_content,
        count(*) FILTER (WHERE disposition='EXISTING_CONTENT')::integer AS existing_content,
        count(*) FILTER (WHERE disposition NOT IN ('NEW_CONTENT','EXISTING_CONTENT'))::integer AS rejected
    FROM research_discovery_hit WHERE run_id=:'run_id'
), decision AS (
    SELECT
        CASE
            WHEN attempts.attempt_count=0 THEN 'BLOCKED'
            WHEN attempts.healthy=attempts.attempt_count THEN 'COMPLETED'
            WHEN attempts.healthy>0 THEN 'PARTIAL'
            WHEN attempts.failed>0 AND attempts.blocked=0 THEN 'FAILED'
            WHEN attempts.blocked>0 AND attempts.failed=0 THEN 'BLOCKED'
            ELSE 'PARTIAL'
        END AS status,
        attempts.*, hits.*
    FROM attempts CROSS JOIN hits
), updated AS (
    UPDATE research_discovery_run run
    SET status=decision.status,
        completed_at=now(),
        attempt_count=decision.attempt_count,
        healthy_attempts=decision.healthy,
        blocked_attempts=decision.blocked,
        failed_attempts=decision.failed,
        raw_hits=decision.raw_hits,
        accepted_hits=decision.accepted,
        new_content=decision.new_content,
        existing_content=decision.existing_content,
        rejected_hits=decision.rejected,
        cost_usd=decision.cost_usd,
        error_category=CASE
            WHEN decision.status='FAILED' THEN 'DISCOVERY_ATTEMPTS_FAILED'
            WHEN decision.status='BLOCKED' THEN 'DISCOVERY_ATTEMPTS_BLOCKED'
            WHEN decision.status='PARTIAL' THEN 'DISCOVERY_PARTIAL'
            ELSE NULL
        END
    FROM decision
    WHERE run.id=:'run_id'
    RETURNING run.*
)
SELECT json_build_object(
    'run_id', id, 'manifest_id', manifest_id, 'manifest_sha256', manifest_sha256,
    'status', status, 'attempt_count', attempt_count,
    'healthy_attempts', healthy_attempts, 'blocked_attempts', blocked_attempts,
    'failed_attempts', failed_attempts, 'raw_hits', raw_hits,
    'accepted_hits', accepted_hits, 'new_content', new_content,
    'existing_content', existing_content, 'rejected_hits', rejected_hits,
    'cost_usd', cost_usd, 'error_category', error_category
)::text FROM updated;
""".strip()


_GET_RUN_SQL = r"""
SELECT json_build_object(
    'run_id', id, 'manifest_id', manifest_id, 'manifest_sha256', manifest_sha256,
    'status', status, 'attempt_count', attempt_count,
    'healthy_attempts', healthy_attempts, 'blocked_attempts', blocked_attempts,
    'failed_attempts', failed_attempts, 'raw_hits', raw_hits,
    'accepted_hits', accepted_hits, 'new_content', new_content,
    'existing_content', existing_content, 'rejected_hits', rejected_hits,
    'cost_usd', cost_usd, 'error_category', error_category
)::text FROM research_discovery_run WHERE id=:'run_id';
""".strip()


class ResearchDiscoveryStore(PsqlRuntime):
    def relevance_content_ref(
        self,
        *,
        canonical_url: str,
        source_id: str | None,
        external_id: str | None,
        platform: str | None,
    ) -> str | None:
        new_content_id = _url_content_id(canonical_url)
        raw = self.run(
            """
            WITH identity_matches AS (
                SELECT id FROM content_item WHERE canonical_url=:'canonical_url'
                UNION
                SELECT id FROM content_item
                WHERE NULLIF(:'source_id','') IS NOT NULL
                  AND NULLIF(:'external_id','') IS NOT NULL
                  AND source_id=NULLIF(:'source_id','')
                  AND source_external_id=NULLIF(:'external_id','')
                UNION
                SELECT locator.content_id FROM content_locator locator
                WHERE NULLIF(:'platform','') IS NOT NULL
                  AND NULLIF(:'external_id','') IS NOT NULL
                  AND locator.platform=NULLIF(:'platform','')
                  AND locator.external_id=NULLIF(:'external_id','')
            ), identity_count AS (
                SELECT count(*)::integer AS n, min(id) AS only_id
                FROM identity_matches
            ), id_collision AS (
                SELECT canonical_url FROM content_item WHERE id=:'new_content_id'
            )
            SELECT CASE
                WHEN identity_count.n > 1 THEN ''
                WHEN identity_count.n = 1 THEN identity_count.only_id
                WHEN EXISTS(
                    SELECT 1 FROM id_collision WHERE canonical_url <> :'canonical_url'
                ) THEN ''
                ELSE :'new_content_id'
            END
            FROM identity_count;
            """,
            canonical_url=canonical_url,
            source_id=source_id or "",
            external_id=external_id or "",
            platform=platform or "",
            new_content_id=new_content_id,
        )
        return raw or None

    def persist_manifest(self, manifest: DiscoveryManifest) -> str:
        queries = [
            {
                "id": query.id,
                "ordinal": query.ordinal,
                "query_text": query.query_text,
                "source_families": list(query.source_families),
                "adapter_ids": list(query.adapter_ids),
                "seeds": [_seed_payload(seed) for seed in query.seeds],
                "max_results": query.max_results,
                "metadata": query.metadata,
            }
            for query in manifest.queries
        ]
        raw = self.run(
            _PERSIST_MANIFEST_SQL,
            id=manifest.id,
            collection_id=manifest.collection_id,
            manifest_sha256=manifest.manifest_sha256,
            date_from=manifest.date_from or "",
            date_to=manifest.date_to or "",
            max_results=manifest.max_results,
            max_results_per_host=manifest.max_results_per_host,
            cost_cap_usd=str(manifest.cost_cap_usd),
            seeds=json.dumps([_seed_payload(seed) for seed in manifest.seeds], separators=(",", ":")),
            source_families=json.dumps(list(manifest.source_families), separators=(",", ":")),
            coverage_need_ids=json.dumps(
                list(manifest.coverage_need_ids), separators=(",", ":")
            ),
            metadata=json.dumps(manifest.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            queries=json.dumps(queries, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        state = lines[-1] if lines else ""
        if state != "PERSISTED":
            raise RuntimeError("DISCOVERY_MANIFEST_CONFLICT")
        return state

    def start_run(self, manifest: DiscoveryManifest, run_id: str) -> dict[str, Any]:
        raw = self.run(
            _START_RUN_SQL,
            run_id=run_id,
            manifest_id=manifest.id,
            manifest_sha256=manifest.manifest_sha256,
            metadata=json.dumps({"manifest_version": MANIFEST_VERSION}, separators=(",", ":")),
        )
        if not raw:
            raise RuntimeError("DISCOVERY_RUN_MANIFEST_MISSING")
        result = json.loads(raw)
        if result.get("manifest_id") != manifest.id or result.get("manifest_sha256") != manifest.manifest_sha256:
            raise RuntimeError("DISCOVERY_RUN_CONFLICT")
        return result

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        raw = self.run(_GET_RUN_SQL, run_id=run_id)
        return json.loads(raw) if raw else None

    def start_attempt(
        self,
        *,
        attempt_id: str,
        run_id: str,
        query_id: str,
        adapter_id: str,
        adapter_version: str,
        cost_upper_bound_usd: Decimal,
    ) -> dict[str, Any]:
        raw = self.run(
            _START_ATTEMPT_SQL,
            attempt_id=attempt_id,
            run_id=run_id,
            query_id=query_id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            cost_upper_bound_usd=str(cost_upper_bound_usd),
            metadata="{}",
        )
        if not raw:
            raise RuntimeError("DISCOVERY_ATTEMPT_START_FAILED")
        return json.loads(raw)

    def finish_attempt(
        self,
        *,
        attempt_id: str,
        status: str,
        cost_usd: Decimal = Decimal("0"),
        raw_hits: int = 0,
        accepted_hits: int = 0,
        rejected_hits: int = 0,
        omitted_hits: int = 0,
        error_category: str = "",
        provider_receipt: Mapping[str, Any] | None = None,
    ) -> str:
        return self.run(
            _FINISH_ATTEMPT_SQL,
            attempt_id=attempt_id,
            status=status,
            cost_usd=str(cost_usd),
            raw_hits=max(int(raw_hits), 0),
            accepted_hits=max(int(accepted_hits), 0),
            rejected_hits=max(int(rejected_hits), 0),
            omitted_hits=max(int(omitted_hits), 0),
            error_category=sanitize_category(error_category) if error_category else "",
            provider_receipt=json.dumps(_safe_receipt(provider_receipt), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def record_operation_receipt(
        self,
        *,
        manifest: DiscoveryManifest,
        query: DiscoveryQuery,
        run_id: str,
        attempt_id: str,
        adapter_id: str,
        adapter_version: str,
        status: str,
        cost_upper_bound_usd: Decimal,
        known_cost_usd: Decimal | None,
        error_category: str = "",
    ) -> str:
        billing_basis, estimated_cost, measured_cost = _discovery_billing(
            known_cost_usd=known_cost_usd,
            cost_upper_bound_usd=cost_upper_bound_usd,
        )
        operation_key = _discovery_operation_key(
            run_id=run_id,
            query_id=query.id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
        )
        receipt_id = _discovery_receipt_id(attempt_id)
        ledger_scope = {
            "collection_id": manifest.collection_id,
            "manifest_id": manifest.id,
            "run_id": run_id,
            "query_id": query.id,
            "attempt_id": attempt_id,
        }
        canonical_receipt = {
            "schema": "research-discovery-operation-receipt-v1",
            "manifest_id": manifest.id,
            "run_id": run_id,
            "query_id": query.id,
            "attempt_id": attempt_id,
            "status": sanitize_category(status),
        }
        if error_category:
            canonical_receipt["error_category"] = sanitize_category(error_category)
        raw = self.run(
            _RECORD_DISCOVERY_OPERATION_RECEIPT_SQL,
            receipt_id=receipt_id,
            manifest_id=manifest.id,
            collection_id=manifest.collection_id,
            run_id=run_id,
            query_id=query.id,
            attempt_id=attempt_id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            operation_key=operation_key,
            estimated_cost_usd=str(estimated_cost),
            measured_cost_usd="" if measured_cost is None else str(measured_cost),
            billing_basis=billing_basis,
            ledger_scope=json.dumps(
                ledger_scope,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            status=sanitize_category(status),
            receipt=json.dumps(
                canonical_receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        if not raw or raw == "CONFLICT":
            raise RuntimeError("DISCOVERY_OPERATION_RECEIPT_CONFLICT")
        return raw

    def record_hit(
        self,
        *,
        manifest: DiscoveryManifest,
        query: DiscoveryQuery,
        run_id: str,
        attempt_id: str,
        ordinal: int,
        candidate: DiscoveryHitCandidate,
        policy_disposition: str = "",
        reason_code: str = "",
    ) -> dict[str, Any]:
        canonical_url, host = canonicalize_discovery_url(candidate.canonical_url)
        normalized = DiscoveryHitCandidate(
            canonical_url=canonical_url,
            title=str(candidate.title or "")[:MAX_TITLE_CHARS],
            published_at=candidate.published_at,
            source_family=str(candidate.source_family or "web")[:128],
            source_id=(str(candidate.source_id).strip()[:512] if candidate.source_id else None),
            external_id=(str(candidate.external_id).strip()[:512] if candidate.external_id else None),
            metadata=_json_mapping(candidate.metadata, "hit_metadata"),
        )
        key = _hit_key(normalized, ordinal)
        hit_id = _hit_id(attempt_id, key)
        new_content_id = _url_content_id(canonical_url)
        permit = None
        operation_ref = ""
        relevance_content_ref = ""
        if not policy_disposition:
            relevance_content_ref = self.relevance_content_ref(
                canonical_url=canonical_url,
                source_id=normalized.source_id,
                external_id=normalized.external_id,
                platform=str(normalized.metadata.get("platform") or "")[:64],
            )
            if relevance_content_ref is not None:
                operation_ref = deterministic_ingestion_operation_ref(
                    "RESEARCH_DISCOVERY",
                    hit_id,
                    relevance_content_ref,
                )
                permit = self.issue_ingestion_acquisition_permit(
                    content_ref=relevance_content_ref,
                    canonical_url=canonical_url,
                    operation_kind="RESEARCH_DISCOVERY",
                    operation_ref=operation_ref,
                )
                self.require_ingestion_acquisition_permit(
                    permit_id=permit.permit_id,
                    content_ref=relevance_content_ref,
                    canonical_url=canonical_url,
                    operation_kind="RESEARCH_DISCOVERY",
                    operation_ref=operation_ref,
                )
        raw = self.run(
            _RECORD_HIT_SQL,
            hit_id=hit_id,
            run_id=run_id,
            attempt_id=attempt_id,
            query_id=query.id,
            hit_key=key,
            ordinal=ordinal,
            canonical_url=canonical_url,
            source_host=host,
            title=normalized.title,
            published_at=normalized.published_at or "",
            source_family=normalized.source_family,
            source_id=normalized.source_id or "",
            external_id=normalized.external_id or "",
            platform=str(normalized.metadata.get("platform") or "")[:64],
            policy_disposition=policy_disposition,
            reason_code=reason_code,
            permit_id=permit.permit_id if permit is not None else "",
            permit_content_ref=relevance_content_ref or "",
            permit_operation_ref=operation_ref,
            privacy_policy_version=PRIVACY_POLICY_VERSION,
            metadata=json.dumps(normalized.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            new_content_id=new_content_id,
            content_metadata=json.dumps(
                {
                    "discovered_by": "research-discovery-run-v1",
                    "run_id": run_id,
                    "query_id": query.id,
                    "source_family": normalized.source_family,
                },
                separators=(",", ":"),
            ),
            collection_id=manifest.collection_id,
            rationale=f"Discovery query {query.id}",
        )
        if not raw:
            raise RuntimeError("DISCOVERY_HIT_WRITE_FAILED")
        result = json.loads(raw)
        if result.get("state") == "CONFLICT":
            raise RuntimeError("DISCOVERY_HIT_CONFLICT")
        return result

    def reconcile_running_attempts(self, run_id: str) -> int:
        raw = self.run(_RECONCILE_RUNNING_ATTEMPTS_SQL, run_id=run_id)
        return int(raw or 0)

    def resume_state(self, run_id: str) -> dict[str, Any]:
        raw = self.run(_RESUME_STATE_SQL, run_id=run_id)
        if not raw:
            return {
                "accepted_urls": [],
                "host_counts": {},
                "query_counts": {},
                "accepted_total": 0,
                "cost_usd": "0",
            }
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError("DISCOVERY_RESUME_STATE_INVALID")
        return parsed

    def complete_run(self, run_id: str) -> DiscoveryRunReceipt:
        raw = self.run(_COMPLETE_RUN_SQL, run_id=run_id)
        if not raw:
            raise RuntimeError("DISCOVERY_RUN_COMPLETE_FAILED")
        return receipt_from_dict(json.loads(raw))


def receipt_from_dict(raw: Mapping[str, Any]) -> DiscoveryRunReceipt:
    return DiscoveryRunReceipt(
        run_id=str(raw["run_id"]),
        manifest_id=str(raw["manifest_id"]),
        manifest_sha256=str(raw["manifest_sha256"]),
        status=str(raw["status"]),
        attempt_count=int(raw.get("attempt_count") or 0),
        healthy_attempts=int(raw.get("healthy_attempts") or 0),
        blocked_attempts=int(raw.get("blocked_attempts") or 0),
        failed_attempts=int(raw.get("failed_attempts") or 0),
        raw_hits=int(raw.get("raw_hits") or 0),
        accepted_hits=int(raw.get("accepted_hits") or 0),
        new_content=int(raw.get("new_content") or 0),
        existing_content=int(raw.get("existing_content") or 0),
        rejected_hits=int(raw.get("rejected_hits") or 0),
        cost_usd=_decimal(raw.get("cost_usd") or "0", "run_cost_usd"),
        error_category=(str(raw.get("error_category")) if raw.get("error_category") else None),
    )


def _query_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return {token for token in re.findall(r"[\wà-ÿ]+", normalized, flags=re.UNICODE) if len(token) >= 3}


class ConfiguredRegistryDiscoveryAdapter:
    adapter_id = "configured_registry"
    adapter_version = "configured-registry-discovery-v1"
    supported_families = frozenset({"youtube_channel", "podcast_rss", "public_creator_accounts"})

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path

    def cost_upper_bound_usd(self, request: DiscoveryAdapterRequest) -> Decimal:
        return Decimal("0")

    def discover(self, request: DiscoveryAdapterRequest) -> DiscoveryAdapterResult:
        registry = load_registry(self.registry_path)
        source_ids = [seed.value for seed in request.query.seeds if seed.kind == "source_id"]
        if not source_ids:
            return DiscoveryAdapterResult(status="BLOCKED", error_category="SOURCE_ID_SEED_REQUIRED")
        tokens = _query_tokens(request.query.query_text)
        hits: list[DiscoveryHitCandidate] = []
        omitted = 0
        for source_id in source_ids:
            try:
                source = get_source(registry, source_id)
            except KeyError:
                return DiscoveryAdapterResult(status="BLOCKED", error_category="SOURCE_NOT_CONFIGURED")
            family = str(source.get("kind") or "")
            if family not in request.query.source_families or family not in self.supported_families:
                continue
            result = discover_source_result(source, limit=request.query.max_results)
            if result.status != "OK":
                return DiscoveryAdapterResult(
                    status=result.status,
                    error_category=result.error_category or "SOURCE_FAILURE",
                    omitted_hits=result.omitted_items,
                    provider_receipt={"source_id": source_id, "family": family, "status": result.status},
                )
            omitted += result.omitted_items
            for item in result.items:
                haystack = _query_tokens(f"{item.title} {item.description or ''}")
                if tokens and haystack and not (tokens & haystack):
                    continue
                hits.append(
                    DiscoveryHitCandidate(
                        canonical_url=item.canonical_url,
                        title=item.title,
                        published_at=item.published_at or None,
                        source_family=family,
                        source_id=item.source_id,
                        external_id=item.external_id,
                        metadata={"platform": item.platform, "adapter": self.adapter_id},
                    )
                )
        return DiscoveryAdapterResult(
            hits=tuple(hits),
            cost_usd=Decimal("0"),
            omitted_hits=omitted,
            provider_receipt={"seed_sources": len(source_ids), "matched_hits": len(hits)},
        )


def _candidate_date(candidate: DiscoveryHitCandidate) -> datetime | None:
    if not candidate.published_at:
        return None
    try:
        return _parse_datetime(candidate.published_at, "published_at")
    except DiscoveryManifestError:
        return None


def _policy_disposition(
    *,
    manifest: DiscoveryManifest,
    query: DiscoveryQuery,
    candidate: DiscoveryHitCandidate,
    canonical_url: str,
    host: str,
    seen_urls: set[str],
    host_counts: dict[str, int],
    accepted_total: int,
    accepted_query: int,
) -> tuple[str, str]:
    if candidate.source_family not in query.source_families:
        return "REJECTED_POLICY", "SOURCE_FAMILY_NOT_REQUESTED"
    if canonical_url in seen_urls:
        return "DUPLICATE_WITHIN_RUN", "URL_ALREADY_SEEN"
    if manifest.date_from or manifest.date_to:
        published = _candidate_date(candidate)
        if published is None:
            return "OUTSIDE_DATE_WINDOW", "PUBLISHED_AT_REQUIRED_FOR_WINDOW"
        date_from = _parse_datetime(manifest.date_from, "date_from")
        date_to = _parse_datetime(manifest.date_to, "date_to")
        if date_from and published < date_from:
            return "OUTSIDE_DATE_WINDOW", "BEFORE_DATE_WINDOW"
        if date_to and published > date_to:
            return "OUTSIDE_DATE_WINDOW", "AFTER_DATE_WINDOW"
    if accepted_total >= manifest.max_results:
        return "RESULT_LIMIT", "MANIFEST_RESULT_LIMIT"
    if accepted_query >= query.max_results:
        return "RESULT_LIMIT", "QUERY_RESULT_LIMIT"
    if host_counts.get(host, 0) >= manifest.max_results_per_host:
        return "HOST_LIMIT", "HOST_RESULT_LIMIT"
    return "", ""


def run_discovery_manifest(
    manifest: DiscoveryManifest,
    store: ResearchDiscoveryStore,
    adapters: Mapping[str, DiscoveryAdapter],
    *,
    run_id: str | None = None,
) -> DiscoveryRunReceipt:
    # Manifest + all queries are durable before any adapter invocation. This prevents
    # model/provider-generated query execution without an auditable saved plan.
    store.persist_manifest(manifest)
    run_id = run_id or new_discovery_run_id(manifest)
    started = store.start_run(manifest, run_id)
    if started.get("state") == "EXISTING" and started.get("status") != "RUNNING":
        existing = store.get_run(run_id)
        if existing is None:
            raise RuntimeError("DISCOVERY_RUN_RECEIPT_MISSING")
        return receipt_from_dict(existing)

    if started.get("state") == "EXISTING":
        reconciled = store.reconcile_running_attempts(run_id)
        if reconciled:
            # A RUNNING attempt may already have called a paid/external provider. Its
            # actual cost/result is ambiguous, so do not execute any further adapter in
            # this run. A new run receipt may be started explicitly after review.
            return store.complete_run(run_id)

    resume = store.resume_state(run_id)
    seen_urls: set[str] = set(str(x) for x in (resume.get("accepted_urls") or []))
    host_counts: dict[str, int] = {
        str(k): int(v) for k, v in dict(resume.get("host_counts") or {}).items()
    }
    query_counts: dict[str, int] = {
        str(k): int(v) for k, v in dict(resume.get("query_counts") or {}).items()
    }
    accepted_total = int(resume.get("accepted_total") or 0)
    cost_total = _decimal(resume.get("cost_usd") or "0", "resume_cost_usd")
    cost_breached = cost_total > manifest.cost_cap_usd
    # A prior invoked provider may have an UNKNOWN measured cost even when
    # research_discovery_attempt.cost_usd is zero. Restore the receipt gate
    # across a process restart, not only within one invocation of this runner.
    cost_uncertain = resume.get("cost_uncertain") is True

    def finish_invoked_attempt(
        *,
        query: DiscoveryQuery,
        attempt_id: str,
        adapter_id: str,
        adapter_version: str,
        upper_bound: Decimal,
        status: str,
        known_cost_usd: Decimal | None,
        raw_hits: int = 0,
        accepted_hits: int = 0,
        rejected_hits: int = 0,
        omitted_hits: int = 0,
        error_category: str = "",
        provider_receipt: Mapping[str, Any] | None = None,
    ) -> None:
        store.finish_attempt(
            attempt_id=attempt_id,
            status=status,
            cost_usd=known_cost_usd or Decimal("0"),
            raw_hits=raw_hits,
            accepted_hits=accepted_hits,
            rejected_hits=rejected_hits,
            omitted_hits=omitted_hits,
            error_category=error_category,
            provider_receipt=provider_receipt,
        )
        store.record_operation_receipt(
            manifest=manifest,
            query=query,
            run_id=run_id,
            attempt_id=attempt_id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            status=status,
            cost_upper_bound_usd=upper_bound,
            known_cost_usd=known_cost_usd,
            error_category=error_category,
        )

    for query in manifest.queries:
        accepted_query = query_counts.get(query.id, 0)
        for adapter_id in query.adapter_ids:
            adapter = adapters.get(adapter_id)
            adapter_version = getattr(adapter, "adapter_version", "unavailable-v1") if adapter else "unavailable-v1"
            request = DiscoveryAdapterRequest(
                manifest_id=manifest.id,
                manifest_sha256=manifest.manifest_sha256,
                run_id=run_id,
                query=query,
                date_from=manifest.date_from,
                date_to=manifest.date_to,
                remaining_cost_usd=max(manifest.cost_cap_usd - cost_total, Decimal("0")),
            )
            upper_bound = Decimal("0")
            adapter_contract_error = ""
            if adapter is not None:
                try:
                    upper_bound = _decimal(adapter.cost_upper_bound_usd(request), "adapter_cost_upper_bound")
                except Exception:
                    upper_bound = Decimal("0")
                    adapter = None
                    adapter_version = "invalid-cost-contract-v1"
                    adapter_contract_error = "ADAPTER_COST_CONTRACT_INVALID"
            attempt_id = _attempt_id(run_id, query.id, adapter_id)
            attempt = store.start_attempt(
                attempt_id=attempt_id,
                run_id=run_id,
                query_id=query.id,
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                cost_upper_bound_usd=upper_bound,
            )
            if attempt.get("state") == "EXISTING":
                if attempt.get("status") == "RUNNING":
                    store.finish_attempt(
                        attempt_id=attempt_id,
                        status="BLOCKED",
                        error_category="ATTEMPT_RECONCILIATION_REQUIRED",
                    )
                continue
            if adapter is None:
                store.finish_attempt(
                    attempt_id=attempt_id,
                    status="BLOCKED",
                    error_category=adapter_contract_error or "ADAPTER_UNAVAILABLE",
                )
                continue
            supported_families = frozenset(
                str(value) for value in getattr(adapter, "supported_families", frozenset())
            )
            if not supported_families or not set(query.source_families).issubset(supported_families):
                store.finish_attempt(
                    attempt_id=attempt_id,
                    status="BLOCKED",
                    error_category="ADAPTER_FAMILY_UNSUPPORTED",
                )
                continue
            if cost_breached:
                store.finish_attempt(
                    attempt_id=attempt_id,
                    status="BUDGET_BLOCKED",
                    error_category="COST_CAP_ALREADY_EXCEEDED",
                )
                continue
            if cost_uncertain:
                store.finish_attempt(
                    attempt_id=attempt_id,
                    status="BUDGET_BLOCKED",
                    error_category="COST_STATE_UNCERTAIN",
                )
                continue
            if upper_bound > request.remaining_cost_usd:
                store.finish_attempt(
                    attempt_id=attempt_id,
                    status="BUDGET_BLOCKED",
                    error_category="COST_CAP_PRECALL",
                    provider_receipt={"cost_upper_bound_usd": str(upper_bound)},
                )
                continue
            try:
                result = adapter.discover(request)
            except DiscoveryAdapterError as exc:
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="BLOCKED" if exc.blocked else "FAILED",
                    known_cost_usd=None,
                    error_category=exc.category,
                )
                cost_uncertain = upper_bound > 0
                continue
            except SourceAdapterError as exc:
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="BLOCKED" if exc.blocked else "FAILED",
                    known_cost_usd=None,
                    error_category=exc.category,
                )
                cost_uncertain = upper_bound > 0
                continue
            except Exception:
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="FAILED",
                    known_cost_usd=None,
                    error_category="ADAPTER_FAILURE",
                )
                cost_uncertain = upper_bound > 0
                continue

            cost: Decimal | None = None
            try:
                status = str(result.status or "OK").upper()
                cost = _decimal(result.cost_usd, "adapter_cost_usd")
                result_hits = tuple(result.hits)
                omitted_hits = max(int(result.omitted_hits), 0)
            except (AttributeError, TypeError, ValueError, DiscoveryManifestError):
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="FAILED",
                    known_cost_usd=cost,
                    error_category="ADAPTER_RESULT_INVALID",
                )
                if cost is None and upper_bound > 0:
                    cost_uncertain = True
                continue
            assert cost is not None
            if len(result_hits) > MAX_QUERY_RESULTS:
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="FAILED",
                    known_cost_usd=cost,
                    raw_hits=len(result_hits),
                    omitted_hits=omitted_hits,
                    error_category="ADAPTER_RESULT_BOUND_EXCEEDED",
                )
                if cost_total + cost > manifest.cost_cap_usd:
                    cost_breached = True
                cost_total += cost
                continue
            try:
                receipt = _safe_receipt(result.provider_receipt)
            except DiscoveryAdapterError as exc:
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="FAILED",
                    known_cost_usd=cost,
                    raw_hits=len(result_hits),
                    error_category=exc.category,
                )
                cost_total += cost
                if cost_total > manifest.cost_cap_usd:
                    cost_breached = True
                continue
            if cost > upper_bound or cost_total + cost > manifest.cost_cap_usd:
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="FAILED",
                    known_cost_usd=cost,
                    raw_hits=len(result_hits),
                    omitted_hits=omitted_hits,
                    error_category="COST_RECEIPT_EXCEEDED",
                    provider_receipt=receipt,
                )
                cost_total += cost
                cost_breached = True
                continue
            cost_total += cost
            if status != "OK":
                finish_invoked_attempt(
                    query=query,
                    attempt_id=attempt_id,
                    adapter_id=adapter_id,
                    adapter_version=adapter_version,
                    upper_bound=upper_bound,
                    status="BLOCKED" if status == "BLOCKED" else "FAILED",
                    known_cost_usd=cost,
                    raw_hits=len(result_hits),
                    omitted_hits=omitted_hits,
                    error_category=result.error_category or "ADAPTER_NON_OK",
                    provider_receipt=receipt,
                )
                continue

            accepted_attempt = 0
            rejected_attempt = 0
            for ordinal, raw_candidate in enumerate(result_hits):
                raw_url = getattr(raw_candidate, "canonical_url", "")
                raw_title = getattr(raw_candidate, "title", "")
                raw_published_at = getattr(raw_candidate, "published_at", None)
                raw_source_family = getattr(raw_candidate, "source_family", "")
                raw_source_id = getattr(raw_candidate, "source_id", None)
                raw_external_id = getattr(raw_candidate, "external_id", None)
                raw_metadata = getattr(raw_candidate, "metadata", {})
                try:
                    candidate_metadata = _json_mapping(raw_metadata, "hit_metadata")
                except DiscoveryManifestError:
                    candidate_metadata = {}
                    metadata_rejected = True
                else:
                    metadata_rejected = False
                published_invalid = False
                try:
                    published_at = _iso(
                        _parse_datetime(raw_published_at, "published_at")
                    )
                except DiscoveryManifestError:
                    published_at = None
                    published_invalid = True
                try:
                    canonical_url, host = canonicalize_discovery_url(raw_url)
                except DiscoveryManifestError:
                    candidate = DiscoveryHitCandidate(
                        canonical_url=(
                            "https://invalid.invalid/rejected/"
                            + hashlib.sha256(str(raw_url).encode()).hexdigest()
                        ),
                        title=str(raw_title or ""),
                        published_at=published_at,
                        source_family=str(raw_source_family or "unknown"),
                        source_id=raw_source_id,
                        external_id=raw_external_id,
                        metadata={
                            **candidate_metadata,
                            "unsafe_url_sha256": hashlib.sha256(
                                str(raw_url).encode()
                            ).hexdigest(),
                        },
                    )
                    try:
                        store.record_hit(
                            manifest=manifest,
                            query=query,
                            run_id=run_id,
                            attempt_id=attempt_id,
                            ordinal=ordinal,
                            candidate=candidate,
                            policy_disposition="REJECTED_POLICY",
                            reason_code="UNSAFE_RESULT_URL",
                        )
                    except Exception:
                        finish_invoked_attempt(
                            query=query,
                            attempt_id=attempt_id,
                            adapter_id=adapter_id,
                            adapter_version=adapter_version,
                            upper_bound=upper_bound,
                            status="FAILED",
                            known_cost_usd=cost,
                            raw_hits=len(result_hits),
                            accepted_hits=accepted_attempt,
                            rejected_hits=rejected_attempt,
                            omitted_hits=omitted_hits,
                            error_category="DISCOVERY_HIT_WRITE_FAILED",
                            provider_receipt=receipt,
                        )
                        raise
                    rejected_attempt += 1
                    continue
                candidate = DiscoveryHitCandidate(
                    canonical_url=canonical_url,
                    title=str(raw_title or ""),
                    published_at=published_at,
                    source_family=str(raw_source_family or "unknown"),
                    source_id=raw_source_id,
                    external_id=raw_external_id,
                    metadata=candidate_metadata,
                )
                if metadata_rejected:
                    disposition, reason = "REJECTED_POLICY", "HIT_METADATA_INVALID"
                elif published_invalid:
                    disposition, reason = "REJECTED_POLICY", "PUBLISHED_AT_INVALID"
                else:
                    disposition, reason = _policy_disposition(
                        manifest=manifest,
                        query=query,
                        candidate=candidate,
                        canonical_url=canonical_url,
                        host=host,
                        seen_urls=seen_urls,
                        host_counts=host_counts,
                        accepted_total=accepted_total,
                        accepted_query=accepted_query,
                    )
                try:
                    hit = store.record_hit(
                        manifest=manifest,
                        query=query,
                        run_id=run_id,
                        attempt_id=attempt_id,
                        ordinal=ordinal,
                        candidate=candidate,
                        policy_disposition=disposition,
                        reason_code=reason,
                    )
                except Exception:
                    finish_invoked_attempt(
                        query=query,
                        attempt_id=attempt_id,
                        adapter_id=adapter_id,
                        adapter_version=adapter_version,
                        upper_bound=upper_bound,
                        status="FAILED",
                        known_cost_usd=cost,
                        raw_hits=len(result_hits),
                        accepted_hits=accepted_attempt,
                        rejected_hits=rejected_attempt,
                        omitted_hits=omitted_hits,
                        error_category="DISCOVERY_HIT_WRITE_FAILED",
                        provider_receipt=receipt,
                    )
                    raise
                actual = str(hit.get("disposition") or disposition)
                if actual in {"NEW_CONTENT", "EXISTING_CONTENT"}:
                    seen_urls.add(canonical_url)
                    host_counts[host] = host_counts.get(host, 0) + 1
                    accepted_total += 1
                    accepted_query += 1
                    accepted_attempt += 1
                else:
                    if actual == "DUPLICATE_WITHIN_RUN":
                        seen_urls.add(canonical_url)
                    rejected_attempt += 1
            finish_invoked_attempt(
                query=query,
                attempt_id=attempt_id,
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                upper_bound=upper_bound,
                status="HEALTHY",
                known_cost_usd=cost,
                raw_hits=len(result_hits),
                accepted_hits=accepted_attempt,
                rejected_hits=rejected_attempt,
                omitted_hits=omitted_hits,
                provider_receipt=receipt,
            )

    return store.complete_run(run_id)


__all__ = [
    "ConfiguredRegistryDiscoveryAdapter",
    "DiscoveryAdapter",
    "DiscoveryAdapterError",
    "DiscoveryAdapterRequest",
    "DiscoveryAdapterResult",
    "DiscoveryHitCandidate",
    "DiscoveryManifest",
    "DiscoveryManifestError",
    "DiscoveryQuery",
    "DiscoveryRunReceipt",
    "DiscoverySeed",
    "MANIFEST_VERSION",
    "ResearchDiscoveryStore",
    "canonicalize_discovery_url",
    "load_discovery_manifest",
    "new_discovery_run_id",
    "receipt_from_dict",
    "run_discovery_manifest",
    "sanitize_category",
]

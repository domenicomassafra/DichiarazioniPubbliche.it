from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any


RETRIEVAL_VERSION = "official-query-v1"

_ID = re.compile(r"^[A-Za-z0-9_.@:-]{1,120}$")
_SDMX_KEY = re.compile(r"^[A-Za-z0-9_.@*+-]{1,500}$")
_DATASET = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
_FILTER_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
_FILTER_VALUE = re.compile(r"^[A-Za-z0-9_.:@+ -]{1,200}$")
_PARLIAMENT_RESOURCE = re.compile(
    r"^https?://(?:dati\.camera\.it|dati\.senato\.it)/[A-Za-z0-9_./:%#?=&+~-]{1,600}$"
)


@dataclass(frozen=True)
class CompiledEvidenceRequest:
    source_id: str
    method: str
    url: str
    body: bytes | None
    content_type: str | None
    retrieval_method: str
    retrieval_version: str = RETRIEVAL_VERSION


def _bounded_text(value: Any, *, name: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name}_REQUIRED")
    if len(text) > maximum:
        raise ValueError(f"{name}_TOO_LONG")
    if "\x00" in text:
        raise ValueError(f"{name}_NUL_REFUSED")
    return text


def _match(pattern: re.Pattern[str], value: Any, *, name: str) -> str:
    text = _bounded_text(value, name=name, maximum=1000)
    if not pattern.fullmatch(text):
        raise ValueError(f"{name}_INVALID")
    return text


def compile_istat_sdmx(params: dict[str, Any]) -> CompiledEvidenceRequest:
    flow_ref = _match(_ID, params.get("flow_ref"), name="FLOW_REF")
    key = _match(_SDMX_KEY, params.get("key"), name="SDMX_KEY")
    provider_ref = str(params.get("provider_ref") or "all").strip()
    if not _ID.fullmatch(provider_ref):
        raise ValueError("PROVIDER_REF_INVALID")
    query: list[tuple[str, str]] = []
    start = str(params.get("start_period") or "").strip()
    end = str(params.get("end_period") or "").strip()
    if start:
        query.append(("startPeriod", _bounded_text(start, name="START_PERIOD", maximum=32)))
    if end:
        query.append(("endPeriod", _bounded_text(end, name="END_PERIOD", maximum=32)))
    detail = str(params.get("detail") or "dataonly").strip()
    if detail not in {"full", "dataonly", "serieskeysonly", "nodata"}:
        raise ValueError("SDMX_DETAIL_INVALID")
    query.append(("detail", detail))
    path = "/".join(
        urllib.parse.quote(value, safe="@._*+-")
        for value in (flow_ref, key, provider_ref)
    )
    url = "https://esploradati.istat.it/SDMXWS/rest/data/" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    return CompiledEvidenceRequest(
        source_id="istat-sdmx",
        method="GET",
        url=url,
        body=None,
        content_type=None,
        retrieval_method="ISTAT_SDMX_DATA",
    )


def compile_eurostat_statistics(params: dict[str, Any]) -> CompiledEvidenceRequest:
    dataset = _match(_DATASET, params.get("dataset"), name="EUROSTAT_DATASET")
    language = str(params.get("lang") or "en").strip().lower()
    if language not in {"en", "de", "fr"}:
        raise ValueError("EUROSTAT_LANG_INVALID")
    query: list[tuple[str, str]] = [("lang", language)]
    filters = params.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("EUROSTAT_FILTERS_NOT_OBJECT")
    if len(filters) > 20:
        raise ValueError("EUROSTAT_TOO_MANY_FILTERS")
    for key in sorted(filters):
        if not _FILTER_KEY.fullmatch(str(key)):
            raise ValueError("EUROSTAT_FILTER_KEY_INVALID")
        raw_values = filters[key]
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        if len(values) > 50:
            raise ValueError("EUROSTAT_TOO_MANY_FILTER_VALUES")
        for raw in values:
            value = str(raw).strip()
            if not _FILTER_VALUE.fullmatch(value):
                raise ValueError("EUROSTAT_FILTER_VALUE_INVALID")
            query.append((str(key), value))
    since = str(params.get("since_time_period") or "").strip()
    until = str(params.get("until_time_period") or "").strip()
    if since:
        query.append(("sinceTimePeriod", _bounded_text(since, name="EUROSTAT_SINCE", maximum=32)))
    if until:
        query.append(("untilTimePeriod", _bounded_text(until, name="EUROSTAT_UNTIL", maximum=32)))
    url = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        + urllib.parse.quote(dataset, safe="._-")
        + "?"
        + urllib.parse.urlencode(query, doseq=True)
    )
    return CompiledEvidenceRequest(
        source_id="eurostat-api",
        method="GET",
        url=url,
        body=None,
        content_type=None,
        retrieval_method="EUROSTAT_STATISTICS_API",
    )


def compile_normattiva_simple_search(params: dict[str, Any]) -> CompiledEvidenceRequest:
    text = _bounded_text(
        params.get("text"),
        name="NORMATTIVA_SEARCH_TEXT",
        maximum=500,
    )
    page = int(params.get("page") or 1)
    page_size = int(params.get("page_size") or 10)
    if not 1 <= page <= 1000:
        raise ValueError("NORMATTIVA_PAGE_INVALID")
    if not 1 <= page_size <= 20:
        raise ValueError("NORMATTIVA_PAGE_SIZE_INVALID")
    order = str(params.get("order") or "recente").strip().lower()
    if order not in {"recente", "vecchio"}:
        raise ValueError("NORMATTIVA_ORDER_INVALID")
    payload = {
        "testoRicerca": text,
        "orderType": order,
        "paginazione": {
            "paginaCorrente": page,
            "numeroElementiPerPagina": page_size,
        },
    }
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return CompiledEvidenceRequest(
        source_id="normattiva-opendata",
        method="POST",
        url=(
            "https://api.normattiva.it/t/normattiva.api/"
            "bff-opendata/v1/api/v1/ricerca/semplice"
        ),
        body=body,
        content_type="application/json",
        retrieval_method="NORMATTIVA_SIMPLE_SEARCH",
    )


def compile_parliament_resource_properties(
    source_id: str,
    params: dict[str, Any],
) -> CompiledEvidenceRequest:
    if source_id not in {"camera-linked-data", "senato-linked-data"}:
        raise ValueError("PARLIAMENT_SOURCE_INVALID")
    resource = _bounded_text(
        params.get("resource_uri"),
        name="RESOURCE_URI",
        maximum=700,
    )
    if not _PARLIAMENT_RESOURCE.fullmatch(resource):
        raise ValueError("RESOURCE_URI_INVALID")
    if source_id == "camera-linked-data" and "dati.camera.it/" not in resource:
        raise ValueError("CAMERA_RESOURCE_REQUIRED")
    if source_id == "senato-linked-data" and "dati.senato.it/" not in resource:
        raise ValueError("SENATO_RESOURCE_REQUIRED")
    limit = int(params.get("limit") or 100)
    if not 1 <= limit <= 500:
        raise ValueError("SPARQL_LIMIT_INVALID")
    query = (
        "SELECT ?predicate ?object WHERE { "
        f"<{resource}> ?predicate ?object . "
        "} ORDER BY ?predicate ?object "
        f"LIMIT {limit}"
    )
    endpoint = (
        "https://dati.camera.it/sparql"
        if source_id == "camera-linked-data"
        else "https://dati.senato.it/sparql"
    )
    url = endpoint + "?" + urllib.parse.urlencode(
        {"query": query, "format": "application/sparql-results+json"}
    )
    return CompiledEvidenceRequest(
        source_id=source_id,
        method="GET",
        url=url,
        body=None,
        content_type=None,
        retrieval_method="PARLIAMENT_RESOURCE_PROPERTIES",
    )


def compile_official_query(
    source_id: str,
    query_kind: str,
    params: dict[str, Any],
) -> CompiledEvidenceRequest:
    if not isinstance(params, dict):
        raise ValueError("QUERY_PARAMS_NOT_OBJECT")
    kind = str(query_kind or "").strip().upper()
    if source_id == "istat-sdmx" and kind == "SDMX_DATA":
        return compile_istat_sdmx(params)
    if source_id == "eurostat-api" and kind == "STATISTICS_DATA":
        return compile_eurostat_statistics(params)
    if source_id == "normattiva-opendata" and kind == "SIMPLE_SEARCH":
        return compile_normattiva_simple_search(params)
    if source_id in {"camera-linked-data", "senato-linked-data"} and kind == "RESOURCE_PROPERTIES":
        return compile_parliament_resource_properties(source_id, params)
    raise ValueError("OFFICIAL_QUERY_TEMPLATE_NOT_ALLOWED")
